---
id: kp-derived-class-search
substrate: ThirdPerson
set: python
tier: T1
capability_bucket: Content Integration
category: other
layers: [L1, L2I]
introspect: [kp_derived_class_search.py]
---

# kp-derived-class-search

A `tasks/python/` basket task (owner decision 2026-08-11): **outcome-graded
editor-scripting work**. The deliverable is ONE plain-text report describing
a class-derivation fact the agent must dig out of a verifier-authored asset
corpus — graded by the deterministic L2I introspect lane exactly like the
`bp` basket. The prompt describes an outcome whose exactness (an exact set,
exact names, an exact machine-checkable grammar, a direct-parent column)
makes editor scripting the natural way to complete it, but **no gate asserts
"python was used"** — opening each asset by hand and reading its base class
off the editor UI produces the same bytes and passes identically. A future
v2 may additionally re-execute a submitted script; that is deliberately not
this version.

### Provenance and deliberate divergences from the source row

Imported from an earlier internal task list (not shipped): a usage-search row,
described there as "Search for derived blueprints".
The source row's whole prompt: *"What are all the blueprints in my project that
derive from ACharacter?"* on an *Empty Project* — an **answer-shaped** row
(a chat question expecting a chat answer, no gradable artifact, and on an
empty project the true answer is vacuously "none"). Full divergence record:
`notes.md` §2. Headlines:

1. **Chat answer becomes a strict-grammar FILE.** A printed/spoken answer is
   not an artifact this harness grades deterministically; the answer becomes
   a plain-text report at a pre-declared path with a disclosed grammar (the
   `datatable_csv_export.py` text-artifact idiom, as in the sibling
   audit-report task).
2. **The engine-wide search space becomes a verifier-authored corpus.**
   "All the blueprints in my project" is unbounded, substrate-dependent, and
   empty on the source row's own Empty Project. The searchable universe is
   re-scoped to five verifier-authored class assets under
   `Content/Tasks/<id>/corpus/`, forming a small inheritance tree with one
   transitive child and two red herrings — small enough to grade exactly,
   rich enough that name-matching and direct-only scans both fail.
3. **`ACharacter` becomes a corpus-local stated base.** An engine class name
   in the prompt violates Hard Rule #2; the stated base is the corpus asset
   `BP_MachineBase`, named like any other graded value.
4. **A direct-parent column is added.** The source row's yes/no membership answer
   is guessable at 1-in-16 over a 4-candidate corpus; requiring each line to
   also carry the class's DIRECT base forces reading the real derivation
   chain (and distinguishes the transitive child from a flat list).
5. **A corpus-unmodified guard is added.** The corpus lives inside the
   agent-writable `Content/Tasks/` prefix, so "search the shipped corpus"
   is enforced as a gate: any drift in the corpus file set or its pinned
   derivation facts fails with a named `CORPUS_MODIFIED_*` message (same
   defense pair as the sibling usage-search task: verifier-owned expected
   constants + corpus-unmodified guard).

> **Note on the behavior-only rule (Hard Rule #2).** Like the other
> python-basket tasks, this prompt names the concrete deliverable path, the
> five corpus asset names, the stated base and the exact report grammar —
> the standard, precedented exception for tasks whose whole point is
> producing exactly-specified artifacts (the graded values ARE the outcome
> contract, and the disclosed grammar lines are part of it). **No engine
> class name, no API name, no editor-operation name appears in the
> prompt.** "Based on", "derives", "class" and "immediate base" describe the
> relationship behaviorally; the mechanism for reading it is the agent's.

## Primary concept

- `ps-asset-registry` — Asset Registry
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/asset-registry-in-unreal-engine)

The load-bearing capability is **searching committed project content by a
structural fact that is not visible in asset names** — enumerate a folder,
resolve each asset's class identity, walk derivation, and report the result
faithfully. The registry's derived-class queries are the textbook mechanism
(the adjacent concept is `ps-scripting-editor-python`, Scripting the Unreal
Editor Using Python,
https://dev.epicgames.com/documentation/en-us/unreal-engine/scripting-the-unreal-editor-using-python
— any reflection route that reads the same truth passes; the verifier
grades the outcome, not the query API).

