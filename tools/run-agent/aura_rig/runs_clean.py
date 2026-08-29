"""cb clean --runs — prune graded run directories under runs/, ledger-first.

The runs/ root is HETEROGENEOUS by design:

  runs/<backend>/<ts>-<task>-<model>/  per-backend run dirs (run.py default:
                                       claude-p/, openrouter/, unreal-mcp/,
                                       aura-mcp/ — result.json marker); older
                                       runs sit FLAT at runs/<ts>-<task>-<model>/
  runs/aura-product/<task>-<stamp>/    nested run dirs under a container root
                                       (<stamp> = YYYYMMDD-HHMMSS UTC; older
                                       dirs carry a raw epoch int)
  runs/aura-product-eval/<label>/      batch-eval reports (summary.json)
  runs/matrix-<ts>/                    a leaderboard + nested cells/**/ run dirs
  runs/bench-<ts>/                     a bench report + nested reps/**/ run dirs

so discovery is MARKER-based, never "every top-level dir": a directory that
directly contains one of the marker files is a prunable RUN UNIT. A top-level
dir with no marker is a CONTAINER — its marker-bearing children are the units
and the container itself is only removed once empty. Anything marker-less
deeper down is left alone (unknown = not ours to delete).

Before a unit is deleted, a compact one-line JSON record (verdict / cost /
timing, schema-tolerant across the run.py result.json and the aura-product /
batch-eval summary.json shapes) is APPENDED to runs/LEDGER.jsonl — cleanup
reclaims disk without erasing the cost/outcome history.

TWO SWEEPS, and the difference is the whole point (see :data:`SLIM_DROP`):

  ``--runs``          DELETE whole units, ledger-first. Reclaims everything,
                      keeps only the one-line record.
  ``--runs --slim``   SLIM units in place: drop the large RECONSTRUCTIBLE
                      subdirs, keep every unit and all of its evidence. On this
                      box that is 83% of runs/ for 0 units lost.

Prefer slim. A run's logs are not history, they are INPUT: a verdict graded by
an older fixture can only be re-adjudicated against today's gate while its
l2_pie.log still exists (measured — see :data:`SLIM_DROP`).

Pure logic + injected rmtree; offline-tested (tests/test_runs_clean.py).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

# A dir DIRECTLY containing any of these is one prunable run unit. matrix-/
# bench- report dirs match via their aggregate file and are pruned WHOLE
# (their nested per-cell / per-rep run dirs go with them). prompt.md is the
# FIRST file run.py writes, so aborted runs still match; report.json covers
# both batch-gen reports and runs that died mid-verify. An entirely EMPTY dir
# is debris and counts as a unit too (an aborted run that never got that far).
MARKERS = ("summary.json", "result.json", "agent_result.json",
           "leaderboard.json", "bench.json", "report.json",
           "prompt.md", "PROMPT.md")

LEDGER_NAME = "LEDGER.jsonl"


@dataclass
class RunUnit:
    path: Path
    container: Optional[str]    # top-level container dir name, None for flat units
    mtime: float


def _is_unit(d: Path) -> bool:
    if not d.is_dir():
        return False
    if any((d / m).is_file() for m in MARKERS):
        return True
    try:
        return not any(d.iterdir())        # empty dir = aborted-run debris
    except OSError:
        return False


def _mtime(d: Path) -> float:
    try:
        return d.stat().st_mtime
    except OSError:
        return 0.0


def discover_run_units(runs_root: Path) -> List[RunUnit]:
    """Marker-based unit discovery (see module docstring). Sorted newest-first."""
    units: List[RunUnit] = []
    if not runs_root.is_dir():
        return units
    for child in sorted(runs_root.iterdir()):
        if not child.is_dir():
            continue                          # loose files (LEDGER.jsonl) are never units
        if _is_unit(child):
            units.append(RunUnit(child, None, _mtime(child)))
            continue
        for grand in sorted(child.iterdir()):  # container: prune marker-bearing children
            if _is_unit(grand):
                units.append(RunUnit(grand, child.name, _mtime(grand)))
    units.sort(key=lambda u: u.mtime, reverse=True)
    return units


#: In-flight floor: a unit younger than this is NEVER a victim. prompt.md is
#: written seconds into a 10-60 min eval and bench.json lands after rep 1, so
#: without a floor a concurrent `cb clean --runs` would sweep a LIVE run.
MIN_AGE_S = 3600.0


def plan(units: List[RunUnit], *, keep_last: int = 0,
         older_than_days: Optional[float] = None,
         min_age_s: float = MIN_AGE_S,
         now: Optional[float] = None) -> Tuple[List[RunUnit], List[RunUnit]]:
    """Split units into (victims, kept). ``keep_last`` protects the N newest
    units overall; ``min_age_s`` protects anything young enough to still be in
    flight; ``older_than_days`` additionally protects anything younger.

    A unit still holding a ``fairness_backup/`` is ALWAYS kept: that dir is a
    crashed run's parked answer key AND the DIRTY-SUBSTRATE gate's self-heal
    source — pruning it would leave the substrate half-hidden with the
    automatic recovery path destroyed (back to manual git surgery)."""
    now = time.time() if now is None else now
    victims: List[RunUnit] = []
    kept: List[RunUnit] = []
    for i, u in enumerate(units):             # units arrive newest-first
        age_s = now - u.mtime
        if (u.path / "fairness_backup").is_dir():
            kept.append(u)
        elif i < max(keep_last, 0):
            kept.append(u)
        elif min_age_s and age_s < min_age_s:
            kept.append(u)
        elif (older_than_days is not None and age_s / 86400.0 < older_than_days):
            kept.append(u)
        else:
            victims.append(u)
    return victims, kept


# --------------------------------------------------------------------------- #
# Ledger extraction — schema-tolerant across the three run-record shapes.      #
# --------------------------------------------------------------------------- #

def _read_json(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _first(*vals):
    for v in vals:
        if v is not None:
            return v
    return None


def _find_aggregate(unit_path: Path) -> Tuple[Optional[dict], Optional[str]]:
    """The batch-eval summary / matrix leaderboard / bench report an aggregate
    unit carries, if any. Detected FIRST so a batch's whole-run ``wall_s`` is
    never mis-recorded as one agent's time."""
    for name in ("summary.json", "leaderboard.json", "bench.json"):
        data = _read_json(unit_path / name)
        if data and ("n_pass" in data or "by_model" in data or "by_pair" in data):
            return data, name
    return None, None


