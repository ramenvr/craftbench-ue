"""L2-introspect script for the t2-datatable-csv-export task.

Structural, READ-ONLY verification that a submission exported the three
baseline data tables to CSV files. Emits one CRAFTBENCH-INTROSPECT-JSON block
the L2-introspect layer parses (``layers/l2_introspect.py``; contract:
``layers/INTROSPECT_CONTRACT.md``).

What is graded (Sam/Chris tab R15, "Datatable export"; see the task spec):
the submission must ship exactly three CSV files, one per baseline table,
named ``<TableName>.csv``, under
``Content/Tasks/t2-datatable-csv-export/exports/`` - and each file's CONTENT
must match its table: the same row names and the same field values.

THE GROUND TRUTH IS PINNED IN THIS FILE, NOT READ FROM THE PROJECT.
``PINNED_CSVS`` below is the verifier-owned copy of the baseline content (the
same literals the authoring aid seeds the tables from; the offline oracle
asserts the two never drift). This matters because the baseline tables live
under ``Content/Tasks/<id>/data/`` - INSIDE the agent-writable carve-out - so
a grader that read its expected side off the LIVE tables could be gamed by
overwriting them with empty tables and shipping header-only CSVs: live-vs-file
would compare empty-to-empty and pass a capability-free submission (the
gold-leak shape). Instead:

  * ``<t>_rows_match`` and ``<t>_values_match`` compare the agent's file
    against the PINNED truth;
  * ``<t>_values_match`` FIRST verifies the LIVE table still matches the
    pinned truth - divergence is the graded ``*_BASELINE_TAMPERED`` failure
    (agent-caused by construction: ``apply_submission`` is a copy-only
    overlay, so only submission bytes can change a committed baseline; it
    also cannot DELETE one, which is why a missing table stays a
    verifier-side ``*_TABLE_MISSING``).

Acceptance for values is a **round-trip through the engine's own importer**:
the agent's CSV text and the pinned CSV text are each ingested into TRANSIENT
DataTables sharing the baseline's row struct, both are re-exported by the
engine's own exporter, and the canonical forms are compared (header exactly;
data lines as an order-insensitive set - row ORDER in a CSV is not content).
Cosmetics the engine itself normalizes (quoting, float formatting, row order)
never fail a submission; value differences always do; a file the importer
refuses fails as ``*_CSV_NOT_INGESTIBLE``. If the transient route is
unavailable (API risk points in notes.md), the compare falls back to a pure
csv-module row-dict compare against the pinned truth. Only when every route
breaks does the check report ``*_ROUNDTRIP_PROBE_ERROR``.

Verdict-taxonomy honesty (set convention): ``*_ROUNDTRIP_PROBE_ERROR``,
``*_TAMPER_PROBE_ERROR``, ``*_TABLE_MISSING`` and their siblings are
``passed: false`` checks inside a WELL-FORMED verdict block, so the layer
status is ``fail`` and the run GRADES exit 1 against the model today - only a
missing/malformed block routes to harness-error exit 7. "Uncreditable" means
no MATRIX row credits these tokens (an API break can never masquerade as a
variant's named failure), not that they do not score.

Hard rules honoured here:
  * READ-ONLY with respect to every ASSET and PACKAGE. Transient tables are
    never saved; no asset is mutated. Export-file reads are plain filesystem
    reads of the submission overlay.
  * Identity by **pre-declared content path** and pinned content, never by
    class or by scanning.
  * Stock UE Python only. Never Aura's MCP tools.
  * Every check is wrapped so one wrong API name degrades to exactly one
    FAILED check with the exception in ``detail``.
  * **FAIL CLOSED.** An unreadable export file is a failure, never a skip; an
    unresolvable tamper gate is a failure; a fill that reports False is the
    graded ``*_CSV_NOT_INGESTIBLE`` failure.
  * This script emits **exactly 13 named checks on every leg** (constant
    denominator). The runner's asset-integrity preamble may PREPEND failed
    ``asset_integrity`` checks on violating submissions, so report-level
    totals can exceed 13.

Detail strings are stable, ASCII, greppable tokens. The discrimination MATRIX
joins on the raw ``detail`` string as printed inside the JSON block. Every
failing check owns a unique token that never appears on a passing branch, and
every exception path owns a ``*_PROBE_ERROR`` / ``*_READ_ERROR`` /
``*_TABLE_MISSING`` token that appears in NO matrix row. No detail contains
either automation result marker ("TestResult" + "=Passed" / "Automation Test"
+ " Succeeded"); neither substring appears anywhere in this file.
"""
import csv
import io
import json
import os

