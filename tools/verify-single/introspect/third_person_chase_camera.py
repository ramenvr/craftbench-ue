"""L2-introspect script for the t1-third-person-chase-camera task.

Structural, READ-ONLY verification of ONE Blueprint character asset via stock
UE editor-Python. Emits one CRAFTBENCH-INTROSPECT-JSON block the L2-introspect
layer parses (``layers/l2_introspect.py``; contract:
``layers/INTROSPECT_CONTRACT.md``).

What is graded (seed roster R11 ``t10-spring-arm-camera``, re-pathed, re-tiered
and DEAD-GATE-corrected; see the task spec): the shipped baseline character
``BP_Scout`` starts as a first-person figure whose only viewpoint component,
``FollowCamera``, is bolted to the inherited collision capsule and steers
itself off the player's control rotation. The submission must convert it to a
third-person chase rig by ADDING a boom named ``CameraBoom`` on the capsule
root and re-homing ``FollowCamera`` onto that boom, off control rotation.

Hard rules honoured here:
  * READ-ONLY. Nothing below mutates an asset, a package, or the project.
  * Identity by **pre-declared content path** (``ASSET_CHARACTER``) and
    pre-declared subobject NAMES (``CameraBoom`` / ``FollowCamera``), never by
    class. Classes are consulted only where the class IS the graded property
    ("is this actually a boom", "is this actually a viewpoint"), and always as
    an ``isinstance`` so a legitimate subclass is not penalized.
  * Stock UE Python only (``EditorAssetLibrary``, the SubobjectData interface,
    reflection). Never Aura's MCP tools - that would grade Aura with Aura.
  * Every check is wrapped in its own try/except, so one wrong API name
    degrades to exactly one FAILED check with the exception in ``detail``
    instead of aborting the verdict.
  * **FAIL CLOSED.** No check may pass on the strength of "a probe did not
    raise" or "the walk came back empty". ``_gather_handles`` / ``_components``
    RAISE on an empty walk instead of returning ``[]``; every tri-state
    reflection read treats "could not be read" as NOT satisfied; the one
    NEGATIVE check (``camera_off_control_rotation``) demands a positive read of
    the value ``False`` and never credits an unreadable property.
  * The check list has a **constant length (14)** on every leg, including a
    missing asset. ``registry.py`` reports ``tests_passed/tests_run`` from
    these counts, so a constant denominator keeps the ratio comparable and
    stops a submission from improving its score by making checks unreachable.

Detail strings are stable, ASCII, greppable tokens. The discrimination MATRIX
joins on the raw ``detail`` string **as printed inside the JSON block**, not on
the layer's ``<script>:<check>: FAIL - ...`` note rendering, so each failing
check owns a unique token that never appears on its own passing branch. Every
EXCEPTION path emits a distinct ``*_READ_ERROR`` / ``*_WALK_ERROR`` /
``*_PROBE_ERROR`` / ``*_ABORTED`` token that appears in NO matrix row, so a
broken UE API name can never be credited as a variant's named failure.

No detail contains either of the two automation result markers ("TestResult" +
"=Passed", and "Automation Test" + " Succeeded") that ``parse_automation_log``'s
whole-file ``finditer`` counts as a TEST - a detail carrying one would inflate
the test tally and can flip a PASS to a FAIL through the
``expected_test_count`` guard. Neither substring appears anywhere in this file,
including this docstring.

UE 5.8 API + engine-default notes (all read out of
``<UE_ROOT>/Engine/Source``; the reflection routes are the ones the plan
the introspection-coverage plan sections 10 and 12.1 confirmed):
  * ``SubobjectDataSubsystem`` is an **ENGINE** subsystem -
    ``unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)``.
    ``get_editor_subsystem`` on it raises ``TypeError: Cannot nativize``.
  * ``USCS_Node::AttachToName`` / ``ParentComponentOrVariableName`` /
    ``UBlueprint::SimpleConstructionScript`` are bare ``UPROPERTY()`` with no
    ``CPF_Edit|CPF_BlueprintVisible|CPF_BlueprintAssignable``, so they are
    reflection-DENIED (``PropertyAccessUtil.cpp:425-433``). There is therefore
    NO read route to a component's attach SOCKET name, which is why this script
    grades the attach PARENT (``GetParentHandle``, a UFUNCTION) and never the
    ``SpringEndpoint`` socket.
  * ``AttachParent`` / ``AttachSocketName`` UPROPERTIES are likewise denied;
    the UFUNCTION getter ``USceneComponent::GetAttachParent``
    (``SceneComponent.h:700-702``) is used only as corroboration, because on an
    SCS component TEMPLATE it is null at rest.
  * ``ACharacter``'s native subobject names are ``CollisionCylinder`` (the
    capsule root) and ``CharacterMesh0`` (``Character.cpp:32,34``); the
    anchoring UPROPERTY spellings are ``CapsuleComponent`` and ``Mesh``
    (``Character.h:351,360``, both VisibleAnywhere+BlueprintReadOnly).
  * **Engine defaults matter here.** ``USpringArmComponent``'s constructor
    (``SpringArmComponent.cpp:18-46``) sets ``TargetArmLength = 300``,
    ``bUsePawnControlRotation = false``, ``CameraLagSpeed = 10`` and leaves
    ``SocketOffset`` zero and ``bEnableCameraLag`` false. ``CameraLagSpeed=10``
    is therefore the ENGINE DEFAULT and the source row's "lag speed of 10" is a
    DEAD GATE - this script requires ``EXPECTED_LAG_SPEED = 4`` instead.
    ``UCameraComponent``'s ``bUsePawnControlRotation`` is likewise ``false`` by
    default (``CameraComponent.cpp:94``), so the row's "leave the camera off
    control rotation" only grades anything because the shipped BASELINE sets it
    TRUE; see the spec's dead-gate section.
"""
import json

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax / format checks
    unreal = None

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

