from kitconfig import DRAFTS, ROOT_META, font_file  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Add white/orange cards into empty spans only (keeps user's existing cards).
usage: python addcards.py "<project>" cards.json   cards = [[ws, we, white, os, orange], ...]  (orange may be "")"""
import json, os, sys, glob, shutil, copy, uuid
P = os.path.join(DRAFTS, sys.argv[1], 'draft_content.json')
d = json.load(open(P, encoding='utf-8')); M = d['materials']
C = json.load(open(sys.argv[2], encoding='utf-8'))
tex = {t['id']: t for t in M['texts']}
def nid(): return str(uuid.uuid4()).upper()
def size_of(s): return json.loads(tex[s['material_id']]['content'])['styles'][0]['size']
cards = [t for t in d['tracks'] if t['type'] == 'text' and t['segments'] and not (len(t['segments']) == 1 and t['segments'][0]['target_timerange']['start'] <= 200000) and all(size_of(s) > 12 for s in t['segments'])]
white = min(cards, key=lambda t: sum(size_of(s) for s in t['segments']) / len(t['segments']))
orange = [t for t in cards if t is not white][0]
tw, to = white['segments'][-1], orange['segments'][-1]
for t in (white, orange): t['segments'] = [x for x in t['segments'] if x['target_timerange']['duration'] != 100000]
COMB = set(chr(c) for c in [0x0E31] + list(range(0x0E34, 0x0E3B)) + list(range(0x0E47, 0x0E4F)))
def vis(s): return sum(1 for ch in s if ch not in COMB)
def mk(tmpl, text, a, b, size=None):
    s = copy.deepcopy(tmpl); s['id'] = nid()
    m = copy.deepcopy(tex[tmpl['material_id']]); m['id'] = nid()
    c = json.loads(m['content']); c['text'] = text
    for x in c['styles']:
        x['range'] = [0, len(text)]
        if size: x['size'] = size
    m['content'] = json.dumps(c, ensure_ascii=False); M['texts'].append(m); s['material_id'] = m['id']
    refs = []
    for r in s.get('extra_material_refs', []):
        for k, v in M.items():
            if isinstance(v, list):
                o = next((x for x in v if isinstance(x, dict) and x.get('id') == r), None)
                if o: cc = copy.deepcopy(o); cc['id'] = nid(); v.append(cc); refs.append(cc['id']); break
    s['extra_material_refs'] = refs
    s['target_timerange'] = {'start': int(a * 1e6), 'duration': int((b - a) * 1e6)}
    return s
so = max([size_of(s) for s in orange['segments']] or [size_of(to)])
auds = {a['id']: a for a in M['audios']}
click = next((t for t in d['tracks'] if t['type'] == 'audio' and t['segments'] and 'mouse' in auds[t['segments'][0]['material_id']]['name'].lower()), None)
if click: click['segments'] = [x for x in click['segments'] if x['target_timerange']['duration'] != 100000] or click['segments']  # click placeholder
CT = copy.deepcopy(click['segments'][0]) if click else None
for ws, we, w, os_, o in C:
    white['segments'].append(mk(tw, w, ws, we))
    if o:
        orange['segments'].append(mk(to, o, os_, we, so if vis(o) <= 21 else max(20, int(so * 21 / vis(o)))))
        if click:
            c = copy.deepcopy(CT); c['id'] = nid(); c['target_timerange'] = {'start': int(os_ * 1e6), 'duration': CT['target_timerange']['duration']}
            click['segments'].append(c)
if click: click['segments'] = [x for x in click['segments'] if x['target_timerange']['duration'] != 100000]
for t in d['tracks']:
    t['segments'].sort(key=lambda s: s['target_timerange']['start']); prev = -1
    for s in t['segments']:
        assert s['target_timerange']['start'] >= prev - 1000, ('overlap', t['type'], s['target_timerange']['start'] / 1e6)
        prev = s['target_timerange']['start'] + s['target_timerange']['duration']
    assert prev <= d['duration'] + 50000, ('past end', t['type'])
os.path.exists(P.replace('.json', '.before_addcards.json')) or shutil.copy(P, P.replace('.json', '.before_addcards.json'))  # keep the first original, never overwrite it
json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False)
for tl in glob.glob(os.path.join(os.path.dirname(P), 'Timelines', '*', 'draft_content.json')): shutil.copy(P, tl)
print('added', len(C))
