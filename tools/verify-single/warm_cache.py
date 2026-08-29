"""Path-stable warm build cache for the L1 verifier layer.

L1 (the UBT build) is ~64% of a cold verify's wall time: every submission is
graded in a fresh tempdir with no ``Intermediate/`` or ``Binaries/``, so UBT
recompiles the project's C++ modules from scratch each time — both the
``<Module>Editor`` and ``<Module>`` (Game) targets.

A naive "seed the prebuilt Intermediate/Binaries into the fresh tempdir"
DOES NOT WORK: UBT bakes **absolute paths** into its makefiles, ``.response``
files, and action graph, so a build relocated to a different path invalidates
the whole cache and rebuilds almost everything (measured: 64s vs 70s cold —
no win). The build must happen at the **same absolute path** the cache was
built at (measured in-place: 14s vs 70s — a 5x win).

So this module keeps a **fixed, reusable slot** per (substrate-tree, UE version)
instead of a fresh tempdir:

  <cache>/<substrate>/
    build/                  the slot — substrate is BUILT here and every warm
                            verify ALSO builds here (same path -> cache valid)
    snapshot/               pristine copies of the agent-writable dirs, for reset
    slot.lock               OS advisory lock (one verify per slot at a time)
    baseline.meta.json      tree SHA + UE version + writable prefixes

Per-verify lifecycle (run_task.py, warm mode):
  1. ``try_acquire`` — validate the baseline, take the slot's lock NON-blocking.
     A miss (no/stale baseline, or slot busy) returns None -> caller falls back
     to a normal cold mkdtemp verify. Warming never blocks and never changes a
     verdict; at worst it does nothing.
  2. ``reset_to_pristine`` — restore the agent-writable dirs from ``snapshot/``
     (removing the *previous* submission's files), KEEPING Intermediate/Binaries.
     This is what gives per-verify isolation without a fresh tempdir.
  3. overlay the submission, then ``bump_overlaid`` — set each overlaid file's
     mtime strictly newer than every cached artifact, so UBT recompiles the
     agent's delta. THE CORRECTNESS GATE: without it, a broken submission could
     reuse a baseline ``.obj`` and falsely PASS L1.
  4. build in-place (fast), run layers, ``release`` (the slot persists).

Invalidation is conservative: the baseline is keyed on the substrate git **tree
SHA** (``git rev-parse HEAD:<relpath>``), the UE version, and the **engine
build** that produced the cached objects (:func:`engine_build_id`; the caller
must name the engine it is about to build with). Any mismatch — or an
uncommitted substrate, or an engine whose build cannot be named — is a miss ->
cold fallback.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from fs_cleanup import robust_rmtree

# Bumped when the on-disk layout/meta changes incompatibly. v2 = path-stable
# slot. v3 = Config/ snapshotted + reset (the B7 per-task UE config overlay
# appends to Config/*.ini at staging, so a v2 snapshot without Config/ could
# leak one verify's overlay into the next — old baselines auto-invalidate).
# v4 = ANTI-CONTAMINATION reset. The snapshot now captures the whole tree minus
# COMPILER_CACHE_KEEP, and reset deletes anything absent from it. A v3 snapshot
# holds ONLY the writable prefixes, so running the v4 reset against one would
# delete Source/, Content/, Saved/ and the .uproject — everything it never
# captured. The bump makes every pre-existing slot invalidate (-> cold fallback,
# harmless) instead of being destroyed by a reset it was not built for.
SCHEMA = 4

META_NAME = "baseline.meta.json"
# Records WHAT SOURCE the slot's Binaries/ were last compiled from: "pristine"
# (the primer built them from the committed substrate, no submission) or the
# submission sha of the last verify that built here.
#
# WHY IT EXISTS. A warm slot's Binaries/ are NOT the baseline after the first
# verify — they are whatever the last verify compiled. A normal warm run is
# immune (it resets source to pristine, bumps mtimes, and REBUILDS, so the
# binary is re-derived), but any consumer that reuses the binaries WITHOUT
# building inherits the previous submission's compiled behaviour wholesale.
# Observed live 2026-07-31: a --lite run reported L2 1/1 PASS purely because the
# preceding warm grade had linked that submission's code into the slot a minute
# earlier. That is the stale-.obj false pass in its most complete form — not a
# weaker signal but an actively wrong one.
BINARIES_STATE_NAME = "slot-binaries.json"
PRISTINE = "pristine"

# WHAT COUNTS AS A COMPILE INPUT — by LOCATION, never by extension.
#
# UE draws this line structurally and the fingerprint follows it:
#   Source/**   UBT compiles this. Whatever the extension.
#   Content/**  UBT has no mechanism to compile anything here, ever.
#
# Every writable prefix in both substrates sits under one or the other
# (Source/<Module>/ and Content/Tasks/ plus the asset_writable Content/ dirs), so
# the split is total for anything a submission can legally contain.
#
# THIS USED TO BE AN EXTENSION ALLOWLIST (.cpp/.h/.hpp/.cs/...) and that was
# unsafe in the one direction that matters. An agent may submit ANY file; a
# compile input whose extension was not on the list (`.ixx` C++ modules, an
# `.mm`, whatever a future UE adds) would hash as absent, the mtime bump would be
# skipped, and UBT — told nothing changed — would report "Target is up to date"
# and link a binary that does not contain the submitted code. That is a false
# PASS produced by a guess about file naming.
#
# Location has no such failure mode. An unknown file under Source/ counts as a
# compile input and forces a rebuild; the cost of being wrong is one extra
# compile, not a wrong verdict. Anything under Content/ is genuinely not
# compilable, which is what preserves the win: a discrimination row's legs differ
# only in .uasset bytes and must stay on the fast path.
#
# Config/*.ini is deliberately absent from both sides: UBT invalidates its own
# makefile when DefaultEngine.ini changes and then re-decides for itself (observed
# live: "Invalidating makefile (DefaultEngine.ini modified)" followed by
# "Target is up to date"). That is UBT's call to make, not ours to pre-empt.
COMPILE_INPUT_DIR = "Source"


def _is_compile_input(rel_posix: str) -> bool:
    """True when a repo-relative POSIX path lies under a ``Source/`` directory.

    Matches ``Source/`` at any depth (``Plugins/Foo/Source/...`` counts) so a
    substrate that declares a nested module as writable is covered without a
    second rule.
    """
    parts = rel_posix.split("/")
    return COMPILE_INPUT_DIR in parts[:-1]  # a DIRECTORY component, not the file
BUILD_NAME = "build"       # the slot: substrate built here, verifies build here
SNAPSHOT_NAME = "snapshot"  # pristine agent-writable dirs, for reset
LOCK_NAME = "slot.lock"

# UBT build outputs that carry across verifies (the cache). Everything else in
# the slot is reset to pristine each verify, so isolation is preserved.
_CACHED_DIRS = ("Intermediate", "Binaries")

# THE KEEP-LIST — the ONLY paths permitted to survive from one verify to the next.
#
# This is deliberately an allowlist of what is KEPT, not an allowlist of what is
# restored. The original design reset only the agent-writable prefixes, which
# meant anything a future UE (or a task's own editor session) wrote anywhere else
# in the tree persisted silently into the next task's grade. Inspecting a real
# slot after a night of runs found exactly that, and one entry is dangerous:
#
#   Intermediate/CachedAssetRegistry/          119 MB   <-- the ASSET REGISTRY
#   Intermediate/CachedAssetRegistryDiscovery.bin
#   Intermediate/ShaderAutogen/
#   Saved/Config/WindowsEditor/*.ini           editor settings that persist
#   Saved/Logs, Saved/Autosaves
#
# L2I grades by INTROSPECTING THE ASSET REGISTRY, and all 18 kp- rows use it.
# A registry cache carried in from a different task is a direct path to a verdict
# decided by another task's assets. Note `fs_cleanup.slim_workdir` already treats
# CachedAssetRegistry as disposable — but it REFUSES on warm pool slots, so the
# registry cache was being cleaned everywhere except the one place it survived
# across tasks.
#
# Everything here is a pure function of the source tree, which is precisely what
# `compile_input_fingerprint` certifies. Nothing else may be added without that
# same argument: "is this derivable from the source alone?" If the answer is no,
# it is contamination, however convenient it is to keep.
COMPILER_CACHE_KEEP = ("Binaries", "Intermediate/Build")

# Non-writable dirs the VERIFIER itself may mutate per-verify: the per-task UE
# config overlay (B7, config_overlay.py) appends to Config/*.ini at staging.
# They are snapshotted at prime time and reset to pristine each verify exactly
# like the agent-writable prefixes — but are NOT mtime-bumped (ini files are
# not compile inputs, so bumping them would only churn mtimes).
VERIFIER_MUTABLE_PREFIXES = ("Config/",)

# Safety margin (s) added over the newest cached artifact when bumping overlaid
# mtimes, so UBT recompiles them even on coarse (1-2s) filesystem clocks.
_MTIME_MARGIN_S = 4.0


# --------------------------------------------------------------------------- #
# Paths / keys
# --------------------------------------------------------------------------- #
def default_cache_root() -> Path:
    """The warm-baseline pool root, ALWAYS canonicalized.

    Every input here is an environment string a Windows host can hand us in 8.3
    SHORT form (``CB_WARM_CACHE_DIR``, ``LOCALAPPDATA``, even ``Path.home()`` —
    the 2026-07-25 testbed host reports ``%TEMP%`` as
    ``C:\\Users\\SHORT~1\\AppData\\Local\\Temp``). A slot dir under this root is
    handed to UE as the project path AND is the parent of the ``out/l2_report``
    dir passed as ``-ReportExportPath`` — the exact path role that scored
    ``cb batch-eval --references all`` **0/15** on 2026-07-25 (FAILURE-LOG;
    every L2 leg exit 3 -> ``skipped`` -> FAIL). Same class of bug as the cold
    ``mkdtemp`` workdir, same fix: expand the short name BEFORE any use.

    Second, independent reason: **UBT's build cache is path-bound** (see the
    module docstring's pool rationale). If ``build_warm_baseline.py`` primes a
    slot at the short form and a verify builds at the long form, UBT sees two
    different paths and throws the warm build away. Canonicalizing in the one
    shared helper keeps primer and consumer on a single spelling.

    ``Path.resolve()`` expands an 8.3 component even when the tail does not
    exist yet (only the existing prefix needs to resolve), and is a no-op on
    macOS/Linux.

    SET ``CB_WARM_CACHE_DIR`` SHORT ON WINDOWS. The default is 53 chars before
    the pool even starts; measured on the live slot, the path to a slot is 79
    chars and the longest build path inside it is 221 of the 260-char MAX_PATH —
    39 chars of headroom, against ~100 for the ``C:\\cb\\wd\\<hash>`` workdir a
    cold verify pins. Both the primer and the verifier read this var, and they
    MUST agree: UBT's cache is path-bound, so priming at one spelling and
    verifying at another silently throws the warm build away.
    """
    env = os.environ.get("CB_WARM_CACHE_DIR")
    if env:
        return Path(env).resolve()
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return (Path(base) / "CraftBench" / "warm-baseline").resolve()
    return (Path.home() / ".cache" / "craftbench" / "warm-baseline").resolve()


def slot_root(cache_root: Path, substrate_key: str) -> Path:
    """The per-substrate POOL dir, holding one or more ``slot-<i>`` baselines.

    A pool of N slots lets N concurrent verifies each build warm at their OWN
    stable path (UBT's cache is path-bound, so the slots can't share a path).
    A single interactive verify just uses the one free slot.
    """
    return Path(cache_root) / substrate_key


def slot_path(root: Path, index: int) -> Path:
    """The i-th slot directory within a pool root."""
    return Path(root) / f"slot-{index}"


def discover_slot_dirs(root: Path) -> list[Path]:
    """Existing ``slot-<i>`` directories under a pool root, ordered by index."""
    root = Path(root)
    if not root.is_dir():
        return []
    found: list[tuple[int, Path]] = []
    for child in root.iterdir():
        if child.is_dir() and child.name.startswith("slot-"):
            try:
                found.append((int(child.name[len("slot-"):]), child))
            except ValueError:
                continue
    return [d for _i, d in sorted(found)]


def slot_substrate_dir(slot_dir: Path) -> Path:
    """The fixed build path within a slot — substrate root for prime + verify."""
    return Path(slot_dir) / BUILD_NAME


def snapshot_dir(slot_dir: Path) -> Path:
    return Path(slot_dir) / SNAPSHOT_NAME


def lock_path(slot_dir: Path) -> Path:
    return Path(slot_dir) / LOCK_NAME


def meta_path(slot_dir: Path) -> Path:
    return Path(slot_dir) / META_NAME


def substrate_tree_sha(substrate_src: Path, *, repo_root: Optional[Path] = None) -> Optional[str]:
    """Git tree SHA of the committed substrate subtree (``HEAD:<relpath>``).

    The content identity of what ``copy_substrate`` clones, so the correct
    invalidation key. None when git is unavailable / the substrate is untracked
    or uncommitted — warm-caching must not engage then (cold fallback).
    """
    substrate_src = Path(substrate_src).resolve()
    root = repo_root
    if root is None:
        try:
            out = subprocess.run(
                ["git", "-C", str(substrate_src), "rev-parse", "--show-toplevel"],
                capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=False,
            )
            if out.returncode != 0:
                return None
            root = Path(out.stdout.strip())
        except (OSError, ValueError):
            return None
    try:
        relpath = substrate_src.relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return None
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", f"HEAD:{relpath}"],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=False,
        )
    except OSError:
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def _version_id(version: dict) -> str:
    """``"5.8.1+56057345"`` from an engine ``Version`` block."""
    return "%s.%s.%s+%s" % (version["MajorVersion"], version["MinorVersion"],
                            version["PatchVersion"], version["Changelist"])


def engine_build_id(ue_root: Optional[Path]) -> Optional[str]:
    """Identity of the engine build installed at ``ue_root``, or None.

    A version TRIPLE is not an engine identity — an in-place hotfix can bump the
    changelist alone, and then a slot whose objects the OLD toolchain produced
    validates against the new one. Format matches
    ``aura_rig/refgate.py::engine_build_id`` so both sides spell "which engine"
    alike.

    None when ``Build.version`` is missing or unparseable, i.e. "cannot name the
    engine" — which callers turn into a cold build, never into a trusted slot.
    """
    if ue_root is None:
        return None
    try:
        raw = (Path(ue_root) / "Engine" / "Build" / "Build.version").read_text(
            encoding="utf-8")
        return _version_id(json.loads(raw))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def slot_engine_build(slot_dir: Path) -> Optional[str]:
    """The engine build UBT recorded for the slot's CACHED binaries, or None.

    Taken from the ``.target`` files UBT writes beside them rather than from our
    own meta: it is the build tool's own record of what produced these object
    files, so it cannot drift from them, and slots primed before this check
    existed already carry it.

    None when no ``.target`` parses or two of them disagree — the cache cannot
    then be attributed to one engine build, which :func:`is_valid` treats as a
    miss rather than a trusted slot.
    """
    found: set[str] = set()
    binaries = slot_substrate_dir(slot_dir) / "Binaries"
    for target in sorted(binaries.rglob("*.target")):
        try:
            data = json.loads(target.read_text(encoding="utf-8-sig"))
            found.add(_version_id(data["Version"]))
        except (OSError, ValueError, KeyError, TypeError):
            return None
    return found.pop() if len(found) == 1 else None


def read_meta(baseline_dir: Path) -> Optional[dict]:
    mp = meta_path(baseline_dir)
    if not mp.exists():
        return None
    try:
        return json.loads(mp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def binaries_state_path(slot_dir: Path) -> Path:
    return Path(slot_dir) / BINARIES_STATE_NAME


def read_binaries_state(slot_dir: Path) -> str:
    """What the slot's Binaries/ were last built from.

    Returns the recorded value, or ``"unknown"`` when the marker is missing or
    unreadable. ``"unknown"`` is deliberately NOT treated as pristine: a slot
    primed before this marker existed genuinely has unknown binaries, and a
    consumer that reuses them without building must refuse rather than guess.
    """
    try:
        data = json.loads(binaries_state_path(slot_dir).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unknown"
    value = data.get("built_from")
    return value if isinstance(value, str) and value else "unknown"


def read_compile_files(slot_dir: Path) -> Optional[dict]:
    """Per-file hashes the slot's object files were built from, or None.

    None means "cannot attribute the cache to specific files", which callers
    must treat as "everything may have changed" — the same fail-safe direction
    :func:`read_compile_fingerprint` takes.
    """
    try:
        data = json.loads(binaries_state_path(slot_dir).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    files = data.get("compile_files")
    return files if isinstance(files, dict) and files else None


def write_binaries_state(
    slot_dir: Path, built_from: str, compile_fingerprint: Optional[str] = None,
    compile_files: Optional[dict] = None,
) -> None:
    """Record what the slot's Binaries/ are being built from.

    Callers MUST write this BEFORE starting the build, not after: a build that
    crashes or is reaped mid-flight has already overwritten object files, so
    recording the dirty state only on success would leave a half-written binary
    labelled pristine. Fail-safe direction is 'assume dirty'.

    ``compile_fingerprint`` is the identity of the SOURCE the object files were
    produced from — written as None before the build and re-written with the
    real value only after the build SUCCEEDS, so a failed or partial build can
    never be mistaken for a valid cache.

    ``compile_files`` is the per-file form of the same fact and follows the same
    rule — written only alongside a real fingerprint, i.e. only after success.
    """
    Path(slot_dir).mkdir(parents=True, exist_ok=True)
    binaries_state_path(slot_dir).write_text(
        json.dumps(
            {"built_from": built_from,
             "compile_fingerprint": compile_fingerprint,
             "compile_files": compile_files or None},
            indent=2,
        ),
        encoding="utf-8",
    )


def read_compile_fingerprint(slot_dir: Path) -> Optional[str]:
    """The source fingerprint the slot's object files were built from, or None.

    None means "do not trust the cache" and is returned for a missing marker, a
    corrupt one, and a build that did not complete — all three are cases where
    the object files may not correspond to any source tree we can name.
    """
    try:
        data = json.loads(binaries_state_path(slot_dir).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    fp = data.get("compile_fingerprint")
    return fp if isinstance(fp, str) and fp else None


def compile_input_hashes(
    substrate_path: Path, prefixes: Iterable[str]
) -> dict:
    """``{repo-relative POSIX path: sha256}`` for every compile input.

    The PER-FILE form of :func:`compile_input_fingerprint`. The aggregate answers
    "did anything change?" — yes or no — and that all-or-nothing shape is what
    limited the warm win: on a t0 eval the agent changed TWO files and the
    harness told UBT that all fifty-three had, so UBT recompiled 28 actions and
    the warm grade came in at 1.35x instead of the 26x an unchanged tree gets.

    With per-file hashes the caller can bump exactly the files whose bytes
    differ. It does NOT need to reason about dependencies: making a changed
    header look new is enough, and UBT's own dependency graph cascades to every
    dependent. We only have to be right about WHICH FILES CHANGED; UBT still
    owns what must therefore be rebuilt.
    """
    out: dict = {}
    root = Path(substrate_path)
    for pref in _dedupe_prefixes(prefixes):
        base = root / pref
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if rel in out or not _is_compile_input(rel):
                continue
            try:
                out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                # Unreadable -> a value nothing can match, so it always counts
                # as changed and gets bumped. Fail-safe is "rebuild it".
                out[rel] = "<unreadable>"
    return out


def changed_compile_inputs(current: dict, built: Optional[dict]) -> list:
    """Files to bump: those whose bytes differ from what produced the cache.

    ``built`` is None/empty when the cache's provenance is unknown (a slot primed
    before per-file hashes existed, or a build that never completed) — then EVERY
    current file is returned, which is exactly the old whole-tree behaviour and
    the safe direction.

    A file present in ``built`` but absent now needs no bump: it is gone, and
    UBT notices a removed source on its own.
    """
    if not built:
        return sorted(current)
    return sorted(rel for rel, sha in current.items() if built.get(rel) != sha)


def compile_input_fingerprint(
    substrate_path: Path, prefixes: Iterable[str]
) -> str:
    """Content identity of every COMPILE INPUT under the writable prefixes.

    WHY CONTENT AND NOT MTIME. ``bump_writable_sources`` exists because mtimes
    inside a warm slot are not trustworthy: ``reset_to_pristine`` restores files
    with their pristine snapshot mtimes, which can be OLDER than object files
    built from a previous leg's edit, so UBT would skip a recompile it needed.
    The bump answers that by making EVERYTHING look new — correct, but it forces
    a full recompile of the writable module on every single verify, which is why
    a warm verify measured SLOWER than a cold one (173.7s vs 104.3s on t0,
    2026-07-31).

    Hashing the content instead answers the same question exactly, and strictly
    better: if the bytes UBT would compile are identical to the bytes it already
    compiled, the cached object files are valid — no mtime reasoning required.
    Callers use this to decide whether the bump is needed at all; UBT still owns
    the actual build decision, so this can only avoid redundant work, never
    substitute for the build itself.

    Only the WRITABLE prefixes are hashed because they are the only compile
    inputs that can differ between two verifies in the same slot: the verifier
    module and the engine come from the primed clone and ``reset_to_pristine``
    never touches them.
    """
    h = hashlib.sha256()
    root = Path(substrate_path)
    seen: set[str] = set()
    for pref in _dedupe_prefixes(prefixes):
        base = root / pref
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if not _is_compile_input(rel):
                continue
            if rel in seen:      # overlapping prefixes must not double-count
                continue
            seen.add(rel)
            h.update(rel.encode("utf-8"))
            h.update(b"\0")
            try:
                h.update(path.read_bytes())
            except OSError:
                # Unreadable source is a reason to DISTRUST the cache, so feed a
                # unique-per-path marker rather than silently skipping the file
                # (skipping would make an unreadable file hash as "absent").
                h.update(b"<unreadable>")
            h.update(b"\0")
    return h.hexdigest()


def write_meta(baseline_dir: Path, meta: dict) -> None:
    Path(baseline_dir).mkdir(parents=True, exist_ok=True)
    meta_path(baseline_dir).write_text(json.dumps(meta, indent=2), encoding="utf-8")


def is_valid(
    baseline_dir: Path,
    *,
    substrate_tree_sha: Optional[str],
    ue_version: str,
    ue_root: Optional[Path],
) -> tuple[bool, str]:
    """Whether a baseline can be used for the current verify. ``ok=False`` always
    means "fall back to cold build", never an error.

    ``ue_root`` is the engine this verify is about to build with: the slot's
    cached objects must carry that engine's BUILD (:func:`slot_engine_build` vs
    :func:`engine_build_id`), and an engine that cannot be named invalidates the
    slot. It is REQUIRED, not defaulted: the ``ue_version`` triple alone cannot
    see an in-place rebuild at the same triple, and a default would let the next
    caller inherit that blindness without saying so. ``None`` is the explicit
    "no engine to check against" form and leaves the key unenforced — every
    production entry point takes ``--ue-root`` as a required argument, so only
    offline tests can reach it."""
    if not substrate_tree_sha:
        return False, "substrate not committed (no tree SHA); cold build"
    bdir = Path(baseline_dir)
    if not bdir.exists():
        return False, f"no baseline at {bdir}"
    meta = read_meta(bdir)
    if meta is None:
        return False, "baseline meta missing/unreadable"
    if meta.get("schema") != SCHEMA:
        return False, f"baseline schema {meta.get('schema')} != {SCHEMA}"
    if meta.get("substrate_tree_sha") != substrate_tree_sha:
        return False, "substrate changed since baseline (tree SHA mismatch)"
    if meta.get("ue_version") != ue_version:
        return False, f"UE version changed ({meta.get('ue_version')} -> {ue_version})"
    build = slot_substrate_dir(bdir)
    for d in _CACHED_DIRS:
        if not (build / d).is_dir():
            return False, f"baseline missing {d}/"
    if not snapshot_dir(bdir).is_dir():
        return False, "baseline missing snapshot/"
    if ue_root is not None:
        want = engine_build_id(ue_root)
        if want is None:
            return False, (f"engine build unnameable at {ue_root} "
                           f"(Engine/Build/Build.version missing or unreadable)")
        have = slot_engine_build(bdir)
        if have is None:
            return False, "baseline attributable to no single engine build"
        if have != want:
            return False, f"engine build changed ({have} -> {want})"
    return True, "valid"


# --------------------------------------------------------------------------- #
# Snapshot (taken at prime time) / reset (per verify)
# --------------------------------------------------------------------------- #
def _dedupe_prefixes(prefixes: Iterable[str]) -> list[str]:
    """Drop exact duplicates (a prefix may appear in both ``writable`` and
    ``asset_writable``, e.g. Content/Tasks/) while preserving first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for p in prefixes:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def snapshot_scopes(slot_substrate: Path) -> list[str]:
    """Every path that must be restored per verify — i.e. the whole tree MINUS
    the compiler cache.

    Expressed as top-level entries, descending into a directory only when part of
    it is kept (``Intermediate/`` is kept for ``Build/`` and reset for everything
    else). Computed from what is ACTUALLY on disk rather than a hard-coded list,
    so a path a future UE version invents is reset by default instead of silently
    becoming a new leftover — the direction of failure this whole mechanism turns on.
    """
    root = Path(slot_substrate)
    keep = {k.replace("\\", "/") for k in COMPILER_CACHE_KEEP}
    scopes: list[str] = []
    for child in sorted(root.iterdir()):
        name = child.name
        if name in keep:                      # wholly kept (Binaries)
            continue
        if not any(k.startswith(name + "/") for k in keep):
            scopes.append(name)               # wholly reset
            continue
        # Partially kept (Intermediate): reset each child except the kept one.
        for sub in sorted(child.iterdir()):
            rel = f"{name}/{sub.name}"
            if rel not in keep:
                scopes.append(rel)
    return scopes


