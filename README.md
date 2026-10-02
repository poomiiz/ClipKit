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
3. Edit `config.json` (your folders), then `python scripts\doctor.py --asr` must show all OK.
   Fonts are each editor's choice (not bundled); `card_font` is optional and only used for quick previews.
4. `python scripts\envato.py login` - sign in to the **company** Envato account once in the Chrome window that opens.
5. Open the app from the desktop icon **ClipKit - Video to CapCut**.

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
| `skills/style-nina` | Nina look: cards, colours, animations, storytelling |
| `skills/style-bps` | BPS คุณตั้น look: sentence-pair pop text, red hook, film-effect inserts |
| `templates/EDIT_LOG.md` | Per-client edit log to copy into the client folder |
| `scripts/clipkit.py` | Transcribe (Thai), pause-cut plan, ffmpeg render |
| `scripts/capcut/` | Edit CapCut `draft_content.json`: cards, B-roll, SFX, trims, preview |
| `scripts/bps/` | BPS3 episode pipeline (analyze, build, verify) |
| `scripts/envato.py` | Envato search/download with this machine's Chrome (Playwright) |
| `scripts/broll_picker.py` | Keyword plan -> Envato search -> HTML picker with thumbnails -> download ticked |
| `scripts/doctor.py`, `scripts/setup.ps1` | Machine check and one-time install |
| `reference/tricks.md` | Every effect and when to use it |
| `app/` | Video -> CapCut web app (desktop icon) |

## Rules
- No video, footage, client files, fonts or passwords in this repo. Media stays on the shared drive.
- Machine paths only in `config.json` (git-ignored).
- New client = new `skills/style-<client>/SKILL.md`.
