---
name: make-clip
description: One-request runner for a whole short clip - "ทำคลิปนี้", "ตัดคลิปจากไฟล์นี้", "make a clip from this footage". Checks the machine, transcribes, proposes stories, waits for the person to pick, then builds the CapCut draft with cuts and subtitles, adds cards/B-roll/motion per the client style, runs QC and logs the clip. Use this as the entry point; it calls clip-workflow, style-*, broll-finder and clip-qc in order.
---

# Make a clip (entry point)

Run from the ClipKit folder. Stop and report `Blocked` with the exact error if any command fails - never skip a step or guess a value.

## 1. Machine ready
`python scripts/doctor.py` - every line OK (WARN on "preview font" is fine). FAIL = tell the person which line and stop.

## 2. Which client and which file
Ask only what is missing: client style (`style-nina`, `style-bps`, or none) and the raw footage path. Load that style skill now.

## 3. Transcript of the whole recording (once per file)
`python scripts/clipkit.py transcribe "<RAW>"` -> `<RAW>.words.json`. Reuse it if it already exists.

## 4. Propose stories - wait for the person
Follow `clip-workflow` step 2. Show a numbered list: `start-end s | title | promise | why it works`. Do not build anything until the person picks.

## 5. Build the draft for each picked story (pilot first: ONE story, then wait)
```
python scripts/make_clip.py --file "<RAW>" --start <s> --end <e> --name "<client> <EP> <title>"
```
It prints JSON: `draft_path`, `cuts`, `subtitles`, `result_length_s`, `plan_file`, `started_at`, `minutes`. Keep `started_at` for the log. Check `result_length_s` is 60-130 s; outside = adjust the range and rerun.

## 6. Cards, motion, B-roll, music (client style)
- Cards and subtitles: `clip-workflow` step 4 plus the style skill (fonts, colours, positions).
- Motion overlays (hook title, sentence pair): the app page `/motion.html`, or POST `/api/kit/motion`; files land in `<output>/motion` as transparent MOV - place them in CapCut on the exact spoken word.
- B-roll: `broll-finder` (the person ticks; only ticked items are downloaded - each download uses one Envato licence).
- Cover: `/cover.html`.

## 7. QC and hand-over
Run `clip-qc` on the pilot clip. Tell the person: draft name to open in CapCut, length, what to check. Wait for their verdict before building the next story.

## 8. Log the clip (the moment it is done)
```
python scripts/log_clip.py add --project "<client>" --item "<clip name>" --agent <claude|codex> \
  --started-at <started_at from step 5> --minutes <measured agent minutes> \
  --metadata '{"human_fix_min": N, "source_range": "s-e", "final_len_s": N, "draft": "<draft name>"}'
```
- Always written to `<output>/logs/clips_log.jsonl`. On the office machine it also goes straight to the central work log.
- Team machine: the file prints "hand clips_log.jsonl to the office" - send that file; the office runs `python scripts/log_clip.py import <file>` (already-imported rows are skipped).
- A problem row needs `--problem`, `--cause`, `--fix`.

## Report format
End with one of `Changed` / `Verified` / `Blocked`, plain language, the draft name, and the next action for the person.
