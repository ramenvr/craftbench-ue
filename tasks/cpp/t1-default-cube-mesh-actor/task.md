---
id: t1-default-cube-mesh-actor
substrate: CraftBenchTemplate
set: cpp
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_DefaultCubeMesh :: ADefaultCubeMeshFunctionalTest"]
---

# t1-default-cube-mesh-actor

A default-appearance exercise: an actor type whose every instance displays the
engine's built-in cube mesh out of the box, because the cube is part of the
type's class defaults rather than something acquired at runtime. Drawn from an
earlier internal task list, not shipped ("Construction helper usage for
hard-coded content paths"). The source row's code-shape checks (a `CreateDefaultSubobject`
stored on a `UPROPERTY`, a `ConstructorHelpers::FObjectFinder` with a success
check) are cut with documented provenance — no source-inspection lane exists
(L5 is defined, not implemented) — and replaced by the behavioral observable
that separates the same solutions: a class default is present before any
play-time logic runs and lives on the class default object; a runtime
assignment is not and does not.

## Primary concept

- `ps-components` — Components
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/components-in-unreal-engine)

Establishing a component with its content as part of an actor type's defaults
is the load-bearing concept: the actor must carry its visual by construction,
not acquire it during play.

## Prompt given to the agent

> The project contains an actor type placed once in the level (tagged
> `CubeMeshDisplay`). Out of the box it renders nothing. Change the type so
> that the engine's built-in cube shape (the primitive asset at
> `/Engine/BasicShapes/Cube`) is its default appearance: every instance — the
> one already placed, any new one a designer drops into a level, any one
> spawned by code — must visibly display that cube with no per-instance
> configuration and no level edits. The cube must be part of what the type
> itself carries by default, already in place before any of the actor's
> play-time logic would run. Specifically, the cube must be part of the
> type's own default state: inspecting the type's defaults (what the editor
> shows as class defaults, before any instance exists) must already reveal
> the cube on its mesh component — not something each instance sets up for
> itself as it initializes. Solve in C++ on the existing class — do not
> create a Blueprint subclass, do not edit the level, and do not edit any
> test file.

## Workspace state pre-task

Files that **exist** under `Source/CraftBenchTemplate/`:

- `CraftBenchTemplate.Build.cs` — already depends on `Core`, `CoreUObject`,
  `Engine`, `InputCore`, `FunctionalTesting`. No edit needed.
- `Tasks/t1-default-cube-mesh-actor/CubeMeshActor.h` / `.cpp` — declares and
  defines `class CRAFTBENCHTEMPLATE_API ACubeMeshActor : public AActor`. The
  constructor disables tick, creates a plain `USceneComponent` root ("Root"),
  and adds the `CubeMeshDisplay` tag. **No visual component and no mesh
  assignment are provided.**
- `Content/Maps/t1-default-cube-mesh-actor/L_DefaultCubeMesh.umap` — persistent
  level with one placed `ACubeMeshActor` (tagged `CubeMeshDisplay`) and one
  placed test harness actor.

Files that **do not exist**:

- No static-mesh component, no mesh reference, no Blueprint subclass, no level
  edits. Solve in C++ on the existing class.
- No test source in the agent's writable path. The test harness lives in a
  separate `CraftBenchTests` module the agent cannot read or modify.

## Verifier specification

The test runs in PIE from
`Maps/t1-default-cube-mesh-actor/L_DefaultCubeMesh.umap` at a fixed
deterministic step (`-deterministic -FPS=60`).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for both the Editor and Game targets
assert: no new shadowed-variable / deprecated-declarations warnings in
        Source/CraftBenchTemplate/Tasks/t1-default-cube-mesh-actor/CubeMeshActor.{h,cpp}
        (warning diff pinned to agent-authored files only)
```

### L2 — AFunctionalTest behavioral trace

```text
ADefaultCubeMeshFunctionalTest::ctor():
    // Pre-BeginPlay observation — OnWorldInitializedActors fires after
    // PostInitializeComponents and before placed-actor BeginPlay (the t0
    // listener window). Record whether the 'CubeMeshDisplay' actor ALREADY
    // carries a static-mesh component whose mesh is
    // StaticMesh'/Engine/BasicShapes/Cube.Cube'.

ADefaultCubeMeshFunctionalTest::PrepareTest():
    // Identity by project tag, never by C++ class name — the agent may
    // legitimately subclass ACubeMeshActor.
    Found = GetAllActorsWithTag(World, "CubeMeshDisplay")
    AssertEqual_Int(Found.Num(), 1, "Exactly one CubeMeshDisplay actor")
    SetCheckpointSchedule({ 0.5 })

checkpoint 0 (t=0.5s, after BeginPlay so any runtime assignment has happened):
    assert: a registered, visible static-mesh component on the tagged actor
            displays '/Engine/BasicShapes/Cube.Cube'
            (fail detail names what was found instead: no component / a
            component with no mesh assigned / a different mesh path)
    assert: the pre-BeginPlay observation already saw the cube — a mesh
            "assigned at runtime rather than carried as a class default" fails
    assert: the actor's class default object carries the cube on a
            static-mesh component (the TYPE ships the cube, not the instance)
    FinishTest(Succeeded)
```

**Pass criteria**: both L1 and L2 green. **Robust identity**: lookup by the
`CubeMeshDisplay` tag, never by class name.

## Reference solution metadata

- LOC range: ~12-20 LOC (a default-subobject static-mesh component plus a
  constructor-time asset lookup with a success check).
- Files touched: 2 (the pre-existing header + cpp; no new files).
- Senior-dev minutes: under 30.

## Anti-gaming notes

1. **Per-instance initialization instead of a type default.** *Failure mode*:
   agent assigns the cube from each instance's own lifecycle (`BeginPlay`,
   first tick, or an earlier per-instance initialization hook), so every
   instance looks correct when sampled without the type carrying anything.
   *Defense*: the prompt explicitly discloses the type-defaults requirement,
   so this route is an excluded non-solution, not a trap. A BeginPlay/tick
   assignment fails the pre-BeginPlay observation (OnWorldInitializedActors
   window) with the runtime-assignment message; any per-instance route —
   including hooks that run before that window — fails the class-default-object
   probe.
2. **Wrong primitive.** *Failure mode*: agent assigns some other engine
   primitive (sphere, cylinder) or a project-local cube-looking mesh.
   *Defense*: the assert compares the mesh's full object path against
   `/Engine/BasicShapes/Cube.Cube`; the failure names the path found instead.
3. **Half-delivery.** *Failure mode*: agent adds the static-mesh component but
   never assigns a mesh; a component-presence check would pass. *Defense*: all
   three probes key on the assigned mesh's identity, not component presence
   ("with no mesh assigned" fails).
4. **Invisible delivery.** *Failure mode*: the cube is assigned on a component
   that is never registered or is hidden in game. *Defense*: the checkpoint
   probe requires a registered, visible, not-hidden-in-game component.
5. **Test disabling.** *Failure mode*: agent edits `ADefaultCubeMeshFunctionalTest`
   to lower the bar. *Defense*: `CraftBenchTests` is outside the writable
   workspace and the runner grades the substrate from git HEAD —
   human review gates any committed change to it.
