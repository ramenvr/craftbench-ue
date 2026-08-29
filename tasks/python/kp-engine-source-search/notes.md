# kp-engine-source-search — authoring notes

Wave-3 `tasks/python/` basket task (owner decision 2026-08-11: outcome-graded
editor-scripting; the deliverable is the resulting editor state / text
report, graded by the deterministic L2I lane; no gate asserts "python was
used"). This task is the basket's minimal report-only shape: ONE text file,
zero assets, answer key pinned from an immutable corpus (the engine source).

## 1. Provenance (source row)

- **Source**: an earlier internal task list (not shipped) — a code-search row
  ("Search engine source"). **Answer-shaped**: the source row's deliverable is
  an answer to a question, not an artifact.
- **Its prompt cell**: "Which specific EPixelFormat types are supported by
  this engine version?" (workspace column: "Empty Project").
- **Id scheme**: `kp-` is the python-basket family prefix; the source row's
  `t12-` is a row index, not a tier, and is dropped. Substring audit:
  `kp-engine-source-search` is not a substring of any other task id and
  contains none (`inventory.py` raw-substring membership trap).

## 2. Divergences from the source row (full record)

| # | source row | this task | why |
|---|---|---|---|
| 1 | one open enumeration question (EPixelFormat support) | four exact-token questions (header path, cvar default, owning module, core constant) | the source row's answer is a ~90-entry enum whose "supported" subset is platform- and RHI-conditional — not deterministically gradable by exact match; the replacement keeps the capability (navigate the pinned engine source, read precisely) and makes every answer a single unambiguous token |
| 2 | answer-shaped (no deliverable) | strict-grammar report file at `Content/Tasks/<id>/reports/answers.txt` | printed/chat answers are not gradable artifacts; the report idiom is the basket's proven text-artifact lane (`kp_blueprint_actor_audit_report.py` precedent) |
| 3 | "Empty Project" workspace | `ThirdPerson` substrate, no baseline asset | repo substrate law; the workspace is irrelevant to the lookup, and ThirdPerson is the python-basket home |
| 4 | implicit "this engine version" | explicit engine-pin guard (`engine_pin_matches`) + answers pinned as verifier-owned constants with file+line evidence | makes "this engine version" a checked invariant instead of an assumption; grading on a non-5.8 engine fails loudly (`ENGINE_PIN_MISMATCH version=`) |

## 3. Verifier-owned constants TABLE (the authoring-time truth)

Derived 2026-08-11 from the pinned engine at `<UE-root>` — **engine
Build.version: 5.8.0, Changelist 55116800, branch `++UE5+Release-5.8`**
(`<UE-root>/Engine/Build/Build.version`). These are the constants embedded
in `tools/verify-single/introspect/kp_engine_source_search.py::EXPECTED_ANSWERS`;
the aid re-derives each one from the live engine tree and dies on drift
before anything is harvested.

| qid | question | pinned answer | engine evidence (path relative to `<UE-root>`) |
|---|---|---|---|
| `delegate-header` | header declaring `FCoreDelegates::OnEnginePreExit` | `Engine/Source/Runtime/Core/Public/Misc/CoreDelegates.h` | `Engine/Source/Runtime/Core/Public/Misc/CoreDelegates.h:262` — `static CORE_API FSimpleMulticastDelegate OnEnginePreExit;` (declaration unique in the tree: 6 other files only reference/subscribe; the decl-pattern greps exactly once in this header) |
| `cvar-default` | compiled-in default of `net.MaxConstructedPartialBunchSizeBytes` | `65536` | `Engine/Source/Runtime/Engine/Private/DataChannel.cpp:105` — `static int32 NetMaxConstructedPartialBunchSizeBytes = 1024 * 64;`, registered at `:107` (`TEXT("net.MaxConstructedPartialBunchSizeBytes")`); initializer pattern greps exactly once |
| `class-module` | module whose public sources declare `FJsonObject` | `Json` | `Engine/Source/Runtime/Json/Public/Dom/JsonObject.h:322` — `class FJsonObject` (the real declaration; other hits are forward decls in sibling headers); module rules `Engine/Source/Runtime/Json/Json.Build.cs` |
| `name-capacity` | value of `NAME_SIZE` | `1024` | `Engine/Source/Runtime/Core/Public/UObject/NameTypes.h:57` — `enum {NAME_SIZE = 1024};` (the `NAME_SIZE =` pattern greps exactly once in the header) |

All four uniqueness claims and the `1024 * 64 == 65536` evaluation were
re-verified mechanically on 2026-08-11 with the same regexes the aid uses
(offline run against `<UE-root>`; all four derivations matched the pinned
constants exactly).

## 4. Design decisions

- **The corpus is the pinned engine; the corpus guard is the version pin.**
  Sibling report tasks guard a writable corpus with per-file hash/asset
  facts. Here the corpus is read-only, outside every writable prefix, and
  never staged — the only way the answer key rots is grading on a different
  engine, so the guard is `engine_pin_matches` (prefix `5.8.`), failing
  with the named `ENGINE_PIN_MISMATCH version=` corpus-stale message. The
  introspect **never reads the engine source at grade time** — grading is
  a pure text compare, fast and deterministic (the task-card requirement).
- **Answer key excludes lazy defaults / prompt transcription.** The brief
  contains zero answer values; a well-formed file of guesses fails four
  exact matches. The cvar answer additionally requires evaluating the
  source expression (`1024 * 64`), so even verbatim source-copying needs a
  processing step (and the un-evaluated paste fails the single-token
  grammar).
- **Shotgun-proof grammar.** Duplicate ids and unknown ids are grammar
  failures (not per-answer ones), so a submission can never submit two
  candidate values for one question or pad with invented ids.
- **Single-literal token heads.** Every `TOKEN key=` failure head lives in
  ONE source string literal so the MATRIX oracle's static source grep finds
  it. Verified 2026-08-11: all five matrix heads (`ENGINE_PIN_MISMATCH
  version=`, `ANSWERS_FILE_MISSING path=`, `ANSWERS_GRAMMAR_BAD line=`,
  `ANSWER_WRONG id=`, `ANSWER_MISSING id=`) grep as single literals; the
  two automation result markers appear nowhere in the script.
- **Error-token disjointness**: `ENGINE_PIN_PROBE_ERROR`,
  `ANSWERS_PROBE_ERROR`, `ANSWERS_READ_ERROR`, `KPESS_INTROSPECTION_ABORTED`,
  `CHECK_NOT_EVALUATED` appear in no MATRIX row — a broken UE API is never
  creditable as a named failure.
- **The empty leg scores 1/7, not 0/7.** The pin check is a harness
  invariant and passes on any healthy rig regardless of submission. Overall
  is still FAIL via `ANSWERS_FILE_MISSING path=` — the non-vacuity bar is
  FAIL-on-empty, which holds; recorded here so nobody "fixes" the 1/7.
- **T1 / Debug & Refactoring / `ps-console-manager`.** The capability is
  engine-source literacy (don't guess, open the engine); the cvar question
  sits on the primary concept, the module question on
  `pipeline-build-build-cs`. Four lookups ≈ 15-45 senior-dev minutes.
- **cameras.json: N/A by design** (checklist §5 is a SHOULD). The
  deliverable is a text file; there is no scene, no actor, and nothing to
  film. Recording the decision here rather than leaving the absence
  ambiguous.

## 5. Offline proof (2026-08-11, no editor)

Runner: a fake-`unreal` harness driving the real introspect end to end
(script kept in the authoring session's scratchpad; trivially
reconstructible — fake `Paths.project_content_dir` + fake
`SystemLibrary.get_engine_version`). Nine legs, all green:

1. **no-module**: 7 checks, all fail, ONLY uncreditable error tokens
   (`ENGINE_PIN_PROBE_ERROR`, `ANSWERS_PROBE_ERROR`) — no matrix row
   claimable.
2. **empty submission**: 1/7 (pin passes), the six report checks all carry
   `ANSWERS_FILE_MISSING path=` — the MATRIX empty row.
3. **reference-shaped file**: 7/7.
4. **one wrong value**: 6/7, failing check carries
   `ANSWER_WRONG id=cvar-default reported=2 expected=65536`.
5. **shotgun duplicate id**: 2/7, grammar fails
   `reason=duplicate_answer_id` and fans out.
6. **unknown id**: grammar fails `reason=unknown_answer_id`.
7. **missing id (3 of 4 answered)**: grammar passes, the absent answer
   fails `ANSWER_MISSING id=name-capacity present=[...]`.
8. **multi-token smuggling** (`value=1024 * 64`): grammar fails
   `reason=unrecognized_line`.
9. **wrong engine pin** (`5.9.0-...`): pin fails
   `ENGINE_PIN_MISMATCH version=`, answers still compared independently.

## 6. Reference status

**Reference pending the authoring-lane run.** This track cannot run UE, so
`reference/` is EMPTY (not even committed as a directory) and no byte in
this change-set is fabricated — deliberately including the reference
`answers.txt` itself, even though it is plain text: the aid run is what
certifies the file against the live engine pin (step 3 proves
`SystemLibrary.get_engine_version` headless) rather than against my reading
of the source. There is likewise **no corpus to build** (the corpus is the
engine); the aid's step 1 substitutes corpus-truth re-derivation.

`aids/author_reference.py` is the generator: derive engine root from the
running editor, re-derive all four answers from the live source (die on any
drift from the grader's constants), write `answers.txt` from the grader's
own `EXPECTED_ANSWERS` (agreement by construction), self-grade in-process
against the real introspect, harvest into `reference/` ONLY on 7/7, then
delete the substrate folder (disk-is-truth cleanup; no assets were created,
so any stale registry row would be a KPESS-WARN, never a die). `KPESS-DONE`
in the editor log is the success marker; absence = failed.

## 7. Calibration TODOs (run in the authoring-lane editor session)

- [ ] **`unreal.SystemLibrary.get_engine_version()` headless under
  `-nullrhi`** — the one unproven grader probe (everything else is
  `os`/`re` + the precedented `Paths.project_content_dir` route). Record
  the exact returned string here after the run. If the API is unavailable
  headless, the pin check fails as an uncreditable
  `ENGINE_PIN_PROBE_ERROR` (never a false PASS) and the refgate run
  surfaces it before any agent sees the task; fallback route:
  `unreal.Paths.engine_version_agnostic_user_dir` is NOT a version source —
  prefer parsing `Engine/Build/Build.version` from `Paths.root_dir()`.
- [ ] **Aid run**: `UnrealEditor-Cmd <ThirdPerson.uproject>
  -ExecutePythonScript=<abs path to aids/author_reference.py> -nullrhi
  -unattended -nosplash`; grep the newest `ThirdPerson*.log` for
  `KPESS-DONE` + the four `KPESS-TRUTH` lines; commit
  `reference/Content/Tasks/kp-engine-source-search/reports/answers.txt`.
- [ ] `cb lint --task python/kp-engine-source-search` (also flushes any
  remaining `bp|cpp` assumptions in tooling — the `set: python` risk the
  basket's first task recorded).
- [ ] `cb discriminate --task python/kp-engine-source-search --wip`
  (reference PASS + empty FAIL via `ANSWERS_FILE_MISSING path=`).
- [ ] Post-commit: `./cb refgate python/kp-engine-source-search` green from
  git HEAD (the close).
- [ ] **Repo-count edits**: CATALOG row + any hard-coded task-count claims
  when this task lands (imported-set precedent).

## 8. Risks

1. **Agent discoverability of the engine root** (the one real open
   question). The prompt says "the pinned installation the project builds
   against, rooted at the directory containing the top-level `Engine/`
   folder" but does not hand over a filesystem path (host-specific).
   Agents can find it (uproject association, build logs, environment), and
   answers are engine-relative so the root's location never enters the
   grade — but if pilot runs show agents wasting their budget locating the
   root, add the root path to the harness preamble (a harness change, not
   a spec change; the preamble-substrate-blind lesson says check this
   BEFORE the first bench).
2. **Memory answering** — accepted residual (task.md): outcome-graded
   basket, no search gate. The question mix makes blind recall of all four
   exact tokens brittle; a model that truly knows the pinned source cold
   earns the pass.
3. **5.8 hotfix drift**: a hypothetical 5.8.x bump that moved one of the
   four facts would make the committed reference FAIL refgate loudly (and
   the aid die on re-derivation) — the fail-safe direction. Exact pin
   recorded in §3.
4. **`spec.py` front-matter parse**: verified through the real parser
   (2026-08-11) — `id`, `set: python`, `layers: [L1, L2I]`,
   `introspect: [kp_engine_source_search.py]` all round-trip.
5. **Grader-helper coupling in the aid** (imports `EXPECTED_ANSWERS`,
   `QUESTION_IDS`, `main`): a grader refactor can break the aid. Accepted:
   the aid dies loudly and is dev-only; the coupling is what guarantees
   reference/grader agreement.

## 9. Checklist state (docs/TASK-AUTHOR-GUIDE.md)

- [x] 1. Spec — `task.md` (v2 front matter parses through the real
      `spec.py`; behavior-only prompt with the precedented search-key
      exception documented; 5 anti-gaming notes with resolvable defense
      pointers; verifier spec names every failure substring)
- [ ] 2. Scaffold pair — N/A by design (no C++ scaffold; text-only
      deliverable, no baseline asset)
- [ ] 3. Fixture pair — N/A (no L2; L2I only)
- [ ] 4. Map — N/A (no committed verifier map, no level anywhere in the
      task; no `docs/MAPS.md` row owed)
- [ ] 5. Camera plan — N/A by design (§4: nothing to film; decision
      recorded)
- [ ] 6. Reference — PENDING the authoring-lane run of
      `aids/author_reference.py` (this change-set ships the generator, not
      the bytes)
- [x] 7. Discrimination — `discrimination/MATRIX.md`: automatic
      reference-PASS / empty-FAIL rows + the §7a requirements table (7
      rows, every requirement mapped to a live assertion; no variant owed)
- [ ] 8. Gates — lint can run now; discriminate/refgate blocked on the
      reference file
- [ ] 9. Commit + PR + refgate close — future work

> **Residual (review catch 2026-08-12):** the class-module answer is an
> incidental substring of the class identifier in the prompt's search key.
> Recorded next to the memory-answering residual - both accepted under the
> outcome-graded basket law. The full-definition clause added to the prompt
> disambiguates against the 20+ forward-declaration sites verified in the
> pinned source.

## Accepted residuals (moved from task.md 2026-08-16; lint spec-h2-allowlist)

- **Memory answering.** An agent that happens to know all four facts
  without opening the source passes — the basket is outcome-graded and no
  gate asserts the search happened. Mitigation by construction, not by
  gate: the cvar value is written in source as an expression (`1024 * 64`),
  the path answer demands an exact engine-relative normalization, and the
  question set spans four unrelated corners of the tree — blind recall of
  all four exact tokens is brittle. Recorded, accepted.
- **Exact match may fail a semantically-defensible variant** (`0x10000`,
  a backslashed path, a leading `/`). Accepted: the normalization is fully
  disclosed in the prompt, so this grades instruction-following exactness,
  which is part of the point.
- **The pin guard cannot tell 5.8.0 from a future 5.8.x hotfix.** If a
  hotfix moved one of the four facts, the reference gate would FAIL loudly
  at the next refgate run (the aid re-derives every constant from the live
  engine and dies on drift) — but an agent graded between hotfix and
  re-derivation would see a false FAIL. Exact pinned build recorded in
  `notes.md` §3 (5.8.0 CL 55116800); considered acceptable for a
  version-pinned repo.
- **No gate asserts the mechanism** (basket law): grep, IDE search, an
  editor-python `Paths.engine_source_dir()` walk, or reading the files by
  hand are all equally passing routes. That is the basket's design, not a
  leak.
