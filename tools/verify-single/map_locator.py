"""Locate a task ``.umap`` on disk — flat OR one-level-foldered layout.

Maps historically live flat at ``Content/Maps/<map>.umap``. After the
folder-per-task migration they may instead live at
``Content/Maps/<task-id>/<map>.umap``. Everything that used to hard-code the
flat path (the L2 editor positional map argument, the automation-filter map
segment) DISCOVERS the actual location through this module instead, so both
layouts grade identically.

Resolution rule (shared by every caller):

  1. Gather EVERY candidate for the basename: ``Content/Maps/<map>.umap`` plus
     ``Content/Maps/*/<map>.umap`` (one folder level only).
  2. **Two or more candidates raise `DuplicateMapBasenameError`** — a duplicate
     basename is a substrate bug, not something to silently pick a winner for.
  3. Exactly one candidate -> that location (flat or foldered).
  4. nothing on disk -> ``None``. Maps ship exclusively as committed binaries
     (scaffolders retired 2026-07), so callers treat a miss as an explicit
     FAIL — there is no re-bake fallback.

CHANGED 2026-08-08 (bp-g2 scale-up, I0.5b): rule 2 used to be "root ALWAYS
wins", and only a multi-FOLDER collision raised. That made the flat layout a
silent first-match: with ``L_GlideStamina.umap`` flat at ``Content/Maps/`` (it
and ``L_PoisonStack.umap`` are the two flat ThirdPerson maps; the other seven
are foldered under ``Content/Maps/<task-id>/``), a NEW task that committed
``Content/Maps/<new-id>/L_GlideStamina.umap`` would have been graded against
the OLD flat map with no diagnostic anywhere — the new task's fixture running
in the wrong world, reported as an ordinary L2 FAIL. Which map a task grades
against must never be decided by a tie-break. Flat-layout tasks are unaffected:
a basename with exactly one candidate resolves exactly as before, whichever
layout it is in.

The raise is deliberate and routes to HARNESS-ERROR (exit 7), never to a graded
FAIL: an ambiguous substrate is a repo defect, and a repo defect must not be
scored against the model under test.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence


@dataclass(frozen=True)
class MapLocation:
    """Where a map actually lives, in every coordinate system callers need."""

    # Absolute filesystem path to the found .umap.
    umap_path: Path
    # UE package path: "/Game/Maps/L_X" (root) or "/Game/Maps/<folder>/L_X".
    package_path: str
    # The dot-joined automation segment(s) between "Maps" and the map name in
    # a `Project.Functional Tests.Maps.<...>.<Map>.<Class>` filter: "" for
    # root maps, "<folder>" for one-level-foldered maps. Kept RAW (no leading/
    # trailing dot) — the CALLER composes the filter (derive_test_filter).
    automation_prefix: str


class DuplicateMapBasenameError(ValueError):
    """Two or more committed ``.umap``s under one substrate share a basename.

    Subclasses ``ValueError`` on purpose: the pre-2026-08-08 multi-folder
    ambiguity raised a plain ``ValueError``, and every caller that already
    handles that keeps working unchanged. The named type exists so a caller —
    or a log reader — can tell "the substrate is ambiguous" apart from any
    other ValueError without substring-matching a message.

    Carries the machine-readable facts (``map_name`` / ``maps_root`` /
    ``paths``) as attributes so a diagnostic never has to re-parse the text.
    """

    def __init__(self, map_name: str, maps_root: Path,
                 paths: Sequence[Path]) -> None:
        self.map_name = map_name
        self.maps_root = maps_root
        self.paths = tuple(paths)
        where = ", ".join(_candidate_label(p, maps_root) for p in self.paths)
        super().__init__(
            f"duplicate map basename '{map_name}.umap' under {maps_root}: "
            f"found in [{where}] - a duplicate basename is a substrate bug. "
            "Which map a task grades against must not be decided by a "
            "tie-break: rename one map (or delete the stale copy) so exactly "
            "one candidate remains."
        )


def _candidate_label(path: Path, maps_root: Path) -> str:
    """How to name one candidate in the error: ``<Maps root>`` for the flat
    copy, the folder name for a per-task-foldered one."""
    return "<Content/Maps>" if path.parent == maps_root else path.parent.name


def _map_candidates(maps_root: Path, map_name: str) -> List[Path]:
    """Every ``<map_name>.umap`` under ``maps_root``, flat first then one
    folder level deep (sorted, so the error text is deterministic)."""
    candidates: List[Path] = []
    flat = maps_root / f"{map_name}.umap"
    if flat.exists():
        candidates.append(flat)
    candidates.extend(sorted(maps_root.glob(f"*/{map_name}.umap")))
    return candidates


def locate_map(workdir_substrate: Path, map_name: str) -> Optional[MapLocation]:
    """Resolve ``map_name`` under ``<workdir_substrate>/Content/Maps/``.

    Exactly one candidate (flat ``<map>.umap`` OR one-level
    ``*/<map>.umap``) resolves. Two or more raise
    ``DuplicateMapBasenameError`` — including a flat copy colliding with a
    foldered one, which used to resolve silently to the flat copy. Nothing
    found returns ``None`` — callers grade that as an explicit FAIL (committed
    binaries are the only map source; scaffolders retired 2026-07).
    """
    maps_root = workdir_substrate / "Content" / "Maps"
    candidates = _map_candidates(maps_root, map_name)
    if len(candidates) > 1:
        raise DuplicateMapBasenameError(map_name, maps_root, candidates)
    if not candidates:
        return None
    found = candidates[0]
    if found.parent == maps_root:
        return MapLocation(
            umap_path=found.resolve(),
            package_path=f"/Game/Maps/{map_name}",
            automation_prefix="",
        )
    folder = found.parent.name
    return MapLocation(
        umap_path=found.resolve(),
        package_path=f"/Game/Maps/{folder}/{map_name}",
        automation_prefix=folder,
    )
