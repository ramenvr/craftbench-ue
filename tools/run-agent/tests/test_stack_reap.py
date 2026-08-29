"""Unit tests for stack.ensure_editor_dead — the zombie-editor verify/reap.

Fully offline: procs()/kill/sweep/foreign_check/sleep/clock are all INJECTED, so
nothing here lists real processes, kills anything, or sleeps. The behaviours
under test are the 2026-07-24 zombie-overlap heal: exact-PID and scoped-set
verification, escalation to the scoped tree-kill, the gated LiveCodingConsole/
CrashReportClient sweep, foreign-editor safety, the CB_NO_EDITOR_REAP escape
hatch, and never-raises.
"""

import os
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import stack  # noqa: E402

CB = r"c:/u/x/appdata/local/craftbench/scratch/craftbenchscratch/craftbenchtemplate.uproject -renderoffscreen"
FOREIGN = r"c:/u/x/github/unrealfeaturedev/unrealfeaturedev.uproject -game"


def _proc_seq(*snapshots):
    """A zero-arg procs() yielding each snapshot once, then the last forever."""
    state = {"i": 0}

    def procs():
        i = min(state["i"], len(snapshots) - 1)
        state["i"] += 1
        return list(snapshots[i])

    return procs


def _clock(step=1.0):
    state = {"t": -step}

    def now():
        state["t"] += step
        return state["t"]

    return now


class _Rig:
    """Recorder harness around ensure_editor_dead with inert defaults."""

    def __init__(self, procs, foreign=None):
        self.procs = procs
        self.killed = []
        self.swept = []
        self.logs = []
        self.foreign = foreign

    def kill(self, log=None):
        self.killed.append(1)

    def sweep(self):
        self.swept.append(1)

    def run(self, old_pids=None, **kw):
        return stack.ensure_editor_dead(
            old_pids,
            procs=self.procs, kill_scoped=self.kill, sweep=self.sweep,
            foreign_check=lambda: self.foreign,
            sleep=lambda s: None, clock=_clock(),
            log=self.logs.append, **kw)


