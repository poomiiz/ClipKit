from kitconfig import DRAFTS, ROOT_META, font_file  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Give a project white + orange card tracks (one template segment each at the end) cloned from a reference Nina draft.
usage: python import_cardtracks.py "<project>" "<ref prefix e.g. Nina 08>" """
import json, os, sys, glob, shutil, copy, uuid
base = DRAFTS
P = os.path.join(base, sys.argv[1], 'draft_content.json'); d = json.load(open(P, encoding='utf-8')); M = d['materials']
ref = json.load(open(os.path.join(base, [x for x in os.listdir(base) if x.startswith(sys.argv[2])][0], 'draft_content.json'), encoding='utf-8')); RM = ref['materials']
rtex = {t['id']: t for t in RM['texts']}
def nid(): return str(uuid.uuid4()).upper()
def sz(s): return json.loads(rtex[s['material_id']]['content'])['styles'][0]['size']
def rclone(r):
    for k, v in RM.items():
        if isinstance(v, list):
            o = next((x for x in v if isinstance(x, dict) and x.get('id') == r), None)
            if o: c = copy.deepcopy(o); c['id'] = nid(); M.setdefault(k, []).append(c); return c['id']
cands = [t for t in ref['tracks'] if t['type'] == 'text' and len(t['segments']) > 5 and all(sz(s) > 12 for s in t['segments'])]
white = min(cands, key=lambda t: sum(sz(s) for s in t['segments']) / len(t['segments'])); orange = [t for t in cands if t is not white][0]
T = d['duration']
for src, want in ((white, 25), (orange, 30)):
    s0 = next(s for s in src['segments'] if sz(s) == want and abs(s['clip']['scale']['x'] - 1) < 0.01)
    tr = copy.deepcopy(src); tr['id'] = nid()
    s = copy.deepcopy(s0); s['id'] = nid(); s['material_id'] = rclone(s0['material_id'])
    s['extra_material_refs'] = [x for x in (rclone(r) for r in s0['extra_material_refs']) if x]
    s['target_timerange'] = {'start': T - 100000, 'duration': 100000}
    tr['segments'] = [s]; d['tracks'].append(tr)
shutil.copy(P, P.replace('.json', '.before_import.json'))
json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False)
print('imported card tracks from', sys.argv[2])
