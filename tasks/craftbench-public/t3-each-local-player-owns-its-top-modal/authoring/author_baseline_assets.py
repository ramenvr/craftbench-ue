"""Create exactly two untouched editable Widget Blueprint assets."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import production_contract as contract


def fail(message: str) -> None:
    unreal.log_error("LOCAL-PLAYER-MODAL-BASELINE-AUTHOR-ERROR " + message)
    raise RuntimeError(message)


def main() -> None:
    if os.path.lexists(contract.TASK_ROOT):
        fail("task asset namespace is not fresh")
    if os.path.lexists(contract.FINAL_MAP):
        fail("final map already exists")
    contract.require_reference_absent()
    if not unreal.LocalPlayerModalAssetAuthoring.create_baseline_assets():
        fail("native baseline author failed")
    if not unreal.LocalPlayerModalAssetAuthoring.validate_baseline_assets():
        fail("same-process baseline readback failed")
    assets = contract.asset_vector()
    marker = (
        "LOCAL-PLAYER-MODAL-BASELINE-AUTHOR-PASS assets=2 behavior=0 "
        "root_stack=1 focus_buttons=2 hashes=%s" %
        ",".join(item["sha256"] for item in assets.values()))
    unreal.log(marker)
    print(marker)


main()
