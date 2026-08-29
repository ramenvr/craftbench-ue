# kp-config-source-audit — authoring notes

Wave-3 `tasks/python/` basket task (outcome-graded editor-scripting;
deliverable = resulting editor state / text report; no gate asserts
"python was used"). Pattern: the strict-grammar report CROSS-CHECK
(exemplar `kp_blueprint_actor_audit_report.py`) plus a new element this
wave introduces — a **corpus-unmodified guard** protecting committed
evidence that lives inside the agent-writable prefix.

## 1. Provenance (source row)

- **Source**: an earlier internal task list (not shipped) — a data-asset
  config row, "Data asset read ability set".
- **Its cells**: capability *"Whether it can find the right data asset
  for GAS config in a Lyra project"*; verification *"will need to write a
  python script that does this correctly and check resulting output
  against the output of Aura"*; expected outcome *"discovers or infers
  AbilitySet_ShooterHero and lists its abilities"*; prompt *"what are the
  current default player abilities?"*; substrate *"Lyra Project"*.
- **Id scheme**: `kp-` is the python-basket family prefix; this row comes
  from a different part of the source list but lands in the same basket
  under the same prefix convention (wave-3 decision: basket = deliverable
  surface, prefix = basket family, provenance recorded here). Substring
  audit: `kp-config-source-audit` is not a substring of any other task id
  and contains none.

## 2. Divergences from the source row (full record)

| # | source row | this task | why |
|---|---|---|---|
| 1 | Lyra Project substrate; `AbilitySet_ShooterHero` | verifier-authored corpus + wiring on `ThirdPerson` | **There is no Lyra substrate** (Hard Rule 5; `AUTHORING_TEMPLATE.md` records that `substrate: lyra` never existed on disk). The row's discriminating capability — find the RIGHT config asset among plausible ones by tracing what the live object references, not by name vibes — is reproduced with a controlled corpus: 4 look-alike candidates, deceptively named, one wired live via a committed rig, decoys referenced by nothing |
| 2 | "lists its abilities" | "states the one stored value" | the Lyra ability list does not exist off Lyra; a single exact float preserves the read-the-right-asset gate with a deterministic compare |
| 3 | conversational answer, judged against Aura's own output | plain-text `reports/config.txt` with a strict disclosed grammar | chat output is not a deliverable this harness grades; grading "against the output of Aura" would grade Aura with Aura (`craftbench-aura-mcp-auth` law). The file + pinned-constant cross-check is the established `kp-` idiom |
| 4 | "infers" accepted as success | inference-by-name is the ENGINEERED FAILURE mode | the source row's own success cell rewards name-guessing ("discovers **or infers**"). This task inverts that: names anti-correlate with liveness (`Flash_Archive_2024` is live; `Flash_Current`/`Flash_Primary` are decoys), so the shortcut the source row rewarded is the one this task reliably fails |
| 5 | no tamper protection (read-only chat task) | corpus-unmodified guard (7 of 12 checks) | our agent WRITES into `Content/Tasks/` (sandbox-writable), so the evidence must be re-asserted at grade time or the task is trivially gamed by editing the corpus/wiring to match a guessed report |
| 6 | GAS flavor | "dash-flash brightness" flavor, no GAS plugin surface | keeps the id's `gas-config` provenance without needing AbilitySystem assets; the graded capability (config-in-assets tracing) is engine-system-agnostic |

## 3. Design decisions

- **Corpus carriers are Blueprint assets, not literal `UDataAsset`
  instances.** A typed DataAsset needs a property-bearing class first,
  and BP member-variable creation from stock python is the one step the
  audit-report task could NOT prove (its reference needed the MCP graph
  lane for variables). This task's whole authoring surface is
  REFGATE-PROVEN primitives only: BlueprintFactory creation, subobject
  add via the ENGINE `SubobjectDataSubsystem`, template property writes.
  The value lives on a stock component property
  (`PointLightComponent.intensity` of the part `Glow`), the wiring
  reference on a stock component property
  (`ChildActorComponent.child_actor_class` of the slot `FlashSlot`) —
  component/property/asset-reference wiring only, **zero K2 graph
  nodes, zero BP member variables, zero CDO reads** anywhere in aid or
  grader.
