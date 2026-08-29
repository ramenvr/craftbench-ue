---
id: kp-routine-usage-search
substrate: ThirdPerson
set: python
tier: T1
capability_bucket: Tools & Pipeline
category: other
layers: [L1, L2I]
introspect: [kp_routine_usage_search.py]
---

# kp-routine-usage-search

A `tasks/python/` basket task (outcome-graded editor scripting): the
deliverable is a single plain-text **usage report** — which of four
committed corpus class assets reference a stated source-library routine —
graded by the deterministic L2I lane against **verifier-owned expected
constants** (authoring-time truth pinned in the introspect script), plus a
**corpus-unmodified guard** (per-file hashes) so that editing the search
targets to match a report can never move the truth. The prompt describes an
outcome whose exactness (per-entry yes/no verdicts under a strict machine
grammar) makes editor scripting the natural way to complete it, but **no
gate asserts "python was used"** — any route that produces a truthful
report passes identically.

### Provenance and deliberate divergences from the source row

Imported from an earlier internal task list (not shipped): a usage-search row.
The source row's prompt: *"Which blueprints use `UMyUtilityLibrary::GetBlueprintComponent`?"*
with starting assets *"C++ function library UMyUtilityLibrary. A blueprint
that references one of its functions."* Full divergence record:
`notes.md` §2. Headlines:

1. **The plan's obstacle O1 ("answer-shaped, doesn't fit the
   overlay-and-grade verifier") is dissolved**, not worked around: the
   answer becomes a strict-grammar text artifact at a pre-declared path,
   cross-checked line-by-line — the report pattern
   `kp-blueprint-actor-audit-report` refgate-proved this week.
2. **The one-referencer fixture becomes a discriminating four-entry
   corpus.** The source row's single referencing blueprint makes every naive
   strategy (all-yes, name-grep, library-dependency scan) indistinguishable
   from real search. This corpus is built so each naive strategy gets at
   least one entry wrong: a direct caller, an **inheriting child with no
   mention of the routine in its own file**, a caller of a *sibling*
   routine from the same library, and a non-referencer that merely
   **carries the routine's name as a marker value**.
3. **Truth is pinned, not recomputed.** The verifier never inspects the
   corpus graphs at grade time (no protected-reflection reads); it checks
   the corpus is byte-identical to the committed baseline and that the
   report tells the pinned authoring-time truth about it.
4. **Names re-homed**: the source row's `UMyUtilityLibrary::GetBlueprintComponent`
   leaks mechanism vocabulary ("Blueprint", "Component") into the graded
   symbol; the library becomes `EvalUtilityLibrary` with behavior-named
   routines (`ComputeChecksum`, `FormatLabel`, `ClampScore`), and the
   corpus lives at the repo-convention path
   `/Game/Tasks/<task-id>/corpus/` with direction-neutral entry names.

> **Note on the behavior-only rule (Hard Rule #2).** Like the sibling
> report task, this prompt names the concrete graded values — the routine
> name, the corpus folder, the report path and its grammar — the
> precedented exception for tasks whose whole point is producing
> exactly-specified artifacts. **No engine class name, no API name, no
> editor-operation name appears in the prompt**; the corpus items are
> "placeable object classes" and the mechanism of searching is entirely the
> agent's choice.

## Primary concept

- `ps-bp-function-library` — Blueprint Function Libraries
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/blueprint-function-libraries-in-unreal-engine)

The load-bearing capability is **usage search across the C++/asset seam**:
understanding that a natively-defined library routine can be referenced by
a class asset directly, inherited from a base class, or merely name-dropped
without any real tie — and telling those cases apart. Adjacent concepts:
`ps-asset-registry` (dependency/registry literacy is one honest route) and
`ps-scripting-editor-python` (the natural bulk-inspection tool); the
primary difficulty is knowing what "uses a library function" actually means
across those routes, which is the function-library page's home ground.

## Prompt given to the agent

> The project's game source includes a small utility routine library; one
> of its routines is named `ComputeChecksum`. The folder
> `Content/Tasks/kp-routine-usage-search/corpus/` contains four
> ready-made placeable object classes. Determine, for each of the four,
> whether it **references** `ComputeChecksum`, and record your findings in
> a plain-text report at
> `Content/Tasks/kp-routine-usage-search/reports/usage.txt`.
>
> An entry references the routine when running an object of that class can
> invoke it — through logic of the entry's own, or through logic it
> inherits from the class it is based on. The routine's **name merely
> appearing** — stored as text or a marker value, or alongside a use of a
> *different* routine from the same library — does **not** make an entry a
> referencer.
>
> The four corpus entries and the utility source are **inputs**: examine
> them any way you like, but do not modify, move, or delete them. Grading
> checks they are byte-identical to how you found them, and any change
> fails the task regardless of what the report says.
>
> The report consists only of lines in these two shapes (blank lines are
> ignored; order does not matter; values never contain spaces):
>
> ```text
> function name=ComputeChecksum
> entry name=<entry-name> references=<yes|no>
> ```
>
> Exactly one `function` line, exactly as shown above. Exactly one `entry`
> line for each of the four corpus entries, using the exact name each has
> in the corpus folder (without any file extension), and no other `entry` lines. Every verdict is
> checked against the truth of the corpus as committed; a verdict that
> disagrees with it fails the task.

