"""Author the two protected soft records, and nothing else."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from epoch_travel_common import (  # noqa: E402
    MAP_ROOT, NEW_ASSET, NEW_MAP, NEW_RECORD, OLD_ASSET, OLD_MAP,
    OLD_RECORD, RECORD_VECTOR, assert_absent, record_vector,
    reference_vector, source_vector,
)


def fail(message: str) -> None:
    unreal.log_error("EPOCH-TRAVEL-ASSET-AUTHOR-FAILED: " + message)
    raise RuntimeError(message)


def main() -> None:
    assert_absent(MAP_ROOT, OLD_ASSET, NEW_ASSET, OLD_MAP, NEW_MAP)
    source_before = source_vector()
    reference_before = reference_vector()
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    for package, name, record_id, value in (
            (OLD_RECORD, "DA_EpochRecord_Old", "OldQuartz", 31),
            (NEW_RECORD, "DA_EpochRecord_New", "NewViolet", 74)):
        package_path = package.rsplit("/", 1)[0]
        factory = unreal.DataAssetFactory()
        factory.set_editor_property("data_asset_class", unreal.EpochAssetRecord)
        asset = tools.create_asset(name, package_path, unreal.EpochAssetRecord,
                                   factory)
        if asset is None:
            fail("create_asset failed: " + package)
        asset.set_editor_property("record_id", unreal.Name(record_id))
        asset.set_editor_property("record_value", value)
        if not unreal.EditorAssetLibrary.save_loaded_asset(asset, False):
            fail("save_loaded_asset failed: " + package)
    helper = getattr(unreal, "EpochTravelAssetAuthoring", None)
    detail = helper.inspect_records() if helper else None
    if type(detail) is not str or detail != RECORD_VECTOR:
        fail("same-process record contract mismatch: %r" % detail)
    hashes = record_vector()
    if source_vector() != source_before or reference_vector() != reference_before:
        fail("source/reference changed")
    if os.path.lexists(OLD_MAP) or os.path.lexists(NEW_MAP):
        fail("map appeared during asset authoring")
    marker = "EPOCH-TRAVEL-ASSETS-SAVED records=2 exact=1 hashes=%r" % hashes
    unreal.log(marker)
    print(marker, flush=True)


main()
