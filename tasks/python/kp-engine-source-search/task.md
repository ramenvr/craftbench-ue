---
id: kp-engine-source-search
substrate: ThirdPerson
set: python
tier: T1
capability_bucket: Debug & Refactoring
category: other
layers: [L1, L2I]
introspect: [kp_engine_source_search.py]
---

# kp-engine-source-search

A `tasks/python/` basket task (owner decision 2026-08-11): **outcome-graded
editor-scripting work**. The deliverable is one plain-text answers file
produced by searching the **pinned UE 5.8 engine source** — this repo is
engine-version pinned, so the answers are stable facts of an immutable,
read-only corpus. The file is graded by the deterministic L2I lane exactly
like the `bp` basket: strict disclosed grammar plus **exact-match per line
against verifier-owned constants** derived from the engine source at
authoring time. The introspect never reads the engine at grade time (one
version probe aside), so grading is fast and fully deterministic. No gate
asserts *how* the answers were found — grep, an IDE, an editor-python walk of
the installed source, or plain reading all pass identically (basket law: no
"python was used" gate).

### Provenance and deliberate divergences from the source row

Imported from an earlier internal task list (not shipped): a code-search row
("Search engine source"), **answer-shaped** — the source row's deliverable is
an answer, not an artifact. The source row's prompt cell: *"Which specific EPixelFormat types are supported by
this engine version?"*. Full divergence record: `notes.md` §2. Headlines:

1. **The open enumeration becomes four exact-token questions.** The source row's
   question has a sprawling, hard-to-pin answer (an enum of ~90 entries whose
   "supported" subset is platform-conditional — not deterministically
   gradable). Replaced with four questions of the same *capability* (navigate
   the pinned engine source, read precisely) whose answers are each a single
   unambiguous token: a header path, two integers, a module name.
2. **The answer becomes a FILE.** Answer-shaped rows have no gradable
   deliverable; the answers land in a strict-grammar report at a pre-declared
   path — the report-grading idiom proven by
   `kp_blueprint_actor_audit_report.py`.
3. **Answers are verifier-owned constants.** Settled from `<UE-root>` source
   at authoring time with file+line citations (`notes.md` §3), pinned in the
   introspect, and re-derived from the live engine tree by the authoring aid
   before the reference is harvested. An engine-pin guard fails grading
   loudly on any non-5.8 engine rather than grading against a stale key.

> **Note on the behavior-only rule (Hard Rule #2).** The prompt names four
> engine identifiers (`FCoreDelegates::OnEnginePreExit`,
> `net.MaxConstructedPartialBunchSizeBytes`, `FJsonObject`, `NAME_SIZE`).
> These are **search keys — question inputs, data to look up** — exactly like
> the audit task's `/Engine/BasicShapes/Cube.Cube` asset path: the
> precedented exception for tasks whose whole point is exactly-specified
> lookups. No identifier instructs a mechanism, names a plugin, or tells the
> agent how to search; the graded values (the answers) are never stated in the
> prompt.

## Primary concept

- `ps-console-manager` — Console Variables and Commands (CVars and Commands)
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/console-variables-cplusplus-in-unreal-engine)

