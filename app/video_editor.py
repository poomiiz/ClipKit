"""Router: video_editor — scan a folder of footage, transcribe it, find the
pauses worth trimming, and hand the result to CapCut as a ready draft."""
from __future__ import annotations

import subprocess
import sys
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

import capcut_edit
import video_edit
from video_edit import VideoEditError


router = APIRouter(prefix="/api/video", tags=["video-editor"])
_transcribe_jobs: dict[str, subprocess.Popen[str]] = {}
_APP_DIR = Path(__file__).resolve().parent


class ScanRequest(BaseModel):
    path: str


class AnalyzeRequest(BaseModel):
    file: str
    start: float = 0.0
    end: float | None = None
    threshold_db: int = Field(default=-33, ge=-60, le=-10)
    min_pause: float = Field(default=0.30, ge=0.1, le=3.0)
    keep: float = Field(default=0.25, ge=0.0, le=2.0)
    min_gain: float = Field(default=0.30, ge=0.05, le=3.0)


class TranscribeRequest(BaseModel):
    file: str
    start: float = 0.0
    end: float | None = None
    language: str = "th"
    model: str | None = None


class SubtitleStyle(BaseModel):
    size: float | None = None
    y: float | None = None
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    stroke: float | None = None


class SubtitleIn(BaseModel):
    start: float
    end: float
    text: str
    style: SubtitleStyle | None = None


class CutIn(BaseModel):
    start: float
    end: float


class DraftRequest(BaseModel):
    file: str
    name: str
    start: float = 0.0
    end: float | None = None
    cuts: list[CutIn] = Field(default_factory=list)
    subs: list[SubtitleIn] = Field(default_factory=list)
    sub_size: int = Field(default=18, ge=6, le=60)
    sub_y: float = Field(default=-0.60, ge=-1.0, le=1.0)
    sub_color: str = Field(default="#ffffff", pattern=r"^#[0-9a-fA-F]{6}$")
    sub_stroke: float = Field(default=0.05, ge=0.0, le=0.3)


class BriefRequest(BaseModel):
    path: str


class BrowseRequest(BaseModel):
    path: str | None = None


class DraftPath(BaseModel):
    path: str


class DraftSubsRequest(BaseModel):
    path: str
    subs: list[SubtitleIn]
    size: float | None = None
    y: float | None = None
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    stroke: float | None = None
    replace: bool = True


class FillGapsRequest(BaseModel):
    path: str
    min_gap: float = Field(default=1.0, ge=0.3, le=10.0)
    preview: bool = False


class DraftStyleRequest(BaseModel):
    path: str
    size: float | None = None
    y: float | None = None
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    stroke: float | None = None


class DraftTrimRequest(BaseModel):
    path: str
    keep: float = Field(default=0.25, ge=0.0, le=2.0)
    min_gain: float = Field(default=0.30, ge=0.05, le=3.0)
    apply: bool = True


class GradeRequest(BaseModel):
    source: str
    target: str


class AnimationRequest(BaseModel):
    path: str
    name: str
    target: str = Field(default="text", pattern="^(text|video)$")
    duration: float | None = Field(default=None, ge=0.1, le=5.0)


class AnimationClearRequest(BaseModel):
    path: str
    target: str = Field(default="text", pattern="^(text|video)$")


class MusicRequest(BaseModel):
    path: str
    music: str
    volume: float = Field(default=0.10, ge=0.0, le=1.0)
    fade_out: float = Field(default=5.0, ge=0.0, le=10.0)
    start: float = Field(default=0.0, ge=0.0)
    fade_in: float | None = Field(default=None, ge=0.0, le=10.0)


class SoundRequest(BaseModel):
    path: str
    sound: str = "sfx_pop"
    volume: float = Field(default=0.35, ge=0.0, le=2.0)
    every_line: bool = True
    offset: float = Field(default=0.0, ge=-1.0, le=1.0)


class TranslateRequest(BaseModel):
    lines: list[str]
    target: str = "en"


class EmphasisRequest(BaseModel):
    lines: list[str]
    ratio: float = Field(default=0.25, ge=0.05, le=0.8)


class TermsRequest(BaseModel):
    lines: list[str]
    per_line: int = Field(default=2, ge=1, le=4)


class StockSearchRequest(BaseModel):
    query: str
    count: int = Field(default=4, ge=1, le=8)
    kind: str = Field(default="stock-video")


def _clip_end(file: str, end: float | None) -> float:
    return float(end) if end is not None else video_edit.probe(file)["duration"]


@router.post("/scan")
def scan(req: ScanRequest) -> dict[str, Any]:
    try:
        files = video_edit.scan_folder(req.path)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"path": req.path, "count": len(files), "files": files}


@router.post("/projects/plan")
def project_plan(req: ScanRequest) -> dict[str, Any]:
    try:
        plans = video_edit.suggest_projects(req.path)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"count": len(plans), "plans": plans}


