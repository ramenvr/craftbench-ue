"""A drive that produced NOTHING must not grade as a model failure.

Measured 2026-08-17, and the reason the model slate's cheap end was at risk:

    bare:deepseek/deepseek-v4-flash on gp-dot-aoe-burn-cpp
    -> agent exit 1, 0 turns, 0 tool calls, 0 tokens, "TimeoutError: The read
       operation timed out" (the LLM call's per-read timeout was hardcoded 60s)
    -> submission snapshot found the UNTOUCHED scaffold, so it was NOT empty
    -> the empty-submission guard never ran
    -> the verifier graded the unmodified scaffold: L1 pass, L2 fail
    -> recorded verdict: **FAIL**, against the model

The bias is directional: slow and cheap models time out more, so this
manufactured fake FAILs at exactly the low-price end of the slate — against the
price-vs-capability claim the sweep exists to test. It is also invisible after the
fact, because a fake FAIL and a real FAIL are byte-identical in the report.

The pre-existing ``_agent_config_error`` could not cover it twice over: it keys on
Claude-CLI transcript artifacts no other adapter emits, AND it is only consulted
when the snapshot is empty.

Half of this file asserts the guard DECLINES. A too-permissive version hands the
model under test a denominator opt-out, which is strictly worse than the bug.
"""

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from adapters.base import (  # noqa: E402
    VERDICT_AGENT_CONFIG_ERROR,
    VERDICT_AGENT_TRANSPORT_ERROR,
    is_graded_verdict,
)
from run import _agent_never_ran  # noqa: E402


class _Result:
    """Minimal AgentResult stand-in; only the fields the predicate reads."""

    def __init__(self, exit_code=0, num_turns=0, tool_use_count=0,
                 tokens_in=None, tokens_out=None, summary=""):
        self.exit_code = exit_code
        self.num_turns = num_turns
        self.tool_use_count = tool_use_count
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.summary = summary


#: The exact shape recorded by the 2026-08-17 run, from its agent_result.json.
THE_MEASURED_RUN = _Result(
    exit_code=1, num_turns=0, tool_use_count=0, tokens_in=None, tokens_out=None,
    summary="bare adapter error: TimeoutError: The read operation timed out")


class TestFiresOnTheMeasuredShape(unittest.TestCase):

    def test_the_2026_08_17_timeout(self):
        reason = _agent_never_ran(THE_MEASURED_RUN)
        self.assertIsNotNone(reason)
        self.assertIn("timed out", reason)

    def test_it_reports_the_adapter_message_verbatim(self):
        """The operator needs the provider's words to know whether to re-run or
        fix something."""
        self.assertIn("bare adapter error", _agent_never_ran(THE_MEASURED_RUN))

    def test_it_still_fires_when_the_adapter_reports_no_summary(self):
        """A silent adapter must not escape the guard for lack of a message."""
        reason = _agent_never_ran(_Result(exit_code=1, summary=""))
        self.assertIsNotNone(reason)
        self.assertIn("no turns", reason)

    def test_zero_tokens_spelled_as_0_also_fires(self):
        """Adapters differ: some report None for "no usage", some report 0."""
        self.assertIsNotNone(_agent_never_ran(
            _Result(exit_code=1, tokens_in=0, tokens_out=0, summary="503")))


