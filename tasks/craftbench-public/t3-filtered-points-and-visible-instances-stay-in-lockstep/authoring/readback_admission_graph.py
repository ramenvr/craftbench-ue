"""Fresh-process readback of the solved PCG admission graph."""

from __future__ import annotations

from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pcg_task_common import (  # noqa: E402
    ADMISSION_GRAPH, FINAL_GRAPH_ROOT, FINAL_MAP_FILE, REFERENCE,
    SOLVED_VECTOR, admission_graph_vector, assert_absent, immutable_vector,
)


def fail(message: str) -> None:
    unreal.log_error("FILTERED-POINT-ADMISSION-GRAPH-READBACK-FAILED: " + message)
    raise RuntimeError(message)


def main() -> None:
    assert_absent(FINAL_GRAPH_ROOT, FINAL_MAP_FILE, REFERENCE)
    before = {"graph": admission_graph_vector(),
              "immutable": immutable_vector()}
    graph = unreal.EditorAssetLibrary.load_asset(ADMISSION_GRAPH)
    helper = getattr(unreal, "FilteredPointInstancesAssetAuthoring", None)
    if graph is None or helper is None:
        fail("graph/helper unavailable")
    detail = helper.inspect_solved_graph(graph)
    if type(detail) is not str or detail != SOLVED_VECTOR:
        fail("cold solved vector mismatch: %r" % detail)
    after = {"graph": admission_graph_vector(),
             "immutable": immutable_vector()}
    if after != before:
        fail("cold readback changed protected hashes")
    marker = (
        "FILTERED-POINT-ADMISSION-GRAPH-READBACK-PASS assets=1 solved=1 "
        "nodes=6 dual_filter=1 shared_branch=1 hashes_unchanged=1"
    )
    unreal.log(marker)
    print(marker, flush=True)


main()
