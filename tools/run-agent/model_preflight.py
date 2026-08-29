"""Refuse to pin a model id the catalogue already says will misbehave.

Born from qwen/qwen3.8-max, which ran a whole 60-cell sweep at ~3.6x the next
model's cost and ~66% of total spend. The cause was not the model: its route
never caches the growing conversation, so ~10.5M input tokens per cell were
billed fresh where every other panel member paid a tenth of that on 92-98% cache
hits. All of it was visible in the catalogue BEFORE the first cell, for free.

WHAT THE CATALOGUE EXPOSES, and the discriminator that matters:

  * ``pricing.input_cache_write`` ABSENT  -> the provider bills nothing to create
    a cache, i.e. it caches prefixes automatically. Measured on this harness:
    deepseek-v4-pro-0813 (14 endpoints) and grok-4.6 (4) have no write price and
    recorded cache_creation == 0 at 87-99% hit. They need nothing from us.
  * ``pricing.input_cache_write`` PRESENT -> explicit-breakpoint economics: the
    caller must place cache markers or nothing is cached.
  * ``supports_implicit_caching`` (endpoints endpoint ONLY, absent from /models)
    -> whether there is an automatic fallback when markers are missing or wrong.

The fatal combination is BOTH: write-priced AND no implicit fallback. That is
qwen3.8-max exactly, and it is the only panel model in that class. gemini-3.7-flash
is write-priced but implicit-TRUE, which is why it measured fine.

SERVING VARIANTS, and why this cannot be a string rule. ``openai/gpt-5.6-sol-pro``
is "the same underlying model as GPT-5.6 Sol, served with reasoning.mode set to
pro" -- same price, same created date. Pooling it with the base id would silently
mix two serving configs. But a ``-pro`` SUFFIX rule would be wrong: 15 catalogue
ids end in ``-pro`` and 12 name genuinely distinct tiers (google/gemini-2.5-pro,
openai/gpt-5-pro, openai/o1-pro, deepseek/deepseek-v4-pro, perplexity/sonar-pro).
So variant-ness is decided from the CATALOGUE -- base id exists, identical price,
identical created date -- never from the name.

Usage:
    py -3 model_preflight.py <model-id> [<model-id> ...]
    py -3 model_preflight.py --panel          # the pre-registered panel

Exit 0 = every id is fit to pin, 1 = at least one FAIL, 2 = could not check.
Needs no key for the public catalogue; sends OPENROUTER_API_KEY if one is set.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

CATALOG = "https://openrouter.ai/api/v1/models"
ENDPOINTS = "https://openrouter.ai/api/v1/models/{ident}/endpoints"
#: the cost rule.
PANEL = ("anthropic/claude-sonnet-5", "deepseek/deepseek-v4-pro-0813",
         "x-ai/grok-4.6", "google/gemini-3.7-flash")
#: A pinned id older than this is worth a second look: section 5's freshness rule
#: rejected google/gemini-3.1-pro-preview at 181 days. Advisory, never a FAIL --
#: "old" is a judgement about the field, not a property of the id.
STALE_DAYS = 120


def _get(url: str):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _price(d, key):
    """A price field as float, or None when the provider does not bill it."""
    v = (d or {}).get(key)
    if v in (None, "", "0", 0):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f or None


def check(ident: str, catalog: dict) -> tuple[list[str], list[str]]:
    """(fails, notes) for one id."""
    fails: list[str] = []
    notes: list[str] = []
    entry = catalog.get(ident)
    if entry is None:
        near = sorted(k for k in catalog if ident.split("/")[-1][:12] in k)[:6]
        fails.append(f"not in the catalogue ({len(catalog)} ids)"
                     + (f"; nearest: {', '.join(near)}" if near else ""))
        return fails, notes

    pr = entry.get("pricing") or {}
    p_in, p_out = _price(pr, "prompt"), _price(pr, "completion")
    c_read, c_write = _price(pr, "input_cache_read"), _price(pr, "input_cache_write")
    created = entry.get("created")
    notes.append(f"in ${(p_in or 0) * 1e6:.2f}/M  out ${(p_out or 0) * 1e6:.2f}/M"
                 + (f"  cache_read ${c_read * 1e6:.2f}/M" if c_read else "")
                 + (f"  cache_write ${c_write * 1e6:.2f}/M" if c_write else
                    "  cache_write NOT BILLED (automatic caching)"))

    # --- the fatal combination -------------------------------------------
    implicit = None
    try:
        eps = (_get(ENDPOINTS.format(ident=ident)).get("data") or {}).get("endpoints") or []
    except (urllib.error.URLError, OSError, ValueError) as exc:
        notes.append(f"could not read endpoints ({type(exc).__name__}); "
                     "implicit-cache support UNKNOWN")
        eps = []
    if eps:
        flags = {bool(e.get("supports_implicit_caching")) for e in eps}
        implicit = all(flags) if flags else None
        provs = sorted({str(e.get("provider_name")) for e in eps})
        notes.append(f"{len(eps)} endpoint(s): {', '.join(provs)}"
                     + f"  implicit_caching={implicit}")
        if len(eps) == 1:
            notes.append("single endpoint: provider routing cannot rescue a bad "
                         "cache story here")
    if c_write and implicit is False:
        # WARN, NOT FAIL -- and that distinction was measured, not assumed. This
        # is qwen/qwen3.8-max's signature (write-priced, no implicit fallback,
        # ~3.6x the next model's cost per cell in the 2026-08 sweep), so the
        # first cut of this check FAILED on it. But openai/gpt-5.6-sol carries the
        # SAME signature and a live 4-round probe showed it caching and growing
        # normally with 19 tools present -- so the field predicts "you must place
        # markers", NOT "markers will not work". Failing here would have blocked a
        # good model. The only thing that settles it is a live probe against
        # the candidate: 4 requests with tools present, a few cents.
        notes.append(
            "NEEDS EXPLICIT MARKERS and has no implicit fallback -- qwen's "
            "signature. Not disqualifying on its own (gpt-5.6-sol shares it and "
            "caches fine), but PROBE IT before pinning: 4 requests, pennies. A "
            "model in this class that does not cache costs ~3.6x per cell.")
    elif c_write and implicit is None:
        notes.append("write-priced and implicit support unknown -- verify before "
                     "pinning, this is the class the qwen incident came from")
    elif c_write:
        notes.append("write-priced but implicit caching is on: markers help, "
                     "their absence is not fatal (gemini-3.7-flash's class)")

    # --- serving variant of an id we may already run ----------------------
    for sep in ("-pro", "-mini", "-fast", "-thinking"):
        if not ident.endswith(sep):
            continue
        base = ident[: -len(sep)]
        b = catalog.get(base)
        if b is None:
            notes.append(f"ends in {sep!r} but {base!r} is not in the catalogue, "
                         "so this is a distinct model, not a serving variant")
            continue
        same_price = (_price(b.get("pricing"), "prompt") == p_in
                      and _price(b.get("pricing"), "completion") == p_out)
        if same_price and b.get("created") == created:
            fails.append(
                f"SERVING VARIANT of {base!r}: identical price and created date, "
                "so it is the same model served differently. Never pool the two "
                "in one arm -- pin the base, or report this as its own arm")
        else:
            notes.append(f"ends in {sep!r} and {base!r} exists, but price/date "
                         "differ -- a distinct model, fine to pin")

    # --- freshness (advisory) ---------------------------------------------
    if isinstance(created, (int, float)):
        import datetime as _dt
        age = (_dt.datetime.now(_dt.timezone.utc)
               - _dt.datetime.fromtimestamp(created, _dt.timezone.utc)).days
        notes.append(f"created {age} days ago")
        if age > STALE_DAYS:
            notes.append(f"OLDER THAN {STALE_DAYS} DAYS -- section 5's freshness "
                         "rule rejected a 181-day preview; check nothing newer "
                         "exists in this family")
    return fails, notes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--panel", action="store_true",
                    help="check the pre-registered panel")
    a = ap.parse_args(argv)
    ids = list(a.ids) + (list(PANEL) if a.panel else [])
    if not ids:
        print(__doc__)
        return 2

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        raw = _get(CATALOG)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"could not read the catalogue: {type(exc).__name__}: {exc}")
        print("UNVERIFIED -- do not treat this as a pass")
        return 2
    catalog = {m["id"]: m for m in (raw.get("data") or raw)}
    print(f"catalogue: {len(catalog)} ids\n")

    bad = 0
    for ident in ids:
        # the offline identity rules first: cheaper, and they catch aliases
        try:
            from adapters.bare_wire import validate_model_id
            validate_model_id(ident)
            offline = []
        except Exception as exc:                                  # noqa: BLE001
            offline = [f"{type(exc).__name__}: {exc}"]
        fails, notes = check(ident, catalog)
        fails = offline + fails
        verdict = "FAIL" if fails else "ok"
        print(f"{verdict:>4}  {ident}")
        for n in notes:
            print(f"        {n}")
        for f in fails:
            print(f"        !! {f}")
        print()
        bad += 1 if fails else 0
    print(f"{len(ids) - bad}/{len(ids)} fit to pin")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
