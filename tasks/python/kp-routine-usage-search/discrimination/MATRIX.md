# Discrimination matrix — kp-routine-usage-search

Self-validation oracle. Under the **2026-08-11 amended section 7** the
mandatory artifacts are the automatic reference-PASS / empty-FAIL legs plus
the **requirements table** below - not a variant per anti-gaming note. Two
hand-authored variant legs ship anyway, added 2026-08-17 to meet the
the corpus ledger floor (`_MIN_VARIANT_LEGS` = 2 in
the corpus-ledger tool (since removed)): one leg shows only that a gate FIRES,
so a package needs a second leg at a DIFFERENT requirement before it can
claim its gates cannot be gamed. The two legs therefore die at two
different checks - `report_verdicts_truthful` (R05) and
`report_covers_corpus_exactly` (R04) - and neither is entailed by `empty`.
Both are ANSWER-FILE deltas: the deliverable is a single text file, so a
variant needs no editor, no asset and no build.

> **STATUS: TEXT-ONLY TRACK — not yet runnable.** The corpus binaries and
> the reference report do not exist yet (this track cannot run UE); the
> authoring-lane run of `../aids/author_reference.py` builds both, prints
> the `KPUSAGE-HASH` digests, and the same change-set that commits the
> binaries must pin those digests into
> `tools/verify-single/introspect/kp_routine_usage_search.py::CORPUS_SHA256`
> (replacing the fail-closed sentinel). Until then `corpus_bytes_unmodified`
> fails every leg with the uncreditable `USAGE_CORPUS_HASH_UNPINNED` token —
> by design, so an unpinned task can never certify.

## Parser traps honoured (inherited from the kp-audit matrix)

- **ONE table with submission rows.** `discriminate.parse_matrix` keys rows
  by first-column label; the submission table below is the only one whose
  first column contains submission labels, and the requirements table uses
  `R##` keys that collide with no submission dir.
- **Every expected-substring cell is backtick-wrapped and contains a space
  and `=`** (the `_extract_substrings` substantiveness rule), and each is a
  verbatim substring of the raw `detail` printed inside the
  `CRAFTBENCH-INTROSPECT-JSON` block, living as ONE contiguous string
  literal in the introspect source (proven offline 2026-08-11: all 12
  graded token heads grep as single literals).
- **The reference row's substring cell is `—`** (maps to the empty tuple).
- **ASCII rule**: every substring is ASCII-only; the whole introspect script
  is ASCII by construction.
- **Error tokens are disjoint from failure tokens.** `*_PROBE_ERROR` /
  `*_READ_ERROR` / `USAGE_CORPUS_HASH_UNPINNED` /
  `USAGE_CORPUS_HASH_TARGET_MISSING` / `USAGE_INTROSPECTION_ABORTED` /
  `CHECK_NOT_EVALUATED` appear in no row here, so a broken UE API name — or
  the not-yet-pinned hash sentinel — can never be credited as a named
  failure (observed directly: with no `unreal` module all four guard checks
  fail as `*_PROBE_ERROR`, which no row claims).

## Layout

- `../reference/Content/Tasks/kp-routine-usage-search/reports/usage.txt` —
  the one correct deliverable (the report ONLY; the corpus and the library
  are substrate baseline, never part of the overlay), **pending the
  authoring-lane run** of `../aids/author_reference.py`.
- empty leg — run implicitly by `cb discriminate` (throwaway empty dir;
  nothing to author). The corpus baseline is intact on this leg, so the
  four guard checks legitimately pass and the leg fails 4/9 via the named
  report-missing root cause (proven offline with the report path
  monkeypatched to a missing file: all five report checks carry
  `USAGE_REPORT_MISSING path=`).
- `name-grep-verdicts/` - the report a per-file NAME GREP produces: BP_East
  flipped to `no` (it inherits the call, so the routine's name never
  appears in its own file) and BP_West flipped to `yes` (it carries the
  name as a marker value only). ONE coherent delta - one wrong search
  strategy - even though it moves two rows. Grammar, function line and
  coverage all pass, so the leg dies at the verdict-truth gate (8/9).
- `omits-inherited-entry/` - the reference report with the BP_East line
  DELETED: the hedge an agent makes when it cannot resolve the inherited
  case. Dies at the two-directional coverage gate (7/9), which fires
  BEFORE the verdict gate that also fails (`USAGE_VERDICT_MISSING
  entry=BP_East missing_count=1`, recorded, never matched).

## Matrix

**This is the only table in this file whose first column is a submission.**