- **The wiring is a class reference, not event-graph logic.** The rig
  "produces one candidate when the flash fires" is realized as a
  child-actor slot holding the live candidate's class — a real,
  runtime-meaningful reference (the engine would spawn it), readable
  headless from the SCS template, and authorable without graph wiring
  (the K2-wiring lane is not available; task card law).
- **Deceptive names are the point.** The source row rewarded "infers"; the
   corpus punishes it. Live = the "archive"; the two plausible names are
  decoys; `Flash_Test_DoNotUse` bait-inverts twice.
- **Every pinned value excludes the untouched default** (row R5
  `intensity == 5000` dead-gate lesson): fresh point-light intensity is
  5000.0; the pins are 1450 / 950 / 725 / 1200. All four distinct, so a
  value can never ambiguously identify two candidates and a
  right-path+wrong-value report always fails.
- **Guard + pins + live trace are three separate nets.** Pins catch a
  wrong report; the guard catches evidence edits; the live-trace check
  (`report_agrees_with_wiring`) binds the report to what is ACTUALLY
  wired, so pin-vs-guard gaps (e.g. a rewire) can never cancel out.
- **Empty leg is 7/12 by design**, not 0/12: the guard checks pass on an
  intact baseline — they discriminate tampering, not effort. Overall
  still FAILs via `report_file_present` (`CONFIG_REPORT_MISSING path=`),
  which is the empty leg's named substring in MATRIX.md.
- **Single-literal token heads** (MATRIX-oracle law): every `TOKEN key=`
  head lives in ONE source literal; the grammar-failure template is
  emitted by one `_grammar_bad` helper. Error tokens are disjoint from
  graded tokens and appear in no MATRIX row.
- **Fail-closed proven offline** (py -3.13, 2026-08-12): no-module leg =
  12 checks, all failing, only uncreditable `*_PROBE_ERROR` tokens;
  baseline-absent fake-module leg = 12 checks failing with the graded
  `CORPUS_SET_CHANGED` / `CORPUS_ASSET_MISSING` / `WIRING_RIG_MISSING` /
  `CONFIG_REPORT_MISSING` root causes; grammar parser accepts the
  reference shape, rejects extras/duplicates/missing lines; object-path
  normalization collapses `/pkg/Name.Name` to `/pkg/Name`.
- **cameras.json not authored**: nothing in this task renders or places
  anything in a level; a camera plan has no subject. Confirm at lint
  whether the SHOULD-ship rule wants a stub anyway.

## 4. Verifier-owned constants (the authoring-time truth the introspect embeds)

| constant | value | role |
|---|---|---|
| corpus folder | `/Game/Tasks/kp-config-source-audit/corpus` | enumerated by `corpus_set_exact` |
| `Flash_Primary` | 1450.0 | decoy (plausible name, referenced by nothing) |
| `Flash_Current` | 950.0 | decoy (the name bait) |
| `Flash_Archive_2024` | **725.0** | **LIVE** (deceptively "dead" name) |
| `Flash_Test_DoNotUse` | 1200.0 | decoy (double-bluff name) |
| value part / property | part `Glow`, a point-source light; its intensity | where every value is stored |
| fresh-part default | 5000.0 | excluded by every pin (dead-gate audit) |
| wiring artifact | `/Game/Tasks/kp-config-source-audit/wiring/BP_DashRig` | the one trace root |
| slot | `FlashSlot` (child-actor slot) | holds the live class |
| pinned slot class | `/Game/Tasks/kp-config-source-audit/corpus/Flash_Archive_2024.Flash_Archive_2024_C` | exact object-path compare |
| live report answer | `source asset=/Game/Tasks/kp-config-source-audit/corpus/Flash_Archive_2024` + `value brightness=725` | what reference/config.txt will contain |
| value tolerance | 1e-3 | pre-calibration |
| check denominator | 12 (7 guard + 5 report) | constant on every leg |