@router.post("/projects/transcribe")
def start_project_transcription(req: ScanRequest) -> dict[str, Any]:
    folder = Path(req.path).resolve()
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail="folder not found")
    key = str(folder).lower()
    active = _transcribe_jobs.get(key)
    if active and active.poll() is None:
        raise HTTPException(status_code=409, detail="bot is already transcribing this project")
    output = folder / "transcripts"
    output.mkdir(parents=True, exist_ok=True)
    log = (output / "bot.log").open("a", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, str(_APP_DIR / "transcribe_folder.py"), str(folder)],
        cwd=str(_APP_DIR), stdout=log, stderr=subprocess.STDOUT, text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    _transcribe_jobs[key] = process
    return {"status": "running", "takes": len(video_edit.scan_folder(str(folder)))}


@router.get("/projects/transcribe/status")
def project_transcription_status(path: str = Query(...)) -> dict[str, Any]:
    folder = Path(path).resolve()
    key = str(folder).lower()
    process = _transcribe_jobs.get(key)
    output = folder / "transcripts"
    completed = len([file for file in output.glob("*.json") if file.name != "status.json"]) if output.is_dir() else 0
    return {"status": "running" if process and process.poll() is None else "idle",
            "completed": completed, "takes": len(video_edit.scan_folder(str(folder)))}


@router.get("/projects/transcribe/results")
def project_transcription_results(path: str = Query(...)) -> dict[str, Any]:
    output = Path(path).resolve() / "transcripts"
    results = []
    for file in sorted(output.glob("*.json")) if output.is_dir() else []:
        if file.name == "status.json":
            continue
        data = json.loads(file.read_text(encoding="utf-8"))
        results.append({"file": file.stem, "source": data.get("source"),
                        "duration": data.get("duration"), "review": data.get("review", {}),
                        "markdown": file.with_suffix(".md").read_text(encoding="utf-8") if file.with_suffix(".md").is_file() else ""})
    return {"results": results}


@router.post("/analyze")
def analyze(req: AnalyzeRequest) -> dict[str, Any]:
    try:
        end = _clip_end(req.file, req.end)
        pauses = video_edit.detect_pauses(req.file, req.start, end,
                                          req.threshold_db, req.min_pause)
        cuts = video_edit.suggest_cuts(pauses, req.keep, req.min_gain)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    removed = round(sum(c["gain"] for c in cuts), 2)
    length = round(end - req.start, 2)
    return {
        "length": length,
        "pauses": pauses,
        "cuts": cuts,
        "removed": removed,
        "result_length": round(length - removed, 2),
        "cuts_per_10s": round(10 * len(cuts) / max(length - removed, 0.1), 2),
    }


@router.post("/transcribe")
def transcribe(req: TranscribeRequest) -> dict[str, Any]:
    try:
        end = _clip_end(req.file, req.end)
        phrases = video_edit.transcribe(req.file, req.start, end, req.language, req.model)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # model load / runtime problems must surface, not hide
        raise HTTPException(status_code=500, detail=f"transcribe failed: {exc}") from exc
    return {"count": len(phrases), "phrases": phrases}


@router.post("/capcut")
def capcut(req: DraftRequest) -> dict[str, Any]:
    try:
        end = _clip_end(req.file, req.end)
        result = video_edit.create_capcut_draft(
            video_path=req.file,
            project_name=req.name,
            clip_in=req.start,
            clip_out=end,
            cuts=[c.model_dump() for c in req.cuts],
            subs=[s.model_dump() for s in req.subs],
            sub_size=req.sub_size,
            sub_y=req.sub_y,
            sub_color=req.sub_color,
            sub_stroke=req.sub_stroke,
        )
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.post("/browse")
def browse(req: BrowseRequest) -> dict[str, Any]:
    """Folder picker data: drives, subfolders, and video counts."""
    try:
        return video_edit.browse(req.path)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/presets")
def presets() -> dict[str, Any]:
    """Colour grade and subtitle styling taken from the projects already cut."""
    try:
        return video_edit.extract_presets()
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/briefs")
def briefs(req: BriefRequest) -> dict[str, Any]:
    """Per-clip notes of a 'For Cutting' style folder (hook line, footage)."""
    try:
        items = video_edit.read_briefs(req.path)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"count": len(items), "briefs": items}


@router.post("/translate")
def translate(req: TranslateRequest) -> dict[str, Any]:
    try:
        return {"lines": video_edit.translate_lines(req.lines, req.target)}
    except VideoEditError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/frame")
def frame(path: str = Query(...), t: float = Query(1.0), width: int = Query(360)) -> Response:
    """A still from the clip, used as the backdrop of the subtitle preview."""
    try:
        data = video_edit.grab_frame(path, t, width)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(content=data, media_type="image/jpeg",
                    headers={"Cache-Control": "max-age=300"})


@router.get("/drafts")
def drafts() -> dict[str, Any]:
    """CapCut projects already on this machine."""
    try:
        items = capcut_edit.list_drafts()
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"count": len(items), "drafts": items}


@router.post("/draft")
def draft(req: DraftPath) -> dict[str, Any]:
    try:
        return capcut_edit.read_draft(req.path)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/draft/transcribe")
