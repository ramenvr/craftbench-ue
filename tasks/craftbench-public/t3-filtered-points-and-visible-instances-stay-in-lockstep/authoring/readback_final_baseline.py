"""Fresh-process readback of the answer-free production PCG graph."""

from __future__ import annotations

from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pcg_task_common import (  # noqa: E402
    BASELINE_VECTOR, FINAL_GRAPH, FINAL_MAP_FILE, REFERENCE,
    admission_graph_vector, admission_map_vector, assert_absent,
    final_graph_vector, immutable_vector,
)


def fail(message: str) -> None:
    unreal.log_error("FILTERED-POINT-FINAL-BASELINE-READBACK-FAILED: " + message)
    raise RuntimeError(message)


def main() -> None:
    assert_absent(FINAL_MAP_FILE, REFERENCE)
    before = {
        "baseline": final_graph_vector(),
        "admission_graph": admission_graph_vector(),
        "admission_map": admission_map_vector(),
        "immutable": immutable_vector(),
    }
    graph = unreal.EditorAssetLibrary.load_asset(FINAL_GRAPH)
    helper = getattr(unreal, "FilteredPointInstancesAssetAuthoring", None)
    if graph is None or helper is None:
        fail("graph/helper unavailable")
    detail = helper.inspect_baseline_graph(graph)
    if type(detail) is not str or detail != BASELINE_VECTOR:
        fail("cold baseline vector mismatch: %r" % detail)
    after = {
        "baseline": final_graph_vector(),
        "admission_graph": admission_graph_vector(),
        "admission_map": admission_map_vector(),
        "immutable": immutable_vector(),
    }
    if after != before:
        fail("cold readback changed protected hashes")
    marker = (
        "FILTERED-POINT-FINAL-BASELINE-READBACK-PASS assets=1 "
        "baseline_empty=1 nodes=1 filters=0 spawner=0 hashes_unchanged=1"
    )
    unreal.log(marker)
    print(marker, flush=True)


main()