The aid (`aids/author_reference.py`) embeds the same table and **cross-dies
at startup** if its pins and the imported grader's pins ever disagree.

### Calibration TODOs (run in the authoring-lane editor session)

The aid prints `KPGCA-SPELLING` lines to settle each; record winners here:

- [ ] **`child_actor_class` template write/read** — THE unproven step of
  this task (set via `set_editor_property` spellings, then the
  `set_child_actor_class` method; read via the same two spellings in the
  grader). If no route works, the named fallback is authoring the slot
  through the MCP graph lane (`edit_blueprint` — component property
  defaults, still no graph nodes), and re-running the aid with the
  wiring step skipped; the GRADER is unaffected (it only reads).
- [ ] **`ChildActorComponent` via `add_new_subobject`** — precedented
  (mesh/light adds proven) but unproven for this component class.
- [ ] **`list_assets` return shape** under `-nullrhi` (object paths vs
  package paths; whether an asset-registry scan wait is needed before
  `corpus_set_exact` sees all four).
- [ ] **`intensity` read-back precision** — confirm 725.0 survives
  save/reload exactly; tighten or keep 1e-3.
- [ ] **Hash-guard upgrade** — once the baseline binaries are committed,
  record their file hashes and consider adding byte-hash assertions on
  the five files alongside the asset-fact guard (closes the
  fact-preserving-rewrite residual). Hashes CANNOT be pinned today: the
  binaries do not exist yet (this track cannot run UE).
- [ ] **Guess-ceiling decision** — the 1-in-4 blind-guess residual
  (task.md). If unacceptable after first agent runs, rev options:
  6-8 candidates, or per-run randomized live pick (`randomization` key +
  per-run corpus authoring — a harness feature ask, not a spec edit).
- [ ] **`cb lint --task python/kp-config-source-audit`** as the first gate
  after this change-set lands.
- [ ] **Repo-count edits** — CATALOG row + inventory count claims when
  this task lands (imported-set precedent).

## 5. Reference + baseline status

**This track cannot run UE, so NO binary in this change-set exists yet
and none is fabricated:**

- `reference/` is EMPTY (not even committed as a directory).
- The corpus/wiring baseline binaries do not exist yet either — unlike
  the sibling tasks, this task's baseline is itself verifier-authored
  content that the aid builds INTO the substrate
  (`UE-projects/ThirdPerson/Content/Tasks/kp-config-source-audit/`), where
  it must then be COMMITTED as substrate baseline (the aid prints one
  `KPGCA-BASELINE` line per file for the commit).

