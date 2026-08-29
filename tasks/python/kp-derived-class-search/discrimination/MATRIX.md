# Discrimination matrix — kp-derived-class-search

Self-validation oracle, authored under the **2026-08-11 amended section 7**:
the mandatory artifacts are the automatic reference-PASS / empty-FAIL legs
plus the **requirements table** below — not a variant per anti-gaming note.
The requirements table still finds no *unenforced* requirement, and yet two
hand-authored variants ship (added 2026-08-17), because the automatic legs
leave both TRUTH gates unproven in the direction that matters. `empty` dies
at the presence gate, so it says nothing about the two truth checks; and a
reference-PASS leg cannot catch a truth check that is too WEAK — a set check
written one-directionally, or a parent check that only tested presence, would
grade the reference PASS *and* grade a plausible-wrong report PASS. Each
variant below is a one-line delta on the reference report that isolates
exactly one of those two checks (9/10 each), and the two die at DIFFERENT
check ids.

> **STATUS: TEXT-ONLY TRACK (never executed against a real editor).** The
> corpus binaries and the reference report do not exist yet; both are built
> by `../aids/author_reference.py` in the authoring-lane editor session,
> which self-grades against the real introspect script and requires 10/10
> before harvesting. Until that run and the git-HEAD refgate, every row here
> is an offline claim (offline proofs listed under *Status* at the bottom).

## Parser traps honoured (inherited from the audit-report matrix)

- **ONE table with submission rows.** `discriminate.parse_matrix` keys rows
  by first-column label; the submission table below is the only one whose
  first column contains submission labels — the requirements table uses
  `R##` keys that collide with no submission dir.
- **Every expected-substring cell is backtick-wrapped and contains a space
  and `=`** (the `_extract_substrings` substantiveness rule), and each is a
  verbatim substring of a raw `detail` printed inside the
  `CRAFTBENCH-INTROSPECT-JSON` block, living in ONE source string literal of
  `tools/verify-single/introspect/kp_derived_class_search.py`.
- **The reference row's substring cell is `—`** (maps to the empty tuple).
- **ASCII rule**: every substring is ASCII-only (the cp1252 log read-back
  trap); the whole introspect script is ASCII by construction.
- **Error tokens are disjoint from failure tokens.** `*_PROBE_ERROR` /
  `*_READ_ERROR` / `*_ABORTED` / `CHECK_NOT_EVALUATED` appear in no row
  here, so a broken UE API name can never be credited as a named failure.

## Layout

- `../reference/Content/Tasks/kp-derived-class-search/reports/derived.txt`
  — the one correct solution (the report ONLY; deliverable = report only),
  **pending the authoring-lane run** of `../aids/author_reference.py`. The
  corpus binaries are NOT part of the reference overlay — they are substrate
  baseline, committed under
  `UE-projects/ThirdPerson/Content/Tasks/kp-derived-class-search/corpus/`
  by the same authoring run.
- empty leg — run implicitly by `cb discriminate` (throwaway empty dir;
  nothing to author).
- `lists-name-stem-herring/Content/Tasks/kp-derived-class-search/reports/derived.txt`
  — the reference report PLUS one line claiming the name-stem herring
  `BP_MachineBaseplate` is based on `BP_MachineBase` (anti-gaming note #1;
  requirement R03). The line is well-formed and both pinned pairs stay
  truthful, so `report_derived_set_exact` is the ONE check that fails:
  **9/10**.
