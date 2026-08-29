# Discrimination matrix — kp-blueprint-actor-audit-report

Self-validation oracle for the first `tasks/python/` task, authored under the
**2026-08-11 amended section 7**: the mandatory artifacts are the automatic
reference-PASS / empty-FAIL legs plus the **requirements table** below — not
a variant per anti-gaming note. No hand-authored variant ships today because
the requirements table found no unenforced requirement; author one only if a
future audit of this table finds a hole (section 7a law).

> **STATUS: RUNNABLE (reference leg PROVEN).** reference authored via the MCP graph lane (edit_blueprint variables + python components/level/report), refgated PASS from git HEAD (159 s, 2026-08-12) after two grader-route fixes the gate itself caught.
> Remaining before full certification: the empty-FAIL leg and the
> requirements-table spot checks ride the next `cb discriminate` run.

## Parser traps honoured (inherited from the dawn-fog matrix)

- **ONE table with submission rows.** `discriminate.parse_matrix` keys rows
  by first-column label and a later table silently overwrites a repeated
  label with a blank substring tuple. The submission table below is the only
  one whose first column contains submission labels; the requirements table
  uses `R##` keys that collide with no submission dir.
- **Every expected-substring cell is backtick-wrapped and contains a space
  and `=`** (the `_extract_substrings` substantiveness rule), and each is a
  verbatim substring of the raw `detail` printed inside the
  `CRAFTBENCH-INTROSPECT-JSON` block.
- **The reference row's substring cell is `—`** (maps to the empty tuple).
- **ASCII rule**: every substring is ASCII-only (the cp1252 log read-back
  trap); the whole introspect script is ASCII by construction.
- **Error tokens are disjoint from failure tokens.** `*_PROBE_ERROR` /
  `*_READ_ERROR` / `*_WALK_ERROR` / `*_ABORTED` / `CHECK_NOT_EVALUATED`
  appear in no row here, so a broken UE API name can never be credited as a
  named failure (observed directly: with no `unreal` module all 20 checks
  fail as `AUDIT_BP_PROBE_ERROR` / `AUDIT_LEVEL_PROBE_ERROR` /
  `REPORT_PROBE_ERROR`, which no row claims).

## Layout

- `../reference/Content/Tasks/kp-blueprint-actor-audit-report/…` — the one
  correct solution (asset + level + `reports/audit.txt`), **pending the
  authoring-lane run** of `../aids/author_reference.py`. If the level saves
  One-File-Per-Actor, the overlay also carries
  `Content/__ExternalActors__/Tasks/…` / `Content/__ExternalObjects__/Tasks/…`
  mirrors (both `asset_writable` in the ThirdPerson manifest).
- empty leg — run implicitly by `cb discriminate` (throwaway empty dir;
  nothing to author).
- No variant dirs (amended §7; `discriminate.py` treats a missing variant
  set as non-fatal).

This task ships **no baseline asset**, so the empty leg is a genuinely empty
deliverable and scores `0/20` (proven offline with a fake `unreal` module:
all 20 checks fail carrying the three `*_MISSING path=` root causes).

## Matrix

**This is the only table in this file whose first column is a submission.**

| Submission | Overall | Fails at (check id) | Expected substring | Also fails (recorded, not matched) | Anti-gaming note |
|---|---|---|---|---|---|
| `../reference` | PASS | — | — | none — all 20 checks green (20/20) | — |
| empty | FAIL | `audit_bp_exists` | `AUDIT_BP_MISSING path=` | all 19 remaining checks fan out the three per-group root causes (`AUDIT_LEVEL_MISSING path=`, `REPORT_FILE_MISSING path=`) — `0/20` | #1 / FR-017 non-vacuity |

## Requirements table (the mandatory §7a artifact)

One row per requirement in the agent-visible prompt. Assertion pointers name
the check id (all in
`tools/verify-single/introspect/kp_blueprint_actor_audit_report.py`; find a
check id in the `CHECK_IDS` tuple and its emitting function). "Skipped when"
names the ONLY condition under which the gate does not evaluate its own
predicate — in every such case the check still FAILS with the prerequisite's
root-cause token (fanout), never a silent pass.

