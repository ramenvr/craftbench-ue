---
id: t1-gameplay-tag-gate
substrate: CraftBenchTemplate
set: cpp
tier: T1
capability_bucket: Content Integration
category: gameplay
layers: [L1, L2]
fixtures: ["L_TagGate :: ATagGateFunctionalTest"]
---

# t1-gameplay-tag-gate

Simple-slate T1 (weak-model floor): a repeating log line that runs only while a
named hierarchical state marker is present on the actor. The verifier removes
and re-adds the marker mid-run through an accessor seam the scaffold declares,
so the pass condition is genuinely conditional behavior — not a one-shot log.
One mechanism, few steps: a marker container, one membership query, one timer.
Provenance: coverage gap — `gameplay-tags` was an uncovered Deliverable 1
concept (see `notes.md`).

## Primary concept

- `gameplay-tags` — Gameplay Tags
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/using-gameplay-tags-in-unreal-engine)

Holding a hierarchical tag on an actor, querying membership at runtime, and
reacting to external add/remove is the load-bearing concept: the repeating
emission is deliberately trivial so the tag-gate is the only thing under test.

## Prompt given to the agent

> The project contains an actor placed in the level that keeps a set of
> hierarchical state markers. External code adds and removes markers at any
> time through the two accessor functions the actor's class already declares —
> keep their names and signatures working. When gameplay begins, the marker
> `CraftBench.TagGate.Active` must already be in the actor's set. While that
> marker is present, the actor must write the exact line
> `CRAFTBENCH_TAG_GATE_TICK` to the engine log on the `LogTemp` category at
> `Display` verbosity (or louder), once every 0.5 seconds — the first line
> within 0.6 seconds of gameplay start, and never more than one line per
> half-second. Whenever the marker is removed, the lines must stop: no further
> emission while it is absent. Whenever it is re-added, emission must resume
> within 0.6 seconds and continue at the same period. Solve in C++ on the
> existing class — do not create a Blueprint subclass, do not edit the level,
> and do not edit any test file.

## Workspace state pre-task

Files that **exist** under `Source/CraftBenchTemplate/`:

- `CraftBenchTemplate.Build.cs` — already depends on `Core`, `CoreUObject`,
  `Engine`, `InputCore`, `FunctionalTesting`, `GameplayAbilities`,
  `GameplayTags`, `GameplayTasks`. No edit needed.
- `Tasks/t1-gameplay-tag-gate/TagGateActor.h` / `.cpp` — declares and defines
  `class CRAFTBENCHTEMPLATE_API ATagGateActor : public AActor`. The
  constructor disables tick and adds the `TagGateRoot` identity tag. The
  header declares two accessor functions external code calls by name at
  runtime — `AddGateTag(FGameplayTag)` and `RemoveGateTag(FGameplayTag)`,
  both plain `UFUNCTION()`s — **whose bodies are empty stubs**. The module
  also natively registers the gameplay tag `CraftBench.TagGate.Active`
  (`UE_DEFINE_GAMEPLAY_TAG_COMMENT` in the `.cpp`, extern-declared in the
  header as `TAG_CraftBench_TagGate_Active`). **No marker storage, no query,
  and no timed behavior are implemented.**
- `Content/Maps/t1-gameplay-tag-gate/L_TagGate.umap` — persistent level with
  one placed `ATagGateActor` (tagged `TagGateRoot`) and one placed test
  harness actor.

Files that **do not exist**:

- No marker container member, no `BeginPlay` override, no timer, no Blueprint
  subclass. Solve in C++ on the existing class.
- No test source in the agent's writable path. The test harness lives in a
  separate `CraftBenchTests` module the agent cannot modify.

## Verifier specification

Single PIE-native fixture (`pie-checkpoint-sampling` +
`beginplay-log-capture` primitives), run deterministically
(`-deterministic -FPS=60`) from `Maps/t1-gameplay-tag-gate/L_TagGate.umap`.
The fixture drives the marker through the scaffold's accessor seam by
**reflection** (`FindFunction`/`ProcessEvent` by function name), so it never
needs the agent's class type; the host is resolved by the `TagGateRoot` tag,
never by class.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for both the CraftBenchTemplateEditor and
        CraftBenchTemplate (Game) targets
assert: no new shadowed-variable / deprecated-declarations warnings in
        Source/CraftBenchTemplate/Tasks/t1-gameplay-tag-gate/TagGateActor.{h,cpp}
        (warning diff pinned to agent-authored files only)
```

### L2 — AFunctionalTest behavioral trace (`ATagGateFunctionalTest`)

```text
ATagGateFunctionalTest::ctor():
    // GLog listener installed via OnWorldInitializedActors (pre-BeginPlay so
    // a legal immediate first line is counted), filtered to LogTemp at
    // Display-or-louder, substring "CRAFTBENCH_TAG_GATE_TICK".

ATagGateFunctionalTest::PrepareTest():
    Super::PrepareTest()                            // base sets fixed timestep
    Found = GetAllActorsWithTag(World, "TagGateRoot")
    if Found.Num() != 1:
        FAIL "Expected exactly one TagGateRoot-tagged actor in the level; found N."
    GateTag = RequestGameplayTag("CraftBench.TagGate.Active", ErrorIfNotFound=false)
    if !GateTag.IsValid():
        FAIL "The state marker CraftBench.TagGate.Active is not registered ..."
    for Fn in { AddGateTag, RemoveGateTag }:        // reflection, by name
        if missing:            FAIL "... missing the required accessor function ..."
        if wrong param layout: FAIL "... has an unexpected parameter layout ..."
    SetCheckpointSchedule({ 1.8, 3.6, 5.4 })        // seconds of WORLD game-time
    // Mid-interval times vs the 0.5 s period: no legal implementation races a
    // checkpoint against a scheduled emission.

