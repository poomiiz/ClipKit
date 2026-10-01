# -*- coding: utf-8 -*-
"""Split timeline ASR (char/word timestamps) into subtitle-sized lines at natural pauses.
Breaks on pauses > 0.30s; runs longer than MAX are split at the widest gap between 1.4s and MAX.
usage: python sublines.py words.json out_lines.json [max_len_sec]
"""
import json, sys
W = [w for w in json.load(open(sys.argv[1], encoding='utf-8')) if w[2].strip()]
MAX = float(sys.argv[3]) if len(sys.argv) > 3 else 3.6
runs = []; cur = [W[0]]
for w in W[1:]:
    if w[0] - cur[-1][1] > 0.30: runs.append(cur); cur = [w]
    else: cur.append(w)
runs.append(cur)
lines = []
for r in runs:
    while r[-1][1] - r[0][0] > MAX:
        t0 = r[0][0]
        cands = [i for i in range(1, len(r)) if 1.4 <= r[i][0] - t0 <= MAX]
        if not cands: cands = [i for i in range(1, len(r)) if r[i][0] - t0 <= MAX] or [1]
        i = max(cands, key=lambda i: (r[i][0] - r[i - 1][1], r[i][0]))
        lines.append(r[:i]); r = r[i:]
    lines.append(r)
out = []
for l in lines:
    if out and l[-1][1] - l[0][0] < 0.8 and l[-1][1] - out[-1][0][0] < MAX + 0.8:
        out[-1] += l
    else:
        out.append(l)
res = [[round(l[0][0], 2), round(l[-1][1], 2), ''.join(x[2] for x in l)] for l in out]
json.dump(res, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
for i, (a, b, t) in enumerate(res):
    print(f'{i:2d} {a:6.2f}-{b:6.2f} {t}')
