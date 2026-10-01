import sys as _s; from pathlib import Path as _P; _s.path.insert(0, str(_P(__file__).resolve().parents[1] / 'capcut'))
from kitconfig import DRAFTS, STOCK, OLD_BUILDS, FFMPEG, enable_cuda_libs  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Check a built episode: nothing dangling, nothing overlapping, every file
present, and the cut audio re-transcribed so clipped words show up.

Usage: python verify_episode.py "<draft folder name>"
"""
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
_enable_cuda_libs = enable_cuda_libs
from faster_whisper import WhisperModel  # noqa: E402

US = 1e6
draft = Path(DRAFTS) / sys.argv[1]
c = json.loads((draft / 'draft_content.json').read_text(encoding='utf-8'))
ids = {m['id']: (k, m) for k, v in c['materials'].items() if isinstance(v, list)
       for m in v if isinstance(m, dict) and 'id' in m}
used = {s['material_id'] for t in c['tracks'] for s in t['segments']}
dangling = sum(r not in ids for t in c['tracks'] for s in t['segments']
               for r in [s['material_id'], *s.get('extra_material_refs', [])])
overlaps = []
for ti, t in enumerate(c['tracks']):
    ss = sorted(t['segments'], key=lambda s: s['target_timerange']['start'])
    overlaps += [ti for a, b in zip(ss, ss[1:])
                 if a['target_timerange']['start'] + a['target_timerange']['duration'] > b['target_timerange']['start'] + 1000]
missing = [ids[u][1]['path'] for u in used if ids[u][0] in ('videos', 'audios') and ids[u][1].get('path')
           and '##' not in ids[u][1]['path'] and not Path(ids[u][1]['path']).exists()]
past_src = [Path(ids[s['material_id']][1]['path']).name for t in c['tracks'] for s in t['segments']
            if ids[s['material_id']][0] == 'videos' and s.get('source_timerange')
            and s['source_timerange']['start'] + s['source_timerange']['duration'] > ids[s['material_id']][1]['duration'] + 1000]
from fix_timeline_ids import check as _check_tl  # noqa: E402
timeline = _check_tl(draft) or 'ok'
print(f"duration {c['duration'] / US:.1f}s | dangling {dangling} | overlaps {overlaps} | missing {missing} | past source end {past_src} | timeline ids {timeline}")

work = Path(__file__).with_name('_work')
work.mkdir(exist_ok=True)
segs = sorted(c['tracks'][0]['segments'], key=lambda s: s['target_timerange']['start'])
cam = ids[segs[0]['material_id']][1]['path']
parts = []
for i, s in enumerate(segs):
    f = work / f'v{i:03d}.wav'
    subprocess.run([FFMPEG, '-y', '-v', 'error', '-ss', f"{s['source_timerange']['start'] / US:.3f}",
                    '-t', f"{s['source_timerange']['duration'] / US:.3f}", '-i', cam, '-ac', '1', '-ar', '16000', str(f)],
                   check=True)
    parts.append(f)
(work / 'v.txt').write_text(''.join(f"file '{p.as_posix()}'\n" for p in parts), encoding='utf-8')
subprocess.run([FFMPEG, '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(work / 'v.txt'),
                '-c', 'copy', str(work / 'episode.wav')], check=True)
_enable_cuda_libs()
# int8 weights: same large-v3, about half the memory; float16 ran out of VRAM
# while other apps were holding part of the 8 GB card (2026-09-19)
model = WhisperModel('large-v3', device='cuda', compute_type='int8_float16')
r, _ = model.transcribe(str(work / 'episode.wav'), language='th', beam_size=5, condition_on_previous_text=False)
for x in r:
    print(f'{x.start:5.1f} {x.text}')
