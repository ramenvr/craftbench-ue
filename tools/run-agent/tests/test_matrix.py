"""Unit tests for aura_rig.matrix — the {model}x{task} leaderboard.

UE-free: the cell runner is an injected seam, so we drive the orchestration
loop + aggregation + rendering with canned CellResults.
"""
import json
import tempfile
import unittest
from pathlib import Path

from aura_rig import matrix as mtx


class TestPureHelpers(unittest.TestCase):
    def test_parse_models_splits_trims_dedupes_in_order(self):
        self.assertEqual(
            mtx.parse_models(" claude-p:sonnet , openrouter:openai/gpt-4o-mini , claude-p:sonnet "),
            ["claude-p:sonnet", "openrouter:openai/gpt-4o-mini"],
        )

    def test_parse_models_empty(self):
        self.assertEqual(mtx.parse_models(""), [])
        self.assertEqual(mtx.parse_models("  , ,"), [])

    def test_build_cells_is_models_major_cross_product(self):
        cells = mtx.build_cells(["A", "B"], ["t1", "t2"])
        self.assertEqual([(c.model, c.task_id) for c in cells],
                         [("A", "t1"), ("A", "t2"), ("B", "t1"), ("B", "t2")])

    def test_safe_name(self):
        self.assertEqual(mtx.safe_name("openrouter:openai/gpt-4o-mini"),
                         "openrouter-openai-gpt-4o-mini")


class TestAggregate(unittest.TestCase):
    def _mix(self):
        # model A: PASS + FAIL + HARNESS-ERROR (non-graded) -> pass-rate 1/2
        # model B: PASS + error (harness) -> pass-rate 1/1
        #
        # The non-graded cell was a SANDBOX-REJECT until 2026-08-17, when that
        # verdict became a counted MODEL outcome (the denominator rule).
        # Swapped for a real harness fault so these assertions keep testing
        # exclusion; SANDBOX-REJECT's new behaviour is pinned separately below.
        return [
            mtx.CellResult("A", "t1", "PASS", cost_usd=0.10, duration_s=20),
            mtx.CellResult("A", "t2", "FAIL", cost_usd=0.20, duration_s=30),
            mtx.CellResult("A", "t3", "HARNESS-ERROR", cost_usd=0.05, duration_s=5),
            mtx.CellResult("B", "t1", "PASS", cost_usd=0.50, duration_s=40),
            mtx.CellResult("B", "t2", None, error="no result.json (run.py exit 4)"),
            mtx.CellResult("B", "t3", "PASS", cost_usd=0.30, duration_s=25),
        ]

    def test_pass_rate_excludes_non_graded_and_errors(self):
        agg = mtx.aggregate(self._mix(), ["A", "B"], ["t1", "t2", "t3"])
        a, b = agg["by_model"]["A"], agg["by_model"]["B"]
        # A: graded = {PASS, FAIL} -> 1/2 = 0.5; HARNESS-ERROR excluded
        self.assertEqual(a["graded_n"], 2)
        self.assertAlmostEqual(a["pass_rate"], 0.5)
        self.assertEqual(a["non_graded"], 1)
        self.assertEqual(a["errors"], 0)
        self.assertAlmostEqual(a["total_cost_usd"], 0.35)
        # B: graded = {PASS, PASS} -> 2/2 = 1.0; the error cell is excluded, not a FAIL
        self.assertEqual(b["graded_n"], 2)
        self.assertAlmostEqual(b["pass_rate"], 1.0)
        self.assertEqual(b["errors"], 1)
        self.assertEqual(b["fail"], 0)

    def test_no_graded_sample_is_none_not_zero(self):
        # Both cells must be genuinely non-graded for "no sample" to be the
        # thing under test — see _mix's note on the 2026-08-17 swap.
        results = [mtx.CellResult("A", "t1", "HARNESS-ERROR"),
                   mtx.CellResult("A", "t2", None, error="boom")]
        agg = mtx.aggregate(results, ["A"], ["t1", "t2"])
        self.assertIsNone(agg["by_model"]["A"]["pass_rate"])  # distinct from 0%

    def test_sandbox_reject_is_a_counted_non_pass_not_an_exclusion(self):
        """A cell the model lost by writing outside the sandbox still counts.

        Excluding it let a model that reliably submits denied paths report the
        pass rate of only the cells it happened to get right — the upward bias
        the denominator rule names. Was graded_n=1 / pass_rate=1.0 before
        2026-08-17.
        """
        results = [mtx.CellResult("A", "t1", "PASS", cost_usd=0.1),
                   mtx.CellResult("A", "t2", "SANDBOX-REJECT", cost_usd=0.1)]
        a = mtx.aggregate(results, ["A"], ["t1", "t2"])["by_model"]["A"]
        self.assertEqual(a["graded_n"], 2)
        self.assertAlmostEqual(a["pass_rate"], 0.5)
        self.assertEqual(a["non_graded"], 0)

    def test_renderers_smoke(self):
        agg = mtx.aggregate(self._mix(), ["A", "B"], ["t1", "t2", "t3"])
        md = mtx.render_markdown(agg)
        self.assertIn("leaderboard", md.lower())
        self.assertIn("A", md)
        self.assertIn("100%", md)  # B
        html = mtx.render_html(agg)
        self.assertIn("<!doctype html>", html.lower())
        self.assertIn("PASS", html)
        self.assertIn("FAIL", html)
        # tooltip/label for the non-graded + error cells present
        self.assertIn("HARNESS-ERROR", html)
        # And the caption must not promise an exclusion that no longer happens.
        self.assertNotIn("sandbox/substrate-reject", html)

    def test_meta_ue_version_disclosed_in_renders(self):
        agg = mtx.aggregate(self._mix(), ["A", "B"], ["t1", "t2", "t3"],
                            meta={"ue_root": r"C:\Program Files\Epic Games\UE_5.7",
                                  "generated_at": "20260619-000000 UTC"})
        self.assertIn("meta", agg)
        self.assertIn("UE_5.7", mtx.render_markdown(agg))
        self.assertIn("UE_5.7", mtx.render_html(agg))


