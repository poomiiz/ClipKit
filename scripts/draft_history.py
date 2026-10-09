"""Every version ClipKit saved of a project (an autosave history), and putting one back.

    python scripts/draft_history.py "<project folder>"                  # list versions, oldest first
    python scripts/draft_history.py "<project folder>" "<version name>" # put that version back

Close CapCut first. Putting a version back is itself saved as a new version, so nothing is lost.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import capcut_edit  # noqa: E402

if len(sys.argv) not in (2, 3):
    sys.exit(__doc__)
if len(sys.argv) == 2:
    print("\n".join(capcut_edit.history(sys.argv[1])) or "no saved versions yet")
else:
    capcut_edit.restore(sys.argv[1], sys.argv[2])
    print("ok: put back", sys.argv[2])
