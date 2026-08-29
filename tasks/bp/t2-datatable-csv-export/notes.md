# t2-datatable-csv-export — build contract + verifier design notes

Maintainer-only. The agent never sees this file.

## §0 Dead-gate audit (values chosen so no gate passes vacuously)

Every graded value is non-default (a fresh row struct default-initializes to
`""` / `0` / `0.0` — nothing in the pinned data equals a default), distinct
per row, and **exactly float-representable** (fractions limited to .5 / .25
/ .75), so:

- `*_rows_match` cannot pass on an empty or template table (row names are
  task-specific words, not `NewRow`);
- `*_values_match` cannot pass on fabricated defaults (no cell is `0`, `1`,
  or an engine default), and can never FAIL on decimal formatting — every
  pinned float round-trips bit-exact through text in both directions;
- `no_extra_csvs` is live on any submission that writes anything beyond the
  three names (the natural failure of "export everything into one dump").

## §1 Baseline build contract (binary half; `aids/author_DT_baselines.py`)

Three DataTable assets under
`UE-projects/ThirdPerson/Content/Tasks/t2-datatable-csv-export/data/`:

| asset | row struct (`/Script/ThirdPerson.…`) | rows (name: values) |
|---|---|---|
| `DT_EvalItems` | `EvalItemRow` (DisplayName str, Cost int32, Weight float) | Sword: "Iron Sword", 250, 8.5 · Shield: "Oak Shield", 180, 12.25 · Potion: "Healing Draught", 35, 0.5 · Torch: "Pine Torch", 12, 1.75 |
| `DT_EvalWaves` | `EvalWaveRow` (EnemyCount int32, SpawnInterval float) | Wave1: 5, 2.5 · Wave2: 9, 1.75 · Wave3: 14, 1.25 |
| `DT_EvalTuning` | `EvalTuningRow` (Value float) | PlayerSpeed: 640 · JumpHeight: 420 |

**THE single source of truth is `BASELINE_CSVS` in the aids script.** The
reference CSVs and the offline oracle both derive from it; the oracle test
`test_reference_files_match_the_aids_pinned_literals` fails on any drift. Edit
all three together or not at all.

