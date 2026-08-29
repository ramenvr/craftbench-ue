"""Unit tests for the shared verifier-verdict mapping (adapters/base.py) and its
two harness consumers (run.py, run_batch.py).

These tests pin the F2/F5 stability fixes (the verdict-stability notes):

  - verify-single exit-3 (verifier-hash-manifest reject) maps to a DISTINCT
    SUBSTRATE-REJECT verdict, NOT a silent agent FAIL;
  - exit-4 (sandbox reject) maps to SANDBOX-REJECT;
  - exit-5/exit-7 map to HARNESS-ERROR — the verifier produced no verdict, so
    the run is NOT graded (verdict-taxonomy finding 2), and exit-2 keeps the
    driver's historical ERROR label;
  - the two exit->verdict maps (adapters.base + aura_rig.driver) agree;
  - the non-graded verdicts are EXCLUDED from any pass-rate denominator;
  - the authoritative ``overall`` from report.json is PREFERRED over a
    contradictory human-rendered stdout ``overall :`` line (F5);
  - the no-report.json stdout-regex fallback still works (back-compat).

Fully offline: no Unreal editor, no Aura, no network, no subprocess.

Run from tools/run-agent:

    python3 -m unittest tests.test_verdict_mapping
"""

import asyncio
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.base import (  # noqa: E402
    GRADED_VERDICTS,
    VERDICT_ERROR,
    VERDICT_FAIL,
    VERDICT_HARNESS_ERROR,
    VERDICT_PASS,
    VERDICT_SANDBOX_REJECT,
    VERDICT_SUBSTRATE_REJECT,
    VERIFIER_EXIT_VERDICT,
    is_graded_verdict,
    pass_rate,
    verdict_from_verifier,
)
from aura_rig import driver as rig_driver  # noqa: E402
from run_batch import (  # noqa: E402
    make_default_verify,
    summarize_verdicts,
)

# Import run.py's helpers without executing main() (mirrors test_run_parsers.py).
RUN_PY = Path(__file__).resolve().parents[1] / "run.py"
_spec = importlib.util.spec_from_file_location("run_module_verdict", RUN_PY)
run_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_module)


# Human-rendered verifier stdout (graded path) — note the trailing
# ``json report:`` marker that points at a report.json on disk.
_STDOUT_PASS_TMPL = """\
sandbox: accepted 2 file(s), 0 violations
CraftBench verifier report
  L1  : PASS    [exit=0, warn=0]
  L2  : PASS    [exit=0, tests=1/1]
  overall   : PASS
json report: {report_path}
"""

# A CONTRADICTORY stdout: the human line says FAIL but report.json says pass.
# report.json must win (F5).
_STDOUT_CONTRADICTS_REPORT = """\
CraftBench verifier report
  L2  : FAIL    [exit=1, tests=0/1]
  overall   : FAIL
json report: {report_path}
"""

# Exit-3 verifier-hash-manifest reject: verifier wrote NO report, stderr-only, so stdout
# has no ``overall :`` line and no ``json report:`` marker at all.
_STDOUT_EXIT3 = ""


def _write_report(tmpdir: Path, overall_lower: str) -> Path:
    """Write a minimal report.json carrying the authoritative lowercase
    ``overall`` field (pass|fail), as Report.to_dict() does."""
    p = tmpdir / "report.json"
    p.write_text(json.dumps({"task_id": "t", "overall": overall_lower}))
    return p


class FakeCompleted:
    """Stand-in for subprocess.CompletedProcess: only stdout + returncode."""

    def __init__(self, stdout: str, returncode: int):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = ""


