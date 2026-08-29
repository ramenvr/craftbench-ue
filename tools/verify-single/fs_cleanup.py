"""fs_cleanup — Windows-safe recursive delete for verifier workdirs / slots.

A just-finished L2 PIE run leaves ``UnrealEditor-Cmd`` exited, but Windows releases a
process's file handles asynchronously and UE's short-lived children
(ShaderCompileWorker, CrashReportClient, EpicWebHelper) can briefly keep a handle on a
workdir file — most visibly the ``.umap`` the test loaded. So an *immediate*
``shutil.rmtree`` fails with WinError 32 ("The process cannot access the file because
it is being used by another process"). A plain ``ignore_errors=True`` merely hides that
and LEAKS the locked tree, which then trips the next warm-slot reuse.

``robust_rmtree`` retries with backoff to let the handles drop, then falls back to a
non-raising sweep so cleanup NEVER crashes the run. Shared by ``run_task`` (workdir
cleanup) and ``warm_cache`` (slot reset). Dependency-free on purpose so importing it
never pulls the heavy verifier modules; the harness (a separate package) keeps its own
small copy of the same idea.

RETENTION MODE "slim" (``slim_workdir``) — measured 2026-07-25 across a 21-run stress
test. A kept workdir at ``C:\\cb\\wd\\<hash>`` is **5.54 GB**, of which 4.72 GB is
``<Proj>/Intermediate/Build/Win64/x64`` (cl.exe .obj/.pch) and 0.82 GB is
``<Proj>/Binaries``; the genuinely diagnostic ``out/`` dir is ~0 GB. 24 kept workdirs
came to **121 GB against 128 GB free** — ~23 more evals to a full disk, with no CLI
path to reclaim: ``cb bench`` has ``--prune-workdirs`` but ``cb eval`` does not, and
``cb clean --workdirs`` deliberately KEEPS any workdir a ``runs/**/summary.json``
names in ``graded_workdir``. ``slim_workdir`` is the missing middle: drop the pure
build byproduct, keep every byte a human or a re-run actually reads back, so "slim"
can be the DEFAULT retention mode instead of the all-or-nothing delete.
"""
from __future__ import annotations

import os
import shutil
import stat
import time
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Callable, Iterator, List, Optional


def robust_rmtree(path, *, retries: int = 6, base_delay: float = 0.5,
                  log: Optional[Callable[[str], None]] = None) -> bool:
    """Remove a tree, tolerating the transient Windows lock a just-finished L2 leaves
    on the workdir. Returns True iff the tree is gone. Never raises.

    Retries with exponential backoff (capped) while the delete keeps hitting an open
    handle, short-circuits the moment the path is gone, and — if a handle is *still*
    held after the last retry — degrades to a non-raising sweep and (optionally) logs a
    one-line warning naming the still-locked path, rather than crashing the caller.

    A FILE (or symlink/junction) is handled by unlink, NOT by the retry loop below:
    shutil.rmtree on a file raises NotADirectoryError, which IS an OSError, so the loop
    would swallow it, burn all `retries` attempts of backoff (~9.5s at the defaults),
    then "degrade" to an ignore_errors sweep that is a no-op on a file — and report
    False. Against the 1814 leaked cb-aura-driver-*.json temp files measured on a real
    box (2026-07-25) that is ~4.8 HOURS spent deleting nothing. Kept byte-for-byte in
    step with its harness-local twin cb.py::_robust_rmtree (separate packages, so the
    ~15 lines are duplicated rather than cross-imported — fix BOTH or neither)."""
    p = str(path)
    if not os.path.exists(p):
        return True
    if os.path.isfile(p) or os.path.islink(p):
        try:
            os.unlink(p)
        except OSError:
            # A DIRECTORY symlink/junction unlinks via rmdir on Windows (os.unlink
            # raises PermissionError on one). Neither call follows the link, so the
            # target tree is untouched whichever one lands.
            try:
                os.rmdir(p)
            except OSError as e:
                if log is not None:
                    log(f"WARN: not removed (a process still holds it): {p} ({e})")
        return not os.path.lexists(p)
    last: Optional[OSError] = None
    for attempt in range(retries):
        try:
            shutil.rmtree(p)
            return True
        except FileNotFoundError:
            return True
        except OSError as e:  # PermissionError / WinError 32 while a handle lingers
            last = e
            if not os.path.exists(p):
                return True
            time.sleep(min(base_delay * (2 ** attempt), 3.0))
    shutil.rmtree(p, ignore_errors=True)  # last resort — never raise
    gone = not os.path.exists(p)
    if not gone and log is not None:
        log(f"WARN: not fully removed (a process still holds a file under it): "
            f"{p} ({last})")
    return gone


