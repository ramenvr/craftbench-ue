"""Fairness staging for live-project agent runs (aura-mcp / unreal-mcp).

During a live-project run the agent drives the REAL running editor, so the
live working tree IS the substrate it can read. To keep the eval
uncontaminated we must hide the verifier answer key from the agent phase:

  1. Move AGENT_WRITABLE.json out of the live tree (it leaks the writable map
     and the deny prefixes — i.e. where the verifier-only module lives).
  2. Replace the C++ fixture bodies under Source/CraftBenchTests/ with one-line
     comment stubs so the agent (or any editor inspection it triggers) cannot
     read the L2 assertions.

Both are RESTORED byte-for-byte before the snapshot/verify step, so:
  * the live working tree is identical to pre-run (git stays clean), and
  * grading is unaffected regardless — run_task.py copies the REPO substrate,
    not the live tree, and hashes its CraftBenchTests/ against
    substrate_hashes.json. We never touch the repo substrate during a live run.

Dependency direction is one-way: CraftBenchTests (editor-only) → CraftBenchTemplate
(runtime). The runtime module the agent edits never links CraftBenchTests, and
the already-running editor has the real fixtures compiled in memory — so stubbing
the .h/.cpp bodies carries no compile risk for the agent's own edits.

.Build.cs is deliberately LEFT UNSTUBBED (it contains no answer-key logic; its
unchanged deps/include-paths keep the editor-target include graph intact if the
agent triggers a recompile). Only the .h/.cpp fixture bodies are stubbed.

All functions operate purely on the filesystem and are unit-tested on a temp
tree — no editor, no network.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from substrate_check import check_substrate_clean, porcelain_path

# The verifier-only editor module whose fixture bodies hold the L2 answer key.
_CRAFTBENCH_TESTS_REL = "Source/CraftBenchTests"
_MANIFEST_NAME = "AGENT_WRITABLE.json"

# The agent-WRITABLE runtime module. It ships every task's scaffold actor at
# once; for any single run all but the active task's scaffolds are decoys the
# agent can grep into and edit by mistake (the gp-spawn-sequence run edited
# TaskActor — gp-timer-delayed-destroy's scaffold — instead of SpawnHostActor).
_WRITABLE_MODULE_REL = "Source/CraftBenchTemplate"
# Subdir under fairness_backup/ where isolated (foreign-task) sources are parked.
_ISOLATED_SUBDIR = "TemplateIsolated"
# Each scaffold source self-declares its owning task in a header comment, e.g.
# "// ASpawnHostActor — pre-existing actor pair for task gp-spawn-sequence." or
# "// Reference solution for task gp-inventory-save-roundtrip." Task IDs are
# kebab-case (gp-spawn-sequence, t0-sanity-log-on-beginplay). The id may wrap
# onto the next comment line ("… fixture for task\n// gp-harvestable-regrow" —
# three fixtures do this today), so an optional newline + comment prefix is
# tolerated between "for task" and the id.
_FOR_TASK_RE = re.compile(
    r"for task\s+(?://+\s*)?([a-z0-9][a-z0-9-]*)", re.IGNORECASE)
# Only the header comment carries the tag; cap the read so a huge file is cheap.
_HEAD_BYTES = 4096

# Subdir under fairness_backup/ where whole per-task DIRECTORIES are parked by
# stage_task_tree_isolation_hide (the folder-per-task migration's counterpart to
# the marker-based file isolation above).
_TREE_ISOLATED_SUBDIR = "TreeIsolated"

# Subdir under fairness_backup/ where the pre-apply bytes of Config/*.ini files
# mutated by the B7 per-task UE config overlay are parked (see
# stage_config_overlay_apply).
_CONFIG_OVERLAY_SUBDIR = "ConfigOverlay"
# The live project's UE config dir the overlay appends into (agent-denied).
_CONFIG_DIR_REL = "Config"
# Roots whose IMMEDIATE child directories are per-task folders. Source roots are
# per-task by construction (Tasks/<id>/); the Content roots additionally require
# a task-id-looking name (see _TASK_DIR_RE) because the engine/editor drops its
# own folders under Content/ (Developers/, __ExternalActors__/, ...). The tuple
# is the UNION across substrates (both writable modules); a root absent from a
# given tree no-ops, so listing both is safe on either substrate. Keep in
# lockstep with tools/verify-single/task_layout.py:PER_TASK_ROOTS.
_PER_TASK_ROOTS = (
    "Source/CraftBenchTemplate/Tasks",
    "Source/CraftBenchTests/Tasks",
    "Source/ThirdPerson/Tasks",
    "Content/Maps",
    "Content/Tasks",
)
# Kebab-case task id (t0-sanity-log-on-beginplay, gp-spawn-sequence).
_TASK_DIR_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# What we write into each stubbed .h/.cpp. A bare comment — the live editor has
# the real classes compiled in memory and the agent's runtime module does not
# depend on these.
#
# THAT SECOND CLAUSE WAS THE UNSTATED PREMISE, and it only held while nothing
# recompiled. It does not: see the block under _STUB_BODY. A bare comment is
# valid C++, so a mid-drive rebuild compiles the stubs into the module.
_STUB_BODY = (
    "// CraftBench fairness stub — verifier source hidden during agent phase.\n"
)

# --------------------------------------------------------------------------- #
# THE STUB IS COMPILABLE, AND THAT BRICKS THE RIG (issue 11, 2026-08-22).
#
# Arm C's agent has Aura's `recompile_unreal_project`. One agent recompiled
# mid-drive while every fixture body was stubbed, baking the stubs into
# `UnrealEditor-CraftBenchTests.dll` — 49,152 bytes against 837,632 for a real
# build. The engine then loads the verifier module, cannot initialise it, and
# calls EngineExit: NO editor starts, on either substrate, for any lane. Nine
# consecutive cells died at ~2 min each while the stack log blamed "crash on
# startup". CraftBenchTemplate's copy carried the same 49,152 bytes dated 08-19 —
# that substrate had been bricked for DAYS with nobody noticing.
#
# The SOURCES restore correctly (measured: 100/100 match HEAD, 0 stubbed). Only
# the build PRODUCTS are poisoned, which is exactly why nothing that inspects the
# source tree can see it, and why the fix belongs on the restore path.
#
# The invariant, stated once: NO AGENT ACTION MAY LEAVE BUILD PRODUCTS THE NEXT
# CELL INHERITS. Enforced by fingerprinting the module's binaries at hide time
# and comparing at restore — a change means they were rebuilt while the stubs
# were live, so they are invalidated and the next build regenerates them.
#
# CONDITIONAL ON PURPOSE: invalidating every time would force a full editor
# rebuild on every cell, which costs more wall clock than the bug does.
_MODULE_BUILD_GLOBS = (
    "Binaries/*/UnrealEditor-CraftBenchTests.*",
    "Binaries/*/*CraftBenchTests*.dll",
    "Binaries/*/*CraftBenchTests*.pdb",
    "Binaries/*/*CraftBenchTests*.exp",
    "Binaries/*/*CraftBenchTests*.lib",
)
#: What the REBUILD DETECTOR reads — the loadable module only, deliberately NOT
#: the .pdb. The .pdb is PARKED during the agent phase (issue 12), so including it
#: would make the hide-time baseline and the restore-time reading differ by the
#: park itself: every clean run would read as "rebuilt" and pay a full editor
#: rebuild. A rebuild always rewrites the DLL, so the DLL alone is sufficient
#: evidence, and this decouples detection from the park's ORDERING entirely —
#: better than getting that ordering right, because an ordering is easy to break
#: later and this cannot be. (The first cut of the park had exactly that bug.)
_MODULE_FINGERPRINT_GLOBS = (
    "Binaries/*/UnrealEditor-CraftBenchTests.dll",
    "Binaries/*/*CraftBenchTests*.dll",
)
#: Deleting the DLL alone was MEASURED insufficient: the next build failed
#: "Unable to find parent class type ... ACraftBenchFunctionalTest" because UHT's
#: cached parse of the base class ALSO dated from when the header was a stub.
_MODULE_INTERMEDIATE_REL = "Intermediate/Build"
#: Dropped when invalidation could not finish — an editor still holding a handle
#: is the normal reason, since the restore runs before the editor is reaped. A
#: poisoned box that could not be cleaned must REFUSE the next cell rather than
#: run it, and this marker is the hand-off to that refusal.
BUILD_POISON_MARKER = ".cb-build-poisoned.json"


#: The verifier module's DEBUG SYMBOLS. Parked for the agent phase, because the
#: source stub hides the fixture and the compiled form gives it straight back
#: (audit issue 12, 2026-08-22): the .pdb carries full source paths, a symbol per
#: fixture and 51 tolerance hits, and it sits inside the workspace the agent is
#: handed.
#:
#: WHO THIS ACTUALLY PROTECTS AGAINST, measured rather than assumed — the answer
#: differs by arm and the audit's "reachable from BOTH arms" is too strong:
#:   * unreal-mcp / claude-p keep Bash, so `strings` / `grep -a` dump it verbatim.
#:     Real leak, closed by this.
#:   * aura-mcp denies Bash and keeps only Read/Glob/Grep. Grep is ripgrep with no
#:     --text escape, so it reports "binary file matches" and prints NOTHING; Read
#:     does return raw bytes, but locating one assertion by paging a 112 MB file is
#:     not a realistic path.
#: So the leak biases the NON-Aura arms — the opposite direction from issue 5's
#: index leak, which is why closing it matters for the comparison rather than for
#: one lane.
#:
#: THE .DLL IS NOT PARKED AND CANNOT BE: the running editor has it loaded, and
#: Windows locks a loaded module's file. It carries assertion text too, so THIS
#: DOES NOT CLOSE THE LEAK — it removes the larger and more structured half.
#: Detection for the rest stays `leak_audit.py`'s fixture markers.
_MODULE_SYMBOL_GLOBS = (
    "Binaries/*/*CraftBenchTests*.pdb",
)
#: Subdir under fairness_backup/ where parked symbols live.
_SYMBOLS_SUBDIR = "ModuleSymbols"


def stage_module_symbols_hide(project_dir: Path, state: "FairnessState",
                              log=None) -> None:
    """Move the verifier module's .pdb aside for the agent phase.

    A same-volume ``os.rename`` via ``_robust_move``, so this is instant on a
    112 MB file rather than a copy — the backup root lives under ``run_dir``,
    which is on the repo's volume.

    FAIL-OPEN on purpose. This is leak REDUCTION, not a correctness gate: a
    symbol file the editor happens to hold must not abort a paid drive, and an
    un-parked .pdb leaves the run exactly as exposed as every run before this
    existed. It is logged, so a persistent failure is visible rather than
    assumed away.
    """
    backup_root = Path(state.backup_root) / _SYMBOLS_SUBDIR
    for pattern in _MODULE_SYMBOL_GLOBS:
        for src in sorted(Path(project_dir).glob(pattern)):
            rel = src.relative_to(project_dir).as_posix()
            dst = backup_root / rel
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                _robust_move(src, dst)
            except Exception as exc:  # noqa: BLE001
                if log:
                    log(f"  WARN  could not park {rel} ({exc}); the compiled "
                        f"fixture's symbols stay readable this run")
                continue
            state.parked_symbols.append(rel)
    if log and state.parked_symbols:
        log(f"  ..    parked {len(state.parked_symbols)} verifier symbol "
            f"file(s) for the agent phase")


def stage_module_symbols_restore(state: "FairnessState",
                                 project_dir: Path) -> None:
    """Put the parked .pdb files back. Idempotent; never raises."""
    backup_root = Path(state.backup_root) / _SYMBOLS_SUBDIR
    for rel in list(getattr(state, "parked_symbols", [])):
        src = backup_root / rel
        if not src.exists():
            continue                       # already restored
        dst = Path(project_dir) / rel
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            _robust_move(src, dst)
        except Exception:  # noqa: BLE001
            # Same posture as the rest of restore: a symbol file that cannot come
            # back is a rebuild away, and raising here would skip the steps that
            # put the SOURCE tree back.
            continue


def module_build_fingerprint(project_dir: Path) -> str:
    """Cheap identity of the verifier module's build products.

    ``name:size:mtime_ns`` per artifact, sorted. Deliberately not a hash: the
    only question is "were these bytes REPLACED during the agent phase", a
    rebuild always moves size or mtime, and hashing a multi-MB DLL twice per cell
    buys nothing. Returns "" for a never-built checkout, which compares equal to
    itself and so cannot false-positive.
    """
    parts = []
    for pattern in _MODULE_FINGERPRINT_GLOBS:
        for p in sorted(Path(project_dir).glob(pattern)):
            try:
                st = p.stat()
            except OSError:
                continue
            parts.append(f"{p.name}:{st.st_size}:{st.st_mtime_ns}")
    return "|".join(sorted(set(parts)))


def _invalidate_module_build(project_dir: Path, log=None):
    """Delete the verifier module's build products. ``(complete, failures)``.

    Best-effort by design: this can run while the drive's editor still holds a
    handle, and a partial delete plus the marker is strictly better than raising
    out of a restore path whose remaining steps put the SOURCE tree back.
    """
    failed = []
    project_dir = Path(project_dir)
    for pattern in _MODULE_BUILD_GLOBS:
        for p in sorted(project_dir.glob(pattern)):
            try:
                p.unlink()
            except OSError as exc:
                failed.append(f"{p.name}: {exc}")
    inter = project_dir / _MODULE_INTERMEDIATE_REL
    if inter.is_dir():
        try:
            _robust_rmtree(inter)
        except Exception as exc:                          # noqa: BLE001
            failed.append(f"{_MODULE_INTERMEDIATE_REL}: {exc}")
    if inter.exists():
        failed.append(f"{_MODULE_INTERMEDIATE_REL}: still present after rmtree")
    if log:
        log("  fairness: the verifier module's build products were REWRITTEN "
            "during the agent phase. A recompile while fixtures are stubbed bakes "
            "the stubs in and bricks every later cell, so they are invalidated "
            "here and the next build regenerates them.")
        for f in failed:
            log(f"    NOT removed — {f}")
    return (not failed), failed


def build_poison_marker_path(project_dir: Path) -> Path:
    return Path(project_dir) / BUILD_POISON_MARKER


def verifier_build_suspect(project_dir: Path):
    """Why this project must not be driven, or ``None`` if it is fit.

    The pre-cell half, and the half that survives a CRASH: a run that dies before
    its restore invalidates nothing, so the next cell inherits the poisoned DLL
    exactly as the nine dead cells did. The preflight that passed all nine had 21
    checks and not one of them asked this.
    """
    marker = build_poison_marker_path(project_dir)
    if marker.is_file():
        try:
            why = json.loads(marker.read_text(encoding="utf-8")).get("reason", "")
        except (OSError, ValueError):
            why = ""
        return (f"{BUILD_POISON_MARKER} is present: the verifier module's build "
                f"products were poisoned and could not be cleaned automatically"
                + (f" ({why})" if why else "")
                + f". Delete {Path(project_dir) / _MODULE_INTERMEDIATE_REL} plus "
                  f"the Binaries/*/UnrealEditor-CraftBenchTests.* artifacts, "
                  f"rebuild the editor target, then remove the marker.")
    return _declared_module_missing(project_dir)


def _declared_module_missing(project_dir):
    """Why the editor cannot start: a module the manifest DECLARES has no binary.

    THE OTHER HALF OF THE SAME DEFECT, measured 2026-08-25 and it cost most of a
    day. The check above asks "are the build products POISONED". It does not ask
    "are they THERE" -- and the invalidation this module performs is a DELETE:

        fairness: the verifier module's build products were REWRITTEN during the
        agent phase ... so they are invalidated here and the next build
        regenerates them.

    "The next build" is L1, which builds a WORKDIR COPY. The LIVE project is
    never rebuilt, so after the first cell whose agent recompiles, the live tree
    permanently declares `CraftBenchTests` in `Binaries/*/UnrealEditor.modules`
    with no DLL beside it. UE reads that manifest, cannot load the module, and
    exits CLEANLY about twelve seconds in.

    Every downstream message was misleading, which is why this returns a reason
    rather than leaving the diagnosis to them:

      * unreal-mcp  -> "editor MCP never became ready at :8000"
      * aura-mcp    -> "editor launched but EXITED before binding :30010 - crash
                        on startup (e.g. missing/out-of-date plugin binary)"

    The second one sent me to rebuild the Aura plugin, which was never broken:
    the editor log showed `LogAura:` lines and a clean `LogExit`. The sweep's own
    ISSUE 11 note records the same trap from a previous occurrence -- "nine
    consecutive cells died that way at ~2 min each while the stack log blamed
    'crash on startup', and the 21-check preflight passed every one of them".

    Fail OPEN on an unreadable manifest: a project whose manifest cannot be
    parsed is not thereby proven unfit, and refusing to drive on a read error
    would turn a diagnostic into an outage.
    """
    root = Path(project_dir) / "Binaries"
    try:
        manifests = sorted(root.glob("*/UnrealEditor.modules"))
    except OSError:
        return None

    # THE HOLE THIS CLOSES, measured 2026-08-26 while block 1 was running. The
    # loop below asks "does every module the manifest DECLARES have a binary",
    # and answers CLEAN when there is no manifest to read. But the manifest
    # itself is ABSENT is just as fatal, and the engine says so in as many words
    # -- a modal dialog, which in a headless editor is an immediate exit:
    #
    #     Message dialog closed, result: Ok, title: 消息,
    #     text: 游戏模块"ThirdPerson"无法被找到。请确认此模块存在且已被编译。
    #     LogCore: Engine exit requested (reason: EngineExit() was called)
    #
    # ("The game module 'ThirdPerson' could not be found.") Every aura-mcp cell
    # on gp-glide-stamina-cpp died that way, ~1 minute each, while this function
    # returned None and the heal therefore never fired. The DLLs were both
    # present; `UnrealEditor.modules` and `<Target>Editor.target` were not --
    # the shape a build interrupted after it deletes them and before it rewrites
    # them leaves behind.
    #
    # Scoped to the case that is PROVEN fatal: binaries exist, manifest does not.
    # A project with no Binaries tree at all is a source-only checkout and says
    # nothing about fitness (the caller's own no-binaries test pins that), and a
    # manifest that is present but unparseable stays fail-open below -- unreadable
    # is not the same as absent, and refusing on a read error would turn a
    # diagnostic into an outage.
    if not manifests:
        try:
            built = sorted(root.glob("*/UnrealEditor-*.dll"))
        except OSError:
            return None
        if built:
            where = built[0].parent.name
            return (f"{where}/UnrealEditor.modules is ABSENT while "
                    f"{len(built)} module DLL(s) sit beside it. The editor "
                    "cannot find the game module without that manifest: it "
                    "raises a modal dialog (\"could not be found ... ensure "
                    "this module exists and is compiled\") and, headless, "
                    "exits a few seconds in. The lanes report that as 'MCP "
                    "never became ready' or 'crash on startup', both of which "
                    "point away from the cause. Rebuild the editor target for "
                    "this project; a workdir L1 build does NOT regenerate the "
                    "LIVE project's binaries.")
        return None

    for man in manifests:
        try:
            declared = json.loads(man.read_text(encoding="utf-8")).get("Modules") or {}
        except (OSError, ValueError):
            continue
        missing = []
        for name, dll in declared.items():
            if not isinstance(dll, str) or not dll:
                continue
            if not (man.parent / dll).is_file():
                missing.append(name)
        if missing:
            return (f"{man.parent.name}/UnrealEditor.modules declares "
                    f"{', '.join(sorted(missing))} but the binary is MISSING. "
                    "The editor will read that manifest, fail to load the "
                    "module and exit cleanly a few seconds in - which the "
                    "lanes report as 'MCP never became ready' or 'crash on "
                    "startup (missing/out-of-date plugin binary)', both of "
                    "which point away from the cause. Rebuild the editor "
                    "target for this project; a workdir L1 build does NOT "
                    "regenerate the LIVE project's binaries.")
    return None


def classify_deliverable_file(rel: str, content_head: str,
                              active_task_id: str) -> str:
    """Which task does a deliverable file belong to: 'active', 'foreign', or
    'unknown' (agent-authored new files carry no marker — that's normal).

    Path wins (folder-per-task layout: .../Tasks/<id>/... or Content/Tasks/
    <id>/...); otherwise the 'for task <id>' header marker in the content
    (the wrong-actor failure recreates a foreign scaffold INCLUDING its
    marker comment — the 2026-07-11 signature)."""
    active = _bare_task_id(active_task_id)
    parts = rel.replace("\\", "/").split("/")
    for anchor in ("Tasks",):
        if anchor in parts:
            idx = parts.index(anchor)
            if idx + 1 < len(parts) - 1 and _TASK_DIR_RE.match(parts[idx + 1]):
                return "active" if parts[idx + 1] == active else "foreign"
    declared = set(_FOR_TASK_RE.findall(content_head[:_HEAD_BYTES]))
    declared = {d.lower() for d in declared if _TASK_DIR_RE.match(d)}
    if not declared:
        return "unknown"
    return "active" if active in declared else "foreign"


def deliverable_contamination(files, active_task_id, read_head) -> Optional[dict]:
    """The context-contamination detector: a deliverable that contains
    foreign-task files and NOTHING for the active task is the signature of
    the client-context leak (agent solved/recreated another task's scaffold
    — proven 2026-07-11, SpawnerActor recreated byte-for-byte during a t0
    run). Returns {'foreign_files': [...]} when suspected, else None.
    ``files`` = deliverable-relative paths; ``read_head`` = rel -> first
    bytes of the DELIVERED content (injected for testability)."""
    verdicts = {}
    for rel in files:
        try:
            head = read_head(rel)
        except OSError:
            head = ""
        verdicts[rel] = classify_deliverable_file(rel, head, active_task_id)
    foreign = [r for r, v in verdicts.items() if v == "foreign"]
    if foreign and not any(v == "active" for v in verdicts.values()):
        return {"foreign_files": foreign}
    return None


# Per-task dir moves need a longer budget than the default. Measured
# 2026-08-22 on arm C: an indexer that runs during the Aura-staged bring-up
# opens content files in a repeating cycle, so the map file is FREE most of the
# time but the default ~12.5s budget can land entirely inside held windows —
# 4 of 4 cells failed the first hide and every retry then succeeded, wasting a
# full stack bring-up (~5-10 min) per cell. A dir rename needs every file inside
# free at once, so patience is the fix; this only makes the hide wait longer and
# it still fails CLOSED.
_ISOLATION_MOVE_RETRIES = 14


def _robust_move(src: Path, dst: Path, *, retries: int = 6,
                 base_delay: float = 0.5) -> None:
    """Same-volume rename that retries through the transient Windows share
    violation a lingering editor/OneDrive handle leaves on a file inside the
    tree (WinError 5/32) — the fairness twin of cb._robust_rmtree. Deliberately
    NOT shutil.move: its copy+rmtree fallback half-deletes the source when the
    lock outlives the copy, leaving the live tree partially stripped (bit the
    gp-gas-launch tree isolation on 2026-07-10). os.rename either fully
    succeeds or leaves the source untouched. Raises the last OSError (with the
    locked path) after the final retry."""
    last: OSError | None = None
    for attempt in range(retries):
        try:
            os.rename(src, dst)
            return
        except OSError as exc:
            last = exc
            time.sleep(min(base_delay * (2 ** attempt), 3.0))
    raise OSError(
        f"fairness move still locked after {retries} attempts: {src} -> {dst} "
        f"— a process holds a file inside it open (a live editor with the map "
        f"loaded, or OneDrive sync); close/restart the holder and re-run"
    ) from last


def _robust_rmtree(path: Path, *, retries: int = 6,
                   base_delay: float = 0.5) -> bool:
    """rmtree with the same retry/backoff, returning True iff the tree is gone
    (never raises). Callers decide whether a survivor is fatal: a live copy
    that must disappear for fairness IS; a parked backup copy is not."""
    for attempt in range(retries):
        if not path.exists():
            return True
        try:
            shutil.rmtree(path)
            return True
        except OSError:
            time.sleep(min(base_delay * (2 ** attempt), 3.0))
    return not path.exists()


@dataclass
class FairnessState:
    """Records exactly what stage_fairness_hide moved/stubbed, for restore."""

    backup_root: Path
    stubbed_rels: List[str] = field(default_factory=list)
    moved_manifest: bool = False
    # Foreign-task scaffold sources moved entirely out of the writable runtime
    # module by stage_task_isolation_hide (paths relative to that module dir).
    isolated_rels: List[str] = field(default_factory=list)
    # Whole per-task DIRECTORIES moved aside by stage_task_tree_isolation_hide:
    # (src rel to project_dir, backup rel to backup_root) per directory.
    isolated_dirs: List[Tuple[str, str]] = field(default_factory=list)
    # Config/*.ini files mutated by stage_config_overlay_apply (the B7 per-task
    # UE config overlay): (ini_name, created, backup rel to backup_root) per
    # ini. `created` files had no pre-apply bytes (backup rel is "") and are
    # DELETED on restore; the rest are restored byte-identically from backup.
    applied_config: List[Tuple[str, bool, str]] = field(default_factory=list)
    # Repo-level answer material hidden by stage_repo_answer_hide: (absolute
    # src dir, absolute hidden sibling dir) per rename. Siblings live in the
    # SAME parent (".cb-fairness-hidden__<name>") so the move is a same-volume
    # os.rename, and so a crashed run's leftovers are discoverable by naming
    # convention even without this record.
    repo_hidden: List[Tuple[str, str]] = field(default_factory=list)
    # The project the hide was staged on (resolved path string). Persisted so
    # crash recovery can refuse to restore a backup into the WRONG project.
    # "" for states built before persistence existed / by hand in tests.
    project_dir: str = ""
    # The verifier module's build-product fingerprint AT HIDE TIME. Compared on
    # restore: a change means something rebuilt the module while its sources were
    # stubbed, so the binaries now contain the stubs and must not be inherited by
    # the next cell (issue 11). "" = not captured (an old state, or a
    # never-built checkout) and then the comparison is skipped rather than
    # guessed at — an absent baseline is not evidence of a rewrite.
    # None = never captured (a pre-2026-08-22 state, or a hand-built checkout)
    # and the comparison is skipped. "" = captured and nothing was built, which
    # IS comparable: module_build_fingerprint returns "" for a project with no
    # artifacts and _invalidate_module_build DELETES them, so the cell after any
    # successful invalidation baselines as "" and a truthiness test would skip
    # exactly one cell after an agent proved it rebuilds mid-drive.
    module_build_fp: Optional[str] = None
    # Verifier-module .pdb files parked by stage_module_symbols_hide, as
    # project-relative POSIX paths. Empty when nothing was parked (no symbols on
    # disk, or the move failed and was logged) — never a reason to abort.
    parked_symbols: List[str] = field(default_factory=list)
    # MERGE-parked copies of answer material: (source dir, park dir) per dir.
    # Merge-back rather than a rename because the source dir stays LIVE while
    # parked — the indexer keeps writing docs into it, and a recompile recreates
    # UHT's output — so whatever came back on its own wins. Named for its first
    # user (stage_index_cache_hide); stage_generated_code_hide shares it, and
    # the name is kept so persisted state from before that stays readable.
    index_hidden: List[Tuple[str, str]] = field(default_factory=list)


# Persisted next to the backed-up files so a hard-killed run (taskkill /F,
# power loss — anything the in-process try/finally can't survive) leaves a
# machine-readable restore recipe alongside the bytes. Without it the state
# lived only in memory and crash recovery meant manual git surgery.
_STATE_FILE_NAME = "fairness_state.json"
_STATE_SCHEMA = "craftbench.fairness-state/v1"


def _persist_state(state: FairnessState, project_dir: Path) -> None:
    """Write/refresh ``backup_root/fairness_state.json`` after a hide stage.

    Best-effort: a persist failure must never abort the run it serves (the
    in-memory state still drives the normal restore path) — it only degrades
    crash recovery back to layout inference.
    """
    if not state.project_dir:
        try:
            state.project_dir = str(Path(project_dir).resolve())
        except OSError:
            state.project_dir = str(project_dir)
    payload = {
        "schema": _STATE_SCHEMA,
        "project_dir": state.project_dir,
        "stubbed_rels": list(state.stubbed_rels),
        "moved_manifest": state.moved_manifest,
        "isolated_rels": list(state.isolated_rels),
        "isolated_dirs": [list(t) for t in state.isolated_dirs],
        "applied_config": [list(t) for t in state.applied_config],
        "repo_hidden": [list(t) for t in state.repo_hidden],
        "index_hidden": [list(t) for t in getattr(state, "index_hidden", [])],
        # Persisted so CRASH recovery can make the same call the normal restore
        # makes. A run killed before its restore is exactly how a poisoned DLL
        # reached the next cell in the first place.
        "module_build_fp": getattr(state, "module_build_fp", None),
        "parked_symbols": list(getattr(state, "parked_symbols", [])),
    }
    try:
        state.backup_root.mkdir(parents=True, exist_ok=True)
        (state.backup_root / _STATE_FILE_NAME).write_text(
            json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass


def _infer_state_from_layout(backup_root: Path) -> FairnessState:
    """Reconstruct a FairnessState from the backup dir CONVENTIONS alone —
    the fallback for backups written before fairness_state.json existed.

    Everything is recoverable from layout except ``applied_config``'s
    ``created`` flags: a CREATED Config ini left no parked bytes, so it can't
    be inferred — it stays behind as an untracked file (harmless: untracked
    files never trip the DIRTY-SUBSTRATE gate)."""
    state = FairnessState(backup_root=backup_root)
    state.moved_manifest = (backup_root / _MANIFEST_NAME).is_file()
    tests_backup = fixture_backup_root(backup_root)
    if tests_backup.is_dir():
        state.stubbed_rels = sorted(
            p.relative_to(tests_backup).as_posix()
            for p in tests_backup.rglob("*") if p.is_file())
    isolated = backup_root / _ISOLATED_SUBDIR
    if isolated.is_dir():
        state.isolated_rels = sorted(
            p.relative_to(isolated).as_posix()
            for p in isolated.rglob("*") if p.is_file())
    tree = backup_root / _TREE_ISOLATED_SUBDIR
    if tree.is_dir():
        for root_key_dir in sorted(tree.iterdir()):
            if not root_key_dir.is_dir():
                continue
            src_root = root_key_dir.name.replace("__", "/")
            for child in sorted(root_key_dir.iterdir()):
                if not child.is_dir():
                    continue
                state.isolated_dirs.append((
                    f"{src_root}/{child.name}",
                    f"{_TREE_ISOLATED_SUBDIR}/{root_key_dir.name}/{child.name}",
                ))
    overlay = backup_root / _CONFIG_OVERLAY_SUBDIR
    if overlay.is_dir():
        for ini in sorted(overlay.iterdir()):
            if ini.is_file():
                state.applied_config.append(
                    (ini.name, False, f"{_CONFIG_OVERLAY_SUBDIR}/{ini.name}"))
    return state


def load_fairness_state(backup_root: Path) -> FairnessState:
    """Rebuild the FairnessState for an on-disk ``fairness_backup`` dir.

    Layout inference (see :func:`_infer_state_from_layout`) is the base —
    it enumerates exactly the parked bytes restore consumes, so a stale,
    torn, or absent state file can never cause an under-restore. The
    persisted ``fairness_state.json`` overlays only what layout can't carry:
    ``project_dir`` (heal targeting) and CREATED config-overlay inis (they
    parked no bytes but must be deleted on restore). Never raises."""
    backup_root = Path(backup_root)
    state = _infer_state_from_layout(backup_root)
    try:
        data = json.loads(
            (backup_root / _STATE_FILE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return state
    if not isinstance(data, dict) or data.get("schema") != _STATE_SCHEMA:
        return state
    state.project_dir = data.get("project_dir") or ""
    raw_cfg = data.get("applied_config")
    if isinstance(raw_cfg, list):
        inferred_inis = {t[0] for t in state.applied_config}
        state.applied_config += [
            (t[0], bool(t[1]), t[2]) for t in raw_cfg
            if isinstance(t, list) and len(t) == 3
            and isinstance(t[0], str) and isinstance(t[2], str)
            and t[0] not in inferred_inis]
    raw_rh = data.get("repo_hidden")
    if isinstance(raw_rh, list):
        state.repo_hidden = [
            (t[0], t[1]) for t in raw_rh
            if isinstance(t, list) and len(t) == 2
            and isinstance(t[0], str) and isinstance(t[1], str)]
    raw_ih = data.get("index_hidden")
    if isinstance(raw_ih, list):
        state.index_hidden = [
            (t[0], t[1]) for t in raw_ih
            if isinstance(t, list) and len(t) == 2
            and isinstance(t[0], str) and isinstance(t[1], str)]
    # The build-product baseline (issue 11). Layout cannot carry it, and it is
    # the CRASH path that matters: a run killed before its restore is exactly how
    # a poisoned DLL reached the next cell. Recovering it here lets the leftover
    # restore make the same invalidation call the normal restore makes.
    raw_fp = data.get("module_build_fp")
    if isinstance(raw_fp, str):
        state.module_build_fp = raw_fp
    # Parked symbols: layout inference cannot carry these either, and a crashed
    # run that leaves the .pdb parked would otherwise never get it back.
    raw_sym = data.get("parked_symbols")
    if isinstance(raw_sym, list):
        state.parked_symbols = [x for x in raw_sym if isinstance(x, str)]
    return state


def _is_fixture_source(rel: str) -> bool:
    """True for the .h/.cpp fixture bodies we stub (NOT .Build.cs, NOT others)."""
    lower = rel.lower()
    if lower.endswith(".build.cs"):
        return False
    return lower.endswith(".h") or lower.endswith(".cpp")


#: Written inside ``fairness_backup/`` so the CRASH-RECOVERY rebuild can still
#: find the parked originals after the process that parked them is gone.
_FIXTURE_POINTER = "CraftBenchTests.parked"


def fixture_backup_root(backup_root: Path) -> Path:
    """Where the ORIGINAL fixture bodies live during a drive - OUTSIDE ``runs/``.

    WHY THEY MOVED, measured 2026-08-26/27. The hide used to copy the answer key
    to ``runs/<this-run>/fairness_backup/CraftBenchTests/`` -- inside the agent's
    own reachable filesystem. The agent runs under
    ``--permission-mode bypassPermissions``, which makes ``--add-dir`` and the
    deliberately "neutral cwd" HINTS rather than boundaries, so the process can
    read anywhere on the box. Across 53 cells, seven touched that directory and
    two read the fixture bodies back in full and were voided for it. The hide had
    MOVED the key and left it in the same room.

    Now it goes to the system temp area, keyed by run-dir name so two concurrent
    cells cannot collide. `runs/` keeps an empty-ish ``fairness_backup/`` holding
    the manifest and a pointer file, which preserves the two things that read the
    directory's EXISTENCE rather than its contents: the crash-recovery rebuild in
    ``rebuild_state_from_backup`` and the ``runs_clean`` interlock that never
    deletes a unit still holding one.

    This is a hiding place, not a permission boundary -- an agent that guessed
    the path could still read it. It stops discovery, which is how both real
    leaks happened (one arrived via a worktree-wide ``Glob``), and it takes the
    key out of the tree the agent is invited to explore.
    """
    ptr = backup_root / _FIXTURE_POINTER
    try:
        if ptr.is_file():
            parked = Path(ptr.read_text(encoding="utf-8").strip())
            if str(parked):
                return parked
    except OSError:
        pass
    key = backup_root.parent.name or "unknown-run"
    return Path(tempfile.gettempdir()) / "cb-fairness-fixture-park" / key


def stage_fairness_hide(project_dir: Path, run_dir: Path) -> FairnessState:
    """Hide the verifier answer key from the live tree for the agent phase.

    1. Move AGENT_WRITABLE.json -> run_dir/fairness_backup/AGENT_WRITABLE.json
       (out of the live tree entirely).
    2. For every .h/.cpp under Source/CraftBenchTests/: copy the ORIGINAL to
       run_dir/fairness_backup/CraftBenchTests/<rel>, then overwrite the live
       file with a one-line comment stub. .Build.cs and any other files are
       left untouched (so the editor-target include graph is unchanged).

    Returns a FairnessState recording exactly what was moved/stubbed.
    """
    backup_root = run_dir / "fairness_backup"
    backup_root.mkdir(parents=True, exist_ok=True)
    state = FairnessState(backup_root=backup_root)

    # 1. Move the manifest aside.
    manifest_src = project_dir / _MANIFEST_NAME
    if manifest_src.exists():
        manifest_dst = backup_root / _MANIFEST_NAME
        shutil.copy2(manifest_src, manifest_dst)
        manifest_src.unlink()
        state.moved_manifest = True

    # 2. Stub the fixture .h/.cpp bodies.
    tests_dir = project_dir / _CRAFTBENCH_TESTS_REL
    if tests_dir.is_dir():
        tests_backup_root = fixture_backup_root(backup_root)
        tests_backup_root.mkdir(parents=True, exist_ok=True)
        try:
            (backup_root / _FIXTURE_POINTER).write_text(
                str(tests_backup_root), encoding="utf-8")
        except OSError:
            pass          # restore still works from state.backup_root in-process
        for p in sorted(tests_dir.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(tests_dir).as_posix()
            if not _is_fixture_source(rel):
                continue
            dst = tests_backup_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            p.write_text(_STUB_BODY, encoding="utf-8")
            state.stubbed_rels.append(rel)

    # 3. Park the module's DEBUG SYMBOLS. Stubbing the source is only half the
    #    hide: the .pdb beside the compiled module carries source paths, a symbol
    #    per fixture and the tolerance constants (issue 12). Same volume, so this
    #    is a rename rather than a 112 MB copy.
    stage_module_symbols_hide(project_dir, state)

    # 4. Baseline the module's build products. Taken AFTER stubbing so the
    #    window it covers is exactly the window in which a rebuild would bake a
    #    stub in — the agent phase. Also after the symbol park, so a parked .pdb
    #    is not later mistaken for one the agent deleted.
    state.module_build_fp = module_build_fingerprint(project_dir)

    _persist_state(state, project_dir)
    return state


def _declared_tasks(path: Path) -> set:
    """Task IDs a source file's header comment declares (`for task <id>`).

    Returns the lower-cased set of every distinct task ID tagged in the first
    few KB of the file. Empty for shared infra (module .cpp/.h, base classes)
    that carries no `for task` tag. Unreadable files yield an empty set (kept).
    """
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:_HEAD_BYTES]
    except OSError:
        return set()
    return {m.group(1).lower() for m in _FOR_TASK_RE.finditer(head)}


def _bare_task_id(active_task_id: str) -> str:
    """Normalize a possibly SET-QUALIFIED active id to the bare, lower-case id.

    Scaffold markers and per-task folder names carry the BARE task id
    ("gp-spawn-sequence"), but callers may pass a set-qualified id
    ("bp-g2/gp-spawn-sequence") — strip the set prefix (and tolerate a Windows
    backslash) so the active task's own artifacts still match and are KEPT.
    """
    return (active_task_id or "").lower().replace("\\", "/").rsplit("/", 1)[-1]


def stage_task_isolation_hide(
    project_dir: Path,
    active_task_id: str,
    state: FairnessState,
    *,
    writable_src_rel: str = _WRITABLE_MODULE_REL,
) -> FairnessState:
    """Hide OTHER tasks' scaffold sources from the agent-writable runtime module.

    The writable runtime module ships every task's scaffold actor at once; each
    source self-declares its owning task in a `// ... for task <id>` header
    comment. For a single run all but the active task's scaffolds are DECOYS the
    agent can grep into and edit by mistake. This moves every basename whose
    sources declare ONLY foreign task(s) entirely aside (the .h/.cpp pair moved
    together into state.backup_root/TemplateIsolated/), leaving in place:

      * the active task's own scaffold (declares ``active_task_id``), and
      * all untagged shared infra (module .cpp/.h, base classes, Build.cs).

    Fail-safe by construction: a file with no `for task` tag, or one naming the
    active task, is KEPT — we never hide shared infra or the active task's files,
    so the worst case is the pre-existing (over-permissive) behavior, never a
    broken active build. ``.Build.cs`` and ``.Target.cs`` are skipped (suffix
    filter / live above the module dir). Pairs by basename stem so a header is
    never orphaned from its translation unit.

    Mutates and returns the SAME ``state`` (so one FairnessState carries both the
    CraftBenchTests stubs and these moves, and a single stage_fairness_restore
    undoes everything). Records moved paths in ``state.isolated_rels``.
    """
    # Scaffold markers carry the BARE task id ("// ... for task gp-spawner-population"),
    # but callers may pass a set-qualified id ("cpp/gp-spawner-population") —
    # normalize so the active task's own scaffold still matches and is KEPT, not
    # hidden + clobbered by the restore.
    active = _bare_task_id(active_task_id)
    src_dir = project_dir / writable_src_rel
    if not src_dir.is_dir():
        return state

    # Group .h/.cpp by basename stem so a pair (SpawnHostActor.h + .cpp) is
    # classified and moved together; collect every task each stem declares.
    by_stem: dict = defaultdict(lambda: {"paths": [], "tasks": set()})
    for p in sorted(src_dir.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in (".h", ".cpp"):
            continue
        info = by_stem[p.stem]
        info["paths"].append(p)
        info["tasks"] |= _declared_tasks(p)

    isolated_root = state.backup_root / _ISOLATED_SUBDIR
    for _stem, info in sorted(by_stem.items()):
        tasks = info["tasks"]
        if not tasks:
            continue                       # untagged shared infra → keep
        if active and active in tasks:
            continue                       # active task's own scaffold → keep
        # Every declared task is foreign → move the whole basename pair aside.
        for p in info["paths"]:
            rel = p.relative_to(src_dir).as_posix()
            dst = isolated_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            p.unlink()
            state.isolated_rels.append(rel)

    _persist_state(state, project_dir)
    return state


# WAITING IS COUNTERPRODUCTIVE, and this probe exists to prove it and to name
# what blocked the move. Measured 2026-08-23 with the probe asking for the
# rename's real precondition (DELETE access, not just a readable file): 43 hide
# targets held, every one of them a foreign task's `.umap` --
#
#   Content/Maps/gp-additem-stack-fix-bp/L_AdditemStack.umap
#   Content/Maps/gp-door-hitch-fix-bp/L_DoorHitch.umap
#   Content/Maps/gp-dot-aoe-burn/L_AoeBurn.umap            ... 43 of them
#
# WHICH PROCESS is still not proven, and the obvious guess is wrong: it is not
# the editor's asset gather, because arm B (unreal-mcp) runs an editor too and
# has never hit this lock -- 0 of 12 aborts. The asymmetry points at something
# only the Aura-staged bring-up has, and its indexing service does walk the whole
# project (that is where indexed_files_aura comes from). Untested.
#
# What IS established: those 43 packages are open without FILE_SHARE_DELETE, so
# the containing directory cannot be renamed; a 180 s wait did not release one of
# them; and the holder dies with the stack, since the sweep's teardown-and-retry
# usually wins. So the abort rate is a race against the holder REACHING
# Content/Maps, and every second of waiting hands it more time -- which is why
# the window is 5 s (for a genuinely transient holder such as a virus scan) and
# the held set is logged on the FIRST probe rather than only at timeout.
#
# The only real fix is ORDERING: hide BEFORE the editor exists, so those
# packages are never opened. Implemented for aura-mcp -- `cb eval` brings the
# stack up services-only and `run.py --defer-editor` starts the editor after
# the last hide (stack.ensure_drive_editor). The window below therefore now
# covers the OTHER holders (a virus scan, OneDrive, an editor an operator left
# up) and is deliberately still short.
_HIDE_SETTLE_TIMEOUT_S = 5.0
_HIDE_SETTLE_POLL_S = 2.0
# The two errors a rename dies on. Anything else (2 not-found, 3 path-not-found)
# is not a holder.
_HELD_ERRNOS = (5, 32)
#: CreateFileW needs this to open a DIRECTORY at all.
_BACKUP_SEMANTICS = 0x02000000
#: os.rename needs DELETE on the thing it moves, and an existing handle without
#: FILE_SHARE_DELETE denies it. Asking for exactly that is what makes this probe
#: measure the rename's real precondition instead of a proxy for it.
_DELETE_ACCESS = 0x00010000


def _held_paths(dirs) -> List[str]:
    """What under ``dirs`` (including each dir ITSELF) blocks a rename.

    Non-mutating on purpose: opens each path with dwShareMode=0, so a handle
    surfaces as ERROR_SHARING_VIOLATION / ERROR_ACCESS_DENIED. The obvious
    alternative -- rename the dir and rename it back -- leaves a broken tree if
    this dies between the two renames. Non-Windows returns nothing: POSIX
    renames do not care about open handles.

    THE DIRECTORY ITSELF IS THE POINT. A files-only probe read "0 held" on
    2026-08-23 while `os.rename` of the containing directory failed
    ACCESS_DENIED 14 times in a row -- a handle on the directory, opened without
    FILE_SHARE_DELETE, blocks the rename without blocking any file open. So each
    dir is probed for DELETE access, which is precisely what the rename needs.
    """
    if os.name != "nt":
        return []
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateFileW.restype = ctypes.c_void_p
        k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                    wintypes.DWORD, ctypes.c_void_p,
                                    wintypes.DWORD, wintypes.DWORD,
                                    ctypes.c_void_p]
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
    except Exception:
        return []
    invalid = ctypes.c_void_p(-1).value

    def blocked(path: str, access: int, flags: int) -> bool:
        h = k32.CreateFileW(path, access, 0, None, 3, flags, None)
        if h != invalid:
            k32.CloseHandle(ctypes.c_void_p(h))
            return False
        return ctypes.get_last_error() in _HELD_ERRNOS

    held: List[str] = []
    for d in dirs:
        if blocked(str(d), _DELETE_ACCESS, _BACKUP_SEMANTICS):
            held.append(str(d))
        for dirpath, subs, files in os.walk(d):
            for name in subs:
                p = os.path.join(dirpath, name)
                if blocked(p, _DELETE_ACCESS, _BACKUP_SEMANTICS):
                    held.append(p)
            for f in files:
                p = os.path.join(dirpath, f)
                if blocked(p, 0x80000000, 0x80):
                    held.append(p)
    return held


def _wait_until_movable(dirs, timeout: float = _HIDE_SETTLE_TIMEOUT_S) -> List[str]:
    """Block until nothing under ``dirs`` is held, or ``timeout``.

    Returns the still-held paths, which is empty on the normal path. Costs one
    exclusive-open per file when clean (measured 0.1s for Content/Maps), and
    the caller proceeds either way -- a timeout leaves the pre-existing
    fail-closed abort in place rather than adding a second failure mode.
    """
    deadline = time.time() + timeout
    waited = 0.0
    named = False
    while True:
        held = _held_paths(dirs)
        if held and not named:
            named = True
            print(f"  fairness: {len(held)} hide target(s) are held. The "
                  f"holder is unidentified but dies with the stack, and waiting "
                  f"only gives it more time to open more packages:", flush=True)
            for p in held[:8]:
                print(f"      {p}", flush=True)
            if len(held) > 8:
                print(f"      ... and {len(held) - 8} more", flush=True)
        if not held or time.time() >= deadline:
            if waited:
                if not held:
                    print(f"  fairness: waited {waited:.0f}s for the hide "
                          f"targets to be released - clear", flush=True)
                else:
                    print(f"  fairness: still held after {waited:.0f}s - the "
                          f"abort below is a race lost, not a stale holder",
                          flush=True)
            return held
        time.sleep(_HIDE_SETTLE_POLL_S)
        waited += _HIDE_SETTLE_POLL_S


def stage_task_tree_isolation_hide(
    project_dir: Path,
    active_task_id: str,
    state: FairnessState,
    *,
    per_task_roots: tuple = _PER_TASK_ROOTS,
) -> FairnessState:
    """Hide OTHER tasks' whole per-task DIRECTORIES (the folder-per-task layout).

    Tasks are migrating to per-task UE folders (Source/CraftBenchTemplate/Tasks/<id>/,
    Source/CraftBenchTests/Tasks/<id>/, Content/Maps/<id>/, Content/Tasks/<id>/).
    The marker-based stage_task_isolation_hide only sees `for task <id>`-tagged
    .h/.cpp; it never hides per-task CONTENT (maps/assets) and leaves stubbed
    fixture FOLDERS name-visible. This complements it at directory granularity:
    for each root in ``per_task_roots`` that exists, every IMMEDIATE child dir
    whose name is not the active BARE task id is moved wholesale to
    ``state.backup_root/TreeIsolated/<root with '/'->'__'>/<dirname>`` and
    recorded in ``state.isolated_dirs`` for stage_fairness_restore.

    Guard rails:
      * Only DIRECTORIES move — root-level files (the un-migrated flat .umap
        maps under Content/Maps/) always stay.
      * Under the Content/ roots a child dir counts as per-task ONLY if its
        name looks like a task id (kebab-case) — engine folders (Developers/,
        __ExternalActors__/, ...) are kept. The Source .../Tasks/ roots are
        per-task by construction, so every foreign child moves.
      * The ACTIVE task's own folder stays under EVERY root (including
        Content/Tasks — asset-task baselines the agent needs). Set-qualified
        active ids are normalized via the same rule as the marker isolation.
      * Idempotent / double-hide tolerant: an already-hidden dir simply isn't
        there to move (zero moves); if a live copy REAPPEARS while a parked
        copy exists (external restore between two hides), the live bytes are
        merged over the parked copy and the live dir dropped — never nested.
      * Missing roots are a no-op.

    Mutates and returns the SAME ``state`` (one FairnessState carries the
    stubs, the marker moves and these dir moves; a single
    stage_fairness_restore undoes everything).
    """
    active = _bare_task_id(active_task_id)
    for root_rel in per_task_roots:
        root_rel = root_rel.replace("\\", "/").strip("/")
        root_dir = project_dir / root_rel
        if not root_dir.is_dir():
            continue                       # missing root → no-op
        require_task_like = root_rel.startswith("Content/")
        root_key = root_rel.replace("/", "__")
        movers = [c for c in sorted(root_dir.iterdir()) if c.is_dir()
                  and not (active and c.name.lower() == active)
                  and not (require_task_like and not _TASK_DIR_RE.match(c.name))]
        _wait_until_movable(movers)
        for child in sorted(root_dir.iterdir()):
            if not child.is_dir():
                continue                   # flat files (un-migrated .umap) stay
            name = child.name
            if active and name.lower() == active:
                continue                   # active task's own folder → keep
            if require_task_like and not _TASK_DIR_RE.match(name):
                continue                   # engine/non-task folder → keep
            src_rel = f"{root_rel}/{name}"
            backup_rel = f"{_TREE_ISOLATED_SUBDIR}/{root_key}/{name}"
            dst = state.backup_root / _TREE_ISOLATED_SUBDIR / root_key / name
            if dst.exists():
                # A prior hide already parked this dir and something recreated
                # the live copy: merge live bytes over the parked copy, then
                # drop the live dir (same net effect as a fresh move). The live
                # copy MUST go — a survivor stays agent-visible, so a lock that
                # outlives the retries is fatal for the run's fairness.
                shutil.copytree(child, dst, dirs_exist_ok=True)
                if not _robust_rmtree(child):
                    raise OSError(
                        f"fairness tree-isolation could not remove the live "
                        f"copy {child} (locked by a running process — a live "
                        f"editor with the map loaded, or OneDrive sync)")
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                _robust_move(child, dst, retries=_ISOLATION_MOVE_RETRIES)
            if (src_rel, backup_rel) not in state.isolated_dirs:
                state.isolated_dirs.append((src_rel, backup_rel))

    _persist_state(state, project_dir)
    return state


# Repo-level answer material a live-project agent must not see. Everything an
# agent legitimately needs is inside its substrate (the prompt is
# self-contained), so these hide WHOLESALE during the agent phase:
#   tasks/               committed reference solutions, discrimination
#                        variants, authoring aids, notes — measured 2026-08-19:
#                        two deepseek runs Read tasks/<id>/reference/* verbatim
#                        and delivered the same four files; a sonnet run Read
#                        aids/author_reference.py (the step-by-step reference
#                        builder).
#   tools/verify-single/ the verifier itself, incl. introspect/<task>.py —
#                        the L2I answer key.
# Sibling substrates' CraftBenchTests also hide wholesale (the active
# substrate's are STUBBED so agent-triggered builds still compile; a sibling
# substrate is never built during the drive) — measured: an agent blocked by
# the active substrate's stubs Read the same task's pre-port fixture from the
# OTHER substrate.
_REPO_HIDE_PREFIX = ".cb-fairness-hidden__"
# ".git" is in the list because renaming the working tree is not enough for a
# Bash-bearing lane: measured 2026-08-20, an unreal-mcp agent that found the
# tree hidden ran `git show HEAD:<fixture>` / `git show HEAD:<reference>` and
# recovered the full answer key from the object store (its own find command
# echoed "---REFERENCE?---" — it was hunting). Hiding .git for the drive
# window is safe by the same order argument as tasks/: every harness git read
# (live_hygiene, provenance shas, substrate materialization)
# happens before the hide or after the restore, and the agent-facing `git`
# then fails with "not a git repository" — an audit-visible refusal. On a
# WORKTREE .git is a one-line pointer file; on a full checkout a directory;
# _robust_move handles both, and a hide-time lock aborts the run BEFORE any
# token is spent (fail-closed).
#   docs/               authoring queues and eval notes name the very facts a
#                       behaviour-only prompt withholds — measured 2026-08-21:
#                       a drive read a task queue naming the required
#                       Ability.Poison tag and the reference path. Nothing in
#                       the drive window reads docs/ (PREAMBLE.md is under
#                       tasks/ and is rendered before the hide).
_REPO_HIDE_RELS = ("tasks", "tools/verify-single", "docs", ".git")


def _park_root(repo_root: Path) -> Path:
    """Where parked answer trees live: OUTSIDE ``repo_root``, same volume.

    Outside is the whole point. Parking as a same-parent sibling kept the rename
    atomic but left the tree fully readable under a predictable name, and agents
    walked straight into it — measured 2026-08-21, six drives read
    ``.cb-fairness-hidden__tasks/<set>/<id>/reference/`` including their own
    task's. Same volume keeps ``os.rename`` atomic; a different-volume temp dir
    falls back to a sibling of the repo, which is still out of reach of every
    repo-scoped glob/grep.
    """
    env = os.environ.get("CB_FAIRNESS_PARK")
    if env:
        base = Path(env)
    else:
        # A test process gets its OWN root. The default is keyed on the volume
        # alone, so any repo_root on C: resolves to the one shared park — and
        # _reclaim_parks then reaches into a LIVE drive's slot. Measured
        # 2026-08-22: a diagnostic run with a temp "repo" un-hid tasks/, docs/
        # and .git 40 minutes into a drive; the breach probe caught it and the
        # cell was voided instead of mis-scored, but the cell was still lost.
        # Same seam and same reasoning as kill_guard's no-kills-from-a-test
        # rule, so it reuses that detector.
        try:
            from aura_rig.kill_guard import in_test_process
            testing = in_test_process()
        except Exception:
            testing = False
        base = Path(tempfile.gettempdir()) / (
            "cb-fairness-park-test" if testing else "cb-fairness-park")
    if os.path.splitdrive(base)[0].lower() != os.path.splitdrive(repo_root)[0].lower():
        base = repo_root.parent / (repo_root.name + ".cb-fairness-park")
    return base


def _park_slot(repo_root: Path) -> Path:
    return _park_root(repo_root) / str(os.getpid())


def _park_name(repo_root: Path, src: Path) -> str:
    """Flatten the repo-relative path: sibling substrates all end in
    CraftBenchTests, which would collide in one flat park dir."""
    rel = os.path.relpath(str(src), str(repo_root))
    return _REPO_HIDE_PREFIX + rel.replace(os.sep, "__").replace("/", "__")


# No run outlives this, so a park older than it cannot belong to one. The
# fallback matters because refusing to reclaim on doubt is self-deadlocking:
# cb imports spec from tools/verify-single, so a park that is never reclaimed
# leaves the repo unable to reach its own heal path.
_PARK_STALE_AGE_S = 4 * 60 * 60


def _park_slot_is_live(slot: Path) -> Optional[bool]:
    """Is the run that created ``slot`` still going? None = cannot tell."""
    try:
        pid = int(slot.name)
    except ValueError:
        return None
    if pid == os.getpid():
        return True
    try:
        created = json.loads(
            (slot / "park.json").read_text(encoding="utf-8")).get("owner_created")
    except Exception:
        created = None
    try:
        from aura_rig.stack_guard import pid_alive
        return bool(pid_alive(pid, created))
    except Exception:
        return None


def _reclaim_parks(park_root: Path) -> None:
    """Put back any park left by a dead run.

    Relocating the park out of the tree removed the old crash-recovery cue (a
    leftover sibling next to its source), so recovery reads each slot's
    ``park.json`` instead. Without this an interrupted run leaves tasks/ and
    tools/verify-single/ simply MISSING, which is self-deadlocking: cb imports
    spec from verify-single and so cannot reach its own heal path.
    """
    if not park_root.is_dir():
        return
    for slot in sorted(park_root.iterdir()):
        manifest = slot / "park.json"
        if not manifest.is_file():
            continue
        # Reclaim only what a DEAD run left. Measured 2026-08-22: a diagnostic
        # script built a park root on the same volume, so it resolved to the
        # shared one, and its reclaim put tasks/, docs/ and .git back into the
        # repo 40 minutes into a live drive. The breach probe caught it and the
        # cell was voided rather than mis-scored, but the cell was still lost.
        if _park_slot_is_live(slot) is not False and \
                _age_s(manifest) < _PARK_STALE_AGE_S:
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            pairs = data["pairs"]
        except Exception:
            continue
        for src_s, hidden_s in pairs:
            src, hidden = Path(src_s), Path(hidden_s)
            if not hidden.exists():
                continue
            if src.exists():
                _robust_rmtree(hidden) if hidden.is_dir() else hidden.unlink(missing_ok=True)
            else:
                src.parent.mkdir(parents=True, exist_ok=True)
                _robust_move(hidden, src)
        for src_s, park_s in data.get("merge_pairs") or []:
            _merge_park_back(Path(src_s), Path(park_s))
        manifest.unlink(missing_ok=True)
        try:
            slot.rmdir()
        except OSError:
            pass


def _write_park_manifest(slot: Path, state: FairnessState) -> None:
    """Refresh the park's crash-recovery recipe, or drop an empty slot."""
    pairs = [list(t) for t in getattr(state, "repo_hidden", [])]
    merges = [list(t) for t in getattr(state, "index_hidden", [])]
    try:
        from aura_rig.stack_guard import pid_create_time
        created = pid_create_time(os.getpid())
    except Exception:
        created = None
    if not pairs and not merges:
        try:
            slot.rmdir()
        except OSError:
            pass
        return
    try:
        (slot / "park.json").write_text(
            json.dumps({"pairs": pairs, "merge_pairs": merges,
                        "owner_created": created}),
            encoding="utf-8")
    except OSError:
        pass


