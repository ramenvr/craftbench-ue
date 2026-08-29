"""Unit tests for the kill audit — the one trail that lets the rig rule ITSELF
out when a process dies mid-run.

HISTORY OF THIS FILE (2026-08-28, public-release cut). It used to open with two
suites covering `aura_rig/run_graded.py`'s ceiling-cutoff relabel
(`flag_agent_cutoff`: a 905s drive against a 900s ceiling becoming AGENT-TIMEOUT
instead of a FAIL that reached the pass-rate denominator) and its editor-death
gate (`_model_pin_gate` -> EDITOR-GONE). `run_graded.py` was the spine of the
aura-product lane, which is not part of this release; it is gone, and with it
`VERDICT_AGENT_TIMEOUT` / `VERDICT_EDITOR_GONE`, which no surviving arm emits.
The three shipped arms (claude-p / aura-mcp / unreal-mcp) all run through
`tools/run-agent/run.py`, whose wall-clock ceiling is the adapter's own
`timeout_s` (run.py:416/:899) and whose verdict constants live in
`adapters/base.py`. So those two suites went with the module they tested. The
file KEEPS its name so the path stays stable for anyone holding a reference to
it; what it now covers is the kill audit alone.

Why the kill audit is worth its own suite even though `test_kill_guard.py`
exists: that module redirects `stack._KILL_AUDIT_PATH` into a tempdir and
asserts on line CONTENT (`REFUSED(test-process)`, `image=...`, `role=test`). The
two properties below are different and neither is covered there — the line must
be readable by another process the instant `audit_kill` returns (no buffering,
no close in between; a trail you can only read after the writer exits is useless
while you are watching a run die), and `audit_kill` must never raise, because it
sits inside teardown paths where an audit failure would break the kill it is
recording.

The incident these pin: 2026-08-03, a run died with no crash dump and the rig
could not tell whether it had killed its own editor — see
the build-machine handoff §4, and the fuller 2026-08-07 finding in the repo conventions
("NO PROCESS KILL FROM A TEST PROCESS"), where a unit-test run really had
murdered a live drive editor and the missing `role=` field is what made it take
two days to establish.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestKillAudit(unittest.TestCase):
    """Every process the rig kills must leave a flushed line, or the rig cannot
    rule ITSELF out when something dies (which is exactly what happened on
    2026-08-03 — see the build-machine handoff §4)."""

    def test_audit_line_is_written_and_flushed_immediately(self):
        from aura_rig import stack
        path = stack._KILL_AUDIT_PATH()
        before = path.read_text(encoding="utf-8") if path.exists() else ""
        stack.audit_kill("pid=424242 (unit test)", "unit-test")
        after = path.read_text(encoding="utf-8")     # no close/flush in between
        self.assertGreater(len(after), len(before))
        line = after[len(before):]
        for token in ("pid=424242", "reason=unit-test", "caller="):
            self.assertIn(token, line)

    def test_audit_never_raises(self):
        """It runs inside teardown paths; an audit failure must never be able to
        break a kill."""
        from aura_rig import stack
        stack.audit_kill(None, None)          # type: ignore[arg-type]
        stack.audit_kill("", "")


if __name__ == "__main__":
    unittest.main()
