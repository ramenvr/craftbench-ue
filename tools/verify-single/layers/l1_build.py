"""L1 — Build via UnrealBuildTool.

Invokes the platform-appropriate UBT batch script twice — once for the
Editor target (``<Module>Editor``) and once for the Game target
(``<Module>``) — and treats exit-code 0 on **both** as the pass
criterion. Building both targets catches the ``#if WITH_EDITOR`` escape
hatch: a submission that only compiles in editor builds passes the
Editor target but fails the Game target, which is what would happen at
packaging time. Warnings from both targets are summed; the runner
applies ``--strict-warnings`` against the agent-file count.

Cross-platform notes:
- macOS:   <UE_ROOT>/Engine/Build/BatchFiles/Mac/Build.sh
- Linux:   <UE_ROOT>/Engine/Build/BatchFiles/Linux/Build.sh
- Windows: <UE_ROOT>/Engine/Build/BatchFiles/Build.bat

The script path is always **absolute** (rooted under ``ue_root``), so the
invocation never depends on ``PATH`` resolution; ``run_l1`` checks
``script.exists()`` up front, so a missing ``Build.bat`` (or ``Build.sh``)
surfaces as a clean L1 abort rather than an exec/PATH error.

On **Windows**, ``Build.bat`` is a batch file and cannot be exec'd
directly with ``shell=False`` (CreateProcess rejects ``.bat``), so the
command is wrapped as ``cmd /c <Build.bat> ...`` — ``cmd.exe`` then
interprets the batch file. macOS/Linux invoke ``Build.sh`` directly
(it has a shebang and is executable); their behavior is unchanged.
``shell=False`` is kept on every platform.

The expected UBT invocation form per target is::

    <Build script> <Target> <Platform> Development \\
        -project=<absolute path to .uproject> -waitmutex

(on Windows, prefixed with ``cmd /c``).

ASSUMPTION (UNVERIFIED): The exact target name suffix ``Editor`` is what
UE 5.7 expects; verified against UE docs but not a live UE install.
"""

from __future__ import annotations

import os
import pathlib
import platform
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from job_governor import resource_job, assign, L1_MEM_MB
from build_lock import ubt_build_lock


@dataclass
class L1Result:
    status: str  # "pass" or "fail"
    exit_code: int  # last nonzero exit across targets, or 0 if all passed
    log_path: Path  # combined log; per-target sections delimited inside
    duration_seconds: float  # sum across targets
    warning_count: int  # sum across targets
    warning_count_agent_files: int  # sum across targets
    notes: list[str]  # includes per-target summary lines
    # Set on the two paths that mean no build process ever ran: the UBT script
    # is absent (exit 127), or a no-trace spawn reproduced (SPAWN_FAULT_EXIT).
    build_tool_never_ran: bool = False


# Regex for clang/gcc-style warnings and MSVC warnings.
# clang:  /path/file.cpp:12:3: warning: foo
# msvc:   C:\path\file.cpp(12): warning C4244: foo
# msvc:   C:\path\file.cpp(12,3): warning C4244: foo   <- what UE 5.8 emits
#
# THE COLUMN IS OPTIONAL, and omitting it made this a DEAD GATE (found
# 2026-08-15). The toolchain UE 5.8 drives emits `file(line,col):`, which the
# `\((\d+)\)` form cannot match, so EVERY MSVC warning went uncounted:
# `warning_count` and `warning_count_agent_files` read 0 on every build, and
# `--strict-warnings` (registry.py: `l1.warning_count_agent_files > 0`) could
# not fire. Measured: all 63 reports of the 2026-08-15 reference sweep carry
# `warnings_in_agent_files: 0`, while the retained log of one of them holds
# `Source/ThirdPerson/PoisonEffect.cpp(34,2): warning C4996:` in an
# AGENT-WRITABLE file. No graded verdict was wrong -- the flag is off by default
# and no shipping task sets it -- but the count in every report was false and the
# gate was unfailable.
_WARNING_RE = re.compile(
    r"(?P<path>[^\s:()]+(?:\.h|\.cpp|\.hpp|\.cc|\.cxx))"  # source file
    r"(?:\((?P<msvc_line>\d+)(?:,\d+)?\)|:(?P<clang_line>\d+):\d+)"
    r"\s*:\s*"
    r"(?P<msg>warning(?:\s+[CW]\d+)?\s*:.*)",
    re.IGNORECASE,
)


