"""Model-identity guards for the ``bare`` arm.

Added 2026-08-17, before the model slate was locked. Two faults are in scope, and
only the first is detectable after the fact:

1. A pinned id that does not name one fixed model (``~`` alias, ``-latest``) or
   names a non-comparable serving variant (``:free``, ``:batch``). Refused
   pre-spend.
2. A gateway serving a DIFFERENT model than the one requested. Nothing downstream
   can detect this — the run carries our label, not the provider's — so the wire
   name is asserted on every turn.

Both were found live: the 2026-08-17 OpenRouter survey listed
``z-ai/glm-5.2:free`` beside ``z-ai/glm-5.2``, and
``~deepseek/deepseek-v4-flash-latest`` at a different price from
``deepseek/deepseek-v4-flash``.

Most of ``TestWireMatch`` is NEGATIVE — an over-strict identity check voids honest
runs, and providers legitimately answer with a more specific name than was asked.
"""

import sys
import unittest
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from adapters.bare_wire import (  # noqa: E402
    NON_COMPARABLE_VARIANTS,
    ModelIdentityError,
    ProviderHTTPError,
    validate_model_id,
    wire_model_matches,
)

#: The 2026-08-17 slate. Every id below was confirmed present in the live
#: OpenRouter catalogue WITH tool-calling support, and every one except
#: ``meta/muse-spark-1.2`` was additionally driven end-to-end through the bare loop
#: (exit 0, both files written). ``muse-spark-1.2`` returns 403 until the account
#: completes an 18+ attestation — an account setting, not a model property.
SLATE = (
    "anthropic/claude-opus-5",
    "openai/gpt-5.6-sol",
    "google/gemini-3.1-pro-preview",
    "openai/gpt-5.6-terra",
    "anthropic/claude-sonnet-5",
    "x-ai/grok-4.6",
    "qwen/qwen3.8-max",
    "meta/muse-spark-1.2",
    "google/gemini-3.6-flash",
    "deepseek/deepseek-v4-pro",
    "meta/muse-glimmer-30b",
    "z-ai/glm-5.2",
    "openai/gpt-5.6-luna",
    "google/gemma-4-31b-it",
    "deepseek/deepseek-v4-flash",
)


class TestValidateAcceptsTheRealSlate(unittest.TestCase):
    """The guard is worthless if it blocks the models we intend to run."""

    def test_every_slate_id_passes(self):
        for model in SLATE:
            with self.subTest(model=model):
                validate_model_id(model)  # must not raise

    def test_an_id_we_have_never_seen_passes(self):
        """Narrow by design: an allowlist would fail closed on every new release.

        Our Aura-side key map was 12 days stale and wrongly reported grok-4.6 and
        deepseek-v4-flash as nonexistent. A whitelist here repeats that with teeth.
        """
        for model in ("some-vendor/model-that-ships-next-week",
                      "openai/gpt-9", "z-ai/glm-6"):
            with self.subTest(model=model):
                validate_model_id(model)


