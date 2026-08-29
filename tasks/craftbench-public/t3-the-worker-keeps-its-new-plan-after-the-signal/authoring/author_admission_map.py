"""One-shot isolated worker-plan admission map authoring."""

import hashlib
from pathlib import Path
import re
import unreal


TASK_ID = "t3-the-worker-keeps-its-new-plan-after-the-signal"
TREE = "/Game/__CraftBenchAdmission/" + TASK_ID + "/ST_WorkerPlan_Admission"
MAP = "/Game/Maps/" + TASK_ID + "/L_WorkerPlanAdmission"
MAP_FILE = (Path(unreal.Paths.project_content_dir()) / "Maps" / TASK_ID /
            "L_WorkerPlanAdmission.umap").resolve()
NAV_SUCCESS = re.compile(
    r"^PASS world=Editor initialized=1 persistent_config=1 "
    r"config=/(?:Script/Engine\.NavigationSystemConfig|"
    r"Script/NavigationSystem\.NavigationSystemModuleConfig) "
    r"config_class_supported=1 "
    r"configured_nav_class=/Script/NavigationSystem\.NavigationSystemV1 "
    r"configured_nav_class_exact=1 "
    r"async_load_lock=1 other_lock=0 asset_compiles=0 "
    r"build_lock_released=1 "
    r"nav_system=/Script/NavigationSystem\.NavigationSystemV1 "
    r"bounds=1 bounds_box_valid=1 recast=1 default_recast=1 "
    r"active_tiles=([1-9][0-9]*) build_in_progress=0 "
    r"remaining_tasks=0 nav_data=/Script/NavigationSystem\.RecastNavMesh$")


def fail(message):
    unreal.log_error("WORKER-PLAN-ADMISSION-MAP-FAILED: " + message)
    raise RuntimeError(message)


def spawn(actors, cls, location, label, rotation=None):
    actor = actors.spawn_actor_from_class(
        cls, location, rotation or unreal.Rotator())
    if actor is None:
        fail("spawn failed: " + label)
    actor.set_actor_label(label)
    return actor


def exact_tag(actor, tag):
    actor.set_editor_property("tags", [unreal.Name(tag)])


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main():
    if unreal.EditorAssetLibrary.does_asset_exist(MAP):
        fail("refusing to overwrite retained map: " + MAP)
    tree = unreal.EditorAssetLibrary.load_asset(TREE)
    if tree is None:
        fail("admission StateTree missing: " + TREE)
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
                  unreal.Vector(1300.0, 0.0, -50.0), "WorkerPlanRunway")
    floor.static_mesh_component.set_static_mesh(cube)
    floor.set_actor_scale3d(unreal.Vector(32.0, 12.0, 0.5))
    floor.static_mesh_component.set_collision_enabled(
        unreal.CollisionEnabled.QUERY_AND_PHYSICS)

    nav = spawn(actors, unreal.NavMeshBoundsVolume,
                unreal.Vector(1300.0, 0.0, 150.0), "WorkerPlanNavBounds")
    nav.set_actor_scale3d(unreal.Vector(32.0, 12.0, 4.0))
    worker = spawn(actors, unreal.WorkerPlanCharacter,
                   unreal.Vector(0.0, 0.0, 100.0), "WorkerPlanSubject")
    signal = spawn(actors, unreal.WorkerPlanSignalActor,
                   unreal.Vector(-250.0, 350.0, 80.0), "WorkerPlanSignal")
    destination = spawn(actors, unreal.TargetPoint,
                        unreal.Vector(2450.0, 0.0, 100.0),
                        "WorkerPlanDestination")
    exact_tag(worker, "WorkerPlanSubject")
    exact_tag(signal, "WorkerPlanSignal")
    exact_tag(destination, "WorkerPlanDestination")
    fixture = spawn(actors, unreal.WorkerPlanFunctionalTest,
                    unreal.Vector(-300.0, -350.0, 120.0),
                    "WorkerPlanFunctionalTest")
    fixture.set_editor_property("expected_state_tree", tree)
    spawn(actors, unreal.PlayerStart, unreal.Vector(-500.0, -500.0, 120.0),
          "WorkerPlanPlayerStart")
    spawn(actors, unreal.DirectionalLight, unreal.Vector(0.0, 0.0, 900.0),
          "WorkerPlanKeyLight", unreal.Rotator(-50.0, -25.0, 0.0))
    spawn(actors, unreal.SkyLight, unreal.Vector(0.0, 0.0, 650.0),
          "WorkerPlanSkyLight")

    # ARecastNavMesh is UCLASS(notplaceable) in UE 5.8. The verifier-only
    # native helper creates/configures UNavigationSystemV1 from the persistent
    # WorldSettings config, then calls public Build(). Python accepts only the
    # complete native engine-owned result vector.
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None:
        fail("editor world missing before navigation build")
    nav_contract = unreal.WorkerPlanAssetAuthoring.build_admission_navigation(
        world)
    if nav_contract is None:
        fail("native navigation returned no contract; inspect "
             "WORKER-PLAN-ADMISSION-NAVIGATION-NATIVE in the log")
    if type(nav_contract) is not str:
        fail("native navigation binding shape mismatch: %r" %
             type(nav_contract))
    if nav_contract.startswith("FAIL "):
        fail("native navigation failed: " + nav_contract)
    nav_match = NAV_SUCCESS.fullmatch(nav_contract)
    if nav_match is None:
        fail("native navigation contract mismatch: " + nav_contract)
    active_nav_tiles = int(nav_match.group(1))
    unreal.log("WORKER-PLAN-ADMISSION-NAVIGATION-READY " + nav_contract)

    all_actors = list(actors.get_all_level_actors())
    exact = {
        "fixture": sum(a.get_class() == unreal.WorkerPlanFunctionalTest.static_class()
                       for a in all_actors),
        "worker": sum(
            a.get_class() == unreal.WorkerPlanCharacter.static_class()
            and a.actor_has_tag("WorkerPlanSubject") for a in all_actors),
        "signal": sum(
            a.get_class() == unreal.WorkerPlanSignalActor.static_class()
            and a.actor_has_tag("WorkerPlanSignal") for a in all_actors),
        "destination": sum(
            a.get_class() == unreal.TargetPoint.static_class()
            and a.actor_has_tag("WorkerPlanDestination")
            for a in all_actors),
        "nav": sum(a.get_class() == unreal.NavMeshBoundsVolume.static_class()
                   for a in all_actors),
        "recast": sum(a.get_class() == unreal.RecastNavMesh.static_class()
                      for a in all_actors),
    }
    if any(value != 1 for value in exact.values()):
        fail("exact staged cardinality mismatch: %r" % exact)
    if not levels.save_current_level():
        fail("save_current_level failed")
    if fixture.get_editor_property("expected_state_tree") != tree:
        fail("fixture StateTree readback mismatch")
    if not MAP_FILE.is_file():
        fail("saved map file missing: " + str(MAP_FILE))
    map_hash = sha256(MAP_FILE)
    unreal.log(
        "WORKER-PLAN-ADMISSION-MAP-SAVED map=%s sha256=%s actors=%d "
        "fixture=1 worker=1 signal=1 destination=1 nav_bounds=1 recast=1 "
        "nav_build=native-public-api active_nav_tiles=%d tree=%s" %
        (MAP, map_hash, len(all_actors), active_nav_tiles,
         tree.get_path_name()))


main()
