"""job_governor — real Win32 Job-Object behavior tests.

These exercise the kill-on-job-close backstop end-to-end by spawning genuine
``sys.executable`` child trees, assigning them to a job, and asserting the kernel
reaps them when the job handle closes (and when a committed-memory cap is breached).

GATING: the kill tests need a real Win32 Job Object, so they are
``@unittest.skipUnless(os.name == "nt")`` — they actually run on this Windows box.
``setUp`` opts the governor in via ``CRAFTBENCH_GOVERN_RESOURCES=1`` and
``tearDown`` restores the prior environment exactly (set or unset). The
``test_noop_passthrough`` case is the cross-platform exception: it clears the env
var locally and proves the disabled path is a pure no-op everywhere.

Children are spawned with ``sys.executable -c "..."`` (the interpreter running the
suite — no launcher registration required) so the tests run on any Python; the
job-object/kill semantics are identical to the real L1/L2 spawns the governor wraps.
Each spawned child prints a ``ready`` handshake first, and the tests assert it
arrived — a child that failed to launch fails loudly instead of passing vacuously
(a dead-on-arrival child trivially satisfies "the child died").
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

import job_governor  # noqa: E402
from job_governor import assign, resource_job  # noqa: E402

_PY = [sys.executable]
_ENV_VAR = "CRAFTBENCH_GOVERN_RESOURCES"

# Win32 access bits / wait sentinels for liveness probing in the tests.
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_STILL_ACTIVE = 259


def _pid_alive(pid: int) -> bool:
    """True iff ``pid`` names a live (non-exited) process, probed via Win32.

    Uses OpenProcess(QUERY_LIMITED_INFORMATION) + GetExitCodeProcess so the test's
    liveness check is independent of job_governor's own handle plumbing. A pid that
    can't be opened is treated as dead (the common reap outcome). Windows-only —
    callers guard with the os.name skip."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_uint]
    handle = k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return False
    try:
        code = ctypes.c_ulong(0)
        k32.GetExitCodeProcess.restype = ctypes.c_int
        k32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        ok = k32.GetExitCodeProcess(handle, ctypes.byref(code))
        if not ok:
            return False
        return code.value == _STILL_ACTIVE
    finally:
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        k32.CloseHandle(handle)