# --- Pre-declared identity (content PATH and subobject NAMES, never class) ---
TASK_ID = "t1-third-person-chase-camera"
ASSET_CHARACTER = "/Game/Tasks/%s/BP_Scout" % TASK_ID

BOOM_NAME = "CameraBoom"
CAMERA_NAME = "FollowCamera"

# The inherited collision body of a walking-character class, under either
# spelling: the anchoring UPROPERTY name ("CapsuleComponent") or the native
# subobject name it is constructed with ("CollisionCylinder",
# ACharacter::CapsuleComponentName). FSubobjectData::GetVariableName can return
# either depending on whether an SCS node or a native component backs it.
ROOT_BODY_NAMES = ("CapsuleComponent", "CollisionCylinder")

# --- Graded scalars (every one of these is a NON-default; see the docstring) --
EXPECTED_ARM_LENGTH = 400.0
ARM_LENGTH_TOL = 0.5
EXPECTED_SOCKET_OFFSET = (0.0, 0.0, 75.0)
SOCKET_OFFSET_TOL = 0.5
EXPECTED_LAG_SPEED = 4.0            # NOT the row's 10 - that is the engine default
LAG_SPEED_TOL = 0.01

# --- The check ids, in emission order. Length is the score denominator. ------
CHECK_IDS = (
    "character_asset_exists",
    "boom_component_exists",
    "boom_is_spring_arm",
    "boom_authored_on_this_asset",
    "boom_attached_to_character_root",
    "boom_arm_length_400",
    "boom_socket_offset_up_75",
    "boom_uses_control_rotation",
    "boom_camera_lag_enabled",
    "boom_camera_lag_speed_4",
    "camera_component_exists",
    "camera_attached_to_boom",
    "camera_off_control_rotation",
    "character_compiles_up_to_date",
)

# Emitted for every check that cannot run because the asset itself is absent.
ASSET_MISSING_TOKEN = "CHARACTER_ASSET_MISSING"
# Emitted for every boom-side check that cannot run because CameraBoom is
# absent. It is ALWAYS rendered through ``_absent``, which appends
# ``searched=<N>`` - a positive record that the subobject walk resolved N
# subobjects and read a display name for every one of them. Without that,
# a build in which the name accessors had broken printed the identical token
# with an empty list, and the empty leg's credited substring would have been
# satisfiable by an API break (see ``_components``).
BOOM_MISSING_TOKEN = "BOOM_COMPONENT_MISSING"
# Emitted for the two camera-side checks when FollowCamera is absent. Same
# rule: always through ``_absent``.
CAMERA_MISSING_TOKEN = "CAMERA_COMPONENT_MISSING"

