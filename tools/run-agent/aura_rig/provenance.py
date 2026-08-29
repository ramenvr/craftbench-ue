"""provenance — archive WHAT a run produced + the context it ran in.

A graded run leaves a `runs/<lane>/<ts>/` dir that, on its own, holds only the
trace. This module adds the *provenance* layer: the deliverable assets the run
produced, the run-window screenshots, the available-tool manifest, and a
reproducibility manifest (versions / git SHA / model / timestamps) — so a run is
self-describing and replayable.

Each capture is a SMALL, individually unit-testable function. All I/O is behind an
injectable seam (an HTTP opener, a `runner` callable, a clock), so the whole module
imports cleanly and is exercised OFFLINE with no editor, no socket, no UE install.

The functions, and what each proves:

  * capture_tool_manifest   GET :41200/api/mcp -> the AVAILABLE tools this run could
                            use (the MCP servers expanded to their tool lists).
  * capture_assets          flush dirty packages + sweep Content/ for the produced
                            .uasset deliverables (reuses asset_capture.py verbatim).
  * capture_screenshots     copy the EPHEMERAL run-window PNGs (overwritten next run)
                            into run_dir/screenshots/ by mtime.
  * genius_provenance       which Aura plugin ACTUALLY ran (junction target, version,
                            repo sha + dirty) vs the one the rig is configured to run.
  * build_run_manifest      a reproducibility dict (engine ver, Aura plugin ver, git
                            SHA, wire model, timestamps, substrate-hash ref, exposed
                            tool count) + the sub-agent model/token verdicts.
  * capture_subagent_telemetry  what CAN be established about the sub-agent loop from
                            LOCAL records: the dev server's '[usage] billed' lines as
                            a crosscheck, plus explicit UNRESOLVED verdicts for the
                            sub-agent model and its token/cost usage.

Sub-agent cost + model accounting in this release:
  The sub-agent LLM loop runs cloud-side, and its per-call billing was only ever
  readable through a third party's private production service. That readback is NOT
  part of this release (see THIRD-PARTY.md §4), so sub-agent tokens and USD are
  UNAVAILABLE rather than zero: every consumer sees ``available: False`` and a stated
  reason, never a fabricated number it could sum into a run cost.

  The sub-agent model is likewise NOT the main-loop wire model — sub-agents read the
  renderer picker model (default opus-4.8) while the headless ``/api/chat`` ``model``
  field sets only the MAIN loop. With billing gone there is no authoritative source
  for it, so the verdict says so instead of proxying the wire model. The only local
  signal is the dev server's '[usage] billed ... model=' lines, recorded as a
  crosscheck and never promoted to the verdict.
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
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import driver as _driver

# --- well-known local geometry (overridable in every function for tests) -----
# REPO + GW reuse driver's single source of truth (env-overridable: CRAFTBENCH_REPO
# / CB_GATEWAY, with the original Mac literal / :41200 as the preserved fallback).
REPO = _driver.REPO
PROJECT_REL = "UE-projects/CraftBenchTemplate"
GW = _driver.GW
SCREENSHOT_DIR_REL = "Saved/Screenshots/AuraScreenshots"
# tools/verify-single — asset_capture lives there; _import_asset_capture puts it on
# sys.path when it is not already importable.
VERIFY_SINGLE_DIR = Path(__file__).resolve().parents[2] / "verify-single"
_CB_TMP = Path(os.environ.get("CB_TMP", tempfile.gettempdir()))
VERCELSERVER_LOG = _CB_TMP / "vercelserver_3008.log"
# The verifier hash manifest retired 2026-07-16 (git provenance = pinning
# substrate_revision superseded it). The report key "substrate_hashes_ref"
# stays for wire-format stability — downstream consumers still see the key —
# but it now emits null; there is no manifest file to point at.
SUBSTRATE_HASHES_REL = None

# The per-thread billing readback against the proprietary backend was removed for the
# open-source release: the per-thread usage GET, the session-token fetch that
# authenticated it, and the ledger summation it fed all described and depended on a
# third party's private production service. They were removed rather than stubbed.
# Cost accounting in this release comes from the local run records only, and sub-agent
# cost is reported ABSENT rather than zero. See THIRD-PARTY.md §4.

def _import_asset_capture():
    """Import tools/verify-single/asset_capture, adding its dir to sys.path if needed."""
    try:
        import asset_capture  # type: ignore  # noqa: F401
        return asset_capture
    except ImportError:
        if str(VERIFY_SINGLE_DIR) not in sys.path and VERIFY_SINGLE_DIR.exists():
            sys.path.insert(0, str(VERIFY_SINGLE_DIR))
        import asset_capture  # type: ignore  # noqa: F401
        return asset_capture


# ===========================================================================
# (a) capture_tool_manifest — the AVAILABLE tools this run could use.
# ===========================================================================

def _default_mcp_opener(url: str, timeout: float) -> bytes:
    """Real GET returning the /api/mcp response bytes (localhost, read-only)."""
    with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 localhost
        return r.read()


def parse_tool_manifest(payload) -> dict:
    """Pure: reduce an /api/mcp response into a {servers, tool_count, tools} manifest.

    The endpoint returns a LIST of MCP servers, each ``{name, status, toolInfo:[{name,
    description, inputSchema}, ...]}``. We record, per server, its name/status and the
    list of tool names, plus the flat union of tool names and the grand total. Tolerant
    of a dict-wrapped list, missing keys, and non-list payloads (-> empty manifest).
    """
    servers_in = payload
    if isinstance(payload, dict):
        # Some builds wrap the list (e.g. {"servers":[...]}); accept either.
        for key in ("servers", "mcpServers", "data"):
            if isinstance(payload.get(key), list):
                servers_in = payload[key]
                break
    if not isinstance(servers_in, list):
        return {"servers": [], "tool_count": 0, "tools": []}
    servers: List[dict] = []
    all_names: List[str] = []
    for srv in servers_in:
        if not isinstance(srv, dict):
            continue
        info = srv.get("toolInfo") or srv.get("tools") or []
        names = [t.get("name") for t in info
                 if isinstance(t, dict) and t.get("name")]
        servers.append({
            "name": srv.get("name"),
            "status": srv.get("status"),
            "tool_count": len(names),
            "tools": names,
        })
        all_names.extend(names)
    return {
        "servers": servers,
        "tool_count": len(all_names),
        "tools": sorted(set(all_names)),
    }


def capture_tool_manifest(
    *,
    gw: str = GW,
    timeout: float = 8.0,
    opener: Optional[Callable[[str, float], bytes]] = None,
    run_dir: Optional[Path] = None,
) -> dict:
    """GET ``gw/api/mcp`` and return the available-tool manifest (read-only).

    On any failure (editor down, bad JSON) returns a structured empty manifest with
    an ``error`` field rather than raising — provenance capture must never block a
    completed run. ``opener(url, timeout)->bytes`` is the injectable HTTP seam;
    when None it resolves the module-level ``_default_mcp_opener`` at CALL time (so a
    monkeypatched seam is honoured). When ``run_dir`` is given, also writes
    ``tool_manifest.json``.
    """
    if opener is None:
        opener = _default_mcp_opener
    manifest: dict
    try:
        raw = opener(gw + "/api/mcp", timeout)
        payload = json.loads(raw)
        manifest = parse_tool_manifest(payload)
    except Exception as e:  # noqa: BLE001 — never block capture
        manifest = {"servers": [], "tool_count": 0, "tools": [],
                    "error": f"{type(e).__name__}: {e}"[:200]}
    if run_dir is not None:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "tool_manifest.json").write_text(
            json.dumps(manifest, indent=2))
    return manifest


# ===========================================================================
# (b) capture_assets — flush dirty packages, snapshot produced .uasset files.
# ===========================================================================

def capture_assets(
    *,
    run_dir: Path,
    project_root: Path,
    manifest_allow_prefixes,
    manifest_deny_prefixes,
    ue_root: Optional[Path] = None,
    do_save_dirty: bool = True,
    _save_all_dirty: Optional[Callable] = None,
    _capture_content_assets: Optional[Callable] = None,
) -> dict:
    """Persist + snapshot the produced .uasset deliverables into ``run_dir/assets/``.

    Reuses ``tools/verify-single/asset_capture.py`` (NOT re-invented): first runs the
    headless ``save_all_dirty`` editor pass so in-memory sub-agent packages hit disk,
    then sweeps ``Content/`` for asset files the sandbox would accept (under an allow
    prefix, not under a deny prefix). Returns ``{captured:[rel...], count, save:{...}}``.

    ``_save_all_dirty`` / ``_capture_content_assets`` are injectable so this is fully
    offline-testable; in production they default to asset_capture's functions. The
    save step is skipped when ``do_save_dirty`` is False or ``ue_root`` is None (e.g.
    the editor already saved, or no UE install) — the sweep still runs against disk.
    """
    if _capture_content_assets is None:
        _capture_content_assets = _import_asset_capture().capture_content_assets

    assets_dir = run_dir / "assets"
    save_info: dict = {"ran": False}
    if do_save_dirty and ue_root is not None:
        if _save_all_dirty is None:
            _save_all_dirty = _import_asset_capture().save_all_dirty_assets
        res = _save_all_dirty(
            ue_root=Path(ue_root),
            project_path=project_root,
            log_path=run_dir / "save_all_dirty.log",
        )
        save_info = {
            "ran": True,
            "status": getattr(res, "status", None),
            "exit_code": getattr(res, "exit_code", None),
        }

    captured = _capture_content_assets(
        project_root=project_root,
        out_dir=assets_dir,
        deny_prefixes=tuple(manifest_deny_prefixes or ()),
        allow_prefixes=tuple(manifest_allow_prefixes or ()),
    )
    result = {"captured": list(captured), "count": len(captured), "save": save_info}
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "assets_captured.json").write_text(json.dumps(result, indent=2))
    return result


# ===========================================================================
# (c) capture_screenshots — copy EPHEMERAL run-window PNGs before they vanish.
# ===========================================================================

def capture_screenshots(
    run_dir: Path,
    since_ts: float,
    *,
    project_root: Path = REPO / PROJECT_REL,
    screenshot_dir_rel: str = SCREENSHOT_DIR_REL,
    now: Optional[float] = None,
) -> dict:
    """Copy AuraScreenshots PNGs with mtime >= ``since_ts`` into ``run_dir/screenshots/``.

    Aura writes viewport/PIE/window PNGs into
    ``<project>/Saved/Screenshots/AuraScreenshots/`` and OVERWRITES them next run, so
    a run must snapshot them while they exist. We select by mtime >= since_ts (the run
    start) so a prior run's stale PNGs are excluded. Returns
    ``{copied:[name...], count, source}``. Missing dir -> empty result, never raises.
    """
    src_dir = project_root / screenshot_dir_rel
    out_dir = run_dir / "screenshots"
    copied: List[str] = []
    if src_dir.exists():
        for png in sorted(src_dir.glob("*.png")):
            try:
                if png.stat().st_mtime >= since_ts:
                    out_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(png, out_dir / png.name)
                    copied.append(png.name)
            except OSError:
                continue
    return {
        "copied": copied,
        "count": len(copied),
        "source": str(src_dir),
        "since_ts": since_ts,
    }


# ===========================================================================
# (d) build_run_manifest — the reproducibility + telemetry-verdict manifest.
# ===========================================================================

def _git_sha(repo: Path, runner: Callable = subprocess.run) -> Optional[str]:
    try:
        r = runner(["git", "-C", str(repo), "rev-parse", "HEAD"],
                   capture_output=True, text=True, timeout=15)
        out = (r.stdout or "").strip()
        return out or None
    except Exception:  # noqa: BLE001
        return None


def read_aura_plugin_version(uplugin_path: Path) -> Optional[str]:
    """Pull ``VersionName`` from an Aura.uplugin (e.g. '0.13.13'); None if absent."""
    try:
        data = json.loads(uplugin_path.read_text(encoding="utf-8"))
        return data.get("VersionName")
    except Exception:  # noqa: BLE001
        return None


def read_engine_association(uproject_path: Path) -> Optional[str]:
    """Pull ``EngineAssociation`` from the .uproject (e.g. '5.8')."""
    try:
        data = json.loads(uproject_path.read_text(encoding="utf-8"))
        return data.get("EngineAssociation")
    except Exception:  # noqa: BLE001
        return None


def _git_dirty(repo: Path, subpath: str = ".",
               runner: Callable = subprocess.run) -> Optional[bool]:
    """True dirty / False clean / None UNKNOWN (git itself failed).

    A failed git (exit 128 in a non-repo dir, dubious ownership) prints
    nothing to stdout, so reading stdout alone scored the failure as CLEAN:
    every copy-era scratch stamped plugin_repo_dirty=False off its non-repo
    Plugins/ parent while the rig sat dirty (2026-08-05 glide-bp matrix).
    """
    try:
        r = runner(["git", "-C", str(repo), "status", "--porcelain",
                    "--untracked-files=no", "--", subpath],
                   capture_output=True, text=True, timeout=15)
        if getattr(r, "returncode", 0) != 0:
            return None
        return bool((r.stdout or "").strip())
    except Exception:  # noqa: BLE001
        return None


def genius_provenance(project_dir: Path, *, environ: Optional[dict] = None,
                      runner: Callable = subprocess.run) -> dict:
    """Which Aura ACTUALLY ran, vs which the rig is configured to run.

    The Plugins/Aura junction can be re-pointed by hand (e.g. at a veval
    worktree) while stack.py keeps resolving CB_GENIUS / the sibling
    aura-plugin for vercel + client — a silent version split. Record both
    sides so every run's summary.json is version-attributable:

      plugin_link_target / aura_plugin_version / plugin_repo_sha+dirty
          the junction's REAL target and its repo state (the editor plugin);
      genius_root / genius_sha
          the stack-configured repo (vercel + client + skills);
      split
          True when the junction does not live under genius_root.
    """
    env = os.environ if environ is None else environ
    out: dict = {"plugin_link_target": None, "aura_plugin_version": None,
                 "plugin_repo_sha": None, "plugin_repo_dirty": None,
                 "plugin_copy_src": None, "plugin_copy_sha": None,
                 "plugin_copied_at": None,
                 "genius_root": None, "genius_sha": None, "split": None}
    target = None
    try:
        link = project_dir / "Plugins" / "Aura"
        if link.exists():
            target = link.resolve()
            out["plugin_link_target"] = str(target)
            out["aura_plugin_version"] = read_aura_plugin_version(
                target / "Aura.uplugin")
            out["plugin_repo_sha"] = _git_sha(target.parent, runner)
            out["plugin_repo_dirty"] = _git_dirty(target.parent, "Aura", runner)
            # Copy-era scratches (ensure_scratch_plugins) are real dirs, not
            # junctions — their origin is the provenance marker written at
            # copy time, not the (non-repo) parent dir.
            try:
                mk = json.loads((target / ".cb-plugin-provenance.json")
                                .read_text(encoding="utf-8"))
                out["plugin_copy_src"] = mk.get("src")
                out["plugin_copy_sha"] = mk.get("genius_sha")
                out["plugin_copied_at"] = mk.get("copied_at")
                if out["plugin_repo_sha"] is None:
                    out["plugin_repo_sha"] = mk.get("genius_sha")
                # A copy has no repo of its own; dirty resolves against the
                # copy SOURCE repo, and only while its HEAD still matches the
                # copy-time sha — a moved rig describes a different tree, so
                # the honest answer there stays None.
                if out["plugin_repo_dirty"] is None and mk.get("src"):
                    src = Path(mk["src"])
                    if mk.get("genius_sha") and (
                            _git_sha(src.parent, runner) == mk["genius_sha"]):
                        out["plugin_repo_dirty"] = _git_dirty(
                            src.parent, src.name, runner)
            except (OSError, ValueError):
                pass
    except Exception:  # noqa: BLE001
        pass
    try:
        genius = Path(env["CB_GENIUS"]) if env.get("CB_GENIUS") else None
        if genius is None:
            # Mirror StackPaths' resolution: craftbench/.env CB_GENIUS -> sibling.
            cbenv = REPO / ".env"
            if cbenv.exists():
                try:
                    m = re.search(r"^\s*CB_GENIUS\s*=\s*(.+?)\s*$",
                                  cbenv.read_text(encoding="utf-8", errors="replace"),
                                  re.MULTILINE)
                    if m and m.group(1) and not m.group(1).startswith("#"):
                        from . import stack as _stack  # local: keep module import-light
                        val = _stack._dotenv_value(m.group(1))
                        if val:
                            genius = Path(val)
                except OSError:
                    pass
        if genius is None:
            # aura-plugin is cloned into <substrate>/Plugins/ (the 2026-07 refactor).
            genius = REPO / "UE-projects" / "CraftBenchTemplate" / "Plugins"
        if genius.is_dir():
            out["genius_root"] = str(genius)
            out["genius_sha"] = _git_sha(genius, runner)
            if target is not None:
                if out.get("plugin_copy_sha") or out.get("plugin_copy_src"):
                    # Marker-anchored copy: split iff the copy's recorded
                    # origin is not THIS rig at ITS CURRENT sha.
                    out["split"] = (
                        out.get("plugin_copy_src") != str(genius / "Aura")
                        or out.get("plugin_copy_sha") != out["genius_sha"])
                elif genius.resolve() in target.parents:
                    out["split"] = False   # junction/dir living under the rig
                else:
                    # Unanchored real copy (pre-marker vintage): which Aura
                    # this is cannot be known — say so EXPLICITLY instead of
                    # leaving a silent null (2026-07-22 audit finding).
                    out["split"] = None
                    out["plugin_copy_unanchored"] = True
    except Exception:  # noqa: BLE001
        pass
    return out


def subagent_model_verdict(wire_model, model_key) -> dict:
    """The sub-agent MODEL verdict — UNRESOLVED, and explicit about why.

    The sub-agent model is NOT the main-loop wire model: sub-agents read the RENDERER
    picker model (``state.model``, default ``opus-4.8``), while the headless
    ``/api/chat`` ``model`` field sets ONLY the main loop. The one authoritative source
    was the cloud billing ledger, which is not part of this release, so this reports
    ``available: False`` / ``model: None`` and states that the ``wire_model`` is NOT a
    substitute — rather than proxying it and recording a model that was never used.
    Still NOT pinned to the hardcoded sonnet-4.5 default either.
    """
    return {
        "model_key": model_key,
        "available": False,
        "model": None,
        "source": None,
        "derivation": "sub-agents use the renderer picker model (state.model, "
                      "default opus-4.8); the headless /api/chat `model` field sets "
                      "only the MAIN loop, NOT sub-agents, so the sub-agent model is "
                      "DECOUPLED from the main-loop wire model.",
        "pinned_to_default": False,
        "lands_on_renderer_default": "opus-4.8 unless the renderer picker UI was "
                                     "changed; the /api/chat `model` field does NOT "
                                     "change it.",
        "hardcoded_default_ignored": "anthropic/claude-sonnet-4-5-20250929",
        "main_loop_wire_model": wire_model,
        "wire_model_is_not_a_proxy": "the main-loop wire_model is DECOUPLED from the "
                                     "sub-agent model; do NOT use it as a proxy.",
        "local_crosscheck_only": "the dev server's '[usage] billed ... model=' lines "
                                 "are recorded as evidence (model_local_crosscheck) "
                                 "and only exist when sub-agents happened to route "
                                 "locally; they are not the verdict.",
    }


def subagent_token_verdict() -> dict:
    """The sub-agent TOKEN verdict — UNAVAILABLE in this release, and never zero.

    The sub-agent LLM loop runs cloud-side, so its per-call token/credit usage was only
    ever readable from the vendor's private billing ledger; that readback is not part
    of this release, and the local anthropic proxy only ever saw the MAIN loop. So we
    record the absence explicitly — no totals, no ``credits`` key, no fabricated 0 —
    because a zero here would be summed into a run cost as if it had been measured.
    """
    return {
        "available": False,
        "reachable": "cloud",
        "reason": "the sub-agent LLM loop runs cloud-side; its per-call billing is "
                  "not readable from this release, and the local proxy sees only the "
                  "MAIN loop.",
        "not_zero": "ABSENT, not zero — do not sum this into a run cost.",
    }


def build_run_manifest(
    *,
    task_id: str,
    run_dir: Path,
    model_key: Optional[str],
    wire_model: Optional[str],
    ts_start: float,
    ts_end: Optional[float] = None,
    repo: Path = REPO,
    project_rel: str = PROJECT_REL,
    exposed_tool_count: Optional[int] = None,
    aura_uplugin: Optional[Path] = None,
    git_runner: Callable = subprocess.run,
    now: Optional[float] = None,
    subagent_model: Optional[dict] = None,
    subagent_token: Optional[dict] = None,
) -> dict:
    """Assemble the reproducibility + telemetry-verdict manifest and write it.

    Records: engine version, Aura plugin version, git SHA, the MAIN-loop wire model,
    run timestamps, the substrate-hash manifest reference, the exposed-tool count, and
    the sub-agent MODEL + TOKEN verdicts.

    A caller that already built the sub-agent verdicts (e.g. from one
    ``capture_subagent_telemetry`` call) passes them as ``subagent_model`` /
    ``subagent_token`` and they are recorded verbatim; otherwise the explicit
    UNRESOLVED verdicts are recorded. Neither is ever fetched from a remote service —
    sub-agent model and cost are not measurable in this release, and the verdicts say
    so rather than reporting a zero. Writes ``run_dir/run_manifest.json``.
    """
    project = repo / project_rel
    uproject = project / "CraftBenchTemplate.uproject"

    if subagent_token is None:
        subagent_token = subagent_token_verdict()
    if subagent_model is None:
        subagent_model = subagent_model_verdict(wire_model, model_key)

    manifest = {
        "task_id": task_id,
        "captured_at": now if now is not None else time.time(),
        "git_sha": _git_sha(repo, git_runner),
        "engine_version": read_engine_association(uproject),
        "aura_plugin_version": (read_aura_plugin_version(aura_uplugin)
                                if aura_uplugin else None),
        "model_key": model_key,
        "wire_model": wire_model,
        "ts_start": ts_start,
        "ts_end": ts_end,
        "elapsed_s": (round(ts_end - ts_start, 1)
                      if (ts_end is not None and ts_start is not None) else None),
        "substrate_hashes_ref": SUBSTRATE_HASHES_REL,
        "exposed_tool_count": exposed_tool_count,
        "subagent_model": subagent_model,
        "subagent_token": subagent_token,
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


# ===========================================================================
# (e) capture_subagent_telemetry — the local :3008 crosscheck + honest verdicts.
# ===========================================================================

_BILLED_RE = re.compile(
    r"\[usage\]\s+billed\s+thread=(?P<thread>\S+)\s+provider=(?P<provider>\S+)\s+"
    r"model=(?P<model>\S+)\s+credits=(?P<credits>\d+)")


def parse_vercelserver_billed(text: str, *, thread_filter: Optional[str] = None
                              ) -> List[dict]:
    """Pure: extract '[usage] billed ...' lines from a :3008 log into records.

    Each match -> {thread, provider, model, credits}. When ``thread_filter`` is given,
    keep only lines whose thread CONTAINS it (sub-agent threads are aura_tool_<id>,
    not the run thread, so substring match is the loosest sane filter — pass None to
    take all). Tolerant of unrelated log lines.
    """
    out: List[dict] = []
    for m in _BILLED_RE.finditer(text or ""):
        d = m.groupdict()
        if thread_filter and thread_filter not in d["thread"]:
            continue
        out.append({
            "thread": d["thread"],
            "provider": d["provider"],
            "model": d["model"],
            "credits": int(d["credits"]),
        })
    return out


def capture_subagent_telemetry(
    *,
    wire_model: Optional[str],
    model_key: Optional[str] = None,
    run_dir: Optional[Path] = None,
    vercelserver_log: Path = VERCELSERVER_LOG,
    thread_filter: Optional[str] = None,
) -> dict:
    """Capture what can be established about the sub-agent loop from LOCAL records.

    The sub-agent MODEL and its TOKEN/cost usage are UNRESOLVED here: both were only
    ever readable from the cloud billing ledger, which is not part of this release. So
    both blocks are the explicit ``available: False`` verdicts — never a proxied model,
    never a zero cost (see ``subagent_model_verdict`` / ``subagent_token_verdict``).

    What IS real is ``model_local_crosscheck``: a cheap LOCAL grep of the dev :3008 log
    for '[usage] billed ... model=' (present only when sub-agents happened to route
    through dev :3008; EMPTY otherwise — expected, not a failure). It is recorded as
    evidence, not promoted to the verdict.

    Returns a dict; writes ``run_dir/subagent_telemetry.json`` when ``run_dir`` given.
    """
    model_block = subagent_model_verdict(wire_model, model_key)
    tokens_block = subagent_token_verdict()

    local: List[dict] = []
    if vercelserver_log.exists():
        try:
            local = parse_vercelserver_billed(
                vercelserver_log.read_text(encoding="utf-8", errors="replace"),
                thread_filter=thread_filter)
        except OSError:
            local = []

    telemetry = {
        "model": model_block,
        "model_local_crosscheck": {
            "source": str(vercelserver_log),
            "billed_lines": local,
            "count": len(local),
            "note": "empty is EXPECTED whenever sub-agents did not route through "
                    "dev :3008; not a failure.",
        },
        "tokens": tokens_block,
    }
    if run_dir is not None:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "subagent_telemetry.json").write_text(
            json.dumps(telemetry, indent=2))
    return telemetry


# ===========================================================================
# Thin integration hook — one call the driver / a scratch run can make.
# ===========================================================================

def capture_all(
    *,
    task_id: str,
    run_dir: Path,
    model_key: Optional[str],
    wire_model: Optional[str],
    ts_start: float,
    ts_end: Optional[float] = None,
    repo: Path = REPO,
    project_rel: str = PROJECT_REL,
    manifest_allow_prefixes=None,
    manifest_deny_prefixes=None,
    ue_root: Optional[Path] = None,
    gw: str = GW,
    aura_uplugin: Optional[Path] = None,
    capture_assets_enabled: bool = True,
    mcp_opener: Optional[Callable[[str, float], bytes]] = None,
    git_runner: Callable = subprocess.run,
    log: Callable[[str], None] = print,
) -> dict:
    """Run every provenance capture for one run and return the merged index.

    Best-effort and import-safe: each sub-capture catches its own errors, so a failed
    editor/socket never aborts the others. Writes the per-artifact JSONs under
    ``run_dir`` plus a ``provenance.json`` index. Designed to be called once at the
    end of a graded/scratch run (after the trace is written, before tree restore).

    ``mcp_opener`` (the 2-arg :41200/api/mcp GET) is the one injectable HTTP seam;
    tests inject it. Nothing here reaches a remote service.
    """
    project = repo / project_rel
    index: Dict[str, dict] = {}

    tools = capture_tool_manifest(gw=gw, run_dir=run_dir, opener=mcp_opener)
    index["tool_manifest"] = {"tool_count": tools.get("tool_count"),
                              "servers": len(tools.get("servers") or [])}
    log(f"  [prov] tool manifest: {tools.get('tool_count')} tools across "
        f"{len(tools.get('servers') or [])} server(s)")

    shots = capture_screenshots(run_dir, ts_start, project_root=project)
    index["screenshots"] = {"count": shots["count"]}
    log(f"  [prov] screenshots: {shots['count']} run-window PNG(s)")

    if capture_assets_enabled:
        try:
            assets = capture_assets(
                run_dir=run_dir, project_root=project,
                manifest_allow_prefixes=manifest_allow_prefixes,
                manifest_deny_prefixes=manifest_deny_prefixes,
                ue_root=ue_root,
            )
            index["assets"] = {"count": assets["count"]}
            log(f"  [prov] assets: {assets['count']} .uasset deliverable(s)")
        except Exception as e:  # noqa: BLE001
            index["assets"] = {"count": 0, "error": f"{type(e).__name__}: {e}"[:160]}
            log(f"  [prov] assets capture error: {e}")

    sub = capture_subagent_telemetry(
        wire_model=wire_model, model_key=model_key, run_dir=run_dir)
    index["subagent_telemetry"] = {
        "model_available": sub["model"]["available"],
        "model": sub["model"].get("model"),
        "tokens_available": sub["tokens"]["available"],
        # Key kept for wire-format stability — downstream consumers still see it.
        # Sub-agent cost is UNAVAILABLE in this release, so it stays null, never 0.0;
        # `tokens_available` is the flag to branch on. Hardcoded None rather than a
        # dig into the verdict: the only thing that ever carried a total here was the
        # removed cloud ledger, and subagent_token_verdict emits no `totals` at all.
        "tokens_usd": None,
        "local_crosscheck_lines": sub["model_local_crosscheck"]["count"],
    }
    log(f"  [prov] sub-agent: model={sub['model'].get('model')} "
        f"(available={sub['model']['available']}), "
        f"tokens available={sub['tokens']['available']}")

    manifest = build_run_manifest(
        task_id=task_id, run_dir=run_dir, model_key=model_key,
        wire_model=wire_model, ts_start=ts_start, ts_end=ts_end,
        repo=repo, project_rel=project_rel,
        exposed_tool_count=tools.get("tool_count"),
        aura_uplugin=aura_uplugin, git_runner=git_runner,
        subagent_model=sub["model"], subagent_token=sub["tokens"],
    )
    index["run_manifest"] = {
        "git_sha": manifest["git_sha"],
        "engine_version": manifest["engine_version"],
        "aura_plugin_version": manifest["aura_plugin_version"],
        "exposed_tool_count": manifest["exposed_tool_count"],
    }

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "provenance.json").write_text(json.dumps(index, indent=2))
    return index
