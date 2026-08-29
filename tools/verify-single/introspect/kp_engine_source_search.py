"""L2-introspect script for the kp-engine-source-search task (python basket).

Deterministic verification of ONE agent-written text artifact: the strict
grammar answers file ``Content/Tasks/kp-engine-source-search/reports/
answers.txt``. Emits one CRAFTBENCH-INTROSPECT-JSON block the L2-introspect
layer parses (``layers/l2_introspect.py``; contract:
``layers/INTROSPECT_CONTRACT.md``).

What is graded (seed roster Block A row R13, sheet name
``t12-engine-source-search``, re-shaped from an open enumeration into four
exact-token questions; see the task spec):

  * The answers file exists at the pre-declared path, parses under the ONE
    disclosed line shape ``answer id=<qid> value=<token>`` with no duplicate
    and no unknown question ids, and
  * each of the four answers EXACTLY matches a VERIFIER-OWNED constant that
    was derived from the pinned UE 5.8 engine source at authoring time
    (file+line citations in the task's notes.md). The engine is
    version-pinned repo-wide, so these are stable facts, not moving targets.

THE CORPUS OF THIS TASK IS THE PINNED ENGINE SOURCE ITSELF. It is read-only,
lives outside every agent-writable prefix, and is NEVER read at grade time -
grading is a pure text compare against the pinned constants plus one engine
version probe, so the grade is fast and deterministic. The corpus-unmodified
guard is the ENGINE PIN CHECK: if the grading editor does not report a 5.8
engine, the pinned constants are stale by definition and the check FAILS
with the named ``ENGINE_PIN_MISMATCH`` message rather than silently grading
answers against the wrong corpus.

Hard rules honoured here:
  * READ-ONLY. Nothing below mutates an asset, a package, a file, or the
    project. The only ``unreal`` calls are the version read and the
    content-dir path resolution.
  * Identity by pre-declared file path and pre-declared question ids; the
    expected values are constants in THIS file (verifier-owned; the agent
    can write none of them).
  * Every probe is wrapped so one wrong API name degrades to exactly one
    FAILED check with the exception in ``detail``.
  * FAIL CLOSED. No check passes because a probe did not raise. A missing or
    empty submission fails every report-side check with one named root cause
    fanned out (never a vacuous pass); a grammar violation fails the grammar
    check AND every answer check with the same parse-fail detail; a missing
    answer id is a graded per-answer failure, never a skip.
  * The check list has a CONSTANT length (7) on every leg, including the
    empty submission. ``registry.py`` reports ``tests_passed/tests_run``
    from these counts, so a submission cannot improve its ratio by making
    checks unreachable. (On the empty leg the engine-pin check - a harness
    invariant, not an agent requirement - still passes: 1/7, overall FAIL.)

Detail strings are stable, ASCII-ONLY, greppable tokens; each meaningful
token+key literal lives in ONE string literal (never split across
concatenations) so the MATRIX oracle can grep it from source. Error tokens
(``*_PROBE_ERROR`` / ``*_READ_ERROR`` / ``*_ABORTED`` / ``CHECK_NOT_EVALUATED``)
are disjoint from graded failure tokens and appear in no MATRIX row, so a
broken UE API name can never be credited as a named assertion. No detail
contains either automation result marker; neither marker substring appears
anywhere in this file.

UE 5.8 API notes:
  * Version  - ``unreal.SystemLibrary.get_engine_version()`` (stock, proven;
    returns a string beginning ``5.8.``).
  * Path     - ``unreal.Paths.project_content_dir`` +
    ``convert_relative_path_to_full`` (the same route every sibling
    report-grading introspect uses).
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

# --- Pre-declared identity (file path and question ids) ----------------------
TASK_ID = "kp-engine-source-search"
ANSWERS_REL = "Content/Tasks/%s/reports/answers.txt" % TASK_ID

QID_DELEGATE = "delegate-header"
QID_CVAR = "cvar-default"
QID_MODULE = "class-module"
QID_NAME = "name-capacity"
QUESTION_IDS = (QID_DELEGATE, QID_CVAR, QID_MODULE, QID_NAME)

# --- VERIFIER-OWNED expected constants ---------------------------------------
# Derived from the PINNED UE 5.8 engine source at authoring time (2026-08-11,
# engine Build.version 5.8.0 CL 55116800, branch ++UE5+Release-5.8); file+line
# citations live in the task's notes.md. The introspect NEVER reads the engine
# source at grade time - these constants ARE the answer key, and the engine
# pin check below is what keeps them honest. The aid re-derives every one of
# them from the live engine tree before the reference is harvested.
EXPECTED_ANSWERS = {
    # FCoreDelegates::OnEnginePreExit declaration
    # (Runtime/Core/Public/Misc/CoreDelegates.h line 262).
    QID_DELEGATE: "Engine/Source/Runtime/Core/Public/Misc/CoreDelegates.h",
    # net.MaxConstructedPartialBunchSizeBytes compiled-in default, written in
    # source as 1024 * 64 (Runtime/Engine/Private/DataChannel.cpp lines
    # 105-110).
    QID_CVAR: "65536",
    # FJsonObject declaring module (Runtime/Json/Public/Dom/JsonObject.h line
    # 322; module rules file Runtime/Json/Json.Build.cs).
    QID_MODULE: "Json",
    # NAME_SIZE (Runtime/Core/Public/UObject/NameTypes.h line 57).
    QID_NAME: "1024",
}

# The corpus pin. A version string not starting with this prefix means the
# constants above were derived from a DIFFERENT corpus than the one grading.
ENGINE_VERSION_PREFIX = "5.8."

# --- The answers-file grammar (disclosed verbatim in the agent prompt) -------
RE_ANSWER = re.compile(r"^answer id=(\S+) value=(\S+)$")

# --- The check ids, in emission order. Length is the score denominator (7). --
PIN_CHECK_ID = "engine_pin_matches"
REPORT_CHECK_IDS = (
    "answers_file_present",
    "answers_grammar_parses",
    "answer_delegate_header_exact",
    "answer_cvar_default_exact",
    "answer_class_module_exact",
    "answer_name_capacity_exact",
)
ANSWER_CHECK_IDS = REPORT_CHECK_IDS[2:]
ANSWER_CHECK_BY_QID = {
    QID_DELEGATE: "answer_delegate_header_exact",
    QID_CVAR: "answer_cvar_default_exact",
    QID_MODULE: "answer_class_module_exact",
    QID_NAME: "answer_name_capacity_exact",
}
CHECK_IDS = (PIN_CHECK_ID,) + REPORT_CHECK_IDS


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
# the corpus pin (harness invariant; graded so a stale corpus fails LOUDLY)    #
# --------------------------------------------------------------------------- #

def _pin_check(results):
    if unreal is None:
        results[PIN_CHECK_ID] = check(
            PIN_CHECK_ID, False,
            "ENGINE_PIN_PROBE_ERROR the unreal module is unavailable")
        return
    try:
        version = str(unreal.SystemLibrary.get_engine_version())
    except Exception as e:  # noqa: BLE001
        results[PIN_CHECK_ID] = check(
            PIN_CHECK_ID, False, "ENGINE_PIN_PROBE_ERROR raised %r" % (e,))
        return
    if version.startswith(ENGINE_VERSION_PREFIX):
        results[PIN_CHECK_ID] = check(
            PIN_CHECK_ID, True, "ENGINE_PIN_OK version=%s" % version)
    else:
        results[PIN_CHECK_ID] = check(
            PIN_CHECK_ID, False,
            "ENGINE_PIN_MISMATCH version=%s expected_prefix=5.8. the pinned "
            "answer constants only hold on the 5.8 engine" % version)


# --------------------------------------------------------------------------- #
# answers file: locate, read, parse, compare                                   #
# --------------------------------------------------------------------------- #

def _content_dir():
    raw = unreal.Paths.project_content_dir()
    try:
        full = unreal.Paths.convert_relative_path_to_full(raw)
    except Exception:  # noqa: BLE001 - older spelling; abspath is equivalent
        full = os.path.abspath(str(raw))
    return str(full)


def _answers_path():
    return os.path.join(_content_dir(), "Tasks", TASK_ID, "reports",
                        "answers.txt")


def _read_text(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _parse_answers(text):
    """({qid: value}, None) or (None, failure_detail). Strict grammar.

    One line shape only; blank lines ignored; order-free; a duplicate id or
    an id outside the four disclosed question ids is a grammar failure (the
    shotgun defense: only ONE value can ever be submitted per question). A
    file with no answer lines at all is a grammar failure, never an empty
    success.
    """
    parsed = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = RE_ANSWER.match(line)
        if not m:
            return None, ("ANSWERS_GRAMMAR_BAD line=%r reason=%s"
                          % (line, "unrecognized_line"))
        qid, value = m.group(1), m.group(2)
        if qid in parsed:
            return None, ("ANSWERS_GRAMMAR_BAD line=%r reason=%s"
                          % (line, "duplicate_answer_id"))
        if qid not in EXPECTED_ANSWERS:
            return None, ("ANSWERS_GRAMMAR_BAD line=%r reason=%s"
                          % (line, "unknown_answer_id"))
        parsed[qid] = value
    if not parsed:
        return None, ("ANSWERS_GRAMMAR_BAD line=%r reason=%s"
                      % ("", "no_answer_lines"))
    return parsed, None


def _report_checks(results):
    try:
        path = _answers_path()
        present = os.path.isfile(path)
    except Exception as e:  # noqa: BLE001
        cause = "ANSWERS_PROBE_ERROR raised %r" % (e,)
        _fanout(results, REPORT_CHECK_IDS, cause)
        return
    if not present:
        cause = "ANSWERS_FILE_MISSING path=%s" % ANSWERS_REL
        _fanout(results, REPORT_CHECK_IDS, cause)
        return
    results["answers_file_present"] = check(
        "answers_file_present", True, "ANSWERS_FILE_OK path=%s" % ANSWERS_REL)

    try:
        text = _read_text(path)
    except Exception as e:  # noqa: BLE001
        cause = "ANSWERS_READ_ERROR raised %r" % (e,)
        _fanout(results, REPORT_CHECK_IDS, cause)
        return
    parsed, parse_fail = _parse_answers(text)
    if parsed is None:
        results["answers_grammar_parses"] = check(
            "answers_grammar_parses", False, parse_fail)
        _fanout(results, ANSWER_CHECK_IDS, parse_fail)
        return
    results["answers_grammar_parses"] = check(
        "answers_grammar_parses", True,
        "ANSWERS_GRAMMAR_OK answers=%d" % len(parsed))

    present_ids = sorted(parsed.keys())
    for qid in QUESTION_IDS:
        cid = ANSWER_CHECK_BY_QID[qid]
        if qid not in parsed:
            results[cid] = check(
                cid, False,
                "ANSWER_MISSING id=%s present=%s" % (qid, present_ids))
            continue
        reported = parsed[qid]
        expected = EXPECTED_ANSWERS[qid]
        ok = reported == expected
        results[cid] = check(
            cid, ok,
            ("ANSWER_OK id=%s value=%s" % (qid, reported)) if ok
            else ("ANSWER_WRONG id=%s reported=%s expected=%s"
                  % (qid, reported, expected)))


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #

def main():
    results = {}
    try:
        _pin_check(results)
    except Exception as e:  # noqa: BLE001 - never abort the verdict
        _fanout(results, (PIN_CHECK_ID,),
                "KPESS_INTROSPECTION_ABORTED raised %r" % (e,))
    try:
        _report_checks(results)
    except Exception as e:  # noqa: BLE001
        _fanout(results, REPORT_CHECK_IDS,
                "KPESS_INTROSPECTION_ABORTED raised %r" % (e,))

    # Constant-length, deterministically ordered verdict.
    checks = [results.get(cid) or check(cid, False,
                                        "CHECK_NOT_EVALUATED id=%s" % cid)
              for cid in CHECK_IDS]
    emit_verdict(checks)


if __name__ == "__main__":
    main()
