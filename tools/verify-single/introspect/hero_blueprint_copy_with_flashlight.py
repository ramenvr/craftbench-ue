"""L2-introspect script for the t1-hero-blueprint-copy-with-flashlight task.

Structural, READ-ONLY verification of two Blueprint class assets via stock UE
editor-Python. Emits one CRAFTBENCH-INTROSPECT-JSON block the L2-introspect
layer parses (``layers/l2_introspect.py``; contract:
``layers/INTROSPECT_CONTRACT.md``).

What is graded (seed roster R5, re-pathed and re-tiered; see the task spec):
``BP_Hero`` must be a copy of the shipped baseline ``BP_Source`` that has been
rebuilt on the engine's walking-character class, keeps the source's ``Body``
subobject and ``Health = 100``, and carries a new cone-beam light named
``Flashlight`` attached beneath the INHERITED animated mesh with a non-default
brightness - while ``BP_Source`` itself is left untouched.

Hard rules honoured here:
  * READ-ONLY. Nothing below mutates an asset, a package, or the project.
  * Identity by **pre-declared content path** (``ASSET_HERO`` / ``ASSET_SOURCE``)
    and pre-declared subobject NAME, never by class. The one place a class is
    consulted is the assertion itself ("is this a walking-character class"),
    which is the graded property, not the lookup key - and it is written as an
    ``isinstance`` so a legitimate subclass is not penalized.
  * Stock UE Python only (``EditorAssetLibrary``, the SubobjectData interface,
    reflection). Never Aura's MCP tools - that would grade Aura with Aura.
  * Every check is wrapped in its own try/except, so one wrong API name
    degrades to exactly one FAILED check with the exception in ``detail``
    instead of aborting the verdict.
  * **FAIL CLOSED.** No check may pass on the strength of "a probe did not
    raise" or "the walk came back empty"; every PASS needs a positive read.
    The two NEGATIVE checks (``source_*``) are the sharp edge here - "I found
    no Flashlight" is only a pass when the component walk actually succeeded,
    which is why ``_gather_handles`` / ``_components`` RAISE on an empty walk
    instead of returning ``[]``, and why an unloadable ``BP_Source`` class is
    an error rather than "unchanged".
  * The check list has a **constant length (13)** on every leg, including a
    missing ``BP_Hero``. ``registry.py`` reports ``tests_passed/tests_run`` from
    these counts, so a constant denominator keeps the ratio comparable and
    stops a submission from improving its score by making checks unreachable.
    It was 11 until 2026-08-19; two SPECIFIED-but-ungated requirements-table rows
    were closed (``hero_locomotion_intact``, ``source_retains_body_and_health``)
    and every recorded score from before that date is out of 11, not 13.

Detail strings are stable, ASCII, greppable tokens. The discrimination MATRIX
joins on the raw ``detail`` string **as printed inside the JSON block**, not on
the layer's ``<script>:<check>: FAIL - ...`` note rendering, so each failing
check owns a unique ``*_MISSING`` / ``*_WRONG`` / ``*_NOT_*`` token that never
appears on the passing branch. No detail contains either of the two automation
result markers ("TestResult" + "=Passed", and "Automation Test" + " Succeeded")
that ``parse_automation_log``'s whole-file ``finditer`` counts as a TEST - a
detail carrying one would inflate the test tally and can flip a PASS to a FAIL
through the ``expected_test_count`` guard. Neither substring appears anywhere
in this file, including this docstring.

UE 5.8 API notes (routes confirmed live 2026-07-27 on UE 5.8.0-55116800,
headless editor; plan the introspection-coverage plan section 10):
  * ``SubobjectDataSubsystem`` is an **ENGINE** subsystem -
    ``unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)``.
    ``get_editor_subsystem`` on it raises ``TypeError: Cannot nativize``.
  * ``UBlueprint::ParentClass`` is a bare ``UPROPERTY()`` with no visibility
    specifier, so ``get_editor_property('parent_class')`` is NOT a reliable
    route. The parent is read from the generated class' CDO instead, and the
    asset-registry tags ``ParentClass`` / ``NativeParentClass`` are recorded
    alongside it for the human-readable detail.
  * ``UBlueprint::Status`` is ``UPROPERTY(transient, BlueprintReadOnly)`` - it
    is NOT serialized, so what this reads is the compile state produced by
    loading the submitted asset, which is the property worth gating.
  * ``ULocalLightComponent`` constructor sets ``Intensity = 5000`` (engine
    default, ``LocalLightComponent.cpp:13``), which is why the required
    brightness here is deliberately NOT 5000.
"""
import json

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax / format checks
    unreal = None

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

