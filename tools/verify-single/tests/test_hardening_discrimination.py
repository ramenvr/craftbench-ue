"""UE-gated discrimination tests for the lightweight-hardening resource governor.

These exercise the *whole* runner end-to-end (build + PIE) with the opt-in
``--govern-resources`` flag turned ON, to prove the Win32 Job Object backstop does
NOT change verdicts — it is a runaway-containment backstop, never a gate:

  - the reference solution still PASSes, and
  - an empty submission still FAILs,

both with the governor active. (Component A — verify-time scaffold isolation — was
dropped: it breaks the L1 build because the hash-pinned CraftBenchTests fixtures
#include the task scaffold headers. See the hardening-prototype memory note.)

These tests REQUIRE a UE 5.8 install and so are gated behind ``CRAFTBENCH_UE_ROOT``
(the directory containing ``Engine/``). On a dev box without UE they SKIP — they
are an integration smoke gate, not a unit test. Each builds the run_task.py CLI
via subprocess (the same way an operator would invoke it) and asserts on both the
process exit code (0=pass / 1=fail) and the JSON report's ``overall`` field.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Make the verify package importable when running this file directly.
_HERE = Path(__file__).resolve().parent
_VERIFY = _HERE.parent
if str(_VERIFY) not in sys.path:
    sys.path.insert(0, str(_VERIFY))

REPO_ROOT = _VERIFY.parents[1]
RUN_TASK = _VERIFY / "run_task.py"

# Subject task: gp-spawner-population (bp-g2 set — survived the fresh-start
# cull and ships a folder-local reference/). Prefer the folder-per-task layout,
# fall back to the legacy flat .md — whichever exists on the UE box that
# actually runs this.
_TASK_CANDIDATES = (
    REPO_ROOT / "tasks" / "cpp" / "gp-spawner-population" / "task.md",
    REPO_ROOT / "tasks" / "bp-g2" / "gp-spawner-population.md",  # legacy flat shape, absent by design
)
TASK_PATH = next((p for p in _TASK_CANDIDATES if p.exists()), _TASK_CANDIDATES[-1])
REFERENCE_SUBMISSION = (
    REPO_ROOT / "tasks" / "cpp" / "gp-spawner-population" / "reference"
)

_UE_ROOT = os.environ.get("CRAFTBENCH_UE_ROOT")


@unittest.skipUnless(
    _UE_ROOT,
    "CRAFTBENCH_UE_ROOT not set (UE 5.8 install required for end-to-end "
    "discrimination)",
)
class TestGovernorDiscrimination(unittest.TestCase):
    """Reference PASS + empty FAIL, both with --govern-resources ON.

    Proves the Job Object backstop preserves the discrimination contract (it must
    not flip a FAIL to PASS, nor a PASS to FAIL)."""

    def _run_grade(self, submission: Path) -> tuple[int, str, dict]:
        """Invoke run_task.py with --govern-resources and return
        (exit_code, combined_output, parsed_report_dict)."""
        # Use a private, deterministic report path so the assertion does not
        # have to scrape stdout for a verdict.
        report_json = Path(self._tmp.name) / "report.json"
        cmd = [
            sys.executable,
            str(RUN_TASK),
            "--task",
            str(TASK_PATH),
            "--submission",
            str(submission),
            "--ue-root",
            str(_UE_ROOT),
            "--govern-resources",
            "--report-json",
            str(report_json),
        ]
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        report: dict = {}
        if report_json.exists():
            try:
                report = json.loads(report_json.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                report = {}
        return proc.returncode, combined, report

    def setUp(self) -> None:
        self.assertTrue(RUN_TASK.exists(), f"missing runner {RUN_TASK}")
        self.assertTrue(TASK_PATH.exists(), f"missing task spec {TASK_PATH}")
        self.assertTrue(
            REFERENCE_SUBMISSION.is_dir(),
            f"missing reference solution {REFERENCE_SUBMISSION}",
        )
        self._tmp = tempfile.TemporaryDirectory(prefix="cb-harden-disc-")
        self.addCleanup(self._tmp.cleanup)

    def test_reference_passes_with_governor_on(self) -> None:
        code, out, report = self._run_grade(REFERENCE_SUBMISSION)
        self.assertEqual(
            code,
            0,
            f"reference solution must PASS with --govern-resources on; "
            f"exit={code}\n{out}",
        )
        # Belt-and-suspenders: the report verdict must agree with the exit code.
        if report:
            self.assertEqual(report.get("overall"), "pass", out)

    def test_empty_fails_with_governor_on(self) -> None:
        # An empty submission tree: a valid (sandbox-clean) but behaviorally
        # empty directory. The verifier must still FAIL it with the governor on.
        empty = Path(self._tmp.name) / "empty-submission"
        (empty / "Source" / "CraftBenchTemplate").mkdir(parents=True)
        code, out, report = self._run_grade(empty)
        self.assertEqual(
            code,
            1,
            f"empty submission must FAIL with --govern-resources on; "
            f"exit={code}\n{out}",
        )
        if report:
            self.assertEqual(report.get("overall"), "fail", out)


if __name__ == "__main__":
    unittest.main()
