"""Free stock video from Pexels and Pixabay (both: free for commercial use, no credit needed).
Each needs its own free API key in config.json: pexels_key, pixabay_key (Settings > เครื่องนี้).
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from video_edit import VideoEditError

SIGNUP = {"pexels": "https://www.pexels.com/api/new/", "pixabay": "https://pixabay.com/api/docs/"}


def _get(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "ClipKit", **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _pick(files: list[dict[str, Any]], want_h: int = 1920) -> dict[str, Any] | None:
    """The smallest file that is still at least 1080 on its short side, else the biggest there is."""
    ok = [f for f in files if f.get("link") and min(f.get("width") or 0, f.get("height") or 0) >= 1080]
    pool = ok or [f for f in files if f.get("link")]
    if not pool:
        return None
    return min(pool, key=lambda f: (f.get("width") or 0) * (f.get("height") or 0)) if ok else \
        max(pool, key=lambda f: (f.get("width") or 0) * (f.get("height") or 0))


def search(cfg: dict[str, Any], query: str, count: int = 6, portrait: bool = True) -> dict[str, Any]:
    """Hits from every source that has a key; a source without a key is reported, never skipped silently."""
    items: list[dict[str, Any]] = []
    missing = [s for s in ("pexels", "pixabay") if not cfg.get(f"{s}_key")]
    if len(missing) == 2:
        raise VideoEditError("ยังไม่ได้ใส่รหัส Pexels / Pixabay — ไปที่ ตั้งค่า > เครื่องนี้ (สมัครฟรี)")
    errors = []
    if cfg.get("pexels_key"):
        try:
            q = urllib.parse.urlencode({"query": query, "per_page": count, "orientation": "portrait" if portrait else "landscape"})
            for v in _get(f"https://api.pexels.com/videos/search?{q}", {"Authorization": cfg["pexels_key"]}).get("videos", []):
                f = _pick([{"link": x.get("link"), "width": x.get("width"), "height": x.get("height")} for x in v.get("video_files", [])])
                if f:
                    items.append({"source": "pexels", "id": str(v["id"]), "title": (v.get("user") or {}).get("name", "Pexels"),
                                  "thumb": v.get("image"), "url": v.get("url"), "file": f["link"],
                                  "duration": v.get("duration"), "width": f["width"], "height": f["height"]})
        except Exception as exc:  # one source down must not hide the other's hits, but it is reported
            errors.append(f"Pexels: {exc}")
    if cfg.get("pixabay_key"):
        try:
            q = urllib.parse.urlencode({"key": cfg["pixabay_key"], "q": query, "per_page": max(3, count), "safesearch": "true"})
            for v in _get(f"https://pixabay.com/api/videos/?{q}").get("hits", []):
                vids = v.get("videos") or {}
                f = _pick([{"link": x.get("url"), "width": x.get("width"), "height": x.get("height")} for x in vids.values()])
                if f:
                    items.append({"source": "pixabay", "id": str(v["id"]), "title": v.get("tags", "Pixabay"),
                                  "thumb": (vids.get("tiny") or {}).get("thumbnail") or "", "url": v.get("pageURL"),
                                  "file": f["link"], "duration": v.get("duration"), "width": f["width"], "height": f["height"]})
        except Exception as exc:
            errors.append(f"Pixabay: {exc}")
    if errors and not items:
        raise VideoEditError("ค้นภาพฟรีไม่ได้: " + " · ".join(errors))
    return {"items": items, "missing_keys": missing, "errors": errors, "signup": {s: SIGNUP[s] for s in missing}}


def download(folder: str, source: str, item_id: str, file_url: str) -> str:
    """Save one clip into <stock_video>/free (kept once; the same clip is not downloaded twice)."""
    if source not in SIGNUP or not item_id.isdigit():
        raise VideoEditError("unknown free stock item")
    host = urllib.parse.urlparse(file_url).hostname or ""
    if not host.endswith(("pexels.com", "pixabay.com")):
        raise VideoEditError(f"not a Pexels/Pixabay file: {host}")
    out = Path(folder) / "free"
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"{source}-{item_id}.mp4"
    if not target.is_file():
        req = urllib.request.Request(file_url, headers={"User-Agent": "ClipKit"})
        part = target.with_suffix(".part")
        with urllib.request.urlopen(req, timeout=120) as r, open(part, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        part.replace(target)
    return str(target)
