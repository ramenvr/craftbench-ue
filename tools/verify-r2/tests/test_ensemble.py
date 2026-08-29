"""R2 ensemble math: weighted score, median aggregation, coverage/agreement/
groundedness confidence, abstention, reliability flags."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_R2 = Path(__file__).resolve().parents[1]
if str(_R2) not in sys.path:
    sys.path.insert(0, str(_R2))

from ensemble import aggregate, score_judge  # noqa: E402


class TestEnsemble(unittest.TestCase):
    def test_score_judge_renormalizes_over_non_na(self):
        s = score_judge({"C1": 1.0, "C2": 0.0, "C3": None}, {"C1": 0.6, "C2": 0.4, "C3": 0.2})
        self.assertAlmostEqual(s, 0.6)  # 0.6*1 / (0.6+0.4)

    def test_aggregate_basic(self):
        weights = {"C1": 0.6, "C2": 0.4}
        judges = [{"C1": 1.0, "C2": 0.0}, {"C1": 1.0, "C2": 0.0}, {"C1": 1.0, "C2": 0.5}]
        r = aggregate(judges, weights, groundedness=1.0)
        self.assertAlmostEqual(r.advisory_score, 0.6)         # median(0.6,0.6,0.8)
        self.assertAlmostEqual(r.confidence_factors["coverage"], 1.0)
        self.assertAlmostEqual(r.confidence_factors["agreement"], 0.8)  # 1 - 0.4*0.5
        self.assertAlmostEqual(r.confidence, 0.8)
        self.assertEqual(r.reliability_flags, [])

    def test_abstain_lowers_coverage(self):
        weights = {"C1": 0.5, "C2": 0.5}
        judges = [{"C1": 1.0, "C2": None}, {"C1": 1.0, "C2": None}]
        r = aggregate(judges, weights)
        self.assertAlmostEqual(r.confidence_factors["coverage"], 0.5)
        self.assertIn("partial_coverage", r.reliability_flags)
        c2 = next(c for c in r.per_criterion if c.criterion_id == "C2")
        self.assertTrue(c2.abstained)

    def test_groundedness_flag_and_factor(self):
        r = aggregate([{"C1": 1.0}], {"C1": 1.0}, groundedness=0.5)
        self.assertIn("ungrounded_claims", r.reliability_flags)
        self.assertAlmostEqual(r.confidence, 0.5)  # 1.0 * 1.0 * 0.5


if __name__ == "__main__":
    unittest.main()