def _merge_park_back(src_dir: Path, park_dir: Path) -> None:
    """Return parked files to ``src_dir``, newest-wins, then drop the park.

    Merge rather than rename because the directory stays LIVE while parked:
    the indexer keeps writing into it for the whole drive. A name that came
    back on its own therefore wins, and a file that cannot be moved stays in
    the park for the next run's reclaim instead of aborting the restore.
    """
    if not park_dir.is_dir():
        return
    for parked in sorted(park_dir.iterdir()):
        dst = src_dir / parked.name
        if dst.exists():
            parked.unlink(missing_ok=True)
            continue
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            _robust_move(parked, dst)
        except OSError:
            pass
    try:
        park_dir.rmdir()
    except OSError:
        pass


def stage_repo_answer_hide(repo_root: Path, project_dir: Path,
                           state: FairnessState) -> FairnessState:
    """Hide repo-level answer material for the agent phase.

    Each target is renamed into a per-pid park OUTSIDE the repo (see
    :func:`_park_root`), so nothing an agent can enumerate from the repo or the
    project reaches it. Reclaims a dead run's park first, and still puts back a
    pre-relocation in-tree sibling if one is lying around.

    Call this LAST in the hide sequence — stage_config_overlay_apply lazily
    imports from tools/verify-single and prompt rendering reads tasks/, both
    of which must complete first. Nothing in the drive window reads either
    tree (verified 2026-08-19: the only in-window code is the adapter
    subprocess and the pressure sampler).

    Mutates and returns the SAME ``state``; stage_fairness_restore undoes it.
    """
    repo_root = Path(repo_root)
    # Reclaim BEFORE enumerating: a crashed run's parked sibling substrate is
    # outside the repo, so its CraftBenchTests is invisible to the scan below
    # and would be left out of this run's hide entirely.
    _reclaim_parks(_park_root(repo_root))
    slot = _park_slot(repo_root)
    slot.mkdir(parents=True, exist_ok=True)
    targets = [repo_root / rel for rel in _REPO_HIDE_RELS]
    ue_root = Path(project_dir).parent
    try:
        for sib in sorted(ue_root.iterdir()):
            if sib.is_dir() and sib.resolve() != Path(project_dir).resolve():
                tests = sib / _CRAFTBENCH_TESTS_REL
                legacy = tests.parent / (_REPO_HIDE_PREFIX + tests.name)
                # ALREADY in our own park counts too: reclaim leaves a LIVE
                # owner's slot alone, so a sibling this process parked and never
                # restored is absent from disk and would otherwise drop out of
                # the hide entirely -- the same blind spot the reclaim-first
                # ordering was added to close.
                if (tests.is_dir() or legacy.is_dir()
                        or (slot / _park_name(repo_root, tests)).exists()):
                    targets.append(tests)
    except OSError:
        pass

    for src in targets:
        legacy = src.parent / (_REPO_HIDE_PREFIX + src.name)
        if legacy.exists():
            if src.exists():
                _robust_rmtree(legacy) if legacy.is_dir() else legacy.unlink(missing_ok=True)
            else:
                _robust_move(legacy, src)
        # NOT is_dir(): a worktree's .git is a one-line pointer FILE, and
        # os.rename moves files and dirs alike.
        hidden = slot / _park_name(repo_root, src)
        if hidden.exists():
            # our own earlier park in this slot: one process hiding twice (a
            # retry, a heal, or two tests in one runner) lands on the same path,
            # and os.rename onto an existing directory is ERROR_ACCESS_DENIED —
            # which _robust_move can only report as "still locked", forever.
            # Reclaim used to clear this incidentally; it no longer touches a
            # LIVE owner's slot, so handle it here on the same terms the legacy
            # branch above uses: the live tree wins, a park with no source is
            # put back.
            if src.exists():
                _robust_rmtree(hidden) if hidden.is_dir() \
                    else hidden.unlink(missing_ok=True)
            else:
                # Put it back so THIS hide re-parks it and records the pair.
                # Skipping instead would leave the tree hidden with nothing in
                # the state to restore it from.
                _robust_move(hidden, src)
        if not src.exists():
            continue                       # missing target -> no-op
        _robust_move(src, hidden)
        pair = (str(src), str(hidden))
        if pair not in state.repo_hidden:
            state.repo_hidden.append(pair)
    _write_park_manifest(slot, state)
    _persist_state(state, project_dir)
    return state


