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
    via: str = Field(default="capcut", pattern="^(clipkit|capcut)$")
    shape: str = Field(default="source", pattern="^(source|portrait|landscape|square)$")
    focus_x: float = Field(default=0.5, ge=0, le=1)  # where to keep in frame when cropping (0 left, 1 right)
    focus_y: float = Field(default=0.5, ge=0, le=1)  # which button made it: finish in ClipKit or in CapCut


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


class StoryPlanRequest(BaseModel):
    file: str


_story_jobs: dict[str, dict[str, Any]] = {}


def _run_story_plan(file: str) -> None:
    """Transcribe once and save <file>.transcript.json; the agent (Claude / Codex with the ClipKit skill)
    reads it and writes <file>.stories.json, which the status call below picks up."""
    job = _story_jobs[file]
    try:
        tf = video_edit.transcript_file(file)
        if tf.is_file():
            phrases = json.loads(tf.read_text(encoding="utf-8"))
        else:
            duration = video_edit.probe(file)["duration"]
            job["step"] = "ถอดเสียง"
            phrases = video_edit.transcribe(file, 0, duration, "th", None)  # one model: video_edit.WHISPER_MODEL
            tf.write_text(json.dumps(phrases, ensure_ascii=False, indent=1), encoding="utf-8")
        job.update(status="waiting", step="รอ Claude แบ่งเรื่อง", transcript=str(tf),
                   command=video_edit.agent_command("stories", file),
                   duration=round(phrases[-1]["end"] if phrases else 0, 1),
                   speech=round(sum(p["end"] - p["start"] for p in phrases), 1))
    except Exception as exc:  # surface every failure to the page
        job.update(status="error", error=str(exc))


@router.post("/story-plan")
def story_plan(req: StoryPlanRequest) -> dict[str, Any]:
    """Transcribe a whole file and split it into stories before choosing CapCut or HyperFrames."""
    import threading
    if not Path(req.file).is_file():
        raise HTTPException(status_code=400, detail="file not found")
    job = _story_jobs.get(req.file)
    if not job or job["status"] == "error":
        _story_jobs[req.file] = {"status": "running", "step": "เริ่ม"}
        threading.Thread(target=_run_story_plan, args=(req.file,), daemon=True).start()
    return _story_jobs[req.file]


@router.get("/story-plan")
def story_plan_status(file: str = Query(...)) -> dict[str, Any]:
    job = _story_jobs.get(file)
    if not job:
        raise HTTPException(status_code=404, detail="no plan started for this file")
    if job["status"] == "waiting":
        try:
            phrases = json.loads(Path(job["transcript"]).read_text(encoding="utf-8"))
            stories = video_edit.stories_from_agent(file, phrases)
        except VideoEditError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if stories is not None:
            job.update(status="done", stories=stories)
    return job


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
            shape=req.shape,
            focus=(req.focus_x, req.focus_y),
        )
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # which raw file this project came from: the sidebar groups projects under it
    (Path(result["draft_path"]) / "clipkit.json").write_text(
        json.dumps({"raw": req.file, "start": req.start, "end": end, "via": req.via}, ensure_ascii=False), encoding="utf-8")
    return result


class FocusRequest(BaseModel):
    file: str
    start: float = 0.0
    end: float | None = None


@router.post("/focus")
def focus(req: FocusRequest) -> dict[str, Any]:
    """Where the speaker's face is, to place the crop."""
    try:
        return video_edit.find_focus(req.file, req.start, req.end)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    for d in items:  # made by the ClipKit button, or a CapCut project (any made before the buttons split)
        meta = Path(d["path"]) / "clipkit.json"
        d["via"] = json.loads(meta.read_text(encoding="utf-8")).get("via", "capcut") if meta.is_file() else "capcut"
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


class ExportRequest(BaseModel):
    path: str
    preview: bool = False  # quick half-size file for review before the real export


@router.post("/draft/export")
def draft_export(req: ExportRequest) -> dict[str, Any]:
    """MP4 straight from ClipKit (no CapCut): <output_dir>/exports/<project>.mp4"""
    import kit_settings
    import render
    cfg = kit_settings._read_config()
    out = cfg.get("output_dir") or cfg.get("work_root")  # same place covers and motion files go
    if not out:
        raise HTTPException(400, "ยังไม่ได้ตั้งที่เก็บไฟล์ส่งออก — ไปที่ ตั้งค่า > โฟลเดอร์")
    try:
        return render.render_draft(req.path, str(Path(out) / "exports"), preview=req.preview)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