# --- Pre-declared identity (content PATHS and subobject NAMES, never class) --
TASK_ID = "t1-hero-blueprint-copy-with-flashlight"
ASSET_SOURCE = "/Game/Tasks/%s/BP_Source" % TASK_ID
ASSET_HERO = "/Game/Tasks/%s/BP_Hero" % TASK_ID

BODY_NAME = "Body"
FLASHLIGHT_NAME = "Flashlight"
HEALTH_PROPERTY = "Health"

# The inherited animated body part, under either spelling: the anchoring
# UPROPERTY name on the walking-character class ("Mesh") or the native
# subobject name it is constructed with ("CharacterMesh0"). Both are what the
# source row names, and FSubobjectData::GetVariableName can return either
# depending on whether an SCS node or a native component backs the subobject.
INHERITED_MESH_NAMES = ("Mesh", "CharacterMesh0")

# --- Graded scalars ----------------------------------------------------------
EXPECTED_HEALTH = 100.0
HEALTH_TOL = 0.01
EXPECTED_INTENSITY = 12000.0
INTENSITY_TOL = 0.5

# --- The check ids, in emission order. Length is the score denominator. ------
CHECK_IDS = (
    "hero_asset_exists",
    "hero_parent_is_character",
    "hero_locomotion_intact",
    "hero_retains_body_component",
    "hero_retains_health_100",
    "hero_has_flashlight_component",
    "hero_flashlight_is_cone_light",
    "hero_flashlight_attach_parent_is_mesh",
    "hero_flashlight_intensity_12000",
    "hero_compiles_up_to_date",
    "source_unchanged_not_character",
    "source_retains_body_and_health",
    "source_has_no_flashlight",
)

# --- Locomotion floors (requirements table row 6, closed 2026-08-19) ---------
#
# The prompt asks for a figure that "walks, jumps and collides using the
# engine's standard humanoid locomotion". Deriving from ACharacter was the only
# thing gated, and derivation is not capability: a Character subclass with
# MaxWalkSpeed = 0, jump zeroed, and the capsule set to NoCollision in its class
# defaults satisfied every check.
#
# These are FLOORS, not target values. The prompt names no speeds, so nothing
# here asserts a number the agent was never given - each bound only separates
# "this ability was switched off" from "this ability exists". The engine defaults
# (MaxWalkSpeed 500, JumpZVelocity 700) clear them by orders of magnitude, and so
# does any playable retune.
MIN_WALK_SPEED = 1.0
MIN_JUMP_VELOCITY = 1.0

# Emitted for every hero-side check that cannot run because BP_Hero is absent.
HERO_MISSING_TOKEN = "HERO_ASSET_MISSING"


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

    UE pythonizes UPROPERTY names (``Mesh`` -> ``mesh``) while Blueprint
    variables keep their authored spelling, and which one ``get_editor_property``
    resolves depends on the property. Trying both spellings is cheaper than
    being wrong, and it never invents a value - if every spelling fails the
    last exception propagates and the caller records a *_READ_ERROR.
    """
    last = None
    for name in names:
        try:
            return obj.get_editor_property(name)
        except Exception as e:  # noqa: BLE001
            last = e
    raise last if last is not None else AttributeError("no property name given")


def _registry_tag(path, tag_name):
    """Asset-registry tag value as a string, or '' - never raises.

    ``UAssetRegistryHelpers::GetTagValue`` is a ScriptMethod with a bool return
    AND an out param, so Python may hand back either ``(ok, value)`` or the
    value alone depending on codegen. Both shapes are handled.
    """
    try:
        data = unreal.EditorAssetLibrary.find_asset_data(path)
        res = data.get_tag_value(tag_name)
    except Exception:  # noqa: BLE001
        return ""
    if isinstance(res, (tuple, list)):
        if len(res) >= 2:
            return "" if res[1] is None else str(res[1])
        return "" if not res else str(res[0])
    return "" if res is None else str(res)


def _parent_tags(path):
    """A stable one-line summary of what the registry thinks the parent is."""
    return "ParentClass=%s NativeParentClass=%s" % (
        _registry_tag(path, "ParentClass") or "?",
        _registry_tag(path, "NativeParentClass") or "?",
    )


def _generated_cdo(path):
    """The class-default object of the Blueprint's generated class, or None."""
    cls = unreal.EditorAssetLibrary.load_blueprint_class(path)
    if cls is None:
        return None
    return unreal.get_default_object(cls)


def _is_walking_character(cdo):
    """True iff the generated class is the engine walking-character class or a
    subclass of it. Deliberately ``isinstance``, not class equality - see the
    spec's "Why the parent check accepts subclasses"."""
    return bool(cdo is not None and isinstance(cdo, unreal.Character))


def _subobject_subsystem():
    """The SubobjectData subsystem. ENGINE subsystem, not editor."""
    return unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)


