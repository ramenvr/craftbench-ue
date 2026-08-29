"""anthropic_proxy — transparent logging proxy for api.anthropic.com.

Captures per-request token usage AND a per-request reasoning+tool-call trace
WITHOUT modifying Aura. Point Aura's server (and the :3008 vercelServer that
runs the *_agent sub-agents) at it via env:

    ANTHROPIC_BASE_URL=http://127.0.0.1:41299/v1

It forwards /v1/* to https://api.anthropic.com/v1/* by DEFAULT, STREAMS responses
through untouched (so the agent loop is unaffected), and tees each response to
extract:

  * token usage   -> appended one JSON line per request to USAGE_LOG
  * reasoning+tool -> appended one JSON line per request to TRACE_LOG

Upstream is CONFIGURABLE (``CB_PROXY_UPSTREAM``, default unchanged) so the same
tee can sit in front of OpenRouter's Anthropic skin::

    CB_PROXY_UPSTREAM=https://openrouter.ai/api

WHY (measured 2026-08-18): behind that gateway the Claude Code CLI's own
``total_cost_usd`` is WRONG. The CLI prices the call itself at Anthropic
FIRST-PARTY rates and has no idea it is behind a gateway — a probe of 55,351
cache-creation + 2 input + 4 output tokens reported $0.20763225, which is
Anthropic's own first-party list applied term by term::

    55351 * $3.75/1M   (cache WRITE)  = $0.20756625
    +   2 * $3.00/1M   (fresh input)  = $0.00000600
    +   4 * $15.00/1M  (output)       = $0.00006000
                                      = $0.20763225  <- the CLI's number, exactly

CORRECTED 2026-08-18 (adversarial review): an earlier version of this comment
attributed the WHOLE $0.20763225 to the cache-write term. That term alone is
$0.20756625 — the reconciliation is real, the attribution was not; the missing
$0.000066 is the 2 fresh input + 4 output tokens above. Token counts are right;
only the unit price is wrong, and OpenRouter's rate is lower, so the CLI
OVER-reports on that path. OpenRouter itself returns the true number on every response
(``usage.cost`` + ``usage.cost_details``) plus a ``gen-...`` id that joins to its
ledger (``aura_rig.openrouter_cost``), and this proxy is the only seam that sees
those bytes — the CLI does not surface them. Account-level reconciliation is NOT
an alternative: ``/api/v1/credits`` moved $72.19 during a window in which our
probes cost cents (the account is not quiet), and ``/api/v1/activity`` 403s for
non-management keys. Per-generation ids are the only sound audit path.

The MAIN /api/chat loop and each *_agent sub-agent BOTH flow through this proxy;
they are told apart downstream by their on-wire ``model`` and ``system_preview``
(see ``usage_since`` / ``subagent_trace_since``).

Structure
---------
The HTTP plumbing (``Handler`` / ``Srv``) is unchanged from the proven
/tmp/anthropic_proxy.py, but the *parsing* is factored into pure functions
(``parse_sse_response`` / ``parse_json_response`` / ``build_trace_record``) and
the *aggregation* readers (``usage_since`` / ``subagent_trace_since``) live here
too — so the whole module is importable and unit-testable with no socket and no
network. ``python3 -m aura_rig.proxy`` (or running the file) starts the server.
"""
from __future__ import annotations

import http.client
import http.server
import hashlib
import json
import os
import ssl
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Dict, List, Mapping, NamedTuple, Optional, Tuple

from . import model_keys

PORT = 41299
#: Default upstream HOST — unchanged from the day this proxy was written.
UPSTREAM = "api.anthropic.com"
#: Env override. A bare host ("api.anthropic.com"), "host:port", or a full URL
#: with a PATH PREFIX ("https://openrouter.ai/api"). The prefix is the reason a
#: bare host is not enough: OpenRouter's Anthropic skin lives under /api, and a
#: client's "/v1/messages" must arrive there as "/api/v1/messages".
UPSTREAM_ENV = "CB_PROXY_UPSTREAM"
#: What Aura's server / the :3008 vercelServer are pointed at (they do NOT append
#: "/v1" themselves). NOT interchangeable with CLI_BASE_URL below.
BASE_URL = f"http://127.0.0.1:{PORT}/v1"
#: What the Claude Code CLI is pointed at (ANTHROPIC_BASE_URL). The Anthropic SDK
#: appends "/v1/messages" ITSELF — the same reason adapters/registry.py points the
#: CLI at OpenRouter's "/api" and not "/api/v1" — so this form carries no "/v1" or
#: the CLI would ask this proxy for "/v1/v1/messages".
CLI_BASE_URL = f"http://127.0.0.1:{PORT}"
#: OpenRouter's per-call generation id prefix. It is the join key for
#: GET /api/v1/generation (see aura_rig.openrouter_cost). Anthropic's own
#: top-level id is "msg_..." and 404s there, so only a gen- id may be collected
#: as a generation id — a msg_ id in that list would manufacture a fake ledger gap.
GENERATION_ID_PREFIX = "gen-"
_CB_TMP = Path(os.environ.get("CB_TMP", tempfile.gettempdir()))
USAGE_LOG = _CB_TMP / "cb-anthropic-usage.jsonl"
TRACE_LOG = _CB_TMP / "cb-anthropic-trace.jsonl"
# Opt-in: inject cache_control breakpoints into outbound /v1/messages (models
# prod cost for a desktop Aura build that ships an un-cached route). OFF -> pure
# pass-through, so the as-measured cost stays the honest primary number.
_INJECT_CACHE = os.environ.get("CB_PROXY_INJECT_CACHE", "") not in ("", "0", "false", "no")
_lock = threading.Lock()

# Mac Python often lacks a system CA bundle -> use certifi (the documented fix).
try:
    import certifi

    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover - depends on host certifi
    _SSL_CTX = ssl.create_default_context()


# ---------------------------------------------------------------------------
# Upstream resolution (pure; no socket).
# ---------------------------------------------------------------------------

class Upstream(NamedTuple):
    """Where this proxy forwards to, fully resolved."""

    host: str
    port: int
    tls: bool
    #: Path glued in FRONT of the client's path ("" for api.anthropic.com,
    #: "/api" for OpenRouter's Anthropic skin). Never ends in "/".
    path_prefix: str

    @property
    def host_header(self) -> str:
        """The ``Host:`` header value (port omitted when it is the scheme's default)."""
        default_port = 443 if self.tls else 80
        return self.host if self.port == default_port else f"{self.host}:{self.port}"

    @property
    def label(self) -> str:
        return f"{'https' if self.tls else 'http'}://{self.host_header}{self.path_prefix}"

    def forward_path(self, path: str) -> str:
        """Upstream path for a client path: ``/v1/messages`` -> ``/api/v1/messages``."""
        if not self.path_prefix:
            return path
        return self.path_prefix + (path if path.startswith("/") else "/" + path)


DEFAULT_UPSTREAM = Upstream(UPSTREAM, 443, True, "")


