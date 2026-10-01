---
name: style-bps
description: Style guide + technique manual for editing BPS คุณตั้น (Tony, BPS Tech CEO branding) TikTok interview clips in CapCut — insert-heavy 30–60 s cuts with white/blue "sentence pair" pop text, red hook title, film-effect inserts, typing/mouse SFX. Use when cutting, building, captioning, adding inserts/SFX/music, or reviewing any BPS / BPS2 / BPS3 draft (CapCut drafts named `BPS*` under `capcut_drafts` in config.json). Use together with clip-workflow, broll-finder and clip-qc, or when spawning capcut-cutter / capcut-sfx / capcut-validator agents.
---

# BPS คุณตั้น clip editing guide

Source of truth = drafts P'Ohm edited himself: **BPS3 01** (template, never touch), **BPS3 07**, **BPS3 10**. Bot-vs-Ohm diff: `<work_root>/BPS/คุณตั้น3/_bot/gold/` (work_root from config.json; on the shared drive, not in this repo). When this file and those drafts disagree, the drafts win — open them and copy values.

Full runbook (deeper detail): `<MoonRacle>/Data Notebooklm/30_Video_Editor/` (team notebook, not in this repo) — `02_สูตร.md`, `13_ระบบตัวหนังสือ...md`, `06_โครงสร้างไฟล์ CapCut draft.md`, `08_ปัญหาที่เคยเจอ...md`.

## 0. Safety rules (check before every write)
- CapCut must be closed: `Get-Process CapCut` returns nothing. Otherwise CapCut overwrites your edit on exit.
- Never overwrite an existing draft. Move it to an `_old_builds/<name>` folder next to `capcut_drafts` first. Never keep a copied draft folder inside CapCut Drafts as a backup (duplicate timeline id breaks both).
- Protected: **BPS3 01**, BPS 01, BPS 02, any segment that already has `common_keyframes` (P'Ohm's own work).
- Music and episode title: P'Ohm decides. Add music only when told.
- Done = `verify_episode.py` passes **and** the draft was re-transcribed and read end to end. Say what is verified vs. assumed.

## 1. Format and rhythm
- 1080x1920, 30–55 s (median 42), ceiling ~65 s. Over length: cut repeated content first.
- Hook = strongest sentence 3–4.5 s pulled from mid-take to the front (may repeat later). 5–7 s hook = too long.
- Body = answer only: drop interviewer lines ("ใช่ไหมครับ", leading "ครับ", far-mic voice). Never end mid-sentence.
- Main-camera shots median 1.7 s (1.1–2.4). Change framing without cutting audio: main cam zoom at several levels 1.25–1.83 (not just 1.25↔1.62), cut to second camera (DJI) every ~4 shots, DJI zoom 1.27–2.15.
- Silence cut (tight mode): every gap ≥0.3 s between words, shrink edges 0.05 s each side. Detect at −24 dB ≥0.28 s (−33 dB misses). Never cut inside a word ("เพราะฉะ|นั้น") — merge or skip.
- Interview audio is quiet: main clip volume ~3.92 in set 1.

## 2. Inserts (B-roll)
- 12–16 per clip, ~2.2 s each (1.6–2.7), 2–4 s apart; inserts + DJI cover 48–81% of the clip (target 60–77).
- **Only images that match the spoken word** (noun → literal picture, e.g. "เก็บเงิน" → hands counting cash). P'Ohm deletes vague "future network / server room / robot / brainstorm" shots.
- Real office footage beats stock: `คุณตั้น\insert\DJI_*.MP4` under 60 s (0778 BPS sign · 0760/0761 server racks · 0790–0799 NOC room · 0787–0789 field team). Files ≥60 s are the second interview camera, not B-roll.
- Always open a contact sheet of frames before placing — folder names and plans lie.
- Landscape stock: scale 3.16 to fill vertical; vertical native: 1.0. Stock lives in `stock_video` from config.json (Envato, 1080p only, account GT).
- Film effect over the same span on ~half the inserts (random from: สปาร์เคิลเกรน, รั่วซึม 2, วินเทจเรคคอร์ดดิ้ง, เสียงรบกวน 2, DV ย้อนยุค 3, ฟัซซี่เมมโมรี่, รังสีโบเก้).
- Transitions rare: หายใจสั่นๆ, ลบภาพยนตร์, แสงจ้า II, ดึงเข้า.
- Keyframe zoom: `uniform_scale.value = 1.0` always, `clip.scale` = final kf value, all 4 kf sets (PositionX/Y, ScaleX/Y), `time_offset = source_timerange.start + offset in shot`. Otherwise the insert renders as a thin band. Start scale ≥ cover ratio of that file (16:9 → 3.16). Default: no movement.

