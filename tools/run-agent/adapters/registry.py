"""Adapter slug parser for the three CraftBench products.

All three coding products run through the SAME `claude -p` harness so the
comparison isolates the tool-layer (the only variable):

  - claude-p[:<model>]          Baseline: a strong generalist with generic file
                                edits and NO Aura MCP (--strict-mcp-config, no
                                --mcp-config → zero MCP servers).
  - aura-mcp[:<model>]          Aura's tool-layer: the model is given ONLY Aura's
                                MCP servers and is DENIED the generic actuators
                                (Write/Edit/Bash/...), so it can change the project
                                only THROUGH Aura's tools (bp_agent, edit_cpp_file,
                                create_edit_material, …). The authentic measurement.
                                DISCLOSED BUT NOT REPRODUCIBLE from this public
                                repository — the dispatch and the exact tool
                                policy are here in full, the private plugin the
                                config points at is not. See the branch below.
  - unreal-mcp[:<model>]        "Claude Code + Epic's Unreal MCP": Claude's own
                                file/shell tools stay ENABLED, plus Epic's
                                first-party in-editor MCP server (UE 5.8
                                `ModelContextProtocol` + `AllToolsets`, HTTP
                                :8000/mcp). UNLIKE aura-mcp we do NOT strip
                                Write/Edit/Bash — Epic's MCP has no C++ source
                                tool (aura-mcp keeps C++ editing via Aura's own
                                edit_cpp_file), so Claude edits the source and the
                                MCP drives the editor. Only orchestration/web tools
                                are denied. Comparison: claude-p (no editor) vs
                                unreal-mcp (Claude + Epic editor) vs aura-mcp
                                (Aura's tools).
                                Requires the headless editor started with
                                -ModelContextProtocolStartServer (see
                                aura_rig.unreal_mcp_stack / `cb eval`).

Two further backends exist for support work and are NOT arms of the published
comparison: ``bare:<provider/model>`` (our own minimal loop plus five local file
tools, over any OpenAI-compatible endpoint) and ``openrouter:<model>`` (the same
Claude CLI harness pointed at OpenRouter's Anthropic-compatible skin). Both are
documented on their own branches below.

REMOVED FOR THE PUBLIC RELEASE. Four slugs this file used to dispatch —
``aura-product``, ``aura-agent``, ``aura-baseline`` and ``aura-mcp-bridge`` —
drove Aura's PRIVATE product/agent surfaces: a CDP attach to the packaged client,
and a local server-side loop reached over HTTP. Their adapters, their drivers and
the login step that authenticated them are not part of this repository, so the
slugs are refused here BY NAME (``_REMOVED_BACKENDS``) rather than left as
branches that would die on an ImportError from a module that no longer ships.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional

from adapters.base import AgentAdapter
from adapters.claude_p import ClaudePAdapter
from adapters.aura_mcp_config import resolve_aura_mcp_config
from adapters.unreal_mcp_config import resolve_unreal_mcp_config

# Aura's two MCP servers (unreal_editor + unreal_inspector). The config is
# RESOLVED PER MACHINE at adapter-construction time (interpreter + script paths
# off the live Aura plugin) rather than read from a frozen, machine-specific
# file — see adapters/aura_mcp_config.py. The committed aura_mcp.json is only a
# last-resort fallback when the plugin can't be located.

# Tools an aura-mcp agent must NOT use, so it can change the project ONLY through
# Aura's MCP tools and so the measurement isn't a Claude-Code agent in disguise.
# Kept allowed: Read/Glob/Grep/LSP (read-only inspection) + ToolSearch (Aura ships
# ~138 tools which arrive DEFERRED, so the agent must search to reach them).
# Orchestration / subagent / web tools that pollute the "model + tool layer"
# measurement or bypass the sandbox — denied for BOTH mcp backends. Agent/Task
# would let the agent spawn an UNrestricted child that bypasses the denylist (a
# real leak seen in the first spike); Web* would let it look up answers.
_DENIED_ORCHESTRATION = [
    "Agent", "Task", "TaskCreate", "TaskUpdate", "TaskGet", "TaskList",
    "TaskOutput", "TaskStop", "Monitor", "Skill", "Workflow",
    "EnterPlanMode", "ExitPlanMode", "EnterWorktree", "ExitWorktree",
    "WebFetch", "WebSearch", "ScheduleWakeup",
    # SELF-DESTRUCT (measured 2026-08-06, 5 reps lost across 3 models):
    # recompile_unreal_project calls shutdown_headless, waits for the editor to
    # fully exit, runs UBT, and expects the CALLER to relaunch
    # (Aura/MCP/base_aura_mcp.py:7278). Agents that skip the relaunch end their
    # own session; the drive reports EDITOR-GONE ~60s later. Denying it costs
    # NOTHING measurable: the agent-side compile never reaches a verdict — the
    # verifier always builds the submission itself in a clean workdir (L1).
    # The same rule is ALSO stated in prose in tasks/PREAMBLE.md, which every
    # backend shares: a lane whose tool set the harness does not own has nothing
    # stronger than the prompt to bind it.
    "recompile_unreal_project",
    # Same self-destruct family, added 2026-08-14. The preamble has banned this
    # in PROSE since it was written, but nothing enforced it — so on the two
    # lanes that CAN enforce, it was a request rather than a rule. Its
    # `interactive` parameter defaults to true, so a relaunch opens a WINDOWED
    # editor on whoever's desktop is attached, and the resulting process is
    # outside the harness's lifecycle: it can outlive the session and collide
    # with the next one. Denying costs nothing — the harness owns editor
    # restarts (stack.restart_editor_via_client) and compiles the submission
    # itself in a clean workdir.
    #
    # THE PRINCIPLE (owner, 2026-08-14): keep ONE preamble for every backend so
    # runs stay comparable, and push backend-specific tool policy into the
    # harness layer that can actually enforce it. Prose in a shared prompt is
    # the weakest form of both — it costs every backend tokens and binds none
    # of them.
    "relaunch_editor",
    # Verification-orchestrator sub-agent, added 2026-08-19. Until today this
    # was PROSE-ONLY in the shared preamble ("do not call verification/testing
    # orchestrator sub-agents") — i.e. on the two lanes that CAN enforce, it
    # was a request rather than a rule. Denying costs nothing measurable: the
    # verifier's own fixtures are the only verification that reaches a verdict,
    # and the agent keeps direct tool calls for self-checks.
    "verification_agent",
]

# aura-mcp additionally denies the generic file/shell actuators, so the agent
# changes the project ONLY through Aura's MCP tools (which INCLUDE edit_cpp_file,
# create_edit_material, …) — otherwise it's a Claude-Code agent in disguise and
# the measurement isn't "Aura's tool layer". Kept allowed: Read/Glob/Grep + the
# deferred ToolSearch (Aura ships ~138 tools that arrive deferred).
_DENIED_GENERIC_ACTUATORS = [
    "Write", "Edit", "MultiEdit", "Bash", "NotebookEdit",
    *_DENIED_ORCHESTRATION,
]


def _unquote(v: str) -> str:
    """Strip surrounding quotes from a .env value.

    ``OPENROUTER_API_KEY="sk-or-..."`` is the common mistake; the quotes survive
    into the Bearer header and 401.
    """
    return v.strip().strip('"').strip("'") if v else v


def route_via_openrouter(model: Optional[str]) -> Optional[Dict[str, str]]:
    """Env overrides if this model routes through OpenRouter, else ``None``.

    The single decision point, so the id guard cannot be applied on one backend and
    forgotten on another: any model reaching OpenRouter — through ``openrouter``,
    ``unreal-mcp`` or ``aura-mcp`` — is refused here if it is an alias or a
    non-comparable serving variant (``:free``, ``:batch``), pre-spend.

    ASYMMETRY worth knowing when reading results: the ``bare`` arm additionally
    asserts on every turn that the model which ANSWERED is the one pinned. These
    Claude-CLI backends cannot — the served model name is not surfaced to us
    through the CLI — so an id guard is all the protection they get. A silent
    gateway substitution would be invisible on these two arms and caught on ``bare``.
    """
    if not is_openrouter_model_id(model):
        return None
    return openrouter_transport(model)


#: TRUE context windows, snapshotted from OpenRouter's catalog 2026-08-20 (the
#: `context_length` field). DATED like §9's price sheet and for the same reason:
#: the number must come from a recorded snapshot, never from a remembered one.
#:
#: WHY THIS EXISTS (measured 2026-08-20, right after the CLAUDE_CONFIG_DIR fix
#: made these ids reachable again). The CLI does not RECOGNIZE a slashed
#: non-Anthropic id, so it assumes a 200k window and auto-compacts there, while
#: `claude-sonnet-5` is recognized and gets its true 1M. Left alone that is a
#: FAIRNESS CONFOUND aimed squarely at §5's monoculture defense: measured drives
#: run ~0.35M input tokens, so every non-Anthropic panel model would compact
#: mid-drive and the fixed model would not — and the resulting score gap would
#: read as a model difference. Owner decision the same day: give each model its
#: REAL window.
#:
#: A model ABSENT from this table deliberately gets no override, so it keeps
#: today's behaviour and the CLI prints its own "not a model this version
#: recognizes" warning into the run log — a visible signal rather than a silent
#: 200k cap. Refresh with:
#:     GET https://openrouter.ai/api/v1/models -> .data[].context_length
_MODEL_CONTEXT_WINDOW = {
    # §5 pinned panel
    "anthropic/claude-sonnet-5":       1_000_000,
    "deepseek/deepseek-v4-pro-0813":   1_048_576,
    "x-ai/grok-4.6":                     500_000,
    "google/gemini-3.7-flash":         1_048_576,
    # §5 named reserve
    "qwen/qwen3.8-max":                1_000_000,
    # calibration-only ids that have appeared in briefs; same snapshot
    "anthropic/claude-opus-5":         1_000_000,
    "deepseek/deepseek-v4-flash-0731": 1_310_720,
    "openai/gpt-5.6-terra":            1_050_000,
    "z-ai/glm-5.3":                    1_048_576,
    "z-ai/glm-5.3-flash":              1_310_720,
    "meta/muse-spark-1.2":             1_048_576,
}


def openrouter_transport(model: Optional[str]) -> Dict[str, str]:
    """Validate the id, then return the OpenRouter transport env. Unconditional.

    For the ``openrouter`` backend, which routes through the gateway whatever the
    slug looks like. ``route_via_openrouter`` is the conditional wrapper the two MCP
    backends use. Both funnel through here so the id guard has exactly one home —
    the first cut applied it only to the MCP branches and left the ``openrouter``
    baseline able to pin ``:free``, which a test caught.

    This is also where the per-model CONTEXT WINDOW is pinned
    (``_MODEL_CONTEXT_WINDOW``): it is the one funnel that both knows the model id
    and feeds every CLI backend, so the window cannot be set on one arm and
    forgotten on another — the same argument that put the id guard here.
    """
    from adapters.bare_wire import validate_model_id
    if model:
        validate_model_id(model)
    env = openrouter_env_overrides()
    window = _MODEL_CONTEXT_WINDOW.get((model or "").strip())
    if window:
        env["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] = str(window)
    return env


def is_openrouter_model_id(model: Optional[str]) -> bool:
    """Is this slug's model an OpenRouter id rather than a native Anthropic one?

    OpenRouter ids are ``provider/model`` (``deepseek/deepseek-v4-flash``);
    the ids Claude Code takes natively have no slash (``sonnet-5``,
    ``claude-sonnet-4-5-20250929``). So the slash IS the routing decision, which
    keeps every existing ``unreal-mcp:sonnet-5`` / ``aura-mcp:<claude>`` slug on
    exactly the path it used before this existed — no behaviour change without a
    slash in the slug.
    """
    return bool(model) and "/" in model


#: OPT-IN ONLY. Route the Claude Code CLI through the local logging proxy
#: (aura_rig.proxy) instead of straight at the gateway. Unset -> no routing change
#: for any backend, which is why the default path is untouched by this.
PROXY_OPENROUTER_ENV = "CB_PROXY_OPENROUTER"


def _flag_on(name: str) -> bool:
    """Same truthiness convention as the proxy's own CB_PROXY_INJECT_CACHE."""
    return os.environ.get(name, "") not in ("", "0", "false", "no")


