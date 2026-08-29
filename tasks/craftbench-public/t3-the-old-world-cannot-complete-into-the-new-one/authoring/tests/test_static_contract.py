from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


HERE = Path(__file__).resolve()
TASK = HERE.parents[2]
REPO = HERE.parents[5]
AUTHORING = TASK / "authoring"
sys.path.insert(0, str(AUTHORING))

from run_travel import GATES, classify_log  # noqa: E402


class EpochTravelStaticTests(unittest.TestCase):
    def test_success_log_is_exact(self):
        lines = ["EPOCH-TRAVEL-START READY",
                 "EPOCH-TRAVEL-DESTINATION READY",
                 "EPOCH-TRAVEL-OLD-CLEANUP"]
        lines += ["GATE[%s]=PASS" % gate for gate in GATES]
        lines.append("EPOCH-TRAVEL-SUCCEEDED gates=4/4")
        status, kind, problems, counts = classify_log(
            "\n".join(lines), 0, True)
        self.assertEqual(("pass", "none", []), (status, kind, problems))
        self.assertTrue(all(value == 1 for value in counts.values()))

    def test_named_gate_failure_is_behavior(self):
        lines = ["EPOCH-TRAVEL-START READY",
                 "EPOCH-TRAVEL-DESTINATION READY",
                 "EPOCH-TRAVEL-OLD-CLEANUP"]
        lines += ["GATE[%s]=%s" % (gate, "FAIL" if index == 2 else "PASS")
                  for index, gate in enumerate(GATES)]
        lines.append("EPOCH-TRAVEL-FAILED kind=behavior")
        status, kind, _, _ = classify_log("\n".join(lines), 0, True)
        self.assertEqual(("fail", "behavior"), (status, kind))

    def test_missing_destination_is_harness(self):
        status, kind, problems, _ = classify_log(
            "EPOCH-TRAVEL-HARNESS-ERROR", 0, True)
        self.assertEqual(("fail", "harness"), (status, kind))
        self.assertTrue(problems)

    def test_installed_introspector_has_three_checks(self):
        path = (REPO / "tools" / "verify-single" / "introspect"
                / "t3_epoch_world_async_guard.py")
        text = path.read_text(encoding="utf-8")
        self.assertIn("UsesCancellableAsynchronousRequest", text)
        self.assertIn("CallbackIsBoundToWeakWorldEpoch", text)
        self.assertIn("SubmissionHasNoCrossWorldOrSynchronousSubstitute", text)


if __name__ == "__main__":
    unittest.main()
