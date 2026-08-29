"""L2-introspect script for the t1-playable-level-bootstrap task (bp basket).

Structural, READ-ONLY verification of ONE agent-saved LEVEL asset and the two
agent-authored Blueprint assets its world settings wire in, via stock UE
editor-Python. Emits one CRAFTBENCH-INTROSPECT-JSON block the L2-introspect
layer parses (``layers/l2_introspect.py``; contract:
``layers/INTROSPECT_CONTRACT.md``).

What is graded (seed roster R2 lineage, ``t1-basic-level-setup``; see the task
spec): the level ``/Game/Tasks/t1-playable-level-bootstrap/L_PlayableBootstrap``
must exist, load headless, and be a minimal PLAYABLE bootstrap:

  * its world settings carry a per-level game-rules OVERRIDE that resolves to
    a Blueprint class saved under the task folder (never a native class,
    never stock content such as the substrate's own game-mode Blueprint);
  * that class's CDO names a default pawn class that is ALSO a Blueprint
    saved under the task folder, and really is a possessable pawn class
    (subclassing the substrate's stock third-person character is legal - the
    authored Blueprint asset itself is what must live in the task folder);
  * EXACTLY ONE player spawn marker is placed;
  * a floor-like collidable surface sits directly under that marker (box
    heuristic with a generous band - see the constants below).

Wiring is property-and-asset-reference only: no event-graph logic exists in
the reference and none is graded (the authoring lane cannot wire K2 graphs;
the graded outcome deliberately needs none).

THE LEVEL LOAD rides the map-load lane proven by kp_spawn_level_actors.py /
kp_blueprint_actor_audit_report.py: the L2I layer launches
``UnrealEditor-Cmd -ExecutePythonScript= -nullrhi`` with NO map argument, so
this script opens the submitted level itself through the exemplar's
three-route loader (``LevelEditorSubsystem.load_level``,
``EditorLoadingAndSavingUtils.load_map``, ``EditorLevelLibrary.load_level``).

Hard rules honoured here:
  * READ-ONLY with respect to every asset and package. Loading a level into
    the headless editor mutates nothing on disk; nothing below saves,
    renames, or deletes anything.
  * Identity by **pre-declared content path** (``LEVEL_ASSET``) and by the
    WIRING the level itself declares (world settings -> rules class -> pawn
    class) - never by asset-name scanning and never by actor label. Class is
    consulted only as an ASSERTION (``isinstance``, subclass-tolerant,
    tri-state: an unexposed type FAILS the check rather than passing on the
    absence of an exception).
  * CDO reads use ``unreal.get_default_object(cls)`` ONLY (refgate catch
    2026-08-12: ``cls.get_default_object()`` resolves against the class OF
    THE INSTANCE and returns the CDO of BlueprintGeneratedClass itself - a
    poisoned object that fails every downstream read).
  * Stock UE Python only. Never Aura's MCP tools - that would grade Aura
    with Aura.
  * Every check is wrapped so one wrong API name degrades to exactly one
    FAILED check with the exception in ``detail`` instead of aborting the
    verdict.
  * **FAIL CLOSED.** No check passes because a probe did not raise. A
    missing level fails every check with one named root cause; a level that
    opens to an EMPTY actor list is a graded failure, never a skip; a
    prerequisite failure (no override, unresolvable CDO, no unique spawn
    marker) fans its own root-cause token into every dependent check.
  * The check list has a **constant length (12)** on every leg, including a
    missing level. ``registry.py`` reports ``tests_passed/tests_run`` from
    these counts, so a submission cannot improve its ratio by making checks
    unreachable.

Dead-gate audit (every graded fact excludes the free/untouched value):
  * a fresh level's world settings carry NO game-rules override (None) - the
    override-present gate is live;
  * a freshly authored game-rules Blueprint's default pawn class is NOT None
    (the engine seeds its own built-in stand-in pawn class), so presence
    alone would be a DEAD gate - the live gate is the task-folder Blueprint
    gate, which the built-in native class (a ``/Script/`` path) fails;
  * the substrate's stock game-mode / character Blueprints live under
    ``/Game/ThirdPerson/``, outside the demanded prefix - pointing the
    override at stock content fails the same prefix gate;
  * a fresh level places zero spawn markers and zero collidable geometry, so
    the count gate and both floor gates cannot pass by accident;
  * a no-collision decorative mesh reports ZERO colliding bounds and fails
    the floor footprint gate by construction.

Detail strings are stable, ASCII-ONLY, greppable tokens; each meaningful
token+key literal lives in ONE string literal (never split across
concatenations) so the MATRIX oracle can grep it from source. Error tokens
(``*_PROBE_ERROR`` / ``*_READ_ERROR`` / ``*_ABORTED`` /
``CHECK_NOT_EVALUATED``) are disjoint from graded failure tokens and appear
in NO matrix row, so a broken UE API name can never be credited as a named
assertion. No detail contains either automation result marker; neither
marker substring appears anywhere in this file.

UE 5.8 API notes (routes and their provenance):
  * Existence   - ``unreal.EditorAssetLibrary.does_asset_exist`` (proven).
  * LEVEL LOAD  - three routes, the kp_blueprint_actor_audit_report order:
    ``LevelEditorSubsystem.load_level`` first,
    ``EditorLoadingAndSavingUtils.load_map`` second,
    ``EditorLevelLibrary.load_level`` legacy last (route proven live under
    ``-nullrhi`` by the kp-spawn / audit refgates, 2026-08-11/12).
  * Actor walk  - ``EditorActorSubsystem.get_all_level_actors`` with the
    ``EditorLevelLibrary`` legacy fallback.
  * World settings - three routes: the world's ``get_world_settings``
    method, the reflected ``persistent_level.world_settings`` property
    chain, and a ``WorldSettings`` actor scan; the game-rules override is
    the reflected ``default_game_mode`` property (both spellings tried -
    UE underscore-folds reflected names).
  * CDO reads   - ``unreal.get_default_object`` (module function, the one
    correct route - see above); the pawn wiring is the reflected
    ``default_pawn_class`` property.
  * Floor       - ``Actor.get_actor_bounds(only_colliding_components=True)``
    per candidate actor: colliding-only bounds are the collision truth (a
    mesh with no collision contributes nothing), the footprint and band
    thresholds live in this file's constants.
"""
import json

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax / oracle checks
    unreal = None

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