class TestVerdictFromVerifier(unittest.TestCase):
    def test_exit3_maps_to_substrate_reject_not_fail(self):
        # The headline F2 bug: exit-3 silently became FAIL. Now it is distinct.
        v = verdict_from_verifier(3, _STDOUT_EXIT3)
        self.assertEqual(v, VERDICT_SUBSTRATE_REJECT)
        self.assertNotEqual(v, VERDICT_FAIL)

    def test_exit4_maps_to_sandbox_reject(self):
        self.assertEqual(verdict_from_verifier(4, ""), VERDICT_SANDBOX_REJECT)

    def test_report_json_overall_preferred_over_contradictory_stdout(self):
        # F5: report.json says pass, the rendered stdout line says FAIL.
        with tempfile.TemporaryDirectory() as d:
            rpath = _write_report(Path(d), "pass")
            stdout = _STDOUT_CONTRADICTS_REPORT.format(report_path=rpath)
            self.assertEqual(verdict_from_verifier(0, stdout), VERDICT_PASS)

    def test_report_json_fail_is_read_authoritatively(self):
        with tempfile.TemporaryDirectory() as d:
            rpath = _write_report(Path(d), "fail")
            stdout = _STDOUT_PASS_TMPL.format(report_path=rpath)  # stdout says PASS
            # report.json says fail → fail wins.
            self.assertEqual(verdict_from_verifier(0, stdout), VERDICT_FAIL)

    def test_stdout_fallback_when_no_report_json(self):
        # No ``json report:`` marker → fall back to the rendered stdout line.
        stdout = "CraftBench verifier report\n  overall   : PASS\n"
        self.assertEqual(verdict_from_verifier(0, stdout), VERDICT_PASS)

    def test_stdout_fallback_when_report_path_missing_on_disk(self):
        # Marker present but file gone (tempdir torn down) → stdout fallback.
        stdout = (
            "  overall   : PASS\n"
            "json report: /tmp/does-not-exist-craftbench-xyz/report.json\n"
        )
        self.assertEqual(verdict_from_verifier(0, stdout), VERDICT_PASS)

    def test_harness_error_when_nothing_parseable(self):
        # UPDATED (verdict-taxonomy): this used to assert the legacy
        # default-to-FAIL. No report.json AND no rendered ``overall`` line means
        # the verifier never produced a verdict; labelling that FAIL fabricated a
        # measurement and put it in the pass-rate denominator.
        v = verdict_from_verifier(0, "noise")
        self.assertEqual(v, VERDICT_HARNESS_ERROR)
        self.assertNotEqual(v, VERDICT_FAIL)
        self.assertFalse(is_graded_verdict(v))

    def test_exit7_maps_to_harness_error_not_fail(self):
        # Exit 7 writes NO report.json at all when it came from the crash trap,
        # which is why the exit code must be consulted first.
        v = verdict_from_verifier(7, "")
        self.assertEqual(v, VERDICT_HARNESS_ERROR)
        self.assertFalse(is_graded_verdict(v))

    def test_exit7_wins_over_a_report_json_on_disk(self):
        # The layers-based exit-7 routes DO write a report (overall
        # "harness-error"); either way the verdict must not be graded. Even a
        # stale/contradictory pass report cannot promote exit 7.
        with tempfile.TemporaryDirectory() as d:
            rpath = _write_report(Path(d), "pass")
            stdout = _STDOUT_PASS_TMPL.format(report_path=rpath)
            self.assertEqual(verdict_from_verifier(7, stdout), VERDICT_HARNESS_ERROR)

    def test_report_json_harness_error_overall_round_trips(self):
        # run_task writes overall="harness-error"; uppercased it must be exactly
        # the shared verdict string, so the report route and the exit-code route
        # agree instead of inventing two labels.
        with tempfile.TemporaryDirectory() as d:
            rpath = _write_report(Path(d), "harness-error")
            stdout = _STDOUT_PASS_TMPL.format(report_path=rpath)
            self.assertEqual(verdict_from_verifier(0, stdout), VERDICT_HARNESS_ERROR)

    def test_rendered_harness_error_line_parses_via_the_stdout_fallback(self):
        # Report.render_text() prints "  overall   : HARNESS-ERROR". With no
        # report.json on disk the regex fallback must recover exactly the shared
        # verdict string — not a near-miss the graded check would misread.
        stdout = "CraftBench verifier report\n  overall   : HARNESS-ERROR\n"
        v = verdict_from_verifier(0, stdout)
        self.assertEqual(v, VERDICT_HARNESS_ERROR)
        self.assertFalse(is_graded_verdict(v))

    def test_exit5_maps_to_harness_error(self):
        # 5 = no .uproject in the materialized substrate — a harness fault.
        self.assertEqual(verdict_from_verifier(5, ""), VERDICT_HARNESS_ERROR)

    def test_exit2_maps_to_error_not_fail(self):
        # A malformed spec / bad CLI usage is not an agent outcome. Label matches
        # driver.VERDICT[2], which is historical and must not be renamed.
        v = verdict_from_verifier(2, "")
        self.assertEqual(v, VERDICT_ERROR)
        self.assertFalse(is_graded_verdict(v))


