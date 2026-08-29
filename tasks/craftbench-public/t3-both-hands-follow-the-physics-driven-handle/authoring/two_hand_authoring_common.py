"""Fail-closed filesystem helpers shared by task-local authoring runners."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PROJECT = REPO / "UE-projects" / "ThirdPerson" / "ThirdPerson.uproject"
CONTENT = PROJECT.parent / "Content"
TASK_ID = "t3-both-hands-follow-the-physics-driven-handle"
ADMISSION_DIR = CONTENT / "__CraftBenchAdmission" / TASK_ID
TASK_DIR = CONTENT / "Tasks" / TASK_ID
MAP_DIR = CONTENT / "Maps" / TASK_ID
REFERENCE_DIR = HERE.parent / "reference"
REFERENCE_FILES = {
    REFERENCE_DIR / "Content" / "Tasks" / TASK_ID /
    "CR_TwoHandPhysics.uasset":
        "03709FE0A2E03B85EC09F0128A8964EC35C68612FAFA9ED435FCBEBA75F82B97",
    REFERENCE_DIR / "Content" / "Tasks" / TASK_ID /
    "ABP_TwoHandPhysics.uasset":
        "C4423D78C055232339E3802EC5CAC45995F47A0EC67C0C7A31FF658F14C57BD3",
}
ADMISSION_ASSETS = (
    ADMISSION_DIR / "CR_TwoHandPhysicsAdmission.uasset",
    ADMISSION_DIR / "ABP_TwoHandPhysicsAdmission.uasset",
)
TASK_ASSETS = (
    TASK_DIR / "CR_TwoHandPhysics.uasset",
    TASK_DIR / "ABP_TwoHandPhysics.uasset",
)
ADMISSION_MAP = MAP_DIR / "L_TwoHandPhysicsAdmission.umap"
FINAL_MAP = MAP_DIR / "L_TwoHandPhysics.umap"
STOCK = (
    CONTENT / "Characters" / "Mannequins" / "Meshes" / "SKM_Manny_Simple.uasset",
    CONTENT / "Characters" / "Mannequins" / "Anims" / "Unarmed" / "MM_Idle.uasset",
    CONTENT / "ThirdPerson" / "Blueprints" / "BP_ThirdPersonGameMode.uasset",
    CONTENT / "ThirdPerson" / "Blueprints" / "BP_ThirdPersonCharacter.uasset",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def assert_regular(path: Path) -> None:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("missing/non-regular protected file: %s" % path)
    current = path.parent
    while current != current.parent:
        if (os.path.islink(current) or
                (hasattr(current, "is_junction") and current.is_junction())):
            raise RuntimeError("reparse ancestor rejected: %s" % current)
        if current == REPO:
            break
        current = current.parent


def vector(paths) -> dict[str, str]:
    result = {}
    for path in paths:
        assert_regular(path)
        result[str(path.relative_to(REPO)).replace("\\", "/")] = sha256(path)
    return result


def asset_vector(admission: bool) -> dict[str, str]:
    expected = ADMISSION_ASSETS if admission else TASK_ASSETS
    directory = ADMISSION_DIR if admission else TASK_DIR
    files = tuple(sorted(directory.rglob("*.uasset"))) if directory.is_dir() else ()
    if set(files) != set(expected):
        raise RuntimeError("exact asset inventory mismatch expected=%r actual=%r" %
                           ([str(value) for value in expected],
                            [str(value) for value in files]))
    return vector(expected)


def map_files(map_path: Path) -> tuple[Path, ...]:
    assert_regular(map_path)
    stem = map_path.stem
    mirrors = []
    for root_name in ("__ExternalActors__", "__ExternalObjects__"):
        mirror = CONTENT / root_name / "Maps" / TASK_ID / stem
        if mirror.is_dir():
            mirrors.extend(path for path in mirror.rglob("*") if path.is_file())
    return tuple([map_path] + sorted(mirrors))


def reference_state() -> dict[str, object]:
    """Return an exact, hash-pinned reference state without loading it in UE."""
    if not os.path.lexists(REFERENCE_DIR):
        return {"present": False}
    actual = {path for path in REFERENCE_DIR.rglob("*") if path.is_file()}
    if actual != set(REFERENCE_FILES):
        raise RuntimeError("reference exact inventory mismatch")
    observed = vector(tuple(sorted(actual)))
    expected = {
        str(path.relative_to(REPO)).replace("\\", "/"): digest
        for path, digest in REFERENCE_FILES.items()
    }
    if observed != expected:
        raise RuntimeError("reference exact hashes mismatch")
    return {"present": True, "hashes": observed}


def protected_vector(include_admission_map=False,
                     include_final_map=False) -> dict[str, object]:
    value = {
        "admission_assets": asset_vector(True),
        "task_assets": asset_vector(False),
        "stock": vector(STOCK),
    }
    if include_admission_map:
        value["admission_map"] = vector(map_files(ADMISSION_MAP))
    if include_final_map:
        value["final_map"] = vector(map_files(FINAL_MAP))
    value["reference_absent"] = not os.path.lexists(REFERENCE_DIR)
    if not value["reference_absent"]:
        raise RuntimeError("reference directory must remain absent before closure")
    return value


def require_absent(path: Path) -> None:
    if path.exists() or os.path.lexists(path):
        raise RuntimeError("exact output must be absent: %s" % path)