## Prompt given to the agent

> The folder `Content/Tasks/kp-derived-class-search/corpus/` ships with
> five pre-authored placeable object classes: `BP_MachineBase`,
> `BP_DrillRig`, `BP_HeavyDrillRig`, `BP_MachineBaseplate`, and
> `BP_ScoutRig`. Some of them are based on others; their names do NOT tell
> you which — the only source of truth is the classes themselves. The task
> is graded with the corpus exactly as shipped: changing, replacing, or
> adding anything under `corpus/` fails the task.
>
> Determine which of the five classes are based on `BP_MachineBase` —
> directly, or through any chain of intermediate classes — and write the
> result to a plain-text report at
> `Content/Tasks/kp-derived-class-search/reports/derived.txt`. The
> report contains one line per class that IS so based (never
> `BP_MachineBase` itself), and no lines of any other kind; blank lines are
> ignored and order does not matter. Each line has exactly this shape:
>
> ```text
> derived name=<class-name> parent=<direct-base-name>
> ```
>
> where `<class-name>` is the exact name of the qualifying class and
> `<direct-base-name>` is the exact name of the class it is DIRECTLY based
> on — its immediate base, not the far end of the chain. Names are
> case-sensitive, contain no spaces, and must match the shipped names
> exactly; no class may appear on more than one line. Every line is checked
> against what is actually on disk: a listed class that is not based on
> `BP_MachineBase`, a missing class that is, or a wrong `parent` value all
> fail the task.

## Workspace state pre-task

Substrate content that **exists** under
`Content/Tasks/kp-derived-class-search/`:

- `corpus/BP_MachineBase.uasset`, `corpus/BP_DrillRig.uasset`,
  `corpus/BP_HeavyDrillRig.uasset`, `corpus/BP_MachineBaseplate.uasset`,
  `corpus/BP_ScoutRig.uasset` — five verifier-authored placeable-class
  assets forming a small inheritance tree (authored by
  `aids/author_reference.py` in the authoring-lane editor session and
  committed as binaries; their true parentage is recorded verifier-side in
  `notes.md` and pinned in the introspect constants, never in any
  agent-visible file). The folder is inside the agent-writable
  `Content/Tasks/` carve-out of the `ThirdPerson` substrate — which is
  exactly why the verifier carries a corpus-unmodified guard.

Files that **do not exist** (the agent must create the report; nothing
else):

- `Content/Tasks/kp-derived-class-search/reports/derived.txt` — the
  ONLY deliverable.

Out of scope / not needed:

- No C++ is required or expected; no level is involved. `Content/Maps/`
  and the stock content folders are deny-listed — the agent neither can
  nor needs to touch them.

## Verifier specification