def parse_upstream(spec: Optional[str]) -> Upstream:
    """Parse a CB_PROXY_UPSTREAM spec. Blank/None -> the api.anthropic.com default.

    RAISES on a spec that is set but unparseable, and that is deliberate. The
    alternative — falling back to the default — would send traffic to Anthropic
    FIRST-PARTY while the operator believed they were measuring a gateway: real
    money spent on the wrong endpoint, and a cost number that is wrong in a way
    nothing downstream could detect. Fail closed and say which spec was bad.
    """
    spec = (spec or "").strip().strip('"').strip("'")
    if not spec:
        return DEFAULT_UPSTREAM
    # urlsplit needs a scheme to populate .hostname; a bare host is the common form.
    if "//" not in spec:
        spec = "https://" + spec
    u = urllib.parse.urlsplit(spec)
    if u.scheme not in ("http", "https"):
        raise ValueError(f"{UPSTREAM_ENV}: unsupported scheme {u.scheme!r} in {spec!r} "
                         "(want http or https)")
    if u.query or u.fragment:
        raise ValueError(f"{UPSTREAM_ENV}: {spec!r} carries a query/fragment; an "
                         "upstream is a scheme+host+path prefix only")
    host = u.hostname
    if not host:
        raise ValueError(f"{UPSTREAM_ENV}: no host in {spec!r}")
    tls = u.scheme == "https"
    try:
        port = u.port or (443 if tls else 80)
    except ValueError as e:  # non-numeric port
        raise ValueError(f"{UPSTREAM_ENV}: bad port in {spec!r} ({e})") from None
    return Upstream(host, port, tls, u.path.rstrip("/"))


def resolve_upstream(spec: Optional[str] = None) -> Upstream:
    """The live upstream, resolved at CALL time from ``CB_PROXY_UPSTREAM``.

    Late-bound on purpose, exactly like ``usage_since``'s USAGE_LOG: a test (or an
    operator restarting a drive) can rebind the env without re-importing, and one
    running proxy never serves a stale target it printed at boot.
    """
    if spec is None:
        spec = os.environ.get(UPSTREAM_ENV, "")
    return parse_upstream(spec)


# ---------------------------------------------------------------------------
# Pure parsing (no socket / no network) — the unit-testable core.
# ---------------------------------------------------------------------------

#: Fields that exist ONLY behind a gateway. Never seeded into a record: their
#: ABSENCE is the signal that this response came from api.anthropic.com (or that
#: the gateway stopped sending them), and a 0.0 there would read as "free".
GATEWAY_FIELDS = ("response_id", "generation_id", "cost_usd", "cost_details",
                  "reasoning_tokens", "provider")


#: Version stamped on every USAGE_LOG line, bumped whenever a change alters what
#: a recorded COLUMN MEANS — otherwise two windows recorded under different rules
#: read as one comparable series:
#:   1  prompt-side counts were read only from a stream's ``message_start``, so
#:      every streamed gateway row under-reports input_tokens/cache_read/
#:      cache_write (see ``_absorb_prompt_usage``). Rows written before the stamp
#:      existed carry no version at all, and that is exactly schema 1.
#:   2  prompt-side counts are read from whichever event carries them.
USAGE_REC_SCHEMA = 2


def _is_number(v) -> bool:
    """True for a real number. ``bool`` is an int subclass — exclude it explicitly."""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _absorb_cost(rec: dict, usage) -> None:
    """Copy OpenRouter's ``usage.cost`` / ``usage.cost_details`` into ``rec`` IF PRESENT.

    Absent stays absent (see GATEWAY_FIELDS). ``cost_details`` is copied VERBATIM
    rather than filtered to the two keys measured on 2026-08-18
    (upstream_inference_prompt_cost / upstream_inference_completions_cost), so a
    key the gateway adds later is recorded instead of silently dropped; the
    aggregator sums only the numeric ones.
    """
    if not isinstance(usage, Mapping):
        return
    if _is_number(usage.get("cost")):
        rec["cost_usd"] = float(usage["cost"])
    cd = usage.get("cost_details")
    if isinstance(cd, Mapping) and cd:
        rec["cost_details"] = dict(cd)


def _absorb_reasoning(rec: dict, usage) -> None:
    """Copy the gateway's reasoning-token count into ``rec`` IF PRESENT.

    The count arrives as ``usage.output_tokens_details.thinking_tokens`` and is a
    SUBSET of ``output_tokens``, so it is not derivable from anything already
    recorded — output tokens alone cannot say how many were spent thinking.
    Absent stays absent (see GATEWAY_FIELDS): a 0 on api.anthropic.com, whose
    usage block has no such member, would claim a model did not think when the
    truth is that this wire cannot tell us.
    """
    if not isinstance(usage, Mapping):
        return
    details = usage.get("output_tokens_details")
    if isinstance(details, Mapping) and _is_number(details.get("thinking_tokens")):
        rec["reasoning_tokens"] = int(details["thinking_tokens"])


def _absorb_provider(rec: dict, obj) -> None:
    """Copy the BACKEND that served the call IF PRESENT (gateway-only field).

    OpenRouter fans one model id across hosts differing in quantization and
    version cadence, so the id alone does not name the system under test —
    ``adapters/bare_wire`` already records this on the OpenAI-shaped path, and
    the Anthropic-shaped one carries it too: top-level on a JSON body, on
    ``message.provider`` in a stream.
    """
    if not isinstance(obj, Mapping):
        return
    provider = obj.get("provider")
    if isinstance(provider, str) and provider:
        rec["provider"] = provider


def _absorb_id(rec: dict, ident) -> None:
    """Record the response id, and the ``gen-`` generation id if that is what it is.

    Two fields on purpose: ``response_id`` is present on BOTH providers (Anthropic
    sends ``msg_...``), while only a ``gen-`` id can be looked up in OpenRouter's
    ledger. Collecting a msg_ id as a generation id would send the auditor to an
    endpoint that 404s and read as a missing record rather than as "not a gateway
    call at all".
    """
    if isinstance(ident, str) and ident:
        rec["response_id"] = ident
        if ident.startswith(GENERATION_ID_PREFIX):
            rec["generation_id"] = ident


#: Prompt-side usage members, as (record key, wire key). Cumulative totals on
#: every carrier that reports them, so LAST NUMERIC WINS.
_PROMPT_USAGE = (
    ("input_tokens", "input_tokens"),
    ("cache_read", "cache_read_input_tokens"),
    ("cache_write", "cache_creation_input_tokens"),
)


def _absorb_prompt_usage(rec: dict, usage) -> None:
    """Copy the prompt-side token counts from whichever carrier HAS them.

    There is no single carrier. On api.anthropic.com they are final on
    ``message_start``; on OpenRouter's Anthropic skin that block's token members
    are all zero/null and the real counts ride ``message_delta`` (measured
    2026-08-24). Reading only message_start recorded every streamed gateway call
    as 0 input_tokens, 0 cache_read and 0 cache_write — and unlike the
    gateway-only fields these three are SEEDED to 0, so the loss reads as a
    measurement rather than as absence.

    Only a NUMBER assigns: a null must not wipe a count an earlier event already
    established, which is the same trap from the other side.
    """
    if not isinstance(usage, Mapping):
        return
    for key, wire in _PROMPT_USAGE:
        if _is_number(usage.get(wire)):
            rec[key] = int(usage[wire])


