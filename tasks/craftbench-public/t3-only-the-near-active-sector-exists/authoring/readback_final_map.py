"""Fresh-process, read-only final World Partition map readback."""

from __future__ import annotations

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
    unreal.log_error("NEAR-ACTIVE-SECTOR-FINAL-MAP-READBACK-FAILED " + message)
    raise RuntimeError(message)


def main() -> None:
    try:
        contract.require_admission_frozen()
        contract.require_reference_absent()
        assets_before = contract.file_vector(
            contract.final_asset_files(allow_map=True))
        actual_asset_hashes = {
            key: value[1] for key, value in assets_before.items()}
        if not contract.EXPECTED_FINAL_ASSET_HASHES \
                or actual_asset_hashes != contract.EXPECTED_FINAL_ASSET_HASHES:
            fail("frozen final asset hashes mismatch")
        before = contract.file_vector(contract.final_map_files())
        if contract.EXPECTED_FINAL_MAP_FILE_COUNT <= 0 \
                or not contract.EXPECTED_FINAL_MAP_MANIFEST_SHA:
            fail("frozen final map manifest is not populated")
        if len(before) != contract.EXPECTED_FINAL_MAP_FILE_COUNT \
                or contract.manifest_sha(before) != \
                contract.EXPECTED_FINAL_MAP_MANIFEST_SHA:
            fail("frozen final map vector mismatch")
        protected_before = contract.protected_vector()
        levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if levels is None or not levels.load_level(contract.FINAL_MAP_PACKAGE):
            fail("cold load_level failed")
        world = unreal.get_editor_subsystem(
            unreal.UnrealEditorSubsystem).get_editor_world()
        inspected = unreal.NearActiveSectorAssetAuthoring.inspect_map(world, False)
        if type(inspected) is not str or inspected != EXPECTED_MAP:
            fail("native cold map vector mismatch: %r" % inspected)
        if contract.file_vector(contract.final_map_files()) != before:
            fail("final map packages changed during readback")
        if contract.file_vector(
                contract.final_asset_files(allow_map=True)) != assets_before:
            fail("final support/controller hashes changed")
        if contract.protected_vector() != protected_before:
            fail("protected source/config hashes changed")
        contract.require_admission_frozen()
        contract.require_reference_absent()
        marker = (
            "NEAR-ACTIVE-SECTOR-FINAL-MAP-COLD-READBACK-PASS files=%d "
            "manifest_sha256=%s world_partition=1 ofpa=1 source=1 layers=2 "
            "markers=4 spatial=4 locations=far fixtures=2 hashes_unchanged=1 "
            "runtime_observed=0" %
            (len(before), contract.manifest_sha(before)))
        unreal.log(marker)
        print(marker)
    except Exception as exc:
        if not isinstance(exc, RuntimeError):
            fail(str(exc))
        raise


main()
