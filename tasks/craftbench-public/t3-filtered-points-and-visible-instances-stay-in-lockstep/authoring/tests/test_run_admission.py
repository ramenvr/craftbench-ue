"""Offline runner contract tests; no UE process is started."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


AUTHORING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AUTHORING))
SPEC = importlib.util.spec_from_file_location(
    "filtered_point_runner", AUTHORING / "run_admission.py")
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RUNNER)


class RunnerContractTests(unittest.TestCase):
    def test_exact_two_fixture_paths(self):
        self.assertEqual(len(RUNNER.EXPECTED_TESTS), 2)
        self.assertTrue(all(path.startswith(RUNNER.TEST_FILTER + ".")
                            for path in RUNNER.EXPECTED_TESTS))
        self.assertEqual({path.rsplit(".", 1)[-1]
                          for path in RUNNER.EXPECTED_TESTS}, {
                              "FilteredPointInstancesFunctionalTestA",
                              "FilteredPointInstancesFunctionalTestB",
                          })

    def test_child_command_uses_fresh_explicit_output(self):
        command = RUNNER.child_command(Path("C:/cbtmp/pcg-test"))
        self.assertIn("--child", command)
        self.assertIn("--output", command)
        self.assertIn("C:\\cbtmp\\pcg-test", command)

    def test_six_fixed_gate_names(self):
        self.assertEqual(len(RUNNER.GATES), 6)
        self.assertEqual(len(set(RUNNER.GATES)), 6)

    def test_audit_accepts_only_exact_success(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            (output / "report").mkdir()
            (output / "l2_result.json").write_text(
                '{"status":"pass","tests_run":2,"tests_passed":2,'
                '"result_source":"json"}\n', encoding="utf-8")
            tests = [{"fullTestPath": path, "state": "Success"}
                     for path in sorted(RUNNER.EXPECTED_TESTS)]
            import json
            (output / "report" / "index.json").write_text(json.dumps({
                "succeeded": 2, "failed": 0, "tests": tests,
            }), encoding="utf-8")
            lines = [
                "FILTERED-POINT-PCG-SUCCEEDED policy=A gates=6/6",
                "FILTERED-POINT-PCG-SUCCEEDED policy=B gates=6/6",
            ]
            for gate in RUNNER.GATES:
                lines.extend([f"GATE[{gate}]=PASS", f"GATE[{gate}]=PASS"])
            (output / "l2.log").write_text("\n".join(lines), encoding="utf-8")
            with mock.patch.object(RUNNER, "protected_vector",
                                   return_value={"lock": 1}):
                ok, evidence = RUNNER.audit(output, {"lock": 1})
            self.assertTrue(ok, evidence["problems"])

    def test_audit_rejects_gate_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            (output / "report").mkdir()
            (output / "l2_result.json").write_text("{}", encoding="utf-8")
            (output / "report" / "index.json").write_text(
                '{"tests":[]}', encoding="utf-8")
            (output / "l2.log").write_text(
                "GATE[AllEligiblePointsRetained]=FAIL", encoding="utf-8")
            with mock.patch.object(RUNNER, "protected_vector",
                                   return_value={"lock": 1}):
                ok, evidence = RUNNER.audit(output, {"lock": 1})
            self.assertFalse(ok)
            self.assertTrue(evidence["problems"])


if __name__ == "__main__":
    unittest.main()
