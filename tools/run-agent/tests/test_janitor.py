"""Unit tests for aura_rig.janitor — the detached stack watchdog's decision
logic and poll loop, fully offline (decide is pure; run_loop takes every
effect injected — no process is spawned, polled, or killed here).
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import janitor  # noqa: E402


def _m(**over):
    base = {"schema": 1, "generation": "g1", "created_at": 1000.0,
            "last_activity": 1000.0, "owner_pid": 42, "owner_created": 999.0,
            "owner_kind": "cb", "no_teardown": False}
    base.update(over)
    return base


class TestDecide(unittest.TestCase):
    def test_no_manifest_exits(self):
        self.assertEqual(
            janitor.decide(None, owner_alive=False, now=0, idle_limit_h=None),
            "exit")
        self.assertEqual(
            janitor.decide({}, owner_alive=False, now=0, idle_limit_h=None),
            "exit")

    def test_dead_owner_is_torn_down(self):
        self.assertEqual(
            janitor.decide(_m(), owner_alive=False, now=2000.0,
                           idle_limit_h=None),
            "teardown-orphan")

    def test_no_teardown_flag_never_protects_a_dead_owner(self):
        # THE scenario-4 semantics: --no-teardown means 'keep the stack
        # between MY runs', not 'keep it after I'm gone'.
        self.assertEqual(
            janitor.decide(_m(no_teardown=True), owner_alive=False,
                           now=2000.0, idle_limit_h=None),
            "teardown-orphan")

    def test_live_owner_waits(self):
        self.assertEqual(
            janitor.decide(_m(), owner_alive=True, now=2000.0,
                           idle_limit_h=None),
            "wait")

    def test_dead_owner_pending_bringup_is_torn_down_like_any_orphan(self):
        # The manifest is armed at bring-up START since 2026-08-07, so a
        # bring-up interrupted mid-flight leaves state='pending' with a dead
        # owner — half a stack running, exactly as leaky as a green one. The
        # decision is state-BLIND on purpose: same verdict, no special case.
        self.assertEqual(
            janitor.decide(_m(state="pending"), owner_alive=False,
                           now=2000.0, idle_limit_h=None),
            "teardown-orphan")

    def test_live_owner_pending_bringup_waits(self):
        # ...and a bring-up IN FLIGHT is never reaped out from under itself.
        self.assertEqual(
            janitor.decide(_m(state="pending"), owner_alive=True,
                           now=2000.0, idle_limit_h=None),
            "wait")

    def test_arm_is_a_noop_in_a_test_process(self):
        # Spawning a detached watchdog that can stop_stack the operator's box
        # is never something a unit test should do (incident 2026-08-07).
        self.assertFalse(janitor.arm(log=lambda *a: None))

    def test_live_owner_never_torn_down_without_idle_limit(self):
        # Even a WEEK-stale stack waits when the idle limit is unset (the
        # conservative default) — the janitor is a dead-man's switch, not a
        # policy engine.
        self.assertEqual(
            janitor.decide(_m(last_activity=0.0, created_at=0.0),
                           owner_alive=True, now=7 * 86400.0,
                           idle_limit_h=None),
            "wait")

    def test_idle_limit_tears_down_an_idle_live_stack(self):
        self.assertEqual(
            janitor.decide(_m(last_activity=1000.0), owner_alive=True,
                           now=1000.0 + 13 * 3600.0, idle_limit_h=12.0),
            "teardown-idle")

    def test_idle_limit_not_exceeded_waits(self):
        self.assertEqual(
            janitor.decide(_m(last_activity=1000.0), owner_alive=True,
                           now=1000.0 + 11 * 3600.0, idle_limit_h=12.0),
            "wait")

    def test_idle_clock_prefers_last_activity(self):
        # Old created_at + fresh last_activity = an ACTIVE stack.
        m = _m(created_at=0.0, last_activity=90000.0)
        self.assertEqual(
            janitor.decide(m, owner_alive=True, now=90000.0 + 3600.0,
                           idle_limit_h=12.0),
            "wait")

    def test_garbage_activity_never_becomes_a_verdict(self):
        m = _m(last_activity="soon", created_at=None)
        self.assertEqual(
            janitor.decide(m, owner_alive=True, now=1e9, idle_limit_h=1.0),
            "wait")


class TestIdleLimitParsing(unittest.TestCase):
    def test_unset_is_off(self):
        self.assertIsNone(janitor.idle_limit_hours(env={}))
        self.assertIsNone(
            janitor.idle_limit_hours(env={"CB_STACK_IDLE_TEARDOWN_HOURS": ""}))

    def test_number_parses(self):
        self.assertEqual(
            janitor.idle_limit_hours(env={"CB_STACK_IDLE_TEARDOWN_HOURS": "12"}),
            12.0)
        self.assertEqual(
            janitor.idle_limit_hours(
                env={"CB_STACK_IDLE_TEARDOWN_HOURS": "1.5 # overnight"}),
            1.5)

    def test_garbage_and_nonpositive_read_as_off(self):
        for raw in ("soon", "0", "-3"):
            self.assertIsNone(
                janitor.idle_limit_hours(
                    env={"CB_STACK_IDLE_TEARDOWN_HOURS": raw}), raw)


class _LoopRig:
    def __init__(self, manifests, alive=True):
        self._seq = list(manifests)
        self.alive = alive
        self.teardowns = []
        self.logs = []
        self.sleeps = []

    def read(self):
        return self._seq.pop(0) if self._seq else None

    def run(self, **kw):
        kw.setdefault("idle_limit", lambda: None)
        return janitor.run_loop(
            read=self.read,
            owner_alive_of=(self.alive if callable(self.alive)
                            else lambda m: self.alive),
            teardown=lambda action, m: self.teardowns.append((action, m)),
            interval_s=0.0, sleep=self.sleeps.append, clock=lambda: 1e6,
            log=self.logs.append, **kw)


class TestRunLoop(unittest.TestCase):
    def test_dead_owner_triggers_one_teardown_then_exit(self):
        rig = _LoopRig([_m()], alive=False)
        self.assertEqual(rig.run(), "teardown-orphan")
        self.assertEqual(len(rig.teardowns), 1)
        self.assertEqual(rig.teardowns[0][0], "teardown-orphan")

    def test_manifest_gone_exits_without_teardown(self):
        rig = _LoopRig([None])
        self.assertEqual(rig.run(), "exit")
        self.assertEqual(rig.teardowns, [])

    def test_live_owner_keeps_waiting(self):
        rig = _LoopRig([_m(), _m(), _m()], alive=True)
        self.assertEqual(rig.run(max_ticks=3), "wait")
        self.assertEqual(rig.teardowns, [])
        self.assertEqual(len(rig.sleeps), 2, "sleeps BETWEEN ticks only")

    def test_new_generation_is_served_without_restart(self):
        # gen1 alive, gen2 alive (a re-arm replaced the manifest), then a
        # teardown elsewhere removed it -> exit. One janitor, three states.
        rig = _LoopRig([_m(generation="g1"), _m(generation="g2"), None],
                       alive=True)
        self.assertEqual(rig.run(), "exit")
        self.assertEqual(rig.teardowns, [])

    def test_unknown_liveness_never_tears_down(self):
        def boom(m):
            raise RuntimeError("cannot probe")

        rig = _LoopRig([_m(), _m()], alive=boom)
        self.assertEqual(rig.run(max_ticks=2), "wait")
        self.assertEqual(rig.teardowns, [],
                         "a liveness glitch must NEVER kill a live stack")

    def test_teardown_error_still_terminates_the_loop(self):
        rig = _LoopRig([_m()], alive=False)

        def bad_teardown(action, m):
            rig.teardowns.append((action, m))
            raise OSError("kill failed")

        got = janitor.run_loop(
            read=rig.read, owner_alive_of=lambda m: False,
            teardown=bad_teardown, idle_limit=lambda: None,
            interval_s=0.0, sleep=rig.sleeps.append, clock=lambda: 1e6,
            log=rig.logs.append)
        self.assertEqual(got, "teardown-orphan")
        self.assertIn("backstop", "\n".join(rig.logs))

    def test_idle_teardown_via_injected_limit(self):
        rig = _LoopRig([_m(last_activity=0.0)], alive=True)
        got = rig.run(idle_limit=lambda: 1.0)
        self.assertEqual(got, "teardown-idle")
        self.assertEqual(rig.teardowns[0][0], "teardown-idle")

    def test_declined_teardown_keeps_watching_the_new_generation(self):
        # The stale-decision race: a bring-up replaced the manifest between the
        # poll's read and the kill. The teardown DECLINES (returns False) and
        # the loop must keep serving the NEW generation instead of exiting —
        # the new arm saw our lock held and exited, so we are its watchdog.
        calls = []

        def decline_once(action, m):
            calls.append(action)
            return False if len(calls) == 1 else True

        reads = iter([_m(generation="g1"),               # dead owner -> decide teardown
                      _m(generation="g2", owner_pid=1),  # new gen, dead again
                      ])
        alive_seq = iter([False, False])
        logs = []
        got = janitor.run_loop(
            read=lambda: next(reads),
            owner_alive_of=lambda m: next(alive_seq),
            teardown=decline_once, idle_limit=lambda: None,
            interval_s=0.0, sleep=lambda s: None, clock=lambda: 1e6,
            log=logs.append)
        self.assertEqual(got, "teardown-orphan")
        self.assertEqual(calls, ["teardown-orphan", "teardown-orphan"],
                         "declined once, executed on the NEXT generation")
        self.assertIn("superseded", "\n".join(logs))


if __name__ == "__main__":
    unittest.main()