def repo_hide_breaches(state: FairnessState) -> List[str]:
    """Which repo-level hides are no longer in force.

    stage_repo_answer_hide's contract is that each recorded source stays absent
    for the whole agent phase, so a source back on disk means something outside
    this run resurrected it (a sync client, a checkout, an operator) and the
    agent phase ran with the answer key readable. Callers must not grade such a
    run: stage_fairness_restore's ``src.exists()`` branch handles the same
    condition as bookkeeping and would otherwise drop the park silently.
    """
    return [src for src, _hidden in getattr(state, "repo_hidden", [])
            if Path(src).exists()]


# Aura's RAG index keeps its own copy of every indexed file's TEXT, and
# query_unreal_project_assets serves content from that copy -- it never re-reads
# the source. Stubbing Source/CraftBenchTests/*.{h,cpp} therefore changes
# nothing the tool returns, which is how fixtures leaked verbatim (comments
# included) out of a tree whose fixtures were 77-char stubs.
_INDEX_DOC_DIR_RELS = (
    "Saved/.Aura/indexed_files_aura",
    "Saved/.Aura/IndexPipeline/Docs",      # the V2 indexer's location
)
# A verbatim dump of the LAST query's output, so it can carry answer text
# across cells even when this cell's own index is clean.
_INDEX_SPILL_DIR_REL = "Saved/.Aura"
_INDEX_SPILL_NAMES = ("last_query_output.txt",)
_INDEX_PARK_PREFIX = ".cb-fairness-index__"
_INDEX_DOC_HEAD_BYTES = 512
_INDEX_DOC_PATH_RE = re.compile(rb'"file_path"\s*:\s*"([^"]*)"')


