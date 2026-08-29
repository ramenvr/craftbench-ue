---
id: kp-blueprint-actor-audit-report
substrate: ThirdPerson
set: python
tier: T2
capability_bucket: Tools & Pipeline
category: other
layers: [L1, L2I]
introspect: [kp_blueprint_actor_audit_report.py]
---

# kp-blueprint-actor-audit-report

The first task of the `tasks/python/` basket (owner decision 2026-08-11):
**outcome-graded editor-scripting work**. The deliverable is the resulting
editor state — one Blueprint actor class, one saved level with exactly two
placed and labeled instances, and one plain-text audit report whose every
line must match what is actually on disk — graded by the existing
deterministic L2I introspect lane exactly like the `bp` basket. The prompt
describes outcomes whose exactness and volume (exact names, exact defaults,
exact world positions, an exact machine-checkable report grammar) make
editor scripting the natural way to complete them, but **no gate asserts
"python was used"** — a hybrid or hand-authored route that produces the same
bytes passes identically. A future v2 may additionally re-execute a
submitted script; that is deliberately not this version.

### Provenance and deliberate divergences from the source row

Imported from an earlier internal task list (not shipped): an inspection row,
one of a group derived from observed editor-scripting-agent failures. The
source row's verification cell: *"BP exists, compiles, has the right
components/variables; exactly 2 named instances spawned; printed audit
reports class, components, vars, compile status, per-actor
location/light."* Full divergence record: `notes.md` §2. Headlines:

1. **"Using Unreal Python, do the following" is dropped.** The source row's
   prompt opens by naming the tool and then names APIs verbatim
   (`StaticMeshComponent`, `PointLightComponent`, subobject data). Per Hard
   Rule #2 and the basket law, the prompt below is rewritten as observable
   outcomes; the tool choice is the agent's.
2. **PRINT becomes a FILE.** The source row grades a *printed* report; printed
   output is not a deliverable this harness grades deterministically. The
   report becomes a plain-text artifact at a pre-declared path with a
   strict disclosed grammar — the `datatable_csv_export.py` text-artifact
   idiom — and gains the property the source row's version could not have: every
   line is **cross-checked against the introspected truth**, so a report
   that disagrees with the asset FAILs.
3. **Paths re-homed.** The source row's `/Game/EvalAssets/` does not exist and is
   outside every writable prefix; re-pathed to the repo convention
   `/Game/Tasks/<task-id>/`. Instance labels lose the source row's `Actor`
   infix (`AuditActor_Alpha` → `Audit_Alpha`) to keep the prompt free of
   the word "Actor" (an engine class name).
4. **Component hierarchy is not graded.** The source row nests the light under
   the mesh and makes the mesh the root. SCS attach-parent authoring from
   stock python is doable but socket attachment is not
   (`craftbench-scs-attachtoname-gap`), and hierarchy grading adds an
   attach-chain read for no capability signal this row needs — both parts
   are graded by name + type + value, wherever they sit.
5. **The source row's D1 partial score maps to the reported check ratio.** The
   The source list's "partial scoring" intent is satisfied by the constant
   20-check denominator: `report.json` carries `x/20` as trajectory signal,
   while `overall` stays all-or-nothing like every certified task.

> **Note on the behavior-only rule (Hard Rule #2).** Like the other
> asset-deliverable tasks (`t1-dawn-fog-lighting-rig`,
> `t1-hero-blueprint-copy-with-flashlight`), this task names the concrete
> deliverable paths, the subobject/variable names, the instance labels and
> the exact numbers the verifier keys on — the standard, precedented
> exception for tasks whose whole point is producing exactly-specified
> artifacts, and the express point of this basket (exactness and volume in
> the prompt; mechanism never). **No engine class name, no API name, no
> editor-operation name appears in the prompt.** The parts are described by
> what they do; the report records "the name the editor itself gives" each
> thing, so the agent reads names back rather than being told them.

## Primary concept

- `ps-scripting-editor-python` — Scripting the Unreal Editor Using Python
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/scripting-the-unreal-editor-using-python)

