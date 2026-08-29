# Authoring provenance for tasks/bp-g2/gp-health-attribute-ops-bp/reference/
# Content/Tasks/gp-health-attribute-ops-bp/{DT_HealthInit,BP_HealthOpsPawn,
# GE_Damage,GE_Heal,GA_Damage,GA_Heal}.uasset
#
# Spec: ../notes.md "Blueprint asset specification (the serial editor pass)".
# Shape cloned from ../../gp-double-jump-stamina-bp/aids/author_assets.py, the
# script that authored the first shipped twin (graded PASS 2026-08-11).
#
# WHAT THIS SCRIPT DOES AND DELIBERATELY DOES NOT DO
# ==================================================
# Everything that is a CDO / data property — which for this task is FOUR of the
# six assets in full, plus the CDO half of the two abilities:
#
#   DT_HealthInit    - COMPLETE here (DataTable, AttributeMetaData rows).
#   BP_HealthOpsPawn - COMPLETE here (spec: "No event graph is needed").
#   GE_Damage        - COMPLETE here (data-only).
#   GE_Heal          - COMPLETE here (data-only).
#   GA_Damage        - CDO here (policy, Ability.Damage tag, NO cost); its
#                      4-node ActivateAbility graph is the MCP pass's job.
#   GA_Heal          - same, with Ability.Heal.
#
# RE-RUNNING THIS IS THE REPAIR STEP AFTER THE GRAPH PASS, NOT JUST A NO-OP:
# make_bp REUSES an existing asset, so this restores the CDO without touching
# the event graph. Aura's bp_agent regenerates whole graphs and DROPPED
# `ability_tags` on gp-double-jump-stamina-bp (measured 2026-08-11); the tags
# are how the fixture finds and fires these abilities. Author graphs -> re-run
# this -> byte-verify both.
#
# Run headlessly against the ThirdPerson substrate (class bindings resolve
# natively — the shipped DJ twin proved no CoreRedirect port is needed):
#
#   %CB_UE_ROOT%\Engine\Binaries\Win64\UnrealEditor-Cmd.exe ^
#     <repo>\UE-projects\ThirdPerson\ThirdPerson.uproject ^
#     -ExecutePythonScript=<this file> -unattended -nopause -nosplash -RenderOffScreen
#
# 5.8 API laws obeyed (measured on the DJ twin, 2026-08-11):
#   * GameplayModifierInfo exposes ZERO editor properties to Python and
#     GameplayAttribute.attribute_name is READ-ONLY — T3D import_text is the
#     only way to build a modifier. Verified to round-trip.
#   * EGameplayModOp Additive is the token "AddBase" in T3D.
#   * Tags: GameplayTag.import_text + GameplayTagLibrary.add_gameplay_tag; the
#     ability's property is `ability_tags`.

import unreal

TASK = "gp-health-attribute-ops-bp"
PKG = "/Game/Tasks/%s" % TASK

MESH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
ATTRSET = "/Script/ThirdPerson.CraftBenchAttributeSet"
DAMAGE = -10.0
HEAL = 10.0

_tools = unreal.AssetToolsHelpers.get_asset_tools()
_eal = unreal.EditorAssetLibrary


def die(msg):
    unreal.log_error("[%s] %s" % (TASK, msg))
    raise SystemExit(1)


def say(msg):
    unreal.log("[%s] %s" % (TASK, msg))


def load_class(path):
    cls = unreal.load_object(None, path)
    if cls is None:
        die("could not load class %s (is the project built?)" % path)
    return cls


def make_bp(name, parent_class):
    path = "%s/%s" % (PKG, name)
    if _eal.does_asset_exist(path):
        say("reusing existing %s" % path)
        return _eal.load_asset(path)
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", parent_class)
    bp = _tools.create_asset(name, PKG, unreal.Blueprint, factory)
    if bp is None:
        die("create_asset failed at %s" % path)
    say("created %s (parent %s)" % (path, parent_class.get_name()))
    return bp


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


