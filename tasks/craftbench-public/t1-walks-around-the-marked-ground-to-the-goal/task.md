---
id: t1-walks-around-the-marked-ground-to-the-goal
substrate: ThirdPerson
set: craftbench-public
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_DetourYard :: AMarkedGroundDetourFunctionalTest"]
---

# t1-walks-around-the-marked-ground-to-the-goal

Getting a figure across a yard without setting foot on the ground that is out of
bounds — where the out-of-bounds ground is a **concave** shape whose mouth
straddles the direct line, and where **which** of the two identically-shaped
patches is out of bounds **changes between the two trips**.

Imported from the Startup Eval corpus row `t1-nav-avoids-region-to-goal`
(provenance, owner note, and every deviation: `notes.md`).

> **This task is deliberately harder than the eight that shipped before it**
> (owner directive 2026-08-18: a task a hand-written reference passes easily is
> probably a task every flagship model passes, and a benchmark of those measures
> nothing). Three things carry that, and all three are **measured by the
> authoring script**, which refuses to save a level where any of them stops
> being true:
>
> 1. **Local steering does not solve it.** The authoring script simulates a
>    greedy avoider — head for the goal, sidestep when the next step lands on
>    out-of-bounds paint — and refuses to save unless it gets *stuck*, with
>    either patch marked. Measured: stuck both ways.
> 2. **Keeping off all marked ground does not solve it.** A route avoiding both
>    patches exists but costs 1.31x the straight line against a 1.30x budget,
>    so a submission has to work out *which* patch is out of bounds.
> 3. **A route decided once does not solve it.** The yard swaps the marking
>    between trip 1 and trip 2. The measured reference detours to y=+1088 on the
>    first trip and y=-1070 on the second — the opposite way round.

## Primary concept

- `navigation-avoidance` — routing around ground that must not be crossed
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/navigation-system-in-unreal-engine)

The load-bearing behaviour is **planning a route against a constraint that is
read from the world and changes**, with the shape of the route graded rather
than only the arrival. The grade never asks *how*: a grid search, a navigation
mesh with a modifier, a visibility graph, or anything else pass identically.

## Prompt given to the agent

