# Discrimination matrix — kp-typed-input-bindings

The self-validation oracle, in the amended §7 shape (owner decision
2026-08-11): the **automatic legs** (reference PASS, empty FAIL at the named
substring) plus the **requirements table** mapping every prompt requirement to
the assertion that enforces it. **No hand-authored variant is shipped** — the
table found no requirement without a live gate (see the audit column), and per
§7 a variant is authored only for a hole this table actually finds.

> **STATUS: RUNNABLE (reference leg PROVEN 2026-08-11).** reference authored + self-graded 14/14 by aids/author_reference.py, harvested, committed 39433c2, and `cb refgate` graded the committed reference PASS from git HEAD (161 s, 2026-08-11).
> Remaining before full certification: the empty-FAIL leg and the
> requirements-table spot checks ride the next `cb discriminate` run.

## Parser traps this matrix is written against

- **ONE parseable row per label.** `discriminate.parse_matrix` returns
  `Dict[label -> MatrixRow]`, and ANY markdown table row whose first cell
  contains a `<name>/` span (the `_VARIANT_DIR_RE.search` branch), starts
  with "empty", or resolves to a reference form registers a label — a
  colliding row in a *second* table silently overwrites the first, usually
  with a blank substring tuple. This file therefore keeps **every first-column
  cell of the requirements table slash-free** (short `R<n>` ids + slash-free
  prose; all paths live in later columns), so only the matrix table below
  registers labels.
- **Every "Expected substring" cell is a backtick-wrapped literal containing
  a space or one of `(),.=`** — that keeps `_extract_substrings` on its
  substantive branch, where the cell is matched verbatim against the raw
  `detail` inside the `CRAFTBENCH-INTROSPECT-JSON` block (not the layer's
  note rendering).
- **The reference row's substring cell is `—`** (empty tuple; a PASS row must
  not seed an expected substring).
- **ASCII rule:** every expected substring is ASCII-only (the UE log's UTF-8
  read back as cp1252 turns non-ASCII into mojibake and the grep misses —
  the t2-homing-projectile live incident).
- **Static-oracle rule:** every expected substring below is a span that lives
  **inside ONE source literal** of
  `tools/verify-single/introspect/kp_typed_input_bindings.py` — never a
  span that crosses a printf placeholder or a concatenation. The
  missing-asset tokens embed their full content path in a single literal for
  exactly this reason.
- **Error tokens are uncreditable.** Every exception path in the script emits
  `*_READ_ERROR` / `*_PROBE_ERROR` / `*_CLASS_PROBE_ERROR` / `*_ABORTED`,
  none of which appears in any row below — a broken UE API name shows up as
  an uncredited FAIL, never as a credited named failure. (Observed directly:
  with no `unreal` module all 14 checks fail as `IA_*_PROBE_ERROR` /
  `IMC_PROBE_ERROR`, which no row claims.)

## Layout

- `../reference/Content/Tasks/kp-typed-input-bindings/` — the one correct
  solution: `IA_Move.uasset`, `IA_Zoom.uasset`, `IA_Jump.uasset`,
  `IMC_Bindings.uasset` (pending the authoring-lane run).
- empty leg — run IMPLICITLY by `cb discriminate` (throwaway empty dir;
  nothing to author). This task ships **no baseline asset**, so the empty leg
  is a genuinely empty deliverable and scores 0/14.
- No variant dirs (amended §7; see the audit column for why none was needed).

## Matrix

**This is the only table in this file whose rows register labels.**

| Submission | Overall | Fails at (check id) | Expected substring | Notes |
|---|---|---|---|---|
| `../reference` | PASS | — | — | all 14 checks green (14/14) |
| empty | FAIL | `ia_move_asset_exists` | `IA_MOVE_MISSING /Game/Tasks/` | first gate of the emission order; the other asset gates fail on their own one-piece MISSING tokens and every dependent check fans out carrying its resolution token (0/14) |
| `zoom-left-boolean/` | FAIL | `ia_zoom_reads_axis1d` | `IA_ZOOM_VALUE_TYPE_WRONG value_type=` | **MEASURED 13/14 in the authoring boot, self-graded by the real grader; harvested only because it isolates that one check.** IA_Zoom is created but never typed, so it keeps the engine-default on-off reading. Its existence gate PASSES on purpose, and every other asset and binding is correct, so this is the single most likely real slip: one of three value types forgotten. |
| `s-swizzled-not-negated/` | FAIL | `map_s_move_swizzled_negated` | `MAP_S_MODIFIER_CHAIN_WRONG chain=` | **MEASURED 13/14 in the authoring boot, self-graded by the real grader; harvested only because it isolates that one check.** the S binding keeps its axis-swap but loses the sign flip — the only binding in the set that needs two modifiers rather than one. All six bindings exist, target the right actions, and are bound exactly once. |

## Requirements table (§7 soundness artifact)

One row per requirement in the agent-visible prompt. Column key: *asserted* =
fully / partially / NOT AT ALL; *pointer* = the enforcing check id in
`tools/verify-single/introspect/kp_typed_input_bindings.py` (all 14 check
ids live in its `CHECK_IDS` tuple; per-binding logic in `_binding_check`,
asset resolution in `_resolve_asset`); *skipped when* = the condition under
which the gate does not evaluate; *gets away with* = what a submission could
still do.

