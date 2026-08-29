"""L2-introspect script for the kp-spawn-level-actors task (python basket).

Structural, READ-ONLY verification of ONE agent-saved LEVEL asset via stock UE
editor-Python. Emits one CRAFTBENCH-INTROSPECT-JSON block the L2-introspect
layer parses (``layers/l2_introspect.py``; contract:
``layers/INTROSPECT_CONTRACT.md``).

What is graded (seed roster R23, re-shaped and re-pathed; see the task spec):
the level ``/Game/Tasks/kp-spawn-level-actors/L_ActorLayout`` must exist,
load, and contain six placed actors resolved BY ACTOR LABEL, each label used
exactly once:

  * ``Floor``   - a cube-mesh actor at (0, 0, -50), scale (20, 20, 1)
  * ``Start``   - a player spawn marker at (0, 0, 110)
  * ``Bounds``  - an actor carrying a box collision region, world center
                  (0, 0, 200), scaled world extent (1000, 1000, 400)
  * ``Enemy_1`` ``Enemy_2`` ``Enemy_3`` - sphere-mesh actors at
                  (300, 0, 110), (-300, 0, 110), (0, 300, 110)

plus: no OTHER actor's label may start with ``Enemy_``.

THE LEVEL LOAD IS THE ONE UNSPIKED STEP IN THIS SCRIPT (plan U1). The L2I
layer launches ``UnrealEditor-Cmd -ExecutePythonScript= -nullrhi`` with NO map
argument (``layers/l2_introspect.py`` builds the command line without one), so
this script must open the submitted level itself, headless. Two routes are
tried (``LevelEditorSubsystem.load_level``, then
``EditorLevelLibrary.load_level``); neither has been proven live under
``-nullrhi`` on UE 5.8 at the time of authoring. Until the authoring-lane run
proves it, treat any ``LEVEL_LOAD_PROBE_ERROR`` verdict as a harness question,
never as agent evidence. The risk is recorded in the task's ``notes.md`` and
is shared by every future level-deliverable task in this basket.

Hard rules honoured here:
  * READ-ONLY with respect to every asset and package. Loading a level into
    the headless editor mutates nothing on disk; nothing below saves, renames,
    or deletes anything.
  * Identity by **pre-declared content path** (``LEVEL_ASSET``) and
    pre-declared ACTOR LABEL, never by class scanning. Class is consulted only
    as an assertion ("is the thing labeled Start really a player spawn
    marker"), written as ``isinstance`` so a legitimate subclass passes.
  * Stock UE Python only (``EditorAssetLibrary``, level-editor subsystems,
    reflection). Never Aura's MCP tools - that would grade Aura with Aura.
  * Every check is wrapped so one wrong API name degrades to exactly one
    FAILED check with the exception in ``detail`` instead of aborting the
    verdict.
  * **FAIL CLOSED.** No check passes because a probe did not raise. A missing
    asset fails every check with one named root cause; a level that opens to
    an EMPTY actor list is a graded failure (``LEVEL_ACTOR_LIST_EMPTY``),
    never a skip; a type probe that cannot be evaluated fails the check; an
    unreadable transform is a ``*_READ_ERROR`` failure, never a pass. Every
    absence assertion (``no_extra_enemy_labels``) only runs after the
    positive existence checks had the chance to run against a real actor
    list - on an empty or unloadable level it FAILS carrying the root cause.
  * The check list has a **constant length (17)** on every leg, including a
    missing level. ``registry.py`` reports ``tests_passed/tests_run`` from
    these counts, so a submission cannot improve its ratio by making checks
    unreachable.

Every graded number EXCLUDES the value an untouched spawn gets for free
(the dead-gate audit lives in the task spec): spawn-default location is the
origin and every graded location is off-origin in at least one axis;
spawn-default scale is (1, 1, 1) vs the floor's (20, 20, 1); a fresh
box-region actor's extent is tens of units vs the graded 1000/1000/400; a
freshly spawned mesh actor carries NO mesh, so the cube/sphere gates cannot
pass by accident; editor auto-labels (class-derived) never equal the six
demanded labels.

Detail strings are stable, ASCII, greppable tokens, and every meaningful
token span is written in ONE string literal (never assembled from a
``"%s_SUFFIX"`` stem) so the MATRIX oracle's source grep always finds it.
Failing tokens never appear on a passing branch. Error tokens
(``*_PROBE_ERROR`` / ``*_READ_ERROR`` / ``*_ABORTED`` / ``CHECK_NOT_EVALUATED``)
are disjoint from graded-failure tokens and appear in NO matrix row, so a
broken UE API name can never be credited as a named assertion. No detail
contains either automation result marker the log parser counts as a test
result; neither substring appears anywhere in this file.

UE 5.8 API notes:
  * ``LevelEditorSubsystem`` is an EDITOR subsystem
    (``unreal.get_editor_subsystem``); ``EditorLevelLibrary`` is the
    deprecated-but-present static fallback for both ``load_level`` and
    ``get_all_level_actors``.
  * ``AActor::GetActorLabel`` is editor-only and exposed as
    ``get_actor_label`` - labels are the identity key here precisely because
    they are what the prompt demands and what the editor shows.
  * ``get_actor_location`` / ``get_actor_scale3d`` are the pythonized
    ``K2_GetActorLocation`` / actor scale accessors.
  * Box regions are read via ``get_components_by_class(unreal.BoxComponent)``
    (subclass-tolerant); extent via ``get_scaled_box_extent`` first (world
    truth: accepts BOTH the set-extent route and the scaled-actor route),
    falling back to the ``box_extent`` property times the component's world
    scale. Property spellings are underscore-folded by UE's codegen, so every
    property read tries several spellings.
"""
import json

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax / oracle checks
    unreal = None

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

