"""Web AI: ClipKit's two judgement steps (split into stories; subtitles, emphasis, title, motion per clip) done by
an AI in the browser (claude.ai, ChatGPT...) instead of an agent on this machine.

export_*() writes one text file to upload: the prompt plus the transcript and timings, never the video. The AI
answers with one JSON (schema: prompts/web_ai/schema.md); import_answer() checks it and writes the same files the
local agent writes (<video>.stories.json, clipkit_punch.json, clipkit_hook.json, clipkit_caption.json, motion), so
run_clip / the editor carry on as before and the CapCut project is built here from this machine's own media.
The same file works for an AI on this machine: it saves the JSON to answer_file() and the editor imports it.
"""
from __future__ import annotations

import atomic
import json
import cue_data
import math
import re
import time
from pathlib import Path
from typing import Any

import capcut_edit
import render
import video_edit
from video_edit import VideoEditError

VERSION = 1
PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
LOOKS = {"pair", "white", "color", "red", "hold", "skip"}


def _motion_menu() -> list[dict[str, Any]]:
    """Every motion/<name> template the AI may place: name, label, role and its fields (quick ones need none)."""
    import kit_settings
    import video_editor
    return [{"template": k, "label": v.get("label", k), "role": v.get("role", ""),
             **({} if k in video_editor.QUICK_MOTION else {"params": {
                 f["key"] + ("" if f.get("required") else "?"): f["type"] if f["type"] != "select" else [o[0] for o in f["options"]]
                 for f in v.get("fields", []) if f["type"] not in ("font",)}})}
            for k, v in kit_settings.motion_templates().items()]


def _prompt(name: str) -> str:
    bare = lambda f: re.sub(r"<!--.*?-->\s*", "", f.read_text(encoding="utf-8"), flags=re.S).strip()  # noqa: E731
    return bare(PROMPTS / "web_ai" / name).replace("{STORY_RULES}", bare(PROMPTS / "story_split.md"))


def packet_file(step: str, target: str) -> Path:
    return (Path(target).with_name(Path(target).name + ".web-ai-stories.md") if step == "stories"
            else Path(target) / "clipkit_web_ai.md")


def answer_file(step: str, target: str) -> Path:
    """Where an AI on this machine (Claude Code...) saves its answer instead of replying in chat."""
    return packet_file(step, target).with_suffix(".answer.json")


def _packet(prompt: str, data: dict[str, Any], out: Path) -> Path:
    ans = out.with_suffix(".answer.json")
    ans.unlink(missing_ok=True)  # an answer to an older export must not be imported for this one
    atomic.write_text(out, "# คำสั่งสำหรับ AI: ทำงานจากไฟล์แนบนี้ได้ทันที\n\n"
                   "> ใช้ AI บนเว็บได้โดยไม่ต้องติดตั้ง agent: อ่านคำสั่งและข้อมูลทั้งหมดในไฟล์นี้ "
                   "ทำงานตามขั้นที่ระบุ แล้วตอบ JSON ตามรูปแบบด้านล่าง ผู้ใช้ไม่ต้องพิมพ์ prompt เพิ่ม "
                   "และจะนำคำตอบกลับไปวางใน EditorKrab\n\n"
                   f"> ทางเลือกสำหรับ AI ที่เขียนไฟล์ในเครื่องได้: บันทึก JSON ลง `{ans}` แล้ว EditorKrab จะนำเข้าเอง\n\n"
                   + prompt.rstrip() + "\n\n## ข้อมูล (อย่าแก้ช่อง clipkit_web_ai, step, video, project)\n\n```json\n"
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


def story_target(video: str) -> float | None:
    path = Path(video + ".story-preferences.json")
    value = json.loads(path.read_text(encoding="utf-8")).get("max_minutes") if path.is_file() else None
    return _target_minutes(value)


def has_story_target(video: str) -> bool:
    return Path(video + ".story-preferences.json").is_file()


def _target_minutes(value: float | None) -> float | None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0):
        raise VideoEditError("ความยาวต้องเป็นจำนวนนาทีที่มากกว่า 0")
    return value