class TestExitTaxonomyAgreement(unittest.TestCase):
    """The two verifier-facing exit->verdict maps must not drift apart.

    adapters.base.VERIFIER_EXIT_VERDICT serves run.py / run_batch.py;
    aura_rig.driver.VERDICT serves the cb rig. The same verify-single exit code
    graded by either path has to read as the SAME outcome — otherwise one run
    means two different things depending on who ran it.
    """

    def test_maps_agree_on_every_shared_key(self):
        for code, verdict in VERIFIER_EXIT_VERDICT.items():
            self.assertIn(code, rig_driver.VERDICT, f"driver.VERDICT lacks {code}")
            self.assertEqual(
                rig_driver.VERDICT[code], verdict,
                f"exit {code}: base says {verdict}, driver says "
                f"{rig_driver.VERDICT[code]}",
            )

    def test_graded_codes_in_the_rig_map_are_0_1_and_the_sandbox_reject(self):
        """Was ``== {0, 1}`` until 2026-08-17, and the change is the point.

        A graded verdict is one that counts in the pass-rate DENOMINATOR, and
        exit 4 / SANDBOX-REJECT now does (the denominator rule — it describes
        what the model did). Its exit code is unchanged at 4; what changed is
        only that it stopped being excluded from the score. Exit codes 5/7/8 and
        the reject at 3 stay non-graded, which is the property that actually
        protects the denominator.
        """
        graded = {c for c, v in rig_driver.VERDICT.items() if is_graded_verdict(v)}
        self.assertEqual(graded, {0, 1, 4})
        for code in (2, 3, 5, 7, 8):
            with self.subTest(code=code):
                self.assertFalse(
                    is_graded_verdict(rig_driver.VERDICT.get(code)),
                    "exit %d is a harness condition and must stay out of every "
                    "pass-rate denominator" % code,
                )

    def test_exit_0_and_1_absent_from_base_map(self):
        # PASS/FAIL are read from report.json, never inferred from the code.
        self.assertNotIn(0, VERIFIER_EXIT_VERDICT)
        self.assertNotIn(1, VERIFIER_EXIT_VERDICT)

    def test_exit3_reserved_and_still_mapped(self):
        # 3 is RETIRED (the removed hash-manifest reject) and must never be
        # re-used; it stays mapped so historical artifacts still read right.
        self.assertEqual(VERIFIER_EXIT_VERDICT[3], VERDICT_SUBSTRATE_REJECT)
        self.assertEqual(rig_driver.VERDICT[3], VERDICT_SUBSTRATE_REJECT)

    def test_exit6_is_never_mapped(self):
        # 6 is UBT's OWN build-failure code; verify-single must never claim it.
        self.assertNotIn(6, VERIFIER_EXIT_VERDICT)
        self.assertNotIn(6, rig_driver.VERDICT)

    def test_driver_error_label_for_exit2_unchanged(self):
        # Renaming this churns every historical summary.json for zero gain.
        self.assertEqual(rig_driver.VERDICT[2], "ERROR")
        self.assertEqual(rig_driver.verdict_for_exit(2), "ERROR")

    def test_driver_verdict_for_exit_7(self):
        self.assertEqual(rig_driver.verdict_for_exit(7), VERDICT_HARNESS_ERROR)
        self.assertEqual(rig_driver.verdict_for_exit(5), VERDICT_HARNESS_ERROR)