def parse_sse_response(data: bytes) -> dict:
    """Parse a streamed Anthropic /v1/messages SSE body into a usage+content rec.

    Returns {input_tokens, output_tokens, cache_read, cache_write, model,
    text, tool_uses, stop_reason}. Tolerant of partial/garbage lines.
    """
    rec = {
        "input_tokens": 0, "output_tokens": 0, "cache_read": 0,
        "cache_write": 0, "model": None,
    }
    text, tool_uses, stop_reason = "", [], None
    blocks: Dict[int, dict] = {}
    for line in data.split(b"\n"):
        line = line.strip()
        if not line.startswith(b"data:"):
            continue
        try:
            ev = json.loads(line[5:].strip())
        except Exception:
            continue
        t = ev.get("type")
        if t == "message_start":
            msg = ev.get("message") or {}
            u = msg.get("usage") or {}
            _absorb_prompt_usage(rec, u)
            rec["model"] = msg.get("model")
            # Gateway-only extras. The STREAMED shape is measured (2026-08-24, a
            # probe against OpenRouter's Anthropic skin): `provider` rides
            # message_start, while cost/cost_details and output_tokens_details ride
            # message_delta alongside the finalised counts. Every carrier is read
            # for every field that could be on it — absorbing from a block that
            # turns out to be empty is a no-op — and if the gateway moves one, the
            # field stays ABSENT and usage_since reports the shortfall via
            # cost_partial rather than inventing a number.
            _absorb_id(rec, msg.get("id"))
            _absorb_cost(rec, u)
            _absorb_reasoning(rec, u)
            _absorb_provider(rec, msg)
        elif t == "content_block_start":
            cb = ev.get("content_block") or {}
            blocks[ev.get("index")] = {
                "type": cb.get("type"), "name": cb.get("name"),
                "text": "", "input": "",
            }
        elif t == "content_block_delta":
            b = blocks.get(ev.get("index"))
            d = ev.get("delta") or {}
            if b is not None:
                if d.get("type") == "text_delta":
                    b["text"] += d.get("text", "")
                elif d.get("type") == "input_json_delta":
                    b["input"] += d.get("partial_json", "")
        elif t == "message_delta":
            u = ev.get("usage") or {}
            if "output_tokens" in u:
                rec["output_tokens"] = u["output_tokens"]
            _absorb_prompt_usage(rec, u)
            _absorb_cost(rec, u)
            _absorb_reasoning(rec, u)
            stop_reason = (ev.get("delta") or {}).get("stop_reason") or stop_reason
    for b in blocks.values():
        if b["type"] == "text":
            text += b["text"]
        elif b["type"] == "tool_use":
            tool_uses.append({"name": b["name"], "input": b["input"][:600]})
    rec["text"] = text
    rec["tool_uses"] = tool_uses
    rec["stop_reason"] = stop_reason
    return rec


def parse_json_response(data: bytes) -> dict:
    """Parse a non-streamed Anthropic /v1/messages JSON body into the same rec."""
    rec = {
        "input_tokens": 0, "output_tokens": 0, "cache_read": 0,
        "cache_write": 0, "model": None,
        "text": "", "tool_uses": [], "stop_reason": None,
    }
    if not data.strip():
        return rec
    ev = json.loads(data)
    u = ev.get("usage") or {}
    rec["input_tokens"] = u.get("input_tokens", 0)
    rec["output_tokens"] = u.get("output_tokens", 0)
    rec["cache_read"] = u.get("cache_read_input_tokens", 0)
    rec["cache_write"] = u.get("cache_creation_input_tokens", 0)
    rec["model"] = ev.get("model")
    rec["stop_reason"] = ev.get("stop_reason")
    _absorb_id(rec, ev.get("id"))
    _absorb_cost(rec, u)
    _absorb_reasoning(rec, u)
    _absorb_provider(rec, ev)
    text, tool_uses = "", []
    for blk in ev.get("content") or []:
        if blk.get("type") == "text":
            text += blk.get("text", "")
        elif blk.get("type") == "tool_use":
            tool_uses.append({"name": blk.get("name"),
                              "input": json.dumps(blk.get("input"))[:600]})
    rec["text"] = text
    rec["tool_uses"] = tool_uses
    return rec


def parse_response(data: bytes, is_sse: bool) -> dict:
    """Dispatch to the SSE or JSON parser, never raising (records parse_error)."""
    try:
        return parse_sse_response(data) if is_sse else parse_json_response(data)
    except Exception as e:  # pragma: no cover - defensive
        return {
            "input_tokens": 0, "output_tokens": 0, "cache_read": 0,
            "cache_write": 0, "model": None, "text": "", "tool_uses": [],
            "stop_reason": None, "parse_error": str(e)[:120],
        }


def build_usage_record(parsed: dict, path: str, status: int, is_sse: bool,
                       ts: Optional[float] = None) -> dict:
    """Shape one USAGE_LOG line from a parsed response."""
    rec = {
        "ts": ts if ts is not None else time.time(),
        "rec_schema": USAGE_REC_SCHEMA,
        "path": path, "status": status, "stream": is_sse,
        "input_tokens": parsed.get("input_tokens", 0),
        "output_tokens": parsed.get("output_tokens", 0),
        "cache_read": parsed.get("cache_read", 0),
        "cache_write": parsed.get("cache_write", 0),
        "model": parsed.get("model"),
    }
    for k in GATEWAY_FIELDS:
        if k in parsed:  # present-only: see GATEWAY_FIELDS
            rec[k] = parsed[k]
    if "parse_error" in parsed:
        rec["parse_error"] = parsed["parse_error"]
    return rec


def build_trace_record(parsed: dict, request_body: bytes,
                       ts: Optional[float] = None) -> dict:
    """Shape one TRACE_LOG line from a parsed response + the request body.

    Pulls system_preview/last_user/n_messages/tools_offered from the request so
    the MAIN loop and each *_agent sub-agent can be told apart downstream.
    """
    try:
        req = json.loads(request_body) if request_body else {}
    except Exception:
        req = {}
    sysv = req.get("system")
    sys_preview = (
        (sysv if isinstance(sysv, str) else json.dumps(sysv))[:200] if sysv else ""
    )
    msgs = req.get("messages") or []
    last_user = ""
    for m in reversed(msgs):
        if m.get("role") == "user":
            c = m.get("content")
            last_user = (c if isinstance(c, str) else json.dumps(c))[:300]
            break
    rec = {
        "ts": ts if ts is not None else time.time(),
        "model": parsed.get("model") or req.get("model"),
        "system_preview": sys_preview,
        "n_messages": len(msgs),
        "tools_offered": len(req.get("tools") or []),
        "last_user_preview": last_user,
        "assistant_text": (parsed.get("text") or "")[:1800],
        "tool_uses": parsed.get("tool_uses") or [],
        "stop_reason": parsed.get("stop_reason"),
        "input_tokens": parsed.get("input_tokens", 0),
        "output_tokens": parsed.get("output_tokens", 0),
    }
    # Prefix hashes, so "did the cacheable prefix stay byte-identical between
    # turns" is answerable from one cell instead of from probes that could not
    # reproduce it. Merged rather than nested: the readers below key on flat
    # fields, and an absent fingerprint must look like an older record, not like
    # a record with an empty one.
    rec.update(prefix_fingerprint(request_body))
    return rec


# ---------------------------------------------------------------------------
# Aggregation readers (read the JSONL the running proxy wrote).
# ---------------------------------------------------------------------------

def line_count(path: Path) -> int:
    """Number of lines currently in a JSONL log (0 if absent)."""
    try:
        with open(path) as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def usage_line_count() -> int:
    return line_count(USAGE_LOG)


def trace_line_count() -> int:
    return line_count(TRACE_LOG)


def _is_completion_path(path) -> bool:
    """True for a ``/v1/messages``-shaped CLIENT path (query stripped).

    Recorded paths are the ones the CLIENT asked this proxy for, so they carry no
    upstream prefix ("/v1/messages", never "/api/v1/messages"). ``count_tokens``
    is deliberately NOT a match: ``/v1/messages/count_tokens`` is a free probe the
    Anthropic SDK issues alongside real calls and the gateway prices nothing for it.
    """
    p = (path or "").split("?", 1)[0].rstrip("/")
    return p.endswith("/messages")


