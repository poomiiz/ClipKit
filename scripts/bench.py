"""Summarize balanced editing trials. Total elapsed time is observed, never inferred."""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

MODES = {"manual", "editorkrab"}
COLUMNS = ("trial_id", "pair_id", "video", "source_min", "length_group", "format", "mode", "editor",
           "order", "output_count", "output_min", "human_min", "elapsed_min", "fixes", "qc_pass", "notes")


def number(value, label: str, positive: bool = False) -> float:
    try:
        n = float(value)
    except (ValueError, TypeError):
        raise ValueError(f"{label}: needs a finite number") from None
    if isinstance(value, bool) or not math.isfinite(n) or n < 0 or (positive and n == 0):
        raise ValueError(f"{label}: needs a finite number {'>' if positive else '>='} 0")
    return n


def integer(value, label: str) -> int:
    n = number(value, label)
    if not n.is_integer():
        raise ValueError(f"{label}: needs a whole number")
    return int(n)


def machine_trials(path: Path, selected: set[str]) -> dict[str, dict]:
    """Select trial IDs; sum full attempts including retries, not nested step events."""
    trials, legacy = {}, 0
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"timings line {line_no}: needs an object")
        if "trial_id" not in row:
            legacy += 1
            continue
        tid = row["trial_id"]
        if tid not in selected:
            continue
        if row.get("schema_version") != 2 or row.get("event") not in {"run_start", "run_end", "step"}:
            raise ValueError(f"{tid}: unsupported timing record at line {line_no}")
        if any(not isinstance(row.get(k), str) or not row[k] for k in ("run_id", "source_id", "video")):
            raise ValueError(f"{tid}: timing record needs run_id, source_id and video")
        t = trials.setdefault(tid, {"video": row["video"], "source_id": row["source_id"],
                                   "minutes": 0.0, "starts": set(), "ends": set(), "runs": set(), "successful": False})
        if (t["video"], t["source_id"]) != (row["video"], row["source_id"]):
            raise ValueError(f"{tid}: multiple sources share this trial ID")
        rid, event = row["run_id"], row["event"]
        t["runs"].add(rid)
        if event == "step":
            if rid not in t["starts"] or rid in t["ends"]:
                raise ValueError(f"{tid}: step outside an active invocation")
            number(row.get("s"), f"{tid} step seconds")
            continue
        seen = t["starts"] if event == "run_start" else t["ends"]
        if rid in seen:
            raise ValueError(f"{tid}: duplicate {event} for invocation {rid}")
        seen.add(rid)
        if event == "run_end":
            if rid not in t["starts"]:
                raise ValueError(f"{tid}: run_end without a preceding run_start")
            code, outcome = row.get("exit_code"), row.get("outcome")
            if code is not None and (isinstance(code, bool) or not isinstance(code, int)):
                raise ValueError(f"{tid}: exit_code must be an integer or null")
            if outcome != ("ok" if code == 0 else "waiting" if code == 2 else "error"):
                raise ValueError(f"{tid}: exit code and outcome disagree")
            t["minutes"] += number(row.get("s"), f"{tid} invocation seconds") / 60
            t["successful"] |= outcome == "ok"
    if legacy:
        print(f"Ignored {legacy} legacy timing records without trial IDs.", file=sys.stderr)
    for t in trials.values():
        t["complete"] = t["runs"] == t["starts"] == t["ends"]
    return trials


