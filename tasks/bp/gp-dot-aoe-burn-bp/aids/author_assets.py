# Authoring provenance for tasks/bp-g2/gp-dot-aoe-burn-bp/reference/
# Content/Tasks/gp-dot-aoe-burn-bp/{BP_AoeBurnPawn,GA_AoeBurn,GE_AoeBurnTick}.uasset
#
# Spec: ../task.md "Reference solution metadata". Two-lane recipe, proven on the
# three 2026-08-11 twins (read any of their REFERENCE-NOTE.md first):
#   MCP lane (CraftBenchTemplate)  - the K2 graph, which 5.8 Python cannot author
#   headless lane (THIS script)    - every CDO/data property, plus the PORT REPAIR
#
# RE-RUNNING THIS IS THE REPAIR STEP, NOT A NO-OP. Aura's graph tools regenerate
# whole graphs and have DROPPED `ability_tags` before (measured 2026-08-11 on
# gp-double-jump-stamina-bp). Author graph -> run this -> byte-verify both.
#
# THIS FAMILY'S PORT RESIDUE, and why it is worse than the siblings':
# the ability's SphereOverlapActors node carries an `ActorClassFilter` PIN whose
# value is a CLASS REFERENCE. On the template that literal is
# /Script/CraftBenchTemplate.CraftBenchCharacter. A class pin default is a real
# object import, so the temporary [CoreRedirects] block re-points it on load -
# but the heal-over-time family proved that some pin literals get NO fix-up
# (its FGameplayAttribute pins kept an empty field path and healed 0.00 per
# period). So this script ASSERTS the filter after load rather than assuming:
# a filter still pointing at the template class would make the reference burn
# nothing, and AB-2 would report "the burn was not periodic" - a true statement
# about a symptom whose cause is the port, not the solve.
#
# Run headlessly against the ThirdPerson substrate, WITH the temporary
# [CoreRedirects] block in Config/DefaultEngine.ini (appended by the port step,
# reverted by `git checkout` immediately after this run - it must never be
# committed; the graded substrate materializes from git HEAD):
#
#   %CB_UE_ROOT%\Engine\Binaries\Win64\UnrealEditor-Cmd.exe ^
#     <repo>\UE-projects\ThirdPerson\ThirdPerson.uproject ^
#     -ExecutePythonScript=<this file> -unattended -nopause -nosplash -RenderOffScreen

import unreal

TASK = "gp-dot-aoe-burn-bp"
PKG = "/Game/Tasks/%s" % TASK
MESH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
ATTRSET = "/Script/ThirdPerson.CraftBenchAttributeSet"
ABILITY_TAG = "Ability.AoeBurn"
BURN_PER_TICK = -5.0

_eal = unreal.EditorAssetLibrary
_bel = unreal.BlueprintEditorLibrary


def die(msg):
    unreal.log_error("[%s] %s" % (TASK, msg))
    raise SystemExit(1)


def say(msg):
    unreal.log("[%s] %s" % (TASK, msg))


def load(name):
    bp = _eal.load_asset("%s/%s" % (PKG, name))
    if bp is None:
        die("asset missing: %s/%s (did the port copy-in run?)" % (PKG, name))
    return bp


def cdo_of(bp):
    return unreal.get_default_object(bp.generated_class())


# --------------------------------------------------------------------------- #
# GE_AoeBurnTick - HasDuration 5.0 / Period 1.0 / periodic-on-application ON.
# Six executions over five seconds (the flag makes N seconds of a 1 s period
# N+1 executions - the V1.1 header's warning), which is the -cpp reference's
# MEASURED total of 30 at -5.0 a tick. Recipe corrections from the 2026-08-11
# research: duration magnitude via struct import_text (the kwarg ctor throws),
# period via get-modify-set (a fresh bare ScalableFloat throws).
# --------------------------------------------------------------------------- #
def repair_effect():
    bp = load("GE_AoeBurnTick")
    cdo = cdo_of(bp)
    cdo.modify()
    cdo.set_editor_property("duration_policy", unreal.GameplayEffectDurationType.HAS_DURATION)
    mag = unreal.GameplayEffectModifierMagnitude()
    if not mag.import_text("(MagnitudeCalculationType=ScalableFloat,"
                           "ScalableFloatMagnitude=(Value=5.000000))"):
        die("duration magnitude import_text rejected")
    cdo.set_editor_property("duration_magnitude", mag)
    period = cdo.get_editor_property("period")
    period.set_editor_property("value", 1.0)
    cdo.set_editor_property("period", period)
    cdo.set_editor_property("execute_periodic_effect_on_application", True)
    mod = unreal.GameplayModifierInfo()
    t3d = ('(Attribute=(AttributeName="Health",AttributeOwner=Class\'"%s"\'),'
           'ModifierOp=AddBase,'
           'ModifierMagnitude=(MagnitudeCalculationType=ScalableFloat,'
           'ScalableFloatMagnitude=(Value=%f)))' % (ATTRSET, BURN_PER_TICK))
    if not mod.import_text(t3d):
        die("modifier import_text rejected")
    cdo.set_editor_property("modifiers", [mod])
    _bel.compile_blueprint(bp)
    chk = cdo_of(bp)
    say("GE_AoeBurnTick: policy=%s period=%.1f periodic_on_app=%s mods=%d" % (
        chk.get_editor_property("duration_policy"),
        chk.get_editor_property("period").get_editor_property("value"),
        chk.get_editor_property("execute_periodic_effect_on_application"),
        len(chk.get_editor_property("modifiers"))))
    return bp