def _index_cache_projects(project_dir: Path) -> List[Path]:
    """The active project plus every sibling substrate.

    A sibling's cache is answer material by the same argument that puts its
    Source/CraftBenchTests in _REPO_HIDE_RELS: the agent cannot query it
    through Aura, but it can read the doc JSONs off disk.
    """
    project_dir = Path(project_dir)
    projects = [project_dir]
    try:
        active = project_dir.resolve()
        for sib in sorted(project_dir.parent.iterdir()):
            if sib.is_dir() and sib.resolve() != active:
                projects.append(sib)
    except OSError:
        pass
    return projects


def _index_cache_targets(project_dir: Path) -> List[Tuple[Path, str]]:
    return [(proj, rel)
            for proj in _index_cache_projects(project_dir)
            for rel in _INDEX_DOC_DIR_RELS]


def _index_doc_names_answer_key(doc: Path) -> bool:
    """Does this cached doc hold verifier source? Unclassifiable means yes.

    ``file_path`` is the first key every doc writes, so a 512-byte head is
    enough: measured 0 misses over 15,440 docs, 2.4s for the whole scan.
    """
    try:
        with open(doc, "rb") as fh:
            head = fh.read(_INDEX_DOC_HEAD_BYTES)
    except OSError:
        return True
    m = _INDEX_DOC_PATH_RE.search(head)
    if m is None:
        return True
    rel = m.group(1).decode("utf-8", "replace")
    rel = rel.replace("\\\\", "/").replace("\\", "/")
    return rel.startswith(_CRAFTBENCH_TESTS_REL + "/")


