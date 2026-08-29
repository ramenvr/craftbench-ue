"""Aura model-KEY <-> on-wire modelName map + a token-cost helper.

Why this module exists
----------------------
The local Aura ``:41200/api/chat`` ``model`` field expects the Aura **KEY**
(e.g. ``sonnet-4.6``), **NOT** the provider **modelName** (``claude-sonnet-4-6``).
Sending an unknown string (like the modelName) does NOT error — it **silently
falls back**: a BARE unknown key resolves to the hard ``fallbackModelKey``
``sonnet-4.6`` (getModel.ts:172/:262 — served AND billed as sonnet-4.6), and
only an unknown ``provider/key`` form tries ``DEFAULT_MODEL``
(``anthropic/opus-5``) first. So the rig always:

  * pins by KEY when POSTing /api/chat, and
  * asserts the on-wire ``modelName`` via the :41299 logging proxy.

``KEY_TO_WIRE`` is the join between those two namespaces (source of truth:
Aura's published key list / Aura ``SHARED.ts``). ``cost_usd`` turns proxy
token counts into a USD estimate via ``WIRE_PRICING`` (from Aura's
``model-pricing.ts``). Pure data + pure functions — no I/O, fully unit-testable.

Re-check Aura's published key list after an Aura update; keys/defaults change.
Last synced: 2026-08-05 against aura-plugin origin/main @ 3a2112ac9 (plugin
0.15.5). The 4 commits since the prior audit point (27c9f6d82..3a2112ac9:
livecoding log-parse refactor, python lint/wrap move, summarize prompt,
FullBuild.ps1 line endings) touch ZERO model-layer files — getModel.ts,
modelCatalog.ts, SHARED.ts, the migrations and the picker are all last
touched 1299c01ea (2026-07-30). Seed still ends at
0051_opus_5_bedrock_and_default.sql; DEFAULT_MODEL = 'anthropic/opus-5'.
(Prior sync 2026-07-27 @ 4ff4bbc45 closed the ``grok-4.5`` mirror gap.)

``opus-5`` — CORRECTED 2026-08-03, row added 2026-08-05: earlier docstrings
called it runtime-DB-only with an unobservable wire name. Wrong on both
counts. It is seeded by 0050_seed_opus_5_model.sql (key ``opus-5``,
``model_name = claude-opus-5``, adaptiveThinking+fast) and priced by
0049_opus_5_operations.sql ($5/$25/$0.5/$10 — same as opus-4.8), so it now
has real KEY_TO_WIRE/WIRE_PRICING rows below. ``opus-5-fast`` ($10/$50, a
genuine 2x premium) is a BILLING key only — no ``models`` row, never
pinnable, so it deliberately gets no row here.

RUNTIME-ONLY KEY, still (re-verified 2026-08-05 at 3a2112ac9):
``gpt-5.6-luna`` — pins and attributes on the product path (daily-report
first outings) but has zero repo presence even at origin/main tip (only
``gpt-5.6-sol`` is seeded/priced upstream); runtime-DB row only, so no
KEY_TO_WIRE/WIRE_PRICING row — do NOT invent one. Note it also does NOT match
the Fable/Sol entitlement substring gate (SHARED.ts:161 tests
``includes('fable') || includes('gpt-5.6-sol')``). The 2026-07-22 note
stands: the static SHARED.ts model list is gone — compare against the backend
models source (vercelServer DB seed / models endpoint / getModel.ts).
Watch-item from 07-24 stands: Anthropic-via-Bedrock routing is flag-gated
server-side (AUR-163 #2898/#2899); if active, on-wire ids report as
``global.anthropic.*`` (getModel.ts anthropicToBedrockModelId — the earlier
``us.anthropic.*`` spelling is gone) and the proxy wire-assert /
model_mismatch flag will fire.
"""
from __future__ import annotations

from typing import Dict, Mapping, Optional