`aids/author_reference.py` is the single generator for both products: it
builds the four corpus BPs and the wiring rig at their real content paths
(read-back verifying every step through the REAL grader's own helpers),
writes `reports/config.txt` from a fresh live trace (never from the pins
— the pins only cross-check), grades itself in-process against the real
introspect, harvests the report into `reference/` ONLY on a 12/12 vector,
deletes the report from the substrate, and leaves the baseline in place.
`KPGCA-DONE` in the editor log is the success marker; absence = failed.
Cleanup treats DISK as truth: a stale in-memory registry row after the
validated harvest is a `KPGCA-WARN`, never a die.

## 6. Risks

1. **`child_actor_class` authoring/reading is unproven** for SCS
   templates from stock python (both directions fail closed; the
   reference gate surfaces a break before any agent run). Fallback: MCP
   graph lane for the slot property (aid only; grader unaffected).
2. **Baseline-commit ordering.** Until the aid's output is committed,
   any git-HEAD grade fails the guard with `CORPUS_ASSET_MISSING path=`
   — a wrong-reason FAIL. The MATRIX status block and §5 flag this;
   refgate must run only after the baseline commit. Also: the baseline
   commit touches the SUBSTRATE tree, so it must respect the
   no-git-during-a-bench law and will show as a substrate diff on the PR
   (expected; it IS the task's workspace state).
3. **Guard-vs-sandbox seam.** The corpus lives inside `Content/Tasks/`
   (agent-writable by design of the basket), so the guard — not the
   sandbox — is the only tamper defense. If a future sandbox change adds
   per-task read-only carve-outs, this task should adopt one and keep
   the guard as belt-and-braces.
4. **1-in-4 blind guess** passes a single run (accepted residual,
   task.md; rev options in §4).
5. **Fact-preserving corpus rewrite** is invisible to the fact-based
   guard until the hash upgrade (accepted residual; no graded fact can
   be changed by it, by definition).
6. **Grader helper reuse by the aid** (`_read_glow`, `_scene_components`,
   `_read_property`): a grader refactor can break the aid silently.
   Accepted: the aid dies loudly and is dev-only; the coupling is what
   guarantees aid/grader agreement (sibling precedent).
7. **Prompt narrative vs runtime truth.** The rig is a committed
   artifact no gameplay code invokes; the prompt frames it as "the
   committed object that decides where the brightness comes from",
   which is true of the artifact chain being graded. An agent that goes
   hunting for a runtime consumer will find none — the prompt points at
   the two committed folders explicitly to keep the trace bounded.

## 7. Checklist state (docs/TASK-AUTHOR-GUIDE.md)

- [x] 1. Spec — `task.md` (v2 front matter; behavior-only prompt with the
      basket's exactness exception; 5 anti-gaming notes with resolvable
      defense pointers; verifier spec with named failure substrings)
- [ ] 2. Scaffold pair — N/A by design (no C++ scaffold; content+text
      task)
- [ ] 3. Fixture pair — N/A (no L2; L2I only)
- [ ] 4. Map — N/A (no map anywhere in this task; no `docs/MAPS.md` row)
- [ ] 5. Camera plan — likely N/A (nothing renders; confirm at lint)
- [ ] 6. Reference — PENDING the authoring-lane run of
      `aids/author_reference.py` (this change-set ships the generator,
      not the bytes; the run also produces the substrate BASELINE that
      must be committed)
- [x] 7. Discrimination — `discrimination/MATRIX.md`: automatic
      reference-PASS / empty-FAIL rows + the §7a requirements table
      (7 rows, every requirement mapped to a live assertion; no variant
      owed)
- [ ] 8. Gates — blocked on the baseline + reference binaries (lint can
      run now; discriminate/refgate cannot)
- [ ] 9. Commit + PR + refgate close — future work

## Accepted residuals (moved from task.md 2026-08-16; lint spec-h2-allowlist)

- **A 1-in-4 blind guess passes.** With four candidates, an agent that
  ignores the wiring, picks a path at random, and honestly reads THAT
  asset's value has a 25% single-run pass chance. Accepted for v1 and
  recorded here honestly: the corpus size is the card's 3-4, the guess
  still requires opening the guessed asset (reading the value), and the
  deceptive naming makes the *systematic* shortcuts (name heuristics)
  reliably WRONG rather than 25% right. A future rev can randomize the
  live pick per run (`randomization` key + per-run corpus authoring) —
  out of scope now, noted in `notes.md` §4.
- **A byte-level corpus rewrite that preserves every pinned fact
  passes the guard.** The guard asserts introspected facts (set, part,
  type, value, slot class), not file hashes — a re-save that changes no
  graded fact is invisible to it. No graded consequence follows (the
  facts ARE the evidence); a hash upgrade once the binaries are
  committed is a calibration TODO (`notes.md` §4).
- **Subclass-tolerant part typing.** A part named `Glow` of a
  point-light-derived class satisfies the guard's type gate (repo law);
  the guard's value pin is what actually protects the evidence.
- **Path-format tolerance.** The grader accepts the object-path form
  `/pkg/Name.Name` for the source line by collapsing it to `/pkg/Name`
  when the object name repeats the package tail — the one deliberate
  tolerance, disclosed in the verifier spec above; nothing else is
  normalized.
- **No gate asserts the mechanism** (basket law): a hand-authored
  editor session, MCP-driven inspection, or any other route producing a
  truthful report passes. That is the basket's design, not a leak.
