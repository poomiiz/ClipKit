r"""ClipKit Autosave: keep every version of every CapCut project and write down what changed, on this machine only.

    python scripts/autosave.py run                      # one pass (the scheduled task runs this every 5 minutes)
    python scripts/autosave.py install                  # add the Windows scheduled task (every 5 minutes, hidden)
    python scripts/autosave.py uninstall
    python scripts/autosave.py history "<project>"      # the saved versions of one project
    python scripts/autosave.py restore "<project>" [version]   # put a saved version back (CapCut must be closed)

Each pass looks at every project in config.json capcut_drafts. A project whose timeline changed is checked
(the JSON reads, every clip points at a material that exists) and, when sound, saved as a new version in a
git repository under history_dir (default %LOCALAPPDATA%\ClipKit\history). Only the timeline JSON is kept,
never the video. Every saved change adds one line to <history_dir>/changes.jsonl: what moved (cut count,
shot length, subtitle size / position / length, b-roll, music volume) and who made it ("clipkit" when the
project still carries ClipKit's seal, "person" when it was edited in CapCut, "unknown" for an unsealed project). A broken project is never saved
over the last good version; it is written to changes.jsonl as "broken" and named in the output.
Nothing here is sent anywhere.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
if sys.stdout is None:  # pythonw (the scheduled task) has no console: the output goes to a log next to the history
    _log = Path(os.environ["LOCALAPPDATA"]) / "ClipKit" / "autosave.log"
    _log.parent.mkdir(parents=True, exist_ok=True)
    sys.stdout = sys.stderr = _log.open("a", encoding="utf-8")
    print(f"--- {datetime.datetime.now().isoformat(timespec='seconds')}")
else:
    sys.stdout.reconfigure(encoding="utf-8")
import capcut_edit  # noqa: E402
import kitconfig  # noqa: E402  (on sys.path through video_edit)

US = 1_000_000
TASK = "ClipKit-Autosave"


def history_dir() -> Path:
    d = Path(kitconfig.CFG.get("history_dir") or Path(os.environ["LOCALAPPDATA"]) / "ClipKit" / "history")
    d.mkdir(parents=True, exist_ok=True)
    if not (d / ".git").is_dir():
        subprocess.run(["git", "init", "-q", str(d)], check=True)
        (d / ".gitignore").write_text("changes.jsonl\n", encoding="utf-8")
    return d


def git(d: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(d), "-c", "user.name=ClipKit Autosave", "-c", "user.email=autosave@clipkit.local",
                        *args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def timeline(folder: Path) -> Path:
    """The copy CapCut edits: Timelines/<main id>/draft_content.json (CapCut 9.x) when it is the newer one."""
    root = folder / "draft_content.json"
    proj = folder / "Timelines" / "project.json"
    if proj.is_file():
        tid = json.loads(proj.read_text(encoding="utf-8")).get("main_timeline_id")
        inner = folder / "Timelines" / str(tid) / "draft_content.json"
        if inner.is_file() and (not root.is_file() or inner.stat().st_mtime > root.stat().st_mtime):
            return inner
    return root


def problems(draft: dict[str, Any]) -> list[str]:
    """What would stop CapCut opening this timeline."""
    bad = [f"missing '{k}'" for k in ("tracks", "materials", "duration") if k not in draft]
    if bad:
        return bad
    ids = {m["id"] for v in draft["materials"].values() if isinstance(v, list) for m in v if isinstance(m, dict) and "id" in m}
    for t in draft["tracks"]:
        for s in t.get("segments", []):
            if s.get("material_id") and s["material_id"] not in ids:
                bad.append(f"a {t.get('type')} clip points at material {s['material_id']} that is not in the project")
    return bad[:5]


def measure(draft: dict[str, Any]) -> dict[str, Any]:
    """The editing choices worth learning from, in plain numbers."""
    tracks = draft["tracks"]
    videos = [t for t in tracks if t["type"] == "video"]
    main = videos[0]["segments"] if videos else []
    texts = [s for t in tracks if t["type"] == "text" for s in t["segments"]]
    mats = {m["id"]: m for m in draft["materials"].get("texts", [])}
    words = [json.loads(mats[s["material_id"]]["content"]).get("text", "") for s in texts if s["material_id"] in mats]
    sizes = [mats[s["material_id"]].get("font_size") for s in texts if s["material_id"] in mats]
    audio = [s for t in tracks if t["type"] == "audio" for s in t["segments"]]
    r = lambda x, n=2: round(x, n) if x is not None else None  # noqa: E731
    return {
        "length_s": r(draft["duration"] / US, 1),
        "cuts": len(main),
        "shot_s": r(mean(s["target_timerange"]["duration"] / US for s in main)) if main else None,
        "subtitles": len(texts),
        "subtitle_letters": r(mean(len(w) for w in words), 1) if words else None,
        "subtitle_size": r(mean(x for x in sizes if x), 1) if any(sizes) else None,
        "subtitle_y": r(mean(s["clip"]["transform"]["y"] for s in texts)) if texts else None,
        "broll": sum(len(t["segments"]) for t in videos[1:]),
        "audio_clips": len(audio),
        "audio_volume": r(mean(s.get("volume", 1) for s in audio)) if audio else None,
    }


def editor(folder: Path, text: str) -> str:
    seal = folder / capcut_edit.SEAL
    if not seal.is_file():
        return "unknown"  # made before ClipKit sealed its projects
    return "clipkit" if json.loads(seal.read_text(encoding="utf-8")).get("draft_content") == capcut_edit._digest(text) else "person"


def slug(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "_"


def run() -> int:
    drafts = Path(kitconfig.need("capcut_drafts"))
    hist = history_dir()
    log = hist / "changes.jsonl"
    saved, broken = [], []
    for folder in sorted(p for p in drafts.iterdir() if p.is_dir()):
        src = timeline(folder)
        if not src.is_file():
            continue
        text = src.read_text(encoding="utf-8")
        dst = hist / slug(folder.name) / "draft_content.json"
        if dst.is_file() and dst.read_text(encoding="utf-8") == text:
            continue
        now = datetime.datetime.now().isoformat(timespec="seconds")
        try:
            draft = json.loads(text)
            bad = problems(draft)
        except (ValueError, KeyError, TypeError) as exc:
            draft, bad = None, [f"cannot read the timeline: {exc}"]
        if bad:
            broken.append(f"{folder.name}: {'; '.join(bad)}")
            with log.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"at": now, "project": folder.name, "broken": bad}, ensure_ascii=False) + "\n")
            continue
        before = measure(json.loads(dst.read_text(encoding="utf-8"))) if dst.is_file() else {}
        after = measure(draft)
        dst.parent.mkdir(exist_ok=True)
        dst.write_text(text, encoding="utf-8")
        who = editor(folder, (folder / "draft_content.json").read_text(encoding="utf-8")) if (folder / "draft_content.json").is_file() else "unknown"
        changed = {k: [before.get(k), v] for k, v in after.items() if before.get(k) != v}
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"at": now, "project": folder.name, "by": who, "new": not before, "changed": changed},
                               ensure_ascii=False) + "\n")
        saved.append(folder.name)
    if saved:
        git(hist, "add", "-A")
        git(hist, "commit", "-q", "-m", f"{len(saved)} project(s): " + ", ".join(saved)[:200])
    print(f"saved {len(saved)} project(s)" + (f", {len(broken)} broken:" if broken else ""))
    for b in broken:
        print("  BROKEN", b)
    return 1 if broken else 0


def history(project: str) -> None:
    hist = history_dir()
    print(git(hist, "log", "--format=%h  %ad  %s", "--date=format:%Y-%m-%d %H:%M", "--", f"{slug(Path(project).name)}/"))


def restore(project: str, version: str = "HEAD") -> None:
    folder = Path(project)
    if not folder.is_absolute():
        folder = Path(kitconfig.need("capcut_drafts")) / project
    hist = history_dir()
    text = git(hist, "show", f"{version}:{slug(folder.name)}/draft_content.json")
    content = folder / "draft_content.json"
    if content.is_file():
        shutil.copy2(content, content.with_suffix(".json.bak_restore"))
    content.write_text(text, encoding="utf-8")
    capcut_edit.sync_timeline(folder, text)
    print(f"restored {folder.name} to {version} (the current file is kept as draft_content.json.bak_restore)")


def install() -> None:
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe") if py.with_name("pythonw.exe").is_file() else py
    cmd = f'"{pyw}" "{Path(__file__).resolve()}" run'
    subprocess.run(["schtasks", "/create", "/f", "/tn", TASK, "/sc", "minute", "/mo", "5", "/tr", cmd], check=True)
    print(f"installed: {TASK} runs every 5 minutes; history in {history_dir()}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("run", "install", "uninstall", "history", "restore"):
        sys.exit(__doc__)
    if a[0] == "run":
        sys.exit(run())
    if a[0] == "install":
        install()
    elif a[0] == "uninstall":
        subprocess.run(["schtasks", "/delete", "/f", "/tn", TASK], check=True)
    elif a[0] == "history" and len(a) == 2:
        history(a[1])
    elif a[0] == "restore" and len(a) in (2, 3):
        restore(*a[1:])
    else:
        sys.exit(__doc__)
