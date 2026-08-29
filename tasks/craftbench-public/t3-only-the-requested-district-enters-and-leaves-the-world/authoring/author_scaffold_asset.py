"""Author the exact empty editable loader Blueprint; never overwrite."""

from __future__ import annotations

import unreal


TASK_ID = "t3-only-the-requested-district-enters-and-leaves-the-world"
ASSET_DIR = "/Game/Tasks/" + TASK_ID
ASSET_NAME = "BP_DistrictStreamLoader"
ASSET_PATH = ASSET_DIR + "/" + ASSET_NAME
PARENT_PATH = "/Script/ThirdPerson.DistrictStreamLoaderBase"


def fail(message: str) -> None:
    unreal.log_error("DISTRICT-STREAMING-ASSET-ERROR " + message)
    raise RuntimeError(message)


def inventory() -> set[str]:
    return {
        str(value).split(".", 1)[0]
        for value in unreal.EditorAssetLibrary.list_assets(
            ASSET_DIR, recursive=True, include_folder=False
        )
    }


def main() -> None:
    if inventory():
        fail("task asset namespace must be empty before authoring")
    parent = unreal.load_class(None, PARENT_PATH)
    if parent is None:
        fail("runtime loader parent did not load")
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", parent)
    blueprint = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        ASSET_NAME, ASSET_DIR, unreal.Blueprint, factory
    )
    if blueprint is None:
        fail("BlueprintFactory returned None")
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    if not unreal.EditorAssetLibrary.save_asset(ASSET_PATH, only_if_is_dirty=False):
        fail("save failed")
    loaded = unreal.EditorAssetLibrary.load_asset(ASSET_PATH)
    actual_parent = unreal.BlueprintEditorLibrary.get_blueprint_parent_class(loaded)
    if actual_parent is None or actual_parent.get_path_name() != PARENT_PATH:
        fail("cold identity mismatch parent=%r" % actual_parent)
    if inventory() != {ASSET_PATH}:
        fail("exact inventory mismatch after save")
    unreal.log(
        "DISTRICT-STREAMING-SCAFFOLD-SAVED assets=1 parent=direct graph=empty"
    )
    print("DISTRICT-STREAMING-SCAFFOLD-SAVED assets=1 parent=direct graph=empty")


main()
