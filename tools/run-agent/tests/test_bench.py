"""Unit tests for aura_rig.bench — the sequential {model}x{task} repetition bench.

UE-free: the rep runner is an injected seam (matrix.py pattern), so the loop +
aggregation + rendering run against canned RepResults; `pause` is injected so
tests never sleep.
"""
import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from aura_rig import bench as bch


class TestSplitBenchModels(unittest.TestCase):
    def test_partition_baseline_vs_unsupported(self):
        # The `product` partition went with the aura-product lane. What reaches
        # this function is already routable: cmd_bench refuses aura-product /
        # aura-mcp / bare-Aura-key slugs via _refuse_unroutable_model BEFORE
        # calling it (cb.py), so the split only has to separate the models
        # `cb bench` can drive from unreal-mcp, which needs one editor per run
        # and is driven by `cb eval` instead.
        from aura_rig.cb import _split_bench_models
        baseline, unsupported = _split_bench_models(
            ["claude-p:sonnet", "openrouter:openai/gpt-4o-mini",
             "bare:openai/gpt-4o-mini", "unreal-mcp:opus"])
        self.assertEqual(baseline, ["claude-p:sonnet",
                                    "openrouter:openai/gpt-4o-mini",
                                    "bare:openai/gpt-4o-mini"])
        self.assertEqual(unsupported, ["unreal-mcp:opus"])

    def test_the_refusal_that_makes_this_split_safe(self):
        # Guards the premise above: if a removed backend ever stopped being
        # refused, it would silently land in `baseline` and burn a bench.
        from aura_rig.cb import _refuse_unroutable_model
        for slug in ("aura-product:opus-4.8", "aura-mcp:sonnet-4.6", "sonnet-4.6"):
            self.assertTrue(_refuse_unroutable_model(slug), slug)
        for slug in ("claude-p:sonnet", "unreal-mcp:opus", "bare:x/y"):
            self.assertFalse(_refuse_unroutable_model(slug), slug)


class TestParseTaskSpec(unittest.TestCase):
    def test_per_task_override_and_default(self):
        self.assertEqual(bch.parse_task_spec("a:5,b", 3), [("a", 5), ("b", 3)])

    def test_set_qualified_ids_keep_their_slash(self):
        self.assertEqual(bch.parse_task_spec("flagship/t0:2", 3),
                         [("flagship/t0", 2)])

    def test_non_digit_suffix_is_part_of_the_id(self):
        self.assertEqual(bch.parse_task_spec("weird:name", 2), [("weird:name", 2)])

    def test_dedupe_blank_and_floor(self):
        self.assertEqual(bch.parse_task_spec(" a , ,a:9", 0), [("a", 1)])
        self.assertEqual(bch.parse_task_spec("", 3), [])


class TestBuildReps(unittest.TestCase):
    def test_reps_of_a_pair_run_back_to_back(self):
        reps = bch.build_reps(["M"], [("t1", 2), ("t2", 1)])
        self.assertEqual([(r.task_id, r.rep, r.n_reps) for r in reps],
                         [("t1", 1, 2), ("t1", 2, 2), ("t2", 1, 1)])

    def test_multi_task_order_is_task_major_models_within(self):
        # Per-task BLOCKS (a task switch invalidates the composed scratch's
        # incremental build), models within a block, reps of a pair
        # back-to-back.
        reps = bch.build_reps(["A", "B"], [("t1", 2), ("t2", 1)])
        self.assertEqual([(r.task_id, r.model, r.rep) for r in reps],
                         [("t1", "A", 1), ("t1", "A", 2),
                          ("t1", "B", 1), ("t1", "B", 2),
                          ("t2", "A", 1), ("t2", "B", 1)])

    def test_model_groups_run_as_ordered_phases(self):
        # cmd_bench passes [baseline, product]: every baseline rep (all tasks)
        # runs BEFORE any product rep, so baselines never build under the
        # product stack's memory pressure; each phase is task-major within.
        reps = bch.build_reps(["base", "prod"], [("t1", 1), ("t2", 1)],
                              model_groups=[["base"], ["prod"]])
        self.assertEqual([(r.model, r.task_id) for r in reps],
                         [("base", "t1"), ("base", "t2"),
                          ("prod", "t1"), ("prod", "t2")])

    def test_empty_group_is_dropped(self):
        # A baseline-only or product-only bench passes one empty group.
        reps = bch.build_reps(["prod"], [("t1", 1)],
                              model_groups=[[], ["prod"]])
        self.assertEqual([(r.model, r.task_id) for r in reps],
                         [("prod", "t1")])


class TestAggregate(unittest.TestCase):
    def _mix(self):
        return [
            bch.RepResult("M", "t0", 1, "PASS", cost_usd=0.5, agent_s=60, verify_s=240),
            bch.RepResult("M", "t0", 2, "PASS", cost_usd=0.7, agent_s=80, verify_s=250),
            bch.RepResult("M", "t0", 3, "FAIL", cost_usd=0.6, agent_s=70, verify_s=245),
            # HARNESS-ERROR, not SANDBOX-REJECT: this fixture's job is to be a
            # NON-graded rep, and SANDBOX-REJECT stopped being one on 2026-08-17
            # (it is a model outcome — the denominator rule). Swapped rather
            # than deleted so the "a harness fault never counts as a FAIL"
            # assertions below keep testing that.
            bch.RepResult("M", "gas", 1, "HARNESS-ERROR", cost_usd=0.1),
            bch.RepResult("M", "gas", 2, None, error="no result.json (run.py exit 4)"),
        ]

    def test_pair_stats_and_graded_denominator(self):
        agg = bch.aggregate(self._mix(), ["M"], [("t0", 3), ("gas", 2)])
        t0 = agg["by_pair"]["M :: t0"]
        self.assertEqual((t0["pass"], t0["fail"], t0["graded_n"]), (2, 1, 3))
        self.assertAlmostEqual(t0["pass_rate"], 2 / 3)
        self.assertAlmostEqual(t0["cost_usd"]["mean"], 0.6)
        self.assertAlmostEqual(t0["cost_usd"]["total"], 1.8)
        self.assertEqual(t0["agent_s"]["min"], 60)
        self.assertEqual(t0["agent_s"]["max"], 80)
        gas = agg["by_pair"]["M :: gas"]
        self.assertEqual(gas["graded_n"], 0)
        self.assertIsNone(gas["pass_rate"])       # non-graded/error never count as FAIL
        self.assertEqual(gas["non_graded"], 1)
        self.assertEqual(gas["errors"], 1)

    def test_a_sandbox_reject_rep_is_graded_as_a_non_pass(self):
        """The other half of the split, pinned so the swap above can't hide it.

        A SANDBOX-REJECT is the model submitting outside the writable set. It
        counts, as a non-pass — otherwise a model that reliably writes to denied
        paths scores 100% on the reps it happens to get right. Before 2026-08-17
        this pair reported graded_n=1 / pass_rate=1.0.
        """
        reps = [
            bch.RepResult("M", "t0", 1, "PASS", cost_usd=0.5),
            bch.RepResult("M", "t0", 2, "SANDBOX-REJECT", cost_usd=0.1),
        ]
        pair = bch.aggregate(reps, ["M"], [("t0", 2)])["by_pair"]["M :: t0"]
        self.assertEqual(pair["graded_n"], 2)
        self.assertEqual(pair["pass"], 1)
        self.assertAlmostEqual(pair["pass_rate"], 0.5)
        self.assertEqual(pair["non_graded"], 0)

    def test_model_rollup(self):
        agg = bch.aggregate(self._mix(), ["M"], [("t0", 3), ("gas", 2)])
        m = agg["by_model"]["M"]
        self.assertEqual(m["reps_done"], 5)
        self.assertEqual(m["pass"], 2)
        self.assertAlmostEqual(m["cost_usd"]["total"], 1.9)

    def test_render_markdown_carries_tool_mix(self):
        reps = [bch.RepResult("M", "t0", 1, "PASS", cost_usd=0.5, agent_s=60,
                              verify_s=240, num_turns=7, tool_use_count=6,
                              tool_names=["Read", "Read", "Edit"])]
        md = bch.render_markdown(bch.aggregate(reps, ["M"], [("t0", 1)]))
        self.assertIn("Read×2", md)
        self.assertIn("Edit×1", md)
        self.assertIn("$0.5000", md)