def ledger_row(unit: RunUnit, *, deleted_at: Optional[str] = None) -> dict:
    """One compact JSON record for a unit about to be deleted.

    Field fallback chains cover: run.py result.json (overall / agent.cost_usd /
    timings), run_graded[_product] summary.json (verdict / est_cost_usd /
    model|main_model|model_intended / timings.drive_s|grade_s), and the
    batch-eval / matrix / bench aggregate shapes (counts + by_model/by_pair
    rollups — their nested per-cell/per-rep dirs are pruned with them, so the
    rollup is the only surviving record).
    """
    result = _read_json(unit.path / "result.json") or {}
    summary = _read_json(unit.path / "summary.json") or {}
    agent = result.get("agent") or {}
    timings = result.get("timings") or {}
    s_timings = summary.get("timings") if isinstance(summary.get("timings"), dict) else {}
    verifier = result.get("verifier") or {}
    agg, agg_name = _find_aggregate(unit.path)
    row = {
        "run": unit.path.name,
        "container": unit.container,
        "mtime": round(unit.mtime, 1),
        "deleted_at": deleted_at,
        "task": _first(summary.get("task_id"), result.get("task")),
        "model": _first(summary.get("model"), summary.get("main_model"),
                        summary.get("model_intended"), result.get("model")),
        "verdict": _first(result.get("overall"), summary.get("verdict")),
        "cost_usd": _first(agent.get("cost_usd"), summary.get("est_cost_usd")),
        "agent_s": _first(timings.get("agent_s"), agent.get("duration_s"),
                          s_timings.get("drive_s"),
                          # a batch's wall_s is the WHOLE batch, not one agent
                          None if agg else summary.get("wall_s")),
        "verify_s": _first(timings.get("verify_s"),
                           verifier.get("duration_seconds")
                           if isinstance(verifier, dict) else None,
                           s_timings.get("grade_s")),
    }
    if agg is not None and row["verdict"] is None:
        row["aggregate"] = agg_name
        if "n_pass" in agg:
            row["n_pass"], row["n_fail"] = agg.get("n_pass"), agg.get("n_fail")
        rollup = agg.get("by_pair") or agg.get("by_model")
        if rollup:
            row["rollup"] = rollup
    return {k: v for k, v in row.items() if v is not None}


