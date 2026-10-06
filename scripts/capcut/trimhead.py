from kitconfig import DRAFTS, ROOT_META, font_file  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Cut the first T seconds off a project: drop/trim/shift every segment. Hook text track (single segment at 0), logo and music stay anchored at 0.
usage: python trimhead.py "<project>" T"""
import json, os, sys, glob, shutil
P = os.path.join(DRAFTS, sys.argv[1], 'draft_content.json')
T = int(float(sys.argv[2]) * 1e6)
d = json.load(open(P, encoding='utf-8'))
full = lambda s: s['target_timerange']['start'] == 0 and s['target_timerange']['duration'] >= d['duration'] - 50000
for i, t in enumerate(d['tracks']):
    hook = t['type'] == 'text' and len(t['segments']) == 1 and t['segments'][0]['target_timerange']['start'] == 0
    out = []
    for s in t['segments']:
        tr = s['target_timerange']
        if hook or full(s):
            if full(s): tr['duration'] -= T
            out.append(s); continue
        a, e = tr['start'], tr['start'] + tr['duration']
        if e <= T: continue
        cut = max(0, T - a)
        if cut:
            sr = s.get('source_timerange')
            if sr: sr['start'] += int(cut * s.get('speed', 1)); sr['duration'] -= int(cut * s.get('speed', 1))
        tr['start'] = a + cut - T; tr['duration'] = e - a - cut
        out.append(s)
    t['segments'] = out
d['duration'] -= T
for t in d['tracks']:
    prev = -1
    for s in t['segments']:
        assert s['target_timerange']['start'] >= prev - 1000 and s['target_timerange']['duration'] > 0
        prev = s['target_timerange']['start'] + s['target_timerange']['duration']
    assert prev <= d['duration'] + 50000
os.path.exists(P.replace('.json', '.before_trimhead.json')) or shutil.copy(P, P.replace('.json', '.before_trimhead.json'))  # keep the first original, never overwrite it
json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False)
for tl in glob.glob(os.path.join(os.path.dirname(P), 'Timelines', '*', 'draft_content.json')): shutil.copy(P, tl)
print('new duration', d['duration'] / 1e6)
