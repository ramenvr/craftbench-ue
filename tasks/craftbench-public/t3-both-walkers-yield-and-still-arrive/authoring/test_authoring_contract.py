"""Lightweight tests for fail-closed runner parsing and map facts."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


HERE = Path(__file__).resolve().parent


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "walker_yield_runner", HERE / "run_admission.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RunnerContractTests(unittest.TestCase):
    def test_json_writer_serializes_path_evidence(self):
        module = load_runner()
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "evidence.json"
            module.write_json(path, {"log_path": Path(raw) / "l2.log"})
            self.assertIn('"log_path":', path.read_text(encoding="utf-8"))

    def test_map_wrappers_bootstrap_their_own_import_directory(self):
        for name in ("author_admission_map.py", "author_final_map.py"):
            text = (HERE / name).read_text(encoding="utf-8")
            self.assertIn("Path(__file__).resolve().parent", text)
            self.assertIn("sys.path.insert(0", text)

    def test_exact_enumeration_is_unique(self):
        module = load_runner()
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "list.log"
            path.write_text("prefix " + module.EXACT_FILTER + " suffix\n",
                            encoding="utf-8")
            self.assertEqual(module.parse_enumeration(path),
                             [module.EXACT_FILTER])

    def test_duplicate_lines_deduplicate_but_foreign_candidate_fails_shape(self):
        module = load_runner()
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "list.log"
            foreign = ("Project.Functional Tests.Foreign.Map."
                       + module.DISPLAY_NAME)
            path.write_text("\n".join((module.EXACT_FILTER,
                                       module.EXACT_FILTER, foreign)),
                            encoding="utf-8")
            self.assertEqual(module.parse_enumeration(path),
                             sorted((module.EXACT_FILTER, foreign)))

    def test_missing_listing_is_empty(self):
        module = load_runner()
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "list.log"
            path.write_text("Automation list complete\n", encoding="utf-8")
            self.assertEqual(module.parse_enumeration(path), [])

    def test_world_facts_are_distinct(self):
        text = (HERE / "author_map_common.py").read_text(encoding="utf-8")
        self.assertIn('Scenario("LayoutA", (-2200.0, 0.0)', text)
        self.assertIn('Scenario("LayoutB", (2200.0, 0.0)', text)
        self.assertIn("25.0, 115.0", text)
        self.assertIn("36.0, 54.0", text)
        self.assertIn("configure_goal_marker(goal)", text)

    def test_navigation_is_dynamic_and_runtime_built_without_bypass(self):
        fixture = (HERE.parents[3] / "UE-projects" / "ThirdPerson" /
                   "Source" / "CraftBenchTests" / "Tasks" /
                   "t3-both-walkers-yield-and-still-arrive" /
                   "BothWalkersYieldFunctionalTest.cpp").read_text(
                       encoding="utf-8")
        author = (HERE.parents[3] / "UE-projects" / "ThirdPerson" /
                  "Source" / "CraftBenchTests" / "Tasks" /
                  "t3-both-walkers-yield-and-still-arrive" /
                  "WalkerYieldAuthoringLibrary.cpp").read_text(
                      encoding="utf-8")
        self.assertIn("ERuntimeGenerationType::Dynamic", author)
        self.assertIn("ERuntimeGenerationType::Dynamic", fixture)
        self.assertIn("NavigationSystem->Build()", fixture)
        self.assertIn("MoveToLocation(", fixture)
        self.assertNotIn("SimpleMoveTo", fixture)

    def test_reference_uses_one_engine_avoidance_system(self):
        fixture = (HERE.parents[3] / "UE-projects" / "ThirdPerson" /
                   "Source" / "CraftBenchTests" / "Tasks" /
                   "t3-both-walkers-yield-and-still-arrive" /
                   "BothWalkersYieldFunctionalTest.cpp").read_text(
                       encoding="utf-8")
        author = (HERE.parents[3] / "UE-projects" / "ThirdPerson" /
                  "Source" / "CraftBenchTests" / "Tasks" /
                  "t3-both-walkers-yield-and-still-arrive" /
                  "WalkerYieldAuthoringLibrary.cpp").read_text(
                      encoding="utf-8")
        self.assertIn("ADetourCrowdAIController::StaticClass", author)
        self.assertIn("bUseRVOAvoidance = false", author)
        self.assertIn("UCrowdManager::GetCurrent", fixture)
        self.assertIn("IsAgentValid", fixture)
        self.assertNotIn("GetAvoidanceObjectForUID", fixture)

    def test_admission_controls_are_isolated_and_gate_specific(self):
        module = load_runner()
        self.assertEqual(module.CONTROL_GATES, {
            "no-avoidance": "BothAgentsConflictDrivenSteering",
            "freeze-one": "BothAgentsKeepForwardProgress",
            "collision-disabled": "NoOverlapEnRoute",
            "permanent-detour": "BothAgentsReachOwnGoals",
        })
        fixture = (HERE.parents[3] / "UE-projects" / "ThirdPerson" /
                   "Source" / "CraftBenchTests" / "Tasks" /
                   "t3-both-walkers-yield-and-still-arrive" /
                   "BothWalkersYieldFunctionalTest.cpp").read_text(
                       encoding="utf-8")
        self.assertIn("CRAFTBENCH_WALKER_YIELD_CONTROL", fixture)
        self.assertIn(
            "ABothWalkersYieldAdmissionFunctionalTest::StaticClass()",
            fixture)
        self.assertIn("SetCrowdObstacleAvoidance(false)", fixture)
        self.assertIn("DisableMovement()", fixture)
        self.assertIn("SetCollisionResponseToChannel(ECC_Pawn, ECR_Ignore)",
                      fixture)
        self.assertIn('AdmissionControl == TEXT("permanent-detour")', fixture)

    def test_reference_cold_readback_uses_final_asset_path(self):
        text = (HERE / "introspect_walker_yield.py").read_text(
            encoding="utf-8")
        self.assertIn('"reference": ("/Game/Tasks/%s/BP_YieldingWalker"',
                      text)
        self.assertIn('"baseline", "reference", "admission", "final"', text)


if __name__ == "__main__":
    unittest.main()
