"""Quick checks that run before every sync to the team repo (scripts/sync_team.py). No video, no network.

    python scripts/smoke_test.py

Each check guards a bug that once reached a machine. Exit 1 = do not ship.
"""
import json
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "scripts"))
FAILED = []


def check(name, fn):
    try:
        fn()
        print("ok  ", name)
    except Exception as exc:  # noqa: BLE001 - every failure is reported, none is skipped
        FAILED.append(name)
        print("FAIL", name, "-", exc)


def python_compiles():
    for f in list((ROOT / "app").glob("*.py")) + list((ROOT / "scripts").rglob("*.py")):
        py_compile.compile(str(f), doraise=True)


def pages_parse():
    # a typo in one <script> leaves the whole page blank
    if not shutil.which("node"):
        raise RuntimeError("node not installed")
    for page in (ROOT / "app" / "static").glob("*.html"):
        for k, js in enumerate(re.findall(r"<script>([\s\S]*?)</script>", page.read_text(encoding="utf-8"))):
            r = subprocess.run(["node", "-e", "new Function(require('fs').readFileSync(0,'utf8'))"],
                               input=js, capture_output=True, text=True, encoding="utf-8")
            if r.returncode:
                raise RuntimeError(f"{page.name} script {k}: {r.stderr.strip().splitlines()[-1]}")


def json_files_valid():
    # config.example.json once shipped with an unescaped backslash
    for f in [ROOT / "config.example.json", ROOT / "app" / "capcut_templates.json", *(ROOT / "presets").glob("*.json")]:
        json.loads(f.read_text(encoding="utf-8"))


def _fake_project(folder: Path, tid: str) -> None:
    (folder / "Timelines" / tid).mkdir(parents=True)
    (folder / "Timelines" / "project.json").write_text(json.dumps({"main_timeline_id": tid}), encoding="utf-8")
    body = json.dumps({"id": tid, "duration": 1, "tracks": [], "materials": {}})
    (folder / "draft_content.json").write_text(body, encoding="utf-8")
    (folder / "Timelines" / tid / "draft_content.json").write_text(body, encoding="utf-8")


def capcut_ids_unique_and_synced():
    # CapCut 9.6 would not open or hung on a copy that kept its source's timeline id
    import capcut_edit
    with tempfile.TemporaryDirectory() as t:
        a, b = Path(t) / "a", Path(t) / "b"
        _fake_project(a, "SAME")
        shutil.copytree(a, b)
        ida, idb = capcut_edit.fresh_ids(a), capcut_edit.fresh_ids(b)
        assert ida != idb, "two copies share a timeline id"
        for f, tid in ((a, ida), (b, idb)):
            assert json.loads((f / "Timelines" / "project.json").read_text())["main_timeline_id"] == tid
            assert (f / "Timelines" / tid / "draft_content.json").read_text() == (f / "draft_content.json").read_text(), \
                "Timelines copy differs from draft_content.json"


def autosave_spots_a_broken_project():
    # a timeline whose clip points at a missing material would not open in CapCut: never saved as "good"
    import autosave
    ok = {"duration": 1, "materials": {"videos": [{"id": "m1"}]}, "tracks": [{"type": "video", "segments": [{"material_id": "m1"}]}]}
    assert autosave.problems(ok) == [], autosave.problems(ok)
    bad = {**ok, "tracks": [{"type": "video", "segments": [{"material_id": "gone"}]}]}
    assert autosave.problems(bad), "missing material not caught"


def outside_edit_is_caught():
    import capcut_edit
    from video_edit import VideoEditError
    with tempfile.TemporaryDirectory() as t:
        f = Path(t) / "p"
        _fake_project(f, "X")
        capcut_edit._save(f, capcut_edit._load(f), "smoke")
        (f / "draft_content.json").write_text('{"id": "X", "tracks": [], "materials": {}, "edited": 1}', encoding="utf-8")
        listed = capcut_edit.list_drafts(t)
        assert len(listed) == 1 and listed[0]["external_changed"], "external edits disappeared from the read-only list"
        try:
            capcut_edit._load(f)
        except VideoEditError:
            return
        raise AssertionError("an edit made outside ClipKit was not caught")


def pictures_are_stills():
    # a picture probed as a 0.04 s video showed for one frame
    import video_edit
    assert video_edit.is_image("a.JPG") and video_edit.is_image("b.png") and not video_edit.is_image("c.mp4")


