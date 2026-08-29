"""Author the exact editable, answer-free production PCG graph."""

from __future__ import annotations

from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pcg_task_common import (  # noqa: E402
    ADMISSION_MAP_FILE, BASELINE_VECTOR, FINAL_GRAPH, FINAL_GRAPH_ROOT,
    FINAL_MAP_FILE, REFERENCE, admission_graph_vector, admission_map_vector,
    assert_absent, final_graph_vector, immutable_vector,
)


def fail(message: str) -> None:
    unreal.log_error("FILTERED-POINT-FINAL-BASELINE-FAILED: " + message)
    raise RuntimeError(message)


def main() -> None:
    assert_absent(FINAL_GRAPH_ROOT, FINAL_MAP_FILE, REFERENCE)
    before = {
        "admission_graph": admission_graph_vector(),
        "admission_map": admission_map_vector(),
        "immutable": immutable_vector(),
    }
    helper = getattr(unreal, "FilteredPointInstancesAssetAuthoring", None)
    factory_type = getattr(unreal, "PCGGraphFactory", None)
    graph_type = getattr(unreal, "PCGGraph", None)
    if helper is None or factory_type is None or graph_type is None:
        fail("native helper/PCG graph factory unavailable")
    graph = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "PCG_FilteredPointInstances",
        "/Game/Tasks/t3-filtered-points-and-visible-instances-stay-in-lockstep",
        graph_type, factory_type())
    if graph is None:
        fail("PCGGraphFactory returned None")
    detail = helper.configure_graph(graph, False)
    if type(detail) is not str or detail != BASELINE_VECTOR:
        fail("configure baseline vector mismatch: %r" % detail)
    if not unreal.EditorAssetLibrary.save_asset(
            FINAL_GRAPH, only_if_is_dirty=False):
        fail("save_asset failed")
    readback = helper.inspect_baseline_graph(graph)
    if type(readback) is not str or readback != BASELINE_VECTOR:
        fail("same-process baseline vector mismatch: %r" % readback)
    hashes = final_graph_vector()
    after = {
        "admission_graph": admission_graph_vector(),
        "admission_map": admission_map_vector(),
        "immutable": immutable_vector(),
    }
    if after != before or not ADMISSION_MAP_FILE.is_file():
        fail("protected admission/source vector changed")
    marker = (
        "FILTERED-POINT-FINAL-BASELINE-SAVED assets=1 baseline_empty=1 "
        "nodes=1 filters=0 spawner=0 hashes=%r" % hashes
    )
    unreal.log(marker)
    print(marker, flush=True)


main()
