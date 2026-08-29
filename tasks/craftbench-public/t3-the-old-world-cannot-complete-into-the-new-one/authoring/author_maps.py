"""Author the two visible, playable travel maps from a stock template."""

from __future__ import annotations

from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from epoch_travel_common import (  # noqa: E402
    MAP_ROOT, NEW_MAP, NEW_MAP_VECTOR, NEW_PACKAGE, NEW_RECORD, OLD_MAP,
    OLD_MAP_VECTOR, OLD_PACKAGE, OLD_RECORD, map_vector, record_vector,
    reference_vector, source_vector,
)


def fail(message: str) -> None:
    unreal.log_error("EPOCH-TRAVEL-MAP-AUTHOR-FAILED: " + message)
    raise RuntimeError(message)


def spawn(actors, cls, location, label, rotation=None):
    actor = actors.spawn_actor_from_class(
        cls, location, rotation or unreal.Rotator())
    if actor is None:
        fail("spawn failed: " + label)
    actor.set_actor_label(label)
    return actor


def build_map(package: str, start_stage: bool) -> str:
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not levels.new_level_from_template(
            package, "/Engine/Maps/Templates/Template_Default"):
        fail("new_level_from_template failed: " + package)
    for actor in list(actors.get_all_level_actors()):
        actors.destroy_actor(actor)
    cube = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
    record = unreal.EditorAssetLibrary.load_asset(
        OLD_RECORD if start_stage else NEW_RECORD)
    if cube is None or record is None:
        fail("cube/record unavailable")
    floor = spawn(actors, unreal.StaticMeshActor,
                  unreal.Vector(0.0, 0.0, -50.0), "EpochTravelFloor")
    floor.tags = [unreal.Name("EpochTravelFloor")]
    floor.static_mesh_component.set_static_mesh(cube)
    floor.set_actor_scale3d(unreal.Vector(32.0, 22.0, 0.5))
    floor.static_mesh_component.set_collision_enabled(
        unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    display = spawn(actors, unreal.EpochAssetDisplay,
                    unreal.Vector(250.0, 0.0, 160.0),
                    "OldEpochDisplay" if start_stage else "NewEpochDisplay")
    display.tags = [unreal.Name("EpochAssetDisplay")]
    fixture_class = (unreal.OldEpochStartFunctionalTest if start_stage
                     else unreal.NewEpochDestinationFunctionalTest)
    fixture = spawn(actors, fixture_class,
                    unreal.Vector(-900.0, -650.0, 120.0),
                    "OldEpochStartFunctionalTest" if start_stage
                    else "NewEpochDestinationFunctionalTest")
    fixture.set_editor_property("assigned_record", record)
    fixture.set_editor_property("display", display)
    fixture.set_editor_property(
        "expected_record_id",
        unreal.Name("OldQuartz" if start_stage else "NewViolet"))
    fixture.set_editor_property(
        "expected_record_value", 31 if start_stage else 74)
    if start_stage:
        fixture.set_editor_property("destination_map", unreal.Name(NEW_PACKAGE))
    spawn(actors, unreal.PlayerStart,
          unreal.Vector(-800.0, 650.0, 120.0), "EpochTravelPlayerStart")
    spawn(actors, unreal.DirectionalLight,
          unreal.Vector(0.0, 0.0, 1200.0), "EpochTravelKeyLight",
          unreal.Rotator(-48.0, -32.0, 0.0))
    spawn(actors, unreal.SkyLight,
          unreal.Vector(0.0, 0.0, 900.0), "EpochTravelSkyLight")
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    game_mode = unreal.load_class(
        None, "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode."
              "BP_ThirdPersonGameMode_C")
    helper = getattr(unreal, "EpochTravelAssetAuthoring", None)
    if world is None or game_mode is None or helper is None:
        fail("world/game mode/helper unavailable")
    world.get_world_settings().set_editor_property("default_game_mode", game_mode)
    detail = helper.inspect_map(world, start_stage)
    expected = OLD_MAP_VECTOR if start_stage else NEW_MAP_VECTOR
    if type(detail) is not str or detail != expected:
        fail("same-process map contract mismatch: %r" % detail)
    if not levels.save_current_level():
        fail("save_current_level failed: " + package)
    return detail


def main() -> None:
    if OLD_MAP.exists() or NEW_MAP.exists():
        fail("map outputs must be absent")
    records_before = record_vector()
    source_before = source_vector()
    reference_before = reference_vector()
    old_detail = build_map(OLD_PACKAGE, True)
    new_detail = build_map(NEW_PACKAGE, False)
    hashes = map_vector()
    if record_vector() != records_before or source_vector() != source_before \
            or reference_vector() != reference_before:
        fail("protected inputs changed")
    marker = "EPOCH-TRAVEL-MAPS-SAVED maps=2 old_contract=%r " \
        "new_contract=%r hashes=%r" % (old_detail, new_detail, hashes)
    unreal.log(marker)
    print(marker, flush=True)


main()
