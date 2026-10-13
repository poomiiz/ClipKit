"""No NVIDIA GPU on this machine: switch config.json from whisper_device "cuda" to "cpu" (slow but works).

    python scripts/use_cpu.py      # setup.ps1 runs this when nvidia-smi is missing
"""
import json
import sys
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / "config.json"
cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
if cfg.get("whisper_device", "cuda") != "cuda":
    sys.exit(0)
cfg["whisper_device"] = "cpu"
CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print('No NVIDIA GPU: config.json whisper_device set to "cpu" (transcription is slow without a GPU)')
