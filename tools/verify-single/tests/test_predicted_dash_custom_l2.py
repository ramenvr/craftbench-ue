from pathlib import Path
import sys
import unittest


VERIFY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VERIFY))
from layers.l2_predicted_dash import GATES, classify_aggregate  # noqa: E402


class PredictedDashLayerTests(unittest.TestCase):
    def aggregate(self):
        return {
            "status": "pass", "failure_kind": "none",
            "tests_run": 2, "tests_passed": 2, "tests_failed": 0,
            "inputs_unchanged": True, "problems": [],
            "gate_counts": {gate: 1 for gate in GATES},
        }

    def test_exact_pass(self):
        self.assertEqual(classify_aggregate(self.aggregate(), 0), "pass")

    def test_gate_drop_is_not_pass(self):
        value = self.aggregate()
        value["gate_counts"][GATES[2]] = 0
        self.assertEqual(classify_aggregate(value, 0), "error")

    def test_behavior_failure_is_graded(self):
        value = self.aggregate()
        value.update(status="fail", failure_kind="behavior",
                     tests_passed=1, tests_failed=1)
        self.assertEqual(classify_aggregate(value, 1), "fail")

    def test_harness_failure_is_error(self):
        value = self.aggregate()
        value.update(status="fail", failure_kind="harness",
                     tests_run=1, tests_passed=0)
        self.assertEqual(classify_aggregate(value, 1), "error")


if __name__ == "__main__":
    unittest.main()
