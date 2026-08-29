"""Offline contract tests for the district-streaming admission audit."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


RUNNER_PATH = Path(__file__).with_name("run_admission.py")
SPEC = importlib.util.spec_from_file_location("district_admission_runner", RUNNER_PATH)
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RUNNER)


class DistrictAdmissionAuditTests(unittest.TestCase):
    def write_green_evidence(self, root: Path) -> None:
        (root / "report").mkdir()
        tests = [
            {
                "testDisplayName": display,
                "fullTestPath": RUNNER.EXACT_FILTER + "." + display,
                "state": "Success",
            }
            for display in sorted(RUNNER.EXPECTED_DISPLAYS)
        ]
        (root / "report" / "index.json").write_text(json.dumps({
            "tests": tests, "succeeded": 2, "failed": 0,
            "succeededWithWarnings": 0, "notRun": 0,
        }), encoding="utf-8")
        (root / "l2_result.json").write_text(json.dumps({
            "status": "pass", "tests_run": 2, "tests_passed": 2,
            "tests_failed": 0, "result_source": "json",
        }), encoding="utf-8")
        telemetry = [
            "DISTRICT-STREAMING-TELEMETRY cp=%d request=%s" %
            (checkpoint, request)
            for request in ("Alpha", "Beta")
            for checkpoint in range(7)
        ]
        telemetry.extend([
            "DISTRICT-STREAMING-SUCCEEDED request=Alpha gates=5 runtime_observed=1",
            "DISTRICT-STREAMING-SUCCEEDED request=Beta gates=5 runtime_observed=1",
        ])
        (root / "l2.log").write_text("\n".join(telemetry), encoding="utf-8")

    def test_exact_two_green_report_passes(self) -> None:
        before = {"locked": {"sha256": "A"}}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_green_evidence(root)
            with mock.patch.object(RUNNER, "snapshot", return_value=before):
                ok, evidence = RUNNER.audit(root, before)
            self.assertTrue(ok, evidence["problems"])
            self.assertEqual([], evidence["problems"])

    def test_wrong_display_and_gate_marker_fail_closed(self) -> None:
        before = {"locked": {"sha256": "A"}}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_green_evidence(root)
            report = json.loads((root / "report" / "index.json").read_text())
            report["tests"][1]["testDisplayName"] = "WrongFixture"
            (root / "report" / "index.json").write_text(
                json.dumps(report), encoding="utf-8")
            with (root / "l2.log").open("a", encoding="utf-8") as stream:
                stream.write("\nExactActorsLeaveAfterUnload: forced failure\n")
            with mock.patch.object(RUNNER, "snapshot", return_value=before):
                ok, evidence = RUNNER.audit(root, before)
            self.assertFalse(ok)
            self.assertTrue(any("display set mismatch" in item
                                for item in evidence["problems"]))
            self.assertTrue(any("ExactActorsLeaveAfterUnload" in item
                                for item in evidence["problems"]))


if __name__ == "__main__":
    unittest.main()
