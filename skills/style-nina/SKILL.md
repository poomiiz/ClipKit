---
name: style-nina
description: Style guide + technique manual for editing Nina (Nina Digital / @kruningnina) TikTok talking-head clips in CapCut, extracted from projects Nina 01–07. Use when cutting, captioning, adding B-roll/SFX/music, or reviewing any Nina clip draft (CapCut drafts named `Nina *` under `capcut_drafts` in config.json). Use together with clip-workflow, broll-finder and clip-qc.
---

# Nina clip editing guide (from Nina 01–07)

Source of truth = user's own edits: **Nina 01** (card style), **Nina 06** (English subs), **Nina 07** (reaction jokes, current look). When unsure, open those drafts and copy values.

## 1. Format
- 1080x1920 vertical, 60–120 s (01: 59 s · 02: 88 · 03: 103 · 04: 66 · 05: 73 · 06: 98 · 07: 117).
- One clip = one idea. The title must be something actually said in the kept audio (never promise content that was cut, e.g. "3 ปี" in 07).
- Before building, check the clip's content against every earlier clip: no repeated story, point or punchline. Neighbouring source ranges often overlap at the edges (07 tail = 08 head; 07 ending = 06 opening line).

## 2. Cutting (main track)
- Jump cuts on breaths and fillers: 01/07 average 2–3 s per cut (28 and 40 cuts). Longer takes (6–9 s) only when the story flows (04, 05).
- Main audio volume ≈ 2.24 (+7 dB); 01 at 2.72, 02 at 3.0.
- **Punch-in zoom for reactions:** scale 2.1–2.7, x −1.1…−1.7, y 0.1–0.2 = crop onto the other speaker when she reacts or asks. Straight cut, no keyframe. 1–5 per clip.
- Never end mid-sentence. Extend the last cut to the end of the sentence.
- No transitions, no stickers, no video effects in any clip.

## 3. Thai keyword cards (the core look)
Font **DB Heavent Bd v3.2.1**, stroke on, shadow on, text animation in 0.3 s.

| Layer | Size | Colour | y | Animation | Hold |
|---|---|---|---|---|---|
| White context line | 22–25 | white | −0.29 … −0.33 (01: −0.60) | เครื่องพิมพ์ดีด (typewriter) 0.3 s | ~2.2–3.3 s |
| Orange punch | 30–37 | orange (1, 0.49, 0) | −0.43 … −0.46 | คลื่นเสียง or เครื่องพิมพ์ดีด 0.3 s | ~1.3–2.1 s |
| Red quote / shock | 27–37 | red (0.93, 0.11, 0.11) | −0.30 … −0.41 | เส้นทางเคอร์เซอร์ / typewriter | ~2.3 s |
| Hook (0–4 s) | 36 | orange | +0.15 (07: red at −0.37) | none | 4.0 s |

Rules:
- White = the setup ("บางคนบอก", "ถ้าพูดในแง่"). Orange = the keyword or punch, which pops **on the exact spoken word** and ends with its white line.
- Cards are short, 2–6 words: rewrite, don't transcribe ("ยิ่งหลืบ ยิ่งเซ็กซี่", "จักรวาลติดหนี้", "2-3 นาทีก็เสร็จ!").
- Use `!` and `?` for tone, "..." for suspense ("แต่ถามว่า...").
- **Keep English words that were spoken in English**: Branding, CRM, Connection, Overwhelm, Consult, Flow, Journey, Push, Sustainable, Last Long, Incentive, Approve, Go.
- Quotes go in red with quotation marks: “ได้ 5 แสน เองเหรอวะ?”
- Single-word hits ("ให้", "ใช่") can be enlarged with scale 1.2–1.9 on their own track for repetition gags (04: "ให้ ให้ ให้").
- Special emphasis titles get a flashier animation: ลำแสงหนาม-I, เส้นคลื่น, ซูมเข้า 0.23 s.
- Cover every spoken stretch. There must be no silent-caption gaps longer than ~1 s while someone is talking.
- Hooks longer than one line need a manual `\n` (CapCut does not auto-wrap). Count visible Thai characters without combining marks, and shrink a card when it has more than 21.

