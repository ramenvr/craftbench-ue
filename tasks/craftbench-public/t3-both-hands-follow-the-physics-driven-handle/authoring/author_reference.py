"""One-shot creation of the complete reference pair at the live package paths.

This script is invoked only by ``close_reference.py`` after an offline
byte-for-byte baseline vault has been created and the baseline pair has been
atomically moved out of the live namespace.  It never harvests or restores
files itself.
"""

import unreal


TASK_ID = "t3-both-hands-follow-the-physics-driven-handle"
ROOT = "/Game/Tasks/" + TASK_ID
RIG_PATH = ROOT + "/CR_TwoHandPhysics"
ANIM_PATH = ROOT + "/ABP_TwoHandPhysics"
EXPECTED = {RIG_PATH, ANIM_PATH}
MESH_PATH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"


def fail(message):
    unreal.log_error("TWO-HAND-REFERENCE-AUTHOR-FAILED " + message)
    raise RuntimeError(message)


def inventory():
    return {str(value).split(".", 1)[0] for value in
            unreal.EditorAssetLibrary.list_assets(
                ROOT, recursive=True, include_folder=False)}


if inventory() or any(unreal.EditorAssetLibrary.does_asset_exist(path)
                      for path in EXPECTED):
    fail("fresh exact task namespace required: %r" % sorted(inventory()))
mesh = unreal.EditorAssetLibrary.load_asset(MESH_PATH)
if mesh is None:
    fail("Manny mesh missing")
rig = unreal.ControlRigBlueprintFactory.create_new_control_rig_asset(
    RIG_PATH, False)
if rig is None or str(rig.get_path_name()) != \
        RIG_PATH + ".CR_TwoHandPhysics":
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
    "ABP_TwoHandPhysics", ROOT, unreal.AnimBlueprint, factory)
if anim is None:
    fail("AnimBlueprintFactory returned None")
rig_result = str(unreal.TwoHandRigAssetAuthoring.build_control_rig(rig, True))
if not rig_result.startswith("PASS TWO_HAND_RIG_AUTHORED"):
    fail(rig_result)
anim_result = str(unreal.TwoHandRigAssetAuthoring.build_anim_graph(
    anim, rig, True))
if not anim_result.startswith("PASS TWO_HAND_ANIM_AUTHORED"):
    fail(anim_result)
complete = str(unreal.TwoHandRigIntrospectionLibrary.inspect_assets(
    rig, anim, True, False))
if not complete.startswith("PASS TWO_HAND_ASSET_READBACK"):
    fail("complete same-process readback failed: " + complete)
if inventory() != EXPECTED:
    fail("post-author inventory drift: %r" % sorted(inventory()))
marker = (
    "TWO-HAND-REFERENCE-AUTHOR-PASS assets=2 complete=1 controls=2 "
    "fabrik=2 runtime_control_rig=1 harvest=PENDING restore=PENDING"
)
unreal.log(marker)
print(marker)
