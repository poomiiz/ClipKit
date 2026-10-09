"""Preset packs: one .clipkit file (a zip) holding subtitle presets, covers and motion templates, so a team
can hand looks to each other by dropping a file. The format is the one a future preset store will sell
(spec: "ClipKit Preset Pack - สเปค v0.1"); tiers and their minimums live here so the app and the store agree.

    my-pack.clipkit
      manifest.json
      subtitles/<id>.json            -> presets/<id>.json
      covers/<cover-id>/...          -> motion/<cover-id>/      (ids start with "cover-")
      motion/<id>/...                -> motion/<id>/
      fonts/<file>.ttf|otf + fonts/<stem>-LICENSE.txt -> fonts/
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

KIT = Path(__file__).resolve().parents[1]
FORMAT = 1
# minimum covers, subtitle styles, motion templates per tier; price in baht is fixed per tier (sellers pick a tier)
TIERS = {"team": (0, 0, 0, 0), "free": (1, 1, 0, 0), "basic": (3, 2, 2, 49),
         "standard": (6, 4, 4, 99), "pro": (12, 8, 8, 199)}
ID = re.compile(r"[a-z0-9][a-z0-9-]{0,47}")
FONT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\.(ttf|otf)")


class PackError(ValueError):
    pass


def _ids(m: dict, key: str) -> list[str]:
    v = m.get(key, [])
    if not isinstance(v, list) or not all(isinstance(i, str) and ID.fullmatch(i) for i in v):
        raise PackError(f"manifest '{key}' must be a list of ids (a-z, 0-9, -): {v!r}")
    return v


def check_manifest(m: dict) -> dict:
    if m.get("format") != FORMAT:
        raise PackError(f"pack format {m.get('format')!r} not supported (this app reads format {FORMAT})")
    if not isinstance(m.get("id"), str) or not ID.fullmatch(m["id"]):
        raise PackError(f"pack id must be a-z, 0-9, -: {m.get('id')!r}")
    if not str(m.get("name", "")).strip():
        raise PackError("pack has no name")
    if m.get("tier") not in TIERS:
        raise PackError(f"tier must be one of {', '.join(TIERS)}: {m.get('tier')!r}")
    covers, subs, motion = _ids(m, "covers"), _ids(m, "subtitles"), _ids(m, "motion")
    if bad := [c for c in covers if not c.startswith("cover-")]:
        raise PackError(f"cover ids must start with 'cover-': {bad}")
    if bad := [c for c in motion if c.startswith("cover-")]:
        raise PackError(f"motion ids must not start with 'cover-': {bad}")
    need = TIERS[m["tier"]]
    for label, have, n in (("covers", covers, need[0]), ("subtitle styles", subs, need[1]), ("motion", motion, need[2])):
        if len(have) < n:
            raise PackError(f"tier '{m['tier']}' needs at least {n} {label}, pack has {len(have)}")
    fonts = m.get("fonts", [])
    if not isinstance(fonts, list) or not all(isinstance(f, dict) and FONT.fullmatch(str(f.get("file", "")))
                                              and str(f.get("license", "")).strip() for f in fonts):
        raise PackError('manifest "fonts" must be [{"file": "Name.ttf", "license": "OFL-1.1"}, ...]')
    return m


def _plan(m: dict) -> list[tuple[str, Path]]:
    """(name inside the zip or a folder prefix ending in '/', where it goes) for everything the manifest lists."""
    out = [(f"subtitles/{i}.json", KIT / "presets" / f"{i}.json") for i in m.get("subtitles", [])]
    out += [(f"covers/{i}/", KIT / "motion" / i) for i in m.get("covers", [])]
    out += [(f"motion/{i}/", KIT / "motion" / i) for i in m.get("motion", [])]
    for f in m.get("fonts", []):
        stem = Path(f["file"]).stem
        out += [(f"fonts/{f['file']}", KIT / "fonts" / f["file"]),
                (f"fonts/{stem}-LICENSE.txt", KIT / "fonts" / f"{stem}-LICENSE.txt")]
    return out


def read_pack(path: str | Path) -> dict[str, Any]:
    """The manifest of a .clipkit file, checked, plus what installing it would add or clash with."""
    p = Path(path)
    if not p.is_file():
        raise PackError(f"file not found: {p}")
    try:
        z = zipfile.ZipFile(p)
    except zipfile.BadZipFile as exc:
        raise PackError(f"{p.name} is not a .clipkit pack (not a zip): {exc}") from exc
    with z:
        names = set(z.namelist())
        if "manifest.json" not in names:
            raise PackError(f"{p.name} has no manifest.json")
        try:
            m = json.loads(z.read("manifest.json").decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PackError(f"manifest.json is broken: {exc}") from exc
        if not isinstance(m, dict):
            raise PackError("manifest.json must be an object")
        check_manifest(m)
        missing, clash = [], []
        for src, dst in _plan(m):
            if src.endswith("/"):
                if f"{src}index.html" not in names:
                    missing.append(f"{src}index.html")
            elif src not in names:
                missing.append(src)
            if dst.exists():
                clash.append(str(dst.relative_to(KIT)))
        if missing:
            raise PackError(f"{p.name} is missing files its manifest lists: {missing}")
        for sub in m.get("subtitles", []):
            try:
                s = json.loads(z.read(f"subtitles/{sub}.json").decode("utf-8"))
                s["normal"], s["emphasis"]
            except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
                raise PackError(f"subtitles/{sub}.json is not a subtitle preset (needs normal + emphasis): {exc}")
    return {"manifest": m, "clash": sorted(set(clash))}


def install_pack(path: str | Path) -> dict[str, Any]:
    """Unpack a checked .clipkit into presets/, motion/ and fonts/. Refuses (changes nothing) when any of its
    names is already taken, so a pack never overwrites someone's own look."""
    info = read_pack(path)
    if info["clash"]:
        raise PackError(f"already installed or same names exist: {info['clash']} - rename or remove them first")
    m, writes = info["manifest"], []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        for src, dst in _plan(m):   # every path checked before anything is written
            files = [n for n in names if n.startswith(src) and not n.endswith("/")] if src.endswith("/") else [src]
            for n in files:
                target = dst / n[len(src):] if src.endswith("/") else dst
                if dst.resolve() not in target.resolve().parents and target.resolve() != dst.resolve():
                    raise PackError(f"unsafe path in pack: {n}")   # ../ in a zip name
                writes.append((n, target))
        for n, target in writes:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(n))
    return {"installed": m["id"], "name": m["name"], "added": [str(d.relative_to(KIT)) for _, d in _plan(m)]}


