"""stack — the cross-platform orchestration library for the CraftBench stack.

This module is the *library* half of the launcher; :mod:`aura_rig.cb` is the thin
argparse CLI front-end that sits on top of it. (It was ported from the retired
Windows PowerShell pair — ``stack/cb-common.ps1`` was this library, ``stack/cb.ps1``
the CLI — removed 2026-06-14; the inline ``# ports cb-common.ps1 ...`` comments
record that lineage, the .ps1 files no longer exist.)

It owns the orchestration *machinery* (NOT the agent loop in ``run_graded.py`` —
that is still shelled out to identically):

  - path / harness-python / UE-engine resolution (env + arg overridable, smart
    defaults; uses ``shutil.which`` / ``sys.executable``, never PowerShell);
  - ``load_aura_env`` — read craftbench/.env into os.environ;
  - ``invoke_bringup`` — the idempotent editor gate: one headless UnrealEditor
    on the substrate with Epic's in-engine ``ModelContextProtocol`` server,
    gated on a real MCP ``initialize`` round-trip;
  - the scratch playground lifecycle: ``get_drive_project_dir`` /
    ``initialize_drive_project`` (lean copy + one-time editor build behind a
    ``.cb-built`` marker) / ``reset_drive_project``;
  - teardown ``stop_stack`` (scoped editor reap, then the UE helper images).

WHAT THIS MODULE NO LONGER DOES (open-source release, 2026-08-28). It used to
bring up the private Aura product alongside the editor — a vercel dev server on
:3000, a Playwright dev-browser on :9222, a Next.js client on :3002 that
supervised the editor, that client's ``.env`` / ``.mcp-config.json`` / session
store, and the HTTP probes that drove them (``/api/tool-execute``,
``/api/mcp-tools``, ``/api/headless/*``). None of those components ship in this
repository, so all of that machinery was removed rather than stubbed; the
``aura-mcp`` arm is disclosed but not reproducible here. See THIRD-PARTY.md §4,
and the ``invoke_bringup`` / ``ensure_drive_editor`` docstrings for the
stage-by-stage record of what went and why.

Cross-platform notes (the genuinely Windows-only bits of the original):
  * Detached long-running servers use ``subprocess.Popen`` with
    ``DETACHED_PROCESS | CREATE_NO_WINDOW`` (Windows) or ``start_new_session``
    (POSIX), stdout/stderr -> a log file, so they SURVIVE this process.
  * Port-owner kills use ``psutil`` when available, else ``lsof``/``fuser``
    (POSIX) or ``Get-NetTCPConnection`` shelled out (Windows fallback).
  * Image-name kills map to ``taskkill /F /IM`` (Windows) vs ``pkill -f`` (POSIX);
    LiveCodingConsole / CrashReportClient are Windows-only (harmless no-op else).
  * The editor target build uses ``Build.bat`` (Windows) / ``Build.sh`` (Mac,Linux)
    with the platform token swapped (Win64 -> Mac / Linux).
  * ``robocopy /E`` (copy, no-delete) and ``/MIR`` (mirror, delete extras) become
    a recursive copy and a true mirror; their non-Unix exit semantics
    (0-7 == success) are irrelevant here.
  * PortablePython lives under a per-OS subdir (Windows/Mac/Linux).

The hard invariant of the original is preserved: nothing here drives the agent
or spends tokens; the only token-spending step is the shelled-out
``run_graded.py`` (which this module does NOT call — the CLI front-end does).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from . import kill_guard  # the refusal layer in front of every REAL kill
from . import paths as cb_paths  # the ONE machine-dir resolver (CB_ROOT)

IS_WINDOWS = os.name == "nt"


# =========================================================================== #
# 1. Resolution — repo roots, derived dirs, harness python, UE engine.        #
#    (ports the top-of-file block + Resolve-HarnessPy + Resolve-UE)           #
# =========================================================================== #

def _resolve_path(p: Path) -> Path:
    """Canonicalize like PowerShell Resolve-Path, but tolerate a missing path
    (Resolve-Path throws; we keep the un-resolved absolute path instead)."""
    try:
        return p.resolve()
    except OSError:
        return p.absolute()


class StackPaths:
    """All the repo / stack paths cb-common.ps1 derives on dot-source.

    Eager (computed at construction) because cb.ps1 reads them immediately after
    sourcing. ``uproject`` is intentionally re-pointable at runtime (the headless
    command sets CB_UPROJECT to the scratch) — read ``env CB_UPROJECT`` live via
    the :pyattr:`uproject` property rather than freezing it.
    """

    def __init__(self, craftbench: Optional[Path] = None, genius: Optional[Path] = None):
        # CRAFTBENCH (repo root): env -> auto-derive 3 levels up from this file's
        # sibling stack/ dir (== repo root) -> caller override.
        if craftbench is not None:
            self.craftbench = _resolve_path(Path(craftbench))
        elif os.environ.get("CB_CRAFTBENCH"):
            self.craftbench = Path(os.environ["CB_CRAFTBENCH"])  # verbatim, no existence check
        else:
            # this file is tools/run-agent/aura_rig/stack.py -> parents[3] == repo root.
            self.craftbench = _resolve_path(Path(__file__).resolve().parents[3])

        # The benchmark substrate (graded-only). Computed BEFORE genius because the
        # aura-plugin clone now lives INSIDE it (<substrate>/Plugins/), so genius
        # derives from template_dir.
        self.template_dir = self.craftbench / "UE-projects" / "CraftBenchTemplate"

        # GENIUS (aura-plugin repo): env -> craftbench/.env CB_GENIUS -> the host-local
        # clone inside the substrate's Plugins/ folder. The 2026-07 refactor clones
        # aura-plugin DIRECTLY into <substrate>/Plugins/ (real dirs — no sibling, no
        # junction), so Plugins/{Aura,Ramen,.claude} are the genius subtrees. The .env
        # peek happens HERE (not in load_aura_env) because paths are constructed before
        # the env loader runs. Real env still wins.
        if genius is not None:
            self.genius = Path(genius)
        elif os.environ.get("CB_GENIUS"):
            self.genius = Path(os.environ["CB_GENIUS"])  # verbatim
        else:
            dotenv_genius = None
            cbenv = self.craftbench / ".env"
            if cbenv.exists():
                try:
                    dotenv_genius = _env_val(
                        cbenv.read_text(encoding="utf-8", errors="replace"), "CB_GENIUS")
                except OSError:
                    pass
            if dotenv_genius:
                self.genius = Path(dotenv_genius)  # verbatim, like the env var
            else:
                emb = self.template_dir / "Plugins"
                self.genius = _resolve_path(emb) if emb.exists() else emb  # keep bare path if missing

        # Derived-from-GENIUS dirs (no override).
        self.vercel_dir = self.genius / "Ramen" / "vercelServer"
        self.client_dir = self.genius / "Ramen" / "mcp-client-chatbot"
        self.devbrowser = self.genius / ".claude" / "skills" / "dev-browser"

        self.mcp_cfg = self.client_dir / ".mcp-config.json"

        # %TEMP% on Windows; $TMPDIR / /tmp on POSIX. All stack logs + the
        # editor-project marker live here.
        self.log = Path(os.environ.get("TEMP") or tempfile.gettempdir())
        self.editor_marker = self.log / "cb_editor_uproject.txt"

        # Aura's bundled PortablePython that runs the editor MCP stdio servers
        # (NOT the harness python). Per-OS subdir. Derived from GENIUS — on the
        # The clone-into-Plugins layout genius == <substrate>/Plugins so the
        # path is unchanged; on a CB_GENIUS box the old hardcoded
        # <substrate>/Plugins form pointed at a dir that may not exist at all
        # (2026-07-21: the FF deleted it, and the client's MCP stdio servers
        # silently failed to spawn -> mcp-tools catalog {}).
        self.portable_py = (
            self.genius / "Aura" / "PortablePython"
            / _portable_py_subdir() / _portable_py_exe()
        )

    @property
    def uproject(self) -> Path:
        """Which .uproject the headless editor opens. Re-pointable at runtime via
        CB_UPROJECT (the headless command sets it to the scratch)."""
        env = os.environ.get("CB_UPROJECT")
        if env:
            return Path(env)
        return self.template_dir / "CraftBenchTemplate.uproject"

    @property
    def runagent(self) -> Path:
        return self.craftbench / "tools" / "run-agent"


def _portable_py_subdir() -> str:
    if IS_WINDOWS:
        return "Windows"
    if sys.platform == "darwin":
        return "Mac"
    return "Linux"


def _portable_py_exe() -> str:
    return "python.exe" if IS_WINDOWS else "python"


# --- harness python (ports Resolve-HarnessPy) ------------------------------- #

def _py_candidate_works(exe: str, pre: Sequence[str]) -> bool:
    """Run ``<exe> <pre...> --version`` swallowing all output; True iff exit 0."""
    located = shutil.which(exe)
    if located is None:
        return False
    try:
        cp = subprocess.run(
            [located, *pre, "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        return cp.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def resolve_harness_py() -> Optional[Tuple[str, List[str]]]:
    """Pick the harness Python launcher as ``(exe, pre_args)``, or None.

    Candidate order (first whose ``--version`` exits 0 wins):
      1. ``$CB_PY`` whitespace-split (a full path, or a launcher line 'py -3.12')
      2. ('py', ['-3.12'])  3. ('py', ['-3'])  4. ('python', [])
      5. ('python3', [])    6. ('py', [])

    ``pre_args`` is ALWAYS a list (the original's @() force-wrap gotcha vanishes
    in Python — but the caller MUST splat it as separate argv elements, never a
    joined string). On POSIX 'py' simply isn't on PATH so the cascade falls
    through to python3/python naturally.
    """
    cands: List[Tuple[str, List[str]]] = []
    cb_py = os.environ.get("CB_PY")
    if cb_py:
        parts = [p for p in cb_py.split() if p]
        if parts:
            cands.append((parts[0], parts[1:]))
    cands += [
        ("py", ["-3.12"]),
        ("py", ["-3"]),
        ("python", []),
        ("python3", []),
        ("py", []),
    ]
    for exe, pre in cands:
        if _py_candidate_works(exe, pre):
            located = shutil.which(exe) or exe
            return located, list(pre)
    return None


# --- UE engine (ports Resolve-UE, INCLUDING the CB_UE_ROOT export side effect) #

def _ue_editor_subpath() -> Path:
    if IS_WINDOWS:
        return Path("Engine") / "Binaries" / "Win64" / "UnrealEditor.exe"
    if sys.platform == "darwin":
        return Path("Engine") / "Binaries" / "Mac" / "UnrealEditor.app" / "Contents" / "MacOS" / "UnrealEditor"
    return Path("Engine") / "Binaries" / "Linux" / "UnrealEditor"


def _ue_search_roots() -> List[Path]:
    """Ordered candidate UE roots. CB_UE_ROOT (env, then craftbench/.env) first,
    then the canonical 5.8 install, then any discovered UE_5.* (newest-name-first)."""
    roots: List[Path] = []
    env_root = os.environ.get("CB_UE_ROOT")
    if not env_root:
        # env -> craftbench/.env fallback, same pattern as StackPaths' CB_GENIUS
        # peek: parsed here because resolve_ue can run before load_aura_env, and
        # load_aura_env's whitelist never exports CB_UE_ROOT anyway.
        cb_root = Path(os.environ.get("CB_CRAFTBENCH")
                       or Path(__file__).resolve().parents[3])
        cbenv = cb_root / ".env"
        if cbenv.exists():
            try:
                env_root = _env_val(
                    cbenv.read_text(encoding="utf-8", errors="replace"), "CB_UE_ROOT")
            except OSError:
                pass
    if env_root:
        roots.append(Path(env_root))

    if IS_WINDOWS:
        epic = Path(r"C:\Program Files\Epic Games")
        roots.append(epic / "UE_5.8")
    elif sys.platform == "darwin":
        epic = Path("/Users/Shared/Epic Games")
        roots.append(epic / "UE_5.8")
    else:
        epic = Path("/opt/unreal-engine")  # common Linux layout
        roots.append(Path("/Users/Shared/Epic Games") / "UE_5.8")  # parity placeholder

    # Discovery: any UE_5.* under the Epic base, newest NAME first (preserves the
    # original's lexical-descending quirk; the explicit UE_5.8 above usually wins).
    try:
        if epic.exists():
            discovered = sorted(
                (d for d in epic.iterdir() if d.is_dir() and d.name.startswith("UE_5.")),
                key=lambda d: d.name,
                reverse=True,
            )
            roots.extend(discovered)
    except OSError:
        pass
    return roots


def resolve_ue() -> Optional[Path]:
    """Return the UnrealEditor binary path or None. SIDE EFFECT: on success
    exports ``CB_UE_ROOT`` to the winning root so the downstream Python grade
    (driver.DEFAULT_UE_ROOT) reuses the SAME engine — the original relies on this."""
    sub = _ue_editor_subpath()
    for root in _ue_search_roots():
        exe = root / sub
        if exe.exists():
            os.environ["CB_UE_ROOT"] = str(root)  # load-bearing side effect
            return exe
    return None


# =========================================================================== #
# 2. load_aura_env — craftbench/.env -> os.environ                             #
#    (ports Import-AuraEnv; best-effort, never raises, a missing file skipped) #
# =========================================================================== #

def _dotenv_value(raw: str) -> str:
    """Dotenv semantics for the text after ``KEY=``: a double-quoted value ends
    at its closing quote (a ``#`` INSIDE the quotes is part of the value); an
    unquoted value ends at the first whitespace-then-``#`` (inline comment).
    ``SOME_SECRET="secret" # note`` must yield ``secret``, not
    ``secret" # note`` — that exact line cost a Supabase invalid-credentials
    wall (FAILURE-LOG 2026-07-24; same .env inline-comment class as the L1 cap)."""
    v = raw.strip()
    if v.startswith('"'):
        end = v.find('"', 1)
        if end != -1:
            return v[1:end]
        return v.strip('"')  # unterminated quote: legacy behavior
    return re.split(r"\s#", v, maxsplit=1)[0].strip()


def _env_val(text: str, key: str) -> Optional[str]:
    """First ``KEY=value`` line, parsed with :func:`_dotenv_value`."""
    prefix = key + "="
    for line in text.splitlines():
        if line.startswith(prefix):
            v = _dotenv_value(line[len(prefix):])
            return v or None
    return None


def env_flag(name: str) -> bool:
    """True iff the env var is set to a truthy value (1/true/yes)."""
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


_PLACEHOLDER_MARKERS = (
    "xxxx",                  # sk-ant-xxxx… / sk-or-xxxx…
    "you@example.com",
    "your-",                 # your-aura-password / your-vercel-token
    "changeme",
)


def _is_placeholder(value: str) -> bool:
    """True iff ``value`` is still an unfilled `.env.example` placeholder.

    Deliberately a SUBSTRING match on a short, boring marker list rather than a
    regex per key: the failure it prevents (exporting `sk-ant-xxxx` over a real
    key) is silent and confusing, while a false positive is loud and obvious —
    the operator sees the var as unset and fixes their `.env`. Real secrets do
    not contain "xxxx" or "your-".
    """
    low = value.strip().lower()
    return any(m in low for m in _PLACEHOLDER_MARKERS)


def load_aura_env(paths: StackPaths) -> None:
    """Load model keys + build/disk tuning from craftbench/.env into os.environ:
      ANTHROPIC_API_KEY/OPENROUTER_API_KEY/OPENROUTER_BASE_URL/CB_BARE_BASE_URL passthrough,
      CRAFTBENCH_L1_MAX_PARALLEL/CRAFTBENCH_ALLOW_UBA passthrough (UE 5.8 build tuning),
      CB_WORKDIR_RETENTION/CB_WARM_CACHE_DIR passthrough (disk, warm pool),
      CB_GENIUS/CB_AURA_SKILLS/CB_ISOLATE_AURA_SESSION passthrough (rig layout).
    Only non-empty values are exported; an absent file is skipped.

    It also used to read a SECOND file — the private vercel server's ``.env`` —
    renaming ``NEXT_PUBLIC_SUPABASE_URL``/``_ANON_KEY`` to CB_SUPABASE_URL /
    CB_SUPABASE_ANON, and to export the ``AURA_USERNAME``/``AURA_PASSWORD``
    pair. All four fed the Aura product login and its Supabase-backed
    entitlement check, both of which are out of this release (THIRD-PARTY.md
    §4), and nothing in this repository reads them any more. The generic
    loading below is untouched.

    PRECEDENCE: an already-set, non-blank environment variable WINS over `.env`,
    matching `tools/verify-single/repo_env.load_repo_env`. Any `.env` entry
    overridden that way is announced on stdout rather than resolved silently —
    the failure this prevents is a build tuned one way and grading another, and
    the operator has no other way to see which value won.
    """
    _skipped: list[str] = []
    cbenv = paths.craftbench / ".env"
    if cbenv.exists():
        try:
            text = cbenv.read_text(encoding="utf-8", errors="replace")
            for src, dst in (
                ("ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
                ("OPENROUTER_API_KEY", "OPENROUTER_API_KEY"),
                ("OPENROUTER_BASE_URL", "OPENROUTER_BASE_URL"),
                # The `bare` arm's endpoint override. Same silent-no-op class as
                # CB_WORKDIR_RETENTION below: this loader is a WHITELIST, so
                # without this line an operator pointing `bare` at a non-OpenRouter
                # OpenAI-compatible endpoint via `.env` gets no error and is
                # silently still talking to OpenRouter — i.e. the run would be
                # attributed to the wrong provider. (OPENROUTER_API_KEY above is
                # what `bare` reads for auth, so that half already worked.)
                ("CB_BARE_BASE_URL", "CB_BARE_BASE_URL"),
                # Build tuning, propagated to the verifier subprocess (UE 5.8):
                ("CRAFTBENCH_L1_MAX_PARALLEL", "CRAFTBENCH_L1_MAX_PARALLEL"),
                ("CRAFTBENCH_ALLOW_UBA", "CRAFTBENCH_ALLOW_UBA"),
                # Disk tuning, same class as the two above — and the ONLY way to
                # opt out of slim retention, since there is no CLI flag for it.
                # Without this line a `.env` entry is a SILENT no-op: the loader
                # is a whitelist, so the operator sets CB_WORKDIR_RETENTION=full,
                # gets no error, and still finds a ~42 MB slimmed workdir when
                # they go to debug the build they meant to keep.
                ("CB_WORKDIR_RETENTION", "CB_WORKDIR_RETENTION"),
                # Warm-pool root, same class again — and `cb warm-prime` tells
                # the operator to set it in `.env` to get MAX_PATH headroom the
                # default LOCALAPPDATA root does not have.
                ("CB_WARM_CACHE_DIR", "CB_WARM_CACHE_DIR"),
                # Rig layout (the junction+CB_GENIUS box): without these a
                # fresh process resolves skills/genius from the substrate's
                # Plugins/ dir only — the .env mitigation must survive into
                # os.environ (2026-07-21 dev-browser login WinError-267).
                ("CB_GENIUS", "CB_GENIUS"),
                ("CB_AURA_SKILLS", "CB_AURA_SKILLS"),
                # Session-isolation opt-out must survive into os.environ so a
                # Mac operator can set it in .env: on Mac the editor's
                # aura_server resolves .Aura to ~/Library/Application Support
                # (HOME-derived, ignores the scoped LOCALAPPDATA), so the
                # isolated worktree/.Aura session never reaches the editor and
                # it boots "not signed in" -> the tool queue is never drained
                # (2026-07-22 Mac bring-up: zero tool calls / empty scene).
                ("CB_ISOLATE_AURA_SESSION", "CB_ISOLATE_AURA_SESSION"),
                # :8000 is one of the most-collided dev ports, and this is
                # the ONLY documented way off it. Without the passthrough,
                # setting it in .env did nothing: resolve_url() fell back to
                # DEFAULT_URL, editor_launch_args saw the default port and
                # omitted -ModelContextProtocolPort, and the editor retried
                # the same busy port with no error shown.
                ("CB_UNREAL_MCP_URL", "CB_UNREAL_MCP_URL"),
            ):
                val = _env_val(text, src)
                # Never export a value that is still the shipped .env.example
                # placeholder. `cb bootstrap` copies .env.example verbatim, and
                # until 2026-07-26 three secrets were UNCOMMENTED there — so a
                # fresh box exported ANTHROPIC_API_KEY=sk-ant-xxxx OVER a real
                # key the operator already had in their environment, and the
                # resulting auth failure gave no hint (the var *is* set, just to
                # nonsense). .env.example is now fully commented, but existing
                # .env files on disk still carry the placeholders, so the guard
                # protects those too.
                if not val or _is_placeholder(val):
                    continue
                # EXPLICIT ENV WINS. This loader used to assign unconditionally
                # while its sibling `repo_env.load_repo_env` (the raw run_task.py
                # path) skipped already-set vars with "explicit env wins" — so the
                # SAME variable resolved differently depending on whether you went
                # through `cb`. Concretely: `export CRAFTBENCH_L1_MAX_PARALLEL=4 &&
                # cb eval` with `.env` saying 2 silently built at 2, and the repo conventions
                # claimed the opposite. The two loaders now agree (2026-07-26).
                if (os.environ.get(dst) or "").strip():
                    if os.environ[dst] != val:
                        _skipped.append(dst)
                    continue
                os.environ[dst] = val
        except OSError:
            pass

    # (A second block read the private vercel server's `.env` here and renamed
    # its two Supabase keys into CB_SUPABASE_URL / CB_SUPABASE_ANON. That file
    # belongs to a component this release does not ship and nothing left in the
    # repository reads either variable, so the block went with it — 2026-08-28.)

    if _skipped:
        # Announced, not silent: a surprising resolution the operator cannot
        # otherwise observe is exactly how the 5x-verify and cap-mismatch
        # incidents stayed invisible for so long.
        print(f"[env] .env NOT applied (an explicit environment value wins): "
              f"{', '.join(sorted(set(_skipped)))}", flush=True)


# =========================================================================== #
# 3. HTTP probes + process / port helpers (cross-platform).                    #
# =========================================================================== #

def test_up(port: int, timeout: float = 3.0) -> bool:
    """True if something HTTP-answers on 127.0.0.1:<port>. Like Test-Up, ANY HTTP
    response (incl. 4xx/5xx) counts as up; only a connect/transport failure is
    'down'."""
    url = f"http://127.0.0.1:{port}/"
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, socket.timeout, OSError, ValueError):
        return False


# (`gate_up` — test_up with four retries — lived here. It existed for ONE
# reason: the private Next.js dev servers on :3000/:3002 stalled 10-30 s on an
# on-demand route compile, so the bring-up's one-shot final probe read a
# healthy server as down and killed ~100% of first attempts post-rebase
# (FAILURE-LOG 2026-07-10/11). Those servers are not part of this release and
# the editor gate is a real MCP round-trip rather than a port probe, so the
# retry wrapper went with them — 2026-08-28.)


def wait_up(port: int, timeout_sec: int, interval: int = 5) -> bool:
    """Poll test_up every <interval>s until <timeout_sec> elapses."""
    end = time.time() + timeout_sec
    while time.time() < end:
        if test_up(port):
            return True
        time.sleep(interval)
    return test_up(port)


def _detached_kwargs(log_path: Path):
    """Popen kwargs that detach the child so it survives this process, with all
    output redirected to <log_path>. Windows: CREATE_NEW_PROCESS_GROUP|
    CREATE_NO_WINDOW; POSIX: start_new_session (own session, immune to our
    SIGHUP).

    DETACHED_PROCESS WAS HERE AND SILENTLY DESTROYED EVERY SERVICE LOG
    (root-caused 2026-08-07, replacing a two-week-old WRONG diagnosis).
    ``start_detached`` routes npx/pnpm/yarn/npm through ``cmd /c`` (those shims
    are batch files CreateProcess cannot launch directly) — i.e. EVERY stack
    service. DETACHED_PROCESS gives the child NO console, so ``cmd.exe``
    re-initializes its own std handles and the inherited redirection is lost:
    the log file stays at 0 bytes forever, whatever the service prints.

    That is why `cb_client.log` / `cb_devbrowser.log` were 0 bytes and
    `cb_vercel.log` 4 bytes on both boxes, why the 2026-08-07 client death that
    cost a paid turn was UNDIAGNOSABLE, and why the codebase carried the
    plausible-but-false
    "node block-buffers stdout to a file" story. Measured, same box, same
    ``cmd /c node`` child, hard-killed after 2 s:

        DETACHED|NO_WINDOW (was)   survives parent exit: True   log   0 bytes
        NO_WINDOW only             survives parent exit: True   log  47 bytes
        NEW_GROUP|NO_WINDOW        survives parent exit: True   log  47 bytes

    A DIRECT node child logged fine under every combo — node writes to a file
    synchronously on Windows, so the buffering story was never the mechanism.

    Survival, the property DETACHED_PROCESS was there for, does NOT depend on
    it: on Windows a child outlives its parent unless it is in a Job object.
    CREATE_NO_WINDOW still gives the child its own (hidden) console rather than
    the parent's, and CREATE_NEW_PROCESS_GROUP keeps a Ctrl+C aimed at our
    group off it — the two properties DETACHED_PROCESS actually provided here,
    minus the handle destruction."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(log_path, "ab", buffering=0)
    kwargs = dict(stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    if IS_WINDOWS:
        flags = 0
        flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        kwargs["creationflags"] = flags
    else:
        kwargs["start_new_session"] = True
    return kwargs, fh


def start_detached(argv: Sequence[str], cwd: Path, log_path: Path,
                   extra_env: Optional[Dict[str, str]] = None) -> Optional[subprocess.Popen]:
    """Launch a long-running server detached + hidden, surviving this process,
    all output -> <log_path>. ``argv`` is a real argv list (no shell). On Windows,
    node tool shims (npx/pnpm/yarn) are .cmd batch files CreateProcess can't launch
    directly, so they're routed through ``cmd /c``.

    Log note: the old "node block-buffers stdout to a file" caveat here was a
    WRONG diagnosis, corrected 2026-08-07 — see :func:`_detached_kwargs`. The
    real cause of the perpetually-empty ``cb_*.log`` files was
    DETACHED_PROCESS destroying ``cmd /c``'s inherited handles, and it is
    fixed. Service logs now carry real output; an EMPTY log is once again
    evidence (the service printed nothing), not an artifact. Port/process
    probes remain the authoritative liveness check."""
    cmd = list(argv)
    if IS_WINDOWS and cmd and Path(cmd[0]).stem in ("npx", "pnpm", "yarn", "npm"):
        cmd = ["cmd", "/c", *cmd]
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    kwargs, fh = _detached_kwargs(log_path)
    proc = None
    try:
        proc = subprocess.Popen(cmd, cwd=str(cwd), env=env, **kwargs)
    except OSError as e:
        try:
            fh.write(f"[stack] failed to launch {cmd!r}: {e}\n".encode("utf-8"))
        except Exception:
            pass
    finally:
        # The detached child inherited its OWN copy of the fd, so close the
        # parent's handle in BOTH paths. Without this, every launch (each
        # per-drive editor restart's fallback + each client/vercel relaunch)
        # orphaned a file handle for the harness's lifetime — a slow-drip
        # resource leak over a long bench (FAILURE-LOG 2026-07-13).
        try:
            fh.close()
        except Exception:
            pass
    return proc


def editor_boot_timeout(uproject: Path) -> int:
    """Seconds to allow for the editor to bind :30010 / become tool-ready,
    scaled to DerivedDataCache warmth. A FIRST-ever UE 5.8 boot with a cold DDC
    compiles global shaders + builds asset DDC and routinely takes 10-30 min on
    a modest box; the default 240/480s windows time out on a HEALTHY editor
    mid-compile, and the retry then kills the still-compiling process — churning
    forever (FAILURE-LOG 2026-07-24). Warm DDC → 480s (unchanged); cold → 1800s.

    Warmth = a non-trivial engine-wide Common DDC (the shared shader cache) OR a
    project-local DDC. Env override: ``CB_EDITOR_BOOT_TIMEOUT`` (leading int)."""
    raw = os.environ.get("CB_EDITOR_BOOT_TIMEOUT", "")
    m = re.match(r"\s*([0-9]+)", raw)
    if m:
        n = int(m.group(1))
        if n > 0:
            return n
    candidates = []
    la = os.environ.get("LOCALAPPDATA")
    if la:
        candidates.append(Path(la) / "UnrealEngine" / "Common" / "DerivedDataCache")
    ue_root = os.environ.get("CB_UE_ROOT")
    if ue_root:
        candidates.append(Path(ue_root) / "Engine" / "DerivedDataCache")
    try:
        candidates.append(Path(uproject).parent / "DerivedDataCache")
    except (OSError, ValueError):
        pass
    for ddc in candidates:
        try:
            # "warm" = the cache dir exists and holds SOMETHING (any child entry);
            # an empty freshly-created dir does not count. Cheap top-level probe —
            # never walk a multi-GB DDC.
            if ddc.is_dir() and next(ddc.iterdir(), None) is not None:
                return 480
        except OSError:
            continue
    return 1800


def kill_port_owner(port: int) -> None:
    """Kill the process LISTENING on <port> (established connections ignored).
    psutil -> lsof/fuser (POSIX) -> Get-NetTCPConnection (Windows). All swallowed."""
    pids = _listening_pids(port)
    for pid in pids:
        _kill_pid(pid, f"kill_port_owner({port})")


def _listening_pids(port: int) -> List[int]:
    # Preferred: psutil (cross-platform, no shell).
    try:
        import psutil  # type: ignore
        pids = set()
        for c in psutil.net_connections(kind="tcp"):
            if c.status == psutil.CONN_LISTEN and c.laddr and c.laddr.port == port and c.pid:
                pids.add(c.pid)
        return list(pids)
    except Exception:
        pass

    if IS_WINDOWS:
        # netstat -ano | findstr LISTENING :<port>  -> last column is the PID.
        try:
            # errors="replace": netstat's banner is OEM-codepage on zh-CN
            # Windows and text=True's strict utf-8 decode dies on it, leaving
            # stdout None (the same signature as the tasklist probe,
            # FAILURE-LOG 2026-07-24) — the numeric columns we parse are ASCII
            # either way.
            out = subprocess.run(
                ["netstat", "-ano", "-p", "tcp"],
                capture_output=True, text=True, timeout=15,
                encoding="utf-8", errors="replace",
            ).stdout
            pids = set()
            for line in (out or "").splitlines():
                # cols: proto  local_addr  remote_addr  state  pid
                cols = line.split()
                if len(cols) >= 5 and cols[3] == "LISTENING":
                    # EXACT port match on the local address (substring `:3000` would
                    # otherwise also match :30005 etc. and kill adjacent listeners).
                    if cols[1].rsplit(":", 1)[-1] == str(port) and cols[-1].isdigit():
                        pids.add(int(cols[-1]))
            return list(pids)
        except (OSError, subprocess.SubprocessError):
            return []

    # POSIX: lsof, then fuser.
    try:
        out = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
            capture_output=True, text=True, timeout=15,
        ).stdout
        return [int(x) for x in out.split() if x.strip().isdigit()]
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        out = subprocess.run(
            ["fuser", f"{port}/tcp"], capture_output=True, text=True, timeout=15,
        ).stdout
        return [int(x) for x in out.split() if x.strip().isdigit()]
    except (OSError, subprocess.SubprocessError):
        return []


def audit_kill(target: str, reason: str = "") -> None:
    """Append ONE flushed line recording a process this rig is about to kill.

    WHY THIS EXISTS. On 2026-08-03 a graded rep lost 6m42s of its ceiling because
    the headless editor vanished mid-drive. Every objective source came back
    empty — no UE ``Fatal``/callstack, no ``LogExit``, zero Windows Application or
    System events, no WER report — which leaves "terminated by another process"
    as the only explanation ``TerminateProcess`` is consistent with. But the rig
    could not even rule ITSELF out: every kill path here swallowed its result and
    logged nothing, so "CraftBench killed it" and "something else killed it" were
    indistinguishable after the fact.

    Written straight to ``runs/.kill-audit.log`` with a flush per line, on
    purpose: the stack servers' own logs are block-buffered by node and are lost
    entirely when a process is hard-killed (see ``start_detached``'s log caveat),
    which is exactly the case this record has to survive. Never raises — an
    audit line must not be able to break a teardown.

    The line carries the acting process's ROLE (``cb`` / ``janitor`` / ``test``
    / ``other``, :func:`aura_rig.kill_guard.acting_role`). On 2026-08-07 the
    absence of that one field cost hours: the log proved SOMETHING wrote mock
    pids and real image kills from the same pid, but not that the writer was a
    unittest process — which was the whole diagnosis.
    """
    try:
        import datetime as _dt
        import inspect
        caller = "?"
        for fr in inspect.stack()[1:5]:
            if fr.function not in ("audit_kill", "_kill_pid", "_kill_permitted"):
                caller = f"{fr.function}:{fr.lineno}"
                break
        line = (f"{_dt.datetime.now().isoformat(timespec='milliseconds')}\t"
                f"pid={os.getpid()}\trole={kill_guard.acting_role()}\t"
                f"{target}\treason={reason or '?'}\tcaller={caller}\n")
        path = _KILL_AUDIT_PATH()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
    except Exception:  # noqa: BLE001 — auditing must never break a teardown
        pass


def _KILL_AUDIT_PATH() -> Path:
    # this file is tools/run-agent/aura_rig/stack.py -> parents[3] == repo root,
    # the same derivation _Paths uses at :113-114.
    return Path(__file__).resolve().parents[3] / "runs" / ".kill-audit.log"


# --------------------------------------------------------------------------- #
# THE KILL GATE (incident 2026-08-07 — see aura_rig/kill_guard.py).             #
#                                                                              #
# A unit-test run reached these primitives and taskkill'd a LIVE drive editor  #
# plus the :3000/:3002/:9222 owners. Every real kill in this module now passes  #
# through `_kill_permitted` (or `_run_kill_cmd`, which calls it), and a refusal #
# is written to runs/.kill-audit.log with `reason=REFUSED(...)`.               #
#                                                                              #
# WHERE THE SEAM SITS, AND WHY THE EXISTING TESTS STILL PASS. The refusal is at #
# the OUTERMOST REAL-EFFECT boundary — the point where a command would actually #
# reach the OS — never in the scoping/decision logic the tests exercise. The    #
# existing kill tests (test_cb_stack.TestEditorScoping, test_stack_reap,        #
# TestScopedClientKill) SUBSTITUTE that boundary: they assign `stack.subprocess #
# .run = fake_run`, which mutates the shared `subprocess` module. So            #
# `_effect_is_real()` compares the current `subprocess.run` against the genuine #
# function captured at IMPORT time (before any double can exist): a substituted #
# boundary performs no real effect, so there is nothing to refuse and those     #
# assertions keep holding verbatim. A path that has NOT been doubled — exactly  #
# the incident's path — sees the real function and is refused.                  #
#                                                                              #
# The primitives with no test double at all (`_kill_pid`, `kill_by_image`,      #
# `stop_stack`) are gated UNCONDITIONALLY at entry:                             #
# nothing may reach the OS through them from a test process, ever.              #
# --------------------------------------------------------------------------- #

#: The genuine OS-effect callables, captured at import BEFORE any test double
#: can replace them. Identity against these is how the gate answers "would this
#: call actually reach the operating system?"
_REAL_SUBPROCESS_RUN = subprocess.run
#: Kept for reference/diagnosis only — do NOT add it to `_effect_is_real()`.
#: A doubled `os.kill` must never be able to move that answer away from
#: REFUSE (see the docstring below). `os.kill`'s only use is in `_kill_pid`,
#: which is gated unconditionally and so needs no identity check.
_REAL_OS_KILL = os.kill


def _effect_is_real() -> bool:
    """True when the SHELLED kill boundary has NOT been substituted by a test
    double — i.e. a command issued now would really reach the OS.

    Deliberately tests ONLY ``subprocess.run``, because that is the only
    boundary its single caller :func:`_run_kill_cmd` uses. ANDing ``os.kill``
    in here was a hole, not extra safety: a test that doubles ``os.kill`` alone
    (leaving ``subprocess.run`` genuine) would make this return False, skip the
    gate, and shell a REAL ``taskkill`` — measured 2026-08-07, it killed a live
    probe process from inside a ``-m unittest`` run. ``os.kill`` needs no term
    here at all: its only use is inside :func:`_kill_pid`, which is gated
    UNCONDITIONALLY. Every predicate in this gate must be one where a test
    double moves the answer toward REFUSE, never away from it."""
    return subprocess.run is _REAL_SUBPROCESS_RUN


def _kill_permitted(target: str, reason: str = "") -> bool:
    """The gate. False -> the caller MUST NOT kill (the refusal is audited).

    Two refusals, both documented in :mod:`aura_rig.kill_guard`: a test-runner
    process (override ``CB_ALLOW_REAL_KILLS=1``) and a live foreign stack owner
    (override ``CB_ALLOW_STACK_TAKEOVER=1``). Never raises — and when it cannot
    tell, it refuses: a missed kill costs a ~1 min re-bring-up, a murdered live
    run costs a graded rep and lands as a machine-fault verdict."""
    try:
        refusal = kill_guard.refusal(target, reason)
    except Exception:  # noqa: BLE001 — an unusable gate is not a licence to kill
        refusal = "REFUSED(guard-error)"
    if refusal is None:
        return True
    audit_kill(f"{target} intent={reason or '?'}", refusal)
    return False


def _run_kill_cmd(cmd: "Sequence[str]", *, target: str, reason: str,
                  timeout: int = 20) -> bool:
    """Shell ONE kill command through the gate. Returns True iff it ran.

    Gated only when the boundary is real (see the block comment above), so the
    scoping tests that substitute ``subprocess.run`` keep asserting on exactly
    the argv this rig would have issued."""
    if _effect_is_real() and not _kill_permitted(target, reason):
        return False
    try:
        cp = subprocess.run(list(cmd), capture_output=True, timeout=timeout)
        # SPAWN-POISONING FALLBACK (2026-08-07 finding 3): under a
        # 0xC0000142 storm the kill COMMAND itself dies at DLL init — the rig
        # cannot kill anything precisely when it most needs to (a 21.8 GB
        # zombie editor survived force-kill and held the scratch). When the
        # shelled kill was the thing that died (exit 0xC0000142), fall back to
        # the in-process ctypes tree-kill for a /PID-shaped argv. Only past
        # the SAME gate above — the fallback inherits this call's clearance,
        # it never widens it.
        if _effect_is_real() and cp.returncode == 3221225794:
            pid = _pid_from_kill_argv(cmd)
            if pid is not None:
                audit_kill(f"pid={pid}", f"{reason} [0xC0000142 fallback]")
                try:
                    from . import pressure
                    n = pressure.terminate_tree_in_process(pid)
                    return n > 0
                except Exception:  # noqa: BLE001 — fallback must not raise
                    return False
        return True
    except (OSError, subprocess.SubprocessError):
        # The spawn itself failed (poisoning can also present as an OSError
        # before any exit code exists) — same in-process fallback.
        if _effect_is_real():
            pid = _pid_from_kill_argv(cmd)
            if pid is not None:
                audit_kill(f"pid={pid}", f"{reason} [spawn-failed fallback]")
                try:
                    from . import pressure
                    return pressure.terminate_tree_in_process(pid) > 0
                except Exception:  # noqa: BLE001
                    return False
        return False


def _pid_from_kill_argv(cmd) -> "Optional[int]":
    """The /PID argument of a taskkill-shaped argv, or None. Image-name kills
    (/IM) have no single pid to fall back on and stay shell-only — enumerating
    by name and killing the matches would WIDEN the audited scope of the
    original command, which the fallback must never do."""
    try:
        toks = [str(t) for t in cmd]
        for j, t in enumerate(toks):
            if t.upper() == "/PID" and j + 1 < len(toks):
                return int(toks[j + 1])
    except (ValueError, TypeError):
        pass
    return None


def _kill_pid(pid: int, reason: str = "") -> None:
    if not _kill_permitted(f"pid={pid}", reason):
        return
    audit_kill(f"pid={pid}", reason)
    try:
        import psutil  # type: ignore
        psutil.Process(pid).kill()
        return
    except Exception:
        pass
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                           capture_output=True, timeout=15)
        else:
            os.kill(pid, 9)
    except (OSError, subprocess.SubprocessError):
        pass


