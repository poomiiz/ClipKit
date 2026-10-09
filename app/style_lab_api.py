"""Style lab API for app/static/styles.html: take a look from a CapCut project or a video, preview it, keep it.
The work is in scripts/style_lab.py; this only maps it to HTTP."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import style_lab  # noqa: E402

router = APIRouter(prefix="/api/style", tags=["style-lab"])


class Source(BaseModel):
    source: str


class Folder(BaseModel):
    folder: str


class Keep(BaseModel):
    folder: str
    name: str
    parts: list[str] | None = None
    overwrite: bool = False


class Mix(BaseModel):
    name: str
    main: str
    caption: str | None = None
    second: str | None = None


def _lab_folder(folder: str) -> Path:
    f = Path(folder).resolve()
    if f.parent != style_lab.lab().resolve() or not (f / "source.json").is_file():
        raise HTTPException(400, f"not a style lab folder: {folder}")
    return f


def _run(fn, *args) -> Any:
    try:
        return fn(*args)
    except (ValueError, FileExistsError, RuntimeError) as exc:   # RuntimeError: config.json path missing
        raise HTTPException(400, str(exc)) from exc


@router.get("/items")
def items() -> dict[str, Any]:
    return {"items": _run(style_lab.items), "collection": _run(style_lab.collection)}


@router.get("/capcut-projects")
def capcut_projects() -> dict[str, Any]:
    return {"projects": _run(style_lab.capcut_projects)}


@router.post("/start")
def start(body: Source) -> dict[str, Any]:
    return _run(style_lab.start, body.source)


@router.post("/preview")
def preview(body: Folder) -> dict[str, Any]:
    return _run(style_lab.preview, _lab_folder(body.folder))


@router.post("/save")
def save(body: Keep) -> dict[str, Any]:
    return _run(style_lab.save, _lab_folder(body.folder), body.name, body.parts, body.overwrite)


@router.post("/compose")
def compose(body: Mix) -> dict[str, Any]:
    return _run(style_lab.compose, body.name, body.main, body.caption, body.second)


class Share(BaseModel):
    preset: str


@router.post("/share")
def share(body: Share) -> dict[str, Any]:
    return _run(style_lab.share, body.preset)


@router.post("/remove")
def remove(body: Share) -> dict[str, Any]:
    return _run(style_lab.remove, body.preset)


@router.get("/file")
def file(path: str) -> FileResponse:
    """A frame or preview picture from the lab or the collection; nothing else on the disk."""
    f = Path(path).resolve()
    roots = (style_lab.lab().resolve(), style_lab.PREVIEWS.resolve(), style_lab.PARTS.resolve())
    if f.suffix.lower() not in (".png", ".gif", ".jpg") or not any(f.is_relative_to(r) for r in roots) or not f.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(f, headers={"Cache-Control": "no-store"})