def stage_index_cache_hide(repo_root: Path, project_dir: Path,
                           state: FairnessState) -> FairnessState:
    """Park Aura's CACHED COPY of the verifier sources for the agent phase.

    Same root as the compiled-fixture leak: the hide covered the source and
    not its copies. Measured 2026-08-22 on this box, 3,940 cached docs held
    53.7 MB of verifier source across 108 files, inside the agent's own
    project tree.

    Only docs whose recorded ``file_path`` is under Source/CraftBenchTests/
    move, so the lane keeps the index capability it exists to measure. A doc
    that cannot be parked raises out of ``_robust_move`` and aborts the run
    pre-spend -- the same fail-closed contract the tree-isolation hide uses.

    Mutates and returns the SAME ``state``; stage_fairness_restore undoes it.
    """
    repo_root, project_dir = Path(repo_root), Path(project_dir)
    slot = _park_slot(repo_root)
    for idx, (proj, rel) in enumerate(_index_cache_targets(project_dir)):
        docs_dir = proj / rel
        if not docs_dir.is_dir():
            continue
        answers = [Path(e.path) for e in os.scandir(docs_dir)
                   if e.is_file() and _index_doc_names_answer_key(Path(e.path))]
        if not answers:
            continue
        park_dir = slot / (_INDEX_PARK_PREFIX + str(idx))
        park_dir.mkdir(parents=True, exist_ok=True)
        for doc in answers:
            _robust_move(doc, park_dir / doc.name)
        pair = (str(docs_dir), str(park_dir))
        if pair not in state.index_hidden:
            state.index_hidden.append(pair)

    for sidx, proj in enumerate(_index_cache_projects(project_dir)):
        spill_dir = proj / _INDEX_SPILL_DIR_REL
        spilled = [spill_dir / n for n in _INDEX_SPILL_NAMES
                   if (spill_dir / n).is_file()]
        if not spilled:
            continue
        park_dir = slot / (_INDEX_PARK_PREFIX + "spill" + str(sidx))
        park_dir.mkdir(parents=True, exist_ok=True)
        for p in spilled:
            _robust_move(p, park_dir / p.name)
        pair = (str(spill_dir), str(park_dir))
        if pair not in state.index_hidden:
            state.index_hidden.append(pair)

    if state.index_hidden:
        _write_park_manifest(slot, state)
        _persist_state(state, project_dir)
    return state