- `flat-parent-lines/Content/Tasks/kp-derived-class-search/reports/derived.txt`
  — the exactly-correct derived set, with `BP_HeavyDrillRig`'s `parent`
  flattened to the far ancestor `BP_MachineBase` instead of its direct base
  (anti-gaming note #3; requirement R04). Set equality still passes, so
  `report_parent_lines_truthful` is the ONE check that fails: **9/10**.

Because the corpus is substrate baseline, the empty leg scores **6/10**
(corpus guard green, report group red), not 0/10 — the FAIL is still
unambiguous and lands on the named report root cause below.

## Matrix

**This is the only table in this file whose first column is a submission.**

| Submission | Overall | Fails at (check id) | Expected substring | Also fails (recorded, not matched) | Anti-gaming note |
|---|---|---|---|---|---|
| `../reference` | PASS | — | — | none — all 10 checks green (10/10) | — |
| empty | FAIL | `report_file_present` | `REPORT_FILE_MISSING path=` | the 3 remaining report checks fan out the same root cause; corpus guard passes (6/10) | #5 / FR-017 non-vacuity |
| `lists-name-stem-herring/` | FAIL | `report_derived_set_exact` | `DERIVED_SET_MISMATCH reported_only=` | nothing else — 9/10: presence, grammar and both pinned parent facts PASS | #1 name-similarity guessing |
| `flat-parent-lines/` | FAIL | `report_parent_lines_truthful` | `DERIVED_PARENT_WRONG problems=` | nothing else — 9/10: presence, grammar and set equality PASS | #3 flat-parent shortcut |

## Requirements table (the mandatory §7a artifact)

One row per requirement in the agent-visible prompt. Assertion pointers name
the check id (all in
`tools/verify-single/introspect/kp_derived_class_search.py`; find a
check id in the `CHECK_IDS` tuple and its emitting function). "Skipped when"
names the ONLY condition under which the gate does not evaluate its own
predicate — in every such case the check still FAILS with the prerequisite's
root-cause token (fanout), never a silent pass.

| Key | Prompt requirement | Asserted | Check id (assertion) | Named failure substring | Skipped when | What a submission could get away with |
|---|---|---|---|---|---|---|
| R01 | the report exists at `reports/derived.txt` | fully | `report_file_present` (`_report_checks`) | `REPORT_FILE_MISSING path=` | unconditional | nothing |
| R02 | only the one disclosed line shape; no duplicate names; no other line kinds | fully | `report_grammar_parses` (`_parse_report`) | `REPORT_GRAMMAR_BAD line=` | report missing → fails with R01's root cause | trailing blank lines (disclosed as ignored) |
| R03 | lists exactly the classes based on `BP_MachineBase`, directly or transitively; never the base itself | fully (two-directional set equality vs pinned constants) | `report_derived_set_exact` (`_report_checks`) | `DERIVED_SET_MISMATCH reported_only=` | report missing/unparsed → fails with that root cause | nothing — a listed herring and an omitted transitive child both fail |
| R04 | each line's `parent` names the class it is DIRECTLY based on | fully (iterates the pinned pairs, so an empty report fails too) | `report_parent_lines_truthful` (`_report_checks`) | `DERIVED_PARENT_WRONG problems=` | report missing/unparsed → fails with that root cause | parents of extra (non-pinned) reported names are not parent-checked — but R03 already fails any extra name |
| R05 | the corpus is exactly as shipped: nothing changed, replaced, or added under `corpus/` | fully at the file-set level (disk truth) | `corpus_set_intact` (`_corpus_file_set_check`) | `CORPUS_MODIFIED_SET files=` | unconditional | an in-place byte edit that keeps the file set and every guarded fact (accepted residual, task.md — cannot move the graded bar) |
| R06 | (shipped-fact guard) the stated base is still a placeable object class | fully | `corpus_base_is_placeable_class` (`_base_class_check`) | `CORPUS_MODIFIED_BASE_CLASS class=` | base class unresolved → fails with `CORPUS_MODIFIED_CLASS_UNRESOLVED name=` | nothing |
| R07 | (shipped-fact guard) the true derivation chain still holds | fully | `corpus_drill_derives_base` + `corpus_heavy_derives_drill` (`_derivation_check`) | `CORPUS_MODIFIED_DRILL_PARENT name=` / `CORPUS_MODIFIED_HEAVY_PARENT name=` | either class unresolved → fails with `CORPUS_MODIFIED_CLASS_UNRESOLVED name=` | nothing — the two checks together pin the whole chain |
| R08 | (shipped-fact guard) the two herrings are still NOT based on the base | fully (conjoined with the positive class-resolution read) | `corpus_baseplate_underived` + `corpus_scout_underived` (`_derivation_check`) | `CORPUS_MODIFIED_BASEPLATE_PARENT name=` / `CORPUS_MODIFIED_SCOUT_PARENT name=` | either class unresolved → fails with `CORPUS_MODIFIED_CLASS_UNRESOLVED name=` | nothing |

Every requirement row above resolves to a live assertion — no requirement is
unenforced prose. What the table cannot show is that a live assertion is
STRONG, which is what the two variants add: `lists-name-stem-herring` is the
live proof that R03 is two-directional (a report that is a strict SUPERSET of
the truth is rejected), and `flat-parent-lines` is the live proof that R04
compares the parent VALUE rather than merely requiring the name to appear.
The first leg also settles R04's recorded get-away-with cell empirically: its
extra name's `parent` is indeed never parent-checked, and the leg FAILs anyway
because R03 dominates. The other recorded cell (R05's guard-invisible byte
edit) stays provably unable to change the graded outcome and is recorded in
the spec's *Accepted residuals* and `../notes.md`.

## How to run (deterministic verifier, no agent, no tokens)

After the authoring-lane run lands the corpus binaries + reference report:

```sh
cb discriminate --task python/kp-derived-class-search --wip
```

Per-leg fallback while iterating (short `--workdir` for MAX_PATH; use the
`py` launcher — `py -3.12` does not resolve on this box, use `py -3.13`):

```sh
UE='<UE-root>'
py tools/verify-single/run_task.py \
    --task tasks/python/kp-derived-class-search/task.md \
    --submission tasks/python/kp-derived-class-search/reference \
    --ue-root "$UE" --workdir C:\cb\wd\kdbs       # expect exit 0
```

L2I graders are read from the LIVE working tree, so iterating on the script
needs no commit — but the corpus binaries DO need committing before a
non-`--wip` grade sees them (the runner materializes the substrate from git
HEAD).

## Status

- Authored from the spec, text-only track. **Never executed against a real
  editor** — no binary exists yet.
- Proven offline: the script emits a constant 10-check verdict; with no
  `unreal` module all 10 checks fail carrying only uncreditable
  `*_PROBE_ERROR` / error tokens, which no row above claims; every expected
  substring above greps as a single source literal; no automation result
  marker appears anywhere in the script.
- Still missing, in order: (1) the corpus binaries + reference report via
  `../aids/author_reference.py` (which grades itself in-process against
  this script and requires 10/10 before harvesting); (2) live confirmation
  of `class_is_child_of` across the BP-of-BP chain (`../notes.md` §4);
  (3) the empty-FAIL discriminate leg; (4) the git-HEAD refgate close.

> **UPDATE 2026-08-12 (authoring-lane run DONE):** every pending-binary
> statement above is now historical - corpus/reference artifacts are
> committed and `cb refgate` refgated PASS from git HEAD (198 s, 2026-08-12); the BP-of-BP factory route proven from stock python. The empty-FAIL leg rides the
> next `cb discriminate` run.

> **UPDATE 2026-08-17 (variant legs authored):** the two variant dirs above
> ship as ANSWER-FILE deltas - one text file each, no editor and no asset
> involved. Their gate order was traced offline against the real grader
> (`_parse_report` plus the pinned set/parent comparisons of `_report_checks`,
> run over this package's three report files): the reference fails nothing,
> `lists-name-stem-herring` fails ONLY `report_derived_set_exact` with
> `reported_only=['BP_MachineBaseplate'] expected_only=[]`, and
> `flat-parent-lines` fails ONLY `report_parent_lines_truthful` with
> `problems=['BP_HeavyDrillRig reported=BP_MachineBase expected=BP_DrillRig']`.
> Both row substrings are ASCII, stop at the `=` before a `%s`, are pairwise
> non-containing, and neither is entailed by `empty`'s
> `REPORT_FILE_MISSING path=` (the empty leg fans that token into all four
> report checks, so it can never satisfy either variant's row). The corpus
> guard is untouched by both legs - neither submits anything under `corpus/`.
> The live `cb discriminate` confirmation rides the next central run.