def _is_windows_host(system: str) -> bool:
    """True for native Windows CPython (``Windows``) AND Git-Bash/MSYS2/Cygwin
    Python, which report ``MINGW64_NT-*`` / ``MSYS_NT-*`` / ``CYGWIN_NT-*``.
    Mirrors the host-family match in ``l2_pie._editor_binary`` so L1 and L2 agree
    on what counts as a Windows host (otherwise L1 aborts on a host L2 accepts)."""
    sys_l = system.lower()
    return sys_l.startswith("win") or sys_l.startswith(("cygwin", "msys", "mingw"))



def _spawn_forensics(exit_code: int, target: str) -> None:
    """Snapshot box state on a non-zero L1 target. Never raises, never gates."""
    try:
        import sys
        rig = pathlib.Path(__file__).resolve().parents[2] / "run-agent"
        if str(rig) not in sys.path:
            sys.path.insert(0, str(rig))
        from aura_rig import spawn_health
        spawn_health.snapshot(
            pathlib.Path(__file__).resolve().parents[3] / "runs",
            trigger=f"L1 target {target} exit {exit_code}")
    except Exception:
        pass

def _build_script(ue_root: Path) -> Path:
    system = platform.system()
    if system == "Darwin":
        return ue_root / "Engine" / "Build" / "BatchFiles" / "Mac" / "Build.sh"
    if system == "Linux":
        return ue_root / "Engine" / "Build" / "BatchFiles" / "Linux" / "Build.sh"
    if _is_windows_host(system):
        return ue_root / "Engine" / "Build" / "BatchFiles" / "Build.bat"
    raise RuntimeError(f"Unsupported host OS for UBT: {system}")


def _max_parallel_actions_args() -> list[str]:
    """``-MaxParallelActions=N`` from ``CRAFTBENCH_L1_MAX_PARALLEL``, else no cap.

    UE 5.8's editor-module PCH compiles are memory-heavy and UBT's default
    per-action memory heuristic under-estimates them, so on a RAM-constrained
    host a full-parallel build exhausts the commit charge and ``cl.exe`` fails
    PCH creation (error C3859 / "the paging file is too small"). Capping the
    parallel action count keeps peak memory bounded. Unset (the default) means
    no cap, so beefy CI hosts build at full speed unchanged."""
    raw = os.environ.get("CRAFTBENCH_L1_MAX_PARALLEL", "").strip()
    if not raw:
        return []
    # Leading-integer parse: a .env inline comment ("2 #tested up to 4") must
    # not silently drop the cap - that resurrects the exact C3859 failure the
    # knob exists to prevent (FAILURE-LOG 2026-07-24).
    m = re.match(r"[0-9]+", raw)
    if not m:
        print(f"WARNING: CRAFTBENCH_L1_MAX_PARALLEL={raw!r} has no leading "
              "number; building with NO parallel cap (C3859 risk)",
              file=sys.stderr)
        return []
    n = int(m.group())
    return [f"-MaxParallelActions={n}"] if n > 0 else []


def _platform_arg() -> str:
    system = platform.system()
    if system == "Linux":
        return "Linux"
    if _is_windows_host(system):
        return "Win64"
    # Darwin and anything unrecognized fall back to Mac (unchanged behavior).
    return "Mac"


_L1_TIMEOUT_DEFAULT = 1800.0

# Synthesized for a process-creation fault confirmed by retry, alongside the 127
# and 124 this module already invents (126 is POSIX for "found but could not be
# executed"). run_task routes it out of the denominator, so it is reachable ONLY
# through _spawn_produced_nothing below, and the route additionally requires
# L1Result.build_tool_never_ran: a submission owns Build.cs and can make the
# build tool exit any code it likes, and it can reach process creation distally
# by shaping the Editor build's peak memory. Provenance, never the code alone.
SPAWN_FAULT_EXIT = 126

