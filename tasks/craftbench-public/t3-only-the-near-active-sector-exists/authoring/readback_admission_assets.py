"""Fresh-process, read-only admission Data Layer cold readback."""

from __future__ import annotations

import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contract


def fail(message: str) -> None:
    unreal.log_error("NEAR-ACTIVE-SECTOR-ASSET-READBACK-FAILED " + message)
    raise RuntimeError(message)


def main() -> None:
    try:
        contract.require_production_absent()
        before = contract.file_vector(contract.layer_files())
        if not contract.EXPECTED_LAYER_HASHES:
            fail("frozen expected layer hashes are not populated")
        actual_hashes = {key: value[1] for key, value in before.items()}
        if actual_hashes != contract.EXPECTED_LAYER_HASHES:
            fail("frozen layer hashes mismatch: %r" % actual_hashes)
        protected_before = contract.protected_vector()
        expected = (
            "PASS DATA_LAYER_READBACK mode=admission exact=2 runtime=2 "
            "filter_none=2 a=/Game/__CraftBenchAdmission/%s/"
            "DL_SectorA.DL_SectorA b=/Game/__CraftBenchAdmission/%s/"
            "DL_SectorB.DL_SectorB" % (contract.TASK_ID, contract.TASK_ID))
        inspected = unreal.NearActiveSectorAssetAuthoring.inspect_data_layer_assets(
            True)
        if type(inspected) is not str or inspected != expected:
            fail("native vector mismatch: %r" % inspected)
        if contract.file_vector(contract.layer_files()) != before:
            fail("admission layer hashes changed during readback")
        if contract.protected_vector() != protected_before:
            fail("protected source/config hashes changed")
        contract.require_production_absent()
        marker = (
            "NEAR-ACTIVE-SECTOR-ASSET-COLD-READBACK-PASS assets=2 "
            "runtime=2 filter_none=2 hashes_unchanged=1 no_reparse=1")
        unreal.log(marker)
        print(marker)
    except Exception as exc:
        if not isinstance(exc, RuntimeError):
            fail(str(exc))
        raise


main()
