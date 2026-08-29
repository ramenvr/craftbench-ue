"""Shared fail-closed paths and byte snapshots for production authoring."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TASK_ID = "t3-each-local-player-owns-its-top-modal"
PROJECT_ROOT = REPO / "UE-projects" / "ThirdPerson"
PROJECT = PROJECT_ROOT / "ThirdPerson.uproject"
CONTENT = PROJECT_ROOT / "Content"
TASK_ROOT = CONTENT / "Tasks" / TASK_ID
MAP_ROOT = CONTENT / "Maps" / TASK_ID
FINAL_MAP = MAP_ROOT / "L_LocalPlayerModalIsolation.umap"
ADMISSION_MAP = MAP_ROOT / "L_LocalPlayerModalIsolationAdmission.umap"
REFERENCE_ROOT = HERE.parent / "reference"
ASSET_NAMES = (
    "WBP_LocalPlayerModalRoot.uasset",
    "WBP_LocalPlayerModalScreen.uasset",
)
ASSET_FILES = tuple(TASK_ROOT / name for name in ASSET_NAMES)


class ContractError(RuntimeError):
    """A protected authoring invariant failed."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def is_reparse(path: Path) -> bool:
    info = path.lstat()
    return bool(getattr(info, "st_file_attributes", 0) &
                getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def require_plain(path: Path) -> None:
    current = Path(os.path.abspath(path))
    while True:
        if not current.exists():
            raise ContractError("required path missing: %s" % current)
        if current.is_symlink() or is_reparse(current):
            raise ContractError("link/reparse rejected: %s" % current)
        if current == REPO:
            return
        if REPO not in current.parents:
            raise ContractError("path escaped repo: %s" % path)
        current = current.parent


def exact_assets() -> tuple[Path, ...]:
    if not TASK_ROOT.is_dir() or TASK_ROOT.is_symlink():
        raise ContractError("task asset root missing/non-plain")
    files = tuple(sorted(path for path in TASK_ROOT.rglob("*") if path.is_file()))
    if files != tuple(sorted(ASSET_FILES)):
        raise ContractError("exact asset inventory mismatch: %r" %
                            [path.name for path in files])
    for path in files:
        require_plain(path)
    return files


def vector(paths: tuple[Path, ...]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for path in paths:
        require_plain(path)
        if not path.is_file():
            raise ContractError("protected file missing: %s" % path)
        result[path.relative_to(REPO).as_posix()] = {
            "size": path.stat().st_size,
            "sha256": sha256(path),
        }
    return result


def asset_vector() -> dict[str, dict[str, object]]:
    return vector(exact_assets())


def require_reference_absent() -> None:
    if os.path.lexists(REFERENCE_ROOT):
        raise ContractError("reference must be absent: %s" % REFERENCE_ROOT)
