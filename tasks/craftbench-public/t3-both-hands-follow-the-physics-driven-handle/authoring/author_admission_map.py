"""One-shot real-RHI authoring of the isolated admission world."""

import os
from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from two_hand_authoring_common import (  # noqa: E402
    ADMISSION_MAP, FINAL_MAP, REFERENCE_DIR, asset_vector, require_absent,
    vector, STOCK,
)


TASK_ID = "t3-both-hands-follow-the-physics-driven-handle"
MAP = "/Game/Maps/%s/L_TwoHandPhysicsAdmission" % TASK_ID
ANIM = ("/Game/__CraftBenchAdmission/%s/"
        "ABP_TwoHandPhysicsAdmission" % TASK_ID)


def fail(message):
    unreal.log_error("TWO-HAND-ADMISSION-MAP-FAILED " + message)
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


def main():
    require_absent(ADMISSION_MAP)
    require_absent(FINAL_MAP)
    if REFERENCE_DIR.exists() or os.path.lexists(REFERENCE_DIR):
        fail("reference must remain absent")
    before = {"admission": asset_vector(True), "task": asset_vector(False),
              "stock": vector(STOCK)}
    anim = unreal.EditorAssetLibrary.load_asset(ANIM)
    if anim is None:
        fail("admission AnimBlueprint missing")
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
                  unreal.Vector(0.0, 0.0, -50.0), "TwoHandAdmissionFloor")
    floor.static_mesh_component.set_static_mesh(cube)
    floor.set_actor_scale3d(unreal.Vector(18.0, 12.0, 0.5))
    floor.static_mesh_component.set_collision_enabled(
        unreal.CollisionEnabled.QUERY_AND_PHYSICS)

    scenario_tag = "TwoHandPhysics.AdmissionQuartz"
    handle = spawn(actors, unreal.TwoHandPhysicsHandle,
                   unreal.Vector(100.0, 0.0, 0.0), "AdmissionPhysicsHandle")
    handle.set_editor_property("tags", [unreal.Name(scenario_tag)])
    handle.set_editor_property("scenario_id", unreal.Name("AdmissionQuartz"))
    handle.set_editor_property("left_grip_local", grip(-43.0))
    handle.set_editor_property("right_grip_local", grip(54.0))
    subject = spawn(actors, unreal.TwoHandRigCharacter,
                    unreal.Vector(0.0, 0.0, 0.0), "AdmissionRigCharacter")
    subject.set_editor_property("tags", [unreal.Name(scenario_tag)])
    detail = str(unreal.TwoHandRigAssetAuthoring.configure_scenario(
        handle, subject, anim))
    if not detail.startswith("PASS TWO_HAND_SCENARIO_CONFIGURED"):
        fail(detail)
    fixture = spawn(actors, unreal.TwoHandPhysicsAdmissionFunctionalTest,
                    unreal.Vector(-250.0, -350.0, 120.0),
                    "TwoHandPhysicsAdmissionFunctionalTest")
    fixture.set_editor_property("scenario_tag", unreal.Name(scenario_tag))
    fixture.set_editor_property("first_impulse",
                                unreal.Vector(22000.0, 8000.0, 4000.0))
    fixture.set_editor_property("second_impulse",
                                unreal.Vector(-6000.0, -23000.0, 5000.0))
    spawn(actors, unreal.PlayerStart, unreal.Vector(-500.0, 500.0, 120.0),
          "TwoHandAdmissionPlayerStart")
    spawn(actors, unreal.DirectionalLight, unreal.Vector(0.0, 0.0, 800.0),
          "TwoHandAdmissionKey", unreal.Rotator(-45.0, -25.0, 0.0))
    spawn(actors, unreal.SkyLight, unreal.Vector(0.0, 0.0, 650.0),
          "TwoHandAdmissionSky")

    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    game_mode = unreal.EditorAssetLibrary.load_blueprint_class(
        "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode")
    if world is None or game_mode is None:
        fail("world/game mode missing")
    world.get_world_settings().set_editor_property("default_game_mode", game_mode)
    readback = str(unreal.TwoHandRigAssetAuthoring.inspect_authored_world(
        world, True))
    if not readback.startswith("PASS TWO_HAND_MAP_READBACK"):
        fail(readback)
    if not levels.save_current_level():
        fail("save_current_level failed")
    if not ADMISSION_MAP.is_file() or ADMISSION_MAP.is_symlink():
        fail("saved map missing/non-regular")
    after = {"admission": asset_vector(True), "task": asset_vector(False),
             "stock": vector(STOCK)}
    if after != before:
        fail("asset/stock hashes changed while authoring map")
    marker = ("TWO-HAND-ADMISSION-MAP-SAVED handles=1 subjects=1 fixtures=1 "
              "scenario=AdmissionQuartz impulses=2 player_start=1 "
              "authored_contract=1 runtime_observed=0 hashes_unchanged=1")
    unreal.log(marker)
    print(marker)


main()
