---
name: make-clip
description: One-request runner for a whole short clip - "ทำคลิปนี้", "ตัดคลิปจากไฟล์นี้", "ทำคลิปสั้นไม่เกิน 2 นาที", "make a clip from this footage", "ทำเป็นโปรเจกต์ CapCut ด้วย", and the commands the ClipKit app asks the person to paste ("ClipKit: แบ่งเรื่อง ...", "ClipKit: เลือกคำเน้น ..."). Runs scripts/run_clip.py end to end (transcribe, stories, cuts, subtitles in the person's preset, title, b-roll, music, MP4 and/or CapCut project) and does its two thinking steps. Use this as the entry point; it uses broll-finder and clip-qc.
---

# Make a clip (entry point)

Run from the ClipKit folder. Stop and report `Blocked` with the exact error if any command fails - never skip a step or guess a value.

## New machine (once)
1. `python scripts/setup_workspace.py D:\ClipKit` (any folder) - makes `config.json` with every folder.
2. `python scripts/doctor.py` - every line OK (WARN on "preview font" is fine). FAIL = tell the person which line
   and stop. Python packages: `scripts/setup.ps1`. Node.js LTS from nodejs.org. Speech model: `scripts/fetch_model.py`.
3. Optional: free Pixabay key (pixabay.com/api/docs) as `"pixabay_key"` in `config.json` for automatic b-roll.

## One command: "ตัดคลิปนี้" / "ทำคลิปสั้นจากไฟล์นี้" (no ClipKit window needed)
```
python scripts/run_clip.py "<video>" [--max 120] [--preset default] [--all] [--capcut] [--export] [--insert]
```
Ask only what is missing: the video path, and which subtitle preset (`default` when they have no preference;
list: the `presets/` folder; none they like: make one, see **Subtitle presets**). "ทำเป็นโปรเจกต์ CapCut" = add
`--capcut`; "ขอไฟล์ MP4" = add `--export`. `--look` (pair, karaoke, pop, none) and `--shape` (portrait default)
rarely change.
It transcribes, splits into stories, makes one project per story (face crop, subtitles, silences trimmed,
subtitle look, zoom cut), finds free Pixabay b-roll, makes the cover and the HyperFrames page, and writes
`<video> - ClipKit.html` with one Envato search link per b-roll spot. Rerunning skips every finished step.
1. Run it. Output is one JSON line per step.
2. `{"WAIT": ...}` (exit 2) = a thinking step is yours: do the pasted command(s) below (`แบ่งเรื่อง`, then
   `เลือกคำเน้น` for each project), keep stories within `--max` seconds, then run the same command again.
3. Pilot rule: without `--all` only story 1 is built. Send the person the HTML file and wait for their OK
   before `--all`.
4. Envato: the person opens the links, downloads into each project's `clipkit_insert` folder (name starts with
   the link number, e.g. `2 coffee.mp4`), then you run with `--insert`. Never log in to Envato for them.
5. `--capcut` also builds "<project> · CapCut": the same clip laid out in CapCut (subtitle roles on their own
   tracks, title, English caption, b-roll, clicks, music, zoom, skin) for a person to keep editing there.
6. `--export` renders the MP4s (about 4 min per minute of clip); look at frames before saying done.

## Commands pasted from the ClipKit app
The app does the mechanical work; the thinking steps are yours. It shows the person a line to paste here.

### `ClipKit: แบ่งเรื่อง "<video path>"`
1. Read `<video path>.transcript.json` (list of `{start, end, text}`, seconds). Missing = tell the person to press the button in the app again.
2. Split it following every rule in `prompts/story_split.md` (60-130 s per story, one point each, start on the hook, end on a finished sentence, skip greetings).
3. Write `<video path>.stories.json` as UTF-8 JSON: `[{"title": "...", "summary": "...", "start": 12.3, "end": 95.0}]` with start/end taken from transcript lines.
4. Reply with the list (number, title, length). The app picks the file up by itself within a few seconds.

### `ClipKit: แปลซับเป็นอังกฤษ "<CapCut project folder>"`
1. Read `<folder>/clipkit_subs_th.json` (list of `{start, end, text}`).
2. Translate every line into short natural English for a vertical short; keep brand names and technical terms.
3. Write `<folder>/clipkit_subs_en.json` as a JSON list of strings, exactly one per Thai line, same order.
4. Tell the person to press "ซับขาว ภาษาอังกฤษ" again.

