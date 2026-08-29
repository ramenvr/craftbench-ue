"""L2-introspect script for the kp-fog-and-postprocess-rig task (python basket).

Structural, READ-ONLY verification of ONE agent-authored LEVEL via stock UE
editor-Python. Emits one CRAFTBENCH-INTROSPECT-JSON block the L2-introspect
layer parses (``layers/l2_introspect.py``; contract:
``layers/INTROSPECT_CONTRACT.md``).

*** THIS IS THE FIRST INTROSPECT THAT LOADS A MAP. *** ``l2_introspect.py``
builds the editor command line with NO map argument, so this script must load
the graded level itself, headless, under ``-nullrhi`` (``_load_level`` below,
two routes, fail-closed). No shipped introspect did this before; treat the
pattern as UNPROVEN until the reference leg has run live (task notes.md,
risks).

What is graded (seed roster Block B row R28, sheet id
``t9-configure-fog-and-postprocess``, re-shaped; see the task spec): a level
saved at ``/Game/Tasks/kp-fog-and-postprocess-rig/L_FogRig`` carrying three
configured actors, identified by ACTOR LABEL - ``Fog`` (an exponential height
fog actor at exact density / height-falloff / inscattering-colour values),
``Mood`` (an UNBOUND post-process volume with four specific overrides
switched ON and their settings at exact values) and ``Ambient`` (a sky light
at an exact intensity).

Every numeric band below was DEAD-GATE AUDITED against the UE 5.8 engine
default on 2026-08-11, from engine source at
``<UE_ROOT>/Engine/Source/Runtime/Engine/``:

  * ``UExponentialHeightFogComponent``  FogDensity = 0.02, FogHeightFalloff
    = 0.2 (ExponentialHeightFogComponent.cpp:92-93),
    FogInscatteringLuminance = FLinearColor::Black (:76)
  * ``FPostProcessSettings``  every bOverride_* flag false via Memzero
    (Scene.cpp:398-402); BloomIntensity = 0.675 (:458); VignetteIntensity
    = 0.4 (:541); ColorSaturation = (1,1,1,1) (:408); AutoExposureBias =
    the ``r.DefaultFeature.AutoExposure.Bias`` cvar (:516-519), which is
    non-negative in the stock template - the graded band is negative
  * ``APostProcessVolume``  bUnbound never set in the ctor (only
    ``bEnabled = true``, PostProcessVolume.cpp:21) -> zero-initialised false
  * ``USkyLightComponent``  Intensity = 1 (ULightComponentBase; same audit
    as dawn_fog_lighting_rig.py)

The exact target values ARE in the agent-visible prompt - that is the python
basket's point (owner decision 2026-08-11): outcome-graded exactness that
makes editor scripting the natural route. The bands are therefore transcription
TOLERANCES around the promised numbers, and the dead-gate discipline still
holds: an untouched actor fails every value gate, and every override gate
additionally requires a flag whose default is false.

Hard rules honoured here (same as dawn_fog_lighting_rig.py):
  * READ-ONLY with respect to every asset and package. Loading a map into the
    headless editor mutates nothing on disk; nothing below saves, renames or
    deletes anything.
  * Identity by **pre-declared content path** (``LEVEL_ASSET``) and
    pre-declared ACTOR LABEL, never by class. Class is consulted only as an
    ASSERTION ("is the thing labelled Mood really a post-process volume"),
    written as ``isinstance`` so a legitimate subclass is not penalized.
  * Stock UE Python only. Never Aura's MCP tools.
  * Every check is wrapped in its own try/except, so one wrong API name
    degrades to exactly one FAILED check with the exception in ``detail``.
  * **FAIL CLOSED.** No check passes because a probe did not raise. A type
    probe that cannot be evaluated FAILS; an unreadable value is a
    ``*_READ_ERROR`` failure; a level that exists but will not load, or loads
    the WRONG world, fails everything downstream with that single root cause.
    Every absence check is conjoined with the positive existence chain
    (asset exists -> level loads -> world identity matches) that precedes it.
  * The check list has a **constant length (14)** on every leg, including a
    missing submission (the empty leg scores 0/14 - this task ships no
    baseline, so there is nothing for an empty submission to pass).

Detail strings are stable, ASCII, greppable tokens. The discrimination MATRIX
joins on the raw ``detail`` string as printed inside the JSON block. Each
failing check owns a unique token that never appears on a passing branch, and
every MATRIX-creditable span sits INSIDE ONE string literal (never split
across concatenations or printf placeholders - the MATRIX oracle greps source
literals statically). Exception paths own ``*_READ_ERROR`` / ``*_PROBE_ERROR``
/ ``*_WALK_ERROR`` / ``*_LOAD_ERROR`` / ``*_ABORTED`` tokens that appear in NO
matrix row. No detail contains either automation result marker ("TestResult"
+ "=Passed" / "Automation Test" + " Succeeded"); neither substring appears
anywhere in this file.

UE 5.8 API notes:
  * Level load, route 1: ``unreal.get_editor_subsystem(
    unreal.LevelEditorSubsystem).load_level(asset_path)`` -> bool.
    Route 2: ``unreal.EditorLoadingAndSavingUtils.load_map(path)`` -> World.
    Both are then verified against the EDITOR WORLD's package path - a truthy
    return alone is not trusted (fail-closed on the wrong-world case).
  * Actor enumeration: ``unreal.get_editor_subsystem(
    unreal.EditorActorSubsystem).get_all_level_actors()``; legacy
    ``unreal.EditorLevelLibrary`` spelling as fallback.
  * ``AActor::GetActorLabel`` is BlueprintCallable (editor build), so
    ``actor.get_actor_label()`` reads; labels are saved into the level.
  * ``FogDensity`` / ``FogHeightFalloff`` / ``FogInscatteringLuminance`` are
    BlueprintReadOnly|interp (ExponentialHeightFogComponent.h:22-43).
  * ``APostProcessVolume::Settings`` is ``UPROPERTY(interp)``
    (PostProcessVolume.h:27; interp implies CPF_Edit) and ``bUnbound`` is
    EditAnywhere|BlueprintReadWrite (:50-51), so both read.
  * ``FPostProcessSettings`` value members are interp|BlueprintReadWrite and
    every ``bOverride_*`` flag is EditAnywhere|BlueprintReadWrite
    (Scene.h:819-820, 726-727, 937, 1015, 1628-1629), so all read.
  * UE pythonizes a bool UPROPERTY by dropping the leading ``b``
    (``bUnbound`` -> ``unbound``, ``bOverride_BloomIntensity`` ->
    ``override_bloom_intensity``). Every read tries several spellings.
"""
import json

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax / format checks
    unreal = None

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

