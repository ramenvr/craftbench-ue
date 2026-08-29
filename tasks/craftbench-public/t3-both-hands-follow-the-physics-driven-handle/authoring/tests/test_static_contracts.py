"""Offline seams for the first-wave two-hand authoring package."""

import ast
from pathlib import Path
import unittest


TASK = Path(__file__).resolve().parents[2]
REPO = TASK.parents[2]
RUNTIME = (REPO / "UE-projects" / "ThirdPerson" / "Source" / "ThirdPerson" /
           "Tasks" / TASK.name)
VERIFIER = (REPO / "UE-projects" / "ThirdPerson" / "Source" /
            "CraftBenchTests" / "Tasks" / TASK.name)


class StaticContracts(unittest.TestCase):
    def test_all_python_parses(self):
        files = sorted(TASK.rglob("*.py"))
        self.assertGreaterEqual(len(files), 10)
        for path in files:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_fixed_denominators_are_named_in_spec_and_source(self):
        task = (TASK / "task.md").read_text(encoding="utf-8")
        fixture = (VERIFIER / "TwoHandPhysicsFunctionalTest.cpp").read_text(
            encoding="utf-8")
        introspector = (TASK / "authoring" / "fixed_introspector" /
                        "t3_both_hands_physics.py").read_text(encoding="utf-8")
        for gate in (
                "HandleMovesThroughRealConstraint",
                "BothHandsTrackSamePhysicalHandle",
                "TrackingRespondsToSecondImpulseDirection",
                "FeetAndPelvisPreserveBasePose"):
            self.assertIn(gate, task)
            self.assertIn(gate, fixture)
        for gate in (
                "RuntimeControlRigComposesOverBasePose",
                "RigUsesIndependentHandControls",
                "NoDirectTransformTwoBoneIKOrMirror"):
            self.assertIn(gate, task)
            self.assertIn(gate, introspector)

    def test_runtime_is_transport_not_pose_solver(self):
        text = "\n".join(path.read_text(encoding="utf-8")
                         for path in RUNTIME.glob("TwoHandPhysicsActors.*"))
        for forbidden in ("ControlRig.h", "SetBoneTransformByName",
                          "TwoBoneIK", "ModifyBone"):
            self.assertNotIn(forbidden, text)
        self.assertIn("LeftHandTarget", text)
        self.assertIn("RightHandTarget", text)
        self.assertIn("GetRelativeTransform", text)

    def test_anim_inputs_use_public_compiler_mapping_api(self):
        author = (VERIFIER / "TwoHandRigAssetAuthoring.cpp").read_text(
            encoding="utf-8")
        inspect = (VERIFIER / "TwoHandRigIntrospectionLibrary.cpp").read_text(
            encoding="utf-8")
        self.assertEqual(author.count("AddSourceTargetProperties("), 2)
        self.assertNotIn("SetCustomPinVisibility", author)
        self.assertNotIn("CustomPinProperties", author)
        self.assertNotIn("UK2Node_VariableGet", author)
        self.assertIn("HasExactPropertyMappings", inspect)
        self.assertIn("FAnimNode_CustomProperty::StaticStruct()", inspect)

    def test_fixture_never_manually_ticks_world_or_animation(self):
        text = (VERIFIER / "TwoHandPhysicsFunctionalTest.cpp").read_text(
            encoding="utf-8")
        for forbidden in ("World->Tick(", "TickAnimation(",
                          "RefreshBoneTransforms(", "Subject->Tick("):
            self.assertNotIn(forbidden, text)
        self.assertIn("SetCheckpointSchedule", text)
        self.assertIn("OnWorldPostActorTick", text)
        self.assertIn("thresholds_frozen=%d", text)
        self.assertIn("constexpr bool bThresholdsFrozen = true", text)
        self.assertNotIn("CandidateHandle", text)
        for threshold in (
                "FrozenHandleDisplacementMin = 4.0",
                "FrozenHandErrorMax = 18.0",
                "FrozenControlErrorMax = 2.0",
                "FrozenBodyTranslationMax = 8.0",
                "FrozenBodyAngularMaxDegrees = 15.0"):
            self.assertIn(threshold, text)

    def test_admission_runner_is_exact_one_real_rhi_with_watchdog(self):
        text = (TASK / "authoring" / "run_admission.py").read_text(
            encoding="utf-8")
        self.assertIn("expected_test_count=1", text)
        self.assertIn("use_nullrhi=False", text)
        self.assertIn("watchdog_seconds", text)
        self.assertIn("taskkill-exact-owned-tree", text)
        self.assertIn("TwoHandPhysicsAdmissionFunctionalTest", text)
        self.assertIn("thresholds_frozen=1", text)

    def test_authoring_is_first_write_fail_closed(self):
        for name in ("author_admission_assets.py", "author_baseline_assets.py",
                     "author_admission_map.py", "author_final_map.py"):
            text = (TASK / "authoring" / name).read_text(encoding="utf-8")
            self.assertTrue("refusing existing" in text or
                            "require_absent" in text, name)
            self.assertNotIn("delete_asset", text)
            self.assertNotIn("shutil.rmtree", text)


if __name__ == "__main__":
    unittest.main()