class SubsLangRequest(BaseModel):
    path: str
    lang: str = Field(pattern="^(th|en)$")


@router.post("/draft/subs-lang")
def draft_subs_lang(req: SubsLangRequest) -> dict[str, Any]:
    try:
        return capcut_edit.subtitles_language(req.path, req.lang)
    except capcut_edit.NeedsAgent as exc:
        raise HTTPException(status_code=409, detail={"command": str(exc)}) from exc
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class TextPlace(BaseModel):
    id: str
    x: float = Field(ge=-1.5, le=1.5)
    y: float = Field(ge=-1.5, le=1.5)
    rotation: float = Field(default=0.0, ge=-180, le=180)
    size: float | None = Field(default=None, ge=2, le=60)


class TextLayoutRequest(BaseModel):
    path: str
    items: list[TextPlace]


@router.post("/draft/layout")
def draft_layout(req: TextLayoutRequest) -> dict[str, Any]:
    try:
        return capcut_edit.set_text_layout(req.path, [i.model_dump() for i in req.items])
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
                for d in capcut_edit.music_dirs())
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
        "drafts_root": video_edit.kitconfig.CFG.get("capcut_drafts", ""),
        "template_draft": video_edit.CAPCUT_TEMPLATE_DRAFT or "(newest draft in folder)",
        "whisper_model": video_edit.WHISPER_MODEL,
        "whisper_cpu_fallback": video_edit.WHISPER_CPU_FALLBACK,
        "gpu": video_edit._has_cuda(),
        "local_llm": video_edit.LOCAL_LLM_URL,
    }


# --- motion on top of the clip: pick a subtitle line, pick a template, it renders and sits at that time ---
OVERLAYS = "clipkit_overlays.json"
MOTION_TEMPLATES = {"hook-title": "หัวคลิป", "bps-sentence-pair": "คำเน้น"}


def _overlays(path: str) -> list[dict[str, Any]]:
    f = Path(path) / OVERLAYS
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else []


def _split2(text: str) -> tuple[str, str]:
    """Two halves at the Thai word break that balances them (lead / punch, key / sub)."""
    from pythainlp.tokenize import word_tokenize
    w = word_tokenize(text.replace("\n", " "), keep_whitespace=True)
    if len(w) < 2:
        return text, ""
    i = min(range(1, len(w)), key=lambda k: abs(len("".join(w[:k])) - len("".join(w[k:]))))
    return "".join(w[:i]).strip(), "".join(w[i:]).strip()


@router.get("/draft/overlays")
def draft_overlays(path: str = Query(...)) -> dict[str, Any]:
    try:
        d = capcut_edit.read_draft(path)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"subs": [{"start": s["start"], "end": s["end"], "text": s["text"]} for s in d["subtitles"]],
            "overlays": _overlays(path), "templates": MOTION_TEMPLATES}


class OverlayRequest(BaseModel):
    path: str
    template: str
    start: float = Field(ge=0)
    end: float
    text: str


@router.post("/draft/overlay")
def draft_overlay_add(req: OverlayRequest) -> dict[str, Any]:
    import kit_settings
    if req.template not in MOTION_TEMPLATES:
        raise HTTPException(400, f"unknown template: {req.template}")
    a, b = _split2(req.text)
    dur = round(min(6.0, max(3.0, req.end - req.start)), 2)
    params = ({"key": a, "sub": b, "duration": dur} if req.template == "hook-title"
              else {"pairs": [[0, dur, a, b, 0.8]]})
    name = f"{Path(req.path).name[:40]} {req.template} {int(req.start * 1000)}ms"
    mov = kit_settings.make_motion(kit_settings.MotionRequest(template=req.template, name=name, params=params))["file"]
    items = [o for o in _overlays(req.path) if abs(o["start"] - req.start) > 0.05]  # one motion per moment
    items.append({"file": mov, "start": req.start, "duration": dur, "template": req.template, "text": req.text})
    (Path(req.path) / OVERLAYS).write_text(json.dumps(sorted(items, key=lambda o: o["start"]), ensure_ascii=False,
                                                      indent=1), encoding="utf-8")
    return {"overlays": _overlays(req.path)}


