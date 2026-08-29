"""Unit tests for aura_rig.kill_guard + its seam inside aura_rig.stack.

THE INCIDENT (2026-08-07). A unit-test run reached the real kill primitives and
taskkill'd a LIVE aura-product drive editor plus the :3000/:3002/:9222 owners;
``runs/.kill-audit.log`` holds mock pids 101/303 interleaved with real
``image=UnrealEditor reason=kill_by_image`` lines from one pid. The drive died
"EDITOR GONE" with no crash dump because it was KILLED.

The decisive property under test here is NEGATIVE and structural: from a test
process, the REAL kill boundary is never reached. Everything is offline — no
process is enumerated, signalled or shelled, and the audit path is redirected
into a tempdir so these tests never append to the machine's real kill log.
"""

import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import kill_guard as kg  # noqa: E402
from aura_rig import stack  # noqa: E402
from aura_rig import stack_guard as sg  # noqa: E402


# --------------------------------------------------------------------------- #
# 1. Detection (pure, over injected facts).                                    #
# --------------------------------------------------------------------------- #

class TestTestProcessDetection(unittest.TestCase):
    def test_this_process_is_detected(self):
        # The load-bearing base case: we ARE unittest.
        self.assertTrue(kg.in_test_process())

    def test_modules_signal(self):
        self.assertTrue(kg.in_test_process(modules={"unittest": 1},
                                           argv=["cb"], env={}))
        self.assertTrue(kg.in_test_process(modules={"pytest": 1},
                                           argv=["cb"], env={}))
        self.assertTrue(kg.in_test_process(modules={"_pytest": 1},
                                           argv=["cb"], env={}))

    def test_argv_signal(self):
        # `-m unittest` rewrites argv[0] to .../unittest/__main__.py
        self.assertTrue(kg.in_test_process(
            modules={}, argv=[r"C:\Py\Lib\unittest\__main__.py", "discover"],
            env={}))
        self.assertTrue(kg.in_test_process(
            modules={}, argv=["/usr/bin/pytest", "-q"], env={}))
        self.assertTrue(kg.in_test_process(
            modules={}, argv=["python", "-m", "pytest"], env={}))

    def test_env_signal(self):
        self.assertTrue(kg.in_test_process(modules={}, argv=["cb"],
                                           env={"CB_IN_TEST": "1"}))
        self.assertFalse(kg.in_test_process(modules={}, argv=["cb"],
                                            env={"CB_IN_TEST": "0"}))

    def test_a_real_cb_is_not_a_test(self):
        self.assertFalse(kg.in_test_process(
            modules={"json": 1, "aura_rig.stack": 1},
            argv=[r"C:\Py\Scripts\cb.exe", "bench", "--task", "t0"], env={}))

    def test_unknowable_modules_read_as_test(self):
        # Fail-SAFE: when the probe cannot answer, the answer is "test".
        class Hostile:
            def __contains__(self, item):
                raise RuntimeError("no")
        self.assertTrue(kg.in_test_process(modules=Hostile(), argv=[], env={}))

    def test_a_real_cb_import_graph_imports_no_test_runner(self):
        # The whole `unittest in sys.modules` signal rests on this: no
        # production module under tools/run-agent may import a test runner, or
        # every real teardown would refuse itself.
        out = subprocess.run(
            [sys.executable, "-c",
             "import sys; from aura_rig import cb, stack, stack_guard, janitor;"
             " print(int(any(m in sys.modules for m in "
             "('unittest', 'pytest', '_pytest'))))"],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True, text=True, timeout=120)
        self.assertEqual(out.stdout.strip().splitlines()[-1], "0",
                         "a production import graph must not pull in a test "
                         f"runner (stderr: {out.stderr[-400:]})")


class TestActingRole(unittest.TestCase):
    """The audit line's `role=` field — cheap, and it would have made the
    2026-08-07 diagnosis instant."""

    def test_test_role_wins(self):
        self.assertEqual(kg.acting_role(modules={"unittest": 1},
                                        argv=[r"C:\Py\Scripts\cb.exe"], env={}),
                         "test")

    def test_this_process_reports_test(self):
        self.assertEqual(kg.acting_role(), "test")

    def test_janitor(self):
        self.assertEqual(kg.acting_role(
            modules={}, argv=["python", "-m", "aura_rig.janitor", "--respawned"],
            env={}), "janitor")

    def test_cb(self):
        self.assertEqual(kg.acting_role(
            modules={}, argv=[r"C:\Py\Scripts\cb.exe", "down"], env={}), "cb")
        self.assertEqual(kg.acting_role(
            modules={}, argv=["python", "-m", "aura_rig.cb", "up"], env={}), "cb")

    def test_other(self):
        self.assertEqual(kg.acting_role(modules={}, argv=["/bin/whatever"],
                                        env={}), "other")

    def test_explicit_env_override(self):
        self.assertEqual(kg.acting_role(modules={}, argv=["x"],
                                        env={"CB_PROC_ROLE": "bench"}), "bench")


