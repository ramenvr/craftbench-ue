"""Fail-closed paths, inventories, and hash locks for the PCG task."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat


TASK_ID = "t3-filtered-points-and-visible-instances-stay-in-lockstep"
HERE = Path(__file__).resolve().parent
TASK_ROOT = HERE.parent
REPO = HERE.parents[3]
PROJECT_ROOT = REPO / "UE-projects" / "ThirdPerson"
CONTENT = PROJECT_ROOT / "Content"
PROJECT = PROJECT_ROOT / "ThirdPerson.uproject"

ADMISSION_ROOT = CONTENT / "__CraftBenchAdmission" / TASK_ID
ADMISSION_GRAPH_FILE = ADMISSION_ROOT / "PCG_FilteredPointInstances_Admission.uasset"
ADMISSION_GRAPH = (
    f"/Game/__CraftBenchAdmission/{TASK_ID}/"
    "PCG_FilteredPointInstances_Admission"
)
MAP_ROOT = CONTENT / "Maps" / TASK_ID
ADMISSION_MAP_FILE = MAP_ROOT / "L_FilteredPointInstancesAdmission.umap"
ADMISSION_MAP = f"/Game/Maps/{TASK_ID}/L_FilteredPointInstancesAdmission"
FINAL_GRAPH_ROOT = CONTENT / "Tasks" / TASK_ID
FINAL_GRAPH_FILE = FINAL_GRAPH_ROOT / "PCG_FilteredPointInstances.uasset"
FINAL_GRAPH = f"/Game/Tasks/{TASK_ID}/PCG_FilteredPointInstances"
FINAL_MAP_FILE = MAP_ROOT / "L_FilteredPointInstances.umap"
FINAL_MAP = f"/Game/Maps/{TASK_ID}/L_FilteredPointInstances"
REFERENCE = TASK_ROOT / "reference"
REFERENCE_GRAPH_ROOT = REFERENCE / "Content" / "Tasks" / TASK_ID
REFERENCE_GRAPH_FILE = REFERENCE_GRAPH_ROOT / FINAL_GRAPH_FILE.name

SOLVED_VECTOR = (
    "PASS graph_exact=1 solved=1 nodes=6 source=1 bounds=1 density=1 "
    "exclusion=1 parameter=MinDensity spawner=1 metadata=Excluded "
    "mesh_attribute=Mesh output_branch=1 shared_branch=1"
)
BASELINE_VECTOR = (
    "PASS baseline_empty=1 graph_exact=1 nodes=1 source=1 "
    "parameter=MinDensity direct_output=1 filters=0 spawner=0"
)
ADMISSION_MAP_VECTOR = (
    "PASS map_exact=1 mode=admission host=1 fixture_a=1 fixture_b=1 "
    "player_start=1 floor=1 graph_exact=1 pcg_on_demand=1 mesh=1 "
    "game_mode_exact=1 runtime_observed=0"
)
FINAL_MAP_VECTOR = ADMISSION_MAP_VECTOR.replace("mode=admission", "mode=final")

IMMUTABLE_FILES = (
    PROJECT,
    PROJECT_ROOT / "Source" / "CraftBenchTests" / "CraftBenchTests.Build.cs",
    PROJECT_ROOT / "Source" / "CraftBenchTests" / "Tasks" / TASK_ID
    / "FilteredPointPCGTypes.h",
    PROJECT_ROOT / "Source" / "CraftBenchTests" / "Tasks" / TASK_ID
    / "FilteredPointPCGTypes.cpp",
    PROJECT_ROOT / "Source" / "CraftBenchTests" / "Tasks" / TASK_ID
    / "FilteredPointInstancesFunctionalTest.h",
    PROJECT_ROOT / "Source" / "CraftBenchTests" / "Tasks" / TASK_ID
    / "FilteredPointInstancesFunctionalTest.cpp",
    PROJECT_ROOT / "Source" / "CraftBenchTests" / "Tasks" / TASK_ID
    / "FilteredPointInstancesAssetAuthoring.h",
    PROJECT_ROOT / "Source" / "CraftBenchTests" / "Tasks" / TASK_ID
    / "FilteredPointInstancesAssetAuthoring.cpp",
    CONTENT / "ThirdPerson" / "Blueprints" / "BP_ThirdPersonGameMode.uasset",
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
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def require_regular(path: Path) -> None:
    if not path.is_file() or is_reparse(path):
        raise RuntimeError(f"missing/non-regular/reparse file: {path}")
    current = path.parent
    repo = REPO.resolve()
    while True:
        if is_reparse(current):
            raise RuntimeError(f"reparse ancestor: {current}")
        if current.resolve() == repo:
            break
        if current.parent == current:
            raise RuntimeError(f"file escaped repository ancestry: {path}")
        current = current.parent


def vector(paths: tuple[Path, ...] | list[Path]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for path in paths:
        require_regular(path)
        key = path.relative_to(REPO).as_posix()
        result[key] = {"size": path.stat().st_size, "sha256": sha256(path)}
    return result


def immutable_vector() -> dict[str, dict[str, object]]:
    return vector(list(IMMUTABLE_FILES))


def exact_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    if not os.path.lexists(root):
        return []
    if not root.is_dir() or is_reparse(root):
        raise RuntimeError(f"namespace is not a regular directory: {root}")
    files = sorted(path for path in root.rglob("*") if path.is_file())
    extras = [path for path in files if path.suffix.lower() not in suffixes]
    if extras:
        raise RuntimeError(f"unexpected files in namespace: {extras}")
    return files


def admission_graph_vector() -> dict[str, dict[str, object]]:
    files = exact_files(ADMISSION_ROOT, (".uasset",))
    if files != [ADMISSION_GRAPH_FILE]:
        raise RuntimeError(f"admission graph inventory mismatch: {files}")
    return vector(files)


def admission_map_vector() -> dict[str, dict[str, object]]:
    require_regular(ADMISSION_MAP_FILE)
    return vector([ADMISSION_MAP_FILE])


def final_graph_vector() -> dict[str, dict[str, object]]:
    files = exact_files(FINAL_GRAPH_ROOT, (".uasset",))
    if files != [FINAL_GRAPH_FILE]:
        raise RuntimeError(f"final graph inventory mismatch: {files}")
    return vector(files)


def final_map_vector() -> dict[str, dict[str, object]]:
    require_regular(FINAL_MAP_FILE)
    return vector([FINAL_MAP_FILE])


def reference_graph_vector() -> dict[str, dict[str, object]]:
    files = exact_files(REFERENCE_GRAPH_ROOT, (".uasset",))
    if files != [REFERENCE_GRAPH_FILE]:
        raise RuntimeError(f"reference graph inventory mismatch: {files}")
    return vector(files)


def assert_absent(*paths: Path) -> None:
    present = [str(path) for path in paths if os.path.lexists(path)]
    if present:
        raise RuntimeError(f"protected paths must be absent: {present}")
