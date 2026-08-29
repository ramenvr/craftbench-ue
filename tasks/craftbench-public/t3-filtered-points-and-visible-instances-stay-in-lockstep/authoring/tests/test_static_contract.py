"""Offline trust-boundary checks for the PCG authoring package."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
AUTHORING = HERE.parent
TASK = AUTHORING.parent
REPO = AUTHORING.parents[3]
CPP = (REPO / "UE-projects" / "ThirdPerson" / "Source" /
       "CraftBenchTests" / "Tasks" / TASK.name)


class StaticContractTests(unittest.TestCase):
    def test_python_files_parse(self):
        for path in AUTHORING.rglob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_fixed_denominators_match_task(self):
        task = (TASK / "task.md").read_text(encoding="utf-8")
        fixture = (CPP / "FilteredPointInstancesFunctionalTest.cpp").read_text(
            encoding="utf-8")
        introspector = (AUTHORING / "fixed_introspector" /
                        "t3_filtered_points_visible_instances.py").read_text(
                            encoding="utf-8")
        gates = (
            "BelowThresholdPointsRejected",
            "ExclusionMarkedPointsRejected",
            "AllEligiblePointsRetained",
            "EligiblePointsNotDuplicated",
            "SpawnCountMatchesFilteredOutput",
            "SpawnTransformsMatchFilteredPoints",
        )
        checks = (
            "UsesMetadataDrivenDualFilter",
            "PublishesAndSpawnsTheSameFilteredBranch",
            "SubmissionHasNoInstanceSubstitute",
        )
        for gate in gates:
            self.assertEqual(task.count("`" + gate + "`"), 1)
            self.assertGreaterEqual(fixture.count(gate), 2)
        for check in checks:
            self.assertEqual(task.count("`" + check + "`"), 1)
            self.assertEqual(introspector.count('"' + check + '"'), 1)

    def test_oracle_and_engine_outputs_are_independent(self):
        fixture = (CPP / "FilteredPointInstancesFunctionalTest.cpp").read_text(
            encoding="utf-8")
        for token in (
                "GetPointFacts()", "GetProtectedFilterBounds()",
                "GetGeneratedGraphOutput()", "ForEachManagedResource",
                "UPCGManagedISMComponent", "GetInstanceTransform"):
            self.assertIn(token, fixture)
        self.assertNotIn("CandidateTelemetry", fixture)
        self.assertNotIn("ManualTick", fixture)

    def test_each_fixture_schedule_is_epoch_relative(self):
        fixture = (CPP / "FilteredPointInstancesFunctionalTest.cpp").read_text(
            encoding="utf-8")
        self.assertIn("GenerationIssuedAt + 0.25", fixture)
        self.assertIn("GenerationIssuedAt + 5.0", fixture)
        self.assertNotIn("SetCheckpointSchedule({0.25, 5.0})", fixture)

    def test_candidate_surface_is_exact_one_graph(self):
        task = (TASK / "task.md").read_text(encoding="utf-8")
        expected = (
            "Content/Tasks/t3-filtered-points-and-visible-instances-stay-in-"
            "lockstep/PCG_FilteredPointInstances.uasset"
        )
        self.assertIn("accepted_files: [" + expected + "]", task)
        introspector = (AUTHORING / "fixed_introspector" /
                        "t3_filtered_points_visible_instances.py").read_text(
                            encoding="utf-8")
        self.assertIn("PCG_FilteredPointInstances.uasset", introspector)
        self.assertNotIn(".umap\" % TASK_ID", introspector)

    def test_task_local_and_shared_introspectors_match(self):
        local = AUTHORING / "fixed_introspector" / \
            "t3_filtered_points_visible_instances.py"
        shared = REPO / "tools" / "verify-single" / "introspect" / local.name
        self.assertEqual(local.read_bytes(), shared.read_bytes())


if __name__ == "__main__":
    unittest.main()
