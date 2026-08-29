# gp-crafting-queue — discrimination matrix

**Status (2026-08-17):** package AUTHORED this session, the task's first. It previously had
**no `discrimination/` directory at all** — the dossier verdict was `NO-EVIDENCE`. Four
one-delta variant legs are rowed below; each is a byte-exact copy of `../reference` carrying
a single behavioural change, and each "fails at" cell is a **gate-order trace** against
`UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/gp-crafting-queue/CraftingQueueFunctionalTest.cpp`, not
a measurement. Nothing here may be read as measured until a `cb discriminate` result is
recorded in this file.

**How the legs isolate, given ONE failure literal.** This fixture has a single
`FinishTest(…Failed…)` call, reused at all five checkpoints — so a naive package would be
five legs sharing one substring, proving nothing about *which* requirement failed. The
expected count is fixed by the **checkpoint index**, never by the submission, so the
rendered `expected exactly N` isolates the gate exactly. The five legs below fail at four
distinct checkpoints with five pairwise-disjoint rendered substrings.

| Submission | Overall | Fails at | Expected message substring | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | **PASS** | — | all 5 checkpoints green (1/1) | — (PASS oracle) |
| empty (no overlay → scaffold stub) | **FAIL** | checkpoint 1 (t=1.5s) | `FIFO); found 0.` | FR-017 empty. The stub has no `BeginPlay`, so nothing is ever queued. Note it **passes checkpoint 0** — 0 completions is correct at t=0.5s — so the empty leg here is not a first-gate trip |
| `burst-all-at-once/` | **FAIL** | checkpoint 0 (t=0.5s) | `expected exactly 0 'CraftCompleted'` | #1 burst-complete in BeginPlay. AUTHORED 2026-08-17, NOT YET RUN. One delta: `BeginPlay` drains the queue in a `while` loop instead of arming the timer. Every action IS processed, in correct FIFO order, and the final tally IS four — **only the pacing is missing**, and it fails the very first checkpoint at 4-vs-0 |
| `over-spawn-two-per-craft/` | **FAIL** | checkpoint 1 (t=1.5s) | `FIFO); found 2.` | #4 over-spawn per completion. AUTHORED 2026-08-17, NOT YET RUN. One delta: two markers are spawned per completed action instead of one. Pacing, FIFO order and the drain are all correct, and checkpoint 0 passes verbatim. **Pairs with the `empty` leg at the same checkpoint to prove the count gate is exact in BOTH directions** — too-few (0) and too-many (2). No `empty` leg can reach the too-many side |
| `stalls-after-first/` | **FAIL** | checkpoint 2 (t=2.5s) | `expected exactly 2 'CraftCompleted'` | #3 stall mid-queue, *early* half. AUTHORED 2026-08-17, NOT YET RUN. One delta: `bLoop=false`, a one-shot timer never rescheduled, so exactly one action ever completes. Checkpoints 0 and 1 are indistinguishable from the reference (0 then 1) |
| `drops-the-last/` | **FAIL** | checkpoint 4 (t=4.5s) | `expected exactly 4 'CraftCompleted'` | #3 stall mid-queue, *late* half — the "count must keep climbing to 4" clause. AUTHORED 2026-08-17, NOT YET RUN. One delta: an off-by-one drain condition (`<= 1` for `== 0`) clears the timer while one action still remains. **Passes checkpoints 0–3 verbatim** — the subtlest leg in the package, and the only one that reaches the final checkpoint |

## Requirements table (checklist §7, the mandatory soundness artifact)

