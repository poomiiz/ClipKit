"""macOS host controller. It controls only this checkout's verified local Python server."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import host_platform
from host_platform import ProcessIdentity, process_identity, same_process

APP = Path(__file__).resolve().with_name("app.py")


def _validate(action: str, port: int, expected_pid: int, issued_at: int,
              expected_created: float | None) -> None:
    if (action not in {"start", "restart", "shutdown"} or type(port) is not int or
            not 1 <= port <= 65535 or type(expected_pid) is not int or expected_pid < 0):
        raise ValueError("Invalid EditorKrab control arguments")
    if expected_pid and (expected_created is None or expected_created <= 0):
        raise ValueError("An expected PID requires its creation time")
    if issued_at and not -5 <= time.time() - issued_at <= 20:
        raise RuntimeError("EditorKrab control command expired")


def port_owner(port: int) -> ProcessIdentity | None:
    result = subprocess.run(["/usr/sbin/lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
                            capture_output=True, text=True, timeout=10)
    if result.returncode not in {0, 1} or result.stderr.strip():
        raise RuntimeError("Could not verify the local port owner")
    lines = result.stdout.split()
    if any(not value.isdecimal() for value in lines):
        raise RuntimeError("Invalid port-owner response")
    owners = {int(value) for value in lines}
    if len(owners) > 1:
        raise RuntimeError("Port has multiple owners; refusing to control it")
    return process_identity(owners.pop()) if owners else None


def assert_owned(owner: ProcessIdentity) -> None:
    command = owner.command
    if (len(command) != 2 or not Path(command[0]).is_absolute() or
            not Path(command[1]).is_absolute() or Path(command[1]).resolve() != APP or
            str(Path(command[0]).resolve()) != owner.executable or
            not Path(owner.executable).name.casefold().startswith("python")):
        raise RuntimeError("Port is not owned by this EditorKrab Python server")


def _changed_fields(before: ProcessIdentity, current: ProcessIdentity) -> list[str]:
    return [name for name in ("pid", "created", "parent", "executable", "command")
            if getattr(before, name) != getattr(current, name)]


def assert_same(owner: ProcessIdentity) -> None:
    current = process_identity(owner.pid)
    if not same_process(owner, current):
        changed = ", ".join(_changed_fields(owner, current))
        raise RuntimeError(f"Process identity changed ({changed}); refusing to control a replacement")


def _request(port: int, path: str, method: str = "GET") -> dict:
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
    # Local control must never pass through HTTP_PROXY / a configured network proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=2) as response:
        return json.load(response)


def health(port: int, owner: ProcessIdentity) -> dict:
    assert_same(owner)
    result = _request(port, "/api/window/health")
    assert_same(owner)
    if result.get("instance") != owner.pid or result.get("created_at") != owner.created:
        raise RuntimeError("EditorKrab server identity changed")
    if not isinstance(result.get("busy"), bool) or not isinstance(result.get("ready"), bool):
        raise RuntimeError("EditorKrab did not report its readiness and job state")
    return result


def port_free(port: int) -> bool:
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def wait_ready(port: int, owner: ProcessIdentity, timeout: float = 60) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        assert_same(owner)
        current = port_owner(port)
        if current:
            assert_owned(current)
            if not same_process(owner, current):
                raise RuntimeError("Another process took the EditorKrab port")
            try:
                state = health(port, owner)
            except (OSError, ValueError):
                state = {}
            if state.get("ready"):
                return owner.pid
        time.sleep(0.25)
    raise RuntimeError("EditorKrab did not become ready; check video_editor.log")


def _capture_started_owner(port: int, launched: ProcessIdentity, timeout: float) -> ProcessIdentity:
    """Freeze identity after this exact spawned process has finished exec and binds its listener.

    CPython's macOS framework launcher re-execs its Python.app runtime with a different
    executable/argv[0]. PID, creation time, user (process_identity), and parent must remain
    unchanged throughout bootstrap. Existing listeners never use this allowance.
    """
    def same_birth(current: ProcessIdentity) -> None:
        changed = [name for name in ("pid", "created", "parent")
                   if getattr(launched, name) != getattr(current, name)]
        if changed:
            raise RuntimeError("Launched process identity changed (" + ", ".join(changed) +
                               "); refusing to adopt a replacement")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        same_birth(process_identity(launched.pid))
        listener = port_owner(port)
        if listener:
            same_birth(listener)
            assert_owned(listener)
            assert_same(listener)
            return listener
        time.sleep(0.25)
    raise RuntimeError("The launched EditorKrab process did not bind its port; check video_editor.log")


def start_server(port: int, python: str) -> int:
    executable = Path(python).expanduser()
    if not executable.is_absolute() or not executable.is_file():
        raise ValueError("Python must be an existing absolute executable path")
    if port_owner(port) or not port_free(port):
        raise RuntimeError("EditorKrab port is occupied; refusing to start another copy")
    env = {**os.environ, "VIDEO_EDITOR_PORT": str(port), "CLIPKIT_MANAGED_WINDOW": "0"}
    with (APP.parent / "video_editor.out.log").open("ab") as out, (
            APP.parent / "video_editor.log").open("ab") as err:
        proc = subprocess.Popen([str(executable), str(APP)], cwd=str(APP.parent), env=env,
                                stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                close_fds=True, start_new_session=True)
    deadline = time.monotonic() + 60
    launched = process_identity(proc.pid)
    owner = _capture_started_owner(port, launched, max(0, deadline - time.monotonic()))
    return wait_ready(port, owner, max(0, deadline - time.monotonic()))


def _children(owner: ProcessIdentity) -> list[ProcessIdentity]:
    import psutil
    excluded = {os.getpid(), *(child.pid for child in psutil.Process(os.getpid()).children(recursive=True))}
    return [process_identity(child.pid) for child in psutil.Process(owner.pid).children(recursive=True)
            if child.pid not in excluded]


def _wait_stopped(owner: ProcessIdentity, timeout: float = 20) -> None:
    import psutil
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            assert_same(owner)
        except psutil.NoSuchProcess:
            return
        time.sleep(0.25)
    # Busy or unresponsive servers are not force-killed.
    raise RuntimeError("EditorKrab did not exit gracefully; its process was preserved")


def _stop_children(children: list[ProcessIdentity]) -> None:
    import psutil
    for old in reversed(children):
        try:
            current = process_identity(old.pid)
            if same_process(old, current, reparented=True):
                proc = psutil.Process(old.pid)
                # psutil also checks PID reuse before delivering its signal.
                if same_process(old, process_identity(old.pid), reparented=True):
                    proc.terminate()
                    proc.wait(timeout=5)
        except psutil.NoSuchProcess:
            continue
        except psutil.TimeoutExpired as exc:
            raise RuntimeError("An owned helper did not stop; no replacement server was started") from exc


def invoke(action: str, port: int, python: str, expected_pid: int = 0, issued_at: int = 0,
           expected_created: float | None = None) -> dict:
    _validate(action, port, expected_pid, issued_at, expected_created)
    owner = port_owner(port)
    if expected_pid and (not owner or owner.pid != expected_pid or owner.created != expected_created):
        raise RuntimeError("EditorKrab instance changed before control ran")
    if owner:
        assert_owned(owner)
    if action == "start" and owner:
        # Opening the app while it is busy reuses it; it never interrupts that job.
        health(port, owner)
        _request(port, "/api/window/cancel-shutdown?control=v2", "POST")
        return {"state": "succeeded", "instance": wait_ready(port, owner)}
    if owner:
        state = health(port, owner)
        if state["busy"]:
            raise RuntimeError("EditorKrab has an active job; finish it before host control")
        children = _children(owner)
        if host_platform.server_has_active_helpers(owner):
            raise RuntimeError("EditorKrab has an active helper; finish it before host control")
        if expected_pid:
            time.sleep(0.5)  # let the original control response finish
        current = port_owner(port)
        if not current or not same_process(owner, current):
            raise RuntimeError("EditorKrab port owner changed")
        assert_same(owner)
        # The server checks both PID and creation time, and rechecks its busy state.
        _request(port, f"/api/window/exit?instance={owner.pid}&created_at={owner.created}", "POST")
        _wait_stopped(owner)
        _stop_children(children)
        replacement = port_owner(port)
        if replacement or not port_free(port):
            raise RuntimeError("Port did not become free; no replacement server was started")
    instance = None if action == "shutdown" else start_server(port, python)
    return {"state": "succeeded", "instance": instance}


@contextlib.contextmanager
def control_lock(port: int):
    import fcntl
    key = hashlib.sha256(f"{APP}|{port}".encode()).hexdigest()[:16]
    path = Path(tempfile.gettempdir()) / f"editorkrab-control-{os.getuid()}-{key}.lock"
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise RuntimeError("Unsafe EditorKrab control lock")
        deadline = time.monotonic() + 60
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Another EditorKrab control command is still running")
                time.sleep(0.25)
        yield
    finally:
        os.close(fd)  # releases the lock without unlinking a file another controller may use


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=("start", "restart", "shutdown"), default="start")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--expected-pid", type=int, default=0)
    parser.add_argument("--expected-created", type=float)
    parser.add_argument("--issued-at", type=int, default=0)
    args = parser.parse_args()
    try:
        if not host_platform.is_macos():
            raise RuntimeError("This controller is for macOS; use control.ps1 on Windows")
        _validate(args.action, args.port, args.expected_pid, args.issued_at, args.expected_created)
        with control_lock(args.port):
            result = invoke(args.action, args.port, args.python, args.expected_pid,
                            args.issued_at, args.expected_created)
        print(json.dumps(result))
        return 0
    except Exception as exc:
        print(json.dumps({"state": "failed", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
