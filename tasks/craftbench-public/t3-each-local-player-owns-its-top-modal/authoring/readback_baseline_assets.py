"""Fresh-process, read-only baseline asset validation."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import production_contract as contract


def fail(message: str) -> None:
    unreal.log_error("LOCAL-PLAYER-MODAL-BASELINE-READBACK-ERROR " + message)
    raise RuntimeError(message)


def main() -> None:
    if os.path.lexists(contract.FINAL_MAP):
        fail("final map unexpectedly exists")
    contract.require_reference_absent()
    before = contract.asset_vector()
    if not unreal.LocalPlayerModalAssetAuthoring.validate_baseline_assets():
        fail("native baseline readback failed")
    after = contract.asset_vector()
    if after != before:
        fail("baseline bytes changed during readback")
    marker = (
        "LOCAL-PLAYER-MODAL-BASELINE-COLD-READBACK-PASS assets=2 "
        "behavior=0 hashes_unchanged=1 reference_absent=1")
    unreal.log(marker)
    print(marker)


main()
