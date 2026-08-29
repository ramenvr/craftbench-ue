"""Exact paths and hash locks for the cross-world epoch task."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat


TASK_ID = "t3-the-old-world-cannot-complete-into-the-new-one"
HERE = Path(__file__).resolve().parent
TASK = HERE.parent
REPO = HERE.parents[3]
PROJECT_ROOT = REPO / "UE-projects" / "ThirdPerson"
PROJECT = PROJECT_ROOT / "ThirdPerson.uproject"
CONTENT = PROJECT_ROOT / "Content"
MAP_ROOT = CONTENT / "Maps" / TASK_ID
SUPPORT_ROOT = MAP_ROOT / "Support"
OLD_ASSET = SUPPORT_ROOT / "DA_EpochRecord_Old.uasset"
NEW_ASSET = SUPPORT_ROOT / "DA_EpochRecord_New.uasset"
OLD_MAP = MAP_ROOT / "L_OldEpochStart.umap"
NEW_MAP = MAP_ROOT / "L_NewEpochDestination.umap"
OLD_PACKAGE = f"/Game/Maps/{TASK_ID}/L_OldEpochStart"
NEW_PACKAGE = f"/Game/Maps/{TASK_ID}/L_NewEpochDestination"
OLD_RECORD = f"/Game/Maps/{TASK_ID}/Support/DA_EpochRecord_Old"
NEW_RECORD = f"/Game/Maps/{TASK_ID}/Support/DA_EpochRecord_New"
LIVE_SOURCE = PROJECT_ROOT / "Source" / "ThirdPerson" / "Tasks" / TASK_ID
REFERENCE_SOURCE = (TASK / "reference" / "Source" / "ThirdPerson"
                    / "Tasks" / TASK_ID)
RECORD_VECTOR = "PASS records=2 old=OldQuartz:31 new=NewViolet:74 exact=1"
OLD_MAP_VECTOR = (
    "PASS map_exact=1 stage=old display=1 fixture=1 player_start=1 "
    "record_soft=1 facts_exact=1 game_mode_exact=1 playable=1 "
    "runtime_observed=0")
NEW_MAP_VECTOR = OLD_MAP_VECTOR.replace("stage=old", "stage=new")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def is_reparse(path: Path) -> bool:
    info = path.lstat()
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def require_regular(path: Path) -> None:
    if not path.is_file() or is_reparse(path):
        raise RuntimeError("missing/nonregular/reparse: %s" % path)
    current = path.parent
    root = REPO.resolve()
    while True:
        if is_reparse(current):
            raise RuntimeError("reparse ancestor: %s" % current)
        if current.resolve() == root:
            return
        if current.parent == current:
            raise RuntimeError("escaped repository ancestry: %s" % path)
        current = current.parent


def vector(paths: list[Path]) -> dict[str, dict[str, object]]:
    result = {}
    for path in paths:
        require_regular(path)
        result[path.relative_to(REPO).as_posix()] = {
            "size": path.stat().st_size, "sha256": sha256(path)}
    return result


def record_vector() -> dict[str, dict[str, object]]:
    return vector([OLD_ASSET, NEW_ASSET])


def map_vector() -> dict[str, dict[str, object]]:
    return vector([OLD_MAP, NEW_MAP])


def source_vector() -> dict[str, dict[str, object]]:
    names = [
        "EpochAssetWorldSubsystem.cpp", "EpochAssetWorldSubsystem.h",
        "EpochTravelProtectedTypes.cpp", "EpochTravelProtectedTypes.h",
    ]
    files = sorted(path.name for path in LIVE_SOURCE.iterdir()
                   if path.is_file()) if LIVE_SOURCE.is_dir() else []
    if files != names:
        raise RuntimeError("live source inventory mismatch: %r" % files)
    return vector([LIVE_SOURCE / name for name in names])


def reference_vector() -> dict[str, dict[str, object]]:
    names = ["EpochAssetWorldSubsystem.cpp", "EpochAssetWorldSubsystem.h"]
    files = sorted(path.name for path in REFERENCE_SOURCE.iterdir()
                   if path.is_file()) if REFERENCE_SOURCE.is_dir() else []
    if files != names:
        raise RuntimeError("reference inventory mismatch: %r" % files)
    return vector([REFERENCE_SOURCE / name for name in names])


def assert_absent(*paths: Path) -> None:
    present = [str(path) for path in paths if os.path.lexists(path)]
    if present:
        raise RuntimeError("paths must be absent: %r" % present)