> The yard has a start mark, a goal mark, and two patches of marked ground
> between them. Both patches are the same shape and both are **paint** — nothing
> about them blocks anything, and a figure walks over them without noticing.
>
> One of the two is **out of bounds**; the other may be crossed freely. Each
> patch says which it is, and the yard **changes its mind between trips**: the
> figure makes the crossing twice, and the patch that is out of bounds the
> second time is the other one.
>
> Get the figure from the start mark to the goal mark, both times, without ever
> standing on the patch that is out of bounds at that moment. Each crossing must
> finish within **70 seconds** and must cover no more than **1.3 times** the
> straight-line distance from start to goal.
>
> Two things that will not work, so you do not spend the time: keeping off
> **both** patches costs more than the distance budget allows, and steering
> locally — heading for the goal and stepping aside when the next step would
> land on out-of-bounds ground — walks the figure into a dead end it cannot
> reason its way out of. The marked shapes are not convex.
>
> Do not change which patch is out of bounds, and do not make the marked ground
> solid: it is paint, it must stay walkable, and a straight line across either
> patch must be as clear at the end of the run as it was at the start.
>
> The figure already has a body, a facing, one call that walks it toward a point
> at a given speed, and a test for whether it has arrived. Nothing decides where
> it should be going. Do not move the patches, the marks or the figure's start,
> and do not edit the level, any config file, or any test file. Write your
> solution in C++ under `Source/ThirdPerson/`.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on
this substrate). `Source/CraftBenchTests/` is deny-listed and a submission file
under it is a SANDBOX-REJECT (exit 4), not a graded FAIL; so are
`Content/Maps/`, `Content/ThirdPerson/`, `Content/Characters/` and every
`Config/` file (no `config_allow` is declared by this task).

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t1-walks-around-the-marked-ground-to-the-goal/DetourWalkerActor.h` /
  `.cpp` — `class THIRDPERSON_API ADetourWalkerActor : public AActor`, tagged
  `DetourWalker`. Supplied:
  - `Hull` — a capsule, 70 cm across and 180 cm tall, **the root**, collision
    `BlockAll`. A capsule and not the mesh on purpose: a root component's
    relative location *is* the actor's location, so a mesh made root and offset
    upward leaves its collision centred on the actor origin, half buried in the
    floor and permanently penetrating it.
  - `Body`, `Snout` — what a reviewer sees, and which way it faces.
  - `UPROPERTY(EditDefaultsOnly) float WalkSpeedUu = 340.f`,
    `float ArriveRadiusUu = 110.f`.
  - `UFUNCTION(BlueprintCallable) void StepToward(const FVector& Destination,
    float SpeedUu, float DeltaSeconds)` — the supplied locomotion. One frame
    toward `Destination` at `SpeedUu`, never overshooting, turning to face the
    way it moved, leaving height alone.
  - `UFUNCTION(BlueprintPure) bool HasReached(const FVector& Point) const`.
  - **No tick, no route, no call to `StepToward` anywhere.** The whole decision
    is the agent's, **and it has to land on this class**: the figure is a placed
    instance of `ADetourWalkerActor` in a map you cannot edit, so a subclass
    would never be instantiated and the placed figure would stay inert.
- `Tasks/t1-walks-around-the-marked-ground-to-the-goal/MarkedGroundActor.h` /
  `.cpp` — `class THIRDPERSON_API AMarkedGroundActor : public AActor`, tagged
  `MarkedGround`. **Supplied and complete**:
  - Three flat painted strokes forming a **U**, 34 m across the mouth and 15 m
    deep, all with **no collision**. Built in the constructor, so both patches
    are the same shape by construction.
  - `UPROPERTY(BlueprintReadOnly) bool bOutOfBounds` and
    `UFUNCTION(BlueprintPure) bool IsOutOfBounds() const` — whether crossing
    this patch is out of bounds right now. The yard sets it before each trip.
  - `UFUNCTION(BlueprintCallable) void SetOutOfBounds(bool)` — sets the flag and
    repaints the patch (lava for out of bounds, glow for allowed) so the state
    is on screen. **The yard calls this; a submission that calls it has changed
    the question rather than answered it, and the fixture fails that by name.**
  - `UFUNCTION(BlueprintPure) bool CoversPoint(const FVector&) const` and
    `FBox WorldFootprint() const` — the patch's own geometry, supplied so that
    working out the shape is not the exercise.
- `Content/Maps/t1-walks-around-the-marked-ground-to-the-goal/L_DetourYard.umap` —
  the staged yard, committed binary. World Settings name NO game mode, so the
  level inherits `BP_ThirdPersonGameMode` and a reviewer can walk in and watch.
  What is in it:

  | Element | Placement | Notes |
  |---|---|---|
  | Floor | 8,000 x 5,200, striped every 400 cm | stripes **non-colliding** — a 3 cm lip is a wall to anything moved by a swept `SetActorLocation` |
  | Two `AMarkedGroundActor`s | mouths facing back toward the start, staggered | same shape; which is out of bounds is the yard's to say, and it says something different on each trip |
  | One `ADetourWalkerActor` | on the start mark, standing at its own half-height | |
  | Start and goal marks | tagged `DetourStart` / `DetourGoal`, flat discs **below** the walker's capsule | a disc standing proud of the floor overlaps the capsule and the walker cannot move at all |
  | Backdrop + landmarks | a low back wall and two differently sized marker posts | a moving camera is distinguishable from a still one |
  | Fixture | one placed `AMarkedGroundDetourFunctionalTest` | |

  **The patches' coordinates are deliberately NOT in this section**, and neither
  is which one starts out of bounds.

- `cameras.json` (the camera-plan lane; not part of this release) — the
  presentation-only camera plan. Non-gating.

Files that **do not exist**:

- No route, no planner, no Blueprint subclass, no level edits. The empty
  submission compiles (L1 green) and FAILs L2 on the first trip's time limit.
- No test source in the agent's writable path. `AMarkedGroundDetourFunctionalTest`
  lives in the `CraftBenchTests` module the agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t1-walks-around-the-marked-ground-to-the-goal/L_DetourYard.umap` on
