"""Tests for the live-run advisory lock (pure fcntl — no UE, no Aura, no network).

The lock serializes a `--live-project` run (which transiently hides the shared
source substrate via fairness-hide) against any other process that reads the
source tree, closing the cross-process FileNotFoundError window observed
2026-06-04.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from live_lock import (  # noqa: E402
    LiveRunLockBusy, acquire_live_run_lock, is_live_run_active, live_run_lock)

_PKG = str(Path(__file__).resolve().parents[1])


class TestLiveRunLock(unittest.TestCase):
    def _lp(self, td) -> Path:
        return Path(td) / ".live-run.lock"

    def test_inactive_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(is_live_run_active(self._lp(td)))

    def test_active_while_held_then_released(self):
        with tempfile.TemporaryDirectory() as td:
            lp = self._lp(td)
            with live_run_lock(lp):
                self.assertTrue(is_live_run_active(lp))     # a sibling reader sees it
            self.assertFalse(is_live_run_active(lp))         # released on normal exit

    def test_released_on_exception(self):
        with tempfile.TemporaryDirectory() as td:
            lp = self._lp(td)
            with self.assertRaises(RuntimeError):
                with live_run_lock(lp):
                    raise RuntimeError("boom")
            self.assertFalse(is_live_run_active(lp))          # finally-released even on error

    def test_second_acquire_nonblocking_is_busy(self):
        with tempfile.TemporaryDirectory() as td:
            lp = self._lp(td)
            with live_run_lock(lp):
                with self.assertRaises(LiveRunLockBusy):
                    with live_run_lock(lp, blocking=False):
                        pass

    def test_timeout_raises_when_held(self):
        with tempfile.TemporaryDirectory() as td:
            lp = self._lp(td)
            with live_run_lock(lp):
                t0 = time.monotonic()
                with self.assertRaises(LiveRunLockBusy):
                    with live_run_lock(lp, timeout=0.2):
                        pass
                self.assertGreaterEqual(time.monotonic() - t0, 0.15)

    def test_acquire_release_helper(self):
        # The try/finally-style API the graded runners use.
        with tempfile.TemporaryDirectory() as td:
            lp = self._lp(td)
            release = acquire_live_run_lock(lp)
            try:
                self.assertTrue(is_live_run_active(lp))
                with self.assertRaises(LiveRunLockBusy):
                    acquire_live_run_lock(lp)
            finally:
                release()
            self.assertFalse(is_live_run_active(lp))
            # Reacquirable after release.
            release2 = acquire_live_run_lock(lp)
            release2()

    def test_cross_process_lock(self):
        # The real point: a SEPARATE process holding the lock must be visible to us.
        with tempfile.TemporaryDirectory() as td:
            lp = self._lp(td)
            acq = lp.with_suffix(".acquired")
            rel = lp.with_suffix(".release")
            code = textwrap.dedent(f"""
                import sys, time
                from pathlib import Path
                sys.path.insert(0, {_PKG!r})
                from live_lock import live_run_lock
                with live_run_lock(Path({str(lp)!r})):
                    Path({str(acq)!r}).write_text("1")
                    while not Path({str(rel)!r}).exists():
                        time.sleep(0.02)
            """)
            proc = subprocess.Popen([sys.executable, "-c", code])
            try:
                for _ in range(250):
                    if acq.exists():
                        break
                    time.sleep(0.02)
                self.assertTrue(acq.exists(), "child never acquired the lock")
                self.assertTrue(is_live_run_active(lp), "parent must see the child's live lock")
            finally:
                rel.write_text("1")
                proc.wait(timeout=5)
            self.assertFalse(is_live_run_active(lp), "lock must free once the child exits")


if __name__ == "__main__":
    unittest.main()
