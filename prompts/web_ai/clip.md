<!-- ClipKit web AI step 2: subtitles, emphasis, clip headline and motion for one clip (put in front of the subtitle data on export; edit freely, no code change needed) -->
# ClipKit step 2: Subtitle / emphasis / HL Hook / Motion text for one clip

The data below is the subtitles of one short clip that is already cut (`lines`: n, start, end in seconds on the clip timeline, text). You do not need to see the video.
ClipKit builds the CapCut project on this machine from your answer: white subtitles (Subtitle), coloured emphasis words (เน้น), a headline for the first 4 seconds (HL Hook) and Motion text.

**Language:** every text you write (lead, punch, show, second, hook) is in the same language as the `text` in `lines`, so the on-screen text matches the clip. Only image search terms are English, and `caption` uses `caption_language`. The examples below are Thai; follow their shape, not their language.

## 0. Tighten the edit (optional)
`cut`: line numbers to drop, picture and sound, such as greetings, repeats, a slip followed by a retake, or going off topic, so the clip is tight and still flows.
Never cut down to less than one line. A cut line needs no items, caption or motion (only whole lines can be cut, and the order stays).

## 1. Subtitle + emphasis (every line that is not cut)
- Split each line into short chunks of about 2 seconds / 10-18 Thai characters (about 3-6 words in other languages), in spoken order, breaking where a thought ends
- Each chunk = `[lead, punch]`: punch is the key word or phrase (a feeling, a number, a result, a brand, e.g. "ถูกกดดัน", "20 ปี", "ไม่อิ่ม"), not just the last word
- **The lead + punch of all chunks joined together must be the line's original text, every character, in order** (spaces may change, nothing else). punch may come first: then lead is ""
- lead is at most about 15 characters; split longer ones into more chunks
- Not every chunk needs colour: fillers and connectors ("อืมๆ", "แบบว่า", repeated words) use `[text, ""]`. Colour only the chunks that carry the point, about half or fewer
- Display options (4th slot, optional) `{"look": ..., "show": [white, colour]}`:
  - `pair` (default) white lead + coloured punch · `white` white only (set-up sentences, questions) · `color` colour only (short chunks that are pure point)
  - `red` red, only for the 1-2 strongest points · `hold` keep the previous white line while the coloured word changes (for lists) · `skip` no subtitle (fillers, repeats, slips)
  - `show`: on-screen words rewritten short and clean ("ไปจ้างพนักงานขายซิ" -> "จ้างเซลส์มาขาย"), at most about 15 characters (lead + punch must still be the spoken words, they set the timing)
  - `color`: "#rrggbb" colour for this chunk only · `second`: a short word from a second person ("ห๊ะ!", "โห")
- Pictures: on about 1 in 3 chunks that talk about something visible, put 2-4 English search words in the 3rd slot, e.g. `["เดี๋ยวมากิน", "กาแฟต่อ", "coffee cup cafe"]`. No brand names, never two chunks in a row
- Chunk shapes: `[lead, punch]`, `[lead, punch, search]`, `[lead, punch, {options}]` or `[lead, punch, search, {options}]`

## 2. HL Hook (clip headline)
1-2 lines, a short promise of what the clip gives, about 8-16 Thai characters (3-5 words) per line, not a sentence from the speech. Colour per line: `white`, `orange` or `red`
(red = warning/shock, orange = promise), e.g. "ทำธุรกิจไม่เหนื่อย / ต้องรู้ 2 เรื่องนี้", "เงิน 5 แสนก็ไม่เอา!"
The headline shows for the first 4 seconds and subtitles in that span are hidden, but every line must still be in lines.

## 3. Motion text (optional)
Lines that should be animated text instead of a subtitle, at most 1-2 per clip: `{"n": line number, "template": "hook-title"}` (big title) or `"sentence-pair"` (emphasis pair)

## 4. caption (only when `caption_language` below is not null)
Translate every line into that language, short and natural, brand names unchanged: `{"1": "...", "2": "..."}`

## Reply

Reply with one JSON object in a ```json block only, no explanation. lines has every line, n = 1..number of lines, in order (a cut line has only n):

```json
{"clipkit_web_ai": 1, "step": "clip", "project": "<name from the project field below>",
 "hook": [{"text": "เริ่มทำธุรกิจใหม่", "color": "red"}, {"text": "ทำสิ่งนี้ก่อน", "color": "white"}],
 "lines": [{"n": 1, "items": [["บางคนบอกต้องลง", "ระบบ Crm", {"look": "hold", "show": ["", "ลงระบบ CRM"]}]]}, {"n": 2}],
 "cut": [2],
 "motion": [{"n": 3, "template": "hook-title"}],
 "caption": null}
```
