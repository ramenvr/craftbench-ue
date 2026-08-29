"""Fresh-process, read-only exact graph/L2I reference readback."""
from __future__ import annotations

import os
import re
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reference_contract import immutable_vector, snapshot  # noqa: E402


ASSET = (
    "/Game/Tasks/t3-only-the-requested-district-enters-and-leaves-the-world/"
    "BP_DistrictStreamLoader")
HASH_ENV = "CRAFTBENCH_DISTRICT_REFERENCE_SHA256"
REFERENCE = re.compile(
    r"^PASS DISTRICT_REFERENCE_GRAPH l2i=5 identity=1 nodes=10 "
    r"request_soft_world=1 engine_load_level_instance=1 active_store=1 "
    r"exact_active_unload=1 hardcoded_world=0$")


def fail(message: str) -> None:
    rendered = "DISTRICT-REFERENCE-COLD-READBACK-ERROR " + message
    unreal.log_error(rendered)
    print(rendered, flush=True)
    raise RuntimeError(message)


def main() -> None:
    expected = os.environ.get(HASH_ENV, "").strip().upper()
    if len(expected) != 64 or any(c not in "0123456789ABCDEF" for c in expected):
        fail("missing or malformed " + HASH_ENV)
    before = snapshot(expected_loader_hash=expected)
    blueprint = unreal.EditorAssetLibrary.load_asset(ASSET)
    helper = getattr(unreal, "DistrictStreamingReferenceAuthoring", None)
    inspect = getattr(helper, "inspect_reference_graph", None)
    if blueprint is None or inspect is None:
        fail("exact loader or compiled native helper unavailable")
    result = str(inspect(blueprint))
    if REFERENCE.fullmatch(result) is None:
        fail("fixed L2I failed: " + result)
    after = snapshot(expected_loader_hash=expected)
    if after["loader"] != before["loader"] or \
            immutable_vector(after) != immutable_vector(before):
        fail("read-only inspection changed protected bytes")
    marker = (
        "DISTRICT-REFERENCE-COLD-READBACK-PASS l2i=5 graph_exact=1 "
        "nodes=10 request_soft_world=1 exact_active_unload=1 "
        "hardcoded_world=0 hashes_unchanged=1 no_reparse=1 "
        "reference_sha256=%s" % expected)
    unreal.log(marker)
    print(marker, flush=True)


if __name__ == "__main__":
    main()