# --------------------------------------------------------------------------- #
# SLIM — reclaim the bulk of runs/ IN PLACE, without deleting a single unit.   #
# --------------------------------------------------------------------------- #

#: Sub-directories a ``--slim`` pass drops from a run unit. This is a DELETE
#: ALLOWLIST of exactly the names that are (a) large and (b) RECONSTRUCTIBLE,
#: mirroring ``fs_cleanup.slim_workdir``'s inversion: anything a future run
#: writes survives by default, and a name earns a place here only by proof.
#:
#: ``project-lean/`` qualifies on both counts. Measured 2026-08-07 on this box:
#: it is 1.78 GB of runs/'s 2.13 GB (83%), across just 33 of 130 units — a full
#: copy of the graded project's Source/Content/Config, and on the ThirdPerson
#: substrate ~138 MB of that is the stock Content (the Manny/Quinn pool) reused
#: verbatim by every rep. Nothing READS it: ``run_graded.copy_lean_project`` is
#: its only writer, ``cb review`` overlays the run's ``deliverable/`` instead,
#: and the docs already call it "no Binaries - will not launch". Substrate (git)
#: + ``deliverable/`` (21 MB total, kept) reconstruct it.
#:
#: What slim must NEVER drop is the run's EVIDENCE — summary.json, report.json,
#: l2_pie.log, trace.jsonl, deliverable/, preview/. That is not tidiness: on
#: 2026-08-07 two of opus-5's three graded FAILs on gp-glide-stamina-bp were
#: RE-ADJUDICATED from 08-04 l2_pie.log lines against the current gate-5
#: semantics (window floor + ratio, which landed later in a448869) and both
#: turned out to be artefacts of a fixture that no longer exists. A whole-unit
#: prune would have destroyed the only record that could show that. Hence slim
#: rather than delete: verdicts stay re-checkable for the price of 120 MB.
SLIM_DROP = ("project-lean",)

#: Written into a slimmed unit so a later reader knows where the bytes went
#: instead of wondering whether the run was truncated. summary.json is graded
#: evidence and is never mutated.
SLIM_MARKER = ".slimmed.json"


@dataclass
class SlimTarget:
    unit: RunUnit
    drops: List[Path]          # absolute paths present on disk, in SLIM_DROP order
    nbytes: int                # bytes those paths hold right now


def dir_size(path: Path) -> int:
    """Bytes held under ``path`` (0 when absent/unreadable). Best-effort: a
    file that vanishes mid-walk is skipped, never raised."""
    total = 0
    try:
        for entry in path.rglob("*"):
            try:
                if entry.is_file():
                    total += entry.stat().st_size
            except OSError:
                continue
    except OSError:
        return total
    return total


def slim_plan(units: List[RunUnit], *, min_age_s: float = MIN_AGE_S,
              now: Optional[float] = None,
              drop_names: Tuple[str, ...] = SLIM_DROP) -> List[SlimTarget]:
    """Units that still carry reclaimable bytes, largest first.

    Only the in-flight floor applies. The ``fairness_backup/`` rule that
    :func:`plan` uses deliberately does NOT: it protects a crashed run's parked
    answer key and the dirty-substrate self-heal source, and slim does not touch
    that directory — extending the rule here would skip precisely the biggest
    units for a reason that cannot apply to them.

    Idempotent by construction: a unit whose drops are already gone holds 0
    reclaimable bytes and is not a target, so a second pass is a no-op."""
    now = time.time() if now is None else now
    targets: List[SlimTarget] = []
    for u in units:
        if min_age_s and (now - u.mtime) < min_age_s:
            continue                          # in flight - never touch
        drops = [u.path / name for name in drop_names if (u.path / name).is_dir()]
        if not drops:
            continue
        nbytes = sum(dir_size(d) for d in drops)
        targets.append(SlimTarget(u, drops, nbytes))
    targets.sort(key=lambda t: t.nbytes, reverse=True)
    return targets


