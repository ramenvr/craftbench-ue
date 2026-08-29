"""Byte-level contract shared by menu reference authoring and closure.

This module is deliberately Unreal-free so the external orchestrator, its
offline tests, and UE Python readbacks all use one exact inventory/hash policy.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
from typing import Any


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TASK_ID = "t2-menu-blocks-gameplay-and-restores-it-exactly"
PROJECT_ROOT = REPO / "UE-projects" / "ThirdPerson"
CONTENT = PROJECT_ROOT / "Content"
TASK_ASSET_DIR = CONTENT / "Tasks" / TASK_ID
MENU_FILE = TASK_ASSET_DIR / "WBP_InputBlockingMenu.uasset"
SUPPORT_DIR = CONTENT / "Maps" / TASK_ID / "Support"
MAP_DIR = CONTENT / "Maps" / TASK_ID
MAIN_MAP = MAP_DIR / "L_MenuInputRouting.umap"
EXTERNAL_ACTORS_DIR = (
    CONTENT / "__ExternalActors__" / "Maps" / TASK_ID / "L_MenuInputRouting")
EXTERNAL_OBJECTS_DIR = (
    CONTENT / "__ExternalObjects__" / "Maps" / TASK_ID / "L_MenuInputRouting")
REFERENCE_ROOT = HERE.parent / "reference"
REFERENCE_FILE = (
    REFERENCE_ROOT / "Content" / "Tasks" / TASK_ID /
    "WBP_InputBlockingMenu.uasset")

BASELINE_SHA256 = (
    "1c61d351779608bb69df3880ac00371dfcb1b68c1c3745a3d852e04b57ee3fd0")
EXPECTED_MAIN_HASH = (
    "c48ddd5b6cf00b32478d07dd9b2d7ce74dba6bf12ac86399f419c98392a37525")
EXPECTED_MAP_MANIFEST = (
    "c494ff1355142fc460c05e947b4f21e626a60f57d3b306456bcdc3e3576df7ed")
EXPECTED_STOCK_MANIFEST = (
    "b197fab3f5d75c48b4e33ae072e3bf10fdfe0b6d4af6cbcb51810e13797f9b81")
EXPECTED_SUPPORT_HASHES = {
    "IA_GameplayProbe.uasset":
        "83013436e91e27fde185d627848f76b1a0da35406c58209feee5185468e089fa",
    "IA_MenuProbe.uasset":
        "99facea7eadf0089d638b92d8af4c38e4dad9ec9b32443b1b141d9da71774b6e",
    "IA_UnrelatedProbe.uasset":
        "92272356f0b3b640adf9fcf0937acd9e4b573577ac1956de527328b11e8eb536",
    "IMC_GameplayQuartz.uasset":
        "be03e71f1fb20151027082a8154f5eec78a70d1c7abd2279dc1f2d02c3d4356c",
    "IMC_GameplayViolet.uasset":
        "4e53228c5d0d37204d804156da4ce387bb505ff70a2d7468797a9c42adae03a6",
    "IMC_MenuQuartz.uasset":
        "540101c7d6b04c388d62c880e6628b117a0ba1c9bd6c8d7aa2d03b33893ffb52",
    "IMC_MenuViolet.uasset":
        "9b0f92087180137fd36051b182567d17cd5976858686aa9bee60c13db966b2a8",
    "IMC_UnrelatedQuartz.uasset":
        "092f8eebd401f569c6d4ef5045c67a20701d1b27215c2c011e16056dc08d5d90",
    "IMC_UnrelatedViolet.uasset":
        "6795b125de661b6041e50677330417100f30d77dc3e8c95126150163ceaac35b",
}
STOCK_FILES = (
    CONTENT / "ThirdPerson" / "Lvl_ThirdPerson.umap",
    CONTENT / "ThirdPerson" / "Blueprints" / "BP_ThirdPersonCharacter.uasset",
    CONTENT / "ThirdPerson" / "Blueprints" / "BP_ThirdPersonGameMode.uasset",
    CONTENT / "ThirdPerson" / "Blueprints" /
    "BP_ThirdPersonPlayerController.uasset",
)


class ContractError(RuntimeError):
    """One exact authoring/protected-package contract was violated."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_reparse(path: Path) -> bool:
    info = path.lstat()
    attributes = getattr(info, "st_file_attributes", 0)
    return stat.S_ISLNK(info.st_mode) or bool(
        attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def require_plain_chain(path: Path, anchor: Path, *, must_exist: bool = True) -> None:
    path = Path(os.path.abspath(path))
    anchor = Path(os.path.abspath(anchor))
    try:
        if os.path.normcase(os.path.commonpath((path, anchor))) != \
                os.path.normcase(str(anchor)):
            raise ValueError("common path differs")
    except (OSError, ValueError) as exc:
        raise ContractError("path escapes anchor: %s" % path) from exc
    current = anchor
    if not current.exists() or is_reparse(current):
        raise ContractError("anchor missing or reparse: %s" % current)
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
    return sorted(found, key=lambda value: value.as_posix().lower())


def manifest(paths: list[Path]) -> tuple[str, dict[str, dict[str, Any]]]:
    digest = hashlib.sha256()
    vector: dict[str, dict[str, Any]] = {}
    for path in sorted(paths, key=lambda value: value.as_posix().lower()):
        require_plain_chain(path, CONTENT)
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        size = path.stat().st_size
        file_hash = sha256(path)
        vector[relative] = {"size": size, "sha256": file_hash}
        digest.update(("%s\0%d\0%s\n" %
                       (relative, size, file_hash)).encode("utf-8"))
    return digest.hexdigest(), vector


def require_reference_absent() -> None:
    require_plain_chain(REFERENCE_ROOT, REPO, must_exist=False)
    if os.path.lexists(REFERENCE_ROOT):
        raise ContractError("reference output already exists: %s" % REFERENCE_ROOT)


def snapshot(*, expected_menu_hash: str | None,
             require_absent_reference: bool = True) -> dict[str, Any]:
    if require_absent_reference:
        require_reference_absent()
    require_plain_chain(TASK_ASSET_DIR, CONTENT)
    task_files = files_under(TASK_ASSET_DIR)
    if task_files != [MENU_FILE]:
        raise ContractError("task inventory is not exact one WBP: %r" % task_files)
    menu_hash = sha256(MENU_FILE)
    if expected_menu_hash is not None and menu_hash != expected_menu_hash:
        raise ContractError(
            "menu hash mismatch actual=%s expected=%s" %
            (menu_hash, expected_menu_hash))

    support_files = files_under(SUPPORT_DIR)
    support_names = {path.name for path in support_files}
    if support_names != set(EXPECTED_SUPPORT_HASHES):
        raise ContractError("support inventory mismatch: %r" % sorted(support_names))
    for path in support_files:
        if sha256(path) != EXPECTED_SUPPORT_HASHES[path.name]:
            raise ContractError("support hash mismatch: %s" % path)

    direct_files = {path.name for path in MAP_DIR.iterdir() if path.is_file()}
    direct_dirs = {path.name for path in MAP_DIR.iterdir() if path.is_dir()}
    if direct_files != {MAIN_MAP.name} or direct_dirs != {"Support"}:
        raise ContractError(
            "map root inventory mismatch files=%r dirs=%r" %
            (sorted(direct_files), sorted(direct_dirs)))
    external_actors = files_under(EXTERNAL_ACTORS_DIR)
    external_objects = files_under(EXTERNAL_OBJECTS_DIR)
    if len(external_actors) != 69 or len(external_objects) != 2:
        raise ContractError(
            "OFPA cardinality mismatch actors=%d objects=%d" %
            (len(external_actors), len(external_objects)))
    map_digest, map_vector = manifest(
        [MAIN_MAP] + external_actors + external_objects)
    support_digest, support_vector = manifest(support_files)
    stock_digest, stock_vector = manifest(list(STOCK_FILES))
    if sha256(MAIN_MAP) != EXPECTED_MAIN_HASH:
        raise ContractError("main map differs from frozen authoring")
    if map_digest != EXPECTED_MAP_MANIFEST:
        raise ContractError("map72 differs from frozen authoring")
    if stock_digest != EXPECTED_STOCK_MANIFEST:
        raise ContractError("stock4 differs from frozen authoring")
    return {
        "menu": {"size": MENU_FILE.stat().st_size, "sha256": menu_hash},
        "support": support_vector,
        "map": map_vector,
        "stock": stock_vector,
        "manifests": {
            "map72": map_digest,
            "support9": support_digest,
            "stock4": stock_digest,
        },
        "no_reparse": True,
        "reference_absent": require_absent_reference,
    }


def immutable_vector(value: dict[str, Any]) -> dict[str, Any]:
    """Drop the only intentionally editable package from a snapshot."""
    return {
        "support": value["support"],
        "map": value["map"],
        "stock": value["stock"],
        "manifests": value["manifests"],
        "no_reparse": value["no_reparse"],
    }
