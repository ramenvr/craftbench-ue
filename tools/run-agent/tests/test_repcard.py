"""Unit tests for aura_rig.repcard — the per-rep terminal summary card.

Pure rendering over synthetic envelopes + injected checkpoint states (no UE,
no color assumptions about the test console: color is an explicit argument).
The honesty rules under test: measurements never become per-checkpoint
verdicts, the failing gate is the verifier's OWN evidence line, absent
fields are absent lines, an unmeasured reasoning count never reads as zero,
and color degrades to plain honestly.
"""
import json
import tempfile
import types
import unittest
from pathlib import Path

from aura_rig import repcard


def _st(idx, t=None, state=None):
    return types.SimpleNamespace(idx=idx, t=t, state=state)


#: What adapters.base.reasoning_policy_fields stamps on a measured lane's record.
#: The _envelope() fixture is an aura-product summary, and that lane stamps none.
_POLICY_BLOCK = {"reasoning_policy": "provider-default",
                 "reasoning_requested": None,
                 "reasoning_measurement": "unmeasured"}


def _envelope(**over):
    """A representative aura-product summary.json (the poison-FAIL shape)."""
    base = {
        "verdict": "FAIL",
        "task_id": "bp/gp-poison-dot-stack-bp",
        "model": "sonnet-5",
        "model_pinned": "Sonnet 5",
        "est_cost_usd": 2.034,
        "cost_thread": {"usd": 2.034, "input_tokens": 164664,
                        "output_tokens": 41853},
        "timings": {"drive_s": 1173.0, "aura_execution_time": 1111.0,
                    "grade_s": 285.6},
        "agent": {"tool_calls": 39, "by_tool": {"grep": 18, "edit": 8}},
        "posthog_url": "https://us.posthog.com/project/000000/llm-analytics/"
                       "traces/th-1",
        "graded_workdir": "C:/wd/abc123",
        "project": "C:/scratch/Graded",
        "verifier": {
            "layers": {
                "L1": {"status": "pass", "duration_seconds": 223.1},
                "L2": {"status": "fail", "duration_seconds": 26.7,
                       "tests_run": 1, "tests_passed": 0,
                       "notes": [
                           "map L_PoisonStack: /Game/Maps/L_PoisonStack",
                           "verdict-evidence: FinishTest TestResult=Failed. "
                           "poison did not STOP after its duration",
                           "verdict-evidence: Test Completed. Result={Fail}",
                       ]},
                "L2I": {"status": "pass", "duration_seconds": 13.6,
                        "tests_run": 4, "tests_passed": 4},
            },
        },
    }
    base.update(over)
    return base


class TestSupportsColor(unittest.TestCase):
    _TTY = types.SimpleNamespace(isatty=lambda: True)
    _PIPE = types.SimpleNamespace(isatty=lambda: False)
    _OK_ENV = {"WT_SESSION": "1"}     # known-good terminal on every OS branch

    def test_no_color_convention_disables(self):
        self.assertFalse(repcard.supports_color(
            self._TTY, {"NO_COLOR": "1", **self._OK_ENV}))
        # presence means NON-EMPTY per no-color.org — empty string is not set.
        self.assertTrue(repcard.supports_color(
            self._TTY, {"NO_COLOR": "", **self._OK_ENV}))

    def test_cb_no_color_disables(self):
        self.assertFalse(repcard.supports_color(
            self._TTY, {"CB_NO_COLOR": "1", **self._OK_ENV}))

    def test_non_tty_disables(self):
        self.assertFalse(repcard.supports_color(self._PIPE, self._OK_ENV))

    def test_tty_on_a_known_good_terminal_enables(self):
        self.assertTrue(repcard.supports_color(self._TTY, self._OK_ENV))


