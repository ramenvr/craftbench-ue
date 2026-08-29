"""One-shot creation of the two supplied editable baseline assets."""

import unreal


TASK_ID = "t3-both-hands-follow-the-physics-driven-handle"
OUTPUT = "/Game/Tasks/" + TASK_ID
RIG = OUTPUT + "/CR_TwoHandPhysics"
ANIM = OUTPUT + "/ABP_TwoHandPhysics"
MESH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
EXPECTED = {RIG, ANIM}


def fail(message):
    unreal.log_error("TWO-HAND-BASELINE-ASSETS-FAILED " + message)
    raise RuntimeError(message)


def inventory():
    return {str(value).split(".", 1)[0] for value in
            unreal.EditorAssetLibrary.list_assets(
                OUTPUT, recursive=True, include_folder=False)}


def main():
    existing = inventory()
    if existing or any(unreal.EditorAssetLibrary.does_asset_exist(path)
                       for path in EXPECTED):
        fail("refusing existing task namespace: %r" % sorted(existing))
    mesh = unreal.EditorAssetLibrary.load_asset(MESH)
    if mesh is None:
        fail("Manny mesh missing")
    rig = unreal.ControlRigBlueprintFactory.create_new_control_rig_asset(
        RIG, False)
    if rig is None or str(rig.get_path_name()) != RIG + ".CR_TwoHandPhysics":
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
        "ABP_TwoHandPhysics", OUTPUT, unreal.AnimBlueprint, factory)
    if anim is None:
        fail("AnimBlueprintFactory returned None")
    helper = unreal.TwoHandRigAssetAuthoring
    rig_result = str(helper.build_control_rig(rig, False))
    anim_result = str(helper.build_anim_graph(anim, rig, False))
    if not rig_result.startswith("PASS TWO_HAND_RIG_AUTHORED"):
        fail(rig_result)
    if not anim_result.startswith("PASS TWO_HAND_ANIM_AUTHORED"):
        fail(anim_result)
    detail = str(unreal.TwoHandRigIntrospectionLibrary.inspect_assets(
        rig, anim, False, False))
    if not detail.startswith("PASS TWO_HAND_ASSET_READBACK"):
        fail("same-process readback: " + detail)
    if inventory() != EXPECTED:
        fail("unexpected final inventory: %r" % sorted(inventory()))
    marker = ("TWO-HAND-BASELINE-ASSETS-SAVED assets=2 complete=0 "
              "controls=2 rig_units=0 base_sequence=1 readback=PASS")
    unreal.log(marker)
    print(marker)


main()