_BOOM_DEPENDENT = (
    "boom_is_spring_arm",
    "boom_authored_on_this_asset",
    "boom_attached_to_character_root",
    "boom_arm_length_400",
    "boom_socket_offset_up_75",
    "boom_uses_control_rotation",
    "boom_camera_lag_enabled",
    "boom_camera_lag_speed_4",
)


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

    UE pythonizes UPROPERTY names and strips the leading ``b`` off bools
    (``bUsePawnControlRotation`` -> ``use_pawn_control_rotation``), while a
    Blueprint variable keeps its authored spelling. Trying every plausible
    spelling is cheaper than being wrong, and it never invents a value - if
    every spelling fails the last exception propagates and the caller records a
    ``*_READ_ERROR``.
    """
    last = None
    for name in names:
        try:
            return obj.get_editor_property(name)
        except Exception as e:  # noqa: BLE001
            last = e
    raise last if last is not None else AttributeError("no property name given")


def _read_bool(obj, *names):
    """A reflected bool as a real ``bool``; raises if no spelling reads."""
    return bool(_read_property(obj, *names))


def _read_float(obj, *names):
    return float(_read_property(obj, *names))


def _vector_xyz(value):
    """``(x, y, z)`` floats out of an ``unreal.Vector`` (or any xyz-ish value).

    Raises if the value cannot be resolved to three numbers - never guesses a
    zero, because a silently-zeroed read would make the socket-offset check
    fail for the wrong reason (or, on the reverse comparison, pass for it).
    """
    for attrs in (("x", "y", "z"), ("X", "Y", "Z")):
        if all(hasattr(value, a) for a in attrs):
            return tuple(float(getattr(value, a)) for a in attrs)
    if isinstance(value, (tuple, list)) and len(value) == 3:
        return tuple(float(v) for v in value)
    raise TypeError("not an xyz vector: %r" % (value,))


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
    walk, never a legitimate "this asset has no components". Returning ``[]``
    here would hand ``camera_off_control_rotation`` - the one NEGATIVE-shaped
    check - a free pass on an API break.
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

    FAIL-CLOSED, on THREE distinct degradations, because everything downstream
    is a NAME LOOKUP and a nameless walk is indistinguishable from an absent
    component:

      1. an empty gather (see ``_gather_handles``);
      2. a handle whose ``FSubobjectData`` will not resolve;
      3. a subobject whose DISPLAY NAME cannot be read - neither
         ``GetVariableName`` nor the object-name fallback.

    (2) and (3) used to be `continue`/`""`, and `_names_of` then filtered the
    blank out. The result was that a build in which ``get_variable_name`` and
    ``get_object`` had both broken produced ``BOOM_COMPONENT_MISSING names=[]``
    - byte-identical to the token the empty leg is CREDITED for. An API break
    would have scored as the empty submission's named failure, which is the
    silent-wrong-verdict shape this repo treats as its worst defect class. Both
    now raise a ``*_UNREADABLE`` error the matrix claims on no row.
    """
    subsystem = _subobject_subsystem()
    if subsystem is None:
        raise RuntimeError("SUBOBJECT_SUBSYSTEM_UNAVAILABLE")
    handles = _gather_handles(subsystem, blueprint)
    out = []
    unresolved = 0
    unnamed = 0
    for handle in handles:
        data = _data_for(handle)
        if data is None:
            unresolved += 1
            continue
        name = _sub_display_name(data)
        if not name:
            unnamed += 1
            continue
        out.append((name, data))
    if unresolved or unnamed:
        raise RuntimeError(
            "SUBOBJECT_NAMES_UNREADABLE unresolved=%d unnamed=%d named=%d of=%d"
            % (unresolved, unnamed, len(out), len(handles)))
    if not out:
        raise RuntimeError("SUBOBJECT_WALK_EMPTY")
    return out


def _names_of(components):
    return sorted(n for n, _ in components if n)


def _absent(token, components, names, wanted):
    """The detail for "this pre-declared component is not on the asset".

    ``searched=`` is load-bearing, not decoration: it is a POSITIVE record that
    the walk resolved N subobjects and read a name for every one of them, which
    is exactly what ``_components`` now refuses to continue without. Together
    they make this token mean one thing only - "the walk worked and the
    component is not there" - so the empty leg's credited substring cannot be
    manufactured by a degraded read.
    """
    return "%s searched=%d names=%s wanted=%s" % (
        token, len(components), names, wanted)


