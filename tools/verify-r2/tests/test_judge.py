"""Tests for the firewalled tool-using judge-agent (judge.py).

Headline invariant: the judge is FIREWALLED from the deterministic answer key —
the gate's verdict/report, the reference solution, and the verifier-spec /
anti-gaming sections never reach its context. Plus: the loop maps a scripted
model's verdicts onto the rubric, records auditable evidence, and the ensemble
yields a NON-GATING advisory block.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_R2 = Path(__file__).resolve().parents[1]
if str(_R2) not in sys.path:
    sys.path.insert(0, str(_R2))

import judge  # noqa: E402
from judge import (  # noqa: E402
    FirewallViolation,
    JudgeContext,
    ToolSpec,
    assert_firewalled,
    build_judge_context,
    build_readonly_fs_tools,
    extract_judge_visible_prompt,
    run_ensemble,
    run_one_judge,
)
from config import EVIDENCE_SOURCES  # noqa: E402
from report_block import compute_overall, validate_non_gating  # noqa: E402


# A task .md carrying BOTH the agent-visible surface and the answer key. The
# answer-key sections must never survive into the judge's prompt.
SECRET_SPEC = "SECRET-VERIFIER-DETAIL: assert actor count == 3 in PIE"
SECRET_ANTIGAME = "GAMING-DEFENSE: reject hardcoded literal 42"
SECRET_REF = "REFERENCE-ANSWER: return Value * 2 in TickComponent"

TASK_MD = f"""# Task

## Task ID
demo-advisory

## Prompt given to the agent

Make the cube pulse and write a short note explaining your approach.

## Workspace state pre-task

A default third-person project with one cube actor tagged "Target".

## Verifier specification

{SECRET_SPEC}

## Anti-gaming notes

{SECRET_ANTIGAME}

## Reference solution

{SECRET_REF}

## R2 advisory rubric

