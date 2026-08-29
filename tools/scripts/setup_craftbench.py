#!/usr/bin/env python3
"""setup_craftbench.py - the ONE setup script a new team member runs right after clone.

Usage (from anywhere; the script resolves the repo root from its own location):

    py -3.12 tools/scripts/setup_craftbench.py            # full report + unit tests
    py -3.12 tools/scripts/setup_craftbench.py --no-tests # skip the unit-test phase
    py -3.12 tools/scripts/setup_craftbench.py --json     # machine summary on stdout
    py -3.12 tools/scripts/setup_craftbench.py --full     # + smoke-grade the t0 reference (~7 min, needs UE 5.8)
    py -3.12 tools/scripts/setup_craftbench.py --add-path # + append the Python Scripts dir to the USER Path (Windows)
    py -3.12 tools/scripts/setup_craftbench.py --strict   # repo unit-test failures also flip the exit code
    py -3.12 tools/scripts/setup_craftbench.py --verbose  # list every .env key (default: set + required-missing only)

    # or via the thin root wrappers (they locate a python and forward all args):
    .\\setup.ps1 [--no-tests] [--json] [--full] [--add-path] [--strict] [--verbose]   # Windows PowerShell
    ./setup.sh  [--no-tests] [--json] [--full] [--strict] [--verbose]                # git-bash / macOS / Linux

Phases (each prints plain PASS/WARN/FAIL lines - no emoji, cp1252-safe):
  1. Prereqs   python / git / tar (grade tier), claude CLI (baseline, WARN-only),
               UE 5.8 (WARN if absent: grade tier blocked).
  2. Config    copy .env.example -> .env when .env is absent (announced write);
               condensed per-key report - set + required-missing keys (names only,
               NEVER values; --verbose lists all); target-tier inference.
  3. PATH      pip install -e tools/run-agent (the `cb` console script; announced,
               idempotent), then verify `cb` resolves PATH-wide; the repo-root
               shims (.\\cb / ./cb) are the no-install fallback.
  4. Tests     tools/verify-single/tests + tools/coverage/tests via unittest discover;
               tools/run-agent/tests only when no live run holds runs/.live-run.lock.
  5. Readiness `cb doctor` in-process (aura_rig.doctor) - THE per-tier authority.
  6. Summary   per-tier READY/blocked table (canonical cumulative tiers:
               grade-only / baseline, matching cb doctor); blocked tiers get
               unblock>/then> steps, READY tiers get run now>.

TWO TIERS, NOT THREE (public release): this harness used to report a third
"full-rig" tier whose job was to provision a private product stack for the
`aura-mcp` arm - a private UE plugin checkout, two local services, and an
entitled account. That arm stays dispatchable and documented, but none of its
bring-up machinery ships in this repository, so setup reports only the two
tiers a clone of it can actually reach: grade-only and baseline. Everything
the old tier needed (its credentials, its private clone step, its
`cb bootstrap` repairs) was removed outright rather than left as a branch that
fails halfway through.

Safety: stdlib-only, py 3.10+, idempotent, read-only except the announced writes:
the .env copy, the `pip install -e tools/run-agent` console script, --add-path's
USER-Path append (opt-in), and --full's short build workdir (opt-in; safe to
delete afterwards).
Exit code: TIER-SCOPED - 0 unless a FAIL blocks a tier at or below the target
tier inferred from real provisioning signals (a non-placeholder agent key ->
baseline; else grade-only). Repo unit-test failures are reported with names + log + rerun
command but flip the exit code only under --strict. The phase-5 doctor verdict
is advisory (informational only - it never gates this script's exit code).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_AGENT_DIR = REPO_ROOT / "tools" / "run-agent"
IS_WINDOWS = os.name == "nt"

T0_TASK = "tasks/cpp/t0-sanity-log-on-beginplay/task.md"
T0_REFERENCE = "tasks/cpp/t0-sanity-log-on-beginplay/reference"

# --------------------------------------------------------------------------- #
# Output plumbing. In --json mode the human report goes to stderr and stdout   #
# carries ONLY the JSON summary. Plain ASCII status words; errors='replace'    #
# keeps cp1252 consoles from crashing on any stray non-ASCII (paths, doctor).  #
# --------------------------------------------------------------------------- #

_JSON_MODE = False
_CHECKS: list = []  # [{phase, id, status, detail}] - the machine summary rows


def _out():
    return sys.stderr if _JSON_MODE else sys.stdout


def say(line: str = "") -> None:
    print(line, file=_out(), flush=True)


def record(phase: str, cid: str, status: str, detail: str, hint: str = "") -> None:
    """One report line + one machine-summary row. status: PASS/WARN/FAIL/SKIP/INFO."""
    _CHECKS.append({"phase": phase, "id": cid, "status": status, "detail": detail})
    say(f"{status:<4}  {cid:<14} {detail}")
    if hint:
        for h in hint.splitlines():
            say(f"      {h}")


def header(n: int, total: int, title: str) -> None:
    say("")
    say(f"--- [{n}/{total}] {title} ---")


# --------------------------------------------------------------------------- #
# Tiny .env parsing (names + set-ness only - values are never printed).        #
# --------------------------------------------------------------------------- #

# Unedited .env.example placeholder sentinels count as "not set".
# KEEP IN SYNC with tools/run-agent/aura_rig/doctor.py::_PLACEHOLDERS - the two
# dicts must stay identical (this script is stdlib-only and cannot import it).
# The public release dropped the two credential keys of the removed private
# tier from BOTH dicts; if doctor.py still carries them, it is the one that is
# behind, not this file.
_PLACEHOLDERS = {
    "ANTHROPIC_API_KEY": ("sk-ant-xxxx", "sk-ant-xxx"),
    "OPENROUTER_API_KEY": ("sk-or-xxxx",),
}

# Which tier needs each .env.example key (True = a tier is BLOCKED without it).
# A key with no row here renders as plain "optional" - that is the deliberate
# fallback, so rows for keys that no longer have a tier are deleted, not kept
# with a dangling tier name.
_KEY_NOTES = {
    "ANTHROPIC_API_KEY": ("baseline tier requires it", True),
    "OPENROUTER_API_KEY": ("baseline openrouter:<model> backend only", False),
    "OPENROUTER_BASE_URL": ("optional openrouter URL override", False),
    "CRAFTBENCH_ALLOW_UBA": ("optional; UBA (Unreal Build Accelerator) off by default", False),
    "CRAFTBENCH_L1_MAX_PARALLEL": ("optional; set 2-4 on a ~32 GB box to avoid C3859 (MSVC out-of-memory)", False),
    "CB_CRAFTBENCH": ("optional; auto = this repo root", False),
    "CB_UE_ROOT": ("grade tier; auto = the Epic default UE_5.8 install", False),
    "CB_PY": ("optional; auto-resolved python launcher", False),
    "CB_UPROJECT": ("optional; auto = the substrate .uproject", False),
    "CB_ROOT": ("optional machine root for workdirs (auto = C:\\cb); MUST stay SHORT "
                "on Windows - a long root hits the 260-char MAX_PATH mid-build", False),
    "CB_DRIVE_PROJECT": ("optional; cb headless/view on your own project", False),
    "CB_TMP": ("optional scratch/log dir override", False),
    "CB_PROXY_INJECT_CACHE": ("optional", False),
}


def _dotenv_value(raw: str) -> str:
    """Dotenv semantics (mirrors aura_rig.stack._dotenv_value — this script is
    zero-dependency by design, so the 6 lines are duplicated, not imported):
    a double-quoted value ends at its closing quote; an unquoted value ends at
    the first whitespace-then-# inline comment."""
    v = raw.strip()
    if v.startswith('"'):
        end = v.find('"', 1)
        if end != -1:
            return v[1:end]
        return v.strip('"')
    return re.split(r"\s#", v, maxsplit=1)[0].strip()


