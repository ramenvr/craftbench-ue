#!/usr/bin/env python3
"""tools/run-agent/run.py — CraftBench agent harness CLI (v0).

Usage:
    python3 tools/run-agent/run.py \\
        --task tasks/cpp/gp-glide-stamina-cpp/task.md \\
        --model claude-p:opus \\
        --ue-root "C:/Program Files/Epic Games/UE_5.8" \\
        [--keep-workspace] [--run-dir runs/<backend>/] [--max-turns 25] [--timeout 600]
        [--no-preflight]

Exit codes:
    0   overall PASS
    2   agent produced no edits (empty submission)
    3   verifier returned non-PASS
    4   harness error (task spec missing required section, etc.)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Self-relative imports (the package uses sys.path injection).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from adapters.base import (  # noqa: E402
    AgentResult,
    VERDICT_AGENT_CONFIG_ERROR,
    VERDICT_AGENT_TRANSPORT_ERROR,
    VERDICT_EDITOR_NOT_READY,
    VERDICT_FAIRNESS_BREACH,
    reasoning_policy_fields,
    verdict_from_verifier,
)
from adapters.registry import make_adapter  # noqa: E402
from aura_port import ensure_aura_client_port  # noqa: E402
from fairness import (  # noqa: E402
    heal_and_recheck, repo_hide_breaches, stage_config_overlay_apply, stage_fairness_hide,
    stage_generated_code_hide, stage_index_cache_hide,
    stage_fairness_restore, stage_repo_answer_hide, stage_task_isolation_hide,
    stage_task_tree_isolation_hide)
import leak_audit  # noqa: E402
from live_lock import LiveRunLockBusy, acquire_live_run_lock  # noqa: E402
from live_hygiene import quarantine_untracked_writable  # noqa: E402
from prompt_extract import extract_agent_visible_prompt  # noqa: E402
from snapshot import (  # noqa: E402
    SubmissionRule, collect_submission, snapshot_submission)
from substrate_check import check_substrate_clean  # noqa: E402
from workspace import Workspace, build_workspace  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUBSTRATE = REPO_ROOT / "UE-projects/CraftBenchTemplate"
#: Resolved THROUGH any junction, because the run dir is the root of the
#: longest paths the harness builds and MAX_PATH is measured on the STRING,
#: not on the target. On the build machine `<repo>/runs` is a junction to a
#: short root such as `C:\cb\runs`:
#: the logical form is 46 chars longer than the physical one, and
#: `fairness.stage_*_hide` copies into
#: `<run_dir>/fairness_backup/<subdir>/<rel>`. With the logical form the worst
#: ThirdPerson fixture destination is 301 chars, so the answer-key hide dies
#: `WinError 3` MID-STUB — leaving the live tree half-stubbed and, because the
#: crash precedes `_persist_state`, no state file for the self-heal to read
#: (measured 2026-08-20; the dev box never saw it because its own worktree
#: root is already short). Resolving is a no-op when `runs/` is a real directory.
#: NOTE the margin is thin, not comfortable: resolved worst case is 255 of 260.
#: The durable fix is extended-length (`\\?\`) destinations in fairness.py,
#: which lifts the 260-char ceiling outright; this resolve is the cheap half.
DEFAULT_RUN_DIR = (REPO_ROOT / "runs").resolve()
VERIFIER = REPO_ROOT / "tools/verify-single/run_task.py"


def derive_substrate_root(task_path: Path, repo_root: Path = REPO_ROOT) -> Path:
    """The substrate root the TASK declares — the --substrate-root default.

    Only reached when the operator did NOT pass --substrate-root (an explicit
    flag always wins). Reads the spec's ``substrate:`` front-matter field via
    tools/verify-single's spec.py (the existing sys.path bridge) and maps it
    through run_task._substrate_dir_name (legacy alias ``template`` →
    CraftBenchTemplate; unknown names pass through, e.g. ThirdPersonTemplate).
    Falls back to DEFAULT_SUBSTRATE when the spec can't be parsed — the
    downstream prompt extraction reports the real error."""
    try:
        vs_dir = Path(__file__).resolve().parents[1] / "verify-single"
        if str(vs_dir) not in sys.path:
            sys.path.insert(0, str(vs_dir))
        import spec as _spec  # noqa: E402  (tools/verify-single)
        from run_task import _substrate_dir_name  # noqa: E402
        name = _substrate_dir_name(_spec.parse_task_file(Path(task_path)).substrate)
        return repo_root / "UE-projects" / name
    except Exception:
        return repo_root / "UE-projects" / "CraftBenchTemplate"


def _verifier_workdir(uniq: str):
    """The SHORT pinned verifier workdir for this run (Windows only; None on
    POSIX). On POSIX the verifier keeps its own SELF-DELETING tempdir — a
    pinned workdir there would leak a multi-GB built project every run that
    cb clean's KEEP set (runs/**/summary.json + result.json graded_workdir
    refs) was never designed to bound.
    Checkpoint-PNG retention comes from the pinned ``--out-dir`` instead
    (:func:`_verifier_out_dir`, design §5). Where the pin IS on (Windows),
    :func:`_write_result` records the surviving dir as ``graded_workdir`` in
    result.json so a later reader can find the built project."""
    if os.name != "nt":
        return None
    import hashlib
    # Resolve through aura_rig.paths — the single source of truth for the
    # machine-local roots (env CRAFTBENCH_WD_ROOT still wins inside wd_root();
    # the old C:\cbwd default is retired). cb.py's --prune-workdirs re-derives
    # this exact path, so the two sides MUST share the resolver.
    from aura_rig import paths as cb_paths
    root = cb_paths.wd_root()
    root.mkdir(parents=True, exist_ok=True)
    return root / hashlib.sha1(uniq.encode("utf-8")).hexdigest()[:10]


def _warm_cache_enabled() -> bool:
    """``CB_WARM_CACHE`` as a bool — the SAME opt-in ``driver.grade`` reads.

    OPT-IN ONLY, never a default, and that is a deliberate limit rather than an
    oversight: a warm slot is persistent state reused across runs (its
    ``Intermediate/`` and ``Binaries/`` survive by design), so a MEASURED eval —
    which is what this file runs — should start clean unless someone explicitly
    asks otherwise. Warm belongs to the token-free grading lane and to
    prompt/agent iteration, not to a run whose numbers anyone will quote.
    """
    return str(os.environ.get("CB_WARM_CACHE", "")).strip().lower() in (
        "1", "true", "yes", "on")


def _verifier_workdir_args(uniq: str) -> list:
    """How this run gets its workdir — pinned-and-cold, or the warm slot.

    The two are MUTUALLY EXCLUSIVE and returning them from one function is what
    keeps them that way: ``run_task`` treats an explicit ``--workdir`` as "force
    cold" (warm_cache.py), so passing both would silently disable warming and
    leave the caller believing it was on. Both verifier call sites in this file
    route through here, so neither can drift from the other.

    COLD (the default): on Windows, pin a SHORT, fresh ``--workdir``. The
    verifier defaults to ``tempfile.mkdtemp()`` under the long ``%TEMP%`` path;
    UE build paths then blow the 260-char MAX_PATH limit and the grade produces
    NO parseable report (-> ``verifier: null`` -> spurious FAIL). A short root
    keeps build paths under the limit. Honors ``CRAFTBENCH_WD_ROOT`` (default
    ``aura_rig.paths.wd_root()`` = ``<CB_ROOT>/wd``). No-op on POSIX, where long
    /tmp paths are fine and the tempdir stays self-deleting.

    WARM (``CB_WARM_CACHE=1``): pass ``--warm-cache`` and NO ``--workdir``. The
    slot is itself a short, path-stable root, so the MAX_PATH reason for pinning
    does not apply. Until this existed, ``run.py`` had no warm-cache handling at
    all — so ``cb eval`` on every baseline backend (claude-p / openrouter /
    unreal-mcp) built cold unconditionally, which is why a Sonnet-5 t0 eval spent
    87.2s of its 100.6s grade on a build the slot already had. A warm MISS falls
    back to cold inside run_task and can never change a verdict.
    """
    if _warm_cache_enabled():
        return ["--warm-cache"]
    wd = _verifier_workdir(uniq)
    return ["--workdir", str(wd)] if wd is not None else []


def _verifier_out_dir(run_dir: Path) -> Path:
    """The pinned verifier ``--out-dir`` for this run (all platforms).

    Layer logs, the default report and the --capture ``artifacts/`` sweep land
    here and OUTLIVE the verifier's self-deleting POSIX tempdir — the design §5
    POSIX sweep fix: baselines retain no workdir, so this is the only surviving
    source of checkpoint PNGs."""
    return run_dir / "verifier_out"


def _verifier_mode_args(args) -> list:
    """--visible / --capture passthrough to the verifier (opt-in; absent flags
    keep the verifier command byte-identical to today's)."""
    out = []
    if getattr(args, "visible", False):
        out.append("--visible")
    if getattr(args, "capture", False):
        out.append("--capture")
    return out


def _collect_artifacts(out_dir, run_dir: Path) -> list:
    """Copy the --capture screenshot sweep into ``<run_dir>/artifacts/`` and
    return the sorted run_dir-relative paths.

    Source of truth (design §5): the pinned ``report.json``'s ``artifacts``
    list — run-relative ``artifacts/<name>`` paths resolved against the
    ``--out-dir`` we passed the verifier. Falls back to globbing
    ``<out_dir>/artifacts/`` when the report is missing/keyless (older
    verifiers). No-op ([]) when the out dir is unknown or holds nothing."""
    if out_dir is None:
        return []
    out_dir = Path(out_dir)
    pairs = []  # (src, run-relative dst)
    try:
        report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
        listed = report.get("artifacts") or []
    except (OSError, ValueError, AttributeError):
        listed = []
    for rel in listed:
        # Containment:
        # a report-listed artifact path must stay INSIDE both the verifier
        # out-dir (read side) and the run bundle (write side). An absolute or
        # '..'-escaping entry is skipped — this is the run bundle's only
        # report-driven write, so it must never be unconfined.
        rel_path = Path(str(rel))
        if rel_path.is_absolute():
            continue
        src = out_dir / rel_path
        try:
            contained = (src.resolve().is_relative_to(Path(out_dir).resolve())
                         and (run_dir / rel_path).resolve().is_relative_to(
                             Path(run_dir).resolve()))
        except (OSError, ValueError):
            contained = False
        if contained and src.is_file():
            pairs.append((src, rel_path))
    if not pairs:
        src_root = out_dir / "artifacts"
        if src_root.is_dir():
            pairs = [(p, Path("artifacts") / p.relative_to(src_root))
                     for p in sorted(src_root.rglob("*")) if p.is_file()]
    copied = []
    for src, rel in pairs:
        dst = run_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel.as_posix())
    return sorted(set(copied))


