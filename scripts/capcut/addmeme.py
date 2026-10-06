from kitconfig import DRAFTS, ROOT_META, font_file  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Add meme sound stings (audio from a local file) on a new audio track.
usage: python addmeme.py "<project>" FILE '[[src_a, src_b, tl_start, volume], ...]'"""
import json, os, sys, glob, shutil, copy, uuid, subprocess
P = os.path.join(DRAFTS, sys.argv[1], 'draft_content.json'); d = json.load(open(P, encoding='utf-8')); M = d['materials']
F = sys.argv[2]; L = json.loads(sys.argv[3])
def nid(): return str(uuid.uuid4()).upper()
mt = next(t for t in d['tracks'] if t['type'] == 'audio' and t['segments'][0]['target_timerange']['duration'] > 20e6)
ms = mt['segments'][0]; mm = next(a for a in M['audios'] if a['id'] == ms['material_id'])
dur = int(float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', F]).decode()) * 1e6)
m = copy.deepcopy(mm); m['id'] = nid(); m['path'] = F.replace(chr(92), '/'); m['name'] = os.path.basename(F); m['duration'] = dur; M['audios'].append(m)
def clone_ref(r):
    for k, v in M.items():
        if isinstance(v, list):
            o = next((x for x in v if isinstance(x, dict) and x.get('id') == r), None)
            if o: c = copy.deepcopy(o); c['id'] = nid(); v.append(c); return c['id']
tr = copy.deepcopy(mt); tr['id'] = nid(); tr['segments'] = []
for a, b, t, vol in L:
    s = copy.deepcopy(ms); s['id'] = nid(); s['material_id'] = m['id']
    s['extra_material_refs'] = [x for x in (clone_ref(r) for r in ms['extra_material_refs']) if x]
    du = min(int((b - a) * 1e6), d['duration'] - int(t * 1e6))
    s['source_timerange'] = {'start': int(a * 1e6), 'duration': du}; s['target_timerange'] = {'start': int(t * 1e6), 'duration': du}; s['volume'] = vol
    tr['segments'].append(s)
d['tracks'].append(tr)
os.path.exists(P.replace('.json', '.before_meme.json')) or shutil.copy(P, P.replace('.json', '.before_meme.json'))  # keep the first original, never overwrite it
json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False)
for tl in glob.glob(os.path.join(os.path.dirname(P), 'Timelines', '*', 'draft_content.json')): shutil.copy(P, tl)
print('stings', len(tr['segments']))
