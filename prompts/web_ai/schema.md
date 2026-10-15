# ClipKit web AI - JSON schema v2 (stories and clip)

Lets an AI in the browser (claude.ai, ChatGPT...) do ClipKit's two judgement steps instead of an agent on this
machine. The AI never needs the video: ClipKit exports the transcript and timings, and the CapCut project is built
on this machine from its own media files.

| step | export (upload this file to the AI) | prompt | import writes |
|---|---|---|---|
| `stories` | `<video>.web-ai-stories.md` | `stories.md` + `../story_split.md` | `<video>.stories.json` + bound `<video>.story-selection.json` |
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

The answer may be pasted bare or inside a ```json block. Each uploaded packet names only the answer's basename;
it contains no local absolute answer path. A local agent saves that file **beside the packet**:
`<video>.web-ai-stories.answer.json`, or `<project>/clipkit_web_ai.answer.json`. Use the CLI import above or let
the active app AI box import it. Both use the same validation, writer lock and durable receipt; retrying the
same answer does not repeat a cut. Browser AI only returns JSON for the person to paste.

Exporting another packet retains a pending local answer as `.answer.json.before-export-<timestamp>`.
A successfully imported local answer is retained as `.answer.json.imported-<packet_id>`. These files are evidence,
not instructions to apply old answers automatically. Readable v1 packets/answers remain historical input;
v1 cannot mutate stories or clips. Export a fresh v2 packet instead of adding invented identity fields to v1.

AI emits this answer schema, never a replacement `draft_content.json`. EditorKrab builds native projects locally
using installed media and templates. A parsed JSON file is not proof that CapCut opens it; subtitle timestamp
coverage is not proof of alignment to audible speech. Preview and listening checks remain required.

## Common fields

- `clipkit_web_ai`: `2` for `stories` and `clip`. Another number is refused: export again from this ClipKit.
- `step`: `"stories"` or `"clip"`; must match the import.
- `video` (stories) / `project` (clip): copy the file / folder name from the export. Names alone are not identity.
- `packet_id`, `revision`, `source_id`: **copy all three exactly from this exported packet** into the answer.
  They are opaque identifiers; never generate, shorten, translate or infer them. `source_id` binds the actual
  canonical source(s), not just a filename. `revision` binds the transcript, brief, saved target, project/cue/word
  state, native timeline copies, style, preset/font and relevant prompt/template/code dependencies.
- The packet's `max_minutes` and `preferences.max_minutes` describe the chosen approximate duration;
  preserve that intent. The identifiers bind the preferences used for the request. Do not add a new duration
  field to the answer or assume a new target without exporting another packet.

## Import, retry and recovery

Every answer without an existing receipt must match the **latest active packet** and its current dependency
revision. Export again after source, transcript, brief, duration, project or style changes. Two files/projects
with the same basename are different work; a packet from one cannot authorize changes to the other.

An already committed `packet_id` plus the same canonical JSON answer returns its stored result, even after
another export or subsequent edits. JSON key order/formatting does not cause a second import. The same packet
with different answer content is rejected; make a fresh packet for a new decision. Receipt replay is not a
rebuild and does not undo later human edits.

The importer prepares metadata and renders unique private motion assets in staging before applying changes
under the shared project writer lock. An ordinary failure rolls back; after an interruption, an application
without a commit receipt is restored before the next edit/import. A durable receipt is the commit point:
recovery/retry must retain that successful edit. If recovery finds unexpected external/native content, it
preserves both versions and stops for review instead of overwriting the new work. Manual controls still edit
the same artifacts under the shared lock. Close CapCut before modifying its project.

These guarantees protect local state; they do not establish audible subtitle alignment, motion placement or
native CapCut compatibility. Keep human playback/listening and native project acceptance as separate gates.

## `stories`

```json
{"clipkit_web_ai": 2, "step": "stories", "video": "EP07.mov",
 "packet_id": "<copy packet_id exactly>", "revision": "<copy revision exactly>", "source_id": "<copy source_id exactly>",
 "stories": [{"title": "...", "summary": "...", "reason": "Why this opens and finishes one point",
              "duration_reason": "Why this duration fits the content and requested target",
              "start_anchor": {"cue_id": "source-1", "word": 1},
              "end_anchor": {"cue_id": "source-3", "word": 7}}]}
