"""OpenAI-compatible wire adapter, normalised to the Anthropic message shape.

This exists so ``adapters/bare.py`` can reuse ``aura_mcp.run_loop`` **verbatim**.
That loop speaks Anthropic shapes (content blocks with ``type: "tool_use"``,
``usage.input_tokens``); OpenAI-compatible endpoints speak ``tool_calls`` arrays,
``role: "tool"`` messages and ``usage.prompt_tokens``. Rather than fork the loop —
which would let two arms' loop semantics drift apart, the one thing a tool-layer
comparison cannot survive — the entire difference is confined to this module:
``call_openai_compatible`` accepts Anthropic-shaped input and returns
Anthropic-shaped output.

Provider coverage is whatever the endpoint serves. Pointed at OpenRouter this
reaches essentially every hosted model (grok, gpt, deepseek, gemini, llama, …)
through ONE code path — which is deliberate: if each provider were called
natively, the transport would become a confounding variable in a comparison whose
whole claim is that only the model changed.

**Endpoint note, easy to get wrong.** The pre-existing ``openrouter`` backend
targets OpenRouter's *Anthropic-compatible* base (``…/api``, because the Anthropic
SDK appends ``/v1/messages`` itself). This module targets the *OpenAI-compatible*
base (``…/api/v1``, and we append ``/chat/completions``). Same provider, two
different endpoints; using one URL for the other yields 404s or doubled path
segments.

**Malformed tool arguments are a MODEL outcome, not a harness fault.** Weaker
models emit invalid JSON in ``function.arguments`` at a materially higher rate
than frontier ones. If that raised, the harness would convert a model's syntax
error into a crash or a HARNESS-ERROR — excluded from the denominator — and the
comparison would systematically flatter exactly the models that make the mistake.
So a bad ``arguments`` payload is passed through as ``_MALFORMED_ARGS`` and the
dispatcher turns it into an ordinary tool error the model can see and retry.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

#: Sentinel key placed in a tool-use ``input`` when the provider returned
#: ``arguments`` that is not valid JSON. ``bare.dispatch_files`` recognises it and
#: replies with a tool error. Never raise on this path — see the module docstring.
MALFORMED_ARGS_KEY = "_MALFORMED_ARGS"

#: OpenAI-compatible default (NOT the Anthropic-compatible one — see docstring).
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class ProviderCallTimeout(RuntimeError):
    """A single provider call exceeded its TOTAL wall-clock budget.

    Distinct from a socket timeout: this fires when the response never completed
    within the budget even though bytes may have kept arriving. Surfaces as an
    adapter error -> NON-graded verdict, because a hung provider is not a model
    failure.
    """


class ProviderHTTPError(RuntimeError):
    """A provider HTTP error that KEEPS its response body.

    Exists because the body is where the fix is written and ``HTTPError.__str__``
    discards it. Carries the parts a run summary needs to be actionable without a
    second request.
    """

    def __init__(self, status: int, body: str, url: str = ""):
        self.status = status
        self.body = body
        self.url = url
        detail = f" — {body.strip()}" if body.strip() else ""
        super().__init__(f"HTTP {status} from provider{detail}")


class ModelIdentityError(RuntimeError):
    """The model that answered is not the model we pinned, or cannot be cited.

    Raised — never swallowed — because every number this arm produces is labelled
    with a model name. A run served by a different model than its label is not a
    degraded measurement, it is a FALSE one, and no downstream analysis can detect
    it. ``bare.BareAdapter`` routes this to an adapter error (a harness condition),
    so a mislabelled run leaves the denominator instead of scoring against whatever
    model the label happens to name.
    """


#: OpenRouter id suffixes that change WHAT WAS SERVED, not merely how the request
#: routed — so a run pinned to one is not comparable with the plain id, and the two
#: must never share a cell. ``:free`` is separately rate-limited (and its serving
#: config is not guaranteed to match the paid route); ``:batch`` is a different
#: queue with its own latency and truncation behaviour. Both were live in the
#: 2026-08-17 catalogue survey (e.g. ``z-ai/glm-5.2:free``,
#: ``openai/gpt-5.6-sol:batch``), i.e. one stray keystroke away from a paid slate.
NON_COMPARABLE_VARIANTS = frozenset({"free", "batch"})

#: Substrings marking an id that does not name a fixed model. A published table
#: cites a model; an alias cites whatever that alias pointed at on the day, and it
#: moves without notice. ``~`` prefixes OpenRouter's alias namespace and
#: ``-latest`` is a rolling pointer — the survey found
#: ``~deepseek/deepseek-v4-flash-latest`` priced differently from the pinned
#: ``deepseek/deepseek-v4-flash``, which is exactly the drift this refuses.
_MOVING_ID_MARKERS = ("-latest", "/latest", ":latest")


def validate_model_id(model: str) -> None:
    """Refuse a model id that cannot anchor a published number. Raises.

    Pre-spend and pure. Deliberately NARROW: it rejects only ids that are either
    non-comparable variants or moving aliases. Anything else — including variants
    we have not seen, and ids this catalogue does not list — is allowed through,
    because a whitelist would have to be re-synced against 414 models and would
    fail closed on every new release. (Our stale Aura-side key map was 12 days out
    of date and wrongly reported ``x-ai/grok-4.6`` and
    ``deepseek/deepseek-v4-flash`` as nonexistent; a whitelist here would have
    repeated that error with teeth.)
    """
    ident = (model or "").strip()
    if not ident:
        raise ModelIdentityError("empty model id")
    if ident.startswith("~"):
        raise ModelIdentityError(
            f"{ident!r} is in OpenRouter's alias namespace ('~'), which does not "
            "name a fixed model — pin the concrete id instead")
    low = ident.lower()
    for marker in _MOVING_ID_MARKERS:
        if low.endswith(marker):
            raise ModelIdentityError(
                f"{ident!r} is a rolling alias ({marker!r}); it can change under a "
                "run set and make two reps of 'the same model' different models")
    if ":" in ident:
        variant = ident.rsplit(":", 1)[1].lower()
        if variant in NON_COMPARABLE_VARIANTS:
            raise ModelIdentityError(
                f"{ident!r} pins the {variant!r} serving variant, which is not "
                f"comparable with {ident.rsplit(':', 1)[0]!r} — drop the suffix "
                "or report it as its own arm, never pooled")


def _identity_core(model: str) -> str:
    """The comparable core of an id: no provider prefix, no variant, lowercased."""
    core = (model or "").strip().lstrip("~").lower()
    if ":" in core:
        core = core.rsplit(":", 1)[0]
    if "/" in core:
        core = core.rsplit("/", 1)[1]
    return core


def wire_model_matches(pinned: str, wire: Optional[str]) -> Optional[bool]:
    """Did the model that answered match the one we pinned?

    Returns ``None`` when the provider did not report a model at all — that is
    *unverified*, not *mismatched*, and it must not fail a paid run: OpenAI-compatible
    endpoints are not obliged to echo the field, and treating silence as a mismatch
    would void whole arms for a serving detail with no bearing on the answer.
    Callers record the ``None`` rather than laundering it into a pass.

    Matching is containment on the core id in either direction, because providers
    legitimately return a MORE specific name than was asked for — a dated build
    (``gpt-5.6-sol`` -> ``gpt-5.6-sol-2026-07-11``) is the same model, and demanding
    string equality would reject every honest response from those providers. What it
    still catches is the fault that matters: a substitution to an unrelated model,
    which is what a silent gateway fallback looks like.
    """
    if wire is None or not str(wire).strip():
        return None
    want, got = _identity_core(pinned), _identity_core(str(wire))
    if not want or not got:
        return None
    return want in got or got in want


def anthropic_tools_to_openai(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """``{name, description, input_schema}`` -> OpenAI ``function`` tool defs."""
    out: List[Dict[str, Any]] = []
    for t in tools:
        out.append({
            "type": "function",
            "function": {
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                # Some endpoints reject a missing/empty schema, so always send a
                # well-formed object rather than None.
                "parameters": t.get("input_schema")
                or {"type": "object", "properties": {}},
            },
        })
    return out


def anthropic_messages_to_openai(
    messages: List[Dict[str, Any]], system: Optional[str]
) -> List[Dict[str, Any]]:
    """Translate the loop's Anthropic-shaped history into OpenAI chat messages.

    Three input shapes occur, and they are exactly what ``run_loop`` produces:
      * ``{"role": "user", "content": "<str>"}`` — the task prompt;
      * ``{"role": "assistant", "content": [blocks]}`` — text and/or tool_use;
      * ``{"role": "user", "content": [tool_result blocks]}`` — tool outputs,
        which OpenAI models expect as one ``role: "tool"`` message EACH, keyed by
        ``tool_call_id``. Collapsing them into one message loses the pairing and
        makes multi-tool turns unattributable.
    """
    out: List[Dict[str, Any]] = []
    if system:
        out.append({"role": "system", "content": system})
    for m in messages:
        role = m.get("role")
        content = m.get("content")
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue
        blocks = content if isinstance(content, list) else []
        if role == "assistant":
            text = "\n".join(
                b.get("text", "") for b in blocks if b.get("type") == "text"
            ).strip()
            tool_calls = [
                {
                    "id": b.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": b.get("name", ""),
                        "arguments": json.dumps(b.get("input", {})),
                    },
                }
                for b in blocks
                if b.get("type") == "tool_use"
            ]
            msg: Dict[str, Any] = {"role": "assistant"}
            # An assistant turn with tool calls may legitimately carry no text.
            # Send content=None rather than "" — some endpoints reject the empty
            # string when tool_calls is present.
            msg["content"] = text or None
            if tool_calls:
                msg["tool_calls"] = tool_calls
            out.append(msg)
            continue
        # role == "user" carrying tool_result blocks
        for b in blocks:
            if b.get("type") == "tool_result":
                out.append({
                    "role": "tool",
                    "tool_call_id": b.get("tool_use_id", ""),
                    "content": str(b.get("content", "")),
                })
            elif b.get("type") == "text":
                out.append({"role": "user", "content": b.get("text", "")})
    return out


def openai_response_to_anthropic(payload: Dict[str, Any]) -> Dict[str, Any]:
    """OpenAI chat completion -> ``{"content": [blocks], "usage": {...}}``.

    Returns the shape ``run_loop`` reads: ``content`` blocks it scans for
    ``text``/``tool_use``, and ``usage`` with Anthropic's key names.
    """
    choices = payload.get("choices") or []
    message = (choices[0].get("message") if choices else None) or {}
    blocks: List[Dict[str, Any]] = []

    text = message.get("content")
    if isinstance(text, list):
        # A few providers return content as a parts array; flatten defensively.
        text = "".join(
            p.get("text", "") for p in text if isinstance(p, dict)
        )
    if text:
        blocks.append({"type": "text", "text": text})

    for tc in message.get("tool_calls") or []:
        fn = tc.get("function") or {}
        raw = fn.get("arguments")
        if isinstance(raw, dict):
            parsed: Dict[str, Any] = raw
        else:
            try:
                parsed = json.loads(raw or "{}")
                if not isinstance(parsed, dict):
                    raise ValueError("arguments must decode to an object")
            except (ValueError, TypeError):
                # A model outcome, not a harness fault — see module docstring.
                parsed = {MALFORMED_ARGS_KEY: raw}
        blocks.append({
            "type": "tool_use",
            "id": tc.get("id") or "",
            "name": fn.get("name") or "",
            "input": parsed,
        })

    # WHY THE TURN ENDED. Without this the loop cannot tell "the model chose to
    # stop" from "we truncated it": a max_tokens cut-off returns
    # finish_reason="length" with content=None and NO tool calls, which is
    # byte-identical to a clean finish. Measured 2026-08-18 — claude-opus-5 explored
    # for 20 turns, got truncated, and the run recorded FAIL_NO_EDITS as though the
    # model had decided it was done. Our config, charged to the model, and biased
    # toward whichever models write the longest turns.
    finish = (choices[0] or {}).get("finish_reason") if choices else None

    usage = payload.get("usage") or {}
    pd = usage.get("prompt_tokens_details") or {}
    cd = usage.get("completion_tokens_details") or {}
    return {
        "content": blocks,
        "usage": {
            "input_tokens": int(usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or 0),
            # OpenRouter reports AUTHORITATIVE cost per call, plus cache and
            # reasoning breakdowns. We used to drop all of it and re-derive cost by
            # multiplying tokens against a hand-maintained price table — an estimate
            # that drifts, and which was wrong twice on 2026-08-17 alone (the table
            # held Aura's marked-up prices, not OpenRouter's). Prefer the provider's
            # own number; the table stays only as a fallback for endpoints that
            # report none.
            "cost_usd": usage.get("cost"),
            "cache_read_tokens": pd.get("cached_tokens"),
            "cache_creation_tokens": pd.get("cache_write_tokens"),
            "reasoning_tokens": cd.get("reasoning_tokens"),
        },
        "finish_reason": finish,
        # The provider's own id for this call: the join key to OpenRouter's activity
        # records, so a published cost can be audited against their ledger rather
        # than trusted from ours.
        "generation_id": payload.get("id"),
        # Kept for attribution: which model actually answered. Providers behind a
        # gateway can silently substitute, and a benchmark that cannot name the
        # responder cannot label its own results.
        "model": payload.get("model"),
        # WHICH BACKEND served it. OpenRouter fans one model id out across several
        # hosts that differ in quantization, context window and version cadence, so
        # the model id alone does not identify the system under test. Observed
        # 2026-08-18: the same pinned slug answered as grok-4.5 on one call and
        # grok-4.6 on another. Recording the served provider makes that drift
        # visible per run instead of averaging two systems into one row.
        "provider": payload.get("provider"),
    }


#: Body bytes kept from a provider error. Enough for a full OpenRouter error
#: object; short enough that a misconfigured endpoint returning an HTML page does
#: not paste a document into a run summary.
_ERROR_BODY_LIMIT = 800


def _post_json(url: str, body: Dict[str, Any], headers: Dict[str, str],
               timeout: float) -> Dict[str, Any]:
    """POST and parse JSON, with ``timeout`` as a TOTAL wall clock.

    urllib's ``timeout`` is a PER-READ socket timeout: it resets on every byte
    that arrives, so a provider dribbling keepalives is unbounded under it. And
    ``run_loop`` can only check its ceiling BETWEEN turns, so a call that never
    returns is never interrupted. Measured 2026-08-17: a bare drive sat **65
    minutes inside one call** against a 20-minute ceiling, writing nothing.

    So the request runs in a daemon thread that is ABANDONED on expiry. The socket
    leaks until the process exits — the right trade against an unbounded run, and
    bounded in practice because the drive is ending anyway. Raising here surfaces as
    an adapter error, which ``run._agent_never_ran`` routes to a NON-graded verdict:
    a hung provider must not read as a model failure.
    """
    box: Dict[str, Any] = {}

    def _work() -> None:
        try:
            box["ok"] = _post_json_inner(url, body, headers, timeout)
        except BaseException as exc:  # noqa: BLE001 - re-raised on the caller's thread
            box["err"] = exc

    worker = threading.Thread(target=_work, daemon=True,
                              name="bare-wire-post")
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        raise ProviderCallTimeout(
            f"no response within {timeout:.0f}s (total wall clock, not per-read) "
            f"from {url} — abandoning the call")
    if "err" in box:
        raise box["err"]
    return box["ok"]


def _post_json_inner(url: str, body: Dict[str, Any], headers: Dict[str, str],
                     timeout: float) -> Dict[str, Any]:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", **headers},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        # The RESPONSE BODY carries the actionable half of every provider 4xx, and
        # HTTPError's str() drops it: a gated model reads only as "HTTP Error 403:
        # Forbidden" when the body names the exact setting to change, a spent key
        # reads the same as a bad one, and a rate limit does not say for how long.
        # Measured 2026-08-17 on meta/muse-spark-1.2 — diagnosing that 403 took a
        # second hand-written request purely to read the body this now keeps.
        # Re-raised (never swallowed) so the adapter still routes it to a HARNESS
        # condition rather than letting a provider refusal score as a model failure.
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:_ERROR_BODY_LIMIT]
        except Exception:  # noqa: BLE001 - a body we cannot read must not mask the status
            pass
        raise ProviderHTTPError(e.code, detail, url) from e


def _is_openrouter(base_url: str) -> bool:
    """Is this endpoint OpenRouter? Gates OpenRouter-only request fields.

    Checked rather than assumed because ``usage``/``provider`` are OpenRouter
    extensions: a strict OpenAI-compatible server may 400 on an unknown top-level
    field, and a benchmark that cannot call a provider at all is worse than one
    that cannot price it.
    """
    return "openrouter.ai" in (base_url or "").lower()


def _provider_routing() -> Optional[Dict[str, Any]]:
    """The OpenRouter ``provider`` block: env override, else no-fallback.

    A malformed override is IGNORED with a warning rather than being sent: a
    rejected request looks like a provider outage and would be diagnosed for an
    hour before anyone suspected a typo in an env var.
    """
    raw = (os.environ.get("CB_OPENROUTER_PROVIDER") or "").strip()
    if not raw:
        return {"allow_fallbacks": False}
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        print(f"  WARN  CB_OPENROUTER_PROVIDER is not valid JSON ({exc}); "
              f"falling back to allow_fallbacks=false", flush=True)
        return {"allow_fallbacks": False}
    if not isinstance(parsed, dict):
        print("  WARN  CB_OPENROUTER_PROVIDER must be a JSON object; "
              "falling back to allow_fallbacks=false", flush=True)
        return {"allow_fallbacks": False}
    return parsed


def call_openai_compatible(
    *,
    api_key: str,
    model: str,
    system: Optional[str],
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    max_tokens: int,
    timeout: float = 60.0,
    base_url: str = DEFAULT_BASE_URL,
    post_json=_post_json,
) -> Dict[str, Any]:
    """Drop-in for ``run_loop``'s ``llm_call`` seam, against any OpenAI-compatible API.

    Signature matches ``aura_agent.call_anthropic_with_tools`` so ``run_loop``
    needs no change. ``post_json`` is injected so this is unit-testable with no
    network and no key.
    """
    body: Dict[str, Any] = {
        "model": model,
        "messages": anthropic_messages_to_openai(messages, system),
        "max_tokens": max_tokens,
    }
    if tools:
        body["tools"] = anthropic_tools_to_openai(tools)
    if _is_openrouter(base_url):
        # ACCOUNTING. OpenRouter only populates ``usage.cost`` when the request
        # ASKS for it. Without this the field is simply absent, we recorded a
        # blank/zero, and the run looked free — measured 2026-08-18 on x-ai/grok-4.6,
        # whose list price is $2/$6 per M, and on the gpt-5.6 family, which has no
        # free tier on OpenRouter at all. Two models with no plausible zero both
        # reading zero is a reporting gap, not a promotion.
        body["usage"] = {"include": True}
        # ROUTING. Without a provider block OpenRouter may fail over to another
        # backend, or to a quantized build, mid-run. That is a VALIDITY problem
        # before it is a cost one: a panel that pins a model but not the machine
        # serving it silently compares different systems. Defaults to
        # ``allow_fallbacks: false`` so a routing change surfaces as an error the
        # transport path already routes to a NON-graded verdict, rather than as a
        # quietly different model answering. Override wholesale with
        # ``CB_OPENROUTER_PROVIDER`` (JSON), e.g. to pin an order or exclude
        # quantizations: {"order":["xai"],"allow_fallbacks":false,
        #                 "quantizations":["fp8","bf16"]}
        prov = _provider_routing()
        if prov:
            body["provider"] = prov
    payload = post_json(
        base_url.rstrip("/") + "/chat/completions",
        body,
        {"Authorization": f"Bearer {api_key}"},
        timeout,
    )
    out = openai_response_to_anthropic(payload)
    # Checked on EVERY turn, not just the first: a gateway can fail over
    # mid-conversation, and a rep whose later turns were served by a different
    # model is mislabelled just as badly as one that started wrong.
    if wire_model_matches(model, out.get("model")) is False:
        raise ModelIdentityError(
            f"pinned {model!r} but {out.get('model')!r} answered — the run would be "
            "labelled with a model that did not produce it")
    return out
