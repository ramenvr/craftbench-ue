---
id: t1-overlap-logs-once
substrate: CraftBenchTemplate
set: cpp
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_OverlapLog :: AOverlapLogFunctionalTest"]
---

# t1-overlap-logs-once

An overlap-triggered log emission: an actor with a collision volume that stays
silent until another actor enters it, then emits a single marker line — exactly
once per overlap, never on startup. Drawn from an earlier internal task list (not shipped)
("Dynamic delegate usage"); the visual debug-sphere from the original is dropped
as it is a non-gating (advisory) render concern.

## Primary concept

- `ps-collision-overlap` — Collision overlap events
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine)

Binding and responding to a component begin-overlap event is the load-bearing
concept: the actor must react to a runtime overlap, not to its own lifecycle.

## Prompt given to the agent

> The project contains an actor placed in the level with a collision volume.
> When another actor first enters (overlaps) that volume, the actor must emit
> the exact log line `CRAFTBENCH_OVERLAP_OK` to the engine log on the `LogTemp`
> category at `Display` verbosity (or louder), once for that overlap. Before
> anything overlaps it, the actor must not emit that line at all. Solve in C++
> on the existing class — do not create a Blueprint subclass, do not edit the
> level, and do not edit any test file.

## Workspace state pre-task

Files that **exist** under `Source/CraftBenchTemplate/`:

- `CraftBenchTemplate.Build.cs` — already depends on `Core`, `CoreUObject`,
  `Engine`, `InputCore`, `FunctionalTesting`. No edit needed.
- `Tasks/t1-overlap-logs-once/OverlapLogActor.h` / `.cpp` — declares and defines
  `class CRAFTBENCHTEMPLATE_API AOverlapLogActor : public AActor`. The
  constructor disables tick, creates a query-only `USphereComponent`
  ("CollisionSphere") as the root with overlap events enabled and Overlap
  responses to all channels, and adds the `OverlapLogRoot` tag. **No overlap
  handling or logging is provided.**
- `Content/Maps/t1-overlap-logs-once/L_OverlapLog.umap` — persistent level with
  one placed `AOverlapLogActor` (tagged `OverlapLogRoot`) and one placed test
  harness actor.

Files that **do not exist**:

- No begin-overlap binding, no overlap handler, no logging, no Blueprint subclass,
  no level edits. Solve in C++ on the existing class.
- No test source in the agent's writable path. The test harness lives in a
  separate `CraftBenchTests` module the agent cannot read or modify.

## Verifier specification

The test runs in PIE from
`Maps/t1-overlap-logs-once/L_OverlapLog.umap` at a fixed deterministic step
(`-deterministic -FPS=60`).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for both the Editor and Game targets
assert: no new shadowed-variable / deprecated-declarations warnings in
        Source/CraftBenchTemplate/Tasks/t1-overlap-logs-once/OverlapLogActor.{h,cpp}
        (warning diff pinned to agent-authored files only)
```

### L2 — AFunctionalTest behavioral trace

```text
AOverlapLogFunctionalTest::PrepareTest():
    // Identity by project tag, never by C++ class name — the agent may
    // legitimately subclass AOverlapLogActor.
    Found = GetAllActorsWithTag(World, "OverlapLogRoot")
    AssertEqual_Int(Found.Num(), 1, "Exactly one OverlapLogRoot actor")
    // GLog listener installed in OnWorldInitializedActors (before BeginPlay),
    // filtered to LogTemp / Display, substring "CRAFTBENCH_OVERLAP_OK".
    SetCheckpointSchedule({ 0.5, 2.0 })

checkpoint 0 (t≈0.5s, after BeginPlay so any overlap binding is in place):
    AssertEqual_Int(MarkerCount, 0, "silent before any overlap")
    // Spawn a probe with an overlap sphere on the host and force an overlap
    // update to fire the host's begin-overlap event (headless stand-in for
    // another actor walking in).
    InduceOverlap()

checkpoint 1 (t≈2.0s):
    AssertEqual_Int(MarkerCount, 1, "logged exactly once on the overlap")
    FinishTest(Succeeded)
```

**Pass criteria**: both L1 and L2 green. **Robust identity**: lookup by the
`OverlapLogRoot` tag, never by class name.

## Reference solution metadata

- LOC range: ~8-14 LOC (a `BeginPlay` override that binds
  `CollisionSphere->OnComponentBeginOverlap` + a `UFUNCTION` handler with one
  `UE_LOG`).
- Files touched: 2 (the pre-existing header + cpp; no new files).
- Senior-dev minutes: under 15.

## Anti-gaming notes

1. **Log on BeginPlay instead of on overlap.** *Failure mode*: agent emits the
   marker unconditionally in `BeginPlay` to satisfy a `>= 1` check. *Defense*:
   checkpoint 0 runs after BeginPlay and asserts `MarkerCount == 0` before any
   overlap is induced; a BeginPlay-time log fails there.
2. **Wrong log category/verbosity.** *Failure mode*: agent logs to a custom
   category or a quieter verbosity to hide the literal. *Defense*: the listener
   is filtered to `LogTemp` at `Display`-or-louder; other channels are not
   counted.
3. **Multiple emits.** *Failure mode*: agent logs from a per-tick or per-frame
   path so the marker fires repeatedly. *Defense*: checkpoint 1 asserts
   `== 1`, not `>= 1`; repeated emission produces `>= 2` and fails.
4. **Empty override.** *Failure mode*: agent overrides `BeginPlay` but never
   binds the overlap; L1 passes. *Defense*: checkpoint 1 asserts `== 1`; with no
   binding the induced overlap produces 0 and fails.
5. **Test disabling.** *Failure mode*: agent edits `AOverlapLogFunctionalTest`
   to lower the bar. *Defense*: `CraftBenchTests` is outside the writable
   workspace and the runner materializes it from git HEAD (an on-disk edit
   never reaches the grade); committed changes are review-gated on commit.
