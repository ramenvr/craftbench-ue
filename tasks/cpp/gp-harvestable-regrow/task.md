---
id: gp-harvestable-regrow
substrate: CraftBenchTemplate
set: cpp
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_HarvestableRegrow :: AHarvestableRegrowFunctionalTest"]
fps_legs: [60, 20]
---

# gp-harvestable-regrow

Port of the **g2-3 "Harvestable"** eval prompt onto the UE 5.7 CraftBenchTemplate
substrate. Probes the `collision-overview` concept (an overlap event triggers a
gameplay reaction) plus a timer-driven state machine: an actor starts in an
"active" state, transitions to a "regrowing" state when something walks into it,
and returns to "active" automatically after a fixed 5-second delay.

The original g2-3 prompt named `BP_Harvestable`, asked for an enum, a cube mesh,
a per-state material swap, multiplayer-replicated state, and a sound on state
change, with a Blueprint deliverable under `/Game/G2/3/`. This port restates only
the **deterministically gradeable core behavior-only** (Hard Rule #2) and grades
it in headless PIE. The ungateable aspects of the original (replication,
material-swap visuals, and the state-change sound) are **dropped** — headless PIE
with `-nullrhi` and no second client cannot observe them. What remains, and what
the verifier checks, is the observable state machine: active -> regrowing (on
overlap) -> active (after 5 s). The 5-second regrow window and the
return-to-active leg make a single "did it react once" check insufficient
(FR-017): the verifier samples the state at three world-times across the cycle.

## Primary concept

- `collision-overview` — Collision Overview
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine---overview)

A primitive-component overlap event is the load-bearing trigger: the actor must
detect that another actor has entered its collision volume ("walked into it") and
react. The secondary mechanism is `ps-timers` (Gameplay Timers,
https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-timers-in-unreal-engine) —
the 5-second return-to-active delay must be a framerate-independent scheduled
callback, not a tick-count or a hardcoded frame number. The verifier observes the
state transition outcomes; any mechanism (a timer, a timeline, a polling Tick
accumulator) that satisfies the observable schedule passes.

## Prompt given to the agent

> The project contains an actor placed in the level that represents a harvestable
> object. It begins in an **active** state. When any other actor walks into it
> (enters its collision volume), it is harvested: it prints a log message and
> immediately switches to a **regrowing** state. While the actor is regrowing it
> must carry the tag `Regrowing` in its `Tags` array, and it must **not** be
> harvestable again — walking into it while it is regrowing does nothing.
> Exactly **5 seconds** after it begins regrowing, it returns to the active state:
> the `Regrowing` tag is removed and it can be harvested again. The 5-second delay
> must hold regardless of frame rate. Solve in C++ on the existing class.

## Workspace state pre-task

Files that **exist** under `Source/CraftBenchTemplate/`:

- `CraftBenchTemplate.Build.cs` — `PublicDependencyModuleNames` already includes
  `Core`, `CoreUObject`, `Engine`, `InputCore`, `FunctionalTesting`. No edit
  needed.
- `HarvestableActor.h` / `HarvestableActor.cpp` — declares
  `class CRAFTBENCHTEMPLATE_API AHarvestableActor : public AActor`. The
  constructor enables tick, creates a `USphereComponent` set as the root component
  (collision enabled as a query-only overlap volume so something walking into it
  can be detected), and adds `Tags.Add(FName("HarvestableRoot"))`. No `BeginPlay`,
  no overlap handler, no state logic, and **no** `Regrowing` tag are declared —
  that is the agent's responsibility.
- `Maps/L_HarvestableRegrow.umap` — persistent level with one placed
  `AHarvestableActor` (tag `HarvestableRoot`, located off the world origin) and one
  placed `AHarvestableRegrowFunctionalTest`. The runner opens it explicitly as a
  positional argument.
- `AHarvestableRegrowFunctionalTest` lives in the verifier-only `CraftBenchTests`
  editor module; the agent cannot read or modify it.

Files that **do not exist**:

- No `BeginPlay`, no overlap-event binding, no state enum, no `FTimerHandle`
  member, no Blueprint subclass of `AHarvestableActor`, no level edits. Solve in
  C++ on the existing class.

## Verifier specification

The test runs in a real PIE world via the standard runner invocation. `BeginPlay`
auto-fires on the placed `HarvestableRoot` actor (which initializes it in the
active state); the fixture advances time via its checkpoint schedule, samples the
`Regrowing` tag, and induces a harvest by spawning a probe actor inside the
harvestable's collision volume (the verifier never injects player input — it
drives the overlap directly).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH the "CraftBenchTemplateEditor <Platform>
        Development" and "CraftBenchTemplate <Platform> Development" targets
        (short-circuits on the first failure)
