# Discrimination matrix — kp-motion-set-shares-one-rig

The self-validation oracle: the reference must PASS and every negative leg must
FAIL **at the predicted check, via the named substring**. A wrong-reason FAIL
(L1 failure, a different check, a `0`-check/`error` L2I verdict,
SANDBOX-REJECT exit 4) means the verifier is NOT discriminated — fix it, or
relabel the task for the weaker property it actually tests.

Per the amended checklist §7 (owner decision 2026-08-11) the mandatory
artifacts are the automatic reference-PASS / empty-FAIL legs plus the
**requirements table** below. One hand-authored variant ships anyway, and it
earns its place: `duplicate-the-shipped-set` is the exact failure the
task-owned-rig design exists to catch, so leaving it to a table would mean the
central claim was never run.

## Four parser traps this matrix is written against

- **NO cell may reach PAST a runtime placeholder into the value.** Every
  expected substring below stops at the `=` that precedes an interpolated
  value (`MOTIONSET_WRONG_RIG expected=`), because the grader formats those
  tails with `%s`. A longer cell would depend on the runtime value and could
  turn a *correct* FAIL into a wrong-reason FAIL — the `granted=0` vs
  `granted=` rule from `matrix_oracle`'s docstring. This trap is written first
  because it cost a cell on `t2-consistent-enum-names` on 2026-08-12.
- **ONE parseable row per label.** `discriminate.parse_matrix` returns
  `Dict[label -> MatrixRow]`, so a second table repeating a variant label
  silently OVERWRITES the first. This file has exactly one table with
  submission rows; the requirements table's first cells are integers and its
  columns name neither "substring" nor "message", so `parse_matrix` skips it.
- **Every "Expected substring" cell is a backtick-wrapped literal containing a
  space or `=`**, so `_extract_substrings` keeps it verbatim instead of falling
  through to the de-noised whole cell.
- **Error tokens are distinct from failure tokens.** Every verifier-side path
  emits `MOTIONSET_LOAD_ERROR` / `MOTIONSET_CLASS_READ_ERROR` /
  `MOTIONSET_ANCHOR_READ_ERROR` / `MOTIONSET_LINK_READ_ERROR` /
  `MOTIONSET_NO_UNREAL`, none of which appears in any row below — a broken
  probe surfaces as an uncredited FAIL, never as a credited named failure.

## Layout (folder-local; agent-writable prefixes only)

- `../reference/Content/Tasks/<id>/{A_TaskMotion,AM_TaskAction,ABP_TaskLogic}.uasset`
  — the three assets authored for the task rig. **7/7.**
- `duplicate-the-shipped-set/Content/Tasks/<id>/{same three names}.uasset` —
  the stock Mannequin clip / montage / animation-logic assets duplicated under
  the required names. Authored 2026-08-14 by
  `../authoring/author_variant.py`; every one reports the STOCK rig, verified
  at authoring time.
- empty leg — run IMPLICITLY by `cb discriminate` (a throwaway empty dir). The
  graded state is the untouched baseline: the rig alone, a genuine **0/7**.

The baseline rig itself is NOT in any leg. It lives in the substrate
(`UE-projects/ThirdPerson/Content/Tasks/<id>/SK_TaskRig.uasset`) and is
therefore present under every leg by construction, which is what makes the
anchor comparison meaningful.

## Requirements table (checklist §7, the mandatory soundness artifact)

One row per requirement in the agent-visible prompt. The check id is the
durable join key; every backticked span is a contiguous literal in
`tools/verify-single/introspect/kp_motion_set_shares_one_rig.py`.

| # | Prompt requirement | Asserted | Enforcing check — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | produce `A_TaskMotion`, a motion clip | fully | C1 `clip_present` — `MOTIONSET_ASSET_ABSENT path=` / `MOTIONSET_WRONG_CLASS path=` | unconditional | the clip's CONTENT — deliberate and disclosed in the prompt (no scripting route exists to write curve data) |
| 2 | produce `AM_TaskAction`, an assembled action | fully | C2 `montage_present` — same token family | unconditional | slot names, blend times, segment count beyond the first |
| 3 | produce `ABP_TaskLogic`, the per-frame logic asset | fully | C3 `animbp_present` — same token family | unconditional | its graph contents — deliberate; authoring graph nodes is not reachable from stock editor scripting |
| 4 | each of the three is built for `SK_TaskRig`, not another rig | fully | C4-C6 `clip_uses_task_rig` / `montage_uses_task_rig` / `animbp_uses_task_rig` — `MOTIONSET_WRONG_RIG expected=` | skipped only when its own asset is missing, which C1-C3 already fail (`MOTIONSET_ANCHOR_UNCHECKABLE`) | nothing — the rig reference is a single object ref, so "exactly one rig" is a property of the type |
| 5 | the assembled action really plays the clip you made | fully | C7 `montage_plays_the_clip` — `MOTIONSET_LINK_WRONG expected=` | skipped only when the montage is missing (`MOTIONSET_LINK_UNCHECKABLE`) | which segment/slot holds it beyond the first reference |
| 6 | save all three where they are named | fully | no separate check by design — the runner grades a file overlay, so an unsaved asset presents as no file and fails C1-C3 | unconditional | nothing |
| 7 | do not rename, move, modify or delete the rig | **not asserted** | none — and deliberately so | n/a | **the accepted residual**: the submission overlay is COPY-ONLY, so a deleted rig is restored before grading and the check could never fail (a dead gate). Overwriting the rig cannot help either: C4-C6 compare the rig's PATH, which an overwrite does not change. The instruction stands to keep submissions tidy, not because a gate backs it. |

