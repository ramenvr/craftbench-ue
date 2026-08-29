"""AuraMcpAdapter — drive Claude + Aura's MCP tool layer against the workspace.

The ``aura-mcp`` product entry: an external Claude reasoner whose ONLY actuator
is Aura's ``execute_unreal_python`` (dispatched through Aura's bridge), pointed
at WRITING SOURCE FILES into the open workspace project. It reuses the proven
bridge primitives in ``tools/scripts/aura_agent.py`` + ``tools/scripts/prompt.py``.

This measures Aura's TOOL LAYER, not Aura's autonomous agent (redesign spec D6).
Label every result ``aura-mcp:<model>`` — never bare "Aura".

All live dependencies (the Anthropic call, the bridge dispatch, port discovery,
tool-registry fetch) are injectable seams so the adapter is unit-testable with
no editor, no signed-in Aura, and no real API key.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from adapters.base import AgentResult

# Make the working Aura bridge primitives in tools/scripts/ importable. The
# import of `aura_agent`/`prompt` themselves is deferred to _ensure_real_deps so
# constructing the adapter (and the whole unit-test suite) never needs them.
_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


# Per-1M-token (input, output) USD rates, keyed by a substring of the model id.
# Used only to populate AgentResult.cost_usd; unknown models -> None.
_RATES = {
    "haiku": (1.0, 5.0),
    "sonnet": (3.0, 15.0),
    "opus": (15.0, 75.0),
}


@dataclass
class LoopRecord:
    """Internal result of the Aura tool-use loop, mapped to AgentResult."""
    exit_code: int
    conversation_json: str
    summary: Optional[str]
    tool_names: List[str]
    tokens_in: int
    tokens_out: int
    num_turns: int
    duration_s: float
    model: str
    # Scaffold identity + the degenerate-loop measurement. Defaulted so every
    # existing LoopRecord construction stays valid.
    tools_offered: Optional[List[str]] = None
    system_prompt_sha: Optional[str] = None
    max_consecutive_repeats: Optional[int] = None
    truncated_turns: Optional[int] = None
    provider_cost_usd: Optional[float] = None
    cache_read_tokens: Optional[int] = None
    cache_creation_tokens: Optional[int] = None
    generation_ids: Optional[List[str]] = None
    #: Distinct OpenRouter backends that served this run's turns. MORE THAN ONE is
    #: a validity alarm, not a curiosity: one slug fans out across hosts differing
    #: in quantization and version cadence, and a run served by two of them is two
    #: systems averaged into one row.
    providers_served: Optional[List[str]] = None


def _cost_for(model: str, tokens_in: int, tokens_out: int) -> Optional[float]:
    for key, (rin, rout) in _RATES.items():
        if key in model:
            return tokens_in * rin / 1_000_000 + tokens_out * rout / 1_000_000
    return None


def record_to_agent_result(
    rec: LoopRecord,
    *,
    is_mcp_tool: Optional[Callable[[str], bool]] = None,
) -> AgentResult:
    """Map the loop's internal record onto the harness AgentResult contract.

    ``is_mcp_tool`` classifies each tool name for ``mcp_tool_use_count``. The
    default answers True for everything, which is right for the aura-mcp arm
    (every Aura tool goes via the MCP bridge) and wrong for any arm whose tools
    are local — the ``bare`` adapter passes a predicate that answers False, so
    ``mcp=0`` honestly reports "this arm used no MCP tools" instead of
    mislabelling file edits as MCP traffic.
    """
    mcp_pred = is_mcp_tool if is_mcp_tool is not None else (lambda _n: True)
    return AgentResult(
        exit_code=rec.exit_code,
        transcript=rec.conversation_json,
        summary=rec.summary,
        tool_use_count=len(rec.tool_names),
        mcp_tool_use_count=sum(1 for n in rec.tool_names if mcp_pred(n)),
        tool_names=list(rec.tool_names),
        # The PROVIDER's own figure wins; the price-table estimate is the fallback
        # for endpoints that report none.
        cost_usd=(rec.provider_cost_usd if rec.provider_cost_usd is not None
                  else _cost_for(rec.model, rec.tokens_in, rec.tokens_out)),
        num_turns=rec.num_turns,
        duration_s=rec.duration_s,
        # The loop counted these and this mapping used to DROP them, so every
        # aura-mcp run recorded tokens_in/out as None while the numbers sat in
        # the LoopRecord. They are the only cross-provider-comparable usage
        # figures we have (``_cost_for`` returns None for any model whose id
        # does not contain haiku/sonnet/opus), so a token comparison across
        # arms was silently impossible. Passed through as of 2026-08-17.
        tokens_in=rec.tokens_in or None,
        tokens_out=rec.tokens_out or None,
        cache_read_tokens=rec.cache_read_tokens,
        cache_creation_tokens=rec.cache_creation_tokens,
        truncated_turns=rec.truncated_turns,
        tools_offered=rec.tools_offered,
        system_prompt_sha=rec.system_prompt_sha,
        max_consecutive_repeats=rec.max_consecutive_repeats,
        # Passed through as of 2026-08-18. Without the ids, a cost figure in a
        # paper is unfalsifiable: there is nothing to check it against.
        generation_ids=rec.generation_ids,
        providers_served=rec.providers_served,
    )


_WORKSPACE_SYSTEM = """You are an agent that edits an Unreal Engine 5.7 C++ project to satisfy a task.