| Submission | Overall | Fails at (check id) | Expected substring | Also fails (recorded, not matched) | Anti-gaming note |
|---|---|---|---|---|---|
| `../reference` | PASS | — | — | none — all 9 checks green (9/9) | — |
| empty | FAIL | `report_file_present` | `USAGE_REPORT_MISSING path=` | the four remaining report checks fan out the same root cause — `4/9` (guard passes: baseline intact) | #1 / FR-017 non-vacuity |
| `name-grep-verdicts/` | FAIL | `report_verdicts_truthful` | `USAGE_VERDICT_WRONG entry=` | nothing else - the guard is 4/4 and the four earlier report checks all pass, `8/9`; the uncredited tail of the same detail reads `entry=BP_East reported=no expected=yes wrong_count=2` | #2 (per-file name grep) |
| `omits-inherited-entry/` | FAIL | `report_covers_corpus_exactly` | `USAGE_COVERAGE_MISMATCH reported_only=` | `report_verdicts_truthful` fans its own root cause `USAGE_VERDICT_MISSING entry=BP_East missing_count=1` (recorded, not matched); guard 4/4, `7/9` | #5 (coverage gaming) |

## Requirements table (the mandatory §7a artifact)

One row per requirement in the agent-visible prompt. Assertion pointers name
the check id (all in
`tools/verify-single/introspect/kp_routine_usage_search.py`; find a check
id in `CHECK_IDS` and its emitting function). "Skipped when" names the ONLY
condition under which the gate does not evaluate its own predicate — in
every such case the check still FAILS with the prerequisite's root-cause
token (fanout), never a silent pass.

| Key | Prompt requirement | Asserted | Check id (assertion) | Named failure substring | Skipped when | What a submission could get away with |
|---|---|---|---|---|---|---|
| R01 | `usage.txt` exists at the pre-declared path | fully | `report_file_present` (`_report_checks`) | `USAGE_REPORT_MISSING path=` | unconditional | nothing |
| R02 | only the two disclosed line shapes; exactly one `function` line; no duplicate entries | fully | `report_grammar_parses` (`_parse_report`) | `USAGE_GRAMMAR_BAD line=` | report missing/unreadable → fails with that root cause | nothing |
| R03 | the `function` line names exactly `ComputeChecksum` | fully | `report_function_line_correct` (`_report_checks`) | `USAGE_FUNCTION_LINE_WRONG reported=` | report unparsed → fails with parse root cause | nothing — string equality against the pinned constant |
| R04 | one `entry` line per corpus entry, exact names, no others | fully (two-directional set equality) | `report_covers_corpus_exactly` (`_report_checks`) | `USAGE_COVERAGE_MISMATCH reported_only=` | report unparsed → fails with parse root cause | nothing — fabrication and omission both fail; an omission ALSO fails R05 via `USAGE_VERDICT_MISSING entry=` |
| R05 | every verdict agrees with the truth of the committed corpus | fully (iterates the verifier's pinned list, never the report's) | `report_verdicts_truthful` (`_report_checks`) | `USAGE_VERDICT_WRONG entry=` | report unparsed → fails with parse root cause | nothing — the pinned truth is two-yes/two-no, so all-yes, all-no, per-file name-grep (wrong on BP_East + BP_West) and library-dependency scans (wrong on BP_South) each fail at least one entry |
| R06 | the four corpus entries are not modified, moved, or deleted | fully | `corpus_assets_present` + `corpus_dir_exact` + `corpus_bytes_unmodified` (`_guard_checks`) | `USAGE_CORPUS_MODIFIED file=` (edit) / `USAGE_CORPUS_ASSET_MISSING path=` (delete, registry) / `USAGE_CORPUS_FILE_MISSING file=` (delete, disk) / `USAGE_CORPUS_EXTRA_FILES extras=` (addition) | unconditional (three independent probes; hash leg uncreditable-fails until digests are pinned) | a byte-identical resave (nothing actually changed — accepted); truth constants never move regardless |
| R07 | the utility source is not modified, moved, or deleted | fully | `library_source_unmodified` (`_guard_library_unmodified`) | `USAGE_LIBRARY_MODIFIED file=` / `USAGE_LIBRARY_SOURCE_MISSING file=` | unconditional | whitespace-only edits still fail (CR-normalized hash, not semantic diff) — strictness disclosed in the prompt |

Every requirement row above resolves to a live assertion - no requirement is
unenforced prose, so neither shipped leg is owed to a HOLE. They exist to
EXERCISE two of these rows on real bytes: the table proves an assertion
exists, a leg proves that assertion REJECTS plausible-wrong work. R05 is
exercised by `name-grep-verdicts/`, R04 by `omits-inherited-entry/`, R01
by the `empty` leg.

