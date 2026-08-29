"""L2-introspect script for the kp-derived-class-search task (python basket).

Structural, READ-ONLY verification of ONE submitted text report against a
VERIFIER-AUTHORED Blueprint corpus, via stock UE editor-Python. Emits one
CRAFTBENCH-INTROSPECT-JSON block the L2-introspect layer parses
(``layers/l2_introspect.py``; contract: ``layers/INTROSPECT_CONTRACT.md``).

What is graded (seed roster Block A row R14, sheet name ``t13-asset-search``,
category *Usage Search*; see the task spec):

  * CORPUS GUARD - the five verifier-authored Blueprints under
    ``/Game/Tasks/kp-derived-class-search/corpus/`` are exactly as
    shipped: the on-disk file set is exactly the five committed ``.uasset``
    names, the stated base is still a placeable actor class, the two true
    derivations still hold (``BP_DrillRig`` derives from ``BP_MachineBase``;
    ``BP_HeavyDrillRig`` derives from ``BP_DrillRig``, hence transitively
    from the base), and the two red herrings are still NOT derived from the
    base (``BP_MachineBaseplate`` - the name-stem herring; ``BP_ScoutRig`` -
    the suffix herring). Any drift FAILs with a named ``CORPUS_MODIFIED_*``
    message: the corpus is inside the agent-writable ``Content/Tasks/``
    prefix, so "do not modify the corpus" must be a GATE, not a request.
  * REPORT - ``Content/Tasks/kp-derived-class-search/reports/derived.txt``:
    a strict-grammar plain-text listing of exactly the corpus Blueprints that
    derive (directly or transitively) from ``BP_MachineBase``, each with its
    DIRECT parent. Graded by set equality in both directions against
    VERIFIER-OWNED expected constants - a listed herring fails, an omitted
    transitive child fails, a flat-parent line (naming the far ancestor
    instead of the direct base) fails.

The gold-leak defense (usage-search family; datatable_csv_export.py
precedent): every EXPECTED value (the five corpus names, the derivation
facts, the two expected report pairs) is PINNED in this file's constants.
Nothing expected is ever recomputed from state the agent can write - the
corpus guard asserts the live corpus still MATCHES the pins, and the report
is graded against the pins, so tampering with the corpus can never move the
bar; it can only add a named guard failure.

Hard rules honoured here:
  * READ-ONLY. Nothing below mutates an asset, a package, or the project.
    No level is loaded (the deliverable is a text file; the corpus is
    class assets only).
  * Identity by pre-declared content path and asset NAME, never by class
    scanning. Class relationships are consulted only as ASSERTIONS, via
    ``unreal.MathLibrary.class_is_child_of`` (the route the audit task's
    refgate proved live 2026-08-12).
  * CDO access is ``unreal.get_default_object(cls)`` ONLY - calling
    ``cls.get_default_object()`` on a class instance resolves against the
    instance's own class and returns a poisoned object (refgate catch
    2026-08-12; see kp_blueprint_actor_audit_report.py::_default_object).
  * No protected reflection reads (no UbergraphPages, no EdGraphPinType pin
    properties, no ``new_variables`` walk) - derivation is read off the
    generated-class hierarchy, which is public reflection.
  * Stock UE Python only. Never Aura's MCP tools - that would grade Aura
    with Aura.
  * Every check wrapped in its own try/except: one wrong API name degrades
    to exactly one FAILED check with the exception in ``detail``.
  * FAIL CLOSED. No check passes because a probe did not raise. A missing
    report fails all four report checks with one named root cause; an empty
    report parses but fails set equality (the expected set is non-empty by
    construction); every negative assertion (the two ``*_underived`` guards)
    is conjoined with the positive class-resolution read that produced it,
    and a failed prerequisite fans its own root-cause token into dependents.
  * The check list has a CONSTANT length (10) on every leg, including the
    empty submission. ``registry.py`` reports ``tests_passed/tests_run``
    from these counts. (The empty submission scores 6/10, not 0/10: the
    corpus is substrate baseline and its guard legitimately passes; the
    four report checks all fail via ``REPORT_FILE_MISSING`` - overall FAIL.)

Detail strings are stable, ASCII-ONLY, greppable tokens; each meaningful
token+key literal lives in ONE string constant (never split across
concatenations) so the MATRIX oracle can grep it from source. Error tokens
(``*_PROBE_ERROR`` / ``*_READ_ERROR`` / ``*_ABORTED`` /
``CHECK_NOT_EVALUATED``) are disjoint from graded failure tokens and appear
in no MATRIX row, so a broken UE API name can never be credited as a named
assertion. No detail contains either automation result marker; neither
marker substring appears anywhere in this file.

UE 5.8 API notes (routes and their provenance):
  * Corpus file-set guard - plain ``os.walk`` under the project Content dir
    (``unreal.Paths.project_content_dir``). DISK is the truth for the set
    check on purpose: it cannot lag the asset registry and it sees a
    hand-dropped foreign ``.uasset`` the registry might not have scanned.
  * Class resolution - ``unreal.load_object(None, "<pkg>.<name>_C")``
    (proven by the audit task). ``None`` on an existing file is a GRADED
    corpus-modified failure (the asset no longer carries its class); a
    raise is an uncreditable probe error.
  * Derivation - ``unreal.MathLibrary.class_is_child_of`` (proven live for
    Blueprint generated classes by the audit task's instance-identity gate).
    ``class_is_child_of(X, X)`` is True in engine semantics; every pinned
    pair here is between two DISTINCT classes, and the base itself is never
    a graded "derived" candidate.
  * CDO - ``unreal.get_default_object`` (module function; the one correct
    route, see above).
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
TASK_ID = "kp-derived-class-search"
CORPUS_DIR = "/Game/Tasks/%s/corpus" % TASK_ID
REPORT_REL = "Content/Tasks/%s/reports/derived.txt" % TASK_ID

BASE_NAME = "BP_MachineBase"
DRILL_NAME = "BP_DrillRig"
HEAVY_NAME = "BP_HeavyDrillRig"
BASEPLATE_NAME = "BP_MachineBaseplate"
SCOUT_NAME = "BP_ScoutRig"
CORPUS_NAMES = (BASE_NAME, DRILL_NAME, HEAVY_NAME, BASEPLATE_NAME, SCOUT_NAME)

# --- Pinned expected values (the agent cannot write any of these) ------------
# The report's whole truth: exactly these (name, direct-parent) pairs, no
# more, no fewer. BP_HeavyDrillRig's parent is BP_DrillRig (the DIRECT base),
# never BP_MachineBase - the flat-parent gate.
EXPECTED_DERIVED = (
    (DRILL_NAME, BASE_NAME),
    (HEAVY_NAME, DRILL_NAME),
)
EXPECTED_DERIVED_NAMES = tuple(name for name, _parent in EXPECTED_DERIVED)
# The two red herrings: similar names, NOT derived from the base.
UNDERIVED_NAMES = (BASEPLATE_NAME, SCOUT_NAME)

# --- The check ids, grouped; total length is the score denominator (10). -----
CORPUS_CHECK_IDS = (
    "corpus_set_intact",
    "corpus_base_is_placeable_class",
    "corpus_drill_derives_base",
    "corpus_heavy_derives_drill",
    "corpus_baseplate_underived",
    "corpus_scout_underived",
)
REPORT_CHECK_IDS = (
    "report_file_present",
    "report_grammar_parses",
    "report_derived_set_exact",
    "report_parent_lines_truthful",
)
CHECK_IDS = CORPUS_CHECK_IDS + REPORT_CHECK_IDS

# --- Report grammar (disclosed verbatim in the agent prompt) -----------------
RE_DERIVED = re.compile(r"^derived name=(\S+) parent=(\S+)$")


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
# small helpers                                                                #
# --------------------------------------------------------------------------- #

def _content_dir():
    raw = unreal.Paths.project_content_dir()
    try:
        full = unreal.Paths.convert_relative_path_to_full(raw)
    except Exception:  # noqa: BLE001 - older spelling; abspath is equivalent
        full = os.path.abspath(str(raw))
    return str(full)


def _corpus_disk_dir():
    return os.path.join(_content_dir(), "Tasks", TASK_ID, "corpus")


def _report_path():
    return os.path.join(_content_dir(), "Tasks", TASK_ID, "reports",
                        "derived.txt")


def _read_text(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


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


def _default_object(gen_cls):
    """The class default object, or raises.

    ONE route on purpose (refgate catch 2026-08-12, audit task): calling
    ``gen_cls.get_default_object()`` on a class INSTANCE resolves the method
    against the instance's own class and returns the CDO of
    BlueprintGeneratedClass itself - a poisoned object. The module function
    takes the class as an argument and is the correct route."""
    fn = getattr(unreal, "get_default_object", None)
    if fn is None:
        raise RuntimeError("unreal.get_default_object is not exposed")
    cdo = fn(gen_cls)
    if cdo is None:
        raise RuntimeError("class default object unavailable")
    return cdo


def _child_of(child_cls, base_cls):
    """True/False via class_is_child_of; raises when the route is missing."""
    lib = getattr(unreal, "MathLibrary", None)
    fn = getattr(lib, "class_is_child_of", None) if lib is not None else None
    if fn is None:
        raise RuntimeError("class_is_child_of is not exposed to Python")
    return bool(fn(child_cls, base_cls))


# --------------------------------------------------------------------------- #
# group 1: the corpus guard (fills 6 results)                                  #
# --------------------------------------------------------------------------- #

def _corpus_file_set_check(results):
    """Disk-truth set equality: exactly the five shipped .uasset files."""
    try:
        disk_dir = _corpus_disk_dir()
        found = []
        for root, _dirs, files in os.walk(disk_dir):
            for fname in files:
                rel = os.path.relpath(os.path.join(root, fname), disk_dir)
                found.append(rel.replace(os.sep, "/"))
        found = sorted(found)
    except Exception as e:  # noqa: BLE001
        results["corpus_set_intact"] = check(
            "corpus_set_intact", False,
            "CORPUS_LIST_PROBE_ERROR raised %r" % (e,))
        return
    expected = sorted("%s.uasset" % name for name in CORPUS_NAMES)
    ok = found == expected
    results["corpus_set_intact"] = check(
        "corpus_set_intact", ok,
        ("CORPUS_SET_OK count=%d" % len(found)) if ok
        else ("CORPUS_MODIFIED_SET files=%s expected=%s" % (found, expected)))


def _resolve_corpus_classes():
    """({name: generated_class}, {name: failure_detail}) for all five.

    A ``load_object`` that RETURNS None on a name the set check saw on disk
    is a graded corpus-modified failure (the file no longer carries its
    class); a raise is an uncreditable probe error.
    """
    classes, fails = {}, {}
    for name in CORPUS_NAMES:
        path = "%s/%s.%s_C" % (CORPUS_DIR, name, name)
        try:
            cls = unreal.load_object(None, path)
        except Exception as e:  # noqa: BLE001
            fails[name] = ("CORPUS_CLASS_PROBE_ERROR name=%s raised %r"
                           % (name, e))
            continue
        if cls is None:
            fails[name] = ("CORPUS_MODIFIED_CLASS_UNRESOLVED name=%s path=%s"
                           % (name, path))
        else:
            classes[name] = cls
    return classes, fails


def _base_class_check(results, classes, fails):
    cls = classes.get(BASE_NAME)
    if cls is None:
        results["corpus_base_is_placeable_class"] = check(
            "corpus_base_is_placeable_class", False, fails[BASE_NAME])
        return
    try:
        cdo = _default_object(cls)
    except Exception as e:  # noqa: BLE001
        results["corpus_base_is_placeable_class"] = check(
            "corpus_base_is_placeable_class", False,
            "CORPUS_CDO_PROBE_ERROR name=%s raised %r" % (BASE_NAME, e))
        return
    verdict = _isinstance_tristate(cdo, "Actor")
    if verdict is None:
        results["corpus_base_is_placeable_class"] = check(
            "corpus_base_is_placeable_class", False,
            "CORPUS_BASE_TYPE_PROBE_ERROR class=%s" % _class_name(cdo))
    else:
        results["corpus_base_is_placeable_class"] = check(
            "corpus_base_is_placeable_class", bool(verdict),
            ("CORPUS_BASE_OK class=%s" % _class_name(cdo)) if verdict
            else ("CORPUS_MODIFIED_BASE_CLASS class=%s "
                  "not_a_placeable_object_class" % _class_name(cdo)))


def _derivation_check(results, cid, classes, fails, child_name, base_name,
                      want, fail_literal, ok_literal):
    """One pinned derivation fact. ``fail_literal`` / ``ok_literal`` arrive
    as WHOLE static literals from the call site (single-literal token law):
    every name in them is pinned, so no formatting is needed."""
    for name in (child_name, base_name):
        if name not in classes:
            results[cid] = check(cid, False, fails[name])
            return
    try:
        got = _child_of(classes[child_name], classes[base_name])
    except Exception as e:  # noqa: BLE001
        results[cid] = check(
            cid, False,
            "CORPUS_CHILDOF_PROBE_ERROR pair=%s->%s raised %r"
            % (child_name, base_name, e))
        return
    ok = got is want
    results[cid] = check(cid, ok, ok_literal if ok else fail_literal)


def _corpus_checks(results):
    _corpus_file_set_check(results)
    classes, fails = _resolve_corpus_classes()
    _base_class_check(results, classes, fails)
    _derivation_check(
        results, "corpus_drill_derives_base", classes, fails,
        DRILL_NAME, BASE_NAME, True,
        "CORPUS_MODIFIED_DRILL_PARENT name=BP_DrillRig no_longer_derives_from=BP_MachineBase",  # noqa: E501 - single literal by MATRIX-oracle law
        "CORPUS_DRILL_OK derives_from=BP_MachineBase")
    _derivation_check(
        results, "corpus_heavy_derives_drill", classes, fails,
        HEAVY_NAME, DRILL_NAME, True,
        "CORPUS_MODIFIED_HEAVY_PARENT name=BP_HeavyDrillRig no_longer_derives_from=BP_DrillRig",  # noqa: E501 - single literal by MATRIX-oracle law
        "CORPUS_HEAVY_OK derives_from=BP_DrillRig")
    _derivation_check(
        results, "corpus_baseplate_underived", classes, fails,
        BASEPLATE_NAME, BASE_NAME, False,
        "CORPUS_MODIFIED_BASEPLATE_PARENT name=BP_MachineBaseplate now_derives_from=BP_MachineBase",  # noqa: E501 - single literal by MATRIX-oracle law
        "CORPUS_BASEPLATE_OK underived_from=BP_MachineBase")
    _derivation_check(
        results, "corpus_scout_underived", classes, fails,
        SCOUT_NAME, BASE_NAME, False,
        "CORPUS_MODIFIED_SCOUT_PARENT name=BP_ScoutRig now_derives_from=BP_MachineBase",  # noqa: E501 - single literal by MATRIX-oracle law
        "CORPUS_SCOUT_OK underived_from=BP_MachineBase")


# --------------------------------------------------------------------------- #
# group 2: the report checks (fills 4 results)                                 #
# --------------------------------------------------------------------------- #

def _parse_report(text):
    """({name: parent}, None) or (None, failure_detail). Strict grammar:
    every non-blank line must be a ``derived`` line; no duplicate names."""
    parsed = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = RE_DERIVED.match(line)
        if m is None:
            return None, ("REPORT_GRAMMAR_BAD line=%r reason=%s"
                          % (line, "unrecognized_line"))
        if m.group(1) in parsed:
            return None, ("REPORT_GRAMMAR_BAD line=%r reason=%s"
                          % (line, "duplicate_derived_name"))
        parsed[m.group(1)] = m.group(2)
    return parsed, None


def _report_checks(results):
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
        "REPORT_GRAMMAR_OK lines=%d" % len(parsed))

    # --- set equality against the PINNED expected derived set ----------------
    reported_names = set(parsed)
    expected_names = set(EXPECTED_DERIVED_NAMES)
    reported_only = sorted(reported_names - expected_names)
    expected_only = sorted(expected_names - reported_names)
    ok = not reported_only and not expected_only
    results["report_derived_set_exact"] = check(
        "report_derived_set_exact", ok,
        ("DERIVED_SET_OK count=%d" % len(expected_names)) if ok
        else ("DERIVED_SET_MISMATCH reported_only=%s expected_only=%s"
              % (reported_only, expected_only)))

    # --- per-line direct-parent truth against the PINNED pairs ---------------
    # Iterates the pinned pairs (never the report), so an empty report fails
    # here too instead of passing vacuously; extra reported names are owned
    # by the set check above.
    problems = []
    for name, parent in EXPECTED_DERIVED:
        reported = parsed.get(name)
        if reported is None:
            problems.append("%s reported=absent expected=%s" % (name, parent))
        elif reported != parent:
            problems.append("%s reported=%s expected=%s"
                            % (name, reported, parent))
    results["report_parent_lines_truthful"] = check(
        "report_parent_lines_truthful", not problems,
        ("DERIVED_PARENTS_OK count=%d" % len(EXPECTED_DERIVED))
        if not problems
        else ("DERIVED_PARENT_WRONG problems=%s" % problems[:4]))


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #

def main():
    results = {}
    try:
        _corpus_checks(results)
    except Exception as e:  # noqa: BLE001 - never abort the verdict
        _fanout(results, CORPUS_CHECK_IDS,
                "KDBS_INTROSPECTION_ABORTED raised %r" % (e,))
    try:
        _report_checks(results)
    except Exception as e:  # noqa: BLE001
        _fanout(results, REPORT_CHECK_IDS,
                "KDBS_INTROSPECTION_ABORTED raised %r" % (e,))

    checks = [results.get(cid) or check(cid, False,
                                        "CHECK_NOT_EVALUATED id=%s" % cid)
              for cid in CHECK_IDS]
    emit_verdict(checks)


if __name__ == "__main__":
    main()
