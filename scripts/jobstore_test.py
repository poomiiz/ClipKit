"""Job status survives a restart: a finished job keeps its result, a running one comes back as interrupted.
Run: python scripts/jobstore_test.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import jobstore

with tempfile.TemporaryDirectory() as d:
    jobstore.STATE = Path(d) / "state"
    jobs = jobstore.JobStore("kit")
    assert not jobs, "new store must start empty"
    jobs["update"] = {"status": "done", "log": "ok\n", "code": 0}
    jobs["doctor"] = {"status": "running", "log": "checking\n"}
    jobs.save()
    stories = jobstore.JobStore("story-plan", failed="error")
    stories["a.mp4"] = {"status": "running", "step": "ถอดเสียง"}
    stories.save()

    again = jobstore.JobStore("kit")
    assert again["update"] == {"status": "done", "log": "ok\n", "code": 0}, again["update"]
    assert again["doctor"]["status"] == "failed", again["doctor"]
    assert again["doctor"]["log"].endswith(jobstore.INTERRUPTED), again["doctor"]["log"]
    s = jobstore.JobStore("story-plan", failed="error")["a.mp4"]
    assert s["status"] == "error" and s["error"] == jobstore.INTERRUPTED, s
    assert sorted(p.name for p in jobstore.STATE.iterdir()) == ["jobs-kit.json", "jobs-story-plan.json"]

    (jobstore.STATE / "jobs-bad.json").write_text("{not json", encoding="utf-8")
    try:
        jobstore.JobStore("bad")
    except ValueError:
        pass
    else:
        raise AssertionError("a broken state file must raise, not be skipped")
print("PASS jobstore: finished jobs kept, running jobs marked interrupted, broken file raises")