def _status_billable(status) -> bool:
    """True when a recorded HTTP status is a success — or is UNREADABLE.

    Absent/garbage status fails CLOSED (counts as billable). "Could not tell" must
    widen the denominator so ``cost_partial`` warns; letting it shrink the
    denominator would turn an unclassifiable record into a confident "complete".
    """
    if status is None:
        return True
    try:
        return 200 <= int(status) < 300
    except (TypeError, ValueError):
        return True


def cost_bearing_request(rec: Mapping) -> bool:
    """True when the GATEWAY would have billed the request this record describes.

    This is the DENOMINATOR for ``cost_partial``, and it is deliberately not
    ``requests``. ``Handler._proxy`` appends one usage record for EVERY forwarded
    request — ``/v1/messages/count_tokens`` probes, non-``/v1/messages`` GETs, and
    every non-2xx error — and none of those can carry ``usage.cost``. Measured
    against the total request count (the shape shipped before this fix),
    ``cost_partial`` therefore read True the moment a window contained a single
    non-completion request, i.e. on essentially any real gateway run: a flag that
    is always True is worse than no flag. NB this reasoning is read off the code
    (``_proxy`` logs unconditionally; only /v1/messages responses carry cost) —
    no live gateway window has been re-measured against it.

    Positive evidence, in order:
      * the record already carries a numeric cost -> it WAS billed, by definition;
      * a non-success status                      -> the gateway bills no error;
      * a ``model`` in the response body          -> only a completion has one;
      * a /messages path with no parsed model     -> fail CLOSED and count it: a
        body the tee could not read must not be scored as "not billed".
    """
    if _is_number(rec.get("cost_usd")):
        return True
    if not _status_billable(rec.get("status")):
        return False
    return bool(rec.get("model")) or _is_completion_path(rec.get("path"))


def usage_since(n_before: int, model_key: str, *,
                usage_log: Optional[Path] = None) -> dict:
    """Aggregate USAGE_LOG records appended since line ``n_before``.

    Returns totals + per-model counts + an ``expected_wire`` field and a
    ``wire_model_mismatch`` flag (None unless the on-wire model set differs from
    what ``model_key`` should resolve to).

    GATEWAY COST (present only when the proxy sat in front of OpenRouter):

      * ``cost_usd`` — the summed provider-reported cost, or **None** when NO
        record carried one. None, never 0.0: on api.anthropic.com these fields do
        not exist, and a zero there would read as a free run.
      * ``requests_with_cost`` / ``requests_billable`` / ``cost_partial`` — how
        much of the BILLABLE window that sum actually covers. ``cost_partial`` is
        True when SOME billable request reported a cost and another did not (the
        sum then UNDER-states), False when every billable request did, None when
        none did. A partial sum presented as a total is exactly the failure this
        whole path exists to end. The denominator is ``requests_billable``
        (``cost_bearing_request``), **never** ``requests`` — see that function for
        why the total-request denominator made this flag read True on essentially
        every gateway run and so carry no information. ``requests_billable`` is
        reported alongside so a reader can see the denominator instead of
        inferring it.
      * ``cost_details_usd`` — per-key sums of ``usage.cost_details``, only for
        keys actually observed.
      * ``generation_ids`` — the ``gen-`` ids, in order, one per request that
        reported one. The join key for ``aura_rig.openrouter_cost``'s ledger audit.
      * ``reasoning_tokens`` — summed thinking tokens, or **None** when no record
        reported any. None, never 0: "this window did not think" and "this wire
        does not say" are different answers.
      * ``providers`` — the distinct backends that served the window. MORE THAN
        ONE means the window averages two systems under one model id.
      * ``rec_schemas`` — the distinct ``USAGE_REC_SCHEMA`` versions of the lines
        in this window, unstamped legacy lines counting as 1. Two windows are
        comparable only when these agree: a 1 means the prompt-token columns came
        from the rule that lost them on the streamed gateway path.

    NB ``cost_usd`` is the PROVIDER's number. Do not conflate it with
    ``model_keys.cost_usd_for_usage(...)`` (a price-table estimate, recorded as
    ``est_cost_usd``) or with the Claude Code CLI's ``total_cost_usd``, which
    prices every call at Anthropic first-party rates even behind a gateway.

    ``usage_log`` defaults (None) to the live module-level USAGE_LOG resolved at
    CALL time — so tests that rebind ``proxy.USAGE_LOG`` are honoured.
    """
    if usage_log is None:
        usage_log = USAGE_LOG
    agg = {
        "requests": 0, "input_tokens": 0, "output_tokens": 0,
        "cache_read": 0, "cache_write": 0, "models": {},
        "expected_wire": model_keys.expected_wire_for_key(model_key),
        "wire_model_mismatch": None,
        "cost_usd": None,
        "cost_details_usd": {},
        "requests_with_cost": 0,
        "requests_billable": 0,
        "cost_partial": None,
        "generation_ids": [],
        "reasoning_tokens": None,
        "providers": [],
        "rec_schemas": [],
    }
    providers_seen: set = set()
    schemas_seen: set = set()
    try:
        with open(usage_log) as f:
            lines = f.read().splitlines()[n_before:]
    except OSError:
        return agg
    for ln in lines:
        try:
            r = json.loads(ln)
        except Exception:
            continue
        agg["requests"] += 1
        for k in ("input_tokens", "output_tokens", "cache_read", "cache_write"):
            agg[k] += r.get(k, 0) or 0
        m = r.get("model")
        if m:
            agg["models"][m] = agg["models"].get(m, 0) + 1
        c = r.get("cost_usd")
        if _is_number(c):
            agg["cost_usd"] = (agg["cost_usd"] or 0.0) + float(c)
            agg["requests_with_cost"] += 1
        # A cost-carrying record is billable BY CONSTRUCTION (first branch of
        # cost_bearing_request), so requests_with_cost <= requests_billable always
        # holds and cost_partial below can never go negative-sense.
        if cost_bearing_request(r):
            agg["requests_billable"] += 1
        cd = r.get("cost_details")
        if isinstance(cd, Mapping):
            for k, v in cd.items():
                if _is_number(v):
                    agg["cost_details_usd"][k] = (
                        agg["cost_details_usd"].get(k, 0.0) + float(v))
        gid = r.get("generation_id")
        if gid:
            # Not de-duplicated: one id per request is the invariant, so a repeat
            # is a real double-count worth seeing rather than something to hide.
            agg["generation_ids"].append(gid)
        rt = r.get("reasoning_tokens")
        if _is_number(rt):
            agg["reasoning_tokens"] = (agg["reasoning_tokens"] or 0) + int(rt)
        prov = r.get("provider")
        if prov:
            providers_seen.add(prov)
        sv = r.get("rec_schema")
        schemas_seen.add(int(sv) if _is_number(sv) else 1)
    agg["providers"] = sorted(providers_seen)
    agg["rec_schemas"] = sorted(schemas_seen)
    if agg["requests_with_cost"]:
        agg["cost_partial"] = agg["requests_with_cost"] < agg["requests_billable"]
    agg["wire_model_mismatch"] = model_keys.detect_wire_mismatch(
        model_key, agg["models"]
    )
    return agg


