"""Managed-window lifecycle checks; no server/process is started or stopped."""
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
        assert client.post("/api/window/heartbeat", json={"session_id": str(first)}).json()["windows"] == 1
        assert client.post("/api/window/release", content='{"session_id":"' + str(first) + '"}',
                           headers={"content-type": "text/plain"}).status_code == 200
        for payload in ({"session_id": "bad"}, {}, [], {"session_id": 10}):
            assert client.post("/api/window/heartbeat", json=payload).status_code == 400
        assert client.post("/api/window/release", content="x" * 257).status_code == 400
    print("ok managed windows: startup, expiry, refresh, multiple windows, requests, jobs, validation")


if __name__ == "__main__":
    main()
