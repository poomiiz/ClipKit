"""Copy engine changes from this repo into a clone of ClipKit-Team (the team edition) and commit them there.

    python scripts/sync_team.py "<path to ClipKit-Team clone>"          # copy + commit
    python scripts/sync_team.py "<path to ClipKit-Team clone>" --push   # and push

Every file the team repo has is refreshed from here, except the ones written for the team edition (TEAM_OWN).
A file new in this repo is not added there by itself: copy it once by hand when the team needs it.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEAM_OWN = {"README.md", "AGENTS.md", "skills/make-clip/SKILL.md", "scripts/setup.ps1", "scripts/doctor.py",
            ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"}


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("team")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()
    team = Path(a.team)
    if git(team, "status", "--porcelain").strip():
        sys.exit("the team clone has uncommitted changes - commit or discard them first")
    copied = []
    for rel in git(team, "ls-files").splitlines():
        src = ROOT / rel
        if rel in TEAM_OWN or not src.is_file():
            continue
        if src.read_bytes() != (team / rel).read_bytes():
            shutil.copy2(src, team / rel)
            copied.append(rel)
    if not copied:
        print("team repo already up to date")
        return 0
    head = git(ROOT, "log", "-1", "--format=%h %s").strip()
    git(team, "add", *copied)
    git(team, "commit", "-m", f"sync engine from ClipKit {head}\n\n" + "\n".join(copied))
    print("updated:", *copied, sep="\n  ")
    if a.push:
        git(team, "push", "-q")
        print("pushed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
