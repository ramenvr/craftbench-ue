"""R2 advisory report block — the NON-GATING field attached to a Verdict.

The deterministic ``outcome`` is computed BEFORE R2 runs and is read-only to R2.
This block is ``gating: false`` by construction; ``validate_non_gating()``
refuses anything else, and the leaderboard renders it as a second-class
"advisory — not certified" column. Pure data — no model, no UE.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_R2 = Path(__file__).resolve().parent
if str(_R2) not in sys.path:
    sys.path.insert(0, str(_R2))

from config import R2_CONTRACT_VERSION  # noqa: E402


class NonGatingViolation(ValueError):
    """Raised when an R2 advisory block is anything other than non-gating."""


@dataclass
class R2Advisory:
    rigor_tier: str
    evaluator_model_id: str
    ensemble_n: int
    advisory_score: float                 # informational ONLY — never gates
    confidence: float
    confidence_factors: Dict[str, float]
    per_criterion: List[Dict[str, Any]] = field(default_factory=list)
    run_level_agreement_alpha: Optional[float] = None
    reliability_flags: List[str] = field(default_factory=list)
    evidence_record_sha256: str = ""
    evaluator_contract_version: str = R2_CONTRACT_VERSION
    gating: bool = False                  # hard-coded; NEVER True
    NON_GATING: bool = True

    def to_dict(self) -> dict:
        return {
            "rigor_tier": self.rigor_tier,
            "gating": False,
            "NON_GATING": True,
            "evaluator_model_id": self.evaluator_model_id,
            "evaluator_contract_version": self.evaluator_contract_version,
            "ensemble_n": self.ensemble_n,
            "advisory_score": self.advisory_score,
            "confidence": self.confidence,
            "confidence_factors": dict(self.confidence_factors),
            "run_level_agreement_alpha": self.run_level_agreement_alpha,
            "reliability_flags": list(self.reliability_flags),
            "evidence_record_sha256": self.evidence_record_sha256,
            "per_criterion": list(self.per_criterion),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "R2Advisory":
        return cls(
            rigor_tier=d.get("rigor_tier", "R2"),
            evaluator_model_id=d.get("evaluator_model_id", ""),
            ensemble_n=int(d.get("ensemble_n", 0)),
            advisory_score=float(d.get("advisory_score", 0.0)),
            confidence=float(d.get("confidence", 0.0)),
            confidence_factors=dict(d.get("confidence_factors", {})),
            per_criterion=list(d.get("per_criterion", [])),
            run_level_agreement_alpha=d.get("run_level_agreement_alpha"),
            reliability_flags=list(d.get("reliability_flags", [])),
            evidence_record_sha256=d.get("evidence_record_sha256", ""),
            evaluator_contract_version=d.get("evaluator_contract_version", R2_CONTRACT_VERSION),
        )


def validate_non_gating(advisory: R2Advisory) -> None:
    """Raise unless the advisory block is non-gating (the FR-020d guard)."""
    if advisory.gating is not False:
        raise NonGatingViolation("r2_advisory.gating must be False")
    if advisory.NON_GATING is not True:
        raise NonGatingViolation("r2_advisory.NON_GATING must be True")


def compute_overall(layer_statuses: Iterable[str], r2_advisory: Optional[R2Advisory] = None) -> str:
    """The certified overall — DETERMINISTIC layers only; R2 is structurally ignored.

    Mirrors run_task's overall computation and exists to make the non-gating
    invariant EXECUTABLE: ``r2_advisory`` is accepted but never read, so no R2
    value can change the result. PASS iff every deterministic layer passed.
    """
    statuses = list(layer_statuses)
    return "pass" if statuses and all(s == "pass" for s in statuses) else "fail"
