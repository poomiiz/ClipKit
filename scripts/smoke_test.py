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


def name_check_works():
    import sync_team
    assert sync_team.names_in("style from Nina 07".encode()), "a client name was not found"
    assert not sync_team.names_in('icon "ClipKit Nina.lnk"'.encode()), "the allowed icon name was flagged"


def preset_pack_roundtrip():
    # a .clipkit made on one machine installs on another, and never overwrites a look that is already there
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
            pp.KIT = dst
            pp.install_pack(f)
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


for name, fn in list(globals().items()):
    if callable(fn) and fn.__module__ == "__main__" and not name.startswith("_") and name != "check":
        check(name, fn)
print(f"\n{len(FAILED)} failed" if FAILED else "\nall checks passed")
sys.exit(1 if FAILED else 0)
