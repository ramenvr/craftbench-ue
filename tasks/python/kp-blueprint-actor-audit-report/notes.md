# kp-blueprint-actor-audit-report — authoring notes

First task of the new `tasks/python/` basket (owner decision 2026-08-11:
outcome-graded editor-scripting tasks; the deliverable is the resulting
editor state, graded by the deterministic L2I lane exactly like `bp/`; no
gate asserts "python was used"; a future v2 may re-execute submitted
scripts — deliberately not this version).

## 1. Provenance (source row)

- **Source**: an earlier internal task list (not shipped) — an inspection row,
  one of a group derived from observed editor-scripting-agent failures.
- **Its verification cell**: "BP exists, compiles, has the right
  components/variables; exactly 2 named instances spawned; printed audit
  reports class, components, vars, compile status, per-actor
  location/light."
- **Its scoring cells**: "% of verification checks passed (0-100%)" (a
  partial-credit scheme) and "# of execute_unreal_python calls
  + compile errors to reach success" (an efficiency metric this harness
  does not gate; the action budget bounds it coarsely).
- **Id scheme**: `kp-` is the python-basket family prefix; the source row's
  `t4-` is a row index, not a tier, and is dropped.
  Substring audit: `kp-blueprint-actor-audit-report` is not a substring of
  any other task id and contains none (`inventory.py` raw-substring
  membership trap).

## 2. Divergences from the source row (full record)

