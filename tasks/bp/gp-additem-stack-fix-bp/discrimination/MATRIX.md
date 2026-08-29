# Discrimination matrix — gp-additem-stack-fix-bp

The self-validation oracle: the reference solution must PASS and the empty
leg must FAIL **at the predicted gate, via the named substring**. A
wrong-reason FAIL (L1 build failure, a different gate, a machine-fault
verdict) means the verifier is NOT discriminated — fix it, or relabel the
task for the weaker property it actually tests.

Per the amended checklist §7 (owner decision 2026-08-11) this package
ships **no hand-authored gaming variants**: the automatic reference-PASS /
empty-FAIL legs provide the non-vacuity bit, and the **requirements
table** below is the mandatory soundness artifact.

**The empty leg IS the shipped defect** (the door-hitch pattern): an
empty submission runs the committed BUGGY component, whose add path's
already-exists branch falls through to the new-stack logic — so the
first add works and the repeat add overwrites instead of accumulating,
minting a phantom stack. The empty leg exercises the whole pipeline and
dies exactly at the stacking gate.

## Parser traps this matrix is written against (inherited from the bp L2 set)

- **ONE parseable row-table**; the requirements table names no column
  "substring"/"message".
- **Every "Expected substring" cell is a backtick-wrapped literal with a
  space or `=`**, a verbatim contiguous span of ONE
  `FinishTest(EFunctionalTestResult::Failed, ...)` source literal in
  `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-additem-stack-fix-bp/AdditemStackFunctionalTest.cpp`,
  never spanning a printf placeholder. ASCII-only (cp1252 read-back).
- **L2 substrings match the editor stdout captured in `out/l2_pie.log`**
  (index.json is authoritative for PASS/FAIL; the substring credits the
  REASON).