def save_story_target(video: str, value: float | None) -> bool:
    value = _target_minutes(value)
    changed = not has_story_target(video) or story_target(video) != value
    if changed:
        answer = answer_file("stories", video)
        if answer.is_file():
            answer.replace(answer.with_name(answer.name + f".before-target-{time.time_ns()}"))
        stories = video_edit.stories_file(video)
        if stories.is_file():
            stories.replace(stories.with_name(stories.name + f".before-target-{time.time_ns()}"))
        atomic.write_text(Path(video + ".story-preferences.json"), json.dumps({"max_minutes": value}), encoding="utf-8")
    return changed


def export_stories(video: str, max_minutes: float | None = None) -> Path:
    if max_minutes is not None or not has_story_target(video):
        save_story_target(video, max_minutes)
    max_minutes = story_target(video)
    tf = video_edit.transcript_file(video)
    if not tf.is_file():
        raise VideoEditError(f"ยังไม่ได้ถอดเสียง: ไม่มี {tf.name} (กด ถอดเสียงและแบ่งเรื่อง ก่อน)")
    lines = [{"start": round(p["start"], 2), "end": round(p["end"], 2), "text": p["text"]}
             for p in json.loads(tf.read_text(encoding="utf-8"))]
    data = {"clipkit_web_ai": VERSION, "step": "stories", "video": Path(video).name, "max_minutes": max_minutes, "lines": lines}
    prompt, brief = _prompt("stories.md"), video_edit.read_brief(video)
    if brief:  # the person's own words go first, so the AI picks stories for them
        prompt = (f"## ความต้องการของผู้ตัดต่อ\n\n{brief}\n\nเลือกและแบ่งเรื่องให้ตรงกับความต้องการนี้ "
                  f"โดยยังทำตามกฎทุกข้อด้านล่าง\n\n" + prompt)
    if max_minutes is not None:
        prompt = (f"## ความยาวเป้าหมาย\n\nเลือกเนื้อหาให้แต่ละคลิปยาวราว {max_minutes:g} นาที "
                  "เริ่มและจบให้ครบประเด็น สั้นกว่าได้หรือยาวกว่าเล็กน้อย ไม่ใช่เพดานตายตัว "
                  "อย่าตัดประโยคหรือเติมเนื้อหาเพื่อให้ครบเวลา\n\n" + prompt)
    else:
        prompt = "ความยาว: ตามเนื้อหา ผู้ใช้เลือกแล้ว ไม่ต้องถามเพิ่ม เลือกช่วงที่จบครบประเด็น\n\n" + prompt
    return _packet(prompt, data, packet_file("stories", video))


