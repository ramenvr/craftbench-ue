"""Author only the verifier-owned solved PCG admission graph."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import unreal


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pcg_task_common import (  # noqa: E402
    ADMISSION_GRAPH, ADMISSION_GRAPH_FILE, ADMISSION_ROOT,
    FINAL_GRAPH_ROOT, FINAL_MAP_FILE, REFERENCE, SOLVED_VECTOR,
    admission_graph_vector, assert_absent, immutable_vector,
)


def fail(message: str) -> None:
    unreal.log_error("FILTERED-POINT-ADMISSION-GRAPH-FAILED: " + message)
    raise RuntimeError(message)


def main() -> None:
    assert_absent(ADMISSION_ROOT, FINAL_GRAPH_ROOT, FINAL_MAP_FILE, REFERENCE)
    before = immutable_vector()
    helper = getattr(unreal, "FilteredPointInstancesAssetAuthoring", None)
    factory_type = getattr(unreal, "PCGGraphFactory", None)
    graph_type = getattr(unreal, "PCGGraph", None)
    if helper is None or factory_type is None or graph_type is None:
        fail("native helper/PCG graph factory unavailable")
    graph = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "PCG_FilteredPointInstances_Admission",
        "/Game/__CraftBenchAdmission/"
        "t3-filtered-points-and-visible-instances-stay-in-lockstep",
        graph_type, factory_type())
    if graph is None:
        fail("PCGGraphFactory returned None")
    detail = helper.configure_graph(graph, True)
    if type(detail) is not str or detail != SOLVED_VECTOR:
        fail("configure solved vector mismatch: %r" % detail)
    if not unreal.EditorAssetLibrary.save_asset(
            ADMISSION_GRAPH, only_if_is_dirty=False):
        fail("save_asset failed")
    readback = helper.inspect_solved_graph(graph)
    if type(readback) is not str or readback != SOLVED_VECTOR:
        fail("same-process solved vector mismatch: %r" % readback)
    hashes = admission_graph_vector()
    if immutable_vector() != before:
        fail("immutable source/stock vector changed")
    marker = (
        "FILTERED-POINT-ADMISSION-GRAPH-SAVED assets=1 solved=1 nodes=6 "
        "dual_filter=1 shared_branch=1 spawner=1 graph_output=1 "
        "hashes=%r" % hashes
    )
    unreal.log(marker)
    print(marker, flush=True)


main()
