"""Job status kept in a JSON file on this machine (state/), so a restart shows which jobs were cut off
instead of forgetting them. Written atomically; a job still marked running at load was interrupted."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import atomic

STATE = Path(__file__).resolve().parent.parent / "state"
INTERRUPTED = "หยุดกลางทางเพราะ EditorKrab ถูกปิดหรือรีสตาร์ต ลองสั่งใหม่อีกครั้ง"


class JobStore(dict[str, dict[str, Any]]):
    def __init__(self, name: str, failed: str = "failed") -> None:
        super().__init__()
        self.path = STATE / f"jobs-{name}.json"
        self._lock = threading.Lock()
        if self.path.is_file():
            jobs = json.loads(self.path.read_text(encoding="utf-8"))   # a broken file is a bug to see, not to skip
            for job in jobs.values():
                if job.get("status") == "running":
                    job.update(status=failed, error=INTERRUPTED)
                    if "log" in job:
                        job["log"] += "\n" + INTERRUPTED
            self.update(jobs)

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(exist_ok=True)
            atomic.write_text(self.path, json.dumps({k: dict(v) for k, v in self.items()}, ensure_ascii=False, indent=1))
