"""One-shot authoring of the retained production map; refuses overwrite."""

import hashlib
import os
from pathlib import Path

import unreal


TASK_ID = "t2-shared-helper-lives-until-the-last-lease-ends"
FINAL_DIR = "/Game/Maps/" + TASK_ID
FINAL_MAP = FINAL_DIR + "/L_SharedHelperLeases"
ADMISSION_DIR = "/Game/__CraftBenchAdmission/" + TASK_ID
ADMISSION_MAP = ADMISSION_DIR + "/L_SharedHelperLeaseAdmission"
CONTENT = Path(unreal.Paths.project_content_dir()).resolve()
FINAL_ROOT = (CONTENT / "Maps" / TASK_ID).resolve()
FINAL_FILE = (FINAL_ROOT / "L_SharedHelperLeases.umap").resolve()
ADMISSION_FILE = (CONTENT / "__CraftBenchAdmission" / TASK_ID /
                  "L_SharedHelperLeaseAdmission.umap").resolve()
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIVE = (REPO / "UE-projects/ThirdPerson/Source/ThirdPerson/Tasks" /
        TASK_ID)
REFERENCE = (HERE.parent / "reference/Source/ThirdPerson/Tasks" /
             TASK_ID)
LIVE_SOURCE_FILES = (
    "SharedHelperLeaseSubsystem.h", "SharedHelperLeaseSubsystem.cpp")
REFERENCE_SOURCE_FILES = ("SharedHelperLeaseSubsystem.cpp",)
RUNTIME_VECTOR = (
    "PASS subsystem=1 acquire=1 release=1 lease_strong=1 owner_weak=1 "
    "cache_array=1 cache_helper_strong=1 cache_leases_strong=1 "
    "active_leases_strong=1")
WORLD_VECTOR = "PASS world=1 fixtures=1 tag=1 serialized_owners=0"


def fail(message):
    rendered = "SHARED-HELPER-FINAL-MAP-AUTHOR FAILED " + message
    unreal.log_error(rendered)
    print(rendered, flush=True)
    raise RuntimeError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def is_reparse(path):
    if path.is_symlink():
        return True
    return bool(getattr(os.lstat(path), "st_file_attributes", 0) & 0x400)


def source_lock():
    facts = {}
    inventories = (
        ("live", LIVE, LIVE_SOURCE_FILES),
        ("reference", REFERENCE, REFERENCE_SOURCE_FILES),
    )
    for prefix, root, expected in inventories:
        if not root.is_dir() or is_reparse(root):
            fail("source root missing/reparse: " + str(root))
        found = sorted(path.name for path in root.iterdir() if path.is_file())
        if found != sorted(expected):
            fail("exact source inventory mismatch %s=%r" % (prefix, found))
        for name in expected:
            path = root / name
            if is_reparse(path):
                fail("source file is reparse: " + str(path))
            facts[prefix + ":" + name] = sha256(path)
    return facts


def registry_inventory(directory):
    return {str(value).split(".", 1)[0] for value in
            unreal.EditorAssetLibrary.list_assets(
                directory, recursive=True, include_folder=False)}


def main():
    if os.path.lexists(str(FINAL_ROOT)) or \
            unreal.EditorAssetLibrary.does_directory_exist(FINAL_DIR):
        fail("refusing existing final namespace: " + str(FINAL_ROOT))
    if registry_inventory(ADMISSION_DIR) != {ADMISSION_MAP}:
        fail("admission registry inventory is not exact one map")
    if not ADMISSION_FILE.is_file() or is_reparse(ADMISSION_FILE):
        fail("protected admission map missing/non-regular")
    admission_before = sha256(ADMISSION_FILE)
    sources_before = source_lock()

    helper = getattr(unreal, "SharedHelperLeaseAuthoringLibrary", None)
    if helper is None or helper.inspect_runtime_contract() != RUNTIME_VECTOR:
        fail("fixed runtime contract did not read back")
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if levels is None or actors is None:
        fail("editor subsystems unavailable")
    if not levels.new_level_from_template(
            FINAL_MAP, "/Engine/Maps/Templates/Template_Default"):
        fail("new_level_from_template failed")
    for actor in list(actors.get_all_level_actors()):
        actors.destroy_actor(actor)

    fixture_class = unreal.load_class(
        None, "/Script/CraftBenchTests.SharedHelperLeaseFunctionalTest")
    if fixture_class is None:
        fail("fixture class unavailable")
    fixture = actors.spawn_actor_from_class(
        fixture_class, unreal.Vector(0.0, 0.0, 120.0), unreal.Rotator())
    if fixture is None:
        fail("fixture spawn failed")
    fixture.set_actor_label("SharedHelperLeaseFunctionalTest")

    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    if helper.inspect_world(world) != WORLD_VECTOR:
        fail("pre-save world contract mismatch")
    if not levels.save_current_level():
        fail("save_current_level failed")
    if not FINAL_FILE.is_file() or is_reparse(FINAL_FILE):
        fail("saved final map missing/non-regular")
    if registry_inventory(FINAL_DIR) != {FINAL_MAP}:
        fail("final registry inventory is not exact one map")
    disk_files = sorted(path.name for path in FINAL_ROOT.rglob("*")
                        if path.is_file())
    if disk_files != ["L_SharedHelperLeases.umap"]:
        fail("final disk inventory mismatch: %r" % disk_files)
    if helper.inspect_world(world) != WORLD_VECTOR:
        fail("post-save world contract mismatch")
    if source_lock() != sources_before:
        fail("source/reference hashes changed during final authoring")
    if sha256(ADMISSION_FILE) != admission_before:
        fail("protected admission map hash changed")
    marker = (
        "SHARED-HELPER-FINAL-MAP-AUTHOR SAVED map=%s sha256=%s "
        "fixtures=1 tag=1 serialized_owners=0 runtime_contract=PASS" %
        (FINAL_MAP, sha256(FINAL_FILE)))
    unreal.log(marker)
    print(marker, flush=True)


main()
