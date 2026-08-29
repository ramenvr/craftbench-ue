"""Fresh-process, read-only scaffold identity check."""

from __future__ import annotations

import unreal


TASK_ID = "t3-only-the-requested-district-enters-and-leaves-the-world"
ASSET_DIR = "/Game/Tasks/" + TASK_ID
ASSET_PATH = ASSET_DIR + "/BP_DistrictStreamLoader"
PARENT_PATH = "/Script/ThirdPerson.DistrictStreamLoaderBase"


def main() -> None:
    observed = {
        str(value).split(".", 1)[0]
        for value in unreal.EditorAssetLibrary.list_assets(
            ASSET_DIR, recursive=True, include_folder=False
        )
    }
    if observed != {ASSET_PATH}:
        raise RuntimeError("DISTRICT_SCAFFOLD_INVENTORY %r" % sorted(observed))
    blueprint = unreal.EditorAssetLibrary.load_asset(ASSET_PATH)
    parent = unreal.BlueprintEditorLibrary.get_blueprint_parent_class(blueprint)
    if parent is None or parent.get_path_name() != PARENT_PATH:
        raise RuntimeError("DISTRICT_SCAFFOLD_PARENT %r" % parent)
    unreal.log("DISTRICT-STREAMING-SCAFFOLD-READBACK PASS assets=1 parent=direct")
    print("DISTRICT-STREAMING-SCAFFOLD-READBACK PASS assets=1 parent=direct")


main()