def _apply_retention(run_id: str, args, report):
    """Reclaim the pinned verifier workdir — AFTER this run's evidence left it.

    Measured 2026-07-25 across a 21-run stress test: ONE kept workdir under
    ``C:\\cb\\wd\\<hash>`` is 5.54 GB, of which 4.72 GB is
    ``<Proj>/Intermediate/Build/Win64/x64`` (cl.exe .obj/.pch) and the genuinely
    diagnostic ``out/`` dir is ~0 GB. The same sweep found 24 workdirs holding
    121 GB against 128 GB free — ~23 more evals to a full disk — with no CLI
    path to reclaim: ``cb bench`` has ``--prune-workdirs``, ``cb eval`` (this
    file's entry point) has none, and ``cb clean --workdirs`` deliberately KEEPS
    every workdir a ``graded_workdir`` field names, i.e. exactly the ones a
    finished eval produces. Mode ``"slim"`` is the default (maintainer decision,
    2026-07-25): the .obj tree goes, the launchable ``Binaries/`` and the whole
    ``out/`` dir stay.

    ORDERING — load-bearing: both call sites run this AFTER
    :func:`_collect_artifacts` has copied the ``--capture`` PNGs into the run
    bundle, and the report was already pinned run-side by ``--report-json``.
    Reclaiming any earlier would delete the run's own evidence.

    It also sits deliberately OUTSIDE the ``verify_s`` window (measured around
    the verifier subprocess itself): folding a multi-GB delete into that number
    would silently inflate a dashboard-visible metric. The reclaim reports its
    own ``elapsed_s`` in the returned dict, which :func:`_write_result` stamps
    into result.json as ``retention``.

    Returns None when there is nothing to act on: POSIX (no pin at all — the
    verifier's tempdir self-deletes, see :func:`_verifier_workdir`) or a workdir
    that never materialized. That existence guard mirrors the ``graded_workdir``
    one in :func:`_write_result`. ``report`` is threaded through so apply()'s
    "never slim a failed L1" refusal can fire — a BROKEN BUILD is precisely when
    a human wants the .obj/.pch tree kept, because it is the evidence."""
    try:
        wd = _verifier_workdir(run_id)
        if wd is None or not Path(wd).is_dir():
            return None
        # Lazy import, same reason _verifier_workdir imports aura_rig.paths
        # lazily: run.py is entered directly (python3 tools/run-agent/run.py) as
        # well as through the installed `cb`, and the rig package resolves via
        # the sys.path injection at the top of this file.
        from aura_rig import workdir_retention
        # warm= is NOT auto-detected by apply() — the caller must say so. Under
        # CB_WARM_CACHE the graded workdir IS the shared warm slot, whose
        # Intermediate/ + Binaries/ ARE the path-bound UBT cache; slimming it
        # would delete the very thing that makes the next verify fast (and every
        # verify after it, since the pool is shared). apply() refuses on warm and
        # reports mode "full"/reason "warm_cache_pool".
        return workdir_retention.apply(wd, getattr(args, "retention", None),
                                       report=report,
                                       warm=_warm_cache_enabled(),
                                       log=lambda m: print(m, flush=True))
    except Exception as e:  # noqa: BLE001 — a reclaim must never cost the run
        # apply() already contracts to never raise; this covers everything
        # AROUND it (the lazy import in an odd checkout, an OSError resolving
        # the wd-root). It matters because this call sits BEFORE _write_result:
        # an escape here would cost the run its result.json — i.e. the whole
        # graded outcome — to save disk space. Warn and keep every byte.
        print(f"WARN: workdir retention skipped ({type(e).__name__}: {e}) — "
              f"the workdir is left intact", file=sys.stderr, flush=True)
        return None


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--task", required=True, type=Path,
                   help="Path to the task .md (e.g. tasks/cpp/gp-glide-stamina-cpp/task.md)")
    p.add_argument("--model", required=True,
                   help="Adapter slug, e.g. 'claude-p:opus'")
    p.add_argument("--ue-root", required=True,
                   help="Path to the UE 5.8 install root")
    p.add_argument("--substrate-root", type=Path, default=None,
                   help="Substrate to copy into the workspace. Default: derived "
                        "from the task spec's 'substrate:' front-matter field "
                        f"(falling back to {DEFAULT_SUBSTRATE}). An explicit "
                        "value always wins.")
    p.add_argument("--run-dir", type=Path, default=None,
                   help="Where to put run artefacts. Default: runs/<backend>/ — "
                        "each backend gets its own folder (runs/claude-p/, "
                        "runs/aura-mcp/, runs/unreal-mcp/, ...). "
                        "An explicit value is used as-is (cb matrix/bench pass "
                        "their own cell/rep dirs).")
    p.add_argument("--keep-workspace", action="store_true",
                   help="Don't tear down /tmp/run-agent-<id>/ after the run")
    p.add_argument("--keep", dest="keep_workspace", action="store_true",
                   help="Alias of --keep-workspace (the shared cb retention flag)")
    p.add_argument("--visible", action="store_true",
                   help="Forward --visible to the verifier: real-RHI L2/L2I legs "
                        "(visible PIE window) instead of -nullrhi. Opt-in; the "
                        "default stays headless-deterministic.")
    p.add_argument("--capture", action="store_true",
                   help="Forward --capture to the verifier: real RHI + the "
                        "-CraftBenchCapture screenshot hook; swept PNGs land in "
                        "<run_dir>/artifacts/.")
    # Deliberately NO argparse `choices=`: workdir_retention.resolve_mode WARNs
    # on an unrecognised value and falls back to the default, because killing a
    # 40-minute eval over a typo'd retention word is worse than the typo. An
    # argparse choices= here would re-introduce exactly that abort.
    p.add_argument("--retention", default=None,
                   help="What survives in the graded verifier workdir: 'slim' "
                        "(DEFAULT — drop the ~4.7 GB compiler intermediate, keep "
                        "Binaries/ + the whole out/ dir, so the project still "
                        "launches and still explains its verdict), 'full' (keep "
                        "every byte — the debugging escape hatch), 'none' "
                        "(delete the workdir). Env: CB_WORKDIR_RETENTION.")
    p.add_argument("--max-turns", type=int, default=0,
                   help="Agent tool-use loop cap (default: 0 = uncapped — the "
                        "--timeout wall clock governs; adapters whose loop has "
                        "no wall-clock deadline clamp 0 to a finite safety cap)")
    p.add_argument("--timeout", type=int, default=1200,
                   help="Per-agent-run WALL-CLOCK ceiling in seconds (default: 1200). "
                        "Enforced at each turn boundary by adapters.aura_mcp.run_loop; "
                        "before 2026-08-17 it bounded only per-tool waits, so a drive "
                        "measured at 2199s ran under a nominal 600s.")
    p.add_argument("--no-preflight", action="store_true",
                   help="Skip the A2 'open UE' handshake (CI/tests only)")
    p.add_argument("--skip-plugins", action="store_true",
                   help="Omit Plugins/ from the workspace copy. For baseline "
                        "backends (claude-p/openrouter) that edit source directly "
                        "and never open UE: avoids copying the Aura plugin's "
                        "bundled PortablePython (6k+ files, exceeds Windows MAX_PATH).")
    p.add_argument("--prepare-only", action="store_true",
                   help="Build workspace + prompt, print the path, exit. "
                        "For two-step runs: prepare → user opens UE → dispatch with --workspace.")
    p.add_argument("--workspace", type=Path, default=None,
                   help="Reuse an existing workspace root (e.g. /tmp/run-agent-<id>/). "
                        "Skips substrate copy and prompt rendering — the existing PROMPT.md "
                        "and writable file list are reused as-is.")
    p.add_argument("--allow-dirty-substrate", action="store_true",
                   help="Skip the substrate-integrity pre-flight check. Use when you "
                        "intentionally want to test against modified substrate files "
                        "(e.g. local level edits that haven't been committed).")
    p.add_argument("--live-project", action="store_true",
                   help="Run the agent against the LIVE substrate project instead of a "
                        "/tmp workspace copy. Required for aura-mcp (Aura's plugin only "
                        "lives in the live project, not the workspace copy). The harness "
                        "backs up the agent-writable area, dispatches the agent, snapshots "
                        "the diff as the submission, grades it, then RESTORES the backup.")
    p.add_argument("--defer-editor", action="store_true",
                   help="--live-project only: THIS process owns the drive editor. It is "
                        "started after the fairness hide and stopped before the restore, "
                        "because an Aura-staged editor holds every map package open and "
                        "the hide's directory renames then fail. Set by cb's aura-mcp "
                        "lane, whose bring-up then comes up services-only.")
    args = p.parse_args(argv)
    # Multi-substrate: an omitted --substrate-root derives from the task spec's
    # 'substrate:' field; an explicitly passed flag always wins (it parsed into
    # args.substrate_root above and is left untouched).
    if args.substrate_root is None:
        args.substrate_root = derive_substrate_root(args.task)
    return args


def _make_run_id(task_path: Path, model_slug: str) -> str:
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    # Folder-form specs are named task.md — the task id is the folder name.
    task_id = task_path.parent.name if task_path.stem == "task" else task_path.stem
    model_slug_safe = model_slug.replace(":", "-").replace("/", "_")
    return f"{ts}-{task_id}-{model_slug_safe}"


def _default_run_root(model_slug: str) -> Path:
    """runs/<backend>/ — the per-backend folder default runs land in.

    The backend is the adapter name before ':' in the model slug (claude-p,
    aura-mcp, unreal-mcp, ...), so every backend groups its runs under its
    own folder and no two arms can overwrite each other. Only applies when
    --run-dir is omitted — explicit callers (cb matrix/bench cell dirs) keep their layout,
    and their one-level `<run-dir>/<run_id>` harvest globs stay valid.

    Separators are flattened (a malformed slug like 'openai/gpt-4o' must not
    create a two-level runs/openai/gpt-4o/ that layout consumers can't see).
    """
    backend = model_slug.split(":", 1)[0].strip()
    backend = backend.replace("/", "_").replace("\\", "_") or "unknown"
    return DEFAULT_RUN_DIR / backend


def _git_text(repo_root, argv, runner=subprocess.run):
    """stdout of a read-only git query, or None when git could not answer.

    None means UNKNOWN and never "clean" / "absent". The exit code is checked,
    not just stdout, because a failed git (exit 128 in a non-repo dir, dubious
    ownership) prints nothing to stdout — reading stdout alone is exactly how
    every copy-era scratch stamped ``plugin_repo_dirty=False`` off a non-repo
    parent while the rig sat dirty (aura_rig/provenance.py::_git_dirty,
    2026-08-05 glide-bp matrix).
    """
    try:
        r = runner(["git", "-C", str(repo_root), *argv],
                   capture_output=True, text=True, timeout=15)
    except Exception:  # noqa: BLE001 - git absent, hung, or not executable
        return None
    if getattr(r, "returncode", 1) != 0:
        return None
    return r.stdout or ""


