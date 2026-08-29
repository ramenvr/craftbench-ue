"""Author the `duplicate-the-shipped-set` discrimination variant.

The cheapest wrong answer: instead of authoring three assets for the task rig,
duplicate the shipped Mannequin animations under the required names. Names and
classes are then correct (C1-C3 PASS) and every rig reference is the STOCK one
(C4-C6 FAIL). This leg is the live proof of the design's central claim.
"""
import sys
import unreal

TASK = "kp-motion-set-shares-one-rig"
DIR = "/Game/Tasks/" + TASK
SRC_CLIP = "/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle"
SRC_MONT = "/Game/Characters/Mannequins/Anims/Pistol/MM_Pistol_Fire_Montage"
SRC_ABP = "/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed"
OUT = []

def say(k, v):
    OUT.append("%-40s %s" % (k, v))

def anchor(p):
    a = unreal.EditorAssetLibrary.load_asset(p)
    if a is None:
        return "<absent>"
    for prop in ("skeleton", "target_skeleton"):
        try:
            s = a.get_editor_property(prop)
            if s is not None:
                return s.get_path_name().split(".")[0]
        except Exception:
            continue
    return None

for src, name in ((SRC_CLIP, "A_TaskMotion"),
                  (SRC_MONT, "AM_TaskAction"),
                  (SRC_ABP, "ABP_TaskLogic")):
    dst = DIR + "/" + name
    try:
        if not unreal.EditorAssetLibrary.does_asset_exist(dst):
            unreal.EditorAssetLibrary.duplicate_asset(src, dst)
        unreal.EditorAssetLibrary.save_asset(dst, only_if_is_dirty=False)
        say("dup." + name, anchor(dst))
    except Exception as e:
        say("dup." + name, "FAILED %s: %s" % (type(e).__name__, e))

say("VERDICT.any_on_task_rig",
    any(anchor(DIR + "/" + n) == DIR + "/SK_TaskRig"
        for n in ("A_TaskMotion", "AM_TaskAction", "ABP_TaskLogic")))

print("R26-VARIANT-START")
for l in OUT:
    print(l)
print("R26-VARIANT-END")
sys.stdout.flush()
