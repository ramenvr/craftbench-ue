"""Fresh-process readback of the exact PCG admission map."""

from __future__ import annotations

from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pcg_task_common import (  # noqa: E402
    ADMISSION_MAP, ADMISSION_MAP_VECTOR, FINAL_GRAPH_ROOT, FINAL_MAP_FILE,
    REFERENCE, admission_graph_vector, admission_map_vector, assert_absent,
    immutable_vector,
)


def fail(message: str) -> None:
    unreal.log_error("FILTERED-POINT-ADMISSION-MAP-READBACK-FAILED: " + message)
    raise RuntimeError(message)


def main() -> None:
    assert_absent(FINAL_GRAPH_ROOT, FINAL_MAP_FILE, REFERENCE)
    before = {"graph": admission_graph_vector(),
              "map": admission_map_vector(),
              "immutable": immutable_vector()}
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.load_level(ADMISSION_MAP):
        fail("cold load_level failed")
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    helper = getattr(unreal, "FilteredPointInstancesAssetAuthoring", None)
    if world is None or helper is None:
        fail("cold world/helper unavailable")
    detail = helper.inspect_map(world, True)
    if type(detail) is not str or detail != ADMISSION_MAP_VECTOR:
        fail("cold map contract mismatch: %r" % detail)
    after = {"graph": admission_graph_vector(),
             "map": admission_map_vector(),
             "immutable": immutable_vector()}
    if after != before:
        fail("cold map readback changed protected hashes")
    marker = (
        "FILTERED-POINT-ADMISSION-MAP-READBACK-PASS map=1 host=1 "
        "fixture_a=1 fixture_b=1 player_start=1 floor=1 graph_exact=1 "
        "hashes_unchanged=1 runtime_observed=0"
    )
    unreal.log(marker)
    print(marker, flush=True)


main()
