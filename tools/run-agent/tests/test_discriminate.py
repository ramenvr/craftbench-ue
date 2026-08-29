"""Unit tests for aura_rig.discriminate — the batch DISCRIMINATION runner
(`cb discriminate` / `cb wip`), fully offline.

The ``run_task.py`` subprocess seam is MOCKED everywhere: tests inject a runner
callable returning canned :class:`RunResult`s (or a fake ``subprocess.run`` for
the seam-construction test), so NO Unreal editor, NO git, NO network is touched.
We assert the normative behaviours:

  (1) MATRIX.md parsing of BOTH recorded shapes (the gp-spawn-sequence
      "expected N, found M" prose column, and the gp-inventory-stacking
      backtick-literal substring column).
  (2) Leg assembly from on-disk artifacts (reference required; variants from dirs).
  (3) Aggregation: all-legs-good => discriminated; ANY bad leg => NOT.
  (4) Wrong-reason detection — a variant FAIL whose L2 log lacks the named
      substring (wrong checkpoint), a SUBSTRATE/SANDBOX reject (exit 3/4), a
      SKIPPED L2, and an unexpected PASS all count as NOT discriminated.
  (5) The named-substring match itself (exact substring of the L2 log).
  (6) The from-live decision (committed-clean => from-HEAD; dirty/untracked or
      --wip => from-live), with git mocked.
  (7) Set/id expansion via tasks.discover.

Run from tools/run-agent:  python3 -m unittest tests.test_discriminate -v
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import discriminate as D  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures: the two MATRIX shapes seen in the repo, trimmed to the table.      #
# --------------------------------------------------------------------------- #

MATRIX_SPAWN = """# Discrimination matrix — gp-spawn-sequence

| Submission | Overall | Fails at | Message (expected/found) | Anti-gaming note |
|---|---|---|---|---|
| `tests/reference-solutions/gp-spawn-sequence/` | **PASS** | — | all four checkpoints green | — (PASS oracle) |
| empty stub (any empty dir) | **FAIL** | checkpoint 1 (t=1.5s) | expected 1, found 0 | — (FR-017) |
| `burst-spawn/` | **FAIL** | checkpoint 0 (t=0.5s) | expected 0, found 2 | #1 burst-spawn in BeginPlay |
| `over-spawn/` | **FAIL** | checkpoint 3 (t=3.5s) | expected 2, found 3 | #2 over-spawn |
| `wrong-tag/` | **FAIL** | checkpoint 1 (t=1.5s) | expected 1, found 0 (children tagged `SpawnedClone`) | #3 wrong tag |

Discrimination is confirmed only when the PASS row is green.
"""

MATRIX_INVENTORY = """# gp-inventory-stacking — discrimination matrix

| Submission | Overall | Fails at | Expected message substring | Anti-gaming note |
|---|---|---|---|---|
| `tests/reference-solutions/gp-inventory-stacking` | **PASS** | — | all 5 checkpoints green (1/1) | — (PASS oracle) |
| empty (no overlay → scaffold stub) | **FAIL** | checkpoint 0 (t=0.5s) | `AddItem(Stone,7) returned false; 7 units should fit.` | FR-017 empty |