the **ThirdPerson** substrate, ticked at a fixed deterministic step
(`-deterministic -FPS=60`). Verification primitive:
**pie-checkpoint-sampling** with an every-frame position probe.

**The fixture works out for itself whether the walker is on painted ground**,
from the patches' component bounds measured before play. It does NOT call
`AMarkedGroundActor::CoversPoint` — that class lives in the agent-writable
module, and an assertion that asks the submission whether the submission is
correct is not an assertion.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

The yard is crossed **twice**. `ApplyTripStaging` marks patch 0 out of bounds for
trip 1 and patch 1 for trip 2, puts the walker back on the start mark **at its
own standing height**, and starts the clock.

```text
assert: NeverStepsOnTheGroundThatIsOutOfBounds -- every frame, the walker's
        position is outside every stroke of the patch marked out of bounds
        for the trip in progress
assert: CrossesTheGroundThatIsAllowed  -- on each trip the walker set foot on
        the OTHER patch at least once. Keeping off all marked ground is not
        the task, and a route that does costs more than the budget anyway
assert: StaysWithinTheDistanceBudget   -- distance actually covered, per trip,
        <= 1.30x the straight-line start-to-goal distance
assert: ReachesTheGoalOnBothTrips      -- each trip reaches the goal within
        70 s; a trip that does not ends the test naming the trip
assert: TheMarkingWasNotChanged        -- each patch's bOutOfBounds still reads
        what the yard set it to, every frame
assert: TheMarkedGroundWasNotMadeSolid -- a straight line across each patch at
        chest height was clear before play and is still clear
```

The checkpoint schedule carries a **sentinel at t = 260 s**, far past the two
trips, because `ACraftBenchFunctionalTest::Tick` ends the test the moment the
last scheduled checkpoint is sampled — so every gate that can only be judged
once both trips are done hangs off that sentinel.

**Staging faults are attributed, not scored.** A yard that cannot resolve its
walker, patches or marks, a patch with fewer than three strokes, a patch that
does not expose `bOutOfBounds` readably, or a patch that already blocks a
straight line before play, all end the run as `HARNESS-PRECONDITION`
(`EFunctionalTestResult::Error`), never as a model failure.

## Anti-gaming notes

1. **Steering instead of planning.** *Failure mode*: head for the goal and step
   aside when the next step lands on out-of-bounds paint — the shape most
   submissions reach for first. *Defense*: each patch is a **U whose mouth
   straddles the straight line**, so a steering walker drives into the pocket,
   meets the back wall, and meets an arm whichever way it slides; getting out
   means going backwards, which a greedy rule never does. The authoring script
   simulates exactly this walker and **refuses to save the level unless it gets
   stuck**, with either patch marked.
2. **Keeping off both patches.** *Failure mode*: treat all marked ground as out
   of bounds and never read the flag. *Defense*: a route avoiding both exists
   but costs 1.31x the straight line against a 1.30x budget, so
   `StaysWithinTheDistanceBudget` fails it — and `CrossesTheGroundThatIsAllowed`
   fails it by name even if it somehow fitted. The authoring script measures all
   three routes and refuses to save if avoiding both fits the budget.
3. **Deciding the route once.** *Failure mode*: work out a detour on the first
   trip and reuse it, or hard-code "go round the left-hand patch". *Defense*:
   the yard swaps which patch is out of bounds between trips, so a reused route
   walks straight over the newly forbidden patch and fails
   `NeverStepsOnTheGroundThatIsOutOfBounds` on trip 2 — and
   `ReachesTheGoalOnBothTrips` names the trip that did not finish.
4. **Making the ground solid.** *Failure mode*: give the marked patch collision,
   or drop a wall on it, so ordinary movement slides round it and no routing is
   needed. *Defense*: `TheMarkedGroundWasNotMadeSolid` traces a line across each
   patch at chest height before play and every frame after; paint that starts
   clear must stay clear. The authoring script separately refuses to save a
   level whose patches have any colliding geometry, so the gate cannot be
   vacuous.
5. **Repainting the question.** *Failure mode*: call `SetOutOfBounds` to mark
   the patch the walker was going to cross anyway as allowed. *Defense*:
   `TheMarkingWasNotChanged` compares every patch's flag against what the yard
   set, every frame, and fails naming the patch and the trip.