# --- Pre-declared identity (content PATHS, never asset-name scanning) --------
TASK_ID = "t1-playable-level-bootstrap"
LEVEL_NAME = "L_PlayableBootstrap"
LEVEL_ASSET = "/Game/Tasks/t1-playable-level-bootstrap/L_PlayableBootstrap"
TASK_CLASS_PREFIX = "/Game/Tasks/t1-playable-level-bootstrap/"

# --- Verifier-owned constants (authoring-time truth; see the task notes.md) --
EXPECTED_START_COUNT = 1
FLOOR_MIN_HALF_EXTENT_XY = 100.0   # colliding half-extent per horizontal axis
                                   # (= at least 200 units across; prompt-
                                   # disclosed because it is graded)
FLOOR_XY_MARGIN = 50.0             # verifier-only generosity on containment
FLOOR_BAND_ABOVE = 10.0            # marker may sit up to 10 units below top
FLOOR_BAND_BELOW = 500.0           # floor top at most 500 units below marker

# --- The check ids, in emission order. Length is the score denominator. ------
CHECK_IDS = (
    "level_asset_exists",
    "level_opens_with_actors",
    "world_settings_resolved",
    "gamemode_override_present",
    "gamemode_is_task_blueprint",
    "gamemode_is_gamemode_subclass",
    "default_pawn_class_present",
    "default_pawn_is_task_blueprint",
    "default_pawn_is_pawn_subclass",
    "player_start_exactly_one",
    "floor_candidate_present",
    "floor_under_player_start",
)


# --------------------------------------------------------------------------- #
# verdict plumbing                                                             #
# --------------------------------------------------------------------------- #

