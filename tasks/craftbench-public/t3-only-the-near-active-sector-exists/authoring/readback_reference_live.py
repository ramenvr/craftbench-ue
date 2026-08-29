"""Fresh-process readback for the temporarily live reference controller."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contract


REFERENCE = re.compile(
    r"^PASS CONTROLLER reference=1 nodes=[0-9]+ links=([3-9][0-9]|[1-9][0-9]{2,}) "
    r"event=1 manager=1 layers=3 array_get=2 move=1 request_reads=4$")


def fail(message: str) -> None:
    unreal.log_error("NEAR-ACTIVE-SECTOR-REFERENCE-READBACK-FAILED " + message)
    raise RuntimeError(message)


def main() -> None:
    try:
        expected_hash = os.environ.get("CRAFTBENCH_NEAR_SECTOR_REFERENCE_SHA256", "")
        if not re.fullmatch(r"[0-9A-F]{64}", expected_hash):
            fail("expected reference hash missing/invalid")
        contract.require_reference_absent()
        immutable_before = contract.immutable_snapshot()
        contract.controller_hash(expected_hash)
        inspected = unreal.NearActiveSectorAssetAuthoring.inspect_controller(True)
        if type(inspected) is not str or REFERENCE.fullmatch(inspected) is None:
            fail("cold reference vector mismatch: %r" % inspected)
        if contract.controller_hash(expected_hash) != expected_hash:
            fail("reference hash changed during readback")
        if contract.immutable_snapshot() != immutable_before:
            fail("immutable source/map/support hashes changed")
        contract.require_reference_absent()
        marker = (
            "NEAR-ACTIVE-SECTOR-REFERENCE-COLD-READBACK-PASS l2i=3 "
            "graph_exact=1 runtime_layer_selection=1 placed_source_move=1 "
            "substitutes=0 hashes_unchanged=1 reference_sha256=%s" %
            expected_hash)
        unreal.log(marker)
        print(marker)
    except Exception as exc:
        if not isinstance(exc, RuntimeError):
            fail(str(exc))
        raise


main()
