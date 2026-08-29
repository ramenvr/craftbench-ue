"""Fixed-denominator L2I for the PCG filtered-points task."""

import json
import os

try:
    import unreal
except ImportError:
    unreal = None


START = "CRAFTBENCH-INTROSPECT-JSON-START"
END = "CRAFTBENCH-INTROSPECT-JSON-END"
TASK_ID = "t3-filtered-points-and-visible-instances-stay-in-lockstep"
ROOT = "/Game/Tasks/" + TASK_ID
GRAPH = ROOT + "/PCG_FilteredPointInstances"
CHECK_IDS = (
    "UsesMetadataDrivenDualFilter",
    "PublishesAndSpawnsTheSameFilteredBranch",
    "SubmissionHasNoInstanceSubstitute",
)
EXPECTED_FILES = [
    "Content/Tasks/%s/PCG_FilteredPointInstances.uasset" % TASK_ID,
]


def check(check_id, passed, detail):
    detail = " ".join(str(detail).replace(START, "<START>")
                      .replace(END, "<END>").split())[:900]
    return {"id": check_id, "passed": bool(passed), "detail": detail}


def inspect_graph():
    graph = unreal.EditorAssetLibrary.load_asset(GRAPH)
    helper = getattr(unreal, "FilteredPointInstancesAssetAuthoring", None)
    method = getattr(helper, "inspect_solved_graph", None) if helper else None
    if graph is None or method is None:
        raise RuntimeError("FILTERED_POINT_GRAPH_OR_HELPER_UNAVAILABLE")
    detail = method(graph)
    if type(detail) is not str:
        raise RuntimeError("FILTERED_POINT_HELPER_BAD_SHAPE %r" % detail)
    return detail


def submitted_files():
    raw = os.environ.get("CRAFTBENCH_SUBMITTED_FILES_JSON")
    if raw is None:
        raise RuntimeError("FILTERED_POINT_SUBMISSION_MANIFEST_UNAVAILABLE")
    files = json.loads(raw)
    if not isinstance(files, list) or not all(isinstance(item, str)
                                              for item in files):
        raise RuntimeError("FILTERED_POINT_SUBMISSION_MANIFEST_BAD_SHAPE")
    return sorted({item.replace("\\", "/") for item in files})


def main():
    results = {}
    detail = ""
    if unreal is None:
        results = {gate: check(gate, False, "FILTERED_POINT_NO_UNREAL")
                   for gate in CHECK_IDS}
    else:
        try:
            detail = inspect_graph()
            passed = detail.startswith("PASS ") \
                and "source=1" in detail and "bounds=1" in detail \
                and "density=1" in detail and "exclusion=1" in detail \
                and "parameter=MinDensity" in detail \
                and "metadata=Excluded" in detail
            results[CHECK_IDS[0]] = check(CHECK_IDS[0], passed, detail)
        except Exception as exc:
            results[CHECK_IDS[0]] = check(
                CHECK_IDS[0], False, "FILTERED_POINT_FILTER_READ_ERROR %r" % exc)
        try:
            if not detail:
                detail = inspect_graph()
            passed = detail.startswith("PASS ") \
                and "spawner=1" in detail \
                and "mesh_attribute=Mesh" in detail \
                and "output_branch=1" in detail \
                and "shared_branch=1" in detail
            results[CHECK_IDS[1]] = check(CHECK_IDS[1], passed, detail)
        except Exception as exc:
            results[CHECK_IDS[1]] = check(
                CHECK_IDS[1], False, "FILTERED_POINT_BRANCH_READ_ERROR %r" % exc)
        try:
            files = submitted_files()
            observed = {str(value).split(".", 1)[0] for value in
                        unreal.EditorAssetLibrary.list_assets(
                            ROOT, recursive=True, include_folder=False)}
            passed = files == EXPECTED_FILES and observed == {GRAPH}
            results[CHECK_IDS[2]] = check(
                CHECK_IDS[2], passed,
                "FILTERED_POINT_ASSET_ONLY_BOUNDARY expected_files=%r "
                "actual_files=%r expected_assets=%r actual_assets=%r" %
                (EXPECTED_FILES, files, [GRAPH], sorted(observed)))
        except Exception as exc:
            results[CHECK_IDS[2]] = check(
                CHECK_IDS[2], False, "FILTERED_POINT_BOUNDARY_READ_ERROR %r" % exc)
    ordered = [results.get(gate) or check(
        gate, False, "FILTERED_POINT_CHECK_UNREACHED") for gate in CHECK_IDS]
    payload = json.dumps({"checks": ordered}, separators=(",", ":"))
    print(START)
    print(payload)
    print(END)
    if unreal is not None:
        unreal.log(START)
        unreal.log(payload)
        unreal.log(END)


main()