def _index_doc_holds_answer_text(doc: Path) -> bool:
    """Is this a verifier-path doc whose CONTENT is not the fairness stub?

    The hide selects by PATH (fail-safe: park anything that could be answer
    material). The PROBE must not, because the indexer re-indexes the STUBBED
    sources DURING the drive and writes fresh docs under those same paths —
    measured 2026-08-22: 12 appeared mid-drive, every one of them the 73-char
    stub. A path-only probe reads those as a breach, and an alarm that fires on
    the system working correctly is worse than no alarm.
    """
    if not _index_doc_names_answer_key(doc):
        return False
    try:
        text = json.loads(doc.read_text(encoding="utf-8")).get("content") or ""
    except (OSError, ValueError):
        return True          # unreadable -> assume the worst, as in the selector
    return _STUB_BODY.strip() not in text or len(text.strip()) > 200


def indexed_answer_doc_count(project_dir: Path) -> int:
    """How many cached index docs currently hold verifier SOURCE.

    The direct probe for this leak: 0 while a drive is live. Content-aware, so
    the indexer's own stub docs do not count (see
    :func:`_index_doc_holds_answer_text`).
    """
    n = 0
    for proj, rel in _index_cache_targets(Path(project_dir)):
        docs_dir = proj / rel
        if not docs_dir.is_dir():
            continue
        n += sum(1 for e in os.scandir(docs_dir)
                 if e.is_file() and _index_doc_holds_answer_text(Path(e.path)))
    return n


# UHT compiles the fixture headers into reflection glue that lives in the
# agent's own project tree. It carries no bodies and no tolerances, but it does
# carry REFLECTED MEMBER NAMES: AoeBurn's TargetNear/Far/Control/Edge (that
# there is a control probe and an edge case), WingHost's Cp0..Cp3r (the
# checkpoint count and that one repeats), PlateDoor's whole phase enum. Third
# copy of the same source, after the RAG cache and the compiled module.
_UHT_INC_LEAF = "Inc/" + _CRAFTBENCH_TESTS_REL.split("/")[-1]
_UHT_INC_GLOB = "Intermediate/Build/*/*/" + _UHT_INC_LEAF


def stage_generated_code_hide(repo_root: Path, project_dir: Path,
                              state: FairnessState) -> FairnessState:
    """Park UHT's generated copy of the fixtures for the agent phase.

    Merge-back, NOT the ``repo_hidden`` rename: an agent that recompiles
    mid-drive legitimately recreates this directory, and ``repo_hide_breaches``
    would read the reappearance as a hide breach and void an honest cell. A
    rebuilt copy is derived from the STUBS anyway, and
    ``_invalidate_module_build`` already deletes the whole
    ``Intermediate/Build`` tree whenever the module's products were rewritten
    during the hide, so newest-wins needs no special case here.

    Mutates and returns the SAME ``state``; stage_fairness_restore undoes it.
    """
    repo_root, project_dir = Path(repo_root), Path(project_dir)
    slot = _park_slot(repo_root)
    for idx, proj in enumerate(_index_cache_projects(project_dir)):
        for jdx, inc in enumerate(sorted(proj.glob(_UHT_INC_GLOB))):
            if not inc.is_dir():
                continue
            _wait_until_movable([inc])
            park_dir = slot / f"{_INDEX_PARK_PREFIX}uht-{idx}-{jdx}"
            park_dir.mkdir(parents=True, exist_ok=True)
            _robust_move(inc, park_dir / inc.name,
                         retries=_ISOLATION_MOVE_RETRIES)
            pair = (str(inc.parent), str(park_dir))
            if pair not in state.index_hidden:
                state.index_hidden.append(pair)
    if state.index_hidden:
        _write_park_manifest(slot, state)
        _persist_state(state, project_dir)
    return state