def background_jobs_are_reserved_and_bounded():
    from unittest.mock import patch
    import kit_settings
    from fastapi import HTTPException
    name = "smoke-job"
    try:
        with patch.object(kit_settings.threading.Thread, "start"):
            kit_settings._start(name, [sys.executable])
            try:
                kit_settings._start(name, [sys.executable])
            except HTTPException as exc:
                assert exc.status_code == 409
            else:
                raise AssertionError("a second job started before the worker ran")
        kit_settings._run_job(name, [sys.executable, "-c", "print('x' * 12000); print('tail')"])
        state = kit_settings.job(name)
        assert state["status"] == "done"
        assert len(kit_settings._jobs[name]["log"]) <= 6000
        assert state["log"].endswith("tail\n")
        with patch.object(kit_settings.threading.Thread, "start", side_effect=RuntimeError("no thread")):
            try:
                kit_settings._start(name, [])
            except RuntimeError:
                pass
            else:
                raise AssertionError("thread failure was hidden")
        assert kit_settings.job(name)["status"] == "failed"
    finally:
        kit_settings._jobs.pop(name, None)


def local_browser_boundary():
    from fastapi.testclient import TestClient
    from app import app
    with TestClient(app, base_url="http://127.0.0.1:8770") as client:
        assert client.get("/video-editor.html").status_code == 200
        assert client.get("/", headers={"host": "untrusted.example"}).status_code == 400
        for headers in ({"origin": "https://untrusted.example"}, {"origin": "null"},
                        {"origin": "http://127.0.0.1:9999"}, {"sec-fetch-site": "cross-site"}):
            assert client.get("/api/kit/job/unused", headers=headers).status_code == 403
            assert client.post("/api/kit/setup", headers=headers).status_code == 403
        response = client.get("/api/kit/job/unused", headers={"origin": "http://127.0.0.1:8770"})
        assert response.status_code == 200
        assert response.headers["x-frame-options"] == "SAMEORIGIN"
        assert response.headers["content-security-policy"] == "frame-ancestors 'self'"
        for path in ("/motion.html", "/motion/hook-title/index.html"):
            preview = client.get(path, headers={"sec-fetch-site": "same-origin"})
            assert preview.status_code == 200
            assert "x-frame-options" not in preview.headers
        for parent in ("http://localhost:8765", "http://127.0.0.1:8765"):
            headers = {"referer": parent + "/dashboard/", "sec-fetch-site": "cross-site",
                       "sec-fetch-dest": "iframe", "sec-fetch-mode": "navigate"}
            for path in ("/video-editor.html", "/library.html"):
                preview = client.get(path, headers=headers)
                assert preview.status_code == 200
                assert parent in preview.headers["content-security-policy"]
                assert "x-frame-options" not in preview.headers
                assert "access-control-allow-origin" not in preview.headers
            health_headers = {"origin": parent, "sec-fetch-site": "cross-site"}
            health = client.get("/api/window/health", headers=health_headers)
            assert health.status_code == 200 and health.json()["ready"] is True
            assert health.headers["access-control-allow-origin"] == parent
            assert client.get("/api/kit/config", headers=health_headers).status_code == 403
            assert client.post("/api/kit/setup", headers=health_headers).status_code == 403
        headers["referer"] = "https://untrusted.example/dashboard/"
        assert client.get("/video-editor.html", headers=headers).status_code == 403
        assert client.get("/api/window/health", headers={"origin": "null"}).status_code == 403
        assert client.get("/video-editor.html", headers={"referer": "http://["}).status_code == 400


