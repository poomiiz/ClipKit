"""Checkpoint failure, retry, final-write failure and cache identity without GPU/network."""
import json
import sys
import tempfile
import unittest
import subprocess
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import video_edit as ve


class Checkpoints(unittest.TestCase):
    def test_last_word_cannot_extend_beyond_audio(self):
        phrases = [{"start": 8.1, "end": 10.92, "text": "สวัสดี", "words":
                    [[8.1, 9.5, "ส"], [9.5, 10.72, "ว"], [10.72, 10.92, "ัสดี"]]}]
        ve._bound_phrase_times(phrases, 10.25)
        self.assertEqual(phrases[0]["end"], 10.25)
        self.assertEqual(phrases[0]["words"][-1], [10.25, 10.25, "ัสดี"])
        self.assertEqual("".join(w[2] for w in phrases[0]["words"]), "สวัสดี")

    def test_quiet_boundary_in_real_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "pauses.wav"
            subprocess.run([ve.FFMPEG, "-v", "error", "-f", "lavfi", "-i",
                            r"aevalsrc=sin(2000*t)*lt(mod(t\,2)\,1.5):s=16000:d=70", str(source)], check=True)
            for near in (20, 40):
                seam = ve._quiet_point(str(source), near)
                self.assertTrue(1.5 < seam % 2 < 2, seam)

    def test_cpu_fallback_is_part_of_identity(self):
        with patch.object(ve, "_has_cuda", return_value=False), \
             patch.object(ve, "WHISPER_CPU_FALLBACK", "cpu-model"):
            self.assertEqual(ve._model_settings(), ("cpu-model", "cpu", "int8"))
        with patch.object(ve, "_has_cuda", return_value=True), \
             patch.object(ve, "whisper_model", return_value="gpu-model"):
            self.assertEqual(ve._model_settings(), ("gpu-model", "cuda", "int8_float16"))

    def test_legacy_transcript_is_preserved_without_claiming_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "legacy.mp4"
            source.write_bytes(b"source")
            transcript = ve.transcript_file(str(source))
            transcript.write_text("[]", encoding="utf-8")
            with patch.object(ve, "transcribe", side_effect=AssertionError("legacy cache discarded")):
                self.assertEqual(ve.transcribe_file(str(source)), [])
            self.assertFalse(transcript.with_suffix(".meta.json").exists())

    def test_resume_and_cache_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "talk.mp4"
            source.write_bytes(b"source")
            calls = []

            def recognize(path, start, end, language, model_size=None):
                calls.append((start, end, language))
                if len(calls) == 2:
                    raise RuntimeError("interrupted")
                return [{"start": 0, "end": 1, "text": "speech", "words": [[0, 1, "speech"]]}]

            with patch.object(ve, "probe", return_value={"duration": 31}), \
                 patch.object(ve, "CHUNK_S", 10), \
                 patch.object(ve, "_quiet_point", side_effect=lambda p, t: t), \
                 patch.object(ve, "_file_language", return_value="th"), \
                 patch.object(ve, "transcribe", side_effect=recognize):
                with self.assertRaisesRegex(RuntimeError, "interrupted"):
                    ve.transcribe_file(str(source))
                self.assertEqual(json.loads(ve.transcript_file(str(source)).with_suffix(".part.json").read_text())["end"], 10)
                phrases = ve.transcribe_file(str(source))
                self.assertEqual(calls, [(0, 10, "th"), (10, 20, "th"), (10, 20, "th"), (20, 31, "th")])
                self.assertEqual([p["start"] for p in phrases], [0, 10, 20])
                self.assertEqual(phrases[-1]["words"], [[20, 21, "speech"]])
                self.assertEqual(ve.transcribe_file(str(source)), phrases)
                self.assertEqual(len(calls), 4)
                source.write_bytes(b"change")  # same length; content hash must invalidate it
                ve.transcribe_file(str(source))
                self.assertEqual(len(calls), 7)
                with patch.object(ve, "_model_settings", return_value=("other", "cpu", "int8")):
                    ve.transcribe_file(str(source))
                self.assertEqual(len(calls), 10)
                self.assertEqual(set(json.loads(ve.lines_file(str(source)).read_text())[0]), {"start", "end", "text"})

    def test_completed_checkpoint_survives_failed_final_write(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "short.mp4"
            source.write_bytes(b"source")
            original = ve.atomic.write_text

            def write(path, *args, **kwargs):
                if path == ve.transcript_file(str(source)):
                    raise OSError("disk failure")
                return original(path, *args, **kwargs)

            with patch.object(ve, "probe", return_value={"duration": 0.25}), \
                 patch.object(ve, "transcribe", return_value=[]) as recognize:
                with patch.object(ve.atomic, "write_text", side_effect=write):
                    with self.assertRaisesRegex(OSError, "disk failure"):
                        ve.transcribe_file(str(source))
                self.assertEqual(ve.transcribe_file(str(source)), [])
                self.assertEqual(recognize.call_count, 1)

    def test_missing_metadata_is_not_legacy_when_checkpoint_exists(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "short.mp4"
            source.write_bytes(b"source")
            original = ve.atomic.write_text

            def write(path, *args, **kwargs):
                if path == ve.transcript_file(str(source)).with_suffix(".meta.json"):
                    raise OSError("metadata failure")
                return original(path, *args, **kwargs)

            with patch.object(ve, "probe", return_value={"duration": 1}), \
                 patch.object(ve, "transcribe", return_value=[]) as recognize:
                with patch.object(ve.atomic, "write_text", side_effect=write):
                    with self.assertRaisesRegex(OSError, "metadata failure"):
                        ve.transcribe_file(str(source))
                source.write_bytes(b"change")
                ve.transcribe_file(str(source))
                self.assertEqual(recognize.call_count, 2)


if __name__ == "__main__":
    unittest.main()