def subagent_trace_since(n_before: int, model_key: str, *,
                         trace_log: Optional[Path] = None) -> Tuple[List[dict], dict]:
    """TRACE_LOG records since ``n_before`` whose model != the MAIN-loop wire model.

    The MAIN /api/chat loop runs on the pinned KEY's wire model; *_agent
    sub-agents (on :3008) run on a different model (account useUserModel) — so a
    trace record whose model != expected_wire is a sub-agent call. Returns
    (sub_records, by_system_signature_count).

    ``trace_log`` defaults (None) to the live module-level TRACE_LOG resolved at
    CALL time — so tests that rebind ``proxy.TRACE_LOG`` are honoured.
    """
    if trace_log is None:
        trace_log = TRACE_LOG
    expected = model_keys.expected_wire_for_key(model_key)
    try:
        with open(trace_log) as f:
            lines = f.read().splitlines()[n_before:]
    except OSError:
        return [], {}
    sub: List[dict] = []
    for ln in lines:
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if r.get("model") and r.get("model") != expected:
            sub.append(r)
    by_sig: Dict[str, int] = {}
    for r in sub:
        sig = (r.get("system_preview", "")[:50] or "?")
        by_sig[sig] = by_sig.get(sig, 0) + 1
    return sub, by_sig


def cache_health(usage: Mapping) -> dict:
    """Cache-hit health for one proxy-usage aggregate (``usage_since`` shape).

    Returns {cache_read, cache_write, hit_rate, misconfigured}. ``misconfigured``
    is True when a MULTI-request window NEVER cached (cache_read==0 AND
    cache_write==0 over >1 request) — the signature of a server that sends NO
    Anthropic cache_control, so every turn re-sends the full system+tools prefix
    at full input price. A single request can't demonstrate a miss; a write-only
    window is the normal first-turn cache CREATE — so neither is flagged.

    ``hit_rate`` = cache_read / (input_tokens + cache_read + cache_write), the
    fraction of all prompt tokens served from cache (0.0 when nothing cached).
    """
    reqs = usage.get("requests", 0) or 0
    cr = usage.get("cache_read", 0) or 0
    cw = usage.get("cache_write", 0) or 0
    in_tok = usage.get("input_tokens", 0) or 0
    denom = in_tok + cr + cw
    return {
        "cache_read": cr,
        "cache_write": cw,
        "hit_rate": (cr / denom) if denom else 0.0,
        "misconfigured": bool(reqs > 1 and cr == 0 and cw == 0),
    }


# ---------------------------------------------------------------------------
# Outbound cache_control injection (FLAG-GATED — CB_PROXY_INJECT_CACHE=1).
# ---------------------------------------------------------------------------

_EPHEMERAL = {"type": "ephemeral"}

#: One JSON line per outbound /v1/messages, recording which of the three cache
#: sites the CLIENT had already marked and which this proxy had to add. Written
#: only when CB_PROXY_INJECT_CACHE is on, i.e. never on the pass-through path.
_MARKER_CENSUS_LOG = os.environ.get(
    "CB_PROXY_MARKER_CENSUS", str(Path(LOG_DIR) / "marker_census.jsonl")
    if "LOG_DIR" in dir() else "marker_census.jsonl")


