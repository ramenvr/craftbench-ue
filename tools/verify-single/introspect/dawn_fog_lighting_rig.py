"""L2-introspect script for the t1-dawn-fog-lighting-rig task.

Structural, READ-ONLY verification of ONE Blueprint class asset via stock UE
editor-Python. Emits one CRAFTBENCH-INTROSPECT-JSON block the L2-introspect
layer parses (``layers/l2_introspect.py``; contract:
``layers/INTROSPECT_CONTRACT.md``).

What is graded (seed roster R3, re-shaped and re-pathed; see the task spec):
``BP_DawnLighting`` must carry four named lighting subobjects - ``Sky``
(sky/atmosphere), ``Ambient`` (sky light), ``Sun`` (directional light) and
``Fog`` (exponential height fog) - each of the RIGHT TYPE, with the numeric
values that produce a dim, foggy, warm-red early dawn: a low sun angle, a warm
sun colour, a dim sun and ambient, and dense fog with raised volumetric
extinction.

Every numeric band below was DEAD-GATE AUDITED against the UE 5.8 constructor
default for the component that owns it, and every band EXCLUDES that default -
a check that an untouched component satisfies grades nothing. The defaults, all
from ``<UE_ROOT>/Engine/Source/Runtime/Engine/Private/Components/``:

  * ``UDirectionalLightComponent``  Intensity = 10          (DirectionalLightComponent.cpp)
  * ``ULightComponentBase``         LightColor = White      (LightComponent.cpp)
  * ``ULightComponent``             Temperature = 6500, bUseTemperature = false
  * ``USceneComponent``             RelativeRotation = (0,0,0)
  * ``USkyLightComponent``          Intensity = 1, bRealTimeCapture = false
  * ``UExponentialHeightFogComponent``
                                    FogDensity = 0.02, VolumetricFogExtinctionScale = 1.0,
                                    bEnableVolumetricFog = false (never set in the
                                    constructor, so zero-initialised)

Hard rules honoured here:
  * READ-ONLY. Nothing below mutates an asset, a package, or the project.
  * Identity by **pre-declared content path** (``ASSET_RIG``) and pre-declared
    subobject NAME, never by class. Class is consulted only as an ASSERTION
    ("is the thing named Sun really a directional light"), which is the graded
    property, not the lookup key - and it is written as ``isinstance`` so a
    legitimate subclass is not penalized.
  * Stock UE Python only (``EditorAssetLibrary``, the SubobjectData interface,
    reflection). Never Aura's MCP tools - that would grade Aura with Aura.
  * Every check is wrapped in its own try/except, so one wrong API name
    degrades to exactly one FAILED check with the exception in ``detail``
    instead of aborting the verdict.
  * **FAIL CLOSED.** No check passes on the strength of "a probe did not
    raise". A type probe that cannot be evaluated returns ``None`` and the
    check FAILS; ``_gather_handles`` / ``_components`` RAISE on an empty walk
    instead of returning ``[]``; an unreadable numeric is a ``*_READ_ERROR``
    failure, never a pass.
  * The check list has a **constant length (14)** on every leg, including a
    missing asset. ``registry.py`` reports ``tests_passed/tests_run`` from
    these counts, so a constant denominator keeps the ratio comparable and
    stops a submission from improving its score by making checks unreachable.

Detail strings are stable, ASCII, greppable tokens. The discrimination MATRIX
joins on the raw ``detail`` string **as printed inside the JSON block**, not on
the layer's ``<script>:<check>: FAIL - ...`` note rendering, so each failing
check owns a unique ``*_MISSING`` / ``*_WRONG_TYPE`` / ``*_NOT_*`` / ``*_TOO_*``
token that never appears on the passing branch. No detail contains either of
the two automation result markers ("TestResult" + "=Passed", and "Automation
Test" + " Succeeded") that ``parse_automation_log``'s whole-file ``finditer``
counts as a TEST - a detail carrying one would inflate the test tally and can
flip a PASS to a FAIL through the ``expected_test_count`` guard. Neither
substring appears anywhere in this file, including this docstring.

UE 5.8 API notes (reflection visibility established from engine source per
``PropertyAccessUtil.cpp:425-433`` - Python readability needs
CPF_Edit | CPF_BlueprintVisible | CPF_BlueprintAssignable):
  * ``SubobjectDataSubsystem`` is an **ENGINE** subsystem -
    ``unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)``.
    ``get_editor_subsystem`` on it raises ``TypeError: Cannot nativize``.
  * ``USceneComponent::RelativeRotation`` is EditAnywhere|BlueprintReadOnly
    (``SceneComponent.h:142``), so it is readable. **The sun's angle is NOT
    graded off it directly.** A rig whose ROOT is rotated and whose light sits
    at identity produces exactly the same sun as the reverse, and grading the
    light component's own rotation failed that correct answer outright
    (`SUN_PITCH_NOT_LOW world_pitch=0.0`, found 2026-07-27). The relative
    rotations are therefore composed up the SCS attach chain and the WORLD-space
    forward vector is what the band is applied to (``_world_elevation_of``).
  * The chain itself is read with
    ``SubobjectDataBlueprintFunctionLibrary::GetParentHandle``, a
    ``UFUNCTION(BlueprintCallable, BlueprintPure)``
    (``SubobjectDataBlueprintFunctionLibrary.h:49-50``). It has to be a
    UFUNCTION: ``USceneComponent::AttachParent`` is a bare
    ``UPROPERTY(ReplicatedUsing=..., meta=(...))`` with NONE of
    ``CPF_Edit | CPF_BlueprintVisible | CPF_BlueprintAssignable``
    (``SceneComponent.h:108-109``), so ``CanGetPropertyValue`` returns
    ``PermissionDenied`` for it (``PropertyAccessUtil.cpp:425-433``) - and on an
    SCS component TEMPLATE it is null at rest anyway, so even a readable
    ``AttachParent`` would not give the hierarchy.
  * The rotator-to-matrix transcription is UE's own
    (``RotationTranslationMatrix.h:72-84``, row-vector convention, row 0 is
    forward). Doing it in Python rather than through ``unreal.MathLibrary``
    keeps the graded quantity independent of which math helpers a build
    pythonizes, and lets the composition be tested with no editor.
  * ``Intensity`` / ``LightColor`` are BlueprintReadOnly
    (``LightComponentBase.h:36,44``); ``Temperature`` / ``bUseTemperature``
    are EditAnywhere|BlueprintReadOnly (``LightComponent.h:57,69``).
  * ``FogDensity`` is BlueprintReadOnly
    (``ExponentialHeightFogComponent.h:22``); ``bEnableVolumetricFog`` and
    ``VolumetricFogExtinctionScale`` are EditAnywhere|BlueprintReadOnly
    (``:136,163``).
  * ``bRealTimeCapture`` is EditAnywhere|BlueprintReadOnly
    (``SkyLightComponent.h:108``).
  * All four component types carry ``meta=(BlueprintSpawnableComponent)``, so
    all four are addable to a Blueprint's component list - the deliverable
    shape this task grades is legal by construction.
  * ``UBlueprint::Status`` is ``UPROPERTY(transient, BlueprintReadOnly)`` - it
    is NOT serialized, so what this reads is the compile state produced by
    loading the submitted asset, which is the property worth gating.
  * UE pythonizes a bool UPROPERTY by dropping the leading ``b``
    (``bRealTimeCapture`` -> ``real_time_capture``). Every read below tries
    several spellings rather than betting on one.
"""
import json
import math

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax / format checks
    unreal = None

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

