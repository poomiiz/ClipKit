# ClipKit web AI - JSON schema v1

Lets an AI in the browser (claude.ai, ChatGPT...) do ClipKit's two judgement steps instead of an agent on this
machine. The AI never needs the video: ClipKit exports the transcript and timings, and the CapCut project is built
on this machine from its own media files.

| step | export (upload this file to the AI) | prompt | import writes |
|---|---|---|---|
| `stories` | `<video>.web-ai-stories.md` | `stories.md` + `../story_split.md` | `<video>.stories.json` |
| `clip` | `<project>/clipkit_web_ai.md` | `clip.md` | `clipkit_punch.json`, `clipkit_hook.json`, `clipkit_caption.json` (only when the preset has a translated caption), motion (`clipkit_overlays.json`) |

From the app: the "AI บนเว็บ" box under the paste-to-Claude command (story split, and เลือกคำเน้น). From a terminal:

    python scripts/web_ai.py export stories "<video>"
    python scripts/web_ai.py import stories "<video>" answer.json
    python scripts/run_clip.py "<video>"                    # builds the projects, then WAITs for step 2
    python scripts/web_ai.py export clip "<project folder>"
    python scripts/web_ai.py import clip "<project folder>" answer.json
    python scripts/run_clip.py "<video>" --capcut            # same command again: carries on to the CapCut project

The answer may be pasted bare or inside a ```json block. Every field is checked before anything is written; a bad
answer raises with the line at fault and changes nothing (motion is rendered last, after the files are written).

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

`title` required, `start < end` in seconds, each story must contain speech. Stories longer than `run_clip --max`
are still split at a pause by ClipKit, as for the local agent.

## `clip`

```json
{"clipkit_web_ai": 1, "step": "clip", "project": "EP07 - 1 ...",
 "hook": [{"text": "...", "color": "white|orange|red"}],
 "lines": [{"n": 1, "items": [["lead", "punch", "b-roll search", {"look": "pair", "show": ["", ""]}]]}],
 "motion": [{"n": 3, "template": "hook-title|sentence-pair"}],
 "caption": {"1": "..."}}
```

| field | text layer | rule |
|---|---|---|
| `hook` | HL Hook | 1-2 lines, `color` white / orange / red |
| `lines[].items` | Subtitle (lead, white) + เน้น (punch, colour) | every subtitle line, `n` = 1..N in order; lead + punch of all items = the line's exact text (spaces may differ); item `[lead, punch]` + optional search string and/or options `{look: pair|white|color|red|hold|skip, show: [white, colour], color: "#rrggbb", second: "..."}` |
| `motion` | Motion text | optional; line number + template, rendered here like the editor's Motion button |
| `caption` | small translated caption | required only when the export's `caption_language` is not null; one string per line number |