def slim_execute(targets: List[SlimTarget], ledger_path: Path,
                 rmtree: Callable[[Path], bool], *, check: bool = False,
                 now_iso: Optional[str] = None,
                 log: Callable[[str], None] = print) -> Tuple[int, int]:
    """Drop each target's reclaimable dirs in place. Returns
    ``(units_slimmed, bytes_reclaimed)`` — both 0 under ``check``.

    A partial failure (a held file) is recorded and does not stop the sweep;
    the ledger row and the in-unit marker are written only for what actually
    went, so neither ever over-claims."""
    slimmed = 0
    reclaimed = 0
    now_iso = now_iso or time.strftime("%Y-%m-%dT%H:%M:%S")
    for t in targets:
        if check:
            log(f"  WOULD SLIM    {t.unit.path}  (-{t.nbytes / 2**20:.0f} MB: "
                f"{', '.join(p.name for p in t.drops)})")
            continue
        gone: List[str] = []
        got = 0
        for d in t.drops:
            size = dir_size(d)
            if rmtree(d):
                gone.append(d.name)
                got += size
            else:
                log(f"  PARTIAL       {d}  (a process still holds a file under it)")
        if not gone:
            continue
        slimmed += 1
        reclaimed += got
        row = ledger_row(t.unit)
        row.update({"action": "slim", "slimmed_at": now_iso,
                    "dropped": gone, "reclaimed_bytes": got})
        try:
            with ledger_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            (t.unit.path / SLIM_MARKER).write_text(json.dumps(
                {"slimmed_at": now_iso, "dropped": gone, "reclaimed_bytes": got,
                 "note": "reclaimed by `cb clean --runs --slim`; reconstruct from "
                         "the substrate at this run's revision + deliverable/"},
                indent=1) + "\n", encoding="utf-8")
        except OSError:
            pass                               # bookkeeping must never fail a sweep
        log(f"  SLIMMED       {t.unit.path}  (-{got / 2**20:.0f} MB: {', '.join(gone)})")
    return slimmed, reclaimed


def execute(victims: List[RunUnit], ledger_path: Path,
            rmtree: Callable[[Path], bool], *, check: bool = False,
            now_iso: Optional[str] = None,
            log: Callable[[str], None] = print) -> int:
    """Archive each victim to the ledger, then delete it. Returns the number
    actually removed (0 in --check mode). The row is BUILT before the delete
    (it reads the unit's JSON) but APPENDED after, with a ``status`` field, so
    the ledger never claims a locked, partially-deleted tree was removed.
    Container dirs left empty by the sweep are removed too (best-effort)."""
    removed = 0
    containers: set = set()
    now_iso = now_iso or time.strftime("%Y-%m-%dT%H:%M:%S")
    for u in victims:
        if check:
            log(f"  WOULD DELETE  {u.path}")
            continue
        row = ledger_row(u, deleted_at=now_iso)
        ok = rmtree(u.path)
        row["status"] = "deleted" if ok else "partial"
        with ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        if ok:
            removed += 1
            log(f"  DELETED       {u.path}")
            if u.container:
                containers.add(u.path.parent)
        else:
            log(f"  PARTIAL       {u.path}  (a process still holds a file under it)")
    for c in containers:                       # drop containers the sweep emptied
        try:
            if c.is_dir() and not any(c.iterdir()):
                c.rmdir()
                log(f"  DELETED       {c}  (container emptied)")
        except OSError:
            pass
    return removed
