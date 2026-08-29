"""Author both discrimination variants for kp-typed-input-bindings (one boot).

    UnrealEditor-Cmd.exe <repo>/UE-projects/ThirdPerson/ThirdPerson.uproject
        -ExecutePythonScript=<this file> -nullrhi -unattended -nosplash -stdout

  zoom-left-boolean/       IA_Zoom never typed        -> fails ONLY ia_zoom_reads_axis1d
  s-swizzled-not-negated/  S keeps swizzle, no negate -> fails ONLY map_s_move_swizzled_negated

All legs share the same four content paths, so they are authored serially:
build -> self-grade -> harvest -> delete -> next. Asset tasks can do that in one boot;
level tasks cannot (see the level scripts).

Helpers come from this task's own author_reference.py via
cb_variant_lib.load_reference_helpers, which exec's it WITHOUT running its main() --
copying it would let the copy drift from the grader it was calibrated against. The
self-grade is a GATE, not a report: a leg is harvested only when its failure set
equals exactly the one check it targets.
"""
import os
import sys

import unreal  # noqa: F401 - required by the exec'd reference source

_HERE = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.abspath(os.path.join(_HERE, ".."))
REPO_ROOT = os.path.abspath(os.path.join(TASK_DIR, "..", "..", ".."))
REFERENCE_AUTHOR = os.path.join(_HERE, "author_reference.py")

# The shared authoring machinery — loader, acceptance gate, harvest. Unit-tested
# off-box at tools/authoring/tests/, which is where its tail-shape handling was
# proven; do NOT re-implement any of it per task.
sys.path.insert(0, os.path.join(REPO_ROOT, "tools", "authoring"))
import cb_variant_lib as CBV  # noqa: E402

MARK = "KPEIM-VARIANTS"


def log(msg):
    print("%s %s" % (MARK, msg))


def die(msg):
    print("%s-ERROR %s" % (MARK, msg))
    sys.stdout.flush()
    raise SystemExit(1)


try:
    R = CBV.load_reference_helpers(REFERENCE_AUTHOR, [
        "EAL", "set_prop", "read_prop", "_cls", "create_data_asset", "make_key",
        "make_modifier", "make_mapping", "save_asset", "grade_in_process",
        "PKG_DIR", "ASSET_NAMES", "TASK_ID", "SUBSTRATE_TASK_DIR",
        "ACTION_MOVE", "ACTION_ZOOM", "ACTION_JUMP", "CONTEXT_ASSET"])
except CBV.AuthoringError as e:
    die(str(e))
EAL = R["EAL"]
PKG_DIR = R["PKG_DIR"]
TASK_ID = R["TASK_ID"]
ASSET_NAMES = R["ASSET_NAMES"]
ALL_PATHS = (R["ACTION_MOVE"], R["ACTION_ZOOM"], R["ACTION_JUMP"],
             R["CONTEXT_ASSET"])


def build(zoom_typed=True, negate_s=True):
    """Author the four assets. The two keyword flags ARE the variant deltas."""
    input_action_cls = R["_cls"]("InputAction")
    context_cls = R["_cls"]("InputMappingContext")
    value_type_enum = R["_cls"]("InputActionValueType")

    ia_move = R["create_data_asset"]("IA_Move", input_action_cls)
    ia_zoom = R["create_data_asset"]("IA_Zoom", input_action_cls)
    ia_jump = R["create_data_asset"]("IA_Jump", input_action_cls)

    axis2d = getattr(value_type_enum, "AXIS2_D",
                     getattr(value_type_enum, "AXIS2D", None))
    axis1d = getattr(value_type_enum, "AXIS1_D",
                     getattr(value_type_enum, "AXIS1D", None))
    boolean = getattr(value_type_enum, "BOOLEAN", None)
    if axis2d is None or axis1d is None or boolean is None:
        die("InputActionValueType entries not found")

    R["set_prop"](ia_move, axis2d, "value_type", "ValueType", "action_value_type")
    if zoom_typed:
        R["set_prop"](ia_zoom, axis1d, "value_type", "ValueType",
                      "action_value_type")
    # else: left at the engine default (Boolean) — the whole delta of variant 1.
    R["set_prop"](ia_jump, boolean, "value_type", "ValueType", "action_value_type")

    imc = R["create_data_asset"]("IMC_Bindings", context_cls)

    def swizzle():
        mod = R["make_modifier"]("InputModifierSwizzleAxis", imc)
        order_enum = R["_cls"]("InputAxisSwizzle")
        yxz = getattr(order_enum, "YXZ", None)
        if yxz is None:
            die("InputAxisSwizzle.YXZ not found")
        R["set_prop"](mod, yxz, "order", "Order")
        return mod

    def negate():
        return R["make_modifier"]("InputModifierNegate", imc)

    s_chain = [swizzle(), negate()] if negate_s else [swizzle()]
    mappings = [
        R["make_mapping"](ia_move, "W", [swizzle()]),
        R["make_mapping"](ia_move, "S", s_chain),
        R["make_mapping"](ia_move, "A", []),
        R["make_mapping"](ia_move, "D", []),
        R["make_mapping"](ia_zoom, "MouseWheelAxis", []),
        R["make_mapping"](ia_jump, "SpaceBar", []),
    ]
    R["set_prop"](imc, mappings, "mappings", "Mappings")
    got = list(R["read_prop"](imc, "mappings", "Mappings") or [])
    if len(got) != 6:
        die("mapping array read back %d entries, wanted 6" % len(got))

    for path in ALL_PATHS:
        R["save_asset"](path)