def export_clip(path: str, max_minutes: float | None = None) -> Path:
    """max_minutes: about how long the person wants the clip; a rough aim for the cut, not a hard limit."""
    if max_minutes is None:
        meta = Path(path) / "clipkit.json"
        raw = json.loads(meta.read_text(encoding="utf-8")).get("raw") if meta.is_file() else None
        max_minutes = story_target(raw) if raw else None
    max_minutes = _target_minutes(max_minutes)
    subs = capcut_edit.read_draft(path)["subtitles"]
    if not subs:
        raise VideoEditError("ยังไม่มีซับ — ถอดเสียงก่อน")
    lines = [s["text"] for s in subs]
    words_file = Path(path) / "clipkit_words.json"
    word_times = cue_data.load(path, "clipkit_words.json", subs)
    atomic.write_text((Path(path) / "clipkit_lines.json"), json.dumps(lines, ensure_ascii=False, indent=1), encoding="utf-8")
    data = {"clipkit_web_ai": VERSION, "step": "clip", "project": Path(path).name, "max_minutes": max_minutes, "caption_language": _caption_lang(path),
            "lines": [{"n": n, "cue_id": s["id"], "start": s["start"], "end": s["end"], "text": s["text"],
                       "words": [{"start": round(s["start"] + a, 3), "end": round(s["start"] + b, 3), "text": w}
                                 for a, b, w in word_times.get(cue_data.key(s["id"]), [])]} for n, s in enumerate(subs, 1)],
            "motion_templates": _motion_menu()}
    style = render._json(Path(path) / "clipkit_style.json", {})
    look = render.pair_look(style)
    data["subtitle_layout"] = {"fixed_size": look["fixed_size"], "normal_size": look["lead"][0],
                               "emphasis_size": look["punch"][0], "normal_y": look["lead"][1],
                               "emphasis_y": look["punch"][1]}
    prompt = _prompt("clip.md")
    if max_minutes:
        prompt = prompt.replace("## 1. Subtitle", f"ผู้ตัดต่ออยากได้คลิปยาวราว {max_minutes:g} นาที (คลิปตอนนี้ยาว "
                                f"{subs[-1]['end'] / 60:.1f} นาที): ตัดพูดซ้ำ พูดผิด ออกนอกเรื่องก่อน ถ้ายังยาวกว่ามาก ให้ตัดบรรทัดที่เป็น"
                                "รายละเอียดรองที่ตัดแล้วยังเล่าต่อกันรู้เรื่อง คุมคร่าวๆ เกินได้บ้าง อย่าตัดใจความจนเรื่องขาด\n\n## 1. Subtitle", 1)
    return _packet(prompt, data, packet_file("clip", path))


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
    out = video_edit.validate_stories(ans.get("stories"), phrases)
    atomic.write_text(video_edit.stories_file(video), json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
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
    if any(x.get("cue_id", s["id"]) != s["id"] for x, s in zip(lines, subs)):
        raise VideoEditError("cue ID ไม่ตรงกับซับล่าสุด · ส่งออกคำสั่ง AI ใหม่")
    cut = ans.get("cut") or []
    if not isinstance(cut, list) or any(n not in range(1, len(subs) + 1) for n in cut) or len(set(cut)) >= len(subs):
        raise VideoEditError(f"cut ต้องเป็นรายการเลขบรรทัด 1..{len(subs)} ที่จะตัดทิ้ง และต้องเหลืออย่างน้อย 1 บรรทัด")
    groups, continuation = [], set()
    for x in lines:
        if x["n"] in continuation:
            if set(x) - {"n", "cue_id"}:
                raise VideoEditError("บรรทัดต่อของกลุ่มต้องมีแค่ n และ cue_id")
            continue
        last = x.get("through", x["n"])
        if isinstance(last, bool) or not isinstance(last, int) or not x["n"] <= last <= len(subs):
            raise VideoEditError("through ต้องเป็นเลขบรรทัดสุดท้ายของกลุ่มต่อเนื่อง")
        if last > x["n"]:
            if any(n in cut for n in range(x["n"], last + 1)):
                raise VideoEditError("กลุ่มซับห้ามทับบรรทัดที่ตัด")
            groups.append((x["n"], last))
            continuation.update(range(x["n"] + 1, last + 1))
    merged = capcut_edit.merge_subtitles(path, groups, dry=True) if groups else [
        {**s, "n": n} for n, s in enumerate(subs, 1)]
    punch = {}
    for s in merged:
        x = lines[s["n"] - 1]
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
        if groups:
            render._pair(s["text"], s["words"], s["start"], s["end"], 1080, 1920, "Kanit",
                         render.DEFAULT_FONT, render.pair_look({}), picked=items)
        if x.get("cue_id") is not None and x["cue_id"] != s["id"]:
            raise VideoEditError("cue ID ไม่ตรงกับซับล่าสุด · ส่งออกคำสั่ง AI ใหม่")
        punch[cue_data.key(s["id"])] = items
    hook = ans.get("hook", [])
    if not isinstance(hook, list) or len(hook) > 2 or any(
            not isinstance(h, dict) or not str(h.get("text", "")).strip() or h.get("color") not in render.HOOK_COLORS for h in hook):
        raise VideoEditError('hook ต้องเป็น [] หรือ 1-2 บรรทัด [{"text": "...", "color": "white|orange|red"}]')
    lang = _caption_lang(path)
    caption = None
    if lang:
        cap = ans.get("caption")
        if not isinstance(cap, dict) or any(not isinstance(cap.get(str(n)), str) or not cap[str(n)].strip()
                                            for n in range(1, len(subs) + 1) if n not in cut and n not in continuation):
            raise VideoEditError(f'preset นี้มีซับแปล ({lang}): caption ต้องเป็น {{"1": "...", ...}} ครบทุกบรรทัด')
        caption = {cue_data.key(s["id"]): cap[str(s["n"])].strip() for s in merged if s["n"] not in cut}
    motion = ans.get("motion") or []
    import video_editor
    quick = video_editor.QUICK_MOTION
    if not isinstance(motion, list) or any(not isinstance(m, dict) or m.get("n") not in range(1, len(subs) + 1)
                                           or m["n"] in cut or m["n"] in continuation for m in motion):
        raise VideoEditError('motion ต้องเป็น [{"n": เลขบรรทัด, "template": "...", "params": {...}}]')
    for m in motion:  # checked before anything is written; params only for templates not made from the line
        if m.get("params") is not None:
            video_editor.motion_params(m.get("template"), m["params"], 3.0)
        elif m.get("template") not in quick:
            raise VideoEditError(f'motion บรรทัด {m["n"]}: "{m.get("template")}" ต้องมี params (ช่องตาม motion_templates)')

    folder = Path(path)
    if groups:
        if cut:
            ends = [max(s["end"], nxt["start"]) for s, nxt in zip(subs, subs[1:])] + [subs[-1]["end"]]
            capcut_edit.trim_pauses(path, ranges=[(subs[n - 1]["start"], ends[n - 1]) for n in sorted(set(cut))])
        shifted = lambda n: n - sum(k < n for k in set(cut))
        grouped = capcut_edit.merge_subtitles(path, [(shifted(a), shifted(b)) for a, b in groups])
        current = dict(zip([s["n"] for s in merged if s["n"] not in cut], grouped))
    written = ["clipkit_punch.json", "clipkit_hook.json"]
    if groups:
        written.append("merge_subs")
    cue_data.save(folder, "clipkit_punch.json", punch)
    atomic.write_text((folder / "clipkit_hook.json"), json.dumps([{"text": h["text"].strip(), "color": h["color"]} for h in hook],
                                                         ensure_ascii=False, indent=1), encoding="utf-8")
    if caption is not None:
        cue_data.save(folder, "clipkit_caption.json", caption)
        written.append("clipkit_caption.json")
    if cut and not groups:  # the footage of each dropped line (up to the next line) goes, its subtitle with it
        ends = [max(s["end"], nxt["start"]) for s, nxt in zip(subs, subs[1:])] + [subs[-1]["end"]]
        capcut_edit.trim_pauses(path, ranges=[(subs[n - 1]["start"], ends[n - 1]) for n in sorted(set(cut))])
        written.append(f"ตัด {len(set(cut))} บรรทัด")
        kept = {s["id"]: s for s in capcut_edit.read_draft(path)["subtitles"]}
        subs = [kept.get(s["id"], s) for s in subs]
    if motion:  # renders each motion here, the same as the editor's Motion button
        for m in motion:
            s = current[m["n"]] if groups else subs[m["n"] - 1]
            video_editor.draft_overlay_add(video_editor.OverlayRequest(path=path, template=m["template"], params=m.get("params"),
                                                                       start=s["start"], end=s["end"], text=s["text"], cue_id=s["id"]))
        written.append(video_editor.OVERLAYS)
    out = {"written": written, "lines": len(punch), "cut": len(set(cut)), "motion": len(motion)}
    return out


def import_answer(step: str, target: str, text: str) -> dict[str, Any]:
    """text = the pasted answer; empty = the answer file an AI on this machine saved ({"waiting": True} until then)."""
    if step not in ("stories", "clip"):
        raise VideoEditError(f"unknown step: {step}")
    saved = answer_file(step, target) if not text.strip() else None
    if saved and not saved.is_file():
        return {"waiting": True}
    ans = parse(saved.read_text(encoding="utf-8-sig") if saved else text)
    out = {"stories": import_stories(target, ans)} if step == "stories" else import_clip(target, ans)
    if saved:
        saved.unlink()  # imported once: a clip answer cuts footage, so it must never run twice
    return out
