# kp-derived-class-search — authoring notes

Wave-3 `tasks/python/` basket task (outcome-graded editor-scripting; the
deliverable is the resulting editor state / text report, graded by the
deterministic L2I lane; no gate asserts "python was used"). Built on the two
patterns refgate-proven this week: the strict-grammar report CROSS-CHECK
(`kp_blueprint_actor_audit_report.py`) and the pinned-constants +
corpus-guard defense pair shared with the sibling usage-search task.

## 1. Provenance (source row)

- **Source**: an earlier internal task list (not shipped) — a usage-search
  row, described there as "Search for derived blueprints".
- **Its prompt cell**: *"What are all the
  blueprints in my project that derive from ACharacter?"*; project column:
  *Empty Project*; no verification cell at all — the row is
  **answer-shaped**: a chat question expecting a chat answer, with nothing
  the harness could grade and (on the source row's own Empty Project) a
  vacuously empty true answer.
- **Id scheme**: `kp-` is the imported-set family prefix; the source row's
  `t13-` is a row index, not a tier, and is dropped. Substring audit:
  `kp-derived-class-search` is not a substring of any other task id and
  contains none (`inventory.py` raw-substring membership trap). The slug
  names the outcome (finding derived classes), not an editor operation.

## 2. Divergences from the source row (full record)

| # | source row | this task | why |
|---|---|---|---|
| 1 | chat ANSWER ("What are all the blueprints...") | strict-grammar report file `reports/derived.txt`, cross-checked line by line | an answer is not a gradable artifact; the file version follows the `datatable_csv_export.py` text-artifact idiom and the audit-report task's disclosed-grammar pattern |
| 2 | search space = "my project" (Empty Project) | a 5-asset verifier-authored corpus under `Content/Tasks/<id>/corpus/` | unbounded/substrate-dependent search space, vacuously empty on the source row's own project; the corpus makes the true answer exact, non-empty, and verifier-owned |
| 3 | base = `ACharacter` | base = corpus asset `BP_MachineBase` | an engine class name in the prompt violates Hard Rule #2; a corpus-local base also keeps the answer independent of substrate stock content |
| 4 | membership-only answer | each line also carries the DIRECT parent | a 4-candidate membership answer is guessable at 1-in-16; the parent column forces reading the real chain and separates the transitive child from a flat list |
| 5 | no anti-tamper story (chat answer, nothing writable) | corpus-unmodified guard (6 checks) | the corpus lives inside the agent-writable `Content/Tasks/` prefix; "search the shipped corpus" must be a gate |
| 6 | no red herrings (real project content) | `BP_MachineBaseplate` (name-stem herring) + `BP_ScoutRig` (suffix herring) + `BP_HeavyDrillRig` (transitive child) | the corpus is DESIGNED so name-matching and direct-only scans each fail in a named way |

## 3. Design decisions

- **Deliverable = report ONLY.** The corpus is substrate baseline (like the
  dawn-fog baseline assets), not part of the reference overlay. The empty
  submission therefore scores 6/10 (corpus guard green, report group red),
  not 0/10 — recorded in MATRIX.md; the FAIL still lands on the named
  `REPORT_FILE_MISSING path=` root cause.
- **Pinned truth, not recomputed truth** (the gold-leak defense, shared
  with the sibling usage-search task): the expected derived set and both
  direct parents are constants in the verifier script. The live corpus is
  separately asserted to still MATCH the pins (the guard), so corpus
  tampering cannot move the bar — it can only add a named
  `CORPUS_MODIFIED_*` failure.
- **Disk truth for the corpus set check** (os.walk, not
  `EditorAssetLibrary.list_assets`): cannot lag the asset registry under a
  fresh `-nullrhi` boot, and sees a hand-dropped foreign `.uasset` the
  registry may not have scanned. Class facts then load per pinned path,
  registry-free.
- **Derivation via `class_is_child_of` only** — the route the audit task's
  refgate proved live for Blueprint generated classes. No parent-class
  property reads, no `get_super_struct` (both were found unreadable on 5.8
  for loaded generated classes, audit task refgate 2026-08-12), no
  protected reflection anywhere. Direct parentage is expressed as TWO
  child_of facts (Heavy→Drill and Drill→Base) rather than a direct-parent
  read; reparenting Heavy straight onto Base flips Heavy→Drill to False
  and fails the guard.
- **Bare corpus Blueprints on purpose**: no components, no variables, no
  graphs. The graded fact is derivation; every extra authored feature is
  aid-side failure surface with zero capability signal. This also keeps
  the corpus inside the proven BlueprintFactory lane (no K2 wiring, no
  SCS, no socket attachment).
- **Single-literal token heads.** Every `TOKEN key=` failure head lives in
  ONE source string literal (the four derivation fail/ok strings are whole
  static literals passed from `_corpus_checks` call sites), so the MATRIX
  oracle's static source grep can verify every expected substring.
- **Error tokens disjoint from graded tokens**: `CORPUS_LIST_PROBE_ERROR`,
  `CORPUS_CLASS_PROBE_ERROR`, `CORPUS_CDO_PROBE_ERROR`,
  `CORPUS_BASE_TYPE_PROBE_ERROR`, `CORPUS_CHILDOF_PROBE_ERROR`,
  `REPORT_PROBE_ERROR`, `REPORT_READ_ERROR`, `KDBS_INTROSPECTION_ABORTED`,
  `CHECK_NOT_EVALUATED` appear in no MATRIX row — a broken UE API is never
  creditable as a named failure.
- **The grammar has ONE line shape** (vs the audit task's five): the report
  is a set of (name, parent) pairs and nothing else. An entirely empty
  report parses (grammar asserts shape, not count) and then fails both
  truth checks — the truth checks iterate pinned constants, never the
  report, so there is no vacuous-pass path.
- **cameras.json not authored**: the deliverable is a text file and bare
  class assets — there is nothing to film. If `cb lint` insists, revisit at
  commit time (the audit-report task set the no-cameras precedent for
  report-deliverable tasks).

## 4. Verifier-owned constants table (the authoring-time truth the introspect embeds)

| constant | value | why this value / what it excludes |
|---|---|---|
| corpus folder | `/Game/Tasks/kp-derived-class-search/corpus` | inside the writable prefix — hence the guard |
| corpus file set | exactly `BP_MachineBase.uasset`, `BP_DrillRig.uasset`, `BP_HeavyDrillRig.uasset`, `BP_MachineBaseplate.uasset`, `BP_ScoutRig.uasset` | additions/replacements/deletions all fail `corpus_set_intact` |
| `BP_MachineBase` parentage | the engine placeable-actor root; CDO must be a placeable actor | the stated base; guard `corpus_base_is_placeable_class` |
| `BP_DrillRig` parentage | derives from `BP_MachineBase` (direct) | true child #1; guard `corpus_drill_derives_base` |
| `BP_HeavyDrillRig` parentage | derives from `BP_DrillRig` (direct), hence transitively from the base | THE transitive child — kills direct-only scans; guard `corpus_heavy_derives_drill` |
| `BP_MachineBaseplate` parentage | engine root; NOT derived from the base | name-stem red herring (shares `MachineBase` as a prefix) — kills stem matching; guard `corpus_baseplate_underived` |
| `BP_ScoutRig` parentage | engine root; NOT derived from the base | suffix red herring (shares `Rig` with both true children) — kills suffix matching; guard `corpus_scout_underived` |
| expected report pairs (`EXPECTED_DERIVED`) | `(BP_DrillRig, BP_MachineBase)`, `(BP_HeavyDrillRig, BP_DrillRig)` | the whole reference report content, order-free |
| report path | `Content/Tasks/kp-derived-class-search/reports/derived.txt` | pre-declared deliverable path |
| report grammar | `^derived name=(\S+) parent=(\S+)$` per non-blank line; no duplicate names | disclosed verbatim in the prompt |

The reference report the aid must produce (order-free):

```text
derived name=BP_DrillRig parent=BP_MachineBase
derived name=BP_HeavyDrillRig parent=BP_DrillRig
```

## 5. Calibration TODOs (run in the authoring-lane editor session)

The aid (`aids/author_reference.py`) prints `KDBS-SPELLING` / `KDBS-WARN`
lines to settle each of these; record the winners here after the run:

- [ ] **BlueprintFactory with a Blueprint GENERATED class as parent** — THE
  unproven step (BP-of-BP creation from stock python). If the factory
  refuses, create `BP_DrillRig` / `BP_HeavyDrillRig` via the desktop
  editor / MCP graph lane (`create_assets` with a BP parent — proven in
  the earlier-task-list unlock campaign) and re-run the aid: it skips existing
  corpus members and still read-back-verifies every parentage fact. The
  GRADER is unaffected either way (it reads the saved class chain).
- [ ] **`class_is_child_of` across the BP-of-BP chain** — proven for
  BP-vs-BP instance identity (audit task refgate); unproven for a
  grandparent chain (`Heavy` vs `Base`). The aid asserts the transitive
  fact explicitly at build time, so a surprise dies in the aid, not in a
  graded run.
- [ ] **`unreal.get_default_object` on the base's generated class** —
  proven route (audit refgate catch); confirm on this corpus.
- [ ] **Corpus asset file naming** — the disk set check assumes the editor
  saves `<AssetName>.uasset` under the corpus folder. Confirm no
  sidecar files (e.g. `.uexp` does not exist in editor saves; OFPA does
  not apply to non-level assets) land there; if any do, widen the pinned
  file set to match reality and re-run.
- [ ] **Optional hash pinning** — after the corpus binaries are final,
  decide whether to add per-file SHA-256 pins to the guard (closes the
  guard-invisible byte-edit residual at the cost of breaking on any
  legitimate corpus recommit). Current decision: NO (asset-fact guard
  only), because the residual provably cannot change the graded outcome.
- [ ] **Empty-FAIL leg + refgate**: `cb discriminate --task
  python/kp-derived-class-search --wip`, then commit binaries + `cb
  refgate python/kp-derived-class-search`.
- [ ] **`cb lint`** over the new task (first flush of any remaining
  `set: python` tooling assumptions; the audit-report task cleared most).
- [ ] **Repo-count edits** — CATALOG row + the `inventory.py` hard-coded
  count claims when this task lands (imported-set precedent).

## 6. Reference status

**Corpus and reference binaries are EMPTY in this change-set — nothing is
fabricated.** This track cannot run UE, so:

- `reference/` does not exist yet (not even as an empty directory). The
  only reference artifact is a 2-line ASCII text file, but it is still
  produced by the aid from READ-BACK truth (derivation recomputed from the
  saved classes via `class_is_child_of`) and self-graded to 10/10 before
  harvest — never hand-typed — so the report and the shipped corpus can
  never disagree.
- The corpus `.uasset` binaries do not exist yet either. The aid builds
  them at their real substrate paths, verifies every pinned parentage fact
  by read-back, and leaves them IN the substrate as the committed baseline
  (it prints one `KDBS-CORPUS` line per file for the commit step).
- Aid cleanup removes only `Content/Tasks/<id>/reports/` from the
  substrate (disk truth; a stale registry row after the validated harvest
  is a `KDBS-WARN`, never a die) — the shipped baseline is corpus-present,
  reports-absent, exactly what `task.md`'s workspace state declares.
- `KDBS-DONE` in the editor log is the success marker; absence = failed.

## 7. Risks

1. **BP-of-BP creation via BlueprintFactory is unproven** (aid-side only).
   Named fallback: MCP graph lane / desktop editor for the two child BPs;
   the aid is idempotent over existing corpus members and re-verifies
   parentage regardless of who authored them. The grader never depends on
   the authoring route.
2. **`class_is_child_of` transitivity over BPGC chains is unproven live**
   (grader-side). Fail-closed: an unevaluable probe is an uncreditable
   `CORPUS_CHILDOF_PROBE_ERROR`, which the refgate run surfaces before any
   agent sees the task. If it genuinely cannot see through BP parent
   chains, the redesign is a two-level corpus (all children direct), which
   weakens but does not kill the task — flagged now on purpose.
3. **Guard byte-blindness residual**: an in-place corpus edit preserving
   the file set and every guarded fact passes the guard; it provably
   cannot change the graded outcome (pinned constants). Accepted; optional
   hash pinning recorded as a calibration decision (§5).
4. **Grader-vs-aid coupling**: the aid imports the real grader and requires
   10/10 in-process; a grader refactor can break the aid loudly (dev-only
   tool; the coupling is what guarantees agreement — audit-task
   precedent).
5. **Source-fidelity risk**: the source row wanted an engine-wide
   `ACharacter` search; this task grades a 5-asset corpus search. The
   capability graded (derivation search + faithful reporting) is the row's
   core; the scope change is recorded as divergence 2/3 rather than
   silently claimed as equivalent.
6. **Empty-leg shape is unusual for the basket** (6/10, not 0/10, because
   the corpus is baseline). MATRIX.md documents it so nobody reads the
   6/10 trajectory signal as a near-pass; `overall` is all-or-nothing as
   everywhere.

## 8. Checklist state (docs/TASK-AUTHOR-GUIDE.md)

- [x] 1. Spec — `task.md` (v2 front matter; behavior-only prompt with the
      disclosed grammar as outcome contract; 5 anti-gaming notes with
      resolvable defense pointers; verifier spec naming every check id and
      failure substring)
- [ ] 2. Scaffold pair — N/A by design (no C++ scaffold; the corpus IS the
      baseline content, authored by the aid)
- [ ] 3. Fixture pair — N/A (no L2; L2I only)
- [ ] 4. Map — N/A (no map anywhere in this task)
- [ ] 5. Camera plan — N/A candidate (nothing renderable; see §3)
- [ ] 6. Reference — PENDING the authoring-lane run of
      `aids/author_reference.py` (this change-set ships the generator, not
      the bytes; corpus baseline binaries pend the same run)
- [x] 7. Discrimination — `discrimination/MATRIX.md`: automatic
      reference-PASS / empty-FAIL rows + the §7a requirements table (8
      rows, every prompt requirement mapped to a live assertion; no
      variant owed)
- [ ] 8. Gates — blocked on the corpus/reference binaries (lint can run
      now; discriminate/refgate cannot)
- [ ] 9. Commit + PR + refgate close — future work

## Accepted residuals (moved from task.md 2026-08-16; lint spec-h2-allowlist)

- **Corpus byte edits invisible to the guard are not caught.** The guard
  asserts the file set and the derivation facts, not byte hashes (the
  binaries do not exist at spec-authoring time, and byte hashes would break
  on any legitimate substrate recommit). An in-place corpus edit that
  changes none of the guarded facts — e.g. adding a component to
  `BP_ScoutRig` — passes the guard; it also cannot change the graded
  outcome, because the report is graded against pinned constants, so the
  residual is cosmetic. Recorded with a calibration note (`notes.md` §4) to
  optionally pin sizes/hashes after the authoring run if wanted.
- **`parent=` is only graded on the two derived classes.** The direct
  parents of the base and the herrings are never reported (they have no
  report line), so their exact engine-side parentage is a guard concern
  ("not derived from the base"), not a report concern. By design.
- **A submission that opens each asset by hand and types the report
  passes.** That is the basket's design (outcome-graded, no mechanism
  gate), not a leak.
- **The corpus is only guarded at grade time.** An agent that modifies the
  corpus mid-run and restores it byte-perfectly before finishing is
  indistinguishable from one that never touched it — acceptable: the graded
  contract is the final state.
