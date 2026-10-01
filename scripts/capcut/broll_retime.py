from kitconfig import DRAFTS, ROOT_META, font_file  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Move b-roll clips (by file name) to new timeline spans.
usage: python broll_retime.py "<project>" '{"file.mp4":[start,end], ...}'
"""
import json, os, sys, glob, shutil
proj = sys.argv[1]; NEW = json.loads(sys.argv[2])
P = os.path.join(DRAFTS, proj, 'draft_content.json')
d = json.load(open(P, encoding='utf-8'))
v = {x['id']: x for x in d['materials']['videos']}
tracks = set(); moved = 0
for t in d['tracks'][1:]:
    if t['type'] != 'video': continue
    for s in t['segments']:
        n = os.path.basename(v[s['material_id']]['path'])
        if n in NEW:
            a, b = NEW[n]; du = min(int((b - a) * 1e6), v[s['material_id']]['duration'])
            s['target_timerange'] = {'start': int(a * 1e6), 'duration': du}
            s['source_timerange'] = {'start': 0, 'duration': du}
            tracks.add(id(t)); moved += 1
for t in d['tracks']:
    if id(t) not in tracks: continue
    t['segments'].sort(key=lambda s: s['target_timerange']['start'])
    prev = -1
    for s in t['segments']:
        a = s['target_timerange']['start']
        assert a >= prev, ('overlap', a / 1e6, os.path.basename(v[s['material_id']]['path']))
        prev = a + s['target_timerange']['duration']
    assert prev <= d['duration'] + 50000, 'past end'
shutil.copy(P, P.replace('.json', '.before_brollretime.json'))
json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False)
for tl in glob.glob(os.path.join(os.path.dirname(P), 'Timelines', '*', 'draft_content.json')): shutil.copy(P, tl)
print(proj[:10], 'moved', moved, 'of', len(NEW))
