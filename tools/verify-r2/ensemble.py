"""R2 ensemble aggregation + reliability. Pure math — no model, no UE.

Two numbers, deliberately separated: ``advisory_score`` (how good, conditional
on captured evidence) and ``confidence = coverage × agreement × groundedness``
(how much to trust that score). See the design §5.
"""
from __future__ import annotations

import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

_R2 = Path(__file__).resolve().parent
if str(_R2) not in sys.path:
    sys.path.insert(0, str(_R2))

from config import AGREEMENT_LOW  # noqa: E402


@dataclass
class CriterionAgg:
    criterion_id: str
    ensemble_points: Optional[float]   # None when every judge abstained (n/a)
    spread: float
    agreement_fraction: float
    n_judges: int
    weight: float
    abstained: bool


@dataclass
class EnsembleResult:
    advisory_score: float
    confidence: float
    confidence_factors: Dict[str, float]
    per_criterion: List[CriterionAgg]
    reliability_flags: List[str] = field(default_factory=list)


def score_judge(verdicts: Dict[str, Optional[float]], weights: Dict[str, float]) -> Optional[float]:
    """One judge's weighted score over its non-``n/a`` criteria (renormalized)."""
    num = den = 0.0
    for cid, pts in verdicts.items():
        if pts is None:  # n/a → excluded from score, lowers coverage instead
            continue
        w = weights.get(cid, 0.0)
        num += w * pts
        den += w
    return (num / den) if den > 0 else None


def aggregate(
    judges: List[Dict[str, Optional[float]]],
    weights: Dict[str, float],
    groundedness: float = 1.0,
) -> EnsembleResult:
    """Aggregate N judges' per-criterion points into an advisory score + confidence.

    ``judges`` — one dict per judge, mapping criterion_id → points (or None for n/a).
    ``weights`` — criterion_id → weight. ``groundedness`` — fraction of criteria
    whose rationale quote-check passed (the numeric anti-fluency arm).
    """
    per_criterion: List[CriterionAgg] = []
    flags: List[str] = []
    total_w = sum(weights.values()) or 1.0
    covered_w = 0.0
    weighted_spread_num = weighted_spread_den = 0.0

    for cid, w in weights.items():
        real = [j.get(cid) for j in judges]
        real = [p for p in real if p is not None]
        if not real:
            per_criterion.append(CriterionAgg(cid, None, 0.0, 0.0, 0, w, True))
            continue
        covered_w += w
        med = statistics.median(real)
        spread = max(real) - min(real)
        agree = sum(1 for p in real if abs(p - med) < 1e-9) / len(real)
        per_criterion.append(CriterionAgg(cid, med, spread, agree, len(real), w, False))
        weighted_spread_num += w * spread
        weighted_spread_den += w
        if agree < AGREEMENT_LOW:
            flags.append(f"low_agreement:{cid}")

    judge_scores = [s for s in (score_judge(j, weights) for j in judges) if s is not None]
    advisory_score = statistics.median(judge_scores) if judge_scores else 0.0
    coverage = covered_w / total_w
    agreement = (1.0 - weighted_spread_num / weighted_spread_den) if weighted_spread_den else 0.0
    confidence = coverage * agreement * groundedness
    if coverage < 0.999:
        flags.append("partial_coverage")
    if groundedness < 0.999:
        flags.append("ungrounded_claims")

    return EnsembleResult(
        advisory_score=advisory_score,
        confidence=confidence,
        confidence_factors={
            "coverage": coverage, "agreement": agreement, "groundedness": groundedness,
        },
        per_criterion=per_criterion,
        reliability_flags=flags,
    )