You have ONE tool: execute_unreal_python. The Unreal editor is ALREADY OPEN on the exact project you must modify. Use Python to WRITE or EDIT SOURCE FILES ON DISK. Do NOT spawn actors, do NOT modify the live level, do NOT change assets.

Resolve the project directory at runtime and write files beneath it:

    import unreal, os
    proj = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    target = os.path.join(proj, 'Source', 'CraftBenchTemplate', 'SomeFile.cpp')
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, 'w') as f:
        f.write(SOURCE_TEXT)
    unreal.log('CRAFTBENCH-EDIT: wrote ' + target)

Rules:
- Only write under Source/CraftBenchTemplate/ (the agent-writable runtime module).
- NEVER write under Source/CraftBenchTests/ (the verifier module) or anywhere else.
- CRITICAL: Aura's bridge may dispatch the SAME script TWICE. Keep scripts IDEMPOTENT — overwrite files with 'w' (never append), and re-running must produce the same result.
- Read an existing file first with open(path).read() when you need to edit it rather than create it.
- Always end each script with a unreal.log('CRAFTBENCH-EDIT: <what changed>') line.

When the task is fully satisfied, reply with plain text and NO further tool call.
"""


def build_system_prompt() -> str:
    """The workspace-write system prompt for the Aura tool-layer loop."""
    return _WORKSPACE_SYSTEM


#: Per-turn output budget. 8192 was too low for a frontier model writing several
#: C++ files in one turn: it truncated mid-answer, and a truncated turn is
#: INDISTINGUISHABLE from a clean stop unless finish_reason is checked (it was not,
#: until 2026-08-18). Raised so truncation is rare; the check below is what makes it
#: safe when it still happens.
DEFAULT_MAX_TOKENS = 32000

#: Floor for a single LLM call, in seconds, and the value ``run_loop`` falls back to
#: when a caller passes none. A reasoning model on a 10 KB+ prompt legitimately takes
#: minutes; the previous hardcoded 60s cut one off and the adapter's error then
#: graded as a model FAIL. Overridable with ``CB_BARE_LLM_TIMEOUT_S``.
#:
#: NOT a total bound on the call. ``urllib`` applies it PER SOCKET READ, so a
#: provider that dribbles bytes can exceed it in aggregate — the run's own ceiling
#: bounds the drive. That is why the measured failure burned 648s under a 60s
#: setting and looked like ten retries when this loop has no retry at all: one call
#: whose reads kept arriving just inside the window.
DEFAULT_LLM_TIMEOUT_S = 300.0

#: A single call may not consume the whole ceiling — one hung request would then
#: spend the entire budget and still report 0 turns, i.e. the very failure this
#: guards against, only slower. So the per-call budget is a FRACTION of the ceiling.
LLM_TIMEOUT_CEILING_FRACTION = 3.0


def llm_timeout_for(timeout_s: float) -> float:
    """Per-call socket timeout for a run whose ceiling is ``timeout_s``.

    ONE definition, shared by every adapter that drives ``run_loop`` — the ceiling
    was hardcoded in this file while a second copy of the reasoning lived in the bare
    adapter, which is how the two would drift into different timeouts and make the
    tool-layer arms non-comparable on transport.

    Generous enough that a slow model finishes, bounded so one call cannot eat the
    drive. An explicit ``CB_BARE_LLM_TIMEOUT_S`` wins outright, so a provider we have
    not characterised needs no code change.
    """
    env = os.environ.get("CB_BARE_LLM_TIMEOUT_S", "").strip()
    if env:
        try:
            explicit = float(env)
            if explicit > 0:
                return explicit
        except ValueError:
            pass  # a typo must not silently re-impose the old 60s
    return max(DEFAULT_LLM_TIMEOUT_S,
               float(timeout_s) / LLM_TIMEOUT_CEILING_FRACTION)


#: Never hand a call a budget below this, even when the ceiling is nearly spent —
#: a 0s or negative timeout would abort instantly and look like a provider fault.
MIN_CALL_BUDGET_S = 15.0


def _call_budget(llm_timeout: Optional[float],
                 wall_deadline: Optional[float]) -> float:
    """How long this one call may take: the per-call figure, capped by what is left."""
    per_call = (llm_timeout if llm_timeout and llm_timeout > 0
                else DEFAULT_LLM_TIMEOUT_S)
    if wall_deadline is None:
        return per_call
    remaining = wall_deadline - time.monotonic()
    return max(MIN_CALL_BUDGET_S, min(per_call, remaining))


#: Per-field cap on a recorded tool input. A `write_file` carries the whole file,
#: and 450 turns of that would make the transcript larger than the submission it
#: describes. Long enough to identify a command or a path; not a content archive.
MAX_RECORDED_INPUT_CHARS = 2000


def _bounded(tool_input):
    """A tool input safe to persist: same shape, long string values truncated."""
    if not isinstance(tool_input, dict):
        return str(tool_input)[:MAX_RECORDED_INPUT_CHARS]
    out = {}
    for k, v in tool_input.items():
        if isinstance(v, str) and len(v) > MAX_RECORDED_INPUT_CHARS:
            out[k] = v[:MAX_RECORDED_INPUT_CHARS] + f"...[+{len(v) - MAX_RECORDED_INPUT_CHARS} chars]"
        else:
            out[k] = v
    return out


def max_consecutive_repeats(calls):
    """Longest run of IDENTICAL (name, input) calls back to back.

    MEASUREMENT, deliberately not an intervention. Breaking the loop for the model
    would be scaffolding, and "minimal and identical across models" is the premise
    this arm rests on — so the harness keeps serving the repeat and simply records
    how bad it got. Measured 2026-08-17: gemini-3.1-pro returned the same result
    366 times of 374 and produced nothing, at $12.26; muse-glimmer-30b 268 of 452
    at $10.08. The two most expensive runs of the day both produced zero output, so
    this number is what lets a published comparison quantify that failure mode instead of
    describing it.
    """
    best = cur = 0
    prev = None
    for c in calls:
        key = (c.get("name"), json.dumps(c.get("input"), sort_keys=True, default=str))
        cur = cur + 1 if key == prev else 1
        prev = key
        best = max(best, cur)
    return best


def run_loop(
    *,
    base_url: str,
    api_key: str,
    task_prompt: str,
    model: str,
    max_turns: int,
    tool_deadline: float,
    max_tokens: int,
    anthropic_tools: List[Dict[str, Any]],
    llm_call: Callable,
    dispatch: Callable,
    system_prompt: Optional[str] = None,
    llm_timeout: Optional[float] = None,
    wall_deadline: Optional[float] = None,
) -> LoopRecord:
    """External Claude tool-use loop over Aura's execute_unreal_python.

    ``llm_call`` matches aura_agent.call_anthropic_with_tools' signature and
    ``dispatch`` matches aura_agent.dispatch_tool_call's; both are injected so
    the loop is testable without a live Anthropic endpoint or Aura bridge.

    Everything here except those two seams is provider-neutral: turn counting,
    token accumulation, tool-name collection, the "assistant stopped calling
    tools -> done" termination, and max-turns exhaustion. ``adapters/bare.py``
    reuses this loop verbatim with a different ``llm_call``/``dispatch`` pair, so
    the arms cannot drift apart in loop semantics — which is the whole point of a
    tool-layer comparison. Keep new behaviour in the seams, not in here.

    ``system_prompt`` overrides the Aura workspace prompt. It is a PARAMETER
    rather than a call to ``build_system_prompt()`` because the system prompt is
    a silent fairness lever: two arms differing here would produce an unfair
    comparison with nothing in any log to show it. Default preserves the
    aura-mcp behaviour exactly.
    """
    t0 = time.monotonic()
    system = system_prompt if system_prompt is not None else build_system_prompt()
    offered = [t.get("name", "?") for t in (anthropic_tools or [])]
    sys_sha = hashlib.sha256(system.encode("utf-8")).hexdigest()[:16]

    def _facts():
        calls = [c for m in conversation if m.get("role") == "assistant"
                 for c in (m.get("tool_calls") or [])]
        return dict(truncated_turns=truncated_turns,
                    tools_offered=offered, system_prompt_sha=sys_sha,
                    max_consecutive_repeats=max_consecutive_repeats(calls),
                    provider_cost_usd=provider_cost,
                    cache_read_tokens=cache_read,
                    cache_creation_tokens=cache_write,
                    generation_ids=generation_ids or None,
                    providers_served=sorted(providers_seen) or None)
    msgs: List[Dict[str, Any]] = [{"role": "user", "content": task_prompt}]
    conversation: List[Dict[str, Any]] = [{"role": "user", "content": task_prompt}]
    tool_names: List[str] = []
    tokens_in = tokens_out = 0
    # Provider-reported accounting, accumulated. None stays None when the endpoint
    # reports nothing (the Aura bridge does not), so "unknown" never becomes 0.
    provider_cost = None
    cache_read = cache_write = None
    generation_ids: List[str] = []
    providers_seen: set = set()
    summary: Optional[str] = None
    num_turns = 0
    stop_reason = "max_turns"
    truncated_turns = 0
    run_id = f"aura-mcp-{uuid.uuid4().hex[:8]}"

    for turn_n in range(max_turns):
        # WALL CLOCK, checked at the turn boundary. Until 2026-08-17 the loop's
        # only bound was the turn cap, so `--ceiling` bounded nothing: a measured
        # bare drive ran 2199s against a 600s ceiling and 105 turns against an
        # uncapped turn count. Across a 500-run sweep one wedged drive is
        # unbounded machine time, and the turn cap cannot substitute — a slow model
        # blows the clock long before it blows 1000 turns.
        #
        # Checked BETWEEN turns, never mid-call: aborting a request in flight would
        # discard work the model already paid for and, worse, produce the 0-turn
        # shape `_agent_never_ran` reads as a transport fault — turning a slow model
        # into a NON-graded run, i.e. a denominator opt-out earned by being slow.
        if wall_deadline is not None and time.monotonic() >= wall_deadline:
            stop_reason = "wall_clock"
            break
        num_turns += 1
        try:
            resp = llm_call(
                api_key=api_key, model=model, system=system,
                messages=msgs, tools=anthropic_tools,
                max_tokens=max_tokens,
                # Was a hardcoded 60.0 until 2026-08-17: it cut a slow model off
                # mid-answer and the adapter's error then graded as a model FAIL.
                # Because this loop is SHARED, that ceiling applied to aura-mcp too,
                # which now matters there since it can route non-Claude models.
                #
                # Clamped to the REMAINING ceiling: the turn-boundary check above
                # cannot interrupt a call already in flight, so without the clamp one
                # hung call overshoots without bound (measured: 65 minutes inside ONE
                # call against a 20-minute ceiling, nothing written).
                # bare_wire._post_json enforces it as a TOTAL wall clock, because
                # urllib's own timeout is per-READ and resets on every byte received.
                timeout=_call_budget(llm_timeout, wall_deadline),
            )
        except Exception as exc:  # noqa: BLE001
            # PRESERVE what the model already did. Letting this escape discarded
            # every count, and `bare._fail` then reported num_turns=0 /
            # tool_use_count=0 / no tokens — so `run._agent_never_ran` saw four
            # zeros and pulled a drive that had genuinely worked OUT of the
            # denominator. Measured 2026-08-17: grok-4.6 drove the full 1200s
            # ceiling and recorded "0 turns, never ran".
            #
            # That is the bug this file just fixed, inverted: not a fault charged to
            # the model, but real model work excused as a fault. Returning the true
            # counts is what makes the four-zeros guard mean something — it now fires
            # only when nothing WAS attempted, which is the claim it makes.
            # The failing turn did not complete, so it is not counted — and the
            # summary must agree with the record, or the two disagree about how far
            # the drive got.
            completed = num_turns - 1
            summary = summary or f"transport error after {completed} turn(s): {exc}"
            return LoopRecord(
                exit_code=1, conversation_json=json.dumps(conversation),
                summary=summary, tool_names=tool_names,
                tokens_in=tokens_in, tokens_out=tokens_out,
                num_turns=completed, duration_s=time.monotonic() - t0,
                model=model, **_facts(),
            )
        usage = resp.get("usage", {})
        tokens_in += int(usage.get("input_tokens", 0))
        tokens_out += int(usage.get("output_tokens", 0))
        if usage.get("cost_usd") is not None:
            provider_cost = (provider_cost or 0.0) + float(usage["cost_usd"])
        if usage.get("cache_read_tokens") is not None:
            cache_read = (cache_read or 0) + int(usage["cache_read_tokens"])
        if usage.get("cache_creation_tokens") is not None:
            cache_write = (cache_write or 0) + int(usage["cache_creation_tokens"])
        if resp.get("generation_id"):
            generation_ids.append(str(resp["generation_id"]))
        if resp.get("provider"):
            providers_seen.add(str(resp["provider"]))
        content_blocks = resp.get("content", [])
        text_parts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
        tool_uses = [b for b in content_blocks if b.get("type") == "tool_use"]
        assistant_text = "\n".join(text_parts).strip()
        # Record WHAT WAS ASKED, not only what came back. Until 2026-08-17 the
        # transcript held role+content only, so a run could show "bash x374" with no
        # way to learn what those 374 commands were — which makes trajectory analysis
        # impossible after the fact, and it is the record, not the run, that a report
        # cites. Found while diagnosing a gemini-3.1-pro drive that issued the SAME
        # call 366 times: the pathology was visible, its content was not.
        conversation.append({
            "role": "assistant",
            "content": assistant_text or "(no text)",
            "turn": num_turns,
            "tool_calls": [
                {"name": tu.get("name", "?"), "input": _bounded(tu.get("input", {}))}
                for tu in tool_uses
            ],
        })
        msgs.append({"role": "assistant", "content": content_blocks})

        # A TRUNCATED TURN IS NOT A FINISHED TURN. finish_reason="length" with no
        # tool call looks exactly like "the model stopped calling tools", i.e. the
        # loop's own done-condition — so without this check our max_tokens silently
        # ended the drive and the verdict was charged to the model. Give it another
        # turn to finish the thought; the turn cap and the wall clock still bound it.
        if not tool_uses and resp.get("finish_reason") == "length":
            truncated_turns += 1
            conversation.append({
                "role": "user", "turn": num_turns,
                "content": "(your previous turn was cut off at the output limit — "
                           "continue from where you stopped)"})
            msgs.append({"role": "user", "content":
                         "Your previous turn was cut off at the output limit. "
                         "Continue from where you stopped."})
            continue

        if not tool_uses:
            summary = assistant_text or summary
            return LoopRecord(
                exit_code=0, conversation_json=json.dumps(conversation),
                summary=summary, tool_names=tool_names,
                tokens_in=tokens_in, tokens_out=tokens_out,
                num_turns=num_turns, duration_s=time.monotonic() - t0, model=model,
                **_facts(),
            )

        tool_results: List[Dict[str, Any]] = []
        for tu in tool_uses:
            name = tu.get("name", "?")
            tool_names.append(name)
            res = dispatch(
                base_url, name, tu.get("input", {}),
                description=f"{run_id}-t{turn_n}-{uuid.uuid4().hex[:6]}",
                deadline_seconds=tool_deadline,
            )
            conversation.append({
                "role": "tool_result",
                "turn": num_turns,
                "name": name,
                "is_error": not res.get("bSuccess", False),
                "content": res.get("result_text") or res.get("error") or "",
            })
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.get("id", "?"),
                "content": (res.get("result_text") or res.get("error") or "(no result)")[:2000],
                "is_error": not res.get("bSuccess", False),
            })
        msgs.append({"role": "user", "content": tool_results})

    # Budget exhausted — turns or wall clock. exit_code stays 0 and the record is
    # GRADED: running out of the disclosed budget is a model outcome, identical for
    # every arm, and whatever it wrote by then is its answer. Routing it non-graded
    # would let a slow model leave the denominator by being slow.
    _exhausted = ("(wall-clock ceiling reached)" if stop_reason == "wall_clock"
                  else "(max turns reached)")
    return LoopRecord(
        exit_code=0, conversation_json=json.dumps(conversation),
        summary=summary or _exhausted, tool_names=tool_names,
        tokens_in=tokens_in, tokens_out=tokens_out,
        num_turns=num_turns, duration_s=time.monotonic() - t0, model=model,
        **_facts(),
    )


# The legacy ``aura-mcp-bridge`` adapter class lived here. It was removed for the
# open-source release: it drove a proprietary in-editor bridge and its deferred
# imports resolved to scripts that are not part of this repository. The shared
# agent-loop helpers ABOVE this line are arm-generic and stay -- adapters/bare.py
# and run.py both import them. See THIRD-PARTY.md.
