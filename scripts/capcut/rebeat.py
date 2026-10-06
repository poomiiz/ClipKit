from kitconfig import DRAFTS, ROOT_META, font_file  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Rebuild white/orange card timing as short beats locked to spoken keywords (Nina 01 style).

usage: python rebeat.py "<project>" words.json beats.json
beats.json = [[white_text, white_key, orange_text, orange_key], ...]
  *_key = a few characters as the ASR heard them; the card starts when that key is spoken.
  white shows from its key until the next beat; orange pops at its key and ends with the white.
"""
import json, os, sys, glob, shutil, difflib, copy, uuid

proj, wfile, bfile = sys.argv[1], sys.argv[2], sys.argv[3]
P = os.path.join(DRAFTS, proj, 'draft_content.json')
d = json.load(open(P, encoding='utf-8')); M = d['materials']
W = json.load(open(wfile, encoding='utf-8'))
beats = json.load(open(bfile, encoding='utf-8'))
tex = {t['id']: t for t in M['texts']}
def nid(): return str(uuid.uuid4()).upper()
def norm(s): return ''.join(ch for ch in s.lower() if ch.isalnum())

stream = ''; times = []
for a, b, t in W:
    for ch in norm(t): stream += ch; times.append(a)

def find(key, after):
    if key.startswith('@'): return float(key[1:])
    key = norm(key)
    lo = next((i for i, t in enumerate(times) if t >= after - 0.05), len(times))
    best = None
    for i in range(lo, len(stream)):
        r = difflib.SequenceMatcher(None, stream[i:i + len(key)], key).ratio()
        if r >= 0.75: return times[i]
        if best is None or r > best[0]: best = (r, i)
        if times[i] - after > 25: break
    raise SystemExit(f'key not found: {key!r} after {after:.2f} (best {best[0]:.2f} at {times[best[1]]:.2f})')

dur = d['duration'] / 1e6
plan = []; t = 0.0
for bt in beats:
    w, wk, o, ok = bt[:4]
    ws = find(wk, t)
    os_ = find(ok, ws) if o else None
    plan.append([ws, w, os_, o, bt[4] if len(bt) > 4 else None]); t = ws + 0.3
for i, p in enumerate(plan):
    p.append(plan[i + 1][0] - 0.05 if i + 1 < len(plan) else dur)
# plan rows: [ws, white, os, orange, english, end]

def size_of(s): return json.loads(tex[s['material_id']]['content'])['styles'][0]['size']
cards = [t for t in d['tracks'] if t['type'] == 'text' and t['segments'] and not (len(t['segments']) == 1 and t['segments'][0]['target_timerange']['start'] < 6e6 and t['segments'][0]['target_timerange']['duration'] < 10e6 and t['segments'][0]['target_timerange']['start'] + t['segments'][0]['target_timerange']['duration'] < 6e6)]
eng = ([t for t in cards if all(size_of(s) <= 10 for s in t['segments'])] or [None])[0]
rest = [t for t in cards if t is not eng]
white = min(rest, key=lambda t: sum(size_of(s) for s in t['segments']) / len(t['segments']))
orange = [t for t in rest if t is not white][0]
tmpl_w = copy.deepcopy(white['segments'][0]); tmpl_o = copy.deepcopy(orange['segments'][0])
size_w = size_of(tmpl_w); size_o = max(size_of(s) for s in orange['segments'])

def mk(tmpl, text, st, en, size):
    s = copy.deepcopy(tmpl); s['id'] = nid()
    m = copy.deepcopy(tex[tmpl['material_id']]); m['id'] = nid()
    c = json.loads(m['content']); c['text'] = text
    for x in c['styles']: x['range'] = [0, len(text)]; x['size'] = size
    m['content'] = json.dumps(c, ensure_ascii=False); M['texts'].append(m); tex[m['id']] = m
    s['material_id'] = m['id']
    s['target_timerange'] = {'start': int(st * 1e6), 'duration': int((en - st) * 1e6)}
    return s

COMB = set(chr(c) for c in [0x0E31] + list(range(0x0E34, 0x0E3B)) + list(range(0x0E47, 0x0E4F)))
def vis(s): return sum(1 for ch in s if ch not in COMB)
white['segments'] = []; orange['segments'] = []
tmpl_e = copy.deepcopy(eng['segments'][0]) if eng else None; size_e = size_of(tmpl_e) if eng else 0
if eng and any(p[4] for p in plan): eng['segments'] = []
for ws, w, os_, o, e_txt, en in plan:
    if e_txt and eng: eng['segments'].append(mk(tmpl_e, e_txt, ws, en, size_e))
    white['segments'].append(mk(tmpl_w, w, ws, en, size_w))
    if o:
        sz = size_o if vis(o) <= 21 else max(28, int(size_o * 21 / vis(o)))
        orange['segments'].append(mk(tmpl_o, o, min(max(os_ - 0.05, ws + 0.25), en - 0.6), en, sz))

# clicks: one per orange pop
auds = {a['id']: a for a in M['audios']}
for t in d['tracks']:
    if t['type'] != 'audio' or not t['segments']: continue
    if 'mouse' not in auds.get(t['segments'][0]['material_id'], {}).get('name', '').lower(): continue
    tm = copy.deepcopy(t['segments'][0]); t['segments'] = []
    for s in orange['segments']:
        c = copy.deepcopy(tm); c['id'] = nid(); c['target_timerange'] = {'start': s['target_timerange']['start'], 'duration': tm['target_timerange']['duration']}
        if c['target_timerange']['start'] + c['target_timerange']['duration'] <= d['duration']: t['segments'].append(c)

used = {s['material_id'] for t in d['tracks'] for s in t['segments']}
M['texts'] = [m for m in M['texts'] if m['id'] in used]
for t in d['tracks']:
    prev = -1
    for s in sorted(t['segments'], key=lambda s: s['target_timerange']['start']):
        assert s['target_timerange']['start'] >= prev - 1000, ('overlap', t['type'], s['target_timerange']['start'] / 1e6)
        prev = s['target_timerange']['start'] + s['target_timerange']['duration']
os.path.exists(P.replace('.json', '.before_rebeat.json')) or shutil.copy(P, P.replace('.json', '.before_rebeat.json'))  # keep the first original, never overwrite it
json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False)
for tl in glob.glob(os.path.join(os.path.dirname(P), 'Timelines', '*', 'draft_content.json')): shutil.copy(P, tl)
for ws, w, os_, o, e_txt, en in plan:
    print(f'{ws:6.2f}-{en:6.2f} W {w:24s} | O {(os_ or 0):6.2f} {o}')
print('beats', len(plan))
