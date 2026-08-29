"""Editor lifecycle for the `unreal-mcp` backend (Epic's in-editor MCP server).

The whole "stack" for this backend is ONE process: a headless UnrealEditor on
the substrate with Epic's Experimental `ModelContextProtocol` server started
in-process (``-ModelContextProtocolStartServer``, HTTP :8000/mcp). None of the
Aura bring-up applies — no vercel :3000, no client :3002, no dev-browser, no
Supabase auth — and none of Aura's readiness hazards transfer: the MCP listener
lives IN the editor process, so a fresh process implies a fresh listener (no
stale-port-file / client-rebind failure mode).

The readiness gate still follows the stack.py principle "a REAL round-trip, not
a port probe": we require a full MCP ``initialize`` JSON-RPC exchange (the
server negotiates a protocol version and issues a session id) before a drive is
dispatched. Empirically the HTTP port answers only once the server is live, but
initialize also proves the JSON-RPC layer — and is what `claude -p` will do
first.

Spike-verified on UE 5.8.0 / Windows (2026-07-02): editor launched with
``-RenderOffScreen -unattended ... -DisablePlugins=Reflex,Aura
-ModelContextProtocolStartServer`` serves initialize/tools-list/tools-call, and
``claude -p --mcp-config --strict-mcp-config`` drives the lazy 3-tool surface
(list_toolsets / describe_toolset / call_tool) end-to-end.

NOTE on backend mixing: this editor deliberately runs with the Aura plugin
DISABLED (clean stock-tooling baseline), so it exposes neither RC :30010 nor
Aura's bridge. Aura-path code that keys readiness on those will treat this
editor as "down"; switching aura-* <-> unreal-mcp between runs is safe because
both paths start by reaping craftbench-scoped editors (kill_craftbench_editors
spares foreign ones).
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

from adapters.unreal_mcp_config import DEFAULT_URL, resolve_url
from aura_rig import stack

Log = Callable[[str], None]

# Editor cold boot on the substrate is ~1-3 min warm, worse cold — mirror the
# generous ceiling the Aura path uses for its editor gate.
BOOT_TIMEOUT_S = 480


def _mcp_initialize_once(url: str, timeout: float = 10.0) -> bool:
    """One MCP ``initialize`` round-trip. True iff the server negotiated.

    Streamable-HTTP servers may answer JSON *or* SSE; parse both, tolerantly —
    an empty/dataless body counts as NOT ready (matches the tool-execute gate's
    success-by-evidence principle, never success-by-connect)."""
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "craftbench-gate", "version": "0"}},
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            if "text/event-stream" in (resp.headers.get("Content-Type") or ""):
                lines = [l[5:].strip() for l in raw.splitlines() if l.startswith("data:")]
                raw = lines[-1] if lines else ""
            if not raw.strip():
                return False
            parsed = json.loads(raw)
            return isinstance(parsed, dict) and "result" in parsed
    except (urllib.error.URLError, ConnectionError, OSError, ValueError):
        return False


def unreal_mcp_ready(url: str = DEFAULT_URL, timeout_s: int = BOOT_TIMEOUT_S,
                     interval: float = 5.0, log: Log = print) -> bool:
    """Poll until a real MCP initialize round-trips on <url>, or time out."""
    end = time.time() + timeout_s
    while True:
        if _mcp_initialize_once(url):
            return True
        remaining = end - time.time()
        if remaining <= 0:
            return False
        log(f"  ..    waiting for the editor MCP server at {url} "
            f"({int(remaining)}s left)")
        time.sleep(min(interval, max(remaining, 0.1)))


def _port_of(url: str) -> int:
    parsed = urlparse(url)
    return parsed.port or (443 if parsed.scheme == "https" else 80)


def editor_launch_args(ue, uproject, *, visible: bool = False,
                       port: Optional[int] = None) -> list:
    """The Epic-MCP editor launch argv. ``visible=True`` (CB_VISIBLE) drops ONLY
    ``-RenderOffScreen`` (real window); ``-unattended``/``-nosplash``/``-nopause``/
    ``-nosound`` and the MCP server switch stay in ALL modes."""
    eargs = [
        str(ue), str(uproject), "-RenderOffScreen", "-unattended", "-nosplash",
        "-nopause", "-nosound", "-DisablePlugins=Reflex,Aura",
        "-ModelContextProtocolStartServer", "-log",
    ]
    if port is not None and port != _port_of(DEFAULT_URL):
        eargs.insert(-1, f"-ModelContextProtocolPort={port}")
    if visible:
        eargs.remove("-RenderOffScreen")
    return eargs


def _editor_cmdlines_ps() -> "dict[int, str]":
    """Windows-only fallback for editor cmdline enumeration: psutil is absent on
    this rig's stock interpreter and wmic is REMOVED on current Win11 builds, so
    stack._editor_procs() can come back empty. CIM via powershell still works."""
    if os.name != "nt":
        return {}
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='UnrealEditor.exe'\" | "
             "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }"],
            capture_output=True, text=True, timeout=25,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    procs: "dict[int, str]" = {}
    for line in out.splitlines():
        pid, _, cl = line.partition("\t")
        if pid.strip().isdigit():
            procs[int(pid.strip())] = cl.strip().lower()
    return procs


def _port_owner_is_foreign(port: int) -> Optional[bool]:
    """True/False = the :<port> listener is/isn't a non-craftbench process;
    None = can't attribute (no listener found, or process enumeration failed —
    callers fail-open with a WARN, matching stack.py's enumeration policy)."""
    pids = stack._listening_pids(port)
    if not pids:
        return None
    editors = dict(stack._editor_procs()) or _editor_cmdlines_ps()
    if not editors:
        return None  # can't enumerate ANY process cmdlines -> can't attribute
    for pid in pids:
        cl = editors.get(pid)
        if cl is None:
            return True   # someone non-UnrealEditor owns the MCP port
        if not stack._is_craftbench_editor(cl):
            return True
    return False


