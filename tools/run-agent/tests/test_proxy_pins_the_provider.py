"""One arm must be one deployment, and until 2026-08-26 it was not.

`CB_OPENROUTER_PROVIDER` existed and was read by exactly one caller --
`adapters.bare_wire`, i.e. the `bare:` lane. The lanes actually being benchmarked
(`unreal-mcp`, `aura-mcp`) reach OpenRouter through the Claude Code CLI and
`openrouter_env_overrides`, which never set one. They ran unpinned for a whole
block, and the proxy usage log recorded the result:

    deepseek/deepseek-v4-pro-0813 -> DeepSeek 273, Alibaba 3, Sail Research 1,
                                     Cloudflare 1, Together 1, Fireworks 1

Six vendors served one "model" arm. `bare_wire` already states why that matters
and it is not the money: "a panel that pins a model but not the machine serving
it silently compares different systems."

The knob-with-no-consumer is this repo's recurring defect, so these tests hold
the WIRING as much as the behaviour.

Stdlib only. No socket, no key, no tokens.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from aura_rig import proxy  # noqa: E402


def _body(**extra) -> bytes:
    b = {"model": "deepseek/deepseek-v4-pro-0813", "max_tokens": 16,
         "messages": [{"role": "user", "content": "hi"}]}
    b.update(extra)
    return json.dumps(b).encode()


class TestTheBlockIsAdded(unittest.TestCase):
    def test_default_forbids_fallback_for_every_model(self):
        # Same floor as the bare lane: an unpinned request is the defect.
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CB_OPENROUTER_PROVIDER", None)
            os.environ.pop("CB_PROXY_PROVIDER_ORDER", None)
            for m in ("x-ai/grok-4.6", "openai/gpt-5.6-sol"):
                out = json.loads(proxy.inject_provider_routing(
                    json.dumps({"model": m, "messages": []}).encode()))
                self.assertIs(False, out["provider"]["allow_fallbacks"], m)

    def test_deepseek_also_carries_an_ORDER_because_seven_vendors_served_it(self):
        # allow_fallbacks alone forbids switching AFTER selection; it does not
        # say which endpoint to select. Block 1 measured the consequence: the
        # deepseek arm was served by seven vendors, DeepSeek at 1.8% cache and
        # $40.80 against Alibaba at 97.2% and $2.54 -- not one arm, and not one
        # price.
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CB_OPENROUTER_PROVIDER", None)
            os.environ.pop("CB_PROXY_PROVIDER_ORDER", None)
            out = json.loads(proxy.inject_provider_routing(_body()))
        self.assertEqual(["DeepSeek"], out["provider"]["order"])
        self.assertIs(False, out["provider"]["allow_fallbacks"])

    def test_the_order_map_is_overridable_per_model(self):
        pin = {"deepseek/deepseek-v4-pro-0813": ["Alibaba"]}
        with mock.patch.dict(os.environ,
                             {"CB_PROXY_PROVIDER_ORDER": json.dumps(pin)}):
            os.environ.pop("CB_OPENROUTER_PROVIDER", None)
            out = json.loads(proxy.inject_provider_routing(_body()))
        self.assertEqual(["Alibaba"], out["provider"]["order"])

    def test_the_rest_of_the_body_is_untouched(self):
        out = json.loads(proxy.inject_provider_routing(_body()))
        self.assertEqual("deepseek/deepseek-v4-pro-0813", out["model"])
        self.assertEqual(16, out["max_tokens"])
        self.assertEqual([{"role": "user", "content": "hi"}], out["messages"])

    def test_an_env_override_is_used_verbatim(self):
        pin = {"order": ["DeepSeek"], "allow_fallbacks": False,
               "quantizations": ["fp8", "bf16"]}
        with mock.patch.dict(os.environ,
                             {"CB_OPENROUTER_PROVIDER": json.dumps(pin)}):
            out = json.loads(proxy.inject_provider_routing(_body()))
        self.assertEqual(pin, out["provider"])


class TestItNeverMakesThingsWorse(unittest.TestCase):
    """Every branch here forwards the request rather than mangling it. A
    diagnostic that breaks a live request costs more than the thing it measures."""

    def test_a_client_set_provider_is_not_overwritten(self):
        mine = {"order": ["xAI"]}
        out = json.loads(proxy.inject_provider_routing(_body(provider=mine)))
        self.assertEqual(mine, out["provider"])

    def test_a_non_json_body_is_returned_unchanged(self):
        raw = b"not json at all"
        self.assertEqual(raw, proxy.inject_provider_routing(raw))

    def test_an_empty_body_is_returned_unchanged(self):
        self.assertEqual(b"", proxy.inject_provider_routing(b""))

    def test_a_json_array_body_is_returned_unchanged(self):
        raw = b'[1, 2, 3]'
        self.assertEqual(raw, proxy.inject_provider_routing(raw))

    def test_malformed_env_falls_back_instead_of_sending_garbage(self):
        # A rejected request looks like a provider outage; the wrong pin would be
        # diagnosed for an hour before anyone suspected the env var.
        for bad in ("{not json", '["a","list"]', '"a string"'):
            with mock.patch.dict(os.environ, {"CB_OPENROUTER_PROVIDER": bad}):
                out = json.loads(proxy.inject_provider_routing(_body()))
            self.assertEqual({"allow_fallbacks": False}, out["provider"], bad)


class TestItIsActuallyWired(unittest.TestCase):
    """The knob-with-no-consumer is the defect this replaces. These read the
    call site, because a correct function nothing calls is what we already had."""

    def test_the_proxy_calls_it_on_outbound_messages(self):
        src = (_ROOT / "aura_rig" / "proxy.py").read_text(encoding="utf-8")
        self.assertIn("body = inject_provider_routing(body)", src)

    def test_it_is_gated_on_the_openrouter_upstream_only(self):
        # The block is meaningless to api.anthropic.com and would be a stray
        # field there. "/api" is exactly OpenRouter's Anthropic skin.
        src = (_ROOT / "aura_rig" / "proxy.py").read_text(encoding="utf-8")
        self.assertIn('up.path_prefix == "/api"', src)

    def test_it_matches_the_query_string_the_cli_actually_posts(self):
        # The live CLI posts to "/v1/messages?beta=true". An endswith test on the
        # raw path never matches it -- that exact bug made CB_PROXY_INJECT_CACHE a
        # silent no-op for 2,741 requests, so the split is load-bearing here too.
        src = (_ROOT / "aura_rig" / "proxy.py").read_text(encoding="utf-8")
        i = src.index("inject_provider_routing(body)")
        window = src[max(0, i - 400):i]
        self.assertIn('self.path.split("?", 1)[0].endswith("/messages")', window)

    def test_it_is_on_by_default(self):
        # Unlike CB_PROXY_INJECT_CACHE, which MODELS a hypothetical cost and must
        # not touch the primary number, this removes a source of invalidity.
        src = (_ROOT / "aura_rig" / "proxy.py").read_text(encoding="utf-8")
        self.assertIn('os.environ.get("CB_PROXY_PIN_PROVIDER", "1")', src)

    def test_one_knob_one_meaning(self):
        # Same env var as the bare lane, so the two lanes cannot drift into
        # pinning differently -- which a tool-layer comparison cannot survive.
        from adapters import bare_wire
        self.assertIn("CB_OPENROUTER_PROVIDER",
                      Path(bare_wire.__file__).read_text(encoding="utf-8"))
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CB_OPENROUTER_PROVIDER", None)
            self.assertEqual(bare_wire._provider_routing(),
                             proxy._provider_routing())


if __name__ == "__main__":
    unittest.main()
