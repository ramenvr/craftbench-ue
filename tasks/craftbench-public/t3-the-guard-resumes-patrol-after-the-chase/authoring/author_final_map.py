"""One-shot authoring of the retained production guard map."""

from pathlib import Path
import os
import re
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from guard_authoring_common import (  # noqa: E402
    ADMISSION_MAP, ADMISSION_MAP_DIR, FINAL_MAP, REFERENCE,
    exact_admission_asset_vector, exact_final_asset_vector, require_plain,
    sha256, stock_vector,
)

TASK_ID = "t3-the-guard-resumes-patrol-after-the-chase"
DIRECTORY = "/Game/Tasks/" + TASK_ID
BLACKBOARD = DIRECTORY + "/BB_GuardPatrolChase"
TREE = DIRECTORY + "/BT_GuardPatrolChase"
MAP = "/Game/Maps/" + TASK_ID + "/L_GuardPatrolChase"
MAP_SUCCESS = re.compile(
    r"^PASS admission=0 subject=1 alert=1 target=1 markers=2 "
    r"admission_fixture=0 final_fixture=1 player_start=1 nav_bounds=1 "
    r"tags=1 fixture_contract=1 game_mode=1 playable=1 "
    r"decision_reference=1 runtime_observed=0 world=.+$")
NAV_SUCCESS = re.compile(
    r"^PASS recast=1 default=1 active_tiles=([1-9][0-9]*) "
    r"build_in_progress=0 remaining=0$")


def fail(message):
    unreal.log_error("GUARD-FINAL-MAP-FAILED " + message)
    raise RuntimeError(message)


def native_detail(value):
    if type(value) is str:
        return value
    if (isinstance(value, tuple) and len(value) == 2 and
            type(value[0]) is bool and type(value[1]) is str and value[0]):
        return value[1]
    fail("unexpected native return shape: %r" % (value,))


def spawn(actors, actor_class, location, label, rotation=None):
    actor = actors.spawn_actor_from_class(
        actor_class, location, rotation or unreal.Rotator())
    if actor is None:
        fail("spawn failed: " + label)
    actor.set_actor_label(label)
    return actor


def exact_tag(actor, value):
    actor.set_editor_property("tags", [unreal.Name(value)])


def protected_snapshot():
    require_plain(ADMISSION_MAP)
    return {
        "admission_assets": exact_admission_asset_vector(),
        "admission_map": sha256(ADMISSION_MAP),
        "final_assets": exact_final_asset_vector(),
        "stock": stock_vector(),
    }