def _wait_until(predicate, timeout_s: float, interval_s: float = 0.1) -> bool:
    """Poll ``predicate`` until truthy or ``timeout_s`` elapses; return its final value."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval_s)
    return predicate()


@unittest.skipUnless(os.name == "nt", "Win32 Job Object backstop is Windows-only")
class TestJobGovernorKill(unittest.TestCase):
    """Real-kill behavior; runs on Windows with the governor opted in."""

    def setUp(self):
        # Opt the governor in for the duration of the test; remember the prior
        # value so tearDown restores the environment byte-for-byte.
        self._prev = os.environ.get(_ENV_VAR)
        os.environ[_ENV_VAR] = "1"

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(_ENV_VAR, None)
        else:
            os.environ[_ENV_VAR] = self._prev

    def test_kill_on_job_close_terminates_child(self):
        """A long-sleeping child assigned to the job dies when the job closes."""
        with resource_job(name="cb-test-kill") as job:
            self.assertIsNotNone(job, "governor should be enabled on Windows w/ env set")
            proc = subprocess.Popen(
                _PY + ["-c", "import time; print('ready', flush=True); time.sleep(600)"],
                stdout=subprocess.PIPE, text=True)
            self.assertTrue(assign(job, proc.pid))
            # Startup handshake: a child that never launched would also "die",
            # so the kill assertion below would pass vacuously without this.
            line = proc.stdout.readline().strip()
            proc.stdout.close()  # done reading; avoid an unclosed-pipe ResourceWarning
            self.assertEqual(line, "ready", f"child never started (got {line!r})")
            self.assertIsNone(proc.poll(), "child should be alive inside the job")
        # Job handle closed -> KILL_ON_JOB_CLOSE reaps the assigned tree.
        self.assertTrue(
            _wait_until(lambda: proc.poll() is not None, timeout_s=3.0),
            "child was not reaped within 3s of job close",
        )
        self.assertIsNotNone(proc.poll())

    def test_memory_limit_kills_hog(self):
        """A child that commits past the job memory cap is terminated by the kernel."""
        # 256 MB cap; the child grows + touches a bytearray well past it. The job's
        # JOB_OBJECT_LIMIT_JOB_MEMORY makes the over-commit fail/abort the child.
        hog = (
            "import time\n"
            "print('ready', flush=True)\n"   # startup handshake (asserted below)
            "buf = bytearray()\n"
            "chunk = b'x' * (16 * 1024 * 1024)\n"  # 16 MB chunks
            "for _ in range(200):\n"               # would reach ~3.2 GB unbounded
            "    buf += chunk\n"
            "    buf[-1] = 1\n"                     # touch to force commit
            "    time.sleep(0.02)\n"
            "time.sleep(600)\n"                     # if never killed, the test deadline trips
        )
        with resource_job(memory_limit_mb=256, name="cb-test-mem") as job:
            self.assertIsNotNone(job)
            proc = subprocess.Popen(_PY + ["-c", hog], stdout=subprocess.PIPE, text=True)
            self.assertTrue(assign(job, proc.pid))
            # Startup handshake: a hog that never launched exits fast + non-zero,
            # which would satisfy BOTH assertions below without capping anything.
            line = proc.stdout.readline().strip()
            proc.stdout.close()  # done reading; avoid an unclosed-pipe ResourceWarning
            self.assertEqual(line, "ready", f"hog child never started (got {line!r})")
            died = _wait_until(lambda: proc.poll() is not None, timeout_s=30.0, interval_s=0.2)
            self.assertTrue(died, "memory hog was not terminated before the 30s deadline")
            self.assertNotEqual(proc.returncode, 0,
                                "hog should exit non-zero (killed / MemoryError), not clean")

    def test_child_tree_killed(self):
        """Closing the job reaps a grandchild the assigned parent spawned."""
        # The parent prints its grandchild's pid on stdout, then both sleep long.
        # We assign only the PARENT to the job; KILL_ON_JOB_CLOSE must still reap
        # the grandchild because the job owns the whole spawned tree.
        parent_src = (
            "import subprocess, sys, time\n"
            "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)'])\n"
            "print(g.pid, flush=True)\n"
            "time.sleep(600)\n"
        )
        with resource_job(name="cb-test-tree") as job:
            self.assertIsNotNone(job)
            proc = subprocess.Popen(_PY + ["-c", parent_src], stdout=subprocess.PIPE, text=True)
            self.assertTrue(assign(job, proc.pid))
            line = proc.stdout.readline().strip()
            proc.stdout.close()  # done reading; avoid an unclosed-pipe ResourceWarning
            self.assertTrue(line.isdigit(), f"parent did not report grandchild pid (got {line!r})")
            grandchild_pid = int(line)
            self.assertTrue(_pid_alive(grandchild_pid), "grandchild should be alive before job close")
        # Job closed: parent AND grandchild must be gone.
        self.assertTrue(
            _wait_until(lambda: proc.poll() is not None, timeout_s=3.0),
            "parent was not reaped within 3s",
        )
        self.assertTrue(
            _wait_until(lambda: not _pid_alive(grandchild_pid), timeout_s=3.0),
            "grandchild survived the job close (tree was not fully reaped)",
        )


class TestJobGovernorNoop(unittest.TestCase):
    """The disabled path is a pure passthrough — runs on every platform."""

    def setUp(self):
        # This class deliberately exercises the DISABLED governor, so it clears the
        # opt-in env regardless of ambient state, and restores it in tearDown.
        self._prev = os.environ.get(_ENV_VAR)
        os.environ.pop(_ENV_VAR, None)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(_ENV_VAR, None)
        else:
            os.environ[_ENV_VAR] = self._prev

    def test_noop_passthrough(self):
        """With the env unset, resource_job yields None and assign is a no-op True."""
        self.assertFalse(job_governor._enabled())
        with resource_job(memory_limit_mb=256, name="cb-test-noop") as job:
            self.assertIsNone(job, "disabled governor must yield None")
            # assign on a None job is a no-op that reports success, no exception.
            self.assertTrue(assign(job, 123))
        # assign(None, ...) is True even outside the context.
        self.assertTrue(assign(None, 123))


if __name__ == "__main__":
    unittest.main()
