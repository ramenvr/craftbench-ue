"""Unit tests for run_batch — the product-neutral two-pool batch orchestrator
(spec §6, §11).

Everything the orchestrator touches is INJECTED, so these run fully offline:
NO Unreal editor, NO Aura, NO claude, NO network, NO real API key. We use a
FAKE adapter (records its run, optionally emits, can be told to fail/timeout),
a FAKE Environment (configurable ``max_concurrency``, instruments observed
acting concurrency), a FAKE verify callable (records + returns a canned
verdict), and an injected clock.

We assert the normative behaviours:

  (1) Pool-A effective width = min(--concurrency, env.max_concurrency):
      NullEnvironment(5) runs up to 5 at once; AuraEditorEnvironment(1) runs
      strictly sequentially (instrument max observed concurrency).
  (2) Pool-B (verify) is bounded by verify_concurrency.
  (3) Phase transitions land in status.json (queued → running → grading → done).
  (4) result.json is written atomically BEFORE status.json.phase flips to done.
  (5) A failing task is isolated — the others still complete.
  (6) Cancellation stops NEW task starts (in-flight drain, no new acquires).

Mirrors the sibling tests' sys.path + unittest convention (test_environment.py,
test_run_events.py). asyncio coroutines are driven with ``asyncio.run``.

Run from tools/run-agent:

    python3 -m unittest tests.test_run_batch
"""

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run_batch import (  # noqa: E402
    BatchTask,
    Cancellation,
    run_batch,
)


# Deterministic, monotonically-advancing clock (same shape as test_run_events).
class _StubClock:
    def __init__(self, start: int = 0):
        self._t = start

    def __call__(self) -> str:
        self._t += 1
        return f"2026-06-04T00:00:{self._t:02d}Z"


# --------------------------------------------------------------------------
# Fakes — NO UE, NO Aura, NO claude, NO network
# --------------------------------------------------------------------------

class _FakeResult:
    """Stand-in for adapters.base.AgentResult — only the bits result.json reads."""

    def __init__(self, exit_code=0):
        self.exit_code = exit_code
        self.duration_s = 0.0
        self.summary = "ok"
        self.tool_use_count = 2
        self.mcp_tool_use_count = 1
        self.tool_names = ["a", "b"]
        self.cost_usd = 0.01
        self.num_turns = 1
        self.tokens_in = 100
        self.tokens_out = 50


class _FakeAdapter:
    name = "fake-adapter"

    def run(self, *args, **kwargs):  # never actually called (env.run_one is faked)
        return _FakeResult()


class _ConcurrencyProbeEnv:
    """Fake Environment that records the MAX number of run_one()s acting at once.

    ``run_one`` awaits an event before returning so the harness can pin several
    tasks "in flight" simultaneously and read off the peak concurrency. This is
    the instrument for asserting Pool-A width = min(--concurrency, max).
    """

    def __init__(self, max_concurrency, *, fail_ids=None, timeout_ids=None):
        self.max_concurrency = max_concurrency
        self._fail_ids = set(fail_ids or [])
        self._timeout_ids = set(timeout_ids or [])
        self.active = 0
        self.peak = 0
        self.setup_calls = 0
        self.teardown_calls = 0
        self.precheck_calls = 0
        # An asyncio.Event the test sets to let all in-flight run_one()s return.
        self.release = None
        self.lock = None

    def setup(self):
        self.setup_calls += 1

    def precheck(self):
        self.precheck_calls += 1

    def teardown(self):
        self.teardown_calls += 1

    def workspace_for(self, task):
        return object()

    async def run_one(self, task, adapter, events):
        # Track concurrency of *acting* (Pool A holds the slot across this).
        async with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            tid = task.task_id
            if tid in self._timeout_ids:
                raise asyncio.TimeoutError(f"fake timeout for {tid}")
            if tid in self._fail_ids:
                raise RuntimeError(f"fake adapter failure for {tid}")
            # Wait until the test releases everyone (so peak can build up).
            if self.release is not None:
                await self.release.wait()
            return _FakeResult()
        finally:
            async with self.lock:
                self.active -= 1


