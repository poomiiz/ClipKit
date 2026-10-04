"""A ClipKit project as a HyperFrames composition: what the timeline editor shows live in <hyperframes-player>
and what `hyperframes render` turns into the MP4, so the preview and the file are drawn by the same engine.

Built from the renderer's dry run (cuts, crop, subtitle phrases, b-roll, music, effects, colour) into
<project>/clipkit_hf/index.html. Media is not copied (raw clips can be gigabytes): it is served by this app.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

import render


def _local(out: Path, path: str, name: str | None = None) -> str:
    """A file the composition points at, inside its own folder (the renderer takes only local or https files).
    Small files (b-roll, music, effects, font) are copied once; same name = same file."""
    import shutil
    src = Path(path)
    dst = out / "media" / (name or src.name)
    dst.parent.mkdir(exist_ok=True)
    if not dst.is_file() or dst.stat().st_size != src.stat().st_size:
        shutil.copy2(src, dst)
    return "media/" + quote(dst.name)


def _proxy(out: Path, src: str, a: float, b: float) -> tuple[str, float]:
    """The used stretch of the raw clip as a light H.264 copy (raw files can be 4 GB HEVC that a browser may not
    play): made once per range. Returns (relative src, offset of the copy's 0 inside the raw file)."""
    import subprocess
    a = max(0.0, a - 0.5)
    dst = out / "media" / f"footage_{int(a * 1000)}_{int(b * 1000)}.mp4"
    dst.parent.mkdir(exist_ok=True)
    if not dst.is_file():
        for old in dst.parent.glob("footage_*.mp4"):
            old.unlink()
        r = subprocess.run([render.FFMPEG, "-v", "error", "-y", "-ss", f"{a:.3f}", "-to", f"{b + 0.5:.3f}", "-i", src,
                            "-vf", "scale='min(1920,iw)':-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                            "-g", "15", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(dst)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode or not dst.is_file():
            raise render.VideoEditError("could not prepare the footage: " + r.stderr[-300:])
    return "media/" + dst.name, a


def _css_color(rgb: list[float]) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c * 255))) for c in rgb[:3])


