# Discrimination matrix — t1-extraction-volume-per-actor-trigger

One row per submission; the "Expected message" cell must appear as a
substring of the L2 failure (discriminate greps the log for it — a
wrong-reason FAIL is NOT discrimination). Run:
`cb discriminate --task cpp/t1-extraction-volume-per-actor-trigger [--wip]`.

| Submission | Verdict | Fails at | Expected message substring | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | PASS | — | — | — |
| empty | FAIL | cp1 (1.5s) | `after the first entrant` | #1 (unbound handler shape) |
| `log-on-beginplay/` | FAIL | cp0 (0.5s) | `to NOT be logged before any entry` | #1 |
| `log-every-entry/` | FAIL | cp3 (2.5s) | `re-entering to add no new emission` | #2 |
| `global-once/` | FAIL | cp4 (3.5s) | `after a second distinct individual entered` | #3 |

Notes:
- Checkpoint schedule is {0.5, 1.5, 2.0, 2.5, 3.5}: cp2 (2.0s) carries NO
  graded assert — it only performs probe A's re-entry, on its own engine frame,
  so the exit (cp1) and the re-entry (cp2) can never coalesce into "no overlap
  state change" and silently un-test the dedupe gate at cp3.
- The empty leg (scaffold as shipped: no overlap handling) sails through cp0
  silent, then observes 0 emissions at cp1 — the same named assertion an
  agent's dead binding would hit.
- Anti-gaming note #4 (wrong category/verbosity) is argued from the listener's
  category+verbosity filter rather than a separate submission — the filter is
  the same machinery the t0 sanity and t1-overlap-logs-once fixtures already
  field-proved. Bounded coverage, stated honestly.
- **ASCII rule (inherited from t2-homing-projectile the hard way):** FinishTest
  messages and these substrings must be ASCII-only — the UE log's UTF-8 bytes
  are read back as cp1252, so an em dash becomes mojibake and the substring
  grep misses, classifying a CORRECT fail as wrong-reason.

## Status
- Authored 2026-07-29 from the spec + the fixture source.
- **EXECUTED 2026-07-29** (same date, after the binary half landed):
  `cb discriminate --task cpp/t1-extraction-volume-per-actor-trigger --wip`
  = **discriminated: YES** — reference PASS; empty, global-once,
  log-every-entry, log-on-beginplay all FAIL, each `[ok ]` (credited via its
  named substring). The 5-checkpoint out/re-in split behaved as designed:
  the re-entry begin-overlap fired on its own frame and log-every-entry died
  at the re-entry dedupe assert, not by coalescence luck.

