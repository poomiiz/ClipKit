# EditorKrab

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/brand/logo-dark.png">
  <img src="docs/brand/logo.png" alt="EditorKrab" width="460">
</picture>

**ตัดคลิป จัดงาน จบในทีม**

[![Sponsor](https://img.shields.io/badge/Sponsor-%E2%99%A5-db61a2?logo=githubsponsors&logoColor=white)](https://github.com/sponsors/poomiiz)

<a href="docs/brand/promo.mp4"><img src="docs/brand/promo.gif" alt="EditorKrab in 33 seconds" width="300"></a>

▶️ [Watch the 33 s promo (MP4)](docs/brand/promo.mp4)

Previously ClipKit. EditorKrab is an **early-access** Windows editing workflow, not a complete replacement for Premiere Pro or CapCut. Existing projects and plugin IDs remain compatible.

Prepare story cuts, Thai subtitles, covers and presets; continue in the local editor, CapCut or HyperFrames. See the [launch kit](docs/launch.md) for announcement copy and brand assets.

The optional team workspace stores ownership and review metadata in Supabase. Google sign-in requires operator configuration; users do not enter provider credentials. Hosted sign-in and two-device synchronization have not passed live acceptance yet. Teams configure Drive for desktop or Syncthing themselves, sharing only footage and MP4 exports. Private project folders stay with their owner. See [team setup](docs/team-setup.md).

Open-source kit for cutting talking-head footage into 60-130 s vertical shorts: Thai subtitles, story cut, B-roll, CapCut drafts, QC.
Works in **Claude Code** (plugin) and **Codex** (skills), plus a local web app for reviewing on a timeline.

Requirements: Windows 10/11, Python 3.10+, ffmpeg, Node.js LTS (MP4 export), CapCut desktop. An NVIDIA GPU is
recommended for transcription (`whisper_device: "cuda"`); CPU works but is slow.

## Install

Claude Code:
```
claude plugin marketplace add poomiiz/EditorKrab
claude plugin install clip-kit@clip-kit
```

Codex:
```
npx skills add poomiiz/EditorKrab --agent codex -g
```

The `clip-kit` plugin ID stays unchanged so existing installations keep working.

Update later: `claude plugin marketplace update clip-kit` (Claude) or re-run the `npx skills add` line (Codex).

## Machine setup (once)
1. `git clone https://github.com/poomiiz/EditorKrab.git`, then `cd EditorKrab` (scripts run from the clone).
2. `powershell -ExecutionPolicy Bypass -File scripts\setup.ps1` - installs Python, ffmpeg (via winget) and all packages, creates `config.json` and the desktop icon.
3. `python scripts\setup_workspace.py D:\EditorKrab` (any folder: makes `config.json` and every folder), install
   Node.js LTS (nodejs.org, needed for MP4 export), then `python scripts\doctor.py --asr` must show all OK.
   Fonts are each editor's choice (not bundled); `card_font` is optional and only used for quick previews.
4. Then ask your AI agent (Claude Code / Codex) "ตัดคลิปนี้ ..." - it follows `skills/make-clip`. The EditorKrab
   window (desktop icon) is optional, for reviewing on a timeline.

## Stock footage
Free b-roll comes from Pixabay (free API key in `pixabay_key`). The clip page also lists one Pixabay search link per
b-roll spot; clips you download by hand from any library you hold a licence for go in with `--insert-from`.

## What is inside
| Path | What |
|---|---|
| `skills/make-clip` | Entry point: "ทำคลิปนี้" - runs every step below in order, pilot first |
| `skills/clip-workflow` | Client-neutral steps from raw footage to finished clip |
| `skills/clip-qc` | Checklist before a clip is called done |
| `presets/` | Subtitle presets (normal + emphasis text): `default`, `with-caption`, and the ones each user makes |
| `templates/EDIT_LOG.md` | Per-client edit log to copy into the client folder |
| `scripts/make_clip.py` | One story -> transcribe, jump cuts, subtitles, CapCut draft (prints JSON) |
| `scripts/log_clip.py` | Log a finished clip: always to `<output>/logs/clips_log.jsonl`, plus central log on the office machine; `import` loads team files |
| `scripts/clipkit.py` | Transcribe (Thai), pause-cut plan, ffmpeg render |
| `scripts/capcut/` | Edit CapCut `draft_content.json`: cards, B-roll, SFX, trims, preview |
| `scripts/capcut/editdata.py` | Approved CapCut drafts -> edits.sqlite (cuts, cards, inserts, audio, effects, AI-vs-person diff) -> Obsidian notes |
| `scripts/capcut/pace.py` | Per-client pace from edits.sqlite (`presets/pace/<client>.json`), pace check of a CapCut project, `learn` = what the person changed in the AI versions |
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
