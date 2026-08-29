"""driver — the proven graded-run logic, refactored into composable functions.

This is the headless-HTTP rig that drives Aura's REAL autonomous agent (the FULL
version, *_agent sub-agents live) against the CraftBench substrate and grades it
deterministically. Ported from /tmp/graded_run.py.

The pieces, each a function so the adapter (and a standalone CLI) can compose them:

  * fairness / backup / restore  -> safe live-tree handling (NO git checkout)
  * open_task_map                -> SETUP: load the task's map (not measured)
  * drive_agent                  -> POST :41200/api/chat, capture the FULL SSE
                                    trace (tool calls + text + usage), write
                                    trace.jsonl + trace.md
  * trace capture                -> proxy usage (true on-wire model) + SUB-AGENT
                                    trace (proxy records whose model != main wire)
  * grade                        -> run_task.py --submission-from-project (L1+L2)

The SSE-stream parser (``parse_chat_stream``) is a PURE function over a sequence
of decoded SSE event dicts, so the trace reconstruction is unit-testable with no
socket and no editor. ``run_graded`` is the full standalone orchestration; the
adapter (adapters/aura_agent.py) calls the smaller seams directly so the harness
keeps owning fairness/backup/restore around it.

HTTP is injectable (``post_sse`` seam) so drive_agent is testable offline.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from . import exit_status, model_keys, proxy, tasks


def _detect_repo() -> Path:
    """Locate the craftbench repo root: CRAFTBENCH_REPO env -> __file__ walk-up
    (first parent holding BOTH tools/verify-single AND UE-projects).

    Raises if neither resolves — e.g. run from outside the repo on a machine
    where CRAFTBENCH_REPO isn't set. Fail loud with an actionable message rather
    than silently point at some other developer's absolute path."""
    env = os.environ.get("CRAFTBENCH_REPO")
    if env:
        return Path(env)
    for parent in Path(__file__).resolve().parents:
        if (parent / "tools" / "verify-single").exists() and (parent / "UE-projects").exists():
            return parent
    raise RuntimeError(
        f"Could not locate the craftbench repo root from {Path(__file__).resolve()} "
        "(no parent holds both tools/verify-single and UE-projects). "
        "Set CRAFTBENCH_REPO to the repo root."
    )


# --- repo geometry (overridable for tests) ---------------------------------
REPO = _detect_repo()
DEFAULT_SUBSTRATE = "CraftBenchTemplate"
PROJECT_REL = "UE-projects/CraftBenchTemplate"
SRC_REL = "Source/CraftBenchTemplate"
CONTENT_TASKS_REL = "Content/Tasks"
CONTENT_REL = "Content"  # broadened DELIVERABLE detection (sub-agents author outside Content/Tasks)


def available_substrates(repo: Optional[Path] = None) -> List[str]:
    """Substrate dir names under ``UE-projects/`` — a dir counts as a substrate
    iff it holds a root ``*.uproject`` (filters out README.md and scratch
    folders). Sorted for stable error messages."""
    root = (Path(repo) if repo is not None else REPO) / "UE-projects"
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir()
                  if p.is_dir() and next(p.glob("*.uproject"), None) is not None)


def project_rel(substrate: str = DEFAULT_SUBSTRATE, *, repo: Optional[Path] = None) -> str:
    """Repo-relative dir of a substrate (``UE-projects/<substrate>``), validated.

    Multi-substrate seam: :data:`PROJECT_REL` stays the DEFAULT-substrate
    constant for back-compat; callers with a task id/spec in scope thread the
    spec's substrate through here instead. An unknown substrate raises
    ``ValueError`` listing what is actually on disk (``repo`` is injectable
    for tests; default :data:`REPO`)."""
    name = (substrate or DEFAULT_SUBSTRATE).strip()
    base = Path(repo) if repo is not None else REPO
    rel = f"UE-projects/{name}"
    if not (base / rel).is_dir():
        avail = ", ".join(available_substrates(base)) or "(none)"
        raise ValueError(
            f"unknown substrate {substrate!r} — no {rel} under {base}; "
            f"available substrates: {avail}")
    return rel


def src_rel(substrate: str = DEFAULT_SUBSTRATE, *, repo: Optional[Path] = None) -> str:
    """``Source/<game module>`` — the agent-writable runtime module of a
    substrate. :data:`SRC_REL` stays the default-substrate constant. The module
    name comes from the substrate's ``AGENT_WRITABLE.json`` ``game_module``
    (repo-side policy), falling back to the substrate dir name (true for every
    current substrate)."""
    rel = project_rel(substrate, repo=repo)
    base = Path(repo) if repo is not None else REPO
    module = (substrate or DEFAULT_SUBSTRATE).strip()
    manifest = base / rel / "AGENT_WRITABLE.json"
    try:
        module = json.loads(manifest.read_text(encoding="utf-8")).get("game_module") or module
    except (OSError, ValueError):
        pass
    return f"Source/{module}"
GW = os.environ.get("CB_GATEWAY", "http://127.0.0.1:41200")
DEFAULT_UE_ROOT = os.environ.get("CB_UE_ROOT") or (
    r"C:\Program Files\Epic Games\UE_5.8" if os.name == "nt"
    else "/Users/Shared/Epic Games/UE_5.8"
)
WIP_STASH = Path(os.environ.get("CB_TMP", tempfile.gettempdir())) / "cb-wip-fixtures"


def _env_flag(name: str) -> bool:
    """True iff the env var is set to a truthy value (1/true/yes)."""
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