# Aura model KEY (the /api/chat `model` field) -> on-wire modelName (the
# ModelProviders `modelName`; for anthropic models that is what
# message_start.model reports on the wire). Keys are copied VERBATIM from
# SHARED.ts (case included — `GPT-5.1`, not `gpt-5.1`), grouped and ordered as
# SHARED.ts groups them.
KEY_TO_WIRE: Dict[str, str] = {
    # anthropic
    "sonnet-5": "claude-sonnet-5",
    "sonnet-4.6": "claude-sonnet-4-6",
    "sonnet-4.5": "claude-sonnet-4-5-20250929",
    "opus-4.5": "claude-opus-4-5-20251101",
    "opus-4.6": "claude-opus-4-6",
    "opus-4.7": "claude-opus-4-7",
    "opus-4.8": "claude-opus-4-8",
    "opus-5": "claude-opus-5",  # seed 0050 (the DEFAULT_MODEL since 0051-era)
    "fable-5": "claude-fable-5",
    "haiku-4.5": "claude-haiku-4-5-20251001",
    # openai
    "GPT-5.1": "gpt-5.1-2025-11-13",
    "GPT-5.2": "gpt-5.2",
    "GPT-5.4": "gpt-5.4",
    "GPT-5.5": "gpt-5.5",
    "gpt-5.6-sol": "gpt-5.6-sol",  # lowercase key on purpose (SHARED.ts billing row)
    # google
    "gemini-3-pro-preview": "gemini-3-pro-preview",
    "gemini-3.1-pro-preview": "gemini-3.1-pro-preview",
    # openrouter
    "deepseek-v4-pro": "deepseek/deepseek-v4-pro",
    # NOT bumped to 5.3 with the pricing row below, deliberately: this map
    # mirrors Aura's SHARED.ts, and Aura ships no glm-5.3 key (checked
    # 2026-08-18 against the aura-plugin checkout: seed 0046, SHARED.ts and
    # modelCatalogFixture are all 5.2). Adding it here would make
    # is_known_key("glm-5.3") report True while /api/chat silently resolves
    # the unknown bare key to FALLBACK_WIRE — a run labelled GLM, served and
    # billed as sonnet-4.6. Bump only when sync-aura shows the key upstream.
    "glm-5.2": "z-ai/glm-5.2",
    "grok-4.5": "x-ai/grok-4.5",
}

# The model an unknown KEY silently falls back to on /api/chat. Since the
# DB-catalog era this is NOT the default model: a BARE unknown key resolves to
# the hard fallbackModelKey 'sonnet-4.6' (getModel.ts:172/:262; asserted by
# upstream getModelKeyBilling.test.ts — 'totally-made-up-model' → 'sonnet-4.6',
# served AND billed as such), while an unknown 'provider/key' form resolves to
# DEFAULT_MODEL ('anthropic/opus-5') first. The rig pins bare keys, so the
# bare-key branch is the one this constant mirrors. Surfaced so the adapter can
# explain a wire-model mismatch.
FALLBACK_WIRE = "claude-sonnet-4-6"

# USD per 1M tokens (input, output, cache_read, cache_write) keyed by on-wire
# modelName. From Aura's src/lib/pricing/model-pricing.ts — each model's own
# provider row (rows keyed there by the Aura KEY are stored HERE under the
# wire modelName KEY_TO_WIRE maps that key to).
WIRE_PRICING: Dict[str, tuple] = {
    # anthropic
    "claude-sonnet-5": (2.0, 10.0, 0.2, 4.0),
    "claude-sonnet-4-6": (3.0, 15.0, 0.3, 6.0),
    "claude-sonnet-4-5-20250929": (3.0, 15.0, 0.3, 6.0),
    "claude-opus-4-5-20251101": (5.0, 25.0, 0.5, 10.0),
    "claude-opus-4-6": (5.0, 25.0, 0.5, 10.0),
    "claude-opus-4-7": (5.0, 25.0, 0.5, 10.0),
    "claude-opus-4-8": (5.0, 25.0, 0.5, 10.0),
    # operation row 0049_opus_5_operations.sql; the 2x fast tier ('opus-5-fast',
    # $10/$50) is a billing-only key with no models row — not pinnable, no row.
    "claude-opus-5": (5.0, 25.0, 0.5, 10.0),
    "claude-fable-5": (10.0, 50.0, 1.0, 20.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0, 0.1, 2.0),
    # openai (no cache-write price upstream -> 0.0)
    "gpt-5.1-2025-11-13": (1.25, 10.0, 0.175, 0.0),
    "gpt-5.2": (1.75, 14.0, 0.175, 0.0),
    "gpt-5.4": (2.5, 15.0, 0.25, 0.0),
    "gpt-5.5": (5.0, 30.0, 0.5, 0.0),
    "gpt-5.6-sol": (5.0, 30.0, 0.5, 6.25),  # HAS a cacheWrite price upstream (unlike the rows above)
    # google
    "gemini-3-pro-preview": (2.0, 12.0, 0.2, 4.5),
    "gemini-3.1-pro-preview": (2.0, 12.0, 0.2, 4.5),
    # openrouter
    "deepseek/deepseek-v4-pro": (0.435, 0.87, 0.003625, 0.435),
    "z-ai/glm-5.2": (1.40, 4.40, 0.26, 1.40),
    # glm-5.3 (2026-08-18). PROVENANCE DIFFERS from the row above and that
    # matters: the 5.2 row is Aura's model-pricing.ts (what Aura bills us),
    # while 5.3 is not in Aura's catalogue at all yet, so this row is
    # OpenRouter's own list price — the only lane that can currently run it.
    # OpenRouter publishes NO separate cache-write charge for any z-ai row
    # (including 5.2, which Aura nonetheless bills at 1.40), hence 0.0 here
    # by the same convention as the grok/openai rows. The 5.2 row is KEPT:
    # deleting it would silently turn every already-graded glm run's cost
    # into None rather than recomputing it.
    "z-ai/glm-5.3": (1.40, 4.40, 0.26, 0.0),
    # operation row 0041_grok_4_5_operation.sql (no explicit cache-write charge)
    "x-ai/grok-4.5": (2.0, 6.0, 0.5, 0.0),
}


