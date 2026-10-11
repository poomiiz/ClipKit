#!/usr/bin/env python3
"""ClipKit Video -> CapCut. Local only: http://127.0.0.1:8770/video-editor.html"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

if sys.stdout:  # a Thai project name in a log line would stop the Autosave thread on a cp874/cp1252 console
    sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.responses import JSONResponse, RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from starlette.middleware.trustedhost import TrustedHostMiddleware  # noqa: E402

# first run on a new machine: create config.json from the example (same as setup.ps1) so the app can open
# and the Settings page can show what is still missing; the folders stay unset until the person picks them
_CFG = HERE.parent / "config.json"
if not _CFG.is_file():
    import shutil
    shutil.copyfile(HERE.parent / "config.example.json", _CFG)

# Windows: every helper the app starts (ffmpeg, npx, powershell, python) runs without a console window,
# otherwise a black terminal flashes up for each cover, motion render, check or file dialog
if os.name == "nt":
    import subprocess
    _Popen_init = subprocess.Popen.__init__

    def _no_window(self, *args, **kwargs):
        flags = kwargs.get("creationflags", 0)
        if not flags & subprocess.CREATE_NEW_CONSOLE:   # a window asked for on purpose (sign-in) stays visible
            flags |= subprocess.CREATE_NO_WINDOW
        kwargs["creationflags"] = flags
        _Popen_init(self, *args, **kwargs)
    subprocess.Popen.__init__ = _no_window

import kit_settings  # noqa: E402
import style_lab_api  # noqa: E402
import video_editor  # noqa: E402
from window_lifecycle import window_router  # noqa: E402

PORT = int(os.environ.get("VIDEO_EDITOR_PORT", "8770"))
WIDGET_ORIGINS = ("http://localhost:8765", "http://127.0.0.1:8765")


def jobs_running() -> bool:
    if any(job.get("status") == "running" for job in list(kit_settings._jobs.values())):
        return True
    if any(proc.poll() is None for proc in list(video_editor._transcribe_jobs.values())):
        return True
    return any(job.get("status") == "running" for job in list(video_editor._story_jobs.values()))


def exit_server():
    app.state.exit_requested = True
    app.state.server.should_exit = True

app = FastAPI(title="Video to CapCut", version="1.0.0")
app.state.exit_requested = False
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"], www_redirect=False)
app.include_router(video_editor.router)
app.include_router(kit_settings.router)
app.include_router(style_lab_api.router)
app.include_router(window_router(PORT, exit_server, jobs_running, lambda: not app.state.exit_requested))


@app.exception_handler(Exception)
async def report_crash(request, exc: Exception) -> JSONResponse:
    """A server error the code did not expect: tell the page, and send it to the team as an auto bug report."""
    import traceback
    from fastapi import HTTPException
    from starlette.concurrency import run_in_threadpool
    tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
    try:
        await run_in_threadpool(kit_settings.report_bug, f"[auto] {type(exc).__name__}: {exc}",
                                request.url.path, [line.strip()[:300] for line in tb[-10:]], True)
    except HTTPException as sent:
        print(f"auto bug report not sent: {sent.detail}", file=sys.stderr)
    return JSONResponse({"detail": f"{type(exc).__name__}: {exc}"}, status_code=500)


@app.middleware("http")
async def no_cache_html(request, call_next):
    # The local dashboard may embed pages, read readiness and use explicit host controls.
    origin = request.headers.get("origin")
    try:
        referrer = urlsplit(request.headers.get("referer", ""))
    except ValueError:
        return JSONResponse({"detail": "Invalid referrer"}, status_code=400)
    referrer_origin = f"{referrer.scheme}://{referrer.netloc}"
    is_page = request.url.path.endswith(".html") or request.url.path == "/"
    widget_navigation = (request.method == "GET" and is_page
                         and request.headers.get("sec-fetch-dest") == "iframe"
                         and request.headers.get("sec-fetch-mode") == "navigate"
                         and referrer_origin in WIDGET_ORIGINS
                         and (origin is None or origin in WIDGET_ORIGINS))
    widget_health = (request.method == "GET" and request.url.path == "/api/window/health"
                     and origin in WIDGET_ORIGINS)
    widget_control = (request.method == "POST" and request.url.path in
                      {"/api/window/restart", "/api/window/shutdown"} and origin in WIDGET_ORIGINS)
    foreign = ((origin is not None and origin != f"{request.url.scheme}://{request.url.netloc}")
               or request.headers.get("sec-fetch-site") == "cross-site")
    if foreign and not (widget_navigation or widget_health or widget_control):
        return JSONResponse({"detail": "Cross-origin requests are not allowed"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'self'" + (" " + " ".join(WIDGET_ORIGINS) if is_page else "")
    if widget_health or widget_control:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    if is_page:
        response.headers["Cache-Control"] = "no-store, must-revalidate"
    else:
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


@app.get("/", include_in_schema=False)
def home() -> RedirectResponse:
    return RedirectResponse("/video-editor.html")


# motion / cover templates, so the cover page can show a live preview of the real template
app.mount("/motion", StaticFiles(directory=str(HERE.parent / "motion"), html=True), name="motion")
app.mount("/ckfonts", StaticFiles(directory=str(HERE.parent / "fonts")), name="ckfonts")  # Kanit for the live player
app.mount("/", StaticFiles(directory=str(HERE / "static"), html=True), name="static")


def _watch_drafts() -> None:
    """ClipKit - Autosave: record every project CapCut saves (capcut_edit.watch), in a thread, on every machine.
    Stays on this machine; config.json "autosave": false turns it off."""
    import threading
    import capcut_edit
    cfg = kit_settings._read_config()
    if cfg.get("autosave", True) and cfg.get("capcut_drafts"):
        threading.Thread(target=capcut_edit.watch, args=(cfg["capcut_drafts"],), daemon=True).start()
        threading.Thread(target=_profile_daily, daemon=True).start()


def _profile_daily() -> None:
    """Remake the Autosave style profile (and presets/my-style.json) once a day; checked every hour."""
    import time
    sys.path.insert(0, str(HERE.parent / "scripts"))
    import autosave_profile
    while True:
        if kit_settings._read_config().get("output_dir"):
            autosave_profile.refresh()
        time.sleep(3600)


if __name__ == "__main__":
    _watch_drafts()
    if sys.stdout:  # pythonw (autostart) has no console
        print(f"Video -> CapCut: http://127.0.0.1:{PORT}/video-editor.html")
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="info",
                           log_config=None if sys.stderr is None else uvicorn.config.LOGGING_CONFIG,
                           timeout_graceful_shutdown=10))
    app.state.server = server
    server.run()
