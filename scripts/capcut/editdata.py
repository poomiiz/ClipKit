"""Edit-data warehouse: pull every editing decision out of CapCut drafts a person approved, into one SQLite file,
then write Obsidian notes from it (one per clip, one per technique).

Only drafts listed in <edit_data>/approved.json are read. Paths come from config.json: edit_data, capcut_drafts,
obsidian_notes. Generated notes are overwritten on every run - never hand-edit them.

    python scripts/capcut/editdata.py extract     # approved drafts -> <edit_data>/edits.sqlite
                                                  # (with each draft's clipkit_changes.jsonl: every edit ClipKit wrote)
    python scripts/capcut/editdata.py notes       # sqlite -> Obsidian notes
"""
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import kitconfig

if sys.stdout:  # pythonw (the app on autostart) has none; capcut_edit imports this module
    sys.stdout.reconfigure(encoding="utf-8")


def __getattr__(name):
    # read on use, so read() can be imported (pace.py check) on a machine without edit_data set
    if name == "DATA":
        return Path(kitconfig.need("edit_data"))
    if name == "DB":
        return Path(kitconfig.need("edit_data")) / "edits.sqlite"
    raise AttributeError(name)

COMB = set(chr(c) for c in [0x0E31] + list(range(0x0E34, 0x0E3B)) + list(range(0x0E47, 0x0E4F)))

SCHEMA = """
CREATE TABLE clips(id INTEGER PRIMARY KEY, client, draft, folder, approved_by, approved_on, duration_s, hook);
CREATE TABLE cuts(clip_id, version, idx, start_s, dur_s, source, src_start_s, scale, x, y);
CREATE TABLE cards(clip_id, version, role, start_s, dur_s, text, size, color, x, y, scale, rotation, anim, anim_kind, anim_s, track);
CREATE TABLE inserts(clip_id, version, start_s, dur_s, file, scale, x, y);
CREATE TABLE audio(clip_id, version, start_s, dur_s, name, volume);
CREATE TABLE effects(clip_id, version, start_s, dur_s, name);
CREATE TABLE changes(clip_id, time, op, kind, tbl, row);
"""


def color(st):
    c = st.get("fill", {}).get("content", {}).get("solid", {}).get("color") or [1, 1, 1]
    r, g, b = [round(v, 2) for v in c[:3]]
    if r > 0.9 and g > 0.9 and b > 0.9:
        return "white"
    if r > 0.9 and 0.4 < g < 0.6 and b < 0.1:
        return "orange"
    if r > 0.85 and g < 0.2:
        return "red"
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


def role(size, col, x, rot, anim, start, dur, ntrack):
    if size <= 12:
        return "english"
    # hook: opening title, either one big card or a few stacked lines on short tracks (BPS)
    if start < 1.0 and dur > 2.5 and (size >= 34 or ntrack <= 4):
        return "hook"
    if abs(x) >= 0.2 or abs(rot) >= 3:
        if anim in ("เลื่อนเข้า",):
            return "listener"
        if anim in ("อาการภาพสั่น",):
            return "reaction"
        return "wordplay"
    if col == "red":
        return "quote"
    return "context" if col == "white" else "punch"  # any accent colour (Nina orange, BPS blue) is the punch layer


