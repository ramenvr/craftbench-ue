"""Author the `tuned-but-wrong-values` discrimination variant.

Isolates C5 (movement_values_exact), which no other leg does:
duplicate-the-stock-character/ fails C3-C6 at once and is credited at C6, so if C5
regressed to always-pass the package would look unchanged.

  hierarchy   TaskBoom (SpringArm) at root, TaskCam (Camera) under it -> C3, C4 PASS
  walk 900, jump 700   both the required values
  accel 1500           wrong (1024 required) but NOT stock (2048), so C6 PASSES

That last line is the whole trick: C5 fires on any deviation from required, C6 only
when a field still EQUALS its stock value. 5/6, failing C5 alone.

Authored AT the grading path with the internal package name asserted -- hygiene, so
the bytes stay readable; a _v_-staged asset carries a stale self-path. Requires the
reference and other variants NOT staged simultaneously, since all legs share the path.
"""
import contextlib
import io
import json
import os
import re
import sys

import unreal

_HERE = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.dirname(_HERE)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(_HERE))))
GRADER = os.path.join(REPO_ROOT, "tools", "verify-single", "introspect",
                      "kp_character_boom_and_movement.py")

# Shared harvest (raises rather than partially harvesting). Unit-tested off-box at
# tools/authoring/tests/.
sys.path.insert(0, os.path.join(REPO_ROOT, "tools", "authoring"))
import cb_variant_lib as CBV  # noqa: E402

TASK = "kp-character-boom-and-movement"
VARIANT_DIR = "tuned-but-wrong-values"
DIR = "/Game/Tasks/" + TASK          # the REAL path — see the module docstring
NAME = "BP_TaskChar"
PKG = DIR + "/" + NAME

#: The reference's required values, for reference only — this variant matches two
#: of the three on purpose so the failure is a single field.
REQUIRED = {"max_walk_speed": 900.0, "jump_z_velocity": 700.0,
            "max_acceleration": 1024.0}
#: What the stock BP_ThirdPersonCharacter ships. C6 fires if ANY field equals its
#: stock value, so every value below must avoid these.
STOCK = {"max_walk_speed": 500.0, "jump_z_velocity": 500.0,
         "max_acceleration": 2048.0}
#: The single delta: accel is wrong (1024 required) but NOT stock (2048).
VARIANT = {"max_walk_speed": 900.0, "jump_z_velocity": 700.0,
           "max_acceleration": 1500.0}

OUT = []


def say(k, v):
    OUT.append("%-46s %s" % (k, v))


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
    return unreal.get_default_object(
        unreal.load_object(None, path + "." + cls_suffix)
    ).get_editor_property("character_movement")


def self_grade():
    """Run the REAL grader in-process and return its checks.

    This is what makes the authoring lane cheap: it turns a *predicted* verdict
    into a *measured* one inside the same headless boot, so a variant that does
    not discriminate is caught before it is harvested — instead of after a
    ~300 s-per-leg `cb discriminate`. Recipe lifted verbatim from
    `kp-anim-track-bake/aids/author_reference.py`, including setting `__name__`
    to a non-`__main__` value so the grader's own entry guard does not fire and
    `main()` is called explicitly.
    """
    if not os.path.isfile(GRADER):
        return None, "grader not found at %s" % GRADER
    src = io.open(GRADER, encoding="utf-8").read()
    buf = io.StringIO()
    ns = {"__name__": "__cb_selfgrade__", "__file__": GRADER}
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(src, GRADER, "exec"), ns)  # noqa: S102 verifier-owned
            ns["main"]()
    except Exception as e:  # noqa: BLE001
        return None, "grader raised %r" % (e,)
    m = re.search(r"CRAFTBENCH-INTROSPECT-JSON-START\s*\n(.*?)\n\s*"
                  r"CRAFTBENCH-INTROSPECT-JSON-END", buf.getvalue(), re.S)
    if m is None:
        return None, "self-grade produced no verdict block"
    try:
        checks = json.loads(m.group(1))["checks"]
    except Exception as e:  # noqa: BLE001
        return None, "unparseable verdict block %r" % (e,)
    # Return the repo-standard VECTOR shape {cid: (passed, detail)} — identical to
    # every aids/author_reference.py grade_in_process() — so cb_variant_lib's
    # acceptance() can consume it directly. Returning the raw list here is what
    # broke the first authoring run (NameError, then a shape mismatch).
    return {c["id"]: (bool(c["passed"]), c.get("detail", "")) for c in checks}, None


