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
2. `powershell -ExecutionPolicy Bypass -File scripts\setup.ps1` - installs packages, creates `config.json`.
3. Edit `config.json` (your folders), then `python scripts\doctor.py --asr` must show all OK.
   The card font must be installed by hand (licensed font).

## What is inside
| Path | What |
|---|---|
| `skills/clip-workflow` | Client-neutral steps from raw footage to finished clip |
| `skills/broll-finder` | Transcript -> Envato keywords -> HTML picker -> download ticked items only |
| `skills/clip-qc` | Checklist before a clip is called done |
| `skills/style-nina` | Nina look: cards, colours, animations, storytelling |
| `skills/style-bps` | BPS คุณตั้น look: sentence-pair pop text, red hook, film-effect inserts |
| `templates/EDIT_LOG.md` | Per-client edit log to copy into the client folder |
| `scripts/clipkit.py` | Transcribe (Thai), pause-cut plan, ffmpeg render |
| `scripts/capcut/` | Edit CapCut `draft_content.json`: cards, B-roll, SFX, trims, preview |

## Rules
- No video, footage, client files, fonts or passwords in this repo. Media stays on the shared drive.
- Machine paths only in `config.json` (git-ignored).
- New client = new `skills/style-<client>/SKILL.md`.
