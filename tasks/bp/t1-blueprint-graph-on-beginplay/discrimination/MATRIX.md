# Discrimination matrix — t1-blueprint-graph-on-beginplay

Verdicts are from the DETERMINISTIC verifier (no agent, no tokens). Run with
`cb discriminate --task bp/t1-blueprint-graph-on-beginplay --wip` until the
fixture/map are committed (the runner grades from git HEAD).

Design: **L1 + L2 only.** The fixture loads the one deliverable by its required
path `/Game/Tasks/t1-blueprint-graph-on-beginplay/BP_GraphMath`, checks its
parent class, spawns it into the not-yet-begun PIE world, overrides both
editable values (137/42) **before BeginPlay**, and asserts the exact line
`CRAFTBENCH_GRAPH_TOTAL=179` is logged exactly once. No asset scan, no L2I,
no tags.

Per the amended checklist §7 (owner decision 2026-08-11) this package ships
**no hand-authored gaming variants**: the automatic reference-PASS / empty-FAIL
legs provide the non-vacuity bit, and the **requirements table** below is the
mandatory soundness artifact. A variant is owed only if a table row exposes a
requirement whose defense turns out not to exist — none does.

> **STATUS: RUNNABLE (reference leg PROVEN).** reference graph wired via the MCP graph tools, compiles clean, refgated PASS from git HEAD (125 s, 2026-08-12).
> Remaining before full certification: the empty-FAIL leg and the
> requirements-table spot checks ride the next `cb discriminate` run.

## Parser traps this matrix is written against

- **ONE parseable row-table.** `discriminate.parse_matrix` keys on the
  submission-row table; the requirements table below deliberately names none
  of its columns "substring" or "message" and its first cells are requirement
  prose, so the parser skips it.
- **Every expected-message cell is a backtick-wrapped literal containing a
  space or `=`**, matched against the L2 log.
- **Every cell below is a verbatim contiguous span of ONE quoted string
  segment** in `UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/t1-blueprint-graph-on-beginplay/GraphMathFunctionalTest.cpp`
  — never a span crossing a printf placeholder or an adjacent-literal seam
  (the fixture's multi-line `TEXT("..." "...")` strings are seamed; each cell
  was checked against the single segment it lives in).
- **ASCII rule:** all fixture assertion strings and all cells here are
  ASCII-only (UE's UTF-8 log read back as cp1252 turns anything else into
  mojibake and the grep misses).

## Matrix

**This is the only table in this file that carries submission rows.**

| Submission | Overall | Fails at | Expected message |
|------------|---------|----------|------------------|
| `../reference` | **PASS** | — | BP_GraphMath BeginPlay reads 137+42 and prints once; all gates green (L1 ok, L2 exact count==1, prefix count==1) |
| empty (no overlay -> base scaffold, no BP at the path) | **FAIL** | L2 PrepareTest | `No Actor Blueprint found at the required path` |
| `hardcoded-default/` (BP prints constant `CRAFTBENCH_GRAPH_TOTAL=12`) | **FAIL (PREDICTED)** — UNAUTHORED, absent from disk | L2 cp0 | `the printed total does not reflect the` |
| `wrong-parent/` (plain-Actor BP at the path with its own variables) | **FAIL (PREDICTED)** — UNAUTHORED, absent from disk | L2 PrepareTest | `does not derive from the task actor type` |
| `silent-graph/` (BP subclass with an empty graph) | **FAIL (PREDICTED)** — UNAUTHORED, absent from disk | L2 cp0 | `observed none - the graph did not` |
| `tick-print/` (BP prints the correct line every Tick) | **FAIL (PREDICTED)** — UNAUTHORED, absent from disk | L2 cp0 | `must be printed exactly once` |

## Coverage bounded (stated honestly, not silently)

- The `hardcoded-default/`, `wrong-parent/`, `silent-graph/`, and `tick-print/`
  rows require authoring Blueprint `.uasset` binaries in a UE 5.8 editor; per
  the §7 amendment they are NOT materialized as variant dirs — they are
  documented rows whose defenses are pinned by the requirements table below.
  `reference` and `empty` are the graded legs (`cb discriminate` runs both
  automatically).
- **`empty` and a C++-only submission fail at the SAME point** (load-by-path
  returns null) with the same named message. Correct and intended: neither
  produces a `.uasset` at the required path.

## Requirements table (checklist §7, the mandatory soundness artifact)

One row per requirement in the agent-visible prompt. Every backticked span in
the *verbatim token* column is a contiguous span of one quoted segment in
`GraphMathFunctionalTest.cpp` (file:line anchors at authoring time; the named
setup-status / checkpoint branch is the durable join key if lines drift).

