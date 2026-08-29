"""Offline fake tests for run_admission.py.  Never starts UBT or Unreal."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


RUNNER_PATH = Path(__file__).with_name("run_admission.py")
SPEC = importlib.util.spec_from_file_location("catalog_admission_runner", RUNNER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load catalog admission runner")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_bytes(data)


def synthetic_workspace(root: Path) -> tuple[Path, Path]:
    repo = root / "repo"
    project = runner.project_root(repo)
    write(project / runner.UPROJECT_NAME, "{}\n")
    write(project / "Intermediate/Fake/CatalogReaderActor.obj", b"stale-empty")
    write(
        project / runner.RUNTIME_REL.with_suffix(".cpp"),
        "// Empty scaffold implementation\n",
    )
    write(
        project / runner.RUNTIME_REL.with_suffix(".h"),
        "// No catalog query or report behavior is\n// supplied\n",
    )
    for index, relative in enumerate(runner.CATALOG_FILE_RELS):
        write(project / runner.CATALOG_REL / relative, f"live-{index}".encode())
    write(project / runner.ADMISSION_MAP_REL, b"admission-map")

    reference = runner.reference_root(repo)
    write(
        reference / runner.REFERENCE_FILE_RELS[0],
        "// reference cpp\nvoid QueryCatalog();\n",
    )
    write(
        reference / runner.REFERENCE_FILE_RELS[1],
        "// reference h\nclass CatalogReference {};\n",
    )

    quarantine = root / "quarantine" / "Catalog"
    for index, relative in enumerate(runner.CATALOG_FILE_RELS):
        write(quarantine / relative, f"quarantine-{index}".encode())
    return repo, quarantine


class CatalogAdmissionRunnerTests(unittest.TestCase):
    def test_build_argv_pins_both_targets_and_all_four_required_flags(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            ue_root = root / "UE_5.8"
            write(
                ue_root / "Engine/Build/BatchFiles/Build.bat",
                "@echo off\n",
            )
            project = root / "scratch/ThirdPerson.uproject"
            commands = runner.build_commands(ue_root, project)
            self.assertEqual(
                [command[5] for command in commands],
                ["ThirdPersonEditor", "ThirdPerson"],
            )
            for command in commands:
                self.assertIn("-WaitMutex", command)
                self.assertIn("-NoHotReloadFromIDE", command)
                self.assertIn("-NoUBA", command)
                self.assertIn("-MaxParallelActions=2", command)
                self.assertIn(f"-Project={project}", command)

    def test_prepare_overlays_only_scratch_and_locks_exact_21(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            repo, quarantine = synthetic_workspace(root)
            output = root / "out"
            live_cpp = (
                runner.project_root(repo)
                / runner.RUNTIME_REL.with_suffix(".cpp")
            )
            live_before = live_cpp.read_bytes()

            state = runner.prepare_workspace(
                repo=repo,
                output_root=output,
                quarantine=quarantine,
                copy_func=lambda source, dest: shutil.copytree(source, dest),
            )

            self.assertEqual(len(state["locks_21"]), 21)
            self.assertEqual(live_cpp.read_bytes(), live_before)
            scratch_cpp = (
                Path(state["scratch_project"])
                / runner.RUNTIME_REL.with_suffix(".cpp")
            )
            reference_cpp = (
                runner.reference_root(repo) / runner.REFERENCE_FILE_RELS[0]
            )
            self.assertEqual(scratch_cpp.read_bytes(), reference_cpp.read_bytes())
            self.assertNotEqual(scratch_cpp.read_bytes(), live_cpp.read_bytes())
            self.assertFalse(
                (Path(state["scratch_project"]) / "Intermediate").exists()
            )
            self.assertFalse((Path(state["scratch_project"]) / "Binaries").exists())
            self.assertFalse(
                (Path(state["scratch_project"]) / runner.FINAL_MAP_REL).exists()
            )

    def test_engine_enumeration_selects_one_observed_path_and_rejects_ambiguity(self):
        full_path = (
            "Project.Functional Tests.__CraftBenchAdmission."
            + runner.TASK_ID
            + ".L_CatalogReadersAdmission.CatalogReadersAdmissionFunctionalTest"
        )
        log = (
            "[0]LogAutomationCommandLine: Display: Found 4 Automation Tests\n"
            f"[0]LogAutomationCommandLine: Display: \t'{full_path}'\n"
            "[0]LogAutomationCommandLine: Display: \t'Project.Unit.Other'\n"
        )
        evidence = runner.discover_exact_filter(log)
        self.assertEqual(evidence["full_test_path"], full_path)
        self.assertEqual(
            evidence["display_name"],
            "CatalogReadersAdmissionFunctionalTest",
        )
        self.assertIn("exact task/map prefix", evidence["selection"])

        class_derived_path = full_path.replace(
            "CatalogReadersAdmissionFunctionalTest",
            "CatalogReadersFunctionalTest",
        )
        with self.assertRaisesRegex(RuntimeError, "display name mismatch"):
            runner.discover_exact_filter(
                "LogAutomationCommandLine: Display: "
                f"\t'{class_derived_path}'\n"
            )

        second = full_path.replace(
            "CatalogReadersAdmissionFunctionalTest",
            "CatalogReadersAdmissionFunctionalTestDuplicate",
        )
        with self.assertRaisesRegex(RuntimeError, "exactly one"):
            runner.discover_exact_filter(
                log
                + f"[0]LogAutomationCommandLine: Display: \t'{second}'\n"
            )

    def test_l2_worker_reuses_shared_contract_with_nullrhi_count_and_timeout(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            request_path = root / "request.json"
            result_path = root / "result.json"
            full_path = "Project.Functional Tests.Observed.Exact"
            state_path = root / "state.json"
            enumeration_path = root / "enumeration.json"
            runner.write_json(
                state_path,
                {
                    "task_id": runner.TASK_ID,
                    "scratch_uproject": str(root / "Scratch.uproject"),
                },
            )
            runner.write_json(
                enumeration_path, {"full_test_path": full_path}
            )
            request = {
                "ue_root": str(root / "UE"),
                "project": str(root / "Scratch.uproject"),
                "full_test_path": full_path,
                "l2_log": str(root / "l2.log"),
                "report_dir": str(root / "report"),
                "result_json": str(result_path),
                "state_json": str(state_path),
                "enumeration_json": str(enumeration_path),
            }
            runner.write_json(request_path, request)
            captured = {}

            def fake_run_l2(**kwargs):
                captured.update(kwargs)
                return runner.L2Result(
                    status="pass",
                    log_path=Path(kwargs["log_path"]),
                    duration_seconds=1.0,
                    tests_run=1,
                    tests_passed=1,
                    tests_failed=0,
                    tests_skipped=0,
                    notes=[],
                    exit_code=0,
                    report_path=Path(kwargs["report_dir"]) / "index.json",
                    result_source="json",
                )

            serialized = runner.l2_worker(
                request_path, run_l2_fn=fake_run_l2
            )
            self.assertTrue(captured["use_nullrhi"])
            self.assertEqual(captured["expected_test_count"], 1)
            self.assertEqual(
                captured["timeout_seconds"], runner.INNER_L2_TIMEOUT_SECONDS
            )
            self.assertEqual(captured["map_package_path"], runner.MAP_PACKAGE)
            self.assertEqual(captured["test_filter"], full_path)
            self.assertEqual(serialized["status"], "pass")
            self.assertTrue(result_path.is_file())

    def test_test_audit_requires_report_identity_and_exact_primary_telemetry(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            full_path = (
                "Project.Functional Tests.__CraftBenchAdmission."
                + runner.TASK_ID
                + ".L_CatalogReadersAdmission.CatalogReadersAdmissionFunctionalTest"
            )
            report = {
                "succeeded": 1,
                "succeededWithWarnings": 0,
                "failed": 0,
                "notRun": 0,
                "inProcess": 0,
                "tests": [
                    {
                        "testDisplayName": runner.DISPLAY_NAME,
                        "fullTestPath": full_path,
                        "state": "Success",
                    }
                ],
            }
            report_path = root / "report" / "index.json"
            runner.write_json(report_path, report)
            payloads = (
                list(runner.EXPECTED_CHECKPOINTS)
                + [runner.EXPECTED_SUMMARY]
            )
            log_path = root / "l2.log"
            log_path.write_text(
                "".join(
                    f"[0]LogTemp: Display: {payload}\n" for payload in payloads
                )
                # AutomationController replay is deliberately ignored.
                + "[0]LogAutomationController: LogTemp: [CB-CP] idx=0 t=0.20 [log]\n",
                encoding="utf-8",
            )
            result = {
                "status": "pass",
                "tests_run": 1,
                "tests_passed": 1,
                "tests_failed": 0,
                "tests_skipped": 0,
                "result_source": "json",
                "report_path": str(report_path),
                "log_path": str(log_path),
            }
            evidence = runner.audit_test_outputs(
                result=result, full_path=full_path
            )
            self.assertEqual(evidence["executed_count"], 1)
            self.assertEqual(len(evidence["named_gates"]), 3)

            log_path.write_text(
                log_path.read_text(encoding="utf-8")
                + "[0]LogTemp: Display: CR-1 exact_actor_scoped_metadata_reports\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "named failure"):
                runner.audit_test_outputs(result=result, full_path=full_path)


if __name__ == "__main__":
    unittest.main()