# --- Pre-declared identity (content PATH and subobject NAMES, never class) ---
TASK_ID = "t1-dawn-fog-lighting-rig"
ASSET_RIG = "/Game/Tasks/%s/BP_DawnLighting" % TASK_ID

SKY_NAME = "Sky"
AMBIENT_NAME = "Ambient"
SUN_NAME = "Sun"
FOG_NAME = "Fog"

# --- Graded numeric bands (every one EXCLUDES the engine default) ------------
# NONE of these numbers is visible to the agent: the prompt describes the LOOK
# and the direction of travel away from the untouched part, and never a
# threshold (task.md divergences 5 and 6, 2026-07-27). Every band below was
# therefore re-cut on the question "is this reachable by anyone who actually
# produced the described look, without having been told the number?", and the
# dead-gate column was re-run afterwards - every band still excludes the
# engine default it must exclude.

# Sun elevation. A directional light points along its forward vector, so a sun
# ABOVE the horizon has a NEGATIVE pitch. Engine default relative rotation is
# (0,0,0) => pitch 0.0, which this band excludes.
# Widened from [-20, -2]: "low" has no canonical degree count, and 20 vs 25
# degrees of elevation is not a distinction the prose can carry. The MAX end is
# only a dead-gate guard against the 0.0 default, so it needs to be non-zero,
# not large - it is relaxed to -1.0 so "sitting ON the horizon" is not punished.
SUN_PITCH_MIN = -25.0
SUN_PITCH_MAX = -1.0

# The band is applied to the WORLD-space elevation of the sun's forward vector,
# NOT to the light component's own RelativeRotation - see `_world_elevation_of`.
# Depth guard for the attach-chain walk that composition needs: an SCS
# hierarchy this deep is a cycle or a broken read, never a lighting rig.
_MAX_ATTACH_DEPTH = 32

# Sun brightness in lux. Engine default is 10 (DirectionalLightComponent.cpp).
# The CEILING carries the discrimination (half the engine default = "dim") and
# is unchanged. The FLOOR's only job is to reject a light that is effectively
# switched off; a very dim dawn sun is a legitimate reading of the prompt, so
# it is relaxed from 0.5 to 0.05 (still 200x below the default).
SUN_INTENSITY_MIN = 0.05
SUN_INTENSITY_MAX = 5.0

# Warmth, route A: colour temperature. Engine default is 6500 K with
# bUseTemperature FALSE, so BOTH conditions must be met for this route.
# NOT widened: "warm and red" / "firelight-warm" pins this unambiguously, and
# 1000-4000 K already spans candle through tungsten.
SUN_TEMPERATURE_MAX = 4000.0
SUN_TEMPERATURE_MIN = 1000.0

# Warmth, route B: an explicitly warm-red filter colour. Engine default is
# pure white (R == G == B), which fails the strict ordering below.
# NOT widened, for the same reason as route A.
SUN_COLOR_MIN_RED = 150
SUN_COLOR_MIN_RED_BLUE_GAP = 60

# Ambient sky-light brightness. Engine default is 1.0 (SkyLightComponent.cpp).
# Ceiling unchanged (60% of the default is the "clearly weaker" boundary);
# floor relaxed from 0.05 to 0.01 on the same argument as the sun floor - it
# rejects "off", nothing more.
SKYLIGHT_INTENSITY_MIN = 0.01
SKYLIGHT_INTENSITY_MAX = 0.6

# Fog. Engine defaults: FogDensity 0.02, VolumetricFogExtinctionScale 1.0.
# Density floor relaxed from 0.2 to 0.1: 0.1 is already 5x the default and is
# visibly thick fog, and it is a value an agent aiming at "swallow the
# distance" plausibly picks. Ceiling raised 5.0 -> 10.0 so an agent that goes
# extreme is not failed for over-delivering the described look.
# Extinction floor relaxed from 2.0 to 1.5: 2.0 was an author's round number,
# not a look boundary. The graded property is "turned up well above where it
# starts", and 1.5 is half again the 1.0 default - a real raise, still a live
# gate against the untouched value.
FOG_DENSITY_MIN = 0.1
FOG_DENSITY_MAX = 10.0
FOG_EXTINCTION_MIN = 1.5

