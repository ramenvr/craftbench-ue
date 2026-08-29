"""A void with no reason is unauditable, and must be visible as exactly that.

THE CASE, found on the bench host on 2026-08-25 while triaging the 127-cell
MCP sweep against the per-run marker fix. One cell —
``20260823-040909-gp-glide-stamina-bp-aura-mcp-claude-sonnet-5`` — carries
``overall = FAIRNESS-BREACH`` with ``voided_reason`` and ``voided_verdict`` both
``null``, against $8.33 of spend.

Every writer in the rig pairs a void with its reason: ``leak_audit.main``'s
``--void`` branch and ``run.py``'s ``void_reason`` branch both go through
``stamp_void``, which refuses to write a reasonless record. So this one came
from neither, and the consequence is that the cell can be neither recovered nor
confirmed — the other four breaches from the same window WERE triaged, because
each named the mechanism ("read own task's reference via the in-tree park").

The state is worse than merely undocumented, and that is what this file pins:

  * to anything reading ``overall``, the cell is a fairness breach;
  * to ``read_void``, which returns None on an empty reason, it is NOT voided.

``sweep_report.is_graded`` asks both questions, so today the cell lands outside
the pass rate on the verdict test alone — the right answer reached by luck
rather than by evidence. Change ``VOID_VERDICTS``, or add a void verdict that is
in ``GRADED_VERDICTS``, and the luck runs out silently.

Diagnostic only. ``unauditable_void`` never changes a verdict; it exists so a
review SEES the contradiction instead of inheriting it.

Stdlib only. No UE, no editor, no tokens.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import leak_audit  # noqa: E402

#: The record as it actually sat on the bench host's disk, reduced to the
#: keys that decide the question.
MEASURED_CASE = {
    "overall": "FAIRNESS-BREACH",
    "voided_reason": None,
    "voided_verdict": None,
    "model": "aura-mcp:claude-sonnet-5",
}


class TestTheContradictionIsDetected(unittest.TestCase):
    def test_the_measured_case_is_flagged(self):
        why = leak_audit.unauditable_void(MEASURED_CASE)
        self.assertIsNotNone(why, "the cell that started this reads as fine")
        self.assertIn("FAIRNESS-BREACH", why)
        self.assertIn("cannot be reviewed", why)

    def test_the_two_readers_genuinely_disagree_on_it(self):
        # The reason the flag is needed, asserted rather than described: one
        # reader calls it a breach and the other calls it un-voided.
        self.assertEqual("FAIRNESS-BREACH", MEASURED_CASE["overall"])
        self.assertIsNone(leak_audit.read_void(MEASURED_CASE),
                          "read_void reported a void, so the contradiction "
                          "this guard exists for is gone — re-point it")

    def test_an_empty_dict_void_is_caught_too(self):
        # The other shape the same mistake takes: the key exists, the reason
        # does not.
        self.assertIsNotNone(leak_audit.unauditable_void(
            {"overall": "FAIRNESS-BREACH", "void": {}}))
        self.assertIsNotNone(leak_audit.unauditable_void(
            {"overall": "FAIRNESS-BREACH", "void": {"at": "2026-08-23T04:09:09Z"}}))


class TestItNeverFiresOnAWellFormedRecord(unittest.TestCase):
    """The loud direction. A false alarm here would send a reviewer hunting a
    defect in cells that are correctly recorded — which is how the retired
    fixture-marker set cost four graded PASSes."""

    def test_a_void_with_a_modern_reason_is_fine(self):
        self.assertIsNone(leak_audit.unauditable_void({
            "overall": "FAIRNESS-BREACH",
            "void": {"reason": "fairness breach — leak_audit: fixturex1",
                     "verdict_before": "PASS"}}))

    def test_a_void_with_the_legacy_flat_reason_is_fine(self):
        self.assertIsNone(leak_audit.unauditable_void({
            "overall": "FAIRNESS-BREACH",
            "voided_reason": "read own task's reference via the in-tree park",
            "voided_verdict": "PASS"}))

    def test_an_ordinary_graded_verdict_is_never_flagged(self):
        for v in ("PASS", "FAIL", "FAIL_NO_EDITS", "NO_DELIVERABLE",
                  "SANDBOX-REJECT", "EDITOR-NOT-READY", "AGENT-TRANSPORT-ERROR"):
            self.assertIsNone(leak_audit.unauditable_void({"overall": v}), v)

    def test_a_missing_overall_is_not_an_accusation(self):
        self.assertIsNone(leak_audit.unauditable_void({}))
        self.assertIsNone(leak_audit.unauditable_void({"overall": None}))


class TestItIsWiredWhereAReviewerWouldSeeIt(unittest.TestCase):
    def test_sweep_report_carries_it_on_every_row(self):
        # A detector nothing calls is the defect this repo keeps finding.
        src = (_ROOT / "sweep_report.py").read_text(encoding="utf-8")
        self.assertIn("unauditable_void(r)", src)
        self.assertIn('"unauditable_void"', src)

    def test_it_is_diagnostic_and_does_not_gate(self):
        # is_graded must still decide on the verdict and the void alone: a
        # diagnostic that silently changed a denominator would be a worse
        # version of the bug it reports.
        src = (_ROOT / "sweep_report.py").read_text(encoding="utf-8")
        body = src[src.index("def is_graded("):]
        body = body[:body.index("\ndef ")]
        self.assertNotIn("unauditable_void", body,
                         "the diagnostic reached the pass-rate filter")


if __name__ == "__main__":
    unittest.main()