# ===========================================================================
# SSE event-stream parsing (pure; the unit-testable core of trace capture).
# ===========================================================================

@dataclass
class DriveResult:
    """Structured outcome of one /api/chat drive (what the adapter surfaces)."""

    thread: str
    elapsed: float
    finish_reason: Optional[str]
    tool_calls: int
    by_tool: Dict[str, int]
    tool_names: List[str]
    usage: List[dict]                       # messageMetadata.totalUsage events, if any
    ev_types: Dict[str, int]
    final_text: str
    calls: List[dict] = field(default_factory=list)  # ordered tool-call records
    raw_events: List[dict] = field(default_factory=list)
    timing: Dict[str, float] = field(default_factory=dict)  # gen-timing (aura-product fetch-tee): ttft_s/gen_s/finish_s/wall_s
    # Driver-side PHASE accounting (aura-product): where the drive subprocess's
    # wall-clock went. `drive_s` was one number over a large unattributed gap --
    # on a t0 eval 176.5s against an 84.0s measured turn, so 92.5s happened
    # before submit or after waitComplete with nothing naming it. Closes against
    # its own `total` via a DERIVED `unaccounted`, like report.json's phases.
    phases: Dict[str, float] = field(default_factory=dict)
    # IN-DRIVE commit-pressure evidence (aura_rig.pressure.DriveMonitor.report()).
    # Filled by aura_product.drive for the whole measured turn and recorded into
    # summary.json even when the drive is perfectly healthy -- min-free + at-exit
    # free commit is what makes the NEXT unexplained EDITOR-GONE attributable in
    # one read. `{"aborted": True}` means the drive was stopped DELIBERATELY
    # under the floor and the caller must record COMMIT-EXHAUSTED (non-graded).
    # Empty dict = the layer was off (CB_PRESSURE_GUARD=0 / CB_NO_PREFLIGHT /
    # a test process) or nothing was sampled -- never a claim about the box.
    pressure: Dict = field(default_factory=dict)


def parse_chat_stream(events: Iterable[dict]) -> DriveResult:
    """Reconstruct a DriveResult from a sequence of decoded /api/chat SSE events.

    Mirrors the proven graded_run.py loop: tool-input-start opens a call,
    tool-input-available fills its input, tool-output-available fills its
    output (and is when it ends), text-delta accumulates the assistant text,
    finishReason / messageMetadata.totalUsage are captured when present.

    Pure: no time, no socket. Timing fields default to 0 (the live drive_agent
    overlays wall-clock t_start/t_end). ``thread`` is filled by the caller.
    """
    calls: "OrderedDict[str, dict]" = OrderedDict()
    order: List[str] = []
    text: List[str] = []
    usage: List[dict] = []
    ev_types: Counter = Counter()
    finish_reason: Optional[str] = None
    raw: List[dict] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        raw.append(ev)
        ty = ev.get("type", "?")
        ev_types[ty] += 1
        cid = ev.get("toolCallId")
        if ty == "tool-input-start":
            nm = ev.get("toolName") or "?"
            calls[cid] = {"seq": len(order) + 1, "name": nm, "input": None,
                          "output": None, "t_start": 0.0, "t_end": None}
            order.append(cid)
        elif ty == "tool-input-available":
            if cid in calls:
                calls[cid]["input"] = ev.get("input")
        elif ty == "tool-output-available":
            if cid in calls:
                calls[cid]["output"] = ev.get("output")
        elif ty == "text-delta":
            text.append(ev.get("delta", ""))
        if "finishReason" in ev:
            finish_reason = ev.get("finishReason")
        md = ev.get("messageMetadata")
        if isinstance(md, dict) and md.get("totalUsage"):
            usage.append(md["totalUsage"])
    ordered_calls = [calls[c] for c in order]
    names = Counter(c["name"] for c in ordered_calls)
    return DriveResult(
        thread="", elapsed=0.0, finish_reason=finish_reason,
        tool_calls=len(ordered_calls), by_tool=dict(names),
        tool_names=[c["name"] for c in ordered_calls],
        usage=usage, ev_types=dict(ev_types), final_text="".join(text).strip(),
        calls=ordered_calls, raw_events=raw,
    )


_SUBSCRIPTION_401_MARKER = "Subscription validation request failed"

# Every way @requires_subscription can refuse a tool WITHOUT running its body.
# The 401 marker alone was incomplete: it only fires when the validator answers
# non-200, whereas the commonest refusal — an expired trial — comes back HTTP
# 200 with the route's verbatim 'No active subscription found: …', and a missing
# session gives 'No valid session token found'. A drive whose every call was
# refused for THOSE reasons therefore scored as the agent's failure; with writes
# that landed before the lapse it could even reach a GRADED FAIL, putting a
# non-agent condition in a pass-rate denominator. Kept in sync with
# stack.ACCOUNT_BLOCK_MARKERS (same server strings, other side of the run).
_TOOL_BLOCK_MARKERS = (
    _SUBSCRIPTION_401_MARKER,
    "No active subscription",
    "No valid session token",
)


