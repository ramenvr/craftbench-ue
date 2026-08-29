"""Fresh-process, read-only worker-plan admission map validation."""

import hashlib
from pathlib import Path
import unreal


TASK_ID = "t3-the-worker-keeps-its-new-plan-after-the-signal"
TREE = "/Game/__CraftBenchAdmission/" + TASK_ID + "/ST_WorkerPlan_Admission"
MAP = "/Game/Maps/" + TASK_ID + "/L_WorkerPlanAdmission"
MAP_DIRECTORY = "/Game/Maps/" + TASK_ID
MAP_FILE = (Path(unreal.Paths.project_content_dir()) / "Maps" / TASK_ID /
            "L_WorkerPlanAdmission.umap").resolve()


def fail(message):
    rendered = "WORKER-PLAN-ADMISSION-MAP-READBACK-FAILED: " + message
    unreal.log_error(rendered)
    print(rendered, flush=True)
    raise RuntimeError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main():
    inventory = {
        str(path).split(".", 1)[0]
        for path in unreal.EditorAssetLibrary.list_assets(
            MAP_DIRECTORY, recursive=True, include_folder=False)
    }
    if inventory != {MAP}:
        fail("map inventory mismatch actual=%r expected=%s" %
             (sorted(inventory), MAP))
    if not MAP_FILE.is_file():
        fail("map file missing: " + str(MAP_FILE))
    before_hash = sha256(MAP_FILE)
    tree = unreal.EditorAssetLibrary.load_asset(TREE)
    if tree is None:
        fail("admission StateTree missing: " + TREE)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.load_level(MAP):
        fail("load_level failed: " + MAP)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = list(actor_subsystem.get_all_level_actors())
    fixture_class = unreal.WorkerPlanFunctionalTest.static_class()
    fixtures = [actor for actor in actors
                if actor.get_class() == fixture_class]
    exact = {
        "fixture": len(fixtures),
        "worker": sum(
            actor.get_class() == unreal.WorkerPlanCharacter.static_class()
            and actor.actor_has_tag("WorkerPlanSubject") for actor in actors),
        "signal": sum(
            actor.get_class() == unreal.WorkerPlanSignalActor.static_class()
            and actor.actor_has_tag("WorkerPlanSignal") for actor in actors),
        "destination": sum(
            actor.get_class() == unreal.TargetPoint.static_class()
            and actor.actor_has_tag("WorkerPlanDestination")
            for actor in actors),
        "nav_bounds": sum(
            actor.get_class() == unreal.NavMeshBoundsVolume.static_class()
            for actor in actors),
        "recast": sum(
            actor.get_class() == unreal.RecastNavMesh.static_class()
            for actor in actors),
    }
    if any(value != 1 for value in exact.values()):
        fail("exact staged cardinality mismatch: %r" % exact)
    if fixtures[0].get_editor_property("expected_state_tree") != tree:
        fail("fixture StateTree readback mismatch")
    after_hash = sha256(MAP_FILE)
    if after_hash != before_hash:
        fail("read-only map hash changed before=%s after=%s" %
             (before_hash, after_hash))
    marker = (
        "WORKER-PLAN-ADMISSION-MAP-READBACK-PASS map=%s sha256=%s "
        "actors=%d fixture=1 worker=1 signal=1 destination=1 "
        "nav_bounds=1 recast=1 tree=%s" %
        (MAP, after_hash, len(actors), tree.get_path_name()))
    unreal.log(marker)
    print(marker, flush=True)


main()
