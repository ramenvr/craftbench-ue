"""Offline contract tests for the dedicated replicated-door L2 adapter."""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path
import unittest


VERIFY = Path(__file__).resolve().parent.parent
if str(VERIFY) not in sys.path:
    sys.path.insert(0, str(VERIFY))

from layers.l2_replicated_door import GATES, classify_aggregate  # noqa: E402


RUNNER = (
    VERIFY.parents[1] / "tasks" / "craftbench-public"
    / "t3-every-player-sees-the-same-door-state" / "authoring"
    / "run_network.py"
)


def load_runner():
    spec = importlib.util.spec_from_file_location("replicated_door_runner", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def passing() -> dict:
    return {
        "status": "pass", "failure_kind": "none", "tests_run": 1,
        "tests_passed": 1, "tests_failed": 0, "inputs_unchanged": True,
        "late_launched": True, "guid_values": ["123"],
        "gate_counts": {gate: 1 for gate in GATES}, "problems": [],
    }


class ReplicatedDoorAdapterTests(unittest.TestCase):
    def test_exact_contract_passes(self):
        self.assertEqual("pass", classify_aggregate(passing(), 0))

    def test_named_behavior_failure_stays_graded(self):
        value = passing()
        value.update(status="fail", failure_kind="behavior",
                     tests_passed=0, tests_failed=1)
        value["gate_counts"][GATES[1]] = 0
        self.assertEqual("fail", classify_aggregate(value, 1))

    def test_harness_failure_is_error(self):
        value = passing()
        value.update(status="fail", failure_kind="harness",
                     tests_run=0, tests_passed=0, problems=["peer missing"])
        self.assertEqual("error", classify_aggregate(value, 1))

    def test_multiple_netguids_invalidates_nominal_pass(self):
        value = passing()
        value["guid_values"] = ["123", "456"]
        self.assertEqual("error", classify_aggregate(value, 0))

    def test_missing_late_client_invalidates_nominal_pass(self):
        value = passing()
        value["late_launched"] = False
        self.assertEqual("error", classify_aggregate(value, 0))

    def test_mutated_input_invalidates_behavior_verdict(self):
        value = passing()
        value.update(status="fail", failure_kind="behavior",
                     tests_passed=0, tests_failed=1,
                     inputs_unchanged=False)
        self.assertEqual("error", classify_aggregate(value, 1))

    def test_input_hashes_follow_passed_project(self):
        runner = load_runner()
        project = Path("C:/scratch-door/ThirdPerson.uproject")
        final_asset, final_map = runner.project_inputs(project, False)
        admission_asset, admission_map = runner.project_inputs(project, True)
        self.assertEqual(
            project.parent / "Content" / "Tasks" / runner.TASK_ID
            / "BP_ReplicatedDoorState.uasset", final_asset)
        self.assertEqual(
            project.parent / "Content" / "Maps" / runner.TASK_ID
            / "L_ReplicatedDoorState.umap", final_map)
        self.assertIn("__CraftBenchAdmission", admission_asset.parts)
        self.assertIn("__CraftBenchAdmission", admission_map.parts)


if __name__ == "__main__":
    unittest.main()
