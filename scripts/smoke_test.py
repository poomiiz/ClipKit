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


def outside_edit_is_caught():
    import capcut_edit
    from video_edit import VideoEditError
    with tempfile.TemporaryDirectory() as t:
        f = Path(t) / "p"
        _fake_project(f, "X")
        capcut_edit._save(f, capcut_edit._load(f), "smoke")
        (f / "draft_content.json").write_text('{"id": "X", "tracks": [], "materials": {}, "edited": 1}', encoding="utf-8")
        try:
            capcut_edit._load(f)
        except VideoEditError:
            return
        raise AssertionError("an edit made outside ClipKit was not caught")



def edits_are_logged():
    # the owner's edits are the data a personal style is learned from: each write records before and after
    import capcut_edit
    with tempfile.TemporaryDirectory() as t:
        f = Path(t) / "p"
        _fake_project(f, "X")
        d = capcut_edit._load(f)
        content = {"text": "สวัสดี", "styles": [{"size": 8.0}]}
        d["materials"]["texts"] = [{"id": "m", "content": json.dumps(content)}]
        d["tracks"] = [{"type": "text", "segments": [{"material_id": "m", "clip": {},
                                                       "target_timerange": {"start": 0, "duration": 1000000}}]}]
        capcut_edit._save(f, d, "smoke")
        content["styles"][0]["size"] = 12.0
        d["materials"]["texts"][0]["content"] = json.dumps(content)
        capcut_edit._save(f, d, "smoke")
        rows = [json.loads(x) for x in (f / capcut_edit.CHANGES).read_text(encoding="utf-8").splitlines()]
        assert [r["added"]["cards"][0]["size"] for r in rows] == [8.0, 12.0], rows
        assert rows[1]["removed"]["cards"][0]["size"] == 8.0, rows[1]
        versions = capcut_edit.history(str(f))
        assert len(versions) == 3 and versions[0].endswith(" start.json.gz"), versions
        capcut_edit.restore(str(f), rows[0]["version"])  # back to size 8
        assert capcut_edit._rows(capcut_edit._load(f))["cards"][0].count('"size": 8.0') == 1



def broken_draft_is_not_written():
    # a segment whose material is gone makes CapCut fail to open the project: refuse it, keep the file as it was
    import capcut_edit
    from video_edit import VideoEditError
    with tempfile.TemporaryDirectory() as t:
        f = Path(t) / "p"
        _fake_project(f, "X")
        before = (f / "draft_content.json").read_text(encoding="utf-8")
        d = capcut_edit._load(f)
        d["tracks"] = [{"type": "video", "segments": [{"material_id": "gone",
                                                        "target_timerange": {"start": 0, "duration": 1}}]}]
        try:
            capcut_edit._save(f, d, "smoke")
        except VideoEditError:
            assert (f / "draft_content.json").read_text(encoding="utf-8") == before, "file changed"
            return
        raise AssertionError("a draft pointing at a missing material was written")



def capcut_saves_are_recorded():
    # the draft bot: an edit saved by CapCut itself lands in the history; a broken one is reported, not kept
    import capcut_edit
    with tempfile.TemporaryDirectory() as t:
        f = Path(t) / "p"
        _fake_project(f, "X")
        assert capcut_edit.record_outside(str(f)) is None and len(capcut_edit.history(str(f))) == 1
        assert capcut_edit.record_outside(str(f)) is None and len(capcut_edit.history(str(f))) == 1, "unchanged kept"
        d = json.loads((f / "draft_content.json").read_text(encoding="utf-8"))
        d["materials"]["texts"] = [{"id": "m", "content": json.dumps({"text": "จาก CapCut", "styles": [{"size": 9.0}]})}]
        d["tracks"] = [{"type": "text", "segments": [{"material_id": "m", "clip": {},
                                                       "target_timerange": {"start": 0, "duration": 1000000}}]}]
        (f / "draft_content.json").write_text(json.dumps(d), encoding="utf-8")
        assert capcut_edit.record_outside(str(f)) is None and len(capcut_edit.history(str(f))) == 2
        assert "จาก CapCut" in (f / capcut_edit.CHANGES).read_text(encoding="utf-8")
        d["tracks"][0]["segments"][0]["material_id"] = "gone"
        (f / "draft_content.json").write_text(json.dumps(d), encoding="utf-8")
        assert "missing material" in capcut_edit.record_outside(str(f))
        assert len(capcut_edit.history(str(f))) == 2, "a broken save was kept as a version"