### `ClipKit: เลือกคำเน้น "<CapCut project folder>"`
For the sentence-pair subtitles (normal lead line + bigger emphasis punch line, in the project's preset).
1. Read `<folder>/clipkit_lines.json` (list of subtitle line texts, in order) and the whole clip's meaning.
2. For every line, split it into short phrases of about 2 seconds / 10-18 Thai letters, in speaking order,
   breaking where a thought ends. Each phrase = `[lead, punch]`: the punch is the word or short phrase that
   carries the point (a feeling, a number, a result, a brand: "ถูกกดดัน", "20 ปี", "ไม่อิ่ม"), not just the
   last word. Lead + punch together must be that phrase's exact text (punch may come first: then lead is "").
   Every character of the line must be used once, in order (spaces may be dropped).
   Keep each lead to about 15 Thai letters; split a longer phrase rather than letting the text shrink.
   Not every phrase deserves a coloured punch. Filler and connective talk ("อืมๆ", "เออจริงๆ", "แบบว่า",
   "อะไรอย่างนี้", repeated words) and phrases with no point get white only: `[text, ""]`. Colour only the
   phrases that carry the message (a feeling, a number, a result, a key idea) - roughly half or fewer.
   The screen shows at most 2 lines: white 1 + colour 1, or one of them on 2 lines.
   Display options - a 4th item `{"look": ..., "show": [white, colour]}` per phrase ("white" = the preset's
   normal text, "colour" = its emphasis text), measured from real hand-edited clips:
   - `pair` (default): white lead + coloured punch.
   - `white`: white only - setups and questions ("จะแนะนำยังไง", "ธุรกิจเขาเป็นยังไง").
   - `color`: coloured only - a short line that is all point.
   - `red`: the colour line turns red - the one or two strongest points or the clip's question.
   - `hold`: the previous white line stays while the coloured line changes - lists ("บางคนบอก" ->
     "ทำแบรนด์ดิ้ง" / "ลงระบบ CRM" / "จ้างเซลส์มาขาย").
   - `skip`: no subtitle - filler, repeats, false starts, the other person's "อืมๆ".
   - `show`: the words on screen, rewritten short and clean ("ไปจ้างพนักงานขายซิ" ->
     "จ้างเซลส์มาขาย", "มันคือแบบกูต้องทำอะไร" -> "ต้องทำอะไรก่อน?"). Keep the meaning, drop slang and
     filler, max ~15 letters per line. Lead + punch still hold the exact spoken text (they give the timing).
   Example item: `["บางคนบอกต้องลง", "ระบบ Crm", {"look": "hold", "show": ["", "ลงระบบ CRM"]}]`;
   with a b-roll search: `[lead, punch, "office team computer", {...}]`.
3. B-roll: about one phrase in three that names something you can see (a product, food, a place, an action,
   an emotion on a face), add a third item: a short English stock-footage search, e.g.
   `["เดี๋ยวมากิน", "กาแฟต่อ", "coffee cup cafe"]`. Concrete nouns, 2-4 words, no brand names.
   Skip abstract phrases; never two b-roll phrases in a row.
4. Write `<folder>/clipkit_punch.json` as `{"<line text>": [item, ...], ...}`, each item
   `[lead, punch]`, `[lead, punch, query]`, `[lead, punch, options]` or `[lead, punch, query, options]`
   covering every line.
5. Clip title (every clip has one, on screen for the first 4 s; the subtitles start after it): write
   `<folder>/clipkit_hook.json` as 1-2 lines `[{"text": "เริ่มทำธุรกิจใหม่", "color": "red"},
   {"text": "ทำสิ่งนี้ก่อน", "color": "white"}]`. Short punchy promise of the clip, ~8-16 letters per line, not a
   sentence from the talk. Colours per line: `white`, `orange` or `red`, any mix (red/white, white/orange,
   orange/white, one big red word...) - pick by the content: red for a warning or shock, orange for the promise.
   Examples of good titles: "ธุรกิจสมัยนี้ / ไม่ต้องแย่งทำเลอีกแล้ว", "ทำธุรกิจไม่เหนื่อย / ต้องรู้ 2 เรื่องนี้",
   "เงิน 5 แสนก็ไม่เอา!", "Burn out".
6. Only when the project's preset has a `caption` (e.g. `with-caption`): write `<folder>/clipkit_caption.json`
   as `{"<line text>": "<translation>"}` for every line, in the preset's caption `language` (default English) -
   short and natural ("If I want to start my own business from scratch, let's say..."). Brand names stay.
7. Tell the person the clip is ready to review in ClipKit (แท็บ ส่งออก > ดูตัวอย่าง).

### `ClipKit: สร้างท่าใหม่ ใช้ทำ "<role>" อารมณ์ "<mood>"` and `ClipKit: ทำเทมเพลตจาก HyperFrames "<name>"`
Owner only: do this only when `config.json` has `"creator": true`; otherwise say it is done on the owner's machine.
1. Read `motion/library/README.md` and `motion/library/hyperframes.md`. A new move must not repeat an existing template in `motion/*/` or a registry item with the same role and mood; for the HyperFrames command, start from that item (`npx hyperframes@0.8.101 add <name>` in a scratch project) and rebuild it as our template.
2. Make `motion/<kebab-name>/index.html`: 1080x1920 transparent, Thai-safe (grapheme splitting with `Intl.Segmenter`, never per code point), lines shrink to fit the frame, `speed` and `font` params, and a `<script type="application/json" id="clipkit-motion">` block with `role`, `mood`, `label`, `fields`, `length` (copy the shape from `motion/hook-title`).
3. Render one MOV through `POST /api/kit/motion` with Thai words, pull 3 frames with ffmpeg and look at them (pilot first). Fix anything cut off or broken before going on.
4. Commit and push to ClipKit; teammates get it from the update banner and it appears on the motion page and in the library.

## Cut log (always)
Every finished clip is logged by `run_clip.py` (`<output>/logs/runs.jsonl`). Its output has a `check` per clip (score + problems
against the rules): fix every problem it lists (re-pick emphasis / title) and run again before showing the person. When the person complains about a
result ("ซับยาวไป", "ซับสั้นเกิน", "เรียงเนื้อหาไม่ดี", "หัวคลิปไม่ตรง"...), BEFORE you change anything run
`python scripts/cutlog.py feedback "<project folder>" "<what they said, their words>"`, then fix, then run it again
with `--fix "<what you changed>"`. Asked to send results back: `clipkit report` (or `python scripts/cutlog.py report`)
makes a small zip with no video - tell them it contains the clip's spoken words.
Every change ClipKit writes to a project (subtitles, style, cuts, hook...) is also recorded with its before and after
in the project's own `clipkit_changes.jsonl` (stays on this machine); `editdata.py extract` loads it into `edits.sqlite`
(table `changes`) for the clips in approved.json, so the owner's own style can be learned from it.
Each edit also keeps a copy of the project in `clipkit_history/` (an autosave history):
`python scripts/draft_history.py "<project folder>"` lists them, adding a version name puts that one back.

**ClipKit itself goes wrong** (an error, CapCut will not open a project, a crash): report it through the log,
never as a loose file on the Desktop - `python scripts/cutlog.py feedback "<project folder>" "BUG: <what happened,
exact error text>" --fix "<what you tried>"`. It lands in the team sheet with the version. Do not hand-edit a
project's draft_content.json / Timelines files or ClipKit's code to work around it: a hand fix hides the bug and
is lost on the next update. Tell the person it is reported.
ClipKit also seals every project it writes: after a hand edit it stops with "ถูกแก้นอก ClipKit". Then make the
project again from the raw file. `scripts/accept_edit.py` is only for a change the person made in CapCut themselves,
never to get past your own edit.

## Subtitle presets (each person makes their own)
A preset is `presets/<name>.json`: how the normal text and the emphasis text look, plus an optional small
translated caption. Never name one after a client unless the person asks; ask them for a name.
- **By chat** ("ตัวปกติขาวขอบดำ ตัวเน้นเหลืองใหญ่กว่า"): copy `presets/default.json` and change it.
  Per role: `size` (CapCut text size, 15-40 normal), `y` (-1 bottom .. 1 top; normal above emphasis, about 0.12
  apart), `color` / `outline` as `#rrggbb`, `outline_width` (0-0.15). `caption`: `null`, or the same fields plus
  `language`.
- **From the person's own CapCut project**: `python scripts/preset_from_capcut.py "<CapCut project folder>" --name <name>`
  reads the text styles they used most and writes the preset; show them what it wrote.
- Use it: `run_clip.py ... --preset <name>`, or the preset list in the ClipKit editor.

## QC and hand-over
Run `clip-qc` on the pilot clip. Tell the person what to open (the HTML page, the MP4, or the "· CapCut"
project), its length and what to check. Wait for their verdict before `--all`.

## Log the clip (the moment it is done)
```
python scripts/log_clip.py add --project "<client>" --item "<clip name>" --agent <claude|codex> \
  --started-at <when you started, ISO time> --minutes <measured agent minutes> \
  --metadata '{"human_fix_min": N, "source_range": "s-e", "final_len_s": N, "draft": "<draft name>"}'
```
- Always written to `<output>/logs/clips_log.jsonl`. On the office machine it also goes straight to the central work log.
- Team machine: the file prints "hand clips_log.jsonl to the office" - send that file; the office runs `python scripts/log_clip.py import <file>` (already-imported rows are skipped).
- A problem row needs `--problem`, `--cause`, `--fix`.

## Report format
End with one of `Changed` / `Verified` / `Blocked`, plain language, the draft name, and the next action for the person.