# t1-extraction-volume-per-actor-trigger — requirements-table draft (checklist §7)

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span in the "Enforcing gate" column is a contiguous source
literal in
`UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/t1-extraction-volume-per-actor-trigger/ExtractionVolumeFunctionalTest.cpp`
(a `FinishTest(EFunctionalTestResult::Failed, ...)` message, cut before any
printf placeholder); get-away-column backticks may be hypothetical agent-side
examples (e.g. rows 3 and 5) and carry no grep contract. The L1 and sandbox rows cite the layer/manifest instead
because those gates have no FinishTest literal, and row 12 cites the task
spec's own front matter (`tasks/cpp/t1-extraction-volume-per-actor-trigger/task.md`).
Rows marked "(composed)" quote a runtime-composed message's SOURCE-side
fragment verbatim: the L1 target names are Python f-string compositions in
`tools/verify-single/layers/l1_build.py` (`f"{game_module}Editor"`), and the
registry's short-circuit note interpolates the failed dependency's key into
`short-circuited: ` at build time. Checkpoint schedule for
reference: cp0=0.5s (silence gate, then probe A enters), cp1=1.5s (first-entrant
gate, then A exits), cp2=2.0s (ungraded, A re-enters on its own frame),
cp3=2.5s (dedupe gate, then probe B enters), cp4=3.5s (second-entrant gate).
The GLog counter is installed in `OnWorldInitializedActors` (after
`PostInitializeComponents`, before placed-actor BeginPlay) and counts one match
per log record on `LogTemp` at `Display`-or-louder whose text CONTAINS
`CRAFTBENCH_EXTRACTION_OK`.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the placed zone actor stays discoverable as THE zone (tagged `ExtractionZone`, exactly one) | fully | resolve gate (PrepareTest) — `Expected exactly one actor tagged 'ExtractionZone' in the test level; found ` | unconditional (first graded gate; only a no-UWorld harness `::Error` precedes it) | nothing structural — the tag lives on the placed instance in the deny-listed map; a BeginPlay-time destroy, untag, or SECOND tagged spawn lands here (BeginPlay precedes PrepareTest). The lookup runs exactly ONCE in PrepareTest (`GetAllActorsWithTag`, cpp:89) and no gate re-resolves: a post-PrepareTest untag alone would PASS outright, a post-PrepareTest second tagged spawn is never rechecked, and a post-PrepareTest destroy fails at the checkpoint count gates, not here |
| 2 | "Solve in C++" — the edited class must compile (implicit) | fully | L1 layer — UnrealBuildTool must exit 0 for BOTH targets, composed at `tools/verify-single/layers/l1_build.py:273` as `f"{game_module}Editor"` plus the bare `game_module` (here CraftBenchTemplateEditor / CraftBenchTemplate); no FinishTest literal (layer verdict) (composed) | unconditional; when L1 fails, every L2 row below is emitted `status="skipped"` with the composed note `short-circuited: ` (`layers/registry.py:648-651`) (composed) | compiler WARNINGS of any kind and count — see row 15 |
| 3 | emit "the exact log line `CRAFTBENCH_EXTRACTION_OK`" | partially — matched as a SUBSTRING (`FCString::Strstr`), not a whole-line equality | first-entrant gate (cp1) — `emission after the first entrant; observed ` | the PrepareTest resolve/spawn gates already FinishTest'd, cp0 already FinishTest'd, or the cp0 probe-A move failed | any surrounding text on the line (`Zone 7: CRAFTBENCH_EXTRACTION_OK (A)` counts as the marker); the marker twice in ONE log record still counts once (forgiving, never inflating) |
| 4 | on the `LogTemp` category | fully — listener drops every record whose category != `LogTemp` before counting | same cp1 token as row 3 (a wrong-category marker counts 0, so the run dies at `emission after the first entrant; observed `) | the PrepareTest resolve/spawn gates or cp0 already FinishTest'd | nothing — a custom category is simply never counted |
| 5 | at `Display` verbosity or louder | fully — verbosity-mask floor: Fatal/Error/Warning/Display count, Log/Verbose/VeryVerbose are dropped | same cp1 token as row 3 (a too-quiet marker counts 0) | the PrepareTest resolve/spawn gates or cp0 already FinishTest'd | nothing — `UE_LOG(LogTemp, Log, ...)` is not counted and fails cp1 |
| 6 | "Before anything has entered the zone, it must not emit the line at all" | fully (from listener-install onward) | silence gate (cp0, t=0.5s, after BeginPlay) — `to NOT be logged before any entry; observed ` | the PrepareTest resolve/spawn gates already FinishTest'd | an emission from the actor's C++ CONSTRUCTOR (object construction during PIE world creation precedes the `OnWorldInitializedActors` listener install) is invisible to the counter — it escapes cp0, and contributes nothing at cp1, so a stray constructor-time line in the engine log goes ungraded |
| 7 | exactly once per distinct individual, "at the moment that individual first enters" (first entrant) | fully on the count (== 1); the MOMENT has ~1.0s latitude | first-entrant gate (cp1) — `emission after the first entrant; observed ` (count read BEFORE A is walked out, so an emit-on-EXIT handler reads 0 here and fails) | the PrepareTest resolve/spawn gates fired, cp0 failed, or the cp0 probe-A move failed | an emission deferred up to ~1.0s after the entry (e.g. a timer) is indistinguishable from "at the moment of entry"; anything slower than the cp0→cp1 window fails |
| 8 | "The same individual leaving and entering again must not produce another line" | fully | dedupe gate (cp3) — `re-entering to add no new emission (still exactly one); observed ` (A's exit at cp1 and re-entry at cp2 sit on separate engine frames, so the round trip can never coalesce away) | the PrepareTest resolve/spawn gates fired, cp0/cp1 failed, or any probe move (incl. cp2's ungraded re-entry move) failed | any dedupe key stable across the ~1s out/in round trip (raw pointer, actor name, weak ptr) passes equally; pointer reuse after actor destruction is not exercised |
| 9 | "Two different individuals must produce two lines, one each" | fully on the TOTAL (== 2); "one each" attribution is implied by rows 7+8, not separately observable | second-entrant gate (cp4) — `emissions after a second distinct individual entered; observed ` | the PrepareTest resolve/spawn gates fired, any earlier checkpoint failed, or the cp3 probe-B move failed | grading ends at t=3.5s — a third/fourth line emitted AFTER cp4 (e.g. a slow timer loop) is never seen; total-count grading cannot tell "one from A + one from B" apart from "two from B" if some exotic path produced that split while still passing cp1/cp3 |
| 10 | "whenever ANY other actor enters" (entrant genericity) | partially — exercised with exactly two bare `AActor`s carrying query-only overlap spheres | rows 7/9 tokens (`emission after the first entrant; observed ` / `emissions after a second distinct individual entered; observed `) | as rows 7/9 | class/type filtering that happens to ACCEPT a bare component-only AActor (e.g. a handler that ignores Pawns/Characters, or requires only a primitive root) passes; "any" is sampled at two points, not proven |
| 11 | the box-shaped detection volume keeps detecting (scaffold geometry survives the edit) | partially — geometry sampled at 2 interior points (±60 units off center) and 2 far parking spots (~5000 units, ±250) | rows 6/7 tokens: an oversized volume that reaches the parking spots trips `to NOT be logged before any entry; observed ` at cp0; a shrunken/disabled one reads 0 at `emission after the first entrant; observed ` | as rows 6/7 | any detection shape (box or not) covering the two entry points but not the parking spots passes — "box-shaped" itself is never asserted (no structural lane), and resizing within [covers ±60, misses ~5000] is free |
| 12 | "do not create a Blueprint subclass" / "Solve in C++ on the existing class" | **NOT ASSERTED** | none — the spec front matter declares `layers: [L1, L2]` (`tasks/cpp/t1-extraction-volume-per-actor-trigger/task.md`, front-matter block); no L2I/structural lane exists on this task, and L2 identifies by tag precisely so a subclass would ALSO pass (Hard Rule #2) | — | shipping a stray Blueprint subclass `.uasset` under an `asset_writable` prefix (`Content/Tasks/`, `Content/Blueprints/`, ...) alongside a working C++ fix: sandbox-accepted, verdict unaffected. Behaviorally inert (the graded instance is the placed C++ actor and the map is deny-listed), so the prohibition is enforceable only by trajectory review, not by any gate |
| 13 | "do not edit the level" | fully, by the substrate model | not an L2 gate — `Content/Maps/` is an explicit `deny` prefix in `UE-projects/CraftBenchTemplate/AGENT_WRITABLE.json`; a submission touching the map exits 4 SANDBOX-REJECT before any layer runs | unconditional (sandbox precedes grading) | nothing — deny wins over every allowlist, including `asset_writable` |
| 14 | "do not edit any test file" | fully, by the substrate model | not an L2 gate — `Source/CraftBenchTests/` is a `deny` prefix (exit 4 on submission); independently, the runner materializes the graded substrate from git HEAD, so an on-disk fixture edit never reaches the grade, and human review gates committed changes | unconditional | nothing that reaches a graded verdict |
| 15 | (Verifier-spec claim, not in the agent prompt) "no new shadowed-variable / deprecated-declarations warnings" in the agent files | **NOT ASSERTED** on the default grading path | none by default — L1 counts agent-file warnings (`l1_build.py::_count_warnings`) but the verdict only consumes the count under the opt-in `--strict-warnings` flag (`layers/registry.py:100`), which no default run/refgate/discriminate invocation passes; even when on, it is an any-warning COUNT, not the category-pinned DIFF the spec text promises | — | unlimited C4458/C4996 (or any other) warnings in `ExtractionZoneActor.{h,cpp}` grade PASS; the task.md L1 block over-claims its gate |

Accepted-residual candidates the table surfaces (for the escalation list, not
for silent papering-over): rows 12 and 15 are the two genuine holes; rows 3,
6, 7, 9, 10, 11 document deliberate behavioral latitude consistent with
Hard Rule #2 (behavior-only grading) and are disclosure, not defects.
