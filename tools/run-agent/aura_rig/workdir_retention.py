"""workdir_retention — WHICH bytes of a graded verifier workdir survive the run.

Measured 2026-07-25 across a 21-run stress test on the Windows testbed: one
verifier workdir under ``C:\\cb\\wd\\<hash>`` is **5.54 GB**, and the split is
lopsided —

    4.72 GB   <Project>/Intermediate/Build/Win64/x64   MSVC .obj / .pch
    0.82 GB   <Project>/Binaries                       the launchable DLLs
    ~0   GB   out/                                     l1_build.log, l2_pie.log,
                                                       l2_report/, report.json —
                                                       the only DIAGNOSTIC bytes

so ~85% of a kept workdir is a compiler intermediate nobody reads. The same
sweep found 24 workdirs holding 121 GB against 128 GB free (~23 more evals to a
full disk) with **no CLI path to reclaim them**: ``cb bench --prune-workdirs``
deletes workdirs, but ``cb eval`` has no such flag, and ``cb clean --workdirs``
deliberately KEEPS any workdir a ``runs/**/summary.json`` still names in
``graded_workdir`` (``cb._referenced_workdirs``) — i.e. exactly the workdirs a
finished eval produces. So the leak had no exit.

This module is the POLICY half of the fix; the deletion half lives in
``tools/verify-single/fs_cleanup``. Three modes:

    "full"   keep every byte — today's behaviour, the debugging escape hatch
    "slim"   drop the compiler intermediates, KEEP Binaries/ + out/ so the
             graded project still LAUNCHES and still explains its verdict.
             **THE DEFAULT** (maintainer decision, 2026-07-25)
    "none"   keep nothing — the whole workdir goes

NAMING, deliberately: the mode is **slim**, not "lean". ``lean`` is already
spoken for by ``run_graded.copy_lean_project`` -> ``runs/<run>/project-lean/``
(the CB_KEEP snapshot), which EXCLUDES ``Binaries/`` — the exact opposite of
what slim keeps. Two names, two contracts; do not merge the vocabulary.

Everything here is policy only — env/flag resolution plus REFUSALS — with the
deletion behind a lazy import, so this module stays importable (and offline
unit-testable) with no verifier package on sys.path.
"""
from __future__ import annotations

import inspect
import os
import sys
import time
from pathlib import Path
from typing import Callable, Optional

from . import paths as cb_paths  # the ONE wd-root resolver (CB_ROOT)

__all__ = ["MODES", "DEFAULT_MODE", "ENV_VAR", "resolve_mode", "apply"]

#: The retention modes, widest to narrowest. See the module docstring for what
#: each one keeps.
MODES = ("full", "slim", "none")

#: "slim" is the DEFAULT (maintainer decision, 2026-07-25): full retention is
#: what filled 121 GB with .obj files nobody reads, and slim still leaves a
#: launchable project plus the whole diagnostic out/ dir.
DEFAULT_MODE = "slim"

#: Env override, consulted by :func:`resolve_mode` when no explicit flag came in.
ENV_VAR = "CB_WORKDIR_RETENTION"

# fs_cleanup.py lives under tools/verify-single/ and is NOT on sys.path when the
# rig is imported standalone — same lazy sys.path add that
# provenance._import_asset_capture and driver._map_name_for use, so the reuse
# import succeeds from the rig, from the verifier, and from the unit tests.
VERIFY_SINGLE_DIR = Path(__file__).resolve().parents[2] / "verify-single"


def _log_default(msg: str) -> None:
    print(msg, flush=True)


def _logger(log: Optional[Callable[[str], None]]) -> Callable[[str], None]:
    return log if log is not None else _log_default


def _gb(n: int) -> str:
    return f"{n / 1e9:.2f} GB"


# --------------------------------------------------------------------------- #
# Mode resolution                                                              #
# --------------------------------------------------------------------------- #

