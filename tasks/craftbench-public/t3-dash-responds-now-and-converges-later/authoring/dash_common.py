"""Immutable paths and file locks for predicted-dash authoring."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
TASK = HERE.parent
REPO = HERE.parents[3]
PROJECT = REPO / "UE-projects" / "ThirdPerson"
CONTENT = PROJECT / "Content"
TASK_ID = "t3-dash-responds-now-and-converges-later"
MAP_PACKAGE = f"/Game/Maps/{TASK_ID}/L_PredictedDash"
MAP_DIR = CONTENT / "Maps" / TASK_ID
MAP_FILE = MAP_DIR / "L_PredictedDash.umap"
REFERENCE = TASK / "reference"
LIVE_SOURCE = (
    PROJECT / "Source" / "ThirdPerson" / "Tasks" / TASK_ID
)
ACCEPTED_NAMES = (
    "PredictedDashMovementComponent.h",
    "PredictedDashMovementComponent.cpp",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def is_reparse(path: Path) -> bool:
    try:
        return bool(path.lstat().st_file_attributes & 0x400)
    except AttributeError:
        return path.is_symlink()


def files_under(directory: Path) -> tuple[Path, ...]:
    if not directory.exists():
        return ()
    if not directory.is_dir() or directory.is_symlink() or is_reparse(directory):
        raise RuntimeError("nonregular directory: %s" % directory)
    return tuple(sorted(path for path in directory.rglob("*") if path.is_file()))


def vector(paths: tuple[Path, ...]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for path in paths:
        if not path.is_file() or path.is_symlink() or is_reparse(path):
            raise RuntimeError("missing/nonregular input: %s" % path)
        result[str(path)] = {"size": path.stat().st_size,
                             "sha256": sha256(path)}
    return result


def optional_vector(paths: tuple[Path, ...]) -> dict[str, object]:
    result: dict[str, object] = {}
    for path in paths:
        if os.path.lexists(path):
            result[str(path)] = vector((path,))[str(path)]
        else:
            result[str(path)] = None
    return result


def source_vector(project: Path) -> dict[str, dict[str, object]]:
    root = project.resolve().parent / "Source" / "ThirdPerson" / "Tasks" / TASK_ID
    return vector(tuple(root / name for name in ACCEPTED_NAMES))


def project_inputs(project: Path) -> tuple[Path, ...]:
    root = project.resolve().parent
    map_dir = root / "Content" / "Maps" / TASK_ID
    source = root / "Source" / "ThirdPerson" / "Tasks" / TASK_ID
    return tuple(sorted(files_under(map_dir))) + tuple(
        source / name for name in ACCEPTED_NAMES)
