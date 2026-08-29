---
id: t1-physics-drop-and-rest
substrate: CraftBenchTemplate
set: cpp
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_PhysicsDrop :: APhysicsDropFunctionalTest"]
---

# t1-physics-drop-and-rest

A dynamic physics object with channel-specific collision: a cube that falls under
gravity, passes through the player (Pawn) channel, blocks static world geometry,
and comes to rest on the floor. Drawn from an earlier internal task list (not shipped)
("t6-dynamic-physics-and-collision").

## Primary concept

- `ps-collision-physics` — Simulated physics + collision channel responses
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine)

Enabling rigid-body simulation and configuring per-channel collision responses is
the load-bearing concept; the result is observed as runtime motion, not config.

## Prompt given to the agent

> The project contains an actor placed in the level a few metres above a floor,
> displaying a cube. Make the cube a dynamic physics object so it falls under
> gravity and reacts to forces. Then set its collision so it **ignores the player
> (Pawn) channel** — it must not collide on the Pawn channel — while still
> **blocking static world geometry (the WorldStatic channel)** so it comes to
> rest on the floor rather than passing through it. Solve in C++ on the existing
> class — do not edit the level and do not edit any test file.

## Workspace state pre-task

Files that **exist** under `Source/CraftBenchTemplate/`:

- `CraftBenchTemplate.Build.cs` — already depends on `Core`, `CoreUObject`,
  `Engine`, `InputCore`, `FunctionalTesting`. No edit needed.
- `Tasks/t1-physics-drop-and-rest/PhysicsDropActor.h` / `.cpp` — declares and
  defines `class CRAFTBENCHTEMPLATE_API APhysicsDropActor : public AActor`. The
  constructor creates a **movable** `UStaticMeshComponent` ("Body") showing the
  engine cube as the root and adds the `PhysicsDropRoot` tag. **Physics is off
  and collision is at defaults.**
- `Content/Maps/t1-physics-drop-and-rest/L_PhysicsDrop.umap` — the actor placed
  at height above a large static floor, plus a test harness actor.

Files that **do not exist**:

- No physics enable, no collision configuration, no Blueprint subclass, no level
  edits. Solve in C++ on the existing class.
- No test source in the agent's writable path (the harness is in a separate,
  read-only `CraftBenchTests` module).

## Verifier specification

The test runs in PIE from
`Maps/t1-physics-drop-and-rest/L_PhysicsDrop.umap` at a fixed deterministic step
(`-deterministic -FPS=60`), so the physics simulation is deterministic.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for both the Editor and Game targets
assert: no new shadowed-variable / deprecated-declarations warnings in
        Source/CraftBenchTemplate/Tasks/t1-physics-drop-and-rest/PhysicsDropActor.{h,cpp}
```

### L2 — AFunctionalTest behavioral trace

```text
APhysicsDropFunctionalTest::PrepareTest():
    Found = GetAllActorsWithTag(World, "PhysicsDropRoot")
    AssertEqual_Int(Found.Num(), 1, "Exactly one PhysicsDropRoot actor")
    SetCheckpointSchedule({ 0.2, 1.5, 3.0, 3.5 })

checkpoint 0 (t≈0.2s): record StartZ; read the root primitive's collision:
    AssertEqual(response to Pawn == Ignore)
    AssertEqual(response to WorldStatic == Block)
checkpoint 1 (t≈1.5s): AssertLess(Z, StartZ - 50)   // fell under gravity
checkpoint 2 (t≈3.0s): record RestZ
checkpoint 3 (t≈3.5s): AssertNear(Z, RestZ, 5)       // came to rest
                       AssertGreater(Z, 20)          // did not fall through the floor
    FinishTest(Succeeded)
```

**Pass criteria**: both L1 and L2 green. **Robust identity**: lookup by the
`PhysicsDropRoot` tag, never by class name.

## Reference solution metadata

- LOC range: ~5-8 LOC (`SetSimulatePhysics(true)` + the collision enable/object
  type + the two channel responses, in the constructor).
- Files touched: 2 (the pre-existing header + cpp; no new files).
- Senior-dev minutes: under 15.

## Anti-gaming notes

1. **No physics.** *Failure mode*: agent sets the collision responses but never
   enables simulation, so the cube never falls; L1 passes. *Defense*: checkpoint
   1 asserts the cube descended at least 50 units under gravity; a static cube
   fails.
2. **Wrong Pawn response.** *Failure mode*: agent leaves the default Pawn
   response (Block). *Defense*: checkpoint 0 asserts the Pawn response is
   Ignore.
3. **Doesn't block the floor.** *Failure mode*: agent disables collision entirely
   to "simulate" falling, so the cube passes through the floor. *Defense*:
   checkpoint 3 asserts the resting Z is above the floor; a fall-through lands
   far below and fails, and checkpoint 0 asserts WorldStatic == Block.
4. **Never settles.** *Failure mode*: the cube keeps bouncing/moving. *Defense*:
   checkpoint 3 asserts Z is within 5 units of the checkpoint-2 Z (at rest).
5. **Test disabling.** *Failure mode*: agent edits the fixture to lower the bar.
   *Defense*: `CraftBenchTests` is outside the writable workspace and the
   runner materializes it from git HEAD (an on-disk edit never reaches the
   grade); committed changes are review-gated on commit.
