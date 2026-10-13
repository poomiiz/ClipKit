"""EditorKrab promo: a 33 s vertical motion graphic drawn frame by frame with Pillow, encoded with ffmpeg.

    python scripts/make_promo.py docs/brand/promo.mp4          # the video (silent, with English captions)
    python scripts/make_promo.py stills 2.5,16,31              # stills_<t>.png to check single moments
The voice-over lines and their times are LINES below; docs/brand/promo-voiceover.md has them for recording."""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, FPS, DUR = 1080, 1920, 30, 33.3
NAVY, CORAL, CREAM, GREY, CARD = (23, 36, 59), (255, 120, 92), (247, 245, 239), (185, 194, 214), (34, 50, 79)
REPO = Path(__file__).resolve().parents[1]
F = lambda s: ImageFont.truetype(f"{REPO}/fonts/Kanit-Bold.ttf", s)  # noqa: E731
ICON = Image.open(f"{REPO}/docs/brand/icon-512.png").convert("RGBA")
EMO = {c: Image.open(f"{REPO}/emoji/{c}.png").convert("RGBA") for c in ("1f525", "23f0", "1f4a1", "2705")}

LINES = [
    (0.3, 4.3, "One long video. Hours of editing."),
    (4.6, 8.4, "Meet EditorKrab. It turns long videos into ready-to-post shorts."),
    (8.6, 13.4, "Drop in your video, and tell it what you want."),
    (13.6, 18.4, "It transcribes the speech and splits it into stories."),
    (18.6, 24.8, "One click adds subtitles, zoom cuts, emoji and music."),
    (25.0, 28.8, "Export an MP4, or keep editing in CapCut."),
    (29.0, 33.0, "EditorKrab. Edit less, post more. Free on GitHub."),
]
SCENES = [(0, 4.5), (4.5, 8.5), (8.5, 13.5), (13.5, 18.5), (18.5, 25), (25, 29), (29, 33.3)]


def clamp(x):
    return max(0.0, min(1.0, x))


def ease(x):  # ease-out cubic
    x = clamp(x)
    return 1 - (1 - x) ** 3