class TestCardRendering(unittest.TestCase):
    def _card(self, s=None, color=False, states=None, run_dir=None):
        return repcard.render_card(s or _envelope(),
                                   run_dir or Path("runs") / "x",
                                   states=states, color=color)

    def test_plain_mode_has_zero_ansi(self):
        text = "\n".join(self._card(color=False))
        self.assertNotIn("\x1b", text)

    def test_box_and_core_fields(self):
        lines = self._card()
        self.assertTrue(lines[0].startswith("┌─"))
        self.assertTrue(lines[-1].startswith("└"))
        text = "\n".join(lines)
        self.assertIn("bp/gp-poison-dot-stack-bp", text)
        self.assertIn("FAIL", text)
        self.assertIn("$2.0340", text)
        self.assertIn("164,664 in / 41,853 out tok", text)
        # 2026-08-06 measured-quantity labels, kept consistent with
        # report.html: spend is thread-billed, time is wall clock.
        self.assertIn("model spend", text)
        self.assertIn("thread-billed", text)
        self.assertIn("agent 1111s (wall 1173s)", text)
        self.assertIn("verify 286s", text)
        # (the note may wrap mid-phrase; assert wrap-safe fragments)
        self.assertIn("wall clock", text)
        self.assertIn("LLM generation time only", text)
        self.assertIn("L1 pass 223s", text)
        self.assertIn("L2 FAIL 0/1 27s", text)
        self.assertIn("L2I pass 4/4 14s", text)
        self.assertIn("posthog", text)
        self.assertIn("graded wd", text)

    def test_colored_verdicts(self):
        red = "\n".join(self._card(color=True))
        self.assertIn("\x1b[1m\x1b[31mFAIL\x1b[0m", red)
        green = "\n".join(self._card(_envelope(verdict="PASS"), color=True))
        self.assertIn("\x1b[1m\x1b[32mPASS\x1b[0m", green)
        # non-graded codes are yellow — never red (aborted != failed).
        y = "\n".join(self._card(_envelope(verdict="SANDBOX-REJECT"),
                                 color=True))
        self.assertIn("\x1b[1m\x1b[33mSANDBOX-REJECT\x1b[0m", y)

    def test_gate_line_carries_the_verifier_evidence_verbatim(self):
        text = "\n".join(self._card())
        self.assertIn("L2 gate", text)
        self.assertIn("FinishTest TestResult=Failed. poison did not STOP",
                      text)

    def test_no_gate_line_when_everything_passed(self):
        s = _envelope(verdict="PASS")
        s["verifier"]["layers"]["L2"] = {"status": "pass", "tests_run": 1,
                                         "tests_passed": 1}
        self.assertNotIn("gate", "\n".join(self._card(s)))

    def test_l2i_failing_check_note_is_the_gate_fallback(self):
        s = _envelope()
        s["verifier"]["layers"]["L2"]["status"] = "pass"
        s["verifier"]["layers"]["L2"]["notes"] = []
        s["verifier"]["layers"]["L2I"] = {
            "status": "fail",
            "notes": ["x.py:stack_count: FAIL — expected 3, got 0"]}
        text = "\n".join(self._card(s))
        self.assertIn("L2I gate", text)
        self.assertIn("stack_count: FAIL — expected 3, got 0", text)

    def test_absent_fields_are_absent_lines_never_blanks(self):
        minimal = {"verdict": "PASS", "task_id": "t0"}
        lines = self._card(minimal)
        text = "\n".join(lines)
        for absent in ("model spend", "posthog", "film strip", "graded wd",
                       "project", "checkpoints", "tools", "layers", "time"):
            self.assertNotIn(absent, text)
        self.assertNotIn("None", text)
        # nothing renders as an empty value after a label
        for ln in lines[1:-1]:
            self.assertTrue(ln.rstrip() != "│", f"blank card line: {ln!r}")

    def test_unreadable_envelope_prints_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(repcard.card_for_run(Path(td)), [])


