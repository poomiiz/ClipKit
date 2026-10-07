"""FFmpeg integration check with generated media; no client footage or network.

    python scripts/media_test.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
import hf_build
import video_edit


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "source.mp4"
        subprocess.run([video_edit.FFMPEG, "-v", "error", "-f", "lavfi", "-i",
                        "testsrc2=size=320x240:rate=30:duration=3", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-shortest", str(source)], check=True, timeout=30)
        out = root / "preview"
        out.mkdir()
        cuts = [{"media_start": 0, "dur": 1}, {"media_start": 2, "dur": 1}]
        first = out / hf_build._proxy(out, str(source), cuts)
        info = video_edit.probe(str(first))
        assert abs(info["duration"] - 2) < 0.15, info
        subprocess.run([video_edit.FFMPEG, "-v", "error", "-i", str(first), "-f", "null", "-"],
                       check=True, timeout=30)
        before = first.read_bytes()
        with patch.object(hf_build.render.subprocess, "run", side_effect=AssertionError("cache was missed")):
            assert out / hf_build._proxy(out, str(source), cuts) == first
        changed = [{"media_start": 0, "dur": 0.5}]

        def fail(command, **kwargs):
            Path(command[-1]).write_bytes(b"interrupted")
            return subprocess.CompletedProcess(command, 1, stderr="simulated interruption")

        with patch.object(hf_build.render.subprocess, "run", side_effect=fail):
            try:
                hf_build._proxy(out, str(source), changed)
            except video_edit.VideoEditError:
                pass
            else:
                raise AssertionError("failed encoding was accepted")
        assert first.read_bytes() == before, "working preview was lost"
        assert list((out / "media").iterdir()) == [first], "partial cache was left behind"
        retry = out / hf_build._proxy(out, str(source), changed)
        assert abs(video_edit.probe(str(retry))["duration"] - 0.5) < 0.15
        other = root / "other.mp4"
        other.write_bytes(source.read_bytes())
        alternate = out / hf_build._proxy(out, str(other), cuts)
        assert alternate != first, "different sources share a cached preview"
        print(json.dumps({"status": "passed", "duration": info["duration"],
                          "checks": ["decode", "cuts", "cache", "interruption", "retry", "source identity"]}))


if __name__ == "__main__":
    main()
