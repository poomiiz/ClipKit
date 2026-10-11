"""Explicit host controls; closing a browser window never stops ClipKit."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse


def launch_control(action: str, port: int) -> None:
    if action not in {"restart", "shutdown"} or not 1 <= port <= 65535:
        raise ValueError("Invalid ClipKit control action")
    here = Path(__file__).resolve().parent
    with (here / "control.log").open("ab") as log:
        subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                          str(here / "control.ps1"), "-Action", action, "-Port", str(port),
                          "-Python", sys.executable, "-ExpectedPid", str(os.getpid()),
                          "-IssuedAt", str(int(time.time()))],
                         cwd=str(here), stdout=log, stderr=subprocess.STDOUT,
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)


def window_router(port: int, exit_server: Callable[[], None],
                  busy: Callable[[], bool], ready: Callable[[], bool]) -> APIRouter:
    router = APIRouter(prefix="/api/window", tags=["window"])

    @router.get("/watch")
    def watch():
        # Cached clients close their former lease connection after this single event.
        return StreamingResponse(iter(['data: {"managed": false, "windows": 0}\n\n']),
                                 media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store"})

    @router.get("/status")
    def status():
        return {"managed": False, "windows": 0}

    @router.get("/health")
    def health():
        return {"ready": ready(), "managed": False, "instance": os.getpid(), "busy": busy()}

    def control(action: str, control_version: str):
        # Cached pages from before explicit controls must not issue a delayed restart.
        if control_version != "v2":
            raise HTTPException(409, "หน้านี้เก่าเกินไป กรุณารีเฟรช ClipKit ก่อนสั่งระบบ")
        try:
            launch_control(action, port)
        except OSError as exc:
            raise HTTPException(503, "เปิดตัวควบคุม ClipKit ไม่ได้") from exc
        return {"action": action, "accepted": True, "instance": os.getpid()}

    @router.post("/restart", status_code=202)
    def restart(control_version: str = Query("", alias="control")):
        return control("restart", control_version)

    @router.post("/shutdown", status_code=202)
    def shutdown(control_version: str = Query("", alias="control")):
        return control("shutdown", control_version)

    @router.post("/exit", status_code=202, include_in_schema=False)
    def exit_after_response(instance: int, background_tasks: BackgroundTasks):
        if instance != os.getpid():
            raise HTTPException(409, "ClipKit instance changed")
        background_tasks.add_task(exit_server)
        return {"accepted": True}

    return router
