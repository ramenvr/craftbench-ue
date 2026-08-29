"""Author the retained playable production map around the empty graph shell."""

from __future__ import annotations

from pathlib import Path
import os
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pcg_task_common import (  # noqa: E402
    FINAL_GRAPH, FINAL_MAP, FINAL_MAP_FILE, FINAL_MAP_VECTOR, MAP_ROOT,
    REFERENCE, admission_graph_vector, admission_map_vector,
    final_graph_vector, final_map_vector, immutable_vector,
)


def fail(message: str) -> None:
    unreal.log_error("FILTERED-POINT-FINAL-MAP-FAILED: " + message)
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
    if os.path.lexists(FINAL_MAP_FILE) or os.path.lexists(REFERENCE):
        fail("final map/reference must be absent")
    before = {
        "admission_graph": admission_graph_vector(),
        "admission_map": admission_map_vector(),
        "baseline": final_graph_vector(),
        "immutable": immutable_vector(),
    }
    graph = unreal.EditorAssetLibrary.load_asset(FINAL_GRAPH)
    if graph is None:
        fail("final baseline graph missing")

    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not levels.new_level_from_template(
            FINAL_MAP, "/Engine/Maps/Templates/Template_Default"):
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
    detail = helper.inspect_map(world, False)
    if type(detail) is not str or detail != FINAL_MAP_VECTOR:
        fail("same-process map contract mismatch: %r" % detail)
    if not levels.save_current_level():
        fail("save_current_level failed")
    hashes = final_map_vector()
    direct_files = sorted(path.name for path in MAP_ROOT.iterdir()
                          if path.is_file())
    if direct_files != ["L_FilteredPointInstances.umap",
                        "L_FilteredPointInstancesAdmission.umap"]:
        fail("map root inventory mismatch: %r" % direct_files)
    after = {
        "admission_graph": admission_graph_vector(),
        "admission_map": admission_map_vector(),
        "baseline": final_graph_vector(),
        "immutable": immutable_vector(),
    }
    if after != before or os.path.lexists(REFERENCE):
        fail("protected input changed during final-map authoring")
    marker = (
        "FILTERED-POINT-FINAL-MAP-SAVED map=%s host=1 fixture_a=1 "
        "fixture_b=1 player_start=1 floor=1 graph_exact=1 "
        "runtime_observed=0 hashes=%r" % (FINAL_MAP, hashes)
    )
    unreal.log(marker)
    print(marker, flush=True)


main()
