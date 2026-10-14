"""Read-only CapCut draft structure check; human listening and native CapCut opening stay pending."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import draft_quality
from video_edit import VideoEditError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", help="CapCut project folder")
    args = parser.parse_args()
    try:
        print(json.dumps(draft_quality.check(args.project), ensure_ascii=False, allow_nan=False, indent=2))
        return 0
    except VideoEditError as exc:
        print(json.dumps({"structural_pass": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