# --------------------------------------------------------------------------- #
# 2. Live-owner resolution + the pure decision.                                #
# --------------------------------------------------------------------------- #

def _owner(pid=4242, created=999.0):
    return {"owner_pid": pid, "owner_created": created}


class TestLiveForeignOwner(unittest.TestCase):
    def test_alive_and_unrelated_is_foreign(self):
        self.assertEqual(
            kg.live_foreign_owner(_owner(), alive=lambda *a: True,
                                  is_ancestor=lambda p: False), 4242)

    def test_dead_owner_is_not_a_claim(self):
        self.assertIsNone(kg.live_foreign_owner(
            _owner(), alive=lambda *a: False, is_ancestor=lambda p: False))

    def test_self_is_not_foreign(self):
        self.assertIsNone(kg.live_foreign_owner(
            _owner(pid=os.getpid()), alive=lambda *a: True,
            is_ancestor=lambda p: False))

    def test_ancestor_is_not_foreign(self):
        # The session anchor is an ancestor of every cb launched from it —
        # this is what lets the owning session's own `cb down` / mid-bench
        # recycle through.
        self.assertIsNone(kg.live_foreign_owner(
            _owner(), alive=lambda *a: True, is_ancestor=lambda p: True))

    def test_no_manifest_or_unattributable_is_none(self):
        for m in (None, {}, {"owner_pid": "x"}, {"owner_pid": 0}):
            self.assertIsNone(kg.live_foreign_owner(
                m, alive=lambda *a: True, is_ancestor=lambda p: False), m)

    def test_probe_failure_is_not_a_claim_of_ownership(self):
        def boom(*a, **k):
            raise OSError("no process table")
        self.assertIsNone(kg.live_foreign_owner(
            _owner(), alive=boom, is_ancestor=lambda p: False))


class TestDecide(unittest.TestCase):
    def test_test_process_refused(self):
        self.assertEqual(kg.decide(is_test=True, allow_real_kills=False),
                         kg.REFUSED_TEST)

    def test_override_allows_a_test_process(self):
        self.assertIsNone(kg.decide(is_test=True, allow_real_kills=True))

    def test_live_owner_refused(self):
        self.assertEqual(
            kg.decide(is_test=False, allow_real_kills=False,
                      live_owner_pid=777),
            "REFUSED(live-owner pid=777)")

    def test_takeover_override(self):
        self.assertIsNone(kg.decide(is_test=False, allow_real_kills=False,
                                    live_owner_pid=777, allow_takeover=True))

    def test_clean_process_allowed(self):
        self.assertIsNone(kg.decide(is_test=False, allow_real_kills=False))

    def test_test_refusal_outranks_the_takeover_override(self):
        # CB_ALLOW_STACK_TAKEOVER is about stack ownership, never a licence for
        # a test process to kill.
        self.assertEqual(
            kg.decide(is_test=True, allow_real_kills=False,
                      live_owner_pid=777, allow_takeover=True),
            kg.REFUSED_TEST)


# --------------------------------------------------------------------------- #
# 3. THE SEAM: the real boundary is not reached from a test process.           #
# --------------------------------------------------------------------------- #

