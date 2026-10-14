# ClipKit web AI - JSON schema v1

Lets an AI in the browser (claude.ai, ChatGPT...) do ClipKit's two judgement steps instead of an agent on this
machine. The AI never needs the video: ClipKit exports the transcript and timings, and the CapCut project is built
on this machine from its own media files.

| step | export (upload this file to the AI) | prompt | import writes |
|---|---|---|---|
| `stories` | `<video>.web-ai-stories.md` | `stories.md` + `../story_split.md` | `<video>.stories.json` |
| `clip` | `<project>/clipkit_web_ai.md` | `clip.md` | `clipkit_punch.json`, `clipkit_hook.json`, `clipkit_caption.json` (only when the preset has a translated caption), motion (`clipkit_overlays.json`) |

From the app: download one file from the AI box, attach it to a browser AI without an extra prompt, then paste
the JSON answer back. A local agent is optional: it reads the same packet and saves the same answer schema.
Manual editing uses the editor's phrases, title and motion controls without requiring an AI service.
From a terminal:

    python scripts/web_ai.py export stories "<video>"
    python scripts/web_ai.py import stories "<video>" answer.json
    python scripts/run_clip.py "<video>"                    # builds the projects, then WAITs for step 2
    python scripts/web_ai.py export clip "<project folder>"
    python scripts/web_ai.py import clip "<project folder>" answer.json
    python scripts/run_clip.py "<video>" --capcut            # same command again: carries on to the CapCut project

The answer may be pasted bare or inside a ```json block. Local agents save stories answers to
`<video>.web-ai-stories.answer.json`, or clip answers to `<project>/clipkit_web_ai.answer.json`. Use the CLI import
above or let the active app AI box import the saved answer; do not import it twice, because it may cut footage.
The importer validates the answer before writing artifacts; motion rendering and disk failures can still occur
after writing starts. Re-export after edits or cuts before asking for another answer.

AI emits this answer schema, never a replacement `draft_content.json`. EditorKrab builds native projects locally
using installed media and templates. A parsed JSON file is not proof that CapCut opens it; subtitle timestamp
coverage is not proof of alignment to audible speech. Preview and listening checks remain required.

## Common fields

- `clipkit_web_ai`: `1` (this version). Another number is refused: export again from this ClipKit.
- `step`: `"stories"` or `"clip"`; must match the import.
- `video` (stories) / `project` (clip): the file / folder name from the export; guards against importing an answer
  into the wrong video or project.

## `stories`

```json
{"clipkit_web_ai": 1, "step": "stories", "video": "EP07.mov",
 "stories": [{"title": "...", "summary": "...", "start": 12.3, "end": 95.0}]}
```

`title` required, `start < end` in seconds, each story must contain speech. `max_minutes` in the exported packet
is the saved approximate target before selecting content: shorter is acceptable and slightly longer can finish
a complete thought. With a saved target, imported selections are retained rather than split at a hard limit.

## `clip`

Consecutive ASR transport lines can form one semantic group: put optional `through: <last n>` on its head,
whose items cover all original text in that group in source order (whitespace may differ). Keep every original
`n`; continuation entries contain only `{"n": ...}`. Groups cannot overlap or include `cut` lines. Caption and
motion entries refer only to group heads. Actual word clocks are merged without inventing times; selected
emphasis without a complete clock is rejected before files are changed. With no `through`, existing answers
keep their meaning. The manual `/api/video/draft/subs/merge` action uses the same merge helper.

```json
{"clipkit_web_ai": 1, "step": "clip", "project": "EP07 - 1 ...",
 "hook": [{"text": "...", "color": "white|orange|red"}],
 "lines": [{"n": 1, "items": [["lead", "punch", "b-roll search", {"look": "pair", "show": ["", ""]}]]}],
 "cut": [2],
 "motion": [{"n": 3, "template": "hook-title|sentence-pair"}, {"n": 5, "template": "stat-number", "params": {"number": "87", "unit": "%", "label": "..."}}],
 "caption": {"1": "..."}}
```

| field | text layer | rule |
|---|---|---|
| `hook` | HL Hook | `[]` is valid; otherwise 1-2 source-supported lines, `color` white / orange / red |
| `lines[].items` | Subtitle (lead, white) + เน้น (punch, colour) | all original `n` = 1..N in order; group heads have items covering their exact combined text (spaces may differ), continuation entries have only `n`; item `[lead, punch]` + optional search string and/or options `{look: pair|white|color|red|hold|skip, show: [white, colour], color: "#rrggbb", second: "..."}` |
| `cut` | (footage) | optional; line numbers dropped with their footage (up to the next line), via `trim_pauses(ranges=...)`; whole lines only, order kept; a cut line needs no items / caption / motion; at least one line stays. The project's `draft_content.json` is backed up first (`.bak_trim`). Export again before importing a second answer: line numbers change |
| `motion` | Motion text | optional; line number + template, rendered here like the editor's Motion button. `hook-title` / `sentence-pair` are made from the line's words; any other template from the export's `motion_templates` needs `params` (its fields; `duration` defaults to the line's length), checked against the template's clipkit-motion block before anything is written |
| `caption` | small translated caption | required only when the export's `caption_language` is not null; one string per retained group head or ungrouped line number |

Grouping changes subtitle line numbers. Export a fresh packet before another answer; the backup and seal cover
the merged draft, and no source footage is removed by grouping itself. The group head's styling is retained.

## `inserts` (downloaded stock files to links)

After downloading stock clips by hand into one folder:

    python scripts/run_clip.py "<video>" --all --no-ai --capcut --insert-sheet "<folder>"   # writes "<video> - inserts.md" + ".jpg"
    python scripts/run_clip.py "<video>" --all --no-ai --capcut --insert-from "<folder>" --insert-plan answer.json

Upload both files; the picture has one numbered frame per video. The answer pairs files with the page's links:

```json
{"clipkit_web_ai": 1, "step": "inserts", "video": "EP07.mov", "place": [{"file": "coffee-cup-X1.mp4", "link": 2}]}
```

Every file must be in the folder, every link on the page, each used once; a link that already has a file in
`clipkit_insert` raises. Files left out stay in the folder. Nothing moves until the whole answer checks out.