# --------------------------------------------------------------------------- #
# GA_AoeBurn - CDO restore + the port assert described in the header.
# --------------------------------------------------------------------------- #
def repair_ability():
    bp = load("GA_AoeBurn")
    cdo = cdo_of(bp)
    cdo.set_editor_property(
        "instancing_policy", unreal.GameplayAbilityInstancingPolicy.INSTANCED_PER_ACTOR)
    t = unreal.GameplayTag()
    t.import_text(ABILITY_TAG)
    cdo.set_editor_property("ability_tags", unreal.GameplayTagLibrary.add_gameplay_tag(
        unreal.GameplayTagContainer(), t))
    _bel.compile_blueprint(bp)

    # PORT ASSERT: the spatial filter must name the ThirdPerson class. Node
    # object names come from the MCP authoring pass; EdGraph.Nodes is protected
    # to Python, so resolve by name via find_object (the heal-over-time
    # precedent).
    graph = _bel.find_event_graph(bp)
    if graph is None:
        die("GA_AoeBurn has no event graph - the port lost it")
    node = unreal.find_object(graph, "K2Node_CallFunction_5")
    if node is None:
        die("SphereOverlapActors node not found - MCP node names changed?")
    pin = _bel.find_input_pin(node, "ActorClassFilter")
    if pin is None or not pin.is_valid():
        die("SphereOverlapActors has no ActorClassFilter pin")
    val = str(pin.get_pin_value())
    if "CraftBenchTemplate" in val:
        die("the spatial filter is STILL template-bound (%s). The redirects did "
            "not cover this pin; a reference with this filter burns nothing and "
            "AB-2 would blame the solve." % val)
    if "CraftBenchCharacter" not in val:
        die("the spatial filter does not name CraftBenchCharacter: %s" % val)
    say("GA_AoeBurn: InstancedPerActor, tag=%s, spatial filter=%s (graph preserved)"
        % (ABILITY_TAG, val))
    return bp


# --------------------------------------------------------------------------- #
# BP_AoeBurnPawn - CDO restore. Parent arrives re-pointed by the redirects.
# --------------------------------------------------------------------------- #
def repair_pawn(ga):
    bp = load("BP_AoeBurnPawn")
    parent = _bel.get_blueprint_parent_class(bp)
    if parent is None or "ThirdPerson" not in parent.get_path_name():
        die("pawn parent did not redirect: %r - is the temp [CoreRedirects] "
            "block present in Config/DefaultEngine.ini?"
            % (parent.get_path_name() if parent else None))
    cdo = cdo_of(bp)
    cdo.set_editor_property("granted_abilities", [ga.generated_class()])
    mesh = cdo.get_editor_property("mesh")
    skm = _eal.load_asset(MESH)
    if mesh is None or skm is None:
        die("pawn mesh component or SKM_Manny_Simple missing")
    mesh.set_editor_property("skeletal_mesh_asset", skm)
    mesh.set_editor_property("relative_location", unreal.Vector(0.0, 0.0, -90.0))
    mesh.set_editor_property("relative_rotation", unreal.Rotator(0.0, -90.0, 0.0))
    _bel.compile_blueprint(bp)
    say("BP_AoeBurnPawn: parent=%s, granted=[GA_AoeBurn], mesh=SKM_Manny_Simple"
        % parent.get_name())
    return bp


def main():
    ge = repair_effect()
    ga = repair_ability()
    pawn = repair_pawn(ga)
    for asset in (ge, ga, pawn):
        path = asset.get_path_name().split(".")[0]
        if not _eal.save_asset(path, only_if_is_dirty=False):
            die("save_asset failed for %s" % path)
        say("saved %s" % path)
    say("DONE - 3 assets finalized. NOW REVERT Config/DefaultEngine.ini "
        "(git checkout) before grading.")


main()
