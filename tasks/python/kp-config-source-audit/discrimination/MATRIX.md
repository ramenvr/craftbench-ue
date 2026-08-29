# Discrimination matrix — kp-config-source-audit

Self-validation oracle, authored under the **2026-08-11 amended section 7**:
the mandatory artifacts are the automatic reference-PASS / empty-FAIL legs
plus the **requirements table** below — not a variant per anti-gaming note.
The requirements table found no UNENFORCED requirement, so nothing here is
hole-filling. Two hand-authored variants ship anyway (2026-08-17) because the
count rule is its own bar: one leg would show a gate FIRES, not that the
package cannot be gamed. They probe the two requirements this task is ABOUT -
R03 (which candidate is live) and R04 (that candidate's stored value) - and
each dies at a different named check, so neither is entailed by the other or
by `empty`.

> **STATUS: TEXT-ONLY (never executed against a real editor).** The corpus
> baseline and the reference report do not exist yet — both are built by
> `../aids/author_reference.py` in the authoring-lane run, which self-grades
> in-process against the real introspect and requires 12/12 before
> harvesting. Until that run lands and the baseline binaries are committed,
> a live grade fails the guard with `CORPUS_ASSET_MISSING path=` — a
> wrong-reason FAIL that means "baseline not built yet", never agent
> evidence.

## Parser traps honoured (inherited from the audit-report matrix)

- **ONE table with submission rows.** `discriminate.parse_matrix` keys rows
  by first-column label; the submission table below is the only one whose
  first column contains submission labels. The requirements table uses
  `R##` keys that collide with no submission dir.
- **Every expected-substring cell is backtick-wrapped and contains a space
  and `=`** (the `_extract_substrings` substantiveness rule), and each is a
  verbatim substring of the raw `detail` printed inside the
  `CRAFTBENCH-INTROSPECT-JSON` block.
- **The reference row's substring cell is `—`** (maps to the empty tuple).
- **ASCII rule**: every substring is ASCII-only; the whole introspect
  script is ASCII by construction.
- **Error tokens are disjoint from failure tokens.** `*_PROBE_ERROR` /
  `*_READ_ERROR` / `*_WALK_ERROR` / `*_ABORTED` / `CHECK_NOT_EVALUATED`
  appear in no row here, so a broken UE API name can never be credited as
  a named failure (proven offline: with no `unreal` module all 12 checks
  fail as `CORPUS_SET_PROBE_ERROR` / `CORPUS_PROBE_ERROR` /
  `WIRING_PROBE_ERROR` / `CONFIG_REPORT_PROBE_ERROR`, which no row claims).

## Layout

- `../reference/Content/Tasks/kp-config-source-audit/reports/config.txt` — the
  one correct solution (a two-line text report), **pending the
  authoring-lane run** of `../aids/author_reference.py`. Note the reference
  overlay is TEXT ONLY: the corpus/wiring binaries are substrate BASELINE
  (committed under `UE-projects/ThirdPerson/Content/Tasks/<id>/`), never
  part of any submission overlay.
- empty leg — run implicitly by `cb discriminate` (throwaway empty dir;
  nothing to author).
- `name-bait-current/` - the name-bait answer (anti-gaming note #1): the
  plausible-sounding decoy `Flash_Current` reported with ITS OWN stored
  brightness `950`, i.e. an internally consistent report about the wrong
  asset. Text-only overlay, exactly one file, same relative path as the
  reference.
- `right-asset-sibling-value/` - the half-true answer (anti-gaming note #4):
  the source line is the CORRECT live asset `Flash_Archive_2024`, the value
  line carries a sibling's brightness `1450` (Flash_Primary's) - the trace was
  done, the value was read off the wrong asset. Text-only overlay, one file.
- Both variants leave the committed corpus and wiring untouched, so all 7
  guard checks PASS on both legs and each leg's FIRST failing check is the one
  its row names (`CHECK_IDS` puts the 7 guard checks ahead of the 5 report
  checks, and within the report group presence -> grammar -> source -> value
  -> wiring).

Unlike the sibling audit-report task, this task's empty leg is NOT 0-of-N:
the 7 guard checks pass on an intact baseline (that is their whole point —
they discriminate evidence-tampering, not effort), so the empty submission
scores **7/12** and FAILs overall via the report group's named root cause.

## Matrix

**This is the only table in this file whose first column is a submission.**

| Submission | Overall | Fails at (check id) | Expected substring | Also fails (recorded, not matched) | Anti-gaming note |
|---|---|---|---|---|---|
| `../reference` | PASS | — | — | none — all 12 checks green (12/12) | — |
| empty | FAIL | `report_file_present` | `CONFIG_REPORT_MISSING path=` | the four remaining report checks fan out the same root cause; the 7 guard checks PASS (baseline intact) — `7/12` | #3 / FR-017 non-vacuity |
| `name-bait-current/` | FAIL | `report_source_is_live_asset` | `CONFIG_SOURCE_WRONG reported=` | `report_value_is_live_value` also fails (the decoy's own 950 is not the live 725) and `report_agrees_with_wiring` records `CONFIG_WIRING_DISAGREES reported_asset=`; the 7 guard checks PASS - `9/12` | #1 (guess by name / plausibility) |
| `right-asset-sibling-value/` | FAIL | `report_value_is_live_value` | `CONFIG_VALUE_WRONG reported=` | `report_agrees_with_wiring` also fails (same value disagreement, recorded not matched); `report_source_is_live_asset` PASSES - the source line is right - and the 7 guard checks PASS - `10/12` | #4 (right path, made-up number) |

## Requirements table (the mandatory §7a artifact)

One row per requirement in the agent-visible prompt. Assertion pointers
name the check id (all in
`tools/verify-single/introspect/kp_config_source_audit.py`; find a check id in
the `CHECK_IDS` tuple and its emitting function). "Skipped when" names the
ONLY condition under which the gate does not evaluate its own predicate —
in every such case the check still FAILS with the prerequisite's root-cause
token (fanout), never a silent pass.

| Key | Prompt requirement | Asserted | Check id (assertion) | Named failure substring | Skipped when | What a submission could get away with |
|---|---|---|---|---|---|---|
| R01 | a report exists at `reports/config.txt` | fully | `report_file_present` (`_report_checks`) | `CONFIG_REPORT_MISSING path=` | unconditional | nothing |
| R02 | exactly the two disclosed line shapes, one of each, nothing else | fully | `report_grammar_parses` (`_parse_report`) | `CONFIG_GRAMMAR_BAD line=` | report missing/unreadable → fails with R01's root cause (or the uncreditable read-error token) | nothing — duplicates, extras, and missing lines all fail |
| R03 | the source line names the candidate that is really live | fully | `report_source_is_live_asset` (`_report_checks`) | `CONFIG_SOURCE_WRONG reported=` | report unparsed → fails with R02's detail | a 1-in-4 blind guess (accepted residual, task.md) |
| R04 | the value line states that candidate's stored brightness | fully | `report_value_is_live_value` (`_report_checks`) | `CONFIG_VALUE_WRONG reported=` | report unparsed → fails with R02's detail | 1e-3 tolerance on the float compare (pre-calibration) |
| R05 | the report tells the truth about the wiring as it stands (both fields, traced fresh) | fully | `report_agrees_with_wiring` (`_report_checks`) | `CONFIG_WIRING_DISAGREES reported_asset=` | wiring unreadable → fails with the wiring root cause; wired target unreadable → fails with that asset's `CORPUS_*` detail | nothing — an agent-rewired slot makes this check compare against the REWIRE, and R06/R07 + the pins catch the rewire itself |
| R06 | "do not modify … the candidates" and "do not add anything to `corpus/`" | fully | `corpus_set_exact` + `corpus_primary_intact` + `corpus_current_intact` + `corpus_archive_intact` + `corpus_testflash_intact` (`_corpus_checks` / `_read_glow`) | `CORPUS_SET_CHANGED found=` / `CORPUS_ASSET_MISSING path=` / `CORPUS_MODIFIED_PARTS asset=` / `CORPUS_MODIFIED_PART_TYPE asset=` / `CORPUS_MODIFIED_VALUE asset=` | unconditional | a byte rewrite preserving every pinned fact (accepted residual; hash upgrade is a calibration TODO) |
| R07 | "do not modify … the rig" | fully | `wiring_rig_present` + `wiring_slot_intact` (`_wiring_checks`) | `WIRING_RIG_MISSING path=` / `CORPUS_MODIFIED_WIRING names=` / `CORPUS_MODIFIED_WIRING_CLASS slot_class=` | unconditional | nothing — slot class is an exact object-path compare against the pin |

Every requirement row above resolves to a live assertion — no requirement
is unenforced prose, so no variant is owed to fill a HOLE under the amended
§7. The two variants that do ship are anti-gaming probes of the two rows a
wrong-but-plausible answer actually lands on: `name-bait-current/` exercises
R03 (`report_source_is_live_asset`) and `right-asset-sibling-value/`
exercises R04 (`report_value_is_live_value`). R03's recorded residual (a
1-in-4 blind guess) is exactly what `name-bait-current/` makes concrete: the
guess is punished on BOTH fields, not just the one it got wrong.
The residual rows (R03's blind guess, R06's fact-preserving rewrite) are
recorded in the spec's *Accepted residuals* and in `../notes.md` with their
calibration TODOs.

## How to run (deterministic verifier, no agent, no tokens)

After the authoring-lane run lands the baseline binaries + reference
report (and they are committed):

```sh
cb discriminate --task python/kp-config-source-audit --wip
```

Per-leg fallback while iterating (short `--workdir` for MAX_PATH; use the
`py` launcher — `py -3.12` does not resolve on this box, use `py -3.13`):

```sh
UE='<UE-root>'
py tools/verify-single/run_task.py \
    --task tasks/python/kp-config-source-audit/task.md \
    --submission tasks/python/kp-config-source-audit/reference \
    --ue-root "$UE" --workdir C:\cb\wd\kpgca       # expect exit 0
```

L2I graders are read from the LIVE working tree, so iterating on the
script needs no commit — but the substrate baseline binaries DO need
committing before a non-`--wip` grade sees them (the runner materializes
the substrate from git HEAD), and the guard fails with
`CORPUS_ASSET_MISSING path=` until they land.

## Status

- Authored 2026-08-12 from the spec, text-only track. **Never executed
  against a real editor** — no binary exists yet.
- **Two variant legs authored 2026-08-17** (`name-bait-current/`,
  `right-asset-sibling-value/`), text-only, never executed against a real
  editor. Offline evidence, no UE and no tokens: the introspect grammar
  parser accepts both variant texts (so neither dies at
  `report_grammar_parses`, which would be a wrong-reason FAIL), the pinned
  compares put `name-bait-current/`'s first failure at
  `report_source_is_live_asset` and `right-asset-sibling-value/`'s at
  `report_value_is_live_value`, both recorded substrings fold out of
  `kp_config_source_audit.py` as single literal runs (matrix_oracle
  `introspect` tier, `%`-placeholders never crossed), both are pure ASCII,
  neither entails the other, and neither is entailed by `empty`. Both files
  are CRLF + ASCII, byte-matching the reference report except for the
  authored delta. The live confirmation rides the next `cb discriminate` run.
- Proven offline (py -3.13, fake/no `unreal` module): the script emits a
  constant 12-check verdict; the no-module leg carries only uncreditable
  `*_PROBE_ERROR` tokens; the baseline-absent leg carries the graded
  `CORPUS_SET_CHANGED found=` / `CORPUS_ASSET_MISSING path=` /
  `WIRING_RIG_MISSING path=` / `CONFIG_REPORT_MISSING path=` root causes;
  the grammar parser accepts the reference shape and rejects extras,
  duplicates and missing lines; every expected substring above greps as a
  single source literal; neither automation result marker appears anywhere
  in the script.
- Still missing, in order: (1) the baseline + reference via
  `../aids/author_reference.py` (12/12 self-grade required before
  harvest); (2) commit of the substrate baseline binaries + reference
  report; (3) live confirmation of the `child_actor_class` template
  read/write spellings and the `list_assets` return shape (notes.md §4);
  (4) the git-HEAD certification run (`cb refgate python/kp-config-source-audit`).

> **UPDATE 2026-08-12 (authoring-lane run DONE):** every pending-binary
> statement above is now historical - corpus/reference artifacts are
> committed and `cb refgate` refgated PASS from git HEAD (189 s, 2026-08-12). The empty-FAIL leg rides the
> next `cb discriminate` run.
