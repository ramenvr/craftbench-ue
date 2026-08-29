"""Unit tests for aura_rig.proxy — pure SSE/JSON parsing + aggregation readers.

Fully offline: no socket, no network. We feed canned Anthropic response bytes
into the pure parsers and canned JSONL into the aggregators.
"""

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import proxy  # noqa: E402


def _sse(*events: dict) -> bytes:
    return b"\n".join(b"data: " + json.dumps(e).encode() for e in events) + b"\n"


_MESSAGE_SSE = _sse(
    {"type": "message_start", "message": {"model": "claude-sonnet-4-6",
                                          "usage": {"input_tokens": 120,
                                                    "cache_read_input_tokens": 30,
                                                    "cache_creation_input_tokens": 10}}},
    {"type": "content_block_start", "index": 0, "content_block": {"type": "text"}},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hello "}},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "world"}},
    {"type": "content_block_start", "index": 1,
     "content_block": {"type": "tool_use", "name": "edit_cpp_file"}},
    {"type": "content_block_delta", "index": 1,
     "delta": {"type": "input_json_delta", "partial_json": '{"path":"X.cpp"}'}},
    {"type": "message_delta", "delta": {"stop_reason": "tool_use"},
     "usage": {"output_tokens": 88}},
)


class TestSSEParse(unittest.TestCase):
    def test_usage_and_content(self):
        rec = proxy.parse_sse_response(_MESSAGE_SSE)
        self.assertEqual(rec["model"], "claude-sonnet-4-6")
        self.assertEqual(rec["input_tokens"], 120)
        self.assertEqual(rec["output_tokens"], 88)
        self.assertEqual(rec["cache_read"], 30)
        self.assertEqual(rec["cache_write"], 10)
        self.assertEqual(rec["text"], "Hello world")
        self.assertEqual(rec["stop_reason"], "tool_use")
        self.assertEqual(len(rec["tool_uses"]), 1)
        self.assertEqual(rec["tool_uses"][0]["name"], "edit_cpp_file")

    def test_garbage_lines_tolerated(self):
        rec = proxy.parse_sse_response(b"data: not json\nplain line\ndata: [DONE]\n")
        self.assertEqual(rec["input_tokens"], 0)
        self.assertEqual(rec["model"], None)


class TestJSONParse(unittest.TestCase):
    def test_non_streamed(self):
        body = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "usage": {"input_tokens": 10, "output_tokens": 5,
                      "cache_read_input_tokens": 1, "cache_creation_input_tokens": 2},
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "hi"},
                        {"type": "tool_use", "name": "foo", "input": {"a": 1}}],
        }).encode()
        rec = proxy.parse_json_response(body)
        self.assertEqual(rec["model"], "claude-haiku-4-5-20251001")
        self.assertEqual(rec["output_tokens"], 5)
        self.assertEqual(rec["text"], "hi")
        self.assertEqual(rec["tool_uses"][0]["name"], "foo")

    def test_empty_body(self):
        rec = proxy.parse_json_response(b"")
        self.assertEqual(rec["input_tokens"], 0)


class TestBuildRecords(unittest.TestCase):
    def test_usage_record_shape(self):
        parsed = proxy.parse_sse_response(_MESSAGE_SSE)
        rec = proxy.build_usage_record(parsed, "/v1/messages", 200, True, ts=1.0)
        self.assertEqual(rec["ts"], 1.0)
        self.assertEqual(rec["path"], "/v1/messages")
        self.assertEqual(rec["status"], 200)
        self.assertTrue(rec["stream"])
        self.assertEqual(rec["model"], "claude-sonnet-4-6")

    def test_trace_record_extracts_request_context(self):
        parsed = proxy.parse_sse_response(_MESSAGE_SSE)
        req = json.dumps({
            "model": "sonnet-4.6",
            "system": "You are a python_agent sub-agent.",
            "messages": [{"role": "user", "content": "do the thing"}],
            "tools": [{"name": "a"}, {"name": "b"}],
        }).encode()
        tr = proxy.build_trace_record(parsed, req, ts=2.0)
        self.assertEqual(tr["ts"], 2.0)
        self.assertIn("python_agent", tr["system_preview"])
        self.assertEqual(tr["n_messages"], 1)
        self.assertEqual(tr["tools_offered"], 2)
        self.assertIn("do the thing", tr["last_user_preview"])
        self.assertEqual(tr["model"], "claude-sonnet-4-6")  # observed wins over req


class TestAggregators(unittest.TestCase):
    def test_usage_since_aggregates_and_flags_mismatch(self):
        with TemporaryDirectory() as td:
            log = Path(td) / "usage.jsonl"
            recs = [
                {"model": "claude-sonnet-4-6", "input_tokens": 100, "output_tokens": 10,
                 "cache_read": 5, "cache_write": 1},
                {"model": "claude-sonnet-4-6", "input_tokens": 50, "output_tokens": 20,
                 "cache_read": 0, "cache_write": 0},
            ]
            log.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
            agg = proxy.usage_since(0, "sonnet-4.6", usage_log=log)
            self.assertEqual(agg["requests"], 2)
            self.assertEqual(agg["input_tokens"], 150)
            self.assertEqual(agg["output_tokens"], 30)
            self.assertEqual(agg["models"], {"claude-sonnet-4-6": 2})
            self.assertIsNone(agg["wire_model_mismatch"])

    def test_usage_since_n_before_offset(self):
        with TemporaryDirectory() as td:
            log = Path(td) / "usage.jsonl"
            log.write_text(
                json.dumps({"model": "claude-sonnet-4-6", "input_tokens": 999}) + "\n"
                + json.dumps({"model": "claude-sonnet-4-6", "input_tokens": 7}) + "\n")
            agg = proxy.usage_since(1, "sonnet-4.6", usage_log=log)
            self.assertEqual(agg["input_tokens"], 7)  # first line skipped

    def test_subagent_trace_isolates_non_main_model(self):
        with TemporaryDirectory() as td:
            log = Path(td) / "trace.jsonl"
            recs = [
                # MAIN loop (matches expected wire) — excluded.
                {"model": "claude-sonnet-4-6", "system_preview": "main",
                 "tool_uses": [{"name": "edit_cpp_file"}]},
                # A sub-agent on a different model — included.
                {"model": "claude-opus-4-7", "system_preview": "python_agent here",
                 "tool_uses": [{"name": "execute_unreal_python"}]},
                {"model": "claude-opus-4-7", "system_preview": "python_agent here",
                 "tool_uses": []},
            ]
            log.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
            sub, by_sig = proxy.subagent_trace_since(0, "sonnet-4.6", trace_log=log)
            self.assertEqual(len(sub), 2)
            self.assertEqual(sum(by_sig.values()), 2)

    def test_line_count(self):
        with TemporaryDirectory() as td:
            log = Path(td) / "x.jsonl"
            self.assertEqual(proxy.line_count(log), 0)
            log.write_text("a\nb\nc\n")
            self.assertEqual(proxy.line_count(log), 3)


class TestHealthz(unittest.TestCase):
    def test_healthz_ok(self):
        def opener(url, timeout):
            return 200, '{"proxy":"ok"}'
        self.assertTrue(proxy.healthz(opener=opener))

    def test_healthz_bad_body(self):
        self.assertFalse(proxy.healthz(opener=lambda u, t: (200, "nope")))

    def test_healthz_exception(self):
        def boom(url, timeout):
            raise OSError("down")
        self.assertFalse(proxy.healthz(opener=boom))


if __name__ == "__main__":
    unittest.main()
