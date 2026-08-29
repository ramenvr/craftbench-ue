"""Offline contract tests for the menu-input admission runner."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


RUNNER = Path(__file__).resolve().parents[1] / "run_admission.py"
SPEC = importlib.util.spec_from_file_location("menu_input_run_admission", RUNNER)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load run_admission.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AuditTests(unittest.TestCase):
    def make_output(self, root: Path, *, display: str | None = None,
                    success: str | None = None) -> Path:
        output = root / "out"
        (output / "report").mkdir(parents=True)
        result = {
            "status": "pass",
            "tests_run": 1,
            "tests_passed": 1,
            "tests_failed": 0,
            "result_source": "json",
        }
        (output / "l2_result.json").write_text(
            json.dumps(result), encoding="utf-8")
        index = {
            "succeeded": 1,
            "failed": 0,
            "notRun": 0,
            "tests": [{
                "fullTestPath": MODULE.EXACT_FILTER,
                "testDisplayName": display or MODULE.EXPECTED_DISPLAY,
                "state": "Success",
            }],
        }
        (output / "report" / "index.json").write_text(
            "\ufeff" + json.dumps(index), encoding="utf-8")
        (output / "l2.log").write_text(
            (success or MODULE.EXPECTED_SUCCESS) + "\n", encoding="utf-8")
        return output

    def test_exact_report_and_unchanged_snapshot_pass(self) -> None:
        snapshot = {"map": {"a": "b"}, "reference_absent": True}
        with tempfile.TemporaryDirectory() as temp:
            output = self.make_output(Path(temp))
            with mock.patch.object(
                    MODULE, "protected_snapshot", return_value=snapshot):
                passed, summary = MODULE.audit(output, snapshot)
        self.assertTrue(passed)
        self.assertEqual([], summary["problems"])
        self.assertEqual(MODULE.EXACT_FILTER,
                         summary["automation_report"]["tests"][0]["fullTestPath"])

    def test_wrong_display_fails_closed(self) -> None:
        snapshot = {"map": {"a": "b"}, "reference_absent": True}
        with tempfile.TemporaryDirectory() as temp:
            output = self.make_output(Path(temp), display="NearMiss")
            with mock.patch.object(
                    MODULE, "protected_snapshot", return_value=snapshot):
                passed, summary = MODULE.audit(output, snapshot)
        self.assertFalse(passed)
        self.assertTrue(any("testDisplayName" in item
                            for item in summary["problems"]))

    def test_changed_snapshot_and_error_marker_fail_closed(self) -> None:
        before = {"map": {"a": "old"}, "reference_absent": True}
        after = {"map": {"a": "new"}, "reference_absent": True}
        with tempfile.TemporaryDirectory() as temp:
            output = self.make_output(
                Path(temp), success=MODULE.EXPECTED_SUCCESS + "\nGATE[Shortcut]")
            with mock.patch.object(
                    MODULE, "protected_snapshot", return_value=after):
                passed, summary = MODULE.audit(output, before)
        self.assertFalse(passed)
        self.assertTrue(any("snapshot changed" in item
                            for item in summary["problems"]))
        self.assertTrue(any("GATE[" in item for item in summary["problems"]))


class ConfigOverlayTests(unittest.TestCase):
    def test_both_fragments_apply_before_boot_and_restore_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "UE-projects" / "ThirdPerson" / "Config"
            task = root / "tasks" / "bp" / MODULE.TASK_ID
            fragments = task / "ue-config"
            config.mkdir(parents=True)
            fragments.mkdir(parents=True)
            spec = task / "task.md"
            spec.write_text("# fixture\n", encoding="utf-8")
            engine_original = b"[/Script/Engine.Engine]\nExisting=True\n"
            game_original = b"[/Script/Test.Settings]\nExisting=True\n"
            (config / "DefaultEngine.ini").write_bytes(engine_original)
            (config / "DefaultGame.ini").write_bytes(game_original)
            (fragments / "DefaultEngine.ini").write_text(
                "[/Script/Engine.Engine]\n"
                "GameViewportClientClassName=/Script/CommonUI.CommonGameViewportClient\n",
                encoding="utf-8")
            (fragments / "DefaultGame.ini").write_text(
                "[/Script/CommonInput.CommonInputSettings]\n"
                "bEnableEnhancedInputSupport=True\n", encoding="utf-8")

            with mock.patch.multiple(
                    MODULE, REPO=root, PROJECT_CONFIG=config, TASK_SPEC=spec):
                state = MODULE.apply_task_config_overlay()
                self.assertIn(
                    b"bEnableEnhancedInputSupport=True",
                    (config / "DefaultGame.ini").read_bytes())
                self.assertIn(
                    b"CommonGameViewportClient",
                    (config / "DefaultEngine.ini").read_bytes())
                facts = MODULE.revert_task_config_overlay(state)

            self.assertTrue(facts["restored_byte_identically"])
            self.assertEqual(
                engine_original, (config / "DefaultEngine.ini").read_bytes())
            self.assertEqual(
                game_original, (config / "DefaultGame.ini").read_bytes())


if __name__ == "__main__":
    unittest.main()
