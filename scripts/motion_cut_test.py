"""Motion cut: a still - moving - still clip keeps only the moving part, then renders.
Run: python scripts/motion_cut_test.py"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clipkit  # noqa: E402


def main():
    # the pure range logic (5 samples a second): a short still inside a move is bridged, a long one splits
    # the move, and a lone blip is dropped
    s = [0, 0, 0.1, 0.1, 0, 0, 0.1, 0.1, 0, 0, 0, 0, 0.1, 0.1, 0, 0, 0, 0, 0, 0.1, 0, 0]
    got = clipkit.keep_from_motion(s, 0.2, 4.4, 0.02, 0.6, 0.5, 0)
    assert got == [[0.4, 1.8], [2.4, 3.0]], got

    with tempfile.TemporaryDirectory() as t:
        src = Path(t).resolve() / "broll.mov"   # render writes broll.mp4 next to it
        subprocess.run(["ffmpeg", "-v", "error", "-y",
                        "-f", "lavfi", "-i", "color=c=gray:s=320x180:r=25:d=2",
                        "-f", "lavfi", "-i", "testsrc2=s=320x180:r=25:d=2",
                        "-f", "lavfi", "-i", "color=c=gray:s=320x180:r=25:d=2",
                        "-f", "lavfi", "-i", "sine=f=440:d=6",
                        "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
                        "-map", "[v]", "-map", "3:a", "-pix_fmt", "yuv420p", "-shortest", str(src)], check=True)
        plan = src.with_suffix(".plan.json")
        subprocess.run([sys.executable, str(HERE / "clipkit.py"), "plan", str(src), "--cut", "motion"], check=True)
        keep = json.loads(plan.read_text(encoding="utf-8"))["keep"]
        assert len(keep) == 1 and 1.6 <= keep[0][0] <= 2.1 and 3.9 <= keep[0][1] <= 4.4, keep
        try:
            subprocess.run([sys.executable, str(HERE / "clipkit.py"), "plan", str(src), "--cut", "motion", "--motion", "0.9"],
                           check=True, capture_output=True, text=True)
            raise AssertionError("a threshold nothing reaches still made a plan")
        except subprocess.CalledProcessError as exc:
            assert "nothing moved enough" in exc.stderr, exc.stderr
        subprocess.run([sys.executable, str(HERE / "clipkit.py"), "render", str(plan)], check=True)
        out = src.with_name("broll.mp4")
        length = clipkit.probe_duration(out)
        assert abs(length - (keep[0][1] - keep[0][0])) < 0.3, (length, keep)
    print("PASS motion cut: bridged stills, dropped blips, kept the moving 2 s of a still-moving-still clip, rendered it")


if __name__ == "__main__":
    main()