## Anti-gaming modes
1. Constant return → diverges.
"""


def _ec(report=None, l2_log="", exit_code=0):
    return D.RunResult(exit_code=exit_code, report=report, l2_log=l2_log)


def _l2_report(status="fail", log="x.log"):
    return {"layers": {"L2": {"status": status, "log": log}}}


# --------------------------------------------------------------------------- #
# (1) MATRIX parsing                                                          #
# --------------------------------------------------------------------------- #

class TestMatrixParse(unittest.TestCase):
    def test_spawn_prose_column(self):
        rows = D.parse_matrix(MATRIX_SPAWN)
        self.assertIn("reference", rows)
        self.assertTrue(rows["reference"].expect_pass)
        self.assertIn("empty", rows)
        self.assertFalse(rows["empty"].expect_pass)
        # The "expected N, found M" summary splits into two number-anchored
        # fragments (robust to the engine's verbatim "<thing>; " interpolation).
        self.assertEqual(rows["empty"].substrings, ("expected 1", "found 0"))
        # Variant rows by dir name.
        self.assertEqual(rows["burst-spawn"].substrings, ("expected 0", "found 2"))
        self.assertEqual(rows["over-spawn"].substrings, ("expected 2", "found 3"))
        # The parenthetical `SpawnedClone` tick is dropped; the expected/found wins.
        self.assertEqual(rows["wrong-tag"].substrings, ("expected 1", "found 0"))
        self.assertFalse(rows["wrong-tag"].expect_pass)

    def test_inventory_backtick_literal_column(self):
        rows = D.parse_matrix(MATRIX_INVENTORY)
        self.assertTrue(rows["reference"].expect_pass)
        self.assertEqual(
            rows["empty"].substrings,
            ("AddItem(Stone,7) returned false; 7 units should fit.",),
        )

    def test_reference_row_has_no_substring(self):
        rows = D.parse_matrix(MATRIX_SPAWN)
        self.assertEqual(rows["reference"].substrings, ())

    def test_reference_row_folder_local_forms(self):
        # The folder-per-task layout's MATRIX writes the reference row as a
        # folder-local path: bare, trailing-slash, and ../-relative forms all
        # classify as the reference row (not a variant).
        for cell in ("`reference`", "`reference/`", "`../reference`", "`../reference/`"):
            with self.subTest(cell=cell):
                rows = D.parse_matrix(
                    "| Submission | Overall | Expected message substring |\n"
                    "|--|--|--|\n"
                    f"| {cell} | **PASS** | all green |\n"
                )
                self.assertIn("reference", rows)
                self.assertTrue(rows["reference"].expect_pass)
                self.assertEqual(rows["reference"].substrings, ())

    def test_malformed_matrix_is_tolerant(self):
        self.assertEqual(D.parse_matrix("no table here\njust prose"), {})


class TestExtractSubstrings(unittest.TestCase):
    def test_prefers_backtick_literal(self):
        self.assertEqual(
            D._extract_substrings("`AddItem(Stone,7) returned false; 7 fit.`"),
            ("AddItem(Stone,7) returned false; 7 fit.",),
        )

    def test_drops_short_bareword_tick(self):
        # `SpawnedClone` is a parenthetical id, not the assertion; the
        # "expected/found" summary becomes the two number-anchored fragments.
        self.assertEqual(
            D._extract_substrings("expected 1, found 0 (tagged `SpawnedClone`)"),
            ("expected 1", "found 0"),
        )

    def test_dash_means_none(self):
        self.assertEqual(D._extract_substrings("—"), ())
        self.assertEqual(D._extract_substrings(""), ())


# --------------------------------------------------------------------------- #
# (2) Leg assembly from disk                                                  #
# --------------------------------------------------------------------------- #

class TestBuildLegs(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="disc-legs-"))
        (self.tmp / "tasks").mkdir()
        (self.tmp / "tasks" / "demo.md").write_text("# demo\n", encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _ref(self, tid="demo"):
        d = self.tmp / "tests" / "reference-solutions" / tid
        (d / "Source").mkdir(parents=True)
        return d

    def _variant(self, name, tid="demo"):
        d = self.tmp / "tests" / "discrimination" / tid / name
        (d / "Source").mkdir(parents=True)
        return d

    def test_missing_reference_is_fatal(self):
        legs, err = D.build_legs(self.tmp, "demo")
        self.assertEqual(legs, [])
        self.assertIn("no reference solution", err)

    def test_reference_plus_empty_minimum(self):
        self._ref()
        legs, err = D.build_legs(self.tmp, "demo")
        self.assertIsNone(err)
        kinds = [(l.kind, l.label, l.expect_pass) for l in legs]
        self.assertEqual(kinds, [("reference", "reference", True), ("empty", "empty", False)])

    def test_variants_pull_substrings_from_matrix(self):
        self._ref()
        self._variant("burst-spawn")
        self._variant("over-spawn")
        mdir = self.tmp / "tests" / "discrimination" / "demo"
        (mdir / "MATRIX.md").write_text(
            "| Submission | Overall | Msg | Message (x) |\n|--|--|--|--|\n"
            "| `burst-spawn/` | FAIL | a | expected 0, found 2 |\n"
            "| `over-spawn/`  | FAIL | b | expected 2, found 3 |\n",
            encoding="utf-8",
        )
        legs, err = D.build_legs(self.tmp, "demo")
        self.assertIsNone(err)
        variants = {l.label: l.expected_substrings for l in legs if l.kind == "variant"}
        self.assertEqual(variants["burst-spawn"], ("expected 0", "found 2"))
        self.assertEqual(variants["over-spawn"], ("expected 2", "found 3"))

    def test_variant_without_matrix_row_has_empty_substrings(self):
        self._ref()
        self._variant("mystery")  # no MATRIX.md at all
        legs, _ = D.build_legs(self.tmp, "demo")
        v = [l for l in legs if l.kind == "variant"][0]
        self.assertEqual(v.expected_substrings, ())

    def test_empty_leg_inherits_matrix_substring(self):
        self._ref()
        mdir = self.tmp / "tests" / "discrimination" / "demo"
        mdir.mkdir(parents=True)
        (mdir / "MATRIX.md").write_text(
            "| Submission | Overall | Expected message substring |\n|--|--|--|\n"
            "| empty (stub) | FAIL | `AddItem returned false` |\n",
            encoding="utf-8",
        )
        legs, _ = D.build_legs(self.tmp, "demo")
        empty = [l for l in legs if l.kind == "empty"][0]
        self.assertEqual(empty.expected_substrings, ("AddItem returned false",))

    def test_set_qualified_id_resolves_bare_test_trees(self):
        # BLOCKER 2 regression: a set-qualified id (set/id) addresses its spec at
        # tasks/<set>/<id>.md, but its reference/discrimination packages live at the
        # BARE-id path. build_legs must resolve the test trees to the bare id — else
        # `cb discriminate --task <set>` falsely reports every set task SKIPPED.
        self._ref("gp-thing")                      # tests/reference-solutions/gp-thing/ (BARE)
        self._variant("over-cap", "gp-thing")      # tests/discrimination/gp-thing/over-cap/
        legs, err = D.build_legs(self.tmp, "bp-g2/gp-thing")
        self.assertIsNone(err)                     # pre-fix: "no reference solution at .../bp-g2/gp-thing"
        labels = {l.label for l in legs}
        self.assertIn("reference", labels)
        self.assertIn("over-cap", labels)


class TestBuildLegsFolderLayout(unittest.TestCase):
    """Dual-layout resolution: the folder-per-task form (tasks/<set>/<id>/task.md
    with sibling reference/ + discrimination/) resolves folder-LOCAL packages
    first; a folder-form task without local packages still falls back to the
    legacy tests/... trees."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="disc-legs-folder-"))
        self.task = self.tmp / "tasks" / "concept-1" / "gp-demo"
        self.task.mkdir(parents=True)
        (self.task / "task.md").write_text("# gp-demo\n", encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_folder_local_reference_and_variants_resolve(self):
        (self.task / "reference" / "Source").mkdir(parents=True)
        (self.task / "discrimination" / "burst-spawn" / "Source").mkdir(parents=True)
        (self.task / "discrimination" / "MATRIX.md").write_text(
            "| Submission | Overall | Expected message substring |\n|--|--|--|\n"
            "| `reference/` | **PASS** | all green |\n"
            "| `burst-spawn/` | FAIL | expected 0, found 2 |\n",
            encoding="utf-8",
        )
        legs, err = D.build_legs(self.tmp, "concept-1/gp-demo")
        self.assertIsNone(err)
        by_label = {l.label: l for l in legs}
        self.assertEqual(by_label["reference"].submission, self.task / "reference")
        self.assertEqual(by_label["burst-spawn"].submission,
                         self.task / "discrimination" / "burst-spawn")
        self.assertEqual(by_label["burst-spawn"].expected_substrings,
                         ("expected 0", "found 2"))

    def test_bare_id_resolves_folder_form_task(self):
        (self.task / "reference" / "Source").mkdir(parents=True)
        legs, err = D.build_legs(self.tmp, "gp-demo")  # bare id, unique across sets
        self.assertIsNone(err)
        by_label = {l.label: l for l in legs}
        self.assertEqual(by_label["reference"].submission, self.task / "reference")

    def test_folder_task_falls_back_to_legacy_trees(self):
        # Folder-form spec but NO local reference/discrimination: the legacy
        # tests/reference-solutions/<bare>/ + tests/discrimination/<bare>/ still win.
        ref = self.tmp / "tests" / "reference-solutions" / "gp-demo"
        (ref / "Source").mkdir(parents=True)
        var = self.tmp / "tests" / "discrimination" / "gp-demo" / "wrong-tag"
        (var / "Source").mkdir(parents=True)
        legs, err = D.build_legs(self.tmp, "concept-1/gp-demo")
        self.assertIsNone(err)
        by_label = {l.label: l for l in legs}
        self.assertEqual(by_label["reference"].submission, ref)
        self.assertEqual(by_label["wrong-tag"].submission, var)

    def test_no_reference_anywhere_is_fatal(self):
        legs, err = D.build_legs(self.tmp, "concept-1/gp-demo")
        self.assertEqual(legs, [])
        self.assertIn("no reference solution", err)


# --------------------------------------------------------------------------- #
# (3)+(4)+(5) grade_leg: aggregation, wrong-reason, named-substring           #
# --------------------------------------------------------------------------- #

class TestGradeReference(unittest.TestCase):
    def test_reference_pass_discriminates(self):
        spec = D.LegSpec(kind="reference", label="reference", submission=Path("r"), expect_pass=True)
        out = D.grade_leg(spec, _ec(exit_code=0))
        self.assertTrue(out.discriminated)
        self.assertEqual(out.cell, "PASS")

    def test_reference_fail_does_not_discriminate(self):
        spec = D.LegSpec(kind="reference", label="reference", submission=Path("r"), expect_pass=True)
        out = D.grade_leg(spec, _ec(report=_l2_report("fail"), exit_code=1))
        self.assertFalse(out.discriminated)
        self.assertEqual(out.detail, "did-not-pass")

    def test_reference_substrate_reject_is_wrong_reason(self):
        spec = D.LegSpec(kind="reference", label="reference", submission=Path("r"), expect_pass=True)
        out = D.grade_leg(spec, _ec(exit_code=D.EXIT_SUBSTRATE_REJECT))
        self.assertFalse(out.discriminated)
        self.assertEqual(out.detail, "substrate-reject")
        self.assertEqual(out.cell, "FAIL(substrate-reject)")

    def test_reference_skipped_is_wrong_reason(self):
        spec = D.LegSpec(kind="reference", label="reference", submission=Path("r"), expect_pass=True)
        out = D.grade_leg(spec, _ec(report=_l2_report("skipped"), exit_code=1))
        self.assertFalse(out.discriminated)
        self.assertEqual(out.detail, "skipped")


class TestGradeVariant(unittest.TestCase):
    def _spec(self, subs=("expected 0", "found 2")):
        return D.LegSpec(
            kind="variant", label="burst-spawn", submission=Path("v"),
            expect_pass=False, expected_substrings=subs,
        )

    def test_fail_with_named_substring_discriminates(self):
        # Realistic UE fixture message; the two number-anchored fragments are
        # both present even though "expected 0, found 2" is not verbatim.
        log = "...\nAt t=0.50s (checkpoint 0): expected 0 SpawnedChild actor(s); found 2.\n..."
        out = D.grade_leg(self._spec(), _ec(report=_l2_report("fail"), l2_log=log, exit_code=1))
        self.assertTrue(out.discriminated)
        self.assertEqual(out.detail, "fail-named")

    def test_fail_wrong_checkpoint_is_wrong_reason(self):
        # Exit 1, but the LOG names the WRONG checkpoint (found 3, not found 2):
        # the "found 2" fragment is absent → wrong reason.
        log = "At t=3.50s (checkpoint 3): expected 2 SpawnedChild actor(s); found 3."
        out = D.grade_leg(self._spec(("expected 0", "found 2")),
                          _ec(report=_l2_report("fail"), l2_log=log, exit_code=1))
        self.assertFalse(out.discriminated)
        self.assertEqual(out.detail, "wrong-reason")

    def test_unexpected_pass_is_not_discriminated(self):
        out = D.grade_leg(self._spec(), _ec(exit_code=0))
        self.assertFalse(out.discriminated)
        self.assertEqual(out.detail, "unexpected-pass")

    def test_compile_error_exit1_without_substring_is_wrong_reason(self):
        # A compile error fails L1; the L2 log never names the assertion.
        out = D.grade_leg(self._spec(), _ec(report=_l2_report("fail"), l2_log="", exit_code=1))
        self.assertFalse(out.discriminated)
        self.assertEqual(out.detail, "wrong-reason")

    def test_sandbox_reject_is_wrong_reason(self):
        out = D.grade_leg(self._spec(), _ec(exit_code=D.EXIT_SANDBOX_REJECT))
        self.assertFalse(out.discriminated)
        self.assertEqual(out.detail, "sandbox-reject")

    def test_variant_without_named_assertion_cannot_be_credited(self):
        out = D.grade_leg(self._spec(subs=()), _ec(report=_l2_report("fail"), l2_log="boom", exit_code=1))
        self.assertFalse(out.discriminated)
        self.assertEqual(out.detail, "no-named-assertion")

    def test_multi_substring_requires_all(self):
        spec = self._spec(("expected 0", "found 2", "checkpoint 0"))
        # "checkpoint 0" is absent → wrong reason even though the other two match.
        out = D.grade_leg(spec, _ec(report=_l2_report("fail"),
                                    l2_log="expected 0 ...; found 2.", exit_code=1))
        self.assertFalse(out.discriminated)


class TestGradeHarnessError(unittest.TestCase):
    """A verifier that could not answer (exit 5/7 -> HARNESS-ERROR) is a
    wrong-reason on EVERY leg kind. Crediting it on a negative leg would record
    "I could not measure this" as "the gaming variant was correctly caught" —
    the fail-everything trap this module exists to detect."""

    def _variant(self):
        return D.LegSpec(
            kind="variant", label="burst-spawn", submission=Path("v"),
            expect_pass=False, expected_substrings=("expected 0",),
        )

    def test_harness_error_exit_codes_are_wrong_reasons(self):
        self.assertEqual(D._WRONG_REASON[D.EXIT_HARNESS_ERROR], "harness-error")
        self.assertEqual(D._WRONG_REASON[D.EXIT_NO_UPROJECT], "harness-error")

    def test_variant_harness_error_not_credited(self):
        out = D.grade_leg(self._variant(), _ec(exit_code=D.EXIT_HARNESS_ERROR))
        self.assertFalse(out.discriminated)
        self.assertEqual(out.detail, "harness-error")
        self.assertEqual(out.cell, "FAIL(harness-error)")

    def test_variant_harness_error_not_credited_even_with_the_named_substring(self):
        # The named substring can be in the log from an earlier leg / partial
        # run; the exit code still says nothing was measured.
        out = D.grade_leg(
            self._variant(),
            _ec(report=_l2_report("skipped"), l2_log="expected 0 actors",
                exit_code=D.EXIT_HARNESS_ERROR),
        )
        self.assertFalse(out.discriminated)
        self.assertEqual(out.detail, "harness-error")

    def test_empty_harness_error_not_credited(self):
        spec = D.LegSpec(kind="empty", label="empty", submission=None, expect_pass=False)
        out = D.grade_leg(spec, _ec(exit_code=D.EXIT_HARNESS_ERROR))
        self.assertFalse(out.discriminated)
        self.assertEqual(out.detail, "harness-error")

    def test_reference_harness_error_not_credited(self):
        spec = D.LegSpec(kind="reference", label="reference",
                         submission=Path("r"), expect_pass=True)
        out = D.grade_leg(spec, _ec(exit_code=D.EXIT_HARNESS_ERROR))
        self.assertFalse(out.discriminated)
        self.assertEqual(out.detail, "harness-error")

    def test_graded_fail_exit1_is_still_credited(self):
        # Guard against over-reach: the ordinary graded FAIL path is untouched.
        out = D.grade_leg(
            self._variant(),
            _ec(report=_l2_report("fail"), l2_log="expected 0 actors", exit_code=1),
        )
        self.assertTrue(out.discriminated)
        self.assertEqual(out.detail, "fail-named")


class TestGradeEmpty(unittest.TestCase):
    def test_empty_fail_without_recorded_substring_is_enough(self):
        spec = D.LegSpec(kind="empty", label="empty", submission=None, expect_pass=False)
        out = D.grade_leg(spec, _ec(report=_l2_report("fail"), exit_code=1))
        self.assertTrue(out.discriminated)
        self.assertEqual(out.detail, "fail")

    def test_empty_with_recorded_substring_must_match(self):
        spec = D.LegSpec(kind="empty", label="empty", submission=None,
                         expect_pass=False, expected_substrings=("7 units should fit",))
        ok = D.grade_leg(spec, _ec(report=_l2_report("fail"),
                                   l2_log="AddItem(Stone,7) returned false; 7 units should fit.", exit_code=1))
        self.assertTrue(ok.discriminated)
        bad = D.grade_leg(spec, _ec(report=_l2_report("fail"), l2_log="different message", exit_code=1))
        self.assertFalse(bad.discriminated)
        self.assertEqual(bad.detail, "wrong-reason")

    def test_empty_unexpected_pass_fails(self):
        spec = D.LegSpec(kind="empty", label="empty", submission=None, expect_pass=False)
        out = D.grade_leg(spec, _ec(exit_code=0))
        self.assertFalse(out.discriminated)


# --------------------------------------------------------------------------- #
# (3) run_matrix aggregation with a mocked runner                             #
# --------------------------------------------------------------------------- #

class TestRunMatrix(unittest.TestCase):
    def _legs(self):
        return [
            D.LegSpec("reference", "reference", Path("r"), True),
            D.LegSpec("empty", "empty", None, False),
            D.LegSpec("variant", "burst", Path("v1"), False, ("expected 0", "found 2")),
        ]

    def test_all_good_discriminated(self):
        scripted = {
            Path("r"): _ec(exit_code=0),
            None: _ec(report=_l2_report("fail"), exit_code=1),
            Path("v1"): _ec(report=_l2_report("fail"), l2_log="expected 0 ...; found 2.", exit_code=1),
        }
        oc = D.run_matrix(self._legs(), lambda sub: scripted[sub], "demo")
        self.assertTrue(oc.discriminated)
        self.assertEqual([l.cell for l in oc.legs], ["PASS", "FAIL", "FAIL"])

    def test_reference_fail_taints_whole_task(self):
        scripted = {
            Path("r"): _ec(report=_l2_report("fail"), exit_code=1),  # reference FAILED
            None: _ec(report=_l2_report("fail"), exit_code=1),
            Path("v1"): _ec(report=_l2_report("fail"), l2_log="expected 0 ...; found 2.", exit_code=1),
        }
        oc = D.run_matrix(self._legs(), lambda sub: scripted[sub], "demo")
        self.assertFalse(oc.discriminated)

    def test_wrong_reason_variant_taints_whole_task(self):
        scripted = {
            Path("r"): _ec(exit_code=0),
            None: _ec(report=_l2_report("fail"), exit_code=1),
            # Variant FAILS exit 1 but the wrong checkpoint message (no "found 2"):
            Path("v1"): _ec(report=_l2_report("fail"), l2_log="expected 2 ...; found 3.", exit_code=1),
        }
        oc = D.run_matrix(self._legs(), lambda sub: scripted[sub], "demo")
        self.assertFalse(oc.discriminated)
        bad = [l for l in oc.legs if not l.discriminated]
        self.assertEqual([l.spec.label for l in bad], ["burst"])

    def test_exit_code_and_table_render(self):
        scripted = {
            Path("r"): _ec(exit_code=0),
            None: _ec(report=_l2_report("fail"), exit_code=1),
            Path("v1"): _ec(report=_l2_report("fail"), l2_log="expected 0 ...; found 2.", exit_code=1),
        }
        oc = D.run_matrix(self._legs(), lambda sub: scripted[sub], "demo")
        self.assertEqual(D.overall_exit_code([oc]), 0)
        table = D.render_table([oc])
        self.assertIn("discriminated: YES", table)
        self.assertIn("discriminated 1/1 task(s)", table)

    def test_failed_task_table_shows_bad_cell_reason(self):
        scripted = {
            Path("r"): _ec(exit_code=0),
            None: _ec(report=_l2_report("fail"), exit_code=1),
            Path("v1"): _ec(exit_code=D.EXIT_SANDBOX_REJECT),
        }
        oc = D.run_matrix(self._legs(), lambda sub: scripted[sub], "demo")
        self.assertEqual(D.overall_exit_code([oc]), 1)
        table = D.render_table([oc])
        self.assertIn("FAIL(sandbox-reject)", table)
        self.assertIn("discriminated: NO", table)


# --------------------------------------------------------------------------- #
# (6) from-live decision with git mocked                                      #
# --------------------------------------------------------------------------- #

class _FakeCP:
    def __init__(self, stdout="", returncode=0):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = ""


class TestFromLiveDecision(unittest.TestCase):
    def test_wip_forces_from_live(self):
        called = []
        self.assertTrue(
            D.decide_from_live(Path("/repo"), "demo", force_wip=True,
                               run=lambda *a, **k: called.append(a) or _FakeCP())
        )
        self.assertEqual(called, [])  # forced; git never consulted

    def test_clean_committed_grades_from_head(self):
        self.assertFalse(
            D.decide_from_live(Path("/repo"), "demo", force_wip=False,
                               run=lambda *a, **k: _FakeCP(stdout="", returncode=0))
        )

    def test_dirty_or_untracked_grades_from_live(self):
        self.assertTrue(
            D.decide_from_live(Path("/repo"), "demo", force_wip=False,
                               run=lambda *a, **k: _FakeCP(stdout="?? tests/discrimination/demo/\n"))
        )

    def test_git_failure_fails_safe_to_from_live(self):
        def boom(*a, **k):
            raise FileNotFoundError("git missing")
        self.assertTrue(
            D.decide_from_live(Path("/repo"), "demo", force_wip=False, run=boom)
        )

    def test_git_nonzero_fails_safe_to_from_live(self):
        self.assertTrue(
            D.decide_from_live(Path("/repo"), "demo", force_wip=False,
                               run=lambda *a, **k: _FakeCP(stdout="", returncode=128))
        )


class TestFromLiveProbePaths(unittest.TestCase):
    """decide_from_live probes the DUAL-LAYOUT resolutions (the resolved spec +
    the folder-local reference/discrimination packages), not the old literal
    tasks/<id>.md + tests/... paths; missing resolutions are skipped."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="disc-probe-"))
        self.task = self.tmp / "tasks" / "concept-1" / "gp-demo"
        (self.task / "reference").mkdir(parents=True)
        (self.task / "discrimination").mkdir()
        (self.task / "task.md").write_text("# gp-demo\n", encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _probed(self, task_id):
        seen = {}

        def fake_run(cmd, capture_output=True, text=True, env=None):
            seen["cmd"] = cmd
            return _FakeCP(stdout="")

        dirty = D.decide_from_live(self.tmp, task_id, force_wip=False, run=fake_run)
        cmd = seen["cmd"]
        return dirty, cmd[cmd.index("--") + 1:]

    def test_probes_folder_form_paths(self):
        dirty, probed = self._probed("concept-1/gp-demo")
        self.assertFalse(dirty)  # git reported clean
        self.assertIn(str(self.task / "task.md"), probed)
        self.assertIn(str(self.task / "reference"), probed)
        self.assertIn(str(self.task / "discrimination"), probed)
        # The substrate's verifier-only tree is still probed.
        self.assertTrue(any(p.endswith("CraftBenchTests") for p in probed))
        # The old literal legacy paths (which don't exist here) are NOT probed.
        self.assertNotIn(str(self.tmp / "tasks" / "concept-1" / "gp-demo.md"), probed)
        self.assertNotIn(str(self.tmp / "tests" / "reference-solutions" / "gp-demo"),
                         probed)

    def test_missing_resolutions_are_skipped(self):
        # Unknown id: no spec, no packages — only the substrate path remains.
        dirty, probed = self._probed("nope")
        self.assertFalse(dirty)
        self.assertEqual(len(probed), 1)
        self.assertTrue(probed[0].endswith("CraftBenchTests"))


class TestFromLiveProbesTheTaskSOWNSubstrate(unittest.TestCase):
    """The dirtiness probe must look at the substrate the TASK declares.

    It used to hardcode CraftBenchTemplate, so a ThirdPerson task with only
    `UE-projects/ThirdPerson/Source/CraftBenchTests/` dirty was judged clean →
    graded from HEAD → the author's uncommitted fixture edit silently had no
    effect. That is the tp*-family iteration loop.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="disc-substrate-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def _write_spec(self, task_id: str, substrate: str) -> None:
        d = self.tmp / "tasks" / "craftbench-tasks" / task_id
        d.mkdir(parents=True)
        (d / "task.md").write_text(
            f"---\nid: {task_id}\nsubstrate: {substrate}\nlayers: [L1]\n---\n\n"
            f"# {task_id}\n", encoding="utf-8")

    def _probed(self, task_id: str):
        seen = {}

        def fake_run(cmd, capture_output=True, text=True, env=None):
            seen["cmd"] = cmd
            return _FakeCP(stdout="")

        D.decide_from_live(self.tmp, task_id, force_wip=False, run=fake_run)
        cmd = seen["cmd"]
        return cmd[cmd.index("--") + 1:]

    def test_thirdperson_task_probes_thirdperson_tests_tree(self):
        self._write_spec("tp-demo", "ThirdPerson")
        probed = self._probed("tp-demo")
        want = str(self.tmp / "UE-projects" / "ThirdPerson" / "Source" / "CraftBenchTests")
        self.assertIn(want, probed,
                      f"probed the wrong substrate tree: {probed}")
        self.assertNotIn(
            str(self.tmp / "UE-projects" / "CraftBenchTemplate" / "Source" / "CraftBenchTests"),
            probed)

    def test_default_substrate_task_still_probes_craftbenchtemplate(self):
        self._write_spec("cbt-demo", "CraftBenchTemplate")
        probed = self._probed("cbt-demo")
        self.assertIn(
            str(self.tmp / "UE-projects" / "CraftBenchTemplate" / "Source" / "CraftBenchTests"),
            probed)

    def test_explicit_substrate_rel_still_wins(self):
        self._write_spec("tp-demo2", "ThirdPerson")
        seen = {}

        def fake_run(cmd, capture_output=True, text=True, env=None):
            seen["cmd"] = cmd
            return _FakeCP(stdout="")

        D.decide_from_live(self.tmp, "tp-demo2", force_wip=False,
                           substrate_rel="UE-projects/Explicit", run=fake_run)
        self.assertTrue(any("Explicit" in p for p in seen["cmd"]))

    def test_force_wip_short_circuits_without_touching_git(self):
        def boom(*a, **k):
            raise AssertionError("git must not run when --wip forces from-live")
        self.assertTrue(D.decide_from_live(self.tmp, "anything",
                                           force_wip=True, run=boom))


# --------------------------------------------------------------------------- #
# (the subprocess seam itself): make_run_task_runner with a fake subprocess   #
# --------------------------------------------------------------------------- #

class TestRunnerSeam(unittest.TestCase):
    def test_runner_builds_cmd_and_reads_report_and_log(self):
        tmp = Path(tempfile.mkdtemp(prefix="disc-seam-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        captured = {}

        def fake_run(cmd, capture_output=True, text=True, env=None):
            captured["cmd"] = cmd
            # Locate the --report-json + --workdir the runner chose, write artifacts.
            rj = Path(cmd[cmd.index("--report-json") + 1])
            log = tmp / "l2.log"
            log.write_text("At t=0.50s (checkpoint 0): expected 0 ...; found 2.\n", encoding="utf-8")
            rj.parent.mkdir(parents=True, exist_ok=True)
            rj.write_text(
                '{"layers": {"L2": {"status": "fail", "log": "%s"}}, "overall": "fail"}'
                % log.as_posix(),
                encoding="utf-8",
            )
            return _FakeCP(stdout="", returncode=1)

        runner = D.make_run_task_runner(
            py_exe="python3", py_pre=[], run_task_py=Path("run_task.py"),
            task_spec=Path("tasks/demo.md"), ue_root=Path("/UE"),
            from_live=True, run=fake_run,
        )
        result = runner(Path("tests/discrimination/demo/burst-spawn"))
        self.assertEqual(result.exit_code, 1)
        self.assertIn("expected 0 ...; found 2.", result.l2_log)
        # Cmd shape: from-live flag present; submission threaded through.
        self.assertIn("--substrate-from-live", captured["cmd"])
        sub_arg = captured["cmd"][captured["cmd"].index("--submission") + 1]
        self.assertEqual(Path(sub_arg), Path("tests/discrimination/demo/burst-spawn"))
        self.assertIn("--ue-root", captured["cmd"])

    def test_runner_empty_submission_creates_throwaway_dir(self):
        seen = {}

        def fake_run(cmd, capture_output=True, text=True, env=None):
            sub = Path(cmd[cmd.index("--submission") + 1])
            seen["sub_exists"] = sub.exists()
            seen["sub_empty"] = sub.is_dir() and not any(sub.iterdir())
            rj = Path(cmd[cmd.index("--report-json") + 1])
            rj.parent.mkdir(parents=True, exist_ok=True)
            rj.write_text('{"layers": {}, "overall": "fail"}', encoding="utf-8")
            return _FakeCP(returncode=1)

        runner = D.make_run_task_runner(
            py_exe="python3", py_pre=[], run_task_py=Path("rt.py"),
            task_spec=Path("t.md"), ue_root=Path("/UE"), from_live=False, run=fake_run,
        )
        result = runner(None)
        self.assertEqual(result.exit_code, 1)
        self.assertTrue(seen["sub_exists"])
        self.assertTrue(seen["sub_empty"])


# --------------------------------------------------------------------------- #
# (7) set/id expansion                                                        #
# --------------------------------------------------------------------------- #

class TestExpandTargets(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="disc-exp-"))
        t = self.tmp / "tasks"
        (t / "bp-g2").mkdir(parents=True)
        (t / "alpha.md").write_text("# alpha\n", encoding="utf-8")
        (t / "bp-g2" / "one.md").write_text("# one\n", encoding="utf-8")
        (t / "bp-g2" / "two.md").write_text("# two\n", encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_set_name_expands_to_qualified_ids(self):
        ids, err = D.expand_targets(self.tmp, "bp-g2")
        self.assertIsNone(err)
        self.assertEqual(ids, ["bp-g2/one", "bp-g2/two"])

    def test_single_task_id(self):
        ids, err = D.expand_targets(self.tmp, "alpha")
        self.assertIsNone(err)
        self.assertEqual(ids, ["alpha"])

    def test_set_qualified_id(self):
        ids, err = D.expand_targets(self.tmp, "bp-g2/one")
        self.assertIsNone(err)
        self.assertEqual(ids, ["bp-g2/one"])

    def test_unknown_target_errors(self):
        ids, err = D.expand_targets(self.tmp, "nope")
        self.assertEqual(ids, [])
        self.assertIn("no task or set matched", err)


class TestRunnerCmd(unittest.TestCase):
    """make_run_task_runner builds the right run_task.py command (warm vs cold)."""

    def _capture(self, *, warm_cache):
        captured = {}

        class _CP:
            returncode = 0
            stdout = ""
            stderr = ""

        def _fake_run(cmd, **_kw):
            captured["cmd"] = cmd
            return _CP()

        runner = D.make_run_task_runner(
            py_exe="py", py_pre=[], run_task_py=Path("rt.py"),
            task_spec=Path("t.md"), ue_root=Path("/UE"),
            from_live=False, warm_cache=warm_cache, run=_fake_run)
        runner(Path("/sub"))
        return captured["cmd"]

    def test_warm_uses_warm_cache_and_out_dir_not_workdir(self):
        cmd = self._capture(warm_cache=True)
        self.assertIn("--warm-cache", cmd)
        self.assertIn("--out-dir", cmd)
        self.assertNotIn("--workdir", cmd)  # --workdir would force cold

    def test_cold_uses_workdir_not_warm_cache(self):
        cmd = self._capture(warm_cache=False)
        self.assertIn("--workdir", cmd)
        self.assertNotIn("--warm-cache", cmd)


class TestRunnerKeepRoot(unittest.TestCase):
    """`cb discriminate --keep`: keep_root retains each leg's dir (report +
    workdir) under keep_root/<leg-label>/; the empty-submission throwaway tmp
    is still cleaned; keep_root=None keeps today's full cleanup."""

    def _fake_run_writing_report(self):
        def _fake_run(cmd, capture_output=True, text=True, env=None):
            rj = Path(cmd[cmd.index("--report-json") + 1])
            rj.parent.mkdir(parents=True, exist_ok=True)
            rj.write_text('{"layers": {}, "overall": "fail"}', encoding="utf-8")
            return _FakeCP(returncode=1)
        return _fake_run

    def _runner(self, keep_root):
        return D.make_run_task_runner(
            py_exe="py", py_pre=[], run_task_py=Path("rt.py"),
            task_spec=Path("t.md"), ue_root=Path("/UE"), from_live=False,
            keep_root=keep_root, run=self._fake_run_writing_report())

    def test_keep_root_retains_leg_dir_named_by_submission(self):
        with tempfile.TemporaryDirectory() as td:
            keep = Path(td) / "keep"
            sub = Path(td) / "burst-spawn"
            sub.mkdir()
            runner = self._runner(keep)
            result = runner(sub)
            self.assertEqual(result.exit_code, 1)
            leg = keep / "burst-spawn"
            self.assertTrue(leg.is_dir(), "leg dir must SURVIVE under keep_root")
            self.assertTrue((leg / "report.json").exists())

    def test_keep_root_dedupes_colliding_labels(self):
        with tempfile.TemporaryDirectory() as td:
            keep = Path(td) / "keep"
            sub = Path(td) / "burst-spawn"
            sub.mkdir()
            runner = self._runner(keep)
            runner(sub)
            runner(sub)
            self.assertTrue((keep / "burst-spawn").is_dir())
            self.assertTrue((keep / "burst-spawn-2").is_dir())

    def test_keep_root_empty_leg_kept_but_throwaway_tmp_cleaned(self):
        seen = {}

        def _fake_run(cmd, capture_output=True, text=True, env=None):
            seen["sub"] = Path(cmd[cmd.index("--submission") + 1])
            rj = Path(cmd[cmd.index("--report-json") + 1])
            rj.parent.mkdir(parents=True, exist_ok=True)
            rj.write_text('{"layers": {}, "overall": "fail"}', encoding="utf-8")
            return _FakeCP(returncode=1)

        with tempfile.TemporaryDirectory() as td:
            keep = Path(td) / "keep"
            runner = D.make_run_task_runner(
                py_exe="py", py_pre=[], run_task_py=Path("rt.py"),
                task_spec=Path("t.md"), ue_root=Path("/UE"), from_live=False,
                keep_root=keep, run=_fake_run)
            runner(None)
            self.assertTrue((keep / "empty" / "report.json").exists(),
                            "the empty LEG dir (report) must be kept")
            self.assertFalse(seen["sub"].exists(),
                             "the empty-submission throwaway tmp must be cleaned")

    def test_no_keep_root_cleans_leg_dir(self):
        captured = {}

        def _fake_run(cmd, capture_output=True, text=True, env=None):
            rj = Path(cmd[cmd.index("--report-json") + 1])
            captured["leg_dir"] = rj.parent
            rj.parent.mkdir(parents=True, exist_ok=True)
            rj.write_text('{"layers": {}, "overall": "fail"}', encoding="utf-8")
            return _FakeCP(returncode=1)

        runner = D.make_run_task_runner(
            py_exe="py", py_pre=[], run_task_py=Path("rt.py"),
            task_spec=Path("t.md"), ue_root=Path("/UE"), from_live=False,
            run=_fake_run)
        runner(Path("/sub"))
        self.assertFalse(captured["leg_dir"].exists(),
                         "without --keep the leg tempdir is removed (today's behavior)")


if __name__ == "__main__":
    unittest.main()