def make_snapshot(slot_substrate: Path, snap_dir: Path, prefixes: Iterable[str] = ()) -> int:
    """Copy the pristine NON-CACHE tree out of a freshly-built slot.

    Called once at prime time, before any submission is overlaid, so the snapshot
    captures the clean (committed) state of everything a verify may perturb.

    ``prefixes`` is accepted for call-site compatibility and is NOT the scope:
    the scope is "everything except COMPILER_CACHE_KEEP". Snapshotting only the
    agent-writable prefixes — the original behaviour — is what let the asset
    registry cache and Saved/ survive across tasks.
    """
    slot_substrate = Path(slot_substrate)
    snap_dir = Path(snap_dir)
    if snap_dir.exists():
        shutil.rmtree(snap_dir, ignore_errors=True)
    n = 0
    for rel in snapshot_scopes(slot_substrate):
        src = slot_substrate / rel
        dst = snap_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst)  # copy2 -> preserves pristine mtimes
        else:
            shutil.copy2(src, dst)
        n += 1
    return n


def _newest_mtime(root: Path) -> float:
    newest = 0.0
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            try:
                m = (Path(dirpath) / f).stat().st_mtime
            except OSError:
                continue
            if m > newest:
                newest = m
    return newest


# --------------------------------------------------------------------------- #
# Slot lock — OS advisory, non-blocking, auto-released on process death
# --------------------------------------------------------------------------- #
class SlotLock:
    """Cross-process advisory lock on a single byte of a lock file.

    Uses msvcrt (Windows) / fcntl (POSIX). Non-blocking: ``acquire`` returns
    False immediately if another process holds it. The OS drops the lock when
    the holding process exits, so a crashed verify never leaves a stale lock.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self._fh = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+")
        try:
            if os.name == "nt":
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        self._fh = fh
        return True

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fh, fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            self._fh.close()
            self._fh = None


# --------------------------------------------------------------------------- #
# WarmSlot — the acquired, ready-to-use slot
# --------------------------------------------------------------------------- #
@dataclass
class ResetStats:
    prefixes_restored: int = 0
    prefixes_removed: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass
class BumpStats:
    overlaid_touched: int = 0
    bumped_to: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass
class WarmSlot:
    slot_dir: Path                 # this slot's directory (a pool member)
    substrate_path: Path           # the fixed build path (substrate root)
    out_dir: Path
    writable_prefixes: tuple[str, ...]
    _lock: SlotLock

    def reset_to_pristine(self) -> ResetStats:
        """Return the slot to its pristine state, keeping ONLY the compiler cache.

        ANTI-CONTAMINATION IS THE CONTRACT: after this returns, the only bytes
        surviving from the previous verify are ``COMPILER_CACHE_KEEP`` — paths
        that are a pure function of the source tree, which
        ``compile_input_fingerprint`` independently certifies. Everything else is
        the pristine post-prime state.

        This used to reset only the agent-writable prefixes plus ``Config/``,
        which let ``Intermediate/CachedAssetRegistry`` (119 MB on a real slot) and
        all of ``Saved/`` carry from one task's grade into the next. L2I grades by
        introspecting the asset registry, so that was a path to a verdict decided
        by a DIFFERENT task's assets.

        The union of "restore what the snapshot has" and "delete what it does not"
        is what makes the guarantee total: a file some future UE writes into a
        directory nobody anticipated is removed because it is absent from the
        snapshot, not because anyone listed it.
        """
        snap = snapshot_dir(self.slot_dir)
        st = ResetStats()
        scopes = set(snapshot_scopes(self.substrate_path))
        # Anything the snapshot captured must come back even if the last verify
        # deleted the whole directory, so drive from the union of both sides.
        if snap.is_dir():
            for entry in snap.iterdir():
                if entry.is_dir() and any(
                    s.startswith(entry.name + "/") for s in scopes
                ):
                    scopes.update(f"{entry.name}/{c.name}" for c in entry.iterdir())
                else:
                    scopes.add(entry.name)
        for rel in sorted(scopes):
            target = self.substrate_path / rel
            src = snap / rel
            if target.exists():
                # retry-on-lock: a lingering editor handle under Saved/ would
                # otherwise leave a partial tree and break the copy below.
                robust_rmtree(target)
            if src.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                if src.is_dir():
                    shutil.copytree(src, target)  # copy2 -> pristine mtimes
                else:
                    shutil.copy2(src, target)
                st.prefixes_restored += 1
            else:
                # Present in the slot, absent from the pristine snapshot -> it was
                # created by a previous verify. Dropped, not carried forward.
                st.prefixes_removed += 1
        return st

    def bump_writable_sources(self) -> BumpStats:
        """Set the mtime of EVERY file under the writable prefixes (reset-restored
        pristine files AND the agent's overlaid files) strictly newer than every
        cached artifact, so UBT recompiles the writable module against the EXACT
        current source.

        THE CORRECTNESS GATE. Bumping only the overlaid files is NOT enough:
        when a submission EDITS an existing substrate file, the next leg's reset
        restores the pristine version with its OLD snapshot mtime — older than the
        previous leg's ``.obj`` — so UBT would skip recompiling it and silently
        reuse the previous leg's compiled behavior (a stale-`.obj` false pass,
        e.g. an empty submission "passing" because the reference leg's edit is
        still linked in). Recompiling the whole (small) writable module each verify
        is the price of correctness; the large modules (verifier tests, engine)
        stay cached, so warm is still far faster than cold.
        """
        newest = max(
            (_newest_mtime(self.substrate_path / d) for d in _CACHED_DIRS),
            default=0.0,
        )
        bump_to = max(time.time(), newest + _MTIME_MARGIN_S)
        st = BumpStats(bumped_to=bump_to)
        for pref in _dedupe_prefixes(self.writable_prefixes):
            base = self.substrate_path / pref
            if not base.exists():
                continue
            for dirpath, _dirs, files in os.walk(base):
                for f in files:
                    p = Path(dirpath) / f
                    try:
                        os.utime(p, (bump_to, bump_to))
                        st.overlaid_touched += 1
                    except OSError as e:
                        st.notes.append(f"could not bump mtime of {p}: {e}")
        return st

    def bump_files(self, rel_paths) -> BumpStats:
        """Bump ONLY the named files (repo-relative POSIX), not the whole tree.

        The precise form of :meth:`bump_writable_sources`. That method exists
        because a warm slot's mtimes are untrustworthy after a reset, and it
        answers by making EVERYTHING look new — correct, but far too coarse: on a
        t0 eval the agent changed two files and UBT recompiled 28 actions,
        because the harness had told it all fifty-three were new. The warm grade
        came in at 1.35x where an unchanged tree gets 26x.

        Given per-file hashes (``compile_input_hashes`` /
        ``changed_compile_inputs``) the caller knows exactly which files differ
        from the ones that produced the cached objects, and only those need to
        look new. Crucially this does NOT require reasoning about dependencies:
        making a changed header look new is enough, and UBT's own dependency
        graph cascades to every dependent. We are only claiming WHICH FILES
        CHANGED; UBT still decides what must be rebuilt.

        An empty ``rel_paths`` is a legitimate no-op — nothing changed, so
        nothing needs to look new.
        """
        newest = max(
            (_newest_mtime(self.substrate_path / d) for d in _CACHED_DIRS),
            default=0.0,
        )
        bump_to = max(time.time(), newest + _MTIME_MARGIN_S)
        st = BumpStats(bumped_to=bump_to)
        for rel in rel_paths:
            p = self.substrate_path / rel
            try:
                os.utime(p, (bump_to, bump_to))
                st.overlaid_touched += 1
            except OSError as e:
                # A file we cannot touch is one UBT may skip. Recorded rather
                # than swallowed so a systematic failure is visible instead of
                # silently degrading into a stale-object build.
                st.notes.append(f"could not bump mtime of {p}: {e}")
        return st

    def release(self) -> None:
        self._lock.release()


def try_acquire(
    slot_dir: Path,
    *,
    substrate_tree_sha: Optional[str],
    ue_version: str,
    writable_prefixes: Iterable[str],
    ue_root: Optional[Path],
) -> tuple[Optional[WarmSlot], str]:
    """Validate ONE slot and take its lock (non-blocking).

    Returns ``(WarmSlot, "valid")`` on success, or ``(None, reason)`` when this
    slot can't be used (no/stale baseline, or busy). Callers grading a pool
    should prefer :func:`try_acquire_any`.
    """
    sdir = Path(slot_dir)
    ok, reason = is_valid(sdir, substrate_tree_sha=substrate_tree_sha,
                          ue_version=ue_version, ue_root=ue_root)
    if not ok:
        return None, reason
    lock = SlotLock(lock_path(sdir))
    if not lock.acquire():
        return None, "slot busy (another verify holds it)"
    slot = WarmSlot(
        slot_dir=sdir,
        substrate_path=slot_substrate_dir(sdir),
        out_dir=sdir / "out",
        writable_prefixes=tuple(writable_prefixes),
        _lock=lock,
    )
    slot.out_dir.mkdir(parents=True, exist_ok=True)
    return slot, "valid"


def try_acquire_any(
    root: Path,
    *,
    substrate_tree_sha: Optional[str],
    ue_version: str,
    writable_prefixes: Iterable[str],
    ue_root: Optional[Path],
) -> tuple[Optional[WarmSlot], str]:
    """Acquire the first free, valid slot in a pool (non-blocking).

    Scans ``slot-<i>`` dirs under ``root`` and returns the first one whose
    baseline is valid AND whose lock we can take — so N concurrent verifies fan
    out across N slots, and any extra verify (or a stale/missing pool) gets a
    miss and falls back to cold. Never blocks; never changes a verdict.
    """
    slots = discover_slot_dirs(root)
    if not slots:
        return None, f"no warm pool at {root} (prime with build_warm_baseline.py)"
    last_reason = "all slots busy or invalid"
    for sdir in slots:
        slot, reason = try_acquire(
            sdir,
            substrate_tree_sha=substrate_tree_sha,
            ue_version=ue_version,
            writable_prefixes=writable_prefixes,
            ue_root=ue_root,
        )
        if slot is not None:
            return slot, reason
        last_reason = reason
    return None, last_reason