**Holes this table found: none that lack a defense.** Row 7 is the only
unasserted requirement, and it is unassertable-by-construction rather than
unguarded — the overlay semantics make its failure state unreachable. Rows 1-6
each name a live gate.

## Matrix

**This is the only table in this file that carries variant rows.** The
requirements table above carries none — see the parser traps.

| Submission | Overall | Fails at (check id) | Expected substring | Also fails (recorded, not matched) | Anti-gaming note |
|---|---|---|---|---|---|
| `../reference` | PASS | — | all 7 checks green (7/7) | — | — |
| empty | FAIL | `clip_present` | `MOTIONSET_ASSET_ABSENT path=` | every other check — 0/7: the two sibling `MOTIONSET_ASSET_ABSENT`, three `MOTIONSET_ANCHOR_UNCHECKABLE`, and `MOTIONSET_LINK_UNCHECKABLE` | FR-017 |
| `montage-plays-the-wrong-clip/` | FAIL | `montage_plays_the_clip` | `MOTIONSET_LINK_WRONG expected=` | — (no other check failed) | **MEASURED 6/7 in the authoring boot, self-graded by the real grader; harvested only because it isolates that one check.** **the leg that separates C7 from the anchor checks.** All three rig anchors PASS (measured) — the decoy clip lives on the SAME task rig, so the montage still anchors correctly; pointing it at the stock clip would also break C5 and destroy the isolation. What a submission looks like when it authors two clips and wires the montage to whichever it made last. |
| `duplicate-the-shipped-set/` | FAIL | `clip_uses_task_rig` | `MOTIONSET_WRONG_RIG expected=` | `montage_uses_task_rig` and `animbp_uses_task_rig` (both `MOTIONSET_WRONG_RIG`), plus `montage_plays_the_clip` (`MOTIONSET_LINK_WRONG` — the duplicated action plays the stock clip). C1-C3 PASS — **3/7** | #1 duplicate-instead-of-author |

**Why the third leg is the important one.** It is the cheapest wrong answer
available — three `duplicate_asset` calls — and it is the one a naive version of
this task would have waved through. Measured at authoring time on 2026-08-14:
all three duplicates report
`/Game/Characters/Mannequins/Meshes/SK_Mannequin`, and none reports the task rig.

**Without the task-owned rig this leg would score 6/7**, failing only
`montage_plays_the_clip` (the duplicated montage plays the stock clip, not
`A_TaskMotion`) — so the three anchor checks, 43% of the score, would have been
DEAD, and the cheapest wrong answer would have presented as a near-miss rather
than a clear miss. That is why the rig is shipped.

*(An earlier draft of this paragraph said 7/7. Corrected 2026-08-14 by code
review, which recomputed the counterfactual instead of taking it on trust. The
number was wrong in the direction that flattered the design — 6/7 is a weaker
claim about how badly the naive task fails, and a stronger one about why the rig
is necessary, since a near-miss is harder to notice than a clear miss.)*

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task python/kp-motion-set-shares-one-rig
```

No `--wip`: the committed tree must discriminate, not someone's disk. Grade a
single leg directly:

```sh
python tools/verify-single/run_task.py \
    --task tasks/python/kp-motion-set-shares-one-rig/task.md \
    --submission tasks/python/kp-motion-set-shares-one-rig/discrimination/duplicate-the-shipped-set \
    --ue-root <UE_5.8>
```

## Status

**VALIDATED 2026-08-14** (Windows, UE 5.8). Both committed-tree runs are in:

- `cb refgate python/kp-motion-set-shares-one-rig` — **PASS 7/7**, 184s.
- `cb discriminate` with NO `--wip` — **discriminated YES, 3/3 legs at their
  named checks**: reference PASS, empty 0/7, `duplicate-the-shipped-set` 3/7.

The dated row is in the dated validation table (internal, not shipped), which is the status authority.
Recorded for the next reader: the reference was ALSO verified 7/7 read FROM DISK
in a fresh headless editor rather than in the session that authored it — the
distinction earned its keep, because the spike had found a read route that works
on shipped assets and raises on same-session ones.
