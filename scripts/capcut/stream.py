from kitconfig import DRAFTS, ROOT_META, font_file  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Print an ASR words json as timed lines, plus the current cards of a project for side-by-side editing.
usage: python stream.py words.json ["<project>"]
"""
import json, os, sys
W = json.load(open(sys.argv[1], encoding='utf-8'))
line = ''; t0 = None
for a, b, t in W:
    if t0 is None: t0 = a
    line += t
    if len(line) >= 30: print(f'{t0:6.2f} {line}'); line = ''; t0 = None
if line: print(f'{t0:6.2f} {line}')
if len(sys.argv) > 2:
    d = json.load(open(os.path.join(DRAFTS, sys.argv[2], 'draft_content.json'), encoding='utf-8'))
    tex = {t['id']: t for t in d['materials']['texts']}
    rows = []
    for t in d['tracks']:
        if t['type'] != 'text' or len(t['segments']) <= 5: continue
        for s in t['segments']:
            c = json.loads(tex[s['material_id']]['content'])
            rows.append((s['target_timerange']['start'] / 1e6, c['styles'][0]['size'], c['text'].replace('\n', ' ')))
    print('---- cards')
    for a, sz, x in sorted(rows):
        print(f'{a:6.2f} sz{sz:<3} {x[:70]}')
