"""Motion API ownership and explicit replacement; renderer boundary is mocked."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
with tempfile.TemporaryDirectory() as folder:
    config = Path(folder) / "config.json"
    config.write_text("{}", encoding="utf-8")
    with patch.dict(os.environ, {"CLIP_KIT_CONFIG": str(config)}):
        import video_editor
import kit_settings
import kitconfig
import render


class MotionApiTests(unittest.TestCase):
    def setUp(self):
        self.path = self.enterContext(tempfile.TemporaryDirectory())
        config = Path(self.path) / "config.json"
        config.write_text("{}", encoding="utf-8")
        self.enterContext(patch.object(kitconfig, "_CANDIDATES", [config]))
        self.file = Path(self.path) / video_editor.OVERLAYS
        self.make = self.enterContext(patch.object(kit_settings, "make_motion", return_value={"file": "fixture.mov"}))

    def req(self, **values):
        return video_editor.OverlayRequest(path=self.path, template="hook-title", start=1.123456,
                                          end=3.234567, text="literal", **values)

    def test_close_start_never_deletes_old_motion_or_allocates_renderer(self):
        before = [{"placement_id": "old", "start": 1.13, "duration": .5, "file": "old.mov"}]
        self.file.write_text(json.dumps(before), encoding="utf-8")
        original = self.file.read_bytes()
        with self.assertRaises(video_editor.HTTPException) as error:
            video_editor.draft_overlay_add(self.req())
        self.assertEqual(error.exception.status_code, 409)
        self.make.assert_not_called()
        self.assertEqual(self.file.read_bytes(), original)

    def test_explicit_id_replaces_only_the_selected_recipe_and_preserves_clock(self):
        before = [{"placement_id": "old", "start": 1.13, "duration": .5, "file": "old.mov"},
                  {"placement_id": "other", "start": 4, "duration": .5, "file": "other.mov"}]
        self.file.write_text(json.dumps(before), encoding="utf-8")
        out = video_editor.draft_overlay_add(self.req(placement_id="old"))["overlays"]
        self.assertEqual(out[1], before[1])
        self.assertEqual(out[0]["placement_id"], "old")
        self.assertEqual(out[0]["start"], 1.123456)
        self.assertEqual(out[0]["duration"], 3.234567 - 1.123456)
        self.assertEqual(out[0]["params"]["key"], "literal")

    def test_missing_or_duplicate_id_cannot_render_or_remove(self):
        before = [{"placement_id": "same", "start": 1, "duration": 1},
                  {"placement_id": "same", "start": 3, "duration": 1}]
        self.file.write_text(json.dumps(before), encoding="utf-8")
        original = self.file.read_bytes()
        for selected in ("missing", "same"):
            with self.subTest(selected=selected), self.assertRaises(video_editor.HTTPException):
                video_editor.draft_overlay_add(self.req(placement_id=selected))
            with self.subTest(selected=selected), self.assertRaises(video_editor.HTTPException):
                video_editor.draft_overlay_remove(video_editor.OverlayDelete(path=self.path, placement_id=selected))
        self.make.assert_not_called()
        self.assertEqual(self.file.read_bytes(), original)

    def test_remove_by_id_or_exact_legacy_time_cannot_remove_nearby_items(self):
        before = [{"placement_id": "one", "start": 1, "duration": .01},
                  {"start": 1.03, "duration": .01}, {"start": 1.06, "duration": .01}]
        self.file.write_text(json.dumps(before), encoding="utf-8")
        rows = video_editor.draft_overlay_remove(video_editor.OverlayDelete(path=self.path, placement_id="one"))["overlays"]
        self.assertEqual(rows, before[1:])
        rows = video_editor.draft_overlay_remove(video_editor.OverlayDelete(path=self.path, start=1.03))["overlays"]
        self.assertEqual(rows, before[2:])
        with self.assertRaises(video_editor.HTTPException):
            video_editor.draft_overlay_remove(video_editor.OverlayDelete(path=self.path, start=1.04))

    def test_sentence_pair_owns_only_its_cue_including_caption_it_reproduces(self):
        phrase = {"start": 1, "end": 3, "hit": 2, "lead": "normal", "punch": "key",
                  "line": "normal key", "cue_id": "chosen", "opts": {}, "k": 0}
        timeline = {"style": {}, "width": 1080, "height": 1920, "phrases": [phrase], "hook": [], "motions": []}
        base = render.pair_events_from_timeline(timeline)
        # A neighboring held role can intersect this interval without belonging to this cue.
        neighbor = dict(base[0], cue_id="neighbor", role="caption", start=0, end=3)
        caption = dict(base[0], role="caption", center_y_px=300, size_px=20, outline_px=2, effect="none")
        with patch.object(render, "render_draft", return_value=timeline), \
                patch.object(render, "pair_events_from_timeline", return_value=base + [caption, neighbor]):
            req = video_editor.OverlayRequest(path=self.path, template="sentence-pair", start=1, end=3,
                                              text="normal key", cue_id="chosen")
            row = video_editor.draft_overlay_add(req)["overlays"][0]
        self.assertEqual({e["cue_id"] for e in self.make.call_args.args[0].params["subtitle_events"]}, {"chosen"})
        self.assertEqual(row["cue_id"], "chosen")
        self.assertEqual(row["ownership"], {"mode": "replace", "targets": [
            {"cue_id": "chosen", "roles": ["caption", "emphasis", "normal"]}], "caption_policy": "replace"})
        self.assertIn("params", row)

    def test_failed_render_preserves_existing_metadata(self):
        before = [{"placement_id": "old", "start": 1.13, "duration": .5, "file": "old.mov"}]
        self.file.write_text(json.dumps(before), encoding="utf-8")
        original = self.file.read_bytes()
        self.make.side_effect = RuntimeError("synthetic renderer failure")
        with self.assertRaisesRegex(RuntimeError, "renderer failure"):
            video_editor.draft_overlay_add(self.req(placement_id="old"))
        self.assertEqual(self.file.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