# --- The check ids, in emission order. Length is the score denominator. ------
CHECK_IDS = (
    "rig_asset_exists",
    "rig_sky_atmosphere_present",
    "rig_sky_light_present",
    "rig_sun_light_present",
    "rig_height_fog_present",
    "sun_angle_is_low_dawn",
    "sun_color_is_warm",
    "sun_intensity_is_dim",
    "skylight_intensity_is_dim",
    "skylight_recaptures_live_sky",
    "fog_density_is_dense",
    "fog_volumetric_enabled",
    "fog_extinction_raised",
    "rig_is_placeable_actor",
    "rig_carries_only_the_four_parts",
    "sun_casts_shadows",
    "rig_compiles_up_to_date",
)

# Emitted for every check that cannot run because the asset is absent.
RIG_MISSING_TOKEN = "RIG_ASSET_MISSING"


# --------------------------------------------------------------------------- #
# verdict plumbing                                                             #
# --------------------------------------------------------------------------- #

def check(check_id, passed, detail=""):
    return {"id": str(check_id), "passed": bool(passed), "detail": str(detail)}


def emit_verdict(checks):
    """Print the one verdict block the L2-introspect layer parses."""
    payload = json.dumps({"checks": checks})
    print(INTROSPECT_JSON_START)
    print(payload)
    print(INTROSPECT_JSON_END)
    if unreal is not None:
        try:
            unreal.log(INTROSPECT_JSON_START)
            unreal.log(payload)
            unreal.log(INTROSPECT_JSON_END)
        except Exception:  # noqa: BLE001 - stdout copy is authoritative
            pass


# --------------------------------------------------------------------------- #
# small reflection helpers (each defensive; callers wrap in try/except)         #
# --------------------------------------------------------------------------- #

def _asset_exists(path):
    return bool(unreal.EditorAssetLibrary.does_asset_exist(path))


def _read_property(obj, *names):
    """First readable spelling of a reflected property; re-raises if none is.

    UE pythonizes UPROPERTY names (``FogDensity`` -> ``fog_density``, and a
    bool loses its leading ``b``: ``bRealTimeCapture`` -> ``real_time_capture``)
    while an authored Blueprint variable keeps its own spelling. Trying every
    plausible spelling is cheaper than being wrong, and it never invents a
    value - if every spelling fails the last exception propagates and the
    caller records a ``*_READ_ERROR``.
    """
    last = None
    for name in names:
        try:
            return obj.get_editor_property(name)
        except Exception as e:  # noqa: BLE001
            last = e
    raise last if last is not None else AttributeError("no property name given")


def _class_name(obj):
    if obj is None:
        return "None"
    try:
        return str(obj.get_class().get_name())
    except Exception:  # noqa: BLE001
        return "<unreadable>"


def _isinstance_tristate(obj, type_name):
    """``isinstance(obj, unreal.<type_name>)`` as True / False / None.

    ``None`` means "the type is not exposed / the probe could not be
    evaluated", and every caller treats that as NOT satisfied. This never
    returns True because an exception did not happen.
    """
    if obj is None:
        return False
    cls = getattr(unreal, type_name, None)
    if cls is None:
        return None
    try:
        return bool(isinstance(obj, cls))
    except Exception:  # noqa: BLE001
        return None


def _subobject_subsystem():
    """The SubobjectData subsystem. ENGINE subsystem, not editor."""
    return unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)


def _is_handle(obj):
    try:
        return isinstance(obj, unreal.SubobjectDataHandle)
    except Exception:  # noqa: BLE001
        return False


def _gather_handles(subsystem, blueprint):
    """Every subobject handle on a Blueprint (root actor + all components).

    UE's Python codegen strips the ``K2_`` prefix off
    ``K2_GatherSubobjectDataForBlueprint``; the prefixed spelling is tried as a
    fallback in case a future build keeps it.

    FAIL-CLOSED: an unavailable accessor or an EMPTY gather RAISES. A Blueprint
    always has at least its root actor subobject
    (``SubobjectDataSubsystem.cpp:147-154`` gathers off
    ``GeneratedClass->GetDefaultObject()``), so an empty result is a broken
    walk, never a legitimate "this asset has no components".
    """
    for name in ("gather_subobject_data_for_blueprint",
                 "k2_gather_subobject_data_for_blueprint"):
        fn = getattr(subsystem, name, None)
        if fn is None:
            continue
        out = fn(blueprint)
        if (isinstance(out, (tuple, list)) and len(out) == 2
                and isinstance(out[-1], (tuple, list)) and not _is_handle(out[0])):
            # (return_value, out_array) shape
            out = out[-1]
        handles = list(out or [])
        if not handles:
            raise RuntimeError("SUBOBJECT_GATHER_EMPTY via %s" % name)
        return handles
    raise AttributeError("SUBOBJECT_GATHER_UNAVAILABLE on %r" % (subsystem,))


def _data_for(handle):
    """FSubobjectData for a handle, or None."""
    try:
        res = unreal.SubobjectDataBlueprintFunctionLibrary.get_data(handle)
    except Exception:  # noqa: BLE001
        return None
    if isinstance(res, (tuple, list)):
        res = res[-1] if res else None
    return res


def _var_name(data):
    try:
        return str(unreal.SubobjectDataBlueprintFunctionLibrary.get_variable_name(data))
    except Exception:  # noqa: BLE001
        return ""


def _sub_object(data):
    """The component template behind a subobject, or None.

    ``get_object`` is the route proven live; ``get_associated_object`` is its
    5.8 non-deprecated replacement and is tried second.
    """
    lib = unreal.SubobjectDataBlueprintFunctionLibrary
    for name in ("get_object", "get_associated_object"):
        fn = getattr(lib, name, None)
        if fn is None:
            continue
        try:
            obj = fn(data)
        except Exception:  # noqa: BLE001
            continue
        if obj is not None:
            return obj
    return None


def _sub_display_name(data):
    """A name for a subobject: its variable name, else its object name."""
    name = _var_name(data)
    if name and name != "None":
        return name
    obj = _sub_object(data)
    if obj is not None:
        try:
            return str(obj.get_name())
        except Exception:  # noqa: BLE001
            return ""
    return ""