def parse_env_file(path: Path) -> dict:
    """{KEY: value} from uncommented KEY=value lines (dotenv-parsed)."""
    out: dict = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if m and not line.lstrip().startswith("#"):
            key, val = m.group(1), _dotenv_value(m.group(2))
            if key not in out:
                out[key] = val
    return out


def example_keys(path: Path) -> list:
    """Ordered, de-duped key names declared in .env.example (commented or not)."""
    keys: list = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return keys
    for line in text.splitlines():
        m = re.match(r"^#?([A-Z][A-Z0-9_]*)=", line.strip())
        if m and m.group(1) not in keys:
            keys.append(m.group(1))
    return keys


def _is_placeholder(key: str, value: str) -> bool:
    for ph in _PLACEHOLDERS.get(key, ()):
        if value == ph or value.startswith(ph):
            return True
    return False


def key_status(key: str, dotenv: dict) -> str:
    """'set' | 'set(env)' | 'placeholder' | 'missing' - presence only, never the value."""
    val = dotenv.get(key, "")
    if val:
        return "placeholder" if _is_placeholder(key, val) else "set"
    env_val = os.environ.get(key, "")
    if env_val and not _is_placeholder(key, env_val):
        return "set(env)"
    return "missing"


# --------------------------------------------------------------------------- #
# UE 5.8 resolution - pure/stdlib mirror of aura_rig.stack (CB_UE_ROOT env ->  #
# .env CB_UE_ROOT -> Epic default -> discovered UE_5.*). Never exports env.    #
# --------------------------------------------------------------------------- #

def _ue_editor_subpath() -> Path:
    if IS_WINDOWS:
        return Path("Engine") / "Binaries" / "Win64" / "UnrealEditor.exe"
    if sys.platform == "darwin":
        return (Path("Engine") / "Binaries" / "Mac" / "UnrealEditor.app"
                / "Contents" / "MacOS" / "UnrealEditor")
    return Path("Engine") / "Binaries" / "Linux" / "UnrealEditor"


def resolve_ue(dotenv: dict):
    """(root, version_string) for the first root holding the editor binary, else (None, '')."""
    roots: list = []
    for src in (os.environ.get("CB_UE_ROOT"), dotenv.get("CB_UE_ROOT")):
        if src:
            roots.append(Path(src))
    if IS_WINDOWS:
        epic = Path(r"C:\Program Files\Epic Games")
    elif sys.platform == "darwin":
        epic = Path("/Users/Shared/Epic Games")
    else:
        epic = Path("/opt/unreal-engine")
    roots.append(epic / "UE_5.8")
    try:
        if epic.exists():
            roots += sorted(
                (d for d in epic.iterdir() if d.is_dir() and d.name.startswith("UE_5.")),
                key=lambda d: d.name, reverse=True)
    except OSError:
        pass
    sub = _ue_editor_subpath()
    for root in roots:
        if (root / sub).exists():
            ver = ""
            try:
                bv = json.loads((root / "Engine" / "Build" / "Build.version")
                                .read_text(encoding="utf-8"))
                ver = f"{bv.get('MajorVersion', '?')}.{bv.get('MinorVersion', '?')}"
            except (OSError, ValueError):
                pass
            return root, ver
    return None, ""


# --------------------------------------------------------------------------- #
# Phase 1 - prerequisites.                                                     #
# --------------------------------------------------------------------------- #