try:
    import unreal  # available only inside UnrealEditor-Cmd
except ImportError:  # allow import for offline syntax / oracle checks
    unreal = None

INTROSPECT_JSON_START = "CRAFTBENCH-INTROSPECT-JSON-START"
INTROSPECT_JSON_END = "CRAFTBENCH-INTROSPECT-JSON-END"

# --- Pre-declared identity (content PATHS and NAMES, never class) ------------
TASK_ID = "t2-datatable-csv-export"

# key, table asset name. The key doubles as the check-id stem and the token
# prefix (upper-cased).
TABLES = (
    ("items", "DT_EvalItems"),
    ("waves", "DT_EvalWaves"),
    ("tuning", "DT_EvalTuning"),
)

TABLE_ASSET = {key: "/Game/Tasks/%s/data/%s" % (TASK_ID, name)
               for key, name in TABLES}
# Row structs are C++ (module-compiled), used only to build TRANSIENT tables.
STRUCT_PATH = {
    "items": "/Script/ThirdPerson.EvalItemRow",
    "waves": "/Script/ThirdPerson.EvalWaveRow",
    "tuning": "/Script/ThirdPerson.EvalTuningRow",
}
EXPORT_NAME = {key: "%s.csv" % name for key, name in TABLES}
# Submission-relative spelling used in tokens (stable, never read from disk).
EXPORT_REL = {key: "Content/Tasks/%s/exports/%s" % (TASK_ID, EXPORT_NAME[key])
              for key, _ in TABLES}
EXPORTS_DIR_REL = "Content/Tasks/%s/exports" % TASK_ID

EXPECTED_FILES = tuple(sorted(EXPORT_NAME.values()))

# --- THE PINNED GROUND TRUTH --------------------------------------------------
# Verifier-owned copy of the baseline table content. Keep byte-identical to
# BASELINE_CSVS in tasks/bp/t2-datatable-csv-export/aids/
# author_DT_baselines.py - the offline oracle asserts the two match, and the
# authoring aid seeds the committed .uasset baselines from its copy.
PINNED_CSVS = {
    "items": (
        '---,DisplayName,Cost,Weight\n'
        'Sword,"Iron Sword",250,8.5\n'
        'Shield,"Oak Shield",180,12.25\n'
        'Potion,"Healing Draught",35,0.5\n'
        'Torch,"Pine Torch",12,1.75\n'
    ),
    "waves": (
        '---,EnemyCount,SpawnInterval\n'
        'Wave1,5,2.5\n'
        'Wave2,9,1.75\n'
        'Wave3,14,1.25\n'
    ),
    "tuning": (
        '---,Value\n'
        'PlayerSpeed,640\n'
        'JumpHeight,420\n'
    ),
}

# --- The check ids, in emission order. Length is the score denominator. ------
CHECK_IDS = (
    "items_csv_present",
    "items_csv_parses",
    "items_rows_match",
    "items_values_match",
    "waves_csv_present",
    "waves_csv_parses",
    "waves_rows_match",
    "waves_values_match",
    "tuning_csv_present",
    "tuning_csv_parses",
    "tuning_rows_match",
    "tuning_values_match",
    "no_extra_csvs",
)


# --------------------------------------------------------------------------- #
# verdict plumbing                                                             #
# --------------------------------------------------------------------------- #

def check(check_id, passed, detail=""):
    return {"id": str(check_id), "passed": bool(passed), "detail": str(detail)}


def emit_verdict(checks):
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
# filesystem resolution                                                        #
# --------------------------------------------------------------------------- #

def _content_dir():
    """Absolute path of the graded project's Content/ directory."""
    raw = unreal.Paths.project_content_dir()
    try:
        full = unreal.Paths.convert_relative_path_to_full(raw)
    except Exception:  # noqa: BLE001 - older spelling; abspath is equivalent
        full = os.path.abspath(str(raw))
    return str(full)


