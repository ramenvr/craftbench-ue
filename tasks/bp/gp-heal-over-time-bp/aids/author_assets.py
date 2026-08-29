# Authoring provenance for tasks/bp-g2/gp-heal-over-time-bp/reference/
# Content/Tasks/gp-heal-over-time-bp/{DT_HealthInit,BP_HealOverTimePawn,
# MMC_HealClamp,GE_HealOverTime,GA_HealOverTime}.uasset
#
# Spec: ../notes.md "Blueprint asset specification (the serial editor pass)".
# Shape cloned from the two shipped twins' aids scripts (gp-double-jump-
# stamina-bp, gp-health-attribute-ops-bp — both graded PASS 2026-08-11), plus
# the PORT-REPAIR half this task needs and they did not:
#
# THIS TASK'S ASSETS ARRIVE IN TWO LANES
# ======================================
#   native lane (this script authors from scratch):
#     DT_HealthInit    - DataTable, AttributeMetaData rows (<OwnerClass>.<Prop>
#                        row names — the load-bearing contract).
#     GE_HealOverTime  - HasDuration 5.0, Period 1.0, periodic-on-application
#                        OFF, one Health AddBase modifier whose magnitude is
#                        CustomCalculationClass = MMC_HealClamp_C.
#   ported lane (MCP-authored on CraftBenchTemplate, copied in, REPAIRED here):
#     BP_HealOverTimePawn - BeginPlay -> GetASC -> InitStats graph.
#     MMC_HealClamp       - CalculateBaseMagnitude override graph.
#     GA_HealOverTime     - ActivateAbility graph.
#
# THE PORT LEAVES THREE CLASSES OF TEMPLATE RESIDUE, EACH REPAIRED DIFFERENTLY:
#   1. IMPORTS (pawn parent class, InitStats' Attributes class-pin object) —
#      fixed by CoreRedirects at LOAD time. This script therefore requires the
#      TEMPORARY [CoreRedirects] block in Config/DefaultEngine.ini (appended by
#      the port step, reverted by git checkout right after this run — it must
#      never be committed; the graded substrate comes from git HEAD).
#   2. PIN-DEFAULT STRINGS (the MMC's two FGameplayAttribute struct pins) —
#      NOT imports, CoreRedirects do not touch them. Rewritten here via
#      BlueprintGraphPin.set_pin_value (measured available in 5.8, probe
#      2026-08-11).
#   3. CDO VALUES (tags, policy, captures, granted, mesh) — simply re-set here
#      with native ThirdPerson classes, same as the sibling scripts' repair
#      step. make_bp/load reuse the existing asset, so graphs are PRESERVED.
#
# Run headlessly against the ThirdPerson substrate:
#   %CB_UE_ROOT%\Engine\Binaries\Win64\UnrealEditor-Cmd.exe ^
#     <repo>\UE-projects\ThirdPerson\ThirdPerson.uproject ^
#     -ExecutePythonScript=<this file> -unattended -nopause -nosplash -RenderOffScreen
#
# RE-RUNNING IS THE REPAIR STEP, NOT A NO-OP — after ANY MCP graph pass, run
# this again and byte-verify (bp_agent dropped `ability_tags` once, 2026-08-11).

import unreal

TASK = "gp-heal-over-time-bp"
PKG = "/Game/Tasks/%s" % TASK

MESH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
ATTRSET = "/Script/ThirdPerson.CraftBenchAttributeSet"
TEMPLATE_ATTRSET = "/Script/CraftBenchTemplate.CraftBenchAttributeSet"

_tools = unreal.AssetToolsHelpers.get_asset_tools()
_eal = unreal.EditorAssetLibrary
_bel = unreal.BlueprintEditorLibrary


def die(msg):
    unreal.log_error("[%s] %s" % (TASK, msg))
    raise SystemExit(1)


def say(msg):
    unreal.log("[%s] %s" % (TASK, msg))


def load_class(path):
    cls = unreal.load_object(None, path)
    if cls is None:
        die("could not load class %s" % path)
    return cls


def cdo_of(bp):
    gc = bp.generated_class()
    if gc is None:
        die("blueprint %s has no generated class" % bp.get_name())
    return unreal.get_default_object(gc)


def tag_container(name):
    t = unreal.GameplayTag()
    t.import_text(name)
    return unreal.GameplayTagLibrary.add_gameplay_tag(
        unreal.GameplayTagContainer(), t)


