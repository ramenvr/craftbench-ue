"""L2-introspect script for the kp-routine-usage-search task (python basket).

Structural, READ-ONLY verification of ONE submitted text artifact against a
VERIFIER-OWNED truth table, plus a corpus-unmodified guard. Emits one
CRAFTBENCH-INTROSPECT-JSON block the L2-introspect layer parses
(``layers/l2_introspect.py``; contract: ``layers/INTROSPECT_CONTRACT.md``).

What is graded (seed roster R12, sheet name ``t11-blueprint-search``,
re-shaped from answer-shaped Q&A into the strict-grammar report pattern the
kp-blueprint-actor-audit-report task proved; see the task spec):

  * REPORT - ``Content/Tasks/kp-routine-usage-search/reports/usage.txt``:
    a strict-grammar plain-text usage report naming the stated library
    function (``ComputeChecksum``) and giving, for each of the four
    committed SEARCH-CORPUS class assets under
    ``/Game/Tasks/kp-routine-usage-search/corpus/``, a yes/no verdict on
    whether it references that function. Every verdict is cross-checked
    against the PINNED authoring-time truth below - never against anything
    the submission can write.
  * GUARD  - the corpus (four ``.uasset`` files) and the library source pair
    (``Source/ThirdPerson/Tasks/kp-routine-usage-search/``) must be
    byte-identical to the committed baseline. Editing the search TARGETS to
    match a report must never move the truth: the truth is a constant in
    this file, and any corpus/library edit is itself a graded FAIL with a
    named corpus-modified message.

The verifier-owned truth (authoring-time facts about the committed corpus):

  * ``BP_North`` - references ``ComputeChecksum`` DIRECTLY (a call in its
    own graph; authored via the MCP graph lane at corpus-authoring time).
  * ``BP_East``  - references it INDIRECTLY: it is a child class of
    ``BP_North`` with no logic of its own, so its own file never mentions
    the function name (a naive per-file name grep answers this row wrong).
  * ``BP_South`` - does NOT reference it; it calls the sibling routine
    ``FormatLabel`` from the same library (a module/library-level dependency
    scan answers this row wrong).
  * ``BP_West``  - does NOT reference it; it merely CARRIES the name
    ``ComputeChecksum`` as an identifying marker value, with no tie to the
    library at all (a naive byte/name grep answers this row wrong).

The deliverable is the report ONLY. No gate asserts how the answer was
produced (basket law: outcome-graded editor scripting).

Hard rules honoured here:
  * READ-ONLY. Nothing below loads, mutates, saves, renames, or deletes any
    asset or file; the corpus guard reads raw bytes off disk and the
    registry existence probe reads metadata only.
  * Identity by pre-declared content path and file name, never by class
    scanning.
  * Stock UE Python only (``EditorAssetLibrary``, ``unreal.Paths``). Never
    Aura's MCP tools - that would grade Aura with Aura.
  * NO protected-reflection reads: no UbergraphPages walk, no
    EdGraphPinType pin reads, no graph traversal at all. The graded truth
    is pinned at authoring time; grade time only checks the corpus is still
    the authored corpus (hashes) and the report tells that pinned truth.
  * Every check is wrapped so one wrong API name degrades to exactly one
    FAILED check with the exception in ``detail`` instead of aborting the
    verdict.
  * FAIL CLOSED. No check passes because a probe did not raise. An empty
    submission leaves the corpus baseline intact (the guard checks
    legitimately pass) and fails every report check with the
    ``USAGE_REPORT_MISSING path=`` root cause fanned out - overall FAIL,
    never a vacuous pass. The verdict-truth check iterates the PINNED
    corpus list, so an empty or evasive report can never shrink the set it
    is graded on; a failed prerequisite fans its own root-cause token into
    the dependent checks.
  * The check list has a CONSTANT length (9) on every leg, including the
    empty submission. ``registry.py`` reports ``tests_passed/tests_run``
    from these counts.

Detail strings are stable, ASCII-ONLY, greppable tokens; each meaningful
token+key literal lives in ONE string literal (never split across
concatenations) so the MATRIX oracle can grep it from source. Error tokens
(``*_PROBE_ERROR`` / ``*_READ_ERROR`` / ``*_UNPINNED`` / ``*_ABORTED`` /
``CHECK_NOT_EVALUATED`` / ``USAGE_CORPUS_HASH_TARGET_MISSING``) are
disjoint from graded failure tokens and appear in no MATRIX row, so a
broken UE API name - or a not-yet-pinned corpus hash - can never be
credited as a named variant failure. No detail contains either automation
result marker; neither marker substring appears anywhere in this file.

Hash pinning protocol: the corpus binaries are built by the authoring-lane
aid (``tasks/python/kp-routine-usage-search/aids/author_reference.py``),
which prints one ``KPUSAGE-HASH`` line per corpus file. Those hex digests
are then pinned into ``CORPUS_SHA256`` below (replacing the
fail-closed sentinel) in the same change-set that commits the binaries.
The library source hashes are pinned already (authored alongside this
file); they are computed over CR-stripped bytes so git line-ending
normalization cannot flip them.

UE 5.8 API notes:
  * Existence  - ``unreal.EditorAssetLibrary.does_asset_exist`` (proven).
  * Paths      - ``unreal.Paths.project_content_dir`` / ``project_dir`` +
    ``convert_relative_path_to_full`` (proven by the sibling kp tasks).
  * Everything else here is plain ``os`` / ``hashlib`` / ``re`` - by
    design, this is the least UE-coupled introspect in the basket.
"""
import hashlib
import json
import os
import re

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax / oracle checks
    unreal = None

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

