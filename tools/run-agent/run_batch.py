#!/usr/bin/env python3
"""tools/run-agent/run_batch.py — product-neutral two-pool batch orchestrator
(design spec §6, §11).

Runs a batch of CraftBench tasks against ONE coding product (``claude-p`` up to
5-wide in its own ``/tmp`` copies; ``aura-mcp``/``aura-agent`` strictly
sequential on the single shared editor) and emits the live disk contract
(``runs/<id>/status.json`` + ``events.jsonl`` + ``result.json``) that the
read-only TUI / ``live.py`` tail.

The orchestrator is **product-blind**: every Aura/UE/claude/verify/clock seam is
INJECTED, so the whole module is unit-testable with NO Unreal editor, NO Aura,
NO network, NO real API key — exactly how the adapters inject ``run_subprocess``
and ``environment.py`` injects its launch/probe seams.

Two-pool scheduling (spec §6.3):
  * **Pool A — agent dispatch**: ``Semaphore(min(--concurrency, env.max_concurrency))``.
    A task acquires A, runs ``env.run_one(task, adapter, events)``, and RELEASES A
    the instant the run finishes. So ``aura-*`` (``max_concurrency==1``) is
    sequential regardless of ``--concurrency``.
  * **Pool B — verification**: ``Semaphore(verify_concurrency)`` (default 1). On
    agent finish the task acquires B, snapshots + verifies (a separate cold UE
    process that does NOT touch the shared live editor), writes ``result.json``
    ATOMICALLY, then flips ``status.json.phase`` to ``done``.

Phase machine (spec §6.4):
  ``queued → launching(*) → running → grading → done`` (terminal
  ``error | timeout | cancelled``). ``launching`` only for the FIRST ``aura-*``
  task on a cold editor. Per-task failure isolation: one task's error/timeout
  NEVER aborts the others (spec §11). Cancellation (spec §6.5) sets a flag:
  in-flight tasks drain, no new task acquires Pool A, the un-started tasks end
  ``cancelled``, and the ``Environment`` is torn down.

result.json BEFORE done (spec §5.2): ``result.json`` is written atomically (via
``run_events.write_result_json`` — tmp + ``os.replace``) BEFORE
``status.json.phase`` flips to ``done``, closing the torn-read window.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import functools
import glob as _glob
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

# Self-relative imports (the package uses sys.path injection, mirroring run.py).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from adapters.base import (  # noqa: E402
    VERDICT_HARNESS_ERROR,
    is_graded_verdict,
    pass_rate,
    verdict_from_verifier,
)
from environment import for_product  # noqa: E402
from run_events import (  # noqa: E402
    FileEventSink,
    write_result_json,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUBSTRATE = REPO_ROOT / "UE-projects/CraftBenchTemplate"
VERIFIER = REPO_ROOT / "tools/verify-single/run_task.py"

# The §5.1 status.json phase enum (spec §6.4). Open enum for readers, but the
# orchestrator only ever writes these.
PHASE_QUEUED = "queued"
PHASE_LAUNCHING = "launching"
PHASE_RUNNING = "running"
PHASE_GRADING = "grading"
PHASE_DONE = "done"
PHASE_ERROR = "error"
PHASE_TIMEOUT = "timeout"
PHASE_CANCELLED = "cancelled"


# =============================================================================
# Task + cancellation value objects
# =============================================================================

@dataclass
class BatchTask:
    """One orchestrator-level task: identity + the bits the scheduler needs.

    ``payload`` carries whatever the chosen ``Environment.run_one`` /
    ``workspace_for`` need (the run.py argv namespace for aura-*, or the
    build_workspace kwargs for claude-p) — the orchestrator never inspects it,
    keeping the scheduler product-blind.
    """

    task_id: str
    run_id: str
    product: str
    max_steps: int = 40
    timeout_s: int = 600
    payload: Dict[str, Any] = field(default_factory=dict)


class Cancellation:
    """A cooperative cancellation flag (spec §6.5).

    The TUI key / SIGINT handler calls ``cancel()``; the scheduler checks
    ``cancelled`` before acquiring Pool A for each task. In-flight tasks drain;
    un-started tasks end ``cancelled``. Pure stdlib, thread/async-agnostic.
    """

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled


# A verify callable: (task, agent_result, events) -> (overall, report_dict).
VerifyResult = Tuple[str, Optional[Dict[str, Any]]]
VerifyFn = Callable[[BatchTask, Any, Any], Awaitable[VerifyResult]]


# =============================================================================
# Helpers — run_id, result.json shape, the default shelling verify
# =============================================================================

def make_run_id(task_id: str, model_slug: str, now: Optional[Callable[[], str]] = None) -> str:
    """Build ``<YYYYMMDD-HHMMSS>-<task_id>-<model_slug_safe>`` (run.py's scheme).

    Matches ``run.py::_make_run_id`` so ``collect()`` join keys are unchanged
    (spec §5). ``now`` is an injected wall-clock for deterministic tests.
    """
    if now is not None:
        ts = now()
    else:
        ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    model_slug_safe = model_slug.replace(":", "-").replace("/", "_")
    return f"{ts}-{task_id}-{model_slug_safe}"


def _agent_result_to_dict(agent_result: Any) -> Dict[str, Any]:
    """Best-effort pull of the AgentResult fields the matrix reads (run.py shape).

    Tolerant of partial result objects (fakes / coarse adapters) — missing
    attributes simply land as ``None``.
    """
    def g(name):
        return getattr(agent_result, name, None)

    return {
        "exit_code": g("exit_code"),
        "duration_s": g("duration_s"),
        "summary": g("summary"),
        "tool_use_count": g("tool_use_count"),
        "mcp_tool_use_count": g("mcp_tool_use_count"),
        "tool_names": g("tool_names"),
        "cost_usd": g("cost_usd"),
        "num_turns": g("num_turns"),
    }


def _build_result_obj(
    task: BatchTask,
    agent_result: Any,
    overall: str,
    verifier_report: Optional[Dict[str, Any]],
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble the ``result.json`` body (mirrors run.py::_write_result shape)."""
    obj: Dict[str, Any] = {
        "run_id": task.run_id,
        "task": task.task_id,
        "model": task.product,
        "overall": overall,
        "agent": _agent_result_to_dict(agent_result) if agent_result is not None else None,
        "verifier": verifier_report,
    }
    if error is not None:
        obj["error"] = error
    return obj


def _parse_verifier_overall(stdout: str) -> str:
    """Parse the verifier's 'overall : <VALUE>' line (FALLBACK only).

    Retained for back-compat. The verify path now uses
    :func:`adapters.base.verdict_from_verifier`, which reads report.json's
    authoritative ``overall`` and maps exit-3/4 to distinct non-graded
    verdicts. Delegates to the shared regex (single source of truth).
    """
    from adapters.base import _overall_from_stdout_regex

    return _overall_from_stdout_regex(stdout)


def summarize_verdicts(verdicts: List[Optional[str]]) -> Dict[str, Any]:
    """Aggregate a batch's verdicts into a pass-rate summary.

    The pass-rate DENOMINATOR is the count of GRADED verdicts
    (``adapters.base.GRADED_VERDICTS``): SUBSTRATE-REJECT / TIMEOUT /
    HARNESS-ERROR / UNGRADED and the rig's infra verdicts are harness conditions
    and are EXCLUDED so they can never be silently relabelled an agent FAIL
    (the verdict-stability notes F2). The excluded verdicts are still
    counted per-kind so they are visible, not lost.

    **``n_fail`` means "graded and did not pass", not "verdict == FAIL".** Since
    the 2026-08-17 denominator widening (the denominator rule) the graded set
    also carries SANDBOX-REJECT / NO_DELIVERABLE / FAIL_NO_EDITS, so a
    SANDBOX-REJECT lands in ``n_graded`` and therefore in ``n_fail``. That is
    deliberate — those describe what the model did — but anything rendering this
    dict as a table must not label the column "FAIL"; use "not passed", or split
    it with ``excluded_by_verdict``'s sibling reasoning.
    """
    graded = [v for v in verdicts if is_graded_verdict(v)]
    n_graded = len(graded)
    n_pass = sum(1 for v in graded if v == "PASS")
    excluded: Dict[str, int] = {}
    for v in verdicts:
        if not is_graded_verdict(v):
            key = v if v is not None else "None"
            excluded[key] = excluded.get(key, 0) + 1
    return {
        "n_total": len(verdicts),
        "n_graded": n_graded,
        "n_pass": n_pass,
        "n_fail": n_graded - n_pass,
        "pass_rate": pass_rate(verdicts),  # None when nothing graded
        "n_excluded": len(verdicts) - n_graded,
        "excluded_by_verdict": excluded,
    }


def _collect_result_verdicts(tasks: List[BatchTask], run_root: Path) -> List[Optional[str]]:
    """Read each task's ``result.json`` ``overall`` field off disk (or None)."""
    import json as _json

    verdicts: List[Optional[str]] = []
    for task in tasks:
        rj = Path(run_root) / task.run_id / "result.json"
        try:
            verdicts.append(_json.loads(rj.read_text(encoding="utf-8")).get("overall"))
        except Exception:
            verdicts.append(None)
    return verdicts


def make_default_verify(
    *,
    task_path_for: Callable[[BatchTask], Path],
    submission_dir_for: Callable[[BatchTask], Path],
    ue_root: str,
    run_subprocess: Callable[..., Any] = subprocess.run,
    repo_root: Path = REPO_ROOT,
    verifier: Path = VERIFIER,
) -> VerifyFn:
    """Build the default verify callable that shells ``tools/verify-single/run_task.py``.

    This is the production Pool-B grader: it spawns a SEPARATE cold UE process
    (it does NOT touch the shared live editor, so Pool B never contends with
    Pool A's editor — spec §6.3). ``run_subprocess`` is injectable so the unit
    suite passes a FAKE verify instead and never shells anything.
    """

    async def _verify(task: BatchTask, agent_result: Any, events: Any) -> VerifyResult:
        cmd = [
            sys.executable,
            str(verifier),
            "--task",
            str(task_path_for(task)),
            "--submission",
            str(submission_dir_for(task)),
            "--ue-root",
            ue_root,
        ]
        # Run the blocking subprocess off the event loop so Pool A keeps moving.
        loop = asyncio.get_event_loop()
        completed = await loop.run_in_executor(
            None,
            functools.partial(
                run_subprocess, cmd, cwd=str(repo_root), capture_output=True, text=True
            ),
        )
        stdout = getattr(completed, "stdout", "") or ""
        returncode = getattr(completed, "returncode", None)
        # Exit-3 (verifier-hash-manifest reject) / exit-4 (sandbox reject) map to
        # distinct NON-GRADED verdicts — verifier-noise, never an agent FAIL
        # (mirrors aura_rig/driver.py and run.py). Otherwise read the
        # authoritative `overall` from report.json, falling back to stdout.
        overall = verdict_from_verifier(returncode, stdout)
        report = {"stdout": stdout, "overall": overall}
        return (overall, report)

    return _verify


# =============================================================================
# The two-pool scheduler (spec §6.3, §6.4, §11)
# =============================================================================

async def run_batch(
    tasks: List[BatchTask],
    *,
    env: Any,
    make_adapter: Callable[[str], Any],
    verify: VerifyFn,
    concurrency: int,
    verify_concurrency: int = 1,
    run_root: Path,
    now: Optional[Callable[[], str]] = None,
    cancellation: Optional[Cancellation] = None,
    make_sink: Optional[Callable[[Path, Optional[Callable[[], str]]], Any]] = None,
    disk_settle: Callable[[], Awaitable[None]] = lambda: asyncio.sleep(0),
) -> List[BatchTask]:
    """Drive a batch through the two-pool scheduler. Returns the task list.

    Injectable seams (so the whole orchestrator is unit-testable with fakes):
      * ``env``          — an ``Environment`` (NullEnvironment / AuraEditorEnvironment
                           / a fake). Owns ``max_concurrency`` + the world lifecycle.
      * ``make_adapter`` — slug → adapter factory (fake in tests).
      * ``verify``       — async ``(task, agent_result, events) -> (overall, report)``.
      * ``now``          — injected clock for ``status.json``/``events.jsonl`` ts.
      * ``cancellation`` — a ``Cancellation`` flag (spec §6.5).
      * ``make_sink``    — sink factory ``(run_dir, now) -> EventSink`` (default
                           ``FileEventSink``); override to spy in tests.
      * ``disk_settle``  — the short post-finish settle before snapshot (spec §6.3);
                           a no-op ``asyncio.sleep(0)`` by default, real sleep in prod.

    Pool A width = ``min(concurrency, env.max_concurrency)`` (spec §6.3): so
    ``aura-*`` (``max_concurrency==1``) is sequential regardless of ``--concurrency``.
    """
    cancellation = cancellation or Cancellation()
    if make_sink is None:
        make_sink = lambda run_dir, now: FileEventSink(run_dir, now=now)  # noqa: E731

    pool_a_width = max(1, min(concurrency, getattr(env, "max_concurrency", 1)))
    pool_a = asyncio.Semaphore(pool_a_width)
    pool_b = asyncio.Semaphore(max(1, verify_concurrency))

    # `aura-*` launching: the FIRST task on a cold editor passes through the
    # 'launching' phase. A single-acquire async lock + a flag track that exactly
    # one task does the launch transition. max_concurrency==1 ⇒ the env is the
    # one-shared-editor world (spec §6.1).
    is_aura_world = getattr(env, "max_concurrency", 1) == 1
    launched_flag = {"done": False}
    launch_lock = asyncio.Lock()

    # --- shared world: setup + precheck ONCE (spec §6.1) -----------------
    env.setup()
    env.precheck()

    try:
        await asyncio.gather(
            *[
                _run_task(
                    task,
                    env=env,
                    make_adapter=make_adapter,
                    verify=verify,
                    pool_a=pool_a,
                    pool_b=pool_b,
                    run_root=run_root,
                    now=now,
                    cancellation=cancellation,
                    make_sink=make_sink,
                    disk_settle=disk_settle,
                    is_aura_world=is_aura_world,
                    launched_flag=launched_flag,
                    launch_lock=launch_lock,
                )
                for task in tasks
            ]
        )
    finally:
        # Tear the shared world down ONCE (spec §6.1, §6.5: also on cancel).
        env.teardown()

    return tasks


async def _run_task(
    task: BatchTask,
    *,
    env: Any,
    make_adapter: Callable[[str], Any],
    verify: VerifyFn,
    pool_a: asyncio.Semaphore,
    pool_b: asyncio.Semaphore,
    run_root: Path,
    now: Optional[Callable[[], str]],
    cancellation: Cancellation,
    make_sink: Callable[[Path, Optional[Callable[[], str]]], Any],
    disk_settle: Callable[[], Awaitable[None]],
    is_aura_world: bool,
    launched_flag: Dict[str, bool],
    launch_lock: asyncio.Lock,
) -> None:
    """Run ONE task through the phase machine, isolated from its siblings.

    Any error/timeout sets the terminal phase, writes a harness ``result.json``,
    and releases the pool slot — it NEVER propagates (spec §11 failure
    isolation). A torn pre-run cancellation lands the task in ``cancelled``.
    """
    run_dir = Path(run_root) / task.run_id
    sink = make_sink(run_dir, now)

    # --- queued: lay down the FULL §5.1 contract shape -------------------
    sink.write_status_full(
        run_id=task.run_id,
        task_id=task.task_id,
        product=task.product,
        phase=PHASE_QUEUED,
        step=None,
        max_steps=task.max_steps,
        current_tool=None,
        tool_count=None,
        tokens_in=None,
        tokens_out=None,
        started_at=None,
        elapsed_s=None,
        result=None,
        error=None,
    )
    sink.emit({"type": "phase", "phase": PHASE_QUEUED})

    # --- cancellation BEFORE acquiring Pool A → never starts (spec §6.5) --
    if cancellation.cancelled:
        sink.emit({"type": "phase", "phase": PHASE_CANCELLED})
        sink.status(phase=PHASE_CANCELLED)
        return

    agent_result: Any = None
    try:
        # ---- Pool A: agent dispatch (acquire → run → RELEASE on finish) --
        async with pool_a:
            # Re-check cancellation after acquiring (a cancel may have landed
            # while we waited for the slot) — drain without starting.
            if cancellation.cancelled:
                sink.emit({"type": "phase", "phase": PHASE_CANCELLED})
                sink.status(phase=PHASE_CANCELLED)
                return

            # launching(*) — only the FIRST aura-* task on the cold editor.
            if is_aura_world:
                async with launch_lock:
                    if not launched_flag["done"]:
                        launched_flag["done"] = True
                        sink.emit({"type": "phase", "phase": PHASE_LAUNCHING})
                        sink.status(phase=PHASE_LAUNCHING)

            started_at = now() if now is not None else None
            sink.emit({"type": "phase", "phase": PHASE_RUNNING})
            sink.status(phase=PHASE_RUNNING, started_at=started_at)

            adapter = make_adapter(task.product)
            agent_result = await env.run_one(task, adapter, sink)

        # Pool A is now released (we left the `async with`); a short disk-settle
        # before snapshot/verify (spec §6.3 snapshot ordering).
        await disk_settle()

        # ---- Pool B: verification (snapshot → grade) --------------------
        async with pool_b:
            sink.emit({"type": "phase", "phase": PHASE_GRADING})
            sink.status(phase=PHASE_GRADING)
            overall, report = await verify(task, agent_result, sink)

        # result.json ATOMICALLY, BEFORE the done flip (spec §5.2).
        result_obj = _build_result_obj(task, agent_result, overall, report)
        write_result_json(run_dir, result_obj)

        # ---- done ------------------------------------------------------
        sink.emit({"type": "phase", "phase": PHASE_DONE})
        sink.status(phase=PHASE_DONE, result=overall)

    except asyncio.TimeoutError as exc:
        _terminal_failure(sink, run_dir, task, agent_result, PHASE_TIMEOUT, str(exc) or "timeout")
    except asyncio.CancelledError:
        # Cooperative drain: mark cancelled, then re-raise so gather unwinds.
        sink.emit({"type": "phase", "phase": PHASE_CANCELLED})
        sink.status(phase=PHASE_CANCELLED)
        raise
    except Exception as exc:  # noqa: BLE001 — per-task isolation (spec §11)
        _terminal_failure(sink, run_dir, task, agent_result, PHASE_ERROR, repr(exc))


def _terminal_failure(
    sink: Any,
    run_dir: Path,
    task: BatchTask,
    agent_result: Any,
    phase: str,
    error: str,
) -> None:
    """Land a task in a terminal failure phase + write a harness result.json.

    Spec §11: a task that errors/times out sets ``phase=error|timeout``, writes a
    harness ``result.json`` (so the matrix has an entry), and releases its slot;
    the others continue. ``result.json`` is written BEFORE the phase flip so a
    reader that sees the terminal phase can still find a matrix entry (§5.2).

    The error phase writes ``HARNESS-ERROR``, NOT ``FAIL``. Its only caller is the
    bare ``except Exception`` in ``_run_one``, which wraps adapter dispatch AND the
    grading call — so an adapter crash, a dead editor, a full disk, or a bug in the
    verify callable all land here. ``FAIL`` is in ``GRADED_VERDICTS``
    (``adapters/base.py``), so writing it here charged every one of those to the
    model under test. The allowlist was never the problem: the writer had already
    laundered the fault into a graded verdict before any consumer saw it.
    ``TIMEOUT`` is non-graded by omission and is correct as-is.
    ``aura_rig/batch_eval.py`` has always done this right (``overall=None``).
    """
    overall = VERDICT_HARNESS_ERROR if phase == PHASE_ERROR else "TIMEOUT"
    result_obj = _build_result_obj(task, agent_result, overall, None, error=error)
    write_result_json(run_dir, result_obj)
    sink.emit({"type": "phase", "phase": phase, "error": error})
    sink.status(phase=phase, error=error, result=overall)


# =============================================================================
# CLI — mirrors run.py's args + --tasks / --concurrency / --verify-concurrency
#       / --no-tui (spec §6 header)
# =============================================================================

def _expand_tasks(patterns: List[str]) -> List[Path]:
    """Expand a glob/list of task patterns into concrete .md paths.

    Each entry is a literal path OR a glob (``tasks/gp-*.md``). De-duped,
    order-stable. Mirrors the spec §6 ``--tasks tasks/gp-*.md`` example.
    """
    out: List[Path] = []
    seen = set()
    for pat in patterns:
        matches = sorted(_glob.glob(pat))
        if matches:
            for m in matches:
                p = Path(m)
                if p not in seen:
                    seen.add(p)
                    out.append(p)
        else:
            # Treat as a literal path even if it doesn't glob (let downstream
            # surface the missing-file error consistently with run.py).
            p = Path(pat)
            if p not in seen:
                seen.add(p)
                out.append(p)
    return out


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="CraftBench product-neutral two-pool batch orchestrator (spec §6)."
    )
    # --- mirrors run.py ---
    p.add_argument(
        "--model", required=True, help="Adapter/product slug, e.g. 'aura-agent:claude-sonnet-4-6'"
    )
    p.add_argument("--ue-root", required=True, help="Path to the UE 5.8 install root")
    p.add_argument(
        "--substrate-root", type=Path, default=DEFAULT_SUBSTRATE,
        help=f"Substrate root (default: {DEFAULT_SUBSTRATE})",
    )
    p.add_argument(
        "--run-dir", type=Path, default=None,
        help="Where to put run artefacts (default: runs/<backend>/ — the same "
             "per-backend folder run.py defaults to; explicit values are used "
             "as-is).",
    )
    p.add_argument("--max-turns", type=int, default=40, help="Agent tool-use loop cap (default: 40)")
    p.add_argument("--timeout", type=int, default=600, help="Per-agent-run timeout seconds (default: 600)")
    p.add_argument(
        "--live-project", action="store_true",
        help="Run against the LIVE substrate project (required for aura-*).",
    )
    # --- batch-only ---
    p.add_argument(
        "--tasks", nargs="+", required=True,
        help="Glob or explicit list of task .md paths (e.g. tasks/gp-*.md).",
    )
    p.add_argument(
        "--concurrency", type=int, default=5,
        help="Pool-A agent concurrency request (capped by env.max_concurrency).",
    )
    p.add_argument(
        "--verify-concurrency", type=int, default=1,
        help="Pool-B verification concurrency (default: 1).",
    )
    p.add_argument(
        "--no-tui", action="store_true",
        help="Run headless — do not launch the live TUI (CI / unattended).",
    )
    return p.parse_args(argv)


