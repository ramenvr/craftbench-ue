"""Tests for the 2026-08-13 standardization rules in tasklint.

These rules exist to stop the drift a survey of all 59 tasks measured (section
order 29/59, requirements table 16/49, category enum 42/59). The tests below
pin the two things that made the rules trustworthy in the first place:

  * they fire on the real defects (a leg that cannot be credited, a variant dir
    with no row, a shared FAIL literal);
  * they do NOT fire on a well-formed modern package. That half matters more —
    the first draft of `_submission_tables` matched any table containing the
    word "submission" and flagged every good package, because the §7
    requirements table has a column "What a submission could get away with".
    A second draft still flagged kp-engine-source-search, whose requirements
    table names a column "Named failure substring". Both regressions are
    covered here.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

from tasklint import (  # noqa: E402
    _classify_row_label,
    _md_tables,
    _rule_matrix_requirements_table,
    _rule_matrix_structure,
    _rule_matrix_variant_bijection,
    _rule_section_order,
    _submission_tables,
)

# A well-formed package: ONE submission table (message column + classifying
# rows) plus a §7 requirements table that mentions "submission" AND
# "substring" in its headers — the exact shape that broke two earlier drafts.
GOOD_MATRIX = """# Discrimination matrix — demo

## Matrix

| Submission | Overall | Fails at (check id) | Expected substring | Notes |
|---|---|---|---|---|
| `../reference` | PASS | — | — | all green |
| empty | FAIL | `thing_exists` | `THING_MISSING path=` | fans out |

## Requirements table (checklist §7, the mandatory soundness artifact)

| # | Prompt requirement | Asserted | Named failure substring | What a submission could get away with |
|---|---|---|---|---|
| 1 | a thing exists | fully | `THING_MISSING path=` / `THING_BROKEN id=` | naming it anything |
"""


class TestTableDetection(unittest.TestCase):
    def test_requirements_table_is_not_a_submission_table(self):
        """The regression that mattered: a good package must yield exactly one
        submission table even though its requirements table names columns
        containing both 'submission' and 'substring'."""
        self.assertEqual(len(_submission_tables(GOOD_MATRIX)), 1)

    def test_md_tables_finds_both_tables(self):
        self.assertEqual(len(_md_tables(GOOD_MATRIX)), 2)

    def test_row_label_classification_mirrors_the_runner(self):
        self.assertEqual(_classify_row_label("`../reference`"), "reference")
        self.assertEqual(_classify_row_label("empty"), "empty")
        self.assertEqual(_classify_row_label("`no-cap/`"), "no-cap")
        # Prose rows contribute no label — this is why a requirements table
        # never collides with the submission table's keys.
        self.assertIsNone(_classify_row_label("1"))
        self.assertIsNone(_classify_row_label("a thing exists"))


class _MatrixCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.task = Path(self._tmp.name) / "demo-task"
        (self.task / "discrimination").mkdir(parents=True)
        self.spec = self.task / "task.md"
        self.spec.write_text("# demo\n", encoding="utf-8")

    def write_matrix(self, text: str) -> None:
        (self.task / "discrimination" / "MATRIX.md").write_text(
            text, encoding="utf-8")

    def rules_from(self, fn) -> list[str]:
        return [f.rule for f in fn(self.spec, "", {}, _Ctx())]


class _Ctx:
    repo_root = None
    spec = None


class TestMatrixStructure(_MatrixCase):
    def test_good_matrix_is_silent(self):
        self.write_matrix(GOOD_MATRIX)
        self.assertEqual(self.rules_from(_rule_matrix_structure), [])

    def test_multi_literal_cell_is_flagged(self):
        """grade_leg matches ALL literals in a cell, so a second literal that is
        never logged makes the leg uncreditable — the real defect found in
        gp-poison-dot-stack-cpp."""
        self.write_matrix(GOOD_MATRIX.replace(
            "| empty | FAIL | `thing_exists` | `THING_MISSING path=` | fans out |",
            "| empty | FAIL | `thing_exists` | `THING_MISSING path=` and `StackLimitCount = 0` | fans out |"))
        self.assertIn("matrix-row-single-literal",
                      self.rules_from(_rule_matrix_structure))

    def test_non_ascii_literal_is_flagged(self):
        self.write_matrix(GOOD_MATRIX.replace("THING_MISSING path=",
                                              "THING_MISSING — path="))
        self.assertIn("matrix-row-ascii", self.rules_from(_rule_matrix_structure))

    def test_reference_row_em_dash_is_not_a_literal(self):
        """The reference row's '—' cell is legitimately empty, not a literal."""
        self.write_matrix(GOOD_MATRIX)
        self.assertNotIn("matrix-row-ascii",
                         self.rules_from(_rule_matrix_structure))


class TestVariantBijection(_MatrixCase):
    def test_unrowed_variant_dir_is_flagged(self):
        self.write_matrix(GOOD_MATRIX)
        (self.task / "discrimination" / "no-cap").mkdir()
        self.assertIn("matrix-variant-unrowed",
                      self.rules_from(_rule_matrix_variant_bijection))

    def test_rowed_variant_dir_is_silent(self):
        self.write_matrix(GOOD_MATRIX.replace(
            "| empty | FAIL |",
            "| `no-cap/` | FAIL | `x` | `X_MISSING id=` | v |\n| empty | FAIL |"))
        (self.task / "discrimination" / "no-cap").mkdir()
        self.assertEqual(self.rules_from(_rule_matrix_variant_bijection), [])


class TestRequirementsTable(_MatrixCase):
    def test_present_is_silent(self):
        self.write_matrix(GOOD_MATRIX)
        self.assertEqual(self.rules_from(_rule_matrix_requirements_table), [])

    def test_absent_is_flagged(self):
        self.write_matrix(GOOD_MATRIX.split("## Requirements table")[0])
        self.assertIn("matrix-requirements-table",
                      self.rules_from(_rule_matrix_requirements_table))


class TestSectionOrder(unittest.TestCase):
    def _order(self, headings):
        sections = {h: "" for h in headings}
        return [f.rule for f in _rule_section_order(Path("x"), "", sections, _Ctx())]

    def test_canonical_order_is_silent(self):
        self.assertEqual(self._order([
            "Primary concept", "Prompt given to the agent",
            "Workspace state pre-task", "Verifier specification",
            "Reference solution metadata", "Anti-gaming notes"]), [])

    def test_legacy_order_is_flagged(self):
        """The 30-spec legacy shape: anti-gaming hoisted above primary concept."""
        self.assertIn("spec-section-order", self._order([
            "Prompt given to the agent", "Workspace state pre-task",
            "Anti-gaming notes", "Primary concept", "Verifier specification"]))

    def test_a_missing_section_does_not_imply_disorder(self):
        """Presence is a different rule's job; order must judge only order."""
        self.assertEqual(self._order([
            "Primary concept", "Verifier specification", "Anti-gaming notes"]), [])


if __name__ == "__main__":
    unittest.main()
