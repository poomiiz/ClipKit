from kitconfig import DRAFTS, ROOT_META, font_file  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Replace a project's English subtitle track with speech-timed lines, styled like the user's Nina 06 English.
usage: python set_english.py "<project>" lines.json english.json
lines.json   = [[start, end, thai_asr], ...]  (from sublines.py)
english.json = ["line 0 english", "line 1 english", ...]  same length as lines.json ("" = skip)
"""
import json, os, sys, copy, uuid, glob, shutil
base = DRAFTS
proj, lf, ef = sys.argv[1], sys.argv[2], sys.argv[3]
L = json.load(open(lf, encoding='utf-8')); E = json.load(open(ef, encoding='utf-8'))
assert len(L) == len(E), (len(L), len(E))
P = os.path.join(base, proj, 'draft_content.json')
d = json.load(open(P, encoding='utf-8')); M = d['materials']
ref = json.load(open(os.path.join(base, [x for x in os.listdir(base) if x.startswith('Nina 06')][0], 'draft_content.json'), encoding='utf-8'))
rtex = {t['id']: t for t in ref['materials']['texts']}
def nid(): return str(uuid.uuid4()).upper()
def rsize(s): return json.loads(rtex[s['material_id']]['content'])['styles'][0]['size']
rtrack = [t for t in ref['tracks'] if t['type'] == 'text' and len(t['segments']) > 5 and all(rsize(s) <= 10 for s in t['segments'])][0]
tseg = copy.deepcopy(rtrack['segments'][1]); tmat = copy.deepcopy(rtex[tseg['material_id']])
def refmat(mid):
    for k, v in ref['materials'].items():
        if isinstance(v, list):
            for m in v:
                if isinstance(m, dict) and m.get('id') == mid: return k, m
    return None, None

tex = {t['id']: t for t in M['texts']}
def size(s): return json.loads(tex[s['material_id']]['content'])['styles'][0]['size']
eng = [t for t in d['tracks'] if t['type'] == 'text' and len(t['segments']) > 5 and all(size(s) <= 10 for s in t['segments'])]
if eng: eng = eng[0]
else:
    eng = copy.deepcopy(rtrack); eng['segments'] = []
    if 'id' in eng: eng['id'] = nid()
    d['tracks'].append(eng)
ri = eng['segments'][0]['track_render_index'] if eng['segments'] else max(s.get('track_render_index', 0) for t in d['tracks'] for s in t['segments']) + 1
eng['segments'] = []
dur = d['duration'] / 1e6
rows = [(a, b, e) for (a, b, _), e in zip(L, E) if e]
for i, (a, b, e) in enumerate(rows):
    nxt = rows[i + 1][0] if i + 1 < len(rows) else dur
    end = min(nxt - 0.03, max(b + 0.35, a + 1.2)) if nxt - b < 1.0 else min(b + 0.5, nxt - 0.03)
    end = min(end, dur)
    s = copy.deepcopy(tseg); s['id'] = nid()
    m = copy.deepcopy(tmat); m['id'] = nid()
    c = json.loads(m['content']); c['text'] = e
    for x in c['styles']: x['range'] = [0, len(e)]
    m['content'] = json.dumps(c, ensure_ascii=False); M['texts'].append(m); s['material_id'] = m['id']
    out = []
    for r in s['extra_material_refs']:
        k, mm = refmat(r)
        if mm is None: continue
        cc = copy.deepcopy(mm); cc['id'] = nid(); M.setdefault(k, []).append(cc); out.append(cc['id'])
    s['extra_material_refs'] = out
    s['target_timerange'] = {'start': int(a * 1e6), 'duration': int((end - a) * 1e6)}
    s['track_render_index'] = ri
    eng['segments'].append(s)
used = {s['material_id'] for t in d['tracks'] for s in t['segments']}
M['texts'] = [m for m in M['texts'] if m['id'] in used]
prev = -1
for s in eng['segments']:
    assert s['target_timerange']['start'] >= prev - 1000 and s['target_timerange']['duration'] > 0
    prev = s['target_timerange']['start'] + s['target_timerange']['duration']
os.path.exists(P.replace('.json', '.before_english.json')) or shutil.copy(P, P.replace('.json', '.before_english.json'))  # keep the first original, never overwrite it
json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False)
for tl in glob.glob(os.path.join(os.path.dirname(P), 'Timelines', '*', 'draft_content.json')): shutil.copy(P, tl)
print(proj[:10], 'english lines', len(eng['segments']))
