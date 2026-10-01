import sys as _s; from pathlib import Path as _P; _s.path.insert(0, str(_P(__file__).resolve().parents[1] / 'capcut'))
from kitconfig import DRAFTS, STOCK, OLD_BUILDS, FFMPEG, enable_cuda_libs  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Make a cloned CapCut draft point at its own timeline.

The builders copy the whole BPS3 01 folder, and newer CapCut keeps the real
timeline in Timelines/<id>/draft_content.json, listed in Timelines/project.json
and timeline_layout.json. The copies kept BPS3 01's timeline folder and id
(62D812C8...), so every clone claimed to be 01's timeline while its root
draft_content.json said something else, and CapCut could not open them
(P'Ohm, 2026-09-21).

A working draft has one id everywhere: root draft_content.json "id",
draft_meta_info.json "draft_id", the single folder under Timelines/, project.json
id/main_timeline_id/timelines[0].id, and timeline_layout.json timelineIds.
The root draft_content.json is what the builder wrote and verify_episode.py
checked, so it is the source of truth here.

Usage: python fix_timeline_ids.py "<draft folder name>" [...]
Old Timelines/, project.json and timeline_layout.json go to
<capcut_old_builds>/timeline_fix/<draft>/ first.
"""
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(DRAFTS)
candidates = list(ROOT.glob('*Just In Time*'))
assert candidates, f'Template folder Just In Time not found in {ROOT}'
tl_subdirs = [d for d in (candidates[0] / 'Timelines').iterdir() if d.is_dir()]
assert tl_subdirs, f'No timeline subdir in {candidates[0]}'
TEMPLATE_TL = tl_subdirs[0]
BACKUP = Path(OLD_BUILDS) / 'timeline_fix'
AUX = ['attachment', 'attachment_editing.json', 'attachment_pc_common.json', 'common_attachment', 'draft.extra']


def fix(folder: Path) -> str:
    content = json.loads((folder / 'draft_content.json').read_text(encoding='utf-8'))
    tid = content['id']
    back = BACKUP / folder.name / time.strftime('%Y%m%d_%H%M%S')
    back.mkdir(parents=True)
    for name in ('Timelines', 'timeline_layout.json', 'draft_meta_info.json'):
        src = folder / name
        if src.is_dir():
            shutil.copytree(src, back / name)
        elif src.exists():
            shutil.copy2(src, back / name)

    tl_root = folder / 'Timelines'
    shutil.rmtree(tl_root, ignore_errors=True)
    tl = tl_root / tid
    tl.mkdir(parents=True)
    for name in AUX:
        src = TEMPLATE_TL / name
        if src.is_dir():
            shutil.copytree(src, tl / name)
        elif src.exists():
            shutil.copy2(src, tl / name)
    shutil.copy2(folder / 'draft_content.json', tl / 'draft_content.json')

    now = int(time.time() * 1_000_000)
    project = {'config': {'color_space': 0, 'hdr_vivid': False, 'mixed_track_mode_on': False,
                          'render_index_track_mode_on': True, 'use_float_render': False},
               'create_time': now, 'id': tid, 'main_timeline_id': tid,
               'timelines': [{'create_time': now, 'id': tid, 'is_marked_delete': False,
                              'name': 'ไทม์ไลน์ 01', 'update_time': now}],
               'update_time': now, 'version': 0}
    (tl_root / 'project.json').write_text(json.dumps(project, ensure_ascii=False), encoding='utf-8')
    layout = {'dockItems': [{'dockIndex': 0, 'ratio': 1, 'timelineIds': [tid], 'timelineNames': ['ไทม์ไลน์ 01']}],
              'layoutOrientation': 1}
    (folder / 'timeline_layout.json').write_text(json.dumps(layout, ensure_ascii=False), encoding='utf-8')

    meta_p = folder / 'draft_meta_info.json'
    meta = json.loads(meta_p.read_text(encoding='utf-8'))
    meta['draft_id'] = tid
    meta['tm_draft_modified'] = now
    meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    return tid


def check(folder: Path) -> list[str]:
    """Every place that names the timeline must agree; returns the mismatches."""
    tid = json.loads((folder / 'draft_content.json').read_text(encoding='utf-8'))['id']
    bad = []
    meta = json.loads((folder / 'draft_meta_info.json').read_text(encoding='utf-8'))
    if meta['draft_id'] != tid:
        bad.append('meta draft_id')
    dirs = [p.name for p in (folder / 'Timelines').iterdir() if p.is_dir()]
    if dirs != [tid]:
        bad.append(f'Timelines dirs {dirs}')
    elif json.loads((folder / 'Timelines' / tid / 'draft_content.json').read_text(encoding='utf-8'))['id'] != tid:
        bad.append('timeline content id')
    proj = json.loads((folder / 'Timelines' / 'project.json').read_text(encoding='utf-8'))
    if {proj['id'], proj['main_timeline_id'], *(t['id'] for t in proj['timelines'])} != {tid}:
        bad.append('project.json')
    lay = json.loads((folder / 'timeline_layout.json').read_text(encoding='utf-8'))
    if [i for d in lay['dockItems'] for i in d['timelineIds']] != [tid]:
        bad.append('timeline_layout')
    return bad


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    for name in sys.argv[1:]:
        folder = ROOT / name
        tid = fix(folder)
        print(name, tid, 'mismatches:', check(folder) or 'none')