def clean():
    for path in ALL_PATHS:
        if EAL.does_asset_exist(path):
            EAL.delete_asset(path)
    try:
        EAL.delete_directory(PKG_DIR)
    except Exception:  # noqa: BLE001 - best effort; the task ships no folder
        pass
    for path in ALL_PATHS:
        if EAL.does_asset_exist(path):
            die("asset still exists after delete: %s" % path)


def harvest(variant):
    dst = CBV.harvest(TASK_DIR, variant, TASK_ID, ASSET_NAMES,
                      R["SUBSTRATE_TASK_DIR"])
    log("HARVESTED %s -> %s" % (variant, dst))


#: (variant dir, build kwargs, the ONE check it must fail, its credited substring)
VARIANTS = (
    ("zoom-left-boolean", {"zoom_typed": False}, "ia_zoom_reads_axis1d",
     "IA_ZOOM_VALUE_TYPE_WRONG value_type="),
    ("s-swizzled-not-negated", {"negate_s": False}, "map_s_move_swizzled_negated",
     "MAP_S_MODIFIER_CHAIN_WRONG chain="),
)


def main():
    if any(EAL.does_asset_exist(p) for p in ALL_PATHS):
        die("substrate already carries %s content — clean via git first "
            "(renames leave registry tombstones)" % PKG_DIR)

    harvested, refused = [], []
    for variant, kwargs, target, substring in VARIANTS:
        log("=== %s (delta %s) ===" % (variant, kwargs))
        build(**kwargs)
        vector = R["grade_in_process"]()
        passed, total = CBV.score(vector)
        fails = sorted(cid for cid, (ok, _) in vector.items() if not ok)
        log("%s graded %d/%d fails=%s" % (variant, passed, total, fails))
        for cid in fails:
            log("  FAIL-DETAIL %s %s" % (cid, vector[cid][1]))

        ok, why = CBV.acceptance(vector, target, substring)
        if ok:
            try:
                harvest(variant)
                harvested.append(variant)
                log("OK %s %s" % (variant, why))
            except CBV.AuthoringError as e:
                refused.append(variant)
                log("DO NOT HARVEST %s — %s" % (variant, e))
        else:
            refused.append(variant)
            log("DO NOT HARVEST %s — %s" % (variant, why))
        clean()

    log("SUMMARY harvested=%s refused=%s" % (harvested, refused))
    log("DONE" if not refused else "DONE-WITH-REFUSALS")


def _cleanup_after_failure():
    """Best-effort substrate cleanup on the failure path."""
    try:
        clean()
        print("%s cleaned up after failure" % MARK)
    except Exception:  # noqa: BLE001
        print("%s CLEANUP FAILED — check the substrate by hand" % MARK)



try:
    main()
except SystemExit:
    # A die() — ours or the reference author's — raises SystemExit. Re-raising it
    # WITHOUT cleaning left authored assets in the substrate, and an untracked
    # directory there makes a certifying sweep certify NOTHING (the cert key covers
    # the substrate tree and identities are computed before the loop). Measured
    # 2026-08-18: one failed leg left Content/Tasks/<id>/ behind and the next
    # sweep had to be killed and restarted. So clean, THEN re-raise.
    try:
        _cleanup_after_failure()
    finally:
        raise
except Exception as e:  # noqa: BLE001
    import traceback
    print("%s-ERROR %s: %s" % (MARK, type(e).__name__, e))
    print(traceback.format_exc()[-1200:])
    try:
        clean()
        print("%s cleaned up after failure" % MARK)
    except Exception:  # noqa: BLE001
        print("%s CLEANUP ALSO FAILED — check the substrate by hand" % MARK)
sys.stdout.flush()