# --------------------------------------------------------------------------- #
# Retention mode "slim" — what a finished workdir may drop and what it may not
# --------------------------------------------------------------------------- #

# Whole trees to drop, spelled PROJECT-relative. Sizes measured on a real 5.54 GB
# workdir (C:\cb\wd\<hash>\<Substrate>\, 2026-07-25):
_SLIM_TREES: tuple[tuple[str, ...], ...] = (
    # 4704 MB — cl.exe .obj/.pch/.res for both L1 targets (Editor + Game). Pure
    # byproduct: nothing reads it after the link step and UBT regenerates it. It is
    # a SIBLING of Build/Win64/UnrealEditor/Inc, not its parent, so dropping the
    # whole tree still spares the UHT output (verified on a real workdir: zero
    # *.generated.h live under x64/).
    ("Intermediate", "Build", "Win64", "x64"),
    # 119 MB — the asset-registry cache. Costs exactly one registry scan on the next
    # editor launch in this workdir, and nothing else; no verdict depends on it.
    ("Intermediate", "CachedAssetRegistry"),
)

# 814 MB of Binaries/ is debug symbols + link scaffolding. Matched by EXTENSION and
# never by name: the workdir holds whichever substrate the spec selected — the
# default CraftBenchTemplate OR ThirdPerson — so a literal
# "UnrealEditor-CraftBenchTemplate.pdb" here would silently skip half the fleet.
# Recursive, because UE nests per-RHI subdirs (Binaries/Win64/D3D12, .../DML).
_SLIM_BINARY_EXTS = frozenset((".pdb", ".exe", ".lib", ".exp", ".iobj", ".ipdb"))

# KEEP — slimming is an ALLOWLIST of deletes, so everything below survives by
# construction (and so does anything UE adds to Intermediate/ in a later version).
# Each is kept for a stated reason, not by accident:
#   DerivedDataCache/    2 MB = 0.04% of the reclaim, so dropping it buys nothing
#                        measurable, while a cold DDC risks a shader-compile stall
#                        in any real-RHI PIE leg (`--visible` / `--capture`
#                        run with use_nullrhi=False under a timeout), where a
#                        cold-shader stall reads as a timeout — i.e. a spurious
#                        failure bought for 2 MB.
#   Intermediate/Build/Win64/UnrealEditor/Inc/**   7 MB of *.generated.h /
#                        *.uhtmanifest / *.deps — THE forensic artifact when UHT
#                        fails, which is exactly the run whose workdir you kept.
#   Binaries/**/*.dll, *.modules, *.target   what UnrealEditor-Cmd actually loads to
#                        re-run L2 against the graded build.
#   Source/ Content/ Config/ *.uproject   the reviewable project itself.
#   Saved/               carries Crashes/*.dmp and the --capture PNGs under
#                        Saved/CraftBench/.
#   out/                 the report + layer logs — the whole point of keeping a
#                        workdir at all. (It is a SIBLING of the project dir, so no
#                        project-relative rule can reach it anyway.)


@dataclass
class SlimStats:
    """Outcome of one :func:`slim_workdir` pass.

    ``reclaimed_bytes`` counts only what actually left the disk — measured
    before/after each delete — so a tree that robust_rmtree could only partially
    remove (a lingering handle) is credited honestly rather than optimistically.
    ``deleted_paths`` counts delete OPERATIONS that fully succeeded (one per tree,
    one per Binaries file), not the file count inside a tree. ``refused`` separates
    "the safety gate said no" from "there was nothing to do" — both report
    ``reclaimed_bytes == 0``, and a caller that wants to warn needs to tell them
    apart."""

    reclaimed_bytes: int = 0
    deleted_paths: int = 0
    elapsed_s: float = 0.0
    notes: List[str] = field(default_factory=list)
    refused: bool = False
    project_dir: Optional[str] = None

    @property
    def reclaimed_mb(self) -> float:
        """Reclaim in MB, the unit the measurements above are quoted in."""
        return round(self.reclaimed_bytes / (1024.0 * 1024.0), 1)