class TestReasoningRow(unittest.TestCase):
    """The reasoning row. Requested first — a run always knows what it sent, so
    that half renders unconditionally — and the provider's token count appended
    only when the record carries one. The load-bearing case is the last: an
    unmeasured run must not read as a run that reasoned zero."""

    def _row(self, s):
        """The reasoning row as one string: label line + wrapped remainder."""
        got, grabbing = [], False
        for ln in repcard.render_card(s, Path("r"), color=False)[1:-1]:
            body = ln[2:]                      # past the box gutter
            if body.startswith("reasoning "):
                grabbing = True
                got.append(body[len("reasoning"):].strip())
            elif grabbing and body.startswith(" " * (repcard._LABEL_W + 1)):
                got.append(body.strip())
            elif grabbing:
                break
        return " ".join(got)

    def test_measured_run_names_the_count_and_its_share_of_output(self):
        s = _envelope()
        # A measured count only ever reaches the record via claude_p, which stamps
        # the policy block in the same write — so this is the shape that carries both.
        s["agent"].update({"reasoning_tokens": 36412, "tokens_out": 41853,
                           **_POLICY_BLOCK})
        row = self._row(s)
        self.assertIn("requested: provider default", row)
        self.assertIn("36,412 reasoning tok", row)
        self.assertIn("87.0% of output", row)

    def test_an_envelope_with_no_reasoning_block_claims_nothing(self):
        """The aura lanes' writers stamp no reasoning block, so their records
        witness nothing about the request. Rendering the affirmative
        "no reasoning parameter sent" there would assert a fact about a request
        this envelope never saw — and the affirmative is the form that gets quoted.
        """
        for envelope in ({"verdict": "PASS", "task_id": "t0"}, _envelope()):
            row = self._row(envelope)
            self.assertIn("requested: not recorded", row)
            self.assertNotIn("provider default", row)

    def test_a_stamped_default_is_distinguishable_from_an_unstamped_record(self):
        s = _envelope()
        s["agent"].update(_POLICY_BLOCK)
        self.assertIn("requested: provider default", self._row(s))

    def test_unmeasured_must_not_read_as_zero(self):
        row = self._row(_envelope())           # no reasoning_tokens recorded
        self.assertIn("not reported", row)
        self.assertIn("not zero", row)
        # no count, no share, no "0" — an unproxied run measured nothing, and a
        # digit in this row would be a measurement it never made.
        self.assertNotRegex(row, r"\d")

    def test_reported_zero_stays_distinguishable_from_unmeasured(self):
        s = _envelope()
        s["agent"].update({"reasoning_tokens": 0, "tokens_out": 41853})
        row = self._row(s)
        self.assertIn("0 reasoning tok", row)
        self.assertIn("0.0% of output", row)
        self.assertNotIn("not reported", row)

    def test_a_recorded_policy_is_named_instead_of_the_default(self):
        s = _envelope()
        s["agent"]["reasoning_requested"] = {"effort": "high"}
        row = self._row(s)
        self.assertIn("requested: effort=high", row)
        self.assertNotIn("provider default", row)
        # top-level record, scalar shape
        self.assertIn("requested: high",
                      self._row(_envelope(reasoning_effort="high")))

    def test_share_omitted_rather_than_taken_from_the_billed_output(self):
        """cost_thread's output figure is thread-billed; the share is only ever
        reasoning over the SAME record's output count."""
        s = _envelope()
        s["agent"]["reasoning_tokens"] = 1234
        row = self._row(s)                     # agent block has no tokens_out
        self.assertIn("1,234 reasoning tok", row)
        self.assertNotIn("%", row)
        self.assertNotIn("41,853", row)

    def test_row_sits_with_attribution_above_spend(self):
        """Reasoning is a property of the configuration, not of the spend."""
        s = _envelope()
        s["agent"]["reasoning_tokens"] = 36412
        w = repcard._LABEL_W
        labels = [lab for lab in
                  (ln[2:2 + w].strip() for ln in
                   repcard.render_card(s, Path("r"), color=False)[1:-1])
                  if lab]
        self.assertLess(labels.index("model"), labels.index("reasoning"))
        self.assertLess(labels.index("reasoning"), labels.index("model spend"))


