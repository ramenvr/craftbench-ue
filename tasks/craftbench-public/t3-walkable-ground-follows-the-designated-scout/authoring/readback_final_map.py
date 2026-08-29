"""Fresh-process read-only validation of the retained production map."""

from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from walkable_ground_final_common import (  # noqa: E402
    FINAL_ASSET, FINAL_MAP, final_vector, immutable_vector, map_vector, sha256,
)

TASK_ID = "t3-walkable-ground-follows-the-designated-scout"
MAP = "/Game/Maps/" + TASK_ID + "/L_WalkableGround"
SHELL_SUCCESS = (
    "PASS baseline_empty=1 class_exact=1 compile_exact=1 component_count=0 "
    "graph_nodes=0 visible=1")


def fail(message):
    unreal.log_error("WALKABLE-GROUND-FINAL-MAP-READBACK-FAILED: " + message)
    raise RuntimeError(message)


def snapshot():
    return {"final": final_vector(), "immutable": immutable_vector(),
            "maps": map_vector()}


def main():
    before = snapshot()
    blueprint = unreal.EditorAssetLibrary.load_asset(FINAL_ASSET)
    helper = getattr(unreal, "WalkableGroundAdmissionAuthoring", None)
    if blueprint is None or helper is None:
        fail("baseline Blueprint/helper unavailable")
    shell = helper.inspect_designated_scout_blueprint_shell(blueprint)
    if type(shell) is not str or shell != SHELL_SUCCESS:
        fail("baseline shell mismatch: %r" % shell)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.load_level(MAP):
        fail("fresh map load failed")
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    detail = helper.inspect_production_world(world) if world else None
    if type(detail) is not str or not detail.startswith(
            "PASS scout=1 fixture=1 bounds=1 floor=1 player_start=1 ") \
            or "baseline_empty=1" not in detail \
            or "invoker_count=0" not in detail:
        fail("native production map contract mismatch: %r" % detail)
    after = snapshot()
    if after != before:
        fail("readback changed protected artifacts")
    marker = ("WALKABLE-GROUND-FINAL-MAP-READBACK-PASS map=%s sha256=%s "
              "scout=1 fixture=1 bounds=1 floor=1 player_start=1 "
              "playable_game_mode=1 baseline_empty=1 serialized_nav_data=0 "
              "hashes_unchanged=1" % (MAP, sha256(FINAL_MAP)))
    unreal.log(marker)
    print(marker, flush=True)


main()