def build_tasks_for_cli(args: argparse.Namespace) -> List[BatchTask]:
    """Turn CLI args into BatchTask objects (one per expanded task .md).

    The ``payload`` carries a run.py-shaped argv namespace so the chosen
    ``Environment.run_one`` can reuse ``run.py::_run_live_project`` unchanged
    for aura-*, or ``workspace.build_workspace`` for claude-p.
    """
    task_paths = _expand_tasks(args.tasks)
    tasks: List[BatchTask] = []
    for task_path in task_paths:
        task_id = task_path.stem
        run_id = make_run_id(task_id, args.model)
        # The argv namespace run.py::_run_live_project expects (spec §6.1 reuse).
        run_args = argparse.Namespace(
            task=task_path,
            model=args.model,
            ue_root=args.ue_root,
            substrate_root=args.substrate_root,
            run_dir=args.run_dir,
            max_turns=args.max_turns,
            timeout=args.timeout,
            live_project=args.live_project,
        )
        tasks.append(
            BatchTask(
                task_id=task_id,
                run_id=run_id,
                product=args.model,
                max_steps=args.max_turns,
                timeout_s=args.timeout,
                payload={
                    "args": run_args,
                    "run_id": run_id,
                    "run_dir": args.run_dir / run_id,
                    "task_path": task_path,
                },
            )
        )
    return tasks


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint. Selects the Environment for the product, builds the verify
    seam, and drives the async scheduler. Returns 0 on a clean batch run."""
    from adapters.registry import make_adapter  # local: keeps import cheap

    args = parse_args(argv)
    if args.run_dir is None:
        # run.py owns the per-backend folder rule (runs/<backend>/) — one
        # source so the two producers can't drift.
        from run import _default_run_root
        args.run_dir = _default_run_root(args.model)
    env = for_product(args.model)
    tasks = build_tasks_for_cli(args)
    if not tasks:
        print("ERROR: no tasks matched --tasks patterns.", file=sys.stderr)
        return 4

    def task_path_for(task: BatchTask) -> Path:
        return task.payload["task_path"]

    def submission_dir_for(task: BatchTask) -> Path:
        return task.payload["run_dir"] / "submission"

    verify = make_default_verify(
        task_path_for=task_path_for,
        submission_dir_for=submission_dir_for,
        ue_root=args.ue_root,
    )

    cancellation = Cancellation()

    # SIGINT → cooperative cancel (spec §6.5).
    import signal

    def _on_sigint(_signum, _frame):
        print("\nCancellation requested — draining in-flight tasks...", file=sys.stderr, flush=True)
        cancellation.cancel()

    try:
        signal.signal(signal.SIGINT, _on_sigint)
    except (ValueError, OSError):
        pass  # not on the main thread (e.g. tests) — skip

    # NOTE: --no-tui is honored here by simply not launching the TUI; the TUI
    # extension (tools/dashboard/tui.py) reads the disk contract independently
    # (spec §8) and is out of this module's scope.
    asyncio.run(
        run_batch(
            tasks,
            env=env,
            make_adapter=make_adapter,
            verify=verify,
            concurrency=args.concurrency,
            verify_concurrency=args.verify_concurrency,
            run_root=args.run_dir,
            cancellation=cancellation,
            disk_settle=lambda: asyncio.sleep(2.0),  # UE asset saves can lag (spec §6.3)
        )
    )

    # Batch pass-rate summary. SUBSTRATE-REJECT / SANDBOX-REJECT / TIMEOUT /
    # errors are EXCLUDED from the denominator (verifier-noise, not agent FAIL).
    summary = summarize_verdicts(_collect_result_verdicts(tasks, args.run_dir))
    rate = summary["pass_rate"]
    rate_s = f"{rate * 100:.1f}%" if rate is not None else "n/a (0 graded)"
    print(
        f"\nBatch summary: {summary['n_pass']}/{summary['n_graded']} graded PASS "
        f"({rate_s}); {summary['n_excluded']} excluded {summary['excluded_by_verdict']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
