---
id: t2-datatable-csv-export
substrate: ThirdPerson
set: bp
tier: T2
capability_bucket: Gameplay Programming
category: other
layers: [L1, L2I]
introspect: [datatable_csv_export.py]
---

# t2-datatable-csv-export

The set's first `L1+L2I` task, built in the imported-set shape:
committed baseline assets → the agent produces a deliverable → **one**
verifier-owned introspect script asserts named structural checks. No map, no
fixture C++, no scaffold actor. Unusually, the DELIVERABLE here is plain text
(three `.csv` files), so the reference and every discrimination variant ship
fully authored; only the three baseline `DataTable` assets are binary-half
work.

### Provenance and deliberate divergences from the source row

Imported from an earlier internal task list (not shipped): a data-table export
row. Three divergences, recorded so the source row and the task reconcile:

1. **Verification replaced.** The source row's cell — "write a python script that
   does this correctly and check resulting exports against the output of what
   Aura exports" — grades one tool with another and is not deterministic. It
   is replaced by an engine ROUND-TRIP acceptance: the submitted CSV must be
   losslessly re-importable into a table identical to the baseline (verifier
   spec below). That is what "a correct export" observably means.
2. **Start state pinned.** The source row says "any project with datatables". This
   substrate ships none the agent may touch, so the task seeds three tables
   under the task's own content folder — which also makes "find all
   datatables" a bounded, fairness-prunable fact.
3. **Scope narrowed to the task folder.** "Find ALL datatables" project-wide
   would drag engine/plugin content in; the prompt scopes discovery to the
   task's `data/` folder (the row R4 `/Game/`-scoping precedent).

> **Note on the behavior-only rule (Hard Rule #2).** Per the asset-deliverable
> exception (imported-set precedent), the prompt names the concrete content paths and
> the exact output naming contract — the names ARE the observable. It never
> names an API, an editor operation, or the export mechanism: "produce a CSV
> file whose content matches the table" is the whole behavioral contract, and
> the agent may reach it through the editor UI, editor scripting, or by
> hand-writing the files.

## Primary concept

- `ps-data-driven-gameplay` — Data-Driven Gameplay Elements
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/data-driven-gameplay-elements-in-unreal-engine)

The load-bearing capability is reading structured game data out of the asset
form it actually lives in — enumerating tables, understanding row structs, and
serializing content faithfully enough that a consumer could re-import it.

## Prompt given to the agent

> The project ships three data tables under
> `Content/Tasks/t2-datatable-csv-export/data/` (`DT_EvalItems`,
> `DT_EvalWaves`, `DT_EvalTuning`). Export every data table in that folder to
> a CSV file:
>
> - one CSV file per table, named exactly `<TableName>.csv` (so
>   `DT_EvalItems.csv`, and likewise for the others);
> - all of them in a folder `Content/Tasks/t2-datatable-csv-export/exports/`
>   (create it), and nothing else in that folder;
> - each file's content must match its table exactly — every row, every
>   column, every value, so that the file could stand in for the table.
>
> Do not modify the tables themselves or anything outside
> `Content/Tasks/t2-datatable-csv-export/`.

## Workspace state pre-task

Substrate content that **exists** (committed, agent-writable via the
`Content/Tasks/` carve-out; fairness isolation keeps this task's folder while
hiding every other task's):

- `Content/Tasks/t2-datatable-csv-export/data/DT_EvalItems.uasset` — 4 rows
  (`Sword`, `Shield`, `Potion`, `Torch`), columns `DisplayName` (text),
  `Cost` (integer), `Weight` (decimal).
- `Content/Tasks/t2-datatable-csv-export/data/DT_EvalWaves.uasset` — 3 rows
  (`Wave1`..`Wave3`), columns `EnemyCount` (integer), `SpawnInterval`
  (decimal).
- `Content/Tasks/t2-datatable-csv-export/data/DT_EvalTuning.uasset` — 2 rows
  (`PlayerSpeed`, `JumpHeight`), column `Value` (decimal).
- `Source/ThirdPerson/Tasks/t2-datatable-csv-export/EvalTableRows.{h,cpp}` —
  the three row structs backing those tables. Read-only context; no C++ change
  is required or expected.

Files that **do not exist** (the agent must produce them):

- `Content/Tasks/t2-datatable-csv-export/exports/` and the three CSV files
  inside it.

The exact cell values are readable off the tables themselves and are not
repeated here — reading them is the task.

## Verifier specification

Layer choice: **L1 + L2I**. The deliverable is file content compared against
saved asset content — nothing to observe over time, so L2 is deliberately not
declared. L1 is a load-clean precondition (content-plus-text submissions must
not break the build).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development"
```

### L2I — Structural assertion

The verifier-owned script
`tools/verify-single/introspect/datatable_csv_export.py` runs headless under
`-nullrhi` and **emits exactly 13 named checks on every leg**; the runner's
asset-integrity preamble may PREPEND failed `asset_integrity` checks on
violating submissions, so report-level totals can exceed 13. PASS requires
every check. Per table (`items` / `waves` / `tuning`):

```text
<t>_csv_present      Content/Tasks/<id>/exports/<TableName>.csv exists
<t>_csv_parses       the file is structurally valid CSV: a header plus
                     consistently-shaped data lines
<t>_rows_match       the file's row-name column equals the PINNED truth's
                     row names
<t>_values_match     first the TAMPER GATE: the live table must still match
                     the PINNED truth (divergence = the graded
                     *_BASELINE_TAMPERED failure); then THE ACCEPTANCE: the
                     file, ingested by the engine's own importer into a
                     transient table, canonically re-exports IDENTICAL to the
                     PINNED truth's canonical export (header exact; data
                     lines as an order-insensitive set)
