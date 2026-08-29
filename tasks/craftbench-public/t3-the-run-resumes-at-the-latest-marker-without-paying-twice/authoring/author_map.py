"""Author the visible, playable two-process SaveGame fixture map."""

from __future__ import annotations

from pathlib import Path
import os
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run_resume_common import (  # noqa: E402
    MAP_FILE, MAP_PACKAGE, MAP_ROOT, MAP_VECTOR, map_vector, reference_vector,
    source_vector,
)


def fail(message: str) -> None:
    unreal.log_error("RUN-RESUME-MAP-FAILED: " + message)
    raise RuntimeError(message)


def spawn(actors, cls, location, label, rotation=None):
    actor = actors.spawn_actor_from_class(
        cls, location, rotation or unreal.Rotator())
    if actor is None:
        fail("spawn failed: " + label)
    actor.set_actor_label(label)
    return actor


def main() -> None:
    if os.path.lexists(MAP_ROOT):
        fail("map root must be absent")
    source_before = source_vector()
    reference_before = reference_vector()
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
                  unreal.Vector(400.0, 0.0, -50.0), "RunResumeFloor")
    floor.static_mesh_component.set_static_mesh(cube)
    floor.set_actor_scale3d(unreal.Vector(42.0, 20.0, 0.5))
    floor.static_mesh_component.set_collision_enabled(
        unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    subject = spawn(actors, unreal.RunResumeSubject,
                    unreal.Vector(-1200.0, 0.0, 100.0), "RunResumeSubject")
    subject.set_editor_property("tags", [unreal.Name("RunResumeSubject")])
    old = spawn(actors, unreal.RunResumeCheckpoint,
                unreal.Vector(-250.0, -500.0, 100.0), "Checkpoint_HarborOld")
    old.set_editor_property("checkpoint_id", unreal.Name("HarborOld"))
    latest = spawn(actors, unreal.RunResumeCheckpoint,
                   unreal.Vector(1450.0, 650.0, 100.0), "Checkpoint_CedarLatest")
    latest.set_editor_property("checkpoint_id", unreal.Name("CedarLatest"))
    for reward_id, value, location in (
            ("RewardQuartz", 17, unreal.Vector(100.0, 500.0, 100.0)),
            ("RewardViolet", 29, unreal.Vector(950.0, -450.0, 100.0)),
            ("RewardAmberControl", 41, unreal.Vector(2100.0, 0.0, 100.0))):
        reward = spawn(actors, unreal.RunResumeReward, location, reward_id)
        reward.set_editor_property("reward_id", unreal.Name(reward_id))
        reward.set_editor_property("reward_value", value)
    spawn(actors, unreal.LatestMarkerWriteFunctionalTest,
          unreal.Vector(-2800.0, -900.0, 120.0),
          "LatestMarkerWriteFunctionalTest")
    spawn(actors, unreal.LatestMarkerResumeFunctionalTest,
          unreal.Vector(2800.0, 900.0, 120.0),
          "LatestMarkerResumeFunctionalTest")
    spawn(actors, unreal.PlayerStart,
          unreal.Vector(-1800.0, 900.0, 120.0), "RunResumePlayerStart")
    spawn(actors, unreal.DirectionalLight,
          unreal.Vector(0.0, 0.0, 1200.0), "RunResumeKeyLight",
          unreal.Rotator(-48.0, -32.0, 0.0))
    spawn(actors, unreal.SkyLight,
          unreal.Vector(0.0, 0.0, 900.0), "RunResumeSkyLight")
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    game_mode = unreal.load_class(
        None, "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode."
              "BP_ThirdPersonGameMode_C")
    helper = getattr(unreal, "LatestMarkerResumeAssetAuthoring", None)
    if world is None or game_mode is None or helper is None:
        fail("world/game mode/native helper unavailable")
    world.get_world_settings().set_editor_property("default_game_mode", game_mode)
    detail = helper.inspect_map(world)
    if type(detail) is not str or detail != MAP_VECTOR:
        fail("same-process map contract mismatch: %r" % detail)
    if not levels.save_current_level():
        fail("save_current_level failed")
    hashes = map_vector()
    if (source_vector() != source_before
            or reference_vector() != reference_before):
        fail("source/reference changed during map authoring")
    marker = "RUN-RESUME-MAP-SAVED map=1 subject=1 checkpoints=2 rewards=3 " \
        "fixtures=2 player_start=1 playable=1 hashes=%r" % hashes
    unreal.log(marker)
    print(marker, flush=True)


main()
