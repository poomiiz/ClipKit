# Text standard (measured from BPS3 01-10)

Measured from `draft_content.json` of the ten hand-edited CapCut projects BPS3 01-10 (plus the SUB copies of
04, 06, 07, 08, 09), 661 text segments; the Motion text numbers are from the ten main projects only. Canvas 1080x1920. Size = CapCut `size` x clip scale (ClipKit writes
scale 1, so this is the number a preset uses). y = CapCut transform y (-1 bottom .. 1 top). UNKNOWN = not in
these projects.

All layers: font DB Heavent Bd, centre-aligned, line spacing 0.2, line max width 0.85, black shadow
(alpha 0.7, distance 5, smoothing 0.45, angle -45).

## Motion text (`presets/default.json`)

| | measured (BPS3) | old default |
|---|---|---|
| white line size | 22.7 (172 of 181 lines) | 22 |
| white line y | -0.37 | -0.33 |
| white line outline | #000000, 0.03 | #000000, 0.04 |
| keyword size | 32.2 median; per project 27-41; SUB copies 22.1 | 26 |
| keyword y | -0.50 (SUB copies -0.485) | -0.46 |
| keyword colour | #051192 navy in 9 projects, #ff8000 in BPS3 03 | #ff7d00 |
| keyword outline | #ffffff, 0.03 | #000000, 0.06 |
| white in | "เคอร์เซอร์คู่" 0.5 s (167 of 181) | not in preset (template) |
| keyword in | "คลื่นเสียง" 0.17 s (176 of 182) | not in preset (template) |
| out animation | none | - |
| keyword appears after white | median 1.2 s (p25 0.88, p75 1.7), when the word is spoken | ClipKit caps at 0.6 s |
| end | both lines end together (143 of 160 pairs within 0.03 s) | same |

Line breaking: one line per text, white median 17 characters (max 34), keyword median 15 (max 37). A line break
inside a text is rare (0 white, 3 keyword). Lines split between phrases, never inside a word; an English term stays
whole on one line ("Smart Home", "Fiber Optic To The Room"). 18 of 181 white lines have no keyword under them.
White lines median 2.7 s, keyword median 1.4 s.

## HL Hook (start of clip)

Two lines from 0.03 s, lasting 3.1-7.3 s (median about 4.7 s), the whole block tilted -3 to -8 degrees
(most often -4.68).

| | line 1 | line 2 |
|---|---|---|
| y | -0.38 (older layout -0.265) | -0.51 (older layout -0.42) |
| CapCut size / scale | 32 / 0.7-1.3 | 32 / 0.68-0.93 |
| colours seen | white, black or red #ed1c1c | red #ed1c1c, white or navy |
| in | "คลื่นเสียง" 0.5 s | "เคอร์เซอร์คู่" 0.5 s, starts 0.27 s after line 1 |

ClipKit today (`app/render.py` `_hook`): y -0.37, sizes 30/36, no tilt, 4.0 s. Not changed here.

## ปก (cover)

The hook lines are copied a second time as 0.03 s segments at 0 s, no animation (the frame used as cover),
sometimes a little bigger and lower (line 1 y -0.34).

## เน้น, Subtitle

UNKNOWN: no separate emotional-push layer and no small (size 8) full-transcript subtitle in BPS3 01-10. The
SUB copies use the Motion text pair with the keyword at the white line's size (22.1), not a small subtitle.
