---
name: broll-finder
description: Find B-roll inserts for a talking-head clip - turn the transcript into timed search keywords, search Envato through the team bot, build one HTML picker page with previews and checkboxes, then queue downloads of only the ticked items and file them by topic. Use for "หาอินเสิร์ต", "หา B-roll", "ลิสต์ลิงก์ Envato", "โหลด Envato".
---

# B-roll finder

## Rule that never changes
**Each Envato download registers a licence on the company account.** Only download items a person ticked. Never auto-download search results.

## Steps
1. **Keyword list** - read the edited-timeline transcript and write `broll_plan.json`:
   `[{"t": 12.4, "dur": 1.5, "said": "ช่างไฟตรวจตู้", "query": "electrician checking control panel", "topic": "01_ผู้รับเหมา_งานระบบ"}]`
   - English queries work best on Envato. Describe the shot, not the idea.
   - One insert every 5-8 s; flash length 1-2.5 s.
   - Reuse files already in the client's stock folder before searching (match by file name).
2. **Search** - `python scripts/broll_picker.py search broll_plan.json` queues one Envato search job per row on the team bot (runs on the bot host only) and waits for the results.
3. **Picker page** - `python scripts/broll_picker.py html broll_plan.json` writes `broll_picker.html`: rows in clip order, each with the spoken line, the query, 3-4 Envato titles as links (open to preview) with checkboxes, and the bot's search screenshot. The **Export** button saves `broll_selected.json`.
4. **Person ticks** - send the HTML to the person who owns the Envato decision. Wait.
5. **Download** - `python scripts/broll_picker.py download broll_selected.json` queues one download job per ticked item (1080p, never 4K). Files are renamed `<topic>/<NN>_<said>.mp4` into the clip's insert folder.

## Without the bot
On a machine without bot access, stop after step 3 and give the person the HTML. They download by hand from the links into the topic folders.
