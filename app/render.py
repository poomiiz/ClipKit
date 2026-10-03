"""Export a ClipKit project to MP4 without opening CapCut: the kept pieces of the raw clip joined in timeline
order, on the project's own canvas, with its subtitles drawn in (text, size, colour, outline, place, tilt).

Round 1 covers what ClipKit itself makes: the main video track and the main text track. Extra tracks
(b-roll, music, effects added by hand in CapCut) are reported, not silently dropped.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import capcut_edit
from video_edit import FFMPEG, VideoEditError, probe

US = 1_000_000
CAPCUT_PX = 5.2  # pixels per CapCut font-size unit per 1080 px of the canvas short side (same number the editor preview uses)
FONTS = Path(__file__).resolve().parents[1] / "fonts"
DEFAULT_FONT = FONTS / "Kanit-Bold.ttf"  # Google Fonts, OFL: shipped with ClipKit so Thai always shapes


def _font(path: str | None) -> tuple[str, Path]:
    """(family name, file) for libass: the project's own font when the file exists, else the bundled Kanit."""
    from fontTools.ttLib import TTFont
    f = Path(path) if path and Path(path).is_file() else DEFAULT_FONT
    if not f.is_file():
        raise VideoEditError(f"font file missing: {f}")
    return TTFont(str(f), fontNumber=0)["name"].getDebugName(1), f


def _fit(text: str, font_file: Path, size: float, max_w: float) -> tuple[list[str], float]:
    """Keep a subtitle inside the frame: one line when it fits, else two lines split at the Thai word break
    that balances them best, and only if the longer of the two still overflows, a smaller size."""
    from PIL import ImageFont
    from pythainlp.tokenize import word_tokenize
    font = ImageFont.truetype(str(font_file), 100)
    width = lambda t: font.getlength(t) * size / 100  # noqa: E731
    if "\n" in text:  # the editor already chose the line breaks
        lines = text.split("\n")
    elif width(text) <= max_w:
        return [text], size
    else:
        words = word_tokenize(text, keep_whitespace=True)
        cuts = [("".join(words[:i]).strip(), "".join(words[i:]).strip()) for i in range(1, len(words))]
        lines = list(min(cuts, key=lambda c: max(width(c[0]), width(c[1])))) if cuts else [text]
    widest = max(width(t) for t in lines)
    return lines, size if widest <= max_w else size * max_w / widest


def _ass_color(rgb: list[float]) -> str:
    r, g, b = (max(0, min(255, round(c * 255))) for c in rgb[:3])
    return f"&H00{b:02X}{g:02X}{r:02X}"


