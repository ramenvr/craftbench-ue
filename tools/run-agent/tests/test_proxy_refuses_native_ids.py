"""Claude models go to api.anthropic.com. The proxy now enforces that.

OWNER REQUIREMENT, 2026-08-26: "claude models should go through api.anthropic,
not openrouter". It already held by construction --
`registry.is_openrouter_model_id` routes on the slash, so a slashless id never
receives the proxy base URL, and 1,174 proxied requests contained zero Claude
ids. These tests make it hold by enforcement, because the failure mode is silent
and expensive: the proxy's upstream is ONE global setting, so anything that ever
reached it with a native id would be forwarded to a gateway, billed there, and
recorded as though measured.

Not hypothetical. Minutes before this file, a proxy restart that dropped
`CB_PROXY_UPSTREAM` came up pointing at api.anthropic.com while every arm in
flight was an OpenRouter one -- the same mistake mirrored, caught only because
someone read the boot line.

Stdlib only. No socket, no key, no tokens.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from aura_rig.proxy import Upstream, native_id_sent_to_gateway  # noqa: E402

GATEWAY = Upstream("openrouter.ai", 443, True, "/api")
FIRST_PARTY = Upstream("api.anthropic.com", 443, True, "")


def body(model) -> bytes:
    return json.dumps({"model": model, "messages": []}).encode()


class TestANativeIdBoundForAGatewayIsCaught(unittest.TestCase):
    def test_a_claude_id_is_named(self):
        self.assertEqual("claude-sonnet-5",
                         native_id_sent_to_gateway(body("claude-sonnet-5"), GATEWAY))

    def test_every_slashless_form_the_cli_accepts(self):
        for m in ("sonnet-5", "claude-sonnet-4-5-20250929", "opus-5", "haiku-4-5"):
            self.assertEqual(m, native_id_sent_to_gateway(body(m), GATEWAY), m)


class TestNothingElseIsRefused(unittest.TestCase):
    """A false refusal breaks a live drive, which is worse than the leak it
    prevents -- so every one of these must pass through."""

    def test_openrouter_ids_pass(self):
        for m in ("deepseek/deepseek-v4-pro-0813", "x-ai/grok-4.6",
                  "openai/gpt-5.6-sol", "google/gemini-3.7-flash",
                  "anthropic/claude-opus-5"):
            self.assertIsNone(native_id_sent_to_gateway(body(m), GATEWAY), m)

    def test_a_claude_id_to_the_FIRST_PARTY_upstream_is_fine(self):
        # That is the correct destination; refusing here would ban the right thing.
        self.assertIsNone(native_id_sent_to_gateway(body("claude-sonnet-5"),
                                                    FIRST_PARTY))

    def test_an_unparseable_body_fails_open(self):
        # A request we cannot read proves nothing, and a diagnostic must not be
        # what breaks a drive.
        for raw in (b"", b"not json", b"[1,2,3]"):
            self.assertIsNone(native_id_sent_to_gateway(raw, GATEWAY), raw)

    def test_a_body_with_no_model_fails_open(self):
        self.assertIsNone(native_id_sent_to_gateway(b'{"messages":[]}', GATEWAY))


class TestItAgreesWithTheROUTER(unittest.TestCase):
    """Two places must not drift into disagreeing about what 'native' means."""

    def test_the_same_slash_rule_decides_both(self):
        from adapters.registry import is_openrouter_model_id
        for m in ("claude-sonnet-5", "sonnet-5", "deepseek/deepseek-v4-pro-0813",
                  "x-ai/grok-4.6", "anthropic/claude-opus-5"):
            routed_to_gateway = is_openrouter_model_id(m)
            refused = native_id_sent_to_gateway(body(m), GATEWAY) is not None
            self.assertEqual(routed_to_gateway, not refused, m)


class TestItIsWired(unittest.TestCase):
    def test_the_proxy_refuses_instead_of_forwarding(self):
        src = (_ROOT / "aura_rig" / "proxy.py").read_text(encoding="utf-8")
        self.assertIn("native_id_sent_to_gateway(body, up)", src)
        self.assertIn("self.send_response(421)", src)


if __name__ == "__main__":
    unittest.main()
