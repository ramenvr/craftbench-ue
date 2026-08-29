"""Exact paths and hash locks for the two-process SaveGame task."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat


TASK_ID = "t3-the-run-resumes-at-the-latest-marker-without-paying-twice"
HERE = Path(__file__).resolve().parent
TASK = HERE.parent
REPO = HERE.parents[3]
PROJECT_ROOT = REPO / "UE-projects" / "ThirdPerson"
PROJECT = PROJECT_ROOT / "ThirdPerson.uproject"
CONTENT = PROJECT_ROOT / "Content"
MAP_ROOT = CONTENT / "Maps" / TASK_ID
MAP_FILE = MAP_ROOT / "L_LatestMarkerResume.umap"
MAP_PACKAGE = f"/Game/Maps/{TASK_ID}/L_LatestMarkerResume"
LIVE_SOURCE = PROJECT_ROOT / "Source" / "ThirdPerson" / "Tasks" / TASK_ID
REFERENCE_SOURCE = TASK / "reference" / "Source" / "ThirdPerson" / "Tasks" / TASK_ID
REFERENCE = TASK / "reference"
MAP_VECTOR = (
    "PASS map_exact=1 subject=1 checkpoints=2 rewards=3 write_fixture=1 "
    "resume_fixture=1 player_start=1 facts_exact=1 "
    "persistence_component=1 game_mode_exact=1 playable=1 runtime_observed=0"
)


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
        raise RuntimeError("missing/non-regular/reparse file: %s" % path)
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


def require_exact_source(root: Path, names: list[str]) \
        -> dict[str, dict[str, object]]:
    expected = [root / name for name in names]
    files = sorted(path for path in root.iterdir() if path.is_file()) if \
        root.is_dir() else []
    if files != sorted(expected):
        raise RuntimeError("source inventory mismatch: %r" % files)
    return vector(expected)


def source_vector() -> dict[str, dict[str, object]]:
    return require_exact_source(LIVE_SOURCE, [
        "RunResumePersistenceComponent.cpp",
        "RunResumePersistenceComponent.h",
        "RunResumeProtectedTypes.cpp",
        "RunResumeProtectedTypes.h",
    ])


def reference_vector() -> dict[str, dict[str, object]]:
    return require_exact_source(REFERENCE_SOURCE, [
        "RunResumePersistenceComponent.cpp",
        "RunResumePersistenceComponent.h",
    ])


def map_vector() -> dict[str, dict[str, object]]:
    return vector([MAP_FILE])


def assert_absent(*paths: Path) -> None:
    present = [str(path) for path in paths if os.path.lexists(path)]
    if present:
        raise RuntimeError("protected paths must be absent: %r" % present)