def _exports_dir():
    return os.path.join(_content_dir(), "Tasks", TASK_ID, "exports")


def _read_text(path):
    """File text, tolerating a UTF-8 BOM. Raises on unreadable bytes/IO."""
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


# --------------------------------------------------------------------------- #
# csv structure helpers (pure python; no unreal)                               #
# --------------------------------------------------------------------------- #

def _parse_csv(text):
    """[[cells...], ...] with blank lines dropped. Raises on csv errors."""
    rows = [row for row in csv.reader(io.StringIO(text))
            if row and any(cell.strip() for cell in row)]
    return rows


def _structure_report(rows):
    """(ok, why) - a header plus consistently-shaped data lines."""
    if not rows:
        return False, "no rows at all"
    width = len(rows[0])
    if width < 2:
        return False, "header has %d column(s); a row-name column plus at " \
                      "least one field column is required" % width
    for i, row in enumerate(rows[1:], start=2):
        if len(row) != width:
            return False, "line %d has %d cell(s), header has %d" \
                          % (i, len(row), width)
    return True, "cols=%d datarows=%d" % (width, len(rows) - 1)


def _row_names(rows):
    return [row[0].strip() for row in rows[1:]]


def _pinned_rows(key):
    return _parse_csv(PINNED_CSVS[key])


def _pinned_row_names(key):
    return sorted(_row_names(_pinned_rows(key)))


# --------------------------------------------------------------------------- #
# engine-side helpers                                                          #
# --------------------------------------------------------------------------- #

def _load_table(key):
    """(table, None) or (None, root_cause_token). Fail-closed.

    The overlay is copy-only (no wipe), so a submission cannot DELETE a
    committed baseline - absence is verifier-side, never agent evidence.
    """
    path = TABLE_ASSET[key]
    prefix = key.upper()
    try:
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            return None, "%s_TABLE_MISSING %s" % (prefix, path)
        table = unreal.EditorAssetLibrary.load_asset(path)
        if table is None:
            return None, "%s_TABLE_LOAD_FAILED %s" % (prefix, path)
        return table, None
    except Exception as e:  # noqa: BLE001
        return None, "%s_TABLE_PROBE_ERROR %s raised %r" % (prefix, path, e)


def _canonical_export(table):
    """The engine's own CSV rendering of a table. Raises if unavailable."""
    fn = getattr(unreal.DataTableFunctionLibrary,
                 "export_data_table_to_csv_string", None)
    if fn is None:
        raise AttributeError("export_data_table_to_csv_string unavailable")
    out = fn(table)
    if isinstance(out, (tuple, list)):
        out = out[-1] if out else ""
    return str(out)


def _canon_forms(csv_text):
    """(header_line, sorted_data_lines) - the order-insensitive canonical form."""
    lines = [ln.rstrip("\r") for ln in str(csv_text).splitlines()
             if ln.strip()]
    if not lines:
        return "", []
    return lines[0], sorted(lines[1:])


def _row_struct_for(key, live_table):
    """The row struct for transient tables: the live table's if readable,
    else the module's struct by script path. Raises when neither resolves."""
    if live_table is not None:
        try:
            struct = live_table.get_editor_property("row_struct")
            if struct is not None:
                return struct
        except Exception:  # noqa: BLE001 - fall through to the script path
            pass
    struct = unreal.load_object(None, STRUCT_PATH[key])
    if struct is None:
        raise RuntimeError("row struct unresolvable: %s" % STRUCT_PATH[key])
    return struct


def _transient_table(row_struct):
    """A TRANSIENT DataTable with ``row_struct``. Raises when unavailable;
    never saved, never registered as an asset.

    ``RowStruct`` is ``VisibleAnywhere`` (EditConst), so
    ``set_editor_property`` may refuse it - the plain-attribute assignment is
    tried FIRST (the kp- ``skm.skeleton = skel`` precedent), then the
    property route, and the write is verified by reading back.
    """
    transient = unreal.new_object(unreal.DataTable)
    if transient is None:
        raise RuntimeError("new_object(DataTable) returned None")
    try:
        transient.row_struct = row_struct
    except Exception:  # noqa: BLE001 - fall through to the property route
        transient.set_editor_property("row_struct", row_struct)
    got = transient.get_editor_property("row_struct")
    if got != row_struct:
        raise RuntimeError("row_struct assignment did not stick")
    return transient


