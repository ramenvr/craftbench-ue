"""R2 rubric model + parser (advisory-only evaluator).

A rubric is authored INLINE in a task's ``## R2 advisory rubric`` H2 section as a
fenced ```json block (per the maintainer decision: inline, parsed by the same
``_split_h2_sections`` machinery as every other task section). It is
verifier-owned, hash-pinned, and review-gated — like a fixture.

This module parses + validates a rubric into dataclasses. It judges nothing and
touches no model — pure data. Design intent: judge.py's module docstring.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from config import DIMENSIONS  # noqa: E402

# A fenced ```json / ```jsonc block, or (fallback) a bare {...} object.
_JSON_FENCE_RE = re.compile(r"```(?:json|jsonc)?\s*(?P<body>\{.*\})\s*```", re.DOTALL)

# The H2 heading text the runner uses as the join key.
RUBRIC_SECTION = "R2 advisory rubric"


class RubricError(ValueError):
    """Raised when a rubric section is missing, malformed, or invalid."""


# Tokens that would let a task-authored ground-truth "fact" act as a grading
# instruction to the judge (the system prompt treats ground-truth as
# authoritative). A fact must state PROJECT TRUTH, never how to score (#4).
_GRADING_TOKENS = ("score", "verdict", "grade", "grading", "rubric")


def _validate_groundtruth_facts(facts) -> None:
    for f in facts:
        low = str(f).lower()
        hit = next((t for t in _GRADING_TOKENS if t in low), None)
        if hit:
            raise RubricError(
                f"groundtruth fact carries a grading directive (token {hit!r}); facts must "
                f"state project truths, not how to score: {f!r}")


@dataclass
class Criterion:
    id: str
    dimension: str
    statement: str
    weight: float
    verdict_to_points: Dict[str, Optional[float]]
    cites: List[Dict[str, str]] = field(default_factory=list)
    required_evidence_kinds: List[str] = field(default_factory=list)
    verdict_scale: Dict[str, str] = field(default_factory=dict)
    evidence_required: bool = True
    rationale_required: bool = True


@dataclass
class Rubric:
    rubric_id: str
    criteria: List[Criterion]
    task_ref: str = ""
    rubric_version: str = "1.0.0"
    rigor_tier: str = "R2"
    evaluator_model_pin: str = ""
    ensemble_n: int = 5
    score_policy: Dict[str, Any] = field(default_factory=dict)
    exemplars: Dict[str, Any] = field(default_factory=dict)

    @property
    def dimensions(self) -> List[str]:
        seen: set = set()
        out: List[str] = []
        for c in self.criteria:
            if c.dimension not in seen:
                seen.add(c.dimension)
                out.append(c.dimension)
        return out


def extract_rubric_json(section_text: str) -> str:
    """Pull the JSON body from a ``## R2 advisory rubric`` section.

    Prefers a fenced ```json block; falls back to the first ``{`` .. last ``}``.
    """
    if not section_text or not section_text.strip():
        raise RubricError("empty R2 advisory rubric section")
    m = _JSON_FENCE_RE.search(section_text)
    if m:
        return m.group("body")
    start = section_text.find("{")
    end = section_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise RubricError("no JSON object found in R2 advisory rubric section")
    return section_text[start:end + 1]


def parse_r2_rubric(section_text: str) -> Rubric:
    """Parse + validate an inline rubric section into a ``Rubric``."""
    raw = extract_rubric_json(section_text)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RubricError(f"rubric JSON parse error: {e}") from e
    if not isinstance(obj, dict):
        raise RubricError("rubric must be a JSON object")

    rid = obj.get("rubric_id")
    if not rid:
        raise RubricError("rubric missing 'rubric_id'")

    raw_criteria = obj.get("criteria")
    if not isinstance(raw_criteria, list) or not raw_criteria:
        raise RubricError("rubric missing a non-empty 'criteria' list")

    criteria: List[Criterion] = []
    for i, c in enumerate(raw_criteria):
        if not isinstance(c, dict):
            raise RubricError(f"criterion #{i} is not an object")
        for req in ("id", "dimension", "statement", "weight", "verdict_to_points"):
            if req not in c:
                raise RubricError(f"criterion #{i} missing '{req}'")
        if c["dimension"] not in DIMENSIONS:
            raise RubricError(
                f"criterion {c['id']!r} dimension {c['dimension']!r} not in {DIMENSIONS}"
            )
        try:
            weight = float(c["weight"])
        except (TypeError, ValueError) as e:
            raise RubricError(f"criterion {c['id']!r} weight not a number") from e
        criteria.append(Criterion(
            id=str(c["id"]),
            dimension=str(c["dimension"]),
            statement=str(c["statement"]),
            weight=weight,
            verdict_to_points=dict(c["verdict_to_points"]),
            cites=list(c.get("cites", [])),
            required_evidence_kinds=list(c.get("required_evidence_kinds", [])),
            verdict_scale=dict(c.get("verdict_scale", {})),
            evidence_required=bool(c.get("evidence_required", True)),
            rationale_required=bool(c.get("rationale_required", True)),
        ))

    score_policy = dict(obj.get("score_policy", {}))
    _validate_groundtruth_facts(score_policy.get("groundtruth_facts", []))

    return Rubric(
        rubric_id=str(rid),
        criteria=criteria,
        task_ref=str(obj.get("task_ref", "")),
        rubric_version=str(obj.get("rubric_version", "1.0.0")),
        rigor_tier=str(obj.get("rigor_tier", "R2")),
        evaluator_model_pin=str(obj.get("evaluator_model_pin", "")),
        ensemble_n=int(obj.get("ensemble_n", 5)),
        score_policy=score_policy,
        exemplars=dict(obj.get("exemplars", {})),
    )


def has_r2_rubric(sections: Dict[str, str]) -> bool:
    """True if a task's H2-section map carries a non-empty R2 advisory rubric."""
    return bool(sections.get(RUBRIC_SECTION, "").strip())