class TestDeclinesOnEverythingThatMustStayGraded(unittest.TestCase):
    """The important half."""

    def test_a_successful_drive_declines(self):
        self.assertIsNone(_agent_never_ran(
            _Result(exit_code=0, num_turns=4, tool_use_count=6,
                    tokens_in=900, tokens_out=120)))

    def test_a_model_that_BURNED_TOKENS_and_did_nothing_still_grades(self):
        """THE load-bearing case. This is a real model outcome — it ran, it just
        produced nothing — and it must remain FAIL_NO_EDITS. Excusing it would let
        any model leave the denominator by erroring after one call."""
        self.assertIsNone(_agent_never_ran(
            _Result(exit_code=1, num_turns=0, tool_use_count=0,
                    tokens_in=1500, tokens_out=0, summary="crashed after a call")))
        self.assertIsNone(_agent_never_ran(
            _Result(exit_code=1, tokens_in=0, tokens_out=42, summary="x")))

    def test_a_drive_that_took_a_turn_still_grades(self):
        """One turn means the provider answered — the model was measured."""
        self.assertIsNone(_agent_never_ran(
            _Result(exit_code=1, num_turns=1, summary="died in turn 2")))

    def test_a_drive_that_called_a_tool_still_grades(self):
        """Tool calls cannot happen without a model response."""
        self.assertIsNone(_agent_never_ran(
            _Result(exit_code=1, tool_use_count=1, summary="died mid-tool")))

    def test_a_ZERO_exit_with_no_work_still_grades(self):
        """A clean exit having done nothing is a lazy model, not a fault. This is
        the boundary that keeps 'did nothing' from becoming a free pass."""
        self.assertIsNone(_agent_never_ran(
            _Result(exit_code=0, num_turns=0, tool_use_count=0)))

    def test_it_does_not_match_on_error_TEXT(self):
        """Deliberately text-blind: matching "timeout"/"429" would silently
        re-grade every provider message we failed to predict, and the four zeros
        already prove nothing was measured."""
        for msg in ("some phrasing we have never seen", "", "429", "boom"):
            with self.subTest(msg=msg):
                # zeros present -> fires regardless of wording
                self.assertIsNotNone(_agent_never_ran(
                    _Result(exit_code=1, summary=msg)))
                # a token spent -> declines regardless of wording
                self.assertIsNone(_agent_never_ran(
                    _Result(exit_code=1, tokens_out=1, summary=msg)))


class TestTheVerdictStaysOutOfEveryPassRate(unittest.TestCase):

    def test_both_agent_verdicts_are_non_graded(self):
        self.assertFalse(is_graded_verdict(VERDICT_AGENT_TRANSPORT_ERROR))
        self.assertFalse(is_graded_verdict(VERDICT_AGENT_CONFIG_ERROR))

    def test_transport_and_config_are_DISTINCT(self):
        """They demand opposite responses — re-run the rep vs fix our setup — so
        collapsing them would hide which one a sweep's losses were."""
        self.assertNotEqual(VERDICT_AGENT_TRANSPORT_ERROR,
                            VERDICT_AGENT_CONFIG_ERROR)


class TestTheTimeoutIsNoLongerHardcoded(unittest.TestCase):

    def test_it_derives_from_the_run_ceiling(self):
        from adapters.bare import BareAdapter
        # 900s ceiling -> 300s per call, not 60.
        self.assertEqual(BareAdapter.llm_timeout_for(900), 300.0)
        self.assertGreater(BareAdapter.llm_timeout_for(900), 60.0)

    def test_a_short_ceiling_still_gets_the_generous_floor(self):
        """A small ceiling must not re-impose a timeout that cuts off a slow
        model mid-answer — that is the bug, not a scaled-down version of it."""
        from adapters.aura_mcp import DEFAULT_LLM_TIMEOUT_S
        from adapters.bare import BareAdapter
        self.assertEqual(BareAdapter.llm_timeout_for(30), DEFAULT_LLM_TIMEOUT_S)

    def test_env_override_wins(self):
        import os
        from adapters.bare import BareAdapter
        prev = os.environ.get("CB_BARE_LLM_TIMEOUT_S")
        os.environ["CB_BARE_LLM_TIMEOUT_S"] = "45"
        try:
            self.assertEqual(BareAdapter.llm_timeout_for(900), 45.0)
        finally:
            if prev is None:
                os.environ.pop("CB_BARE_LLM_TIMEOUT_S", None)
            else:
                os.environ["CB_BARE_LLM_TIMEOUT_S"] = prev

    def test_a_typo_does_not_silently_restore_the_old_60s(self):
        import os
        from adapters.bare import BareAdapter
        prev = os.environ.get("CB_BARE_LLM_TIMEOUT_S")
        os.environ["CB_BARE_LLM_TIMEOUT_S"] = "not-a-number"
        try:
            self.assertEqual(BareAdapter.llm_timeout_for(900), 300.0)
        finally:
            if prev is None:
                os.environ.pop("CB_BARE_LLM_TIMEOUT_S", None)
            else:
                os.environ["CB_BARE_LLM_TIMEOUT_S"] = prev


