"""Offline contract checks for the first-wave authoring package."""

import ast
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TASK = HERE.parent
RUNTIME = (REPO / "UE-projects" / "ThirdPerson" / "Source" / "ThirdPerson" /
           "Tasks" / TASK.name / "GuardPatrolChaseTypes.cpp")
FIXTURE = (REPO / "UE-projects" / "ThirdPerson" / "Source" /
           "CraftBenchTests" / "Tasks" / TASK.name /
           "GuardPatrolChaseFunctionalTest.cpp")
INTROSPECT = (REPO / "tools" / "verify-single" / "introspect" /
              "t3_guard_resumes_patrol_after_chase.py")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    python_files = sorted(HERE.glob("*.py")) + [INTROSPECT]
    for path in python_files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    fixture = FIXTURE.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    task = (TASK / "task.md").read_text(encoding="utf-8")
    introspect = INTROSPECT.read_text(encoding="utf-8")
    for gate in (
            "PrioritySelectorAndDecoratorsAuthored",
            "TrueKeyAbortsPatrolAndStartsChase",
            "ChaseClosesDistance",
            "ResetFalseExitsChase",
            "PatrolResumesAfterReset"):
        require(gate in task and gate in fixture, "missing runtime gate " + gate)
    require("SetCheckpointSchedule" in fixture, "world-clock schedule missing")
    require("World->Tick" not in fixture, "manual world tick forbidden")
    require("GetActiveNode" in fixture and "GetSelectedBlackboardKey" in fixture,
            "engine-owned active-node telemetry missing")
    require("PrimaryActorTick.bCanEverTick = false" in runtime,
            "runtime decisions must not use actor Tick")
    require(introspect.count('"PrioritySelectorAndDecoratorsAuthored"') == 1,
            "fixed introspector denominator changed")
    require("if type(result) is not str:" in introspect and
            'result.startswith("PASS ")' in introspect,
            "UE5.8 FString helper binding contract missing")
    require("expected_test_count=1" in (HERE / "run_admission.py").read_text(
        encoding="utf-8"), "runner exact-count lock missing")
    print("GUARD-STATIC-CONTRACTS-PASS python=%d gates=5 l2i=4" %
          len(python_files))


if __name__ == "__main__":
    main()
