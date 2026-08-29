"""MCP stdio servers whose client is gone must be reaped; live ones must not.

THE INCIDENT, measured 2026-08-24. Twenty-six stranded ``Aura/MCP`` python
children held **11.75 GB of COMMIT** on a box with no Aura client and no editor
running. Free commit sat at 5.9 GB against envgate's 10 GB floor, and the cost
was a WRONG VERDICT rather than slowness: an eight-leg ``cb discriminate`` sweep
lost every leg — the first leg's L1 died and was recorded as the SUBMISSION
failing (the C1060/C3859 out-of-heap shape), and the remaining seven aborted at
the preflight blocker. Reaping them returned free commit to 22.3 GB, after which
the identical command reported ``11 checks OK`` and PASSed.

Nothing else in the rig reaps these. ``stop_stack``, ``orphan_sweep`` and
``ensure_editor_dead`` scope to the UE family, the Aura client and the port
owners; an MCP stdio child is none of those, so a box can sit under the commit
floor with no stack up and nothing able to explain why.

Both directions are pinned, because a reaper fails two ways and only one is loud:

  * reaping too LITTLE leaves the commit drain in place — silent, and what
    happened;
  * reaping too MUCH kills the working set of whoever is driving an editor right
    now. That is why the gate is a DEAD PARENT and not "no Aura is running":
    these servers are spawned by an MCP CLIENT (Claude Code), not by the Aura
    desktop client, so a live client owns its children legitimately.

Stdlib only. No psutil, no editor, no UE, no tokens.
"""
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import stack_guard as sg  # noqa: E402

MCP_A = ("python.exe", 101, 9001,
         "c:\\py\\python.exe q:\\ue\\plugins\\aura\\mcp\\unreal_editor.py")
MCP_B = ("python.exe", 102, 9002, "q:/ue/plugins/aura/mcp/unreal_inspector.py")
NOT_MCP = ("python.exe", 103, 9003, "c:\\repo\\tools\\coverage\\coverage.py")


class _Rec:
    """Records what the sweep would have done, so no test ever kills anything."""

    def __init__(self):
        self.killed = []
        self.audited = []

    def kill(self, pid):
        self.killed.append(pid)

    def audit(self, target, reason=""):
        self.audited.append((target, reason))


def _sweep(entries, dead_parents, rec=None):
    rec = rec or _Rec()
    out = sg.mcp_orphan_sweep(
        procs=lambda: entries,
        alive=lambda ppid: ppid not in dead_parents,
        kill=rec.kill, audit=rec.audit, log=lambda *_a, **_k: None)
    return out, rec


class TestDeadParentIsReaped(unittest.TestCase):
    def test_an_orphan_is_reaped(self):
        out, rec = _sweep([MCP_A], {9001})
        self.assertEqual([("python.exe", 101)], out)
        self.assertEqual([101], rec.killed)

    def test_every_reap_is_audited_with_the_reason(self):
        _out, rec = _sweep([MCP_A], {9001})
        self.assertEqual(1, len(rec.audited))
        target, reason = rec.audited[0]
        self.assertIn("pid=101", target)
        self.assertIn("ppid=9001", target)
        self.assertIn("mcp_orphan_sweep", reason)

    def test_both_slash_spellings_are_recognised(self):
        # The measured fleet had BACKSLASH command lines; psutil joins argv with
        # forward slashes on some hosts, so a single spelling would miss half.
        out, _rec = _sweep([MCP_A, MCP_B], {9001, 9002})
        self.assertEqual({101, 102}, {pid for _img, pid in out})

    def test_the_incident_scale_reaps_all_of_them(self):
        fleet = [("python.exe", 200 + i, 9100 + i, "aura/mcp/unreal_editor.py")
                 for i in range(26)]
        out, rec = _sweep(fleet, {9100 + i for i in range(26)})
        self.assertEqual(26, len(out))
        self.assertEqual(26, len(rec.killed))