# --- Pre-declared identity (content PATH and actor LABELS, never class) ------
TASK_ID = "kp-spawn-level-actors"
LEVEL_ASSET = "/Game/Tasks/kp-spawn-level-actors/L_ActorLayout"

FLOOR_LABEL = "Floor"
START_LABEL = "Start"
BOUNDS_LABEL = "Bounds"
ENEMY_LABELS = ("Enemy_1", "Enemy_2", "Enemy_3")
ENEMY_PREFIX = "Enemy_"

CUBE_MESH = "/Engine/BasicShapes/Cube.Cube"
SPHERE_MESH = "/Engine/BasicShapes/Sphere.Sphere"

# --- Graded numbers (every one excludes the untouched-spawn default) ---------
FLOOR_LOCATION = (0.0, 0.0, -50.0)      # z off origin; spawn default is origin
FLOOR_SCALE = (20.0, 20.0, 1.0)         # x,y far from the (1,1,1) default
START_LOCATION = (0.0, 0.0, 110.0)      # z off origin
BOUNDS_CENTER = (0.0, 0.0, 200.0)       # z off origin
BOUNDS_EXTENT = (1000.0, 1000.0, 400.0)  # a fresh box region is tens of units
ENEMY_LOCATIONS = (
    ("Enemy_1", (300.0, 0.0, 110.0)),
    ("Enemy_2", (-300.0, 0.0, 110.0)),
    ("Enemy_3", (0.0, 300.0, 110.0)),
)

# Tolerances (verifier-only; the TARGETS are in the prompt, these are not).
LOCATION_TOL = 1.0
SCALE_TOL = 0.01
EXTENT_TOL = 1.0

