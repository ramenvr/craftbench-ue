# Discrimination matrix — t2-datatable-csv-export

The self-validation oracle: the reference solution must PASS and every gaming
variant + the empty leg must FAIL **at the predicted check, via the named
substring**. A wrong-reason FAIL (L1 build failure, a different check, a
`0`-check/`error` L2I verdict, SANDBOX-REJECT exit 4) means the verifier is NOT
discriminated.

Unusually for an asset task, **every leg of this matrix is plain text**: the
deliverable is three `.csv` files, so the reference and all three variants are
fully authored in this tree. Only the three baseline `DataTable` `.uasset`s
(the substrate side, `../notes.md` §1) are binary-half work.

## Parser + L2I traps this matrix is written against (imported-set precedent)

- **ONE parseable table with variant rows** — a second table repeating a label
  would overwrite the first with a blank substring set. Secondary observations
  live in prose.
- **Every "Expected substring" cell is a backtick-wrapped literal containing a
  space** (`_extract_substrings` drops space-less bareword ticks).
- Substrings are matched against the **raw `detail` string inside the
  CRAFTBENCH-INTROSPECT-JSON block**, and every cell below is a literal printed
  by `tools/verify-single/introspect/datatable_csv_export.py`.
- **Exactly ONE introspect script per task** (`registry.py` keeps only
  `li_last_log`).
- **ASCII rule**: all substrings ASCII; the grader is ASCII by construction.
- **Error tokens are disjoint from failure tokens**: `*_TABLE_MISSING`,
  `*_TABLE_LOAD_FAILED`, `*_PROBE_ERROR` (incl. `*_TAMPER_PROBE_ERROR`),
  `*_READ_ERROR`, `*_ABORTED`, `CHECK_NOT_EVALUATED` appear in no row below —
  a broken UE API or a missing BASELINE can never be credited as a variant's
  named failure. (Honesty: they still GRADE exit 1 today; "uncredited" is a
  matrix property, not a taxonomy routing — notes.md §3.) Asserted by
  `tools/verify-single/tests/test_introspect_datatable_csv_export.py::TestErrorTokensAreDisjointFromMatrix`.

## Layout (agent-writable prefixes only)

- `../reference/Content/Tasks/t2-datatable-csv-export/exports/*.csv` — the one
  correct solution (three files).
- `<variant>/Content/Tasks/t2-datatable-csv-export/exports/*.csv` — one dir per
  gaming shape, sibling to this file.
- empty leg — run implicitly by `cb discriminate`. The exports are 100%
  agent-produced (the baseline ships only the `data/` tables), so the expected
  empty vector is **0/13**.

## Matrix

**This is the only table in this file that carries variant rows.**

| Submission | Overall | Fails at (check id) | Expected substring | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | PASS | — | all 13 checks green (13/13) | — |
| empty | FAIL | `items_csv_present` | `ITEMS_CSV_MISSING Content/Tasks/` | #1 / FR-017 |
| `missing-table/` | FAIL | `tuning_csv_present` | `TUNING_CSV_MISSING Content/Tasks/` | #3 only the easy tables exported |
| `wrong-values/` | FAIL | `waves_values_match` | `WAVES_VALUES_WRONG mismatches=` | #2 plausible hand-typed values |
| `header-only/` | FAIL | `items_rows_match` | `ITEMS_ROWS_WRONG got=` | #4 stub files with the right names |

Secondary fan-out, in prose so no label re-registers:

- **empty** fails all 13: each table's quartet roots on its own
  `*_CSV_MISSING` token, and `no_extra_csvs` fails `EXPORTS_DIR_ABSENT`
  (the folder was never created). 0/13 is the expected empty score.
