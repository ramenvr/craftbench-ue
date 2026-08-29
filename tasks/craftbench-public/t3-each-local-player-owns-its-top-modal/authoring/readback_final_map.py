"""Fresh-process, read-only final-map contract validation."""

from __future__ import annotations

from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import production_contract as contract


MAP_PACKAGE = "/Game/Maps/%s/L_LocalPlayerModalIsolation" % contract.TASK_ID


def fail(message: str) -> None:
    unreal.log_error("LOCAL-PLAYER-MODAL-FINAL-MAP-READBACK-ERROR " + message)
    raise RuntimeError(message)


def main() -> None:
    if not contract.FINAL_MAP.is_file() or contract.FINAL_MAP.is_symlink():
        fail("exact final map is absent/non-regular")
    contract.require_reference_absent()
    assets_before = contract.asset_vector()
    map_before = contract.vector((contract.ADMISSION_MAP, contract.FINAL_MAP))
    if not unreal.EditorLoadingAndSavingUtils.load_map(MAP_PACKAGE):
        fail("cold map load failed")
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    actors = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem).get_all_level_actors()
    fixtures = sum(
        actor.get_class() ==
        unreal.LocalPlayerModalIsolationFunctionalTest.static_class()
        for actor in actors)
    starts = sum(actor.get_class() == unreal.PlayerStart.static_class()
                 for actor in actors)
    tags = sum(actor.actor_has_tag("LocalPlayerModalIsolationFixture")
               for actor in actors)
    game_mode = unreal.load_class(
        None, "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode."
              "BP_ThirdPersonGameMode_C")
    actual = world.get_world_settings().get_editor_property(
        "default_game_mode") if world is not None else None
    if fixtures != 1 or starts != 1 or tags != 1 or actual != game_mode:
        fail("cold contract mismatch fixture=%d start=%d tag=%d game_mode=%r" %
             (fixtures, starts, tags, actual))
    if contract.asset_vector() != assets_before or \
            contract.vector((contract.ADMISSION_MAP, contract.FINAL_MAP)) != map_before:
        fail("cold map readback changed protected bytes")
    marker = (
        "LOCAL-PLAYER-MODAL-FINAL-MAP-COLD-READBACK-PASS fixtures=1 "
        "player_starts=1 game_mode_exact=1 hashes_unchanged=1 "
        "runtime_observed=0")
    unreal.log(marker)
    print(marker)


main()
