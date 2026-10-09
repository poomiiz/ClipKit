"""ClipKit - Autosave profile: your own editing style, read from what you changed in your projects.

Reads every clipkit_changes.jsonl in the CapCut drafts folder (written by ClipKit - Autosave) and writes
<output_dir>/autosave/profile.md (to read) and profile.json (for agents), plus presets/my-style.json: the subtitle
look of the project the person edited last, which run_clip.py uses when no --preset is given. Stays on this machine
(presets/my-style.json is git-ignored). The app reruns this once a day by itself.

    python scripts/autosave_profile.py
"""
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "capcut"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import kitconfig  # noqa: E402
import preset_from_capcut  # noqa: E402

MY_STYLE = Path(__file__).resolve().parents[1] / "presets" / "my-style.json"

SKIP = {"capcut_build", "restore"}  # made by the AI, or a version put back: not a choice of yours
MEASURES = {"cards": ("dur_s", "size", "letters"), "cuts": ("dur_s",), "inserts": ("dur_s", "scale"),
            "audio": ("volume",)}
LABEL = {("cards", "dur_s"): "ป้ายค้าง (วิ)", ("cards", "size"): "ขนาดตัวอักษร", ("cards", "letters"): "ความยาวข้อความ (ตัวอักษร)",
         ("cuts", "dur_s"): "ความยาวช็อต (วิ)", ("inserts", "dur_s"): "ภาพแทรกยาว (วิ)", ("inserts", "scale"): "ขนาดภาพแทรก",
         ("audio", "volume"): "ความดังเสียง"}


def build(drafts: Path) -> dict:
    ops, projects, rows, last = Counter(), set(), {"removed": {}, "added": {}}, {}
    for log in drafts.glob("*/clipkit_changes.jsonl"):
        for line in log.read_text(encoding="utf-8").splitlines():
            ch = json.loads(line)
            if ch["op"] in SKIP or "problem" in ch:
                continue
            ops[ch["op"]] += 1
            projects.add(log.parent.name)
            last[log.parent] = max(last.get(log.parent, ""), ch["time"])
            for kind in ("removed", "added"):
                for tbl, rs in ch[kind].items():
                    rows[kind].setdefault(tbl, []).extend(rs)
    for kind in rows.values():
        for r in kind.get("cards", []):
            r["letters"] = len(str(r.get("text", "")).replace(" ", ""))
    med = lambda rs, k: round(statistics.median(v), 2) if (v := [r[k] for r in rs if isinstance(r.get(k), (int, float))]) else None  # noqa: E731
    changed = [{"what": LABEL[(t, k)], "table": t, "measure": k, "before": med(rows["removed"].get(t, []), k),
                "after": med(rows["added"].get(t, []), k)} for t, ks in MEASURES.items() for k in ks]
    added = rows["added"]
    return {"made": time.strftime("%Y-%m-%d %H:%M"), "projects": len(projects), "edits": sum(ops.values()),
            "by_op": ops.most_common(), "changed": [c for c in changed if c["before"] is not None or c["after"] is not None],
            "card_colours": Counter(r.get("color") for r in added.get("cards", [])).most_common(5),
            "card_roles": Counter(r.get("role") for r in added.get("cards", [])).most_common(5),
            "effects": Counter(r.get("name") for r in added.get("effects", [])).most_common(5),
            "last_edited": str(max(last, key=last.get)) if last else None}


def markdown(p: dict) -> str:
    out = [f"# ClipKit - Autosave: สไตล์การตัดต่อของคุณ", "",
           f"จาก {p['edits']} ครั้งที่แก้ ใน {p['projects']} โปรเจกต์ (อัปเดต {p['made']})", "",
           "## สิ่งที่แก้บ่อย", ""] + [f"- {op}: {n} ครั้ง" for op, n in p["by_op"][:10]]
    out += ["", "## ค่าที่คุณเปลี่ยน (ค่ากลาง: ก่อนแก้ → หลังแก้)", "", "| อะไร | ก่อน | หลัง |", "|---|---|---|"]
    out += [f"| {c['what']} | {c['before'] if c['before'] is not None else '-'} | {c['after'] if c['after'] is not None else '-'} |"
            for c in p["changed"]]
    for title, key in (("สีป้ายที่ใส่", "card_colours"), ("ชนิดป้ายที่ใส่", "card_roles"), ("เอฟเฟกต์ที่ใส่", "effects")):
        if p[key]:
            out += ["", f"## {title}", ""] + [f"- {v}: {n}" for v, n in p[key]]
    return "\n".join(out) + "\n"


def write(drafts: Path, out: Path) -> dict:
    prof = build(drafts)
    prof["my_style"] = None
    if prof["last_edited"]:
        try:
            preset = preset_from_capcut.learn(prof["last_edited"])
            MY_STYLE.write_text(json.dumps(preset, ensure_ascii=False, indent=1), encoding="utf-8")
            prof["my_style"] = {"preset": str(MY_STYLE), "from": Path(prof["last_edited"]).name}
        except ValueError as exc:  # the last project has no subtitles yet: the profile says so, my-style stays as it was
            prof["my_style"] = {"not_made": str(exc), "from": Path(prof["last_edited"]).name}
    out.mkdir(parents=True, exist_ok=True)
    (out / "profile.json").write_text(json.dumps(prof, ensure_ascii=False, indent=1), encoding="utf-8")
    md = markdown(prof)
    if prof["my_style"]:
        ms = prof["my_style"]
        md += (f"\n## ค่าเริ่มต้นของคลิปใหม่\n\npresets/my-style.json จากโปรเจกต์ {ms['from']} (แก้ล่าสุด)\n" if "preset" in ms
               else f"\n## ค่าเริ่มต้นของคลิปใหม่\n\nยังทำ my-style ไม่ได้: {ms['not_made']} ({ms['from']})\n")
    (out / "profile.md").write_text(md, encoding="utf-8")
    return prof


def refresh(max_age_h: float = 24) -> dict | None:
    """Remake the profile when it is older than max_age_h (the app calls this every hour); None = still fresh."""
    out = Path(kitconfig.need("output_dir")) / "autosave"
    f = out / "profile.json"
    if f.is_file() and time.time() - f.stat().st_mtime < max_age_h * 3600:
        return None
    return write(Path(kitconfig.need("capcut_drafts")), out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(kitconfig.need("output_dir")) / "autosave"
    prof = write(Path(kitconfig.need("capcut_drafts")), out)
    print(f"{prof['edits']} edits in {prof['projects']} projects -> {out / 'profile.md'}; my-style: {prof['my_style']}")
