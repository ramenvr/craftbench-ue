---
id: gp-spawner-population
substrate: CraftBenchTemplate
set: cpp
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_SpawnerPopulation :: ASpawnerPopulationFunctionalTest"]
---

# gp-spawner-population

Port of the **g2-4 "Spawner"** eval prompt onto the UE 5.7 CraftBenchTemplate
substrate. Probes the `ps-actors` concept (runtime `SpawnActor`) plus delegate-
driven lifecycle management: an actor must spawn and maintain a fixed population
of child actors, replace any that are destroyed, and clean them up when it dies.

The original g2-4 prompt named `BP_Spawner` and asked for a Blueprint deliverable
under `/Game/G2/4/`; this port restates the same behavior **behavior-only**
(Hard Rule #2) and grades it deterministically in headless PIE. The respawn and
cleanup legs make a single "spawned something" check insufficient (FR-017): the
verifier perturbs the population at runtime and requires the agent's logic to
recover.

## Primary concept

- `ps-actors` — Actors
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/actors-in-unreal-engine)

`UWorld::SpawnActor` is the load-bearing API: an actor must produce additional
runtime-spawned actors during play, maintain their count against destruction,
and tear them down on its own destruction. The verifier counts outcomes — any
mechanism (a destroyed-delegate, a polling Tick, or a timer) that satisfies the
observables passes.

## Prompt given to the agent

> The project contains an actor placed in the level. After gameplay begins, this
> actor must immediately spawn exactly **five** additional actors, each at a
> random location within **500 units** of the spawning actor. Each spawned actor
> must carry the tag `SpawnedMinion` (added to its `Tags` array) so it can be
> identified in the world. If any spawned actor is destroyed during play, the
> spawning actor must spawn a replacement so that exactly five `SpawnedMinion`
> actors exist again shortly afterward. When the spawning actor itself is
> destroyed, all of its spawned actors must be removed from the world. Solve in
> C++ on the existing class.

## Workspace state pre-task

Files that **exist** under `Source/CraftBenchTemplate/`:

- `CraftBenchTemplate.Build.cs` — `PublicDependencyModuleNames` already includes
  `Core`, `CoreUObject`, `Engine`, `InputCore`, `FunctionalTesting`. No edit
  needed.
- `SpawnerActor.h` / `SpawnerActor.cpp` — declares
  `class CRAFTBENCHTEMPLATE_API ASpawnerActor : public AActor`. Constructor sets
  `PrimaryActorTick.bCanEverTick = true;` and adds `Tags.Add(FName("SpawnerRoot"))`.
  No `BeginPlay`, no `EndPlay`, no spawn logic declared.
- `Maps/L_SpawnerPopulation.umap` — persistent level with one placed
  `ASpawnerActor` (tag `SpawnerRoot`, located off the world origin) and one
  placed `ASpawnerPopulationFunctionalTest`. The runner opens it explicitly as a
  positional argument.
- `ASpawnerPopulationFunctionalTest` lives in the verifier-only `CraftBenchTests`
  editor module; the agent cannot read or modify it.

Files that **do not exist**:

- No `BeginPlay`, no `EndPlay`, no `Tick` override, no Blueprint subclass of
  `ASpawnerActor`, no level edits. Solve in C++ on the existing class.

## Verifier specification

The test runs in a real PIE world via the standard runner invocation. `BeginPlay`
auto-fires on the placed `SpawnerRoot` actor (spawning the initial population);
the fixture advances time via its checkpoint schedule, samples the
`SpawnedMinion` population, and perturbs it to probe respawn + cleanup.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for "CraftBenchTemplateEditor <Platform>
        Development" target
assert: no new shadowed-variable or deprecated-declarations warnings in
        Source/CraftBenchTemplate/SpawnerActor.{h,cpp}
```

### L2 — AFunctionalTest behavioral trace

```text
ASpawnerPopulationFunctionalTest::PrepareTest():
    // Identify the host by tag, cache its location for the radius check.
    TArray<AActor*> Found
    UGameplayStatics::GetAllActorsWithTag(World, FName("SpawnerRoot"), Found)
    AssertEqual_Int(Found.Num(), 1, "Exactly one SpawnerRoot")
    SpawnerLocation = Found[0]->GetActorLocation()
    SetCheckpointSchedule({0.5, 1.5, 2.5})

ASpawnerPopulationFunctionalTest::OnCheckpoint():
    at t = 0.5 (checkpoint 0):
        AssertEqual_Int(CountTag("SpawnedMinion"), 5, "5 minions on BeginPlay")
        AssertAll(dist(minion, SpawnerLocation) <= 650, "each within radius")
        // then: destroy ONE SpawnedMinion to probe respawn

    at t = 1.5 (checkpoint 1):
        AssertEqual_Int(CountTag("SpawnedMinion"), 5, "population restored")
        // then: destroy the SpawnerRoot host to probe cleanup

    at t = 2.5 (checkpoint 2):
        AssertEqual_Int(CountTag("SpawnedMinion"), 0, "children cleaned up")
        // base FinishTest(Succeeded) after the last checkpoint
```

**Pass criteria**: every assertion green. **Robust identity**: host lookup by
tag, never by class. **Radius slack**: the prompt asks for 500 units; the
verifier allows up to 650 and places the host OFF the world origin so a rootless
"minion" reporting (0,0,0) lands far outside the limit and fails.

## Reference solution metadata

- LOC range: 35-60 LOC (BeginPlay population spawn, a spawn helper that gives
  each child a scene root + tag + an OnDestroyed binding, the destroyed-delegate
  respawn callback with a shutdown guard, and an EndPlay cleanup)
- Files touched: 2 (1 header, 1 cpp; both pre-existing — no new files)
- Senior-dev hours: 30-45 minutes

## Anti-gaming notes

1. **Spawn one and stop ("not empty" overfit).** *Failure mode*: agent spawns a
   single child so a naive "SpawnedMinion exists" check passes. *Defense*: the
   0.5s checkpoint asserts exactly 5 — a count != 5 fails.
2. **Over-spawn (loop bug).** *Failure mode*: agent spawns every tick, producing
   dozens of children. *Defense*: every checkpoint asserts an exact count (5,
   then 5, then 0); a runaway loop fails the count.
3. **Rootless / wrong-location spawn.** *Failure mode*: agent spawns bare actors
   with no root component (world location reads as the origin) or dumps them at a
   fixed point. *Defense*: the host is placed off the origin and the verifier
   asserts each minion is within 650 units of the host; origin-located minions
   are ~thousands of units away and fail.
4. **No respawn (static population).** *Failure mode*: agent spawns 5 once and
   never reacts to destruction. *Defense*: the fixture destroys one minion at
   0.5s; the 1.5s checkpoint requires the count back at 5, so a static solution
   fails.
5. **No cleanup (orphaned children).** *Failure mode*: agent leaves spawned
   actors in the world when the spawner dies. *Defense*: the fixture destroys the
   host at 1.5s; the 2.5s checkpoint requires 0 SpawnedMinion actors, so leaked
   children fail. (A solution that respawns *during* its own teardown also fails
   this checkpoint, forcing a shutdown guard.)