- **missing-table/** fails exactly the tuning quartet (4 checks): present roots
  the other three. `no_extra_csvs` PASSES — its gate is extras-only; absence is
  `tuning_csv_present`'s job. 9/13.
- **wrong-values/** fails exactly ONE check (12/13): the single edited cell
  (`Wave2` `EnemyCount` 9→7 in `DT_EvalWaves.csv`) survives presence, structure
  and row-name checks and dies only at the engine round-trip compare. That is
  the leg proving the values gate carries independent discriminating power.
- **header-only/** fails `*_rows_match` + `*_values_match` on all three tables
  (7/13): structurally valid CSVs with the right headers and no data rows.

Coverage bounds (argued, not run as separate submissions):

- A submission whose CSVs differ only cosmetically from the tables — row
  ORDER, quoting, float formatting — **PASSES by design**: acceptance is the
  engine round-trip (fill a transient table from the agent CSV, canonical-
  export both sides, compare order-insensitively). Asserted offline by
  `TestRoundTripSemantics::test_row_order_does_not_matter`.
- A submission dumping EXTRA files into `exports/` (a combined dump, logs)
  dies at `no_extra_csvs` (`EXPORTS_DIR_EXTRA_FILES files=`) — covered by the
  offline oracle rather than a fifth variant tree.
- A CSV the engine's importer refuses (mangled quoting that still parses
  loosely) dies at `*_values_match` via `*_CSV_NOT_INGESTIBLE` — an export a
  consumer cannot re-import is not an export. Oracle-covered.
- A renamed row dies at `*_rows_match` (`*_ROWS_WRONG got=`) — oracle-covered
  (`test_a_renamed_row_fails_the_rows_gate`).
- **A submission that rewrites the baseline TABLES to match lazy files dies
  at `*_values_match` via `*_BASELINE_TAMPERED`** — both compares run against
  the truth PINNED inside the verifier-owned grader, never the live tables
  (the gold-leak defense, notes.md §1.5). Oracle-covered
  (`TestPinnedTruthDefeatsBaselineTampering`) rather than authored as a
  binary `.uasset` variant; no MATRIX row credits the tamper token, and the
  oracle also pins that it appears on no clean leg.

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task bp/t2-datatable-csv-export --wip   # pre-commit
```

Per-leg fallback while iterating (short workdir dodges MAX_PATH; use `py`,
this box resolves `py -3.12`):

```sh
py -3.12 tools/verify-single/run_task.py \
    --task tasks/bp/t2-datatable-csv-export/task.md \
    --submission tasks/bp/t2-datatable-csv-export/discrimination/wrong-values \
    --ue-root "C:\Program Files\Epic Games\UE_5.8" --workdir C:\cb\wd\dtexp   # expect exit 1
```

L2I graders are read from the LIVE working tree, so grader iteration needs no
commit; the baseline `.uasset`s DO need committing before a non-`--wip` grade
sees them.

## Status
- Authored 2026-07-30 (text half + adversarial-review fixes same day).
- **EXECUTED 2026-07-30**: `cb discriminate --task bp/t2-datatable-csv-export --wip` =
  **discriminated: YES** — reference PASS; empty, header-only, missing-table, wrong-values all FAIL (5/5), each `[ok ]` (credited via its named
  substring). Calibration record in ../notes.md.

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span in the gate column is a contiguous literal from the emitted
`detail` string of a named check in the verifier-owned grader
`tools/verify-single/introspect/datatable_csv_export.py` (this task is `layers:
[L1, L2I]` — there is no L2 fixture; the check id is the durable join key), except
row 10 (the runner's `tools/verify-single/sandbox.py`, exit 4) and row 12 (the L1
build layer, no token — UBT exit codes are the signal). The grader emits exactly 13
checks on every leg; a check that cannot run still FAILS (fan-out root token), so
"gate skipped when" below means "reports the upstream token instead of its own",
never "silently green".

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | export EVERY table in `data/` — all three of `DT_EvalItems`, `DT_EvalWaves`, `DT_EvalTuning` produce a file | fully, per table | `items_csv_present` / `waves_csv_present` / `tuning_csv_present` — `ITEMS_CSV_MISSING Content/Tasks/` (siblings `WAVES_` / `TUNING_`) | unconditional (first check of each table's quartet; a filesystem probe exception fails the whole quartet closed) | nothing on presence itself; each absent file roots its own quartet, so "only the easy tables" can never pass (anti-gaming #3) |
| 2 | each file named exactly `<TableName>.csv` | fully, by a PAIR of gates | `<t>_csv_present` (the path is built from the pre-declared name, never scanned) + `no_extra_csvs` — `EXPORTS_DIR_EXTRA_FILES files=` (any not-exactly-expected name lists as an extra) | never — both halves run on every leg | on Windows's case-insensitive filesystem a wrong-CASED name (`dt_evalitems.csv`) satisfies `os.path.isfile` in the presence half — it is the extras half's case-sensitive `not in EXPECTED_FILES` membership that restores exactness; on a case-sensitive box the presence half fails instead. Net: nothing |
| 3 | all files in `Content/Tasks/t2-datatable-csv-export/exports/` (folder created by the agent) | fully | `<t>_csv_present` joins on that exact folder; a never-created folder additionally fails `no_extra_csvs` — `EXPORTS_DIR_ABSENT ` (composed: `"EXPORTS_DIR_ABSENT %s" % EXPORTS_DIR_REL` appends the folder rel-path) | never | CSVs written anywhere else are simply invisible to the grader (they fail presence); duplicate copies elsewhere INSIDE the task folder are unconstrained — the prompt only forbids extras in `exports/` itself |
| 4 | nothing else in the `exports/` folder | fully | `no_extra_csvs` — `EXPORTS_DIR_EXTRA_FILES files=` (`os.listdir` — subdirectories count as extras too) | never (runs even when the folder is absent — then `EXPORTS_DIR_ABSENT`) | junk anywhere OUTSIDE `exports/` but inside the task folder (a scratch dir, a README beside `exports/`) — the gate lists exactly one directory (anti-gaming #5 covers only the declared folder) |
| 5 | each file is a real CSV (implied by "a CSV file"): a header plus consistently-shaped data lines, >= 2 columns | fully | `<t>_csv_parses` — `_CSV_UNPARSEABLE ` (composed: `"%s_CSV_UNPARSEABLE %s in %s"` with per-table prefix ITEMS/WAVES/TUNING; detail carries the structural reason and the rel-path) | file absent (row 1's fan-out root `*_CSV_MISSING` fails this check too) | any consistently-shaped junk table parses — it dies one gate later at `<t>_rows_match`; encoding latitude: UTF-8-BOM tolerated, undecodable bytes fall back to latin-1 before the csv parse |
| 6 | "every row" — the file carries exactly the table's row names | fully, order-insensitive | `<t>_rows_match` — `ITEMS_ROWS_WRONG got=` (compared sorted against the truth PINNED inside the grader, never the live table) | file absent or unparseable (fan-out) | row ORDER is free by design (sorted compare); the row-name column's HEADER label is ignored (`---` vs anything — producer-defined); duplicated or renamed row names FAIL (the sorted lists diverge) |
| 7 | "every column, every value" — cell content matches the table exactly | fully | `<t>_values_match` — `WAVES_VALUES_WRONG mismatches=` (siblings `ITEMS_` / `TUNING_`); acceptance is the engine round-trip: agent CSV and PINNED truth each fill a transient table, both canonically re-export, compare header-exact + data lines as an order-insensitive set | file absent/unparseable (fan-out); tamper gate fires first (row 9); baseline table unloadable (verifier-side `*_TABLE_MISSING` / `*_TABLE_LOAD_FAILED` — still a failed check, but uncreditable) | cosmetics the engine itself normalizes: quoting, float formatting (`8.50` vs `8.5`), row order — all pass BY DESIGN; the pure-python fallback route additionally tolerates numerically-equal spellings via `float()` compare |
| 8 | the file "could stand in for the table" — a consumer could re-import it | fully on the primary route | `<t>_values_match` — `_CSV_NOT_INGESTIBLE the engine importer rejected ` (composed: per-table prefix interpolated ahead of the literal) (the engine's own `fill_data_table_from_csv_string` returning False is the graded refusal) | same fan-outs as row 7; ALSO when the transient-table route is broken (engine API unavailable): the fallback is a pure csv-module dict-compare, which cannot observe engine-ingestibility | on the fallback route only, a file the engine would refuse but that csv-parses into matching row-dicts passes — documented residual (task spec + notes.md §5), reachable only when the engine API itself is broken, never by submission content |
| 9 | "do not modify the tables themselves" | fully at content level | tamper gate inside `<t>_values_match`, evaluated BEFORE the file compare — `_BASELINE_TAMPERED ` + detail `table_diverges_from_pinned` (composed: two source literals joined at emit — `"%s_BASELINE_TAMPERED %s" % (prefix, tamper_report)`) (live table's canonical export vs the PINNED truth; an unresolvable probe fails closed as `*_TAMPER_PROBE_ERROR`) | the table's file absent/unparseable fan-out fires first (the leg still FAILS, just with the upstream token); table deleted is impossible — the overlay is copy-only, so absence is verifier-side `*_TABLE_MISSING` | a byte-different but content-identical re-save of a `.uasset` (same rows, same values) passes — behavior-only by design; package-identity abuse and redirectors are the asset-integrity preamble's job (prepended `asset_integrity` checks), not this gate's |
| 10 | "do not modify... anything outside `Content/Tasks/t2-datatable-csv-export/`" — outside the sandbox-writable set entirely (verifier module, `Content/Maps/`, `Plugins/`, the `.uproject`, non-allowlisted `Config/`) | fully, pre-layer | runner sandbox (`tools/verify-single/sandbox.py` + `UE-projects/ThirdPerson/AGENT_WRITABLE.json`) — `sandbox: REJECTED` (exit 4; deny wins, config edits diff-validated against a `config_allow` this spec does not declare, so any ini change also rejects) | never — sandbox screening precedes every layer | nothing at those prefixes |
| 11 | "do not modify... anything outside `Content/Tasks/t2-datatable-csv-export/`" — writes INSIDE the sandbox-writable set but outside the task folder (`Source/ThirdPerson/**` edits/additions, stray assets under `Content/Tasks/<other-id>/`, `Content/Blueprints/`, `Content/Generated_*`) | **NOT ASSERTED** | — no gate exists: no L2I check reads anything outside `data/` + `exports/`, and the sandbox accepts these prefixes by design (they are the substrate's writable lanes) | n/a | a submission may ship arbitrary compiling C++ into `Source/ThirdPerson/` or park assets in other writable Content folders and still PASS 13/13 — only L1 (it must still build) and fairness isolation bound it. Nearest indirect cover: editing this task's OWN row structs (`Source/ThirdPerson/Tasks/t2-datatable-csv-export/EvalTableRows.*`) changes the live tables' canonical export and trips row 9's tamper gate — but any behavior-neutral or unrelated Source write is ungated |
| 12 | implicit precondition (verifier spec: "content-plus-text submissions must not break the build") | fully | L1 — UnrealBuildTool exit 0 for BOTH `ThirdPersonEditor Win64 Development` and `ThirdPerson Win64 Development` (no token; the layer short-circuits L2I on failure) | never (gating layer; L2I `requires` it) | anything that compiles — L1 asserts buildability, not restraint (see row 11) |