The aids script is the dawn-fog authoring mold: create (DataTableFactory with
the struct) → fill from the pinned CSV → verify row names → save → **grade
in-process with the real grader**, twice: stage 1 expects the empty vector
(0/13, all agent-side `*_CSV_MISSING` tokens, NO verifier-side token — this is
the grader's first live contact and proves the baseline reads); stage 2
overlays `reference/…/exports/`, expects 13/13, then deletes the overlay so
the substrate ends baselines-only. `DTEXPORT-DONE` is the success marker.

Commit the three `.uasset`s promptly (fairness isolation moves untracked
`Content/Tasks/<id>/` trees on a later drive of a different task; grading
reads git HEAD).

## §1.5 The pinned-truth defense (adversarial-review BLOCKER fix, 2026-07-30)

The baseline tables live INSIDE the agent-writable carve-out
(`Content/Tasks/<id>/data/`), so the first draft of this grader — which read
its expected side off the LIVE tables — was gameable: overlay three valid
EMPTY DataTables plus three header-only CSVs and every live-vs-file compare
is empty-vs-empty (the gp-gas-launch gold-leak shape). The fix:

- the grader carries its own verifier-owned copy of the truth
  (`PINNED_CSVS` in `datatable_csv_export.py`) and grades BOTH the agent's
  files AND the live tables against it;
- a live table diverging from the pinned truth is the graded
  `*_BASELINE_TAMPERED` failure, folded into `<t>_values_match`'s fail path
  (denominator stays 13). It is agent-caused BY CONSTRUCTION:
  `apply_submission` is a copy-only overlay, so only submission bytes can
  change a committed baseline — and it cannot DELETE one, which is why a
  missing table remains the verifier-side `*_TABLE_MISSING`;
- `<t>_rows_match` compares against the pinned row names (engine-free), so
  even a gutted live table cannot blank the expected side.

Three copies of the truth now exist (grader `PINNED_CSVS`, aids
`BASELINE_CSVS`, the reference CSVs). The offline oracle pins BOTH pairings
(`test_grader_pinned_truth_matches_the_aids_literals`,
`test_reference_files_match_the_aids_pinned_literals`), so drift fails
offline before any editor session.

## §2 Why the values gate is an engine round-trip

The acceptance must be *"a consumer could re-import this file and get the same
table"* — that is what an export IS. Comparing raw file bytes against one
blessed rendering would fail correct submissions over quoting, float
formatting, or row order (all producer-defined cosmetics), and hand-rolling a
tolerant text diff re-implements the engine's CSV dialect badly. So:

1. fill a TRANSIENT `DataTable` (same row struct) from the agent's file via
   the engine importer — refusal is the graded `*_CSV_NOT_INGESTIBLE`;
2. canonical-export BOTH tables via the engine exporter;
3. compare: header exactly, data lines as an order-insensitive sorted set.

Cosmetics normalize through the one exporter; content differences never do.
Fallback (route 2, only if route 1's APIs break): parse both the agent file
and the live table's canonical export with the csv module and compare
row-name-keyed / column-name-keyed with float-tolerant cells. Both routes
broken → `*_ROUNDTRIP_PROBE_ERROR`, an uncreditable verifier-side token.

## §3 Check inventory (13, constant on every leg)

Per table t ∈ {items, waves, tuning}: `<t>_csv_present` (filesystem),
`<t>_csv_parses` (csv-module structure), `<t>_rows_match` (row-name column vs
`get_data_table_row_names`), `<t>_values_match` (§2). Plus `no_extra_csvs`
(extras-only gate: missing files are `_csv_present`'s job, so the
missing-table variant fails exactly 4 checks, not 5). The grader emits
exactly 13 named checks on every leg; the runner's asset-integrity preamble
may prepend failed `asset_integrity` checks on violating submissions, so
report-level totals can exceed 13.

Fan-out rules: absent file roots its quartet on `*_CSV_MISSING`; unparseable
file roots rows+values on the parse token; a missing BASELINE hits ONLY
`<t>_values_match` (rows compare against the pinned truth and are
engine-free), with the uncreditable `*_TABLE_MISSING` token.

**Set-convention honesty caveat (verdict taxonomy):** `*_TABLE_MISSING`,
`*_TAMPER_PROBE_ERROR` and `*_ROUNDTRIP_PROBE_ERROR` are `passed: false`
checks inside a well-formed verdict block — the layer status is `fail` and
the run GRADES exit 1 against the MODEL today. Only a missing or malformed
verdict block routes to harness-error exit 7. "Uncreditable" means no MATRIX
row credits these tokens (an API break can never masquerade as a variant's
named failure); it does not mean they don't score. A future runner-side
routing rule may reclassify them; until then this is the honest state
(same caveat as the wave-1/2 fixture HARNESS-PRECONDITION paths).

## §4 Landing gate

Do NOT add the CATALOG/registry rows before (1) the three baseline `.uasset`s
are committed, (2) the aids script's stage-1/2 in-process grades are green
(the calibration record below is filled), and (3) one full
`cb discriminate --wip` run credits every leg. The registry pass is batched at
the wave-3 commit window (parent session owns it).

## §5 Calibration checklist (runtime-unproven; resolve at the binary half)

1. **Transient-table construction** — `unreal.new_object(unreal.DataTable)`
   plus `RowStruct` assignment (plain attribute first — the imported-set
   `skm.skeleton` EditConst precedent — then `set_editor_property`). If both
   refuse, the grader's fallback route carries the task (route 2 needs only
   exporter + csv module); confirm which route stage 2 actually used via the
   `roundtrip=engine|fallback` fragment in the 13/13 details.
2. **Canonical export header format** — the reference CSVs write `---` as the
   row-name header cell on the belief that `export_data_table_to_csv_string`
   does the same. Nothing gates on it (fill ignores the first header cell;
   the canonical compare normalizes both sides through one exporter), but
   confirm and correct the reference files if the live exporter differs.
3. **`fill_data_table_from_csv_string` return shape** — bool assumed; a
   tuple's first element is taken. Stage 1/2 exercise both fill sites.
4. **`export_data_table_to_csv_string` return shape** — str assumed; a
   tuple's last element is taken.
5. **Float text fidelity** — pinned values are exactly representable, so both
   exporters must render them stably; stage 2's 13/13 proves it end-to-end.
6. **DataTableFactory struct property spelling** — `struct` assumed
   (`factory.set_editor_property("struct", …)`); the aids script dies loudly
   if refused.

## §6 Offline oracle summary

`tools/verify-single/tests/test_introspect_datatable_csv_export.py` — fake
`unreal` (tables as row-dicts, importer/exporter = csv module), legs read the
SHIPPED reference/variant files and fill fake baselines from the aids
literals. Pins: reference 13/13; empty 0/13; per-variant credited substring on
the predicted check; failure budgets (13/4/1/6); round-trip order/quoting
insensitivity; changed-value and renamed-row failures; baseline-missing
uncredited; importer-refusal graded; broken-exporter → PROBE_ERROR; broken
transient construction → fallback still passes the reference; ASCII purity;
automation-marker absence; error-token/matrix disjointness.

Tamper coverage added with the pinned-truth fix: gutted live
tables + header-only CSVs fail with `*_BASELINE_TAMPERED` (never
13/13); a tampered table fails even a pinned-perfect reference; the
tamper token appears on no clean leg; grader/aids/reference truth
copies are drift-pinned both ways.

## Calibration record — first live validation

Not yet run. To be filled from the aids script's stage-1/2 log lines
(`DTEXPORT-VECTOR …`) and the first `cb discriminate --wip`: per-leg
verdicts, which round-trip route graded (engine or fallback), and the live
canonical header format (§5.2).

## Calibration record — first live validation (2026-07-30)

Binary half + full matrix ran this date (Win11, UE 5.8, substrate=live via
`--wip`): **`cb discriminate` = discriminated: YES** — reference PASS; empty +
EVERY variant FAIL via its named MATRIX substring (`[ok ]` on all legs).
Editor-target builds of the scaffold/fixture C++ were clean; per-leg run dirs
not retained (no `--keep`) — the verdicts answer the checklist's yes/no items.

Wave-3 specifics resolved by the run: the aids script's in-process grades were
the grader's first live contact — stage 1 (baselines only, no submission) =
0/13 with no verifier-side tokens; stage 2 (reference overlay) = **13/13**,
`roundtrip=engine` (the transient-DataTable round-trip route worked; the
dict-compare fallback was not needed). The pinned-truth defense shipped
(BASELINE_TAMPERED tokens) after review; the matrix proves the four graded
failure shapes.