def tool_auth_health(calls) -> dict:
    """Detect the Aura entitlement refusals that silently block tool use.

    Every Aura MCP tool is wrapped by ``@requires_subscription``; when the account
    cannot use tools it hands back ``{"error": "…"}`` as a NORMAL output
    (``isError=false``) WITHOUT running the tool body — so the agent cannot
    actuate and the run looks like a silent NO_DELIVERABLE. Three shapes exist:
    a non-200 from the validator (``Subscription validation request failed with
    status 401``), an expired/absent subscription (``No active subscription
    found: …``, HTTP 200), and a missing session (``No valid session token``).

    Scans the ordered ``DriveResult.calls``. A call is "completed" if it produced
    an output. ``blocked`` is True only when EVERY completed call was refused —
    a lone transient among successes (seen even in passing runs) must NOT block.
    Keys ONLY on those specific markers, never on generic tool errors, to avoid
    false positives.
    """
    completed = 0
    auth = 0
    sample = None
    for c in calls or []:
        out = c.get("output")
        if out is None:
            continue
        completed += 1
        blob = out if isinstance(out, str) else json.dumps(out)
        hit = next((m for m in _TOOL_BLOCK_MARKERS if m in blob), None)
        if hit is not None:
            auth += 1
            if sample is None:
                i = blob.find(hit)
                sample = blob[i:i + 60]
    return {
        "tool_calls": completed,
        "auth_error_calls": auth,
        "sample_error": sample,
        "blocked": completed >= 1 and auth == completed,
    }


def tool_starvation(calls) -> dict:
    """Detect the dead-transport shape: the agent CALLED tools but (almost)
    none ever produced an output.

    Measured on the build machine (2026-08-07, finding 1): the client :3002
    died 92 s into a turn; the cloud thread kept generating and billing for
    the remaining ceiling while all 39 server-routed tool calls starved -
    only the 2 client-LOCAL calls had output. That run graded like a real
    attempt. The signature is a STARVATION RATIO, not a zero-count, precisely
    because client-local calls still complete.

    ``starved`` = attempted calls with NO output at all (distinct from
    tool_auth_health's refusals, which ARE outputs). Flags at >= 5 starved AND
    >= 90% of attempts starved - a cut-off run's one in-flight call, or a few
    transient failures among successes, never trips it.

    **EVIDENCE-ONLY since 2026-08-11.** A 46-run audit falsified
    ``dead_transport`` as a death signal on the aura-product transport: 37
    runs flag it — clean PASSes with real deliverables included — and even
    unflagged healthy runs sit at 82-86% starved, because output banking is
    client-local only (server-routed outputs never reach the recorded seam).
    The key keeps its name and formula for dashboard continuity, but no
    caller may set a verdict from it; a genuinely dead client is detected by
    the pressure sampler's :3002 liveness probe. See
    ``run_graded._flag_tool_starvation``."""
    attempted = 0
    starved = 0
    for c in calls or []:
        attempted += 1
        if c.get("output") is None:
            starved += 1
    ratio = (starved / attempted) if attempted else 0.0
    return {
        "attempted": attempted,
        "starved": starved,
        "starved_ratio": round(ratio, 3),
        "dead_transport": starved >= 5 and ratio >= 0.9,
    }


def observed_editor_project(gw: Optional[str] = None, *, opener=None,
                            timeout: float = 6.0) -> Optional[str]:
    """The uproject path the :41200 editor currently has open, or None.

    GETs ``<gw>/api/headless/status`` and returns its ``project`` field (None when
    disconnected/unreachable). ``opener`` is an injectable (url, timeout)->(status,
    body) seam for tests.
    """
    if gw is None:
        gw = GW
    url = f"{gw}/api/headless/status"
    if opener is None:
        def opener(u, t):  # noqa: E306
            with urllib.request.urlopen(u, timeout=t) as r:  # noqa: S310 localhost
                return r.status, r.read().decode("utf-8", "replace")
    try:
        _status, body = opener(url, timeout)
        d = json.loads(body)
    except Exception:
        return None
    return d.get("project") or None


def preflight_editor_project(expected_uproject, gw: Optional[str] = None, *,
                             opener=None, timeout: float = 6.0):
    """(ok, observed): is the connected editor open on ``expected_uproject``?

    ``ok`` is True only when the editor reports a ``project`` whose resolved path
    equals ``expected_uproject``. A wrong project (or none) returns (False,
    observed) so the caller can REFUSE to drive — otherwise the agent's edits land
    in the wrong project and the run silently produces NO_DELIVERABLE while burning
    tokens (the e2e gotcha: the harness drives whatever editor is on :41200, and a
    machine set up for another Unreal project leaves Aura bound to it).
    """
    obs = observed_editor_project(gw, opener=opener, timeout=timeout)
    if not obs:
        return (False, obs)
    try:
        ok = Path(obs).resolve() == Path(expected_uproject).resolve()
    except Exception:
        ok = (str(obs) == str(expected_uproject))
    return (ok, obs)


def iter_sse_events(byte_stream: Iterable[bytes]):
    """Yield decoded JSON event dicts from a raw SSE byte stream.

    Handles ``data:`` framing across chunk boundaries; skips ``[DONE]`` and
    non-data lines; tolerates malformed JSON (skipped).
    """
    buf = ""
    for raw in byte_stream:
        buf += raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            line = line.strip()
            if not line.startswith("data:"):
                continue
            p = line[5:].strip()
            if p == "[DONE]":
                continue
            try:
                yield json.loads(p)
            except Exception:
                continue


