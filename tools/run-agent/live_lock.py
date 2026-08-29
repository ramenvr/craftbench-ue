"""Process-level advisory lock for live-substrate (`--live-project`) runs.

WHY. A `--live-project` `aura-*` run mutates the **shared source substrate**:
``fairness.stage_fairness_hide`` ``copy2``s then ``unlink()``s
``AGENT_WRITABLE.json`` (and stubs ``Source/CraftBenchTests/``) for the whole
agent-dispatch window, restoring in ``try/finally``. ``copy2`` preserves mtime, so
during that window the source manifest is genuinely ABSENT while looking
"unchanged". Any OTHER process that reads the source tree in that window — a
``verify-single`` suite, a ``build_workspace``, a second ``run-agent`` — hits a
transient ``FileNotFoundError`` (observed 2026-06-04, root-caused by the diagnostic
workflow). This lock serializes that.

HOW. An OS-level advisory lock on a lockfile (``runs/.live-run.lock`` by
default). The mutating live run holds it EXCLUSIVE for its duration; readers call
:func:`is_live_run_active` to wait/skip instead of reading a half-hidden tree. The
lock is released automatically when the fd closes — on context exit, on exception,
AND on process death — so there is no stale-lock to clean up. The primitive is
``fcntl.flock`` on POSIX and ``msvcrt.locking`` (a 1-byte range lock) on Windows;
acquisition is a poll loop so blocking/timeout/non-blocking behave identically on
both platforms.

WIRING (apply when you next touch the live path — NOT applied here because
``run.py``/``fairness.py`` are uncommitted WIP):

    # writer side — tools/run-agent/run.py :: _run_live_project
    from live_lock import live_run_lock
    def _run_live_project(...):
        with live_run_lock():          # serialize the source-tree mutation window
            ...                        # existing fairness-hide / dispatch / snapshot / restore

    # reader side (optional) — anything reading the source substrate, e.g.
    # verify-single's integrity check or build_workspace:
    from live_lock import live_run_lock   # block until any live run finishes
    with live_run_lock(timeout=900):      # then read the source tree safely
        ...
    # or non-destructively probe and skip/warn:
    if is_live_run_active():
        ...  # a live --live-project run is hiding the source manifest right now
"""

from __future__ import annotations

import errno
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

try:
    import fcntl  # POSIX advisory locks
    _HAVE_FCNTL = True
except ImportError:  # Windows has no fcntl — fall back to msvcrt byte-range locks
    fcntl = None  # type: ignore[assignment]
    _HAVE_FCNTL = False
    import msvcrt

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOCK_PATH = _REPO_ROOT / "runs" / ".live-run.lock"

_BUSY_ERRNOS = (errno.EAGAIN, errno.EWOULDBLOCK)


class LiveRunLockBusy(RuntimeError):
    """The live-run lock is held and we could not acquire it (non-blocking, or
    the timeout elapsed)."""


def _open_lock(path: Path) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # The lockfile's CONTENT is irrelevant — only its lock state matters.
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
    if not _HAVE_FCNTL:
        # Windows byte-range locks need a byte to lock; ensure the lockfile is
        # non-empty. Harmless on POSIX (flock locks the whole file regardless).
        try:
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"0")
            os.lseek(fd, 0, os.SEEK_SET)
        except OSError:
            pass
    return fd


def _try_lock(fd: int) -> bool:
    """Attempt a NON-BLOCKING exclusive lock. Return True if acquired, False if it
    is held by another open file description / process. Re-raise unexpected errors."""
    if _HAVE_FCNTL:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError as e:
            if e.errno in _BUSY_ERRNOS:
                return False
            raise
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        return True
    except OSError:
        # EACCES / EDEADLOCK: the 1-byte region is locked elsewhere.
        return False


def _unlock(fd: int) -> None:
    if _HAVE_FCNTL:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    except OSError:
        pass


@contextmanager
def live_run_lock(
    lock_path: Optional[Path] = None,
    *,
    blocking: bool = True,
    timeout: Optional[float] = None,
    poll: float = 0.05,
) -> Iterator[Path]:
    """Hold an EXCLUSIVE advisory lock for the body's duration.

    - ``blocking=True`` (default), no ``timeout``: wait indefinitely.
    - ``timeout=<seconds>``: poll up to ``timeout`` then raise :class:`LiveRunLockBusy`.
    - ``blocking=False``: raise :class:`LiveRunLockBusy` immediately if held.

    Released on normal exit, on exception, and on process death.
    """
    lp = Path(lock_path) if lock_path is not None else DEFAULT_LOCK_PATH
    fd = _open_lock(lp)
    acquired = False
    try:
        if not blocking and timeout is None:
            if _try_lock(fd):
                acquired = True
            else:
                raise LiveRunLockBusy(f"live-run lock {lp} is held by another process")
        else:
            deadline = (time.monotonic() + timeout) if timeout is not None else None
            while True:
                if _try_lock(fd):
                    acquired = True
                    break
                if deadline is not None and time.monotonic() >= deadline:
                    raise LiveRunLockBusy(
                        f"live-run lock {lp} held; timed out after {timeout}s"
                    )
                time.sleep(poll)
        yield lp
    finally:
        if acquired:
            try:
                _unlock(fd)
            except OSError:
                pass
        os.close(fd)


def acquire_live_run_lock(lock_path: Optional[Path] = None):
    """NON-BLOCKING acquire for try/finally-style callers (the graded runners'
    bodies are one big try/finally, not a with-block). Returns a ``release()``
    callable; raises :class:`LiveRunLockBusy` if another process holds it.

    Like :func:`live_run_lock`, the lock dies with the process — a hard-killed
    run releases it automatically, which is exactly what lets the next run's
    crash-recovery heal distinguish "leftovers of a DEAD run" (lock free →
    heal) from "a run is LIVE right now" (lock held → keep hands off)."""
    lp = Path(lock_path) if lock_path is not None else DEFAULT_LOCK_PATH
    fd = _open_lock(lp)
    if not _try_lock(fd):
        os.close(fd)
        raise LiveRunLockBusy(f"live-run lock {lp} is held by another process")

    def release() -> None:
        try:
            _unlock(fd)
        except OSError:
            pass
        os.close(fd)

    return release


def is_live_run_active(lock_path: Optional[Path] = None) -> bool:
    """Best-effort, non-blocking probe: ``True`` iff a live-substrate run currently
    holds the lock. Never blocks; never mutates lock state."""
    lp = Path(lock_path) if lock_path is not None else DEFAULT_LOCK_PATH
    if not lp.exists():
        return False
    fd = _open_lock(lp)
    try:
        if _try_lock(fd):
            _unlock(fd)
            return False
        return True
    finally:
        os.close(fd)