class TestValidateRefusesUnciteableIds(unittest.TestCase):

    def test_alias_namespace_is_refused(self):
        with self.assertRaises(ModelIdentityError):
            validate_model_id("~deepseek/deepseek-v4-flash-latest")

    def test_rolling_alias_is_refused_even_without_the_tilde(self):
        for model in ("deepseek/deepseek-v4-flash-latest",
                      "anthropic/claude-opus:latest",
                      "vendor/latest"):
            with self.subTest(model=model):
                with self.assertRaises(ModelIdentityError):
                    validate_model_id(model)

    def test_non_comparable_serving_variants_are_refused(self):
        for model in ("z-ai/glm-5.2:free", "openai/gpt-5.6-sol:batch"):
            with self.subTest(model=model):
                with self.assertRaises(ModelIdentityError):
                    validate_model_id(model)

    def test_the_refusal_names_the_plain_id_to_use_instead(self):
        """A guard that blocks without saying what to type gets disabled."""
        with self.assertRaises(ModelIdentityError) as ctx:
            validate_model_id("z-ai/glm-5.2:free")
        self.assertIn("z-ai/glm-5.2", str(ctx.exception))

    def test_an_unknown_variant_suffix_is_ALLOWED(self):
        """Only the two suffixes that change what was served are refused.

        Routing-only suffixes (``:nitro``, ``:floor``) and capability suffixes are a
        legitimate operator choice; refusing them all would make the guard a
        catalogue we have to maintain.
        """
        for model in ("x-ai/grok-4.6:nitro", "z-ai/glm-5.2:floor"):
            with self.subTest(model=model):
                validate_model_id(model)

    def test_empty_is_refused(self):
        for model in ("", "   ", None):
            with self.subTest(model=model):
                with self.assertRaises(ModelIdentityError):
                    validate_model_id(model)

    def test_the_refused_variant_set_is_pinned(self):
        """Adding to this set stops runs; removing from it silently pools two
        different serving configs into one cell. Either way, argue for it."""
        self.assertEqual(NON_COMPARABLE_VARIANTS, frozenset({"free", "batch"}))


class TestWireMatch(unittest.TestCase):
    """Mostly negative: an over-strict check voids honest paid runs."""

    def test_exact_echo_matches(self):
        for model in SLATE:
            with self.subTest(model=model):
                self.assertTrue(wire_model_matches(model, model))

    def test_a_more_specific_dated_build_matches(self):
        """Providers answer with a dated build of the model asked for."""
        self.assertTrue(wire_model_matches(
            "openai/gpt-5.6-sol", "gpt-5.6-sol-2026-07-11"))
        self.assertTrue(wire_model_matches(
            "anthropic/claude-sonnet-5", "claude-sonnet-5-20260601"))

    def test_a_dropped_provider_prefix_matches(self):
        self.assertTrue(wire_model_matches("x-ai/grok-4.6", "grok-4.6"))

    def test_a_variant_suffix_on_either_side_matches(self):
        self.assertTrue(wire_model_matches("z-ai/glm-5.2:nitro", "z-ai/glm-5.2"))

    def test_a_substitution_to_an_unrelated_model_is_caught(self):
        """The fault this exists for: a silent gateway fallback."""
        self.assertFalse(wire_model_matches(
            "x-ai/grok-4.6", "anthropic/claude-sonnet-4-6"))
        self.assertFalse(wire_model_matches(
            "deepseek/deepseek-v4-flash", "openai/gpt-5.6-luna"))

    def test_a_silent_provider_is_UNVERIFIED_not_mismatched(self):
        """None, never False. OpenAI-compatible endpoints need not echo the field,
        and voiding an arm over that would cost real runs for no measurement gain."""
        for wire in (None, "", "   "):
            with self.subTest(wire=wire):
                self.assertIsNone(wire_model_matches("x-ai/grok-4.6", wire))

    def test_the_tier_trap_is_NOT_silently_accepted(self):
        """``-fast`` is a 2x-priced serving tier, not the model we pinned.

        Documents current behaviour: the plain core is a substring of the fast one,
        so containment ACCEPTS this direction. The pre-spend id check is not what
        stops it either — ``-fast`` is a real distinct id, not an alias. So the
        protection is the slate itself, and this test exists to make that explicit
        rather than to assert a guard we do not have.
        """
        self.assertTrue(wire_model_matches(
            "anthropic/claude-opus-5", "anthropic/claude-opus-5-fast"))
        self.assertNotIn("anthropic/claude-opus-5-fast", SLATE)


