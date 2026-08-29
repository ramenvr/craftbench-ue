"""Author only the verifier-owned invoker admission map; fail closed."""

from __future__ import annotations

import hashlib
from pathlib import Path

import unreal


TASK_ID = "t3-walkable-ground-follows-the-designated-scout"
MAP_NAME = "L_WalkableGroundAdmission"
MAP_PACKAGE = f"/Game/Maps/{TASK_ID}/{MAP_NAME}"
REPO = Path(__file__).resolve().parents[4]
PROJECT_ROOT = REPO / "UE-projects" / "ThirdPerson"
CONTENT = PROJECT_ROOT / "Content"
MAP_DIR = CONTENT / "Maps" / TASK_ID
MAP_FILE = MAP_DIR / f"{MAP_NAME}.umap"
FINAL_MAP = MAP_DIR / "L_WalkableGround.umap"
TASK_CONTENT = CONTENT / "Tasks" / TASK_ID
REFERENCE = Path(__file__).resolve().parents[1] / "reference"
PROTECTED_FILES = (
    PROJECT_ROOT / "ThirdPerson.uproject",
    PROJECT_ROOT / "Source" / "ThirdPerson" / "ThirdPerson.Build.cs",
    PROJECT_ROOT / "Source" / "CraftBenchTests" / "CraftBenchTests.Build.cs",
    CONTENT / "Characters" / "Mannequins" / "Meshes" / "SKM_Manny_Simple.uasset",
    CONTENT / "Characters" / "Mannequins" / "Anims" / "Unarmed" / "ABP_Unarmed.uasset",
    CONTENT / "ThirdPerson" / "Blueprints" / "BP_ThirdPersonGameMode.uasset",
)


def fail(message: str) -> None:
    unreal.log_error("WALKABLE-GROUND-ADMISSION-MAP-FAILED: " + message)
    raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def protected_hashes() -> dict[str, str]:
    missing = [str(path) for path in PROTECTED_FILES
               if not path.is_file() or path.is_symlink()]
    if missing:
        fail("protected prerequisite missing/non-regular: %r" % missing)
    return {str(path.relative_to(REPO)).replace("\\", "/"): sha256(path)
            for path in PROTECTED_FILES}


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
    if MAP_DIR.exists() or MAP_FILE.exists() \
            or unreal.EditorAssetLibrary.does_asset_exist(MAP_PACKAGE):
        fail("refusing existing admission map namespace")
    if FINAL_MAP.exists() or TASK_CONTENT.exists() or REFERENCE.exists():
        fail("production final/task/reference boundary is not absent")
    before = protected_hashes()

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
                  unreal.Vector(0.0, 0.0, -50.0), "InvokerAdmissionGround")
    floor.static_mesh_component.set_static_mesh(cube)
    floor.set_actor_scale3d(unreal.Vector(140.0, 32.0, 0.5))
    floor.static_mesh_component.set_collision_enabled(
        unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    exact_tag(floor, "WalkableGroundAdmissionFloor")

    bounds = spawn(actors, unreal.NavMeshBoundsVolume,
                   unreal.Vector(0.0, 0.0, 300.0),
                   "InvokerAdmissionNavBounds")
    bounds.set_actor_scale3d(unreal.Vector(140.0, 32.0, 8.0))

    scout = spawn(actors, unreal.WalkableGroundAdmissionScout,
                  unreal.Vector(-5000.0, 0.0, 100.0),
                  "WalkableGroundAdmissionScout")
    exact_tag(scout, "WalkableGroundAdmissionScout")
    fixture = spawn(
        actors, unreal.WalkableGroundInvokerAdmissionFunctionalTest,
        unreal.Vector(-5900.0, -900.0, 120.0),
        "WalkableGroundInvokerAdmissionFunctionalTest")
    exact_tag(fixture, "WalkableGroundAdmissionFixture")
    spawn(actors, unreal.PlayerStart,
          unreal.Vector(-5900.0, 900.0, 120.0),
          "WalkableGroundAdmissionPlayerStart")
    spawn(actors, unreal.DirectionalLight,
          unreal.Vector(0.0, 0.0, 1000.0),
          "WalkableGroundAdmissionKeyLight", unreal.Rotator(-50.0, -25.0, 0.0))
    spawn(actors, unreal.SkyLight,
          unreal.Vector(0.0, 0.0, 750.0),
          "WalkableGroundAdmissionSkyLight")

    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    game_mode = unreal.load_class(
        None, "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode."
              "BP_ThirdPersonGameMode_C")
    if world is None or game_mode is None:
        fail("editor world or stock playable game mode missing")
    world.get_world_settings().set_editor_property("default_game_mode", game_mode)

    helper = getattr(unreal, "WalkableGroundAdmissionAuthoring", None)
    configure = getattr(helper, "configure_admission_world", None) if helper else None
    inspect = getattr(helper, "inspect_admission_world", None) if helper else None
    if configure is None or inspect is None:
        fail("native admission helper unavailable")
    configured = configure(world)
    if type(configured) is not str or not configured.startswith(
            "PASS config=") or "serialized_nav_data=0" not in configured:
        fail("native configure vector mismatch: %r" % configured)
    inspected = inspect(world)
    if type(inspected) is not str or not inspected.startswith(
            "PASS scout=1 fixture=1 bounds=1 bounds_span_all=1 ") \
            or "loaded_nav_data=0" not in inspected:
        fail("same-process map inspection mismatch: %r" % inspected)

    all_actors = list(actors.get_all_level_actors())
    exact = {
        "scout": sum(a.get_class() ==
                     unreal.WalkableGroundAdmissionScout.static_class()
                     for a in all_actors),
        "fixture": sum(a.get_class() ==
                       unreal.WalkableGroundInvokerAdmissionFunctionalTest.static_class()
                       for a in all_actors),
        "bounds": sum(a.get_class() == unreal.NavMeshBoundsVolume.static_class()
                      for a in all_actors),
        "floor": sum(a.get_class() == unreal.StaticMeshActor.static_class()
                     and a.actor_has_tag("WalkableGroundAdmissionFloor")
                     for a in all_actors),
        "player_start": sum(a.get_class() == unreal.PlayerStart.static_class()
                            for a in all_actors),
    }
    if exact != {"scout": 1, "fixture": 1, "bounds": 1,
                 "floor": 1, "player_start": 1}:
        fail("exact actor cardinality mismatch: %r" % exact)
    if not levels.save_current_level() or not MAP_FILE.is_file() \
            or MAP_FILE.is_symlink():
        fail("map save/output failed")
    after = protected_hashes()
    if after != before:
        fail("protected stock/source metadata hash changed")
    unreal.log(
        "WALKABLE-GROUND-ADMISSION-MAP-SAVED map=%s sha256=%s "
        "scout=1 fixture=1 bounds=1 floor=1 player_start=1 "
        "serialized_nav_data=0 config=%s protected_hashes=%d" %
        (MAP_PACKAGE, sha256(MAP_FILE), configured, len(after)))


main()
