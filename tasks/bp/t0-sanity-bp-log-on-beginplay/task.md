---
id: t0-sanity-bp-log-on-beginplay
substrate: CraftBenchTemplate
set: bp
tier: T0
capability_bucket: Gameplay Programming
category: other
layers: [L1, L2]
fixtures: ["L_BpSanityTask :: ABpSanityFunctionalTest"]
---

# t0-sanity-bp-log-on-beginplay

Smoke task — the Blueprint-authoring counterpart to `t0-sanity-log-on-beginplay`.
Its job is not to stress the agent's reasoning; its job is to test that the
**asset-authoring path** wires together end-to-end: an agent authors a brand-new
Actor **Blueprint** `.uasset` at a known path, and the verifier grades it via L1
(build) + L2 (the Blueprint is loaded by path, instantiated in a real PIE world,
and its BeginPlay emission is observed in the log). Where
`t0-sanity-log-on-beginplay` smoke-tests the C++/PIE path, this task smoke-tests
the Blueprint asset path — the surface the editor-driving arms (`unreal-mcp`,
`aura-mcp`) exercise and the pure-`claude-p` C++ path does not. If this task
ever fails to distinguish a real Blueprint submission from an empty one (or from a
C++-only edit that produces no `.uasset`), the asset path is broken before any
real asset task can be trusted.

> **Note on the behavior-only rule.** This task deliberately names the concrete
> deliverable (an Actor Blueprint at a fixed path) rather than staying purely
> behavior-only. That is the standard, precedented exception for asset-authoring
> sanity/canary tasks whose whole point *is* producing a specific asset (see
> `canary-umg-button-distinct-name`, which names `Content/UI/WBP_CanaryTrigger`).
> Naming the path lets the verifier load the one asset directly — no asset scan.

## Primary concept

- `ps-bp-class` — Blueprint Class
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/blueprint-class-assets-in-unreal-engine)

Authoring a **new Blueprint Class** (a new `UClass` asset defined without writing
C++, with its own event graph) is the load-bearing concept — it is exactly what
distinguishes this task from the three existing C++ BeginPlay-log tasks. The
`actor-lifecycle` `BeginPlay` hook and the `ps-bp-intro` event-graph/print
fundamentals are exercised as supporting concepts, but the discriminating
requirement the verifier checks is that a **Blueprint** (not C++) carries the
behavior.

## Prompt given to the agent

> This project has no object that announces itself when the game starts. Create a
> new Actor Blueprint asset at `Content/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer`. When gameplay
> begins for a placed instance of it, the object must print the exact message
> `CRAFTBENCH_BP_OK` to the screen and to the engine log, exactly once. After that
> single message it should do nothing further and simply remain in the world. You
> do not need to place it in any level — just author and save the Blueprint asset
> at that path. Make sure it compiles cleanly before considering the work done.

## Workspace state pre-task

- Substrate: `CraftBenchTemplate` third-person C++ template, UE 5.8.
- Pre-existing: standard template content; the default third-person character.
  No asset exists at `Content/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer`
  (the per-task content folder is empty pre-task).
- The agent's writable area includes the asset-writable Content carve-out
  `Content/Tasks/<task-id>/`, so authoring `BP_Announcer` there is permitted.
  `Content/Maps/` is deny-listed — the agent neither can nor needs to place the
  Blueprint in a level (the verifier instantiates it).

Files that **do not exist** (the agent must create):

- `Content/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer.uasset` — an Actor
  Blueprint whose BeginPlay prints `CRAFTBENCH_BP_OK`.

## Verifier specification

The deliverable is one Blueprint at a known path. The fixture **loads that exact
class by path and spawns one instance** in a real PIE world (no asset scan, no
tags), then observes the BeginPlay-window log. A C++-only submission produces no
`.uasset` at that path, so the load fails and the test FAILs — this is what makes
the task a Blueprint-authoring task rather than a generic log task.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for "CraftBenchTemplateEditor Win64 Development"
assert: UnrealBuildTool exits 0 for "CraftBenchTemplate Win64 Development" (Game)
```

The deliverable is content (a Blueprint); L1 confirms the project + Asset Registry
still load and cook-prepare the agent's package cleanly. No new source is expected;
if the agent adds any `.h/.cpp`, the usual "no new shadowed-variable or
deprecated-declarations warnings in agent-touched files" pin applies.

### L2 — PIE-native behavioral trace (`ABpSanityFunctionalTest`)

```text
ABpSanityFunctionalTest::ctor():
    // Register a GLog listener BEFORE any actor exists so the BeginPlay-window
    // emission is captured. Filter the exact token on the channel Print String
    // uses: category = LogBlueprintUserMessages, verbosity floor = Log
    // (UKismetSystemLibrary::PrintString logs there at Log verbosity when
    // bPrintToLog=true, the Print String default — empirically confirmed headless
    // on Windows, see the vendor headless bring-up runbook (not shipped)).
    substring = "CRAFTBENCH_BP_OK"

