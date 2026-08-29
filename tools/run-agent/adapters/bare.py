"""BareAdapter — a minimal, provider-neutral agent loop. The no-editor arm.

``bare:<provider/model>`` is the arm that measures a MODEL rather than a product:
the same loop, the same five local tools, the same system prompt, for every model,
against any OpenAI-compatible endpoint (pointed at OpenRouter this reaches grok /
gpt / deepseek / gemini / llama through one code path).

**What it deliberately is not.** "No harness" is unachievable — an agentic task
needs a loop. What is achievable is a scaffold that is minimal, identical across
models, and disclosed, which is what the SWE-bench-style minimal agents do. Every
number from this arm is a claim about *(model, this scaffold, surface)*, not
about the model alone -- which is why the scaffold is disclosed here in full.

**Its tools assume POSIX, deliberately.** The ``grep`` tool execs the POSIX
``grep`` binary directly, and the ``bash`` tool runs the model's command with
``shell=True`` -- which is ``cmd.exe /c`` on Windows, the validated platform.
On Windows, run this arm from an environment where those resolve (Git Bash /
MSYS puts ``grep`` on PATH); a bare ``cmd.exe`` session will fail the grep tool
and mis-parse POSIX shell syntax.

This is DISCLOSED rather than repaired on purpose. An arm's tool surface *is*
the measurement: substituting a Python grep, or re-routing bash through another
shell, changes what the model is measured against and would break comparability
with every number already collected under this scaffold.

**It reuses ``aura_mcp.run_loop`` verbatim.** Turn counting, token accumulation,
the stop condition and max-turns exhaustion are shared with the aura-mcp arm, so
the arms cannot drift apart in loop semantics — which is the one thing a
tool-layer comparison cannot survive. Only two seams differ: ``llm_call``
(``bare_wire.call_openai_compatible``) and ``dispatch`` (``dispatch_files`` here).

**Prompt parity is free and load-bearing.** ``run.py`` builds ``PROMPT.md`` from
``tasks/PREAMBLE.md`` + the task's agent-visible section and hands every adapter a
``prompt_path``. So this arm reads the byte-identical prompt the other arms read,
and ``preamble_sha`` is recorded per run. Nothing here re-derives a prompt.

**Scope: this arm can only reach tasks whose deliverable is a file it can write.**
It has no editor, so a ``.uasset`` deliverable is structurally unreachable — which
is why it is run on the ``cpp`` basket plus the four ``python`` tasks whose
deliverable is a plain-text report, and NOT on the asset baskets. That exclusion
is about the deliverable's FILE TYPE, never about whether the model could figure
the answer out — the latter is the measurement. Running it on an asset task would
score NO_DELIVERABLE, which since 2026-08-17 is a GRADED model outcome
(``base.MODEL_OUTCOME_VERDICTS``), so it would charge our design choice to the
model.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from adapters.aura_mcp import (
    DEFAULT_MAX_TOKENS,
    LoopRecord,
    llm_timeout_for,
    record_to_agent_result,
    run_loop,
)
from adapters.bare_wire import (
    DEFAULT_BASE_URL,
    MALFORMED_ARGS_KEY,
    ModelIdentityError,
    call_openai_compatible,
    validate_model_id,
)
from adapters.base import AgentResult

#: Per-tool wall clock. A model can ask for a build; it may not hang the rep.
DEFAULT_TOOL_DEADLINE_S = 300.0

#: Truncation for tool output fed back to the model. run_loop separately clips
#: tool_result content to 2000 chars for the API; this bounds what we even read,
#: so a `grep` over the engine tree cannot blow out memory or the context window.
MAX_TOOL_OUTPUT_CHARS = 20_000

BARE_SYSTEM_PROMPT = """You are a software engineering agent working inside a checked-out project directory.

You have five tools: read_file, write_file, list_dir, grep, and bash. All paths are relative to the project root. Work directly on the files.

Rules:
- Read a file before editing it. write_file replaces the whole file.
- Stay inside the project directory.
- Use bash to inspect, search, or build. It runs in the project root.
- The task description tells you which files you are allowed to change. Respect it.

