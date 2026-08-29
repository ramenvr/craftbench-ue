"""Fresh-process readback of the temporary live solved reference graph."""

from __future__ import annotations

from pathlib import Path
import json
import os
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pcg_task_common import (  # noqa: E402
    FINAL_GRAPH, REFERENCE, SOLVED_VECTOR, admission_graph_vector,
    admission_map_vector, final_graph_vector, final_map_vector,
    immutable_vector,
)


def fail(message: str) -> None:
    unreal.log_error("FILTERED-POINT-REFERENCE-COLD-FAILED: " + message)
    raise RuntimeError(message)


def snapshot() -> dict[str, object]:
    return {
        "reference": final_graph_vector(),
        "admission_graph": admission_graph_vector(),
        "admission_map": admission_map_vector(),
        "final_map": final_map_vector(),
        "immutable": immutable_vector(),
    }


def main() -> None:
    try:
        expected = json.loads(os.environ.get(
            "CRAFTBENCH_FILTERED_POINT_REFERENCE_HASHES", ""))
    except Exception as exc:
        fail("reference hash environment invalid: %r" % exc)
    before = snapshot()
    if before["reference"] != expected or os.path.lexists(REFERENCE):
        fail("temporary reference hashes/reference-absence mismatch")
    graph = unreal.EditorAssetLibrary.load_asset(FINAL_GRAPH)
    helper = getattr(unreal, "FilteredPointInstancesAssetAuthoring", None)
    if graph is None or helper is None:
        fail("graph/helper unavailable")
    detail = helper.inspect_solved_graph(graph)
    if type(detail) is not str or detail != SOLVED_VECTOR:
        fail("cold solved vector mismatch: %r" % detail)
    if snapshot() != before or os.path.lexists(REFERENCE):
        fail("cold reference readback changed protected packages")
    marker = (
        "FILTERED-POINT-REFERENCE-COLD-PASS assets=1 l2i=3 solved=1 "
        "hashes_unchanged=1 reference_absent=1"
    )
    unreal.log(marker)
    print(marker, flush=True)


main()