def phase_prereqs(dotenv: dict) -> dict:
    header(1, _TOTAL, "Prerequisites")
    facts: dict = {}

    v = sys.version_info
    ver = f"{v.major}.{v.minor}.{v.micro}"
    if v >= (3, 11):
        record("prereqs", "python", "PASS",
               f"{ver} ({sys.executable}) (3.12 recommended)")
        facts["python"] = True
    elif v[:2] == (3, 10):
        record("prereqs", "python", "WARN",
               f"{ver} - verifier core runs, but the cb harness install requires 3.11+ "
               "(tools/run-agent/pyproject.toml)",
               "Install Python 3.11+ (3.12 recommended) so `py -3.12 --version` works, then re-run.")
        facts["python"] = True
    else:
        record("prereqs", "python", "FAIL",
               f"{ver} - CraftBench needs Python 3.11+ (3.12 recommended)",
               "Install Python 3.11+ (3.12 recommended) so `py -3.12 --version` works, then re-run.")
        facts["python"] = False

    for tool, tier, blocking in (("git", "grade tier", True), ("tar", "grade tier", True)):
        found = shutil.which(tool)
        if found:
            record("prereqs", tool, "PASS", found)
        else:
            record("prereqs", tool, "FAIL", f"not on PATH - {tier} blocked",
                   "Git for Windows provides both git and tar; Win10 1803+/11 also ship tar.exe.")
        facts[tool] = bool(found)

    claude = (shutil.which("claude") or shutil.which("claude.cmd")
              or shutil.which("claude.exe"))
    if claude:
        record("prereqs", "claude-cli", "PASS", claude)
    else:
        record("prereqs", "claude-cli", "WARN",
               "not on PATH - only the baseline agent tier (claude-p/openrouter) needs it",
               "Install Claude Code and add its dir to PATH. Grading needs no agent at all.")
    facts["claude"] = bool(claude)

    ue_root, ue_ver = resolve_ue(dotenv)
    if ue_root is None:
        record("prereqs", "ue-5.8", "WARN",
               "UnrealEditor not found - the grade-only tier is blocked until UE 5.8 is installed",
               "Install UE 5.8 via the Epic Games Launcher (default: C:\\Program Files\\Epic "
               "Games\\UE_5.8; ~100 GB disk, allow hours - one-time), or set CB_UE_ROOT in "
               ".env / the environment.")
    elif ue_ver and ue_ver != "5.8":
        record("prereqs", "ue-5.8", "WARN",
               f"found UE {ue_ver} at {ue_root} - the repo is pinned to UE 5.8",
               "Point CB_UE_ROOT at a UE 5.8 install (switching engines is pure config).")
    else:
        record("prereqs", "ue-5.8", "PASS", f"{ue_root}" + (f" (Build.version {ue_ver})" if ue_ver else ""))
    facts["ue_root"] = str(ue_root) if ue_root else None
    facts["ue_version"] = ue_ver
    return facts


# --------------------------------------------------------------------------- #
# Phase 2 - config (.env copy + per-key report + target-tier inference).       #
# --------------------------------------------------------------------------- #

def phase_config(verbose: bool = False) -> dict:
    header(2, _TOTAL, "Config (.env)")
    env_path = REPO_ROOT / ".env"
    example_path = REPO_ROOT / ".env.example"
    out: dict = {"created": False, "keys": {}, "extra_keys": [],
                 "target_tier": "grade-only"}

    if not example_path.exists():
        record("config", ".env.example", "FAIL",
               "missing at the repo root - incomplete clone?",
               "`git checkout -- .env.example` (it is the authoritative key list).")
        return out

    if not env_path.exists():
        try:
            shutil.copyfile(example_path, env_path)
            out["created"] = True
            record("config", ".env", "PASS",
                   "WROTE .env (copied from .env.example - one of the announced writes)",
                   "Open .env and fill the keys for your tier; grade-only needs none.")
        except OSError as e:
            record("config", ".env", "FAIL", f"could not copy .env.example -> .env ({e})")
            return out
    else:
        record("config", ".env", "PASS", ".env present at the repo root (left untouched)")

    dotenv = parse_env_file(env_path)
    keys = example_keys(example_path)

    def _s(k: str) -> bool:
        return key_status(k, dotenv) in ("set", "set(env)")

    # Target tier from REAL provisioning signals (mirrors doctor.provisioned_tier;
    # never mere .env presence - this script creates .env on every fresh clone).
    # It scopes this script's exit code: only FAILs at/below it flip the exit.
    # Two tiers only - the private-stack tier and its CB_GENIUS/plugins-checkout
    # signals were removed with the lane they provisioned.
    if _s("ANTHROPIC_API_KEY") or _s("OPENROUTER_API_KEY"):
        target = "baseline"
    else:
        target = "grade-only"
    out["target_tier"] = target
    record("config", "target-tier", "INFO",
           f"{target} (inferred from a real agent key, not mere .env presence; "
           "scopes this script's exit code)")

    say("      per-key status (names only - values are never printed):")
    missing_required = []
    optional_unset = 0
    for key in keys:
        status = key_status(key, dotenv)
        note, required = _KEY_NOTES.get(key, ("optional", False))
        out["keys"][key] = status
        shown = {"set": "set", "set(env)": "set (shell env)",
                 "placeholder": "PLACEHOLDER", "missing": "MISSING"}[status]
        interesting = (status in ("set", "set(env)")
                       or (required and status in ("missing", "placeholder")))
        if verbose or interesting:
            say(f"        {key:<27} {shown:<16} {note}")
        else:
            optional_unset += 1
        if required and status in ("missing", "placeholder"):
            missing_required.append((key, note))
    if not verbose and optional_unset:
        say(f"        {optional_unset} optional keys unset "
            "(run with --verbose to list all; --json has everything)")
    for key, note in missing_required:
        record("config", key, "WARN", f"not set - {note}")
    extra = sorted(k for k in dotenv if k not in keys)
    if extra:
        out["extra_keys"] = extra
        n = len(extra)
        record("config", "extra-keys", "INFO",
               f"{n} .env key{'s' if n != 1 else ''} not in .env.example - names "
               "withheld from the shareable report; see --json")

    say("      safe to share: this report names expected keys but never values")
    return out


