"""Fix one subtitle line's words in a CapCut project (the agent's ClipKit: ตรวจคำผิด step).

    python scripts/fix_text.py "<project folder>" "<line as it is>" "<fixed line>"

Close CapCut first. The old version is kept (scripts/draft_history.py puts it back) and the changed words are
learned (app/spelling.py), so the next transcripts come out fixed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import capcut_edit  # noqa: E402

if len(sys.argv) != 4:
    sys.exit(__doc__)
capcut_edit.set_line_text(sys.argv[1], sys.argv[2], sys.argv[3])
print("ok:", sys.argv[2], "->", sys.argv[3])
