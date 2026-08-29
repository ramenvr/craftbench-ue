# Discrimination matrix — kp-engine-source-search

Self-validation oracle for the task, authored under the **2026-08-11 amended
section 7**: the mandatory artifacts are the automatic reference-PASS /
empty-FAIL legs plus the **requirements table** below — not a variant per
anti-gaming note. The requirements table below still finds no unenforced
requirement, so NO variant is owed on that ground (section 7a law).

**Two variants nevertheless ship as of 2026-08-17**, owed on a different
ground: the corpus evidence bar
(the corpus-ledger tool's test (since removed)) - "one leg shows the gate
FIRES, not that it cannot be gamed", so a settled package needs at least two
negative legs probing DIFFERENT requirements. `empty` proves only that the
file-presence gate fires; it can prove nothing about the grammar gate or the
per-answer exact compare, because it never reaches either. The two legs below
are each a one-delta copy of the reference and each dies at a check `empty`
never evaluates. Both are ANSWER-FILE-only deltas: no editor, no asset, no
C++, no map.

> **STATUS: text-track authored 2026-08-11; never run against a real
> editor.** The introspect's behavior is proven OFFLINE (fake `unreal`
> module, real emission path) across nine legs: no-module, empty, reference,
> wrong-value, shotgun-duplicate, unknown-id, missing-id, multi-token
> smuggling, wrong-engine-pin — see `../notes.md` §5. Remaining before
> certification: the authoring-lane run of `../aids/author_reference.py`
> (harvests `reference/`), then `cb discriminate --wip` and the git-HEAD
> refgate.

## Parser traps honoured (inherited from the audit-task matrix)

- **ONE table with submission rows.** `discriminate.parse_matrix` keys rows
  by first-column label; the submission table below is the only one whose
  first column contains submission labels — the requirements table uses
  `R##` keys that collide with no submission dir.
- **Every expected-substring cell is backtick-wrapped and contains a space
  and `=`** (the `_extract_substrings` substantiveness rule), and each is a
  verbatim substring of the raw `detail` printed inside the
  `CRAFTBENCH-INTROSPECT-JSON` block.
- **The reference row's substring cell is `—`** (maps to the empty tuple).
- **ASCII rule**: every substring is ASCII-only; the whole introspect script
  is ASCII by construction.
- **Error tokens are disjoint from failure tokens.** `*_PROBE_ERROR` /
  `*_READ_ERROR` / `*_ABORTED` / `CHECK_NOT_EVALUATED` appear in no row
  here, so a broken UE API name can never be credited as a named failure
  (observed directly in the offline no-module leg: all 7 checks fail as
  `ENGINE_PIN_PROBE_ERROR` / `ANSWERS_PROBE_ERROR`, which no row claims).
- **Every backticked expected substring below greps as ONE source literal**
  in `tools/verify-single/introspect/kp_engine_source_search.py` (verified
  2026-08-11).

## Layout

