---
id: t0-sanity-log-on-beginplay
substrate: CraftBenchTemplate
set: cpp
tier: T0
capability_bucket: Gameplay Programming
category: other
layers: [L1, L2]
fixtures: ["L_SanityTask :: ASanityFunctionalTest"]
---

# t0-sanity-log-on-beginplay

Smoke task — the simplest viable CraftBench task. Its job is not to test
the agent under evaluation; its job is to test that the
**verification framework itself** (L1 build + L2 AFunctionalTest in PIE
with log capture) wires together end-to-end. If this task ever fails to
distinguish a correct submission from an empty submission, the verifier
is broken before any real task can be trusted.

## Primary concept

- `ps-actors` — Actors
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/actors-in-unreal-engine)

`AActor` lifecycle (`BeginPlay`) is the load-bearing concept. Every
later task assumes the runner can spawn a level, advance ticks, and
observe an actor's runtime behavior — this task probes exactly that
substrate.

## Prompt given to the agent

> The project contains an actor placed in the level via the Outliner.
> When gameplay begins, this actor must emit the exact log line
> `CRAFTBENCH_SANITY_OK` via `UE_LOG` on the `LogTemp` category at
> `Display` verbosity (or louder), exactly once, on the first frame of
> play. No other behavior is required and the actor should otherwise
> remain in the world. Solve in C++ on the existing class — do not
> create a Blueprint subclass, do not edit the level, and do not edit
> any test file.

## Workspace state pre-task

Files that **exist** under `Source/CraftBenchTemplate/`:

- `CraftBenchTemplate.Build.cs` — `PublicDependencyModuleNames`
  already includes `Core`, `CoreUObject`, `Engine`, `InputCore`,
  `FunctionalTesting`. No edit needed.
- `Tasks/t0-sanity-log-on-beginplay/SanityActor.h` / `.cpp` — declares
  and defines `class CRAFTBENCHTEMPLATE_API ASanityActor : public AActor`.
  Constructor sets `PrimaryActorTick.bCanEverTick = false;` and adds
  `Tags.Add(FName("SanityRoot"))`. **No `BeginPlay` override is
  declared.**
- `Maps/t0-sanity-log-on-beginplay/L_SanityTask.umap` — persistent level with one placed
  `ASanityActor` (tagged `SanityRoot`) and one placed
  `ASanityFunctionalTest` (UE requires the `A` prefix on `AActor`
  subclasses; `AFunctionalTest` inherits from `AActor`). Set as
  Editor Startup Map.

Files that **do not exist**:

- No `BeginPlay` override, no Blueprint subclass of `ASanityActor`, no
  level edits. Solve in C++ on the existing class.
- No test source in the agent's writable path. `ASanityFunctionalTest`
  lives in a separate `CraftBenchTests` module the agent cannot read
  or modify.

## Verifier specification

The test runs in PIE from `Maps/t0-sanity-log-on-beginplay/L_SanityTask.umap`. The engine ticks
the world at a fixed deterministic step (`-deterministic -FPS=60`) so
the assertion does not depend on wall-clock pacing.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for "CraftBenchTemplateEditor Win64
        Development" target
assert: no new "shadowed-variable" or "deprecated-declarations"
        warnings in Source/CraftBenchTemplate/Tasks/t0-sanity-log-on-beginplay/SanityActor.{h,cpp}
        (warning diff is pinned to agent-authored files only;
        substrate-baseline warnings are not asserted on)
```

### L2 — AFunctionalTest behavioral trace

```text
ASanityFunctionalTest::PrepareTest():
    // Identify the candidate by project tag, never by C++ class name —
    // the agent may legitimately subclass ASanityActor.
    TArray<AActor*> Found
    UGameplayStatics::GetAllActorsWithTag(World, FName("SanityRoot"), Found)
    AssertEqual_Int(Found.Num(), 1, "Exactly one SanityRoot actor in test level")

    // Bind the log listener AFTER world spawn but BEFORE the first
    // post-BeginPlay tick, so constructor-time logs (CDO construction)
    // are NOT captured and only the BeginPlay-window emission counts.
    BindLogListener(
        category = "LogTemp",
        verbosity = Display,
        capture_substring = "CRAFTBENCH_SANITY_OK")
    SetFixedStepping(dt = 1.0 / 60.0)

ASanityFunctionalTest::StartTest():
    // The fixture runs in PIE; BeginPlay auto-fires on the placed
    // SanityRoot actor before PrepareTest. The log listener is installed
    // in PrepareTest before that first BeginPlay-window tick — this is the
    // "BeginPlay window" the assertion below counts against. Future task
    // fixtures that probe BeginPlay-window behavior must follow this
    // substrate convention.
    AdvanceWorldBy(1.0 / 60.0)
    AssertEqual_Int(
        CapturedLogCount, 1,
        "Sanity log line emitted exactly once in the BeginPlay window")
    FinishTest(EFunctionalTestResult::Succeeded, "")
```

**Pass criteria**: both L1 and L2 green. **Robust identity**: lookup
by the `SanityRoot` tag, never by class name — subclassing
`ASanityActor` does not penalize the agent.

## Reference solution metadata

- LOC range: 3-8 LOC (BeginPlay override declaration in the header +
  the override definition with one `UE_LOG` call and a
  `Super::BeginPlay()` invocation in the .cpp)
- Files touched: 2 (1 header, 1 cpp; both pre-existing — no new files)
- Senior-dev hours: under 0.25 (5-15 minutes, including reading the
  prompt and building once)

## Anti-gaming notes

1. **Empty BeginPlay satisfies build.** *Failure mode*: agent declares
   the override but emits no log line; L1 passes. *Defense*: L2
   asserts `CapturedLogCount == 1`; an empty body fails L2.
2. **Wrong log category.** *Failure mode*: agent logs to
   `LogActor` or a custom category to "hide" the literal. *Defense*:
   L2's log listener is bound to `LogTemp` with `Display` verbosity;
   logs to other categories are not counted.
3. **Constructor-time log.** *Failure mode*: agent puts the
   `UE_LOG` in the constructor to satisfy the substring without
   touching BeginPlay. *Defense*: `PrepareTest` binds the listener
   AFTER world spawn but BEFORE the first post-BeginPlay tick;
   CDO-construction logs fire earlier and are not captured.
4. **Multiple emits.** *Failure mode*: agent puts the log line in a
   tick or timer that fires repeatedly, satisfying a `>= 1` check.
   *Defense*: L2 asserts `== 1`, not `>= 1`; per-tick emission would
   produce `>= 2` and fail.
5. **Test disabling.** *Failure mode*: agent edits
   `ASanityFunctionalTest` to lower the assertion bar. *Defense*:
   `CraftBenchTests` lives outside the agent's writable workspace, is
   built by a separate CI target, and is verified by hash; any tamper
   appears as a diff outside permitted edit paths and is rejected
   pre-grade.
