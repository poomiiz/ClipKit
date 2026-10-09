"""The draft bot: watch the CapCut drafts folder (config.json "capcut_drafts") and record every project CapCut saves
into that project's history and change log (clipkit_history/, clipkit_changes.jsonl), and say when a save would
stop CapCut opening it. Stays on this machine. The app runs this by itself on the owner's machine ("creator": true).

    python scripts/draft_watch.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import capcut_edit  # noqa: E402
import kitconfig  # noqa: E402

root = kitconfig.need("capcut_drafts")
print("watching", root, "(Ctrl+C to stop)")
capcut_edit.watch(root)
