"""L2 — AFunctionalTest in PIE via UnrealEditor-Cmd automation harness.

The runner spawns ``UnrealEditor-Cmd`` against the project's ``.uproject``
and asks the automation framework to run a specific filter::

    <UE_ROOT>/Engine/Binaries/<Platform>/UnrealEditor-Cmd \\
        <project>.uproject \\
        -ExecCmds="Automation RunTests <TestFilter>; Quit" \\
        -ReportOutputPath="<workdir>/out/l2_report" \\
        -unattended -nopause -nullrhi -log -stdout \\
        -fullstdoutlogoutput -testexit="Automation Test Queue Empty"

Result signal
-------------
**Primary**: ``index.json`` written under ``-ReportOutputPath`` contains
per-test ``state`` plus ``succeeded``/``failed`` counts. Authoritative
when present.

**Fallback**: ``Test Completed. Result={Passed|Failed|Skipped}`` lines
in the captured stdout. Used only if ``index.json`` is missing or
unparseable (e.g. editor died before flush).

Important: the UE editor process exits 0 even on test failure. Exit
code is **not** a reliable pass/fail signal — only the JSON/stdout are.

ASSUMPTIONS (recheck when broadening beyond the current UE 5.8 pin):
1. ``-ReportOutputPath`` writes ``index.json`` with the ``{ succeeded,
   failed, tests: [{ state: "Success"|"Fail"|"NotRun"|"InProcess",
   fullTestPath, testDisplayName }] }`` shape. Confirmed in
   UE 4.x..5.x community references; not pinned to a release-notes
   line.
2. The exact automation-test filter syntax. Default derivation:
   ``Project.Functional Tests./Game/Maps/<MapName>.<TestActorName>``.
   Callers override via ``test_filter``.
3. The exact ``-testexit`` flag spelling. Drop it and rely on ``Quit``
   in ``-ExecCmds`` if the editor hangs after tests finish.
4. ``-nullrhi`` is safe for L_SanityTask. If a future test needs a
   real viewport, call ``run_l2(use_nullrhi=False)``.
"""

from __future__ import annotations

import json
import platform
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


_RESULT_RE = re.compile(
    r"Test\s+Completed\.\s+Result=\{(?P<result>Passed|Failed|Skipped)\}",
    re.IGNORECASE,
)
# Locale-stable per-test signal — UE always emits this in English even when
# the editor UI is localized (Chinese, Japanese, etc.).
_TEST_RESULT_RE = re.compile(
    r"TestResult=(?P<result>Passed|Failed|Skipped)", re.IGNORECASE
)
_SUCCEEDED_RE = re.compile(r"Automation Test Succeeded", re.IGNORECASE)
_FAILED_RE = re.compile(r"Automation Test Failed", re.IGNORECASE)


@dataclass
class L2Result:
    status: str  # "pass" | "fail" | "skipped"
    log_path: Path
    duration_seconds: float
    tests_run: int
    tests_passed: int
    tests_failed: int
    tests_skipped: int
    notes: list[str]
    exit_code: int
    report_path: Optional[Path] = None
    result_source: str = "unknown"  # "json" | "stdout-fallback" | "none"
    # True when the editor could not obtain a GPU resource (see _RHI_OOM_MARKERS).
    # STRUCTURAL, computed HERE where the log is already in hand, so the verdict
    # layer never has to read note prose to tell a machine fault from agent code.
    rhi_unavailable: bool = False
    # True when the editor QUEUED the requested test and exited before starting
    # it — our own `; Quit` racing the automation controller. Same doctrine as
    # rhi_unavailable: structural, computed here, never inferred from prose.
    queued_never_started: bool = False
    # True when a fixture finished through EFunctionalTestResult::Error, i.e. it
    # declared that the HARNESS could not set the test up. MATCHED from the
    # engine's own FunctionalTest emission (AFunctionalTest::FinishTest ->
    # AddError, FunctionalTest.cpp:471), not from our note prose.
    #
    # NOT unspoofable, and it must not be documented as if it were: agent C++
    # runs in this process and writes this same log, so a submission could emit a
    # look-alike line. Anchoring on the engine's exact format REDUCES that, and
    # two further things bound the damage — see _harness_precondition for the
    # residual-risk argument, which is what makes the reduction acceptable rather
    # than merely hopeful.
    #
    # The corpus-wide invariant that makes this safe to route on was established
    # by the 2026-08-14 ::Error audit (the ::Error tag audit): every
    # ::Error whose guard read agent-writable state was retagged ::Failed, so the
    # 32 survivors mean exactly one thing. Any NEW ::Error must satisfy the same
    # rule or this predicate starts excusing submissions.
    harness_precondition: bool = False
    # True when the editor process produced NO OUTPUT AT ALL — an empty/absent
    # log — while exiting non-zero on something other than the governed timeout.
    # It never reached the point of opening its own log file, so it never ran the
    # test and never ran the submission.
    #
    # THE PROPERTY THAT MAKES THIS THE STRONGEST SIGNAL IN THIS DATACLASS: unlike
    # rhi_unavailable / harness_precondition / queued_never_started, it does not
    # read log TEXT, so agent C++ cannot spoof it. Those three match strings in a
    # log the submission's own code can write (see _harness_precondition's
    # residual-risk argument). This one keys on the ABSENCE of the log, and agent
    # code only executes after the process has initialised and opened it. A
    # submission cannot cause its own emptiness.
    #
    # Measured shape, 2026-08-17 (runs/bare/…-t0-sanity-log-on-beginplay-bare-
    # deepseek_deepseek-v4-pro): both legs 0 bytes, NO UECC dump, tests_run 0,
    # exit 3221225794 = 0xC0000142 STATUS_DLL_INIT_FAILED. L1 had PASSED, so the
    # submission compiled; the editor simply never started. That run recorded
    # `overall: FAIL` and charged it to the model, with all three sibling flags
    # False — i.e. exactly the bias the denominator rule exists to prevent, on
    # a signal nothing was watching for.
    editor_never_started: bool = False