def setup_stops_after_package_failure():
    import os
    command = """
    function ffmpeg { }
    function npx { }
    function python { $global:LASTEXITCODE = 17 }
    try { & $env:CLIPKIT_SETUP_TEST; exit 2 }
    catch {
        if ($_.Exception.Message -like 'Installing Python packages failed*') { exit 0 }
        Write-Error $_; exit 3
    }
    """
    result = subprocess.run(["powershell", "-NoProfile", "-Command", command],
                            env={**os.environ, "CLIPKIT_SETUP_TEST": str(ROOT / "scripts" / "setup.ps1")},
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def story_input_is_validated():
    import video_edit
    with tempfile.TemporaryDirectory() as tmp:
        raw = str(Path(tmp) / "raw.mp4")
        path = video_edit.stories_file(raw)
        phrases = [{"start": 0, "end": 10, "text": "test"}]
        assert video_edit.stories_from_agent(raw, phrases) is None
        for value in ([], {}, [None], [{"start": 0, "end": 10, "title": None}],
                      [{"start": -1, "end": 10, "title": "x"}],
                      [{"start": 10, "end": 0, "title": "x"}],
                      [{"start": True, "end": 10, "title": "x"}],
                      [{"start": 0, "end": float("inf"), "title": "x"}]):
            path.write_text(json.dumps(value), encoding="utf-8")
            try:
                video_edit.stories_from_agent(raw, phrases)
            except video_edit.VideoEditError:
                pass
            else:
                raise AssertionError(f"invalid story accepted: {value}")
        path.write_text(json.dumps([{"start": 0, "end": 10, "title": " valid "}]), encoding="utf-8")
        result = video_edit.stories_from_agent(raw, phrases)
        assert result[0]["title"] == "valid" and result[0]["end"] == 10


def subtitle_font_dependencies_work():
    import render
    from PIL import ImageFont
    family, path = render._font(None)
    assert family and ImageFont.truetype(str(path), 30).getlength("ทดสอบภาษาไทย") > 0


def speech_settings_and_failures():
    import os
    from types import SimpleNamespace
    from unittest.mock import Mock, patch
    import video_edit
    previous = video_edit._model
    cfg = {"whisper_model": "small", "whisper_device": "cpu", "models_dir": "cache-one"}
    constructor = Mock(return_value=object())
    try:
        video_edit._model = None
        with patch.dict(sys.modules, {"faster_whisper": SimpleNamespace(WhisperModel=constructor)}), \
                patch.dict(os.environ, {"VIDEO_WHISPER_MODEL": ""}), \
                patch.object(video_edit.kitconfig, "_load", return_value=cfg), \
                patch.object(video_edit, "_has_cuda", return_value=True):
            first, engine = video_edit._get_model()
            assert engine == "small/cpu/int8", engine
            constructor.assert_called_once_with("small", device="cpu", compute_type="int8", download_root="cache-one")
            assert video_edit._get_model()[0] is first
            assert constructor.call_count == 1
            cfg["models_dir"] = "cache-two"
            video_edit._get_model()
            assert constructor.call_count == 2
            cfg["whisper_model"] = "medium"
            video_edit._get_model()
            assert constructor.call_args.args == ("medium",)
            video_edit._get_model("tiny")
            assert constructor.call_args.args == ("tiny",)
            cfg["whisper_device"] = "cuda"
            constructor.side_effect = RuntimeError("GPU load failed")
            with patch.object(video_edit, "_enable_cuda_libs"):
                try:
                    video_edit._get_model()
                except video_edit.VideoEditError as exc:
                    assert "GPU load failed" in str(exc)
                else:
                    raise AssertionError("model failure was hidden")
            assert constructor.call_args.kwargs["device"] == "cuda"
            assert video_edit._model is None
            with patch.object(video_edit, "_has_cuda", return_value=False):
                count = constructor.call_count
                try:
                    video_edit._get_model()
                except video_edit.VideoEditError as exc:
                    assert "CUDA is unavailable" in str(exc)
                else:
                    raise AssertionError("unavailable GPU was hidden")
                assert constructor.call_count == count
    finally:
        video_edit._model = previous
    for start, end, window in ((0, 10, 1), (0, 10, 0), (-1, 10, 15), (5, 2, 15), (0, float("nan"), 15)):
        try:
            video_edit.transcribe("unused.mp4", start, end, window=window)
        except video_edit.VideoEditError:
            pass
        else:
            raise AssertionError("invalid transcription input was accepted")


def settings_preserve_config_on_failure():
    from unittest.mock import patch
    from fastapi import HTTPException
    import kit_settings
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "config.json"
        original = {"whisper_device": "cuda", "custom": "keep me"}
        target.write_text(json.dumps(original), encoding="utf-8")
        with patch.object(kit_settings, "CONFIG", target):
            with patch.object(Path, "replace", side_effect=OSError("simulated disk failure")):
                try:
                    kit_settings.save_config(kit_settings.ConfigUpdate(values={"whisper_device": "cpu"}))
                except OSError:
                    pass
                else:
                    raise AssertionError("save failure was hidden")
            assert json.loads(target.read_text()) == original
            assert list(Path(tmp).iterdir()) == [target], "temporary settings file leaked"
            kit_settings.save_config(kit_settings.ConfigUpdate(values={"whisper_device": "cpu"}))
            saved = json.loads(target.read_text())
            assert saved == {"whisper_device": "cpu", "custom": "keep me"}
            try:
                kit_settings.save_config(kit_settings.ConfigUpdate(values={"whisper_device": "unknown"}))
            except HTTPException as exc:
                assert exc.status_code == 400
            else:
                raise AssertionError("invalid device setting was accepted")
            assert json.loads(target.read_text()) == saved


def concurrent_settings_are_preserved():
    from concurrent.futures import ThreadPoolExecutor
    from unittest.mock import patch
    import threading
    import time
    import kit_settings
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "config.json"
        target.write_text('{}', encoding="utf-8")
        read = kit_settings._read_config
        barrier = threading.Barrier(2)
        def delayed_read():
            value = read()
            time.sleep(0.05)
            return value
        def save(values):
            barrier.wait(timeout=5)
            kit_settings.save_config(kit_settings.ConfigUpdate(values=values))
        with patch.object(kit_settings, "CONFIG", target), patch.object(kit_settings, "_read_config", delayed_read):
            with ThreadPoolExecutor(max_workers=2) as pool:
                tasks = [pool.submit(save, {"card_font": "test"}), pool.submit(save, {"whisper_model": "small"})]
                for task in tasks:
                    task.result(timeout=5)
        assert json.loads(target.read_text()) == {"card_font": "test", "whisper_model": "small"}


def local_media_cannot_collide():
    from urllib.parse import unquote
    from unittest.mock import patch
    import hf_build
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        out = root / "out"
        out.mkdir()
        a, b = root / "a", root / "b"
        a.mkdir(); b.mkdir()
        first, second = a / "clip.mp4", b / "clip.mp4"
        first.write_bytes(b"first")
        second.write_bytes(b"other")
        p = out / unquote(hf_build._local(out, str(first)))
        q = out / unquote(hf_build._local(out, str(second)))
        assert p != q and p.read_bytes() == b"first" and q.read_bytes() == b"other"
        with patch("shutil.copy2", side_effect=AssertionError("cache missed")):
            assert out / unquote(hf_build._local(out, str(first))) == p
        first.write_bytes(b"changed")
        with patch("shutil.copy2", side_effect=OSError("interrupted copy")):
            try:
                hf_build._local(out, str(first))
            except OSError:
                pass
            else:
                raise AssertionError("copy failure was hidden")
        assert set((out / "media").iterdir()) == {p, q}
        r = out / unquote(hf_build._local(out, str(first)))
        assert r != p and r.read_bytes() == b"changed" and p.read_bytes() == b"first"


def transcription_process_status_is_truthful():
    from unittest.mock import Mock, patch
    from fastapi import HTTPException
    import video_editor
    with tempfile.TemporaryDirectory() as tmp:
        key = str(Path(tmp).resolve()).lower()
        worker = Mock()
        worker.poll.return_value = None
        try:
            with patch.object(video_editor.video_edit, "scan_folder", return_value=[{}]), \
                    patch.object(video_editor.subprocess, "Popen", return_value=worker) as launch:
                request = video_editor.ScanRequest(path=tmp)
                assert video_editor.project_transcription_status(tmp)["status"] == "idle"
                video_editor.start_project_transcription(request)
                assert launch.call_args.kwargs["stdout"].closed, "parent log handle leaked"
                assert video_editor.project_transcription_status(tmp)["status"] == "running"
                try:
                    video_editor.start_project_transcription(request)
                except HTTPException as exc:
                    assert exc.status_code == 409
                else:
                    raise AssertionError("duplicate transcription started")
                assert launch.call_count == 1
                worker.poll.return_value = 1
                assert video_editor.project_transcription_status(tmp)["status"] == "failed"
                worker.poll.return_value = 0
                assert video_editor.project_transcription_status(tmp)["status"] == "done"
        finally:
            video_editor._transcribe_jobs.pop(key, None)


def transcription_ui_does_not_claim_failed_work_is_done():
    page = (ROOT / "app" / "static" / "video-editor.html").read_text(encoding="utf-8")
    source = page[page.index("async function refreshTranscription("):page.index("async function showTranscriptResults(")]
    test = """
    const source = JSON.parse(require('fs').readFileSync(0, 'utf8'));
    const assert = require('assert');
    (async () => {
      for (const status of ['running', 'done', 'failed', 'idle', 'error']) {
        const label = {textContent: ''}, button = {disabled: true};
        let shown = 0, cleared = 0;
        const api = async () => { if (status === 'error') throw Error('offline'); return {status,code:1,completed:1,takes:2}; };
        const fn = new Function('api','document','window','state','showTranscriptResults', source + ';return refreshTranscription;')(
          api, {getElementById:()=>label}, {clearInterval:()=>cleared++}, {transcribePoll:1}, async()=>shown++);
        await fn('folder', button);
        assert.strictEqual(shown, status === 'done' ? 1 : 0);
        assert.strictEqual(label.textContent.includes('พร้อมเคาะหัวข้อ'), status === 'done');
        if (['done','failed','idle'].includes(status)) { assert(!button.disabled); assert.strictEqual(cleared,1); }
        if (status === 'error') assert(label.textContent.includes('offline'));
      }
    })().catch(e=>{console.error(e);process.exit(1)});
    """
    result = subprocess.run(["node", "-e", test], input=json.dumps(source), capture_output=True,
                            text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr


def launcher_does_not_open_a_dead_server():
    import os
    command = """
    $global:clipkitTestLaunches = 0
    function git { return 'ClipKit' }
    function Start-Process {
        $global:clipkitTestLaunches++
    }
    try {
        & $env:CLIPKIT_START_TEST
        if ($env:CLIPKIT_LAUNCH_CASE -eq 'ready' -and $global:clipkitTestLaunches -eq 1) { exit 0 }
        exit 2
    } catch {
        if ($env:CLIPKIT_LAUNCH_CASE -eq 'failed' -and
            $_.Exception.Message -like 'ClipKit could not start*' -and $global:clipkitTestLaunches -eq 0) { exit 0 }
        Write-Error $_; exit 3
    }
    """
    with tempfile.TemporaryDirectory() as tmp:
        launcher = Path(tmp) / "start.ps1"
        launcher.write_text((ROOT / "app" / "start.ps1").read_text(encoding="utf-8"), encoding="utf-8")
        (Path(tmp) / "control.ps1").write_text("""
        param($Action, $Port)
        if ($env:CLIPKIT_LAUNCH_CASE -eq 'failed') { throw 'ClipKit could not start (mocked controller).' }
        Write-Output '{"state":"succeeded","instance":123}'
        """, encoding="utf-8")
        for case in ("ready", "failed"):
            result = subprocess.run(["powershell", "-NoProfile", "-Command", command],
                                    env={**os.environ, "CLIPKIT_START_TEST": str(launcher),
                                         "CLIPKIT_LAUNCH_CASE": case},
                                    capture_output=True, text=True, timeout=30)
            assert result.returncode == 0, result.stdout + result.stderr


def capcut_unused_materials_are_pruned_safely():
    import capcut_build
    draft = {"tracks": [{"segments": [{"material_id": "video", "extra_material_refs": ["helper"]}]}],
             "materials": {"videos": [{"id": "video"}, {"id": "unused-video"}],
                           "texts": [{"id": "removed-subtitle"}],
                           "helpers": [{"id": "helper", "nested": {"ref": "child"}},
                                       {"id": "child", "ref": "helper"}, {"global_ref": "global"},
                                       {"id": "global"}, {"id": "discarded-click"}],
                           "config": {"keep": True}}}
    assert capcut_build._prune_materials(draft) == 3
    assert [m["id"] for m in draft["materials"]["videos"]] == ["video"]
    assert draft["materials"]["texts"] == []
    assert {m.get("id") for m in draft["materials"]["helpers"]} == {"helper", "child", "global", None}
    assert draft["materials"]["config"] == {"keep": True}
    assert capcut_build._prune_materials(draft) == 0


def name_check_works():
    import sync_team
    assert sync_team.names_in("style from Nina 07".encode()), "a client name was not found"
    assert not sync_team.names_in('icon "ClipKit Nina.lnk"'.encode()), "the allowed icon name was flagged"


for name, fn in list(globals().items()):
    if callable(fn) and fn.__module__ == "__main__" and not name.startswith("_") and name != "check":
        check(name, fn)
print(f"\n{len(FAILED)} failed" if FAILED else "\nall checks passed")
sys.exit(1 if FAILED else 0)