def resolve_mode(explicit: Optional[str] = None, *,
                 log: Optional[Callable[[str], None]] = None) -> str:
    """The retention mode this run should use.

    Precedence: ``explicit`` (a CLI flag) > env ``CB_WORKDIR_RETENTION`` >
    :data:`DEFAULT_MODE` (``"slim"``).

    An unrecognised value from EITHER source is a WARN, never an abort: killing
    a 40-minute eval over a typo'd env var is worse than reclaiming, and
    silently reverting to ``"full"`` would just restart the 5.54 GB/run leak
    this module exists to stop. An empty/whitespace value reads as UNSET (an
    exported-but-empty env var is routine on Windows and in CI), so it falls
    through to the next source rather than tripping the warning."""
    say = _logger(log)
    for value, origin in ((explicit, "the explicit retention argument"),
                          (os.environ.get(ENV_VAR), ENV_VAR)):
        if value is None:
            continue
        v = str(value).strip().lower()
        if not v:
            continue
        if v in MODES:
            return v
        say(f"WARN  unrecognised workdir retention mode {value!r} from "
            f"{origin} — using {DEFAULT_MODE!r} "
            f"(valid: {', '.join(MODES)})")
        return DEFAULT_MODE
    return DEFAULT_MODE


# --------------------------------------------------------------------------- #
# Refusal predicates                                                           #
# --------------------------------------------------------------------------- #

def _norm(p) -> str:
    """Comparable path form — 8.3 SHORT components expanded, separators
    normalized, case-folded on Windows.

    The expansion is not cosmetic. ``%TEMP%`` on the 2026-07-25 testbed host
    reports as ``C:\\Users\\SHORT~1\\AppData\\Local\\Temp``, and that same
    short-vs-long spelling mismatch is what scored ``cb batch-eval --references
    all`` 0/15 (FAILURE-LOG 2026-07-25). Compared unresolved, a perfectly
    in-root workdir would read as "outside wd_root", the refusal would fire,
    and the 5.54 GB would be kept forever with nobody the wiser."""
    try:
        p = Path(p).resolve()
    except OSError:
        p = Path(p)
    return os.path.normcase(os.path.normpath(str(p)))


def _under_wd_root(wd: Path) -> bool:
    """True iff ``wd`` is a STRICT descendant of the resolved wd-root.

    Strict on purpose: ``wd_root()`` itself is the POOL, not a run workdir.
    Handing the pool to a deleter would take out every other run's workdir —
    including the ones ``cb clean --workdirs`` is under orders to KEEP — and in
    ``"none"`` mode would delete the root the next eval expects to find."""
    try:
        root = _norm(cb_paths.wd_root()).rstrip(os.sep)
    except Exception:  # noqa: BLE001 — a broken CB_ROOT must refuse, not raise
        return False
    return _norm(wd).startswith(root + os.sep)


def _l1_status(report) -> str:
    """``report["layers"]["L1"]["status"]``, or ``"missing"`` when any hop is
    absent or the wrong shape.

    Tolerates a verifier ``Report`` dataclass as well as the plain dict, since
    callers hold whichever shape their layer produced (summary.json's embedded
    ``"verifier"`` block is the dict form)."""
    if report is None:
        return "missing"
    if not isinstance(report, dict) and hasattr(report, "to_dict"):
        try:
            report = report.to_dict()
        except Exception:  # noqa: BLE001 — an unreadable report is just "missing"
            return "missing"
    if not isinstance(report, dict):
        return "missing"
    layers = report.get("layers")
    if not isinstance(layers, dict):
        return "missing"
    l1 = layers.get("L1")
    if not isinstance(l1, dict):
        return "missing"
    status = l1.get("status")
    return status.strip().lower() if isinstance(status, str) else "missing"


# --------------------------------------------------------------------------- #
# The deletion delegates (tools/verify-single/fs_cleanup)                       #
# --------------------------------------------------------------------------- #

