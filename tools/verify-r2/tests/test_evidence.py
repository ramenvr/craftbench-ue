"""R2 EvidenceRecord: kind allowlist, fuzzy tag, anti-circularity guards, round-trip."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_R2 = Path(__file__).resolve().parents[1]
if str(_R2) not in sys.path:
    sys.path.insert(0, str(_R2))

from evidence.record import (  # noqa: E402
    AntiCircularityViolation,
    EvidenceItem,
    EvidenceRecord,
)


class TestEvidence(unittest.TestCase):
    def test_kind_allowlist_enforced(self):
        with self.assertRaises(ValueError):
            EvidenceItem("e1", "not_a_source", "P2")
        e = EvidenceItem("e1", "editor_introspect", "P2", payload={"x": 1})
        self.assertEqual(e.determinism, "deterministic")
        self.assertTrue(e.artifact_sha256)  # auto content-address

    def test_screenshot_is_fuzzy(self):
        self.assertEqual(EvidenceItem("e2", "viewport_screenshot", "P5").determinism, "fuzzy")

    def test_anticircular_ok(self):
        r = EvidenceRecord("t", "R2", "sha", evaluator_model_pinned="opus", agent_model_id="sonnet")
        r.evidence.append(EvidenceItem("e1", "editor_introspect", "P2"))
        r.assert_anticircular()  # must not raise

    def test_anticircular_aura_tool_raises(self):
        r = EvidenceRecord("t", "R2", "sha", aura_mcp_tools_invoked=["mcp__unreal_editor__bp_agent"])
        with self.assertRaises(AntiCircularityViolation):
            r.assert_anticircular()

    def test_anticircular_self_grading_raises(self):
        r = EvidenceRecord("t", "R2", "sha", evaluator_model_pinned="x", agent_model_id="x")
        with self.assertRaises(AntiCircularityViolation):
            r.assert_anticircular()

    def test_roundtrip_and_sha(self):
        r = EvidenceRecord("t", "R2", "sha", evaluator_model_pinned="opus", agent_model_id="sonnet")
        r.evidence.append(EvidenceItem("e1", "editor_introspect", "P2", payload={"a": 1}))
        d = r.to_dict()
        r2 = EvidenceRecord.from_dict(d)
        self.assertEqual(r2.ids(), ["e1"])
        self.assertEqual(r2.record_sha256(), r.record_sha256())
        self.assertTrue(d["anti_circularity"]["evaluator_differs_from_agent"])
        self.assertEqual(d["anti_circularity"]["aura_mcp_tools_invoked"], [])


if __name__ == "__main__":
    unittest.main()