def _fill_from_csv(table, csv_text):
    """Engine importer verdict for ``csv_text``. True/False from the engine;
    raises only when the API itself is broken."""
    res = unreal.DataTableFunctionLibrary.fill_data_table_from_csv_string(
        table, csv_text)
    if isinstance(res, (tuple, list)):
        res = res[0] if res else False
    return bool(res)


def _canon_of_csv_text(key, live_table, csv_text, refusal_is_error=True):
    """The engine-canonical (header, sorted_lines) of arbitrary CSV text, via
    a transient fill + export. Raises RuntimeError('REFUSED') when the
    importer rejects the text and ``refusal_is_error``; returns None on a
    tolerated refusal."""
    struct = _row_struct_for(key, live_table)
    transient = _transient_table(struct)
    if not _fill_from_csv(transient, csv_text):
        if refusal_is_error:
            raise RuntimeError("REFUSED")
        return None
    return _canon_forms(_canonical_export(transient))


# --------------------------------------------------------------------------- #
# the fallback semantic compare (pure python)                                  #
# --------------------------------------------------------------------------- #

def _cells_equal(a, b):
    a, b = a.strip(), b.strip()
    if a == b:
        return True
    a2 = a[1:-1] if len(a) >= 2 and a[0] == a[-1] == '"' else a
    b2 = b[1:-1] if len(b) >= 2 and b[0] == b[-1] == '"' else b
    if a2 == b2:
        return True
    try:
        return float(a2) == float(b2)
    except (TypeError, ValueError):
        return False


def _row_dicts(rows):
    """{row_name: {column_name: cell}} from parsed csv rows. The first header
    cell (the row-name column label) is producer-defined and ignored."""
    header = [c.strip() for c in rows[0][1:]]
    out = {}
    for row in rows[1:]:
        out[row[0].strip()] = dict(zip(header, [c for c in row[1:]]))
    return out


def _dict_compare(expected_rows, got_rows):
    """(ok, mismatches) comparing two _row_dicts structures."""
    mismatches = []
    for name in sorted(set(expected_rows) | set(got_rows)):
        if name not in got_rows:
            mismatches.append("row %s absent from submission" % name)
            continue
        if name not in expected_rows:
            mismatches.append("row %s not in the pinned table" % name)
            continue
        exp, got = expected_rows[name], got_rows[name]
        for col in sorted(set(exp) | set(got)):
            if col not in got:
                mismatches.append("%s.%s absent" % (name, col))
            elif col not in exp:
                mismatches.append("%s.%s unexpected" % (name, col))
            elif not _cells_equal(exp[col], got[col]):
                mismatches.append("%s.%s=%s expected %s"
                                  % (name, col, got[col].strip(),
                                     exp[col].strip()))
    return not mismatches, mismatches


# --------------------------------------------------------------------------- #
# the values gate: tamper first, then agent-vs-pinned                          #
# --------------------------------------------------------------------------- #

def _tamper_report(key, live_table):
    """(tampered, report) - does the LIVE table still match the PINNED truth?

    Route 1: engine-canonical both sides (live export vs pinned-through-
    transient export). Route 2 (transient route broken): dict-compare the
    live table's own export against the pinned parse - still engine-exported
    on the live side. Raises when even that is unavailable; the caller fails
    closed. Never resolves to "not tampered" on a broken probe.
    """
    live_canon = _canon_forms(_canonical_export(live_table))
    try:
        pinned_canon = _canon_of_csv_text(key, live_table, PINNED_CSVS[key])
        if live_canon == pinned_canon:
            return False, "live_matches_pinned rows=%d" % len(live_canon[1])
        live_only = [ln for ln in live_canon[1] if ln not in pinned_canon[1]][:3]
        pinned_only = [ln for ln in pinned_canon[1] if ln not in live_canon[1]][:3]
        return True, ("table_diverges_from_pinned live_only=%s pinned_only=%s"
                      % (live_only, pinned_only))
    except Exception:  # noqa: BLE001 - transient route broken: dict fallback
        expected = _row_dicts(_pinned_rows(key))
        live_rows = _parse_csv("\n".join([live_canon[0]] + list(live_canon[1])))
        ok, mismatches = _dict_compare(expected, _row_dicts(live_rows))
        if ok:
            return False, ("live_matches_pinned rows=%d route=fallback"
                           % max(len(live_rows) - 1, 0))
        return True, "table_diverges_from_pinned mismatches=%s" % mismatches[:4]


