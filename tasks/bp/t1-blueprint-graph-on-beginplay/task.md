---
id: t1-blueprint-graph-on-beginplay
substrate: CraftBenchTemplate
set: bp
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_GraphMath :: AGraphMathFunctionalTest"]
---

# t1-blueprint-graph-on-beginplay

Simple-slate task (weak-model floor): author one Actor Blueprint that, at start
of play, reads two of its own editable numeric values, adds them, and prints one
exactly-formatted line. One graph, two variable reads, one arithmetic node, one
string build, one print — deliberately few steps so a weak model can pass and
the model-comparison leaderboard gains resolution at the bottom end. The
verifier still has teeth: the fixture overrides both per-instance values
**before** gameplay begins (to constants that differ from the scaffold
defaults), so a hardcoded print of the default-derived sum FAILs — only a graph
that actually reads the instance's current values passes. An empty submission
FAILs at a named assertion (no asset at the required path).

> **Note on the behavior-only rule.** Like `t0-sanity-bp-log-on-beginplay`,
> this task names its concrete deliverable (an Actor Blueprint at a fixed path,
> derived from a named pre-existing actor type) rather than staying purely
> behavior-only. That is the standard, precedented exception for
> asset-deliverable tasks whose point *is* producing a specific asset; the
> scaffold type and its two property names are workspace-state inputs, not
> solution-shape instructions.

## Primary concept

- `ps-bp-intro` — Introduction to Blueprints (variables, execution flow,
  event-graph fundamentals)
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/introduction-to-blueprints-visual-scripting-in-unreal-engine)

Reading Blueprint-exposed variables in an event graph and flowing them through
an arithmetic + string-build + print chain is the load-bearing concept: the
task is exactly "wire real variable reads through a graph". Authoring the
Blueprint Class itself (`ps-bp-class`) is exercised as a supporting concept but
is already the discriminating requirement of `t0-sanity-bp-log-on-beginplay`;
what T1 adds here is dataflow through the graph, enforced by the pre-BeginPlay
value override.

## Prompt given to the agent

