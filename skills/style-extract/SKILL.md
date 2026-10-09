---
name: style-extract
description: Read the subtitle look out of a video's frames for the ClipKit style lab - the command the app copies, "ClipKit: ถอดสไตล์ "<folder>"", or "ถอดสไตล์จากคลิปนี้" - and approve a style shared for the team ("อนุมัติสไตล์ #<issue>"). Writes style.json in the preset format and renders its still and GIF preview so the person can confirm it on the คลังสไตล์ page.
---

# Extract a subtitle style from a video

Run from the ClipKit folder. A CapCut project never comes here: the app reads it directly.

1. The command names a lab folder (`<output_dir>/style_lab/<name>`). Without one, run
   `python scripts/style_lab.py start "<video>"` first and use the `folder` it prints.
2. Look at every picture in `<folder>/frames/` (the video at even steps). Find the burned-in text.
3. Write `<folder>/style.json` in the same format as `presets/4-levels.json`:
   - `normal` (the plain, usually white line) and `emphasis` (the bigger or coloured line) are required.
   - `caption` (small reading subtitle, add `"language": "en"` or `"th"`, `"shadow": true` if it has one) and
     `second` (off-centre tilted line, with `x` and `rotation`) only when the frames show them; else `null` / leave out.
   - Each line: `size` (the frames are 960 px tall: height of one text line in px ÷ 3 ≈ size; 22-30 is a
     normal subtitle), `y` (centre of the line, 1 = top edge, 0 = middle, -1 = bottom edge),
     `color` and `outline` as `#rrggbb`, `outline_width` (0 none, 0.04 thin, 0.08 thick).
   - `about`: one line on what you saw and which frame. Measure from the pictures; never copy a preset's numbers.
   - No text in any frame: stop and tell the person this video has no subtitles to learn from.
4. `python scripts/style_lab.py preview "<folder>"`. An error names the wrong value: fix style.json and rerun.
5. Look at `<folder>/preview.png` next to a frame. Wrong size or place: fix and rerun step 4.
6. Tell the person it is ready on the คลังสไตล์ page, where they look at it and press เก็บเข้าคอลเลกชัน.
   Do not save it for them (`style_lab.py save`) unless they ask.

# Approve a shared style for the team ("อนุมัติสไตล์ #<issue>")

Only the repo owner approves. Shared styles arrive as `[style] <name>` issues in the repo this ClipKit updates from.

1. Read the issue: the preset is in its ```json block, the preview GIF is attached. Show the person the GIF and
   wait for their OK on this issue; never approve on your own.
2. Save the JSON block to a file and run `python scripts/style_lab.py approve "<file>" <name>`. An error names
   what is wrong: tell the person and stop (ask the sender to fix it), never edit their numbers.
3. Commit `presets/team-<name>.json` with `Closes #<issue>` and push to the default branch the team updates from.
   Every machine gets it with its next update and the คลังสไตล์ page lists it under สไตล์ทีม.