class _SequentialProbeEnv(_ConcurrencyProbeEnv):
    """Same probe but run_one returns immediately (no release gate needed) —
    used for the strictly-sequential aura case where overlap would mean a bug."""

    async def run_one(self, task, adapter, events):
        async with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            # Yield control so any (buggy) concurrent task could overlap if the
            # semaphore width were >1.
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            return _FakeResult()
        finally:
            async with self.lock:
                self.active -= 1


class _VerifyProbe:
    """Fake verify callable. Records concurrency + order; returns a canned verdict.

    Signature mirrors the orchestrator's verify seam:
        verify(task, agent_result, events) -> (overall, report)
    """

    def __init__(self, *, gate=False, verdict="PASS"):
        self.calls = []
        self.active = 0
        self.peak = 0
        self.verdict = verdict
        self._gate = gate
        self.release = None
        self.lock = None

    async def __call__(self, task, agent_result, events):
        async with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            self.calls.append(task.task_id)
            if self._gate and self.release is not None:
                await self.release.wait()
            return (self.verdict, {"task_id": task.task_id, "overall": self.verdict})
        finally:
            async with self.lock:
                self.active -= 1


def _make_tasks(n):
    return [
        BatchTask(
            task_id=f"t{i}",
            run_id=f"20260604-000000-t{i}-claude-p",
            product="claude-p:opus",
            max_steps=40,
            timeout_s=600,
            payload={},
        )
        for i in range(n)
    ]


def _read_status(run_root: Path, run_id: str) -> dict:
    return json.loads((run_root / run_id / "status.json").read_text(encoding="utf-8"))


class _BatchCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="run-batch-test-"))

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def _drive(self, coro):
        return asyncio.run(coro)


# --------------------------------------------------------------------------
# (1) Pool-A width = min(--concurrency, env.max_concurrency)
# --------------------------------------------------------------------------

class TestPoolAWidth(_BatchCase):
    def test_null_env_runs_up_to_five_at_once(self):
        env = _ConcurrencyProbeEnv(max_concurrency=5)

        async def go():
            env.lock = asyncio.Lock()
            env.release = asyncio.Event()
            verify = _VerifyProbe()
            verify.lock = asyncio.Lock()
            tasks = _make_tasks(8)

            async def releaser():
                # Wait until all 5 slots are occupied, then let them finish.
                while env.peak < 5:
                    await asyncio.sleep(0)
                env.release.set()

            await asyncio.gather(
                run_batch(
                    tasks,
                    env=env,
                    make_adapter=lambda slug: _FakeAdapter(),
                    verify=verify,
                    concurrency=5,
                    verify_concurrency=1,
                    run_root=self.tmp,
                    now=_StubClock(),
                ),
                releaser(),
            )

        self._drive(go())
        # 5-wide cap honored: peak acting == 5 (never 6+), and >1 (truly concurrent).
        self.assertEqual(env.peak, 5)

    def test_concurrency_flag_caps_below_env_max(self):
        # --concurrency 3 with env.max=5 → effective width 3.
        env = _ConcurrencyProbeEnv(max_concurrency=5)

        async def go():
            env.lock = asyncio.Lock()
            env.release = asyncio.Event()
            verify = _VerifyProbe()
            verify.lock = asyncio.Lock()
            tasks = _make_tasks(8)

            async def releaser():
                # Once we've seen the cap saturated (3), release.
                for _ in range(2000):
                    if env.peak >= 3:
                        break
                    await asyncio.sleep(0)
                env.release.set()

            await asyncio.gather(
                run_batch(
                    tasks, env=env, make_adapter=lambda s: _FakeAdapter(),
                    verify=verify, concurrency=3, verify_concurrency=1,
                    run_root=self.tmp, now=_StubClock(),
                ),
                releaser(),
            )

        self._drive(go())
        self.assertEqual(env.peak, 3)

    def test_aura_env_runs_strictly_sequentially(self):
        # AuraEditorEnvironment-style max_concurrency=1 → peak acting must be 1
        # regardless of --concurrency=5.
        env = _SequentialProbeEnv(max_concurrency=1)

        async def go():
            env.lock = asyncio.Lock()
            verify = _VerifyProbe()
            verify.lock = asyncio.Lock()
            tasks = _make_tasks(6)
            await run_batch(
                tasks, env=env, make_adapter=lambda s: _FakeAdapter(),
                verify=verify, concurrency=5, verify_concurrency=1,
                run_root=self.tmp, now=_StubClock(),
            )

        self._drive(go())
        self.assertEqual(env.peak, 1)  # strictly sequential