def render_trace_md(dr: DriveResult, *, task_id: str, model_key: str) -> str:
    """Human-readable ordered tool-call trace (the trace.md artifact)."""
    def clip(x, n=1800):
        if x is None:
            return "(none)"
        s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)
        return s if len(s) <= n else s[:n] + f"\n…[+{len(s)-n} chars truncated]"

    names = Counter(dr.tool_names)
    md = [
        f"# aura-agent trace — {task_id}", "",
        f"- thread: `{dr.thread}`", f"- model: `{model_key}`",
        f"- elapsed: {dr.elapsed}s", f"- finishReason: {dr.finish_reason}",
        *([f"- generation timing: ttft={dr.timing.get('ttft_s')}s "
           f"gen={dr.timing.get('gen_s')}s finish={dr.timing.get('finish_s')}s "
           f"wall={dr.timing.get('wall_s')}s (src {dr.timing.get('source')})"]
          if dr.timing else []),
        f"- tool calls: {dr.tool_calls} "
        f"({', '.join(f'{n}×{c}' for n, c in names.most_common())})",
        f"- token usage: {dr.usage or 'none on wire (needs messageMetadata patch)'}",
        "", "## Tool calls (in order)", "",
    ]
    for c in dr.calls:
        md += [
            f"### {c['seq']}. `{c['name']}`  (+{c.get('t_start', 0)}s → +{c.get('t_end')}s)",
            "**input:**", "```json", clip(c["input"]), "```",
            "**output:**", "```", clip(c["output"]), "```", "",
        ]
    md += ["## Assistant final text", "", dr.final_text or "(none)"]
    return "\n".join(md)


# ===========================================================================
# Live drive (POST /api/chat). HTTP is an injectable seam.
# ===========================================================================

def session_token(gw: str = GW, *, timeout: float = 6.0) -> Optional[str]:
    try:
        with urllib.request.urlopen(gw + "/api/sessionToken", timeout=timeout) as r:
            return (json.loads(r.read()) or {}).get("sessionToken")
    except Exception:
        return None


def _default_post_sse(url: str, body: dict, headers: dict, timeout: float):
    """Real POST returning a byte-iterator over the SSE response."""
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 method="POST", headers=headers)
    return urllib.request.urlopen(req, timeout=timeout)


def drive_agent(
    prompt: str,
    *,
    task_id: str,
    ts: int,
    model_key: str,
    gw: str = GW,
    ceiling_s: int = 700,
    run_dir: Optional[Path] = None,
    post_sse: Callable = _default_post_sse,
    token: Optional[str] = None,
    log: Callable[[str], None] = print,
) -> DriveResult:
    """POST /api/chat with the scrubbed prompt; capture EVERY SSE event.

    Writes trace.jsonl (raw events) + trace.md (readable) under ``run_dir`` when
    given. ``post_sse(url, body, headers, timeout)`` is the injectable HTTP seam
    (returns an iterable of byte chunks); defaults to a real urlopen. Returns a
    DriveResult with wall-clock timings overlaid on the pure parse.
    """
    thread = f"cb-graded-{task_id}-{ts}"
    body = {"id": thread, "model": model_key, "activeTool": True,
            "messages": [{"id": "m1", "role": "user",
                          "parts": [{"type": "text", "text": prompt}]}]}
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    tk = token if token is not None else session_token(gw)
    if tk:
        headers["Authorization"] = f"Bearer {tk}"

    raw_f = open(run_dir / "trace.jsonl", "w", encoding="utf-8") if run_dir else None
    calls: "OrderedDict[str, dict]" = OrderedDict()
    order: List[str] = []
    text: List[str] = []
    usage: List[dict] = []
    ev_types: Counter = Counter()
    finish_reason: Optional[str] = None
    t0 = time.time()
    log(f"  thread id: {thread}")
    try:
        resp = post_sse(gw + "/api/chat", body, headers, ceiling_s)
        for ev in iter_sse_events(resp):
            if raw_f:
                raw_f.write(json.dumps(ev) + "\n")
            ty = ev.get("type", "?")
            ev_types[ty] += 1
            cid = ev.get("toolCallId")
            if ty == "tool-input-start":
                nm = ev.get("toolName") or "?"
                calls[cid] = {"seq": len(order) + 1, "name": nm, "input": None,
                              "output": None, "t_start": round(time.time() - t0, 1),
                              "t_end": None}
                order.append(cid)
                log(f"  +{time.time()-t0:6.1f}s TOOL {nm}")
            elif ty == "tool-input-available":
                if cid in calls:
                    calls[cid]["input"] = ev.get("input")
            elif ty == "tool-output-available":
                if cid in calls:
                    calls[cid]["output"] = ev.get("output")
                    calls[cid]["t_end"] = round(time.time() - t0, 1)
            elif ty == "text-delta":
                text.append(ev.get("delta", ""))
            if "finishReason" in ev:
                finish_reason = ev.get("finishReason")
            md = ev.get("messageMetadata")
            if isinstance(md, dict) and md.get("totalUsage"):
                usage.append(md["totalUsage"])
    except Exception as e:
        log(f"  stream ended/err: {type(e).__name__}: {e}")
    finally:
        if raw_f:
            raw_f.close()

    elapsed = round(time.time() - t0, 1)
    ordered_calls = [calls[c] for c in order]
    names = Counter(c["name"] for c in ordered_calls)
    log(f"  stream ended @ {elapsed}s  finishReason={finish_reason}")
    log(f"  TOOL CALLS ({len(ordered_calls)}): "
        + ", ".join(f"{n}×{c}" for n, c in names.most_common()))

    dr = DriveResult(
        thread=thread, elapsed=elapsed, finish_reason=finish_reason,
        tool_calls=len(ordered_calls), by_tool=dict(names),
        tool_names=[c["name"] for c in ordered_calls], usage=usage,
        ev_types=dict(ev_types), final_text="".join(text).strip(),
        calls=ordered_calls,
    )
    if run_dir:
        (run_dir / "trace.md").write_text(
            render_trace_md(dr, task_id=task_id, model_key=model_key),
            encoding="utf-8",
        )
    return dr


