"""The OpenRouter request must ASK for what we later claim to have measured.

THE BUG THESE PIN (2026-08-18). Every openrouter-routed run recorded no cost. The
cost READER was already correct — ``usage.cost`` was parsed and stored — but
OpenRouter only populates that field when the request sets ``usage:
{"include": true}``, which we never sent. So the number was always absent and every
model looked free. Two models with no free tier on OpenRouter (``x-ai/grok-4.6`` at
$2/$6 per M, and the whole ``gpt-5.6`` family) both reading zero is a reporting gap,
not a promotion.

**A reader without its request is the shape of a measurement that silently never
happens** — nothing errors, a plausible value appears, and the gap is only visible
by comparing against the provider's own ledger. Hence tests on the REQUEST BODY, not
just on the parser.

The routing tests cover a validity problem that rides along: without a ``provider``
block OpenRouter may fail over to another host, or to a quantized build, mid-run.
A panel that pins a model but not the machine serving it compares different systems
under one label — observed the same day, one pinned slug answering as grok-4.5 on
some calls and grok-4.6 on others.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters import bare_wire  # noqa: E402


class TestOpenRouterAccountingAndRouting(unittest.TestCase):
    def _capture(self, base_url=bare_wire.DEFAULT_BASE_URL):
        """Send one call through a fake transport and return the request body."""
        seen = {}

        def fake_post(url, body, headers, timeout):
            seen["url"], seen["body"] = url, body
            return {"choices": [{"message": {"content": "ok"},
                                 "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1}}

        bare_wire.call_openai_compatible(
            api_key="k", model="x-ai/grok-4.6", system=None,
            messages=[{"role": "user", "content": "hi"}], tools=[],
            max_tokens=16, base_url=base_url, post_json=fake_post)
        return seen["body"]

    def test_usage_accounting_is_requested(self):
        self.assertEqual(self._capture().get("usage"), {"include": True})

    def test_provider_defaults_to_no_fallback(self):
        self.assertEqual(self._capture().get("provider"), {"allow_fallbacks": False})

    def test_openrouter_only_fields_are_not_sent_elsewhere(self):
        """A strict OpenAI server may 400 on unknown top-level fields, and being
        unable to CALL a provider is worse than being unable to price it."""
        body = self._capture(base_url="https://api.example.com/v1")
        self.assertNotIn("usage", body)
        self.assertNotIn("provider", body)

    def test_provider_override_is_honoured(self):
        os.environ["CB_OPENROUTER_PROVIDER"] = (
            '{"order":["xai"],"allow_fallbacks":false,"quantizations":["fp8"]}')
        try:
            self.assertEqual(
                self._capture().get("provider"),
                {"order": ["xai"], "allow_fallbacks": False,
                 "quantizations": ["fp8"]})
        finally:
            os.environ.pop("CB_OPENROUTER_PROVIDER", None)

    def test_malformed_override_falls_back_rather_than_sending_garbage(self):
        """A rejected request looks like a provider outage and gets diagnosed as
        one; a typo in an env var must not cost an hour of debugging."""
        os.environ["CB_OPENROUTER_PROVIDER"] = "{not json"
        try:
            self.assertEqual(self._capture().get("provider"),
                             {"allow_fallbacks": False})
        finally:
            os.environ.pop("CB_OPENROUTER_PROVIDER", None)

    def test_served_provider_and_cost_are_recorded(self):
        out = bare_wire.openai_response_to_anthropic({
            "id": "gen-123", "model": "x-ai/grok-4.6", "provider": "xAI",
            "choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2, "cost": 0.0031},
        })
        self.assertEqual(out["provider"], "xAI")
        # generation_id is the join key to OpenRouter's own activity ledger, so a
        # published cost can be audited rather than trusted from our side.
        self.assertEqual(out["generation_id"], "gen-123")
        self.assertAlmostEqual(out["usage"]["cost_usd"], 0.0031)

    def test_absent_cost_stays_None_never_zero(self):
        """None means 'not reported'; 0.0 means 'reported as free'. Collapsing the
        two is what made an unasked-for field look like a $0 model."""
        out = bare_wire.openai_response_to_anthropic({
            "model": "m", "choices": [{"message": {"content": "x"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1}})
        self.assertIsNone(out["usage"]["cost_usd"])


if __name__ == "__main__":
    unittest.main()
