# ClipKit - agent instructions

For any short-clip editing task, read `skills/clip-workflow/SKILL.md` first, then the client style skill `skills/style-<client>/SKILL.md`, `skills/broll-finder/SKILL.md` for inserts, and `skills/clip-qc/SKILL.md` before calling a clip done.

- Machine paths come from `config.json`; never hard-code a drive path.
- Close CapCut before editing a draft and back up `draft_content.json` first.
- Envato downloads only for items a person ticked (each download registers a licence).
- Pilot one clip and get it watched before building the rest of a batch.
- Scripts raise on bad input; never add a silent fallback.
