from kitconfig import DRAFTS, ROOT_META, font_file  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""End a project at T seconds: drop/clip segments after T, update meta + CapCut registry durations.
usage: python trimtail.py "<project>" T"""
import json, os, sys, glob, shutil
base = DRAFTS
P = os.path.join(base, sys.argv[1], 'draft_content.json'); T = int(float(sys.argv[2]) * 1e6)
d = json.load(open(P, encoding='utf-8'))
for t in d['tracks']:
    out = []
    for s in t['segments']:
        tr = s['target_timerange']
        if tr['start'] >= T - 200000: continue
        if tr['start'] + tr['duration'] > T:
            tr['duration'] = T - tr['start']
            if s.get('source_timerange'): s['source_timerange']['duration'] = int(tr['duration'] * s.get('speed', 1))
        out.append(s)
    t['segments'] = out
d['tracks'] = [t for t in d['tracks'] if t['segments']]
d['duration'] = T
os.path.exists(P.replace('.json', '.before_trimtail.json')) or shutil.copy(P, P.replace('.json', '.before_trimtail.json'))  # keep the first original, never overwrite it
json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False)
for tl in glob.glob(os.path.join(os.path.dirname(P), 'Timelines', '*', 'draft_content.json')): shutil.copy(P, tl)
mp = os.path.join(base, sys.argv[1], 'draft_meta_info.json'); m = json.load(open(mp, encoding='utf-8')); m['tm_duration'] = T
json.dump(m, open(mp, 'w', encoding='utf-8'), ensure_ascii=False)
RM = ROOT_META
r = json.load(open(RM, encoding='utf-8'))
for e in r['all_draft_store']:
    if e['draft_name'] == sys.argv[1]: e['tm_duration'] = T
json.dump(r, open(RM, 'w', encoding='utf-8'), ensure_ascii=False)
print(sys.argv[1][:8], 'duration', T / 1e6)
