"""End-to-end contract test: the WRITER (run_events.FileEventSink) and the
READER (dashboard/live.py) agree on the live disk contract (spec §5.1/§5.2).

The two halves are built independently against the spec; this test drives a real
FileEventSink to lay down a run-dir, then asserts live.active_runs() /
tail_events() read back exactly what was written — proving the contract is
self-consistent, not just that each side matches its own fixtures.

Pure stdlib; no editor, Aura, network, or real clock (the sink clock is injected
and the reader's ``now`` is passed in for deterministic staleness).
"""

from __future__ import annotations

import datetime as _dt
import sys
import tempfile
import unittest
from pathlib import Path

# Writer lives in tools/run-agent/; reader lives in tools/dashboard/. Put both on
# the path (distinct module names, no collision; live.py is standalone stdlib).
_TESTS = Path(__file__).resolve()
_RUN_AGENT = _TESTS.parents[1]          # tools/run-agent
_DASHBOARD = _TESTS.parents[2] / "dashboard"  # tools/dashboard
sys.path.insert(0, str(_RUN_AGENT))
sys.path.insert(0, str(_DASHBOARD))

from run_events import FileEventSink, write_result_json  # noqa: E402
import live  # noqa: E402


# A deterministic clock for the sink: returns a fixed ISO-Z string we control.
class _Clock:
    def __init__(self, value: str):
        self.value = value

    def __call__(self) -> str:
        return self.value


def _iso(dt: _dt.datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class LiveContractIntegration(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmp.name)
        self.run_id = "20260604-120000-gp-gas-launch-aura-agent-claude-sonnet-4-6"
        self.run_dir = self.repo_root / "runs" / self.run_id
        self.run_dir.mkdir(parents=True)
        # Sink clock fixed at T0; reader 'now' a few seconds later (not stale).
        self.t0 = _dt.datetime(2026, 6, 4, 12, 0, 0, tzinfo=_dt.timezone.utc)
        self.clock = _Clock(_iso(self.t0))
        self.sink = FileEventSink(self.run_dir, now=self.clock)

    def tearDown(self):
        self._tmp.cleanup()

    def _running_status(self, **over):
        base = dict(
            run_id=self.run_id, task_id="gp-gas-launch",
            product="aura-agent:claude-sonnet-4-6", phase="running",
            step=12, max_steps=40, current_tool="generate_cpp_file",
            tool_count=28, tokens_in=41000, tokens_out=6000,
            started_at=_iso(self.t0), elapsed_s=38.2, result=None, error=None,
        )
        base.update(over)
        self.sink.write_status_full(**base)

    def test_writer_output_is_read_by_reader(self):
        # WRITE: full running status + a tool_call/tool_result/finish tape.
        self._running_status()
        self.sink.emit({"type": "tool_call", "tool": "generate_cpp_file",
                        "tool_call_id": "tc_1", "input_preview": "UCBLaunchAbility"})
        self.sink.emit({"type": "tool_result", "tool_call_id": "tc_1",
                        "ok": True, "ms": 3100, "output_preview": "wrote 2 files"})

        # READ active_runs at a time 5s later → present, not stale, fields intact.
        now = self.t0 + _dt.timedelta(seconds=5)
        rows = live.active_runs(self.repo_root, now=now, stale_after_s=30.0)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r.run_id, self.run_id)
        self.assertEqual(r.task_id, "gp-gas-launch")
        self.assertEqual(r.product, "aura-agent:claude-sonnet-4-6")
        self.assertEqual(r.phase, "running")
        self.assertEqual(r.step, 12)
        self.assertEqual(r.max_steps, 40)
        self.assertEqual(r.current_tool, "generate_cpp_file")
        self.assertEqual(r.tool_count, 28)
        self.assertEqual(r.tokens_in, 41000)
        self.assertFalse(r.stale)

        # READ tail_events from seq 0 → both events, monotonic seq, in order.
        evs = live.tail_events(self.run_dir, after_seq=0)
        self.assertEqual([e["seq"] for e in evs], [1, 2])
        self.assertEqual(evs[0]["type"], "tool_call")
        self.assertEqual(evs[0]["tool_call_id"], "tc_1")
        self.assertEqual(evs[1]["type"], "tool_result")
        # incremental tail: after seq 1 → only the second event.
        self.assertEqual([e["seq"] for e in live.tail_events(self.run_dir, after_seq=1)], [2])

    def test_stale_flag_when_heartbeat_lapses(self):
        self._running_status()
        # reader 'now' 60s later, stale_after_s=30 → running row flagged stale.
        now = self.t0 + _dt.timedelta(seconds=60)
        rows = live.active_runs(self.repo_root, now=now, stale_after_s=30.0)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].stale)

    def test_grading_then_done_leaves_active_panel(self):
        # grading is non-terminal → still active.
        self._running_status(phase="grading")
        now = self.t0 + _dt.timedelta(seconds=5)
        self.assertEqual(len(live.active_runs(self.repo_root, now=now)), 1)

        # result.json lands atomically, THEN phase flips to done (spec §5.2 order).
        write_result_json(self.run_dir, {"run_id": self.run_id, "overall": "PASS"})
        self.assertTrue((self.run_dir / "result.json").exists())
        self.sink.status(phase="done", result="PASS")
        # done is terminal → leaves the Active panel.
        self.assertEqual(live.active_runs(self.repo_root, now=now), [])

    def test_status_json_has_full_spec_5_1_shape(self):
        self._running_status()
        import json
        obj = json.loads((self.run_dir / "status.json").read_text(encoding="utf-8"))
        # every §5.1 key present (run_events.STATUS_FIELDS is the pinned set).
        from run_events import STATUS_FIELDS
        for key in STATUS_FIELDS:
            self.assertIn(key, obj, f"status.json missing §5.1 key {key!r}")
        self.assertEqual(obj["schema"], "craftbench.livestatus/v1")


if __name__ == "__main__":
    unittest.main()
