"""Resolve the `--mcp-config` JSON for the `unreal-mcp` baseline backend.

`unreal-mcp` is the STOCK-tooling counterpart of `aura-mcp`: the same
`claude -p` reasoner, given ONLY Epic's first-party in-editor MCP server
(the Experimental `ModelContextProtocol` plugin that ships in UE 5.8) plus
`AllToolsets`. The server is embedded in the editor process and speaks
streamable HTTP at ``http://127.0.0.1:8000/mcp`` (start it with
``-ModelContextProtocolStartServer`` or ``ModelContextProtocol.StartServer``)
— verified working under a ``-RenderOffScreen`` headless editor on 5.8.0.

Unlike aura_mcp_config.py there is nothing machine-specific to resolve: no
interpreter (no child process — claude connects over HTTP) and no plugin dir
(the plugins are engine-side). The only knob is the URL, via the
``CB_UNREAL_MCP_URL`` env override (e.g. a non-default
``-ModelContextProtocolPort=N``). The server key is ``unreal_mcp`` —
UNDERSCORE, deliberately — so tools namespace as ``mcp__unreal_mcp__*``
(a hyphen would produce the awkward ``mcp__unreal-mcp__*``).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Optional

DEFAULT_URL = "http://127.0.0.1:8000/mcp"

# The claude-p tool namespace key (mcp__unreal_mcp__*).
SERVER_KEY = "unreal_mcp"


def resolve_url(env: Optional[Dict[str, str]] = None) -> str:
    """The Epic MCP endpoint: ``CB_UNREAL_MCP_URL`` env else the :8000 default."""
    env = os.environ if env is None else env
    return (env.get("CB_UNREAL_MCP_URL") or "").strip() or DEFAULT_URL


def build_config_dict(url: str) -> Dict[str, object]:
    """The ``--mcp-config`` dict: one HTTP server, no command/interpreter."""
    return {"mcpServers": {SERVER_KEY: {"type": "http", "url": url}}}


def _generated_config_path() -> Path:
    """Stable path in the OS temp dir (sibling of the generated aura config)."""
    out = Path(tempfile.gettempdir()) / "craftbench"
    out.mkdir(parents=True, exist_ok=True)
    return out / "unreal_mcp.json"


def resolve_unreal_mcp_config(env: Optional[Dict[str, str]] = None) -> Path:
    """Write the machine-correct config to the temp dir; return its path.

    Never raises: there is nothing that can fail to resolve (the URL always
    has a default), so — unlike the aura config — no legacy-file fallback is
    needed. Whether the server is actually UP is the editor lifecycle's job
    (aura_rig.unreal_mcp_stack), gated before dispatch, not here.
    """
    config = build_config_dict(resolve_url(env))
    out = _generated_config_path()
    out.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return out