## Workspace state pre-task

Files that **exist** (substrate baseline, agent-readable; the source pair
is inside the agent-writable module, the corpus inside the agent-writable
content root — but per the prompt, all of it is guarded input):

- `Source/ThirdPerson/Tasks/kp-routine-usage-search/EvalUtilityLibrary.h`
  / `.cpp` — a small callable utility library exposing three routines:
  `ComputeChecksum`, `FormatLabel`, `ClampScore`. Pure computation, no
  gameplay behavior.
- `Content/Tasks/kp-routine-usage-search/corpus/` — four committed class
  assets: `BP_North.uasset`, `BP_East.uasset`, `BP_South.uasset`,
  `BP_West.uasset`. (Verifier-authored binaries; what each one does is the
  question the task asks, so it is deliberately not restated here.)

Files that **do not exist** (the agent must create exactly one):

- `Content/Tasks/kp-routine-usage-search/reports/usage.txt`

Out of scope / not needed:

- No C++ edits are required or expected; the deliverable is the report
  only. `Content/Maps/`, stock content and the verifier module are
  deny-listed as always.

## Verifier specification

Layer choice: **L1 + L2I**. The graded artifact is a text file judged
against constants plus a byte-level guard on committed inputs — all static
facts, no time evolution, no PIE. L2 is deliberately not declared. Nothing
asserts *how* the answer was produced (basket law).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

The baseline library compiles in the substrate; a submission is expected to
add no source, so L1 is a precondition (an agent that breaks the module
FAILs here), never a correctness signal.

### L2I — Report cross-check + corpus-unmodified guard

The verifier-owned script
`tools/verify-single/introspect/kp_routine_usage_search.py` runs headless
via `UnrealEditor-Cmd -ExecutePythonScript=` under `-nullrhi`, read-only,
and prints one `CRAFTBENCH-INTROSPECT-JSON` verdict block with **exactly 9
named checks on every leg** (constant denominator). PASS requires all 9.

**The verifier-owned truth** (pinned constants in the script; authoring
record in `notes.md` §3): the stated function is `ComputeChecksum`; the
corpus verdicts are `BP_North=yes` (direct call), `BP_East=yes` (child of
`BP_North`, inherits the call — its own file never mentions the routine),
`BP_South=no` (calls sibling `FormatLabel`), `BP_West=no` (carries the
name `ComputeChecksum` as a marker value only, no tie to the library).

Group 1 — the corpus-unmodified guard (4 checks):

```text
corpus_assets_present       all four corpus assets resolve in the registry
                            (USAGE_CORPUS_ASSET_MISSING path=)
corpus_dir_exact            the on-disk corpus folder holds EXACTLY the four
                            pinned .uasset files - nothing missing
                            (USAGE_CORPUS_FILE_MISSING file=), nothing added
                            (USAGE_CORPUS_EXTRA_FILES extras=)
corpus_bytes_unmodified     raw sha256 of every corpus file equals the
                            digest pinned at authoring time
                            (USAGE_CORPUS_MODIFIED file=)
library_source_unmodified   CR-normalized sha256 of EvalUtilityLibrary.h/.cpp
                            equals the pinned pair
                            (USAGE_LIBRARY_MODIFIED file= /
                             USAGE_LIBRARY_SOURCE_MISSING file=)
```

Group 2 — the report (5 checks):

```text
report_file_present         Content/Tasks/<id>/reports/usage.txt exists
                            (USAGE_REPORT_MISSING path=)
report_grammar_parses       every non-blank line matches one of the two
                            disclosed shapes; exactly one function line; no
                            duplicate entry names (USAGE_GRAMMAR_BAD line=)
report_function_line_correct  the function line names exactly
                            ComputeChecksum (USAGE_FUNCTION_LINE_WRONG
                            reported=)
report_covers_corpus_exactly  reported entry-name set EQUALS the pinned
                            corpus set, both directions — a fabricated
                            entry fails, an omitted one fails
                            (USAGE_COVERAGE_MISMATCH reported_only=)
report_verdicts_truthful    iterates the PINNED corpus list: every entry
                            must be reported (USAGE_VERDICT_MISSING entry=)
                            with the pinned verdict
                            (USAGE_VERDICT_WRONG entry=)
```

