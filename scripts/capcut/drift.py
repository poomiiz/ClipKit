from kitconfig import DRAFTS, ROOT_META, font_file  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Measure how far each Thai card is from where its words are actually spoken.
usage: python drift.py "<project>" words.json
"""
import json, os, sys, difflib
proj, wf = sys.argv[1], sys.argv[2]
d = json.load(open(os.path.join(DRAFTS, proj, 'draft_content.json'), encoding='utf-8'))
tex = {t['id']: t for t in d['materials']['texts']}
W = json.load(open(wf, encoding='utf-8'))
def norm(s): return ''.join(ch for ch in s.lower() if ch.isalnum())
stream = ''; times = []
for a, b, t in W:
    for ch in norm(t): stream += ch; times.append(a)

def locate(text, around, span=10.0):
    key = norm(text)
    if len(key) < 2: return None
    best = (0, None)
    for i in range(len(stream)):
        if abs(times[i] - around) > span: continue
        r = difflib.SequenceMatcher(None, stream[i:i + len(key)], key).ratio()
        if r > best[0]: best = (r, times[i])
    return best if best[0] >= 0.55 else None

rows = []
for t in d['tracks']:
    if t['type'] != 'text' or len(t['segments']) <= 5: continue
    for s in t['segments']:
        c = json.loads(tex[s['material_id']]['content'])
        if c['styles'][0]['size'] <= 10: continue
        st = s['target_timerange']['start'] / 1e6
        f = locate(c['text'], st)
        rows.append((st, c['styles'][0]['size'], c['text'].replace('\n', ' '), None if not f else round(f[1] - st, 2), None if not f else round(f[0], 2)))
rows.sort()
for st, sz, txt, dl, r in rows:
    print(f'{st:6.2f} sz{sz:<3} {txt[:26]:28s} spoken {"%+.2fs" % dl if dl is not None else "   ?  "} (match {r})')
ds = [r[3] for r in rows if r[3] is not None]
if ds:
    ds.sort(); print('median drift %+.2fs | late(>+1s) %d | early(<-1s) %d | unmatched %d of %d' %
                     (ds[len(ds) // 2], sum(x > 1 for x in ds), sum(x < -1 for x in ds), len(rows) - len(ds), len(rows)))
