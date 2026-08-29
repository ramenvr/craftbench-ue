"""An empty submission is ambiguous — tell a CONFIG fault from a lazy model.

Measured 2026-08-10: `cb eval --model aura-mcp:opus-5` handed an AURA model key
to `claude -p`, whose CLI rejected it outright. The run produced 0 turns, 0
tokens and `model=<synthetic>`, and graded **FAIL_NO_EDITS** — indistinguishable
from a model that did nothing, which is why it read as a tool-access problem for
days while both boxes dug through the auth layer.

The rule is explicit: never let a non-agent condition reach a graded
verdict. These tests pin the discrimination, and especially the NEGATIVE side —
a classifier that over-fires would hand every model a way out of the denominator.
"""

from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run as _run  # noqa: E402
from adapters.base import is_graded_verdict  # noqa: E402


_MSG = ("There's an issue with the selected model (opus-5). It may not exist or "
        "you may not have access to it. Run --model to pick a different model.")

# Verbatim shape of the real failing run (runs/aura-mcp/20260810-051706-…).
_ASSISTANT = {"type": "assistant", "message": {
    "model": "<synthetic>", "role": "assistant",
    "usage": {"input_tokens": 0, "output_tokens": 0},
    "content": [{"type": "text", "text": _MSG}]}}
_RESULT = {"type": "result", "subtype": "success", "is_error": True,
           "duration_api_ms": 0, "num_turns": 1, "terminal_reason": "api_error",
           "total_cost_usd": 0,
           "usage": {"input_tokens": 0, "output_tokens": 0}}


def _res(*records):
    return types.SimpleNamespace(
        transcript="\n".join(json.dumps(r) for r in records))


class TestAgentConfigError(unittest.TestCase):

    def test_returns_the_agents_OWN_words(self):
        # The CLI's message names the offending value; a summary of ours would
        # lose it and send the reader back to the transcript.
        self.assertEqual(_run._agent_config_error(_res(_ASSISTANT, _RESULT)), _MSG)

    def test_real_tokens_mean_the_model_DID_run(self):
        spent = dict(_RESULT, usage={"input_tokens": 5000, "output_tokens": 12})
        self.assertIsNone(_run._agent_config_error(_res(_ASSISTANT, spent)))

    def test_a_different_terminal_reason_is_not_excused(self):
        other = dict(_RESULT, terminal_reason="max_turns")
        self.assertIsNone(_run._agent_config_error(_res(_ASSISTANT, other)))

    def test_a_crash_with_no_terminal_record_is_not_excused(self):
        # Must be POSITIVELY established. A transcript that merely CARRIES the
        # <synthetic> marker but never reached a terminal record could be a
        # mid-run crash, and excusing that would hide real faults.
        self.assertIsNone(_run._agent_config_error(_res(_ASSISTANT)))

    def test_no_synthetic_marker_short_circuits(self):
        self.assertIsNone(_run._agent_config_error(_res(_RESULT)))

    def test_missing_or_empty_transcript_is_safe(self):
        self.assertIsNone(_run._agent_config_error(types.SimpleNamespace()))
        self.assertIsNone(_run._agent_config_error(_res()))

    def test_a_truncated_tail_line_does_not_break_it(self):
        r = _res(_ASSISTANT, _RESULT)
        r.transcript += '\n{"type": "resu'
        self.assertEqual(_run._agent_config_error(r), _MSG)


class TestVerdictIsNonGraded(unittest.TestCase):

    def test_AGENT_CONFIG_ERROR_stays_out_of_every_pass_rate(self):
        # GRADED_VERDICTS is an allowlist, so this holds by construction — but
        # pin it, because the whole point is that a config fault must never be
        # counted against a model.
        self.assertFalse(is_graded_verdict("AGENT-CONFIG-ERROR"))
        self.assertTrue(is_graded_verdict("PASS"))
        self.assertTrue(is_graded_verdict("FAIL"))


if __name__ == "__main__":
    unittest.main()



class TestEveryEmptySubmissionPathAsksFirst(unittest.TestCase):
    """Wiring, not behaviour: the 2026-08-10 fix reached only one of run.py's two
    empty-submission branches, so the same fault recurred on the live path."""

    def test_no_path_writes_FAIL_NO_EDITS_without_consulting_the_guard(self):
        import ast
        tree = ast.parse(Path(_run.__file__).read_text(encoding="utf-8"))
        offenders = [
            n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and "'FAIL_NO_EDITS'" in ast.dump(n)
            and "_agent_config_error" not in ast.dump(n)
        ]
        self.assertEqual(offenders, [], f"unguarded FAIL_NO_EDITS paths: {offenders}")
