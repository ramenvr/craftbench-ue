"""Author the retained, playable production worker-plan map once."""

import hashlib
import os
from pathlib import Path
import re
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from worker_plan_final_common import (  # noqa: E402
    ADMISSION_MAP, FINAL_MAP, FINAL_TREE, REFERENCE,
    final_vector, immutable_vector,
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
NAV_SUCCESS = re.compile(
    r"^PASS world=Editor initialized=1 persistent_config=1 "
    r"config=/(?:Script/Engine\.NavigationSystemConfig|"
    r"Script/NavigationSystem\.NavigationSystemModuleConfig) "
    r"config_class_supported=1 "
    r"configured_nav_class=/Script/NavigationSystem\.NavigationSystemV1 "
    r"configured_nav_class_exact=1 "
    r"async_load_lock=1 other_lock=0 asset_compiles=0 "
    r"build_lock_released=1 "
    r"nav_system=/Script/NavigationSystem\.NavigationSystemV1 "
    r"bounds=1 bounds_box_valid=1 recast=1 default_recast=1 "
    r"active_tiles=([1-9][0-9]*) build_in_progress=0 "
    r"remaining_tasks=0 nav_data=/Script/NavigationSystem\.RecastNavMesh$")


def fail(message):
    unreal.log_error("WORKER-PLAN-FINAL-MAP-FAILED: " + message)
    raise RuntimeError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def spawn(actors, cls, location, label, rotation=None):
    actor = actors.spawn_actor_from_class(
        cls, location, rotation or unreal.Rotator())
    if actor is None:
        fail("spawn failed: " + label)
    actor.set_actor_label(label)
    return actor


def exact_tag(actor, tag):
    actor.set_editor_property("tags", [unreal.Name(tag)])


def main():
    if os.path.lexists(FINAL_MAP) or unreal.EditorAssetLibrary.does_asset_exist(MAP):
        fail("refusing existing final map")
    if os.path.lexists(REFERENCE):
        fail("reference must remain absent before final map authoring")
    before = {"final": final_vector(), "immutable": immutable_vector()}
    tree = unreal.EditorAssetLibrary.load_asset(FINAL_TREE)
    helper = getattr(unreal, "WorkerPlanAssetAuthoring", None)
    if tree is None or helper is None:
        fail("baseline StateTree/helper unavailable")
    shell_detail = helper.inspect_state_tree_shell(tree)
    if type(shell_detail) is not str or shell_detail != SHELL_SUCCESS:
        fail("baseline StateTree contract mismatch: %r" % shell_detail)

    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not levels.new_level_from_template(
            MAP, "/Engine/Maps/Templates/Template_Default"):
        fail("new_level_from_template failed")
    for actor in list(actors.get_all_level_actors()):
        actors.destroy_actor(actor)

    cube = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
    game_mode = unreal.EditorAssetLibrary.load_blueprint_class(GAME_MODE)
    if cube is None or game_mode is None:
        fail("stock cube/game mode unavailable")
    floor = spawn(actors, unreal.StaticMeshActor,
                  unreal.Vector(1300.0, 0.0, -50.0), "WorkerPlanRunway")
    floor.static_mesh_component.set_static_mesh(cube)
    floor.set_actor_scale3d(unreal.Vector(32.0, 12.0, 0.5))
    floor.static_mesh_component.set_collision_enabled(
        unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    nav = spawn(actors, unreal.NavMeshBoundsVolume,
                unreal.Vector(1300.0, 0.0, 150.0), "WorkerPlanNavBounds")
    nav.set_actor_scale3d(unreal.Vector(32.0, 12.0, 4.0))
    worker = spawn(actors, unreal.WorkerPlanCharacter,
                   unreal.Vector(0.0, 0.0, 100.0), "WorkerPlanSubject")
    signal = spawn(actors, unreal.WorkerPlanSignalActor,
                   unreal.Vector(-250.0, 350.0, 80.0), "WorkerPlanSignal")
    destination = spawn(actors, unreal.TargetPoint,
                        unreal.Vector(2450.0, 0.0, 100.0),
                        "WorkerPlanDestination")
    exact_tag(worker, "WorkerPlanSubject")
    exact_tag(signal, "WorkerPlanSignal")
    exact_tag(destination, "WorkerPlanDestination")
    fixture = spawn(actors, unreal.WorkerPlanFunctionalTest,
                    unreal.Vector(-300.0, -350.0, 120.0),
                    "WorkerPlanFunctionalTest")
    fixture.set_editor_property("expected_state_tree", tree)
    spawn(actors, unreal.PlayerStart, unreal.Vector(-650.0, -450.0, 120.0),
          "WorkerPlanPlayerStart", unreal.Rotator(0.0, 25.0, 0.0))
    spawn(actors, unreal.DirectionalLight, unreal.Vector(0.0, 0.0, 900.0),
          "WorkerPlanKeyLight", unreal.Rotator(-50.0, -25.0, 0.0))
    spawn(actors, unreal.SkyLight, unreal.Vector(0.0, 0.0, 650.0),
          "WorkerPlanSkyLight")

    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None:
        fail("editor world missing")
    world.get_world_settings().set_editor_property("default_game_mode", game_mode)
    nav_detail = helper.build_admission_navigation(world)
    if type(nav_detail) is not str or nav_detail.startswith("FAIL "):
        fail("native navigation failed: %r" % nav_detail)
    match = NAV_SUCCESS.fullmatch(nav_detail)
    if match is None:
        fail("native navigation contract mismatch: " + nav_detail)
    active_tiles = int(match.group(1))

    all_actors = list(actors.get_all_level_actors())
    exact = {
        "fixture": sum(a.get_class() == unreal.WorkerPlanFunctionalTest.static_class()
                       for a in all_actors),
        "worker": sum(a.get_class() == unreal.WorkerPlanCharacter.static_class()
                      and a.actor_has_tag("WorkerPlanSubject") for a in all_actors),
        "signal": sum(a.get_class() == unreal.WorkerPlanSignalActor.static_class()
                      and a.actor_has_tag("WorkerPlanSignal") for a in all_actors),
        "destination": sum(a.get_class() == unreal.TargetPoint.static_class()
                           and a.actor_has_tag("WorkerPlanDestination")
                           for a in all_actors),
        "nav_bounds": sum(a.get_class() == unreal.NavMeshBoundsVolume.static_class()
                          for a in all_actors),
        "recast": sum(a.get_class() == unreal.RecastNavMesh.static_class()
                      for a in all_actors),
        "player_start": sum(a.get_class() == unreal.PlayerStart.static_class()
                            for a in all_actors),
    }
    if any(value != 1 for value in exact.values()):
        fail("exact staged cardinality mismatch: %r" % exact)
    if not levels.save_current_level() or not FINAL_MAP.is_file():
        fail("save/final map file failed")
    if world.get_world_settings().get_editor_property("default_game_mode") != game_mode:
        fail("stock playable game mode readback mismatch")
    observed_maps = {str(value).split(".", 1)[0] for value in
                     unreal.EditorAssetLibrary.list_assets(
                         MAP_DIRECTORY, recursive=True, include_folder=False)}
    expected_maps = {
        "/Game/Maps/" + TASK_ID + "/L_WorkerPlanAdmission", MAP}
    if observed_maps != expected_maps:
        fail("map inventory mismatch: %r" % sorted(observed_maps))
    after = {"final": final_vector(), "immutable": immutable_vector()}
    if after != before:
        fail("baseline/admission/stock artifacts changed")
    marker = (
        "WORKER-PLAN-FINAL-MAP-SAVED map=%s sha256=%s actors=%d fixture=1 "
        "worker=1 signal=1 destination=1 nav_bounds=1 recast=1 "
        "player_start=1 playable_game_mode=1 active_nav_tiles=%d "
        "baseline_empty=1" %
        (MAP, sha256(FINAL_MAP), len(all_actors), active_tiles))
    unreal.log(marker)
    print(marker, flush=True)


main()
