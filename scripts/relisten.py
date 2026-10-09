"""Hear one subtitle line again (the agent's ClipKit: ตรวจคำผิด step, for lines that read cut short).

    python scripts/relisten.py "<project folder>" "<line as it is>"

Prints what the speech model hears over that line's time, a little wider. Changes nothing; fix the line with
scripts/fix_text.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import capcut_edit  # noqa: E402

if len(sys.argv) != 3:
    sys.exit(__doc__)
print(capcut_edit.relisten(sys.argv[1], sys.argv[2]))
