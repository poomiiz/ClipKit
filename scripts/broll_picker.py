"""B-roll picker: Envato search -> HTML picker -> download only ticked items.

    python broll_picker.py search   broll_plan.json      # queue searches on the team bot, save results
    python broll_picker.py html     broll_plan.json      # write broll_picker.html (thumbnails + checkboxes)
    python broll_picker.py download broll_selected.json  # queue downloads for ticked items, then file them

broll_plan.json rows: {"t": 12.4, "dur": 1.5, "said": "...", "query": "english shot description", "topic": "01_..."}
Bot access needs config.json "bot_api_url" (default http://127.0.0.1:8765) and env KB_API_KEY.
Every download registers a licence on the company Envato account: only ticked items are downloaded.
"""
import html
import json
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "capcut"))
from kitconfig import CFG  # noqa: E402

API = (CFG.get("bot_api_url") or "http://127.0.0.1:8765").rstrip("/") + "/bot/api"
OPEN_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, path, body=None):
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("KB_API_KEY") or os.environ.get("API_KEY")
    if key:  # the bot host may run without a key; a remote host returns 401/403 and the call raises
        headers["X-API-Key"] = key
    req = urllib.request.Request(API + path, method=method, headers=headers,
                                 data=json.dumps(body).encode() if body is not None else None)
    with OPEN_PROXY.open(req, timeout=30) as r:
        return json.loads(r.read())


def wait(job_ids, timeout=1800):
    pending, done = set(job_ids), {}
    end = time.time() + timeout
    while pending:
        if time.time() > end:
            raise RuntimeError(f"bot jobs still running after {timeout}s: {sorted(pending)}")
        for jid in list(pending):
            j = call("GET", f"/jobs/{jid}")
            if j["status"] in ("done", "failed", "needs_human", "cancelled"):
                done[jid] = j
                pending.discard(jid)
        if pending:
            time.sleep(5)
    return done


def load(path):
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"{path}: expected a non-empty list")
    for i, r in enumerate(rows):
        for k in ("t", "said", "query", "topic"):
            if k not in r:
                raise RuntimeError(f"{path} row {i}: missing '{k}'")
    return rows


def cmd_search(plan_path):
    rows = load(plan_path)
    ids = [call("POST", "/jobs", {"site": "envato", "action": "search", "created_by": "clip-kit",
                                  "payload": {"query": r["query"], "count": 4}})["id"] for r in rows]
    results = wait(ids)
    problems = []
    for r, jid in zip(rows, ids):
        j = results[jid]
        r["job"] = jid
        r["options"] = (j.get("result") or {}).get("items") or []
        r["screenshot"] = j.get("artifact_url")
        if j["status"] != "done":
            problems.append(f"t={r['t']} '{r['query']}': {j['status']} {j.get('error') or ''}")
    Path(plan_path).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{plan_path}: {len(rows) - len(problems)}/{len(rows)} searches have results")
    for p in problems:
        print("  NO RESULT", p)


def cmd_html(plan_path):
    rows = load(plan_path)
    if not any(r.get("options") for r in rows):
        raise RuntimeError("no search results in the plan - run 'search' first")
    out = Path(plan_path).with_name("broll_picker.html")
    body = []
    for i, r in enumerate(rows):
        opts = "".join(
            f'<label class="opt"><input type="checkbox" data-row="{i}" data-url="{html.escape(o["url"])}">'
            f'<a href="{html.escape(o["url"])}" target="_blank">{html.escape(o["title"])}</a></label>'
            for o in r.get("options") or []) or "<em>no results - search by hand</em>"
        shot = f'<a href="{html.escape(r["screenshot"])}" target="_blank">screenshot</a>' if r.get("screenshot") else ""
        body.append(f'<tr><td>{r["t"]:.1f}s</td><td><b>{html.escape(r["said"])}</b><br><small>{html.escape(r["query"])} · {html.escape(r["topic"])} {shot}</small></td><td>{opts}</td></tr>')
    rows_js = json.dumps([{k: r[k] for k in ("t", "said", "query", "topic")} for r in rows], ensure_ascii=False)
    out.write_text(f"""<!doctype html><meta charset="utf-8"><title>B-roll picker</title>
<style>body{{font:14px system-ui;margin:16px}}table{{border-collapse:collapse;width:100%}}td{{border-bottom:1px solid #ddd;padding:6px;vertical-align:top}}
.opt{{display:block;margin:2px 0}}button{{position:sticky;top:0;padding:8px 16px;font-size:15px}}</style>
<h2>B-roll picker - tick the clips to download (each download uses a licence)</h2>
<button onclick="exp()">Export selected (broll_selected.json)</button> <span id="n"></span>
<table>{''.join(body)}</table>
<script>
const ROWS={rows_js};
document.addEventListener('change',()=>document.getElementById('n').textContent=document.querySelectorAll('input:checked').length+' selected');
function exp(){{const sel=[...document.querySelectorAll('input:checked')].map(c=>({{...ROWS[c.dataset.row],url:c.dataset.url}}));
if(!sel.length){{alert('nothing ticked');return}}
const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(sel,null,1)],{{type:'application/json'}}));
a.download='broll_selected.json';a.click();}}
</script>""", encoding="utf-8")
    print(out)


def cmd_download(sel_path):
    sel = load(sel_path)
    dest_root = Path(sel_path).resolve().parent / "inserts"
    ids = [call("POST", "/jobs", {"site": "envato", "action": "download", "created_by": "clip-kit",
                                  "payload": {"url": s["url"], "kind": "video", "quality": "1080P"}})["id"] for s in sel]
    results = wait(ids, timeout=3600)
    failed = 0
    for n, (s, jid) in enumerate(zip(sel, ids), 1):
        j = results[jid]
        src = (j.get("result") or {}).get("file")
        if j["status"] != "done" or not src or not Path(src).is_file():
            failed += 1
            print(f"  FAILED t={s['t']} {s['url']}: {j['status']} {j.get('error') or ''}")
            continue
        d = dest_root / s["topic"]
        d.mkdir(parents=True, exist_ok=True)
        safe = "".join(ch for ch in s["said"] if ch not in '\\/:*?"<>|').strip()[:40]
        target = d / f"{n:02d}_{safe}{Path(src).suffix}"
        shutil.copy2(src, target)          # keep the original in stock_video for reuse
        print(f"  {target}")
    if failed:
        raise RuntimeError(f"{failed} of {len(sel)} downloads failed - see lines above")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 3 or sys.argv[1] not in ("search", "html", "download"):
        sys.exit(__doc__)
    {"search": cmd_search, "html": cmd_html, "download": cmd_download}[sys.argv[1]](sys.argv[2])
