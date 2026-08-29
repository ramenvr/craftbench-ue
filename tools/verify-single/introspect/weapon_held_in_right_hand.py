"""L2-introspect script for the t2-weapon-held-in-right-hand task.

Structural, READ-ONLY verification of a duplicated mannequin rig + a character
Blueprint via stock UE editor-Python. Emits one CRAFTBENCH-INTROSPECT-JSON
block the L2-introspect layer parses (``layers/l2_introspect.py``; contract:
``layers/INTROSPECT_CONTRACT.md``).

What is graded (seed roster R6, re-pathed and re-tiered; see the task spec):
the task-local skeletal mesh must carry an attachment point named
``WeaponSocket`` anchored to bone ``hand_r`` with an identity offset; the
character Blueprint ``BP_EvalChar`` must own a static-mesh subobject named
``Weapon`` showing ``/Engine/BasicShapes/Cube``; and that subobject must hang
off the INHERITED animated mesh **at that named attachment point**.

Hard rules honoured here:
  * READ-ONLY with respect to every ASSET and PACKAGE. Nothing below saves,
    renames, or mutates a ``.uasset``. The single exception is documented in
    ``_attach_socket_check``: check 9 constructs one TRANSIENT actor in the
    already-live editor world and destroys it in a ``finally``. That world is
    never saved by the verifier, and the construction is the ONLY route to the
    graded fact (see "Why check 9 needs a world" below).
  * Identity by **pre-declared content path** (``ASSET_MESH`` / ``ASSET_CHAR``)
    and pre-declared NAMES (``WeaponSocket`` / ``hand_r`` / ``Weapon``), never
    by class. The one place a class is consulted is an assertion itself
    ("is this subobject a static-mesh part", "is its parent an animated mesh"),
    written as ``isinstance`` so a legitimate subclass is not penalized.
  * Stock UE Python only (``EditorAssetLibrary``, the SubobjectData interface,
    the EditorActorSubsystem, reflection). Never Aura's MCP tools - that would
    grade Aura with Aura.
  * Every check is wrapped in its own try/except, so one wrong API name
    degrades to exactly one FAILED check with the exception in ``detail``
    instead of aborting the verdict.
  * **FAIL CLOSED.** No check may pass on the strength of "a probe did not
    raise" or "the walk came back empty". ``_gather_handles`` RAISES on an
    empty gather; a socket object that cannot be read is a failure, never an
    "unchanged"; a spawn that does not happen fails check 9 rather than
    skipping it.
  * The check list has a **constant length (10)** on every leg, including a
    missing ``BP_EvalChar``. ``registry.py`` reports ``tests_passed/tests_run``
    from these counts, so a constant denominator keeps the ratio comparable and
    stops a submission from improving its score by making checks unreachable.

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

UE 5.8 API notes (answered from engine source at ``<UE_ROOT>/Engine/Source``;
the reflection-visibility rule is ``PropertyAccessUtil.cpp:425-433`` -
CPF_Edit | CPF_BlueprintVisible | CPF_BlueprintAssignable):
  * ``USkinnedAsset::FindSocket`` is a ``UFUNCTION(BlueprintCallable)``
    (``SkinnedAsset.h:156-159``); ``USkeletalMesh`` overrides it
    (``SkeletalMesh.h:2658``) and ``USkeletalMesh::FindSocketAndIndex``
    searches the MESH's own sockets first and then falls through to the
    skeleton's (``SkeletalMesh.cpp:5238-5266``). So one call accepts a socket
    authored on either asset - which is what the prompt asks for and what an
    editor "Add Socket" flow actually produces.
  * ``USkeletalMeshSocket::SocketName`` / ``BoneName`` are
    ``VisibleAnywhere + BlueprintReadOnly`` and ``RelativeLocation`` /
    ``RelativeRotation`` are ``EditAnywhere + BlueprintReadOnly``
    (``SkeletalMeshSocket.h:24-38``) - all four are reflection-readable.
    ``USkeleton::Sockets`` carries NO flag at all and is unreadable; this
    script never touches it.
  * **Do NOT use ``DoesSocketExist``.** ``USkinnedMeshComponent::DoesSocketExist``
    delegates to ``GetSocketBoneName``, which falls back to a BONE lookup when
    no socket matches (``SkinnedMeshComponent.cpp:3709-3739``). It therefore
    returns True for ``hand_r`` on a mesh with ZERO sockets authored. That is
    the grading hole anti-gaming note #1 is written against; ``FindSocket``
    has no such fallback.
  * ``SubobjectDataSubsystem`` is an **ENGINE** subsystem -
    ``unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)``.
    ``get_editor_subsystem`` on it raises ``TypeError: Cannot nativize``.
  * ``UStaticMeshComponent::StaticMesh`` is ``EditAnywhere + BlueprintReadOnly``
    (``StaticMeshComponent.h:132``) -> readable. ``USkeletalMeshComponent``'s
    mesh is read through the ``GetSkeletalMeshAsset`` / ``GetSkinnedAsset``
    BlueprintPure UFUNCTIONs (``SkeletalMeshComponent.h:374``,
    ``SkinnedMeshComponent.h:1222``).
  * ``USceneComponent::AttachParent`` and ``AttachSocketName`` are
    ``UPROPERTY(ReplicatedUsing=...)`` with no Edit/BlueprintVisible flag
    (``SceneComponent.h:107-113``) -> reflection-DENIED. The UFUNCTION getters
    ``GetAttachParent`` / ``GetAttachSocketName`` (``SceneComponent.h:699-705``)
    are the supported route.

Why check 9 needs a world
-------------------------
For an SCS-authored component the attachment SOCKET is stored on the SCS node
(``USCS_Node::AttachToName``), and it is unreachable from Python at three
independent levels:
  1. ``USCS_Node::AttachToName`` is a bare ``UPROPERTY()`` (``SCS_Node.h:43``)
     - no Edit/BlueprintVisible flag, so reflection denies it.
  2. ``UBlueprint::SimpleConstructionScript`` is also a bare ``UPROPERTY()``
     (``Blueprint.h:537``), so the SCS node graph cannot even be reached.
  3. ``FSubobjectData::GetSocketFName()`` exists (``SubobjectData.h:181``) but
     has **no** wrapper in ``USubobjectDataBlueprintFunctionLibrary`` - it is
     not a UFUNCTION and is invisible to Python.
And the component TEMPLATE is no help: ``FSubobjectData::SetupAttachment``
explicitly writes ``NAME_None`` into the template's ``AttachSocketName``
(``SubobjectData.cpp:672-692``). The value only materializes when
``USCS_Node::ExecuteNodeOnActor`` runs ``AttachToComponent(parent, rules,
AttachToName)`` on a CONSTRUCTED actor. Hence the transient spawn.
A live editor world is guaranteed for this script: ``EditorPythonExecuter.cpp``
refuses to start an ``-ExecutePythonScript`` payload until ``GWorld``,
``GEngine`` and ``GEditor`` are up and the asset registry has finished.
"""
import json

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax / format checks
    unreal = None

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