no_extra_csvs        exports/ contains nothing beyond the three expected files
```

**The ground truth is PINNED inside the verifier-owned grader**, never read
from the project: the baseline tables live inside the agent-writable
`Content/Tasks/` carve-out, so a grader trusting the LIVE tables could be
gamed by overwriting them with empty tables and shipping header-only CSVs
(empty-vs-empty compares clean — the gold-leak shape). Rewriting the
baselines is itself a graded failure via the tamper gate; it is agent-caused
by construction, because the submission overlay is the only thing that can
change a committed baseline (and, being copy-only, it cannot DELETE one —
which is why a MISSING table stays the verifier-side `*_TABLE_MISSING`).

Why the acceptance is a round-trip: both sides normalize through the ENGINE's
own importer+exporter, so quoting, float formatting and row order — cosmetics
the engine itself does not consider content — can never fail a submission,
while any changed cell always does. A file the engine's importer refuses
fails `*_values_match` as `*_CSV_NOT_INGESTIBLE`: an export a consumer cannot
re-import is not an export. If the transient-table route is unavailable
(`notes.md` §5), the compare falls back to a csv-module row-dict compare
against the pinned truth; only a full break reports `*_ROUNDTRIP_PROBE_ERROR`.

Verdict-taxonomy honesty (set convention): `*_ROUNDTRIP_PROBE_ERROR`,
`*_TAMPER_PROBE_ERROR` and `*_TABLE_MISSING` are `passed: false` checks
inside a well-formed verdict block — the layer status is `fail` and the run
GRADES exit 1 against the model today (only a missing/malformed verdict block
routes to harness-error exit 7). "Uncreditable" means no MATRIX row credits
these tokens, not that they do not score.

**Score granularity**: `report.json` carries `x/13` per the registry's
per-check counts; reported, not gating.

## Reference solution metadata

- LOC range: **0** lines of code; the deliverable is 3 text files (~4-6 lines
  each), shipped at `reference/Content/Tasks/t2-datatable-csv-export/exports/`.
- Files touched: 3 created, 0 modified.
- Senior-dev minutes: 5-15 (locate the tables, export or transcribe each,
  place the files).

## Anti-gaming notes

1. **Nothing exported, prose instead.** *Failure mode*: the agent reports
   success, or writes a README describing the tables, without producing the
   files. *Defense*: `<t>_csv_present` reads the filesystem at the pre-declared
   path (`ITEMS_CSV_MISSING Content/Tasks/`); a README in `exports/` also dies
   at `no_extra_csvs`.
2. **Plausible hand-typed content — or the tables rewritten to match it.**
   *Failure mode*: the agent fabricates values that look right instead of
   reading the tables; or, with editor tooling, overwrites the baseline
   tables themselves (they sit in the agent-writable carve-out) so that lazy
   files and gutted tables agree. *Defense*: both comparisons run against the
   truth PINNED inside the verifier-owned grader — a wrong cell prints
   `WAVES_VALUES_WRONG mismatches=` (or its siblings), and a rewritten
   baseline prints `*_BASELINE_TAMPERED` before the file is even considered.
   The pinned values are deliberately non-default and per-row distinct
   (dead-gate audit, `notes.md` §0), so no fabrication coincides with the
   truth.
3. **Only the easy table(s) exported.** *Failure mode*: one or two files ship
   and the claim covers all three. *Defense*: each table owns its own quartet
   of checks; the first absent file prints its own token
   (`TUNING_CSV_MISSING Content/Tasks/`).
4. **Stub files with the right names.** *Failure mode*: three files with
   correct headers and no rows (or empty files) satisfy any existence-only
   check. *Defense*: `<t>_rows_match` compares the row-name column against the
   live table (`ITEMS_ROWS_WRONG got=`); an outright empty file dies earlier at
   `<t>_csv_parses`.
5. **Junk alongside the deliverables.** *Failure mode*: the agent dumps a
   combined export, logs, or scratch files into `exports/`, gaming any
   "at least the three files exist" reading. *Defense*: `no_extra_csvs` allows
   exactly the three expected filenames (`EXPORTS_DIR_EXTRA_FILES files=`).

## Hidden invariants

- The three baseline values sets are exactly float-representable (`.5` / `.25`
  / `.75` fractions), so the values gate can never hinge on decimal-formatting
  luck — a mismatch is always a real content difference.
- Row ORDER inside a CSV is deliberately NOT content: the canonical compare
  sorts data lines. An agent exporting rows in a different order than the
  table's internal order is correct, and the offline oracle pins that.
- The exports are 100% agent-produced (the baseline ships only `data/`), so
  the expected empty-submission vector is **0/13** — unlike the imported-set tasks whose
  baselines leave some checks green on the empty leg.
- The grader emits exactly 13 named checks on every leg; a submission cannot
  improve its reported ratio by making checks unreachable. (The runner's
  asset-integrity preamble may prepend `asset_integrity` checks on violating
  submissions, so report-level totals can exceed 13.)
- Rows and values are graded against the PINNED truth, and the live tables
  are themselves graded against it (the tamper gate) — so neither editing the
  tables nor fabricating files can converge on a vacuous pass.
