"""Create the exact empty, editable designated-scout Blueprint once."""

import os
from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from walkable_ground_final_common import (  # noqa: E402
    FINAL_ASSET, FINAL_DIR, FINAL_FILE, FINAL_MAP, REFERENCE,
    final_vector, immutable_vector,
)

SHELL_SUCCESS = (
    "PASS baseline_empty=1 class_exact=1 compile_exact=1 component_count=0 "
    "graph_nodes=0 visible=1")


def fail(message):
    unreal.log_error("WALKABLE-GROUND-BASELINE-ASSET-FAILED: " + message)
    raise RuntimeError(message)


def exact(value, expected, name):
    if type(value) is not str or value != expected:
        fail("%s contract mismatch expected=%r actual=%r" %
             (name, expected, value))


def main():
    if os.path.lexists(FINAL_DIR) or unreal.EditorAssetLibrary.does_directory_exist(
            "/Game/Tasks/t3-walkable-ground-follows-the-designated-scout"):
        fail("refusing existing final task namespace")
    if os.path.lexists(FINAL_MAP) or os.path.lexists(REFERENCE):
        fail("final map/reference must remain absent")
    before = immutable_vector()
    parent = unreal.load_class(None, "/Script/ThirdPerson.DesignatedScoutCharacter")
    helper = getattr(unreal, "WalkableGroundAdmissionAuthoring", None)
    if parent is None or helper is None:
        fail("parent/helper unavailable")
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", parent)
    blueprint = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "BP_DesignatedScout", "/Game/Tasks/"
        "t3-walkable-ground-follows-the-designated-scout",
        unreal.Blueprint, factory)
    if blueprint is None:
        fail("BlueprintFactory returned None")
    exact(helper.configure_designated_scout_blueprint(
        blueprint, False, 1600.0, 2200.0), SHELL_SUCCESS,
        "configure_designated_scout_blueprint")
    exact(helper.inspect_designated_scout_blueprint_shell(blueprint),
          SHELL_SUCCESS, "inspect_designated_scout_blueprint_shell")
    if not FINAL_FILE.is_file():
        fail("exact baseline package missing")
    observed = {str(value).split(".", 1)[0] for value in
                unreal.EditorAssetLibrary.list_assets(
                    "/Game/Tasks/t3-walkable-ground-follows-the-designated-scout",
                    recursive=True, include_folder=False)}
    if observed != {FINAL_ASSET}:
        fail("asset registry inventory mismatch: %r" % sorted(observed))
    hashes = final_vector()
    if immutable_vector() != before:
        fail("admission/stock artifacts changed")
    marker = ("WALKABLE-GROUND-BASELINE-ASSET-SAVED assets=1 "
              "baseline_empty=1 component_count=0 graph_nodes=0 visible=1 "
              "immutable_hashes_unchanged=1 hashes=%r" % hashes)
    unreal.log(marker)
    print(marker, flush=True)


main()