| # | source row | this task | why |
|---|---|---|---|
| 1 | "Using Unreal Python, do the following" + verbatim API names (`StaticMeshComponent`, `PointLightComponent`, subobject data) | behavior-only prompt; tool unnamed | Hard Rule #2 + the basket law: outcomes, not mechanisms. This is exactly the "prompts violate Hard Rule #2 verbatim" blocker the import plan recorded — resolved by rewrite, not exception |
| 2 | PRINT a structured report | plain-text file `reports/audit.txt` with a strict disclosed grammar, cross-checked against introspected truth | printed output is not a gradable artifact; the file version follows the `datatable_csv_export.py` text-artifact idiom and gains the fabrication gate the source row could not have |
| 3 | `/Game/EvalAssets/` | `/Game/Tasks/<id>/` | the source row path exists nowhere and is outside every writable prefix (same finding as dawn-fog's divergence 3) |
| 4 | `BP_EvalAuditActor`, `AuditMesh`, `AuditLight`, `bIsAudited`, `AuditScore`, `AuditActor_Alpha/Beta` | `BP_AuditTarget`, `Body`, `Beacon`, `Flagged`, `Score`, `Audit_Alpha/Beta` | the source row names leak the mechanism vocabulary ("Mesh", "Light", the `b` bool prefix, "Actor") into agent-visible identifiers; the replacements are behavior-neutral |
| 5 | light nested under the mesh, mesh as root | hierarchy not graded; both parts anywhere | SCS socket attachment is un-settable from python (`craftbench-scs-attachtoname-gap`); plain parenting is settable but grading it buys no capability signal here and adds an attach-chain read |
| 6 | spawn into "the current level" | a NAMED saved level `L_AuditScene` under the task folder | "current level" is not a deliverable; a saved level is, and the OFPA carve-out (2026-07-29) made agent-authored levels submittable |
| 7 | "has a PointLightComponent" per-actor report field | per-instance label + location only | the per-actor light probe duplicates the class-level Beacon gate; dropped to keep the instance grammar one line per actor |
| 8 | % score | constant 20-check denominator reported as `x/20`; `overall` stays all-or-nothing | D1 partial credit as trajectory signal, FR-020d-compliant |

## 3. Design decisions

- **Three independently gated artifact groups** (asset 8 / level 5 /
  report 7 = 20 checks, constant denominator). A perfect report never
  compensates for missing state and vice versa — that is the whole
  anti-fabrication design, and it is what makes the source row's "audit" idea
  gradable at all.
- **Pinned truth, not report-derived truth** (the datatable gold-leak
  lesson): every expected value (names, cube path, True/99.0, labels,
  locations, count, `clean`) is a constant in the verifier script. The
  report cross-check only ADDS "tell the truth about the submission".
- **Every pinned value excludes the untouched default**: fresh bool =
  False (gate True), fresh float = 0.0 (gate 99.0), fresh mesh slot = None
  (gate the cube), fresh level = 0 instances (gate exactly 2). The
  row R5 `intensity == 5000` dead-gate lesson, applied at authoring time.
- **Single-literal token heads.** Every `TOKEN key=` failure head lives in
  ONE source string literal (the `_resolve` / `_instance_check` helpers
  take whole format-string literals from call sites instead of assembling
  from stems), so the MATRIX oracle's static source grep can verify every
  expected substring. Proven offline 2026-08-11: all 29 cited heads grep;
  the two automation result markers appear nowhere in the script.
- **Fail-closed proven offline**: with no `unreal` module and with a fake
  module reporting nothing on disk, the script emits exactly 20 checks,
  all failing — the no-module leg carries only uncreditable
  `*_PROBE_ERROR` tokens, the empty leg carries the three graded
  `*_MISSING path=` root causes.
- **Report grammar is order-insensitive** within its line kinds and
  requires exactly one `class` + one `compile` line, uniqueness everywhere
  else. Order-insensitivity mirrors the datatable "row order is not
  content" ruling.
- **`compile status=clean` is the only legal compile line** — a truthful
  "status=errors" report still fails (the task requires a clean compile;
  the report check conjoins claim with truth so a false "clean" fails at
  the cross-check even before the asset gate).
- **cameras.json not authored** (SHOULD-ship per checklist §5): deferred to
  the authoring-lane session, where the camera plan needed
  the committed binaries anyway. TODO below.

## 4. Calibration TODOs (run in the authoring-lane editor session)

The aid (`aids/author_reference.py`) prints `KPAUDIT-SPELLING` lines to
settle each of these; record the winners here after the run:

- [ ] **BP member-variable creation** — THE unproven step.
  `BlueprintEditorLibrary.add_member_variable` + `EdGraphPinType` across
  pin specs `bool`, `real/double`, `real/float`, `float`. If no route
  works: author the two variables through the MCP graph lane
  (`edit_blueprint` — proven in the earlier-task-list unlock campaign), harvest,
  and record that this aid's variable step is aspirational. The GRADER is
  unaffected either way (it reads the CDO, not the authoring route).
- [ ] **CDO default-value writes** stick and survive compile+save
  (read-back verified in the aid; confirm the saved asset re-reads
  True/99.0 in a FRESH editor, not just in-session).
- [ ] **Headless level load** under `-ExecutePythonScript` + `-nullrhi` —
  the route dawn-fog's spec recorded as unspiked (plan U1).
  `LevelEditorSubsystem.load_level` first; record which route wins and
  whether the asset-registry scan needs an explicit wait before
  `does_asset_exist(LEVEL_PATH)`.
- [ ] **`get_actor_label`** readability on placed instances headless.
- [ ] **Parent-class read** — `bp.get_editor_property("parent_class")` vs
  `gen_cls.get_super_struct()`; record the winner and the exact string it
  yields (expected `Actor`) so the reference report matches.
- [ ] **Class-name strings in the report** — confirm
  `get_class().get_name()` yields `StaticMeshComponent` /
  `PointLightComponent` / `SceneComponent` for the parts (the reference
  report is generated from the same reads, so it self-consists; this TODO
  is about documenting the strings for humans).
- [ ] **`UBlueprint::NewVariables` readability** — if
  `bp.get_editor_property("new_variables")` reads, upgrade
  `report_variable_lines_truthful` to full set equality and delete the
  omitted-extra-variable residual from task.md + MATRIX R18.
- [ ] **Location tolerance** — 1.0 unit is pre-calibration; confirm the
  spawned actors read back exactly and consider tightening to 0.1.
- [ ] **Int-typed 99 residual (MATRIX R07)** — decide whether an integer
  variable named Score should fail `audit_score_var_value` (add an
  `isinstance(value, float)` strictness) once the live read's python type
  for a BP double is confirmed.
- [ ] **OFPA or monolithic save** — record which shape
  `LevelEditorSubsystem.new_level` + save produced; if OFPA, confirm the
  external-actor mirrors harvested into `reference/` overlay-apply
  cleanly and the sandbox accepts them (both prefixes are
  `asset_writable`).
- [ ] **cameras.json** — propose after the binaries commit.
- [ ] **Repo-count edits** — CATALOG row + the `inventory.py` hard-coded
  count claims (the repo conventions, `tasks/CATALOG.md`, two SKILL.md files) when
  this task lands; budget it with the commit (imported-set precedent §9.2).

## 5. Reference status

**Reference pending the authoring-lane run.** This track cannot run UE, so
`reference/` is EMPTY (not even committed as a directory) and no `.uasset`
/ `.umap` byte in this change-set is fabricated. `aids/author_reference.py`
is the generator: it builds the three artifacts at the real content paths,
writes the report from READ-BACK truth (importing the real grader's truth
helpers, so report and grader can never disagree by construction), grades
itself in-process against the real verifier script, harvests into
`reference/` ONLY on a 20/20 vector, and leaves the substrate empty
(verified, with the editor parked on a neutral engine map before deletion).
`KPAUDIT-DONE` in the editor log is the success marker; absence = failed.

## 6. Risks

1. **Headless level load is unspiked** (shared flag for the python-basket
   wave: any sibling task grading a saved level inherits this risk). No
   shipped L2I script loads a map; `l2_introspect.py` builds the command
   line with no map argument, so the script must load the level itself
   under `-nullrhi`. Mitigation: three-route loader, fail-closed both ways
   (refusal = graded `AUDIT_LEVEL_LOAD_FAILED`, missing API = uncreditable
   `AUDIT_LEVEL_LOAD_PROBE_ERROR` → the reference gate catches it before
   any agent run). If the spike fails outright, the fallback redesign is
   dropping artifact 2 to instance-data-in-report only — a spec change,
   flagged now on purpose.
2. **BP member-variable creation from stock python is unproven**
   (`add_member_variable` exposure + `EdGraphPinType` pin-category
   spellings). Affects the AID only, not the grader; MCP graph lane is the
   named fallback.
3. **CDO reads of BP-authored variables** are precedented-but-unproven for
   this exact shape (bool + double defaults on a BlueprintFactory actor
   BP). Multi-spelling, fail-closed.
4. **OFPA residue**: if the level saves One-File-Per-Actor, harvesting and
   cleanup must handle the mirror trees; the aid does both, but external
   actor GUID-named files make the reference overlay bigger and
   git-noisier than a monolithic `.umap`. If so, consider forcing
   monolithic save in the aid (world-partition off) at calibration time.
5. **Class-name string drift**: the report grammar embeds editor-reported
   class names; an engine minor bump that renames a component class would
   break reference-vs-grader agreement. Low likelihood on the repo-wide
   UE 5.8 pin; the reference report being GENERATED from the same reads
   confines the blast radius to regeneration.
6. **Grader helper reuse by the aid** (`build_report` imports the grader's
   `_`-prefixed helpers): a grader refactor can break the aid silently.
   Accepted: the aid dies loudly and is a dev-only tool; the coupling is
   what guarantees report/grader agreement.
7. **`set: python` is new to every consumer.** `spec.py` parses it (free
   scalar — verified through the real parser 2026-08-11), and discovery is
   pure file-drop, but `tasklint` / `inventory` / CATALOG tooling may
   carry `bp|cpp` assumptions this first task will flush out. Run
   `cb lint --task python/kp-blueprint-actor-audit-report` as the first
   gate after this change-set lands.

## 7. Checklist state (docs/TASK-AUTHOR-GUIDE.md)

- [x] 1. Spec — `task.md` (v2 front matter, parses through the real
      `spec.py`; behavior-only prompt; 5 anti-gaming notes with resolvable
      defense pointers; verifier spec with named failure substrings)
- [ ] 2. Scaffold pair — N/A by design (no C++ scaffold; content-only task,
      no baseline asset — the dawn-fog precedent)
- [ ] 3. Fixture pair — N/A (no L2; L2I only)
- [ ] 4. Map — N/A (no committed verifier map; the LEVEL is the agent's
      deliverable, not a fixture map. `docs/MAPS.md` row not required —
      confirm at lint)
- [ ] 5. Camera plan — TODO after binaries commit
- [ ] 6. Reference — PENDING the authoring-lane run of
      `aids/author_reference.py` (this change-set ships the generator, not
      the bytes)
- [x] 7. Discrimination — `discrimination/MATRIX.md`: automatic
      reference-PASS / empty-FAIL rows + the §7a requirements table
      (20 rows, every requirement mapped to a live assertion; no variant
      owed). Parses through the real `parse_matrix` (verified 2026-08-11).
- [ ] 8. Gates — blocked on the reference binaries (lint can run now;
      discriminate/refgate cannot)
- [ ] 9. Commit + PR + refgate close — future work

> **RECONCILIATION 2026-08-11/12 (authoring-lane + graph-lane runs DONE).**
> Statements above about pending binaries / empty reference/ describe the
> authoring-time state and are now historical: binaries are committed
> (39433c2, 09781a8) and `cb refgate` graded this task's reference PASS
> from git HEAD. Remaining: the empty-FAIL discriminate leg.

## Accepted residuals (moved from task.md 2026-08-16; lint spec-h2-allowlist)

- **A real extra variable omitted from the report is not caught.** Stock
  python cannot reliably enumerate a Blueprint's authored variable list
  (`UBlueprint::NewVariables` reflection readability is unverified), so
  variable truthfulness is: required two + every *reported* variable must
  resolve on the CDO. A submission that adds a third variable and omits it
  from the report passes. Calibration TODO in `notes.md` §4: attempt the
  `new_variables` read at reference time and upgrade to set equality if it
  reads.
- **The exact-class fallback for instance identity loses subclass
  tolerance.** If `class_is_child_of` is unavailable, a placed *subclass*
  of `BP_AuditTarget` would not be counted. The primary route is
  subclass-tolerant; the fallback never creates a false PASS, only a
  potential false FAIL on an exotic-but-legitimate shape, and its use is
  visible in the detail strings.
- **A spot-light-shaped subclass of the point-light component satisfies
  `Beacon`.** Subclass tolerance is the repo law; the prompt's "in all
  directions" is not separately gated. Accepted: the capability graded is
  part-of-the-right-kind, not photometry.
- **Component hierarchy is not graded** (divergence 4): nesting `Beacon`
  under `Body` or leaving both under the default root are equally
  accepted.
- **No gate asserts the mechanism** (basket law): a hand-authored editor
  session producing identical bytes passes. That is the basket's design,
  not a leak.
