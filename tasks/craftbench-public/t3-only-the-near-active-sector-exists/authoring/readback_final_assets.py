"""Fresh-process, read-only final support/controller cold readback."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contract


INSPECT_BASELINE = re.compile(
    r"^PASS CONTROLLER reference=0 nodes=[0-9]+ links=0 event=0 manager=0 "
    r"layers=0 array_get=0 move=0 request_reads=0$")


def fail(message: str) -> None:
    unreal.log_error("NEAR-ACTIVE-SECTOR-FINAL-ASSET-READBACK-FAILED " + message)
    raise RuntimeError(message)


def main() -> None:
    try:
        contract.require_admission_frozen()
        contract.require_reference_absent()
        before = contract.file_vector(contract.final_asset_files())
        actual_hashes = {key: value[1] for key, value in before.items()}
        if not contract.EXPECTED_FINAL_ASSET_HASHES \
                or actual_hashes != contract.EXPECTED_FINAL_ASSET_HASHES:
            fail("frozen final asset hashes mismatch: %r" % actual_hashes)
        protected_before = contract.protected_vector()
        expected_layers = (
            "PASS DATA_LAYER_READBACK mode=final exact=2 runtime=2 "
            "filter_none=2 a=/Game/Maps/%s/Support/DL_SectorA.DL_SectorA "
            "b=/Game/Maps/%s/Support/DL_SectorB.DL_SectorB" %
            (contract.TASK_ID, contract.TASK_ID))
        layers = unreal.NearActiveSectorAssetAuthoring.inspect_data_layer_assets(
            False)
        controller = unreal.NearActiveSectorAssetAuthoring.inspect_controller(False)
        if type(layers) is not str or layers != expected_layers:
            fail("native layer vector mismatch: %r" % layers)
        if type(controller) is not str \
                or INSPECT_BASELINE.fullmatch(controller) is None:
            fail("native baseline vector mismatch: %r" % controller)
        if contract.file_vector(contract.final_asset_files()) != before:
            fail("final assets changed during cold readback")
        if contract.protected_vector() != protected_before:
            fail("protected source/config hashes changed")
        contract.require_admission_frozen()
        contract.require_reference_absent()
        marker = (
            "NEAR-ACTIVE-SECTOR-FINAL-ASSET-COLD-READBACK-PASS assets=3 "
            "layers=2 controller=1 baseline_empty=1 hashes_unchanged=1 "
            "no_reparse=1")
        unreal.log(marker)
        print(marker)
    except Exception as exc:
        if not isinstance(exc, RuntimeError):
            fail(str(exc))
        raise


main()