def _find_component(components, name):
    for got, data in components:
        if got == name:
            return data
    return None


def _parent_data(data):
    """The FSubobjectData of a subobject's ATTACH PARENT, or None.

    FAIL-CLOSED: a handle whose validity cannot be established is treated as
    invalid rather than walked unvalidated.
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


def _isinstance_tristate(obj, type_name):
    """``isinstance(obj, unreal.<type_name>)`` as True / False / None.

    ``None`` means "the type is not exposed / the probe could not be
    evaluated"; every caller treats that as NOT satisfied (fail-closed) but
    reports it under a distinct ``*_TYPE_PROBE_ERROR`` token, never under the
    graded semantic failure token - a broken probe is a harness event, not
    evidence about the submission. This never returns True because an
    exception did not happen.
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


def _compile_status(blueprint):
    """A string for the Blueprint's compile status, e.g. 'BlueprintStatus.BS_UP_TO_DATE'."""
    return str(_read_property(blueprint, "status", "Status"))


# --------------------------------------------------------------------------- #
# the two attachment reports                                                   #
# --------------------------------------------------------------------------- #

def _boom_attach_report(boom_data):
    """``(ok, report)`` for "CameraBoom hangs off the character's own body".

    A NAME MATCH IS NOT ENOUGH - a submission can call any scene component
    ``CapsuleComponent``. Three INDEPENDENT positive facts must all hold, and
    any read that raises or comes back unknown makes the check FAIL:

      1. the SubobjectData parent handle resolves to a subobject named one of
         ``ROOT_BODY_NAMES``. This is the authoritative structural parent for a
         Blueprint: an SCS component TEMPLATE's own ``AttachParent`` pointer is
         null at rest, the hierarchy lives in the SCS node graph.
      2. that parent's component template really IS a capsule collision body -
         a ``SceneComponent`` renamed ``CollisionCylinder`` dies here.
      3. that parent is INHERITED or NATIVE, i.e. it is the walking-character
         base's own body rather than something this submission authored.
         ``IsInheritedComponent`` / ``IsNativeComponent`` are both
         ``BlueprintCallable`` (``SubobjectDataBlueprintFunctionLibrary.h:113-117``).

    ``IsRootComponent`` is recorded as a corroboration and gates only when it
    reads back, so an accessor missing from a future build cannot manufacture a
    failure on a correct submission.
    """
    parent = _parent_data(boom_data)
    if parent is None:
        return False, "parent=<none> reason=no_resolvable_parent_handle"

    parent_name = _sub_display_name(parent)
    name_ok = parent_name in ROOT_BODY_NAMES

    parent_obj = _sub_object(parent)
    capsule_ok = _isinstance_tristate(parent_obj, "CapsuleComponent")
    if capsule_ok is None:
        return None, ("TYPE_PROBE_ERROR type=CapsuleComponent parent=%s "
                      "parent_class=%s"
                      % (parent_name or "<none>", _class_name(parent_obj)))

    inherited = _bp_lib_tristate("is_inherited_component", parent)
    native = _bp_lib_tristate("is_native_component", parent)
    inherited_ok = (inherited is True) or (native is True)

    # Corroboration - the parent should also be the actor's root component.
    is_root = _bp_lib_tristate("is_root_component", parent)
    root_ok = True if is_root is None else bool(is_root)

    ok = bool(name_ok and capsule_ok and inherited_ok and root_ok)
    report = ("parent=%s parent_class=%s name_ok=%s capsule=%s inherited=%s "
              "native=%s is_root=%s expected_one_of=%s"
              % (parent_name or "<none>", _class_name(parent_obj), name_ok,
                 capsule_ok, inherited, native, is_root, list(ROOT_BODY_NAMES)))
    return ok, report


