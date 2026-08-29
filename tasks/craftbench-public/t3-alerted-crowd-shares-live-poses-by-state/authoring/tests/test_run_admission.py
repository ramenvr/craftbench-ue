"""Offline contract tests for the fail-closed admission wrapper."""

import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import unittest


RUNNER = Path(__file__).resolve().parents[1] / "run_admission.py"
SPEC = importlib.util.spec_from_file_location("alert_crowd_runner", RUNNER)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load runner")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class AdmissionContractTests(unittest.TestCase):
    def test_exact_contract_is_nullrhi_world_clock_exact_one(self):
        self.assertEqual(MODULE.MAP_NAME, "L_AlertCrowdSharingAdmission")
        self.assertIn(TASK_ID := "t3-alerted-crowd-shares-live-poses-by-state",
                      MODULE.TEST_FILTER)
        self.assertTrue(MODULE.TEST_FILTER.endswith(
            "AlertCrowdSharingAdmissionFunctionalTest"))
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn("use_nullrhi=True", source)
        self.assertIn("expected_test_count=1", source)
        self.assertIn('"world_clock": True', source)
        self.assertEqual(len(MODULE.PROTECTED_FILES), 3)
        self.assertEqual(MODULE.TASK_ID, TASK_ID)

    def test_child_argv_preserves_required_round(self):
        output = Path("C:/cbtmp/alert-crowd-round-3")
        command = MODULE.child_command(3, output)
        self.assertEqual(command[2:],
                         ["--round", "3", "--child", "--output", str(output)])
        parsed = MODULE.parse_args(command[2:])
        self.assertEqual(parsed.round, 3)
        self.assertTrue(parsed.child)
        self.assertEqual(parsed.output, output)

    def test_round_and_child_output_are_required(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                MODULE.parse_args([])
            with self.assertRaises(SystemExit):
                MODULE.parse_args(["--round", "1", "--child"])


if __name__ == "__main__":
    unittest.main()
