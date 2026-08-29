"""Offline invariants for the static first-wave package."""

import ast
from pathlib import Path
import unittest


TASK = Path(__file__).resolve().parents[2]
REPO = TASK.parents[2]
TASK_ID = "t3-alerted-crowd-shares-live-poses-by-state"
RUNTIME = (REPO / "UE-projects" / "ThirdPerson" / "Source" / "ThirdPerson" /
           "Tasks" / TASK_ID / "AlertCrowdSharingActors.cpp")
FIXTURE = (REPO / "UE-projects" / "ThirdPerson" / "Source" /
           "CraftBenchTests" / "Tasks" / TASK_ID /
           "AlertCrowdSharingFunctionalTest.cpp")
INTROSPECT = (TASK / "authoring" / "fixed_introspector" /
              "t3_alerted_crowd_sharing.py")
AUTHOR = (REPO / "UE-projects" / "ThirdPerson" / "Source" /
          "CraftBenchTests" / "Tasks" / TASK_ID /
          "AlertCrowdSharingAssetAuthoring.cpp")


class StaticContractTests(unittest.TestCase):
    def test_every_authoring_script_parses(self):
        for path in sorted((TASK / "authoring").rglob("*.py")):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_runtime_scaffold_uses_cmc_not_direct_transform(self):
        source = RUNTIME.read_text(encoding="utf-8")
        self.assertIn("Movement->AddInputVector", source)
        self.assertNotIn("SetActorLocation", source)
        self.assertNotIn("SetLeaderPoseComponent", source)
        self.assertIn("EvaluateAlertState(Subject)", source)

    def test_fixture_reads_engine_manager_leader_and_single_node(self):
        source = FIXTURE.read_text(encoding="utf-8")
        for token in ("CheckDataForActor", "LeaderPoseComponent",
                      "GetSingleNodeInstance", "GetAnimationAsset",
                      "GetCurrentTime", "RTS_Component"):
            self.assertIn(token, source)
        self.assertIn("Subject->TravelDirection = FVector::ForwardVector", source)
        self.assertNotIn("Index % 2 == 0", source)

    def test_override_author_removes_generated_parent_call(self):
        source = AUTHOR.read_text(encoding="utf-8")
        self.assertIn("TArray<UEdGraphNode*>(Graph->Nodes)", source)
        self.assertIn("Graph->RemoveNode(Node)", source)
        self.assertIn("UK2Node_FunctionEntry", source)
        self.assertIn("UK2Node_FunctionResult", source)

    def test_final_reference_authoring_is_separated_and_fail_closed(self):
        source = AUTHOR.read_text(encoding="utf-8")
        self.assertIn("AuthorEmptyFinalScaffold", source)
        self.assertIn("AuthorReferenceAssets", source)
        self.assertIn("InspectFinalAssets", source)
        self.assertIn("expected_complete=0", source)
        self.assertIn("expected_complete=1", source)

        authoring = TASK / "authoring"
        empty_author = (authoring / "author_final_assets.py").read_text("utf-8")
        reference_author = (
            authoring / "author_reference_assets.py").read_text("utf-8")
        final_map = (authoring / "author_final_map.py").read_text("utf-8")
        self.assertIn("author_empty_final_scaffold", empty_author)
        self.assertNotIn("author_reference_assets", empty_author)
        self.assertIn("author_reference_assets", reference_author)
        self.assertIn("AlertCrowdSharingFunctionalTest", final_map)
        self.assertNotIn("AdmissionFunctionalTest", final_map)

    def test_introspector_denominator_and_submission_boundary_are_fixed(self):
        source = INTROSPECT.read_text(encoding="utf-8")
        # Parse constants without executing main()/requiring Unreal.
        tree = ast.parse(source)
        selected = [node for node in tree.body if isinstance(
            node, (ast.Assign, ast.Try, ast.Import, ast.ImportFrom,
                   ast.FunctionDef))]
        compile(ast.Module(body=selected, type_ignores=[]),
                str(INTROSPECT), "exec")
        self.assertIn("CRAFTBENCH_SUBMITTED_FILES_JSON", source)
        self.assertIn("SetupDefinesTwoEngineSharedPoseStates", source)
        self.assertIn("ProcessorReadsTheLiveAlertFact", source)
        self.assertIn("SubmissionHasNoIndependentAnimationSubstitute", source)
        self.assertEqual(source.count("AS_AlertCrowdSharing.uasset"), 1)
        self.assertEqual(source.count("BP_AlertCrowdStateProcessor.uasset"), 1)


if __name__ == "__main__":
    unittest.main()