def build(path: str) -> Path:
    t = render.render_draft(path, "", dry=True)
    W, H, D = t["width"], t["height"], t["duration"]
    st = t["style"] or {}
    k = min(W, H) / 1080 * render.CAPCUT_PX
    fit = t["fit"]
    c = st.get("color") or {}
    flt = (f"brightness({1 + float(c.get('brightness', 0)) * 1.6:.3f}) contrast({float(c.get('contrast', 1)):.3f}) "
           f"saturate({float(c.get('saturation', 1)):.3f}) sepia({max(0.0, float(c.get('warmth', 0))) * 0.8:.3f})") if c else "none"
    els, anim = [], []
    n = 0
    out = Path(path) / "clipkit_hf"
    out.mkdir(exist_ok=True)
    segs = t["segments"]
    foot, off = _proxy(out, t["source"], min(x["media_start"] for x in segs), max(x["media_start"] + x["dur"] for x in segs))

    def nid(p: str) -> str:
        nonlocal n
        n += 1
        return f"{p}{n}"

    # the talking footage: one clip per kept piece, placed exactly where the ffmpeg export puts it
    for s in t["segments"]:
        a, d, m = s["start"], s["dur"], s["media_start"]
        els.append(f'<video id="{nid("v")}" class="clip cam" src="{foot}" muted playsinline data-start="{a:.3f}" '
                   f'data-duration="{d:.3f}" data-media-start="{m - off:.3f}" data-track-index="0" style="position:absolute;'
                   f'left:{fit["x"]}px;top:{fit["y"]}px;width:{fit["w"]}px;height:{fit["h"]}px;filter:{flt}"></video>')
        els.append(f'<audio id="{nid("a")}" src="{foot}" data-start="{a:.3f}" data-duration="{d:.3f}" '
                   f'data-media-start="{m - off:.3f}" data-track-index="1" data-volume="1"></audio>')
    # zoom cut: every other subtitle line punched in
    if st.get("zoomcut"):
        lines = sorted({(p["start"], p["end"], p["line"]) for p in t["phrases"]})
        seen = []
        for a, b, line in lines:
            if line not in seen:
                seen.append(line)
                if len(seen) % 2 == 0:
                    anim.append(f'tl.set(".cam",{{scale:1.12}},{a:.3f});tl.set(".cam",{{scale:1}},{b:.3f});')
    # b-roll over the speaker
    for b in t["broll"]:
        if b.get("file"):
            els.append(f'<video id="{nid("b")}" class="clip" src="{_local(out, b["file"])}" muted playsinline data-start="{b["start"]:.3f}" '
                       f'data-duration="{b["dur"]:.3f}" data-media-start="0" data-track-index="2" '
                       f'style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover"></video>')

    def text(words: str, size: float, y: float, fill, stroke, width: float, a: float, b: float, grow: str = "both", floor: float = 0) -> str:
        i = nid("t")
        # same fitting as the ffmpeg export: one line when it fits, two balanced lines, then smaller
        lines, px = render._fit(words, render.DEFAULT_FONT, size * k, W * 0.9)
        # a wrapped lead grows upward and a wrapped punch downward, so the pair never covers each other
        top = H / 2 - y * H / 2 + {"up": px * 0.625, "down": -px * 0.625}.get(grow, 0)
        top = max(top, floor) if grow == "down" else top
        shift = {"up": "-100%", "down": "0"}.get(grow, "-50%")
        tops[i] = top
        els.append(f'<div id="{i}" class="clip txt" data-start="{a:.3f}" data-duration="{max(0.05, b - a):.3f}" data-track-index="3" '
                   f'style="top:{top:.0f}px;transform:translateY({shift});font-size:{px:.0f}px;color:{_css_color(fill)};'
                   f'-webkit-text-stroke:{px * width * 1.2 + 2:.1f}px {_css_color(stroke)}">{"<br>".join(html.escape(x) for x in lines)}</div>')
        return i

    tops: dict[str, float] = {}
    look = t["look"]
    if look in ("pair", "pair-nina"):
        P = render.PAIR["nina" if look == "pair-nina" else "bps"]
        for p in t["phrases"]:
            a, b = p["start"], p["end"]
            lead_id = ""
            if p["lead"]:
                i = lead_id = text(p["lead"], *P["lead"], a, b, "up")
                anim.append(f'tl.fromTo("#{i}",{{opacity:0}},{{opacity:1,duration:0.08}},{a:.3f});')
            if p["punch"]:
                hit = min(b - 0.05, max(a + 0.2, a + 0.6)) if p["lead"] else a
                i = text(p["punch"], *P["punch"], hit, b, "down", tops.get(lead_id, 0) + 8)
                anim.append(f'tl.fromTo("#{i}",{{scale:1.3}},{{scale:1,duration:0.14}},{hit:.3f});')
            if P["caption"]:
                text((p["lead"] + " " + p["punch"]).strip(), *P["caption"], a, b)
    else:
        for p in t["phrases"]:
            i = text(p["lead"], 16, -0.6, [1, 1, 1], [0, 0, 0], 0.08, p["start"], p["end"])
            if look == "pop":
                anim.append(f'tl.fromTo("#{i}",{{scale:0.7}},{{scale:1,duration:0.2,ease:"back.out(2)"}},{p["start"]:.3f});')
    # sound: quiet steady music bed, pops on punches, whooshes as b-roll comes in
    mu = t["music"]
    if mu.get("file"):
        els.append(f'<audio id="{nid("m")}" src="{_local(out, mu["file"])}" data-start="0" data-duration="{D:.3f}" '
                   f'data-media-start="0" data-track-index="4" data-volume="{mu["volume"]}"></audio>')
    fx = t["sfx"]
    if fx.get("on"):
        for tp in t["pops"]:
            els.append(f'<audio id="{nid("s")}" src="{_local(out, render._sfx("pop"))}" data-start="{tp:.3f}" data-duration="0.2" '
                       f'data-track-index="5" data-volume="{0.5 * fx["volume"]:.2f}"></audio>')
        for b in t["broll"]:
            if b.get("file"):
                els.append(f'<audio id="{nid("s")}" src="{_local(out, render._sfx("whoosh"))}" data-start="{max(0, b["start"] - 0.15):.3f}" '
                           f'data-duration="0.5" data-track-index="5" data-volume="{0.35 * fx["volume"]:.2f}"></audio>')
    font = _local(out, render.DEFAULT_FONT)
    # the HyperFrames runtime (clip windows, media sync, seeking) for the live player; the renderer brings its own
    runtime = _local(out, str(Path(__file__).with_name("hyperframe.runtime.iife.js")))
    page = f"""<!doctype html>
<html lang="th"><head><meta charset="UTF-8"><meta name="viewport" content="width={W}, height={H}">
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<script src="{runtime}"></script>
<style>
@font-face{{font-family:"ClipKit Thai";src:url("{font}")}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px;overflow:hidden;background:#000}}
.cam{{transform-origin:{W / 2 - fit["x"]}px {H / 2 - fit["y"]}px}}
.txt{{position:absolute;left:5%;width:90%;white-space:nowrap;transform:translateY(-50%);text-align:center;font-family:"ClipKit Thai",sans-serif;
  font-weight:700;line-height:1.25;paint-order:stroke fill;text-shadow:0 3px 8px rgba(0,0,0,.45)}}
</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{D:.3f}" data-width="{W}" data-height="{H}">
{chr(10).join(els)}
</div>
<script>
const tl = gsap.timeline({{paused: true}});
{chr(10).join(anim)}
window.__timelines = window.__timelines || {{}};
window.__timelines["main"] = tl;
</script>
</body></html>
"""
    (out / "index.html").write_text(page, encoding="utf-8")
    if not (out / "hyperframes.json").is_file():
        (out / "hyperframes.json").write_text(json.dumps({"name": Path(path).name}), encoding="utf-8")
    return out / "index.html"
