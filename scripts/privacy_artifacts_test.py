"""Private artifacts stay ignored while public images, media examples and presets remain addable."""
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PrivacyArtifacts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name)
        self.repo = folder / "repo"
        self.repo.mkdir()
        template = folder / "empty-template"
        template.mkdir()
        excludes = folder / "empty-excludes"
        excludes.write_text("", encoding="utf-8")
        self.git = ["git", "-C", str(self.repo), "-c", f"core.excludesFile={excludes}"]
        subprocess.run([*self.git, "init", "--quiet", f"--template={template}"], check=True, capture_output=True)
        (self.repo / ".gitignore").write_text((ROOT / ".gitignore").read_text(encoding="utf-8"), encoding="utf-8")

    def ignored(self, paths):
        result = subprocess.run([*self.git, "check-ignore", "--no-index", "--stdin", "-z"],
                                input="\0".join(paths) + "\0", capture_output=True, text=True, encoding="utf-8")
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return set(result.stdout.rstrip("\0").split("\0")) if result.stdout else set()

    def test_generated_media_and_browser_sessions_are_ignored(self):
        paths = ["output/final.mp4", "nested/output/preview.png", ".playwright-cli/page.png",
                 "nested/.playwright-cli/page.yml", ".codex/visualizations/private-page.png",
                 "envato-profile/Default/Cookies", "envato-profile/Local State",
                 "nested/envato-profile/Default/Preferences"]
        self.assertEqual(self.ignored(paths), set(paths))

    def test_clip_story_transaction_state_and_private_presets_are_ignored(self):
        paths = ["project/.clipkit-web-ai/receipts/packet.json",
                 "nested/project/.clipkit-web-ai/transactions/job/assets/render.mov",
                 "talk.mp4.web-ai-state/packets/packet.json",
                 "nested/talk.mp4.web-ai-state/transactions/job/journal.json",
                 "presets/reference.private.json", "nested/session.private.json"]
        self.assertEqual(self.ignored(paths), set(paths))

    def test_existing_config_state_and_private_workspace_guards_remain(self):
        paths = ["config.json", "nested/config.json", "config.json.bak1", ".env", "nested/.env",
                 "state/jobs.json", "nested/state/private.json", "bug_reports/error.json",
                 "project_templates/private.json", "presets/my-personal.json", "presets/pace/private.json"]
        self.assertEqual(self.ignored(paths), set(paths))

    def test_public_images_sample_videos_source_and_presets_are_not_hidden(self):
        paths = ["docs/example-frame.png", "motion/example/assets/icon.png", "docs/brand/promo.mp4",
                 "fixtures/media/sample.mp4", "docs/output-chart.png", "config.example.json",
                 "presets/default.json", "motion/example/index.html", "scripts/privacy_artifacts_test.py",
                 "docs/test-logs/synthetic.json", ".codex/instructions.md"]
        self.assertEqual(self.ignored(paths), set())


if __name__ == "__main__":
    unittest.main()