def _gather_handles(subsystem, blueprint):
    """Every subobject handle on a Blueprint (root actor + all components).

    UE's Python codegen strips the ``K2_`` prefix off
    ``K2_GatherSubobjectDataForBlueprint``; the prefixed spelling is tried as a
    fallback in case a future build keeps it.

    FAIL-CLOSED: an unavailable accessor or an EMPTY gather RAISES. A Blueprint
    always has at least its root actor subobject
    (``SubobjectDataSubsystem.cpp:147-154`` gathers off
    ``GeneratedClass->GetDefaultObject()``), so an empty result is a broken
    walk, never a legitimate "this asset has no components". Returning ``[]``
    here used to hand the two NEGATIVE ``source_*`` checks a free PASS ("no
    Flashlight found") on an API break.
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


def _is_handle(obj):
    try:
        return isinstance(obj, unreal.SubobjectDataHandle)
    except Exception:  # noqa: BLE001
        return False


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


def _names_of(components):
    return sorted(n for n, _ in components if n)


def _find_component(components, name):
    for got, data in components:
        if got == name:
            return data
    return None


def _parent_data(data):
    """The FSubobjectData of a subobject's ATTACH PARENT, or None.

    FAIL-CLOSED: a handle whose validity cannot be established is treated as
    invalid (previously the validity probe raising was swallowed and the walk
    continued on an unvalidated handle).
    """
    lib = unreal.SubobjectDataBlueprintFunctionLibrary
    handle = lib.get_parent_handle(data)
    if isinstance(handle, (tuple, list)):
        handle = handle[-1] if handle else None
    if handle is None:
        return None
    validator = getattr(lib, "is_handle_valid", None)
    if validator is not None:
        try:
            valid = bool(validator(handle))
        except Exception:  # noqa: BLE001 - unreadable => not valid
            return None
        if not valid:
            return None
    return _data_for(handle)


def _bp_lib_tristate(fn_name, data):
    """A SubobjectData bool predicate as True / False / None.

    ``None`` means "could not be read", and every caller treats that as NOT
    satisfied. Never returns True on the strength of an absent exception.
    """
    fn = getattr(unreal.SubobjectDataBlueprintFunctionLibrary, fn_name, None)
    if fn is None:
        return None
    try:
        res = fn(data)
    except Exception:  # noqa: BLE001
        return None
    if isinstance(res, (tuple, list)):
        res = res[-1] if res else None
    return None if res is None else bool(res)


def _is_skeletal_mesh_component(obj):
    """``isinstance`` against the animated-mesh type as True / False / None.

    ``None`` means the probe could not be evaluated (type unexposed, or the
    isinstance itself raised). Callers treat that as NOT satisfied but report
    it under a distinct ``*_TYPE_PROBE_ERROR`` token - a broken probe is a
    harness event, never evidence about the submission.
    """
    if obj is None:
        return False
    try:
        return bool(isinstance(obj, unreal.SkeletalMeshComponent))
    except Exception:  # noqa: BLE001
        return None


def _path_name(obj):
    if obj is None:
        return ""
    try:
        return str(obj.get_path_name())
    except Exception:  # noqa: BLE001
        return ""


def _class_name(obj):
    if obj is None:
        return "None"
    try:
        return str(obj.get_class().get_name())
    except Exception:  # noqa: BLE001
        return "<unreadable>"


def _attach_parent_report(flashlight_data, hero_cdo):
    """``(ok, report)`` for "Flashlight hangs off the INHERITED animated mesh".

    A NAME MATCH IS NOT ENOUGH. Anti-gaming note #2 is defeated by any
    component the agent merely *names* ``CharacterMesh0``, so three
    INDEPENDENT positive facts must all hold, and any read that raises or comes
    back unknown makes the check FAIL:

      1. the SubobjectData parent handle resolves to a subobject whose name is
         one of ``INHERITED_MESH_NAMES``. This is the authoritative structural
         parent for a Blueprint: an SCS component TEMPLATE's own
         ``AttachParent`` pointer is null at rest, the hierarchy lives in the
         SCS node graph.
      2. that parent's component template really IS a skeletal (animated) mesh
         component - a ``StaticMeshComponent`` called ``CharacterMesh0`` dies
         here.
      3. that parent is INHERITED or NATIVE, not authored by this submission.
         ``FSubobjectData::IsInheritedComponent`` / ``IsNativeComponent`` are
         both ``BlueprintCallable``
         (``SubobjectDataBlueprintFunctionLibrary.h:113-117``), and for the
         Character's native ``CharacterMesh0`` both are true
         (``SubobjectData.cpp:1064-1103``). A component the agent added to
         BP_Hero's own SCS is neither, whatever it is called - this is the fact
         that actually closes the impostor hole.

    Two corroborating reads are recorded and can only ADD a failure:

      * ``USceneComponent::GetAttachParent`` - the UFUNCTION getter at
        ``SceneComponent.h:700-702``; the ``AttachParent`` /
        ``AttachSocketName`` UPROPERTIES are reflection-denied (plan 12.1), and
        ``GetAttachSocketName`` is the wrong accessor here because the graded
        property is the parent component, not a socket. On an SCS template this
        getter is normally null, so it gates only when it returns something.
      * object identity against ``ACharacter::Mesh`` on the hero CDO
        (``Character.h:351``, ``VisibleAnywhere|BlueprintReadOnly``).
        ``K2_GatherSubobjectDataForBlueprint`` walks
        ``GeneratedClass->GetDefaultObject()``
        (``SubobjectDataSubsystem.cpp:147-154``), so the inherited mesh
        subobject and the CDO's ``mesh`` are the same UObject and their path
        names match. Compared as PATH NAMES so no binding equality semantics
        are assumed; gates only when both path reads succeed.
    """
    parent = _parent_data(flashlight_data)
    if parent is None:
        return False, "parent=<none> reason=no_resolvable_parent_handle"

    parent_name = _sub_display_name(parent)
    name_ok = parent_name in INHERITED_MESH_NAMES

    parent_obj = _sub_object(parent)
    skeletal_ok = _is_skeletal_mesh_component(parent_obj)
    if skeletal_ok is None:
        return None, ("TYPE_PROBE_ERROR type=SkeletalMeshComponent parent=%s "
                      "parent_class=%s"
                      % (parent_name or "<none>", _class_name(parent_obj)))

    inherited = _bp_lib_tristate("is_inherited_component", parent)
    native = _bp_lib_tristate("is_native_component", parent)
    inherited_ok = (inherited is True) or (native is True)

    # Corroboration 1 - the UFUNCTION attach-parent getter.
    attach_getter = "<null>"
    attach_ok = True
    light_obj = _sub_object(flashlight_data)
    getter = getattr(light_obj, "get_attach_parent", None) if light_obj else None
    if getter is not None:
        try:
            raw = getter()
        except Exception as e:  # noqa: BLE001 - unreadable corroboration
            attach_getter = "<raised %r>" % (e,)
        else:
            if raw is not None:
                try:
                    attach_getter = str(raw.get_name())
                except Exception:  # noqa: BLE001
                    attach_getter = "<unnamed>"
                attach_ok = attach_getter in INHERITED_MESH_NAMES

    # Corroboration 2 - identity with the Character CDO's own inherited mesh.
    identity = "unknown"
    identity_ok = True
    try:
        cdo_mesh = (_read_property(hero_cdo, "mesh", "Mesh")
                    if hero_cdo is not None else None)
    except Exception:  # noqa: BLE001
        cdo_mesh = None
    cdo_path, parent_path = _path_name(cdo_mesh), _path_name(parent_obj)
    if cdo_path and parent_path:
        identity_ok = cdo_path == parent_path
        identity = "same" if identity_ok else "different"

    ok = bool(name_ok and skeletal_ok and inherited_ok
              and attach_ok and identity_ok)
    report = ("parent=%s parent_class=%s name_ok=%s skeletal=%s inherited=%s "
              "native=%s attach_getter=%s cdo_mesh=%s expected_one_of=%s"
              % (parent_name or "<none>", _class_name(parent_obj), name_ok,
                 skeletal_ok, inherited, native, attach_getter, identity,
                 list(INHERITED_MESH_NAMES)))
    return ok, report


def _locomotion_report(cdo):
    """``(ok, report)`` for "it walks, jumps and collides" (row 6).

    STRUCTURAL, and honest about it: there is no PIE world on this task
    (``layers: [L1, L2I]``), so nothing here observes the hero move. What it does
    do is refuse the four ways the ability can be switched off in class defaults
    while the class still derives from ACharacter - which is what
    ``hero_parent_is_character`` alone permitted:

      1. the movement component is gone entirely (gutted defaults);
      2. ``MaxWalkSpeed`` is zero, so "walks" is false at runtime;
      3. ``JumpZVelocity`` is zero, so "jumps" is false at runtime;
      4. the capsule's collision is ``NoCollision``, so "collides" is false.

    FAIL-CLOSED on every read. A property that cannot be read is NOT evidence
    that the ability is present - it makes the check fail with the exception
    recorded, exactly like the rest of this file.
    """
    if cdo is None:
        return False, "cdo=<none>"

    move = None
    try:
        move = _read_property(cdo, "character_movement", "CharacterMovement")
    except Exception as e:  # noqa: BLE001
        return False, "movement=<unreadable> raised %r" % (e,)
    if move is None:
        return False, "movement=<none> reason=movement_component_absent"

    def _num(obj, *names):
        """A float property, or None when unreadable."""
        try:
            return float(_read_property(obj, *names))
        except Exception:  # noqa: BLE001
            return None

    walk = _num(move, "max_walk_speed", "MaxWalkSpeed")
    jump = _num(move, "jump_z_velocity", "JumpZVelocity")

    # Collision: the capsule is ACharacter's root and the thing that collides.
    collision = "unreadable"
    collides_ok = False
    try:
        capsule = _read_property(cdo, "capsule_component", "CapsuleComponent")
    except Exception as e:  # noqa: BLE001
        capsule, collision = None, "raised %r" % (e,)
    if capsule is not None:
        getter = getattr(capsule, "get_collision_enabled", None)
        try:
            raw = (getter() if getter is not None
                   else _read_property(capsule, "collision_enabled", "CollisionEnabled"))
        except Exception as e:  # noqa: BLE001
            collision = "raised %r" % (e,)
        else:
            collision = str(raw)
            # Anything but the explicit off switch counts. Compared as a NAME so
            # no enum-binding equality is assumed, and phrased as "not off"
            # rather than "== QueryAndPhysics" so a query-only or physics-only
            # profile - both of which collide - is not punished.
            collides_ok = "NO_COLLISION" not in collision.upper()

    walk_ok = walk is not None and walk >= MIN_WALK_SPEED
    jump_ok = jump is not None and jump >= MIN_JUMP_VELOCITY
    ok = bool(walk_ok and jump_ok and collides_ok)
    report = ("walk=%s jump=%s collision=%s walk_ok=%s jump_ok=%s collides_ok=%s "
              "floors=(%s,%s)"
              % (walk, jump, collision, walk_ok, jump_ok, collides_ok,
                 MIN_WALK_SPEED, MIN_JUMP_VELOCITY))
    return ok, report


def _is_cone_light(component):
    """True iff the component projects a cone beam rather than an omni glow.

    FAIL-CLOSED. Every branch demands POSITIVE evidence:
      * a successful ``isinstance`` against the spot-light component type
        (subclass-tolerant); else
      * a cone half-angle that reads back as a real angle in ``(0, 90]``.
        A point light has no ``outer_cone_angle`` property at all, so the read
        raises and this returns False.

    It used to ``return True`` merely because the probe did not raise, which
    made ``hero_flashlight_is_cone_light`` unfailable the moment the property
    existed for any reason. "The probe did not raise" is not evidence.

    Tristate: returns ``None`` only when NEITHER route could be evaluated -
    the isinstance probe raised/was unexposed AND the cone-angle read raised.
    A point light also fails the cone-angle read, but for it the isinstance
    probe evaluates (to False), so the genuine negative keeps returning False;
    ``None`` is reserved for "both instruments broken", which is a harness
    event and must not wear the graded NOT_CONE token.
    """
    if component is None:
        return False
    type_probe_evaluated = True
    try:
        if isinstance(component, unreal.SpotLightComponent):
            return True
    except Exception:  # noqa: BLE001 - type not exposed; fall through to value
        type_probe_evaluated = False
    try:
        outer = float(_read_property(component, "outer_cone_angle", "OuterConeAngle"))
    except Exception:  # noqa: BLE001
        return False if type_probe_evaluated else None
    return 0.0 < outer <= 90.0


def _compile_status(blueprint):
    """A string for the Blueprint's compile status, e.g. 'BlueprintStatus.BS_UP_TO_DATE'."""
    return str(_read_property(blueprint, "status", "Status"))