def _components(blueprint):
    """[(display_name, data)] for every subobject on the Blueprint.

    The actor root subobject is included; callers match by pre-declared name,
    so it is harmless and it keeps the ``names=`` detail honest.

    FAIL-CLOSED: raises rather than returning an empty walk (see
    ``_gather_handles``).
    """
    subsystem = _subobject_subsystem()
    if subsystem is None:
        raise RuntimeError("SUBOBJECT_SUBSYSTEM_UNAVAILABLE")
    out = []
    for handle in _gather_handles(subsystem, blueprint):
        data = _data_for(handle)
        if data is None:
            continue
        out.append((_sub_display_name(data), data))
    if not out:
        raise RuntimeError("SUBOBJECT_WALK_EMPTY")
    return out



def _is_component(data):
    """True when this subobject row is an ActorComponent (not the actor root).

    The walk deliberately includes the actor root subobject so ``names=`` stays
    honest, but a census of PARTS must not count it. Identifying it by name would
    be fragile (it carries the Blueprint/class name), so it is identified by type
    instead: the root row's object is the actor CDO, not a component.
    """
    return _isinstance_tristate(_sub_object(data), "ActorComponent") is True


def _placeable_checks(results, blueprint):
    """Row 2 -- the prompt says "Produce one PLACEABLE game-object asset".

    Generate-Abstract-Class or NotPlaceable both make the asset undroppable while
    every value gate still passes, so a 14/14 rig that can never be put in a level
    was possible. Read the Blueprint's own flag, then the class flag as a
    fallback, and FAIL CLOSED if neither can be read -- an unreadable placeability
    is not evidence of placeability.
    """
    cid = "rig_is_placeable_actor"
    try:
        abstract = _read_property(blueprint, "generate_abstract_class")
    except Exception as e:  # noqa: BLE001
        results[cid] = check(cid, False, "RIG_PLACEABLE_READ_ERROR raised %r" % (e,))
        return
    if abstract is None:
        results[cid] = check(
            cid, False,
            "RIG_PLACEABLE_UNREADABLE generate_abstract_class is not exposed")
        return
    if bool(abstract):
        results[cid] = check(
            cid, False,
            "RIG_NOT_PLACEABLE generate_abstract_class=True the asset cannot be "
            "dropped into a level")
        return
    results[cid] = check(cid, True, "RIG_PLACEABLE_OK generate_abstract_class=False")


def _census_check(results, components, names):
    """Row 8 -- the prompt says "It must carry EXACTLY FOUR working parts".

    The four presence checks are floors, not a census: a fifth bright point light
    re-lighting the "dim" scene, or a post-process component re-exposing it, passed
    every gate. This counts the parts and rejects any beyond the four named ones.

    TWO THINGS ARE DELIBERATELY EXCLUDED FROM THE COUNT, and both were measured
    rather than guessed:

      * the actor ROOT subobject -- the walk includes it so ``names=`` stays honest,
        but it is not a component. Excluded by type (its object is the actor CDO).
      * UE's structural attach root, e.g. ``DefaultSceneRoot`` -- this IS a real
        SceneComponent, so the type filter does not catch it, and the reference
        legitimately carries one (measured: RIG_EXTRA_PARTS extras=
        ['DefaultSceneRoot'] failed the reference on the first attempt). It is
        scaffolding UE creates automatically, not a "working part".

    The structural root is identified by TOPOLOGY -- the component with no
    scene-component ancestor -- not by name, which would break on a rename. Exactly
    ONE is tolerated: a second rootless component is still an extra, so this cannot
    become a loophole for "attach nothing and pass".
    """
    cid = "rig_carries_only_the_four_parts"
    expected = {SKY_NAME, AMBIENT_NAME, SUN_NAME, FOG_NAME}
    try:
        parts = [(n, data) for n, data in components if _is_component(data)]
        rootless = []
        for n, data in parts:
            if _scene_ancestors(data):
                continue
            rootless.append(n)
    except Exception as e:  # noqa: BLE001 - fail closed; an unreadable hierarchy is
        # not evidence that the part count is right.
        results[cid] = check(cid, False, "RIG_CENSUS_READ_ERROR raised %r" % (e,))
        return

    # Tolerate a single structural root that is not itself one of the four.
    structural = [n for n in rootless if n not in expected]
    tolerated = set(structural[:1]) if len(structural) == 1 else set()

    extras = sorted(n for n, _ in parts if n not in expected and n not in tolerated)
    if extras:
        results[cid] = check(
            cid, False,
            "RIG_EXTRA_PARTS extras=%s only %s are permitted (a single structural "
            "attach root is not counted)" % (extras, sorted(expected)))
        return
    counted = sorted(n for n, _ in parts if n not in tolerated)
    results[cid] = check(
        cid, True,
        "RIG_PARTS_OK count=%d names=%s root_excluded=%s"
        % (len(counted), counted, sorted(tolerated)))


def _sun_shadow_check(results, sun, sun_detail):
    """Row 14 -- the prompt says "Sun -- the ONE distant light that CASTS THE
    SCENE'S SHADOWS".

    No check read CastShadows, so a sun with shadows switched off scored full
    marks; the engine default merely happens to be on, which is exactly the
    default-coincidence the calibration law says to exclude by conjoining it with
    a non-default fact -- here, the sun's own presence and dimming.
    """
    cid = "sun_casts_shadows"
    if sun is None:
        results[cid] = check(cid, False, sun_detail)
        return
    try:
        casts = _read_property(sun, "cast_shadows")
    except Exception as e:  # noqa: BLE001
        results[cid] = check(cid, False, "SUN_SHADOW_READ_ERROR raised %r" % (e,))
        return
    if casts is None:
        results[cid] = check(
            cid, False, "SUN_SHADOW_UNREADABLE cast_shadows is not exposed")
        return
    if not bool(casts):
        results[cid] = check(
            cid, False,
            "SUN_CASTS_NO_SHADOWS cast_shadows=False the one light that casts the "
            "scene's shadows casts none")
        return
    results[cid] = check(cid, True, "SUN_SHADOWS_OK cast_shadows=True")

