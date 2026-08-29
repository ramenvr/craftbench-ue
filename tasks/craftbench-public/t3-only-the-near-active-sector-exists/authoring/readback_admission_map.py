"""Fresh-process, read-only World Partition admission map readback."""

from __future__ import annotations

import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contract


def fail(message: str) -> None:
    unreal.log_error("NEAR-ACTIVE-SECTOR-MAP-READBACK-FAILED " + message)
    raise RuntimeError(message)


def main() -> None:
    try:
        contract.require_production_absent()
        before = contract.file_vector(contract.map_files())
        if contract.EXPECTED_MAP_FILE_COUNT <= 0 \
                or not contract.EXPECTED_MAP_MANIFEST_SHA:
            fail("frozen expected map manifest is not populated")
        if len(before) != contract.EXPECTED_MAP_FILE_COUNT \
                or contract.manifest_sha(before) != \
                contract.EXPECTED_MAP_MANIFEST_SHA:
            fail("frozen map vector mismatch")
        protected_before = contract.protected_vector()
        levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if levels is None or not levels.load_level(contract.MAP_PACKAGE):
            fail("cold load_level failed")
        world = unreal.get_editor_subsystem(
            unreal.UnrealEditorSubsystem).get_editor_world()
        expected = (
            "PASS MAP mode=admission world_partition=1 ofpa=1 source=1 "
            "shape_radius=3200 layers=2 markers=4 spatial=4 locations=far "
            "controller=1 request=1 fixtures=2")
        inspected = unreal.NearActiveSectorAssetAuthoring.inspect_map(world, True)
        if type(inspected) is not str or inspected != expected:
            fail("native cold map vector mismatch: %r" % inspected)
        after = contract.file_vector(contract.map_files())
        if after != before:
            fail("map/side-package hashes changed during cold readback")
        if contract.protected_vector() != protected_before:
            fail("protected source/config hashes changed")
        contract.require_production_absent()
        marker = (
            "NEAR-ACTIVE-SECTOR-MAP-COLD-READBACK-PASS files=%d "
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