def ensure_unreal_mcp_editor(uproject: Path, ue: Path, *, fresh: bool = True,
                             log: Log = print) -> bool:
    """Bring up (or verify) the headless Epic-MCP editor on <uproject>.

    fresh=True (the per-drive default, mirroring `cb eval`'s aura paths): reap
    craftbench-scoped editors and launch a brand-new process, so a drive can't
    inherit the prior run's in-editor state. fresh=False (--reuse-editor):
    accept an already-ready server, launching only if none answers.

    Refuses to proceed when the MCP port is owned by a NON-craftbench process
    (e.g. another project's editor with the flag on, or an unrelated :8000
    service) — killing or driving it would sabotage the user's own session.
    CB_ALLOW_FOREIGN_EDITOR=1 overrides, exactly like the Aura-path guard.
    """
    url = resolve_url()
    port = _port_of(url)
    override = os.environ.get("CB_ALLOW_FOREIGN_EDITOR", "").lower() in ("1", "true", "yes")

    answering = _mcp_initialize_once(url, timeout=3.0)
    if answering:
        foreign = _port_owner_is_foreign(port)
        if foreign and not override:
            log(f"  FAIL  something OTHER than a CraftBench editor already serves {url}")
            log("        — close it (or point CB_UNREAL_MCP_URL at a free port +")
            log("        -ModelContextProtocolPort=N), or set CB_ALLOW_FOREIGN_EDITOR=1.")
            return False
        if foreign is None:
            log(f"  WARN  {url} answers but the owner could not be attributed; proceeding")
        if not fresh:
            log(f"  OK    editor MCP already ready at {url} (--reuse-editor)")
            return True

    # Fresh (or nothing ready yet): reap craftbench editors, launch, gate.
    if fresh:
        stack.kill_craftbench_editors(log)
        time.sleep(3)

    if not fresh and not answering and _mcp_initialize_once(url, timeout=3.0):
        return True  # raced up between probes

    _visible = stack.env_flag("CB_VISIBLE")
    log(f"  ..    launching {'VISIBLE' if _visible else 'headless'} editor on "
        f"{uproject} with Epic MCP (detached; warm-up ~1-3min)")
    eargs = editor_launch_args(ue, uproject, visible=_visible, port=port)
    log_path = stack.StackPaths().log / "cb_unrealmcp_editor.log"
    stack.start_detached(eargs, cwd=uproject.parent, log_path=log_path)

    if unreal_mcp_ready(url, BOOT_TIMEOUT_S, log=log):
        log(f"  OK    editor MCP ready at {url} (initialize round-trips)")
        return True
    # POINT AT THE LOG THAT HAS CONTENT. `-log` makes UE write to its OWN
    # Saved/Logs/<Project>.log; the redirected stdout this launcher captures is
    # ALWAYS ~0 bytes, so the old message sent the reader to an empty file and made
    # every bring-up failure look identical and information-free. Measured
    # 2026-08-18: diagnosing one cost an hour, and the actual cause (below) was
    # sitting in the project log the whole time.
    ue_log = uproject.parent / "Saved" / "Logs" / f"{uproject.stem}.log"
    log(f"  FAIL  editor MCP never became ready at {url}")
    log(f"        editor log (has the real error): {ue_log}")
    log(f"        launcher stdout (usually EMPTY, -log redirects): {log_path}")
    # The cause that is invisible in any log, because the process dies before
    # writing one: a fresh git worktree or clone has no Binaries/ (gitignored), so a
    # C++ project cannot load at all — 0-byte log, exit 1, no message anywhere.
    binaries = uproject.parent / "Binaries" / "Win64"
    built = binaries.is_dir() and any(binaries.glob("UnrealEditor-*.dll"))
    if not built:
        log(f"        LIKELY CAUSE: no built binaries at {binaries} — this project "
            f"has never been compiled here (a fresh worktree/clone has none; "
            f"Binaries/ is gitignored). Build once:")
        log(f'          "{ue}/../../Build/BatchFiles/Build.bat" {uproject.stem}Editor '
            f'Win64 Development -Project="{uproject}" -NoUBA -MaxParallelActions=4')
    return False
