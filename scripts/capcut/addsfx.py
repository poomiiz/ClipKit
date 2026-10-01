from kitconfig import DRAFTS, ROOT_META, font_file  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Put back mouse-click SFX on every orange pop and typing SFX on every white card, using templates from a backup draft.
usage: python addsfx.py "<project>" "<template draft json>" """
import json, os, sys, glob, shutil, copy, uuid
P = os.path.join(DRAFTS, sys.argv[1], 'draft_content.json')
d = json.load(open(P, encoding='utf-8')); t_ = json.load(open(sys.argv[2], encoding='utf-8')); M, TM = d['materials'], t_['materials']
def nid(): return str(uuid.uuid4()).upper()
TA = {a['id']: a for a in TM['audios']}
def tmpl(word):
    for t in t_['tracks']:
        for s in t['segments']:
            if t['type'] == 'audio' and word in TA.get(s['material_id'], {}).get('name', '').lower(): return t, s
def clone_ref(r):
    for k, v in TM.items():
        if isinstance(v, list):
            o = next((x for x in v if isinstance(x, dict) and x.get('id') == r), None)
            if o: c = copy.deepcopy(o); c['id'] = nid(); M.setdefault(k, []).append(c); return c['id']
tex = {t['id']: json.loads(t['content']) for t in M['texts']}
cards = [(t, s) for t in d['tracks'] if t['type'] == 'text' for s in t['segments'] if tex[s['material_id']]['styles'][0]['size'] > 12]
hook = {id(s) for t, s in cards if s['target_timerange']['duration'] > 5e6 and s['target_timerange']['start'] < 200000}
orange = sorted(s['target_timerange']['start'] for t, s in cards if id(s) not in hook and tex[s['material_id']]['styles'][0]['size'] >= 28)
white = sorted((s['target_timerange']['start'], s['target_timerange']['duration']) for t, s in cards if id(s) not in hook and tex[s['material_id']]['styles'][0]['size'] < 28)
for word, times in (('mouse', [(a, None) for a in orange]), ('typing', white)):
    tt, ts = tmpl(word)
    mat = copy.deepcopy(TA[ts['material_id']]); mat['id'] = nid(); M['audios'].append(mat)
    tr = copy.deepcopy(tt); tr['id'] = nid(); tr['segments'] = []
    prev = -1
    for a, du in times:
        if a < prev: continue
        s = copy.deepcopy(ts); s['id'] = nid(); s['material_id'] = mat['id']
        s['extra_material_refs'] = [x for x in (clone_ref(r) for r in ts.get('extra_material_refs', [])) if x]
        L = ts['target_timerange']['duration'] if du is None else min(ts['target_timerange']['duration'], du - 50000)
        L = min(L, d['duration'] - a)
        if L <= 100000: continue
        s['target_timerange'] = {'start': a, 'duration': L}; s['source_timerange'] = {'start': ts['source_timerange']['start'], 'duration': L}
        tr['segments'].append(s); prev = a + L
    d['tracks'].append(tr); print(word, len(tr['segments']))
shutil.copy(P, P.replace('.json', '.before_sfx.json'))
json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False)
for tl in glob.glob(os.path.join(os.path.dirname(P), 'Timelines', '*', 'draft_content.json')): shutil.copy(P, tl)
