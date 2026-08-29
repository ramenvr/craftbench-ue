"""Fixed-denominator, read-only Behavior Tree structural verifier."""

import json
import re

try:
    import unreal
except ImportError:
    unreal = None


START = "CRAFTBENCH-INTROSPECT-JSON-START"
END = "CRAFTBENCH-INTROSPECT-JSON-END"
TASK_ID = "t3-the-guard-resumes-patrol-after-the-chase"
DIRECTORY = "/Game/Tasks/" + TASK_ID
BLACKBOARD = DIRECTORY + "/BB_GuardPatrolChase"
TREE = DIRECTORY + "/BT_GuardPatrolChase"
CHECK_IDS = (
    "PrioritySelectorAndDecoratorsAuthored",
    "TrueKeyObserverAbortsPatrol",
    "ChaseBranchUsesLiveTarget",
    "PatrolBranchSelectsAndMoves",
)


def check(check_id, passed, detail):
    clean = " ".join(str(detail).replace(START, "<START>").replace(
        END, "<END>").split())[:900]
    return {"id": check_id, "passed": bool(passed), "detail": clean}


def unpack(result):
    # UE 5.8 exposes a native FString return as one built-in ``str``.  A
    # bool+out-param UFUNCTION would surface as a tuple, but this helper is the
    # dedicated FString wrapper and must not be interpreted using that older
    # binding shape.
    if type(result) is not str:
        raise RuntimeError("GUARD_BT_HELPER_SHAPE value=%r" % (result,))
    return result.startswith("PASS "), result


def inspect():
    observed = {str(value).split(".", 1)[0] for value in
                unreal.EditorAssetLibrary.list_assets(
                    DIRECTORY, recursive=True, include_folder=False)}
    expected = {BLACKBOARD, TREE}
    if observed != expected:
        raise ValueError("GUARD_BT_EXACT_INVENTORY expected=%r observed=%r" %
                         (sorted(expected), sorted(observed)))
    blackboard = unreal.EditorAssetLibrary.load_asset(BLACKBOARD)
    tree = unreal.EditorAssetLibrary.load_asset(TREE)
    if blackboard is None or tree is None:
        raise ValueError("GUARD_BT_DECLARED_ASSET_MISSING")
    if str(blackboard.get_class().get_name()) != "BlackboardData":
        raise ValueError("GUARD_BT_BLACKBOARD_WRONG_CLASS")
    if str(tree.get_class().get_name()) != "BehaviorTree":
        raise ValueError("GUARD_BT_TREE_WRONG_CLASS")
    helper = getattr(unreal, "GuardPatrolChaseAssetAuthoring", None)
    if helper is None:
        raise RuntimeError("GUARD_BT_NATIVE_HELPER_UNAVAILABLE")
    all_ok, detail = unpack(
        helper.inspect_decision_assets_text(tree, blackboard))
    match = re.search(
        r"\bblackboard_contract=([01])\s+priority_selector=([01])\s+"
        r"observer_abort=([01])\s+chase_target=([01])\s+patrol_loop=([01])\b",
        detail)
    if match is None:
        raise RuntimeError("GUARD_BT_HELPER_DETAIL_UNPARSEABLE " + detail)
    blackboard_ok, priority, observer, chase, patrol = (
        value == "1" for value in match.groups())
    return (
        (blackboard_ok and priority, blackboard_ok and observer,
         blackboard_ok and chase, blackboard_ok and patrol),
        all_ok,
        detail,
    )


def main():
    results = {}
    if unreal is None:
        for check_id in CHECK_IDS:
            results[check_id] = check(check_id, False, "GUARD_BT_NO_UNREAL")
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
                    check_id, False, "GUARD_BT_READ_ERROR %r" % (exc,))
    payload = json.dumps(
        {"checks": [results[item] for item in CHECK_IDS]},
        separators=(",", ":"))
    print(START)
    print(payload)
    print(END)
    if unreal is not None:
        unreal.log(START)
        unreal.log(payload)
        unreal.log(END)


main()
