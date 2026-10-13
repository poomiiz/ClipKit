"""Run preview/render from a HyperFrames project folder using EditorKrab's host guard.

    <EditorKrab>/.venv/bin/python <EditorKrab>/scripts/hf.py preview --no-open
    <EditorKrab>/.venv/bin/python <EditorKrab>/scripts/hf.py render --format mov -o clip.mov
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
import host_platform


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in {"preview", "render"}:
        raise SystemExit(__doc__)
    sys.path.insert(0, str(ROOT / "scripts/capcut"))
    import kitconfig  # noqa: F401 (applies configured tool folders)
    npx = shutil.which("npx")
    if not npx:
        raise SystemExit("Node.js (npx) is missing; run setup")
    env = {**os.environ, "HYPERFRAMES_SKIP_SKILLS": "1"}
    command = host_platform.hyperframes_command(
        [npx, "--yes", "hyperframes@0.8.101", *sys.argv[1:]], Path.cwd(), env)
    return subprocess.call(command, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