def map_package_path(map_name: str, project: Optional[Path] = None) -> str:
    """Resolve the live project's ``/Game/...`` package path for ``map_name``.

    Same discovery rule as verify-single's map_locator (root
    ``Content/Maps/<map>.umap`` wins, else the one-level ``*/<map>.umap``
    glob) — duplicated as a small local helper because the driver may not
    import verify-single. Falls back to the legacy flat form when the umap
    isn't on disk (the editor errors the same way it always did).
    """
    proj = project if project is not None else REPO / PROJECT_REL
    maps_root = proj / "Content" / "Maps"
    if (maps_root / f"{map_name}.umap").exists():
        return f"/Game/Maps/{map_name}"
    matches = sorted(maps_root.glob(f"*/{map_name}.umap"))
    if matches:
        # sorted() keeps a multi-folder ambiguity (a substrate bug the
        # verifier rejects loudly) at least deterministic here — setup must
        # not crash the drive.
        return f"/Game/Maps/{matches[0].parent.name}/{map_name}"
    return f"/Game/Maps/{map_name}"


def open_task_map(
    map_name: str,
    *,
    task_id: str,
    ts: int,
    model_key: str,
    gw: str = GW,
    timeout: int = 150,
    post_sse: Callable = _default_post_sse,
    token: Optional[str] = None,
    log: Callable[[str], None] = print,
    project: Optional[Path] = None,
) -> List[str]:
    """SETUP (separate thread, NOT measured): load the task's map so the agent's
    get_available_actors_in_level shows the RIGHT actor. Returns tools used.

    The level path is DISCOVERED from the live project's disk layout
    (``map_package_path``: flat Content/Maps/ or one folder deep), not
    assumed flat."""
    pkg = map_package_path(map_name, project=project)
    instr = (
        "Use execute_unreal_python to run EXACTLY this and nothing else, then "
        "reply 'MAP_READY':\nimport unreal\n"
        f"unreal.LevelEditorSubsystem().load_level('{pkg}')"
    )
    body = {"id": f"cb-setup-{task_id}-{ts}", "model": model_key, "activeTool": True,
            "messages": [{"id": "s1", "role": "user",
                          "parts": [{"type": "text", "text": instr}]}]}
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    tk = token if token is not None else session_token(gw)
    if tk:
        headers["Authorization"] = f"Bearer {tk}"
    tools: List[str] = []
    try:
        resp = post_sse(gw + "/api/chat", body, headers, timeout)
        for ev in iter_sse_events(resp):
            if ev.get("type") == "tool-input-start":
                tools.append(ev.get("toolName"))
    except Exception as e:
        log(f"  open_task_map err: {type(e).__name__}: {e}")
    return tools


# ===========================================================================
# Task-spec helpers.
# ===========================================================================

def scrubbed_prompt(task_path: Path, *, preamble: str = "") -> str:
    """The agent-visible prompt for the aura paths: the same allow-listed
    extraction every backend uses (prompt_extract — 'Prompt given to the
    agent' + 'Workspace state pre-task'), with markdown '>' quoting stripped
    (the aura chat renders raw text) and the central benchmark preamble
    prepended when given. Previously a private regex that read ONLY the
    prompt section — unified so no backend can drift from the shared
    contract."""
    try:
        from prompt_extract import extract_agent_visible_prompt
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from prompt_extract import extract_agent_visible_prompt
    try:
        text = extract_agent_visible_prompt(task_path, preamble=preamble)
    except ValueError:
        # Malformed spec (no prompt section) — legacy behavior: whole file.
        text = task_path.read_text(encoding="utf-8")
        if preamble:
            text = preamble.strip() + "\n\n# Task\n\n" + text
    return "\n".join(re.sub(r'^\s*>\s?', '', ln)
                     for ln in text.strip().splitlines()).strip()


def task_map(task_path: Path) -> Optional[str]:
    """Resolve the task's map name (e.g. L_SpawnSequence) from the spec.

    THE single parser is authoritative: ``spec.map_name`` (fixtures[0] on v2
    front matter) — the v2 migration deleted the ``## Verifier fixtures``
    dash-lists the scans below matched, so regex-only resolution returns None
    on migrated multi-fixture specs and the drive skips the pre-drive
    map-open — the agent never sees the right actors and produces
    NO_DELIVERABLE.

    The legacy scans remain as the fallback for foreign/un-migrated specs:
    maps may live flat (``Maps/L_X.umap``) or one folder deep
    (``Maps/<task-id>/L_X.umap``) — both regexes tolerate an optional folder
    segment — plus the ``- L_Map :: AFooFunctionalTest`` bullet form.
    """
    try:
        _vs = str(Path(__file__).resolve().parents[2] / "verify-single")
        if _vs not in sys.path:
            sys.path.insert(0, _vs)
        from spec import parse_task_file
        mp = parse_task_file(task_path).map_name
        if mp:
            return mp
    except (ValueError, ImportError):
        pass  # malformed/foreign spec — the legacy scans below still apply
    t = task_path.read_text(encoding="utf-8")
    m = (re.search(r'Maps/(?:[A-Za-z0-9_\-]+/)?(L_[A-Za-z0-9_]+)\.umap', t)
         or re.search(r'/Game/Maps/(?:[A-Za-z0-9_\-]+/)?(L_[A-Za-z0-9_]+)', t))
    if m:
        return m.group(1)
    fm = re.search(r'^\s*-\s*(L_[A-Za-z0-9_]+)\s*::', t, re.MULTILINE)
    return fm.group(1) if fm else None


