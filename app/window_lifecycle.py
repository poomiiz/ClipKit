"""A managed launcher exits after its last browser window closes."""
from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request


class WindowLifecycle:
    def __init__(self, enabled: bool, clock: Callable[[], float] = time.monotonic):
        self.enabled = enabled
        self.clock = clock
        self.started = clock()
        self.seen_window = False
        self.leases: dict[UUID, float] = {}
        self.requests = 0
        self.lock = threading.Lock()

    def heartbeat(self, session_id: UUID) -> None:
        with self.lock:
            if self.enabled:
                # Background browser tabs throttle timers; normal close uses release.
                self.leases[session_id] = self.clock() + 180
                self.seen_window = True

    def release(self, session_id: UUID) -> None:
        with self.lock:
            if session_id in self.leases:
                # Refresh/navigation gets time to renew the same window's lease.
                self.leases[session_id] = min(self.leases[session_id], self.clock() + 15)

    def request_started(self) -> None:
        with self.lock:
            self.requests += 1

    def request_finished(self) -> None:
        with self.lock:
            self.requests -= 1

    def _prune(self, now: float) -> None:
        for session_id in list(self.leases):
            if self.leases[session_id] <= now:
                del self.leases[session_id]

    def should_stop(self, busy: bool = False) -> bool:
        with self.lock:
            now = self.clock()
            self._prune(now)
            return (self.enabled and not busy and self.requests == 0 and not self.leases
                    and (self.seen_window or now - self.started >= 120))

    def status(self) -> dict:
        with self.lock:
            self._prune(self.clock())
            return {"managed": self.enabled, "windows": len(self.leases)}


def window_router(lifecycle: WindowLifecycle) -> APIRouter:
    router = APIRouter(prefix="/api/window", tags=["window"])

    async def session(request: Request) -> UUID:
        # sendBeacon may use text/plain; validate its small JSON payload explicitly.
        raw = await request.body()
        if len(raw) > 256:
            raise HTTPException(400, "Invalid window session")
        try:
            body = json.loads(raw)
            return UUID(body["session_id"])
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise HTTPException(400, "Invalid window session") from exc

    @router.post("/heartbeat")
    async def heartbeat(request: Request):
        lifecycle.heartbeat(await session(request))
        return lifecycle.status()

    @router.post("/release")
    async def release(request: Request):
        lifecycle.release(await session(request))
        return lifecycle.status()

    @router.get("/status")
    def status():
        return lifecycle.status()

    return router