def _ts(t: float) -> str:
    cs = max(0, round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def render_draft(path: str, out_dir: str) -> dict[str, Any]:
    folder = Path(path)
    draft = capcut_edit._load(folder)
    index = capcut_edit._index(draft)
    W, H = draft["canvas_config"]["width"], draft["canvas_config"]["height"]
    video = capcut_edit._video_track(draft)
    text = capcut_edit._text_track(draft)
    skipped = sum(1 for t in draft["tracks"] if t is not video and t is not text and t["segments"])

    segs = sorted(video["segments"], key=lambda s: s["target_timerange"]["start"])
    if not segs:
        raise VideoEditError("project has no video on its timeline")
    mats = {m["id"]: m for m in draft["materials"].get("videos", [])}
    src = mats[segs[0]["material_id"]]["path"]
    if any(mats[s["material_id"]]["path"] != src for s in segs):
        raise VideoEditError("main track mixes several source files - round 1 exports one raw clip only")
    if not Path(src).is_file():
        raise VideoEditError(f"raw file not found: {src}")
    info = probe(src)

    # footage placed the way CapCut shows it: fit inside the canvas, then the clip's own scale and offset
    clip = segs[0]["clip"]
    fit = min(W / info["width"], H / info["height"]) * clip["scale"]["x"]
    vw, vh = round(info["width"] * fit / 2) * 2, round(info["height"] * fit / 2) * 2
    ox = round((W - vw) / 2 + clip["transform"]["x"] * W / 2)
    oy = round((H - vh) / 2 - clip["transform"]["y"] * H / 2)

    parts, labels = [], []
    for i, s in enumerate(segs):
        a = s["source_timerange"]["start"] / US
        b = a + s["source_timerange"]["duration"] / US
        parts.append(f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[v{i}];"
                     f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS[a{i}]")
        labels.append(f"[v{i}][a{i}]")
    graph = ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(segs)}:v=1:a=1[vc][ac];" + \
        f"[vc]scale={vw}:{vh}[vs];color=black:s={W}x{H}[bg];[bg][vs]overlay={ox}:{oy}:shortest=1[vo]"

    # subtitles: one ASS event per line, positioned and tilted like the CapCut segment
    events, font_files, family = [], set(), None
    for s in sorted((text or {}).get("segments", []), key=lambda s: s["target_timerange"]["start"]):
        m = index.get(s["material_id"], (None, None))[1]
        if not m:
            continue
        body = json.loads(m["content"])
        st = (body.get("styles") or [{}])[0]
        fam, fdir = _font((st.get("font") or {}).get("path") or m.get("font_path"))
        family = family or fam
        font_files.add(fdir)
        size = (m.get("font_size") or st.get("size") or 15) * CAPCUT_PX * (min(W, H) / 1080) * s["clip"]["scale"]["x"]
        fill = ((st.get("fill") or {}).get("content") or {}).get("solid", {}).get("color", [1, 1, 1])
        strokes = st.get("strokes") or []
        outline = size * strokes[0].get("width", 0) * 0.6 if strokes else 0  # measured by eye against CapCut
        ocol = strokes[0]["content"]["solid"]["color"] if strokes else [0, 0, 0]
        x = W / 2 + s["clip"]["transform"].get("x", 0) * W / 2
        y = H / 2 - s["clip"]["transform"]["y"] * H / 2
        t0 = s["target_timerange"]["start"] / US
        t1 = t0 + s["target_timerange"]["duration"] / US
        lines, size = _fit(body.get("text", ""), fdir, size, W * 0.9)
        words = "\\N".join(lines)
        events.append(f"Dialogue: 0,{_ts(t0)},{_ts(t1)},S,,0,0,0,,{{\\an5\\pos({x:.0f},{y:.0f})\\fn{fam}"
                      f"\\fs{size:.0f}\\frz{-s['clip'].get('rotation', 0):.1f}\\1c{_ass_color(fill)}"
                      f"\\3c{_ass_color(ocol)}\\bord{outline:.1f}}}{words}")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"{folder.name}.mp4"
    with tempfile.TemporaryDirectory() as tmp:
        if events:
            fam0 = family or _font(None)[0]
            (Path(tmp) / "subs.ass").write_text(
                "[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nWrapStyle: 2\n\n"
                "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BorderStyle, Outline, "
                "Shadow, Alignment, Encoding\nStyle: S,%s,60,&H00FFFFFF,&H00000000,1,0,0,5,1\n\n"
                "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n%s\n"
                % (W, H, fam0, "\n".join(events)), encoding="utf-8")
            # relative names + cwd=tmp: no Windows drive-letter escaping inside the filter string;
            # libass reads one fonts folder, so the project's font files and Kanit are copied into it
            import shutil
            fd = Path(tmp) / "fonts"
            fd.mkdir()
            for f in font_files | {DEFAULT_FONT}:
                shutil.copy2(f, fd / f.name)
            graph += ";[vo]ass=subs.ass:fontsdir=fonts[vf]"
            vout = "[vf]"
        else:
            vout = "[vo]"
        # motion clips (transparent MOV) on top, each from its own moment; scaled to the canvas height
        ins = []
        olist = folder / "clipkit_overlays.json"
        for k, o in enumerate(json.loads(olist.read_text(encoding="utf-8")) if olist.is_file() else []):
            if not Path(o["file"]).is_file():
                raise VideoEditError(f"motion file missing: {o['file']}")
            ins += ["-i", o["file"]]
            s0 = float(o["start"])
            graph += (f";[{k + 1}:v]scale=-2:{H},setpts=PTS-STARTPTS+{s0:.3f}/TB[m{k}];"
                      f"{vout}[m{k}]overlay=(W-w)/2:0:eof_action=pass:enable='between(t,{s0:.3f},{s0 + float(o['duration']):.3f})'[o{k}]")
            vout = f"[o{k}]"
        cmd = [FFMPEG, "-y", "-i", src, *ins, "-filter_complex", graph, "-map", vout, "-map", "[ac]",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(target)]
        r = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not target.is_file():
        raise VideoEditError("export failed: " + r.stderr.strip()[-800:])
    return {"file": str(target), "subtitles": len(events), "motions": len(ins) // 2, "pieces": len(segs), "skipped_tracks": skipped,
            "duration": probe(str(target))["duration"]}
