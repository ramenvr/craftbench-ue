---
id: t1-blueprint-event-to-action
substrate: CraftBenchTemplate
set: bp
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_DelayedMove :: ADelayedMoveFunctionalTest"]
---

# t1-blueprint-event-to-action

Simple-slate task (weak-model bottom-end resolution): wire ONE gameplay-start
event to ONE observable world action inside an existing Blueprint asset. A
placed object waits a stated 1.0 s after gameplay begins, then makes one single
300-unit translation along world +X, and never moves again. The intended
solution is three nodes: a start-of-play event, a delay, a move. The verifier
still has teeth: the fixture samples the actor's transform at three world-time
checkpoints (delay respected / arrived / stayed), pins the actor's identity,
and pins the behavior to the editable Blueprint asset so a C++-side edit or an
empty submission fails at a named assertion.

## Primary concept

- `ps-bp-intro` — Introduction to Blueprints (event-graph fundamentals)
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/introduction-to-blueprints-visual-scripting-in-unreal-engine)

Wiring an event-graph execution chain (event, latent delay, world action) in an
existing Blueprint Class is the load-bearing concept. The supporting
`ps-bp-class` (the asset the agent edits already exists; this task does not test
asset creation, unlike `t0-sanity-bp-log-on-beginplay`).

## Prompt given to the agent

> The level contains one placed object that currently does nothing. Its behavior
> lives in the editable asset at
> `Content/Tasks/t1-blueprint-event-to-action/BP_DelayedMover`, which is
> currently empty. Author the following start-of-play behavior entirely inside
> that asset: when gameplay begins, the object stays exactly where it was placed
> for **1.0 second**, then moves **300 units along the world positive X axis**
> from its placed position in one single step, and then never moves again. The
> checker samples the object's position over time: at **0.5 s** after gameplay
> begins the object must not have moved (within 2 units of its placed position);
> by **1.5 s** it must be at its placed position plus (300, 0, 0) (within 2
> units); at **2.5 s** it must still be at that same offset position (within 2
> units). The object must not be destroyed or replaced, and must not move at any
> other time or in any other direction. Do not edit any level or test file.

(Behavior-only: no engine class, node, or pattern names. The asset path is a
workspace input — the asset exists pre-task. Every number the fixture gates on
— the delay, the offset, the three sample times, the 2-unit tolerance — is
disclosed.)

## Workspace state pre-task

Files that **exist**:

- `Source/CraftBenchTemplate/Tasks/t1-blueprint-event-to-action/DelayedMoverActor.h`
  / `.cpp` — declares `ADelayedMoverActor : public AActor`; the constructor
  disables tick, creates a movable scene root, and adds
  `Tags.Add(FName("DelayedMoverRoot"))`. **No behavior is implemented.**
- `Content/Tasks/t1-blueprint-event-to-action/BP_DelayedMover.uasset` — a
  Blueprint subclass of `ADelayedMoverActor` with an **empty** event graph (no
  event implementations). This is the deliverable surface: the agent edits this
  asset (it sits inside the `Content/Tasks/` asset-writable carve-out).
- `Content/Maps/t1-blueprint-event-to-action/L_DelayedMove.umap` — persistent
  level with exactly one placed `BP_DelayedMover` instance at world location
  `(0, -400, 150)` (off the world origin, deliberately) and the placed L2
  fixture actor. Committed binary; `Content/Maps/` is deny-listed, so the agent
  neither can nor needs to edit it.

Files that **do not exist**:

- No event-graph logic in `BP_DelayedMover`, no C++ lifecycle overrides on
  `ADelayedMoverActor`, no other Blueprint. Solve by editing the existing
  Blueprint asset.
- No test source in the agent's writable path — the fixture lives in the
  `CraftBenchTests` module, which is deny-listed and graded from git HEAD.

## Verifier specification

