---
id: t1-extraction-volume-per-actor-trigger
substrate: CraftBenchTemplate
set: cpp
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_ExtractionVolume :: AExtractionVolumeFunctionalTest"]
---

# t1-extraction-volume-per-actor-trigger

A per-individual extraction trigger: a zone that fires its extraction event
exactly once for each distinct actor that enters it — never on startup, never
twice for the same individual, once each for different individuals. Drawn from
an earlier internal task list (not shipped) ("Basic volume class implementation", CSV row R3).
The source row's verification cell is written as code-shape checks ("uses AVolume as
the base", "uses `NotifyActorBeginOverlap` override", "doesn't use AddDynamic")
— **all three are cut**: no source-inspection lane exists (L5 is defined-only,
unimplemented), and repo law grades observable behavior, not implementation
pattern (Hard Rule #2). The behavioral core the source row describes — "triggers
endgame logic for an extraction match for each individual that touches it" —
is what this task grades, with the endgame side effect abstracted to an exact
marker line (the substrate ships no endgame system).

## Primary concept

- `ps-collision-overlap` — Collision overlap events
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine)

Reacting to runtime volume entry with per-entrant state is the load-bearing
concept: the zone must respond to each distinct actor's first overlap, not to
its own lifecycle and not to raw overlap-event counts.

## Prompt given to the agent

> The level contains a placed zone actor (tagged `ExtractionZone`) with a
> box-shaped detection volume. Turn it into the level's extraction point:
> whenever any other actor enters the volume, the zone must emit the exact log
> line `CRAFTBENCH_EXTRACTION_OK` to the engine log on the `LogTemp` category
> at `Display` verbosity (or louder) — exactly once per distinct individual,
> at the moment that individual first enters. The same individual leaving and
> entering again must not produce another line. Two different individuals must
> produce two lines, one each. Before anything has entered the zone, it must
> not emit the line at all. Solve in C++ on the existing class — do not create
> a Blueprint subclass, do not edit the level, and do not edit any test file.

## Workspace state pre-task

Files that **exist** under `Source/CraftBenchTemplate/`:

- `CraftBenchTemplate.Build.cs` — already depends on `Core`, `CoreUObject`,
  `Engine`, `InputCore`, `FunctionalTesting`. No edit needed.
- `Tasks/t1-extraction-volume-per-actor-trigger/ExtractionZoneActor.h` / `.cpp`
  — declares and defines
  `class CRAFTBENCHTEMPLATE_API AExtractionZoneActor : public AActor`. The
  constructor disables tick, creates a query-only `UBoxComponent` ("ZoneVolume",
  half-extent 200x200x100) as the root with overlap events enabled and Overlap
  responses to all channels, and adds the `ExtractionZone` tag. **No overlap
  handling, per-entrant bookkeeping, or logging is provided.**
- `Content/Maps/t1-extraction-volume-per-actor-trigger/L_ExtractionVolume.umap`
  — persistent level with one placed `AExtractionZoneActor` (tagged
  `ExtractionZone`) and one placed test harness actor.

Files that **do not exist**:

- No begin-overlap handling, no per-entrant record, no logging, no Blueprint
  subclass, no level edits. Solve in C++ on the existing class.
- No test source in the agent's writable path. The test harness lives in a
  separate `CraftBenchTests` module the agent cannot read or modify.

## Verifier specification

The test runs in PIE from
`Maps/t1-extraction-volume-per-actor-trigger/L_ExtractionVolume.umap` at a
fixed deterministic step (`-deterministic -FPS=60`).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for both the Editor and Game targets
assert: no new shadowed-variable / deprecated-declarations warnings in
        Source/CraftBenchTemplate/Tasks/t1-extraction-volume-per-actor-trigger/
        ExtractionZoneActor.{h,cpp}
        (warning diff pinned to agent-authored files only)
```

### L2 — AFunctionalTest behavioral trace

```text
AExtractionVolumeFunctionalTest::PrepareTest():
    // Identity by project tag, never by C++ class name — the agent may
    // legitimately subclass AExtractionZoneActor.
    Found = GetAllActorsWithTag(World, "ExtractionZone")
    AssertEqual_Int(Found.Num(), 1, "Exactly one ExtractionZone actor")
    // GLog listener installed in OnWorldInitializedActors (before BeginPlay),
    // filtered to LogTemp / Display, substring "CRAFTBENCH_EXTRACTION_OK".
    // Two probe actors A and B spawned parked ~5000 units outside the zone.
    SetCheckpointSchedule({ 0.5, 1.5, 2.0, 2.5, 3.5 })

checkpoint 0 (t≈0.5s, after BeginPlay so any overlap binding is in place):
    AssertEqual_Int(MarkerCount, 0, "NOT be logged before any entry")
    MoveProbe(A, inside-the-zone)      // teleport + forced overlap update

checkpoint 1 (t≈1.5s):
    AssertEqual_Int(MarkerCount, 1, "exactly one ... after the first entrant")
    MoveProbe(A, parking)              // A exits; the re-entry waits for cp2

checkpoint 2 (t≈2.0s, no graded count assert):
    MoveProbe(A, inside-the-zone)      // same-individual re-entry, on its own
                                       // engine frame — never a same-frame
                                       // out-then-in the engine could coalesce

checkpoint 3 (t≈2.5s):
    AssertEqual_Int(MarkerCount, 1, "re-entering to add no new emission")
    MoveProbe(B, inside-the-zone)      // second distinct individual

checkpoint 4 (t≈3.5s):
    AssertEqual_Int(MarkerCount, 2, "after a second distinct individual entered")
    FinishTest(Succeeded)
```

**Pass criteria**: both L1 and L2 green. **Robust identity**: lookup by the
`ExtractionZone` tag, never by class name.

## Reference solution metadata

- LOC range: ~15-25 LOC (a `NotifyActorBeginOverlap` override — or an
  equivalent component-event binding — plus a per-entrant set and one
  `UE_LOG`).
- Files touched: 2 (the pre-existing header + cpp; no new files).
- Senior-dev minutes: under 30.

## Anti-gaming notes

1. **Log on BeginPlay instead of on entry.** *Failure mode*: agent emits the
   marker unconditionally in `BeginPlay` to satisfy a `>= 1` check. *Defense*:
   checkpoint 0 runs after BeginPlay and asserts `MarkerCount == 0` before any
   probe enters; a BeginPlay-time log fails there.
2. **Raw event counting (no per-individual dedupe).** *Failure mode*: agent
   logs on every begin-overlap, passing the single-entry check. *Defense*:
   the fixture walks the SAME probe out (checkpoint 1) and back in (checkpoint
   2, a separate engine frame) and checkpoint 3 asserts the count is still
   exactly 1; an undeduped handler produces 2 and fails.
3. **Global one-shot latch.** *Failure mode*: agent logs only the first entry
   ever (a single bool), satisfying "once" checks cheaply. *Defense*:
   checkpoint 3 sends a SECOND distinct probe in and checkpoint 4 asserts the
   count reaches exactly 2; a global latch stays at 1 and fails.
4. **Wrong log category/verbosity.** *Failure mode*: agent logs to a custom
   category or a quieter verbosity to hide the literal. *Defense*: the listener
   is filtered to `LogTemp` at `Display`-or-louder; other channels are not
   counted.
5. **Test disabling.** *Failure mode*: agent edits
   `AExtractionVolumeFunctionalTest` to lower the bar. *Defense*:
   `CraftBenchTests` is outside the writable workspace and graded from git
   HEAD — the runner materializes the substrate from HEAD, so an on-disk edit
   never reaches the grade, and human review gates any committed
   change to it.