# codesign's refusal line when bundle files carry extended attributes. macOS
# stamps every file this process tree creates with com.apple.provenance, and
# the Game target's Xcode finalize then refuses to sign the composed .app
# ("resource fork, Finder information, or similar detritus not allowed").
# Re-running UBT cannot heal it: xcodebuild regenerates Info.plist/Assets.car
# on every invocation, so the bundle is freshly restamped before its internal
# codesign runs (proven live 2026-07-22, FAILURE-LOG). The working repair is
# to finish UBT's last step ourselves: strip the composed bundle and re-run
# the exact codesign — the bundle is complete when the finalize dies at
# CodeSign, so a successful ad-hoc sign yields the same artifact UBT would
# have produced.
_DETRITUS_SIGNATURE = "detritus not allowed"


def _strip_xattrs(root: Path) -> None:
    """Best-effort `xattr -cr` over the workdir project tree (Darwin only)."""
    try:
        subprocess.run(
            ["xattr", "-cr", str(root)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
    except OSError:
        pass


def _manual_codesign_fallback(project_path: Path, target: str) -> tuple[bool, str]:
    """Complete a detritus-failed Xcode finalize: strip + ad-hoc sign the .app.

    Mirrors the finalize's own invocation (force, ad-hoc identity, project
    entitlements when present, entitlement DER) against the already-composed
    bundle. Returns (success, transcript)."""
    app = project_path.parent / "Binaries" / "Mac" / f"{target}.app"
    if not app.is_dir():
        return False, f"manual codesign: bundle missing at {app}\n"
    _strip_xattrs(app)
    cmd = ["/usr/bin/codesign", "--force", "--sign", "-"]
    xcents = sorted((project_path.parent / "Binaries").glob(
        f"{target} (*).build/*/{target}.build/*.xcent"))
    if xcents:
        cmd += ["--entitlements", str(xcents[0])]
    cmd += ["--timestamp=none", "--generate-entitlement-der", str(app)]
    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, check=False,
        )
    except OSError as e:
        return False, f"manual codesign: exec failed ({e})\n"
    transcript = f"$ {' '.join(cmd)}\n{proc.stdout or ''}"
    return proc.returncode == 0, transcript


def _binaries_state(project_path: Path) -> dict:
    """``{relative path: (size, mtime_ns)}`` for the project's ``Binaries`` tree.

    The pre-spawn half of "did this invocation do any WORK". Compared as a SET
    rather than against a clock reading, because a clock reading is not sound
    here: ``time.time()`` resolves to sub-microsecond, while a file's mtime is
    stamped from the system clock at its own granularity, so a file written
    immediately AFTER a ``time.time()`` call can carry an mtime BELOW it.
    Measured on this box, 2026-08-24: 2830 of 4000 writes did exactly that, by
    up to 1.6 ms. Under ``st_mtime >= started_at`` those writes are invisible,
    so a spawn that wrote a build product inside that window reads as one that
    never ran — and this predicate is half of the route that takes such a
    target OUT of the denominator. It made
    ``test_a_build_that_wrote_a_product_is_never_retried`` fail on one CI leg
    while the other two passed on identical bytes.

    A set comparison also keeps the property the clock version was reaching for:
    the previous target's products, and a warm slot's, are already IN the
    snapshot, so they cannot mask a later target's fault — and it needs no
    slack, so the Editor target's writes landing milliseconds before the Game
    target's spawn are still attributed correctly.

    Unreadable entries are recorded as ``None`` rather than skipped: a file that
    could not be stat'd before and can be after IS a change.
    """
    out: dict = {}
    root = project_path.parent / "Binaries"
    try:
        for p in root.rglob("*"):
            try:
                key = str(p.relative_to(root)).replace("\\", "/")
            except ValueError:
                continue
            try:
                st = p.stat()
                out[key] = (st.st_size, st.st_mtime_ns)
            except OSError:
                out[key] = None
    except OSError:
        pass
    return out


def _spawn_produced_nothing(
    r: "_SingleTargetResult", project_path: Path, before: dict
) -> bool:
    """True when a failing UBT invocation left no trace at all.

    Both conjuncts are required. UBT prints its banner and target list before it
    schedules the first action, so any invocation that reached the toolchain has
    output — that is the conjunct keeping this out of a submission's reach. The
    second asks whether the spawn did any WORK, by comparing the ``Binaries``
    tree against the snapshot ``before`` the spawn (see :func:`_binaries_state`
    for why this is a set difference and not a timestamp cutoff).
    """
    if r.exit_code == 0 or r.output.strip():
        return False
    return _binaries_state(project_path) == before


def _env_l1_timeout() -> float:
    """Per-target UBT timeout (seconds) for the governed Popen path only.

    Read from ``CRAFTBENCH_L1_TIMEOUT``; falls back to 30 min on
    absence/parse-miss. Only consulted when the Job-Object governor is enabled
    (``job is not None``); the default ``subprocess.run`` path is never bounded
    by a timeout, preserving historical behavior."""
    try:
        return float(str(os.environ.get("CRAFTBENCH_L1_TIMEOUT", "")).strip())
    except (TypeError, ValueError):
        return _L1_TIMEOUT_DEFAULT


@dataclass
class _SingleTargetResult:
    """Internal: outcome of one UBT invocation."""

    target: str
    exit_code: int
    output: str  # captured stdout+stderr
    duration_seconds: float
    note: str  # one-line summary suitable for L1Result.notes


def run_l1(
    *,
    ue_root: Path,
    project_path: Path,
    game_module: str,
    log_path: Path,
    extra_env: Optional[dict[str, str]] = None,
    agent_writable_prefixes: Iterable[str] = (),
) -> L1Result:
    """Execute UBT for both the Editor and Game targets, return an L1Result.

    Parameters
    ----------
    ue_root:
        Root of the UE installation (the directory that contains ``Engine/``).
    project_path:
        Absolute path to the ``.uproject`` file in the workdir copy.
    game_module:
        The game module name. The Editor target is ``<Module>Editor`` and
        the Game target is ``<Module>``; both are built and both must
        exit 0 for L1 to pass.
    log_path:
        Where to dump combined stdout+stderr from UBT. Per-target sections
        are prefixed with ``=== L1 target: <name> ===`` headers.
    agent_writable_prefixes:
        Repo-relative prefixes (POSIX) the agent may write to; warnings
        whose path lies under one of these prefixes are counted toward
        ``warning_count_agent_files``.
    """
    notes: list[str] = []
    build_tool_never_ran = False
    script = _build_script(ue_root)
    if not script.exists():
        notes.append(f"UBT script missing at {script}")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            f"L1 ABORTED: UBT script not found at {script}\n", encoding="utf-8"
        )
        return L1Result(
            status="fail",
            exit_code=127,
            log_path=log_path,
            duration_seconds=0.0,
            warning_count=0,
            warning_count_agent_files=0,
            notes=notes,
            build_tool_never_ran=True,
        )

    log_path.parent.mkdir(parents=True, exist_ok=True)
    targets = (f"{game_module}Editor", game_module)
    sections: list[str] = []
    results: list[_SingleTargetResult] = []
    # Job-Object backstop (Windows + CRAFTBENCH_GOVERN_RESOURCES only; a no-op
    # passthrough otherwise). One job spans both UBT invocations so the entire
    # cl.exe tree is reaped on context exit. When disabled, ``_job`` is None and
    # ``_run_one_target`` takes its existing ``subprocess.run`` path unchanged.
    # Serialize the compile window against other CraftBench builds. Build.bat's
    # own mutex is keyed on the ENGINE INSTALL, so unrelated projects contend and
    # the loser returns exit 1 with no compile errors — a graded FAIL on correct
    # work (reproduced 2026-07-31). This lock is MONOTONE: on timeout, a hostile
    # lock path, or any OS refusal it yields held=False and we build exactly as
    # before, so it can never change a verdict class. See build_lock.py.
    #
    # It wraps resource_job (rather than the reverse) so the job object — which
    # reaps the cl.exe tree — is the inner, shorter-lived resource, and so the
    # lock is released the moment the last target finishes.
    with ubt_build_lock(ue_root, log=lambda m: print(f"info: {m}")) as _blk, \
            resource_job(memory_limit_mb=L1_MEM_MB, name="cb-l1") as _job:
        _lock_note = _blk.note
        if _lock_note:
            notes.append(_lock_note)
        for target in targets:
            before = _binaries_state(project_path)
            r = _run_one_target(
                script=script,
                target=target,
                project_path=project_path,
                extra_env=extra_env,
                job=_job,
            )
            # Nothing printed and nothing written means the process was never
            # created. Re-spawn once so a transient heals into a real verdict;
            # only a reproduced no-trace failure is a machine fault. Snapshot the
            # box FIRST: the state that explains a spawn death is gone seconds
            # later, and a healed retry would otherwise discard the only evidence
            # of it.
            if _spawn_produced_nothing(r, project_path, before):
                _spawn_forensics(r.exit_code, r.target)
                sections.append(
                    f"\n=== L1 target: {r.target} (exit {r.exit_code}, "
                    f"{r.duration_seconds:.1f}s — zero output, no build product; "
                    "retrying the spawn once) ===\n"
                )
                notes.append(
                    f"target {r.target}: exit {r.exit_code} wrote no output and "
                    "no build product — retrying the spawn once"
                )
                # Re-snapshotted, not reused: the first spawn is the one being
                # judged as having written nothing, so `before` from it would
                # answer a question about the wrong invocation the moment the
                # first spawn did in fact write.
                before = _binaries_state(project_path)
                retry = _run_one_target(
                    script=script,
                    target=target,
                    project_path=project_path,
                    extra_env=extra_env,
                    job=_job,
                )
                if _spawn_produced_nothing(retry, project_path, before):
                    build_tool_never_ran = True
                    retry = _SingleTargetResult(
                        target=retry.target,
                        exit_code=SPAWN_FAULT_EXIT,
                        output=(
                            f"L1 spawn fault: target {retry.target} exited "
                            f"{retry.exit_code} with zero output and no build "
                            "product on two consecutive spawns\n"
                        ),
                        duration_seconds=retry.duration_seconds,
                        note=(f"target {retry.target}: process creation failed "
                              f"twice (observed exit {retry.exit_code}) — "
                              "machine fault, not graded"),
                    )
                r = retry
            # Darwin self-heal: a detritus codesign failure is environmental
            # (com.apple.provenance xattrs on files the harness created), not a
            # submission defect. The bundle is fully composed when the finalize
            # dies at CodeSign, so first finish that one step ourselves
            # (strip + ad-hoc sign — a whole-UBT retry can never work, see
            # _DETRITUS_SIGNATURE); fall back to one full UBT retry only if
            # the manual sign fails.
            if (r.exit_code != 0 and platform.system() == "Darwin"
                    and _DETRITUS_SIGNATURE in r.output):
                sections.append(
                    f"\n=== L1 target: {r.target} (exit {r.exit_code}, "
                    f"{r.duration_seconds:.1f}s — detritus codesign failure, "
                    f"attempting harness finalize) ===\n" + r.output
                )
                signed, transcript = _manual_codesign_fallback(
                    project_path, target)
                sections.append(
                    f"\n=== L1 target: {r.target} (harness codesign "
                    f"{'OK' if signed else 'FAILED'}) ===\n" + transcript
                )
                if signed:
                    notes.append(
                        f"target {r.target}: UBT finalize failed on detritus "
                        "xattrs — harness completed the codesign after an "
                        "xattr strip (environmental repair)"
                    )
                    r = _SingleTargetResult(
                        target=r.target, exit_code=0, output=transcript,
                        duration_seconds=r.duration_seconds,
                        note=(f"target {r.target}: pass via harness codesign "
                              "(detritus repair)"),
                    )
                else:
                    notes.append(
                        f"target {r.target}: detritus codesign failure — "
                        "manual sign failed, stripped xattrs and retried once"
                    )
                    _strip_xattrs(project_path.parent)
                    r = _run_one_target(
                        script=script,
                        target=target,
                        project_path=project_path,
                        extra_env=extra_env,
                        job=_job,
                    )
            results.append(r)
            sections.append(
                f"\n=== L1 target: {r.target} (exit {r.exit_code}, {r.duration_seconds:.1f}s) ===\n"
                + r.output
            )
            notes.append(r.note)
            # Short-circuit on the first failing target: log it but skip the
            # next target since downstream layers are gated on L1 success and
            # the second UBT invocation only adds wallclock without changing
            # the outcome.
            if r.exit_code != 0:
                # DIAGNOSTIC ONLY, fail-open, no effect on the verdict. 0xC0000142
                # (3221225794) means the child died in DLL init before running its
                # own code, so the box state AT THIS INSTANT is the only evidence
                # that exists — and it is gone seconds later: measured 2026-08-21,
                # free physical RAM went 0.18 GB -> 18.13 GB in the time between two
                # samples while commit stayed >26 GB free. Prior analyses checked
                # commit, found it healthy, and concluded "not memory".
                _spawn_forensics(r.exit_code, r.target)
                break

    log_path.write_text("".join(sections), encoding="utf-8")
    total_duration = sum(r.duration_seconds for r in results)
    last_nonzero = next((r.exit_code for r in reversed(results) if r.exit_code != 0), 0)
    total_warnings, agent_warnings = _count_warnings(log_path, agent_writable_prefixes)
    all_pass = all(r.exit_code == 0 for r in results) and len(results) == len(targets)
    return L1Result(
        status="pass" if all_pass else "fail",
        exit_code=last_nonzero,
        log_path=log_path,
        duration_seconds=total_duration,
        warning_count=total_warnings,
        warning_count_agent_files=agent_warnings,
        notes=notes,
        build_tool_never_ran=build_tool_never_ran,
    )


