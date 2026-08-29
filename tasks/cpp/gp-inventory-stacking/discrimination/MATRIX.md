# gp-inventory-stacking — discrimination matrix

Validated on Windows / UE 5.7.4 (2026-06-15) via
`run_task.py --substrate-from-live`. Reference + empty were run empirically. Two
one-delta variant legs were AUTHORED 2026-08-17 (`hard-coded-cap/`,
`no-op-remove/`) and are rowed below; each one's gate order is traced against the
fixture source, and neither has been RUN yet -- they ride the next
`cb discriminate --task cpp/gp-inventory-stacking`. The three remaining
anti-gaming modes stay argued from the fixture's named assertions (the
5-checkpoint schedule); bounded coverage below says why authoring them would add
a count rather than an isolation.

| Submission | Overall | Fails at | Expected message substring | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | **PASS** | — | all 5 checkpoints green (1/1) | — (PASS oracle) |
| empty (no overlay → scaffold stub) | **FAIL** | checkpoint 0 (t=0.5s) | `AddItem(Stone,7) returned false; 7 units should fit.` | FR-017 empty |
| `hard-coded-cap/` | **FAIL** | checkpoint 3 (t=3.5s), occupied-slot gate | `occupied slot(s); found ` | #2 hard-coded cap (requirements-table rows 7 + 10). AUTHORED 2026-08-17, NOT YET RUN. One delta: `MaxStackFor` returns a hard-coded 10 for every type instead of that row's `MaxStackSize`. Stone's real cap IS 10, so cp0-cp2 behave exactly like the reference and pass; 25 Wood then fill 3 slots instead of 2. At cp3 the Wood total (25) and the re-checked Stone total (17) are both still correct, so the two totals gates ahead of it PASS and the occupied-slot gate (4 expected, 5 found) is the FIRST gate this submission can trip |
| `no-op-remove/` | **FAIL** | checkpoint 4 (t=4.5s), Stone total gate | `): expected total ` | #5 no-op remove (requirements-table row 11). AUTHORED 2026-08-17, NOT YET RUN. One delta: `RemoveItem`'s range-for binds each slot BY VALUE, so it reports the units it would have taken while writing them to a copy. cp0-cp3 never call `RemoveItem` and pass verbatim; at cp4 the return-value gate passes ON PURPOSE (15 is the correct count), so the Stone total gate is the FIRST to fire, reading 17 where 2 is required |

## Anti-gaming modes (defended by the named-assertion schedule)

The fixture drives the fixed contract and asserts the *evolving* (total,
occupied-slot) state across 5 checkpoints with two distinct caps, so each mode
below fails at a specific checkpoint:

1. **Constant / single-point return** → the occupied-slot sequence 1→1→2→4→3 and
   the two-type totals cannot be matched by a constant (fails at the first
   diverging checkpoint).
2. **Hard-coded single cap (ignores the data table)** → a cap of 10 applied to
   `Wood` makes 25 Wood occupy 3 slots; checkpoint 3 asserts `occupied == 4`
   (Wood caps at 20). FAIL at t=3.5s. **COMMITTED as
   `discrimination/hard-coded-cap/`** and rowed above.
3. **No partial-fill (always new slot)** → checkpoint 1 asserts `occupied == 1`
   after adding 2 onto a 7-stack; a new-slot impl reports 2. FAIL at t=1.5s.
4. **No spill at cap (unbounded stack)** → checkpoint 2 asserts `occupied == 2`
   for 17 Stone; an unbounded stack reports 1. FAIL at t=2.5s.
5. **No-op remove** → checkpoint 4 asserts `Stone total == 2` / `occupied == 3`;
   a no-op leaves 17/4. FAIL at t=4.5s (the post-state is asserted, not the
   return value alone). **COMMITTED as `discrimination/no-op-remove/`** and rowed
   above.

## Bounded coverage (honest note)

Reference (PASS) and empty (FAIL) were each run through the deterministic
verifier. Two of the five gaming modes are now **committed one-delta variants**
(mode 2 as `hard-coded-cap/`, mode 5 as `no-op-remove/`, both authored 2026-08-17
as byte-exact copies of `../reference` carrying a single behavioural change).
Neither has been RUN: each row's "fails at" cell is a gate-order trace against
`UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/gp-inventory-stacking/InventoryStackingFunctionalTest.cpp`,
not a measurement, and nothing here may be read as measured until a
`cb discriminate` result is recorded in this file.