# --------------------------------------------------------------------------
# (2) Pool-B bounded by verify_concurrency
# --------------------------------------------------------------------------

class TestPoolBBound(_BatchCase):
    def test_verify_concurrency_one_serializes_grading(self):
        env = _ConcurrencyProbeEnv(max_concurrency=5)
        verify = _VerifyProbe(gate=True)

        async def go():
            env.lock = asyncio.Lock()
            verify.lock = asyncio.Lock()
            verify.release = asyncio.Event()
            tasks = _make_tasks(6)

            async def releaser():
                # Let agents finish (no gate on run_one), then let verify drain.
                await asyncio.sleep(0)
                verify.release.set()

            await asyncio.gather(
                run_batch(
                    tasks, env=env, make_adapter=lambda s: _FakeAdapter(),
                    verify=verify, concurrency=5, verify_concurrency=1,
                    run_root=self.tmp, now=_StubClock(),
                ),
                releaser(),
            )

        self._drive(go())
        self.assertEqual(verify.peak, 1)  # Pool-B width 1 → never 2 grading at once
        self.assertEqual(len(verify.calls), 6)

    def test_verify_concurrency_two_allows_two_grading(self):
        env = _ConcurrencyProbeEnv(max_concurrency=5)
        verify = _VerifyProbe(gate=True)

        async def go():
            env.lock = asyncio.Lock()
            verify.lock = asyncio.Lock()
            verify.release = asyncio.Event()
            tasks = _make_tasks(6)

            async def releaser():
                for _ in range(2000):
                    if verify.peak >= 2:
                        break
                    await asyncio.sleep(0)
                verify.release.set()

            await asyncio.gather(
                run_batch(
                    tasks, env=env, make_adapter=lambda s: _FakeAdapter(),
                    verify=verify, concurrency=5, verify_concurrency=2,
                    run_root=self.tmp, now=_StubClock(),
                ),
                releaser(),
            )

        self._drive(go())
        self.assertEqual(verify.peak, 2)


# --------------------------------------------------------------------------
# (3) Phase transitions land in status.json + lifecycle calls
# --------------------------------------------------------------------------

