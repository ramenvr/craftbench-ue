"""The answer key must not sit inside the tree the agent is invited to explore.

MEASURED 2026-08-26/27. The hide copied the ORIGINAL fixture bodies to
`runs/<this-run>/fairness_backup/CraftBenchTests/` -- inside the agent's own
reachable filesystem. The agent runs under `--permission-mode bypassPermissions`,
which makes `--add-dir` and the deliberately "neutral cwd" HINTS rather than
boundaries. Across 53 cells, seven touched that directory and two read the
fixture bodies back in full and were voided for it. The hide had MOVED the key
and left it in the same room.

This is a hiding place, not a permission boundary: an agent that guessed the path
could still read it. What it removes is DISCOVERY -- both real leaks began with a
walk of the run tree, one of them a worktree-wide `Glob`.

The round trip is tested as hard as the placement, because a hide that cannot
restore is worse than the leak: it bricks the substrate for every later cell.

Stdlib only. No UE, no editor, no tokens.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import fairness  # noqa: E402
from fairness import (_CRAFTBENCH_TESTS_REL, _FIXTURE_POINTER,  # noqa: E402
                      fixture_backup_root, load_fairness_state,
                      stage_fairness_hide, stage_fairness_restore)

BODY = "// the graded assertion text and the UNDISCLOSED tolerance constants\n"


def _project(tmp: Path):
    proj = tmp / "UE-projects" / "ThirdPerson"
    tests = proj / _CRAFTBENCH_TESTS_REL
    tests.mkdir(parents=True)
    (tests / "CraftBenchFunctionalTest.h").write_text(BODY, encoding="utf-8")
    (tests / "CraftBenchFunctionalTest.cpp").write_text(BODY, encoding="utf-8")
    run = tmp / "runs" / "unreal-mcp" / "20260827-120000-t1-x-unreal-mcp-m"
    run.mkdir(parents=True)
    return proj, run


class TestTheKeyLeavesTheRunTree(unittest.TestCase):
    def test_no_fixture_body_survives_anywhere_under_the_run_dir(self):
        with tempfile.TemporaryDirectory() as d:
            proj, run = _project(Path(d))
            state = stage_fairness_hide(proj, run)
            try:
                leaked = [p for p in run.rglob("*")
                          if p.is_file() and BODY in p.read_text(
                              encoding="utf-8", errors="replace")]
                self.assertEqual([], leaked,
                                 "the answer key is still inside runs/")
            finally:
                stage_fairness_restore(state, proj)

    def test_the_live_file_really_was_stubbed(self):
        # Guards the premise: if nothing was hidden, "no leak" is vacuous.
        with tempfile.TemporaryDirectory() as d:
            proj, run = _project(Path(d))
            state = stage_fairness_hide(proj, run)
            try:
                live = (proj / _CRAFTBENCH_TESTS_REL
                        / "CraftBenchFunctionalTest.cpp").read_text(encoding="utf-8")
                self.assertNotIn(BODY, live)
                self.assertTrue(state.stubbed_rels)
            finally:
                stage_fairness_restore(state, proj)

    def test_the_parked_copy_exists_outside_the_run_dir(self):
        with tempfile.TemporaryDirectory() as d:
            proj, run = _project(Path(d))
            state = stage_fairness_hide(proj, run)
            try:
                parked = fixture_backup_root(run / "fairness_backup")
                self.assertTrue(parked.is_dir())
                self.assertNotIn(str(run).lower(), str(parked).lower())
                self.assertTrue(any(BODY in p.read_text(encoding="utf-8",
                                                        errors="replace")
                                    for p in parked.rglob("*") if p.is_file()))
            finally:
                stage_fairness_restore(state, proj)


class TestTheRoundTripStillWorks(unittest.TestCase):
    """A hide that cannot restore bricks the substrate for every later cell."""

    def test_restore_returns_the_original_bodies(self):
        with tempfile.TemporaryDirectory() as d:
            proj, run = _project(Path(d))
            state = stage_fairness_hide(proj, run)
            stage_fairness_restore(state, proj)
            for name in ("CraftBenchFunctionalTest.h", "CraftBenchFunctionalTest.cpp"):
                self.assertEqual(
                    BODY, (proj / _CRAFTBENCH_TESTS_REL / name).read_text(
                        encoding="utf-8"), name)

    def test_crash_recovery_finds_the_parked_copy_via_the_pointer(self):
        # The process that parked it is gone; only what is on disk can lead
        # back. Without the pointer the rebuild sees an empty backup and
        # silently restores nothing.
        with tempfile.TemporaryDirectory() as d:
            proj, run = _project(Path(d))
            state = stage_fairness_hide(proj, run)
            backup_root = run / "fairness_backup"
            self.assertTrue((backup_root / _FIXTURE_POINTER).is_file())
            recovered = load_fairness_state(backup_root)
            self.assertEqual(sorted(state.stubbed_rels),
                             sorted(recovered.stubbed_rels))
            stage_fairness_restore(recovered, proj)
            self.assertEqual(BODY, (proj / _CRAFTBENCH_TESTS_REL
                                    / "CraftBenchFunctionalTest.cpp").read_text(
                                        encoding="utf-8"))


class TestTheInterlocksStillSeeWhatTheyRead(unittest.TestCase):
    """Two callers key on the DIRECTORY existing, not on its contents:
    `runs_clean` never deletes a unit still holding one, and the crash-recovery
    rebuild walks it. Emptying it entirely would break both silently."""

    def test_fairness_backup_still_exists_during_a_drive(self):
        with tempfile.TemporaryDirectory() as d:
            proj, run = _project(Path(d))
            state = stage_fairness_hide(proj, run)
            try:
                self.assertTrue((run / "fairness_backup").is_dir())
            finally:
                stage_fairness_restore(state, proj)


if __name__ == "__main__":
    unittest.main()
