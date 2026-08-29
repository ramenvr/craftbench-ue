---
id: gp-crafting-queue
substrate: CraftBenchTemplate
set: cpp
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_CraftingQueue :: ACraftingQueueFunctionalTest"]
---

# gp-crafting-queue

Port of the **g2-5 "Crafting queue"** eval prompt onto the UE 5.7
CraftBenchTemplate substrate. Probes the `ps-timers` concept
(`FTimerManager` API) plus FIFO queue processing: an actor must process a
queue of named crafting actions strictly one-at-a-time, paced by timers
(roughly one second per action), never starting the next until the current
finishes.

The original g2-5 prompt named a `BPC_CraftingQueue` component, asked for an
event-dispatcher payload, and forbade ticking, all under `/Game/G2/5/`. This
port restates the deterministic core **behavior-only** (Hard Rule #2) and
grades it in headless PIE. Two rules from the original are dropped because they
are not world-observable: "must not tick" (tick vs. timer is indistinguishable
to a headless observer) and "signal an event dispatcher with the completed
craft" (a fixture cannot bind to an agent's arbitrary BP multicast delegate).
Each completion is instead made world-observable: the agent must spawn a small
tagged marker actor per completed craft, so completions can be **counted in
order over time**. The per-second pacing across five checkpoints makes a
single "spawned something" check insufficient (FR-017): burst-completing in
BeginPlay, never completing, or processing too fast all fail.

## Primary concept

- `ps-timers` — Gameplay Timers (FTimerManager API)
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-timers-in-unreal-engine)

`FTimerManager` is the load-bearing API: the actor must process four queued
actions strictly one at a time, each spaced ~1 second apart, which a timer
(one-shot rescheduled per item, or a repeating timer) guarantees and a
burst loop does not. The verifier counts completions at five checkpoints —
any mechanism (a repeating timer, a chained one-shot timer, or a tick
accumulator) that satisfies the one-per-second FIFO pacing passes.

## Prompt given to the agent

> The project contains an actor placed in the level. After gameplay begins,
> this actor must queue exactly **four** named crafting actions (each action
> is just a string name) and process them strictly **one at a time, in the
> order they were queued** — it must never begin the next action until the
> current one has finished. Each crafting action takes about **one second**
> to complete. Each time an action completes, the actor must spawn one small
> marker actor into the world carrying the tag `CraftCompleted` (added to its
> `Tags` array), so that completions can be counted in order. Concretely:
> roughly one second after gameplay begins the first action completes (one
> `CraftCompleted` actor exists), about two seconds in the second completes
> (two exist), and so on until all four have completed (four exist). The
> actor must not complete several actions at once or finish them all
> instantly. Solve in C++ on the existing class.

## Workspace state pre-task

Files that **exist** under `Source/CraftBenchTemplate/`:

- `CraftBenchTemplate.Build.cs` — `PublicDependencyModuleNames` already includes
  `Core`, `CoreUObject`, `Engine`, `InputCore`, `FunctionalTesting`. No edit
  needed.
- `CraftQueueActor.h` / `CraftQueueActor.cpp` — declares
  `class CRAFTBENCHTEMPLATE_API ACraftQueueActor : public AActor`. Constructor sets
  `PrimaryActorTick.bCanEverTick = true;` and adds `Tags.Add(FName("CraftQueueRoot"))`.
  No `BeginPlay`, no queue, no timer logic declared.
- `Maps/L_CraftingQueue.umap` — persistent level with one placed
  `ACraftQueueActor` (tag `CraftQueueRoot`, located off the world origin) and one
  placed `ACraftingQueueFunctionalTest`. The runner opens it explicitly as a
  positional argument.
- `ACraftingQueueFunctionalTest` lives in the verifier-only `CraftBenchTests`
  editor module; the agent cannot read or modify it.

Files that **do not exist**:

- No `BeginPlay`, no `Tick` override, no timer logic, no Blueprint subclass of
  `ACraftQueueActor`, no level edits. Solve in C++ on the existing class.

## Verifier specification

The test runs in a real PIE world via the standard runner invocation. `BeginPlay`
auto-fires on the placed `CraftQueueRoot` actor (queuing the four actions and
starting the first timer); `FTimerManager` ticks; the fixture advances time via
its checkpoint schedule and samples the running count of `CraftCompleted` marker
actors, which must increase by exactly one per second in FIFO order.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for "CraftBenchTemplateEditor <Platform>
        Development" target
