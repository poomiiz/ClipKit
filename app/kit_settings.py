"""Settings API for the ClipKit app: machine check, setup, config folders, Envato login, update.

Local tool only (the app binds 127.0.0.1). Long jobs (setup, update, login) run in the background
and report through GET /api/kit/job/{name}.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

KIT = Path(__file__).resolve().parents[1]
CONFIG = KIT / "config.json"
EXAMPLE = KIT / "config.example.json"

# keys the settings page may edit; everything else in config.json is kept untouched
FOLDER_KEYS = ["work_root", "capcut_drafts", "stock_video", "stock_music", "sfx", "output_dir"]
TEXT_KEYS = ["card_font", "envato_backend", "whisper_device", "whisper_model", "bot_api_url", "workspace"]
# standard layout under one workspace folder: every machine in the team looks the same
WORKSPACE_LAYOUT = {"work_root": "footage", "stock_video": "stock\\video", "stock_music": "stock\\music",
                    "sfx": "sfx", "output_dir": "output"}


def capcut_default_drafts() -> str:
    """CapCut's own default drafts folder on this Windows user, or '' if CapCut never created it."""
    import os
    d = Path(os.environ.get("LOCALAPPDATA", "")) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"
    return str(d) if d.is_dir() else ""

router = APIRouter(prefix="/api/kit", tags=["kit-settings"])
_jobs: dict[str, dict[str, Any]] = {}


def _read_config() -> dict[str, Any]:
    src = CONFIG if CONFIG.is_file() else EXAMPLE
    return json.loads(src.read_text(encoding="utf-8-sig"))


def _run_job(name: str, cmd: list[str], cwd: Path = KIT) -> None:
    job = _jobs[name] = {"status": "running", "log": "", "started": time.time()}
    try:
        p = subprocess.Popen(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace")
        for line in p.stdout:
            job["log"] += line
        p.wait()
        job["status"] = "done" if p.returncode == 0 else "failed"
        job["code"] = p.returncode
    except Exception as exc:  # report, never swallow
        job["status"] = "failed"
        job["log"] += f"\n{exc}"


def _start(name: str, cmd: list[str]) -> dict[str, Any]:
    if _jobs.get(name, {}).get("status") == "running":
        raise HTTPException(409, f"{name} is already running")
    threading.Thread(target=_run_job, args=(name, cmd), daemon=True).start()
    return {"job": name, "status": "running"}


@router.get("/doctor")
def doctor(asr: bool = False) -> dict[str, Any]:
    """Run scripts/doctor.py and return one row per check."""
    cmd = [sys.executable, str(KIT / "scripts" / "doctor.py")] + (["--asr"] if asr else [])
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    rows = []
    for line in p.stdout.splitlines():
        state, rest = line[:4].strip(), line[5:]
        if state in ("OK", "FAIL", "WARN"):
            rows.append({"state": state, "name": rest[:18].strip(), "detail": rest[18:].strip()})
    if not rows:
        raise HTTPException(500, f"doctor produced no result: {p.stderr.strip()[-400:]}")
    return {"ok": p.returncode == 0, "checks": rows}


@router.get("/config")
def get_config() -> dict[str, Any]:
    cfg = _read_config()
    return {"exists": CONFIG.is_file(), "folders": {k: cfg.get(k, "") for k in FOLDER_KEYS},
            "options": {k: cfg.get(k, "") for k in TEXT_KEYS}, "layout": WORKSPACE_LAYOUT}


class ConfigUpdate(BaseModel):
    values: dict[str, str]


@router.post("/config")
def save_config(body: ConfigUpdate) -> dict[str, Any]:
    cfg = _read_config()
    bad = [k for k in body.values if k not in FOLDER_KEYS + TEXT_KEYS]
    if bad:
        raise HTTPException(400, f"unknown setting: {', '.join(bad)}")
    missing = [f"{k}={v}" for k, v in body.values.items() if k in FOLDER_KEYS and v and not Path(v).is_dir()]
    if missing:
        raise HTTPException(400, "folder not found: " + "; ".join(missing))
    cfg.update({k: v for k, v in body.values.items()})
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"saved": True, "note": "restart the app for scripts already running to pick up new paths"}


class Workspace(BaseModel):
    root: str