def autosave_profile_reads_the_log():
    # ClipKit - Autosave: the style profile comes from the change log, the AI's own build is not counted
    import capcut_edit
    import autosave_profile
    with tempfile.TemporaryDirectory() as t:
        f = Path(t) / "p"
        _fake_project(f, "X")
        d = capcut_edit._load(f)
        d["materials"]["texts"] = [{"id": "m", "content": json.dumps({"text": "AI", "styles": [{"size": 8.0}]})}]
        d["tracks"] = [{"type": "text", "segments": [{"material_id": "m", "clip": {},
                                                       "target_timerange": {"start": 0, "duration": 1000000}}]}]
        capcut_edit._save(f, d, "capcut_build")
        d["materials"]["texts"][0]["content"] = json.dumps({"text": "คน", "styles": [{"size": 12.0}]})
        capcut_edit._save(f, d, "subs")
        prof = autosave_profile.build(Path(t))
        assert prof["edits"] == 1 and prof["by_op"] == [("subs", 1)], prof
        size = next(c for c in prof["changed"] if c["measure"] == "size")
        assert (size["before"], size["after"]) == (8.0, 12.0), size
        # the last edited project's subtitle look becomes presets/my-style.json (here: a temp file)
        style = lambda text, rgb: json.dumps({"text": text, "styles": [{"size": 22.0, "fill": {"content": {"solid": {"color": rgb}}}}]})  # noqa: E731
        d["materials"]["texts"] = [{"id": "m", "content": style("ขาว", [1, 1, 1])}, {"id": "e", "content": style("ส้ม", [1, 0.5, 0])}]
        d["tracks"][0]["segments"] = [{"material_id": i, "clip": {"transform": {"y": -0.4}},
                                       "target_timerange": {"start": n * 1000000, "duration": 1000000}} for n, i in enumerate("me")]
        capcut_edit._save(f, d, "subs")
        autosave_profile.MY_STYLE = Path(t) / "my-style.json"
        prof = autosave_profile.write(Path(t), Path(t) / "out")
        mine = json.loads(autosave_profile.MY_STYLE.read_text(encoding="utf-8"))
        assert (mine["normal"]["color"], mine["emphasis"]["color"]) == ("#ffffff", "#ff8000"), mine
        assert (Path(t) / "out" / "profile.md").is_file() and prof["my_style"]["from"] == "p", prof["my_style"]


def pictures_are_stills():
    # a picture probed as a 0.04 s video showed for one frame
    import video_edit
    assert video_edit.is_image("a.JPG") and video_edit.is_image("b.png") and not video_edit.is_image("c.mp4")


def subtitles_stay_on_one_line():
    # a long subtitle wrapped to two lines and ran off the frame: it goes on as the next piece instead
    import render
    from PIL import ImageFont
    f, px, w = render.DEFAULT_FONT, 120.0, 900.0
    font = ImageFont.truetype(str(f), 100)
    text = "ถ้าเราไม่รู้ว่าคุณค่าของเราอยู่ตรงไหน เราก็จะไม่มีวันรู้ว่าควรขายอะไรให้ใคร in a very long English tail"
    pieces = render.one_line(text, f, px, w, 1.0, 9.0)
    assert len(pieces) > 1 and "".join(x for x, *_ in pieces).replace(" ", "") == text.replace(" ", ""), pieces
    for piece, a, b, size in pieces:
        assert "\n" not in piece and 1.0 <= a < b <= 9.0, piece
        assert font.getlength(piece) * size / 100 <= w + 1, (piece, font.getlength(piece) * size / 100)
    # two emphasis lines in a row stack in two beats; a held white line keeps them replacing each other
    assert render.stacks(["color", "color", "color", None, "hold", "color"]) == {0: 1}
    assert render.stacks(["color", "hold", "color"]) == {}
    p = render.pair_look({"preset": "4-levels"})
    assert p["caption_shadow"] and p["second"] and p["second_at"] == (0.3, -6.0) and p["caption_lang"] == "en"


