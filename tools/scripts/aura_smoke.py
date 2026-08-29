#!/usr/bin/env python3
"""Aura + UE end-to-end smoke loop (MVP).

Runs one iteration of:
    1. Validate prerequisites (UE install, Aura install, ThirdParty deps, ...)
    2. Spawn UE Editor with the Aura plugin loaded (uses Aura's own
       headless launch path under ~/.aura/)
    3. Send a prompt to Aura
    4. Wait for a done-marker
    5. Run the existing L1+L2 verifier on the resulting substrate state
    6. Report PASS/FAIL with attribution

Failure modes are first-class — every step produces a structured
``IterationResult`` whose ``blocker`` field names the specific
prerequisite or step that failed, so an outer loop can decide whether
to retry, fall back, or stop.

Mode hierarchy for the prompt-send step (Aura currently has NO
documented synchronous "send prompt programmatically" API outside its
own UI):

    1. file-watcher mode (R-1 hypothesis) — drop a prompt JSON into
       a watched directory; requires an Aura-side patch that we do not
       know to exist on this machine. Try first.
    2. operator-paste mode — print the prompt; the operator pastes it
       into Aura's chat window; we watch for a done-marker file the
       operator creates (`runs/<run_id>/.agent_done`).

A fully-automated mode (the bare-LLM adapter using Aura's MCP server as
a tool provider, per the v1.0 contract) lands separately at T067/T068/T070.

This script intentionally does NOT use the existing HarnessAdapter +
SubstrateAdapter machinery. Those abstractions exist for the batch
runner; this script is the first-touch smoke that proves the wiring
end-to-end before we wire the batch runner to use it.

Usage::

    UE_ROOT=/path/to/UE_5.8 python3 tools/scripts/aura_smoke.py \\
        --task tasks/t0-sanity-log-on-beginplay.md \\
        --substrate UE-projects/CraftBenchTemplate \\
        --mode operator-paste

Exit codes:
    0   smoke PASSED (verifier returned PASS)
    1   verifier returned FAIL on the resulting submission
    2   verifier returned ERROR / something else non-PASS
    10  prerequisite missing (UE / Aura / ThirdParty / Aura.app)
    11  Aura never became ready (port files never appeared)
    12  prompt send failed (no programmatic API found, operator declined)
    13  agent timeout (deadline exceeded waiting for done marker)
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]
if str(_REPO_ROOT / "tools" / "verify-single") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "tools" / "verify-single"))

from run_task import parse_task_spec  # noqa: E402


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class IterationResult:
    ok: bool = False
    blocker: Optional[str] = None  # short tag for the outer loop's switch
    detail: str = ""
    exit_code: int = 0
    timings: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Step 1: prerequisites
# ---------------------------------------------------------------------------


@dataclass
class Prereqs:
    ue_root: Path
    substrate: Path
    aura_root: Path
    aura_app: Path
    aura_third_party_lib: Path
    editor_launcher: Path
    dot_aura: Path
    uproject_path: Path


def check_prerequisites(
    ue_root: Optional[Path],
    substrate: Path,
    *,
    collect_all: bool = True,
) -> tuple[Optional[Prereqs], list[tuple[str, str, bool]]]:
    """Walk every prerequisite check, collecting (name, detail, ok).

    When ``collect_all=True`` (default): all checks run regardless of
    earlier failures, so the operator gets a complete matrix of
    "what's installed and what's missing." Returns (Prereqs|None,
    rows). Prereqs is None if any required check failed.

    The legacy "fail fast" mode (collect_all=False) bails on first
    missing — kept for future caller use; current call sites use the
    collect-all path.
    """
    rows: list[tuple[str, str, bool]] = []
    substrate = substrate.resolve()

    # UE_ROOT
    if ue_root is None:
        rows.append((
            "UE_ROOT",
            "unset — pass --ue-root or export UE_ROOT (must point at the dir with Engine/, e.g. C:/Program Files/Epic Games/UE_5.8)",
            False,
        ))
    elif not (ue_root / "Engine" / "Build" / "Build.version").exists():
        rows.append((
            "UE_ROOT",
            f"{ue_root} exists but no Engine/Build/Build.version — not a UE install",
            False,
        ))
    else:
        rows.append(("UE_ROOT", str(ue_root), True))

    # substrate uproject
    uproject_candidates = list(substrate.glob("*.uproject"))
    if not uproject_candidates:
        rows.append(("substrate uproject", f"no .uproject in {substrate}", False))
        uproject_path = None
    else:
        uproject_path = uproject_candidates[0]
        rows.append(("substrate uproject", str(uproject_path), True))

    # Aura plugin symlink/dir
    aura_root = (substrate / "Plugins" / "Aura").resolve()
    if not aura_root.exists():
        rows.append(("Aura plugin", f"missing at {aura_root}", False))
    else:
        rows.append(("Aura plugin", str(aura_root), True))

    # Aura.app
    aura_app_candidates = [
        Path.home() / "Applications" / "Aura.app",
        Path("/Applications/Aura.app"),
    ]
    aura_app_found = next((p for p in aura_app_candidates if p.exists()), None)
    if aura_app_found is None:
        rows.append((
            "Aura.app",
            "not found in ~/Applications or /Applications (install per MAC_PORT.md Modes A/B)",
            False,
        ))
        aura_app = aura_app_candidates[0]  # placeholder
    else:
        rows.append(("Aura.app", str(aura_app_found), True))
        aura_app = aura_app_found

    # Aura ThirdParty/Lib populated
    aura_third_party_lib = aura_root / "ThirdParty" / "Lib"
    if not aura_root.exists():
        rows.append(("Aura ThirdParty/Lib", "(skipped — Aura plugin missing)", False))
    elif not aura_third_party_lib.exists() or not any(aura_third_party_lib.iterdir()):
        rows.append((
            "Aura ThirdParty/Lib",
            f"missing or empty at {aura_third_party_lib} (run MAC_PORT.md Mode C pip-install)",
            False,
        ))
    else:
        n = sum(1 for _ in aura_third_party_lib.iterdir())
        rows.append(("Aura ThirdParty/Lib", f"{aura_third_party_lib} ({n} entries)", True))

    # Aura native dylib built for THIS host's architecture.
    # UE 5.7 on Apple Silicon refuses to load a plugin that doesn't have an
    # arm64 slice — and even a universal binary can be rejected if the slice
    # isn't ABI-compatible with the engine's loaded modules. Find the dylib
    # and inspect it via `file(1)` which handles universal binaries.
    if aura_root.exists():
        aura_dylib = aura_root / "Binaries" / "Mac" / "UnrealEditor-Aura.dylib"
        if not aura_dylib.exists():
            rows.append((
                "Aura native dylib",
                f"missing at {aura_dylib} — Aura plugin needs build (see MAC_PORT.md Mode C step 2)",
                False,
            ))
        else:
            host_arch = _host_macho_arch()
            slices = _macho_slices(aura_dylib)
            if host_arch and host_arch not in slices:
                rows.append((
                    "Aura native dylib",
                    f"{aura_dylib} has slices {slices} but host is {host_arch} — UE will refuse to load",
                    False,
                ))
            else:
                slice_label = "+".join(slices) if slices else "unknown"
                rows.append(("Aura native dylib", f"{aura_dylib} ({slice_label})", True))
    else:
        rows.append(("Aura native dylib", "(skipped — Aura plugin missing)", False))

    # WARN (not fail) on a duplicate Aura plugin at the engine level. This
    # appears at Engine/Plugins/Marketplace/Aura/ when the operator has
    # installed the marketplace version of Aura into the engine. UE
    # prioritizes the project plugin in our case, but the duplicate is a
    # known source of load-time confusion (see editor log for the
    # "prioritizing project plugin" message).
    if ue_root is not None:
        engine_aura = ue_root / "Engine" / "Plugins" / "Marketplace" / "Aura"
        if engine_aura.exists():
            rows.append((
                "Engine-level Aura plugin",
                f"present at {engine_aura} (WARN: duplicate; project plugin will be prioritized but ABI collision is possible)",
                True,  # WARN, not fail
            ))

    # UnrealEditor-Cmd launcher
    if ue_root is None:
        rows.append(("UnrealEditor-Cmd", "(skipped — UE_ROOT unset)", False))
        editor_launcher = Path("/missing")
    else:
        editor_launcher = _default_editor_launcher(ue_root)
        if editor_launcher.exists():
            rows.append(("UnrealEditor-Cmd", str(editor_launcher), True))
        else:
            rows.append(("UnrealEditor-Cmd", f"missing at {editor_launcher}", False))

    # Aura's port-marker dir. Phase A of the Mac port (commit 4d14d3de5)
    # moved this from ~/.aura/ to ~/Library/Application Support/Aura/.Aura/
    # on macOS; Linux/Windows still use ~/.aura. Mirror the plugin's logic
    # so wait_for_aura_ready polls where the plugin actually writes.
    dot_aura = _default_dot_aura()
    rows.append((
        "Aura .Aura dir",
        str(dot_aura) + (" (exists)" if dot_aura.exists() else " (will be created)"),
        True,
    ))

    # All required checks must pass to construct Prereqs.
    REQUIRED = {
        "UE_ROOT", "substrate uproject", "Aura plugin", "Aura.app",
        "Aura ThirdParty/Lib", "UnrealEditor-Cmd",
    }
    failed_required = [name for name, _detail, ok in rows if name in REQUIRED and not ok]
    if failed_required:
        return None, rows

    return Prereqs(
        ue_root=ue_root,  # type: ignore
        substrate=substrate,
        aura_root=aura_root,
        aura_app=aura_app,
        aura_third_party_lib=aura_third_party_lib,
        editor_launcher=editor_launcher,
        dot_aura=dot_aura,
        uproject_path=uproject_path,  # type: ignore
    ), rows


def render_prereq_matrix(rows: list[tuple[str, str, bool]]) -> str:
    """Pretty-print the prereq check matrix."""
    out = ["Prerequisite check:"]
    name_w = max(len(n) for n, _, _ in rows) + 2
    for name, detail, ok in rows:
        mark = "OK  " if ok else "MISS"
        out.append(f"  [{mark}] {name:<{name_w}}{detail}")
    return "\n".join(out)


def _default_dot_aura() -> Path:
    """Per-platform Aura port-marker dir. Mirrors the plugin's own
    AuraUtils::GetClientPath / Python utils._installed_client_path logic.
    """
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Aura" / ".Aura"
    return Path.home() / ".aura"


def _default_editor_launcher(ue_root: Path) -> Path:
    plat = sys.platform
    if plat == "darwin":
        return ue_root / "Engine" / "Binaries" / "Mac" / "UnrealEditor-Cmd"
    if plat == "linux":
        return ue_root / "Engine" / "Binaries" / "Linux" / "UnrealEditor-Cmd"
    if plat == "win32":
        return ue_root / "Engine" / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe"
    return ue_root / "Engine" / "Binaries" / "Linux" / "UnrealEditor-Cmd"


def _host_macho_arch() -> Optional[str]:
    """Mach-O architecture name matching `file(1)` output for this host."""
    if sys.platform != "darwin":
        return None
    import platform as _p
    m = _p.machine()
    if m == "arm64":
        return "arm64"
    if m in ("x86_64", "amd64"):
        return "x86_64"
    return m


def _macho_slices(path: Path) -> tuple[str, ...]:
    """Return the architecture slices present in a Mach-O binary.

    Works for both single-arch and universal-binary cases.
    """
    if sys.platform != "darwin":
        return ()
    try:
        out = subprocess.run(
            ["file", str(path)], capture_output=True, text=True, check=False, timeout=5
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ()
    txt = out.stdout
    slices: list[str] = []
    if "arm64" in txt:
        slices.append("arm64")
    if "x86_64" in txt:
        slices.append("x86_64")
    return tuple(slices)


# ---------------------------------------------------------------------------
# Step 2: spawn UE + Aura
# ---------------------------------------------------------------------------


def spawn_ue_editor(prereqs: Prereqs, log_file: Path) -> subprocess.Popen:
    """Spawn UE Editor headless with Aura's headless bootstrap active.

    Args mirror Aura's own ``MCP/headless_launcher.py::launch_headless``:

    - ``-RenderOffScreen`` (NOT ``-nullrhi``) so RemoteControl + Aura's
      websocket bridge can still bind ports.
    - ``-AuraHeadless`` is Aura's custom CLI flag that
      ``FAuraModule::IsRunningHeadless()`` detects to bootstrap Aura's
      bridge servers. WITHOUT this flag the Aura plugin loads as a
      normal editor plugin (waiting for a UI click) and never writes
      the ``~/.aura/rc_server_port.txt`` / ``aura_server_port.txt``
      marker files we poll for in ``wait_for_aura_ready``.
    - ``-log -stdout -fullstdoutlogoutput`` route UE's log to our
      captured stdout (without these, UE writes to its own log file
      under ``<project>/Saved/Logs/`` and our captured stdout is
      empty except for trace-server side-process output).
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_fh = open(log_file, "wb")
    return subprocess.Popen(
        [
            str(prereqs.editor_launcher),
            str(prereqs.uproject_path),
            "-RenderOffScreen",
            "-AuraHeadless",
            "-unattended",
            "-nosplash",
            "-nopause",
            "-nosound",
            "-log",
            "-stdout",
            "-fullstdoutlogoutput",
        ],
        stdout=log_fh,
        stderr=subprocess.STDOUT,
    )