ABpSanityFunctionalTest::PrepareTest():
    Super::PrepareTest()
    Class = StaticLoadClass(AActor, "/Game/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer.BP_Announcer_C")
    if Class == null:
        FinishTest(Failed, "No Actor Blueprint found at the required path "
                           "/Game/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer; the deliverable was "
                           "not authored (or was authored elsewhere / in C++).")
        return
    World->SpawnActor<AActor>(Class, FTransform::Identity)
        // Spawning into a HasBegunPlay world dispatches BeginPlay immediately;
        // the listener captures it. No World->Tick / Actor->Tick (re-entrant).
    SetCheckpointSchedule({ 0.2 })

ABpSanityFunctionalTest::OnCheckpoint(0, T):
    AssertEqual_Int(
        CapturedTokenCount, 1,
        "Expected exactly one CRAFTBENCH_BP_OK emission from BP_Announcer during "
        "its BeginPlay window; observed N")
    // base class calls FinishTest(Succeeded) after the last checkpoint;
    // SetCheckpointSchedule also arms a TimeLimit so a stuck run FAILs, not hangs.
```

**Pass criteria**: L1 green and L2 observes the token exactly once. The Blueprint
is resolved by its required path `/Game/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer`; the agent must
author it there (named in the prompt).

## Reference solution metadata

- Deliverable: 1 new Actor Blueprint `Content/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer` whose
  EventGraph wires the BeginPlay event to a single Print String node with the
  literal `CRAFTBENCH_BP_OK`. Zero C++.
- Files touched: 1 new `.uasset` (no source edits).
- Senior-dev hours: under 0.1 (about 5 minutes of editor work: create Blueprint
  Class → Actor at the named path, add BeginPlay → Print String, set the string,
  compile + save).

## Anti-gaming notes

1. **C++-only solution (defeats the point of the task).** *Failure mode*: agent
   overrides `BeginPlay` in C++ to emit the token instead of authoring a Blueprint.
   *Defense*: L2 loads the class from `/Game/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer`; a C++ edit
   produces no `.uasset` there, so `StaticLoadClass` returns null → named FAIL. The
   agent cannot place a C++ actor in the deny-listed verifier map either.
2. **Empty / interrupted run (asset never committed).** *Failure mode*: the agent
   reports success after a tool interrupt without saving the Blueprint. *Defense*:
   no asset at the required path → load fails → named FAIL. Prose cannot satisfy it.
3. **Wrong path / name.** *Failure mode*: agent authors the Blueprint somewhere
   other than the named path. *Defense*: the fixture loads the exact required path;
   an asset elsewhere is not found → FAIL. (The path is stated in the prompt, so
   this is a spec-compliance check, not a trick.)
4. **Wrong or mutated message string.** *Failure mode*: agent prints a different or
   misspelled string. *Defense*: the fixture's listener filters the exact substring
   `CRAFTBENCH_BP_OK`; any other string yields count 0 → FAIL.
5. **Multiple emits.** *Failure mode*: agent prints the token in a loop or on Tick
   to satisfy a `>= 1` check. *Defense*: L2 asserts `== 1`, not `>= 1`; repeated
   emission produces `>= 2` → FAIL — mirroring the C++ sanity task's exactly-once
   discipline.

## Hidden invariants

- **"Must be a Blueprint" is enforced by the required asset path.** Because the
  fixture loads `/Game/Tasks/t0-sanity-bp-log-on-beginplay/BP_Announcer` (a `.uasset`), a C++-only solution
  — which produces no such asset — cannot pass; no separate structural layer is
  needed.
- **Verifier owns the placement.** Because the agent cannot edit the deny-listed
  map, the L2 fixture — not the agent — instantiates the loaded Blueprint at
  runtime; this is what lets a "standalone new Blueprint" be graded in PIE without
  granting the agent write access to the level.
- **Accepted residual (T0 scope).** A Blueprint that prints the token from its
  Construction Script rather than BeginPlay would also be captured once (the
  listener is installed before spawn). Distinguishing construction-time from
  BeginPlay-time emission needs graph introspection; for a T0 smoke task this edge
  is accepted and left unguarded (a real task would add an L2I graph check).
