"""Lightweight first-wave contract check; never starts Unreal or UBT."""

from pathlib import Path


TASK_ID = "t2-shared-helper-lives-until-the-last-lease-ends"
HERE = Path(__file__).resolve().parent
TASK = HERE.parent
REPO = TASK.parents[2]
RUNTIME = (REPO / "UE-projects/ThirdPerson/Source/ThirdPerson/Tasks" /
           TASK_ID)
TESTS = (REPO / "UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks" /
         TASK_ID)
REFERENCE = (TASK / "reference/Source/ThirdPerson/Tasks" / TASK_ID)


def require(condition, detail):
    if not condition:
        raise RuntimeError("SHARED-HELPER-STATIC ERROR " + detail)


def read(path):
    require(path.is_file(), "missing file " + str(path))
    return path.read_text(encoding="utf-8")


def main():
    required = (
        TASK / "task.md",
        TASK / "notes.md",
        TASK / "discrimination/MATRIX.md",
        HERE / "API_AUDIT.md",
        HERE / "AUTHORING_RUNBOOK.md",
        HERE / "REFERENCE_RECIPE.md",
        HERE / "author_admission_map.py",
        HERE / "admission_readback.py",
        HERE / "author_final_map.py",
        HERE / "final_map_readback.py",
        HERE / "run_admission.py",
        HERE / "test_run_admission.py",
        HERE / "t2_shared_helper_last_lease.py",
        RUNTIME / "SharedHelperLeaseSubsystem.h",
        RUNTIME / "SharedHelperLeaseSubsystem.cpp",
        TESTS / "SharedHelperLeaseFunctionalTest.h",
        TESTS / "SharedHelperLeaseFunctionalTest.cpp",
        TESTS / "SharedHelperLeaseAuthoringLibrary.h",
        TESTS / "SharedHelperLeaseAuthoringLibrary.cpp",
        REFERENCE / "SharedHelperLeaseSubsystem.cpp",
    )
    for path in required:
        require(path.is_file(), "missing artifact " + str(path))

    header = read(RUNTIME / "SharedHelperLeaseSubsystem.h")
    source = read(RUNTIME / "SharedHelperLeaseSubsystem.cpp")
    require("for task\n * " + TASK_ID in header,
            "literal supplied-scaffold marker absent")
    require("return nullptr;" in source and "return false;" in source,
            "live runtime is not the intentional empty behavior scaffold")
    for token in ("UGameInstanceSubsystem", "TObjectPtr<USharedLeaseHelper>",
                  "TWeakObjectPtr<UObject>", "CacheEntries", "ActiveLeases"):
        require(token in header, "runtime surface lacks " + token)

    fixture = read(TESTS / "SharedHelperLeaseFunctionalTest.cpp")
    for gate in (
        "SHL-1 SameKeySharesOneLiveHelper",
        "SHL-2 FirstReleaseDoesNotCollectSharedHelper",
        "SHL-3 ReplacementKeepsFreshIdentityAndPayload",
        "SHL-4 RetiredVersionCollectedAfterLastLease",
        "SHL-5 LastLeaseCollectsCurrentAndControl",
    ):
        require(gate in fixture, "missing named L2 gate " + gate)
    for token in ("FGuid::NewGuid", "ForceGarbageCollection(true)",
                  "USharedHelperGcWitness", "TWeakObjectPtr<USharedLeaseHelper>",
                  "GetTimeSeconds", "SetCheckpointSchedule"):
        require(token in fixture or token in read(
            TESTS / "SharedHelperLeaseFunctionalTest.h"),
            "fixture lacks " + token)
    for forbidden in ("CollectGarbage(", "World->Tick(", "AddToRoot("):
        require(forbidden not in fixture, "fixture contains forbidden " + forbidden)

    reference = read(REFERENCE / "SharedHelperLeaseSubsystem.cpp")
    for token in ("NewObject<USharedLeaseHelper>", "GetTransientPackage()",
                  "Entry.bRetired = true", "RemoveSingleSwap(Lease)",
                  "CacheEntries.RemoveAtSwap", "Lease->Helper = nullptr"):
        require(token in reference, "reference lacks " + token)
    for forbidden in ("AddToRoot(", "RemoveFromRoot(", "ConditionalBeginDestroy("):
        require(forbidden not in reference, "reference contains " + forbidden)

    introspector = read(HERE / "t2_shared_helper_last_lease.py")
    for check_id in (
        "GameInstanceLeaseSurfacePresent",
        "ReflectedLeaseAndCacheOwnership",
        "WeakOwnerAndNoRootPin",
    ):
        require(introspector.count('"' + check_id + '"') == 1,
                "fixed introspector ID count mismatch " + check_id)

    runner = read(HERE / "run_admission.py")
    for token in (
        "from layers.l2_pie import run_l2",
        "copy_substrate_from_live",
        "expected_test_count=1",
        "use_nullrhi=True",
        "OUTER_WATCHDOG_SECONDS = 720",
        "INNER_L2_TIMEOUT_SECONDS = 710",
        '"-WaitMutex"', '"-NoHotReloadFromIDE"', '"-NoUBA"',
        '"-MaxParallelActions=2"',
        "overlay_reference",
        "protected_snapshot",
    ):
        require(token in runner, "admission runner lacks " + token)
    require("REPO_ROOT / RUNTIME_REL" not in runner,
            "runner contains suspicious root/runtime overlay expression")
    reference_inventory = sorted(
        path.name for path in REFERENCE.iterdir() if path.is_file())
    require(reference_inventory == ["SharedHelperLeaseSubsystem.cpp"],
            "reference overlay must contain only the implementation source")

    print("SHARED-HELPER-STATIC PASS artifacts=%d gates=5 l2i=3 locks=4 overlay=1" %
          len(required))


main()
