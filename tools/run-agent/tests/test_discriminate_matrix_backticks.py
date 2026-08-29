"""A MATRIX substring quoted in markdown backticks must still match the log.

THE DEFECT, measured 2026-08-23 on
`t3-gate-and-door-cpp`. Its MATRIX names the empty
leg's expected assertion as `` `TheGateStaysShutUntilBothItsCratesAreHome` ``, and
`_extract_substrings` returned it WITH the ticks while the L2 log holds it
without. `grade_leg` matches by plain `in`, so the match could never succeed and
the leg was recorded as `wrong-reason` — i.e. "it failed, but not for the reason
the MATRIX claims" — when it had failed for exactly that reason.

Why it hid: the leg still FAILS, so nothing looks broken; only the LABEL is wrong,
and `wrong-reason` reads as a task-design problem. It sends the reader to the
MATRIX row and the fixture rather than to the parser.

Why it only bites some tasks: `_extract_substrings` prefers backticked literals
that look "substantive" (containing a space or one of `(),.=`), a filter meant to
drop parenthetical barewords like `` `SpawnedClone` ``. This repo's assertion
NAMES are barewords too — the fixtures print `AssertionName: message` — so a
CamelCase name is dropped by that filter and falls through to the last-resort
path, which stripped `(...)` and `**` but not the ticks. A task whose MATRIX
quotes a phrase (with a space) never took that path and always worked.

The fix is MONOTONE, which is the argument for putting it in the parser: a
substring that matches today cannot contain a backtick, because the log does not,
so stripping ticks can only turn an impossible match into a possible one. It can
never flip a credited leg to uncredited — and these tests assert that direction
explicitly, not just the happy case.

Stdlib only. No editor, no UE, no tokens.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig.discriminate import _extract_substrings, parse_matrix  # noqa: E402

_HEADER = (
    "| Submission | Overall | Message substring |\n"
    "|---|---|---|\n"
)


def _matrix(first_cell: str, overall: str, message: str) -> str:
    return _HEADER + f"| {first_cell} | {overall} | {message} |\n"


class TestBacktickedBarewordAssertionNames(unittest.TestCase):
    def test_a_backticked_camelcase_name_loses_its_ticks(self):
        got = _extract_substrings("`TheGateStaysShutUntilBothItsCratesAreHome`")
        self.assertEqual(("TheGateStaysShutUntilBothItsCratesAreHome",), got)

    def test_the_ticked_form_would_never_have_matched_a_real_log(self):
        # The point of the fix, stated as the failure it prevents.
        log = ("Error: OldDoorYardFunctionalTest: FinishTest TestResult=Failed. "
               "TheGateStaysShutUntilBothItsCratesAreHome: the arch gate opened "
               "at phase 3")
        (sub,) = _extract_substrings("`TheGateStaysShutUntilBothItsCratesAreHome`")
        self.assertIn(sub, log)
        self.assertNotIn("`TheGateStaysShutUntilBothItsCratesAreHome`", log)

    def test_it_reaches_grade_leg_through_the_real_parser(self):
        rows = parse_matrix(_matrix(
            "`empty`", "FAIL (predicted)",
            "`TheGateStaysShutUntilBothItsCratesAreHome`"))
        self.assertIn("empty", rows)
        self.assertEqual(("TheGateStaysShutUntilBothItsCratesAreHome",),
                         rows["empty"].substrings)


class TestTheFixIsMonotone(unittest.TestCase):
    """It may only ever turn an impossible match possible — never the reverse."""

    def test_a_substantive_backticked_literal_is_unchanged(self):
        # This shape already worked (it has spaces and punctuation, so the
        # `substantive` filter keeps it and the last-resort path is never used).
        cell = "`AddItem(Stone,7) returned false; 7 units should fit.`"
        self.assertEqual(("AddItem(Stone,7) returned false; 7 units should fit.",),
                         _extract_substrings(cell))

    def test_the_expected_N_found_M_anchor_pair_is_unchanged(self):
        got = _extract_substrings(
            "expected 1, found 0 (children tagged `SpawnedClone`)")
        self.assertEqual(("expected 1", "found 0"), got)

    def test_a_plain_unticked_cell_is_unchanged(self):
        got = _extract_substrings("the score readout shows 0")
        self.assertEqual(("the score readout shows 0",), got)

    def test_no_returned_substring_ever_contains_a_backtick(self):
        # The invariant, over every shape the docstring records. A tick in the
        # output is by construction unmatchable against a UE log.
        for cell in (
            "`TheGateStaysShutUntilBothItsCratesAreHome`",
            "`AddItem(Stone,7) returned false; 7 units should fit.`",
            "expected 1, found 0 (children tagged `SpawnedClone`)",
            "**bold** `BarewordOnly` and prose",
            "`ANIMBAKE_NO_NEW_TRACK baseline=`",
            "the score readout shows 0",
        ):
            for sub in _extract_substrings(cell):
                self.assertNotIn("`", sub, f"tick survived from {cell!r}")

    def test_an_empty_or_placeholder_cell_still_yields_nothing(self):
        for cell in ("", "   ", "—", "-", "n/a", "N/A"):
            self.assertEqual((), _extract_substrings(cell))

    def test_a_cell_of_only_ticks_does_not_become_a_match_everything(self):
        # Stripping ticks must not leave an EMPTY substring: `"" in log` is
        # always True, which would credit any failure at all as the named one.
        for sub in _extract_substrings("``"):
            self.assertNotEqual("", sub)
        self.assertEqual((), _extract_substrings("``"))


class TestTheRealMatrixItWasFoundOn(unittest.TestCase):
    def test_new_gate_cpp_empty_row_parses_without_ticks(self):
        repo = Path(__file__).resolve().parents[3]
        p = (repo / "tasks" / "cpp"
             / "t3-gate-and-door-cpp"
             / "discrimination" / "MATRIX.md")
        if not p.is_file():
            self.skipTest("task not in this checkout (renamed?)")
        rows = parse_matrix(p.read_text(encoding="utf-8"))
        empty = rows.get("empty")
        self.assertIsNotNone(empty)
        self.assertTrue(empty.substrings, "the empty row records no substring")
        for sub in empty.substrings:
            self.assertNotIn("`", sub)


if __name__ == "__main__":
    unittest.main()
