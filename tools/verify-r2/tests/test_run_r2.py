"""Tests for the R2 orchestrator (run_r2.py).

Covers the workspace-level firewall (judge workspace = substrate ∪ submission,
with CraftBenchTests + gate artifacts excluded) and the end-to-end advisory run
producing a non-gating block + auditable per-judge records.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_R2 = Path(__file__).resolve().parents[1]
if str(_R2) not in sys.path:
    sys.path.insert(0, str(_R2))

import run_r2  # noqa: E402
from run_r2 import build_judge_workspace, run_r2 as run_r2_fn  # noqa: E402


RUBRIC_BLOCK = """## R2 advisory rubric

```json
{
  "rubric_id": "demo/v1",
  "criteria": [
    {"id": "c1", "dimension": "design_quality",
     "statement": "The change is well structured.",
     "weight": 1.0,
     "verdict_to_points": {"meets": 1.0, "partial": 0.5, "misses": 0.0, "n/a": null}}
  ]
}
```
"""

TASK_MD = f"""# Task

## Prompt given to the agent

Implement a pulsing cube and explain the approach.

## Verifier specification

SECRET: actor count must equal 3.

{RUBRIC_BLOCK}
"""


def _make_substrate(root: Path) -> Path:
    """A minimal fake UE project: a writable source file, a verifier-only fixture,
    a gate artifact, plus skip-subtrees that must not be copied."""
    sub = root / "CraftBenchTemplate"
    (sub / "Source" / "CraftBenchTemplate").mkdir(parents=True)
    (sub / "Source" / "CraftBenchTemplate" / "Existing.cpp").write_text("// base", encoding="utf-8")
    (sub / "Source" / "CraftBenchTests").mkdir(parents=True)
    (sub / "Source" / "CraftBenchTests" / "Fixture.cpp").write_text("// ANSWER KEY", encoding="utf-8")
    (sub / "AGENT_WRITABLE.json").write_text('{"writable":["Source/CraftBenchTemplate/"]}', encoding="utf-8")
    (sub / "report.json").write_text('{"outcome":"pass"}', encoding="utf-8")  # a stray gate artifact
    (sub / "Intermediate").mkdir()
    (sub / "Intermediate" / "junk.bin").write_text("regenerated", encoding="utf-8")
    return sub


def _make_submission(root: Path) -> Path:
    sub = root / "submission"
    (sub / "Source" / "CraftBenchTemplate").mkdir(parents=True)
    (sub / "Source" / "CraftBenchTemplate" / "PulseActor.cpp").write_text(
        "// pulse via Time->Sine", encoding="utf-8")
    return sub


class ScriptedJudge:
    def __init__(self, label="meets"):
        self.label = label
        self.calls = {}

    def __call__(self, *, system, messages, tools, judge_index):
        n = self.calls.get(judge_index, 0)
        self.calls[judge_index] = n + 1
        if n == 0:
            return {"type": "tool_call", "tool": "list_submission", "args": {}}
        return {"type": "final", "verdicts": [
            {"criterion_id": "c1", "verdict_label": self.label,
             "rationale": "structured well", "cited_evidence_ids": [f"ev-{judge_index}-0"]}]}


class TestJudgeWorkspace(unittest.TestCase):
    def test_workspace_excludes_answer_key_and_skip_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            substrate = _make_substrate(d)
            submission = _make_submission(d)
            proj = build_judge_workspace(substrate, submission, "t1", root_dir=d / "ws")

            files = {p.relative_to(proj).as_posix() for p in proj.rglob("*") if p.is_file()}
            # submission overlaid
            self.assertIn("Source/CraftBenchTemplate/PulseActor.cpp", files)
            # base substrate source kept
            self.assertIn("Source/CraftBenchTemplate/Existing.cpp", files)
            # firewall: fixtures, gate report, sandbox manifest, skip-dirs all gone
            self.assertNotIn("Source/CraftBenchTests/Fixture.cpp", files)
            self.assertNotIn("report.json", files)
            self.assertNotIn("AGENT_WRITABLE.json", files)
            self.assertFalse(any(f.startswith("Intermediate/") for f in files))

    def test_submission_cannot_smuggle_gate_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            substrate = _make_substrate(d)
            bad = d / "bad-submission"
            bad.mkdir()
            (bad / "report.json").write_text('{"outcome":"pass"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                build_judge_workspace(substrate, bad, "t2", root_dir=d / "ws2")


class TestRunR2(unittest.TestCase):
    def test_end_to_end_advisory_is_non_gating(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            substrate = _make_substrate(d)
            submission = _make_submission(d)
            task_md = d / "demo.md"
            task_md.write_text(TASK_MD, encoding="utf-8")
            out = d / "r2-advisory.json"

            res = run_r2_fn(
                task_md, submission, substrate,
                agent_model_id="agent@x", evaluator_model_id="judge@y",
                llm_call=ScriptedJudge("meets"), n=3,
                out_path=out, root_dir=d / "ws",
            )

            self.assertTrue(out.exists())
            payload = json.loads(out.read_text())
            self.assertFalse(payload["advisory"]["gating"])
            self.assertTrue(payload["advisory"]["NON_GATING"])
            self.assertEqual(payload["advisory"]["advisory_score"], 1.0)
            self.assertEqual(len(payload["judges"]), 3)
            # each judge cited the evidence id it gathered
            self.assertTrue(all(j["verdicts"][0]["grounded"] for j in payload["judges"]))


if __name__ == "__main__":
    unittest.main()