def count_image(name: str) -> int:
    """Count running processes whose image/name matches <name> (e.g.
    'LiveCodingConsole'). psutil -> tasklist (Windows) / pgrep -x (POSIX)."""
    try:
        import psutil  # type: ignore
        n = 0
        for p in psutil.process_iter(["name"]):
            pn = (p.info.get("name") or "")
            if pn == name or pn == name + ".exe":
                n += 1
        return n
    except Exception:
        pass
    try:
        if IS_WINDOWS:
            # errors="replace": with no match, tasklist prints a LOCALIZED
            # "INFO: No tasks are running…" line (zh-CN: 0xd0 GBK bytes) that
            # crashes the strict-utf-8 reader thread — off-thread, so the
            # except below can't catch it (FAILURE-LOG 2026-07-24). Only reached
            # when psutil is absent (fresh box).
            out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}.exe"],
                                 capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", timeout=15).stdout
            return out.count(name + ".exe")
        cp = subprocess.run(["pgrep", "-x", name], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=15)
        return len([x for x in cp.stdout.split() if x.strip()])
    except (OSError, subprocess.SubprocessError):
        return 0


def kill_by_image(*names: str) -> None:
    """Force-kill processes by image/executable name. taskkill /F /IM (Windows)
    vs pkill -f (POSIX). Names without a meaning on the host (LiveCodingConsole,
    CrashReportClient on POSIX) are harmless no-ops.

    The BLUNTEST primitive in the rig — it reaps by image name, so it cannot
    tell a live drive editor from debris. It is therefore gated
    UNCONDITIONALLY (no test substitutes it; see the kill-gate block comment):
    this is the exact call that killed a live editor on 2026-08-07."""
    for name in names:
        if not _kill_permitted(f"image={name}", "kill_by_image"):
            continue
        audit_kill(f"image={name}", "kill_by_image")
        try:
            if IS_WINDOWS:
                image = name if name.lower().endswith(".exe") else name + ".exe"
                subprocess.run(["taskkill", "/F", "/IM", image],
                               capture_output=True, timeout=20)
            else:
                subprocess.run(["pkill", "-9", "-f", name],
                               capture_output=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            pass


# --------------------------------------------------------------------------- #
# Cross-folder editor isolation: craftbench shares ONE editor RC port (:30010)
# and ONE Aura session (%LOCALAPPDATA%/Programs/aura-client/.Aura) with any other
# Aura usage on this box (e.g. a dev editor in ../unrealfeaturedev). So a blanket
# `kill_by_image("UnrealEditor")` would reap the user's OWN editor, and a
# project-aware restart would hijack :30010 out from under it. These helpers scope
# every destructive action to craftbench's OWN editor (a CraftBench* project) and
# let callers REFUSE to run while a foreign editor is live.
# --------------------------------------------------------------------------- #

# craftbench's editor opens a substrate project either in the managed scratch
# root (<cb_root>/scratch/* — CraftBenchScratch, CraftBenchGraded,
# ThirdPersonScratch, ...) or in-repo under UE-projects/. The default-substrate
# paths carry "craftbench" in the .uproject path, but a NON-default substrate's
# scratch does NOT (2026-07-21: the r4 ThirdPerson scratch editor was
# misclassified FOREIGN and blocked its own re-run) — so ownership is
# path-based: the legacy marker OR a project under the managed scratch root.
# Any other UnrealEditor is FOREIGN.
_CB_EDITOR_MARKER = "craftbench"


def _cb_owned_path_markers() -> "list[str]":
    """Lowercased path fragments that mark an editor cmdline as craftbench's own.

    ONE source of truth: stack_guard.cb_cmdline_markers() — the same set the
    orphan sweep kills on — so the per-drive gate, foreign_editor(),
    kill_craftbench_editors() and the sweep can never disagree about whose an
    editor is. They DID disagree (measured 2026-08-19): this function knew only
    the legacy name marker + the scratch root, so a headless editor opened on
    the repo's own UE-projects/ThirdPerson — a path with no "craftbench"
    substring — was refused as FOREIGN by the unreal-mcp per-drive gate, while
    `cb down`'s sweep (whose markers include the repo root and wd root)
    correctly reaped the same process as "older-generation cb debris". Two
    ceilinged go/no-go runs stalled pre-spend on exactly that split.

    Lazy import (stack_guard references this module's primitives, so a
    top-level import would be circular). The fallback keeps the old narrower
    set if the import ever breaks — a narrower set only ever REFUSES more at
    the gate; it never widens a kill."""
    try:
        from aura_rig import stack_guard as _sg  # noqa: PLC0415
        return [m.lower() for m in _sg.cb_cmdline_markers()]
    except Exception:
        markers = [_CB_EDITOR_MARKER]
        try:
            root = str(cb_paths.scratch_root()).lower()
            markers.append(root)
            markers.append(root.replace("\\", "/"))
        except Exception:
            pass
        return markers


def _parse_pid_cmdline_lines(text: str) -> "list[tuple[int, str]]":
    """Parse 'PID|commandline' lines (the PowerShell CIM fallback's format) into
    [(pid, cmdline_lower)]. Pure — unit-tested offline."""
    procs: "list[tuple[int, str]]" = []
    for line in (text or "").splitlines():
        pid_s, sep, cl = line.strip().partition("|")
        if sep and pid_s.isdigit():
            procs.append((int(pid_s), cl.lower()))
    return procs


def _editor_procs() -> "list[tuple[int, str]]":
    """[(pid, cmdline_lower)] for running UnrealEditor (GUI/headless, NOT -Cmd).
    psutil → wmic → PowerShell CIM (Win) / ps (POSIX) fallbacks. Empty if nothing
    runs OR enumeration fails (callers fail-open: don't block, fall back to the
    blanket kill). The CIM rung matters on current Win11, where wmic is removed
    and a psutil-less install used to leave the editor guards blind."""
    procs: "list[tuple[int, str]]" = []
    try:
        import psutil  # type: ignore
        for p in psutil.process_iter(["name", "pid", "cmdline"]):
            if (p.info.get("name") or "") in ("UnrealEditor", "UnrealEditor.exe"):
                procs.append((p.info.get("pid"), " ".join(p.info.get("cmdline") or []).lower()))
        return procs
    except Exception:
        pass
    try:
        if IS_WINDOWS:
            # PowerShell CIM FIRST, wmic second: wmic is removed by default on
            # Windows 11 24H2+, and psutil is an OPTIONAL dep (pyproject deps=[]),
            # so on a fresh box neither the psutil arm above nor wmic may exist —
            # without a CIM fallback _editor_procs returns [], the foreign-editor
            # guard fails open, and kill scoping degrades to a blanket kill that
            # could reap the operator's OWN editor (FAILURE-LOG 2026-07-24).
            ps = (
                "Get-CimInstance Win32_Process -Filter \"Name='UnrealEditor.exe'\" | "
                "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }"
            )
            out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                                 capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=20).stdout
            for line in out.splitlines():
                if "\t" not in line:
                    continue
                pid_s, _, cl = line.partition("\t")
                if pid_s.strip().isdigit():
                    procs.append((int(pid_s.strip()), cl.lower()))
            if procs:
                return procs
            # wmic fallback (older Windows where CIM returned nothing/failed).
            out = subprocess.run(["wmic", "process", "where", "name='UnrealEditor.exe'",
                                  "get", "ProcessId,CommandLine", "/format:list"],
                                 capture_output=True, text=True, timeout=15).stdout
            pid, cl = None, ""
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("CommandLine="):
                    cl = line[len("CommandLine="):].lower()
                elif line.startswith("ProcessId="):
                    try:
                        pid = int(line[len("ProcessId="):])
                    except ValueError:
                        pid = None
                    if pid is not None:
                        procs.append((pid, cl))
                    pid, cl = None, ""
        else:
            out = subprocess.run(["ps", "-eo", "pid=,args="],
                                 capture_output=True, text=True, timeout=15).stdout
            for line in out.splitlines():
                low = line.lower()
                if "unrealeditor" in low and "unrealeditor-cmd" not in low:
                    parts = line.strip().split(None, 1)
                    if len(parts) == 2 and parts[0].isdigit():
                        procs.append((int(parts[0]), parts[1].lower()))
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    if not procs and IS_WINDOWS:
        try:  # wmic removed on current Win11 builds — CIM is the surviving route
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Process -Filter \"Name='UnrealEditor.exe'\" | "
                 "ForEach-Object { '{0}|{1}' -f $_.ProcessId, $_.CommandLine }"],
                capture_output=True, text=True, timeout=20).stdout
            procs = _parse_pid_cmdline_lines(out)
        except (OSError, subprocess.SubprocessError):
            pass
    return procs


