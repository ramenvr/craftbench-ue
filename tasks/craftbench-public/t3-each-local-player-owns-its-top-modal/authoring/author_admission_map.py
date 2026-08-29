"""Author the isolated two-LocalPlayer admission map exactly once."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import unreal


TASK_ID = "t3-each-local-player-owns-its-top-modal"
MAP_NAME = "L_LocalPlayerModalIsolationAdmission"
MAP_PACKAGE = "/Game/Maps/%s/%s" % (TASK_ID, MAP_NAME)
REPO = Path(__file__).resolve().parents[4]
PROJECT_ROOT = REPO / "UE-projects" / "ThirdPerson"
CONTENT = PROJECT_ROOT / "Content"
MAP_DIR = CONTENT / "Maps" / TASK_ID
MAP_FILE = MAP_DIR / (MAP_NAME + ".umap")
PRODUCTION_MAP = MAP_DIR / "L_LocalPlayerModalIsolation.umap"
TASK_ASSETS = CONTENT / "Tasks" / TASK_ID
REFERENCE = REPO / "tasks" / "bp" / TASK_ID / "reference"
PROTECTED = (
    PROJECT_ROOT / "ThirdPerson.uproject",
    PROJECT_ROOT / "Config" / "DefaultEngine.ini",
    PROJECT_ROOT / "Config" / "DefaultGame.ini",
    PROJECT_ROOT / "Source" / "CraftBenchTests" / "Tasks" / TASK_ID /
    "LocalPlayerModalIsolationAdmissionFunctionalTest.h",
    PROJECT_ROOT / "Source" / "CraftBenchTests" / "Tasks" / TASK_ID /
    "LocalPlayerModalIsolationAdmissionFunctionalTest.cpp",
    CONTENT / "ThirdPerson" / "Blueprints" / "BP_ThirdPersonGameMode.uasset",
)


def fail(message: str) -> None:
    unreal.log_error("LOCAL-PLAYER-MODAL-MAP-AUTHOR-FAILED " + message)
    raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def vector() -> dict[str, str]:
    result = {}
    for path in PROTECTED:
        if not path.is_file() or path.is_symlink():
            fail("protected prerequisite missing/non-regular: %s" % path)
        result[str(path.relative_to(REPO)).replace("\\", "/")] = sha256(path)
    return result


def spawn(actor_subsystem, actor_class, location, label):
    actor = actor_subsystem.spawn_actor_from_class(actor_class, location)
    if actor is None:
        fail("spawn failed: " + label)
    actor.set_actor_label(label)
    return actor


def main() -> None:
    if os.path.lexists(MAP_DIR) or unreal.EditorAssetLibrary.does_asset_exist(
            MAP_PACKAGE):
        fail("refusing existing admission map namespace")
    if os.path.lexists(PRODUCTION_MAP) or os.path.lexists(TASK_ASSETS) \
            or os.path.lexists(REFERENCE):
        fail("production map/task/reference boundary is not absent")
    before = vector()

    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not levels.new_level_from_template(
            MAP_PACKAGE, "/Engine/Maps/Templates/Template_Default"):
        fail("new_level_from_template failed")
    for actor in list(actors.get_all_level_actors()):
        actors.destroy_actor(actor)

    fixture = spawn(
        actors,
        unreal.LocalPlayerModalIsolationAdmissionFunctionalTest,
        unreal.Vector(0.0, 0.0, 120.0),
        "LocalPlayerModalIsolationAdmissionFunctionalTest")
    fixture.set_editor_property(
        "tags", [unreal.Name("LocalPlayerModalIsolationAdmissionFixture")])
    spawn(actors, unreal.PlayerStart, unreal.Vector(-500.0, 0.0, 120.0),
          "LocalPlayerModalIsolationAdmissionPlayerStart")
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
        unreal.LocalPlayerModalIsolationAdmissionFunctionalTest.static_class()
        for actor in all_actors)
    player_starts = sum(
        actor.get_class() == unreal.PlayerStart.static_class()
        for actor in all_actors)
    tagged = sum(
        actor.actor_has_tag("LocalPlayerModalIsolationAdmissionFixture")
        for actor in all_actors)
    if fixture_count != 1 or player_starts != 1 or tagged != 1:
        fail("exact actor cardinality mismatch fixtures=%d starts=%d tags=%d" %
             (fixture_count, player_starts, tagged))
    if not levels.save_current_level() or not MAP_FILE.is_file() \
            or MAP_FILE.is_symlink():
        fail("map save/output failed")
    if vector() != before:
        fail("protected input hash changed")
    marker = (
        "LOCAL-PLAYER-MODAL-ADMISSION-MAP-SAVED map=%s fixtures=1 "
        "player_starts=1 game_mode_exact=1 runtime_observed=0 sha256=%s" %
        (MAP_PACKAGE, sha256(MAP_FILE)))
    unreal.log(marker)
    print(marker)


main()
