from kitconfig import DRAFTS, ROOT_META, font_file  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Add b-roll clips onto the existing b-roll track (clones an existing b-roll segment + material).
usage: python addbroll.py "<project>" '[["path.mp4", start, end], ...]'"""
import json, os, sys, glob, shutil, copy, uuid, subprocess
P = os.path.join(DRAFTS, sys.argv[1], 'draft_content.json')
d = json.load(open(P, encoding='utf-8')); M = d['materials']; ADD = json.loads(sys.argv[2])
V = {v['id']: v for v in M['videos']}
def nid(): return str(uuid.uuid4()).upper()
tr = next(t for t in d['tracks'][1:] if t['type'] == 'video' and any('bro_' in V[s['material_id']]['path'] for s in t['segments']))
tmpl = next(s for s in tr['segments'] if 'bro_' in V[s['material_id']]['path'])
def clone_ref(r):
    for k, v in M.items():
        if isinstance(v, list):
            o = next((x for x in v if isinstance(x, dict) and x.get('id') == r), None)
            if o: c = copy.deepcopy(o); c['id'] = nid(); v.append(c); return c['id']
for path, a, b in ADD:
    dur = int(float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path]).decode()) * 1e6)
    m = copy.deepcopy(V[tmpl['material_id']]); m['id'] = nid(); m['path'] = path.replace(chr(92), '/'); m['material_name'] = os.path.basename(path); m['duration'] = dur
    M['videos'].append(m)
    s = copy.deepcopy(tmpl); s['id'] = nid(); s['material_id'] = m['id']
    s['extra_material_refs'] = [x for x in (clone_ref(r) for r in tmpl['extra_material_refs']) if x]
    du = min(int((b - a) * 1e6), dur)
    s['target_timerange'] = {'start': int(a * 1e6), 'duration': du}; s['source_timerange'] = {'start': 0, 'duration': du}
    tr['segments'].append(s)
tr['segments'].sort(key=lambda s: s['target_timerange']['start']); prev = -1
for s in tr['segments']:
    assert s['target_timerange']['start'] >= prev - 1000, ('overlap', s['target_timerange']['start'] / 1e6)
    prev = s['target_timerange']['start'] + s['target_timerange']['duration']
assert prev <= d['duration'] + 50000
os.path.exists(P.replace('.json', '.before_addbroll2.json')) or shutil.copy(P, P.replace('.json', '.before_addbroll2.json'))  # keep the first original, never overwrite it
json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False)
for tl in glob.glob(os.path.join(os.path.dirname(P), 'Timelines', '*', 'draft_content.json')): shutil.copy(P, tl)
print('added', len(ADD), 'total', len(tr['segments']))
