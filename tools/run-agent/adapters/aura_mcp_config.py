"""Resolve Aura's MCP `--mcp-config` JSON at runtime (no hardcoded paths).

The legacy ``aura_mcp.json`` was a frozen macOS artifact: it baked in one
machine's home dir (``/Users/<user>/...``), the UE 5.7 *Mac* engine
python, and a Mac-only plugin path. None of that resolves on a Windows box, so
the authentic ``aura-mcp`` backend was effectively Mac-only.

Nothing about Aura's MCP servers actually *needs* those values pinned: the two
server scripts (``unreal_inspector.py`` / ``unreal_editor.py``) resolve the live
project root (``engine_resolver.get_project_root``) and the client port
(``utils.get_client_port`` -> ``aura_client_port.txt``, default 41200) THEMSELVES
at runtime. So the only things the ``--mcp-config`` JSON has to pin are:

  * ``command`` — a python interpreter that can import Aura's MCP deps
    (``mcp.server.fastmcp``, ``aiohttp``, ``requests``, ``pydantic``). Aura ships
    exactly such an interpreter at ``<plugin>/PortablePython/<Plat>/python(.exe)``.
  * ``args``    — the absolute path to each server wrapper script under
    ``<plugin>/MCP/``.

This module resolves all three off the live machine (with env-var escape hatches)
and writes a generated config to the OS temp dir, returning its path. Resolution
is best-effort and NEVER raises at adapter-construction time — a machine with no
Aura plugin still gets a config path back (falling back to the committed legacy
file) so offline unit tests stay green; the real, explainable failure surfaces
when ``claude -p`` tries to launch a server whose command/script doesn't exist.
``resolve_aura_mcp_config`` logs a one-line WARN naming every component it could
not resolve, so that runtime failure is never a mystery.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

# repo/tools/run-agent/adapters/aura_mcp_config.py -> parents[3] == repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]

# The committed legacy config — kept only as a last-resort fallback so adapter
# construction always yields *some* path (and offline tests don't crash).
_LEGACY_CONFIG = Path(__file__).resolve().parent / "aura_mcp.json"

# The two MCP servers Aura exposes, mapped to the wrapper script under <plugin>/MCP/.
# Keys are the server names `claude -p` will namespace tools under (mcp__<key>__*).
_SERVER_SCRIPTS = {
    "unreal_inspector": "unreal_inspector.py",
    "unreal_editor": "unreal_editor.py",
}


def _platform_dir() -> str:
    """Aura's PortablePython sub-dir name for this OS (Windows / Mac / Linux)."""
    if sys.platform == "win32":
        return "Windows"
    if sys.platform == "darwin":
        return "Mac"
    return "Linux"


def resolve_aura_plugin_dir(
    repo_root: Path = _REPO_ROOT, env: Optional[Dict[str, str]] = None
) -> Optional[Path]:
    """Locate the Aura plugin root (the dir containing ``MCP/`` and ``PortablePython/``).

    Priority:
      1. ``CB_AURA_PLUGIN`` env override (explicit escape hatch).
      2. ``<repo>/UE-projects/CraftBenchTemplate/Plugins/Aura`` — the aura-plugin
         clone inside the substrate's Plugins/ (a real dir since the 2026-07 refactor).
         Preferred because it is the plugin the editor loads.
      3. ``CB_GENIUS/Aura`` (explicit override).

    Returns the first candidate that actually contains ``MCP/unreal_inspector.py``,
    else ``None``.
    """
    env = os.environ if env is None else env
    candidates: List[Path] = []
    if env.get("CB_AURA_PLUGIN"):
        candidates.append(Path(env["CB_AURA_PLUGIN"]))
    candidates.append(repo_root / "UE-projects" / "CraftBenchTemplate" / "Plugins" / "Aura")
    if env.get("CB_GENIUS"):
        candidates.append(Path(env["CB_GENIUS"]) / "Aura")

    for cand in candidates:
        try:
            if (cand / "MCP" / "unreal_inspector.py").is_file():
                return cand.resolve()
        except OSError:
            continue
    return None


def resolve_mcp_python(
    plugin_dir: Optional[Path], env: Optional[Dict[str, str]] = None
) -> Optional[str]:
    """Resolve the interpreter that can run Aura's MCP servers (has fastmcp et al.).

    Priority:
      1. ``CB_AURA_MCP_PYTHON`` env override.
      2. Aura's bundled ``<plugin>/PortablePython/<Plat>/python(.exe)`` — this is
         what Aura itself launches the servers with (see ``MCP/run.bat``), and it
         carries all MCP deps. THE preferred interpreter.
      3. The UE engine python (preserves the legacy Mac behavior) under
         ``CB_UE_ROOT/Engine/Binaries/ThirdParty/Python3/<Plat>/...``.

    Returns an absolute interpreter path, or ``None`` if none resolve.
    """
    env = os.environ if env is None else env
    if env.get("CB_AURA_MCP_PYTHON"):
        p = Path(env["CB_AURA_MCP_PYTHON"])
        if p.is_file():
            return str(p)

    plat = _platform_dir()
    if plugin_dir is not None:
        exe = "python.exe" if sys.platform == "win32" else "python3"
        # PortablePython/<Plat>/python(.exe), and a couple of common nested layouts.
        for rel in (
            Path("PortablePython") / plat / exe,
            Path("PortablePython") / plat / "bin" / exe,
            Path("ThirdParty") / "Python" / plat / exe,
        ):
            cand = plugin_dir / rel
            if cand.is_file():
                return str(cand.resolve())

    # UE engine python (legacy Mac path lived here).
    ue_root = env.get("CB_UE_ROOT")
    if ue_root:
        exe = "python.exe" if sys.platform == "win32" else "python3"
        for rel in (
            Path("Engine/Binaries/ThirdParty/Python3") / plat / "bin" / exe,
            Path("Engine/Binaries/ThirdParty/Python3") / plat / exe,
        ):
            cand = Path(ue_root) / rel
            if cand.is_file():
                return str(cand.resolve())
    return None


