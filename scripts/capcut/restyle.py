from kitconfig import DRAFTS, ROOT_META, font_file  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Restyle a project's white + orange card tracks to match Nina 07's standard cards (keeps text + timing).
usage: python restyle.py "<project>" """
import json, os, sys, glob, shutil, copy, uuid
from collections import Counter
base = DRAFTS
P = os.path.join(base, sys.argv[1], 'draft_content.json')
d = json.load(open(P, encoding='utf-8')); M = d['materials']
ref = json.load(open(os.path.join(base, [x for x in os.listdir(base) if x.startswith('Nina 07')][0], 'draft_content.json'), encoding='utf-8'))
RM = ref['materials']; rtex = {t['id']: t for t in RM['texts']}
def nid(): return str(uuid.uuid4()).upper()
def sz(tex, s): return json.loads(tex[s['material_id']]['content'])['styles'][0]['size']
def templ(want_y):  # most common segment near y in ref
    segs = [s for t in ref['tracks'] if t['type'] == 'text' for s in t['segments']
            if abs(s['clip']['transform']['y'] - want_y) < 0.02 and s['clip']['scale']['x'] == 1.0]
    key = Counter((sz(rtex, s), round(s['clip']['transform']['y'], 2)) for s in segs).most_common(1)[0][0]
    return next(s for s in segs if (sz(rtex, s), round(s['clip']['transform']['y'], 2)) == key)
TW, TO = templ(-0.29), templ(-0.44)
def rfind(r):
    for k, v in RM.items():
        if isinstance(v, list):
            o = next((x for x in v if isinstance(x, dict) and x.get('id') == r), None)
            if o: return k, o
    return None, None
COMB = set(chr(c) for c in [0x0E31] + list(range(0x0E34, 0x0E3B)) + list(range(0x0E47, 0x0E4F)))
def vis(s): return max(sum(1 for ch in l if ch not in COMB) for l in s.split('\n'))
tex = {t['id']: t for t in M['texts']}
cards = [t for t in d['tracks'] if t['type'] == 'text' and len(t['segments']) > 3 and all(sz(tex, s) > 12 for s in t['segments'])]
white = min(cards, key=lambda t: sum(sz(tex, s) for s in t['segments']) / len(t['segments']))
orange = [t for t in cards if t is not white]
def rebuild(track, T):
    base_size = sz(rtex, T); out = []
    for s in track['segments']:
        text = json.loads(tex[s['material_id']]['content'])['text']
        n = copy.deepcopy(T); n['id'] = nid()
        m = copy.deepcopy(rtex[T['material_id']]); m['id'] = nid()
        c = json.loads(m['content']); c['text'] = text
        size = base_size if vis(text) * base_size <= 600 else int(600 / vis(text))
        for x in c['styles']: x['range'] = [0, len(text)]; x['size'] = size
        m['content'] = json.dumps(c, ensure_ascii=False); M['texts'].append(m); n['material_id'] = m['id']
        refs = []
        for r in T['extra_material_refs']:
            k, o = rfind(r)
            if o: cc = copy.deepcopy(o); cc['id'] = nid(); M.setdefault(k, []).append(cc); refs.append(cc['id'])
        n['extra_material_refs'] = refs
        n['target_timerange'] = s['target_timerange']; n['render_index'] = s.get('render_index', n.get('render_index'))
        n['track_render_index'] = s.get('track_render_index', n.get('track_render_index'))
        out.append(n)
    track['segments'] = out
rebuild(white, TW)
for t in orange: rebuild(t, TO)
used = {s['material_id'] for t in d['tracks'] for s in t['segments']}
M['texts'] = [m for m in M['texts'] if m['id'] in used]
os.path.exists(P.replace('.json', '.before_restyle.json')) or shutil.copy(P, P.replace('.json', '.before_restyle.json'))  # keep the first original, never overwrite it
json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False)
for tl in glob.glob(os.path.join(os.path.dirname(P), 'Timelines', '*', 'draft_content.json')): shutil.copy(P, tl)
print(sys.argv[1][:8], 'white', len(white['segments']), 'orange', sum(len(t['segments']) for t in orange))