class TestItRaisesThroughTheCallPath(unittest.TestCase):

    def _payload(self, wire_model):
        return {
            "model": wire_model,
            "choices": [{"message": {"role": "assistant", "content": "hi"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2},
        }

    def _call(self, pinned, wire_model):
        from adapters.bare_wire import call_openai_compatible
        return call_openai_compatible(
            api_key="k", model=pinned, system=None,
            messages=[{"role": "user", "content": "go"}], tools=[],
            max_tokens=16, post_json=lambda *a, **k: self._payload(wire_model))

    def test_a_substitution_raises(self):
        with self.assertRaises(ModelIdentityError):
            self._call("x-ai/grok-4.6", "anthropic/claude-sonnet-4-6")

    def test_a_match_returns_normally(self):
        out = self._call("x-ai/grok-4.6", "grok-4.6")
        self.assertEqual(out["usage"]["input_tokens"], 5)

    def test_a_silent_provider_returns_normally(self):
        """Unverified must not cost a paid run."""
        out = self._call("x-ai/grok-4.6", None)
        self.assertEqual(out["usage"]["output_tokens"], 2)


class TestPreSpendGateInTheAdapter(unittest.TestCase):

    def test_a_bad_id_never_reaches_the_provider(self):
        """It must fail before the key is even resolved, let alone a token bought."""
        import tempfile
        from adapters.bare import BareAdapter

        def explode(**_kw):
            raise AssertionError("the provider was called for a refused id")

        with tempfile.TemporaryDirectory() as td:
            prompt = Path(td) / "PROMPT.md"
            prompt.write_text("do the thing", encoding="utf-8")
            adapter = BareAdapter("z-ai/glm-5.2:free", llm_call=explode)
            res = adapter.run(prompt, Path(td), max_turns=2, timeout_s=30)
        self.assertEqual(res.exit_code, 1)
        self.assertIn("glm-5.2", res.summary)
        self.assertEqual(res.tool_use_count, 0)


class TestProviderErrorsKeepTheirBody(unittest.TestCase):
    """A provider refusal must say WHY, or every 4xx costs a hand-written request.

    Added the same day the muse-spark-1.2 403 turned out to mean "confirm 18+ in
    account settings" — information the old message threw away.
    """

    def _raise(self, status, body):
        import io
        import urllib.error
        from adapters.bare_wire import _post_json
        real = urllib.request.urlopen

        def boom(*_a, **_k):
            raise urllib.error.HTTPError(
                "http://x", status, "Forbidden", {}, io.BytesIO(body.encode()))

        urllib.request.urlopen = boom
        try:
            return _post_json("http://x", {}, {}, 5.0)
        finally:
            urllib.request.urlopen = real

    def test_the_body_reaches_the_message(self):
        gated = ('{"error":{"message":"This model requires you to complete the '
                 'following before use: 18+ age confirmation."}}')
        with self.assertRaises(ProviderHTTPError) as ctx:
            self._raise(403, gated)
        self.assertIn("18+ age confirmation", str(ctx.exception))
        self.assertEqual(ctx.exception.status, 403)

    def test_an_unreadable_body_still_reports_the_status(self):
        """A body we cannot decode must not mask which error it was."""
        with self.assertRaises(ProviderHTTPError) as ctx:
            self._raise(429, "")
        self.assertIn("429", str(ctx.exception))

    def test_a_huge_body_is_bounded(self):
        """A misconfigured endpoint returning HTML must not paste a page into a
        run summary."""
        with self.assertRaises(ProviderHTTPError) as ctx:
            self._raise(500, "<html>" + "x" * 50000)
        self.assertLess(len(ctx.exception.body), 1000)

    def test_it_is_still_an_exception_the_adapter_routes_to_harness(self):
        """It must remain an Exception subclass, or bare.py's handler misses it and
        a provider refusal propagates as a crash."""
        self.assertTrue(issubclass(ProviderHTTPError, Exception))


class TestMcpLayersCanRunNonClaudeModels(unittest.TestCase):
    """The full {model} x {tool layer} cross, enabled 2026-08-17.

    Before this, ``unreal-mcp`` / ``aura-mcp`` could only run Claude: the env
    overrides that point the Claude CLI at OpenRouter were wired into the
    ``openrouter`` backend alone. That forced the tool-layer axis and the model axis
    to be separate experiments, because holding the model fixed across tool layers
    meant holding it Claude.

    The routing decision is the SLASH in the model id, so every pre-existing
    Claude slug keeps its exact old path — that is the property these tests pin.
    """

    def setUp(self):
        import os
        self._prev = os.environ.get("OPENROUTER_API_KEY")
        os.environ["OPENROUTER_API_KEY"] = "sk-or-test"

    def tearDown(self):
        import os
        if self._prev is None:
            os.environ.pop("OPENROUTER_API_KEY", None)
        else:
            os.environ["OPENROUTER_API_KEY"] = self._prev

    def _overrides(self, slug):
        from adapters.registry import make_adapter
        return getattr(make_adapter(slug), "env_overrides", None) or {}

    def test_a_claude_slug_still_goes_direct_to_anthropic(self):
        """No behaviour change without a slash. This is the regression that would
        silently re-route every historical run through a gateway."""
        for slug in ("unreal-mcp:sonnet-5", "aura-mcp:claude-sonnet-5",
                     "unreal-mcp:claude-sonnet-4-5-20250929", "claude-p:sonnet-5"):
            with self.subTest(slug=slug):
                self.assertEqual(self._overrides(slug), {})

    def test_an_openrouter_slug_routes_through_the_gateway(self):
        for slug in ("unreal-mcp:deepseek/deepseek-v4-flash",
                     "aura-mcp:x-ai/grok-4.6",
                     "unreal-mcp:meta/muse-glimmer-30b"):
            with self.subTest(slug=slug):
                ov = self._overrides(slug)
                self.assertEqual(ov.get("ANTHROPIC_BASE_URL"),
                                 "https://openrouter.ai/api")
                self.assertEqual(ov.get("ANTHROPIC_AUTH_TOKEN"), "sk-or-test")
                # Blanked deliberately: OpenRouter ignores x-api-key and a stray
                # logged-in value 401s the subprocess.
                self.assertEqual(ov.get("ANTHROPIC_API_KEY"), "")

    def test_all_three_openrouter_backends_share_ONE_transport(self):
        """If these drift, the tool-layer arms differ in auth as well as tools —
        and the comparison's whole premise is that transport is the constant."""
        a = self._overrides("openrouter:deepseek/deepseek-v4-flash")
        b = self._overrides("unreal-mcp:deepseek/deepseek-v4-flash")
        c = self._overrides("aura-mcp:deepseek/deepseek-v4-flash")
        self.assertEqual(a, b)
        self.assertEqual(b, c)

    def test_the_id_guard_applies_on_the_new_route_too(self):
        """A guard wired on one backend and forgotten on another is not a guard."""
        for slug in ("unreal-mcp:z-ai/glm-5.2:free",
                     "aura-mcp:~deepseek/deepseek-v4-flash-latest",
                     "openrouter:z-ai/glm-5.2:batch"):
            with self.subTest(slug=slug):
                with self.assertRaises(ModelIdentityError):
                    self._overrides(slug)

    def test_a_missing_key_fails_loud_on_the_new_route(self):
        """Silently falling back to Anthropic would bill the wrong account and
        label the run with a model that never ran."""
        import os
        os.environ.pop("OPENROUTER_API_KEY", None)
        with self.assertRaises(ValueError):
            self._overrides("unreal-mcp:deepseek/deepseek-v4-flash")

    def test_a_missing_key_does_NOT_break_the_claude_route(self):
        """An unset OpenRouter key must not stop a plain Claude run."""
        import os
        os.environ.pop("OPENROUTER_API_KEY", None)
        self.assertEqual(self._overrides("unreal-mcp:sonnet-5"), {})


if __name__ == "__main__":
    unittest.main()
