"""One-shot authoring of the two-fixture committed-path final world."""

from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from two_hand_authoring_common import (  # noqa: E402
    ADMISSION_MAP, FINAL_MAP, asset_vector, map_files,
    reference_state, require_absent, vector, STOCK,
)


TASK_ID = "t3-both-hands-follow-the-physics-driven-handle"
MAP = "/Game/Maps/%s/L_TwoHandPhysics" % TASK_ID
ANIM = "/Game/Tasks/%s/ABP_TwoHandPhysics" % TASK_ID


def fail(message):
    unreal.log_error("TWO-HAND-FINAL-MAP-FAILED " + message)
    raise RuntimeError(message)


def spawn(subsystem, actor_class, location, label, rotation=None):
    actor = subsystem.spawn_actor_from_class(
        actor_class, location, rotation or unreal.Rotator())
    if actor is None:
        fail("spawn failed: " + label)
    actor.set_actor_label(label)
    return actor


def grip(y):
    value = unreal.Transform()
    value.set_editor_property("translation", unreal.Vector(0.0, y, 0.0))
    return value


def add_scenario(actors, anim, fixture_class, suffix, center_y, left_y, right_y,
                 impulse_a, impulse_b):
    tag = "TwoHandPhysics." + suffix
    handle = spawn(actors, unreal.TwoHandPhysicsHandle,
                   unreal.Vector(100.0, center_y, 0.0), suffix + "PhysicsHandle")
    handle.set_editor_property("tags", [unreal.Name(tag)])
    handle.set_editor_property("scenario_id", unreal.Name(suffix))
    handle.set_editor_property("left_grip_local", grip(left_y))
    handle.set_editor_property("right_grip_local", grip(right_y))
    subject = spawn(actors, unreal.TwoHandRigCharacter,
                    unreal.Vector(0.0, center_y, 0.0), suffix + "RigCharacter")
    subject.set_editor_property("tags", [unreal.Name(tag)])
    detail = str(unreal.TwoHandRigAssetAuthoring.configure_scenario(
        handle, subject, anim))
    if not detail.startswith("PASS TWO_HAND_SCENARIO_CONFIGURED"):
        fail(suffix + ": " + detail)
    fixture_label = "TwoHandPhysics%sFunctionalTest" % suffix
    fixture = spawn(actors, fixture_class,
                    unreal.Vector(-250.0, center_y - 300.0, 120.0),
                    fixture_label)
    fixture.set_editor_property("scenario_tag", unreal.Name(tag))
    fixture.set_editor_property("first_impulse", unreal.Vector(*impulse_a))
    fixture.set_editor_property("second_impulse", unreal.Vector(*impulse_b))


def main():
    require_absent(FINAL_MAP)
    if not ADMISSION_MAP.is_file() or ADMISSION_MAP.is_symlink():
        fail("admission map must exist and be regular")
    before = {"admission": asset_vector(True), "task": asset_vector(False),
              "admission_map": vector(map_files(ADMISSION_MAP)),
              "stock": vector(STOCK), "reference": reference_state()}
    anim = unreal.EditorAssetLibrary.load_asset(ANIM)
    if anim is None:
        fail("baseline AnimBlueprint missing")
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
                  unreal.Vector(0.0, 0.0, -50.0), "TwoHandStageFloor")
    floor.static_mesh_component.set_static_mesh(cube)
    floor.set_actor_scale3d(unreal.Vector(18.0, 18.0, 0.5))
    floor.static_mesh_component.set_collision_enabled(
        unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    add_scenario(actors, anim, unreal.TwoHandPhysicsQuartzFunctionalTest,
                 "Quartz", -420.0, -43.0, 54.0,
                 (22000.0, 8000.0, 4000.0),
                 (-6000.0, -23000.0, 5000.0))
    add_scenario(actors, anim, unreal.TwoHandPhysicsVioletFunctionalTest,
                 "Violet", 420.0, -58.0, 38.0,
                 (-18000.0, 13000.0, 6000.0),
                 (17000.0, -9000.0, -7000.0))
    spawn(actors, unreal.PlayerStart, unreal.Vector(-650.0, 0.0, 120.0),
          "TwoHandStagePlayerStart")
    spawn(actors, unreal.DirectionalLight, unreal.Vector(0.0, 0.0, 900.0),
          "TwoHandStageKey", unreal.Rotator(-45.0, -25.0, 0.0))
    spawn(actors, unreal.SkyLight, unreal.Vector(0.0, 0.0, 700.0),
          "TwoHandStageSky")
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    game_mode = unreal.EditorAssetLibrary.load_blueprint_class(
        "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode")
    if world is None or game_mode is None:
        fail("world/game mode missing")
    world.get_world_settings().set_editor_property("default_game_mode", game_mode)
    readback = str(unreal.TwoHandRigAssetAuthoring.inspect_authored_world(
        world, False))
    if not readback.startswith("PASS TWO_HAND_MAP_READBACK"):
        fail(readback)
    if not levels.save_current_level():
        fail("save_current_level failed")
    if not FINAL_MAP.is_file() or FINAL_MAP.is_symlink():
        fail("saved map missing/non-regular")
    after = {"admission": asset_vector(True), "task": asset_vector(False),
             "admission_map": vector(map_files(ADMISSION_MAP)),
             "stock": vector(STOCK), "reference": reference_state()}
    if after != before:
        fail("protected package hashes changed")
    marker = ("TWO-HAND-FINAL-MAP-SAVED handles=2 subjects=2 fixtures=2 "
              "scenarios=Quartz,Violet distinct_grips=1 distinct_impulses=1 "
              "fixture_labels_exact=1 player_start=1 authored_contract=1 "
              "runtime_observed=0")
    unreal.log(marker)
    print(marker)


main()