def _is_craftbench_editor(cmdline_lower: str) -> bool:
    return any(m in cmdline_lower for m in _cb_owned_path_markers())


def foreign_editor() -> "Optional[tuple[int, str]]":
    """(pid, cmdline) of a running UnrealEditor that is NOT craftbench's — e.g. the
    user's dev editor in another folder (unrealfeaturedev). None if none / can't
    enumerate (fail-open). craftbench shares :30010 + the .Aura session, so callers
    use this to refuse to hijack someone else's editor."""
    for pid, cl in _editor_procs():
        if cl and not _is_craftbench_editor(cl):
            return (pid, cl)
    return None


def kill_craftbench_editors(log=print) -> None:
    """Force-kill ONLY craftbench's UnrealEditor(s) (a CraftBench* project), SPARING
    any foreign editor (e.g. unrealfeaturedev). Replaces a blanket
    `kill_by_image("UnrealEditor")` so `cb down`/restart never reaps the user's own
    dev editor. Falls back to the blanket kill only when no procs can be enumerated.

    TREE-kill (taskkill /T / children-first): a bare per-PID kill orphans the
    editor's LiveCodingConsole (holds the machine-wide Live Coding build mutex)
    and its aura_server python child — the 2026-07-24 zombie-overlap debris."""
    procs = _editor_procs()
    if not procs:
        kill_by_image("UnrealEditor")  # can't enumerate → old best-effort behavior
        return
    killed = spared = 0
    for pid, cl in procs:
        if _is_craftbench_editor(cl):
            audit_kill(f"pid={pid} (editor tree)", "ensure_editor_dead")
            try:
                if IS_WINDOWS:
                    _run_kill_cmd(["taskkill", "/F", "/T", "/PID", str(pid)],
                                  target=f"pid={pid} (editor tree)",
                                  reason="kill_craftbench_editors")
                else:
                    for tpid in _proc_tree_pids(pid):  # children first, then the editor
                        _run_kill_cmd(["kill", "-9", str(tpid)],
                                      target=f"pid={tpid} (editor tree)",
                                      reason="kill_craftbench_editors")
                killed += 1
            except (OSError, subprocess.SubprocessError):
                pass
        else:
            spared += 1
    if spared:
        log(f"  SPARED {spared} foreign UnrealEditor(s) (not a CraftBench project — "
            f"e.g. another folder's Aura); killed {killed} craftbench editor(s)")