def _fs_cleanup():
    """The verifier's ``fs_cleanup`` module, imported LAZILY.

    Function-level on purpose: the deleters live in
    the VERIFIER package, this policy module is imported by the RIG, and a
    module-level import would both close that cross-package loop and make this
    file unimportable in any checkout or test process with no verifier dir on
    sys.path. It is also the seam the unit tests replace, so no test ever needs
    the real deleters (or a real 5.54 GB workdir)."""
    try:
        import fs_cleanup  # type: ignore  # noqa: F401
        return fs_cleanup
    except ImportError:
        if str(VERIFY_SINGLE_DIR) not in sys.path and VERIFY_SINGLE_DIR.is_dir():
            sys.path.insert(0, str(VERIFY_SINGLE_DIR))
        import fs_cleanup  # type: ignore  # noqa: F401
        return fs_cleanup


def _call_delegate(fn, wd: Path, say: Callable[[str], None]):
    """Call an fs_cleanup deleter, passing ``log=`` only when it accepts one.

    The deleters are authored on the other side of a package seam; hard-binding
    to their exact keyword set here would turn a harmless signature difference
    into a TypeError that costs the run its reclaim."""
    try:
        takes_log = "log" in inspect.signature(fn).parameters
    except (TypeError, ValueError):  # builtins / C callables expose no signature
        takes_log = False
    return fn(wd, log=say) if takes_log else fn(wd)


def _as_bytes(value) -> int:
    """Coerce a delegate's return value into a byte count.

    ``fs_cleanup.slim_workdir`` returns a ``SlimStats`` dataclass carrying
    ``reclaimed_bytes``; ``robust_rmtree`` returns a bool. Reading the attribute
    (then a dict key, then a bare number) keeps this policy layer from
    importing that dataclass just to unwrap one integer — same seam argument as
    :func:`_call_delegate`. Anything unrecognised counts as 0: this is
    bookkeeping, and no bookkeeping number is worth failing a graded run over."""
    for key in ("reclaimed_bytes", "bytes", "freed_bytes"):
        v = getattr(value, key, None)
        if v is None and isinstance(value, dict):
            v = value.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return max(int(v), 0)
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return max(int(value), 0)
    return 0


def _tree_size(path: Path) -> int:
    """Total bytes of files under ``path`` (stat-only walk, unreadable entries
    skipped, symlinks not followed).

    Needed only for mode ``"none"``: the whole-tree deleter reports success as a
    bool, not a byte count, and ``reclaimed_bytes`` is the number the whole
    disk-pressure story gets told with. Measured before AND after the delete so
    a Windows-locked PARTIAL removal reports what actually went away rather
    than what we hoped would."""
    total = 0
    for root, _dirs, files in os.walk(str(path), onerror=lambda _e: None):
        for f in files:
            try:
                total += os.stat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return total


# --------------------------------------------------------------------------- #
# The policy entry point                                                       #
# --------------------------------------------------------------------------- #

