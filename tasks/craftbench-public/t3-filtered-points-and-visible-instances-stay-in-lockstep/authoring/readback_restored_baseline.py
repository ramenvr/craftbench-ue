"""Fresh-process proof that closure restored the answer-free baseline."""

from __future__ import annotations

from pathlib import Path
import os
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pcg_task_common import (  # noqa: E402
    BASELINE_VECTOR, FINAL_GRAPH, REFERENCE, admission_graph_vector,
    admission_map_vector, final_graph_vector, final_map_vector,
    immutable_vector,
)


def fail(message: str) -> None:
    unreal.log_error("FILTERED-POINT-RESTORED-BASELINE-COLD-FAILED: " + message)
    raise RuntimeError(message)


def snapshot() -> dict[str, object]:
    return {
        "baseline": final_graph_vector(),
        "admission_graph": admission_graph_vector(),
        "admission_map": admission_map_vector(),
        "final_map": final_map_vector(),
        "immutable": immutable_vector(),
    }


def main() -> None:
    if os.path.lexists(REFERENCE):
        fail("reference must remain absent during baseline proof")
    before = snapshot()
    graph = unreal.EditorAssetLibrary.load_asset(FINAL_GRAPH)
    helper = getattr(unreal, "FilteredPointInstancesAssetAuthoring", None)
    if graph is None or helper is None:
        fail("graph/helper unavailable")
    detail = helper.inspect_baseline_graph(graph)
    if type(detail) is not str or detail != BASELINE_VECTOR:
        fail("cold baseline vector mismatch: %r" % detail)
    if snapshot() != before:
        fail("restored baseline readback changed protected packages")
    marker = (
        "FILTERED-POINT-RESTORED-BASELINE-COLD-PASS assets=1 "
        "baseline_empty=1 l2i_fail_closed=1 hashes_unchanged=1 "
        "reference_absent=1"
    )
    unreal.log(marker)
    print(marker, flush=True)


main()