def _proc_tree_pids(pid: int) -> "list[int]":
    """<pid> plus all its live descendants, children first (so kills walk leaf-up).
    psutil when present; just [pid] when it isn't / the pid is already gone."""
    try:
        import psutil  # type: ignore
        return [c.pid for c in psutil.Process(pid).children(recursive=True)] + [pid]
    except Exception:
        return [pid]


def ensure_editor_dead(old_pids: "Optional[Sequence[int]]" = None, *,
                       grace_s: float = 15.0, kill_wait_s: float = 10.0,
                       sweep_wait_s: float = 5.0, poll_s: float = 1.0,
                       always_sweep: bool = False,
                       procs=None, kill_scoped=None, sweep=None,
                       foreign_check=None,
                       sleep=time.sleep, clock=time.monotonic,
                       log=print) -> bool:
    """Verify craftbench's OLD editor actually died — force-killing zombies and
    their children if it didn't — BEFORE the next editor launches.

    UE 5.8 editors wedge on graceful exit (the RequestExit quirk the L2 grader
    force-kills for). A lingering drive editor overlaps the next rep's session:
    it clobbers the machine-global aura_server_port.txt (the new session's
    "LogAura: Failed to start server after 50 attempts" → every agent tool
    'Failed to fetch'), holds the primary log (sessions land in <Project>_2.log)
    and scratch file handles the recompose deletes from under it (disk I/O
    errors), and its LiveCodingConsole child blocks the next bench's envgate
    preflight. FAILURE-LOG 2026-07-24 (7/9 reps).

    Modes: ``old_pids`` given → poll those EXACT pids until gone (a NEWLY
    launched editor never matches). ``old_pids=None`` → poll the scoped
    set (every live CraftBench-owned editor). Foreign/user editors are
    structurally excluded in both modes — never poll or kill by image here.

    Escalation: grace-poll → scoped tree-kill → LiveCodingConsole/
    CrashReportClient image sweep (gated on NO foreign editor — with one
    running, those images may be the user's own crash dialog / live-coding
    session; the envgate live-coding probe stays the pre-spend detector).
    ``always_sweep`` sweeps even after a clean death (the per-rep grade path
    uses it so a bench never leaves the mutex-holding console behind).

    Never raises; returns False (WARN, callers proceed — bring-up self-heal
    attempts 2/3 are the backstop) only when a pid survives everything.
    ``CB_NO_EDITOR_REAP=1`` skips the whole thing (debugging a live editor)."""
    if env_flag("CB_NO_EDITOR_REAP"):
        log("  ..    CB_NO_EDITOR_REAP=1 — editor reap/verify SKIPPED")
        return True
    procs = procs or _editor_procs
    kill_scoped = kill_scoped or kill_craftbench_editors
    sweep = sweep or (lambda: kill_by_image("LiveCodingConsole", "CrashReportClient"))
    foreign_check = foreign_check or foreign_editor

    def _targets() -> "set[int]":
        try:
            live = procs()
        except Exception:
            return set()
        if old_pids is not None:
            wanted = set(old_pids)
            return {pid for pid, _cl in live if pid in wanted}
        return {pid for pid, cl in live if _is_craftbench_editor(cl)}

    def _sweep_if_safe(reason: str) -> None:
        try:
            if foreign_check() is not None:
                log("  ..    LiveCodingConsole/CrashReportClient sweep SKIPPED "
                    "(a foreign editor is running — they may be its)")
                return
            sweep()
            log(f"  ..    swept LiveCodingConsole/CrashReportClient ({reason})")
        except Exception:
            pass

    try:
        start = clock()
        alive = _targets()
        if not alive:                     # already gone (or enumeration blind: fail-open)
            if always_sweep:
                _sweep_if_safe("post-shutdown reap")
            return True
        # Phase 1 — grace: a healthy graceful shutdown finishes here in a poll or two.
        while clock() - start < grace_s:
            sleep(poll_s)
            alive = _targets()
            if not alive:
                log(f"  OK    old editor gone after {clock() - start:.0f}s")
                if always_sweep:
                    _sweep_if_safe("post-shutdown reap")
                return True
        # Phase 2 — escalate: the RequestExit zombie. Scoped tree-kill.
        log(f"  WARN  old editor pid(s) {sorted(alive)} still alive {grace_s:.0f}s "
            f"after shutdown — force-killing (scoped tree-kill)")
        try:
            kill_scoped(log)
        except Exception:
            pass
        kill_start = clock()
        while clock() - kill_start < kill_wait_s:
            sleep(poll_s)
            alive = _targets()
            if not alive:
                break
        # Phase 3 — sweep the mutex-holding children even if the editor died,
        # then give survivors one last window.
        _sweep_if_safe("post-force-kill")
        if alive:
            sweep_start = clock()
            while clock() - sweep_start < sweep_wait_s:
                sleep(poll_s)
                alive = _targets()
                if not alive:
                    break
        if not alive:
            log(f"  OK    old editor reaped after {clock() - start:.0f}s")
            return True
        log(f"  WARN  old editor pid(s) {sorted(alive)} survived the force-kill — "
            f"proceeding (bring-up attempts 2/3 are the backstop)")
        return False
    except Exception as e:  # the reap must never be the outage
        log(f"  WARN  editor reap errored ({e.__class__.__name__}: {e}) — proceeding")
        return False


