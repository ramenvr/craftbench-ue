"""One-shot UE author leg; invoked only by close_reference.py."""
from __future__ import annotations

import os
import re
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reference_contract import (  # noqa: E402
    BASELINE_SHA256, LOADER_FILE, immutable_vector, sha256, snapshot)


ASSET = (
    "/Game/Tasks/t3-only-the-requested-district-enters-and-leaves-the-world/"
    "BP_DistrictStreamLoader")
EMPTY = re.compile(
    r"^PASS DISTRICT_EMPTY_BASELINE identity=1 behavior_nodes=0 "
    r"links=0 total_nodes=[0-9]+$")
REFERENCE = re.compile(
    r"^PASS DISTRICT_REFERENCE_GRAPH l2i=5 identity=1 nodes=10 "
    r"request_soft_world=1 engine_load_level_instance=1 active_store=1 "
    r"exact_active_unload=1 hardcoded_world=0$")


def fail(message: str) -> None:
    rendered = "DISTRICT-REFERENCE-AUTHOR-ERROR " + message
    unreal.log_error(rendered)
    print(rendered, flush=True)
    raise RuntimeError(message)


def main() -> None:
    before = snapshot(expected_loader_hash=BASELINE_SHA256)
    blueprint = unreal.EditorAssetLibrary.load_asset(ASSET)
    helper = getattr(unreal, "DistrictStreamingReferenceAuthoring", None)
    inspect_empty = getattr(helper, "inspect_empty_baseline", None)
    author = getattr(helper, "author_reference_graph", None)
    inspect_reference = getattr(helper, "inspect_reference_graph", None)
    if blueprint is None or inspect_empty is None or author is None or \
            inspect_reference is None:
        fail("exact loader or compiled native helper unavailable")
    empty = str(inspect_empty(blueprint))
    if EMPTY.fullmatch(empty) is None:
        fail("baseline graph gate failed: " + empty)
    authored = str(author(blueprint))
    if not authored.startswith("PASS DISTRICT_REFERENCE_AUTHORED "):
        fail("native author failed: " + authored)
    reference = str(inspect_reference(blueprint))
    if REFERENCE.fullmatch(reference) is None:
        fail("same-process fixed L2I failed: " + reference)
    reference_hash = sha256(LOADER_FILE)
    if reference_hash == BASELINE_SHA256:
        fail("reference bytes equal baseline")
    after = snapshot(expected_loader_hash=reference_hash)
    if immutable_vector(after) != immutable_vector(before):
        fail("author changed protected section/admission/final vector")
    marker = (
        "DISTRICT-REFERENCE-AUTHOR-PASS l2i=5 graph_exact=1 nodes=10 "
        "request_soft_world=1 hardcoded_world=0 hashes_unchanged=1 "
        "reference_sha256=%s" % reference_hash)
    unreal.log(marker)
    print(marker, flush=True)


if __name__ == "__main__":
    main()
