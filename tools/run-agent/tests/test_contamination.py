"""Unit tests for the context-contamination detector (fairness.py).

The signature it must catch (proven live 2026-07-11): a t0 drive delivered
ONLY a recreated SpawnerActor pair — a FOREIGN task's scaffold, marker comment
included — because the client's stale project context bypassed on-disk
isolation. It must NOT fire on normal runs: active-task edits, agent-authored
new files (no marker), or mixed deliverables that do touch the active task.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fairness import classify_deliverable_file, deliverable_contamination  # noqa: E402

_ACTIVE = "t0-sanity-log-on-beginplay"
_SPAWNER_HEAD = ("// ASpawnerActor — pre-existing actor for task "
                 "gp-spawner-population (ported from the g2-4 eval).\n")
_SANITY_HEAD = "// SanityActor for task t0-sanity-log-on-beginplay.\n"


class TestClassify(unittest.TestCase):
    def test_foldered_path_wins(self):
        self.assertEqual(
            classify_deliverable_file(
                "UE-projects/CraftBenchTemplate/Source/CraftBenchTemplate/"
                "Tasks/t0-sanity-log-on-beginplay/SanityActor.cpp",
                "", _ACTIVE),
            "active")
        self.assertEqual(
            classify_deliverable_file(
                "UE-projects/CraftBenchTemplate/Content/Tasks/"
                "umg-image-brush-bound/WBP_CardSlot.uasset",
                "", _ACTIVE),
            "foreign")

    def test_marker_classification_flat(self):
        self.assertEqual(
            classify_deliverable_file(
                "UE-projects/CraftBenchTemplate/Source/CraftBenchTemplate/"
                "SpawnerActor.cpp", _SPAWNER_HEAD, _ACTIVE),
            "foreign")
        self.assertEqual(
            classify_deliverable_file("x/SanityActor.cpp", _SANITY_HEAD, _ACTIVE),
            "active")

    def test_agent_authored_file_is_unknown(self):
        self.assertEqual(
            classify_deliverable_file(
                "UE-projects/CraftBenchTemplate/Source/CraftBenchTemplate/"
                "GA_LaunchAbility.cpp", "// my new ability\n", _ACTIVE),
            "unknown")

    def test_set_qualified_active_id(self):
        self.assertEqual(
            classify_deliverable_file(
                "x/Tasks/t0-sanity-log-on-beginplay/SanityActor.h", "",
                "cpp/t0-sanity-log-on-beginplay"),
            "active")


class TestDetector(unittest.TestCase):
    def _run(self, heads: dict):
        return deliverable_contamination(
            list(heads), _ACTIVE, lambda rel: heads[rel])

    def test_wrong_actor_signature_fires(self):
        # The live 2026-07-11 case: only a recreated foreign scaffold pair.
        hit = self._run({
            "UE-projects/CraftBenchTemplate/Source/CraftBenchTemplate/SpawnerActor.cpp": _SPAWNER_HEAD,
            "UE-projects/CraftBenchTemplate/Source/CraftBenchTemplate/SpawnerActor.h": _SPAWNER_HEAD,
        })
        self.assertIsNotNone(hit)
        self.assertEqual(len(hit["foreign_files"]), 2)

    def test_active_edit_never_flagged(self):
        self.assertIsNone(self._run({
            "UE-projects/CraftBenchTemplate/Source/CraftBenchTemplate/"
            "Tasks/t0-sanity-log-on-beginplay/SanityActor.cpp": _SANITY_HEAD,
        }))

    def test_mixed_deliverable_not_flagged(self):
        # Touching the active task exonerates the run even if foreign files
        # also moved (e.g. an agent that tidied a decoy alongside real work).
        self.assertIsNone(self._run({
            "x/Tasks/t0-sanity-log-on-beginplay/SanityActor.cpp": _SANITY_HEAD,
            "x/Source/CraftBenchTemplate/SpawnerActor.cpp": _SPAWNER_HEAD,
        }))

    def test_unknown_only_not_flagged(self):
        self.assertIsNone(self._run({
            "x/Source/CraftBenchTemplate/GA_New.cpp": "// fresh agent file\n",
        }))

    def test_unreadable_file_tolerated(self):
        def _head(rel):
            raise OSError("gone")
        self.assertIsNone(deliverable_contamination(["x/GA_New.cpp"], _ACTIVE, _head))

    def test_empty_deliverable_none(self):
        self.assertIsNone(self._run({}))


if __name__ == "__main__":
    unittest.main()
