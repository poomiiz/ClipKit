"""Trial-scoped pipeline measurements. Sum attempt totals, never nested step times."""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


class TimingLog:
    def __init__(self, path: Path, video: str, trial_id: str | None = None):
        self.path = Path(path)
        self.trial_id = trial_id or uuid.uuid4().hex
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", self.trial_id):
            raise ValueError("trial-id must be 1-80 letters, digits, dots, hyphens or underscores")
        source = Path(video).resolve()
        self.video = source.name
        self.source_id = hashlib.sha256(str(source).encode("utf-8")).hexdigest()
        self.run_id = uuid.uuid4().hex
        self.depth = 0
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("trial_id") == self.trial_id and row.get("source_id") != self.source_id:
                    raise ValueError(f"trial-id {self.trial_id} already belongs to another source")

    def record(self, event: str, **fields) -> None:
        row = {"schema_version": 2, "time": datetime.now(timezone.utc).isoformat(),
               "trial_id": self.trial_id, "run_id": self.run_id, "video": self.video,
               "source_id": self.source_id, "event": event, **fields}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")

    def timed(self, name: str, fn, *args, **kw):
        started = time.perf_counter()
        depth = self.depth
        self.depth += 1
        outcome = "error"
        try:
            result = fn(*args, **kw)
            outcome = "ok"
            return result
        finally:
            self.depth -= 1
            self.record("step", step=name, s=round(time.perf_counter() - started, 6),
                        outcome=outcome, depth=depth)

    def run(self, fn, *args, **kw) -> int:
        self.record("run_start")
        started = time.perf_counter()
        code = None
        try:
            code = fn(*args, **kw)
            return code
        finally:
            self.record("run_end", s=round(time.perf_counter() - started, 6), exit_code=code,
                        outcome="ok" if code == 0 else "waiting" if code == 2 else "error")
