"""L2-introspect script for the kp-blueprint-actor-audit-report task.

Structural, READ-ONLY verification of THREE submitted artifacts via stock UE
editor-Python. Emits one CRAFTBENCH-INTROSPECT-JSON block the L2-introspect
layer parses (``layers/l2_introspect.py``; contract:
``layers/INTROSPECT_CONTRACT.md``).

What is graded (seed roster Block B row R25, sheet name
``t4-blueprint-actor-audit-report``; see the task spec):

  1. ASSET  - ``BP_AuditTarget`` under ``/Game/Tasks/<id>/``: an actor-class
     Blueprint carrying a mesh part ``Body`` assigned the engine cube, a
     point-light part ``Beacon``, a bool variable ``Flagged`` defaulting True
     and a float variable ``Score`` defaulting 99.0, compiling up to date.
  2. LEVEL  - ``L_AuditScene`` under the same folder: EXACTLY two placed
     instances of that class, labeled ``Audit_Alpha`` at (0, 0, 100) and
     ``Audit_Beta`` at (500, 0, 100).
  3. REPORT - ``Content/Tasks/<id>/reports/audit.txt``: a strict-grammar
     plain-text audit whose every line is CROSS-CHECKED against the
     introspected truth of artifacts 1 and 2. A report line that disagrees
     with what is actually on disk FAILS; the report can never substitute for
     the artifacts (each artifact group is gated independently), and the
     artifacts can never substitute for the report.

The gold-leak defense (datatable_csv_export.py precedent): the REQUIRED
values (names, the cube path, the two defaults, the two labels and
locations, the count of two) are PINNED in this file's constants - the
report cross-check only ever ADDS the requirement "the report tells the
truth about the submission". Nothing expected is read from a place the
agent can write.

Hard rules honoured here:
  * READ-ONLY. Nothing below mutates an asset, a package, or the project.
    (Loading the submitted level changes only the editor's current-map
    session state, never a saved byte.)
  * Identity by pre-declared content path, subobject NAME, variable NAME and
    actor LABEL - never by class lookup. Class is consulted only as an
    ASSERTION and written subclass-tolerant where a route allows it.
  * Stock UE Python only. Never Aura's MCP tools - that would grade Aura
    with Aura.
  * Every check wrapped in its own try/except: one wrong API name degrades
    to exactly one FAILED check with the exception in ``detail``.
  * FAIL CLOSED. No check passes because a probe did not raise. An empty or
    missing submission fails every check (never a vacuous pass): every
    absence/negative assertion here is conjoined with the positive
    existence read that produced it - the instance COUNT gate requires a
    loaded level and a resolved class, the report set-equality gates
    require a parsed report AND resolved asset truth, and a failed
    prerequisite fans its own root-cause token into the dependent checks.
  * The check list has a CONSTANT length (20) on every leg, including the
    empty submission (0/20). ``registry.py`` reports
    ``tests_passed/tests_run`` from these counts.

Detail strings are stable, ASCII-ONLY, greppable tokens; each meaningful
token+key literal lives in ONE string constant (never split across
concatenations) so the MATRIX oracle can grep it from source. Error tokens
(``*_PROBE_ERROR`` / ``*_READ_ERROR`` / ``*_WALK_ERROR``) are disjoint from
graded failure tokens and appear in no MATRIX row. No detail contains either
automation result marker; neither marker substring appears anywhere in this
file.

UE 5.8 API notes (routes and their provenance):
  * Existence   - ``unreal.EditorAssetLibrary.does_asset_exist`` (proven).
  * SCS walk    - ``unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)``
    + ``SubobjectDataBlueprintFunctionLibrary`` (proven live by the dawn-fog
    and flashlight tasks; ENGINE subsystem, get_editor_subsystem raises).
  * CDO reads   - generated class via ``BlueprintEditorLibrary.generated_class``
    with a ``load_object(None, "<path>.<name>_C")`` fallback; CDO via
    ``Class.get_default_object()`` with ``unreal.get_default_object``
    fallback. BP-authored variables keep their authored spelling; reflected
    engine props are underscore-folded - every read tries both.
  * LEVEL LOAD  - ``LevelEditorSubsystem.load_level`` first,
    ``EditorLoadingAndSavingUtils.load_map`` then ``EditorLevelLibrary``
    legacy spelling last. THIS IS THE UNSPIKED ROUTE (plan U1 listed
    "level load/enumerate" as an open probe): first task to grade an
    agent-authored level headless under ``-nullrhi``. Fail-closed either
    way - a refused load is the graded AUDIT_LEVEL_LOAD_FAILED, an
    unavailable API is an uncreditable AUDIT_LEVEL_LOAD_PROBE_ERROR.
  * Actor walk  - ``EditorActorSubsystem.get_all_level_actors`` with the
    ``EditorLevelLibrary`` legacy fallback; labels via
    ``Actor.get_actor_label`` (editor-only), locations via
    ``Actor.get_actor_location``.
  * Class match - ``unreal.MathLibrary.class_is_child_of`` (subclass
    tolerant); exact-path compare fallback (tolerance loss recorded in
    notes.md as an accepted residual).
"""
import json
import os
import re

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax / oracle checks
    unreal = None

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

