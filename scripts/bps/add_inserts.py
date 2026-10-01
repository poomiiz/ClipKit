import sys as _s; from pathlib import Path as _P; _s.path.insert(0, str(_P(__file__).resolve().parents[1] / 'capcut'))
from kitconfig import DRAFTS, STOCK, OLD_BUILDS, FFMPEG, enable_cuda_libs  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Second pass of inserts (2026-09-20): P'Ohm asked for ~14 per episode,
series-1 density. Each entry sits on a pop word that had no picture yet.
Adds to ep_XX.json (06-15) and to the INSERTS list of build_bps3_0X.py (02-05);
originals are copied to *.bak_insert2 first.
"""
import json
import re
import shutil
from pathlib import Path

HERE = Path(__file__).parent

ADD = {
    '06': [(335.0, 2.0, 'futuristic-holographic-ai-agent', 2.0),
           (384.6, 2.0, 'modern-electric-car-displayed', 2.0),
           (387.4, 2.0, 'charging-electric-vehicle', 8.0),
           (392.4, 2.0, 'coin-going-into-piggy', 2.0),
           (395.8, 2.0, 'electric-vehicle-charging-station-parking', 2.0)],
    '07': [(653.3, 1.8, 'futuristic-digital-data-analysis', 2.0),
           (667.7, 2.0, 'excited-team-smiles', 2.0),
           (674.4, 2.2, 'ai-robot-reading-book', 2.0)],
    '08': [(905.9, 2.0, 'close-up-of-stopwatch', 2.0),
           (990.6, 2.0, 'futuristic-digital-hexagon-icons', 2.0),
           (994.3, 2.0, 'dart-hits-bullseye', 2.0),
           (1008.9, 2.0, 'global-network-growth', 2.0),
           (1021.0, 2.0, 'close-up-shot-of-multiple-arrows', 2.0)],
    '09': [(1507.6, 2.0, 'businessman-writes-the-word-risk', 2.0),
           (1532.1, 2.0, 'tired-man-rubbing-eyes', 2.0),
           (1536.0, 1.8, 'global-network-growth', 6.0),
           (1542.0, 1.6, 'diverse-professionals-stack-hands', 2.0)],
    '10': [(1597.3, 2.0, 'beautiful-female-executive-listens', 2.0),
           (1612.1, 2.0, 'people-working-together-in-a-modern', 2.0),
           (1645.8, 2.0, 'friends-conversing-indoors', 2.0),
           (1665.4, 2.0, 'man-meditating-at-desk', 2.0)],
    '11': [(1739.8, 2.0, 'hand-moving-pieces-on-a-chess', 2.0),
           (1765.1, 2.0, 'hand-moving-pieces-on-a-chess', 8.0),
           (1771.3, 2.0, 'diverse-professionals-stack-hands', 2.0),
           (1794.5, 2.0, 'man-meditating-at-desk', 6.0)],
    '12': [(48.7, 2.0, 'close-up-of-website-subscription', 2.0),
           (103.5, 2.0, 'ai-hologram-network', 6.0)],
    '13': [(306.3, 1.8, 'businessman-writes-the-word-risk', 2.0),
           (319.3, 2.0, 'futuristic-holographic-ai-agent', 4.0),
           (322.2, 1.8, 'hand-adjusting-gold-antique-balance', 2.0),
           (331.7, 2.0, 'happy-business-team-celebrating', 2.0),
           (347.9, 1.4, 'excited-team-smiles', 4.0)],
    '14': [(754.4, 1.6, 'time-lapse-of-busy-traffic', 12.0),
           (769.6, 2.0, 'futuristic-holographic-ai-agent', 8.0)],
    '15': [(868.5, 2.0, 'automated-car-assembly-line', 2.0),
           (896.0, 2.0, 'futuristic-digital-ecosystems', 2.0),
           (916.7, 2.0, 'birds-eye-view-of-bangkok', 2.0)],
    '02': [(96.76, 1.4, 'customer-using-smartphone-to-pay', 2.0),
           (111.78, 2.0, 'construction-worker-inspects-wall', 2.0),
           (124.34, 2.0, 'coin-going-into-piggy', 4.0),
           (133.6, 1.8, 'men-unloading-boxes-from-moving-van', 2.0)],
    '03': [(52.22, 1.2, 'woman-works-on-laptop-at-beach', 2.0),
           (71.46, 2.0, 'hands-assemble-brain-puzzle', 2.0),
           (90.4, 2.0, 'loving-family-embracing', 2.0),
           (95.0, 2.0, 'father-and-daughter-playing', 2.0),
           (104.6, 2.0, 'friends-conversing-indoors', 2.0)],
    '04': [(256.6, 2.0, 'loving-family-looking-at-old-photo', 2.0),
           (284.1, 2.0, 'child-talking-to-adult-on-couch', 2.0),
           (304.4, 1.6, 'upset-child-being-disciplined', 5.0),
           (309.9, 2.0, 'woman-and-child-having-a-conversation', 2.0)],
    '05': [(35.0, 2.0, 'asian-young-smart-business-man', 2.0),
           (52.4, 2.0, 'futuristic-digital-server-room', 2.0),
           (73.6, 2.0, 'programmers-typing-code', 2.0),
           (109.7, 2.0, 'animated-globe-with-international', 2.0)],
}

STOCK = Path(STOCK)
for ep, rows in ADD.items():
    for _, _, prefix, _ in rows:          # fail now, not halfway through a build
        assert any(p.name.lower().startswith(prefix.lower()) for p in STOCK.iterdir()), prefix
    spec = HERE / f'ep_{ep}.json'
    if spec.exists():
        shutil.copy2(spec, spec.with_suffix('.json.bak_insert2'))
        s = json.loads(spec.read_text(encoding='utf-8'))
        s['inserts'] = sorted(s['inserts'] + [list(r) for r in rows])
        spec.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding='utf-8')
    else:
        script = HERE / f'build_bps3_{ep}.py'
        shutil.copy2(script, script.with_suffix('.py.bak_insert2'))
        src = script.read_text(encoding='utf-8')
        start = src.index('INSERTS = [')
        end = src.index('\n]', start)
        extra = ''.join(f"\n    ({a}, {n}, find('{p}'), {s0}),  # second pass 2026-09-20" for a, n, p, s0 in rows)
        script.write_text(src[:end] + extra + src[end:], encoding='utf-8')
    print(ep, '+', len(rows))