# ===========================================================================
# Live-tree safety: untracked-WIP move, backup/restore, deliverable snapshot.
# ===========================================================================

def _git(repo: Path, *args):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True)


def untracked_test_fixtures(repo: Path = REPO) -> List[Path]:
    """Untracked .cpp/.h WIP fixtures under Source/CraftBenchTests (to move aside)."""
    r = _git(repo, "ls-files", "--others", "--exclude-standard",
             f"{PROJECT_REL}/Source/CraftBenchTests")
    return [repo / ln.strip() for ln in r.stdout.splitlines()
            if ln.strip().endswith((".cpp", ".h"))]


def writable_dirs(project: Path) -> List[Path]:
    return [d for d in (project / SRC_REL, project / CONTENT_TASKS_REL) if d.exists()]


def backup_tree(project: Path, backup: Path) -> int:
    """Snapshot the writable tree (SRC + Content/Tasks) to ``backup`` (NO git)."""
    if backup.exists():
        shutil.rmtree(backup)
    backup.mkdir(parents=True)
    n = 0
    for d in writable_dirs(project):
        for p in d.rglob("*"):
            if p.is_file():
                dst = backup / p.relative_to(project)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dst)
                n += 1
    return n


def restore_tree(project: Path, backup: Path) -> Tuple[int, int]:
    """Restore the writable tree EXACTLY from ``backup`` (delete extras, copy back)."""
    backed = {p.relative_to(backup).as_posix(): p
              for p in backup.rglob("*") if p.is_file()}
    deleted = 0
    for d in writable_dirs(project):
        for p in list(d.rglob("*")):
            if p.is_file() and p.relative_to(project).as_posix() not in backed:
                p.unlink()
                deleted += 1
    restored = 0
    for rel, src in backed.items():
        dst = project / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        restored += 1
    return restored, deleted


def snapshot(*dirs: Path, repo: Path = REPO) -> Dict[str, tuple]:
    """(size, mtime) of every file under each dir, keyed by repo-relative path."""
    out: Dict[str, tuple] = {}
    for d in dirs:
        if d.exists():
            for p in d.rglob("*"):
                if p.is_file():
                    try:
                        st = p.stat()
                        out[str(p.relative_to(repo))] = (st.st_size, int(st.st_mtime))
                    except OSError:
                        pass
    return out


def diff_deliverable(before: Dict[str, tuple], after: Dict[str, tuple]
                     ) -> Tuple[List[str], List[str]]:
    """(new, changed) repo-relative paths between two snapshots."""
    new = sorted(set(after) - set(before))
    chg = sorted(k for k in after if k in before and after[k] != before[k])
    return new, chg


# ===========================================================================
# Proxy-derived telemetry (true on-wire model, sub-agent trace).
# ===========================================================================

def capture_proxy_usage(usage_before: int, model_key: str) -> dict:
    return proxy.usage_since(usage_before, model_key)


def capture_subagent_trace(trace_before: int, model_key: str
                           ) -> Tuple[List[dict], dict]:
    return proxy.subagent_trace_since(trace_before, model_key)


# ===========================================================================
# Grade (run_task.py --submission-from-project) — full standalone path only.
# ===========================================================================