| Key | Prompt requirement | Asserted | Check id (assertion) | Named failure substring | Skipped when | What a submission could get away with |
|---|---|---|---|---|---|---|
| R01 | `BP_AuditTarget` exists in the task folder | fully | `audit_bp_exists` (`_asset_checks`) | `AUDIT_BP_MISSING path=` | unconditional | nothing |
| R02 | it is a placeable object class | fully | `audit_bp_is_actor_class` (`_asset_checks`) | `AUDIT_BP_NOT_ACTOR class=` | BP missing/unresolvable → fails with that root cause | any actor subclass as parent (accepted by design) |
| R03 | part `Body` exists and is a solid-shape (mesh) part | fully | `audit_body_is_mesh_part` (`_resolve`) | `AUDIT_BODY_WRONG_TYPE class=` (impostor) / `AUDIT_BODY_MISSING names=` (absent) | SCS walk failed → fails with walk root cause | a mesh-component *subclass* (accepted: subclass tolerance) |
| R04 | `Body` uses exactly `/Engine/BasicShapes/Cube.Cube` | fully | `audit_body_mesh_is_engine_cube` (`_asset_checks`) | `AUDIT_BODY_MESH_WRONG mesh=` | Body unresolved → fails with R03's detail | nothing — path equality |
| R05 | part `Beacon` exists and is a point-source light | fully | `audit_beacon_is_point_light` (`_resolve`) | `AUDIT_BEACON_WRONG_TYPE class=` / `AUDIT_BEACON_MISSING names=` | SCS walk failed → fails with walk root cause | a point-light subclass, e.g. spot-shaped (accepted residual, task.md) |
| R06 | value `Flagged` is true/false-typed, default `true` | fully | `audit_flag_var_true` (`_asset_checks`) | `AUDIT_FLAG_NOT_TRUE value=` / `AUDIT_FLAG_NOT_BOOL value_type=` / `AUDIT_FLAG_VAR_ABSENT name=` | CDO unresolvable → fails with that root cause | nothing — type asserted before value; fresh default False excluded |
| R07 | value `Score` is fractional-number-typed, default exactly `99.0` | fully | `audit_score_var_value` (`_asset_checks`) | `AUDIT_SCORE_WRONG_VALUE value=` / `AUDIT_SCORE_NOT_NUMERIC value_type=` / `AUDIT_SCORE_VAR_ABSENT name=` | CDO unresolvable → fails with that root cause | an int-typed 99 passes the numeric read (tolerance 1e-3); recorded residual, calibration TODO |
| R08 | the class compiles with no errors and is saved | fully | `audit_bp_compiles_clean` (`_asset_checks`); unsaved state presents as a missing/old asset (overlay grades disk bytes) | `AUDIT_BP_NOT_UP_TO_DATE status=` | BP load failed → fails with load root cause | nothing |
| R09 | `L_AuditScene` exists in the task folder | fully | `audit_level_exists` (`_level_checks`) | `AUDIT_LEVEL_MISSING path=` | unconditional | nothing |
| R10 | the level is a loadable saved level | fully | `audit_level_loads` (`_level_checks`) | `AUDIT_LEVEL_LOAD_FAILED path=` | level missing → fails with R09's root cause | nothing (an unavailable load API is an uncreditable `*_PROBE_ERROR`, never a pass) |
| R11 | exactly two placed objects of the class, no others of it | fully | `audit_instances_exactly_two` (`_level_checks`) | `AUDIT_INSTANCE_COUNT_WRONG count=` | level unloaded / class unresolved → fails with that root cause | nothing — counts ALL instances of the class |
| R12 | one labeled `Audit_Alpha` at `(0, 0, 100)` | fully | `audit_alpha_instance_placed` (`_instance_check`) | `AUDIT_ALPHA_MISSING labels=` / `AUDIT_ALPHA_WRONG_LOCATION location=` | level unloaded → fails with that root cause | 1.0-unit placement tolerance (disclosed as exact; calibration may tighten) |
| R13 | one labeled `Audit_Beta` at `(500, 0, 100)` | fully | `audit_beta_instance_placed` (`_instance_check`) | `AUDIT_BETA_MISSING labels=` / `AUDIT_BETA_WRONG_LOCATION location=` | level unloaded → fails with that root cause | same as R12 |
| R14 | `reports/audit.txt` exists at the pre-declared path | fully | `report_file_present` (`_report_checks`) | `REPORT_FILE_MISSING path=` | unconditional | nothing |
| R15 | the report uses only the five disclosed line shapes, one class + one compile line, no duplicates | fully | `report_grammar_parses` (`_parse_report`) | `REPORT_GRAMMAR_BAD line=` | report missing → fails with R14's root cause | nothing |
| R16 | the class line names the real class and its real parent | fully | `report_class_line_truthful` (`_report_checks`) | `REPORT_CLASS_NAME_MISMATCH reported=` / `REPORT_PARENT_MISMATCH reported=` | asset truth unavailable → fails with that root cause | nothing |
| R17 | one component line per part the class really carries, truthfully typed | fully (two-directional set equality) | `report_component_lines_truthful` (`_report_checks`) | `REPORT_COMPONENTS_MISMATCH reported_only=` | SCS walk failed / report unparsed → fails with that root cause | nothing — fabrication and omission both fail |
| R18 | one variable line per stored value, truthfully typed | partially | `report_variable_lines_truthful` (`_report_checks`) | `REPORT_VARIABLES_MISMATCH problems=` | CDO unavailable → fails with that root cause | an EXTRA real variable omitted from the report (variable enumeration unproven from stock python) — accepted residual, task.md + notes.md |
| R19 | the compile line claims clean only if true | fully | `report_compile_line_truthful` (`_report_checks`) | `REPORT_COMPILE_MISMATCH reported=` | compile truth unavailable → fails with that root cause | nothing — claim conjoined with actual status |
| R20 | one instance line per placed object, truthful label + location | fully (set equality + per-label location) | `report_instance_lines_truthful` (`_report_checks`) | `REPORT_INSTANCES_MISMATCH reported_only=` | level truth unavailable → fails with that root cause | location honesty within the same 1.0-unit tolerance as R12/R13 |