assert: no new shadowed-variable or deprecated-declarations warnings in
        Source/CraftBenchTemplate/CraftQueueActor.{h,cpp}
```

### L2 — AFunctionalTest behavioral trace

```text
ACraftingQueueFunctionalTest::PrepareTest():
    // Identify the host by tag (never by class — agent may subclass).
    TArray<AActor*> Found
    UGameplayStatics::GetAllActorsWithTag(World, FName("CraftQueueRoot"), Found)
    AssertEqual_Int(Found.Num(), 1, "Exactly one CraftQueueRoot")
    SetCheckpointSchedule({0.5, 1.5, 2.5, 3.5, 4.5})

ACraftingQueueFunctionalTest::OnCheckpoint():
    at t = 0.5 (checkpoint 0):
        AssertEqual_Int(CountTag("CraftCompleted"), 0, "no craft done before 1s")
    at t = 1.5 (checkpoint 1):
        AssertEqual_Int(CountTag("CraftCompleted"), 1, "first craft done by ~1s")
    at t = 2.5 (checkpoint 2):
        AssertEqual_Int(CountTag("CraftCompleted"), 2, "second craft done by ~2s")
    at t = 3.5 (checkpoint 3):
        AssertEqual_Int(CountTag("CraftCompleted"), 3, "third craft done by ~3s")
    at t = 4.5 (checkpoint 4):
        AssertEqual_Int(CountTag("CraftCompleted"), 4, "all four crafts done by ~4s")
        // base FinishTest(Succeeded) after the last checkpoint
```

**Pass criteria**: every assertion green. **Robust identity**: host lookup by
tag, never by class. **Pacing window**: each checkpoint is at the ~midpoint of a
1-second window (0.5, 1.5, …), giving a correct one-per-second solution
comfortable slack on both sides while still rejecting a burst (count too high
early) and a stall (count too low late). The strictly-increasing 0,1,2,3,4
sequence gates BOTH that processing is one-at-a-time AND that all four actions
complete.

## Reference solution metadata

- LOC range: 30-50 LOC (BeginPlay enqueues 4 string actions and starts a
  repeating ~1s FTimerManager timer; the timer handler dequeues the front item,
  spawns one `CraftCompleted`-tagged marker actor for it, and clears the timer
  once the queue is empty)
- Files touched: 2 (1 header, 1 cpp; both pre-existing — no new files)
- Senior-dev hours: 30-45 minutes

## Anti-gaming notes

1. **Burst-complete all in BeginPlay ("count reaches 4" overfit).** *Failure
   mode*: agent spawns all four `CraftCompleted` markers immediately on
   BeginPlay so a naive "four markers exist" check passes. *Defense*: the 0.5s
   checkpoint asserts the count is exactly 0 and the 1.5s checkpoint asserts
   exactly 1 — an instant burst reads 4 at 0.5s and fails the very first
   checkpoint.
2. **Process too fast (no per-item pacing).** *Failure mode*: agent runs a tight
   timer (e.g. 0.1s) or a per-tick loop and finishes all four within the first
   second. *Defense*: every checkpoint asserts an exact running count
   (0,1,2,3,4); a fast solution overshoots (e.g. count 3 or 4 at t=1.5s) and
   fails the exact-count assertion.
3. **Never complete / stall mid-queue.** *Failure mode*: agent queues actions but
   never fires the timer, or stops after the first item. *Defense*: the later
   checkpoints require the count to keep climbing to 4 by t=4.5s; a stalled queue
   leaves the count too low and fails. A hung test also trips the base class
   TimeLimit and FAILS rather than hanging.
4. **Wrong count / over-spawn per completion.** *Failure mode*: agent spawns two
   markers per completed craft, or spawns extras, inflating the count.
   *Defense*: each checkpoint asserts the exact cumulative count, so spawning
   more than one marker per second fails (e.g. count 2 at t=1.5s).
5. **Out-of-order or parallel processing.** *Failure mode*: agent kicks off all
   four crafts concurrently with independent timers so they finish around the
   same time instead of one-at-a-time. *Defense*: the strictly +1-per-second
   sequence (0→1→2→3→4 across the five checkpoints) is only satisfiable by
   sequential one-at-a-time completion; concurrent completion bunches the count
   and fails the early checkpoints.