## 3. Pop text (replaces full subtitles)
**Sentence pair** — the only accepted pattern (bot's old "independent 2.4 s summary words" was rejected):
- White = first half of the spoken sentence, appears first → blue = second half, enters 0.5–2 s later → **both end together** → next pair starts immediately. Pair length follows the real sentence (2–6 s).
- Text on screen is **continuous** from end of hook to end of clip, no gaps.
- Words = real speech, shortened to spoken style ("เขาเรียนรู้กับเรา" → "เขาเรียนรู้พัฒนา"). Check meaning, not letters (Whisper wrote "ลดภาระไม่ได้" where he meant "ลดได้").
- Card timing = the second the word is actually spoken (word-level Whisper). Never place by proportion.
- English words capitalised, space-separated from Thai.

| Element | Colour RGB | Size | Scale | Animation |
|---|---|---|---|---|
| White lead | 1,1,1 | 25 (or 20) | 0.91 | เคอร์เซอร์คู่ |
| Blue punch | 0.02,0.07,0.57 | 26–30 | 1.35 | คลื่นเสียง |
| Big number (blue) | 0.02,0.07,0.57 | 17 | 1.79 | — |
| Red single word ("แต่") / pain word ("เป็นเดือน") | 0.93,0.11,0.11 | 30 | 1.74 | — |
| Bracket note "(บังคับ)" | white | 20 | 0.91 | — |

No yellow anywhere (old yellow #FFD400 spec is dead). Red is rare (set 1 had one red card total).
Fonts seen: สุขุมวิท-CnExBd (`7545361202768121105`) + คณิต-Rg (`7550201955503705345`); white has black stroke 0.08 + shadow.

**Layouts** (x 0 unless stated):
1. Bottom pair (default): white y −0.37 / blue y −0.50.
2. Top mode (when an insert fills the lower screen): white +0.66…+0.83 / blue +0.47…+0.58. About half the cards in Ohm's edits sit on top. Exact rule not confirmed with P'Ohm — ask before assuming.
3. Split left/right: white lead y +0.83, blue left x −0.34 y +0.68, blue right x +0.38 y +0.51 (e.g. "Artwork" | "Graphic").
4. 3-tier cascade: +0.74 white / +0.58 blue / +0.39 blue.
5. Giant red solo: x 0 y −0.15, scale 1.74, 1–2 syllables, ~1.8 s.
6. Bracket sub-note under blue: y −0.61…−0.65.

## 4. Hook title + cover
- 0–3.8 s: top line = context/problem **white** size 28 scale 0.86 y −0.26; bottom line = answer/punch **red** size 22–28 scale 1.37–1.50 y −0.39. (Bot had it reversed — rejected.)
- Title in 2 lines from what is actually said; numbers must be true ("เกือบ" not "กว่า" if not reached).
- Cover: P'Ohm uses a photo jpg; still title frame = 1 frame (33,333 µs) at t=0 on its own track (one cover per track).

## 5. Sound
- White card ↔ "Realistic sound effects for typing" 0.5 s, 100%.
- Blue card ↔ "PC mouse 05-1" 0.3 s, 25%.
- Still photo ↔ "Camera shutter" ~43%.
- SFX only on a text-animation start or a picture change, never random times. Banned: Pop (lower), ฟาด, ฟิ้ว.
- Same-track audio must not overlap.
- Music (only when told): volume 10–29% (default 10%), fade-in 3 s if not starting at 0, fade-out 5 s, `type = "extract_music"`. Local files must not carry CapCut library ids (`effect_id/music_id/resource_id` cleared, `app_id 0`) or every clip plays the same cached song.

## 6. Draft file rules (CapCut breaks otherwise)
- Times in microseconds. Segments on one track must not overlap (>1 ms). Every `material_id`/`extra_material_refs` must exist in materials. `source_timerange` ≤ source length.
- One id across the draft: root `draft_content.json` id = `draft_meta_info.json` draft_id = `Timelines/<id>/` folder = `project.json` ids = `timeline_layout.json` timelineIds. CapCut reads `Timelines/<id>/draft_content.json`, not the root file. After any clone run `python scripts/bps/fix_timeline_ids.py "<draft>"`.
- Rename a project: edit `draft_name` in `draft_meta_info.json` and the matching `root_meta_info.json` entry (match by `draft_fold_path` basename); don't rename the folder.
- Before restoring any backup, check its mtime and size — stale same-name backups have wiped current work.

## 7. Pipeline (BPS3 scripts in `scripts/bps/` of this kit: analyze_range, build_bps3_ep, verify_episode, fix_timeline_ids, add_inserts; shared CapCut tools in `scripts/capcut/`)
1. `python analyze_range.py "<file>" <start> <len>` → read transcript, pick body + hook + cuts.
2. Write `ep_XX.json` (name, title [red, white], cam, dji, dji_offset, hook, body, cuts, inserts `[cam_time, len, stock_prefix, stock_start]`, pops). Confirm every stock file exists.
3. `python build_bps3_ep.py ep_XX.json` → check `cover %` 60–77.
4. `python verify_episode.py "<name>"` → first line must be `dangling 0 | overlaps [] | missing [] | past source end []`; read the full re-transcription.
5. Fix config → move old draft to `_old_builds` → rebuild → verify. Pilot one episode before batching.
- DJI offset: FFT cross-correlation of the two audio tracks (`dji_time = cam_time + offset`); one DJI file may not cover the whole take.
- ASR: faster-whisper `large-v3` int8_float16 only (small/medium mishear names). ASR text is for picking ranges; on-screen text must be checked by meaning.

## 8. Reporting
- Thai, answer first in 1–3 plain lines, then per episode: name, length, insert count, verify result.
- Always state: music not added / not yet opened in CapCut / what needs P'Ohm's confirmation.
- End with `Changed` / `Verified` / `Blocked`. Log via `worklog.py add --type video` (problems need problem + cause + fix).
