"""Reasoning must reach the rollup without an absence rendering as a zero.

One test per reading that a plain average or a bare integer gets wrong: a cell nobody
measured is not a cell that did not reason, a cell that reported zero is not
unmeasured, a share whose denominator includes unmeasured cells is not that model's
share, and two policies under one model name are an alarm rather than a number.
"""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sweep_report  # noqa: E402


def _cell(lane_dir: Path, run: str, task: str, model: str, agent: dict) -> None:
    d = lane_dir / run
    d.mkdir(parents=True)
    a = {"duration_s": 100.0, "cost_usd": 1.0, "num_turns": 1,
         "tool_use_count": 1, "mcp_tool_use_count": 1}
    a.update(agent)
    (d / "result.json").write_text(json.dumps(
        {"overall": "PASS", "task": f"tasks/bp/{task}/task.md",
         "model": f"{lane_dir.name}:{model}", "agent": a}), encoding="utf-8")


def _report(lane_dir_name="unreal-mcp", **cells) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        lane = Path(tmp) / lane_dir_name
        for run, (task, model, agent) in sorted(cells.items()):
            _cell(lane, run, task, model, agent)
        out = io.StringIO()
        with redirect_stdout(out):
            sweep_report.main([tmp, "--lanes", lane_dir_name])
    return out.getvalue()


def _rsn_rows(text: str) -> list:
    body = text.split("REASONING BY MODEL", 1)[1].split("=" * 78, 1)[0]
    return [ln for ln in body.splitlines() if "gemini" in ln or "deepseek" in ln]


class TestUnmeasuredIsNotZero(unittest.TestCase):
    def test_a_cell_with_no_reported_count_renders_the_marker_not_a_zero(self):
        text = _report(a=("t1-a", "google/gemini-3.7-flash",
                          {"tokens_out": 5000, "reasoning_policy": "provider-default"}))
        rows = _rsn_rows(text)
        self.assertEqual(len(rows), 1, text)
        self.assertIn("provider-default", rows[0])
        self.assertIn("0/1", rows[0])
        self.assertEqual(rows[0].count("unmeasured"), 3, rows[0])
        # The one rendering this column exists to prevent.
        self.assertNotIn("0.0%", rows[0])

    def test_a_reported_zero_still_reads_as_a_measured_zero(self):
        text = _report(a=("t1-a", "google/gemini-3.7-flash",
                          {"tokens_out": 5000, "reasoning_tokens": 0}))
        row = _rsn_rows(text)[0]
        self.assertIn("1/1", row)
        self.assertIn("0.0%", row)
        self.assertNotIn("unmeasured", row)
        self.assertIn("unrecorded", row)  # no policy on the record

    def test_the_records_own_measurement_state_beats_a_placeholder_count(self):
        # ``reasoning_measurement`` is the writer's discriminator (adapters/base.py),
        # so a record declaring itself unmeasured stays unmeasured -- a placeholder 0
        # beside it is the exact "did not reason" misread the column prevents.
        text = _report(a=("t1-a", "google/gemini-3.7-flash",
                          {"tokens_out": 5000, "reasoning_tokens": 0,
                           "reasoning_measurement": "unmeasured"}))
        row = _rsn_rows(text)[0]
        self.assertIn("0/1", row)
        self.assertIn("unmeasured", row)
        self.assertNotIn("0.0%", row)


class TestShareDenominator(unittest.TestCase):
    def test_unmeasured_cells_do_not_dilute_the_share(self):
        text = _report(
            a=("t1-a", "deepseek/deepseek-v4-pro-0813",
               {"tokens_out": 1000, "reasoning_tokens": 800}),
            b=("t1-b", "deepseek/deepseek-v4-pro-0813", {"tokens_out": 9000}))
        row = _rsn_rows(text)[0]
        self.assertIn("1/2", row)
        self.assertIn("80.0%", row)
        self.assertNotIn("8.0%", row)

    def test_a_count_with_no_output_tokens_reports_the_count_not_a_share(self):
        # The proxy has logged output_tokens=0 against a real ledger completion, so
        # the share can genuinely have no denominator -- and the aggregator must not
        # divide by it.
        text = _report(a=("t1-a", "deepseek/deepseek-v4-pro-0813",
                          {"reasoning_tokens": 100}))
        row = _rsn_rows(text)[0]
        self.assertIn("100", row)
        self.assertIn("no out tok", row)


