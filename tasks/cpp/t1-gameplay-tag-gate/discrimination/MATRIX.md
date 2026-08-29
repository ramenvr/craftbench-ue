# Discrimination matrix — t1-gameplay-tag-gate

Fixture: `UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/t1-gameplay-tag-gate/TagGateFunctionalTest.cpp`
(all `file:line` cells below refer to it). Run:
`cb discriminate --task cpp/t1-gameplay-tag-gate [--wip]`.

Every backticked expected-substring in this file is a verbatim literal inside
ONE string literal of the fixture source (never spanning a printf placeholder)
— the oracle greps statically.

## Requirements table (section-7a soundness artifact)

One row per requirement in the agent-visible prompt. "Skip condition" names
the only way the gate does not execute; "unconditional" means it runs on every
graded L2 leg that reaches PIE.

| # | Prompt requirement | Asserted | Check / named assertion | Skip condition | What a submission could get away with |
|---|---|---|---|---|---|
| R1 | Marker present at gameplay start + line every 0.5 s while present, first within 0.6 s | fully | cp0 two-sided band `3 <= Count <= 4` at t=1.8s — line 210-212, `expected 3-4 CRAFTBENCH_TAG_GATE_TICK emissions while the marker is present` | unconditional (first checkpoint; runs unless a prepare-time named FAIL already ended the test) | first line anywhere in [0, 0.6] and phase jitter inside the window (counts, not timestamps, are gated) |
| R2 | Exact line `CRAFTBENCH_TAG_GATE_TICK` on `LogTemp` at `Display`+ | fully | listener filter (category `LogTemp`, verbosity floor Display, exact substring) — `FTagGateTickCounterDevice::Serialize`, lines 33-51; a wrong token/channel counts 0 and R1's gate fires | unconditional (device installed pre-BeginPlay via `OnWorldInitializedActors`) | extra unrelated log lines (only the token is counted) |
| R3 | Lines STOP while the marker is absent | fully | cp1 `NewSinceStop == 0` at t=3.6s after the fixture's reflection call to `RemoveGateTag` at t=1.8s — line 229-231, `expected no further emissions after the marker was removed` | skipped only when an earlier checkpoint/prepare gate already `FinishTest`'d (that run is already a FAIL) | nothing within the window; a single in-flight emission would FAIL (band is exactly 0) |
| R4 | Lines RESUME within 0.6 s of re-add, same period | fully | cp2 two-sided band `2 <= NewSinceResume <= 4` at t=5.4s after the fixture's `AddGateTag` call at t=3.6s — line 248-250, `expected the emissions to resume after the marker was re-added` | skipped only when an earlier gate already `FinishTest`'d | resume latency up to ~0.9s would still land 2 emissions (band floor is 2, one below the computed legit minimum of 3) |
| R5 | Accessor functions keep their names + single-marker signature | fully | prepare-time reflection checks — lines 151-176: `is missing the required accessor function` / `has an unexpected parameter layout` (`NumParms == 1 && ParmsSize == sizeof(FGameplayTag)`) | unconditional | a signature-compatible body that ignores its argument (caught behaviorally by R3/R4 instead) |
| R6 | Exactly one placed marker-set actor (workspace invariant) | fully | prepare-time `Found.Num() != 1` — line 107, `Expected exactly one TagGateRoot-tagged actor` | unconditional | — |
| R7 | Marker name `CraftBench.TagGate.Active` resolvable | fully | prepare-time `GateTag.IsValid()` — line 122, `is not registered with the tag system` (submission deleted/renamed the scaffold's native definition) | unconditional | — |
| R8 | "Do not edit any test file / the level" | fully (harness, not fixture) | sandbox: `Source/CraftBenchTests/` and `Content/Maps/` outside `AGENT_WRITABLE.json`'s writable set (exit-4 reject); grading materializes from git HEAD | unconditional | — |
| R9 | "Solve in C++ / no Blueprint subclass" | structurally | the graded instance is the PLACED scaffold-class actor in the committed map; a Blueprint subclass asset is never instantiated by the fixture, and the C++ accessors it inherits would not reach BP-side state | unconditional (structural, no explicit assertion) | agent may ALSO author unused BP assets; harmless |
| R10 | workspace invariant: the placed host actor keeps existing for the whole run (kin of R6 — a submission must not destroy it) | fully | per-checkpoint host null-check — `The TagGateRoot host actor is no longer present at a checkpoint.` | unconditional | review catch 2026-08-11: this row was missing, and its sibling null-host branch inside the accessor resolver was UNREACHABLE dead code — that branch is deleted (a fail literal that can never fire is exactly what a re-anchor pass would hunt for); fixture line anchors below :155 shifted by -2 and are re-anchored in the authoring-lane pass |

Requirements with no assertion: none. Known partial/residual coverage
(fixture readable in scratch; container type unasserted; single-framerate;
counts-not-timestamps) is recorded under **Hidden invariants** in `task.md` —
each is an accepted residual, not an unenforced prompt requirement, so no
targeted variant is authored (per the 2026-08-11 §7 amendment: variants only
for holes this table actually found).

## Submission rows

| Submission | Verdict | Fails at | Expected message substring | Requirement row |
|---|---|---|---|---|
| `../reference` | PASS | — | — | — |
| empty | FAIL | cp0 (t=1.8s) | `expected 3-4 CRAFTBENCH_TAG_GATE_TICK emissions while the marker is present` | R1 (stub accessors + no timer emit nothing; count 0) |
| `unconditional-emission/` | FAIL | cp1 (t=3.6s) | `expected no further emissions after the marker was removed` | R3. Anti-gaming note #1 (marker ignored): the 0.5 s timer emits on every fire and never queries the marker set. Gate order: both prepare-time accessor checks pass (the accessors still mutate the container) and cp0 passes (3 emissions by t=1.8s, inside the 3-4 band), so cp1 is the FIRST gate that can fire - it observes 4 new lines against a band of exactly 0. |
| `stops-forever-on-remove/` | FAIL | cp2 (t=5.4s) | `expected the emissions to resume after the marker was re-added` | R4. Anti-gaming note #4 (the stop-forever hack): the HasTag gate is intact, but `RemoveGateTag` also clears the looping timer and `AddGateTag` re-adds only the marker, so nothing restarts it. Gate order: prepare passes, cp0 passes (3 emissions), and cp1 passes for the RIGHT reason (0 new after the removal), so cp2 is the FIRST gate that can fire - it observes 0 new against the 2-4 resume band. |

Two hand-authored variants (added 2026-08-17). The requirements table found no
*unasserted* requirement, so these do not close a coverage hole - they close the
non-vacuity gap the reference/empty pair alone leaves: one leg shows a gate
FIRES, not that the package cannot be gamed. They deliberately sit on the two
OPPOSITE sides of the conditional behavior this task is about - R3
(stop-on-remove, cp1) and R4 (resume-on-re-add, cp2) - so the pair proves the
two halves of the gate are independently live rather than crediting one gate
twice. Neither is entailed by `empty`, whose run dies at cp0 before either
literal can print.

Notes:
- **Variant gate order is traced, not assumed.** Each variant is a copy of
  `../reference` with exactly ONE behavioral delta (the `.h` files are
  byte-identical to the reference's; the `.cpp` diff is one construct plus the
  variant's own header comment). Both keep the accessor names/signatures and the
  native marker definition, so no prepare-time gate can pre-empt the checkpoint
  the row names, and both keep the 0.5 s period so cp0's two-sided band passes.
  `unconditional-emission/` therefore first meets cp1 and
  `stops-forever-on-remove/` first meets cp2 - no leg can be credited
  `wrong-reason`. The sharpest form of that argument: NEITHER delta is
  reachable before t=1.8s (one is a dropped `HasTag` query on a timer whose
  schedule is unchanged, the other lives in `RemoveGateTag`, which the
  fixture does not call until cp0 has already passed), so both legs present
  cp0 with exactly the emission count the refgate-PASS reference presents.
- **Each variant's log carries only ITS literal.** A checkpoint that passes
  prints no `FinishTest(Failed, ...)` message at all, so
  `unconditional-emission/`'s log cannot contain the cp0 or cp2 literal and
  `stops-forever-on-remove/`'s cannot contain the cp0 or cp1 literal. The raw
  emitted line (`CRAFTBENCH_TAG_GATE_TICK`, which both variants still print)
  contains none of the credited spans - each one is fixture prose.
- **Substring disjointness:** the three checkpoint failure fragments
  (`while the marker is present` / `after the marker was removed` /
  `resume after the marker was re-added`) and the four prepare-time fragments
  share no containing substring, so a FAIL can never be credited to the wrong
  gate by the grep.
- **ASCII rule:** every `FinishTest` literal in the fixture is ASCII-only (the
  UE log's UTF-8 read back as cp1252 turns an em dash into mojibake and the
  grep misses — t2-homing-projectile lesson).
- Checkpoint times (1.8 / 3.6 / 5.4) sit mid-interval against the 0.5 s
  period, so no legitimate implementation races a checkpoint against a
  scheduled emission at the deterministic 60 FPS step.

## Status

- **Variants authored 2026-08-17** (`unconditional-emission/`,
  `stops-forever-on-remove/`) - byte-derived from `../reference` (ASCII + CRLF,
  one delta each). NOT YET EXECUTED: both rows' substrings are statically
  verbatim spans of the fixture's cp1 / cp2 `FinishTest(Failed, ...)` literals
  (neither crosses the trailing `%d`), and the gate-order claim above is a
  source trace; only a real `cb discriminate --task cpp/t1-gameplay-tag-gate`
  run upgrades either to evidence. Execution-time checks: the cp1 leg should
  report `observed 4 new` (3.5s emission included; >= 1 suffices) and the cp2
  leg `observed 0 new`.
- Authored 2026-08-11 from the spec + fixture source (line anchors current as
  of authoring; re-anchor if the fixture is edited).
- **UPDATE 2026-08-11: the map binary IS committed** (authoring-lane run 1,
  commit 39433c2) and `cb refgate cpp/t1-gameplay-tag-gate` graded the
  committed C++ reference **PASS from git HEAD (114 s)**. The empty-FAIL leg
  and the variant expectations above still ride the next
  `cb discriminate --task cpp/t1-gameplay-tag-gate` run.