class TestFlagThreadReuse(unittest.TestCase):
    """Rep INDEPENDENCE. Regression for the 2026-08-10 finding: thread
    4bf9bfa4-… served nine runs, and four consecutive reps of one bench were
    four turns of one conversation — reps 1-3 scored PASS, the third having
    read nothing at all. Across all nine: 5 PASS / 2 FAIL / 1 GRADE-SPAWN-DIED,
    which is why demotion must apply to a FAIL too."""

    @staticmethod
    def _rep(n, verdict, tid):
        return bch.RepResult("grok-4.5", "bp-g2/glide", n, verdict, thread_id=tid)

    def test_first_rep_on_a_thread_keeps_its_verdict(self):
        reps = [self._rep(1, "PASS", "tab_a")]
        self.assertEqual(bch.flag_thread_reuse(reps), 0)
        self.assertEqual(reps[0].verdict, "PASS")
        self.assertIsNone(reps[0].thread_reused_from)

    def test_later_reps_on_one_thread_are_demoted_and_the_first_is_not(self):
        reps = [self._rep(i, "PASS", "4bf9bfa4") for i in (1, 2, 3, 4)]
        self.assertEqual(bch.flag_thread_reuse(reps), 3)
        self.assertEqual(reps[0].verdict, "PASS")           # opened the thread
        for r in reps[1:]:
            self.assertEqual(r.verdict, bch.VERDICT_THREAD_REUSED)
            self.assertEqual(r.underlying_verdict, "PASS")  # preserved, not lost
            self.assertIn("rep 1", r.thread_reused_from)

    def test_a_fail_on_a_reused_thread_is_demoted_too(self):
        """The inverse of the pass-rate worry: a contaminated rep must not land
        in the denominator as an agent FAIL either."""
        reps = [self._rep(1, "PASS", "x"), self._rep(2, "FAIL", "x")]
        bch.flag_thread_reuse(reps)
        self.assertEqual(reps[1].verdict, bch.VERDICT_THREAD_REUSED)
        self.assertEqual(reps[1].underlying_verdict, "FAIL")

    def test_demoted_reps_leave_the_graded_denominator(self):
        reps = [self._rep(1, "PASS", "x"), self._rep(2, "PASS", "x"),
                self._rep(3, "PASS", "x")]
        bch.flag_thread_reuse(reps)
        pair = bch.aggregate(reps, ["grok-4.5"],
                             [("bp-g2/glide", 3)])["by_pair"]["grok-4.5 :: bp-g2/glide"]
        self.assertEqual(pair["graded_n"], 1)      # not 3
        self.assertEqual(pair["non_graded"], 2)
        self.assertEqual(pair["pass_rate"], 1.0)   # of the ONE real rep

    def test_known_threads_catches_a_first_rep_with_no_in_bench_duplicate(self):
        """The case in-bench uniqueness structurally cannot see — and four of
        the nine measured collisions were exactly this."""
        reps = [self._rep(1, "PASS", "4bf9bfa4")]
        n = bch.flag_thread_reuse(
            reps, known_threads={"4bf9bfa4": "an earlier run (…-20260809-020710)"})
        self.assertEqual(n, 1)
        self.assertEqual(reps[0].verdict, bch.VERDICT_THREAD_REUSED)
        self.assertIn("20260809-020710", reps[0].thread_reused_from)

    def test_missing_thread_ids_are_not_grouped_with_each_other(self):
        """None is 'not observed', not 'the same conversation'. A drive that
        died before any POST must not demote the next rep."""
        reps = [self._rep(1, "PASS", None), self._rep(2, "PASS", None)]
        self.assertEqual(bch.flag_thread_reuse(reps), 0)
        self.assertTrue(all(r.verdict == "PASS" for r in reps))

    def test_an_already_non_graded_rep_is_flagged_but_not_relabelled(self):
        """A more specific non-graded label (STACK-DOWN) is the better
        diagnosis and already excluded from the rate — keep it."""
        reps = [self._rep(1, "PASS", "x"), self._rep(2, "STACK-DOWN", "x")]
        self.assertEqual(bch.flag_thread_reuse(reps), 0)
        self.assertEqual(reps[1].verdict, "STACK-DOWN")
        self.assertIsNotNone(reps[1].thread_reused_from)   # still recorded

    def test_running_twice_does_not_double_demote(self):
        """bench.run calls it after EVERY rep, so it must be idempotent — a
        second pass must not turn THREAD-REUSED into its own underlying."""
        reps = [self._rep(1, "PASS", "x"), self._rep(2, "PASS", "x")]
        bch.flag_thread_reuse(reps)
        self.assertEqual(bch.flag_thread_reuse(reps), 0)
        self.assertEqual(reps[1].underlying_verdict, "PASS")

    def test_distinct_threads_are_left_alone(self):
        reps = [self._rep(i, "PASS", f"tab_{i}") for i in (1, 2, 3, 4, 5)]
        self.assertEqual(bch.flag_thread_reuse(reps), 0)

    def test_aggregate_reports_the_collision_as_a_provenance_warning(self):
        reps = [self._rep(1, "PASS", "x"), self._rep(2, "PASS", "x")]
        bch.flag_thread_reuse(reps)
        agg = bch.aggregate(reps, ["grok-4.5"], [("bp-g2/glide", 2)])
        warns = " ".join(agg["provenance_warnings"])
        self.assertIn("NOT an independent rep", warns)
        self.assertEqual(agg["reps"][1]["thread_id"], "x")

    def test_reuse_is_not_a_graded_verdict(self):
        from adapters.base import is_graded_verdict
        self.assertFalse(is_graded_verdict(bch.VERDICT_THREAD_REUSED))

    def test_a_resumed_rep_does_not_collide_with_its_own_earlier_run(self):
        """The bench-side HALF of the resume fix: given a correct (excluded)
        `known_threads`, a resumed rep keeps its verdict and is not re-run.

        This does NOT pin the resume bug itself — that lived in which run dirs
        `cb._threads_already_used` scans, and handing run() an already-correct
        `known_threads` cannot see it. The test that pins it is
        test_cb_routing.TestThreadsAlreadyUsed
        .test_excluded_run_dirs_do_not_contribute_their_thread, which was
        negative-controlled against the broken implementation."""
        prior = [bch.RepResult("grok-4.5", "t0", 1, "PASS", thread_id="T1",
                               run_dir="runs/aura-product/x")]
        # What cb.py must NOT pass: T1 keyed from the resumed rep's own run dir.
        agg = bch.run(["grok-4.5"], [("t0", 1)],
                      lambda rep: self.fail("resumed rep must not be re-run"),
                      Path(tempfile.mkdtemp()), log=lambda *_: None,
                      prior=prior, pause=lambda: None,
                      known_threads={})           # correctly excluded by cb.py
        self.assertEqual(agg["reps"][0]["verdict"], "PASS")
        self.assertIsNone(agg["reps"][0]["thread_reused_from"])

    def test_a_resumed_rep_still_collides_with_a_genuine_earlier_bench(self):
        """The other half: excluding the rep's OWN run dir must not blind the
        guard to a DIFFERENT earlier run that used the same thread — which is
        the case worth catching, and why cb.py excludes by run dir rather than
        by thread id."""
        prior = [bch.RepResult("grok-4.5", "t0", 1, "PASS", thread_id="T1",
                               run_dir="runs/aura-product/x")]
        agg = bch.run(["grok-4.5"], [("t0", 1)],
                      lambda rep: self.fail("resumed rep must not be re-run"),
                      Path(tempfile.mkdtemp()), log=lambda *_: None,
                      prior=prior, pause=lambda: None,
                      known_threads={"T1": "an earlier run (some-other-bench)"})
        self.assertEqual(agg["reps"][0]["verdict"], bch.VERDICT_THREAD_REUSED)
        self.assertEqual(agg["reps"][0]["underlying_verdict"], "PASS")

    def test_the_spelling_is_the_published_one(self):
        """The literal is the report surface, not an internal enum: it lands in
        bench.json, in the markdown grid and in the HTML badge, so a rename
        silently splits one condition into two across archived benches. Until
        the 2026-08-28 public release this was cross-checked against the
        aura-product spine's own copy of the constant; that lane is gone, so
        the literal itself is now the thing pinned."""
        self.assertEqual(bch.VERDICT_THREAD_REUSED, "THREAD-REUSED")


