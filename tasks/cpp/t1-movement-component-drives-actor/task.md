---
id: t1-movement-component-drives-actor
substrate: CraftBenchTemplate
set: cpp
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_Drift :: ADriftFunctionalTest"]
---

# t1-movement-component-drives-actor

An actor driven by a movement component so it glides continuously at a steady
velocity once gameplay begins, with no per-frame scripting and no player input.
Adapted from the the internal design corpus v2 task-design corpus (source: Epic's Movement
Components documentation).

## Primary concept

- `movement-components` — Movement Components
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/movement-components-in-unreal-engine)

The load-bearing behavior is component-driven self-motion: once play begins the
actor translates steadily in a fixed direction at a constant speed, covering
equal distance in equal time — the hallmark of a movement component updating the
transform every frame rather than a one-off teleport.

## Prompt given to the agent

> The project contains an object placed in the level. Make it drift smoothly and
> continuously in one horizontal direction as soon as gameplay begins. It must
> move at a steady speed — covering equal distance in equal time — without
> accelerating, stopping, or snapping. The object must not require any player
> input; it moves on its own from the moment play starts, and the motion must be
> the same regardless of frame rate. Solve in C++ on the existing class — do not
> edit the level and do not edit any test file.

## Workspace state pre-task

Files that **exist** under `Source/CraftBenchTemplate/`:

- `CraftBenchTemplate.Build.cs` — already depends on `Core`, `CoreUObject`,
  `Engine`, `InputCore`, `FunctionalTesting`. No edit needed.
- `Tasks/t1-movement-component-drives-actor/DriftActor.h` / `.cpp` — declares and
  defines `class CRAFTBENCHTEMPLATE_API ADriftActor : public AActor`. The
  constructor creates a movable cube mesh root (collision disabled) and adds the
  `DriftRoot` tag. **It has no self-motion, so it sits still.**
- `Content/Maps/t1-movement-component-drives-actor/L_Drift.umap` — the actor
  placed with open space ahead of it, plus a test harness actor.

Files that **do not exist**:

- No movement logic, no Blueprint subclass, no level edits. Solve in C++ on the
  existing class.
- No test source in the agent's writable path (the harness is in a separate,
  read-only `CraftBenchTests` module).

## Verifier specification

The test runs in PIE from
`Maps/t1-movement-component-drives-actor/L_Drift.umap` at a fixed deterministic
step (`-deterministic -FPS=60`), so the motion is framerate-independent by
construction.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for both the Editor and Game targets
assert: no new shadowed-variable / deprecated-declarations warnings in
        Source/CraftBenchTemplate/Tasks/t1-movement-component-drives-actor/DriftActor.{h,cpp}
```

### L2 — AFunctionalTest behavioral trace

```text
ADriftFunctionalTest::PrepareTest():
    Found = GetAllActorsWithTag(World, "DriftRoot")
    AssertEqual_Int(Found.Num(), 1, "Exactly one DriftRoot actor")
    StartLocation = actor->GetActorLocation()
    SetCheckpointSchedule({ 0.5, 1.0, 1.5, 2.0 })

OnCheckpoint records P[idx] = actor->GetActorLocation():
    idx 0: AssertGreater(Dist(P[0], StartLocation), 20)      // MovingFromStart
    idx 3: d01=Dist(P1,P0); d12=Dist(P2,P1); d23=Dist(P3,P2)
           AssertGreater(d23, 20)                             // ContinuesMoving
           AssertWithinPct(d12, d01, 30%)                     // ConstantVelocity
           AssertWithinPct(d23, d12, 30%)
    FinishTest(Succeeded)
```

**Pass criteria**: both L1 and L2 green. **Robust identity**: lookup by the
`DriftRoot` tag, never by class name.

## Reference solution metadata

- LOC range: ~8-12 LOC (attach a `UProjectileMovementComponent` with zero gravity
  and a constant velocity in the constructor).
- Files touched: 2 (the pre-existing header + cpp; no new files).
- Senior-dev minutes: 15-30.

## Anti-gaming notes

1. **One-shot teleport.** *Failure mode*: agent snaps the actor far away once in
   `BeginPlay`, then leaves it static. *Defense*: `ContinuesMoving` requires
   further advance in the final interval (a static actor's last step is ~0), and
   `ConstantVelocity` fails because the post-snap steps differ from the snap.
2. **Acceleration ramp.** *Failure mode*: agent applies gravity/impulse so speed
   increases over time. *Defense*: `ConstantVelocity` asserts equal displacement
   across equal intervals; an accelerating actor's later steps are larger.
3. **Move-then-stop.** *Failure mode*: agent moves the actor briefly then stops
   it before the test ends. *Defense*: `ContinuesMoving` samples the final
   interval and requires the actor to still be advancing.
4. **No motion.** *Failure mode*: empty override; L1 passes. *Defense*:
   `MovingFromStart` fails when the actor never leaves its spawn.
5. **Test disabling.** *Failure mode*: agent edits the fixture. *Defense*:
   `CraftBenchTests` is outside the writable workspace and the runner
   materializes it from git HEAD (an on-disk edit never reaches the grade);
   committed changes are review-gated on commit.