> The project provides a placeable base actor for this task (its source lives
> in the task's workspace folder) that carries two per-instance editable
> whole-number values: `BaseValue` (default 7) and `BonusValue` (default 5).
> Create a new Actor Blueprint asset at
> `Content/Tasks/t1-blueprint-graph-on-beginplay/BP_GraphMath` based on that
> provided actor. When gameplay begins for an instance of your Blueprint, it must print
> one line to the screen and to the engine log in exactly this format:
> `CRAFTBENCH_GRAPH_TOTAL=<total>`, where `<total>` is the sum of that
> instance's two values at the moment gameplay begins, written as a plain whole
> number with no spaces or decimals (with the defaults the line would read
> `CRAFTBENCH_GRAPH_TOTAL=12`). The two values can be changed on any individual
> instance before its gameplay begins, and the checker does exactly that — so
> the printed total must come from reading the instance's actual current
> values, not from precomputing the default sum. Print the line exactly once
> per instance; after that single line the object does nothing further. You do
> not need to place the Blueprint in any level — author it at that path, make
> sure it compiles cleanly, and save it.

## Workspace state pre-task

Files that **exist**:

- `Source/CraftBenchTemplate/Tasks/t1-blueprint-graph-on-beginplay/GraphMathActor.h`
  / `.cpp` — declares `AGraphMathActor : public AActor` with two per-instance
  editable `int32` values, `BaseValue = 7` and `BonusValue = 5` (readable from
  Blueprint graphs), and a constructor that disables tick and stamps the
  `GraphMathRoot` tag. **No lifecycle overrides, no behavior.**
- `Content/Maps/t1-blueprint-graph-on-beginplay/L_GraphMath.umap` — persistent
  level containing the placed L2 fixture actor plus stock environment actors
  (committed binary, authored 2026-08-11).
- Nothing under `Content/Tasks/t1-blueprint-graph-on-beginplay/` — the per-task
  content folder is empty pre-task.

The agent's writable area includes the asset carve-out `Content/Tasks/<task-id>/`,
so authoring `BP_GraphMath` there is permitted. `Content/Maps/` is deny-listed —
the agent neither can nor needs to place the Blueprint in a level (the verifier
spawns it).

Files that **do not exist** (the agent must create):

- `Content/Tasks/t1-blueprint-graph-on-beginplay/BP_GraphMath.uasset` — an
  Actor Blueprint derived from `AGraphMathActor` whose start-of-play behavior
  prints `CRAFTBENCH_GRAPH_TOTAL=<BaseValue + BonusValue>` exactly once.

## Verifier specification

The deliverable is one Blueprint at a known path. The fixture — the
`beginplay-log-capture` primitive in the `t0-sanity-bp-log-on-beginplay`
idiom — loads that exact class by path, spawns one instance in a real PIE
world, and observes the BeginPlay-window log. What this task adds to the t0
idiom is the **pre-BeginPlay per-instance value override**: in
`FWorldDelegates::OnWorldInitializedActors` (the repo's documented
pre-BeginPlay hook) the fixture installs the log listener, spawns the agent's
Blueprint into the not-yet-begun world, and sets `BaseValue=137`,
`BonusValue=42` on the instance. BeginPlay then fires with the overrides in
place, so only a graph that reads the current values can print the expected
line.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for "CraftBenchTemplateEditor Win64 Development"
assert: UnrealBuildTool exits 0 for "CraftBenchTemplate Win64 Development" (Game)
```

The deliverable is content (a Blueprint); L1 confirms the project + Asset
Registry still load the agent's package cleanly. If the agent adds any
`.h/.cpp`, the usual "no new shadowed-variable or deprecated-declarations
warnings in agent-touched files" pin applies.

### L2 — PIE-native behavioral trace (`AGraphMathFunctionalTest`)

```text
AGraphMathFunctionalTest::ctor():
    bind FWorldDelegates::OnWorldInitializedActors -> OnWorldActorsInitialized

OnWorldActorsInitialized(Params):            // PRE-BeginPlay, this world only
    install GLog device: category = LogBlueprintUserMessages, verbosity floor
        = Log (Print String's default log routing), counting
        (a) lines containing the marker prefix "CRAFTBENCH_GRAPH_TOTAL="
        (b) lines containing the exact line   "CRAFTBENCH_GRAPH_TOTAL=179"
    Class = StaticLoadClass(AActor, "/Game/Tasks/t1-blueprint-graph-on-beginplay/BP_GraphMath.BP_GraphMath_C")
    if Class == null:            record AssetMissing        // named FAIL later
    elif !Class->IsChildOf(AGraphMathActor): record WrongParent
    else:
        Instance = SpawnActor(Class)         // world not begun play ->
                                             // BeginPlay deferred to world start
        Instance->BaseValue  = 137           // pre-BeginPlay override
        Instance->BonusValue = 42
        record Ok

AGraphMathFunctionalTest::PrepareTest():
    Super::PrepareTest()
    // fallback if the delegate never fired: SpawnActorDeferred + set values +
    // FinishSpawning keeps the override ahead of BeginPlay
    AssetMissing -> FinishTest(Failed, "No Actor Blueprint found at the required path ...")
    WrongParent  -> FinishTest(Failed, "... does not derive from the task actor type ...")
    SpawnFailed  -> FinishTest(Failed, "Failed to spawn an instance of ...")
    Ok           -> SetCheckpointSchedule({ 0.3 })

AGraphMathFunctionalTest::OnCheckpoint(0, T):
    Prefix = count of "CRAFTBENCH_GRAPH_TOTAL=" lines; Exact = count of
             "CRAFTBENCH_GRAPH_TOTAL=179" lines
    Exact == 1 && Prefix == 1 -> FinishTest(Succeeded)
    Prefix == 0 -> Failed "observed none - the graph did not print the required line"
    Exact == 0  -> Failed "the printed total does not reflect the instance's current values"
    else        -> Failed "must be printed exactly once; observed N"
```

**Pass criteria**: L1 green and L2 observes the exact line
`CRAFTBENCH_GRAPH_TOTAL=179` exactly once, with no other marker-prefixed lines.
The Blueprint is resolved by its required path (named in the prompt); identity
is by asset path + parent-class check, no tag scan (verifier owns placement).

## Reference solution metadata

- Deliverable: 1 new Actor Blueprint
  `Content/Tasks/t1-blueprint-graph-on-beginplay/BP_GraphMath` (parent
  `AGraphMathActor`) whose EventGraph wires BeginPlay -> Get BaseValue / Get
  BonusValue -> integer Add -> string build ("CRAFTBENCH_GRAPH_TOTAL="
  appended with the int) -> one Print String. Zero C++.
- Files touched: 1 new `.uasset` (no source edits).
- Senior-dev hours: under 0.25 (about 10 minutes of editor work: create the
  Blueprint at the named path with the named parent, wire ~5 nodes, compile,
  save).

## Anti-gaming notes

1. **Hardcoded default-derived print.** *Failure mode*: the agent precomputes
   `7 + 5` and prints the constant line `CRAFTBENCH_GRAPH_TOTAL=12` (or any
   other literal), never reading the variables. *Defense*: the fixture sets
   `BaseValue=137` / `BonusValue=42` on the tested instance **before** its
   BeginPlay runs (pre-BeginPlay world-init window), and the checkpoint
   requires the exact line `CRAFTBENCH_GRAPH_TOTAL=179`; a constant print hits
   the named FAIL `the printed total does not reflect the` instance's current
   values (GraphMathFunctionalTest.cpp:256).
2. **Empty / C++-only submission.** *Failure mode*: nothing is authored, or the
   behavior is written in C++ with no `.uasset` produced. *Defense*: the fixture
   loads the exact required path; a null class is the named FAIL
   `No Actor Blueprint found at the required path` (GraphMathFunctionalTest.cpp:203).
3. **Repeated printing (Tick / loop / timer).** *Failure mode*: the agent
   prints the line every frame to satisfy a `>= 1` check. *Defense*: the
   checkpoint asserts the marker count `== 1`, not `>= 1`; two or more
   emissions hit the named FAIL `must be printed exactly once`
   (GraphMathFunctionalTest.cpp:265).
4. **Plain-Actor Blueprint with look-alike variables.** *Failure mode*: the
   agent authors a Blueprint at the right path that does not derive from
   `AGraphMathActor`, giving it its own `BaseValue`/`BonusValue`. The fixture
   could not override those, so a default-sum print might slip through.
   *Defense*: an explicit `IsChildOf(AGraphMathActor)` gate FAILs it by name —
   `does not derive from the task actor type` (GraphMathFunctionalTest.cpp:211)
   — and the required parentage is stated in the prompt, so this is
   spec-compliance, not a trick.
5. **Graph-side mutation of the inputs.** *Failure mode*: the agent's graph
   overwrites the two values (e.g. sets both to constants) before printing, so
   the "read" is of its own planted numbers. *Defense*: both properties are
   exposed to Blueprint as read-only — the generated class has no setter nodes
   for them — and any printed total other than 179 fails the exact-line gate
   (GraphMathFunctionalTest.cpp:255-257).

## Hidden invariants

- **Construction-time printing FAILs (tightened vs the t0 residual).** The
  fixture's override lands *after* the instance is constructed but *before*
  BeginPlay, so a print fired at construction time can only see the defaults
  (total 12) — it fails the exact-line gate; and a construction-time print
  *plus* a BeginPlay print trips the exactly-once gate. The t0 sanity task had
  to accept construction-script emission as a residual; here the value
  override closes it without graph introspection.
- **Verifier owns the placement.** The agent cannot edit the deny-listed map;
  the L2 fixture instantiates the loaded Blueprint at runtime, which is what
  lets a standalone new Blueprint be graded in PIE without granting the agent
  level write access.

### Accepted residuals (stated, not defended)

- **Verifier-owned fixture source is readable in the agent's scratch** — a
  suite-wide residual, not specific to this task: the override constants
  (137/42) and the expected line (`...=179`) are visible to an agent that
  reads `Source/CraftBenchTests/` (readable, not writable). An agent could
  hardcode 179 after reading the fixture. Accepted for the whole suite: the
  graded substrate is materialized from git HEAD and the fixture cannot be
  edited, but its constants are not secrets. (Per-run randomization of the
  override pair is the known hardening if this residual ever shows up in the
  wild; recorded in `notes.md` as a calibration TODO.)
- **A C++ carrier under a thin Blueprint wrapper passes.** An agent may write
  a C++ subclass of `AGraphMathActor` whose BeginPlay does the read/sum/print
  and author `BP_GraphMath` as a graph-empty Blueprint child of it. The
  observable contract (real reads of the current values, exact line, exactly
  once, a Blueprint asset at the path) is fully met, so this passes —
  consistent with the bp-basket law that outcomes, not mechanisms, are graded,
  and with the same residual accepted on `t0-sanity-bp-log-on-beginplay`.
  Closing it would need L2I graph introspection, out of scope for a T1
  simple-slate task.
- **"To the screen" is not asserted.** The graded leg runs headless
  (`-nullrhi`); only the engine-log side of the print is observable. The
  prompt phrases screen+log as one action (Print String's defaults do both),
  so the log assertion is the graded surface.