- **Error/machine-fault classes are never credited**: `PrepareTest: no
  UWorld`, the `MARSHALING-FAULT: ` family (every contract call's return
  is checked, so a mid-run seam break fails through its OWN token rather
  than borrowing a behavior gate's — review catch 2026-08-12),
  `queued_never_started`, EDITOR-GONE — no row below names them.

## Layout (folder-local; agent-writable prefixes only)

- Substrate baseline (committed, aid-authored via the MCP editor lane):
  `UE-projects/ThirdPerson/Content/Tasks/gp-additem-stack-fix-bp/BP_InventoryComponent.uasset`
  (the BUGGY component) +
  `.../BP_InventoryHost.uasset` (the trivial host actor carrying it).
- Verifier map (committed, deny-listed path):
  `UE-projects/ThirdPerson/Content/Maps/gp-additem-stack-fix-bp/L_AdditemStack.umap`
  — one placed `BP_InventoryHost` tagged `StackHost` + the placed
  `AAdditemStackFunctionalTest`.
- `../reference/Content/Tasks/gp-additem-stack-fix-bp/BP_InventoryComponent.uasset`
  — the FIXED component: the already-exists branch routes into the
  accumulate path (`notes.md` §2). Same asset path; the overlay replaces
  the baseline.
- empty leg — run IMPLICITLY by `cb discriminate`: the untouched buggy
  baseline.

## Matrix

**This is the only table in this file that carries submission rows.**

| Submission | Overall | Fails at (gate) | Expected substring | Notes |
|---|---|---|---|---|
| `../reference` | PASS | — | — | all three checkpoints green; fixture finishes past cp2 |
| empty | FAIL | stacking (cp1) | `Adding to an existing stack did not stack: GetItemCount('Wood') returned ` | the buggy baseline PASSES empty-start and first-add (its defect is REPEAT adds only — the point) and dies at THE gate |

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span is a contiguous `FinishTest(Failed, ...)` literal in
`AdditemStackFunctionalTest.cpp`; the gate name is the durable join key.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the placed host stays discoverable | fully | resolve gate — `Expected exactly one actor tagged 'StackHost' (the inventory holder) in the running level; found ` | unconditional (first gate) | nothing; the TAG lives on the placed instance in the verifier-owned map |
| 2 | the three functions keep their names and shapes | fully | seam gate — `No component on the host exposes the inventory contract: reflected 'AddItem' (name + whole number), 'GetItemCount' (name -> whole number) and 'GetStackCount' (-> whole number) - the interface is broken.` | host unresolvable (row 1) | parameter NAMES are free (shape-matched, name-insensitive); the contract may live on ANY component of the host, or the actor itself — deliberate (see residuals) |
| 3 | the inventory starts empty | fully | empty-start gate — `The inventory did not start empty: GetStackCount() returned ` | rows 1–2 | nothing at this layer |
| 4 | first-time adds keep working | fully | first-add gate — `A first AddItem did not register: GetItemCount('Wood') returned ` | rows 1–3 | nothing; a constant-5 hardcode dies HERE (3 expected) |
| 5 | adding to an existing stack accumulates | fully | stacking gate — `Adding to an existing stack did not stack: GetItemCount('Wood') returned ` | rows 1–4 fan out first | nothing at the count layer; storage mechanism free |
| 6 | the repeat add must not mint a second stack | fully | duplicate-stack gate — `The repeat AddItem minted a duplicate stack: GetStackCount() returned ` | stacking gate fires first if both broken (owns the count concept) | internal storage layout — only the reported stack count is gated |
| 7 | different items stay independent | fully | isolation gate — `A later AddItem for a different item corrupted state: Wood=` | rows 4–6 fan out | order-independence beyond the tested sequence (accepted residual) |
| 8 | fix is IN PLACE (same assets, same folder) | fully, by the substrate model | not a gate — the map references the committed host; a component authored elsewhere never runs UNLESS attached to this host (row 2's residual, accepted) | unconditional | see residual: a NEW component carrying the contract on the same host passes by design |

## Accepted residuals (documented, not defended)

- **A replacement component passes** (rows 2/8): the seam accepts any
  component of the tagged host exposing the contract. Deliberate —
  behavior-only; "fix the shipped component" vs "replace its logic" is a
  mechanism distinction the gates refuse to see. The HOST is shipped and
  placed, so the deliverable still routes through the committed level.
- **Only the tested sequence is gated**: Wood 3+2, then Stone 4. Permuted
  orders, removals, zero/negative counts are unconstrained — the row's
  capability is the branch bug, not inventory completeness.
- **Storage is unconstrained**: map, arrays, structs, anything — only
  the three reported numbers are gated.
- **No camera plan (`cameras.json` (the camera-plan lane; not part of this release))**: nothing visual moves — N/A by
  shape (the door task has the visual; this one is pure state).

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task bp/gp-additem-stack-fix-bp --wip
```

Per-leg fallback while iterating:

```sh
UE='<UE-root>'
py tools/verify-single/run_task.py \
    --task tasks/bp/gp-additem-stack-fix-bp/task.md \
    --submission tasks/bp/gp-additem-stack-fix-bp/reference \
    --ue-root "$UE" --workdir C:\cb\wd\additem-ref    # expect exit 0
```

## Status

- Fixture authored + built clean 2026-08-12 (19.4 s incremental UBT).
- Binaries authored the same day in ONE MCP-lane session (all three live
  spikes held: `map:Name,Integer` type-hint grammar, BlueprintMapLibrary
  wildcards resolving on connect, function-graph strand wiring - laws in
  notes.md §3).
- **Validation legs run 2026-08-12 (`--substrate-from-live`): the oracle
  held exactly.** Reference: PASS (L1 227.3 s; L2 50.0 s, tests=1/1).
  Empty (= the buggy baseline): FAIL at the stacking gate with the
  credited literal - measured `GetItemCount('Wood') returned 2` (the
  overwrite) `(expected 5)`; L1 + empty-start + first-add green first,
  the targeted-debug shape.
- **Refgate (certified, from git HEAD): PASS, 200 s** (2026-08-12,
  commit 22e2a0f; gp-door-hitch-fix-bp re-certified 161 s on the same
  run after the task-#34 verifier-tags fix touched shared fixture
  code). Empty-FAIL legs + this task's discriminate sweep ride the
  next `cb discriminate` run.