def _same_endpoint(a: str, b: str) -> bool:
    """Endpoint equality that ignores a trailing slash and host case."""
    return (a or "").strip().rstrip("/").lower() == (b or "").strip().rstrip("/").lower()


def proxy_base_url_for(direct_base: str) -> str:
    """ANTHROPIC_BASE_URL pointing at the local proxy — or RAISE saying why not.

    WHY THIS EXISTS (measured 2026-08-18): behind OpenRouter the Claude Code CLI's
    ``total_cost_usd`` is wrong. The CLI prices each call ITSELF at Anthropic
    first-party rates and cannot see the gateway — a probe of 55,351 cache-create
    + 2 in + 4 out reported $0.20763225, which is Anthropic's first-party list
    applied term by term::

        55351 * $3.75/1M  (cache write) = $0.20756625
        +   2 * $3.00/1M  (fresh input) = $0.00000600
        +   4 * $15.00/1M (output)      = $0.00006000
                                        = $0.20763225

    CORRECTED 2026-08-18 (adversarial review): this comment used to say the figure
    was "exactly 55351 * $3.75/1M". That term alone is $0.20756625 — the
    reconciliation holds, the attribution did not. OpenRouter charges less, so the
    CLI OVER-reports, and the true number (``usage.cost``) plus the ``gen-``
    ledger id are only visible on the wire. The proxy is the only seam that sees
    them.

    THREE FAIL-CLOSED REFUSALS, all for the same reason: a run that silently went
    direct still LOOKS measured, and would publish the CLI's wrong number as if it
    were the provider's.
      1. proxy module not importable -> refuse;
      2. no proxy answering /healthz (or too old to report an upstream) -> refuse;
      3. the proxy IS up but tee-ing a DIFFERENT upstream -> refuse. This is not
         hypothetical: :41299 is ONE shared instance, and a first-party run
         leaves it pinned at api.anthropic.com, so feeding OpenRouter traffic
         into it would ship an OpenRouter key to Anthropic (401) — or, in the
         other direction, first-party traffic to a gateway it has no account on.

    KNOWN GAP — TOCTOU, deliberately not closed. All three refusals run ONCE, from
    ``openrouter_env_overrides()`` at ``make_adapter()`` time; the returned
    ``ANTHROPIC_BASE_URL`` is then handed to a CLI subprocess that may not make its
    first call for minutes. If the operator restarts the :41299 proxy with a
    different ``CB_PROXY_UPSTREAM`` in that window, this check has already passed
    and nothing re-reads it, so the drive silently tees to the new target. Not
    over-engineered away because the proxy resolves its upstream per REQUEST
    (``proxy.resolve_upstream``), so the damage is bounded and DETECTABLE after
    the fact: the recorded usage lines carry ``cost_usd``/``generation_id`` only
    behind a gateway, and a mid-drive switch to api.anthropic.com shows up as a
    window whose ``cost_partial`` is True with ``gen-`` ids missing for part of the
    run. The durable fix, if this ever bites, is to re-assert
    ``reported_upstream()`` at drive START (inside the adapter) rather than at
    construction — not to poll.
    """
    try:
        from aura_rig import proxy as _proxy
    except Exception as e:
        raise ValueError(
            f"{PROXY_OPENROUTER_ENV} is set but aura_rig.proxy could not be "
            f"imported ({e}); unset it or fix the install."
        ) from None
    reported = _proxy.reported_upstream()
    if not reported:
        raise ValueError(
            f"{PROXY_OPENROUTER_ENV} is set but no logging proxy answered "
            f"http://127.0.0.1:{_proxy.PORT}/healthz with an upstream. Start it "
            f"with {_proxy.UPSTREAM_ENV}={direct_base} "
            f"(python -m aura_rig.proxy), or unset {PROXY_OPENROUTER_ENV}. "
            "Refusing to route direct: the run would record the CLI's "
            "first-party-priced cost as though it were measured."
        )
    if not _same_endpoint(reported, direct_base):
        raise ValueError(
            f"{PROXY_OPENROUTER_ENV} is set but the proxy on "
            f"127.0.0.1:{_proxy.PORT} forwards to {reported!r}, not "
            f"{direct_base!r}. Restart it with "
            f"{_proxy.UPSTREAM_ENV}={direct_base} (note :41299 is ONE shared "
            "instance — another run may have left it pinned at api.anthropic.com)."
        )
    # No "/v1": the Anthropic SDK appends "/v1/messages" itself, exactly as it
    # does for the direct "/api" base above.
    return _proxy.CLI_BASE_URL


