"""Fresh-process, read-only validation of the retained production map."""

from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from worker_plan_final_common import (  # noqa: E402
    ADMISSION_MAP, FINAL_MAP, FINAL_TREE, final_vector, immutable_vector,
    sha256, vector,
)

TASK_ID = "t3-the-worker-keeps-its-new-plan-after-the-signal"
MAP = "/Game/Maps/" + TASK_ID + "/L_WorkerPlan"
MAP_DIRECTORY = "/Game/Maps/" + TASK_ID
GAME_MODE = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode"
TREE_OBJECT = FINAL_TREE + ".ST_WorkerPlan"
SCHEMA_OBJECT = TREE_OBJECT + ":StateTreeEditorData_0.StateTreeAIComponentSchema_0"
SHELL_SUCCESS = (
    "PASS baseline_empty=1 ownership=1 signal_transition=0 navigation_task=0 "
    "tree=" + TREE_OBJECT + " schema=" + SCHEMA_OBJECT)


def fail(message):
    unreal.log_error("WORKER-PLAN-FINAL-MAP-READBACK-FAILED: " + message)
    raise RuntimeError(message)


def snapshot():
    return {"final_asset": final_vector(), "immutable": immutable_vector(),
            "final_map": vector((FINAL_MAP,))}


def main():
    if not ADMISSION_MAP.is_file() or not FINAL_MAP.is_file():
        fail("exact admission/final maps missing")
    before = snapshot()
    observed_maps = {str(value).split(".", 1)[0] for value in
                     unreal.EditorAssetLibrary.list_assets(
                         MAP_DIRECTORY, recursive=True, include_folder=False)}
    if observed_maps != {
            "/Game/Maps/" + TASK_ID + "/L_WorkerPlanAdmission", MAP}:
        fail("map inventory mismatch: %r" % sorted(observed_maps))
    tree = unreal.EditorAssetLibrary.load_asset(FINAL_TREE)
    helper = getattr(unreal, "WorkerPlanAssetAuthoring", None)
    game_mode = unreal.EditorAssetLibrary.load_blueprint_class(GAME_MODE)
    if tree is None or helper is None or game_mode is None:
        fail("tree/helper/game mode unavailable")
    shell_detail = helper.inspect_state_tree_shell(tree)
    if type(shell_detail) is not str or shell_detail != SHELL_SUCCESS:
        fail("baseline StateTree contract mismatch: %r" % shell_detail)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.load_level(MAP):
        fail("load_level failed")
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = list(actor_subsystem.get_all_level_actors())
    fixtures = [a for a in actors
                if a.get_class() == unreal.WorkerPlanFunctionalTest.static_class()]
    exact = {
        "fixture": len(fixtures),
        "worker": sum(a.get_class() == unreal.WorkerPlanCharacter.static_class()
                      and a.actor_has_tag("WorkerPlanSubject") for a in actors),
        "signal": sum(a.get_class() == unreal.WorkerPlanSignalActor.static_class()
                      and a.actor_has_tag("WorkerPlanSignal") for a in actors),
        "destination": sum(a.get_class() == unreal.TargetPoint.static_class()
                           and a.actor_has_tag("WorkerPlanDestination")
                           for a in actors),
        "nav_bounds": sum(a.get_class() == unreal.NavMeshBoundsVolume.static_class()
                          for a in actors),
        "recast": sum(a.get_class() == unreal.RecastNavMesh.static_class()
                      for a in actors),
        "player_start": sum(a.get_class() == unreal.PlayerStart.static_class()
                            for a in actors),
    }
    if any(value != 1 for value in exact.values()):
        fail("exact staged cardinality mismatch: %r" % exact)
    if fixtures[0].get_editor_property("expected_state_tree") != tree:
        fail("fixture StateTree identity mismatch")
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None or world.get_world_settings().get_editor_property(
            "default_game_mode") != game_mode:
        fail("stock playable game mode mismatch")
    after = snapshot()
    if after != before:
        fail("readback changed protected artifacts")
    marker = (
        "WORKER-PLAN-FINAL-MAP-READBACK-PASS map=%s sha256=%s actors=%d "
        "fixture=1 worker=1 signal=1 destination=1 nav_bounds=1 recast=1 "
        "player_start=1 playable_game_mode=1 baseline_empty=1 "
        "hashes_unchanged=1" % (MAP, sha256(FINAL_MAP), len(actors)))
    unreal.log(marker)
    print(marker, flush=True)


main()
