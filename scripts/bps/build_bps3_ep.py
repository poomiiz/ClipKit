import sys as _s; from pathlib import Path as _P; _s.path.insert(0, str(_P(__file__).resolve().parents[1] / 'capcut'))
from kitconfig import DRAFTS, STOCK, OLD_BUILDS, FFMPEG, enable_cuda_libs  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Build one BPS3 episode from an episode spec (ep_XX.json), using BPS3 01 (the
cut P'Ohm made himself) as the template: same grade, text looks, animations
and SFX pairing. Usage: python build_bps3_ep.py ep_06.json

Recipe behind the numbers: RECIPE_BPS_INSERT_STYLE.md (same folder).
Refuses to run if the target project already exists.
"""
import copy
import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

US = 1_000_000
ROOT = Path(DRAFTS)
candidates = list(ROOT.glob('*Just In Time*'))
assert candidates, f'Template Just In Time not found in {ROOT}'
SRC = candidates[0]
SPEC = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
NEW = ROOT / SPEC['name']
CAM = Path(SPEC['cam'])
DJI = Path(SPEC['dji'])
DJI_OFFSET = SPEC['dji_offset']   # seconds DJI runs behind the main camera (audio cross-correlation)
STOCK = Path(STOCK)


def nid():
    return str(uuid.uuid4()).upper()


def us(t):
    return int(round(t * US))


assert not NEW.exists(), NEW
shutil.copytree(SRC, NEW, ignore=shutil.ignore_patterns('*.bak*', 'template-2.tmp', 'draft_cover.jpg', '*.jpg'))
c = json.loads((NEW / 'draft_content.json').read_text(encoding='utf-8'))
idx = {m['id']: (k, m) for k, v in c['materials'].items() if isinstance(v, list)
       for m in v if isinstance(m, dict) and 'id' in m}
T = c['tracks']


def seg_text(s):
    return json.loads(idx[s['material_id']][1]['content'])['text']


# identify the template tracks by what they hold, not by position alone
assert T[0]['type'] == 'video' and len(T[0]['segments']) == 20
assert T[1]['type'] == 'video' and 'DJI' in idx[T[1]['segments'][0]['material_id']][1]['path']
assert T[2]['type'] == 'video' and 'stock' in idx[T[2]['segments'][0]['material_id']][1]['path']
assert T[3]['type'] == 'effect'
assert seg_text(T[4]['segments'][3]) == 'ผู้รับเหมา' and seg_text(T[5]['segments'][0]) == 'ถูกกดดัน'
assert seg_text(T[8]['segments'][0]) in ('20 ปีในวงการ', 'พฤติกรรมลูกค้า')
assert any(seg_text(T[9]['segments'][0]).startswith(p) for p in ('จากผู้รับเหมา', 'ที่เปลี่ยนไป'))
assert T[12]['type'] == 'audio' and T[13]['type'] == 'audio'

tpl = {
    'main': copy.deepcopy(T[0]['segments'][2]),
    'dji': copy.deepcopy(T[1]['segments'][1]),
    'ins': copy.deepcopy(T[2]['segments'][0]),
    'fx': {idx[s['material_id']][1]['name']: copy.deepcopy(s) for s in T[3]['segments']},
    'white': copy.deepcopy(T[4]['segments'][3]),
    'navy': copy.deepcopy(T[5]['segments'][0]),
    'type_sfx': copy.deepcopy(T[12]['segments'][1]),
    'click_sfx': copy.deepcopy(T[12]['segments'][3]),
}


def clone(seg, clone_material=True):
    s = copy.deepcopy(seg)
    s['id'] = nid()
    if clone_material:
        k, m = idx[s['material_id']]
        m2 = copy.deepcopy(m)
        m2['id'] = nid()
        if 'local_material_id' in m2:
            m2['local_material_id'] = nid()
        c['materials'][k].append(m2)
        idx[m2['id']] = (k, m2)
        s['material_id'] = m2['id']
    refs = []
    for r in s.get('extra_material_refs', []):
        if r not in idx:
            continue
        k, m = idx[r]
        m2 = copy.deepcopy(m)
        m2['id'] = nid()
        c['materials'][k].append(m2)
        idx[m2['id']] = (k, m2)
        refs.append(m2['id'])
    s['extra_material_refs'] = refs
    return s


# ── 1. cut list: hook + body, pauses out ─────────────────────────────
# the hook may be one range or several short ones joined (to skip a pause inside it)
HOOKS = [tuple(h) for h in SPEC['hook']] if isinstance(SPEC['hook'][0], list) else [tuple(SPEC['hook'])]
BODY = tuple(SPEC['body'])
# Pauses from silencedetect at -24dB, kept only where they fall between words
# (checked against Whisper's per-character timings); the ones inside a word
# (เบิก, ดีล, และ, ส่ง) were dropped because cutting there clips the word.
PAUSES = [tuple(p) for p in SPEC['cuts']]   # pauses between words and whole sentences dropped
keep, at = [], BODY[0]
for a, b in PAUSES:
    a, b = a + 0.08, b - 0.08          # leave a breath either side
    if a > at:
        keep.append([at, a])
    at = max(at, b)
keep.append([at, BODY[1]])
pieces = []
for a, b in keep:                       # split long takes so the camera can move
    while b - a > 2.8:
        cut = a + (b - a) / 2 if b - a < 5.6 else a + 2.2
        pieces.append([a, cut])
        a = cut
    pieces.append([a, b])
pieces = [p for p in pieces if p[1] - p[0] >= 0.25]

timeline = []                            # (tl_start, src_a, src_b, look)
looks = ['wide', 'punch', 'wide', 'dji']
cursor = 0.0
for h0, h1 in HOOKS:
    timeline.append((cursor, h0, h1, 'punch'))
    cursor += h1 - h0
NH = len(HOOKS)
for i, (a, b) in enumerate(pieces):
    timeline.append((cursor, a, b, looks[i % 4]))
    cursor += b - a
TOTAL = cursor


def tl(src):
    """Timeline time of a body source time."""
    for t0, a, b, _ in timeline[NH:]:
        if a <= src < b:
            return t0 + (src - a)
    return min(timeline[NH:], key=lambda x: abs(x[1] - src))[0]


def probe(p):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                        'stream=width,height:format=duration', '-of', 'json', str(p)],
                       capture_output=True, text=True, encoding='utf-8')
    j = json.loads(r.stdout)
    st = j['streams'][0]
    return st['width'], st['height'], float(j['format']['duration'])


CAM_LEN = probe(CAM)[2]
DJI_LEN = probe(DJI)[2]


LOOK = {'wide': (1.25, 0.0, -0.21), 'punch': (1.62, 0.06, -0.34)}
main, dji = [], []
for t0, a, b, look in timeline:
    s = clone(tpl['main'])
    idx[s['material_id']][1].update({'path': str(CAM), 'material_name': CAM.name, 'duration': us(CAM_LEN)})
    s['source_timerange'] = {'start': us(a), 'duration': us(b - a)}
    s['target_timerange'] = {'start': us(t0), 'duration': us(b - a)}
    sc, x, y = LOOK['wide' if look == 'dji' else look]
    s['clip']['scale'] = {'x': sc, 'y': sc}
    s['clip']['transform'] = {'x': x, 'y': y}
    main.append(s)
    if look == 'dji':
        d = clone(tpl['dji'])
        idx[d['material_id']][1].update({'path': str(DJI), 'material_name': DJI.name, 'duration': us(DJI_LEN)})
        d['source_timerange'] = {'start': us(a + DJI_OFFSET), 'duration': us(b - a)}
        d['target_timerange'] = {'start': us(t0), 'duration': us(b - a)}
        dji.append(d)


# ── 2. inserts, each with the grain/leak effect over it ─────────────
def find(prefix):
    return next(p for p in sorted(STOCK.iterdir()) if p.name.lower().startswith(prefix.lower()))


INSERTS = [(a, n, Path(f) if ':' in f else find(f), s0) for a, n, f, s0 in SPEC['inserts']]


FX = ['สปาร์เคิลเกรน', 'รั่วซึม 2', 'วินเทจเรคคอร์ดดิ้ง', 'เสียงรบกวน 2', 'DV ย้อนยุค 3', 'ฟัซซี่เมมโมรี่', 'รังสีโบเก้']
ins, fx = [], []
for i, (at_src, length, path, s0) in enumerate(INSERTS):
    w, h, dur = probe(path)
    t0 = tl(at_src)
    later = [tl(x[0]) for x in INSERTS if tl(x[0]) > t0 + 0.01]
    length = min(length, TOTAL - t0 - 0.1, dur - s0,
                 (min(later) - t0 - 0.05) if later else 99)   # never overlap the next insert
    s = clone(tpl['ins'])
    m = idx[s['material_id']][1]
    m.update({'path': str(path), 'material_name': path.name, 'width': w, 'height': h, 'duration': us(dur)})
    s['source_timerange'] = {'start': us(s0), 'duration': us(length)}
    s['target_timerange'] = {'start': us(t0), 'duration': us(length)}
    # a landscape clip is scaled up until it fills the 9:16 frame (BPS3 01 uses 3.16)
    sc = round((w / h) / (1080 / 1920), 2) if w > h else 1.0
    s['clip']['scale'] = {'x': sc, 'y': sc}
    s['clip']['transform'] = {'x': 0.0, 'y': 0.0}
    ins.append(s)
    e = clone(tpl['fx'][FX[i % len(FX)]])
    e['target_timerange'] = {'start': us(t0), 'duration': us(length)}
    fx.append(e)

# ── 3. keyword pops + paired SFX ────────────────────────────────────
POPS = [tuple(p) for p in SPEC['pops']]


def set_text(seg, text):
    m = idx[seg['material_id']][1]
    b = json.loads(m['content'])
    b['text'] = text
    for st in b['styles']:
        st['range'] = [0, len(text)]
    m['content'] = json.dumps(b, ensure_ascii=False)


rows = {'w': [], 'n': []}
sfx = []
starts = {r: sorted(tl(s) for s, rr, _ in POPS if rr == r) for r in 'wn'}
for src_t, row, text in POPS:
    t0 = tl(src_t)
    nxt = [x for x in starts[row] if x > t0 + 0.01]
    end = min(t0 + 2.4, (nxt[0] - 0.05) if nxt else TOTAL - 0.05, TOTAL - 0.05)
    end = max(end, t0 + 0.8)
    if nxt:
        end = min(end, nxt[0] - 0.05)       # a close follow-up word wins over the 0.8s floor
    s = clone(tpl['white' if row == 'w' else 'navy'])
    s['target_timerange'] = {'start': us(t0), 'duration': us(end - t0)}
    s['clip']['transform']['x'] = 0.0
    set_text(s, text)
    rows[row].append(s)
    a = clone(tpl['type_sfx' if row == 'w' else 'click_sfx'])
    a['target_timerange']['start'] = us(t0)
    sfx.append(a)

# ── 4. title over the hook, still first frame for the thumbnail ─────
FRAME = 33333
red, white = T[8]['segments'][0], T[9]['segments'][0]
set_text(red, SPEC['title'][0])
set_text(white, SPEC['title'][1])
hook_len = sum(h1 - h0 for h0, h1 in HOOKS)
red['target_timerange'] = {'start': FRAME, 'duration': us(hook_len) - FRAME}
white['target_timerange'] = {'start': us(0.3), 'duration': us(hook_len - 0.3)}
covers = []
for seg in (red, white):
    cov = clone(seg)
    for r in cov['extra_material_refs']:
        k, m = idx[r]
        if k == 'material_animations':
            m['animations'] = []
    cov['target_timerange'] = {'start': 0, 'duration': FRAME}
    covers.append(cov)
title_sfx = [clone(tpl['click_sfx']), clone(tpl['type_sfx'])]
title_sfx[0]['target_timerange']['start'] = 0
title_sfx[0]['volume'] = 0.3
title_sfx[1]['target_timerange']['start'] = us(0.3)

# ── 5. assemble ─────────────────────────────────────────────────────
T[0]['segments'] = main
T[1]['segments'] = dji
T[2]['segments'] = ins
T[3]['segments'] = fx
T[4]['segments'] = sorted(rows['w'], key=lambda s: s['target_timerange']['start'])
T[5]['segments'] = sorted(rows['n'], key=lambda s: s['target_timerange']['start'])
T[12]['segments'] = sorted(title_sfx + sfx, key=lambda s: s['target_timerange']['start'])
# one cover per track: CapCut does not allow two clips to overlap on a track
cover_tracks = [{'type': 'text', 'attribute': 0, 'flag': 0, 'is_default_name': True, 'id': nid(),
                 'segments': [cv]} for cv in covers]

# BGM music track from template
bgm_track = []
if len(T) > 13 and T[13]['type'] == 'audio' and len(T[13]['segments']) > 0:
    bgm = clone(T[13]['segments'][0])
    bgm['target_timerange'] = {'start': 0, 'duration': us(TOTAL)}
    bgm['source_timerange'] = {'start': 0, 'duration': us(TOTAL)}
    bgm['volume'] = 0.103
    bgm_track = [{'type': 'audio', 'attribute': 0, 'flag': 0, 'is_default_name': True, 'id': nid(),
                  'segments': [bgm]}]

drop = {id(T[i]) for i in (6, 7, 10, 11, 13)}   # extra texts, nested hook, old cover, old music
c['tracks'] = [t for t in T if id(t) not in drop] + cover_tracks + bgm_track
# Clear any stabilization or quality enhance on all video materials
for v in c.get('materials', {}).get('videos', []):
    if 'stable' in v:
        v['stable'] = {'stable_level': 0, 'matrix_path': '', 'time_range': {'start': 0, 'duration': 0}}
    if 'video_algorithm' in v and v['video_algorithm']:
        va = v['video_algorithm']
        va['algorithms'] = []
        va['quality_enhance'] = None
        va['super_resolution'] = None
        va['noise_reduction'] = None
        va['path'] = ''

c['duration'] = us(TOTAL)
c['id'] = nid()
(NEW / 'draft_content.json').write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding='utf-8')

meta_p = NEW / 'draft_meta_info.json'
meta = json.loads(meta_p.read_text(encoding='utf-8'))
meta.update({'draft_name': NEW.name, 'draft_fold_path': NEW.as_posix(), 'draft_root_path': ROOT.as_posix(),
             'draft_id': nid(), 'tm_duration': us(TOTAL), 'tm_draft_create': int(time.time() * US),
             'tm_draft_modified': int(time.time() * US), 'draft_cover': ''})
meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')

# newer CapCut opens Timelines/<id>/draft_content.json, and the clone still carried
# BPS3 01's timeline there; give this draft its own (2026-09-21)
from fix_timeline_ids import fix as _fix_tl, check as _check_tl  # noqa: E402
_fix_tl(NEW)
assert not _check_tl(NEW), _check_tl(NEW)

print('duration', round(TOTAL, 2), '| main cuts', len(main), '| dji', len(dji), '| inserts', len(ins),
      '| pops', len(POPS), '| sfx', len(T[12]['segments']))
cover = sum(s['target_timerange']['duration'] for s in ins + dji) / US
print('insert+cam2 cover %', round(cover / TOTAL * 100),
      '| pauses removed', round(BODY[1] - BODY[0] - (TOTAL - hook_len), 2))
