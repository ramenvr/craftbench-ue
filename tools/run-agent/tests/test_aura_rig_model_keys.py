"""Unit tests for aura_rig.model_keys — KEY<->wire map + cost helper. Fully offline."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aura_rig import model_keys  # noqa: E402


class TestKeyToWire(unittest.TestCase):
    def test_known_key_resolves(self):
        self.assertEqual(model_keys.wire_model_for_key("sonnet-4.6"), "claude-sonnet-4-6")
        self.assertEqual(model_keys.expected_wire_for_key("sonnet-4.6"), "claude-sonnet-4-6")

    def test_unknown_key_returns_verbatim_not_fallback(self):
        # An unknown key returns itself (callers detect via is_known_key), NOT
        # the silent fallback model — the wire model is OBSERVED, not predicted.
        self.assertEqual(model_keys.wire_model_for_key("claude-sonnet-4-6"),
                         "claude-sonnet-4-6")
        self.assertFalse(model_keys.is_known_key("claude-sonnet-4-6"))
        self.assertTrue(model_keys.is_known_key("sonnet-4.6"))

    def test_fallback_constant_present(self):
        # 2026-08-05 sync: a BARE unknown key falls back to the hard
        # fallbackModelKey 'sonnet-4.6' (getModel.ts:172/:262), NOT the
        # default model (DEFAULT_MODEL 'anthropic/opus-5' is only the
        # unknown-slash-form fallback).
        self.assertEqual(model_keys.FALLBACK_WIRE, "claude-sonnet-4-6")

    def test_opus5_seeded_key_resolves_and_prices(self):
        # 2026-08-05 sync: opus-5 IS seeded upstream (0050: model_name
        # claude-opus-5; 0049: $5/$25/$0.5/$10, same as opus-4.8).
        self.assertEqual(model_keys.wire_model_for_key("opus-5"), "claude-opus-5")
        self.assertTrue(model_keys.is_known_key("opus-5"))
        self.assertAlmostEqual(
            model_keys.cost_usd("claude-opus-5", 1_000_000, 1_000_000), 30.0)

    def test_new_provider_keys_resolve(self):
        # 2026-07-02 sync: keys copied verbatim from SHARED.ts (case included).
        self.assertEqual(model_keys.wire_model_for_key("fable-5"), "claude-fable-5")
        self.assertEqual(model_keys.wire_model_for_key("GPT-5.1"), "gpt-5.1-2025-11-13")
        self.assertEqual(model_keys.wire_model_for_key("gemini-3.1-pro-preview"),
                         "gemini-3.1-pro-preview")
        self.assertEqual(model_keys.wire_model_for_key("deepseek-v4-pro"),
                         "deepseek/deepseek-v4-pro")
        self.assertEqual(model_keys.wire_model_for_key("glm-5.2"), "z-ai/glm-5.2")
        for k in ("fable-5", "GPT-5.1", "GPT-5.2", "GPT-5.4", "GPT-5.5",
                  "gemini-3-pro-preview", "gemini-3.1-pro-preview",
                  "deepseek-v4-pro", "glm-5.2"):
            self.assertTrue(model_keys.is_known_key(k), k)

    def test_every_wire_model_is_priced(self):
        # Parity invariant: every KEY_TO_WIRE wire id has a WIRE_PRICING row,
        # so cost_usd never returns None for a pinnable model.
        for key, wire in model_keys.KEY_TO_WIRE.items():
            self.assertIn(wire, model_keys.WIRE_PRICING, f"{key} -> {wire}")


class TestDetectWireMismatch(unittest.TestCase):
    def test_match_returns_none(self):
        self.assertIsNone(model_keys.detect_wire_mismatch("sonnet-4.6", {"claude-sonnet-4-6": 5}))
        self.assertIsNone(model_keys.detect_wire_mismatch("sonnet-4.6", "claude-sonnet-4-6"))
        self.assertIsNone(model_keys.detect_wire_mismatch("sonnet-4.6", ["claude-sonnet-4-6"]))

    def test_empty_observed_is_no_mismatch(self):
        self.assertIsNone(model_keys.detect_wire_mismatch("sonnet-4.6", {}))
        self.assertIsNone(model_keys.detect_wire_mismatch("sonnet-4.6", None))

    def test_silent_fallback_is_flagged(self):
        # Requesting a modelName (unknown key) -> the sonnet-4.6 fallback on
        # the wire (getModel.ts:262).
        m = model_keys.detect_wire_mismatch("claude-opus-4-8", {"claude-sonnet-4-6": 3})
        self.assertIsNotNone(m)
        self.assertEqual(m["expected_wire"], "claude-opus-4-8")
        self.assertEqual(m["on_wire"], ["claude-sonnet-4-6"])
        self.assertFalse(m["is_known_key"])

    def test_real_drift_flagged_for_known_key(self):
        m = model_keys.detect_wire_mismatch("sonnet-4.6", {"claude-opus-4-8": 2})
        self.assertIsNotNone(m)
        self.assertTrue(m["is_known_key"])


class TestCost(unittest.TestCase):
    def test_sonnet_cost(self):
        # 1M in @ $3, 1M out @ $15.
        self.assertAlmostEqual(
            model_keys.cost_usd("claude-sonnet-4-6", 1_000_000, 1_000_000), 18.0)

    def test_cache_priced(self):
        c = model_keys.cost_usd("claude-sonnet-4-6", 0, 0, cache_read=1_000_000,
                                cache_write=1_000_000)
        self.assertAlmostEqual(c, 0.3 + 6.0)

    def test_unpriced_model_is_none_not_zero(self):
        self.assertIsNone(model_keys.cost_usd("some-unknown-model", 1_000_000))

    def test_new_rows_priced(self):
        # 2026-07-02 sync: fable-5 (anthropic) + glm-5.2 (openrouter) rows.
        self.assertAlmostEqual(
            model_keys.cost_usd("claude-fable-5", 1_000_000, 1_000_000), 60.0)
        self.assertAlmostEqual(
            model_keys.cost_usd("z-ai/glm-5.2", 1_000_000, 1_000_000,
                                cache_read=1_000_000, cache_write=1_000_000),
            1.40 + 4.40 + 0.26 + 1.40)

    def test_glm_5_3_is_priced_but_is_NOT_an_aura_key(self):
        """The 2026-08-18 bump, and the half of it that must NOT happen.

        glm-5.3 is live on OpenRouter, so the bare/openrouter lane can pin it and
        needs a price. Aura's catalogue has no such key, and an unknown BARE key
        on /api/chat resolves to FALLBACK_WIRE — so declaring it "known" here
        would let a run be labelled GLM while sonnet-4.6 was served and billed.
        Both halves are asserted together because the temptation is to bump them
        together.
        """
        self.assertAlmostEqual(
            model_keys.cost_usd("z-ai/glm-5.3", 1_000_000, 1_000_000,
                                cache_read=1_000_000, cache_write=1_000_000),
            1.40 + 4.40 + 0.26)  # OpenRouter charges no separate cache write
        self.assertFalse(model_keys.is_known_key("glm-5.3"))
        self.assertTrue(model_keys.is_known_key("glm-5.2"))

    def test_cost_for_usage_aggregate(self):
        usage = {"input_tokens": 1_000_000, "output_tokens": 0,
                 "cache_read": 0, "cache_write": 0,
                 "models": {"claude-sonnet-4-6": 4}}
        self.assertAlmostEqual(model_keys.cost_usd_for_usage(usage), 3.0)

    def test_cost_for_usage_no_models_is_none(self):
        self.assertIsNone(model_keys.cost_usd_for_usage({"models": {}}))

    def test_cost_for_usage_all_unpriced_is_none(self):
        usage = {"input_tokens": 1_000_000, "models": {"mystery": 1}}
        self.assertIsNone(model_keys.cost_usd_for_usage(usage))


if __name__ == "__main__":
    unittest.main()