```

`title` required, `start < end` in seconds, each story must contain speech. `max_minutes` in the exported packet
is the saved approximate target before selecting content: shorter is acceptable and slightly longer can finish
a complete thought. Accepted selections are retained rather than split at a hard limit, including natural duration.

Packet rows contain stable source `cue_id` values and `words` with original `n`, optional group `end_n`, `text`,
`start`, `end`. Copy `words[].n` for an anchor, even when the numbers skip: Thai ASR pieces are grouped into
complete words. A start anchor resolves to that word's start; an end anchor resolves to its end. Omitting `word`
selects the row edge, including rows without a word clock. ASR row boundaries do not impose story boundaries.
Numeric `start`/`end` remain supported at exact whole-word or row edges; if supplied with anchors they must agree.
The example anchors above are illustrative and must be replaced by real anchors from the current packet.

Normalized stories retain the reasons, anchors, actual `duration_s`, requested `target_s` and `delta_s`.
`review_required` marks a duration deviation greater than max(15 seconds, 20% of target); it never truncates,
splits or approves the story. Humans still judge whether the opening and ending make sense on their own.
The importer stages the list and its binding together. The binding records the exact current input revision
and story-file hash. Legacy, externally changed or stale lists stay readable history but are not current
accepted selections; explicitly revalidate/save them through the manual controls or a current v2 import.
Brief, target, source, transcript/meta and relevant code changes invalidate acceptance. Read-only cache checks
do not issue a packet or overwrite a pending answer. A receipt replay remains historical and never restores it.

## `clip`

Each exported line includes `cue_id`, the subtitle occurrence ID. Copy it into the matching answer entry,
including continuation entries when grouping. Two identical spoken lines can have different word clocks,
emphasis and captions. `n` still refers to the original numbered input; never combine repeated wording
unless it is an explicit consecutive semantic group.

Local `clipkit_words.json`, `clipkit_punch.json`, and `clipkit_caption.json` use `cue:<segment-id>` keys.
Browser/local AI answers still use the packet's numbered contract and importer; do not write sidecars directly.
Unique legacy text keys are read and backed up on first migration. Ambiguous repeated legacy text is refused:
re-transcribe or reselect the affected content rather than inheriting another occurrence's timings.
Merge/split provenance is kept locally in `clipkit_cues.json`; cut undo includes the occurrence sidecars.

Every v2 input entry requires its exact `cue_id`, including cut and continuation entries. The same shared
validator checks merged and unmerged imports, local-agent answers, manual choices and rendering. It preserves
whitespace-only source equivalence, checks option types/keys and real whole-word clock boundaries, and preflights
against the project's actual canvas, font, safe box and preset. A missing clock permits one complete plain cue;
multiple timed phrases or emphasis require actual word clocks. A lead/punch boundary inside a timing token or
Thai syllable is rejected even for a single phrase. Display `show` wording never replaces source words/clocks.

The exported `subtitle_layout` reports real canvas dimensions, resolved font basename/family, safe box and
scaled preset positions/sizes without exposing local font paths. Fixed presets reject overflow with the cue
that needs shorter display wording or a valid semantic split; they never shrink individual phrases silently.
Translated captions remain separate from lead/punch and never fall back to invented source-language translations.
Manual spelling edits explicitly provide `source_text` through the manual editor; an AI answer cannot authorize
that mutation. Corrections default to the project; machine-wide learning requires an explicit opt-in.

Consecutive ASR transport lines can form one semantic group: put optional `through: <last n>` on its head,
whose items cover all original text in that group in source order (whitespace may differ). Keep every original
`n` and its `cue_id`; continuation entries contain only `{"n": ..., "cue_id": "..."}`. Groups cannot overlap or include `cut` lines. Caption and
motion entries refer only to group heads. Actual word clocks are merged without inventing times; selected
emphasis without a complete clock is rejected before files are changed. With no `through`, existing answers
keep their meaning. The manual `/api/video/draft/subs/merge` action uses the same merge helper.

```json
{"clipkit_web_ai": 2, "step": "clip", "project": "EP07 - 1 ...",
 "packet_id": "<copy packet_id exactly>", "revision": "<copy revision exactly>", "source_id": "<copy source_id exactly>",
 "hook": [],
 "lines": [{"n": 1, "cue_id": "<copy this line's cue_id>", "items": [["lead", "punch"]]}],
 "cut": [], "motion": [], "caption": null}
```

This one-line example is illustrative: include every original `n`/`cue_id` from the actual packet, use its
source wording, and supply translated captions when `caption_language` is not null.

| field | text layer | rule |
|---|---|---|
| `hook` | HL Hook | `[]` is valid; otherwise 1-2 source-supported lines, `color` white / orange / red |
| `lines[].items` | Subtitle (lead, white) + เน้น (punch, colour) | all original `n` = 1..N and their `cue_id` in order; group heads have items covering their exact combined text (spaces may differ), continuation entries have only `n` and `cue_id`; item `[lead, punch]` + optional search string and/or options `{look: pair|white|color|red|hold|skip, show: [white, colour], color: "#rrggbb", second: "..."}` |
| `cut` | (footage) | optional; line numbers dropped with their footage (up to the next line), via `trim_pauses(ranges=...)`; whole lines only, order kept; a cut line keeps its `n`/`cue_id` but needs no items / caption / motion; at least one line stays. The draft is backed up and the import journal covers all applied metadata. Export again for a different answer after cutting; an exact retry returns its receipt |
| `motion` | Motion text | optional; line number + template, rendered here like the editor's Motion button. `hook-title` / `sentence-pair` are made from the line's words; any other template from the export's `motion_templates` needs `params` (its fields; `duration` defaults to the line's length), checked against the template's clipkit-motion block before anything is written |
| `caption` | small translated caption | required only when the export's `caption_language` is not null; one string per retained group head or ungrouped line number |

Grouping changes subtitle line numbers. Export a fresh packet before another answer; the backup and seal cover
the merged draft, and no source footage is removed by grouping itself. The group head's styling is retained.

## `inserts` (downloaded stock files to links)

This separate stock-link matcher remains **v1**; the v2 packet identity/import contract above applies only to
`stories` and `clip`. Do not change the inserts answer version or add v2 identifiers to it.

After downloading stock clips by hand into one folder:

    python scripts/run_clip.py "<video>" --all --no-ai --capcut --insert-sheet "<folder>"   # writes "<video> - inserts.md" + ".jpg"
    python scripts/run_clip.py "<video>" --all --no-ai --capcut --insert-from "<folder>" --insert-plan answer.json

Upload both files; the picture has one numbered frame per video. The answer pairs files with the page's links:

```json
{"clipkit_web_ai": 1, "step": "inserts", "video": "EP07.mov", "place": [{"file": "coffee-cup-X1.mp4", "link": 2}]}
```

Every file must be in the folder, every link on the page, each used once; a link that already has a file in
`clipkit_insert` raises. Files left out stay in the folder. Nothing moves until the whole answer checks out.
