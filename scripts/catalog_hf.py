"""Sort the HyperFrames registry into ClipKit's motion library: what each item is for in a talking-head short,
which mood it fits, and whether Thai text or a vertical frame still needs a test.

    python scripts/catalog_hf.py            # reads `npx hyperframes catalog --json`, writes motion/library/
The output is a first pass by tags and words; items marked "test" must be tried with Thai before real use.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "motion" / "library"
HF = "hyperframes@0.8.101"

# role in a short clip, first match wins (checked against tags + name)
ROLES = [
    ("skip", {"showcase", "product-demo", "mock-ui", "code", "developer", "code-animation", "webgl", "3d", "3d-motion",
              "carousel", "gallery", "experiment", "ui-props", "html-in-canvas", "ad-template", "app"}),
    ("ซับ", {"captions", "caption-style"}),
    ("ป้ายชื่อ", {"lower-third"}),
    ("หัวคลิป", {"title-card", "intro", "headline", "logo"}),
    ("ตัวเลข/ข้อมูล", {"data", "chart", "statistics", "counter", "ranking", "finance", "map", "geography"}),
    ("ทรานสิชัน", {"transition", "transition-primitive", "wipe", "transitions-dev-port"}),
    ("โซเชียล", {"social", "notification", "chat", "follow", "comment"}),
    ("คำเน้น", {"typography", "text", "text-effects", "highlight", "marker", "annotation", "handwritten", "kinetic", "reveal"}),
    ("บรรยากาศ", {"overlay", "texture", "background", "effect", "effects", "grain", "vignette", "light"}),
]
MOODS = [
    ("ตื่นเต้น", ["slam", "glitch", "explode", "burst", "particle", "flash", "shake", "impact", "rgb", "kinetic", "punch",
                  "beat", "freeze", "neon", "scramble", "decode", "shatter", "zoom"]),
    ("ตลก/โซเชียล", ["emoji", "social", "tiktok", "comment", "notification", "pop", "bounce", "bubble", "reddit", "x-post",
                     "spotify", "instagram", "follow", "chat"]),
    ("เล่าเรื่อง", ["hand", "hw-", "typewriter", "marker", "annotate", "highlight", "whiteboard", "ink", "scribble",
                   "underline", "circle", "arrow", "vox", "strike"]),
    ("ทางการ", ["calm", "clean", "minimal", "titlecard", "soft", "focus", "fade", "lockup", "lt-", "corporate", "blur",
                "crossfade", "per-word", "tracking", "editorial"]),
]
THAI_RISK = ["letter", "glyph", "character", "per-char", "scramble", "decode", "matrix", "split-flap", "write-on",
             "caveat", "slot-machine", "char-"]


def first(words, text):
    return next((label for label, keys in words if any(k in text for k in keys)), "")


def main() -> None:
    npx = shutil.which("npx")
    if not npx:
        raise SystemExit("Node.js (npx) is not installed")
    r = subprocess.run([npx, "--yes", HF, "catalog", "--json"], capture_output=True, text=True, encoding="utf-8")
    items = json.loads(r.stdout)
    rows = []
    for it in items:
        tags = set(it.get("tags", []))
        text = (it["name"] + " " + " ".join(tags) + " " + it.get("description", "")).lower()
        role = next((label for label, keys in ROLES if tags & keys or any(k in it["name"] for k in keys)), "อื่น ๆ")
        if role == "skip":
            continue
        dim = it.get("dimensions") or {}
        rows.append({
            "name": it["name"], "type": it["type"], "role": role,
            "mood": first(MOODS, text) or "ทั่วไป",
            "thai": "test" if any(k in text for k in THAI_RISK) else "ok?",
            "vertical": "yes" if dim.get("height", 0) > dim.get("width", 1) or "vertical" in tags else "adapt",
            "seconds": it.get("duration"), "title": it.get("title", ""),
            "description": it.get("description", ""), "preview": (it.get("preview") or {}).get("video", ""),
        })
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "hyperframes.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    order = ["หัวคลิป", "คำเน้น", "ซับ", "ป้ายชื่อ", "ตัวเลข/ข้อมูล", "โซเชียล", "ทรานสิชัน", "บรรยากาศ", "อื่น ๆ"]
    md = ["# คลัง HyperFrames สำหรับคลิปสั้น", "",
          f"คัดจาก {len(items)} ชิ้นในคลัง HyperFrames เหลือ {len(rows)} ชิ้นที่ใช้กับคลิปพูดแนวตั้งได้ "
          "(ตัดกลุ่มโชว์สินค้า หน้าจอแอป โค้ด และ 3D ออก) · จัดอัตโนมัติจากแท็ก ต้องลองกับคำไทยก่อนใช้จริง",
          "", "ไทย: `test` = แยกตัวอักษรทีละตัว สระ/วรรณยุกต์ไทยอาจหลุด ต้องลอง · แนวตั้ง: `adapt` = ออกแบบมาแนวนอน ต้องปรับ",
          "", "ติดตั้งชิ้นไหน: `npx hyperframes@0.8.101 add <name>` ในโปรเจกต์ HyperFrames", ""]
    for role in order:
        group = [x for x in rows if x["role"] == role]
        if not group:
            continue
        md += [f"## {role} ({len(group)})", "", "| ชื่อ | อารมณ์ | ไทย | แนวตั้ง | ใช้ทำอะไร |", "|---|---|---|---|---|"]
        for x in sorted(group, key=lambda x: (x["mood"], x["name"])):
            md.append(f"| `{x['name']}` | {x['mood']} | {x['thai']} | {x['vertical']} | {x['description'][:90]} |")
        md.append("")
    (OUT / "hyperframes.md").write_text("\n".join(md), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    from collections import Counter
    print(len(items), "->", len(rows), dict(Counter(x["role"] for x in rows)), dict(Counter(x["mood"] for x in rows)))


if __name__ == "__main__":
    main()