# --- Pre-declared identity (content PATHS and NAMES, never class) ------------
TASK_ID = "t2-weapon-held-in-right-hand"
ASSET_MESH = "/Game/Tasks/%s/SKM_EvalChar" % TASK_ID
ASSET_CHAR = "/Game/Tasks/%s/BP_EvalChar" % TASK_ID

SOCKET_NAME = "WeaponSocket"
SOCKET_BONE = "hand_r"
WEAPON_NAME = "Weapon"
CUBE_PATH = "/Engine/BasicShapes/Cube"

# The inherited animated body part, under either spelling: the anchoring
# UPROPERTY name on the walking-character class ("Mesh") or the native
# subobject name it is constructed with ("CharacterMesh0").
# FSubobjectData::GetVariableName can return either depending on whether an SCS
# node or a native component backs the subobject.
INHERITED_MESH_NAMES = ("Mesh", "CharacterMesh0")

# --- Graded tolerances -------------------------------------------------------
OFFSET_TOL = 1e-3

# --- The check ids, in emission order. Length is the score denominator. ------
CHECK_IDS = (
    "weapon_socket_exists",
    "weapon_socket_on_hand_r",
    "weapon_socket_offset_is_identity",
    "char_mesh_uses_task_skeletal_mesh",
    "char_has_weapon_component",
    "weapon_is_static_mesh_component",
    "weapon_shows_engine_cube",
    "weapon_attach_parent_is_character_mesh",
    "weapon_attach_socket_is_weapon_socket",
    "char_bp_compiles_up_to_date",
)

