from kitconfig import DRAFTS, ROOT_META, font_file  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Rebuild a project's main track from a list of source cuts and clear cards/inserts/SFX/English (keeps hook, logo, music).
usage: python rebuild_main.py "<project>" cuts.json      cuts = [["IMG_5113-001.mov", a, b], ...]"""
import json, os, sys, glob, shutil, copy, uuid
base = DRAFTS
P = os.path.join(base, sys.argv[1], 'draft_content.json'); d = json.load(open(P, encoding='utf-8')); M = d['materials']
C = json.load(open(sys.argv[2], encoding='utf-8'))
def nid(): return str(uuid.uuid4()).upper()
V = {v['id']: v for v in M['videos']}
main = d['tracks'][0]; tmpl = main['segments'][0]
mats = {os.path.basename(v['path']): v for v in M['videos'] if 'Footage' in v['path']}
for name in {c[0] for c in C} - set(mats):  # borrow material from another Nina draft
    for f in glob.glob(os.path.join(base, 'Nina *', 'draft_content.json')):
        o = next((v for v in json.load(open(f, encoding='utf-8'))['materials']['videos'] if os.path.basename(v['path']) == name), None)
        if o: o = copy.deepcopy(o); o['id'] = nid(); M['videos'].append(o); mats[name] = o; break
def clone_ref(r):
    for k, v in M.items():
        if isinstance(v, list):
            o = next((x for x in v if isinstance(x, dict) and x.get('id') == r), None)
            if o: c = copy.deepcopy(o); c['id'] = nid(); v.append(c); return c['id']
segs = []; t = 0
for name, a, b in C:
    s = copy.deepcopy(tmpl); s['id'] = nid(); s['material_id'] = mats[name]['id']
    s['extra_material_refs'] = [x for x in (clone_ref(r) for r in tmpl['extra_material_refs']) if x]
    du = int((b - a) * 1e6); s['source_timerange'] = {'start': int(a * 1e6), 'duration': du}; s['target_timerange'] = {'start': t, 'duration': du}
    s['clip']['scale'] = {'x': 1.0, 'y': 1.0}; s['clip']['transform'] = {'x': 0.0, 'y': 0.0}
    segs.append(s); t += du
main['segments'] = segs; T = t
keep = []
for tr in d['tracks'][1:]:
    if not tr['segments']: continue
    s0 = tr['segments'][0]
    full = s0['target_timerange']['start'] == 0 and len(tr['segments']) == 1 and s0['target_timerange']['duration'] > 20e6
    hook = tr['type'] == 'text' and len(tr['segments']) == 1 and s0['target_timerange']['start'] <= 200000 and not full
    if full:
        s0['target_timerange']['duration'] = T
        if s0.get('source_timerange') and tr['type'] == 'audio': s0['source_timerange']['duration'] = T
        keep.append(tr)
    elif hook: keep.append(tr)
    elif tr['type'] == 'text' and all(json.loads(next(x for x in M['texts'] if x['id'] == s['material_id'])['content'])['styles'][0]['size'] > 12 for s in tr['segments']) and len(tr['segments']) > 3:
        tr['segments'] = tr['segments'][:1]; tr['segments'][0]['target_timerange'] = {'start': T - 100000, 'duration': 100000}; keep.append(tr)  # keep card track as template
    elif tr['type'] == 'audio' or (tr['type'] == 'video'):
        tr['segments'] = tr['segments'][:1]; tr['segments'][0]['target_timerange'] = {'start': T - 100000, 'duration': min(100000, tr['segments'][0]['target_timerange']['duration'])}; keep.append(tr)
d['tracks'] = [main] + keep; d['duration'] = T
os.path.exists(P.replace('.json', '.before_rebuild.json')) or shutil.copy(P, P.replace('.json', '.before_rebuild.json'))  # keep the first original, never overwrite it
json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False)
for tl in glob.glob(os.path.join(os.path.dirname(P), 'Timelines', '*', 'draft_content.json')): shutil.copy(P, tl)
print('duration', T / 1e6, 'tracks', [(tr['type'], len(tr['segments'])) for tr in d['tracks']])