class OverlayDelete(BaseModel):
    path: str
    start: float


@router.post("/draft/overlay-remove")
def draft_overlay_remove(req: OverlayDelete) -> dict[str, Any]:
    items = [o for o in _overlays(req.path) if abs(o["start"] - req.start) > 0.05]
    (Path(req.path) / OVERLAYS).write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"overlays": items}


class SubAnimRequest(BaseModel):
    path: str
    anim: str = Field(pattern="^(none|pop|karaoke|pair|pair-nina)$")


@router.post("/draft/sub-anim")
def draft_sub_anim(req: SubAnimRequest) -> dict[str, Any]:
    """How subtitles move in the MP4 export: still, pop in, or the spoken word lit up."""
    f = Path(req.path) / "clipkit_style.json"
    style = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    style["anim"] = req.anim
    f.write_text(json.dumps(style, ensure_ascii=False), encoding="utf-8")
    words = Path(req.path) / "clipkit_words.json"
    return {"anim": req.anim, "zoomcut": bool(style.get("zoomcut")), "has_word_times": words.is_file()}


@router.get("/draft/sub-anim")
def draft_sub_anim_get(path: str = Query(...)) -> dict[str, Any]:
    f = Path(path) / "clipkit_style.json"
    style = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    return {"anim": style.get("anim", "none"), "zoomcut": bool(style.get("zoomcut")),
            "has_word_times": (Path(path) / "clipkit_words.json").is_file()}


class ZoomCut(BaseModel):
    path: str
    on: bool


@router.post("/draft/zoomcut")
def draft_zoomcut(req: ZoomCut) -> dict[str, Any]:
    """Every other subtitle line punched in (an editing effect for the MP4 export)."""
    f = Path(req.path) / "clipkit_style.json"
    style = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    style["zoomcut"] = req.on
    f.write_text(json.dumps(style, ensure_ascii=False), encoding="utf-8")
    return {"zoomcut": req.on}


@router.post("/draft/punch-request")
def draft_punch_request(req: DraftPath) -> dict[str, Any]:
    """Lines for the agent to pick punch words from; the editor pastes the returned command into chat."""
    lines = [s["text"] for s in capcut_edit.read_draft(req.path)["subtitles"]]
    if not lines:
        raise HTTPException(400, "ยังไม่มีซับ — ถอดเสียงก่อน")
    (Path(req.path) / "clipkit_lines.json").write_text(json.dumps(lines, ensure_ascii=False, indent=1), encoding="utf-8")
    done = Path(req.path) / "clipkit_punch.json"
    picked = json.loads(done.read_text(encoding="utf-8")) if done.is_file() else {}
    return {"command": video_edit.agent_command("punch", req.path), "lines": len(lines),
            "picked": sum(1 for t in lines if t in picked)}


class FreeSearch(BaseModel):
    query: str
    count: int = Field(default=6, ge=1, le=20)
    portrait: bool = True


@router.post("/stock/free-search")
def stock_free_search(req: FreeSearch) -> dict[str, Any]:
    """Pexels + Pixabay hits (free for commercial use)."""
    import free_stock
    import kit_settings
    try:
        return free_stock.search(kit_settings._read_config(), req.query, req.count, req.portrait)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class FreeDownload(BaseModel):
    source: str
    id: str
    file: str


