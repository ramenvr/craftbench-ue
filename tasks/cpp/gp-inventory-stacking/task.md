---
id: gp-inventory-stacking
substrate: CraftBenchTemplate
set: cpp
tier: T2
capability_bucket: Content Integration
category: gameplay
layers: [L1, L2]
fixtures: ["L_InventoryStacking :: AInventoryStackingFunctionalTest"]
---

# gp-inventory-stacking

Port of the **g2-1 "Inventory"** eval prompt onto the UE 5.7 CraftBenchTemplate
substrate. Probes `ps-data-driven-gameplay` (data-table-driven gameplay): an
inventory whose per-type stack limits come from external data, with slot-aware
add/remove math. The original g2-1 prompt named a component and a data table and
targeted `/Game/G2/1/`; this port restates the same behavior **behavior-only**
and grades it deterministically in headless PIE.

Determinism strategy (the reason this is gateable without input/UI): the
substrate ships the host as an actor with a **fixed C++ operation contract**
(`AddItem` / `RemoveItem` / `GetTotalQuantity` / `GetOccupiedSlotCount`, empty
stubs) — exactly the `gp-modular-attach` entry-point pattern. The agent fills in
the bodies; the L2 fixture resolves the host by tag, drives the operations on a
checkpoint schedule, and asserts the evolving (total, occupied-slot) invariants.
No internal variable is read; only the contract's return values are observed.

## Primary concept

- `ps-data-driven-gameplay` — Data Driven Gameplay Elements
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/data-driven-gameplay-elements-in-unreal-engine)

The load-bearing concept is **externally-stored, data-driven configuration**:
the per-type maximum stack size is not hard-coded in the inventory logic — it is
read from the data the project provides, so two item types with different caps
behave differently from the same code path. The slot/stack bookkeeping
(fill-partial-first, spill-at-cap, free-on-empty) is the supporting math the
verifier samples.

## Prompt given to the agent

> The project provides an actor placed in the level that is meant to hold a
> stackable-item inventory of a fixed number of slots. The set of valid item
> types, and the maximum number of units of each type that may occupy a single
> slot, are defined by external data the project already ships and the actor can
> read — do not hard-code the per-type limits. Implement the inventory
> operations the actor exposes:
>
> - **Add** N units of an item type: fill existing partial stacks of that same
>   type first, then occupy empty slots, and never let any single slot hold more
>   than that type's maximum stack size. Report whether all N units fit.
> - **Remove** N units of an item type: take units from that type's stacks, and
>   free any slot that reaches zero units.
> - **Report** the total units of a given item type currently held across all
>   slots, and the number of slots currently occupied (holding ≥1 unit).
>
> Worked example of the required stacking math (for a type whose maximum stack
> size is M): adding M+3 units to an empty inventory occupies 2 slots holding M
> and 3; adding 4 more of the same type fills the partial stack to M-? — i.e.
> the second slot becomes 7 — still 2 slots; a type with a *different* maximum
> stack size must spill at *its* limit, not the first type's. Solve in C++ on
> the existing class; the operation signatures are fixed.

## Workspace state pre-task

Files that **exist** under `Source/CraftBenchTemplate/`:

- `CraftBenchTemplate.Build.cs` — `PublicDependencyModuleNames` already includes
  `Core`, `CoreUObject`, `Engine`, `InputCore`, `FunctionalTesting`. No edit
  needed (Data Table / row-struct types live in `Engine`/`CoreUObject`).
- `InventoryItemRow.h` — a substrate-provided row struct
  `struct FInventoryItemRow : public FTableRowBase` with an `int32 MaxStackSize`
  field (the per-type stack cap). The agent does not edit this.
- `InventoryHostActor.h` / `InventoryHostActor.cpp` — declares
  `class CRAFTBENCHTEMPLATE_API AInventoryHostActor : public AActor`. The
  constructor tags it `InventoryRoot` (the verifier resolves the host by this
  tag, never by class) and holds a reference to the project's item-type data
  table (assigned on the placed instance). It declares the **fixed** operation
  contract as empty stubs — `bool AddItem(FName ItemType, int32 Count)` →
  returns false; `int32 RemoveItem(FName ItemType, int32 Count)` → returns 0;
  `int32 GetTotalQuantity(FName ItemType) const` → returns 0;
  `int32 GetOccupiedSlotCount() const` → returns 0. No inventory logic. The
  agent implements the bodies in C++; the header signatures are fixed.
- `Content/Data/DT_InventoryItemTypes` — the project's item-type data table
  (row struct `FInventoryItemRow`) with at least the rows `Stone`
  (`MaxStackSize` 10) and `Wood` (`MaxStackSize` 20). Assigned to the placed
  host's data-table reference.
- `Maps/L_InventoryStacking.umap` — persistent level with one placed
  `AInventoryHostActor` (tag `InventoryRoot`, data-table reference set) and one
  placed `AInventoryStackingFunctionalTest`. The runner opens it explicitly as a
  positional argument.
- `AInventoryStackingFunctionalTest` lives in the verifier-only `CraftBenchTests`
  editor module; the agent cannot read or modify it.

Files that **do not exist**:

- No inventory implementation, no Blueprint subclass, no level edits. Solve in
  C++ in `InventoryHostActor.cpp` (the four operation signatures are fixed; do
  not change them). The per-type caps must be read from the provided data table,
  not hard-coded.

## Verifier specification

The test runs in a real PIE world via the standard runner invocation. The
fixture resolves the host by tag, then drives the operation contract at a
checkpoint schedule and asserts the (total, occupied-slot) invariants after each
operation. Item-type caps are `Stone`=10, `Wood`=20 (from the shipped data
table), so a solution that hard-codes a single cap fails one of the two types.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for "CraftBenchTemplateEditor <Platform>
        Development" target
assert: no new shadowed-variable or deprecated-declarations warnings in
        Source/CraftBenchTemplate/InventoryHostActor.{h,cpp}
```

### L2 — AFunctionalTest behavioral trace

```text
AInventoryStackingFunctionalTest::PrepareTest():
    TArray<AActor*> Found
    UGameplayStatics::GetAllActorsWithTag(World, FName("InventoryRoot"), Found)
    AssertEqual_Int(Found.Num(), 1, "Exactly one InventoryRoot")
    Host = Cast resolution via the substrate header (AInventoryHostActor*)
    SetCheckpointSchedule({0.5, 1.5, 2.5, 3.5, 4.5})

AInventoryStackingFunctionalTest::OnCheckpoint():
    t=0.5: Host->AddItem("Stone", 7) == true
           Total("Stone")==7 ; OccupiedSlots()==1        // partial single slot
    t=1.5: Host->AddItem("Stone", 2) == true
           Total("Stone")==9 ; OccupiedSlots()==1        // FILLED the partial, no new slot
    t=2.5: Host->AddItem("Stone", 8)
           Total("Stone")==17 ; OccupiedSlots()==2       // spill at cap 10 -> 10 + 7
    t=3.5: Host->AddItem("Wood", 25)
           Total("Wood")==25 ; Total("Stone")==17        // Wood caps at 20, not 10
           OccupiedSlots()==4                            // Stone:2 (10,7) + Wood:2 (20,5)
    t=4.5: Host->RemoveItem("Stone", 15) == 15
           Total("Stone")==2 ; OccupiedSlots()==3        // Stone collapses to 1 slot; Wood:2
           // base FinishTest(Succeeded) after the last checkpoint
```

**Pass criteria**: every assertion green. **Robust identity**: host lookup by
tag, never by class. **Discrimination**: two different caps (10 vs 20), a
fill-partial-before-new-slot check (t=1.5), a cap-spill check (t=2.5), and a
remove-frees-slot check (t=4.5) — see Anti-gaming + Hidden invariants.

## Reference solution metadata

- LOC range: 60-100 LOC (a `TArray` of `{FName Type, int32 Count}` slots with a
  fixed capacity; `AddItem` looks up `MaxStackSize` from the data table, fills
  partial stacks of the type then empty slots capping per slot; `RemoveItem`
  decrements and frees emptied slots; the two getters fold over the slots)
- Files touched: 2 (1 header — only if a private slot type is added — and 1 cpp;
  the four operation signatures are pre-existing and unchanged)
- Senior-dev hours: 2-4 hours

## Anti-gaming notes

1. **Constant / single-point return.** *Failure mode*: `GetOccupiedSlotCount`
   always returns 1, or `GetTotalQuantity` echoes the last added count.
   *Defense*: the occupied-slot count evolves 1→1→2→4→3 and totals evolve across
   two item types over five checkpoints; no constant matches the sequence.
2. **Hard-coded cap (ignores the data table).** *Failure mode*: the agent
   hard-codes a single max-stack (say 10) instead of reading the per-type value.
   *Defense*: `Wood` caps at 20 — a hard-coded 10 makes 25 Wood occupy 3 slots,
   failing the t=3.5 `OccupiedSlots()==4` assertion. The two distinct caps force
   the value to come from the provided data.
3. **No partial-fill (always opens a new slot).** *Failure mode*: every add
   grabs a fresh slot. *Defense*: t=1.5 adds 2 Stone onto a 7-stack and asserts
   `OccupiedSlots()==1`; an always-new-slot impl reports 2 and fails.
4. **No spill at cap (one unbounded stack).** *Failure mode*: a slot holds more
   than its cap. *Defense*: t=2.5 (17 Stone) asserts exactly 2 occupied slots;
   an unbounded stack reports 1 and fails.
5. **No-op remove.** *Failure mode*: `RemoveItem` returns the count but doesn't
   mutate state. *Defense*: t=4.5 asserts `Total("Stone")==2` and
   `OccupiedSlots()==3`; a no-op leaves 17/4 and fails (the return value alone is
   not trusted — post-state is asserted).

## Hidden invariants

- **Per-slot cap is read per-type from the data table**, never assumed constant.
  The visible assertions are satisfiable only if `Stone` spills at 10 and `Wood`
  spills at 20; any single hard-coded cap fails one of the two types.
- **Fill-partial-before-new-slot** is load-bearing: adding to a non-full stack
  of the same type must not consume a new slot (t=1.5). A solution that passes
  the totals but opens new slots per add fails the occupied-slot counts.
- **Occupied = slots holding ≥1 unit.** A freed (zero) slot does not count
  (t=4.5), so `RemoveItem` must actually release emptied slots.