First-column cells are deliberately slash-free (parser trap #1).

| Req | Requirement (prompt language) | Asserted | Pointer (check id) | Skipped when | What a submission could get away with |
|---|---|---|---|---|---|
| R1 | IA_Move exists in the named folder as an input-definition asset | fully | `ia_move_asset_exists` | never — unconditional | nothing: absence, a non-loading file, and a wrong-class impostor carry distinct tokens |
| R2 | IA_Move carries a two-axis reading | fully | `ia_move_reads_axis2d` | never SKIPPED — when R1 fails it still FAILS, carrying R1's resolution token | nothing; the creation default (on-off) is outside the gate |
| R3 | IA_Zoom exists as an input-definition asset | fully | `ia_zoom_asset_exists` | never — unconditional | nothing |
| R4 | IA_Zoom carries a one-axis reading | fully | `ia_zoom_reads_axis1d` | never skipped; fails-forward on R3's token | nothing; default excluded |
| R5 | IA_Jump exists as an input-definition asset | fully | `ia_jump_asset_exists` | never — unconditional | nothing |
| R6 | IA_Jump carries an on-off reading | fully | `ia_jump_reads_boolean` | never skipped; fails-forward on R5's token | the creation default already satisfies the enum value (recorded in the spec's dead-gate table); the conjoined existence gate is the non-default fact, and a wrongly-typed IA_Jump still fails here |
| R7 | IMC_Bindings exists as an input-configuration asset | fully | `imc_asset_exists` | never — unconditional | nothing |
| R8 | exactly six key-to-intent bindings, these six and no others | fully | `imc_binding_count_is_six` plus the six exactly-once gates | never skipped; fails-forward on R7's token (or on an unreadable mapping array) | nothing: a seventh binding fails the count; six-by-duplication fails a per-key exactly-once gate |
| R9 | key W drives IA_Move with exactly the first-two-component swap | fully | `map_w_move_swizzled` | never skipped; fails-forward on R7's token | an explicit wrong swizzle ORDER that is still the default enum value cannot occur (order is read and compared); a swizzle with a non-default order fails the chain equality |
| R10 | key S drives IA_Move with the swap then the sign flip, in that order | fully | `map_s_move_swizzled_negated` | never skipped; fails-forward on R7's token | the sign flip's per-axis flags are not read (accepted residual — the prompt does not disclose them) |
| R11 | key A drives IA_Move with no transforms | fully | `map_a_move_plain` | never skipped; fails-forward on R7's token | trigger configuration is not read (accepted residual) |
| R12 | key D drives IA_Move with no transforms | fully | `map_d_move_plain` | never skipped; fails-forward on R7's token | same residuals as R11 |
| R13 | the mouse wheel axis drives IA_Zoom with no transforms | fully | `map_wheel_zoom_plain` | never skipped; fails-forward on R7's token | same residuals as R11 |
| R14 | the space bar drives IA_Jump with no transforms | fully | `map_space_jump_plain` | never skipped; fails-forward on R7's token | same residuals as R11 |
| R15 | each key appears in exactly one binding | fully | the six `MAP_*_KEY_NOT_BOUND_ONCE` branches of the per-binding gates | never skipped; fails-forward on R7's token | a stray binding of a key OUTSIDE the six (e.g. LeftShift) is caught by R8's exact count, not by a per-key gate |
| R16 | all four assets are saved in the named folder under exactly the names given | fully | the four `*_asset_exists` gates (the overlay materializes files; unsaved editor state presents as a missing asset) | never — unconditional | extra scratch assets beside the four are not failed (accepted residual; sandbox-bounded) |

**Audit outcome:** every requirement row reads *fully asserted, never
skipped* — the fan-out design converts "skipped" into "failed with the
upstream resolution token", which is the fail-closed direction. No hole ⇒ no
targeted variant authored. The three default-coincident gates (R6, the empty
chains inside R11-R14, the swizzle order inside R9) are recorded in the
spec's dead-gate table with the non-default fact each is conjoined with.

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task python/kp-typed-input-bindings --wip
```

Per-leg fallback while iterating (short `--workdir` dodges Windows MAX_PATH;
use the `py` launcher — this box's `py -3.12` does not resolve, use
`py -3.13`):

```sh
UE='<UE-root>'
py tools/verify-single/run_task.py \
    --task tasks/python/kp-typed-input-bindings/task.md \
    --submission tasks/python/kp-typed-input-bindings/reference \
    --ue-root "$UE" --workdir C:\cb\wd\kpeim       # expect exit 0
```

Then open the workdir's `report.json` and the L2I log it names, find the
`CRAFTBENCH-INTROSPECT-JSON-START` block, and confirm the check details.

**L2I graders are read from the LIVE working tree** (`registry.py` resolves
`introspect/` beside itself), so iterating on
`kp_typed_input_bindings.py` needs no commit — but the `.uasset` files DO
need committing before a non-`--wip` grade sees them (`run_task`
materializes the substrate from git HEAD).

## Status

- Authored 2026-08-11 from the task card, text-only track. **Never executed
  against a real editor** — no `.uasset` exists yet.
- **Proven offline, against the real logic.** The empty leg and a
  reference-shaped fake were run through the REAL grader with a simulated
  `unreal` module: empty = 0/14 with `IA_MOVE_MISSING /Game/Tasks/` printed
  verbatim; reference shape = 14/14; four wrongness probes (chain order
  swapped on S, W bound to the stock same-named action, W duplicated to 7
  bindings, everything left on-off-typed) each died at their predicted
  one-piece token. That is the LOGIC oracle, not an engine oracle.
- **Still missing, in order:** (1) the four reference `.uasset` binaries —
  `../aids/author_reference.py` builds, self-grades (requires 14/14), and
  harvests them; (2) live confirmation of the UE 5.8 property spellings the
  offline fake cannot settle (`value_type`, `mappings`, `key_name`, `order`,
  and the mapping-struct member spellings) — the grader tries several
  spellings each, but only an editor decides; (3) a `cb discriminate --wip`
  run, then the git-HEAD certified re-run after the binary commit.
