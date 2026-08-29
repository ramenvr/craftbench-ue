"""The `editor_never_started` structural signal, and what it must NOT catch.

Added 2026-08-17 after a real run graded FAIL against a model for an editor that
never started: both L2 legs 0 bytes, no UECC dump, exit 0xC0000142
(STATUS_DLL_INIT_FAILED), L1 PASS, and all three pre-existing structural flags
False. See l2_pie._editor_never_started.

Most of this file is NEGATIVE cases. A void predicate that is too permissive is
strictly worse than none, because it hands the model under test a denominator
opt-out — so the tests that matter here are the ones asserting it DECLINES.
"""

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from layers.l2_pie import (  # noqa: E402
    _NEVER_STARTED_GRADED_EXITS,
    _editor_never_started,
)

#: The measured exit code: STATUS_DLL_INIT_FAILED.
DLL_INIT_FAILED = 3221225794


class TestFiresOnTheMeasuredShape(unittest.TestCase):

    def test_the_2026_08_17_run(self):
        """Empty log + zero tests + 0xC0000142 -> True."""
        self.assertTrue(_editor_never_started(
            log_text="", exit_code=DLL_INIT_FAILED, tests_run=0))

    def test_whitespace_only_log_counts_as_empty(self):
        """A log holding only a newline is still "the editor wrote nothing"."""
        self.assertTrue(_editor_never_started(
            log_text="\n  \r\n\t", exit_code=DLL_INIT_FAILED, tests_run=0))

    def test_it_does_not_key_on_the_exit_code_identity(self):
        """Any non-carve-out exit qualifies, deliberately.

        Keying on 0xC0000142 alone would be an implicit claim that agent C++ can
        never cause a DLL-init failure. A static initialiser in submitted code
        plausibly could, so the predicate is built not to depend on that.
        """
        for code in (1, 5, 3221225477, 0xC0000135, 139):
            with self.subTest(exit_code=code):
                self.assertTrue(_editor_never_started(
                    log_text="", exit_code=code, tests_run=0))


class TestDeclinesOnEverythingThatMustStayGraded(unittest.TestCase):
    """The important half. Each of these is a real case that must be scored."""

    def test_a_log_with_any_content_declines(self):
        """A real L2 failure WRITES. Emptiness is the whole discriminator.

        An assertion, a fixture FAIL, a filter that matched nothing, an
        agent-C++ crash — all produce log bytes.
        """
        for text in (
            "LogAutomationController: Test Completed. Result={Failed}",
            "no tests found matching filter",
            "Assertion failed: IsValid(Actor)",
            "x",
        ):
            with self.subTest(log=text[:40]):
                self.assertFalse(_editor_never_started(
                    log_text=text, exit_code=DLL_INIT_FAILED, tests_run=0))

    def test_a_run_that_recorded_a_test_result_declines(self):
        """Banked a real outcome -> it keeps it.

        Stops a submission passing part of a fixture and voiding the rest.
        """
        self.assertFalse(_editor_never_started(
            log_text="", exit_code=DLL_INIT_FAILED, tests_run=1))

    def test_the_governed_timeout_stays_graded(self):
        """Exit 124 is THE carve-out.

        A pathological submission can hang the editor. Routing a hang out of the
        denominator would be an opt-out requiring no submission content at all —
        one hanging fixture and the rep stops counting.
        """
        self.assertFalse(_editor_never_started(
            log_text="", exit_code=124, tests_run=0))
        self.assertIn(124, _NEVER_STARTED_GRADED_EXITS)

    def test_a_clean_exit_stays_graded(self):
        """Exit 0 with an empty log is OUR capture breaking, not the editor
        failing to start — and it must not be laundered into a void."""
        self.assertFalse(_editor_never_started(
            log_text="", exit_code=0, tests_run=0))
        self.assertIn(0, _NEVER_STARTED_GRADED_EXITS)

    def test_the_carve_out_set_is_exactly_the_two_documented_codes(self):
        """Widening this set widens what stops being scored. Pinned by value so
        an addition has to be argued for."""
        self.assertEqual(_NEVER_STARTED_GRADED_EXITS, frozenset({0, 124}))


class TestItIsNotSpoofableFromTheLog(unittest.TestCase):
    """The property that makes this the strongest of the four signals.

    rhi_unavailable / harness_precondition / queued_never_started all match text
    in a log agent C++ can write. This one requires the log to be EMPTY, and
    agent code runs only after the process has opened it — so anything a
    submission emits DISQUALIFIES the void rather than triggering it.
    """

    def test_every_sibling_marker_disqualifies_rather_than_triggers(self):
        for spoof in (
            "LogRHI: Error: Failed to create D3D12 device",       # rhi-ish
            "Test Completed. Result={Error}",                      # ::Error-ish
            "LogAutomationController: Display: Test Queued",       # queued-ish
        ):
            with self.subTest(spoof=spoof[:40]):
                self.assertFalse(_editor_never_started(
                    log_text=spoof, exit_code=DLL_INIT_FAILED, tests_run=0))


class TestPlumbing(unittest.TestCase):

    def test_l2result_and_layerreport_both_carry_the_field(self):
        """A flag the layer computes but the report drops is invisible to the
        verdict — the exact shape of the tokens_in bug found the same day."""
        from layers.l2_pie import L2Result
        from report import LayerReport
        self.assertIn("editor_never_started", L2Result.__dataclass_fields__)
        self.assertIn("editor_never_started", LayerReport.__dataclass_fields__)

    def test_it_defaults_false_so_a_missing_signal_grades(self):
        """Ambiguity resolves toward GRADED, per the verdict-contract doctrine."""
        from layers.l2_pie import L2Result
        self.assertIs(
            L2Result.__dataclass_fields__["editor_never_started"].default, False)


if __name__ == "__main__":
    unittest.main()