def main() -> int:
    args = parse_args()
    run_id = _make_run_id(args.task, args.model)
    run_root = args.run_dir if args.run_dir is not None else _default_run_root(args.model)
    run_dir = run_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # ---- 0. Substrate integrity (pre-flight) ---------------------------
    # Catch auto-saves from a running UE editor and other working-tree drift
    # BEFORE we spend 2+ minutes on a build that's pre-doomed by a mutated
    # .umap or substrate source. Untracked files are ignored — only tracked
    # paths that diverge from HEAD count as "dirty." Before aborting, try the
    # crashed-run self-heal (a hard-killed live-project run leaves its
    # fairness_backup / live_backup / presnap behind with no in-process
    # restore) and re-check.
    if not args.allow_dirty_substrate:
        dirty = check_substrate_clean(args.substrate_root)
        if dirty:
            dirty = heal_and_recheck(args.substrate_root, DEFAULT_RUN_DIR, dirty,
                                     log=lambda s: print(s, file=sys.stderr))
        if dirty:
            print("ERROR: substrate has dirty tracked files — this would invalidate the run.",
                  file=sys.stderr)
            print("Possibly a UE editor auto-save, an accidental level edit, or "
                  "unstaged source changes.", file=sys.stderr)
            print("", file=sys.stderr)
            for entry in dirty:
                print(f"  {entry}", file=sys.stderr)
            print("", file=sys.stderr)
            print("Fix one of:", file=sys.stderr)
            print(f"  cd {args.substrate_root.parent.parent}", file=sys.stderr)
            print(f"  git checkout HEAD -- <listed paths>", file=sys.stderr)
            print(f"  # OR re-run with --allow-dirty-substrate (only if the modifications "
                  "are intentional).", file=sys.stderr)
            return 4

    # ---- 1. Extract prompt (central preamble + task sections) -----------
    # The benchmark preamble (tasks/PREAMBLE.md) is the uniform prompt
    # contract every backend prepends. A missing template degrades to
    # no-preamble with a LOUD warning (toy test repos have no template; the
    # real repo always does); preamble_sha stays None so the gap is visible
    # in the run artifacts.
    preamble_text = ""
    preamble_sha = None
    try:
        from preamble import render_preamble
        from aura_rig.tasks import task_id_for
        _pre = render_preamble(
            task_id_for(args.task), args.substrate_root.parents[1],
            substrate_root=args.substrate_root)
        preamble_text, preamble_sha = _pre.text, _pre.sha
    except FileNotFoundError as e:
        print(f"WARNING: benchmark preamble unavailable ({e}) — running "
              "WITHOUT the uniform prompt contract", file=sys.stderr)
    try:
        prompt = extract_agent_visible_prompt(args.task, preamble=preamble_text)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 4
    # Ride the args namespace (already threaded through every result writer)
    # so _write_result can stamp which contract the agent saw.
    args.preamble_sha = preamble_sha

    # ---- 1b. Live-project mode (required for aura-mcp) -----------------
    # Aura's plugin lives only in the live project, not the /tmp workspace copy,
    # so aura-mcp must drive the live project. Backup → dispatch → diff → grade →
    # restore keeps the live substrate clean afterward.
    if args.live_project:
        return _run_live_project(args, run_id, run_dir, prompt)

    # ---- 2. Build workspace (or reuse existing) ------------------------
    agent_writable = args.substrate_root / "AGENT_WRITABLE.json"
    if args.workspace is not None:
        workspace = _load_workspace_from_disk(args.workspace, args.substrate_root, agent_writable)
        print(f"Reusing existing workspace at {workspace.root}")
    else:
        # Per-task isolation (same staging as the graded scratch): the copy
        # carries ONLY the active task's content — foreign per-task trees,
        # foreign flat scaffolds/maps, and Tools/ never reach the agent.
        # Gate on the id resolving under tasks/: a spec run from an ad-hoc
        # path (--task /tmp/foo/task.md) would derive a wrong id and prune
        # the ACTIVE task's own scaffold/maps — for unknown ids fall back to
        # the historical unpruned shape instead.
        task_id = (args.task.parent.name if args.task.stem == "task"
                   else args.task.stem)
        canonical = any((REPO_ROOT / "tasks").glob(f"*/{task_id}/task.md"))
        if not canonical:
            print(f"note: task id {task_id!r} not found under tasks/ — "
                  f"building the workspace WITHOUT per-task isolation")
        workspace = build_workspace(
            substrate_root=args.substrate_root,
            agent_writable_json=agent_writable,
            prompt_text=prompt,
            run_id=run_id,
            extra_skip_subtrees=("Plugins",) if args.skip_plugins else (),
            active_task_id=task_id if canonical else "",
            task_spec_text=(args.task.read_text(encoding="utf-8",
                                                errors="replace")
                            if canonical else ""),
        )
    (run_dir / "prompt.md").write_text(
        workspace.prompt_path.read_text(encoding="utf-8"), encoding="utf-8")
    _write_manifest(run_dir / "workspace_manifest.json", workspace)

    if args.prepare_only:
        print()
        print("=" * 70)
        print("Workspace prepared. Open this UE project in your editor:")
        print()
        print(f"  {workspace.project_dir / 'CraftBenchTemplate.uproject'}")
        print()
        print("When UE finishes loading, dispatch the agent with:")
        print()
        print(f"  python3 tools/run-agent/run.py \\")
        print(f"      --task {args.task} \\")
        print(f"      --model {args.model} \\")
        print(f"      --ue-root \"{args.ue_root}\" \\")
        print(f"      --workspace {workspace.root} \\")
        print(f"      --no-preflight")
        print("=" * 70)
        return 0

    # ---- 3. A2 pre-flight ----------------------------------------------
    if not args.no_preflight:
        print()
        print("=" * 70)
        print("A2 pre-flight: open this UE project in your editor, then press Enter:")
        print()
        print(f"  {workspace.project_dir / 'CraftBenchTemplate.uproject'}")
        print()
        print("The Unreal MCP plugin in UE will then point at the workspace copy,")
        print("so the agent's MCP edits land here and the live template stays clean.")
        print("=" * 70)
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            print("Pre-flight aborted.", file=sys.stderr)
            return 4

    # ---- 4. Dispatch agent ---------------------------------------------
    # No transport seam is forwarded. It used to pass CB_GATEWAY / CB_BEARER
    # through to make_adapter, but its only consumer was the removed
    # aura-agent adapter: every surviving backend (claude-p, aura-mcp,
    # unreal-mcp, bare) takes its transport from the slug and the
    # environment, so the pair was read here and ignored there. Two env vars
    # that silently do nothing are worse than none — an operator who sets
    # them gets no error AND no effect.
    adapter = make_adapter(args.model)
    print(f"Dispatching {adapter.name} (max_turns={args.max_turns}, timeout={args.timeout}s)...",
          flush=True)
    result = adapter.run(
        prompt_path=workspace.prompt_path,
        workspace_dir=workspace.project_dir,
        max_turns=args.max_turns,
        timeout_s=args.timeout,
    )
    # Stream-json transcript is line-delimited JSON; save as .jsonl for clarity.
    (run_dir / "agent_transcript.jsonl").write_text(result.transcript, encoding="utf-8")
    (run_dir / "agent_result.json").write_text(result.to_json(), encoding="utf-8")
    mcp_note = ""
    if result.tool_use_count is not None:
        mcp_note = (f" tools={result.tool_use_count} "
                    f"(mcp={result.mcp_tool_use_count or 0})")
    cost_note = f" cost=${result.cost_usd:.4f}" if result.cost_usd is not None else ""
    model_note = (f" model={','.join(result.models_used)}"
                  if getattr(result, "models_used", None) else "")
    print(f"Agent finished: exit={result.exit_code}, duration={result.duration_s:.1f}s"
          f"{mcp_note}{cost_note}{model_note}",
          flush=True)
    # Attribution guard (2026-07-22: two bare `claude-p` runs silently ran on
    # claude-fable-5 — a Mythos-tier model — and got compared against a
    # sonnet-5 aura run). A slug with no explicit :model runs on the CLI's
    # session default; say so LOUDLY so nobody reads the label as the model.
    if getattr(result, "models_used", None) and ":" not in str(args.model):
        print(f"NOTE: `{args.model}` pinned no model — the CLI's session default "
              f"answered: {', '.join(result.models_used)}. Pin one for "
              f"comparable runs (e.g. --model {args.model}:<model-id>); "
              f"result.json records agent.models_used either way.", flush=True)
    # BEFORE the snapshot, deliberately: a task whose writable module ships a
    # scaffold snapshots NON-EMPTY even after a drive that did nothing, so the
    # empty-submission guard below cannot catch this class. Checked for every
    # backend — the Claude-CLI-specific check further down cannot see the bare arm.
    never_ran = _agent_never_ran(result)
    if never_ran:
        print(f"ERROR: the agent produced nothing — {never_ran}", file=sys.stderr)
        print("       0 turns, 0 tool calls, 0 tokens and a non-zero adapter exit: "
              "no measurement was taken, so this is a TRANSPORT/setup fault and not "
              "a model failure. Non-graded (out of every pass-rate denominator); "
              "re-run the rep.", file=sys.stderr)
        _write_result(run_dir, args, run_id, result, verifier_report=None,
                      overall=VERDICT_AGENT_TRANSPORT_ERROR)
        return 2

    if result.exit_code != 0:
        print(f"WARNING: agent exit_code != 0 — continuing to snapshot anyway",
              file=sys.stderr, flush=True)

    if not args.no_preflight:
        print("You can close UE now (workspace files are about to be snapshotted).")

    # ---- 5. Snapshot submission ----------------------------------------
    submission_dir = run_dir / "submission"
    staged = snapshot_submission(workspace, submission_dir, args.substrate_root)

    # ---- 5b. Answer-key leak gate --------------------------------------
    # AFTER the snapshot so the deliverable survives as evidence; BEFORE the
    # verifier so a cell no denominator can use never buys a build and an editor
    # session; and ahead of the empty-submission branch, whose FAIL_NO_EDITS is
    # GRADED and would otherwise bank a contaminated cell in the denominator.
    leak = _answer_key_leak(run_dir, spec_path=args.task)
    if leak:
        # _report_line, not print: the reason carries an em-dash and a raise
        # here would cost the run the result.json written below.
        _report_line(f"ERROR: {leak}")
        _report_line("       The drive read verifier source, so neither a PASS "
                     "nor a FAIL from it means anything. Non-graded; re-run "
                     "the cell.")
        _write_result(run_dir, args, run_id, result, verifier_report=None,
                      overall=VERDICT_FAIRNESS_BREACH, void_reason=leak)
        # Step 7's teardown, repeated because an early return skips it:
        # skipping a build buys nothing if the substrate copy is left behind.
        if not args.keep_workspace:
            shutil.rmtree(workspace.root, ignore_errors=True)
        return 2

    if not staged:
        # BEFORE blaming the agent: an empty submission is ALSO what a config
        # error looks like. Measured 2026-08-10 — `aura-mcp:opus-5` passed an
        # AURA model key to `claude -p`, whose CLI rejected it outright; the run
        # produced 0 turns, 0 tokens, `model=<synthetic>` and a single assistant
        # message reading "There's an issue with the selected model (opus-5)".
        # That graded as FAIL_NO_EDITS for DAYS and read as a tool-access
        # problem, because the symptom is identical to a model that did nothing.
        # The rule is explicit: never let a non-agent condition reach a
        # graded verdict. AGENT-CONFIG-ERROR is not in GRADED_VERDICTS, so it
        # stays out of every pass-rate by construction.
        cfg = _agent_config_error(result)
        if cfg:
            print(f"ERROR: the agent never ran — {cfg}", file=sys.stderr)
            print("       This is a CONFIG fault, not a model failure: no API "
                  "call was made (0 turns, 0 tokens). NB every arm slug "
                  "(`claude-p:<model>`, `aura-mcp:<model>`, "
                  "`unreal-mcp:<model>`) takes a CLAUDE model id (opus / "
                  "sonnet / claude-opus-5); a key minted in some other "
                  "vendor's namespace lands here.",
                  file=sys.stderr)
            _write_result(run_dir, args, run_id, result, verifier_report=None,
                          overall=VERDICT_AGENT_CONFIG_ERROR)
            return 2
        print("ERROR: agent produced no edits — submission is empty", file=sys.stderr)
        _write_result(run_dir, args, run_id, result, verifier_report=None, overall="FAIL_NO_EDITS")
        return 2
    print(f"Snapshotted {len(staged)} file(s) to {submission_dir}", flush=True)

    # ---- 6. Run verifier -----------------------------------------------
    verifier_cmd = [
        sys.executable, str(VERIFIER),
        "--task", str(args.task),
        "--submission", str(submission_dir),
        "--ue-root", args.ue_root,
        # Pin the report into the run dir (the discriminate-runner pattern): the
        # verifier's default report lands in a workdir that may be gone by the
        # time we read it -> the old `verifier: null` in result.json.
        "--report-json", str(run_dir / "report.json"),
        # Decouple logs/artifacts from the workdir lifecycle: the POSIX
        # tempdir self-deletes, so the --capture sweep must land run-side.
        "--out-dir", str(_verifier_out_dir(run_dir)),
    ]
    verifier_cmd += _verifier_workdir_args(run_id)
    verifier_cmd += _verifier_mode_args(args)
    print(f"Running verifier: {' '.join(verifier_cmd)}", flush=True)
    _t_verify = time.time()
    completed = subprocess.run(verifier_cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    verify_s = round(time.time() - _t_verify, 1)
    (run_dir / "verifier_stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (run_dir / "verifier_stderr.txt").write_text(completed.stderr, encoding="utf-8")

    verifier_report = _load_verifier_report(run_dir, completed.stdout)
    artifacts = _collect_artifacts(_verifier_out_dir(run_dir), run_dir)
    # Retention runs HERE and nowhere earlier: report.json/logs were pinned
    # run-side by --report-json/--out-dir and the --capture sweep has just been
    # copied into the run bundle, so the 4.72 GB of .obj about to go is the only
    # thing left that this run still owns. (Outside the verify_s window above by
    # design — see _apply_retention.)
    retention = _apply_retention(run_id, args, verifier_report)
    # Exit-3 (substrate-pin reject) / exit-4 (sandbox reject) map to distinct
    # NON-GRADED verdicts — they are verifier-noise, never an agent FAIL
    # (mirrors aura_rig/driver.py). For graded codes we read the authoritative
    # `overall` from report.json, falling back to the stdout regex.
    overall = verdict_from_verifier(completed.returncode, completed.stdout)
    print(completed.stdout, flush=True)

    _write_result(run_dir, args, run_id, result, verifier_report, overall,
                  artifacts=artifacts,
                  timings={"agent_s": round(result.duration_s, 1), "verify_s": verify_s},
                  retention=retention,
                  graded_workdir=_verifier_workdir(run_id))
    print(f"\nResult: {overall}  (agent {result.duration_s:.1f}s | verify {verify_s}s; "
          f"full report at {run_dir / 'result.json'})", flush=True)

    # ---- 7. Teardown ---------------------------------------------------
    if not args.keep_workspace:
        shutil.rmtree(workspace.root, ignore_errors=True)

    return 0 if overall == "PASS" else 3


def _report_line(msg: str, stream=None) -> None:
    """Emit one diagnostic line that CANNOT raise, whatever stream it is handed.

    WHY (found reviewing the 2026-08-18 containment fix): the reporting block in
    :func:`_restore_live_writable` exists so a post-verdict cleanup stays quiet,
    yet it fed file paths and raw OS-exception text straight into
    ``print(..., file=sys.stderr)``. A text stream whose codec cannot represent
    a character raises UnicodeEncodeError from inside the very handler that is
    supposed to swallow everything — reinstating, inside the handler, exactly
    the post-verdict raise the fix removed.

    MEASURED on this box (CPython 3.13, Windows 11), so the scope is not
    overstated in either direction:
      * CPython's OWN ``sys.stderr`` is utf-8 with errors='backslashreplace'
        and does NOT raise — it stayed backslashreplace even under
        ``PYTHONIOENCODING=cp1252:strict``. The default path was never the
        exposure, and claiming otherwise would be a measurement I do not have.
      * A strict stream in front of it IS. On
        ``io.TextIOWrapper(io.BytesIO(), encoding='ascii', errors='strict')``
        the pre-fix block raised ``UnicodeEncodeError: 'ascii' codec can't
        encode character '\\u2014' in position 64`` — on the block's OWN
        em-dash, before any path or localized OS message was even reached.
        Anything that REPLACES sys.stderr can hand us such a stream; cb's
        launcher reconfigures its own streams to errors='replace' against this
        same failure class (aura_rig/cb.py, main()), but run.py is spawned as a
        CHILD process and inherits none of that.

    Three attempts, each strictly weaker than the last: write as-is; write a
    transliteration the stream's own codec accepts; write ASCII-escaped bytes
    past the text layer. Then give up. Dropping a console line is a real loss of
    signal, which is why it is the LAST resort and why the same facts are also
    persisted to ``<run_dir>/live_restore.json`` in explicit UTF-8 — the console
    is never the only record of a failed restore.
    """
    stream = sys.stderr if stream is None else stream
    try:
        stream.write(msg + "\n")
        return
    except Exception:  # noqa: BLE001 — not raising IS this function's whole job
        pass
    try:
        enc = getattr(stream, "encoding", None) or "ascii"
        stream.write(msg.encode(enc, "backslashreplace").decode(enc, "replace")
                     + "\n")
        return
    except Exception:  # noqa: BLE001
        pass
    try:
        stream.buffer.write(msg.encode("ascii", "backslashreplace") + b"\n")
    except Exception:  # noqa: BLE001
        # A stream that accepts neither text nor bytes. The LINE is lost; the
        # outcome dict it describes still reaches live_restore.json and the
        # caller still gets ok=False, so this degrades the console, not the
        # evidence.
        pass


def _restore_live_writable(project_dir: Path, backup: Path, pre_rels: set,
                           writable_files_fn, run_dir: Path | None = None,
                           log=None) -> dict:
    """Put the live agent-writable area back to its pre-run bytes.

    DOES NOT RAISE — every step, INCLUDING its own error reporting, is
    contained: diagnostics go through :func:`_report_line`, which cannot raise,
    and the injected ``log`` sink is called inside a try as well. That
    qualifier is load-bearing. An earlier version of this docstring claimed
    "NEVER raises" while the handler printed OS-exception text straight to
    sys.stderr, so the claim was simply false for any strict stream — see
    :func:`_report_line` for the measured counter-example.

    WHY IT MUST NOT RAISE — measured 2026-08-18 local time (run dirs are
    UTC-stamped, which is why the id below reads 20260819), run
    ``runs/aura-mcp/20260819-004238-t1-dawn-fog-lighting-rig-aura-mcp-claude-sonnet-5``:
    this restore is the last thing `_run_live_project`'s ``finally`` does, long
    after the verdict is decided. result.json recorded overall=PASS (L1 pass
    310s, L2I pass 14/14) and the console printed ``Result: PASS`` — then one
    ``shutil.copy2`` hit ``PermissionError: [WinError 32]`` because a surviving
    editor still held the file. An exception raised inside a ``finally``
    DISCARDS the pending ``return 0``: it propagated out of ``main()``,
    ``sys.exit(main())`` never received a value, CPython exited 1, cb printed
    ``eval exit=1``, and the batch scored a PASS as a failed rep. A post-verdict
    cleanup step must never be able to author the exit code.

    FAIL-CLOSED IS PRESERVED, but by the NEXT run's pre-flight rather than by
    this run's exit code — the only place it can still prevent a contaminated
    measurement. What that pre-flight ACTUALLY does, read out of fairness.py
    rather than assumed:
      * tracked drift -> ``main()``'s dirty-substrate gate. It tries
        ``fairness.heal_and_recheck`` first, and for the run that follows this
        one the self-heal is NOT what saves it: ``heal_dirty_from_presnap``
        keeps only snapshots with ``_age_s(snap) >= LEFTOVER_MIN_AGE_S``
        (fairness.py — 3600 s), and ``heal_leftover_fairness`` applies the same
        floor. A run started within the hour therefore heals NOTHING, gets the
        dirty list back unchanged, and ``main()`` returns 4. The protection is
        the REFUSAL, not the repair. Only a run started more than an hour later
        can revert automatically from this ``live_backup``, and even that is
        skipped outright while ``runs/.live-run.lock`` is held
        (``heal_crashed_run_leftovers``). So recovery rests on the hygiene guard
        refusing to drive a tree it cannot return to HEAD; this backup is the
        bytes a later gate (or a human) restores FROM, not something the next
        run is guaranteed to consume.
      * agent-created leftovers -> ``_run_live_project``'s own
        ``live_hygiene.quarantine_untracked_writable``, which MOVES untracked
        writable files aside before the next drive, and returns 4 via
        ``hygiene.stuck`` only when a move itself fails.
        ``check_substrate_clean`` skips ``??`` porcelain lines, so untracked
        leftovers are this layer's business by design, not the dirty gate's.
    So: report loudly, record the evidence, refuse LATER — never rewrite a
    verdict that was already certified.

    BEHAVIOUR SHIFT, disclosed because it changes WHO catches a botched
    restore. Pre-fix, the first raising unlink/copy2 aborted the whole loop:
    every file after it stayed at the agent's bytes, so tracked drift was
    near-certain and the next run's dirty-substrate gate reliably fired.
    Post-fix each file gets its own attempt (and a missing parent dir is
    recreated, so an agent that deleted a folder no longer makes every file
    under it unrestorable), which means a botched restore can now leave a
    SMALLER mess — including the case where the only casualty is an
    agent-created UNTRACKED file that would not unlink. That case is invisible
    to the dirty gate and is caught one layer over, by the next run's
    ``quarantine_untracked_writable``.
    HOW THAT WAS CONFIRMED — by reading both gates, not by running a live pair:
    ``substrate_check.check_substrate_clean`` drops ``??`` lines, so it cannot
    be the catcher for untracked leftovers; ``live_hygiene.untracked_under`` +
    ``quarantine_untracked_writable`` enumerate exactly the writable prefixes
    and move them aside; and both live substrates' AGENT_WRITABLE.json declare
    only ``Source/<module>/`` and ``Content/Tasks/`` writable — neither sits
    under ``substrate_check.SKIP_SUBTREES``, and on 2026-08-18 neither
    substrate tracked a ``.md`` or ``.uproject`` under those prefixes —
    ``git ls-files <prefixes>`` filtered on those two suffixes returned nothing
    in BOTH this tree and the frozen bench worktree checked out alongside it,
    so no failed restore of a TRACKED writable file can currently slip
    ``SKIP_FILE_SUFFIXES``.
    RESIDUAL, stated rather than papered over: that last property is a fact
    about today's substrates, not an invariant. Track a ``.md`` under a
    writable prefix and a failed restore of it is ungated by BOTH layers — the
    dirty gate filters the suffix as noise and hygiene only looks at untracked
    files.

    Returns the outcome dict that is also written to
    ``<run_dir>/live_restore.json``. Recorded as a FILE for the same reason
    ``live_hygiene.json`` is: every exit path out of a live drive then carries
    the provenance. A run whose result.json has no sibling ``live_restore.json``
    predates this check — treat it as unverified, not as cleanly restored.
    """
    say = log or (lambda m: print(m, flush=True))
    out = {"ok": True, "restored": 0, "expected": len(pre_rels), "removed": 0,
           "failed_restore": [], "failed_remove": [], "enumerate_error": None}
    try:
        now_rels = {p.relative_to(project_dir).as_posix()
                    for p in writable_files_fn()}
    except Exception as e:  # noqa: BLE001 — see the docstring: this does not raise
        # The rglob walk is not safe either: it runs over a tree an editor may
        # still be writing. Without this the WALK, not the copy, becomes the new
        # uncaught exception and the bug simply moves one line up.
        out["ok"] = False
        out["enumerate_error"] = f"{type(e).__name__}: {e}"
        now_rels = set()
    for rel in sorted(now_rels - set(pre_rels)):
        try:
            (project_dir / rel).unlink()
            out["removed"] += 1
        except Exception as e:  # noqa: BLE001
            out["ok"] = False
            out["failed_remove"].append(
                {"rel": rel, "error": f"{type(e).__name__}: {e}"})
    for rel in sorted(pre_rels):
        try:
            dst = project_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup / rel, dst)
            out["restored"] += 1
        except Exception as e:  # noqa: BLE001
            out["ok"] = False
            out["failed_restore"].append(
                {"rel": rel, "error": f"{type(e).__name__}: {e}"})
    summary = (f"Restored live writable area: {out['restored']}/"
               f"{out['expected']} files restored, {out['removed']} "
               f"agent-created file(s) removed.")
    try:
        say(summary)
    except Exception as e:  # noqa: BLE001
        # An INJECTED sink must not be able to author the exit code either —
        # the default `say` prints to stdout, and a caller may pass anything.
        _report_line(f"  WARN  log sink raised ({type(e).__name__}: {e}); "
                     f"summary was: {summary}")
    if not out["ok"]:
        n_bad = len(out["failed_restore"]) + len(out["failed_remove"])
        _report_line(f"ERROR: the live writable area was NOT fully restored "
                     f"({n_bad} file(s) — the recurring cause is WinError 32, a "
                     f"surviving editor still holding them). The graded verdict "
                     f"above stands unchanged: it was certified before this "
                     f"cleanup ran, so this run's exit code is NOT touched. The "
                     f"refusal belongs to the next run, which will not drive a "
                     f"tree it cannot return to HEAD (dirty-substrate gate / "
                     f"live-hygiene quarantine, both exit 4).")
        for item in out["failed_restore"]:
            _report_line(f"  NOT RESTORED  {item['rel']} — {item['error']}")
        for item in out["failed_remove"]:
            _report_line(f"  NOT REMOVED   {item['rel']} — {item['error']}")
        if out["enumerate_error"]:
            _report_line(f"  could not enumerate the writable tree — "
                         f"{out['enumerate_error']} (agent-created leftovers, "
                         f"if any, were not even looked for)")
        _report_line(f"  the pre-run bytes are still at {backup} — that is the "
                     f"dir a later gate's self-heal reads (see the docstring: "
                     f"only once it is older than LEFTOVER_MIN_AGE_S, and never "
                     f"while the live-run lock is held, so the NEXT run most "
                     f"likely just refuses with exit 4).")
    if run_dir is not None:
        try:
            (run_dir / "live_restore.json").write_text(
                json.dumps(out, indent=2), encoding="utf-8")
        except Exception as e:  # noqa: BLE001 — evidence, not a gate
            _report_line(f"  WARN  could not record live_restore.json — "
                         f"{type(e).__name__}: {e}")
    return out


def _preserve_deliverable(project_dir: Path, backup: Path, run_dir: Path,
                          rule, log=None) -> None:
    """Stage the agent's diff into ``<run_dir>/submission/`` on an abort path.

    Grading's own first step is this same collection, so an abort that returns
    ahead of it loses the bytes for good: the ``finally`` reverts the live
    writable area immediately afterwards. Same collector, so what is kept is
    exactly what would have been graded.

    Cannot raise: nothing downstream of a decided verdict may author the exit
    code.
    """
    say = log or (lambda m: print(m, flush=True))
    try:
        staged = collect_submission(project_dir, backup, run_dir / "submission",
                                    rule)
        say(f"Kept {len(staged)} changed file(s) as evidence in "
            f"{run_dir / 'submission'}")
    except Exception as e:  # noqa: BLE001 — see the docstring
        _report_line(f"  WARN  could not keep the deliverable as evidence "
                     f"({type(e).__name__}: {e})")


def _start_drive_editor(project_dir: Path, log=None) -> Optional[str]:
    """Start the drive editor on the LIVE project, AFTER the fairness hide.

    THE ORDERING IS THE FIX. Aura's in-editor indexer force-loads every map
    (RetrieveFileInfo adds UWorld to AssetClassesThatRequireLoad), so an editor
    that is already up holds every foreign task's .umap without
    FILE_SHARE_DELETE and the hide's directory renames die on WinError 5 —
    measured 2026-08-23: 11 of 20 aura-mcp cells, ~96 min of a 12.1 h block,
    against 0 of 21 on unreal-mcp, whose editor disables Aura. Waiting is
    counterproductive (see fairness._HIDE_SETTLE_TIMEOUT_S); starting later is
    not.

    Returns None on success, else the reason the drive must not proceed.
    """
    say = log or (lambda m: print(m, flush=True))
    from aura_rig import stack as _stack
    from aura_rig.aura_plugin_stage import aura_enabled
    try:
        uproject = _stack.find_uproject(project_dir)
    except OSError as e:   # FileNotFoundError: zero or several .uproject
        return f"no single .uproject under {project_dir} ({e})"
    ue = _stack.resolve_ue()
    if ue is None:
        return "no UnrealEditor binary resolvable (set CB_UE_ROOT / --ue-root)"
    # Aura must be listed in the .uproject AT LAUNCH or the editor never loads
    # it, never loads RemoteControl (its dependency) and :30010 never binds. The
    # bring-up staged it around its own launch and has already restored it, so
    # this launch stages it again — byte-identically reverted (aura_plugin_stage).
    #
    # DECIDED DELIBERATELY: the per-task config overlay is now EFFECTIVE on this
    # lane, because the editor finally launches after it is applied. One task
    # ships an EditorStartupMap (tasks/bp/t2-consistent-enum-names ->
    # /Game/Maps/<id>/L_Playground), so its editor boots into the ACTIVE task's
    # playground and holds that map for the whole drive. Kept effective rather
    # than overridden with a neutral startup map, for three reasons: the hide
    # KEEPS the active task's per-task folders under every root
    # (stage_task_tree_isolation_hide), so the held package is never a rename
    # target; the editor is stopped before the restore moves the foreign folders
    # back; and forcing a different startup map here would make this lane's
    # agent open a different scene than the other arms' on the same task,
    # which is a fairness difference rather than a safety measure.
    #
    # restart=True is not optional: with no editor up, restart=False takes the
    # DIRECT-spawn path, which leaves the client unbound and the agent's
    # editor-bound tools returning nothing (see stack.restart_editor_via_client).
    try:
        with aura_enabled(uproject, log=say):
            ok = _stack.ensure_drive_editor(
                uproject, ue, _stack.StackPaths(), restart=True,
                verdict_subject="DRIVE EDITOR", log=say)
    except Exception as e:  # noqa: BLE001
        # The cross-folder guard RAISES (a foreign UnrealEditor holds :30010 and
        # the shared .Aura session). Anything raising here must become this
        # function's named reason rather than an uncaught main() exception, which
        # would land as a bare exit 7 with no verdict.
        return f"{type(e).__name__}: {e}"
    if not ok:
        return "the drive editor did not come up drive-ready (see the log above)"
    # REMOVED WITH THE PRIVATE PRODUCT LANE (2026-08-28). This used to re-gate
    # the helper services that lane's bring-up started: splitting the bring-up
    # had removed the only place that re-measured them after the 1-3 min editor
    # boot, so one of them dying mid-boot reached the agent as a MODEL failure.
    # None of those services exist in this repository, and the editor-readiness
    # check above is the only gate the published arms depend on.
    return None


def _run_live_project(args, run_id: str, run_dir: Path, prompt: str) -> int:
    """Run the agent against the LIVE substrate project (the in-editor arms).

    Both MCP arms take this path: an in-editor tool layer is installed as a
    plugin of the live project, so the agent must edit that project directly
    rather than a copy. We back up the agent-writable area, dispatch,
    snapshot the diff as the submission, grade it, and ALWAYS restore the
    backup (try/finally).
    """
    substrate = args.substrate_root
    project_dir = substrate  # the live project IS the substrate
    backend = args.model.split(":", 1)[0]
    agent_writable_json = substrate / "AGENT_WRITABLE.json"
    # ONE rule object for this whole drive — backup, restore, workspace manifest
    # and the submission collector below all read it. Before 2026-08-19 each of
    # those spelled the rule as `manifest["writable"]` and so ignored
    # asset_writable / config_writable / deny; see snapshot.py's module docstring
    # for the run that proves what that cost. Loaded HERE, before
    # stage_fairness_hide moves AGENT_WRITABLE.json out of the live tree for the
    # drive — the rule lives in memory from this point on.
    rule = SubmissionRule.load(agent_writable_json)

    def _writable_files():
        return rule.files_under(project_dir)

    prompt_path = run_dir / "PROMPT.md"
    # UTF-8 explicitly: the prompt carries em-dashes/unicode, and the adapter reads
    # it back as strict UTF-8. Without this, Path.write_text defaults to the Windows
    # locale (cp1252) and the em-dash (0x97) crashes the adapter's utf-8 read.
    prompt_path.write_text(prompt, encoding="utf-8")
    (run_dir / "prompt.md").write_text(prompt, encoding="utf-8")
    workspace = Workspace(
        root=substrate.parent, project_dir=project_dir, prompt_path=prompt_path,
        writable_files=_writable_files(), readonly_files=[],
        # The dataclass field means exactly what its name says (the manifest's
        # `writable` key, which build_workspace uses to classify PROMPT-listed
        # source files). It is NOT the submission rule any more — snapshot.py
        # loads that from the substrate manifest itself.
        writable_prefixes=list(rule.manifest.writable),
    )
    _write_manifest(run_dir / "workspace_manifest.json", workspace)

    # Serialize the live-tree mutation window (see live_lock.py). The lock
    # dies with the process, so a hard-killed run never strands it; while
    # held, a concurrent run's gate self-heal keeps hands off our backups.
    try:
        release_lock = acquire_live_run_lock(DEFAULT_RUN_DIR / ".live-run.lock")
    except LiveRunLockBusy:
        print("ERROR: another live-substrate run holds runs/.live-run.lock — "
              "two concurrent live-project runs would corrupt each other. "
              "Wait for it (or kill it), then re-run.", file=sys.stderr)
        return 4

    # P0 (2026-08-18): the writable area must match git HEAD BEFORE we snapshot it.
    # A previous live run's deliverable sits in Content/Tasks/<task>/, which is
    # UNTRACKED, so `git checkout -- UE-projects/` leaves it and the fairness stage
    # deliberately keeps the ACTIVE task's folder — handing this agent the last
    # agent's finished work. Measured byte-exact: a run began with GA_Glide.uasset at
    # 100857 B, the exact size of the previous lane's submission, and "improved" it.
    # Nothing in result.json distinguishes that from an honest run, so the check has
    # to happen here rather than being left to whoever drives the harness.
    # Ordering is load-bearing: this runs BEFORE live_backup, because the end-of-run
    # restore replays live_backup and would otherwise put the contamination back.
    # Scanned area = the same area the collector reads, so a leftover cannot be
    # both invisible to this gate and gradeable by the collector. The prefix set
    # is derived from the ONE rule; see SubmissionRule.untracked_scan_prefixes
    # for the two approximations it makes (no extension gate; deny coverage is
    # whole-prefix) and why config files are deliberately excluded.
    hygiene = quarantine_untracked_writable(
        project_dir, rule.untracked_scan_prefixes(), run_dir,
        log=lambda m: print(m, flush=True))
    # Recorded as a FILE rather than threaded through _write_result's six call
    # sites: every exit path out of a live drive then carries the provenance,
    # including the early FAIL_NO_EDITS returns that skip the normal assembly. A
    # cell whose result.json lacks this key predates the check — treat it as
    # unverified, not as clean.
    (run_dir / "live_hygiene.json").write_text(
        json.dumps(hygiene.as_dict(), indent=2), encoding="utf-8")
    if hygiene.stuck:
        print("ERROR: the agent-writable area could not be returned to git HEAD "
              "(files above are locked — a surviving editor still holds the "
              "project). Refusing to drive: the agent would start on top of a "
              "previous run's work and the result would look completely normal.",
              file=sys.stderr)
        release_lock()
        return 4

    # Back up the agent-writable area (content + the set of pre-existing rels).
    backup = run_dir / "live_backup"
    backup.mkdir(parents=True, exist_ok=True)
    pre_rels = set()
    for p in _writable_files():
        rel = p.relative_to(project_dir).as_posix()
        dst = backup / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)
        pre_rels.add(rel)
    print(f"Backed up {len(pre_rels)} writable file(s) to {backup}", flush=True)

    editor_stopped = [False]

    def _stop_drive_editor() -> None:
        """Stop the editor THIS process started, BEFORE anything restores the
        hidden trees. Idempotent; a no-op unless --defer-editor.

        Deferring the START without moving the STOP is worse than not
        reordering at all. stage_fairness_restore puts ~209-213 folders (~626
        files) back, and with the editor started post-hide this cell never
        indexed them — so the restore, not the hide, becomes the trigger for a
        full UWorld-loading pass. What runs in the next ~50 s is
        collect_submission, the verifier, and _restore_live_writable, and that
        last one NEVER RAISES and leaves the agent's bytes in the live tree on
        WinError. A cheap retryable pre-spend abort would have become a silent
        restore corruption on a graded cell.
        """
        if not getattr(args, "defer_editor", False) or editor_stopped[0]:
            return
        ok = False
        try:
            from aura_rig import stack as _stack
            ok = _stack.shutdown_drive_editor(log=lambda m: print(m, flush=True))
        except Exception as e:  # noqa: BLE001 — teardown never authors a verdict
            print(f"WARN  drive-editor teardown raised ({type(e).__name__}: "
                  f"{e})", file=sys.stderr)
        # Latch only on a VERIFIED death. shutdown_drive_editor returns False
        # when a pid survived every escalation, and that is precisely when the
        # `finally` backstop needs to run again -- latching first made the one
        # failure the backstop exists for the one that disabled it.
        if ok:
            editor_stopped[0] = True
        else:
            print("ERROR: the drive editor did not verifiably die. The fairness "
                  "restore is about to move files it may still hold, and "
                  "_restore_live_writable never raises — so expect an "
                  "incomplete restore and check live_restore.json.",
                  file=sys.stderr)

    fairness_state = None
    try:
        # Fairness staging: an agent that drives the live tree with file-read
        # tools could otherwise read the verifier answer key. Hide it BEFORE
        # dispatch (source-stub CraftBenchTests fixture bodies + move
        # AGENT_WRITABLE.json aside), then restore it BEFORE the snapshot/verify
        # below. Grading copies the REPO substrate, not the live tree, so the
        # hash-pin is unaffected.
        #
        # UNCONDITIONAL for every live-project backend (2026-08-19). It was
        # gated on an arm allow-list with the rationale "aura-mcp
        # denies Write/Edit/Bash so it can only read via Aura's own tools" —
        # a FALSE premise: the deny list covers the generic ACTUATORS, and
        # Read/Glob/Grep were never in it. Measured in the 2026-08-18/19
        # calibration transcripts: aura-mcp runs Read the CURRENT task's
        # fixture (GlideStaminaFunctionalTest.cpp, 23,499 chars — checkpoint
        # schedule, tags, tolerances) and both base classes IN FULL, while the
        # same night's unreal-mcp reads of the same paths returned the 77-char
        # fairness stub. A fairness stage gated on a tool-list assumption
        # breaks silently the moment the tool list changes; the tree state is
        # the only thing worth trusting, so hide for everyone.
        fairness_state = stage_fairness_hide(project_dir, run_dir)
        print(f"Fairness: hid CraftBenchTests fixtures "
              f"({len(fairness_state.stubbed_rels)} file(s)) + moved "
              f"AGENT_WRITABLE.json aside", flush=True)
        # Drive-time task isolation (B6): hide foreign-task scaffold
        # sources (marker-based) AND foreign per-task trees (folder-based:
        # Source/*/Tasks/<id>/, Content/Maps/<id>/, Content/Tasks/<id>/)
        # so the agent only sees the active task's artifacts. Safe here
        # because the writable-area backup above already captured the full
        # pre-hide tree (hide-after-backup, same contract as run_graded);
        # both calls tolerate an already-hidden tree (they move nothing).
        # stage_fairness_restore below puts everything back BEFORE the
        # snapshot, so the submission diff is unaffected.
        task_id = (args.task.parent.name if args.task.stem == "task"
                   else args.task.stem)
        stage_task_isolation_hide(project_dir, task_id, fairness_state)
        stage_task_tree_isolation_hide(project_dir, task_id, fairness_state)
        # Per-task UE config overlay (B7): append the task's verifier-owned
        # ue-config/*.ini fragments onto the live Config/ BEFORE dispatch
        # (the editor reads Config at launch). stage_fairness_restore
        # reverts it byte-identically — Config/ is outside the writable
        # backup, so the fairness state is its only undo path.
        stage_config_overlay_apply(project_dir, args.task, task_id,
                                   fairness_state)
        # Repo-level answer material — LAST in the hide sequence (the config
        # overlay above lazily imports from tools/verify-single, and the
        # prompt render already read tasks/). Measured 2026-08-19: agents
        # with a plain Read tool were reading tasks/<id>/reference/* verbatim
        # (two deepseek "PASSes" delivered the reference's own four files),
        # tasks/<id>/aids/author_reference.py, and the SIBLING substrate's
        # un-stubbed copy of the same task's fixture. The substrate-level
        # hide cannot see any of that; this one renames tasks/,
        # tools/verify-single/ and sibling substrates' CraftBenchTests aside
        # for exactly the agent phase.
        stage_repo_answer_hide(project_dir.parent.parent, project_dir,
                               fairness_state)
        # Aura's RAG index caches the TEXT of everything it indexed, and its
        # query tool serves content from that cache rather than re-reading the
        # file — so the fixture stub above is invisible to it. Measured
        # 2026-08-22: four arm-C drives were served verbatim fixture bodies,
        # comments and all, while the on-disk fixture was a 77-char stub.
        stage_index_cache_hide(project_dir.parent.parent, project_dir,
                               fairness_state)
        # UHT's generated reflection glue is a third copy of the same
        # fixtures, carrying their reflected member NAMES (a control probe, an
        # edge case, a repeated checkpoint). Merge-parked, not renamed: a
        # mid-drive recompile recreates it and must not read as a breach.
        stage_generated_code_hide(project_dir.parent.parent, project_dir,
                                  fairness_state)
        print(f"Fairness: isolated {len(fairness_state.isolated_rels)} "
              f"foreign-task scaffold file(s) + "
              f"{len(fairness_state.isolated_dirs)} per-task folder(s); "
              f"applied {len(fairness_state.applied_config)} config "
              f"overlay ini(s); hid {len(fairness_state.repo_hidden)} "
              f"repo-level answer tree(s) + "
              f"{len(getattr(fairness_state, 'index_hidden', []))} "
              f"index-cache dir(s)",
              flush=True)

        # EVERY HIDE IS NOW IN FORCE — so this is where the editor may start
        # (see _start_drive_editor for why not earlier, and why the hide itself
        # cannot move: pre_rels above was captured from the FULL un-isolated
        # tree, and _restore_live_writable deletes now_rels - pre_rels).
        # An editor failure here is a HARNESS state, never a model one: no
        # tokens were spent, so it is recorded non-graded (EDITOR-NOT-READY,
        # absent from GRADED_VERDICTS) and the grid cell stays open for a
        # re-run. The `finally` below still runs every restore.
        if getattr(args, "defer_editor", False):
            why = _start_drive_editor(project_dir)
            if why:
                print(f"ERROR: the drive editor never became usable — {why}",
                      file=sys.stderr)
                print("       The agent was not dispatched, so nothing was "
                      "measured. Non-graded; re-run the cell.", file=sys.stderr)
                _write_result(
                    run_dir, args, run_id,
                    AgentResult(exit_code=-1, transcript="",
                                summary=f"never dispatched: {why}",
                                tool_use_count=0, duration_s=0.0,
                                mcp_tool_use_count=0, num_turns=0),
                    None, VERDICT_EDITOR_NOT_READY)
                return 4

        # Authentic aura-mcp launches Aura's MCP server standalone; it reads
        # Plugins/Aura/aura_client_port.txt to find the live editor's HTTP port
        # for the session-token fetch. A stale value there is THE recurring
        # auth failure ("No valid session token"), so self-heal it before
        # dispatch. No-op for non-aura-mcp models / non-Aura projects.
        if backend == "aura-mcp":
            ensure_aura_client_port(project_dir, log=lambda m: print(m, flush=True))

        # Same as the workspace spine above: no transport seam is forwarded
        # (see the comment at the step-4 dispatch for why the pair went).
        adapter = make_adapter(args.model)
        print(f"Dispatching {adapter.name} against LIVE project (max_turns={args.max_turns}, "
              f"timeout={args.timeout}s)...", flush=True)
        result = adapter.run(
            prompt_path=prompt_path, workspace_dir=project_dir,
            max_turns=args.max_turns, timeout_s=args.timeout,
        )
        # encoding="utf-8" is load-bearing on Windows: agent transcripts carry
        # unicode (e.g. the ⚠ the model emits), and Path.write_text defaults to
        # cp1252 → UnicodeEncodeError that crashes the whole eval at exit 1. The
        # workspace path above already does this; the live-project path did not.
        (run_dir / "agent_transcript.jsonl").write_text(
            result.transcript or "", encoding="utf-8")
        (run_dir / "agent_result.json").write_text(
            result.to_json(), encoding="utf-8")
        print(f"Agent finished: exit={result.exit_code}, duration={result.duration_s:.1f}s, "
              f"tools={result.tool_use_count} (mcp={result.mcp_tool_use_count or 0})"
              + (f", model={','.join(result.models_used)}"
                 if getattr(result, "models_used", None) else ""), flush=True)

        # The drive is over, so the editor's job is done — and every path from
        # here restores the hidden trees (the never-ran and breach returns just
        # below, the pre-snapshot restore, the `finally`). It must not be holding
        # a package when any of them runs; see _stop_drive_editor.
        _stop_drive_editor()

        # Same unconditional never-ran guard as the workdir lane. This is the
        # --live-project path (aura-mcp / unreal-mcp), so without it the two MCP
        # tool layers keep grading provider outages as model failures — and now that
        # they can run non-Claude models, they inherit exactly the transport
        # failures this was found on.
        never_ran = _agent_never_ran(result)
        if never_ran:
            print(f"ERROR: the agent produced nothing — {never_ran}",
                  file=sys.stderr)
            print("       0 turns, 0 tool calls, 0 tokens and a non-zero adapter "
                  "exit: no measurement was taken. Non-graded; re-run the rep.",
                  file=sys.stderr)
            if fairness_state is not None:
                stage_fairness_restore(fairness_state, project_dir)
            _write_result(run_dir, args, run_id, result, None,
                          VERDICT_AGENT_TRANSPORT_ERROR)
            return 2

        # The hide must still have been in force when the agent stopped;
        # otherwise the drive could have read the reference solution and neither
        # the verdict nor the transcript would show it. Checked BEFORE the
        # restore, which is the only other place this condition is visible and
        # which resolves it silently.
        breaches = (repo_hide_breaches(fairness_state)
                    if fairness_state is not None else [])
        if breaches:
            print("ERROR: fairness breach — repo-level answer material was back "
                  "on disk when the agent finished:", file=sys.stderr)
            for src in breaches:
                print(f"         {src}", file=sys.stderr)
            print("       The drive may have read the reference solution. "
                  "Non-graded; re-run the cell.", file=sys.stderr)
            stage_fairness_restore(fairness_state, project_dir)
            # The `finally` below reverts the live writable area, so this is
            # the only chance to keep the bytes a breach audit wants to read.
            _preserve_deliverable(project_dir, backup, run_dir, rule)
            _write_result(run_dir, args, run_id, result, None,
                          VERDICT_FAIRNESS_BREACH)
            return 2

        # Restore the fairness-staged answer key BEFORE snapshot/verify so the
        # snapshot sees a clean tree and the verifier subprocess (which reads the
        # restored manifest indirectly) runs against an intact substrate.
        if fairness_state is not None:
            stage_fairness_restore(fairness_state, project_dir)
            print("Fairness: restored CraftBenchTests + AGENT_WRITABLE.json before "
                  "snapshot", flush=True)

        # Snapshot = the agent's diff vs the backup (changed + newly-created).
        # SAME collector the workspace lanes run (snapshot.collect_submission);
        # only the baseline differs — live_backup here, the pristine substrate
        # there. Two copies of this loop is how the live lane came to gather a
        # strict subset of what the sandbox accepts.
        submission_dir = run_dir / "submission"
        staged = [p.relative_to(submission_dir).as_posix() for p in
                  collect_submission(project_dir, backup, submission_dir, rule)]

        # Same gate the workspace lane runs, placed the same way and for the
        # same three reasons (see step 5b). Complements the path check above:
        # that one asks whether the PARK held, this one asks what the drive
        # actually read.
        leak = _answer_key_leak(run_dir, spec_path=args.task)
        if leak:
            _report_line(f"ERROR: {leak}")
            _report_line("       The drive read verifier source, so neither a "
                         "PASS nor a FAIL from it means anything. Non-graded; "
                         "re-run the cell.")
            _write_result(run_dir, args, run_id, result, None,
                          VERDICT_FAIRNESS_BREACH, void_reason=leak)
            return 2

        if not staged:
            # Same two-step as the workspace lane: an empty submission is also what
            # a config error looks like. `_agent_never_ran` above misses this case
            # because the CLI reports num_turns=1 for a synthetic rejection.
            cfg = _agent_config_error(result)
            if cfg:
                print(f"ERROR: the agent never ran — {cfg}", file=sys.stderr)
                _write_result(run_dir, args, run_id, result, None,
                              VERDICT_AGENT_CONFIG_ERROR)
                return 2
            print("ERROR: agent produced no edits — submission is empty", file=sys.stderr)
            _write_result(run_dir, args, run_id, result, None, "FAIL_NO_EDITS")
            return 2
        print(f"Snapshotted {len(staged)} changed file(s): {staged}", flush=True)

        verifier_cmd = [
            sys.executable, str(VERIFIER), "--task", str(args.task),
            "--submission", str(submission_dir), "--ue-root", args.ue_root,
            "--report-json", str(run_dir / "report.json"),
            "--out-dir", str(_verifier_out_dir(run_dir)),
        ]
        verifier_cmd += _verifier_workdir_args(run_id)
        verifier_cmd += _verifier_mode_args(args)
        print(f"Running verifier: {' '.join(verifier_cmd)}", flush=True)
        _t_verify = time.time()
        completed = subprocess.run(verifier_cmd, cwd=REPO_ROOT, capture_output=True, text=True)
        verify_s = round(time.time() - _t_verify, 1)
        (run_dir / "verifier_stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (run_dir / "verifier_stderr.txt").write_text(completed.stderr, encoding="utf-8")
        # Same mapping as the workspace path: exit-3/4 -> distinct non-graded
        # verdict; otherwise prefer report.json's authoritative `overall`.
        overall = verdict_from_verifier(completed.returncode, completed.stdout)
        print(completed.stdout, flush=True)
        artifacts = _collect_artifacts(_verifier_out_dir(run_dir), run_dir)
        # Same ordering rule as the workspace path above: the artifacts sweep
        # has lifted this run's evidence out of the workdir, so the reclaim can
        # safely run now. The report is hoisted into a local because retention
        # needs it too — apply()'s "never slim a failed L1" guard reads it.
        verifier_report = _load_verifier_report(run_dir, completed.stdout)
        retention = _apply_retention(run_id, args, verifier_report)
        _write_result(run_dir, args, run_id, result,
                      verifier_report, overall,
                      artifacts=artifacts,
                      timings={"agent_s": round(result.duration_s, 1),
                               "verify_s": verify_s},
                      retention=retention,
                      graded_workdir=_verifier_workdir(run_id))
        print(f"\nResult: {overall}  (agent {result.duration_s:.1f}s | verify {verify_s}s; "
              f"full report at {run_dir / 'result.json'})", flush=True)
        return 0 if overall == "PASS" else 3
    finally:
        # EVERYTHING IN THIS BLOCK IS POST-VERDICT AND NON-GATING. Each step is
        # individually contained because an exception raised in a `finally`
        # DISCARDS the pending `return` — that is how a PASS became `eval
        # exit=1` on 2026-08-18 (full incident in _restore_live_writable's
        # docstring). It also DISCARDS an in-flight exception from the `try`,
        # so containment here keeps the original traceback readable too.
        # Every gating return above (2 transport/no-edits, 3 verifier FAIL,
        # 4 lock-busy / hygiene-stuck / editor-not-ready) survives this block
        # untouched.
        # FIRST, and before any restore: the editor this process started (a
        # dispatch that threw, or an editor that came up and then failed its own
        # gate, both land here with it still running).
        _stop_drive_editor()
        if fairness_state is not None:
            # Idempotent double-restore safety: if dispatch threw before the
            # pre-snapshot restore ran, put the fairness-staged answer key back
            # now. A copy-back over identical bytes is a no-op.
            try:
                stage_fairness_restore(fairness_state, project_dir)
            except Exception as e:  # noqa: BLE001 — see the block comment above
                print(f"ERROR: fairness restore failed ({type(e).__name__}: "
                      f"{e}) — the answer key may still be staged aside. The "
                      f"next run's dirty-substrate gate self-heals from this "
                      f"run's leftovers or refuses (exit 4); this run's verdict "
                      f"and exit code are unchanged.", file=sys.stderr)
        # ALWAYS restore the live writable area to its pre-run state.
        _restore_live_writable(project_dir, backup, pre_rels, _writable_files,
                               run_dir=run_dir)
        try:
            release_lock()
        except Exception as e:  # noqa: BLE001 — see the block comment above
            # live_lock.py holds the lock on an fd, so the OS drops it at
            # process exit regardless — this is diagnostics only. It is listed
            # LAST on purpose: before the containment above, a raising copy2
            # skipped this call entirely.
            print(f"WARN  live-run lock release failed ({type(e).__name__}: "
                  f"{e}) — the OS releases it at process exit.",
                  file=sys.stderr)


def _load_workspace_from_disk(workspace_root: Path, substrate_root: Path, agent_writable_json: Path) -> Workspace:
    """Rehydrate a Workspace dataclass from a pre-built /tmp/run-agent-<id>/ dir.

    The on-disk shape is exactly what build_workspace produced, so we just
    rebuild the in-memory lists by re-walking the project_dir and re-applying
    the substrate's submission rule. PROMPT.md is left as-is.

    ``writable_files`` is classified by the FULL rule (2026-08-19), not by
    ``manifest["writable"]`` alone, so a reused workspace's manifest lists the
    same set the collector will stage. The listing is a run artifact only —
    PROMPT.md is not re-rendered here, so nothing the agent sees changes.
    """
    project_dir = workspace_root / substrate_root.name
    if not project_dir.exists():
        raise SystemExit(f"--workspace {workspace_root} has no project dir at {project_dir}")
    prompt_path = workspace_root / "PROMPT.md"
    if not prompt_path.exists():
        raise SystemExit(f"--workspace {workspace_root} has no PROMPT.md")

    rule = SubmissionRule.load(agent_writable_json)
    writable_files = []
    readonly_files = []
    for p in project_dir.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(project_dir).as_posix()
        if rule.accepts(rel):
            writable_files.append(p)
        else:
            readonly_files.append(p)

    return Workspace(
        root=workspace_root,
        project_dir=project_dir,
        prompt_path=prompt_path,
        writable_files=writable_files,
        readonly_files=readonly_files,
        # Same note as the live path: this field is the manifest's `writable`
        # key, not the submission rule.
        writable_prefixes=list(rule.manifest.writable),
    )


def _write_manifest(path: Path, workspace: Workspace) -> None:
    manifest = {
        "project_dir": str(workspace.project_dir),
        "writable_files": [
            str(p.relative_to(workspace.project_dir)) for p in workspace.writable_files
        ],
        "readonly_files_count": len(workspace.readonly_files),
    }
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _load_verifier_report(run_dir: Path, stdout: str):
    """Load the report the verifier wrote DIRECTLY into the run dir (we pass
    ``--report-json <run_dir>/report.json``), so result.json's ``verifier``
    field is reliable. Falls back to the legacy stdout-scrape (a workdir path
    that may already be gone) when the pinned file is missing/corrupt."""
    try:
        return json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _parse_verifier_report(stdout)


def _parse_verifier_report(stdout: str):
    """Best-effort: try to read the verifier's report.json if its path is still
    present on disk (it lives in a /tmp dir that may have been torn down by
    the time we look). Returns None if unreadable — overall PASS/FAIL is
    parsed separately from the stdout text and is authoritative."""
    marker = "json report:"
    for line in stdout.splitlines():
        if marker in line:
            json_path = line.split(marker, 1)[1].strip()
            try:
                return json.loads(Path(json_path).read_text(encoding="utf-8"))
            except Exception:
                return None
    return None


def _parse_verifier_overall(stdout: str) -> str:
    """Parse the verifier's 'overall : <VALUE>' line from stdout (FALLBACK only).

    Prefer :func:`adapters.base.verdict_from_verifier`, which (a) reads the
    authoritative ``overall`` from report.json and (b) maps exit-3/4 to distinct
    non-graded verdicts. This stdout-regex helper is retained for back-compat
    and is the fallback used when no report.json is available. Delegates to the
    shared regex so there is a single source of truth.
    """
    from adapters.base import _overall_from_stdout_regex
    return _overall_from_stdout_regex(stdout)


def _agent_never_ran(agent_result) -> Optional[str]:
    """The adapter's error when the agent produced NOTHING, else None.

    Backend-neutral counterpart to ``_agent_config_error``, which can only fire for
    the Claude CLI: that one keys on ``<synthetic>`` and a ``terminal_reason``
    record in the CLI's own transcript, artifacts no other adapter emits. So the
    ``bare`` arm — the whole multi-model column — had no equivalent protection at
    all, and its transport failures graded as model FAILs.

    Worse, ``_agent_config_error`` is only consulted when the submission snapshot
    comes back EMPTY. A task whose writable module already holds a scaffold snapshots
    non-empty even after a 0-turn drive, so the guard was skipped and the verifier
    graded the untouched scaffold. This predicate is therefore checked
    unconditionally, before the snapshot is even considered.

    CONSERVATIVE, in the direction the verdict contract requires. It demands FOUR
    independent pieces of positive evidence that no work was attempted:

      * the adapter reported failure (``exit_code != 0``), and
      * zero turns, and
      * zero tool calls, and
      * zero tokens in AND out.

    A model that burned tokens and then produced nothing therefore still grades
    ``FAIL_NO_EDITS`` — it ran, it just failed. Anything less strict would hand the
    model under test a denominator opt-out, which is the same objection that killed
    "could not take the build lock -> non-graded".

    Deliberately does NOT inspect the error text. Matching on "timeout"/"429" would
    silently re-grade every provider message we failed to anticipate, and the four
    zeros already establish the only thing that matters: nothing was measured.
    """
    if getattr(agent_result, "exit_code", 0) == 0:
        return None
    if getattr(agent_result, "num_turns", 0):
        return None
    if getattr(agent_result, "tool_use_count", 0):
        return None
    # Absent (None) and zero both count as "no tokens"; a missing field must not
    # be read as evidence that tokens WERE spent, or an adapter that simply does
    # not report usage could never reach this guard.
    if getattr(agent_result, "tokens_in", None) or getattr(
            agent_result, "tokens_out", None):
        return None
    return (getattr(agent_result, "summary", None)
            or f"adapter exited {getattr(agent_result, 'exit_code', '?')} "
               "with no turns, no tool calls and no tokens")


def _agent_config_error(agent_result) -> Optional[str]:
    """The agent's own words when it never ran, else None.

    An empty submission is ambiguous: it is what a lazy model produces AND what a
    misconfigured run produces. This tells them apart on evidence the CLI already
    emits, rather than on a guess about which model names are valid (that list
    lives in the CLI and would rot here).

    The signature, measured 2026-08-10 on `aura-mcp:opus-5`: the transcript's
    terminal record carries ``terminal_reason: "api_error"`` with
    ``num_turns: 1``, ``duration_api_ms: 0`` and ALL-ZERO usage, and the single
    assistant message has ``model: "<synthetic>"`` — the CLI's own placeholder for
    "I never reached the API". Its text is the useful part ("There's an issue with
    the selected model (opus-5)"), so return that verbatim rather than a summary.

    Conservative by design: it requires the zero-token evidence, so a model that
    genuinely burned tokens and then produced nothing still grades FAIL_NO_EDITS.
    """
    text = getattr(agent_result, "transcript", None) or ""
    if "<synthetic>" not in text:
        return None
    msg = None
    # Must be POSITIVELY established, not merely un-contradicted: a transcript
    # with no terminal record at all (a crash mid-run) must NOT be excused as a
    # config error just because it happens to carry the marker.
    proven = False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("type") == "assistant":
            for part in (rec.get("message") or {}).get("content") or []:
                if part.get("type") == "text" and part.get("text"):
                    msg = part["text"].strip()
        elif rec.get("type") == "result":
            # Require the "never reached the API" evidence, not merely the marker.
            if rec.get("terminal_reason") != "api_error":
                return None
            usage = rec.get("usage") or {}
            if usage.get("input_tokens") or usage.get("output_tokens"):
                return None
            proven = True
    return msg if proven else None


def _answer_key_leak(run_dir, spec_path=None, log=None) -> Optional[str]:
    """The void reason when this drive's transcript shows it READ verifier
    source, else None. Checked between the drive and the grade.

    Creates NO new non-graded route, which is the only reason it may skip a
    grade: ``leak_audit --void`` voids exactly this cell after the fact, so the
    same cells are non-graded either way. Only the timing moves.

    Only the ``fixture`` class gates. That is a SCOPING limit, not a judgement
    about the others: ``leak_audit.own_task`` reads the task id out of
    result.json, which does not exist yet here, so the ``answer`` class would
    widen from this cell's own answer dirs to every task's — and widening the
    void set is the one thing this must not do.

    ``fixture`` is scoped too, and MUST be — this is the correction of
    2026-08-24. Its markers used to be three names of the fixture base class's
    public API, which appear in 66 of 117 task specs and 219 docs because
    DATASET.md Tier 1 publishes the checkpoint-schedule shape for every task on
    purpose. A gate that voids on reading published material is a denominator
    opt-out a drive can take with one ``Read``. ``spec_path`` (``args.task``) is
    threaded in so the markers come from THIS task's own verifier; see
    ``leak_audit.own_fixture_markers``.

    Fails OPEN. A detector that cannot answer is not evidence of a breach, and
    the post-hoc sweep still runs over the finished bundle.
    """
    say = log or _report_line
    try:
        hits = leak_audit.audit(Path(run_dir), spec_path=spec_path)
    except Exception as e:  # noqa: BLE001 — see the docstring: fail open
        say(f"WARN  leak audit skipped ({type(e).__name__}: {e})")
        return None
    if not hits:
        return None
    counts = ", ".join(f"{k}x{len(v)}" for k, v in sorted(hits.items()))
    if "fixture" not in hits:
        # park/foreign/answer without fixture: exposure, or an unscoped answer
        # hit. leak_audit's own doctrine warns on exposure rather than voiding.
        say(f"leak audit: EXPOSED — {counts} (not consumption; still graded)")
        return None
    return (f"fairness breach — leak_audit: {counts}, fixture body served at "
            f"transcript line {hits['fixture'][0]}")


def _read_live_hygiene(run_dir):
    """The pre-drive hygiene verdict this run recorded, or None if it took the
    graded-copy path (which materializes from git HEAD and cannot inherit)."""
    p = Path(run_dir) / "live_hygiene.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — provenance must never break result writing
        return {"checked": False, "unavailable_reason": "live_hygiene.json unreadable",
                "safe_to_grade": False}


def _epoch_record_fields(args) -> dict:
    """Per-run identity fields the record writer would otherwise omit:

    repeat_id      which repetition of the (task × arm) cell this run is.
                   From CB_REPEAT_ID (the epoch driver sets it; §6's
                   extra-reps-after-voids exception is unreportable without
                   it — "re-runs are reported with their own count" needs
                   the count on the record). None = not driven as a rep
                   (ad-hoc eval), which is itself information.
    task_revision  git tree hash of the task's own directory at run start.
                   Computed BEFORE the fairness hide (tasks/ and .git are
                   renamed away during the drive window), via the repo git —
                   run-agent-side on purpose: stamping it in the VERIFIER
                   would change the judge tree and void every refgate cert.
                   NOT_COMPUTED on any failure, never absent: an unknown
                   value must never read the same as a recorded one.
    """
    fields = {"repeat_id": os.environ.get("CB_REPEAT_ID") or None,
              "task_revision": "NOT_COMPUTED"}
    try:
        task_path = Path(getattr(args, "task", "")).resolve()
        task_dir = task_path.parent if task_path.suffix else task_path
        cp = subprocess.run(
            ["git", "rev-parse", "HEAD:" + task_dir.relative_to(
                REPO_ROOT).as_posix()],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=15)
        if cp.returncode == 0 and cp.stdout.strip():
            fields["task_revision"] = cp.stdout.strip()
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return fields


def _plugin_build_fields(args) -> dict:
    """`plugin_build_id` for aura-mcp runs — {} for every other lane.

    An aura-mcp run must record which build of the private editor plugin its
    tool layer came from, because the tool layer is the experimental factor. Resolution runs on the LIVE project (the substrate root — the
    plugin only exists there), preferring the junction target's repo sha and
    falling back to the copy-provenance marker. Fail-open in effect but
    fail-CLOSED in the record: any resolution failure stamps the literal
    NOT_COMPUTED, never drops the key and never aborts a result write.
    """
    model = getattr(args, "model", "") or ""
    if not model.split(":", 1)[0].startswith("aura-mcp"):
        return {}
    fields = {"plugin_build_id": "NOT_COMPUTED", "plugin_provenance": None}
    try:
        from aura_rig.provenance import genius_provenance
        root = getattr(args, "substrate_root", None)
        if root:
            prov = genius_provenance(Path(root))
            fields["plugin_build_id"] = (prov.get("plugin_repo_sha")
                                         or prov.get("plugin_copy_sha")
                                         or "NOT_COMPUTED")
            fields["plugin_provenance"] = {
                k: prov.get(k) for k in (
                    "plugin_link_target", "aura_plugin_version",
                    "plugin_repo_dirty", "plugin_copy_src", "split")}
    except Exception:
        pass
    return fields


def _write_result(run_dir, args, run_id, agent_result, verifier_report, overall,
                  artifacts=None, timings=None, preamble_sha=None,
                  graded_workdir=None, retention=None, void_reason=None):
    result = {
        "run_id": run_id,
        "task": str(args.task),
        "model": args.model,
        "overall": overall,
        # The persistent built-project workdir the verifier graded in (short
        # Windows path; None on POSIX / when no verify ran). Mirrors the
        # summary.json contract the graded lane writes — dashboards and audits
        # resolve the raw l1/l2 logs through it (2026-07-22 audit gap).
        "graded_workdir": str(graded_workdir) if graded_workdir else None,
        # Which benchmark preamble (tasks/PREAMBLE.md render) the agent saw;
        # None = the run had NO uniform prompt contract (pre-preamble run or
        # missing template) — comparisons across that boundary are suspect.
        "preamble_sha": preamble_sha if preamble_sha is not None
                        else getattr(args, "preamble_sha", None),
        # The wall-clock ceiling THIS run actually ran under (--timeout, which
        # cb's --ceiling forwards). Recorded because the §6b uniform-ceiling
        # claim is unauditable without it, and a forgotten flag silently
        # manufactures graded FAIL_NO_EDITS at the 1200 s default — measured
        # 2026-08-19: the qwen python go/no-go leg died at exactly 20.0 min
        # while the operator believed the ceiling was 40.
        "agent_ceiling_s": getattr(args, "timeout", None),
        # Live-project runs only: did this run provably start from the committed
        # substrate? Absent on graded-copy runs (which materialize from git HEAD
        # and cannot inherit anything) and on any live run recorded before
        # 2026-08-18. `safe_to_grade: false` or a MISSING key both mean the same
        # thing for an analyst — the head-start question was not answered — and a
        # contaminated run is otherwise indistinguishable from an honest one.
        "live_hygiene": _read_live_hygiene(run_dir),
        # aura-mcp runs only: which build of the tool layer this run
        # exercised. The tool layer is the experimental factor, so a run of that
        # arm without it is unanchored the way an unversioned model would be.
        # Fail closed: on an aura-mcp run the key is always present —
        # NOT_COMPUTED when resolution fails — because an absent key would read
        # as "no tool-layer version" rather than "version unknown".
        # Other lanes omit it entirely; the requirement is scoped to the arm
        # whose tool layer is not pinned by the engine build already.
        **_plugin_build_fields(args),
        # repeat_id + task_revision — the last two §3 fields the 2026-08-20
        # audit found missing from real records (see _epoch_record_fields).
        **_epoch_record_fields(args),
        "agent": {
            "exit_code": agent_result.exit_code,
            "duration_s": agent_result.duration_s,
            "summary": agent_result.summary,
            "tool_use_count": agent_result.tool_use_count,
            "mcp_tool_use_count": agent_result.mcp_tool_use_count,
            "tool_names": agent_result.tool_names,
            "cost_usd": agent_result.cost_usd,
            "num_turns": agent_result.num_turns,
            # USAGE — added 2026-08-17. Note precisely what was wrong, because
            # the data was NOT missing from disk: `agent_result.json` (the raw
            # AgentResult dump) has carried these all along, and `cb bench`
            # reads them from there. It was THIS file that dropped them — and
            # `result.json` is what the aggregators consume
            # (tools/compare/compare_products.py, tools/dashboard/collect.py),
            # so those two were blind to usage while bench was not.
            #
            # Harmless while every arm was Anthropic, because `cost_usd` stood
            # in. Not harmless the moment a non-Anthropic model runs: cost_usd
            # comes from a rate table keyed on haiku/sonnet/opus substrings
            # (aura_mcp._RATES) and is therefore None for every other vendor,
            # leaving the aggregators with no usage figure at all. Tokens are
            # the only vendor-neutral usage measure available, so the file the
            # aggregators read has to carry them.
            "tokens_in": getattr(agent_result, "tokens_in", None),
            "tokens_out": getattr(agent_result, "tokens_out", None),
            # Cache split, where the backend surfaces it. Kept separate rather
            # than folded into tokens_in because the billing rates differ (1.25x
            # to write, 0.1x to read) and because a session's first run costs
            # ~57% more than its second purely from cache state — pooling them
            # makes that effect unattributable.
            "cache_creation_tokens": getattr(
                agent_result, "cache_creation_tokens", None),
            "cache_read_tokens": getattr(agent_result, "cache_read_tokens", None),
            # REASONING, both halves: the parameter this run SENT (none, on
            # every path — so the cell ran at its provider's default) and the
            # THINKING tokens the provider reported, a subset of tokens_out.
            # Shape and policy label come from adapters/base.py so the record
            # cannot claim a policy the request layer has stopped obeying;
            # `reasoning_measurement` is what stops an unproxied run reading as a
            # zero-reasoning one, which is a measurement it never made.
            **reasoning_policy_fields(
                getattr(agent_result, "reasoning_tokens", None)),
            # SCAFFOLD IDENTITY + the degenerate-loop measure. Added 2026-08-18
            # after the fields existed on AgentResult but never reached disk — the
            # SAME "computed then dropped" bug this file fixed for tokens_in the day
            # before. A field the adapter fills and the writer omits is invisible to
            # every analysis, and indistinguishable from a field nobody measured.
            "truncated_turns": getattr(agent_result, "truncated_turns", None),
            "tools_offered": getattr(agent_result, "tools_offered", None),
            "system_prompt_sha": getattr(agent_result, "system_prompt_sha", None),
            "max_consecutive_repeats": getattr(
                agent_result, "max_consecutive_repeats", None),
            # The model(s) that ACTUALLY answered (from the CLI stream) — the
            # attribution. `model` above is only the REQUESTED slug; a bare
            # backend slug runs on the CLI's session default (2026-07-22).
            "models_used": getattr(agent_result, "models_used", None),
            # The provider's own record ids. `cb or-cost` resolves these against
            # OpenRouter's ledger for the authoritative cost and the DATED model
            # version; keeping them here is what makes that possible after the
            # fact, since the ids exist only in the live response.
            "generation_ids": getattr(agent_result, "generation_ids", None),
            "providers_served": getattr(agent_result, "providers_served", None),
        },
        "verifier": verifier_report,
        "artifacts": sorted(artifacts) if artifacts else [],
    }
    # Additive (mirrors summary.json's graded_workdir): record the pinned
    # verifier workdir when it actually exists at write time. Omitted
    # whenever the pin is off
    # (_verifier_workdir returns None) or the dir never materialized (e.g.
    # FAIL_NO_EDITS writes before any verifier run) — absent key == no
    # retained workdir, never an empty/dangling path.
    wd = _verifier_workdir(run_id)
    if wd is not None and Path(wd).is_dir():
        result["graded_workdir"] = str(wd)
    elif result["graded_workdir"]:
        # The kwarg above carries the PREDICTED pin, which retention mode
        # "none" has just deleted (2026-07-25: the mode exists precisely to
        # stop 24 workdirs holding 121 GB). Null it rather than shipping a
        # dangling path — cb clean's KEEP set chases this field, and this
        # block's own contract is
        # "never an empty/dangling path".
        result["graded_workdir"] = None
    if retention:
        # What retention actually did (mode / reclaimed_bytes / elapsed_s, plus
        # `reason` when a guard refused). Additive and SEPARATE from timings:
        # the reclaim is deliberately outside the verify_s window, so its cost
        # must never be readable as verifier time.
        result["retention"] = retention
    if timings:
        # Additive (mirrors summary.json's timings): agent_s = the agent's own
        # wall, verify_s = the deterministic verifier's wall.
        result["timings"] = timings
    if void_reason:
        # leak_audit owns the void shape, so its writer stamps it. Onto an
        # empty dict so `verdict_before` reads null: a void taken BEFORE the
        # grade has no graded verdict to name.
        stub = {}
        leak_audit.stamp_void(stub, void_reason, by="run.py")
        result[leak_audit.VOID_KEY] = stub[leak_audit.VOID_KEY]
    (run_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
