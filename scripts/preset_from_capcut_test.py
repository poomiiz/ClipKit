"""A learned preset uses the displayed size, including the editor's scale."""
import json
import tempfile
import unittest
from pathlib import Path

from preset_from_capcut import learn


class PresetScale(unittest.TestCase):
    def project(self, folder, scale):
        texts, segments = [], []
        for role, color, y in (("normal", [1, 1, 1], -.366), ("emphasis", [0, 0, .5], -.484759)):
            texts.append({"id": role, "content": json.dumps({"styles": [{"size": 25,
                "fill": {"content": {"solid": {"color": color}}}}]})})
            segments.append({"material_id": role, "clip": {"scale": scale[role], "transform": {"y": y}}})
        (folder / "draft_content.json").write_text(json.dumps({"materials": {"texts": texts},
            "tracks": [{"type": "text", "segments": segments}]}), encoding="utf-8")

    def test_measured_scale_and_position_survive(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            self.project(p, {"normal": {"x": .908, "y": .908},
                "emphasis": {"x": .8854454897620365, "y": .8854454897620365}})
            result = learn(p)
            self.assertEqual(result["normal"]["size"], 22.7)
            self.assertEqual(result["emphasis"]["size"], 22.136)
            self.assertEqual(result["emphasis"]["y"], -.484759)

    def test_missing_scale_is_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            self.project(p, {"normal": {}, "emphasis": {}})
            self.assertEqual(learn(p)["normal"]["size"], 25)

    def test_unrepresentable_scale_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            for scale in ({"x": 1, "y": .5}, {"x": 0, "y": 0}, {"x": float("nan"), "y": 1}):
                self.project(p, {"normal": scale, "emphasis": {}})
                with self.assertRaises(ValueError):
                    learn(p)


if __name__ == "__main__":
    unittest.main()