class TestPhaseMachine(_BatchCase):
    def test_status_json_ends_done_with_pass_result(self):
        env = _ConcurrencyProbeEnv(max_concurrency=5)

        async def go():
            env.lock = asyncio.Lock()
            verify = _VerifyProbe(verdict="PASS")
            verify.lock = asyncio.Lock()
            tasks = _make_tasks(2)
            await run_batch(
                tasks, env=env, make_adapter=lambda s: _FakeAdapter(),
                verify=verify, concurrency=5, verify_concurrency=1,
                run_root=self.tmp, now=_StubClock(),
            )
            return tasks

        tasks = self._drive(go())
        for t in tasks:
            data = _read_status(self.tmp, t.run_id)
            self.assertEqual(data["phase"], "done")
            self.assertEqual(data["result"], "PASS")
            self.assertEqual(data["schema"], "craftbench.livestatus/v1")
            self.assertEqual(data["task_id"], t.task_id)

    def test_env_lifecycle_setup_precheck_teardown_called_once(self):
        env = _ConcurrencyProbeEnv(max_concurrency=5)

        async def go():
            env.lock = asyncio.Lock()
            verify = _VerifyProbe()
            verify.lock = asyncio.Lock()
            await run_batch(
                _make_tasks(3), env=env, make_adapter=lambda s: _FakeAdapter(),
                verify=verify, concurrency=5, verify_concurrency=1,
                run_root=self.tmp, now=_StubClock(),
            )

        self._drive(go())
        self.assertEqual(env.setup_calls, 1)
        self.assertEqual(env.precheck_calls, 1)
        self.assertEqual(env.teardown_calls, 1)

    def test_launching_phase_only_for_first_aura_task(self):
        # aura-* (env.max_concurrency==1): the FIRST task transits through
        # 'launching'; the events tape records it. claude-p never launches.
        env = _SequentialProbeEnv(max_concurrency=1)

        async def go():
            env.lock = asyncio.Lock()
            verify = _VerifyProbe()
            verify.lock = asyncio.Lock()
            tasks = [
                BatchTask(task_id=f"a{i}", run_id=f"rid-a{i}",
                          product="aura-mcp:claude-sonnet-4-6",
                          max_steps=40, timeout_s=600, payload={})
                for i in range(3)
            ]
            await run_batch(
                tasks, env=env, make_adapter=lambda s: _FakeAdapter(),
                verify=verify, concurrency=1, verify_concurrency=1,
                run_root=self.tmp, now=_StubClock(),
            )
            return tasks

        tasks = self._drive(go())

        def phases_in_events(run_id):
            p = self.tmp / run_id / "events.jsonl"
            out = []
            for line in p.read_text(encoding="utf-8").splitlines():
                rec = json.loads(line)
                if rec.get("type") == "phase":
                    out.append(rec["phase"])
            return out

        # First aura task: launching appears. Subsequent aura tasks: no launching.
        self.assertIn("launching", phases_in_events(tasks[0].run_id))
        self.assertNotIn("launching", phases_in_events(tasks[1].run_id))
        self.assertNotIn("launching", phases_in_events(tasks[2].run_id))


# --------------------------------------------------------------------------
# (4) result.json written atomically BEFORE phase flips to done
# --------------------------------------------------------------------------

class TestResultBeforeDone(_BatchCase):
    def test_result_json_exists_when_status_is_done(self):
        # Spec §5.2: any reader that sees phase==done can ALWAYS find result.json.
        # We assert ordering by making the verify gate, snapshotting the run dir
        # AT the moment phase==done is observed and confirming result.json is there.
        env = _ConcurrencyProbeEnv(max_concurrency=5)

        async def go():
            env.lock = asyncio.Lock()
            verify = _VerifyProbe(verdict="PASS")
            verify.lock = asyncio.Lock()
            tasks = _make_tasks(1)
            await run_batch(
                tasks, env=env, make_adapter=lambda s: _FakeAdapter(),
                verify=verify, concurrency=1, verify_concurrency=1,
                run_root=self.tmp, now=_StubClock(),
            )
            return tasks

        tasks = self._drive(go())
        t = tasks[0]
        run_dir = self.tmp / t.run_id
        status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["phase"], "done")
        # result.json present and complete (it was written BEFORE the flip).
        self.assertTrue((run_dir / "result.json").exists())
        result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["overall"], "PASS")
        # No leftover tmp partials anywhere in the run dir.
        names = [p.name for p in run_dir.iterdir()]
        self.assertFalse(any(".tmp" in n for n in names), names)

    def test_status_writer_records_result_before_done_in_event_order(self):
        # Tighter ordering proof: a recording sink factory captures the SEQUENCE
        # of (action) calls; result-write must precede the done status flip.
        env = _ConcurrencyProbeEnv(max_concurrency=5)
        order = []

        # Wrap write_result_json to record when it fires relative to status flips.
        import run_batch as rb

        orig_write_result = rb.write_result_json

        def spy_write_result(run_dir, obj):
            order.append(("result_json", Path(run_dir).name))
            return orig_write_result(run_dir, obj)

        async def go():
            env.lock = asyncio.Lock()
            verify = _VerifyProbe(verdict="FAIL")
            verify.lock = asyncio.Lock()
            tasks = _make_tasks(1)

            # Monkeypatch the module-level writer + a status spy via the sink seam.
            rb.write_result_json = spy_write_result

            real_make_sink = rb.FileEventSink

            class _SpySink(real_make_sink):
                def status(self, **fields):
                    if fields.get("phase") == "done":
                        order.append(("status_done", self.run_dir.name))
                    return super().status(**fields)

            try:
                await run_batch(
                    tasks, env=env, make_adapter=lambda s: _FakeAdapter(),
                    verify=verify, concurrency=1, verify_concurrency=1,
                    run_root=self.tmp, now=_StubClock(),
                    make_sink=lambda run_dir, now: _SpySink(run_dir, now=now),
                )
            finally:
                rb.write_result_json = orig_write_result
            return tasks

        self._drive(go())
        # The result_json write must come before the done status write.
        result_idx = next(i for i, e in enumerate(order) if e[0] == "result_json")
        done_idx = next(i for i, e in enumerate(order) if e[0] == "status_done")
        self.assertLess(result_idx, done_idx)


