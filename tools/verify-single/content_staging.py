"""Per-task CONTENT staging — prune other tasks' content from a staged workdir.

The graded workdir used to ship the ENTIRE substrate: all ~28 committed maps
and every task's ``Content/Tasks/`` baseline, even when grading one task. This
module makes the staged project carry only what the graded task needs.

Scope — CONTENT ONLY, by design. ``Source/`` always stays whole: the L1 build
compiles the verifier-owned CraftBenchTests module, whose per-task fixtures
``#include`` their task scaffolds, so excluding foreign source breaks the
verifier's own compile. What CAN be excluded, for a graded task ``T``:

  * other tasks' ``Content/Maps/<task-id>/`` folders (folder-per-task maps);
  * flat pre-convention ``Content/Maps/<map>.umap`` files owned by other
    tasks — ownership is DERIVED from the task specs (``spec.py`` is the
    single parser; fixtures / legacy ``map_name``), never hand-coded;
  * other tasks' ``Content/Tasks/<task-id>/`` asset baselines;
  * other tasks' OFPA mirrors under ``Content/__ExternalActors__/Tasks/<id>``
    and ``Content/__ExternalObjects__/Tasks/<id>`` (ThirdPerson);
  * protected-map OFPA mirrors under ``Content/__ExternalActors__/Maps/<id>``
    and ``Content/__ExternalObjects__/Maps/<id>``. These are task-addressed
    side packages and travel in lockstep with ``Content/Maps/<id>``.

Everything else is KEPT: the graded task's own map(s) + baseline + OFPA
mirrors, all non-task content (Characters/, engine basics, template content),
and anything not attributable to a task.

FAIL-OPEN IS THE CONTRACT. A wrongly-KEPT file costs bytes; a wrongly-EXCLUDED
map is a false L2 FAIL scored against the model — the one unforgivable failure
mode. Therefore:

  * ownership is claimed only from a spec that parses; an unparseable spec
    contributes nothing, so its content stays staged;
  * a map/folder claimed by NO spec stays staged;
  * a map claimed by the graded task AND others stays staged;
  * flat-map ownership is derived per-substrate (the two glide variants share
    the ``L_GlideStamina`` basename across CraftBenchTemplate/ThirdPerson —
    cross-substrate claims must not attribute this substrate's file);
  * any error deriving ownership stages the FULL substrate with a note; a
    single failed deletion keeps that entry and notes it. The filter can
    never fail a run — it is NON-GATING and never reaches a verdict.

The report records the staging outcome (``content_staging``: mode + excluded
count + entries) so a graded report is self-describing. Escape hatch:
``--full-substrate`` / ``CB_FULL_SUBSTRATE=1`` stages everything, recorded as
``mode: "full"``.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from spec import TaskSpec, parse_task_file

# Report / provenance mode strings.
MODE_PER_TASK = "per-task"
MODE_FULL = "full"

# UE's two OFPA namespaces. Both the agent-authored Tasks/<id> branch and the
# verifier-owned protected-map Maps/<id> branch are task-addressed mirrors.
_OFPA_ROOTS = ("__ExternalActors__", "__ExternalObjects__")


class OwnershipError(RuntimeError):
    """Ownership derivation could not produce a trustworthy answer at all.

    Raised (and caught by ``stage_per_task_content``) so the caller stages the
    FULL substrate with a note instead of pruning on bad data.
    """


@dataclass
class ContentOwnership:
    """Which task owns which content, derived from the task specs.

    ``map_owners`` maps a map basename (no extension, e.g. ``L_GlideStamina``)
    to the set of task ids claiming it — SAME-SUBSTRATE specs only, because a
    basename can legitimately repeat across substrates (both glide variants).
    ``task_ids`` is every parseable spec's id across ALL substrates: an
    id-named directory belongs to that task wherever it appears.
    """

    map_owners: dict[str, set[str]] = field(default_factory=dict)
    task_ids: set[str] = field(default_factory=set)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StagingResult:
    """Outcome of one staging pass — what the report records.

    ``mode`` is ``"per-task"`` (filter ran) or ``"full"`` (escape hatch, or
    fail-open on a derivation error — the note says which). ``excluded`` holds
    workdir-substrate-relative POSIX paths actually removed, sorted.
    """

    mode: str
    excluded: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "mode": self.mode,
            "excluded_count": len(self.excluded),
        }
        if self.excluded:
            d["excluded"] = list(self.excluded)
        if self.notes:
            d["notes"] = list(self.notes)
        return d


def full_substrate_requested(
    cli_flag: bool, env: Optional[Mapping[str, str]] = None
) -> bool:
    """True when the escape hatch is engaged (``--full-substrate`` flag OR
    ``CB_FULL_SUBSTRATE=1`` truthy in ``env``/os.environ)."""
    e = os.environ if env is None else env
    return bool(cli_flag) or (
        str(e.get("CB_FULL_SUBSTRATE", "")).strip().lower()
        in ("1", "true", "yes", "on")
    )


def _spec_map_names(spec: TaskSpec) -> set[str]:
    """Every map basename a spec claims: v2 fixtures, legacy single-fixture
    ``map_name`` derivation, and the legacy L3 fixture block."""
    names = {fx.map_name for fx in spec.fixtures}
    names.update(fx.map_name for fx in spec.l3_fixtures)
    if spec.map_name:
        names.add(spec.map_name)
    return {n for n in names if n}


def derive_content_ownership(
    tasks_root: Path,
    substrate_dir_name: str,
    *,
    substrate_alias: Optional[Callable[[str], str]] = None,
) -> ContentOwnership:
    """Walk ``tasks_root`` for ``task.md`` specs and derive content ownership.

    ``substrate_alias`` maps a spec's ``substrate:`` value to its on-disk dir
    name (run_task passes ``_substrate_dir_name``); identity when omitted.
    Per-spec parse failures are fail-open — noted, and that task claims
    nothing (its content stays staged). Raises :class:`OwnershipError` when no
    spec at all is found (a mis-resolved tasks root must not be read as "no
    tasks exist, prune freely").
    """
    alias = substrate_alias or (lambda k: k)
    own = ContentOwnership()
    if not tasks_root.is_dir():
        raise OwnershipError(f"tasks root not found: {tasks_root}")
    spec_paths = sorted(tasks_root.rglob("task.md"))
    if not spec_paths:
        raise OwnershipError(f"no task specs (task.md) found under {tasks_root}")
    for spec_path in spec_paths:
        try:
            spec = parse_task_file(spec_path)
        except Exception as exc:  # noqa: BLE001 — fail-open per spec
            own.notes.append(
                f"spec unparseable — its content stays staged (fail-open): "
                f"{spec_path}: {exc}"
            )
            continue
        own.task_ids.add(spec.task_id)
        try:
            spec_substrate = alias(spec.substrate)
        except Exception:  # noqa: BLE001 — fail-open per spec
            continue
        if spec_substrate != substrate_dir_name:
            continue
        for map_name in _spec_map_names(spec):
            own.map_owners.setdefault(map_name, set()).add(spec.task_id)
    return own


def compute_exclusions(
    workdir_substrate: Path,
    graded_task: TaskSpec,
    ownership: ContentOwnership,
) -> list[Path]:
    """Absolute paths under ``<workdir_substrate>/Content/`` to exclude for
    ``graded_task``. Pure computation — deletes nothing.

    Every rule keeps on ambiguity: a path is excluded only when it is
    positively attributed to at least one task and NONE of its owners is the
    graded task.
    """
    tid = graded_task.task_id
    own_maps = _spec_map_names(graded_task)
    content = workdir_substrate / "Content"
    exclusions: list[Path] = []

    # --- Content/Maps: per-task folders + flat pre-convention maps ---------
    maps_root = content / "Maps"
    if maps_root.is_dir():
        for entry in sorted(maps_root.iterdir()):
            if entry.is_dir():
                stems = {u.stem for u in entry.glob("*.umap")}
                owners: set[str] = set()
                if entry.name in ownership.task_ids:
                    owners.add(entry.name)  # folder-per-task convention
                for stem in stems:
                    owners |= ownership.map_owners.get(stem, set())
                if owners and tid not in owners and not (stems & own_maps):
                    exclusions.append(entry)
            elif entry.suffix.lower() == ".umap":
                owners = ownership.map_owners.get(entry.stem, set())
                if owners and tid not in owners and entry.stem not in own_maps:
                    exclusions.append(entry)
                    # A map's cooked-lighting sidecar travels with the map.
                    built = entry.with_name(f"{entry.stem}_BuiltData.uasset")
                    if built.exists():
                        exclusions.append(built)
            # Anything else directly under Maps/ is unattributable — KEEP.

    # --- Content/Tasks/<id>: per-task asset baselines ----------------------
    # --- OFPA mirrors: Content/__External*__/Tasks/<id> --------------------
    id_dir_roots = [content / "Tasks"]
    id_dir_roots += [
        content / ofpa / branch
        for ofpa in _OFPA_ROOTS
        for branch in ("Tasks", "Maps")
    ]
    for root in id_dir_roots:
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir()):
            if (
                entry.is_dir()
                and entry.name in ownership.task_ids
                and entry.name != tid
            ):
                exclusions.append(entry)
            # Names that are not a known task id (e.g. _runreport) — KEEP.

    return exclusions


def stage_per_task_content(
    workdir_substrate: Path,
    graded_task: TaskSpec,
    tasks_root: Path,
    substrate_dir_name: str,
    *,
    substrate_alias: Optional[Callable[[str], str]] = None,
) -> StagingResult:
    """Prune other tasks' content from ``workdir_substrate`` for ``graded_task``.

    NEVER raises and NEVER fails a run: any error in ownership derivation or
    exclusion computation returns ``mode: "full"`` with a note (nothing was
    deleted — derivation runs before any removal); a single failed deletion
    keeps that entry and notes it. Deletions are confined to ``Content/`` by
    construction, with a defensive containment check per entry.
    """
    try:
        ownership = derive_content_ownership(
            tasks_root, substrate_dir_name, substrate_alias=substrate_alias
        )
        exclusions = compute_exclusions(workdir_substrate, graded_task, ownership)
    except Exception as exc:  # noqa: BLE001 — the filter must never fail a run
        return StagingResult(
            mode=MODE_FULL,
            excluded=(),
            notes=(
                "per-task content staging disabled (fail-open) — full "
                f"substrate staged: {exc}",
            ),
        )

    notes = list(ownership.notes)
    removed: list[str] = []
    content_root = (workdir_substrate / "Content").resolve()
    for path in exclusions:
        try:
            rel = path.resolve().relative_to(content_root)
        except ValueError:
            notes.append(
                f"refused to remove path outside Content/ (kept): {path}"
            )
            continue
        rel_posix = f"Content/{rel.as_posix()}"
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            removed.append(rel_posix)
        except OSError as exc:
            notes.append(f"could not remove {rel_posix} (kept): {exc}")
    return StagingResult(
        mode=MODE_PER_TASK,
        excluded=tuple(sorted(removed)),
        notes=tuple(notes),
    )