SOCKET_CHECK_IDS = (
    "weapon_socket_exists",
    "weapon_socket_on_hand_r",
    "weapon_socket_offset_is_identity",
)
CHAR_CHECK_IDS = tuple(c for c in CHECK_IDS if c not in SOCKET_CHECK_IDS)


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

    UE pythonizes UPROPERTY names (``BoneName`` -> ``bone_name``) while a few
    surfaces keep the authored spelling. Trying both is cheaper than being
    wrong, and it never invents a value - if every spelling fails the last
    exception propagates and the caller records a ``*_READ_ERROR``.
    """
    last = None
    for name in names:
        try:
            return obj.get_editor_property(name)
        except Exception as e:  # noqa: BLE001
            last = e
    raise last if last is not None else AttributeError("no property name given")


def _call_first(obj, *names):
    """Call the first present zero-arg UFUNCTION; raise if none is callable."""
    last = None
    for name in names:
        fn = getattr(obj, name, None)
        if fn is None:
            continue
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
    raise last if last is not None else AttributeError(
        "none of %s on %r" % (list(names), obj))


def _path_name(obj):
    if obj is None:
        return "None"
    try:
        return str(obj.get_path_name())
    except Exception:  # noqa: BLE001
        return "<unreadable>"


def _class_name(obj):
    if obj is None:
        return "None"
    try:
        return str(obj.get_class().get_name())
    except Exception:  # noqa: BLE001
        return "<unreadable>"


def _triple(value):
    """(a, b, c) out of an FVector (x/y/z) or an FRotator (pitch/yaw/roll).

    FAIL-CLOSED: raises when neither shape reads, so an unreadable transform is
    never scored as "identity".
    """
    for attrs in (("x", "y", "z"), ("roll", "pitch", "yaw")):
        try:
            return tuple(float(getattr(value, a)) for a in attrs)
        except Exception:  # noqa: BLE001
            continue
    raise TypeError("not a readable 3-tuple: %r" % (value,))


def _is_identity(triple):
    return all(abs(c) <= OFFSET_TOL for c in triple)


# --- subobject walk (shared with the pilot's proven shape) ------------------ #

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
    here would hand ``char_has_weapon_component`` a wrong-reason failure and,
    worse, would let a future negative check pass for free.
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

    ``get_object`` is the route proven live on 5.8; ``get_associated_object``
    is its non-deprecated replacement and is tried second.
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

    FAIL-CLOSED: raises rather than returning an empty walk.
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
    """``isinstance`` against ``unreal.<type_name>`` as True / False / None.

    ``None`` means "the type is not exposed / the probe could not be
    evaluated"; every caller treats that as NOT satisfied (fail-closed) but
    reports it under a distinct ``*_TYPE_PROBE_ERROR`` token, never under the
    graded semantic failure token - a broken probe is a harness event, not
    evidence about the submission.
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


# --------------------------------------------------------------------------- #
# the socket checks (static: no world, no spawn)                               #
# --------------------------------------------------------------------------- #

