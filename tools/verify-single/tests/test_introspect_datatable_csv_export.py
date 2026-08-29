"""Offline oracle for the t2-datatable-csv-export L2I grader.

No editor, no UE install, no tokens. A minimal fake ``unreal`` module models
the engine surface the introspect script actually uses (asset loads, the
DataTable row-name read, the CSV importer/exporter pair, transient-object
construction, path resolution), so every leg of ``discrimination/MATRIX.md``
can be simulated and joined against the REAL ``discriminate.parse_matrix`` +
the REAL ``layers/l2_introspect`` parser.

The legs read the SHIPPED artifacts: the reference and variant CSV files come
straight from the task tree, and the fake baselines are filled from the
``BASELINE_CSVS`` literals in ``aids/author_DT_baselines.py`` — the same
single source of truth the binary half will use. Content drift between the
aids script, the reference files and the variants therefore fails HERE,
offline, before any editor session.

What this pins:
  * every negative leg's MATRIX substring is a literal the script PRINTS, on
    the check the MATRIX blames;
  * the round-trip acceptance really is order/formatting-insensitive (a
    row-reordered, requoted reference still passes) while a single changed
    value fails;
  * baseline-table absence is an UNCREDITED verifier-side token, never a
    variant's named failure, and never blocks the filesystem checks;
  * an engine importer that refuses the CSV is the graded NOT_INGESTIBLE
    failure; a broken exporter degrades to the dict-compare fallback and only
    a double break reports the PROBE_ERROR token;
  * a constant denominator of 13 on every leg, including with no ``unreal``.

The fake is deliberately dumb: tables are {row_name: [cell, ...]} with a
header list, the "engine" importer/exporter round-trip is the csv module, and
nothing else is modeled. It cannot prove the UE API names are right — only a
live editor does that (the aids script's stage-1/2 in-process grades) — but it
does prove the grader's LOGIC and its printed tokens.
"""
import contextlib
import importlib.util
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_VERIFY = _TESTS.parent
_REPO = _VERIFY.parent.parent

sys.path.insert(0, str(_VERIFY))
sys.path.insert(0, str(_REPO / "tools" / "run-agent"))

from layers.l2_introspect import parse_introspect_verdict  # noqa: E402
from aura_rig.discriminate import parse_matrix  # noqa: E402

TASK_DIR = _REPO / "tasks" / "bp" / "t2-datatable-csv-export"
MATRIX_PATH = TASK_DIR / "discrimination" / "MATRIX.md"
SCRIPT_PATH = _VERIFY / "introspect" / "datatable_csv_export.py"
AIDS_PATH = TASK_DIR / "aids" / "author_DT_baselines.py"
EXPORT_REL = Path("Content") / "Tasks" / "t2-datatable-csv-export" / "exports"


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module(SCRIPT_PATH, "_dt_export_introspect")
AIDS = _load_module(AIDS_PATH, "_dt_export_aids")

import csv as _csv  # noqa: E402  (used by the fake engine)


# --------------------------------------------------------------------------- #
# the fake unreal module                                                       #
# --------------------------------------------------------------------------- #

class FakeTable:
    def __init__(self, header, rows, row_struct="S"):
        self.header = list(header)          # field columns, no row-name col
        self.rows = dict(rows)              # row_name -> [cell, ...]
        self.row_struct = row_struct

    def get_editor_property(self, prop):
        if prop == "row_struct":
            return self.row_struct
        raise Exception("unknown property %r" % (prop,))

    def set_editor_property(self, prop, value):
        if prop == "row_struct":
            self.row_struct = value
            return
        raise Exception("unknown property %r" % (prop,))


def _table_from_csv_text(text):
    rows = [r for r in _csv.reader(io.StringIO(text))
            if r and any(c.strip() for c in r)]
    return FakeTable(rows[0][1:], {r[0]: r[1:] for r in rows[1:]})


class _World:
    def __init__(self):
        self.assets = {}            # /Game path -> FakeTable
        self.content_dir = None     # str, per-leg temp dir
        self.fill_result = None     # None=normal, False=refuse
        self.export_broken = False  # exporter raises when True
        self.new_object_broken = False


WORLD = _World()


class _EditorAssetLibrary:
    @staticmethod
    def does_asset_exist(path):
        return path in WORLD.assets

    @staticmethod
    def load_asset(path):
        return WORLD.assets.get(path)