def hand_fixes_are_learned():
    # the same misheard word had to be fixed by hand in every clip
    import spelling
    keep = spelling.FILE
    with tempfile.TemporaryDirectory() as t:
        spelling.FILE = Path(t) / "corrections.json"
        try:
            assert spelling.learn("มันน่าจะดีคัป", "มันน่าจะดีครับ") == [("คัป", "ครับ")]
            assert spelling.fix("โอเคคัป") == "โอเคครับ"
            assert spelling.fix("ไปที่กองทัพ") == "ไปที่กองทัพ"  # whole words only
        finally:
            spelling.FILE = keep


def stories_are_not_transcribed_twice():
    # run_clip transcribed the whole video, then Whisper ran again on every story's own range
    import capcut_edit
    import video_edit
    with tempfile.TemporaryDirectory() as t:
        video = Path(t) / "talk.mp4"
        video.write_bytes(b"x")
        video_edit.transcript_file(str(video)).write_text(json.dumps([
            {"start": 1.0, "end": 3.0, "text": "หนึ่ง", "words": [[1.0, 3.0, "หนึ่ง"]]},
            {"start": 10.0, "end": 12.0, "text": "สอง", "words": [[10.0, 11.0, "ส"], [11.0, 12.0, "อง"]]},
            {"start": 20.0, "end": 22.0, "text": "สาม", "words": []}]), encoding="utf-8")
        got = capcut_edit._from_transcript(str(video), 9.0, 15.0)
        assert got == [{"start": 1.0, "end": 3.0, "text": "สอง", "words": [[1.0, 2.0, "ส"], [2.0, 3.0, "อง"]]}], got
        assert capcut_edit._from_transcript(str(video), 11.0, 15.0) is None, "a phrase cut by the edge was reused"


def run_clip_follows_speech_language():
    # run_clip passed "th" to the whole-file transcribe, so config.json "speech_language" never reached the CLI
    import run_clip
    import video_edit
    asked = []
    keep = video_edit.transcribe, video_edit.probe
    video_edit.transcribe = lambda path, start, end, language=None, model_size=None: asked.append(language) or []
    video_edit.probe = lambda path: {"duration": 10.0}
    try:
        with tempfile.TemporaryDirectory() as t:
            video = Path(t) / "talk.mp4"
            video.write_bytes(b"x")
            run_clip.stories(str(video), 60)
    finally:
        video_edit.transcribe, video_edit.probe = keep
    assert asked == [None], f"run_clip chose the language itself: {asked}"


def run_clip_logs_step_times_for_the_benchmark():
    # The CLI adapter must associate step records with the active trial, not just a basename.
    import run_clip
    from benchmark_timing import TimingLog
    with tempfile.TemporaryDirectory() as t:
        keep = run_clip.TIMING
        log = Path(t) / "timings.jsonl"
        run_clip.TIMING = TimingLog(log, str(Path(t) / "talk.mp4"), "smoke")
        try:
            run_clip.timed("step", lambda: None)
        finally:
            run_clip.TIMING = keep
        row = json.loads(log.read_text(encoding="utf-8"))
    assert (row["video"], row["trial_id"], row["event"]) == ("talk.mp4", "smoke", "step"), row


def benchmark_measurements_are_isolated():
    import unittest
    import benchmark_test
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromModule(benchmark_test).run(result)
    assert result.wasSuccessful(), result.failures + result.errors


def saved_stories_come_back_after_restart():
    # the split is saved beside the video; after ClipKit restarts, opening the file shows it again with no new AI round
    import video_editor
    from fastapi import HTTPException
    with tempfile.TemporaryDirectory() as t:
        video = str(Path(t) / "talk.mp4")
        Path(video).write_bytes(b"x")
        keep = video_editor._story_jobs.path
        video_editor._story_jobs.path = Path(t) / "jobs-story-plan.json"  # keep test jobs out of this machine's state/
        try:
            video_editor.story_plan_status(video)
            raise AssertionError("a file never split returned a plan")
        except HTTPException as exc:
            assert exc.status_code == 404
        Path(video + ".transcript.json").write_text(json.dumps([{"start": 1.0, "end": 9.0, "text": "เงิน"}]), encoding="utf-8")
        Path(video + ".stories.json").write_text(json.dumps([{"title": "เงิน", "start": 1, "end": 9}]), encoding="utf-8")
        job = video_editor.story_plan_status(video)
        assert job["status"] == "done" and job["stories"][0]["title"] == "เงิน" and job["duration"] == 9.0, job
        video_editor._story_jobs.pop(video)
        video_editor._story_jobs.path = keep


