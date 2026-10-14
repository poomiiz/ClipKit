"""Encoder selection and failed hardware exports never overwrite an existing MP4; no GPU needed."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import render
import draft_quality
import video_edit


class EncoderTests(unittest.TestCase):
    def test_default_profile_keeps_existing_cpu_quality(self):
        with patch.object(video_edit.kitconfig, "_load", return_value={}):
            self.assertEqual(render._video_encoder(),
                             ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"])
            self.assertIn("ultrafast", render._video_encoder(preview=True))

    def test_hardware_profiles_do_not_use_cpu_options_or_allow_fallback(self):
        for name in ("h264_nvenc", "h264_videotoolbox"):
            with self.subTest(name=name), patch.object(video_edit.kitconfig, "_load", return_value={"render_encoder": name}):
                args = render._video_encoder()
                self.assertEqual(args[:2], ["-c:v", name])
                self.assertNotIn("-crf", args)
                self.assertNotIn("libx264", args)
                if name == "h264_videotoolbox":
                    self.assertEqual(args[args.index("-allow_sw") + 1], "0")

    def test_invalid_profile_raises_before_reading_a_project(self):
        for invalid in ("auto", "", None, ["h264_nvenc"], "h264_nvenc -y"):
            with self.subTest(value=invalid), patch.object(video_edit.kitconfig, "_load", return_value={"render_encoder": invalid}):
                with self.assertRaisesRegex(video_edit.VideoEditError, "render_encoder"):
                    render.render_draft("missing project", "unused output")

    def test_failed_hardware_export_retains_previous_file_and_reports_encoder(self):
        self._export(success=False)

    def test_success_replaces_only_after_encode_and_returns_timing(self):
        self._export(success=True)

    def _export(self, success):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "project"
            folder.mkdir()
            source = root / "source.mp4"
            source.touch()
            clip = {"scale": {"x": 1}, "transform": {"x": 0, "y": 0}}
            segment = {"material_id": "video", "clip": clip,
                       "source_timerange": {"start": 0, "duration": 2_000_000},
                       "target_timerange": {"start": 0, "duration": 2_000_000}}
            draft = {"canvas_config": {"width": 320, "height": 180},
                     "tracks": [{"type": "video", "segments": [segment]}],
                     "materials": {"videos": [{"id": "video", "path": str(source)}]}}
            (folder / "draft_content.json").write_text(json.dumps(draft))
            (folder / "clipkit_style.json").write_text('{"music":"","sfx":false}')
            out = root / "exports"
            out.mkdir()
            target = out / "project.mp4"
            target.write_bytes(b"previous accepted export")

            def encode(command, **kwargs):
                self.assertEqual(target.read_bytes(), b"previous accepted export")
                self.assertEqual(command[command.index("-c:v") + 1], "h264_nvenc")
                partial = Path(command[-1])
                self.assertNotEqual(partial, target)
                self.assertEqual(partial.parent.parent, out)
                partial.write_bytes(b"new export" if success else b"incomplete")
                return SimpleNamespace(returncode=0 if success else 1, stderr="hardware unavailable")

            with patch.object(video_edit.kitconfig, "_load", return_value={"render_encoder": "h264_nvenc"}), \
                    patch.object(video_edit.kitconfig, "simple", return_value=False), \
                    patch.object(render, "probe", return_value={"width": 320, "height": 180, "fps": 30, "duration": 2}), \
                    patch.object(draft_quality, "probe", return_value={"width": 320, "height": 180, "fps": 30, "duration": 2}), \
                    patch.object(render.subprocess, "run", side_effect=encode) as run:
                if success:
                    result = render.render_draft(str(folder), str(out))
                    self.assertEqual(result["encoder"], "h264_nvenc")
                    self.assertGreaterEqual(result["encode_seconds"], 0)
                else:
                    with self.assertRaisesRegex(video_edit.VideoEditError, r"export failed \(h264_nvenc\)"):
                        render.render_draft(str(folder), str(out))
                self.assertEqual(run.call_count, 1)
            self.assertEqual(target.read_bytes(), b"new export" if success else b"previous accepted export")
            self.assertEqual(list(out.iterdir()), [target])


if __name__ == "__main__":
    unittest.main()