def main():
    if os.path.lexists(FINAL_MAP) or unreal.EditorAssetLibrary.does_asset_exist(MAP):
        fail("refusing existing exact final map: " + MAP)
    if os.path.lexists(REFERENCE):
        fail("reference must remain absent before final-map closure")
    before = protected_snapshot()
    blackboard = unreal.EditorAssetLibrary.load_asset(BLACKBOARD)
    tree = unreal.EditorAssetLibrary.load_asset(TREE)
    if blackboard is None or tree is None:
        fail("final baseline assets missing")

    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not levels.new_level_from_template(
            MAP, "/Engine/Maps/Templates/Template_Default"):
        fail("new_level_from_template failed")
    for actor in list(actors.get_all_level_actors()):
        actors.destroy_actor(actor)

    cube = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
    if cube is None:
        fail("engine cube unavailable")
    floor = spawn(actors, unreal.StaticMeshActor,
                  unreal.Vector(600.0, 0.0, -50.0), "GuardYardFloor")
    floor.static_mesh_component.set_static_mesh(cube)
    floor.set_actor_scale3d(unreal.Vector(44.0, 24.0, 0.5))
    floor.static_mesh_component.set_collision_enabled(
        unreal.CollisionEnabled.QUERY_AND_PHYSICS)

    nav = spawn(actors, unreal.NavMeshBoundsVolume,
                unreal.Vector(600.0, 0.0, 250.0), "GuardYardNavBounds")
    nav.set_actor_scale3d(unreal.Vector(44.0, 24.0, 6.0))
    subject = spawn(actors, unreal.GuardPatrolCharacter,
                    unreal.Vector(-900.0, 100.0, 100.0), "GuardPatrolSubject")
    subject.set_editor_property("decision_tree", tree)
    exact_tag(subject, "GuardPatrolSubject")
    alert = spawn(actors, unreal.GuardAlertSource,
                  unreal.Vector(-650.0, 650.0, 100.0), "GuardAlertSource")
    exact_tag(alert, "GuardAlertSource")
    target = spawn(actors, unreal.GuardChaseTarget,
                   unreal.Vector(2200.0, -250.0, 100.0), "GuardChaseTarget")
    exact_tag(target, "GuardChaseTarget")
    marker_a = spawn(actors, unreal.GuardPatrolMarker,
                     unreal.Vector(-250.0, 650.0, 100.0), "GuardPatrolMarkerA")
    marker_b = spawn(actors, unreal.GuardPatrolMarker,
                     unreal.Vector(1400.0, -500.0, 100.0), "GuardPatrolMarkerB")
    exact_tag(marker_a, "GuardPatrolMarker.A")
    exact_tag(marker_b, "GuardPatrolMarker.B")
    fixture = spawn(actors, unreal.GuardPatrolChaseFunctionalTest,
                    unreal.Vector(-900.0, -900.0, 120.0),
                    "GuardPatrolChaseFunctionalTest")
    fixture.set_editor_property("expected_behavior_tree", tree)
    fixture.set_editor_property("expected_blackboard", blackboard)
    fixture.set_editor_property(
        "target_velocity", unreal.Vector(0.0, -155.0, 0.0))
    spawn(actors, unreal.PlayerStart, unreal.Vector(-950.0, 950.0, 120.0),
          "GuardYardPlayerStart")
    spawn(actors, unreal.DirectionalLight, unreal.Vector(0.0, 0.0, 1000.0),
          "GuardYardKeyLight", unreal.Rotator(-50.0, -25.0, 0.0))
    spawn(actors, unreal.SkyLight, unreal.Vector(0.0, 0.0, 700.0),
          "GuardYardSkyLight")

    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None:
        fail("editor world missing")
    game_mode = unreal.EditorAssetLibrary.load_blueprint_class(
        "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode")
    if game_mode is None:
        fail("stock game mode class missing")
    world.get_world_settings().set_editor_property("default_game_mode", game_mode)

    helper = getattr(unreal, "GuardPatrolChaseAssetAuthoring", None)
    if helper is None:
        fail("compiled native helper unavailable")
    nav_detail = helper.build_admission_navigation(world)
    nav_match = NAV_SUCCESS.fullmatch(nav_detail) if type(nav_detail) is str else None
    if nav_match is None:
        fail("navigation build contract mismatch: %r" % (nav_detail,))
    map_detail = native_detail(helper.inspect_authored_map_text(world, False))
    if MAP_SUCCESS.fullmatch(map_detail) is None:
        fail("map contract mismatch: " + map_detail)
    if not levels.save_current_level():
        fail("save_current_level failed")
    require_plain(FINAL_MAP)
    direct_files = {item.name for item in ADMISSION_MAP_DIR.iterdir()
                    if item.is_file()}
    direct_dirs = {item.name for item in ADMISSION_MAP_DIR.iterdir()
                   if item.is_dir()}
    if direct_files != {ADMISSION_MAP.name, FINAL_MAP.name} or direct_dirs:
        fail("map root inventory mismatch files=%r dirs=%r" %
             (sorted(direct_files), sorted(direct_dirs)))
    if protected_snapshot() != before or os.path.lexists(REFERENCE):
        fail("protected input changed during final-map authoring")
    marker = (
        "GUARD-FINAL-MAP-SAVED actors=%d subject=1 alert=1 target=1 "
        "markers=2 fixture=1 player_start=1 nav_bounds=1 active_tiles=%s "
        "protected_hashes_unchanged=1" %
        (len(list(actors.get_all_level_actors())), nav_match.group(1)))
    unreal.log(marker)
    print(marker)


main()