def _names_of(components):
    return sorted(n for n, _ in components if n)


def _find_component(components, name):
    for got, data in components:
        if got == name:
            return data
    return None


def _relative_rotation(component):
    """The component template's own ``(pitch, yaw, roll)`` in degrees.

    ``RelativeRotation`` is EditAnywhere|BlueprintReadOnly
    (``SceneComponent.h:142``), so it IS reflection-readable per
    ``PropertyAccessUtil.cpp:425-433``. The UFUNCTION getter
    ``GetRelativeRotation`` is tried first where codegen exposes it; either
    route yields an ``unreal.Rotator``.
    """
    getter = getattr(component, "get_relative_rotation", None)
    rot = None
    if getter is not None:
        try:
            rot = getter()
        except Exception:  # noqa: BLE001 - fall through to the property read
            rot = None
    if rot is None:
        rot = _read_property(component, "relative_rotation", "RelativeRotation")
    if rot is None:
        raise RuntimeError("ROTATION_UNREADABLE")
    return (float(_read_rotator_axis(rot, "pitch", "Pitch")),
            float(_read_rotator_axis(rot, "yaw", "Yaw")),
            float(_read_rotator_axis(rot, "roll", "Roll")))


def _read_rotator_axis(rot, *names):
    for attr in names:
        val = getattr(rot, attr, None)
        if val is not None:
            return val
    return _read_property(rot, *names)


def _rotator_matrix(pitch, yaw, roll):
    """UE's ``FRotationMatrix`` rows for one rotator, in degrees.

    Transcribed from ``RotationTranslationMatrix.h:72-84`` (UE 5.8). UE is
    ROW-VECTOR: ``v_world = v_local * M``, and row 0 is the forward (X) axis.
    Composing a child onto its parent is therefore ``M_child * M_parent``.
    Doing the trigonometry here rather than through ``unreal.MathLibrary``
    keeps the graded quantity independent of which math helpers a given build
    pythonizes - and testable with no editor at all.
    """
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cr, sr = math.cos(math.radians(roll)), math.sin(math.radians(roll))
    return (
        (cp * cy, cp * sy, sp),
        (sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp),
        (-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp),
    )


def _vec_times_matrix(v, m):
    """Row-vector times 3x3 matrix, UE's multiplication order."""
    return tuple(sum(v[k] * m[k][i] for k in range(3)) for i in range(3))


def _scene_ancestors(data):
    """Every SCENE-COMPONENT ancestor of a subobject, nearest parent first.

    ``FSubobjectData::GetParentHandle`` is exposed as
    ``UFUNCTION(BlueprintCallable, BlueprintPure)``
    (``SubobjectDataBlueprintFunctionLibrary.h:49-50``), so the SCS attach
    hierarchy is readable even though ``USceneComponent::AttachParent`` itself
    is a bare ``UPROPERTY()`` with none of ``CPF_Edit |
    CPF_BlueprintVisible | CPF_BlueprintAssignable`` and is therefore
    reflection-DENIED (``SceneComponent.h:108-109``,
    ``PropertyAccessUtil.cpp:425-433``).

    The walk STOPS at the first ancestor that is not a scene component - that
    is the Blueprint's root ACTOR subobject, which carries no relative
    rotation. FAIL-CLOSED throughout: an unresolvable template, an unevaluable
    ``SceneComponent`` probe, or a chain longer than ``_MAX_ATTACH_DEPTH``
    RAISES rather than silently truncating the composition (a truncated chain
    would drop exactly the rotation this function exists to find).
    """
    lib = getattr(unreal, "SubobjectDataBlueprintFunctionLibrary", None)
    if lib is None or getattr(lib, "get_parent_handle", None) is None:
        raise RuntimeError("SUBOBJECT_PARENT_HANDLE_UNAVAILABLE")
    out = []
    seen = 0
    current = data
    while True:
        seen += 1
        if seen > _MAX_ATTACH_DEPTH:
            raise RuntimeError("SUBOBJECT_ATTACH_CHAIN_TOO_DEEP depth=%d" % seen)
        handle = lib.get_parent_handle(current)
        if isinstance(handle, (tuple, list)):
            handle = handle[-1] if handle else None
        if handle is None:
            return out
        validator = getattr(lib, "is_handle_valid", None)
        if validator is not None:
            try:
                valid = bool(validator(handle))
            except Exception as e:  # noqa: BLE001 - unreadable => fail closed
                raise RuntimeError("SUBOBJECT_PARENT_HANDLE_UNREADABLE %r" % (e,))
            if not valid:
                return out
        parent = _data_for(handle)
        if parent is None:
            return out
        obj = _sub_object(parent)
        if obj is None:
            raise RuntimeError("SUBOBJECT_PARENT_TEMPLATE_UNAVAILABLE")
        is_scene = _isinstance_tristate(obj, "SceneComponent")
        if is_scene is None:
            raise RuntimeError("SUBOBJECT_PARENT_TYPE_PROBE_ERROR class=%s"
                               % _class_name(obj))
        if not is_scene:
            return out          # the actor root subobject: end of the chain
        out.append((_sub_display_name(parent) or "<unnamed>", obj))
        current = parent


