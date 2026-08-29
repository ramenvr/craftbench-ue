"""Offline trust-boundary tests for the SaveGame task."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
AUTHORING = HERE.parent
TASK = AUTHORING.parent
REPO = AUTHORING.parents[3]
RUNTIME = (REPO / "UE-projects" / "ThirdPerson" / "Source" /
           "ThirdPerson" / "Tasks" / TASK.name)
FIXTURE = (REPO / "UE-projects" / "ThirdPerson" / "Source" /
           "CraftBenchTests" / "Tasks" / TASK.name)


class StaticContractTests(unittest.TestCase):
    def test_python_parses(self):
        for path in AUTHORING.rglob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_reference_header_matches_live_surface(self):
        live = RUNTIME / "RunResumePersistenceComponent.h"
        reference = (TASK / "reference" / "Source" / "ThirdPerson" /
                     "Tasks" / TASK.name / live.name)
        self.assertEqual(live.read_bytes(), reference.read_bytes())

    def test_source_lock_inventories_are_exact(self):
        live_names = sorted(path.name for path in RUNTIME.iterdir()
                            if path.is_file())
        reference_root = (TASK / "reference" / "Source" / "ThirdPerson" /
                          "Tasks" / TASK.name)
        reference_names = sorted(path.name for path in reference_root.iterdir()
                                 if path.is_file())
        self.assertEqual(live_names, [
            "RunResumePersistenceComponent.cpp",
            "RunResumePersistenceComponent.h",
            "RunResumeProtectedTypes.cpp",
            "RunResumeProtectedTypes.h",
        ])
        self.assertEqual(reference_names, [
            "RunResumePersistenceComponent.cpp",
            "RunResumePersistenceComponent.h",
        ])

    def test_fixed_gate_denominators(self):
        task = (TASK / "task.md").read_text(encoding="utf-8")
        fixture = (FIXTURE / "LatestMarkerResumeFunctionalTest.cpp").read_text(
            encoding="utf-8")
        for gate in (
                "FreshNonceScopedSlotBeginsEmpty",
                "NewestCheckpointRecordIsSerialized",
                "CollectedRewardIdentitySetIsSerialized",
                "ResumeUsesLatestMarkerTransform",
                "RewardTotalRestoresExactly",
                "AlreadyCollectedRewardsDoNotPayTwice",
                "UncollectedControlStillPaysOnce"):
            self.assertEqual(task.count("`" + gate + "`"), 1)
            self.assertGreaterEqual(fixture.count(gate), 1)

    def test_runner_is_two_process_and_exact_cleanup(self):
        runner = (AUTHORING / "run_protocol.py").read_text(encoding="utf-8")
        self.assertEqual(runner.count("run_l2("), 2)
        self.assertIn("slot_file.unlink()", runner)
        self.assertNotIn("glob(", runner)
        self.assertNotIn("rmtree", runner)

    def test_task_local_and_shared_introspectors_match(self):
        local = AUTHORING / "fixed_introspector" / "t3_latest_marker_resume.py"
        shared = REPO / "tools" / "verify-single" / "introspect" / local.name
        self.assertEqual(local.read_bytes(), shared.read_bytes())


if __name__ == "__main__":
    unittest.main()