class _DataTableFunctionLibrary:
    @staticmethod
    def get_data_table_row_names(table):
        return list(table.rows)

    @staticmethod
    def fill_data_table_from_csv_string(table, text):
        if WORLD.fill_result is False:
            return False
        try:
            parsed = _table_from_csv_text(text)
        except Exception:  # noqa: BLE001
            return False
        if not parsed.header:
            return False
        table.header = parsed.header
        table.rows = parsed.rows
        return True

    @staticmethod
    def export_data_table_to_csv_string(table):
        if WORLD.export_broken:
            raise RuntimeError("exporter unavailable in this fake")
        buf = io.StringIO()
        writer = _csv.writer(buf, lineterminator="\n")
        writer.writerow(["---"] + list(table.header))
        for name, cells in table.rows.items():
            writer.writerow([name] + list(cells))
        return buf.getvalue()


class _Paths:
    @staticmethod
    def project_content_dir():
        return WORLD.content_dir

    @staticmethod
    def convert_relative_path_to_full(path):
        return path


def _new_object(cls):
    if WORLD.new_object_broken:
        raise RuntimeError("new_object unavailable in this fake")
    return FakeTable([], {}, row_struct=None)


class FakeUnreal:
    EditorAssetLibrary = _EditorAssetLibrary
    DataTableFunctionLibrary = _DataTableFunctionLibrary
    Paths = _Paths
    DataTable = FakeTable
    new_object = staticmethod(_new_object)

    @staticmethod
    def log(msg):
        pass


# --------------------------------------------------------------------------- #
# leg builders                                                                 #
# --------------------------------------------------------------------------- #

def _baselines():
    """Fake live tables filled from the aids script's pinned literals."""
    for name, text in AIDS.BASELINE_CSVS.items():
        for key, asset_name in MOD.TABLES:
            if asset_name == name:
                WORLD.assets[MOD.TABLE_ASSET[key]] = _table_from_csv_text(text)


def _overlay(tree):
    """Copy a submission tree's exports/ into the fake content dir."""
    src = tree / EXPORT_REL
    if not src.is_dir():
        return
    dst = Path(WORLD.content_dir) / "Tasks" / MOD.TASK_ID / "exports"
    shutil.copytree(src, dst, dirs_exist_ok=True)


LEGS = {}


def _leg(name):
    def deco(fn):
        LEGS[name] = fn
        return fn
    return deco


@_leg("reference")
def _reference():
    _baselines()
    _overlay(TASK_DIR / "reference")


@_leg("empty")
def _empty():
    _baselines()


@_leg("wrong-values")
def _wrong_values():
    _baselines()
    _overlay(TASK_DIR / "discrimination" / "wrong-values")


@_leg("missing-table")
def _missing_table():
    _baselines()
    _overlay(TASK_DIR / "discrimination" / "missing-table")


@_leg("header-only")
def _header_only():
    _baselines()
    _overlay(TASK_DIR / "discrimination" / "header-only")


