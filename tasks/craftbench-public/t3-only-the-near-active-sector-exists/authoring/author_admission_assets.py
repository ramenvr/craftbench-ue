"""Author exactly two isolated admission Data Layer assets."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contract


def fail(message: str) -> None:
    unreal.log_error("NEAR-ACTIVE-SECTOR-ASSET-AUTHOR-FAILED " + message)
    raise RuntimeError(message)


def main() -> None:
    try:
        contract.require_production_absent()
        if any(os.path.lexists(path) for path in (
                contract.ADMISSION_ROOT, contract.EXTERNAL_ACTORS,
                contract.EXTERNAL_OBJECTS)):
            fail("admission output namespace is not fresh")
        protected_before = contract.protected_vector()
        expected_create = (
            "PASS DATA_LAYERS mode=admission exact=2 runtime=2 "
            "a=/Game/__CraftBenchAdmission/%s/DL_SectorA.DL_SectorA "
            "b=/Game/__CraftBenchAdmission/%s/DL_SectorB.DL_SectorB" %
            (contract.TASK_ID, contract.TASK_ID))
        created = unreal.NearActiveSectorAssetAuthoring.create_data_layer_assets(
            True)
        if type(created) is not str or created != expected_create:
            fail("native create vector mismatch: %r" % created)
        expected_readback = (
            "PASS DATA_LAYER_READBACK mode=admission exact=2 runtime=2 "
            "filter_none=2 a=/Game/__CraftBenchAdmission/%s/"
            "DL_SectorA.DL_SectorA b=/Game/__CraftBenchAdmission/%s/"
            "DL_SectorB.DL_SectorB" % (contract.TASK_ID, contract.TASK_ID))
        inspected = unreal.NearActiveSectorAssetAuthoring.inspect_data_layer_assets(
            True)
        if type(inspected) is not str or inspected != expected_readback:
            fail("native readback vector mismatch: %r" % inspected)
        vector = contract.file_vector(contract.layer_files())
        if contract.protected_vector() != protected_before:
            fail("protected source/config hashes changed")
        contract.require_production_absent()
        marker = (
            "NEAR-ACTIVE-SECTOR-ASSETS-SAVED assets=2 runtime=2 "
            "manifest_sha256=%s hashes=%s" %
            (contract.manifest_sha(vector),
             ",".join(value[1] for _, value in sorted(vector.items()))))
        unreal.log(marker)
        print(marker)
    except Exception as exc:
        if not isinstance(exc, RuntimeError):
            fail(str(exc))
        raise


main()
