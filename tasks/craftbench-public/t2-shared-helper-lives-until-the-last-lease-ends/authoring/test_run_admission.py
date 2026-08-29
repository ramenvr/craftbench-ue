"""Offline contract tests; never launches Unreal or UBT."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "shared_helper_run_admission", HERE / "run_admission.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class SharedHelperAdmissionContractTests(unittest.TestCase):
    def test_write_json_serializes_path_values(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "path-value.json"
            runner.write_json(output, {"path": Path("C:/example")})
            observed = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(observed, {"path": str(Path("C:/example"))})

    def test_exact_filter_and_map(self):
        self.assertEqual(
            runner.TEST_FILTER,
            "Project.Functional Tests.__CraftBenchAdmission."
            "t2-shared-helper-lives-until-the-last-lease-ends."
            "L_SharedHelperLeaseAdmission."
            "SharedHelperLeaseAdmissionFunctionalTest")
        self.assertEqual(
            runner.MAP_PACKAGE,
            "/Game/__CraftBenchAdmission/"
            "t2-shared-helper-lives-until-the-last-lease-ends/"
            "L_SharedHelperLeaseAdmission")

    def test_cli_requires_phase_and_fresh_output_argument(self):
        args = runner.parse_args([
            "--phase", "prepare", "--output-root", "C:/cbtmp/example"])
        self.assertEqual(args.phase, "prepare")
        self.assertEqual(args.output_root, Path("C:/cbtmp/example"))
        with self.assertRaises(SystemExit):
            runner.parse_args(["--output-root", "C:/cbtmp/example"])

    def test_build_commands_pin_no_uba_and_cap_two(self):
        with tempfile.TemporaryDirectory() as temp:
            ue = Path(temp) / "UE"
            build = ue / "Engine/Build/BatchFiles/Build.bat"
            build.parent.mkdir(parents=True)
            build.write_text("@echo off\n", encoding="ascii")
            commands = runner.build_commands(ue, Path(temp) / "P.uproject")
        self.assertEqual(len(commands), 2)
        self.assertEqual([command[5] for command in commands],
                         ["ThirdPersonEditor", "ThirdPerson"])
        for command in commands:
            self.assertIn("-WaitMutex", command)
            self.assertIn("-NoHotReloadFromIDE", command)
            self.assertIn("-NoUBA", command)
            self.assertIn("-MaxParallelActions=2", command)

    def test_overlay_is_cpp_only_keeps_header_and_never_touches_live(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            live = root / "live"
            reference = root / "reference"
            scratch = root / "scratch"
            for directory in (live, reference, scratch):
                directory.mkdir()
            for name in runner.LIVE_SOURCE_NAMES:
                (live / name).write_text("empty " + name, encoding="utf-8")
                (scratch / name).write_text("empty " + name, encoding="utf-8")
            for name in runner.REFERENCE_SOURCE_NAMES:
                (reference / name).write_text("reference " + name,
                                              encoding="utf-8")
            live_before = {name: runner.sha256_file(live / name)
                           for name in runner.LIVE_SOURCE_NAMES}
            scratch_header_before = runner.sha256_file(
                scratch / "SharedHelperLeaseSubsystem.h")
            hashes = runner.overlay_reference(reference, scratch)
            self.assertEqual(set(hashes), set(runner.REFERENCE_SOURCE_NAMES))
            self.assertEqual(live_before, {
                name: runner.sha256_file(live / name)
                for name in runner.LIVE_SOURCE_NAMES})
            self.assertEqual(hashes, {
                name: runner.sha256_file(reference / name)
                for name in runner.REFERENCE_SOURCE_NAMES})
            self.assertEqual(
                scratch_header_before,
                runner.sha256_file(scratch / "SharedHelperLeaseSubsystem.h"))

    def test_overlay_refuses_extra_reference_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reference = root / "reference"
            scratch = root / "scratch"
            reference.mkdir()
            scratch.mkdir()
            for name in runner.LIVE_SOURCE_NAMES:
                (scratch / name).write_text(name, encoding="utf-8")
            for name in runner.REFERENCE_SOURCE_NAMES:
                (reference / name).write_text(name, encoding="utf-8")
            (reference / "Extra.cpp").write_text("unexpected", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "exact source inventory"):
                runner.overlay_reference(reference, scratch)


if __name__ == "__main__":
    unittest.main()