class TestRunOrchestration(unittest.TestCase):
    def test_run_writes_leaderboard_files_and_returns_agg(self):
        calls = []

        def fake_runner(cell):
            calls.append((cell.model, cell.task_id))
            verdict = "PASS" if cell.model == "good" else "FAIL"
            return mtx.CellResult(cell.model, cell.task_id, verdict, cost_usd=0.1, duration_s=10)

        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "matrix-x"
            agg = mtx.run(["good", "bad"], ["t1"], fake_runner, out, log=lambda *_: None)
            self.assertEqual(calls, [("good", "t1"), ("bad", "t1")])
            self.assertTrue((out / "leaderboard.json").exists())
            self.assertTrue((out / "leaderboard.md").exists())
            self.assertTrue((out / "leaderboard.html").exists())
            saved = json.loads((out / "leaderboard.json").read_text(encoding="utf-8"))
            self.assertAlmostEqual(saved["by_model"]["good"]["pass_rate"], 1.0)
            self.assertAlmostEqual(saved["by_model"]["bad"]["pass_rate"], 0.0)
            self.assertAlmostEqual(agg["by_model"]["good"]["pass_rate"], 1.0)

    def test_run_survives_a_throwing_cell_runner(self):
        def boom(cell):
            if cell.task_id == "t2":
                raise RuntimeError("cell blew up")
            return mtx.CellResult(cell.model, cell.task_id, "PASS")

        with tempfile.TemporaryDirectory() as d:
            agg = mtx.run(["A"], ["t1", "t2", "t3"], boom, Path(d) / "m", log=lambda *_: None)
            # t1 + t3 PASS graded; t2 is an ERROR cell (excluded from pass-rate)
            self.assertEqual(agg["by_model"]["A"]["graded_n"], 2)
            self.assertAlmostEqual(agg["by_model"]["A"]["pass_rate"], 1.0)
            self.assertEqual(agg["by_model"]["A"]["errors"], 1)


if __name__ == "__main__":
    unittest.main()
