"""Copy engine changes from this repo into a clone of ClipKit-Team (the team edition) and commit them there.

    python scripts/sync_team.py "<path to ClipKit-Team clone>"          # copy + commit
    python scripts/sync_team.py "<path to ClipKit-Team clone>" --push   # and push

Every file the team repo has is refreshed from here, except the ones written for the team edition (TEAM_OWN).
A file new in this repo is not added there by itself: copy it once by hand when the team needs it.
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEAM_OWN = {"README.md", "AGENTS.md", "skills/make-clip/SKILL.md", "scripts/setup.ps1", "scripts/doctor.py",
            ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"}


# personal and client names never leave this repo; the sync stops and lists where they are
NAMES = re.compile(r"nina|bps|p'?ohm|poomi|พี่โอม", re.I)
ALLOWED = ("poomiiz/ClipKit",)  # the GitHub owner in links


def names_in(data: bytes) -> list[str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return []  # images, fonts
    for a in ALLOWED:
        text = text.replace(a, "")
    return [f"{n}: {line.strip()[:100]}" for n, line in enumerate(text.splitlines(), 1) if NAMES.search(line)]


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("team")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()
    team = Path(a.team)
    if subprocess.run([sys.executable, str(ROOT / "scripts" / "smoke_test.py")]).returncode:
        sys.exit("smoke test failed - nothing was copied")
    if git(team, "status", "--porcelain").strip():
        sys.exit("the team clone has uncommitted changes - commit or discard them first")
    todo = []
    for rel in git(team, "ls-files").splitlines():
        src = ROOT / rel
        if rel in TEAM_OWN or not src.is_file():
            continue
        if src.read_bytes() != (team / rel).read_bytes():
            todo.append(rel)
    found = {rel: hits for rel in todo if (hits := names_in((ROOT / rel).read_bytes()))}
    if found:
        for rel, hits in found.items():
            print(rel, *hits, sep="\n  ")
        sys.exit("names found - nothing was copied. Take them out of the files above, then sync again.")
    copied = []
    for rel in todo:
        shutil.copy2(ROOT / rel, team / rel)
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
