"""Fixed-denominator read-only L2I candidate for Alert Stride.

The shared-file owner must copy this file byte-for-byte to
tools/verify-single/introspect before promotion.
"""

import json

try:
    import unreal
except ImportError:  # offline AST/unit-test lane
    unreal = None


START = "CRAFTBENCH-INTROSPECT-JSON-START"
END = "CRAFTBENCH-INTROSPECT-JSON-END"
TASK_ID = "t3-alert-state-swaps-the-upper-body-without-breaking-stride"
ROOT = "/Game/Tasks/" + TASK_ID
INTERFACE = "/Game/Maps/" + TASK_ID + "/ALI_AlertStrideUpperBody"
NAMES = (
    "ABP_AlertStrideHost",
    "ABP_AlertStrideCalmLayer",
    "ABP_AlertStrideAlertLayer",
    "ST_AlertStride",
)
CHECK_IDS = (
    "StateTreeHasCalmAlertBidirectional",
    "HostUsesDeclaredLinkedLayer",
    "LocomotionRemainsBasePose",
    "LayerImplementationsAvoidMontageRoutes",
)


def defang(value, limit=850):
    return " ".join(str(value).replace(START, "<START>").replace(
        END, "<END>").split())[:limit]


def check(check_id, passed, detail):
    return {"id": check_id, "passed": bool(passed),
            "detail": defang(detail)}


def inspect():
    expected = {ROOT + "/" + name for name in NAMES}
    observed = {str(value).split(".", 1)[0]
                for value in unreal.EditorAssetLibrary.list_assets(
                    ROOT, recursive=True, include_folder=False)}
    if observed != expected:
        raise ValueError("ALERT_STRIDE_EXACT_INVENTORY expected=%r observed=%r" %
                         (sorted(expected), sorted(observed)))
    helper = getattr(unreal, "AlertStrideVerifierLibrary", None)
    if helper is None:
        raise RuntimeError("ALERT_STRIDE_VERIFIER_HELPER_MISSING")
    if not unreal.EditorAssetLibrary.does_asset_exist(INTERFACE):
        raise ValueError("ALERT_STRIDE_INTERFACE_ABSENT path=" + INTERFACE)
    facts = json.loads(str(helper.inspect_asset_set(ROOT, INTERFACE, True)))
    detail = json.dumps(facts, sort_keys=True)
    values = {
        CHECK_IDS[0]: facts.get("state_tree_calm_alert_bidirectional") is True,
        CHECK_IDS[1]: (facts.get("declared_layer_interface") is True and
                       facts.get("host_linked_layer_route") is True and
                       facts.get("compiled_linked_node_present") is True),
        CHECK_IDS[2]: facts.get("locomotion_is_base_pose") is True,
        CHECK_IDS[3]: (facts.get("calm_layer_implements_interface") is True and
                       facts.get("alert_layer_implements_interface") is True and
                       facts.get("no_slot_or_montage_route") is True),
    }
    return {item: check(item, values[item], detail) for item in CHECK_IDS}


def emit(results):
    ordered = [results.get(item) or check(
        item, False, "ALERT_STRIDE_CHECK_UNREACHED id=" + item)
        for item in CHECK_IDS]
    payload = json.dumps({"checks": ordered}, separators=(",", ":"))
    print(START)
    print(payload)
    print(END)
    if unreal is not None:
        unreal.log(START)
        unreal.log(payload)
        unreal.log(END)


def main():
    if unreal is None:
        emit({item: check(item, False, "ALERT_STRIDE_NO_UNREAL")
              for item in CHECK_IDS})
        return
    try:
        emit(inspect())
    except Exception as exc:  # fixed denominator, submission failures grade
        emit({item: check(item, False,
                          "ALERT_STRIDE_READ_ERROR id=%s error=%r" %
                          (item, exc)) for item in CHECK_IDS})


main()