# --- Pre-declared identity (content PATHS and NAMES, never class lookup) -----
TASK_ID = "kp-blueprint-actor-audit-report"
BP_NAME = "BP_AuditTarget"
ASSET_BP = "/Game/Tasks/%s/%s" % (TASK_ID, BP_NAME)
GEN_CLASS_PATH = "%s.%s_C" % (ASSET_BP, BP_NAME)
LEVEL_NAME = "L_AuditScene"
ASSET_LEVEL = "/Game/Tasks/%s/%s" % (TASK_ID, LEVEL_NAME)
REPORT_REL = "Content/Tasks/%s/reports/audit.txt" % TASK_ID

BODY_NAME = "Body"
BEACON_NAME = "Beacon"
FLAG_NAME = "Flagged"
SCORE_NAME = "Score"

# --- Pinned expected values (the agent cannot write any of these) ------------
EXPECTED_CUBE = "/Engine/BasicShapes/Cube.Cube"
FLAG_EXPECTED = True          # a fresh bool variable defaults False - live gate
SCORE_EXPECTED = 99.0         # a fresh float variable defaults 0.0 - live gate
SCORE_TOLERANCE = 1e-3
ALPHA_LABEL = "Audit_Alpha"
BETA_LABEL = "Audit_Beta"
ALPHA_LOCATION = (0.0, 0.0, 100.0)
BETA_LOCATION = (500.0, 0.0, 100.0)
LOCATION_TOLERANCE = 1.0      # cm; authored by exact spawn, so 1.0 is generous
EXPECTED_INSTANCE_COUNT = 2
COMPILE_CLEAN_TOKEN = "clean"  # the one legal value of the report compile line

# --- The check ids, grouped; total length is the score denominator (20). -----
ASSET_CHECK_IDS = (
    "audit_bp_exists",
    "audit_bp_is_actor_class",
    "audit_body_is_mesh_part",
    "audit_body_mesh_is_engine_cube",
    "audit_beacon_is_point_light",
    "audit_flag_var_true",
    "audit_score_var_value",
    "audit_bp_compiles_clean",
)
LEVEL_CHECK_IDS = (
    "audit_level_exists",
    "audit_level_loads",
    "audit_instances_exactly_two",
    "audit_alpha_instance_placed",
    "audit_beta_instance_placed",
)
REPORT_CHECK_IDS = (
    "report_file_present",
    "report_grammar_parses",
    "report_class_line_truthful",
    "report_component_lines_truthful",
    "report_variable_lines_truthful",
    "report_compile_line_truthful",
    "report_instance_lines_truthful",
)
CHECK_IDS = ASSET_CHECK_IDS + LEVEL_CHECK_IDS + REPORT_CHECK_IDS

# --- Report grammar (disclosed verbatim in the agent prompt) -----------------
_NUM = r"(-?\d+(?:\.\d+)?)"
RE_CLASS = re.compile(r"^class name=(\S+) parent=(\S+)$")
RE_COMPONENT = re.compile(r"^component name=(\S+) class=(\S+)$")
RE_VARIABLE = re.compile(r"^variable name=(\S+) type=(\S+)$")
RE_COMPILE = re.compile(r"^compile status=(\S+)$")
RE_INSTANCE = re.compile(
    r"^instance label=(\S+) location=%s,%s,%s$" % (_NUM, _NUM, _NUM))


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


def _fanout(results, cids, detail):
    for cid in cids:
        if cid not in results:
            results[cid] = check(cid, False, detail)


# --------------------------------------------------------------------------- #
# small reflection helpers                                                     #
# --------------------------------------------------------------------------- #

def _read_property(obj, *names):
    """First readable spelling of a property; re-raises if none reads.

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


def _isinstance_tristate(obj, type_name):
    """isinstance as True / False / None; None means the probe could not be
    evaluated, and every caller treats that as NOT satisfied."""
    if obj is None:
        return False
    cls = getattr(unreal, type_name, None)
    if cls is None:
        return None
    try:
        return bool(isinstance(obj, cls))
    except Exception:  # noqa: BLE001
        return None


def _content_dir():
    raw = unreal.Paths.project_content_dir()
    try:
        full = unreal.Paths.convert_relative_path_to_full(raw)
    except Exception:  # noqa: BLE001 - older spelling; abspath is equivalent
        full = os.path.abspath(str(raw))
    return str(full)


def _report_path():
    return os.path.join(_content_dir(), "Tasks", TASK_ID, "reports",
                        "audit.txt")


def _read_text(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


# --------------------------------------------------------------------------- #
# Blueprint truth: generated class, CDO, SCS components, variables, compile    #
# --------------------------------------------------------------------------- #

def _generated_class(bp):
    """The Blueprint's generated class, or raises. Two routes."""
    lib = getattr(unreal, "BlueprintEditorLibrary", None)
    if lib is not None and getattr(lib, "generated_class", None) is not None:
        try:
            cls = lib.generated_class(bp)
            if cls is not None:
                return cls
        except Exception:  # noqa: BLE001 - fall through to load_object
            pass
    cls = unreal.load_object(None, GEN_CLASS_PATH)
    if cls is None:
        raise RuntimeError("generated class unresolvable at %s" % GEN_CLASS_PATH)
    return cls


def _default_object(gen_cls):
    """The class default object, or raises.

    ONE route on purpose (refgate catch 2026-08-12): calling
    ``gen_cls.get_default_object()`` on a class INSTANCE resolves the method
    against the instance's own class and returns the CDO *of
    BlueprintGeneratedClass itself* - a poisoned object that then fails every
    downstream read (no Flagged/Score, not an Actor, wrong class name). The
    module function takes the class as an argument and is the correct route."""
    fn = getattr(unreal, "get_default_object", None)
    if fn is not None:
        cdo = fn(gen_cls)
        if cdo is not None:
            return cdo
    raise RuntimeError("class default object unavailable")


