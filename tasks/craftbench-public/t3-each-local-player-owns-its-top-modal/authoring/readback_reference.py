"""Fresh-process reference graph readback with optional frozen hashes."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import production_contract as contract


def fail(message: str) -> None:
    unreal.log_error("LOCAL-PLAYER-MODAL-REFERENCE-READBACK-ERROR " + message)
    raise RuntimeError(message)


def main() -> None:
    before = contract.asset_vector()
    expected = os.environ.get("CRAFTBENCH_LOCAL_MODAL_REFERENCE_HASHES", "")
    actual_hashes = ",".join(item["sha256"] for item in before.values())
    if expected and expected != actual_hashes:
        fail("entry reference hashes differ from closure lock")
    parsed = json.loads(
        unreal.LocalPlayerModalAssetAuthoring.inspect_submission_assets())
    if len(parsed) != 3 or not all(
            item.get("passed") is True for item in parsed.values()):
        fail("cold reference inspection failed: %r" % parsed)
    if contract.asset_vector() != before:
        fail("reference bytes changed during readback")
    marker = (
        "LOCAL-PLAYER-MODAL-REFERENCE-COLD-READBACK-PASS assets=2 "
        "l2i=3 hashes_unchanged=1")
    unreal.log(marker)
    print(marker)


main()