def back(x, s=2.0):  # overshoot
    x = clamp(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def p(t, a, d):
    return clamp((t - a) / d)


def text(img, xy, s, size, fill=CREAM, alpha=1.0, anchor="mm", scale=1.0, stroke=0):
    if alpha <= 0 or scale <= 0.01:
        return
    f = F(max(1, int(size * scale)))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.multiline_text(xy, s, font=f, fill=fill + (int(255 * alpha),), anchor=anchor, align="center", spacing=int(size * 0.15),
                     stroke_width=stroke, stroke_fill=(0, 0, 0, int(255 * alpha)))
    img.alpha_composite(layer)


def paste(img, src, cx, cy, size, alpha=1.0, rot=0):
    if alpha <= 0 or size < 2:
        return
    im = src.resize((int(size), int(size)), Image.LANCZOS)
    if rot:
        im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 1:
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    img.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def rect(img, box, fill, r=30, alpha=1.0, outline=None, width=0):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(box, r, fill=fill + (int(255 * alpha),) if fill else None,
                        outline=outline + (int(255 * alpha),) if outline else None, width=width)
    img.alpha_composite(layer)


def wordmark(img, y, size, alpha=1.0):
    f = F(size)
    a, b = f.getlength("Editor"), f.getlength("Krab")
    x = W / 2 - (a + b) / 2
    text(img, (x, y), "Editor", size, alpha=alpha, anchor="lm")
    text(img, (x + a, y), "Krab", size, fill=CORAL, alpha=alpha, anchor="lm")


def scene_alpha(t, a, b):
    return min(p(t, a, 0.3), 1 - p(t, b - 0.3, 0.3))


def frame(t):
    img = Image.new("RGBA", (W, H), NAVY + (255,))
    # 1: one long video = hours of editing
    a = scene_alpha(t, *SCENES[0])
    if a > 0:
        text(img, (W / 2, 700 - 60 * (1 - ease(p(t, 0.1, 0.4)))), "1 long video", 64, alpha=a * ease(p(t, 0.1, 0.4)))
        w = 960 * ease(p(t, 0.4, 1.4))
        if w > 2:
            rect(img, (60, 790, 60 + w, 910), CORAL, 24, a)
            for x in range(120, int(60 + w), 64):
                rect(img, (x, 790, x + 4, 910), (255, 154, 133), 0, a)
        s = back(p(t, 2.0, 0.45))
        text(img, (W / 2, 1120), "= hours of", 118, alpha=a * clamp(s), scale=s)
        text(img, (W / 2 - 60, 1250), "editing", 118, fill=CORAL, alpha=a * clamp(s), scale=s)
        paste(img, EMO["23f0"], W / 2 + 280, 1250, 120 * s, a * clamp(s))
    # 2: logo
    a = scene_alpha(t, *SCENES[1])
    if a > 0:
        s = back(p(t, 4.6, 0.6), 2.2)
        paste(img, ICON, W / 2, 720, 380 * s, a, rot=-25 * (1 - clamp(s)))
        k = ease(p(t, 5.1, 0.45))
        wordmark(img, 1080 + 80 * (1 - k), 118, a * k)
        text(img, (W / 2, 1210), "long videos → ready-to-post shorts", 44, fill=GREY, alpha=a * p(t, 5.7, 0.4))
    # 3: drop a video and say what you want
    a = scene_alpha(t, *SCENES[2])
    if a > 0:
        text(img, (W / 2, 470), "STEP 1", 42, fill=CORAL, alpha=a)
        hit = p(t, 9.5, 0.2)
        rect(img, (130, 540, 950, 1060), CARD, 34, a, outline=CORAL if hit else (51, 71, 107), width=5)
        text(img, (W / 2, 800), "Drop your video here", 44, fill=GREY, alpha=a * (1 - p(t, 9.3, 0.2)))
        k = p(t, 8.8, 0.8)
        y = 800 - 700 * (1 - ease(k)) + (30 * abs((1 - k) * 4 % 2 - 1) if k < 1 else 0)
        rect(img, (W / 2 - 170, y - 110, W / 2 + 170, y + 110), CORAL, 24, a)
        text(img, (W / 2, y), "vlog.mp4", 50, fill=NAVY, alpha=a)
        rect(img, (130, 1110, 950, 1330), CARD, 34, a, outline=(51, 71, 107), width=4)
        text(img, (170, 1160), "What do you want?", 30, fill=GREY, alpha=a, anchor="lm")
        brief = "relaxed vlog, funny parts, under 1 min"
        n = round(len(brief) * p(t, 10.2, 2.2))
        caret = "|" if int(t * 3) % 2 == 0 else ""
        text(img, (170, 1250), brief[:n] + caret, 44, alpha=a, anchor="lm")
    # 4: split into stories
    a = scene_alpha(t, *SCENES[3])
    if a > 0:
        text(img, (W / 2, 470), "STEP 2", 42, fill=CORAL, alpha=a)
        text(img, (W / 2, 620), "Transcribe & split\ninto stories", 64, alpha=a)
        bw = 960 * ease(p(t, 13.7, 0.6))
        if bw > 2:
            rect(img, (60, 960, 60 + bw, 1080), CORAL, 24, a * (1 - p(t, 14.8, 0.2)))
        for i, (title, length, code) in enumerate((("Morning\ncoffee", "0:48", "1f4a1"), ("The funny\nfail", "1:05", "1f525"),
                                                     ("City at\nnight", "0:56", "2705"))):
            s = back(p(t, 14.8 + i * 0.25, 0.5), 1.8)
            if s <= 0.01:
                continue
            cx, cy = 205 + i * 335, 1020 + 200 * (1 - clamp(s))
            w2, h2 = 145 * s, 210 * s
            rect(img, (cx - w2, cy - h2, cx + w2, cy + h2), CARD, 30, a * clamp(s), outline=CORAL, width=5)
            paste(img, EMO[code], cx, cy - 90 * s, 110 * s, a * clamp(s))
            text(img, (cx, cy + 50 * s), title, 40, alpha=a * clamp(s), scale=s)
            text(img, (cx, cy + 150 * s), length, 30, fill=GREY, alpha=a * clamp(s), scale=s)
    # 5: one click edit, on a phone
    a = scene_alpha(t, *SCENES[4])
    if a > 0:
        text(img, (W / 2, 330), "STEP 3 · ONE CLICK", 42, fill=CORAL, alpha=a)
        dy = 300 * (1 - ease(p(t, 18.6, 0.5)))
        x0, y0, x1, y1 = 240, 420 + dy, 840, 1486 + dy
        phone = Image.new("RGBA", (600, 1066), (0, 0, 0, 0))
        g = Image.linear_gradient("L").resize((600, 1066))
        grad = Image.composite(Image.new("RGBA", (600, 1066), (255, 92, 138, 255)), Image.new("RGBA", (600, 1066), (124, 92, 255, 255)), g)
        z = 1.08 if t >= 21.0 else 1.0  # zoom cut
        if z != 1:
            grad = grad.resize((int(600 * z), int(1066 * z))).crop((24, 43, 624, 1109))
        phone.alpha_composite(grad)
        d = ImageDraw.Draw(phone)
        d.ellipse((300 - 120 * z, 400 - 120 * z, 300 + 120 * z, 400 + 120 * z), fill=(255, 215, 168, 255))
        d.ellipse((300 - 230 * z, 850 - 200 * z, 300 + 230 * z, 850 + 260 * z), fill=(43, 47, 85, 255))
        if t >= 19.4:
            text(phone, (300, 640), "This place is", 58, stroke=8)
        if t >= 20.0:
            s = 1 + 0.5 * (1 - p(t, 20.0, 0.18))
            text(phone, (300, 740), "AMAZING", 84, fill=CORAL, scale=s, stroke=10)
        s = back(p(t, 21.6, 0.25), 2.5)
        paste(phone, EMO["1f525"], 470, 250, 160 * s, clamp(s))
        pb = 600 * p(t, 19.0, 4.4)
        if pb > 1:
            d.rectangle((0, 1054, pb, 1066), fill=(255, 255, 255, 255))
        mask = Image.new("L", (600, 1066), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, 599, 1065), 50, fill=int(255 * a))
        phone.putalpha(Image.composite(phone.getchannel("A"), Image.new("L", phone.size, 0), mask))
        rect(img, (x0 - 14, y0 - 14, x1 + 14, y1 + 14), (13, 22, 38), 62, a)
        img.alpha_composite(phone, (int(x0), int(y0)))
        k = ease(p(t, 22.4, 0.4))
        text(img, (W / 2, 1600 + 30 * (1 - k)), "Subtitles · Zoom cuts · Emoji · Music", 44, alpha=a * k)
    # 6: export
    a = scene_alpha(t, *SCENES[5])
    if a > 0:
        x1 = -900 * (1 - ease(p(t, 25.2, 0.5)))
        s = 1 + 0.06 * max(0, 1 - abs(t - 26.95) / 0.15)
        rect(img, (160 + x1 - 380 * (s - 1), 690 - 75 * (s - 1), 920 + x1 + 380 * (s - 1), 840 + 75 * (s - 1)), CORAL, 40, a)
        text(img, (W / 2 + x1, 765), "Export MP4", 56, fill=NAVY, alpha=a, scale=s)
        text(img, (W / 2, 920), "or", 44, fill=GREY, alpha=a)
        x2 = 900 * (1 - ease(p(t, 25.7, 0.5)))
        rect(img, (160 + x2, 1000, 920 + x2, 1150), CARD, 40, a, outline=(51, 71, 107), width=4)
        text(img, (W / 2 + x2, 1075), "Keep editing in CapCut", 50, alpha=a)
    # 7: end card
    a = scene_alpha(t, *SCENES[6])
    if a > 0:
        s = back(p(t, 29.1, 0.5))
        paste(img, ICON, W / 2, 560, 300 * s, a)
        wordmark(img, 850, 118, a)
        k = ease(p(t, 29.7, 0.4))
        text(img, (W / 2, 1040 + 60 * (1 - k)), "Edit less.", 64, alpha=a * k)
        text(img, (W / 2, 1120 + 60 * (1 - k)), "Post more.", 64, fill=CORAL, alpha=a * k)
        k = p(t, 30.5, 0.4)
        text(img, (W / 2, 1330), "Free & open source", 44, fill=GREY, alpha=a * k)
        text(img, (W / 2, 1400), "github.com/poomiiz/EditorKrab", 44, alpha=a * k)
    # caption of the voice line, so it also works muted
    for la, lb, line in LINES:
        if la <= t <= lb:
            k = min(p(t, la, 0.25), 1 - p(t, lb - 0.2, 0.2))
            f = F(46)
            words, rows, cur = line.split(), [], ""
            for w_ in words:
                if f.getlength((cur + " " + w_).strip()) > 860:
                    rows.append(cur)
                    cur = w_
                else:
                    cur = (cur + " " + w_).strip()
            rows.append(cur)
            hgt = len(rows) * 60 + 36
            rect(img, (60, H - 150 - hgt, W - 60, H - 150), (0, 0, 0), 22, 0.35 * k)
            text(img, (W / 2, H - 150 - hgt / 2), "\n".join(rows), 46, alpha=k)
    return img.convert("RGB")


if __name__ == "__main__":
    out = sys.argv[1]
    if len(sys.argv) > 2:  # stills at the given times, for checking
        for t in sys.argv[2].split(","):
            frame(float(t)).save(f"{out}_{t}.png")
        sys.exit(0)
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                           "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                           "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    for i in range(int(DUR * FPS)):
        ff.stdin.write(frame(i / FPS).tobytes())
    ff.stdin.close()
    if ff.wait():
        raise SystemExit("ffmpeg failed")