# Markers that indicate the editor has finished the requested work. On
# macOS the wait past this point is just the known UE-Mac "RequestExit
# ignored" Cocoa-runloop hang; on Windows/Linux the editor usually exits on
# its own and the marker-kill simply short-circuits the wait. The marker-kill
# approach itself is platform-agnostic (see _run_editor_with_marker_kill) and
# is primarily *needed* on macOS, but it is safe and correct on every host.
# Used as the default set by run_l2 and the sibling editor-driving modules.
DEFAULT_TERMINAL_MARKERS: tuple[str, ...] = (
    "**** TEST COMPLETE. EXIT CODE:",
    "FPlatformMisc::RequestExit",
    "LogExit: Exiting.",
)


def run_editor_with_marker_kill(
    *,
    cmd: list[str],
    env: Optional[dict[str, str]],
    log_path: Path,
    timeout_seconds: float,
    extra_markers: tuple[str, ...] = (),
) -> tuple[int, bool]:
    """Public wrapper for the marker-kill streaming Popen pattern.

    ``run_l2``, ``l2_introspect.py`` and ``asset_capture.py`` all route their
    editor subprocess through here and so inherit any fix made in this
    module. The pattern is platform-agnostic — we tail stdout for terminal
    markers and kill on first match — but it is primarily *needed* on macOS,
    where the editor doesn't honor ``RequestExit`` cleanly and otherwise sits
    forever in a Cocoa runloop. On Windows/Linux the editor typically exits
    on its own, so the marker-kill just short-circuits the wait.
    ``extra_markers`` lets callers add domain-specific signals (e.g. a
    script's own "done" line).
    """
    return _run_editor_with_marker_kill(
        cmd=cmd,
        env=env,
        log_path=log_path,
        timeout_seconds=timeout_seconds,
        markers=DEFAULT_TERMINAL_MARKERS + extra_markers,
    )


# Keep the original private alias name in use internally — saves churning
# every existing call site.
_TERMINAL_MARKERS = DEFAULT_TERMINAL_MARKERS


