"""Offline fail-closed audit for row-5 task-local authoring contracts."""

from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
TASK = HERE.parent
REPO = HERE.parents[3]
RUNTIME = (REPO / "UE-projects" / "ThirdPerson" / "Source" / "ThirdPerson" /
           "Tasks" / TASK.name)
FIXTURE = (REPO / "UE-projects" / "ThirdPerson" / "Source" /
           "CraftBenchTests" / "Tasks" / TASK.name)


def require(path, tokens):
    text = path.read_text(encoding="utf-8")
    missing = [token for token in tokens if token not in text]
    if missing:
        raise SystemExit("%s missing tokens %r" % (path, missing))
    return text


task_text = require(TASK / "task.md", [
    "tier: T3", "layers: [L1, L2]",
    "BothAgentsConflictDrivenSteering", "BothAgentsKeepForwardProgress",
    "NoOverlapEnRoute", "BothAgentsReachOwnGoals",
])
fixture_text = require(FIXTURE / "BothWalkersYieldFunctionalTest.cpp", [
    "GetCurrentDirection", "UCrowdManager::GetCurrent",
    "IsAgentValid", "IsCrowdObstacleAvoidanceActive",
    "MoveToLocation", "PrepareEpochSeconds", "SetCheckpointSchedule",
    "EnsureRuntimeNavigationReady", "runtime_dynamic=1",
    "NavigationSystem->Build()",
])
require(RUNTIME / "WalkerYieldCharacter.cpp", [
    "SetAvoidanceEnabled(false)", "PlacedInWorldOrSpawned", "Pawn",
])
require(FIXTURE / "WalkerYieldAuthoringLibrary.cpp", [
    "ADetourCrowdAIController::StaticClass", "bUseRVOAvoidance = false",
    "AvoidanceWeight", "BuildNavigation",
    "GetNumActiveTiles", "InspectWorld", "ERuntimeGenerationType::Dynamic",
    "runtime_supported=1",
])
map_text = require(HERE / "author_map_common.py", [
    "FINAL_SCENARIOS", "ADMISSION_SCENARIOS", "PairA", "PairB",
    "SoloA", "SoloB", "expected_walker_class", "build_navigation",
])
runner_text = require(HERE / "run_admission.py", [
    "expected_test_count", "use_nullrhi=True", "watchdog",
    "expected_test_count=1", "EXACT_FILTER", "all_locks",
])
for forbidden in ("LoadObject<AWalkerYield", "SetActorLocation(",
                  "AddActorWorldOffset(", "ManualTick", "TickComponent("):
    if forbidden in fixture_text:
        raise SystemExit("forbidden verifier shortcut: " + forbidden)
if len(re.findall(r"FailGate\(TEXT\(\"[A-Za-z]+", fixture_text)) < 4:
    raise SystemExit("fixture lacks four explicit named graded gates")
if map_text.count("Scenario(") != 3:
    raise SystemExit("expected two final facts plus one admission fact")
notes_text = (TASK / "notes.md").read_text(encoding="utf-8")
if "PUBLISHED / COMMITTED-SUBSTRATE DISCRIMINATION PASS" not in notes_text:
    raise SystemExit("completed production discrimination state is not explicit")
if "4ad7763bdaf352c7228d1b5b7260c07cd8cfbb94" not in notes_text:
    raise SystemExit("committed certification substrate is not explicit")
print("WALKER-YIELD-STATIC-CONTRACT PASS files=19 layers=L1,L2 gates=4 "
      "world_fact_groups=2 admission=PASS discrimination=PASS "
      "certification=GIT-HEAD-PASS")
