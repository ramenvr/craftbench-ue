# tools/verify-single/task_layout.py
"""Shared per-task layout classification + additive staging (Phase C0).

THE single source of truth for "which files belong to which task" — used by
the verifier (workdir staging + the manifest-v2 integrity check) and, via the
run-agent side, by fairness/preamble consumers. Inverting the fairness model
(monolithic substrate + hide-foreign  →  disposable trees staged to
base ∪ active-task) requires both sides to classify identically; this module
absorbs the previously-unwired ``staging.py`` classifier (unit-tested since
2026-06-18, blocked only by the old full-set hash manifest — the v2 manifest
removes that blocker).

Classification is layered:
  * STRUCTURAL (authoritative): per-task DIRECTORIES under PER_TASK_ROOTS —
    ``Source/CraftBenchTemplate/Tasks/<id>/``, ``Source/CraftBenchTests/
    Tasks/<id>/``, ``Content/Maps/<id>/``, ``Content/Tasks/<id>/``, and the
    matching OFPA side-package roots below ``Content/__External*/Maps/<id>/``.
    A task
    "participates" in structural staging once it is foldered (t0 today; the
    7 flat tasks migrate in C3).
  * MARKER (fallback for the flat writable module): the ``for task <id>``
    header comment, pair-aware (.h/.cpp with one tagged sibling stage
    together), WRAP-tolerant (three real fixtures split the tag across a
    comment line). Fail-safe: untagged files are always KEPT.
  * ALLOWLIST (the verifier-only tests module): base infrastructure that is
    never per-task — module files, the two fixture base classes, the shared
    L3 render probe, the deny marker.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

# "Which identity does a pair SHARE?" has exactly ONE implementation, in
# tools/runlib/run_identity.py, which also owns the surface-suffix list. Bridged
# onto sys.path by DIRECTORY -- the pattern layers/registry.py
# and dashboard/collect.py all use -- rather than copied, because a second copy
# of the suffix rule is how the staging below silently disagreed with the task
# ids in the first place. Resolved relative to THIS file, so it works whichever
# tree imports it (verify-single directly, or aura_rig/tasks.py).
_RUNLIB = Path(__file__).resolve().parent.parent / "runlib"
if str(_RUNLIB) not in sys.path:
    sys.path.insert(0, str(_RUNLIB))
from run_identity import pair_base  # noqa: E402

# Roots whose IMMEDIATE child directories are per-task folders. Source roots
# are per-task by construction; the Content roots additionally require a
# task-id-looking name (engine folders — Developers/, __ExternalActors__/ —
# must be kept). The tuple is the UNION across substrates (CraftBenchTemplate
# and ThirdPerson writable modules); a root absent from a given tree is a
# no-op in every consumer, so listing both is safe on either substrate.
PER_TASK_ROOTS = (
    "Source/CraftBenchTemplate/Tasks",
    "Source/CraftBenchTests/Tasks",
    "Source/ThirdPerson/Tasks",
    "Content/Maps",
    "Content/Tasks",
    "Content/__ExternalActors__/Maps",
    "Content/__ExternalObjects__/Maps",
    "Plugins/GameFeatures/Tasks",
)

WRITABLE_MODULE_REL = "Source/CraftBenchTemplate"
TESTS_MODULE_REL = "Source/CraftBenchTests"

# Kebab-case task id (t0-sanity-log-on-beginplay, gp-spawner-population).
TASK_DIR_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# The "for task <id>" scaffold/fixture self-declaration. The id may wrap onto
# the next comment line ("… fixture for task\n// gp-harvestable-regrow") —
# keep in lockstep with tools/run-agent/fairness.py:_FOR_TASK_RE.
FOR_TASK_RE = re.compile(
    r"for task\s+(?://+\s*)?([a-z0-9][a-z0-9-]*)", re.IGNORECASE)
HEAD_BYTES = 4096

# CraftBenchTests files that are BASE infrastructure (never per-task): the
# module triple, the two abstract fixture base classes every L2 fixture
# derives from, the shared L3 render probe, and the sandbox deny marker.
# Everything else in the tests module is a task fixture (foldered under
# Tasks/<id>/ post-migration; flat + marker/name-classified until then).
TESTS_BASE_ALLOWLIST = frozenset({
    "CraftBenchTests.h",
    "CraftBenchTests.cpp",
    "CraftBenchTests.Build.cs",
    "CraftBenchFunctionalTest.h",
    "CraftBenchFunctionalTest.cpp",
    "CraftBenchPawnFunctionalTest.h",
    "CraftBenchPawnFunctionalTest.cpp",
    "RenderProbeFunctionalTest.h",
    "RenderProbeFunctionalTest.cpp",
    ".AGENT_WRITE_DENY",
})

# Root-level map FILES under Content/Maps/ that are shared infrastructure,
# not task fixtures (kept on every staged surface). Per-task-foldered maps
# are handled structurally via PER_TASK_ROOTS.
ROOT_MAPS_SHARED_KEEP = frozenset({"L_RenderProbe"})

# Every L_<Name> token a task spec can name (fixtures block, workspace-state
# prose). Used to decide which root-level flat maps the active task needs.
# IGNORECASE + the case-insensitive stem compare in stage_root_maps keep this
# in lockstep with the runner's case-insensitive map derivation
# (run_task.py's _MAP_NAME_RE) — a lowercase spec mention must not prune a
# map the runner would still drive.
MAP_NAME_RE = re.compile(r"\bL_[A-Za-z0-9_]+\b", re.IGNORECASE)


def bare_task_id(task_id: str) -> str:
    """'set/id' (either separator) → bare 'id', lowercased."""
    return (task_id or "").lower().replace("\\", "/").rsplit("/", 1)[-1]


def declared_tasks(path: Path) -> Set[str]:
    """Task ids self-declared in a file's header comment (first HEAD_BYTES)."""
    try:
        head = Path(path).read_text(encoding="utf-8", errors="replace")[:HEAD_BYTES]
    except OSError:
        return set()
    return {m.group(1).lower() for m in FOR_TASK_RE.finditer(head)
            if TASK_DIR_RE.match(m.group(1).lower())}