class TestGradedExclusion(unittest.TestCase):
    def test_graded_set_is_pass_fail_plus_the_model_outcomes(self):
        """The pass-rate denominator, pinned by value.

        Widened 2026-08-17 from ``{PASS, FAIL}``. The three additions describe
        what the MODEL did, so excluding them biased scores UPWARD — the mirror
        of charging a harness fault to the model (the denominator rule, owner
        decision 2026-08-14). This assertion is deliberately by-value: changing
        the denominator must be a decision, never a drive-by, and it has to land
        in the same change as ``tools/compare/compare_products.py`` and
        ``tools/dashboard/collect.py`` or one run set yields two pass rates.
        """
        self.assertEqual(
            GRADED_VERDICTS,
            frozenset({"PASS", "FAIL", "FAIL_NO_EDITS", "SANDBOX-REJECT",
                       "NO_DELIVERABLE"}),
        )
        self.assertTrue(is_graded_verdict(VERDICT_PASS))
        self.assertTrue(is_graded_verdict(VERDICT_FAIL))
        # Model outcomes: in the denominator, as non-passes.
        self.assertTrue(is_graded_verdict(VERDICT_SANDBOX_REJECT))
        self.assertTrue(is_graded_verdict("NO_DELIVERABLE"))
        self.assertTrue(is_graded_verdict("FAIL_NO_EDITS"))
        # Harness conditions: still out, and still the majority of the taxonomy.
        self.assertFalse(is_graded_verdict(VERDICT_SUBSTRATE_REJECT))
        self.assertFalse(is_graded_verdict(VERDICT_HARNESS_ERROR))
        self.assertFalse(is_graded_verdict(VERDICT_ERROR))
        self.assertFalse(is_graded_verdict("TIMEOUT"))
        self.assertFalse(is_graded_verdict("UNGRADED"))
        self.assertFalse(is_graded_verdict("TOOL-AUTH-BLOCKED"))
        self.assertFalse(is_graded_verdict(None))

    def test_pass_rate_counts_a_sandbox_reject_as_a_non_pass(self):
        """The arithmetic the widening exists to fix.

        Two runs, one PASS and one SANDBOX-REJECT, is 50% — not 100%. Reading it
        as 100% is the upward bias the denominator rule names.
        """
        from adapters.base import pass_rate
        self.assertEqual(pass_rate(["PASS", "SANDBOX-REJECT"]), 0.5)
        self.assertEqual(pass_rate(["PASS", "NO_DELIVERABLE"]), 0.5)
        # A harness fault still does not touch the denominator at all.
        self.assertEqual(pass_rate(["PASS", "HARNESS-ERROR"]), 1.0)
        self.assertIsNone(pass_rate(["HARNESS-ERROR", "TIMEOUT"]))

    def test_harness_error_excluded_from_pass_rate(self):
        # 1 PASS, 1 FAIL, 1 HARNESS-ERROR -> 1/2, NOT 1/3. A verifier that could
        # not answer must not deflate (or inflate) an agent's score.
        verdicts = [VERDICT_PASS, VERDICT_FAIL, VERDICT_HARNESS_ERROR]
        self.assertAlmostEqual(pass_rate(verdicts), 1 / 2)

    def test_summarize_excludes_harness_error_from_denominator(self):
        s = summarize_verdicts(
            [VERDICT_PASS, VERDICT_FAIL, VERDICT_HARNESS_ERROR, VERDICT_ERROR]
        )
        self.assertEqual(s["n_total"], 4)
        self.assertEqual(s["n_graded"], 2)
        self.assertAlmostEqual(s["pass_rate"], 1 / 2)
        self.assertEqual(
            s["excluded_by_verdict"],
            {VERDICT_HARNESS_ERROR: 1, VERDICT_ERROR: 1},
        )

    def test_substrate_reject_excluded_from_pass_rate(self):
        # 2 PASS, 1 FAIL, 1 SUBSTRATE-REJECT → rate is 2/3, NOT 2/4.
        verdicts = ["PASS", "PASS", "FAIL", VERDICT_SUBSTRATE_REJECT]
        self.assertAlmostEqual(pass_rate(verdicts), 2 / 3)

    def test_pass_rate_none_when_no_graded_sample(self):
        self.assertIsNone(pass_rate([VERDICT_SUBSTRATE_REJECT, "TIMEOUT", None]))

    def test_summarize_excludes_harness_conditions_but_counts_model_outcomes(self):
        """The split, on one batch, after the 2026-08-17 widening.

        SUBSTRATE-REJECT and TIMEOUT are things the HARNESS did — excluded.
        SANDBOX-REJECT is a thing the MODEL did — counted, as a non-pass. Before
        the widening this batch scored 2/3 = 67%; it is 2/4 = 50%, and the 17
        points were the upward bias the denominator rule names.
        """
        verdicts = [
            "PASS",
            "PASS",
            "FAIL",
            VERDICT_SUBSTRATE_REJECT,
            VERDICT_SANDBOX_REJECT,
            "TIMEOUT",
        ]
        s = summarize_verdicts(verdicts)
        self.assertEqual(s["n_total"], 6)
        self.assertEqual(s["n_graded"], 4)  # + the SANDBOX-REJECT
        self.assertEqual(s["n_pass"], 2)
        # NB "n_fail" is graded-and-not-passed: the FAIL plus the SANDBOX-REJECT.
        self.assertEqual(s["n_fail"], 2)
        self.assertAlmostEqual(s["pass_rate"], 2 / 4)
        self.assertEqual(s["n_excluded"], 2)
        self.assertEqual(
            s["excluded_by_verdict"],
            {VERDICT_SUBSTRATE_REJECT: 1, "TIMEOUT": 1},
        )

    def test_summarize_all_rejected_yields_none_rate(self):
        s = summarize_verdicts([VERDICT_SUBSTRATE_REJECT, VERDICT_SUBSTRATE_REJECT])
        self.assertEqual(s["n_graded"], 0)
        self.assertIsNone(s["pass_rate"])


