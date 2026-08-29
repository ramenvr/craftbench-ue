"""Fresh-process readback of the retained playable production PCG map."""

from __future__ import annotations

from pathlib import Path
import os
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pcg_task_common import (  # noqa: E402
    FINAL_MAP, FINAL_MAP_VECTOR, REFERENCE, admission_graph_vector,
    admission_map_vector, final_graph_vector, final_map_vector,
    immutable_vector,
)


def fail(message: str) -> None:
    unreal.log_error("FILTERED-POINT-FINAL-MAP-READBACK-FAILED: " + message)
    raise RuntimeError(message)


def main() -> None:
    if os.path.lexists(REFERENCE):
        fail("reference must remain absent")
    before = {
        "admission_graph": admission_graph_vector(),
        "admission_map": admission_map_vector(),
        "baseline": final_graph_vector(),
        "map": final_map_vector(),
        "immutable": immutable_vector(),
    }
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.load_level(FINAL_MAP):
        fail("cold load_level failed")
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    helper = getattr(unreal, "FilteredPointInstancesAssetAuthoring", None)
    if world is None or helper is None:
        fail("cold world/helper unavailable")
    detail = helper.inspect_map(world, False)
    if type(detail) is not str or detail != FINAL_MAP_VECTOR:
        fail("cold map contract mismatch: %r" % detail)
    after = {
        "admission_graph": admission_graph_vector(),
        "admission_map": admission_map_vector(),
        "baseline": final_graph_vector(),
        "map": final_map_vector(),
        "immutable": immutable_vector(),
    }
    if after != before:
        fail("cold map readback changed protected hashes")
    marker = (
        "FILTERED-POINT-FINAL-MAP-READBACK-PASS map=1 host=1 fixture_a=1 "
        "fixture_b=1 player_start=1 floor=1 graph_exact=1 "
        "hashes_unchanged=1 runtime_observed=0"
    )
    unreal.log(marker)
    print(marker, flush=True)


main()