def _values_check(key, agent_text, results):
    cid = "%s_values_match" % key
    prefix = key.upper()

    # --- the tamper gate (agent-caused by construction; graded) -------------
    live_table, root_cause = _load_table(key)
    if live_table is None:
        # Copy-only overlay: absence is verifier-side. Uncreditable, but it
        # still GRADES as a failed check (set-convention honesty note).
        results[cid] = check(cid, False, root_cause)
        return
    try:
        tampered, tamper_report = _tamper_report(key, live_table)
    except Exception as e:  # noqa: BLE001 - unresolvable gate: fail closed
        results[cid] = check(
            cid, False, "%s_TAMPER_PROBE_ERROR raised %r" % (prefix, e))
        return
    if tampered:
        results[cid] = check(
            cid, False, "%s_BASELINE_TAMPERED %s" % (prefix, tamper_report))
        return

    # --- the agent gate: file vs PINNED truth --------------------------------
    roundtrip_error = None
    try:
        agent_canon = _canon_of_csv_text(key, live_table, agent_text,
                                         refusal_is_error=False)
        if agent_canon is None:
            results[cid] = check(
                cid, False,
                "%s_CSV_NOT_INGESTIBLE the engine importer rejected %s"
                % (prefix, EXPORT_REL[key]))
            return
        pinned_canon = _canon_of_csv_text(key, live_table, PINNED_CSVS[key])
        if agent_canon == pinned_canon:
            results[cid] = check(
                cid, True, "%s_VALUES_OK rows=%d roundtrip=engine"
                % (prefix, len(agent_canon[1])))
            return
        pinned_only = [ln for ln in pinned_canon[1]
                       if ln not in agent_canon[1]][:3]
        sub_only = [ln for ln in agent_canon[1]
                    if ln not in pinned_canon[1]][:3]
        header_note = ("" if agent_canon[0] == pinned_canon[0]
                       else " header_differs=1")
        results[cid] = check(
            cid, False,
            "%s_VALUES_WRONG mismatches=pinned_only=%s submission_only=%s%s"
            % (prefix, pinned_only, sub_only, header_note))
        return
    except Exception as e:  # noqa: BLE001
        roundtrip_error = repr(e)

    # Route 2: pure-python dict compare against the pinned truth.
    try:
        expected = _row_dicts(_pinned_rows(key))
        got = _row_dicts(_parse_csv(agent_text))
        ok, mismatches = _dict_compare(expected, got)
        if ok:
            results[cid] = check(
                cid, True, "%s_VALUES_OK rows=%d roundtrip=fallback"
                % (prefix, len(got)))
        else:
            results[cid] = check(
                cid, False,
                "%s_VALUES_WRONG mismatches=%s" % (prefix, mismatches[:4]))
        return
    except Exception as e:  # noqa: BLE001
        results[cid] = check(
            cid, False,
            "%s_ROUNDTRIP_PROBE_ERROR route1 %s route2 %r"
            % (prefix, roundtrip_error, e))


# --------------------------------------------------------------------------- #
# per-table checks                                                             #
# --------------------------------------------------------------------------- #

