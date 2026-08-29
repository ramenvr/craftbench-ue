"""Author the isolated World Partition admission map exactly once."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contract


def fail(message: str) -> None:
    unreal.log_error("NEAR-ACTIVE-SECTOR-MAP-AUTHOR-FAILED " + message)
    raise RuntimeError(message)


def main() -> None:
    try:
        contract.require_production_absent()
        layer_before = contract.file_vector(contract.layer_files())
        actual_layer_hashes = {key: value[1] for key, value in layer_before.items()}
        if not contract.EXPECTED_LAYER_HASHES \
                or actual_layer_hashes != contract.EXPECTED_LAYER_HASHES:
            fail("frozen admission layer hashes mismatch")
        if os.path.lexists(contract.MAP_FILE) \
                or os.path.lexists(contract.HLOD_FILE) \
                or os.path.lexists(contract.EXTERNAL_ACTORS) \
                or os.path.lexists(contract.EXTERNAL_OBJECTS) \
                or unreal.EditorAssetLibrary.does_asset_exist(contract.MAP_PACKAGE):
            fail("map or side-package namespace is not fresh")
        protected_before = contract.protected_vector()
        levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if levels is None or not levels.new_level_from_template(
                contract.MAP_PACKAGE, "/Engine/Maps/Templates/OpenWorld"):
            fail("new World Partition level from OpenWorld failed")
        world = unreal.get_editor_subsystem(
            unreal.UnrealEditorSubsystem).get_editor_world()
        configured = unreal.NearActiveSectorAssetAuthoring.configure_map(
            world, True)
        expected = (
            "PASS MAP mode=admission world_partition=1 ofpa=1 source=1 "
            "shape_radius=3200 layers=2 markers=4 spatial=4 locations=far "
            "controller=1 request=1 fixtures=2")
        if type(configured) is not str or configured != expected:
            fail("native configure vector mismatch: %r" % configured)
        if not levels.save_current_level():
            fail("save_current_level failed")
        inspected = unreal.NearActiveSectorAssetAuthoring.inspect_map(world, True)
        if type(inspected) is not str or inspected != expected:
            fail("same-process map readback mismatch: %r" % inspected)
        output = contract.file_vector(contract.map_files())
        if contract.file_vector(contract.layer_files(allow_map=True)) != layer_before:
            fail("admission layer hashes changed")
        if contract.protected_vector() != protected_before:
            fail("protected source/config hashes changed")
        contract.require_production_absent()
        marker = (
            "NEAR-ACTIVE-SECTOR-ADMISSION-MAP-SAVED map=%s files=%d "
            "manifest_sha256=%s world_partition=1 ofpa=1 layers=2 markers=4 "
            "spatial=4 locations=far fixtures=2 runtime_observed=0" %
            (contract.MAP_PACKAGE, len(output), contract.manifest_sha(output)))
        unreal.log(marker)
        print(marker)
    except Exception as exc:
        if not isinstance(exc, RuntimeError):
            fail(str(exc))
        raise


main()
