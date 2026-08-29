"""Offline contracts for the Guard Visible Aim first-wave package."""

import ast
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
TASK = HERE.parent
REPO = TASK.parents[2]
RUNTIME = (REPO / "UE-projects/ThirdPerson/Source/ThirdPerson/Tasks"
           / TASK.name)
TESTS = (REPO / "UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks"
         / TASK.name)


class StaticContracts(unittest.TestCase):
    def test_python_parses(self):
        for path in HERE.glob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_execute_python_wrappers_bootstrap_their_directory(self):
        for name in (
            "author_admission_assets.py", "author_final_assets.py",
            "author_admission_map.py", "author_final_map.py",
            "readback_assets.py",
        ):
            text = (HERE / name).read_text(encoding="utf-8")
            self.assertIn("Path(__file__).resolve().parent", text, name)
            self.assertIn("sys.path.insert(0, str(HERE))", text, name)

    def test_complete_file_set(self):
        for path in (
            TASK / "task.md", TASK / "notes.md",
            TASK / "discrimination/MATRIX.md", HERE / "RUNBOOK.md",
            RUNTIME / "GuardVisibleAimTypes.h",
            RUNTIME / "GuardVisibleAimTypes.cpp",
            TESTS / "GuardVisibleAimFunctionalTest.h",
            TESTS / "GuardVisibleAimFunctionalTest.cpp",
            TESTS / "GuardVisibleAimVerifierLibrary.h",
            TESTS / "GuardVisibleAimVerifierLibrary.cpp",
            TESTS / "GuardVisibleAimAssetAuthoring.h",
            TESTS / "GuardVisibleAimAssetAuthoring.cpp",
        ):
            self.assertTrue(path.is_file(), str(path))

    def test_behavior_and_graph_are_load_bearing(self):
        runtime = (RUNTIME / "GuardVisibleAimTypes.cpp").read_text("utf-8")
        fixture = (TESTS / "GuardVisibleAimFunctionalTest.cpp").read_text("utf-8")
        graph = (TESTS / "GuardVisibleAimVerifierLibrary.cpp").read_text("utf-8")
        for token in (
            "UAISenseConfig_Sight", "OnTargetPerceptionUpdated",
            "ForgetActor", "RegisterWithPerceptionSystem",
            "GetCurrentVisibleTarget", "AimYaw", "AimPitch", "AimAlpha",
        ):
            self.assertIn(token, runtime)
        for token in (
            "GetCurrentlyPerceivedActors", "GetKnownPerceivedActors",
            "GetBoneTransform", "MoveToLocation", "SetCheckpointSchedule",
            "EnsureRuntimeNavigationReady", "Navigation->Build()",
            "ProjectPointToNavigation", "FindPathToLocationSynchronously",
            "GUARD-VISIBLE-AIM-NAV-ROUTE PASS",
            "runtime_dynamic=1",
            "OnlySightPerceivedIdentityMayDriveAim",
            "PerceivedTargetDrivesAdditiveAimOverlay",
            "OccludedTargetStopsDrivingAim",
            "ReappearingTargetIsReacquired",
            "BaseLocomotionRemainsContinuous",
        ):
            self.assertIn(token, fixture)
        asset_author = (TESTS / "GuardVisibleAimAssetAuthoring.cpp").read_text(
            "utf-8")
        self.assertIn("ERuntimeGenerationType::Dynamic", asset_author)
        self.assertIn("runtime_supported=%d", asset_author)
        self.assertIn("projected_endpoints=%d", asset_author)
        self.assertIn("navigable_pairs=%d", asset_author)
        map_author = (HERE / "author_map_common.py").read_text("utf-8")
        self.assertEqual(map_author.count(
            "unreal.Vector(140.0, 55.0, 1.0)"), 1)
        self.assertEqual(map_author.count(
            "unreal.Vector(140.0, 55.0, 9.0)"), 1)
        self.assertIn(
            'Scenario("RightLow", (3500.0, 300.0), (1150.0, 400.0, 25.0)',
            map_author)
        for token in (
            "UAnimGraphNode_RotationOffsetBlendSpace",
            "UAimOffsetBlendSpace", "GroundSpeed", "AimYaw", "AimPitch",
            "AimAlpha", "UAnimGraphNode_Slot", "locomotion_is_base_pose",
        ):
            self.assertIn(token, graph)

    def test_task_contract_and_hold(self):
        task = (TASK / "task.md").read_text("utf-8")
        notes = (TASK / "notes.md").read_text("utf-8")
        matrix = (TASK / "discrimination/MATRIX.md").read_text("utf-8")
        self.assertIn("layers: [L1, L2, L2I]", task)
        self.assertEqual(task.count("L_GuardVisibleAim ::"), 2)
        self.assertIn("introspect: [t3_guard_visible_aim.py]", task)
        self.assertIn("GOVERNED REFERENCE PASS", notes)
        self.assertIn("GOVERNED EMPTY FAILS AS PREDICTED", notes)
        self.assertIn("REFGATE PENDING", notes)
        self.assertIn("GOVERNED REFERENCE PASS", matrix)
        self.assertIn("FAILS AT THE PREDICTED L2/L2I GATES", matrix)
        self.assertIn("REFGATE PENDING", matrix)

    def test_runner_is_exact_and_nullrhi(self):
        runner = (HERE / "run_admission.py").read_text("utf-8")
        for token in (
            "GuardVisibleAimAdmissionFunctionalTest", "expected_test_count=1",
            "use_nullrhi=True", "watchdog_seconds", "taskkill",
            "fullTestPath", "testDisplayName", "state",
        ):
            self.assertIn(token, runner)

    def test_map_readback_loads_exact_package_before_inspection(self):
        readback = (HERE / "readback_map.py").read_text("utf-8")
        for token in (
            "ADMISSION_MAP if args.mode == \"admission\" else FINAL_MAP",
            "levels.load_level(map_package)",
            "GUARD_AIM_MAP_LOAD",
            "get_editor_world()",
            "inspect_world",
        ):
            self.assertIn(token, readback)
        self.assertLess(readback.index("levels.load_level(map_package)"),
                        readback.index("get_editor_world()"))


if __name__ == "__main__":
    unittest.main()
