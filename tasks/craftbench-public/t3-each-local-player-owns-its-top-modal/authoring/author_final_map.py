"""Author the protected production map exactly once."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import production_contract as contract


MAP_PACKAGE = "/Game/Maps/%s/L_LocalPlayerModalIsolation" % contract.TASK_ID


def fail(message: str) -> None:
    unreal.log_error("LOCAL-PLAYER-MODAL-FINAL-MAP-AUTHOR-ERROR " + message)
    raise RuntimeError(message)


def spawn(subsystem, actor_class, location, label):
    actor = subsystem.spawn_actor_from_class(actor_class, location)
    if actor is None:
        fail("spawn failed: " + label)
    actor.set_actor_label(label)
    return actor


def main() -> None:
    assets_before = contract.asset_vector()
    if os.path.lexists(contract.FINAL_MAP) or unreal.EditorAssetLibrary.does_asset_exist(
            MAP_PACKAGE):
        fail("refusing existing final map")
    if not contract.ADMISSION_MAP.is_file():
        fail("retained admission map is missing")
    contract.require_reference_absent()

    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not levels.new_level_from_template(
            MAP_PACKAGE, "/Engine/Maps/Templates/Template_Default"):
        fail("new_level_from_template failed")
    for actor in list(actors.get_all_level_actors()):
        actors.destroy_actor(actor)

    fixture = spawn(
        actors, unreal.LocalPlayerModalIsolationFunctionalTest,
        unreal.Vector(0.0, 0.0, 120.0),
        "LocalPlayerModalIsolationFunctionalTest")
    fixture.set_editor_property(
        "tags", [unreal.Name("LocalPlayerModalIsolationFixture")])
    spawn(actors, unreal.PlayerStart, unreal.Vector(-500.0, 0.0, 120.0),
          "LocalPlayerModalIsolationPlayerStart")
    spawn(actors, unreal.DirectionalLight, unreal.Vector(0.0, 0.0, 900.0),
          "LocalPlayerModalIsolationKeyLight")

    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    game_mode = unreal.load_class(
        None, "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode."
              "BP_ThirdPersonGameMode_C")
    if world is None or game_mode is None:
        fail("editor world or stock game mode unavailable")
    world.get_world_settings().set_editor_property("default_game_mode", game_mode)

    all_actors = list(actors.get_all_level_actors())
    fixture_count = sum(
        actor.get_class() ==
        unreal.LocalPlayerModalIsolationFunctionalTest.static_class()
        for actor in all_actors)
    player_starts = sum(
        actor.get_class() == unreal.PlayerStart.static_class()
        for actor in all_actors)
    tagged = sum(actor.actor_has_tag("LocalPlayerModalIsolationFixture")
                 for actor in all_actors)
    if fixture_count != 1 or player_starts != 1 or tagged != 1:
        fail("actor cardinality mismatch fixtures=%d starts=%d tags=%d" %
             (fixture_count, player_starts, tagged))
    if not levels.save_current_level() or not contract.FINAL_MAP.is_file() \
            or contract.FINAL_MAP.is_symlink():
        fail("final map save/output failed")
    if contract.asset_vector() != assets_before:
        fail("editable assets changed while authoring map")
    marker = (
        "LOCAL-PLAYER-MODAL-FINAL-MAP-SAVED fixtures=1 player_starts=1 "
        "game_mode_exact=1 assets_unchanged=1 runtime_observed=0 sha256=%s" %
        contract.sha256(contract.FINAL_MAP))
    unreal.log(marker)
    print(marker)


main()