def run_leg(builder, unreal_module=FakeUnreal, mutate=None):
    global WORLD
    WORLD = _World()
    tmp = tempfile.mkdtemp(prefix="cb-dtexport-")
    WORLD.content_dir = tmp
    MOD.unreal = unreal_module
    try:
        builder()
        if mutate is not None:
            mutate()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            MOD.main()
        out = buf.getvalue()
        return out, parse_introspect_verdict(out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _by_id(parsed):
    return {c.id: c for c in parsed.checks}


# --------------------------------------------------------------------------- #
# tests                                                                        #
# --------------------------------------------------------------------------- #

class TestMatrixIsCreditable(unittest.TestCase):
    """Every MATRIX row must be parseable AND its substring actually printed."""

    def setUp(self):
        self.rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))

    def test_every_declared_leg_has_a_row(self):
        self.assertEqual(set(self.rows), set(LEGS))

    def test_no_negative_leg_has_a_blank_substring_tuple(self):
        blank = sorted(k for k, v in self.rows.items()
                       if not v.expect_pass and not v.substrings)
        self.assertEqual(blank, [], "these legs can never be credited")

    def test_no_substring_carries_backticks(self):
        for label, row in self.rows.items():
            for s in row.substrings:
                self.assertNotIn("`", s,
                                 "%s: backticks never match log text" % label)

    def test_reference_leg_passes_all_thirteen(self):
        out, parsed = run_leg(LEGS["reference"])
        self.assertTrue(parsed.found)
        self.assertEqual(parsed.total, 13)
        failed = [(c.id, c.detail) for c in parsed.checks if not c.passed]
        self.assertEqual(failed, [], out)

    def test_every_leg_reports_the_same_thirteen_checks(self):
        for label, builder in LEGS.items():
            with self.subTest(leg=label):
                _, parsed = run_leg(builder)
                self.assertEqual(parsed.total, 13)
                self.assertEqual([c.id for c in parsed.checks],
                                 list(MOD.CHECK_IDS))

    def test_every_negative_leg_fails_with_its_named_substring(self):
        for label, builder in LEGS.items():
            row = self.rows[label]
            if row.expect_pass:
                continue
            with self.subTest(leg=label):
                out, parsed = run_leg(builder)
                self.assertTrue(parsed.found)
                self.assertLess(parsed.passed_count, 13, "expected a FAIL")
                details = "\n".join(c.detail for c in parsed.checks
                                    if not c.passed)
                for sub in row.substrings:
                    self.assertIn(sub, details,
                                  "%s: MATRIX substring never printed" % label)

    def test_named_substring_lands_on_the_predicted_check(self):
        expected = {
            "empty": "items_csv_present",
            "missing-table": "tuning_csv_present",
            "wrong-values": "waves_values_match",
            "header-only": "items_rows_match",
        }
        self.assertEqual(set(expected) | {"reference"}, set(LEGS))
        for label, check_id in expected.items():
            with self.subTest(leg=label):
                _, parsed = run_leg(LEGS[label])
                got = _by_id(parsed)[check_id]
                self.assertFalse(got.passed)
                for sub in self.rows[label].substrings:
                    self.assertIn(sub, got.detail)

    def test_each_variant_fails_only_its_predicted_family(self):
        budget = {
            "empty": 13,          # nothing shipped: every check fails
            "missing-table": 4,   # the tuning quartet
            "wrong-values": 1,    # exactly the waves values gate
            "header-only": 6,     # rows + values on all three tables
        }
        for label, allowed in budget.items():
            with self.subTest(leg=label):
                _, parsed = run_leg(LEGS[label])
                failed = [c.id for c in parsed.checks if not c.passed]
                self.assertEqual(len(failed), allowed, failed)


class TestRoundTripSemantics(unittest.TestCase):
    """The acceptance is semantic, not textual."""

    def _reference_with_items_rewritten(self, rewrite):
        def build():
            _baselines()
            _overlay(TASK_DIR / "reference")
            path = (Path(WORLD.content_dir) / "Tasks" / MOD.TASK_ID /
                    "exports" / "DT_EvalItems.csv")
            path.write_text(rewrite(path.read_text(encoding="utf-8")),
                            encoding="utf-8")
        return build

    def test_row_order_does_not_matter(self):
        def reorder(text):
            lines = [ln for ln in text.splitlines() if ln.strip()]
            return "\n".join([lines[0]] + list(reversed(lines[1:]))) + "\n"
        _, parsed = run_leg(self._reference_with_items_rewritten(reorder))
        got = _by_id(parsed)["items_values_match"]
        self.assertTrue(got.passed, got.detail)

    def test_a_single_changed_value_fails_values_only(self):
        def corrupt(text):
            return text.replace("250", "999")
        _, parsed = run_leg(self._reference_with_items_rewritten(corrupt))
        by_id = _by_id(parsed)
        self.assertFalse(by_id["items_values_match"].passed)
        self.assertIn("ITEMS_VALUES_WRONG mismatches=",
                      by_id["items_values_match"].detail)
        self.assertTrue(by_id["items_rows_match"].passed)

    def test_a_renamed_row_fails_the_rows_gate(self):
        def rename(text):
            return text.replace("Torch,", "Lantern,")
        _, parsed = run_leg(self._reference_with_items_rewritten(rename))
        got = _by_id(parsed)["items_rows_match"]
        self.assertFalse(got.passed)
        self.assertIn("ITEMS_ROWS_WRONG got=", got.detail)


