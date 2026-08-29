"""Author final Data Layers and the exact empty editable controller once."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contract


CREATE_BASELINE = re.compile(
    r"^PASS BASELINE asset=/Game/Tasks/t3-only-the-near-active-sector-exists/"
    r"BP_NearActiveSectorController\.BP_NearActiveSectorController "
    r"parent=/Script/ThirdPerson\.NearActiveSectorControllerBase graphs=[0-9]+$")
INSPECT_BASELINE = re.compile(
    r"^PASS CONTROLLER reference=0 nodes=[0-9]+ links=0 event=0 manager=0 "
    r"layers=0 array_get=0 move=0 request_reads=0$")


def fail(message: str) -> None:
    unreal.log_error("NEAR-ACTIVE-SECTOR-FINAL-ASSET-AUTHOR-FAILED " + message)
    raise RuntimeError(message)


def main() -> None:
    try:
        contract.require_admission_frozen()
        contract.require_reference_absent()
        for path in (contract.FINAL_ROOT, contract.TASK_ASSET_ROOT,
                     contract.FINAL_EXTERNAL_ACTORS,
                     contract.FINAL_EXTERNAL_OBJECTS):
            if os.path.lexists(path):
                fail("final output namespace is not fresh: %s" % path)
        protected_before = contract.protected_vector()
        created_layers = unreal.NearActiveSectorAssetAuthoring.create_data_layer_assets(
            False)
        expected_layers = (
            "PASS DATA_LAYERS mode=final exact=2 runtime=2 "
            "a=/Game/Maps/%s/Support/DL_SectorA.DL_SectorA "
            "b=/Game/Maps/%s/Support/DL_SectorB.DL_SectorB" %
            (contract.TASK_ID, contract.TASK_ID))
        if type(created_layers) is not str or created_layers != expected_layers:
            fail("native layer vector mismatch: %r" % created_layers)
        created_controller = \
            unreal.NearActiveSectorAssetAuthoring.create_baseline_controller()
        if type(created_controller) is not str \
                or CREATE_BASELINE.fullmatch(created_controller) is None:
            fail("native baseline vector mismatch: %r" % created_controller)
        inspected_layers = \
            unreal.NearActiveSectorAssetAuthoring.inspect_data_layer_assets(False)
        expected_readback = (
            "PASS DATA_LAYER_READBACK mode=final exact=2 runtime=2 "
            "filter_none=2 a=/Game/Maps/%s/Support/DL_SectorA.DL_SectorA "
            "b=/Game/Maps/%s/Support/DL_SectorB.DL_SectorB" %
            (contract.TASK_ID, contract.TASK_ID))
        if type(inspected_layers) is not str \
                or inspected_layers != expected_readback:
            fail("native layer readback mismatch: %r" % inspected_layers)
        inspected_controller = \
            unreal.NearActiveSectorAssetAuthoring.inspect_controller(False)
        if type(inspected_controller) is not str \
                or INSPECT_BASELINE.fullmatch(inspected_controller) is None:
            fail("native baseline readback mismatch: %r" % inspected_controller)
        vector = contract.file_vector(contract.final_asset_files())
        if len(vector) != 3:
            fail("final asset count mismatch: %d" % len(vector))
        if contract.protected_vector() != protected_before:
            fail("protected source/config hashes changed")
        contract.require_admission_frozen()
        contract.require_reference_absent()
        marker = (
            "NEAR-ACTIVE-SECTOR-FINAL-ASSETS-SAVED assets=3 layers=2 "
            "controller=1 baseline_empty=1 manifest_sha256=%s hashes=%s" %
            (contract.manifest_sha(vector),
             ",".join(value[1] for _, value in sorted(vector.items()))))
        unreal.log(marker)
        print(marker)
    except Exception as exc:
        if not isinstance(exc, RuntimeError):
            fail(str(exc))
        raise


main()
