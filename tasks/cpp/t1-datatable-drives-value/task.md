---
id: t1-datatable-drives-value
substrate: CraftBenchTemplate
set: cpp
tier: T1
capability_bucket: Content, Data, Assets
category: gameplay
layers: [L1, L2]
fixtures: ["L_DataDriven :: ADataDrivenFunctionalTest"]
---

# t1-datatable-drives-value

A runtime value configured from an externally authored data record (looked up by
row name) rather than from a value written in code — the data-driven-gameplay
core. This is an **asset-bearing** task: the substrate ships a DataTable the
agent must read. Adapted from the the internal design corpus v2 corpus (source: Epic's
Data-Driven Gameplay Elements documentation).

## Primary concept

- `ps-data-driven-gameplay` — Data-Driven Gameplay
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/data-driven-gameplay-elements-in-unreal-engine)

The load-bearing behavior is reading a numeric field from a named row of an
external data record and applying it at runtime — retuning the record (without
touching code) changes the applied value.

## Prompt given to the agent

> The project contains an actor placed in the level and a table of tunable
> records, each identified by a row name; the table is already assigned to the
> actor. When gameplay begins, the actor must look up the record named `Default`
> and copy that record's numeric field onto its own public `ConfiguredValue`
> setting (which starts at the sentinel `-1`), so other gameplay code can read
> it. The value must come from the record — reading the record must be what sets
> `ConfiguredValue`, never a number written in code. Solve in C++ on the existing
> class — do not edit the data table and do not edit any test file.

## Workspace state pre-task

Files/assets that **exist**:

- `Source/CraftBenchTemplate/Tasks/t1-datatable-drives-value/DataDrivenActor.h` /
  `.cpp` — `class CRAFTBENCHTEMPLATE_API ADataDrivenActor : public AActor`, tagged
  `DataDrivenRoot`, with a public `float ConfiguredValue = -1` and an assigned
  `UDataTable* TuningTable`. **No row lookup is implemented.**
- `Source/CraftBenchTemplate/Tasks/t1-datatable-drives-value/TuningRow.h` — the
  row struct `FTuningRow : FTableRowBase` with a `float TunedValue` field (read
  it; do not edit it).
- `Content/Data/DT_Tuning` — the tuning record (row type `FTuningRow`) with a row
  named `Default`. Assigned to the placed actor's `TuningTable`. Read-only.
- `Content/Maps/t1-datatable-drives-value/L_DataDriven.umap` — the placed actor
  plus a test harness actor.

Files/assets that **do not exist**: the row-lookup-and-apply wiring. Add it in
C++ on the existing class.

## Verifier specification

The test runs in PIE from
`Maps/t1-datatable-drives-value/L_DataDriven.umap` at a fixed deterministic step
(`-deterministic -FPS=60`). The substrate `DT_Tuning` (with its undisclosed
`Default.TunedValue`) and the map are materialized headlessly by
committed binaries (the scaffolder scripts were retired 2026-07; the
committed `.umap`/`.uasset` are the only source).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for both the Editor and Game targets
assert: no new shadowed-variable / deprecated-declarations warnings in
        Source/CraftBenchTemplate/Tasks/t1-datatable-drives-value/DataDrivenActor.{h,cpp}
```

### L2 — AFunctionalTest behavioral trace

```text
ADataDrivenFunctionalTest::PrepareTest():
    Found = GetAllActorsWithTag(World, "DataDrivenRoot")
    AssertEqual_Int(Found.Num(), 1, "Exactly one DataDrivenRoot actor")
    SetCheckpointSchedule({ 1.0, 2.0 })

OnCheckpoint reads the host's ConfiguredValue float UPROPERTY (by reflection):
    idx 0 (t=1.0): AssertNear(ConfiguredValue, DT_Tuning.Default.TunedValue, 0.01)
    idx 1 (t=2.0): AssertNear(ConfiguredValue, ...)  // stable
    FinishTest(Succeeded)
```

**Pass criteria**: both L1 and L2 green. **Robust identity**: the actor is found
by the `DataDrivenRoot` tag; `ConfiguredValue` is read by UPROPERTY name so a
subclass still works.

## Reference solution metadata

- LOC range: ~8-14 LOC (a `BeginPlay` override that `FindRow<FTuningRow>("Default")`
  on `TuningTable` and assigns `TunedValue` to `ConfiguredValue`).
- Files touched: 2 (the pre-existing header + cpp).
- Senior-dev minutes: 15-30.

## Anti-gaming notes

1. **Hardcoded constant.** *Failure mode*: agent writes a number to
   `ConfiguredValue` in code instead of reading the record. *Defense*: the
   `Default` row's `TunedValue` is never disclosed in the prompt; only a real
   lookup produces the exact expected value, and the assertion is tight (±0.01
   on a non-round value).
2. **Empty override.** *Failure mode*: agent overrides `BeginPlay` but never
   reads the table; L1 passes. *Defense*: L2 asserts `ConfiguredValue` equals the
   record value; an unread table leaves the `-1` sentinel and fails.
3. **Reads a self-authored table.** *Failure mode*: agent creates its own table
   with a guessed value. *Defense*: the placed actor's `TuningTable` is wired to
   the substrate `DT_Tuning`; a `FindRow` on the assigned table reads the real
   record, and the expected value is keyed to that record.
4. **Wrong property.** *Failure mode*: agent renames or shadows `ConfiguredValue`.
   *Defense*: the fixture reads the `ConfiguredValue` UPROPERTY by name; if it is
   absent the test fails with a clear message.
5. **Test disabling.** *Failure mode*: agent edits the fixture. *Defense*:
   `CraftBenchTests` is outside the writable workspace and the runner
   materializes it from git HEAD (an on-disk edit never reaches the grade);
   committed changes are review-gated on commit.