def _socket_checks(results):
    """Fill ``results`` for the three attachment-point checks.

    Read route: ``USkeletalMesh::FindSocket`` - a UFUNCTION inherited from
    ``USkinnedAsset`` that searches the mesh's own sockets and then the
    skeleton's, so a socket authored on EITHER asset is accepted. Deliberately
    NOT ``DoesSocketExist``, which falls back to a bone lookup and would return
    True with zero sockets authored (anti-gaming note #1).
    """
    root_cause = None
    mesh = None
    try:
        if not _asset_exists(ASSET_MESH):
            root_cause = "TASK_MESH_ASSET_MISSING %s" % ASSET_MESH
        else:
            mesh = unreal.EditorAssetLibrary.load_asset(ASSET_MESH)
            if mesh is None:
                root_cause = "TASK_MESH_LOAD_FAILED %s" % ASSET_MESH
    except Exception as e:  # noqa: BLE001
        root_cause = "TASK_MESH_PROBE_ERROR %s raised %r" % (ASSET_MESH, e)

    socket = None
    if root_cause is None:
        try:
            socket = mesh.find_socket(SOCKET_NAME)
        except Exception as e:  # noqa: BLE001
            root_cause = "WEAPONSOCKET_FIND_ERROR %s raised %r" % (ASSET_MESH, e)

    if root_cause is None and socket is None:
        # The graded failure: the attachment point was never authored.
        root_cause = "WEAPONSOCKET_NOT_FOUND %s socket=%s" % (ASSET_MESH, SOCKET_NAME)

    if root_cause is not None:
        for cid in SOCKET_CHECK_IDS:
            results[cid] = check(cid, False, root_cause)
        return

    results["weapon_socket_exists"] = check(
        "weapon_socket_exists", True,
        "WEAPONSOCKET_OK %s socket=%s owner=%s"
        % (ASSET_MESH, SOCKET_NAME, _path_name(socket)))

    # Anchored to the right-hand bone.
    try:
        bone = str(_read_property(socket, "bone_name", "BoneName"))
        ok = bone == SOCKET_BONE
        results["weapon_socket_on_hand_r"] = check(
            "weapon_socket_on_hand_r", ok,
            ("WEAPONSOCKET_BONE_OK bone=%s" % bone) if ok
            else ("WEAPONSOCKET_BONE_WRONG bone=%s expected=%s"
                  % (bone, SOCKET_BONE)))
    except Exception as e:  # noqa: BLE001
        results["weapon_socket_on_hand_r"] = check(
            "weapon_socket_on_hand_r", False,
            "WEAPONSOCKET_BONE_READ_ERROR raised %r" % (e,))

    # Sitting exactly on the bone: no positional and no angular offset.
    try:
        loc = _triple(_read_property(socket, "relative_location", "RelativeLocation"))
        rot = _triple(_read_property(socket, "relative_rotation", "RelativeRotation"))
        ok = _is_identity(loc) and _is_identity(rot)
        results["weapon_socket_offset_is_identity"] = check(
            "weapon_socket_offset_is_identity", ok,
            ("WEAPONSOCKET_OFFSET_OK loc=%s rot=%s" % (list(loc), list(rot))) if ok
            else ("WEAPONSOCKET_OFFSET_NOT_IDENTITY loc=%s rot=%s tol=%s"
                  % (list(loc), list(rot), OFFSET_TOL)))
    except Exception as e:  # noqa: BLE001
        results["weapon_socket_offset_is_identity"] = check(
            "weapon_socket_offset_is_identity", False,
            "WEAPONSOCKET_OFFSET_READ_ERROR raised %r" % (e,))


# --------------------------------------------------------------------------- #
# the character-Blueprint checks                                               #
# --------------------------------------------------------------------------- #

def _attach_parent_report(weapon_data):
    """``(ok, report)`` for "Weapon hangs off the INHERITED animated mesh".

    A NAME MATCH IS NOT ENOUGH. Anti-gaming note #3 is defeated by any
    component the agent merely *names* ``Mesh``, so three INDEPENDENT positive
    facts must all hold, and any read that raises or comes back unknown makes
    the check FAIL:

      1. the SubobjectData parent handle resolves to a subobject whose name is
         one of ``INHERITED_MESH_NAMES``. This is the authoritative structural
         parent for a Blueprint: an SCS component TEMPLATE's own
         ``AttachParent`` pointer is null at rest, the hierarchy lives in the
         SCS node graph.
      2. that parent's component template really IS a skeletal (animated) mesh
         component - a ``StaticMeshComponent`` called ``Mesh`` dies here.
      3. that parent is INHERITED or NATIVE, not authored by this submission.
         ``FSubobjectData::IsInheritedComponent`` / ``IsNativeComponent`` are
         both ``BlueprintCallable``
         (``SubobjectDataBlueprintFunctionLibrary.h``), and for the Character's
         native ``CharacterMesh0`` both are true. A component the agent added
         to ``BP_EvalChar``'s own SCS is neither, whatever it is called.
    """
    parent = _parent_data(weapon_data)
    if parent is None:
        return False, "parent=<none> reason=no_resolvable_parent_handle"

    parent_name = _sub_display_name(parent)
    name_ok = parent_name in INHERITED_MESH_NAMES

    parent_obj = _sub_object(parent)
    skeletal_ok = _isinstance_tristate(parent_obj, "SkeletalMeshComponent")
    if skeletal_ok is None:
        return None, ("TYPE_PROBE_ERROR type=SkeletalMeshComponent parent=%s "
                      "parent_class=%s"
                      % (parent_name or "<none>", _class_name(parent_obj)))

    inherited = _bp_lib_tristate("is_inherited_component", parent)
    native = _bp_lib_tristate("is_native_component", parent)
    inherited_ok = (inherited is True) or (native is True)

    ok = bool(name_ok and skeletal_ok and inherited_ok)
    report = ("parent=%s parent_class=%s name_ok=%s skeletal=%s inherited=%s "
              "native=%s expected_one_of=%s"
              % (parent_name or "<none>", _class_name(parent_obj), name_ok,
                 skeletal_ok, inherited, native, list(INHERITED_MESH_NAMES)))
    return ok, report


