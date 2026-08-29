"""Regression tests for the pre-drive live-project hygiene guard.

THE BUG THESE PIN (P0, 2026-08-18). A `--live-project` run writes its deliverable
into `Content/Tasks/<task>/`, which is UNTRACKED, so `git checkout -- UE-projects/`
leaves it and the fairness stage deliberately keeps the ACTIVE task's folder. The
next run of that task therefore started on top of the previous run's finished work
and graded normally — two of five cells that day, and they were the two best-looking
ones. Nothing in `result.json` distinguished such a run from an honest one.

The tests below are written against the two properties that make the bug possible,
not against the code path that happened to expose it:
  1. an untracked file in the writable area must not survive into the drive, and
  2. when the question CANNOT be answered, the run must not be reported as clean.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from live_hygiene import (  # noqa: E402
    QUARANTINE_SUBDIR, HygieneReport, quarantine_untracked_writable, untracked_under)

WRITABLE = ("Content/Tasks/", "Source/CraftBenchTemplate/")


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


def _init_repo(root: Path):
    _git(["init", "-q"], root)
    _git(["config", "user.email", "t@t"], root)
    _git(["config", "user.name", "t"], root)


class TestUntrackedDetection(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _init_repo(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def _commit(self, rel, body="x"):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        _git(["add", "-A"], self.root)
        _git(["commit", "-qm", "c"], self.root)
        return p

    def test_committed_baseline_is_not_a_leftover(self):
        """A task whose baseline IS committed must be left completely alone.

        This is the case the fairness rule exists for; quarantining it would break
        every asset task that ships a starting point.
        """
        self._commit("Content/Tasks/demo/Baseline.uasset")
        rels, reason = untracked_under(self.root, WRITABLE)
        self.assertEqual(reason, "")
        self.assertEqual(rels, [])

    def test_untracked_deliverable_is_found(self):
        self._commit("README.md")
        leftover = self.root / "Content/Tasks/demo/GA_Prev.uasset"
        leftover.parent.mkdir(parents=True, exist_ok=True)
        leftover.write_bytes(b"previous run's work")
        rels, reason = untracked_under(self.root, WRITABLE)
        self.assertEqual(reason, "")
        self.assertIn("Content/Tasks/demo/GA_Prev.uasset", rels)

    def test_untracked_outside_the_writable_area_is_ignored(self):
        """Scope discipline: the guard must not become a general tree cleaner."""
        self._commit("README.md")
        (self.root / "Saved").mkdir(parents=True, exist_ok=True)
        (self.root / "Saved" / "scratch.log").write_text("noise", encoding="utf-8")
        rels, _ = untracked_under(self.root, WRITABLE)
        self.assertEqual(rels, [])

    def test_gitignored_build_output_is_never_listed(self):
        """Binaries/ and friends are ignored, so the guard must not provoke a rebuild."""
        (self.root / ".gitignore").write_text("Binaries/\n", encoding="utf-8")
        self._commit("README.md")
        b = self.root / "Content/Tasks/demo/Binaries"
        b.mkdir(parents=True, exist_ok=True)
        (b / "big.dll").write_bytes(b"\x00" * 16)
        rels, _ = untracked_under(self.root, WRITABLE)
        self.assertEqual(rels, [])


class TestQuarantine(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "proj"
        self.run_dir = Path(self._tmp.name) / "run"
        self.root.mkdir(parents=True)
        self.run_dir.mkdir(parents=True)
        _init_repo(self.root)
        (self.root / "README.md").write_text("r", encoding="utf-8")
        _git(["add", "-A"], self.root)
        _git(["commit", "-qm", "c"], self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_leftover_is_moved_not_deleted(self):
        """Quarantine, never delete — the bytes are the evidence the bug happened."""
        rel = "Content/Tasks/demo/GA_Prev.uasset"
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"previous run")

        rep = quarantine_untracked_writable(self.root, WRITABLE, self.run_dir)

        self.assertTrue(rep.checked)
        self.assertEqual(rep.quarantined, [rel])
        self.assertTrue(rep.safe_to_grade)
        self.assertFalse(p.exists(), "the agent must not still see the leftover")
        moved = self.run_dir / QUARANTINE_SUBDIR / rel
        self.assertTrue(moved.exists(), "the bytes must be preserved for audit")
        self.assertEqual(moved.read_bytes(), b"previous run")

    def test_clean_tree_reports_checked_and_safe(self):
        rep = quarantine_untracked_writable(self.root, WRITABLE, self.run_dir)
        self.assertTrue(rep.checked)
        self.assertEqual(rep.quarantined, [])
        self.assertTrue(rep.safe_to_grade)

    def test_non_git_tree_is_UNAVAILABLE_never_clean(self):
        """The core inversion: an unanswerable check must not report success.

        Reporting "clean" from a check that did not run is precisely how the
        original bug stayed invisible, so this is the single most important
        assertion in the file.
        """
        plain = Path(self._tmp.name) / "not-a-repo"
        (plain / "Content/Tasks/demo").mkdir(parents=True)
        (plain / "Content/Tasks/demo/GA.uasset").write_bytes(b"x")

        rep = quarantine_untracked_writable(plain, WRITABLE, self.run_dir)

        self.assertFalse(rep.checked)
        self.assertFalse(rep.safe_to_grade)
        self.assertTrue(rep.unavailable_reason)
        # And it must NOT have moved anything on a guess.
        self.assertTrue((plain / "Content/Tasks/demo/GA.uasset").exists())

    def test_stuck_file_makes_the_run_unsafe_to_grade(self):
        rep = HygieneReport(checked=True, quarantined=["a"], stuck=["b (PermissionError)"])
        self.assertFalse(rep.safe_to_grade)

    def test_report_serialises_for_result_json(self):
        rep = quarantine_untracked_writable(self.root, WRITABLE, self.run_dir)
        blob = json.loads(json.dumps(rep.as_dict()))
        self.assertIn("safe_to_grade", blob)
        self.assertIn("quarantined", blob)


if __name__ == "__main__":
    unittest.main()
