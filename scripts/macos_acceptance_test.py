"""Mac CI proof for fonts, Thai ASS rendering and an isolated owned HyperFrames preview.

The default/self-check mode never launches preview. --live runs only on a disposable GitHub Mac
runner; it does not establish file-dialog, Finder Trash, browser or native CapCut acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import select
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.parse
import urllib.request
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def prepare_proof(path: Path) -> Path:
    target = path.absolute()
    allowed = ROOT / "bug_reports"
    require(not any(parent.is_symlink() for parent in (target, *target.parents)),
            "Proof folder has a linked parent")
    target = target.resolve()
    require(target != allowed and target.is_relative_to(allowed), "Proof folder must be inside bug_reports")
    require(not target.exists(), "Proof folder already exists; choose a new proof folder")
    target.mkdir(parents=True)
    return target.resolve()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def image_evidence(path: Path) -> dict:
    from PIL import Image
    with Image.open(path) as image:
        require(image.size == (640, 360), "Unexpected subtitle frame dimensions")
        grey = image.convert("L")
        bright = sum(value > 100 for value in grey.getdata())
        require(300 < bright < 640 * 360 // 3, "Subtitle frame is blank or covers the entire canvas")
        return {"width": image.width, "height": image.height, "bright_pixels": bright,
                "sha256": file_hash(path)}


def font_evidence() -> tuple[dict, Path, str]:
    import host_platform as host
    bundled = ROOT / "fonts" / "Kanit-Bold.ttf"
    require(bundled.is_file(), "Bundled Kanit is missing")
    family = host._font_family(bundled)
    names = host.font_names()
    require(family in names, "Bundled Kanit family was not discovered")
    require(host.find_font(str(bundled)) == bundled, "Bundled Kanit direct lookup failed")
    found = host.find_font(family)
    require(found is not None and found.is_file() and host._font_family(found) == family,
            "Kanit family lookup failed")
    system = [path for path in host._font_files() if path.is_relative_to(Path("/System/Library/Fonts"))]
    require(bool(system), "Actual macOS system fonts were not discovered")
    return {"status": "PASS", "families": len(names), "system_font_files": len(system),
            "bundled_family": family, "bundled_sha256": file_hash(bundled)}, bundled, family


def render_evidence(proof: Path, font: Path, family: str) -> dict:
    require(shutil.which("ffmpeg") is not None, "ffmpeg is missing")
    with tempfile.TemporaryDirectory(prefix="editor-krab-ass-") as folder:
        fixture = Path(folder)
        (fixture / "fonts").mkdir()
        shutil.copyfile(font, fixture / "fonts" / font.name)
        ass = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 640\nPlayResY: 360\nWrapStyle: 2\n\n"
               "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
               "BorderStyle, Outline, Shadow, Alignment, Encoding\n"
               f"Style: S,{family},42,&H00FFFFFF,&H00000000,1,1,0,5,1\n\n"
               "[Events]\nFormat: Layer, Start, End, Style, Text\n"
               "Dialogue: 0,0:00:00.00,0:00:01.00,S,ทดสอบภาษาไทย น้ำใจ ก้าวหน้า\n")
        (fixture / "caption.ass").write_text(ass, encoding="utf-8")
        frame = proof / "thai-subtitle.png"
        result = subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "info",
                                 "-f", "lavfi", "-i", "color=c=black:s=640x360:r=1:d=1",
                                 "-vf", "ass=caption.ass:fontsdir=fonts", "-frames:v", "1",
                                 "-threads", "1", str(frame)], cwd=fixture, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=60)
        require(result.returncode == 0, "Thai ASS render failed: " + result.stderr[-1200:])
        selection = [line for line in result.stderr.splitlines() if "fontselect:" in line]
        require(bool(selection) and any("Kanit" in line for line in selection),
                "libass did not report selecting Kanit")
        require("glyph" not in result.stderr.casefold(), "libass reported a missing/fallback glyph")
        shutil.copyfile(fixture / "caption.ass", proof / "thai-subtitle.ass")
        return {"status": "PASS", "renderer": "ffmpeg/libass", "requested_family": family,
                **image_evidence(frame)}


def preview_preflight() -> None:
    require(os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted",
            "Preview acceptance requires a dedicated GitHub-hosted runner")


def preview_evidence() -> dict:
    import control
    import host_platform as host
    import kit_settings as kit
    import psutil
    preview_preflight()
    require(not kit._hf_preview, "Acceptance process already tracks a preview")
    npx = shutil.which("npx")
    require(npx is not None, "npx is missing")
    source = ROOT / "motion" / "sentence-pair"
    require(source.is_dir() and not any(path.is_symlink() for path in (source, *source.rglob("*"))),
            "Public preview fixture is missing or linked")
    originals = {path.relative_to(source).as_posix(): file_hash(path)
                 for path in source.rglob("*") if path.is_file()}
    fixture = Path(tempfile.mkdtemp(prefix="editor-krab-preview-")).resolve()
    project = fixture / "sentence-pair"
    shutil.copytree(source, project)
    # CLI stamps hf-ids in its temp copy. A unique comment proves the HTTP response is this fixture.
    marker = "editor-krab-acceptance-" + fixture.name
    html = (project / "index.html").read_text(encoding="utf-8")
    require("<html " in html, "Public fixture has no HTML root")
    (project / "index.html").write_text(
        html.replace("<html ", '<html data-editor-krab-acceptance="' + marker + '" ', 1), encoding="utf-8")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    require(control.port_owner(port) is None and control.port_free(port), "Test preview port is occupied")
    sentinel = None
    sentinel_identity = None
    descendants = []
    stopped = False

    def children(pid):
        snapshots = []
        for child in psutil.Process(pid).children(recursive=True):
            try:
                snapshots.append(host.process_identity(child.pid))
            except psutil.NoSuchProcess:
                pass
        return snapshots

    try:
        sentinel = subprocess.Popen([sys.executable, "-u", "-c",
                                     "import time; print('ready', flush=True); time.sleep(600)",
                                     "puppeteer_dev_chrome_profile"],
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        require(bool(select.select([sentinel.stdout], [], [], 10)[0]), "Sentinel did not start")
        require(sentinel.stdout.readline().strip() == "ready", "Unexpected sentinel readiness")
        sentinel_identity = host.process_identity(sentinel.pid)
        env = {**os.environ, "HYPERFRAMES_SKIP_SKILLS": "1", "HYPERFRAMES_NO_AUTO_INSTALL": "1",
               "HYPERFRAMES_NO_UPDATE_CHECK": "1", "HYPERFRAMES_NO_TELEMETRY": "1"}
        kit._start_preview([npx, "--yes", f"hyperframes@{kit.HF_VERSION}", "preview", str(project),
                            "--port", str(port), "--no-open"], project, env)
        proc, expected = kit._hf_preview["proc"], kit._hf_preview["identity"]
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline = time.monotonic() + 180
        config = None
        while time.monotonic() < deadline:
            require(proc.poll() is None, "Preview launcher exited before readiness")
            current = host.process_identity(proc.pid)
            changed = [field for field in ("created", "parent", "executable", "command")
                       if getattr(expected, field) != getattr(current, field)]
            require(not changed, "Preview launch identity changed: " + ", ".join(changed))
            owner = control.port_owner(port)
            if owner is not None:
                descendants = children(proc.pid)
                own = [expected, *descendants]
                require(any(host.same_process(item, owner) for item in own),
                        "Preview port belongs to an unrelated process")
                try:
                    with opener.open(f"http://127.0.0.1:{port}/__hyperframes_config", timeout=3) as response:
                        config = json.load(response)
                    break
                except (OSError, ValueError):
                    pass
            time.sleep(0.25)
        require(config is not None, "Preview did not become ready on the requested test port")
        require(config.get("isHyperframes") is True and config.get("pid") == owner.pid and
                config.get("version") == kit.HF_VERSION and
                Path(config.get("projectDir", "")).resolve() == project.resolve() and
                config.get("projectName") == project.name, "Preview reported another project or process")
        encoded = urllib.parse.quote(project.name, safe="")
        with opener.open(f"http://127.0.0.1:{port}/api/projects/{encoded}/files/index.html", timeout=5) as response:
            require(marker in json.load(response)["content"], "Preview did not serve the temp source")
        with opener.open(f"http://127.0.0.1:{port}/api/projects/{encoded}/preview", timeout=5) as response:
            require(response.status == 200 and marker in response.read().decode("utf-8"),
                    "Preview did not serve the compiled temp composition")
        require(sentinel.poll() is None and host.same_process(sentinel_identity, host.process_identity(sentinel.pid)),
                "Preview startup affected the unrelated sentinel")
        descendants = children(proc.pid)
        kit._stop_studio()
        stopped = True
        require(proc.poll() is not None and control.port_owner(port) is None and control.port_free(port),
                "Owned preview cleanup left the test port occupied")
        for child in descendants:
            try:
                require(not host.same_process(child, host.process_identity(child.pid), reparented=True),
                        "Owned preview child remains alive")
            except psutil.NoSuchProcess:
                pass
        require(sentinel.poll() is None and host.same_process(sentinel_identity, host.process_identity(sentinel.pid)),
                "Preview cleanup affected the unrelated sentinel")
        require(all(file_hash(source / name) == digest for name, digest in originals.items()),
                "Public source project changed")
        return {"status": "PASS", "version": kit.HF_VERSION, "source": "motion/sentence-pair",
                "http_source_and_compiled_marker": True, "port_released": True,
                "owned_children_checked": len(descendants), "unrelated_sentinel_survived": True,
                "sentinel_has_browser_marker": True, "sentinel_is_orphan": False,
                "flags": ["--foreground", "--no-open"],
                "automatic_updates_skills_and_telemetry": "disabled", "media_proxy": "default"}
    finally:
        try:
            if not stopped and kit._hf_preview:
                kit._stop_studio()  # refuses changed/reused identities; never falls back to a global kill
                stopped = True
        finally:
            if sentinel is not None and sentinel_identity is not None:
                host.stop_owned_preview(sentinel, sentinel_identity)
                sentinel.wait(timeout=10)
                sentinel.stdout.close()
            if stopped or not kit._hf_preview:
                # This path was freshly allocated by this invocation; failed ownership cleanup retains it.
                require(fixture.parent == Path(tempfile.gettempdir()).resolve() and
                        fixture.name.startswith("editor-krab-preview-"), "Unexpected temp fixture path")
                shutil.rmtree(fixture)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--proof", type=Path, default=ROOT / "bug_reports" / "macos-acceptance")
    args = parser.parse_args()
    # setup records keg-only ffmpeg/Node folders here; a later CI step does not inherit setup.sh's PATH.
    if args.live or os.environ.get("CLIP_KIT_CONFIG") or (ROOT / "config.json").is_file():
        sys.path.insert(0, str(ROOT / "scripts" / "capcut"))
        import kitconfig  # noqa: F401 (applies the existing runtime_environment adapter)
    if args.self_check or not args.live:
        result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(SelfChecks))
        if not args.live:
            print("SKIP native Mac media/preview: requires --live on a disposable GitHub Mac runner")
        raise SystemExit(0 if result.wasSuccessful() else 1)
    require(sys.platform == "darwin" and os.environ.get("GITHUB_ACTIONS") == "true",
            "Native preview acceptance is restricted to disposable GitHub Mac runners")
    proof = prepare_proof(args.proof)
    report = {"revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                  text=True).strip(),
              "macos": platform.mac_ver()[0], "architecture": platform.machine(),
              "checks": {}, "unverified": ["native file picker", "Finder Trash", "browser window",
                                              "CapCut draft open/edit/save/export", "human editorial QC"]}
    try:
        font, path, family = font_evidence()
        report["checks"]["fonts"] = font
        report["checks"]["thai_ass"] = render_evidence(proof, path, family)
        report["checks"]["preview"] = preview_evidence()
        report["status"] = "PASS"
    except Exception as exc:
        report["status"] = "FAIL"
        report["error_type"] = type(exc).__name__
        raise
    finally:
        (proof / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("PASS native Mac font discovery, Thai ASS pixels and owned HyperFrames preview cleanup")


class SelfChecks(unittest.TestCase):
    def test_real_thai_ass_fixture_renders_without_opening_a_preview(self):
        import host_platform as host
        with tempfile.TemporaryDirectory() as folder:
            font = ROOT / "fonts" / "Kanit-Bold.ttf"
            evidence = render_evidence(Path(folder), font, host._font_family(font))
            self.assertEqual(evidence["status"], "PASS")
            self.assertGreater(evidence["bright_pixels"], 300)

    def test_blank_frame_is_rejected(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            frame = Path(folder) / "blank.png"
            Image.new("RGB", (640, 360), "black").save(frame)
            with self.assertRaisesRegex(RuntimeError, "blank"):
                image_evidence(frame)

    def test_public_proof_folder_is_scoped_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(globals(), ROOT=Path(folder)):
            root = Path(folder)
            with self.assertRaisesRegex(RuntimeError, "inside bug_reports"):
                prepare_proof(root / "outside")
            with self.assertRaisesRegex(RuntimeError, "inside bug_reports"):
                prepare_proof(root / "bug_reports" / ".." / "outside")
            target = root / "bug_reports" / "proof"
            self.assertEqual(prepare_proof(target), target.resolve())
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                prepare_proof(target)

    def test_preview_refuses_self_hosted_runner(self):
        with patch.dict(os.environ, RUNNER_ENVIRONMENT="self-hosted"), \
                patch.object(subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "GitHub-hosted"):
                preview_preflight()
            run.assert_not_called()


if __name__ == "__main__":
    main()
