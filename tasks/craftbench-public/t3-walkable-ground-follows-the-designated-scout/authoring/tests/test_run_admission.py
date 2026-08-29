"""Offline contract tests for the fail-closed admission runner."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "run_admission.py"
SPEC = importlib.util.spec_from_file_location("walkable_ground_runner", SCRIPT)
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RUNNER)


class RunAdmissionContractTests(unittest.TestCase):

    def test_exact_filter_map_and_denominator_are_locked(self):
        self.assertEqual(
            RUNNER.MAP_PACKAGE,
            "/Game/Maps/t3-walkable-ground-follows-the-designated-scout/"
            "L_WalkableGroundAdmission")
        self.assertEqual(
            RUNNER.TEST_FILTER,
            "Project.Functional Tests.Maps."
            "t3-walkable-ground-follows-the-designated-scout."
            "L_WalkableGroundAdmission."
            "WalkableGroundInvokerAdmissionFunctionalTest")
        self.assertEqual(len(RUNNER.GATE_NAMES), 6)
        self.assertEqual(len(set(RUNNER.GATE_NAMES)), 6)

    def test_parent_transmits_required_round_to_child(self):
        with tempfile.TemporaryDirectory() as directory:
            command = RUNNER.child_command(7, Path(directory))
        self.assertEqual(command.count("--round"), 1)
        self.assertEqual(command[command.index("--round") + 1], "7")
        self.assertIn("--child", command)
        self.assertIn("--output", command)

    def test_cli_rejects_missing_or_invalid_round(self):
        with self.assertRaises(SystemExit):
            RUNNER.parse_args([])
        with self.assertRaises(SystemExit):
            RUNNER.parse_args(["--round", "0"])
        args = RUNNER.parse_args(["--round", "3"])
        self.assertEqual(args.round, 3)
        self.assertFalse(args.child)

    def test_child_requires_output(self):
        with self.assertRaises(SystemExit):
            RUNNER.parse_args(["--round", "1", "--child"])


if __name__ == "__main__":
    unittest.main()
