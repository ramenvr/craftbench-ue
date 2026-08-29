---
id: gp-additem-stack-fix-bp
substrate: ThirdPerson
set: bp
tier: T2
capability_bucket: Debug & Refactoring
category: gameplay
layers: [L1, L2]
fixtures: ["L_AdditemStack :: AAdditemStackFunctionalTest"]
---

# gp-additem-stack-fix-bp

The Edit(Debug) family's **second member**, reusing the door-hitch lane at
a fraction of its cost: the workspace ships a working-but-defective
inventory component whose add path mishandles the already-have-this-item
case — a pure **control-flow** defect (the observed model weakness the
source row records). The deliverable is the fix, graded through the
component's own reflected interface in a real PIE world; every gate is
behavior, none is mechanism.

### Provenance and deliberate divergences from the source row

Ported from **`BP Test Prompts - G2 Medium Prompts.csv` row g2-11**
(`Inventory`, `Edit (Debug)`, easy; observed weakness: "Doesn't seem to
understand control flow") via the scale-up plan's slate row **T2.4**. The source row
row is nearly bare — its whole prompt is *"In the component
/Game/G2/11/BP_InventoryComponent why is AddItem not working?"* — and the
slate note is the design law here: **re-framed as a behavior contract
with the bug NOT described**, because there is no gating prose judge and
a "why" question cannot be graded as-is. The defect itself is authored
(the source row ships no Before Blueprint): the add path's
already-exists branch falls through to the new-stack logic — the classic
copy-paste control-flow error, matching the row's observed weakness.
Folder convention: the source row's `/Game/G2/11/` becomes
`Content/Tasks/gp-additem-stack-fix-bp/`.

> **Note on the behavior-only rule (Hard Rule #2).** The prompt names the
> shipped assets, the three interface functions with their shapes (the
> contract the fixture drives — floored because the grader calls them by
> name), and the graded example numbers. The DEFECT is described as
> observable behavior (what the counts read after a repeat add), never by
> its cause; no engine class, node, or container type appears.

## Primary concept

- `blueprint-flow-control` — Flow Control
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/flow-control-in-unreal-engine)

The load-bearing capability is **debugging branch logic in stateful
Blueprint code**: recognizing that one branch of a condition routes into
the wrong path, and repairing it without breaking the working half or
the surrounding contract.

## Prompt given to the agent

> The folder `Content/Tasks/gp-additem-stack-fix-bp/` contains
> `BP_InventoryHost` (an actor placed in the world) and
> `BP_InventoryComponent`, the stacking inventory it carries. The
> inventory's interface, which callers rely on:
>
> - `AddItem(ItemId, Count)` — add `Count` of `ItemId` to the inventory;
> - `GetItemCount(ItemId)` — the total held for `ItemId` (a whole
>   number);
> - `GetStackCount()` — how many distinct item stacks exist.
>
> The component has a defect around REPEAT adds. The first add of any
> item works: after `AddItem('Wood', 3)`, `GetItemCount('Wood')` is 3
> and there is 1 stack. But adding more of an item you already hold does
> not accumulate: after a further `AddItem('Wood', 2)`,
> `GetItemCount('Wood')` reports only the newest amount instead of the
> total, and `GetStackCount()` reports an extra stack — instead of one
> stack of 5.
>
> Fix the component **in place** (same assets, same folder) so that:
>
> - adding to an existing stack accumulates: 3 then 2 of `'Wood'` reads
>   5, still in a single stack;
> - first-time adds keep working exactly as before;
> - different items stay independent: a later `AddItem('Stone', 4)`
>   reads 4 for `'Stone'`, leaves `'Wood'` at 5, and the stack count at
>   2;
> - the three functions keep their names and shapes.

## Workspace state pre-task

Substrate content that **exists**:

- `Content/Tasks/gp-additem-stack-fix-bp/BP_InventoryComponent.uasset` —
  the defective component (property-by-property spec: `notes.md` §1).
- `Content/Tasks/gp-additem-stack-fix-bp/BP_InventoryHost.uasset` — the
  trivial host actor carrying one instance of the component. Both are in
  the agent-writable carve-out; the natural fix touches only the
  component, but the contract is behavioral — gates never check which
  asset changed.
- `Content/Maps/gp-additem-stack-fix-bp/L_AdditemStack.umap` — the
  VERIFIER'S fixture level (deny-listed): one placed `BP_InventoryHost`
  tagged `StackHost` + the functional-test actor.

## Verifier specification

Layer choice: **L1 + L2**. The graded surface is the runtime behavior of
executed Blueprint logic (state across a call sequence) — L2I is
deliberately NOT declared: a structural gate would pin the storage
mechanism, and the fix is mechanism-free (any rebuild that honors the
interface passes).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

Content-only submission expected; L1 is a precondition, never a signal.

### L2 — PIE behavioral fixture

`AAdditemStackFunctionalTest` (Source/CraftBenchTests/Tasks/
gp-additem-stack-fix-bp/) runs in the committed `L_AdditemStack` map
under `-deterministic -FPS=60 -nullrhi`. The host is found **by actor
tag** (`StackHost`, exactly-one); the inventory is found **by its
SEAM**, never by class — any component (or the actor itself) exposing
all three reflected functions with the contracted shapes qualifies
(parameter NAMES are free; types/arity are the contract). Calls are
driven through typed `ProcessEvent` marshaling (the sprint-fixture seam
idiom extended to parameters).

Phases (calls are synchronous; checkpoints keep the log legible):

```text
prepare     resolve host + seam; GetStackCount() must read 0 (empty start)
t=0.5       AddItem('Wood', 3); GetItemCount('Wood') must read 3
            (the first-add gate — the BASELINE passes this)
t=1.0       AddItem('Wood', 2); GetItemCount('Wood') must read 5 (THE
            stacking gate) and GetStackCount() must read 1 (the
            duplicate-stack gate)
t=1.5       AddItem('Stone', 4); Wood=5, Stone=4, stacks=2 (isolation)
```

Every gate fails through its OWN `FinishTest(Failed, ...)` literal; the
inventory with the requirements mapping is `discrimination/MATRIX.md`.

**Every graded fact excludes the value an untouched or lazy delivery
gets for free** (the dead-gate audit):

| gate | free/untouched (BUGGY BASELINE) value | graded demand | free value inside the gate? |
|---|---|---|---|
| empty start | 0 (guard row — baseline passes) | 0 stacks pre-add | (guard) |
| first add | baseline PASSES (its defect is repeat adds only) | 3 after one add | (deliberate — proves targeted DEBUG: a fix that breaks first adds fails here) |
| stacking | baseline FAILS: reads the newest amount, not the total | 5 after 3 then 2 | **no — THE discriminating gate; the empty leg IS the baseline** |
| duplicate stack | baseline also mints a phantom stack, but dies at the stacking gate first | still 1 stack | **no** (owns the phantom-stack concept) |
| isolation | unreachable on the baseline (dies earlier) | cross-item independence | **no** |

**Score granularity.** L2 is one fixture: `report.json` carries the
fixture verdict; `overall` = all layers green.

## Reference solution metadata

- LOC range: **0** lines of code; the minimal fix reroutes the
  already-exists branch into an accumulate path (`notes.md` §2 pins both
  graphs property-by-property).
- Files touched: 1 (the modified `BP_InventoryComponent.uasset`).
- Senior-dev hours: 0.1–0.3 for the minimal fix; the T2 content is
  DIAGNOSIS (tracing which branch runs), not volume.

## Anti-gaming notes

Per the amended checklist §7 the discrimination package ships no
hand-authored gaming variants; the requirements table in
`discrimination/MATRIX.md` is the soundness artifact. The failure modes
it is written against:

1. **Empty delivery** — the untouched baseline: passes empty-start and
   first-add, dies at the stacking gate with the named literal.
2. **Hardcode the example** — returning 5 for `'Wood'`
   unconditionally dies at first-add (3 expected) or isolation
   (`'Stone'` reads 4, `'Wood'` must still read 5, stacks 2) — the
   sequence is over-determined against constant-shaped fixes.
3. **Suppress repeat adds** — ignoring the second `AddItem` avoids the
   phantom stack but reads 3, not 5: dies at the stacking gate.
4. **Break the interface** — renaming or reshaping the functions dies at
   the seam gate; the TAG lives on the placed instance in the
   verifier-owned map, out of the agent's reach.
5. **Fix by replacement elsewhere** — a new component carrying the
   contract on the same host PASSES by design (the seam finds it):
   behavior-only, recorded as a residual, not a hole.

## Discrimination

`discrimination/MATRIX.md` — reference-PASS / empty-FAIL legs (the empty
leg IS the buggy baseline) plus the mandatory requirements table.