def main():
    # Refuse to clobber a staged reference: they share PKG, and silently
    # overwriting it would produce a variant harvested from the wrong asset.
    if unreal.EditorAssetLibrary.does_asset_exist(PKG):
        raise RuntimeError(
            "%s already exists — author one leg at a time (the reference and "
            "every variant share this path). Delete it first." % PKG)

    tools = unreal.AssetToolsHelpers.get_asset_tools()
    sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)

    fac = unreal.BlueprintFactory()
    fac.set_editor_property("parent_class", unreal.Character)
    bp = tools.create_asset(NAME, DIR, unreal.Blueprint, fac)

    # THE INVARIANT THIS SCRIPT EXISTS TO KEEP: the internal package name must
    # equal the path the grader will load. A `_v_`-staged asset fails this.
    internal = bp.get_path_name().split(".")[0]
    say("internal_package_name", internal)
    if internal != PKG:
        raise RuntimeError(
            "internal package name %r != grading path %r — harvesting this "
            "would commit a PACKAGE_IDENTITY_MISMATCH" % (internal, PKG))

    root = sub.k2_gather_subobject_data_for_blueprint(bp)[0]
    boom = add(sub, bp, unreal.SpringArmComponent, "TaskBoom", root)
    add(sub, bp, unreal.CameraComponent, "TaskCam", boom)   # UNDER the arm
    say("components", components(sub, bp))

    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    mv = movement_of(PKG, NAME + "_C")
    for k, v in VARIANT.items():
        mv.set_editor_property(k, v)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    unreal.EditorAssetLibrary.save_asset(PKG, only_if_is_dirty=False)

    # ---- predict the grade from the saved asset, per check ------------------
    got = {k: movement_of(PKG, NAME + "_C").get_editor_property(k)
           for k in VARIANT}
    for k in ("max_walk_speed", "jump_z_velocity", "max_acceleration"):
        say("saved." + k, got[k])

    wrong = ["%s=%s want=%s" % (k, got[k], v) for k, v in REQUIRED.items()
             if got[k] != v]
    inherited = [k for k in REQUIRED if got[k] == STOCK[k]]
    say("PREDICT.C5_movement_values_exact",
        "FAIL CHARRIG_MOVEMENT_WRONG %s" % wrong if wrong else "PASS")
    say("PREDICT.C6_untouched_defaults_absent",
        "FAIL CHARRIG_MOVEMENT_STILL_STOCK fields=%s" % inherited
        if inherited else "PASS (no field sits at its stock value)")

    # ---- MEASURE it with the real grader, in this same boot ----------------
    vector, err = self_grade()
    if err:
        say("SELFGRADE", "UNAVAILABLE %s" % err)
        say("VERDICT.isolates_C5_alone", "UNVERIFIED — predicted only")
        return
    passed, total = CBV.score(vector)
    failed = sorted(cid for cid, (ok, _) in vector.items() if not ok)
    say("SELFGRADE", "%d/%d" % (passed, total))
    for cid in sorted(vector):
        ok_c, detail = vector[cid]
        say("  " + ("PASS " if ok_c else "FAIL "), "%s %s" % (cid, detail))

    # THE ACCEPTANCE CRITERION for this leg: exactly one failure, and it is C5.
    # A leg that fails more than C5 proves nothing `duplicate-the-stock-character`
    # did not already prove, so refuse to bless it rather than harvest a leg that
    # would credit a substring it did not isolate.
    ok, why = CBV.acceptance(vector, "movement_values_exact",
                             "CHARRIG_MOVEMENT_WRONG ")
    say("VERDICT.isolates_C5_alone", ok)
    if not ok:
        say("DO NOT HARVEST", why)
        return

    # Harvest BEFORE the module-level cleanup deletes the staged asset. Doing it
    # here rather than by hand is the difference between a leg that is validated
    # and a leg that EXISTS: the first run of this script proved 5/6 isolating C5
    # and then deleted the asset, because printing "HARVEST OK" is not harvesting.
    substrate_task_dir = os.path.join(
        REPO_ROOT, "UE-projects", "ThirdPerson", "Content", "Tasks", TASK)
    try:
        dst = CBV.harvest(TASK_DIR, VARIANT_DIR, TASK, ("BP_TaskChar",),
                          substrate_task_dir)
    except CBV.AuthoringError as e:
        say("DO NOT HARVEST", str(e))
        return
    say("HARVESTED", dst)
    say("OK", why)


try:
    main()
except Exception as e:  # noqa: BLE001
    import traceback
    say("FATAL", "%s: %s" % (type(e).__name__, e))
    OUT.append(traceback.format_exc()[-700:])

print("R24-VARIANT-START")
for line in OUT:
    print(line)
print("R24-VARIANT-END")
sys.stdout.flush()

# Harvest happens OUTSIDE this script (copy the saved .uasset into the variant
# dir). Keep the staged asset only when asked, so a normal run leaves the
# project clean and the next leg can author at the same path.
if os.environ.get("CB_KEEP_STAGED") != "1":
    try:
        if unreal.EditorAssetLibrary.does_directory_exist(DIR):
            unreal.EditorAssetLibrary.delete_directory(DIR)
        print("cleanup done")
    except Exception as e:  # noqa: BLE001
        print("cleanup skipped: %r" % (e,))
sys.stdout.flush()
