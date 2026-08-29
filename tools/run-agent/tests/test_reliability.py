"""Unit tests for aura_rig.reliability — the criterion-3 adjudicator.

Pure functions over dicts; no bench dir, no network, no stack.

The tests are written around the ways this report could LIE, because a
reliability report that flatters a bad set is worse than no report at all.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import reliability as R  # noqa: E402


def rep(n, verdict="PASS", model="opus-5", task="t", sha="abc",
        mode=True, agent_s=100.0, cost=1.0, tools=20, warm="ready"):
    return {"model": model, "task_id": task, "rep": n, "verdict": verdict,
            "cost_usd": cost, "agent_s": agent_s, "tools": tools,
            "preamble_sha": sha, "benchmark_mode_active": mode,
            "inspector_warm": warm, "run_dir": None}


class TestContract(unittest.TestCase):
    """The pooling rule — it can invalidate everything downstream."""

    def test_a_uniform_true_contract_is_poolable(self):
        ok, notes = R.check_contract([rep(1), rep(2), rep(3)])
        self.assertTrue(ok)
        self.assertEqual(notes, [])

    def test_mixed_preamble_sha_is_not_poolable(self):
        ok, notes = R.check_contract([rep(1, sha="aaa"), rep(2, sha="bbb")])
        self.assertFalse(ok)
        self.assertTrue(any("preamble_sha" in n for n in notes))

    def test_benchmark_mode_false_is_not_poolable(self):
        ok, _ = R.check_contract([rep(1), rep(2, mode=False)])
        self.assertFalse(ok)

    def test_benchmark_mode_None_is_NOT_treated_as_either(self):
        # Tri-state. None means the probe could not read it — an unverifiable
        # contract, which is not the same as a verified-off one and must not
        # quietly pass as a verified-on one either.
        ok, notes = R.check_contract([rep(1), rep(2, mode=None)])
        self.assertFalse(ok)
        self.assertTrue(any("None" in n for n in notes))

    def test_an_unpoolable_set_reports_NO_pass_rate(self):
        # The load-bearing consequence: a rate across two contracts is a number
        # with no referent, so it must be withheld, not merely footnoted.
        a = R.assess([rep(1, sha="aaa"), rep(2, sha="bbb")])
        self.assertIsNone(a["pass_rate"])
        self.assertFalse(a["reliable"])


class TestHarnessFaults(unittest.TestCase):

    def test_a_harness_fault_blocks_even_when_every_graded_rep_passed(self):
        # 2 PASS + 1 DRAINER-STALLED reads as "100%" on a pass rate, because
        # non-graded verdicts are excluded — which is exactly how a harness
        # death hides. The whole point of this report is to surface it.
        a = R.assess([rep(1), rep(2), rep(3, verdict="DRAINER-STALLED")])
        self.assertEqual(a["pass_rate"], 1.0)
        self.assertFalse(a["reliable"])
        self.assertTrue(any("HARNESS fault" in b for b in a["blockers"]))

    def test_every_non_graded_verdict_is_named_individually(self):
        a = R.assess([rep(1, verdict="COMMIT-EXHAUSTED"),
                      rep(2, verdict="EDITOR-GONE"), rep(3)])
        joined = " ".join(a["blockers"])
        self.assertIn("COMMIT-EXHAUSTED", joined)
        self.assertIn("EDITOR-GONE", joined)

    def test_unknown_future_verdicts_are_non_graded_by_default(self):
        # GRADED is an ALLOWLIST, mirroring adapters.base — a verdict invented
        # tomorrow must not silently enter a denominator.
        a = R.assess([rep(1), rep(2, verdict="SOMETHING-NEW")])
        self.assertEqual(a["n_graded"], 1)
        self.assertFalse(a["reliable"])

    def test_zero_graded_reps_is_a_blocker_not_a_vacuous_pass(self):
        a = R.assess([rep(1, verdict="STACK-DOWN")])
        self.assertFalse(a["reliable"])
        self.assertTrue(any("nothing was measured" in b for b in a["blockers"]))


class TestConsistency(unittest.TestCase):

    def test_unanimous_pass_is_reliable(self):
        a = R.assess([rep(1), rep(2), rep(3), rep(4), rep(5)])
        self.assertTrue(a["reliable"])
        self.assertEqual(a["pass_rate"], 1.0)

    def test_unanimous_FAIL_is_also_reliable(self):
        # Reliability is about REPEATABILITY, not about passing. A task that
        # fails a model 5/5 is a perfectly trustworthy measurement.
        a = R.assess([rep(n, verdict="FAIL") for n in range(1, 6)])
        self.assertTrue(a["reliable"])
        self.assertEqual(a["pass_rate"], 0.0)

    def test_a_split_is_reported_as_a_split_never_as_a_rate(self):
        a = R.assess([rep(1), rep(2), rep(3, verdict="FAIL")])
        self.assertFalse(a["reliable"])
        self.assertTrue(any("SPLIT" in b for b in a["blockers"]))


class TestGroupingByCell(unittest.TestCase):
    """The mistake that would make the report condemn clean results."""

    def test_two_models_are_judged_separately_not_pooled(self):
        reps = ([rep(n, model="A", verdict="PASS") for n in (1, 2, 3)] +
                [rep(n, model="B", verdict="FAIL") for n in (1, 2, 3)])
        cells = R.by_cell(reps)
        self.assertEqual(len(cells), 2)
        for _, group in cells.items():
            self.assertTrue(R.assess(group)["reliable"])
        # Pooled, this same set reads as a SPLIT — i.e. the bug.
        self.assertFalse(R.assess(reps)["reliable"])

    def test_the_same_model_on_two_tasks_is_two_cells(self):
        reps = [rep(1, task="t1"), rep(1, task="t2")]
        self.assertEqual(len(R.by_cell(reps)), 2)


class TestSpread(unittest.TestCase):

    def test_ratio_distinguishes_a_wide_spread_from_a_narrow_one(self):
        self.assertEqual(R.spread([240, 300])["ratio"], 1.25)
        self.assertEqual(R.spread([240, 1800])["ratio"], 7.5)

    def test_unmeasurable_values_yield_None_not_a_fabricated_zero(self):
        self.assertIsNone(R.spread([None, None]))
        self.assertIsNone(R.spread([]))

    def test_partial_measurements_still_report_on_what_exists(self):
        sp = R.spread([None, 10, 20])
        self.assertEqual((sp["min"], sp["max"]), (10.0, 20.0))


class TestRender(unittest.TestCase):

    def test_a_failing_cell_never_prints_a_bare_pass_rate_as_the_headline(self):
        reps = [rep(1), rep(2), rep(3, verdict="DRAINER-STALLED")]
        text = R.render({("opus-5", "t"): (reps, R.assess(reps))})
        self.assertIn("NOT RELIABLE YET", text)
        self.assertIn("DRAINER-STALLED", text)

    def test_an_empty_bench_is_not_reported_as_reliable(self):
        self.assertIn("No reps found", R.render({}))



class TestSkippedGates(unittest.TestCase):
    """A fixture may SKIP a gate rather than fail it (gp-glide-stamina's gate (5)
    went window-consumed on 2026-08-06 so a slow-but-conforming drain stops
    near-miss failing). Good call — but it means two PASSes can assert DIFFERENT
    things, and rendering them identically overstates the weaker one."""

    def _summary(self, notes):
        return {"verifier": {"layers": {"L2": {"notes": notes}}}}

    def test_extracts_the_gate_label_from_the_fixture_note(self):
        s = self._summary([
            "[GLIDE-RESUME-DIAG] Power never reached ~0 in-window (min=4.2) "
            "\u2014 gate (5) is SKIPPED, not failed."])
        self.assertEqual(R.skipped_gates(s), ["gate (5)"])

    def test_a_fully_gated_run_reports_nothing(self):
        s = self._summary(["[GLIDE-FINAL] granted=1 exhausted=1",
                           "[GLIDE-ADVISORY] gate (5) PASSED on the ratio"])
        self.assertEqual(R.skipped_gates(s), [])

    def test_a_skip_is_a_CAVEAT_not_a_blocker(self):
        # Treating it as a fault would push the fixture back toward the false
        # FAILs the skip exists to prevent.
        reps = [dict(rep(n), skipped_gates=["gate (5)"]) for n in (1, 2, 3)]
        a = R.assess(reps)
        self.assertTrue(a["reliable"])
        self.assertEqual(a["skipped_gates"], ["gate (5)"])
        self.assertFalse(a["inconsistent_gating"])

    def test_a_NON_UNIFORM_skip_inside_one_cell_is_flagged(self):
        # THE case found on 2026-08-09: 1 of 4 -cpp PASSes never tested
        # requirement 5, because the model's own drain rate decided whether the
        # gate applied. Those reps do not mean the same thing.
        reps = [dict(rep(1), skipped_gates=["gate (5)"]),
                dict(rep(2), skipped_gates=[]),
                dict(rep(3), skipped_gates=[])]
        a = R.assess(reps)
        self.assertTrue(a["inconsistent_gating"])
        text = R.render({("opus-5", "t"): (reps, a)})
        self.assertIn("gates SKIPPED", text)
        self.assertIn("not all mean the same thing", text)

if __name__ == "__main__":
    unittest.main()