def apply(workdir, mode, *, report=None, warm: bool = False,
          log: Optional[Callable[[str], None]] = None) -> dict:
    """Apply retention ``mode`` to ``workdir``. Returns::

        {"mode": <what ACTUALLY happened>, "reclaimed_bytes": int,
         "elapsed_s": float}

    plus ``"requested"`` and ``"reason"`` whenever the effective mode differs
    from the one asked for, and ``"error"`` when a delete was attempted and
    failed. ``mode`` is put through :func:`resolve_mode` first, so a None/typo'd
    value can never become a silent no-op.

    REFUSALS — each one silently reverts to ``"full"`` and records WHY in
    ``reason`` (the caller is expected to stamp that into summary.json; nothing
    is logged here, because a refusal is a correct outcome, not an incident):

      * the workdir is missing or not a directory — nothing to reclaim;
      * ``warm=True`` — that path is a shared ``warm_cache`` SLOT, not a run
        workdir. Its ``Intermediate/``+``Binaries/`` ARE the cache (UBT's build
        cache is path-bound, warm_cache.py), so slimming it would silently
        destroy the 5x L1 speed-up for every later verify;
      * the path is not a strict descendant of ``paths.wd_root()`` — see
        :func:`_under_wd_root`;
      * no report, or ``report["layers"]["L1"]["status"] != "pass"``. A BROKEN
        BUILD is precisely when a developer wants the .obj/.pch tree — it is
        the evidence. Never slim a failure.

    DOWNGRADE — ``"none"`` becomes ``"slim"`` under ``CB_PREVIEW=1``, because
    ``cb.py``'s ``_maybe_chain_postrun_preview`` re-opens the graded project
    AFTER the eval route returns; ``"none"`` would delete the very thing it is
    about to photograph. Slim keeps ``Binaries/``, so the project still
    launches, and still reclaims the 4.72 GB that matters.

    Never raises. Retention is bookkeeping; a cleanup that crashed a graded run
    would cost far more than the 5.54 GB it was trying to reclaim."""
    started = time.monotonic()
    say = _logger(log)
    requested = resolve_mode(mode, log=log)

    def _out(effective: str, reclaimed: int = 0, reason: Optional[str] = None,
             error: Optional[str] = None) -> dict:
        d = {"mode": effective,
             "reclaimed_bytes": int(reclaimed),
             "elapsed_s": round(time.monotonic() - started, 3)}
        if effective != requested:
            d["requested"] = requested
        if reason is not None:
            d["reason"] = reason
        if error is not None:
            d["error"] = error
        return d

    if requested == "full":
        return _out("full")          # the escape hatch — a deliberate no-op

    wd = Path(workdir) if workdir else None
    if wd is None or not wd.is_dir():
        return _out("full", reason="workdir_missing")
    if warm:
        return _out("full", reason="warm_cache_pool")
    if not _under_wd_root(wd):
        return _out("full", reason="outside_wd_root")
    l1 = _l1_status(report)
    if l1 != "pass":
        return _out("full", reason="no_report" if report is None else f"l1_{l1}")

    effective, reason = requested, None
    if effective == "none" and os.environ.get("CB_PREVIEW") == "1":
        effective, reason = "slim", "cb_preview_needs_launchable_project"

    try:
        fsc = _fs_cleanup()
        if effective == "slim":
            slim = getattr(fsc, "slim_workdir", None)
            if slim is None:
                # The deleter is a separate module. A checkout that predates it
                # must not lose the run — degrade to "full" and say which half
                # is missing, rather than falling through to a whole-tree wipe.
                return _out("full", reason="slim_delegate_unavailable")
            result = _call_delegate(slim, wd, say)
            # The deleter runs its OWN wd-root gate (fs_cleanup.slim_workdir's
            # allow_root) on top of ours — defence in depth across the package
            # seam. When ITS gate says no, nothing left the disk, so the honest
            # effective mode is "full", not a "slim" that reclaimed 0 bytes.
            if getattr(result, "refused", False):
                return _out("full", reason="slim_delegate_refused")
            reclaimed = _as_bytes(result)
        else:                                   # "none" — the whole tree goes
            before = _tree_size(wd)
            _call_delegate(fsc.robust_rmtree, wd, say)
            reclaimed = max(before - _tree_size(wd), 0)
    except Exception as e:  # noqa: BLE001 — see the "never raises" contract above
        say(f"WARN  workdir retention {effective!r} failed on {wd} "
            f"({type(e).__name__}: {e}) — the workdir is left intact")
        return _out("full", reason="delete_failed",
                    error=f"{type(e).__name__}: {e}")

    out = _out(effective, reclaimed, reason)
    say(f"workdir retention: {effective} reclaimed {_gb(reclaimed)} in "
        f"{out['elapsed_s']:.1f}s ({wd})")
    return out