def items() -> dict[str, list[str]]:
    """What this machine has that can go into a pack."""
    motion = KIT / "motion"
    return {"subtitles": sorted(p.stem for p in (KIT / "presets").glob("*.json")),
            "covers": sorted(d.name for d in motion.glob("cover-*") if (d / "index.html").is_file()),
            "motion": sorted(d.name for d in motion.iterdir()
                             if (d / "index.html").is_file() and not d.name.startswith("cover-")),
            "fonts": sorted(f.name for f in (KIT / "fonts").iterdir() if FONT.fullmatch(f.name))}


def make_pack(out_dir: str | Path, manifest: dict) -> Path:
    """Write <out_dir>/<id>.clipkit from this machine's presets, covers, motion and fonts."""
    m = check_manifest({"format": FORMAT, **manifest})
    have = items()
    for key in ("subtitles", "covers", "motion"):
        if bad := [i for i in m.get(key, []) if i not in have[key]]:
            raise PackError(f"not on this machine ({key}): {bad}")
    for f in m.get("fonts", []):
        lic = KIT / "fonts" / f"{Path(f['file']).stem}-LICENSE.txt"
        if f["file"] not in have["fonts"]:
            raise PackError(f"font not in fonts/: {f['file']}")
        if not lic.is_file():
            raise PackError(f"font {f['file']} needs its licence text at fonts/{lic.name} (a pack never ships a font without one)")
    out = Path(out_dir)
    if not out.is_dir():
        raise PackError(f"folder not found: {out}")
    dest = out / f"{m['id']}.clipkit"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(m, ensure_ascii=False, indent=1))
        for src, dst in _plan(m):
            if src.endswith("/"):
                for f in sorted(dst.rglob("*")):
                    if f.is_file() and not f.name.startswith("preview-bg") and "__pycache__" not in f.parts:
                        z.write(f, src + f.relative_to(dst).as_posix())
            else:
                z.write(dst, src)
    return dest
