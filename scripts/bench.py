"""Summarize the editing-time benchmark (docs/benchmark.md): the sheet the editors fill in, plus the machine
time run_clip.py logs per step in <output>/logs/timings.jsonl.

    python scripts/bench.py docs/benchmark-sheet.csv
    python scripts/bench.py my-sheet.csv --timings "<output>/logs/timings.jsonl"

Per (length group, format): average manual minutes vs EditorKrab minutes, the % of editor time saved and how
many times faster. Editor time = human minutes only (the machine runs unattended); wall clock adds machine time.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

MODES = ("manual", "editorkrab")


def machine_minutes(timings: Path) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for line in timings.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["video"]] += r["s"] / 60
    return out


def summarize(rows: list[dict], machine: dict[str, float]) -> list[dict]:
    groups: dict[tuple, dict[str, list]] = defaultdict(lambda: {m: [] for m in MODES})
    for r in rows:
        mode = r["mode"].strip().lower()
        if mode not in MODES:
            raise SystemExit(f"{r['video']}: mode must be manual or editorkrab, got {r['mode']!r}")
        if r["qc_pass"].strip().lower() != "y":
            raise SystemExit(f"{r['video']}: did not pass the quality checklist; finish it or drop the row")
        m = 0.0
        if mode == "editorkrab":
            if r["video"] not in machine:
                raise SystemExit(f"{r['video']}: no machine time in timings.jsonl (was it made with run_clip.py?)")
            m = machine[r["video"]]
        groups[(r["length_group"], r["format"])][mode].append((float(r["human_min"]), m, int(r["fixes"] or 0)))
    out = []
    for (length, fmt), g in sorted(groups.items()):
        if not g["manual"] or not g["editorkrab"]:
            raise SystemExit(f"{length} min {fmt}: needs at least one manual and one editorkrab row")
        avg = lambda xs, i: sum(x[i] for x in xs) / len(xs)  # noqa: E731
        man, ek_h, ek_m = avg(g["manual"], 0), avg(g["editorkrab"], 0), avg(g["editorkrab"], 1)
        out.append({"length_min": length, "format": fmt, "n": f"{len(g['manual'])}/{len(g['editorkrab'])}",
                    "manual_min": round(man, 1), "ek_human_min": round(ek_h, 1), "ek_machine_min": round(ek_m, 1),
                    "editor_time_saved_pct": round(100 * (man - ek_h) / man), "faster_x": round(man / ek_h, 1),
                    "wall_clock_saved_pct": round(100 * (man - ek_h - ek_m) / man),
                    "fixes_avg": round(avg(g["editorkrab"], 2), 1)})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Summarize the editing-time benchmark.")
    ap.add_argument("sheet")
    ap.add_argument("--timings", help="timings.jsonl (default: <output>/logs/timings.jsonl from config.json)")
    a = ap.parse_args()
    if a.timings:
        timings = Path(a.timings)
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import cutlog
        timings = cutlog.logs_dir() / "timings.jsonl"
    with open(a.sheet, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    res = summarize(rows, machine_minutes(timings))
    cols = list(res[0])
    print("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols))
    for r in res:
        print("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