def draft_transcribe(req: DraftPath) -> dict[str, Any]:
    """Subtitles for an existing project, timed to its own timeline."""
    try:
        return capcut_edit.transcribe_draft(req.path)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"transcribe failed: {exc}") from exc


@router.post("/draft/subs")
def draft_subs(req: DraftSubsRequest) -> dict[str, Any]:
    try:
        return capcut_edit.set_subtitles(
            req.path, [s.model_dump() for s in req.subs], size=req.size, y=req.y,
            color=req.color, stroke=req.stroke, replace=req.replace)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/draft/subs/fill")
def draft_subs_fill(req: FillGapsRequest) -> dict[str, Any]:
    """Subtitle only the stretches that have none, for footage added later."""
    try:
        return capcut_edit.fill_subtitle_gaps(req.path, min_gap=req.min_gap,
                                              preview=req.preview)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/draft/style")
def draft_style(req: DraftStyleRequest) -> dict[str, Any]:
    try:
        return capcut_edit.restyle_subtitles(req.path, size=req.size, y=req.y,
                                             color=req.color, stroke=req.stroke)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/draft/trim")
def draft_trim(req: DraftTrimRequest) -> dict[str, Any]:
    try:
        return capcut_edit.trim_pauses(req.path, keep=req.keep,
                                       min_gain=req.min_gain, apply=req.apply)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/draft/grade")
def draft_grade(req: GradeRequest) -> dict[str, Any]:
    try:
        return capcut_edit.copy_grade(req.source, req.target)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/emphasis")
def emphasis(req: EmphasisRequest) -> dict[str, Any]:
    """First guess at which lines should use the emphasised style."""
    return {"lines": video_edit.suggest_emphasis(req.lines, req.ratio)}


@router.post("/terms")
def terms(req: TermsRequest) -> dict[str, Any]:
    """English stock-footage search terms for Thai subtitle lines."""
    try:
        return {"terms": video_edit.search_terms(req.lines, req.per_line)}
    except VideoEditError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/stock/search")
def stock_search(req: StockSearchRequest) -> dict[str, Any]:
    """Ask the browser bot to search Envato in the logged-in Chrome."""
    try:
        return video_edit.stock_search(req.query, req.count, req.kind)
    except VideoEditError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/stock/result/{job_id}")
def stock_result(job_id: int) -> dict[str, Any]:
    try:
        return video_edit.stock_result(job_id)
    except VideoEditError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/animations")
def animations() -> dict[str, Any]:
    """Animations already downloaded on this machine, read from real projects."""
    try:
        items = capcut_edit.list_animations()
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"count": len(items), "animations": items}


@router.post("/draft/animation")
def draft_animation(req: AnimationRequest) -> dict[str, Any]:
    try:
        return capcut_edit.apply_animation(req.path, req.name, req.target, req.duration)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/draft/animation/clear")
def draft_animation_clear(req: AnimationClearRequest) -> dict[str, Any]:
    try:
        return capcut_edit.clear_animations(req.path, req.target)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/file")
def file(path: str = Query(...)) -> FileResponse:
    """Serve one music file so it can be auditioned in the page."""
    from pathlib import Path as _Path
    target = _Path(path)
    if not target.is_file() or target.suffix.lower() not in capcut_edit.AUDIO_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"not an audio file: {path}")
    known = any(str(target).lower().startswith(str(_Path(d)).lower())
                for d in capcut_edit.MUSIC_DIRS)
    if not known:
        raise HTTPException(status_code=403, detail="file is outside the music folders")
    return FileResponse(str(target))


@router.get("/music")
def music() -> dict[str, Any]:
    """Background music already owned, from the known folders."""
    try:
        items = capcut_edit.list_music()
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"count": len(items), "music": items}


@router.post("/draft/music")
def draft_music(req: MusicRequest) -> dict[str, Any]:
    try:
        return capcut_edit.add_music(req.path, req.music, req.volume,
                                     req.fade_out, req.start, req.fade_in)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sounds")
def sounds() -> dict[str, Any]:
    """Sound effects available locally, learned from existing projects."""
    try:
        items = capcut_edit.list_sounds()
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"count": len(items), "sounds": items}


@router.post("/draft/sound")
def draft_sound(req: SoundRequest) -> dict[str, Any]:
    try:
        return capcut_edit.add_sound_on_subtitles(req.path, req.sound, req.volume,
                                                  req.every_line, req.offset)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/draft/sound/clear")
def draft_sound_clear(req: DraftPath) -> dict[str, Any]:
    try:
        return capcut_edit.clear_sounds(req.path)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/config")
def config() -> dict[str, Any]:
    return {
        "drafts_root": video_edit.CAPCUT_DRAFTS_ROOT,
        "template_draft": video_edit.CAPCUT_TEMPLATE_DRAFT or "(newest draft in folder)",
        "whisper_model": video_edit.WHISPER_MODEL,
        "whisper_cpu_fallback": video_edit.WHISPER_CPU_FALLBACK,
        "gpu": video_edit._has_cuda(),
        "local_llm": video_edit.LOCAL_LLM_URL,
    }
