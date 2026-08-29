"""Shared immutable paths and hash locks for replicated-door authoring."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
TASK = HERE.parent
REPO = HERE.parents[3]
PROJECT = REPO / "UE-projects" / "ThirdPerson"
CONTENT = PROJECT / "Content"
TASK_ID = "t3-every-player-sees-the-same-door-state"

FINAL_PACKAGE = f"/Game/Tasks/{TASK_ID}/BP_ReplicatedDoorState"
FINAL_OBJECT = FINAL_PACKAGE + ".BP_ReplicatedDoorState"
FINAL_ASSET = CONTENT / "Tasks" / TASK_ID / "BP_ReplicatedDoorState.uasset"
ADMISSION_PACKAGE = (
    f"/Game/__CraftBenchAdmission/{TASK_ID}/BP_ReplicatedDoorState_Admission"
)
ADMISSION_OBJECT = ADMISSION_PACKAGE + ".BP_ReplicatedDoorState_Admission"
ADMISSION_ASSET = (
    CONTENT / "__CraftBenchAdmission" / TASK_ID
    / "BP_ReplicatedDoorState_Admission.uasset"
)
FINAL_MAP_PACKAGE = f"/Game/Maps/{TASK_ID}/L_ReplicatedDoorState"
FINAL_MAP = CONTENT / "Maps" / TASK_ID / "L_ReplicatedDoorState.umap"
ADMISSION_MAP_PACKAGE = (
    f"/Game/__CraftBenchAdmission/{TASK_ID}/L_ReplicatedDoorStateAdmission"
)
ADMISSION_MAP = (
    CONTENT / "__CraftBenchAdmission" / TASK_ID
    / "L_ReplicatedDoorStateAdmission.umap"
)
REFERENCE_ASSET = (
    TASK / "reference" / "Content" / "Tasks" / TASK_ID
    / "BP_ReplicatedDoorState.uasset"
)

BASELINE_VECTOR = (
    "PASS DOOR_BLUEPRINT mode=final solved=0 parent=direct variable=1 "
    "rpc=0 repnotify=0 nodes=1"
)
FINAL_SOLVED_VECTOR = (
    "PASS DOOR_BLUEPRINT mode=final solved=1 parent=direct variable=1 "
    "rpc=server_reliable repnotify=1 nodes=5 onrep_graph=1"
)
ADMISSION_VECTOR = (
    "PASS DOOR_BLUEPRINT mode=admission solved=1 parent=direct variable=1 "
    "rpc=server_reliable repnotify=1 nodes=5 onrep_graph=1"
)
FINAL_MAP_VECTOR = (
    "PASS DOOR_MAP mode=final map_exact=1 doors=1 fixtures=1 "
    "player_starts=1 game_mode_exact=1 playable=1 fixture_bound=1 "
    "revision=0 closed=1"
)
ADMISSION_MAP_VECTOR = FINAL_MAP_VECTOR.replace("mode=final", "mode=admission")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def is_reparse(path: Path) -> bool:
    try:
        attrs = path.lstat().st_file_attributes
    except AttributeError:
        return path.is_symlink()
    return bool(attrs & 0x400)


def regular_vector(paths: tuple[Path, ...]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for path in paths:
        if not path.is_file() or path.is_symlink() or is_reparse(path):
            raise RuntimeError("missing/nonregular protected file: %s" % path)
        result[str(path)] = {"size": path.stat().st_size, "sha256": sha256(path)}
    return result


def optional_vector(paths: tuple[Path, ...]) -> dict[str, object]:
    result: dict[str, object] = {}
    for path in paths:
        if os.path.lexists(path):
            if not path.is_file() or path.is_symlink() or is_reparse(path):
                raise RuntimeError("unexpected nonregular optional file: %s" % path)
            result[str(path)] = {"size": path.stat().st_size,
                                 "sha256": sha256(path)}
        else:
            result[str(path)] = None
    return result


def exact_files(directory: Path) -> tuple[Path, ...]:
    if not directory.exists():
        return ()
    if not directory.is_dir() or directory.is_symlink() or is_reparse(directory):
        raise RuntimeError("nonregular directory: %s" % directory)
    return tuple(sorted(path for path in directory.rglob("*") if path.is_file()))


def assert_absent(*paths: Path) -> None:
    unexpected = [str(path) for path in paths if os.path.lexists(path)]
    if unexpected:
        raise RuntimeError("expected absent paths: %r" % unexpected)