# --------------------------------------------------------------------------- #
# the checks                                                                   #
# --------------------------------------------------------------------------- #

def _hero_checks(results):
    """Fill ``results`` (a dict keyed by check id) for every hero-side check."""
    # A raised probe is NOT the same event as a genuinely absent asset, and the
    # two must not share a token: an API break that fanned out
    # HERO_ASSET_MISSING would be credited as the empty leg's named failure.
    root_cause = None
    try:
        hero_exists = _asset_exists(ASSET_HERO)
    except Exception as e:  # noqa: BLE001
        root_cause = "HERO_ASSET_PROBE_ERROR %s raised %r" % (ASSET_HERO, e)
        results["hero_asset_exists"] = check("hero_asset_exists", False, root_cause)
        hero_exists = False
    else:
        if hero_exists:
            results["hero_asset_exists"] = check(
                "hero_asset_exists", True, "HERO_ASSET_OK %s" % ASSET_HERO)
        else:
            root_cause = "%s %s" % (HERO_MISSING_TOKEN, ASSET_HERO)
            results["hero_asset_exists"] = check("hero_asset_exists", False, root_cause)

    if not hero_exists:
        # Constant denominator: every hero-side check still reports, as a
        # failure whose detail names the single root cause.
        for cid in CHECK_IDS:
            if cid.startswith("hero_") and cid not in results:
                results[cid] = check(cid, False, root_cause)
        return

    # --- parent class --------------------------------------------------------
    # ``hero_cdo`` is reused by the attach-parent check below.
    hero_cdo = None
    try:
        hero_cdo = _generated_cdo(ASSET_HERO)
        if hero_cdo is None:
            # "the class would not load" is an ERROR event, not the graded
            # "it is not a walking character" failure - distinct token so it
            # can never be credited as a variant's named failure.
            results["hero_parent_is_character"] = check(
                "hero_parent_is_character", False,
                "HERO_PARENT_CDO_UNAVAILABLE %s" % ASSET_HERO)
        else:
            ok = _is_walking_character(hero_cdo)
            results["hero_parent_is_character"] = check(
                "hero_parent_is_character", ok,
                ("HERO_PARENT_OK %s" % _parent_tags(ASSET_HERO)) if ok
                else ("HERO_PARENT_NOT_CHARACTER %s" % _parent_tags(ASSET_HERO)))
    except Exception as e:  # noqa: BLE001
        results["hero_parent_is_character"] = check(
            "hero_parent_is_character", False, "HERO_PARENT_READ_ERROR raised %r" % (e,))

    # --- locomotion is actually switched ON (row 6) ---------------------------
    # Reuses the CDO the parent check already loaded: no new asset load.
    try:
        ok, report = _locomotion_report(hero_cdo)
        results["hero_locomotion_intact"] = check(
            "hero_locomotion_intact", ok,
            ("HERO_LOCOMOTION_OK %s" % report) if ok
            else ("HERO_LOCOMOTION_DISABLED %s" % report))
    except Exception as e:  # noqa: BLE001
        results["hero_locomotion_intact"] = check(
            "hero_locomotion_intact", False,
            "HERO_LOCOMOTION_READ_ERROR raised %r" % (e,))

    # --- subobject walk (shared by four checks) ------------------------------
    components = []
    walk_error = None
    try:
        hero_bp = unreal.EditorAssetLibrary.load_asset(ASSET_HERO)
        components = _components(hero_bp)
    except Exception as e:  # noqa: BLE001
        walk_error = repr(e)
    names = _names_of(components)

    # Body survived the copy.
    try:
        if walk_error is not None:
            raise RuntimeError(walk_error)
        body = _find_component(components, BODY_NAME)
        results["hero_retains_body_component"] = check(
            "hero_retains_body_component", body is not None,
            ("HERO_BODY_OK names=%s" % names) if body is not None
            else ("HERO_BODY_COMPONENT_MISSING names=%s" % names))
    except Exception as e:  # noqa: BLE001
        results["hero_retains_body_component"] = check(
            "hero_retains_body_component", False,
            "HERO_BODY_WALK_ERROR raised %r" % (e,))

    # Health survived the copy.
    try:
        cdo = _generated_cdo(ASSET_HERO)
        value = float(_read_property(cdo, HEALTH_PROPERTY, HEALTH_PROPERTY.lower()))
        ok = abs(value - EXPECTED_HEALTH) <= HEALTH_TOL
        results["hero_retains_health_100"] = check(
            "hero_retains_health_100", ok,
            ("HERO_HEALTH_OK value=%s" % value) if ok
            else ("HERO_HEALTH_NOT_100 value=%s" % value))
    except Exception as e:  # noqa: BLE001
        results["hero_retains_health_100"] = check(
            "hero_retains_health_100", False, "HERO_HEALTH_READ_ERROR raised %r" % (e,))

    # The Flashlight subobject exists.
    flashlight = None
    try:
        if walk_error is not None:
            raise RuntimeError(walk_error)
        flashlight = _find_component(components, FLASHLIGHT_NAME)
        results["hero_has_flashlight_component"] = check(
            "hero_has_flashlight_component", flashlight is not None,
            ("HERO_FLASHLIGHT_OK names=%s" % names) if flashlight is not None
            else ("HERO_FLASHLIGHT_MISSING names=%s" % names))
    except Exception as e:  # noqa: BLE001
        results["hero_has_flashlight_component"] = check(
            "hero_has_flashlight_component", False,
            "HERO_FLASHLIGHT_WALK_ERROR raised %r" % (e,))

    if flashlight is None:
        # A broken walk and a genuinely absent Flashlight are different events
        # and must not share a token.
        fanout = ("HERO_FLASHLIGHT_WALK_ERROR raised %s" % walk_error
                  if walk_error is not None
                  else "HERO_FLASHLIGHT_MISSING names=%s" % names)
        for cid in ("hero_flashlight_is_cone_light",
                    "hero_flashlight_attach_parent_is_mesh",
                    "hero_flashlight_intensity_12000"):
            results[cid] = check(cid, False, fanout)
    else:
        # It is a cone beam, not an omni light.
        try:
            component = _sub_object(flashlight)
            cls_name = "None" if component is None else str(component.get_class().get_name())
            tri = _is_cone_light(component) if component is not None else False
            if tri is None:
                results["hero_flashlight_is_cone_light"] = check(
                    "hero_flashlight_is_cone_light", False,
                    "HERO_FLASHLIGHT_CONE_TYPE_PROBE_ERROR class=%s" % cls_name)
            else:
                results["hero_flashlight_is_cone_light"] = check(
                    "hero_flashlight_is_cone_light", tri,
                    ("HERO_FLASHLIGHT_CONE_OK class=%s" % cls_name) if tri
                    else ("HERO_FLASHLIGHT_NOT_CONE class=%s" % cls_name))
        except Exception as e:  # noqa: BLE001
            results["hero_flashlight_is_cone_light"] = check(
                "hero_flashlight_is_cone_light", False,
                "HERO_FLASHLIGHT_CONE_READ_ERROR raised %r" % (e,))

        # It hangs off the INHERITED animated body part. Name + type +
        # inheritedness, not name alone - see _attach_parent_report.
        try:
            ok, report = _attach_parent_report(flashlight, hero_cdo)
            if ok is None:
                # A type probe that could not be evaluated is a harness event,
                # never the graded "mounted on the wrong parent" failure.
                results["hero_flashlight_attach_parent_is_mesh"] = check(
                    "hero_flashlight_attach_parent_is_mesh", False,
                    "HERO_FLASHLIGHT_ATTACH_TYPE_PROBE_ERROR %s" % report)
            else:
                results["hero_flashlight_attach_parent_is_mesh"] = check(
                    "hero_flashlight_attach_parent_is_mesh", bool(ok),
                    ("HERO_FLASHLIGHT_ATTACH_PARENT_OK %s" % report) if ok
                    else ("HERO_FLASHLIGHT_ATTACH_PARENT_WRONG %s" % report))
        except Exception as e:  # noqa: BLE001
            results["hero_flashlight_attach_parent_is_mesh"] = check(
                "hero_flashlight_attach_parent_is_mesh", False,
                "HERO_FLASHLIGHT_ATTACH_READ_ERROR raised %r" % (e,))

        # Its brightness is the required non-default value.
        try:
            component = _sub_object(flashlight)
            value = float(_read_property(component, "intensity", "Intensity"))
            ok = abs(value - EXPECTED_INTENSITY) <= INTENSITY_TOL
            results["hero_flashlight_intensity_12000"] = check(
                "hero_flashlight_intensity_12000", ok,
                ("HERO_FLASHLIGHT_INTENSITY_OK value=%s" % value) if ok
                else ("HERO_FLASHLIGHT_INTENSITY_WRONG value=%s expected=%s"
                      % (value, EXPECTED_INTENSITY)))
        except Exception as e:  # noqa: BLE001
            results["hero_flashlight_intensity_12000"] = check(
                "hero_flashlight_intensity_12000", False,
                "HERO_FLASHLIGHT_INTENSITY_READ_ERROR raised %r" % (e,))

    # --- compile status ------------------------------------------------------
    try:
        hero_bp = unreal.EditorAssetLibrary.load_asset(ASSET_HERO)
        status = _compile_status(hero_bp)
        ok = "UP_TO_DATE" in status.upper()
        results["hero_compiles_up_to_date"] = check(
            "hero_compiles_up_to_date", ok,
            ("HERO_COMPILE_OK status=%s" % status) if ok
            else ("HERO_NOT_UP_TO_DATE status=%s" % status))
    except Exception as e:  # noqa: BLE001
        results["hero_compiles_up_to_date"] = check(
            "hero_compiles_up_to_date", False, "HERO_COMPILE_READ_ERROR raised %r" % (e,))


