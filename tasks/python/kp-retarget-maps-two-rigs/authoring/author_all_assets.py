"""R27 reference authoring + discrimination proof: kp-retarget-maps-two-rigs.

REFERENCE (what a correct solve produces), all under Content/Tasks/<id>/:
    IK_TaskSource   IKRigDefinition on SKM_Manny_Simple, retarget root + 2 chains
    IK_TaskTarget   IKRigDefinition on SKM_Quinn_Simple, retarget root + 2 chains
    RTG_TaskMotion  IKRetargeter pointing at both, chains mapped

NO SUBSTRATE BASELINE IS NEEDED, and that is a real difference from R26. The two
skeletal meshes the rigs describe are stock template content, and ThirdPerson
ships NO IKRig or IKRetargeter at all -- so unlike R26 there is nothing for a
lazy submission to duplicate, and every check is live without having to
manufacture a task-owned anchor.

THE ONE NON-OBVIOUS STEP, and the reason the spike took four boots: a
factory-fresh IKRetargeter has ZERO OPS. Until AddDefaultOps() runs,
AssignIKRigToAllOps assigns to nothing, AutoMapChains maps nothing, and
GetSourceChain answers None for every chain. That is not an API limitation, it
is an empty op stack -- and it is also a free live gate, because a submission
that skips it produces a retargeter that maps nothing.

Also proves the two cheapest wrong answers fail:
    empty-rigs    rigs created but no root and no chains
    no-ops        everything created, AddDefaultOps never called
"""
import os
import sys
import unreal

TASK = "kp-retarget-maps-two-rigs"
DIR = "/Game/Tasks/" + TASK
SRC_MESH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
TGT_MESH = "/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple"
CHAINS = (("Spine", "spine_01", "spine_05"), ("LeftArm", "upperarm_l", "hand_l"))
OUT = []


def say(k, v):
    OUT.append("%-42s %s" % (k, v))


def build_rig(name, mesh_path, with_chains=True):
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    rig = tools.create_asset(name, DIR, unreal.IKRigDefinition,
                             unreal.IKRigDefinitionFactory())
    c = unreal.IKRigController.get_controller(rig)
    c.set_skeletal_mesh(unreal.EditorAssetLibrary.load_asset(mesh_path))
    if with_chains:
        c.set_retarget_root("root")
        for chain, start, end in CHAINS:
            c.add_retarget_chain(chain, start, end, "None")
    return rig, c


def main():
    tools = unreal.AssetToolsHelpers.get_asset_tools()

    src_rig, src_c = build_rig("IK_TaskSource", SRC_MESH)
    tgt_rig, tgt_c = build_rig("IK_TaskTarget", TGT_MESH)
    say("ref.source_rig", src_rig.get_path_name().split(".")[0])
    say("ref.target_rig", tgt_rig.get_path_name().split(".")[0])
    say("ref.source_root", str(src_c.get_retarget_root()))
    say("ref.source_chains", [str(c.chain_name) for c in src_c.get_retarget_chains()])
    say("ref.target_chains", [str(c.chain_name) for c in tgt_c.get_retarget_chains()])

    rtg = tools.create_asset("RTG_TaskMotion", DIR, unreal.IKRetargeter,
                             unreal.IKRetargetFactory())
    rc = unreal.IKRetargeterController.get_controller(rtg)
    say("ref.ops_before", rc.get_num_retarget_ops())
    rc.add_default_ops()                       # <- the step that makes it work
    say("ref.ops_after", rc.get_num_retarget_ops())
    rc.set_ik_rig(unreal.RetargetSourceOrTarget.SOURCE, src_rig)
    rc.set_ik_rig(unreal.RetargetSourceOrTarget.TARGET, tgt_rig)
    rc.assign_ik_rig_to_all_ops(unreal.RetargetSourceOrTarget.SOURCE, src_rig)
    rc.assign_ik_rig_to_all_ops(unreal.RetargetSourceOrTarget.TARGET, tgt_rig)
    rc.auto_map_chains(unreal.AutoMapChainType.EXACT, True)

    say("ref.retargeter", rtg.get_path_name().split(".")[0])
    say("ref.source_rig_prop",
        rtg.get_editor_property("source_ik_rig_asset").get_path_name().split(".")[0])
    say("ref.target_rig_prop",
        rtg.get_editor_property("target_ik_rig_asset").get_path_name().split(".")[0])
    for chain, _s, _e in CHAINS:
        say("GRADE.mapping[%s]" % chain, str(rc.get_source_chain(chain)))

    for p in ("IK_TaskSource", "IK_TaskTarget", "RTG_TaskMotion"):
        unreal.EditorAssetLibrary.save_asset(DIR + "/" + p, only_if_is_dirty=False)

    # ---- DISCRIMINATION: the two cheapest wrong answers ---------------------
    if os.environ.get("CB_R27_VARIANTS") == "1":
        for vdir, mode in (("_v_emptyrigs", "empty"), ("_v_noops", "noops")):
            d = DIR + vdir
            r1 = tools.create_asset("IK_TaskSource", d, unreal.IKRigDefinition,
                                    unreal.IKRigDefinitionFactory())
            c1 = unreal.IKRigController.get_controller(r1)
            c1.set_skeletal_mesh(unreal.EditorAssetLibrary.load_asset(SRC_MESH))
            r2 = tools.create_asset("IK_TaskTarget", d, unreal.IKRigDefinition,
                                    unreal.IKRigDefinitionFactory())
            c2 = unreal.IKRigController.get_controller(r2)
            c2.set_skeletal_mesh(unreal.EditorAssetLibrary.load_asset(TGT_MESH))
            if mode == "noops":
                for c, _ in ((c1, 0), (c2, 0)):
                    c.set_retarget_root("root")
                    for chain, s, e in CHAINS:
                        c.add_retarget_chain(chain, s, e, "None")
            g = tools.create_asset("RTG_TaskMotion", d, unreal.IKRetargeter,
                                   unreal.IKRetargetFactory())
            gc = unreal.IKRetargeterController.get_controller(g)
            if mode == "noops":
                # everything EXCEPT add_default_ops
                gc.set_ik_rig(unreal.RetargetSourceOrTarget.SOURCE, r1)
                gc.set_ik_rig(unreal.RetargetSourceOrTarget.TARGET, r2)
                gc.auto_map_chains(unreal.AutoMapChainType.EXACT, True)
            say("VARIANT[%s].chains_on_source" % mode,
                [str(x.chain_name) for x in c1.get_retarget_chains()])
            say("VARIANT[%s].mapping_Spine" % mode, str(gc.get_source_chain("Spine")))
            for p in ("IK_TaskSource", "IK_TaskTarget", "RTG_TaskMotion"):
                unreal.EditorAssetLibrary.save_asset(d + "/" + p, only_if_is_dirty=False)


try:
    main()
except Exception as e:  # noqa: BLE001
    import traceback
    say("FATAL", "%s: %s" % (type(e).__name__, e))
    OUT.append(traceback.format_exc()[-800:])

print("R27-AUTHOR-START")
for line in OUT:
    print(line)
print("R27-AUTHOR-END")
sys.stdout.flush()

if os.environ.get("CB_R27_KEEP") != "1":
    for d in (DIR, DIR + "_v_emptyrigs", DIR + "_v_noops"):
        try:
            if unreal.EditorAssetLibrary.does_directory_exist(d):
                unreal.EditorAssetLibrary.delete_directory(d)
        except Exception:  # noqa: BLE001
            pass
    print("cleanup done")
sys.stdout.flush()
