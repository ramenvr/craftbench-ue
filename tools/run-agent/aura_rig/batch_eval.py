"""batch_eval — the ``cb batch-eval`` command (aura-product-eval, design §5).

Takes a folder of **already-isolated submission directories** (each one a
writable-tree overlay named by its task id), pairs each with its task spec, and
runs the EXISTING deterministic verifier ``tools/verify-single/run_task.py``
over all of them **in parallel**. ``--references`` mode swaps the discovery:
instead of an outputs folder it grades every discovered task's OWN reference
solution (folder-local ``reference/`` or the legacy
``tests/reference-solutions/<id>/`` — :func:`discover_reference_submissions`). It
REIMPLEMENTS NO verify logic — every leg shells the same cold-UE ``run_task.py``
``run_batch.py``'s Pool-B grader uses, in its OWN cold process (each verify
``mkdtemp``s a private workdir → copies the substrate → L1 double-target build →
L2 PIE in a headless editor; concurrent verifies share NO mutable state).

Two independent gates bound concurrency on the 26 GB dev Mac (design §5.3):

  * an ``asyncio.Semaphore(verify_concurrency)`` — the same Pool-B width knob
    ``run_batch`` exposes via ``--verify-concurrency`` (default kept small);
  * a :class:`aura_rig.mem_gate.MemGate` slot — admits while memory pressure is
    normal, BLOCKS the (k+1)-th cold verify under WARN/CRITICAL pressure, so the
    batch can never OOM-thrash the box (≈ ~8 GB editor + UBT RAM per verify →
    safe ~2-wide).

The blocking pieces — the per-submission verify subprocess AND the synchronous
``MemGate.acquire_slot()`` context manager — run OFF the event loop via
``run_in_executor`` (mirroring ``run_batch.make_default_verify``), so the async
scheduler stays responsive and a slow verify never wedges its peers.

Every external seam is INJECTED (the verify callable, the mem-gate, the clock),
so the whole module is unit-testable with NO Unreal editor, NO Aura, NO real
memory reads, NO network — exactly how the sibling ``run_batch`` / ``mem_gate``
suites do it.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import functools
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence

# Self-relative imports (the package uses sys.path injection, mirroring cb.py /
# run_batch.py — both spellings resolve depending on the entry point).
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import mem_gate, tasks, workdir_retention  # noqa: E402

# adapters.base lives one level up (tools/run-agent/adapters); both run_batch and
# the adapters import it the same way.
from adapters.base import (  # noqa: E402
    is_graded_verdict,
    pass_rate,
    verdict_from_verifier,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
VERIFIER = REPO_ROOT / "tools" / "verify-single" / "run_task.py"
DEFAULT_RUN_SUBDIR = "aura-product-eval"

# Default Pool-B width. Kept conservative — the mem-gate is the real OOM guard,
# but a small default semaphore matches design §5.4 (realistic gain at K=2 ≈
# 1.3–1.5× because UBT's global -waitmutex serializes the compile phases anyway).
DEFAULT_VERIFY_CONCURRENCY = 1  # serial by default: 2-wide full-RHI L2 PIE editors contend and can
                                # spuriously FAIL an L1-passing solution on a <=32 GB host (and the
                                # mem-gate back-off is off on Windows-without-psutil). Raise on >32 GB.


# =============================================================================
# Submission discovery + task pairing (pure over the filesystem)
# =============================================================================

@dataclass
class Submission:
    """One isolated submission directory paired with its resolved task spec.

    ``submission_dir`` is the on-disk overlay (e.g. ``outputs/<task_id>/``);
    ``task_id`` is the directory name (the value ``tasks.resolve_task_path``
    takes); ``task_spec`` is the resolved ``tasks/<...>/<id>.md`` path, or None
    when no spec matched (the submission is reported UNPAIRED, never silently
    dropped)."""

    task_id: str
    submission_dir: Path
    task_spec: Optional[Path]

    @property
    def paired(self) -> bool:
        return self.task_spec is not None


def discover_submissions(
    outputs_dir: Path,
    repo: Path = REPO_ROOT,
    *,
    resolve: Optional[Callable[[Path, str], Optional[Path]]] = None,
) -> List[Submission]:
    """Enumerate the immediate sub-directories of ``outputs_dir`` as submissions.

    Each child dir is one submission; its name is the task id, resolved to a spec
    via ``tasks.resolve_task_path`` (set-aware: accepts a bare id, ``set/id``, or
    a unique subdir match). Dotfiles and non-dirs are skipped. Order is stable
    (sorted by id) so reports are deterministic. ``resolve`` is injected so the
    pairing is unit-testable without a real ``tasks/`` tree; it is looked up
    lazily off the module so a test can monkeypatch ``tasks.resolve_task_path``."""
    if resolve is None:
        resolve = tasks.resolve_task_path
    if not outputs_dir.is_dir():
        return []
    out: List[Submission] = []
    for child in sorted(outputs_dir.iterdir(), key=lambda p: p.name):
        if not child.is_dir() or child.name.startswith("."):
            continue
        task_id = child.name
        spec = resolve(repo, task_id)
        out.append(Submission(task_id=task_id, submission_dir=child, task_spec=spec))
    return out


def discover_reference_submissions(
    repo: Path = REPO_ROOT,
    target: str = "all",
) -> List[Submission]:
    """Enumerate every discovered task's reference solution as a submission.

    The ``--references`` sibling of :func:`discover_submissions` (same record
    shape, one :class:`Submission` per task): each task ``tasks.discover`` finds
    whose ``tasks.reference_dir`` resolves (folder-local ``reference/`` first,
    legacy ``tests/reference-solutions/<bare id>/`` fallback) yields a record
    whose ``submission_dir`` IS that reference dir, paired with its own spec.
    ``target`` is ``"all"`` or one set name (``root`` for the top-level
    ``tasks/*.md``); an unknown set yields []. Tasks without a reference are
    skipped (nothing to grade). Order follows ``tasks.discover`` (root first,
    then sets alphabetically; tasks by id) so reports are deterministic."""
    repo = Path(repo)
    out: List[Submission] = []
    for set_name, infos in tasks.discover(repo).items():
        if target not in ("all", set_name):
            continue
        for info in infos:
            # Set-qualify non-root ids so a bare id shared by two sets can never
            # resolve ambiguous (and per-submission report stems stay unique).
            tid = info.id if set_name == "root" else f"{set_name}/{info.id}"
            ref = tasks.reference_dir(repo, tid)
            if ref is None:
                continue
            out.append(Submission(task_id=tid, submission_dir=ref,
                                  task_spec=info.path))
    return out


# =============================================================================
# Per-submission verify result + the default shelling verify (reuse run_task.py)
# =============================================================================

@dataclass
class EvalResult:
    """The outcome of grading ONE submission (one row in summary.json)."""

    task_id: str
    submission_dir: str
    overall: Optional[str]            # PASS / FAIL / SUBSTRATE-REJECT / ... / None
    wall_s: float
    layers: Dict[str, Any] = field(default_factory=dict)   # per-layer status from report.json
    error: Optional[str] = None       # set on an UNPAIRED submission or a verify crash
    report_path: Optional[str] = None  # where the per-submission report.json landed
    workdir: Optional[str] = None     # kept verifier workdir (--keep mode only)
    # What workdir retention did to that kept workdir: the dict
    # workdir_retention.apply returns (mode / reclaimed_bytes / elapsed_s, plus
    # `reason` when a guard refused). None when no workdir was kept (nothing to
    # reclaim) or the verify callable is a test fake. A REFUSAL is a correct
    # outcome, not an incident — recording the reason here is how the operator
    # learns why a leg still costs 5.54 GB.
    retention: Optional[Dict[str, Any]] = None

    @property
    def graded(self) -> bool:
        return is_graded_verdict(self.overall)


# A verify callable: (submission, report_json_path) -> (overall, layers_dict).
# Injected so the unit suite passes a FAKE and never shells a real cold UE.
VerifyFn = Callable[[Submission, Path], "tuple[Optional[str], Dict[str, Any]]"]


def _short_workdir(key: str) -> Path:
    """A SHORT verifier workdir under the machine wd root (CRAFTBENCH_WD_ROOT
    override, else ``<cb_root>/wd`` — see aura_rig.paths), keyed by a stable
    hash — the same MAX_PATH dodge driver.grade uses."""
    import hashlib
    from aura_rig import paths as cb_paths
    root = cb_paths.wd_root()
    root.mkdir(parents=True, exist_ok=True)
    return root / hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def make_default_verify(
    *,
    ue_root: str,
    py_exe: Optional[str] = None,
    py_pre: Sequence[str] = (),
    from_live: bool = False,
    warm_cache: bool = False,
    keep_workdir: bool = False,
    workdir_key: Optional[str] = None,
    retention: Optional[str] = None,
    run_subprocess: Callable[..., Any] = subprocess.run,
    repo_root: Path = REPO_ROOT,
    verifier: Path = VERIFIER,
) -> VerifyFn:
    """Build the production verify callable that shells ``run_task.py`` per leg.

    Each call spawns a SEPARATE cold UE process (it never touches a live editor),
    writing its report.json to the caller-provided path so the batch keeps every
    per-submission report. The verdict is mapped exactly as ``run_batch`` does it
    (exit 3/4 → SUBSTRATE/SANDBOX-REJECT, else report.json's authoritative
    ``overall``). ``run_subprocess`` is injectable so the unit suite never shells.

    ``from_live`` adds ``--substrate-from-live`` (the WIP path ``cb discriminate``
    uses when a task's fixtures are uncommitted); the default grades from git HEAD
    for determinism (repo convention).

    ``warm_cache`` adds ``--warm-cache``: each verify tries to grab a free warm
    pool slot (prebuilt Intermediate/Binaries at a stable path) so L1 builds
    incrementally instead of cold. With N pool slots, up to N concurrent verifies
    run warm; extras (or a missing/stale pool) fall back to cold automatically —
    so it's always safe to pass and never changes a verdict.

    ``keep_workdir`` (``cb batch-eval --keep``) adds ``--keep-workdir`` plus a
    SHORT per-submission ``--workdir`` under the machine wd root
    (CRAFTBENCH_WD_ROOT, else ``<cb_root>/wd``) keyed by ``workdir_key`` + the
    task id, so the graded project tree survives for inspection. The path is
    exposed via the callable's ``workdir_for(sub)`` attribute so the row
    result can record it.

    ``retention`` is the workdir retention MODE for those kept workdirs
    (``None`` → env ``CB_WORKDIR_RETENTION`` → the ``"slim"`` default). It
    matters only in ``keep_workdir`` mode — without ``--workdir`` the verifier
    grades in a self-deleting tempdir (or a warm slot) and there is nothing here
    to reclaim. Measured 2026-07-25: each kept workdir is 5.54 GB, 4.72 GB of it
    ``Intermediate/Build/Win64/x64``, so a 15-task ``cb batch-eval --keep`` costs
    ~83 GB of which ~71 GB is compiler byproduct nobody reads. The reclaim is a
    SEPARATE ``retain(sub, report_json)`` attribute rather than part of
    ``_verify``, so ``_grade_one`` can run it once the leg's ``wall_s`` clock has
    stopped — a multi-GB delete folded into a row's wall time would silently
    inflate a number the summary and the per-leg log both publish."""
    exe = py_exe or sys.executable

    def _workdir_for(sub: Submission) -> Optional[Path]:
        if not keep_workdir:
            return None
        return _short_workdir(f"{workdir_key or 'batch-eval'}-{sub.task_id}")

    def _retain(sub: Submission, report_json: Path) -> Optional[Dict[str, Any]]:
        """Apply the retention mode to this leg's KEPT workdir; return the
        apply() record (None when the leg kept no workdir of ours).

        Called by ``_grade_one`` AFTER the verdict is in and the leg's report
        has been read — ``--report-json`` already put that report run-side
        (``run_root/<task>.report.json``), so by here nothing in the batch still
        needs the workdir. The report is re-read WHOLE (:func:`_load_report`)
        because apply()'s "never slim a failed L1" guard needs the nested
        ``layers.L1.status`` that :func:`_read_layers` flattens away."""
        wd = _workdir_for(sub)
        if wd is None:
            return None
        # warm=False is a FACT here, not an assumption: run_task.py forces a
        # cold build whenever --workdir is passed ("warm-cache ignored (forced
        # cold by --workdir …)", run_task.py:1386), and a workdir only exists
        # here because we put --workdir on that command line. So this path can
        # never be handed a shared warm_cache SLOT, whose Intermediate/ +
        # Binaries/ ARE the 5x-L1 cache.
        return workdir_retention.apply(wd, retention,
                                       report=_load_report(report_json),
                                       warm=False)

    def _verify(sub: Submission, report_json: Path) -> "tuple[Optional[str], Dict[str, Any]]":
        cmd: List[str] = [
            exe, *py_pre, str(verifier),
            "--task", str(sub.task_spec),
            "--submission", str(sub.submission_dir),
            "--ue-root", ue_root,
            "--report-json", str(report_json),
        ]
        if from_live:
            cmd.append("--substrate-from-live")
        if warm_cache:
            cmd.append("--warm-cache")
        wd = _workdir_for(sub)
        if wd is not None:
            cmd += ["--keep-workdir", "--workdir", str(wd)]
        completed = run_subprocess(
            cmd, cwd=str(repo_root), capture_output=True, text=True
        )
        stdout = getattr(completed, "stdout", "") or ""
        returncode = getattr(completed, "returncode", None)
        overall = verdict_from_verifier(returncode, stdout)
        layers = _read_layers(report_json)
        return overall, layers

    _verify.workdir_for = _workdir_for  # row-result surfacing (--keep mode)
    _verify.retain = _retain            # the post-verdict workdir reclaim
    return _verify


def _load_report(report_json: Path) -> Optional[Dict[str, Any]]:
    """The WHOLE report.json body, or None when it is absent/unparseable.

    Retention's "never slim a failed L1" guard reads
    ``report["layers"]["L1"]["status"]``, and :func:`_read_layers` has already
    FLATTENED that to ``{"L1": "pass"}`` — handing the flat map to
    ``workdir_retention.apply`` would read as ``l1_missing`` and refuse every
    reclaim on the planet while looking like it worked. So the file is re-read
    whole (a few KB, once per leg, already off the event loop) rather than
    reconstructed from the flattened view."""
    try:
        data = json.loads(report_json.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _read_layers(report_json: Path) -> Dict[str, Any]:
    """Pull a compact ``{layer: status}`` map out of a report.json (best effort)."""
    try:
        data = json.loads(report_json.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return {}
    layers = data.get("layers")
    if not isinstance(layers, dict):
        return {}
    out: Dict[str, Any] = {}
    for name, body in layers.items():
        out[name] = body.get("status") if isinstance(body, dict) else body
    return out


# =============================================================================
# Summary aggregation (pure)
# =============================================================================

def summarize(results: Sequence[EvalResult], *, label: str, wall_s: float) -> Dict[str, Any]:
    """Aggregate per-submission results into the summary.json body.

    The pass-rate DENOMINATOR is the count of GRADED verdicts (PASS/FAIL) only —
    SUBSTRATE-REJECT / SANDBOX-REJECT / UNPAIRED / errors are verifier-noise or
    harness conditions and are EXCLUDED so they can never be silently relabelled
    an agent FAIL (the same rule ``run_batch.summarize_verdicts`` enforces). The
    excluded outcomes are still counted per-kind so they stay visible."""
    verdicts = [r.overall for r in results]
    graded = [v for v in verdicts if is_graded_verdict(v)]
    n_pass = sum(1 for v in graded if v == "PASS")
    excluded: Dict[str, int] = {}
    for v in verdicts:
        if not is_graded_verdict(v):
            excluded[v if v is not None else "None"] = excluded.get(
                v if v is not None else "None", 0) + 1
    return {
        "label": label,
        "wall_s": round(wall_s, 1),
        "n_total": len(results),
        "n_graded": len(graded),
        "n_pass": n_pass,
        "n_fail": len(graded) - n_pass,
        "pass_rate": pass_rate(verdicts),  # None when nothing graded
        "n_excluded": len(results) - len(graded),
        "excluded_by_verdict": excluded,
        "results": [
            {
                "task_id": r.task_id,
                "submission_dir": r.submission_dir,
                "overall": r.overall,
                "wall_s": round(r.wall_s, 1),
                "layers": r.layers,
                "error": r.error,
                "report": r.report_path,
                "workdir": r.workdir,
                "retention": r.retention,
            }
            for r in results
        ],
    }


# =============================================================================
# The GATE verdict — ONE function owning both the exit code and the words
# =============================================================================

# Exit-code convention, matched to the rest of the repo so a CI author never has
# to guess per-command: 2 = USAGE (bad flags / missing UE / a failed envgate —
# see cmd_batch_eval's early returns), 1 = a REAL failure,
# 0 = the thing the caller asked for held. `discriminate.overall_exit_code` is
# the closest sibling and uses exactly this shape (`0 if outcomes and
# all(...) else 1` — note that an EMPTY outcome list is a 1 there too).
EXIT_OK = 0
EXIT_GATE_FAILED = 1
EXIT_USAGE = 2


def gate_result(summary: Dict[str, Any], *, allow_fail: bool = False) -> "tuple[int, str]":
    """Return ``(exit_code, verdict_clause)`` for a finished batch — the SINGLE
    source of truth for "did the gate hold?".

    Both the CLI's printed summary line and its process exit code come from this
    one call, so they CANNOT disagree. That was the 2026-07-25 defect: on the
    testbed ``cb batch-eval --references all`` printed ``0/15 graded PASS
    (0.0%)`` — a total wipeout of the set README.md advertised at the time as
    "the 15/15 regression gate" — and still exited 0, because ``main`` ended in a bare
    ``return 0`` and ``cb.py`` deliberately graded only HARNESS health. A gate
    that returns success on a total wipeout cannot gate anything.

    The rules:
      * ``n_fail > 0``  -> EXIT_GATE_FAILED. A graded FAIL is the failure this
        command exists to catch; "it's a legitimate grading outcome, not a
        harness error" is true and irrelevant to a gate.
      * ``n_graded == 0`` -> EXIT_GATE_FAILED, ALWAYS (``--no-gate`` does not
        relax it). An empty gate is not a passing gate: zero graded verdicts
        means the verifier never rendered judgement on anything (no submissions
        discovered, every leg crashed, every verdict a REJECT), which is exactly
        the silent-green failure mode that hides a broken machine.
      * everything graded passed -> EXIT_OK. Non-graded EXCLUDED rows
        (SUBSTRATE-REJECT / SANDBOX-REJECT / UNPAIRED / crash) stay out of the
        verdict here for the same reason ``summarize`` keeps them out of the
        pass-rate denominator — they are verifier noise, never relabelled an
        agent FAIL. They are still printed, and a machine sick enough to reject
        EVERYTHING lands on the ``n_graded == 0`` rule above.

    ``allow_fail`` (``--no-gate``) restores the PRE-fix cb.py semantics —
    "exit code reflects HARNESS success only" — for the measurement use of this
    command (point it at a folder of real agent submissions and FAILs are the
    expected data, not a red build). No caller in-tree needs it today (surveyed
    2026-07-25: no CI workflow, no shell/PowerShell script, and `cb smoke` runs
    run_task.py directly, never batch-eval), so it is an explicit opt-out rather
    than the default."""
    n_graded = int(summary.get("n_graded") or 0)
    n_fail = int(summary.get("n_fail") or 0)
    n_pass = int(summary.get("n_pass") or 0)
    if n_graded == 0:
        return EXIT_GATE_FAILED, (
            "GATE FAILED: 0 graded verdicts — nothing was actually judged "
            "(an empty gate is not a passing gate)")
    if n_fail:
        if allow_fail:
            return EXIT_OK, (
                f"NOT GATED: {n_fail}/{n_graded} graded FAIL, exit 0 forced by "
                "--no-gate (measurement mode)")
        return EXIT_GATE_FAILED, f"GATE FAILED: {n_fail}/{n_graded} graded FAIL"
    return EXIT_OK, f"GATE OK: {n_pass}/{n_graded} graded PASS"


# =============================================================================
# The parallel scheduler (Pool-B semaphore + mem-gate slot)
# =============================================================================

async def run_batch_eval(
    submissions: Sequence[Submission],
    *,
    verify: VerifyFn,
    run_root: Path,
    label: str,
    gate: Optional[mem_gate.MemGate] = None,
    verify_concurrency: int = DEFAULT_VERIFY_CONCURRENCY,
    clock: Callable[[], float] = None,
    log: Callable[[str], None] = print,
) -> List[EvalResult]:
    """Grade every submission in parallel, bounded by BOTH the Pool-B semaphore
    and the memory-pressure mem-gate. Returns one :class:`EvalResult` per input.

    Concurrency model (design §5.2-§5.3):
      * ``asyncio.Semaphore(verify_concurrency)`` caps in-flight verifies (the
        Pool-B width knob).
      * the :class:`MemGate` slot (default ``max_slots`` matched to the semaphore)
        ADMITS while pressure is normal and BLOCKS under WARN/CRITICAL → no OOM.
      * the blocking verify subprocess AND the synchronous ``gate.acquire_slot()``
        run in a thread (``run_in_executor``) so the loop stays responsive.

    Per-submission failure isolation: an UNPAIRED submission (no task spec) or a
    verify crash resolves to its OWN error result and NEVER sinks the batch
    (``asyncio.gather(return_exceptions=True)`` + per-coroutine try/except)."""
    clock = clock or _monotonic
    width = max(1, int(verify_concurrency))
    sem = asyncio.Semaphore(width)
    # The mem-gate defaults to the same width as the semaphore so the two agree;
    # the gate adds the pressure dimension the bare semaphore lacks.
    gate = gate or mem_gate.MemGate(max_slots=width)

    run_root = Path(run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    log(f"  [batch-eval] {len(submissions)} submission(s), "
        f"verify_concurrency={width}, mem_gate max_slots={gate.max_slots}")

    async def _guarded(sub: Submission) -> EvalResult:
        async with sem:
            return await _grade_one(sub, verify=verify, gate=gate,
                                    run_root=run_root, clock=clock, log=log)

    gathered = await asyncio.gather(
        *[_guarded(s) for s in submissions], return_exceptions=True)

    results: List[EvalResult] = []
    for sub, g in zip(submissions, gathered):
        if isinstance(g, EvalResult):
            results.append(g)
        else:  # an exception escaped _grade_one's own guard — never block peers
            results.append(EvalResult(
                task_id=sub.task_id, submission_dir=str(sub.submission_dir),
                overall=None, wall_s=0.0,
                error=f"unhandled {type(g).__name__}: {g}"))
    return results


async def _grade_one(
    sub: Submission,
    *,
    verify: VerifyFn,
    gate: mem_gate.MemGate,
    run_root: Path,
    clock: Callable[[], float],
    log: Callable[[str], None],
) -> EvalResult:
    """Grade ONE submission behind the mem-gate slot. Errors are contained here."""
    report_json = run_root / f"{_safe(sub.task_id)}.report.json"
    if not sub.paired:
        log(f"  [batch-eval] UNPAIRED {sub.task_id} — no task spec; skipping verify")
        return EvalResult(
            task_id=sub.task_id, submission_dir=str(sub.submission_dir),
            overall=None, wall_s=0.0,
            error=f"no task spec resolved for '{sub.task_id}'")

    t0 = clock()
    try:
        # Run the (blocking) mem-gate acquire + cold verify OFF the event loop so
        # the async scheduler keeps moving. The gate's acquire_slot() context
        # manager blocks under memory pressure; the verify subprocess is the
        # ≈ 8 GB editor — both must live in the executor thread.
        overall, layers = await asyncio.get_event_loop().run_in_executor(
            None, functools.partial(_gated_verify, sub, verify, gate, report_json))
        wall_s = clock() - t0
        log(f"  [batch-eval] {sub.task_id}: {overall}  ({wall_s:.1f}s)")
        # --keep mode: the default verify exposes workdir_for(sub) — record the
        # kept verifier workdir in the row (None for fakes / non-keep runs).
        wd_fn = getattr(verify, "workdir_for", None)
        kept_wd = wd_fn(sub) if callable(wd_fn) else None
        # Workdir retention — the 4.72 GB of .obj this leg no longer needs.
        # Deliberately AFTER the clock stopped and after the verdict was
        # logged: the delete is bookkeeping, and folding it into wall_s would
        # inflate a number summarize() publishes per row. Still in the executor
        # (a real slim pass unlinks tens of thousands of files) so it cannot
        # stall the event loop that is scheduling the other legs, and OUTSIDE
        # the mem-gate slot, which exists for the ~8 GB editor, not for unlink.
        # getattr-guarded exactly like workdir_for: the unit suite's fake
        # verifies expose neither attribute.
        retain = getattr(verify, "retain", None)
        retention = None
        if callable(retain):
            try:
                retention = await asyncio.get_event_loop().run_in_executor(
                    None, functools.partial(retain, sub, report_json))
            except Exception as exc:  # noqa: BLE001 — see below
                # Its OWN guard, INSIDE the verdict's try block: the enclosing
                # handler turns any escape into an error row with overall=None,
                # which would let a failed unlink discard a real PASS and drop
                # the leg out of the pass-rate denominator. A verdict is never
                # worth 4.72 GB. (workdir_retention.apply already contracts to
                # never raise — this covers the seam itself, e.g. an injected
                # retain or an OSError resolving the wd-root.)
                log(f"  [batch-eval] {sub.task_id}: retention skipped — {exc!r}")
        return EvalResult(
            task_id=sub.task_id, submission_dir=str(sub.submission_dir),
            overall=overall, wall_s=wall_s, layers=layers,
            report_path=str(report_json) if report_json.exists() else None,
            workdir=str(kept_wd) if kept_wd is not None else None,
            retention=retention)
    except Exception as exc:  # noqa: BLE001 — per-submission isolation
        wall_s = clock() - t0
        log(f"  [batch-eval] {sub.task_id}: ERROR — {exc!r}")
        return EvalResult(
            task_id=sub.task_id, submission_dir=str(sub.submission_dir),
            overall=None, wall_s=wall_s, error=repr(exc))


def _gated_verify(
    sub: Submission,
    verify: VerifyFn,
    gate: mem_gate.MemGate,
    report_json: Path,
) -> "tuple[Optional[str], Dict[str, Any]]":
    """Acquire a mem-gate slot, run the verify, release. Runs in an executor
    thread (the gate is thread-based by design — see mem_gate)."""
    with gate.acquire_slot():
        return verify(sub, report_json)


# =============================================================================
# Helpers
# =============================================================================

def _monotonic() -> float:
    import time
    return time.monotonic()


def _safe(name: str) -> str:
    """Filesystem-safe report stem (set-qualified ids carry a '/')."""
    return name.replace("/", "__").replace("\\", "__")


def make_run_dir(run_root: Path, label: str,
                 now: Optional[Callable[[], str]] = None) -> Path:
    """``runs/aura-product-eval/<label>-<ts>/`` (created by the caller)."""
    ts = now() if now is not None else _dt.datetime.now(
        _dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Path(run_root) / DEFAULT_RUN_SUBDIR / f"{_safe(label)}-{ts}"


def write_summary(run_dir: Path, summary: Dict[str, Any]) -> Path:
    """Write summary.json into the run dir (atomically) and return its path."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "summary.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return path


# =============================================================================
# Top-level entry (the bit cb.py shells / calls)
# =============================================================================

def run(
    outputs_dir: Optional[Path],
    *,
    ue_root: str,
    repo: Path = REPO_ROOT,
    runs_root: Optional[Path] = None,
    label: str = "batch-eval",
    verify_concurrency: int = DEFAULT_VERIFY_CONCURRENCY,
    py_exe: Optional[str] = None,
    py_pre: Sequence[str] = (),
    from_live: bool = False,
    warm_cache: bool = False,
    keep_workdir: bool = False,
    retention: Optional[str] = None,
    references: Optional[str] = None,
    verify: Optional[VerifyFn] = None,
    gate: Optional[mem_gate.MemGate] = None,
    log: Callable[[str], None] = print,
) -> Dict[str, Any]:
    """Discover, grade, and summarize a folder of submissions. Returns the summary.

    ``references`` (``"all"`` or a set name) switches discovery to every task's
    OWN reference solution (:func:`discover_reference_submissions`) — the
    ``cb batch-eval --references`` mode; ``outputs_dir`` is unused (may be None)
    then. ``retention`` is the workdir retention mode applied to each KEPT
    workdir (``keep_workdir`` only; None → env → the ``"slim"`` default) — see
    :func:`make_default_verify`. ``verify`` / ``gate`` are injectable for tests;
    in production they
    default to the cold-UE ``run_task.py`` shell + a live-pressure mem-gate. The
    summary.json and the per-submission report.json files land under
    ``<runs_root>/aura-product-eval/<label>-<ts>/``."""
    if references is not None:
        submissions = discover_reference_submissions(repo, references)
    else:
        outputs_dir = Path(outputs_dir)
        submissions = discover_submissions(outputs_dir, repo)
    if not submissions:
        if references is not None:
            log(f"  [batch-eval] no reference solutions discovered "
                f"(--references {references})")
        else:
            log(f"  [batch-eval] no submission directories under {outputs_dir}")
        return {"label": label, "n_total": 0, "results": [], "pass_rate": None,
                "n_graded": 0, "n_pass": 0, "n_fail": 0, "n_excluded": 0,
                "excluded_by_verdict": {}, "wall_s": 0.0}

    runs_root = Path(runs_root) if runs_root is not None else (repo / "runs")
    run_dir = make_run_dir(runs_root, label)
    run_dir.mkdir(parents=True, exist_ok=True)

    if verify is None:
        verify = make_default_verify(
            ue_root=ue_root, py_exe=py_exe, py_pre=py_pre, from_live=from_live,
            warm_cache=warm_cache, keep_workdir=keep_workdir,
            retention=retention, workdir_key=run_dir.name)

    t0 = _monotonic()
    results = asyncio.run(run_batch_eval(
        submissions, verify=verify, run_root=run_dir, label=label,
        gate=gate, verify_concurrency=verify_concurrency, log=log))
    wall_s = _monotonic() - t0

    summary = summarize(results, label=label, wall_s=wall_s)
    summary_path = write_summary(run_dir, summary)
    log(f"  [batch-eval] summary -> {summary_path}")
    return summary


# =============================================================================
# CLI (also runnable standalone: python -m aura_rig.batch_eval <outputs>)
# =============================================================================

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="batch-eval",
        description="Grade a folder of isolated submissions in parallel "
                    "(aura-product-eval, design §5).")
    p.add_argument("outputs", type=Path,
                   help="folder of submission dirs (each named by its task id)")
    p.add_argument("--ue-root", required=True, help="UE 5.8 install root")
    p.add_argument("--label", default="batch-eval", help="run label (report dir prefix)")
    p.add_argument("--verify-concurrency", type=int, default=DEFAULT_VERIFY_CONCURRENCY,
                   help=f"Pool-B verify width (default: {DEFAULT_VERIFY_CONCURRENCY})")
    p.add_argument("--from-live", action="store_true",
                   help="grade --substrate-from-live (WIP fixtures not yet committed)")
    p.add_argument("--warm-cache", action="store_true",
                   help="use the L1 warm pool (prime with build_warm_baseline.py --slots N); "
                        "up to N concurrent verifies run warm, extras fall back to cold")
    p.add_argument("--keep-workdir", action="store_true",
                   help="keep each verify's workdir (a short per-task dir under "
                        "the machine wd root — CRAFTBENCH_WD_ROOT, else "
                        "<cb_root>/wd; recorded per row in summary.json)")
    # No argparse `choices=` on --retention, deliberately: resolve_mode WARNs on
    # an unrecognised mode and falls back to the default rather than aborting —
    # losing a multi-hour 15-task batch to a typo'd retention word would cost far
    # more than the bytes the flag is about.
    p.add_argument("--retention", default=None,
                   help="what survives in each KEPT workdir: slim (default — drop "
                        "the ~4.7 GB compiler intermediate, keep Binaries/ + out/), "
                        "full (keep every byte), none (delete it). Only meaningful "
                        "with --keep-workdir. Env: CB_WORKDIR_RETENTION.")
    p.add_argument("--no-gate", "--allow-fail", action="store_true",
                   dest="allow_fail",
                   help="exit 0 even when graded submissions FAIL (measurement "
                        "mode: grading a folder of real agent outputs, where a "
                        "FAIL is data). 0 graded still exits 1 — an empty gate "
                        "is never a passing gate.")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    summary = run(
        args.outputs, ue_root=args.ue_root, label=args.label,
        verify_concurrency=args.verify_concurrency, from_live=args.from_live,
        warm_cache=args.warm_cache, keep_workdir=args.keep_workdir,
        retention=args.retention)
    rate = summary.get("pass_rate")
    rate_s = f"{rate * 100:.1f}%" if rate is not None else "n/a (0 graded)"
    # ONE gate_result call feeds BOTH the printed verdict and the return value,
    # so the line a human reads and the code a script branches on can never
    # disagree (2026-07-25: they did — "0/15 graded PASS" over exit 0).
    code, verdict = gate_result(summary, allow_fail=args.allow_fail)
    print(
        f"\nbatch-eval: {summary['n_pass']}/{summary['n_graded']} graded PASS "
        f"({rate_s}); {summary['n_excluded']} excluded "
        f"{summary['excluded_by_verdict']}\nbatch-eval: {verdict} "
        f"(exit {code})", flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
