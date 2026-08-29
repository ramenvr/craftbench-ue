"""R24 reference + discrimination authoring: kp-character-boom-and-movement.

REFERENCE: Content/Tasks/<id>/BP_TaskChar — a Character-derived Blueprint with
a spring arm on the root, a camera parented UNDER the arm, and three
CharacterMovement numerics set to values the stock character does NOT use.

WHY THE NUMERICS ARE THE DISCRIMINATOR, not the hierarchy. Probed 2026-08-14:
the shipped BP_ThirdPersonCharacter ALREADY has CameraBoom + FollowCamera, so
`duplicate the stock character` satisfies any hierarchy check. It also already
has orient_rotation_to_movement = True, which makes that a DEAD GATE. What it
does not have is 900 / 700 / 1024 — it ships 500 / 500 / 2048. So the numerics
are the only thing a duplicate cannot inherit, and the prompt does not claim to
grade "from scratch", because that is not gradable.

Also authors the `duplicate-the-stock-character` variant, which must score 2/6:
C1-C2 pass (it IS a Character-derived Blueprint at the right path), and C3-C6 all
fail — its components are named `CameraBoom`/`FollowCamera` so both stem lookups
miss, and its movement is the stock 500/500/2048. Confirmed by the committed
`cb discriminate` run; see `../discrimination/MATRIX.md`.
"""
import os
import sys
import unreal

TASK = "kp-character-boom-and-movement"
DIR = "/Game/Tasks/" + TASK
STOCK = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter"
NAME = "BP_TaskChar"

WANT = {"max_walk_speed": 900.0, "jump_z_velocity": 700.0,
        "max_acceleration": 1024.0}
OUT = []


def say(k, v):
    OUT.append("%-44s %s" % (k, v))


def add(sub, bp, cls, name, parent):
    p = unreal.AddNewSubobjectParams()
    p.set_editor_property("parent_handle", parent)
    p.set_editor_property("new_class", cls)
    p.set_editor_property("blueprint_context", bp)
    h, fail = sub.add_new_subobject(p)
    if str(fail):
        raise RuntimeError("add_new_subobject: %s" % fail)
    sub.rename_subobject(h, name)
    return h


def components(sub, bp):
    out = []
    for h in sub.k2_gather_subobject_data_for_blueprint(bp):
        d = unreal.SubobjectDataBlueprintFunctionLibrary.get_data(h)
        o = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(d)
        if o:
            out.append(o.get_name())
    return out


def movement_of(path, cls_suffix):
    cdo = unreal.get_default_object(unreal.load_object(None, path + "." + cls_suffix))
    return cdo.get_editor_property("character_movement")


def main():
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)

    # ---- REFERENCE ------------------------------------------------------
    fac = unreal.BlueprintFactory()
    fac.set_editor_property("parent_class", unreal.Character)
    bp = tools.create_asset(NAME, DIR, unreal.Blueprint, fac)
    say("ref.blueprint", bp.get_path_name().split(".")[0])

    root = sub.k2_gather_subobject_data_for_blueprint(bp)[0]
    boom = add(sub, bp, unreal.SpringArmComponent, "TaskBoom", root)
    add(sub, bp, unreal.CameraComponent, "TaskCam", boom)   # UNDER the arm
    say("ref.components", components(sub, bp))

    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    mv = movement_of(DIR + "/" + NAME, NAME + "_C")
    for k, v in WANT.items():
        mv.set_editor_property(k, v)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    unreal.EditorAssetLibrary.save_asset(DIR + "/" + NAME, only_if_is_dirty=False)

    mv2 = movement_of(DIR + "/" + NAME, NAME + "_C")
    for k in WANT:
        say("GRADE.ref." + k, mv2.get_editor_property(k))

    # ---- VARIANT: duplicate the stock character --------------------------
    if os.environ.get("CB_R24_VARIANTS") == "1":
        vd = DIR + "_v_dupstock"
        unreal.EditorAssetLibrary.duplicate_asset(STOCK, vd + "/" + NAME)
        unreal.EditorAssetLibrary.save_asset(vd + "/" + NAME, only_if_is_dirty=False)
        dbp = unreal.EditorAssetLibrary.load_asset(vd + "/" + NAME)
        say("VARIANT.components", components(sub, dbp))
        dmv = movement_of(vd + "/" + NAME, NAME + "_C")
        for k in WANT:
            got = dmv.get_editor_property(k)
            say("VARIANT.%s" % k, "%s (want %s -> %s)"
                % (got, WANT[k], "PASS" if got == WANT[k] else "FAIL"))


try:
    main()
except Exception as e:  # noqa: BLE001
    import traceback
    say("FATAL", "%s: %s" % (type(e).__name__, e))
    OUT.append(traceback.format_exc()[-700:])

print("R24-AUTHOR-START")
for line in OUT:
    print(line)
print("R24-AUTHOR-END")
sys.stdout.flush()

if os.environ.get("CB_R24_KEEP") != "1":
    for d in (DIR, DIR + "_v_dupstock"):
        try:
            if unreal.EditorAssetLibrary.does_directory_exist(d):
                unreal.EditorAssetLibrary.delete_directory(d)
        except Exception:  # noqa: BLE001
            pass
    print("cleanup done")
sys.stdout.flush()
