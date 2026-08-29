"""R2 EvidenceRecord — the frozen, content-addressed bundle the judge consumes.

Anti-circular by construction: every item is produced by a stock-UE primitive
CraftBench controls; the record carries an attestation that no Aura MCP tool and
no agent-under-test was on the capture path, and that the evaluator model differs
from the agent's. Pure data — NO UE, NO Aura import here.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

_R2 = Path(__file__).resolve().parents[1]
if str(_R2) not in sys.path:
    sys.path.insert(0, str(_R2))

from config import EVIDENCE_SOURCES, FUZZY_SOURCES  # noqa: E402


class AntiCircularityViolation(ValueError):
    """Raised when the evidence record breaches the anti-circularity invariant."""


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


@dataclass
class EvidenceItem:
    evidence_id: str
    kind: str                 # MUST be one of config.EVIDENCE_SOURCES
    primitive: str            # "P1".."P5" / "workspace-read"
    payload: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
    artifact_sha256: str = ""

    @property
    def determinism(self) -> str:
        return "fuzzy" if self.kind in FUZZY_SOURCES else "deterministic"

    def __post_init__(self):
        if self.kind not in EVIDENCE_SOURCES:
            raise ValueError(
                f"evidence kind {self.kind!r} not in the closed allowlist {EVIDENCE_SOURCES}"
            )
        if not self.artifact_sha256:
            self.artifact_sha256 = sha256_text(json.dumps(self.payload, sort_keys=True))


@dataclass
class EvidenceRecord:
    task_id: str
    rigor_tier: str
    submission_sha: str
    evidence: List[EvidenceItem] = field(default_factory=list)
    aura_mcp_tools_invoked: List[str] = field(default_factory=list)  # MUST stay empty
    agent_under_test_consulted: bool = False                          # MUST stay False
    evaluator_model_pinned: str = ""
    agent_model_id: str = ""

    def ids(self) -> List[str]:
        return [e.evidence_id for e in self.evidence]

    def assert_anticircular(self) -> None:
        """Raise unless the capture path used only CraftBench stock-UE primitives."""
        if self.aura_mcp_tools_invoked:
            raise AntiCircularityViolation(
                f"Aura MCP tools on the capture path: {self.aura_mcp_tools_invoked}"
            )
        if self.agent_under_test_consulted:
            raise AntiCircularityViolation("agent-under-test consulted for evidence")
        if (self.evaluator_model_pinned and self.agent_model_id
                and self.evaluator_model_pinned == self.agent_model_id):
            raise AntiCircularityViolation(
                "evaluator model equals agent-under-test model (self-grading)"
            )

    def record_sha256(self) -> str:
        h = hashlib.sha256()
        for e in sorted(self.evidence, key=lambda x: x.evidence_id):
            h.update(e.evidence_id.encode("utf-8"))
            h.update(b"\0")
            h.update(e.artifact_sha256.encode("utf-8"))
            h.update(b"\0")
        return h.hexdigest()

    def to_dict(self) -> dict:
        return {
            "schema": "craftbench.r2.evidence_record/v1",
            "task_id": self.task_id,
            "rigor_tier": self.rigor_tier,
            "submission_sha": self.submission_sha,
            "anti_circularity": {
                "primitives_allowlist": list(EVIDENCE_SOURCES),
                "aura_mcp_tools_invoked": list(self.aura_mcp_tools_invoked),
                "agent_under_test_consulted": self.agent_under_test_consulted,
                "evaluator_model_pinned": self.evaluator_model_pinned,
                "evaluator_differs_from_agent": (
                    self.evaluator_model_pinned != self.agent_model_id
                ),
            },
            "record_sha256": self.record_sha256(),
            "evidence": [
                {
                    "evidence_id": e.evidence_id, "kind": e.kind, "primitive": e.primitive,
                    "determinism": e.determinism, "payload": e.payload,
                    "provenance": e.provenance, "artifact_sha256": e.artifact_sha256,
                }
                for e in self.evidence
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EvidenceRecord":
        ac = d.get("anti_circularity", {})
        rec = cls(
            task_id=d["task_id"],
            rigor_tier=d.get("rigor_tier", "R2"),
            submission_sha=d.get("submission_sha", ""),
            aura_mcp_tools_invoked=list(ac.get("aura_mcp_tools_invoked", [])),
            agent_under_test_consulted=bool(ac.get("agent_under_test_consulted", False)),
            evaluator_model_pinned=ac.get("evaluator_model_pinned", ""),
        )
        for e in d.get("evidence", []):
            rec.evidence.append(EvidenceItem(
                evidence_id=e["evidence_id"], kind=e["kind"], primitive=e.get("primitive", ""),
                payload=e.get("payload", {}), provenance=e.get("provenance", {}),
                artifact_sha256=e.get("artifact_sha256", ""),
            ))
        return rec
