"""job_governor — a Windows Job-Object backstop for the cold headless-UE spawns.

WHY this exists: every L1 (UBT) build and L2/L2I/asset/scaffold editor spawn forks
a heavy ``UnrealEditor-Cmd`` / ``UnrealBuildTool`` process tree (~8 GB editor + UBT
compile RAM). On Windows there is no cgroup/container around a grade, so a hung or
runaway child — or one that out-lives the grader because it spawned grandchildren —
can wedge or OOM the box. A Win32 **Job Object** gives us a kernel-level handle that
(a) reaps the ENTIRE assigned process tree when the handle closes
(``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE``) and (b) optionally caps the job's committed
memory (``JOB_OBJECT_LIMIT_JOB_MEMORY``). This module wraps a spawn in that job.

GATING: it is a no-op UNLESS BOTH ``os.name == "nt"`` AND the env var
``CRAFTBENCH_GOVERN_RESOURCES`` is truthy. The env var is a tri-state the caller
sets explicitly: ``1``/``true`` enables, ``0``/``false`` disables, and ABSENT means
"unspecified". ``run_task.py`` resolves its default-ON ``--govern-resources`` /
opt-out ``--no-govern-resources`` flag down to a ``1``/``0`` env value (an env var
the operator set by hand wins over the flag default, in both directions), keeping
the layer modules decoupled from argparse. Non-Windows hosts are always untouched.
When disabled the wrapper yields ``None`` and ``assign`` is a no-op True, so the
ungoverned path is byte-for-byte unchanged.

FAIL-OPEN: this is a backstop, never a gate. ANY ctypes / Win32 failure logs a one-
time warning and degrades to passthrough — it must NEVER raise into a grade. Stdlib
``ctypes`` only (mirrors the ``GlobalMemoryStatusEx`` shim in
``tools/run-agent/aura_rig/mem_gate.py``); no pywin32, no psutil.
"""
from __future__ import annotations

import os
import warnings
from contextlib import contextmanager
from typing import Optional

IS_WINDOWS = os.name == "nt"


_TRUTHY = {"1", "true", "yes", "on"}
_FALSEY = {"0", "false", "no", "off"}


def _enabled() -> bool:
    """True iff the governor should actuate: Windows AND the env var is truthy.

    The env var is parsed as a tri-state. A truthy value (``1``/``true``/``yes``/
    ``on``) enables; a falsey value (``0``/``false``/``no``/``off``) disables; an
    absent/blank value is unspecified and disables here (``run_task.py`` is the
    component that supplies the default-ON, resolving its flag to an explicit
    ``1``/``0`` before any layer spawns). Parsing ``0``/``false`` as DISABLED — not
    as the old ``bool(non-empty-string)`` which treated ``"0"`` as truthy — is what
    lets ``CRAFTBENCH_GOVERN_RESOURCES=0`` opt OUT via the environment."""
    if not IS_WINDOWS:
        return False
    return str(os.environ.get("CRAFTBENCH_GOVERN_RESOURCES", "")).strip().lower() in _TRUTHY


def _env_int(name: str, default: int) -> int:
    """Read an int env override; fall back to ``default`` on absence/parse miss."""
    try:
        return int(str(os.environ.get(name, "")).strip())
    except (TypeError, ValueError):
        return default


# Conservative, env-tunable memory caps (MB). L1 (UBT compile) is the heavier of
# the two — many parallel cl.exe — so it gets the larger cap by default.
L1_MEM_MB = _env_int("CRAFTBENCH_L1_MEM_MB", 12288)
L2_MEM_MB = _env_int("CRAFTBENCH_L2_MEM_MB", 8192)


# ---------------------------------------------------------------------------
# One-time fail-open WARN latch (don't spam the grade log on every spawn).
# ---------------------------------------------------------------------------

_warned = False


def _warn_once(detail: str) -> None:
    """Emit (at most once per process) the operator signal that the governor
    degraded to passthrough. Reached only on a Win32/ctypes failure — the grade
    proceeds without the kill-on-close backstop, exactly as if the env were unset."""
    global _warned
    if _warned:
        return
    _warned = True
    warnings.warn(
        f"job_governor: Win32 Job Object unavailable, degrading to passthrough "
        f"(no kill-on-job-close / memory backstop): {detail}",
        RuntimeWarning,
        stacklevel=2,
    )


# ---------------------------------------------------------------------------
# Win32 structs + kernel32 plumbing (stdlib ctypes only; built lazily so the
# module imports cleanly on non-Windows and the structs/argtypes only touch
# wintypes when ctypes is actually loaded).
# ---------------------------------------------------------------------------

# Job-object info class for SetInformationJobObject.
_JobObjectExtendedLimitInformation = 9

# BasicLimitInformation.LimitFlags bits.
_JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION = 0x00000400
_JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

# OpenProcess desired-access bits: PROCESS_SET_QUOTA | PROCESS_TERMINATE.
_PROCESS_SET_QUOTA = 0x0100
_PROCESS_TERMINATE = 0x0001


