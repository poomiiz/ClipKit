import sys as _s; from pathlib import Path as _P; _s.path.insert(0, str(_P(__file__).resolve().parents[1] / 'capcut'))
from kitconfig import DRAFTS, STOCK, OLD_BUILDS, FFMPEG, enable_cuda_libs  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Everything needed to cut one BPS3 episode from a take:
Whisper segments with word timings, and the silences (-24 dB) marked by
whether they fall between Whisper segments (safe to cut) or not.

Usage: python analyze_range.py <camera file> <start s> <length s>
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
_enable_cuda_libs = enable_cuda_libs
from faster_whisper import WhisperModel  # noqa: E402

cam, t0, length = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
work = Path(__file__).with_name('_work')
work.mkdir(exist_ok=True)
_enable_cuda_libs()
# int8 weights: same large-v3, about half the memory; float16 ran out of VRAM
# while other apps were holding part of the 8 GB card (2026-09-19)
model = WhisperModel('large-v3', device='cuda', compute_type='int8_float16')
segments, words = [], []
# 60 s windows: a two-minute pass with word timings ran the 8 GB card out of
# memory once other apps held some of it (2026-09-19)
step = 60.0
w0 = t0
while w0 < t0 + length - 0.5:
    span = min(step, t0 + length - w0)
    wav = work / 'range.wav'
    subprocess.run([FFMPEG, '-y', '-v', 'error', '-ss', str(w0), '-t', str(span), '-i', cam,
                    '-ac', '1', '-ar', '16000', str(wav)], check=True)
    segs, _ = model.transcribe(str(wav), language='th', beam_size=5, word_timestamps=True,
                               condition_on_previous_text=False)
    for s in segs:
        segments.append((round(w0 + s.start, 2), round(w0 + s.end, 2), s.text.strip()))
        for w in s.words:
            words.append((round(w0 + w.start, 2), round(w0 + w.end, 2), w.word.strip()))
    w0 += span

run = subprocess.run([FFMPEG, '-ss', str(t0), '-t', str(length), '-i', cam, '-vn', '-af',
                      'silencedetect=n=-24dB:d=0.28', '-f', 'null', '-'],
                     capture_output=True, text=True, encoding='utf-8', errors='replace')
vals = [float(v) for v in re.findall(r'silence_(?:start|end): ([0-9.]+)', run.stderr)]
silences = [(round(t0 + a, 2), round(t0 + b, 2)) for a, b in zip(vals[0::2], vals[1::2])]
gaps = [(a[1], b[0]) for a, b in zip(segments, segments[1:])]

print('== segments')
for a, b, t in segments:
    print(f'{a:7.2f}-{b:7.2f} {t}')
print('== silences (G = between Whisper segments, safe to cut)')
out = []
for a, b in silences:
    between = any(ga - 0.15 <= a + (b - a) / 2 <= gb + 0.15 for ga, gb in gaps)
    out.append(f"({a:.2f},{b:.2f}){'G' if between else ''}")
print(' '.join(out))
print('== tokens')
print(' '.join(f'{a:.1f}{w}' for a, _, w in words))
json.dump({'segments': segments, 'words': words, 'silences': silences},
          open(work / f'range_{int(t0)}.json', 'w', encoding='utf-8'), ensure_ascii=False)