# --- Pre-declared identity (content PATH and actor LABELS, never class) ------
TASK_ID = "kp-fog-and-postprocess-rig"
LEVEL_NAME = "L_FogRig"
LEVEL_ASSET = "/Game/Tasks/%s/%s" % (TASK_ID, LEVEL_NAME)

FOG_LABEL = "Fog"
PPV_LABEL = "Mood"
SKY_LABEL = "Ambient"

# --- Graded bands (prompt target in the middle; every band EXCLUDES the ------
# --- UE 5.8 engine default audited in the docstring) --------------------------

# Fog thickness. Prompt: exactly 0.03. Default 0.02 is below the floor.
FOG_DENSITY_MIN = 0.025
FOG_DENSITY_MAX = 0.035

# Fog height falloff. Prompt: exactly 0.15. Default 0.2 is above the ceiling.
FOG_FALLOFF_MIN = 0.13
FOG_FALLOFF_MAX = 0.17

# Fog inscattering colour. Prompt: (0.02, 0.04, 0.10), full alpha. Default is
# FLinearColor::Black - the blue channel alone (0.10 vs 0.0 at tolerance 0.01)
# excludes it, and red/green exclude it independently. Alpha is NOT graded
# (target 1.0 equals nothing observable on a black default; see task.md
# accepted residuals).
FOG_COLOR_TARGET = (0.02, 0.04, 0.10)
FOG_COLOR_TOL = 0.01