def read(cur, clip_id, version, d):
    M = d["materials"]
    tex = {t["id"]: t for t in M.get("texts", [])}
    vids = {v["id"]: v for v in M.get("videos", [])}
    auds = {a["id"]: a for a in M.get("audios", [])}
    anims = {a["id"]: a for a in M.get("material_animations", [])}
    effs = {e["id"]: e.get("name") for k in ("video_effects", "effects") for e in M.get(k, [])}
    t_ = lambda s, k: s["target_timerange"][k] / 1e6
    for ti, tr in enumerate(d["tracks"]):
        for i, s in enumerate(tr["segments"]):
            a, du = t_(s, "start"), t_(s, "duration")
            if du < 0.05:  # CapCut placeholder segments (cover frames, empty text)
                continue
            cl = s.get("clip") or {}
            sc, tf = cl.get("scale", {}).get("x", 1), cl.get("transform", {})
            if tr["type"] == "video" and s["material_id"] in vids:
                v = vids[s["material_id"]]
                name = os.path.basename(v["path"])
                if ti == 0:
                    cur.execute("INSERT INTO cuts VALUES(?,?,?,?,?,?,?,?,?,?)", (clip_id, version, i, a, du, name,
                                (s.get("source_timerange") or {}).get("start", 0) / 1e6, sc, tf.get("x", 0), tf.get("y", 0)))
                elif name.lower() != "logo.png":
                    cur.execute("INSERT INTO inserts VALUES(?,?,?,?,?,?,?,?)", (clip_id, version, a, du, name, sc, tf.get("x", 0), tf.get("y", 0)))
            elif tr["type"] == "text" and s["material_id"] in tex:
                m = tex[s["material_id"]]
                c = json.loads(m["content"])
                if not c["text"].strip():
                    continue
                st = c["styles"][0]
                an = [x for r in s.get("extra_material_refs", []) if r in anims for x in anims[r].get("animations", [])]
                an0 = an[0] if an else {}
                col = color(st)
                rot = cl.get("rotation", 0)
                rl = role(st["size"], col, tf.get("x", 0), rot, an0.get("name"), a, du, len(tr["segments"]))
                cur.execute("INSERT INTO cards VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (clip_id, version, rl, a, du, c["text"], round(st["size"], 1),
                            col, tf.get("x", 0), tf.get("y", 0), sc, rot, an0.get("name"), an0.get("type"), an0.get("duration", 0) / 1e6, ti))
            elif tr["type"] == "audio" and s["material_id"] in auds:
                cur.execute("INSERT INTO audio VALUES(?,?,?,?,?,?)", (clip_id, version, a, du, auds[s["material_id"]].get("name"), s.get("volume", 1)))
            elif tr["type"] == "effect":
                cur.execute("INSERT INTO effects VALUES(?,?,?,?,?)", (clip_id, version, a, du, effs.get(s["material_id"])))


def extract():
    ap = json.loads((__getattr__("DATA") / "approved.json").read_text(encoding="utf-8-sig"))["clips"]
    drafts = Path(kitconfig.need("capcut_drafts"))
    names = os.listdir(drafts)
    db = __getattr__("DB")
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    cur = con.cursor()
    for n, c in enumerate(ap, 1):
        hits = [x for x in names if x == c["draft"] or x.startswith(c["draft"] + " ")]
        if len(hits) != 1:
            raise SystemExit(f"approved draft {c['draft']!r}: found {hits} in {drafts}")
        folder = drafts / hits[0]
        d = json.loads((folder / "draft_content.json").read_text(encoding="utf-8"))
        cur.execute("INSERT INTO clips VALUES(?,?,?,?,?,?,?,?)", (n, c["client"], c["draft"], hits[0], c.get("approved_by"), c.get("approved_on"), d["duration"] / 1e6, None))
        read(cur, n, "final", d)
        if c.get("ai_version"):
            av = folder / c["ai_version"]
            if not av.is_file():  # a whole backup draft folder next to the approved one
                av = drafts / c["ai_version"] / "draft_content.json"
            read(cur, n, "ai", json.loads(av.read_text(encoding="utf-8")))
        log = folder / "clipkit_changes.jsonl"  # every edit ClipKit wrote to this draft (capcut_edit._log_change)
        if log.is_file():
            for line in log.read_text(encoding="utf-8").splitlines():
                ch = json.loads(line)
                for kind in ("removed", "added"):
                    for tbl, rows in ch[kind].items():
                        cur.executemany("INSERT INTO changes VALUES(?,?,?,?,?,?)", [(n, ch["time"], ch["op"], kind, tbl, json.dumps(r, ensure_ascii=False)) for r in rows])
        hook = [r[0].replace("\n", " ") for r in cur.execute("SELECT text FROM cards WHERE clip_id=? AND version='final' AND role='hook' ORDER BY start_s", (n,))]
        cur.execute("UPDATE clips SET hook=? WHERE id=?", (" / ".join(dict.fromkeys(hook)) or None, n))
    con.commit()
    for t in ("clips", "cuts", "cards", "inserts", "audio", "effects"):
        print(t, con.execute(f"SELECT COUNT(*) FROM {t} WHERE {'1' if t == 'clips' else 'version=' + chr(39) + 'final' + chr(39)}").fetchone()[0])
    print("changes", con.execute("SELECT COUNT(*) FROM changes").fetchone()[0])