def _parent_class_name(bp, gen_cls, cdo=None):
    """Simple name of the Blueprint's parent class, or raises."""
    try:
        parent = _read_property(bp, "parent_class", "ParentClass")
        if parent is not None:
            return str(parent.get_name())
    except Exception:  # noqa: BLE001 - fall through to the struct route
        pass
    getter = getattr(gen_cls, "get_super_struct", None)
    if getter is not None:
        try:
            sup = getter()
            if sup is not None:
                return str(sup.get_name())
        except Exception:  # noqa: BLE001 - fall through to the wrapper route
            pass
    # Wrapper route (refgate catch 2026-08-12: both routes above are
    # unreadable on 5.8 for a loaded generated class): python wraps a BP
    # instance as its nearest NATIVE ancestor, so the CDO's python type name
    # IS the native parent ("Actor" for an Actor-parented BP). Accepted
    # residual, recorded in notes.md: a BP-of-BP parent reports the native
    # ancestor, not the intermediate BP.
    if cdo is not None:
        name = type(cdo).__name__
        if name:
            return str(name)
    raise RuntimeError("no readable parent-class route")


def _is_handle(obj):
    try:
        return isinstance(obj, unreal.SubobjectDataHandle)
    except Exception:  # noqa: BLE001
        return False


def _gather_handles(subsystem, blueprint):
    """Every subobject handle on a Blueprint. FAIL-CLOSED: raises on empty."""
    for name in ("gather_subobject_data_for_blueprint",
                 "k2_gather_subobject_data_for_blueprint"):
        fn = getattr(subsystem, name, None)
        if fn is None:
            continue
        out = fn(blueprint)
        if (isinstance(out, (tuple, list)) and len(out) == 2
                and isinstance(out[-1], (tuple, list)) and not _is_handle(out[0])):
            out = out[-1]
        handles = list(out or [])
        if not handles:
            raise RuntimeError("SUBOBJECT_GATHER_EMPTY via %s" % name)
        return handles
    raise AttributeError("SUBOBJECT_GATHER_UNAVAILABLE on %r" % (subsystem,))


def _data_for(handle):
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


def _scene_components(blueprint):
    """[(display_name, template_object)] for every SCENE component subobject.

    The actor-root subobject (whose template is the actor CDO, not a scene
    component) is excluded; DefaultSceneRoot, if present, is included - the
    report must enumerate it. FAIL-CLOSED: raises rather than returning an
    empty walk, and raises on an unevaluable scene-component probe.
    """
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    if subsystem is None:
        raise RuntimeError("SUBOBJECT_SUBSYSTEM_UNAVAILABLE")
    out = []
    for handle in _gather_handles(subsystem, blueprint):
        data = _data_for(handle)
        if data is None:
            continue
        obj = _sub_object(data)
        if obj is None:
            continue
        is_scene = _isinstance_tristate(obj, "SceneComponent")
        if is_scene is None:
            raise RuntimeError("SUBOBJECT_TYPE_PROBE_ERROR class=%s"
                               % _class_name(obj))
        if not is_scene:
            continue  # the actor root subobject
        out.append((_sub_display_name(data), obj))
    if not out:
        raise RuntimeError("SUBOBJECT_WALK_EMPTY")
    return out


def _resolve(components, wanted_name, type_name, tmpl_missing, tmpl_probe,
             tmpl_wrong, tmpl_ok):
    """(component_or_None, detail) for one pre-declared named part.

    Name AND type both required; three distinct failure outcomes carry three
    distinct tokens so the matrix can tell absent from impostor from an
    unevaluable probe. The templates arrive as WHOLE single literals from
    the call site (never assembled from a stem) so every token+key head is
    greppable in one literal run:
      tmpl_missing % (names, wanted)      tmpl_probe % (class, expected)
      tmpl_wrong % (class, name, expected)   tmpl_ok % (class, name)
    """
    names = sorted(n for n, _ in components if n)
    found = None
    for got, obj in components:
        if got == wanted_name:
            found = obj
            break
    if found is None:
        return None, tmpl_missing % (names, wanted_name)
    verdict = _isinstance_tristate(found, type_name)
    if verdict is None:
        return None, tmpl_probe % (_class_name(found), type_name)
    if not verdict:
        return None, tmpl_wrong % (_class_name(found), wanted_name, type_name)
    return found, tmpl_ok % (_class_name(found), wanted_name)


def _compile_status_clean(bp):
    """True iff the freshly loaded Blueprint reads up to date. Raises on an
    unreadable status (UBlueprint::Status is transient, BlueprintReadOnly)."""
    status = str(_read_property(bp, "status", "Status"))
    return "UP_TO_DATE" in status.upper(), status


# --------------------------------------------------------------------------- #
# group 1: the asset checks (fills 8 results; returns the truth for group 3)   #
# --------------------------------------------------------------------------- #

