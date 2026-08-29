"""One-shot authoring of the isolated complete Control Rig + AnimBP pair."""

import unreal


TASK_ID = "t3-both-hands-follow-the-physics-driven-handle"
OUTPUT = "/Game/__CraftBenchAdmission/" + TASK_ID
RIG = OUTPUT + "/CR_TwoHandPhysicsAdmission"
ANIM = OUTPUT + "/ABP_TwoHandPhysicsAdmission"
MESH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
EXPECTED = {RIG, ANIM}


def fail(message):
    unreal.log_error("TWO-HAND-ADMISSION-ASSETS-FAILED " + message)
    raise RuntimeError(message)


def exact_inventory():
    return {str(value).split(".", 1)[0] for value in
            unreal.EditorAssetLibrary.list_assets(
                OUTPUT, recursive=True, include_folder=False)}


def main():
    existing = exact_inventory()
    if existing or any(unreal.EditorAssetLibrary.does_asset_exist(path)
                       for path in EXPECTED):
        fail("refusing existing admission namespace: %r" % sorted(existing))
    mesh = unreal.EditorAssetLibrary.load_asset(MESH)
    if mesh is None:
        fail("Manny mesh missing")
    rig = unreal.ControlRigBlueprintFactory.create_new_control_rig_asset(
        RIG, False)
    if rig is None or str(rig.get_path_name()) != RIG + ".CR_TwoHandPhysicsAdmission":
        fail("exact Control Rig create failed: %r" % rig)
    factory = unreal.AnimBlueprintFactory()
    parent = unreal.load_class(
        None, "/Script/ThirdPerson.TwoHandRigAnimInstanceBase")
    if parent is None:
        fail("native AnimInstance parent class missing")
    factory.set_editor_property("parent_class", parent)
    factory.set_editor_property("target_skeleton",
                                mesh.get_editor_property("skeleton"))
    factory.set_editor_property("preview_skeletal_mesh", mesh)
    anim = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "ABP_TwoHandPhysicsAdmission", OUTPUT, unreal.AnimBlueprint, factory)
    if anim is None:
        fail("AnimBlueprintFactory returned None")
    helper = unreal.TwoHandRigAssetAuthoring
    rig_result = str(helper.build_control_rig(rig, True))
    if not rig_result.startswith("PASS TWO_HAND_RIG_AUTHORED"):
        fail(rig_result)
    anim_result = str(helper.build_anim_graph(anim, rig, True))
    if not anim_result.startswith("PASS TWO_HAND_ANIM_AUTHORED"):
        fail(anim_result)
    detail = str(unreal.TwoHandRigIntrospectionLibrary.inspect_assets(
        rig, anim, True, True))
    if not detail.startswith("PASS TWO_HAND_ASSET_READBACK"):
        fail("same-process readback: " + detail)
    if exact_inventory() != EXPECTED:
        fail("unexpected final inventory: %r" % sorted(exact_inventory()))
    marker = ("TWO-HAND-ADMISSION-ASSETS-SAVED assets=2 complete=1 "
              "controls=2 fabrik=2 runtime_control_rig=1 readback=PASS")
    unreal.log(marker)
    print(marker)


main()