def _load_kernel32():
    """Build the (kernel32, ctypes, struct-types) bundle, or None on any failure.

    Done lazily and defensively: importing ctypes.wintypes and declaring the
    structs is itself a Win32-only operation, so a single broad swallow here keeps
    a malformed environment from ever raising into the contextmanager."""
    if not IS_WINDOWS:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
                ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.POINTER(wintypes.ULONG)),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)

        # CreateJobObjectW(lpJobAttributes, lpName) -> HANDLE
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]

        # SetInformationJobObject(hJob, JobObjectInfoClass, lpJobObjectInfo, cb) -> BOOL
        k32.SetInformationJobObject.restype = wintypes.BOOL
        k32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
        ]

        # OpenProcess(dwDesiredAccess, bInheritHandle, dwProcessId) -> HANDLE
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]

        # AssignProcessToJobObject(hJob, hProcess) -> BOOL
        k32.AssignProcessToJobObject.restype = wintypes.BOOL
        k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]

        # TerminateJobObject(hJob, uExitCode) -> BOOL
        k32.TerminateJobObject.restype = wintypes.BOOL
        k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]

        # CloseHandle(hObject) -> BOOL
        k32.CloseHandle.restype = wintypes.BOOL
        k32.CloseHandle.argtypes = [wintypes.HANDLE]

        return {
            "ctypes": ctypes,
            "k32": k32,
            "EXT_INFO": JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
        }
    except Exception as exc:  # noqa: BLE001 — fail open, never raise into a grade
        _warn_once(f"kernel32 plumbing failed: {exc!r}")
        return None


def _create_job(memory_limit_mb: Optional[int], name: Optional[str]):
    """Create a job object configured to kill its whole tree on handle close, and
    (optionally) cap committed memory. Returns the raw HANDLE or None on any
    failure (fail open)."""
    bundle = _load_kernel32()
    if bundle is None:
        return None
    ctypes = bundle["ctypes"]
    k32 = bundle["k32"]
    try:
        job = k32.CreateJobObjectW(None, name or None)
        if not job:
            _warn_once(f"CreateJobObjectW failed: err={ctypes.get_last_error()}")
            return None

        info = bundle["EXT_INFO"]()
        flags = (_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                 | _JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION)
        if memory_limit_mb:
            flags |= _JOB_OBJECT_LIMIT_JOB_MEMORY
            info.JobMemoryLimit = int(memory_limit_mb) * 1024 * 1024
        info.BasicLimitInformation.LimitFlags = flags

        ok = k32.SetInformationJobObject(
            job, _JobObjectExtendedLimitInformation,
            ctypes.byref(info), ctypes.sizeof(info),
        )
        if not ok:
            _warn_once(
                f"SetInformationJobObject failed: err={ctypes.get_last_error()}")
            k32.CloseHandle(job)
            return None
        return job
    except Exception as exc:  # noqa: BLE001 — fail open
        _warn_once(f"_create_job failed: {exc!r}")
        return None


def _close_job(job) -> None:
    """Close the job handle. With KILL_ON_JOB_CLOSE set, this reaps every assigned
    process (and their descendants). Best-effort; never raises."""
    if job is None:
        return
    bundle = _load_kernel32()
    if bundle is None:
        return
    k32 = bundle["k32"]
    try:
        # Belt-and-suspenders: explicitly terminate, then close. CloseHandle alone
        # triggers the kill via KILL_ON_JOB_CLOSE, but an explicit Terminate makes
        # the reap synchronous and deterministic for the test's poll-within-3s.
        try:
            k32.TerminateJobObject(job, 1)
        except Exception:  # noqa: BLE001 — terminate is best-effort
            pass
        k32.CloseHandle(job)
    except Exception as exc:  # noqa: BLE001 — fail open
        _warn_once(f"_close_job failed: {exc!r}")


@contextmanager
def resource_job(*, memory_limit_mb: Optional[int] = None, name: str = "craftbench"):
    """Yield a job handle (None if disabled / non-Windows / on any Win32 failure).

    On exit the handle is closed, which — via ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE``
    — terminates the ENTIRE assigned process tree. Usage::

        with resource_job(memory_limit_mb=L2_MEM_MB, name="cb-l2") as job:
            proc = subprocess.Popen(cmd, ...)
            assign(job, proc.pid)
            ...  # existing streaming / deadline / marker-kill loop

    When disabled, yields None and the body runs exactly as today (assign is a
    no-op True), so this is a pure additive backstop."""
    if not _enabled():
        yield None
        return
    handle = _create_job(memory_limit_mb, name)
    try:
        yield handle
    finally:
        _close_job(handle)


def assign(job, pid: int) -> bool:
    """Assign a running pid (and its future children) to the job object.

    Returns True when the assignment succeeded OR when there's nothing to do
    (``job is None`` — disabled/non-Windows/fail-open). Returns False only when an
    actual Win32 assignment was attempted and failed (the caller may log it, but
    must not treat it as fatal — the grade proceeds regardless)."""
    if job is None:
        return True
    bundle = _load_kernel32()
    if bundle is None:
        return True
    ctypes = bundle["ctypes"]
    k32 = bundle["k32"]
    hproc = None
    try:
        hproc = k32.OpenProcess(
            _PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, int(pid))
        if not hproc:
            _warn_once(f"OpenProcess({pid}) failed: err={ctypes.get_last_error()}")
            return False
        ok = k32.AssignProcessToJobObject(job, hproc)
        if not ok:
            _warn_once(
                f"AssignProcessToJobObject({pid}) failed: "
                f"err={ctypes.get_last_error()}")
            return False
        return True
    except Exception as exc:  # noqa: BLE001 — fail open
        _warn_once(f"assign({pid}) failed: {exc!r}")
        return False
    finally:
        if hproc:
            try:
                k32.CloseHandle(hproc)
            except Exception:  # noqa: BLE001
                pass