# =========================================================================== #
# 5. Scratch playground lifecycle.                                             #
#    (ports Get-DriveProjectDir / Initialize-DriveProject / Reset-DriveProject) #
# =========================================================================== #

def find_uproject(dir_: Path) -> Path:
    """The single root ``.uproject`` of a project/scratch dir.

    Multi-substrate seam: the scratch's project name is SUBSTRATE-DERIVED
    (graded_scratch composes whichever substrate the active task declares), so
    consumers GLOB instead of hardcoding ``CraftBenchTemplate.uproject``.
    Exactly one is expected — zero (not a project dir yet) or several (a stale
    other-substrate .uproject survived a recompose) both raise
    ``FileNotFoundError`` naming what was found."""
    found = sorted(Path(dir_).glob("*.uproject"))
    if len(found) == 1:
        return found[0]
    names = ", ".join(p.name for p in found) or "(none)"
    raise FileNotFoundError(
        f"expected exactly one .uproject under {dir_}, found {len(found)}: {names}")


def get_drive_project_dir(explicit: str = "") -> Path:
    """Resolve the headless-drive PLAYGROUND dir — NEVER the benchmark substrate.
    Precedence: explicit arg -> CB_DRIVE_PROJECT -> the CB_ROOT default
    (``<cb_root>/scratch/CraftBenchScratch``, see :mod:`aura_rig.paths` — the
    old LOCALAPPDATA / XDG-cache default retired with CB_ROOT). The leaf
    project dir is 'CraftBenchScratch' but the .uproject inside keeps the
    template name 'CraftBenchTemplate.uproject'."""
    if explicit:
        return Path(explicit)
    env = os.environ.get("CB_DRIVE_PROJECT")
    if env:
        return Path(env)
    return cb_paths.scratch_root() / "CraftBenchScratch"


def _copy2_retry(src: Path, dst: Path, *, retries: int = 5, base_delay: float = 0.4) -> None:
    """shutil.copy2 that rides out a TRANSIENT Windows share-lock on the dst — a
    lingering editor handle on a .umap that a graded-scratch recompose is
    overwriting (WinError 32). Retries with backoff; re-raises the last OSError if
    the lock never clears, so a genuinely-locked file still fails the compose
    LOUDLY (compose raises -> the rep records a clean error) rather than leaving a
    stale scratch file that would grade wrong."""
    for attempt in range(retries):
        try:
            shutil.copy2(src, dst)
            return
        except OSError:
            if attempt == retries - 1:
                raise
            time.sleep(min(base_delay * (2 ** attempt), 3.0))


_DELETE_RETRIES = 4  # default attempts for a WATCHED delete (graded compose)


def _delete_retry(path: Path, *, is_dir: bool, retries: int = _DELETE_RETRIES,
                  base_delay: float = 0.4) -> bool:
    """unlink/rmtree that rides out a TRANSIENT Windows share-lock on a
    delete_extras target — the same lingering-editor-handle class _copy2_retry
    exists for, on the DELETE side. Returns False when the entry still exists
    after the last attempt; the CALLER decides whether a survivor is fatal
    (graded-scratch compose: it is — an un-reset extra contaminates the next
    grade) or tolerable (a drive-project init/reset).

    Verdicts use lexists, not exists: a dangling symlink/junction IS a
    survivor even though exists() follows it to nothing. A symlink/junction
    dir is removed as the LINK (os.rmdir) — never rmtree'd THROUGH to the
    target (the PR-#15 junction-gutting class; see _unlink_plugin_link and
    fs_cleanup.robust_rmtree, this family's other members). A
    FileNotFoundError out of rmtree can be a CHILD vanishing under a
    concurrent cleaner while the dir itself survives, so it only counts as
    success when the path is gone."""
    for attempt in range(retries):
        try:
            if is_dir and _is_link_or_junction(path):
                os.rmdir(str(path))  # the LINK itself, never its target
            elif is_dir:
                shutil.rmtree(path)
            else:
                try:
                    path.unlink()
                except PermissionError:
                    # Windows deletes dir links via rmdir, and a DANGLING dir
                    # link walks as a file — classify only on failure so the
                    # common file delete stays one syscall.
                    if _is_link_or_junction(path):
                        os.rmdir(str(path))
                    else:
                        raise
            return True
        except FileNotFoundError:
            if not os.path.lexists(str(path)):
                return True
            # a CHILD vanished mid-rmtree; the dir itself survives — retry
        except OSError:
            pass
        if attempt == retries - 1:
            break
        time.sleep(min(base_delay * (2 ** attempt), 3.0))
    return not os.path.lexists(str(path))


def _mirror_tree(src: Path, dst: Path, *, delete_extras: bool,
                 failed_deletes: Optional[List[str]] = None) -> bool:
    """Recursive copy of <src> -> <dst>. With delete_extras (the /MIR analog) the
    destination is made to EXACTLY equal the source (deleting dst files absent from
    src). Without it (the /E analog) it copies/overwrites and leaves extras alone.
    Returns True on success (mimics robocopy exit<8); False only on a real OSError.

    A dst extra whose deletion still fails after retries (a LOCKED file — e.g.
    a live editor's handle) is reported into ``failed_deletes`` (dst-relative
    POSIX paths, dirs suffixed "/") when the caller passes a list; the
    graded-scratch compose treats any survivor as fatal because a mirror that
    silently keeps extras is not a reset. Without a collector the sweep stays
    best-effort (a drive-project reset)."""
    try:
        dst.mkdir(parents=True, exist_ok=True)
        # Copy / overwrite everything from src (retry transient dst locks).
        for root, _dirs, files in os.walk(src):
            rel = Path(root).relative_to(src)
            target_dir = dst / rel
            target_dir.mkdir(parents=True, exist_ok=True)
            for f in files:
                _copy2_retry(Path(root) / f, target_dir / f)
        if delete_extras:
            # Remove dst entries that have no src counterpart. Retries are
            # for the WATCHED path only (the graded compose, which turns a
            # survivor into a refusal); collector-less callers keep the old
            # instant best-effort sweep.
            _retries = _DELETE_RETRIES if failed_deletes is not None else 1
            for root, dirs, files in os.walk(dst, topdown=False):
                src_dir = src / Path(root).relative_to(dst)
                for name, entry_is_dir in (
                        [(f, False) for f in files] + [(d, True) for d in dirs]):
                    if (src_dir / name).exists():
                        continue
                    p = Path(root) / name
                    rel = p.relative_to(dst).as_posix()
                    if entry_is_dir and failed_deletes and any(
                            x.startswith(rel + "/") for x in failed_deletes):
                        continue  # ancestor of a reported survivor — told already
                    if not _delete_retry(p, is_dir=entry_is_dir, retries=_retries):
                        if failed_deletes is not None:
                            failed_deletes.append(rel + ("/" if entry_is_dir else ""))
                            # The refusal is already decided by the first
                            # survivor — stop paying per-file backoff.
                            _retries = 1
        return True
    except OSError:
        return False


# Dir names never copied into the agent-visible scratch when staging a plugin:
# VCS metadata, build intermediates (regenerable, huge), and node deps (the Node
# servers run from the MAIN Plugins clone, not the scratch). Binaries/ is DELIBERATELY
# KEPT: Aura ships Installed:true (precompiled), so UBT skips building it in the scratch
# — the editor needs the prebuilt UnrealEditor-Aura.dll, or it mounts Aura with no
# binary and exits on startup. _clean_scratch_build_dirs wipes only the scratch's
# top-level Binaries/, never Plugins/, so the copied plugin DLLs survive a clean rebuild.
_PLUGIN_COPY_EXCLUDE = {".git", "Intermediate", "node_modules"}

# Written into every scratch Plugins/<name>/ copy at copy time so freshness is
# judgeable later: {src, genius_sha, copied_at}. Without it a persisted copy is
# of unknown vintage (2026-07-22 audit: a scratch drove a July-10 Aura while
# the rig sat at a July-21 sha and summary.json couldn't say which ran).
_PLUGIN_PROV_MARKER = ".cb-plugin-provenance.json"