def build_config_dict(
    python_exe: str, plugin_dir: Path,
    server_env: Optional[Dict[str, str]] = None,
) -> Dict[str, object]:
    """Build the ``--mcp-config`` dict: one stdio server per Aura MCP wrapper.

    ``server_env`` is MERGED into each server's process environment by the MCP
    client (parent env inherited, these keys override). Empty by default. The
    one key that matters is ``LOCALAPPDATA`` — the Aura MCP server reads its
    session token + Aura-server port from ``<LOCALAPPDATA>/Programs/
    aura-client/.Aura``, and pointing it at a SCOPED store rather than the real
    one is what kept a stale prod/expired token from shadowing a fresh session
    (without the override the server read the wrong store and got "No valid
    session token found", measured 2026-08-09). The bring-up that MINTED that
    scoped store was the login machinery, which is not part of this release —
    see ``resolve_aura_mcp_config`` for who sets the var now."""
    servers: Dict[str, object] = {}
    for name, script in _SERVER_SCRIPTS.items():
        servers[name] = {
            "type": "stdio",
            "command": python_exe,
            "args": [str((plugin_dir / "MCP" / script).resolve())],
            "env": dict(server_env or {}),
        }
    return {"mcpServers": servers}


def _generated_config_path() -> Path:
    """Stable, per-platform path in the OS temp dir for the generated config."""
    out = Path(tempfile.gettempdir()) / "craftbench"
    out.mkdir(parents=True, exist_ok=True)
    return out / f"aura_mcp.{_platform_dir().lower()}.json"


def resolve_aura_mcp_config(
    repo_root: Path = _REPO_ROOT,
    env: Optional[Dict[str, str]] = None,
    log: Optional[Callable[[str], None]] = None,
) -> Path:
    """Resolve + write a machine-correct Aura MCP config; return its path.

    Best-effort and non-raising: if the plugin or interpreter can't be resolved
    this logs a WARN and falls back to the committed legacy file so adapter
    construction never fails (offline unit tests stay green). The actionable
    failure then surfaces — with context — when ``claude -p`` launches the server.
    """
    log = log or (lambda m: print(m, file=sys.stderr, flush=True))
    plugin_dir = resolve_aura_plugin_dir(repo_root, env)
    if plugin_dir is None:
        log("WARN  aura-mcp: could not locate the Aura plugin — it is closed-source "
            "and NOT part of this release, so on a public clone this line is "
            "expected: the arm is published to be READ and audited, not run "
            "(THIRD-PARTY.md; adapters/registry.py prints the fuller notice when "
            "the arm is actually selected). If you DO have the plugin, point "
            "CB_AURA_PLUGIN at the directory holding MCP/unreal_inspector.py, or "
            "put it at UE-projects/CraftBenchTemplate/Plugins/Aura; "
            f"falling back to the legacy config {_LEGACY_CONFIG}")
        return _LEGACY_CONFIG

    python_exe = resolve_mcp_python(plugin_dir, env)
    if python_exe is None:
        log("WARN  aura-mcp: could not find an interpreter with Aura's MCP deps "
            f"(looked for {plugin_dir}/PortablePython/{_platform_dir()}/python*, "
            "and CB_UE_ROOT's engine python; set CB_AURA_MCP_PYTHON to override); "
            f"falling back to the legacy config {_LEGACY_CONFIG}")
        return _LEGACY_CONFIG

    # Point the MCP server at a SCOPED LOCALAPPDATA store rather than the real
    # one. `cb` used to set CB_AURA_MCP_LOCALAPPDATA itself, to the store its
    # bring-up had just minted a fresh dev session token into; that bring-up was
    # the login machinery and went out of this release, so the var is now purely
    # an OPERATOR escape hatch — set it yourself if you have the private stack
    # and a token store to point at. Unset (the public case, and any non-cb
    # caller), leave env empty and inherit the real LOCALAPPDATA.
    resolve_env = os.environ if env is None else env
    server_env: Dict[str, str] = {}
    scoped_localappdata = resolve_env.get("CB_AURA_MCP_LOCALAPPDATA")
    if scoped_localappdata:
        server_env["LOCALAPPDATA"] = scoped_localappdata
        log(f"aura-mcp: MCP server LOCALAPPDATA -> {scoped_localappdata} "
            "(scoped session-token store, from CB_AURA_MCP_LOCALAPPDATA)")

    config = build_config_dict(python_exe, plugin_dir, server_env=server_env)
    out = _generated_config_path()
    out.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return out


def diagnose(
    repo_root: Path = _REPO_ROOT, env: Optional[Dict[str, str]] = None
) -> Tuple[Optional[Path], Optional[str], Dict[str, bool]]:
    """Return (plugin_dir, python_exe, {script: exists}) for doctor/CLI reporting."""
    plugin_dir = resolve_aura_plugin_dir(repo_root, env)
    python_exe = resolve_mcp_python(plugin_dir, env) if plugin_dir else None
    scripts: Dict[str, bool] = {}
    if plugin_dir is not None:
        for name, script in _SERVER_SCRIPTS.items():
            scripts[name] = (plugin_dir / "MCP" / script).is_file()
    return plugin_dir, python_exe, scripts