# --------------------------------------------------------------------------
# (5) A failing/timing-out task is isolated; others still complete
# --------------------------------------------------------------------------

class TestFailureIsolation(_BatchCase):
    def test_one_failing_task_does_not_abort_others(self):
        env = _ConcurrencyProbeEnv(max_concurrency=5, fail_ids={"t2"})

        async def go():
            env.lock = asyncio.Lock()
            verify = _VerifyProbe(verdict="PASS")
            verify.lock = asyncio.Lock()
            tasks = _make_tasks(5)
            await run_batch(
                tasks, env=env, make_adapter=lambda s: _FakeAdapter(),
                verify=verify, concurrency=5, verify_concurrency=1,
                run_root=self.tmp, now=_StubClock(),
            )
            return tasks

        tasks = self._drive(go())
        # The failing task ends in 'error'; everyone else reaches 'done'.
        failed = _read_status(self.tmp, "20260604-000000-t2-claude-p")
        self.assertEqual(failed["phase"], "error")
        self.assertIsNotNone(failed["error"])
        for tid in ("t0", "t1", "t3", "t4"):
            data = _read_status(self.tmp, f"20260604-000000-{tid}-claude-p")
            self.assertEqual(data["phase"], "done")
            self.assertEqual(data["result"], "PASS")
        # The failing task still gets a result.json (harness result, §11).
        self.assertTrue((self.tmp / "20260604-000000-t2-claude-p" / "result.json").exists())

    def test_timeout_task_lands_timeout_phase_and_isolates(self):
        env = _ConcurrencyProbeEnv(max_concurrency=5, timeout_ids={"t1"})

        async def go():
            env.lock = asyncio.Lock()
            verify = _VerifyProbe(verdict="PASS")
            verify.lock = asyncio.Lock()
            tasks = _make_tasks(3)
            await run_batch(
                tasks, env=env, make_adapter=lambda s: _FakeAdapter(),
                verify=verify, concurrency=5, verify_concurrency=1,
                run_root=self.tmp, now=_StubClock(),
            )

        self._drive(go())
        timed = _read_status(self.tmp, "20260604-000000-t1-claude-p")
        self.assertEqual(timed["phase"], "timeout")
        for tid in ("t0", "t2"):
            data = _read_status(self.tmp, f"20260604-000000-{tid}-claude-p")
            self.assertEqual(data["phase"], "done")


# --------------------------------------------------------------------------
# (5b) A harness exception is NOT charged to the model
# --------------------------------------------------------------------------

