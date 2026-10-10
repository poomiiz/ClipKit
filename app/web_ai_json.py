"""Web AI: ClipKit's two judgement steps (split into stories; subtitles, emphasis, title, motion per clip) done by
an AI in the browser (claude.ai, ChatGPT...) instead of an agent on this machine.

export_*() writes one text file to upload: the prompt plus the transcript and timings, never the video. The AI
answers with one JSON (schema: prompts/web_ai/schema.md); import_answer() checks it and writes the same files the
local agent writes (<video>.stories.json, clipkit_punch.json, clipkit_hook.json, clipkit_caption.json, motion), so
run_clip / the editor carry on as before and the CapCut project is built here from this machine's own media.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import capcut_edit
import render
import video_edit
from video_edit import VideoEditError

VERSION = 1
PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
LOOKS = {"pair", "white", "color", "red", "hold", "skip"}
MOTION = {"hook-title", "sentence-pair"}  # video_editor.MOTION_TEMPLATES


def _prompt(name: str) -> str:
    bare = lambda f: re.sub(r"<!--.*?-->\s*", "", f.read_text(encoding="utf-8"), flags=re.S).strip()  # noqa: E731
    return bare(PROMPTS / "web_ai" / name).replace("{STORY_RULES}", bare(PROMPTS / "story_split.md"))


def _packet(prompt: str, data: dict[str, Any], out: Path) -> Path:
    out.write_text(prompt.rstrip() + "\n\n## ข้อมูล (อย่าแก้ช่อง clipkit_web_ai, step, video, project)\n\n```json\n"
                   + json.dumps(data, ensure_ascii=False, indent=1) + "\n```\n", encoding="utf-8")
    return out


def _caption_lang(path: str) -> str | None:
    """The language the preset's small caption needs from the AI; None = no caption (or Thai: the spoken line)."""
    f = Path(path) / "clipkit_style.json"
    style = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    if style.get("anim") != "pair":
        return None
    look = render.pair_look(style)
    return look["caption_lang"] if look["caption"] and look["caption_lang"] != "th" else None


def export_stories(video: str) -> Path:
    tf = video_edit.transcript_file(video)
    if not tf.is_file():
        raise VideoEditError(f"ยังไม่ได้ถอดเสียง: ไม่มี {tf.name} (กด ถอดเสียงและแบ่งเรื่อง ก่อน)")
    lines = [{"start": round(p["start"], 2), "end": round(p["end"], 2), "text": p["text"]}
             for p in json.loads(tf.read_text(encoding="utf-8"))]
    data = {"clipkit_web_ai": VERSION, "step": "stories", "video": Path(video).name, "lines": lines}
    return _packet(_prompt("stories.md"), data, Path(video).with_name(Path(video).name + ".web-ai-stories.md"))


def export_clip(path: str) -> Path:
    subs = capcut_edit.read_draft(path)["subtitles"]
    if not subs:
        raise VideoEditError("ยังไม่มีซับ — ถอดเสียงก่อน")
    lines = [s["text"] for s in subs]
    (Path(path) / "clipkit_lines.json").write_text(json.dumps(lines, ensure_ascii=False, indent=1), encoding="utf-8")
    data = {"clipkit_web_ai": VERSION, "step": "clip", "project": Path(path).name, "caption_language": _caption_lang(path),
            "lines": [{"n": n, "start": s["start"], "end": s["end"], "text": s["text"]} for n, s in enumerate(subs, 1)]}
    return _packet(_prompt("clip.md"), data, Path(path) / "clipkit_web_ai.md")


def parse(text: str) -> dict[str, Any]:
    """The AI's answer as pasted: bare JSON, or JSON inside a ```json block with words around it."""
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    body = m.group(1) if m else text.strip()
    try:
        out = json.loads(body)
    except ValueError as exc:
        raise VideoEditError(f"คำตอบไม่ใช่ JSON: {exc}") from exc
    if not isinstance(out, dict):
        raise VideoEditError("คำตอบต้องเป็น JSON object { ... }")
    return out