# --------------------------------------------------------------------------- #
# Phase 3 - PATH check for the cb launcher (report-only, never modifies PATH). #
# --------------------------------------------------------------------------- #

def _bash_path(p: Path) -> str:
    s = str(p).replace("\\", "/")
    m = re.match(r"^([A-Za-z]):(/.*)$", s)
    return f"/{m.group(1).lower()}{m.group(2)}" if m else s


def _append_user_path_windows(scripts_dir: str) -> str:
    """Append <scripts_dir> to the USER Path (HKCU\\Environment) and broadcast
    WM_SETTINGCHANGE so NEW shells pick it up. Returns 'added' | 'already
    present' | an error string. Never touches the SYSTEM Path; reversible by
    removing the entry in 'Edit environment variables for your account'."""
    import ctypes
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                            winreg.KEY_READ | winreg.KEY_WRITE) as key:
            try:
                current, kind = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current, kind = "", winreg.REG_EXPAND_SZ
            norm = os.path.normcase(os.path.normpath(scripts_dir))
            if any(os.path.normcase(os.path.normpath(p)) == norm
                   for p in current.split(";") if p.strip()):
                return "already present"
            new = (current.rstrip(";") + ";" if current else "") + scripts_dir
            winreg.SetValueEx(key, "Path", 0, kind, new)
    except OSError as e:
        return f"failed: {e.__class__.__name__}: {e}"
    try:  # tell Explorer so shells launched from it inherit the new Path
        HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG = 0xFFFF, 0x1A, 0x2
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment",
            SMTO_ABORTIFHUNG, 5000, ctypes.byref(ctypes.c_ulong()))
    except Exception:  # noqa: BLE001 — broadcast is best-effort
        pass
    return "added"


def phase_path(add_path: bool = False) -> bool:
    header(3, _TOTAL, "cb command (pip console script + PATH)")
    # (a) Editable-install the `cb` console script (tools/run-agent/pyproject.toml).
    # Idempotent + announced; the SECOND write this script makes (after .env copy).
    # An editable install never copies the source tree - the rig keeps resolving
    # skills/tasks/driver files from this checkout.
    # The package core is stdlib-only; the editable install exists to put the
    # `cb` console script on PATH without copying the source tree.
    say("      pip install -e tools/run-agent (console script `cb`; "
        "editable, idempotent)...")
    try:
        cp = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e",
             str(RUN_AGENT_DIR), "--quiet"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=300)
        if cp.returncode == 0:
            record("path", "pip-install-cb", "PASS",
                   "console script `cb` installed (pip install -e tools/run-agent)")
        else:
            err_lines = [ln for ln in (cp.stderr + cp.stdout).splitlines() if ln.strip()]
            if any("externally-managed-environment" in ln for ln in err_lines):
                # PEP 668: Homebrew/Debian system Pythons refuse global pip installs.
                hint = ("PEP 668: this Python is externally managed and refuses global pip "
                        "installs. Recovery:\n"
                        "  python3 -m venv .venv && .venv/bin/pip install -e tools/run-agent\n"
                        "(the repo-root ./cb shim keeps working either way - no install needed).")
            else:
                hint = ("Not blocking: the repo-root shim needs no install - run  .\\cb <command>  "
                        "(PowerShell/cmd) or  ./cb <command>  (bash) from the repo root.")
            record("path", "pip-install-cb", "WARN",
                   f"pip install -e failed (exit {cp.returncode}) - last output lines below",
                   "\n".join(err_lines[-10:] + [hint]))
    except (OSError, subprocess.TimeoutExpired) as e:
        record("path", "pip-install-cb", "WARN", f"pip unavailable ({e.__class__.__name__})",
               "Not blocking: use the repo-root shim  .\\cb <command>  /  ./cb <command>.")

    # (b) Does `cb` now resolve PATH-wide? Windows' implicit-cwd lookup can fake
    # a PASS from the repo-root shim (.\\cb.CMD), which PowerShell will NOT run
    # bare. Two guards: set NoDefaultCurrentDirectoryInExePath=1 for the probe
    # (Python 3.12+'s shutil.which honors it and skips the cwd), and reject any
    # hit that is relative or resolves inside this repo (covers Python <3.12).
    _NDC = "NoDefaultCurrentDirectoryInExePath"
    _ndc_old = os.environ.get(_NDC)
    os.environ[_NDC] = "1"
    try:
        which_cb = shutil.which("cb", path=os.environ.get("PATH", ""))
    finally:
        if _ndc_old is None:
            os.environ.pop(_NDC, None)
        else:
            os.environ[_NDC] = _ndc_old
    shim_hit = None
    if which_cb:
        p = Path(which_cb)
        try:
            in_repo = p.resolve().is_relative_to(REPO_ROOT)
        except (OSError, ValueError):
            in_repo = False
        if not p.is_absolute() or in_repo:
            shim_hit, which_cb = which_cb, None   # only the repo shim: NOT on PATH
    if which_cb:
        record("path", "cb-on-PATH", "PASS", f"`cb` resolves -> {which_cb}")
        return True
    import sysconfig
    scripts_dir = sysconfig.get_path("scripts") or "<python Scripts dir>"
    if add_path and IS_WINDOWS and scripts_dir and os.path.isdir(scripts_dir):
        # The THIRD announced write, opt-in via --add-path: append the Scripts
        # dir to the USER Path so bare `cb` resolves in every NEW shell
        # (PowerShell never runs from the cwd, so `.\cb` is the only
        # alternative without this).
        say(f"      --add-path: appending {scripts_dir} to the USER Path (HKCU)...")
        outcome = _append_user_path_windows(scripts_dir)
        if outcome in ("added", "already present"):
            # Be precise about WHICH restart: a new TAB in Windows Terminal /
            # VS Code inherits the HOST process's environment block, so it is
            # NOT a new environment and bare `cb` still won't resolve. Operators
            # hit that, re-ran setup, saw "already present" -> PASS, and looped.
            record("path", "cb-on-PATH", "PASS",
                   f"user Path {outcome}: {scripts_dir} - bare `cb` resolves "
                   "once the TERMINAL HOST restarts. A new tab is NOT a new "
                   "environment (it inherits Windows Terminal's / VS Code's "
                   "env block): fully close and reopen the host, or in THIS "
                   "session run  $env:Path += ';" + scripts_dir + "'  . "
                   "Re-running setup will keep saying 'already present' - the "
                   "registry is correct; only the live process is stale. "
                   "Meanwhile `.\\cb <command>` from the repo root always works.")
            return True
        record("path", "cb-on-PATH", "WARN", f"--add-path {outcome}",
               f"Add it manually: Settings > Edit environment variables for your "
               f"account > Path > New > {scripts_dir}")
        return False
    record("path", "cb-on-PATH", "WARN",
           (f"only the repo-root shim resolves ({shim_hit}) - not PATH-wide; "
            "PowerShell needs the .\\cb form" if shim_hit else
            "`cb` does not resolve as a bare command in this shell"),
           "One-time fix: re-run setup with --add-path (appends the Python Scripts "
           "dir to your USER Path; bare `cb` then resolves after the TERMINAL "
           "HOST restarts - a new tab inherits the host's stale env block and is "
           "NOT enough):\n"
           f"  {scripts_dir}\n"
           "or skip PATH entirely - the repo-root shim always works:\n"
           "  .\\cb <command>   (PowerShell/cmd, from the repo root)\n"
           "  ./cb <command>   (bash, from the repo root)")
    return False