def _world_elevation_of(data, component):
    """``(elevation_deg, chain_text)`` for a light's WORLD-space direction.

    A directional light shines along its forward (+X) vector, so what "a sun
    just above the horizon" means is a property of the WORLD-space direction,
    not of any one component's local rotation. Reading only the light
    component's own ``RelativeRotation`` FAILS A CORRECT ANSWER: an author who
    rotates the rig's root and leaves the light at identity produces exactly
    the same sun, and scored ``SUN_PITCH_NOT_LOW pitch=0.0`` until 2026-07-27.

    So the light's relative rotation is composed with every scene-component
    ancestor's, up to (and excluding) the actor root, and the elevation is
    taken off the resulting forward vector as
    ``degrees(asin(forward.z))``. That is identically the rotator pitch in the
    unrotated case (``FRotator::Vector`` is ``(cp*cy, cp*sy, sp)``), so the
    graded band is unchanged and the reference still reads -8.0.
    """
    forward = _rotator_matrix(*_relative_rotation(component))[0]
    parts = ["%s:%.4f" % ("self", math.degrees(math.asin(
        max(-1.0, min(1.0, forward[2])))))]
    for name, ancestor in _scene_ancestors(data):
        forward = _vec_times_matrix(
            forward, _rotator_matrix(*_relative_rotation(ancestor)))
        parts.append("%s:%.4f,%.4f,%.4f"
                     % ((name,) + _relative_rotation(ancestor)))
    elevation = math.degrees(math.asin(max(-1.0, min(1.0, forward[2]))))
    return elevation, "[" + " ".join(parts) + "]"


def _color_rgb(component):
    """``(r, g, b)`` ints of the light's filter colour.

    ``LightColor`` is an ``FColor`` (sRGB bytes), BlueprintReadOnly at
    ``LightComponentBase.h:44``.
    """
    col = _read_property(component, "light_color", "LightColor")
    if col is None:
        raise RuntimeError("LIGHT_COLOR_UNREADABLE")
    out = []
    for lower, upper in (("r", "R"), ("g", "G"), ("b", "B")):
        val = getattr(col, lower, None)
        if val is None:
            val = getattr(col, upper, None)
        if val is None:
            val = _read_property(col, lower, upper)
        out.append(int(round(float(val))))
    return tuple(out)


def _bool_property(component, *names):
    """A reflected bool as a real bool; raises if no spelling reads."""
    return bool(_read_property(component, *names))


def _compile_status(blueprint):
    """A string for the Blueprint's compile status, e.g. 'BlueprintStatus.BS_UP_TO_DATE'."""
    return str(_read_property(blueprint, "status", "Status"))


# --------------------------------------------------------------------------- #
# component resolution (name AND type, both required)                          #
# --------------------------------------------------------------------------- #

def _resolve(components, names, wanted_name, type_name, token_stem):
    """``(component_or_None, detail)`` for one pre-declared lighting part.

    A NAME MATCH IS NOT ENOUGH - a submission that merely *calls* something
    ``Sun`` must not satisfy the sun checks. Three positive facts are required
    and any unreadable one FAILS:

      1. a subobject with the pre-declared variable name exists;
      2. its component template resolves to a real object;
      3. ``isinstance`` against the required component type returns True
         (subclass-tolerant). A probe that cannot be evaluated returns ``None``
         and is treated as NOT satisfied.

    The three outcomes carry three DIFFERENT tokens, so the matrix can tell
    "absent" from "impostor" from "the type is not exposed to Python".
    """
    data = _find_component(components, wanted_name)
    if data is None:
        return None, "%s_MISSING names=%s wanted=%s" % (token_stem, names, wanted_name)
    obj = _sub_object(data)
    if obj is None:
        return None, "%s_TEMPLATE_UNAVAILABLE name=%s" % (token_stem, wanted_name)
    verdict = _isinstance_tristate(obj, type_name)
    if verdict is None:
        return None, ("%s_TYPE_PROBE_ERROR class=%s expected=%s"
                      % (token_stem, _class_name(obj), type_name))
    if not verdict:
        return None, ("%s_WRONG_TYPE class=%s name=%s expected=%s"
                      % (token_stem, _class_name(obj), wanted_name, type_name))
    return obj, "%s_OK class=%s name=%s" % (token_stem, _class_name(obj), wanted_name)


# --------------------------------------------------------------------------- #
# the checks                                                                   #
# --------------------------------------------------------------------------- #

def _fanout(results, cids, detail):
    for cid in cids:
        if cid not in results:
            results[cid] = check(cid, False, detail)


def _rig_checks(results):
    """Fill ``results`` (a dict keyed by check id) for every check."""
    # A raised probe is NOT the same event as a genuinely absent asset, and the
    # two must not share a token: an API break that fanned out
    # RIG_ASSET_MISSING would be credited as the empty leg's named failure.
    root_cause = None
    try:
        rig_exists = _asset_exists(ASSET_RIG)
    except Exception as e:  # noqa: BLE001
        root_cause = "RIG_ASSET_PROBE_ERROR %s raised %r" % (ASSET_RIG, e)
        results["rig_asset_exists"] = check("rig_asset_exists", False, root_cause)
        rig_exists = False
    else:
        if rig_exists:
            results["rig_asset_exists"] = check(
                "rig_asset_exists", True, "RIG_ASSET_OK %s" % ASSET_RIG)
        else:
            root_cause = "%s %s" % (RIG_MISSING_TOKEN, ASSET_RIG)
            results["rig_asset_exists"] = check("rig_asset_exists", False, root_cause)

    if not rig_exists:
        # Constant denominator: every remaining check still reports, as a
        # failure whose detail names the single root cause.
        _fanout(results, CHECK_IDS, root_cause)
        return

    # --- subobject walk (shared by the four presence checks) -----------------
    components = []
    walk_error = None
    try:
        rig_bp = unreal.EditorAssetLibrary.load_asset(ASSET_RIG)
        components = _components(rig_bp)
    except Exception as e:  # noqa: BLE001
        walk_error = repr(e)
    names = _names_of(components)

    if walk_error is not None:
        # A broken walk is an ERROR event, not any variant's graded failure -
        # distinct token, so it can never be credited as a named assertion.
        _fanout(results, [c for c in CHECK_IDS if c != "rig_compiles_up_to_date"],
                "RIG_SUBOBJECT_WALK_ERROR raised %s" % walk_error)
        _compile_check(results)
        return

    sky, sky_detail = _resolve(components, names, SKY_NAME,
                               "SkyAtmosphereComponent", "RIG_SKY_ATMOSPHERE")
    ambient, ambient_detail = _resolve(components, names, AMBIENT_NAME,
                                       "SkyLightComponent", "RIG_SKY_LIGHT")
    sun, sun_detail = _resolve(components, names, SUN_NAME,
                               "DirectionalLightComponent", "RIG_SUN_LIGHT")
    fog, fog_detail = _resolve(components, names, FOG_NAME,
                               "ExponentialHeightFogComponent", "RIG_HEIGHT_FOG")

    results["rig_sky_atmosphere_present"] = check(
        "rig_sky_atmosphere_present", sky is not None, sky_detail)
    results["rig_sky_light_present"] = check(
        "rig_sky_light_present", ambient is not None, ambient_detail)
    results["rig_sun_light_present"] = check(
        "rig_sun_light_present", sun is not None, sun_detail)
    results["rig_height_fog_present"] = check(
        "rig_height_fog_present", fog is not None, fog_detail)

    # Three gates for prompt clauses that had none (2026-08-19): the asset must be
    # PLACEABLE, it must carry EXACTLY four parts, and the Sun must be the light
    # that casts shadows. All three are verbatim prompt requirements; the four
    # presence checks above are floors and never counted or read shadowing.
    _placeable_checks(results, rig_bp)
    _census_check(results, components, names)
    _sun_shadow_check(results, sun, sun_detail)

    # The sun's ELEVATION is a world-space quantity, so the checks need the
    # subobject DATA (for the attach chain) as well as the component template.
    _sun_checks(results, sun, sun_detail, _find_component(components, SUN_NAME))
    _skylight_checks(results, ambient, ambient_detail)
    _fog_checks(results, fog, fog_detail)
    _compile_check(results)


