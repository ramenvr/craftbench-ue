"""aura_port — keep Plugins/Aura/aura_client_port.txt pointing at the LIVE editor.

Why this exists
---------------
Authentic ``aura-mcp`` launches Aura's MCP server *standalone* (via
``claude -p --mcp-config``). That server reads
``Plugins/Aura/aura_client_port.txt`` to learn which local port the running
Aura editor exposes its HTTP API on, then fetches the session token from
``http://127.0.0.1:<port>/api/sessionToken``. If that file is **stale** (a
previous session's port), the token fetch hits the wrong port, and every Aura
write tool returns ``{"error":"No valid session token found..."}``.

That single stale value was misdiagnosed once as a "fundamental cloud-auth
blocker" — it was not; it was a one-line port mismatch (file said 3002, live
editor was on 41200). This module makes the harness **self-healing**: before an
aura-mcp dispatch it probes the live editor and writes the correct port, so the
failure can never silently recur.

Design notes
------------
- The port file is *infrastructure config*, not part of the agent submission, so
  ``ensure_aura_client_port`` writes the live port and **leaves it** (permanent +
  idempotent — a no-op once correct). It is intentionally NOT restored to a stale
  value by the live-project flow's backup/restore.
- The HTTP probe is injectable so the logic is unit-tested without a live editor.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import Callable, List, Optional, Tuple

DEFAULT_AURA_PORT = 41200
PORT_FILE_REL = "Plugins/Aura/aura_client_port.txt"

# An opener takes (url, timeout) and returns (http_status, body_text).
Opener = Callable[[str, float], Tuple[int, str]]


def read_port_file(port_file: Path) -> Optional[int]:
    """Return the integer in the port file, or None if missing/garbage."""
    try:
        return int(port_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _urllib_opener(url: str, timeout: float) -> Tuple[int, str]:
    with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 (localhost only)
        return r.status, r.read().decode("utf-8", "replace")


def probe_aura_port(port: int, *, timeout: float = 1.5, opener: Opener = _urllib_opener) -> bool:
    """True iff a live, signed-in Aura editor answers /api/sessionToken on this port.

    A live+signed-in editor returns HTTP 200 with a non-empty token body. An
    editor that is up but signed out returns an ``error`` payload — treated as
    not-usable so the caller surfaces a clear "sign in" warning rather than
    writing a port that still can't auth.
    """
    url = f"http://127.0.0.1:{port}/api/sessionToken"
    try:
        status, body = opener(url, timeout)
    except Exception:
        return False
    body = (body or "").strip()
    return status == 200 and len(body) > 0 and "error" not in body.lower()


def candidate_ports(current: Optional[int], default: int = DEFAULT_AURA_PORT) -> List[int]:
    """Ports to probe, in priority order: the file's current value, then the default."""
    out: List[int] = []
    if current is not None:
        out.append(current)
    if default not in out:
        out.append(default)
    return out


def discover_live_aura_port(
    candidates: List[int], *, probe: Callable[[int], bool] = probe_aura_port
) -> Optional[int]:
    """First candidate port with a live, signed-in editor — or None."""
    for p in candidates:
        if probe(p):
            return p
    return None


def ensure_aura_client_port(
    project_dir: Path,
    *,
    default_port: int = DEFAULT_AURA_PORT,
    log: Callable[[str], None] = print,
    probe: Callable[[int], bool] = probe_aura_port,
) -> Optional[int]:
    """Normalize the port file to the live editor's port. Return the live port, or None.

    Self-healing + permanent: probes ``[current, default]``; if a live editor is
    found and the file disagrees, rewrites the file (and leaves it). Returns the
    live port on success, or None when this isn't an Aura project / no live editor
    answered (a warning is logged in the latter case).
    """
    port_file = project_dir / PORT_FILE_REL
    if not port_file.parent.exists():
        return None  # not an Aura-enabled project — nothing to normalize

    current = read_port_file(port_file)
    cands = candidate_ports(current, default_port)
    live = discover_live_aura_port(cands, probe=probe)
    if live is None:
        log(
            f"WARNING: no live, signed-in Aura editor answered /api/sessionToken on {cands}. "
            "Authentic aura-mcp will fail auth — open Aura + the live project and sign in."
        )
        return None
    if live != current:
        port_file.write_text(str(live))
        log(f"aura_client_port.txt normalized: {current} -> {live} (live editor port).")
    return live
