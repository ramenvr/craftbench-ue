"""Create one retained walker Blueprint without overwriting any package."""

import argparse
import hashlib
import os
from pathlib import Path
import unreal


TASK_ID = "t3-both-walkers-yield-and-still-arrive"
FINAL = "/Game/Tasks/%s/BP_YieldingWalker" % TASK_ID
ADMISSION = "/Game/__CraftBenchAdmission/%s/BP_YieldingWalker_Admission" % TASK_ID
PARENT = "/Script/ThirdPerson.WalkerYieldCharacter"
EXPECTED = {
    "baseline": (FINAL, False, 0.50, 650.0),
    "admission": (ADMISSION, True, 0.50, 650.0),
}


def fail(message):
    unreal.log_error("WALKER-YIELD-ASSET-FAILED: " + message)
    raise RuntimeError(message)


def disk_path(package):
    relative = package.removeprefix("/Game/") + ".uasset"
    return (Path(unreal.Paths.project_content_dir()) / relative).resolve()


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=sorted(EXPECTED),
                        default=os.environ.get("CRAFTBENCH_WALKER_YIELD_MODE"))
    args, _ = parser.parse_known_args()
    if args.mode is None:
        fail("--mode or CRAFTBENCH_WALKER_YIELD_MODE is required")
    package, enabled, weight, radius = EXPECTED[args.mode]
    output_file = disk_path(package)
    if unreal.EditorAssetLibrary.does_asset_exist(package) or output_file.exists():
        fail("refusing to overwrite retained output: " + package)
    parent = unreal.load_class(None, PARENT)
    if parent is None:
        fail("native parent missing: " + PARENT)
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", parent)
    name = package.rsplit("/", 1)[1]
    directory = package.rsplit("/", 1)[0]
    blueprint = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, directory, unreal.Blueprint, factory)
    if blueprint is None:
        fail("BlueprintFactory returned None")
    result = str(
        unreal.WalkerYieldAuthoringLibrary.configure_walker_blueprint(
            blueprint, enabled, weight, radius))
    if not result.startswith("PASS "):
        fail("native configure/readback failed: " + result)
    if not output_file.is_file():
        fail("saved package missing: " + str(output_file))
    unreal.log(
        "WALKER-YIELD-ASSET-SAVED mode=%s asset=%s sha256=%s "
        "avoidance=%d weight=%.2f radius=%.1f result=%s" %
        (args.mode, package, sha256(output_file), int(enabled), weight,
         radius, result))


main()
