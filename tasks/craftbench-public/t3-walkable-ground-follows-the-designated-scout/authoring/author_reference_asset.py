"""Author the correct designated-scout Blueprint in an absent live namespace."""

import os
from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from walkable_ground_final_common import (  # noqa: E402
    FINAL_ASSET, FINAL_DIR, REFERENCE, final_vector, immutable_vector,
)

SUCCESS = (
    "PASS class_exact=1 compile_exact=1 owner_exact=1 component_count=1 "
    "radii_valid=1 generation=1600.0 removal=2200.0 graph_nodes=0")


def fail(message):
    unreal.log_error("WALKABLE-GROUND-REFERENCE-AUTHOR-FAILED: " + message)
    raise RuntimeError(message)


def exact(value, expected, name):
    if type(value) is not str or value != expected:
        fail("%s contract mismatch expected=%r actual=%r" %
             (name, expected, value))


def main():
    if os.path.lexists(FINAL_DIR) or os.path.lexists(REFERENCE):
        fail("live final namespace and reference must be absent")
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
        blueprint, True, 1600.0, 2200.0), SUCCESS,
        "configure_designated_scout_blueprint")
    exact(helper.inspect_designated_scout_blueprint(blueprint), SUCCESS,
          "inspect_designated_scout_blueprint")
    hashes = final_vector()
    if immutable_vector() != before:
        fail("immutable artifacts changed")
    marker = ("WALKABLE-GROUND-REFERENCE-AUTHOR-PASS assets=1 "
              "component_count=1 generation=1600.0 removal=2200.0 "
              "graph_nodes=0 hashes=%r" % hashes)
    unreal.log(marker)
    print(marker, flush=True)


main()
