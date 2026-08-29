"""One-shot admission map authoring; refuses every existing output."""

import hashlib
import os
from pathlib import Path

import unreal


TASK_ID = "t2-shared-helper-lives-until-the-last-lease-ends"
MAP = "/Game/__CraftBenchAdmission/%s/L_SharedHelperLeaseAdmission" % TASK_ID
MAP_FILE = (Path(unreal.Paths.project_content_dir()) / "__CraftBenchAdmission" /
            TASK_ID / "L_SharedHelperLeaseAdmission.umap").resolve()
FINAL_FILE = (Path(unreal.Paths.project_content_dir()) / "Maps" / TASK_ID /
              "L_SharedHelperLeases.umap").resolve()
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
    rendered = "SHARED-HELPER-MAP-AUTHOR FAILED " + message
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


def main():
    if os.path.lexists(str(MAP_FILE)) or unreal.EditorAssetLibrary.does_asset_exist(MAP):
        fail("refusing to overwrite admission map: " + str(MAP_FILE))
    if os.path.lexists(str(FINAL_FILE)):
        fail("protected final map unexpectedly exists: " + str(FINAL_FILE))
    before = source_lock()
    helper = getattr(unreal, "SharedHelperLeaseAuthoringLibrary", None)
    if helper is None:
        fail("native helper unavailable")
    runtime = helper.inspect_runtime_contract()
    if type(runtime) is not str or runtime != RUNTIME_VECTOR:
        fail("runtime contract mismatch actual=%r" % (runtime,))

    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if levels is None or actors is None:
        fail("editor subsystems unavailable")
    if not levels.new_level_from_template(
            MAP, "/Engine/Maps/Templates/Template_Default"):
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
    fixture.set_actor_label("SharedHelperLeaseAdmissionFunctionalTest")

    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    staged = helper.inspect_world(world)
    if type(staged) is not str or staged != WORLD_VECTOR:
        fail("pre-save world contract mismatch actual=%r" % (staged,))
    if not levels.save_current_level():
        fail("save_current_level failed")
    if not MAP_FILE.is_file() or is_reparse(MAP_FILE):
        fail("saved admission map missing/non-regular")
    after_world = helper.inspect_world(world)
    if after_world != WORLD_VECTOR:
        fail("post-save world contract mismatch actual=%r" % (after_world,))
    if source_lock() != before:
        fail("source/reference hashes changed during map authoring")
    if os.path.lexists(str(FINAL_FILE)):
        fail("protected final map appeared during authoring")
    marker = (
        "SHARED-HELPER-MAP-AUTHOR SAVED map=%s sha256=%s fixtures=1 "
        "tag=1 serialized_owners=0 runtime_contract=PASS" %
        (MAP, sha256(MAP_FILE)))
    unreal.log(marker)
    print(marker, flush=True)


main()