def _sun_checks(results, sun, sun_detail, sun_data=None):
    """The three graded numbers on the directional light.

    When the sun part did not resolve (absent, impostor, or an unreadable type
    probe) these fan out carrying the SAME resolution detail, so the failure is
    attributed once and to the right cause instead of inventing three
    unrelated numeric failures against whatever object happens to be named
    ``Sun``.
    """
    if sun is None:
        _fanout(results, ("sun_angle_is_low_dawn", "sun_color_is_warm",
                          "sun_intensity_is_dim"), sun_detail)
        return

    # Elevation: a sun just above the horizon. WORLD-space, composed up the
    # attach chain - rotating the rig's root is as valid an answer as rotating
    # the light, and grading the component's own rotation failed the former.
    try:
        if sun_data is None:
            raise RuntimeError("SUN_SUBOBJECT_DATA_UNAVAILABLE")
        elevation, chain = _world_elevation_of(sun_data, sun)
        ok = SUN_PITCH_MIN <= elevation <= SUN_PITCH_MAX
        results["sun_angle_is_low_dawn"] = check(
            "sun_angle_is_low_dawn", ok,
            ("SUN_PITCH_OK world_pitch=%.4f band=[%s, %s] chain=%s"
             % (elevation, SUN_PITCH_MIN, SUN_PITCH_MAX, chain))
            if ok else
            ("SUN_PITCH_NOT_LOW world_pitch=%.4f band=[%s, %s] "
             "engine_default=0.0 chain=%s"
             % (elevation, SUN_PITCH_MIN, SUN_PITCH_MAX, chain)))
    except Exception as e:  # noqa: BLE001
        results["sun_angle_is_low_dawn"] = check(
            "sun_angle_is_low_dawn", False, "SUN_PITCH_READ_ERROR raised %r" % (e,))

    # Warmth: EITHER a low colour temperature that is actually switched on, OR
    # an explicitly red-dominant filter colour. Both branches exclude the
    # engine default (white / 6500 K / temperature off).
    try:
        r, g, b = _color_rgb(sun)
        try:
            use_temp = _bool_property(sun, "use_temperature", "bUseTemperature",
                                      "b_use_temperature")
        except Exception:  # noqa: BLE001 - unreadable => that route is not taken
            use_temp = False
        try:
            temperature = float(_read_property(sun, "temperature", "Temperature"))
        except Exception:  # noqa: BLE001
            temperature = float("nan")
        temp_ok = bool(use_temp) and (
            SUN_TEMPERATURE_MIN <= temperature <= SUN_TEMPERATURE_MAX)
        color_ok = (r > g > b and r >= SUN_COLOR_MIN_RED
                    and (r - b) >= SUN_COLOR_MIN_RED_BLUE_GAP)
        ok = bool(temp_ok or color_ok)
        summary = ("color=(R=%d,G=%d,B=%d) use_temperature=%s temperature=%s"
                   % (r, g, b, bool(use_temp), temperature))
        results["sun_color_is_warm"] = check(
            "sun_color_is_warm", ok,
            ("SUN_COLOR_OK %s" % summary) if ok
            else ("SUN_COLOR_NOT_WARM %s max_kelvin=%s min_red=%s min_red_blue_gap=%s"
                  % (summary, SUN_TEMPERATURE_MAX, SUN_COLOR_MIN_RED,
                     SUN_COLOR_MIN_RED_BLUE_GAP)))
    except Exception as e:  # noqa: BLE001
        results["sun_color_is_warm"] = check(
            "sun_color_is_warm", False, "SUN_COLOR_READ_ERROR raised %r" % (e,))

    # Brightness: dimmer than an untouched sun.
    try:
        value = float(_read_property(sun, "intensity", "Intensity"))
        ok = SUN_INTENSITY_MIN <= value <= SUN_INTENSITY_MAX
        results["sun_intensity_is_dim"] = check(
            "sun_intensity_is_dim", ok,
            ("SUN_INTENSITY_OK value=%s band=[%s, %s]"
             % (value, SUN_INTENSITY_MIN, SUN_INTENSITY_MAX)) if ok
            else ("SUN_INTENSITY_NOT_DIM value=%s band=[%s, %s] engine_default=10.0"
                  % (value, SUN_INTENSITY_MIN, SUN_INTENSITY_MAX)))
    except Exception as e:  # noqa: BLE001
        results["sun_intensity_is_dim"] = check(
            "sun_intensity_is_dim", False, "SUN_INTENSITY_READ_ERROR raised %r" % (e,))