class TestEnsureEditorDead(unittest.TestCase):
    def test_old_pid_dies_within_grace_no_kill(self):
        rig = _Rig(_proc_seq([(101, CB)], [(101, CB)], []))
        self.assertTrue(rig.run([101]))
        self.assertEqual(rig.killed, [])
        self.assertEqual(rig.swept, [])

    def test_survivor_escalates_scoped_kill_then_dies(self):
        # Alive through the whole grace window; gone right after the kill.
        alive, dead = [(101, CB)], []
        snapshots = [alive] * 30 + [dead]

        state = {"i": 0, "post_kill": False}

        def procs():
            if state["post_kill"]:
                return []
            i = min(state["i"], len(snapshots) - 1)
            state["i"] += 1
            return list(snapshots[i])

        rig = _Rig(procs)
        real_kill = rig.kill

        def kill(log=None):
            real_kill(log)
            state["post_kill"] = True

        rig.kill = kill
        self.assertTrue(rig.run([101], grace_s=3.0, kill_wait_s=3.0))
        self.assertEqual(rig.killed, [1])
        self.assertEqual(rig.swept, [1])          # post-force-kill sweep fired
        self.assertTrue(any("force-killing" in ln for ln in rig.logs))

    def test_timeout_warns_false_never_raises(self):
        rig = _Rig(_proc_seq([(101, CB)]))       # alive forever

        def kill_raises(log=None):
            rig.killed.append(1)
            raise RuntimeError("taskkill exploded")

        rig.kill = kill_raises
        ok = rig.run([101], grace_s=2.0, kill_wait_s=2.0, sweep_wait_s=1.0)
        self.assertFalse(ok)
        self.assertTrue(any("survived" in ln for ln in rig.logs))

    def test_foreign_pid_never_polled_or_killed_exact_mode(self):
        # Old pid 101 dies; foreign 202 stays alive throughout — must not matter.
        rig = _Rig(_proc_seq([(101, CB), (202, FOREIGN)], [(202, FOREIGN)]))
        self.assertTrue(rig.run([101]))
        self.assertEqual(rig.killed, [])

    def test_scoped_set_mode_ignores_foreign_only(self):
        rig = _Rig(_proc_seq([(202, FOREIGN)]))
        self.assertTrue(rig.run(None))            # foreign-only = nothing to reap
        self.assertEqual(rig.killed, [])
        self.assertEqual(rig.swept, [])

    def test_scoped_set_mode_drains_cb_editor_via_kill(self):
        state = {"post_kill": False}

        def procs():
            return [] if state["post_kill"] else [(101, CB), (202, FOREIGN)]

        rig = _Rig(procs)
        real_kill = rig.kill

        def kill(log=None):
            real_kill(log)
            state["post_kill"] = True

        rig.kill = kill
        self.assertTrue(rig.run(None, grace_s=2.0, kill_wait_s=3.0))
        self.assertEqual(rig.killed, [1])

    def test_default_sweep_targets_livecoding_and_crashreporter(self):
        # Use the DEFAULT sweep (no injection) with kill_by_image recorded.
        o_kbi, o_procs = stack.kill_by_image, stack._editor_procs
        recorded = []
        try:
            stack.kill_by_image = lambda *names: recorded.append(names)
            stack._editor_procs = lambda: []
            ok = stack.ensure_editor_dead(
                None, always_sweep=True,
                foreign_check=lambda: None,
                sleep=lambda s: None, clock=_clock(), log=lambda s: None)
        finally:
            stack.kill_by_image, stack._editor_procs = o_kbi, o_procs
        self.assertTrue(ok)
        self.assertIn(("LiveCodingConsole", "CrashReportClient"), recorded)

    def test_sweep_skipped_when_foreign_editor_present(self):
        rig = _Rig(_proc_seq([]), foreign=(202, FOREIGN))
        self.assertTrue(rig.run(None, always_sweep=True))
        self.assertEqual(rig.swept, [])
        self.assertTrue(any("sweep SKIPPED" in ln for ln in rig.logs))

    def test_always_sweep_after_graceful_death(self):
        rig = _Rig(_proc_seq([(101, CB)], []))
        self.assertTrue(rig.run([101], always_sweep=True))
        self.assertEqual(rig.killed, [])
        self.assertEqual(rig.swept, [1])          # per-rep LiveCodingConsole reap

    def test_escape_hatch_skips_everything(self):
        calls = []

        def procs():
            calls.append(1)
            return [(101, CB)]

        rig = _Rig(procs)
        old = os.environ.get("CB_NO_EDITOR_REAP")
        try:
            os.environ["CB_NO_EDITOR_REAP"] = "1"
            self.assertTrue(rig.run([101]))
        finally:
            if old is None:
                os.environ.pop("CB_NO_EDITOR_REAP", None)
            else:
                os.environ["CB_NO_EDITOR_REAP"] = old
        self.assertEqual(calls, [])
        self.assertEqual(rig.killed, [])
        self.assertTrue(any("SKIPPED" in ln for ln in rig.logs))


class TestTreeKillAndEnumeration(unittest.TestCase):
    def test_windows_kill_is_tree_kill(self):
        # /T must be present so the zombie's LiveCodingConsole + aura_server
        # python child die with it (a bare /PID kill orphans them).
        o_procs, o_run, o_win = stack._editor_procs, stack.subprocess.run, stack.IS_WINDOWS
        cmds = []

        def fake_run(cmd, **kw):
            cmds.append(list(cmd))
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")

        try:
            stack.IS_WINDOWS = True
            stack._editor_procs = lambda: [(101, CB)]
            stack.subprocess.run = fake_run
            stack.kill_craftbench_editors(log=lambda *a: None)
        finally:
            stack._editor_procs, stack.subprocess.run, stack.IS_WINDOWS = o_procs, o_run, o_win
        kill_cmds = [c for c in cmds if "/PID" in c]
        self.assertEqual(len(kill_cmds), 1)
        self.assertIn("/T", kill_cmds[0])
        self.assertIn("101", kill_cmds[0])

    def test_parse_pid_cmdline_lines(self):
        out = ("12345|C:\\UE\\UnrealEditor.exe C:\\cb\\scratch\\X.uproject\n"
               "junk line without a pipe\n"
               "notanumber|whatever\n"
               "  678|Editor -flag  \n")
        procs = stack._parse_pid_cmdline_lines(out)
        self.assertEqual(procs, [(12345, "c:\\ue\\unrealeditor.exe c:\\cb\\scratch\\x.uproject"),
                                 (678, "editor -flag")])


if __name__ == "__main__":
    unittest.main()
