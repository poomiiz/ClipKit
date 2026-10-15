"""Fix one subtitle line's words in a CapCut project (the agent's ClipKit: ตรวจคำผิด step).

    python scripts/fix_text.py "<project folder>" "<line as it is>" "<fixed line>"

Close CapCut first. The old version is kept (scripts/draft_history.py puts it back) and the changed words are
learned (app/spelling.py), so the next transcripts come out fixed.
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import capcut_edit  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("project")
parser.add_argument("old")
parser.add_argument("new")
parser.add_argument("--cue-id", help="Subtitle segment ID; required when wording repeats")
args = parser.parse_args()
capcut_edit.set_line_text(args.project, args.old, args.new, args.cue_id)
print("ok:", args.old, "->", args.new)