# --- Pre-declared identity (content paths and file names, never class) -------
TASK_ID = "kp-routine-usage-search"
CORPUS_PKG_DIR = "/Game/Tasks/%s/corpus" % TASK_ID
REPORT_REL = "Content/Tasks/%s/reports/usage.txt" % TASK_ID
LIBRARY_SRC_REL_DIR = "Source/ThirdPerson/Tasks/%s" % TASK_ID

# --- The verifier-owned truth (the agent cannot write any of this) -----------
STATED_FUNCTION = "ComputeChecksum"
# (corpus entry name, references-the-stated-function) - authoring-time truth.
CORPUS_TRUTH = (
    ("BP_North", True),    # direct call in its own graph
    ("BP_East", True),     # child of BP_North; inherits the call
    ("BP_South", False),   # calls sibling routine FormatLabel instead
    ("BP_West", False),    # carries the name as a marker value only
)
CORPUS_NAMES = tuple(name for name, _ in CORPUS_TRUTH)
EXPECTED_ENTRY_COUNT = 4

# --- Corpus-unmodified guard: pinned raw-byte sha256 per corpus file. --------
# Sentinel = fail-closed until the authoring-lane run pins real digests (the
# aid prints KPUSAGE-HASH lines; pin them in the commit that adds the
# binaries). An unpinned hash is an UNCREDITABLE failure, never a pass.
HASH_UNPINNED = "PIN-FROM-KPUSAGE-HASH-AFTER-AUTHORING-RUN"
CORPUS_SHA256 = {
    "BP_North.uasset": "ce71b4e0d71286f6ff2653f87e7d1f6d26d1ffe47e4242132ab9ad86be65f3f4",
    "BP_East.uasset": "b75d6dcf65fb9d81ded6ff37b135f424c70dfd6270c2e1b6709e5e0a558765b8",
    "BP_South.uasset": "42d20224346fe792e44e9714ac907aac806b6f418ea342c4ecddbd5e7f583d49",
    "BP_West.uasset": "3f3cf9b47efb0783f13d1f028f4c546b7cc3c42c7e8a9a9a01c7501f816ce4e8",
}
# CR-stripped sha256 of the committed library sources (pinned at authoring
# time; recompute with: tr -d '\r' < <file> | sha256sum).
LIBRARY_SHA256 = {
    "EvalUtilityLibrary.h":
        "41bcc87c5c624da2f22c655f62b07fdbe034ddc48eb894238a0bfd50258e1562",
    "EvalUtilityLibrary.cpp":
        "b025f6a4fbdfc4f7a6896b571aa6b0dd05c8a5263e338e480ed53c6e75d76e80",
}