def classify_tests_rel(rel: str) -> Optional[str]:
    """Classify a Source/CraftBenchTests-relative path: None = base, else the
    owning task id. STRUCTURAL only (manifest v2 keying): ``Tasks/<id>/...``
    → <id>; everything else is base until its task folders (C3)."""
    parts = rel.replace("\\", "/").split("/")
    if len(parts) >= 3 and parts[0] == "Tasks" and TASK_DIR_RE.match(parts[1]):
        return parts[1]
    return None


def expected_fileset(entry: dict, active_task_id: Optional[str]) -> Dict[str, str]:
    """The {rel: sha} set a staged workdir MUST equal, from a manifest-v2
    entry: base ∪ tasks[active]. ``active_task_id=None`` = staging not wired
    (C0/C1 interim): expect base ∪ ALL tasks — byte-equivalent to the legacy
    full-set check."""
    expected = dict(entry.get("base") or {})
    tasks = entry.get("tasks") or {}
    if active_task_id is None:
        for files in tasks.values():
            expected.update(files)
    else:
        expected.update(tasks.get(bare_task_id(active_task_id)) or {})
    return expected


def split_manifest_v2(current: Dict[str, str]) -> dict:
    """Regen helper: split a flat {rel: sha} tree-hash map into the v2 entry
    {schema:2, base:{}, tasks:{<id>:{}}} by STRUCTURAL classification."""
    base: Dict[str, str] = {}
    tasks: Dict[str, Dict[str, str]] = {}
    for rel, sha in sorted(current.items()):
        tid = classify_tests_rel(rel)
        if tid is None:
            base[rel] = sha
        else:
            tasks.setdefault(tid, {})[rel] = sha
    return {"schema": 2, "base": base, "tasks": tasks}