**Why those two and not the other three.** Modes 1, 3 and 4 (constant return,
no-partial-fill, unbounded stack) all die at the SAME source literal as mode 2 --
the fixture's single occupied-slot lambda, whose checkpoint index sits inside an
uncreditable `%d` -- so authoring them would add legs sharing one substring and
isolating nothing beyond `hard-coded-cap/`. The pair chosen instead dies at two
DIFFERENT gates (the occupied-slot lambda at cp3 vs the totals lambda at cp4),
probes two different prompt requirements (the per-type cap must come from the
shipped data, and Remove must MUTATE state rather than merely report), and
carries pairwise-disjoint substrings, neither of which is entailed by the `empty`
leg's literal.

Residual, unchanged by this pair: the escalation notes below still stand. Rows 5,
6, 13 and 16 of the requirements table are NOT ASSERTED, so no variant authored
against this fixture can probe them at all, and row 7's hard-coded-MAP hole (a
literal Stone-10/Wood-20 table in C++) stays behaviourally indistinguishable from
reading the data table. `hard-coded-cap/` closes only the SINGLE-cap half of that
hole, which is exactly as much as this fixture can see.

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span is a contiguous literal from a
`FinishTest(EFunctionalTestResult::Failed, ...)` call in
`UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/gp-inventory-stacking/InventoryStackingFunctionalTest.cpp`
(flat-layout fixture, pre-convention), never spanning a printf placeholder.
Layers are `[L1, L2]` — there is no L2I grader for this task; the checkpoint
schedule is sequential and any `FinishTest` ends the run, so every later gate is
skipped once an earlier one fires. The two shared failure literals are the
totals lambda (`At t=%.2fs (checkpoint %d): expected total %s == %d; found %d.`,
join span `): expected total `) and the occupied lambda
(`At t=%.2fs (checkpoint %d): expected %d occupied slot(s); found %d.`, join
span ` occupied slot(s); found `) — the checkpoint index printed in the message
is what names WHICH requirement failed.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the placed inventory host stays discoverable (one actor, resolvable) | fully | resolve gate (PrepareTest) — `Expected exactly one actor tagged 'InventoryRoot' in the test level; found ` | unconditional (first gate) | nothing at authoring time — the tag lives on the placed instance in the verifier-owned map; only runtime destruction/duplication of the actor can trip it, and fails here |
| 2 | the host remains the contract class (the "actor the project provides") | fully | cast gate (PrepareTest) — `is not an AInventoryHostActor (or a subclass); cannot drive the inventory contract.` | row 1 | subclassing is explicitly tolerated (identity is by tag, cast accepts subclasses) — by design |
| 3 | solve in C++ on the existing class; the four operation signatures are fixed | fully, by L1 + the substrate model | not a FinishTest gate — the verifier-only fixture `#include "InventoryHostActor.h"` and calls `Host->AddItem(StoneType, 7)` / `RemoveItem` / `GetTotalQuantity` / `GetOccupiedSlotCount` directly, so a changed signature fails the L1 Editor-target UBT build; the placed instance in the committed map is the C++ host, so logic in a never-placed Blueprint subclass never executes | unconditional | adding private members/helpers to the header is free (spec allows it) |
| 4 | Add reports whether all N units fit — true when they do | fully (fit case only) | cp0 return gate — `AddItem(Stone,7) returned false; 7 units should fit.` | rows 1–2 | the bool is sampled ONLY at cp0; cp1–cp3 discard the return value, so a submission returning nonsense bools after the first call passes if the state math is right |
| 5 | Add reports whether all N units fit — false / correct handling when they do NOT | **NOT ASSERTED** | — (no checkpoint ever overflows the inventory: at most 4 slots are ever occupied and every driven add fits) | — | `AddItem` may unconditionally return true, silently overfill, or crash when the inventory is full — the does-not-fit branch is never driven |
| 6 | the inventory holds a FIXED number of slots (finite capacity) | **NOT ASSERTED** | — (slot capacity is never exhausted or queried) | — | an unbounded `TArray` with no capacity limit passes every checkpoint; "fixed number of slots" is decorative under this fixture |
| 7 | per-type max stack size comes from the external data the project ships — do not hard-code the limits | partially — behavioral proxy only | cp3 occupied gate — ` occupied slot(s); found ` (expects 4: a single hard-coded cap of 10 puts 25 Wood into 3 slots → 5 total) plus cp3 totals gate `): expected total ` (Wood == 25) | rows 1–2 and any cp0–cp2 failure | **HOLE**: only a SINGLE hard-coded cap is caught. A submission hard-coding the literal map `{Stone:10, Wood:20}` in C++ never opens `DT_InventoryItemTypes` and passes every gate — the "read from external data" mechanism is behaviorally indistinguishable from a two-entry constant table |
| 8 | Add fills existing partial stacks of the same type FIRST (no new slot while a partial fits) | fully | cp1 occupied gate — ` occupied slot(s); found ` (expects 1 after adding 2 onto a 7-stack) | rows 1–2, cp0, or the cp1 totals gate (Stone == 9, row 14) fires first | order among MULTIPLE partial stacks of one type is untestable here — the schedule never creates two simultaneous partials of the same type |
| 9 | never let any single slot exceed that type's maximum (spill at cap) | fully at the tested points | cp2 occupied gate — ` occupied slot(s); found ` (17 Stone must occupy exactly 2 slots) | rows 1–2, cp0–cp1, or the cp2 totals gate (Stone == 17, row 14) fires first | per-slot CONTENTS are never read (only the contract's return values are observed): 17 split as 9+8 — no slot at the cap — also shows 2 slots and passes; only the slot-count consequence of the cap is gated |
| 10 | a type with a DIFFERENT maximum spills at ITS limit, not the first type's (Wood=20) | fully | cp3 totals gate — `): expected total ` (Wood == 25 AND Stone == 17 re-checked) then cp3 occupied gate — ` occupied slot(s); found ` (== 4: Stone 10+7, Wood 20+5) | rows 1–2, cp0–cp2 | — |
| 11 | Remove takes N units from that type's stacks (count reported AND state actually mutated) | fully (sufficient-stock case) | cp4 return gate — `RemoveItem(Stone,15) returned ` (expects 15) then cp4 totals gate `): expected total ` (Stone == 2 post-state — the return value alone is not trusted) | rows 1–2, cp0–cp3 | WHICH stacks the 15 units come from is unobserved — any 15-of-17 removal order passes (deliberate: behavior-only) |
| 12 | Remove frees any slot that reaches zero units | fully | cp4 occupied gate — ` occupied slot(s); found ` (expects 3: Stone collapses to one slot, Wood keeps two) | rows 1–2, cp0–cp3, and the cp4 return/total gates fire first | — |
| 13 | Remove behavior when N exceeds the units held | **NOT ASSERTED** | — (every driven remove has sufficient stock: 15 of 17) | — | over-removal may underflow to negative totals, return a wrong count, or crash — never driven |
| 14 | Report the total units of a given type across all slots | fully | totals gate at every checkpoint — `): expected total ` (Stone at cp0/1/2/3/4, Wood at cp3 — echo-last-add or any constant diverges at the first mismatching checkpoint) | rows 1–2 | only the two shipped types are ever queried; `GetTotalQuantity` of an unknown type is never exercised |
| 15 | Report the number of occupied slots (holding ≥1 unit) | fully | occupied gate at every checkpoint — ` occupied slot(s); found ` (the sequence 1→1→2→4→3 across two types; no constant or single-point return matches) | rows 1–2 | — |
| 16 | the SET of valid item types is defined by external data (unknown types are not valid) | **NOT ASSERTED** | — (only `Stone` and `Wood`, both valid rows, are ever passed to the contract) | — | add/remove/query of an item type absent from the data table is never exercised — a submission may accept arbitrary FNames with an invented default cap and pass |

### Escalation notes (holes the table found)

- Rows 5, 6, 13, 16 are NOT ASSERTED: the fixture never drives capacity
  exhaustion, over-removal, or an unknown item type — the entire
  "boundary/rejection" half of the prompt contract is ungated. A sixth
  checkpoint that fills the inventory (assert `AddItem` returns false and
  totals unchanged) would close rows 5 and 6 in one leg.
- Row 7 is the known data-driven-tasks residual: reading from
  `DT_InventoryItemTypes` cannot be distinguished behaviorally from
  hard-coding the exact two-entry map. Closing it would take either a
  fixture-side data-table mutation before PrepareTest (not currently done)
  or a source-AST check (no L2I/AST layer is wired for this task).
