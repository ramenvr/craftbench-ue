"""Author only the two-policy PCG admission map; never touch final content."""

from __future__ import annotations

from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pcg_task_common import (  # noqa: E402
    ADMISSION_GRAPH, ADMISSION_MAP, ADMISSION_MAP_FILE,
    ADMISSION_MAP_VECTOR, FINAL_GRAPH_ROOT, FINAL_MAP_FILE, MAP_ROOT,
    REFERENCE, admission_graph_vector, admission_map_vector, assert_absent,
    immutable_vector,
)


def fail(message: str) -> None:
    unreal.log_error("FILTERED-POINT-ADMISSION-MAP-FAILED: " + message)
    raise RuntimeError(message)


def spawn(actors, cls, location, label, rotation=None):
    actor = actors.spawn_actor_from_class(
        cls, location, rotation or unreal.Rotator())
    if actor is None:
        fail("spawn failed: " + label)
    actor.set_actor_label(label)
    return actor


def exact_tag(actor, tag: str) -> None:
    actor.set_editor_property("tags", [unreal.Name(tag)])
    if not actor.actor_has_tag(tag):
        fail("tag readback failed: " + tag)


def main() -> None:
    assert_absent(MAP_ROOT, FINAL_GRAPH_ROOT, FINAL_MAP_FILE, REFERENCE)
    graph_before = admission_graph_vector()
    immutable_before = immutable_vector()
    graph = unreal.EditorAssetLibrary.load_asset(ADMISSION_GRAPH)
    if graph is None:
        fail("solved admission graph missing")

    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not levels.new_level_from_template(
            ADMISSION_MAP, "/Engine/Maps/Templates/Template_Default"):
        fail("new_level_from_template failed")
    for actor in list(actors.get_all_level_actors()):
        actors.destroy_actor(actor)

    cube = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
    if cube is None:
        fail("engine cube missing")
    floor = spawn(actors, unreal.StaticMeshActor,
                  unreal.Vector(0.0, 0.0, -50.0),
                  "FilteredPointInstancesFloor")
    floor.static_mesh_component.set_static_mesh(cube)
    floor.set_actor_scale3d(unreal.Vector(60.0, 35.0, 0.5))
    floor.static_mesh_component.set_collision_enabled(
        unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    exact_tag(floor, "FilteredPointInstancesFloor")

    # Readable world landmarks make both hidden policies inspectable/playable;
    # they are protected map actors and never contribute oracle evidence.
    for index, (location, scale) in enumerate((
            (unreal.Vector(-1450.0, -550.0, 180.0),
             unreal.Vector(9.0, 6.5, 0.08)),
            (unreal.Vector(1850.0, 700.0, 180.0),
             unreal.Vector(7.6, 5.2, 0.08)))):
        marker = spawn(actors, unreal.StaticMeshActor, location,
                       "FilteredPointPolicyBounds%c" % (65 + index))
        marker.static_mesh_component.set_static_mesh(cube)
        marker.set_actor_scale3d(scale)
        marker.static_mesh_component.set_collision_enabled(
            unreal.CollisionEnabled.NO_COLLISION)
        marker.static_mesh_component.set_editor_property("visible", True)

    host = spawn(actors, unreal.FilteredPointPCGHost,
                 unreal.Vector(-1450.0, -550.0, 120.0),
                 "FilteredPointPCGHost")
    exact_tag(host, "FilteredPointPCGHost")
    host.set_graph_asset(graph)
    fixture_a = spawn(actors, unreal.FilteredPointInstancesFunctionalTestA,
                      unreal.Vector(-3200.0, -1500.0, 150.0),
                      "FilteredPointInstancesFunctionalTestA")
    exact_tag(fixture_a, "FilteredPointInstancesFixtureA")
    fixture_b = spawn(actors, unreal.FilteredPointInstancesFunctionalTestB,
                      unreal.Vector(3200.0, 1500.0, 150.0),
                      "FilteredPointInstancesFunctionalTestB")
    exact_tag(fixture_b, "FilteredPointInstancesFixtureB")
    spawn(actors, unreal.PlayerStart,
          unreal.Vector(-3800.0, 0.0, 120.0),
          "FilteredPointInstancesPlayerStart")
    spawn(actors, unreal.DirectionalLight,
          unreal.Vector(0.0, 0.0, 1200.0),
          "FilteredPointInstancesKeyLight",
          unreal.Rotator(-48.0, -32.0, 0.0))
    spawn(actors, unreal.SkyLight,
          unreal.Vector(0.0, 0.0, 900.0),
          "FilteredPointInstancesSkyLight")

    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    game_mode = unreal.load_class(
        None, "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode."
              "BP_ThirdPersonGameMode_C")
    helper = getattr(unreal, "FilteredPointInstancesAssetAuthoring", None)
    if world is None or game_mode is None or helper is None:
        fail("world/game mode/native helper unavailable")
    world.get_world_settings().set_editor_property("default_game_mode", game_mode)
    detail = helper.inspect_map(world, True)
    if type(detail) is not str or detail != ADMISSION_MAP_VECTOR:
        fail("same-process map contract mismatch: %r" % detail)
    if not levels.save_current_level():
        fail("save_current_level failed")
    map_hashes = admission_map_vector()
    if admission_graph_vector() != graph_before:
        fail("admission graph changed while authoring map")
    if immutable_vector() != immutable_before:
        fail("immutable source/stock vector changed")
    marker = (
        "FILTERED-POINT-ADMISSION-MAP-SAVED map=%s host=1 fixture_a=1 "
        "fixture_b=1 player_start=1 floor=1 graph_exact=1 "
        "runtime_observed=0 hashes=%r" % (ADMISSION_MAP, map_hashes)
    )
    unreal.log(marker)
    print(marker, flush=True)


main()