# --------------------------------------------------------------------------- #
# Additive staging (delete-foreign in a DISPOSABLE tree; never the checkout).  #
# --------------------------------------------------------------------------- #

def stage_flat_scaffolds_active_only(
        tree: Path, active_task_id: str, *,
        module_rel: str = WRITABLE_MODULE_REL) -> List[str]:
    """The absorbed staging.py classifier: delete foreign-task marker-tagged
    .h/.cpp pairs from the flat writable module of a DISPOSABLE tree, keeping
    the active task's scaffold + all untagged shared infra. Pair-aware (one
    tagged sibling stages the pair). Returns sorted removed module-relative
    POSIX paths. Fail-safe: untagged files are always kept."""
    active = bare_task_id(active_task_id)
    src_dir = Path(tree) / module_rel
    if not src_dir.is_dir():
        return []
    by_stem = defaultdict(lambda: {"paths": [], "tasks": set()})
    for p in sorted(src_dir.glob("*")):
        if not p.is_file() or p.suffix.lower() not in (".h", ".cpp"):
            continue
        info = by_stem[p.stem]
        info["paths"].append(p)
        info["tasks"] |= declared_tasks(p)
    removed: List[str] = []
    for _stem, info in sorted(by_stem.items()):
        tasks = info["tasks"]
        if not tasks:                       # untagged shared infra → keep
            continue
        if active and active in tasks:      # active task's scaffold → keep
            continue
        for p in info["paths"]:
            removed.append(p.relative_to(src_dir).as_posix())
            p.unlink()
    return sorted(removed)


def stage_per_task_dirs_active_only(
        tree: Path, active_task_id: str, *,
        roots: Iterable[str] = PER_TASK_ROOTS) -> List[str]:
    """Delete foreign per-task DIRECTORIES under the per-task roots of a
    DISPOSABLE tree (structural staging). Under the Content roots a child
    counts as per-task only when task-id-named (engine folders are kept).
    The OFPA ``__ExternalActors__/Maps`` and ``__ExternalObjects__/Maps``
    roots intentionally use the same immediate task id as ``Content/Maps``;
    their side packages therefore stage in lockstep with the owning map.
    Returns sorted removed tree-relative POSIX dir paths."""
    import shutil
    active = bare_task_id(active_task_id)
    # A PAIR SHARES DIRECTORIES, so the keep test is the pair base, not the id.
    #
    # This was exact id equality, and the 2026-08-20 surface rename broke it
    # silently: the ids gained `-bp`/`-cpp` suffixes while the directories a pair
    # shares kept their old names. Measured on
    # `t1-mud-wade`: staging deleted
    # `Content/Tasks/<base>/` (the SUPPLIED animation clip the prompt orders the
    # agent to play) and `Source/ThirdPerson/Tasks/<base>-cpp/` (the PARENT CLASS
    # the Blueprint must derive from) -- for BOTH legs, since neither id equals
    # the unsuffixed directory name. The `-cpp` leg was broken too, and nobody
    # noticed because that pair had never been graded.
    #
    # NOT a leak. Per-task substrate content is SUPPLIED material; an answer
    # never lives in the substrate (references live under `tasks/<set>/<id>/`,
    # which the repo-level answer hide parks outright). Sharing is what makes a
    # pair a pair, so this is the semantically correct rule, not a workaround.
    # GATED on the active id actually CARRYING a surface suffix, which is what
    # makes it half of a pair. Measured convention in the corpus: a paired task
    # suffixes BOTH legs (`gp-glide-stamina-bp` / `gp-glide-stamina-cpp`), while a
    # STANDALONE task carries no suffix at all (`gp-crafting-queue`,
    # `gp-harvestable-regrow`). Without this gate an unsuffixed active task would
    # start keeping any `<id>-bp` directory as though it had a twin -- there is no
    # such directory today, and "there is no such directory today" is exactly the
    # premise that rots. A test pins both directions.
    active_base = pair_base(active_task_id)
    if active_base == active:
        active_base = ""      # standalone task: keep only its own directory
    removed: List[str] = []
    for root_rel in roots:
        root = Path(tree) / root_rel
        if not root.is_dir():
            continue
        require_task_like = root_rel.replace("\\", "/").startswith("Content/")
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            name = child.name
            if active and name.lower() == active:
                continue
            if active_base and pair_base(name) == active_base:
                continue
            if require_task_like and not TASK_DIR_RE.match(name):
                continue
            removed.append(f"{root_rel}/{name}")
            shutil.rmtree(child)
    return sorted(removed)


