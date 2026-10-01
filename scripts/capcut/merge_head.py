from kitconfig import DRAFTS, ROOT_META, font_file  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Prepend a time block [T0,T1] of project SRC onto the start of project DST (same track layout).
usage: python merge_head.py "<src>" "<dst>" T0 T1"""
import json, os, sys, glob, shutil, copy, uuid
base = DRAFTS
SP = os.path.join(base, sys.argv[1], 'draft_content.json'); DP = os.path.join(base, sys.argv[2], 'draft_content.json')
T0, T1 = int(float(sys.argv[3]) * 1e6), int(float(sys.argv[4]) * 1e6); D = T1 - T0
s_ = json.load(open(SP, encoding='utf-8')); d = json.load(open(DP, encoding='utf-8'))
SM, DM = s_['materials'], d['materials']
def nid(): return str(uuid.uuid4()).upper()
def find(M, r):
    for k, v in M.items():
        if isinstance(v, list):
            o = next((x for x in v if isinstance(x, dict) and x.get('id') == r), None)
            if o: return k, o
    return None, None
def clone(r):
    k, o = find(SM, r)
    if not o: return None
    c = copy.deepcopy(o); c['id'] = nid(); DM.setdefault(k, []).append(c); return c['id']
def role(doc, t):
    M = doc['materials']; s0 = t['segments'][0]
    k, m = find(M, s0['material_id'])
    if t['type'] == 'text':
        sz = json.loads(m['content'])['styles'][0]['size']
        if len(t['segments']) == 1 and s0['target_timerange']['start'] == 0: return 'hook'
        return 'eng' if sz <= 12 else ('white' if sz <= 27 and s0['clip']['transform']['y'] > -0.35 else 'orange')
    if t['type'] == 'video':
        p = os.path.basename(m.get('path', ''))
        return 'logo' if p == 'logo.png' else ('broll' if p.startswith('bro_') else 'main' if doc['tracks'].index(t) == 0 else 'video?')
    n = (m.get('name') or '').lower()
    return 'click' if 'mouse' in n else 'typing' if 'typing' in n else 'music' if s0['target_timerange']['duration'] > 30e6 else 'audio?' + n[:10]
droles = {role(d, t): t for t in d['tracks'] if t['segments']}
full = lambda s, dur: s['target_timerange']['start'] == 0 and s['target_timerange']['duration'] >= dur - 50000
for t in d['tracks']:
    for s in t['segments']:
        if full(s, d['duration']): s['target_timerange']['duration'] += D
        elif role(d, t) == 'hook': pass
        else: s['target_timerange']['start'] += D
skipped = []
for t in s_['tracks']:
    if not t['segments']: continue
    r = role(s_, t)
    if r in ('logo', 'music', 'hook'): continue
    if r not in droles: skipped.append(r); continue
    for s in t['segments']:
        a = s['target_timerange']['start']; e = a + s['target_timerange']['duration']
        if e <= T0 + 50000 or a >= T1 - 50000: continue
        n = copy.deepcopy(s); n['id'] = nid()
        na, ne = max(a, T0), min(e, T1)
        if n.get('source_timerange'):
            n['source_timerange']['start'] += int((na - a) * n.get('speed', 1)); n['source_timerange']['duration'] = int((ne - na) * n.get('speed', 1))
        n['target_timerange'] = {'start': na - T0, 'duration': ne - na}
        n['material_id'] = clone(s['material_id'])
        n['extra_material_refs'] = [x for x in (clone(r_) for r_ in s.get('extra_material_refs', [])) if x]
        tt = droles[r]; n['track_render_index'] = tt['segments'][0].get('track_render_index', n.get('track_render_index'))
        tt['segments'].append(n)
d['duration'] += D
for t in d['tracks']:
    t['segments'].sort(key=lambda s: s['target_timerange']['start']); p = -1
    for s in t['segments']:
        assert s['target_timerange']['start'] >= p - 1000 and s['target_timerange']['duration'] > 0, (role(d, t), s['target_timerange']['start'] / 1e6)
        p = s['target_timerange']['start'] + s['target_timerange']['duration']
shutil.copy(DP, DP.replace('.json', '.before_merge.json'))
json.dump(d, open(DP, 'w', encoding='utf-8'), ensure_ascii=False)
for tl in glob.glob(os.path.join(os.path.dirname(DP), 'Timelines', '*', 'draft_content.json')): shutil.copy(DP, tl)
print('merged', D / 1e6, 's; new duration', d['duration'] / 1e6, 'skipped roles', skipped, 'dst roles', list(droles))