# --- The check ids, in emission order. Length is the score denominator. ------
CHECK_IDS = (
    "level_asset_exists",
    "level_opens_with_actors",
    "floor_actor_present",
    "floor_mesh_is_cube",
    "floor_location_exact",
    "floor_scale_exact",
    "start_actor_present",
    "start_is_spawn_marker",
    "start_location_exact",
    "bounds_actor_present",
    "bounds_is_box_region",
    "bounds_center_exact",
    "bounds_extent_exact",
    "enemy_actors_present",
    "enemy_meshes_are_spheres",
    "enemy_locations_exact",
    "no_extra_enemy_labels",
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


class GradedLevelFailure(RuntimeError):
    """A level-open failure whose message IS the graded detail string."""


# --------------------------------------------------------------------------- #
# small reflection helpers                                                     #
# --------------------------------------------------------------------------- #

def _asset_exists(path):
    return bool(unreal.EditorAssetLibrary.does_asset_exist(path))


def _read_property(obj, *names):
    """First readable spelling of a reflected property; re-raises if none is."""
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
    evaluated" and every caller treats it as NOT satisfied. This never
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


def _vec3(v):
    """(x, y, z) floats out of an unreal.Vector (or anything shaped like one)."""
    out = []
    for lower, upper in (("x", "X"), ("y", "Y"), ("z", "Z")):
        val = getattr(v, lower, None)
        if val is None:
            val = getattr(v, upper, None)
        if val is None:
            val = _read_property(v, lower, upper)
        out.append(float(val))
    return tuple(out)


def _fmt3(t):
    return "(%.3f, %.3f, %.3f)" % (t[0], t[1], t[2])


def _within(got, want, tol):
    return all(abs(g - w) <= tol for g, w in zip(got, want))


# --------------------------------------------------------------------------- #
# level open + actor enumeration (fail-closed)                                 #
# --------------------------------------------------------------------------- #

def _load_routes():
    """[(route_name, callable(path) -> bool)] in preference order."""
    routes = []
    try:
        les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        fn = getattr(les, "load_level", None) if les is not None else None
        if fn is not None:
            routes.append(("LevelEditorSubsystem", fn))
    except Exception:  # noqa: BLE001 - subsystem absent: try the fallback
        pass
    ell = getattr(unreal, "EditorLevelLibrary", None)
    fn = getattr(ell, "load_level", None) if ell is not None else None
    if fn is not None:
        routes.append(("EditorLevelLibrary", fn))
    return routes


def _all_level_actors():
    """Every actor in the loaded level. Raises when no route works."""
    last = None
    try:
        eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        fn = getattr(eas, "get_all_level_actors", None) if eas is not None else None
        if fn is not None:
            return list(fn() or [])
    except Exception as e:  # noqa: BLE001
        last = e
    ell = getattr(unreal, "EditorLevelLibrary", None)
    fn = getattr(ell, "get_all_level_actors", None) if ell is not None else None
    if fn is not None:
        return list(fn() or [])
    raise last if last is not None else RuntimeError("ACTOR_ENUM_UNAVAILABLE")


def _open_level_actors():
    """(actors, route_name) for the submitted level, or a graded failure.

    Raises GradedLevelFailure (message IS the graded detail) when the level
    refuses to open or opens empty; raises any other exception when the probe
    itself is broken (the caller wraps that as LEVEL_LOAD_PROBE_ERROR).
    """
    routes = _load_routes()
    if not routes:
        raise RuntimeError("no level-load route is exposed to Python")
    route_errors = []
    opened_via = None
    for name, fn in routes:
        try:
            if bool(fn(LEVEL_ASSET)):
                opened_via = name
                break
        except Exception as e:  # noqa: BLE001
            route_errors.append((name, repr(e)))
    if opened_via is None:
        if len(route_errors) == len(routes):
            # every route RAISED: a probe problem, not agent evidence
            raise RuntimeError("all load routes raised: %s" % route_errors)
        raise GradedLevelFailure(
            "LEVEL_LOAD_FAILED path=/Game/Tasks/kp-spawn-level-actors/L_ActorLayout the editor did not open the submitted level"  # noqa: E501 - single literal by MATRIX-oracle law
        )
    actors = _all_level_actors()
    if not actors:
        raise GradedLevelFailure(
            "LEVEL_ACTOR_LIST_EMPTY the loaded level enumerated zero actors")
    return actors, opened_via


def _label_of(actor):
    try:
        return str(actor.get_actor_label())
    except Exception:  # noqa: BLE001
        return "<unreadable>"


def _label_map(actors):
    """{label: [actors...]} plus a bounded, sorted summary string."""
    by_label = {}
    for actor in actors:
        by_label.setdefault(_label_of(actor), []).append(actor)
    summary = sorted(by_label.keys())
    if len(summary) > 40:
        summary = summary[:40] + ["..."]
    return by_label, str(summary)


# --------------------------------------------------------------------------- #
# per-actor readbacks (fail-closed; callers wrap in try/except)                #
# --------------------------------------------------------------------------- #

def _actor_location(actor):
    return _vec3(actor.get_actor_location())


def _actor_scale(actor):
    return _vec3(actor.get_actor_scale3d())


def _mesh_path(actor):
    """The object path of the actor's assigned static mesh, or a marker.

    Returns "<no mesh component>" / "<no mesh assigned>" when the actor has
    no mesh surface at all - those flow into the graded *_MESH_WRONG detail
    (a fresh mesh actor ships with NO mesh, so this is a real gate). Raises
    only when the reflection read itself is broken.
    """
    cls = getattr(unreal, "StaticMeshComponent", None)
    if cls is None:
        raise RuntimeError("StaticMeshComponent is not exposed to Python")
    comps = list(actor.get_components_by_class(cls) or [])
    if not comps:
        return "<no mesh component>"
    chosen = None
    for comp in comps:
        try:
            mesh = _read_property(comp, "static_mesh", "StaticMesh")
        except Exception:  # noqa: BLE001 - try the next component
            continue
        if mesh is not None:
            chosen = mesh
            break
    if chosen is None:
        return "<no mesh assigned>"
    return str(chosen.get_path_name())


def _box_component(actor):
    """(box_component, classes_summary). Component may be None.

    Raises only when the component walk itself is broken.
    """
    box_cls = getattr(unreal, "BoxComponent", None)
    if box_cls is None:
        raise RuntimeError("BoxComponent is not exposed to Python")
    boxes = list(actor.get_components_by_class(box_cls) or [])
    if boxes:
        return boxes[0], ""
    classes = []
    try:
        scene_cls = getattr(unreal, "ActorComponent", None)
        for comp in list(actor.get_components_by_class(scene_cls) or []):
            classes.append(_class_name(comp))
    except Exception:  # noqa: BLE001 - the summary is best-effort decoration
        classes = ["<unreadable>"]
    return None, str(sorted(set(classes)))


def _box_world_center(box, actor):
    getter = getattr(box, "get_world_location", None)
    if getter is not None:
        try:
            return _vec3(getter())
        except Exception:  # noqa: BLE001 - fall through to the actor read
            pass
    return _actor_location(actor)


def _box_world_extent(box):
    """The box's scaled WORLD extent - true for both authoring routes
    (setting the extent directly, or scaling the actor)."""
    getter = getattr(box, "get_scaled_box_extent", None)
    if getter is not None:
        try:
            return _vec3(getter())
        except Exception:  # noqa: BLE001 - fall through to the property route
            pass
    extent = _vec3(_read_property(box, "box_extent", "BoxExtent"))
    scale_getter = getattr(box, "get_world_scale", None)
    if scale_getter is None:
        raise RuntimeError("no scaled-extent route is readable")
    scale = _vec3(scale_getter())
    return tuple(e * s for e, s in zip(extent, scale))


# --------------------------------------------------------------------------- #
# label resolution (exactly-once, fail-closed)                                 #
# --------------------------------------------------------------------------- #

def _fanout(results, cids, detail):
    for cid in cids:
        if cid not in results:
            results[cid] = check(cid, False, detail)


def _resolve_floor(by_label, labels_summary):
    matches = by_label.get(FLOOR_LABEL, [])
    if not matches:
        return None, ("FLOOR_ACTOR_MISSING wanted_label=Floor labels=%s"
                      % labels_summary)
    if len(matches) > 1:
        return None, ("FLOOR_LABEL_DUPLICATE count=%d wanted_label=Floor"
                      % len(matches))
    return matches[0], "FLOOR_ACTOR_OK label=Floor class=%s" % _class_name(matches[0])


def _resolve_start(by_label, labels_summary):
    matches = by_label.get(START_LABEL, [])
    if not matches:
        return None, ("START_ACTOR_MISSING wanted_label=Start labels=%s"
                      % labels_summary)
    if len(matches) > 1:
        return None, ("START_LABEL_DUPLICATE count=%d wanted_label=Start"
                      % len(matches))
    return matches[0], "START_ACTOR_OK label=Start class=%s" % _class_name(matches[0])


def _resolve_bounds(by_label, labels_summary):
    matches = by_label.get(BOUNDS_LABEL, [])
    if not matches:
        return None, ("BOUNDS_ACTOR_MISSING wanted_label=Bounds labels=%s"
                      % labels_summary)
    if len(matches) > 1:
        return None, ("BOUNDS_LABEL_DUPLICATE count=%d wanted_label=Bounds"
                      % len(matches))
    return matches[0], "BOUNDS_ACTOR_OK label=Bounds class=%s" % _class_name(matches[0])


# --------------------------------------------------------------------------- #
# the checks                                                                   #
# --------------------------------------------------------------------------- #

def _floor_checks(results, floor, floor_detail):
    if floor is None:
        _fanout(results, ("floor_mesh_is_cube", "floor_location_exact",
                          "floor_scale_exact"), floor_detail)
        return
    try:
        mesh = _mesh_path(floor)
        ok = mesh == CUBE_MESH
        results["floor_mesh_is_cube"] = check(
            "floor_mesh_is_cube", ok,
            ("FLOOR_MESH_OK mesh=%s" % mesh) if ok else
            ("FLOOR_MESH_WRONG mesh=%s expected=/Engine/BasicShapes/Cube.Cube"
             % mesh))
    except Exception as e:  # noqa: BLE001
        results["floor_mesh_is_cube"] = check(
            "floor_mesh_is_cube", False, "FLOOR_MESH_READ_ERROR raised %r" % (e,))
    try:
        got = _actor_location(floor)
        ok = _within(got, FLOOR_LOCATION, LOCATION_TOL)
        results["floor_location_exact"] = check(
            "floor_location_exact", ok,
            ("FLOOR_LOCATION_OK got=%s" % _fmt3(got)) if ok else
            ("FLOOR_LOCATION_WRONG got=%s expected=(0.0, 0.0, -50.0) tol=1.0"
             % _fmt3(got)))
    except Exception as e:  # noqa: BLE001
        results["floor_location_exact"] = check(
            "floor_location_exact", False,
            "FLOOR_LOCATION_READ_ERROR raised %r" % (e,))
    try:
        got = _actor_scale(floor)
        ok = _within(got, FLOOR_SCALE, SCALE_TOL)
        results["floor_scale_exact"] = check(
            "floor_scale_exact", ok,
            ("FLOOR_SCALE_OK got=%s" % _fmt3(got)) if ok else
            ("FLOOR_SCALE_WRONG got=%s expected=(20.0, 20.0, 1.0) tol=0.01 "
             "spawn_default=(1, 1, 1)" % _fmt3(got)))
    except Exception as e:  # noqa: BLE001
        results["floor_scale_exact"] = check(
            "floor_scale_exact", False,
            "FLOOR_SCALE_READ_ERROR raised %r" % (e,))


def _start_checks(results, start, start_detail):
    if start is None:
        _fanout(results, ("start_is_spawn_marker", "start_location_exact"),
                start_detail)
        return
    verdict = _isinstance_tristate(start, "PlayerStart")
    if verdict is None:
        results["start_is_spawn_marker"] = check(
            "start_is_spawn_marker", False,
            "START_TYPE_PROBE_ERROR class=%s the spawn-marker type is not "
            "exposed to Python" % _class_name(start))
    elif not verdict:
        results["start_is_spawn_marker"] = check(
            "start_is_spawn_marker", False,
            "START_NOT_SPAWN_MARKER class=%s the actor labeled Start is not "
            "a player spawn marker" % _class_name(start))
    else:
        results["start_is_spawn_marker"] = check(
            "start_is_spawn_marker", True,
            "START_MARKER_OK class=%s" % _class_name(start))
    try:
        got = _actor_location(start)
        ok = _within(got, START_LOCATION, LOCATION_TOL)
        results["start_location_exact"] = check(
            "start_location_exact", ok,
            ("START_LOCATION_OK got=%s" % _fmt3(got)) if ok else
            ("START_LOCATION_WRONG got=%s expected=(0.0, 0.0, 110.0) tol=1.0"
             % _fmt3(got)))
    except Exception as e:  # noqa: BLE001
        results["start_location_exact"] = check(
            "start_location_exact", False,
            "START_LOCATION_READ_ERROR raised %r" % (e,))


def _bounds_checks(results, bounds, bounds_detail):
    if bounds is None:
        _fanout(results, ("bounds_is_box_region", "bounds_center_exact",
                          "bounds_extent_exact"), bounds_detail)
        return
    box = None
    try:
        box, classes = _box_component(bounds)
        if box is None:
            detail = ("BOUNDS_NO_BOX_REGION classes=%s no box-shaped "
                      "collision component on the actor labeled Bounds"
                      % classes)
            results["bounds_is_box_region"] = check(
                "bounds_is_box_region", False, detail)
            _fanout(results, ("bounds_center_exact", "bounds_extent_exact"),
                    detail)
            return
        results["bounds_is_box_region"] = check(
            "bounds_is_box_region", True,
            "BOUNDS_BOX_OK class=%s" % _class_name(box))
    except Exception as e:  # noqa: BLE001
        detail = "BOUNDS_BOX_PROBE_ERROR raised %r" % (e,)
        results["bounds_is_box_region"] = check(
            "bounds_is_box_region", False, detail)
        _fanout(results, ("bounds_center_exact", "bounds_extent_exact"), detail)
        return
    try:
        got = _box_world_center(box, bounds)
        ok = _within(got, BOUNDS_CENTER, LOCATION_TOL)
        results["bounds_center_exact"] = check(
            "bounds_center_exact", ok,
            ("BOUNDS_CENTER_OK got=%s" % _fmt3(got)) if ok else
            ("BOUNDS_CENTER_WRONG got=%s expected=(0.0, 0.0, 200.0) tol=1.0"
             % _fmt3(got)))
    except Exception as e:  # noqa: BLE001
        results["bounds_center_exact"] = check(
            "bounds_center_exact", False,
            "BOUNDS_CENTER_READ_ERROR raised %r" % (e,))
    try:
        got = _box_world_extent(box)
        ok = _within(got, BOUNDS_EXTENT, EXTENT_TOL)
        results["bounds_extent_exact"] = check(
            "bounds_extent_exact", ok,
            ("BOUNDS_EXTENT_OK got=%s" % _fmt3(got)) if ok else
            ("BOUNDS_EXTENT_WRONG got=%s expected=(1000.0, 1000.0, 400.0) "
             "tol=1.0" % _fmt3(got)))
    except Exception as e:  # noqa: BLE001
        results["bounds_extent_exact"] = check(
            "bounds_extent_exact", False,
            "BOUNDS_EXTENT_READ_ERROR raised %r" % (e,))


def _enemy_checks(results, by_label):
    counts = dict((label, len(by_label.get(label, []))) for label in ENEMY_LABELS)
    counts_text = str(sorted(counts.items()))
    if any(c != 1 for c in counts.values()):
        detail = ("ENEMY_SET_INCOMPLETE found=%s expected_exactly_one_each="
                  "[Enemy_1, Enemy_2, Enemy_3]" % counts_text)
        results["enemy_actors_present"] = check(
            "enemy_actors_present", False, detail)
        _fanout(results, ("enemy_meshes_are_spheres", "enemy_locations_exact"),
                detail)
        return
    results["enemy_actors_present"] = check(
        "enemy_actors_present", True, "ENEMY_SET_OK found=%s" % counts_text)

    try:
        wrong = []
        for label in ENEMY_LABELS:
            mesh = _mesh_path(by_label[label][0])
            if mesh != SPHERE_MESH:
                wrong.append((label, mesh))
        if wrong:
            results["enemy_meshes_are_spheres"] = check(
                "enemy_meshes_are_spheres", False,
                "ENEMY_MESH_WRONG which=%s mesh=%s "
                "expected=/Engine/BasicShapes/Sphere.Sphere wrong_count=%d"
                % (wrong[0][0], wrong[0][1], len(wrong)))
        else:
            results["enemy_meshes_are_spheres"] = check(
                "enemy_meshes_are_spheres", True,
                "ENEMY_MESH_OK all three carry the sphere shape")
    except Exception as e:  # noqa: BLE001
        results["enemy_meshes_are_spheres"] = check(
            "enemy_meshes_are_spheres", False,
            "ENEMY_MESH_READ_ERROR raised %r" % (e,))

    try:
        wrong = []
        for label, want in ENEMY_LOCATIONS:
            got = _actor_location(by_label[label][0])
            if not _within(got, want, LOCATION_TOL):
                wrong.append((label, got, want))
        if wrong:
            label, got, want = wrong[0]
            results["enemy_locations_exact"] = check(
                "enemy_locations_exact", False,
                "ENEMY_LOCATION_WRONG which=%s got=%s expected=%s tol=1.0 "
                "wrong_count=%d"
                % (label, _fmt3(got), _fmt3(want), len(wrong)))
        else:
            results["enemy_locations_exact"] = check(
                "enemy_locations_exact", True,
                "ENEMY_LOCATIONS_OK all three within tol=1.0")
    except Exception as e:  # noqa: BLE001
        results["enemy_locations_exact"] = check(
            "enemy_locations_exact", False,
            "ENEMY_LOCATION_READ_ERROR raised %r" % (e,))


def _extra_labels_check(results, by_label):
    try:
        extras = sorted(label for label in by_label
                        if label.startswith(ENEMY_PREFIX)
                        and label not in ENEMY_LABELS)
        if extras:
            results["no_extra_enemy_labels"] = check(
                "no_extra_enemy_labels", False,
                "ENEMY_EXTRA_LABELS extras=%s only Enemy_1 Enemy_2 and "
                "Enemy_3 may start with Enemy_" % str(extras))
        else:
            results["no_extra_enemy_labels"] = check(
                "no_extra_enemy_labels", True,
                "ENEMY_LABELS_OK no extra Enemy_ labels")
    except Exception as e:  # noqa: BLE001
        results["no_extra_enemy_labels"] = check(
            "no_extra_enemy_labels", False,
            "ENEMY_LABELS_PROBE_ERROR raised %r" % (e,))


def _level_checks(results):
    """Fill ``results`` (a dict keyed by check id) for every check."""
    # A raised probe is NOT the same event as a genuinely absent level, and
    # the two must not share a token: an API break that fanned out
    # LEVEL_ASSET_MISSING would be credited as the empty leg's named failure.
    root_cause = None
    try:
        exists = _asset_exists(LEVEL_ASSET)
    except Exception as e:  # noqa: BLE001
        root_cause = "LEVEL_ASSET_PROBE_ERROR raised %r" % (e,)
        results["level_asset_exists"] = check(
            "level_asset_exists", False, root_cause)
        exists = False
    else:
        if exists:
            results["level_asset_exists"] = check(
                "level_asset_exists", True,
                "LEVEL_ASSET_OK /Game/Tasks/kp-spawn-level-actors/L_ActorLayout")
        else:
            root_cause = "LEVEL_ASSET_MISSING /Game/Tasks/kp-spawn-level-actors/L_ActorLayout"  # noqa: E501 - single literal by MATRIX-oracle law
            results["level_asset_exists"] = check(
                "level_asset_exists", False, root_cause)
    if not exists:
        # Constant denominator: every remaining check still reports, as a
        # failure whose detail names the single root cause.
        _fanout(results, CHECK_IDS, root_cause)
        return

    try:
        actors, route = _open_level_actors()
        results["level_opens_with_actors"] = check(
            "level_opens_with_actors", True,
            "LEVEL_OPEN_OK actors=%d route=%s" % (len(actors), route))
    except GradedLevelFailure as gf:
        detail = str(gf)
        results["level_opens_with_actors"] = check(
            "level_opens_with_actors", False, detail)
        _fanout(results, CHECK_IDS, detail)
        return
    except Exception as e:  # noqa: BLE001
        # Unspiked-route honesty: a broken load probe is an ERROR event with
        # its own token, creditable to no matrix row (see the docstring).
        detail = "LEVEL_LOAD_PROBE_ERROR raised %r" % (e,)
        results["level_opens_with_actors"] = check(
            "level_opens_with_actors", False, detail)
        _fanout(results, CHECK_IDS, detail)
        return

    by_label, labels_summary = _label_map(actors)

    floor, floor_detail = _resolve_floor(by_label, labels_summary)
    results["floor_actor_present"] = check(
        "floor_actor_present", floor is not None, floor_detail)
    _floor_checks(results, floor, floor_detail)

    start, start_detail = _resolve_start(by_label, labels_summary)
    results["start_actor_present"] = check(
        "start_actor_present", start is not None, start_detail)
    _start_checks(results, start, start_detail)

    bounds, bounds_detail = _resolve_bounds(by_label, labels_summary)
    results["bounds_actor_present"] = check(
        "bounds_actor_present", bounds is not None, bounds_detail)
    _bounds_checks(results, bounds, bounds_detail)

    _enemy_checks(results, by_label)
    _extra_labels_check(results, by_label)


def main():
    results = {}
    try:
        _level_checks(results)
    except Exception as e:  # noqa: BLE001 - never abort the verdict
        _fanout(results, CHECK_IDS, "KP_INTROSPECTION_ABORTED %r" % (e,))

    # Constant-length, deterministically ordered verdict.
    checks = [results.get(cid) or check(cid, False, "CHECK_NOT_EVALUATED %s" % cid)
              for cid in CHECK_IDS]
    emit_verdict(checks)


if __name__ == "__main__":
    main()