R02 (grammar) and R03 (the function line) ship no leg: they are cheap to
author, but they probe the report's SHAPE, which the prompt discloses
verbatim - a leg there would measure transcription rather than the
usage-search capability the task is for. R06/R07 ship no leg on purpose,
and this is the honest reason: a corpus- or library-edit variant has to
commit a MUTATED binary or source file, and which guard check fires first
then depends on how the mutation lands (a corrupt `.uasset` can fail
`corpus_assets_present` before the hash check ever runs), so such a row
could not name its gate honestly without an executed run to confirm the
order. The residual rows (R06 byte-identical resave, R07 hash strictness)
are recorded in the spec's *Accepted residuals* and in `../notes.md`.

## How to run (deterministic verifier, no agent, no tokens)

After the authoring-lane run lands the corpus binaries + reference report
and the digests are pinned:

```sh
cb discriminate --task python/kp-routine-usage-search --wip
```

Per-leg fallback while iterating (short `--workdir` for MAX_PATH; use the
`py` launcher — `py -3.12` does not resolve on this box, use `py -3.13`):

```sh
UE='<UE-root>'
py tools/verify-single/run_task.py \
    --task tasks/python/kp-routine-usage-search/task.md \
    --submission tasks/python/kp-routine-usage-search/reference \
    --ue-root "$UE" --workdir C:\cb\wd\kpusage       # expect exit 0
```

L2I graders are read from the LIVE working tree, so iterating on the script
needs no commit — but the corpus binaries DO need committing before a
non-`--wip` grade sees them (the runner materializes the substrate from git
HEAD), and the pinned digests must be of the committed bytes.

## Status

- Authored 2026-08-11 from the spec, text-only track. **Never executed
  against a real editor** — no corpus binary exists yet.
- Proven offline (`py -3.13`, fake-module + monkeypatched-path legs): the
  script emits a constant 9-check verdict; the empty leg carries
  `USAGE_REPORT_MISSING path=` on all five report checks; a flipped verdict
  fails `report_verdicts_truthful` with `USAGE_VERDICT_WRONG entry=BP_East`;
  a one-entry report fails coverage AND verdicts; all 12 graded substrings
  above grep as single source literals; the no-unreal leg carries only
  uncreditable `*_PROBE_ERROR` tokens.
- Still missing, in order: (1) the corpus binaries + the two graph-lane
  call nodes (BP_North -> ComputeChecksum, BP_South -> FormatLabel) via
  `../aids/author_reference.py` + the MCP graph lane; (2) digest pinning
  from the `KPUSAGE-HASH` lines; (3) the reference report harvest (the aid
  self-grades 9/9 before harvesting); (4) the git-HEAD certification run.
- **Two variant legs authored 2026-08-17** (`name-grep-verdicts/`,
  `omits-inherited-entry/`) - **NOT YET EXECUTED** against a real editor;
  they ride the next `cb discriminate` run. Proven offline (`py -3.12`, the
  real introspect module with `_report_path` monkeypatched at each leg's
  committed answer file): the reference answer still grades 5/5 report
  checks; `name-grep-verdicts/` fails ONLY `report_verdicts_truthful`,
  detail `USAGE_VERDICT_WRONG entry=BP_East reported=no expected=yes
  wrong_count=2`; `omits-inherited-entry/` fails
  `report_covers_corpus_exactly` FIRST, detail `USAGE_COVERAGE_MISMATCH
  reported_only=[] missing=['BP_East']`. Checked in BOTH directions: no
  leg's output contains another row's expected substring (`empty`
  included), so each leg can only be credited by its own gate. Both
  substrings fold out of the introspect source as single literals
  (`matrix_oracle`, introspect tier).
- Gate order confirmed for both legs: the guard group (checks 1-4) passes
  on every ANSWER-FILE variant - the overlay adds only
  `reports/usage.txt`, leaving the corpus and the library source at
  baseline - so the first failing check is always inside the report group,
  and within that group emission order is presence -> grammar -> function
  line -> coverage -> verdicts.
- Both variant files are CRLF and ASCII and byte-identical to
  `../reference/Content/Tasks/kp-routine-usage-search/reports/usage.txt`
  except the one claimed delta (two flipped verdicts for the grep leg, one
  deleted entry line for the coverage leg).

> **UPDATE 2026-08-12 (authoring-lane run DONE):** every pending-binary
> statement above is now historical - corpus/reference artifacts are
> committed and `cb refgate` refgated PASS from git HEAD (200 s, 2026-08-12); corpus calls wired via the MCP graph lane, self-grade 9/9, hash pins landed with the binaries. The empty-FAIL leg rides the
> next `cb discriminate` run.