Layer choice: **L1 + L2I**. Every graded property is a static property of
saved editor state (the corpus class assets) or of a text file, read by
verifier-owned editor-Python reflection. L2 is deliberately not declared:
nothing runs, nothing evolves over time, no map exists. Nothing asserts
*how* the report was produced (basket law: outcome-graded, no "python was
used" gate).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

The submission is one text file, so L1 is a precondition (the project must
load cleanly), never a correctness signal.

### L2I — Corpus guard + report cross-check

The verifier-owned script
`tools/verify-single/introspect/kp_derived_class_search.py` runs
headless via `UnrealEditor-Cmd -ExecutePythonScript=` under `-nullrhi`,
read-only, and prints one `CRAFTBENCH-INTROSPECT-JSON` verdict block with
**exactly 10 named checks on every leg** (constant denominator). PASS
requires all 10. No level is loaded — the corpus is class assets only.

Group 1 — the corpus-unmodified guard (6 checks; expected facts PINNED in
the script's constants):

```text
corpus_set_intact               the on-disk corpus folder contains EXACTLY
                                the five shipped .uasset files (disk truth
                                via os.walk, registry-lag-proof; additions,
                                replacements-by-rename and deletions all
                                fail: CORPUS_MODIFIED_SET files=)
corpus_base_is_placeable_class  BP_MachineBase's generated class resolves
                                and its default object is a placeable actor
                                (CORPUS_MODIFIED_BASE_CLASS class=)
corpus_drill_derives_base       BP_DrillRig still derives from
                                BP_MachineBase
                                (CORPUS_MODIFIED_DRILL_PARENT name=)
corpus_heavy_derives_drill      BP_HeavyDrillRig still derives from
                                BP_DrillRig — which, with the previous
                                check, pins the transitive chain
                                (CORPUS_MODIFIED_HEAVY_PARENT name=)
corpus_baseplate_underived      BP_MachineBaseplate is still NOT derived
                                from the base (the name-stem herring)
                                (CORPUS_MODIFIED_BASEPLATE_PARENT name=)
corpus_scout_underived          BP_ScoutRig is still NOT derived from the
                                base (the suffix herring)
                                (CORPUS_MODIFIED_SCOUT_PARENT name=)
```

Derivation is read via `class_is_child_of` on the generated classes (the
route the audit task's refgate proved live); an asset whose class no longer
resolves is the graded `CORPUS_MODIFIED_CLASS_UNRESOLVED name=`; an
unavailable API is an uncreditable `*_PROBE_ERROR`. The two `underived`
absence checks are conjoined with the positive class-resolution reads that
produced them — they never pass because a probe could not run.

Group 2 — the report (4 checks; expected values PINNED, never recomputed
from anything the agent can write):

```text
report_file_present             Content/Tasks/<id>/reports/derived.txt
                                exists (REPORT_FILE_MISSING path=)
report_grammar_parses           every non-blank line matches the one
                                disclosed shape; no duplicate names
                                (REPORT_GRAMMAR_BAD line=)
report_derived_set_exact        the reported name set EQUALS the pinned
                                {BP_DrillRig, BP_HeavyDrillRig} in BOTH
                                directions — a listed herring fails, an
                                omitted transitive child fails
                                (DERIVED_SET_MISMATCH reported_only=)
report_parent_lines_truthful    iterating the PINNED pairs (never the
                                report, so an empty report fails here too):
                                BP_DrillRig's parent is BP_MachineBase and
                                BP_HeavyDrillRig's parent is BP_DrillRig —
                                the flat-parent line naming the far ancestor
                                fails (DERIVED_PARENT_WRONG problems=)
```

**The gold-leak defense.** Every *expected* value (the five corpus names,
the four derivation facts, the two expected report pairs) is **pinned in
the verifier script's constants**. The corpus guard asserts the live corpus
still matches the pins; the report is graded against the pins. Tampering
with the corpus can therefore never move the bar — it can only add a named
`CORPUS_MODIFIED_*` failure.

**Fail-closed properties** (mirroring the set convention):

- A missing report fails all four report checks with the one named root
  cause `REPORT_FILE_MISSING path=` fanned out; an empty report parses but
  fails both truth checks (the pinned expected set is non-empty by
  construction) — never a vacuous pass and never a shrunken denominator.
- The empty submission scores **6/10** (the corpus is substrate baseline,
  so its guard legitimately passes) and the overall verdict is FAIL via the
  report group. The denominator is 10 on every leg.
- Error tokens (`*_PROBE_ERROR`, `*_READ_ERROR`, `*_ABORTED`,
  `CHECK_NOT_EVALUATED`) are disjoint from graded failure tokens and appear
  in no MATRIX row, so a broken UE API can never be credited as a variant's
  named failure.
- All details are ASCII-only (the cp1252 log read-back trap,
  `t2-homing-projectile` 2026-07-21).

**Known-risk reads, all fail-closed** (full list + calibration plan in
`notes.md` §4): `class_is_child_of` across a Blueprint-parent CHAIN
(BP-of-BP) is precedented for instance identity but unproven for this exact
shape; `unreal.get_default_object` on a generated class is the audit task's
proven route. None of these can produce a false PASS — only an uncreditable
FAIL, which the reference-gate run will surface before any agent sees the
task.

**Score granularity.** `registry.py` reports `tests_passed/tests_run`, so
`report.json` carries `x/10` as trajectory signal while `overall` stays
`all(pass)`.

## Reference solution metadata

- LOC range: **0** lines of module code. The deliverable is one 2-line text
  file; the natural route is a throwaway editor-python script of roughly
  15-50 lines the agent writes and runs (not itself graded or submitted).
- Files touched: 1 created (`reports/derived.txt`), 0 modified.
- Senior-dev hours: 0.25-1.0 — the search itself is minutes in an open
  editor; the honest scripted route requires knowing folder enumeration,
  class resolution and derivation-walk APIs, and the exact-grammar report
  discipline is where careless solutions die.

## Anti-gaming notes

1. **Name-similarity guessing.** *Failure mode*: the agent never opens the
   corpus and lists whatever *sounds* derived — `BP_MachineBaseplate`
   shares the base's name stem, and `BP_ScoutRig` shares the true
   children's `Rig` suffix, so every naming heuristic picks at least one
   herring or drops a child. *Defense*: `report_derived_set_exact` is a
   two-directional set equality against the pinned truth
   (`DERIVED_SET_MISMATCH reported_only=`); the corpus was authored so that
   name-set and truth-set disagree in both directions. Pointer:
   `kp_derived_class_search.py::_report_checks` and the
   `EXPECTED_DERIVED` / `UNDERIVED_NAMES` constants.
2. **Direct-only scan.** *Failure mode*: the agent checks only immediate
   parentage against the base and omits the transitive child
   `BP_HeavyDrillRig`. *Defense*: the pinned expected set contains the
   transitive child, so the omission fails the same set equality
   (`DERIVED_SET_MISMATCH reported_only=` with the child in
   `expected_only`). Pointer: `EXPECTED_DERIVED` in
   `kp_derived_class_search.py`.
3. **Flat-parent shortcut.** *Failure mode*: the agent finds the right set
   but writes `parent=BP_MachineBase` on every line instead of each class's
   direct base. *Defense*: `report_parent_lines_truthful` iterates the
   pinned (name, direct-parent) pairs — `BP_HeavyDrillRig` must report
   `BP_DrillRig` (`DERIVED_PARENT_WRONG problems=`). Pointer:
   `kp_derived_class_search.py::_report_checks`, second block.
4. **Corpus tampering.** *Failure mode*: the agent edits the corpus to
   match a guessed report — reparent a herring onto the base, replace a
   corpus asset, or add its own derived class to the folder (all
   physically possible: `corpus/` is inside the writable `Content/Tasks/`
   prefix and the overlay can overwrite baseline files). *Defense*: the
   six-check corpus guard — disk-truth file-set equality
   (`CORPUS_MODIFIED_SET files=`) plus four pinned derivation facts
   (`CORPUS_MODIFIED_BASEPLATE_PARENT name=`, etc.); and because the report
   is graded against PINNED constants, tampering cannot move the bar even
   before the guard fires. Pointer:
   `kp_derived_class_search.py::_corpus_checks`.
5. **Report transcribed from the brief.** *Failure mode*: the agent copies
   the answer out of the prompt without touching the corpus. *Defense*: the
   prompt does not contain the answer — it names the five classes and the
   base but states that names do not encode parentage; the derivation facts
   exist only inside the committed binaries and the verifier's own
   constants. A lucky blind guess over the 4 candidates must also produce
   both exact direct-parent values to pass. Pointer: the prompt text above
   + `EXPECTED_DERIVED`.

## Hidden invariants

- **The check denominator is fixed at 10 on every leg.** A submission
  cannot improve its reported ratio by making checks unreachable.
- **The pinned truth-set and the name-similarity set disagree in both
  directions** (a herring shares the base's stem; a true child is only
  transitively derived). Any future corpus edit must preserve this
  property or the task loses its discrimination — re-run the §7a table's
  R03/R05 rows after any corpus change.
- **A failed prerequisite fans out its own root-cause token** — dependent
  checks never invent unrelated failures, so a wrong-reason FAIL is
  visible as an uncredited token.
