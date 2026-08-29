"""Fixed-denominator L2I for the designated-scout navigation-invoker task."""

import json
import os

try:
    import unreal
except ImportError:
    unreal = None


START = "CRAFTBENCH-INTROSPECT-JSON-START"
END = "CRAFTBENCH-INTROSPECT-JSON-END"
TASK_ID = "t3-walkable-ground-follows-the-designated-scout"
ROOT = "/Game/Tasks/" + TASK_ID
BLUEPRINT = ROOT + "/BP_DesignatedScout"
CHECK_IDS = (
    "DesignatedAgentOwnsNavigationInvoker",
    "InvokerRadiiAreLocalAndOrdered",
    "SubmissionHasNoGlobalNavigationSubstitute",
)
EXPECTED_SUBMISSION = [
    "Content/Tasks/%s/BP_DesignatedScout.uasset" % TASK_ID,
]


def check(check_id, passed, detail):
    detail = " ".join(str(detail).replace(START, "<START>")
                      .replace(END, "<END>").split())[:900]
    return {"id": check_id, "passed": bool(passed), "detail": detail}


def load_blueprint():
    asset = unreal.EditorAssetLibrary.load_asset(BLUEPRINT)
    if asset is None:
        raise ValueError("WALKABLE_GROUND_ASSET_ABSENT path=" + BLUEPRINT)
    if str(asset.get_class().get_name()) != "Blueprint":
        raise ValueError("WALKABLE_GROUND_WRONG_CLASS actual=" +
                         str(asset.get_class().get_name()))
    return asset


def inspect_blueprint(asset):
    helper = getattr(unreal, "WalkableGroundAdmissionAuthoring", None)
    method = getattr(helper, "inspect_designated_scout_blueprint", None) \
        if helper else None
    if method is None:
        raise RuntimeError("WALKABLE_GROUND_HELPER_UNAVAILABLE")
    detail = method(asset)
    if type(detail) is not str:
        raise RuntimeError("WALKABLE_GROUND_HELPER_BAD_SHAPE %r" % detail)
    return detail


def submitted_files():
    raw = os.environ.get("CRAFTBENCH_SUBMITTED_FILES_JSON")
    if raw is None:
        raise RuntimeError("WALKABLE_GROUND_SUBMISSION_MANIFEST_UNAVAILABLE")
    value = json.loads(raw)
    if not isinstance(value, list) or not all(isinstance(item, str)
                                              for item in value):
        raise RuntimeError("WALKABLE_GROUND_SUBMISSION_MANIFEST_BAD_SHAPE")
    return sorted({item.replace("\\", "/") for item in value})


def main():
    results = {}
    if unreal is None:
        results = {gate: check(gate, False, "WALKABLE_GROUND_NO_UNREAL")
                   for gate in CHECK_IDS}
    else:
        asset = None
        detail = ""
        try:
            asset = load_blueprint()
            detail = inspect_blueprint(asset)
            passed = detail.startswith("PASS ") \
                and "class_exact=1" in detail \
                and "compile_exact=1" in detail \
                and "owner_exact=1" in detail \
                and "component_count=1" in detail
            results[CHECK_IDS[0]] = check(CHECK_IDS[0], passed, detail)
        except Exception as exc:
            results[CHECK_IDS[0]] = check(
                CHECK_IDS[0], False,
                "WALKABLE_GROUND_OWNER_READ_ERROR %r" % exc)
        try:
            if asset is None:
                asset = load_blueprint()
            if not detail:
                detail = inspect_blueprint(asset)
            passed = detail.startswith("PASS ") \
                and "radii_valid=1" in detail \
                and "graph_nodes=0" in detail
            results[CHECK_IDS[1]] = check(CHECK_IDS[1], passed, detail)
        except Exception as exc:
            results[CHECK_IDS[1]] = check(
                CHECK_IDS[1], False,
                "WALKABLE_GROUND_RADII_READ_ERROR %r" % exc)
        try:
            files = submitted_files()
            observed = {str(value).split(".", 1)[0] for value in
                        unreal.EditorAssetLibrary.list_assets(
                            ROOT, recursive=True, include_folder=False)}
            expected_assets = {BLUEPRINT}
            passed = files == EXPECTED_SUBMISSION and observed == expected_assets
            boundary = (
                "WALKABLE_GROUND_ASSET_ONLY_BOUNDARY expected_files=%s "
                "actual_files=%s expected_assets=%s actual_assets=%s" %
                (EXPECTED_SUBMISSION, files, sorted(expected_assets),
                 sorted(observed)))
            results[CHECK_IDS[2]] = check(CHECK_IDS[2], passed, boundary)
        except Exception as exc:
            results[CHECK_IDS[2]] = check(
                CHECK_IDS[2], False,
                "WALKABLE_GROUND_BOUNDARY_READ_ERROR %r" % exc)
    ordered = [results.get(gate) or check(
        gate, False, "WALKABLE_GROUND_CHECK_UNREACHED") for gate in CHECK_IDS]
    payload = json.dumps({"checks": ordered}, separators=(",", ":"))
    print(START)
    print(payload)
    print(END)
    if unreal is not None:
        unreal.log(START)
        unreal.log(payload)
        unreal.log(END)


main()