def _path_bytes(path) -> int:
    """Bytes on disk at ``path`` (0 when it does not exist). Never raises and never
    follows a link/junction: a size probe runs right after a UE process exited, so a
    file vanishing mid-walk is normal and must not abort the measurement."""
    p = str(path)
    try:
        st = os.lstat(p)
    except OSError:
        return 0
    if not stat.S_ISDIR(st.st_mode):
        return st.st_size
    total = 0
    for root, _dirs, files in os.walk(p, onerror=lambda _e: None):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                continue  # deleted under us — it is 0 bytes of reclaim, not an error
    return total


def _remove_path(path, *, log: Optional[Callable[[str], None]] = None) -> bool:
    """Delete a FILE or a directory TREE, tolerating the same lingering-handle window
    ``robust_rmtree`` exists for. Returns True iff the path is gone. Never raises.

    Files get their own short retry loop rather than being routed through
    ``robust_rmtree``: ``shutil.rmtree`` on a file raises NotADirectoryError, which
    robust_rmtree would dutifully retry six times with backoff — ~12 s burned per
    file, and a slim pass deletes dozens of them. The retry is not theatre either: a
    ``.pdb`` is precisely the file a just-exited ``mspdbsrv`` or an AV scanner still
    holds for a beat after the build."""
    p = str(path)
    if os.path.isdir(p) and not os.path.islink(p):
        return robust_rmtree(p, log=log)
    for attempt in range(4):
        try:
            os.remove(p)
            return True
        except FileNotFoundError:
            return True
        except OSError:  # PermissionError / WinError 32 while a handle lingers
            if not os.path.exists(p):
                return True
            time.sleep(min(0.25 * (2 ** attempt), 2.0))
    return not os.path.exists(p)


def _is_under(child: Path, root: Path) -> bool:
    """True iff ``child`` resolves inside (or is) ``root``. Both sides are resolved
    FIRST so a ``C:\\cb\\wd\\<hash>\\..\\..\\Users`` traversal — or an 8.3 short name,
    or a subst drive — cannot smuggle a path past the gate."""
    try:
        return child.resolve().is_relative_to(root.resolve())
    except (OSError, ValueError):
        return False


def _resolve_allow_root(allow_root, stats: SlimStats) -> Optional[Path]:
    """The root ``workdir`` must sit under. An explicit ``allow_root=`` wins — that is
    how the verifier's own tests (and any caller with a non-standard root) opt in;
    otherwise the ONLY sanctioned root is ``aura_rig.paths.wd_root()``. Returns None
    after recording the refusal, so nothing is deleted when the root is unknowable.

    The import is LAZY on purpose: ``aura_rig`` lives in the separate tools/run-agent
    package and is NOT on sys.path when tools/verify-single/tests runs, so a
    module-scope import would make fs_cleanup — which run_task and warm_cache import
    for ``robust_rmtree`` — unimportable in that context."""
    if allow_root is not None:
        return Path(allow_root)
    try:
        from aura_rig.paths import wd_root
    except Exception as e:  # noqa: BLE001 — a refusal must never become a crash
        stats.refused = True
        stats.notes.append(
            f"refused: aura_rig.paths.wd_root() is unavailable "
            f"({e.__class__.__name__}: {e}) and no allow_root= was passed")
        return None
    try:
        return wd_root()
    except Exception as e:  # noqa: BLE001 — ditto: never raise out of cleanup
        stats.refused = True
        stats.notes.append(
            f"refused: wd_root() failed ({e.__class__.__name__}: {e})")
        return None


def _locate_project(wd: Path) -> Optional[Path]:
    """The dir inside ``wd`` that holds a ``*.uproject``, or None.

    Found by GLOB, never by name — the verifier clones whichever substrate the spec
    selected to ``<workdir>/<SubstrateName>/``, so hardcoding "CraftBenchTemplate"
    would silently no-op on every ThirdPerson run. Same technique as
    aura_rig/run_graded.py::copy_lean_project; tolerates the workdir itself being the
    project dir."""
    try:
        if any(wd.glob("*.uproject")):
            return wd
        return next((c for c in sorted(wd.iterdir())
                     if c.is_dir() and any(c.glob("*.uproject"))), None)
    except OSError:
        return None


def _binary_victims(binaries: Path) -> Iterator[Path]:
    """Every file under ``Binaries/`` whose extension is link/debug scaffolding."""
    for root, _dirs, files in os.walk(str(binaries), onerror=lambda _e: None):
        for name in files:
            if os.path.splitext(name)[1].lower() in _SLIM_BINARY_EXTS:
                yield Path(root) / name


