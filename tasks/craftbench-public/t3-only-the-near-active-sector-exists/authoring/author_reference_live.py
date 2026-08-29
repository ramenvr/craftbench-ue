"""One-shot UE leg that turns the frozen live baseline into the reference."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contract


REFERENCE = re.compile(
    r"^PASS CONTROLLER reference=1 nodes=[0-9]+ links=([3-9][0-9]|[1-9][0-9]{2,}) "
    r"event=1 manager=1 layers=3 array_get=2 move=1 request_reads=4$")
BASELINE = re.compile(
    r"^PASS CONTROLLER reference=0 nodes=[0-9]+ links=0 event=0 manager=0 "
    r"layers=0 array_get=0 move=0 request_reads=0$")
BASELINE_SHA = contract.EXPECTED_FINAL_ASSET_HASHES[
    "UE-projects/ThirdPerson/Content/Tasks/"
    "t3-only-the-near-active-sector-exists/BP_NearActiveSectorController.uasset"]


def fail(message: str) -> None:
    unreal.log_error("NEAR-ACTIVE-SECTOR-REFERENCE-AUTHOR-FAILED " + message)
    raise RuntimeError(message)


def main() -> None:
    try:
        contract.require_reference_absent()
        immutable_before = contract.immutable_snapshot()
        contract.controller_hash(BASELINE_SHA)
        baseline = unreal.NearActiveSectorAssetAuthoring.inspect_controller(False)
        if type(baseline) is not str or BASELINE.fullmatch(baseline) is None:
            fail("baseline entry vector mismatch: %r" % baseline)
        authored = \
            unreal.NearActiveSectorAssetAuthoring.build_reference_controller_graph()
        if type(authored) is not str or REFERENCE.fullmatch(authored) is None:
            fail("reference author vector mismatch: %r" % authored)
        inspected = unreal.NearActiveSectorAssetAuthoring.inspect_controller(True)
        if type(inspected) is not str or inspected != authored:
            fail("same-process reference readback mismatch: %r" % inspected)
        reference_hash = contract.controller_hash()
        if reference_hash == BASELINE_SHA:
            fail("reference bytes equal baseline")
        if contract.immutable_snapshot() != immutable_before:
            fail("immutable source/map/support hashes changed")
        contract.require_reference_absent()
        marker = (
            "NEAR-ACTIVE-SECTOR-REFERENCE-AUTHOR-PASS l2i=3 graph_exact=1 "
            "runtime_layer_selection=1 placed_source_move=1 substitutes=0 "
            "reference_sha256=%s" % reference_hash)
        unreal.log(marker)
        print(marker)
    except Exception as exc:
        if not isinstance(exc, RuntimeError):
            fail(str(exc))
        raise


main()
