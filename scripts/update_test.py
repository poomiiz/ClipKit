"""update.py follows release tags (vX.Y.Z), not every commit on main; run against a throwaway origin and clone."""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

UPDATE = Path(__file__).resolve().parent / "update.py"


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          capture_output=True, text=True, check=True).stdout.strip()


def commit(repo, name, text):
    (repo / name).write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", f"change {name}")


def run(clone, *args):
    return subprocess.run([sys.executable, str(clone / "scripts" / "update.py"), *args], capture_output=True, text=True)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src, origin, clone = tmp / "src", tmp / "origin.git", tmp / "clone"
        (src / "scripts").mkdir(parents=True)
        shutil.copy(UPDATE, src / "scripts" / "update.py")
        git(tmp, "init", "-q", "-b", "main", str(src))
        commit(src, "requirements.txt", "")
        git(tmp, "clone", "-q", "--bare", str(src), str(origin))
        git(tmp, "clone", "-q", str(origin), str(clone))

        r = run(clone, "--check")
        assert r.returncode != 0 and "no release" in r.stderr, r.stderr

        git(src, "tag", "v0.1.0")
        commit(src, "a.txt", "released")
        git(src, "tag", "v0.2.0")
        commit(src, "b.txt", "merged, not released")
        git(src, "push", "-q", "--tags", str(origin), "main")

        u = json.loads(run(clone, "--check").stdout)
        assert u == {"release": "v0.2.0", "count": 1, "changes": ["change a.txt"]}, u
        r = run(clone)
        assert r.returncode == 0 and "updated to v0.2.0" in r.stdout, r.stdout + r.stderr
        assert (clone / "a.txt").is_file() and not (clone / "b.txt").exists(), "went past the release"
        assert run(clone).stdout.startswith("already the newest"), "second run"
        assert "packages updated" not in r.stdout, "requirements.txt did not change"

        commit(clone, "mine.txt", "local commit")
        commit(src, "requirements.txt", "# no packages\n")
        git(src, "tag", "v0.10.0")   # numeric order: v0.10.0 is newer than v0.2.0
        git(src, "push", "-q", "--tags", str(origin), "main")
        r = run(clone)
        assert r.returncode == 0 and "updated to v0.10.0" in r.stdout and "packages updated" in r.stdout, r.stdout + r.stderr
        assert "backup/local-" in r.stdout and not (clone / "mine.txt").exists(), "local commit not kept on a branch"
        assert "backup/local-" in git(clone, "branch", "--list", "backup/*")
    print("PASS update follows release tags, keeps local commits, reinstalls changed requirements")


if __name__ == "__main__":
    main()