The load-bearing capability is **engine-source literacy**: locating where an
engine fact actually lives (a delegate declaration, a cvar registration and
its compiled-in default, a class's owning module, a core constant) and
reading it precisely — the everyday debug-and-refactoring motion of "don't
guess, open the engine". The cvar question sits directly on this concept's
home ground; the adjacent concept is `pipeline-build-build-cs` — Unreal
Engine Modules
(https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-modules)
— for the class-to-module question.

## Prompt given to the agent

> This project builds against a pinned installation of Unreal Engine,
> version 5.8, and that installation ships its complete source code, rooted
> at the directory containing the top-level `Engine/` folder. Answer the
> four questions below about that source code exactly as it exists in the
> pinned installation — verify each answer in the installed source rather
> than answering from general knowledge, because grading is an exact match
> and other engine versions differ. Deliver the answers as a plain-text
> file at `Content/Tasks/kp-engine-source-search/reports/answers.txt`
> consisting only of lines in this one shape (blank lines are ignored;
> order does not matter; values never contain spaces):
>
> ```text
> answer id=<question-id> value=<single-token-answer>
> ```
>
> Exactly one line per question id below, and no lines with any other id.
>
> - `delegate-header` — the one header file that **declares** the
>   engine-shutdown notification member `FCoreDelegates::OnEnginePreExit`
>   (the declaration of the member itself, not files that merely mention or
>   subscribe to it). Give the file's path relative to the installation
>   root, using forward slashes and no leading slash — it will start with
>   `Engine/`.
> - `cvar-default` — the compiled-in default value of the console-tunable
>   setting registered under the name
>   `net.MaxConstructedPartialBunchSizeBytes`. Give it as a plain base-10
>   integer with no separators; if the source writes the value as an
>   arithmetic expression, give the evaluated result.
> - `class-module` — the name of the code module whose public sources
>   contain the full definition of the class `FJsonObject` (forward
>   declarations in other modules do not count). Give the module's name exactly as the
>   build system spells it: a single word, no path.
> - `name-capacity` — the integer value of the compile-time constant
>   `NAME_SIZE` declared in the engine's own runtime sources. Give it as a
>   plain base-10 integer.

## Workspace state pre-task

Substrate content that **exists** under
`Content/Tasks/kp-engine-source-search/`:

- Nothing. This task ships **no baseline asset**. The folder is the
  agent-writable Content carve-out of the `ThirdPerson` substrate
  (`UE-projects/ThirdPerson/AGENT_WRITABLE.json` lists `Content/Tasks/`
  under both `writable` and `asset_writable`); fairness isolation keeps this
  task's folder while hiding every other task's.

Files that **do not exist** (the agent must create exactly one):

- `Content/Tasks/kp-engine-source-search/reports/answers.txt`

Read-only inputs **outside** the workspace:

- The pinned UE 5.8 engine installation the project builds against,
  including its source under `<engine-root>/Engine/Source/`. It is outside
  every writable prefix — the corpus can be read, never modified, and no
  engine file is part of the submission.

Out of scope / not needed:

- No C++ module change, no asset, no level, no map. `Content/Maps/`,
  `Config/` (beyond the listed config lane), and the stock content folders
  are deny-listed — the agent neither can nor needs to touch them.

## Verifier specification

Layer choice: **L1 + L2I**. The single graded artifact is a text file whose
truth was fixed at authoring time; verifier-owned editor-Python compares it
against pinned constants. L2 is deliberately not declared: nothing runs,
nothing ticks, no fixture map exists. Nothing asserts *how* the answers were
found (basket law: outcome-graded).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

The submission is text-only, so L1 is a precondition (the project must load
cleanly), never a correctness signal.

### L2I — Strict-grammar report, exact-match against verifier-owned constants

The verifier-owned script
`tools/verify-single/introspect/kp_engine_source_search.py` runs headless
via `UnrealEditor-Cmd -ExecutePythonScript=` under `-nullrhi`, read-only,
and prints one `CRAFTBENCH-INTROSPECT-JSON` verdict block with **exactly 7
named checks on every leg** (constant denominator). PASS requires all 7.

The corpus guard (1 check):

```text
engine_pin_matches      unreal.SystemLibrary.get_engine_version() starts
                        with "5.8." — the pinned answer constants were
                        derived from the 5.8 source; grading on any other
                        engine FAILS loudly (ENGINE_PIN_MISMATCH version=)
                        instead of silently using a stale answer key. This
                        is a harness invariant, not an agent requirement:
                        on a healthy rig it always passes (the empty
                        submission therefore scores 1/7, overall FAIL).
```

The report (6 checks):

```text
answers_file_present            Content/Tasks/<id>/reports/answers.txt
                                exists (ANSWERS_FILE_MISSING path=)
answers_grammar_parses          every non-blank line matches
                                ^answer id=(\S+) value=(\S+)$ ; no duplicate
                                id, no id outside the four disclosed ones,
                                at least one answer line
                                (ANSWERS_GRAMMAR_BAD line=)
answer_delegate_header_exact    value(delegate-header) ==
                                Engine/Source/Runtime/Core/Public/Misc/CoreDelegates.h
answer_cvar_default_exact       value(cvar-default) == 65536
answer_class_module_exact       value(class-module) == Json
answer_name_capacity_exact      value(name-capacity) == 1024
```

Each answer check fails as `ANSWER_WRONG id=` (present but wrong, exact
string compare, case-sensitive) or `ANSWER_MISSING id=` (grammar parsed but
the id was never answered).

**The gold-leak defense.** Every expected value is **pinned in the verifier
script's constants**, derived at authoring time from the engine source with
file+line citations recorded in `notes.md` §3 — nothing expected is read
from any path the agent can write, and the engine itself is never read at
grade time.

**Fail-closed properties** (mirroring the basket convention):

- A missing submission fails all six report checks with the one named root
  cause fanned out (`ANSWERS_FILE_MISSING path=`); an existing-but-empty
  file is a grammar failure (`reason=no_answer_lines`), never a vacuous
  pass; a grammar failure fans its own detail into all four answer checks.
- Error tokens (`*_PROBE_ERROR`, `*_READ_ERROR`, `*_ABORTED`,
  `CHECK_NOT_EVALUATED`) are disjoint from graded failure tokens and appear
  in no MATRIX row, so a broken UE API can never be credited as a named
  variant failure.
- All details are ASCII-only (the cp1252 log read-back trap,
  `t2-homing-projectile` 2026-07-21).

**Score granularity.** `registry.py` reports `tests_passed/tests_run`, so
`report.json` carries `x/7` as trajectory signal while `overall` stays
`all(pass)`.

## Reference solution metadata

- LOC range: **0** lines of module code. The deliverable is one 4-line text
  file; the honest route is four engine-source searches (grep/IDE/scripted)
  plus one arithmetic evaluation.
- Files touched: 1 created (`reports/answers.txt`), 0 modified.
- Senior-dev hours: 0.25-0.75 — four lookups in a source tree the dev may
  never have opened, plus care with the disclosed normalization (relative
  path, forward slashes, evaluated integer).

## Anti-gaming notes

1. **Answers transcribed from the brief / guessed placeholders.** *Failure
   mode*: the agent writes a well-formed file without doing the lookups —
   the brief contains the questions and the normalization rules but zero
   answer values. *Defense*: exact match per line against verifier-owned
   constants pinned from the engine source (`ANSWER_WRONG id=`); there is
   no answer VALUE in the agent-visible surface to transcribe (one incidental module-name-inside-identifier substring overlap is a recorded residual in notes.md). Pointer:
   `kp_engine_source_search.py::EXPECTED_ANSWERS` and `::_report_checks`.
   MATRIX rows R03-R06.
2. **Shotgunning.** *Failure mode*: multiple candidate values for one
   question (duplicate `answer id=cvar-default` lines) or extra invented
   ids, hoping one matches. *Defense*: a duplicate id and an unknown id are
   each a grammar failure (`ANSWERS_GRAMMAR_BAD line=` with
   `duplicate_answer_id` / `unknown_answer_id`) that also fans out to all
   four answer checks — only one value per question can ever be submitted.
   Pointer: `kp_engine_source_search.py::_parse_answers`. Proven offline
   (shotgun leg scores 2/7).
3. **Format smuggling.** *Failure mode*: pasting the source expression
   (`1024 * 64`), an absolute local path with a drive letter, or
   backslashes — superficially "right", not the demanded token. *Defense*:
   the full-line-anchored single-token grammar rejects any value containing
   whitespace (`reason=unrecognized_line`), and exact string compare
   rejects every other normalization; the prompt fully discloses the
   required normalization so the exactness is fair (the t0 under-spec
   lesson). Pointer: `kp_engine_source_search.py::RE_ANSWER`.
4. **Empty or missing report.** *Failure mode*: no file, or an empty file,
   passing vacuously. *Defense*: fail-closed fanout with the named root
   cause (`ANSWERS_FILE_MISSING path=` / `reason=no_answer_lines`) and a
   constant 7-check denominator — proven offline: the empty leg scores 1/7
   (only the harness-invariant pin check passes), overall FAIL. Pointer:
   `kp_engine_source_search.py::_report_checks`.
5. **Tampering with the answer key or the grader.** *Failure mode*: edit
   the introspect's constants or the engine source it cites. *Defense*:
   `tools/verify-single/` is outside every writable prefix and graded from
   the harness checkout (sandbox path-acceptance keeps every writable prefix away from it; an agent has no write path into the grader); the engine
   installation is likewise outside the sandbox, and the `engine_pin_matches`
   guard fails grading on any engine that is not 5.8
   (`ENGINE_PIN_MISMATCH version=`). Pointer:
   `kp_engine_source_search.py::_pin_check`; sandbox law in
   `UE-projects/ThirdPerson/AGENT_WRITABLE.json`.

## Hidden invariants

- **The check denominator is fixed at 7 on every leg**, including the empty
  submission. A submission cannot improve its reported ratio by making
  checks unreachable.
- **The engine-pin guard is the corpus-unmodified guard**: the corpus (the
  pinned engine source) is immutable and read-only by construction, so the
  one way the answer key can rot — grading against a different engine — is
  the one thing the guard checks, with a named failure.
- **Error tokens are uncreditable**: a broken UE API name degrades to a
  `*_PROBE_ERROR` check failure that matches no MATRIX row.
