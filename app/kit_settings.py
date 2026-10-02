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


class CoverRequest(BaseModel):
    source: str            # an image, or a video (a frame is taken at `at` seconds)
    at: float = 1.0
    l1: str
    l2: str = ""
    c1: str = "#ff7d00"
    s1: str = "#ffffff"
    c2: str = "#ffffff"
    s2: str = "#111111"
    layout: str = "cover-a"


@router.post("/cover")
def make_cover(body: CoverRequest) -> dict[str, Any]:
    """Render a 1080x1920 cover PNG from a motion/cover-* template into <output_dir>/covers."""
    import re
    import shutil
    import tempfile
    src = Path(body.source)
    if not src.is_file():
        raise HTTPException(400, f"file not found: {src}")
    tpl = KIT / "motion" / body.layout
    if not (tpl / "index.html").is_file() or not body.layout.startswith("cover-"):
        raise HTTPException(400, f"unknown cover layout: {body.layout}")
    if not body.l1.strip():
        raise HTTPException(400, "headline (l1) is empty")
    npx = shutil.which("npx")
    if not npx:
        raise HTTPException(400, "Node.js (npx) is not installed - run setup")
    cfg = _read_config()
    out_dir = Path(cfg.get("output_dir") or cfg.get("work_root") or "") / "covers"
    if not out_dir.parent.is_dir():
        raise HTTPException(400, "set the workspace folder in Settings first")
    out_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="clipkit_cover_"))
    shutil.copytree(tpl, work, dirs_exist_ok=True, ignore=shutil.ignore_patterns("preview-bg*"))
    bg = work / "preview-bg.jpg"
    if src.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920", str(bg)]
    else:
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(body.at), "-i", str(src), "-frames:v", "1",
               "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920", str(bg)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0 or not bg.is_file():
        raise HTTPException(500, "could not read the background: " + p.stderr.strip()[-300:])
    page = (work / "index.html").read_text(encoding="utf-8")
    bad = [v for v in (body.c1, body.s1, body.c2, body.s2) if not re.fullmatch(r"#[0-9a-fA-F]{6}", v)]
    if bad:
        raise HTTPException(400, f"colour must look like #ff7d00: {bad}")
    cover = json.dumps({"l1": body.l1, "l2": body.l2, "bg": "preview-bg.jpg",
                        "c1": body.c1, "s1": body.s1, "c2": body.c2, "s2": body.s2}, ensure_ascii=False)
    page, n = re.subn(r"const COVER = \{.*?\};", lambda _: f"const COVER = {cover};", page, count=1)
    if not n:
        raise HTTPException(500, "template has no COVER line")
    (work / "index.html").write_text(page, encoding="utf-8")
    frames = work / "_frames"
    env = {**__import__("os").environ, "HYPERFRAMES_SKIP_SKILLS": "1"}
    r = subprocess.run([npx, "--yes", f"hyperframes@{HF_VERSION}", "render", "--format", "png-sequence", "--quiet",
                        "-o", str(frames)], cwd=str(work), capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=600)
    first = sorted(frames.glob("*.png"))[:1] if frames.is_dir() else []
    if r.returncode != 0 or not first:
        raise HTTPException(500, "cover render failed: " + (r.stderr or r.stdout).strip()[-500:])
    name = re.sub(r'[\\/:*?"<>|]+', "", body.l1).strip()[:40] or "cover"
    target = out_dir / f"{name}.png"
    shutil.copy2(first[0], target)
    shutil.rmtree(work, ignore_errors=True)
    return {"file": str(target)}


MOTION_TEMPLATES = {"hook-title", "bps-sentence-pair"}   # transparent overlays with window.KIT params


class MotionRequest(BaseModel):
    template: str
    name: str              # output file name (no extension)
    params: dict[str, Any]


@router.post("/motion")
def make_motion(body: MotionRequest) -> dict[str, Any]:
    """Render a motion template with the user's words to a transparent MOV in <output_dir>/motion."""
    import re
    import shutil
    import tempfile
    if body.template not in MOTION_TEMPLATES:
        raise HTTPException(400, f"unknown motion template: {body.template}")
    npx = shutil.which("npx")
    if not npx:
        raise HTTPException(400, "Node.js (npx) is not installed - run setup")
    cfg = _read_config()
    out_dir = Path(cfg.get("output_dir") or cfg.get("work_root") or "") / "motion"
    if not out_dir.parent.is_dir():
        raise HTTPException(400, "set the workspace folder in Settings first")
    out_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="clipkit_motion_"))
    shutil.copytree(KIT / "motion" / body.template, work, dirs_exist_ok=True)
    page = (work / "index.html").read_text(encoding="utf-8")
    kit = json.dumps(body.params, ensure_ascii=False).replace("</", "<\\/")
    page, n = re.subn(r"<head>", lambda _: f"<head>\n<script>window.KIT = {kit};</script>", page, count=1)
    if not n:
        raise HTTPException(500, "template has no <head>")
    (work / "index.html").write_text(page, encoding="utf-8")
    name = re.sub(r'[\\/:*?"<>|]+', "", body.name).strip()[:40] or body.template
    target = out_dir / f"{name}.mov"
    env = {**__import__("os").environ, "HYPERFRAMES_SKIP_SKILLS": "1"}
    r = subprocess.run([npx, "--yes", f"hyperframes@{HF_VERSION}", "render", "--format", "mov", "--quiet",
                        "--workers", "4", "-o", str(target)], cwd=str(work), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=900)
    shutil.rmtree(work, ignore_errors=True)
    if r.returncode != 0 or not target.is_file():
        raise HTTPException(500, "motion render failed: " + (r.stderr or r.stdout).strip()[-500:])
    return {"file": str(target)}