class TestErrorPhaseIsNotGraded(_BatchCase):
    """The error phase must leave the graded denominator.

    ``_terminal_failure``'s only caller is the bare ``except Exception`` in
    ``_run_one``, whose try block spans BOTH adapter dispatch and the grading
    call. So a dead editor, a full disk, or a bug in the verify callable all
    land here. Writing ``FAIL`` charged every one of them to the model under
    test, because ``FAIL`` is in ``GRADED_VERDICTS`` — the allowlist was
    correct and still produced the wrong number, since the writer laundered the
    fault before any consumer saw it.
    """

    def test_error_phase_writes_a_non_graded_verdict(self):
        from adapters.base import GRADED_VERDICTS, is_graded_verdict

        env = _ConcurrencyProbeEnv(max_concurrency=5, fail_ids={"t2"})

        async def go():
            env.lock = asyncio.Lock()
            verify = _VerifyProbe(verdict="PASS")
            verify.lock = asyncio.Lock()
            await run_batch(
                _make_tasks(3), env=env, make_adapter=lambda s: _FakeAdapter(),
                verify=verify, concurrency=5, verify_concurrency=1,
                run_root=self.tmp, now=_StubClock(),
            )

        self._drive(go())
        run_id = "20260604-000000-t2-claude-p"
        self.assertEqual(_read_status(self.tmp, run_id)["phase"], "error")

        result = json.loads((self.tmp / run_id / "result.json").read_text(encoding="utf-8"))
        overall = result["overall"]
        self.assertNotIn(overall, GRADED_VERDICTS)
        self.assertFalse(is_graded_verdict(overall))
        # Specifically NOT the old value, which is the whole point.
        self.assertNotEqual(overall, "FAIL")
        self.assertEqual(overall, "HARNESS-ERROR")

    def test_error_verdict_is_excluded_from_the_pass_rate(self):
        """It must land in ``excluded``, never in ``n_fail``."""
        from run_batch import summarize_verdicts

        summary = summarize_verdicts(["PASS", "PASS", "HARNESS-ERROR"])
        self.assertEqual(summary["n_total"], 3)
        self.assertEqual(summary["n_graded"], 2)
        self.assertEqual(summary["n_pass"], 2)
        self.assertEqual(summary["n_fail"], 0)
        self.assertEqual(summary["pass_rate"], 1.0)
        self.assertEqual(summary["n_excluded"], 1)
        self.assertEqual(summary["excluded_by_verdict"]["HARNESS-ERROR"], 1)

    def test_timeout_stays_non_graded_too(self):
        """The timeout branch was already correct; pin it so it stays that way."""
        from adapters.base import is_graded_verdict

        self.assertFalse(is_graded_verdict("TIMEOUT"))


# --------------------------------------------------------------------------
# (6) Cancellation stops new task starts
# --------------------------------------------------------------------------

class TestCancellation(_BatchCase):
    def test_cancellation_stops_new_starts(self):
        # With max_concurrency=1 (sequential), cancelling after the first task
        # starts must prevent the remaining tasks from ever acquiring Pool A.
        env = _ConcurrencyProbeEnv(max_concurrency=1)
        cancel = Cancellation()
        started = []

        class _CancelOnFirstEnv(_ConcurrencyProbeEnv):
            async def run_one(self, task, adapter, events):
                started.append(task.task_id)
                # Trip cancellation the moment the first task acts.
                cancel.cancel()
                async with self.lock:
                    self.active += 1
                    self.peak = max(self.peak, self.active)
                try:
                    await asyncio.sleep(0)
                    return _FakeResult()
                finally:
                    async with self.lock:
                        self.active -= 1

        env = _CancelOnFirstEnv(max_concurrency=1)

        async def go():
            env.lock = asyncio.Lock()
            verify = _VerifyProbe()
            verify.lock = asyncio.Lock()
            tasks = _make_tasks(5)
            await run_batch(
                tasks, env=env, make_adapter=lambda s: _FakeAdapter(),
                verify=verify, concurrency=1, verify_concurrency=1,
                run_root=self.tmp, now=_StubClock(), cancellation=cancel,
            )
            return tasks

        tasks = self._drive(go())
        # Only the first task ever started acting; the rest were cancelled before start.
        self.assertEqual(started, ["t0"])
        # The un-started tasks end in 'cancelled' phase.
        for tid in ("t1", "t2", "t3", "t4"):
            data = _read_status(self.tmp, f"20260604-000000-{tid}-claude-p")
            self.assertEqual(data["phase"], "cancelled")
        # Teardown still ran (env world torn down on cancel).
        self.assertEqual(env.teardown_calls, 1)


if __name__ == "__main__":
    unittest.main()
