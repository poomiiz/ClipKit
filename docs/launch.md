# EditorKrab open-source launch kit

## Repository description

Open-source short-video editing workflow with Thai subtitles, CapCut drafts, HyperFrames, local editing and team review.

## ข้อความเปิดตัว

เปิดตัว EditorKrab 🦀 เครื่องมือโอเพนซอร์สสำหรับคนตัดคลิปพูดและทีมคอนเทนต์

ช่วยเตรียมเรื่องจากฟุต ทำซับไทย ตัดช่วงเงียบ จัดปกและ preset แล้วแก้ต่อผ่านหน้าตัดต่อในเครื่อง CapCut หรือ HyperFrames ได้ ใช้ร่วมกับ Claude Code และ Codex ได้ด้วย

เปิดซอร์สให้ทุกคนช่วยแก้ ปรับ preset และเพิ่มความสามารถ

รุ่นนี้เป็น early access สำหรับ Windows ต้องตรวจซับและผลตัดก่อนส่งงาน ส่วนระบบบัญชีทีมและ Google login ยังอยู่ระหว่างตั้งค่าและตรวจใช้งานจริง

ซอร์สและวิธีติดตั้ง: https://github.com/poomiiz/EditorKrab

ใบอนุญาต MIT · ยินดีรับ issue และ PR ภาษาไทยหรืออังกฤษ

## English announcement

Meet EditorKrab: an open-source workflow for turning talking-head footage into short videos.

Prepare story cuts, Thai subtitles, covers and presets, then continue in the local editor, CapCut or HyperFrames. Agent workflows are available for Claude Code and Codex.

This is an early-access Windows project. Check subtitles and edits before delivery. Hosted team accounts and Google sign-in are still awaiting live setup and acceptance.

Source, installation and contributions: https://github.com/poomiiz/EditorKrab

MIT licensed. Issues and pull requests in Thai or English are welcome.

## Assets

- `docs/brand/logo.svg` and `logo.png`: transparent wordmark for light backgrounds
- `docs/brand/logo-dark.svg` and `logo-dark.png`: wordmark for dark backgrounds
- `docs/brand/icon.svg`, `icon-512.png`, `icon-1024.png`: app icon
- `app/static/editorkrab.ico`: Windows icon, sizes 16–256
- `docs/brand/github-banner.png`: repository social preview, 1280 × 640

Palette: navy #17243B, coral #FF785C, paper #F7F5EF. Mark: crab with a play symbol. Wordmark: Segoe UI / Arial. Editable SVG sources and raster exports are included.

The `clip-kit` plugin ID and `clipkit` file-format keys retain their existing names for compatibility. The previous `clipkit.ico` path remains an alias for existing shortcuts.

## Before announcing a stable release

- Verify installation on a clean Windows machine and review a real exported pilot clip.
- Finish hosted Supabase migrations and Google OAuth setup; test real sign-in and role isolation.
- Verify two-device external synchronization and project handover procedures.
- Review repository contents for client data, credentials and third-party licensing.
- Upload `github-banner.png` as the repository social preview in GitHub Settings → General.

Prepared copy only; this change does not publish an announcement or stable release.