Every requirement row above resolves to a live assertion — no requirement is
unenforced prose, so no targeted variant is owed under the amended §7. The
two "partially" / residual rows (R18's omitted-extra-variable, R07's
int-typed 99) are recorded in the spec's *Accepted residuals* and in
`../notes.md` with their calibration TODOs.

## How to run (deterministic verifier, no agent, no tokens)

After the authoring-lane run lands the reference binaries:

```sh
cb discriminate --task python/kp-blueprint-actor-audit-report --wip
```

Per-leg fallback while iterating (short `--workdir` for MAX_PATH; use the
`py` launcher — `py -3.12` does not resolve on this box, use `py -3.13`):

```sh
UE='<UE-root>'
py tools/verify-single/run_task.py \
    --task tasks/python/kp-blueprint-actor-audit-report/task.md \
    --submission tasks/python/kp-blueprint-actor-audit-report/reference \
    --ue-root "$UE" --workdir C:\cb\wd\kpaudit       # expect exit 0
```

L2I graders are read from the LIVE working tree, so iterating on the script
needs no commit — but the binaries DO need committing before a non-`--wip`
grade sees them (the runner materializes the substrate from git HEAD).

## Status

- Authored 2026-08-11 from the spec, text-only track. **Never executed
  against a real editor** — no binary exists yet.
- Proven offline: the script emits a constant 20-check verdict; the empty
  leg scores 0/20 with the three graded `*_MISSING path=` root causes (fake
  `unreal` module, real emission path); every expected substring above greps
  as a single source literal; no automation result marker appears anywhere
  in the script.
- Still missing, in order: (1) the reference binaries via
  `../aids/author_reference.py` (which grades itself in-process against this
  script and requires 20/20 before harvesting); (2) live confirmation of the
  level-load route and the CDO variable-read spellings (notes.md §4);
  (3) the git-HEAD certification run.
