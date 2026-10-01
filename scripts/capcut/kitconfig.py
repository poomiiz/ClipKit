"""Machine paths for the CapCut tools, read from clip-kit config.json.

Looked up in order: $CLIP_KIT_CONFIG, <kit>/config.json, %USERPROFILE%/.clip-kit/config.json.
A missing config or key raises - never guess a path.
"""
import json
import os
from pathlib import Path

_KIT = Path(__file__).resolve().parents[2]
_CANDIDATES = [os.environ.get("CLIP_KIT_CONFIG"), _KIT / "config.json", Path.home() / ".clip-kit" / "config.json"]


def _load():
    for c in _CANDIDATES:
        if c and Path(c).is_file():
            return json.loads(Path(c).read_text(encoding="utf-8"))
    raise RuntimeError(f"clip-kit config.json not found; copy {_KIT / 'config.example.json'} to {_KIT / 'config.json'} and set your paths")


CFG = _load()


def need(key):
    v = CFG.get(key)
    if not v:
        raise RuntimeError(f"config.json is missing '{key}'")
    return v


DRAFTS = need("capcut_drafts")
# CapCut's project registry; default location for the current Windows user
ROOT_META = CFG.get("capcut_root_meta") or str(
    Path(os.environ.get("LOCALAPPDATA", "")) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft" / "root_meta_info.json")
FONT_NAME = need("card_font")


def font_file():
    """Absolute path of the card font, for ffmpeg previews."""
    for d in (Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts", Path(r"C:\Windows\Fonts")):
        for f in d.glob(FONT_NAME + ".*"):
            return str(f)
    raise RuntimeError(f"font '{FONT_NAME}' is not installed")