class TestCheckpointStory(unittest.TestCase):
    def _states(self):
        return {0: _st(0, 0.5, "health=100.0"), 1: _st(1, 1.6, "health=90.0"),
                2: _st(2, 3.1, "health=80.0")}

    def test_entries_are_measurements_in_the_caption_shape(self):
        entries = repcard.checkpoint_entries(self._states(), l2_passed=False)
        self.assertEqual(entries[0], "cp00 t=0.5s health=100.0")
        self.assertEqual(entries[1], "cp01 t=1.6s health=90.0")

    def test_no_per_checkpoint_verdict_is_ever_invented_on_fail(self):
        entries = repcard.checkpoint_entries(self._states(), l2_passed=False)
        joined = " ".join(entries)
        self.assertNotIn("✓", joined)
        self.assertNotIn("✗", joined)
        self.assertNotIn("FAIL", joined)

    def test_green_check_only_when_l2_passed(self):
        entries = repcard.checkpoint_entries(self._states(), l2_passed=True)
        self.assertTrue(all(e.startswith("✓ ") for e in entries))

    def test_card_renders_the_story_with_the_honesty_note(self):
        s = _envelope()
        text = "\n".join(repcard.render_card(s, Path("r"),
                                             states=self._states()))
        self.assertIn("checkpoints", text)
        self.assertIn("measured states, not verdicts", text)
        self.assertIn("cp00 t=0.5s health=100.0", text)
        p = _envelope(verdict="PASS")
        p["verifier"]["layers"]["L2"]["status"] = "pass"
        text = "\n".join(repcard.render_card(p, Path("r"),
                                             states=self._states()))
        self.assertIn("all green — L2 passed", text)
        self.assertIn("✓ cp00", text)

    def test_time_only_breadcrumb_renders_without_state(self):
        entries = repcard.checkpoint_entries({0: _st(0, 2.0)}, False)
        self.assertEqual(entries, ["cp00 t=2s"])

    def test_pack_flows_short_entries_and_isolates_long_ones(self):
        short = [f"cp{i:02d} t={i}s" for i in range(4)]
        packed = repcard._pack(short, 40)
        self.assertLess(len(packed), 4)          # short entries share lines
        self.assertTrue(all(len(ln) <= 40 for ln in packed))
        long = ["x" * 60, "y" * 60]
        self.assertEqual(repcard._pack(long, 40), long)   # never cut


class TestCardForRunEndToEnd(unittest.TestCase):
    """card_for_run over a real (temp) run dir: envelope precedence + the
    checkpoint channel resolved through the guarded `checkpoint_states`
    describer, entirely offline."""

    def test_summary_wins_and_states_come_from_the_graded_log(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            run = td / "run"
            wd = td / "wd"
            (wd / "out").mkdir(parents=True)
            run.mkdir()
            (wd / "out" / "l2_pie.log").write_text(
                "[CB-CP] idx=0 t=0.5\n"
                "LogTemp: [POISON] idx=0 t=0.50 health=100.0\n"
                "[CB-CP] idx=1 t=1.6\n"
                "LogTemp: [POISON] idx=1 t=1.60 health=90.0\n",
                encoding="utf-8")
            s = _envelope(graded_workdir=str(wd))
            (run / "summary.json").write_text(json.dumps(s), encoding="utf-8")
            # a stale result.json must NOT shadow the graded envelope
            (run / "result.json").write_text(json.dumps({"overall": "PASS"}),
                                             encoding="utf-8")
            lines = repcard.card_for_run(run, color=False)
        text = "\n".join(lines)
        self.assertIn("FAIL", text)                       # summary.json won
        self.assertIn("cp00 t=0.5s health=100.0", text)   # caption channel
        self.assertIn("cp01 t=1.6s health=90.0", text)
        self.assertNotIn("\x1b", text)

    def test_missing_workdir_means_no_checkpoint_section_not_an_error(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td) / "run"
            run.mkdir()
            s = _envelope(graded_workdir=str(Path(td) / "gone"))
            (run / "summary.json").write_text(json.dumps(s), encoding="utf-8")
            text = "\n".join(repcard.card_for_run(run, color=False))
        self.assertIn("FAIL", text)
        self.assertNotIn("checkpoints", text)


if __name__ == "__main__":
    unittest.main()
