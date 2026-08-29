"""The ``Environment`` seam — the ONLY Aura.app-aware abstraction (spec §6.1, §6.2).

The batch orchestrator (``run_batch.py``) is product-blind: it asks
``Environment.for_product(slug)`` for a world, then drives it through a tiny
contract — ``setup`` (bring the shared world up once), ``precheck`` (GO/NO-GO
before any task), ``workspace_for`` (per-task workspace), ``run_one`` (dispatch
the adapter), ``teardown`` (tear the shared world down once). Concurrency is a
property of the world (``max_concurrency``), not the orchestrator.

Two worlds ship in v1:

  - ``NullEnvironment`` (``claude-p``): no editor at all. ``max_concurrency=5``;
    per-task ``/tmp`` copy via ``workspace.build_workspace``; ``run_one`` is a
    plain ``adapter.run`` dispatch. Zero Aura — runs with Aura.app not even
    installed.

  - ``AuraEditorEnvironment`` (``aura-mcp`` / ``aura-agent`` / ``aura-mcp-bridge``):
    ONE shared live editor. ``max_concurrency=1`` (sequential) because there is
    no per-task write isolation on a single editor (spec §0 / §6.2). The macOS
    launch, the precheck NO-GO gates, the keepalive watchdog awareness, and the
    per-task live-project flow are ALL injectable seams so the whole module is
    unit-testable with NO Unreal editor, NO Aura, NO network, NO real API key
    (exactly how the adapters inject ``run_subprocess``).

This module is the ONLY one that imports the Aura headless surface, and it does
so LAZILY (inside the default seam impls) so importing ``environment`` pulls no
heavy deps. Everything else in the harness is product-neutral.

Pure stdlib. All UE/Aura/subprocess access is injectable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional, Protocol, Tuple, runtime_checkable


# A precheck gate returns (ok, human-readable detail).
GateResult = Tuple[bool, str]


# =============================================================================
# The Protocol (spec §6.1)
# =============================================================================

@runtime_checkable
class Environment(Protocol):
    """The Aura.app isolation seam. Implementations own a shared world's lifecycle."""

    max_concurrency: int                                   # 5 for Null, 1 for AuraEditor (v1)

    def setup(self) -> None:                               # bring the shared world up (once)
        ...

    def precheck(self) -> None:                            # GO/NO-GO before any task runs
        ...

    def workspace_for(self, task: Any) -> Any:             # per-task workspace
        ...

    def run_one(self, task: Any, adapter: Any, events: Any) -> Any:  # wraps the per-task flow
        ...

    def teardown(self) -> None:                            # tear the shared world down (once)
        ...


# =============================================================================
# NullEnvironment — claude-p; no Aura at all (spec §6.1)
# =============================================================================

def _default_build_workspace(**kwargs):
    """Lazily import workspace.build_workspace so importing this module is cheap.

    Injecting a ``build_workspace`` callable into ``NullEnvironment`` is the
    seam tests use; this default just reaches the real one.
    """
    from workspace import build_workspace  # local import: no heavy deps at module load
    return build_workspace(**kwargs)


class NullEnvironment:
    """claude-p world: per-task /tmp copy, trivially parallel, zero Aura.

    ``setup`` / ``precheck`` / ``teardown`` are no-ops (there is no shared world
    to stand up). ``workspace_for`` delegates to ``workspace.build_workspace``
    (injectable). ``run_one`` dispatches ``adapter.run`` on the per-task /tmp
    workspace, forwarding ``events`` keyword-only (spec §7).
    """

    max_concurrency = 5

    def __init__(self, build_workspace: Callable[..., Any] = _default_build_workspace):
        self._build_workspace = build_workspace

    def setup(self) -> None:
        return None

    def precheck(self) -> None:
        return None

    def teardown(self) -> None:
        return None

    def workspace_for(self, task: Any) -> Any:
        """Build a per-task /tmp workspace from the task's substrate inputs.

        ``task`` is a mapping carrying the build_workspace kwargs
        (``substrate_root``, ``agent_writable_json``, ``prompt_text``,
        ``run_id``, and optional ``root_dir``). Delegating like this keeps the
        orchestrator's task shape decoupled from workspace.py's signature.
        """
        kwargs = {
            "substrate_root": task["substrate_root"],
            "agent_writable_json": task["agent_writable_json"],
            "prompt_text": task["prompt_text"],
            "run_id": task["run_id"],
        }
        if task.get("root_dir") is not None:
            kwargs["root_dir"] = task["root_dir"]
        return self._build_workspace(**kwargs)

    def run_one(self, task: Any, adapter: Any, events: Any) -> Any:
        """Dispatch the adapter on the per-task /tmp workspace.

        ``task`` carries the built ``workspace`` (from ``workspace_for``) plus
        ``max_turns`` / ``timeout_s``. ``events`` is forwarded KEYWORD-ONLY so
        it can't collide with adapters that ignore it (spec §7).
        """
        workspace = task["workspace"]
        return adapter.run(
            prompt_path=workspace.prompt_path,
            workspace_dir=workspace.project_dir,
            max_turns=task["max_turns"],
            timeout_s=task["timeout_s"],
            events=events,
        )


