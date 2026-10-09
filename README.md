# ClipKit

Open-source kit for cutting talking-head footage into 60-130 s vertical shorts: Thai subtitles, story cut, B-roll, CapCut drafts, QC.
Works in **Claude Code** (plugin) and **Codex** (skills), plus a local web app for reviewing on a timeline.

Requirements: Windows 10/11, Python 3.10+, ffmpeg, Node.js LTS (MP4 export), CapCut desktop. An NVIDIA GPU is
recommended for transcription (`whisper_device: "cuda"`); CPU works but is slow.

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
4. Optional: `python scripts\envato.py login` - sign in to your Envato account once (only for the bot route; the link page needs no login here).
5. Then ask your AI agent (Claude Code / Codex) "ตัดคลิปนี้ ..." - it follows `skills/make-clip`. The ClipKit
   window (desktop icon) is optional, for reviewing on a timeline.

## Envato (optional)
Free stock comes from Pixabay (free API key in `pixabay_key`). Envato is optional and needs your own subscription:
- Download only items a person ticked in the picker; every download registers a licence.
- One download at a time per machine; never script bulk downloads (it breaks Envato's terms).
- If Envato shows a security check or blocks the account, stop all downloads.

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
| `scripts/envato.py` | Envato search/download with this machine's Chrome (Playwright) |
| `scripts/broll_picker.py` | Keyword plan -> Envato search -> HTML picker with thumbnails -> download ticked |
| `scripts/doctor.py`, `scripts/setup.ps1` | Machine check and one-time install |
| `reference/tricks.md` | Every effect and when to use it |
| `app/` | Video -> CapCut web app (desktop icon) |

## Rules
- No video, footage, client files, edit databases (`*.sqlite`), fonts or passwords in this repo. Media stays on your own drive.
- Machine paths only in `config.json` (git-ignored).
- New look = new subtitle preset in `presets/` (by chat or `scripts/preset_from_capcut.py`).

## Contributing
Bug reports, presets and fixes are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md). Report security problems privately as
described in [SECURITY.md](SECURITY.md).

## License
[MIT](LICENSE). Bundled third-party code and fonts keep their own licences: see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
