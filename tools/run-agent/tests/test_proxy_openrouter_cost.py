"""Unit tests for aura_rig.proxy's OpenRouter lane — upstream + true cost capture.

WHY THIS FILE EXISTS (2026-08-18). Routed through OpenRouter, the Claude Code
CLI's own ``total_cost_usd`` is wrong: it prices every call at Anthropic
FIRST-PARTY rates and cannot see the gateway (measured probe: 55,351 cache-create
+ 2 in + 4 out reported $0.20763225 == 55351 * $3.75/1M exactly). OpenRouter
returns the true number on the response; the proxy is the only seam that sees it.

Fully offline: no socket, no network, no paid call. Canned response bytes go into
the pure parsers; canned JSONL goes into the aggregator; the forward target is
checked as a pure string computation.

THE INVARIANT MOST OF THESE TESTS DEFEND: on api.anthropic.com these fields do
not exist, and absence must stay absence. A 0.0 cost reads as a free run, which
is the exact under-reporting bug this lane exists to end.
"""

import io
import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import proxy  # noqa: E402


def _sse(*events: dict) -> bytes:
    return b"\n".join(b"data: " + json.dumps(e).encode() for e in events) + b"\n"


#: A plain api.anthropic.com stream: msg_ id, no cost anywhere.
_ANTHROPIC_SSE = _sse(
    {"type": "message_start",
     "message": {"id": "msg_01ABC", "model": "claude-sonnet-4-6",
                 "usage": {"input_tokens": 2, "cache_creation_input_tokens": 55351}}},
    {"type": "message_delta", "delta": {"stop_reason": "end_turn"},
     "usage": {"output_tokens": 4}},
)

#: The same call through OpenRouter's Anthropic skin: gen- id + cost, plus the
#: `provider` and `output_tokens_details` members. Streamed, because that is the
#: shape the live lane actually gets.
#:
#: PLACEMENT is the point of this fixture, and every member sits where a probe of
#: that skin put it (probed 2026-08-24): message_start
#: carries `provider` and a usage block whose token members are all zero or null,
#: and the REAL prompt/cache/output counts arrive on message_delta together with
#: cost and the reasoning count. A parser that reads prompt tokens only from
#: message_start therefore records a paid gateway call as 0 in / 0 cached.
_OPENROUTER_SSE = _sse(
    {"type": "message_start",
     "message": {"id": "gen-1755500000-aBcDeF", "model": "anthropic/claude-sonnet-5",
                 "provider": "Google",
                 "usage": {"input_tokens": 0, "output_tokens": 0,
                           "output_tokens_details": None,
                           "cache_creation_input_tokens": None,
                           "cache_read_input_tokens": None}}},
    {"type": "message_delta", "delta": {"stop_reason": "end_turn"},
     "usage": {"input_tokens": 31, "output_tokens": 239, "cost": 9.6e-05,
               "output_tokens_details": {"thinking_tokens": 237},
               "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
               "cost_details": {"upstream_inference_prompt_cost": 1.6e-05,
                                "upstream_inference_completions_cost": 8e-05}}},
)


