"""Offline unit tests for the verifier-noise stability harness.

NO UE, NO network, NO API key. The grading invocation is factored behind an
injectable ``grade_once`` callable, so every test feeds CANNED report dicts and
asserts the acceptance logic + per-layer flip-rate attribution.

Run: python3 -m unittest discover tools/verify-stability/tests
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PKG = _HERE.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

from stability_check import (  # noqa: E402
    EXIT_DELIVERABLE_DRIFT,
    EXIT_STABLE,
    EXIT_USAGE,
    EXIT_VERIFIER_BUG,
    LayerFlip,
    evaluate,
    make_subprocess_grade_once,
    render_text,
    run_stability_check,
)


# --------------------------------------------------------------------------- #
# Canned-report helpers
# --------------------------------------------------------------------------- #
def _report(*, sha: str, overall: str, layers: dict) -> dict:
    """A minimal report.json-shaped dict (mirrors report.py:Report.to_dict)."""
    return {
        "task_id": "t0",
        "submission_sha": sha,
        "overall": overall,
        "layers": layers,
        "duration_seconds": 1.0,
        "ue_version": "5.7.4",
        "host": {"os": "darwin", "arch": "arm64"},
        "sandbox_violations": 0,
    }


def _l1(*, status="pass", exit_code=0) -> dict:
    return {"status": status, "exit_code": exit_code}


def _l2(*, status="pass", tests_passed=1, tests_run=1) -> dict:
    return {"status": status, "tests_passed": tests_passed, "tests_run": tests_run}


def _l2i(*, status="pass") -> dict:
    return {"status": status}


def _canned_grade_once(reports):
    """Return a grade_once that serves the given list of reports in order.

    Writes each canned report to the requested report path too (so the live
    seam's "parse from disk" shape is exercised), then returns the dict.
    """
    seq = list(reports)

    def _grade(run_index: int, report_json_path: Path) -> dict:
        rep = seq[run_index]
        report_json_path.parent.mkdir(parents=True, exist_ok=True)
        report_json_path.write_text(json.dumps(rep), encoding="utf-8")
        return rep

    return _grade


# --------------------------------------------------------------------------- #
# (1) Stable scenario — N identical reports -> exit 0
# --------------------------------------------------------------------------- #
class TestStableScenario(unittest.TestCase):
    def test_n_identical_reports_pass(self):
        reports = [
            _report(sha="abc123", overall="pass",
                    layers={"L1": _l1(), "L2": _l2()})
            for _ in range(5)
        ]
        result = evaluate(reports)
        self.assertEqual(result.exit_code, EXIT_STABLE)
        self.assertTrue(result.stable)
        self.assertTrue(result.deliverable_fixed)
        self.assertTrue(result.overall_stable)
        self.assertTrue(result.layers_stable)
        self.assertFalse(result.layer_flips["L1"].flipped)
        self.assertFalse(result.layer_flips["L2"].flipped)
        self.assertIn("STABLE", "\n".join(result.messages))

    def test_stable_via_run_loop_seam(self):
        reports = [
            _report(sha="abc123", overall="pass",
                    layers={"L1": _l1(), "L2": _l2()})
            for _ in range(5)
        ]
        with tempfile.TemporaryDirectory() as d:
            result = run_stability_check(
                n=5, grade_once=_canned_grade_once(reports), report_dir=Path(d)
            )
            # All 5 per-run report files were written by the seam.
            for i in range(5):
                self.assertTrue((Path(d) / f"report_{i}.json").exists())
        self.assertEqual(result.exit_code, EXIT_STABLE)

    def test_stable_failing_but_consistent_overall_is_still_stable(self):
        # A deliverable that consistently FAILS is verifier-STABLE: the gate is
        # noise-free, the deliverable is just bad. Exit 0.
        reports = [
            _report(sha="dead", overall="fail",
                    layers={"L1": _l1(status="fail", exit_code=6)})
            for _ in range(3)
        ]
        result = evaluate(reports)
        self.assertEqual(result.exit_code, EXIT_STABLE)
        self.assertEqual(set(result.overalls), {"fail"})


# --------------------------------------------------------------------------- #
# (2) Flaky-overall scenario — one report differs -> nonzero + P0
# --------------------------------------------------------------------------- #
class TestFlakyOverall(unittest.TestCase):
    def test_one_overall_differs_is_p0_verifier_bug(self):
        reports = [
            _report(sha="abc123", overall="pass", layers={"L2": _l2()}),
            _report(sha="abc123", overall="pass", layers={"L2": _l2()}),
            _report(sha="abc123", overall="fail",
                    layers={"L2": _l2(status="fail", tests_passed=0)}),
            _report(sha="abc123", overall="pass", layers={"L2": _l2()}),
            _report(sha="abc123", overall="pass", layers={"L2": _l2()}),
        ]
        result = evaluate(reports)
        self.assertEqual(result.exit_code, EXIT_VERIFIER_BUG)
        self.assertFalse(result.overall_stable)
        # The deliverable WAS fixed — so it is a verifier bug, not drift.
        self.assertTrue(result.deliverable_fixed)
        joined = "\n".join(result.messages)
        self.assertIn("P0 VERIFIER BUG", joined)
        self.assertIn("overall flipped", joined)
        # NEVER attributed to the agent.
        self.assertNotIn("agent result", joined.lower().replace("never an agent result", ""))

    def test_p0_message_names_the_fixed_sha(self):
        reports = [
            _report(sha="fixedsha0000", overall="pass", layers={"L1": _l1()}),
            _report(sha="fixedsha0000", overall="fail",
                    layers={"L1": _l1(status="fail", exit_code=6)}),
        ]
        result = evaluate(reports)
        self.assertEqual(result.exit_code, EXIT_VERIFIER_BUG)
        self.assertIn("fixedsha0000"[:12], "\n".join(result.messages))


# --------------------------------------------------------------------------- #
# (3) Per-layer-count flip that nets the SAME overall -> must still fail
# --------------------------------------------------------------------------- #
class TestPerLayerCountFlip(unittest.TestCase):
    def test_count_flip_same_overall_still_fails(self):
        # overall is 'pass' on every run, but L2 tests_passed/tests_run differ:
        # this is exactly the flip that nets out to the same overall and would
        # be invisible without per-layer assertions.
        reports = [
            _report(sha="abc", overall="pass",
                    layers={"L2": _l2(tests_passed=2, tests_run=2)}),
            _report(sha="abc", overall="pass",
                    layers={"L2": _l2(tests_passed=1, tests_run=2)}),
            _report(sha="abc", overall="pass",
                    layers={"L2": _l2(tests_passed=2, tests_run=2)}),
        ]
        result = evaluate(reports)
        # overall is identical...
        self.assertTrue(result.overall_stable)
        # ...but the per-layer count flipped, so the gate must STILL fail P0.
        self.assertEqual(result.exit_code, EXIT_VERIFIER_BUG)
        self.assertFalse(result.layers_stable)
        l2 = result.layer_flips["L2"]
        self.assertGreater(l2.count_flip_rate, 0.0)
        self.assertEqual(l2.exit_flip_rate, 0.0)
        joined = "\n".join(result.messages)
        self.assertIn("P0 VERIFIER BUG", joined)
        self.assertIn("L2-style band/count flip", joined)

    def test_l1_exit_code_flip_attributed_to_l1(self):
        # Same overall netting (both pass) but L1 exit code flips -> L1-attributed.
        reports = [
            _report(sha="z", overall="pass", layers={"L1": _l1(exit_code=0)}),
            _report(sha="z", overall="pass", layers={"L1": _l1(exit_code=0)}),
            _report(sha="z", overall="pass", layers={"L1": _l1(exit_code=2)}),
        ]
        result = evaluate(reports)
        self.assertEqual(result.exit_code, EXIT_VERIFIER_BUG)
        l1 = result.layer_flips["L1"]
        self.assertGreater(l1.exit_flip_rate, 0.0)
        self.assertEqual(l1.count_flip_rate, 0.0)
        self.assertIn("L1-style exit-code flip", "\n".join(result.messages))

    def test_l2i_error_vs_pass_status_flip_attributed(self):
        # L2I cold-boot/flush: 'error' on one run, 'pass' on others -> status flip.
        reports = [
            _report(sha="m", overall="pass", layers={"L2I": _l2i(status="pass")}),
            _report(sha="m", overall="fail", layers={"L2I": _l2i(status="error")}),
            _report(sha="m", overall="pass", layers={"L2I": _l2i(status="pass")}),
        ]
        result = evaluate(reports)
        self.assertEqual(result.exit_code, EXIT_VERIFIER_BUG)
        l2i = result.layer_flips["L2I"]
        self.assertGreater(l2i.status_flip_rate, 0.0)
        self.assertIn("L2I-style error-vs-pass flip", "\n".join(result.messages))


# --------------------------------------------------------------------------- #
# (4) Non-constant submission_sha -> deliverable-not-fixed error
# --------------------------------------------------------------------------- #
class TestDeliverableNotFixed(unittest.TestCase):
    def test_differing_sha_is_deliverable_drift_not_verifier_bug(self):
        reports = [
            _report(sha="aaa", overall="pass", layers={"L1": _l1()}),
            _report(sha="bbb", overall="pass", layers={"L1": _l1()}),
        ]
        result = evaluate(reports)
        self.assertEqual(result.exit_code, EXIT_DELIVERABLE_DRIFT)
        self.assertFalse(result.deliverable_fixed)
        joined = "\n".join(result.messages)
        self.assertIn("DELIVERABLE NOT FIXED", joined)
        # It is explicitly NOT a P0 verifier bug — the input itself drifted.
        self.assertNotIn("P0 VERIFIER BUG", joined)

    def test_rejected_sentinel_flags_f1_env_flake(self):
        # The runner writes submission_sha='rejected' on substrate/sandbox
        # reject (exit 3/4). A constant deliverable that alternates between
        # 'rejected' and a real sha is the F1 working-tree-drift flake.
        reports = [
            _report(sha="realsha", overall="pass", layers={"L1": _l1()}),
            _report(sha="rejected", overall="fail",
                    layers={"sandbox": {"status": "fail"}}),
        ]
        result = evaluate(reports)
        self.assertEqual(result.exit_code, EXIT_DELIVERABLE_DRIFT)
        joined = "\n".join(result.messages)
        self.assertIn("rejected", joined)
        self.assertIn("F1", joined)

    def test_drift_takes_precedence_over_overall_disagreement(self):
        # Even though overall ALSO disagrees, a non-constant sha is reported as
        # drift (the more fundamental fault), never as a P0 verifier bug.
        reports = [
            _report(sha="aaa", overall="pass", layers={"L1": _l1()}),
            _report(sha="bbb", overall="fail",
                    layers={"L1": _l1(status="fail", exit_code=6)}),
        ]
        result = evaluate(reports)
        self.assertEqual(result.exit_code, EXIT_DELIVERABLE_DRIFT)


# --------------------------------------------------------------------------- #
# Usage / edge cases
# --------------------------------------------------------------------------- #
class TestUsageAndEdges(unittest.TestCase):
    def test_single_report_is_usage_error(self):
        result = evaluate([_report(sha="a", overall="pass", layers={"L1": _l1()})])
        self.assertEqual(result.exit_code, EXIT_USAGE)
        self.assertIn("USAGE", "\n".join(result.messages))

    def test_empty_is_usage_error(self):
        result = evaluate([])
        self.assertEqual(result.exit_code, EXIT_USAGE)

    def test_grade_once_raising_is_usage_error(self):
        def _boom(run_index, path):
            raise RuntimeError("run_task.py wrote no report (exit=3)")

        with tempfile.TemporaryDirectory() as d:
            result = run_stability_check(n=5, grade_once=_boom, report_dir=Path(d))
        self.assertEqual(result.exit_code, EXIT_USAGE)
        self.assertIn("failed before producing a report", "\n".join(result.messages))

    def test_layer_present_on_some_runs_only_flips_status(self):
        # L2 ran on run 0+2 but vanished on run 1 (e.g. a materialization flake):
        # the absence must surface as a flip, not be silently dropped.
        reports = [
            _report(sha="s", overall="pass", layers={"L2": _l2()}),
            _report(sha="s", overall="pass", layers={}),  # L2 absent
            _report(sha="s", overall="pass", layers={"L2": _l2()}),
        ]
        result = evaluate(reports)
        self.assertEqual(result.exit_code, EXIT_VERIFIER_BUG)
        self.assertTrue(result.layer_flips["L2"].flipped)


# --------------------------------------------------------------------------- #
# LayerFlip flip-rate math
# --------------------------------------------------------------------------- #
class TestLayerFlipMath(unittest.TestCase):
    def test_all_agree_is_zero(self):
        f = LayerFlip(layer="L1", exit_codes=[0, 0, 0, 0])
        self.assertEqual(f.exit_flip_rate, 0.0)
        self.assertFalse(f.flipped)

    def test_one_outlier_among_five_is_one_fifth(self):
        f = LayerFlip(layer="L1", exit_codes=[0, 0, 6, 0, 0])
        self.assertAlmostEqual(f.exit_flip_rate, 0.2)
        self.assertTrue(f.flipped)

    def test_none_observations_are_ignored_in_rate(self):
        # A layer absent on one run (None) vs present-and-equal on the rest is
        # still a flip via the status axis, but the exit-rate ignores the None.
        f = LayerFlip(layer="L2", exit_codes=[0, None, 0])
        self.assertEqual(f.exit_flip_rate, 0.0)

    def test_count_pair_flip_rate(self):
        f = LayerFlip(
            layer="L2",
            test_counts=[(2, 2), (1, 2), (2, 2)],
        )
        self.assertAlmostEqual(f.count_flip_rate, 1 / 3)
        self.assertTrue(f.flipped)


# --------------------------------------------------------------------------- #
# Live seam wiring (no UE — assert it BUILDS the right argv shape, never runs UE)
# --------------------------------------------------------------------------- #
class TestSubprocessSeamShape(unittest.TestCase):
    def test_make_grade_once_is_callable_without_invoking_ue(self):
        # Just constructing the seam must not touch UE or the network.
        grade = make_subprocess_grade_once(
            task=Path("tasks/t0.md"),
            submission=Path("tests/reference-solutions/t0"),
            ue_root=Path("/nonexistent/UE_5.7"),
        )
        self.assertTrue(callable(grade))


# --------------------------------------------------------------------------- #
# Rendering smoke
# --------------------------------------------------------------------------- #
class TestRender(unittest.TestCase):
    def test_render_stable(self):
        reports = [
            _report(sha="abc", overall="pass", layers={"L1": _l1(), "L2": _l2()})
            for _ in range(3)
        ]
        txt = render_text(evaluate(reports))
        self.assertIn("PASS (verifier-noise == 0)", txt)
        self.assertIn("per-layer flip-rate", txt)

    def test_render_p0(self):
        reports = [
            _report(sha="abc", overall="pass", layers={"L2": _l2()}),
            _report(sha="abc", overall="fail",
                    layers={"L2": _l2(status="fail", tests_passed=0)}),
        ]
        txt = render_text(evaluate(reports))
        self.assertIn("P0 VERIFIER BUG", txt)
        self.assertIn("FLIPPED", txt)


if __name__ == "__main__":
    unittest.main()
