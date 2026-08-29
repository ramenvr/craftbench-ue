# Discrimination matrix — kp-retarget-maps-two-rigs

The self-validation oracle: the reference must PASS and every negative leg must
FAIL **at the predicted check, via the named substring**. A wrong-reason FAIL
means the verifier is NOT discriminated — fix it, or relabel the task for the
weaker property it actually tests.

Two hand-authored variants ship. Per the amended checklist §7 they are owed only
when the requirements table finds a hole, and here it did: requirement 4 ("each
named run resolves") is the row's whole point and is satisfiable-looking without
being satisfied, so leaving it to a table would mean the central claim was never
run.

## Parser traps this matrix is written against

- **NO cell may reach PAST a runtime placeholder into the value.** Every
  expected substring stops at the `=` preceding an interpolated value
  (`RETARGET_MAPPING_UNRESOLVED chains=`), because the grader formats those tails
  with `%s`. A longer cell would depend on the runtime value and could turn a
  *correct* FAIL into a wrong-reason FAIL — the `granted=0` vs `granted=` rule.
- **ONE parseable row per label.** `discriminate.parse_matrix` keys rows by first
  cell and LAST ROW WINS, so a second table repeating a label silently
  overwrites. This file has exactly one table with submission rows; the
  requirements table's first cells are integers and its columns name neither
  "substring" nor "message", so `parse_matrix` skips it.
- **Every "Expected substring" cell is a backtick-wrapped literal containing a
  space or `=`**, so `_extract_substrings` keeps it verbatim.
- **Error tokens are distinct from failure tokens.** `RETARGET_LOAD_ERROR`,
  `RETARGET_CONTROLLER_ERROR`, `RETARGET_CHAIN_READ_ERROR`,
  `RETARGET_MAPPING_READ_ERROR` and `RETARGET_NO_UNREAL` appear in no row below,
  so a broken probe surfaces as an uncredited FAIL rather than a credited named
  failure.

## Layout (folder-local; agent-writable prefixes only)

- `../reference/Content/Tasks/<id>/{IK_TaskSource,IK_TaskTarget,RTG_TaskMotion}.uasset`
  — both rigs with a retarget root and the two named runs, and a transfer asset
  whose stack is populated and whose mappings resolve. **8/8.**
- `rigs-without-chains/…` — both rigs created and bound to their meshes but with
  no root and no runs; transfer asset created and left alone.
- `retargeter-without-ops/…` — **both rigs fully built**, transfer asset created,
  both rigs named on it, auto-map called — and the internal stack never
  populated, so nothing resolves.
- empty leg — run IMPLICITLY by `cb discriminate`. This task ships no baseline,
  so the graded state is genuinely empty: **0/8**.

## Requirements table (checklist §7, the mandatory soundness artifact)

| # | Prompt requirement | Asserted | Enforcing check — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | produce the three named assets in that folder | fully | C1–C3 — `RETARGET_ASSET_ABSENT path=` / `RETARGET_WRONG_CLASS path=` | unconditional | nothing |
| 2 | both rig descriptions name the bone motion is measured from | fully | C4–C5 — `RETARGET_ROOT_UNSET got=` | skipped only when its own rig is missing, which C1–C2 already fail | WHICH bone is chosen — deliberate, the prompt leaves it to the agent |
| 3 | both declare runs named `Spine` and `LeftArm` | fully | C6 — `RETARGET_CHAIN_MISSING ` | as above | which BONES a run spans — deliberate and disclosed |
| 4 | each named run resolves to a run on the source | fully | C8 — `RETARGET_MAPPING_UNRESOLVED chains=` | skipped only when the transfer asset is missing (C3 fails) | nothing — this is the row's central claim and the `retargeter-without-ops` leg is its live proof |
| 5 | the transfer asset reads the first rig and writes the second | fully | C7 — `RETARGET_REFS_WRONG source=` | as above | nothing |
| 6 | save all three where they are named | fully | no separate check by design — the runner grades a file overlay, so an unsaved asset presents as no file and fails C1–C3 | unconditional | nothing |
| 7 | change nothing about the two shipped bodies | **not asserted** | none | n/a | **accepted residual**: `Content/Characters/` is deny-listed by the sandbox manifest, so a write there is rejected at exit 4 before the grader runs. A check here would duplicate the sandbox and could never fail through it. |

**Holes this table found:** requirement 4 was the one that could look satisfied
without being satisfied — which is why `retargeter-without-ops` exists as a
hand-authored leg rather than being left to the table.

## Matrix

**This is the only table in this file that carries variant rows.**

| Submission | Overall | Fails at (check id) | Expected substring | Also fails (recorded, not matched) | Anti-gaming note |
|---|---|---|---|---|---|
| `../reference` | PASS | — | all 8 checks green (8/8) | — | — |
| empty | FAIL | `source_rig_present` | `RETARGET_ASSET_ABSENT path=` | every other check — 0/8: two sibling absences, two `RETARGET_ROOT_UNCHECKABLE`, `RETARGET_CHAIN_MISSING`, `RETARGET_REFS_UNCHECKABLE`, `RETARGET_MAPPING_UNCHECKABLE` | FR-017 |
| `rigs-without-chains/` | FAIL | `source_rig_has_retarget_root` | `RETARGET_ROOT_UNSET got=` | the sibling root check, `RETARGET_CHAIN_MISSING`, `RETARGET_REFS_WRONG`, and `RETARGET_MAPPING_UNRESOLVED`; C1–C3 PASS | #1 create-and-stop |
| `retargeter-without-ops/` | FAIL | `chain_mapping_resolves` | `RETARGET_MAPPING_UNRESOLVED chains=` | nothing else — **C1–C7 all PASS, 7/8** | #2 configure-everything-except-the-stack |

**Why the third leg is the important one.** It is not a lazy submission — it
does everything the obvious reading of the task asks, and fails on the one fact
that makes the pipeline actually work. It scores **7/8**, so it is also the
sharpest possible test that the denominator is honest: a task that graded
"created the three assets" would call it a pass. Measured at authoring time on
2026-08-14: with the stack unpopulated, every required run maps to nothing,
while the identical construction *with* the stack populated maps `Spine→Spine`
and `LeftArm→LeftArm`.

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task python/kp-retarget-maps-two-rigs
```

No `--wip`: the committed tree must discriminate.

## Status

**VALIDATED 2026-08-14** (Windows, UE 5.8.1). Both committed-tree runs are in:

- `cb refgate python/kp-retarget-maps-two-rigs` — **PASS 8/8**, 205s, certified.
- `cb discriminate` with NO `--wip` — **discriminated YES, 4/4 legs at their
  named checks**: reference PASS, empty 0/8, `rigs-without-chains` 3/8,
  `retargeter-without-ops` **7/8**.

The dated row is in the dated validation table (internal, not shipped), which is the status authority.

Worth recording about the FIRST refgate attempt: it PASSED but refused to
certify, because three stray `.uasset` files (byte-identical to the committed
reference, left by a stalled in-session grader test) were sitting in this task's
substrate baseline path. This task ships NO baseline by design, so committing
them would have shipped it PRE-SOLVED. The PASS was honest either way — the
graded substrate comes from git HEAD and the files were untracked — so what the
dirty tree cost was the certificate, not the verdict. The refusal is the only
reason the files were found at all.