def _asset_checks(results):
    """Fill the 8 asset checks; return the truth dict group 3 cross-checks
    against, or None (with every dependent report check set to fan out the
    recorded per-field root cause)."""
    truth = {
        "parent_name": None, "parent_fail": None,
        "components": None, "components_fail": None,
        "cdo": None, "cdo_fail": None,
        "flag_kind": None, "flag_fail": None,
        "score_kind": None, "score_fail": None,
        "compile_clean": None, "compile_fail": None,
    }

    root_cause = None
    try:
        bp_exists = bool(unreal.EditorAssetLibrary.does_asset_exist(ASSET_BP))
    except Exception as e:  # noqa: BLE001
        root_cause = "AUDIT_BP_PROBE_ERROR path=%s raised %r" % (ASSET_BP, e)
        bp_exists = False
    if not bp_exists:
        if root_cause is None:
            root_cause = "AUDIT_BP_MISSING path=%s" % ASSET_BP
        results["audit_bp_exists"] = check("audit_bp_exists", False, root_cause)
        _fanout(results, ASSET_CHECK_IDS, root_cause)
        for key in ("parent_fail", "components_fail", "cdo_fail", "flag_fail",
                    "score_fail", "compile_fail"):
            truth[key] = root_cause
        return truth
    results["audit_bp_exists"] = check(
        "audit_bp_exists", True, "AUDIT_BP_OK path=%s" % ASSET_BP)

    # --- load + generated class + CDO (shared prerequisites) -----------------
    bp, gen_cls, cdo = None, None, None
    try:
        bp = unreal.EditorAssetLibrary.load_asset(ASSET_BP)
        if bp is None:
            raise RuntimeError("load_asset returned None")
        gen_cls = _generated_class(bp)
        cdo = _default_object(gen_cls)
        truth["cdo"] = cdo
        truth["gen_cls"] = gen_cls
    except Exception as e:  # noqa: BLE001
        # Graded: a Blueprint whose generated class/CDO cannot be resolved is
        # a broken deliverable, not a verifier fault - but the token is kept
        # out of every MATRIX row so it can never be credited as a named
        # variant failure.
        cause = "AUDIT_BP_CLASS_UNRESOLVED path=%s raised %r" % (ASSET_BP, e)
        _fanout(results, ("audit_bp_is_actor_class", "audit_flag_var_true",
                          "audit_score_var_value"), cause)
        truth["cdo_fail"] = cause
        truth["flag_fail"] = cause
        truth["score_fail"] = cause
        truth["parent_fail"] = cause

    # --- actor-ness ----------------------------------------------------------
    if cdo is not None:
        verdict = _isinstance_tristate(cdo, "Actor")
        if verdict is None:
            results["audit_bp_is_actor_class"] = check(
                "audit_bp_is_actor_class", False,
                "AUDIT_ACTOR_TYPE_PROBE_ERROR class=%s" % _class_name(cdo))
        else:
            results["audit_bp_is_actor_class"] = check(
                "audit_bp_is_actor_class", bool(verdict),
                ("AUDIT_ACTOR_CLASS_OK class=%s" % _class_name(cdo)) if verdict
                else ("AUDIT_BP_NOT_ACTOR class=%s" % _class_name(cdo)))

    # --- parent name (consumed only by the report cross-check) ---------------
    if bp is not None and gen_cls is not None:
        try:
            truth["parent_name"] = _parent_class_name(bp, gen_cls, cdo)
        except Exception as e:  # noqa: BLE001
            truth["parent_fail"] = "AUDIT_PARENT_READ_ERROR raised %r" % (e,)

    # --- SCS component walk --------------------------------------------------
    components = None
    if bp is not None:
        try:
            components = _scene_components(bp)
            truth["components"] = sorted(
                (name, _class_name(obj)) for name, obj in components)
        except Exception as e:  # noqa: BLE001
            truth["components_fail"] = (
                "AUDIT_SUBOBJECT_WALK_ERROR raised %r" % (e,))
    else:
        truth["components_fail"] = "AUDIT_BP_LOAD_FAILED path=%s" % ASSET_BP
    if components is None:
        walk_fail = truth["components_fail"]
        _fanout(results, ("audit_body_is_mesh_part",
                          "audit_body_mesh_is_engine_cube",
                          "audit_beacon_is_point_light"), walk_fail)
    else:
        body, body_detail = _resolve(
            components, BODY_NAME, "StaticMeshComponent",
            "AUDIT_BODY_MISSING names=%s wanted=%s",
            "AUDIT_BODY_TYPE_PROBE_ERROR class=%s expected=%s",
            "AUDIT_BODY_WRONG_TYPE class=%s name=%s expected=%s",
            "AUDIT_BODY_PART_OK class=%s name=%s")
        beacon, beacon_detail = _resolve(
            components, BEACON_NAME, "PointLightComponent",
            "AUDIT_BEACON_MISSING names=%s wanted=%s",
            "AUDIT_BEACON_TYPE_PROBE_ERROR class=%s expected=%s",
            "AUDIT_BEACON_WRONG_TYPE class=%s name=%s expected=%s",
            "AUDIT_BEACON_PART_OK class=%s name=%s")
        results["audit_body_is_mesh_part"] = check(
            "audit_body_is_mesh_part", body is not None, body_detail)
        results["audit_beacon_is_point_light"] = check(
            "audit_beacon_is_point_light", beacon is not None, beacon_detail)

        if body is None:
            results["audit_body_mesh_is_engine_cube"] = check(
                "audit_body_mesh_is_engine_cube", False, body_detail)
        else:
            try:
                mesh = _read_property(body, "static_mesh", "StaticMesh")
                mesh_path = ("None" if mesh is None
                             else str(mesh.get_path_name()))
                ok = mesh_path == EXPECTED_CUBE
                results["audit_body_mesh_is_engine_cube"] = check(
                    "audit_body_mesh_is_engine_cube", ok,
                    ("AUDIT_BODY_MESH_OK mesh=%s" % mesh_path) if ok
                    else ("AUDIT_BODY_MESH_WRONG mesh=%s expected=%s"
                          % (mesh_path, EXPECTED_CUBE)))
            except Exception as e:  # noqa: BLE001
                results["audit_body_mesh_is_engine_cube"] = check(
                    "audit_body_mesh_is_engine_cube", False,
                    "AUDIT_BODY_MESH_READ_ERROR raised %r" % (e,))

    # --- the two variables, read off the CDO ---------------------------------
    if cdo is not None:
        try:
            value = _read_property(cdo, FLAG_NAME, "flagged")
        except Exception as e:  # noqa: BLE001
            detail = ("AUDIT_FLAG_VAR_ABSENT name=%s raised %r"
                      % (FLAG_NAME, e))
            results["audit_flag_var_true"] = check(
                "audit_flag_var_true", False, detail)
            truth["flag_fail"] = detail
        else:
            if not isinstance(value, bool):
                detail = ("AUDIT_FLAG_NOT_BOOL value_type=%s value=%s"
                          % (type(value).__name__, value))
                results["audit_flag_var_true"] = check(
                    "audit_flag_var_true", False, detail)
                truth["flag_fail"] = detail
            else:
                truth["flag_kind"] = "bool"
                ok = value is True
                results["audit_flag_var_true"] = check(
                    "audit_flag_var_true", ok,
                    ("AUDIT_FLAG_OK value=%s" % value) if ok
                    else ("AUDIT_FLAG_NOT_TRUE value=%s expected=True"
                          % value))
        try:
            value = _read_property(cdo, SCORE_NAME, "score")
        except Exception as e:  # noqa: BLE001
            detail = ("AUDIT_SCORE_VAR_ABSENT name=%s raised %r"
                      % (SCORE_NAME, e))
            results["audit_score_var_value"] = check(
                "audit_score_var_value", False, detail)
            truth["score_fail"] = detail
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                detail = ("AUDIT_SCORE_NOT_NUMERIC value_type=%s value=%s"
                          % (type(value).__name__, value))
                results["audit_score_var_value"] = check(
                    "audit_score_var_value", False, detail)
                truth["score_fail"] = detail
            else:
                truth["score_kind"] = "float"
                ok = abs(float(value) - SCORE_EXPECTED) <= SCORE_TOLERANCE
                results["audit_score_var_value"] = check(
                    "audit_score_var_value", ok,
                    ("AUDIT_SCORE_OK value=%s" % value) if ok
                    else ("AUDIT_SCORE_WRONG_VALUE value=%s expected=99.0"
                          % value))

    # --- compile status ------------------------------------------------------
    if bp is None:
        detail = "AUDIT_BP_LOAD_FAILED path=%s" % ASSET_BP
        results["audit_bp_compiles_clean"] = check(
            "audit_bp_compiles_clean", False, detail)
        truth["compile_fail"] = detail
    else:
        try:
            clean, status = _compile_status_clean(bp)
            truth["compile_clean"] = clean
            results["audit_bp_compiles_clean"] = check(
                "audit_bp_compiles_clean", clean,
                ("AUDIT_COMPILE_OK status=%s" % status) if clean
                else ("AUDIT_BP_NOT_UP_TO_DATE status=%s" % status))
        except Exception as e:  # noqa: BLE001
            detail = "AUDIT_COMPILE_READ_ERROR raised %r" % (e,)
            results["audit_bp_compiles_clean"] = check(
                "audit_bp_compiles_clean", False, detail)
            truth["compile_fail"] = detail
    return truth


