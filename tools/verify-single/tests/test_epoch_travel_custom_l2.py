"""Offline contract tests for the cross-world custom L2 adapter."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest


VERIFY = Path(__file__).resolve().parent.parent
if str(VERIFY) not in sys.path:
    sys.path.insert(0, str(VERIFY))

from layers.l2_epoch_travel import GATES, classify_aggregate  # noqa: E402


def passing() -> dict:
    return {
        "status": "pass", "failure_kind": "none", "tests_run": 1,
        "tests_passed": 1, "tests_failed": 0, "inputs_unchanged": True,
        "gate_counts": {gate: 1 for gate in GATES}, "problems": [],
    }


class EpochTravelAdapterTests(unittest.TestCase):
    def test_exact_contract_passes(self):
        self.assertEqual("pass", classify_aggregate(passing(), 0))

    def test_named_behavior_failure_stays_graded(self):
        value = passing()
        value.update(status="fail", failure_kind="behavior",
                     tests_passed=0, tests_failed=1)
        self.assertEqual("fail", classify_aggregate(value, 1))

    def test_harness_failure_is_error(self):
        value = passing()
        value.update(status="fail", failure_kind="harness",
                     tests_run=0, tests_passed=0)
        self.assertEqual("error", classify_aggregate(value, 1))

    def test_missing_gate_invalidates_nominal_pass(self):
        value = passing()
        value["gate_counts"].pop(GATES[-1])
        self.assertEqual("error", classify_aggregate(value, 0))

    def test_mutated_protected_input_invalidates_pass(self):
        value = passing()
        value["inputs_unchanged"] = False
        self.assertEqual("error", classify_aggregate(value, 0))


if __name__ == "__main__":
    unittest.main()