def _inherited_mesh_data(components):
    """The FSubobjectData of the inherited animated mesh, or None.

    RAISES when a name-matched candidate's type probe cannot be evaluated -
    the caller's except turns that into a READ_ERROR detail, so a broken probe
    never presents as the graded "mesh component missing" failure.
    """
    for name in INHERITED_MESH_NAMES:
        data = _find_component(components, name)
        if data is None:
            continue
        tri = _isinstance_tristate(_sub_object(data), "SkeletalMeshComponent")
        if tri is None:
            raise RuntimeError(
                "MESH_TYPE_PROBE_ERROR name=%s class=%s"
                % (name, _class_name(_sub_object(data))))
        if tri:
            return data
    return None


def _attach_socket_check(results):
    """Check 9 - the ONLY check that needs a live world.

    See the module docstring ("Why check 9 needs a world"): the SCS socket name
    is unreachable statically at three independent levels, and the component
    TEMPLATE is deliberately written with ``NAME_None``. So the generated class
    is CONSTRUCTED once, transiently, and the constructed component's
    ``GetAttachSocketName()`` UFUNCTION is read. The actor is destroyed in a
    ``finally``; the editor world is never saved by the verifier.

    FAIL-CLOSED at every step: a missing subsystem, a spawn that returns None,
    a constructed actor with no ``Weapon`` component, or an unreadable socket
    name are all FAILURES with their own distinct ``*_ERROR`` /
    ``*_UNAVAILABLE`` token - never a skip and never a pass.
    """
    cid = "weapon_attach_socket_is_weapon_socket"
    subsystem = None
    try:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    except Exception as e:  # noqa: BLE001
        results[cid] = check(cid, False,
                             "WEAPON_SPAWN_UNAVAILABLE raised %r" % (e,))
        return
    if subsystem is None:
        results[cid] = check(cid, False,
                             "WEAPON_SPAWN_UNAVAILABLE EditorActorSubsystem=None")
        return

    actor = None
    try:
        cls = unreal.EditorAssetLibrary.load_blueprint_class(ASSET_CHAR)
        if cls is None:
            results[cid] = check(cid, False,
                                 "WEAPON_SPAWN_CLASS_UNAVAILABLE %s" % ASSET_CHAR)
            return
        origin = unreal.Vector(0.0, 0.0, 0.0)
        rotation = unreal.Rotator(0.0, 0.0, 0.0)
        # bTransient=true keeps the probe out of the level's actor list where
        # the signature supports it (EditorActorSubsystem.h:227); older
        # signatures take the 3-arg form.
        try:
            actor = subsystem.spawn_actor_from_class(cls, origin, rotation, True)
        except Exception:  # noqa: BLE001 - fall back to the 3-arg spelling
            actor = subsystem.spawn_actor_from_class(cls, origin, rotation)
        if actor is None:
            results[cid] = check(cid, False,
                                 "WEAPON_SPAWN_FAILED %s" % ASSET_CHAR)
            return

        comps = actor.get_components_by_class(unreal.SceneComponent)
        found = None
        seen = []
        for comp in list(comps or []):
            try:
                name = str(comp.get_name())
            except Exception:  # noqa: BLE001
                continue
            seen.append(name)
            if name == WEAPON_NAME:
                found = comp
        if found is None:
            results[cid] = check(
                cid, False,
                "WEAPON_INSTANCE_COMPONENT_MISSING names=%s" % sorted(seen))
            return

        socket = str(_call_first(found, "get_attach_socket_name"))
        parent_name = "None"
        try:
            parent_name = str(_call_first(found, "get_attach_parent").get_name())
        except Exception:  # noqa: BLE001 - corroboration only, recorded not gated
            parent_name = "<unreadable>"
        ok = socket == SOCKET_NAME
        results[cid] = check(
            cid, ok,
            ("WEAPON_ATTACH_SOCKET_OK socket=%s parent=%s" % (socket, parent_name))
            if ok else
            ("WEAPON_ATTACH_SOCKET_WRONG socket=%s expected=%s parent=%s"
             % (socket, SOCKET_NAME, parent_name)))
    except Exception as e:  # noqa: BLE001
        results[cid] = check(cid, False,
                             "WEAPON_ATTACH_SOCKET_READ_ERROR raised %r" % (e,))
    finally:
        if actor is not None:
            try:
                subsystem.destroy_actor(actor)
            except Exception:  # noqa: BLE001 - the world is never saved
                pass


