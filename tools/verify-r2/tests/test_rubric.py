"""Unit tests for the R2 rubric parser. Pure-Python, no UE, no model."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_VERIFY_R2 = Path(__file__).resolve().parents[1]
if str(_VERIFY_R2) not in sys.path:
    sys.path.insert(0, str(_VERIFY_R2))

from rubric import (  # noqa: E402
    RubricError,
    extract_rubric_json,
    has_r2_rubric,
    parse_r2_rubric,
)

VALID = """
Some prose describing what this rubric judges.

```json
{
  "rubric_id": "r2-row48-project-summary",
  "task_ref": "gold#48",
  "rigor_tier": "R2",
  "ensemble_n": 5,
  "criteria": [
    {"id": "C1", "dimension": "advice_quality",
     "statement": "Every named C++ class exists in the project.",
     "weight": 0.6, "verdict_to_points": {"pass": 1.0, "partial": 0.5, "fail": 0.0, "n/a": null},
     "cites": [{"source": "editor_introspect", "role": "referee"}],
     "required_evidence_kinds": ["editor_introspect"], "evidence_required": true},
    {"id": "C2", "dimension": "advice_quality", "statement": "No hallucinated entities.",
     "weight": 0.4, "verdict_to_points": {"pass": 1.0, "fail": 0.0}}
  ]
}
```
"""


class TestRubric(unittest.TestCase):
    def test_parse_valid(self):
        r = parse_r2_rubric(VALID)
        self.assertEqual(r.rubric_id, "r2-row48-project-summary")
        self.assertEqual(len(r.criteria), 2)
        self.assertEqual(r.criteria[0].dimension, "advice_quality")
        self.assertAlmostEqual(r.criteria[0].weight, 0.6)
        self.assertTrue(r.criteria[0].evidence_required)
        self.assertEqual(r.dimensions, ["advice_quality"])
        self.assertEqual(r.ensemble_n, 5)

    def test_extract_bare_object_fallback(self):
        txt = ('no fence here\n{"rubric_id": "x", "criteria": [{"id": "C1", '
               '"dimension": "advice_quality", "statement": "s", "weight": 1.0, '
               '"verdict_to_points": {"pass": 1.0}}]}')
        self.assertEqual(parse_r2_rubric(txt).rubric_id, "x")

    def test_empty_raises(self):
        with self.assertRaises(RubricError):
            parse_r2_rubric("")
        with self.assertRaises(RubricError):
            extract_rubric_json("   ")

    def test_missing_criteria_raises(self):
        with self.assertRaises(RubricError):
            parse_r2_rubric('```json\n{"rubric_id": "x"}\n```')

    def test_missing_criterion_field_raises(self):
        with self.assertRaises(RubricError):
            parse_r2_rubric('```json\n{"rubric_id": "x", "criteria": '
                            '[{"id": "C1", "dimension": "advice_quality"}]}\n```')

    def test_bad_dimension_raises(self):
        with self.assertRaises(RubricError):
            parse_r2_rubric('```json\n{"rubric_id": "x", "criteria": [{"id": "C1", '
                            '"dimension": "vibes", "statement": "s", "weight": 1.0, '
                            '"verdict_to_points": {"pass": 1.0}}]}\n```')

    def test_has_r2_rubric(self):
        self.assertTrue(has_r2_rubric({"R2 advisory rubric": "```json\n{}\n```"}))
        self.assertFalse(has_r2_rubric({"Prompt given to the agent": "..."}))
        self.assertFalse(has_r2_rubric({"R2 advisory rubric": "   "}))


if __name__ == "__main__":
    unittest.main()