def _table_checks(key, results):
    """All four checks for one table."""
    prefix = key.upper()
    rel = EXPORT_REL[key]
    cid_present = "%s_csv_present" % key
    cid_parses = "%s_csv_parses" % key
    cid_rows = "%s_rows_match" % key
    cid_values = "%s_values_match" % key

    # --- present (pure filesystem) -------------------------------------------
    path = None
    try:
        path = os.path.join(_exports_dir(), EXPORT_NAME[key])
        present = os.path.isfile(path)
    except Exception as e:  # noqa: BLE001
        root = "%s_EXPORT_PROBE_ERROR raised %r" % (prefix, e)
        for cid in (cid_present, cid_parses, cid_rows, cid_values):
            results[cid] = check(cid, False, root)
        return
    if not present:
        root = "%s_CSV_MISSING %s" % (prefix, rel)
        for cid in (cid_present, cid_parses, cid_rows, cid_values):
            results[cid] = check(cid, False, root)
        return
    results[cid_present] = check(cid_present, True, "%s_CSV_OK %s"
                                 % (prefix, rel))

    # --- parses (pure python structure) --------------------------------------
    text, rows = None, None
    try:
        text = _read_text(path)
        rows = _parse_csv(text)
        ok, why = _structure_report(rows)
        results[cid_parses] = check(
            cid_parses, ok,
            ("%s_PARSE_OK %s" % (prefix, why)) if ok
            else ("%s_CSV_UNPARSEABLE %s in %s" % (prefix, why, rel)))
        if not ok:
            rows = None
    except Exception as e:  # noqa: BLE001
        results[cid_parses] = check(
            cid_parses, False,
            "%s_CSV_UNPARSEABLE read failed %r in %s" % (prefix, e, rel))
        rows = None
    if rows is None:
        fanout = results[cid_parses]["detail"]
        for cid in (cid_rows, cid_values):
            results[cid] = check(cid, False, fanout)
        return

    # --- rows vs the PINNED truth (pure python; engine-independent) ----------
    try:
        expected_names = _pinned_row_names(key)
        got_names = sorted(_row_names(rows))
        ok = got_names == expected_names
        results[cid_rows] = check(
            cid_rows, ok,
            ("%s_ROWS_OK rows=%s" % (prefix, got_names)) if ok
            else ("%s_ROWS_WRONG got=%s expected=%s"
                  % (prefix, got_names, expected_names)))
    except Exception as e:  # noqa: BLE001
        results[cid_rows] = check(
            cid_rows, False, "%s_ROWS_READ_ERROR raised %r" % (prefix, e))

    # --- values: tamper gate + agent-vs-pinned (engine round-trip) -----------
    _values_check(key, text, results)


def _extras_check(results):
    """exports/ carries the three expected files and nothing else."""
    cid = "no_extra_csvs"
    try:
        directory = _exports_dir()
        if not os.path.isdir(directory):
            results[cid] = check(
                cid, False, "EXPORTS_DIR_ABSENT %s" % EXPORTS_DIR_REL)
            return
        entries = sorted(os.listdir(directory))
        extras = [e for e in entries if e not in EXPECTED_FILES]
        results[cid] = check(
            cid, not extras,
            ("EXPORTS_DIR_OK files=%s" % entries) if not extras
            else ("EXPORTS_DIR_EXTRA_FILES files=%s expected_only=%s"
                  % (extras, list(EXPECTED_FILES))))
    except Exception as e:  # noqa: BLE001
        results[cid] = check(
            cid, False, "EXPORTS_DIR_PROBE_ERROR raised %r" % (e,))


def main():
    results = {}
    for key, _name in TABLES:
        try:
            _table_checks(key, results)
        except Exception as e:  # noqa: BLE001 - never abort the verdict
            root = "%s_INTROSPECTION_ABORTED %r" % (key.upper(), e)
            for cid in ("%s_csv_present" % key, "%s_csv_parses" % key,
                        "%s_rows_match" % key, "%s_values_match" % key):
                if cid not in results:
                    results[cid] = check(cid, False, root)
    try:
        _extras_check(results)
    except Exception as e:  # noqa: BLE001
        if "no_extra_csvs" not in results:
            results["no_extra_csvs"] = check(
                "no_extra_csvs", False,
                "EXPORTS_INTROSPECTION_ABORTED %r" % (e,))

    checks = [results.get(cid) or check(cid, False, "CHECK_NOT_EVALUATED %s" % cid)
              for cid in CHECK_IDS]
    emit_verdict(checks)


if __name__ == "__main__":
    main()
