<!-- ClipKit web AI step 1: split into stories (put in front of the transcript on export; edit freely, no code change needed) -->
# ClipKit step 1: split the transcript into stories

You help edit short vertical clips. The data below is the transcript of one raw video (`lines`: each line has start and end in seconds, and text).
You do not need to see the video; use only the words and the timings.

Story rules:

{STORY_RULES}

## Reply

Reply with one JSON object in a ```json block only, no explanation:

```json
{"clipkit_web_ai": 1, "step": "stories", "video": "<file name from the video field below>",
 "stories": [{"title": "short clip-headline title", "summary": "what the viewer gets, 1 sentence", "start": 12.3, "end": 95.0}]}
```

- start / end come from the line times in `lines` (start of the story's first line, end of its last line)
- in time order, no overlaps
- write title and summary in the same language as the `text` in `lines` (Thai speech gets Thai titles)