# --------------------------------------------------------------------------- #
# Phase 4 - unit tests (skippable with --no-tests).                            #
# --------------------------------------------------------------------------- #

def _rerun_cmd(rel_dir: str) -> str:
    """The exact command to reproduce a suite run by hand on this platform."""
    py = "py -3" if IS_WINDOWS else "python3"
    return f"{py} -m unittest discover -s {rel_dir} -v"


def _run_suite(rel_dir: str, timeout: int = 2400):
    """unittest discover on <repo>/<rel_dir>.

    Returns (ok, tail, fail_ids, log_path): the Ran-N/OK summary, the failing
    `FAIL:`/`ERROR:` test ids, and the log file holding the FULL unittest
    output (under <tempdir>/craftbench-setup-logs/; None if unwritable).

    The suites run with CraftBench/agent env vars scrubbed so a maintainer's
    shell state (CB_ROOT, CRAFTBENCH_L1_MAX_PARALLEL, keys, ...) can't skew
    results — phase 4 must be reproducible on any box."""
    cmd = [sys.executable, "-m", "unittest", "discover", "-s", rel_dir]
    hermetic_env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("CB_", "CRAFTBENCH_", "ANTHROPIC_",
                                         "OPENROUTER_"))}
    try:
        cp = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True,
                            text=True, timeout=timeout, env=hermetic_env)
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s", [], None
    except OSError as e:
        return False, f"could not launch: {e}", [], None
    output = cp.stderr + cp.stdout
    log_path = None
    try:
        log_dir = Path(tempfile.gettempdir()) / "craftbench-setup-logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / (rel_dir.replace("/", "-").replace("\\", "-") + ".log")
        log_path.write_text(output, encoding="utf-8", errors="replace")
    except OSError:
        log_path = None
    lines = [ln for ln in output.splitlines() if ln.strip()]
    tail = [ln for ln in lines if re.match(r"^(Ran \d+ tests?|OK|FAILED|ERROR)", ln)]
    fail_ids = [ln.strip() for ln in lines if re.match(r"^(FAIL|ERROR): ", ln)]
    summary = "; ".join(tail[-2:]) if tail else (lines[-1] if lines else "<no output>")
    return cp.returncode == 0, summary, fail_ids, log_path


def _live_run_in_flight():
    """(active, how) - is another live run holding runs/.live-run.lock? Uses the
    SAME lock test the harness does (tools/run-agent/live_lock.py); falls back
    to a runs/**/summary.json recency check if that will not import."""
    try:
        sys.path.insert(0, str(RUN_AGENT_DIR))
        import live_lock  # noqa: PLC0415
        active = live_lock.is_live_run_active()
        return active, ("another live run holds the lock (runs/.live-run.lock)"
                        if active else "no other live run holds runs/.live-run.lock")
    except Exception:
        pass
    try:
        import time
        newest = 0.0
        for p in (REPO_ROOT / "runs").rglob("summary.json"):
            try:
                newest = max(newest, p.stat().st_mtime)
            except OSError:
                continue
        active = (time.time() - newest) < 3600 if newest else False
        return active, ("a runs/**/summary.json changed <60 min ago (lock check unavailable)"
                        if active else "no recent runs/ activity (lock check unavailable)")
    except OSError:
        return False, "no runs/ dir"


