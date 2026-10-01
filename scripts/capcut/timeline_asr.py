from kitconfig import DRAFTS, ROOT_META, font_file  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Rebuild a draft's timeline audio (main cuts only) and run faster_whisper with word timestamps.
usage: python timeline_asr.py "<project>" out_words.json
"""
import json, os, sys, subprocess, tempfile
from faster_whisper import WhisperModel

proj, out = sys.argv[1], sys.argv[2]
d = json.load(open(os.path.join(DRAFTS, proj, 'draft_content.json'), encoding='utf-8'))
vids = {v['id']: v for v in d['materials']['videos']}
main = [t for t in d['tracks'] if t['type'] == 'video'][0]['segments']
src = vids[main[0]['material_id']]['path']
tmp = tempfile.mkdtemp(); parts = []
for i, s in enumerate(sorted(main, key=lambda s: s['target_timerange']['start'])):
    a = s['source_timerange']['start'] / 1e6; du = s['source_timerange']['duration'] / 1e6
    p = os.path.join(tmp, f'a{i:03d}.wav')
    subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{a:.3f}', '-t', f'{du:.3f}', '-i', src, '-vn', '-ac', '1', '-ar', '16000', '-y', p], check=True)
    parts.append(p)
lst = os.path.join(tmp, 'l.txt'); open(lst, 'w').write(''.join(f"file '{p}'\n" for p in parts))
wav = os.path.join(tmp, 'all.wav')
subprocess.run(['ffmpeg', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', '-y', wav], check=True)
m = WhisperModel(os.environ.get('ASR_MODEL', 'medium'), device='cpu', compute_type='int8')
import soundfile as sf
y, sr = sf.read(wav)
W = []
step = float(os.environ.get("ASR_STEP", "10"))
t = 0.0
while t < len(y) / sr:
    chunk = os.path.join(tmp, 'c.wav')
    sf.write(chunk, y[int(t * sr):int(min(len(y) / sr, t + step + 1.0) * sr)], sr)
    segs, _ = m.transcribe(chunk, language='th', word_timestamps=True, condition_on_previous_text=False, vad_filter=False)
    for s_ in segs:
        for w in s_.words:
            if w.start < step or t + step >= len(y) / sr:      # overlap second belongs to next chunk
                W.append((round(t + w.start, 2), round(t + w.end, 2), w.word.strip()))
    t += step
json.dump(W, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
print(proj[:12], 'words', len(W))