class TestFlagMismatch(unittest.TestCase):
    def test_envelope_flag_wins(self):
        mm, reason = bch.flag_mismatch("sonnet-5", None, envelope_flag=True)
        self.assertTrue(mm)
        self.assertIn("model_mismatch flag", reason)

    def test_absent_or_empty_models_used_is_not_a_mismatch(self):
        # agent.models_used only exists on 2026-07-22+ envelopes — absence
        # means "unattributed", never "wrong model".
        self.assertEqual(bch.flag_mismatch("claude-p:opus", None), (False, None))
        self.assertEqual(bch.flag_mismatch("claude-p:opus", []), (False, None))

    def test_pinned_slug_disjoint_flags(self):
        mm, reason = bch.flag_mismatch("claude-p:sonnet", ["claude-opus-4-8"])
        self.assertTrue(mm)
        self.assertIn("sonnet", reason)

    def test_pinned_slug_matching_core_passes(self):
        self.assertEqual(
            bch.flag_mismatch("claude-p:opus", ["claude-opus-4-8"]), (False, None))

    def test_openrouter_pin_matches_bare_model_name(self):
        self.assertEqual(
            bch.flag_mismatch("openrouter:openai/gpt-4o-mini", ["gpt-4o-mini"]),
            (False, None))

    def test_bare_slug_is_annotated_never_flagged(self):
        mm, reason = bch.flag_mismatch("claude-p", ["claude-fable-5"])
        self.assertFalse(mm)
        self.assertEqual(reason, "session-default (unpinned slug)")


class TestComparisonAggregate(unittest.TestCase):
    def test_mismatch_counts_and_nongraded_exclusion(self):
        reps = [
            bch.RepResult("M", "t0", 1, "PASS", cost_usd=0.1),
            bch.RepResult("M", "t0", 2, "MODEL-MISMATCH", cost_usd=0.2,
                          models_mismatch=True,
                          mismatch_reason="envelope model_mismatch flag",
                          underlying_verdict="PASS"),
        ]
        agg = bch.aggregate(reps, ["M"], [("t0", 2)])
        pair = agg["by_pair"]["M :: t0"]
        self.assertEqual(pair["mismatches"], 1)
        self.assertEqual(pair["graded_n"], 1)            # mismatch = non-graded
        self.assertAlmostEqual(pair["pass_rate"], 1.0)   # never a FAIL under a wrong label
        self.assertEqual(agg["by_model"]["M"]["mismatches"], 1)
        row = agg["reps"][1]
        self.assertEqual(row["underlying_verdict"], "PASS")  # substitution kept the evidence

    def test_provenance_warning_on_mixed_substrate_revisions(self):
        reps = [
            bch.RepResult("M", "t0", 1, "PASS", substrate_revision="aaaa111"),
            bch.RepResult("M", "t0", 2, "PASS", substrate_revision="bbbb222"),
        ]
        warns = bch.aggregate(reps, ["M"], [("t0", 2)])["provenance_warnings"]
        self.assertEqual(len(warns), 1)
        self.assertIn("substrate revision", warns[0])

    def test_single_revision_yields_no_warning(self):
        reps = [bch.RepResult("M", "t0", 1, "PASS", substrate_revision="aaaa111"),
                bch.RepResult("M", "t0", 2, "PASS", substrate_revision="aaaa111")]
        self.assertEqual(bch.aggregate(reps, ["M"], [("t0", 2)])["provenance_warnings"], [])


