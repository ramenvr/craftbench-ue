"""Shared fail-closed paths and hashes for final Nav Invoker authoring."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat


TASK_ID = "t3-walkable-ground-follows-the-designated-scout"
HERE = Path(__file__).resolve().parent
TASK_ROOT = HERE.parent
REPO = TASK_ROOT.parents[2]
PROJECT_ROOT = REPO / "UE-projects" / "ThirdPerson"
PROJECT = PROJECT_ROOT / "ThirdPerson.uproject"
CONTENT = PROJECT_ROOT / "Content"
FINAL_DIR = CONTENT / "Tasks" / TASK_ID
FINAL_FILE = FINAL_DIR / "BP_DesignatedScout.uasset"
FINAL_ASSET = "/Game/Tasks/%s/BP_DesignatedScout" % TASK_ID
MAP_DIR = CONTENT / "Maps" / TASK_ID
FINAL_MAP = MAP_DIR / "L_WalkableGround.umap"
ADMISSION_MAP = MAP_DIR / "L_WalkableGroundAdmission.umap"
REFERENCE = TASK_ROOT / "reference"
REFERENCE_ASSET_DIR = REFERENCE / "Content" / "Tasks" / TASK_ID
IMMUTABLE = (
    ADMISSION_MAP,
    PROJECT,
    PROJECT_ROOT / "Source" / "ThirdPerson" / "ThirdPerson.Build.cs",
    PROJECT_ROOT / "Source" / "CraftBenchTests" / "CraftBenchTests.Build.cs",
    CONTENT / "Characters" / "Mannequins" / "Meshes" /
    "SKM_Manny_Simple.uasset",
    CONTENT / "Characters" / "Mannequins" / "Anims" / "Unarmed" /
    "ABP_Unarmed.uasset",
    CONTENT / "ThirdPerson" / "Blueprints" /
    "BP_ThirdPersonGameMode.uasset",
    CONTENT / "ThirdPerson" / "Blueprints" /
    "BP_ThirdPersonCharacter.uasset",
    CONTENT / "ThirdPerson" / "Blueprints" /
    "BP_ThirdPersonPlayerController.uasset",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def is_reparse(path: Path) -> bool:
    info = path.lstat()
    attributes = getattr(info, "st_file_attributes", 0)
    return path.is_symlink() or bool(
        attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def require_plain(path: Path) -> None:
    if not path.is_file() or is_reparse(path):
        raise RuntimeError("expected plain file: %s" % path)


def require_plain_ancestors(path: Path) -> None:
    current = Path(os.path.abspath(os.fspath(path)))
    while not current.exists():
        parent = current.parent
        if parent == current:
            raise RuntimeError("no existing ancestor: %s" % path)
        current = parent
    while True:
        if is_reparse(current):
            raise RuntimeError("reparse ancestor rejected: %s" % current)
        parent = current.parent
        if parent == current:
            break
        current = parent


def vector(paths) -> dict[str, str]:
    result = {}
    for path in paths:
        require_plain(path)
        result[str(path.relative_to(REPO)).replace("\\", "/")] = sha256(path)
    return result


def immutable_vector() -> dict[str, str]:
    return vector(IMMUTABLE)


def final_vector() -> dict[str, str]:
    observed = set(FINAL_DIR.iterdir()) if FINAL_DIR.is_dir() else set()
    if observed != {FINAL_FILE}:
        raise RuntimeError("final asset inventory mismatch: %r" %
                           sorted(str(item) for item in observed))
    return vector((FINAL_FILE,))


def map_vector() -> dict[str, str]:
    observed = set(MAP_DIR.iterdir()) if MAP_DIR.is_dir() else set()
    if observed != {ADMISSION_MAP, FINAL_MAP}:
        raise RuntimeError("map inventory mismatch: %r" %
                           sorted(str(item) for item in observed))
    return vector((ADMISSION_MAP, FINAL_MAP))


def reference_vector() -> dict[str, str]:
    observed = (set(REFERENCE_ASSET_DIR.iterdir())
                if REFERENCE_ASSET_DIR.is_dir() else set())
    expected = {REFERENCE_ASSET_DIR / FINAL_FILE.name}
    if observed != expected:
        raise RuntimeError("reference inventory mismatch: %r" %
                           sorted(str(item) for item in observed))
    return vector(tuple(expected))