## 4. Humour / มุข
- **Red reaction cards** (07): the listener's interjections as tiny red cards, size 34, scale 0.84, animation มิดไนท์คลับ 0.5 s. Examples: "อ่าใช่", "จิงดิ", "เห็นพูดจ้อยๆๆ", "นี้เรา", "เบื่อ", "ดูไม่ออก". Keep the colloquial spelling.
- **Side-comment white cards**, slide-in (สไลด์เข้าอย่างรวดเร็ว 0.5 s, scale 0.68): "สนิทกันแล้วหรอ", "จริง".
- **Joke SFX** on a punchline, at most once per clip: the cow moo ("Mo ~ ♪ … cow 03") landed on "ถ้า CEO พลาดขึ้นมา" (06).
- Punch-in on the listener's face (section 2) for her reactions.
- Exaggerate the numbers and contrasts she says ("5 แสนก็ไม่เอา!", "มาเป็นสิบๆ ปี!" vs "ทำแค่ไม่กี่ปี").

## 5. English subtitles
- Font en.ttf, size 8–10 (06 = 9), white, y −0.80, no animation.
- One line per breath (≤ ~3.5 s), speech-timed from the real audio. Don't bind them to card timing.
- Natural short English. Use `- A/- B` for two speakers in one line.
- The user now writes the English subs himself. Don't overwrite them.

## 6. B-roll inserts
- One insert roughly every 5–8 s, 2–5 s each (07 now has 19 in 117 s). Place it on the spoken keyword it illustrates.
- Stock footage from Envato (downloads land in `stock_video` from config.json) plus real screenshots or logos (Grab, LINE MAN, Google, road signs, HEIC photos).
- **Inserts = the original stock file, not a pre-cropped copy.** Put the raw horizontal clip on the insert track and scale it to fill the full 9:16 height, letting the left and right sides overflow. For 16:9 that is scale ≈3.16, and for 1280x672 ≈3.39. The user then slides it in CapCut to frame the real focus point. Use `scripts/capcut/addraw.py`. (User order 2026-09-29, replacing both the center-crop and the blurred-fit approaches.)
- Muted (volume 0).

## 7. Audio
- Music: calm lofi / piano / minimal, volume 0.09–0.12 (`Assets/Music`).
- `PC mouse 05-1` click on every orange pop. `sfx_pop` or typing sounds on white cards. SFX volume 0.15–0.38.

## 8. Branding
- `logo.png`: full-frame 1080x1920 transparent overlay (top-right name tag + @kruningnina) for the whole duration. No text tags.

## 9. Workflow + tools (`scripts/capcut/` in this kit)
1. Close CapCut first (it overwrites the JSON). Back up `draft_content.json`, and also copy it to `Timelines/*/draft_content.json`.
2. `timeline_asr.py` (set `ASR_STEP=8`) transcribes the **real edited timeline**. Never caption from the raw transcript.
3. `sublines.py` splits speech into breath lines. `rebeat.py` builds cards from beats in the speech. `addcards.py` fills gaps without touching the user's cards.
4. `addbroll.py` / `broll_retime.py` add or move inserts. `trimhead.py` cuts the start of a clip. After a trim, update `tm_duration` in `draft_meta_info.json` and `root_meta_info.json`, and drop empty tracks.
5. `preview.py` renders a proxy. Look at frames before reporting.
6. Renames go through `renumber.py`-style edits: folder + `draft_meta_info` + CapCut `root_meta_info.json`.
7. Pilot one clip, then have the user check it in CapCut before rolling out to the rest.

## 10. Lessons from the user's own re-edit of Nina 08 (2026-09-29)
Compared with Claude's version (110.9 s), the user's final 08 (92.9 s) changed the following:
- **Cut the personal opening.** The user dropped the "Introvert ในคราบ Extrovert" story block and opened straight on the point ("ต้องรู้ 2 เรื่อง: ตัวตน + สเตจธุรกิจ"). The clip must open on the promise in the title, not on a warm-up anecdote.
- **Reordered and borrowed.** The user appended the "สมมติไปเช่าคอนโด / อัด 20 คลิป / ส่งทีละล็อต / อัดเป็นแบช" example (source 472–496 s) as the proof, and moved one earlier line (453.8–459.1) to after the stutter beat. Rearranging source order is fine when it makes a setup → example → punchline flow.
- **Hook:** white (not red), size 40, y −0.37, scale 0.84, มิดไนท์คลับ, held ~7 s over the opening.
- **Cards are denser and shorter.** White cards cover every phrase ("คนที่กำลัง", "แกมีลูกค้าอะไร"). Orange pops last 0.4–1.5 s ("เหอะๆ", "ใช่", "เหนื่อย!").
- **Reaction and joke cards:**
  - Short interjections use the shake animation (อาการภาพสั่น) at y −0.08 … −0.18: "เหอะๆ", "ไม่ไป", "ไม่อยากคุย", "กับคนแปลกหน้า".
  - Question beats slide in (เลื่อนเข้า): "BNI", "คืออะไรก่อน?", "เคยไปแล้วไง".
