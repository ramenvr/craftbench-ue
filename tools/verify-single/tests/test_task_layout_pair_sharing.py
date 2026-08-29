"""Per-task staging must keep the directories a bp/cpp PAIR shares.

THE DEFECT, measured 2026-08-22. `stage_per_task_dirs_active_only` deleted every
per-task directory whose name was not exactly the active task id. The 2026-08-20
surface rename gave the task ids their `-bp`/`-cpp` suffixes while the
directories a pair SHARES kept their old names, so for
`t1-mud-wade-bp` the staging deleted:

  * `Content/Tasks/t1-mud-wade/` — the SUPPLIED
    animation clip the prompt orders the agent to play, and
  * `Source/ThirdPerson/Tasks/t1-mud-wade-cpp/` — the
    PARENT CLASS the Blueprint has to derive from.

Both legs lost the clip: neither `...-bp` nor `...-cpp` equals the unsuffixed
directory name, so the C++ leg was broken too. Nobody noticed because that pair
had never been graded — which is exactly why this file exists rather than a note.

Each test below states which side of the rule it pins, because a keep-rule can
fail in two opposite directions and only one of them is loud:

  * keeping too LITTLE deletes the task's own inputs and makes a correct answer
    impossible — silent, and what actually happened;
  * keeping too MUCH leaves a foreign task's material visible, which is the
    anti-gaming property the staging exists for.

Stdlib only. No editor, no UE, no tokens.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from task_layout import pair_base, stage_per_task_dirs_active_only  # noqa: E402

CONTENT = "Content/Tasks"
SOURCE = "Source/ThirdPerson/Tasks"
MAPS = "Content/Maps"


def _tree(*rel_dirs: str) -> Path:
    """A disposable staged tree holding one file inside each named directory."""
    root = Path(tempfile.mkdtemp())
    for rel in rel_dirs:
        d = root / rel
        d.mkdir(parents=True)
        (d / "keep.txt").write_text("x", encoding="utf-8")
    return root


class TestThePairKeepsWhatItShares(unittest.TestCase):
    """Keeping too little — the direction that was silently broken."""

    def test_the_unsuffixed_shared_dir_survives_the_bp_leg(self):
        # The mud clip. This is the exact deletion that made the task unwinnable.
        tree = _tree(f"{CONTENT}/t1-mud-wade")
        removed = stage_per_task_dirs_active_only(tree, "t1-mud-wade-bp")
        self.assertEqual([], removed)
        self.assertTrue((tree / CONTENT / "t1-mud-wade").is_dir())

    def test_the_unsuffixed_shared_dir_survives_the_cpp_leg_TOO(self):
        # The half everyone missed: the C++ leg's id does not equal the
        # unsuffixed directory either, so it lost the clip as well.
        tree = _tree(f"{CONTENT}/t1-mud-wade")
        removed = stage_per_task_dirs_active_only(tree, "t1-mud-wade-cpp")
        self.assertEqual([], removed)
        self.assertTrue((tree / CONTENT / "t1-mud-wade").is_dir())

    def test_the_sibling_legs_source_dir_survives(self):
        # The parent class lives in <base>-cpp for BOTH legs, because that is
        # where the scaffold was authored. A bp run that loses it cannot derive
        # from anything.
        tree = _tree(f"{SOURCE}/t1-mud-wade-cpp")
        removed = stage_per_task_dirs_active_only(tree, "t1-mud-wade-bp")
        self.assertEqual([], removed)
        self.assertTrue((tree / SOURCE / "t1-mud-wade-cpp").is_dir())

    def test_the_active_dir_itself_still_survives(self):
        tree = _tree(f"{CONTENT}/t1-mud-wade-bp")
        removed = stage_per_task_dirs_active_only(tree, "t1-mud-wade-bp")
        self.assertEqual([], removed)

    def test_a_maps_dir_shared_by_the_pair_survives(self):
        # Content/Maps matters more than the others: the L2 automation filter
        # prefix comes from the MAP's folder, so deleting it does not merely hide
        # a map, it makes the fixture unfindable.
        tree = _tree(f"{MAPS}/t1-mud-wade")
        removed = stage_per_task_dirs_active_only(tree, "t1-mud-wade-cpp")
        self.assertEqual([], removed)


class TestForeignTasksAreStillDeleted(unittest.TestCase):
    """Keeping too much — the anti-gaming property the staging exists for."""

    def test_an_unrelated_task_is_still_removed(self):
        tree = _tree(f"{CONTENT}/t1-mud-wade", f"{CONTENT}/t2-race-clock")
        removed = stage_per_task_dirs_active_only(tree, "t1-mud-wade-bp")
        self.assertEqual([f"{CONTENT}/t2-race-clock"], removed)
        self.assertFalse((tree / CONTENT / "t2-race-clock").exists())
        self.assertTrue((tree / CONTENT / "t1-mud-wade").is_dir())

    def test_an_unrelated_task_that_merely_SHARES_A_PREFIX_is_removed(self):
        # The rule is suffix-stripping, NOT prefix matching. `t1-mud-wade-slow`
        # is a different task whose name happens to start the same way, and it
        # must not survive just because it looks similar.
        tree = _tree(f"{CONTENT}/t1-mud-wade", f"{CONTENT}/t1-mud-wade-slow")
        removed = stage_per_task_dirs_active_only(tree, "t1-mud-wade-bp")
        self.assertEqual([f"{CONTENT}/t1-mud-wade-slow"], removed)

    def test_another_pairs_sibling_is_removed(self):
        tree = _tree(f"{SOURCE}/t1-mud-wade-cpp", f"{SOURCE}/t3-gate-and-door-cpp")
        removed = stage_per_task_dirs_active_only(tree, "t1-mud-wade-bp")
        self.assertEqual([f"{SOURCE}/t3-gate-and-door-cpp"], removed)

    def test_an_unsuffixed_task_keeps_only_itself(self):
        # A task with no surface suffix must not suddenly start keeping siblings.
        tree = _tree(f"{CONTENT}/gp-crafting-queue", f"{CONTENT}/gp-crafting-queue-bp")
        removed = stage_per_task_dirs_active_only(tree, "gp-crafting-queue")
        self.assertEqual([f"{CONTENT}/gp-crafting-queue-bp"], removed)
        self.assertTrue((tree / CONTENT / "gp-crafting-queue").is_dir())

    def test_engine_folders_under_content_are_still_kept(self):
        # The pre-existing `require_task_like` guard: Developers/ and the OFPA
        # mirrors are not per-task and must never be swept.
        tree = _tree(f"{CONTENT}/Developers", f"{CONTENT}/t2-race-clock")
        removed = stage_per_task_dirs_active_only(tree, "t1-mud-wade-bp")
        self.assertEqual([f"{CONTENT}/t2-race-clock"], removed)
        self.assertTrue((tree / CONTENT / "Developers").is_dir())


class TestPairBaseIsTheOneImplementation(unittest.TestCase):
    def test_task_layout_uses_runlibs_suffix_rule_rather_than_its_own(self):
        # Imported, not copied: a rename in run_identity must break this loudly.
        import run_identity
        self.assertIs(pair_base, run_identity.pair_base)

    def test_both_surfaces_reduce_to_one_base(self):
        self.assertEqual(pair_base("t1-mud-wade-bp"), pair_base("t1-mud-wade-cpp"))

    def test_an_id_with_no_surface_suffix_is_unchanged(self):
        self.assertEqual(pair_base("gp-crafting-queue"), "gp-crafting-queue")

    def test_a_set_prefix_is_stripped_so_a_qualified_id_still_matches(self):
        self.assertEqual(pair_base("bp/t1-mud-wade-bp"), "t1-mud-wade")


if __name__ == "__main__":
    unittest.main()