# Post-process overrides. Every check requires flag AND band in ONE conjoined
# check - the flag's default is false, so each gate is dead-gate-safe twice.
BLOOM_MIN = 1.7          # prompt 1.8; default 0.675
BLOOM_MAX = 1.9
VIGNETTE_MIN = 0.55      # prompt 0.6; default 0.4 (sheet's 0.45 was re-cut,
VIGNETTE_MAX = 0.65      # see task notes.md divergence 2)
SATURATION_TARGET = (0.85, 0.88, 0.95)   # default (1, 1, 1); W not graded
SATURATION_TOL = 0.02
EXPOSURE_MIN = -0.6      # prompt -0.5; default is the cvar-driven
EXPOSURE_MAX = -0.4      # non-negative r.DefaultFeature.AutoExposure.Bias

# Sky light brightness. Prompt: exactly 0.2. Default 1.0 is above the ceiling.
SKYLIGHT_MIN = 0.15
SKYLIGHT_MAX = 0.25

# --- The check ids, in emission order. Length is the score denominator. ------
CHECK_IDS = (
    "level_asset_exists",
    "level_loads_clean",
    "fog_actor_present",
    "fog_density_exact",
    "fog_falloff_exact",
    "fog_color_night_blue",
    "ppv_actor_present",
    "ppv_is_unbound",
    "ppv_bloom_overridden",
    "ppv_vignette_overridden",
    "ppv_saturation_overridden",
    "ppv_exposure_bias_overridden",
    "skylight_actor_present",
    "skylight_intensity_exact",
)

# --- Actor-resolution token templates. Each template is ONE literal so every
# --- MATRIX-creditable span (token + " labels=" / " class=" / " count=") sits
# --- inside a single literal run, never across a placeholder. ----------------
FOG_TOKENS = {
    "missing": "FOG_ACTOR_MISSING labels=%s wanted=Fog",
    "duplicate": "FOG_ACTOR_DUPLICATE count=%d label=Fog",
    "wrong_type": "FOG_ACTOR_WRONG_TYPE class=%s label=Fog expected=ExponentialHeightFog",
    "probe": "FOG_ACTOR_TYPE_PROBE_ERROR class=%s expected=ExponentialHeightFog",
    "ok": "FOG_ACTOR_OK class=%s label=Fog",
}
PPV_TOKENS = {
    "missing": "PPV_ACTOR_MISSING labels=%s wanted=Mood",
    "duplicate": "PPV_ACTOR_DUPLICATE count=%d label=Mood",
    "wrong_type": "PPV_ACTOR_WRONG_TYPE class=%s label=Mood expected=PostProcessVolume",
    "probe": "PPV_ACTOR_TYPE_PROBE_ERROR class=%s expected=PostProcessVolume",
    "ok": "PPV_ACTOR_OK class=%s label=Mood",
}
SKY_TOKENS = {
    "missing": "SKYLIGHT_ACTOR_MISSING labels=%s wanted=Ambient",
    "duplicate": "SKYLIGHT_ACTOR_DUPLICATE count=%d label=Ambient",
    "wrong_type": "SKYLIGHT_ACTOR_WRONG_TYPE class=%s label=Ambient expected=SkyLight",
    "probe": "SKYLIGHT_ACTOR_TYPE_PROBE_ERROR class=%s expected=SkyLight",
    "ok": "SKYLIGHT_ACTOR_OK class=%s label=Ambient",
}


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

