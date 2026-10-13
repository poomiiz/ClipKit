"""Opt-in Update check against the real remote, using a disposable clone."""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = "fac553c5-4930-4eb5-838f-9cb610e13cab"


def run(cwd: Path, *args: str) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=240)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--expected-release")
    parser.add_argument("--proof", type=Path)
    args = parser.parse_args()
    if not args.live:
        print("SKIP real release Update: use --live --expected-release vX.Y.Z")
        return
    if not args.expected_release or not args.proof:
        parser.error("--live requires --expected-release and --proof")
    remote = run(ROOT, "git", "remote", "get-url", "origin")
    with tempfile.TemporaryDirectory(prefix="editorkrab-update-") as folder:
        clone = Path(folder) / "clone"
        run(ROOT, "git", "clone", "-q", "--branch", "v0.29.0", remote, str(clone))
        git = lambda *values: run(clone, "git", "-c", "user.name=codex",  # noqa: E731
                                 "-c", "user.email=codex@users.noreply.github.com", *values)
        before_requirements = (clone / "requirements.txt").read_bytes()
        config = clone / "config.json"
        config.write_text('{"update_acceptance_fixture": true}\n', encoding="utf-8")
        fixture = clone / "update-local-commit.txt"
        fixture.write_text("retained local fixture\n", encoding="utf-8")
        git("add", fixture.name)
        git("commit", "-q", "-m", "test: preserve a disposable Update fixture\n\nTask-Id: " + TASK)
        local_commit = git("rev-parse", "HEAD")
        readme = clone / "README.md"
        with readme.open("a", encoding="utf-8") as handle:
            handle.write("\nDisposable tracked Update fixture.\n")
        venv.EnvBuilder(with_pip=True).create(clone / ".venv")
        python = clone / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        update = str(clone / "scripts" / "update.py")
        check = json.loads(run(clone, str(python), update, "--check"))
        assert check["release"] == args.expected_release and check["count"] > 0, check
        # This patch check must not install packages into the CI checkout's environment.
        target_requirements = git("show", args.expected_release + ":requirements.txt")
        assert before_requirements.decode("utf-8").strip() == target_requirements.strip(), \
            "dependency changes need an installed baseline environment"
        output = run(clone, str(python), update)
        expected_commit = git("rev-parse", args.expected_release + "^{commit}")
        assert git("rev-parse", "HEAD") == expected_commit
        assert config.read_text(encoding="utf-8") == '{"update_acceptance_fixture": true}\n'
        assert "Disposable tracked Update fixture." in git("stash", "show", "-p", "stash@{0}")
        backups = git("branch", "--format=%(refname:short)", "--list", "backup/local-*").splitlines()
        assert len(backups) == 1 and git("rev-parse", backups[0]) == local_commit, backups
        assert git("show", backups[0] + ":" + fixture.name) == "retained local fixture"
        for name in ("scripts/bench.py", "scripts/setup_macos.py", "scripts/capcut_font_test.py",
                     "docs/benchmark-sheet.csv", "docs/brand/promo.mp4"):
            assert (clone / name).is_file(), name
        version = json.loads((clone / ".claude-plugin/plugin.json").read_text())["version"]
        assert "v" + version == args.expected_release
        second = run(clone, str(python), update)
        assert second.startswith("already the newest"), second
        proof = {"baseline": "v0.29.0", "release": args.expected_release, "commit": expected_commit,
                 "system": platform.system(), "machine": platform.machine(),
                 "check": check, "tracked_edits_stashed": True, "local_commit_backed_up": True,
                 "local_config_preserved": True, "packages": "unchanged", "second_update": second}
        args.proof.parent.mkdir(parents=True, exist_ok=True)
        args.proof.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
        print(output)
        print("PASS real release Update, tracked edits, local commits, config and repeat update")


if __name__ == "__main__":
    main()