class TestTheWallClockCeilingIsEnforced(unittest.TestCase):
    """`--ceiling` bounded NOTHING until 2026-08-17.

    Measured: a bare drive ran 2199s against a nominal 600s ceiling and 105 turns
    against an uncapped turn count. `timeout_s` only shrank the per-TOOL deadline.
    Across a 500-run sweep one wedged drive is unbounded machine time.
    """

    def _loop(self, *, wall_deadline, turns=50, clock_step=0.0):
        """Drive run_loop with a model that NEVER stops asking for tools.

        ``clock_step`` advances a FAKE monotonic clock by that much per reading, so
        the ceiling is exercised deterministically. A real-time deadline cannot be
        tested here: the mocked call and dispatch are instant, so 5000 turns finish
        inside 50ms and a wall-clock assertion silently tests nothing.
        """
        from adapters import aura_mcp
        calls = {"n": 0}

        def llm_call(**_kw):
            calls["n"] += 1
            return {
                "content": [{"type": "tool_use", "id": "t", "name": "x", "input": {}}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }

        real_monotonic = aura_mcp.time.monotonic
        if clock_step:
            state = {"t": real_monotonic()}

            def fake():
                state["t"] += clock_step
                return state["t"]
            aura_mcp.time.monotonic = fake
        try:
            rec = aura_mcp.run_loop(
                base_url="", api_key="k", task_prompt="go", model="m",
                max_turns=turns, tool_deadline=1.0, max_tokens=16,
                anthropic_tools=[], llm_call=llm_call,
                dispatch=lambda *a, **k: {"bSuccess": True, "result_text": "ok"},
                wall_deadline=wall_deadline,
            )
        finally:
            aura_mcp.time.monotonic = real_monotonic
        return rec, calls["n"]

    def test_an_already_passed_deadline_stops_before_any_call(self):
        import time
        rec, n = self._loop(wall_deadline=time.monotonic() - 1)
        self.assertEqual(n, 0)
        self.assertEqual(rec.num_turns, 0)

    def test_it_stops_well_short_of_the_turn_cap(self):
        """The turn cap cannot substitute for a clock: a slow model blows the clock
        long before it blows 1000 turns."""
        import time
        # Fake clock advances 1s per reading; deadline 10s out -> stops in a handful
        # of turns, nowhere near the 5000 cap.
        rec, n = self._loop(wall_deadline=time.monotonic() + 10,
                            turns=5000, clock_step=1.0)
        self.assertLess(rec.num_turns, 50)
        self.assertLess(n, 50)
        self.assertGreater(rec.num_turns, 0)

    def test_no_deadline_preserves_the_old_behaviour(self):
        """None must mean "turn cap only" so every existing caller is unchanged."""
        rec, n = self._loop(wall_deadline=None, turns=7)
        self.assertEqual(rec.num_turns, 7)
        self.assertEqual(n, 7)

    def test_hitting_the_ceiling_stays_GRADED(self):
        """Running out of the disclosed budget is a MODEL outcome, not a fault.

        exit 0 so the verifier still grades whatever it wrote; a non-graded route
        here would let a slow model leave the denominator by being slow.
        """
        import time
        rec, _ = self._loop(wall_deadline=time.monotonic() + 10,
                            turns=5000, clock_step=1.0)
        self.assertEqual(rec.exit_code, 0)

    def test_the_summary_says_WHICH_budget_ran_out(self):
        """Reporting 'max turns reached' for a clock stop would send the next
        person tuning the wrong knob."""
        import time
        rec, _ = self._loop(wall_deadline=time.monotonic() - 1)
        self.assertIn("wall-clock", (rec.summary or "").lower())
        rec2, _ = self._loop(wall_deadline=None, turns=2)
        self.assertIn("max turns", (rec2.summary or "").lower())

    def test_a_ceiling_stop_is_not_mistaken_for_a_transport_fault(self):
        """It must not produce the 0-turn/error shape `_agent_never_ran` reads as
        non-graded — otherwise the ceiling becomes a denominator opt-out."""
        import time
        rec, _ = self._loop(wall_deadline=time.monotonic() + 10,
                            turns=5000, clock_step=1.0)
        from adapters.aura_mcp import record_to_agent_result
        res = record_to_agent_result(rec, is_mcp_tool=lambda _n: False)
        self.assertIsNone(_agent_never_ran(res))


class TestTheCeilingReachesTheBaselineLane(unittest.TestCase):

    def test_cb_forwards_the_ceiling_on_the_baseline_lane(self):
        """It forwarded on the two MCP lanes and NOT on baseline, so run.py's own
        default silently won. Asserted on the source because the lane shells out."""
        src = (_ROOT / "aura_rig" / "cb.py").read_text(encoding="utf-8")
        baseline = src[src.index("=== GRADED EVAL (baseline") - 1200:
                       src.index("=== GRADED EVAL (baseline")]
        self.assertIn('"--timeout", str(args.ceiling)', baseline)

    def test_both_defaults_are_1200(self):
        src = (_ROOT / "aura_rig" / "cb.py").read_text(encoding="utf-8")
        self.assertIn('"--ceiling", type=int, default=1200', src)
        run_src = (_ROOT / "run.py").read_text(encoding="utf-8")
        self.assertIn('"--timeout", type=int, default=1200', run_src)


class TestAHungCallCannotOutliveTheCeiling(unittest.TestCase):
    """The gap the first ceiling fix left open.

    Checking the clock at the TURN BOUNDARY cannot interrupt a call already in
    flight. Measured 2026-08-17: a bare drive sat 65 minutes inside ONE call under
    a 20-minute ceiling and wrote nothing — the model was fine (Sonnet 5 smoke-drove
    the same path in 2 turns), the call just never returned.

    Two things close it: the per-call budget is clamped to the REMAINING ceiling,
    and the budget is enforced as a TOTAL wall clock rather than urllib's per-read
    socket timeout (which resets on every byte, so keepalives defeat it).
    """

    def test_the_budget_is_capped_by_what_is_left(self):
        import time
        from adapters.aura_mcp import _call_budget
        # 300s per-call figure, but only 20s of ceiling remains -> 20s.
        self.assertAlmostEqual(
            _call_budget(300.0, time.monotonic() + 20), 20, delta=1.0)

    def test_it_never_exceeds_the_per_call_figure(self):
        import time
        from adapters.aura_mcp import _call_budget
        self.assertAlmostEqual(
            _call_budget(120.0, time.monotonic() + 9999), 120.0, delta=1.0)

    def test_an_almost_spent_ceiling_still_gets_a_usable_floor(self):
        """A 0s or negative budget would abort instantly and read as a provider
        fault — manufacturing exactly the non-graded verdict we just stopped
        manufacturing."""
        import time
        from adapters.aura_mcp import MIN_CALL_BUDGET_S, _call_budget
        self.assertEqual(_call_budget(300.0, time.monotonic() - 500),
                         MIN_CALL_BUDGET_S)

    def test_no_ceiling_leaves_the_per_call_figure_alone(self):
        from adapters.aura_mcp import _call_budget
        self.assertEqual(_call_budget(250.0, None), 250.0)

    def test_the_total_wall_clock_is_enforced_not_the_socket_timeout(self):
        """A responsive socket that never COMPLETES must still be abandoned.

        Simulates the measured failure: reads keep succeeding (so urllib's own
        timeout never fires) but the response never finishes.
        """
        import time
        from adapters import bare_wire

        real_inner = bare_wire._post_json_inner

        def never_completes(*_a, **_k):
            time.sleep(5)          # longer than the budget below
            return {"model": "m", "choices": [], "usage": {}}

        bare_wire._post_json_inner = never_completes
        try:
            t0 = time.monotonic()
            with self.assertRaises(bare_wire.ProviderCallTimeout):
                bare_wire._post_json("http://x", {}, {}, 0.5)
            # Returned promptly rather than waiting out the sleep.
            self.assertLess(time.monotonic() - t0, 3.0)
        finally:
            bare_wire._post_json_inner = real_inner

    def test_a_prompt_response_is_unaffected(self):
        """The wrapper must not add latency or mangle the happy path."""
        from adapters import bare_wire
        real_inner = bare_wire._post_json_inner
        bare_wire._post_json_inner = lambda *_a, **_k: {"ok": 1}
        try:
            self.assertEqual(bare_wire._post_json("http://x", {}, {}, 30.0),
                             {"ok": 1})
        finally:
            bare_wire._post_json_inner = real_inner

    def test_a_provider_error_still_propagates_with_its_body(self):
        """The thread must re-raise on the caller's side, body intact — otherwise
        this fix would silently undo the 403-diagnosis fix."""
        from adapters import bare_wire
        real_inner = bare_wire._post_json_inner

        def boom(*_a, **_k):
            raise bare_wire.ProviderHTTPError(403, '{"error":"confirm 18+"}')

        bare_wire._post_json_inner = boom
        try:
            with self.assertRaises(bare_wire.ProviderHTTPError) as ctx:
                bare_wire._post_json("http://x", {}, {}, 30.0)
            self.assertIn("confirm 18+", str(ctx.exception))
        finally:
            bare_wire._post_json_inner = real_inner


class TestWorkDoneBeforeATransportErrorSurvives(unittest.TestCase):
    """The four-zeros guard, inverted into a denominator opt-out.

    `bare._fail` hardcodes num_turns=0 / tool_use_count=0 / no tokens, so when a
    transport error escaped `run_loop` every count was erased — and
    `_agent_never_ran` then saw four zeros and pulled a drive that HAD worked out of
    the denominator. Measured 2026-08-17: grok-4.6 drove the full 1200s ceiling on
    gp-dot-aoe-burn-bp and recorded "0 turns, never ran".

    So `run_loop` now returns its real counts on a transport error. That is what
    makes the guard mean what it claims: it fires only when nothing was ATTEMPTED.
    """

    def _loop_that_dies_on_call(self, die_on_call):
        from adapters.aura_mcp import run_loop
        n = {"i": 0}

        def llm_call(**_kw):
            n["i"] += 1
            if n["i"] == die_on_call:
                raise RuntimeError("provider exploded")
            return {
                "content": [{"type": "tool_use", "id": "t", "name": "x", "input": {}}],
                "usage": {"input_tokens": 1000, "output_tokens": 50},
            }

        return run_loop(
            base_url="", api_key="k", task_prompt="go", model="m",
            max_turns=50, tool_deadline=1.0, max_tokens=16, anthropic_tools=[],
            llm_call=llm_call,
            dispatch=lambda *a, **k: {"bSuccess": True, "result_text": "ok"},
        )

    def test_turns_and_tokens_survive_the_error(self):
        rec = self._loop_that_dies_on_call(4)
        self.assertEqual(rec.num_turns, 3)          # 3 completed before the failure
        self.assertEqual(rec.tokens_in, 3000)
        self.assertEqual(rec.tokens_out, 150)
        self.assertEqual(len(rec.tool_names), 3)
        self.assertEqual(rec.exit_code, 1)

    def test_such_a_run_STAYS_GRADED(self):
        """It worked for three turns and spent tokens — a model outcome."""
        from adapters.aura_mcp import record_to_agent_result
        res = record_to_agent_result(self._loop_that_dies_on_call(4),
                                     is_mcp_tool=lambda _n: False)
        self.assertIsNone(_agent_never_ran(res))

    def test_a_failure_on_the_FIRST_call_is_still_non_graded(self):
        """The genuine never-ran case must keep working — that is the whole point of
        the guard, and this is the boundary between the two."""
        from adapters.aura_mcp import record_to_agent_result
        rec = self._loop_that_dies_on_call(1)
        self.assertEqual(rec.num_turns, 0)
        self.assertEqual(rec.tokens_in, 0)
        res = record_to_agent_result(rec, is_mcp_tool=lambda _n: False)
        self.assertIsNotNone(_agent_never_ran(res))

    def test_the_summary_names_how_far_it_got(self):
        rec = self._loop_that_dies_on_call(3)
        self.assertIn("2 turn", rec.summary or "")
        self.assertIn("provider exploded", rec.summary or "")


class TestEveryAgentResultFieldReachesDisk(unittest.TestCase):
    """A field the adapter fills and the writer omits is invisible to every analysis.

    This bug has now happened twice in two days — `tokens_in` (2026-08-17) and the
    scaffold-identity fields (2026-08-18) — so it gets a structural test instead of a
    third fix. Any NEW AgentResult field must either be serialized by
    `run._write_result` or be listed here with a reason.
    """

    #: Fields deliberately not written to result.json, with why.
    NOT_SERIALIZED = {
        "transcript",    # written to its own agent_transcript.jsonl (can be MBs)
        "generation_ids",  # provider join keys; belong with the transcript, not the
                           # summary row — revisit if cost auditing needs them inline
    }

    def test_no_field_is_silently_dropped(self):
        import re
        from dataclasses import fields
        from adapters.base import AgentResult
        src = (_ROOT / "run.py").read_text(encoding="utf-8")
        # Whitespace-tolerant: the writer wraps long calls across lines, and a
        # single-line pattern reported two already-serialized fields as missing.
        written = set(re.findall(r'getattr\(\s*agent_result,\s*"(\w+)"', src, re.S))
        written |= set(re.findall(r'"(\w+)":\s*agent_result\.', src))
        missing = {f.name for f in fields(AgentResult)} - written - self.NOT_SERIALIZED
        self.assertEqual(
            missing, set(),
            f"AgentResult fields never written to result.json: {sorted(missing)}. "
            "Serialize them in run._write_result, or add them to NOT_SERIALIZED "
            "with a reason.")


class TestTruncationIsNotAFinishedTurn(unittest.TestCase):
    """A max_tokens cut-off must not read as "the model chose to stop".

    Measured 2026-08-18: `bare:anthropic/claude-opus-5` on gp-dot-aoe-burn-cpp
    explored for 20 turns, got truncated at the 8192-token output limit, and the loop
    ended because the final turn had no tool calls — recorded as a clean exit 0 and
    graded FAIL_NO_EDITS. OpenRouter returns finish_reason="length" with
    content=None and no tool_calls, which is byte-identical to a genuine stop.

    The bias direction is what makes it serious: it fires on models that write the
    LONGEST turns, i.e. disproportionately the strong ones, and charges our config
    to them — the same defect class as the transport-error bug, mirrored.
    """

    def _run(self, finish_reasons):
        """Drive run_loop over a scripted sequence of (finish_reason, has_tool) turns."""
        from adapters.aura_mcp import run_loop
        seq = list(finish_reasons)
        calls = {"n": 0}

        def llm_call(**_kw):
            i = calls["n"]
            calls["n"] += 1
            reason, has_tool = seq[i] if i < len(seq) else ("stop", False)
            content = ([{"type": "tool_use", "id": "t", "name": "x", "input": {}}]
                       if has_tool else [])
            return {"content": content, "usage": {"input_tokens": 5, "output_tokens": 5},
                    "finish_reason": reason}

        rec = run_loop(
            base_url="", api_key="k", task_prompt="go", model="m", max_turns=20,
            tool_deadline=1.0, max_tokens=100, anthropic_tools=[], llm_call=llm_call,
            dispatch=lambda *a, **k: {"bSuccess": True, "result_text": "ok"})
        return rec, calls["n"]

    def test_a_truncated_turn_gets_another_turn(self):
        """Truncated, then it makes a tool call, then stops -> the drive continued."""
        rec, n = self._run([("length", False), ("stop", True), ("stop", False)])
        self.assertEqual(n, 3)
        self.assertEqual(rec.truncated_turns, 1)
        self.assertEqual(len(rec.tool_names), 1)

    def test_a_CLEAN_stop_still_ends_the_drive(self):
        """The done-condition must survive: no tool calls and finish_reason != length
        is a real finish, and treating it as truncation would never terminate."""
        rec, n = self._run([("stop", False)])
        self.assertEqual(n, 1)
        self.assertEqual(rec.truncated_turns, 0)

    def test_a_missing_finish_reason_is_treated_as_a_clean_stop(self):
        """Endpoints that report nothing must not be read as truncated — that would
        turn every such provider into an infinite loop."""
        rec, n = self._run([(None, False)])
        self.assertEqual(n, 1)
        self.assertEqual(rec.truncated_turns, 0)

    def test_repeated_truncation_is_still_bounded_by_the_turn_cap(self):
        """A model truncated every turn must not spin forever."""
        rec, n = self._run([("length", False)] * 50)
        self.assertLessEqual(n, 20)
        self.assertGreater(rec.truncated_turns, 1)

    def test_the_output_budget_is_no_longer_8192(self):
        from adapters.aura_mcp import DEFAULT_MAX_TOKENS
        self.assertGreater(DEFAULT_MAX_TOKENS, 8192)


if __name__ == "__main__":
    unittest.main()
