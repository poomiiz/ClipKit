---
name: clip-workflow
description: Client-neutral workflow for turning raw talking-head footage into 60-130 s vertical shorts in CapCut - transcribe, pick self-contained stories, cut, Thai keyword cards, B-roll, music/SFX, QC. Use when asked to cut, subtitle or edit a short clip from interview/podcast footage, "ตัดคลิป", "ทำซับ", "ใส่อินเสิร์ต", or to plan a batch of clips from one long recording. Load the client style skill (style-*) for the look.
---

# Clip workflow (any client)

Order matters. Each step has an output file you can show; never skip to the next step without it.

## 0. Setup check
Run `python scripts/doctor.py` once per machine. It must print all green before any work. Paths come from `config.json` (see `config.example.json`) - never type a drive path into a script or skill.

## 1. Transcribe the raw footage once
`python scripts/clipkit.py transcribe RAW.mov` -> `RAW.words.json` (Thai words + times).
- Thai speech-to-text is a draft. Names, brands and English words come out wrong; fix them from the client's word list (`clients/<client>/words.txt`) before you write cards.

## 2. Pick the stories (one idea per clip)
Read the transcript and list candidate clips as `[start, end, title, promise]`. A clip qualifies only if it has:
**Hook (one promise) -> Setup -> Proof (a concrete story, numbers, names) -> Twist -> One-line lesson -> Button (laugh, quote or tease).**
- Open on the promise, not on a warm-up. A personal story belongs in the Proof beat.
- Ask "what does the viewer take away?" No answer = merge or drop.
- No point may repeat across the series. Neighbouring ranges overlap at the edges - check.
- Never end mid-sentence. 60-130 s; length follows content.
Show the list to the person before cutting.

## 3. Cut
- Jump cuts on breaths and fillers; median cut about 2 s. Keep stutters, laughs and the listener's jabs - they become joke cards, not cuts.
- Source order may be rearranged into setup -> proof -> punch. Never change what the speaker means.
- Transcribe the **edited timeline** again before captioning (`timeline_asr`). Never caption from the raw transcript - times shift after cutting.

## 4. Cards and subtitles
- Cards are short rewrites (2-6 words) in the speaker's own slang, not a transcript.
- Every spoken stretch has a card; no gap longer than about 1 s while someone talks.
- Keep words spoken in English in English.
- Colours, sizes, positions and animations come from the client style skill.

## 5. B-roll inserts
Use the `broll-finder` skill: transcript -> keyword list -> Envato search -> HTML picker -> the person ticks -> bot downloads. Place each insert on the exact spoken keyword it shows.

## 6. Audio
Music under the voice (volume from the style skill). SFX only where the style skill says.

## 7. QC, pilot first
Run the `clip-qc` checklist on the **first** clip and have the person watch it in CapCut before you build the rest of the batch. Report problems with time stamps.

## 8. Log every clip when it is done
One row per clip in the central work log, the moment the clip is finished (never later from memory):
```
python <MoonRacle>/knowledge_base/scripts/worklog.py add --agent <registered agent> --type video \
  --project "<client>" --item "<clip name>" --stage done --started-at <ISO time> --minutes <agent minutes> \
  --metadata '{"human_fix_min": N, "source_range": "a-b s", "final_len_s": N, "title": "...", "fixed_by": "agent|person", "rollback": "draft_content.before_*.json"}'
```
- `--started-at`, `--minutes` and `human_fix_min` are measured, never estimated. Unknown = leave the field out.
- A row about a problem also needs `--problem`, `--cause`, `--fix`.
- Also update the client's `EDIT_LOG.md` (copy from `templates/EDIT_LOG.md` on the first clip): state table + per-clip history.
- Machine without the MoonRacle repo: append the same fields as one JSON line to `clips_log.jsonl` in the client folder and hand it over.

## Time budget
10 clips/day = about 45 min per clip including review. If one step eats more than its share, stop and say which step.