Verification primitive: **pie-checkpoint-sampling** (transform over time via
the base class's checkpoint schedule). One fixture, one map, headless PIE at
`-deterministic -FPS=60`.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for "CraftBenchTemplateEditor Win64 Development"
assert: UnrealBuildTool exits 0 for "CraftBenchTemplate Win64 Development" (Game)
```

The expected deliverable is content-only (one `.uasset` edit); L1 confirms the
project still builds both targets. If the agent adds source anyway, the usual
"no new shadowed-variable / deprecated-declarations warnings in agent-touched
files" pin applies.

### L2 — PIE-native behavioral trace (`ADelayedMoveFunctionalTest`)

Fixture source (verifier-owned):
`Source/CraftBenchTests/Tasks/t1-blueprint-event-to-action/DelayedMoveFunctionalTest.{h,cpp}`.
Constants: `StartLocation = (0, -400, 150)`, `MoveOffset = (300, 0, 0)`,
`PositionToleranceUnits = 2.0`, checkpoints `{0.5, 1.5, 2.5}` seconds of world
game-time.

```text
ADelayedMoveFunctionalTest::PrepareTest():
    Super::PrepareTest()                       // base sets fixed timestep
    // Identity by project tag, never by class -- the agent may subclass.
    Found = GetAllActorsWithTag(World, "DelayedMoverRoot")
    if Found.Num() != 1:
        FinishTest(Failed, "Expected exactly one actor tagged 'DelayedMoverRoot'
                            in the level; found N.")
    TargetActor = Found[0]                     // identity pinned (weak ptr)

    // Asset-surface pins (the bp-basket teeth):
    LoadedClass = StaticLoadClass("/Game/Tasks/t1-blueprint-event-to-action/BP_DelayedMover.BP_DelayedMover_C")
    if LoadedClass == null:
        FinishTest(Failed, "No Blueprint asset found at the required path ...")
    if !TargetActor->IsA(LoadedClass):
        FinishTest(Failed, "The placed actor is not an instance of the Blueprint
                            asset at the required path ...")
    if no class in LoadedClass's Blueprint-generated chain (stopping at the
       first native class) declares its OWN ReceiveBeginPlay or ReceiveTick
       (ExcludeSuper):
        FinishTest(Failed, "The Blueprint asset at the required path does not
                            itself handle a start-of-gameplay or per-frame
                            event; ...")
    SetCheckpointSchedule({ 0.5, 1.5, 2.5 })
    // NO DispatchBeginPlay -- PIE fired BeginPlay before PrepareTest ran,
    // arming the agent's delay.

ADelayedMoveFunctionalTest::OnCheckpoint(Index, T):
    if TargetActor is stale:                   // any checkpoint
        FinishTest(Failed, "... the tracked actor no longer exists; the placed
                            object must move, not be destroyed or replaced.")
    Loc = TargetActor->GetActorLocation(); Target = Start + (300, 0, 0)
    Index 0 (t=0.5):  Dist(Loc, Start)  > 2.0 -> FinishTest(Failed,
        "... must still be at its placed start position (the 1.0s delay has not
         elapsed); ...")
    Index 1 (t=1.5):  Dist(Loc, Target) > 2.0 -> FinishTest(Failed,
        "... must have completed its single move to start + (300, 0, 0); ...")
    Index 2 (t=2.5):  Dist(Loc, Target) > 2.0 -> FinishTest(Failed,
        "... moved again after its single translation; ...")
                      else FinishTest(Succeeded)
```

**Pass criteria**: L1 green and all three checkpoints green. **Robust
identity**: lookup by the `DelayedMoverRoot` tag, never by class name; the
resolved instance is pinned for the whole run. **Timing tolerance**: the 1.0 s
delay is bracketed by the 0.5 s (must not have moved) and 1.5 s (must have
arrived) samples; position tolerance is 2 units at every sample.

## Reference solution metadata

- LOC range: 0 C++ LOC. One Blueprint edit: a start-of-play event, one 1.0 s
  delay, one relative-offset move node with `(300, 0, 0)` — three nodes, two
  wires, one literal.
- Files touched: 1 (`Content/Tasks/t1-blueprint-event-to-action/BP_DelayedMover.uasset`).
- Senior-dev hours: under 0.2 (minutes of editor work). Tiered T1 rather than
  T0 because the task asks for a real (if minimal) gameplay mechanism — timed
  event to world action — not just workspace literacy.

## Anti-gaming notes

1. **Instant move (delay skipped).** *Failure mode*: the object teleports to
   the offset immediately at gameplay start (or from a construction-time
   script), banking on the verifier only checking the endpoint. *Defense*:
   checkpoint 0 at t=0.5 s asserts the actor is still within 2 units of its
   placed start — named assertion `must still be at its placed start position`.
2. **Pre-moved placement in the map.** *Failure mode*: the actor is placed (or
   re-placed) at the target position so no runtime move is needed. *Defense*:
   two layers — `Content/Maps/` is deny-listed, so a submitted map edit is a
   sandbox reject (exit 4) before grading; and the fixture asserts against its
   own `StartLocation` constant, not the observed placement, so a re-placed
   actor fails checkpoint 0's named assertion anyway.
3. **Behavior implemented outside the editable asset (C++ edit on the scaffold
   parent).** *Failure mode*: the agent overrides `BeginPlay` in C++ on
   `ADelayedMoverActor` instead of authoring the Blueprint, defeating the
   bp-basket surface. *Defense*: PrepareTest requires the Blueprint-generated
   chain to declare its own start-of-gameplay or per-frame event handler
   (`ExcludeSuper`); a C++ edit never creates one, so the submission fails at
   `does not itself handle a start-of-gameplay or per-frame event`. (Partial —
   see Hidden invariants for the hybrid residual.)
4. **Destroy-and-respawn at the target (move by substitution).** *Failure
   mode*: the original actor is destroyed and a stand-in spawned at the offset
   position. *Defense*: identity is pinned to the instance resolved in
   PrepareTest (weak pointer); a stand-in leaves the pin stale and the next
   checkpoint fails at `the tracked actor no longer exists`.
5. **Test disabling.** *Failure mode*: the agent edits the fixture to lower the
   bar. *Defense*: `Source/CraftBenchTests/` is outside the writable set
   (sandbox deny), and the runner materializes the graded substrate from git
   HEAD, so an on-disk edit never reaches the grade; committed changes are
   review-gated on commit.

## Hidden invariants

This task has no hidden checkpoints; everything the fixture asserts is
disclosed above. Accepted residuals, stated honestly:

- **Fixture source is readable in the scratch (suite-wide residual).** The
  agent can read `Source/CraftBenchTests/` in its working copy (deny applies to
  *writes*), so every constant above is visible there. Accepted for the whole
  suite: the prompt already discloses every gated number, so reading the
  fixture teaches nothing that changes the required behavior.
- **Smooth arrival instead of one step.** A solution that interpolates to the
  offset, arriving within (0.5 s, 1.5 s], and then stops is observationally
  identical at every sampled instant and PASSes. Behavior-only grading accepts
  it; the contract the verifier owns is position-at-times.
- **Hybrid C++/Blueprint submission.** A submission that adds a trivial event
  to the Blueprint *and* implements the actual motion in a C++ edit to the
  scaffold would pass the asset-surface pin (it is a structural pin, not a
  behavior-attribution proof). Accepted at T1; full attribution would need L2I
  graph introspection this simple-slate task deliberately omits.
- **Component-only Blueprint solution.** A Blueprint that produces the motion
  purely via added components with no event implementation would false-fail the
  asset-surface pin. Judged acceptable: the prompt frames the behavior as
  event-then-action, and the pin accepts both the BeginPlay-delay and the
  Tick-accumulator graph shapes (the realistic solution space).
- **Move-away-and-return between samples.** Motion strictly inside the
  (1.5 s, 2.5 s) window that returns to the target by t=2.5 is not observed.
  Accepted at T1 (continuous per-frame policing is a T2+ fixture pattern).
