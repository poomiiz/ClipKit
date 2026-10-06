"""Pace from real edits: how long cards stay up, how long inserts run, how often each comes, per client.

The numbers come from edits.sqlite (editdata.py extract), i.e. from clips a person approved - never typed by hand.

    python scripts/capcut/pace.py baseline              # edits.sqlite -> presets/pace/<client>.json (rerun after every extract)
    python scripts/capcut/pace.py check <draft> <client>   # one CapCut project against that client's pace
    python scripts/capcut/pace.py learn                 # what the person changed in the AI versions; repeats -> rule ideas

A limit is the person's own 75th percentile (holds, insert length) or 90th (gaps between cards); "too few" is below
80 % of the person's rate per minute.
"""
import json
import sqlite3
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import editdata

sys.stdout.reconfigure(encoding="utf-8")
PACE = Path(__file__).resolve().parents[2] / "presets" / "pace"
ROLES = ("context", "punch", "quote", "wordplay")  # the card layers a person paces; hook and english are not
FEW = 0.8          # below 80 % of the person's cards per minute = too few
LOW_DATA_MIN = 5   # fewer approved minutes than this: numbers are shown but marked as not settled yet
REPEAT = 3         # the same change in this many clips becomes a rule idea


def pct(xs, p):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(p * len(xs)))], 2)


def measure(con, clip_ids, version):
    """Holds, insert lengths, gaps and counts over the given clips of one version."""
    q = lambda sql, *a: con.execute(sql, a).fetchall()  # noqa: E731
    ph = ",".join("?" * len(clip_ids))
    minutes = sum(r[0] for r in q(f"SELECT duration_s FROM clips WHERE id IN ({ph})", *clip_ids)) / 60
    holds = defaultdict(list)
    for r, d in q(f"SELECT role, dur_s FROM cards WHERE version=? AND clip_id IN ({ph})", version, *clip_ids):
        holds[r].append(d)
    ins = [r[0] for r in q(f"SELECT dur_s FROM inserts WHERE version=? AND clip_id IN ({ph})", version, *clip_ids)]
    gaps = []
    for cid in clip_ids:
        end = None
        rows = q(f"SELECT start_s, dur_s FROM cards WHERE version=? AND clip_id=? AND role IN ({','.join('?' * len(ROLES))}) ORDER BY start_s",
                 version, cid, *ROLES)
        for a, d in rows:
            if end is not None and a - end > 0.05:
                gaps.append(round(a - end, 2))
            end = max(end or 0, a + d)
    return minutes, holds, ins, gaps


