"""Adapter base interface: AgentResult shape + Protocol conformance check
via a stub adapter that doesn't shell out to any model.
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.base import AgentAdapter, AgentResult  # noqa: E402


class StubAdapter:
    name = "stub:noop"

    def run(self, prompt_path, workspace_dir, max_turns, timeout_s):
        return AgentResult(
            exit_code=0,
            transcript="stub transcript",
            summary="stub did nothing",
            tool_use_count=0,
            duration_s=0.0,
        )


class TestAgentResultShape(unittest.TestCase):
    def test_to_json_round_trip(self):
        r = AgentResult(
            exit_code=0, transcript="t", summary="s",
            tool_use_count=3, duration_s=1.5,
        )
        d = json.loads(r.to_json())
        self.assertEqual(d["exit_code"], 0)
        self.assertEqual(d["transcript"], "t")
        self.assertEqual(d["summary"], "s")
        self.assertEqual(d["tool_use_count"], 3)
        self.assertEqual(d["duration_s"], 1.5)

    def test_optional_fields_default_to_none(self):
        r = AgentResult(exit_code=0, transcript="", summary=None,
                        tool_use_count=None, duration_s=0.0)
        d = json.loads(r.to_json())
        self.assertIsNone(d["summary"])
        self.assertIsNone(d["tool_use_count"])


class TestAdapterProtocol(unittest.TestCase):
    def test_stub_satisfies_protocol(self):
        adapter: AgentAdapter = StubAdapter()
        result = adapter.run(Path("/tmp/p"), Path("/tmp/ws"), 10, 60)
        self.assertIsInstance(result, AgentResult)
        self.assertEqual(adapter.name, "stub:noop")


if __name__ == "__main__":
    unittest.main()