# --------------------------------------------------------------------------- #
# group 2: the level checks (fills 5 results; returns instance truth)          #
# --------------------------------------------------------------------------- #

def _load_level():
    """Load the submitted level into the editor session. True on a route that
    ran and reported failure -> (False, None); raises only when NO route is
    available at all (the unspiked-API case)."""
    errors = []
    try:
        les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    except Exception as e:  # noqa: BLE001
        les = None
        errors.append(repr(e))
    if les is not None and getattr(les, "load_level", None) is not None:
        try:
            return bool(les.load_level(ASSET_LEVEL))
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))
    lib = getattr(unreal, "EditorLoadingAndSavingUtils", None)
    if lib is not None and getattr(lib, "load_map", None) is not None:
        try:
            world = lib.load_map(ASSET_LEVEL)
            return world is not None
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))
    legacy = getattr(unreal, "EditorLevelLibrary", None)
    if legacy is not None and getattr(legacy, "load_level", None) is not None:
        try:
            return bool(legacy.load_level(ASSET_LEVEL))
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))
    raise RuntimeError("no level-load route: %s" % errors)


def _all_level_actors():
    try:
        eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    except Exception:  # noqa: BLE001
        eas = None
    if eas is not None and getattr(eas, "get_all_level_actors", None):
        return list(eas.get_all_level_actors() or [])
    legacy = getattr(unreal, "EditorLevelLibrary", None)
    if legacy is not None and getattr(legacy, "get_all_level_actors", None):
        return list(legacy.get_all_level_actors() or [])
    raise RuntimeError("no actor-enumeration route")


def _is_instance_of(actor, gen_cls):
    """Is this placed actor an instance of the submitted class (or a subclass
    of it)? True/False, raises when no route can decide."""
    cls = actor.get_class()
    lib = getattr(unreal, "MathLibrary", None)
    if lib is not None and getattr(lib, "class_is_child_of", None) is not None:
        try:
            return bool(lib.class_is_child_of(cls, gen_cls))
        except Exception:  # noqa: BLE001 - fall through to the exact compare
            pass
    # Exact-class fallback: loses subclass tolerance (accepted residual,
    # notes.md) but never passes on an unevaluable probe.
    return str(cls.get_path_name()) == str(gen_cls.get_path_name())