def _reclaim(target: Path, remove: Callable, stats: SlimStats) -> None:
    """Size -> delete -> re-size one target, folding the result into ``stats``.

    The re-measure is what keeps ``reclaimed_bytes`` honest: when a handle lingers,
    robust_rmtree degrades to a non-raising sweep that may leave part of the tree
    behind, and crediting the full pre-delete size would report GBs that are still
    occupying the disk we are trying to save."""
    if not os.path.lexists(str(target)):
        return
    before = _path_bytes(target)
    try:
        remove(target)
    except Exception as e:  # noqa: BLE001 — an injected deleter must not crash the run
        stats.notes.append(f"delete raised on {target} ({e.__class__.__name__}: {e})")
    if os.path.lexists(str(target)):
        after = _path_bytes(target)
        stats.notes.append(
            f"PARTIAL: {target} (a process still holds a file under it)")
    else:
        after = 0
        stats.deleted_paths += 1
    stats.reclaimed_bytes += max(before - after, 0)


def slim_workdir(workdir, *, rmtree: Optional[Callable] = None,
                 log: Optional[Callable[[str], None]] = None,
                 allow_root=None) -> SlimStats:
    """Strip the build byproduct out of a finished verifier workdir, in place.

    Deletes ``<Proj>/Intermediate/Build/Win64/x64`` (4704 MB),
    ``<Proj>/Intermediate/CachedAssetRegistry`` (119 MB) and every
    ``<Proj>/Binaries/**`` file with a debug/link extension (814 MB) — ~5.5 GB of the
    5.54 GB a kept workdir costs — while keeping ``out/``, ``Saved/``, ``Source/``,
    ``Content/``, ``Config/``, ``DerivedDataCache/``, the UHT ``Inc/`` output and the
    loadable ``Binaries`` (.dll/.modules/.target). See the KEEP block above for why
    each survivor survives.

    SAFETY: refuses (``reclaimed_bytes == 0``, ``refused=True``, a note explaining
    which gate said no) unless ``workdir`` resolves under ``aura_rig.paths.wd_root()``
    or the caller passes an explicit ``allow_root=``. A workdir with no ``*.uproject``
    is a no-op, not an error. This function NEVER raises — retention is housekeeping
    and must not be able to fail a graded run after the verdict is already in.

    ``rmtree`` overrides the deleter. It is called as ``rmtree(path)`` for BOTH a
    directory tree and a single file (a slim pass deletes individual Binaries/ files),
    so a bare ``shutil.rmtree`` is not a valid override; the default handles both.
    Success is judged by whether the path is gone afterwards, not by the return value.
    """
    t0 = time.monotonic()
    stats = SlimStats()
    try:
        wd = Path(workdir)
        remove = rmtree if rmtree is not None else partial(_remove_path, log=log)
        root = _resolve_allow_root(allow_root, stats)
        if root is not None:
            if not _is_under(wd, root):
                stats.refused = True
                stats.notes.append(
                    f"refused: {wd} does not resolve under the allowed root {root}")
            elif not wd.is_dir():
                stats.notes.append(f"nothing to slim: {wd} is not a directory")
            else:
                proj = _locate_project(wd)
                if proj is None:
                    stats.notes.append(f"no *.uproject under {wd}; nothing to slim")
                else:
                    stats.project_dir = str(proj)
                    for parts in _SLIM_TREES:
                        _reclaim(proj.joinpath(*parts), remove, stats)
                    # sorted() so the deletion order is deterministic across hosts —
                    # os.walk order is filesystem-dependent and a flaky order makes a
                    # PARTIAL note impossible to compare between two runs.
                    for victim in sorted(_binary_victims(proj / "Binaries")):
                        _reclaim(victim, remove, stats)
    except Exception as e:  # noqa: BLE001 — belt and braces; see the NEVER raises note
        stats.notes.append(
            f"slim aborted ({e.__class__.__name__}: {e}) — workdir left intact")
    stats.elapsed_s = round(time.monotonic() - t0, 3)
    if log is not None:
        if stats.refused:
            log(f"slim: REFUSED {workdir} — {stats.notes[-1] if stats.notes else ''}")
        else:
            log(f"slim: reclaimed {stats.reclaimed_mb} MB from {workdir} "
                f"({stats.deleted_paths} path(s), {stats.elapsed_s}s)")
    return stats
