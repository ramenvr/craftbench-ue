"""The post-marker drain — the fix for an 8s-per-leg stdout pipe deadlock.

`_run_editor_with_marker_kill` used to call `proc.wait(timeout=8.0)` from INSIDE
`for line in proc.stdout`, which stops consuming the very pipe it waits on. A
child that keeps writing after the marker fills the OS buffer, blocks in write(),
and can never exit — so the grace ALWAYS expired and the child was terminated.

Measured against the real editor: 8.23s (warm) / 8.25s (cold) burned per L2I leg
AFTER the verdict was already captured, and the editor's own log ran 2,728 bytes
longer than ours, ending mid-shutdown with no "LogExit: Exiting.".

These tests reproduce that shape with a plain python child — no UE required.
"""
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

_VERIFY = Path(__file__).resolve().parent.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

from layers.l2_pie import _run_editor_with_marker_kill  # noqa: E402

MARKER = "CRAFTBENCH-TEST-MARKER-END"
# Comfortably past a Windows anonymous pipe's default (~4 KB) and a POSIX one
# (~64 KB), so the child MUST block unless we keep draining.
TAIL_BYTES = 256 * 1024


def _child(tail_bytes: int, exit_delay: float = 0.0) -> str:
    return textwrap.dedent(f"""
        import sys, time
        print("starting up", flush=True)
        print("{MARKER}", flush=True)
        # The editor's graceful shutdown: keep logging after the verdict.
        chunk = "x" * 120
        written = 0
        while written < {tail_bytes}:
            sys.stdout.write(chunk + chr(10))
            written += len(chunk) + 1
        sys.stdout.flush()
        time.sleep({exit_delay})
    """)


class TestPostMarkerDrain(unittest.TestCase):
    def _run(self, script: str, tmp: Path):
        log = tmp / "child.log"
        t0 = time.monotonic()
        code, killed = _run_editor_with_marker_kill(
            cmd=[sys.executable, "-c", script], env=None, log_path=log,
            timeout_seconds=60.0, markers=(MARKER,),
        )
        return time.monotonic() - t0, code, killed, log

    def test_child_that_writes_past_the_pipe_buffer_is_not_stalled(self):
        """THE regression. Before the fix this took the full 8s grace every
        time; the child physically could not exit."""
        with tempfile.TemporaryDirectory() as td:
            elapsed, _code, killed, log = self._run(_child(TAIL_BYTES), Path(td))
            self.assertTrue(killed, "marker was not detected")
            self.assertLess(
                elapsed, 5.0,
                f"took {elapsed:.1f}s — the post-marker wait is still blocking "
                f"the pipe it waits on (pre-fix this was ~8s)")

    def test_the_post_marker_output_is_actually_captured(self):
        """A second, independent win: we used to throw the shutdown log away.
        The real editor's own copy was 2,728 bytes longer than ours."""
        with tempfile.TemporaryDirectory() as td:
            _elapsed, _code, _killed, log = self._run(
                _child(TAIL_BYTES), Path(td))
            text = log.read_text(encoding="utf-8", errors="replace")
            self.assertIn(MARKER, text)
            after = text.split(MARKER, 1)[1]
            self.assertGreater(
                len(after), 100_000,
                "post-marker output was discarded; the drain is not running")

    def test_a_child_that_lingers_is_still_terminated(self):
        """Draining must not become waiting forever — a child that goes quiet
        without exiting is still killed, which is the marker-kill's whole job
        (UE on macOS sits in a Cocoa runloop after RequestExit)."""
        with tempfile.TemporaryDirectory() as td:
            elapsed, _code, killed, _log = self._run(
                _child(2000, exit_delay=60.0), Path(td))
            self.assertTrue(killed)
            self.assertLess(elapsed, 20.0,
                            f"lingering child was not reaped ({elapsed:.1f}s)")

    def test_quiet_child_exits_fast(self):
        with tempfile.TemporaryDirectory() as td:
            elapsed, _code, killed, _log = self._run(_child(0), Path(td))
            self.assertTrue(killed)
            self.assertLess(elapsed, 5.0)


if __name__ == "__main__":
    unittest.main()