The load-bearing capability is **driving the editor to produce an exactly
specified state and then reading that state back faithfully**: create a
class asset with named, typed parts and typed default values; place and
label instances at exact coordinates in a saved level; then produce a
machine-checkable audit of what actually exists. The adjacent concept is
`ps-asset-registry` (Asset Registry,
https://dev.epicgames.com/documentation/en-us/unreal-engine/asset-registry-in-unreal-engine)
— the audit half is registry-and-reflection literacy — but the primary
difficulty is the authoring-then-introspection round trip, which is the
editor-scripting page's home ground.

## Prompt given to the agent

> The folder `Content/Tasks/kp-blueprint-actor-audit-report/` starts empty.
> Produce three things in it, exactly as described.
>
> **1. A placeable game-object class** saved as `BP_AuditTarget` in that
> folder. Objects of this class must be placeable in a level, and the class
> must carry, each under exactly the name given:
>
> - a part named `Body` that gives the object a visible solid shape, using
>   the engine's stock cube shape asset at `/Engine/BasicShapes/Cube.Cube`;
> - a part named `Beacon` that emits light from a single point in all
>   directions;
> - a stored true/false value named `Flagged` whose default is `true`;
> - a stored fractional-number value named `Score` whose default is exactly
>   `99.0`.
>
> The class must compile with no errors and be saved.
>
> **2. A saved level** named `L_AuditScene` in the same folder, containing
> **exactly two** placed objects of that class and no other objects of it:
> one labeled `Audit_Alpha` at world position `(0, 0, 100)`, one labeled
> `Audit_Beta` at world position `(500, 0, 100)`.
>
> **3. A plain-text audit report** at
> `Content/Tasks/kp-blueprint-actor-audit-report/reports/audit.txt`
> describing what is ACTUALLY in the two artifacts above — read back from
> them after you finish, not restated from this brief. Every line of the
> report is checked against the artifacts, and a line that disagrees with
> what is really on disk fails the task. The report consists only of lines
> in these five shapes (blank lines are ignored; order does not matter;
> values never contain spaces):
>
> ```text
> class name=<class-name> parent=<parent-name>
> component name=<part-name> class=<part-kind-name>
> variable name=<value-name> type=<bool|float>
> compile status=clean
> instance label=<label> location=<x>,<y>,<z>
> ```
>
> Exactly one `class` line and exactly one `compile` line. One `component`
> line for **every** part the class carries — including any default part it
> was created with — where `<part-kind-name>` is the name the editor itself
> gives that part's kind. `<parent-name>` is likewise the name the editor
> gives the class the object is based on. One `variable` line per stored
> value, with `type=bool` for a true/false value and `type=float` for a
> fractional-number value. `compile status=clean` may only be written if
> the class really does compile with no errors. One `instance` line per
> placed object of the class in the level, with its label and its world
> position as three comma-separated numbers.

## Workspace state pre-task

Substrate content that **exists** under
`Content/Tasks/kp-blueprint-actor-audit-report/`:

- Nothing. This task ships **no baseline asset**. The folder is the
  agent-writable Content carve-out of the `ThirdPerson` substrate
  (`UE-projects/ThirdPerson/AGENT_WRITABLE.json` lists `Content/Tasks/`
  under both `writable` and `asset_writable`); fairness isolation keeps
  this task's folder while hiding every other task's.

Files that **do not exist** (the agent must create all three):

- `Content/Tasks/kp-blueprint-actor-audit-report/BP_AuditTarget.uasset`
- `Content/Tasks/kp-blueprint-actor-audit-report/L_AuditScene.umap`
  (if the editor saves the level One-File-Per-Actor, its actor mirrors land
  under `Content/__ExternalActors__/Tasks/` /
  `Content/__ExternalObjects__/Tasks/`, which are `asset_writable` — the
  2026-07-29 OFPA carve-out exists for exactly this level-deliverable lane)
- `Content/Tasks/kp-blueprint-actor-audit-report/reports/audit.txt`

Out of scope / not needed:

- No C++ is required or expected. `Content/Maps/`, `Config/` (beyond the
  listed config lane), and the stock content folders are deny-listed — the
  agent neither can nor needs to touch them.

## Verifier specification

Layer choice: **L1 + L2I**. Every graded property is a static property of
saved editor state — asset structure, level contents, and a text file —
read by verifier-owned editor-Python reflection. L2 is deliberately not
declared: nothing evolves over time, and a PIE fixture would need a
committed map this task has no use for. Nothing asserts *how* the state was
produced (basket law: outcome-graded, no "python was used" gate).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

The submission is content+text only, so L1 is a precondition (the project
must load cleanly), never a correctness signal.

### L2I — Structural assertion + report cross-check

The verifier-owned script
`tools/verify-single/introspect/kp_blueprint_actor_audit_report.py` runs
headless via `UnrealEditor-Cmd -ExecutePythonScript=` under `-nullrhi`,
read-only, and prints one `CRAFTBENCH-INTROSPECT-JSON` verdict block with
**exactly 20 named checks on every leg** (constant denominator; the empty
submission scores 0/20). PASS requires all 20.

Group 1 — the class asset (8 checks):

```text
audit_bp_exists                 /Game/Tasks/<id>/BP_AuditTarget resolves
audit_bp_is_actor_class         its default object is a placeable actor
audit_body_is_mesh_part         a subobject named "Body" exists AND is a
                                static-mesh component (subclass-tolerant)
audit_body_mesh_is_engine_cube  Body's mesh is exactly
                                /Engine/BasicShapes/Cube.Cube
audit_beacon_is_point_light     "Beacon" exists AND is a point-light
                                component (subclass-tolerant)
audit_flag_var_true             CDO variable "Flagged" reads as a real bool
                                AND is True   (a fresh bool defaults False)
audit_score_var_value           CDO variable "Score" reads as a non-bool
                                number AND |v - 99.0| <= 1e-3
                                              (a fresh float defaults 0.0)
audit_bp_compiles_clean         the freshly loaded asset's compile status is
                                up-to-date
```

Group 2 — the level (5 checks):

```text
audit_level_exists              /Game/Tasks/<id>/L_AuditScene resolves
audit_level_loads               the level loads into the headless editor
                                session (LevelEditorSubsystem.load_level,
                                with load_map / legacy fallbacks)
audit_instances_exactly_two     EXACTLY 2 placed actors are instances of the
                                submitted class (child-class-tolerant via
                                class_is_child_of)
audit_alpha_instance_placed     label "Audit_Alpha" present, unique, within
                                1.0 unit of (0, 0, 100)
audit_beta_instance_placed      label "Audit_Beta" present, unique, within
                                1.0 unit of (500, 0, 100)
```

Group 3 — the report (7 checks; the cross-check):

```text
report_file_present             Content/Tasks/<id>/reports/audit.txt exists
report_grammar_parses           every non-blank line matches one of the five
                                disclosed shapes; exactly one class line and
                                one compile line; no duplicate names/labels
report_class_line_truthful      name == BP_AuditTarget AND parent equals the
                                introspected parent-class name
report_component_lines_truthful the reported (name, class) set EQUALS the
                                introspected SCS scene-component set
                                (both directions: a fabricated line fails,
                                an omitted real part fails)
report_variable_lines_truthful  Flagged and Score lines present with the
                                introspected kind; every extra reported
                                variable must resolve on the CDO with a
                                matching kind
report_compile_line_truthful    the line says clean AND the asset really is
                                up-to-date
report_instance_lines_truthful  reported label set EQUALS the placed label
                                set AND each reported location is within
                                1.0 unit of the actual placed location
```

**The gold-leak defense.** Every *expected* value (the four names, the cube
path, True/99.0, the two labels, the two locations, the count of two, the
`clean` token) is **pinned in the verifier script's constants** — the
report cross-check only ever adds "the report must tell the truth about the
submission"; it never supplies the expected side from anything the agent
can write (`datatable_csv_export.py` precedent). The three artifact groups
are gated independently, so a perfect report cannot compensate for a
missing asset and perfect assets cannot compensate for a fabricated report.

**Fail-closed properties** (mirroring the set convention):

- A missing/empty submission fails all 20 checks with per-group
  `*_MISSING path=` root causes fanned out — never a vacuous pass and never
  a shrunken denominator.
- Every negative/exactness assertion is conjoined with the positive read
  that produced it: the instance count needs a loaded level and a resolved
  class; set-equality needs a parsed report and a completed SCS walk; a
  failed prerequisite fans its own token into dependents.
- Error tokens (`*_PROBE_ERROR`, `*_READ_ERROR`, `*_WALK_ERROR`,
  `*_ABORTED`, `CHECK_NOT_EVALUATED`) are disjoint from graded failure
  tokens and appear in no MATRIX row, so a broken UE API can never be
  credited as a variant's named failure.
- All details are ASCII-only (the cp1252 log read-back trap,
  `t2-homing-projectile` 2026-07-21).

**Known-risk reads, all fail-closed** (full list + calibration plan in
`notes.md` §4): the headless level load is THE unspiked route of this task
(plan U1 listed "level load/enumerate" as an open probe; no shipped L2I
script loads a map today); the CDO variable reads and the parent-class
read are multi-route with the winning spelling to be recorded at
calibration. None of these can produce a false PASS — only an uncreditable
FAIL, which the reference-gate run will surface before any agent sees the
task.

**Score granularity.** `registry.py` reports `tests_passed/tests_run`, so
`report.json` carries `x/20` — the D1 partial-credit signal — while
`overall` stays `all(pass)`.

## Reference solution metadata

- LOC range: **0** lines of module code. The deliverable is two binary
  assets plus one ~12-line text file; the natural route is a throwaway
  editor-python script of roughly 60-120 lines the agent writes and runs
  (not itself graded or submitted).
- Files touched: 3 created (`BP_AuditTarget.uasset`, `L_AuditScene.umap`
  plus any OFPA actor mirrors, `reports/audit.txt`), 0 modified.
- Senior-dev hours: 0.75-2.0 — trivial by hand in an open editor, but the
  exactness (labels, coordinates, defaults, report grammar, read-back
  fidelity) makes scripting the honest route, and the scripted route
  requires knowing the subobject, variable, level and label APIs.

## Anti-gaming notes

1. **Report written from the brief, not the editor.** *Failure mode*: the
   agent skips the artifacts (or half of them) and writes an `audit.txt`
   that transcribes the prompt — the source row's original "printed report"
   grading would have scored this. *Defense*: the three groups gate
   independently — with no asset, `audit_bp_exists` fails
   (`AUDIT_BP_MISSING path=`) and every report truth check fans out the
   same root cause; a report can never substitute for state. Pointer:
   `kp_blueprint_actor_audit_report.py::_asset_checks` (the
   `AUDIT_BP_MISSING` fanout) and `::_report_checks` (truth checks read
   introspected truth, never the report alone). MATRIX rows: empty leg +
   requirements table rows 1-13.
2. **Artifacts correct, report fabricated or stale.** *Failure mode*: the
   agent builds everything, then reports a component it later renamed, a
   rounded location, or `status=clean` on a class that never compiled.
   *Defense*: `report_component_lines_truthful` /
   `report_instance_lines_truthful` are two-directional set equalities
   against the introspected truth (`REPORT_COMPONENTS_MISMATCH
   reported_only=`, `REPORT_INSTANCES_MISMATCH reported_only=`);
   `report_compile_line_truthful` conjoins the claim with the actual
   status (`REPORT_COMPILE_MISMATCH reported=`). Pointer:
   `kp_blueprint_actor_audit_report.py::_report_checks`.
3. **Right names, wrong things.** *Failure mode*: a plain empty part named
   `Body`, any light-shaped part named `Beacon` — name-only checks would
   pass. *Defense*: each presence check requires name AND a
   subclass-tolerant type assertion with a tri-state probe that FAILS when
   unevaluable (`AUDIT_BODY_WRONG_TYPE class=`, `AUDIT_BEACON_WRONG_TYPE
   class=`), and `audit_body_mesh_is_engine_cube` pins the exact mesh
   (`AUDIT_BODY_MESH_WRONG mesh=`). Pointer:
   `kp_blueprint_actor_audit_report.py::_resolve` and the cube check in
   `::_asset_checks`.
4. **Variables added but never given the non-default values.** *Failure
   mode*: `Flagged` left at a fresh bool's False, `Score` left at 0.0 —
   presence-only grading passes untouched defaults (the row R5
   `intensity == 5000` dead-gate lesson). *Defense*: both value gates pin
   values that EXCLUDE the fresh-variable defaults (`AUDIT_FLAG_NOT_TRUE
   value=`, `AUDIT_SCORE_WRONG_VALUE value=`), and the type is asserted
   before the value (`AUDIT_FLAG_NOT_BOOL value_type=`,
   `AUDIT_SCORE_NOT_NUMERIC value_type=`). Pointer: the variable block of
   `kp_blueprint_actor_audit_report.py::_asset_checks`.
5. **Instance-count gaming.** *Failure mode*: spawn extras and hope the
   two named ones are found, or place one actor and report two.
   *Defense*: `audit_instances_exactly_two` counts ALL instances of the
   submitted class in the loaded level (`AUDIT_INSTANCE_COUNT_WRONG
   count=`); the per-label checks additionally require uniqueness
   (`AUDIT_ALPHA_MISSING labels=`, `AUDIT_ALPHA_WRONG_LOCATION
   location=`); and the report instance set-equality fails a reported
   phantom (`REPORT_INSTANCES_MISMATCH reported_only=`). Pointer:
   `kp_blueprint_actor_audit_report.py::_level_checks` and
   `::_instance_check`.

## Hidden invariants

- **The check denominator is fixed at 20 on every leg**, including the
  empty submission (0/20). A submission cannot improve its reported ratio
  by making checks unreachable.
- **Every pinned expected value excludes the corresponding untouched
  default**: a fresh bool variable is False (gate: True), a fresh float is
  0.0 (gate: 99.0), a fresh mesh slot is None (gate: the cube), a fresh
  level has zero instances (gate: exactly two), and an absent report is a
  seven-check failure. Any future edit that widens a gate must re-run this
  column.
- **A failed prerequisite fans out its own root-cause token** — dependent
  checks never invent unrelated failures, so a wrong-reason FAIL is
  visible as an uncredited token.