def _run_one_target(
    *,
    script: Path,
    target: str,
    project_path: Path,
    extra_env: Optional[dict[str, str]],
    timeout: Optional[float] = None,
    job=None,
) -> _SingleTargetResult:
    """Invoke UBT once for a single target and return the outcome.

    Two code paths, default-off:

    - ``job is None`` (the governor is disabled — the only path when
      ``CRAFTBENCH_GOVERN_RESOURCES`` is unset or off Windows): runs the
      historical ``subprocess.run(...)`` **byte-for-byte unchanged**, with no
      timeout. This is the default and keeps existing behavior identical.
    - ``job is not None`` (governor enabled): spawns via ``Popen`` so the pid
      can be assigned to the Job Object before it forks ``cl.exe`` children,
      then ``communicate(timeout=...)``. ``timeout`` defaults to the env
      ``CRAFTBENCH_L1_TIMEOUT`` else 1800s; on ``TimeoutExpired`` the tree is
      killed (the Job Object reaps the rest on close) and a clean
      build-FAILED result with reason "L1 build timed out" is returned.
    """
    cmd = [
        str(script),
        target,
        _platform_arg(),
        "Development",
        f"-project={project_path}",
        # Disable Unreal Build Accelerator. UE 5.8 enables UBA by default, but
        # its shared cross-run content store (C:\ProgramData\Epic\
        # UnrealBuildAccelerator\cas\) crashes the build with an access
        # violation (exit 0xC0000005) when a prior build was killed mid-flight
        # — which the resource governor / L1 timeout do by design — leaving the
        # store "not gracefully shutdown". Beyond the crash, shared mutable
        # cross-run state is wrong for a deterministic, isolated verifier. -NoUBA
        # runs actions locally (the UE 5.7 behaviour) and is a valid UBT flag on
        # the engines CraftBench targets (5.7/5.8). Set CRAFTBENCH_ALLOW_UBA=1 to
        # opt back in (e.g. a maintainer benchmarking build speed).
        *([] if os.environ.get("CRAFTBENCH_ALLOW_UBA", "").strip() in ("1", "true", "True")
          else ["-NoUBA"]),
        # OPT-IN because unity does not currently compile against this corpus:
        # merging .cpp files merges their unnamed namespaces, and file-scope
        # names collide across files of the same module. It is worth having
        # because UBT's adaptive-unity heuristic excludes EVERY file here — a
        # workdir staged by `git archive | tar -x` has no .git, and an installed
        # engine then routes SourceFileWorkingSet.Create to the Perforce
        # provider, whose "in the working set" test is "not read-only", which
        # every extracted file satisfies.
        *(["-DisableAdaptiveUnity"]
          if os.environ.get("CRAFTBENCH_DISABLE_ADAPTIVE_UNITY", "").strip()
          in ("1", "true", "True") else []),
        # Cap parallel actions on RAM-constrained hosts (default: no cap) to avoid
        # UE 5.8 PCH C3859 / paging exhaustion — see _max_parallel_actions_args.
        *_max_parallel_actions_args(),
        "-waitmutex",
    ]
    # Windows: Build.bat is a batch file; CreateProcess (shell=False) cannot
    # exec it directly. Wrap it with ``cmd /c`` so cmd.exe interprets the
    # batch file. ``shell=False`` is preserved on all platforms; macOS/Linux
    # invoke Build.sh directly (unchanged).
    if platform.system() == "Windows":
        cmd = ["cmd", "/c"] + cmd
    start = time.monotonic()

    # DEFAULT PATH (governor disabled): unchanged from the historical
    # behavior — a plain blocking subprocess.run with no timeout.
    if job is None:
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                # UBT/MSVC emit ANSI-codepage bytes on localized Windows; a
                # strict decode kills the reader thread mid-build.
                encoding="utf-8",
                errors="replace",
                env=extra_env,
                check=False,
            )
            duration = time.monotonic() - start
            return _SingleTargetResult(
                target=target,
                exit_code=proc.returncode,
                output=proc.stdout or "",
                duration_seconds=duration,
                note=f"target {target}: exit {proc.returncode} in {duration:.1f}s",
            )
        except FileNotFoundError as e:
            duration = time.monotonic() - start
            return _SingleTargetResult(
                target=target,
                exit_code=127,
                output=f"L1 ABORTED for target {target}: {e}\n",
                duration_seconds=duration,
                note=f"target {target}: exec failed ({e})",
            )

    # GOVERNED PATH (governor enabled): Popen so we can assign the pid to the
    # Job Object before it forks its compile children, then communicate with a
    # timeout backstop.
    if timeout is None:
        timeout = _env_l1_timeout()
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=extra_env,
        )
    except FileNotFoundError as e:
        duration = time.monotonic() - start
        return _SingleTargetResult(
            target=target,
            exit_code=127,
            output=f"L1 ABORTED for target {target}: {e}\n",
            duration_seconds=duration,
            note=f"target {target}: exec failed ({e})",
        )

    assign(job, proc.pid)
    try:
        out, _ = proc.communicate(timeout=timeout)
        duration = time.monotonic() - start
        return _SingleTargetResult(
            target=target,
            exit_code=proc.returncode,
            output=out or "",
            duration_seconds=duration,
            note=f"target {target}: exit {proc.returncode} in {duration:.1f}s",
        )
    except subprocess.TimeoutExpired:
        # Kill the immediate process; the Job Object's KILL_ON_JOB_CLOSE reaps
        # any surviving compile descendants when the context manager closes.
        try:
            proc.kill()
        except Exception:  # noqa: BLE001 — kill is best-effort
            pass
        try:
            out, _ = proc.communicate(timeout=30)
        except Exception:  # noqa: BLE001 — drain is best-effort
            out = ""
        duration = time.monotonic() - start
        return _SingleTargetResult(
            target=target,
            exit_code=124,
            output=(out or "")
            + f"\nL1 build timed out for target {target} after {timeout:.0f}s\n",
            duration_seconds=duration,
            note=f"target {target}: L1 build timed out after {timeout:.0f}s",
        )


def _count_warnings(log_path: Path, prefixes: Iterable[str]) -> tuple[int, int]:
    """Return (total, agent_filtered)."""
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0, 0
    prefixes = tuple(p for p in prefixes if p)
    total = 0
    agent = 0
    for line in text.splitlines():
        m = _WARNING_RE.search(line)
        if not m:
            continue
        total += 1
        path = m.group("path").replace("\\", "/")
        if prefixes and any(p in path for p in prefixes):
            agent += 1
    return total, agent
