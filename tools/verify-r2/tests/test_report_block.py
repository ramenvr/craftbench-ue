"""R2 advisory block: round-trip, non-gating self-validation, and the
executable FR-020d proof (advisory score never flips overall)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_R2 = Path(__file__).resolve().parents[1]
if str(_R2) not in sys.path:
    sys.path.insert(0, str(_R2))

from report_block import (  # noqa: E402
    NonGatingViolation,
    R2Advisory,
    compute_overall,
    validate_non_gating,
)


def _adv(score: float) -> R2Advisory:
    return R2Advisory(rigor_tier="R2", evaluator_model_id="m", ensemble_n=5,
                      advisory_score=score, confidence=0.8, confidence_factors={})


class TestReportBlock(unittest.TestCase):
    def test_roundtrip(self):
        b = R2Advisory.from_dict(_adv(0.5).to_dict())
        self.assertEqual(b.advisory_score, 0.5)
        self.assertFalse(b.gating)
        self.assertTrue(b.NON_GATING)

    def test_to_dict_is_non_gating(self):
        d = _adv(0.9).to_dict()
        self.assertFalse(d["gating"])
        self.assertTrue(d["NON_GATING"])

    def test_validate_rejects_gating(self):
        a = _adv(0.5)
        a.gating = True
        with self.assertRaises(NonGatingViolation):
            validate_non_gating(a)

    def test_overall_ignores_advisory(self):
        # Executable FR-020d proof: advisory score can't flip the certified overall.
        passing = ["pass", "pass"]
        self.assertEqual(compute_overall(passing, _adv(0.0)), "pass")
        self.assertEqual(compute_overall(passing, _adv(1.0)), "pass")
        self.assertEqual(compute_overall(passing, None), "pass")
        self.assertEqual(compute_overall(["pass", "fail"], _adv(1.0)), "fail")


if __name__ == "__main__":
    unittest.main()
