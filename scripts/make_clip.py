"""One command from a picked story to a CapCut draft: transcribe -> jump cuts -> subtitles -> draft.

The agent still does the judgement steps of skills/clip-workflow (pick stories, rewrite cards,
B-roll, QC). This script does the mechanical middle for ONE clip and writes a plan file next to
the output so every number can be checked.

    python scripts/make_clip.py --file D:\\footage\\ep07.mov --start 125 --end 212 --name "EP07 burnout"
    python scripts/make_clip.py ... --dry-run      # plan only, no CapCut draft

Prints one JSON object (draft path, length, cut count, subtitle count, plan file, started_at, minutes).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "scripts" / "capcut"))
import kitconfig  # noqa: E402
import video_edit  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--start", type=float, required=True, help="story start in the source, seconds")
    ap.add_argument("--end", type=float, required=True, help="story end in the source, seconds")
    ap.add_argument("--name", required=True, help="CapCut project name")
    ap.add_argument("--threshold-db", type=int, default=-33)
    ap.add_argument("--min-pause", type=float, default=0.30)
    ap.add_argument("--keep", type=float, default=0.25, help="seconds of pause kept at each cut")
    ap.add_argument("--model", help="Whisper model, default from config.json (whisper_model)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    src = Path(a.file)
    if not src.is_file():
        raise SystemExit(f"file not found: {src}")
    if a.end - a.start < 5:
        raise SystemExit("story is shorter than 5 s - check --start/--end")
    base = kitconfig.CFG.get("output_dir") or kitconfig.CFG.get("work_root")
    if not base or not Path(base).is_dir():
        raise SystemExit("set the workspace folder in Settings first (output_dir missing)")
    out = Path(base) / "clips"
    out.mkdir(parents=True, exist_ok=True)
    started = datetime.now().isoformat(timespec="seconds")
    t0 = time.time()

    print(f"[1/3] transcribing {a.end - a.start:.0f} s ...", file=sys.stderr)
    phrases = video_edit.transcribe(str(src), a.start, a.end, model_size=a.model)   # clip-relative seconds
    if not phrases:
        raise SystemExit("no speech found in this range - wrong file or range?")
    print(f"[2/3] finding pauses ({len(phrases)} phrases) ...", file=sys.stderr)
    pauses = video_edit.detect_pauses(str(src), a.start, a.end, a.threshold_db, a.min_pause)
    cuts = video_edit.suggest_cuts(pauses, a.keep, 0.30)

    plan = {"file": str(src), "start": a.start, "end": a.end, "name": a.name,
            "cuts": cuts, "subs": phrases, "removed_s": round(sum(c["gain"] for c in cuts), 2)}
    slug = re.sub(r'[\\/:*?"<>|]+', " ", a.name).strip()
    plan_file = out / f"{slug}.plan.json"
    plan_file.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    result = {"plan_file": str(plan_file), "cuts": len(cuts), "subtitles": len(phrases),
              "result_length_s": round(a.end - a.start - plan["removed_s"], 2)}
    if not a.dry_run:
        print("[3/3] writing CapCut draft ...", file=sys.stderr)
        d = video_edit.create_capcut_draft(str(src), a.name, a.start, a.end, cuts=cuts, subs=phrases,
                                           drafts_root=kitconfig.DRAFTS)
        result.update({"draft_path": d["draft_path"], "result_length_s": d["duration"]})
    result.update({"started_at": started, "minutes": max(1, round((time.time() - t0) / 60))})
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
