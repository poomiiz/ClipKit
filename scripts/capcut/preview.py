from kitconfig import DRAFTS, ROOT_META, font_file  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Render a low-res proxy of a CapCut draft (main cuts + b-roll + full-frame PNG overlays + cards)
so pacing, cards and inserts can be checked without opening CapCut.
usage: python preview.py "<project folder name>" out.mp4
"""
import json, os, sys, subprocess, tempfile

proj, out = sys.argv[1], sys.argv[2]
d = json.load(open(os.path.join(DRAFTS, proj, 'draft_content.json'), encoding='utf-8'))
M = d['materials']
vids = {v['id']: v for v in M['videos']}
tex = {t['id']: t for t in M['texts']}
W, H = 540, 960
FONT = font_file().replace('\\', '/').replace(':', '\\:', 1)
tmp = tempfile.mkdtemp()

vt = [t for t in d['tracks'] if t['type'] == 'video']
main = vt[0]['segments']
src = vids[main[0]['material_id']]['path']
parts = []
for i, s in enumerate(main):
    a = s['source_timerange']['start'] / 1e6; du = s['source_timerange']['duration'] / 1e6
    p = os.path.join(tmp, f'm{i:03d}.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{a:.3f}', '-t', f'{du:.3f}', '-i', src,
                    '-vf', f'scale={W}:{H},fps=30,format=yuv420p', '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
                    '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-y', p], check=True)
    parts.append(p)
lst = os.path.join(tmp, 'l.txt')
open(lst, 'w').write(''.join(f"file '{p}'\n" for p in parts))
base = os.path.join(tmp, 'base.mp4')
subprocess.run(['ffmpeg', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', '-y', base], check=True)

inputs = ['-i', base]; fc = []; last = '0:v'; k = 1
for t in vt[1:]:
    for s in t['segments']:
        m = vids[s['material_id']]
        if 'IMG_51' in m['path']: continue
        st = s['target_timerange']['start'] / 1e6; du = s['target_timerange']['duration'] / 1e6
        if m['path'].lower().endswith('.png') and m.get('width') == 1080 and m.get('height') == 1920:
            inputs += ['-loop', '1', '-t', f'{st + du:.3f}', '-i', m['path']]
        elif m['path'].lower().endswith(('.mp4', '.mov')):
            inputs += ['-itsoffset', f'{st:.3f}', '-t', f'{du:.3f}', '-i', m['path']]
        else:
            continue
        fc.append(f"[{k}:v]scale={W}:{H},setpts=PTS[b{k}];[{last}][b{k}]overlay=eof_action=pass:enable='between(t,{st:.3f},{st + du:.3f})'[v{k}]")
        last = f'v{k}'; k += 1

def esc(s): return s.replace('\\', '\\\\').replace("'", "\u2019").replace(':', '\\:').replace('%', '\\%')
for t in d['tracks']:
    if t['type'] != 'text': continue
    for s in t['segments']:
        c = json.loads(tex[s['material_id']]['content'])
        size = c['styles'][0]['size']; y = s['clip']['transform']['y']
        st = s['target_timerange']['start'] / 1e6; en = st + s['target_timerange']['duration'] / 1e6
        col = c['styles'][0]['fill']['content']['solid']['color']
        hexc = '#%02x%02x%02x' % tuple(int(x * 255) for x in col)
        fs = max(12, int(size * 1.35))
        lines = c['text'].split('\n')
        cy = int(H / 2 - y * H / 2)
        for li, line in enumerate(lines):
            py = cy + int((li - (len(lines) - 1) / 2) * fs * 1.15)
            fc.append(f"[{last}]drawtext=fontfile='{FONT}':text='{esc(line)}':fontsize={fs}:fontcolor={hexc}:borderw=2:bordercolor=black:"
                      f"x=(w-text_w)/2:y={py}-text_h/2:enable='between(t,{st:.3f},{en:.3f})'[v{k}]")
            last = f'v{k}'; k += 1
fcf = os.path.join(tmp, 'fc.txt'); open(fcf, 'w', encoding='utf-8').write(';'.join(fc))
subprocess.run(['ffmpeg', '-v', 'error'] + inputs + ['-filter_complex_script', fcf, '-map', f'[{last}]', '-map', '0:a',
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26', '-c:a', 'aac', '-t', f"{d['duration'] / 1e6:.3f}", '-y', out], check=True)
print('preview', out)