def _char_checks(results):
    """Fill ``results`` for every BP_EvalChar-side check."""
    root_cause = None
    try:
        char_exists = _asset_exists(ASSET_CHAR)
    except Exception as e:  # noqa: BLE001
        root_cause = "CHAR_ASSET_PROBE_ERROR %s raised %r" % (ASSET_CHAR, e)
        char_exists = False
    else:
        if not char_exists:
            # BP_EvalChar ships in the baseline, so this is a destructive
            # submission, not the ordinary "not done yet" shape.
            root_cause = "CHAR_ASSET_MISSING %s" % ASSET_CHAR

    if root_cause is not None:
        for cid in CHAR_CHECK_IDS:
            results[cid] = check(cid, False, root_cause)
        return

    # --- subobject walk (shared by four checks) ------------------------------
    components = []
    walk_error = None
    try:
        char_bp = unreal.EditorAssetLibrary.load_asset(ASSET_CHAR)
        components = _components(char_bp)
    except Exception as e:  # noqa: BLE001
        walk_error = repr(e)
    names = _names_of(components)

    # The character still renders the task-local animated mesh. Without this,
    # an agent could author the socket on the graded asset and then point the
    # figure at some other mesh entirely.
    try:
        if walk_error is not None:
            raise RuntimeError(walk_error)
        mesh_data = _inherited_mesh_data(components)
        if mesh_data is None:
            results["char_mesh_uses_task_skeletal_mesh"] = check(
                "char_mesh_uses_task_skeletal_mesh", False,
                "CHAR_MESH_COMPONENT_MISSING names=%s" % names)
        else:
            mesh_comp = _sub_object(mesh_data)
            asset = _call_first(mesh_comp,
                                "get_skeletal_mesh_asset", "get_skinned_asset")
            got = _path_name(asset)
            ok = got.split(".")[0] == ASSET_MESH
            results["char_mesh_uses_task_skeletal_mesh"] = check(
                "char_mesh_uses_task_skeletal_mesh", ok,
                ("CHAR_MESH_ASSET_OK asset=%s" % got) if ok
                else ("CHAR_MESH_ASSET_WRONG asset=%s expected=%s"
                      % (got, ASSET_MESH)))
    except Exception as e:  # noqa: BLE001
        results["char_mesh_uses_task_skeletal_mesh"] = check(
            "char_mesh_uses_task_skeletal_mesh", False,
            "CHAR_MESH_READ_ERROR raised %r" % (e,))

    # The Weapon subobject exists.
    weapon = None
    try:
        if walk_error is not None:
            raise RuntimeError(walk_error)
        weapon = _find_component(components, WEAPON_NAME)
        results["char_has_weapon_component"] = check(
            "char_has_weapon_component", weapon is not None,
            ("WEAPON_COMPONENT_OK names=%s" % names) if weapon is not None
            else ("WEAPON_COMPONENT_MISSING names=%s" % names))
    except Exception as e:  # noqa: BLE001
        results["char_has_weapon_component"] = check(
            "char_has_weapon_component", False,
            "WEAPON_WALK_ERROR raised %r" % (e,))

    if weapon is None:
        # A broken walk and a genuinely absent Weapon are different events and
        # must not share a token.
        fanout = ("WEAPON_WALK_ERROR raised %s" % walk_error
                  if walk_error is not None
                  else "WEAPON_COMPONENT_MISSING names=%s" % names)
        for cid in ("weapon_is_static_mesh_component",
                    "weapon_shows_engine_cube",
                    "weapon_attach_parent_is_character_mesh",
                    "weapon_attach_socket_is_weapon_socket"):
            results[cid] = check(cid, False, fanout)
    else:
        weapon_obj = _sub_object(weapon)

        # It is a non-animated (static) part, not something else called Weapon.
        try:
            tri = _isinstance_tristate(weapon_obj, "StaticMeshComponent")
            if tri is None:
                results["weapon_is_static_mesh_component"] = check(
                    "weapon_is_static_mesh_component", False,
                    "WEAPON_TYPE_PROBE_ERROR type=StaticMeshComponent class=%s"
                    % _class_name(weapon_obj))
            else:
                results["weapon_is_static_mesh_component"] = check(
                    "weapon_is_static_mesh_component", tri,
                    ("WEAPON_STATIC_MESH_OK class=%s"
                     % _class_name(weapon_obj)) if tri
                    else ("WEAPON_NOT_STATIC_MESH class=%s"
                          % _class_name(weapon_obj)))
        except Exception as e:  # noqa: BLE001
            results["weapon_is_static_mesh_component"] = check(
                "weapon_is_static_mesh_component", False,
                "WEAPON_CLASS_READ_ERROR raised %r" % (e,))

        # It actually displays the engine cube.
        try:
            mesh_asset = _read_property(weapon_obj, "static_mesh", "StaticMesh")
            got = _path_name(mesh_asset)
            ok = got.split(".")[0] == CUBE_PATH
            results["weapon_shows_engine_cube"] = check(
                "weapon_shows_engine_cube", ok,
                ("WEAPON_MESH_OK mesh=%s" % got) if ok
                else ("WEAPON_MESH_NOT_CUBE mesh=%s expected=%s"
                      % (got, CUBE_PATH)))
        except Exception as e:  # noqa: BLE001
            results["weapon_shows_engine_cube"] = check(
                "weapon_shows_engine_cube", False,
                "WEAPON_MESH_READ_ERROR raised %r" % (e,))

        # It hangs off the INHERITED animated body part. Name + type +
        # inheritedness, not name alone - see _attach_parent_report.
        try:
            ok, report = _attach_parent_report(weapon)
            if ok is None:
                # A type probe that could not be evaluated is a harness event,
                # never the graded "held by the wrong parent" failure.
                results["weapon_attach_parent_is_character_mesh"] = check(
                    "weapon_attach_parent_is_character_mesh", False,
                    "WEAPON_ATTACH_TYPE_PROBE_ERROR %s" % report)
            else:
                results["weapon_attach_parent_is_character_mesh"] = check(
                    "weapon_attach_parent_is_character_mesh", bool(ok),
                    ("WEAPON_ATTACH_PARENT_OK %s" % report) if ok
                    else ("WEAPON_ATTACH_PARENT_WRONG %s" % report))
        except Exception as e:  # noqa: BLE001
            results["weapon_attach_parent_is_character_mesh"] = check(
                "weapon_attach_parent_is_character_mesh", False,
                "WEAPON_ATTACH_PARENT_READ_ERROR raised %r" % (e,))

        # ... at the named attachment point. The one check needing a world.
        _attach_socket_check(results)

    # --- compile status ------------------------------------------------------
    try:
        char_bp = unreal.EditorAssetLibrary.load_asset(ASSET_CHAR)
        status = str(_read_property(char_bp, "status", "Status"))
        ok = "UP_TO_DATE" in status.upper()
        results["char_bp_compiles_up_to_date"] = check(
            "char_bp_compiles_up_to_date", ok,
            ("CHAR_COMPILE_OK status=%s" % status) if ok
            else ("CHAR_NOT_UP_TO_DATE status=%s" % status))
    except Exception as e:  # noqa: BLE001
        results["char_bp_compiles_up_to_date"] = check(
            "char_bp_compiles_up_to_date", False,
            "CHAR_COMPILE_READ_ERROR raised %r" % (e,))


def main():
    results = {}
    try:
        _socket_checks(results)
    except Exception as e:  # noqa: BLE001 - never abort the verdict
        for cid in SOCKET_CHECK_IDS:
            if cid not in results:
                results[cid] = check(cid, False,
                                     "SOCKET_INTROSPECTION_ABORTED %r" % (e,))
    try:
        _char_checks(results)
    except Exception as e:  # noqa: BLE001
        for cid in CHAR_CHECK_IDS:
            if cid not in results:
                results[cid] = check(cid, False,
                                     "CHAR_INTROSPECTION_ABORTED %r" % (e,))

    # Constant-length, deterministically ordered verdict.
    checks = [results.get(cid) or check(cid, False, "CHECK_NOT_EVALUATED %s" % cid)
              for cid in CHECK_IDS]
    emit_verdict(checks)


if __name__ == "__main__":
    main()
