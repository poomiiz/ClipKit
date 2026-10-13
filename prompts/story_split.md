<!-- The story rules Claude / Codex use for "ClipKit: แบ่งเรื่อง" (see skills/make-clip); edit freely, no code change needed -->
Read the transcript in <video>.transcript.json (each line has start and end in seconds).

Split it into stories that can each be cut into a separate short vertical clip:
- one point per story, one continuous range, no jumping ahead
- split by point, do not squeeze the length (the clip's length is trimmed later, when repeats and slips are cut); usually 1-3 minutes per story; a point longer than 4 minutes is split by its sub-points
- start on the sentence that opens the point, not on a greeting or a warm-up, and end on a finished sentence, never mid-sentence
- skip parts with no substance, such as greetings, thanks, or talk about the shoot itself
- title = a short clip-headline title that pulls viewers in, summary = what the viewer gets, 1 sentence
- write title and summary in the same language the video is spoken in

Output: the file <video>.stories.json as JSON [{"title": "...", "summary": "...", "start": seconds, "end": seconds}]
