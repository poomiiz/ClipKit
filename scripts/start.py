"""Open EditorKrab using the portable controller and a browser."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from host_platform import runtime_environment


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
    env = runtime_environment(config)
    result = subprocess.run([sys.executable, str(ROOT / "app" / "control.py"), "--action", "start",
                             "--port", str(args.port), "--python", sys.executable], cwd=ROOT,
                            env=env, capture_output=True, text=True, encoding="utf-8", timeout=150)
    if result.returncode:
        print(result.stderr.strip() or result.stdout.strip(), file=sys.stderr)
        return result.returncode
    print(result.stdout.strip())
    if not args.no_open:
        webbrowser.open(f"http://127.0.0.1:{args.port}/video-editor.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
