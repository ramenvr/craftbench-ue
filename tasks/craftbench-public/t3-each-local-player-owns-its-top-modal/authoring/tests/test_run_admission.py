"""Offline contracts for the local-player modal admission runner."""

from __future__ import annotations

import importlib.util
import ast
import json
from pathlib import Path
import tempfile
import unittest


RUNNER = Path(__file__).resolve().parents[1] / "run_admission.py"
SPEC = importlib.util.spec_from_file_location("modal_admission_runner", RUNNER)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load admission runner")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AdmissionAuditTests(unittest.TestCase):
    def make_output(self, root: Path, *, path: str | None = None,
                    marker: str | None = None) -> Path:
        output = root / "out"
        (output / "report").mkdir(parents=True)
        (output / "l2_result.json").write_text(json.dumps({
            "status": "pass", "tests_run": 1, "tests_passed": 1,
            "tests_failed": 0, "result_source": "json",
        }), encoding="utf-8")
        (output / "report" / "index.json").write_text(json.dumps({
            "succeeded": 1, "succeededWithWarnings": 0,
            "failed": 0, "notRun": 0,
            "tests": [{
                "fullTestPath": path or MODULE.EXACT_FILTER,
                "testDisplayName": MODULE.EXPECTED_DISPLAY,
                "state": "Success",
            }],
        }), encoding="utf-8")
        (output / "l2.log").write_text(
            (marker or MODULE.EXPECTED_SUCCESS) + "\n", encoding="utf-8")
        return output

    def test_exact_report_and_terminal_marker_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            passed, summary = MODULE.audit(
                self.make_output(Path(temp)))
        self.assertTrue(passed)
        self.assertEqual([], summary["problems"])
        self.assertEqual("real-offscreen", summary["rhi"])

    def test_near_match_filter_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            passed, summary = MODULE.audit(self.make_output(
                Path(temp), path=MODULE.EXACT_FILTER + "NearMatch"))
        self.assertFalse(passed)
        self.assertTrue(any("fullTestPath" in item
                            for item in summary["problems"]))

    def test_failure_marker_fails_even_with_success_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = self.make_output(Path(temp))
            (output / "l2.log").write_text(
                MODULE.EXPECTED_SUCCESS +
                "\nGATE[OtherPlayersStackNeverChanges]: changed\n",
                encoding="utf-8")
            passed, summary = MODULE.audit(output)
        self.assertFalse(passed)
        self.assertTrue(any("GATE[" in item for item in summary["problems"]))

    def test_cli_requires_external_output_and_keeps_watchdog(self) -> None:
        args = MODULE.parse_args(["--output", "C:/cbtmp/modal-admission"])
        self.assertEqual(Path("C:/cbtmp/modal-admission"), args.output)
        self.assertEqual(720, args.watchdog_seconds)
        self.assertFalse(args.child)

    def test_child_locks_real_offscreen_rhi_and_exact_one(self) -> None:
        tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
        calls = [node for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and
                 isinstance(node.func, ast.Name) and
                 node.func.id == "run_l2"]
        self.assertEqual(1, len(calls))
        keywords = {item.arg: item.value for item in calls[0].keywords}
        self.assertIsInstance(keywords["use_nullrhi"], ast.Constant)
        self.assertFalse(keywords["use_nullrhi"].value)
        self.assertIsInstance(keywords["render_offscreen"], ast.Constant)
        self.assertTrue(keywords["render_offscreen"].value)
        self.assertEqual(1, keywords["expected_test_count"].value)
        self.assertEqual(60, keywords["fps"].value)


if __name__ == "__main__":
    unittest.main()
