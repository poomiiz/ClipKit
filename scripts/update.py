"""Move this ClipKit clone to the newest release (a vX.Y.Z tag) on GitHub, even when the clone has its own commits
or edits. Releases, not every merge to main, reach the editors' machines, so a bad merge can wait for a fix.

`git pull --ff-only` stops with "Not possible to fast-forward" as soon as the clone has a commit GitHub does not
(an autosave, a local fix). Instead: edited files go to a stash, the clone's own commits stay on a backup branch,
then the clone is reset to the newest release. Nothing is thrown away and the update never dead-ends.

    python scripts/update.py           # update, and reinstall packages when requirements.txt changed
    python scripts/update.py --check   # JSON: newest release, how many commits behind, their subjects
"""
from __future__ import annotations

import json
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


def release() -> str:
    """The newest vX.Y.Z tag on GitHub."""
    git("fetch", "-q", "--tags", "--force")
    tags = git("tag", "--list", "v*", "--sort=-v:refname").split()
    if not tags:
        raise SystemExit("no release on GitHub yet (a vX.Y.Z tag)")
    return tags[0]


def check() -> None:
    target = release()
    n = int(git("rev-list", "--count", f"HEAD..{target}"))
    changes = git("log", "--format=%s", "-8", f"HEAD..{target}").splitlines() if n else []
    print(json.dumps({"release": target, "count": n, "changes": changes}, ensure_ascii=False))


def main() -> None:
    target = release()
    if git("rev-list", "--count", f"HEAD..{target}") == "0":
        print(f"already the newest ClipKit ({target})")
        return
    stamp = time.strftime("%Y%m%d-%H%M%S")
    if git("status", "--porcelain", "--untracked-files=no"):
        git("stash", "push", "-m", f"clipkit-update {stamp}")
        print(f"edited files saved: git stash list -> clipkit-update {stamp}")
    if git("rev-list", "--count", f"{target}..HEAD") != "0":
        git("branch", f"backup/local-{stamp}")
        print(f"this copy's own commits saved on branch backup/local-{stamp}")
    old = git("rev-parse", "HEAD")
    git("reset", "--hard", "-q", target)
    print(f"updated to {target}: " + git("log", "-1", "--format=%h %s"))
    if "requirements.txt" in git("diff", "--name-only", old, "HEAD").split():
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(ROOT / "requirements.txt")],
                           check=False)
        if r.returncode != 0:
            setup = "bash scripts/setup.sh" if sys.platform == "darwin" else "scripts/setup.ps1"
            raise SystemExit("updated, but installing the new packages failed - run " + setup)
        print("packages updated")


if __name__ == "__main__":
    sys.exit(check() if "--check" in sys.argv else main())
