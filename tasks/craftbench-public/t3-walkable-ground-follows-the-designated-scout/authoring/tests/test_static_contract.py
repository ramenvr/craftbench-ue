"""Lightweight source/AST locks for the admission-first package."""

import ast
from pathlib import Path
import unittest


TASK = Path(__file__).resolve().parents[2]
REPO = TASK.parents[2]
AUTHOR = TASK / "authoring" / "author_admission_map.py"
READBACK = TASK / "authoring" / "admission_map_readback.py"
RUNNER = TASK / "authoring" / "run_admission.py"
INTRO = (TASK / "authoring" / "fixed_introspector" /
         "t3_walkable_ground_designated_scout.py")
CPP_ROOT = (REPO / "UE-projects" / "ThirdPerson" / "Source" /
            "CraftBenchTests" / "Tasks" /
            "t3-walkable-ground-follows-the-designated-scout")


class StaticContractTests(unittest.TestCase):

    def test_all_python_sources_parse(self):
        for path in (AUTHOR, READBACK, RUNNER, INTRO):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_author_is_map_only_and_refuses_production_outputs(self):
        text = AUTHOR.read_text(encoding="utf-8")
        self.assertIn("refusing existing admission map namespace", text)
        self.assertIn("production final/task/reference boundary is not absent", text)
        self.assertIn("serialized_nav_data=0", text)
        self.assertNotIn("BP_DesignatedScout.uasset", text)

    def test_fixture_uses_engine_navigation_and_never_ticks_it_manually(self):
        text = (CPP_ROOT / "WalkableGroundAdmissionFunctionalTest.cpp").read_text(
            encoding="utf-8")
        for token in ("GetInvokerLocations", "GetActiveTileSet",
                      "GetNumActiveTiles", "FindPathSync", "MoveToLocation",
                      "GetPathFollowingComponent"):
            self.assertIn(token, text)
        for forbidden in ("World->Tick(", "NavigationSystem->Tick(",
                          "SetGenerateNavigationOnlyAround"):
            self.assertNotIn(forbidden, text)

    def test_admission_nav_system_hard_pins_dynamic_invoker_mode(self):
        text = (CPP_ROOT / "WalkableGroundAdmissionTypes.cpp").read_text(
            encoding="utf-8")
        self.assertIn("ERuntimeGenerationType::Dynamic", text)
        self.assertIn(
            "bGenerateNavigationOnlyAroundNavigationInvokers = true", text)
        self.assertIn("SetGenerationRadii(1600.0f, 2200.0f)", text)

    def test_fixed_introspector_denominator_and_manifest_are_exact(self):
        tree = ast.parse(INTRO.read_text(encoding="utf-8"))
        assignments = {node.targets[0].id: ast.literal_eval(node.value)
                       for node in tree.body if isinstance(node, ast.Assign)
                       and len(node.targets) == 1
                       and isinstance(node.targets[0], ast.Name)
                       and node.targets[0].id in {"CHECK_IDS"}}
        self.assertEqual(len(assignments["CHECK_IDS"]), 3)
        text = INTRO.read_text(encoding="utf-8")
        self.assertIn("BP_DesignatedScout.uasset", text)
        self.assertIn("SubmissionHasNoGlobalNavigationSubstitute", text)


if __name__ == "__main__":
    unittest.main()