def summarize(rows: list[dict], machine: dict[str, dict]) -> list[dict]:
    pairs, trial_ids, editor_sources, source_pairs = defaultdict(list), set(), set(), {}
    for line_no, original in enumerate(rows, 2):
        missing = set(COLUMNS) - set(original)
        if missing:
            raise ValueError(f"sheet: missing columns {', '.join(sorted(missing))}")
        r = {k: (v or "").strip() for k, v in original.items() if k is not None}
        for key in ("trial_id", "pair_id", "video", "editor"):
            if not r[key]:
                raise ValueError(f"sheet line {line_no}: {key} is required")
        tid = r["trial_id"]
        if tid in trial_ids:
            raise ValueError(f"{tid}: duplicate sheet trial ID")
        trial_ids.add(tid)
        if (r["editor"], r["video"]) in editor_sources:
            raise ValueError(f"{tid}: an editor saw the same source twice across the sheet")
        editor_sources.add((r["editor"], r["video"]))
        if r["video"] in source_pairs and source_pairs[r["video"]] != r["pair_id"]:
            raise ValueError(f"{tid}: source filenames must be unique across pairs")
        source_pairs[r["video"]] = r["pair_id"]
        for key in ("mode", "qc_pass", "format"):
            r[key] = r[key].lower()
        if r["mode"] not in MODES or r["qc_pass"] not in {"y", "n"}:
            raise ValueError(f"{tid}: mode must be manual/editorkrab and qc_pass must be y/n")
        if r["format"] != "short":
            raise ValueError(f"{tid}: this pipeline benchmark supports short outputs; long-form is unmeasured")
        length = integer(r["length_group"], f"{tid} length_group")
        if length not in {1, 5, 20, 60}:
            raise ValueError(f"{tid}: length_group must be 1/5/20/60")
        r["length_group"] = length
        r["source_min"] = number(r["source_min"], f"{tid} source_min", positive=True)
        if abs(r["source_min"] - length) > length * 0.1 + 1e-9:
            raise ValueError(f"{tid}: source duration is outside the length group's 10% tolerance")
        r["order"] = integer(r["order"], f"{tid} order")
        r["output_count"] = integer(r["output_count"], f"{tid} output_count")
        r["output_min"] = number(r["output_min"], f"{tid} output_min", positive=r["qc_pass"] == "y")
        if r["qc_pass"] == "y" and (r["output_count"] != 1 or not 0.5 <= r["output_min"] <= 1):
            raise ValueError(f"{tid}: this pilot requires exactly one 30-60 second short")
        r["human_min"] = number(r["human_min"], f"{tid} human_min", positive=r["mode"] == "manual")
        r["elapsed_min"] = number(r["elapsed_min"], f"{tid} elapsed_min", positive=True)
        if r["elapsed_min"] < r["human_min"]:
            raise ValueError(f"{tid}: elapsed_min cannot be less than active human_min")
        if r["mode"] == "editorkrab" and not r["fixes"]:
            raise ValueError(f"{tid}: fixes is required for editorkrab")
        r["fixes"] = integer(r["fixes"] or "0", f"{tid} fixes")
        t = machine.get(tid) if r["mode"] == "editorkrab" else None
        r["pipeline_min"] = None
        if t:
            if t["video"] != r["video"]:
                raise ValueError(f"{tid}: sheet video does not match the timing log")
            if t["complete"]:
                r["pipeline_min"] = t["minutes"]
                if t["minutes"] > r["elapsed_min"] + 0.1:
                    raise ValueError(f"{tid}: pipeline time exceeds observed elapsed time; check the trial IDs")
        if r["mode"] == "editorkrab" and r["qc_pass"] == "y" and (not t or not t["complete"] or not t["successful"]):
            raise ValueError(f"{tid}: needs complete timing attempts and a successful pipeline invocation")
        pairs[r["pair_id"]].append(r)
    groups = defaultdict(list)
    for pid, rs in pairs.items():
        if len(rs) != 4 or len({r["editor"] for r in rs}) != 2 or len({r["video"] for r in rs}) != 2:
            raise ValueError(f"{pid}: needs four trials, two editors and two source videos")
        if len({(r["editor"], r["video"]) for r in rs}) != 4:
            raise ValueError(f"{pid}: an editor saw the same source twice")
        if len({(r["length_group"], r["format"]) for r in rs}) != 1:
            raise ValueError(f"{pid}: pair spans different length groups or formats")
        for key in ("editor", "video"):
            for value in {r[key] for r in rs}:
                subset = [r for r in rs if r[key] == value]
                if {r["mode"] for r in subset} != MODES:
                    raise ValueError(f"{pid}: each {key} needs both modes across different trials")
                if key == "editor" and {r["order"] for r in subset} != {1, 2}:
                    raise ValueError(f"{pid}: each editor needs order 1 and 2")
                if key == "video" and len({r["source_min"] for r in subset}) != 1:
                    raise ValueError(f"{pid}: the same source has conflicting durations")
        if {r["mode"] for r in rs if r["order"] == 1} != MODES:
            raise ValueError(f"{pid}: alternate which mode each editor does first")
        if max(r["source_min"] for r in rs) > 1.1 * min(r["source_min"] for r in rs) + 1e-9:
            raise ValueError(f"{pid}: A/B source durations differ by more than 10%")
        delivered = [r for r in rs if r["qc_pass"] == "y"]
        if delivered:
            if max(r["output_min"] for r in delivered) > 1.1 * min(r["output_min"] for r in delivered) + 1e-9:
                raise ValueError(f"{pid}: delivered durations differ by more than 10%")
        groups[(rs[0]["length_group"], rs[0]["format"])].extend(rs)
    out = []
    for (length, fmt), rs in sorted(groups.items()):
        man = [r for r in rs if r["mode"] == "manual"]
        ek = [r for r in rs if r["mode"] == "editorkrab"]
        avg = lambda xs, key: sum(r[key] for r in xs) / len(xs)
        mh, eh = avg(man, "human_min"), avg(ek, "human_min")
        me, ee = avg(man, "elapsed_min"), avg(ek, "elapsed_min")
        failed = sum(r["qc_pass"] == "n" for r in rs)
        out.append({"length_min": length, "format": fmt, "pairs": len(rs) // 4, "trials": len(rs),
                    "qc_failed": failed, "status": "qc_failed" if failed else "pilot",
                    "manual_min": round(mh, 2), "ek_human_min": round(eh, 2),
                    "ek_pipeline_min": round(avg(ek, "pipeline_min"), 2) if all(r["pipeline_min"] is not None for r in ek) else "UNKNOWN",
                    "manual_elapsed_min": round(me, 2), "ek_elapsed_min": round(ee, 2),
                    "editor_time_saved_pct": round(100 * (mh - eh) / mh, 1) if not failed else "UNKNOWN",
                    "faster_x": round(mh / eh, 2) if not failed and eh else "UNKNOWN",
                    "wall_clock_saved_pct": round(100 * (me - ee) / me, 1) if not failed else "UNKNOWN",
                    "fixes_avg": round(avg(ek, "fixes"), 2)})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sheet")
    ap.add_argument("--timings", help="default: <output>/logs/timings.jsonl from config.json")
    args = ap.parse_args()
    try:
        with open(args.sheet, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not set(COLUMNS).issubset(reader.fieldnames or []):
                raise ValueError("sheet needs the current benchmark-sheet.csv header (trial IDs and elapsed time)")
            rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise ValueError("sheet rows must have exactly one cell per header column")
        if not rows:
            print("UNKNOWN: no human trials recorded yet.")
            return 0
        if args.timings:
            path = Path(args.timings)
        else:
            import cutlog
            path = cutlog.logs_dir() / "timings.jsonl"
        selected = {r["trial_id"].strip() for r in rows if r["mode"].strip().lower() == "editorkrab"}
        res = summarize(rows, machine_trials(path, selected) if path.exists() else {})
        cols = list(res[0])
        print("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols))
        for row in res:
            print("| " + " | ".join(str(row[c]) for c in cols) + " |")
        return 0
    except (ValueError, OSError, TypeError) as exc:
        print(f"benchmark: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