# --- The check ids, in emission order. Length is the score denominator (9). --
GUARD_CHECK_IDS = (
    "corpus_assets_present",
    "corpus_dir_exact",
    "corpus_bytes_unmodified",
    "library_source_unmodified",
)
REPORT_CHECK_IDS = (
    "report_file_present",
    "report_grammar_parses",
    "report_function_line_correct",
    "report_covers_corpus_exactly",
    "report_verdicts_truthful",
)
CHECK_IDS = GUARD_CHECK_IDS + REPORT_CHECK_IDS

# --- Report grammar (disclosed verbatim in the agent prompt) -----------------
RE_FUNCTION = re.compile(r"^function name=(\S+)$")
RE_ENTRY = re.compile(r"^entry name=(\S+) references=(yes|no)$")

# One template literal per grammar-failure event (single-literal law).
_GRAMMAR_BAD = "USAGE_GRAMMAR_BAD line=%r reason=%s"


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
# path helpers                                                                 #
# --------------------------------------------------------------------------- #

def _full_path(raw):
    try:
        return str(unreal.Paths.convert_relative_path_to_full(raw))
    except Exception:  # noqa: BLE001 - older spelling; abspath is equivalent
        return os.path.abspath(str(raw))


def _content_dir():
    return _full_path(unreal.Paths.project_content_dir())


def _project_dir():
    return _full_path(unreal.Paths.project_dir())


def _corpus_dir():
    return os.path.join(_content_dir(), "Tasks", TASK_ID, "corpus")


def _report_path():
    return os.path.join(_content_dir(), "Tasks", TASK_ID, "reports",
                        "usage.txt")


def _library_src_dir():
    return os.path.join(_project_dir(), "Source", "ThirdPerson", "Tasks",
                        TASK_ID)


def _sha256_raw(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _sha256_no_cr(path):
    """sha256 over CR-stripped bytes - stable across git eol normalization."""
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read().replace(b"\r", b"")).hexdigest()


