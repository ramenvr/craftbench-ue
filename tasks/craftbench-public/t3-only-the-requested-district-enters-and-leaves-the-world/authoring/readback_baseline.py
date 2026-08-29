"""Fresh-process readback after byte-for-byte baseline restoration."""
from __future__ import annotations

import os
import re
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reference_contract import BASELINE_SHA256, immutable_vector, snapshot  # noqa: E402


ASSET = (
    "/Game/Tasks/t3-only-the-requested-district-enters-and-leaves-the-world/"
    "BP_DistrictStreamLoader")
EMPTY = re.compile(
    r"^PASS DISTRICT_EMPTY_BASELINE identity=1 behavior_nodes=0 "
    r"links=0 total_nodes=[0-9]+$")


def fail(message: str) -> None:
    rendered = "DISTRICT-BASELINE-COLD-READBACK-ERROR " + message
    unreal.log_error(rendered)
    print(rendered, flush=True)
    raise RuntimeError(message)


def main() -> None:
    before = snapshot(expected_loader_hash=BASELINE_SHA256)
    blueprint = unreal.EditorAssetLibrary.load_asset(ASSET)
    helper = getattr(unreal, "DistrictStreamingReferenceAuthoring", None)
    inspect = getattr(helper, "inspect_empty_baseline", None)
    if blueprint is None or inspect is None:
        fail("exact loader or compiled native helper unavailable")
    result = str(inspect(blueprint))
    if EMPTY.fullmatch(result) is None:
        fail("restored baseline graph gate failed: " + result)
    after = snapshot(expected_loader_hash=BASELINE_SHA256)
    if after["loader"] != before["loader"] or \
            immutable_vector(after) != immutable_vector(before):
        fail("baseline readback changed protected bytes")
    marker = (
        "DISTRICT-BASELINE-COLD-READBACK-PASS graph_empty=1 "
        "hashes_unchanged=1 no_reparse=1 baseline_sha256=%s" %
        BASELINE_SHA256)
    unreal.log(marker)
    print(marker, flush=True)


if __name__ == "__main__":
    main()