class _KillSeam(unittest.TestCase):
    """Base: redirect the kill audit into a tempdir, and record every argv the
    rig would shell. `real=True` additionally makes the recorder LOOK like the
    genuine boundary (`stack._REAL_SUBPROCESS_RUN`), which is how an offline
    test can assert on the production path without one real kill."""

    CB = r"c:\gh\craftbench\scratch\craftbenchgraded\craftbenchtemplate.uproject"

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.audit = Path(self.td.name) / "kill-audit.log"
        p = mock.patch.object(stack, "_KILL_AUDIT_PATH", lambda: self.audit)
        p.start(); self.addCleanup(p.stop)
        # No manifest anywhere near the real one.
        e = mock.patch.dict(os.environ, {
            "CB_STACK_MANIFEST": str(Path(self.td.name) / "manifest.json")})
        e.start(); self.addCleanup(e.stop)
        for var in ("CB_ALLOW_REAL_KILLS", "CB_ALLOW_STACK_TAKEOVER",
                    "CB_IN_TEST", "CB_STACK_GUARD"):
            os.environ.pop(var, None)
        self.calls = []

    def _recorder(self, *, real: bool):
        def fake_run(cmd, **kw):
            self.calls.append(list(cmd))
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        ctx = [mock.patch.object(stack.subprocess, "run", fake_run),
               mock.patch.object(stack, "IS_WINDOWS", True)]
        if real:
            # Make the double indistinguishable from the genuine boundary, so
            # the gate treats this call as a REAL effect.
            ctx.append(mock.patch.object(stack, "_REAL_SUBPROCESS_RUN", fake_run))
        for c in ctx:
            c.start(); self.addCleanup(c.stop)

    def audit_text(self) -> str:
        try:
            return self.audit.read_text(encoding="utf-8")
        except OSError:
            return ""


class TestRefusalUnderTestDetection(_KillSeam):
    """THE decisive suite: the taskkill boundary is NOT reached."""

    def test_kill_by_image_never_shells_from_a_test(self):
        self._recorder(real=True)
        stack.kill_by_image("UnrealEditor")
        self.assertEqual(self.calls, [],
                         "kill_by_image is the call that murdered the live "
                         "editor on 2026-08-07 — it must not reach the OS")
        self.assertIn("REFUSED(test-process)", self.audit_text())
        self.assertIn("image=UnrealEditor", self.audit_text())

    def test_kill_by_image_is_gated_even_with_a_substituted_boundary(self):
        # The bluntest primitive has no test that asserts its argv, so it is
        # gated UNCONDITIONALLY — not merely when the boundary looks real.
        self._recorder(real=False)
        stack.kill_by_image("UnrealEditor", "node")
        self.assertEqual(self.calls, [])

    def test_kill_pid_never_signals_from_a_test(self):
        self._recorder(real=True)
        with mock.patch.dict(sys.modules, {"psutil": None}):
            stack._kill_pid(4242, "kill_port_owner(3000)")
        self.assertEqual(self.calls, [])
        self.assertIn("REFUSED(test-process)", self.audit_text())

    def test_kill_port_owner_never_signals_from_a_test(self):
        self._recorder(real=True)
        with mock.patch.object(stack, "_listening_pids", lambda port: [4242]), \
             mock.patch.dict(sys.modules, {"psutil": None}):
            stack.kill_port_owner(3000)
        self.assertEqual(self.calls, [],
                         ":3000/:3002/:9222 owners were collateral in the "
                         "2026-08-07 incident")

    def test_scoped_editor_kill_refused_at_the_real_boundary(self):
        self._recorder(real=True)
        with mock.patch.object(stack, "_editor_procs",
                               lambda: [(101, self.CB)]):
            stack.kill_craftbench_editors(log=lambda *a: None)
        self.assertEqual(self.calls, [])
        self.assertIn("REFUSED(test-process)", self.audit_text())

    # The scoped-CLIENT kill had a sibling case here until 2026-08-28. It
    # covered stack.kill_client_procs, which reaped the Aura web client on
    # :3002 — proprietary bring-up machinery that is not part of the
    # open-source release, so the function and its case both went. The guard
    # itself is unchanged and the editor / port-owner / tree-kill / stop_stack
    # boundaries above and below still pin it.

    def test_orphan_sweep_tree_kill_refused_at_the_real_boundary(self):
        self._recorder(real=True)
        sg._tree_kill(4242)
        self.assertEqual(self.calls, [])
        self.assertIn("REFUSED(test-process)", self.audit_text())

    def test_stop_stack_refuses_whole_and_touches_nothing(self):
        self._recorder(real=True)
        logs = []
        # close_dev_browser_gracefully was removed with the proprietary
        # client lane; the surviving kill primitives carry the contract.
        with mock.patch.object(stack, "kill_port_owner") as ports, \
        mock.patch.object(stack, "kill_craftbench_editors") as editors:
            stack.stop_stack(log=logs.append)
        ports.assert_not_called()
        editors.assert_not_called()
        self.assertIn("REFUSED", "\n".join(logs))
        self.assertIn("REFUSED(test-process)", self.audit_text())

    def test_existing_scoping_tests_keep_their_boundary(self):
        # The compatibility contract, asserted directly: with subprocess.run
        # SUBSTITUTED (what every pre-existing kill test does) the rig still
        # issues exactly the argv those tests assert on.
        self._recorder(real=False)
        with mock.patch.object(stack, "_editor_procs",
                               lambda: [(101, self.CB)]):
            stack.kill_craftbench_editors(log=lambda *a: None)
        self.assertEqual(self.calls, [["taskkill", "/F", "/T", "/PID", "101"]])