- **Stutter / zoom punch:**
  - The rhetorical question "อย่างนี้รู้สึกฝืนไหม" gets a 3-step zoom ramp: scale 1.07 → 1.28 → 1.49, about 0.25 s each.
  - That beat also gets comic effects: เส้นความเร็ว, then วิ่งแข่ง 1 a few seconds later.
  - Rapid micro-cuts of 0.2–0.5 s build the stutter before the payoff.
- **Colour:** effect สีขาวอบอุ่น (warm white) on the main footage.
- **Inserts are flash cuts of 0.6–2.4 s**, not 3–5 s. The user kept 11 of 22 inserts, each placed exactly on the keyword.
- English subs and the click/typing SFX were missing only because the user retimed every card. They are still part of the style: after the user retimes, re-add a click on each orange pop and typing on each white card (`scripts/capcut/addsfx.py`). The user writes the English subs.

## 11. Detailed card choreography (user's final 08 + 09, 2026-09-29)

### Layers and defaults
| Role | Size | Position (x, y) | Rotation | Animation |
|---|---|---|---|---|
| Speaker context (white) | 25 | 0, −0.29 | 0 | เครื่องพิมพ์ดีด in 0.3 s |
| Speaker punch (orange) | 30 (27–28 if long) | 0, −0.44 | 0 | คลื่นเสียง in 0.3 s |
| **Second person / listener line** | 25 white (or 30 orange) | **off-center x ±0.3…0.7**, y −0.1…−0.5 | **tilted ±5…15°** | **เลื่อนเข้า in 0.27–0.5 s** (slides in from the screen edge) |
| Listener reaction / scoff | 25 | x ±0.2…0.6 | ±7…9° | อาการภาพสั่น loop 0.37–0.5 s (shake) |

### Second-person rule (the key technique)
- Anything the **other person** says ("BNI?", "คืออะไรก่อน?", "เคยไปแล้วไง", "อันนี้น่าสนใจนะ", "น่าจะ", "แต่นี่น่าสนใจนะ", "ไม่ฝืน") is **never centered**.
- Push it toward the side of the frame the voice comes from, tilt it, and slide it in with เลื่อนเข้า. The viewer reads it as a separate voice without any name tag.
- Mocking or reluctant interjections ("เหอะๆ", "ไม่ไป", "ไม่อยากคุย", "กับคนแปลกหน้า") use the shake loop instead of a slide.
- Keep them short: 0.4–1.7 s, 1–3 words.

### Word play with the main speaker's words
- **Split a list into scattered big words.** "อึด" / "ทน" / "ถึก" each get their own track:
  - scale 1.72
  - different positions (x −0.5, +0.05, +0.57; y −0.05 … +0.18)
  - animation การตระหนักรู้ loop 1.0 s
  - they pop one after another about 0.2 s apart
- **Echo a stressed word left and right.** "เยอะ" appears twice at once: x −0.42 and x +0.53, scale 1.27–1.57, animation คลื่นเสียง 0.2 s.
- **Contrast pairs sit on opposite sides.**
  - "มันขัด": x −0.41, rotation −9°, scale 1.26
  - "มันฝืน!": x +0.46, rotation +6°, scale 1.26
- **Laugh beats.** Put "555+" twice (x −0.30 and +0.70, opposite tilts) with ความโกลาหลของพินบอล loop, plus the วิ่งแข่ง 1 effect for the same ~1.5 s.
- Rewrite the punch into the speaker's own slang when it's funnier: "ถึก", "เสาร์ อาทิตย์ ไม่มีหยุด", "มีคราวหน้าอีก?".

### Hook (two layers)
- Big keyword in red, size 58, scale 0.84, rotation −4°, y −0.37, มิดไนท์คลับ in 0.5 s, held 5.5 s (e.g. "Burn out").
- White sub-line under it, size 30, y −0.56, same −4° tilt, typewriter in 0.5 s, starting 0.8 s later (e.g. "เพราะพลาดเรื่องนี้").

### Inserts
- Raw stock clip at scale 3.16–3.41, **x shifted ±0.7…1.25** to frame the real subject (never left centered by default). Flash length 0.7–2.4 s.
- Pre-made vertical clips stay at scale 1.0.

### Effects
- One-shot comic effects only on gags:
  - เส้นความเร็ว ~0.7 s on a zoom punch
  - วิ่งแข่ง 1 ~0.6–1.5 s on a laugh or payoff
- A section in a different mood (e.g. the lifestyle "texture / eating" tail appended to 09) gets a continuous texture effect across the whole section: สปาร์เคิลเกรน. This marks it visually as a separate part.