# =============================================================================
# AuraEditorEnvironment — aura-*; ONE shared live editor (spec §6.1, §6.2)
# =============================================================================
#
# Keepalive numbers (spec §6.1, real watchdog values — comments, not asserts):
#   * C++ watchdog (Aura.cpp:864-865): waits 300 s for the initial bridge
#     connect, then self-exits (RequestExit) after 60 s of continuous
#     disconnect.
#   * Python /isMcpAlive (aura_server.py:1026): reports dead after 15 s without
#     a /mcpkeepalive ping.
#   During Pool-B idle grading there is no agent traffic, so liveness depends on
#   the Next server's editorRegistry pinging /mcpkeepalive every 2 s. This env
#   must NOT assume it owns that ping — it only verifies aliveness and confirms
#   the editor stays registered through grading. Worst case to test: a task in
#   Pool-B grading with zero chat traffic for >60 s.


# macOS path to the editor binary inside the .app bundle (spec §6.1 / the
# headless-breakthrough doc's proven launch). The default launch seam spawns
# THIS directly and owns the PID — it does NOT use :41200/api/headless/launch,
# which is Windows-only.
_MACOS_EDITOR_BINARY = "Contents/MacOS/UnrealEditor"


def _default_launch() -> int:
    """Spawn ONE headless macOS editor directly and return its owned PID.

    TODO(spec §15 OQ#1 — cross-platform launch is an OPEN QUESTION): v1 spawns
    ``UnrealEditor.app/Contents/MacOS/UnrealEditor`` directly on macOS (the
    proven path) and owns the PID. Windows / the ``/api/headless/*`` HTTP route
    need a different launch+status+shutdown mechanism — pin the per-OS spawn
    before relying on the HTTP route. This default is intentionally NOT exercised
    by the unit suite (which injects ``launch``); calling it requires a real
    editor on disk.
    """
    raise NotImplementedError(
        "AuraEditorEnvironment.launch default spawns a real macOS UnrealEditor "
        "(TODO spec §15 OQ#1: cross-platform launch unresolved). Inject a "
        "`launch` callable in tests / on non-macOS hosts. Reference path: "
        f"<UnrealEditor.app>/{_MACOS_EDITOR_BINARY}."
    )


def _default_teardown_editor(pid: int) -> None:
    """Shut the owned editor down (PID kill on macOS; /api/headless/shutdown on Win).

    TODO(spec §15 OQ#1): macOS path is a PID kill of the directly-spawned
    process; Windows would POST ``:41200/api/headless/shutdown``. Not exercised
    by the unit suite (teardown_editor is injected).
    """
    raise NotImplementedError(
        "AuraEditorEnvironment.teardown_editor default kills the real spawned "
        "PID (macOS) / POSTs /api/headless/shutdown (Windows). Inject a "
        "`teardown_editor` callable in tests."
    )


def _default_probe_connection() -> GateResult:
    """Gate (a): IPv6/connection — a token must arrive from :41200 in <10 s.

    Spec §6.1: assert ``/etc/hosts`` pins ``::1 api.anthropic.com`` (the
    breakthrough doc proves this is the ONLY working fix — IPv4-only pin,
    ``networksetup -setv6off``, and ``NODE_OPTIONS=--dns-result-order`` all
    failed, the last because Electron STRIPS ``NODE_OPTIONS`` from the :41200
    child), OR fire a one-shot ``:41200/api/chat`` health POST and confirm a
    token arrives in <10 s (not just a TCP connect). Real impl is the live
    smoke; unit tests inject this seam.
    """
    raise NotImplementedError(
        "probe_connection default does a live :41200/api/chat health POST "
        "(IPv6 gate). Inject a probe in tests."
    )