When the task is fully satisfied, reply with plain text and NO further tool call.
"""

# Anthropic tool shape (bare_wire converts to OpenAI's). Descriptions are terse on
# purpose: a verbose tool prompt is itself scaffolding, and this arm's claim is
# that the scaffold is minimal.
BARE_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "read_file",
        "description": "Read a UTF-8 text file. Returns its contents.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write a UTF-8 text file, creating parent directories. Replaces existing content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_dir",
        "description": "List the entries of a directory.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "grep",
        "description": "Search files under a path for a regular expression. Returns matching lines with file:line prefixes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "bash",
        "description": "Run a shell command in the project root. Returns combined stdout and stderr.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
]


def _ok(text: str) -> Dict[str, Any]:
    return {"bSuccess": True, "result_text": text[:MAX_TOOL_OUTPUT_CHARS]}


def _err(text: str) -> Dict[str, Any]:
    """A tool error the MODEL sees and can recover from.

    Never raise out of a dispatcher. An exception here would abort the drive and
    be recorded as a harness fault, i.e. it would remove the rep from the
    denominator because the model passed a bad argument — the exact inversion
    the denominator rule exists to prevent.
    """
    return {"bSuccess": False, "error": text[:MAX_TOOL_OUTPUT_CHARS]}


def _resolve_in(root: Path, rel: str) -> Optional[Path]:
    """Resolve ``rel`` under ``root``, or None if it escapes.

    Checked with ``os.path.commonpath`` on the RESOLVED paths, so ``..``
    traversal and absolute paths are both refused. A symlink out of the tree
    resolves to its target and is refused too. This is a containment guard for
    the drive, not the grading gate — ``sandbox.py`` independently rejects any
    submitted file outside the writable set, so an escape here could not reach a
    grade even if it got past this.
    """
    try:
        target = (root / rel).resolve()
        root_r = root.resolve()
        if os.path.commonpath([str(target), str(root_r)]) != str(root_r):
            return None
        return target
    except (ValueError, OSError):
        return None


def dispatch_files(
    base_url: str,
    name: str,
    tool_input: Dict[str, Any],
    *,
    description: str = "",
    deadline_seconds: float = DEFAULT_TOOL_DEADLINE_S,
    workspace_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """``run_loop``'s ``dispatch`` seam, backed by local files.

    Signature mirrors ``aura_agent.dispatch_tool_call`` so ``run_loop`` needs no
    change; ``base_url`` and ``description`` are unused here and accepted only to
    keep that one calling convention. ``workspace_dir`` is bound per-run by
    ``BareAdapter`` via ``functools.partial``.
    """
    root = Path(workspace_dir) if workspace_dir else Path.cwd()

    if MALFORMED_ARGS_KEY in tool_input:
        return _err(
            "Your tool call arguments were not valid JSON. Re-issue the call with "
            "a well-formed JSON object. Received: "
            + str(tool_input.get(MALFORMED_ARGS_KEY))[:500]
        )

    if name == "read_file":
        p = _resolve_in(root, str(tool_input.get("path", "")))
        if p is None:
            return _err("path is outside the project directory")
        try:
            return _ok(p.read_text(encoding="utf-8", errors="replace"))
        except OSError as e:
            return _err(f"could not read: {e}")

    if name == "write_file":
        p = _resolve_in(root, str(tool_input.get("path", "")))
        if p is None:
            return _err("path is outside the project directory")
        content = tool_input.get("content")
        if not isinstance(content, str):
            return _err("'content' must be a string")
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            # newline="" so the model's own line endings survive verbatim. Python
            # would otherwise translate \n to \r\n on Windows, which silently
            # rewrites every byte of a submitted source file and would make a
            # diff-based or hash-based check disagree with what the model wrote.
            p.write_text(content, encoding="utf-8", newline="")
            return _ok(f"wrote {len(content)} chars to {tool_input.get('path')}")
        except OSError as e:
            return _err(f"could not write: {e}")

    if name == "list_dir":
        p = _resolve_in(root, str(tool_input.get("path", ".")))
        if p is None:
            return _err("path is outside the project directory")
        if not p.is_dir():
            return _err("not a directory")
        try:
            entries = sorted(
                c.name + ("/" if c.is_dir() else "") for c in p.iterdir()
            )
            return _ok("\n".join(entries) or "(empty)")
        except OSError as e:
            return _err(f"could not list: {e}")

    if name == "grep":
        pattern = str(tool_input.get("pattern", ""))
        if not pattern:
            return _err("'pattern' is required")
        rel = str(tool_input.get("path", "."))
        p = _resolve_in(root, rel)
        if p is None:
            return _err("path is outside the project directory")
        return _run_shell(
            ["grep", "-rn", "--", pattern, str(p)], root, deadline_seconds,
            allow_nonzero=True,   # grep exits 1 on "no matches", which is a result
        )

    if name == "bash":
        command = str(tool_input.get("command", ""))
        if not command:
            return _err("'command' is required")
        return _run_shell(command, root, deadline_seconds, shell=True,
                          allow_nonzero=True)

    return _err(f"unknown tool: {name}")


def _run_shell(cmd, cwd: Path, deadline: float, *, shell: bool = False,
               allow_nonzero: bool = False) -> Dict[str, Any]:
    """Run a command, returning its combined output as a tool result.

    A non-zero exit is reported as OUTPUT, not as a tool error, when
    ``allow_nonzero``: a failing compile is information the model must act on,
    and flagging it ``is_error`` invites the model to treat its own broken code as
    a tool malfunction. A TIMEOUT is an error, because there is no output to act
    on and the model needs to know the command was killed.
    """
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd), shell=shell, capture_output=True, text=True,
            timeout=deadline, errors="replace",
        )
    except subprocess.TimeoutExpired:
        return _err(f"command timed out after {deadline:.0f}s")
    except (OSError, ValueError) as e:
        return _err(f"could not run command: {e}")
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0 and not allow_nonzero:
        return _err(out or f"exit {proc.returncode}")
    if proc.returncode != 0:
        out = f"[exit {proc.returncode}]\n{out}"
    return _ok(out or "(no output)")


class BareAdapter:
    """Minimal provider-neutral agent. Satisfies the AgentAdapter Protocol."""

    def __init__(
        self,
        model: str,
        *,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        tool_deadline: float = DEFAULT_TOOL_DEADLINE_S,
        system_prompt: str = BARE_SYSTEM_PROMPT,
        tools: Optional[List[Dict[str, Any]]] = None,
        llm_call: Optional[Callable] = None,
        dispatch: Optional[Callable] = None,
    ):
        self.model = model
        self.base_url = base_url or os.environ.get(
            "CB_BARE_BASE_URL", DEFAULT_BASE_URL)
        self._api_key = api_key
        self.max_tokens = max_tokens
        self.tool_deadline = tool_deadline
        self.system_prompt = system_prompt
        self.tools = tools if tools is not None else BARE_TOOLS
        self.name = f"bare:{model}"
        self._llm_call = llm_call
        self._dispatch = dispatch

    #: Delegates to the SHARED definition in aura_mcp — the module that owns
    #: run_loop, and therefore the only place the per-call timeout can be set once
    #: for every adapter that drives it. Kept as a name here because the bare arm is
    #: where the 60s ceiling was measured.
    llm_timeout_for = staticmethod(llm_timeout_for)

    def _resolve_key(self) -> Optional[str]:
        """Explicit key, else OPENROUTER_API_KEY. Quotes stripped.

        A quoted value in ``.env`` (``OPENROUTER_API_KEY="sk-or-..."``) otherwise
        becomes a malformed Bearer token and 401s — the same footgun the
        ``openrouter`` backend already guards.
        """
        raw = self._api_key or os.environ.get("OPENROUTER_API_KEY") or ""
        return raw.strip().strip('"').strip("'") or None

    def _fail(self, msg: str, t0: float) -> AgentResult:
        return AgentResult(
            exit_code=1, transcript="", summary=f"bare adapter error: {msg}",
            tool_use_count=0, mcp_tool_use_count=0, tool_names=[],
            cost_usd=None, num_turns=0, duration_s=time.monotonic() - t0,
        )

    def run(
        self,
        prompt_path: Path,
        workspace_dir: Path,
        max_turns: int,
        timeout_s: int,
    ) -> AgentResult:
        t0 = time.monotonic()
        # Pre-spend: an id that cannot anchor a published number is refused before
        # a single token is bought, since the fault is in OUR slate, not the run.
        try:
            validate_model_id(self.model)
        except ModelIdentityError as e:
            return self._fail(str(e), t0)
        task_prompt = prompt_path.read_text(encoding="utf-8")
        key = self._resolve_key()
        if key is None and self._llm_call is None:
            return self._fail(
                "no API key — set OPENROUTER_API_KEY (or CB_BARE_BASE_URL + a key "
                "for another OpenAI-compatible endpoint)", t0)

        if self._llm_call is not None:
            llm_call = self._llm_call
        else:
            base_url = self.base_url

            def llm_call(**kw):
                return call_openai_compatible(base_url=base_url, **kw)

        if self._dispatch is not None:
            dispatch = self._dispatch
        else:
            def dispatch(base_url, name, tool_input, **kw):
                return dispatch_files(
                    base_url, name, tool_input,
                    workspace_dir=workspace_dir, **kw)

        # Same "0 = uncapped -> finite safety cap" convention as aura-mcp: the
        # loop's turn count is its only bound, so an uncapped value must still
        # terminate.
        effective_turns = max_turns if max_turns and max_turns > 0 else 1000
        try:
            rec: LoopRecord = run_loop(
                base_url="", api_key=key or "", task_prompt=task_prompt,
                model=self.model, max_turns=effective_turns,
                tool_deadline=min(self.tool_deadline, float(timeout_s)),
                max_tokens=self.max_tokens, anthropic_tools=self.tools,
                llm_call=llm_call, dispatch=dispatch,
                system_prompt=self.system_prompt,
                llm_timeout=llm_timeout_for(timeout_s),
                # t0 is this run's start, so the ceiling bounds the DRIVE and not
                # just each call. Without it `--ceiling` bounded nothing here.
                wall_deadline=t0 + float(timeout_s),
            )
        except Exception as e:  # noqa: BLE001
            # Transport/provider failure. Reported as an adapter error (exit 1)
            # rather than propagating, so the rig classifies it as a harness
            # condition instead of letting a 503 read as a model failure.
            return self._fail(f"{type(e).__name__}: {e}", t0)
        # mcp=0, honestly: none of these five tools is an MCP tool. The default
        # predicate would have counted them all as MCP traffic.
        return record_to_agent_result(rec, is_mcp_tool=lambda _n: False)
