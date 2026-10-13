"""Mac setup/launcher contracts without changing this machine or starting applications."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import setup_macos
import start


class SetupTests(unittest.TestCase):
    def test_user_paths_and_preferences_survive_cpu_setup(self):
        with tempfile.TemporaryDirectory(prefix="editor krab ") as folder:
            cfg = {"whisper_model": "tiny", "capcut_drafts": folder, "pixabay_key": "test-only", "whisper_device": "cuda"}
            result = setup_macos.prepare_config(cfg, [folder, folder], False)
            self.assertEqual(result["whisper_model"], "tiny")
            self.assertEqual(result["capcut_drafts"], folder)
            self.assertEqual(result["pixabay_key"], "test-only")
            self.assertEqual(result["whisper_device"], "cpu")
            self.assertEqual(result["runtime_bin_dirs"], [folder])
            self.assertEqual(cfg["whisper_device"], "cuda")

    def test_fresh_install_uses_medium_and_rejects_invalid_tool_paths(self):
        self.assertEqual(setup_macos.prepare_config({}, [], True)["whisper_model"], "medium")
        for paths in (["relative"], [str(Path(tempfile.gettempdir()) / "missing-editor-tool-123")]):
            with self.assertRaises(ValueError):
                setup_macos.prepare_config({}, paths, True)

    def test_launcher_preserves_path_and_rejects_invalid_config(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"PATH": "existing-path"}):
                env = start.runtime_environment({"runtime_bin_dirs": [folder]})
            self.assertEqual(env["PATH"], folder + os.pathsep + "existing-path")
        for bins in ("not-list", ["relative"], [1]):
            with self.assertRaises(ValueError):
                start.runtime_environment({"runtime_bin_dirs": bins})

    def test_failed_controller_does_not_open_browser(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "config.json").write_text(json.dumps({}), encoding="utf-8")
            result = type("Result", (), {"returncode": 1, "stderr": "owned-server check failed", "stdout": ""})()
            with patch.object(start, "ROOT", root), patch.object(sys, "argv", ["start.py"]), \
                 patch.object(start.subprocess, "run", return_value=result) as run, \
                 patch.object(start.webbrowser, "open") as browser:
                self.assertEqual(start.main(), 1)
                browser.assert_not_called()
                command = run.call_args.args[0]
                self.assertIn("--action", command)
                self.assertIn("start", command)
                self.assertFalse(run.call_args.kwargs.get("shell", False))


if __name__ == "__main__":
    unittest.main()
