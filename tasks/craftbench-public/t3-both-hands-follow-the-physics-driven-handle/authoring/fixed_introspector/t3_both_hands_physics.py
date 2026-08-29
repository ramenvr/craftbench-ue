"""Fixed-denominator L2I for the two-hand physics Control Rig task."""

import json
import os

try:
    import unreal
except ImportError:
    unreal = None


START = "CRAFTBENCH-INTROSPECT-JSON-START"
END = "CRAFTBENCH-INTROSPECT-JSON-END"
TASK_ID = "t3-both-hands-follow-the-physics-driven-handle"
ROOT = "/Game/Tasks/" + TASK_ID
RIG = ROOT + "/CR_TwoHandPhysics"
ANIM = ROOT + "/ABP_TwoHandPhysics"
CHECK_IDS = (
    "RuntimeControlRigComposesOverBasePose",
    "RigUsesIndependentHandControls",
    "NoDirectTransformTwoBoneIKOrMirror",
)
EXPECTED_SUBMISSION = sorted((
    "Content/Tasks/%s/CR_TwoHandPhysics.uasset" % TASK_ID,
    "Content/Tasks/%s/ABP_TwoHandPhysics.uasset" % TASK_ID,
))


def check(check_id, passed, detail):
    detail = " ".join(str(detail).replace(START, "<START>")
                      .replace(END, "<END>").split())[:1200]
    return {"id": check_id, "passed": bool(passed), "detail": detail}


def submitted_files():
    raw = os.environ.get("CRAFTBENCH_SUBMITTED_FILES_JSON")
    if raw is None:
        raise RuntimeError("TWO_HAND_SUBMISSION_MANIFEST_UNAVAILABLE")
    value = json.loads(raw)
    if not isinstance(value, list) or not all(isinstance(item, str)
                                              for item in value):
        raise RuntimeError("TWO_HAND_SUBMISSION_MANIFEST_BAD_SHAPE")
    return sorted({item.replace("\\", "/") for item in value})


def main():
    if unreal is None:
        ordered = [check(gate, False, "TWO_HAND_NO_UNREAL")
                   for gate in CHECK_IDS]
    else:
        try:
            rig = unreal.EditorAssetLibrary.load_asset(RIG)
            anim = unreal.EditorAssetLibrary.load_asset(ANIM)
            helper = getattr(unreal, "TwoHandRigIntrospectionLibrary", None)
            if rig is None or anim is None or helper is None:
                raise RuntimeError("TWO_HAND_ASSET_OR_HELPER_MISSING")
            detail = str(helper.inspect_assets(rig, anim, True, False))
            complete = detail.startswith("PASS TWO_HAND_ASSET_READBACK")
            runtime = complete and "ANIM_COMPLETE" in detail and \
                "runtime_control_rig=1" in detail and "compiled_node=1" in detail
            controls = complete and "RIG_COMPLETE" in detail and \
                "controls=2" in detail and "independent_effectors=2" in detail
            files = submitted_files()
            inventory = {str(value).split(".", 1)[0] for value in
                         unreal.EditorAssetLibrary.list_assets(
                             ROOT, recursive=True, include_folder=False)}
            no_shortcut = complete and "banned=0" in detail and \
                files == EXPECTED_SUBMISSION and inventory == {RIG, ANIM}
            boundary = (" expected_files=%s actual_files=%s inventory=%s" %
                        (EXPECTED_SUBMISSION, files, sorted(inventory)))
            ordered = [
                check(CHECK_IDS[0], runtime, detail),
                check(CHECK_IDS[1], controls, detail),
                check(CHECK_IDS[2], no_shortcut, detail + boundary),
            ]
        except Exception as exc:
            ordered = [check(gate, False, "TWO_HAND_L2I_READ_ERROR %r" % exc)
                       for gate in CHECK_IDS]
    payload = json.dumps({"checks": ordered}, separators=(",", ":"))
    print(START)
    print(payload)
    print(END)
    if unreal is not None:
        unreal.log(START)
        unreal.log(payload)
        unreal.log(END)


main()