The single failure literal is
`At t=%.2fs: expected exactly %d 'CraftCompleted' marker actor(s) (one craft completed per second, FIFO); found %d.`
Layers are `[L1, L2]`. The schedule is sequential and any `FinishTest` ends the run, so
**every later gate is skipped once an earlier one fires**. "cp*N*" below means the count
gate at that checkpoint index, whose expected value is `ExpectedCounts[N]` = 0,1,2,3,4.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the placed actor stays discoverable (exactly one) | fully | resolve gate (`PrepareTest`) — `Expected exactly one actor tagged 'CraftQueueRoot' in the test level; found ` | unconditional (first gate) | nothing at authoring time — the tag is on the placed instance in the verifier-owned map |
| 2 | queue **exactly four** crafting actions | partially — by consequence only | cp4 — `expected exactly 4 'CraftCompleted'` (the tally must reach 4) plus cp0–cp3 (it must not exceed the running count) | row 1, any earlier checkpoint | the QUEUE is never inspected; only completions are counted. A submission with no queue data structure at all — four hard-coded timed spawns — satisfies every gate. "Queue" is a mechanism the verifier cannot see |
| 3 | each action is a **named string** | **NOT ASSERTED** | — (the marker is a bare `AActor` carrying only a tag; no gate reads any action name) | — | **HOLE**: four empty strings, or no strings at all, pass. The prompt's "each action is just a string name" is decorative under this fixture |
| 4 | process **in the order they were queued** (FIFO) | **NOT ASSERTED** | — (markers are mutually indistinguishable: same class, same tag, same location, no ordinal) | — | **HOLE, and the prompt's most emphasised clause**: reverse order, or shuffled order, produces a byte-identical observable. The word "FIFO" appears *inside the failure message* but nothing tests it. Closing it needs per-marker identity (e.g. the action name in the marker's tag or name) — a fixture change, not a variant |
| 5 | process **strictly one at a time**; never begin the next until the current finishes | partially — weakly | the 0→1→2→3→4 sequence across cp0–cp4 rejects bunching in either direction | row 1 | **HOLE (see escalation)**: four *pre-scheduled staggered* timers, all armed at `BeginPlay` for 1s/2s/3s/4s, are concurrent by the prompt's definition yet produce exactly the required sequence. The gate sees completion *timing*, never mutual exclusion |
| 6 | each action takes **about one second** | fully at the tested points | the checkpoint schedule itself (0.5/1.5/2.5/3.5/4.5s midpoints) — every cell of `expected exactly N` | row 1 | ±0.5s of drift per completion is invisible; a 0.6s or 1.4s craft duration still reads correctly at the midpoints. Deliberate calibration slack |
| 7 | **one** marker actor per completion | fully, both directions | cp1 in the too-many direction (`FIFO); found 2.`) and cp1–cp4 in the too-few direction | row 1, cp0 | — (this is the requirement `over-spawn-two-per-craft/` and `empty` jointly prove is gated) |
| 8 | the marker carries the tag `CraftCompleted` | fully, structurally | not a separate gate — the tag IS the counting mechanism (`GetAllActorsWithTag`), so an untagged marker is invisible and reads as a shortfall | row 1 | tagging something that is not a completion marker is not distinguished |
| 9 | must **not** finish them all instantly / several at once | fully | cp0 — `expected exactly 0 'CraftCompleted'` (nothing may have completed at t=0.5s) | row 1 (first count gate) | — (this is the requirement `burst-all-at-once/` proves is gated) |
| 10 | markers are spawned **into the world** (world-observable) | fully, structurally | the same `GetAllActorsWithTag` sweep — an object that is not a spawned world actor is not counted | row 1 | the marker's class, mesh and location are never read; "small" is unasserted and correctly non-load-bearing |
| 11 | solve in C++ on the existing class | fully, by L1 + the substrate model | not a `FinishTest` gate — the committed map places the C++ `ACraftQueueActor`, so logic in a never-placed Blueprint subclass never executes, and the L1 dual-target build must exit 0 | unconditional | private helpers/members in the header are free; subclassing is tolerated by design (identity is by tag) |

### Escalation notes (holes the table found)

- **Row 4 (FIFO order) is entirely ungated, and it is the clause the prompt states most
  forcefully.** No variant can probe it: a variant proves a *gate* catches a defect, and
  there is no gate. The cheap sound fix is per-marker identity — have the marker carry the
  completed action's name (as a second tag or its actor name) and assert the sequence. That
  is a fixture + prompt change and is filed as such, not smuggled in here.
- **Row 5: anti-gaming note 5 in `task.md` OVERCLAIMS, and the requirements table is what
  found it.** The note asserts the +1-per-second sequence "is only satisfiable by sequential
  one-at-a-time completion". It is not: a submission that arms four independent timers at
  `BeginPlay` (1s, 2s, 3s, 4s) begins all four actions at t=0 — precisely the "parallel
  processing" the note claims to reject — and reproduces the required observable exactly.
  **This must not be authored as a discrimination variant**, because it would PASS and be
  recorded as a `[BAD]` leg. It is a gaming demonstration, and the correct place for it is
  the note's own text, which should be narrowed to what the fixture can actually see
  (completion *pacing*), or the fixture given a mutual-exclusion observable.
- Row 3 (action names) is a smaller instance of the same shape as row 4: the deliverable
  the prompt describes is richer than the observable the fixture reads.
- **cp3 (expected 3) has no leg.** Its gate is exercised — `drops-the-last/` passes through
  it — but no authored submission fails *at* it. Any defect that first diverges at the
  fourth checkpoint would be caught by the same literal; the gap is in the evidence, not
  the gate.

## Bounded coverage (honest note)

Reference (PASS) and empty (FAIL) have both been graded through the deterministic verifier
as part of `cb refgate`. The four variant legs are **authored, not yet run**. Of the spec's
five anti-gaming notes, #1, #3 (both halves) and #4 now have committed one-delta variants.
Note #2 (process too fast) fails at cp1 exactly as `over-spawn-two-per-craft/` does and adds
no new substring or checkpoint. **Note #5 is not merely uncovered but partly wrong** — see
the escalation note above; that is the most important thing this package produced.