### Cutting
- Median cut 1.7–2.3 s. Micro-cuts under 0.6 s only to build a stutter before a punchline.
- Zoom punch ramp: scale 1.07 → 1.28 → 1.49, about 0.25 s each, then the effect.

## 12. Storytelling: how Nina clips are told (from the user's 01–09)

### Format
Every clip is a **two-person conversation**. Nina (the expert) talks. The listener stands in for the audience: she asks the viewer's question, doubts, and laughs. Keep the listener's lines; they are the viewer's voice and the source of most jokes. See the second-person card rule in §11.

### Spine: one idea per clip
**Hook (promise) → Setup → Proof (story or example) → Twist or reveal → One-line lesson → Button (joke or teaser)**

| Beat | What it does | Seen in |
|---|---|---|
| Hook, 0–5 s | One promise in ≤ 2 short lines, shown as the title card | "ทำธุรกิจไม่เหนื่อย ต้องรู้ 2 เรื่องนี้", "เงิน 5 แสนก็ไม่เอา!", "Burn out เพราะพลาดเรื่องนี้" |
| Setup | The common belief or the viewer's situation | "บางคนบอกทำแบรนด์ บางคนบอกลง CRM…" (07), "ร้านใหม่ชอบให้สะสมแต้ม" (03) |
| Proof | A concrete story with real numbers, brands and places | ชิโอปัง 60–70 บาท (02); โรงแรมเมืองจีน (02); 5 แสน (05); ตี 2 ตี 4 นอน 9 โมง (09); BNI ทุกวันพฤหัส (08) |
| Twist / reveal | The surprise that flips the belief | "เขาไม่ทำ CRM เลยแต่ขายดี เพราะให้มา 10 ปี จักรวาลติดหนี้" (04); "แต่เราเป็นผู้หญิง" (09) |
| Lesson | One short line, usually the speaker's own words | "ต้องแก้ตามสไตล์ตัวเอง" (07), "เพราะเป็นทางของแก" (08) |
| Button | End on a laugh, a quote punch or a teaser. **Never** on dead air or mid-sentence | "แกจะไปฟ้องเขา!" (02), "ได้ 5 แสนเองเหรอวะ?" (05), "จบคลิปมั้ย? ไปละ!" (09) |

### Hook formulas the user uses
- **Number / shock:** "เงิน 5 แสนก็ไม่เอา!"
- **Contrarian:** "ไม่ต้องแย่งทำเลอีกแล้ว", "ขายดีโดยไม่ต้องง้อ CRM"
- **Question the viewer has:** "ร้านใหม่ CRM ตอนไหนถึงจะเวิร์ก", "ต้องเริ่มแก้ตรงไหนก่อน"
- **List promise:** "ต้องรู้ 2 เรื่องนี้"
- **Confession:** "Burn out เพราะพลาดเรื่องนี้"
- **Principle as metaphor:** "ตีเหล็กตอนที่ยังร้อน"

### Rules the user enforced while re-editing
1. **Open on the promise, not the warm-up.**
   - The user cut the personal Introvert story out of 08's opening. A personal anecdote belongs in the Proof beat, not before the hook pays off.
2. **Every clip must give the viewer something to take away.**
   - Ask "คนดูได้อะไร?" A clip that is only about Nina's life needs a lesson line, or it gets merged into another clip.
3. **Rearrange freely, but keep her voice.**
   - Source order can be shuffled (08: the batch-record example moved to the end as proof). Never rewrite what she means.
   - Cards paraphrase in her slang ("ถึก", "ป้าบ้าของ", "มีคราวหน้าอีก?").
4. **No duplicates across the series.**
   - Before cutting, list every point the earlier clips already made. Neighbouring source ranges overlap at the edges.
   - If two clips share a point, merge them (08 + 09 old, 09 + the texture clip) or drop one.
5. **Proof beats need specifics.**
   - Keep the numbers, prices, brand names, times of day and places. Cut generic filler around them.
6. **Keep the laughs.**
   - Stutters, "เหอะๆ", self-roasts ("ป้าบ้าของ", "ไม่มีลูก ไม่มีสามี") and the listener's jabs stay in. They get joke cards (§4, §11), not cuts.
7. **Endings.**
   - Finish the sentence, then add a button: a laugh, a quote punch, or a tease for the next episode ("ตอนหน้ามาคุยเรื่องความผิดพลาด").
   - A lighter lifestyle or behind-the-scenes tail may follow the button, marked by a texture effect (สปาร์เคิลเกรน, as in 09) instead of a standalone clip.
8. **Length follows content:** 60–130 s. Longer is fine when the story holds; cut dead air, not substance.
