"""Offline contracts for the Alert Stride first-wave package."""

import ast
from pathlib import Path
import tempfile
import unittest

from alert_stride_common import ASSET_NAMES, FINAL_INTERFACE, snapshot


HERE = Path(__file__).resolve().parent
TASK = HERE.parent
REPO = TASK.parents[2]
RUNTIME = (REPO / "UE-projects/ThirdPerson/Source/ThirdPerson/Tasks"
           / TASK.name)
TESTS = (REPO / "UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks"
         / TASK.name)


class StaticContracts(unittest.TestCase):
    def test_task_local_import_wrappers_bootstrap_their_directory(self):
        for name in (
                "author_admission_assets.py", "author_final_assets.py",
                "author_admission_map.py", "author_final_map.py",
                "readback_assets.py", "readback_map.py"):
            source = (HERE / name).read_text(encoding="utf-8")
            self.assertIn("Path(__file__).resolve().parent", source, name)
            self.assertIn("sys.path.insert(0", source, name)

    def test_map_readback_cold_loads_the_exact_package(self):
        source = (HERE / "readback_map.py").read_text(encoding="utf-8")
        self.assertIn("levels.load_level(map_package)", source)
        self.assertIn("ADMISSION_MAP if args.mode", source)

    def test_animation_layer_uses_domain_specific_graph_path(self):
        source = (TESTS / "AlertStrideAssetAuthoring.cpp").read_text(
            encoding="utf-8")
        self.assertIn("AddDomainSpecificGraph(Interface, Graph)", source)
        self.assertNotIn("AddFunctionGraph<UClass>(\n\t\t\tInterface, Graph", source)

    def test_alert_layer_authors_load_bearing_upper_body_offset(self):
        source = (TESTS / "AlertStrideAssetAuthoring.cpp").read_text(
            encoding="utf-8")
        for token in (
                'BoneName = TEXT("hand_r")',
                "Modify->SetNodeValue(",
                "GET_MEMBER_NAME_CHECKED(FAnimNode_ModifyBone, Translation)",
                "Modify->Node.Translation, FVector(0.0, 0.0, 18.0)",
                "PinTranslation.Equals(Expected, KINDA_SMALL_NUMBER)",
                "FAIL ALERT_STRIDE_ALERT_DELTA_READBACK",
                "TranslationMode = BMM_Additive",
                "RotationMode = BMM_Ignore",
                "TranslationSpace = BCS_ComponentSpace"):
            self.assertIn(token, source)
        self.assertNotIn('BoneName = TEXT("spine_03")', source)

    def test_complete_reference_reuses_read_only_interface(self):
        source = (TESTS / "AlertStrideAssetAuthoring.cpp").read_text(
            encoding="utf-8")
        for token in (
                "bComplete && PackageIndex == 0",
                "LoadObject<UAnimBlueprint>(nullptr, *Packages[0])",
                "!bComplete && (!AddLayerFunction(Interface)"):
            self.assertIn(token, source)

    def test_reference_author_is_exact_four_asset_overlay(self):
        source = (HERE / "author_reference.py").read_text(encoding="utf-8")
        for token in (
                "editable namespace must be absent",
                "read-only interface is absent",
                "author_asset_set(ROOT, INTERFACE, True)",
                "exact four-asset inventory mismatch",
                "ALERT-STRIDE-REFERENCE-AUTHOR-PASS"):
            self.assertIn(token, source)

    def test_reference_readback_is_complete_without_changing_final_mode(self):
        source = (HERE / "readback_assets.py").read_text(encoding="utf-8")
        self.assertIn('(\"admission\", \"final\", \"reference\")', source)
        self.assertIn('args.mode in (\"admission\", \"reference\")', source)
        self.assertIn("root, interface, is_complete", source)

    def test_final_fixture_names_match_authored_actor_labels(self):
        spec = (HERE.parent / "task.md").read_text(encoding="utf-8")
        self.assertIn(
            '"L_AlertStride :: AAlertStrideSlowFunctionalTest"', spec)
        self.assertIn(
            '"L_AlertStride :: AAlertStrideFastFunctionalTest"', spec)
        map_author = (HERE / "author_map_common.py").read_text(
            encoding="utf-8")
        self.assertIn('"SlowEarly": "AlertStrideSlowFunctionalTest"', map_author)
        self.assertIn('"FastLate": "AlertStrideFastFunctionalTest"', map_author)

    def test_host_implements_layer_interface_before_linked_layer_graph(self):
        source = (TESTS / "AlertStrideAssetAuthoring.cpp").read_text(
            encoding="utf-8")
        implement = source.index("ImplementLayerInterface(Host, Interface)")
        graph = source.index("BuildHostGraph(Host, Interface, Calm, bComplete)")
        self.assertLess(implement, graph)
        self.assertIn("FAIL ALERT_STRIDE_HOST_INTERFACE", source)

    def test_verifier_emits_condensed_json_for_exact_gate_tokens(self):
        source = (TESTS / "AlertStrideVerifierLibrary.cpp").read_text(
            encoding="utf-8")
        self.assertIn("TCondensedJsonPrintPolicy<TCHAR>", source)
        self.assertIn("Facts->SetBoolField(TEXT(\"probe_ok\"), bPass)", source)

    def test_python_parses(self):
        for path in HERE.glob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_complete_file_set(self):
        for path in (
            TASK / "task.md", TASK / "notes.md",
            TASK / "OWNER_SHARED_PATCH.md",
            TASK / "discrimination/MATRIX.md", HERE / "RUNBOOK.md",
            HERE / "API_AUDIT.md", HERE / "REFERENCE_RECIPE.md",
            HERE / "t3_alert_stride_linked_layer.py",
            RUNTIME / "AlertStrideTypes.h", RUNTIME / "AlertStrideTypes.cpp",
            TESTS / "AlertStrideFunctionalTest.h",
            TESTS / "AlertStrideFunctionalTest.cpp",
            TESTS / "AlertStrideVerifierLibrary.h",
            TESTS / "AlertStrideVerifierLibrary.cpp",
            TESTS / "AlertStrideAssetAuthoring.h",
            TESTS / "AlertStrideAssetAuthoring.cpp",
        ):
            self.assertTrue(path.is_file(), str(path))

    def test_engine_owned_runtime_evidence(self):
        runtime = (RUNTIME / "AlertStrideTypes.cpp").read_text("utf-8")
        fixture = (TESTS / "AlertStrideFunctionalTest.cpp").read_text("utf-8")
        for token in (
            "UStateTreeComponent", "GetActiveStateNames",
            "LinkAnimClassLayers", "UnlinkAnimClassLayers",
            "GetLinkedAnimLayerInstanceByClass", "AddMovementInput",
        ):
            self.assertIn(token, runtime)
        for token in (
            "GetEngineActiveStateNames", "GetLinkedAnimLayerInstanceByClass",
            "GetSocketTransform", "GetCurrentActiveMontage",
            "IsMovingOnGround", "SetCheckpointSchedule",
            "AlertStateBecomesActive",
            "BehaviorStateLinksAndDrivesDeclaredLayer",
            "LowerBodyStrideRemainsContinuous",
            "ClearRestoresOriginalLayerWithoutRestart",
        ):
            self.assertIn(token, fixture)
        self.assertNotIn("SetActorLocation", fixture)

    def test_structure_is_load_bearing(self):
        author = (TESTS / "AlertStrideAssetAuthoring.cpp").read_text("utf-8")
        verifier = (TESTS / "AlertStrideVerifierLibrary.cpp").read_text("utf-8")
        for token in (
            "UAnimLayerInterfaceFactory", "ImplementNewInterface",
            "UAnimGraphNode_LinkedAnimLayer", "UAnimGraphNode_LayeredBoneBlend",
            "AddConditionWithOuter<FAlertStrideSignalCondition>",
            "AddTask<FAlertStrideLinkLayerTask>", "CompileStateTree",
        ):
            self.assertIn(token, author)
        for token in (
            "GetLinkedAnimLayerNodeProperties", "FAnimNode_LinkedAnimLayer",
            "UAnimGraphNode_Slot", "state_tree_calm_alert_bidirectional",
            "locomotion_is_base_pose", "no_slot_or_montage_route",
        ):
            self.assertIn(token, verifier)

    def test_task_contract_is_fixed_and_live_matrix_is_recorded(self):
        task = (TASK / "task.md").read_text("utf-8")
        notes = (TASK / "notes.md").read_text("utf-8")
        matrix = (TASK / "discrimination/MATRIX.md").read_text("utf-8")
        self.assertIn("layers: [L1, L2, L2I]", task)
        self.assertEqual(task.count("L_AlertStride ::"), 2)
        self.assertIn("introspect: [t3_alert_stride_linked_layer.py]", task)
        self.assertIn("HOLD", notes)
        self.assertIn(
            "AUTHORED-WIP / LIVE-SUBSTRATE REFERENCE-EMPTY MATRIX PASS",
            notes)
        self.assertIn("Rounds 03 through 07", notes)
        self.assertIn(
            "AUTHORED-WIP / LIVE-SUBSTRATE REFERENCE-EMPTY MATRIX PASS",
            matrix)
        self.assertIn("Corrected-map empty L2", matrix)
        self.assertIn("Fresh governed supplied empty", matrix)

    def test_l2i_has_fixed_four_check_denominator(self):
        source = (HERE / "t3_alert_stride_linked_layer.py").read_text("utf-8")
        module = ast.parse(source)
        assignment = next(node for node in module.body
                          if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name)
                                  and target.id == "CHECK_IDS"
                                  for target in node.targets))
        self.assertEqual(len(assignment.value.elts), 4)
        self.assertIn("no_slot_or_montage_route", source)

    def test_read_only_interface_is_outside_submission_inventory(self):
        self.assertEqual(len(ASSET_NAMES), 4)
        self.assertNotIn("ALI_AlertStrideUpperBody", ASSET_NAMES)
        self.assertEqual(
            FINAL_INTERFACE,
            "/Game/Maps/t3-alert-state-swaps-the-upper-body-without-breaking-stride/"
            "ALI_AlertStrideUpperBody")

    def test_runner_exact_one_nullrhi_and_watchdog(self):
        runner = (HERE / "run_admission.py").read_text("utf-8")
        for token in (
            "Project.Functional Tests.__CraftBenchAdmission.",
            "AlertStrideAdmissionFunctionalTest", "expected_test_count=1",
            "use_nullrhi=True", "watchdog_seconds", "taskkill",
            "fullTestPath", "testDisplayName", "state",
        ):
            self.assertIn(token, runner)

    def test_snapshot_hashes_plain_files_and_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a.bin").write_bytes(b"alert-stride")
            value = snapshot(root)
            self.assertEqual(value["kind"], "directory")
            self.assertEqual(set(value["files"]), {"a.bin"})
            link = root / "link.bin"
            try:
                link.symlink_to(root / "a.bin")
            except OSError:
                return
            with self.assertRaises(RuntimeError):
                snapshot(root)


if __name__ == "__main__":
    unittest.main()
