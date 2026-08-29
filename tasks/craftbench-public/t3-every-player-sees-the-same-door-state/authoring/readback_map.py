"""Fresh-process, read-only Door map contract proof."""

import os
from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from door_common import (  # noqa: E402
    ADMISSION_ASSET, ADMISSION_MAP, ADMISSION_MAP_PACKAGE,
    ADMISSION_MAP_VECTOR, FINAL_ASSET, FINAL_MAP, FINAL_MAP_PACKAGE,
    FINAL_MAP_VECTOR, REFERENCE_ASSET, optional_vector,
)


def fail(message: str) -> None:
    unreal.log_error("REPLICATED-DOOR-MAP-READBACK-ERROR: " + message)
    raise RuntimeError(message)


def main() -> None:
    mode = os.environ.get("CRAFTBENCH_DOOR_MAP_MODE", "")
    if mode not in ("final", "admission"):
        fail("mode must be final or admission")
    admission = mode == "admission"
    package = ADMISSION_MAP_PACKAGE if admission else FINAL_MAP_PACKAGE
    target = ADMISSION_MAP if admission else FINAL_MAP
    expected = ADMISSION_MAP_VECTOR if admission else FINAL_MAP_VECTOR
    before = optional_vector((FINAL_ASSET, ADMISSION_ASSET, FINAL_MAP,
                              ADMISSION_MAP, REFERENCE_ASSET))
    if before[str(target)] is None:
        fail("target map missing")
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.load_level(package):
        fail("cold level load failed")
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    helper = getattr(unreal, "ReplicatedDoorAssetAuthoring", None)
    detail = helper.inspect_door_map(world, admission) if helper and world else None
    if type(detail) is not str or detail != expected:
        fail("cold map vector mismatch: %r" % detail)
    after = optional_vector((FINAL_ASSET, ADMISSION_ASSET, FINAL_MAP,
                             ADMISSION_MAP, REFERENCE_ASSET))
    if after != before:
        fail("cold map readback changed hashes")
    marker = "REPLICATED-DOOR-MAP-READBACK-PASS mode=%s map_files=1 " \
        "doors=1 fixtures=1 player_starts=1 playable=1 hashes_unchanged=1 " \
        "runtime_observed=0" % mode
    unreal.log(marker)
    print(marker, flush=True)


main()