- `../reference/Content/Tasks/kp-engine-source-search/reports/answers.txt` —
  the one correct solution (a 4-line text file), **pending the
  authoring-lane run** of `../aids/author_reference.py` (the aid re-derives
  every pinned constant from the live engine source, writes the file from
  the grader's own constants, self-grades to 7/7 in-process, then harvests).
  Per the no-fabrication rule the file is not committed by the text-only
  track even though it is plain text — the aid run is what certifies it
  against the live engine pin.
- empty leg — run implicitly by `cb discriminate` (throwaway empty dir;
  nothing to author).
- `delegate-cpp-not-header/Content/Tasks/<id>/reports/answers.txt` - the
  reference file with ONE delta: `delegate-header` answers
  `Engine/Source/Runtime/Core/Private/Misc/CoreDelegates.cpp`, the source file
  that DEFINES the delegate member, instead of the public header that
  DECLARES it. The other three answers are the reference's. **6/7.**
- `cvar-source-expression/Content/Tasks/<id>/reports/answers.txt` - the
  reference file with ONE delta: `cvar-default` answers `1024 * 64`, the
  arithmetic expression the engine source literally writes, instead of its
  evaluated result. The other three answers are the reference's. **2/7.**

This task ships **no baseline asset**, so the empty leg is a genuinely empty
deliverable. It scores **1/7, overall FAIL**: the six report checks fan out
`ANSWERS_FILE_MISSING path=`; the seventh (`engine_pin_matches`) is a
harness invariant, not an agent requirement, and passes on any healthy 5.8
rig (proven offline).

## Matrix

**This is the only table in this file whose first column is a submission.**

| Submission | Overall | Fails at (check id) | Expected substring | Also fails (recorded, not matched) | Anti-gaming note |
|---|---|---|---|---|---|
| `../reference` | PASS | — | — | none — all 7 checks green (7/7) | — |
| empty | FAIL | `answers_file_present` | `ANSWERS_FILE_MISSING path=` | the 5 remaining report checks fan out the same root cause; `engine_pin_matches` passes — `1/7` | #4 / FR-017 non-vacuity |
| `delegate-cpp-not-header/` | FAIL | `answer_delegate_header_exact` | `ANSWER_WRONG id=delegate-header reported=` | nothing else - the other three answers, the presence check, the grammar check and the pin all PASS: **6/7** | #1 answering without reading precisely |
| `cvar-source-expression/` | FAIL | `answers_grammar_parses` | `ANSWERS_GRAMMAR_BAD line=` | the four answer checks fan out the same parse-fail detail (reason `unrecognized_line`); presence + pin PASS: **2/7** | #3 format smuggling |

### Why these two legs, and why each substring stops where it does

- **`delegate-cpp-not-header/` is the sharpest wrong ANSWER this task
  admits.** A grep for `OnEnginePreExit` hits the declaration in the public
  header AND the definition in `Private/Misc/CoreDelegates.cpp`; the prompt's
  whole discriminating clause ("the declaration of the member itself, not
  files that merely mention or subscribe to it") is what tells them apart. So
  this leg is a submission that did search, in the right module, and read
  imprecisely - not a lazy one. It is the only leg that proves the per-answer
  EXACT compare rejects a near-miss: it clears the presence gate AND the
  grammar gate, so it can die nowhere else. **6/7** is also the
  honest-denominator test - a grader that scored "a well-formed answers file"
  would call this a pass.
- **`cvar-source-expression/` probes a DIFFERENT gate on a DIFFERENT
  requirement** - the single-token grammar, not the answer key. The engine
  source writes the default as `1024 * 64` (notes.md §3), so pasting the
  initializer verbatim is the realistic transcription failure; the value then
  contains spaces, which the full-line-anchored `RE_ANSWER` rejects. The gate
  that fires FIRST is `answers_grammar_parses`, reached because the file IS
  present; the four answer checks then fan out the identical parse-fail
  detail, so no `ANSWER_WRONG` / `ANSWER_MISSING` token appears anywhere in
  this leg's log.
- **Gate order is traced, not assumed** (the 2026-08-16 dead-sentinel
  lesson). `_report_checks` runs presence -> read -> grammar -> the four
  per-answer compares, and `_parse_answers` returns on the FIRST offending
  line. For `delegate-cpp-not-header/` every earlier gate genuinely PASSES,
  so `answer_delegate_header_exact` is the first failure; for
  `cvar-source-expression/` the only earlier gate (presence) PASSES, so
  `answers_grammar_parses` is. Neither leg can be credited by the other's
  substring, in EITHER direction, at runtime: the grammar leg emits no
  `ANSWER_WRONG` at all, and the wrong-answer leg emits
  `ANSWERS_GRAMMAR_OK answers=` instead.
- **Both substrings stop at the `=` before an interpolated value**
  (`ANSWER_WRONG id=%s reported=%s ...`, `ANSWERS_GRAMMAR_BAD line=%r ...`),
  per the `granted=0` vs `granted=` rule. `ANSWER_WRONG id=delegate-header
  reported=` is one folded literal run of the grader's own source - the qid is
  a verifier-owned constant, so it sits INSIDE the literal rather than past a
  placeholder. `reason=unrecognized_line` is deliberately NOT the anchor: it
  sits past the `%r`, which `matrix_oracle`'s printf cutter does not treat as
  a placeholder, so naming it would statically read as unbuildable even
  though the log carries it.
- **Pairwise + empty-floor:** the three negative substrings
  (`ANSWERS_FILE_MISSING path=`, `ANSWER_WRONG id=delegate-header reported=`,
  `ANSWERS_GRAMMAR_BAD line=`) are pairwise non-containing, so neither variant
  is entailed by `empty` and the matrix cannot collapse onto the FR-017 smoke
  leg.

## Requirements table (the mandatory §7a artifact)

One row per requirement in the agent-visible prompt. Assertion pointers name
the check id (all in
`tools/verify-single/introspect/kp_engine_source_search.py`; find a check id
in the `CHECK_IDS` tuple and its emitting function). "Skipped when" names
the ONLY condition under which the gate does not evaluate its own predicate
— in every such case the check still FAILS with the prerequisite's
root-cause token (fanout), never a silent pass.

| Key | Prompt requirement | Asserted | Check id (assertion) | Named failure substring | Skipped when | What a submission could get away with |
|---|---|---|---|---|---|---|
| R01 | `reports/answers.txt` exists at the pre-declared path | fully | `answers_file_present` (`_report_checks`) | `ANSWERS_FILE_MISSING path=` | unconditional | nothing |
| R02 | only the one disclosed line shape; exactly one line per question id, no other ids, no duplicates | fully | `answers_grammar_parses` (`_parse_answers`); missing ids fail per-answer (R03-R06) | `ANSWERS_GRAMMAR_BAD line=` | file missing/unreadable → fails with R01's root cause | nothing — duplicate, unknown, multi-token, and zero-line files all fail here; a missing id falls through to `ANSWER_MISSING id=`. Live leg: `cvar-source-expression/` (multi-token) |
| R03 | `delegate-header` names the declaring header, engine-relative, forward slashes | fully | `answer_delegate_header_exact` (`_report_checks`) | `ANSWER_WRONG id=` / `ANSWER_MISSING id=` | grammar failed → fails with R02's detail | answering from memory instead of the source (accepted residual, notes.md — outcome-graded). Live leg: `delegate-cpp-not-header/`, the definition site instead of the declaration site |
| R04 | `cvar-default` is the evaluated compiled-in default, base-10 | fully | `answer_cvar_default_exact` (`_report_checks`) | `ANSWER_WRONG id=` / `ANSWER_MISSING id=` | grammar failed → fails with R02's detail | same residual as R03; the source spells it `1024 * 64`, so recall must also evaluate |
| R05 | `class-module` names the declaring module as the build system spells it | fully | `answer_class_module_exact` (`_report_checks`) | `ANSWER_WRONG id=` / `ANSWER_MISSING id=` | grammar failed → fails with R02's detail | same residual as R03 |
| R06 | `name-capacity` is the constant's integer value | fully | `answer_name_capacity_exact` (`_report_checks`) | `ANSWER_WRONG id=` / `ANSWER_MISSING id=` | grammar failed → fails with R02's detail | same residual as R03 |
| R07 | (harness invariant, not in the prompt) the grading engine is the pinned 5.8 corpus | fully | `engine_pin_matches` (`_pin_check`) | `ENGINE_PIN_MISMATCH version=` | unconditional (an unreadable version is an uncreditable `ENGINE_PIN_PROBE_ERROR`) | nothing — not agent-reachable; documents the corpus-unmodified guard |

Every requirement row above resolves to a live assertion — no requirement is
unenforced prose, so no targeted variant is owed under the amended §7. The
one recorded residual (memory answering, R03-R06) is a basket-law property
(outcome-graded), not a verifier hole: no variant could probe it because
there is no gate whose absence it exploits — the answers are either right or
wrong.

## How to run (deterministic verifier, no agent, no tokens)

After the authoring-lane run lands the reference file:

```sh
cb discriminate --task python/kp-engine-source-search --wip
```

Per-leg fallback while iterating (short `--workdir` for MAX_PATH; use the
`py` launcher — `py -3.12` does not resolve on this box, use `py -3.13`):

```sh
UE='<UE-root>'
py tools/verify-single/run_task.py \
    --task tasks/python/kp-engine-source-search/task.md \
    --submission tasks/python/kp-engine-source-search/reference \
    --ue-root "$UE" --workdir C:\cb\wd\kpess       # expect exit 0
```

L2I graders are read from the LIVE working tree, so iterating on the script
needs no commit — but the reference file DOES need committing before a
non-`--wip` grade sees it (the runner materializes the substrate from git
HEAD).

## Status

- Authored 2026-08-11 from the spec, text-only track. **Never executed
  against a real editor.**
- Proven offline (nine legs, fake `unreal`, real emission path — runner
  script recorded in `../notes.md` §5): constant 7-check verdict on every
  leg; reference 7/7; empty 1/7 via `ANSWERS_FILE_MISSING path=`; shotgun
  and smuggling fail at grammar; wrong value fails `ANSWER_WRONG id=`;
  wrong engine fails `ENGINE_PIN_MISMATCH version=`; the no-module leg
  carries only uncreditable error tokens.
- Still missing, in order: (1) the reference file via
  `../aids/author_reference.py` (which re-derives the answer key from the
  live engine and requires 7/7 before harvesting); (2) live confirmation of
  `SystemLibrary.get_engine_version` headless; (3) the git-HEAD
  certification run.

> **UPDATE 2026-08-17 (two variant legs authored):**
> `delegate-cpp-not-header/` and `cvar-source-expression/` are committed,
> text-only, and each byte-identical to the reference except its one delta
> (CRLF on disk, LF in the index, exactly like the reference). Their verdicts
> were reproduced OFFLINE against the real introspect through a fake `unreal`
> module (the §5 harness): reference 7/7, empty 1/7,
> `delegate-cpp-not-header/` **6/7** with `ANSWER_WRONG id=delegate-header
> reported=Engine/Source/Runtime/Core/Private/Misc/CoreDelegates.cpp
> expected=Engine/Source/Runtime/Core/Public/Misc/CoreDelegates.h`, and
> `cvar-source-expression/` **2/7** with `ANSWERS_GRAMMAR_BAD line='answer
> id=cvar-default value=1024 * 64' reason=unrecognized_line`. NEITHER LEG HAS
> RUN AGAINST A REAL EDITOR - the `cb discriminate` run that credits them
> (and the refgate that re-certifies the unchanged reference) is the
> operator's; until it lands these two rows are predictions, not evidence.

> **UPDATE 2026-08-12 (authoring-lane run DONE):** every pending-binary
> statement above is now historical - corpus/reference artifacts are
> committed and `cb refgate` refgated PASS from git HEAD (204 s, 2026-08-12). The empty-FAIL leg rides the
> next `cb discriminate` run.