def openrouter_env_overrides() -> Dict[str, str]:
    """Env that points the Claude Code CLI at OpenRouter's Anthropic-compatible skin.

    ONE definition, used by every backend that can route through OpenRouter
    (``openrouter``, and — since 2026-08-17 — ``unreal-mcp`` / ``aura-mcp`` when the
    slug carries an OpenRouter id). Three copies of this dict is how the two MCP
    backends would drift into authenticating differently from the baseline, which a
    tool-layer comparison cannot survive: the transport must be the constant.

    Base is OpenRouter's ANTHROPIC endpoint (``/api``, NOT the OpenAI-style
    ``/api/v1``) — the Anthropic SDK appends ``/v1/messages`` itself, so ``/api/v1``
    yields ``/api/v1/v1/messages``.

    ``CB_PROXY_OPENROUTER=1`` (opt-in, off by default) swaps that base for the
    local logging proxy so the run can record OpenRouter's OWN per-call cost and
    generation ids; see ``proxy_base_url_for``.
    """
    base_url = _unquote(os.environ.get(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api"))
    key = _unquote(os.environ.get("OPENROUTER_API_KEY") or "")
    if not key:
        raise ValueError(
            "routing through OpenRouter requires the OPENROUTER_API_KEY "
            "environment variable (set it in your .env). Optionally set "
            f"OPENROUTER_BASE_URL (default: {base_url})."
        )
    # OPT-IN (CB_PROXY_OPENROUTER=1): tee through the local logging proxy so the
    # run can record OpenRouter's OWN cost + generation ids instead of the CLI's
    # first-party-priced estimate. Unset -> base_url is untouched and every lane
    # routes exactly as it did before. Placed AFTER the key check so the far more
    # common missing-key error still wins; raises rather than falling back.
    if _flag_on(PROXY_OPENROUTER_ENV):
        base_url = proxy_base_url_for(base_url)
    # Isolate the gateway subprocess from the operator's ~/.claude LOGIN STATE.
    # Measured 2026-08-20 (the night before task lock): every non-Anthropic
    # slashed id started dying in 6.1s with the CLI's client-side
    # "[claude-code:unrecognized_model]" — SAME binary (2.1.235) that ran the
    # same ids fine the previous afternoon, so not a version change; the flip
    # correlated with the operator's /login that evening, i.e. the CLI's model
    # gate rides the logged-in account's server-side config. With a config dir
    # that has no login, the id goes through and OpenRouter answers (verified:
    # "unrecognized" with the user config, OK with an isolated one, same
    # binary, same env, minutes apart). Scoped HERE deliberately: only the
    # openrouter-routed transport is isolated — native-id runs (claude-p:
    # sonnet-5) keep the login they bill through. The dir is stable across
    # runs so the CLI's one-time state writes don't re-run per cell.
    # `Path.home()` RAISES (not returns falsy) when neither LOCALAPPDATA nor any
    # home variable is set, so it cannot sit behind an `or` — the first cut did,
    # and every test that builds a clean env with `patch.dict(..., clear=True)`
    # died as `RuntimeError: Could not determine home directory` from inside the
    # transport (8 errors in this commit's own regression file, 2026-08-20).
    # Production never saw it because LOCALAPPDATA is always set on Windows,
    # which is exactly why it needs a guard rather than a fix-when-it-bites: the
    # environments that lack it are a cleared test env, a service account, and
    # Linux/CI — i.e. everywhere a fresh machine would first meet this code.
    _root = os.environ.get("LOCALAPPDATA")
    if not _root:
        try:
            _root = str(Path.home())
        except (RuntimeError, OSError):
            _root = tempfile.gettempdir()
    config_dir = Path(_root) / "CraftBench" / "claude-openrouter-config"
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass  # CLI creates it itself on first use
    return {
        "ANTHROPIC_BASE_URL": base_url,
        "CLAUDE_CONFIG_DIR": str(config_dir),
        # Claude Code sends ANTHROPIC_AUTH_TOKEN as the `Authorization: Bearer`
        # header, which is what OpenRouter's gateway requires. ANTHROPIC_API_KEY
        # (the native x-api-key path) is IGNORED by OpenRouter and collides with a
        # logged-in session -> 401 "Missing Authentication header", so blank it for
        # this subprocess (OpenRouter's own docs say to leave it empty).
        "ANTHROPIC_AUTH_TOKEN": key,
        "ANTHROPIC_API_KEY": "",
    }


#: Slugs this file used to dispatch and deliberately no longer does. Each drove
#: one of Aura's PRIVATE surfaces — the packaged client over CDP, or the local
#: server-side agent loop over HTTP — through an adapter, a driver and a login
#: step that are not part of the public release.
#:
#: Kept as a NAMED refusal rather than dropped silently, for the same reason the
#: rest of this module carries its history: an operator arriving with an older
#: command line, brief or eval sheet gets told what happened to the slug, which a
#: bare "Unknown adapter backend" would not do. This table is also the honest
#: record of which arms once existed here.
_REMOVED_BACKENDS = {
    "aura-product": "the packaged Aura client, driven over CDP",
    "aura-agent": "Aura's local server-side autonomous loop, driven over HTTP",
    "aura-baseline": "an alias of aura-agent",
    "aura-mcp-bridge": "the legacy external-bridge loop (execute_unreal_python only)",
}

#: One-shot latch so the aura-mcp notice below is printed once per process rather
#: than once per constructed adapter (a batch builds one per cell).
_WARNED_AURA_MCP_UNAVAILABLE = False


def _warn_if_aura_mcp_unresolvable(log=None) -> bool:
    """Say plainly, ONCE, that this clone cannot run the aura-mcp arm. Never raises.

    THE OPTION-A CONTRACT. The aura-mcp arm stays DISPATCHABLE from the public
    repository — its construction below IS the disclosure, and the asymmetry it
    encodes (Aura's MCP config plus ``_DENIED_GENERIC_ACTUATORS``, against
    unreal-mcp's ``_DENIED_ORCHESTRATION``) is the measurement itself, so it has
    to stay readable, diff-able and unit-testable from a clone that will never
    execute it. What is NOT here is everything the arm needs to actually RUN:
    Aura's UE plugin (which supplies the two MCP servers the generated config
    points at) and the account bring-up that authenticates them.

    So the failure is reported HERE, in words, at the moment the arm is selected.
    ``resolve_aura_mcp_config`` is deliberately non-raising and falls back to the
    committed legacy config, which means without this notice the first sign of
    trouble is ``claude -p`` failing minutes later on a stdio server whose
    ``command`` does not exist — a symptom that reads like a harness bug rather
    than a missing private dependency.

    Returns True if the notice was printed (the plugin is absent), else False.
    """
    global _WARNED_AURA_MCP_UNAVAILABLE
    if _WARNED_AURA_MCP_UNAVAILABLE:
        return False
    from adapters.aura_mcp_config import resolve_aura_plugin_dir
    try:
        if resolve_aura_plugin_dir() is not None:
            return False
    except OSError:
        pass  # unreadable candidate path — treat as absent and say so
    _WARNED_AURA_MCP_UNAVAILABLE = True
    log = log or (lambda m: print(m, file=sys.stderr, flush=True))
    log(
        "NOTE  aura-mcp is DISCLOSED BUT NOT REPRODUCIBLE from this repository. "
        "The arm's dispatch, its MCP config resolution and its exact tool policy "
        "ship here in full, but the Aura UE plugin that provides the two MCP "
        "servers does not, and neither does the account bring-up that "
        "authenticates them. No Aura plugin was found on this machine (set "
        "CB_AURA_PLUGIN if you have one), so this adapter is constructed for "
        "inspection only and a drive WILL fail when `claude -p` tries to launch "
        "the MCP servers. Use claude-p or unreal-mcp to reproduce results."
    )
    return True


def make_adapter(slug: str, *, gateway: Optional[str] = None,
                 token: Optional[str] = None) -> AgentAdapter:
    """Parse a "<backend>[:<model>]" slug and return an instantiated adapter.

    ``gateway`` / ``token`` are an ADDITIVE transport seam whose only consumer was
    the removed aura-agent adapter; every surviving backend takes its transport
    from the slug and the environment, so today they are accepted and ignored.
    Kept in the signature deliberately: run.py passes CB_GATEWAY / CB_BEARER
    unconditionally at both of its call sites, so dropping the parameters here
    would turn a harmless no-op into a TypeError on every run. Removing them is a
    change for run.py's owner to make first."""
    if ":" in slug:
        backend, model = slug.split(":", 1)
    else:
        backend, model = slug, None

    if backend == "claude-p":
        # Baseline: clean generalist — strict MCP with no config = zero MCP servers,
        # so it does NOT silently inherit the operator's Aura MCP from ~/.claude.json.
        return ClaudePAdapter(model=model, strict_mcp=True)

    if backend == "aura-mcp":
        # Authentic Aura tool-layer: only Aura's MCP servers, generic actuators denied.
        # An OpenRouter-shaped model routes the REASONER through OpenRouter while the
        # tool layer stays identical — that is what makes the full
        # {model} x {tool layer} cross measurable instead of two separate axes.
        #
        # DISCLOSED BUT NOT REPRODUCIBLE from this repository. Everything that
        # DEFINES the arm is right here and must stay exactly as it is — the
        # measurement is the difference between this branch and the unreal-mcp
        # branch below, so a "simplification" that aligned their flags would
        # delete the result, not tidy it. Everything that RUNS the arm (Aura's UE
        # plugin, the account bring-up) is private and absent; the helper says so
        # once, in words, instead of letting it surface as a mystery MCP launch
        # failure minutes into a paid drive.
        _warn_if_aura_mcp_unresolvable()
        return ClaudePAdapter(
            model=model,
            mcp_config=resolve_aura_mcp_config(),
            strict_mcp=True,
            disallowed_tools=_DENIED_GENERIC_ACTUATORS,
            env_overrides=route_via_openrouter(model),
            name=f"aura-mcp:{model or 'default'}",
        )

    if backend == "unreal-mcp":
        # "Claude Code + Epic's Unreal MCP": Claude's own file/shell tools stay
        # ENABLED and Epic's in-editor MCP server (HTTP :8000) is added on top.
        # UNLIKE aura-mcp we do NOT strip Write/Edit/Bash — Epic's MCP has no C++
        # source tool (aura-mcp keeps C++ editing via Aura's own edit_cpp_file),
        # so stripping the file tools would leave it unable to solve source tasks
        # at all. Claude edits the C++, the MCP drives the editor (compile, PIE,
        # asset authoring). Only orchestration/web tools are denied.
        return ClaudePAdapter(
            model=model,
            mcp_config=resolve_unreal_mcp_config(),
            strict_mcp=True,
            disallowed_tools=_DENIED_ORCHESTRATION,
            env_overrides=route_via_openrouter(model),
            name=f"unreal-mcp:{model or 'default'}",
        )

    if backend == "bare":
        # The no-scaffold, provider-neutral arm: our own minimal loop (shared
        # with aura-mcp via aura_mcp.run_loop) plus five local file tools, over
        # any OpenAI-compatible endpoint. Unlike `openrouter` — which is the
        # Claude Code CLI pointed elsewhere, and therefore measures a model
        # INSIDE Anthropic's agent harness — this measures the model inside a
        # scaffold we control and disclose. That is the difference the tool-layer
        # comparison rests on, so do not collapse the two backends.
        #
        # No editor: reachable tasks are those whose deliverable is a file it can
        # write (the `cpp` basket + the plain-text-report `python` tasks). See the
        # scope note in adapters/bare.py.
        from adapters.bare import BareAdapter
        return BareAdapter(model=model or "")

    if backend == "openrouter":
        # Generalist baseline via OpenRouter: reuse the SAME Claude CLI harness
        # (clean generalist, no Aura MCP) but point it at OpenRouter's
        # Anthropic-compatible "skin" via env overrides. The slug's model is
        # OpenRouter's model id (e.g. "openai/gpt-5", "anthropic/claude-3.5-sonnet").
        # NOTE: the base is OpenRouter's Anthropic endpoint ("/api", NOT the
        # OpenAI-style "/api/v1") — the Anthropic SDK/CLI appends "/v1/messages"
        # itself, so "/api/v1" would wrongly produce "/api/v1/v1/messages".
        # Transport/auth is `openrouter_env_overrides()` — the SAME function the two
        # MCP backends use, deliberately, so this arm and those differ only in tool
        # layer. It fails loud when OPENROUTER_API_KEY is unset.
        return ClaudePAdapter(
            model=model,
            strict_mcp=True,
            env_overrides=openrouter_transport(model),
            name=f"openrouter:{model or 'default'}",
        )

    if backend in _REMOVED_BACKENDS:
        # A private-surface slug. Refuse BY NAME and say what happened to it:
        # these branches used to construct adapters that no longer ship, and the
        # honest failure is this sentence — not an ImportError raised several
        # frames down by a lazy import of a module that is not in this repo.
        raise ValueError(
            f"adapter backend {backend!r} ({_REMOVED_BACKENDS[backend]}) is not "
            f"part of the public CraftBench-UE release, and slug {slug!r} cannot "
            "be run here. Its adapter, its driver and the login step that "
            "authenticated it drove Aura's private product surfaces and were "
            "removed with them; there is no drop-in replacement. The published "
            "arms are claude-p (baseline), aura-mcp (Aura's tool layer, "
            "disclosed but not reproducible from this repository) and unreal-mcp "
            "(Epic's first-party UE editor MCP)."
        )

    raise ValueError(
        f"Unknown adapter backend {backend!r} in slug {slug!r}. "
        "Supported: claude-p[:<model>] (Baseline), "
        "bare:<provider/model> (minimal provider-neutral loop + 5 local file "
        "tools, any OpenAI-compatible endpoint — no editor), "
        "openrouter:<model> (generalist via OpenRouter's Anthropic-compatible API), "
        "aura-mcp[:<model>] (authentic — dispatchable and documented, but not "
        "reproducible from this repository), "
        "unreal-mcp[:<model>] (Epic's first-party UE 5.8 editor MCP, stock tooling)."
    )
