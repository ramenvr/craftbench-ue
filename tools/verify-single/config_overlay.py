"""Per-task UE config overlay (B7).

A task folder may ship verifier-owned ``Config/*.ini`` fragments at
``tasks/<set>/<id>/ue-config/<IniName>.ini`` (e.g. ``DefaultGameplayTags.ini``,
``DefaultEngine.ini``). Each fragment is APPEND-applied onto the substrate's
``Config/<IniName>.ini`` (creating the file if absent) under a marker header
comment (``; CraftBench per-task overlay: <task-id>``). UE ini semantics are
later-wins for scalar keys plus ``+Array`` accumulation lines, so a plain
append suffices — no section-merge logic.

Two application points share this module:

  * **Verifier workdir staging** (``run_task.py``): the workdir is a
    disposable substrate copy, so nothing reverts it — cold workdirs are
    deleted after the grade and warm slots snapshot + reset ``Config/`` to
    pristine each verify (see ``warm_cache.VERIFIER_MUTABLE_PREFIXES``).
  * **Live-editor drives** (``tools/run-agent/fairness.py``): applied before
    the editor launch and reverted BYTE-IDENTICALLY afterwards via
    :func:`revert`, driven by the FairnessState restore flow.

The fragments live OUTSIDE the UE project (in the task folder), and
``Config/`` stays agent-denied per ``AGENT_WRITABLE.json`` — so the overlay
never widens the agent's writable surface and the verifier hash-pin surface
(``Source/CraftBenchTests/``) is untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# The optional per-task fragment directory, sibling to a folder-form task.md.
UE_CONFIG_DIR_NAME = "ue-config"

# Header comment prepended to every appended fragment. `;` is the UE ini
# comment leader, so the marker is inert config-wise but greppable and makes
# the appended block attributable to its task in a merged Config/<ini>.
MARKER_PREFIX = "; CraftBench per-task overlay: "


@dataclass
class AppliedFragment:
    """One ``Config/<ini_name>`` mutation, recorded for a byte-identical revert."""

    ini_name: str
    created: bool  # Config/<ini_name> did not exist before apply
    original_bytes: Optional[bytes]  # pre-apply bytes; None when created


def discover(task_spec_path: Path) -> dict[str, Path]:
    """Map ``<IniName>.ini -> fragment path`` from the task folder's ue-config/.

    Folder-form specs only: when the spec filename is ``task.md``, the sibling
    ``ue-config/`` directory in the task folder is scanned for ``*.ini`` files.
    Flat specs (``tasks/<set>/<id>.md``) and folders without ``ue-config/``
    yield ``{}`` — the no-op path every current task takes. Non-ini files and
    subdirectories inside ``ue-config/`` are ignored.
    """
    spec = Path(task_spec_path)
    if spec.name != "task.md":
        return {}
    cfg_dir = spec.parent / UE_CONFIG_DIR_NAME
    if not cfg_dir.is_dir():
        return {}
    return {
        p.name: p
        for p in sorted(cfg_dir.iterdir())
        if p.is_file() and p.suffix.lower() == ".ini"
    }


def apply(
    config_dir: Path, fragments: dict[str, Path], task_id: str
) -> list[AppliedFragment]:
    """Append every fragment onto ``config_dir/<IniName>.ini`` (marker-headed).

    Each target receives ``"\\n" + marker line + fragment text`` (fragment text
    gets a trailing newline if it lacks one); a missing target is created and a
    missing ``config_dir`` is created too. Applied in sorted ini-name order for
    deterministic logs. Returns one :class:`AppliedFragment` per target with
    the pre-apply bytes, so callers that must undo the mutation (live-editor
    drives) can :func:`revert` byte-identically. Verifier workdir staging
    discards the return value — the workdir is disposable.
    """
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    applied: list[AppliedFragment] = []
    for ini_name in sorted(fragments):
        frag_text = Path(fragments[ini_name]).read_text(encoding="utf-8")
        if not frag_text.endswith("\n"):
            frag_text += "\n"
        target = config_dir / ini_name
        created = not target.exists()
        original = None if created else target.read_bytes()
        block = f"\n{MARKER_PREFIX}{task_id}\n{frag_text}"
        with open(target, "ab") as fh:  # append; creates the file when absent
            fh.write(block.encode("utf-8"))
        applied.append(
            AppliedFragment(
                ini_name=ini_name, created=created, original_bytes=original
            )
        )
    return applied


def revert(config_dir: Path, applied: list[AppliedFragment]) -> None:
    """Undo :func:`apply` byte-identically: restore each target's pre-apply
    bytes, and DELETE targets the apply created. Idempotent — a second call
    rewrites identical bytes and tolerates already-deleted created files.
    (The verifier staging path never calls this; live-editor drives do.)
    """
    config_dir = Path(config_dir)
    for frag in applied:
        target = config_dir / frag.ini_name
        if frag.created:
            if target.exists():
                target.unlink()
        elif frag.original_bytes is not None:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(frag.original_bytes)
