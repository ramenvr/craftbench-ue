"""One-shot UE author leg used only by close_reference.py."""

from __future__ import annotations

from pathlib import Path
import os
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pcg_task_common import (  # noqa: E402
    FINAL_GRAPH, FINAL_GRAPH_ROOT, REFERENCE, SOLVED_VECTOR,
    admission_graph_vector, admission_map_vector, final_graph_vector,
    final_map_vector, immutable_vector,
)


def fail(message: str) -> None:
    unreal.log_error("FILTERED-POINT-REFERENCE-AUTHOR-FAILED: " + message)
    raise RuntimeError(message)


def protected() -> dict[str, object]:
    return {
        "admission_graph": admission_graph_vector(),
        "admission_map": admission_map_vector(),
        "final_map": final_map_vector(),
        "immutable": immutable_vector(),
    }


def main() -> None:
    if os.path.lexists(FINAL_GRAPH_ROOT) or os.path.lexists(REFERENCE):
        fail("live graph namespace and reference must be absent")
    before = protected()
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
    detail = helper.configure_graph(graph, True)
    if type(detail) is not str or detail != SOLVED_VECTOR:
        fail("configure solved vector mismatch: %r" % detail)
    if not unreal.EditorAssetLibrary.save_asset(
            FINAL_GRAPH, only_if_is_dirty=False):
        fail("save_asset failed")
    readback = helper.inspect_solved_graph(graph)
    if type(readback) is not str or readback != SOLVED_VECTOR:
        fail("same-process solved vector mismatch: %r" % readback)
    hashes = final_graph_vector()
    if protected() != before or os.path.lexists(REFERENCE):
        fail("reference author changed protected packages")
    marker = (
        "FILTERED-POINT-REFERENCE-AUTHOR-PASS assets=1 l2i=3 "
        "solved=1 protected_hashes_unchanged=1 hashes=%r" % hashes
    )
    unreal.log(marker)
    print(marker, flush=True)


main()
