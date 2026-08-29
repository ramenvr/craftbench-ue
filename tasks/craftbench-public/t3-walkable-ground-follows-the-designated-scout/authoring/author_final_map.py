"""Author the retained playable Nav Invoker production map once."""

import os
from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from walkable_ground_final_common import (  # noqa: E402
    FINAL_ASSET, FINAL_MAP, REFERENCE, final_vector, immutable_vector,
    map_vector, sha256,
)

TASK_ID = "t3-walkable-ground-follows-the-designated-scout"
MAP = "/Game/Maps/" + TASK_ID + "/L_WalkableGround"
MAP_DIRECTORY = "/Game/Maps/" + TASK_ID
GAME_MODE = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode"
SHELL_SUCCESS = (
    "PASS baseline_empty=1 class_exact=1 compile_exact=1 component_count=0 "
    "graph_nodes=0 visible=1")


def fail(message):
    unreal.log_error("WALKABLE-GROUND-FINAL-MAP-FAILED: " + message)
    raise RuntimeError(message)


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
    blueprint = unreal.EditorAssetLibrary.load_asset(FINAL_ASSET)
    scout_class = unreal.EditorAssetLibrary.load_blueprint_class(FINAL_ASSET)
    game_mode = unreal.EditorAssetLibrary.load_blueprint_class(GAME_MODE)
    helper = getattr(unreal, "WalkableGroundAdmissionAuthoring", None)
    if blueprint is None or scout_class is None or game_mode is None or helper is None:
        fail("baseline Blueprint/generated class/game mode/helper unavailable")
    shell = helper.inspect_designated_scout_blueprint_shell(blueprint)
    if type(shell) is not str or shell != SHELL_SUCCESS:
        fail("baseline shell contract mismatch: %r" % shell)

    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not levels.new_level_from_template(
            MAP, "/Engine/Maps/Templates/Template_Default"):
        fail("new_level_from_template failed")
    for actor in list(actors.get_all_level_actors()):
        actors.destroy_actor(actor)
    cube = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
    if cube is None:
        fail("engine cube missing")
    floor = spawn(actors, unreal.StaticMeshActor,
                  unreal.Vector(0.0, 0.0, -50.0), "WalkableGroundFloor")
    floor.static_mesh_component.set_static_mesh(cube)
    floor.set_actor_scale3d(unreal.Vector(140.0, 32.0, 0.5))
    floor.static_mesh_component.set_collision_enabled(
        unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    exact_tag(floor, "WalkableGroundFloor")
    bounds = spawn(actors, unreal.NavMeshBoundsVolume,
                   unreal.Vector(0.0, 0.0, 300.0), "WalkableGroundNavBounds")
    bounds.set_actor_scale3d(unreal.Vector(140.0, 32.0, 8.0))
    scout = spawn(actors, scout_class, unreal.Vector(-5000.0, 0.0, 100.0),
                  "DesignatedScout")
    exact_tag(scout, "WalkableGroundDesignatedScout")
    fixture = spawn(actors, unreal.WalkableGroundFunctionalTest,
                    unreal.Vector(-5900.0, -900.0, 120.0),
                    "WalkableGroundFunctionalTest")
    exact_tag(fixture, "WalkableGroundFixture")
    spawn(actors, unreal.PlayerStart, unreal.Vector(-5900.0, 900.0, 120.0),
          "WalkableGroundPlayerStart")
    spawn(actors, unreal.DirectionalLight, unreal.Vector(0.0, 0.0, 1000.0),
          "WalkableGroundKeyLight", unreal.Rotator(-50.0, -25.0, 0.0))
    spawn(actors, unreal.SkyLight, unreal.Vector(0.0, 0.0, 750.0),
          "WalkableGroundSkyLight")
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None:
        fail("editor world missing")
    world.get_world_settings().set_editor_property("default_game_mode", game_mode)
    configured = helper.configure_admission_world(world)
    if type(configured) is not str or not configured.startswith("PASS config=") \
            or "serialized_nav_data=0" not in configured:
        fail("navigation configure vector mismatch: %r" % configured)
    inspected = helper.inspect_production_world(world)
    if type(inspected) is not str or not inspected.startswith(
            "PASS scout=1 fixture=1 bounds=1 floor=1 player_start=1 ") \
            or "baseline_empty=1" not in inspected \
            or "invoker_count=0" not in inspected:
        fail("same-process production contract mismatch: %r" % inspected)
    if not levels.save_current_level() or not FINAL_MAP.is_file():
        fail("save/final map file failed")
    observed = {str(value).split(".", 1)[0] for value in
                unreal.EditorAssetLibrary.list_assets(
                    MAP_DIRECTORY, recursive=True, include_folder=False)}
    if observed != {MAP, MAP_DIRECTORY + "/L_WalkableGroundAdmission"}:
        fail("map registry inventory mismatch: %r" % sorted(observed))
    all_actors = list(actors.get_all_level_actors())
    after = {"final": final_vector(), "immutable": immutable_vector()}
    if after != before:
        fail("baseline/admission/stock artifacts changed")
    maps = map_vector()
    marker = ("WALKABLE-GROUND-FINAL-MAP-SAVED map=%s sha256=%s actors=%d "
              "scout=1 fixture=1 bounds=1 floor=1 player_start=1 "
              "playable_game_mode=1 baseline_empty=1 serialized_nav_data=0 "
              "hashes_unchanged=1 maps=%r" %
              (MAP, sha256(FINAL_MAP), len(all_actors), maps))
    unreal.log(marker)
    print(marker, flush=True)


main()
