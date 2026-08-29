# Authoring provenance for tasks/bp-g2/gp-double-jump-stamina-bp/reference/
# Content/Tasks/gp-double-jump-stamina-bp/{BP_DoubleJumpPawn,GE_DoubleJumpCost,
# GA_DoubleJump}.uasset
#
# Spec: ../notes.md "Blueprint asset specification (the serial editor pass)".
#
# WHAT THIS SCRIPT DOES AND DELIBERATELY DOES NOT DO
# ==================================================
# It authors everything that is a CDO / class-default property, which in UE 5.8
# Python is everything about these three assets EXCEPT the K2 event graph of
# GA_DoubleJump. There is no node-spawning / pin-wiring API in 5.8 Python
# (BlueprintEditorLibrary exposes compile/reparent/variables, not EdGraph
# surgery), which is why the shipped glide/poison -bp graphs were built by
# Aura's bp_agent in a LIVE editor and why the dfee504 headless port did CDO
# surgery + resave ONLY. So:
#
#   BP_DoubleJumpPawn   - COMPLETE here (spec says "no event graph").
#   GE_DoubleJumpCost   - COMPLETE here (data-only asset).
#   GA_DoubleJump       - CDO COMPLETE here (instancing policy, ability tag,
#                         cost GE class); its 7-node ActivateAbility graph is
#                         left EMPTY for the MCP pass. An ability with no graph
#                         never launches, so the reference FAILS until that pass
#                         runs. That is the intended, visible half-state - not a
#                         silent partial.
#
# Run headlessly against the ThirdPerson substrate (class bindings resolve
# natively there, so no CoreRedirect port is needed for what this script
# writes):
#
#   %CB_UE_ROOT%\Engine\Binaries\Win64\UnrealEditor-Cmd.exe ^
#     <repo>\UE-projects\ThirdPerson\ThirdPerson.uproject ^
#     -ExecutePythonScript=<this file> -unattended -nopause -nosplash -RenderOffScreen
#
# PREREQUISITE: ThirdPersonEditor must be BUILT (UnrealEditor-ThirdPerson.dll
# present), or load_class on ACraftBenchCharacter returns None.
#
# 5.8 API laws this script obeys (learned the hard way, see
# tasks/bp-g2/gp-glide-stamina-bp/REFERENCE-NOTE.md "authoring gotchas"):
#   * EGameplayModOp Additive is ADD_BASE in Python, not "Additive".
#   * GameplayTagLibrary.request_gameplay_tag / GameplayTagContainer.to_string
#     do NOT exist in 5.8 Python. Build tags with GameplayTag.import_text and
#     add them with GameplayTagLibrary.add_gameplay_tag.
#   * The ability's editor-facing tag property is `ability_tags`; `asset_tags`
#     is not a property of UGameplayAbility.

import unreal

TASK = "gp-double-jump-stamina-bp"
PKG = "/Game/Tasks/%s" % TASK

MESH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
ATTRSET = "/Script/ThirdPerson.CraftBenchAttributeSet"
ABILITY_TAG = "Ability.DoubleJump"
POWER_COST = -20.0
LAUNCH_Z = 600.0

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
    """Create (or reuse) a Blueprint asset with the given native parent."""
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
    """The class-default object whose properties ARE the asset's defaults."""
    gc = bp.generated_class()
    if gc is None:
        die("blueprint %s has no generated class" % bp.get_name())
    return unreal.get_default_object(gc)


def tag(name):
    t = unreal.GameplayTag()
    t.import_text(name)
    return t


def make_modifier(attr_name, owner_path, op, value):
    """A GameplayModifierInfo built by T3D text import.

    MEASURED 2026-08-11 (probe): GameplayModifierInfo and
    GameplayEffectModifierMagnitude expose ZERO editor properties to Python, and
    GameplayAttribute.attribute_name is READ-ONLY - so set_editor_property
    cannot build a modifier at all. import_text is not a stylistic choice here,
    it is the only route. Verified to round-trip: export_text came back with
    AttributeName="Power", the right AttributeOwner, ModifierOp=AddBase and
    ScalableFloatMagnitude.Value=-20.0.

    The struct's `Attribute=` (the raw FProperty pointer) stays EMPTY in the
    export; GAS re-resolves it from AttributeName+AttributeOwner on load, which
    is why the name and the owner are the two fields that must be right.
    """
    t3d = ('(Attribute=(AttributeName="%s",AttributeOwner=Class\'"%s"\'),'
           'ModifierOp=%s,'
           'ModifierMagnitude=(MagnitudeCalculationType=ScalableFloat,'
           'ScalableFloatMagnitude=(Value=%f)))'
           % (attr_name, owner_path, op, value))
    mod = unreal.GameplayModifierInfo()
    if not mod.import_text(t3d):
        die("GameplayModifierInfo.import_text rejected: %s" % t3d)
    return mod


