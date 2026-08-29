"""Fixed-denominator, read-only L2I for the World Partition controller."""

import json
import re

try:
    import unreal
except ImportError:
    unreal = None


START = "CRAFTBENCH-INTROSPECT-JSON-START"
END = "CRAFTBENCH-INTROSPECT-JSON-END"
TASK_ID = "t3-only-the-near-active-sector-exists"
DIRECTORY = "/Game/Tasks/" + TASK_ID
CONTROLLER = DIRECTORY + "/BP_NearActiveSectorController"
CHECK_IDS = (
    "ControllerUsesRuntimeDataLayerSelection",
    "ControllerMovesThePlacedStreamingSource",
    "SubmissionHasNoStreamingSubstitute",
)
DETAIL = re.compile(
    r"^PASS CONTROLLER reference=1 nodes=([0-9]+) links=([0-9]+) "
    r"event=1 manager=1 layers=3 array_get=2 move=1 request_reads=4$")


def check(check_id, passed, detail):
    clean = " ".join(str(detail).replace(START, "<START>").replace(
        END, "<END>").split())[:900]
    return {"id": check_id, "passed": bool(passed), "detail": clean}


def inspect():
    observed = {str(value).split(".", 1)[0] for value in
                unreal.EditorAssetLibrary.list_assets(
                    DIRECTORY, recursive=True, include_folder=False)}
    if observed != {CONTROLLER}:
        raise ValueError("NEAR_SECTOR_EXACT_INVENTORY expected=%s observed=%r" %
                         (CONTROLLER, sorted(observed)))
    blueprint = unreal.EditorAssetLibrary.load_asset(CONTROLLER)
    if blueprint is None or str(blueprint.get_class().get_name()) != "Blueprint":
        raise ValueError("NEAR_SECTOR_CONTROLLER_MISSING_OR_WRONG_CLASS")
    helper = getattr(unreal, "NearActiveSectorAssetAuthoring", None)
    method = getattr(helper, "inspect_controller", None) if helper else None
    if method is None:
        raise RuntimeError("NEAR_SECTOR_NATIVE_HELPER_UNAVAILABLE")
    detail = str(method(True))
    match = DETAIL.fullmatch(detail)
    if match is None:
        raise RuntimeError("NEAR_SECTOR_GRAPH_VECTOR_MISMATCH " + detail)
    nodes, links = (int(value) for value in match.groups())
    graph_size_ok = 10 <= nodes <= 40 and links >= 30
    return (
        graph_size_ok,
        graph_size_ok,
        observed == {CONTROLLER},
        detail + " exact_inventory=1 graph_size_ok=%d" % int(graph_size_ok),
    )


def main():
    results = {}
    if unreal is None:
        for check_id in CHECK_IDS:
            results[check_id] = check(check_id, False, "NEAR_SECTOR_NO_UNREAL")
    else:
        try:
            layer_ok, source_ok, inventory_ok, detail = inspect()
            for check_id, passed in zip(
                    CHECK_IDS, (layer_ok, source_ok, inventory_ok)):
                results[check_id] = check(check_id, passed, detail)
        except Exception as exc:
            for check_id in CHECK_IDS:
                results[check_id] = check(
                    check_id, False, "NEAR_SECTOR_READ_ERROR %r" % (exc,))
    payload = json.dumps(
        {"checks": [results[check_id] for check_id in CHECK_IDS]},
        separators=(",", ":"))
    print(START)
    print(payload)
    print(END)
    if unreal is not None:
        unreal.log(START)
        unreal.log(payload)
        unreal.log(END)


main()