def wire_model_for_key(key: str) -> str:
    """Map an Aura KEY to its on-wire modelName.

    An unknown key returns the key verbatim (NOT the fallback) so callers can
    detect "this isn't a known key" distinctly from "this key fell back". The
    actual on-wire model for an unknown key is observed via the proxy, not
    predicted here.
    """
    return KEY_TO_WIRE.get(key, key)


def expected_wire_for_key(key: str) -> str:
    """What modelName a correctly-resolved KEY should put on the wire.

    Same as ``wire_model_for_key`` but spelled out for the mismatch check: the
    adapter compares this against the proxy's observed on-wire model(s).
    """
    return KEY_TO_WIRE.get(key, key)


def is_known_key(key: str) -> bool:
    """True iff ``key`` is a recognised Aura model KEY (won't silently fall back)."""
    return key in KEY_TO_WIRE


def detect_wire_mismatch(key: str, on_wire) -> Optional[dict]:
    """Compare requested KEY's expected wire model against the observed set.

    ``on_wire`` may be a single modelName, an iterable of modelNames, or a
    mapping modelName->count (the shape the proxy aggregator emits). Returns
    None when every observed model equals the expected wire model (or when
    nothing was observed); otherwise a dict describing the drift.

    Sub-agent calls run on a DIFFERENT model than the main loop, so the caller
    should pass only the MAIN-loop model set here (the driver isolates that);
    passing a mixed set will (correctly) flag a "mismatch" that is really a
    sub-agent — which is why the driver separates the two before calling this.
    """
    expected = expected_wire_for_key(key)
    if isinstance(on_wire, Mapping):
        observed = set(on_wire.keys())
    elif isinstance(on_wire, str):
        observed = {on_wire}
    elif on_wire is None:
        observed = set()
    else:
        observed = set(on_wire)
    observed.discard(None)
    if not observed or observed == {expected}:
        return None
    return {
        "requested_key": key,
        "expected_wire": expected,
        "on_wire": sorted(observed),
        "is_known_key": is_known_key(key),
    }


def cost_usd(
    wire_model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read: int = 0,
    cache_write: int = 0,
) -> Optional[float]:
    """USD cost of one model's token usage. None if the model has no price row.

    Returns None (not 0.0) for an unpriced model so callers never report a
    fabricated $0 for a model we simply don't have pricing for.
    """
    price = WIRE_PRICING.get(wire_model)
    if price is None:
        return None
    pi, po, pcr, pcw = price
    return (
        input_tokens / 1e6 * pi
        + output_tokens / 1e6 * po
        + cache_read / 1e6 * pcr
        + cache_write / 1e6 * pcw
    )


def cost_usd_for_usage(usage: Mapping) -> Optional[float]:
    """Total USD across every model in a proxy-aggregate usage record.

    ``usage`` has the shape produced by ``proxy.usage_since``:
      {input_tokens, output_tokens, cache_read, cache_write, models:{m:count}}.
    The token totals are shared across all models in the window (the proxy
    aggregates them), so we price the totals once per distinct observed model
    that HAS a price row — matching tools/run-agent legacy render behaviour.
    Returns None only when NO observed model is priced (else the priced sum).
    """
    models = usage.get("models") or {}
    if not models:
        return None
    total = 0.0
    priced_any = False
    for m in models:
        c = cost_usd(
            m,
            usage.get("input_tokens", 0) or 0,
            usage.get("output_tokens", 0) or 0,
            usage.get("cache_read", 0) or 0,
            usage.get("cache_write", 0) or 0,
        )
        if c is not None:
            total += c
            priced_any = True
    return total if priced_any else None
