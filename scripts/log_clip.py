"""One work-log row per finished clip, on any machine.

Every row is appended to <output_dir>/logs/clips_log.jsonl (always, so nothing is lost).
On a machine that also has the MoonRacle KB (config "moonracle_root", or ClipKit sitting next to
knowledge_base/), the row also goes straight into the central platform.work_logs table via worklog.py.
Team machines hand their clips_log.jsonl to the office, where `import` loads it into the central table.

    python scripts/log_clip.py add --project ClientA --item "EP07 burnout" --started-at 2026-10-02T09:10 \
        --minutes 38 --metadata '{"human_fix_min": 5, "final_len_s": 72}'
    python scripts/log_clip.py import D:\\handover\\clips_log.jsonl      # office machine only
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "capcut"))
import kitconfig  # noqa: E402

FIELDS = ["project", "item", "stage", "started_at", "minutes", "note", "problem", "cause", "fix", "artifact_url"]


def log_file() -> Path:
    base = kitconfig.CFG.get("output_dir") or kitconfig.CFG.get("work_root")
    if not base or not Path(base).is_dir():
        raise SystemExit("set the workspace folder in Settings first (output_dir missing)")
    d = Path(base) / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d / "clips_log.jsonl"


def worklog_script() -> Path | None:
    root = kitconfig.CFG.get("moonracle_root")
    cands = [Path(root)] if root else [ROOT.parent]
    for c in cands:
        p = c / "knowledge_base" / "scripts" / "worklog.py"
        if p.is_file():
            return p
    return None


def to_central(row: dict, wl: Path, dry: bool = False) -> None:
    """Send one row to platform.work_logs; raises on failure (never a quiet skip)."""
    meta = dict(row.get("metadata") or {})
    meta.update({"clipkit_id": row["id"], "editor": row.get("editor", ""), "machine": row.get("machine", "")})
    cmd = [sys.executable, str(wl), "add", "--agent", row.get("agent") or "claude", "--type", "video",
           "--project", row["project"], "--item", row["item"], "--stage", row.get("stage") or "done",
           "--method", "clipkit", "--metadata", json.dumps(meta, ensure_ascii=False)]
    for k in ("started_at", "minutes", "note", "problem", "cause", "fix", "artifact_url"):
        if row.get(k) not in (None, ""):
            cmd += ["--" + k.replace("_", "-"), str(row[k])]
    if dry:
        cmd.append("--dry-run")
    env = {**__import__("os").environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}  # Thai names
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    if r.returncode != 0:
        raise RuntimeError(f"worklog.py failed for {row['item']}: {(r.stderr or r.stdout).strip()[-300:]}")


def cmd_add(a) -> None:
    if a.problem and not (a.cause and a.fix):
        raise SystemExit("a problem row needs --cause and --fix too")
    import platform
    row = {"id": uuid.uuid4().hex[:12], "logged_at": datetime.now().isoformat(timespec="seconds"),
           "editor": kitconfig.CFG.get("editor_name", ""), "machine": platform.node(), "agent": a.agent,
           "metadata": json.loads(a.metadata) if a.metadata else {}}
    row.update({k: getattr(a, k) for k in FIELDS if getattr(a, k) is not None})
    path = log_file()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"saved to {path}")
    wl = worklog_script()
    if wl:
        to_central(row, wl, a.dry_run)
        if not a.dry_run:
            mark_imported(path, [row["id"]])
        print("checked against central work log (dry run)" if a.dry_run else "sent to central work log")
    else:
        print("no MoonRacle KB on this machine: hand clips_log.jsonl to the office for import")


def done_file(path: Path) -> Path:
    return path.with_suffix(".imported")


def mark_imported(path: Path, ids: list[str]) -> None:
    with done_file(path).open("a", encoding="utf-8") as f:
        f.writelines(i + "\n" for i in ids)


def cmd_import(a) -> None:
    wl = worklog_script()
    if not wl:
        raise SystemExit("import runs on the office machine (needs knowledge_base/scripts/worklog.py)")
    path = Path(a.file)
    done = set(done_file(path).read_text(encoding="utf-8").split()) if done_file(path).is_file() else set()
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    new = [r for r in rows if r["id"] not in done]
    for r in new:
        to_central(r, wl, a.dry_run)
        if not a.dry_run:
            mark_imported(path, [r["id"]])
    print(f"imported {len(new)} new row(s), {len(rows) - len(new)} already imported")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add")
    p.add_argument("--project", required=True)
    p.add_argument("--item", required=True)
    p.add_argument("--stage", default="done")
    p.add_argument("--agent", default="claude", help="registered agent name: claude or codex")
    p.add_argument("--started-at", dest="started_at")
    p.add_argument("--minutes", type=int)
    p.add_argument("--metadata")
    for k in ("note", "problem", "cause", "fix", "artifact_url"):
        p.add_argument("--" + k.replace("_", "-"), dest=k)
    i = sub.add_parser("import")
    i.add_argument("file")
    for x in (p, i):
        x.add_argument("--dry-run", action="store_true", help="check the row with worklog.py, write nothing central")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    {"add": cmd_add, "import": cmd_import}[a.cmd](a)


if __name__ == "__main__":
    main()