def _census(site_state, extra=None):
    """Append one census line. Fail-open: diagnostics never break a request."""
    try:
        rec = dict(site_state)
        if extra:
            rec.update(extra)
        with open(_MARKER_CENSUS_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    except Exception:                                             # noqa: BLE001
        pass


def _marked(block) -> bool:
    return isinstance(block, dict) and "cache_control" in block



def _mark(block) -> None:
    """Set an ephemeral cache_control breakpoint on a block in place (idempotent)."""
    if isinstance(block, dict) and "cache_control" not in block:
        block["cache_control"] = dict(_EPHEMERAL)


#: OFF switch for the provider pin below. ON by default, unlike
#: CB_PROXY_INJECT_CACHE: that flag MODELS a hypothetical cost and so must not
#: touch the primary number, whereas this one removes a source of invalidity.
_PIN_PROVIDER = os.environ.get("CB_PROXY_PIN_PROVIDER", "1") not in ("0", "false", "no")


#: One arm must be ONE deployment. Measured over block 1: the deepseek arm was
#: served by SEVEN vendors, and they are not interchangeable --
#:
#:     DeepSeek       288 reqs   1.8% cache   $40.80
#:     Alibaba        197 reqs  97.2% cache    $2.54
#:     StreamLake      49 reqs  96.9% cache    $0.44
#:     + 4 more at one request each
#:
#: 16x the cost per request between the top two, and a cache that works on one
#: and not the other. `bare_wire` already wrote down why this matters and it is
#: not the money: "a panel that pins a model but not the machine serving it
#: silently compares different systems."
#:
#: DEFAULT IS FIRST-PARTY. `DeepSeek` is the costly one, and it is chosen anyway:
#: it is the maker's own endpoint, it served 288 of block 1's 485 deepseek
#: requests so block 2 stays comparable with block 1, and "the model as its maker
#: serves it" is the arm definition a published comparison can defend. Its 1.8% cache is then a
#: recorded PROPERTY of that arm, not a defect to hide.
#: Override per model with CB_PROXY_PROVIDER_ORDER, e.g.
#:     {"deepseek/deepseek-v4-pro-0813": ["Alibaba"]}
#: which is ~16x cheaper and caches, at the cost of a third-party redeployment.
_PROVIDER_ORDER_DEFAULT = {
    "deepseek/deepseek-v4-pro-0813": ["DeepSeek"],
}


def _provider_order_map() -> dict:
    raw = (os.environ.get("CB_PROXY_PROVIDER_ORDER") or "").strip()
    if not raw:
        return dict(_PROVIDER_ORDER_DEFAULT)
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        print(f"  WARN  CB_PROXY_PROVIDER_ORDER is not valid JSON ({exc}); "
              f"using the measured default", flush=True)
        return dict(_PROVIDER_ORDER_DEFAULT)
    if not isinstance(parsed, dict):
        print("  WARN  CB_PROXY_PROVIDER_ORDER must be a JSON object; "
              "using the measured default", flush=True)
        return dict(_PROVIDER_ORDER_DEFAULT)
    return parsed


def _provider_routing(model: str = "") -> dict:
    """The OpenRouter provider block, from ``CB_OPENROUTER_PROVIDER`` or default.

    Same env var and same semantics as ``adapters.bare_wire._provider_routing`` on
    purpose: one knob, one meaning. A malformed override is IGNORED with a warning
    rather than sent, because a rejected request looks like a provider outage and
    would be diagnosed for an hour before anyone suspected a typo.
    """
    order = _provider_order_map().get(model or "")
    base = {"allow_fallbacks": False}
    if order:
        base["order"] = list(order)
    raw = (os.environ.get("CB_OPENROUTER_PROVIDER") or "").strip()
    if not raw:
        return base
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


#: Models whose backend does NOT honour Anthropic `cache_control` breakpoints and
#: instead caches by matching the serialized prefix byte for byte. For those the
#: breakpoints are not merely useless, they are ACTIVELY HARMFUL -- see
#: strip_cache_control. Comma-separated override; substring match on the model id.
#: DEFAULT EMPTY -- the strip is OFF until it is shown to work. Measured
#: 2026-08-26 on replayed CLI bodies: stripping raised the absolute hit rate but
#: turn 2 still gained NOTHING over turn 1 (control 38.7% -> 38.5%, stripped
#: 57.8% -> 57.5%), which is the failure itself. The rolling breakpoint is real
#: and documented below; removing it is not sufficient, so shipping it on by
#: default would be a behaviour change to a running benchmark bought with no
#: evidence. Set CB_PROXY_NO_CACHE_CONTROL=deepseek,gemini to try it.
_NO_CC_MODELS = tuple(
    x.strip().lower() for x in os.environ.get(
        "CB_PROXY_NO_CACHE_CONTROL", "").split(",") if x.strip())


def _honours_cache_control(model: str) -> bool:
    """True unless this model is on the opt-in strip list (empty by default)."""
    if not _NO_CC_MODELS:
        return True
    m = (model or "").lower()
    return not any(tok in m for tok in _NO_CC_MODELS)


def native_id_sent_to_gateway(body: bytes, up: "Upstream"):
    """The model id, if a NATIVE Claude id is about to be sent to a gateway.

    OWNER REQUIREMENT, stated 2026-08-26: "claude models should go through
    api.anthropic.com, not openrouter". Today that holds by construction --
    `registry.is_openrouter_model_id` routes on the slash, so a slashless id like
    `claude-sonnet-5` never gets the proxy base URL, and 1,174 proxied requests
    contain zero Claude ids. This makes it hold by ENFORCEMENT instead, because
    the failure is silent and expensive: the proxy's upstream is a single global
    setting, so anything that ever did reach it with a native id would be
    forwarded to OpenRouter, billed there, and recorded as if measured.

    That is not hypothetical plumbing. Minutes before this was written, a proxy
    restart that dropped `CB_PROXY_UPSTREAM` came up pointing at
    api.anthropic.com while every arm in flight was an OpenRouter one -- the same
    class of mistake in the other direction, caught only because the boot line
    was read. `parse_upstream` already refuses a malformed spec for exactly this
    reason: "real money spent on the wrong endpoint, and a cost number that is
    wrong in a way nothing downstream could detect."

    Returns the offending id, or None. Fail OPEN on an unparseable body: a
    request we cannot read is not proof of anything, and a diagnostic must not
    be the thing that breaks a live drive.
    """
    if not body or not up.path_prefix:      # no prefix -> first-party, nothing to catch
        return None
    try:
        obj = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(obj, dict):
        return None
    model = obj.get("model")
    if not isinstance(model, str) or not model:
        return None
    # The same rule registry.is_openrouter_model_id routes on, stated once more
    # here so the two cannot drift into disagreeing about what "native" means.
    if "/" in model:
        return None
    return model


def strip_cache_control(body: bytes) -> bytes:
    """Remove `cache_control` breakpoints for backends that cache by BYTE PREFIX.

    THE MECHANISM, measured 2026-08-26 and reproduced from the CLI's own captured
    request bodies. Claude Code uses a ROLLING breakpoint in the messages:

        turn 1 (msgs=2):  cache_control on msg[0].blk[1]
        turn 2 (msgs=5):  cache_control on msg[3].blk[0]   <- msg[0] LOSES the key
        turn 3 (msgs=8):  cache_control on msg[6].blk[0]

    The TEXT of msg[0] is byte-identical across all three (54,684 chars, verified).
    Only the presence of the `cache_control` key moves. For Anthropic, OpenAI and
    xAI that is exactly what a breakpoint is for -- metadata, not content -- and
    they cached at 89-97%. For a backend that caches by matching the SERIALIZED
    PREFIX, the key moving off the FIRST message changes the prefix at byte one,
    every turn, forever. deepseek measured 1.8% and gemini 2.2% across 26 hours
    and 560 requests; deepseek's fresh input grew monotonically with the
    conversation (27k at 2 messages, 56k at 23) and cost $45.49.

    Seven hypotheses were refuted before this one, all of them by probes built
    from bodies I wrote by hand -- which is precisely why they cached at 99.9%:
    a hand-written probe puts the breakpoint in the same place every time. Only
    replaying the CLI's OWN successive bodies reproduced the failure (turn 2 hit
    0% on turn 1's prefix, while re-sending either body verbatim hit 99.8%).

    STATUS: the mechanism above is measured; this remedy is NOT yet shown to work
    and is therefore OFF by default. Replaying the captured bodies with the strip
    applied raised the absolute hit rate but did NOT restore turn-to-turn caching
    -- control 38.7% -> 38.5%, stripped 57.8% -> 57.5%, i.e. turn 2 still gained
    nothing from turn 1, which is precisely the defect. Something beyond the
    breakpoint is also moving. Kept, wired and tested so the next attempt starts
    from here rather than from scratch; enable with CB_PROXY_NO_CACHE_CONTROL.

    Scoped by model id: stripping for a backend that HONOURS breakpoints would
    destroy the caching it does have. Total-safe -- any parse failure returns the
    original bytes.
    """
    if not body:
        return body
    try:
        obj = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return body
    if not isinstance(obj, dict) or _honours_cache_control(obj.get("model") or ""):
        return body

    removed = [0]

    def scrub(node):
        if isinstance(node, dict):
            if node.pop("cache_control", None) is not None:
                removed[0] += 1
            for v in node.values():
                scrub(v)
        elif isinstance(node, list):
            for v in node:
                scrub(v)

    scrub(obj.get("system"))
    scrub(obj.get("tools"))
    scrub(obj.get("messages"))
    if not removed[0]:
        return body
    try:
        return json.dumps(obj).encode("utf-8")
    except (TypeError, ValueError):
        return body


def prefix_fingerprint(body: bytes) -> dict:
    """Hash the CACHEABLE PREFIX of an outbound /v1/messages body.

    THE QUESTION THIS ANSWERS, and why previews could not. On 2026-08-26 the
    deepseek arm re-sent its whole context every turn -- fresh input grew
    monotonically with the conversation (27k at 2 messages, 56k at 23) while grok
    on byte-identical traffic fell to ~1k from turn 2. That is $39.57 of an $82
    block, and prompt cost is 94% of the bill.

    Every synthetic reproduction FAILED to reproduce it: deepseek cached at
    99.9% across size (to 455k tokens), a 6-minute gap, with and without
    cache_control, pinned and unpinned, multi-turn, and with tool_use /
    tool_result blocks. So the difference is in what the CLI actually sends, and
    the trace log only kept previews -- enough to see that the system prompt and
    tool list matched grok's, not enough to see whether the prefix was STABLE
    between consecutive turns of one conversation.

    An automatic prefix cache (DeepSeek) needs the whole preceding token
    sequence byte-identical; a provider honouring the explicit cache_control
    breakpoint (xAI, OpenAI) only needs the marked span. So a prefix that
    wobbles anywhere would show exactly this split. These hashes make that
    checkable from one cell: if `sys`+`tools` hold steady while `msgs_prefix`
    changes for an unchanged message count, the wobble is in the messages; if
    `sys` itself moves turn to turn, it is upstream of them.

    Cheap and total-safe: hashes only, never content, and any parse failure
    yields an empty dict rather than disturbing the request.
    """
    try:
        obj = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return {}
    if not isinstance(obj, dict):
        return {}

    def h(x):
        return hashlib.sha256(
            json.dumps(x, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:12]

    msgs = obj.get("messages")
    msgs = msgs if isinstance(msgs, list) else []
    out = {
        "fp_sys": h(obj.get("system")),
        "fp_tools": h(obj.get("tools")),
        "fp_n_msgs": len(msgs),
    }
    # The prefix that a growing conversation SHOULD keep byte-identical: every
    # message except the last exchange. If this moves while n_msgs does not, the
    # client is rewriting history and no automatic cache can ever hit.
    if len(msgs) > 2:
        out["fp_msgs_prefix"] = h(msgs[:-2])
    return out


def inject_provider_routing(body: bytes) -> bytes:
    """Pin the OpenRouter backend on an outbound ``/v1/messages`` body.

    WHY, measured 2026-08-26 on the cpp block-1 sweep. ``CB_OPENROUTER_PROVIDER``
    existed but was read ONLY by ``adapters.bare_wire`` -- the ``bare:`` lane.
    The lanes actually being benchmarked (``unreal-mcp``, ``aura-mcp``) reach
    OpenRouter through the Claude Code CLI and ``openrouter_env_overrides``, which
    never sets one, so they ran unpinned. The usage log shows what that bought:

        deepseek/deepseek-v4-pro-0813 -> DeepSeek 273, Alibaba 3, Sail Research 1,
                                         Cloudflare 1, Together 1, Fireworks 1

    Six vendors served one "model" arm. ``bare_wire`` already states the reason
    this matters, and it is not the money: "a panel that pins a model but not the
    machine serving it silently compares different systems."

    Injected HERE because the proxy is the only seam those lanes pass through --
    the CLI speaks Anthropic and has no provider concept.

    VERIFIED before shipping (the skin has no such field in the Anthropic spec, so
    it could have been dropped silently). Three probes against
    ``openrouter.ai/api/v1/messages``: no block -> 200 DeepSeek; pinned DeepSeek ->
    200 DeepSeek; pinned a provider that does not exist -> **HTTP 404 "No endpoints
    found"**. The 404 is the proof: an ignored field cannot produce it. It also
    means a bad pin fails LOUDLY rather than quietly routing elsewhere, which is
    the failure direction this wants.

    Never overwrites a ``provider`` the client already set, and returns the
    ORIGINAL bytes on any parse failure -- a malformed request is forwarded
    exactly as sent rather than being mangled by a diagnostic.
    """
    if not body:
        return body
    try:
        obj = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return body
    if not isinstance(obj, dict) or "provider" in obj:
        return body
    prov = _provider_routing(obj.get("model") or "")
    if not prov:
        return body
    obj["provider"] = prov
    try:
        return json.dumps(obj).encode("utf-8")
    except (TypeError, ValueError):
        return body


def inject_cache_control(body: bytes) -> bytes:
    """Add Anthropic cache_control breakpoints to an outbound /v1/messages body.

    Marks the stable, re-sent prefix as ephemeral so it caches on the wire:
      * the system block (a ``str`` system is promoted to a one-element text block),
      * the LAST tool (caches the whole tools array as one prefix),
      * the LAST message's last content block (a rolling conversation breakpoint).

    Idempotent (never stacks breakpoints) and total-safe: any parse failure, or a
    body with neither ``system`` nor ``tools``, returns the ORIGINAL bytes
    untouched — a malformed request is forwarded exactly as the client sent it.

    This is the FLAG-GATED fix for a desktop Aura build that ships an un-cached
    /api/chat route. It MODELS prod cost (it changes what Aura sends), so it must
    stay OFF by default and the as-measured cost must remain the primary number.
    """
    if not body:
        return body
    try:
        req = json.loads(body)
    except Exception:
        return body
    if not isinstance(req, dict):
        return body
    sysv = req.get("system")
    tools = req.get("tools")
    has_system = bool(sysv)
    has_tools = isinstance(tools, list) and len(tools) > 0
    if not has_system and not has_tools:
        _census({"skipped": "no system and no tools"})
        return body
    # BEFORE: what the client itself marked. This is the diagnostic — if the
    # rolling site is unmarked here, the client is not asking for the
    # conversation to be cached, which is exactly the qwen failure shape.
    _msgs = req.get("messages") if isinstance(req.get("messages"), list) else []
    _last_content = (_msgs[-1].get("content") if _msgs
                     and isinstance(_msgs[-1], dict) else None)
    before = {
        "n_messages": len(_msgs),
        "n_tools": len(tools) if has_tools else 0,
        "system_kind": type(sysv).__name__,
        "system_marked": (any(_marked(b) for b in sysv)
                          if isinstance(sysv, list) else False),
        "last_tool_marked": _marked(tools[-1]) if has_tools else None,
        "rolling_marked": (_marked(_last_content[-1])
                           if isinstance(_last_content, list) and _last_content
                           else None),
        "total_markers_in": _count_markers(req),
    }
    try:
        if isinstance(sysv, str):
            req["system"] = [{"type": "text", "text": sysv,
                              "cache_control": dict(_EPHEMERAL)}]
        elif isinstance(sysv, list) and sysv:
            target = None
            for blk in sysv:
                if isinstance(blk, dict) and blk.get("type") == "text":
                    target = blk  # last text block wins
            _mark(target if target is not None else sysv[-1])
        if has_tools:
            _mark(tools[-1])
        msgs = req.get("messages")
        if isinstance(msgs, list) and msgs:
            content = msgs[-1].get("content")
            if isinstance(content, list) and content and isinstance(content[-1], dict):
                _mark(content[-1])
        before["total_markers_out"] = _count_markers(req)
        before["added"] = before["total_markers_out"] - before["total_markers_in"]
        _census(before)
        return json.dumps(req).encode()
    except Exception:
        return body


def _count_markers(req) -> int:
    """How many cache_control breakpoints the whole request carries."""
    n = 0
    try:
        sysv = req.get("system")
        if isinstance(sysv, list):
            n += sum(1 for b in sysv if _marked(b))
        for t in (req.get("tools") or []):
            n += 1 if _marked(t) else 0
        for m in (req.get("messages") or []):
            c = m.get("content") if isinstance(m, dict) else None
            if isinstance(c, list):
                n += sum(1 for b in c if _marked(b))
    except Exception:                                             # noqa: BLE001
        return -1
    return n


# ---------------------------------------------------------------------------
# Health + start helpers.
# ---------------------------------------------------------------------------

def healthz(port: int = PORT, *, timeout: float = 4.0,
            opener: Optional[Callable[[str, float], Tuple[int, str]]] = None) -> bool:
    """True iff the proxy answers /healthz 200 ``{"proxy":"ok"}`` AND has a usable upstream.

    A proxy whose ``CB_PROXY_UPSTREAM`` does not parse cannot forward a single
    request — every /v1/* call 502s — so it is NOT healthy, and answering True
    here made a preflight gate log PASS for a structurally dead proxy. ``do_GET``
    now answers such a proxy ``503 {"proxy":"misconfigured"}``, which the
    status+substring check below already rejects.

    The explicit INVALID check is for the OTHER build: a proxy started from a
    pre-2026-08-18 copy of this file answers ``200 {"proxy":"ok",
    "upstream":"INVALID: ..."}``, and this function is the CLIENT half — it can be
    newer than the running server. Taking that server's word would reproduce the
    exact SILENT-OK this change closes.

    ``opener`` is an injectable (url, timeout)->(status, body) seam for tests.
    """
    url = f"http://127.0.0.1:{port}/healthz"
    if opener is None:
        def opener(u, t):  # noqa: E306
            with urllib.request.urlopen(u, timeout=t) as r:  # noqa: S310 localhost
                return r.status, r.read().decode("utf-8", "replace")
    try:
        status, body = opener(url, timeout)
    except Exception:
        return False
    if status != 200 or '"proxy":"ok"' not in (body or ""):
        return False
    try:
        up = (json.loads(body) or {}).get("upstream")
    except Exception:
        # Not JSON, but it did carry the '"proxy":"ok"' substring. Unchanged from
        # the original contract: an unreadable body cannot report an INVALID
        # upstream either way, so this is not the case being defended here.
        return True
    return not (isinstance(up, str) and up.startswith("INVALID:"))


def reported_upstream(port: int = PORT, *, timeout: float = 4.0,
                      opener: Optional[Callable[[str, float], Tuple[int, str]]] = None
                      ) -> Optional[str]:
    """What a RUNNING proxy says it forwards to, or ``None`` if that can't be read.

    ``None`` deliberately conflates "no proxy answered" with "answered without an
    upstream field" (an older build): both mean the target is UNCONFIRMED, and a
    caller about to route paid traffic through it must treat unconfirmed as a
    refusal — not as permission to route anyway.

    Same injectable ``opener`` seam as ``healthz`` so this is testable with no socket.
    """
    url = f"http://127.0.0.1:{port}/healthz"
    if opener is None:
        def opener(u, t):  # noqa: E306
            with urllib.request.urlopen(u, timeout=t) as r:  # noqa: S310 localhost
                return r.status, r.read().decode("utf-8", "replace")
    try:
        status, body = opener(url, timeout)
        if status != 200:
            return None
        up = (json.loads(body) or {}).get("upstream")
    except Exception:
        return None
    return up if isinstance(up, str) and up and not up.startswith("INVALID:") else None


def start_in_process(port: int = PORT) -> "Srv":
    """Start the proxy in a background daemon thread (used by the rig/tests).

    Returns the server; call ``.shutdown()`` to stop. The CLI ``__main__`` path
    uses ``serve_forever`` instead.
    """
    USAGE_LOG.touch(exist_ok=True)
    srv = Srv(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


# ---------------------------------------------------------------------------
# HTTP plumbing (forwards untouched; tees usage+trace). From the proven proxy.
# ---------------------------------------------------------------------------

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # silence default request logging
        pass

    def do_GET(self):
        if self.path == "/healthz":
            # The upstream is reported so a CALLER can verify which endpoint an
            # already-running proxy is tee-ing: a proxy started against
            # api.anthropic.com is indistinguishable from outside otherwise, and
            # routing a gateway run through it would spend first-party money.
            # separators=(",",":") is load-bearing — healthz() matches the literal
            # substring '"proxy":"ok"', which json.dumps' default ", " would break.
            # Pinned on the WIRE BYTES by test_proxy_openrouter_cost.py::
            # TestHealthzWireBytes, which hard-codes the expected body rather than
            # re-deriving it here (a test that re-derives it survives any mutation
            # of these separators — adversarial review, 2026-08-18).
            try:
                up, ok = resolve_upstream().label, True
            except Exception as e:
                # A bad CB_PROXY_UPSTREAM: say so, never guess — and answer NON-OK.
                # Such a proxy 502s every forwarded request, so a 200 "ok" here
                # made healthz() True and a preflight gate log PASS for a proxy
                # that cannot forward anything. 503 + "misconfigured" also keeps
                # the literal '"proxy":"ok"' substring OUT of the body, so the
                # substring-matching callers that do NOT go through healthz()
                # (aura_rig/preflight.py's :41299 probe) fail closed as well.
                up, ok = f"INVALID: {e}", False
            body = json.dumps({"proxy": "ok" if ok else "misconfigured",
                               "upstream": up},
                              separators=(",", ":")).encode()
            self.send_response(200 if ok else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._proxy("GET")

    def do_POST(self):
        self._proxy("POST")

    def _proxy(self, method):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b""
        # FLAG-GATED (CB_PROXY_INJECT_CACHE=1): add cache_control breakpoints to
        # outbound /v1/messages so the stable system+tools prefix caches on the
        # wire. OFF by default -> the proxy stays a pure pass-through. inject is
        # total-safe (falls back to the original body on any parse failure).
        # split("?") is load-bearing: the live CLI posts to
        # "/v1/messages?beta=true", so an endswith("/messages") test NEVER
        # matched and CB_PROXY_INJECT_CACHE=1 was a silent no-op on the only
        # path that matters. Measured 2026-08-23: 2,741 proxied requests, zero
        # injections, and the marker census file was never even created.
        if (_INJECT_CACHE and method == "POST"
                and self.path.split("?", 1)[0].endswith("/messages")):
            body = inject_cache_control(body)
        hdrs = {}
        for k, v in self.headers.items():
            if k.lower() in ("host", "content-length", "connection", "accept-encoding"):
                continue
            hdrs[k] = v
        hdrs["Accept-Encoding"] = "identity"  # no gzip -> we can parse SSE/JSON
        conn = None
        try:
            # Resolved per request (late binding, see resolve_upstream). A bad
            # CB_PROXY_UPSTREAM raises HERE and surfaces as the 502 below, rather
            # than silently forwarding to the first-party default.
            up = resolve_upstream()
            # Pin the OpenRouter backend. Gated on the UPSTREAM rather than an
            # env flag alone: the block is meaningless to api.anthropic.com and
            # would be a stray field there. path_prefix "/api" is exactly and
            # only OpenRouter's Anthropic skin (see Upstream.forward_path).
            if (_PIN_PROVIDER and method == "POST" and up.path_prefix == "/api"
                    and self.path.split("?", 1)[0].endswith("/messages")):
                body = inject_provider_routing(body)
            # A rolling breakpoint is worse than no breakpoint on a backend that
            # caches by byte prefix; see strip_cache_control.
            if (method == "POST" and up.path_prefix == "/api"
                    and self.path.split("?", 1)[0].endswith("/messages")):
                body = strip_cache_control(body)
            # Claude ids belong on api.anthropic.com. Refuse rather than forward.
            _native = native_id_sent_to_gateway(body, up)
            if _native is not None:
                msg = json.dumps({"proxy_error": (
                    f"refusing to send the native Claude id {_native!r} to "
                    f"{up.label}: Claude models go to api.anthropic.com. Route "
                    "this slug without the proxy, or set CB_PROXY_UPSTREAM to "
                    "the first-party endpoint.")}).encode()
                self.send_response(421)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)
                return
            hdrs["Host"] = up.host_header
            if up.tls:
                conn = http.client.HTTPSConnection(up.host, up.port, timeout=600,
                                                   context=_SSL_CTX)
            else:
                conn = http.client.HTTPConnection(up.host, up.port, timeout=600)
            conn.request(method, up.forward_path(self.path), body=body, headers=hdrs)
            resp = conn.getresponse()
        except Exception as e:
            if conn is not None:
                try:  # the connect may have half-opened — never leak the socket
                    conn.close()
                except Exception:
                    pass
            msg = json.dumps({"proxy_error": str(e)}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
            return

        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() in ("transfer-encoding", "connection", "content-length", "content-encoding"):
                continue
            self.send_header(k, v)
        self.send_header("Connection", "close")
        self.end_headers()

        is_sse = "text/event-stream" in (resp.getheader("Content-Type") or "")
        sink = bytearray()
        try:
            while True:
                chunk = resp.read(2048)
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                    self.wfile.flush()
                except Exception:
                    break
                if len(sink) < 2_000_000:
                    sink += chunk
        finally:
            try:
                conn.close()
            except Exception:
                pass

        parsed = parse_response(bytes(sink), is_sse)
        rec = build_usage_record(parsed, self.path, resp.status, is_sse)
        with _lock:
            with open(USAGE_LOG, "a") as f:
                f.write(json.dumps(rec) + "\n")
        try:
            trace = build_trace_record(parsed, body)
            with _lock:
                with open(TRACE_LOG, "a") as f:
                    f.write(json.dumps(trace) + "\n")
        except Exception:
            pass


class Srv(http.server.ThreadingHTTPServer):
    daemon_threads = True


def main():  # pragma: no cover - the live server entrypoint
    USAGE_LOG.touch(exist_ok=True)
    # Resolve ONCE up front purely to fail fast: a bad CB_PROXY_UPSTREAM should
    # refuse to start, not 502 every request of a paid drive. Requests still
    # resolve it themselves (late binding).
    up = resolve_upstream()
    s = Srv(("127.0.0.1", PORT), Handler)
    print(f"anthropic proxy :{PORT} -> {up.label}  usage -> {USAGE_LOG}", flush=True)
    s.serve_forever()


if __name__ == "__main__":
    main()
