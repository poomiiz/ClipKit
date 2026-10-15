"""The existing insert-sheet v1 contract stays independent from v2 clip/story packets."""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "scripts"))
with tempfile.TemporaryDirectory() as import_folder:
    config = Path(import_folder) / "config.json"
    config.write_text("{}", encoding="utf-8")
    with patch.dict(os.environ, {"CLIP_KIT_CONFIG": str(config)}):
        import run_clip
from cli_resume_test import accept_selection, write_project
import jobstore


class InsertContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        lock_state = patch.object(jobstore, "STATE", self.root / "locks")
        lock_state.start()
        self.addCleanup(lock_state.stop)
        self.raw = self.root / "talk.mp4"
        self.raw.write_bytes(b"synthetic source")
        self.downloads = self.root / "downloads"
        self.downloads.mkdir()
        for name in ("coffee.mp4", "office.mov", "building.mp4"):
            (self.downloads / name).write_bytes(("synthetic " + name).encode())
        self.projects = [self.root / "first", self.root / "second"]
        self.stories = accept_selection(self.raw,
            [{"start": 0, "end": 10, "text": "first story"}, {"start": 10, "end": 20, "text": "second story"}],
            [{"title": "First", "start": 0, "end": 10}, {"title": "Second", "start": 10, "end": 20}])
        for project, story, queries in zip(self.projects, self.stories, (["coffee", "office"], ["building"])):
            write_project(project, self.raw, story)
            (project / "clipkit_punch.json").write_text(json.dumps(
                {"cue:spoken": [["normal", "keyword", query] for query in queries]}), encoding="utf-8")
        self.context = run_clip._resume_context(str(self.raw), shape="portrait", look="pair", preset="default")
        self.state_file = Path(str(self.raw) + ".clipkit_run.json")
        self.state = run_clip._load_resume(self.state_file)
        for project, story in zip(self.projects, self.stories):
            run_clip._save_project(self.state_file, self.state, run_clip._manifest(self.context, story), str(project))
        self.plan = self.root / "answer.json"
        self.answer = {"clipkit_web_ai": 1, "step": "inserts", "video": self.raw.name,
                       "place": [{"file": "coffee.mp4", "link": 1}, {"file": "building.mp4", "link": 3}]}

    def place(self, answer):
        self.plan.write_text(json.dumps(answer), encoding="utf-8")
        return run_clip.place(str(self.raw), self.stories, [1, 2], self.state, str(self.downloads), str(self.plan), context=self.context)

    def assert_refused_without_moves(self, answer):
        before = {file.name: file.read_bytes() for file in self.downloads.iterdir()}
        with self.assertRaises(run_clip.video_edit.VideoEditError):
            self.place(answer)
        self.assertEqual({file.name: file.read_bytes() for file in self.downloads.iterdir()}, before)
        self.assertTrue(all(not (project / "clipkit_insert").exists() for project in self.projects))

    def test_v1_plan_moves_real_files_to_each_projects_local_link_number(self):
        result = self.place(self.answer)
        self.assertEqual(result, [
            {"link": 1, "search": "coffee", "file": "1 coffee.mp4", "project": "first"},
            {"link": 3, "search": "building", "file": "1 building.mp4", "project": "second"}])
        self.assertEqual((self.projects[0] / "clipkit_insert" / "1 coffee.mp4").read_bytes(), b"synthetic coffee.mp4")
        self.assertEqual((self.projects[1] / "clipkit_insert" / "1 building.mp4").read_bytes(), b"synthetic building.mp4")
        self.assertEqual([file.name for file in self.downloads.iterdir()], ["office.mov"])
        self.assertFalse(list(self.root.rglob(".clipkit-web-ai")))

    def test_v2_insert_plan_is_refused_without_claiming_a_v2_packet(self):
        self.assert_refused_without_moves({**self.answer, "clipkit_web_ai": 2})
        self.assertFalse(list(self.root.rglob(".clipkit-web-ai")))

    def test_wrong_source_or_invalid_pair_leaves_all_downloads_unchanged(self):
        answers = [{**self.answer, "video": "different.mp4"}]
        for pairs in ([{"file": "missing.mp4", "link": 1}], [{"file": "coffee.mp4", "link": 0}],
                      [{"file": "coffee.mp4", "link": 1}, {"file": "coffee.mp4", "link": 2}],
                      [{"file": "coffee.mp4", "link": 1}, {"file": "office.mov", "link": 1}]):
            answer = copy.deepcopy(self.answer)
            answer["place"] = pairs
            answers.append(answer)
        for answer in answers:
            with self.subTest(answer=answer):
                self.assert_refused_without_moves(answer)


if __name__ == "__main__":
    unittest.main()
