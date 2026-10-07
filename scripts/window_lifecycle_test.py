"""Managed-window lifecycle checks; no server/process is started or stopped."""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from window_lifecycle import WindowLifecycle, window_router


def main():
    now = [0.0]
    life = WindowLifecycle(True, lambda: now[0])
    first, second = uuid4(), uuid4()
    now[0] = 119
    assert not life.should_stop()
    now[0] = 120
    assert life.should_stop()  # launcher never opened a window

    life.heartbeat(first)
    now[0] = 299
    assert not life.should_stop()
    now[0] = 300
    assert life.should_stop()  # crashed window's heartbeat expired

    life.heartbeat(first)
    life.release(first)
    now[0] = 314
    assert not life.should_stop()
    life.heartbeat(first)  # refresh reconnects before release grace expires
    now[0] = 316
    assert not life.should_stop()
    life.heartbeat(second)
    life.release(first)
    now[0] = 332
    assert life.status()["windows"] == 1
    assert not life.should_stop()  # another window remains open
    now[0] = 497
    life.request_started()
    assert not life.should_stop()
    life.request_finished()
    assert not life.should_stop(busy=True)
    assert life.should_stop()
    unmanaged = WindowLifecycle(False, lambda: now[0])
    now[0] = 1000
    assert not unmanaged.should_stop()

    app = FastAPI()
    app.include_router(window_router(life))
    with TestClient(app) as client:
        assert client.get("/api/window/watch?session_id=bad").status_code == 422
        assert client.get("/api/window/watch").status_code == 422
        assert client.get("/api/window/status").json() == {"managed": True, "windows": 0}

    async def stream_disconnect():
        watched = WindowLifecycle(True, lambda: now[0])
        watch = next(route.endpoint for route in window_router(watched).routes
                     if route.path == "/api/window/watch")
        response = await watch(session_id=first)
        stream = response.body_iterator
        assert '"managed": true' in await anext(stream)
        assert watched.status()["windows"] == 1
        await stream.aclose()  # browser disconnect/cancellation closes the generator
        now[0] += 14
        assert not watched.should_stop()
        now[0] += 1
        assert watched.should_stop()

    asyncio.run(stream_disconnect())
    app = FastAPI()
    app.include_router(window_router(unmanaged))
    with TestClient(app) as client:
        response = client.get(f"/api/window/watch?session_id={first}")
        assert response.status_code == 200 and '"managed": false' in response.text
    print("ok managed windows: startup, expiry, refresh, multiple windows, requests, jobs, validation, stream close")


if __name__ == "__main__":
    main()