def spec_map_names(spec_text: str) -> Set[str]:
    """The set of L_<Name> tokens a task spec mentions anywhere. Deliberately
    a SUPERSET of the maps the task actually drives — root-map staging keeps
    every map the spec names, so a stray prose mention can only fail SAFE
    (keep), never break a drive by over-pruning."""
    return set(MAP_NAME_RE.findall(spec_text or ""))


def stage_root_maps_active_only(
        tree: Path, keep_map_names: Iterable[str], *,
        maps_rel: str = "Content/Maps",
        shared_keep: Iterable[str] = ROOT_MAPS_SHARED_KEEP) -> List[str]:
    """Delete root-LEVEL map artifacts (``*.umap`` / ``*.uasset`` and any
    legacy ``*.umap.NOTE.md`` sibling) directly under ``<maps_rel>`` of a
    DISPOSABLE tree unless the map stem is in ``keep_map_names`` or
    ``shared_keep``. Closes the pre-migration flat-map gap:
    :func:`stage_per_task_dirs_active_only` walks per-task DIRECTORIES only,
    so flat map FILES at the root used to survive onto every agent-visible
    surface. Returns sorted removed tree-relative POSIX paths."""
    maps_dir = Path(tree) / maps_rel
    if not maps_dir.is_dir():
        return []
    keep = ({str(k).lower() for k in keep_map_names}
            | {str(s).lower() for s in shared_keep})
    removed: List[str] = []
    for p in sorted(maps_dir.iterdir()):
        if not p.is_file():
            continue                            # per-task dirs: other stager
        name = p.name
        for suffix in (".umap.NOTE.md", ".umap", ".uasset"):
            if name.endswith(suffix):
                stem = name[:-len(suffix)]
                break
        else:
            continue                            # non-map root files are kept
        if stem.lower() in keep:
            continue
        removed.append(f"{maps_rel}/{name}")
        p.unlink()
    return sorted(removed)


def strip_tests_to_base(tree: Path, *, keep_task: Optional[str] = None,
                        tests_rel: str = TESTS_MODULE_REL) -> List[str]:
    """DRIVE-side staging of the verifier-only module: delete every tests-module
    file that is neither base-allowlisted nor (optionally) the kept task's
    foldered fixtures. With ``keep_task=None`` the drive project carries ONLY
    the base classes — fixtures never reach the agent-visible tree, which
    retires body-stubbing entirely. Returns sorted removed module-relative
    POSIX paths."""
    import shutil
    tests_dir = Path(tree) / tests_rel
    if not tests_dir.is_dir():
        return []
    keep = bare_task_id(keep_task) if keep_task else None
    removed: List[str] = []
    for p in sorted(tests_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(tests_dir).as_posix()
        tid = classify_tests_rel(rel)
        if tid is None:
            if rel in TESTS_BASE_ALLOWLIST:
                continue                      # base infra → keep
        elif keep and tid == keep:
            continue                          # kept task's fixtures
        removed.append(rel)
        p.unlink()
    # Sweep now-empty per-task dirs (and the Tasks root itself when emptied).
    tasks_root = tests_dir / "Tasks"
    if tasks_root.is_dir():
        for d in sorted(tasks_root.iterdir()):
            if d.is_dir() and not any(d.iterdir()):
                shutil.rmtree(d)
        if not any(tasks_root.iterdir()):
            tasks_root.rmdir()
    return sorted(removed)