```json
{{
  "rubric_id": "demo-advisory/v1",
  "criteria": [
    {{
      "id": "c1",
      "dimension": "advice_quality",
      "statement": "The note clearly explains the chosen approach.",
      "weight": 1.0,
      "verdict_to_points": {{"meets": 1.0, "partial": 0.5, "misses": 0.0, "n/a": null}}
    }}
  ]
}}
```
"""

AGENT_MODEL = "anthropic/agent-under-test@x"
EVAL_MODEL = "anthropic/independent-judge@y"


def _ctx(workspace: Path, submission: Path, **over) -> JudgeContext:
    kw = dict(
        task_md=TASK_MD, task_id="demo-advisory",
        submission_root=submission, workspace_root=workspace,
        agent_model_id=AGENT_MODEL, evaluator_model_id=EVAL_MODEL,
    )
    kw.update(over)
    return build_judge_context(**kw)


class ScriptedJudge:
    """A deterministic stand-in for the LLM: investigate once, then submit."""

    def __init__(self, label: str = "meets"):
        self.label = label
        self.calls: dict = {}

    def __call__(self, *, system, messages, tools, judge_index):
        n = self.calls.get(judge_index, 0)
        self.calls[judge_index] = n + 1
        if n == 0:
            return {"type": "tool_call", "tool": "read_submission_file",
                    "args": {"path": "note.txt"}}
        return {"type": "final", "verdicts": [
            {"criterion_id": "c1", "verdict_label": self.label,
             "rationale": "the note explains the approach",
             "cited_evidence_ids": [f"ev-{judge_index}-0"]},
        ]}


class TestFirewallScrub(unittest.TestCase):
    def test_visible_prompt_keeps_only_allowlisted_sections(self):
        p = extract_judge_visible_prompt(TASK_MD)
        self.assertIn("Make the cube pulse", p)
        self.assertIn('tagged "Target"', p)  # workspace state survives
        # none of the answer-key bodies leak
        self.assertNotIn(SECRET_SPEC, p)
        self.assertNotIn(SECRET_ANTIGAME, p)
        self.assertNotIn(SECRET_REF, p)

    def test_build_context_is_firewalled_and_carries_rubric(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = _ctx(Path(d), Path(d))
            self.assertNotIn(SECRET_SPEC, ctx.behavior_prompt)
            self.assertEqual(ctx.rubric.criteria[0].id, "c1")
            # structurally, the context has no field that could carry a gate verdict
            fields = set(ctx.__dataclass_fields__)
            self.assertFalse(any(k in fields for k in ("gate", "verdict", "report", "outcome")))


class TestFirewallEnforcement(unittest.TestCase):
    def _good_ctx(self, d: Path) -> JudgeContext:
        return _ctx(d, d)

    def test_clean_context_passes(self):
        with tempfile.TemporaryDirectory() as d:
            assert_firewalled(self._good_ctx(Path(d)), raw_task_md=TASK_MD)  # no raise

    def test_rejects_self_grading(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FirewallViolation):
                _ctx(Path(d), Path(d), evaluator_model_id=AGENT_MODEL)

    def test_rejects_leaked_answer_key_in_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = self._good_ctx(Path(d))
            ctx.behavior_prompt = ctx.behavior_prompt + "\n" + SECRET_SPEC
            with self.assertRaises(FirewallViolation):
                assert_firewalled(ctx, raw_task_md=TASK_MD)

    def test_rejects_reachable_gate_report(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = self._good_ctx(Path(d))
            ctx.reachable_paths = ("Source/Foo.cpp", "report.json")
            with self.assertRaises(FirewallViolation):
                assert_firewalled(ctx)

    def test_rejects_reachable_reference_solution(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = self._good_ctx(Path(d))
            ctx.reachable_paths = ("reference-solutions/demo/Source/Foo.cpp",)
            with self.assertRaises(FirewallViolation):
                assert_firewalled(ctx)

    def test_no_gate_result_tool_can_construct(self):
        # gate_result is firewalled OUT of EVIDENCE_SOURCES → a tool exposing it
        # cannot even be built.
        self.assertNotIn("gate_result", EVIDENCE_SOURCES)
        with self.assertRaises(ValueError):
            ToolSpec("sneaky", "gate_result", "P0", "peek at the deterministic verdict")


class TestJudgeLoop(unittest.TestCase):
    def _mk(self):
        d = tempfile.mkdtemp()
        (Path(d) / "note.txt").write_text("I made it pulse via a Time->Sine node.", encoding="utf-8")
        ctx = _ctx(Path(d), Path(d))
        tools = build_readonly_fs_tools(Path(d))
        return ctx, tools

    def test_one_judge_maps_verdict_and_records_evidence(self):
        ctx, tools = self._mk()
        res = run_one_judge(ctx, ScriptedJudge("meets"), tools, judge_index=0)
        self.assertEqual(res.points_by_criterion["c1"], 1.0)
        self.assertTrue(res.verdicts[0].grounded)
        # the tool result was recorded as auditable, allowlisted evidence
        self.assertEqual(len(res.evidence.evidence), 1)
        self.assertIn(res.evidence.evidence[0].kind, EVIDENCE_SOURCES)
        res.evidence.assert_anticircular()  # no aura/agent/self-grading on the path

    def test_partial_verdict_maps_to_half_points(self):
        ctx, tools = self._mk()
        res = run_one_judge(ctx, ScriptedJudge("partial"), tools)
        self.assertEqual(res.points_by_criterion["c1"], 0.5)

    def test_missing_criterion_abstains(self):
        ctx, tools = self._mk()

        def empty_final(*, system, messages, tools, judge_index):
            return {"type": "final", "verdicts": []}

        res = run_one_judge(ctx, empty_final, tools)
        self.assertIsNone(res.points_by_criterion["c1"])
        self.assertEqual(res.verdicts[0].verdict_label, "n/a")


class TestEnsembleNonGating(unittest.TestCase):
    def test_ensemble_is_non_gating(self):
        d = tempfile.mkdtemp()
        (Path(d) / "note.txt").write_text("explanation", encoding="utf-8")
        ctx = _ctx(Path(d), Path(d))
        tools = build_readonly_fs_tools(Path(d))
        advisory, results = run_ensemble(ctx, ScriptedJudge("meets"), tools, n=3)

        self.assertEqual(len(results), 3)
        self.assertFalse(advisory.gating)
        self.assertTrue(advisory.NON_GATING)
        validate_non_gating(advisory)            # no raise
        self.assertEqual(advisory.advisory_score, 1.0)
        self.assertEqual(advisory.ensemble_n, 3)
        # the advisory can never flip the certified overall (FR-020d)
        self.assertEqual(compute_overall(["pass"], advisory), "pass")
        self.assertEqual(compute_overall(["fail"], advisory), "fail")


if __name__ == "__main__":
    unittest.main()
