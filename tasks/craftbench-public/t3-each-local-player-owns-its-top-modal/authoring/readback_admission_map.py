"""Fresh-process, read-only admission-map contract check."""

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
    unreal.log_error("LOCAL-PLAYER-MODAL-MAP-READBACK-FAILED " + message)
    raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def vector() -> dict[str, str]:
    paths = PROTECTED + (MAP_FILE,)
    result = {}
    for path in paths:
        if not path.is_file() or path.is_symlink():
            fail("protected prerequisite missing/non-regular: %s" % path)
        result[str(path.relative_to(REPO)).replace("\\", "/")] = sha256(path)
    return result


def main() -> None:
    if not MAP_FILE.is_file() or MAP_FILE.is_symlink():
        fail("exact map is absent/non-regular")
    files = sorted(path for path in MAP_DIR.rglob("*") if path.is_file())
    if files != [MAP_FILE]:
        fail("map namespace inventory mismatch: %r" %
             [str(path) for path in files])
    if os.path.lexists(PRODUCTION_MAP) or os.path.lexists(TASK_ASSETS) \
            or os.path.lexists(REFERENCE):
        fail("production map/task/reference boundary is not absent")
    before = vector()
    if not unreal.EditorLoadingAndSavingUtils.load_map(MAP_PACKAGE):
        fail("cold map load failed")
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    actors = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem).get_all_level_actors()
    fixture_count = sum(
        actor.get_class() ==
        unreal.LocalPlayerModalIsolationAdmissionFunctionalTest.static_class()
        for actor in actors)
    player_starts = sum(
        actor.get_class() == unreal.PlayerStart.static_class()
        for actor in actors)
    tagged = sum(
        actor.actor_has_tag("LocalPlayerModalIsolationAdmissionFixture")
        for actor in actors)
    game_mode = unreal.load_class(
        None, "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode."
              "BP_ThirdPersonGameMode_C")
    actual_game_mode = world.get_world_settings().get_editor_property(
        "default_game_mode") if world is not None else None
    if fixture_count != 1 or player_starts != 1 or tagged != 1 \
            or game_mode is None or actual_game_mode != game_mode:
        fail("cold contract mismatch fixtures=%d starts=%d tags=%d game_mode=%r" %
             (fixture_count, player_starts, tagged, actual_game_mode))
    if vector() != before:
        fail("readback changed protected bytes")
    marker = (
        "LOCAL-PLAYER-MODAL-ADMISSION-MAP-READBACK-PASS fixtures=1 "
        "player_starts=1 game_mode_exact=1 runtime_observed=0 "
        "hashes_unchanged=1 map_sha256=%s" % sha256(MAP_FILE))
    unreal.log(marker)
    print(marker)


main()