class TestPinnedTruthDefeatsBaselineTampering(unittest.TestCase):
    """The gold-leak defense: rewriting the agent-writable baselines can
    never make a capability-free submission pass."""

    def _tampered_build(self, submission):
        def build():
            _baselines()
            for key, _name in MOD.TABLES:
                # A valid-but-EMPTY table overlaid onto data/ - exactly what
                # an editor-tooled agent could submit.
                live = WORLD.assets[MOD.TABLE_ASSET[key]]
                WORLD.assets[MOD.TABLE_ASSET[key]] = FakeTable(
                    live.header, {}, live.row_struct)
            _overlay(TASK_DIR / "discrimination" / submission)
        return build

    def test_empty_tables_plus_header_only_csvs_fail_with_the_tamper_token(self):
        _, parsed = run_leg(self._tampered_build("header-only"))
        by_id = _by_id(parsed)
        self.assertLess(parsed.passed_count, 13,
                        "the tampered leg must never reach 13/13")
        for key in ("items", "waves", "tuning"):
            values = by_id["%s_values_match" % key]
            self.assertFalse(values.passed)
            self.assertIn("%s_BASELINE_TAMPERED" % key.upper(), values.detail)
            self.assertIn("table_diverges_from_pinned", values.detail)
            # rows compare against the PINNED truth, not the gutted table.
            self.assertFalse(by_id["%s_rows_match" % key].passed)
            self.assertIn("%s_ROWS_WRONG got=" % key.upper(),
                          by_id["%s_rows_match" % key].detail)

    def test_tampered_tables_fail_even_a_correct_looking_reference(self):
        # Tampering alone is a graded failure - even with pinned-perfect CSVs.
        def build():
            _baselines()
            live = WORLD.assets[MOD.TABLE_ASSET["waves"]]
            rows = dict(live.rows)
            rows["Wave2"] = ["7", "1.75"]
            WORLD.assets[MOD.TABLE_ASSET["waves"]] = FakeTable(
                live.header, rows, live.row_struct)
            _overlay(TASK_DIR / "reference")
        _, parsed = run_leg(build)
        got = _by_id(parsed)["waves_values_match"]
        self.assertFalse(got.passed)
        self.assertIn("WAVES_BASELINE_TAMPERED", got.detail)

    def test_tamper_token_never_appears_on_clean_legs(self):
        for label, builder in LEGS.items():
            with self.subTest(leg=label):
                _, parsed = run_leg(builder)
                details = "\n".join(c.detail for c in parsed.checks)
                self.assertNotIn("_BASELINE_TAMPERED", details)

    def test_grader_pinned_truth_matches_the_aids_literals(self):
        """One source of truth, three copies (grader / aids / reference) -
        the grader-vs-aids half of the drift guard."""
        name_by_key = dict(MOD.TABLES)
        for key, _name in MOD.TABLES:
            self.assertEqual(MOD.PINNED_CSVS[key],
                             AIDS.BASELINE_CSVS[name_by_key[key]], key)


class TestFailsClosed(unittest.TestCase):
    """No check may pass because a probe merely did not raise."""

    def test_missing_baseline_hits_only_the_values_gate(self):
        # rows_match now compares against the PINNED truth, so a missing
        # baseline (verifier-side: the overlay cannot delete) fails exactly
        # the tamper-gated values check, with the uncreditable token.
        def build():
            _baselines()
            del WORLD.assets[MOD.TABLE_ASSET["items"]]
            _overlay(TASK_DIR / "reference")
        _, parsed = run_leg(build)
        by_id = _by_id(parsed)
        self.assertTrue(by_id["items_csv_present"].passed)
        self.assertTrue(by_id["items_csv_parses"].passed)
        self.assertTrue(by_id["items_rows_match"].passed)
        self.assertFalse(by_id["items_values_match"].passed)
        self.assertIn("ITEMS_TABLE_MISSING /Game/Tasks/",
                      by_id["items_values_match"].detail)

    def test_importer_refusal_is_the_graded_not_ingestible_failure(self):
        # A refusing importer also breaks the tamper gate's transient route;
        # the gate's dict fallback (live export vs pinned) keeps it resolved,
        # and the agent gate then reports the graded refusal.
        def mutate():
            WORLD.fill_result = False
        _, parsed = run_leg(LEGS["reference"], mutate=mutate)
        got = _by_id(parsed)["items_values_match"]
        self.assertFalse(got.passed)
        self.assertIn("ITEMS_CSV_NOT_INGESTIBLE", got.detail)

    def test_broken_exporter_is_an_unresolvable_tamper_gate_not_a_pass(self):
        # Exporter raises -> the tamper gate cannot read the live table ->
        # TAMPER_PROBE_ERROR, uncredited, still a graded FAIL.
        def mutate():
            WORLD.export_broken = True
        _, parsed = run_leg(LEGS["reference"], mutate=mutate)
        got = _by_id(parsed)["items_values_match"]
        self.assertFalse(got.passed)
        self.assertIn("ITEMS_TAMPER_PROBE_ERROR", got.detail)

    def test_broken_transient_construction_uses_the_dict_fallback(self):
        def mutate():
            WORLD.new_object_broken = True
        _, parsed = run_leg(LEGS["reference"], mutate=mutate)
        got = _by_id(parsed)["items_values_match"]
        self.assertTrue(got.passed, got.detail)
        self.assertIn("roundtrip=fallback", got.detail)

    def test_extra_file_in_exports_fails_the_extras_gate_only(self):
        def build():
            _baselines()
            _overlay(TASK_DIR / "reference")
            stray = (Path(WORLD.content_dir) / "Tasks" / MOD.TASK_ID /
                     "exports" / "combined_dump.csv")
            stray.write_text("a,b\n1,2\n", encoding="utf-8")
        _, parsed = run_leg(build)
        by_id = _by_id(parsed)
        self.assertFalse(by_id["no_extra_csvs"].passed)
        self.assertIn("EXPORTS_DIR_EXTRA_FILES files=",
                      by_id["no_extra_csvs"].detail)
        others = [c for c in parsed.checks
                  if c.id != "no_extra_csvs" and not c.passed]
        self.assertEqual(others, [])

    def test_unparseable_file_fans_out_to_rows_and_values(self):
        def build():
            _baselines()
            _overlay(TASK_DIR / "reference")
            path = (Path(WORLD.content_dir) / "Tasks" / MOD.TASK_ID /
                    "exports" / "DT_EvalTuning.csv")
            path.write_text('---,Value\n"PlayerSpeed,640\n', encoding="utf-8")
        _, parsed = run_leg(build)
        by_id = _by_id(parsed)
        self.assertFalse(by_id["tuning_csv_parses"].passed)
        self.assertIn("TUNING_CSV_UNPARSEABLE",
                      by_id["tuning_csv_parses"].detail)
        self.assertFalse(by_id["tuning_rows_match"].passed)
        self.assertFalse(by_id["tuning_values_match"].passed)