class TestRenderLeaderboard(unittest.TestCase):
    # The `project/000000` in the posthog_url fixtures below is a PLACEHOLDER,
    # not a real project: the leaderboard only ever passes the URL through
    # verbatim, so no assertion here depends on the digits. Scrubbed for the
    # public release 2026-08-28 — do not "restore" a live project id.
    def _agg(self):
        reps = [
            bch.RepResult("A", "t0", 1, "PASS", cost_usd=0.5, agent_s=60,
                          report_href="reps/r01-abc/run1/report.html",
                          posthog_url="https://us.posthog.com/project/000000/"
                                      "llm-analytics/traces/th-1"),
            bch.RepResult("A", "t0", 2, "FAIL", cost_usd=0.6, agent_s=70),  # no report
            bch.RepResult("B", "t0", 1, "MODEL-MISMATCH", cost_usd=0.1,
                          models_mismatch=True, mismatch_reason="pinned 'x' not among ['y']",
                          underlying_verdict="PASS"),
        ]
        return bch.aggregate(reps, ["A", "B"], [("t0", 2)])

    def test_html_grid_links_badges_and_mismatch_chip(self):
        page = bch.render_html(self._agg())
        self.assertIn("<a class='badge'", page)                       # linked rep
        self.assertIn("href='reps/r01-abc/run1/report.html'", page)
        self.assertIn("<span class='badge'", page)                    # link-free rep
        self.assertIn("<sup class='mm'>MM</sup>", page)               # mismatch chip
        self.assertIn("Standings", page)
        # both reps of the A::t0 cell render (multi-rep cell)
        self.assertIn("PASS", page)
        self.assertIn("FAIL", page)

    def test_markdown_grid_links_and_mismatch_marker(self):
        md = bch.render_markdown(self._agg())
        self.assertIn("### Model × task grid", md)
        self.assertIn("[PASS](reps/r01-abc/run1/report.html)", md)
        self.assertIn("MODEL-MISMATCH!", md)
        self.assertIn("PASS · FAIL", md.replace("[PASS](reps/r01-abc/run1/report.html)", "PASS"))

    def test_posthog_trace_chip_next_to_badge(self):
        # aura-product reps carry summary.json's posthog_url; the leaderboard
        # renders it as a companion chip so the badge keeps opening report.html.
        page = bch.render_html(self._agg())
        self.assertIn("<a class='ph' href='https://us.posthog.com/project/"
                      "000000/llm-analytics/traces/th-1'", page)
        # exactly one chip — the two url-less reps must render chip-free
        self.assertEqual(page.count("class='ph'"), 1)

    def test_markdown_per_rep_detail_carries_trace_link(self):
        md = bch.render_markdown(self._agg())
        self.assertIn("| Trace |", md)
        self.assertIn("[trace](https://us.posthog.com/project/000000/"
                      "llm-analytics/traces/th-1)", md)

    def test_aggregate_rep_row_carries_posthog_url(self):
        agg = self._agg()
        self.assertEqual(agg["reps"][0]["posthog_url"],
                         "https://us.posthog.com/project/000000/"
                         "llm-analytics/traces/th-1")
        self.assertIsNone(agg["reps"][1]["posthog_url"])

    def test_provenance_warning_rendered(self):
        reps = [bch.RepResult("A", "t0", 1, "PASS", substrate_revision="aaaa111"),
                bch.RepResult("A", "t0", 2, "PASS", substrate_revision="bbbb222")]
        agg = bch.aggregate(reps, ["A"], [("t0", 2)])
        self.assertIn("substrate revision", bch.render_markdown(agg))
        self.assertIn("class='warn'", bch.render_html(agg))


class TestPriorRepsRoundtrip(unittest.TestCase):
    def test_old_bench_json_without_comparison_fields_rehydrates(self):
        # Pre-2026-07-23 bench.json rows lack the comparison fields — resume
        # must rehydrate them to inert defaults, never crash.
        from aura_rig.cb import _load_prior_reps
        old_row = {"model": "M", "task_id": "t0", "rep": 1, "verdict": "PASS",
                   "cost_usd": 0.1, "agent_s": 5, "verify_s": 10,
                   "tokens_in": None, "tokens_out": None, "num_turns": 3,
                   "tool_use_count": 2, "tool_names": ["Read"],
                   "run_dir": "runs/x", "error": None}
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bench.json"
            p.write_text(json.dumps({"reps": [old_row]}), encoding="utf-8")
            reps = _load_prior_reps(p, bch)
        self.assertEqual(len(reps), 1)
        r = reps[0]
        self.assertEqual(r.verdict, "PASS")
        self.assertIsNone(r.models_used)
        self.assertFalse(r.models_mismatch)
        self.assertIsNone(r.report_href)
        self.assertIsNone(r.posthog_url)

    def test_posthog_url_roundtrips_through_bench_json(self):
        from aura_rig.cb import _load_prior_reps
        url = "https://us.posthog.com/project/000000/llm-analytics/traces/th-9"
        row = {"model": "M", "task_id": "t0", "rep": 1, "verdict": "PASS",
               "posthog_url": url}
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bench.json"
            p.write_text(json.dumps({"reps": [row]}), encoding="utf-8")
            reps = _load_prior_reps(p, bch)
        self.assertEqual(reps[0].posthog_url, url)


class TestRunLoop(unittest.TestCase):
    def test_sequential_incremental_persistence_and_error_capture(self):
        calls = []
        pauses = []

        def _runner(rep):
            calls.append((rep.task_id, rep.rep))
            if rep.rep == 2:
                raise RuntimeError("boom")
            return bch.RepResult(rep.model, rep.task_id, rep.rep, "PASS",
                                 cost_usd=0.1, agent_s=1.0, verify_s=2.0)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench-x"
            agg = bch.run(["M"], [("t0", 3)], _runner, out,
                          log=lambda s: None, pause=lambda: pauses.append(1))
            self.assertEqual(calls, [("t0", 1), ("t0", 2), ("t0", 3)])
            self.assertEqual(len(pauses), 2)     # between consecutive reps only
            on_disk = json.loads((out / "bench.json").read_text(encoding="utf-8"))
            self.assertEqual(len(on_disk["reps"]), 3)
            self.assertTrue((out / "bench.md").exists())
            self.assertTrue((out / "leaderboard.html").exists())  # incremental grid
            page = (out / "leaderboard.html").read_text(encoding="utf-8")
            self.assertIn("Model &times; task grid", page)
        pair = agg["by_pair"]["M :: t0"]
        self.assertEqual(pair["pass"], 2)
        self.assertEqual(pair["errors"], 1)      # the raise became an ERROR rep
        self.assertAlmostEqual(pair["pass_rate"], 1.0)  # errors excluded from denominator