@router.post("/workspace")
def set_workspace(body: Workspace) -> dict[str, Any]:
    """Pick one workspace folder: create the standard subfolders and point every path at them."""
    root = Path(body.root.strip())
    if not body.root.strip() or not root.anchor:
        raise HTTPException(400, "choose a full folder path, e.g. D:\\ClipKit")
    if not Path(root.anchor).exists():
        raise HTTPException(400, f"drive not found: {root.anchor}")
    cfg = _read_config()
    paths = {k: str(root / sub) for k, sub in WORKSPACE_LAYOUT.items()}
    for p in paths.values():
        Path(p).mkdir(parents=True, exist_ok=True)
    cfg.update(paths)
    cfg["workspace"] = str(root)
    if not cfg.get("capcut_drafts") or not Path(cfg["capcut_drafts"]).is_dir():
        found = capcut_default_drafts()
        if found:
            cfg["capcut_drafts"] = found
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"saved": True, "paths": paths, "capcut_drafts": cfg.get("capcut_drafts", "")}


class HyperframesRequest(BaseModel):
    file: str
    name: str


HF_VERSION = "0.8.101"
HF_PORT = 3002
_hf_preview: dict[str, Any] = {}


@router.post("/hyperframes")
def hyperframes_project(body: HyperframesRequest) -> dict[str, Any]:
    """Create a HyperFrames project from a raw clip under <output_dir>/hyperframes and open its Studio."""
    import re
    import shutil
    src = Path(body.file)
    if not src.is_file():
        raise HTTPException(400, f"file not found: {src}")
    if not shutil.which("npx"):
        raise HTTPException(400, "Node.js (npx) is not installed - run setup or install Node.js 22+")
    cfg = _read_config()
    base = cfg.get("output_dir") or cfg.get("work_root")
    if not base or not Path(base).is_dir():
        raise HTTPException(400, "set the workspace folder in Settings first")
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", body.name).strip("-").lower() or "clip"
    root = Path(base) / "hyperframes"
    root.mkdir(parents=True, exist_ok=True)
    project = root / slug
    env = {**__import__("os").environ, "HYPERFRAMES_SKIP_SKILLS": "1"}
    npx = shutil.which("npx")
    if not project.exists():
        p = subprocess.run([npx, "--yes", f"hyperframes@{HF_VERSION}", "init", slug, "--example", "blank",
                            "--video", str(src), "--resolution", "portrait", "--skip-transcribe", "--non-interactive"],
                           cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=env, timeout=900)
        if p.returncode != 0 or not (project / "index.html").is_file():
            raise HTTPException(500, "hyperframes init failed: " + (p.stderr or p.stdout).strip()[-600:])
    old = _hf_preview.get("proc")
    if old and old.poll() is None:
        old.terminate()
    _hf_preview["proc"] = subprocess.Popen(
        [npx, "--yes", f"hyperframes@{HF_VERSION}", "preview", "--port", str(HF_PORT), "--no-open"],
        cwd=str(project), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    import urllib.request
    for _ in range(60):  # wait until the studio answers
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{HF_PORT}/", timeout=1)
            break
        except Exception:
            time.sleep(1)
    else:
        raise HTTPException(500, f"HyperFrames studio did not start on port {HF_PORT}")
    return {"project": str(project), "url": f"http://localhost:{HF_PORT}/#project/{slug}"}


@router.get("/capcut-detect")
def capcut_detect() -> dict[str, str]:
    return {"path": capcut_default_drafts()}


@router.post("/browse")
def browse(start: str = "") -> dict[str, str]:
    """Native folder picker on this machine (the app is local-only)."""
    script = ("import tkinter as t,tkinter.filedialog as f,sys;r=t.Tk();r.withdraw();r.attributes('-topmost',1);"
              "print(f.askdirectory(initialdir=sys.argv[1] or None) or '')")
    p = subprocess.run([sys.executable, "-c", script, start], capture_output=True, text=True, encoding="utf-8",
                       timeout=600)
    return {"path": p.stdout.strip().replace("/", "\\")}


@router.post("/setup")
def run_setup() -> dict[str, Any]:
    return _start("setup", ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                            str(KIT / "scripts" / "setup.ps1")])


@router.post("/envato-login")
def envato_login() -> dict[str, Any]:
    return _start("envato-login", [sys.executable, str(KIT / "scripts" / "envato.py"), "login"])


@router.post("/update")
def update() -> dict[str, Any]:
    if not (KIT / ".git").is_dir():
        raise HTTPException(400, "this copy is not a git clone - download a fresh copy from GitHub")
    return _start("update", ["git", "pull", "--ff-only"])


@router.get("/job/{name}")
def job(name: str) -> dict[str, Any]:
    if name not in _jobs:
        return {"job": name, "status": "idle", "log": ""}
    j = _jobs[name]
    return {"job": name, "status": j["status"], "log": j["log"][-6000:]}


@router.get("/version")
def version() -> dict[str, Any]:
    meta = json.loads((KIT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    commit = subprocess.run(["git", "-C", str(KIT), "log", "-1", "--format=%h %cs"], capture_output=True,
                            text=True).stdout.strip()
    return {"version": meta.get("version"), "commit": commit}
