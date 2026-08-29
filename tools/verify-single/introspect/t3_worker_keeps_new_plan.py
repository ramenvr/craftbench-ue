"""Fixed-denominator, read-only StateTree structural verifier."""

import json
import re

try:
    import unreal
except ImportError:
    unreal = None


START = "CRAFTBENCH-INTROSPECT-JSON-START"
END = "CRAFTBENCH-INTROSPECT-JSON-END"
TASK_ID = "t3-the-worker-keeps-its-new-plan-after-the-signal"
DIR = "/Game/Tasks/" + TASK_ID
TREE = DIR + "/ST_WorkerPlan"
TREE_OBJECT = TREE + ".ST_WorkerPlan"
SCHEMA_OBJECT = (TREE_OBJECT
                 + ":StateTreeEditorData_0.StateTreeAIComponentSchema_0")
CHECK_IDS = (
    "StateTreeOwnsWorkerBehavior",
    "IdleTransitionReadsSeparateSignal",
    "ActiveStateUsesNavigationTask",
)


def check(check_id, passed, detail):
    clean = " ".join(str(detail).replace(START, "<START>").replace(
        END, "<END>").split())[:700]
    return {"id": check_id, "passed": bool(passed), "detail": clean}


def unpack(result):
    # UE 5.8 exposes this native bool + FString& function as one built-in
    # string.  Require that exact binding shape and the complete native vector;
    # do not accept string-coercible wrappers or a merely matching substring.
    if type(result) is not str:
        raise RuntimeError("WORKER_PLAN_HELPER_SHAPE value=%r" % (result,))
    match = re.fullmatch(
        r"(PASS|FAIL) ownership=([01]) signal_transition=([01]) "
        r"navigation_task=([01]) tree=" + re.escape(TREE_OBJECT)
        + r" schema=" + re.escape(SCHEMA_OBJECT), result)
    if match is None:
        raise RuntimeError("WORKER_PLAN_HELPER_VECTOR value=%r" % (result,))
    return match.group(1) == "PASS", result


def inspect():
    observed = {str(value).split(".", 1)[0] for value in
                unreal.EditorAssetLibrary.list_assets(
                    DIR, recursive=True, include_folder=False)}
    if observed != {TREE}:
        raise ValueError("WORKER_PLAN_EXACT_INVENTORY expected=%r observed=%r" %
                         ([TREE], sorted(observed)))
    tree = unreal.EditorAssetLibrary.load_asset(TREE)
    if tree is None or str(tree.get_class().get_name()) != "StateTree":
        raise ValueError("WORKER_PLAN_EXACT_TREE_MISSING_OR_WRONG_CLASS")
    helper = getattr(unreal, "WorkerPlanAssetAuthoring", None)
    if helper is None:
        raise RuntimeError("WORKER_PLAN_NATIVE_HELPER_UNAVAILABLE")
    ok, detail = unpack(helper.inspect_state_tree(tree))
    match = re.search(
        r"\bownership=([01])\s+signal_transition=([01])\s+navigation_task=([01])\b",
        detail)
    if match is None:
        raise RuntimeError("WORKER_PLAN_HELPER_DETAIL_UNPARSEABLE " + detail)
    return (tuple(value == "1" for value in match.groups()), ok, detail)


def main():
    results = {}
    if unreal is None:
        for check_id in CHECK_IDS:
            results[check_id] = check(check_id, False, "WORKER_PLAN_NO_UNREAL")
    else:
        try:
            gates, all_ok, detail = inspect()
            for check_id, passed in zip(CHECK_IDS, gates):
                results[check_id] = check(
                    check_id, passed,
                    detail + " helper_all=%d" % int(all_ok))
        except Exception as exc:
            for check_id in CHECK_IDS:
                results[check_id] = check(
                    check_id, False, "WORKER_PLAN_READ_ERROR %r" % (exc,))
    payload = json.dumps({"checks": [results[item] for item in CHECK_IDS]},
                         separators=(",", ":"))
    print(START)
    print(payload)
    print(END)
    if unreal is not None:
        unreal.log(START)
        unreal.log(payload)
        unreal.log(END)


main()