def _camera_attach_report(camera_data, boom_data):
    """``(ok, report)`` for "FollowCamera rides on CameraBoom".

    Positive facts, all required:

      1. the camera's parent subobject is NAMED ``CameraBoom``;
      2. that parent's template really IS a boom (``SpringArmComponent`` or a
         subclass) - a scene component merely named ``CameraBoom`` dies here;
      3. when the boom subobject was itself resolved by the caller, the parent
         must be the SAME object (compared by path name, so no binding equality
         semantics are assumed). This gates only when both path reads succeed,
         and it is what stops a second, decoy component named ``CameraBoom``
         from satisfying the check.

    The ``GetAttachParent`` UFUNCTION (``SceneComponent.h:700-702``) is read as
    a further corroboration and gates only when it returns something; on an SCS
    component template it is normally null.
    """
    parent = _parent_data(camera_data)
    if parent is None:
        return False, "parent=<none> reason=no_resolvable_parent_handle"

    parent_name = _sub_display_name(parent)
    name_ok = parent_name == BOOM_NAME

    parent_obj = _sub_object(parent)
    boom_type_ok = _isinstance_tristate(parent_obj, "SpringArmComponent")
    if boom_type_ok is None:
        return None, ("TYPE_PROBE_ERROR type=SpringArmComponent parent=%s "
                      "parent_class=%s"
                      % (parent_name or "<none>", _class_name(parent_obj)))

    identity = "unknown"
    identity_ok = True
    boom_obj = _sub_object(boom_data) if boom_data is not None else None
    boom_path, parent_path = _path_name(boom_obj), _path_name(parent_obj)
    if boom_path and parent_path:
        identity_ok = boom_path == parent_path
        identity = "same" if identity_ok else "different"

    attach_getter = "<null>"
    attach_ok = True
    camera_obj = _sub_object(camera_data)
    getter = getattr(camera_obj, "get_attach_parent", None) if camera_obj else None
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
                attach_ok = attach_getter == BOOM_NAME

    ok = bool(name_ok and boom_type_ok and identity_ok and attach_ok)
    report = ("parent=%s parent_class=%s name_ok=%s boom_type=%s boom_identity=%s "
              "attach_getter=%s expected=%s"
              % (parent_name or "<none>", _class_name(parent_obj), name_ok,
                 boom_type_ok, identity, attach_getter, BOOM_NAME))
    return ok, report


# --------------------------------------------------------------------------- #
# the checks                                                                   #
# --------------------------------------------------------------------------- #

def _boom_property_checks(results, boom_obj):
    """The five numeric/boolean boom settings, each independently wrapped.

    Every one of these is asserted against a value that is NOT the engine
    default (``SpringArmComponent.cpp:18-46``), so none of them can be passed
    by an untouched, freshly added boom.
    """
    # Arm length: engine default 300.
    try:
        value = _read_float(boom_obj, "target_arm_length", "TargetArmLength")
        ok = abs(value - EXPECTED_ARM_LENGTH) <= ARM_LENGTH_TOL
        results["boom_arm_length_400"] = check(
            "boom_arm_length_400", ok,
            ("BOOM_ARM_LENGTH_OK value=%s" % value) if ok
            else ("BOOM_ARM_LENGTH_WRONG value=%s expected=%s"
                  % (value, EXPECTED_ARM_LENGTH)))
    except Exception as e:  # noqa: BLE001
        results["boom_arm_length_400"] = check(
            "boom_arm_length_400", False,
            "BOOM_ARM_LENGTH_READ_ERROR raised %r" % (e,))

    # Socket offset: engine default (0,0,0). The far END of the boom is raised,
    # so this is SocketOffset, not TargetOffset - TargetOffset is recorded in
    # the detail so a submission that confused the two is diagnosable.
    try:
        raw = _read_property(boom_obj, "socket_offset", "SocketOffset")
        got = _vector_xyz(raw)
        try:
            other = _vector_xyz(_read_property(boom_obj, "target_offset",
                                               "TargetOffset"))
        except Exception:  # noqa: BLE001 - diagnostic only
            other = "unreadable"
        ok = all(abs(g - e) <= SOCKET_OFFSET_TOL
                 for g, e in zip(got, EXPECTED_SOCKET_OFFSET))
        results["boom_socket_offset_up_75"] = check(
            "boom_socket_offset_up_75", ok,
            ("BOOM_SOCKET_OFFSET_OK value=%s" % (got,)) if ok
            else ("BOOM_SOCKET_OFFSET_WRONG value=%s expected=%s target_offset=%s"
                  % (got, EXPECTED_SOCKET_OFFSET, other)))
    except Exception as e:  # noqa: BLE001
        results["boom_socket_offset_up_75"] = check(
            "boom_socket_offset_up_75", False,
            "BOOM_SOCKET_OFFSET_READ_ERROR raised %r" % (e,))

    # Driven by the player's look: engine default False.
    try:
        value = _read_bool(boom_obj, "use_pawn_control_rotation",
                           "b_use_pawn_control_rotation", "bUsePawnControlRotation")
        results["boom_uses_control_rotation"] = check(
            "boom_uses_control_rotation", value,
            ("BOOM_CONTROL_ROTATION_OK value=%s" % value) if value
            else ("BOOM_NOT_ON_CONTROL_ROTATION value=%s expected=True" % value))
    except Exception as e:  # noqa: BLE001
        results["boom_uses_control_rotation"] = check(
            "boom_uses_control_rotation", False,
            "BOOM_CONTROL_ROTATION_READ_ERROR raised %r" % (e,))

    # Trailing smoothing on: engine default False.
    try:
        value = _read_bool(boom_obj, "enable_camera_lag", "b_enable_camera_lag",
                           "bEnableCameraLag")
        results["boom_camera_lag_enabled"] = check(
            "boom_camera_lag_enabled", value,
            ("BOOM_CAMERA_LAG_OK value=%s" % value) if value
            else ("BOOM_CAMERA_LAG_DISABLED value=%s expected=True" % value))
    except Exception as e:  # noqa: BLE001
        results["boom_camera_lag_enabled"] = check(
            "boom_camera_lag_enabled", False,
            "BOOM_CAMERA_LAG_READ_ERROR raised %r" % (e,))

    # Catch-up rate: engine default 10 - which is exactly what the source row
    # asked for, and why this task asks for something else instead.
    try:
        value = _read_float(boom_obj, "camera_lag_speed", "CameraLagSpeed")
        ok = abs(value - EXPECTED_LAG_SPEED) <= LAG_SPEED_TOL
        results["boom_camera_lag_speed_4"] = check(
            "boom_camera_lag_speed_4", ok,
            ("BOOM_LAG_SPEED_OK value=%s" % value) if ok
            else ("BOOM_LAG_SPEED_WRONG value=%s expected=%s"
                  % (value, EXPECTED_LAG_SPEED)))
    except Exception as e:  # noqa: BLE001
        results["boom_camera_lag_speed_4"] = check(
            "boom_camera_lag_speed_4", False,
            "BOOM_LAG_SPEED_READ_ERROR raised %r" % (e,))