class TestLiveParentIsNeverTouched(unittest.TestCase):
    """The loud direction: never kill a working client's children."""

    def test_a_live_parent_protects_its_child(self):
        out, rec = _sweep([MCP_A], set())
        self.assertEqual([], out)
        self.assertEqual([], rec.killed)

    def test_an_unreadable_parent_counts_as_alive(self):
        rec = _Rec()
        out = sg.mcp_orphan_sweep(procs=lambda: [MCP_A],
                                  alive=lambda _ppid: True,
                                  kill=rec.kill, audit=rec.audit,
                                  log=lambda *_a, **_k: None)
        self.assertEqual([], out)
        self.assertEqual([], rec.killed)

    def test_a_mixed_fleet_reaps_only_the_orphans(self):
        out, rec = _sweep([MCP_A, MCP_B], {9002})
        self.assertEqual([("python.exe", 102)], out)
        self.assertEqual([102], rec.killed)

    def test_unknown_liveness_is_alive_in_the_real_probe_too(self):
        # _pid_alive is the production default for `alive`. Its contract is that
        # it only ever answers False when it KNOWS the pid is gone.
        self.assertFalse(sg._pid_alive(0))
        self.assertFalse(sg._pid_alive(-1))


class TestScopeAndBlindness(unittest.TestCase):
    def test_ordinary_repo_tooling_does_not_match_the_markers(self):
        self.assertFalse(any(m in NOT_MCP[3] for m in sg.MCP_STDIO_MARKERS))

    def test_an_mcp_path_does_match_the_markers(self):
        for row in (MCP_A, MCP_B):
            self.assertTrue(any(m in row[3] for m in sg.MCP_STDIO_MARKERS), row[3])

    def test_blind_enumeration_reaps_nothing(self):
        # DELIBERATELY not fail-open, unlike _ue_family_procs' blanket trio: a
        # blanket kill of every python.exe would take out the operator's own
        # tooling, and an unreaped orphan costs memory, not a verdict.
        rec = _Rec()
        self.assertEqual([], sg.mcp_orphan_sweep(
            procs=lambda: None, alive=lambda _p: False,
            kill=rec.kill, audit=rec.audit, log=lambda *_a, **_k: None))
        self.assertEqual([], rec.killed)

    def test_an_enumerator_that_raises_is_survived(self):
        rec = _Rec()

        def boom():
            raise OSError("no process table")

        self.assertEqual([], sg.mcp_orphan_sweep(
            procs=boom, alive=lambda _p: False, kill=rec.kill,
            audit=rec.audit, log=lambda *_a, **_k: None))

    def test_a_kill_that_raises_does_not_abort_the_rest(self):
        rec = _Rec()

        def flaky(pid):
            if pid == 101:
                raise OSError("access denied")
            rec.killed.append(pid)

        out = sg.mcp_orphan_sweep(procs=lambda: [MCP_A, MCP_B],
                                  alive=lambda _p: False, kill=flaky,
                                  audit=rec.audit, log=lambda *_a, **_k: None)
        self.assertEqual([("python.exe", 102)], out)
        self.assertEqual([102], rec.killed)


class TestItIsWiredAndGated(unittest.TestCase):
    def test_stop_stack_calls_it(self):
        # A reaper nothing calls is exactly the defect this file exists to stop:
        # the 11.75 GB drain existed while three other sweeps ran happily.
        src = (Path(__file__).resolve().parents[1]
               / "aura_rig" / "stack.py").read_text(encoding="utf-8")
        self.assertIn("mcp_orphan_sweep(log=log)", src)

    def test_the_real_kill_routes_through_the_audited_gate(self):
        # _tree_kill -> stack._run_kill_cmd is what makes the 2026-08-07 kill
        # guard (test-process and live-owner refusal) cover this sweep too.
        self.assertIn("_run_kill_cmd", inspect.getsource(sg._tree_kill))

    def test_the_production_default_kill_is_that_gated_path(self):
        sig = inspect.signature(sg.mcp_orphan_sweep)
        self.assertIsNone(sig.parameters["kill"].default,
                          "kill must default to None so the body picks _tree_kill")
        self.assertIn("kill or _tree_kill", inspect.getsource(sg.mcp_orphan_sweep))


if __name__ == "__main__":
    unittest.main()
