# -*- coding: utf-8 -*-
"""Word-timed ASR of source footage ranges. usage: python wordasr.py FILE a-b [a-b ...]"""
import sys, subprocess, os, tempfile
from faster_whisper import WhisperModel
m = WhisperModel('medium', device='cpu', compute_type='int8')
f = sys.argv[1]
for r in sys.argv[2:]:
    a, b = map(float, r.split('-'))
    w = os.path.join(tempfile.gettempdir(), 'wa.wav')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(a), '-t', str(b - a), '-i', f, '-vn', '-ac', '1', '-ar', '16000', w], check=True)
    print('=====', r)
    for s in m.transcribe(w, language='th', word_timestamps=True)[0]:
        ws = ''.join(f'[{a + x.start:.1f}]{x.word.strip()}' if i % 3 == 0 else x.word.strip() for i, x in enumerate(s.words))
        print(f'{a + s.start:7.2f}-{a + s.end:7.2f} {ws}')
