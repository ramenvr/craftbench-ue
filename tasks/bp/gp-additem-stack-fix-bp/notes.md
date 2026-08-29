# gp-additem-stack-fix-bp — verifier-builder notes

g2-11 port (scaleup slate T2.4, the Edit(Debug) family's second member),
built 2026-08-12 in ONE authoring session on the door-hitch lane —
the reuse thesis held: component + host + both graph variants + map in
~20 minutes of tool calls once the lane was up.

## 1. The BUGGY baseline, property-by-property

`UE-projects/ThirdPerson/Content/Tasks/gp-additem-stack-fix-bp/`:

- `BP_InventoryComponent.uasset` (57,693 bytes) — parent
  `ActorComponent`. Variables: `Items` (`TMap<FName,int32>`, empty
  default), `StackCount` (int, 0). Functions:
  - `GetStackCount() -> Count`: returns `StackCount`.
  - `GetItemCount(ItemId) -> Count`: `Map_Find(Items, ItemId)` → Value
    (unfound → 0, exactly the wanted semantic).
  - `AddItem(ItemId, Count)`: `Branch(Map_Contains(Items, ItemId))` —
    **BOTH exec outputs wired into the SAME new-stack leg**
    (`Map_Add(Items, ItemId, Count)` → `StackCount += 1`): the classic
    copy-paste fall-through. Consequences: a FIRST add per item behaves
    correctly (the observational baseline the first-add gate rides); a
    REPEAT add OVERWRITES the count (Map_Add replaces) and mints a
    phantom `StackCount` increment.
- `BP_InventoryHost.uasset` (25,023 bytes) — `Actor` carrying one
  `Inventory` (BP_InventoryComponent) subobject.

## 2. The reference fix

`reference/Content/Tasks/gp-additem-stack-fix-bp/BP_InventoryComponent.uasset`
(63,459 bytes) — the True (already-exists) branch routes into its own
accumulate leg: `Map_Add(Items, ItemId, Add_IntInt(Map_Find(Items,
ItemId).Value, Count))`, with NO StackCount increment. Three extra nodes
(`Map_Find`, `Add_IntInt`, a second `Map_Add`) vs the baseline — the
agent's fix must AUTHOR the missing path, not merely rewire (a step up
in difficulty from door-hitch's two-pin fix, matching the row's
"doesn't understand control flow" weakness).

Authoring order (the stage/mutate/harvest pattern, inverted vs
door-hitch): FIXED graph built first → bytes staged → accumulate nodes
REMOVED (`remove_blueprint_nodes`) + True rewired into the shared leg →
buggy bytes promoted as the substrate baseline, staged FIXED bytes as
the reference.

## 3. Lane notes (new laws caught this session)

- **`edit_blueprint` type-hint grammar for containers is
  `map:KeyType,ValueType`** (parser: the vendor plugin's
  `UnrealMCPCommonUtils.cpp:197` — `array:`/`set:` prefixes likewise).
  "Map<Name,Integer>" is silently ignored and the variable lands as a
  STRING — always read the type back (python `get_editor_property`)
  before building on it.
- **A failed default-value import can still mean the TYPE change
  succeeded**: converting Items to the map errored on importing the
  `null` default ("cannot import non-Object JSON into map property") —
  the error text itself confirmed the new `TMap<FName,int32>` type.
- **`BlueprintMapLibrary` wildcard pins resolve on `connect_blueprint_nodes`**
  — wire the map variable into `TargetMap` first; `Map_Find`'s unfound
  default (0 for int values) is load-bearing for `GetItemCount`.
- **Function-graph strands wire exactly like the EventGraph** (strand
  name = function name; `K2Node_FunctionEntry_0`/`K2Node_FunctionResult_0`
  are the anchors; entry→result exec comes pre-wired for output-bearing
  functions).
- **BP-classed components attach via `AddNewSubobjectParams(new_class=
  <generated class>)`** — same recipe as engine classes.
- The session ALSO fixed two lane-wide breakages (recorded in
  [[craftbench-doorhitch-and-mcp-lane-laws]] and the task-#34 closure):
  a vendor-plugin fast-forward introduced a Dev module that
  asserts on load (entry dropped locally, uncommitted — upstream bug),
  and the #34 native-tag ensure was fixed properly
  (`DefaultGameplayTags.ini` + request-by-name accessors in
  `CraftBenchVerifierTags.cpp`).

## 4. Fixture constants (mirror of AdditemStackFunctionalTest.cpp)

Sequence Wood(3) → Wood(2) → Stone(4); expected 3 / 5+1stack / 5,4,2.
Checkpoints 0.5/1.0/1.5 s (synchronous calls, phases for log clarity).
Seam matching is SHAPE-based, name-insensitive on parameters
(`MatchesShape`), and searches the actor + every component.

## 5. Status / remaining

- Fixture C++ built clean (19.4 s). Binaries + map authored + promoted.
- Validation legs, registry bumps (59 tasks / bp 20 / 38 maps + MAPS.md
  row), commit, refgate, PR: in flight — recorded in MATRIX §Status.
- No camera plan: nothing visual — N/A by shape (recorded in MATRIX).

## Capability bucket corrected 2026-08-17

This spec read `capability_bucket: Gameplay Programming`. It now reads
**`Debug & Refactoring`**, because that is what the task is: it ships a
deliberately-broken baseline and asks for a repair.

**Why it mattered beyond tidiness.** The corpus was misdescribing its own
coverage. Measured across all 62 specs on 2026-08-17, `Debug & Refactoring` held
exactly ONE task — `kp-engine-source-search`, a *search* task — while both
genuine Edit/Debug tasks sat under `Gameplay Programming` (which already holds 45
of 62). So any coverage table built from this field said the benchmark had one
debug-ish task and no fix tasks, when it has two fix tasks. The dossier had
already flagged the symptom ("its one Debug & Refactoring row sits on a SEARCH
task rather than on either fix task"); this is the fix.

**Scope:** metadata only. `capability_bucket` is not agent-visible and has no
grading consumer (`spec.py` parses it; nothing scores on it), so this is not a
D6 contract change and prior measurements stay comparable. It does move the task
tree sha, so this task's refgate certificate re-keys and is re-gated with the
wave it ships in.

**Left for the owner:** whether `kp-engine-source-search` should stay in
`Debug & Refactoring` or move (engine-source literacy is arguably Tools &
Pipeline). Not guessed here — with these two tasks added the bucket no longer
misrepresents the corpus, so its membership is a taxonomy preference rather than
a defect.