def make_modifier(attr_name, op, value):
    """T3D-imported modifier — see the API law block in the header."""
    t3d = ('(Attribute=(AttributeName="%s",AttributeOwner=Class\'"%s"\'),'
           'ModifierOp=%s,'
           'ModifierMagnitude=(MagnitudeCalculationType=ScalableFloat,'
           'ScalableFloatMagnitude=(Value=%f)))'
           % (attr_name, ATTRSET, op, value))
    mod = unreal.GameplayModifierInfo()
    if not mod.import_text(t3d):
        die("GameplayModifierInfo.import_text rejected: %s" % t3d)
    return mod


# --------------------------------------------------------------------------- #
# 1. DT_HealthInit — AttributeMetaData rows. THE ROW-NAME CONTRACT IS          #
#    LOAD-BEARING: InitFromMetaDataTable keys rows as <OwnerClass>.<Property>; #
#    a bare "Health" row reads back as "registered but never initialized" and  #
#    produces a stage-1 HO-3 FAIL that looks like the agent forgot to init.    #
# --------------------------------------------------------------------------- #
def author_datatable():
    path = "%s/DT_HealthInit" % PKG
    if _eal.does_asset_exist(path):
        say("reusing existing %s" % path)
        return _eal.load_asset(path)
    row_struct = unreal.load_object(None, "/Script/GameplayAbilities.AttributeMetaData")
    if row_struct is None:
        die("AttributeMetaData row struct not found")
    factory = unreal.DataTableFactory()
    factory.set_editor_property("struct", row_struct)
    dt = _tools.create_asset("DT_HealthInit", PKG, unreal.DataTable, factory)
    if dt is None:
        die("create_asset failed for DT_HealthInit")
    csv = (
        "Name,BaseValue,MinValue,MaxValue,DerivedAttributeInfo,bCanStack\n"
        '"CraftBenchAttributeSet.Health","100.0","0.0","0.0","","False"\n'
        '"CraftBenchAttributeSet.MaxHealth","100.0","0.0","0.0","","False"\n'
    )
    problems = unreal.DataTableFunctionLibrary.fill_data_table_from_csv_string(dt, csv)
    # fill_* returns True on success in 5.8; be tolerant of either contract but
    # ALWAYS verify by reading the row names back — that is the real assert.
    names = [str(n) for n in unreal.DataTableFunctionLibrary.get_data_table_row_names(dt)]
    expected = ["CraftBenchAttributeSet.Health", "CraftBenchAttributeSet.MaxHealth"]
    if sorted(names) != sorted(expected):
        die("DT rows wrong: got %s (fill returned %r)" % (names, problems))
    say("DT_HealthInit: rows=%s" % names)
    return dt


# --------------------------------------------------------------------------- #
# 2+3. GE_Damage / GE_Heal — instant, Health AddBase -10 / +10.               #
# --------------------------------------------------------------------------- #
def author_effect(name, magnitude):
    bp = make_bp(name, load_class("/Script/GameplayAbilities.GameplayEffect"))
    cdo = cdo_of(bp)
    cdo.set_editor_property("duration_policy", unreal.GameplayEffectDurationType.INSTANT)
    cdo.set_editor_property("modifiers", [make_modifier("Health", "AddBase", magnitude)])
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    say("%s: Instant, Health ADD_BASE %+.1f" % (name, magnitude))
    return bp


# --------------------------------------------------------------------------- #
# 4+5. GA_Damage / GA_Heal — CDO only. NO cost, NO cooldown: the fixture       #
#    activates the damage ability twice 0.7s apart, and anything held open     #
#    refuses the second activation (HO-6 would FAIL conforming work).          #
# --------------------------------------------------------------------------- #
def author_ability(name, tag_name):
    bp = make_bp(name, load_class("/Script/GameplayAbilities.GameplayAbility"))
    cdo = cdo_of(bp)
    cdo.set_editor_property(
        "instancing_policy", unreal.GameplayAbilityInstancingPolicy.INSTANCED_PER_ACTOR)
    cdo.set_editor_property("ability_tags", tag_container(tag_name))
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    say("%s: InstancedPerActor, tag=%s, no cost/cooldown "
        "(CDO set; the event graph is authored separately via MCP and is "
        "PRESERVED by this script)" % (name, tag_name))
    return bp


