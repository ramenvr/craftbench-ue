"""run_task --r2 wiring: the advisory is opt-in, rubric-gated, and never fatal.

The R2 judge is a NON-GATING advisory. These tests prove the wiring honors that:
off by default, skipped without a rubric, and — when the judge can't run (no API
key) — it degrades to a non-gating error note instead of raising or affecting the
deterministic outcome.
"""
from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

import run_task  # noqa: E402
from run_task import TaskSpec, _maybe_run_r2  # noqa: E402


RUBRIC_TASK = """## Prompt given to the agent

Do the thing.

## R2 advisory rubric

```json
{"rubric_id":"x/v1","criteria":[{"id":"c1","dimension":"advice_quality",
"statement":"clear","weight":1.0,
"verdict_to_points":{"meets":1.0,"misses":0.0,"n/a":null}}]}
```
"""


def _task(raw: str, src: Path) -> TaskSpec:
    return TaskSpec(task_id="demo", substrate="template", layers=("L1",),
                    raw_text=raw, source_path=src)


def _args(**over):
    base = dict(r2=True, r2_agent_model="agent@x", model="agent@x",
                r2_eval_model="judge@y", r2_ensemble=2, submission=Path("/tmp"))
    base.update(over)
    return types.SimpleNamespace(**base)


class TestR2Wiring(unittest.TestCase):
    def test_off_by_default_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            t = _task(RUBRIC_TASK, d / "t.md")
            self.assertIsNone(_maybe_run_r2(_args(r2=False), t, d, d))

    def test_no_rubric_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            t = _task("## Prompt given to the agent\n\nDo it.\n", d / "t.md")
            self.assertIsNone(_maybe_run_r2(_args(r2=True), t, d, d))

    def test_missing_api_key_degrades_to_non_gating_error(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            task_md = d / "t.md"
            task_md.write_text(RUBRIC_TASK, encoding="utf-8")
            t = _task(RUBRIC_TASK, task_md)
            sub = d / "sub"
            sub.mkdir()
            # clear the key so the subprocess fails fast at its key check
            with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
                block = _maybe_run_r2(_args(submission=sub), t, d, d)
            self.assertIsNotNone(block)
            self.assertIs(block.get("gating"), False)          # never gates
            self.assertEqual(block.get("status"), "error")     # visible, harmless

    def test_runner_path_resolves(self):
        self.assertTrue(run_task._R2_RUNNER.name == "run_r2.py")


if __name__ == "__main__":
    unittest.main()
