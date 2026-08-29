---
id: t1-data-asset-drives-speed
substrate: CraftBenchTemplate
set: cpp
tier: T1
capability_bucket: Content, Data, Assets
category: gameplay
layers: [L1, L2]
fixtures: ["L_ProfiledMover :: AProfiledMoverFunctionalTest"]
---

# t1-data-asset-drives-speed

An actor whose forward speed is configured by a standalone designer-authored data
asset, read and applied at runtime — the data-asset read-and-apply core. This is
an **asset-bearing** task: the substrate ships a Data Asset the agent must read.
Adapted from the the internal design corpus v2 corpus (source: Epic's Data Assets documentation);
reshaped to a substrate-provided asset graded by L1/L2.

## Primary concept

- `ps-data-assets` — Data Assets
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/data-assets-in-unreal-engine)

The load-bearing behavior is reading a numeric field from a standalone content
asset and applying it at runtime — retuning the asset (without touching code)
changes the applied behavior.

## Prompt given to the agent

> The project contains an actor placed in the level and a standalone piece of
> designer-authored content that holds a single configurable number — a cruise
> speed. That content is already assigned to the actor. When gameplay begins, the
> actor must read the configured speed from that content and move forward
> continuously at that speed, covering equal distance in equal time. The speed
> must come from the content — reading it must be what drives the motion, never a
> number written in code — so retuning the content changes how fast the actor
> moves. It requires no player input. Solve in C++ on the existing class — do not
> edit the content asset and do not edit any test file.

## Workspace state pre-task

Files/assets that **exist**:

- `Source/CraftBenchTemplate/Tasks/t1-data-asset-drives-speed/ProfiledMoverActor.h`
  / `.cpp` — `class CRAFTBENCHTEMPLATE_API AProfiledMoverActor : public AActor`,
  tagged `ProfiledMoverRoot`, with a movable cube root and an assigned
  `UMovementProfileAsset* Profile`. **It has no motion.**
- `Source/CraftBenchTemplate/Tasks/t1-data-asset-drives-speed/MovementProfileAsset.h`
  / `.cpp` — the data-asset class `UMovementProfileAsset : UPrimaryDataAsset` with
  a `float CruiseSpeed` field (read it; do not edit this class).
- `Content/Data/DA_MovementProfile` — a `UMovementProfileAsset` instance assigned
  to the placed actor's `Profile`. Read-only.
- `Content/Maps/t1-data-asset-drives-speed/L_ProfiledMover.umap` — the placed
  actor plus a test harness actor, with open space ahead.

Files/assets that **do not exist**: the read-and-move logic. Add it in C++ on the
existing class.

## Verifier specification

The test runs in PIE from
`Maps/t1-data-asset-drives-speed/L_ProfiledMover.umap` at a fixed deterministic
step (`-deterministic -FPS=60`), so the motion is framerate-independent. The
substrate `DA_MovementProfile` (with its undisclosed `CruiseSpeed`) and the map
are committed binaries (the scaffolder scripts were retired 2026-07; the
committed `.umap`/`.uasset` are the only source).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for both the Editor and Game targets
assert: no new shadowed-variable / deprecated-declarations warnings in
        Source/CraftBenchTemplate/Tasks/t1-data-asset-drives-speed/ProfiledMoverActor.{h,cpp}
```

### L2 — AFunctionalTest behavioral trace

```text
AProfiledMoverFunctionalTest::PrepareTest():
    Found = GetAllActorsWithTag(World, "ProfiledMoverRoot")
    AssertEqual_Int(Found.Num(), 1, "Exactly one ProfiledMoverRoot actor")
    StartLocation = actor->GetActorLocation()
    SetCheckpointSchedule({ 0.5, 1.0, 1.5 })

OnCheckpoint records P[idx] = actor->GetActorLocation():
    idx 0: AssertGreater(Dist(P[0], StartLocation), 20)   // moving
    idx 2: measured = (Dist(P1,P0)+Dist(P2,P1))/2 / 0.5
           AssertWithinPct(measured, DA_MovementProfile.CruiseSpeed, 12%)
    FinishTest(Succeeded)
```

**Pass criteria**: both L1 and L2 green. **Robust identity**: the actor is found
by the `ProfiledMoverRoot` tag.

## Reference solution metadata

- LOC range: ~12-18 LOC (a `UProjectileMovementComponent` in the constructor;
  in `BeginPlay`, read `Profile->CruiseSpeed` and set the component's velocity).
- Files touched: 2 (the pre-existing header + cpp).
- Senior-dev minutes: 20-40.

## Anti-gaming notes

1. **Hardcoded speed.** *Failure mode*: agent moves at a number written in code
   instead of the profile's value. *Defense*: `CruiseSpeed` is never disclosed in
   the prompt; the measured rate must match it within ±12% (on a non-round value),
   which a guess is unlikely to hit.
2. **No motion.** *Failure mode*: agent reads the profile but never moves, or does
   nothing; L1 passes. *Defense*: checkpoint 0 asserts the actor left its start
   and the rate check requires a non-zero measured speed.
3. **One-shot teleport.** *Failure mode*: agent snaps the actor once. *Defense*:
   the rate is measured across two later intervals; a snap-then-static reads a
   near-zero rate and fails.
4. **Ignores the asset.** *Failure mode*: agent moves at some constant unrelated
   to the profile. *Defense*: the expected rate is keyed to the profile's authored
   `CruiseSpeed`; only reading `Profile->CruiseSpeed` produces the matching rate.
5. **Test disabling.** *Failure mode*: agent edits the fixture. *Defense*:
   `CraftBenchTests` is outside the writable workspace and the runner
   materializes it from git HEAD (an on-disk edit never reaches the grade);
   committed changes are review-gated on commit.