def _default_probe_api_key() -> GateResult:
    """Gate (b): ANTHROPIC_API_KEY is in the editor/server process env.

    Spec §6.1: the local route reads the key from env, NOT the request — so the
    spawned editor's environment must carry it. Pure: checks the env the default
    launch would inherit. Inject in tests so no real key is required.
    """
    import os
    key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not key:
        return (False, "ANTHROPIC_API_KEY missing from editor/server process env")
    return (True, "ANTHROPIC_API_KEY present in process env")


def _default_probe_subscription() -> GateResult:
    """Gate (c, aura-mcp only): :3008 validate-access answers (subscription gate).

    Spec §6.1: the subscription gate for ``generate_cpp_file``. Real impl hits
    ``:3008``; unit tests inject this seam.
    """
    raise NotImplementedError(
        "probe_subscription default queries :3008 validate-access. Inject in tests."
    )


DEFAULT_EDITOR_PORT = 41200


def count_listeners_on_port(port: int) -> Optional[int]:
    """Number of distinct PIDs LISTENing on ``port`` per ``lsof``, or None on error.

    macOS/BSD ``lsof -nP -iTCP:<port> -sTCP:LISTEN``. None when lsof is absent or
    errors (the caller degrades to a soft warning rather than a hard FAIL).
    """
    import shutil
    import subprocess

    lsof = shutil.which("lsof")
    if lsof is None:
        return None
    try:
        proc = subprocess.run(
            [lsof, "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    pids: set[str] = set()
    for line in proc.stdout.splitlines()[1:]:  # skip header
        parts = line.split()
        if len(parts) >= 2:
            pids.add(parts[1])
    return len(pids)


def check_single_editor(port: int = DEFAULT_EDITOR_PORT) -> GateResult:
    """Exactly one process LISTENing on the editor port (single-editor exclusivity).

    Two editors racing the same packaged build can route the driver to the wrong
    session, so >1 is a FAIL. If lsof is unavailable we cannot prove exclusivity,
    so it soft-passes with a warning rather than blocking on locked-down hosts.
    """
    n = count_listeners_on_port(port)
    if n is None:
        return True, f"could not enumerate listeners on :{port} (lsof unavailable) — exclusivity UNVERIFIED"
    if n == 0:
        return False, f"no process LISTENing on :{port} (port reachable but no editor owns it?)"
    if n > 1:
        return False, f"{n} processes LISTENing on :{port} — multiple editors race the build; close all but one"
    return True, f"exactly one editor LISTENing on :{port}"


def _default_probe_single_editor() -> GateResult:
    """Gate (d): exactly one process LISTENs on :41200 (single-editor exclusivity).

    aura-* batches are mutually exclusive on the box — no interactive editor may
    be open during a headless batch. Unit tests inject this seam so no real
    listener is needed.
    """
    return check_single_editor(DEFAULT_EDITOR_PORT)


def _default_run_live_project(task: Any, adapter: Any, events: Any) -> Any:
    """Wrap the existing per-task live-project flow (run.py::_run_live_project).

    Spec §6.1: REUSED UNCHANGED — per-task backup → stage fairness → dispatch
    adapter → restore fairness → snapshot diff → restore writable backup. Safe
    because aura-* is sequential, and between tasks the writable tree is restored
    to clean so the next agent doesn't inherit the prior task's edits (the
    breakthrough doc's finding #5: the agent reuses the first writable actor it
    finds). Imported lazily; unit tests inject this seam so NO real editor runs.

    ``task`` carries the ``run.py`` argv namespace (``args``), the ``run_id``,
    the ``run_dir`` and the ``prompt``; this default forwards to the real
    function, which returns its process exit code.
    """
    from run import _run_live_project
    return _run_live_project(task["args"], task["run_id"], task["run_dir"], task["prompt"])


class AuraEditorEnvironment:
    """aura-* world: ONE shared live editor, sequential (max_concurrency=1).

    Every Aura/UE/subprocess access is an INJECTED seam (launch, teardown,
    the four precheck probes, the live-project runner). The defaults reference
    the real macOS spawn / probes but raise NotImplementedError where a real
    editor or network is required, so the unit suite NEVER touches a real editor.
    """

    max_concurrency = 1

    def __init__(
        self,
        launch: Callable[[], int] = _default_launch,
        teardown_editor: Callable[[int], None] = _default_teardown_editor,
        probe_connection: Callable[[], GateResult] = _default_probe_connection,
        probe_api_key: Callable[[], GateResult] = _default_probe_api_key,
        probe_subscription: Callable[[], GateResult] = _default_probe_subscription,
        probe_single_editor: Callable[[], GateResult] = _default_probe_single_editor,
        run_live_project: Callable[[Any, Any, Any], Any] = _default_run_live_project,
    ):
        self._launch = launch
        self._teardown_editor = teardown_editor
        self._probe_connection = probe_connection
        self._probe_api_key = probe_api_key
        self._probe_subscription = probe_subscription
        self._probe_single_editor = probe_single_editor
        self._run_live_project = run_live_project
        # The PID of the ONE editor this env owns; None until setup launches it.
        self.editor_pid: Optional[int] = None

    def setup(self) -> None:
        """Launch ONE headless editor once and own its PID (idempotent).

        Spec §6.1: on macOS, spawn ``UnrealEditor.app/Contents/MacOS/UnrealEditor``
        directly and own the PID. If already launched, this is a no-op (must NOT
        spawn a second editor — single-editor exclusivity).
        """
        if self.editor_pid is not None:
            return None  # already up — do not relaunch
        self.editor_pid = self._launch()
        return None

    def precheck(self) -> None:
        """Run all NO-GO gates; raise RuntimeError on the FIRST failing gate.

        Spec §6.1 gates, in order: (a) IPv6/connection, (b) ANTHROPIC_API_KEY,
        (c) :3008 subscription (aura-mcp), (d) single-editor exclusivity. All
        must pass before ANY task runs.
        """
        for name, gate in (
            ("connection/IPv6", self._probe_connection),
            ("ANTHROPIC_API_KEY", self._probe_api_key),
            ("subscription(:3008)", self._probe_subscription),
            ("single-editor(:41200)", self._probe_single_editor),
        ):
            ok, detail = gate()
            if not ok:
                raise RuntimeError(f"precheck NO-GO [{name}]: {detail}")
        return None

    def workspace_for(self, task: Any) -> Any:
        """The live project itself — no per-task subfolder (spec §6.1, §6.2).

        Tasks keep their existing fixed paths; sequential execution + per-task
        backup/restore (run.py's flow) provide isolation instead of partitioning.
        The returned value is whatever the task carries as its live workspace.
        """
        return task.get("workspace") if hasattr(task, "get") else None

    def run_one(self, task: Any, adapter: Any, events: Any) -> Any:
        """Wrap the existing per-task live-project flow (spec §6.1).

        Delegates to the injected ``run_live_project`` seam (default = the real
        ``run.py::_run_live_project``). Safe because aura-* is sequential.
        """
        return self._run_live_project(task, adapter, events)

    def teardown(self) -> None:
        """Shut the owned editor down once and release the PID (idempotent).

        Spec §6.1: PID kill on macOS (or /api/headless/shutdown on Windows). A
        teardown with nothing launched is a harmless no-op.
        """
        if self.editor_pid is None:
            return None  # never launched — nothing to kill
        self._teardown_editor(self.editor_pid)
        self.editor_pid = None
        return None


# =============================================================================
# Product → Environment selection (spec §4, §6)
# =============================================================================

def for_product(slug: str) -> Environment:
    """Map a product slug to its Environment.

    ``claude-p[:<model>]`` → ``NullEnvironment`` (no editor; 5-wide /tmp copies).
    ``aura-mcp`` / ``aura-agent`` / ``aura-mcp-bridge`` (with optional ``:<model>``)
    → ``AuraEditorEnvironment`` (one shared editor; sequential).
    """
    backend = slug.split(":", 1)[0]
    if backend == "claude-p":
        return NullEnvironment()
    if backend in ("aura-mcp", "aura-agent", "aura-mcp-bridge"):
        return AuraEditorEnvironment()
    raise ValueError(
        f"Unknown product backend {backend!r} in slug {slug!r}. Supported: "
        "claude-p (NullEnvironment), aura-mcp / aura-agent / aura-mcp-bridge "
        "(AuraEditorEnvironment)."
    )