def grade(
    task_id: str,
    *,
    repo: Path = REPO,
    project_rel: str = PROJECT_REL,
    ue_root: str = DEFAULT_UE_ROOT,
    run_dir: Optional[Path] = None,
    runner: Callable = subprocess.run,
    timeout: int = 1500,
    capture_assets: bool = False,
    visible: Optional[bool] = None,
    capture: Optional[bool] = None,
    extra_env: Optional[dict] = None,
    out: Optional[dict] = None,
    log: Callable[[str], None] = print,
) -> Tuple[int, str]:
    """Run run_task.py --submission-from-project (L1 build + L2 PIE). Returns
    (exit_code, stdout). Copies report.json + L1/L2 logs into run_dir.

    ``capture_assets=True`` adds ``--capture-assets`` so the runner first saves
    dirty packages then sweeps ``Content/`` for ``.uasset``/``.umap`` deliverables
    (the BP-deliverable path agents produce through the editor). Default off keeps
    the aura-agent source-only grade unchanged.

    ``visible`` / ``capture`` forward ``--visible`` / ``--capture`` to run_task.py
    (real-RHI L2 legs / screenshot sweep). Default ``None`` reads the CB_VISIBLE /
    CB_CAPTURE env flags, so existing callers inherit the env behavior; an explicit
    True/False always wins over env.

    ``extra_env`` is merged over ``os.environ`` for the grade subprocess (None ->
    inherit unchanged). The aura-product path uses it to cap the cold L1 build's
    parallelism, since the live stack holds RAM during grading.

    ``out`` is an OPTIONAL out-param dict (the return shape stays ``(exit_code,
    stdout)`` so every existing caller keeps working). When given, grade() fills:
      * ``graded_workdir`` — the verifier workdir the grade ran in, or None when
                             nothing of it survives on disk (retention mode
                             ``"none"``, or a workdir a crash took out);
      * ``artifacts``      — run_dir-relative paths of the ``artifacts/`` files
                             copied from the workdir's out/ into run_dir (list);
      * ``report``         — the parsed report.json dict (or None);
      * ``workdir_retention`` — the ``workdir_retention.apply()`` result (the mode
                             ACTUALLY applied, ``reclaimed_bytes``, ``elapsed_s``,
                             plus ``reason`` on a refusal), or None when there was
                             no workdir to act on. Named for the workdir on
                             purpose: summary.json's ``"retention"`` block already
                             means the writable-TREE restore (run_graded.py) — two
                             retentions, two contracts, do not merge the names.
    """
    if visible is None:
        visible = _env_flag("CB_VISIBLE")
    if capture is None:
        capture = _env_flag("CB_CAPTURE")
    # Warm-cache the L1 build (~6x incremental). Env-driven like visible/capture
    # so callers opt in via CB_WARM_CACHE without threading a flag through every
    # layer. When on, the warm slot (path-stable, short) IS the workdir, so we
    # must NOT pin --workdir below — run_task treats an explicit --workdir as
    # "force cold" (warm_cache.py). A warm MISS still falls back to cold safely
    # (never a wrong verdict); prime with `cb warm-prime` so hits are reliable.
    warm_cache = _env_flag("CB_WARM_CACHE")
    if out is None:
        out = {}
    out.setdefault("graded_workdir", None)
    out.setdefault("artifacts", [])
    out.setdefault("report", None)
    out.setdefault("workdir_retention", None)
    # Resolve the spec through the dual-layout resolver (legacy tasks/<id>.md /
    # tasks/<set>/<id>.md AND the folder form tasks/<set>/<id>/task.md) — the old
    # literal f"tasks/{task_id}.md" broke grading a set task by bare id. The
    # verifier subprocess runs with cwd=repo, so a repo-relative path is fine.
    task_spec = tasks.resolve_task_path(repo, task_id)
    if task_spec is None:
        cands = tasks.resolve_task_candidates(repo, task_id)
        if cands:
            opts = "".join(f"\n  {c.relative_to(repo).as_posix()}" for c in cands)
            raise SystemExit(
                f"[grade] ambiguous task id {task_id!r} — use a set-qualified "
                f"'set/id'; candidates:{opts}")
        raise SystemExit(f"[grade] no task spec found for {task_id!r} under tasks/")
    cmd = [sys.executable, "tools/verify-single/run_task.py", "--task",
           task_spec.relative_to(repo).as_posix(),
           "--submission-from-project", project_rel,
           "--ue-root", ue_root, "--keep-workdir"]
    if os.name == "nt" and not warm_cache:
        # Pin a SHORT, fresh verifier workdir so UE build paths stay under the
        # Windows 260-char MAX_PATH limit (the default mkdtemp under %TEMP% blows
        # it -> empty grade report -> spurious FAIL). Honors CRAFTBENCH_WD_ROOT,
        # else <cb_root>/wd (aura_rig.paths).
        # SKIPPED under warm_cache: the warm slot is the (path-stable) workdir,
        # and an explicit --workdir would force run_task to cold-build.
        import hashlib
        from . import paths as cb_paths
        _wd_root = cb_paths.wd_root()
        _wd_root.mkdir(parents=True, exist_ok=True)
        _uniq = run_dir.name if run_dir else task_id
        _pinned_wd = _wd_root / hashlib.sha1(_uniq.encode("utf-8")).hexdigest()[:10]
        cmd += ["--workdir", str(_pinned_wd)]
        out["graded_workdir"] = str(_pinned_wd)
    if warm_cache:
        # The warm slot (short, path-stable) becomes the workdir; graded_workdir
        # is corrected from the parsed report path below.
        cmd.append("--warm-cache")
    if capture_assets:
        cmd.append("--capture-assets")
    if _env_flag("CB_GRADE_FROM_LIVE"):
        # Maintainer escape hatch: grade against the LIVE working tree instead
        # of git HEAD (run_task's default) — the only way to get a REAL verdict
        # while a substrate fix is still uncommitted (e.g. the 2026-07-10
        # gp-gas-launch de-solve). Windows-safe only since the junction-prune +
        # CRLF-tolerant-hash fixes in run_task.py.
        cmd.append("--substrate-from-live")
        log("[grade] CB_GRADE_FROM_LIVE=1 — grading against the LIVE working tree")
    if visible:
        cmd.append("--visible")
    if capture:
        cmd.append("--capture")
    gt0 = time.time()
    grade_env = {**os.environ, **extra_env} if extra_env else None
    gr = runner(cmd, cwd=str(repo), capture_output=True, text=True, timeout=timeout,
                env=grade_env)
    log(f"[grade] exit={gr.returncode}{exit_status.annotate_exit(gr.returncode)}"
        f"  ({time.time()-gt0:.0f}s)")
    if run_dir:
        (run_dir / "grade_stdout.txt").write_text(gr.stdout, encoding="utf-8")
        # stderr was captured (capture_output=True) and then DROPPED on the floor
        # until 2026-07-26 — on the PAID path, which is the one where a lost
        # diagnostic costs real money. Concretely: a run whose grade died before
        # printing anything left an EMPTY grade_stdout.txt and no other trace, so
        # the only way to learn why was to re-derive it from a process sampler.
        # The baseline path had this right all along (run.py writes
        # verifier_stderr.txt); this closes the asymmetry.
        # getattr, not gr.stderr: several tests fake the CompletedProcess with a
        # stub that defines only returncode/stdout.
        _err = getattr(gr, "stderr", None)
        if _err:
            (run_dir / "grade_stderr.txt").write_text(_err, encoding="utf-8")
        m = re.search(r'json report:\s*(\S+)', gr.stdout)
        if m:
            wdout = Path(m.group(1)).parent
            # wdout is the verifier's <workdir>/out — surface the ACTUAL workdir
            # the grade ran in (authoritative over the Windows pinned prediction).
            out["graded_workdir"] = str(wdout.parent)
            for fn in ("report.json", "l1_build.log", "l2_pie.log"):
                src = wdout / fn
                if src.exists():
                    shutil.copy2(src, run_dir / fn)
            # --capture sweeps screenshots into <workdir>/out/artifacts/ — copy
            # them next to the other run artifacts and record run_dir-relative
            # paths. No-op when the dir is absent (default headless grade).
            art_src = wdout / "artifacts"
            if art_src.is_dir():
                copied: List[str] = []
                for p in sorted(art_src.rglob("*")):
                    if p.is_file():
                        rel = p.relative_to(art_src)
                        dst = run_dir / "artifacts" / rel
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(p, dst)
                        copied.append((Path("artifacts") / rel).as_posix())
                out["artifacts"] = sorted(copied)
            report_path = run_dir / "report.json"
            if report_path.exists():
                try:
                    out["report"] = json.loads(
                        report_path.read_text(encoding="utf-8", errors="replace"))
                except ValueError:
                    out["report"] = None
    # RETENTION — dead LAST in this function, and that placement is the whole
    # correctness argument. Measured 2026-07-25 across a 21-run stress test: one
    # graded workdir is 5.54 GB, of which 4.72 GB is
    # <Project>/Intermediate/Build/Win64/x64 (MSVC .obj/.pch nothing downstream
    # ever reads); 24 of them held 121 GB against 128 GB free, and `cb clean
    # --workdirs` deliberately KEEPS every workdir a summary.json still names in
    # graded_workdir — so a finished eval's workdir had no exit. Two orderings
    # are load-bearing:
    #   * report.json / l1_build.log / l2_pie.log and out/artifacts/ are copied
    #     out of the workdir ABOVE. Reclaiming any earlier would delete the run's
    #     own evidence before it was saved.
    #   * it sits outside the gt0 window already logged above, so reclaim time
    #     can never inflate the dashboard-visible verify wall. Its own cost is
    #     reported separately, in out["workdir_retention"]["elapsed_s"].
    # Every refusal (missing dir, outside the wd-root, L1 != pass) lives inside
    # workdir_retention.apply — do NOT re-implement one here. ``warm`` is the one
    # fact only this call site holds: under CB_WARM_CACHE the workdir IS the
    # shared warm slot whose Intermediate/ + Binaries/ ARE the path-bound build
    # cache (warm_cache.py), so slimming it would cost every later verify the 5x
    # L1 speed-up.
    from . import workdir_retention
    if out.get("graded_workdir"):
        out["workdir_retention"] = workdir_retention.apply(
            out["graded_workdir"], workdir_retention.resolve_mode(log=log),
            report=out.get("report"), warm=warm_cache, log=log)
    # ...and only NOW the existence check (mirrors run.py:842). Retention mode
    # "none" leaves graded_workdir naming a path that no longer exists; recorded
    # into summary.json, cb._referenced_workdirs would then read that dead name
    # as a reason to protect it — a permanent KEEP entry for a directory that is
    # already gone, i.e. exactly the class of leak this change exists to remove.
    # Also covers a workdir a crash/reboot took out between grade and write.
    if out.get("graded_workdir") and not Path(out["graded_workdir"]).is_dir():
        out["graded_workdir"] = None
    return gr.returncode, gr.stdout


