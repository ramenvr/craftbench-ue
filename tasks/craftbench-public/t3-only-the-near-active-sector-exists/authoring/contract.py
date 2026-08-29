"""Shared fail-closed paths and hashing for Near Active Sector authoring."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


TASK_ID = "t3-only-the-near-active-sector-exists"
REPO = Path(__file__).resolve().parents[4]
PROJECT = REPO / "UE-projects" / "ThirdPerson"
CONTENT = PROJECT / "Content"
ADMISSION_ROOT = CONTENT / "__CraftBenchAdmission" / TASK_ID
MAP_NAME = "L_NearActiveSectorAdmission"
MAP_PACKAGE = "/Game/__CraftBenchAdmission/%s/%s" % (TASK_ID, MAP_NAME)
MAP_FILE = ADMISSION_ROOT / (MAP_NAME + ".umap")
HLOD_FILE = ADMISSION_ROOT / (MAP_NAME + "_HLOD0_Instancing.uasset")
EXTERNAL_ACTORS = CONTENT / "__ExternalActors__" / "__CraftBenchAdmission" / TASK_ID
EXTERNAL_OBJECTS = CONTENT / "__ExternalObjects__" / "__CraftBenchAdmission" / TASK_ID
FINAL_ROOT = CONTENT / "Maps" / TASK_ID
FINAL_SUPPORT = FINAL_ROOT / "Support"
FINAL_MAP_NAME = "L_NearActiveSector"
FINAL_MAP_PACKAGE = "/Game/Maps/%s/%s" % (TASK_ID, FINAL_MAP_NAME)
FINAL_MAP = FINAL_ROOT / (FINAL_MAP_NAME + ".umap")
FINAL_HLOD = FINAL_ROOT / (FINAL_MAP_NAME + "_HLOD0_Instancing.uasset")
FINAL_EXTERNAL_ACTORS = CONTENT / "__ExternalActors__" / "Maps" / TASK_ID
FINAL_EXTERNAL_OBJECTS = CONTENT / "__ExternalObjects__" / "Maps" / TASK_ID
TASK_ASSET_ROOT = CONTENT / "Tasks" / TASK_ID
CONTROLLER_FILE = TASK_ASSET_ROOT / "BP_NearActiveSectorController.uasset"
REFERENCE = REPO / "tasks" / "bp" / TASK_ID / "reference"
REFERENCE_FILE = (REFERENCE / "Content" / "Tasks" / TASK_ID /
                  "BP_NearActiveSectorController.uasset")
LAYER_FILES = {
    "DL_SectorA.uasset",
    "DL_SectorB.uasset",
}
EXPECTED_LAYER_HASHES: dict[str, str] = {
    "UE-projects/ThirdPerson/Content/__CraftBenchAdmission/"
    "t3-only-the-near-active-sector-exists/DL_SectorA.uasset":
        "4C16113868A7E8CAEDEF806B323A064984ADFFF69ECC28870E1C5A52F69FB123",
    "UE-projects/ThirdPerson/Content/__CraftBenchAdmission/"
    "t3-only-the-near-active-sector-exists/DL_SectorB.uasset":
        "6A28E85D054E288AEEF61A536A0CA110AC6C8A2B84E495A20D28D86436FA1FB4",
}
EXPECTED_MAP_FILE_COUNT = 157
EXPECTED_MAP_MANIFEST_SHA = (
    "94FD4C0767D7FF966DCBFFCA9D19D45E697ED02609C25A0774484DC2E275E4CE")
FINAL_LAYER_FILES = {
    "DL_SectorA.uasset",
    "DL_SectorB.uasset",
}
# Filled only after the one-shot final asset author succeeds and its files are
# inspected from disk.  The cold readback refuses an empty value.
EXPECTED_FINAL_ASSET_HASHES: dict[str, str] = {
    "UE-projects/ThirdPerson/Content/Maps/"
    "t3-only-the-near-active-sector-exists/Support/DL_SectorA.uasset":
        "1C8BE0EAE5BD1E23371DD345536484220D2F4771C691B8CFB25BA59C1262120B",
    "UE-projects/ThirdPerson/Content/Maps/"
    "t3-only-the-near-active-sector-exists/Support/DL_SectorB.uasset":
        "CAED39CFA47B66518C780224C9162D26EBE51236FE16F5134356821226950664",
    "UE-projects/ThirdPerson/Content/Tasks/"
    "t3-only-the-near-active-sector-exists/BP_NearActiveSectorController.uasset":
        "1A7DBF0FF68815EED23E6CE1B4D3E113A63672AE13879347DE669CFE3152CA47",
}
EXPECTED_FINAL_MAP_FILE_COUNT = 157
EXPECTED_FINAL_MAP_MANIFEST_SHA = (
    "48F28642AAADAA13D6C50B3A02647BA70836B9FC94E1A557CC6DCE49D434A02A")

PROTECTED_FILES = (
    PROJECT / "ThirdPerson.uproject",
    PROJECT / "Config" / "DefaultEngine.ini",
    PROJECT / "Config" / "DefaultGame.ini",
    PROJECT / "Source" / "ThirdPerson" / "Tasks" / TASK_ID /
    "NearActiveSectorRuntime.h",
    PROJECT / "Source" / "ThirdPerson" / "Tasks" / TASK_ID /
    "NearActiveSectorRuntime.cpp",
    PROJECT / "Source" / "CraftBenchTests" / "Tasks" / TASK_ID /
    "NearActiveSectorFunctionalTest.h",
    PROJECT / "Source" / "CraftBenchTests" / "Tasks" / TASK_ID /
    "NearActiveSectorFunctionalTest.cpp",
    PROJECT / "Source" / "CraftBenchTests" / "Tasks" / TASK_ID /
    "NearActiveSectorAssetAuthoring.h",
    PROJECT / "Source" / "CraftBenchTests" / "Tasks" / TASK_ID /
    "NearActiveSectorAssetAuthoring.cpp",
)


def is_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        return bool(path.stat().st_file_attributes & 0x400)
    except (AttributeError, FileNotFoundError):
        return False


def require_plain_chain(path: Path) -> None:
    current = path
    while True:
        if os.path.lexists(current) and is_reparse(current):
            raise RuntimeError("reparse/symlink boundary: %s" % current)
        if current == CONTENT or current.parent == current:
            break
        current = current.parent


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def file_vector(paths) -> dict[str, tuple[int, str]]:
    result: dict[str, tuple[int, str]] = {}
    for path in sorted(paths, key=lambda item: str(item).lower()):
        if not path.is_file() or is_reparse(path):
            raise RuntimeError("missing/non-regular/reparse file: %s" % path)
        require_plain_chain(path)
        key = str(path.relative_to(REPO)).replace("\\", "/")
        result[key] = (path.stat().st_size, sha256(path))
    return result


def protected_vector() -> dict[str, tuple[int, str]]:
    return file_vector(PROTECTED_FILES)


def layer_files(allow_map: bool = False) -> list[Path]:
    if not ADMISSION_ROOT.is_dir() or is_reparse(ADMISSION_ROOT):
        raise RuntimeError("admission asset root missing/reparse")
    all_files = sorted(path for path in ADMISSION_ROOT.iterdir() if path.is_file())
    expected_names = LAYER_FILES | (
        {MAP_FILE.name, HLOD_FILE.name} if allow_map else set())
    if {path.name for path in all_files} != expected_names:
        raise RuntimeError("layer inventory mismatch: %r" %
                           [path.name for path in all_files])
    if any(path.is_dir() for path in ADMISSION_ROOT.iterdir()):
        raise RuntimeError("foreign directory in admission asset root")
    return [path for path in all_files if path.name in LAYER_FILES]


def map_files() -> list[Path]:
    roots = (ADMISSION_ROOT, EXTERNAL_ACTORS, EXTERNAL_OBJECTS)
    files: list[Path] = []
    for root in roots:
        if root.exists():
            if not root.is_dir() or is_reparse(root):
                raise RuntimeError("invalid map output root: %s" % root)
            files.extend(path for path in root.rglob("*") if path.is_file())
    if not MAP_FILE.is_file():
        raise RuntimeError("admission map missing")
    names = {path.name for path in ADMISSION_ROOT.iterdir() if path.is_file()}
    if names != LAYER_FILES | {MAP_FILE.name, HLOD_FILE.name}:
        raise RuntimeError("admission root inventory mismatch: %r" % sorted(names))
    return sorted(files, key=lambda item: str(item).lower())


def admission_vector() -> dict[str, tuple[int, str]]:
    vector = file_vector(map_files())
    if len(vector) != EXPECTED_MAP_FILE_COUNT \
            or manifest_sha(vector) != EXPECTED_MAP_MANIFEST_SHA:
        raise RuntimeError("frozen admission map vector mismatch")
    return vector


def final_asset_files(allow_map: bool = False) -> list[Path]:
    if not FINAL_SUPPORT.is_dir() or is_reparse(FINAL_SUPPORT):
        raise RuntimeError("final support root missing/reparse")
    support = sorted(path for path in FINAL_SUPPORT.iterdir() if path.is_file())
    if {path.name for path in support} != FINAL_LAYER_FILES \
            or any(path.is_dir() for path in FINAL_SUPPORT.iterdir()):
        raise RuntimeError("final support inventory mismatch: %r" %
                           [path.name for path in support])
    if not CONTROLLER_FILE.is_file() or is_reparse(CONTROLLER_FILE):
        raise RuntimeError("final controller missing/reparse")
    if not TASK_ASSET_ROOT.is_dir() \
            or {path.name for path in TASK_ASSET_ROOT.iterdir()} != \
            {CONTROLLER_FILE.name}:
        raise RuntimeError("editable task inventory is not exact one")
    if not allow_map:
        unexpected = [path for path in FINAL_ROOT.iterdir()
                      if path.name != FINAL_SUPPORT.name]
        if unexpected:
            raise RuntimeError("final map namespace is not fresh: %r" % unexpected)
    return support + [CONTROLLER_FILE]


def final_map_files() -> list[Path]:
    roots = (FINAL_ROOT, FINAL_EXTERNAL_ACTORS, FINAL_EXTERNAL_OBJECTS)
    files: list[Path] = []
    for root in roots:
        if root.exists():
            if not root.is_dir() or is_reparse(root):
                raise RuntimeError("invalid final map output root: %s" % root)
            files.extend(path for path in root.rglob("*") if path.is_file())
    if not FINAL_MAP.is_file() or not FINAL_HLOD.is_file():
        raise RuntimeError("final map/HLOD missing")
    names = {path.name for path in FINAL_ROOT.iterdir()}
    if names != {FINAL_SUPPORT.name, FINAL_MAP.name, FINAL_HLOD.name}:
        raise RuntimeError("final map root inventory mismatch: %r" % sorted(names))
    return sorted(files, key=lambda item: str(item).lower())


def require_reference_absent() -> None:
    if os.path.lexists(REFERENCE):
        raise RuntimeError("reference boundary exists: %s" % REFERENCE)


def require_admission_frozen() -> None:
    admission_vector()


def final_map_vector() -> dict[str, tuple[int, str]]:
    vector = file_vector(final_map_files())
    if len(vector) != EXPECTED_FINAL_MAP_FILE_COUNT \
            or manifest_sha(vector) != EXPECTED_FINAL_MAP_MANIFEST_SHA:
        raise RuntimeError("frozen final map vector mismatch")
    return vector


def controller_hash(expected: str | None = None) -> str:
    vector = file_vector((CONTROLLER_FILE,))
    digest = next(iter(vector.values()))[1]
    if expected is not None and digest != expected:
        raise RuntimeError("controller hash mismatch: %s != %s" %
                           (digest, expected))
    return digest


def immutable_snapshot() -> dict[str, dict[str, tuple[int, str]]]:
    return {
        "protected": protected_vector(),
        "admission": admission_vector(),
        "final_map": final_map_vector(),
    }


def require_reference_exact(expected_hash: str) -> dict[str, tuple[int, str]]:
    if not REFERENCE.is_dir() or is_reparse(REFERENCE):
        raise RuntimeError("reference root missing/reparse")
    entries = sorted(path for path in REFERENCE.rglob("*") if path.is_file())
    if entries != [REFERENCE_FILE]:
        raise RuntimeError("reference inventory mismatch: %r" %
                           [str(path.relative_to(REFERENCE)) for path in entries])
    vector = file_vector((REFERENCE_FILE,))
    if next(iter(vector.values()))[1] != expected_hash:
        raise RuntimeError("reference hash mismatch")
    return vector


def manifest_sha(vector: dict[str, tuple[int, str]]) -> str:
    payload = "\n".join("%s|%d|%s" % (key, size, digest)
                        for key, (size, digest) in sorted(vector.items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


def require_production_absent() -> None:
    for path in (FINAL_ROOT, FINAL_MAP, TASK_ASSET_ROOT, REFERENCE):
        if os.path.lexists(path):
            raise RuntimeError("production/reference boundary exists: %s" % path)
