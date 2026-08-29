"""Fresh-process readback after restoring the exact empty live baseline."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contract


BASELINE = re.compile(
    r"^PASS CONTROLLER reference=0 nodes=[0-9]+ links=0 event=0 manager=0 "
    r"layers=0 array_get=0 move=0 request_reads=0$")
BASELINE_SHA = contract.EXPECTED_FINAL_ASSET_HASHES[
    "UE-projects/ThirdPerson/Content/Tasks/"
    "t3-only-the-near-active-sector-exists/BP_NearActiveSectorController.uasset"]


def fail(message: str) -> None:
    unreal.log_error("NEAR-ACTIVE-SECTOR-BASELINE-READBACK-FAILED " + message)
    raise RuntimeError(message)


def main() -> None:
    try:
        immutable_before = contract.immutable_snapshot()
        contract.controller_hash(BASELINE_SHA)
        inspected = unreal.NearActiveSectorAssetAuthoring.inspect_controller(False)
        if type(inspected) is not str or BASELINE.fullmatch(inspected) is None:
            fail("cold baseline vector mismatch: %r" % inspected)
        contract.controller_hash(BASELINE_SHA)
        if contract.immutable_snapshot() != immutable_before:
            fail("immutable source/map/support hashes changed")
        marker = (
            "NEAR-ACTIVE-SECTOR-BASELINE-COLD-READBACK-PASS empty=1 "
            "links=0 hashes_unchanged=1 baseline_sha256=%s" % BASELINE_SHA)
        unreal.log(marker)
        print(marker)
    except Exception as exc:
        if not isinstance(exc, RuntimeError):
            fail(str(exc))
        raise


main()