def _head(ans: dict[str, Any], step: str, key: str, name: str) -> None:
    if ans.get("clipkit_web_ai") != VERSION:
        raise VideoEditError(f"clipkit_web_ai ต้องเป็น {VERSION} (ได้ {ans.get('clipkit_web_ai')!r}): ใช้ไฟล์ที่ export จาก ClipKit รุ่นนี้")
    if ans.get("step") != step:
        raise VideoEditError(f"คำตอบนี้เป็นขั้น {ans.get('step')!r} แต่กำลังนำเข้าขั้น {step!r}")
    if ans.get(key) != name:
        raise VideoEditError(f"คำตอบนี้เป็นของ {ans.get(key)!r} ไม่ใช่ {name!r}: นำเข้าผิดไฟล์")


def _num(x: Any, where: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise VideoEditError(f"{where} ต้องเป็นตัวเลขวินาที (ได้ {x!r})")
    return float(x)


def import_stories(video: str, ans: dict[str, Any]) -> list[dict[str, Any]]:
    _head(ans, "stories", "video", Path(video).name)
    phrases = json.loads(video_edit.transcript_file(video).read_text(encoding="utf-8"))
    items = ans.get("stories")
    if not isinstance(items, list) or not items:
        raise VideoEditError("stories ต้องเป็นรายการเรื่องอย่างน้อย 1 เรื่อง")
    out = []
    for n, it in enumerate(items, 1):
        if not isinstance(it, dict) or not isinstance(it.get("title"), str) or not it["title"].strip():
            raise VideoEditError(f"เรื่องที่ {n}: ต้องมี title")
        a, b = _num(it.get("start"), f"เรื่องที่ {n} start"), _num(it.get("end"), f"เรื่องที่ {n} end")
        if not 0 <= a < b:
            raise VideoEditError(f"เรื่องที่ {n} '{it['title']}': start ต้องน้อยกว่า end ({a}-{b})")
        if not any(p["start"] >= a - 0.5 and p["end"] <= b + 0.5 for p in phrases):
            raise VideoEditError(f"เรื่องที่ {n} '{it['title']}' ({a}-{b} วิ) ไม่มีเสียงพูดในช่วงนั้น")
        out.append({"title": it["title"].strip(), "summary": str(it.get("summary", "")).strip(), "start": a, "end": b})
    video_edit.stories_file(video).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def _item(it: Any, where: str) -> list:
    if not isinstance(it, list) or not 2 <= len(it) <= 4 or not all(isinstance(x, str) for x in it[:2]):
        raise VideoEditError(f"{where}: ต้องเป็น [lead, punch] หรือ [lead, punch, คำค้น, ตัวเลือก] (ได้ {it!r})")
    for x in it[2:]:
        if isinstance(x, dict):
            if x.get("look", "pair") not in LOOKS:
                raise VideoEditError(f"{where}: look ต้องเป็นหนึ่งใน {sorted(LOOKS)} (ได้ {x.get('look')!r})")
            show = x.get("show")
            if show is not None and (not isinstance(show, list) or len(show) != 2 or not all(isinstance(s, str) for s in show)):
                raise VideoEditError(f"{where}: show ต้องเป็น [ข้อความขาว, ข้อความเน้น]")
            if x.get("color") is not None and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(x["color"])):
                raise VideoEditError(f"{where}: color ต้องเป็น #rrggbb (ได้ {x['color']!r})")
            if x.get("second") is not None and not isinstance(x["second"], str):
                raise VideoEditError(f"{where}: second ต้องเป็นข้อความ")
        elif not isinstance(x, str):
            raise VideoEditError(f"{where}: ช่องที่ 3-4 ต้องเป็นคำค้น (ข้อความ) หรือตัวเลือก {{...}}")
    return it


