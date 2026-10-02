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