def _location_of(actor):
    loc = actor.get_actor_location()
    return (float(loc.x), float(loc.y), float(loc.z))


def _near(a, b, tol=LOCATION_TOLERANCE):
    return all(abs(a[i] - b[i]) <= tol for i in range(3))


def _fmt_loc(loc):
    return "(%.3f, %.3f, %.3f)" % loc


def _instance_check(results, cid, instances, wanted_label, wanted_location,
                    tmpl_missing, tmpl_dup, tmpl_wrong, tmpl_ok):
    """One labeled-instance gate. The templates arrive as WHOLE single
    literals from the call site (greppable token+key heads):
      tmpl_missing % (labels, wanted)   tmpl_dup % (labels,)
      tmpl_wrong % (loc, expected)      tmpl_ok % (loc,)
    """
    labels = sorted(label for label, _ in instances)
    found = [loc for label, loc in instances if label == wanted_label]
    if not found:
        results[cid] = check(cid, False, tmpl_missing % (labels, wanted_label))
        return
    if len(found) > 1:
        results[cid] = check(cid, False, tmpl_dup % (labels,))
        return
    loc = found[0]
    ok = _near(loc, wanted_location)
    results[cid] = check(
        cid, ok,
        (tmpl_ok % (_fmt_loc(loc),)) if ok
        else (tmpl_wrong % (_fmt_loc(loc), _fmt_loc(wanted_location))))


def _level_checks(results, asset_truth):
    """Fill the 5 level checks; return [(label, (x, y, z))] or (None, cause)."""
    root_cause = None
    try:
        level_exists = bool(
            unreal.EditorAssetLibrary.does_asset_exist(ASSET_LEVEL))
    except Exception as e:  # noqa: BLE001
        root_cause = "AUDIT_LEVEL_PROBE_ERROR path=%s raised %r" % (
            ASSET_LEVEL, e)
        level_exists = False
    if not level_exists:
        if root_cause is None:
            root_cause = "AUDIT_LEVEL_MISSING path=%s" % ASSET_LEVEL
        _fanout(results, LEVEL_CHECK_IDS, root_cause)
        return None, root_cause
    results["audit_level_exists"] = check(
        "audit_level_exists", True, "AUDIT_LEVEL_OK path=%s" % ASSET_LEVEL)

    try:
        loaded = _load_level()
    except Exception as e:  # noqa: BLE001
        cause = "AUDIT_LEVEL_LOAD_PROBE_ERROR raised %r" % (e,)
        _fanout(results, LEVEL_CHECK_IDS, cause)
        return None, cause
    if not loaded:
        cause = "AUDIT_LEVEL_LOAD_FAILED path=%s" % ASSET_LEVEL
        _fanout(results, LEVEL_CHECK_IDS, cause)
        return None, cause
    results["audit_level_loads"] = check(
        "audit_level_loads", True, "AUDIT_LEVEL_LOAD_OK path=%s" % ASSET_LEVEL)

    gen_cls = asset_truth.get("gen_cls") if asset_truth else None
    if gen_cls is None:
        try:
            gen_cls = unreal.load_object(None, GEN_CLASS_PATH)
        except Exception:  # noqa: BLE001
            gen_cls = None
    if gen_cls is None:
        cause = "AUDIT_BP_CLASS_UNRESOLVED path=%s raised load_object None" % (
            ASSET_BP)
        _fanout(results, LEVEL_CHECK_IDS, cause)
        return None, cause

    try:
        actors = _all_level_actors()
        instances = []
        for actor in actors:
            if actor is None:
                continue
            if _is_instance_of(actor, gen_cls):
                instances.append((str(actor.get_actor_label()),
                                  _location_of(actor)))
    except Exception as e:  # noqa: BLE001
        cause = "AUDIT_ACTOR_WALK_ERROR raised %r" % (e,)
        _fanout(results, LEVEL_CHECK_IDS, cause)
        return None, cause

    labels = sorted(label for label, _ in instances)
    count_ok = len(instances) == EXPECTED_INSTANCE_COUNT
    results["audit_instances_exactly_two"] = check(
        "audit_instances_exactly_two", count_ok,
        ("AUDIT_INSTANCE_COUNT_OK count=%d labels=%s"
         % (len(instances), labels)) if count_ok
        else ("AUDIT_INSTANCE_COUNT_WRONG count=%d expected=2 labels=%s"
              % (len(instances), labels)))

    _instance_check(
        results, "audit_alpha_instance_placed", instances,
        ALPHA_LABEL, ALPHA_LOCATION,
        "AUDIT_ALPHA_MISSING labels=%s wanted=%s",
        "AUDIT_ALPHA_DUPLICATE_LABEL labels=%s",
        "AUDIT_ALPHA_WRONG_LOCATION location=%s expected=%s",
        "AUDIT_ALPHA_PLACED_OK location=%s")
    _instance_check(
        results, "audit_beta_instance_placed", instances,
        BETA_LABEL, BETA_LOCATION,
        "AUDIT_BETA_MISSING labels=%s wanted=%s",
        "AUDIT_BETA_DUPLICATE_LABEL labels=%s",
        "AUDIT_BETA_WRONG_LOCATION location=%s expected=%s",
        "AUDIT_BETA_PLACED_OK location=%s")
    return instances, None


# --------------------------------------------------------------------------- #
# group 3: the report checks (7 results; cross-checked against groups 1+2)     #
# --------------------------------------------------------------------------- #