class TestMixedPolicyIsAnAlarm(unittest.TestCase):
    def test_two_policies_under_one_model_split_the_row_and_raise_the_flag(self):
        text = _report(
            a=("t1-a", "deepseek/deepseek-v4-pro-0813",
               {"tokens_out": 1000, "reasoning_tokens": 800,
                "reasoning_policy": "provider-default"}),
            b=("t1-b", "deepseek/deepseek-v4-pro-0813",
               {"tokens_out": 1000, "reasoning_tokens": 0,
                "reasoning_policy": "thinking-disabled"}))
        rows = _rsn_rows(text)
        self.assertEqual(len(rows), 3, text)   # two policy rows + the alarm line
        self.assertTrue(all(r.startswith("! ") for r in rows[:2]), rows)
        self.assertIn("80.0%", rows[0])        # provider-default, not averaged to 40%
        self.assertIn("0.0%", rows[1])
        self.assertIn("MIXED POLICY, NOT COMPARABLE", rows[2])
        self.assertIn("provider-default, thinking-disabled", rows[2])
        self.assertNotIn("40.0%", text)


if __name__ == "__main__":
    unittest.main()


class TestTheShareIsComputedOverPairedCellsOnly(unittest.TestCase):
    def test_a_measured_cell_with_no_output_tokens_cannot_inflate_the_share(self):
        """Summing every measured reasoning count over only the cells that
        reported output tokens ratios two different populations, and the result
        can exceed 100% while the coverage column still reads as full.
        """
        text = _report(
            a=("t1-a", "deepseek/deepseek-v4-pro-0813",
               {"tokens_out": 1000, "reasoning_tokens": 800}),
            b=("t1-b", "deepseek/deepseek-v4-pro-0813",
               {"reasoning_tokens": 5000}))          # measured, no denominator
        row = next(r for r in _rsn_rows(text) if "deepseek" in r)
        self.assertIn("80.0%", row)                  # 800/1000, the paired cell
        self.assertNotIn("580.0%", row)
        # and the row must say the share does not cover every measured cell
        self.assertIn("reported no output tokens", row)


class TestAnAbsentRecordIsNotAPolicy(unittest.TestCase):
    def test_cells_predating_the_field_are_not_a_mixed_policy_alarm(self):
        """`unrecorded` is the ABSENCE of a policy. Treating it as one fires
        `MIXED POLICY, NOT COMPARABLE` on every model as soon as one new cell
        lands beside the existing corpus.
        """
        text = _report(
            a=("t1-a", "deepseek/deepseek-v4-pro-0813",
               {"tokens_out": 1000, "reasoning_tokens": 800,
                "reasoning_policy": "provider-default"}),
            b=("t1-b", "deepseek/deepseek-v4-pro-0813",
               {"tokens_out": 1000}))                # no reasoning block at all
        self.assertNotIn("MIXED POLICY", text)
        self.assertIn("POLICY UNRECORDED", text)

    def test_two_declared_policies_under_one_model_still_alarm(self):
        text = _report(
            a=("t1-a", "deepseek/deepseek-v4-pro-0813",
               {"tokens_out": 1000, "reasoning_policy": "provider-default"}),
            b=("t1-b", "deepseek/deepseek-v4-pro-0813",
               {"tokens_out": 1000, "reasoning_policy": "effort-high"}))
        self.assertIn("MIXED POLICY, NOT COMPARABLE", text)