def _read_property(obj, *names):
    """First readable spelling of a reflected property; re-raises if none is.

    UE pythonizes UPROPERTY names (``FogDensity`` -> ``fog_density``; a bool
    loses its leading ``b``). Trying every plausible spelling never invents a
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


def _asset_exists(path):
    return bool(unreal.EditorAssetLibrary.does_asset_exist(path))


# --------------------------------------------------------------------------- #
# level loading - THE new pattern (no other introspect loads a map)            #
# --------------------------------------------------------------------------- #

def _editor_world():
    """The currently loaded editor world. Raises if unreachable."""
    try:
        ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if ues is not None:
            world = ues.get_editor_world()
            if world is not None:
                return world
    except Exception:  # noqa: BLE001 - fall through to the legacy spelling
        pass
    ell = getattr(unreal, "EditorLevelLibrary", None)
    if ell is not None and getattr(ell, "get_editor_world", None) is not None:
        world = ell.get_editor_world()
        if world is not None:
            return world
    raise RuntimeError("EDITOR_WORLD_UNAVAILABLE")


def _load_level():
    """``(world, route)`` after loading LEVEL_ASSET into the editor.

    FAIL-CLOSED: a falsy return from one route falls through to the next; when
    every route is exhausted this RAISES with each attempt recorded. A truthy
    return is NOT trusted by itself - the caller still verifies the loaded
    world's package path (``_world_matches``), so a route that "succeeds" into
    the wrong map cannot pass.
    """
    attempts = []
    # Route 1: LevelEditorSubsystem.load_level (5.1+ canonical).
    try:
        les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    except Exception as e:  # noqa: BLE001
        les = None
        attempts.append("LevelEditorSubsystem raised %r" % (e,))
    if les is not None and getattr(les, "load_level", None) is not None:
        try:
            if bool(les.load_level(LEVEL_ASSET)):
                return _editor_world(), "level_editor_subsystem"
            attempts.append("load_level returned False")
        except Exception as e:  # noqa: BLE001
            attempts.append("load_level raised %r" % (e,))
    # Route 2: EditorLoadingAndSavingUtils.load_map (returns the World).
    utils = getattr(unreal, "EditorLoadingAndSavingUtils", None)
    fn = getattr(utils, "load_map", None) if utils is not None else None
    if fn is not None:
        try:
            world = fn(LEVEL_ASSET)
            if world is not None:
                return world, "loading_and_saving_utils"
            attempts.append("load_map returned None")
        except Exception as e:  # noqa: BLE001
            attempts.append("load_map raised %r" % (e,))
    raise RuntimeError("LEVEL_LOAD_ROUTES_EXHAUSTED attempts=%s" % attempts)


def _world_matches(world):
    """``(ok, world_path)`` - is the loaded world really the graded level?"""
    path = str(world.get_path_name())
    return path.startswith(LEVEL_ASSET + "."), path


def _all_level_actors():
    """Every placed actor in the loaded level. Raises if no route reads."""
    try:
        eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    except Exception:  # noqa: BLE001
        eas = None
    if eas is not None and getattr(eas, "get_all_level_actors", None) is not None:
        return list(eas.get_all_level_actors() or [])
    ell = getattr(unreal, "EditorLevelLibrary", None)
    if ell is not None and getattr(ell, "get_all_level_actors", None) is not None:
        return list(ell.get_all_level_actors() or [])
    raise RuntimeError("ACTOR_ENUMERATION_UNAVAILABLE")


def _label(actor):
    """The actor's editor label, or "" (an unreadable label can only produce
    a MISSING failure downstream, never a false pass)."""
    try:
        return str(actor.get_actor_label())
    except Exception:  # noqa: BLE001
        return ""


# --------------------------------------------------------------------------- #
# actor resolution (label AND type, both required)                             #
# --------------------------------------------------------------------------- #

def _resolve_actor(actors, labels, wanted_label, type_name, tokens):
    """``(actor_or_None, detail)`` for one pre-declared actor.

    A LABEL MATCH IS NOT ENOUGH - a submission that merely *labels* something
    ``Mood`` must not satisfy the post-process checks. Required, fail-closed:

      1. exactly ONE actor carries the pre-declared label (zero -> missing,
         two or more -> duplicate, both FAIL);
      2. ``isinstance`` against the required actor type returns True
         (subclass-tolerant). A probe that cannot be evaluated returns
         ``None`` and is treated as NOT satisfied.

    The outcomes carry DIFFERENT tokens, so the matrix can tell "absent" from
    "impostor" from "ambiguous" from "type not exposed to Python".
    """
    matches = [a for a in actors if _label(a) == wanted_label]
    if not matches:
        return None, tokens["missing"] % (labels,)
    if len(matches) > 1:
        return None, tokens["duplicate"] % len(matches)
    actor = matches[0]
    verdict = _isinstance_tristate(actor, type_name)
    if verdict is None:
        return None, tokens["probe"] % (_class_name(actor),)
    if not verdict:
        return None, tokens["wrong_type"] % (_class_name(actor),)
    return actor, tokens["ok"] % (_class_name(actor),)


def _component_of(actor, type_name):
    """The actor's first component of ``unreal.<type_name>``. Raises if the
    class is unexposed or the actor carries none (both fail closed)."""
    cls = getattr(unreal, type_name, None)
    if cls is None:
        raise RuntimeError("COMPONENT_CLASS_UNEXPOSED %s" % type_name)
    comps = list(actor.get_components_by_class(cls) or [])
    if not comps:
        raise RuntimeError("COMPONENT_ABSENT %s on %s"
                           % (type_name, _class_name(actor)))
    return comps[0]


def _linear_rgb(color):
    """``(r, g, b)`` floats of an FLinearColor."""
    out = []
    for lower, upper in (("r", "R"), ("g", "G"), ("b", "B")):
        val = getattr(color, lower, None)
        if val is None:
            val = getattr(color, upper, None)
        if val is None:
            val = _read_property(color, lower, upper)
        out.append(float(val))
    return tuple(out)


def _vec4_xyz(vec):
    """``(x, y, z)`` floats of an FVector4."""
    out = []
    for lower, upper in (("x", "X"), ("y", "Y"), ("z", "Z")):
        val = getattr(vec, lower, None)
        if val is None:
            val = getattr(vec, upper, None)
        if val is None:
            val = _read_property(vec, lower, upper)
        out.append(float(val))
    return tuple(out)


# --------------------------------------------------------------------------- #
# the checks                                                                   #
# --------------------------------------------------------------------------- #

def _fanout(results, cids, detail):
    for cid in cids:
        if cid not in results:
            results[cid] = check(cid, False, detail)


def _rig_checks(results):
    """Fill ``results`` (a dict keyed by check id) for every check."""
    # --- existence (a raised probe is NOT a genuinely absent level and the ---
    # --- two never share a token) --------------------------------------------
    root_cause = None
    try:
        exists = _asset_exists(LEVEL_ASSET)
    except Exception as e:  # noqa: BLE001
        root_cause = "RIG_LEVEL_PROBE_ERROR path=%s raised %r" % (LEVEL_ASSET, e)
        results["level_asset_exists"] = check(
            "level_asset_exists", False, root_cause)
        exists = False
    else:
        if exists:
            results["level_asset_exists"] = check(
                "level_asset_exists", True, "RIG_LEVEL_OK path=%s" % LEVEL_ASSET)
        else:
            root_cause = "RIG_LEVEL_MISSING path=%s" % LEVEL_ASSET
            results["level_asset_exists"] = check(
                "level_asset_exists", False, root_cause)
    if not exists:
        # Constant denominator: every remaining check still reports, as a
        # failure whose detail names the single root cause.
        _fanout(results, CHECK_IDS, root_cause)
        return

    # --- load + world identity (THE map-loading pattern) ---------------------
    try:
        world, route = _load_level()
    except Exception as e:  # noqa: BLE001
        detail = "LEVEL_LOAD_ERROR raised %r" % (e,)
        results["level_loads_clean"] = check("level_loads_clean", False, detail)
        _fanout(results, CHECK_IDS, detail)
        return
    try:
        ok, world_path = _world_matches(world)
    except Exception as e:  # noqa: BLE001
        detail = "LEVEL_WORLD_PROBE_ERROR raised %r" % (e,)
        results["level_loads_clean"] = check("level_loads_clean", False, detail)
        _fanout(results, CHECK_IDS, detail)
        return
    if not ok:
        detail = ("LEVEL_WRONG_WORLD world=%s expected_prefix=%s"
                  % (world_path, LEVEL_ASSET))
        results["level_loads_clean"] = check("level_loads_clean", False, detail)
        _fanout(results, CHECK_IDS, detail)
        return
    results["level_loads_clean"] = check(
        "level_loads_clean", True,
        "LEVEL_LOAD_OK world=%s route=%s" % (world_path, route))

    # --- actor walk ----------------------------------------------------------
    try:
        actors = _all_level_actors()
    except Exception as e:  # noqa: BLE001
        detail = "LEVEL_ACTOR_WALK_ERROR raised %r" % (e,)
        _fanout(results, CHECK_IDS, detail)
        return
    labels = sorted(name for name in (_label(a) for a in actors) if name)

    fog, fog_detail = _resolve_actor(
        actors, labels, FOG_LABEL, "ExponentialHeightFog", FOG_TOKENS)
    ppv, ppv_detail = _resolve_actor(
        actors, labels, PPV_LABEL, "PostProcessVolume", PPV_TOKENS)
    sky, sky_detail = _resolve_actor(
        actors, labels, SKY_LABEL, "SkyLight", SKY_TOKENS)

    results["fog_actor_present"] = check(
        "fog_actor_present", fog is not None, fog_detail)
    results["ppv_actor_present"] = check(
        "ppv_actor_present", ppv is not None, ppv_detail)
    results["skylight_actor_present"] = check(
        "skylight_actor_present", sky is not None, sky_detail)

    _fog_checks(results, fog, fog_detail)
    _ppv_checks(results, ppv, ppv_detail)
    _sky_checks(results, sky, sky_detail)


def _fog_checks(results, fog, fog_detail):
    """The three graded numbers on the height-fog actor's fog component.

    When the actor did not resolve (absent, impostor, duplicate, unreadable
    probe) these fan out carrying the SAME resolution detail, so the failure
    is attributed once and to the right cause.
    """
    cids = ("fog_density_exact", "fog_falloff_exact", "fog_color_night_blue")
    if fog is None:
        _fanout(results, cids, fog_detail)
        return
    try:
        comp = _component_of(fog, "ExponentialHeightFogComponent")
    except Exception as e:  # noqa: BLE001
        _fanout(results, cids, "FOG_COMPONENT_READ_ERROR raised %r" % (e,))
        return

    try:
        density = float(_read_property(comp, "fog_density", "FogDensity"))
        ok = FOG_DENSITY_MIN <= density <= FOG_DENSITY_MAX
        results["fog_density_exact"] = check(
            "fog_density_exact", ok,
            ("FOG_DENSITY_OK density=%s band=[%s, %s]"
             % (density, FOG_DENSITY_MIN, FOG_DENSITY_MAX)) if ok
            else ("FOG_DENSITY_OFF_TARGET density=%s band=[%s, %s] "
                  "target=0.03 engine_default=0.02"
                  % (density, FOG_DENSITY_MIN, FOG_DENSITY_MAX)))
    except Exception as e:  # noqa: BLE001
        results["fog_density_exact"] = check(
            "fog_density_exact", False, "FOG_DENSITY_READ_ERROR raised %r" % (e,))

    try:
        falloff = float(_read_property(
            comp, "fog_height_falloff", "FogHeightFalloff"))
        ok = FOG_FALLOFF_MIN <= falloff <= FOG_FALLOFF_MAX
        results["fog_falloff_exact"] = check(
            "fog_falloff_exact", ok,
            ("FOG_FALLOFF_OK falloff=%s band=[%s, %s]"
             % (falloff, FOG_FALLOFF_MIN, FOG_FALLOFF_MAX)) if ok
            else ("FOG_FALLOFF_OFF_TARGET falloff=%s band=[%s, %s] "
                  "target=0.15 engine_default=0.2"
                  % (falloff, FOG_FALLOFF_MIN, FOG_FALLOFF_MAX)))
    except Exception as e:  # noqa: BLE001
        results["fog_falloff_exact"] = check(
            "fog_falloff_exact", False, "FOG_FALLOFF_READ_ERROR raised %r" % (e,))

    try:
        col = _read_property(comp, "fog_inscattering_luminance",
                             "FogInscatteringLuminance",
                             "fog_inscattering_color", "FogInscatteringColor")
        if col is None:
            raise RuntimeError("FOG_COLOR_UNREADABLE")
        r, g, b = _linear_rgb(col)
        ok = all(abs(got - want) <= FOG_COLOR_TOL
                 for got, want in zip((r, g, b), FOG_COLOR_TARGET))
        summary = "(%.4f, %.4f, %.4f)" % (r, g, b)
        results["fog_color_night_blue"] = check(
            "fog_color_night_blue", ok,
            ("FOG_COLOR_OK color=%s target=(0.02, 0.04, 0.1) tolerance=0.01"
             % summary) if ok
            else ("FOG_COLOR_OFF_TARGET color=%s target=(0.02, 0.04, 0.1) "
                  "tolerance=0.01 engine_default=black" % summary))
    except Exception as e:  # noqa: BLE001
        results["fog_color_night_blue"] = check(
            "fog_color_night_blue", False,
            "FOG_COLOR_READ_ERROR raised %r" % (e,))


def _ppv_checks(results, ppv, ppv_detail):
    """Unbound + the four override gates on the post-process volume.

    Each override gate requires the override FLAG (default false) AND the
    value inside its band, conjoined in ONE check - setting the value while
    leaving the flag off (the classic inert-settings trap) fails, and flipping
    the flag while leaving the value default fails too.
    """
    cids = ("ppv_is_unbound", "ppv_bloom_overridden", "ppv_vignette_overridden",
            "ppv_saturation_overridden", "ppv_exposure_bias_overridden")
    if ppv is None:
        _fanout(results, cids, ppv_detail)
        return

    try:
        unbound = bool(_read_property(ppv, "unbound", "bUnbound", "b_unbound"))
        results["ppv_is_unbound"] = check(
            "ppv_is_unbound", unbound,
            ("PPV_UNBOUND_OK unbound=%s" % unbound) if unbound
            else ("PPV_NOT_UNBOUND unbound=%s engine_default=False" % unbound))
    except Exception as e:  # noqa: BLE001
        results["ppv_is_unbound"] = check(
            "ppv_is_unbound", False, "PPV_UNBOUND_READ_ERROR raised %r" % (e,))

    try:
        settings = _read_property(ppv, "settings", "Settings")
        if settings is None:
            raise RuntimeError("PPV_SETTINGS_NONE")
    except Exception as e:  # noqa: BLE001
        _fanout(results, ("ppv_bloom_overridden", "ppv_vignette_overridden",
                          "ppv_saturation_overridden",
                          "ppv_exposure_bias_overridden"),
                "PPV_SETTINGS_READ_ERROR raised %r" % (e,))
        return

    _flag_scalar_check(
        results, "ppv_bloom_overridden", settings,
        ("override_bloom_intensity", "bOverride_BloomIntensity",
         "b_override_bloom_intensity"),
        ("bloom_intensity", "BloomIntensity"),
        BLOOM_MIN, BLOOM_MAX,
        "PPV_BLOOM_OK override=%s value=%s band=[%s, %s]",
        "PPV_BLOOM_NOT_SET override=%s value=%s band=[%s, %s] "
        "target=1.8 engine_default=0.675 override_default=False",
        "PPV_BLOOM_READ_ERROR raised %r")

    _flag_scalar_check(
        results, "ppv_vignette_overridden", settings,
        ("override_vignette_intensity", "bOverride_VignetteIntensity",
         "b_override_vignette_intensity"),
        ("vignette_intensity", "VignetteIntensity"),
        VIGNETTE_MIN, VIGNETTE_MAX,
        "PPV_VIGNETTE_OK override=%s value=%s band=[%s, %s]",
        "PPV_VIGNETTE_NOT_SET override=%s value=%s band=[%s, %s] "
        "target=0.6 engine_default=0.4 override_default=False",
        "PPV_VIGNETTE_READ_ERROR raised %r")

    try:
        flag = bool(_read_property(
            settings, "override_color_saturation", "bOverride_ColorSaturation",
            "b_override_color_saturation"))
        vec = _read_property(settings, "color_saturation", "ColorSaturation")
        if vec is None:
            raise RuntimeError("PPV_SATURATION_NONE")
        x, y, z = _vec4_xyz(vec)
        in_band = all(abs(got - want) <= SATURATION_TOL
                      for got, want in zip((x, y, z), SATURATION_TARGET))
        ok = flag and in_band
        summary = "(%.4f, %.4f, %.4f)" % (x, y, z)
        results["ppv_saturation_overridden"] = check(
            "ppv_saturation_overridden", ok,
            ("PPV_SATURATION_OK override=%s value=%s "
             "target=(0.85, 0.88, 0.95) tolerance=0.02" % (flag, summary))
            if ok else
            ("PPV_SATURATION_NOT_SET override=%s value=%s "
             "target=(0.85, 0.88, 0.95) tolerance=0.02 "
             "engine_default=(1, 1, 1) override_default=False"
             % (flag, summary)))
    except Exception as e:  # noqa: BLE001
        results["ppv_saturation_overridden"] = check(
            "ppv_saturation_overridden", False,
            "PPV_SATURATION_READ_ERROR raised %r" % (e,))

    _flag_scalar_check(
        results, "ppv_exposure_bias_overridden", settings,
        ("override_auto_exposure_bias", "bOverride_AutoExposureBias",
         "b_override_auto_exposure_bias"),
        ("auto_exposure_bias", "AutoExposureBias"),
        EXPOSURE_MIN, EXPOSURE_MAX,
        "PPV_EXPOSURE_OK override=%s value=%s band=[%s, %s]",
        "PPV_EXPOSURE_NOT_SET override=%s value=%s band=[%s, %s] "
        "target=-0.5 engine_default=cvar_nonnegative override_default=False",
        "PPV_EXPOSURE_READ_ERROR raised %r")


def _flag_scalar_check(results, cid, settings, flag_names, value_names,
                       lo, hi, ok_t, fail_t, err_t):
    """One conjoined override gate: flag is ON and value is in [lo, hi].

    ``ok_t`` / ``fail_t`` take ``(flag, value, lo, hi)``; ``err_t`` takes the
    exception. Templates are single literals owned by the caller so every
    greppable span stays inside one literal run.
    """
    try:
        flag = bool(_read_property(settings, *flag_names))
        value = float(_read_property(settings, *value_names))
        ok = flag and (lo <= value <= hi)
        results[cid] = check(
            cid, ok, (ok_t if ok else fail_t) % (flag, value, lo, hi))
    except Exception as e:  # noqa: BLE001
        results[cid] = check(cid, False, err_t % (e,))


def _sky_checks(results, sky, sky_detail):
    if sky is None:
        _fanout(results, ("skylight_intensity_exact",), sky_detail)
        return
    try:
        comp = _component_of(sky, "SkyLightComponent")
        value = float(_read_property(comp, "intensity", "Intensity"))
        ok = SKYLIGHT_MIN <= value <= SKYLIGHT_MAX
        results["skylight_intensity_exact"] = check(
            "skylight_intensity_exact", ok,
            ("SKYLIGHT_INTENSITY_OK value=%s band=[%s, %s]"
             % (value, SKYLIGHT_MIN, SKYLIGHT_MAX)) if ok
            else ("SKYLIGHT_INTENSITY_OFF_TARGET value=%s band=[%s, %s] "
                  "target=0.2 engine_default=1.0"
                  % (value, SKYLIGHT_MIN, SKYLIGHT_MAX)))
    except Exception as e:  # noqa: BLE001
        results["skylight_intensity_exact"] = check(
            "skylight_intensity_exact", False,
            "SKYLIGHT_INTENSITY_READ_ERROR raised %r" % (e,))


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
