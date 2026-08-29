# One-delta discrimination-variant authoring for the three 2026-08-11 -bp twins.
# Driven by env vars (a -ExecutePythonScript run takes no argv):
#   CB_TASK  = task id (gp-double-jump-stamina-bp | gp-health-attribute-ops-bp
#              | gp-heal-over-time-bp)
#   CB_DELTA = delta name (see DELTAS below)
#
# CONTRACT: the driver copies the PRISTINE reference .uassets into the
# substrate's Content/Tasks/<task>/ BEFORE this runs; this script applies
# exactly ONE delta, compiles, saves, and read-back-verifies. The driver then
# copies the whole asset set OUT to discrimination/<variant>/Content/Tasks/
# <task>/ and deletes the substrate copies. Per-variant editor boots on
# purpose: every variant starts from pristine files, so no hand-rolled inverse
# ("restore") step can ever leave the substrate dirty — the false-FAIL class
# this repo keeps re-learning about (see FAILURE-LOG).
#
# Each delta mirrors its MATRIX.md "planned as" cell; the expected named-FAIL
# substring is that file's row. Nothing here invents a new axis.

import os
import unreal

TASK = os.environ["CB_TASK"]
DELTA = os.environ["CB_DELTA"]
PKG = "/Game/Tasks/%s" % TASK
ATTRSET = "/Script/ThirdPerson.CraftBenchAttributeSet"

_eal = unreal.EditorAssetLibrary
_bel = unreal.BlueprintEditorLibrary


def die(msg):
    unreal.log_error("[variant %s/%s] %s" % (TASK, DELTA, msg))
    raise SystemExit(1)


def say(msg):
    unreal.log("[variant %s/%s] %s" % (TASK, DELTA, msg))


def load_bp(name):
    bp = _eal.load_asset("%s/%s" % (PKG, name))
    if bp is None:
        die("asset missing: %s/%s (driver forgot the pristine copy-in?)" % (PKG, name))
    return bp


def cdo_of(bp):
    return unreal.get_default_object(bp.generated_class())


def compile_save(bp, name):
    _bel.compile_blueprint(bp)
    if not _eal.save_asset("%s/%s" % (PKG, name), only_if_is_dirty=False):
        die("save failed for %s" % name)


def clear_mesh(pawn_name):
    """bp-no-mesh (all three tasks): the visibility axis alone."""
    bp = load_bp(pawn_name)
    mesh = cdo_of(bp).get_editor_property("mesh")
    mesh.set_editor_property("skeletal_mesh_asset", None)
    compile_save(bp, pawn_name)
    back = cdo_of(bp).get_editor_property("mesh").get_editor_property("skeletal_mesh_asset")
    if back is not None:
        die("mesh did not clear: %r" % back)
    say("mesh cleared on %s" % pawn_name)


def set_cost_magnitude(value):
    """DJ bp-free-jump (0.0: debit removed, commit machinery KEPT) /
    bp-wrong-cost (-35.0: perfectly one-shot debit of a non-disclosed size)."""
    bp = load_bp("GE_DoubleJumpCost")
    cdo = cdo_of(bp)
    mod = unreal.GameplayModifierInfo()
    t3d = ('(Attribute=(AttributeName="Power",AttributeOwner=Class\'"%s"\'),'
           'ModifierOp=AddBase,'
           'ModifierMagnitude=(MagnitudeCalculationType=ScalableFloat,'
           'ScalableFloatMagnitude=(Value=%f)))' % (ATTRSET, value))
    if not mod.import_text(t3d):
        die("modifier import_text rejected")
    cdo.set_editor_property("modifiers", [mod])
    compile_save(bp, "GE_DoubleJumpCost")
    back = cdo_of(bp).get_editor_property("modifiers")[0].export_text()
    if ("Value=%f" % value).rstrip("0").rstrip(".") not in back.replace("000000", ""):
        say("read-back: %s" % back[:200])
    say("cost magnitude -> %.1f" % value)


def reparent_generic():
    """HO bp-generic-pawn: reparent to the GENERIC CraftBenchCharacter — the
    pre-built attribute set comes along, so the stage-1 derivation gate (HO-1)
    fails by name. Everything else carried."""
    bp = load_bp("BP_HealthOpsPawn")
    parent = unreal.load_object(None, "/Script/ThirdPerson.CraftBenchCharacter")
    _bel.reparent_blueprint(bp, parent)
    compile_save(bp, "BP_HealthOpsPawn")
    back = _bel.get_blueprint_parent_class(bp)
    if back is None or back.get_name() != "CraftBenchCharacter":
        die("reparent did not take: %r" % back)
    say("reparented to generic CraftBenchCharacter")


