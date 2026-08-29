"""Fixed-denominator read-only Guard Aim AnimGraph verifier.

This task-local source must be copied byte-for-byte by the shared-file owner to
tools/verify-single/introspect/t3_guard_visible_aim.py before promotion.
"""

import json

try:
    import unreal
except ImportError:
    unreal = None


START = "CRAFTBENCH-INTROSPECT-JSON-START"
END = "CRAFTBENCH-INTROSPECT-JSON-END"
ASSET = ("/Game/Tasks/t3-guard-aims-only-at-the-visible-target/"
         "ABP_GuardVisibleAim")
CHECKS = (
    "SightStateFeedsAimCoordinates",
    "AimOffsetIsAdditiveOverLocomotion",
)


def result(check_id, passed, detail):
    clean = " ".join(str(detail).replace(START, "<START>").replace(
        END, "<END>").split())[:900]
    return {"id": check_id, "passed": bool(passed), "detail": clean}


def inspect():
    directory = ASSET.rsplit("/", 1)[0]
    observed = {str(value).split(".", 1)[0]
                for value in unreal.EditorAssetLibrary.list_assets(
                    directory, recursive=True, include_folder=False)}
    if observed != {ASSET}:
        raise ValueError("GUARD_AIM_EXACT_INVENTORY observed=%r" %
                         sorted(observed))
    asset = unreal.EditorAssetLibrary.load_asset(ASSET)
    helper = getattr(unreal, "GuardVisibleAimVerifierLibrary", None)
    if asset is None or helper is None:
        raise RuntimeError("GUARD_AIM_ASSET_OR_HELPER_MISSING")
    facts = json.loads(str(helper.inspect_anim_blueprint(asset, True)))
    state_feed = (facts.get("identity") is True and
                  facts.get("ground_speed_feed") is True and
                  facts.get("aim_coordinate_feeds") is True)
    additive = (facts.get("probe_ok") is True and
                facts.get("aim_offset_asset") is True and
                facts.get("locomotion_is_base_pose") is True and
                facts.get("direct_final_route") is True and
                facts.get("no_montage_slot") is True and
                facts.get("root_count") == 1 and
                facts.get("locomotion_count") == 1 and
                facts.get("aim_count") == 1 and
                facts.get("slot_count") == 0)
    return state_feed, additive, json.dumps(facts, sort_keys=True)


def main():
    values = {}
    if unreal is None:
        for check_id in CHECKS:
            values[check_id] = result(check_id, False, "GUARD_AIM_NO_UNREAL")
    else:
        try:
            state_feed, additive, detail = inspect()
            values[CHECKS[0]] = result(CHECKS[0], state_feed, detail)
            values[CHECKS[1]] = result(CHECKS[1], additive, detail)
        except Exception as exc:
            for check_id in CHECKS:
                values[check_id] = result(
                    check_id, False, "GUARD_AIM_READ_ERROR %r" % (exc,))
    payload = json.dumps({"checks": [values[item] for item in CHECKS]},
                         separators=(",", ":"))
    print(START)
    print(payload)
    print(END)
    if unreal is not None:
        unreal.log(START)
        unreal.log(payload)
        unreal.log(END)


main()
