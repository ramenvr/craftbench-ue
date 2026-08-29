"""Task-local filesystem contracts shared by guard authoring runners."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat


TASK_ID = "t3-the-guard-resumes-patrol-after-the-chase"
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PROJECT = REPO / "UE-projects" / "ThirdPerson" / "ThirdPerson.uproject"
CONTENT = PROJECT.parent / "Content"
ADMISSION_DIR = CONTENT / "__CraftBenchAdmission" / TASK_ID
ADMISSION_MAP_DIR = CONTENT / "Maps" / TASK_ID
ADMISSION_MAP = ADMISSION_MAP_DIR / "L_GuardPatrolChaseAdmission.umap"
FINAL_DIR = CONTENT / "Tasks" / TASK_ID
FINAL_MAP = ADMISSION_MAP_DIR / "L_GuardPatrolChase.umap"
REFERENCE = HERE.parent / "reference"
STOCK = (
    CONTENT / "ThirdPerson" / "Lvl_ThirdPerson.umap",
    CONTENT / "ThirdPerson" / "Blueprints" / "BP_ThirdPersonCharacter.uasset",
    CONTENT / "ThirdPerson" / "Blueprints" / "BP_ThirdPersonGameMode.uasset",
    CONTENT / "ThirdPerson" / "Blueprints"
    / "BP_ThirdPersonPlayerController.uasset",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_reparse(path: Path) -> bool:
    info = path.lstat()
    attributes = getattr(info, "st_file_attributes", 0)
    return path.is_symlink() or bool(
        attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def require_plain(path: Path, stop: Path = REPO) -> None:
    current = Path(os.path.abspath(os.fspath(path)))
    boundary = Path(os.path.abspath(os.fspath(stop)))
    while True:
        if not current.exists():
            raise RuntimeError("required path missing: %s" % current)
        if is_reparse(current):
            raise RuntimeError("reparse path rejected: %s" % current)
        if current == boundary:
            return
        if boundary not in current.parents:
            raise RuntimeError("path escaped boundary: %s" % path)
        current = current.parent


def regular_files(root: Path) -> list[Path]:
    require_plain(root)
    result: list[Path] = []
    for current_text, directories, filenames in os.walk(root):
        current = Path(current_text)
        for directory in directories:
            require_plain(current / directory)
        for filename in filenames:
            child = current / filename
            require_plain(child)
            if not child.is_file():
                raise RuntimeError("non-regular inventory child: %s" % child)
            result.append(child)
    return sorted(result, key=lambda item: item.as_posix().lower())


def vector(paths: list[Path] | tuple[Path, ...]) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in paths:
        require_plain(path)
        result[path.relative_to(REPO).as_posix()] = sha256(path)
    return result


def stock_vector() -> dict[str, str]:
    return vector(STOCK)


def require_protected_absent(*, admission_map: bool = True) -> None:
    for path in (FINAL_DIR, FINAL_MAP, REFERENCE):
        if os.path.lexists(path):
            raise RuntimeError("protected output must remain absent: %s" % path)
    if admission_map and os.path.lexists(ADMISSION_MAP):
        raise RuntimeError("admission map must remain absent: %s" % ADMISSION_MAP)


def admission_assets() -> tuple[Path, Path]:
    return (
        ADMISSION_DIR / "BB_GuardPatrolChase_Admission.uasset",
        ADMISSION_DIR / "BT_GuardPatrolChase_Admission.uasset",
    )


def exact_admission_asset_vector() -> dict[str, str]:
    files = regular_files(ADMISSION_DIR)
    expected = set(admission_assets())
    if set(files) != expected:
        raise RuntimeError("admission inventory mismatch: %s" %
                           [item.name for item in files])
    return vector(tuple(files))


def final_assets() -> tuple[Path, Path]:
    return (
        FINAL_DIR / "BB_GuardPatrolChase.uasset",
        FINAL_DIR / "BT_GuardPatrolChase.uasset",
    )


def exact_final_asset_vector() -> dict[str, str]:
    files = regular_files(FINAL_DIR)
    expected = set(final_assets())
    if set(files) != expected:
        raise RuntimeError("final asset inventory mismatch: %s" %
                           [item.name for item in files])
    return vector(tuple(files))
