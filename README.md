# ClipKit

Team kit for cutting talking-head footage into 60-130 s vertical shorts: Thai subtitles, story cut, B-roll from Envato, CapCut drafts, QC.
Works in **Claude Code** (plugin) and **Codex** (skills).

## Install

Claude Code:
```
claude plugin marketplace add poomiiz/ClipKit
claude plugin install clip-kit@clip-kit
```

Codex:
```
npx skills add poomiiz/ClipKit --agent codex -g
```

Update later: `claude plugin marketplace update clip-kit` (Claude) or re-run the `npx skills add` line (Codex).

## Machine setup (once)
1. `git clone https://github.com/poomiiz/ClipKit` (scripts run from the clone).
2. `powershell -ExecutionPolicy Bypass -File scripts\setup.ps1` - installs Python, ffmpeg, Chrome (via winget) and all packages, creates `config.json` and the desktop icon.
3. `python scripts\setup_workspace.py D:\ClipKit` (any folder: makes `config.json` and every folder), install
   Node.js LTS (nodejs.org, needed for MP4 export), then `python scripts\doctor.py --asr` must show all OK.
   Fonts are each editor's choice (not bundled); `card_font` is optional and only used for quick previews.
4. Optional: `python scripts\envato.py login` - sign in to the **company** Envato account once (only for the bot route; the link page needs no login here).
5. Then ask your AI agent (Claude Code / Codex) "ตัดคลิปนี้ ..." - it follows `skills/make-clip`. The ClipKit
   window (desktop icon) is optional, for reviewing on a timeline.

## Envato (shared company account, decided 2026-10-01)
Everyone signs in with the one company account on their own machine. To keep the account safe:
- Download only items a person ticked in the picker; every download registers a licence.
- One download at a time per machine; never script bulk downloads.
- Log out from machines that leave the team (`envato_profile` folder can be deleted).
- If Envato shows a security check or blocks the account, stop all downloads and tell the account owner.

## What is inside
| Path | What |
|---|---|
| `skills/make-clip` | Entry point: "ทำคลิปนี้" - runs every step below in order, pilot first |
| `skills/clip-workflow` | Client-neutral steps from raw footage to finished clip |
| `skills/broll-finder` | Transcript -> Envato keywords -> HTML picker -> download ticked items only |
| `skills/clip-qc` | Checklist before a clip is called done |
| `presets/` | Subtitle presets (normal + emphasis text): `default`, `with-caption`, and the ones each user makes |
| `templates/EDIT_LOG.md` | Per-client edit log to copy into the client folder |
| `scripts/make_clip.py` | One story -> transcribe, jump cuts, subtitles, CapCut draft (prints JSON) |
| `scripts/log_clip.py` | Log a finished clip: always to `<output>/logs/clips_log.jsonl`, plus central log on the office machine; `import` loads team files |
| `scripts/clipkit.py` | Transcribe (Thai), pause-cut plan, ffmpeg render |
| `scripts/capcut/` | Edit CapCut `draft_content.json`: cards, B-roll, SFX, trims, preview |
| `scripts/capcut/editdata.py` | Approved CapCut drafts -> edits.sqlite (cuts, cards, inserts, audio, effects, AI-vs-person diff) -> Obsidian notes |
| `scripts/capcut/pace.py` | Per-client pace from edits.sqlite (`presets/pace/<client>.json`), pace check of a CapCut project, `learn` = what the person changed in the AI versions |
| `scripts/bps/` | BPS3 episode pipeline (analyze, build, verify) |
| `scripts/envato.py` | Envato search/download with this machine's Chrome (Playwright) |
| `scripts/broll_picker.py` | Keyword plan -> Envato search -> HTML picker with thumbnails -> download ticked |
| `scripts/doctor.py`, `scripts/setup.ps1` | Machine check and one-time install |
| `reference/tricks.md` | Every effect and when to use it |
| `app/` | Video -> CapCut web app (desktop icon) |

## Rules
- No video, footage, client files, fonts or passwords in this repo. Media stays on the shared drive.
- Machine paths only in `config.json` (git-ignored).
- New look = new subtitle preset in `presets/` (by chat or `scripts/preset_from_capcut.py`).

## Development checks

Install `requirements-dev.txt`, then run `python scripts/smoke_test.py`.
The checks use temporary drafts and do not require footage or network.
For an unconfigured machine, set `CLIP_KIT_CONFIG` to `config.example.json`.
Windows CI runs these checks on pushes and pull requests.
With FFmpeg installed, `python scripts/media_test.py` additionally generates
test footage and checks real cut output, decode, cache reuse, interrupted renders
and retries. Generated media is temporary and contains no client material.

The app is a local desktop tool; open it through `http://127.0.0.1:8770`
or `http://localhost:8770`. Browser requests from other origins are rejected.
See [release readiness](docs/production-readiness.md) for verified results and
the remaining real-media, installation and licensing acceptance gates.