class TestDeliberateOverride(_KillSeam):
    """CB_ALLOW_REAL_KILLS=1 — the ONE legitimate case (a human debugging kill
    paths from a REPL that happens to have imported unittest)."""

    def test_override_reaches_the_boundary(self):
        self._recorder(real=True)
        os.environ["CB_ALLOW_REAL_KILLS"] = "1"
        stack.kill_by_image("LiveCodingConsole")
        self.assertEqual(self.calls,
                         [["taskkill", "/F", "/IM", "LiveCodingConsole.exe"]])
        self.assertNotIn("REFUSED", self.audit_text())
        self.assertIn("image=LiveCodingConsole", self.audit_text())

    def test_override_is_still_audited_with_the_acting_role(self):
        self._recorder(real=True)
        os.environ["CB_ALLOW_REAL_KILLS"] = "true"
        stack.kill_by_image("CrashReportClient")
        self.assertIn("role=test", self.audit_text())

    def test_override_does_not_bypass_the_live_owner_layer(self):
        self._recorder(real=True)
        os.environ["CB_ALLOW_REAL_KILLS"] = "1"
        with mock.patch.object(sg, "pid_alive", lambda *a, **k: True), \
             mock.patch.object(sg, "_is_ancestor", lambda p: False):
            sg.write_manifest(_manifest(owner_pid=999999))
            stack.kill_by_image("UnrealEditor")
        self.assertEqual(self.calls, [])
        self.assertIn("REFUSED(live-owner pid=999999)", self.audit_text())


def _manifest(**over):
    m = {
        "schema": sg.SCHEMA,
        "state": sg.STATE_GREEN,
        "generation": "20260807-000000-999999",
        "created_at": 1000.0,
        "last_activity": 1000.0,
        "owner_pid": 999999,
        "owner_created": 999.0,
        "owner_kind": "cb",
        "session_pid": None,
        "session_created": None,
        "repo_root": r"C:\gh\craftbench",
        "uproject": r"C:\cb\scratch\X.uproject",
        "ports": [3000, 3002, 9222, 30010],
        "no_teardown": False,
        "command": "bench",
    }
    m.update(over)
    return m


class TestLiveOwnerRefusal(_KillSeam):
    """Layer 2: a LIVE bench is protected from ANY concurrent process — another
    cb, a stray script, another agent session. Exercised with the test layer
    deliberately overridden, so the live-owner refusal is the only thing that
    can stop the kill."""

    def setUp(self):
        super().setUp()
        os.environ["CB_ALLOW_REAL_KILLS"] = "1"
        self._recorder(real=True)

    def _with_owner(self, *, alive: bool, ancestor: bool, **over):
        sg.write_manifest(_manifest(**over))
        return (mock.patch.object(sg, "pid_alive", lambda *a, **k: alive),
                mock.patch.object(sg, "_is_ancestor", lambda p: ancestor))

    def test_live_foreign_owner_refuses(self):
        a, b = self._with_owner(alive=True, ancestor=False)
        with a, b:
            stack.kill_by_image("UnrealEditor")
        self.assertEqual(self.calls, [])
        self.assertIn("REFUSED(live-owner pid=999999)", self.audit_text())

    def test_dead_owner_does_not_refuse(self):
        # An orphan manifest is exactly what teardown exists to clean up.
        a, b = self._with_owner(alive=False, ancestor=False)
        with a, b:
            stack.kill_by_image("UnrealEditor")
        self.assertEqual(self.calls,
                         [["taskkill", "/F", "/IM", "UnrealEditor.exe"]])

    def test_owner_is_us_does_not_refuse(self):
        a, b = self._with_owner(alive=True, ancestor=False,
                                owner_pid=os.getpid())
        with a, b:
            stack.kill_by_image("UnrealEditor")
        self.assertEqual(len(self.calls), 1, "our own stack is ours to recycle")

    def test_session_anchor_ancestor_does_not_refuse(self):
        a, b = self._with_owner(alive=True, ancestor=True, owner_kind="session")
        with a, b:
            stack.kill_by_image("UnrealEditor")
        self.assertEqual(len(self.calls), 1,
                         "`cb down` from the owning session must work")

    def test_takeover_override(self):
        os.environ["CB_ALLOW_STACK_TAKEOVER"] = "1"
        self.addCleanup(os.environ.pop, "CB_ALLOW_STACK_TAKEOVER", None)
        a, b = self._with_owner(alive=True, ancestor=False)
        with a, b:
            stack.kill_by_image("UnrealEditor")
        self.assertEqual(len(self.calls), 1)

    def test_a_pending_manifest_protects_a_bring_up_in_flight(self):
        a, b = self._with_owner(alive=True, ancestor=False,
                                state=sg.STATE_PENDING)
        with a, b:
            stack.kill_by_image("UnrealEditor")
        self.assertEqual(self.calls, [],
                         "a bring-up in flight is as protected as a green stack")

    def test_guard_kill_switch_disables_only_the_owner_layer(self):
        os.environ["CB_STACK_GUARD"] = "0"
        self.addCleanup(os.environ.pop, "CB_STACK_GUARD", None)
        a, b = self._with_owner(alive=True, ancestor=False)
        with a, b:
            stack.kill_by_image("UnrealEditor")
        self.assertEqual(len(self.calls), 1)
        # ...and with the test override removed, the test layer still refuses.
        os.environ.pop("CB_ALLOW_REAL_KILLS")
        self.calls.clear()
        with a, b:
            stack.kill_by_image("UnrealEditor")
        self.assertEqual(self.calls, [])