def _run_editor_with_marker_kill(
    *,
    cmd: list[str],
    env: Optional[dict[str, str]],
    log_path: Path,
    timeout_seconds: float,
    markers: tuple[str, ...] = DEFAULT_TERMINAL_MARKERS,
) -> tuple[int, bool]:
    """Run ``cmd`` streaming stdout to ``log_path``; kill on terminal marker.

    Returns ``(exit_code, killed_on_marker)``. Raises ``TimeoutExpired`` if
    the deadline passes before we see a terminal marker.

    Background: UE on macOS often calls ``RequestExit`` after automation
    completes, prints a "TEST COMPLETE" line, then sits in a Cocoa runloop
    that never actually returns. We tail stdout line-by-line, and once any
    of the ``_TERMINAL_MARKERS`` appears we terminate the process (followed
    by a hard kill after a grace period). Up to that point the captured log
    contains everything the editor wrote, so the JSON report and stdout
    parse paths still work.

    Termination is platform-agnostic: ``proc.terminate()`` / ``proc.kill()``
    map to ``SIGTERM`` / ``SIGKILL`` on POSIX and to ``TerminateProcess`` on
    Windows (Python 3.3+), so no host-specific signaling is needed here. The
    marker-kill itself is primarily *needed* on macOS (the RequestExit /
    Cocoa-runloop hang); on Windows/Linux the editor usually exits cleanly
    and this just short-circuits the post-test wait.
    """
    import os
    import signal

    from job_governor import resource_job, assign, L2_MEM_MB, IS_WINDOWS

    # Opt-in resource backstop (default-off; no-op unless the governor env is set
    # AND we are on Windows). When active, the editor process tree is assigned to
    # a Job Object that KILL_ON_JOB_CLOSE-reaps the whole tree on context exit.
    # CREATE_NEW_PROCESS_GROUP is applied ONLY when the governor is actually
    # active (_job is not None) so the default path stays byte-identical to before
    # — on POSIX, or with the governor off, the flag is 0.
    with resource_job(memory_limit_mb=L2_MEM_MB, name="cb-l2") as _job:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            # editor output may carry ANSI-codepage bytes on localized Windows
            encoding="utf-8",
            errors="replace",
            bufsize=1,  # line-buffered
            env=env,
            creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP
                           if (IS_WINDOWS and _job is not None) else 0),
        )
        assign(_job, proc.pid)
        deadline = time.monotonic() + timeout_seconds
        killed_on_marker = False
        # Write incrementally so a partial log is available if anything wedges.
        with log_path.open("w", encoding="utf-8") as fh:
            assert proc.stdout is not None
            for line in proc.stdout:
                fh.write(line)
                fh.flush()
                if any(m in line for m in markers):
                    killed_on_marker = True
                    # KEEP DRAINING while the editor shuts down.
                    #
                    # This used to call proc.wait(timeout=8.0) right here —
                    # INSIDE `for line in proc.stdout`. That stops consuming the
                    # very pipe it is waiting on: the editor writes ~2.7 KB more
                    # of shutdown log, fills the OS buffer, blocks in WriteFile,
                    # and can therefore NEVER exit. The grace could not succeed,
                    # so it expired every single time and we TerminateProcess'd.
                    #
                    # Measured on this box: L2I paid 8.23s (warm) / 8.25s (cold)
                    # after the verdict was already captured — the two agree to
                    # 0.02s of each other and of the 8.0s constant, which is what
                    # a timeout looks like and a variable shutdown does not. The
                    # editor's own Saved/Logs copy ran 2,728 bytes LONGER than
                    # ours and ended mid-shutdown with no "LogExit: Exiting."
                    #
                    # (L2 never showed this because the automation path force-exits
                    # via RequestExitWithStatus, while -ExecutePythonScript ends in
                    # QUIT_EDITOR -> UUnrealEdEngine::CloseEditor(), the graceful
                    # path that keeps logging.)
                    #
                    # A reader THREAD is required, not a second inline loop: the
                    # iterator blocks until a line arrives, so a deadline checked
                    # between lines cannot fire against a child that has stopped
                    # writing. Draining concurrently lets wait() actually return.
                    def _drain_tail() -> None:
                        try:
                            for tail in proc.stdout:  # runs to EOF
                                fh.write(tail)
                                fh.flush()
                        except (ValueError, OSError):
                            pass  # fh closed / pipe torn down — nothing to save

                    drainer = threading.Thread(target=_drain_tail, daemon=True)
                    drainer.start()
                    try:
                        proc.wait(timeout=8.0)
                    except subprocess.TimeoutExpired:
                        pass
                    # Joined BEFORE the enclosing `with` closes fh, so the thread
                    # can never write into a closed file.
                    drainer.join(timeout=2.0)
                    if proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=5.0)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait()
                    break
                if time.monotonic() > deadline:
                    # Hand the partial output back via TimeoutExpired so the
                    # caller's existing error path keeps working.
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass
                    proc.wait()
                    raise subprocess.TimeoutExpired(
                        cmd=cmd,
                        timeout=timeout_seconds,
                        output=log_path.read_text(encoding="utf-8", errors="replace"),
                    )
            # If the loop exited because stdout closed (proc terminating naturally),
            # wait out the process so we get a real exit code.
            if not killed_on_marker:
                try:
                    proc.wait(timeout=max(0.0, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                    raise

    return (proc.returncode if proc.returncode is not None else -1, killed_on_marker)


def editor_binary(ue_root: Path) -> Path:
    """Public alias for ``_editor_binary``; used by sibling modules
    (l2_introspect, asset_capture) that need the same path."""
    return _editor_binary(ue_root)


def _editor_binary(ue_root: Path) -> Path:
    system = platform.system()
    # Mac branch first, kept as an EXACT match so macOS behavior is byte-identical.
    if system == "Darwin":
        # UE 5.7 launcher layout: flat Engine/Binaries/Mac/UnrealEditor-Cmd
        # (a Mach-O executable directly, not inside a .app bundle).
        flat = ue_root / "Engine" / "Binaries" / "Mac" / "UnrealEditor-Cmd"
        if flat.exists():
            return flat
        # Older UE 5.x and some source builds nest it inside the bundle.
        bundle = (
            ue_root
            / "Engine"
            / "Binaries"
            / "Mac"
            / "UnrealEditor.app"
            / "Contents"
            / "MacOS"
            / "UnrealEditor-Cmd"
        )
        return bundle  # caller checks .exists() and reports a clear error
    if system == "Linux":
        return ue_root / "Engine" / "Binaries" / "Linux" / "UnrealEditor-Cmd"
    # Case-insensitive Windows detection. platform.system() returns "Windows"
    # on a native Python build, but a Git-Bash / Cygwin / MSYS Python reports
    # "CYGWIN_NT-10.0", "MSYS_NT-10.0", "MINGW64_NT-10.0", etc. — all of which
    # are still Win64 hosts that ship UnrealEditor-Cmd.exe. Match the family by
    # lowercased prefix so those shells resolve the right binary instead of
    # falling through to the RuntimeError below.
    sys_l = system.lower()
    if sys_l.startswith("win") or sys_l.startswith(("cygwin", "msys", "mingw")):
        return ue_root / "Engine" / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe"
    raise RuntimeError(f"Unsupported host OS for editor: {system}")


def run_l2(
    *,
    ue_root: Path,
    project_path: Path,
    test_filter: str,
    log_path: Path,
    report_dir: Optional[Path] = None,
    map_name: Optional[str] = None,
    map_package_path: Optional[str] = None,
    use_nullrhi: bool = True,
    fps: int = 60,
    timeout_seconds: float = 600.0,
    extra_env: Optional[dict[str, str]] = None,
    capture: bool = False,
    expected_test_count: Optional[int] = None,
    extra_args: Optional[list[str]] = None,
    render_offscreen: bool = False,
) -> L2Result:
    """Run a single automation-test filter and parse the result.

    If ``report_dir`` is provided, pass ``-ReportOutputPath`` and parse
    ``index.json`` for authoritative pass/fail. Falls back to parsing
    stdout if the JSON is missing or unparseable.

    ``expected_test_count`` (opt-in leg-count guard): when given, PASS
    additionally requires that the parsed ``tests_run`` equals it — the
    caller threads the number of DECLARED fixtures (multi-fixture ``+``
    filters run in one editor session; a silently dropped leg must grade
    FAIL, not PASS). ``None`` keeps the legacy gate byte-identical.

    ``map_package_path`` (opt-in) is the DISCOVERED ``/Game/...`` package
    path of the map (map_locator.MapLocation.package_path) and is used
    VERBATIM as the editor's positional map argument — needed once maps may
    live one folder deep under ``Content/Maps/``. When ``None``, the legacy
    flat form ``/Game/Maps/<map_name>`` is derived from ``map_name``
    (which stays for logging/back-compat).

    ``capture=True`` (opt-in) appends ``-CraftBenchCapture`` to the editor
    command line — the substrate-side hook that makes fixtures write
    screenshots to ``Saved/CraftBench/``. Nothing else changes; the
    determinism switches (``-deterministic``, ``-FPS``) are never dropped.

    ``extra_args`` (opt-in) appends verbatim command-line switches (e.g.
    ``["-NoScreenMessages"]`` so on-screen debug text never lands in captured
    pixels). ``None`` keeps the command byte-identical. NB: never prefix
    extra console commands into ``-ExecCmds`` instead — UE does not split
    that value on semicolons; a prefixed command swallows the whole line and
    the automation never starts (proven live 2026-07-22, FAILURE-LOG).

    ``render_offscreen=True`` (opt-in) appends ``-RenderOffScreen`` — real-RHI
    rendering with window creation suppressed. The certified verifier legs
    never pass it (their real-RHI runs just omit ``-nullrhi``); it exists for
    the review-capture path and for task authoring scripts.
    """
    notes: list[str] = []
    editor = _editor_binary(ue_root)
    if not editor.exists():
        notes.append(f"editor binary missing at {editor}")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            f"L2 ABORTED: editor not found at {editor}\n", encoding="utf-8"
        )
        return L2Result(
            status="fail",
            log_path=log_path,
            duration_seconds=0.0,
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            tests_skipped=0,
            notes=notes,
            exit_code=127,
            report_path=None,
            result_source="none",
        )

    cmd: list[str] = [
        str(editor),
        str(project_path),
    ]
    # Prefer the DISCOVERED package path (maps may sit one folder deep under
    # Content/Maps/ after the folder-per-task migration); fall back to the
    # legacy flat form derived from map_name.
    map_positional = map_package_path or (
        f"/Game/Maps/{map_name}" if map_name else None
    )
    if map_positional:
        # Open the test map as the active level. Combined with the fixture
        # base's IsEditorOnlyLoadedInPIE()->true override (ACraftBenchFunctionalTest),
        # the `Project.Functional Tests.Maps.<MapName>.<TestName>` automation test
        # opens the map in a REAL PIE world (BeginPlay auto-fires; FTimerManager and
        # CharacterMovement tick) instead of Editor World. Empirically validated —
        # recipes in docs/pie-verification-playbook.md (the original spike doc
        # was deleted with the specs tree; git history).
        cmd.append(map_positional)
    cmd.extend([
        f"-ExecCmds=Automation RunTests {test_filter}; Quit",
        "-unattended",
        "-nopause",
        "-nosplash",
        "-nosound",
        # Fixed timestep from frame 0 for deterministic checkpoint timing.
        # `fps` sets the per-frame dt (1/fps); callers pass a non-60 value to drive
        # framerate-independence legs (e.g. fps=20 for the Timer 20Hz leg). A console
        # var in -ExecCmds was tried first but prevented PIE from starting.
        "-deterministic",
        f"-FPS={fps}",
        "-log",
        "-stdout",
        "-fullstdoutlogoutput",
        "-testexit=Automation Test Queue Empty",
    ])
    if use_nullrhi:
        cmd.insert(3 if map_positional else 2, "-nullrhi")
    if render_offscreen:
        # Opt-in (position not load-bearing): real-RHI windowless rendering for
        # the review-capture legs; never passed by the certified verifier.
        cmd.append("-RenderOffScreen")
    if extra_args:
        # Opt-in verbatim switches (position not load-bearing) — see docstring.
        cmd.extend(extra_args)
    if capture:
        # Opt-in substrate hook (position not load-bearing): fixtures gate their
        # screenshot writes on this switch and drop PNGs under Saved/CraftBench/.
        cmd.append("-CraftBenchCapture")
    if report_dir is not None:
        report_dir.mkdir(parents=True, exist_ok=True)
        # UE 5.7 documented flag is -ReportExportPath. Older community
        # references use -ReportOutputPath; both have appeared across UE
        # versions, but ReportExportPath is the current docs spelling.
        cmd.append(f"-ReportExportPath={report_dir}")

    notes.append("cmd: " + " ".join(cmd))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    try:
        exit_code, killed_on_marker = _run_editor_with_marker_kill(
            cmd=cmd,
            env=extra_env,
            log_path=log_path,
            timeout_seconds=timeout_seconds,
        )
        if killed_on_marker:
            notes.append(
                "editor reached terminal marker but did not self-exit; "
                "force-killed (known RequestExit quirk; seen on Mac AND Windows)"
            )
    except subprocess.TimeoutExpired as e:
        # e.stdout may be bytes even when text=True (CPython quirk on timeout
        # of buffered streams). Decode defensively.
        partial = e.stdout if e.stdout is not None else b""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", errors="replace")
        log_path.write_text(
            partial + f"\nL2 TIMEOUT after {timeout_seconds:.0f}s\n",
            encoding="utf-8",
        )
        return L2Result(
            status="fail",
            log_path=log_path,
            duration_seconds=time.monotonic() - start,
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            tests_skipped=0,
            notes=notes + [f"timeout after {timeout_seconds:.0f}s"],
            exit_code=124,
            report_path=None,
            result_source="none",
        )
    except FileNotFoundError as e:
        log_path.write_text(f"L2 ABORTED: {e}\n", encoding="utf-8")
        return L2Result(
            status="fail",
            log_path=log_path,
            duration_seconds=time.monotonic() - start,
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            tests_skipped=0,
            notes=notes + [f"exec failed: {e}"],
            exit_code=127,
            report_path=None,
            result_source="none",
        )

    duration = time.monotonic() - start
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    parsed, source, report_path = _parse_results(
        log_text=log_text,
        report_dir=report_dir,
    )
    notes.append(f"result source: {source}")
    notes.extend(_verdict_evidence(log_text))
    rhi_dead = _rhi_unavailable(log_text)
    if rhi_dead:
        notes.append(
            "GPU refused the editor a resource (RHI allocation failure) — this is "
            "a MACHINE fault, not submission content; the verdict layer routes it "
            "to HARNESS-ERROR when no test result was produced")

    queued_unstarted = _queued_never_started(log_text)
    never_started = _editor_never_started(
        log_text=log_text, exit_code=exit_code, tests_run=parsed.tests_run)
    if never_started:
        notes.append(
            "the editor produced a ZERO-BYTE log and exited non-zero — it never "
            "reached the point of opening its own log, so neither the test nor "
            "the submission ever ran; the verdict layer routes this out of the "
            "graded denominator")
    harness_precondition = _harness_precondition(log_text)
    if harness_precondition:
        notes.append(
            "a fixture finished through EFunctionalTestResult::Error — it declared "
            "that the HARNESS could not set the test up, not that the submission "
            "was wrong; the verdict layer routes this out of the graded denominator "
            "when no pass/fail result accompanied it")

    if parsed.tests_run == 0:
        status = "skipped"
        if queued_unstarted:
            # The stock note below is WRONG for this case and was the note
            # actually printed on 20260811-010729: the filter matched fine —
            # the controller queued the test — and the editor then exited
            # before starting it. Sending a reader to check their filter costs
            # them the real cause.
            notes.append(
                "the test WAS queued (so the filter matched) but the editor "
                "ended before it started, with no exit marker — cause NOT yet "
                "established (it is not the `; Quit`, which is queued "
                "identically on healthy runs, and not -testexit, which never "
                "matches anything). No submission code had run at that point, "
                "so this is a MACHINE fault; the verdict layer routes it to "
                "HARNESS-ERROR"
            )
        else:
            notes.append(
                "no tests counted; check that the test filter matches a "
                "discoverable test (see README known assumptions)"
            )
    elif parsed.tests_failed == 0 and parsed.tests_passed == parsed.tests_run:
        status = "pass"
        # Leg-count guard: every DECLARED fixture must actually have run.
        # A multi-fixture session that silently drops a leg (map failed to
        # open, test not discovered, editor died between legs) would otherwise
        # grade PASS on the legs that did run.
        if expected_test_count is not None and parsed.tests_run != expected_test_count:
            status = "fail"
            if parsed.tests_run < expected_test_count:
                notes.append(
                    f"leg dropped: ran {parsed.tests_run} of "
                    f"{expected_test_count} declared fixtures"
                )
            else:
                notes.append(
                    f"fixture over-count: ran {parsed.tests_run} of "
                    f"{expected_test_count} declared fixtures — filter matched "
                    "more tests than the spec declares"
                )
    else:
        status = "fail"

    return L2Result(
        status=status,
        log_path=log_path,
        duration_seconds=duration,
        tests_run=parsed.tests_run,
        tests_passed=parsed.tests_passed,
        tests_failed=parsed.tests_failed,
        tests_skipped=parsed.tests_skipped,
        notes=notes,
        exit_code=exit_code,
        report_path=report_path,
        result_source=source,
        rhi_unavailable=rhi_dead,
        queued_never_started=queued_unstarted,
        harness_precondition=harness_precondition,
        editor_never_started=never_started,
    )


@dataclass
class _ParsedAutomation:
    tests_run: int
    tests_passed: int
    tests_failed: int
    tests_skipped: int


# The WHY lines a human needs to adjudicate a verdict without re-deriving it
# from the raw log (workflow finding, 2026-08-04: the matrix's headline fact —
# "all 6 failures on gate (3)" — existed nowhere in any report; every failing
# assertion had to be grepped out of l2_pie.log by hand, and a PASS was even
# more opaque because gate (5)'s skipped/ratio/absolute path lived only in
# advisory log lines). Three fixture-agnostic families:
#   * LogFunctionalTest's FinishTest line — the exact failing assertion text;
#   * the automation controller's per-test Result={...} line;
#   * the CraftBench fixture convention's [<TAG>-FINAL] / [<TAG>-ADVISORY] /
#     [<TAG>-RESUME-DIAG] gate-input summaries.
_EVIDENCE_PATTERNS = (
    re.compile(r"FinishTest TestResult=\w+\.[^\r\n]*"),
    re.compile(r"Test Completed\. Result=\{[^\r\n]*"),
    re.compile(r"\[[A-Z][A-Z0-9]*-(?:FINAL|ADVISORY|RESUME-DIAG)\][^\r\n]*"),
)
_EVIDENCE_CAP = 10  # last-N wins: the final run's lines are the verdict's


# The editor asking the GPU driver for memory and being refused. Agent C++ runs
# in GAMEPLAY — it does not allocate render targets — so these lines are the
# machine's condition, not the submission's. That distinction is the whole reason
# this is detected: `run_task.harness_error_reasons` needs to tell "the GPU died"
# apart from "the agent's code crashed the editor", and those are otherwise
# structurally identical (both: L1 pass, tests_run 0, status skipped).
#
# RESIDUAL, stated rather than hidden: a submission cannot change render settings
# under a graded L2, but it could in principle inflate a scene enough to matter.
# Nothing measured has ever shown that; if one does, tighten this rather than
# widen it.
_RHI_OOM_MARKERS = (
    "CreateCommittedResource",          # D3D12 allocation refused
    "OutOfVideoMemory",
    "Out of video memory trying to allocate",
    "DXGI_ERROR_DEVICE_REMOVED",
)


def _rhi_unavailable(log_text: str) -> bool:
    """True iff the log shows the GPU refusing the editor a resource."""
    return any(m in log_text for m in _RHI_OOM_MARKERS)


#: The automation controller accepted our filter and put the test on its queue.
#: Its presence proves the filter MATCHED — which is what makes the stock
#: "check that the test filter matches a discoverable test" note wrong for this
#: case, and it was the note printed on the run that exposed this.
_QUEUED_MARKER = "Automation: RunTests="
#: The test actually began. UE prints this once the worker picks the queued test
#: up; everything a submission can influence happens AFTER it.
_STARTED_MARKERS = ("Test Started", "LogFunctionalTest: Display: Test Started")


#: The engine's exact emission. ``AFunctionalTest::FinishTest`` routes Invalid,
#: Error and Failed through ``AddError`` with the format string
#: ``TEXT("FinishTest TestResult=%s. %s")`` — verified at
#: <UE_ROOT>/.../Developer/FunctionalTesting/Private/FunctionalTest.cpp:471. So the
#: enum name is always followed by a literal period, whether or not a message
#: follows, and requiring that period is a tightening derived from the engine
#: source rather than a guess.
#:
#: The match is anchored as hard as the format allows because this predicate
#: REMOVES a run from the graded denominator: a false positive favours the
#: submission, so precision beats recall in this one direction.
#:
#: CASE-SENSITIVE, unlike its neighbours above. Those match free-form engine
#: prose where casing has drifted between versions; this one matches a FIXED
#: emission — ``LexToString`` returns literally ``FString("Error")``
#: (FunctionalTest.cpp:118-119) into a literal format string, and ``log_text`` is
#: read raw with no case transform (see ``run_l2``). So ``re.IGNORECASE`` bought
#: nothing here and cost precision, which contradicts the paragraph above it.
_HARNESS_PRECONDITION_RE = re.compile(r"FinishTest\s+TestResult=Error\.")


def _harness_precondition(log_text: str) -> bool:
    """True iff a fixture finished through ``EFunctionalTestResult::Error``.

    That enum means one thing corpus-wide after the 2026-08-14 audit: **the
    harness could not set the test up**. It is NOT "the model failed" — that is
    ``::Failed`` — so a run whose only outcome is an ::Error never reached a
    state where the submission could be graded.

    **This is a log-text match, and log text is not a trust boundary.** Agent C++
    runs in this process and writes this same log, so a submission CAN emit a
    look-alike line. Do not describe this signal as unspoofable. Three things
    make the residual risk acceptable rather than merely tolerated:

    1. The anchor is the engine's exact format (above), so a spoof has to be
       deliberate and exact — it is not something a stray log line trips.
    2. The predicate that consumes this also requires ``tests_run == 0``. So a
       spoofing submission must ALSO produce no passing and no failing test,
       i.e. it has to break its own run to use the exploit. It cannot bank a
       partial success and void the rest.
    3. A void is not a free pass: it is re-run (the void-and-retry rule retries a
       void twice, then reports the cell unmeasurable) and it is counted in the
       ``n_excluded`` bucket every consumer now surfaces. The outcome of a
       successful spoof is "this run does not count and someone notices", not
       "this run passes".

    Note the asymmetry with the counters: ``_TEST_RESULT_RE`` matches only
    ``Passed|Failed|Skipped``, so an Error-finished test is invisible to the
    stdout-fallback tally and shows up as ``tests_run == 0`` -> status
    "skipped". Reading ``log_text`` directly is therefore the only available
    signal, and it is also why this must not be inferred from ``notes``:
    ``_verdict_evidence`` de-dups and then keeps only the LAST 10 lines, so a
    multi-leg session can drop the very line this depends on.
    """
    return bool(_HARNESS_PRECONDITION_RE.search(log_text))


#: Exit codes that must NEVER be read as "the editor never started", however
#: empty the log is. 0 = it exited cleanly (an empty log then means our capture
#: broke, not the editor). 124 = the GOVERNED TIMEOUT, which stays GRADED on
#: purpose: a pathological submission can hang the editor, and routing a hang
#: out of the denominator would hand every model an opt-out that needs no
#: submission content at all (run_task.LAYER_ERROR_GRADED_EXITS, same doctrine).
_NEVER_STARTED_GRADED_EXITS = frozenset({0, 124})


def _editor_never_started(*, log_text: str, exit_code: int, tests_run: int) -> bool:
    """True iff the editor produced NO output at all and died on a non-timeout.

    The one L2 fault where the submission provably never ran: the process failed
    before it opened its log. Measured instance is exit ``0xC0000142``
    (STATUS_DLL_INIT_FAILED) with a 0-byte log on BOTH the ``-nullrhi`` leg and
    the full-RHI retry, and no UECC dump.

    **Why this is narrow enough to route on.** Each conjunct excludes a case that
    must stay GRADED, and the list is what keeps this from becoming the
    denominator opt-out that the repo conventions warn about:

    * ``not log_text`` — a real L2 failure WRITES. An assertion, a fixture
      FAIL, a filter that matched nothing ("no tests found"), an agent-C++ crash
      (which also leaves a UECC dump): all of them produce log bytes. Emptiness
      is the discriminator, and it is the one signal a submission cannot forge —
      agent code runs only after the log is open. Contrast
      ``_harness_precondition``, which matches text the submission's own code
      could emit.
    * ``tests_run == 0`` — a run that recorded any graded outcome banked a real
      result and must keep it. Mirrors the same conjunct on the other three
      predicates; it stops a submission from passing part of a fixture and
      voiding the rest.
    * ``exit_code not in _NEVER_STARTED_GRADED_EXITS`` — see that set.

    **Deliberately NOT keyed on the exit code's identity.** Matching
    ``0xC0000142`` specifically would be narrower, but it would also be a claim
    that agent C++ can never cause a DLL-init failure, and a static initialiser
    in submitted code plausibly could. Keying on "no output at all" instead means
    the predicate does not depend on that being true: if agent code ever DID kill
    the process this early, it still could not have produced the empty log AND a
    non-timeout exit AND zero tests while also being distinguishable from the
    machine fault — so the honest reading of that state is "ungradeable", which
    is what this returns.

    **Deliberately NOT keyed on ``status``.** ``registry.run_layers`` emits
    ``skipped`` for every dependent of a failed layer, so a status conjunct would
    catch every L1 compile failure — the exact trap the repo conventions document against
    the zero-test-L2 predicate.
    """
    if log_text.strip():
        return False
    if tests_run != 0:
        return False
    return exit_code not in _NEVER_STARTED_GRADED_EXITS


def _queued_never_started(log_text: str) -> bool:
    """True iff the editor QUEUED the requested test and then exited without
    ever starting it.

    THE FAULT THIS NAMES (measured 2026-08-11,
    runs/aura-product/bp-g2__gp-glide-stamina-cpp-20260811-010729): the editor
    queued the requested test and then ended, with the worker still being
    discovered and the test never started::

        Automation: RunTests='...GlideStaminaFunctionalTest' Queued.   frame 0
        Automation: Quit Command Queued.                               frame 1
        LogAutomationWorker: Received FindWorkersMessage    frame 302, +770ms
        (log ends here — no exit marker of any kind)

    L1 had PASSED both targets and the model had shipped four files; the run
    graded FAIL against the model because L2 counted zero tests.

    WHY THE EDITOR ENDED IS **NOT** ESTABLISHED — stated plainly because the
    first draft of this comment asserted a cause and was wrong, and a confident
    wrong comment is worse than an admitted gap:

      * NOT the ``; Quit``. It is queued at frame 0-1 in HEALTHY runs too
        (…-20260811-014912: RunTests and Quit both at frame 0, test started at
        frame 998 and completed normally). Identical in both, so it cannot be
        the differentiator.
      * NOT ``-testexit="Automation Test Queue Empty"``. That string appears in
        four separate logs ONLY as the command-line echo, never as an engine
        event — the flag is inert and matches nothing.
      * The healthy exit path is the automation framework's own:
        ``**** TEST COMPLETE. EXIT CODE: 0 ****`` -> ``RequestExitWithStatus``.
        The failing log has no such line; it simply stops.

    The one thing that IS established is what this predicate keys on: the test
    was queued and never started, so no submission code had run. That is enough
    to know it is not a model result, which is all this flag is used for.

    WHY THIS CANNOT EXCUSE AN AGENT — the distinction predicate (4b) in
    ``run_task`` was too narrow to make, and the one this repo previously
    recorded as impossible. Measured across three logs of the same task:

        run                       queued   started   completed
        rep 225037 (PASS)           yes      yes        yes
        rep 230658 (PASS)           yes      yes        yes
        20260811-010729 (FAIL)      yes      NO         NO

    "Started then died" is the agent-reachable case — a crash in submission code
    kills the editor mid-test, and ``run_task``'s own note records that such a
    run "had already printed Test Started". "Queued, never started" is the
    opposite: nothing of the submission has run yet. On a ``-cpp`` task the
    writable root is ``Source/``, the map is substrate the agent cannot touch,
    and L1 PASS proves the submission compiled and loaded — so a queued test
    that never starts is the harness's own exit racing the controller.

    Deliberately requires BOTH conjuncts. A log with no queue line at all is a
    different fault (filter miss, editor died during startup) and must keep the
    existing note rather than borrow this one.
    """
    if _QUEUED_MARKER not in log_text:
        return False
    # ``Automation RunTests`` logs ``Queued`` before the automation controller
    # resolves the filter.  A bad/empty filter can therefore produce both a
    # queue line and the authoritative zero-match diagnostic without ever
    # starting a test.  That is a filter/fixture-identity error, not the
    # measured controller race this predicate routes outside the graded
    # denominator.  Never let a submission/task escape by manufacturing a
    # zero-match command that merely contains the generic queue marker.
    if "No automation tests matched" in log_text:
        return False
    return not any(m in log_text for m in _STARTED_MARKERS)


def _verdict_evidence(log_text: str) -> list[str]:
    """``verdict-evidence:``-prefixed WHY lines extracted from the editor log.

    Never raises and never gates — pure report enrichment. Capped at the LAST
    ``_EVIDENCE_CAP`` matches so a multi-leg session reports the legs that
    decided the verdict rather than flooding the notes."""
    try:
        found: list[str] = []
        for pat in _EVIDENCE_PATTERNS:
            found.extend(m.group(0).strip() for m in pat.finditer(log_text))
        # De-dup preserving order (ADVISORY text repeats via -fullstdoutlogoutput).
        seen: set[str] = set()
        uniq = [x for x in found if not (x in seen or seen.add(x))]
        return [f"verdict-evidence: {x}" for x in uniq[-_EVIDENCE_CAP:]]
    except Exception:  # noqa: BLE001 — enrichment must never break a grade
        return []


def _parse_results(
    *, log_text: str, report_dir: Optional[Path]
) -> tuple[_ParsedAutomation, str, Optional[Path]]:
    """Try JSON first, fall back to stdout grep.

    Returns ``(parsed, source, report_path)`` where ``source`` is
    ``"json"`` | ``"stdout-fallback"`` | ``"none"``.
    """
    if report_dir is not None:
        index = report_dir / "index.json"
        if index.exists():
            try:
                parsed = parse_index_json(index.read_text(encoding="utf-8"))
                return parsed, "json", index
            except (ValueError, KeyError, json.JSONDecodeError):
                pass  # fall through to stdout

    parsed = parse_automation_log(log_text)
    source = "stdout-fallback" if parsed.tests_run > 0 else "none"
    return parsed, source, None


def parse_index_json(text: str) -> _ParsedAutomation:
    """Parse UE's automation report ``index.json``.

    Schema (UE 4.x..5.x, community-documented; not pinned to a 5.7
    release-notes line):

        {
          "succeeded": int,
          "failed": int,
          "succeededWithWarnings": int,
          "notRun": int,
          "tests": [
            { "state": "Success"|"Fail"|"NotRun"|"InProcess",
              "fullTestPath": str, "testDisplayName": str, ... },
            ...
          ]
        }

    We trust ``tests[*].state`` if present (per-test ground truth);
    otherwise fall back to the top-level counts. Raises if neither is
    parseable.

    UE 5.7 prepends a UTF-8 BOM to the file, which ``json.loads`` rejects;
    strip it defensively.
    """
    if text.startswith("﻿"):
        text = text[1:]
    obj = json.loads(text)
    tests = obj.get("tests")
    if isinstance(tests, list) and tests:
        passed = sum(1 for t in tests if _state_of(t) == "success")
        failed = sum(1 for t in tests if _state_of(t) == "fail")
        skipped = sum(1 for t in tests if _state_of(t) in ("notrun", "skipped"))
        total = passed + failed + skipped
        if total > 0:
            return _ParsedAutomation(
                tests_run=total,
                tests_passed=passed,
                tests_failed=failed,
                tests_skipped=skipped,
            )

    # Fall back to top-level counts.
    succeeded = int(obj.get("succeeded", 0) or 0)
    succeeded_w = int(obj.get("succeededWithWarnings", 0) or 0)
    failed = int(obj.get("failed", 0) or 0)
    not_run = int(obj.get("notRun", 0) or 0)
    passed = succeeded + succeeded_w
    total = passed + failed + not_run
    if total == 0:
        raise ValueError("index.json has no tests and no counts")
    return _ParsedAutomation(
        tests_run=total,
        tests_passed=passed,
        tests_failed=failed,
        tests_skipped=not_run,
    )


def _state_of(test_obj: dict) -> str:
    raw = str(test_obj.get("state", "")).strip().lower()
    return raw


def parse_automation_log(text: str) -> _ParsedAutomation:
    """Stdout fallback — count per-test result lines.

    Used only when ``index.json`` is missing or unparseable. Tries three
    signals in priority order:

    1. ``Test Completed. Result={...}`` — UE's display line, **localized**
       in some installs (Chinese: ``Result={失败}``), so not always present.
    2. ``TestResult=Passed|Failed|Skipped`` — emitted by ``FinishTest`` in
       English regardless of editor locale; this is the reliable signal.
    3. ``Automation Test Succeeded`` / ``Automation Test Failed`` — old UE
       4.x style headlines, last-ditch fallback.
    """
    passed = failed = skipped = 0
    for m in _RESULT_RE.finditer(text):
        bucket = m.group("result").lower()
        if bucket == "passed":
            passed += 1
        elif bucket == "failed":
            failed += 1
        elif bucket == "skipped":
            skipped += 1

    total = passed + failed + skipped
    if total == 0:
        # Locale-stable signal from FinishTest.
        for m in _TEST_RESULT_RE.finditer(text):
            bucket = m.group("result").lower()
            if bucket == "passed":
                passed += 1
            elif bucket == "failed":
                failed += 1
            elif bucket == "skipped":
                skipped += 1
        total = passed + failed + skipped

    if total == 0:
        passed = len(_SUCCEEDED_RE.findall(text))
        failed = len(_FAILED_RE.findall(text))
        total = passed + failed

    return _ParsedAutomation(
        tests_run=total,
        tests_passed=passed,
        tests_failed=failed,
        tests_skipped=skipped,
    )