ROLE_TH = {"hook": "หัวคลิป", "context": "ตัวขาว (บริบท)", "punch": "ตัวสีเน้น (คำเด็ด)", "quote": "ตัวแดง (คำพูดยกมา หรือช็อก)",
           "listener": "คำพูดคนที่สอง (เลื่อนจากขอบ)", "reaction": "รีแอ็กชัน (ภาพสั่น)", "wordplay": "เล่นคำ (เยื้องหรือเอียง)", "english": "ซับอังกฤษ"}


def notes():
    out = Path(kitconfig.need("obsidian_notes"))
    (out / "คลิป").mkdir(parents=True, exist_ok=True)
    (out / "เทคนิค").mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(__getattr__("DB"))
    q = lambda s, *a: con.execute(s, a).fetchall()
    head = lambda tags: f"---\ntags: [clipkit, ข้อมูลตัดต่อ, {tags}]\ngenerated: editdata.py (อย่าแก้มือ)\n---\n"
    clips = q("SELECT id, client, draft, folder, duration_s, hook, approved_by FROM clips")
    for cid, client, draft, folder, dur, hook, by in clips:
        cuts = q("SELECT dur_s, scale FROM cuts WHERE clip_id=? AND version='final'", cid)
        ins = q("SELECT start_s, dur_s, file, scale, x FROM inserts WHERE clip_id=? AND version='final' ORDER BY start_s", cid)
        cards = q("SELECT role, start_s, dur_s, text, anim FROM cards WHERE clip_id=? AND version='final' ORDER BY start_s", cid)
        fx = q("SELECT start_s, dur_s, name FROM effects WHERE clip_id=? AND version='final' ORDER BY start_s", cid)
        med = sorted(c[0] for c in cuts)[len(cuts) // 2] if cuts else 0
        L = [head(client), f"# {folder}\n", f"กลับ [[ข้อมูลตัดต่อ]] · ลูกค้า {client} · อนุมัติโดย {by}\n",
             f"| ความยาว | ช็อต | ช็อตกลาง | ภาพแทรก | ป้าย | เอฟเฟกต์ |\n|---|---|---|---|---|---|\n| {dur:.1f} วิ | {len(cuts)} | {med:.2f} วิ | {len(ins)} | {sum(r[0] != 'english' for r in cards)} | {len(fx)} |\n",
             f"**หัวคลิป:** {hook or '-'}\n", "## ไทม์ไลน์ป้าย (ไม่รวมซับอังกฤษ)\n| เวลา | ชนิด | ข้อความ | แอนิเมชัน |\n|---|---|---|---|"]
        for rl, a, du, t, an in cards:
            if rl != "english":
                L.append(f"| {a:.1f} | [[{ROLE_TH[rl]}]] | {t.replace(chr(10), ' / ').replace('|', '/')} | {an or ''} |")
        L += ["\n## ภาพแทรก\n| เวลา | ยาว | ไฟล์ | สเกล | เลื่อน x |\n|---|---|---|---|---|"]
        L += [f"| {a:.1f} | {du:.1f} | {f} | {s:.2f} | {x:+.2f} |" for a, du, f, s, x in ins]
        if fx:
            L += ["\n## เอฟเฟกต์"] + [f"- {a:.1f}+{du:.1f} วิ {n}" for a, du, n in fx if n]
        ai = q("SELECT COUNT(*) FROM cards WHERE clip_id=? AND version='ai'", cid)[0][0]
        if ai:
            fin = {r[0] for r in q("SELECT text FROM cards WHERE clip_id=? AND version='final' AND role!='english'", cid)}
            aiv = {r[0] for r in q("SELECT text FROM cards WHERE clip_id=? AND version='ai' AND role!='english'", cid)}
            L += ["\n## AI ทำ vs พี่แก้ (ป้าย)",
                  f"- ป้ายเวอร์ชัน AI {len(aiv)} → พี่ {len(fin)} · คงไว้ {len(fin & aiv)} · พี่ตัดออก {len(aiv - fin)} · พี่เขียนใหม่ {len(fin - aiv)}",
                  "- พี่เขียนใหม่: " + ", ".join(sorted(fin - aiv))[:1500]]
        (out / "คลิป" / f"{folder}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    for rl, th in ROLE_TH.items():
        rows = q("SELECT c.folder, k.start_s, k.dur_s, k.text, k.size, k.x, k.y, k.rotation, k.scale, k.anim FROM cards k JOIN clips c ON c.id=k.clip_id WHERE k.version='final' AND k.role=? ORDER BY c.id, k.start_s", rl)
        if not rows:
            continue
        d = [r[2] for r in rows]
        an = Counter(r[9] or "-" for r in rows).most_common(4)
        L = [head("เทคนิค"), f"# {th}\n", "กลับ [[ข้อมูลตัดต่อ]]\n",
             f"ใช้ {len(rows)} ครั้งใน {len({r[0] for r in rows})} คลิป · ค้างเฉลี่ย {sum(d) / len(d):.2f} วิ · ขนาดที่ใช้บ่อย {Counter(round(r[4]) for r in rows).most_common(1)[0][0]} · แอนิเมชัน: " + ", ".join(f"{a} ({n})" for a, n in an) + "\n",
             "| คลิป | เวลา | ข้อความ | x | y | เอียง | สเกล | แอนิเมชัน |\n|---|---|---|---|---|---|---|---|"]
        L += [f"| [[{f}]] | {a:.1f} | {t.replace(chr(10), ' / ').replace('|', '/')[:60]} | {x:+.2f} | {y:+.2f} | {ro:.0f}° | {s:.2f} | {n or ''} |"
              for f, a, du, t, sz, x, y, ro, s, n in rows]
        (out / "เทคนิค" / f"{th}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    by_client = defaultdict(list)
    for cid, client, draft, folder, dur, hook, by in clips:
        by_client[client].append((folder, dur, hook))
    tot = q("SELECT (SELECT COUNT(*) FROM inserts WHERE version='final'), (SELECT SUM(duration_s) FROM clips)")[0]
    L = [head("index"), "# ข้อมูลตัดต่อ\n",
         "สร้างอัตโนมัติจากโปรเจกต์ CapCut ที่อยู่ในรายชื่อผ่านแล้ว (`approved.json`) ด้วย `editdata.py` · ฐานข้อมูลเต็ม: `edits.sqlite` · แนวคิดเบื้องหลัง: [[เทคนิคตัดต่อของพี่]]\n",
         f"รวม {len(clips)} คลิป · {tot[1] / 60:.1f} นาที · ภาพแทรก {tot[0]} ตัว\n", "## เทคนิค (ตัวอย่างจริงทุกครั้งที่ใช้)"]
    L += [f"- [[{th}]]" for rl, th in ROLE_TH.items() if (out / "เทคนิค" / f"{th}.md").exists()]
    for client, rows in by_client.items():
        L += [f"\n## {client}", "| คลิป | ยาว | หัวคลิป |\n|---|---|---|"] + [f"| [[{f}]] | {d:.0f} วิ | {h or ''} |" for f, d, h in rows]
    (out / "ข้อมูลตัดต่อ.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("notes ->", out)


if __name__ == "__main__":
    {"extract": extract, "notes": notes}[sys.argv[1]]()