def _genius_git_sha(genius: Path) -> Optional[str]:
    """HEAD sha of the aura-plugin checkout; None when git/repo is absent."""
    try:
        r = subprocess.run(["git", "-C", str(genius), "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=15)
        out = (r.stdout or "").strip()
        return out or None
    except (OSError, subprocess.SubprocessError):
        return None


def _plugin_copy_fresh(dst: Path, src: Path, src_sha: Optional[str]) -> "tuple[bool, str]":
    """Is the persisted plugin copy at <dst> still the rig's CURRENT content?

    Anchored by the :data:`_PLUGIN_PROV_MARKER` written at copy time. With no
    rig sha available (genius isn't a git checkout) staleness is unjudgeable —
    keep the copy (the pre-marker behavior)."""
    if src_sha is None:
        return True, "rig sha unavailable - keeping existing copy"
    try:
        m = json.loads((dst / _PLUGIN_PROV_MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False, "no provenance marker (copy of unknown vintage)"
    if m.get("src") != str(src):
        return False, f"copied from a different source ({m.get('src')})"
    if m.get("genius_sha") != src_sha:
        return False, (f"rig moved: copy is {str(m.get('genius_sha'))[:9]}, "
                       f"rig is {src_sha[:9]}")
    return True, "marker matches the rig sha"


def _write_plugin_marker(dst: Path, src: Path, src_sha: Optional[str]) -> None:
    import datetime as _dt
    try:
        (dst / _PLUGIN_PROV_MARKER).write_text(json.dumps({
            "src": str(src),
            "genius_sha": src_sha,
            "copied_at": _dt.datetime.now().isoformat(timespec="seconds"),
        }, indent=1), encoding="utf-8")
    except OSError:
        pass


def _is_link_or_junction(p: Path) -> bool:
    """True for a POSIX/Windows symlink OR an NTFS junction (is_junction is 3.12+)."""
    try:
        if p.is_symlink():
            return True
        ij = getattr(p, "is_junction", None)
        return bool(ij and ij())
    except OSError:
        return False


def _unlink_plugin_link(p: Path, log=print) -> bool:
    """Remove a symlink/junction at <p> WITHOUT recursing into its target (rmdir/unlink
    the reparse point only — NEVER shutil.rmtree, which would delete THROUGH a junction
    into the aura-plugin clone). Returns True iff <p> is absent afterwards."""
    if not os.path.lexists(p):
        return True
    try:
        p.rmdir()             # removes a junction / dir-symlink reparse point (link only)
    except OSError:
        try:
            p.unlink()
        except OSError as e:
            log(f"  FAIL  could not remove link {p}: {e}")
            return False
    return not os.path.lexists(p)


# Client RUNTIME state — live-mutated by a running :3002 client (its exclusive
# handles race the copy: the 2026-07-22 Ramen refresh died on a share-lock) and
# meaningless to the editor, which reads the scratch Ramen ONLY for the client
# .env (GetClientPath). Never copied into a scratch.
_RAMEN_RUNTIME_EXCLUDE = frozenset(
    {".next", ".Aura", "logs", ".turbo", "test-results", "playwright-report"})


def _copy_plugin_tree(src: Path, dst: Path,
                      extra_exclude: frozenset = frozenset()) -> Optional[str]:
    """Copy the plugin subtree <src> -> <dst>, pruning :data:`_PLUGIN_COPY_EXCLUDE`
    (+ ``extra_exclude``, dirs AND files) at every level. Returns None on
    success, else a short error string naming the path that failed."""
    ex = set(_PLUGIN_COPY_EXCLUDE) | set(extra_exclude)
    cur = src
    try:
        for root, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if d not in ex]
            rel = Path(root).relative_to(src)
            target_dir = dst / rel
            target_dir.mkdir(parents=True, exist_ok=True)
            for f in files:
                if f in ex:
                    continue
                cur = Path(root) / f
                _copy2_retry(cur, target_dir / f)
        return None
    except OSError as e:
        return f"{e.__class__.__name__} on {cur}: {e}"


def _build_script(ue_root: Path) -> Path:
    """Per-OS UBT build script under Engine/Build/BatchFiles."""
    bf = ue_root / "Engine" / "Build" / "BatchFiles"
    if IS_WINDOWS:
        return bf / "Build.bat"
    if sys.platform == "darwin":
        return bf / "Mac" / "Build.sh"
    return bf / "Linux" / "Build.sh"


def _build_platform_token() -> str:
    if IS_WINDOWS:
        return "Win64"
    if sys.platform == "darwin":
        return "Mac"
    return "Linux"


def _scratch_build_action(marker_text: Optional[str], engine_stamp: str) -> str:
    """Decide what the scratch build should do, given the ``.cb-built`` marker's
    contents and the CURRENT engine stamp (the UE root). Pure -> unit-testable.

      * ``"skip"``  — marker present AND its stamp matches this engine: up to date.
      * ``"clean"`` — marker present but the stamp DIFFERS (engine changed) OR is
        empty (a pre-stamp marker from the old empty-``touch`` format): the existing
        Binaries/objects are for a different engine, so wipe + rebuild. This is what
        fixes the "scratch built on UE 5.7, editor launched on 5.8 -> 'game module
        could not be found'" failure (and the stale-.obj link errors after it).
      * ``"build"`` — no marker: a normal (incremental) build.
    """
    if marker_text is None:
        return "build"
    return "skip" if marker_text.strip() == engine_stamp.strip() else "clean"


def _clean_scratch_build_dirs(dir_: Path, log=print) -> None:
    """Remove the scratch's ``Binaries`` + ``Intermediate`` for a CLEAN rebuild.
    NEVER touches ``Plugins/`` — it holds the one-time scoped COPY of Aura + Ramen
    (ensure_scratch_plugins); wiping it would force a multi-GB re-copy every clean build."""
    for d in ("Binaries", "Intermediate"):
        p = dir_ / d
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
    log("  ..    cleared scratch Binaries + Intermediate (clean rebuild)")


def _git_restore_gutted_plugin(genius: Path, name: str, log=print) -> bool:
    """Self-heal a GUTTED aura-plugin subtree. The hazard (2026-07-21
    FAILURE-LOG): a checkout in a consumer repo that removes a tracked
    Plugins/<name> link can recurse THROUGH the junction and delete the
    target checkout's files — a later scratch copy then faithfully ships an
    empty plugin and the editor boots Aura-less ("Aura disconnected / MCP
    server not found").

    Restores via ``git -C <genius> checkout -- <name>``, but ONLY when git
    reports the subtree as purely unstaged deletions (plus untracked
    leftovers) — re-materializing files git says are deleted can never lose
    work. Anything else (modifications, staged state, not a git checkout)
    -> False, and the caller fails loudly with the manual recovery hint.
    NB: untracked build artifacts (Binaries/) are NOT git-recoverable; the
    caller warns and the scratch editor-target build recompiles them."""
    try:
        st = subprocess.run(
            ["git", "-C", str(genius), "status", "--porcelain", "--", name],
            capture_output=True, text=True, timeout=120)
        if st.returncode != 0:
            return False
        lines = [ln for ln in st.stdout.splitlines() if ln.strip()]
        deletions = [ln for ln in lines if ln.startswith(" D ")]
        benign = [ln for ln in lines if ln.startswith("?? ")]
        if not deletions or len(deletions) + len(benign) != len(lines):
            return False
        log(f"  WARN  aura-plugin {name}/ is gutted ({len(deletions)} tracked "
            f"files deleted on disk — the Plugins-junction git hazard); "
            f"self-healing via `git -C {genius} checkout -- {name}`")
        rc = subprocess.run(
            ["git", "-C", str(genius), "checkout", "--", name],
            capture_output=True, text=True, timeout=600)
        return rc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def ensure_scratch_plugins(dir_: Path, paths: StackPaths, log=print) -> bool:
    """Ensure <dir>/Plugins/{Aura,Ramen} are real COPIES of the host-local aura-plugin
    clone (``paths.genius/{Aura,Ramen}``), scoped to exclude
    :data:`_PLUGIN_COPY_EXCLUDE`. This replaced the old Aura JUNCTION: a real copy gives
    the scratch its own DLLs (no shared-DLL lock with other editors), stages Ramen too
    (the editor needs <scratch>/Plugins/Ramen/mcp-client-chatbot/.env for GetClientPath),
    and never exposes the aura-plugin clone's non-plugin content to the agent.

    Copied ONCE and persisted — Plugins/ is not in the per-task compose mirror, so this
    is a one-time cost per scratch lifetime. Idempotent: a plugin already copied is kept.
    A legacy Plugins/<name> symlink/junction is removed link-only (never recursing into
    the aura-plugin target) before copying.

    Fail-closed on a GUTTED source (dir present, sentinel missing): tries the
    safe git self-heal (:func:`_git_restore_gutted_plugin`), then refuses
    rather than copy an empty plugin; the copy is also sentinel-verified
    afterwards. Both defenses from the 2026-07-21 incident.

    NO CLONE, NO STAGING, NO FAILURE (open-source release, 2026-08-28). Both
    plugins named here belong to the private Aura product, which this release
    does not ship (THIRD-PARTY.md §4). This used to be fail-CLOSED on an absent
    source, which was right while every lane's editor needed Aura and is wrong
    now: the two arms you can actually run want a stock editor — `unreal-mcp`
    launches with ``-DisablePlugins=Reflex,Aura`` on purpose, and `claude-p`
    opens no editor at all — so refusing here would break `cb headless` and the
    drive playground over a dependency neither of them has. An ABSENT clone is
    therefore announced and skipped. Everything below is unchanged for a box
    that does have the clone, including the fail-closed GUTTED path: a source
    that is present but hollow is still a fault, not a configuration."""
    plug = Path(dir_) / "Plugins"
    plug.mkdir(parents=True, exist_ok=True)
    if not any((paths.genius / n).exists() for n in ("Aura", "Ramen")):
        log("  ..    no aura-plugin clone at "
            f"{paths.genius} — skipping Plugins/{{Aura,Ramen}} staging "
            "(not part of this release; the unreal-mcp editor runs stock)")
        return True
    src_sha = _genius_git_sha(paths.genius)
    for name, sentinel in (("Aura", "Aura.uplugin"),
                           ("Ramen", "mcp-client-chatbot")):
        src = paths.genius / name
        dst = plug / name
        # Migrate a legacy junction/symlink at the dst name (link-only removal).
        if _is_link_or_junction(dst):
            log(f"  ..    replacing legacy Plugins/{name} symlink/junction with a real copy")
            if not _unlink_plugin_link(dst, log):
                return False
        # Idempotent: a real copy already present (sentinel exists) -> keep it,
        # but ONLY while it is still the rig's CURRENT content (marker-anchored;
        # 2026-07-22 audit: a scratch silently drove a stale July-10 Aura).
        if (dst / sentinel).exists() and not _is_link_or_junction(dst):
            fresh, why = _plugin_copy_fresh(dst, src, src_sha)
            if fresh:
                continue
            log(f"  ..    Plugins/{name} persisted copy is STALE -> refreshing ({why})")
            shutil.rmtree(dst, ignore_errors=True)
            if dst.exists():
                log(f"  FAIL  could not remove the stale Plugins/{name} copy at {dst} "
                    f"(held file lock? close editors, then retry)")
                return False
        if not src.exists():
            log(f"  FAIL  aura-plugin clone missing {src} — clone aura-plugin into "
                f"{paths.template_dir / 'Plugins'} (see `cb doctor` / `cb bootstrap`)")
            return False
        if not (src / sentinel).exists():
            # Dir present but GUTTED (2026-07-21 incident: a consumer-repo
            # checkout deleted THROUGH the Plugins/<name> junction). Never
            # copy an empty plugin — try the safe git self-heal, else refuse.
            if _git_restore_gutted_plugin(paths.genius, name, log):
                log(f"  OK    aura-plugin {name}/ restored from its git index")
            if not (src / sentinel).exists():
                log(f"  FAIL  aura-plugin {name}/ is gutted at {src} (no "
                    f"{sentinel}) and could not be self-healed. Recover with "
                    f"`git -C {paths.genius} checkout -- {name}` (built "
                    f"Binaries/ may additionally need a rebuild or a copy "
                    f"from an intact scratch), or re-clone aura-plugin — "
                    f"see `cb doctor`.")
                return False
        log(f"  ..    copying Plugins/{name} from the aura-plugin clone "
            f"(scoped: no {'/'.join(sorted(_PLUGIN_COPY_EXCLUDE))})")
        copy_err = _copy_plugin_tree(
            src, dst,
            extra_exclude=_RAMEN_RUNTIME_EXCLUDE if name == "Ramen" else frozenset())
        if copy_err:
            log(f"  FAIL  could not copy Plugins/{name} from {src} ({copy_err})")
            return False
        if not (dst / sentinel).exists():
            log(f"  FAIL  Plugins/{name} copy landed without {sentinel} — "
                f"refusing a gutted plugin copy (source: {src})")
            return False
        _write_plugin_marker(dst, src, src_sha)
        if name == "Aura" and not (dst / "Binaries").is_dir():
            log("  WARN  Plugins/Aura has no Binaries/ — expected on a fresh "
                "aura-plugin clone (the scratch editor-target build compiles "
                "the plugin); on a previously-built rig this means the built "
                "DLLs were lost (the 2026-07-21 gutting) — rebuild or restore "
                "them or the editor boots Aura-less.")
    return True


def initialize_drive_project(dir_: Path, paths: StackPaths, log=print) -> bool:
    """Create the scratch playground (lean copy) and build its editor target,
    guarded by a ``.cb-built`` marker STAMPED WITH THE ENGINE. Returns True
    when ready.

    PHASE A (only if <dir> holds no root .uproject yet): lean-copy
    Source/Content/Config + 3 root files; stage Plugins/ from the aura-plugin
    clone IF this box has one (:func:`ensure_scratch_plugins` — a no-op in this
    release, where those plugins are not distributed).
    PHASE B: delegated to :func:`build_drive_project` (shared with the graded
    scratch): skip if the marker's engine stamp matches the current UE;
    CLEAN-rebuild (wipe Binaries+Intermediate) if it was built against a
    different engine (or is a pre-stamp marker); else incremental-build.
    """
    dir_ = Path(dir_)
    # Substrate-agnostic project detection (a graded scratch composed for a
    # non-default substrate carries THAT substrate's .uproject name).
    uproj = next(dir_.glob("*.uproject"), None) if dir_.is_dir() else None

    # ---- PHASE A: create the lean project ----
    if uproj is None:
        log(f"  ..    creating drive playground (one-time): {dir_}")
        dir_.mkdir(parents=True, exist_ok=True)
        for d in ("Source", "Content", "Config"):
            s = paths.template_dir / d
            if s.exists():
                if not _mirror_tree(s, dir_ / d, delete_extras=False):
                    log(f"  FAIL  copy of {d} failed")
                    return False
        for f in ("CraftBenchTemplate.uproject", "AGENT_WRITABLE.json", "README.md"):
            s = paths.template_dir / f
            if s.exists():
                try:
                    shutil.copy2(s, dir_ / f)
                except OSError:
                    pass
        if not ensure_scratch_plugins(dir_, paths, log=log):
            return False
        log("  OK    scratch files staged")

    return build_drive_project(dir_, log=log)


def l1_cap() -> Optional[int]:
    """``CRAFTBENCH_L1_MAX_PARALLEL`` as a positive int, or None (no cap).

    Leading-integer parse — an inline .env comment ("2 #tested up to 4" -> 2)
    must not silently drop the operator's cap (FAILURE-LOG 2026-07-24; same
    convention as tools/verify-single/layers/l1_build.py)."""
    raw = os.environ.get("CRAFTBENCH_L1_MAX_PARALLEL", "").strip()
    m = re.match(r"[0-9]+", raw)
    if not m:
        return None
    n = int(m.group())
    return n if n > 0 else None


def build_drive_project(dir_: Path, log=print) -> bool:
    """Build a scratch project's editor target (engine+project-stamped
    ``.cb-built`` staleness; clean-rebuild on engine OR substrate change;
    build-dir clear on failure). Factored from initialize_drive_project
    PHASE B so the graded scratch (C1) reuses the exact proven build path.
    Returns True when up to date.

    Substrate-agnostic: the project + its editor target are derived from the
    ONE .uproject the scratch holds (``find_uproject`` — a composed scratch
    carries whichever substrate the active task declares), never from a
    hardcoded 'CraftBenchTemplate' name."""
    dir_ = Path(dir_)

    # ---- PHASE B: editor-target build (engine+project-stamped staleness) ----
    built_marker = dir_ / ".cb-built"
    if not os.environ.get("CB_UE_ROOT"):
        resolve_ue()  # side-effect sets CB_UE_ROOT
    ue_root_str = os.environ.get("CB_UE_ROOT")
    if not ue_root_str:
        log("  FAIL  no UE root for scratch build (set -UeRoot / CB_UE_ROOT)")
        return False
    # ENGINE|PROJECT stamp: an engine-only stamp let a recompose to a
    # DIFFERENT substrate skip the build — the scratch then held only the
    # previous substrate's module DLLs and the editor exited on startup
    # (2026-07-21: first graded ThirdPerson eval; .cb-built carried just the
    # UE root while Binaries/ held only CraftBenchTemplate DLLs). A legacy
    # engine-only marker mismatches the composite and forces one clean
    # rebuild, which is the safe direction.
    try:
        stamp_uproj = find_uproject(dir_)
    except FileNotFoundError as e:
        log(f"  FAIL  {e}")
        return False
    engine_stamp = f"{ue_root_str.strip()}|{stamp_uproj.stem}"
    marker_text = None
    if built_marker.exists():
        try:
            marker_text = built_marker.read_text(encoding="utf-8")
        except OSError:
            marker_text = ""
    action = _scratch_build_action(marker_text, engine_stamp)
    if action == "skip":
        return True  # already built against this engine + project
    if action == "clean":
        log("  ..    scratch was built against a different UE or substrate "
            "(or a pre-stamp marker) -> forcing a CLEAN rebuild")
        _clean_scratch_build_dirs(dir_, log=log)
        try:
            built_marker.unlink()
        except OSError:
            pass
    if action in ("build", "clean"):  # 'skip' already returned above
        try:
            uproj = find_uproject(dir_)
        except FileNotFoundError as e:
            log(f"  FAIL  {e}")
            return False
        ue_root = Path(ue_root_str)
        build = _build_script(ue_root)
        if not build.exists():
            log(f"  FAIL  build script not found under {ue_root}")
            return False
        # A running editor locks the shared Aura DLLs; stop it before the relink.
        # Scope it: a FOREIGN editor (e.g. unrealfeaturedev) also locks the junction'd
        # Aura DLLs, but we must not kill the user's editor — warn that the build may
        # fail (LNK1104) instead. CB_ALLOW_FOREIGN_EDITOR=1 overrides (kills ALL).
        running = _editor_running()
        if running:
            override = os.environ.get("CB_ALLOW_FOREIGN_EDITOR", "").lower() in ("1", "true", "yes")
            if foreign_editor() is not None and not override:
                log("  WARN  a foreign UnrealEditor is open (e.g. unrealfeaturedev) — it shares")
                log("        + locks the Aura DLLs; the scratch build may fail (LNK1104). Close")
                log("        it, or set CB_ALLOW_FOREIGN_EDITOR=1 to kill ALL editors.")
            elif override:
                log("  ..    stopping ALL editors (CB_ALLOW_FOREIGN_EDITOR override)")
                kill_by_image("UnrealEditor")
            else:
                log("  ..    stopping a running editor (it locks the shared Aura DLLs)")
                kill_craftbench_editors(log)
            time.sleep(4)
        log("  ..    building scratch editor target (~5-8 min)...")
        cmd = [
            # Editor target name is <GameModule>Editor == <uproject stem>Editor
            # for every CraftBench substrate (CraftBenchTemplateEditor,
            # ThirdPersonTemplateEditor, ...).
            str(build), f"{uproj.stem}Editor", _build_platform_token(),
            "Development", f"-project={uproj}",
            # -NoUBA: UE 5.8 enables Unreal Build Accelerator by default, but its
            # shared cross-run CAS crashes the build (access violation, exit
            # 0xC0000005) when a prior build was killed mid-flight and left it
            # "not gracefully shutdown". Run actions locally (UE 5.7 behaviour).
            # Mirrors tools/verify-single/layers/l1_build.py; CRAFTBENCH_ALLOW_UBA=1 opts back in.
            *([] if os.environ.get("CRAFTBENCH_ALLOW_UBA", "").strip() in ("1", "true", "True")
              else ["-NoUBA"]),
            # Cap parallel actions on RAM-constrained hosts to avoid UE 5.8 PCH
            # C3859 / paging exhaustion (same CRAFTBENCH_L1_MAX_PARALLEL knob as
            # the verifier's L1; default: no cap). Leading-int parse via l1_cap().
            *([f"-MaxParallelActions={l1_cap()}"] if l1_cap() else []),
            "-waitmutex",
        ]
        try:
            cp = subprocess.run(cmd, cwd=str(dir_))
        except (OSError, subprocess.SubprocessError) as e:
            log(f"  FAIL  scratch build could not start: {e}")
            return False
        if cp.returncode != 0:
            # A failed build leaves a partial/inconsistent Intermediate; an
            # incremental retry can then reuse stale objects and fail to LINK
            # (e.g. unresolved AbilityPoison/PreferredAbilityTag). Clear the build
            # dirs so the next attempt starts clean.
            log(f"  FAIL  scratch build failed (exit {cp.returncode}); clearing "
                "build dirs so the next attempt is clean")
            _clean_scratch_build_dirs(dir_, log=log)
            return False
        try:
            built_marker.write_text(engine_stamp, encoding="utf-8")  # stamp the engine
        except OSError:
            pass
        log("  OK    scratch editor target built")
    return True


def reset_drive_project(dir_: Path, paths: StackPaths, log=print) -> bool:
    """Mirror the template's Source/Content/Config back over the scratch (discarding
    the agent's edits) and DELETE the ``.cb-built`` marker so the next drive rebuilds.
    Keeps Plugins/ (whatever was staged there). The next build is INCREMENTAL when the engine is
    unchanged (fast — what ``cb headless`` relies on); but if the scratch was built
    against a DIFFERENT UE, the Binaries/Intermediate are wiped here so the rebuild is
    CLEAN (a stale-engine incremental rebuild fails to link). No-op if there is no
    playground. The 'managed scratch vs user -Project' safety is the CALLER's."""
    dir_ = Path(dir_)
    uproj = next(dir_.glob("*.uproject"), None) if dir_.is_dir() else None
    if uproj is None:
        log(f"  ..    no playground at {dir_} (nothing to clean)")
        return True
    # Engine-change check BEFORE we delete the marker: a plain incremental rebuild
    # over objects from a different UE reuses incompatible artifacts -> link errors.
    built_marker = dir_ / ".cb-built"
    if built_marker.exists():
        if not os.environ.get("CB_UE_ROOT"):
            resolve_ue()
        cur = (os.environ.get("CB_UE_ROOT") or "").strip()
        try:
            prev = built_marker.read_text(encoding="utf-8").strip()
        except OSError:
            prev = ""
        if cur and prev and prev != cur:
            log("  ..    scratch was built against a different UE -> clean reset")
            _clean_scratch_build_dirs(dir_, log=log)
    log(f"  ..    cleaning playground -> reverting Source/Content/Config to template: {dir_}")
    for d in ("Source", "Content", "Config"):
        s = paths.template_dir / d
        if s.exists():
            if not _mirror_tree(s, dir_ / d, delete_extras=True):
                log(f"  FAIL  clean of {d} failed")
                return False
    try:
        built_marker.unlink()
    except OSError:
        pass
    log("  OK    playground reset (rebuilds clean if the engine changed, else incremental)")
    return True


def _editor_running() -> bool:
    """True if an UnrealEditor (GUI/headless) process is running. psutil -> tasklist
    / pgrep. NOT UnrealEditor-Cmd (the L2 PIE image is a separate binary)."""
    try:
        import psutil  # type: ignore
        for p in psutil.process_iter(["name"]):
            n = (p.info.get("name") or "")
            if n in ("UnrealEditor", "UnrealEditor.exe"):
                return True
        return False
    except Exception:
        pass
    try:
        if IS_WINDOWS:
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq UnrealEditor.exe"],
                                 capture_output=True, text=True, timeout=15).stdout
            return "UnrealEditor.exe" in out
        cp = subprocess.run(["pgrep", "-x", "UnrealEditor"], capture_output=True, timeout=15)
        return cp.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# =========================================================================== #
# 6. invoke_bringup — bring the headless editor up and gate on readiness.      #
#    (was Invoke-Bringup's SIX-stage gate; five of those stages started the    #
#     private Aura product and went with it. Returns True iff STACK GREEN)     #
# =========================================================================== #

def editor_launch_args(ue, uproject, visible: bool = False) -> List[str]:
    """The headless Aura editor launch argv (the ONE place it is defined).

    ``visible=True`` (CB_VISIBLE) drops ONLY ``-RenderOffScreen`` so the editor
    renders to a real window. EVERYTHING else stays in ALL modes — in particular
    ``-AuraHeadless`` (it bootstraps Aura's tool bridge, NOT rendering; see
    tools/scripts/aura_smoke.py) and ``-unattended``/``-nosplash``/``-nopause``/
    ``-nosound`` (determinism / no modal prompts)."""
    args = [
        str(ue), str(uproject), "-RenderOffScreen", "-AuraHeadless", "-unattended",
        "-nosplash", "-nopause", "-nosound", "-DisablePlugins=Reflex", "-log",
    ]
    if visible:
        args.remove("-RenderOffScreen")
    return args


def _record_stack_ownership(uproject: Path, *, promote: bool, log=print) -> None:
    """Arm (``promote=False``) or promote (``promote=True``) the stack ownership
    manifest and (re-)arm the janitor watchdog. Best-effort in both directions —
    the guard must never turn a healthy bring-up into a failed one.

    Skipped entirely inside a TEST process: writing the machine-global
    ``runs/.stack-manifest.json`` and spawning a detached janitor are real
    effects on the operator's box, and three existing tests drive the real
    ``invoke_bringup`` (TestBringupFailFast / TestBringupToolchainGate).
    ``stack_guard.record_bringup`` itself stays ungated — the guard's own unit
    tests call it directly against a tempdir manifest, which is exactly right."""
    try:
        if kill_guard.in_test_process():
            return
        from aura_rig import janitor as _janitor
        from aura_rig import stack_guard as _stack_guard
        if not _stack_guard.guard_enabled():
            return
        if promote:
            _stack_guard.promote_to_green(uproject, log=log)
        else:
            _stack_guard.record_bringup_pending(uproject, log=log)
        _janitor.arm(log=log)  # idempotent: an incumbent holds the lock and exits
    except Exception as e:  # noqa: BLE001
        log(f"  WARN  stack-guard recording failed ({e.__class__.__name__}: "
            f"{e}) - startup reconciliation remains the backstop")


def invoke_bringup(uproject: Path, ue: Path, py_exe: str, py_pre: Sequence[str],
                   paths: StackPaths, *, restart_editor: bool = False,
                   log=print) -> bool:
    """Bring the headless editor up on <uproject> and gate on a REAL round-trip.

    WHAT THIS WAS, AND WHY IT IS ONE STAGE NOW (open-source release,
    2026-08-28). Until this release ``invoke_bringup`` was a SIX-stage gate,
    and five of those stages brought up the private Aura product rather than
    anything this benchmark measures: ``[1/6]`` a ``yarn local_dev`` vercel dev
    server on :3000, ``[2/6]`` a Playwright dev-browser on :9222 plus its CDP
    tab self-heal, ``[3/6]`` a rewrite of the private client's
    ``.mcp-config.json`` (and of that client's ``.env``), ``[4/6]`` the editor
    session store / entitlement step, and ``[5/6]`` a ``pnpm dev`` client on
    :3002 that SUPERVISED the editor. None of those components are part of this
    repository, so none of those stages could do anything here but fail slowly
    — see THIRD-PARTY.md §4. They were removed rather than stubbed.

    What is left is the one stage the published arms actually need: a headless
    ``UnrealEditor`` on the substrate with Epic's in-engine
    ``ModelContextProtocol`` server, gated on a full MCP ``initialize``
    exchange. That gate is :mod:`aura_rig.unreal_mcp_stack` — the SAME code
    path ``cb eval --model unreal-mcp`` uses, deliberately, so ``cb up`` and a
    graded drive can never disagree about what "ready" means. The stack.py
    principle it inherits is unchanged: readiness is a real round-trip, never a
    port probe.

    ``restart_editor`` maps to that helper's ``fresh``. It defaults False here
    because ``cb up`` exists to HOLD an editor across several hand-driven
    commands, so an already-ready one is accepted; the per-drive lanes ask for
    a fresh process themselves.

    ``py_exe`` / ``py_pre`` are kept in the signature: the CLI resolves and
    passes them positionally (``aura_rig.cb._Ctx.require_stack``) and still
    fails fast when no harness Python resolves. No stage below shells them any
    more — every stage that did was a node/product stage.

    Returns True iff the editor came up ready (STACK GREEN).
    """
    # ARM OWNERSHIP *BEFORE* THE FIRST PROCESS STARTS (gap found live
    # 2026-08-07). The launch below is a real, detached, multi-GB process; a
    # hard-stop / crash / closed console in the next ~1-10 minutes used to
    # leave it running with NO manifest and NO janitor, because ownership was
    # recorded only at STACK GREEN. A PENDING manifest here makes an
    # interrupted bring-up an ORPHAN like any other — reaped by the janitor
    # within a poll, or by the next cb's reconciliation.
    _record_stack_ownership(uproject, promote=False, log=log)

    # NO REAL EDITOR LAUNCH FROM A TEST PROCESS. The launch below is a real,
    # detached, multi-GB UnrealEditor that blocks on a boot timeout, and the
    # seams a caller can patch (`test_up`, `wait_up`, `start_detached`) all live
    # on THIS module while the launch itself lives in `unreal_mcp_stack` -- so a
    # unit test that stubs the old seams still reaches the real process and
    # HANGS for the full timeout. Found exactly that way: the suite stalled on
    # `test_kill_guard.TestBringupArmsOwnershipEarly` after the 2026-08-28 cut
    # reduced this function to the one editor stage. Same doctrine as
    # `kill_guard`'s refusal of real kills from a test process, and the same
    # fail-safe direction: an ambiguous process is a test. `CB_ALLOW_REAL_KILLS`
    # is the deliberate human override, since a REPL that has imported unittest
    # is the one legitimate case for both.
    #
    # Deliberately AFTER the pending arm above: an interrupted bring-up must
    # still be an owned orphan, and the ownership contract is what the tests
    # around this line assert.
    if kill_guard.in_test_process() and not kill_guard.env_true("CB_ALLOW_REAL_KILLS"):
        log("STACK: refusing a real editor launch from a test process "
            "(set CB_ALLOW_REAL_KILLS=1 to override).")
        return False

    # Local import: unreal_mcp_stack imports THIS module at its top level, so a
    # module-level import here would be circular. Same shape as the janitor /
    # stack_guard imports in _record_stack_ownership.
    from aura_rig import unreal_mcp_stack as _ums

    log("\n=== [1/1] headless editor + Epic MCP server ===")
    ok = _ums.ensure_unreal_mcp_editor(Path(uproject), Path(ue),
                                       fresh=restart_editor, log=log)

    log("\n" + "=" * 60)
    log(f"STACK: editor-mcp={_ums.resolve_url()} ready={ok}")
    if not ok:
        # NB: a NOT-GREEN return deliberately LEAVES the pending manifest in
        # place. Whatever did come up is real and must stay owned; a
        # same-process retry reuses the generation (record_bringup_pending),
        # and a dead owner is an orphan either way.
        log("STACK NOT GREEN. Fix the FAIL items above, then re-run.")
        return False
    log("STACK GREEN (headless editor ready).")
    # Ownership + auto-recovery (owner mandate 2026-08-07): PROMOTE the pending
    # manifest armed above to green, keeping the generation the janitor is
    # already watching. A wrapper that dies without teardown then still gets
    # the full stop_stack from the janitor or the next cb invocation, instead
    # of the editor leaking multiple GB of commit overnight.
    _record_stack_ownership(uproject, promote=True, log=log)
    return True


def ensure_drive_editor(uproject: Path, ue: Path, paths: StackPaths, *,
                        restart: bool, verdict_subject: Optional[str] = None,
                        log=print) -> bool:
    """Bring the AURA-LANE drive editor up on ``uproject`` and gate it on :30010.

    NOT REACHABLE FROM A PUBLISHED ARM, AND KEPT ANYWAY. The only caller is
    ``run.py --defer-editor`` (``_start_drive_editor``), which exists so the
    aura-mcp lane can start its editor AFTER run.py's fairness hide — an
    Aura-staged editor force-loads every ``.umap`` and the hide's renames then
    die on WinError 5 (11 of 20 aura-mcp cells lost to it on 2026-08-23,
    against 0 of 21 on unreal-mcp). ``cb eval --model aura-mcp`` refuses before
    it can get here (``cb.py`` ``_refuse_unroutable_model``), and the published
    editor lane is :func:`aura_rig.unreal_mcp_stack.ensure_unreal_mcp_editor`,
    which ``invoke_bringup`` above uses. Read THIRD-PARTY.md §4 first: :30010
    is served by the stock RemoteControl plugin, which reaches the substrate
    only as a DEPENDENCY of Aura's plugin — and that plugin is not part of this
    release, so on a stock open-source checkout this function launches an
    editor that never binds and reports the FAIL below. That is the honest
    outcome; a green verdict here would be the lie.

    WHAT WAS REMOVED WITH THE PRIVATE PRODUCT (2026-08-28). This function used
    to carry four more things, all of which spoke to the cut client on :3002:
    the graceful restart THROUGH that client (``/api/headless/shutdown`` ->
    ``/api/headless/launch``) with its :3002-down kill+relaunch fallback; the
    ``/api/tool-execute`` tool-ready gate that was the only reliable
    drive-readiness signal; that gate's account/entitlement short-circuit; and
    the ``[6/6]`` ``/api/mcp-tools`` catalog poll with its ":3000 died
    mid-bring-up" heal. With no client there is nothing to restart through, no
    tool path to round-trip, and no catalog to count, so the gate is the
    :30010 bind alone.

    Still carried, because they are ours and not the product's: the
    CB_ALLOW_FOREIGN_EDITOR cross-folder guard, the project marker that makes
    the restart project-aware, :func:`editor_boot_timeout`'s DDC-scaled window,
    and the process-died-before-binding bail.

    RAISES ``RuntimeError`` when a FOREIGN editor holds :30010 (refusing to
    hijack another folder's session); every other failure returns False after
    printing its own named reason. ``verdict_subject`` names the subject of the
    NOT-GREEN line (the bring-up says STACK, a deferred drive says DRIVE
    EDITOR).
    """
    # editor (PROJECT-AWARE restart via the marker file)
    cur_proj = ""
    if paths.editor_marker.exists():
        try:
            cur_proj = paths.editor_marker.read_text(encoding="utf-8-sig").strip().lstrip("﻿")
        except OSError:
            cur_proj = ""
    target = str(uproject)
    # CROSS-FOLDER GUARD: refuse to hijack/kill an editor from ANOTHER folder (e.g.
    # the user's ../unrealfeaturedev dev editor). craftbench shares the editor RC port
    # :30010 + the single .Aura session, so the two can't run at once — restarting or
    # launching here would steal :30010 and clobber the session. Abort with a clear
    # message instead. Override with CB_ALLOW_FOREIGN_EDITOR=1 (you accept the conflict).
    if os.environ.get("CB_ALLOW_FOREIGN_EDITOR", "").lower() not in ("1", "true", "yes"):
        fe = foreign_editor()
        if fe is not None:
            fpid, fcl = fe
            fproj = next((t for t in fcl.split() if t.endswith(".uproject")), "")
            log(f"  FAIL  a non-CraftBench UnrealEditor is running (pid={fpid}"
                + (f", {fproj}" if fproj else "") + ")")
            log("        — it holds :30010 + the shared Aura session. Close that editor")
            log("        (e.g. another project's Aura editor) before running craftbench,")
            log("        or set CB_ALLOW_FOREIGN_EDITOR=1 to override (accepts the conflict).")
            raise RuntimeError(
                f"foreign UnrealEditor running (pid={fpid}); refusing to hijack :30010 / the "
                "shared Aura session — close it or set CB_ALLOW_FOREIGN_EDITOR=1")
    boot_timeout = editor_boot_timeout(uproject)
    if boot_timeout > 480:
        log(f"  ..    cold DerivedDataCache — first editor boot compiles shaders; "
            f"extending the bind wait to {boot_timeout // 60} min "
            "(CB_EDITOR_BOOT_TIMEOUT overrides)")
    # A restart is needed when forced (--restart-editor / per-drive isolation) or
    # when the open editor is on the WRONG project.
    need_restart = restart or (test_up(30010) and cur_proj != target)
    if need_restart:
        if test_up(30010) and cur_proj != target:
            log("  ..    editor open on a different project; restarting on the target")
        kill_craftbench_editors(log)  # scoped: spare a foreign editor
        # Verify the kill landed + reap mutex-holding children (replaces a
        # blind sleep(4) that let RequestExit zombies survive into the relaunch).
        ensure_editor_dead(None, grace_s=2.0, log=log)
        if test_up(30010):
            # ADOPTING IT WOULD BE THE WORST OUTCOME. A caller asking for a
            # restart is asking to discard the previous cell's in-editor state;
            # an old editor that survived every escalation and still serves
            # :30010 is exactly that state, so name the failure instead of
            # treating the live port as success. (The old code could not reach
            # this: it restarted THROUGH the client, whose launch route
            # re-adopted whatever process answered.)
            log("  FAIL  :30010 still answers after the scoped reap — the old "
                "editor survived every escalation")
            log(f"\n{verdict_subject or 'STACK'} NOT GREEN (old editor would not die).")
            return False
    elif test_up(30010):
        log(f"  OK    editor :30010 up (project: {cur_proj})")
        return True

    _visible = env_flag("CB_VISIBLE")
    log(f"  ..    launching {'VISIBLE' if _visible else 'headless'} editor on "
        f"{uproject} (detached; warm-up ~1-3min)")
    eargs = editor_launch_args(ue, uproject, visible=_visible)
    # Editor launched directly (not a node shim) — detached + hidden.
    start_detached(eargs, cwd=paths.template_dir,
                   log_path=paths.log / "cb_editor.out.log")
    try:
        paths.editor_marker.write_text(target, encoding="utf-8")
    except OSError:
        pass
    # Wait scaled to DDC warmth (cold first boot compiles shaders for many
    # minutes) but bail early if the process DIED (crash) instead of sitting
    # out the whole window on a dead editor.
    _bind_end = time.time() + boot_timeout
    while time.time() < _bind_end:
        if test_up(30010):
            log("  OK    editor :30010 came up")
            return True
        if not count_image("UnrealEditor"):
            log("  FAIL  editor process exited before binding :30010 — "
                "startup crash (see cb_editor.out.log; run `cb doctor`)")
            log(f"\n{verdict_subject or 'STACK'} NOT GREEN (editor crashed on startup).")
            return False
        time.sleep(5)
    log(f"  FAIL  editor :30010 did not bind within {boot_timeout}s "
        "(process alive but not ready — see cb_editor.out.log)")
    log("        :30010 is RemoteControl, which reaches the project only as a "
        "dependency of Aura's")
    log("        plugin — absent from this release, so this is the EXPECTED "
        "outcome here. The")
    log("        published editor lane is `cb eval --model unreal-mcp`; see "
        "THIRD-PARTY.md §4.")
    log(f"\n{verdict_subject or 'STACK'} NOT GREEN (editor :30010 down).")
    return False


def shutdown_drive_editor(*, log=print) -> bool:
    """Stop the drive editor and VERIFY it died. Never raises.

    It used to POST ``/api/headless/shutdown`` to the private client on :3002
    FIRST, and that was not politeness: that client SUPERVISED the headless
    editor and respawned a bare kill, so the graceful request was what made the
    death stick. Nothing supervises the editor in this release — the client is
    not part of it — so the reap IS the shutdown, and the ``client_url``
    parameter that addressed it is gone.

    :func:`ensure_editor_dead` then force-kills the RequestExit zombie UE 5.8
    leaves behind (scoped — a foreign editor is structurally excluded). Same
    ``always_sweep`` as ``run_graded._stop_editor_for_build`` runs before its
    L1 build.

    ``old_pids`` is deliberately NOT passed: a pid-scoped reap would spare
    exactly the process the caller needs gone if anything did respawn one.
    """
    return ensure_editor_dead(None, grace_s=5.0, always_sweep=True, log=log)


# =========================================================================== #
# 7. Teardown — stop_stack.                                                    #
#    (ports cb.ps1 'down')                                                      #
# =========================================================================== #

def stop_stack(log=print) -> None:
    """Full teardown: reap CraftBench's editors and the UE helper processes.

    IT USED TO BE SUPERVISOR-FIRST, AND NOW THERE IS NO SUPERVISOR. The private
    client on :3002 supervised the headless editor and RESPAWNED a bare kill,
    so this function killed the three server ports (3000 vercel / 3002 client /
    9222 dev-browser) first, slept, and only then force-killed the UE images —
    killing the editor before :3002 was futile. It also asked the dev-browser's
    Chromium to close gracefully first, so its persistent profile was written
    clean (a TerminateProcess'd Chromium greets the next headed launch with a
    "Restore pages?" bubble). None of those three services exist in this
    release, so the ordering they forced is gone with them and the editor reap
    is the whole teardown. What that actually reaps today is the unreal-mcp
    lane's resident headless editor and the Live Coding console holding UE's
    build lock — which is exactly what ``cb eval --teardown`` wants.

    Gated at ENTRY (not just per-kill): a refusal that let the sequence start
    would tear down half a bench before the first ``_kill_permitted`` fired.
    Refusals are audited with ``reason=REFUSED(...)``; the overrides are
    ``CB_ALLOW_REAL_KILLS=1`` (test process) and ``CB_ALLOW_STACK_TAKEOVER=1``
    (another live owner)."""
    if not _kill_permitted("stack (editors + UE helpers)", "stop_stack"):
        log("  ..    stop_stack REFUSED by the kill guard (see "
            "runs/.kill-audit.log; CB_ALLOW_REAL_KILLS=1 / "
            "CB_ALLOW_STACK_TAKEOVER=1 override) — nothing was stopped.")
        return
    log("Stopping headless stack (editor + UE helper processes)...")
    kill_craftbench_editors(log)  # scoped: never reap a FOREIGN editor (e.g. unrealfeaturedev)
    # Generation-aware ORPHAN SWEEP (owner mandate 2026-08-07, scenario 7):
    # replaces the old blanket kill_by_image("UnrealEditor-Cmd",
    # "LiveCodingConsole", "CrashReportClient"). Editors/-Cmd are killed only
    # on a COMMAND-LINE cb path-marker match (a stray headless editor on the
    # repo project held 3.7 GB for 6+ hours; a FOREIGN project's -Cmd was
    # previously reaped by the blanket); the two helper images keep the
    # no-foreign-editor gate from ensure_editor_dead. Enumeration-blind hosts
    # fall back to the legacy blanket trio inside the sweep (fail-open).
    try:
        from aura_rig import stack_guard as _stack_guard
        _stack_guard.orphan_sweep(log=log)
        # MCP stdio servers are NOT in the UE family, so the sweep above
        # cannot see them -- and measured 2026-08-24, twenty-six of them
        # held 11.75 GB of COMMIT with no stack up at all, enough to put
        # the box under envgate's floor and turn a discriminate sweep's
        # first L1 into a recorded SUBMISSION failure. Gated on a DEAD
        # parent, so a live owner keeps its own children.
        _stack_guard.mcp_orphan_sweep(log=log)
        _stack_guard.clear_manifest(log=log)  # no stack -> nothing to own
    except Exception:  # noqa: BLE001 — teardown must finish no matter what
        kill_by_image("UnrealEditor-Cmd", "LiveCodingConsole", "CrashReportClient")
    log("  stopped editor + Live Coding console (engine free for other builds).")


__all__ = [
    "StackPaths",
    "resolve_harness_py",
    "resolve_ue",
    "load_aura_env",
    "env_flag",
    "editor_launch_args",
    "test_up",
    "wait_up",
    "start_detached",
    "kill_port_owner",
    "kill_by_image",
    "count_image",
    "kill_craftbench_editors",
    "ensure_editor_dead",
    "get_drive_project_dir",
    "initialize_drive_project",
    "reset_drive_project",
    "invoke_bringup",
    "ensure_drive_editor",
    "shutdown_drive_editor",
    "stop_stack",
]