| # | Prompt requirement | Asserted | Enforcing check — verbatim token (file:line) | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | an Actor Blueprint asset saved at `Content/Tasks/t1-blueprint-graph-on-beginplay/BP_GraphMath` | fully | PrepareTest AssetMissing branch — `No Actor Blueprint found at the required path` (GraphMathFunctionalTest.cpp:203) | unconditional (first L2 gate) | nothing — every later gate sits behind this load |
| 2 | based on the provided `GraphMathActor` type | fully | PrepareTest WrongParent branch — `does not derive from the task actor type` (:211) | asset missing (row 1 fans out) | any *deeper* subclass chain (e.g. via an agent C++ intermediate) passes `IsChildOf` — accepted, see task residuals |
| 3 | prints when gameplay begins for the instance | fully | cp0 Prefix==0 branch — `observed none - the graph did not` (:245) | rows 1-2 already FinishTest'd (test never reaches cp0) | a print later than BeginPlay but before the 0.3 s checkpoint window closes — accepted: "at start of play" is graded as the pre-checkpoint window, same as t0 |
| 4 | printed total = sum of the instance's CURRENT values (not the defaults) | fully | cp0 Exact==0 branch — `the printed total does not reflect the` (:256); override applied pre-BeginPlay at SetupSubject (:148-149, deferred-spawn fallback :161-162) with the fixture's compile-time sum check at :47 (not a runtime literal; kept out of backticks so the verbatim-token invariant stays about printable spans) | no marker line at all (row 3's branch fires instead) | hardcoding 179 after reading the fixture source in scratch — the suite-wide readable-verifier residual, stated in task.md |
| 5 | exact line format `CRAFTBENCH_GRAPH_TOTAL=<total>`, no deviations | fully | the exact-line counter only matches `CRAFTBENCH_GRAPH_TOTAL=179` (:40); any format drift lands in row 4's branch (prefix hit, exact miss) or row 3's (prefix miss) | rows 1-2 fan out | leading/trailing text on the SAME log line around the exact substring survives (substring match, and Print String prepends its instance prefix by design) — accepted, disclosed as "line contains" semantics |
| 6 | printed exactly once, nothing further afterwards | fully | cp0 else branch — `must be printed exactly once` (:265) | rows 1-3 fan out | a second print *after* the 0.3 s checkpoint would escape — accepted at T1: the fixture windows "nothing further" to the checkpoint horizon (same accepted bound as t0's single checkpoint) |
| 7 | compiles cleanly / project still builds | fully | L1: UBT exit 0 for both targets (runner layer, not fixture source) | never (L1 precedes L2) | an asset that loads but carries non-fatal BP warnings — accepted, L1 gates build + package load only |
| 8 | print goes to the screen and the engine log | partially | log side: the GLog device on LogBlueprintUserMessages (:34, installed :96); screen side: NOT asserted | headless `-nullrhi` has no screen | disabling print-to-screen while keeping print-to-log — accepted residual, stated in task.md ("to the screen" is unobservable headless) |

Every prompt requirement has an enforcing gate or an explicitly stated accepted
residual — nothing is unenforced prose — so no targeted variant is owed under
§7. Rows 3, 5, 6, 8 are honest about being window- or channel-bounded; each
bound is disclosed in the task spec rather than left implicit.

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task bp/t1-blueprint-graph-on-beginplay --wip
```

Per-leg fallback while iterating (short `--workdir` dodges Windows MAX_PATH):

```sh
py tools/verify-single/run_task.py \
    --task tasks/bp/t1-blueprint-graph-on-beginplay/task.md \
    --submission tasks/bp/t1-blueprint-graph-on-beginplay/reference \
    --ue-root <UE_ROOT> --workdir C:\cb\wd\graphmath      # expect exit 0
```

## Status

- Authored 2026-08-11, text-only track. **The reference leg HAS been executed**
  and passes: refgate PASS from git HEAD (125 s, 2026-08-12), re-confirmed in the
  62/62 `cb refgate --all` sweep of 2026-08-17. The map and reference binary do
  exist.
  *(Corrected 2026-08-17: this block previously read "**Never executed** — no map
  or reference binary exists yet", contradicting the STATUS line at the top of
  this same file. The stale half is the one that said nothing exists; it predates
  the authoring-lane run and was never updated when the reference landed.)*
- **What has still never run: the four variant legs.** They are documented rows,
  not directories — each is now marked `FAIL (PREDICTED)` in the matrix above so
  the table cannot be misread as measured. Authoring them needs Blueprint
  `.uasset` binaries built in a UE 5.8 editor.
- Substring cells were statically verified against the fixture source (each is
  a contiguous span of a single quoted segment; grep confirms).
- Calibration TODOs (checkpoint timing margin, Print String int formatting,
  spawn-during-world-init legality) are listed in `../notes.md`. The reference
  PASS resolves them for the reference path; they remain open for any variant
  authored later.