class TestBringupArmsOwnershipEarly(_KillSeam):
    """Layer 3 wiring: `invoke_bringup` arms a PENDING manifest BEFORE the
    first process starts, and promotes it only at STACK GREEN."""

    def _paths(self, root: Path) -> "stack.StackPaths":
        return stack.StackPaths(craftbench=root, genius=root / "genius")

    def test_pending_arm_happens_before_stage_1(self):
        seen = []
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "genius" / "Ramen" / "vercelServer" / "node_modules").mkdir(
                parents=True)
            lines = []
            with mock.patch.object(stack.shutil, "which",
                                   side_effect=lambda t: f"/usr/bin/{t}"), \
                 mock.patch.object(stack, "test_up", return_value=False), \
                 mock.patch.object(stack, "wait_up", return_value=False), \
                 mock.patch.object(stack, "start_detached", return_value=None), \
                 mock.patch.object(
                     stack, "_record_stack_ownership",
                     side_effect=lambda u, *, promote, log=None: seen.append(
                         (promote, len(lines)))):
                ok = stack.invoke_bringup(
                    root / "p.uproject", root / "ue.exe", sys.executable, [],
                    self._paths(root), log=lines.append)
        self.assertFalse(ok)
        self.assertEqual([p for p, _ in seen], [False],
                         "armed PENDING once, never promoted on a failed "
                         "bring-up")
        # ...and it ran before a single stage emitted a line.
        self.assertEqual(seen[0][1], 0)

    # test_toolchain_gate_aborts_before_arming_anything stood here until the
    # public release. It stubbed `pnpm` missing and asserted the toolchain
    # gate aborted BEFORE ownership was armed. That gate existed for the node
    # stages (vercel :3000 / client :3002), which are not part of this
    # release, so there is no pre-arm abort left for it to assert.

    def test_recording_is_skipped_entirely_in_a_test_process(self):
        # The real guard: a unit test must never write the machine-global
        # manifest nor spawn a janitor. (Three existing tests drive the real
        # invoke_bringup.)
        with mock.patch.object(sg, "record_bringup_pending") as pend, \
             mock.patch.object(sg, "promote_to_green") as green:
            stack._record_stack_ownership(Path("X.uproject"), promote=False,
                                          log=lambda s: None)
            stack._record_stack_ownership(Path("X.uproject"), promote=True,
                                          log=lambda s: None)
        pend.assert_not_called()
        green.assert_not_called()

    def test_outside_a_test_process_it_arms_then_promotes(self):
        from aura_rig import janitor as _janitor
        with mock.patch.object(kg, "in_test_process", return_value=False), \
             mock.patch.object(_janitor, "arm", return_value=True) as arm, \
             mock.patch.object(sg, "record_bringup_pending") as pend, \
             mock.patch.object(sg, "promote_to_green") as green:
            stack._record_stack_ownership(Path("X.uproject"), promote=False,
                                          log=lambda s: None)
            stack._record_stack_ownership(Path("X.uproject"), promote=True,
                                          log=lambda s: None)
        pend.assert_called_once()
        green.assert_called_once()
        self.assertEqual(arm.call_count, 2, "arming is idempotent by design")


if __name__ == "__main__":
    unittest.main()
