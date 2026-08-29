"""Offline contract tests for the two-process SaveGame L2 adapter."""
from __future__ import annotations

import sys
from pathlib import Path
import unittest


VERIFY = Path(__file__).resolve().parent.parent
if str(VERIFY) not in sys.path:
    sys.path.insert(0, str(VERIFY))

from layers.l2_run_resume import GATES, classify_aggregate  # noqa: E402


def result(run: int, passed: int, failed: int) -> dict:
    return {"result": {"tests_run": run, "tests_passed": passed,
                       "tests_failed": failed}}


class RunResumeAdapterTests(unittest.TestCase):
    def test_exact_two_process_contract_passes(self):
        aggregate = {
            "status": "pass", "problems": [], "protocol_unchanged": True,
            "cleanup": {"removed": True},
            "gate_counts": {gate: 1 for gate in GATES},
            "legs": {"write": result(1, 1, 0),
                     "resume": result(1, 1, 0)},
        }
        self.assertEqual(classify_aggregate(aggregate, 0), "pass")

    def test_named_candidate_failure_stays_graded(self):
        aggregate = {
            "status": "fail", "failure_kind": "behavior",
            "legs": {"write": result(1, 0, 1)},
        }
        self.assertEqual(classify_aggregate(aggregate, 1), "fail")

    def test_harness_failure_is_not_reinterpreted_as_candidate_failure(self):
        aggregate = {
            "status": "fail", "failure_kind": "harness",
            "legs": {"write": result(0, 0, 0)},
        }
        self.assertEqual(classify_aggregate(aggregate, 1), "error")

    def test_missing_gate_invalidates_nominal_pass(self):
        counts = {gate: 1 for gate in GATES}
        counts.pop(GATES[-1])
        aggregate = {
            "status": "pass", "problems": [], "protocol_unchanged": True,
            "cleanup": {"removed": True}, "gate_counts": counts,
            "legs": {"write": result(1, 1, 0),
                     "resume": result(1, 1, 0)},
        }
        self.assertEqual(classify_aggregate(aggregate, 0), "error")


if __name__ == "__main__":
    unittest.main()
