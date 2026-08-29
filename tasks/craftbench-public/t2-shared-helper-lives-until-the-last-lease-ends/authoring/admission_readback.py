"""Fresh-process, read-only admission map and runtime-surface readback."""

import hashlib
import os
from pathlib import Path

import unreal


TASK_ID = "t2-shared-helper-lives-until-the-last-lease-ends"
DIR = "/Game/__CraftBenchAdmission/" + TASK_ID
MAP = DIR + "/L_SharedHelperLeaseAdmission"
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
    rendered = "SHARED-HELPER-MAP-READBACK FAILED " + message
    unreal.log_error(rendered)
    print(rendered, flush=True)
    raise RuntimeError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def locks():
    facts = {}
    inventories = (
        ("live", LIVE, LIVE_SOURCE_FILES),
        ("reference", REFERENCE, REFERENCE_SOURCE_FILES),
    )
    for prefix, root, expected in inventories:
        found = sorted(path.name for path in root.iterdir() if path.is_file()) \
            if root.is_dir() else []
        if found != sorted(expected):
            fail("source inventory mismatch %s=%r" % (prefix, found))
        for name in expected:
            path = root / name
            if path.is_symlink():
                fail("source link refused: " + str(path))
            facts[prefix + ":" + name] = sha256(path)
    return facts


def main():
    inventory = {str(value).split(".", 1)[0] for value in
                 unreal.EditorAssetLibrary.list_assets(
                     DIR, recursive=True, include_folder=False)}
    if inventory != {MAP}:
        fail("exact map inventory mismatch actual=%r" % sorted(inventory))
    if not MAP_FILE.is_file() or MAP_FILE.is_symlink():
        fail("map missing/non-regular: " + str(MAP_FILE))
    if os.path.lexists(str(FINAL_FILE)):
        fail("protected final map unexpectedly exists")
    before_map = sha256(MAP_FILE)
    before_sources = locks()
    helper = getattr(unreal, "SharedHelperLeaseAuthoringLibrary", None)
    if helper is None or helper.inspect_runtime_contract() != RUNTIME_VECTOR:
        fail("fixed runtime contract did not read back")
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.load_level(MAP):
        fail("load_level failed: " + MAP)
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem).get_editor_world()
    observed = helper.inspect_world(world)
    if type(observed) is not str or observed != WORLD_VECTOR:
        fail("world readback mismatch actual=%r" % (observed,))
    after_map = sha256(MAP_FILE)
    if after_map != before_map or locks() != before_sources:
        fail("read-only process changed protected bytes")
    marker = (
        "SHARED-HELPER-MAP-READBACK PASS map=%s sha256=%s fixtures=1 "
        "tag=1 serialized_owners=0 runtime_contract=PASS" %
        (MAP, after_map))
    unreal.log(marker)
    print(marker, flush=True)


main()
