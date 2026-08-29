"""Unreal-free byte contract for district-streaming reference closure."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
from typing import Any


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TASK_ID = "t3-only-the-requested-district-enters-and-leaves-the-world"
PROJECT_ROOT = REPO / "UE-projects" / "ThirdPerson"
CONTENT = PROJECT_ROOT / "Content"
TASK_DIR = CONTENT / "Tasks" / TASK_ID
LOADER_FILE = TASK_DIR / "BP_DistrictStreamLoader.uasset"
MAP_ROOT = CONTENT / "Maps" / TASK_ID
SUPPORT_ROOT = MAP_ROOT / "Support"
ALPHA_FILE = SUPPORT_ROOT / "L_DistrictAlpha.umap"
BETA_FILE = SUPPORT_ROOT / "L_DistrictBeta.umap"
FINAL_MAP = MAP_ROOT / "L_DistrictStreaming.umap"
ADMISSION_ROOT = CONTENT / "__CraftBenchAdmission" / TASK_ID
ADMISSION_FILE = ADMISSION_ROOT / "L_DistrictStreamingAdmission.umap"
REFERENCE_ROOT = HERE.parent / "reference"
REFERENCE_FILE = (
    REFERENCE_ROOT / "Content" / "Tasks" / TASK_ID /
    "BP_DistrictStreamLoader.uasset")

BASELINE_SHA256 = (
    "BAE83D5C585EF6F7E916CCE540214F51D9D692574EB9BD41B2D89E325AEB9A9B")
EXPECTED_IMMUTABLE = {
    ALPHA_FILE:
        "487D05B80BC8628CE248198A7140420D129280AFE30A1207F8F6BC713240ED7F",
    BETA_FILE:
        "273C35AA564B14559942A56F7A5B9272606018149CD83D6C06C95A25DFE9C7E8",
    ADMISSION_FILE:
        "F8BE965DCC1972BC23D59F3A5C43F9E3E059FE6118187EA5738E484B7C60E065",
}


class ContractError(RuntimeError):
    """A protected path, inventory, or hash differed from the contract."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def is_reparse(path: Path) -> bool:
    info = path.lstat()
    attributes = getattr(info, "st_file_attributes", 0)
    return stat.S_ISLNK(info.st_mode) or bool(
        attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def require_plain_chain(path: Path, anchor: Path, *, must_exist: bool = True) -> None:
    path = Path(os.path.abspath(os.fspath(path)))
    anchor = Path(os.path.abspath(os.fspath(anchor)))
    try:
        common = os.path.commonpath((path, anchor))
    except (OSError, ValueError) as exc:
        raise ContractError("path has no common anchor: %s" % path) from exc
    if os.path.normcase(common) != os.path.normcase(str(anchor)):
        raise ContractError("path escapes anchor: %s" % path)
    if not anchor.exists() or is_reparse(anchor):
        raise ContractError("anchor missing or reparse: %s" % anchor)
    current = anchor
    for part in Path(os.path.relpath(path, anchor)).parts:
        current /= part
        if not current.exists():
            if must_exist:
                raise ContractError("required path missing: %s" % current)
            return
        if is_reparse(current):
            raise ContractError("link/reparse refused: %s" % current)


def files_under(root: Path) -> list[Path]:
    require_plain_chain(root, CONTENT)
    found: list[Path] = []
    for directory, names, filenames in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        for name in names:
            require_plain_chain(directory_path / name, CONTENT)
        for name in filenames:
            candidate = directory_path / name
            require_plain_chain(candidate, CONTENT)
            found.append(candidate)
    return sorted(found, key=lambda item: item.as_posix().lower())


def facts(path: Path) -> dict[str, Any]:
    require_plain_chain(path, CONTENT)
    return {"size": path.stat().st_size, "sha256": sha256(path)}


def require_reference_absent() -> None:
    require_plain_chain(REFERENCE_ROOT, REPO, must_exist=False)
    if os.path.lexists(REFERENCE_ROOT):
        raise ContractError("reference output already exists: %s" % REFERENCE_ROOT)


def require_reference_exact(expected_hash: str) -> dict[str, Any]:
    require_plain_chain(REFERENCE_ROOT, REPO)
    found: list[Path] = []
    for directory, names, filenames in os.walk(REFERENCE_ROOT, followlinks=False):
        directory_path = Path(directory)
        for name in names:
            require_plain_chain(directory_path / name, REPO)
        for name in filenames:
            candidate = directory_path / name
            require_plain_chain(candidate, REPO)
            found.append(candidate)
    if found != [REFERENCE_FILE]:
        raise ContractError("reference inventory is not exact one loader: %r" % found)
    value = {"size": REFERENCE_FILE.stat().st_size,
             "sha256": sha256(REFERENCE_FILE)}
    if value["sha256"] != expected_hash:
        raise ContractError("reference hash mismatch: %s" % value["sha256"])
    return value


def snapshot(*, expected_loader_hash: str | None,
             require_absent_reference: bool = True) -> dict[str, Any]:
    if require_absent_reference:
        require_reference_absent()
    if os.path.lexists(FINAL_MAP):
        raise ContractError("protected final map must remain absent: %s" % FINAL_MAP)

    if files_under(TASK_DIR) != [LOADER_FILE]:
        raise ContractError("task inventory is not exact one loader asset")
    loader = facts(LOADER_FILE)
    if expected_loader_hash is not None and \
            loader["sha256"] != expected_loader_hash:
        raise ContractError(
            "loader hash mismatch actual=%s expected=%s" %
            (loader["sha256"], expected_loader_hash))

    direct_files = sorted(
        item.name for item in MAP_ROOT.iterdir() if item.is_file())
    direct_dirs = sorted(
        item.name for item in MAP_ROOT.iterdir() if item.is_dir())
    if direct_files or direct_dirs != ["Support"]:
        raise ContractError(
            "map root inventory mismatch files=%r dirs=%r" %
            (direct_files, direct_dirs))
    if files_under(SUPPORT_ROOT) != [ALPHA_FILE, BETA_FILE]:
        raise ContractError("support inventory is not exact Alpha/Beta")
    if files_under(ADMISSION_ROOT) != [ADMISSION_FILE]:
        raise ContractError("admission inventory is not exact host map")

    immutable: dict[str, dict[str, Any]] = {}
    for path, expected in EXPECTED_IMMUTABLE.items():
        value = facts(path)
        if value["sha256"] != expected:
            raise ContractError("protected hash mismatch: %s" % path)
        immutable[path.relative_to(PROJECT_ROOT).as_posix()] = value
    return {
        "loader": loader,
        "immutable": immutable,
        "final_absent": True,
        "reference_absent": require_absent_reference,
        "no_reparse": True,
    }


def immutable_vector(value: dict[str, Any]) -> dict[str, Any]:
    """Drop the sole intentionally edited loader package."""
    return {
        "immutable": value["immutable"],
        "final_absent": value["final_absent"],
        "no_reparse": value["no_reparse"],
    }
