"""Prepare Mac paths and CPU speech settings; keep existing user configuration."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))


def prepare_config(config: dict, tool_bins: list[str], fresh: bool) -> dict:
    for folder in tool_bins:
        if not Path(folder).is_absolute() or not Path(folder).is_dir():
            raise ValueError(f"tool directory does not exist: {folder}")
    result = {**config, "whisper_device": "cpu", "runtime_bin_dirs": list(dict.fromkeys(tool_bins))}
    if fresh:
        result["whisper_model"] = "medium"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--tool-bin", action="append", default=[])
    parser.add_argument("--skip-model", action="store_true")
    parser.add_argument("--skip-asr", action="store_true")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("this setup is for macOS")
    import atomic
    cfg_path = ROOT / "config.json"
    fresh = not cfg_path.exists()
    config = json.loads((ROOT / "config.example.json" if fresh else cfg_path).read_text(encoding="utf-8-sig"))
    config = prepare_config(config, args.tool_bin, fresh)
    atomic.write_text(cfg_path, json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "setup_workspace.py"), args.workspace], check=True)
    config = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    if not config.get("capcut_drafts"):
        drafts = Path(args.workspace).expanduser().resolve() / "drafts"
        drafts.mkdir(parents=True, exist_ok=True)
        config["capcut_drafts"] = str(drafts)
        atomic.write_text(cfg_path, json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        print("CapCut not detected. Drafts will stay in your workspace; choose CapCut's real draft folder in Settings to open them there.")
    print("Speech uses the Mac CPU. Apple GPU acceleration is not enabled.")
    if not args.skip_model:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "fetch_model.py")], check=True)
    doctor = [sys.executable, str(ROOT / "scripts" / "doctor.py")]
    if not args.skip_asr:
        doctor.append("--asr")
    if args.skip_model:
        doctor.append("--skip-model")
    subprocess.run(doctor, check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