def name_check_works():
    import sync_team
    assert sync_team.names_in(("style from Ni" + "na 07").encode()), "a client name was not found"  # split: this file is synced too
    assert not sync_team.names_in("github.com/poomiiz/ClipKit".encode()), "the allowed repo link was flagged"
    assert not sync_team.names_in("github.com/poomiiz/EditorKrab".encode()), "the new repo link was flagged"


def preset_pack_roundtrip():
    # a .editorkrab made on one machine installs on another, and never overwrites a look that is already there
    import preset_pack as pp
    real = pp.KIT
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        src, dst = Path(a), Path(b)
        for k in (src, dst):
            for d in ("presets", "motion", "fonts"):
                (k / d).mkdir()
        shutil.copy(ROOT / "presets" / "default.json", src / "presets" / "warm.json")
        shutil.copytree(ROOT / "motion" / "cover-a", src / "motion" / "cover-warm")
        shutil.copytree(ROOT / "motion" / "hook-title", src / "motion" / "warm-hook")
        try:
            pp.KIT = src
            f = pp.make_pack(src, {"id": "warm", "name": "Warm", "tier": "team", "subtitles": ["warm"],
                                   "covers": ["cover-warm"], "motion": ["warm-hook"]})
            assert f.suffix == ".editorkrab", f
            pp.KIT = dst
            old = f.with_suffix(".clipkit")   # packs shared before the rename still install
            shutil.copy(f, old)
            pp.install_pack(old)
            assert (dst / "presets" / "warm.json").is_file() and (dst / "motion" / "cover-warm" / "index.html").is_file()
            assert pp.items()["motion"] == ["warm-hook"], pp.items()
            try:
                pp.install_pack(f)
                raise AssertionError("second install overwrote the first")
            except pp.PackError:
                pass
            try:
                pp.check_manifest({"format": 1, "id": "x", "name": "x", "tier": "basic", "covers": ["cover-a"]})
                raise AssertionError("a basic pack with 1 cover passed")
            except pp.PackError:
                pass
        finally:
            pp.KIT = real


def style_lab_previews_and_keeps():
    # a style is only kept after its preview exists, never over another one, and a broken colour is refused
    import style_lab
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        keep = style_lab.lab, style_lab.PRESETS, style_lab.PREVIEWS
        keep += (style_lab.PARTS,)
        style_lab.lab = lambda: t / "lab"
        style_lab.PRESETS, style_lab.PREVIEWS, style_lab.PARTS = t / "presets", t / "presets" / "previews", t / "parts"
        (t / "lab").mkdir(); (t / "presets").mkdir()
        try:
            proj = t / "proj"
            proj.mkdir()
            seg = lambda i, y: {"material_id": i, "clip": {"transform": {"x": 0, "y": y}, "scale": {"x": 1}}}  # noqa: E731
            mat = lambda i, size, rgb: {"id": i, "content": json.dumps({"text": "x", "styles": [{"size": size,  # noqa: E731
                  "fill": {"content": {"solid": {"color": rgb}}}, "strokes": [{"width": 0.05}]}]})}
            (proj / "draft_content.json").write_text(json.dumps({
                "materials": {"texts": [mat("a", 24, [1, 1, 1]), mat("b", 30, [1, 0.5, 0])]},
                "tracks": [{"type": "text", "segments": [seg("a", -0.3), seg("b", -0.45)]}]}), encoding="utf-8")
            x = style_lab.start(str(proj))
            assert x["status"] == "ready" and Path(x["gif"]).is_file() and Path(x["png"]).is_file(), x
            # the style page groups by the normal line: same normal, other emphasis = one family, two looks
            other = {**x["style"], "emphasis": {**x["style"]["emphasis"], "color": "#051192"}}
            assert style_lab.looks(other)[0] == x["family"] and style_lab.looks(other)[1] != x["look"], (x["family"], x["look"])
            assert style_lab.looks({**x["style"], "normal": {**x["style"]["normal"], "size": 40}})[0] != x["family"]
            assert style_lab.save(x["folder"], "Mine") == {"parts": ["main"], "preset": "my-mine"}
            got = style_lab.collection()
            assert got["presets"][0]["gif"] and got["parts"]["main"][0]["gif"], "kept style lost its preview"
            assert style_lab.compose("mix", "mine")["preset"] == "my-mix"
            link = style_lab.share("my-mix")["url"]
            assert link.startswith("https://github.com/") and "%5Bstyle%5D" in link, link
            shared = t / "shared.json"
            shared.write_text((t / "presets" / "my-mix.json").read_text(encoding="utf-8"), encoding="utf-8")
            assert style_lab.approve(shared, "mix")["preset"] == "team-mix"
            assert "source" not in json.loads((t / "presets" / "team-mix.json").read_text(encoding="utf-8"))
            assert style_lab.collection()["team"][0]["gif"], "approved style has no preview"
            try:
                style_lab.save(x["folder"], "other", ["caption"])
                raise AssertionError("a part the style does not have was kept")
            except ValueError:
                pass
            try:
                style_lab.save(x["folder"], "mine")
                raise AssertionError("a kept style was overwritten")
            except FileExistsError:
                pass
            try:
                style_lab.check({"normal": {"size": 22, "y": 0, "color": "white", "outline": "#000000", "outline_width": 0},
                                 "emphasis": x["style"]["emphasis"]})
                raise AssertionError("a colour that is not #rrggbb was accepted")
            except ValueError:
                pass
        finally:
            style_lab.lab, style_lab.PRESETS, style_lab.PREVIEWS, style_lab.PARTS = keep