def _defang(text, cap=500):
    """Neutralize agent-controlled text before it enters the verdict block.

    Review catch 2026-08-12: the layer parser's non-greedy START/END regex
    means an embedded marker inside a detail string TRUNCATES the JSON body -
    a failing submission could escape its graded FAIL into HARNESS-ERROR (a
    denominator opt-out). Every detail flows through check(), so this is the
    one seam: strip the marker family and cap length."""
    s = str(text)
    for marker in ("CRAFTBENCH-INTROSPECT-JSON", "CRAFTBENCH-ASSET-INTEGRITY-JSON"):
        s = s.replace(marker, "CB-MARKER-DEFANGED")
    if len(s) > cap:
        s = s[:cap] + "...[capped]"
    return s


def check(check_id, passed, detail=""):
    return {"id": str(check_id), "passed": bool(passed),
            "detail": _defang(detail)}


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


def _fanout(results, cids, detail):
    for cid in cids:
        if cid not in results:
            results[cid] = check(cid, False, detail)


# --------------------------------------------------------------------------- #
# small reflection helpers                                                     #
# --------------------------------------------------------------------------- #

def _read_property(obj, *names):
    """First readable spelling of a reflected property; re-raises if none is.

    BP-authored variables keep their authored spelling; engine UPROPERTYs are
    underscore-folded by codegen. Never invents a value: if every spelling
    fails, the last exception propagates and the caller fails closed.
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


def _class_path(cls):
    try:
        return str(cls.get_path_name())
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


def _default_object(cls):
    """The class default object, or raises.

    ONE route on purpose (refgate catch 2026-08-12): calling
    ``cls.get_default_object()`` on a class INSTANCE resolves the method
    against the instance's own class and returns the CDO *of
    BlueprintGeneratedClass itself* - a poisoned object that then fails every
    downstream read. The module function takes the class as an argument and
    is the correct route."""
    fn = getattr(unreal, "get_default_object", None)
    if fn is not None:
        cdo = fn(cls)
        if cdo is not None:
            return cdo
    raise RuntimeError("class default object unavailable for %s"
                       % _class_path(cls))


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


# --------------------------------------------------------------------------- #
# level open + actor enumeration (fail-closed; three-route loader)             #
# --------------------------------------------------------------------------- #

def _load_routes():
    """[(route_name, callable(path) -> truthy)] in preference order."""
    routes = []
    try:
        les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        fn = getattr(les, "load_level", None) if les is not None else None
        if fn is not None:
            routes.append(("LevelEditorSubsystem", fn))
    except Exception:  # noqa: BLE001 - subsystem absent: try the fallbacks
        pass
    lib = getattr(unreal, "EditorLoadingAndSavingUtils", None)
    fn = getattr(lib, "load_map", None) if lib is not None else None
    if fn is not None:
        routes.append(("EditorLoadingAndSavingUtils",
                       lambda path, _fn=fn: _fn(path) is not None))
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
    itself is broken (the caller wraps that as BOOT_LEVEL_LOAD_PROBE_ERROR).
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
            "BOOT_LEVEL_LOAD_FAILED path=/Game/Tasks/t1-playable-level-bootstrap/L_PlayableBootstrap the editor did not open the submitted level"  # noqa: E501 - single literal by MATRIX-oracle law
        )
    actors = _all_level_actors()
    if not actors:
        raise GradedLevelFailure(
            "BOOT_ACTOR_LIST_EMPTY the loaded level enumerated zero actors")
    return actors, opened_via


# --------------------------------------------------------------------------- #
# world settings resolution (three routes, fail-closed)                        #
# --------------------------------------------------------------------------- #

def _editor_world():
    errors = []
    try:
        ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        fn = getattr(ues, "get_editor_world", None) if ues is not None else None
        if fn is not None:
            world = fn()
            if world is not None:
                return world
    except Exception as e:  # noqa: BLE001
        errors.append(repr(e))
    ell = getattr(unreal, "EditorLevelLibrary", None)
    fn = getattr(ell, "get_editor_world", None) if ell is not None else None
    if fn is not None:
        try:
            world = fn()
            if world is not None:
                return world
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))
    raise RuntimeError("no editor-world route: %s" % errors)


def _world_settings(actors):
    """(world_settings, route_name), or raises (probe problem)."""
    errors = []
    world = None
    try:
        world = _editor_world()
    except Exception as e:  # noqa: BLE001
        errors.append(repr(e))
    if world is not None:
        getter = getattr(world, "get_world_settings", None)
        if getter is not None:
            try:
                ws = getter()
                if ws is not None:
                    return ws, "WorldMethod"
            except Exception as e:  # noqa: BLE001
                errors.append(repr(e))
        try:
            level = _read_property(world, "persistent_level", "PersistentLevel")
            if level is not None:
                ws = _read_property(level, "world_settings", "WorldSettings")
                if ws is not None:
                    return ws, "PersistentLevel"
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))
    ws_cls = getattr(unreal, "WorldSettings", None)
    if ws_cls is not None:
        try:
            for actor in actors:
                if actor is not None and isinstance(actor, ws_cls):
                    return actor, "ActorScan"
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))
    raise RuntimeError("no world-settings route: %s" % errors)


# --------------------------------------------------------------------------- #
# the wiring checks: override -> rules class -> pawn class                     #
# --------------------------------------------------------------------------- #

WIRING_CHECK_IDS = (
    "world_settings_resolved",
    "gamemode_override_present",
    "gamemode_is_task_blueprint",
    "gamemode_is_gamemode_subclass",
    "default_pawn_class_present",
    "default_pawn_is_task_blueprint",
    "default_pawn_is_pawn_subclass",
)


def _task_blueprint_check(results, cid, cls, tmpl_not_task, tmpl_not_bp,
                          tmpl_probe, tmpl_ok):
    """One "is an agent-authored task-folder Blueprint class" gate.

    The templates arrive as WHOLE single literals from the call site (never
    assembled from a stem) so every token+key head is greppable in one
    literal run:
      tmpl_not_task % (path,)   tmpl_not_bp % (path,)
      tmpl_probe % (path,)      tmpl_ok % (path,)
    """
    path = _class_path(cls)
    if not path.startswith(TASK_CLASS_PREFIX):
        results[cid] = check(cid, False, tmpl_not_task % (path,))
        return
    verdict = _isinstance_tristate(cls, "BlueprintGeneratedClass")
    if verdict is None:
        results[cid] = check(cid, False, tmpl_probe % (path,))
        return
    if not verdict:
        results[cid] = check(cid, False, tmpl_not_bp % (path,))
        return
    results[cid] = check(cid, True, tmpl_ok % (path,))


def _wiring_checks(results, actors):
    """Fill the 7 wiring checks (world settings through pawn subclass)."""
    try:
        ws, route = _world_settings(actors)
    except Exception as e:  # noqa: BLE001
        cause = "BOOT_WORLD_SETTINGS_PROBE_ERROR raised %r" % (e,)
        _fanout(results, WIRING_CHECK_IDS, cause)
        return
    results["world_settings_resolved"] = check(
        "world_settings_resolved", True,
        "BOOT_WORLD_SETTINGS_OK class=%s route=%s" % (_class_name(ws), route))

    try:
        gm_cls = _read_property(ws, "default_game_mode", "DefaultGameMode")
    except Exception as e:  # noqa: BLE001
        cause = "BOOT_GAMEMODE_OVERRIDE_READ_ERROR raised %r" % (e,)
        _fanout(results, WIRING_CHECK_IDS, cause)
        return
    if gm_cls is None:
        cause = "BOOT_GAMEMODE_OVERRIDE_NONE the level carries no per-level game-rules override"  # noqa: E501 - single literal by MATRIX-oracle law
        _fanout(results, WIRING_CHECK_IDS, cause)
        return
    gm_path = _class_path(gm_cls)
    results["gamemode_override_present"] = check(
        "gamemode_override_present", True,
        "BOOT_GAMEMODE_OVERRIDE_OK class_path=%s" % gm_path)

    _task_blueprint_check(
        results, "gamemode_is_task_blueprint", gm_cls,
        "BOOT_GAMEMODE_NOT_TASK_ASSET class_path=%s expected_prefix=/Game/Tasks/t1-playable-level-bootstrap/",  # noqa: E501
        "BOOT_GAMEMODE_NOT_BLUEPRINT_CLASS class_path=%s the override does not resolve to a Blueprint-generated class",  # noqa: E501
        "BOOT_GAMEMODE_BP_PROBE_ERROR class_path=%s the generated-class type is not exposed to Python",  # noqa: E501
        "BOOT_GAMEMODE_TASK_ASSET_OK class_path=%s")

    try:
        gm_cdo = _default_object(gm_cls)
    except Exception as e:  # noqa: BLE001
        cause = "BOOT_GAMEMODE_CDO_PROBE_ERROR raised %r" % (e,)
        _fanout(results, ("gamemode_is_gamemode_subclass",
                          "default_pawn_class_present",
                          "default_pawn_is_task_blueprint",
                          "default_pawn_is_pawn_subclass"), cause)
        return
    verdict = _isinstance_tristate(gm_cdo, "GameModeBase")
    if verdict is None:
        results["gamemode_is_gamemode_subclass"] = check(
            "gamemode_is_gamemode_subclass", False,
            "BOOT_GAMEMODE_BASE_PROBE_ERROR class=%s the game-rules base type is not exposed to Python"  # noqa: E501
            % _class_name(gm_cdo))
    elif not verdict:
        results["gamemode_is_gamemode_subclass"] = check(
            "gamemode_is_gamemode_subclass", False,
            "BOOT_GAMEMODE_WRONG_BASE class=%s the override class is not a game-rules class"  # noqa: E501
            % _class_name(gm_cdo))
    else:
        results["gamemode_is_gamemode_subclass"] = check(
            "gamemode_is_gamemode_subclass", True,
            "BOOT_GAMEMODE_BASE_OK class=%s" % _class_name(gm_cdo))

    try:
        pawn_cls = _read_property(gm_cdo, "default_pawn_class",
                                  "DefaultPawnClass")
    except Exception as e:  # noqa: BLE001
        cause = "BOOT_DEFAULT_PAWN_READ_ERROR raised %r" % (e,)
        _fanout(results, ("default_pawn_class_present",
                          "default_pawn_is_task_blueprint",
                          "default_pawn_is_pawn_subclass"), cause)
        return
    if pawn_cls is None:
        cause = "BOOT_DEFAULT_PAWN_NONE the ruleset names no default controllable body"  # noqa: E501 - single literal by MATRIX-oracle law
        _fanout(results, ("default_pawn_class_present",
                          "default_pawn_is_task_blueprint",
                          "default_pawn_is_pawn_subclass"), cause)
        return
    pawn_path = _class_path(pawn_cls)
    results["default_pawn_class_present"] = check(
        "default_pawn_class_present", True,
        "BOOT_DEFAULT_PAWN_OK class_path=%s" % pawn_path)

    _task_blueprint_check(
        results, "default_pawn_is_task_blueprint", pawn_cls,
        "BOOT_PAWN_NOT_TASK_ASSET class_path=%s expected_prefix=/Game/Tasks/t1-playable-level-bootstrap/",  # noqa: E501
        "BOOT_PAWN_NOT_BLUEPRINT_CLASS class_path=%s the default body does not resolve to a Blueprint-generated class",  # noqa: E501
        "BOOT_PAWN_BP_PROBE_ERROR class_path=%s the generated-class type is not exposed to Python",  # noqa: E501
        "BOOT_PAWN_TASK_ASSET_OK class_path=%s")

    try:
        pawn_cdo = _default_object(pawn_cls)
    except Exception as e:  # noqa: BLE001
        results["default_pawn_is_pawn_subclass"] = check(
            "default_pawn_is_pawn_subclass", False,
            "BOOT_PAWN_CDO_PROBE_ERROR raised %r" % (e,))
        return
    verdict = _isinstance_tristate(pawn_cdo, "Pawn")
    if verdict is None:
        results["default_pawn_is_pawn_subclass"] = check(
            "default_pawn_is_pawn_subclass", False,
            "BOOT_PAWN_TYPE_PROBE_ERROR class=%s the pawn base type is not exposed to Python"  # noqa: E501
            % _class_name(pawn_cdo))
    elif not verdict:
        results["default_pawn_is_pawn_subclass"] = check(
            "default_pawn_is_pawn_subclass", False,
            "BOOT_PAWN_NOT_PAWN_CLASS class=%s the default body class is not a possessable pawn"  # noqa: E501
            % _class_name(pawn_cdo))
    else:
        results["default_pawn_is_pawn_subclass"] = check(
            "default_pawn_is_pawn_subclass", True,
            "BOOT_PAWN_CLASS_OK class=%s" % _class_name(pawn_cdo))


# --------------------------------------------------------------------------- #
# the placement checks: spawn marker + floor heuristic                         #
# --------------------------------------------------------------------------- #

def _player_starts(actors):
    """[player-start actors], or raises None-probe via ValueError sentinel."""
    cls = getattr(unreal, "PlayerStart", None)
    if cls is None:
        raise RuntimeError("PLAYER_START_TYPE_UNEXPOSED")
    found = []
    for actor in actors:
        if actor is None:
            continue
        try:
            if isinstance(actor, cls):
                found.append(actor)
        except Exception:  # noqa: BLE001 - one unreadable actor is skipped;
            continue      # the count gate still sees every readable one
    return found


def _start_check(results, actors):
    """Fill player_start_exactly_one; return the unique start or (None, why)."""
    try:
        starts = _player_starts(actors)
    except Exception as e:  # noqa: BLE001
        detail = ("BOOT_START_TYPE_PROBE_ERROR raised %r the spawn-marker "
                  "type probe could not run" % (e,))
        results["player_start_exactly_one"] = check(
            "player_start_exactly_one", False, detail)
        return None, detail
    if len(starts) == 0:
        detail = "BOOT_START_MISSING count=0 expected=1 no player spawn marker is placed"  # noqa: E501 - single literal by MATRIX-oracle law
        results["player_start_exactly_one"] = check(
            "player_start_exactly_one", False, detail)
        return None, detail
    if len(starts) != EXPECTED_START_COUNT:
        detail = ("BOOT_START_COUNT_WRONG count=%d expected=1 exactly one spawn marker is demanded"  # noqa: E501 - single literal by MATRIX-oracle law
                  % len(starts))
        results["player_start_exactly_one"] = check(
            "player_start_exactly_one", False, detail)
        return None, detail
    start = starts[0]
    try:
        loc = _vec3(start.get_actor_location())
    except Exception as e:  # noqa: BLE001
        detail = "BOOT_START_LOCATION_READ_ERROR raised %r" % (e,)
        results["player_start_exactly_one"] = check(
            "player_start_exactly_one", False, detail)
        return None, detail
    results["player_start_exactly_one"] = check(
        "player_start_exactly_one", True,
        "BOOT_START_OK count=1 location=%s" % _fmt3(loc))
    return (start, loc), None


def _colliding_bounds(actor):
    """(origin, extent) of the actor's COLLIDING-components bounds; raises on
    a broken probe. A mesh with no collision reports a zero extent."""
    fn = getattr(actor, "get_actor_bounds", None)
    if fn is None:
        raise RuntimeError("get_actor_bounds is not exposed to Python")
    try:
        res = fn(True)
    except TypeError:
        res = fn(True, False)
    origin, extent = res[0], res[1]
    return _vec3(origin), _vec3(extent)


def _floor_checks(results, actors, start_info, start_fail):
    """Fill floor_candidate_present + floor_under_player_start."""
    exclude = []
    if start_info is not None:
        exclude.append(start_info[0])
    ws_cls = getattr(unreal, "WorldSettings", None)

    candidates = []
    examined = 0
    errors = 0
    last_err = None
    for actor in actors:
        if actor is None or any(actor is e for e in exclude):
            continue
        if ws_cls is not None:
            try:
                if isinstance(actor, ws_cls):
                    continue
            except Exception:  # noqa: BLE001 - keep it as a candidate
                pass
        examined += 1
        try:
            origin, extent = _colliding_bounds(actor)
        except Exception as e:  # noqa: BLE001
            errors += 1
            last_err = e
            continue
        if (extent[0] >= FLOOR_MIN_HALF_EXTENT_XY
                and extent[1] >= FLOOR_MIN_HALF_EXTENT_XY):
            candidates.append((origin, extent))

    if not candidates:
        if examined > 0 and errors == examined:
            detail = ("BOOT_FLOOR_BOUNDS_PROBE_ERROR raised %r on every "
                      "examined actor" % (last_err,))
        else:
            detail = ("BOOT_FLOOR_NO_CANDIDATE examined=%d min_half_extent_xy=100.0 no collidable surface at least 200 units across exists in the level"  # noqa: E501 - single literal by MATRIX-oracle law
                      % examined)
        results["floor_candidate_present"] = check(
            "floor_candidate_present", False, detail)
        _fanout(results, ("floor_under_player_start",), detail)
        return
    results["floor_candidate_present"] = check(
        "floor_candidate_present", True,
        "BOOT_FLOOR_CANDIDATE_OK count=%d" % len(candidates))

    if start_info is None:
        _fanout(results, ("floor_under_player_start",), start_fail)
        return
    _start_actor, (sx, sy, sz) = start_info
    hit = None
    for origin, extent in candidates:
        if (abs(sx - origin[0]) <= extent[0] + FLOOR_XY_MARGIN
                and abs(sy - origin[1]) <= extent[1] + FLOOR_XY_MARGIN):
            top = origin[2] + extent[2]
            gap = sz - top
            if -FLOOR_BAND_ABOVE <= gap <= FLOOR_BAND_BELOW:
                hit = (top, gap)
                break
    if hit is None:
        results["floor_under_player_start"] = check(
            "floor_under_player_start", False,
            "BOOT_FLOOR_NOT_UNDER_START start=%s candidates=%d no collidable floor top lies directly under the marker within the band from 10.0 above to 500.0 below"  # noqa: E501 - single literal by MATRIX-oracle law
            % (_fmt3((sx, sy, sz)), len(candidates)))
        return
    results["floor_under_player_start"] = check(
        "floor_under_player_start", True,
        "BOOT_FLOOR_UNDER_START_OK floor_top_z=%.3f gap=%.3f" % hit)


# --------------------------------------------------------------------------- #
# the level gate + main                                                        #
# --------------------------------------------------------------------------- #

def _level_checks(results):
    """Fill ``results`` (a dict keyed by check id) for every check."""
    # A raised probe is NOT the same event as a genuinely absent level, and
    # the two must not share a token: an API break that fanned out the
    # missing-level token would be credited as the empty leg's named failure.
    root_cause = None
    try:
        exists = bool(unreal.EditorAssetLibrary.does_asset_exist(LEVEL_ASSET))
    except Exception as e:  # noqa: BLE001
        root_cause = "BOOT_LEVEL_ASSET_PROBE_ERROR raised %r" % (e,)
        results["level_asset_exists"] = check(
            "level_asset_exists", False, root_cause)
        exists = False
    else:
        if exists:
            results["level_asset_exists"] = check(
                "level_asset_exists", True,
                "BOOT_LEVEL_ASSET_OK /Game/Tasks/t1-playable-level-bootstrap/L_PlayableBootstrap")  # noqa: E501
        else:
            root_cause = "BOOT_LEVEL_MISSING /Game/Tasks/t1-playable-level-bootstrap/L_PlayableBootstrap"  # noqa: E501 - single literal by MATRIX-oracle law
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
            "BOOT_LEVEL_OPEN_OK actors=%d route=%s" % (len(actors), route))
    except GradedLevelFailure as gf:
        detail = str(gf)
        results["level_opens_with_actors"] = check(
            "level_opens_with_actors", False, detail)
        _fanout(results, CHECK_IDS, detail)
        return
    except Exception as e:  # noqa: BLE001
        detail = "BOOT_LEVEL_LOAD_PROBE_ERROR raised %r" % (e,)
        results["level_opens_with_actors"] = check(
            "level_opens_with_actors", False, detail)
        _fanout(results, CHECK_IDS, detail)
        return

    _wiring_checks(results, actors)
    start_info, start_fail = _start_check(results, actors)
    _floor_checks(results, actors, start_info, start_fail)


def main():
    results = {}
    try:
        _level_checks(results)
    except Exception as e:  # noqa: BLE001 - never abort the verdict
        _fanout(results, CHECK_IDS, "BOOT_INTROSPECTION_ABORTED %r" % (e,))

    # Constant-length, deterministically ordered verdict.
    checks = [results.get(cid) or check(cid, False, "CHECK_NOT_EVALUATED %s" % cid)
              for cid in CHECK_IDS]
    emit_verdict(checks)


if __name__ == "__main__":
    main()