@router.post("/stock/free-download")
def stock_free_download(req: FreeDownload) -> dict[str, Any]:
    import free_stock
    import kit_settings
    cfg = kit_settings._read_config()
    folder = cfg.get("stock_video") or cfg.get("output_dir") or cfg.get("work_root")
    if not folder:
        raise HTTPException(400, "ยังไม่ได้ตั้งโฟลเดอร์สต็อกวิดีโอ — ไปที่ ตั้งค่า > โฟลเดอร์")
    try:
        return {"path": free_stock.download(folder, req.source, req.id, req.file)}
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def broll_fill(path: str) -> dict[str, Any]:
    """Free b-roll for the phrases the agent tagged with a search (3rd item in clipkit_punch.json):
    the first Pixabay/Pexels hit for each search is saved and listed in clipkit_broll.json."""
    import free_stock
    import kit_settings
    folder = Path(path)
    punch = folder / "clipkit_punch.json"
    queries = [p[2] for pairs in (json.loads(punch.read_text(encoding="utf-8")).values() if punch.is_file() else [])
               for p in pairs if len(p) > 2 and p[2]]
    out_file = folder / "clipkit_broll.json"
    chosen = json.loads(out_file.read_text(encoding="utf-8")) if out_file.is_file() else {}
    if not queries:
        return {"broll": chosen, "not_found": [], "queries": 0}
    cfg = kit_settings._read_config()
    store = cfg.get("stock_video") or cfg.get("output_dir") or cfg.get("work_root")
    if not store:
        raise VideoEditError("ยังไม่ได้ตั้งโฟลเดอร์สต็อกวิดีโอ — ไปที่ ตั้งค่า > โฟลเดอร์")
    missing = []
    for q in queries:
        if q in chosen and Path(chosen[q]["file"]).is_file():
            continue
        hits = free_stock.search(cfg, q, 3)["items"]
        if not hits:
            missing.append(q)
            continue
        h = hits[0]
        chosen[q] = {"file": free_stock.download(store, h["source"], h["id"], h["file"]), "source": h["source"],
                     "id": h["id"], "thumb": h["thumb"], "page": h["url"]}
    out_file.write_text(json.dumps(chosen, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"broll": chosen, "not_found": missing, "queries": len(queries)}


@router.post("/draft/broll-auto")
def draft_broll_auto(req: DraftPath) -> dict[str, Any]:
    try:
        return broll_fill(req.path)
    except VideoEditError as exc:
        raise HTTPException(400, str(exc)) from exc


class BrollRemove(BaseModel):
    path: str
    query: str


@router.post("/draft/broll-remove")
def draft_broll_remove(req: BrollRemove) -> dict[str, Any]:
    f = Path(req.path) / "clipkit_broll.json"
    chosen = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    chosen.pop(req.query, None)
    f.write_text(json.dumps(chosen, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"broll": chosen}


class AutoRequest(BaseModel):
    path: str
    look: str = Field(default="pair", pattern="^(pair|pair-nina|karaoke|pop|none)$")


@router.post("/draft/auto")
def draft_auto(req: AutoRequest) -> dict[str, Any]:
    """Every step in one go, ending in a quick preview for a person to review before the real export:
    subtitles (if none yet) -> silence trimmed -> subtitle look + zoom cut -> b-roll (where the agent asked)
    -> music + sound effects -> half-size preview MP4."""
    import kit_settings
    import render
    steps = []
    try:
        if not capcut_edit.read_draft(req.path)["subtitles"]:
            got = capcut_edit.transcribe_draft(req.path)
            capcut_edit.set_subtitles(req.path, got["subtitles"])
            capcut_edit.subtitles_language(req.path, "th")
            steps.append(f"ถอดเสียงใส่ซับ {got['count']} บรรทัด")
        t = capcut_edit.trim_pauses(req.path)
        steps.append("ตัดช่วงเงียบแล้ว")
        f = Path(req.path) / "clipkit_style.json"
        style = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
        style.setdefault("anim", req.look)
        style.setdefault("zoomcut", True)
        f.write_text(json.dumps(style, ensure_ascii=False), encoding="utf-8")
        b = broll_fill(req.path)
        steps.append(f"ภาพประกอบ {len(b['broll'])} จุด" if b["queries"] else "ภาพประกอบ: ยังไม่ได้ให้ Claude เลือกคำค้น")
        cfg = kit_settings._read_config()
        out = cfg.get("output_dir") or cfg.get("work_root")
        if not out:
            raise HTTPException(400, "ยังไม่ได้ตั้งที่เก็บไฟล์ส่งออก — ไปที่ ตั้งค่า > โฟลเดอร์")
        r = render.render_draft(req.path, str(Path(out) / "exports"), preview=True)
    except VideoEditError as exc:
        raise HTTPException(status_code=400, detail="; ".join(steps + [str(exc)])) from exc
    return {"steps": steps, "preview": r, "trim": t, "agent_command": video_edit.agent_command("punch", req.path),
            "punch_picked": (Path(req.path) / "clipkit_punch.json").is_file()}