def new_clip_keeps_its_own_sound():
    # a sped-up template clip with enhanced voice put the template's sound out of step with the new clip's picture
    import video_edit
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        clip = t / "clip.mp4"
        subprocess.run([video_edit.FFMPEG, "-v", "error", "-f", "lavfi", "-i", "testsrc=s=160x120:d=3:r=30", "-f", "lavfi",
                        "-i", "sine=d=3", "-shortest", str(clip)], check=True)
        tpl, root = t / "tpl", t / "drafts"
        tpl.mkdir(), root.mkdir()
        (tpl / "draft_content.json").write_text(json.dumps({"materials": {
            "videos": [{"id": "v", "path": "old.MOV", "intensifies_audio_path": "old_enhanced.wav", "reverse_path": "old_rev.mp4"}],
            "speeds": [{"id": "s", "type": "speed", "mode": 0, "speed": 1.5, "curve_speed": None}],
            "audio_fades": [{"id": "f", "type": "audio_fade"}]},
            "tracks": [{"type": "video", "segments": [{"id": "a", "material_id": "v", "speed": 1.5, "reverse": True,
                                                       "intensifies_audio": True, "volume": 0.2, "extra_material_refs": ["s", "f"],
                                                       "clip": {"scale": {"x": 1, "y": 1}, "transform": {"x": 0, "y": 0}}}]}]}),
            encoding="utf-8")
        keep = video_edit.CAPCUT_TEMPLATE_DRAFT
        video_edit.CAPCUT_TEMPLATE_DRAFT = str(tpl)
        try:
            r = video_edit.create_capcut_draft(str(clip), "x", 0.0, 2.5, cuts=[{"start": 1.0, "end": 1.3}], drafts_root=str(root))
        finally:
            video_edit.CAPCUT_TEMPLATE_DRAFT = keep
        d = json.loads((Path(r["draft_path"]) / "draft_content.json").read_text(encoding="utf-8"))
        m = d["materials"]
        assert m["videos"][0]["intensifies_audio_path"] == m["videos"][0]["reverse_path"] == "", m["videos"][0]
        for s in d["tracks"][0]["segments"]:
            assert (s["speed"], s["reverse"], s["intensifies_audio"], s["volume"]) == (1.0, False, False, 1.0), s
            refs = set(s["extra_material_refs"])
            assert not any(f["id"] in refs for f in m.get("audio_fades", [])), "template fade on every cut"
            assert all(x["speed"] == 1.0 for x in m["speeds"] if x["id"] in refs), m["speeds"]