class FramesRequest(BaseModel):
    source: str
    count: int = 6


_FRAME_DIR = Path(__import__("tempfile").gettempdir()) / "clipkit_cover_frames"


@router.post("/cover-frames")
def cover_frames(body: FramesRequest) -> dict[str, Any]:
    """Suggest cover frames: sample the clip, score each frame (sharp + bright enough + a face, bigger is better),
    return the best `count` spread across the clip."""
    import shutil
    try:
        import cv2
    except ImportError as exc:
        raise HTTPException(400, "opencv-python is not installed - run setup") from exc
    src = Path(body.source)
    if not src.is_file():
        raise HTTPException(400, f"file not found: {src}")
    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        raise HTTPException(400, "cannot read this video")
    face = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    samples = min(48, max(body.count * 4, total // int(fps)))  # about one per second, at most 48
    cands = []
    for i in range(samples):
        idx = int((i + 0.5) * total / samples)
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            continue
        small = cv2.resize(frame, (360, int(360 * frame.shape[0] / frame.shape[1])))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        sharp = cv2.Laplacian(gray, cv2.CV_64F).var()
        bright = gray.mean()
        faces = face.detectMultiScale(gray, 1.15, 5, minSize=(40, 40))
        area = max((w * h for (_x, _y, w, h) in faces), default=0) / (gray.shape[0] * gray.shape[1])
        score = sharp * (1.0 if 60 < bright < 200 else 0.4) * (1 + 20 * area) * (1.0 if len(faces) else 0.5)
        cands.append((score, idx / fps, small))
    cap.release()
    if not cands:
        raise HTTPException(400, "no readable frames in this video")
    # best first, but at least ~1.5 s apart so the choices are different moments
    chosen = []
    for c in sorted(cands, key=lambda c: -c[0]):
        if all(abs(c[1] - k[1]) >= 1.5 for k in chosen):
            chosen.append(c)
        if len(chosen) == body.count:
            break
    shutil.rmtree(_FRAME_DIR, ignore_errors=True)
    _FRAME_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for n, (_s, t, img) in enumerate(sorted(chosen, key=lambda c: c[1])):
        f = _FRAME_DIR / f"f{n}_{t:.2f}.jpg"
        cv2.imwrite(str(f), img)
        out.append({"at": round(t, 2), "thumb": f"/api/kit/cover-frame/{f.name}"})
    return {"frames": out}


@router.get("/frame")
def frame(source: str, at: float = 0.0):
    """One 1080x1920 JPEG from a video (or the image itself) for the live cover preview."""
    from fastapi.responses import Response
    src = Path(source)
    if not src.is_file():
        raise HTTPException(404, "file not found")
    seek = [] if src.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") else ["-ss", str(max(at, 0))]
    p = subprocess.run(["ffmpeg", "-v", "error", *seek, "-i", str(src), "-frames:v", "1",
                        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                        "-f", "image2", "-c:v", "mjpeg", "-q:v", "4", "pipe:1"], capture_output=True, timeout=60)
    if p.returncode != 0 or not p.stdout:
        raise HTTPException(500, "could not read a frame: " + p.stderr.decode(errors="replace")[-200:])
    return Response(p.stdout, media_type="image/jpeg")


@router.get("/cover-frame/{name}")
def cover_frame(name: str):
    from fastapi.responses import FileResponse
    p = _FRAME_DIR / Path(name).name
    if not p.is_file():
        raise HTTPException(404, "frame not found")
    return FileResponse(str(p))


@router.get("/cover-file")
def cover_file(path: str):
    """Serve a rendered cover so the page can show it (only files under a covers folder)."""
    from fastapi.responses import FileResponse
    p = Path(path)
    if p.parent.name != "covers" or p.suffix.lower() != ".png" or not p.is_file():
        raise HTTPException(404, "not a cover file")
    return FileResponse(str(p))


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


@router.post("/browse-file")
def browse_file(start: str = "") -> dict[str, str]:
    """Native file picker (video or image) on this machine."""
    script = ("import tkinter as t,tkinter.filedialog as f,sys;r=t.Tk();r.withdraw();r.attributes('-topmost',1);"
              "print(f.askopenfilename(initialdir=sys.argv[1] or None,filetypes=[('Video / image','*.mov *.mp4 *.mkv "
              "*.jpg *.jpeg *.png *.webp'),('All','*.*')]) or '')")
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
