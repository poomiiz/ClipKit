from kitconfig import DRAFTS, ROOT_META, font_file  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Place ORIGINAL (uncropped) stock clips as inserts, scaled to fill the 9:16 height so the sides overflow
(the user repositions in CapCut). Replaces all existing bro_* inserts when --replace is given.
usage: python addraw.py "<project>" inserts.json [--replace]
inserts.json = [["<stock_video>/file.mov", src_start, tl_start, tl_end], ...]"""
import json, os, sys, glob, shutil, copy, uuid, subprocess
P = os.path.join(DRAFTS, sys.argv[1], 'draft_content.json')
d = json.load(open(P, encoding='utf-8')); M = d['materials']; ADD = json.load(open(sys.argv[2], encoding='utf-8'))
V = {v['id']: v for v in M['videos']}
def nid(): return str(uuid.uuid4()).upper()
isins = lambda s: s['material_id'] in V and ('bro_' in V[s['material_id']]['path'] or '/stock/' in V[s['material_id']]['path'].replace(chr(92), '/'))
tr = next((t for t in d['tracks'][1:] if t['type'] == 'video' and any(isins(s) for s in t['segments'])), None)
if tr is None:  # no insert track: import one (track + template segment) from Nina 08
    base = DRAFTS
    ref = json.load(open(os.path.join(base, [x for x in os.listdir(base) if x.startswith('Nina 08')][0], 'draft_content.json'), encoding='utf-8')); RM = ref['materials']
    RV = {v['id']: v for v in RM['videos']}
    rt = next(t for t in ref['tracks'][1:] if t['type'] == 'video' and any('bro_' in RV.get(x['material_id'], {}).get('path', '') for x in t['segments']))
    rs = next(x for x in rt['segments'] if 'bro_' in RV[x['material_id']]['path'])
    def rclone(r):
        for k, v in RM.items():
            if isinstance(v, list):
                o = next((x for x in v if isinstance(x, dict) and x.get('id') == r), None)
                if o: c = copy.deepcopy(o); c['id'] = nid(); M.setdefault(k, []).append(c); return c['id']
    tr = copy.deepcopy(rt); tr['id'] = nid(); rs = copy.deepcopy(rs); rs['id'] = nid()
    rs['material_id'] = rclone(rs['material_id']); rs['extra_material_refs'] = [x for x in (rclone(r) for r in rs['extra_material_refs']) if x]
    V[rs['material_id']] = next(v for v in M['videos'] if v['id'] == rs['material_id'])
    rs['target_timerange'] = {'start': 0, 'duration': 1}; tr['segments'] = [rs]; d['tracks'].insert(1, tr)
tmpl = copy.deepcopy(next(s for s in tr['segments'] if isins(s)))
tr['segments'] = [x for x in tr['segments'] if x['target_timerange']['duration'] != 1]
if '--replace' in sys.argv: tr['segments'] = [s for s in tr['segments'] if not isins(s)]
def clone_ref(r):
    for k, v in M.items():
        if isinstance(v, list):
            o = next((x for x in v if isinstance(x, dict) and x.get('id') == r), None)
            if o: c = copy.deepcopy(o); c['id'] = nid(); v.append(c); return c['id']
for path, ss, a, b in ADD:
    out = subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height:stream_side_data=rotation:format=duration', '-of', 'json', path])
    info = json.loads(out); st = info['streams'][0]; w, h = st['width'], st['height']
    rot = any(abs(x.get('rotation', 0)) == 90 for x in st.get('side_data_list', []))
    if rot: w, h = h, w
    dur = int(float(info['format']['duration']) * 1e6)
    m = copy.deepcopy(V[tmpl['material_id']]); m['id'] = nid(); m['path'] = path.replace(chr(92), '/'); m['material_name'] = os.path.basename(path)
    m['width'], m['height'], m['duration'] = w, h, dur
    M['videos'].append(m)
    s = copy.deepcopy(tmpl); s['id'] = nid(); s['material_id'] = m['id']
    s['extra_material_refs'] = [x for x in (clone_ref(r) for r in tmpl['extra_material_refs']) if x]
    fit_h = 1080 * h / w if w / h > 1080 / 1920 else 1920
    sc = max(1.0, 1920 / fit_h) * 1.0
    s['clip']['scale'] = {'x': sc, 'y': sc}; s['clip']['transform'] = {'x': 0.0, 'y': 0.0}
    du = min(int((b - a) * 1e6), dur - int(ss * 1e6))
    s['target_timerange'] = {'start': int(a * 1e6), 'duration': du}; s['source_timerange'] = {'start': int(ss * 1e6), 'duration': du}
    tr['segments'].append(s)
tr['segments'].sort(key=lambda s: s['target_timerange']['start']); prev = -1
for s in tr['segments']:
    assert s['target_timerange']['start'] >= prev - 1000, ('overlap', s['target_timerange']['start'] / 1e6)
    prev = s['target_timerange']['start'] + s['target_timerange']['duration']
assert prev <= d['duration'] + 50000
os.path.exists(P.replace('.json', '.before_raw.json')) or shutil.copy(P, P.replace('.json', '.before_raw.json'))  # keep the first original, never overwrite it
json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False)
for tl in glob.glob(os.path.join(os.path.dirname(P), 'Timelines', '*', 'draft_content.json')): shutil.copy(P, tl)
print('inserts now', len(tr['segments']))
