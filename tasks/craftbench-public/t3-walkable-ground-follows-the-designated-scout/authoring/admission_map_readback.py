"""Fresh-process, read-only identity check for the admission map."""

from __future__ import annotations

import hashlib
from pathlib import Path

import unreal


TASK_ID = "t3-walkable-ground-follows-the-designated-scout"
MAP_NAME = "L_WalkableGroundAdmission"
MAP_PACKAGE = f"/Game/Maps/{TASK_ID}/{MAP_NAME}"
REPO = Path(__file__).resolve().parents[4]
PROJECT_ROOT = REPO / "UE-projects" / "ThirdPerson"
CONTENT = PROJECT_ROOT / "Content"
MAP_FILE = CONTENT / "Maps" / TASK_ID / f"{MAP_NAME}.umap"
FINAL_MAP = CONTENT / "Maps" / TASK_ID / "L_WalkableGround.umap"
TASK_CONTENT = CONTENT / "Tasks" / TASK_ID
REFERENCE = Path(__file__).resolve().parents[1] / "reference"
PROTECTED_FILES = (
    MAP_FILE,
    PROJECT_ROOT / "ThirdPerson.uproject",
    PROJECT_ROOT / "Source" / "ThirdPerson" / "ThirdPerson.Build.cs",
    PROJECT_ROOT / "Source" / "CraftBenchTests" / "CraftBenchTests.Build.cs",
)


def fail(message: str) -> None:
    unreal.log_error("WALKABLE-GROUND-ADMISSION-MAP-READBACK-FAILED: " + message)
    raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def hashes() -> dict[str, str]:
    missing = [str(path) for path in PROTECTED_FILES
               if not path.is_file() or path.is_symlink()]
    if missing:
        fail("protected input missing/non-regular: %r" % missing)
    return {str(path.relative_to(REPO)).replace("\\", "/"): sha256(path)
            for path in PROTECTED_FILES}


def main() -> None:
    if FINAL_MAP.exists() or TASK_CONTENT.exists() or REFERENCE.exists():
        fail("production final/task/reference boundary is not absent")
    before = hashes()
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.load_level(MAP_PACKAGE):
        fail("fresh map load failed")
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    helper = getattr(unreal, "WalkableGroundAdmissionAuthoring", None)
    inspect = getattr(helper, "inspect_admission_world", None) if helper else None
    detail = inspect(world) if inspect and world else None
    if type(detail) is not str or not detail.startswith(
            "PASS scout=1 fixture=1 bounds=1 bounds_span_all=1 ") \
            or "invoker_exact=1" not in detail \
            or "loaded_nav_data=0" not in detail:
        fail("native cold readback vector mismatch: %r" % detail)
    after = hashes()
    if after != before:
        fail("read-only cold load changed protected bytes")
    unreal.log(
        "WALKABLE-GROUND-ADMISSION-MAP-READBACK-PASS map=%s sha256=%s %s "
        "protected_hashes=%d" %
        (MAP_PACKAGE, after[str(MAP_FILE.relative_to(REPO)).replace('\\', '/')],
         detail, len(after)))


main()