def phase_tests(skip: bool) -> dict:
    header(4, _TOTAL, "Unit tests")
    if skip:
        record("tests", "all-suites", "SKIP", "skipped (--no-tests)")
        return {"skipped": True}
    out: dict = {"skipped": False, "suites": {}}

    def _run_and_record(rel: str) -> None:
        ok, tail, fail_ids, log = _run_suite(rel)
        hint = ""
        if not ok:
            parts = list(fail_ids)
            if log:
                parts.append(f"full output: {log}")
            parts.append(f"rerun: {_rerun_cmd(rel)}")
            hint = "\n".join(parts)
        record("tests", rel, "PASS" if ok else "FAIL", tail, hint)
        out["suites"][rel] = {"ok": ok, "tail": tail, "failing": fail_ids,
                              "log": str(log) if log else None}

    for rel in ("tools/verify-single/tests", "tools/coverage/tests"):
        if not (REPO_ROOT / rel).is_dir():
            record("tests", rel, "FAIL", "suite dir missing - incomplete clone?")
            out["suites"][rel] = {"ok": False, "tail": "missing"}
            continue
        say(f"      running {rel} (unittest discover; no UE needed)...")
        _run_and_record(rel)

    active, how = _live_run_in_flight()
    if active:
        record("tests", "tools/run-agent/tests", "WARN",
               f"SKIPPED - {how}",
               "The run-agent suite is not runnable during a live drive (12 tests read "
               "the live AGENT_WRITABLE.json). Re-run after the drive finishes.")
        out["suites"]["tools/run-agent/tests"] = {"ok": None, "tail": f"skipped: {how}"}
    else:
        say(f"      running tools/run-agent/tests (1100+ tests; {how})...")
        _run_and_record("tools/run-agent/tests")
    return out


# --------------------------------------------------------------------------- #
# Phase 5 - readiness via aura_rig.doctor (THE per-tier authority; advisory).  #
# --------------------------------------------------------------------------- #

def phase_doctor() -> dict:
    header(5, _TOTAL, "Per-tier readiness (cb doctor, in-process)")
    try:
        sys.path.insert(0, str(RUN_AGENT_DIR))
        from types import SimpleNamespace
        from aura_rig import doctor, stack  # noqa: PLC0415

        paths = stack.StackPaths()
        stack.load_aura_env(paths)          # read-only on disk; exports .env keys in-process
        hp = stack.resolve_harness_py()
        ctx = SimpleNamespace(
            paths=paths,
            py_exe=hp[0] if hp else None,
            py_pre=list(hp[1]) if hp else [],
            ue=stack.resolve_ue(),
        )
        probe = doctor.real_probe(ctx)
        diag = doctor.diagnose(probe)
        for line in doctor.render(diag, live_coding=probe.live_coding).splitlines():
            say("  " + line)
        tiers = {t: diag.tier_verdict(t) for t in ("grade-only", "baseline")}
        blockers = {t: [c.id for c in diag.checks if c.tier == t and c.status == "FAIL"]
                    for t in ("grade-only", "baseline")}
        return {"available": True, "exit_code": diag.exit_code(),
                "provisioned_tier": diag.provisioned_tier(), "tiers": tiers,
                "blockers": blockers}
    except Exception as e:  # noqa: BLE001 - degrade, never block the report
        record("doctor", "cb-doctor", "WARN",
               f"in-process doctor unavailable ({e.__class__.__name__}: {e})",
               "Run it directly for the authoritative per-tier readiness: "
               "tools/run-agent/cb doctor  (cb.cmd on Windows)")
        return {"available": False}


# --------------------------------------------------------------------------- #
# --full - smoke-grade the t0 reference end-to-end (needs UE; ~7 min).         #
# --------------------------------------------------------------------------- #

def _short_workdir() -> Path:
    """--full smoke workdir: <root>/wd/s<tag>, root resolved CB_ROOT (env, then
    .env) -> CB_TMP (env, then .env) -> C:\\cb (Windows) / TMPDIR. Kept SHORT so
    UE build paths under it stay inside the 260-char MAX_PATH limit."""
    tag = uuid.uuid4().hex[:6]
    dotenv = parse_env_file(REPO_ROOT / ".env")
    root = (os.environ.get("CB_ROOT") or dotenv.get("CB_ROOT")
            or os.environ.get("CB_TMP") or dotenv.get("CB_TMP"))
    if root:
        return Path(root) / "wd" / f"s{tag}"
    if IS_WINDOWS:
        return Path(r"C:\cb\wd") / f"s{tag}"          # short: dodges MAX_PATH
    return Path(os.environ.get("TMPDIR") or "/tmp") / f"cbw{tag}"


def _slim_smoke_workdir(wd: Path, report: dict | None) -> dict | None:
    """Reclaim the --full smoke workdir once the grade has been reported.

    A finished verifier workdir was measured at 5.54 GB on 2026-07-25 (4.72 GB of
    it <Proj>/Intermediate/Build/Win64/x64, i.e. cl.exe .obj/.pch nobody reads
    afterwards) — a one-off setup smoke should not hand a brand-new team member a
    5.5 GB souvenir on their first run. Mode "slim" (the default) drops the
    compiler intermediate and KEEPS Binaries/ + out/, so the say() line below
    stays true: the leftovers are still a launchable, self-explaining project.

    Called AFTER record() has already folded cp.stdout/stderr into the report -
    the smoke's evidence is in memory (and in out/, which slim keeps) before
    anything is deleted.

    Never blocks the report: an unimportable rig (grade-only checkout, no
    aura_rig on sys.path) or any failure degrades to one printed line and a
    None - it records no FAIL and cannot move the exit code, exactly like the
    other phases' "degrade, never block" try/excepts. apply() also
    refuses on its own whenever this workdir does not resolve under
    aura_rig.paths.wd_root() - _short_workdir() above additionally honors .env's
    CB_ROOT/CB_TMP, which wd_root() (env-only) may not see, and a refusal keeps
    every byte rather than deleting outside the sanctioned root."""
    try:
        sys.path.insert(0, str(RUN_AGENT_DIR))
        from aura_rig import workdir_retention  # noqa: PLC0415

        return workdir_retention.apply(wd, None, report=report,
                                       log=lambda m: say(f"      {m}"))
    except Exception as e:  # noqa: BLE001 - degrade, never block the report
        say(f"      workdir retention unavailable "
            f"({e.__class__.__name__}: {e}); {wd} kept in full")
        return None