# ---------------------------------------------------------------------------
# Step 3: wait for Aura ready (port files appear under ~/.aura)
# ---------------------------------------------------------------------------


def wait_for_aura_ready(prereqs: Prereqs, timeout: float = 60.0) -> bool:
    """Per Aura/MCP/headless_launcher.py: Aura is ready when both
    rc_server_port.txt AND aura_server_port.txt exist under ~/.aura/.
    """
    rc_port = prereqs.dot_aura / "rc_server_port.txt"
    aura_port = prereqs.dot_aura / "aura_server_port.txt"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if rc_port.exists() and aura_port.exists():
            return True
        time.sleep(0.5)
    return False


# ---------------------------------------------------------------------------
# Step 4: send the prompt
# ---------------------------------------------------------------------------


def send_prompt_file_watcher_mode(
    prereqs: Prereqs,
    prompt: str,
    run_id: str,
) -> Optional[Path]:
    """Drop a prompt JSON in Aura's plugin-side prompts/ dir per R-1.

    Returns the path to the expected done file. The caller polls it.
    Returns None if the file-watcher path isn't viable here (e.g.
    Aura hasn't registered the watcher).
    """
    prompts_dir = prereqs.aura_root / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "prompt": prompt,
        "workspace_root": str(prereqs.substrate),
        "writable_prefixes": ["Source/CraftBenchTemplate/"],
        "deadline_seconds": 600,
        "action_budget": 30,
    }
    (prompts_dir / f"{run_id}.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    return prompts_dir / f"{run_id}.done.json"


def operator_paste_mode_present_prompt(
    prompt: str,
    done_marker: Path,
) -> None:
    """Print the prompt; instruct the operator to paste it into Aura,
    then create the done marker when finished.
    """
    print()
    print("=" * 72)
    print("OPERATOR-PASTE MODE")
    print("=" * 72)
    print("1) The UE Editor + Aura should now be open. Click the Aura toolbar")
    print("   button to surface the standalone Aura.app chat window.")
    print()
    print("2) Paste this prompt into the Aura chat input:")
    print()
    print("    " + "\n    ".join(prompt.splitlines()))
    print()
    print("3) When Aura finishes its work, create the done marker:")
    print()
    print(f"     touch {done_marker}")
    print()
    print("4) The smoke loop will detect the marker and run the verifier.")
    print("=" * 72)
    print()


# ---------------------------------------------------------------------------
# Step 5: wait for done signal
# ---------------------------------------------------------------------------


def wait_for_done(done_path: Path, deadline_seconds: float, poll_interval: float = 1.0) -> bool:
    deadline = time.time() + deadline_seconds
    while time.time() < deadline:
        if done_path.exists():
            return True
        time.sleep(poll_interval)
    return False


# ---------------------------------------------------------------------------
# Step 6: invoke the existing verifier
# ---------------------------------------------------------------------------


def run_verifier(
    task_path: Path,
    substrate_src: Path,
    ue_root: Path,
    report_path: Path,
) -> tuple[int, str]:
    """Invoke tools/verify-single/run_task.py against the substrate's
    current on-disk state. We use --submission-from-project so the
    runner extracts the agent's edits from the in-place substrate dir
    (the Aura "human-in-the-loop" mode the existing CLI already supports).
    """
    cmd = [
        sys.executable,
        str(_REPO_ROOT / "tools" / "verify-single" / "run_task.py"),
        "--task", str(task_path),
        "--submission-from-project", str(substrate_src),
        "--ue-root", str(ue_root),
        "--report-json", str(report_path),
        "--harness", "filesystem",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


# ---------------------------------------------------------------------------
# One iteration
# ---------------------------------------------------------------------------


def run_one_iteration(
    *,
    task_path: Path,
    substrate: Path,
    ue_root: Optional[Path],
    mode: str,
    deadline_seconds: float,
    out_dir: Path,
) -> IterationResult:
    timings: dict[str, float] = {}

    # ---- prereqs ----
    t0 = time.time()
    prereqs, rows = check_prerequisites(ue_root, substrate)
    timings["prereqs"] = time.time() - t0
    matrix = render_prereq_matrix(rows)
    print(matrix)
    if prereqs is None:
        return IterationResult(
            ok=False,
            blocker="prereq",
            detail=matrix,
            exit_code=10,
            timings=timings,
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    log_file = out_dir / "ue-editor.log"
    run_id = f"smoke-{uuid.uuid4().hex[:8]}"

    # ---- spawn UE ----
    t0 = time.time()
    print(f"[smoke] spawning UE Editor: {prereqs.editor_launcher}")
    print(f"[smoke] uproject:           {prereqs.uproject_path}")
    print(f"[smoke] log file:           {log_file}")
    proc = spawn_ue_editor(prereqs, log_file=log_file)
    print(f"[smoke] UE pid:             {proc.pid}")

    try:
        # ---- wait Aura ready ----
        t1 = time.time()
        print("[smoke] waiting for Aura readiness (rc_server_port + aura_server_port)…")
        if not wait_for_aura_ready(prereqs, timeout=60):
            timings["spawn_to_aura_ready"] = time.time() - t0
            return IterationResult(
                ok=False,
                blocker="aura_not_ready",
                detail=(
                    f"Aura never wrote rc_server_port.txt / aura_server_port.txt "
                    f"under {prereqs.dot_aura} within 60s. Check {log_file} for "
                    f"the editor's startup output."
                ),
                exit_code=11,
                timings=timings,
            )
        timings["spawn_to_aura_ready"] = time.time() - t1
        print(f"[smoke] Aura ready in {timings['spawn_to_aura_ready']:.1f}s")

        # ---- prompt send ----
        spec = parse_task_spec(task_path)
        prompt = _extract_prompt(spec.raw_text)
        if not prompt:
            return IterationResult(
                ok=False,
                blocker="no_prompt",
                detail=f"could not extract prompt from {task_path}",
                exit_code=12,
                timings=timings,
            )

        done_marker: Path
        if mode == "file-watcher":
            done_marker = send_prompt_file_watcher_mode(prereqs, prompt, run_id)
            print(f"[smoke] prompt dropped at {prereqs.aura_root}/prompts/{run_id}.json")
            print(f"[smoke] watching for done file: {done_marker}")
        elif mode == "operator-paste":
            done_marker = out_dir / ".agent_done"
            operator_paste_mode_present_prompt(prompt, done_marker)
        else:
            return IterationResult(
                ok=False,
                blocker="bad_mode",
                detail=f"unknown mode={mode!r}; expected 'file-watcher' or 'operator-paste'",
                exit_code=12,
                timings=timings,
            )

        # ---- wait for done ----
        t2 = time.time()
        if not wait_for_done(done_marker, deadline_seconds=deadline_seconds):
            timings["agent_loop"] = time.time() - t2
            return IterationResult(
                ok=False,
                blocker="agent_timeout",
                detail=(
                    f"no done signal at {done_marker} after {deadline_seconds:.0f}s. "
                    f"Either the file-watcher mode is not wired on the Aura side, "
                    f"or the operator did not finish + create the marker, or the "
                    f"agent itself timed out."
                ),
                exit_code=13,
                timings=timings,
            )
        timings["agent_loop"] = time.time() - t2
        print(f"[smoke] done signal received after {timings['agent_loop']:.1f}s")

        # ---- verifier ----
        t3 = time.time()
        report_path = out_dir / "report.json"
        rc, output = run_verifier(
            task_path=task_path,
            substrate_src=prereqs.substrate,
            ue_root=prereqs.ue_root,
            report_path=report_path,
        )
        timings["verifier"] = time.time() - t3
        print("[smoke] verifier output:")
        print("\n".join("    " + l for l in output.splitlines()[-30:]))
        print(f"[smoke] verifier exit code: {rc}; report at {report_path}")

        if rc == 0:
            return IterationResult(
                ok=True,
                blocker=None,
                detail=f"verifier PASS; report at {report_path}",
                exit_code=0,
                timings=timings,
            )
        if rc == 1:
            return IterationResult(
                ok=False,
                blocker="verifier_fail",
                detail=f"verifier FAIL; report at {report_path}",
                exit_code=1,
                timings=timings,
            )
        return IterationResult(
            ok=False,
            blocker="verifier_error",
            detail=f"verifier exit code {rc}; report at {report_path}",
            exit_code=2,
            timings=timings,
        )

    finally:
        # ---- teardown ----
        if proc.poll() is None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            except OSError:
                pass


def _extract_prompt(raw_text: str) -> str:
    capturing = False
    out: list[str] = []
    for line in raw_text.splitlines():
        if line.startswith("## ") and not line.startswith("### "):
            if capturing:
                break
            if line[3:].strip() == "Prompt given to the agent":
                capturing = True
                continue
        if capturing:
            out.append(line)
    return "\n".join(out).strip()


# ---------------------------------------------------------------------------
# Outer loop
# ---------------------------------------------------------------------------


def run_loop(args: argparse.Namespace) -> int:
    """Run up to `args.max_iterations` iterations; stop on first PASS or
    on a hard blocker that can't be retried.
    """
    out_root = args.out.resolve()
    for i in range(1, args.max_iterations + 1):
        print(f"\n=== iteration {i}/{args.max_iterations} (mode={args.mode}) ===")
        out_dir = out_root / f"iter-{i}"
        result = run_one_iteration(
            task_path=args.task.resolve(),
            substrate=args.substrate.resolve(),
            ue_root=(args.ue_root.resolve() if args.ue_root else None),
            mode=args.mode,
            deadline_seconds=args.deadline_seconds,
            out_dir=out_dir,
        )
        # Always write the result envelope.
        _write_result(out_dir / "result.json", result, iteration=i)
        if result.ok:
            print(f"\n=== iteration {i} PASS ===")
            return 0
        print(f"\n=== iteration {i} FAIL — blocker={result.blocker} ===")
        print(result.detail)
        # Hard blockers that don't recover from retry:
        if result.blocker == "prereq":
            print("\nFATAL: prerequisite missing; fix and re-run. Not retrying.")
            return result.exit_code
        if result.blocker == "bad_mode":
            return result.exit_code
        # Other blockers may resolve on retry (e.g. transient port-file flake);
        # continue to next iteration.
    return result.exit_code  # last iteration's exit code


def _write_result(path: Path, result: IterationResult, *, iteration: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "iteration": iteration,
                "ok": result.ok,
                "blocker": result.blocker,
                "detail": result.detail,
                "exit_code": result.exit_code,
                "timings": result.timings,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _default_task_path() -> Path:
    """The t0 smoke task, whichever layout the repo is on: the legacy flat
    tasks/<id>.md if present, else the folder form tasks/<set>/<id>/task.md."""
    flat = _REPO_ROOT / "tasks" / "t0-sanity-log-on-beginplay.md"
    if flat.exists():
        return flat
    return _REPO_ROOT / "tasks" / "cpp" / "t0-sanity-log-on-beginplay" / "task.md"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aura_smoke",
        description="Aura + UE 5.8 end-to-end smoke loop (MVP).",
    )
    p.add_argument(
        "--task",
        type=Path,
        default=_default_task_path(),
        help="Path to the task .md to smoke (default: t0-sanity-log-on-beginplay).",
    )
    p.add_argument(
        "--substrate",
        type=Path,
        default=_REPO_ROOT / "UE-projects" / "CraftBenchTemplate",
        help="Path to the substrate root containing the .uproject.",
    )
    p.add_argument(
        "--ue-root",
        type=Path,
        default=(Path(os.environ["CB_UE_ROOT"]) if os.environ.get("CB_UE_ROOT")
                 else Path(os.environ["UE_ROOT"]) if os.environ.get("UE_ROOT")
                 else None),
        help="UE 5.8 install root (or set $CB_UE_ROOT).",
    )
    p.add_argument(
        "--mode",
        choices=("file-watcher", "operator-paste"),
        default="operator-paste",
        help="How to deliver the prompt to Aura. 'file-watcher' requires an "
        "Aura-side patch that may not be present. 'operator-paste' is the "
        "fallback: print the prompt, wait for an operator-created done marker.",
    )
    p.add_argument(
        "--deadline-seconds",
        type=float,
        default=900.0,
        help="How long to wait for the done signal before giving up (default: 900s = 15min).",
    )
    p.add_argument(
        "--max-iterations",
        type=int,
        default=1,
        help="How many smoke iterations to try (default: 1).",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=_REPO_ROOT / "runs" / f"aura-smoke-{int(time.time())}",
        help="Run output directory.",
    )
    p.add_argument(
        "--check-only",
        action="store_true",
        help="Run the prerequisite matrix only; do not spawn UE. Exits "
        "0 if all required prereqs are present, 10 if any are missing.",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    print(f"[smoke] task:        {args.task}")
    print(f"[smoke] substrate:   {args.substrate}")
    print(f"[smoke] ue_root:     {args.ue_root}")
    print(f"[smoke] mode:        {args.mode}")
    print(f"[smoke] deadline:    {args.deadline_seconds}s")
    print(f"[smoke] out:         {args.out}")
    if args.check_only:
        prereqs, rows = check_prerequisites(args.ue_root, args.substrate.resolve())
        print()
        print(render_prereq_matrix(rows))
        return 0 if prereqs is not None else 10
    return run_loop(args)


if __name__ == "__main__":
    raise SystemExit(main())