def web_ai_answers_are_checked():
    # the web AI's JSON goes into the same files the local agent writes; a wrong answer writes nothing
    import capcut_edit
    import web_ai_json as web_ai
    from video_edit import VideoEditError
    with tempfile.TemporaryDirectory() as t:
        video = Path(t) / "ep.mov"
        video.write_bytes(b"")
        (Path(t) / "ep.mov.transcript.json").write_text(json.dumps(
            [{"start": 0.0, "end": 2.0, "text": "สวัสดี"}, {"start": 10.0, "end": 14.0, "text": "เรื่องเงิน"}]), encoding="utf-8")
        assert "เรื่องเงิน" in web_ai.export_stories(str(video)).read_text(encoding="utf-8")
        # what the person typed before the split leads the packet; clearing the box removes it
        import video_editor
        video_editor._story_jobs.path = Path(t) / "jobs-story-plan.json"
        video_editor._story_jobs[str(video)] = {"status": "waiting"}  # a split already going: no Whisper here
        video_editor.story_plan(video_editor.StoryPlanRequest(file=str(video), brief="  vlog สบายๆ เน้นช่วงตลก "))
        assert video_editor.brief(str(video)) == {"brief": "vlog สบายๆ เน้นช่วงตลก"}
        packet = web_ai.export_stories(str(video)).read_text(encoding="utf-8")
        assert packet.index("vlog สบายๆ เน้นช่วงตลก") < packet.index("เรื่องเงิน"), packet[:300]
        video_editor.story_plan(video_editor.StoryPlanRequest(file=str(video)))  # no brief sent: kept
        assert video_editor.brief(str(video))["brief"]
        video_editor.story_plan(video_editor.StoryPlanRequest(file=str(video), brief=""))
        assert video_editor.brief(str(video)) == {"brief": ""}
        assert "ความต้องการของผู้ตัดต่อ" not in web_ai.export_stories(str(video)).read_text(encoding="utf-8")
        head = {"clipkit_web_ai": 1, "step": "stories", "video": "ep.mov"}
        for bad in ({**head, "video": "other.mov", "stories": [{"title": "a", "start": 9, "end": 15}]},
                    {**head, "stories": [{"title": "a", "start": 3, "end": 5}]}):  # wrong video / no speech
            try:
                web_ai.import_answer("stories", str(video), json.dumps(bad))
                raise AssertionError(f"accepted {bad}")
            except VideoEditError:
                pass
        assert not (Path(t) / "ep.mov.stories.json").exists()
        ans = "here:\n```json\n" + json.dumps({**head, "stories": [{"title": "เงิน", "start": 9, "end": 15}]}) + "\n```"
        assert web_ai.import_answer("stories", str(video), ans)["stories"][0]["end"] == 15
        # an AI on this machine saves its answer next to the file instead: imported once, then gone
        assert web_ai.import_answer("stories", str(video), "") == {"waiting": True}
        saved = web_ai.answer_file("stories", str(video))
        assert str(saved) in web_ai.export_stories(str(video)).read_text(encoding="utf-8")
        saved.write_text(json.dumps({**head, "stories": [{"title": "เงิน", "start": 9, "end": 14}]}), encoding="utf-8")
        assert web_ai.import_answer("stories", str(video), "")["stories"][0]["end"] == 14 and not saved.exists()

        proj = Path(t) / "proj"
        proj.mkdir()
        keep = capcut_edit.read_draft
        capcut_edit.read_draft = lambda p: {"subtitles": [{"start": 0.0, "end": 2.0, "text": "เงินไม่พอใช้"}]}
        try:
            web_ai.export_clip(str(proj))
            assert "ยาวราว" not in web_ai.export_clip(str(proj)).read_text(encoding="utf-8")
            aimed = web_ai.export_clip(str(proj), 1.5).read_text(encoding="utf-8")
            assert "ยาวราว 1.5 นาที" in aimed and aimed.index("ยาวราว") < aimed.index("## 1. Subtitle"), "the length aim is not in the cut rules"
            good = {"clipkit_web_ai": 1, "step": "clip", "project": "proj", "hook": [{"text": "เงินหมด", "color": "red"}],
                    "lines": [{"n": 1, "items": [["เงิน", "ไม่พอใช้", "empty wallet", {"look": "red"}]]}]}
            for bad in ({**good, "lines": [{"n": 1, "items": [["เงิน", "พอใช้"]]}]},  # words changed
                        {**good, "hook": [{"text": "x", "color": "blue"}]},
                        {**good, "cut": [1]}):  # nothing left
                try:
                    web_ai.import_answer("clip", str(proj), json.dumps(bad))
                    raise AssertionError(f"accepted {bad}")
                except VideoEditError:
                    pass
            assert not (proj / "clipkit_punch.json").exists()
            web_ai.import_answer("clip", str(proj), json.dumps(good))
        finally:
            capcut_edit.read_draft = keep
        punch = json.loads((proj / "clipkit_punch.json").read_text(encoding="utf-8"))
        assert punch == {"เงินไม่พอใช้": [["เงิน", "ไม่พอใช้", "empty wallet", {"look": "red"}]]}, punch
        assert json.loads((proj / "clipkit_hook.json").read_text(encoding="utf-8"))[0]["color"] == "red"


