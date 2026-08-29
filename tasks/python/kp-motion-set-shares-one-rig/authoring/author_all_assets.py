"""R26 baseline + reference authoring, and the proof the design holds.

Two jobs in one boot:

  BASELINE (what the substrate ships, and what the agent is given):
      Content/Tasks/<id>/SK_TaskRig      a task-owned Skeleton, duplicated from
                                         the stock SK_Mannequin.

  REFERENCE (what a correct solve produces):
      Content/Tasks/<id>/A_TaskMotion    AnimSequence anchored to SK_TaskRig
      Content/Tasks/<id>/AM_TaskAction   AnimMontage from that clip
      Content/Tasks/<id>/ABP_TaskLogic   AnimBlueprint targeting SK_TaskRig

WHY THE TASK-OWNED RIG IS MANDATORY, not decorative. The spike proved the
engine REFUSES to create any of the three anchored to nothing (a clip without a
skeleton fails "cannot initialize RigHierarchy"; a bare montage factory returns
None; the AnimBP template escape hatch is not exposed to Python). So on the
stock rig every anchor check would pass for any submission that created the
assets at all -- three dead gates over 43% of the score. With a task-owned rig,
duplicating stock content lands on SK_Mannequin (the WRONG rig) and fails.

This script therefore also runs the DISCRIMINATION PROOF: it builds the cheapest
gaming route (duplicate the stock assets) and shows it lands on the wrong rig.

Writes only under Content/Tasks/<id>/ and Content/Tasks/<id>_gaming/.
CB_R26_KEEP=1 leaves them for harvesting; default cleans up.
"""
import os
import sys
import unreal

TASK = "kp-motion-set-shares-one-rig"
DIR = "/Game/Tasks/" + TASK
GAMING = "/Game/Tasks/" + TASK + "_gaming"
STOCK_RIG = "/Game/Characters/Mannequins/Meshes/SK_Mannequin"
STOCK_CLIP = "/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle"

RIG = DIR + "/SK_TaskRig"
CLIP = DIR + "/A_TaskMotion"
MONT = DIR + "/AM_TaskAction"
ABP = DIR + "/ABP_TaskLogic"

OUT = []
def say(k, v):
    OUT.append("%-44s %s" % (k, v))

def anchor_of(path):
    """The rig an asset is anchored to, or None. Registry-free object read."""
    a = unreal.EditorAssetLibrary.load_asset(path)
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

def main():
    tools = unreal.AssetToolsHelpers.get_asset_tools()

    # ---- BASELINE ---------------------------------------------------------
    if not unreal.EditorAssetLibrary.does_asset_exist(RIG):
        unreal.EditorAssetLibrary.duplicate_asset(STOCK_RIG, RIG)
    rig = unreal.EditorAssetLibrary.load_asset(RIG)
    say("baseline.rig", rig.get_path_name() if rig else "FAILED")
    say("baseline.rig_is_distinct_from_stock", RIG != STOCK_RIG and rig is not None)

    # ---- REFERENCE --------------------------------------------------------
    f = unreal.AnimSequenceFactory()
    f.set_editor_property("target_skeleton", rig)
    clip = tools.create_asset("A_TaskMotion", DIR, unreal.AnimSequence, f)
    say("ref.clip", clip.get_path_name() if clip else "FAILED")

    fm = unreal.AnimMontageFactory()
    fm.set_editor_property("source_animation", clip)   # anchor DERIVED from clip
    mont = tools.create_asset("AM_TaskAction", DIR, unreal.AnimMontage, fm)
    say("ref.montage", mont.get_path_name() if mont else "FAILED")

    fa = unreal.AnimBlueprintFactory()
    fa.set_editor_property("target_skeleton", rig)
    abp = tools.create_asset("ABP_TaskLogic", DIR, unreal.AnimBlueprint, fa)
    say("ref.animbp", abp.get_path_name() if abp else "FAILED")

    for p in (CLIP, MONT, ABP, RIG):
        unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False)

    # ---- THE GRADED FACTS -------------------------------------------------
    say("GRADE.clip_anchor", anchor_of(CLIP))
    say("GRADE.montage_anchor", anchor_of(MONT))
    say("GRADE.animbp_anchor", anchor_of(ABP))
    ok = all(anchor_of(p) == RIG for p in (CLIP, MONT, ABP))
    say("GRADE.all_three_share_the_task_rig", ok)
    try:
        say("GRADE.montage_plays_the_clip",
            mont.get_first_anim_reference().get_path_name().split(".")[0])
    except Exception as e:
        say("GRADE.montage_plays_the_clip", "FAILED %s" % type(e).__name__)

    # ---- DISCRIMINATION PROOF: the cheapest gaming route -------------------
    # Duplicate the shipped assets instead of authoring. Must land on the STOCK
    # rig and therefore fail the anchor checks.
    unreal.EditorAssetLibrary.duplicate_asset(STOCK_CLIP, GAMING + "/A_TaskMotion")
    say("GAMING.duplicated_clip_anchor", anchor_of(GAMING + "/A_TaskMotion"))
    say("GAMING.lands_on_WRONG_rig",
        anchor_of(GAMING + "/A_TaskMotion") == STOCK_RIG)

try:
    main()
except Exception as e:
    import traceback
    say("FATAL", "%s: %s" % (type(e).__name__, e))
    OUT.append(traceback.format_exc()[-900:])

print("R26-AUTHOR-START")
for line in OUT:
    print(line)
print("R26-AUTHOR-END")
sys.stdout.flush()

if os.environ.get("CB_R26_KEEP") != "1":
    for d in (DIR, GAMING):
        try:
            if unreal.EditorAssetLibrary.does_directory_exist(d):
                unreal.EditorAssetLibrary.delete_directory(d)
        except Exception as e:
            print("cleanup FAILED %s %s" % (d, e))
    print("cleanup done")
else:
    try:
        if unreal.EditorAssetLibrary.does_directory_exist(GAMING):
            unreal.EditorAssetLibrary.delete_directory(GAMING)
    except Exception:
        pass
    print("KEPT %s (gaming dir removed)" % DIR)
sys.stdout.flush()