class TestErrorTokensAreDisjointFromMatrix(unittest.TestCase):
    """An API break must never be creditable as a variant's named failure."""

    def test_no_error_token_appears_in_any_matrix_substring(self):
        rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))
        subs = [s for r in rows.values() for s in r.substrings]
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        tokens = sorted({t for t in re.findall(r"\b[A-Z][A-Z0-9_]{6,}\b", source)
                         if t.endswith(("_ERROR", "_ABORTED", "_MISSING",
                                        "_NOT_EVALUATED", "_LOAD_FAILED"))
                         and not t.endswith("_CSV_MISSING")})
        self.assertTrue(tokens, "expected the script to define error tokens")
        for token in tokens:
            for sub in subs:
                self.assertNotIn(token, sub)

    def test_script_carries_no_automation_result_marker(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("TestResult" + "=Passed", source)
        self.assertNotIn("Automation Test" + " Succeeded", source)

    def test_script_is_pure_ascii(self):
        raw = SCRIPT_PATH.read_bytes()
        self.assertEqual(raw.decode("utf-8"), raw.decode("ascii"))

    def test_matrix_substrings_are_ascii_and_contain_a_space(self):
        rows = parse_matrix(MATRIX_PATH.read_text(encoding="utf-8"))
        for label, row in rows.items():
            for sub in row.substrings:
                sub.encode("ascii")
                self.assertIn(" ", sub,
                              "%s: a space-less tick is dropped by "
                              "_extract_substrings" % label)

    def test_reference_files_match_the_aids_pinned_literals(self):
        """One source of truth: the shipped reference CSVs must parse to the
        same content as the aids script's BASELINE_CSVS."""
        for asset_name, text in AIDS.BASELINE_CSVS.items():
            ref = (TASK_DIR / "reference" / EXPORT_REL /
                   ("%s.csv" % asset_name)).read_text(encoding="utf-8")
            self.assertEqual(_table_from_csv_text(ref).rows,
                             _table_from_csv_text(text).rows, asset_name)

    def test_offline_run_without_unreal_fails_every_check(self):
        global WORLD
        WORLD = _World()
        MOD.unreal = None
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                MOD.main()
            out = buf.getvalue()
            parsed = parse_introspect_verdict(out)
            self.assertEqual(parsed.total, 13)
            self.assertEqual(parsed.passed_count, 0)
            payload = json.loads(out.splitlines()[1])
            self.assertEqual(len(payload["checks"]), 13)
        finally:
            MOD.unreal = FakeUnreal


if __name__ == "__main__":
    unittest.main()