def _parse_report(text):
    """(parsed, None) or (None, failure_detail). Strict grammar, order-free.

    parsed = {"class": (name, parent), "components": {name: class},
              "variables": {name: type}, "compile": status,
              "instances": {label: (x, y, z)}}
    """
    parsed = {"class": None, "components": {}, "variables": {},
              "compile": None, "instances": {}}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = RE_CLASS.match(line)
        if m:
            if parsed["class"] is not None:
                return None, ("REPORT_GRAMMAR_BAD line=%r reason=%s"
                              % (line, "duplicate_class_line"))
            parsed["class"] = (m.group(1), m.group(2))
            continue
        m = RE_COMPONENT.match(line)
        if m:
            if m.group(1) in parsed["components"]:
                return None, ("REPORT_GRAMMAR_BAD line=%r reason=%s"
                              % (line, "duplicate_component_name"))
            parsed["components"][m.group(1)] = m.group(2)
            continue
        m = RE_VARIABLE.match(line)
        if m:
            if m.group(1) in parsed["variables"]:
                return None, ("REPORT_GRAMMAR_BAD line=%r reason=%s"
                              % (line, "duplicate_variable_name"))
            parsed["variables"][m.group(1)] = m.group(2)
            continue
        m = RE_COMPILE.match(line)
        if m:
            if parsed["compile"] is not None:
                return None, ("REPORT_GRAMMAR_BAD line=%r reason=%s"
                              % (line, "duplicate_compile_line"))
            parsed["compile"] = m.group(1)
            continue
        m = RE_INSTANCE.match(line)
        if m:
            if m.group(1) in parsed["instances"]:
                return None, ("REPORT_GRAMMAR_BAD line=%r reason=%s"
                              % (line, "duplicate_instance_label"))
            parsed["instances"][m.group(1)] = (float(m.group(2)),
                                               float(m.group(3)),
                                               float(m.group(4)))
            continue
        return None, ("REPORT_GRAMMAR_BAD line=%r reason=%s"
                      % (line, "unrecognized_line"))
    if parsed["class"] is None:
        return None, ("REPORT_GRAMMAR_BAD line=%r reason=%s"
                      % ("", "missing_class_line"))
    if parsed["compile"] is None:
        return None, ("REPORT_GRAMMAR_BAD line=%r reason=%s"
                      % ("", "missing_compile_line"))
    return parsed, None