# --------------------------------------------------------------------------- #
# 6. BP_HealthOpsPawn — parent CraftBenchBareCharacter (ABSTRACT native base:  #
#    the bare lineage suppresses the attribute-set subobject, so the           #
#    DefaultStartingData entry below is the ONLY set ever created — the whole  #
#    of stage 1 on the no-C++ lane, the route the poison -bp twin proved).     #
# --------------------------------------------------------------------------- #
def author_pawn(dt, ability_bps):
    bp = make_bp("BP_HealthOpsPawn", load_class("/Script/ThirdPerson.CraftBenchBareCharacter"))
    cdo = cdo_of(bp)

    asc = cdo.get_editor_property("ability_system_component")
    if asc is None:
        die("pawn CDO exposes no ability_system_component")
    entry = unreal.AttributeDefaults()
    try:
        entry.set_editor_property("attributes", load_class(ATTRSET))
        entry.set_editor_property("default_starting_table", dt)
    except Exception:
        # Same read-only trap class as GameplayAttribute — fall back to T3D.
        t3d = ('(Attributes=Class\'"%s"\',DefaultStartingTable=DataTable\'"%s.%s"\')'
               % (ATTRSET, "%s/DT_HealthInit" % PKG, "DT_HealthInit"))
        if not entry.import_text(t3d):
            die("AttributeDefaults not settable by property OR import_text")
    asc.set_editor_property("default_starting_data", [entry])

    cdo.set_editor_property(
        "granted_abilities", [b.generated_class() for b in ability_bps])

    mesh_comp = cdo.get_editor_property("mesh")
    if mesh_comp is None:
        die("pawn CDO exposes no 'mesh' component")
    skm = _eal.load_asset(MESH)
    if skm is None:
        die("skeletal mesh missing at %s" % MESH)
    mesh_comp.set_editor_property("skeletal_mesh_asset", skm)
    mesh_comp.set_editor_property("relative_location", unreal.Vector(0.0, 0.0, -90.0))
    mesh_comp.set_editor_property("relative_rotation", unreal.Rotator(0.0, -90.0, 0.0))

    unreal.BlueprintEditorLibrary.compile_blueprint(bp)

    # Read-back assert: DefaultStartingData survived the compile (a BP compile
    # regenerates the class; a value that only lived pre-compile is the kind of
    # silent loss this task's stage 1 would misread as "never initialized").
    asc2 = cdo_of(bp).get_editor_property("ability_system_component")
    dsd = list(asc2.get_editor_property("default_starting_data"))
    if len(dsd) != 1:
        die("DefaultStartingData did not survive compile: %r" % dsd)
    say("BP_HealthOpsPawn: DefaultStartingData=1 entry (%s + DT_HealthInit), "
        "granted=[GA_Damage, GA_Heal], mesh=SKM_Manny_Simple"
        % load_class(ATTRSET).get_name())
    return bp


def main():
    if not _eal.does_directory_exist(PKG):
        _eal.make_directory(PKG)
    dt = author_datatable()
    ge_damage = author_effect("GE_Damage", DAMAGE)
    ge_heal = author_effect("GE_Heal", HEAL)
    ga_damage = author_ability("GA_Damage", "Ability.Damage")
    ga_heal = author_ability("GA_Heal", "Ability.Heal")
    pawn = author_pawn(dt, [ga_damage, ga_heal])
    for asset in (dt, ge_damage, ge_heal, ga_damage, ga_heal, pawn):
        path = asset.get_path_name().split(".")[0]
        if not _eal.save_asset(path, only_if_is_dirty=False):
            die("save_asset failed for %s" % path)
        say("saved %s" % path)
    say("DONE - 6 assets authored; GA_Damage/GA_Heal event graphs are the "
        "MCP pass's job.")


main()