def generated_answer_copy_count(project_dir: Path) -> int:
    """How many UHT files derived from the fixtures are currently readable."""
    n = 0
    for proj in _index_cache_projects(Path(project_dir)):
        for inc in proj.glob(_UHT_INC_GLOB):
            if inc.is_dir():
                n += sum(1 for _ in inc.rglob("*") if _.is_file())
    return n


def _import_config_overlay():
    """Import ``tools/verify-single/config_overlay`` (the shared B7 discover/
    apply core), adding its dir to sys.path if needed. Mirrors how
    aura_rig/provenance.py imports verify-single's asset_capture — the
    hyphenated dir can't be a package, so the module is imported off sys.path
    rather than duplicated here (single source of truth for the append/marker
    semantics the verifier staging path also uses)."""
    try:
        import config_overlay
    except ImportError:
        vs_dir = Path(__file__).resolve().parents[1] / "verify-single"
        if str(vs_dir) not in sys.path and vs_dir.exists():
            sys.path.insert(0, str(vs_dir))
        import config_overlay
    return config_overlay


def stage_config_overlay_apply(
    project_dir: Path,
    task_spec_path: Path,
    active_task_id: str,
    state: FairnessState,
) -> FairnessState:
    """Apply the per-task UE config overlay (B7) to the LIVE project for a drive.

    A task folder may ship verifier-owned ``ue-config/<IniName>.ini`` fragments
    (e.g. DefaultGameplayTags.ini); the editor the agent drives must see them,
    so they are APPEND-applied (marker-headed; UE ini semantics are later-wins
    + ``+Array``, so append suffices) onto ``Config/<IniName>.ini`` BEFORE the
    editor launch. Unlike the verifier's disposable workdir, the live tree must
    come back byte-identical: pre-apply bytes are parked under
    ``state.backup_root/ConfigOverlay/`` and each mutation is recorded in
    ``state.applied_config`` for stage_fairness_restore to revert (created
    files are deleted). Config/ is outside the writable backup tree, so this
    fairness-state revert is the ONLY undo path — restore_tree never touches it.

    No-op (records nothing) for flat specs and tasks without an ``ue-config/``
    dir — every current task. Mutates and returns the SAME ``state`` so a
    single stage_fairness_restore undoes everything.
    """
    co = _import_config_overlay()
    fragments = co.discover(Path(task_spec_path))
    if not fragments:
        return state
    config_dir = Path(project_dir) / _CONFIG_DIR_REL
    marker_id = _bare_task_id(active_task_id) or str(active_task_id)
    applied = co.apply(config_dir, fragments, marker_id)
    for frag in applied:
        backup_rel = ""
        if not frag.created and frag.original_bytes is not None:
            backup_rel = f"{_CONFIG_OVERLAY_SUBDIR}/{frag.ini_name}"
            dst = state.backup_root / _CONFIG_OVERLAY_SUBDIR / frag.ini_name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(frag.original_bytes)
        state.applied_config.append((frag.ini_name, frag.created, backup_rel))
    _persist_state(state, project_dir)
    return state


def stage_fairness_restore(state: FairnessState, project_dir: Path) -> None:
    """Restore the live tree byte-for-byte from the fairness backup.

    Copies every backed-up CraftBenchTests/<rel> back over its stub and moves
    AGENT_WRITABLE.json back into place. Idempotent: a second call copies
    identical bytes (a no-op) and tolerates a manifest already restored.

    Grading does NOT depend on this (run_task.py copies the REPO substrate, not
    the live tree) — restore exists to keep the live working tree clean for the
    next run and for git.

    A CLEAN restore also deletes the backup root: once everything is back in
    the live tree (and in git), the backup is redundant machinery, and leaving
    it under run_dir/ made every shared run result permanently carry the
    hidden answer-key fixtures + parked scaffolds as if they were artifacts.
    A restore that THROWS never reaches the delete, so a failed/partial
    restore keeps the backup as the recovery source.
    """
    backup_root = Path(state.backup_root)

    # Restore repo-level answer material (stage_repo_answer_hide) before
    # anything else — these are same-parent renames, disjoint from every
    # other restore target, and the verifier subprocess launched right after
    # this function needs tasks/ and tools/verify-single back on disk.
    for src_s, hidden_s in getattr(state, "repo_hidden", []):
        src, hidden = Path(src_s), Path(hidden_s)
        if not hidden.exists():
            continue                       # already restored (idempotent)
        if src.exists():
            # Source reappeared while hidden (git checkout mid-run): the live
            # copy wins; the park is redundant bytes.
            _robust_rmtree(hidden)
        else:
            _robust_move(hidden, src)

    # Aura's cached index docs (stage_index_cache_hide). Merge-back rather
    # than rename: the indexer writes into the same directory all drive long.
    for src_s, park_s in getattr(state, "index_hidden", []):
        _merge_park_back(Path(src_s), Path(park_s))

    # Restore whole per-task directories (tree isolation) FIRST: the
    # finer-grained restores below may target paths INSIDE these directories —
    # in particular, a parked Source/CraftBenchTests/Tasks/<id>/ dir holds the
    # STUBBED fixture bodies (stage_fairness_hide stubbed them before the dir
    # was moved), so the per-file stub restore must run AFTER the dir is back
    # to win with the original bytes. Move semantics: the parked copy returns
    # wholesale and the backup entry disappears; if the live dir already
    # exists (an outer restore_tree recreated it), merge over it instead.
    for src_rel, backup_rel in getattr(state, "isolated_dirs", []):
        src = backup_root / backup_rel
        if not src.exists():
            continue                       # already restored (idempotent)
        dst = project_dir / src_rel
        if dst.exists():
            shutil.copytree(src, dst, dirs_exist_ok=True)
            # A parked copy that outlives the retries is tolerable — the live
            # tree already has the bytes back, and the final backup_root
            # delete below is ignore_errors anyway.
            _robust_rmtree(src)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                _robust_move(src, dst)
            except OSError:
                # Locked parked copy (OneDrive holds run_dir files): fall back
                # to copy — the live tree MUST come back whole even if the
                # backup can't be consumed; never abort the remaining restores.
                shutil.copytree(src, dst, dirs_exist_ok=True)
                _robust_rmtree(src)

    # Restore the stubbed fixture bodies from backup.
    tests_backup_root = fixture_backup_root(backup_root)
    tests_dir = project_dir / _CRAFTBENCH_TESTS_REL
    for rel in state.stubbed_rels:
        src = tests_backup_root / rel
        if not src.exists():
            continue
        dst = tests_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    # Restore the foreign-task runtime sources moved aside by task isolation.
    isolated_root = backup_root / _ISOLATED_SUBDIR
    module_dir = project_dir / _WRITABLE_MODULE_REL
    for rel in getattr(state, "isolated_rels", []):
        src = isolated_root / rel
        if not src.exists():
            continue
        dst = module_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    # Move the manifest back.
    if state.moved_manifest:
        manifest_src = backup_root / _MANIFEST_NAME
        manifest_dst = project_dir / _MANIFEST_NAME
        if manifest_src.exists():
            shutil.copy2(manifest_src, manifest_dst)

    # Revert the per-task UE config overlay (B7): restore each appended
    # Config/<ini> byte-identically from its parked pre-apply bytes; DELETE the
    # files the apply created. Idempotent: a second call rewrites identical
    # bytes and tolerates already-deleted created files. This is the only undo
    # path for Config/ — it sits outside the writable backup tree.
    for ini_name, created, backup_rel in getattr(state, "applied_config", []):
        live = project_dir / _CONFIG_DIR_REL / ini_name
        if created:
            if live.exists():
                live.unlink()
            continue
        src = backup_root / backup_rel
        if not src.exists():
            continue
        live.parent.mkdir(parents=True, exist_ok=True)
        live.write_bytes(src.read_bytes())

    # Put the parked .pdb back. Order is NOT load-bearing here, by construction:
    # the rebuild fingerprint reads the DLL only, precisely so the park cannot be
    # mistaken for a rebuild.
    stage_module_symbols_restore(state, project_dir)

    # ISSUE 11: the sources are back, but the BINARIES may carry the stubs.
    #
    # Runs here, after the source restore, and only when the hide captured a
    # baseline. A changed fingerprint means something rebuilt the verifier module
    # while its sources were stubbed, so those build products contain an empty
    # module: the next cell inherits it, the engine cannot initialise the module,
    # and NO editor starts on the box until a human clears it. That is how nine
    # consecutive cells died and how CraftBenchTemplate sat bricked for days.
    #
    # Deliberately NOT allowed to raise: the source tree is already whole at this
    # point, and an exception here would skip the backup delete below and leave
    # the answer key parked under the run dir. A failure downgrades to the marker
    # instead, which the pre-cell check refuses on.
    # `is not None`, NOT truthiness. module_build_fingerprint() returns "" for a
    # project with no artifacts, and _invalidate_module_build DELETES them — so
    # the cell after any successful invalidation baselines as "" and a truthiness
    # test would silently disable this check exactly when the previous cell had
    # just proved an agent rebuilds mid-drive. None still means "never captured"
    # (a pre-2026-08-22 state, or a hand-built one) and is skipped as before.
    baseline = getattr(state, "module_build_fp", None)
    if baseline is not None:
        try:
            if module_build_fingerprint(project_dir) != baseline:
                complete, failures = _invalidate_module_build(
                    project_dir, log=lambda m: print(m, flush=True))
                if not complete:
                    try:
                        build_poison_marker_path(project_dir).write_text(
                            json.dumps({
                                "reason": "; ".join(failures)[:500],
                                "detected": "stage_fairness_restore",
                            }, indent=2), encoding="utf-8")
                        print(f"    wrote {BUILD_POISON_MARKER} — the next cell "
                              f"must REFUSE this project until it is rebuilt "
                              f"by hand", flush=True)
                    except OSError as exc:
                        print(f"    WARN could not write "
                              f"{BUILD_POISON_MARKER}: {exc}", flush=True)
        except Exception as exc:                          # noqa: BLE001
            print(f"  WARN fairness: build-product check failed ({exc}); "
                  f"the source restore below is unaffected", flush=True)

    # Everything above completed without raising -> the live tree is whole and
    # the backup is redundant. Delete it so the run result doesn't retain it.
    # Name-guarded so a hand-built state can never rmtree an arbitrary dir;
    # a second (safety-net) restore call finds it gone and no-ops.
    if backup_root.name == "fairness_backup" and backup_root.exists():
        shutil.rmtree(backup_root, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Crash recovery — self-heal a half-hidden tree from leftover run artifacts.   #
#                                                                              #
# The hide/restore pair above lives inside one process's try/finally; a hard   #
# kill (taskkill /F, console close, power loss) skips the finally and leaves   #
# (1) run_dir/fairness_backup with the parked answer key + a half-hidden live  #
# tree, and/or (2) the agent's writable-area edits with the pristine presnap   #
# orphaned under CB_TMP/cb-presnap. Historically NOTHING consumed those        #
# artifacts — the next run's DIRTY-SUBSTRATE gate aborted and a human did git  #
# surgery (bit t0 on 2026-07-08 and gp-gas-launch on 2026-07-10). The helpers  #
# below give the gates an automatic path: restore leftover fairness backups,   #
# then revert remaining gate-listed dirt from the newest presnap/live_backup.  #
# --------------------------------------------------------------------------- #

# A backup/presnap younger than this is treated as IN FLIGHT (a live drive's
# artifacts must never be consumed from under it — restoring mid-drive would
# un-hide the answer key). Mirrors runs_clean's in-flight floor.
LEFTOVER_MIN_AGE_S = 60 * 60


def _age_s(path: Path) -> float:
    try:
        return time.time() - path.stat().st_mtime
    except OSError:
        return 0.0  # unstatable → treat as brand new (skipped, never consumed)


def _mtime_or_zero(path: Path) -> float:
    """Sort key that tolerates a path vanishing between glob and sort (a
    concurrent heal / cb clean) — the raw ``stat()`` there raised through the
    'never raises' heal contract."""
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def find_leftover_backups(runs_root: Path,
                          names: Tuple[str, ...] = ("fairness_backup",)) -> List[Path]:
    """Leftover backup dirs under ``runs_root`` — flat runs (runs/<id>/) and
    one container level (runs/<family>/<id>/), the only depths the graded
    flows create them at. Sorted oldest-first (restore order)."""
    found = set()
    for name in names:
        try:
            found |= set(runs_root.glob(f"*/{name}"))
            found |= set(runs_root.glob(f"*/*/{name}"))
        except OSError:
            pass
    return sorted((p for p in found if p.is_dir()), key=_mtime_or_zero)


def _rescue_dir() -> Path:
    """Where the heal parks the PRE-HEAL live bytes of every file it
    overwrites: CB_TMP/cb-heal-rescue/<UTC stamp>/. The heal must never be the
    only holder of destroyed bytes — a gate-listed 'dirty' file can be a
    maintainer's intentional uncommitted WIP, not crash dirt, and this repo's
    WIP-heavy workflow makes that routine. Rescue dirs are tiny (only the
    overwritten files) and swept manually when stale."""
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    return (Path(os.environ.get("CB_TMP", tempfile.gettempdir()))
            / "cb-heal-rescue" / stamp)


def _park_pre_heal_bytes(state: FairnessState, project_dir: Path,
                         rescue: Path, log=lambda s: None) -> int:
    """Copy the CURRENT live bytes of every path ``stage_fairness_restore``
    would overwrite into ``rescue`` (project-relative layout). Returns the
    count parked. Best-effort: an unparkable file is logged, never fatal."""
    project_dir = Path(project_dir)
    targets: List[str] = []
    targets += [f"{_CRAFTBENCH_TESTS_REL}/{r}" for r in state.stubbed_rels]
    targets += [f"{_WRITABLE_MODULE_REL}/{r}" for r in state.isolated_rels]
    if state.moved_manifest:
        targets.append(_MANIFEST_NAME)
    for ini_name, _created, _rel in state.applied_config:
        targets.append(f"{_CONFIG_DIR_REL}/{ini_name}")
    parked = 0
    for rel in targets:
        live = project_dir / rel
        if not live.is_file():
            continue
        try:
            dst = rescue / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(live, dst)
            parked += 1
        except OSError as exc:
            log(f"    could not park pre-heal bytes of {rel} ({exc})")
    # Whole isolated dirs: park any LIVE dir the restore would merge over.
    for src_rel, _backup_rel in state.isolated_dirs:
        live_dir = project_dir / src_rel
        if not live_dir.is_dir():
            continue
        try:
            shutil.copytree(live_dir, rescue / src_rel, dirs_exist_ok=True)
            parked += 1
        except OSError as exc:
            log(f"    could not park pre-heal dir {src_rel} ({exc})")
    return parked


def heal_leftover_fairness(project_dir: Path, runs_root: Path, *,
                           rescue: Optional[Path] = None,
                           log=lambda s: None) -> List[Path]:
    """Restore every CONSUMABLE leftover fairness_backup into ``project_dir``.

    Consumable = older than ``LEFTOVER_MIN_AGE_S`` (younger ones may belong to
    a drive in flight) AND recorded/assumed to target this project: a persisted
    fairness_state.json must name ``project_dir``; a legacy stateless backup
    is accepted on layout shape alone (it predates persistence — every such
    flow staged the one live substrate). Restores oldest-first so the newest
    bytes win; each clean restore consumes (deletes) its backup dir. When
    ``rescue`` is given, the pre-heal live bytes of every path the restore
    overwrites are parked there first (never destroy the only copy of what
    might be maintainer WIP).

    Returns the backup roots that were restored. Never raises — a restore
    failure keeps that backup on disk (it stays the recovery source) and the
    gate re-check after the heal decides whether the run can proceed.
    """
    try:
        project_key = str(Path(project_dir).resolve())
    except OSError:
        project_key = str(project_dir)
    healed: List[Path] = []
    for backup_root in find_leftover_backups(Path(runs_root)):
        age = _age_s(backup_root)
        if age < LEFTOVER_MIN_AGE_S:
            log(f"    skipping {backup_root} (only {age / 60:.0f} min old — "
                f"may belong to a drive in flight)")
            continue
        state = load_fairness_state(backup_root)
        if state.project_dir and _norm(state.project_dir) != _norm(project_key):
            log(f"    skipping {backup_root} (staged for a different project: "
                f"{state.project_dir})")
            continue
        if rescue is not None:
            n = _park_pre_heal_bytes(state, Path(project_dir), rescue, log=log)
            if n:
                log(f"    parked {n} pre-heal file(s)/dir(s) under {rescue}")
        try:
            stage_fairness_restore(state, Path(project_dir))
        except OSError as exc:
            log(f"    restore FAILED for {backup_root} ({exc}) — backup kept")
            continue
        log(f"    restored leftover fairness backup: {backup_root}")
        healed.append(backup_root)
    return healed


def find_writable_snapshots(runs_root: Path,
                            presnap_root: Optional[Path] = None) -> List[Path]:
    """Orphaned writable-tree snapshot dirs a heal may revert files from:
    run.py's ``runs/<id>/live_backup`` (flat + one container level) and
    run_graded's ``CB_TMP/cb-presnap/<safe_id>-<stamp>`` children."""
    snaps = list(find_leftover_backups(Path(runs_root), names=("live_backup",)))
    if presnap_root is not None:
        root = Path(presnap_root)
        if root.is_dir():
            snaps.extend(p for p in root.iterdir() if p.is_dir())
    return snaps


def default_presnap_root() -> Path:
    """CB_TMP/cb-presnap — where run_graded parks its pre-run writable
    snapshots. The SINGLE source of that root: run_graded.presnap_backup_dir
    and cb clean --presnaps both build from it."""
    return Path(os.environ.get("CB_TMP", tempfile.gettempdir())) / "cb-presnap"


def heal_dirty_from_presnap(project_dir: Path, dirty: List[str],
                            snapshots: List[Path], *,
                            rescue: Optional[Path] = None,
                            log=lambda s: None) -> int:
    """Revert gate-listed dirty tracked files from orphaned writable-tree
    snapshots (see :func:`find_writable_snapshots`) — the layer that heals a
    killed run's AGENT EDITS, which no fairness backup ever holds.

    ``dirty`` is check_substrate_clean's verbatim porcelain lines (paths are
    repo-root-relative). Each snapshot mirrors the writable tree keyed by
    project-relative paths; for every dirty file found in a consumable
    (age-floored) snapshot, the newest copy is put back — modified files are
    overwritten, deleted files reappear. Files no snapshot covers are left
    for the gate re-check to report. Returns the number of files healed.

    Safety rails: with ``rescue`` set, the pre-heal live bytes of every
    overwritten file are parked there first (a gate-listed file can be
    maintainer WIP, not crash dirt). Snapshots actually USED are CONSUMED
    (deleted) afterwards — without that, one stale orphan would silently
    re-clobber the same WIP on every subsequent gate forever.
    """
    project_dir = Path(project_dir)
    # Newest snapshot first — its bytes are closest to the state the killed
    # run started from (all snapshots are gate-verified ≡ HEAD anyway).
    candidates = [Path(s) for s in snapshots
                  if Path(s).is_dir() and _age_s(Path(s)) >= LEFTOVER_MIN_AGE_S]
    candidates.sort(key=_mtime_or_zero, reverse=True)
    if not candidates:
        return 0

    healed = 0
    used: List[Path] = []
    for line in dirty:
        path = porcelain_path(line)
        if not path:
            continue
        live = _repo_rel_to_live(project_dir, path)
        if live is None:
            continue
        rel = live.relative_to(project_dir).as_posix()
        for snap in candidates:
            src = snap / rel
            if src.is_file():
                if rescue is not None and live.is_file():
                    try:
                        dst = rescue / rel
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(live, dst)
                        log(f"    parked pre-heal bytes of {rel} under {rescue}")
                    except OSError as exc:
                        log(f"    could not park pre-heal bytes of {rel} ({exc})")
                live.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, live)
                log(f"    reverted {rel} from {snap.name}")
                healed += 1
                if snap not in used:
                    used.append(snap)
                break

    # Consume the snapshots we drew from — their remaining content is ≡ the
    # HEAD of their run's start (nothing git doesn't hold), and a survivor
    # would re-clobber the same paths on every later gate. Name-guarded to
    # the two snapshot kinds so a hand-passed arbitrary dir is never deleted.
    for snap in used:
        if snap.name == "live_backup" or "cb-presnap" in snap.parent.name:
            _robust_rmtree(snap)
            log(f"    consumed snapshot {snap}")
    return healed