class TestResume(unittest.TestCase):
    def test_graded_reps_reused_errors_and_nongraded_rerun(self):
        ran = []

        def _runner(rep):
            ran.append((rep.task_id, rep.rep))
            return bch.RepResult(rep.model, rep.task_id, rep.rep, "PASS",
                                 cost_usd=0.2, agent_s=5, verify_s=10)

        prior = [
            bch.RepResult("M", "t0", 1, "PASS", cost_usd=0.1),      # keep
            bch.RepResult("M", "t0", 2, "FAIL", cost_usd=0.1),      # keep (graded)
            bch.RepResult("M", "t0", 3, None, error="bring-up x3"),  # re-run (error)
            bch.RepResult("M", "gas", 1, "MODEL-MISMATCH"),         # re-run (non-graded)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bench-resume"
            agg = bch.run(["M"], [("t0", 3), ("gas", 1)], _runner, out,
                          log=lambda s: None, pause=lambda: None, prior=prior)
        # only the error rep (t0/3) and the non-graded rep (gas/1) re-ran.
        self.assertEqual(sorted(ran), [("gas", 1), ("t0", 3)])
        t0 = agg["by_pair"]["M :: t0"]
        self.assertEqual((t0["pass"], t0["fail"], t0["reps_done"]), (2, 1, 3))
        gas = agg["by_pair"]["M :: gas"]
        self.assertEqual(gas["pass"], 1)   # gas/1 re-ran to PASS

    def test_no_pause_before_resumed_reps(self):
        pauses = []
        prior = [bch.RepResult("M", "t0", 1, "PASS"),
                 bch.RepResult("M", "t0", 2, "PASS")]

        def _runner(rep):
            return bch.RepResult(rep.model, rep.task_id, rep.rep, "PASS")

        with tempfile.TemporaryDirectory() as tmp:
            bch.run(["M"], [("t0", 3)], _runner, Path(tmp) / "b",
                    log=lambda s: None, pause=lambda: pauses.append(1), prior=prior)
        # reps 1-2 resumed (no run, no pause); only rep 3 runs -> first RUN rep,
        # so no pause precedes it either.
        self.assertEqual(len(pauses), 0)


class TestTwoTaskGrid(unittest.TestCase):
    """A multi-task bench must render one COLUMN per task with each rep badge
    in its own (model, task) cell — proven, not assumed."""

    def _agg(self):
        reps = [
            bch.RepResult("A", "glide-bp", 1, "PASS", cost_usd=0.5,
                          report_href="reps/r01-aaa/run1/report.html"),
            bch.RepResult("A", "glide-bp", 2, "FAIL", cost_usd=0.6),
            bch.RepResult("A", "poison-cpp", 1, "PASS", cost_usd=0.4),
            bch.RepResult("B", "glide-bp", 1, "FAIL", cost_usd=0.2),
            bch.RepResult("B", "poison-cpp", 1, "PASS", cost_usd=0.3),
        ]
        return bch.aggregate(reps, ["A", "B"],
                             [("glide-bp", 2), ("poison-cpp", 1)])

    def test_markdown_grid_has_a_column_per_task(self):
        md = bch.render_markdown(self._agg())
        self.assertIn("| Model | `glide-bp` | `poison-cpp` |", md)
        # A's glide-bp GRID cell carries BOTH reps; its poison-cpp cell one
        # (scope to the grid section — the per-pair stats table above it also
        # has rows starting "| `A` |").
        grid = md.split("### Model × task grid", 1)[1]
        row_a = next(ln for ln in grid.splitlines()
                     if ln.startswith("| `A` |"))
        cells = [c.strip() for c in row_a.split("|")[2:-1]]
        self.assertIn("FAIL", cells[0])            # glide-bp cell, rep 2
        self.assertIn("PASS", cells[0])            # glide-bp cell, rep 1
        self.assertEqual(cells[1], "PASS")         # poison-cpp cell

    def test_html_grid_has_a_header_per_task_and_cells_per_pair(self):
        page = bch.render_html(self._agg())
        self.assertIn("<th>glide-bp</th>", page)
        self.assertIn("<th>poison-cpp</th>", page)
        # 2 models x 2 tasks = 4 grid cells, none em-dash-empty.
        self.assertEqual(page.count("<td class='cell'>"), 4)
        self.assertNotIn("<td class='cell'>—</td>", page)

    def test_per_pair_table_has_a_row_per_cell(self):
        agg = self._agg()
        self.assertEqual(
            set(agg["by_pair"]),
            {"A :: glide-bp", "A :: poison-cpp",
             "B :: glide-bp", "B :: poison-cpp"})
        self.assertEqual(agg["by_pair"]["A :: glide-bp"]["graded_n"], 2)


class TestResumeMultiTask(unittest.TestCase):
    def test_rep_identity_is_model_task_and_rep_index(self):
        # A resumed multi-task bench must reuse a graded rep ONLY for its own
        # (model, task, rep) cell — the same rep index of a DIFFERENT task
        # still runs.
        ran = []

        def _runner(rep):
            ran.append((rep.model, rep.task_id, rep.rep))
            return bch.RepResult(rep.model, rep.task_id, rep.rep, "PASS")

        prior = [
            bch.RepResult("M", "glide-bp", 1, "PASS"),     # keep
            bch.RepResult("M", "poison-cpp", 2, "FAIL"),   # keep (graded)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            agg = bch.run(["M"], [("glide-bp", 2), ("poison-cpp", 2)],
                          _runner, Path(tmp) / "b", log=lambda s: None,
                          pause=lambda: None, prior=prior)
        self.assertEqual(sorted(ran),
                         [("M", "glide-bp", 2), ("M", "poison-cpp", 1)])
        self.assertEqual(agg["by_pair"]["M :: glide-bp"]["reps_done"], 2)
        self.assertEqual(agg["by_pair"]["M :: poison-cpp"]["reps_done"], 2)

    def test_model_groups_do_not_change_resume_identity(self):
        ran = []

        def _runner(rep):
            ran.append((rep.model, rep.task_id, rep.rep))
            return bch.RepResult(rep.model, rep.task_id, rep.rep, "PASS")

        prior = [bch.RepResult("base", "t1", 1, "PASS"),
                 bch.RepResult("prod", "t2", 1, "FAIL")]
        with tempfile.TemporaryDirectory() as tmp:
            bch.run(["base", "prod"], [("t1", 1), ("t2", 1)], _runner,
                    Path(tmp) / "b", log=lambda s: None, pause=lambda: None,
                    prior=prior, model_groups=[["base"], ["prod"]])
        # both prior graded reps reused regardless of phase grouping.
        self.assertEqual(sorted(ran),
                         [("base", "t2", 1), ("prod", "t1", 1)])


class TestCostPreview(unittest.TestCase):
    def test_anchor_matches_on_the_pinned_core(self):
        self.assertEqual(bch.cost_anchor_usd("opus-4.8"), 4.0)
        self.assertEqual(bch.cost_anchor_usd("claude-p:opus"), 4.0)
        self.assertEqual(bch.cost_anchor_usd(
            "openrouter:anthropic/claude-opus-4"), 4.0)
        self.assertEqual(bch.cost_anchor_usd("sonnet-5"), 1.5)
        self.assertEqual(bch.cost_anchor_usd("deepseek-v3"), 0.05)
        self.assertIsNone(bch.cost_anchor_usd("grok-4"))
        self.assertIsNone(bch.cost_anchor_usd(""))

    def test_preview_prints_cells_anchors_ceiling_and_floor_total(self):
        txt = bch.render_cost_preview(
            ["opus-4.8", "grok-4", "luna", "deepseek-v3"],
            [("glide-bp", 2), ("glide-cpp", 2), ("poison-bp", 2),
             ("poison-cpp", 2)],
            ceiling_s=1200)
        self.assertIn("4 model(s) x 4 task(s) = 16 cell(s)", txt)
        self.assertIn("32 rep(s) total", txt)
        self.assertIn("agent ceiling 1200s/rep", txt)
        self.assertIn("glide-bp x2", txt)
        self.assertIn("~$4.00/rep", txt)                 # opus anchor
        self.assertIn("~$0.05/rep", txt)                 # deepseek anchor
        # opus 8 reps x $4 + deepseek 8 x $0.05 = $32.40; grok/luna unanchored.
        self.assertIn("TOTAL est ~$32.40", txt)
        self.assertIn("16 rep(s) with no anchor", txt)
        self.assertIn("floor", txt)
        self.assertNotIn("--resume", txt)

    def test_resumed_preview_says_reps_are_reused(self):
        txt = bch.render_cost_preview(["opus-4.8"], [("t0", 3)], 900,
                                      resumed=True)
        self.assertIn("--resume: graded reps are reused", txt)


class TestRefusedCells(unittest.TestCase):
    def test_baseline_on_asset_task_is_refused_product_is_not(self):
        from aura_rig.cb import _refused_cells
        refused = _refused_cells(
            ["claude-p:sonnet", "openrouter:openai/gpt-5"],
            [("glide-bp", 2), ("glide-cpp", 2)],
            asset_task_ids={"glide-bp"})
        # task-major, matching execution order; only the asset task refuses.
        self.assertEqual(refused,
                         [("claude-p:sonnet", "glide-bp"),
                          ("openrouter:openai/gpt-5", "glide-bp")])

    def test_no_asset_tasks_means_no_refusals(self):
        from aura_rig.cb import _refused_cells
        self.assertEqual(
            _refused_cells(["claude-p:sonnet"], [("t0", 3)], set()), [])

    def test_product_only_matrix_never_refuses(self):
        # _refused_cells receives only the BASELINE partition — a product-only
        # bench passes [] and no asset task can refuse anything.
        from aura_rig.cb import _refused_cells
        self.assertEqual(
            _refused_cells([], [("glide-bp", 2)], {"glide-bp"}), [])


class TestAssetDeliverableDerivation(unittest.TestCase):
    """asset_deliverable_task derives from the spec's OWN L2I declaration via
    THE single parser — never from task-id naming."""

    def _spec(self, tmp: Path, body: str) -> Path:
        p = tmp / "task.md"
        p.write_text(body, encoding="utf-8")
        return p

    def test_l2i_spec_is_asset_deliverable(self):
        from aura_rig import tasks as _tasks
        with tempfile.TemporaryDirectory() as td:
            p = self._spec(Path(td),
                           "---\nid: x\nlayers: [L1, L2I]\n"
                           "introspect: [x.py]\n---\n\n# x\n")
            self.assertTrue(_tasks.asset_deliverable_task(p))

    def test_l1_l2_spec_is_not(self):
        from aura_rig import tasks as _tasks
        with tempfile.TemporaryDirectory() as td:
            p = self._spec(Path(td),
                           "---\nid: x\nlayers: [L1, L2]\n"
                           "fixtures: [\"L_X :: AXFunctionalTest\"]\n---\n\n# x\n")
            self.assertFalse(_tasks.asset_deliverable_task(p))

    def test_unreadable_spec_is_false_not_a_crash(self):
        from aura_rig import tasks as _tasks
        self.assertFalse(_tasks.asset_deliverable_task(
            Path("does") / "not" / "exist.md"))


class TestRefgates(unittest.TestCase):
    def test_gates_are_opt_in_regardless_of_task_count(self):
        # Owner decision 2026-08-06: bench gates ONLY under --refgates; the
        # old multi-task default (and its single-task asymmetry) is retired.
        # The explicit flag is honored on any task count, incl. a single task.
        from aura_rig.cb import _refgates_apply
        multi = [("a", 2), ("b", 2)]
        single = [("a", 2)]
        self.assertFalse(_refgates_apply(multi, opt_in=False))
        self.assertFalse(_refgates_apply(single, opt_in=False))
        self.assertTrue(_refgates_apply(multi, opt_in=True))
        self.assertTrue(_refgates_apply(single, opt_in=True))
        self.assertFalse(_refgates_apply([], opt_in=True))

    def test_skip_callback_short_circuits_without_grading(self):
        # The gate-certificate seam: a task `skip` answers for is NEVER
        # graded, its message rides the per-task line, and on_pass fires only
        # for FRESH passes.
        from aura_rig.cb import _run_refgates
        graded, passed, lines = [], [], []

        def _grade(tid):
            graded.append(tid)
            return 0, "overall : PASS"

        out = _run_refgates(
            ["a", "b", "c"], _grade, say=lines.append,
            skip=lambda tid: "already certified — skipping" if tid == "b" else None,
            on_pass=passed.append)
        self.assertIsNone(out)
        self.assertEqual(graded, ["a", "c"])
        self.assertEqual(passed, ["a", "c"])
        self.assertTrue(any("b: already certified — skipping" in ln
                            for ln in lines))

    def test_gate_runs_once_per_distinct_task_all_pass(self):
        from aura_rig.cb import _run_refgates
        graded = []

        def _grade(tid):
            graded.append(tid)
            return 0, "overall : PASS"

        out = _run_refgates(["glide-bp", "glide-cpp", "poison-bp"],
                            _grade, say=lambda s: None)
        self.assertIsNone(out)
        self.assertEqual(graded, ["glide-bp", "glide-cpp", "poison-bp"])

    def test_first_fail_stops_and_carries_verdict_evidence(self):
        from aura_rig.cb import _run_refgates
        graded = []

        def _grade(tid):
            graded.append(tid)
            if tid == "poison-bp":
                return 1, ("L1 ... ok\n"
                           "verdict-evidence: L2I check stack_count FAILED\n"
                           "verdict-evidence: expected 3, got 0\n"
                           "overall : FAIL\n")
            return 0, "overall : PASS"

        out = _run_refgates(["glide-bp", "poison-bp", "poison-cpp"],
                            _grade, say=lambda s: None)
        self.assertIsNotNone(out)
        tid, rc, evidence = out
        self.assertEqual((tid, rc), ("poison-bp", 1))
        self.assertEqual(evidence,
                         ["verdict-evidence: L2I check stack_count FAILED",
                          "verdict-evidence: expected 3, got 0"])
        # fail-verbatim-and-STOP: poison-cpp was never graded.
        self.assertEqual(graded, ["glide-bp", "poison-bp"])

    def test_fail_without_evidence_lines_falls_back_to_tail(self):
        from aura_rig.cb import _run_refgates
        out = _run_refgates(
            ["a", "b"],
            lambda tid: (7, "\n".join(f"line{i}" for i in range(12))),
            say=lambda s: None)
        tid, rc, evidence = out
        self.assertEqual((tid, rc), ("a", 7))
        self.assertEqual(evidence, [f"line{i}" for i in range(4, 12)])

    def test_runner_crash_is_a_gate_fail_not_an_exception(self):
        from aura_rig.cb import _run_refgates

        def _boom(tid):
            raise RuntimeError("editor gone")

        tid, rc, evidence = _run_refgates(["a"], _boom, say=lambda s: None)
        self.assertEqual(tid, "a")
        self.assertIsNone(rc)
        self.assertTrue(any("editor gone" in ln for ln in evidence))

    def test_refgate_exit_code_is_distinct_from_both_domains(self):
        # cb's own 0/1/2 AND run_task.py's 0-8 verdict taxonomy.
        from aura_rig.cb import EXIT_BENCH_REFGATE_FAIL
        self.assertNotIn(EXIT_BENCH_REFGATE_FAIL, set(range(0, 9)))


class _RefgateChild:
    """Stands in for the refgate's run_task.py subprocess: records each cmd and
    answers with a canned (returncode, stdout). No real grades, no UE."""

    def __init__(self, returncode=0, stdout="overall : PASS"):
        self.returncode, self.stdout = returncode, stdout
        self.cmds = []

    def __call__(self, cmd, **kw):
        self.cmds.append([str(c) for c in cmd])
        return types.SimpleNamespace(returncode=self.returncode,
                                     stdout=self.stdout, stderr="")

    def gated_tasks(self):
        """The task ids the fake run_task.py was pointed at, in call order."""
        out = []
        for cmd in self.cmds:
            spec = Path(cmd[cmd.index("--task") + 1])
            out.append(spec.parent.name)      # tasks/<set>/<id>/task.md
        return out


def _fake_git_clean(args, repo):
    """Canned refgate git runner: committed, clean tree, stable shas — the
    state in which gate certificates CAN be written."""
    if args[:2] == ["rev-parse", "HEAD"]:
        return 0, "deadbeefcafe0123"
    if args and args[0] == "rev-parse":
        return 0, "sha:" + args[1]
    if args and args[0] == "status":
        return 0, ""
    return 1, ""


class TestCmdBenchMultiTaskWiring(unittest.TestCase):
    """cmd_bench-level integration of the multi-task machinery: parse-time
    resolution, cell refusal, cost preview, opt-in reference gates (injected
    child — no real grades; injected git — no real repo), phase grouping, and
    the distinct abort code. No UE, no stack, no tokens."""

    def setUp(self):
        import aura_rig.envgate as _envgate
        import aura_rig.refgate as _refgate
        self.repo = Path(tempfile.mkdtemp())
        for tid, fm in (
                ("t-a", "---\nid: t-a\nlayers: [L1]\n---\n\n# t-a\n"),
                ("t-b", "---\nid: t-b\nlayers: [L1]\n---\n\n# t-b\n"),
                ("t-asset", "---\nid: t-asset\nlayers: [L1, L2I]\n"
                            "introspect: [x.py]\n---\n\n# t-asset\n")):
            d = self.repo / "tasks" / "setA" / tid
            (d / "reference").mkdir(parents=True)
            (d / "task.md").write_text(fm, encoding="utf-8")
            (d / "reference" / "stub.txt").write_text("x", encoding="utf-8")
        gate = mock.patch.object(_envgate, "enforce", lambda *a, **k: True)
        gate.start()
        self.addCleanup(gate.stop)
        git = mock.patch.object(_refgate, "_run_git", _fake_git_clean)
        git.start()
        self.addCleanup(git.stop)
        # The refgate certificate key includes the ENGINE BUILD as of
        # 2026-08-14, so a UE root with no Engine/Build/Build.version
        # yields key=None (re-gate) and no certificate is ever honoured.
        _bd = self.repo / "Engine" / "Build"
        _bd.mkdir(parents=True, exist_ok=True)
        (_bd / "Build.version").write_text(
            '{"MajorVersion":5,"MinorVersion":8,"PatchVersion":0,'
            '"Changelist":55116800}', encoding="utf-8")
        env = mock.patch.dict(os.environ, {"CB_UE_ROOT": str(self.repo)})
        env.start()
        self.addCleanup(env.stop)

    def _ctx(self):
        return types.SimpleNamespace(
            ue=Path("UnrealEditor"), py_exe="py", py_pre=[],
            paths=types.SimpleNamespace(craftbench=self.repo,
                                        uproject=self.repo / "X.uproject"))

    @staticmethod
    def _args(**kw):
        base = dict(model="claude-p:sonnet", task="setA/t-a,setA/t-b",
                    repeat=1, ceiling=900, resume=None, wizard=False,
                    no_preflight=True, preview=False, prune_workdirs=False)
        base.update(kw)
        return types.SimpleNamespace(**base)

    def _bench(self, args, child=None):
        from aura_rig import cb as _cb
        child = child or _RefgateChild()
        said, runs = [], []

        def fake_run(models, task_specs, *a, **kw):
            runs.append((list(models), list(task_specs),
                         kw.get("model_groups")))
            said.append("<<REPS START>>")
            return bch.aggregate([], models, task_specs)

        with mock.patch.object(bch, "run", fake_run), \
             mock.patch.object(_cb.subprocess, "run", child), \
             mock.patch.object(_cb.stack, "stop_stack", lambda **k: None), \
             mock.patch.object(_cb, "_say", said.append):
            rc = _cb.cmd_bench(self._ctx(), args)
        return rc, "\n".join(said), runs, child

    def test_multi_task_typo_dies_at_parse_time_before_any_gate_or_spend(self):
        # refgates=True so "no refgate ran" below stays a REAL assertion (a
        # default bench would trivially run none).
        rc, text, runs, child = self._bench(
            self._args(task="setA/t-a,setA/nope", refgates=True))
        self.assertEqual(rc, 2)
        self.assertIn("task not found", text)
        self.assertEqual(runs, [], "no rep may run after a resolution FAIL")
        self.assertEqual(child.cmds, [], "no refgate may run either")

    def test_default_runs_no_gates_at_all(self):
        # The 2026-08-06 owner decision: a multi-task bench spends NOTHING on
        # reference gates unless --refgates is passed.
        rc, text, runs, child = self._bench(self._args())
        self.assertEqual(rc, 0)
        self.assertEqual(child.cmds, [], "no gate may run without --refgates")
        self.assertNotIn("REFGATES", text)
        self.assertEqual(len(runs), 1)

    def test_refgates_opt_in_grades_each_distinct_task_before_the_reps(self):
        rc, text, runs, child = self._bench(
            self._args(task="setA/t-a,setA/t-b:2", refgates=True))
        self.assertEqual(rc, 0)
        self.assertEqual(child.gated_tasks(), ["t-a", "t-b"],
                         "one token-free reference grade per DISTINCT task")
        self.assertEqual(len(runs), 1)
        self.assertLess(text.index("REFGATES"), text.index("<<REPS START>>"),
                        "all gates run upfront, before any spend")
        self.assertIn("COST PREVIEW", text)
        self.assertLess(text.index("COST PREVIEW"), text.index("REFGATES"))

    def test_gate_fail_aborts_with_the_distinct_code_and_evidence(self):
        from aura_rig.cb import EXIT_BENCH_REFGATE_FAIL
        child = _RefgateChild(returncode=1, stdout=(
            "L1 ok\nverdict-evidence: L2 assert glide FAILED\noverall : FAIL"))
        rc, text, runs, child = self._bench(self._args(refgates=True),
                                            child=child)
        self.assertEqual(rc, EXIT_BENCH_REFGATE_FAIL)
        self.assertIn("verdict-evidence: L2 assert glide FAILED", text)
        self.assertIn("harness/machine problem", text)
        self.assertEqual(runs, [], "a failed gate must stop the whole matrix "
                                   "before a single token is spent")
        self.assertEqual(child.gated_tasks(), ["t-a"],
                         "fail-and-STOP: the second task is never graded")

    def test_skip_refgates_is_a_deprecated_noop(self):
        # Operator muscle-memory and existing scripts must keep parsing it;
        # the flag changes NOTHING (there is no default gate left to skip)
        # and says so once.
        rc, text, runs, child = self._bench(self._args(skip_refgates=True))
        self.assertEqual(rc, 0)
        self.assertEqual(child.cmds, [])
        self.assertEqual(len(runs), 1)
        self.assertIn("--skip-refgates", text)
        self.assertIn("DEPRECATED", text)

    def test_refgates_honor_an_existing_certificate(self):
        # First opt-in bench grades + certifies both tasks; the second
        # self-skips them off the stored certs (same repo, same fake git).
        rc1, text1, _runs1, child1 = self._bench(self._args(refgates=True))
        self.assertEqual(rc1, 0)
        self.assertEqual(child1.gated_tasks(), ["t-a", "t-b"])
        rc2, text2, runs2, child2 = self._bench(self._args(refgates=True))
        self.assertEqual(rc2, 0)
        self.assertEqual(child2.cmds, [], "certified tasks must not regrade")
        self.assertIn("already certified", text2)
        self.assertEqual(len(runs2), 1, "the bench itself still runs")

    def test_single_task_default_runs_no_gate(self):
        rc, text, runs, child = self._bench(self._args(task="setA/t-a"))
        self.assertEqual(rc, 0)
        self.assertEqual(child.cmds, [], "single-task default: no gate")
        self.assertNotIn("REFGATES", text)
        self.assertEqual(len(runs), 1)

    def test_single_task_with_explicit_flag_gates(self):
        # The old multi-task-only asymmetry is gone: an EXPLICIT --refgates
        # is honored on any task count.
        rc, text, runs, child = self._bench(
            self._args(task="setA/t-a", refgates=True))
        self.assertEqual(rc, 0)
        self.assertEqual(child.gated_tasks(), ["t-a"])
        self.assertIn("REFGATES", text)
        self.assertEqual(len(runs), 1)

    def test_baseline_on_asset_task_is_refused_at_parse_time(self):
        rc, text, runs, child = self._bench(self._args(task="setA/t-asset"))
        self.assertEqual(rc, 2)
        self.assertIn("--run-mismatched-cells", text)
        self.assertIn("claude-p:sonnet  x  setA/t-asset", text)
        self.assertEqual(runs, [])

    def test_allow_mismatched_cells_runs_them_with_a_warning(self):
        rc, text, runs, child = self._bench(
            self._args(task="setA/t-asset", allow_mismatched_cells=True))
        self.assertEqual(rc, 0)
        self.assertIn("WARN  --run-mismatched-cells", text)
        self.assertEqual(len(runs), 1)

    # test_product_model_on_asset_task_is_not_refused stood here until
    # the public release: it drove the aura-product phase of `cb bench`,
    # a lane this release does not ship.

    # test_mixed_backends_run_as_baseline_then_product_phases stood here until
    # the public release: it drove the aura-product phase of `cb bench`,
    # a lane this release does not ship.

    def test_cost_preview_names_cells_anchors_and_ceiling(self):
        rc, text, runs, child = self._bench(
            self._args(task="setA/t-a,setA/t-b", ceiling=1200))
        self.assertEqual(rc, 0)
        self.assertIn("1 model(s) x 2 task(s) = 2 cell(s)", text)
        self.assertIn("agent ceiling 1200s/rep", text)
        self.assertIn("~$1.50/rep", text)      # claude-p:sonnet anchors as sonnet

    def test_per_rep_summary_card_prints_after_a_baseline_rep(self):
        """Every bench rep ends with the repcard summary box (the evolved
        _recap_run_summary) — injected end to end: a fake run.py child writes
        the rep's result.json, the fake bench.run drives ONE real runner
        call, no UE, no color (CB_NO_COLOR pins determinism vs the test
        console)."""
        from aura_rig import cb as _cb
        said = []

        class _Child:
            def __call__(self, cmd, **kw):
                cmd = [str(c) for c in cmd]
                rd = Path(cmd[cmd.index("--run-dir") + 1]) / "r1"
                rd.mkdir(parents=True, exist_ok=True)
                (rd / "result.json").write_text(json.dumps({
                    "overall": "PASS", "task": "setA/t-a",
                    "agent": {"cost_usd": 0.5, "duration_s": 60},
                    "timings": {"agent_s": 60, "verify_s": 120},
                    "verifier": {"layers": {
                        "L1": {"status": "pass", "duration_seconds": 100.0},
                        "L2": {"status": "pass", "tests_run": 1,
                               "tests_passed": 1, "duration_seconds": 30.0},
                    }},
                }), encoding="utf-8")
                return types.SimpleNamespace(returncode=0, stdout="",
                                             stderr="")

        def fake_run(models, task_specs, run_one_rep, out_dir, **kw):
            res = run_one_rep(bch.Rep(models[0], task_specs[0][0], 1, 1))
            return bch.aggregate([res], models, task_specs)

        with mock.patch.object(bch, "run", fake_run), \
             mock.patch.object(_cb.subprocess, "run", _Child()), \
             mock.patch.dict(os.environ, {"CB_NO_COLOR": "1"}), \
             mock.patch.object(_cb, "_say", said.append):
            rc = _cb.cmd_bench(self._ctx(), self._args(task="setA/t-a"))
        text = "\n".join(said)
        self.assertEqual(rc, 0)
        self.assertIn("┌─", text)                  # the card box rendered
        self.assertIn("run summary", text)
        self.assertIn("L1 pass 100s", text)
        self.assertIn("L2 pass 1/1 30s", text)
        self.assertIn("verify 120s", text)
        self.assertIn("$0.5000", text)


if __name__ == "__main__":
    unittest.main()
