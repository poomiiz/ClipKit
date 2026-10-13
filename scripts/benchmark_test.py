"""Regression checks for benchmark attribution and measurement validity; no media or apps."""
import subprocess
import sys
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

import bench
from benchmark_timing import TimingLog


def _rows():
    data = [("e1", "A.mp4", "manual", 1, 60, 65), ("e1", "B.mp4", "editorkrab", 2, 15, 30),
            ("e2", "A.mp4", "editorkrab", 1, 15, 30), ("e2", "B.mp4", "manual", 2, 60, 65)]
    return [dict(zip(bench.COLUMNS, (f"t{i}", "pair5", video, "5", "5", "short", mode, editor,
                 str(order), "1", "0.75", str(human), str(elapsed), "3" if mode == "editorkrab" else "", "y", "")))
            for i, (editor, video, mode, order, human, elapsed) in enumerate(data)]


def _machine(rows):
    return {r["trial_id"]: {"video": r["video"], "minutes": 5.0, "complete": True, "successful": True}
            for r in rows if r["mode"] == "editorkrab"}


class BenchmarkTests(unittest.TestCase):
    def test_cli_main_scopes_complete_attempts_and_keeps_retry_status(self):
        import run_clip
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "talk.mp4"
            source.touch()  # no media is opened: the pipeline is replaced with a stub
            codes = iter((2, 0))
            def pipeline(args, raw):
                self.assertEqual(args.trial_id, "cli-trial")
                self.assertEqual(Path(raw), source)
                return run_clip.timed("stub", lambda: next(codes))
            previous = run_clip.TIMING
            with patch.object(run_clip.cutlog, "logs_dir", return_value=Path(folder)), \
                 patch.object(run_clip, "_pipeline", side_effect=pipeline), \
                 patch.object(sys, "argv", ["run_clip.py", str(source), "--trial-id", "cli-trial"]):
                self.assertEqual(run_clip.main(), 2)
                self.assertIs(run_clip.TIMING, previous)
                self.assertEqual(run_clip.main(), 0)
                self.assertIs(run_clip.TIMING, previous)
            log = Path(folder) / "timings.jsonl"
            records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([r["outcome"] for r in records if r["event"] == "run_end"], ["waiting", "ok"])
            self.assertTrue(bench.machine_trials(log, {"cli-trial"})["cli-trial"]["complete"])

    def test_nested_steps_are_not_added_to_invocation_totals(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "timings.jsonl"
            timer = TimingLog(log, str(Path(folder) / "talk.mp4"), "trial")
            with patch("benchmark_timing.time.perf_counter", side_effect=[0, 1, 2, 3, 4, 5]):
                timer.run(lambda: timer.timed("outer", lambda: timer.timed("inner", lambda: 0)))
            result = bench.machine_trials(log, {"trial"})["trial"]
            self.assertAlmostEqual(result["minutes"], 5 / 60)
            self.assertTrue(result["complete"])
            self.assertTrue(result["successful"])

    def test_same_basename_and_history_do_not_mix_and_retries_count(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "timings.jsonl"
            a = str(Path(folder) / "a" / "talk.mp4")
            b = str(Path(folder) / "b" / "talk.mp4")
            with patch("benchmark_timing.time.perf_counter", side_effect=[0, 3, 3, 5, 5, 100]):
                first = TimingLog(log, a, "trial1")
                first.run(lambda: 2)
                retry = TimingLog(log, a, "trial1")
                retry.run(lambda: 0)
                other = TimingLog(log, b, "trial2")
                other.run(lambda: 0)
            result = bench.machine_trials(log, {"trial1"})
            self.assertEqual(set(result), {"trial1"})
            self.assertAlmostEqual(result["trial1"]["minutes"], 5 / 60)
            self.assertNotEqual(first.run_id, retry.run_id)
            self.assertNotEqual(first.source_id, other.source_id)
            with self.assertRaisesRegex(ValueError, "another source"):
                TimingLog(log, b, "trial1")

    def test_failed_attempts_remain_in_machine_time(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "timings.jsonl"
            timer = TimingLog(log, "talk.mp4", "trial")
            def fail():
                raise RuntimeError("synthetic failure")
            with patch("benchmark_timing.time.perf_counter", side_effect=[0, 6]):
                with self.assertRaises(RuntimeError):
                    timer.run(fail)
            result = bench.machine_trials(log, {"trial"})["trial"]
            self.assertAlmostEqual(result["minutes"], 0.1)
            self.assertTrue(result["complete"])
            self.assertFalse(result["successful"])

    def test_incomplete_and_duplicate_logs(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "timings.jsonl"
            timer = TimingLog(log, "talk.mp4", "trial")
            timer.record("run_start")
            self.assertFalse(bench.machine_trials(log, {"trial"})["trial"]["complete"])
            timer.record("run_end", s=1, exit_code=0, outcome="ok")
            self.assertTrue(bench.machine_trials(log, {"trial"})["trial"]["complete"])
            timer.record("run_end", s=1, exit_code=0, outcome="ok")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                bench.machine_trials(log, {"trial"})

    def test_elapsed_savings_use_two_observed_timers(self):
        rows = _rows()
        result = bench.summarize(rows, _machine(rows))[0]
        self.assertEqual(result["editor_time_saved_pct"], 75)
        self.assertEqual(result["faster_x"], 4)
        self.assertEqual(result["wall_clock_saved_pct"], 53.8)
        self.assertEqual(result["ek_pipeline_min"], 5)

    def test_out_of_order_and_boolean_exit_codes_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            for event in ("step", "run_end"):
                with self.subTest(event=event):
                    log = Path(folder) / (event + ".jsonl")
                    timer = TimingLog(log, "talk.mp4", "trial")
                    timer.record(event, s=1, exit_code=0, outcome="ok")
                    with self.assertRaises(ValueError):
                        bench.machine_trials(log, {"trial"})
            log = Path(folder) / "boolean.jsonl"
            timer = TimingLog(log, "talk.mp4", "trial")
            timer.record("run_start")
            timer.record("run_end", s=1, exit_code=False, outcome="ok")
            with self.assertRaisesRegex(ValueError, "exit_code"):
                bench.machine_trials(log, {"trial"})

    def test_qc_failures_are_visible_and_percentages_unknown(self):
        rows = _rows()
        rows[1].update(qc_pass="n", output_count="0", output_min="0")
        machine = _machine(rows)
        del machine["t1"]
        result = bench.summarize(rows, machine)[0]
        self.assertEqual(result["qc_failed"], 1)
        self.assertEqual(result["trials"], 4)
        for key in ("editor_time_saved_pct", "faster_x", "wall_clock_saved_pct"):
            self.assertEqual(result[key], "UNKNOWN")

    def test_invalid_numbers_and_mismatched_trials_are_rejected(self):
        edits = [(0, "human_min", "0"), (1, "human_min", "-1"), (1, "human_min", "nan"),
                 (1, "elapsed_min", "inf"), (1, "elapsed_min", "1"), (1, "fixes", "-1"),
                 (1, "source_min", "20"), (1, "output_count", "2"), (1, "output_min", "2"),
                 (1, "trial_id", "t0"), (1, "video", "A.mp4"), (1, "editor", "e2"),
                 (1, "format", "long"), (2, "order", "2")]
        for index, key, value in edits:
            with self.subTest(field=key, value=value):
                rows = _rows()
                rows[index][key] = value
                with self.assertRaises(ValueError):
                    bench.summarize(rows, _machine(rows))
        with self.assertRaises(ValueError):
            bench.summarize(_rows()[:2], _machine(_rows()))

    def test_passed_assisted_rows_require_complete_successful_logs(self):
        for field in ("complete", "successful"):
            rows = _rows()
            machine = _machine(rows)
            machine["t1"][field] = False
            with self.assertRaisesRegex(ValueError, "complete timing"):
                bench.summarize(rows, machine)
        rows = _rows()
        machine = _machine(rows)
        machine["t1"]["minutes"] = 40
        with self.assertRaisesRegex(ValueError, "exceeds"):
            bench.summarize(rows, machine)

    def test_multiple_pairs_cannot_repeat_sources(self):
        rows = _rows()
        repeated = [{**r, "trial_id": r["trial_id"] + "copy", "pair_id": "pair-copy"} for r in rows]
        with self.assertRaisesRegex(ValueError, "same source twice"):
            bench.summarize(rows + repeated, _machine(rows + repeated))

    def test_equal_but_out_of_scope_deliverables_are_rejected(self):
        for count, duration in (("2", "0.75"), ("1", "10"), ("1", "0.1")):
            rows = _rows()
            for row in rows:
                row.update(output_count=count, output_min=duration)
            with self.assertRaisesRegex(ValueError, "30-60 second"):
                bench.summarize(rows, _machine(rows))

    def test_zero_assisted_active_time_and_empty_sheet_do_not_crash(self):
        rows = _rows()
        rows[1]["human_min"] = rows[2]["human_min"] = "0"
        self.assertEqual(bench.summarize(rows, _machine(rows))[0]["faster_x"], "UNKNOWN")
        self.assertEqual(bench.summarize([], {}), [])
        with tempfile.TemporaryDirectory() as folder:
            sheet = Path(folder) / "empty.csv"
            sheet.write_text(",".join(bench.COLUMNS) + "\n", encoding="utf-8")
            run = subprocess.run([sys.executable, str(Path(bench.__file__)), str(sheet)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("UNKNOWN", run.stdout)

    def test_short_csv_rows_report_an_input_error(self):
        with tempfile.TemporaryDirectory() as folder:
            sheet = Path(folder) / "broken.csv"
            sheet.write_text(",".join(bench.COLUMNS) + "\nonly-a-trial-id\n", encoding="utf-8")
            run = subprocess.run([sys.executable, str(Path(bench.__file__)), str(sheet)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 1)
            self.assertIn("one cell per header", run.stderr)
            self.assertNotIn("Traceback", run.stderr)


if __name__ == "__main__":
    unittest.main()