class TestParseUpstream(unittest.TestCase):
    def test_default_is_unchanged(self):
        for spec in (None, "", "   "):
            up = proxy.parse_upstream(spec)
            self.assertEqual(up, proxy.DEFAULT_UPSTREAM)
            self.assertEqual(up.host, "api.anthropic.com")
            self.assertEqual(up.port, 443)
            self.assertTrue(up.tls)
            self.assertEqual(up.path_prefix, "")
            # The default path must be byte-identical to the pre-change forward.
            self.assertEqual(up.forward_path("/v1/messages"), "/v1/messages")
            self.assertEqual(up.host_header, "api.anthropic.com")

    def test_bare_host(self):
        up = proxy.parse_upstream("api.anthropic.com")
        self.assertEqual(up, proxy.DEFAULT_UPSTREAM)

    def test_openrouter_url_keeps_the_path_prefix(self):
        # The whole reason a bare host is not enough: the CLI asks for
        # /v1/messages and OpenRouter's Anthropic skin lives under /api.
        up = proxy.parse_upstream("https://openrouter.ai/api")
        self.assertEqual((up.host, up.port, up.tls), ("openrouter.ai", 443, True))
        self.assertEqual(up.path_prefix, "/api")
        self.assertEqual(up.forward_path("/v1/messages"), "/api/v1/messages")
        self.assertEqual(up.host_header, "openrouter.ai")
        self.assertEqual(up.label, "https://openrouter.ai/api")

    def test_trailing_slash_does_not_double_up(self):
        up = proxy.parse_upstream("https://openrouter.ai/api/")
        self.assertEqual(up.forward_path("/v1/messages"), "/api/v1/messages")

    def test_explicit_port_and_http(self):
        up = proxy.parse_upstream("http://127.0.0.1:8080/api")
        self.assertEqual((up.host, up.port, up.tls), ("127.0.0.1", 8080, False))
        self.assertEqual(up.host_header, "127.0.0.1:8080")
        self.assertEqual(up.label, "http://127.0.0.1:8080/api")

    def test_quoted_value_survives(self):
        # .env values are routinely quoted; the quotes must not become a hostname.
        self.assertEqual(proxy.parse_upstream('"https://openrouter.ai/api"').host,
                         "openrouter.ai")

    def test_bad_spec_raises_rather_than_falling_back(self):
        # Falling back to the default would spend FIRST-PARTY money while the
        # operator believed they were measuring a gateway.
        for bad in ("ftp://openrouter.ai", "https:///api", "https://x/api?k=1",
                    "https://openrouter.ai:notaport/api"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    proxy.parse_upstream(bad)

    def test_resolve_reads_env_at_call_time(self):
        with mock.patch.dict(os.environ, {proxy.UPSTREAM_ENV: "https://openrouter.ai/api"}):
            self.assertEqual(proxy.resolve_upstream().host, "openrouter.ai")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(proxy.resolve_upstream(), proxy.DEFAULT_UPSTREAM)


class TestGatewayFieldCapture(unittest.TestCase):
    def test_sse_captures_cost_and_generation_id(self):
        rec = proxy.parse_sse_response(_OPENROUTER_SSE)
        self.assertAlmostEqual(rec["cost_usd"], 9.6e-05)
        self.assertEqual(rec["cost_details"]["upstream_inference_prompt_cost"], 1.6e-05)
        self.assertEqual(rec["generation_id"], "gen-1755500000-aBcDeF")
        self.assertEqual(rec["response_id"], "gen-1755500000-aBcDeF")
        # The pre-existing fields must be untouched by the addition — and on this
        # wire that means reading them off message_delta, the only event that has
        # them (see the fixture's placement note).
        self.assertEqual(rec["input_tokens"], 31)
        self.assertEqual(rec["output_tokens"], 239)
        self.assertEqual(rec["model"], "anthropic/claude-sonnet-5")

    def test_sse_cost_in_message_start_also_captured(self):
        # The measured skin puts cost on message_delta, but both usage blocks are
        # read: a gateway that finalises earlier must not go unpriced.
        rec = proxy.parse_sse_response(_sse(
            {"type": "message_start",
             "message": {"id": "gen-x", "model": "m",
                         "usage": {"input_tokens": 1, "cost": 0.5}}},
        ))
        self.assertEqual(rec["cost_usd"], 0.5)

    def test_anthropic_stream_leaves_gateway_fields_absent(self):
        rec = proxy.parse_sse_response(_ANTHROPIC_SSE)
        self.assertNotIn("cost_usd", rec)
        self.assertNotIn("cost_details", rec)
        self.assertNotIn("generation_id", rec)  # msg_ ids are NOT generation ids
        self.assertEqual(rec["response_id"], "msg_01ABC")
        self.assertEqual(rec["cache_write"], 55351)

    def test_json_response_captures_and_omits_symmetrically(self):
        openrouter = json.dumps({
            "id": "gen-42", "model": "anthropic/claude-sonnet-5",
            "usage": {"input_tokens": 2, "output_tokens": 4, "cost": 0.00012,
                      "cost_details": {"upstream_inference_prompt_cost": 2e-05}},
            "content": [{"type": "text", "text": "hi"}],
        }).encode()
        rec = proxy.parse_json_response(openrouter)
        self.assertEqual(rec["cost_usd"], 0.00012)
        self.assertEqual(rec["generation_id"], "gen-42")

        anthropic = json.dumps({
            "id": "msg_02", "model": "claude-sonnet-4-6",
            "usage": {"input_tokens": 2, "output_tokens": 4},
            "content": [{"type": "text", "text": "hi"}],
        }).encode()
        rec = proxy.parse_json_response(anthropic)
        self.assertNotIn("cost_usd", rec)
        self.assertNotIn("generation_id", rec)
        self.assertEqual(rec["response_id"], "msg_02")

    def test_zero_cost_is_recorded_but_false_is_not(self):
        # A genuine 0.0 from the gateway (a free/cached call) IS a measurement and
        # must survive; a bool is not a number and must not be mistaken for one.
        rec = proxy.parse_json_response(json.dumps({"usage": {"cost": 0.0}}).encode())
        self.assertEqual(rec["cost_usd"], 0.0)
        rec = proxy.parse_json_response(json.dumps({"usage": {"cost": False}}).encode())
        self.assertNotIn("cost_usd", rec)

    def test_reasoning_and_provider_captured_only_where_the_wire_reports_them(self):
        # output_tokens alone cannot say how much of it was thinking, and the
        # model id alone does not name the backend that answered — both are
        # gateway-only members and neither is derivable from what was already
        # recorded. On api.anthropic.com they must stay absent, not become 0/"".
        rec = proxy.parse_sse_response(_OPENROUTER_SSE)
        self.assertEqual(rec["reasoning_tokens"], 237)
        self.assertEqual(rec["provider"], "Google")
        rec = proxy.parse_json_response(json.dumps({
            "id": "gen-42", "model": "x-ai/grok-4.6", "provider": "xAI",
            "usage": {"input_tokens": 2, "output_tokens": 40,
                      "output_tokens_details": {"thinking_tokens": 31}},
        }).encode())
        self.assertEqual(rec["reasoning_tokens"], 31)
        self.assertEqual(rec["provider"], "xAI")
        rec = proxy.parse_sse_response(_ANTHROPIC_SSE)
        self.assertNotIn("reasoning_tokens", rec)
        self.assertNotIn("provider", rec)

    def test_prompt_side_counts_come_from_whichever_event_carries_them(self):
        # Unlike the gateway-only fields, these three are SEEDED to 0 — so losing
        # them does not read as absence, it reads as a measured zero, and the
        # est_cost/cache-hit numbers derived from the log are silently wrong.
        rec = proxy.parse_sse_response(_sse(
            {"type": "message_start",
             "message": {"id": "gen-y", "model": "qwen/qwen3.8-max",
                         "usage": {"input_tokens": 0,
                                   "cache_read_input_tokens": None,
                                   "cache_creation_input_tokens": None}}},
            {"type": "message_delta", "delta": {"stop_reason": "end_turn"},
             "usage": {"input_tokens": 265135, "output_tokens": 699,
                       "cache_read_input_tokens": 262144,
                       "cache_creation_input_tokens": 2048}},
        ))
        self.assertEqual(rec["input_tokens"], 265135)
        self.assertEqual(rec["cache_read"], 262144)
        self.assertEqual(rec["cache_write"], 2048)
        # The same rule in reverse: api.anthropic.com finalises these on
        # message_start, so a later null must not overwrite them with nothing.
        rec = proxy.parse_sse_response(_sse(
            {"type": "message_start",
             "message": {"id": "msg_01", "model": "claude-sonnet-4-6",
                         "usage": {"input_tokens": 2,
                                   "cache_creation_input_tokens": 55351}}},
            {"type": "message_delta", "delta": {"stop_reason": "end_turn"},
             "usage": {"output_tokens": 4, "input_tokens": None,
                       "cache_creation_input_tokens": None}},
        ))
        self.assertEqual(rec["input_tokens"], 2)
        self.assertEqual(rec["cache_write"], 55351)

    def test_usage_record_carries_the_fields_through(self):
        rec = proxy.build_usage_record(
            proxy.parse_sse_response(_OPENROUTER_SSE), "/v1/messages", 200, True, ts=1.0)
        self.assertAlmostEqual(rec["cost_usd"], 9.6e-05)
        self.assertEqual(rec["generation_id"], "gen-1755500000-aBcDeF")

        rec = proxy.build_usage_record(
            proxy.parse_sse_response(_ANTHROPIC_SSE), "/v1/messages", 200, True, ts=1.0)
        for k in ("cost_usd", "cost_details", "generation_id"):
            self.assertNotIn(k, rec)


def _write(log: Path, recs) -> None:
    log.write_text("\n".join(json.dumps(r) for r in recs) + "\n")


class TestCostAggregate(unittest.TestCase):
    def test_sums_cost_details_and_collects_generation_ids(self):
        with TemporaryDirectory() as td:
            log = Path(td) / "usage.jsonl"
            _write(log, [
                {"model": "anthropic/claude-sonnet-5", "input_tokens": 10,
                 "cost_usd": 9.6e-05, "generation_id": "gen-1",
                 "cost_details": {"upstream_inference_prompt_cost": 1.6e-05,
                                  "upstream_inference_completions_cost": 8e-05}},
                {"model": "anthropic/claude-sonnet-5", "input_tokens": 20,
                 "cost_usd": 4.0e-05, "generation_id": "gen-2",
                 "cost_details": {"upstream_inference_prompt_cost": 1.0e-05}},
            ])
            agg = proxy.usage_since(0, "anthropic/claude-sonnet-5", usage_log=log)
            self.assertAlmostEqual(agg["cost_usd"], 1.36e-04)
            self.assertEqual(agg["requests_with_cost"], 2)
            self.assertIs(agg["cost_partial"], False)
            self.assertEqual(agg["generation_ids"], ["gen-1", "gen-2"])
            self.assertAlmostEqual(
                agg["cost_details_usd"]["upstream_inference_prompt_cost"], 2.6e-05)
            self.assertAlmostEqual(
                agg["cost_details_usd"]["upstream_inference_completions_cost"], 8e-05)
            self.assertEqual(agg["input_tokens"], 30)  # unchanged behaviour

    def test_reasoning_sums_and_providers_dedupe_but_absence_stays_none(self):
        with TemporaryDirectory() as td:
            log = Path(td) / "usage.jsonl"
            _write(log, [
                {"model": "qwen/qwen3.8-max", "reasoning_tokens": 731,
                 "provider": "Alibaba"},
                {"model": "qwen/qwen3.8-max", "reasoning_tokens": 12,
                 "provider": "Novita"},
                {"model": "qwen/qwen3.8-max", "provider": "Alibaba"},
            ])
            agg = proxy.usage_since(0, "qwen/qwen3.8-max", usage_log=log)
            self.assertEqual(agg["reasoning_tokens"], 743)
            # TWO backends under one model id: this window averages two systems.
            self.assertEqual(agg["providers"], ["Alibaba", "Novita"])
        with TemporaryDirectory() as td:
            log = Path(td) / "usage.jsonl"
            _write(log, [{"model": "claude-sonnet-4-6", "output_tokens": 40}])
            agg = proxy.usage_since(0, "sonnet-4.6", usage_log=log)
            # "did not think" and "this wire does not say" are different answers.
            self.assertIsNone(agg["reasoning_tokens"])
            self.assertEqual(agg["providers"], [])

    def test_window_reports_the_record_schemas_it_actually_contains(self):
        # The prompt-token columns changed MEANING (see USAGE_REC_SCHEMA), so a
        # reader has to be able to tell which rule produced a row before averaging
        # two windows together. Legacy lines carry no stamp, and that absence IS
        # schema 1 — treating it as unknown would hide the boundary instead of
        # naming it.
        stamped = proxy.build_usage_record({}, "/v1/messages", 200, True, ts=1.0)
        self.assertEqual(stamped["rec_schema"], proxy.USAGE_REC_SCHEMA)
        with TemporaryDirectory() as td:
            log = Path(td) / "usage.jsonl"
            _write(log, [{"model": "m", "input_tokens": 5},
                         {"model": "m", "input_tokens": 5,
                          "rec_schema": proxy.USAGE_REC_SCHEMA}])
            agg = proxy.usage_since(0, "m", usage_log=log)
            self.assertEqual(agg["rec_schemas"], [1, proxy.USAGE_REC_SCHEMA])

    def test_absent_cost_stays_none_never_zero(self):
        with TemporaryDirectory() as td:
            log = Path(td) / "usage.jsonl"
            _write(log, [{"model": "claude-sonnet-4-6", "input_tokens": 5},
                         {"model": "claude-sonnet-4-6", "input_tokens": 5}])
            agg = proxy.usage_since(0, "sonnet-4.6", usage_log=log)
            self.assertIsNone(agg["cost_usd"])
            self.assertIsNone(agg["cost_partial"])
            self.assertEqual(agg["requests_with_cost"], 0)
            self.assertEqual(agg["generation_ids"], [])
            self.assertEqual(agg["cost_details_usd"], {})

    def test_partial_coverage_is_flagged_not_hidden(self):
        # A window where only some requests priced: the sum UNDER-states, and a
        # caller that reads it as a total publishes a number that is too low.
        with TemporaryDirectory() as td:
            log = Path(td) / "usage.jsonl"
            _write(log, [{"model": "m", "cost_usd": 0.01, "generation_id": "gen-1"},
                         {"model": "m"},
                         {"model": "m", "cost_usd": 0.02, "generation_id": "gen-3"}])
            agg = proxy.usage_since(0, "m", usage_log=log)
            self.assertAlmostEqual(agg["cost_usd"], 0.03)
            self.assertEqual(agg["requests"], 3)
            self.assertEqual(agg["requests_with_cost"], 2)
            self.assertIs(agg["cost_partial"], True)
            self.assertEqual(agg["generation_ids"], ["gen-1", "gen-3"])

    def test_n_before_offset_applies_to_cost_too(self):
        with TemporaryDirectory() as td:
            log = Path(td) / "usage.jsonl"
            _write(log, [{"model": "m", "cost_usd": 999.0, "generation_id": "gen-old"},
                         {"model": "m", "cost_usd": 1.0, "generation_id": "gen-new"}])
            agg = proxy.usage_since(1, "m", usage_log=log)
            self.assertEqual(agg["cost_usd"], 1.0)
            self.assertEqual(agg["generation_ids"], ["gen-new"])

    def test_missing_log_reports_no_cost(self):
        agg = proxy.usage_since(0, "m", usage_log=Path("does-not-exist.jsonl"))
        self.assertIsNone(agg["cost_usd"])
        self.assertEqual(agg["generation_ids"], [])


class TestCostPartialDenominator(unittest.TestCase):
    """``cost_partial`` counts BILLABLE requests, not every forwarded request.

    WHY (adversarial review, 2026-08-18): the proxy appends a usage record for
    EVERY forwarded request — count_tokens probes, non-messages GETs, error
    responses — and only a /v1/messages completion can carry ``usage.cost``. With
    ``requests`` as the denominator the flag went True the moment a window held
    one non-completion request, so it read True on essentially every real gateway
    run and told a reader nothing. The cases below are the four record shapes that
    distinguish the two denominators.
    """

    def _agg(self, recs):
        with TemporaryDirectory() as td:
            log = Path(td) / "usage.jsonl"
            _write(log, recs)
            return proxy.usage_since(0, "m", usage_log=log)

    def test_count_tokens_probe_does_not_fake_a_partial_window(self):
        agg = self._agg([
            {"path": "/v1/messages", "status": 200, "model": "m",
             "cost_usd": 0.01, "generation_id": "gen-1"},
            # The SDK's free token-count probe: logged, never priced.
            {"path": "/v1/messages/count_tokens", "status": 200, "model": None},
        ])
        self.assertEqual(agg["requests"], 2)          # both were forwarded
        self.assertEqual(agg["requests_billable"], 1)  # only one could be billed
        self.assertEqual(agg["requests_with_cost"], 1)
        self.assertIs(agg["cost_partial"], False)

    def test_error_response_does_not_fake_a_partial_window(self):
        agg = self._agg([
            {"path": "/v1/messages", "status": 200, "model": "m", "cost_usd": 0.01},
            {"path": "/v1/messages", "status": 429, "model": None},
        ])
        self.assertEqual(agg["requests_billable"], 1)
        self.assertIs(agg["cost_partial"], False)

    def test_a_real_missed_cost_still_flags_partial(self):
        # The case the flag exists for: a genuine completion the gateway priced
        # and one it did not. The sum UNDER-states and must say so.
        agg = self._agg([
            {"path": "/v1/messages", "status": 200, "model": "m", "cost_usd": 0.01},
            {"path": "/v1/messages", "status": 200, "model": "m"},
        ])
        self.assertEqual(agg["requests_billable"], 2)
        self.assertIs(agg["cost_partial"], True)

    def test_unreadable_completion_body_fails_closed(self):
        # 200 on /v1/messages but no model parsed out (truncated tee / client
        # disconnect). "Could not tell" must widen the denominator and WARN, not
        # shrink it into a confident False.
        agg = self._agg([
            {"path": "/v1/messages", "status": 200, "model": "m", "cost_usd": 0.01},
            {"path": "/v1/messages", "status": 200, "model": None},
        ])
        self.assertEqual(agg["requests_billable"], 2)
        self.assertIs(agg["cost_partial"], True)

    def test_missing_status_fails_closed(self):
        # Legacy/handwritten lines with no status: unclassifiable, so billable.
        agg = self._agg([
            {"path": "/v1/messages", "model": "m", "cost_usd": 0.01},
            {"path": "/v1/messages", "model": "m"},
        ])
        self.assertEqual(agg["requests_billable"], 2)
        self.assertIs(agg["cost_partial"], True)

    def test_a_priced_record_is_billable_by_construction(self):
        # requests_with_cost <= requests_billable must hold even for a record the
        # classifier would otherwise reject, or cost_partial inverts.
        rec = {"path": "/healthz", "status": 500, "model": None, "cost_usd": 0.02}
        self.assertTrue(proxy.cost_bearing_request(rec))
        agg = self._agg([rec])
        self.assertEqual(agg["requests_billable"], 1)
        self.assertIs(agg["cost_partial"], False)

    def test_query_string_and_trailing_slash_still_match_messages(self):
        for path in ("/v1/messages?beta=true", "/v1/messages/"):
            with self.subTest(path=path):
                self.assertTrue(proxy.cost_bearing_request(
                    {"path": path, "status": 200}))
        self.assertFalse(proxy.cost_bearing_request(
            {"path": "/v1/messages/count_tokens", "status": 200}))

    def test_all_gateway_records_priced_reads_complete(self):
        agg = self._agg([
            {"path": "/v1/messages", "status": 200, "model": "m", "cost_usd": 0.01},
            {"path": "/v1/messages", "status": 200, "model": "m", "cost_usd": 0.02},
        ])
        self.assertEqual(agg["requests_billable"], 2)
        self.assertEqual(agg["requests_with_cost"], 2)
        self.assertIs(agg["cost_partial"], False)

    def test_no_cost_anywhere_is_none_not_partial(self):
        # api.anthropic.com: no cost field exists at all. None means "no cost
        # data", which is not the same claim as "the sum is incomplete".
        agg = self._agg([
            {"path": "/v1/messages", "status": 200, "model": "claude-sonnet-4-6"},
            {"path": "/v1/messages", "status": 200, "model": "claude-sonnet-4-6"},
        ])
        self.assertEqual(agg["requests_billable"], 2)
        self.assertIsNone(agg["cost_partial"])
        self.assertIsNone(agg["cost_usd"])


def _serve_healthz():
    """Drive the REAL ``Handler.do_GET('/healthz')`` with no socket and no server.

    Returns ``(status, wire_bytes, headers)``. The handler is built with
    ``__new__`` (BaseHTTPRequestHandler's ``__init__`` IS the request loop), and
    only the three response primitives are stubbed, so the body below is the
    genuine byte string the proxy would put on the wire.
    """
    h = proxy.Handler.__new__(proxy.Handler)
    h.path = "/healthz"
    h.wfile = io.BytesIO()
    captured = {"status": None, "headers": []}

    def send_response(code, message=None):
        captured["status"] = code

    h.send_response = send_response
    h.send_header = lambda k, v: captured["headers"].append((k, str(v)))
    h.end_headers = lambda: None
    h.do_GET()
    return captured["status"], h.wfile.getvalue(), dict(captured["headers"])


class TestHealthzWireBytes(unittest.TestCase):
    """The /healthz body is pinned as LITERAL BYTES, independent of the code.

    WHY THIS SHAPE (adversarial review, 2026-08-18): the test this replaces built
    its own expected body with ``json.dumps(..., separators=(",", ":"))`` — the
    same call as the code under test — so it passed under ANY mutation of those
    separators and defended nothing. ``separators`` is load-bearing: ``healthz()``
    and ``aura_rig/preflight.py`` both match the literal substring '"proxy":"ok"',
    which json.dumps' default ", "/": " spacing breaks. Mutation-checked
    2026-08-18: flipping the proxy to ``separators=(", ", ": ")`` turns the two
    byte-equality tests below RED (and healthz() False), while the old test stayed
    green.
    """

    def test_openrouter_upstream_body_is_exactly_these_bytes(self):
        with mock.patch.dict(os.environ,
                             {proxy.UPSTREAM_ENV: "https://openrouter.ai/api"}):
            status, body, headers = _serve_healthz()
        self.assertEqual(status, 200)
        self.assertEqual(body,
                         b'{"proxy":"ok","upstream":"https://openrouter.ai/api"}')
        # Content-Length is computed by the handler; a body/length disagreement
        # hangs a real client on a keep-alive connection.
        self.assertEqual(headers["Content-Length"], str(len(body)))
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_default_upstream_body_is_exactly_these_bytes(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            status, body, _ = _serve_healthz()
        self.assertEqual(status, 200)
        self.assertEqual(body,
                         b'{"proxy":"ok","upstream":"https://api.anthropic.com"}')

    def test_the_real_bytes_satisfy_the_real_client(self):
        # Closes the loop: the server's actual output is fed to the actual reader,
        # so neither half is allowed to drift into its own private format.
        with mock.patch.dict(os.environ,
                             {proxy.UPSTREAM_ENV: "https://openrouter.ai/api"}):
            status, body, _ = _serve_healthz()
        text = body.decode()
        self.assertTrue(proxy.healthz(opener=lambda u, t: (status, text)))
        self.assertEqual(proxy.reported_upstream(opener=lambda u, t: (status, text)),
                         "https://openrouter.ai/api")


class TestHealthzFailsClosedOnBadUpstream(unittest.TestCase):
    """An unparseable CB_PROXY_UPSTREAM must NOT read as a healthy proxy.

    The SILENT-OK this closes (adversarial review, 2026-08-18): do_GET used to
    answer 200 ``"proxy":"ok"`` and merely swap the upstream value for
    ``INVALID: <err>``, so ``healthz()`` returned True and a preflight gate logged
    PASS while every forwarded request 502'd.
    """

    BAD = "ftp://openrouter.ai"  # rejected by parse_upstream (unsupported scheme)

    def _serve_bad(self):
        with mock.patch.dict(os.environ, {proxy.UPSTREAM_ENV: self.BAD}):
            return _serve_healthz()

    def test_the_spec_really_is_unparseable(self):
        # Guards the test itself: if parse_upstream ever accepted this, the cases
        # below would pass for the wrong reason.
        with self.assertRaises(ValueError):
            proxy.parse_upstream(self.BAD)

    def test_response_is_not_200_and_not_ok(self):
        status, body, _ = self._serve_bad()
        self.assertNotEqual(status, 200)
        self.assertEqual(status, 503)
        self.assertNotIn(b'"proxy":"ok"', body)
        payload = json.loads(body.decode())
        self.assertEqual(payload["proxy"], "misconfigured")
        # It must still SAY which spec was bad — an unnamed refusal is unfixable.
        self.assertTrue(payload["upstream"].startswith("INVALID:"))
        self.assertIn("ftp", payload["upstream"])

    def test_healthz_is_false_for_that_exact_response(self):
        status, body, _ = self._serve_bad()
        self.assertFalse(proxy.healthz(opener=lambda u, t: (status, body.decode())))

    def test_reported_upstream_is_none_for_that_exact_response(self):
        status, body, _ = self._serve_bad()
        self.assertIsNone(
            proxy.reported_upstream(opener=lambda u, t: (status, body.decode())))

    def test_old_build_200_ok_with_invalid_upstream_is_still_refused(self):
        # healthz() is the CLIENT half and can be newer than the running server: a
        # proxy started from a pre-fix copy of proxy.py answers exactly this.
        old = '{"proxy":"ok","upstream":"INVALID: CB_PROXY_UPSTREAM: bad port"}'
        self.assertFalse(proxy.healthz(opener=lambda u, t: (200, old)))

    def test_a_healthy_ok_body_is_still_true(self):
        # The refusal must not swallow the normal case (nor the older build that
        # answers 200 "ok" with no upstream field at all).
        self.assertTrue(proxy.healthz(opener=lambda u, t: (200, '{"proxy":"ok"}')))
        self.assertTrue(proxy.healthz(
            opener=lambda u, t: (200, '{"proxy":"ok","upstream":"https://x/api"}')))


class TestReportedUpstream(unittest.TestCase):
    """The reader a caller uses to confirm WHICH endpoint a live proxy tees."""

    def _body(self, upstream):
        return json.dumps({"proxy": "ok", "upstream": upstream},
                          separators=(",", ":"))

    def test_reads_the_label(self):
        self.assertEqual(
            proxy.reported_upstream(
                opener=lambda u, t: (200, self._body("https://openrouter.ai/api"))),
            "https://openrouter.ai/api")

    def test_unconfirmed_cases_all_return_none(self):
        # Down, erroring, older build with no field, and a proxy whose own env is
        # broken. All mean UNCONFIRMED — never "route anyway".
        cases = {
            "non-200": lambda u, t: (502, ""),
            "no upstream field": lambda u, t: (200, '{"proxy":"ok"}'),
            "not json": lambda u, t: (200, "not json"),
            "invalid upstream": lambda u, t: (200, self._body("INVALID: bad spec")),
        }
        for name, opener in cases.items():
            with self.subTest(case=name):
                self.assertIsNone(proxy.reported_upstream(opener=opener))

        def boom(u, t):
            raise OSError("connection refused")
        self.assertIsNone(proxy.reported_upstream(opener=boom))


class TestOptInProxyRouting(unittest.TestCase):
    """adapters/registry.py's CB_PROXY_OPENROUTER switch (step 4).

    THE DEFAULT MUST NOT MOVE: with the flag unset every lane routes exactly as
    it did before, which is what the first test pins.
    """

    DIRECT = "https://openrouter.ai/api"

    def setUp(self):
        from adapters import registry
        self.registry = registry
        self.base_env = {"OPENROUTER_API_KEY": "sk-or-FAKE-NOT-A-REAL-KEY"}

    def test_flag_unset_leaves_routing_untouched(self):
        with mock.patch.dict(os.environ, self.base_env, clear=True):
            env = self.registry.openrouter_env_overrides()
        self.assertEqual(env["ANTHROPIC_BASE_URL"], self.DIRECT)
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "sk-or-FAKE-NOT-A-REAL-KEY")
        self.assertEqual(env["ANTHROPIC_API_KEY"], "")

    def test_gateway_subprocess_is_isolated_from_the_operator_login(self):
        """CLAUDE_CONFIG_DIR must be set (and not ~/.claude) on every
        openrouter-routed transport. Regression for 2026-08-20: the CLI's
        account-side model gate started rejecting every non-Anthropic slashed
        id ("unrecognized_model", 6.1s synthetic FAIL_NO_EDITS) through the
        operator's logged-in config, while an isolated config dir passed the
        id through to the gateway — same binary, same env, minutes apart. A
        login must never be able to change what models the harness can run."""
        with mock.patch.dict(os.environ, self.base_env, clear=True):
            env = self.registry.openrouter_env_overrides()
        self.assertIn("CLAUDE_CONFIG_DIR", env)
        self.assertNotEqual(
            Path(env["CLAUDE_CONFIG_DIR"]).name, ".claude",
            "the openrouter transport must NOT inherit the operator's "
            "logged-in ~/.claude config")

    def test_flag_on_with_matching_proxy_routes_through_it(self):
        env = dict(self.base_env, CB_PROXY_OPENROUTER="1")
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(proxy, "reported_upstream", return_value=self.DIRECT):
            out = self.registry.openrouter_env_overrides()
        self.assertEqual(out["ANTHROPIC_BASE_URL"], proxy.CLI_BASE_URL)
        # The CLI appends /v1/messages itself — a "/v1" here would ask the proxy
        # for /v1/v1/messages.
        self.assertFalse(out["ANTHROPIC_BASE_URL"].endswith("/v1"))
        # Auth is untouched: the proxy forwards the Bearer header verbatim.
        self.assertEqual(out["ANTHROPIC_AUTH_TOKEN"], "sk-or-FAKE-NOT-A-REAL-KEY")

    def test_trailing_slash_still_matches(self):
        env = dict(self.base_env, CB_PROXY_OPENROUTER="1")
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(proxy, "reported_upstream",
                                  return_value=self.DIRECT + "/"):
            out = self.registry.openrouter_env_overrides()
        self.assertEqual(out["ANTHROPIC_BASE_URL"], proxy.CLI_BASE_URL)

    def test_no_proxy_refuses_rather_than_routing_direct(self):
        # Routing direct here would produce a run that LOOKS cost-measured but
        # carries the CLI's first-party-priced number.
        env = dict(self.base_env, CB_PROXY_OPENROUTER="1")
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(proxy, "reported_upstream", return_value=None):
            with self.assertRaises(ValueError) as cm:
                self.registry.openrouter_env_overrides()
        self.assertIn("CB_PROXY_UPSTREAM", str(cm.exception))

    def test_proxy_pointed_elsewhere_refuses(self):
        # The :41299 proxy is SHARED with the Aura lane, which pins
        # api.anthropic.com; routing OpenRouter traffic into it would send an
        # OpenRouter key to Anthropic.
        env = dict(self.base_env, CB_PROXY_OPENROUTER="1")
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(proxy, "reported_upstream",
                                  return_value="https://api.anthropic.com"):
            with self.assertRaises(ValueError) as cm:
                self.registry.openrouter_env_overrides()
        self.assertIn("api.anthropic.com", str(cm.exception))

    def test_off_values_are_off(self):
        for off in ("", "0", "false", "no"):
            with self.subTest(value=off):
                env = dict(self.base_env, CB_PROXY_OPENROUTER=off)
                with mock.patch.dict(os.environ, env, clear=True):
                    out = self.registry.openrouter_env_overrides()
                self.assertEqual(out["ANTHROPIC_BASE_URL"], self.DIRECT)


if __name__ == "__main__":
    unittest.main()
