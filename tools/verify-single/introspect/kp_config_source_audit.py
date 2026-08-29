"""L2-introspect script for the kp-config-source-audit task (python basket).

Structural, READ-ONLY verification of ONE agent-written text report plus a
CORPUS-UNMODIFIED GUARD over the task's committed baseline assets, via stock
UE editor-Python. Emits one CRAFTBENCH-INTROSPECT-JSON block the
L2-introspect layer parses (``layers/l2_introspect.py``; contract:
``layers/INTROSPECT_CONTRACT.md``).

What is graded (seed row "Data asset read ability set", adapted off the
nonexistent Lyra substrate; see the task spec):

  1. GUARD  - the committed corpus: four config-carrier Blueprint assets
     under ``/Game/Tasks/kp-config-source-audit/corpus/`` (each holding one
     brightness float on a light part named ``Glow``) and ONE wiring
     artifact ``/Game/Tasks/kp-config-source-audit/wiring/BP_DashRig`` (whose
     slot ``FlashSlot`` instantiates exactly one corpus class). All of it is
     verifier-authored and committed as substrate baseline, but it lives
     under the agent-writable ``Content/Tasks/`` prefix, so the sandbox
     CANNOT protect it - this guard is the defense. Every corpus fact is
     re-asserted against the pinned constants below; any drift FAILS with a
     named ``CORPUS_MODIFIED_*`` / ``CORPUS_SET_CHANGED`` message. The task
     is DIAGNOSIS: the only thing the agent legitimately writes is the
     report file.
  2. REPORT - ``Content/Tasks/kp-config-source-audit/reports/config.txt``: a
     strict two-line report naming WHICH corpus asset is the live source of
     the dash-flash brightness and THAT brightness. Cross-checked two ways:
     against the pinned constants AND against a fresh live trace of the
     wiring (slot class -> corpus asset -> stored value), so the answer can
     neither be transcribed from the prompt (neither the winner nor any
     value appears in any agent-visible surface) nor drift from what is
     actually wired.

The gold-leak defense (datatable_csv_export.py precedent): every EXPECTED
value (the four corpus names, the four brightness values, the live asset
path, the live class path, the slot and part names) is PINNED in this
file's constants. Nothing expected is ever read from a place the agent can
write; the live-wiring cross-check only ever ADDS the requirement "the
report tells the truth about what is wired".

Hard rules honoured here:
  * READ-ONLY. Nothing below mutates an asset, a package, or the project.
  * Identity by pre-declared content PATH, subobject NAME and property
    NAME - never by class scanning. Class is consulted only as an
    ASSERTION (subclass-tolerant where a route allows it).
  * Stock UE Python only. Never Aura's MCP tools - that would grade Aura
    with Aura.
  * Every check wrapped in its own try/except: one wrong API name degrades
    to exactly one FAILED check with the exception in ``detail``.
  * FAIL CLOSED. No check passes because a probe did not raise. An empty or
    missing submission fails every REPORT check with one named root cause
    (the guard checks pass on the empty leg by design - the baseline is
    intact - so the empty submission scores 7/12 and FAILs overall via
    ``report_file_present``). A failed prerequisite fans its own root-cause
    token into the dependent checks.
  * The check list has a CONSTANT length (12) on every leg. ``registry.py``
    reports ``tests_passed/tests_run`` from these counts.

Detail strings are stable, ASCII-ONLY, greppable tokens; each meaningful
token+key literal lives in ONE string literal (never split across
concatenations) so the MATRIX oracle can grep it from source. Error tokens
(``*_PROBE_ERROR`` / ``*_READ_ERROR`` / ``*_WALK_ERROR`` / ``*_ABORTED`` /
``CHECK_NOT_EVALUATED``) are disjoint from graded failure tokens and appear
in no MATRIX row, so a broken UE API name can never be credited as a named
assertion. No detail contains either automation result marker; neither
marker substring appears anywhere in this file.

UE 5.8 API notes (routes and their provenance):
  * Existence   - ``unreal.EditorAssetLibrary.does_asset_exist`` (proven).
  * Enumeration - ``unreal.EditorAssetLibrary.list_assets`` (object paths;
    normalized to package paths here).
  * SCS walk    - ``unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)``
    + ``SubobjectDataBlueprintFunctionLibrary`` (proven live by the
    dawn-fog, flashlight and audit-report tasks; ENGINE subsystem,
    get_editor_subsystem raises).
  * Value reads - the light template's ``intensity`` property and the slot
    template's ``child_actor_class`` property via ``get_editor_property``
    with underscore-folded + authored spellings tried in order. NO CDO read
    anywhere (none is needed: every graded value lives on an SCS component
    template), so the ``get_default_object`` foot-gun cannot arise. NO read
    of any protected reflection property (no UbergraphPages, no pin walks).
  * Class match - the slot's class is compared by exact object path against
    the pinned generated-class path; the report's asset path is normalized
    (``/pkg/Name.Name`` -> ``/pkg/Name``) before the exact compare.
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
TASK_ID = "kp-config-source-audit"
CORPUS_DIR = "/Game/Tasks/%s/corpus" % TASK_ID
WIRING_BP = "/Game/Tasks/%s/wiring/BP_DashRig" % TASK_ID
SLOT_NAME = "FlashSlot"
GLOW_NAME = "Glow"
REPORT_REL = "Content/Tasks/%s/reports/config.txt" % TASK_ID

# --- Pinned expected values (the agent may not change any of these) ----------
# The names are DELIBERATELY deceptive: the live one is the "archive", the
# plausible-sounding ones are decoys referenced by nothing. Every value is
# far from a fresh point light's default intensity (5000.0), so an untouched
# or freshly authored impostor can never satisfy a value gate by accident.
LIVE_NAME = "Flash_Archive_2024"
LIVE_VALUE = 725.0
LIVE_ASSET = "%s/%s" % (CORPUS_DIR, LIVE_NAME)
LIVE_CLASS_PATH = "%s.%s_C" % (LIVE_ASSET, LIVE_NAME)
VALUE_TOL = 1e-3

CORPUS_SPECS = (
    ("corpus_primary_intact", "Flash_Primary", 1450.0),
    ("corpus_current_intact", "Flash_Current", 950.0),
    ("corpus_archive_intact", LIVE_NAME, LIVE_VALUE),
    ("corpus_testflash_intact", "Flash_Test_DoNotUse", 1200.0),
)
CORPUS_NAMES = tuple(name for _cid, name, _val in CORPUS_SPECS)

# --- The check ids, grouped; total length is the score denominator (12). -----
GUARD_CHECK_IDS = (
    ("corpus_set_exact",)
    + tuple(cid for cid, _name, _val in CORPUS_SPECS)
    + ("wiring_rig_present", "wiring_slot_intact")
)
REPORT_CHECK_IDS = (
    "report_file_present",
    "report_grammar_parses",
    "report_source_is_live_asset",
    "report_value_is_live_value",
    "report_agrees_with_wiring",
)
CHECK_IDS = GUARD_CHECK_IDS + REPORT_CHECK_IDS

# --- Report grammar (disclosed verbatim in the agent prompt) -----------------
RE_SOURCE = re.compile(r"^source asset=(\S+)$")
RE_VALUE = re.compile(r"^value brightness=(-?\d+(?:\.\d+)?)$")


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
    """First readable spelling of a property; re-raises if none reads."""
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
                        "config.txt")


def _read_text(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _normalize_pkg(path):
    """``/pkg/Name.Name`` -> ``/pkg/Name``; anything else unchanged.

    The one deliberate tolerance of this grader: a reported object path
    whose object name repeats the package tail collapses to the package
    path before the exact compare (recorded in the task spec's accepted
    residuals). Never widens further.
    """
    p = str(path).strip()
    if "." in p:
        pkg, _dot, obj = p.partition(".")
        if obj == pkg.rsplit("/", 1)[-1]:
            return pkg
    return p


# --------------------------------------------------------------------------- #
# SCS component walk (template objects; no CDO anywhere)                       #
# --------------------------------------------------------------------------- #

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
    component) is excluded. FAIL-CLOSED: raises rather than returning an
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


# --------------------------------------------------------------------------- #
# shared truth read: one corpus asset's Glow brightness (fail-closed)          #
# --------------------------------------------------------------------------- #

def _read_glow(asset_path):
    """(value, None) or (None, fail_detail) for one corpus asset.

    Graded tokens (CORPUS_ASSET_MISSING / CORPUS_MODIFIED_PARTS /
    CORPUS_MODIFIED_PART_TYPE) are disjoint from error tokens
    (CORPUS_PROBE_ERROR / CORPUS_WALK_ERROR / CORPUS_TYPE_PROBE_ERROR /
    CORPUS_VALUE_READ_ERROR); only graded tokens may appear in MATRIX rows.
    """
    try:
        exists = bool(unreal.EditorAssetLibrary.does_asset_exist(asset_path))
    except Exception as e:  # noqa: BLE001
        return None, "CORPUS_PROBE_ERROR asset=%s raised %r" % (asset_path, e)
    if not exists:
        return None, "CORPUS_ASSET_MISSING path=%s" % asset_path
    try:
        bp = unreal.EditorAssetLibrary.load_asset(asset_path)
        if bp is None:
            raise RuntimeError("load_asset returned None")
        components = _scene_components(bp)
    except Exception as e:  # noqa: BLE001
        return None, "CORPUS_WALK_ERROR asset=%s raised %r" % (asset_path, e)
    names = sorted(n for n, _obj in components if n)
    glow = None
    for got, obj in components:
        if got == GLOW_NAME:
            glow = obj
            break
    if glow is None:
        return None, ("CORPUS_MODIFIED_PARTS asset=%s names=%s wanted=Glow"
                      % (asset_path, names))
    verdict = _isinstance_tristate(glow, "PointLightComponent")
    if verdict is None:
        return None, ("CORPUS_TYPE_PROBE_ERROR asset=%s class=%s"
                      % (asset_path, _class_name(glow)))
    if not verdict:
        return None, ("CORPUS_MODIFIED_PART_TYPE asset=%s class=%s "
                      "expected=PointLightComponent"
                      % (asset_path, _class_name(glow)))
    try:
        value = float(_read_property(glow, "intensity", "Intensity"))
    except Exception as e:  # noqa: BLE001
        return None, ("CORPUS_VALUE_READ_ERROR asset=%s raised %r"
                      % (asset_path, e))
    return value, None


# --------------------------------------------------------------------------- #
# group 1a: the corpus guard (5 checks)                                        #
# --------------------------------------------------------------------------- #

def _corpus_set_check(results):
    """The corpus folder contains EXACTLY the four pre-declared assets."""
    cid = "corpus_set_exact"
    try:
        listed = list(unreal.EditorAssetLibrary.list_assets(
            CORPUS_DIR, recursive=True, include_folder=False) or [])
    except Exception as e:  # noqa: BLE001
        results[cid] = check(cid, False,
                             "CORPUS_SET_PROBE_ERROR raised %r" % (e,))
        return
    found = sorted(set(
        _normalize_pkg(str(p)).rsplit("/", 1)[-1] for p in listed))
    expected = sorted(CORPUS_NAMES)
    ok = found == expected
    results[cid] = check(
        cid, ok,
        ("CORPUS_SET_OK count=4 names=%s" % found) if ok
        else ("CORPUS_SET_CHANGED found=%s expected=%s" % (found, expected)))


def _corpus_checks(results):
    """Fill the 5 corpus guard checks; return {asset_path: value} truth."""
    _corpus_set_check(results)
    truth = {}
    for cid, name, expected in CORPUS_SPECS:
        asset_path = "%s/%s" % (CORPUS_DIR, name)
        value, fail = _read_glow(asset_path)
        if value is None:
            results[cid] = check(cid, False, fail)
            continue
        truth[asset_path] = value
        ok = abs(value - expected) <= VALUE_TOL
        results[cid] = check(
            cid, ok,
            ("CORPUS_ASSET_OK asset=%s value=%s" % (asset_path, value)) if ok
            else ("CORPUS_MODIFIED_VALUE asset=%s got=%s expected=%s"
                  % (asset_path, value, expected)))
    return truth


# --------------------------------------------------------------------------- #
# group 1b: the wiring guard (2 checks; returns the live trace for group 2)    #
# --------------------------------------------------------------------------- #

def _wiring_checks(results):
    """Fill the 2 wiring checks.

    Returns (slot_class_path or None, fail_detail). The slot class path is
    returned whenever it is READABLE - even when it fails the guard (a
    rewired slot) - because group 2's agrees-with-wiring check compares the
    report against whatever is actually wired, while the guard here pins
    what SHOULD be wired.
    """
    root_cause = None
    try:
        exists = bool(unreal.EditorAssetLibrary.does_asset_exist(WIRING_BP))
    except Exception as e:  # noqa: BLE001
        root_cause = "WIRING_PROBE_ERROR raised %r" % (e,)
        exists = False
    if not exists:
        if root_cause is None:
            root_cause = "WIRING_RIG_MISSING path=%s" % WIRING_BP
        results["wiring_rig_present"] = check(
            "wiring_rig_present", False, root_cause)
        results["wiring_slot_intact"] = check(
            "wiring_slot_intact", False, root_cause)
        return None, root_cause
    results["wiring_rig_present"] = check(
        "wiring_rig_present", True, "WIRING_RIG_OK path=%s" % WIRING_BP)

    try:
        bp = unreal.EditorAssetLibrary.load_asset(WIRING_BP)
        if bp is None:
            raise RuntimeError("load_asset returned None")
        components = _scene_components(bp)
    except Exception as e:  # noqa: BLE001
        detail = "WIRING_WALK_ERROR raised %r" % (e,)
        results["wiring_slot_intact"] = check(
            "wiring_slot_intact", False, detail)
        return None, detail
    names = sorted(n for n, _obj in components if n)
    slot = None
    for got, obj in components:
        if got == SLOT_NAME:
            slot = obj
            break
    if slot is None:
        detail = ("CORPUS_MODIFIED_WIRING names=%s wanted=FlashSlot" % names)
        results["wiring_slot_intact"] = check(
            "wiring_slot_intact", False, detail)
        return None, detail
    try:
        cls = _read_property(slot, "child_actor_class", "ChildActorClass")
    except Exception as e:  # noqa: BLE001
        detail = "WIRING_CLASS_READ_ERROR raised %r" % (e,)
        results["wiring_slot_intact"] = check(
            "wiring_slot_intact", False, detail)
        return None, detail
    cls_path = "None" if cls is None else str(cls.get_path_name())
    ok = cls_path == LIVE_CLASS_PATH
    results["wiring_slot_intact"] = check(
        "wiring_slot_intact", ok,
        ("WIRING_SLOT_OK slot_class=%s" % cls_path) if ok
        else ("CORPUS_MODIFIED_WIRING_CLASS slot_class=%s expected=%s"
              % (cls_path, LIVE_CLASS_PATH)))
    if cls is None:
        return None, results["wiring_slot_intact"]["detail"]
    return cls_path, None


# --------------------------------------------------------------------------- #
# group 2: the report checks (5 checks; cross-checked against pins + wiring)   #
# --------------------------------------------------------------------------- #

def _grammar_bad(line, reason):
    return "CONFIG_GRAMMAR_BAD line=%r reason=%s" % (line, reason)


def _parse_report(text):
    """(source, value, None) or (None, None, failure_detail). Strict grammar:
    exactly one source line and one value line, blank lines ignored, order
    free, nothing else accepted."""
    source = None
    value = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = RE_SOURCE.match(line)
        if m:
            if source is not None:
                return None, None, _grammar_bad(line, "duplicate_source_line")
            source = m.group(1)
            continue
        m = RE_VALUE.match(line)
        if m:
            if value is not None:
                return None, None, _grammar_bad(line, "duplicate_value_line")
            value = float(m.group(1))
            continue
        return None, None, _grammar_bad(line, "unrecognized_line")
    if source is None:
        return None, None, _grammar_bad("", "missing_source_line")
    if value is None:
        return None, None, _grammar_bad("", "missing_value_line")
    return source, value, None


def _report_checks(results, corpus_truth, slot_class_path, wiring_fail):
    try:
        path = _report_path()
        present = os.path.isfile(path)
    except Exception as e:  # noqa: BLE001
        cause = "CONFIG_REPORT_PROBE_ERROR raised %r" % (e,)
        _fanout(results, REPORT_CHECK_IDS, cause)
        return
    if not present:
        cause = "CONFIG_REPORT_MISSING path=%s" % REPORT_REL
        _fanout(results, REPORT_CHECK_IDS, cause)
        return
    results["report_file_present"] = check(
        "report_file_present", True, "CONFIG_REPORT_OK path=%s" % REPORT_REL)

    try:
        text = _read_text(path)
    except Exception as e:  # noqa: BLE001
        cause = "CONFIG_REPORT_READ_ERROR raised %r" % (e,)
        _fanout(results, REPORT_CHECK_IDS, cause)
        return
    source, value, parse_fail = _parse_report(text)
    if source is None:
        results["report_grammar_parses"] = check(
            "report_grammar_parses", False, parse_fail)
        _fanout(results, REPORT_CHECK_IDS, parse_fail)
        return
    results["report_grammar_parses"] = check(
        "report_grammar_parses", True,
        "CONFIG_GRAMMAR_OK source=%s value=%s" % (source, value))

    # --- pinned-constant cross-checks ----------------------------------------
    reported_pkg = _normalize_pkg(source)
    ok = reported_pkg == LIVE_ASSET
    results["report_source_is_live_asset"] = check(
        "report_source_is_live_asset", ok,
        ("CONFIG_SOURCE_OK asset=%s" % reported_pkg) if ok
        else ("CONFIG_SOURCE_WRONG reported=%s expected=%s"
              % (reported_pkg, LIVE_ASSET)))

    ok = abs(value - LIVE_VALUE) <= VALUE_TOL
    results["report_value_is_live_value"] = check(
        "report_value_is_live_value", ok,
        ("CONFIG_VALUE_OK value=%s" % value) if ok
        else ("CONFIG_VALUE_WRONG reported=%s expected=%s"
              % (value, LIVE_VALUE)))

    # --- live-wiring cross-check ---------------------------------------------
    if slot_class_path is None:
        results["report_agrees_with_wiring"] = check(
            "report_agrees_with_wiring", False,
            wiring_fail or ("WIRING_RIG_MISSING path=%s" % WIRING_BP))
        return
    live_pkg = slot_class_path.split(".")[0]
    live_value = corpus_truth.get(live_pkg)
    if live_value is None:
        live_value, glow_fail = _read_glow(live_pkg)
    else:
        glow_fail = None
    if live_value is None:
        results["report_agrees_with_wiring"] = check(
            "report_agrees_with_wiring", False, glow_fail)
        return
    ok = (reported_pkg == live_pkg
          and abs(value - live_value) <= VALUE_TOL)
    results["report_agrees_with_wiring"] = check(
        "report_agrees_with_wiring", ok,
        ("CONFIG_WIRING_AGREES asset=%s value=%s" % (live_pkg, live_value))
        if ok else
        ("CONFIG_WIRING_DISAGREES reported_asset=%s reported_value=%s "
         "live_asset=%s live_value=%s"
         % (reported_pkg, value, live_pkg, live_value)))


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #

def main():
    results = {}
    corpus_truth = {}
    slot_class_path, wiring_fail = None, None
    try:
        corpus_truth = _corpus_checks(results)
    except Exception as e:  # noqa: BLE001 - never abort the verdict
        _fanout(results, GUARD_CHECK_IDS,
                "CFGAUDIT_INTROSPECTION_ABORTED raised %r" % (e,))
    try:
        slot_class_path, wiring_fail = _wiring_checks(results)
    except Exception as e:  # noqa: BLE001
        wiring_fail = "CFGAUDIT_INTROSPECTION_ABORTED raised %r" % (e,)
        _fanout(results, ("wiring_rig_present", "wiring_slot_intact"),
                wiring_fail)
    try:
        _report_checks(results, corpus_truth, slot_class_path, wiring_fail)
    except Exception as e:  # noqa: BLE001
        _fanout(results, REPORT_CHECK_IDS,
                "CFGAUDIT_INTROSPECTION_ABORTED raised %r" % (e,))

    checks = [results.get(cid) or check(cid, False,
                                        "CHECK_NOT_EVALUATED id=%s" % cid)
              for cid in CHECK_IDS]
    emit_verdict(checks)


if __name__ == "__main__":
    main()