def _character_checks(results):
    """Fill ``results`` (a dict keyed by check id) for every check."""
    # A raised probe is NOT the same event as a genuinely absent asset, and the
    # two must not share a token: an API break that fanned out
    # CHARACTER_ASSET_MISSING would be credited as a variant's named failure.
    root_cause = None
    try:
        exists = _asset_exists(ASSET_CHARACTER)
    except Exception as e:  # noqa: BLE001
        root_cause = "CHARACTER_ASSET_PROBE_ERROR %s raised %r" % (ASSET_CHARACTER, e)
        results["character_asset_exists"] = check(
            "character_asset_exists", False, root_cause)
        exists = False
    else:
        if exists:
            results["character_asset_exists"] = check(
                "character_asset_exists", True,
                "CHARACTER_ASSET_OK %s %s"
                % (ASSET_CHARACTER, _parent_tags(ASSET_CHARACTER)))
        else:
            root_cause = "%s %s" % (ASSET_MISSING_TOKEN, ASSET_CHARACTER)
            results["character_asset_exists"] = check(
                "character_asset_exists", False, root_cause)

    if not exists:
        # Constant denominator: every remaining check still reports, as a
        # failure whose detail names the single root cause.
        for cid in CHECK_IDS:
            if cid not in results:
                results[cid] = check(cid, False, root_cause)
        return

    # --- subobject walk (shared by ten checks) -------------------------------
    components = []
    walk_error = None
    try:
        blueprint = unreal.EditorAssetLibrary.load_asset(ASSET_CHARACTER)
        components = _components(blueprint)
    except Exception as e:  # noqa: BLE001
        walk_error = repr(e)
    names = _names_of(components)

    # --- the boom exists -----------------------------------------------------
    boom = None
    if walk_error is not None:
        results["boom_component_exists"] = check(
            "boom_component_exists", False,
            "BOOM_WALK_ERROR raised %s" % walk_error)
    else:
        boom = _find_component(components, BOOM_NAME)
        results["boom_component_exists"] = check(
            "boom_component_exists", boom is not None,
            ("BOOM_COMPONENT_OK names=%s" % names) if boom is not None
            else _absent(BOOM_MISSING_TOKEN, components, names, BOOM_NAME))

    if boom is None:
        # A broken walk and a genuinely absent boom are different events and
        # must not share a token.
        fanout = ("BOOM_WALK_ERROR raised %s" % walk_error
                  if walk_error is not None
                  else _absent(BOOM_MISSING_TOKEN, components, names, BOOM_NAME))
        for cid in _BOOM_DEPENDENT:
            results[cid] = check(cid, False, fanout)
    else:
        boom_obj = _sub_object(boom)

        # It really is a boom, not a bare scene component wearing the name.
        try:
            tri = _isinstance_tristate(boom_obj, "SpringArmComponent")
            if tri is None:
                results["boom_is_spring_arm"] = check(
                    "boom_is_spring_arm", False,
                    "BOOM_TYPE_PROBE_ERROR type=SpringArmComponent class=%s"
                    % _class_name(boom_obj))
            else:
                results["boom_is_spring_arm"] = check(
                    "boom_is_spring_arm", tri,
                    ("BOOM_SPRING_ARM_OK class=%s" % _class_name(boom_obj))
                    if tri
                    else ("BOOM_NOT_SPRING_ARM class=%s"
                          % _class_name(boom_obj)))
        except Exception as e:  # noqa: BLE001
            results["boom_is_spring_arm"] = check(
                "boom_is_spring_arm", False,
                "BOOM_TYPE_PROBE_ERROR raised %r" % (e,))

        # It was ADDED to this asset, not inherited from a base that already
        # ships a chase rig (the substrate has exactly such a base).
        try:
            inherited = _bp_lib_tristate("is_inherited_component", boom)
            native = _bp_lib_tristate("is_native_component", boom)
            if inherited is None or native is None:
                # FAIL-CLOSED, and with a DISTINCT token: an unreadable
                # authorship probe is an error event, never the graded
                # "you inherited the rig" failure.
                results["boom_authored_on_this_asset"] = check(
                    "boom_authored_on_this_asset", False,
                    "BOOM_AUTHORSHIP_READ_ERROR inherited=%s native=%s"
                    % (inherited, native))
            else:
                ok = (not inherited) and (not native)
                results["boom_authored_on_this_asset"] = check(
                    "boom_authored_on_this_asset", ok,
                    ("BOOM_AUTHORED_OK inherited=%s native=%s %s"
                     % (inherited, native, _parent_tags(ASSET_CHARACTER))) if ok
                    else ("BOOM_NOT_AUTHORED_ON_ASSET inherited=%s native=%s %s"
                          % (inherited, native, _parent_tags(ASSET_CHARACTER))))
        except Exception as e:  # noqa: BLE001
            results["boom_authored_on_this_asset"] = check(
                "boom_authored_on_this_asset", False,
                "BOOM_AUTHORSHIP_READ_ERROR raised %r" % (e,))

        # It hangs off the character's own collision body.
        try:
            ok, report = _boom_attach_report(boom)
            if ok is None:
                # A type probe that could not be evaluated is a harness event,
                # never the graded "attached to the wrong parent" failure.
                results["boom_attached_to_character_root"] = check(
                    "boom_attached_to_character_root", False,
                    "BOOM_ATTACH_TYPE_PROBE_ERROR %s" % report)
            else:
                results["boom_attached_to_character_root"] = check(
                    "boom_attached_to_character_root", bool(ok),
                    ("BOOM_ATTACH_PARENT_OK %s" % report) if ok
                    else ("BOOM_ATTACH_PARENT_WRONG %s" % report))
        except Exception as e:  # noqa: BLE001
            results["boom_attached_to_character_root"] = check(
                "boom_attached_to_character_root", False,
                "BOOM_ATTACH_READ_ERROR raised %r" % (e,))

        _boom_property_checks(results, boom_obj)

    # --- the camera ----------------------------------------------------------
    # camera_fail carries the root cause forward to the dependent checks, so
    # "missing", "wrong type" and "unevaluable type probe" never share a token.
    camera = None
    camera_fail = None
    if walk_error is not None:
        camera_fail = "CAMERA_WALK_ERROR raised %s" % walk_error
        results["camera_component_exists"] = check(
            "camera_component_exists", False, camera_fail)
    else:
        candidate = _find_component(components, CAMERA_NAME)
        if candidate is None:
            camera_fail = _absent(CAMERA_MISSING_TOKEN, components, names,
                                  CAMERA_NAME)
            results["camera_component_exists"] = check(
                "camera_component_exists", False, camera_fail)
        else:
            tri = _isinstance_tristate(_sub_object(candidate),
                                       "CameraComponent")
            if tri is None:
                camera_fail = ("CAMERA_TYPE_PROBE_ERROR type=CameraComponent "
                               "class=%s" % _class_name(_sub_object(candidate)))
                results["camera_component_exists"] = check(
                    "camera_component_exists", False, camera_fail)
            elif tri:
                camera = candidate
                results["camera_component_exists"] = check(
                    "camera_component_exists", True,
                    "CAMERA_COMPONENT_OK class=%s"
                    % _class_name(_sub_object(candidate)))
            else:
                camera_fail = ("CAMERA_NOT_A_VIEWPOINT class=%s"
                               % _class_name(_sub_object(candidate)))
                results["camera_component_exists"] = check(
                    "camera_component_exists", False, camera_fail)

    if camera is None:
        for cid in ("camera_attached_to_boom", "camera_off_control_rotation"):
            results[cid] = check(cid, False, camera_fail)
    else:
        try:
            ok, report = _camera_attach_report(camera, boom)
            if ok is None:
                results["camera_attached_to_boom"] = check(
                    "camera_attached_to_boom", False,
                    "CAMERA_ATTACH_TYPE_PROBE_ERROR %s" % report)
            else:
                results["camera_attached_to_boom"] = check(
                    "camera_attached_to_boom", bool(ok),
                    ("CAMERA_ATTACH_PARENT_OK %s" % report) if ok
                    else ("CAMERA_ATTACH_PARENT_WRONG %s" % report))
        except Exception as e:  # noqa: BLE001
            results["camera_attached_to_boom"] = check(
                "camera_attached_to_boom", False,
                "CAMERA_ATTACH_READ_ERROR raised %r" % (e,))

        # The NEGATIVE-shaped check. FAIL-CLOSED: it demands a positive read of
        # the value False; an unreadable property is an error, never "off".
        try:
            camera_obj = _sub_object(camera)
            value = _read_bool(camera_obj, "use_pawn_control_rotation",
                               "b_use_pawn_control_rotation",
                               "bUsePawnControlRotation")
            results["camera_off_control_rotation"] = check(
                "camera_off_control_rotation", not value,
                ("CAMERA_CONTROL_ROTATION_OK value=%s" % value) if not value
                else ("CAMERA_STILL_ON_CONTROL_ROTATION value=%s expected=False"
                      % value))
        except Exception as e:  # noqa: BLE001
            results["camera_off_control_rotation"] = check(
                "camera_off_control_rotation", False,
                "CAMERA_CONTROL_ROTATION_READ_ERROR raised %r" % (e,))

    # --- compile status ------------------------------------------------------
    try:
        blueprint = unreal.EditorAssetLibrary.load_asset(ASSET_CHARACTER)
        status = _compile_status(blueprint)
        ok = "UP_TO_DATE" in status.upper()
        results["character_compiles_up_to_date"] = check(
            "character_compiles_up_to_date", ok,
            ("CHARACTER_COMPILE_OK status=%s" % status) if ok
            else ("CHARACTER_NOT_UP_TO_DATE status=%s" % status))
    except Exception as e:  # noqa: BLE001
        results["character_compiles_up_to_date"] = check(
            "character_compiles_up_to_date", False,
            "CHARACTER_COMPILE_READ_ERROR raised %r" % (e,))


def main():
    results = {}
    try:
        _character_checks(results)
    except Exception as e:  # noqa: BLE001 - never abort the verdict
        for cid in CHECK_IDS:
            if cid not in results:
                results[cid] = check(cid, False, "INTROSPECTION_ABORTED %r" % (e,))

    # Constant-length, deterministically ordered verdict.
    checks = [results.get(cid) or check(cid, False, "CHECK_NOT_EVALUATED %s" % cid)
              for cid in CHECK_IDS]
    emit_verdict(checks)


if __name__ == "__main__":
    main()