# --------------------------------------------------------------------------- #
# 1. DT_HealthInit (native)                                                    #
# --------------------------------------------------------------------------- #
def author_datatable():
    path = "%s/DT_HealthInit" % PKG
    if _eal.does_asset_exist(path):
        say("reusing existing %s" % path)
        return _eal.load_asset(path)
    row_struct = unreal.load_object(None, "/Script/GameplayAbilities.AttributeMetaData")
    factory = unreal.DataTableFactory()
    factory.set_editor_property("struct", row_struct)
    dt = _tools.create_asset("DT_HealthInit", PKG, unreal.DataTable, factory)
    if dt is None:
        die("create_asset failed for DT_HealthInit")
    unreal.DataTableFunctionLibrary.fill_data_table_from_csv_string(dt, (
        "Name,BaseValue,MinValue,MaxValue,DerivedAttributeInfo,bCanStack\n"
        '"CraftBenchAttributeSet.Health","100.0","0.0","0.0","","False"\n'
        '"CraftBenchAttributeSet.MaxHealth","100.0","0.0","0.0","","False"\n'))
    names = [str(n) for n in unreal.DataTableFunctionLibrary.get_data_table_row_names(dt)]
    if sorted(names) != ["CraftBenchAttributeSet.Health", "CraftBenchAttributeSet.MaxHealth"]:
        die("DT rows wrong: %s" % names)
    say("DT_HealthInit: rows=%s" % names)
    return dt


# --------------------------------------------------------------------------- #
# 2. MMC_HealClamp (ported) — pin rewrite + CDO captures                       #
# --------------------------------------------------------------------------- #
def repair_mmc():
    path = "%s/MMC_HealClamp" % PKG
    bp = _eal.load_asset(path)
    if bp is None:
        die("ported MMC_HealClamp missing at %s" % path)

    # (2) template residue in the two FGameplayAttribute struct-pin DEFAULT
    # STRINGS — not imports, so CoreRedirects leave them alone. Rewrite by text.
    graph = _bel.find_graph(bp, "CalculateBaseMagnitude")
    if graph is None:
        die("MMC has no CalculateBaseMagnitude graph — port lost it")
    # EdGraph.Nodes is PROTECTED to Python (measured: this very script), so we
    # cannot enumerate. The capture nodes' OBJECT NAMES are known from the MCP
    # authoring pass (K2Node_CallFunction_0/_1, outer'd to the graph) — resolve
    # them directly.
    rewrote, remaining = 0, []
    for node_name in ("K2Node_CallFunction_0", "K2Node_CallFunction_1"):
        node = unreal.find_object(graph, node_name)
        if node is None:
            die("MMC capture node %s not found in graph — port changed names?"
                % node_name)
        pin = _bel.find_input_pin(node, "Attribute")
        if pin is None or not pin.is_valid():
            die("MMC node %s has no Attribute pin" % node_name)
        val = str(pin.get_pin_value())
        if "CraftBenchTemplate" in val:
            new_val = val.replace("CraftBenchTemplate", "ThirdPerson")
            pin.set_pin_value(new_val)
            rewrote += 1
            say("MMC pin rewritten: %s -> %s" % (val, new_val))
        elif "ThirdPerson" not in val:
            remaining.append("%s=%s" % (node_name, val))
    if remaining:
        die("MMC attribute pins unresolved after port: %s" % remaining)
    say("MMC pins: %d rewritten to ThirdPerson" % rewrote)

    # (3) CDO captures — Target source, bSnapshot=False on BOTH (a snapshotted
    # capture freezes Max-H at application time = the HOT-5 overshoot).
    cdo = cdo_of(bp)
    caps = []
    for attr in ("Health", "MaxHealth"):
        cap = unreal.GameplayEffectAttributeCaptureDefinition()
        t3d = ('(AttributeToCapture=(AttributeName="%s",AttributeOwner=Class\'"%s"\'),'
               'AttributeSource=Target,bSnapshot=False)' % (attr, ATTRSET))
        if not cap.import_text(t3d):
            die("capture import_text rejected for %s" % attr)
        caps.append(cap)
    cdo.set_editor_property("relevant_attributes_to_capture", caps)

    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    say("MMC_HealClamp: 2 Target/no-snapshot captures, graph preserved")
    return bp