assert: no new shadowed-variable or deprecated-declarations warnings in
        Source/CraftBenchTemplate/HarvestableActor.{h,cpp}
```

### L2 — AFunctionalTest behavioral trace

```text
AHarvestableRegrowFunctionalTest::PrepareTest():
    // Identify the host by tag, cache it (the host is never destroyed here).
    TArray<AActor*> Found
    UGameplayStatics::GetAllActorsWithTag(World, FName("HarvestableRoot"), Found)
    AssertEqual_Int(Found.Num(), 1, "Exactly one HarvestableRoot")
    Harvestable = Found[0]
    SetCheckpointSchedule({0.5, 2.0, 7.5})   // seconds since PIE world began play

AHarvestableRegrowFunctionalTest::OnCheckpoint():
    at t = 0.5 (checkpoint 0) — STARTS ACTIVE, then INDUCE a harvest:
        AssertFalse(Harvestable has tag "Regrowing", "starts active, not regrowing")
        // Spawn a probe actor (with an overlapping collision sphere) AT the
        // harvestable's location so its collision volume fires BeginOverlap.
        SpawnProbeAtHarvestable()

    at t = 2.0 (checkpoint 1) — ~1.5 s after harvest, must be REGROWING:
        AssertTrue(Harvestable has tag "Regrowing", "regrowing after overlap")

    at t = 7.5 (checkpoint 2) — ~7 s after harvest (> 5 s regrow), back ACTIVE:
        AssertFalse(Harvestable has tag "Regrowing", "returned to active after 5 s")
        // base FinishTest(Succeeded) after the last checkpoint
```

**Pass criteria**: every assertion green. **Robust identity**: host lookup by
tag, never by class. **Timing tolerance**: the harvest fires at ~0.5 s, so the
return-to-active deadline is ~5.5 s; the t=2.0 s checkpoint lands well inside the
regrow window and the t=7.5 s checkpoint lands ~2 s past the deadline, tolerating
overlap-update and timer-scheduling slack on both ends. **Off-origin host**: the
host is placed off the world origin and the probe is spawned at the host's actual
location, so an agent cannot pass by reacting to an overlap at (0,0,0).

## Reference solution metadata

- LOC range: 35-55 LOC (a state enum or bool, a BeginPlay that sets active +
  binds the sphere's `OnComponentBeginOverlap`, the overlap handler that guards
  against re-harvest while regrowing / logs / adds the `Regrowing` tag / starts a
  5 s timer, and the timer callback that removes the tag and returns to active)
- Files touched: 2 (1 header, 1 cpp; both pre-existing — no new files)
- Senior-dev hours: 30-45 minutes

## Anti-gaming notes

1. **Never regrows (static active).** *Failure mode*: agent ignores the overlap
   entirely, so the actor stays active forever. *Defense*: the t=2.0 s checkpoint
   asserts the `Regrowing` tag is present after the induced harvest; a no-op
   solution fails it.
2. **Permanently regrowing (latches and never returns).** *Failure mode*: agent
   sets the regrowing state on overlap but never starts (or never fires) the
   return timer, so the tag is stuck on. *Defense*: the t=7.5 s checkpoint asserts
   the `Regrowing` tag is gone ~7 s after harvest; a latched solution fails it.
3. **Regrows instantly (no real delay).** *Failure mode*: agent flips to
   regrowing and back within the same frame (or far faster than 5 s), banking on
   the verifier only checking the endpoints. *Defense*: the t=2.0 s checkpoint
   requires the tag to STILL be present ~1.5 s after harvest; an instant-return
   solution has already dropped the tag by then and fails.
4. **Frame-count timer (framerate overfit).** *Failure mode*: agent returns to
   active after a fixed number of ticks (e.g. 300 frames ~ 5 s at 60 Hz) instead
   of a wall-time delay. *Defense*: the base fixture runs under
   `FApp::SetUseFixedTimeStep` at the runner's `-FPS`; a frame-count solution
   tuned for 60 Hz returns at the wrong world-time under any other rate, and the
   wide t=2.0 / t=7.5 sampling band only forgives a real ~5 s wall-time delay.
5. **Re-harvestable while regrowing (no guard).** *Failure mode*: agent restarts
   the regrow timer on every overlap, so a second walk-in during regrowth resets
   the 5 s clock and the actor never returns within the window. *Defense*: the
   prompt requires the actor to be non-harvestable while regrowing; the host is
   placed off-origin with the probe at its location, and a re-entrant overlap that
   keeps resetting the timer pushes the return past the t=7.5 s checkpoint and
   fails. (The fixture spawns a single probe, but a guard is still the only robust
   way to satisfy the "does nothing while regrowing" clause and the late
   checkpoint together.)