# --------------------------------------------------------------------------- #
# 2. GE_DoubleJumpCost - instant, Power Add -20. Authored BEFORE the ability   #
#    because GA_DoubleJump's CostGameplayEffectClass references it.            #
# --------------------------------------------------------------------------- #
def author_cost_effect():
    bp = make_bp("GE_DoubleJumpCost", load_class("/Script/GameplayAbilities.GameplayEffect"))
    cdo = cdo_of(bp)
    cdo.set_editor_property("duration_policy", unreal.GameplayEffectDurationType.INSTANT)

    mod = make_modifier("Power", ATTRSET, "AddBase", POWER_COST)
    cdo.set_editor_property("modifiers", [mod])

    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    say("GE_DoubleJumpCost: Instant, Power ADD_BASE %.1f" % POWER_COST)
    return bp


# --------------------------------------------------------------------------- #
# 3. GA_DoubleJump - CDO only. The graph is the MCP pass's job.                #
# --------------------------------------------------------------------------- #
def author_ability(cost_bp):
    bp = make_bp("GA_DoubleJump", load_class("/Script/GameplayAbilities.GameplayAbility"))
    cdo = cdo_of(bp)
    cdo.set_editor_property(
        "instancing_policy", unreal.GameplayAbilityInstancingPolicy.INSTANCED_PER_ACTOR)

    container = unreal.GameplayTagContainer()
    container = unreal.GameplayTagLibrary.add_gameplay_tag(container, tag(ABILITY_TAG))
    cdo.set_editor_property("ability_tags", container)

    cost_class = cost_bp.generated_class()
    cdo.set_editor_property("cost_gameplay_effect_class", cost_class)

    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    # RE-RUNNING THIS IS THE REPAIR STEP, NOT JUST A NO-OP. make_bp REUSES an
    # existing asset, so this restores the CDO without touching the event graph
    # - which is exactly what the graph pass needs: Aura's bp_agent regenerates
    # the whole graph, and that DROPPED `ability_tags` (measured 2026-08-11: the
    # promoted asset had LaunchCharacter but no "Ability.DoubleJump" bytes).
    # The tag is not cosmetic - NumGrantedAbilitiesWithTag and
    # TryActivateAbilitiesByTag are how the fixture finds and fires this ability,
    # so losing it fails the task in a way that looks like the ability is absent.
    # Author graph -> re-run this -> byte-verify both.
    say("GA_DoubleJump: InstancedPerActor, tag=%s, cost=%s "
        "(CDO set; the event graph is authored separately via MCP and is "
        "PRESERVED by this script)"
        % (ABILITY_TAG, cost_class.get_name()))
    return bp


# --------------------------------------------------------------------------- #
# 1. BP_DoubleJumpPawn - complete here; spec says no event graph.             #
# --------------------------------------------------------------------------- #
def author_pawn(ability_bp):
    bp = make_bp("BP_DoubleJumpPawn", load_class("/Script/ThirdPerson.CraftBenchCharacter"))
    cdo = cdo_of(bp)
    cdo.set_editor_property("granted_abilities", [ability_bp.generated_class()])

    # The inherited Mesh component: the L2I pawn_visibly_represented check reads
    # this, and the -cpp twin's fixture spawns the pawn, so the mannequin must be
    # assigned exactly as the shipped -bp references do.
    mesh_comp = cdo.get_editor_property("mesh")
    if mesh_comp is None:
        die("CraftBenchCharacter CDO exposes no 'mesh' component")
    skm = _eal.load_asset(MESH)
    if skm is None:
        die("skeletal mesh missing at %s" % MESH)
    mesh_comp.set_editor_property("skeletal_mesh_asset", skm)
    mesh_comp.set_editor_property("relative_location", unreal.Vector(0.0, 0.0, -90.0))
    mesh_comp.set_editor_property("relative_rotation", unreal.Rotator(0.0, -90.0, 0.0))

    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    say("BP_DoubleJumpPawn: granted=[GA_DoubleJump], mesh=SKM_Manny_Simple")
    return bp


def main():
    if not _eal.does_directory_exist(PKG):
        _eal.make_directory(PKG)
    cost = author_cost_effect()
    ability = author_ability(cost)
    pawn = author_pawn(ability)
    for bp in (cost, ability, pawn):
        path = bp.get_path_name().split(".")[0]
        if not _eal.save_asset(path, only_if_is_dirty=False):
            die("save_asset failed for %s" % path)
        say("saved %s" % path)
    say("DONE - 3 assets authored; GA_DoubleJump's event graph is still empty.")


main()