def _skylight_checks(results, ambient, ambient_detail):
    if ambient is None:
        _fanout(results, ("skylight_intensity_is_dim",
                          "skylight_recaptures_live_sky"), ambient_detail)
        return

    try:
        value = float(_read_property(ambient, "intensity", "Intensity"))
        ok = SKYLIGHT_INTENSITY_MIN <= value <= SKYLIGHT_INTENSITY_MAX
        results["skylight_intensity_is_dim"] = check(
            "skylight_intensity_is_dim", ok,
            ("SKYLIGHT_INTENSITY_OK value=%s band=[%s, %s]"
             % (value, SKYLIGHT_INTENSITY_MIN, SKYLIGHT_INTENSITY_MAX)) if ok
            else ("SKYLIGHT_INTENSITY_NOT_DIM value=%s band=[%s, %s] engine_default=1.0"
                  % (value, SKYLIGHT_INTENSITY_MIN, SKYLIGHT_INTENSITY_MAX)))
    except Exception as e:  # noqa: BLE001
        results["skylight_intensity_is_dim"] = check(
            "skylight_intensity_is_dim", False,
            "SKYLIGHT_INTENSITY_READ_ERROR raised %r" % (e,))

    try:
        live = _bool_property(ambient, "real_time_capture", "bRealTimeCapture",
                              "b_real_time_capture")
        results["skylight_recaptures_live_sky"] = check(
            "skylight_recaptures_live_sky", bool(live),
            ("SKYLIGHT_REALTIME_OK capture=%s" % bool(live)) if live
            else ("SKYLIGHT_NOT_REALTIME capture=%s engine_default=False" % bool(live)))
    except Exception as e:  # noqa: BLE001
        results["skylight_recaptures_live_sky"] = check(
            "skylight_recaptures_live_sky", False,
            "SKYLIGHT_REALTIME_READ_ERROR raised %r" % (e,))


def _fog_checks(results, fog, fog_detail):
    if fog is None:
        _fanout(results, ("fog_density_is_dense", "fog_volumetric_enabled",
                          "fog_extinction_raised"), fog_detail)
        return

    try:
        density = float(_read_property(fog, "fog_density", "FogDensity"))
        ok = FOG_DENSITY_MIN <= density <= FOG_DENSITY_MAX
        results["fog_density_is_dense"] = check(
            "fog_density_is_dense", ok,
            ("FOG_DENSITY_OK density=%s band=[%s, %s]"
             % (density, FOG_DENSITY_MIN, FOG_DENSITY_MAX)) if ok
            else ("FOG_DENSITY_TOO_THIN density=%s band=[%s, %s] engine_default=0.02"
                  % (density, FOG_DENSITY_MIN, FOG_DENSITY_MAX)))
    except Exception as e:  # noqa: BLE001
        results["fog_density_is_dense"] = check(
            "fog_density_is_dense", False, "FOG_DENSITY_READ_ERROR raised %r" % (e,))

    try:
        enabled = _bool_property(fog, "enable_volumetric_fog", "bEnableVolumetricFog",
                                 "b_enable_volumetric_fog", "volumetric_fog")
        results["fog_volumetric_enabled"] = check(
            "fog_volumetric_enabled", bool(enabled),
            ("FOG_VOLUMETRIC_OK enabled=%s" % bool(enabled)) if enabled
            else ("FOG_VOLUMETRIC_DISABLED enabled=%s engine_default=False"
                  % bool(enabled)))
    except Exception as e:  # noqa: BLE001
        results["fog_volumetric_enabled"] = check(
            "fog_volumetric_enabled", False,
            "FOG_VOLUMETRIC_READ_ERROR raised %r" % (e,))

    try:
        scale = float(_read_property(fog, "volumetric_fog_extinction_scale",
                                     "VolumetricFogExtinctionScale"))
        ok = scale >= FOG_EXTINCTION_MIN
        results["fog_extinction_raised"] = check(
            "fog_extinction_raised", ok,
            ("FOG_EXTINCTION_OK scale=%s required_min=%s" % (scale, FOG_EXTINCTION_MIN))
            if ok else
            ("FOG_EXTINCTION_TOO_LOW scale=%s required_min=%s engine_default=1.0"
             % (scale, FOG_EXTINCTION_MIN)))
    except Exception as e:  # noqa: BLE001
        results["fog_extinction_raised"] = check(
            "fog_extinction_raised", False,
            "FOG_EXTINCTION_READ_ERROR raised %r" % (e,))


def _compile_check(results):
    try:
        rig_bp = unreal.EditorAssetLibrary.load_asset(ASSET_RIG)
        status = _compile_status(rig_bp)
        ok = "UP_TO_DATE" in status.upper()
        results["rig_compiles_up_to_date"] = check(
            "rig_compiles_up_to_date", ok,
            ("RIG_COMPILE_OK status=%s" % status) if ok
            else ("RIG_NOT_UP_TO_DATE status=%s" % status))
    except Exception as e:  # noqa: BLE001
        results["rig_compiles_up_to_date"] = check(
            "rig_compiles_up_to_date", False, "RIG_COMPILE_READ_ERROR raised %r" % (e,))


def main():
    results = {}
    try:
        _rig_checks(results)
    except Exception as e:  # noqa: BLE001 - never abort the verdict
        _fanout(results, CHECK_IDS, "RIG_INTROSPECTION_ABORTED %r" % (e,))

    # Constant-length, deterministically ordered verdict.
    checks = [results.get(cid) or check(cid, False, "CHECK_NOT_EVALUATED %s" % cid)
              for cid in CHECK_IDS]
    emit_verdict(checks)


if __name__ == "__main__":
    main()
