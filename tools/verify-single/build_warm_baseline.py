"""Prime the L1 warm build cache for a substrate (one-time, ~one cold build).

Builds a clean clone of the committed substrate (both the ``<Module>Editor``
and ``<Module>`` targets) and keeps its ``Intermediate/`` + ``Binaries/`` on
disk as the *baseline*. Subsequent ``run_task.py --warm-cache`` verifies seed
that baseline into their fresh workdir so UBT only recompiles the agent's delta
(see ``warm_cache.py`` for the seeding + correctness-gate details).

Usage::

    python3 tools/verify-single/build_warm_baseline.py \\
        --task tasks/t0-sanity-log-on-beginplay.md \\
        --ue-root /path/to/UE_5.8

The substrate is taken from the task spec's ``Substrate`` (or pass
``--substrate <dir-name>`` directly). Re-priming a substrate whose committed
content is unchanged is a no-op unless ``--force`` is given. The baseline is
keyed on the substrate git tree SHA, the UE version and the engine BUILD that
produced its objects; a stale baseline is simply ignored by verifies (cold
fallback), so a forgotten re-prime never corrupts a verdict — it only forgoes
the speedup.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import warm_cache  # noqa: E402
from layers.l1_build import run_l1  # noqa: E402
from run_task import (  # noqa: E402
    REPO_ROOT,
    _detect_ue_version,
    _disable_plugin_in_uproject,
    _substrate_dir_name,
    copy_substrate,
    parse_task_spec,
)
from sandbox import WritableManifest  # noqa: E402


def _iso_utc(epoch: float) -> str:
    """ISO-8601 UTC stamp for the baseline meta (timezone-aware)."""
    import datetime as _dt

    return _dt.datetime.fromtimestamp(epoch, _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--task", type=Path, help="Task spec; its Substrate selects what to build.")
    g.add_argument("--substrate", type=str, help="Substrate dir name under UE-projects/ (e.g. CraftBenchTemplate).")
    p.add_argument("--ue-root", type=Path, required=True, help="Root of the UE install (contains Engine/).")
    p.add_argument("--warm-cache-dir", type=Path, default=None,
                   help="Baseline cache root (default: CB_WARM_CACHE_DIR or %%LOCALAPPDATA%%/CraftBench/warm-baseline).")
    p.add_argument("--force", action="store_true", help="Rebuild even slots that are already current.")
    p.add_argument("--slots", type=int, default=1,
                   help="Number of pool slots to prime (default 1). Match your batch-eval "
                        "--verify-concurrency for full concurrent warming. Each slot is an "
                        "independent cold build (~2 min + ~5 GB disk); built sequentially.")
    return p


#: _prime_slot could not take the slot's lock. Distinct from 0 because a caller
#: that counts a skipped slot as primed then tells the operator the pool is ready
#: while it holds nothing, and the next --warm-cache verify silently builds cold.
BUSY = 2


def _prime_slot(
    slot_dir, *, substrate_src, substrate_dir_name, game_module,
    writable_prefixes, ue_root, ue_version, tree_sha, stale_reason, index,
) -> int:
    """Clone + cold-build + snapshot + stamp ONE pool slot. Returns 0 on success."""
    # Take the slot's OWN lock before touching it. Priming is DESTRUCTIVE (an
    # rmtree of the whole slot) and used to run with no lock at all, so
    # `cb warm-prime --force` could delete the tree a concurrent verify was
    # compiling in — manufacturing exactly the false FAIL this work exists to
    # remove. Non-blocking on purpose: a busy slot means a verify owns it, and
    # the right answer is to skip that slot loudly, never to wait holding a
    # half-deleted tree.
    # Acquired UNCONDITIONALLY, not only when the slot already exists: a fresh
    # slot must be locked too, or two concurrent primers would build into the
    # same path and interleave their output.
    _slot_lock = warm_cache.SlotLock(warm_cache.lock_path(slot_dir))
    if not _slot_lock.acquire():
        print(f"  slot-{index}: BUSY — a verify or another primer holds it; "
              f"skipping (re-run when it finishes; the existing baseline is left "
              f"intact)", file=sys.stderr)
        return BUSY
    try:
        return _prime_slot_locked(
            slot_dir, substrate_src=substrate_src,
            substrate_dir_name=substrate_dir_name, game_module=game_module,
            writable_prefixes=writable_prefixes, ue_root=ue_root,
            ue_version=ue_version, tree_sha=tree_sha,
            stale_reason=stale_reason, index=index,
        )
    finally:
        _slot_lock.release()


def _prime_slot_locked(
    slot_dir, *, substrate_src, substrate_dir_name, game_module,
    writable_prefixes, ue_root, ue_version, tree_sha, stale_reason, index,
) -> int:
    """The original body, now guaranteed to run with the slot lock held."""
    if slot_dir.exists():
        print(f"  slot-{index}: clearing stale ({stale_reason}) at {slot_dir}")
        shutil.rmtree(slot_dir, ignore_errors=True)
    build = warm_cache.slot_substrate_dir(slot_dir)
    build.parent.mkdir(parents=True, exist_ok=True)
    print(f"  slot-{index}: clone -> {build}")
    copy_substrate(substrate_src, build)  # git HEAD by default

    # Mirror the verifier: Aura is disabled for grading builds, so the baseline
    # must be built the same way or its .uproject/module set would differ.
    project_path = build / f"{substrate_dir_name}.uproject"
    _disable_plugin_in_uproject(project_path, "Aura")

    print(f"  slot-{index}: building {game_module}Editor + {game_module} (cold) ...")
    started = time.time()
    # Stamp BEFORE the build: a build reaped mid-flight has already overwritten
    # object files, so a marker written only on success could label a partial
    # binary pristine. A failed prime returns below without writing meta, so the
    # slot is invalid anyway and this marker is never consulted.
    warm_cache.write_binaries_state(slot_dir, warm_cache.PRISTINE)
    l1 = run_l1(
        ue_root=ue_root, project_path=project_path, game_module=game_module,
        log_path=slot_dir / "l1_baseline_build.log",
    )
    for n in l1.notes:
        print(f"      {n}")
    if l1.status != "pass":
        print(f"ERROR: slot-{index} build FAILED (exit {l1.exit_code}); not writing meta.\n"
              f"  log: {l1.log_path}", file=sys.stderr)
        return 1

    # Snapshot the pristine agent-writable dirs (before any submission overlay)
    # so each verify can reset to clean state while keeping Intermediate/Binaries.
    n_snap = warm_cache.make_snapshot(
        build, warm_cache.snapshot_dir(slot_dir), writable_prefixes
    )
    print(f"  slot-{index}: snapshot {n_snap} writable prefix(es); built in {l1.duration_seconds:.0f}s")

    # Re-stamp with the fingerprint of the source these object files came from.
    # Written only NOW, after the build passed, so a failed prime leaves the
    # fingerprint absent and every consumer treats the cache as untrustworthy.
    warm_cache.write_binaries_state(
        slot_dir,
        warm_cache.PRISTINE,
        compile_fingerprint=warm_cache.compile_input_fingerprint(
            build, writable_prefixes
        ),
    )

    warm_cache.write_meta(slot_dir, {
        "schema": warm_cache.SCHEMA,
        "substrate_dir_name": substrate_dir_name,
        "substrate_tree_sha": tree_sha,
        "ue_version": ue_version,
        "game_module": game_module,
        "writable_prefixes": list(writable_prefixes),
        "built_at": _iso_utc(started),
        "l1_duration_seconds": round(l1.duration_seconds, 1),
        "host_os": platform.system().lower(),
    })
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.task:
        substrate_dir_name = _substrate_dir_name(parse_task_spec(args.task).substrate)
    else:
        substrate_dir_name = _substrate_dir_name(args.substrate)

    substrate_src = REPO_ROOT / "UE-projects" / substrate_dir_name
    if not substrate_src.exists():
        print(f"ERROR: substrate not found at {substrate_src}", file=sys.stderr)
        return 2

    manifest_path = substrate_src / "AGENT_WRITABLE.json"
    if not manifest_path.exists():
        print(f"ERROR: AGENT_WRITABLE.json missing at {manifest_path}", file=sys.stderr)
        return 2
    manifest = WritableManifest.load(manifest_path)
    game_module = manifest.game_module
    writable_prefixes = tuple(manifest.writable) + tuple(manifest.asset_writable)

    ue_version = _detect_ue_version(args.ue_root)
    tree_sha = warm_cache.substrate_tree_sha(substrate_src, repo_root=REPO_ROOT)
    if not tree_sha:
        print(
            "ERROR: substrate is not committed (no git tree SHA) — a baseline "
            "built from uncommitted content can't be safely pinned. Commit the "
            "substrate first.",
            file=sys.stderr,
        )
        return 2

    # Canonicalize an explicit --warm-cache-dir too (default_cache_root() already
    # does its own): the primer MUST spell the slot path exactly the way the
    # verifier will, or UBT's path-bound cache treats the warm build as a
    # different target and rebuilds from scratch. FAILURE-LOG 2026-07-25.
    cache_root = (args.warm_cache_dir.resolve() if args.warm_cache_dir
                  else warm_cache.default_cache_root())
    root = warm_cache.slot_root(cache_root, substrate_dir_name)
    n_slots = max(1, int(args.slots))

    print(f"=== priming warm pool: {substrate_dir_name} "
          f"({n_slots} slot(s), tree {tree_sha[:12]}, UE {ue_version}) ===")

    built = skipped = busy = 0
    for i in range(n_slots):
        sdir = warm_cache.slot_path(root, i)
        # ue_root, not just ue_version: an in-place engine rebuild at the same
        # triple leaves the slot's objects orphaned, and without it the primer
        # calls that slot "already current" and skips the one build that heals it.
        ok, reason = warm_cache.is_valid(
            sdir, substrate_tree_sha=tree_sha, ue_version=ue_version,
            ue_root=args.ue_root)
        if ok and not args.force:
            print(f"  slot-{i}: already current ({reason}) — skipping (use --force to rebuild)")
            skipped += 1
            continue
        rc = _prime_slot(
            sdir, substrate_src=substrate_src, substrate_dir_name=substrate_dir_name,
            game_module=game_module, writable_prefixes=writable_prefixes,
            ue_root=args.ue_root, ue_version=ue_version, tree_sha=tree_sha,
            stale_reason=(reason if sdir.exists() else None), index=i,
        )
        if rc == BUSY:
            busy += 1
            continue
        if rc != 0:
            return rc
        built += 1

    print(f"=== warm pool ready: {built} built, {skipped} already current"
          + (f", {busy} BUSY (NOT primed)" if busy else "")
          + f" ({n_slots} slot(s)) ===\n  {root}")
    if not built and not skipped:
        print("  NOTHING was primed — a --warm-cache verify will fall back to a "
              "COLD build.", file=sys.stderr)
        return 1
    print("  verifies can now use:  run_task.py --warm-cache ...   (or `cb ... --warm-cache`)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
