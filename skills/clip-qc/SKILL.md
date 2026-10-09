---
name: clip-qc
description: Pre-delivery checklist for a finished short clip (CapCut draft or MP4). Use before saying a clip is done, before sending it for review, and on the first clip of every batch.
---

# Clip QC

Check with your eyes and ears on the real output, not on the plan. Grab frames with `ffmpeg -ss <t> -i out.mp4 -frames:v 1 f.png` at a card, an insert and the ending; listen to the first 10 s and the last 10 s.

1. **Story** - opens on the promise; one idea; ends on a full sentence plus a button.
2. **Duplicates** - no point already made in an earlier clip of the series.
3. **Subtitles** - every card matches what is said at that moment; names and brands spelled right; no gap > 1 s while someone talks. The `ClipKit: ตรวจคำผิด` check has been run on every project, whichever speech model (`whisper_model`) made the subtitles.
4. **Thai text** - no broken vowels or tone marks; long cards wrapped by hand.
5. **Cuts** - no cut inside a word or syllable; no flash frames.
6. **Inserts** - each on its keyword; framed on the subject; no watermark; no banding.
7. **Audio** - voice clear; music audible but under the voice; SFX not louder than the voice; no click at a cut. ClipKit levels every MP4 to -14 LUFS (`render.LOUDNESS`); a CapCut project is not levelled, so switch on CapCut's loudness normalisation on export.
8. **Colour** - footage not washed out or over-saturated (HDR/Dolby Vision sources need checking on the export).
9. **Format** - 1080x1920, length 60-130 s, file plays from start to end. No text under the apps' top bar, button column or caption area: `run_clip.py` prints `safe_zone` lines for the CapCut project or preset (`render.safe_zone`); the MP4 export moves such lines itself.
10. **Branding** - client logo/overlay present per the style skill.
11. **Pace** - CapCut project: `python scripts/capcut/pace.py check "<project>" <client>` (or `run_clip.py --capcut --client <client>`) has no problems: cards and inserts not held longer than the person holds them for that client, enough cards per minute, no long stretch without a card. `low_data: true` = the client has under 5 approved minutes; treat its limits as a guide.

Report: pass, or a list of `time - problem - fix`. A batch is released only after clip 1 passes and the person has watched it.

After the person approves a clip, add it to `<edit_data>/approved.json` with `"ai_version": "clipkit_ai_version.json"` (ClipKit saves that copy on every CapCut build), then run `editdata.py extract`, `pace.py baseline` and `pace.py learn`; a change the person made in 3+ clips is a rule idea to add here.

Add a line here every time a reviewer sends a clip back for a reason not on this list.
