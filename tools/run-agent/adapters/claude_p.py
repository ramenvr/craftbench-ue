"""ClaudePAdapter — v0 backend that shells out to `claude -p`.

Command construction is factored into the pure function build_claude_command
so it can be unit-tested without a live binary. The subprocess wrapper
captures the full stream-json transcript, parses it for tool-use telemetry
(total + MCP-only counts, tool names, cost, num_turns), derives the final
summary from the `result` event, and returns an AgentResult.

Stream-json was chosen over plain text so the harness can verify MCP
capability (acceptance criterion 6) — plain `-p` text output drops tool
calls and only emits the final assistant text.

The CLI stream is not the whole record. When this adapter routes the CLI through
the local logging proxy (``CB_PROXY_OPENROUTER=1``), the gateway's own per-call
ids, served backend and reasoning-token counts exist ONLY on the wire — the CLI
never surfaces them — so ``run()`` also reads the proxy's usage window for the
drive it just made. See ``_proxy_accounting``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from adapters.base import AgentResult


def _resolve_claude_binary(claude_binary: str) -> str:
    """Resolve the `claude` launcher to something subprocess(shell=False) can exec.

    Mac/Linux: `claude` is a plain executable on PATH; ``shutil.which`` finds it
    (or, if the caller passed an absolute path / unknown name, we leave it
    untouched and let the exec-failure path report it). Behavior there is
    UNCHANGED — we return the bare name as before when it resolves on PATH.

    Windows: the Claude Code launcher is a ``.cmd``/``.exe`` shim, and a bare
    ``claude`` with ``shell=False`` will NOT resolve a ``.cmd`` (cmd shims are
    only found by the shell or by ``shutil.which`` with the right PATHEXT). So
    on Windows, if the bare name does not resolve, fall back to probing the
    ``claude.cmd`` / ``claude.exe`` variants on PATH. If none resolve, leave the
    bare name so the existing FileNotFoundError / exec-failure path reports it.

    NOTE (Windows): users may need ``claude`` (the ``.cmd`` shim installed by the
    Claude Code installer) on PATH for this adapter to find the binary.
    """
    # If the caller gave a concrete path (not just a bare name), respect it.
    if os.path.sep in claude_binary or (os.path.altsep and os.path.altsep in claude_binary):
        return claude_binary

    resolved = shutil.which(claude_binary)
    if resolved is not None:
        # On Mac/Linux this is the same `claude` on PATH; return the bare name
        # to preserve existing behavior (argv[0] == "claude").
        if sys.platform != "win32":
            return claude_binary
        # On Windows, shutil.which already honors PATHEXT; the resolved path
        # (e.g. ...\claude.cmd) is what subprocess(shell=False) needs.
        return resolved

    # Bare name did not resolve. On Windows, try the explicit shim variants.
    if sys.platform == "win32":
        for candidate in (f"{claude_binary}.cmd", f"{claude_binary}.exe"):
            found = shutil.which(candidate)
            if found is not None:
                return found

    # Still unresolved — leave the bare name so the exec path reports it.
    return claude_binary


def _proxy_module():
    """``aura_rig.proxy``, imported on demand.

    Lazy because ``adapters.registry`` imports THIS module unconditionally: a
    module-level ``aura_rig`` import would put the whole rig on the import path of
    every backend, including the baseline that never touches a gateway.
    """
    run_agent_dir = str(Path(__file__).resolve().parents[1])
    if run_agent_dir not in sys.path:
        sys.path.insert(0, run_agent_dir)
    from aura_rig import proxy
    return proxy


def routed_via_logging_proxy(env_overrides: Optional[Dict[str, str]]) -> bool:
    """True when THIS run pointed the CLI at the local logging proxy.

    The gate is not optional. :41299's usage log is SHARED — the Aura lane tees
    into the same file, and nothing in a log line says which drive produced it —
    so reading the window for a run that went straight to the provider would
    attribute another process's generation ids to it. Absent evidence is
    recoverable; wrong evidence is not.

    A False from an unimportable ``aura_rig`` is not a swallowed failure: the
    routing decision itself (``registry.proxy_base_url_for``) refuses unless the
    module imports AND a proxy answers, so a run that could not import it never
    routed through one.
    """
    base = ((env_overrides or {}).get("ANTHROPIC_BASE_URL") or "").strip()
    if not base:
        return False
    try:
        proxy = _proxy_module()
    except Exception:  # noqa: BLE001
        return False
    return base.rstrip("/").lower() == proxy.CLI_BASE_URL.rstrip("/").lower()


def build_claude_command(
    workspace_dir: Path,
    max_turns: int,
    *,
    claude_binary: str = "claude",
    model: Optional[str] = None,
    mcp_config: Optional[Path] = None,
    strict_mcp: bool = False,
    allowed_tools: Optional[List[str]] = None,
    disallowed_tools: Optional[List[str]] = None,
    permission_mode: str = "bypassPermissions",
) -> List[str]:
    """Build the argv list for `claude -p`.

    The PROMPT is NOT in argv — it is passed on stdin by ``run()`` — so the
    variadic ``--allowedTools``/``--disallowedTools`` lists can never swallow it.

    Flag rationale:
      -p / --print              non-interactive, prints final response and exits
      --output-format stream-json  emit line-delimited JSON events (tool calls, result)
      --verbose                 required by stream-json mode
      --add-dir <ws>            file-access scope (CLI-level, not prompt discipline)
      --permission-mode <mode>  bypassPermissions: a single-shot agent must run
                                its ALLOWED tools (after the denylist) without
                                interactive prompts; "auto" was found to DENY MCP
                                write tools like Aura's generate_cpp_file in the
                                parent context (they only ran via a subagent leak).
      --max-turns <N>           cap the tool-use loop (omitted entirely when
                                max_turns <= 0 — uncapped; the subprocess
                                timeout_s wall clock is the governor)
      --model <slug>            optional model override
      --mcp-config <json>       load ONLY these MCP servers (Aura's, for aura-mcp)
      --strict-mcp-config       ignore the operator's global MCP servers entirely
                                (Baseline: no --mcp-config → no MCP at all; clean generalist)
      --disallowedTools ...     deny generic actuators so an aura-mcp agent can only
                                change the project THROUGH Aura's tools (no Write/Bash)
      --allowedTools ...        optional allowlist
    """
    cmd: List[str] = [
        claude_binary,
        "-p",
        "--output-format", "stream-json",
        "--verbose",
        "--add-dir", str(workspace_dir),
        "--permission-mode", permission_mode,
    ]
    if max_turns and max_turns > 0:
        cmd.extend(["--max-turns", str(max_turns)])
    if model is not None:
        cmd.extend(["--model", model])
    if mcp_config is not None:
        cmd.extend(["--mcp-config", str(mcp_config)])
    if strict_mcp:
        cmd.append("--strict-mcp-config")
    if disallowed_tools:
        cmd.extend(["--disallowedTools", *disallowed_tools])
    if allowed_tools:
        cmd.extend(["--allowedTools", *allowed_tools])
    return cmd


def parse_stream_json(stdout: str) -> Dict[str, Any]:
    """Parse `claude -p --output-format stream-json` line-delimited JSON output.

    The transcript is a stream of newline-terminated JSON objects. Relevant
    event shapes (only the fields we use; the actual events have more):

      {"type": "system", "subtype": "init", "session_id": "...", "model": "..."}
      {"type": "assistant", "message": {"content": [
          {"type": "tool_use", "name": "Read", "input": {...}, "id": "..."},
          {"type": "tool_use", "name": "mcp__unreal_editor__edit_cpp_file", ...},
          {"type": "text", "text": "Done."}
      ]}}
      {"type": "result", "subtype": "success", "result": "<final assistant text>",
       "duration_ms": 5000, "num_turns": 3, "total_cost_usd": 0.5}

    Returns a dict with:
      tool_names: list[str]         ordered list of every tool invocation name
      tool_use_count: int           total number of tool calls
      mcp_tool_use_count: int       subset starting with "mcp__"
      summary: str | None           final assistant text from the result event
      cost_usd: float | None        adapter-reported cost
      num_turns: int | None         number of model turns
      session_id: str | None        Claude session UUID (for forensics)
      models_used: list[str]        model ids that ACTUALLY answered (init/
                                    per-message/modelUsage) — the attribution,
                                    since a bare slug runs the CLI default

    Malformed lines are silently skipped — the transcript is still saved
    verbatim, so anything we miss can be re-analyzed manually.
    """
    tool_names: List[str] = []
    summary: Optional[str] = None
    cost_usd: Optional[float] = None
    num_turns: Optional[int] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    cache_creation_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    session_id: Optional[str] = None
    # The model(s) that ACTUALLY answered — from the init event, per-message
    # model ids, and the result's modelUsage keys. A bare `claude-p` slug runs
    # on the CLI's session default, so the label alone is NOT attribution
    # (2026-07-22: two "claude-p" runs silently ran on claude-fable-5; same
    # failure class as the 2026-07-11 aura model-pin incident — trust
    # models_used over the label).
    models_seen: List[str] = []

    def _see_model(m: Any) -> None:
        if isinstance(m, str) and m and m not in models_seen:
            models_seen.append(m)

    for raw in stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue

        evt_type = event.get("type")
        if evt_type == "system" and event.get("subtype") == "init":
            session_id = event.get("session_id") or session_id
            _see_model(event.get("model"))
        elif evt_type == "assistant":
            message = event.get("message") or {}
            _see_model(message.get("model"))
            for item in message.get("content") or []:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    name = item.get("name")
                    if isinstance(name, str):
                        tool_names.append(name)
        elif evt_type == "result":
            mu = event.get("modelUsage")
            if isinstance(mu, dict):
                for k in mu:
                    _see_model(k)
            # The result event may appear once at the end.
            if summary is None:
                summary = event.get("result")
            if cost_usd is None:
                v = event.get("total_cost_usd")
                if isinstance(v, (int, float)):
                    cost_usd = float(v)
            if num_turns is None:
                v = event.get("num_turns")
                if isinstance(v, int):
                    num_turns = v
            # Token usage lives in the result event's `usage` block. Absent ⇒ None
            # (never fabricated as 0).
            #
            # tokens_in is the TOTAL billable input: `input_tokens` counts only the
            # UNCACHED remainder, and under prompt caching that is a rounding error
            # next to the real prompt. Measured 2026-07-26 on a t0 claude-p run:
            # input_tokens=8 while cache_creation=47586 and cache_read=139202 — so
            # reading input_tokens alone under-reported input by ~23,000x and made
            # every tokens_in in bench.json / the leaderboards meaningless (cost_usd
            # came from the CLI's own total_cost_usd and stayed correct throughout).
            # The two cache components are kept separately as well, because their
            # RATES differ (creation 1.25x base, read 0.1x) and that spread is the
            # whole reason a session's first run costs ~57% more than its second.
            usage = event.get("usage")
            if isinstance(usage, dict):
                if tokens_in is None:
                    parts = [usage.get(k) for k in ("input_tokens",
                                                    "cache_creation_input_tokens",
                                                    "cache_read_input_tokens")]
                    present = [v for v in parts if isinstance(v, int)]
                    if present:
                        tokens_in = sum(present)
                if cache_creation_tokens is None and isinstance(
                        usage.get("cache_creation_input_tokens"), int):
                    cache_creation_tokens = usage["cache_creation_input_tokens"]
                if cache_read_tokens is None and isinstance(
                        usage.get("cache_read_input_tokens"), int):
                    cache_read_tokens = usage["cache_read_input_tokens"]
                if tokens_out is None and isinstance(usage.get("output_tokens"), int):
                    tokens_out = usage["output_tokens"]

    mcp_count = sum(1 for n in tool_names if n.startswith("mcp__"))
    return {
        "tool_names": tool_names,
        "tool_use_count": len(tool_names),
        "mcp_tool_use_count": mcp_count,
        "summary": summary,
        "cost_usd": cost_usd,
        "num_turns": num_turns,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cache_creation_tokens": cache_creation_tokens,
        "cache_read_tokens": cache_read_tokens,
        "session_id": session_id,
        "models_used": models_seen,
    }


class ClaudePAdapter:
    """v0 adapter — invoke `claude -p` non-interactively against the workspace."""

    def __init__(
        self,
        model: Optional[str] = None,
        claude_binary: str = "claude",
        *,
        mcp_config: Optional[Path] = None,
        strict_mcp: bool = False,
        allowed_tools: Optional[List[str]] = None,
        disallowed_tools: Optional[List[str]] = None,
        name: Optional[str] = None,
        env_overrides: Optional[Dict[str, str]] = None,
    ):
        self.model = model
        # Resolve the launcher up front so subprocess(shell=False) can exec it
        # on Windows (where `claude` is a .cmd/.exe shim, not a bare executable).
        # On Mac/Linux this returns the bare `claude` unchanged.
        self.claude_binary = _resolve_claude_binary(claude_binary)
        self.mcp_config = mcp_config
        self.strict_mcp = strict_mcp
        self.allowed_tools = allowed_tools
        self.disallowed_tools = disallowed_tools
        self.env_overrides = env_overrides
        self.name = name or f"claude-p:{model or 'default'}"

    def _usage_mark(self) -> Optional[int]:
        """Line offset into the proxy usage log, or None when not routed via it.

        None is the "do not read the log" signal, and it must be taken BEFORE the
        drive: the offset is the only thing that separates this drive's requests
        from every earlier one in a shared, append-only log.
        """
        if not routed_via_logging_proxy(self.env_overrides):
            return None
        return _proxy_module().usage_line_count()

    def _proxy_accounting(self, usage_before: Optional[int]) -> Dict[str, Any]:
        """The provider-side fields this drive can PROVE, from the proxy window.

        Returns AgentResult kwargs, present-only: an empty dict leaves every field
        at its None default, so "we did not route through the gateway" can never
        read as "the gateway reported nothing". The gateway's ``gen-`` ids are the
        join key ``aura_rig.openrouter_cost`` needs to audit a published cost
        against OpenRouter's own ledger, and they exist nowhere else — the CLI
        does not surface them.

        Guarded because the log is SHARED and append-only: one line whose token
        field is a string (a truncated write, a foreign producer) makes
        ``usage_since``'s ``+=`` raise, and losing a paid drive's whole result to
        an accounting read would be the worse failure. Silence is acceptable
        HERE specifically because the log outlives the run — the ids stay
        recoverable from it after the fact.
        """
        if usage_before is None:
            return {}
        try:
            agg = _proxy_module().usage_since(usage_before, self.model or "")
        except Exception:  # noqa: BLE001
            return {}
        out: Dict[str, Any] = {}
        if agg.get("generation_ids"):
            out["generation_ids"] = list(agg["generation_ids"])
        if agg.get("providers"):
            out["providers_served"] = list(agg["providers"])
        if agg.get("reasoning_tokens") is not None:
            out["reasoning_tokens"] = agg["reasoning_tokens"]
        return out

    def run(
        self,
        prompt_path: Path,
        workspace_dir: Path,
        max_turns: int,
        timeout_s: int,
    ) -> AgentResult:
        prompt = prompt_path.read_text(encoding="utf-8")
        cmd = build_claude_command(
            workspace_dir=workspace_dir,
            max_turns=max_turns,
            claude_binary=self.claude_binary,
            model=self.model,
            mcp_config=self.mcp_config,
            strict_mcp=self.strict_mcp,
            allowed_tools=self.allowed_tools,
            disallowed_tools=self.disallowed_tools,
        )

        # Neutral cwd so the repo isn't implicitly on the agent's file path.
        cwd = workspace_dir.parent
        run_env = {**os.environ, **self.env_overrides} if self.env_overrides else None

        usage_before = self._usage_mark()
        t0 = time.monotonic()
        try:
            completed = subprocess.run(
                cmd,
                cwd=cwd,
                input=prompt,  # prompt via stdin so variadic tool flags can't eat it
                capture_output=True,
                text=True,
                # Force UTF-8: agent stream-JSON contains non-Latin1 bytes (smart
                # quotes, box-drawing, emoji). On Windows text=True would otherwise
                # decode with cp1252 and crash the reader thread with
                # UnicodeDecodeError, leaving completed.stdout=None. errors="replace"
                # keeps a stray byte from aborting the whole run.
                encoding="utf-8",
                errors="replace",
                timeout=timeout_s,
                env=run_env,
            )
            duration = time.monotonic() - t0
            stdout = completed.stdout or ""
            transcript = stdout + (
                f"\n--- STDERR ---\n{completed.stderr}" if completed.stderr else ""
            )
            parsed = parse_stream_json(stdout)
            return AgentResult(
                exit_code=completed.returncode,
                transcript=transcript,
                summary=parsed["summary"],
                tool_use_count=parsed["tool_use_count"],
                mcp_tool_use_count=parsed["mcp_tool_use_count"],
                tool_names=parsed["tool_names"],
                cost_usd=parsed["cost_usd"],
                num_turns=parsed["num_turns"],
                tokens_in=parsed["tokens_in"],
                tokens_out=parsed["tokens_out"],
                cache_creation_tokens=parsed["cache_creation_tokens"],
                cache_read_tokens=parsed["cache_read_tokens"],
                models_used=parsed["models_used"],
                duration_s=duration,
                **self._proxy_accounting(usage_before),
            )
        except subprocess.TimeoutExpired as e:
            duration = time.monotonic() - t0
            partial = e.stdout.decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            parsed = parse_stream_json(partial)
            return AgentResult(
                exit_code=124,
                transcript=partial + f"\n--- TIMEOUT after {timeout_s}s ---",
                summary=parsed["summary"],
                tool_use_count=parsed["tool_use_count"],
                mcp_tool_use_count=parsed["mcp_tool_use_count"],
                tool_names=parsed["tool_names"],
                cost_usd=parsed["cost_usd"],
                num_turns=parsed["num_turns"],
                tokens_in=parsed["tokens_in"],
                tokens_out=parsed["tokens_out"],
                cache_creation_tokens=parsed["cache_creation_tokens"],
                cache_read_tokens=parsed["cache_read_tokens"],
                models_used=parsed["models_used"],
                duration_s=duration,
                # A TIMEOUT still spent money and still made calls, so the window
                # is read on this path too — a killed drive is exactly the one
                # whose cost most needs auditing.
                **self._proxy_accounting(usage_before),
            )