# --------------------------------------------------------------------------- #
# 3. GE_HealOverTime (native) — HasDuration 5.0 / Period 1.0 / periodic-on-   #
#    application OFF / Health AddBase via CustomCalculationClass=MMC.         #
#    Recipe corrections from the 2026-08-11 python_agent research: duration   #
#    magnitude via struct import_text; period via get-modify-set.             #
# --------------------------------------------------------------------------- #
def author_effect(mmc_bp):
    path = "%s/GE_HealOverTime" % PKG
    if _eal.does_asset_exist(path):
        say("reusing existing %s" % path)
        bp = _eal.load_asset(path)
    else:
        factory = unreal.BlueprintFactory()
        factory.set_editor_property("parent_class",
                                    load_class("/Script/GameplayAbilities.GameplayEffect"))
        bp = _tools.create_asset("GE_HealOverTime", PKG, unreal.Blueprint, factory)
        if bp is None:
            die("create_asset failed for GE_HealOverTime")
    cdo = cdo_of(bp)
    cdo.set_editor_property("duration_policy", unreal.GameplayEffectDurationType.HAS_DURATION)
    mag = unreal.GameplayEffectModifierMagnitude()
    if not mag.import_text("(MagnitudeCalculationType=ScalableFloat,"
                           "ScalableFloatMagnitude=(Value=5.000000))"):
        die("duration magnitude import_text rejected")
    cdo.set_editor_property("duration_magnitude", mag)
    period = cdo.get_editor_property("period")
    period.set_editor_property("value", 1.0)
    cdo.set_editor_property("period", period)
    cdo.set_editor_property("execute_periodic_effect_on_application", False)
    mmc_cls_path = mmc_bp.generated_class().get_path_name()
    mod = unreal.GameplayModifierInfo()
    t3d = ('(Attribute=(AttributeName="Health",AttributeOwner=Class\'"%s"\'),'
           'ModifierOp=AddBase,'
           'ModifierMagnitude=(MagnitudeCalculationType=CustomCalculationClass,'
           'CustomMagnitude=(CalculationClassMagnitude=Class\'"%s"\','
           'Coefficient=(Value=1.000000),PreMultiplyAdditiveValue=(Value=0.000000),'
           'PostMultiplyAdditiveValue=(Value=0.000000))))' % (ATTRSET, mmc_cls_path))
    mod_obj = unreal.GameplayModifierInfo()
    if not mod_obj.import_text(t3d):
        die("GE modifier import_text rejected")
    cdo.set_editor_property("modifiers", [mod_obj])
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    chk = cdo_of(bp)
    say("GE_HealOverTime: policy=%s periodic_on_app=%s mods=%d (calc=%s)" % (
        chk.get_editor_property("duration_policy"),
        chk.get_editor_property("execute_periodic_effect_on_application"),
        len(chk.get_editor_property("modifiers")), mmc_cls_path))
    return bp


# --------------------------------------------------------------------------- #
# 4. GA_HealOverTime (ported) — CDO restore                                    #
# --------------------------------------------------------------------------- #
def repair_ability():
    path = "%s/GA_HealOverTime" % PKG
    bp = _eal.load_asset(path)
    if bp is None:
        die("ported GA_HealOverTime missing at %s" % path)
    cdo = cdo_of(bp)
    cdo.set_editor_property(
        "instancing_policy", unreal.GameplayAbilityInstancingPolicy.INSTANCED_PER_ACTOR)
    cdo.set_editor_property("ability_tags", tag_container("Ability.HealOverTime"))
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    say("GA_HealOverTime: InstancedPerActor, tag=Ability.HealOverTime, "
        "no cost/cooldown, graph preserved")
    return bp


# --------------------------------------------------------------------------- #
# 5. BP_HealOverTimePawn (ported) — CDO restore. Parent arrives re-pointed to  #
#    /Script/ThirdPerson.CraftBenchCharacter by the CoreRedirects.             #
# --------------------------------------------------------------------------- #
def repair_pawn(ga_bp):
    path = "%s/BP_HealOverTimePawn" % PKG
    bp = _eal.load_asset(path)
    if bp is None:
        die("ported BP_HealOverTimePawn missing at %s" % path)
    parent = _bel.get_blueprint_parent_class(bp)
    if parent is None or "ThirdPerson" not in parent.get_path_name():
        die("pawn parent did not redirect: %r — is the temp [CoreRedirects] "
            "block present in Config/DefaultEngine.ini?" % (
                parent.get_path_name() if parent else None))
    cdo = cdo_of(bp)
    cdo.set_editor_property("granted_abilities", [ga_bp.generated_class()])
    mesh_comp = cdo.get_editor_property("mesh")
    skm = _eal.load_asset(MESH)
    if mesh_comp is None or skm is None:
        die("pawn mesh component or SKM_Manny_Simple missing")
    mesh_comp.set_editor_property("skeletal_mesh_asset", skm)
    mesh_comp.set_editor_property("relative_location", unreal.Vector(0.0, 0.0, -90.0))
    mesh_comp.set_editor_property("relative_rotation", unreal.Rotator(0.0, -90.0, 0.0))
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    say("BP_HealOverTimePawn: parent=%s, granted=[GA_HealOverTime], "
        "mesh=SKM_Manny_Simple, BeginPlay graph preserved"
        % parent.get_name())
    return bp


def main():
    if not _eal.does_directory_exist(PKG):
        _eal.make_directory(PKG)
    dt = author_datatable()
    mmc = repair_mmc()
    ge = author_effect(mmc)
    ga = repair_ability()
    pawn = repair_pawn(ga)
    for asset in (dt, mmc, ge, ga, pawn):
        path = asset.get_path_name().split(".")[0]
        if not _eal.save_asset(path, only_if_is_dirty=False):
            die("save_asset failed for %s" % path)
        say("saved %s" % path)
    say("DONE - 5 assets finalized (2 native, 3 ported+repaired). "
        "NOW REVERT Config/DefaultEngine.ini (git checkout) before grading.")


main()
