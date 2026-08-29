"""Author the single playable predicted-dash network map."""

from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from dash_common import (ACCEPTED_NAMES, MAP_DIR, MAP_FILE, MAP_PACKAGE,
                         REFERENCE, files_under, vector)  # noqa: E402


def fail(message: str) -> None:
    unreal.log_error("PREDICTED-DASH-MAP-AUTHOR-ERROR: " + message)
    raise RuntimeError(message)


def spawn(actors, cls, location, label, rotation=None):
    actor = actors.spawn_actor_from_class(
        cls, location, rotation or unreal.Rotator())
    if actor is None:
        fail("spawn failed: " + label)
    actor.set_actor_label(label)
    return actor


def class_path(actor) -> str:
    return actor.get_class().get_path_name()


def inspect(world, actors) -> str:
    all_actors = list(actors.get_all_level_actors())
    fixtures_a = [a for a in all_actors if class_path(a) ==
                  "/Script/ThirdPerson.PredictedDashNetworkFunctionalTestA"]
    fixtures_b = [a for a in all_actors if class_path(a) ==
                  "/Script/ThirdPerson.PredictedDashNetworkFunctionalTestB"]
    starts = [a for a in all_actors if isinstance(a, unreal.PlayerStart)]
    floors = [a for a in all_actors
              if unreal.Name("PredictedDashFloor") in list(a.tags)]
    settings = world.get_world_settings()
    game_mode = settings.get_editor_property("default_game_mode")
    gm_path = game_mode.get_path_name() if game_mode else ""
    package = world.get_outermost().get_name()
    if package != MAP_PACKAGE or len(fixtures_a) != 1 or len(fixtures_b) != 1 \
            or len(starts) != 2 or len(floors) != 1 \
            or gm_path != "/Script/ThirdPerson.PredictedDashGameMode":
        fail("map contract mismatch package=%s A=%d B=%d starts=%d floors=%d gm=%s" %
             (package, len(fixtures_a), len(fixtures_b), len(starts),
              len(floors), gm_path))
    return "map_exact=1 fixtures_a=1 fixtures_b=1 player_starts=2 " \
        "floor=1 game_mode_exact=1 playable=1"


def main() -> None:
    if MAP_FILE.exists() or MAP_DIR.exists():
        fail("map namespace must be absent on first author")
    reference_files = tuple(
        REFERENCE / "Source" / "ThirdPerson" / "Tasks"
        / "t3-dash-responds-now-and-converges-later" / name
        for name in ACCEPTED_NAMES)
    reference_before = vector(reference_files)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not levels.new_level_from_template(
            MAP_PACKAGE, "/Engine/Maps/Templates/Template_Default"):
        fail("new_level_from_template failed")
    for actor in list(actors.get_all_level_actors()):
        actors.destroy_actor(actor)

    cube = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
    if cube is None:
        fail("engine cube missing")
    floor = spawn(actors, unreal.StaticMeshActor,
                  unreal.Vector(0.0, 0.0, -50.0), "PredictedDashFloor")
    floor.tags = [unreal.Name("PredictedDashFloor")]
    floor.static_mesh_component.set_static_mesh(cube)
    floor.set_actor_scale3d(unreal.Vector(26.0, 20.0, 0.5))
    floor.static_mesh_component.set_collision_enabled(
        unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    spawn(actors, unreal.PredictedDashNetworkFunctionalTestA,
          unreal.Vector(-900.0, -700.0, 120.0),
          "PredictedDashNetworkFunctionalTestA")
    spawn(actors, unreal.PredictedDashNetworkFunctionalTestB,
          unreal.Vector(-900.0, -500.0, 120.0),
          "PredictedDashNetworkFunctionalTestB")
    spawn(actors, unreal.PlayerStart, unreal.Vector(-700.0, -250.0, 120.0),
          "PredictedDashOwnerStart")
    spawn(actors, unreal.PlayerStart, unreal.Vector(-700.0, 250.0, 120.0),
          "PredictedDashObserverStart")
    spawn(actors, unreal.DirectionalLight, unreal.Vector(0.0, 0.0, 1100.0),
          "PredictedDashKeyLight", unreal.Rotator(-48.0, -32.0, 0.0))
    spawn(actors, unreal.SkyLight, unreal.Vector(0.0, 0.0, 900.0),
          "PredictedDashSkyLight")

    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    game_mode = unreal.load_class(
        None, "/Script/ThirdPerson.PredictedDashGameMode")
    if world is None or game_mode is None:
        fail("world/game mode missing")
    world.get_world_settings().set_editor_property("default_game_mode", game_mode)
    details = inspect(world, actors)
    if not levels.save_current_level():
        fail("save_current_level failed")
    outputs = files_under(MAP_DIR)
    if MAP_FILE not in outputs:
        fail("saved map inventory missing main package")
    hashes = vector(outputs)
    if vector(reference_files) != reference_before:
        fail("reference source changed during map author")
    marker = "PREDICTED-DASH-MAP-SAVED %s map_files=%d main_hash=%s" % (
        details, len(outputs), hashes[str(MAP_FILE)]["sha256"])
    unreal.log(marker)
    print(marker, flush=True)


if __name__ == "__main__":
    main()
