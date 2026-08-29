"""Author one playable final or isolated admission network map."""

import os
from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from door_common import (  # noqa: E402
    ADMISSION_ASSET, ADMISSION_MAP, ADMISSION_MAP_PACKAGE,
    ADMISSION_MAP_VECTOR, ADMISSION_OBJECT, FINAL_ASSET, FINAL_MAP,
    FINAL_MAP_PACKAGE, FINAL_MAP_VECTOR, FINAL_OBJECT, REFERENCE_ASSET,
    assert_absent, optional_vector, regular_vector,
)


def fail(message: str) -> None:
    unreal.log_error("REPLICATED-DOOR-MAP-AUTHOR-ERROR: " + message)
    raise RuntimeError(message)


def spawn(actors, cls, location, label, rotation=None):
    actor = actors.spawn_actor_from_class(
        cls, location, rotation or unreal.Rotator())
    if actor is None:
        fail("spawn failed: " + label)
    actor.set_actor_label(label)
    return actor


def main() -> None:
    mode = os.environ.get("CRAFTBENCH_DOOR_MAP_MODE", "")
    if mode not in ("final", "admission"):
        fail("mode must be final or admission")
    admission = mode == "admission"
    map_file = ADMISSION_MAP if admission else FINAL_MAP
    map_package = ADMISSION_MAP_PACKAGE if admission else FINAL_MAP_PACKAGE
    asset_file = ADMISSION_ASSET if admission else FINAL_ASSET
    asset_object = ADMISSION_OBJECT if admission else FINAL_OBJECT
    expected = ADMISSION_MAP_VECTOR if admission else FINAL_MAP_VECTOR
    assert_absent(map_file, REFERENCE_ASSET)
    protected_before = optional_vector((FINAL_ASSET, ADMISSION_ASSET,
                                        REFERENCE_ASSET))
    if protected_before[str(asset_file)] is None:
        fail("required Door Blueprint missing")

    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not levels.new_level_from_template(
            map_package, "/Engine/Maps/Templates/Template_Default"):
        fail("new_level_from_template failed")
    for actor in list(actors.get_all_level_actors()):
        actors.destroy_actor(actor)

    cube = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
    door_bp = unreal.EditorAssetLibrary.load_asset(asset_object)
    door_class = door_bp.generated_class() if door_bp else None
    if cube is None or door_class is None:
        fail("cube/door class unavailable")
    floor = spawn(actors, unreal.StaticMeshActor,
                  unreal.Vector(0.0, 0.0, -55.0), "DoorArenaFloor")
    floor.tags = [unreal.Name("DoorArenaFloor")]
    floor.static_mesh_component.set_static_mesh(cube)
    floor.set_actor_scale3d(unreal.Vector(20.0, 16.0, 0.5))
    floor.static_mesh_component.set_collision_enabled(
        unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    door = spawn(actors, door_class, unreal.Vector(250.0, 0.0, 105.0),
                 "ReplicatedDoorState")
    fixture = spawn(actors, unreal.ReplicatedDoorNetworkFunctionalTest,
                    unreal.Vector(-600.0, -500.0, 120.0),
                    "ReplicatedDoorNetworkFunctionalTest")
    fixture.set_editor_property("door", door)
    spawn(actors, unreal.PlayerStart, unreal.Vector(-650.0, 250.0, 120.0),
          "DoorPlayerStart")
    spawn(actors, unreal.DirectionalLight, unreal.Vector(0.0, 0.0, 1000.0),
          "DoorKeyLight", unreal.Rotator(-48.0, -28.0, 0.0))
    spawn(actors, unreal.SkyLight, unreal.Vector(0.0, 0.0, 850.0),
          "DoorSkyLight")

    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    game_mode = unreal.load_class(
        None, "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode."
              "BP_ThirdPersonGameMode_C")
    helper = getattr(unreal, "ReplicatedDoorAssetAuthoring", None)
    if world is None or game_mode is None or helper is None:
        fail("world/game mode/helper unavailable")
    world.get_world_settings().set_editor_property("default_game_mode", game_mode)
    detail = helper.inspect_door_map(world, admission)
    if type(detail) is not str or detail != expected:
        fail("same-process map vector mismatch: %r" % detail)
    if not levels.save_current_level():
        fail("save_current_level failed")
    map_hash = regular_vector((map_file,))[str(map_file)]["sha256"]
    if optional_vector((FINAL_ASSET, ADMISSION_ASSET, REFERENCE_ASSET)) \
            != protected_before:
        fail("asset/reference inputs changed")
    marker = "REPLICATED-DOOR-MAP-SAVED mode=%s map_files=1 doors=1 " \
        "fixtures=1 player_starts=1 playable=1 hash=%s" % (mode, map_hash)
    unreal.log(marker)
    print(marker, flush=True)


main()