**The gold-leak defense.** Every expected value — the function name, the
four entry names, the four verdicts, the corpus digests, the library
digests — is **pinned in the verifier script's constants**. Nothing
expected is ever read from a place the submission can write, and the
verdict check iterates the pinned list (never the report's own entry set),
so an evasive report cannot shrink what it is graded on.

**Fail-closed properties** (set convention):

- The empty submission leaves the corpus baseline intact, so the guard
  checks legitimately pass; every report check fails with the
  `USAGE_REPORT_MISSING path=` root cause fanned out — overall FAIL via
  the named assertion, never a vacuous pass, denominator still 9.
- Each guard check is independent (registry, disk listing, hashes,
  sources), so a single broken API degrades to exactly one failed check
  with the exception in `detail`.
- Error tokens (`*_PROBE_ERROR`, `*_READ_ERROR`, `*_UNPINNED`,
  `*_ABORTED`, `CHECK_NOT_EVALUATED`,
  `USAGE_CORPUS_HASH_TARGET_MISSING`) are disjoint from graded failure
  tokens and appear in no MATRIX row.
- All details are ASCII-only (the cp1252 log read-back trap).

**Score granularity.** `registry.py` reports `tests_passed/tests_run`, so
`report.json` carries `x/9` as trajectory signal while `overall` stays
all-or-nothing.

## Reference solution metadata

- LOC range: **0** lines of module code. The deliverable is one ~6-line
  text file; the natural route is a throwaway inspection script (or a
  short editor session with the reference viewer) the agent writes and
  runs, not itself graded or submitted.
- Files touched: 1 created (`reports/usage.txt`), 0 modified.
- Senior-dev hours: 0.5-1.5 — the mechanics are trivial; the hours are in
  inspecting four assets correctly (catching the inherited reference and
  rejecting the name-only decoy) rather than pattern-matching names.

## Anti-gaming notes

1. **Blanket or guessed verdicts.** *Failure mode*: the agent answers
   all-yes, all-no, or flips a coin instead of searching. *Defense*: the
   truth is two-yes/two-no by construction, so either blanket answer fails
   `report_verdicts_truthful` (`USAGE_VERDICT_WRONG entry=`) on two
   entries; every verdict is cross-checked against the pinned constants.
   Pointer: `kp_routine_usage_search.py::_report_checks` (the
   `CORPUS_TRUTH` iteration). MATRIX rows R05.
2. **Name-grep shortcut.** *Failure mode*: the agent byte/text-scans each
   corpus file for `ComputeChecksum` and reports hits — a plausible-looking
   mechanism that is wrong on this corpus. *Defense*: discriminating corpus
   design, not an extra gate — `BP_East` references the routine with **no
   occurrence of the name in its own file** (inherited from `BP_North`) and
   `BP_West` carries the name **without referencing** it, so the shortcut
   yields two wrong verdicts and fails `report_verdicts_truthful`. A
   library-level dependency scan similarly mislabels `BP_South`. Pointer:
   `CORPUS_TRUTH` in `kp_routine_usage_search.py` + `notes.md` §3
   (corpus construction).
3. **Editing the targets to match the report.** *Failure mode*: the agent
   deletes `BP_West`'s marker, strips `BP_North`'s call, replaces corpus
   files with fresh empties, or deletes the awkward entries — then writes
   a report that is true of the *edited* corpus. *Defense*: the
   corpus-unmodified guard — registry existence
   (`USAGE_CORPUS_ASSET_MISSING path=`), exact disk listing
   (`USAGE_CORPUS_FILE_MISSING file=` / `USAGE_CORPUS_EXTRA_FILES
   extras=`), and per-file pinned sha256 (`USAGE_CORPUS_MODIFIED file=`) —
   and the truth constants live in the verifier, so even a successful edit
   could never move the expected verdicts. Pointer:
   `kp_routine_usage_search.py::_guard_checks`. MATRIX row R06.
4. **Editing the library source instead.** *Failure mode*: the agent
   renames or deletes `ComputeChecksum` in the writable module so that "no
   reference exists anywhere" (or so a self-run search tool agrees with a
   fabricated report). *Defense*: `library_source_unmodified` pins
   CR-normalized digests of both source files
   (`USAGE_LIBRARY_MODIFIED file=`); truth is pinned regardless. Pointer:
   `kp_routine_usage_search.py::_guard_library_unmodified`. MATRIX row
   R07.
5. **Coverage gaming.** *Failure mode*: omit the hard entries, or pad the
   report with invented entries hoping partial credit. *Defense*:
   `report_covers_corpus_exactly` is a two-directional set equality
   (`USAGE_COVERAGE_MISMATCH reported_only=`), and
   `report_verdicts_truthful` independently iterates the pinned list so an
   omitted entry also fails it (`USAGE_VERDICT_MISSING entry=`); `overall`
   is all-or-nothing. Pointer: `kp_routine_usage_search.py::_report_checks`.
   MATRIX rows R04-R05.

## Hidden invariants

- **The check denominator is fixed at 9 on every leg**, including the
  empty submission. A submission cannot improve its reported ratio by
  making checks unreachable.
- **The truth excludes every trivial strategy's output**: all-yes fails
  two entries, all-no fails two, per-file name-grep fails two (`BP_East`,
  `BP_West`), library-dependency scanning fails one (`BP_South`). Any
  future corpus regeneration must re-verify this column and re-pin both
  the truth constants and the digests together (`notes.md` §4).
- **The verdict gate iterates the verifier's own list, never the
  report's** — dependent checks fan out named root causes, so a
  wrong-reason FAIL is visible as an uncredited token.
