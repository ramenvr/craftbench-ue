"""A void must be readable from the cell's own report, and must cost a cell.

Three properties, each of which a sweep-level ledger got wrong: a voided cell
leaves the denominator AND the paired set, and it cannot win a grid slot away
from a real attempt.
"""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import leak_audit  # noqa: E402
import sweep_report  # noqa: E402


def _cell(lane_dir: Path, run: str, task: str, model: str, overall: str,
          extra: dict = None) -> None:
    d = lane_dir / run
    d.mkdir(parents=True)
    rec = {"overall": overall, "task": f"tasks/bp/{task}/task.md",
           "model": f"{lane_dir.name}:{model}",
           "agent": {"duration_s": 100.0, "cost_usd": 1.0, "num_turns": 1,
                     "tool_use_count": 1, "mcp_tool_use_count": 1}}
    rec.update(extra or {})
    (d / "result.json").write_text(json.dumps(rec), encoding="utf-8")


def _row(**kw):
    row = {"lane": "unreal-mcp", "task": "t1-a", "model": "m1", "run": "r",
           "verdict": "FAIL", "void": None, "superseded": False}
    row.update(kw)
    return row


class TestVoidLeavesTheDenominator(unittest.TestCase):
    def test_report_excludes_voided_cells_both_key_shapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            lane = Path(tmp) / "unreal-mcp"
            _cell(lane, "20260801-000001-a", "t1-a", "m1", "PASS")
            _cell(lane, "20260801-000002-b", "t1-b", "m1", "FAIL")
            # An operator void does NOT rewrite ``overall`` -- every
            # 0xC0000142 void of 2026-08-21 still reads FAIL.
            _cell(lane, "20260801-000003-c", "t1-c", "m1", "FAIL",
                  {"void": {"reason": "0xC0000142 game-target spawn",
                            "at": "2026-08-21T10:52:00Z", "by": "operator",
                            "verdict_before": "FAIL"}})
            # The pre-2026-08-23 flat pair, which 12 records on disk carry.
            _cell(lane, "20260801-000004-d", "t1-d", "m1", "PASS",
                  {"voided_reason": "fairness breach", "voided_verdict": "PASS"})
            out = io.StringIO()
            with redirect_stdout(out):
                rc = sweep_report.main([tmp, "--lanes", "unreal-mcp"])
        self.assertEqual(rc, 0)
        text = out.getvalue()
        self.assertIn("4 cells, 2 graded", text)
        self.assertIn("PASS@budget  1/2", text)


class TestVoidLeavesThePairedSet(unittest.TestCase):
    def test_a_voided_cell_is_not_a_paired_fail(self):
        # The lane denominator and the paired set must agree: a lane reported as
        # "0 graded" cannot also contribute a FAIL to McNemar.
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "unreal-mcp", Path(tmp) / "aura-mcp"
            _cell(a, "20260801-000001-a", "t1-a", "m1", "PASS")
            _cell(b, "20260801-000002-a", "t1-a", "m1", "FAIL",
                  {"void": {"reason": "0xC0000142",
                            "at": "2026-08-21T10:52:00Z"}})
            out = io.StringIO()
            with redirect_stdout(out):
                sweep_report.main([tmp, "--lanes", "unreal-mcp,aura-mcp"])
        text = out.getvalue()
        self.assertIn("aura-mcp: 1 cells, 0 graded", text)
        self.assertIn("paired @budget: n=0", text)


class TestVoidCannotWinAGridSlot(unittest.TestCase):
    def test_newer_void_does_not_displace_an_older_graded_attempt(self):
        real = _row(run="20260801-000001-a", verdict="FAIL")
        void = _row(run="20260801-000002-b", verdict="FAIL",
                    void={"reason": "0xC0000142", "at": "2026-08-21T10:52:00Z"})
        kept = sweep_report.dedupe([real, void])
        self.assertEqual([r["run"] for r in kept], [real["run"]])


class TestLeakAuditStampsTheCell(unittest.TestCase):
    #: A real task and one of its own fixture markers, discovered together.
    #: `tasks/bp/t1-a/` does not exist and `SetCheckpointSchedule` was a
    #: BASE-class API name; since the marker set became per-task (2026-08-24)
    #: that pair voids nothing, so this suite would have gone quietly green
    #: while testing nothing. Discovery keeps it honest through the next rule
    #: change too.
    @staticmethod
    def _task_and_marker():
        repo = Path(__file__).resolve().parents[3]
        for spec in sorted(repo.glob("tasks/*/*/task.md")):
            rel = spec.relative_to(repo)
            marks = leak_audit.own_fixture_markers(Path("."), spec_path=rel)
            if marks:
                return rel.as_posix(), marks[0]
        raise AssertionError("no task yields a fixture marker")

    def _run_dir(self, tmp: str) -> Path:
        task, marker = self._task_and_marker()
        d = Path(tmp) / "20260801-000001-a"
        d.mkdir(parents=True)
        (d / "result.json").write_text(json.dumps(
            {"overall": "PASS", "task": task, "model": "aura-mcp:m1"}),
            encoding="utf-8")
        (d / "agent_transcript.jsonl").write_text(json.dumps(
            {"type": "tool_result",
             "content": "FinishTest(Failed, TEXT(" + chr(34) + marker
                        + chr(34) + "));"}) + chr(10),
            encoding="utf-8")
        return d

    def test_void_mode_writes_reason_timestamp_and_prior_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._run_dir(tmp)
            self.assertEqual(leak_audit.main([str(d), "--void"]), 1)
            rec = json.loads((d / "result.json").read_text(encoding="utf-8"))
        v = leak_audit.read_void(rec)
        self.assertIsNotNone(v)
        self.assertIn("fixture", v["reason"])
        self.assertRegex(v["at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(v["verdict_before"], "PASS")
        self.assertEqual(rec["overall"], "FAIRNESS-BREACH")

    def test_re_voiding_does_not_relabel_the_prior_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._run_dir(tmp)
            leak_audit.main([str(d), "--void"])
            first = json.loads((d / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(leak_audit.main([str(d), "--void"]), 1)
            again = json.loads((d / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(again["void"], first["void"])

    def test_reinstatement_clears_the_void(self):
        rec = {"overall": "PASS",
               "void": {"reason": "fairness breach", "at": "2026-08-21T00:00:00Z"},
               "reinstated": {"from": "FAIRNESS-BREACH", "to": "PASS",
                              "reason": "re-adjudicated"}}
        self.assertIsNone(leak_audit.read_void(rec))


if __name__ == "__main__":
    unittest.main()
