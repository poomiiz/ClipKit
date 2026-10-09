"""Move this ClipKit clone to the newest commit on GitHub, even when the clone has its own commits or edits.

`git pull --ff-only` stops with "Not possible to fast-forward" as soon as the clone has a commit GitHub does not
(an autosave, a local fix). Instead: edited files go to a stash, the clone's own commits stay on a backup branch,
then the clone is reset to GitHub's newest. Nothing is thrown away and the update never dead-ends.

    python scripts/update.py
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> str:
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120, check=False)
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {(r.stderr or r.stdout).strip()}")
    return r.stdout.strip()


def main() -> None:
    git("fetch", "-q")
    if git("rev-list", "--count", "HEAD..@{u}") == "0":
        print("already the newest ClipKit")
        return
    stamp = time.strftime("%Y%m%d-%H%M%S")
    if git("status", "--porcelain", "--untracked-files=no"):
        git("stash", "push", "-m", f"clipkit-update {stamp}")
        print(f"edited files saved: git stash list -> clipkit-update {stamp}")
    if git("rev-list", "--count", "@{u}..HEAD") != "0":
        git("branch", f"backup/local-{stamp}")
        print(f"this copy's own commits saved on branch backup/local-{stamp}")
    git("reset", "--hard", "-q", "@{u}")
    print("updated to " + git("log", "-1", "--format=%h %s"))


if __name__ == "__main__":
    sys.exit(main())
