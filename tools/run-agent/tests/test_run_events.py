"""Unit tests for run_events — the EventSink disk-contract layer (spec §5.1/§5.2/§7).

Pure stdlib; no editor, no Aura, no network. The clock is injected (a stub `now`
callable) so timestamps are deterministic and no real wall-clock is needed.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run_events import (  # noqa: E402
    EventSink,
    FileEventSink,
    NullEventSink,
    write_result_json,
)


# Deterministic, monotonically-advancing clock for tests.
class _StubClock:
    def __init__(self, start: int = 0):
        self._t = start

    def __call__(self) -> str:
        self._t += 1
        return f"2026-06-04T00:00:{self._t:02d}Z"


# The §5.1 status.json keys that the full-status helper must always write.
STATUS_KEYS = {
    "schema",
    "run_id",
    "task_id",
    "product",
    "phase",
    "step",
    "max_steps",
    "current_tool",
    "tool_count",
    "tokens_in",
    "tokens_out",
    "started_at",
    "updated_at",
    "elapsed_s",
    "result",
    "error",
}


class _TmpDirCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="run-events-test-"))

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)


class TestFileEventSinkEmit(_TmpDirCase):
    def test_events_jsonl_is_append_only_with_monotonic_seq(self):
        sink = FileEventSink(self.tmp, now=_StubClock())
        sink.emit({"type": "phase", "phase": "running"})
        sink.emit({"type": "tool_call", "tool": "generate_cpp_file"})
        sink.emit({"type": "finish", "finish_reason": "stop"})

        path = self.tmp / "events.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 3)

        seqs = []
        for line in lines:
            rec = json.loads(line)  # valid JSON per line
            self.assertIn("seq", rec)
            self.assertIn("ts", rec)
            seqs.append(rec["seq"])
        self.assertEqual(seqs, [1, 2, 3])  # monotonic, starting at 1

    def test_emit_preserves_event_fields(self):
        sink = FileEventSink(self.tmp, now=_StubClock())
        sink.emit({"type": "tool_call", "tool": "generate_cpp_file", "tool_call_id": "tc_1"})
        rec = json.loads((self.tmp / "events.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(rec["type"], "tool_call")
        self.assertEqual(rec["tool"], "generate_cpp_file")
        self.assertEqual(rec["tool_call_id"], "tc_1")

    def test_emit_uses_injected_clock_for_ts(self):
        sink = FileEventSink(self.tmp, now=_StubClock())
        sink.emit({"type": "phase", "phase": "running"})
        sink.emit({"type": "finish"})
        ts = [json.loads(l)["ts"] for l in (self.tmp / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(ts, ["2026-06-04T00:00:01Z", "2026-06-04T00:00:02Z"])

    def test_emit_does_not_overwrite_caller_seq(self):
        # The sink owns seq; a caller-supplied seq must not survive.
        sink = FileEventSink(self.tmp, now=_StubClock())
        sink.emit({"type": "phase", "seq": 999})
        rec = json.loads((self.tmp / "events.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(rec["seq"], 1)

    def test_seq_continues_within_one_sink_instance(self):
        sink = FileEventSink(self.tmp, now=_StubClock())
        for _ in range(5):
            sink.emit({"type": "tool_call"})
        seqs = [json.loads(l)["seq"] for l in (self.tmp / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(seqs, [1, 2, 3, 4, 5])


class TestFileEventSinkStatus(_TmpDirCase):
    def test_status_is_valid_json_after_every_update(self):
        sink = FileEventSink(self.tmp, now=_StubClock())
        path = self.tmp / "status.json"

        sink.status(phase="queued")
        json.loads(path.read_text(encoding="utf-8"))  # parses

        sink.status(phase="running", step=1)
        json.loads(path.read_text(encoding="utf-8"))

        sink.status(phase="running", step=2, current_tool="generate_cpp_file")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["phase"], "running")
        self.assertEqual(data["step"], 2)
        self.assertEqual(data["current_tool"], "generate_cpp_file")

    def test_status_merges_fields_into_current_state(self):
        sink = FileEventSink(self.tmp, now=_StubClock())
        sink.status(phase="running", step=1, tool_count=3)
        sink.status(step=2)  # only step changes; phase/tool_count persist
        data = json.loads((self.tmp / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(data["phase"], "running")
        self.assertEqual(data["step"], 2)
        self.assertEqual(data["tool_count"], 3)

    def test_status_always_bumps_updated_at(self):
        sink = FileEventSink(self.tmp, now=_StubClock())
        sink.status(phase="running")
        first = json.loads((self.tmp / "status.json").read_text(encoding="utf-8"))["updated_at"]
        sink.status(step=1)
        second = json.loads((self.tmp / "status.json").read_text(encoding="utf-8"))["updated_at"]
        self.assertNotEqual(first, second)

    def test_write_status_full_contains_section_5_1_keys(self):
        sink = FileEventSink(self.tmp, now=_StubClock())
        sink.write_status_full(
            run_id="20260604-000000-gp-gas-launch-aura-agent",
            task_id="gp-gas-launch",
            product="aura-agent:claude-sonnet-4-6",
            phase="running",
            step=12,
            max_steps=40,
            current_tool="generate_cpp_file",
            tool_count=28,
            tokens_in=41000,
            tokens_out=6000,
            started_at="2026-06-04T00:00:00Z",
            elapsed_s=38.2,
            result=None,
            error=None,
        )
        data = json.loads((self.tmp / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(set(data.keys()), STATUS_KEYS)
        self.assertEqual(data["schema"], "craftbench.livestatus/v1")
        self.assertEqual(data["task_id"], "gp-gas-launch")
        self.assertEqual(data["max_steps"], 40)
        self.assertIsNone(data["result"])

    def test_status_atomic_write_leaves_no_partial_or_tmp_file(self):
        sink = FileEventSink(self.tmp, now=_StubClock())
        sink.status(phase="running")
        sink.status(step=1)
        sink.status(step=2, current_tool="x")
        # Only status.json should exist — no leftover *.tmp partial.
        names = sorted(p.name for p in self.tmp.iterdir())
        self.assertIn("status.json", names)
        self.assertFalse(
            any(n.endswith(".tmp") or ".tmp" in n for n in names),
            f"leftover tmp file in {names}",
        )
        json.loads((self.tmp / "status.json").read_text(encoding="utf-8"))  # complete + valid


class TestWriteResultJson(_TmpDirCase):
    def test_writes_valid_json_atomically(self):
        write_result_json(self.tmp, {"result": "PASS", "task_id": "gp-x"})
        data = json.loads((self.tmp / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(data["result"], "PASS")
        self.assertEqual(data["task_id"], "gp-x")

    def test_leaves_no_partial_or_tmp_file(self):
        write_result_json(self.tmp, {"result": "FAIL"})
        names = sorted(p.name for p in self.tmp.iterdir())
        self.assertEqual(names, ["result.json"])

    def test_overwrites_existing_atomically(self):
        write_result_json(self.tmp, {"result": "FAIL"})
        write_result_json(self.tmp, {"result": "PASS"})
        data = json.loads((self.tmp / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(data["result"], "PASS")


class TestNullEventSink(_TmpDirCase):
    def test_emit_and_status_write_nothing(self):
        sink = NullEventSink()
        sink.emit({"type": "phase", "phase": "running"})
        sink.status(phase="running", step=1)
        # No files created anywhere — Null sink is a pure no-op.
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_satisfies_event_sink_protocol(self):
        self.assertIsInstance(NullEventSink(), EventSink)


class TestProtocolConformance(_TmpDirCase):
    def test_file_event_sink_satisfies_protocol(self):
        self.assertIsInstance(FileEventSink(self.tmp, now=_StubClock()), EventSink)


if __name__ == "__main__":
    unittest.main()