class TestRunPyHelperDelegates(unittest.TestCase):
    """run.py's retained _parse_verifier_overall is a stdout-only fallback."""

    def test_parses_pass(self):
        stdout = "  overall   : PASS\n"
        self.assertEqual(run_module._parse_verifier_overall(stdout), "PASS")

    def test_returns_harness_error_when_marker_missing(self):
        # UPDATED (verdict-taxonomy): was "FAIL". run.py's helper delegates to
        # the shared regex, so it inherits the non-graded default.
        self.assertEqual(
            run_module._parse_verifier_overall("nope"), VERDICT_HARNESS_ERROR
        )


class TestRunBatchDefaultVerify(unittest.TestCase):
    """make_default_verify (the run_batch Pool-B grader) maps exit codes via the
    shared verdict logic — exit-3 must become SUBSTRATE-REJECT, not FAIL."""

    def _run_verify(self, completed):
        captured = {}

        def fake_run_subprocess(cmd, **kwargs):
            captured["cmd"] = cmd
            return completed

        verify = make_default_verify(
            task_path_for=lambda t: Path("tasks/x.md"),
            submission_dir_for=lambda t: Path("/tmp/sub"),
            ue_root="/fake/UE_5.7",
            run_subprocess=fake_run_subprocess,
        )
        task = types.SimpleNamespace(task_id="x", run_id="r", payload={})
        overall, report = asyncio.run(verify(task, None, None))
        return overall, report

    def test_exit3_yields_substrate_reject(self):
        overall, report = self._run_verify(FakeCompleted("", 3))
        self.assertEqual(overall, VERDICT_SUBSTRATE_REJECT)
        self.assertEqual(report["overall"], VERDICT_SUBSTRATE_REJECT)

    def test_exit4_yields_sandbox_reject(self):
        overall, _ = self._run_verify(FakeCompleted("", 4))
        self.assertEqual(overall, VERDICT_SANDBOX_REJECT)

    def test_report_json_preferred_in_batch_path(self):
        with tempfile.TemporaryDirectory() as d:
            rpath = _write_report(Path(d), "pass")
            stdout = _STDOUT_CONTRADICTS_REPORT.format(report_path=rpath)
            overall, _ = self._run_verify(FakeCompleted(stdout, 1))
            self.assertEqual(overall, VERDICT_PASS)

    def test_stdout_fallback_in_batch_path(self):
        overall, _ = self._run_verify(
            FakeCompleted("  overall   : PASS\n", 0)
        )
        self.assertEqual(overall, VERDICT_PASS)


if __name__ == "__main__":
    unittest.main()
