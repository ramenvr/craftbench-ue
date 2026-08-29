"""Author the final World Partition/OFPA map exactly once."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contract


EXPECTED_MAP = (
    "PASS MAP mode=final world_partition=1 ofpa=1 source=1 "
    "shape_radius=3200 layers=2 markers=4 spatial=4 locations=far "
    "controller=1 request=1 fixtures=2")


def fail(message: str) -> None:
    unreal.log_error("NEAR-ACTIVE-SECTOR-FINAL-MAP-AUTHOR-FAILED " + message)
    raise RuntimeError(message)


def main() -> None:
    try:
        contract.require_admission_frozen()
        contract.require_reference_absent()
        assets_before = contract.file_vector(contract.final_asset_files())
        actual_hashes = {key: value[1] for key, value in assets_before.items()}
        if not contract.EXPECTED_FINAL_ASSET_HASHES \
                or actual_hashes != contract.EXPECTED_FINAL_ASSET_HASHES:
            fail("frozen final asset hashes mismatch")
        for path in (contract.FINAL_MAP, contract.FINAL_HLOD,
                     contract.FINAL_EXTERNAL_ACTORS,
                     contract.FINAL_EXTERNAL_OBJECTS):
            if os.path.lexists(path):
                fail("final map namespace is not fresh: %s" % path)
        if unreal.EditorAssetLibrary.does_asset_exist(contract.FINAL_MAP_PACKAGE):
            fail("final map exists in Asset Registry")
        protected_before = contract.protected_vector()
        levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if levels is None or not levels.new_level_from_template(
                contract.FINAL_MAP_PACKAGE, "/Engine/Maps/Templates/OpenWorld"):
            fail("new World Partition level from OpenWorld failed")
        world = unreal.get_editor_subsystem(
            unreal.UnrealEditorSubsystem).get_editor_world()
        configured = unreal.NearActiveSectorAssetAuthoring.configure_map(
            world, False)
        if type(configured) is not str or configured != EXPECTED_MAP:
            fail("native configure vector mismatch: %r" % configured)
        if not levels.save_current_level():
            fail("save_current_level failed")
        inspected = unreal.NearActiveSectorAssetAuthoring.inspect_map(world, False)
        if type(inspected) is not str or inspected != EXPECTED_MAP:
            fail("same-process map readback mismatch: %r" % inspected)
        output = contract.file_vector(contract.final_map_files())
        if contract.file_vector(contract.final_asset_files(allow_map=True)) != \
                assets_before:
            fail("final assets changed during map author")
        if contract.protected_vector() != protected_before:
            fail("protected source/config hashes changed")
        contract.require_admission_frozen()
        contract.require_reference_absent()
        marker = (
            "NEAR-ACTIVE-SECTOR-FINAL-MAP-SAVED map=%s files=%d "
            "manifest_sha256=%s world_partition=1 ofpa=1 layers=2 markers=4 "
            "spatial=4 locations=far fixtures=2 runtime_observed=0" %
            (contract.FINAL_MAP_PACKAGE, len(output),
             contract.manifest_sha(output)))
        unreal.log(marker)
        print(marker)
    except Exception as exc:
        if not isinstance(exc, RuntimeError):
            fail(str(exc))
        raise


main()
