"""Unit tests for environment.py — the Environment seam (spec §6.1, §6.2).

Every Aura/UE/subprocess access is an INJECTED seam, so these run fully
offline: NO Unreal editor, NO Aura, NO network, NO real API key. We assert

  - max_concurrency values per product (5 Null / 1 AuraEditor),
  - for_product(slug) mapping,
  - NullEnvironment.workspace_for delegates to an injected build_workspace,
  - NullEnvironment.run_one dispatches adapter.run on the /tmp workspace,
  - AuraEditorEnvironment.setup/precheck/teardown call the INJECTED seams
    (fakes) in the right order and never touch a real editor,
  - precheck FAILs (raises) when an injected gate fails,
  - AuraEditorEnvironment.run_one wraps the injected live-project runner.

Mirrors the sibling tests' sys.path + unittest convention (test_aura_port.py).

Run from tools/run-agent:

    python3 -m unittest tests.test_environment
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from environment import (  # noqa: E402
    AuraEditorEnvironment,
    Environment,
    NullEnvironment,
    for_product,
)


# --------------------------------------------------------------------------
# Lightweight fakes (no UE, no Aura, no network)
# --------------------------------------------------------------------------

class _FakeAdapter:
    """Records the run() call and returns a canned result object."""

    name = "fake-adapter"

    def __init__(self, result="RESULT"):
        self.result = result
        self.calls = []

    def run(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result


class _FakeWorkspace:
    def __init__(self, project_dir, prompt_path):
        self.project_dir = project_dir
        self.prompt_path = prompt_path


# --------------------------------------------------------------------------
# max_concurrency (spec §6.1: 5 for Null, 1 for AuraEditor)
# --------------------------------------------------------------------------

class TestMaxConcurrency(unittest.TestCase):
    def test_null_is_five(self):
        self.assertEqual(NullEnvironment().max_concurrency, 5)

    def test_aura_editor_is_one(self):
        self.assertEqual(AuraEditorEnvironment().max_concurrency, 1)

    def test_both_satisfy_environment_protocol(self):
        self.assertIsInstance(NullEnvironment(), Environment)
        self.assertIsInstance(AuraEditorEnvironment(), Environment)


# --------------------------------------------------------------------------
# for_product(slug) mapping (spec §4, §6)
# --------------------------------------------------------------------------

class TestForProduct(unittest.TestCase):
    def test_claude_p_is_null(self):
        self.assertIsInstance(for_product("claude-p"), NullEnvironment)

    def test_claude_p_with_model_is_null(self):
        self.assertIsInstance(for_product("claude-p:opus"), NullEnvironment)

    def test_aura_mcp_is_aura_editor(self):
        self.assertIsInstance(for_product("aura-mcp"), AuraEditorEnvironment)

    def test_aura_agent_is_aura_editor(self):
        self.assertIsInstance(for_product("aura-agent:claude-sonnet-4-6"), AuraEditorEnvironment)

    def test_aura_mcp_bridge_is_aura_editor(self):
        self.assertIsInstance(for_product("aura-mcp-bridge"), AuraEditorEnvironment)

    def test_unknown_slug_raises(self):
        with self.assertRaises(ValueError):
            for_product("totally-unknown")


# --------------------------------------------------------------------------
# NullEnvironment — no Aura at all (spec §6.1, §6.2)
# --------------------------------------------------------------------------

class TestNullEnvironment(unittest.TestCase):
    def test_setup_precheck_teardown_are_noops(self):
        env = NullEnvironment()
        # No exceptions, no return value expectations — pure no-ops.
        self.assertIsNone(env.setup())
        self.assertIsNone(env.precheck())
        self.assertIsNone(env.teardown())

    def test_workspace_for_delegates_to_injected_build_workspace(self):
        calls = []
        sentinel_ws = object()

        def fake_build_workspace(**kwargs):
            calls.append(kwargs)
            return sentinel_ws

        env = NullEnvironment(build_workspace=fake_build_workspace)
        task = {
            "substrate_root": Path("/sub"),
            "agent_writable_json": Path("/sub/AGENT_WRITABLE.json"),
            "prompt_text": "do the thing",
            "run_id": "20260604-000000-t1-claude-p",
        }
        out = env.workspace_for(task)
        self.assertIs(out, sentinel_ws)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["substrate_root"], Path("/sub"))
        self.assertEqual(calls[0]["run_id"], "20260604-000000-t1-claude-p")
        self.assertEqual(calls[0]["prompt_text"], "do the thing")

    def test_run_one_dispatches_adapter_run_on_tmp_workspace(self):
        env = NullEnvironment()
        adapter = _FakeAdapter(result="OK")
        ws = _FakeWorkspace(
            project_dir=Path("/tmp/run-agent-x/CraftBenchTemplate"),
            prompt_path=Path("/tmp/run-agent-x/PROMPT.md"),
        )
        task = {
            "workspace": ws,
            "max_turns": 40,
            "timeout_s": 600,
        }
        events = object()  # opaque EventSink — Null env just forwards it
        result = env.run_one(task, adapter, events)
        self.assertEqual(result, "OK")
        self.assertEqual(len(adapter.calls), 1)
        _args, kwargs = adapter.calls[0]
        # Dispatched on the per-task /tmp workspace (its project_dir + prompt).
        self.assertEqual(kwargs["workspace_dir"], ws.project_dir)
        self.assertEqual(kwargs["prompt_path"], ws.prompt_path)
        self.assertEqual(kwargs["max_turns"], 40)
        self.assertEqual(kwargs["timeout_s"], 600)
        # events is passed keyword-only per spec §7 (never positionally).
        self.assertIs(kwargs["events"], events)


# --------------------------------------------------------------------------
# AuraEditorEnvironment — all seams injected; NEVER touches a real editor
# --------------------------------------------------------------------------

class _AuraSeams:
    """Bundle of injectable fakes for AuraEditorEnvironment + an order log."""

    def __init__(self, gates=None):
        self.log = []
        # default gates all pass; flip one to a falsy verdict to test NO-GO
        self.gates = gates or {
            "connection": (True, "ipv6 pinned"),
            "api_key": (True, "ANTHROPIC_API_KEY present"),
            "subscription": (True, ":3008 ok"),
            "single_editor": (True, "exactly one :41200 listener"),
        }

    def launch(self):
        self.log.append("launch")
        return 4242  # fake PID — no real process

    def teardown_editor(self, pid):
        self.log.append(("teardown_editor", pid))

    # precheck probes (all return (ok, detail))
    def probe_connection(self):
        self.log.append("probe_connection")
        return self.gates["connection"]

    def probe_api_key(self):
        self.log.append("probe_api_key")
        return self.gates["api_key"]

    def probe_subscription(self):
        self.log.append("probe_subscription")
        return self.gates["subscription"]

    def probe_single_editor(self):
        self.log.append("probe_single_editor")
        return self.gates["single_editor"]


class TestAuraEditorSetup(unittest.TestCase):
    def test_setup_launches_via_injected_seam_and_owns_pid(self):
        seams = _AuraSeams()
        env = AuraEditorEnvironment(launch=seams.launch)
        env.setup()
        self.assertIn("launch", seams.log)
        # The env owns the PID the injected launch returned (for teardown).
        self.assertEqual(env.editor_pid, 4242)

    def test_setup_does_not_relaunch_when_already_up(self):
        seams = _AuraSeams()
        env = AuraEditorEnvironment(launch=seams.launch)
        env.setup()
        env.setup()  # idempotent — must not spawn a second editor
        self.assertEqual(seams.log.count("launch"), 1)


class TestAuraEditorPrecheck(unittest.TestCase):
    def test_precheck_calls_all_injected_gates_and_passes(self):
        seams = _AuraSeams()
        env = AuraEditorEnvironment(
            probe_connection=seams.probe_connection,
            probe_api_key=seams.probe_api_key,
            probe_subscription=seams.probe_subscription,
            probe_single_editor=seams.probe_single_editor,
        )
        env.precheck()  # all gates pass → no raise
        for probe in (
            "probe_connection",
            "probe_api_key",
            "probe_subscription",
            "probe_single_editor",
        ):
            self.assertIn(probe, seams.log)

    def test_precheck_raises_when_connection_gate_fails(self):
        seams = _AuraSeams(gates={
            "connection": (False, "no token in <10s — IPv6 not pinned"),
            "api_key": (True, ""),
            "subscription": (True, ""),
            "single_editor": (True, ""),
        })
        env = AuraEditorEnvironment(
            probe_connection=seams.probe_connection,
            probe_api_key=seams.probe_api_key,
            probe_subscription=seams.probe_subscription,
            probe_single_editor=seams.probe_single_editor,
        )
        with self.assertRaises(RuntimeError) as ctx:
            env.precheck()
        self.assertIn("IPv6", str(ctx.exception))

    def test_precheck_raises_when_api_key_gate_fails(self):
        seams = _AuraSeams(gates={
            "connection": (True, ""),
            "api_key": (False, "ANTHROPIC_API_KEY missing from editor env"),
            "subscription": (True, ""),
            "single_editor": (True, ""),
        })
        env = AuraEditorEnvironment(
            probe_connection=seams.probe_connection,
            probe_api_key=seams.probe_api_key,
            probe_subscription=seams.probe_subscription,
            probe_single_editor=seams.probe_single_editor,
        )
        with self.assertRaises(RuntimeError) as ctx:
            env.precheck()
        self.assertIn("ANTHROPIC_API_KEY", str(ctx.exception))

    def test_precheck_raises_when_single_editor_gate_fails(self):
        seams = _AuraSeams(gates={
            "connection": (True, ""),
            "api_key": (True, ""),
            "subscription": (True, ""),
            "single_editor": (False, "2 processes LISTEN on :41200"),
        })
        env = AuraEditorEnvironment(
            probe_connection=seams.probe_connection,
            probe_api_key=seams.probe_api_key,
            probe_subscription=seams.probe_subscription,
            probe_single_editor=seams.probe_single_editor,
        )
        with self.assertRaises(RuntimeError):
            env.precheck()


class TestAuraEditorTeardown(unittest.TestCase):
    def test_teardown_kills_owned_pid_via_injected_seam(self):
        seams = _AuraSeams()
        env = AuraEditorEnvironment(
            launch=seams.launch, teardown_editor=seams.teardown_editor
        )
        env.setup()
        env.teardown()
        self.assertIn(("teardown_editor", 4242), seams.log)
        # PID released so a later teardown is a harmless no-op.
        self.assertIsNone(env.editor_pid)

    def test_teardown_without_setup_is_noop(self):
        seams = _AuraSeams()
        env = AuraEditorEnvironment(teardown_editor=seams.teardown_editor)
        env.teardown()  # never launched → nothing to kill
        self.assertNotIn(
            ("teardown_editor", 4242),
            seams.log,
        )


class TestAuraEditorLifecycleOrder(unittest.TestCase):
    def test_setup_then_precheck_then_teardown_call_seams_in_order(self):
        seams = _AuraSeams()
        env = AuraEditorEnvironment(
            launch=seams.launch,
            teardown_editor=seams.teardown_editor,
            probe_connection=seams.probe_connection,
            probe_api_key=seams.probe_api_key,
            probe_subscription=seams.probe_subscription,
            probe_single_editor=seams.probe_single_editor,
        )
        env.setup()
        env.precheck()
        env.teardown()
        # launch happens before any probe; teardown last.
        self.assertEqual(seams.log[0], "launch")
        self.assertEqual(seams.log[-1], ("teardown_editor", 4242))
        # all four gates ran between launch and teardown
        self.assertEqual(
            seams.log[1:-1],
            [
                "probe_connection",
                "probe_api_key",
                "probe_subscription",
                "probe_single_editor",
            ],
        )


class TestAuraEditorRunOne(unittest.TestCase):
    def test_run_one_wraps_injected_live_project_runner(self):
        calls = []
        sentinel_result = object()

        def fake_live_runner(task, adapter, events):
            calls.append((task, adapter, events))
            return sentinel_result

        env = AuraEditorEnvironment(run_live_project=fake_live_runner)
        adapter = _FakeAdapter()
        task = {"task_id": "gp-gas-launch"}
        events = object()
        out = env.run_one(task, adapter, events)
        self.assertIs(out, sentinel_result)
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][1], adapter)
        self.assertIs(calls[0][2], events)

    def test_run_one_never_touches_a_real_editor(self):
        # With the runner injected, run_one must NOT import/launch UE or hit
        # the network. We assert by giving a runner that records and returns.
        seen = {}

        def fake_live_runner(task, adapter, events):
            seen["ran"] = True
            return "DONE"

        env = AuraEditorEnvironment(run_live_project=fake_live_runner)
        out = env.run_one({"task_id": "t"}, _FakeAdapter(), None)
        self.assertEqual(out, "DONE")
        self.assertTrue(seen["ran"])


if __name__ == "__main__":
    unittest.main()