def heal_crashed_run_leftovers(project_dir: Path, runs_root: Path,
                               dirty: List[str], *,
                               presnap_root: Optional[Path] = None,
                               log=lambda s: None) -> bool:
    """The DIRTY-SUBSTRATE gates' one-call self-heal: restore leftover
    fairness backups, then revert remaining gate-listed dirt from orphaned
    writable snapshots. Returns True iff anything was healed — the caller
    must then RE-RUN check_substrate_clean and gate on the fresh result
    (this function heals; it never certifies cleanliness).

    LIVE-RUN GUARD: refuses outright while the live-run lock is held — a
    drive in flight legitimately has the tree hidden, and consuming its
    backup/presnap would un-hide the answer key mid-measured-run (the age
    floor alone can't cover ceilings past 60 min). The lock dies with its
    process, so a hard-killed run never blocks the heal. Every overwrite
    parks the pre-heal live bytes under CB_TMP/cb-heal-rescue/<stamp>/."""
    try:
        from live_lock import is_live_run_active
        if is_live_run_active(Path(runs_root) / ".live-run.lock"):
            log("    a live-substrate run is ACTIVE (runs/.live-run.lock held) "
                "— refusing to touch its backups; aborting instead")
            return False
    except ImportError:
        pass  # standalone import context without live_lock on sys.path
    runs_root = Path(runs_root)
    if presnap_root is None:
        presnap_root = default_presnap_root()
    rescue = _rescue_dir()
    restored = heal_leftover_fairness(project_dir, runs_root,
                                      rescue=rescue, log=log)
    snaps = find_writable_snapshots(runs_root, presnap_root)
    reverted = heal_dirty_from_presnap(project_dir, dirty, snaps,
                                       rescue=rescue, log=log)
    changed = bool(restored) or reverted > 0
    if changed and rescue.exists():
        log(f"    pre-heal bytes preserved at {rescue} (recover overwritten "
            f"WIP from there if this heal was wrong)")
    return changed


def heal_and_recheck(project_dir: Path, runs_root: Path, dirty: List[str], *,
                     presnap_root: Optional[Path] = None,
                     log=lambda s: None) -> List[str]:
    """The full gate choreography the three DIRTY-SUBSTRATE gates share:
    attempt the crashed-run self-heal, then return the FRESH dirty list
    (re-running check_substrate_clean iff anything was healed). The caller
    keeps its own override + abort semantics over the returned list."""
    if not dirty:
        return dirty
    log("    writable tree has TRACKED modifications — trying self-heal "
        "from crashed-run leftovers...")
    if heal_crashed_run_leftovers(project_dir, runs_root, dirty,
                                  presnap_root=presnap_root, log=log):
        dirty = check_substrate_clean(Path(project_dir))
        if not dirty:
            log("    self-heal OK — tree restored to HEAD, proceeding")
    return dirty


def _norm(p) -> str:
    return os.path.normcase(os.path.normpath(str(p)))


def _repo_rel_to_live(project_dir: Path, repo_rel: str) -> Optional[Path]:
    """Map a porcelain repo-root-relative path onto the live project tree.

    The project dir's own repo-relative prefix isn't known here; instead,
    locate the project dir's NAME in the path and take everything after it.
    Returns None for paths outside the project (never healed)."""
    parts = Path(repo_rel).parts
    name = project_dir.name
    for i, part in enumerate(parts):
        if part == name and i < len(parts) - 1:
            return project_dir.joinpath(*parts[i + 1:])
    return None