def drop_starting_data():
    """HO bp-no-health-system: attribute-set wiring removed — registered set
    never exists, HO-2 presence fails by name."""
    bp = load_bp("BP_HealthOpsPawn")
    asc = cdo_of(bp).get_editor_property("ability_system_component")
    asc.set_editor_property("default_starting_data", [])
    compile_save(bp, "BP_HealthOpsPawn")
    back = cdo_of(bp).get_editor_property("ability_system_component") \
                     .get_editor_property("default_starting_data")
    if len(back) != 0:
        die("DefaultStartingData not emptied: %r" % back)
    say("DefaultStartingData emptied")


def drop_maxhealth_row():
    """HOT bp-no-maxhealth: MaxHealth init removed, Health kept — HOT-0 fails
    by name before any behavioral gate."""
    dt = _eal.load_asset("%s/DT_HealthInit" % PKG)
    unreal.DataTableFunctionLibrary.fill_data_table_from_csv_string(dt, (
        "Name,BaseValue,MinValue,MaxValue,DerivedAttributeInfo,bCanStack\n"
        '"CraftBenchAttributeSet.Health","100.0","0.0","0.0","","False"\n'))
    names = [str(n) for n in unreal.DataTableFunctionLibrary.get_data_table_row_names(dt)]
    if names != ["CraftBenchAttributeSet.Health"]:
        die("row drop failed: %s" % names)
    if not _eal.save_asset("%s/DT_HealthInit" % PKG, only_if_is_dirty=False):
        die("DT save failed")
    say("DT rows now %s" % names)


def make_instant():
    """HOT bp-instant: whole amount applied once — policy Instant, magnitude a
    flat 25.0 (mid-band, so HOT-4's total gate cannot take the credit and the
    rise-step gate HOT-2 is what names the failure)."""
    bp = load_bp("GE_HealOverTime")
    cdo = cdo_of(bp)
    cdo.set_editor_property("duration_policy", unreal.GameplayEffectDurationType.INSTANT)
    mod = unreal.GameplayModifierInfo()
    t3d = ('(Attribute=(AttributeName="Health",AttributeOwner=Class\'"%s"\'),'
           'ModifierOp=AddBase,'
           'ModifierMagnitude=(MagnitudeCalculationType=ScalableFloat,'
           'ScalableFloatMagnitude=(Value=25.000000)))' % ATTRSET)
    if not mod.import_text(t3d):
        die("modifier import_text rejected")
    cdo.set_editor_property("modifiers", [mod])
    compile_save(bp, "GE_HealOverTime")
    back = cdo_of(bp)
    if back.get_editor_property("duration_policy") != unreal.GameplayEffectDurationType.INSTANT:
        die("policy did not switch to INSTANT")
    say("GE now Instant, flat +25.0")


DELTAS = {
    ("gp-double-jump-stamina-bp", "bp-no-mesh"): lambda: clear_mesh("BP_DoubleJumpPawn"),
    ("gp-double-jump-stamina-bp", "bp-free-jump"): lambda: set_cost_magnitude(0.0),
    ("gp-double-jump-stamina-bp", "bp-wrong-cost"): lambda: set_cost_magnitude(-35.0),
    ("gp-health-attribute-ops-bp", "bp-generic-pawn"): reparent_generic,
    ("gp-health-attribute-ops-bp", "bp-no-health-system"): drop_starting_data,
    ("gp-health-attribute-ops-bp", "bp-no-mesh"): lambda: clear_mesh("BP_HealthOpsPawn"),
    ("gp-heal-over-time-bp", "bp-no-maxhealth"): drop_maxhealth_row,
    ("gp-heal-over-time-bp", "bp-no-mesh"): lambda: clear_mesh("BP_HealOverTimePawn"),
    ("gp-heal-over-time-bp", "bp-instant"): make_instant,
}

fn = DELTAS.get((TASK, DELTA))
if fn is None:
    die("unknown (task, delta): %r" % [(TASK, DELTA)])
fn()
say("DELTA APPLIED OK")
