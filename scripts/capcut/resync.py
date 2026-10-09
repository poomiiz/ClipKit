from kitconfig import DRAFTS, ROOT_META, font_file  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Re-align Thai cards to the actual speech (from timeline ASR word timestamps).
- white/context card: moved to where its words are spoken if found within +-3s
- orange/punch card: pops in when its keyword is spoken (punch-on-keyword style), ends with its white card
- English line: follows its white card
- mouse-click SFX follow the orange pops
usage: python resync.py "<project>" words.json [--dry]
"""
import json, os, sys, glob, shutil, difflib

proj, wf = sys.argv[1], sys.argv[2]; dry = '--dry' in sys.argv
P = os.path.join(DRAFTS, proj, 'draft_content.json')
d = json.load(open(P, encoding='utf-8'))
tex = {t['id']: t for t in d['materials']['texts']}
auds = {a['id']: a for a in d['materials']['audios']}
W = json.load(open(wf, encoding='utf-8'))
def norm(s): return ''.join(ch for ch in s.lower() if ch.isalnum())
stream = ''; times = []
for a, b, t in W:
    for ch in norm(t): stream += ch; times.append(a)

def locate(text, lo, hi, thr):
    key = norm(text)
    if len(key) < 2: return None
    best = (0, None)
    for i in range(len(stream)):
        if times[i] < lo or times[i] > hi: continue
        r = difflib.SequenceMatcher(None, stream[i:i + len(key)], key).ratio()
        if r > best[0]: best = (r, times[i])
    return best[1] if best[0] >= thr else None

def txt(s): return json.loads(tex[s['material_id']]['content'])['text']
def size(s): return json.loads(tex[s['material_id']]['content'])['styles'][0]['size']
cards = [t for t in d['tracks'] if t['type'] == 'text' and len(t['segments']) > 5]
eng = [t for t in cards if all(size(s) <= 10 for s in t['segments'])]
th = [t for t in cards if t not in eng]
white = min(th, key=lambda t: sum(size(s) for s in t['segments']) / len(t['segments']))
orange = [t for t in th if t is not white][0]
eng = eng[0] if eng else None
dur = d['duration'] / 1e6
def span(s): a = s['target_timerange']['start'] / 1e6; return a, a + s['target_timerange']['duration'] / 1e6
def setspan(s, a, b): s['target_timerange'] = {'start': int(a * 1e6), 'duration': int(max(0.3, b - a) * 1e6)}

ws = sorted(white['segments'], key=lambda s: s['target_timerange']['start'])
os_ = sorted(orange['segments'], key=lambda s: s['target_timerange']['start'])
es = sorted(eng['segments'], key=lambda s: s['target_timerange']['start']) if eng else []
def partner(lst, a, b):
    c = [s for s in lst if abs(span(s)[0] - a) < 0.6 or (span(s)[0] >= a - 0.05 and span(s)[0] < b - 0.2)]
    return c[0] if c else None

log = []
# 1) white starts
new_ws = []
for i, s in enumerate(ws):
    a, b = span(s)
    f = locate(txt(s), a - 3.0, a + 3.0, 0.72)
    na = f - 0.1 if f is not None else a
    new_ws.append([s, a, b, max(0.0, na)])
for i in range(len(new_ws)):                       # keep order + minimum length
    prev_end = new_ws[i - 1][3] + 0.8 if i else 0.0
    new_ws[i][3] = max(new_ws[i][3], prev_end)
for i, (s, a, b, na) in enumerate(new_ws):
    nb = new_ws[i + 1][3] - 0.05 if i + 1 < len(new_ws) else min(dur, max(b, na + 1.0))
    if b < nb - 1.5 and i + 1 < len(new_ws): nb = max(b, na + 1.0)   # don't stretch across long gaps
    o = partner(os_, a, b); e = partner(es, a, b)
    setspan(s, na, nb)
    if o is not None:
        oa, ob = span(o)
        f = locate(txt(o), na, nb + 1.2, 0.62)
        noa = f - 0.1 if f is not None else na + (nb - na) * 0.35
        noa = min(max(noa, na + 0.25), nb - 0.7)
        setspan(o, noa, nb)
        log.append(f'{a:6.2f}->{na:6.2f} W {txt(s)[:18]:20s} | O {oa:6.2f}->{noa:6.2f} {txt(o)[:18]}{"" if f is not None else "  (keyword not heard, 35%)"}')
    else:
        log.append(f'{a:6.2f}->{na:6.2f} W {txt(s)[:18]:20s}')
    if e is not None: setspan(e, na, nb)

# orphan orange cards (no white) keep their own time; check overlaps
for t in (white, orange) + ((eng,) if eng else ()):
    t['segments'].sort(key=lambda s: s['target_timerange']['start'])
    for x, y in zip(t['segments'], t['segments'][1:]):
        xe = x['target_timerange']['start'] + x['target_timerange']['duration']
        if xe > y['target_timerange']['start']:
            x['target_timerange']['duration'] = max(300000, y['target_timerange']['start'] - x['target_timerange']['start'] - 30000)

for t in d['tracks']:
    if t['type'] != 'audio' or not t['segments']: continue
    if 'mouse' not in auds[t['segments'][0]['material_id']]['name'].lower(): continue
    segs = sorted(t['segments'], key=lambda s: s['target_timerange']['start'])
    if len(segs) == len(orange['segments']):
        for c, o in zip(segs, orange['segments']): c['target_timerange']['start'] = o['target_timerange']['start']

for l in log: print(l)
if dry: sys.exit(0)
os.path.exists(P.replace('.json', '.before_resync.json')) or shutil.copy(P, P.replace('.json', '.before_resync.json'))  # keep the first original, never overwrite it
json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False)
for tl in glob.glob(os.path.join(os.path.dirname(P), 'Timelines', '*', 'draft_content.json')): shutil.copy(P, tl)
print('resynced', proj[:20])
