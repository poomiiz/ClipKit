"""ClipKit - Autosave profile: your own editing style, read from what you changed in your projects.

Reads every clipkit_changes.jsonl in the CapCut drafts folder (written by ClipKit - Autosave) and writes
<output_dir>/autosave/profile.md (to read) and profile.json (for presets and agents). Stays on this machine.

    python scripts/autosave_profile.py
"""
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "capcut"))
import kitconfig  # noqa: E402

SKIP = {"capcut_build", "restore"}  # made by the AI, or a version put back: not a choice of yours
MEASURES = {"cards": ("dur_s", "size", "letters"), "cuts": ("dur_s",), "inserts": ("dur_s", "scale"),
            "audio": ("volume",)}
LABEL = {("cards", "dur_s"): "ป้ายค้าง (วิ)", ("cards", "size"): "ขนาดตัวอักษร", ("cards", "letters"): "ความยาวข้อความ (ตัวอักษร)",
         ("cuts", "dur_s"): "ความยาวช็อต (วิ)", ("inserts", "dur_s"): "ภาพแทรกยาว (วิ)", ("inserts", "scale"): "ขนาดภาพแทรก",
         ("audio", "volume"): "ความดังเสียง"}


def build(drafts: Path) -> dict:
    ops, projects, rows = Counter(), set(), {"removed": {}, "added": {}}
    for log in drafts.glob("*/clipkit_changes.jsonl"):
        for line in log.read_text(encoding="utf-8").splitlines():
            ch = json.loads(line)
            if ch["op"] in SKIP or "problem" in ch:
                continue
            ops[ch["op"]] += 1
            projects.add(log.parent.name)
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
            "effects": Counter(r.get("name") for r in added.get("effects", [])).most_common(5)}


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


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    prof = build(Path(kitconfig.need("capcut_drafts")))
    out = Path(kitconfig.need("output_dir")) / "autosave"
    out.mkdir(parents=True, exist_ok=True)
    (out / "profile.json").write_text(json.dumps(prof, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "profile.md").write_text(markdown(prof), encoding="utf-8")
    print(f"{prof['edits']} edits in {prof['projects']} projects -> {out / 'profile.md'}")