def _smoke_report(wd: Path) -> dict | None:
    """The smoke's report.json (<workdir>/out/report.json - run_task.py's default
    when no --report-json is passed). Retention's "never slim a failed L1" guard
    needs it: a broken build is exactly the run whose .obj/.pch tree a human
    still wants. None when it is absent or unreadable -> apply() refuses."""
    try:
        return json.loads((wd / "out" / "report.json").read_text(
            encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None


def phase_full_smoke(ue_root) -> dict:
    header(_TOTAL - 1, _TOTAL, "Smoke grade (--full): t0 reference via run_task.py")
    if not ue_root:
        record("smoke", "t0-reference", "SKIP", "UE 5.8 not found - smoke grade skipped")
        return {"ran": False}
    wd = _short_workdir()
    say(f"      grading {T0_REFERENCE} - takes ~7 min (L1 build + L2 PIE); workdir {wd}")
    cmd = [sys.executable, str(REPO_ROOT / "tools" / "verify-single" / "run_task.py"),
           "--task", T0_TASK, "--submission", T0_REFERENCE,
           "--ue-root", str(ue_root), "--workdir", str(wd)]
    try:
        cp = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True,
                            text=True, timeout=3600)
    except subprocess.TimeoutExpired:
        record("smoke", "t0-reference", "FAIL", "timed out after 3600s")
        say(f"      safe to delete {wd} when done (one-off smoke workdir)")
        return {"ran": True, "ok": False, "workdir": str(wd)}
    tail = [ln for ln in (cp.stdout + cp.stderr).splitlines() if ln.strip()][-6:]
    ok = cp.returncode == 0
    record("smoke", "t0-reference", "PASS" if ok else "FAIL",
           f"run_task.py exit {cp.returncode}", "\n".join(tail))
    retention = _slim_smoke_workdir(wd, _smoke_report(wd))
    say(f"      safe to delete {wd} when done (one-off smoke workdir)")
    return {"ran": True, "ok": ok, "exit": cp.returncode, "workdir": str(wd),
            "retention": retention}


# --------------------------------------------------------------------------- #
# Phase 6 - exit summary: per-tier table + next commands + manual to-dos.      #
# --------------------------------------------------------------------------- #

def phase_summary(pre: dict, cfg: dict, on_path: bool, doc: dict) -> dict:
    header(_TOTAL, _TOTAL, "Per-tier summary + next steps")
    keys = cfg.get("keys", {})

    def _set(k):
        return keys.get(k) in ("set", "set(env)")

    # Prefer the PATH-wide console script; fall back to the repo-root shim
    # (always present, no install needed).
    cb = "cb" if on_path else (".\\cb" if IS_WINDOWS else "./cb")

    ue_fix = ("Install UE 5.8 via the Epic Games Launcher (default C:\\Program Files\\"
              "Epic Games\\UE_5.8; ~100 GB disk, allow hours - one-time) or set CB_UE_ROOT in .env")
    # CUMULATIVE blockers per canonical tier - the same names + semantics as
    # cb doctor (grade-only / baseline): each tier inherits every blocker of the
    # tier below it. Each blocker = (what, how-to-unblock).
    # Doctor's per-tier FAILs are folded into the same lists (attributed, deduped
    # against the checks this script already makes itself), so this table can
    # never disagree with the doctor block above it.
    _covered_by_setup = {"ue", "git", "tar", "claude-cli", "anthropic-key"}
    doc_blockers = doc.get("blockers", {}) if doc.get("available") else {}

    def _doctor_extras(tier):
        return [(f"{cid} (doctor check)", "apply the '->' fix under section [5/6]")
                for cid in doc_blockers.get(tier, []) if cid not in _covered_by_setup]

    grade_blockers = []
    for t in ("python", "git", "tar"):
        if not pre.get(t):
            grade_blockers.append((f"{t} missing", f"Install {t} (see section [1/6])"))
    if not pre.get("ue_root"):
        grade_blockers.append(("UE 5.8 not installed", ue_fix))
    grade_blockers += _doctor_extras("grade-only")

    base_blockers = list(grade_blockers)
    if not pre.get("claude"):
        base_blockers.append(("claude CLI not installed",
                              "Install Claude Code (the claude CLI) and add it to PATH"))
    if not (_set("ANTHROPIC_API_KEY") or _set("OPENROUTER_API_KEY")):
        base_blockers.append(("no agent key",
                              "Put a real ANTHROPIC_API_KEY (or OPENROUTER_API_KEY) in .env"))
    base_blockers += _doctor_extras("baseline")

    # `cb smoke` IS the golden path (preflight -> verifier unit tests -> a real
    # t0 reference grade); the raw run_task.py incantation lives in README
    # "The cb command" for the no-cb route.
    tiers = {
        "grade-only": (grade_blockers, f"{cb} smoke"),
        "baseline": (base_blockers,
                     f"{cb} eval --model claude-p:sonnet --task t0-sanity-log-on-beginplay"),
    }
    ready_map = {}
    for name, (blockers, nxt) in tiers.items():
        ready = not blockers
        ready_map[name] = ready
        if ready:
            say(f"  {name:<25} READY")
            say(f"      run now> {nxt}")
        else:
            say(f"  {name:<25} blocked by: " + ", ".join(b for b, _f in blockers))
            more = f"  (+{len(blockers) - 1} more above)" if len(blockers) > 1 else ""
            say(f"      unblock> {blockers[0][1]}{more}")
            say(f"      then> {nxt}")

    # Doctor's FAILs are already folded into the table above, so no
    # reconciliation line is needed; doctor stays advisory for the exit code.

    manual = []
    if not pre.get("ue_root"):
        manual.append(ue_fix + ".")
    if not _set("ANTHROPIC_API_KEY"):
        manual.append("Put a real ANTHROPIC_API_KEY in .env (baseline tier).")
    if not pre.get("claude"):
        manual.append("Install the claude CLI (baseline tier).")
    if manual:
        say("  Manual steps still needed:")
        for m in manual:
            say(f"    - {m}")
    else:
        say("  Manual steps still needed: none - both tiers provisioned on this box.")
    return {"tiers": ready_map,
            "blockers": {k: [b for b, _f in v[0]] for k, v in tiers.items()},
            "next": {k: v[1] for k, v in tiers.items()}, "manual": manual}


# --------------------------------------------------------------------------- #
# main                                                                          #
# --------------------------------------------------------------------------- #

_TOTAL = 6  # bumped to 7 when --full adds the smoke phase


def main(argv=None) -> int:
    global _JSON_MODE, _TOTAL
    ap = argparse.ArgumentParser(
        description="CraftBench post-clone setup + readiness report. Writes: copies "
                    ".env.example -> .env if absent; pip-installs the cb console script "
                    "(editable, idempotent). --add-path additionally appends your user "
                    "PATH; --full additionally creates a build workdir.")
    ap.add_argument("--no-tests", action="store_true", help="skip the unit-test phase")
    ap.add_argument("--json", action="store_true",
                    help="machine summary as JSON on stdout (human report goes to stderr)")
    ap.add_argument("--full", action="store_true",
                    help="additionally smoke-grade the t0 reference via run_task.py "
                         "(requires UE 5.8; takes ~7 min; creates a short build workdir)")
    ap.add_argument("--add-path", action="store_true",
                    help="Windows: if `cb` does not resolve PATH-wide, append the "
                         "Python Scripts dir to the USER Path (HKCU\\Environment; "
                         "announced, reversible, new shells only)")
    ap.add_argument("--strict", action="store_true",
                    help="repo unit-test failures also flip the exit code (default: "
                         "they are reported with names/log/rerun but do not block your tier)")
    ap.add_argument("--verbose", action="store_true",
                    help="list every .env key in section [2/6] (default: keys that are "
                         "set plus required-but-missing ones)")
    args = ap.parse_args(argv)
    _JSON_MODE = args.json
    if args.full:
        _TOTAL = 7

    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(errors="replace")  # cp1252-safe: never crash on odd chars
        except Exception:  # noqa: BLE001
            pass

    say(f"CraftBench setup - repo root {REPO_ROOT}")
    say("Writes: copies .env.example -> .env if absent + pip-installs the `cb` console script (editable, idempotent).")
    say("--add-path additionally appends your user PATH; --full additionally creates a build workdir.")

    dotenv0 = parse_env_file(REPO_ROOT / ".env")   # pre-copy view, for UE resolution
    pre = phase_prereqs(dotenv0)
    cfg = phase_config(verbose=args.verbose)
    if cfg.get("created"):                          # UE root may live in the fresh .env
        pre_ue, ue_ver = resolve_ue(parse_env_file(REPO_ROOT / ".env"))
        if pre_ue and not pre.get("ue_root"):
            pre["ue_root"], pre["ue_version"] = str(pre_ue), ue_ver
    on_path = phase_path(add_path=args.add_path)
    tests = phase_tests(args.no_tests)
    doc = phase_doctor()
    smoke = phase_full_smoke(pre.get("ue_root")) if args.full else {"ran": False}
    summary = phase_summary(pre, cfg, on_path, doc)

    # TIER-SCOPED exit policy: non-test FAILs block a tier at/below the target
    # tier -> exit 1. Repo unit-test FAILs are reported in full above but flip
    # the exit code only under --strict.
    failed = [c for c in _CHECKS if c["status"] == "FAIL"]
    test_fails = [c for c in failed if c["phase"] == "tests"]
    tier_fails = [c for c in failed if c["phase"] != "tests"]
    target = cfg.get("target_tier", "grade-only")
    exit_code = 1 if tier_fails or (args.strict and test_fails) else 0

    _BLOCKS = {"python": "grade-only", "git": "grade-only", "tar": "grade-only",
               ".env.example": "every tier", ".env": "baseline",
               "t0-reference": "grade-only"}

    def _tag(c: dict) -> str:
        if c["phase"] == "tests":
            return f"{c['id']} [repo unit tests - blocks no tier; enforced by --strict]"
        return f"{c['id']} [blocks {_BLOCKS.get(c['id'], target)}]"

    # Blockers the exit code does not gate on (WARN-level prereqs like a missing
    # UE, advisory doctor FAILs) still deserve a pointer on the last line.
    _left = summary.get("blockers", {}).get(target, [])
    left_note = (f"; {len(_left)} blocker(s) remain for {target} - see section [6/6]"
                 if _left else "")

    say("")
    if exit_code:
        shown = tier_fails + (test_fails if args.strict else [])
        say(f"setup_craftbench: FAIL ({', '.join(_tag(c) for c in shown)}) "
            f"- exit 1 (target tier: {target})")
        if test_fails and not args.strict:
            say("  (repo unit-test failures reported above do not block your tier; "
                "--strict enforces them)")
    elif test_fails:
        say(f"setup_craftbench: OK - exit 0 (target tier: {target}{left_note}; repo unit-test "
            "failures reported above do not block your tier; --strict enforces them)")
    else:
        say(f"setup_craftbench: OK - exit 0 (target tier: {target}{left_note})")

    if _JSON_MODE:
        print(json.dumps({
            "repo_root": str(REPO_ROOT),
            "platform": sys.platform,
            "flags": {"no_tests": args.no_tests, "full": args.full,
                      "strict": args.strict, "verbose": args.verbose},
            "target_tier": target,
            "checks": _CHECKS,
            "prereqs": pre,
            "env": {"created": cfg.get("created", False), "keys": cfg.get("keys", {}),
                    "extra_keys": cfg.get("extra_keys", [])},
            "path": {"run_agent_on_path": on_path, "dir": str(RUN_AGENT_DIR)},
            "tests": tests,
            "doctor": doc,
            "smoke": smoke,
            "summary": summary,
            "exit_code": exit_code,
        }, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