def import_clip(path: str, ans: dict[str, Any]) -> dict[str, Any]:
    """Checks the whole answer first, then writes every file: a bad answer changes nothing."""
    _head(ans, "clip", "project", Path(path).name)
    subs = capcut_edit.read_draft(path)["subtitles"]
    tight = lambda t: "".join(t.split())  # noqa: E731  (spaces may be dropped, nothing else - render._pair)
    lines = ans.get("lines")
    if not isinstance(lines, list) or [x.get("n") if isinstance(x, dict) else None for x in lines] != list(range(1, len(subs) + 1)):
        raise VideoEditError(f"lines ต้องมีครบ {len(subs)} บรรทัด เรียง n = 1..{len(subs)} ตามไฟล์ที่ส่งไป")
    cut = ans.get("cut") or []
    if not isinstance(cut, list) or any(n not in range(1, len(subs) + 1) for n in cut) or len(set(cut)) >= len(subs):
        raise VideoEditError(f"cut ต้องเป็นรายการเลขบรรทัด 1..{len(subs)} ที่จะตัดทิ้ง และต้องเหลืออย่างน้อย 1 บรรทัด")
    punch = {}
    for s, x in zip(subs, lines):
        if x["n"] in cut:
            continue
        items = x.get("items")
        if not isinstance(items, list) or not items:
            raise VideoEditError(f"บรรทัด {x['n']}: items ต้องมีอย่างน้อย 1 ท่อน")
        items = [_item(it, f"บรรทัด {x['n']} ท่อน {k}") for k, it in enumerate(items, 1)]
        got, want = tight("".join(it[0] + it[1] for it in items)), tight(render.unbreak(s["text"]))
        if got != want:
            raise VideoEditError(f"บรรทัด {x['n']}: lead + punch ต้องเป็นคำพูดเดิมครบทุกตัวอักษรตามลำดับ\n"
                                 f"  ซับ: {want}\n  ได้: {got}")
        punch[s["text"]] = items
    hook = ans.get("hook")
    if not isinstance(hook, list) or not 1 <= len(hook) <= 2 or any(
            not isinstance(h, dict) or not str(h.get("text", "")).strip() or h.get("color") not in render.HOOK_COLORS for h in hook):
        raise VideoEditError('hook (HL Hook) ต้องเป็น 1-2 บรรทัด [{"text": "...", "color": "white|orange|red"}]')
    lang = _caption_lang(path)
    caption = None
    if lang:
        cap = ans.get("caption")
        if not isinstance(cap, dict) or any(not isinstance(cap.get(str(n)), str) or not cap[str(n)].strip()
                                            for n in range(1, len(subs) + 1) if n not in cut):
            raise VideoEditError(f'preset นี้มีซับแปล ({lang}): caption ต้องเป็น {{"1": "...", ...}} ครบทุกบรรทัด')
        caption = {s["text"]: cap[str(n)].strip() for n, s in enumerate(subs, 1) if n not in cut}
    motion = ans.get("motion") or []
    if not isinstance(motion, list) or any(not isinstance(m, dict) or m.get("template") not in MOTION
                                           or m.get("n") not in range(1, len(subs) + 1) or m["n"] in cut for m in motion):
        raise VideoEditError(f'motion (Motion text) ต้องเป็น [{{"n": เลขบรรทัด, "template": "{"|".join(sorted(MOTION))}"}}]')

    folder = Path(path)
    written = ["clipkit_punch.json", "clipkit_hook.json"]
    (folder / "clipkit_punch.json").write_text(json.dumps(punch, ensure_ascii=False, indent=1), encoding="utf-8")
    (folder / "clipkit_hook.json").write_text(json.dumps([{"text": h["text"].strip(), "color": h["color"]} for h in hook],
                                                         ensure_ascii=False, indent=1), encoding="utf-8")
    if caption is not None:
        (folder / "clipkit_caption.json").write_text(json.dumps(caption, ensure_ascii=False, indent=1), encoding="utf-8")
        written.append("clipkit_caption.json")
    if cut:  # the footage of each dropped line (up to the next line) goes, its subtitle with it
        ends = [max(s["end"], nxt["start"]) for s, nxt in zip(subs, subs[1:])] + [subs[-1]["end"]]
        capcut_edit.trim_pauses(path, ranges=[(subs[n - 1]["start"], ends[n - 1]) for n in sorted(set(cut))])
        written.append(f"ตัด {len(set(cut))} บรรทัด")
        kept = {s["text"]: s for s in capcut_edit.read_draft(path)["subtitles"]}
        subs = [kept.get(s["text"], s) for s in subs]  # motion goes at the lines' new times
    if motion:
        import video_editor  # renders each motion here, the same as the editor's Motion button
        for m in motion:
            s = subs[m["n"] - 1]
            video_editor.draft_overlay_add(video_editor.OverlayRequest(path=path, template=m["template"],
                                                                       start=s["start"], end=s["end"], text=s["text"]))
        written.append(video_editor.OVERLAYS)
    return {"written": written, "lines": len(punch), "cut": len(set(cut)), "motion": len(motion)}


def import_answer(step: str, target: str, text: str) -> dict[str, Any]:
    ans = parse(text)
    if step == "stories":
        return {"stories": import_stories(target, ans)}
    if step == "clip":
        return import_clip(target, ans)
    raise VideoEditError(f"unknown step: {step}")