OnCheckpoint(0, t=1.8):   // marker present since gameplay start
    // 0.5 s period over 1.8 s = 3 emissions (first at 0.5 s), or 4 with a
    // legal immediate first line. Two-sided: spam fails the upper bound.
    assert 3 <= Count <= 4
        else FAIL "At t=1.8s expected 3-4 CRAFTBENCH_TAG_GATE_TICK emissions while the marker is present; observed N."
    invoke RemoveGateTag(GateTag) on the host        // fixture drives the seam
    StopBaseline = Count

OnCheckpoint(1, t=3.6):   // marker absent for 1.8 s
    assert Count - StopBaseline == 0
        else FAIL "At t=3.6s expected no further emissions after the marker was removed at t=1.8s; observed N new."
    invoke AddGateTag(GateTag) on the host
    ResumeBaseline = Count

OnCheckpoint(2, t=5.4):   // marker present again for 1.8 s
    // Resume within 0.6 s then 0.5 s period = 3 emissions (2-4 with margin
    // for a legal immediate resume; two-sided again).
    assert 2 <= Count - ResumeBaseline <= 4
        else FAIL "At t=5.4s expected the emissions to resume after the marker was re-added at t=3.6s (2-4 new); observed N new."
    FinishTest(Succeeded)
```

**Pass criteria**: L1 green and all three checkpoints green. **Robust
identity**: host lookup by the `TagGateRoot` tag and accessor invocation by
reflection — subclassing or even replacing the scaffold class does not
penalize the agent as long as the tag, the accessor names/signatures, and the
behavior survive.

## Reference solution metadata

- LOC range: 20-40 (one `FGameplayTagContainer` member, one `BeginPlay`
  override that seeds the marker and starts a 0.5 s looping timer, one
  `HasTag`-gated `UE_LOG` in the timer callback, two one-line accessor bodies).
- Files touched: 2 (the pre-existing header + cpp; no new files, no `.uasset`
  edits, no `.Build.cs` edits).
- Senior-dev time: 30-60 minutes.

## Anti-gaming notes

1. **Unconditional repeating log (marker ignored).** *Failure mode*: agent
   starts a looping timer that always emits, never consulting the marker set.
   *Defense*: the fixture removes the marker via the accessor at t=1.8s;
   checkpoint 1 asserts zero new emissions (`expected no further emissions
   after the marker was removed`) — an unconditional loop produces 3-4 new
   lines there and FAILs by name.
2. **One-shot / burst emission instead of a period.** *Failure mode*: agent
   logs once (or a fixed burst) at startup to satisfy a presence check.
   *Defense*: checkpoint 0 requires 3-4 emissions across 1.8 s AND checkpoint
   2 requires 2-4 more after the fixture re-adds the marker; a startup-only
   emitter fails at least one count band.
3. **Per-frame spam to clear lower bounds.** *Failure mode*: agent emits every
   tick so any `>= N` gate passes. *Defense*: both count gates are two-sided;
   at the deterministic 60 FPS a per-frame emitter produces ~108 lines by
   t=1.8s and FAILs the `3-4` upper bound.
4. **Dead accessor stubs (external changes never take effect).** *Failure
   mode*: agent implements the timer + a private flag but leaves the scaffold
   accessors as no-ops (or deletes them). *Defense*: deleted/reshaped
   accessors FAIL at the prepare-time named checks (`missing the required
   accessor function` / `unexpected parameter layout`); no-op bodies leave the
   emission unconditional, which FAILs checkpoint 1 exactly like note 1 — and
   a stop-forever hack instead FAILs checkpoint 2's resume band.
5. **Test disabling.** *Failure mode*: agent edits `ATagGateFunctionalTest` or
   the map to lower the bar. *Defense*: `Source/CraftBenchTests/` and
   `Content/Maps/` are outside the sandbox's writable set (exit-4 reject),
   and the runner materializes the graded substrate from git HEAD, so an
   on-disk edit never reaches the grade; human review gates
   any committed change.

## Hidden invariants

None — every gate in this task is disclosed in the prompt (period, first-line
window, exact token/category/verbosity, stop-on-remove, resume-on-re-add).
Accepted residuals, stated honestly:

- **Fixture source is readable in the scratch (whole-suite residual).** The
  agent can read `Source/CraftBenchTests/` in its working copy (it only cannot
  *modify* what gets graded), so the checkpoint times and the remove/re-add
  schedule are discoverable. A submission could hardcode a time-based emission
  schedule that replays exactly the windows this fixture toggles, with no
  marker logic at all. This is the standard accepted residual of every task in
  the suite (verifier constants are visible); it is overfit to fixture
  constants, not a defeat of the marker gate, and any change to the schedule
  breaks it.
- **Container type is not asserted.** L2 observes behavior only: the
  `FGameplayTag`-typed accessor seam guarantees the agent handles gameplay-tag
  *values*, but a solution storing them in (say) a `TSet<FGameplayTag>` rather
  than an `FGameplayTagContainer` passes identically. No L5/AST layer is
  implemented in the runner; accepted at T1.
- **Framerate coupling is not probed.** The verifier always runs
  `-deterministic -FPS=60`; a frame-counter implementation (30 frames per
  emission) passes even though it is not framerate-independent. `fps_legs`
  was deliberately omitted to keep the simple-slate cost down; see `notes.md`
  for the hardening option.
- **Period phase is bounded, not measured.** The gates are per-window counts
  (two-sided), not per-emission timestamps; a jittery emitter with correct
  window counts passes.
