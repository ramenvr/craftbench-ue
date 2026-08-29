"""Fixed-denominator L2I for the Animation Sharing crowd task."""

import json
import os

try:
    import unreal
except ImportError:
    unreal = None


START = "CRAFTBENCH-INTROSPECT-JSON-START"
END = "CRAFTBENCH-INTROSPECT-JSON-END"
TASK_ID = "t3-alerted-crowd-shares-live-poses-by-state"
ROOT = "/Game/Tasks/" + TASK_ID
SETUP = ROOT + "/AS_AlertCrowdSharing"
PROCESSOR = ROOT + "/BP_AlertCrowdStateProcessor"
CHECK_IDS = (
    "SetupDefinesTwoEngineSharedPoseStates",
    "ProcessorReadsTheLiveAlertFact",
    "SubmissionHasNoIndependentAnimationSubstitute",
)
EXPECTED_SUBMISSION = sorted((
    "Content/Tasks/%s/AS_AlertCrowdSharing.uasset" % TASK_ID,
    "Content/Tasks/%s/BP_AlertCrowdStateProcessor.uasset" % TASK_ID,
))


def check(check_id, passed, detail):
    detail = " ".join(str(detail).replace(START, "<START>")
                      .replace(END, "<END>").split())[:900]
    return {"id": check_id, "passed": bool(passed), "detail": detail}


def load_exact(path, class_name):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if asset is None:
        raise ValueError("ASHARING_ASSET_ABSENT path=" + path)
    if str(asset.get_class().get_name()) != class_name:
        raise ValueError("ASHARING_WRONG_CLASS path=%s expected=%s actual=%s" %
                         (path, class_name, asset.get_class().get_name()))
    return asset


def helper_method(name):
    helper = getattr(unreal, "AlertCrowdSharingIntrospectionLibrary", None)
    method = getattr(helper, name, None) if helper else None
    if method is None:
        raise RuntimeError("ASHARING_HELPER_UNAVAILABLE method=" + name)
    return method


def submitted_files():
    raw = os.environ.get("CRAFTBENCH_SUBMITTED_FILES_JSON")
    if raw is None:
        raise RuntimeError("ASHARING_SUBMISSION_MANIFEST_UNAVAILABLE")
    value = json.loads(raw)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeError("ASHARING_SUBMISSION_MANIFEST_BAD_SHAPE")
    return sorted({item.replace("\\", "/") for item in value})


def main():
    results = {}
    if unreal is None:
        results = {gate: check(gate, False, "ASHARING_NO_UNREAL")
                   for gate in CHECK_IDS}
    else:
        setup = processor = None
        try:
            setup = load_exact(SETUP, "AnimationSharingSetup")
            processor = load_exact(PROCESSOR, "Blueprint")
            detail = str(helper_method("inspect_sharing_setup")(
                setup, processor))
            results[CHECK_IDS[0]] = check(
                CHECK_IDS[0], detail.startswith("PASS "), detail)
        except Exception as exc:
            results[CHECK_IDS[0]] = check(
                CHECK_IDS[0], False, "ASHARING_SETUP_READ_ERROR %r" % exc)
        try:
            if processor is None:
                processor = load_exact(PROCESSOR, "Blueprint")
            detail = str(helper_method("inspect_state_processor_graph")(
                processor))
            results[CHECK_IDS[1]] = check(
                CHECK_IDS[1], detail.startswith("PASS "), detail)
        except Exception as exc:
            results[CHECK_IDS[1]] = check(
                CHECK_IDS[1], False, "ASHARING_GRAPH_READ_ERROR %r" % exc)
        try:
            files = submitted_files()
            observed = {str(value).split(".", 1)[0] for value in
                        unreal.EditorAssetLibrary.list_assets(
                            ROOT, recursive=True, include_folder=False)}
            expected_assets = {SETUP, PROCESSOR}
            passed = files == EXPECTED_SUBMISSION and observed == expected_assets
            detail = ("ASHARING_ASSET_ONLY_BOUNDARY expected_files=%s actual_files=%s "
                      "expected_assets=%s actual_assets=%s" %
                      (EXPECTED_SUBMISSION, files, sorted(expected_assets),
                       sorted(observed)))
            results[CHECK_IDS[2]] = check(CHECK_IDS[2], passed, detail)
        except Exception as exc:
            results[CHECK_IDS[2]] = check(
                CHECK_IDS[2], False, "ASHARING_BOUNDARY_READ_ERROR %r" % exc)
    ordered = [results.get(gate) or check(
        gate, False, "ASHARING_CHECK_UNREACHED") for gate in CHECK_IDS]
    payload = json.dumps({"checks": ordered}, separators=(",", ":"))
    print(START)
    print(payload)
    print(END)
    if unreal is not None:
        unreal.log(START)
        unreal.log(payload)
        unreal.log(END)


main()
