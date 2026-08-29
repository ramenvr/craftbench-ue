"""Fresh-process read-only admission or final asset validation."""

import os
import unreal


TASK_ID = "t3-both-hands-follow-the-physics-driven-handle"
MODE = os.environ.get("CRAFTBENCH_TWO_HAND_READBACK_MODE", "baseline").lower()
if MODE == "admission":
    ROOT = "/Game/__CraftBenchAdmission/" + TASK_ID
    RIG = ROOT + "/CR_TwoHandPhysicsAdmission"
    ANIM = ROOT + "/ABP_TwoHandPhysicsAdmission"
    COMPLETE = True
    ADMISSION = True
elif MODE == "reference":
    ROOT = "/Game/Tasks/" + TASK_ID
    RIG = ROOT + "/CR_TwoHandPhysics"
    ANIM = ROOT + "/ABP_TwoHandPhysics"
    COMPLETE = True
    ADMISSION = False
elif MODE == "baseline":
    ROOT = "/Game/Tasks/" + TASK_ID
    RIG = ROOT + "/CR_TwoHandPhysics"
    ANIM = ROOT + "/ABP_TwoHandPhysics"
    COMPLETE = False
    ADMISSION = False
else:
    raise RuntimeError("unknown CRAFTBENCH_TWO_HAND_READBACK_MODE=" + MODE)


def load(path):
    value = unreal.EditorAssetLibrary.load_asset(path)
    if value is None:
        raise RuntimeError("TWO-HAND-READBACK missing asset=" + path)
    return value


rig = load(RIG)
anim = load(ANIM)
detail = str(unreal.TwoHandRigIntrospectionLibrary.inspect_assets(
    rig, anim, COMPLETE, ADMISSION))
if not detail.startswith("PASS TWO_HAND_ASSET_READBACK"):
    raise RuntimeError("TWO-HAND-READBACK " + detail)
marker = ("TWO-HAND-ASSET-COLD-PASS mode=%s assets=2 complete=%d "
          "runtime_observed=0 %s" % (MODE, 1 if COMPLETE else 0, detail))
unreal.log(marker)
print(marker)