def baseline():
    con = sqlite3.connect(editdata.DB)
    PACE.mkdir(parents=True, exist_ok=True)
    by = defaultdict(list)
    for cid, client in con.execute("SELECT id, client FROM clips"):
        by[client].append(cid)
    for client, ids in by.items():
        minutes, holds, ins, gaps = measure(con, ids, "final")
        out = {"client": client, "clips": len(ids), "minutes": round(minutes, 1), "low_data": minutes < LOW_DATA_MIN,
               "cards": {r: {"per_min": round(len(holds[r]) / minutes, 1), "hold_median": round(statistics.median(holds[r]), 2),
                             "hold_max": pct(holds[r], 0.75)} for r in ROLES if holds[r]},
               "inserts": {"per_min": round(len(ins) / minutes, 1), "len_median": round(statistics.median(ins), 2),
                           "len_max": pct(ins, 0.75)} if ins else None,
               "gap_max": pct(gaps, 0.9) if gaps else None}
        (PACE / f"{client}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False))


def load(client):
    p = PACE / f"{client}.json"
    if not p.is_file():
        raise SystemExit(f"no pace for client {client!r}: run 'pace.py baseline' after editdata.py extract ({p})")
    return json.loads(p.read_text(encoding="utf-8"))


def check(draft, client):
    """One CapCut project (folder or draft_content.json) against the client's pace: {score, checks, problems}."""
    base = load(client)
    f = Path(draft)
    f = f / "draft_content.json" if f.is_dir() else f
    d = json.loads(f.read_text(encoding="utf-8"))
    con = sqlite3.connect(":memory:")
    con.executescript(editdata.SCHEMA)
    con.execute("INSERT INTO clips(id, duration_s) VALUES(1, ?)", (d["duration"] / 1e6,))
    editdata.read(con.cursor(), 1, "check", d)
    minutes, holds, ins, gaps = measure(con, [1], "check")
    checks = []
    add = lambda name, ok, detail: checks.append({"check": name, "ok": bool(ok), "detail": detail})  # noqa: E731
    for r, b in base["cards"].items():
        long = [h for h in holds[r] if h > b["hold_max"]]
        add(f"ป้าย {r} ค้างนาน", not long, f"{len(long)}/{len(holds[r])} อันเกิน {b['hold_max']} วิ (คนตัดค้างกลาง {b['hold_median']} วิ)")
        rate = len(holds[r]) / minutes if minutes else 0
        add(f"ป้าย {r} ถี่พอ", rate >= FEW * b["per_min"], f"{rate:.1f}/นาที (คนตัด {b['per_min']})")
    if base["inserts"]:
        b = base["inserts"]
        long = [x for x in ins if x > b["len_max"]]
        add("ภาพแทรกยาว", not long, f"{len(long)}/{len(ins)} ตัวเกิน {b['len_max']} วิ (คนตัดกลาง {b['len_median']} วิ)")
    if base["gap_max"]:
        long = [g for g in gaps if g > base["gap_max"]]
        add("ช่วงไม่มีป้าย", not long, f"{len(long)} ช่วงเกิน {base['gap_max']} วิ")
    passed = sum(c["ok"] for c in checks)
    return {"client": client, "low_data": base["low_data"], "score": f"{passed}/{len(checks)}", "checks": checks,
            "problems": [f"{c['check']}: {c['detail']}" for c in checks if not c["ok"]]}


def learn():
    """Per clip with an AI version: what the person changed. A change seen in REPEAT+ clips is printed as a rule idea."""
    con = sqlite3.connect(editdata.DB)
    clips = con.execute("SELECT DISTINCT c.id, c.client, c.folder FROM clips c JOIN cards k ON k.clip_id=c.id WHERE k.version='ai'").fetchall()
    seen = defaultdict(list)
    report = []
    for cid, client, folder in clips:
        _, h_ai, i_ai, _ = measure(con, [cid], "ai")
        _, h_fi, i_fi, _ = measure(con, [cid], "final")
        row = {"clip": folder, "client": client}
        for r in ROLES:
            if h_ai[r] and h_fi[r]:
                a, b = statistics.median(h_ai[r]), statistics.median(h_fi[r])
                row[f"{r}_hold"] = [round(a, 2), round(b, 2)]
                if b < 0.8 * a:
                    seen[(client, f"ป้าย {r} ค้างสั้นลง")].append(f"{folder}: {a:.2f}→{b:.2f} วิ")
        if i_ai and i_fi:
            a, b = statistics.median(i_ai), statistics.median(i_fi)
            row["insert_len"] = [round(a, 2), round(b, 2)]
            if b < 0.8 * a:
                seen[(client, "ภาพแทรกสั้นลง")].append(f"{folder}: {a:.2f}→{b:.2f} วิ")
        q = lambda v: {t for (t,) in con.execute("SELECT text FROM cards WHERE clip_id=? AND version=? AND role IN (%s)" % ",".join("?" * len(ROLES)), (cid, v, *ROLES))}  # noqa: E731
        ai, fi = q("ai"), q("final")
        row["cards_kept"] = f"{len(ai & fi)}/{len(ai)}"
        if ai and len(ai & fi) / len(ai) < 0.5:
            seen[(client, "ป้าย AI ถูกเขียนใหม่เกินครึ่ง")].append(f"{folder}: เก็บ {len(ai & fi)}/{len(ai)}")
        report.append(row)
    rules = [{"client": c, "change": ch, "clips": ev} for (c, ch), ev in seen.items() if len(ev) >= REPEAT]
    waiting = [{"client": c, "change": ch, "clips": ev, "need": REPEAT - len(ev)} for (c, ch), ev in seen.items() if len(ev) < REPEAT]
    print(json.dumps({"clips_with_ai_version": len(clips), "per_clip": report, "rule_ideas": rules, "not_yet": waiting},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "check":
        print(json.dumps(check(sys.argv[2], sys.argv[3]), ensure_ascii=False, indent=1))
    else:
        {"baseline": baseline, "learn": learn}[cmd]()
