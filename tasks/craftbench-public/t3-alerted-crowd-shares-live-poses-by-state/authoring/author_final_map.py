"""One-shot retained final map authoring; never edits task/reference assets."""

import hashlib
from pathlib import Path

import unreal


TASK_ID = "t3-alerted-crowd-shares-live-poses-by-state"
ASSET_ROOT = "/Game/Tasks/" + TASK_ID
SETUP_PATH = ASSET_ROOT + "/AS_AlertCrowdSharing"
MAP = "/Game/Maps/" + TASK_ID + "/L_AlertCrowdSharing"
CONTENT = Path(unreal.Paths.convert_relative_path_to_full(
    unreal.Paths.project_content_dir()))
MAP_FILE = CONTENT / "Maps" / TASK_ID / "L_AlertCrowdSharing.umap"
ASSET_FILES = (
    CONTENT / "Tasks" / TASK_ID / "AS_AlertCrowdSharing.uasset",
    CONTENT / "Tasks" / TASK_ID / "BP_AlertCrowdStateProcessor.uasset",
)


def fail(message):
    unreal.log_error("ALERT-CROWD-FINAL-MAP-FAILED: " + message)
    raise RuntimeError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def spawn(actors, cls, location, label, rotation=None):
    actor = actors.spawn_actor_from_class(
        cls, location, rotation or unreal.Rotator())
    if actor is None:
        fail("spawn failed: " + label)
    actor.set_actor_label(label)
    return actor


def main():
    if MAP_FILE.exists() or unreal.EditorAssetLibrary.does_asset_exist(MAP):
        fail("refusing to overwrite retained final map")
    if any(not path.is_file() or path.is_symlink() for path in ASSET_FILES):
        fail("exact retained asset pair is missing/non-regular")
    before = {path.name: sha256(path) for path in ASSET_FILES}
    setup = unreal.EditorAssetLibrary.load_asset(SETUP_PATH)
    helper = getattr(unreal, "AlertCrowdSharingAssetAuthoring", None)
    readback = helper.inspect_final_assets(False) if helper else None
    if setup is None or type(readback) is not str or not readback.startswith(
            "PASS EMPTY exact_assets=2 expected_complete=0 "):
        fail("empty asset preflight mismatch: %r" % (readback,))

    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not levels.new_level_from_template(
            MAP, "/Engine/Maps/Templates/Template_Default"):
        fail("new_level_from_template failed")
    for actor in list(actors.get_all_level_actors()):
        actors.destroy_actor(actor)

    cube = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
    if cube is None:
        fail("engine cube missing")
    floor = spawn(actors, unreal.StaticMeshActor,
                  unreal.Vector(0.0, 0.0, -50.0), "AlertCrowdFloor")
    floor.static_mesh_component.set_static_mesh(cube)
    floor.set_actor_scale3d(unreal.Vector(24.0, 14.0, 0.5))
    floor.static_mesh_component.set_collision_enabled(
        unreal.CollisionEnabled.QUERY_AND_PHYSICS)

    for index in range(6):
        subject = spawn(
            actors, unreal.AlertCrowdSharingSubject,
            unreal.Vector(-350.0 + 130.0 * (index % 3),
                          -450.0 + 300.0 * (index // 3), 100.0),
            "AlertCrowdSubject_%d" % index)
        subject.set_editor_property("slot_index", index)
        subject.set_editor_property(
            "subject_identity", unreal.Name("Slot%d" % index))

    host = spawn(actors, unreal.AlertCrowdSharingHost,
                 unreal.Vector(-650.0, 0.0, 100.0),
                 "AlertCrowdSharingHost")
    host.set_editor_property("sharing_setup", setup)
    fixture = spawn(actors, unreal.AlertCrowdSharingFunctionalTest,
                    unreal.Vector(-650.0, -350.0, 120.0),
                    "AlertCrowdSharingFunctionalTest")
    fixture.set_editor_property("expected_setup", setup)
    spawn(actors, unreal.PlayerStart, unreal.Vector(-950.0, -700.0, 120.0),
          "AlertCrowdPlayerStart", unreal.Rotator(0.0, 25.0, 0.0))
    spawn(actors, unreal.DirectionalLight, unreal.Vector(0.0, 0.0, 900.0),
          "AlertCrowdKeyLight", unreal.Rotator(-50.0, -25.0, 0.0))
    spawn(actors, unreal.SkyLight, unreal.Vector(0.0, 0.0, 650.0),
          "AlertCrowdSkyLight")

    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    game_mode = unreal.load_class(
        None, "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode."
              "BP_ThirdPersonGameMode_C")
    if world is None or game_mode is None:
        fail("editor world or stock playable game mode missing")
    world.get_world_settings().set_editor_property("default_game_mode", game_mode)

    all_actors = list(actors.get_all_level_actors())
    exact = {
        "subjects": sum(
            actor.get_class() == unreal.AlertCrowdSharingSubject.static_class()
            and int(actor.get_editor_property("slot_index")) in range(6)
            for actor in all_actors),
        "host": sum(
            actor.get_class() == unreal.AlertCrowdSharingHost.static_class()
            for actor in all_actors),
        "fixture": sum(
            actor.get_class() == unreal.AlertCrowdSharingFunctionalTest.static_class()
            for actor in all_actors),
    }
    if exact != {"subjects": 6, "host": 1, "fixture": 1}:
        fail("exact actor cardinality mismatch: %r" % exact)
    if host.get_editor_property("sharing_setup") != setup \
            or fixture.get_editor_property("expected_setup") != setup:
        fail("setup assignment readback mismatch")
    if not levels.save_current_level() or not MAP_FILE.is_file():
        fail("map save/output failed")
    after = {path.name: sha256(path) for path in ASSET_FILES}
    if after != before:
        fail("map authoring changed retained asset bytes")
    unreal.log(
        "ALERT-CROWD-FINAL-MAP-SAVED map=%s sha256=%s subjects=6 "
        "host=1 fixture=1 setup=%s playable_game_mode=1" %
        (MAP, sha256(MAP_FILE), setup.get_path_name()))


main()
