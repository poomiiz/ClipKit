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


def _json(path: Path, empty: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else empty


def _clock(spoken: list | None, length: float):
    """Seconds into the line at a fraction of its text: from the heard words' times, else evenly by letters."""
    if not spoken:
        return lambda f: f * length
    marks, n, acc = [], sum(len(w) for _, _, w in spoken) or 1, 0
    for a, _, w in spoken:
        marks.append((acc / n, a))
        acc += len(w)
    marks.append((1.0, spoken[-1][1]))
    return lambda f: next((t for p, t in reversed(marks) if p <= f), 0.0)


# the sentence-pair look measured from P'Ohm's own CapCut edits (BPS3 01/07, Nina 02/08): each spoken phrase
# becomes a short white lead line plus a bigger coloured punch line; Nina adds a small full caption at the bottom
PAIR = {
    "bps": {"lead": (25, -0.37, [1, 1, 1], [0, 0, 0], 0.03), "punch": (30, -0.50, [0.02, 0.07, 0.57], [1, 1, 1], 0.08),
            "caption": None},
    "nina": {"lead": (25, -0.29, [1, 1, 1], [0, 0, 0], 0.05), "punch": (30, -0.44, [1, 0.49, 0], [0, 0, 0], 0.06),
             "caption": (8, -0.80, [1, 1, 1], [0, 0, 0], 0.08)},
}


JOINERS = {"แต่", "และ", "ก็", "คือ", "เพราะ", "ซึ่ง", "แล้วก็", "หรือ", "ถ้า", "เลยทำให้", "ดังนั้น", "ส่วน"}


def _pair(text: str, spoken: list | None, t0: float, t1: float, W: int, H: int, fam: str, font_file: Path,
          preset: str, picked: list | None = None, max_chars: int = 16) -> list[str]:
    """Split a spoken line into phrases of about two seconds, each shown as lead + punch.
    picked = the agent's [[lead, punch], ...] for this line (the words that carry the point); without it the
    phrases break at breaths / ~16 letters / Thai joining words and the punch is the phrase's last words."""
    from pythainlp.tokenize import word_tokenize
    look = PAIR[preset]
    flat = text.replace("\n", " ")
    at, total = _clock(spoken, t1 - t0), len(flat) or 1
    phrases = []  # (lead, punch, start, punch time, last word time)
    if picked:
        tight = lambda t: "".join(t.split())  # noqa: E731  (spaces may be dropped, nothing else)
        if tight("".join(a + b for a, b in picked)) != tight(flat):
            raise VideoEditError(f"clipkit_punch.json does not match the subtitle line: {flat}")
        # time of a position in the line, counting letters only (the agent may have dropped spaces)
        letters = [i for i, c in enumerate(flat) if not c.isspace()]
        when = lambda n: t0 + at(letters[min(n, len(letters) - 1)] / total)  # noqa: E731
        n = 0
        for lead, punch in picked:
            a, hit = when(n), when(n + len(tight(lead)))
            n += len(tight(lead)) + len(tight(punch))
            phrases.append((lead.strip(), punch.strip(), a, hit, when(n - 1)))
    else:
        timed, pos = [], 0
        for tok in word_tokenize(flat, keep_whitespace=True):
            timed.append((tok, t0 + at(pos / total)))
            pos += len(tok)
        chunks, cur = [], []
        for k, (tok, t) in enumerate(timed):
            gap = k and tok.strip() and t - timed[k - 1][1] > 0.6
            joiner = tok.strip() in JOINERS and sum(len(x) for x, _ in cur) >= 6  # a new thought starts here
            if cur and (gap or joiner or sum(len(x) for x, _ in cur) >= max_chars):
                chunks.append(cur)
                cur = []
            cur.append((tok, t))
        if cur:
            chunks.append(cur)
        for ch in chunks:
            words = [x for x, _ in ch]
            real = [i for i, w in enumerate(words) if w.strip()]
            if not real:
                continue
            # punch = trailing words worth ~40% of the letters (at least one word); lead = the rest
            cut, acc, size = real[-1], 0, sum(len(w) for w in words)
            for i in reversed(real):
                acc += len(words[i])
                cut = i
                if acc >= size * 0.4:
                    break
            phrases.append(("".join(words[:cut]).strip(), "".join(words[cut:]).strip(), ch[0][1], ch[cut][1], ch[-1][1]))
    k = min(W, H) / 1080 * CAPCUT_PX

    def line(words: str, part: tuple, a: float, b: float, extra: str = "") -> str:
        size, y, fill, stroke, width = part
        px = size * k
        lines, px = _fit(words, font_file, px, W * 0.9)
        return (f"Dialogue: 0,{_ts(a)},{_ts(b)},S,,0,0,0,,{{\\an5\\pos({W / 2:.0f},{H / 2 - y * H / 2:.0f})\\fn{fam}"
                f"\\fs{px:.0f}\\1c{_ass_color(fill)}\\3c{_ass_color(stroke)}\\bord{px * width * 0.6 + 2:.1f}"
                f"\\shad2{extra}}}" + "\\N".join(lines))

    out = []
    for n, (lead, punch, a, hit, last) in enumerate(phrases):
        # stays until the next phrase, but not through a long pause after its last word
        b = min(phrases[n + 1][2] if n + 1 < len(phrases) else t1, last + 1.5)
        # the punch lands when it is said, but never leaves the lead alone on screen for long (slow talkers)
        hit = min(b - 0.05, max(a + 0.2, min(hit, a + 0.6)))
        if lead:
            out.append(line(lead, look["lead"], a, b, "\\fad(80,0)"))
        if punch:
            out.append(line(punch, look["punch"], hit if lead else a, b, "\\fscx130\\fscy130\\t(0,140,\\fscx100\\fscy100)"))
        if look["caption"]:
            out.append(line((lead + " " + punch).strip(), look["caption"], a, b))
    return out


def _karaoke(lines: list[str], spoken: list | None, length: float, base: str, hl: str) -> list[tuple[float, float, str]]:
    """The whole line shows; the word being said turns the highlight colour, then back.
    Returned as back-to-back pieces (start, end, text in seconds from the line start), one per word, each with
    plain colour switches: libass chains two \\t colour changes on one word wrongly (unsaid words lit up).
    Word times come from the speech model (relative to the line start); the shown words can differ from the
    heard ones (fixed typos, English terms), so they are matched by position in the text, not by spelling."""
    from pythainlp.tokenize import word_tokenize
    total = sum(len(t) for t in lines) or 1
    at = _clock(spoken, length)
    toks, pos = [], 0  # (line no, text, start, end)
    for li, line in enumerate(lines):
        for tok in word_tokenize(line, keep_whitespace=True):
            a = at(pos / total)
            pos += len(tok)
            toks.append((li, tok, a, max(a + 0.08, at(pos / total))))

    def text(lit: int) -> str:
        parts = []
        for k, (li, tok, _, _) in enumerate(toks):
            if k and li != toks[k - 1][0]:
                parts.append("\\N")
            parts.append(f"{{\\1c{hl}}}{tok}{{\\1c{base}}}" if k == lit and tok.strip() else tok)
        return "".join(parts)

    words = [k for k, t in enumerate(toks) if t[1].strip()]
    if not words:
        return [(0.0, length, text(-1))]
    out = [(0.0, toks[words[0]][2], text(-1))]
    for n, k in enumerate(words):
        end = toks[words[n + 1]][2] if n + 1 < len(words) else toks[k][3]
        out.append((toks[k][2], end, text(k)))
    out.append((toks[words[-1]][3], length, text(-1)))
    return [(a, min(b, length), t) for a, b, t in out if min(b, length) - a > 0.005]


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
        f"[vc]scale={vw}:{vh}[vs];color=black:s={W}x{H}:r={info.get("fps") or 30}[bg];[bg][vs]overlay={ox}:{oy}:shortest=1[vo]"

    # subtitles: one ASS event per line, positioned and tilted like the CapCut segment
    events, font_files, family = [], set(), None
    olist = folder / "clipkit_overlays.json"
    overlays = json.loads(olist.read_text(encoding="utf-8")) if olist.is_file() else []
    # subtitle look chosen in the editor: none (still), pop (bounce in), karaoke (the spoken word lights up)
    style = _json(folder / "clipkit_style.json", {})
    anim, highlight = style.get("anim", "none"), style.get("highlight", [1, 0.83, 0])
    said = _json(folder / "clipkit_words.json", {})
    punches = _json(folder / "clipkit_punch.json", {})  # punch words picked by the agent (ClipKit: เลือกคำเน้น)
    shown = 0
    estimated = 0  # lines with no word times (typed by hand, or English): highlight paced by letters instead
    for s in sorted((text or {}).get("segments", []), key=lambda s: s["target_timerange"]["start"]):
        m = index.get(s["material_id"], (None, None))[1]
        if not m:
            continue
        at = s["target_timerange"]["start"] / US
        if any(o["start"] - 0.05 <= at < o["start"] + o["duration"] for o in overlays):
            continue  # a motion shows this line's words already: no second copy as a subtitle
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
        if anim in ("pair", "pair-nina"):
            spoken = said.get(body.get("text", ""))
            estimated += spoken is None
            events += _pair(body.get("text", ""), spoken, t0, t1, W, H, fam, fdir,
                            "nina" if anim == "pair-nina" else "bps", punches.get(body.get("text", "")))
            shown += 1
            continue
        lines, size = _fit(body.get("text", ""), fdir, size, W * 0.9)
        if anim == "karaoke":
            spoken = said.get(body.get("text", ""))
            estimated += spoken is None
            pieces = [(t0 + a, t0 + b, w) for a, b, w in
                      _karaoke(lines, spoken, t1 - t0, _ass_color(fill), _ass_color(highlight))]
        else:
            pieces = [(t0, t1, "\\N".join(lines))]
        shown += 1
        pop = "\\fscx70\\fscy70\\t(0,120,\\fscx108\\fscy108)\\t(120,200,\\fscx100\\fscy100)" if anim == "pop" else ""
        for a, b, words in pieces:
            events.append(f"Dialogue: 0,{_ts(a)},{_ts(b)},S,,0,0,0,,{{\\an5\\pos({x:.0f},{y:.0f})\\fn{fam}"
                          f"\\fs{size:.0f}\\frz{-s['clip'].get('rotation', 0):.1f}\\1c{_ass_color(fill)}"
                          f"\\3c{_ass_color(ocol)}\\bord{outline:.1f}{pop}}}{words}")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"{folder.name}.mp4"
    with tempfile.TemporaryDirectory() as tmp:
        base = "[vo]"
        if style.get("zoomcut"):
            # jump-cut feel without new footage: every other subtitle line plays punched in (112%), a hard cut each time
            beats = sorted((s["target_timerange"]["start"] / US, (s["target_timerange"]["start"] + s["target_timerange"]["duration"]) / US)
                           for s in (text or {}).get("segments", []))
            zin = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in beats[1::2]) or "0"
            # a zoomed copy laid over the plain one only during those lines (zoompan dropped frames: 60 s -> 25 s)
            zw, zh = round(W * 1.12 / 2) * 2, round(H * 1.12 / 2) * 2
            graph += (f";[vo]split[zp][zq];[zq]scale={zw}:{zh},crop={W}:{H}[zz];"
                      f"[zp][zz]overlay=0:0:enable='{zin}'[vz]")
            base = "[vz]"
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
            graph += f";{base}ass=subs.ass:fontsdir=fonts[vf]"
            vout = "[vf]"
        else:
            vout = base
        # motion clips (transparent MOV) on top, each from its own moment; scaled to the canvas height
        ins = []
        for k, o in enumerate(overlays):
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
    return {"file": str(target), "subtitles": shown, "motions": len(ins) // 2, "sub_anim": anim,
            "karaoke_estimated": estimated, "pieces": len(segs), "skipped_tracks": skipped,
            "duration": probe(str(target))["duration"]}