def _read_text(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


# --------------------------------------------------------------------------- #
# group 1: the corpus-unmodified guard (4 checks, each independent)            #
# --------------------------------------------------------------------------- #

def _guard_assets_present(results):
    """Registry existence of the four pinned corpus assets."""
    try:
        missing = []
        for name in CORPUS_NAMES:
            path = "%s/%s" % (CORPUS_PKG_DIR, name)
            if not bool(unreal.EditorAssetLibrary.does_asset_exist(path)):
                missing.append(path)
        if missing:
            results["corpus_assets_present"] = check(
                "corpus_assets_present", False,
                "USAGE_CORPUS_ASSET_MISSING path=%s missing_count=%d"
                % (missing[0], len(missing)))
        else:
            results["corpus_assets_present"] = check(
                "corpus_assets_present", True,
                "USAGE_CORPUS_ASSETS_OK count=%d" % len(CORPUS_NAMES))
    except Exception as e:  # noqa: BLE001
        results["corpus_assets_present"] = check(
            "corpus_assets_present", False,
            "USAGE_CORPUS_REGISTRY_PROBE_ERROR raised %r" % (e,))


def _guard_dir_exact(results):
    """The on-disk corpus folder holds EXACTLY the four pinned files."""
    try:
        corpus_dir = _corpus_dir()
        expected = set(CORPUS_SHA256.keys())
        found = set(os.listdir(corpus_dir)) if os.path.isdir(corpus_dir) \
            else set()
        missing = sorted(expected - found)
        extras = sorted(found - expected)
        if missing:
            results["corpus_dir_exact"] = check(
                "corpus_dir_exact", False,
                "USAGE_CORPUS_FILE_MISSING file=%s missing_count=%d"
                % (missing[0], len(missing)))
        elif extras:
            results["corpus_dir_exact"] = check(
                "corpus_dir_exact", False,
                "USAGE_CORPUS_EXTRA_FILES extras=%s" % (extras,))
        else:
            results["corpus_dir_exact"] = check(
                "corpus_dir_exact", True,
                "USAGE_CORPUS_DIR_OK files=%d" % len(expected))
    except Exception as e:  # noqa: BLE001
        results["corpus_dir_exact"] = check(
            "corpus_dir_exact", False,
            "USAGE_CORPUS_DIR_PROBE_ERROR raised %r" % (e,))


def _guard_bytes_unmodified(results):
    """Raw sha256 of every corpus file equals its pinned authoring digest."""
    try:
        corpus_dir = _corpus_dir()
        unpinned = sorted(f for f, h in CORPUS_SHA256.items()
                          if h == HASH_UNPINNED)
        if unpinned:
            # Uncreditable by design: the authoring run has not pinned the
            # digests yet, so nothing can be graded against them.
            results["corpus_bytes_unmodified"] = check(
                "corpus_bytes_unmodified", False,
                "USAGE_CORPUS_HASH_UNPINNED file=%s unpinned_count=%d"
                % (unpinned[0], len(unpinned)))
            return
        target_missing = []
        modified = []
        for fname, pinned in sorted(CORPUS_SHA256.items()):
            path = os.path.join(corpus_dir, fname)
            if not os.path.isfile(path):
                target_missing.append(fname)
                continue
            got = _sha256_raw(path)
            if got != pinned:
                modified.append((fname, got, pinned))
        if target_missing:
            results["corpus_bytes_unmodified"] = check(
                "corpus_bytes_unmodified", False,
                "USAGE_CORPUS_HASH_TARGET_MISSING file=%s missing_count=%d"
                % (target_missing[0], len(target_missing)))
        elif modified:
            fname, got, pinned = modified[0]
            results["corpus_bytes_unmodified"] = check(
                "corpus_bytes_unmodified", False,
                "USAGE_CORPUS_MODIFIED file=%s got=%s expected=%s "
                "wrong_count=%d" % (fname, got, pinned, len(modified)))
        else:
            results["corpus_bytes_unmodified"] = check(
                "corpus_bytes_unmodified", True,
                "USAGE_CORPUS_BYTES_OK count=%d" % len(CORPUS_SHA256))
    except Exception as e:  # noqa: BLE001
        results["corpus_bytes_unmodified"] = check(
            "corpus_bytes_unmodified", False,
            "USAGE_CORPUS_HASH_PROBE_ERROR raised %r" % (e,))


def _guard_library_unmodified(results):
    """CR-normalized sha256 of both library sources equals the pinned pair."""
    try:
        src_dir = _library_src_dir()
        source_missing = []
        modified = []
        for fname, pinned in sorted(LIBRARY_SHA256.items()):
            path = os.path.join(src_dir, fname)
            if not os.path.isfile(path):
                source_missing.append(fname)
                continue
            got = _sha256_no_cr(path)
            if got != pinned:
                modified.append((fname, got, pinned))
        if source_missing:
            results["library_source_unmodified"] = check(
                "library_source_unmodified", False,
                "USAGE_LIBRARY_SOURCE_MISSING file=%s missing_count=%d"
                % (source_missing[0], len(source_missing)))
        elif modified:
            fname, got, pinned = modified[0]
            results["library_source_unmodified"] = check(
                "library_source_unmodified", False,
                "USAGE_LIBRARY_MODIFIED file=%s got=%s expected=%s "
                "wrong_count=%d" % (fname, got, pinned, len(modified)))
        else:
            results["library_source_unmodified"] = check(
                "library_source_unmodified", True,
                "USAGE_LIBRARY_OK count=%d" % len(LIBRARY_SHA256))
    except Exception as e:  # noqa: BLE001
        results["library_source_unmodified"] = check(
            "library_source_unmodified", False,
            "USAGE_LIBRARY_PROBE_ERROR raised %r" % (e,))


def _guard_checks(results):
    _guard_assets_present(results)
    _guard_dir_exact(results)
    _guard_bytes_unmodified(results)
    _guard_library_unmodified(results)


# --------------------------------------------------------------------------- #
# group 2: the report checks (5 checks; cross-checked against pinned truth)    #
# --------------------------------------------------------------------------- #

def _parse_report(text):
    """(parsed, None) or (None, failure_detail). Strict grammar, order-free.

    parsed = {"function": name, "entries": {entry_name: "yes"|"no"}}
    """
    parsed = {"function": None, "entries": {}}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = RE_FUNCTION.match(line)
        if m:
            if parsed["function"] is not None:
                return None, _GRAMMAR_BAD % (line, "duplicate_function_line")
            parsed["function"] = m.group(1)
            continue
        m = RE_ENTRY.match(line)
        if m:
            if m.group(1) in parsed["entries"]:
                return None, _GRAMMAR_BAD % (line, "duplicate_entry_name")
            parsed["entries"][m.group(1)] = m.group(2)
            continue
        return None, _GRAMMAR_BAD % (line, "unrecognized_line")
    if parsed["function"] is None:
        return None, _GRAMMAR_BAD % ("", "missing_function_line")
    return parsed, None


def _report_checks(results):
    try:
        path = _report_path()
        present = os.path.isfile(path)
    except Exception as e:  # noqa: BLE001
        cause = "USAGE_REPORT_PROBE_ERROR raised %r" % (e,)
        _fanout(results, REPORT_CHECK_IDS, cause)
        return
    if not present:
        cause = "USAGE_REPORT_MISSING path=%s" % REPORT_REL
        _fanout(results, REPORT_CHECK_IDS, cause)
        return
    results["report_file_present"] = check(
        "report_file_present", True, "USAGE_REPORT_OK path=%s" % REPORT_REL)

    try:
        text = _read_text(path)
    except Exception as e:  # noqa: BLE001
        cause = "USAGE_REPORT_READ_ERROR raised %r" % (e,)
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
        "USAGE_GRAMMAR_OK entries=%d" % len(parsed["entries"]))

    # --- the function line ---------------------------------------------------
    reported_fn = parsed["function"]
    fn_ok = reported_fn == STATED_FUNCTION
    results["report_function_line_correct"] = check(
        "report_function_line_correct", fn_ok,
        ("USAGE_FUNCTION_LINE_OK name=%s" % reported_fn) if fn_ok
        else ("USAGE_FUNCTION_LINE_WRONG reported=%s expected=%s"
              % (reported_fn, STATED_FUNCTION)))

    # --- coverage: reported entry set EQUALS the pinned corpus set -----------
    reported_names = set(parsed["entries"].keys())
    expected_names = set(CORPUS_NAMES)
    reported_only = sorted(reported_names - expected_names)
    missing_names = sorted(expected_names - reported_names)
    coverage_ok = not reported_only and not missing_names
    results["report_covers_corpus_exactly"] = check(
        "report_covers_corpus_exactly", coverage_ok,
        ("USAGE_COVERAGE_OK count=%d" % EXPECTED_ENTRY_COUNT) if coverage_ok
        else ("USAGE_COVERAGE_MISMATCH reported_only=%s missing=%s"
              % (reported_only, missing_names)))

    # --- verdict truth: iterate the PINNED list, never the report's ----------
    absent = []
    wrong = []
    yes_count, no_count = 0, 0
    for name, refs in CORPUS_TRUTH:
        expected_value = "yes" if refs else "no"
        reported_value = parsed["entries"].get(name)
        if reported_value is None:
            absent.append(name)
            continue
        if reported_value != expected_value:
            wrong.append((name, reported_value, expected_value))
        elif refs:
            yes_count += 1
        else:
            no_count += 1
    if absent:
        results["report_verdicts_truthful"] = check(
            "report_verdicts_truthful", False,
            "USAGE_VERDICT_MISSING entry=%s missing_count=%d"
            % (absent[0], len(absent)))
    elif wrong:
        name, reported_value, expected_value = wrong[0]
        results["report_verdicts_truthful"] = check(
            "report_verdicts_truthful", False,
            "USAGE_VERDICT_WRONG entry=%s reported=%s expected=%s "
            "wrong_count=%d"
            % (name, reported_value, expected_value, len(wrong)))
    else:
        results["report_verdicts_truthful"] = check(
            "report_verdicts_truthful", True,
            "USAGE_VERDICTS_OK yes=%d no=%d" % (yes_count, no_count))


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #

def main():
    results = {}
    try:
        _guard_checks(results)
    except Exception as e:  # noqa: BLE001 - never abort the verdict
        _fanout(results, GUARD_CHECK_IDS,
                "USAGE_INTROSPECTION_ABORTED raised %r" % (e,))
    try:
        _report_checks(results)
    except Exception as e:  # noqa: BLE001
        _fanout(results, REPORT_CHECK_IDS,
                "USAGE_INTROSPECTION_ABORTED raised %r" % (e,))

    # Constant-length, deterministically ordered verdict.
    checks = [results.get(cid) or check(cid, False,
                                        "CHECK_NOT_EVALUATED id=%s" % cid)
              for cid in CHECK_IDS]
    emit_verdict(checks)


if __name__ == "__main__":
    main()