def _source_checks(results):
    """The baseline must come back untouched. Runs whether or not BP_Hero exists."""
    # Still not a walking-character class (i.e. it was not reparented in place).
    try:
        if not _asset_exists(ASSET_SOURCE):
            results["source_unchanged_not_character"] = check(
                "source_unchanged_not_character", False,
                "SOURCE_ASSET_MISSING %s" % ASSET_SOURCE)
        else:
            cdo = _generated_cdo(ASSET_SOURCE)
            if cdo is None:
                # FAIL-CLOSED: this is a NEGATIVE check ("still not a
                # character"), so an unreadable class must not be scored as
                # "unchanged". Distinct token - it is an error, not the
                # graded failure.
                results["source_unchanged_not_character"] = check(
                    "source_unchanged_not_character", False,
                    "SOURCE_PARENT_CDO_UNAVAILABLE %s" % ASSET_SOURCE)
            else:
                changed = _is_walking_character(cdo)
                results["source_unchanged_not_character"] = check(
                    "source_unchanged_not_character", not changed,
                    ("SOURCE_PARENT_OK %s" % _parent_tags(ASSET_SOURCE)) if not changed
                    else ("SOURCE_PARENT_CHANGED %s" % _parent_tags(ASSET_SOURCE)))
    except Exception as e:  # noqa: BLE001
        results["source_unchanged_not_character"] = check(
            "source_unchanged_not_character", False,
            "SOURCE_PARENT_READ_ERROR raised %r" % (e,))

    # Still carries no light.
    #
    # The walk is done ONCE and reused by the baseline check below - BP_Source is
    # already loaded by this point, so row 14 costs no additional asset load.
    source_components = None
    source_walk_error = None
    try:
        if not _asset_exists(ASSET_SOURCE):
            results["source_has_no_flashlight"] = check(
                "source_has_no_flashlight", False,
                "SOURCE_ASSET_MISSING %s" % ASSET_SOURCE)
            source_walk_error = "SOURCE_ASSET_MISSING"
        else:
            source_bp = unreal.EditorAssetLibrary.load_asset(ASSET_SOURCE)
            source_components = _components(source_bp)
            names = _names_of(source_components)
            has = _find_component(source_components, FLASHLIGHT_NAME) is not None
            results["source_has_no_flashlight"] = check(
                "source_has_no_flashlight", not has,
                ("SOURCE_CLEAN_OK names=%s" % names) if not has
                else ("SOURCE_HAS_FLASHLIGHT names=%s" % names))
    except Exception as e:  # noqa: BLE001
        source_walk_error = repr(e)
        results["source_has_no_flashlight"] = check(
            "source_has_no_flashlight", False,
            "SOURCE_WALK_ERROR raised %r" % (e,))

    # The baseline is unchanged in the respects the prompt named: "an inert thing
    # with a cube body part named Body and a numeric value named Health set to
    # 100 ... BP_Source must be unchanged when you are done" (row 14).
    #
    # Before this, "unchanged" was sampled at exactly two properties - its parent
    # class and the absence of a light - so a submission could overlay a BP_Source
    # with Health rewritten or Body deleted and still pass both source_* checks.
    # This is the same pair of facts the hero side already gates on the COPY;
    # asserting them on the ORIGINAL too is what makes "leaving the original
    # untouched" mean something.
    #
    # FAIL-CLOSED, and pointedly so: this is a negative claim ("nothing changed"),
    # so an unreadable Health or a broken walk must never be scored as unchanged.
    try:
        if source_walk_error is not None:
            raise RuntimeError(source_walk_error)
        names = _names_of(source_components)
        body_ok = _find_component(source_components, BODY_NAME) is not None
        health = _read_property(_generated_cdo(ASSET_SOURCE),
                                HEALTH_PROPERTY, HEALTH_PROPERTY.lower())
        value = float(health)
        health_ok = abs(value - EXPECTED_HEALTH) <= HEALTH_TOL
        if body_ok and health_ok:
            detail = "SOURCE_BASELINE_OK body=1 health=%s names=%s" % (value, names)
        elif not body_ok:
            detail = "SOURCE_BODY_MISSING health=%s names=%s" % (value, names)
        else:
            detail = ("SOURCE_HEALTH_CHANGED value=%s expected=%s names=%s"
                      % (value, EXPECTED_HEALTH, names))
        results["source_retains_body_and_health"] = check(
            "source_retains_body_and_health", bool(body_ok and health_ok), detail)
    except Exception as e:  # noqa: BLE001
        results["source_retains_body_and_health"] = check(
            "source_retains_body_and_health", False,
            "SOURCE_BASELINE_READ_ERROR raised %r" % (e,))


def main():
    results = {}
    try:
        _hero_checks(results)
    except Exception as e:  # noqa: BLE001 - never abort the verdict
        for cid in CHECK_IDS:
            if cid.startswith("hero_") and cid not in results:
                results[cid] = check(cid, False, "HERO_INTROSPECTION_ABORTED %r" % (e,))
    try:
        _source_checks(results)
    except Exception as e:  # noqa: BLE001
        for cid in CHECK_IDS:
            if cid.startswith("source_") and cid not in results:
                results[cid] = check(cid, False, "SOURCE_INTROSPECTION_ABORTED %r" % (e,))

    # Constant-length, deterministically ordered verdict.
    checks = [results.get(cid) or check(cid, False, "CHECK_NOT_EVALUATED %s" % cid)
              for cid in CHECK_IDS]
    emit_verdict(checks)


if __name__ == "__main__":
    main()