def progress_bar_fills_over_the_clip():
    # the bar is empty at the start, half way at the middle and full at the end of a 2 s clip
    import render
    import numpy as np
    bar, out = render.progress_bar("[vo]", 2.0, 320, 180)
    assert out == "[pb]", out
    for at, lit in ((0.05, 0.0), (1.0, 0.5), (1.96, 1.0)):
        r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=320x180:r=25:d=2",
                            "-filter_complex", "[0:v]null[vo]" + bar, "-map", out, "-ss", str(at), "-frames:v", "1",
                            "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True)
        row = np.frombuffer(r.stdout, np.uint8).reshape(180, 320)[-2]
        assert abs((row > 128).mean() - lit) < 0.06, (at, (row > 128).mean())
    try:
        render.progress_bar("[vo]", 0, 320, 180)
        raise AssertionError("a 0 s clip got a bar")
    except render.VideoEditError:
        pass


def emoji_pops_on_keywords():
    # one emoji per keyword phrase, 2.5 s apart at least, none under the clip title; drawn only during its beat
    import render
    import numpy as np
    beats = render.emoji_beats([(0.5, 2.0, "วันนี้ได้เงินเยอะ"), (1.0, 3.0, "ไฟไหม้"), (4.0, 5.0, "ธรรมดา"),
                                (6.0, 7.0, "I have an idea")])
    assert [(b["at"], Path(b["file"]).stem) for b in beats] == [(0.5, "1f4b0"), (6.0, "1f4a1")], beats
    assert render.emoji_beats([(0.5, 2.0, "เงิน")], skip_until=3) == []
    for code in render.EMOJI:
        assert (render.EMOJI_DIR / f"{code}.png").is_file(), code
    piece, out = render.emoji_overlay("[vo]", 1, 0, {"at": 0.5, "dur": 1.0, "file": ""}, 320, 568)
    es, ex, ey = render.emoji_box(320, 568)
    for at, shown in ((0.2, False), (0.9, True), (1.8, False)):
        r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=320x568:r=25:d=2",
                            "-loop", "1", "-i", str(render.EMOJI_DIR / "1f525.png"),
                            "-filter_complex", "[0:v]null[vo]" + piece, "-map", out, "-ss", str(at), "-frames:v", "1",
                            "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True)
        box = np.frombuffer(r.stdout, np.uint8).reshape(568, 320)[ey:ey + es, ex:ex + es]
        assert ((box > 40).mean() > 0.3) == shown, (at, (box > 40).mean())

def speed_ramp_eases_into_normal_speed():
    # a source whose brightness is 25 x its own time: the ramped copy runs 3x at first, 1x after 0.6 s
    import render
    import numpy as np
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "count.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "nullsrc=s=64x64:r=30:d=6,geq=lum='T*25':cb=128:cr=128",
                        "-c:v", "libx264", "-crf", "1", "-pix_fmt", "yuv420p", str(src)], check=True)
        out = render.speed_ramp(str(src), 2.0, Path(tmp) / "c")
        assert render.speed_ramp(str(src), 2.0, Path(tmp) / "c") == out  # made once, then reused
        info = render.probe(out)
        assert abs(info["duration"] - 2.0) < 0.1, info
        for at, source_t in ((0.3, 0.75), (0.6, 1.2), (1.6, 2.2)):
            r = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(at), "-i", out, "-frames:v", "1", "-f", "rawvideo",
                                "-pix_fmt", "yuv420p", "-"], capture_output=True, check=True)
            got = np.frombuffer(r.stdout[:64 * 64], np.uint8).mean() / 25  # the Y plane, as geq wrote it
            assert abs(got - source_t) < 0.12, (at, got, source_t)
    try:
        render.speed_ramp("x", 0, Path("."))
        raise AssertionError("a 0 s b-roll got a ramp")
    except render.VideoEditError:
        pass

for name, fn in list(globals().items()):
    if callable(fn) and fn.__module__ == "__main__" and not name.startswith("_") and name != "check":
        check(name, fn)
print(f"\n{len(FAILED)} failed" if FAILED else "\nall checks passed")
sys.exit(1 if FAILED else 0)
