"""Opt-in Mac acceptance for this checkout's server on an unused test port."""
from __future__ import annotations
import json
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    if sys.platform != "darwin" or "--live" not in sys.argv:
        print("SKIP native Mac lifecycle: run on macOS with --live")
        return
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    sys.path.insert(0, str(ROOT / "app"))
    import control
    owner = None
    command = [sys.executable, str(ROOT / "app" / "control.py"), "--port", str(port),
               "--python", sys.executable]

    def invoke(action: str) -> dict:
        args = ([str(ROOT / "start.command"), "--port", str(port), "--no-open"] if action == "start"
                else command + ["--action", action])
        result = subprocess.run(args, capture_output=True,
                                text=True, timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout)

    try:
        first = invoke("start")
        owner = control.port_owner(port)
        assert owner and first["instance"] == owner.pid
        control.assert_owned(owner)
        assert control.health(port, owner)["ready"]
        assert invoke("start")["instance"] == owner.pid, "opening duplicated the server"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{port}/video-editor.html", timeout=5) as response:
            assert response.url.endswith("/login.html"), "editing page did not require sign-in"
            assert "frame-ancestors 'self'" in response.headers["Content-Security-Policy"]
        second = invoke("restart")
        assert second["instance"] != first["instance"]
        owner = control.port_owner(port)
        assert owner and control.health(port, owner)["ready"]
        assert invoke("shutdown")["instance"] is None
        assert control.port_owner(port) is None and control.port_free(port)
        owner = None
    except Exception:
        for name in ("video_editor.log", "video_editor.out.log"):
            log = ROOT / "app" / name
            if log.is_file():
                print(name + ":\n" + log.read_text(encoding="utf-8", errors="replace")[-6000:], file=sys.stderr)
        raise
    finally:
        # A failed check may only stop the exact test instance it started.
        if owner:
            current = control.port_owner(port)
            if current and control.same_process(owner, current):
                result = subprocess.run(command + ["--action", "shutdown", "--expected-pid", str(owner.pid),
                                        "--expected-created", str(owner.created)],
                                        capture_output=True, text=True, timeout=90)
                assert result.returncode == 0, result.stdout + result.stderr
    print("PASS native Mac start, readiness, reuse, login gate, restart and graceful shutdown")


if __name__ == "__main__":
    main()