# verify-single exit code -> rig verdict label. Only 0/1 are GRADED (see
# adapters.base.GRADED_VERDICTS); every other label here is a harness/rejection
# state that pass-rate denominators must exclude.
#
#   2 "ERROR"          usage / spec error — the grade never started. The label
#                      is HISTORICAL and stays exactly as-is: summary.json files
#                      already carry it and its semantics were always non-graded.
#   3 "SUBSTRATE-REJECT" RETIRED-AND-RESERVED code (the removed hash-manifest
#                      reject). Kept mapped so old artifacts still read, never
#                      re-used for anything new.
#   5, 7 "HARNESS-ERROR" the verifier could not produce a verdict at all
#                      (no .uproject in the materialized substrate / empty or
#                      incomplete gating layer set, L1 could not exec the build
#                      tool, a gating layer counted nothing with its
#                      dependencies passing, or an uncaught exception).
#
# 6 is deliberately ABSENT and must stay absent: it is UBT's own build-failure
# code, and docs/harness-tour/02-verify-single.md documents that verify-single
# never emits it.
#
# Keep in lockstep with adapters.base.VERIFIER_EXIT_VERDICT (the same taxonomy
# on the run.py / run_batch.py path). tests/test_verdict_mapping.py asserts the
# two agree key-for-key.
VERDICT = {
    0: "PASS",
    1: "FAIL",
    2: "ERROR",
    3: "SUBSTRATE-REJECT",
    4: "SANDBOX-REJECT",
    5: "HARNESS-ERROR",
    7: "HARNESS-ERROR",
    # 8 = --lite ran (no L1 build, so no verdict was even attempted). Must stay
    # in step with adapters/base.VERIFIER_EXIT_VERDICT — the two are the same
    # taxonomy on two harness paths and test_verdict_mapping pins their equality.
    8: "UNGRADED",
}


def verdict_for_exit(code: int) -> str:
    return VERDICT.get(code, f"exit{code}")