def _report_checks(results, asset_truth, level_truth, level_fail):
    path = None
    try:
        path = _report_path()
        present = os.path.isfile(path)
    except Exception as e:  # noqa: BLE001
        cause = "REPORT_PROBE_ERROR raised %r" % (e,)
        _fanout(results, REPORT_CHECK_IDS, cause)
        return
    if not present:
        cause = "REPORT_FILE_MISSING path=%s" % REPORT_REL
        _fanout(results, REPORT_CHECK_IDS, cause)
        return
    results["report_file_present"] = check(
        "report_file_present", True, "REPORT_FILE_OK path=%s" % REPORT_REL)

    try:
        text = _read_text(path)
    except Exception as e:  # noqa: BLE001
        cause = "REPORT_READ_ERROR raised %r" % (e,)
        _fanout(results, REPORT_CHECK_IDS, cause)
        return
    parsed, parse_fail = _parse_report(text)
    if parsed is None:
        results["report_grammar_parses"] = check(
            "report_grammar_parses", False, parse_fail)
        _fanout(results, REPORT_CHECK_IDS, parse_fail)
        return
    results["report_grammar_parses"] = check(
        "report_grammar_parses", True,
        "REPORT_GRAMMAR_OK components=%d variables=%d instances=%d"
        % (len(parsed["components"]), len(parsed["variables"]),
           len(parsed["instances"])))

    # --- class line ----------------------------------------------------------
    reported_name, reported_parent = parsed["class"]
    if reported_name != BP_NAME:
        results["report_class_line_truthful"] = check(
            "report_class_line_truthful", False,
            "REPORT_CLASS_NAME_MISMATCH reported=%s expected=%s"
            % (reported_name, BP_NAME))
    elif asset_truth is None or asset_truth["parent_name"] is None:
        results["report_class_line_truthful"] = check(
            "report_class_line_truthful", False,
            asset_truth["parent_fail"] if asset_truth else
            "AUDIT_BP_MISSING path=%s" % ASSET_BP)
    else:
        actual = asset_truth["parent_name"]
        ok = reported_parent == actual
        results["report_class_line_truthful"] = check(
            "report_class_line_truthful", ok,
            ("REPORT_CLASS_LINE_OK parent=%s" % actual) if ok
            else ("REPORT_PARENT_MISMATCH reported=%s actual=%s"
                  % (reported_parent, actual)))

    # --- component lines: set equality against the SCS walk ------------------
    if asset_truth is None or asset_truth["components"] is None:
        results["report_component_lines_truthful"] = check(
            "report_component_lines_truthful", False,
            asset_truth["components_fail"] if asset_truth else
            "AUDIT_BP_MISSING path=%s" % ASSET_BP)
    else:
        actual_set = set(asset_truth["components"])
        reported_set = set(parsed["components"].items())
        reported_only = sorted(reported_set - actual_set)
        actual_only = sorted(actual_set - reported_set)
        ok = not reported_only and not actual_only
        results["report_component_lines_truthful"] = check(
            "report_component_lines_truthful", ok,
            ("REPORT_COMPONENT_LINES_OK count=%d" % len(actual_set)) if ok
            else ("REPORT_COMPONENTS_MISMATCH reported_only=%s actual_only=%s"
                  % (reported_only, actual_only)))

    # --- variable lines ------------------------------------------------------
    problems = []
    reported_vars = dict(parsed["variables"])
    cdo = asset_truth.get("cdo") if asset_truth else None
    for name, kind_key, fail_key in ((FLAG_NAME, "flag_kind", "flag_fail"),
                                     (SCORE_NAME, "score_kind", "score_fail")):
        reported_kind = reported_vars.pop(name, None)
        if reported_kind is None:
            problems.append("required variable %s not reported" % name)
            continue
        actual_kind = asset_truth.get(kind_key) if asset_truth else None
        if actual_kind is None:
            problems.append("%s unresolvable on the asset: %s"
                            % (name, (asset_truth or {}).get(fail_key)))
        elif reported_kind != actual_kind:
            problems.append("%s reported type %s actual %s"
                            % (name, reported_kind, actual_kind))
    for name, reported_kind in sorted(reported_vars.items()):
        if cdo is None:
            problems.append("extra variable %s unverifiable (no CDO)" % name)
            continue
        try:
            value = _read_property(cdo, name)
        except Exception:  # noqa: BLE001
            problems.append("reported variable %s does not exist" % name)
            continue
        if isinstance(value, bool):
            actual_kind = "bool"
        elif isinstance(value, (int, float)):
            actual_kind = "float"
        else:
            actual_kind = type(value).__name__
        if reported_kind != actual_kind:
            problems.append("%s reported type %s actual %s"
                            % (name, reported_kind, actual_kind))
    results["report_variable_lines_truthful"] = check(
        "report_variable_lines_truthful", not problems,
        ("REPORT_VARIABLE_LINES_OK count=%d" % len(parsed["variables"]))
        if not problems
        else ("REPORT_VARIABLES_MISMATCH problems=%s" % problems[:4]))

    # --- compile line --------------------------------------------------------
    if asset_truth is None or asset_truth["compile_clean"] is None:
        results["report_compile_line_truthful"] = check(
            "report_compile_line_truthful", False,
            asset_truth["compile_fail"] if asset_truth else
            "AUDIT_BP_MISSING path=%s" % ASSET_BP)
    else:
        actual_clean = bool(asset_truth["compile_clean"])
        ok = parsed["compile"] == COMPILE_CLEAN_TOKEN and actual_clean
        results["report_compile_line_truthful"] = check(
            "report_compile_line_truthful", ok,
            ("REPORT_COMPILE_LINE_OK status=%s" % parsed["compile"]) if ok
            else ("REPORT_COMPILE_MISMATCH reported=%s actual_clean=%s"
                  % (parsed["compile"], actual_clean)))

    # --- instance lines: set equality + per-label location truth -------------
    if level_truth is None:
        results["report_instance_lines_truthful"] = check(
            "report_instance_lines_truthful", False,
            level_fail or ("AUDIT_LEVEL_MISSING path=%s" % ASSET_LEVEL))
        return
    actual_by_label = {}
    duplicate = None
    for label, loc in level_truth:
        if label in actual_by_label:
            duplicate = label
        actual_by_label[label] = loc
    if duplicate is not None:
        results["report_instance_lines_truthful"] = check(
            "report_instance_lines_truthful", False,
            "AUDIT_DUPLICATE_INSTANCE_LABEL label=%s" % duplicate)
        return
    reported_only = sorted(set(parsed["instances"]) - set(actual_by_label))
    actual_only = sorted(set(actual_by_label) - set(parsed["instances"]))
    loc_problems = []
    for label in sorted(set(parsed["instances"]) & set(actual_by_label)):
        if not _near(parsed["instances"][label], actual_by_label[label]):
            loc_problems.append(
                "%s reported %s actual %s"
                % (label, _fmt_loc(parsed["instances"][label]),
                   _fmt_loc(actual_by_label[label])))
    ok = not reported_only and not actual_only and not loc_problems
    results["report_instance_lines_truthful"] = check(
        "report_instance_lines_truthful", ok,
        ("REPORT_INSTANCE_LINES_OK count=%d" % len(actual_by_label)) if ok
        else ("REPORT_INSTANCES_MISMATCH reported_only=%s actual_only=%s "
              "location_problems=%s"
              % (reported_only, actual_only, loc_problems[:3])))


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #

def main():
    results = {}
    asset_truth = None
    level_truth, level_fail = None, None
    try:
        asset_truth = _asset_checks(results)
    except Exception as e:  # noqa: BLE001 - never abort the verdict
        _fanout(results, ASSET_CHECK_IDS,
                "AUDIT_INTROSPECTION_ABORTED raised %r" % (e,))
    try:
        level_truth, level_fail = _level_checks(results, asset_truth)
    except Exception as e:  # noqa: BLE001
        level_fail = "AUDIT_INTROSPECTION_ABORTED raised %r" % (e,)
        _fanout(results, LEVEL_CHECK_IDS, level_fail)
    try:
        _report_checks(results, asset_truth, level_truth, level_fail)
    except Exception as e:  # noqa: BLE001
        _fanout(results, REPORT_CHECK_IDS,
                "REPORT_INTROSPECTION_ABORTED raised %r" % (e,))

    checks = [results.get(cid) or check(cid, False,
                                        "CHECK_NOT_EVALUATED id=%s" % cid)
              for cid in CHECK_IDS]
    emit_verdict(checks)


if __name__ == "__main__":
    main()
