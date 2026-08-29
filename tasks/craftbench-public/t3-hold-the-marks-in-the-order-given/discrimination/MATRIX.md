# Discrimination matrix — t3-hold-the-marks-in-the-order-given

The self-validation oracle: the reference must PASS, and the empty leg must FAIL
**at the predicted gate, via the named substring**. A wrong-reason FAIL (an L1
build failure, a different gate, `SANDBOX-REJECT` exit 4, `HARNESS-PRECONDITION`
exit 7) means the gates are NOT discriminated — fix them, or relabel the task for
the weaker property it actually tests.

> **EVERYTHING IN THIS FILE IS PREDICTED. NOTHING HAS BEEN BUILT AND NOTHING HAS
> BEEN RUN.** No UBT invocation, no PIE leg, no `cb discriminate`. Every verdict,
> every substring, every time and every gate ordering below is derived by reading
> `MarkOrderFunctionalTest.cpp` against the reference and against the empty
> scaffold — it is an argument, not a measurement. Three tasks are already in this
> tree whose MATRIX claims a PASS the run does not give; treat every row here as
> a claim to be checked, and overwrite the Status section with what actually
> happened the first time it runs.

**REFERENCE + EMPTY ONLY**, per the owner directive of 2026-08-18: discrimination
is those two legs, and the thirteen per-checkpoint named gates carry the rest. No
variant legs are authored. The wrong answers this task is built against are
listed at the bottom, each against the gate that names it, so that anybody who
wants to prove one later knows where to look.

## Three parser rules this file is written against

- **One parseable row per label.** `parse_matrix` returns
  `Dict[label -> MatrixRow]`, so a second table repeating a label silently
  overwrites the first. There are **two** pipe tables in this file — the
  discrimination table immediately below and the mandatory requirements table
  further down — and `parse_matrix` reads BOTH. Only the first mints rows; the
  requirements table is worded so that none of its first cells can classify
  (checked: parsing this file yields exactly `reference` and `empty`).
  Everything else is prose or a bullet list, deliberately.
- **A variant cell must contain a `/`.** A row is only classified as a variant
  when the first cell matches `` `?([A-Za-z0-9_-]+)/`? `` and `"/" in first`
  (`discriminate.py:284-286`). This task ships no variants, so the rule is
  recorded rather than defended — but it is also why the wrong-answer list below
  is a bullet list and why the requirements table's first column carries no
  slash. **This is a live defect elsewhere in this set:** six sibling MATRIX
  files word a requirement as "C++ under `Source/ThirdPerson/`" in a first cell
  and thereby mint a phantom variant leg called `Source`, which `cb discriminate`
  then looks for on disk.
- **A backticked substring must (a) contain a space or one of `(),.=` and
  (b) fall inside ONE literal run of the fixture's format string** — no `%`
  placeholder may appear inside it. The one substring below was checked against
  the source: `MarkOrderFunctionalTest.cpp:1855` opens
  `TEXT("TheBoardShowsHowFarYouGot: at t=%.2f s the board's tally face has "…`,
  so `TheBoardShowsHowFarYouGot: at t=` is the contiguous run that precedes the
  first placeholder. ASCII-only, contains spaces and `=`.

| Submission | Expected verdict | Expected substring | Which gate fires, and why it is that one |
|---|---|---|---|
| `../reference` | PASS (**predicted**) | — (a PASS row carries no substring; `discriminate.py` skips extraction on it) | All thirteen gates green, and the run ends on `FinishTest(Succeeded, …)` whose text opens `The hall held the marks in the order given: two full rounds on lists of …`. The reference banks in a `TMap` keyed by mark name that is never cleared on exit, wipes the whole hall on the ring-entry EDGE for **either** direction of the out-of-turn rule (`Idx != TurnIndex`, so a name later in the list counts as much as one already finished), poisons the stand it interrupts, tests completion as a **separate per-frame step** against the number read at that instant (so a drop below an already-banked value finishes a mark with nobody standing anywhere), restarts on a list replacement detected by an **ordered** array comparison (`LastSeenList != ListedMarkNames`, so a same-length reorder is caught), and repaints all five faces, all five lamps and the tally every frame from one place. **The reference source is UNCHANGED by the 2026-08-19 hardening** — all three newly-gated branches were already satisfied by it; what changed is that the drive now exercises them. **Predicted world time ≈ 285 s**, inside the 400 s sentinel and the `TimeLimit` the base class derives from the schedule. |
| `empty` | FAIL (**predicted**) | `TheBoardShowsHowFarYouGot: at t=` | The unmodified scaffold **compiles** — the rings, the faces, the lamps, the ring predicate and both display calls are supplied and working — so L1 is green and the failure is behavioural. `ADutyBoardActor` ships `bTallyEverWritten = false` and a blank tally face; the drive parks the character clear of every ring and arms the gates at the **baseline** step, where `GateBoardTally` runs FIRST by the precedence table. `ReadTally` returns false and the gate fails on its never-written clause. **Predicted t ≈ 4.5 s** — the earliest, cheapest named FAIL in the task. |

## Why the empty leg fails at the baseline, and at THAT gate

Worth stating, because a reader could reasonably guess three other gates. Walked
in the order `Tick` evaluates them, for the inert scaffold:

- `GateHallNotRewired` runs every frame from the first, **before** `bGatesArmed`.
  It passes: an empty submission rewrites nothing, so every mark's name, seconds,
  ring and location still match what `PrepareTest` staged and the board still
  carries the staged list. (This is corpus defect DEF-5 — a gate that passes
  trivially for an empty delivery — and it is acceptable *only* because the
  CraftBench verdict is binary, so it inflates no denominator. Do not translate
  this gate list into a scored k/N rubric without re-auditing it.)
- Step 0 (walk to the parking spot) is ungated on purpose: the character may
  spawn anywhere and `bGatesArmed` is still false.
- `BeginStep(1)` sets `bGatesArmed` and `bBaselineStep`. On the first frame past
  the staging settle, the baseline clause
  `if (bBaselineStep && !StagingSuppressed(Now) && !GateBoardTally(Now))` runs
  **ahead of gates 2–8**, which is what pins the empty leg's substring: none of
  the windowed gates can be armed yet, because no ring has been entered, no list
  has been replaced and nothing has completed.
- `GateBoardTally` → `ReadTally` reads `bTallyEverWritten` off the board by
  property name, gets `false`, and fails on the never-written clause.

**The empty FAIL does not rest on one string.** `EveryFaceReadsItsOwnBank` and
`TheUnnamedMarkStaysCold` would fail on the *same frame* for the same reason —
all five faces ship blank with `bFaceEverWritten == false` — and
`EveryLampBurnsOnlyForAFinishedMark` would pass at the baseline (every lamp
correctly dark) but fail later. Gate order is what selects which name appears;
the failure itself is over-determined. If the baseline clause were ever removed,
the empty leg would instead die a frame or two later at
`EveryFaceReadsItsOwnBank`, and the run would still be a graded FAIL at under
5 s of world time.

## Why the reference is predicted to PASS, gate by gate

Each line is the reference behaviour that satisfies the gate, and the gate is
named so a real FAIL can be read straight off this list.

- **`TheHallIsNotYoursToRewire`** — the reference writes no mark's `MarkName`,
  `RequiredSeconds` or `RingRadiusUu`, never moves an actor and never touches
  `ListedMarkNames`. It only ever *reads* them.
- **`AWrongStepEmptiesEveryClock`** — the reference's test is `Idx != INDEX_NONE
  && Idx != TurnIndex`, which is **both directions of the rule**, so it fires on
  the two SKIP-AHEAD steps (a name later in the list that has never been current)
  as well as on the three steps onto a name already finished.
  `StartRoundOver()` empties the whole `Banked` map and zeroes the cursor on the
  entry edge, and `PaintHall()` runs on the same frame, so every named face reads
  `0.0`, every lamp goes dark and the tally reads `0/<current length>` well
  inside the 0.75 s the window waits. **The skip-ahead half is the one that
  matters for discrimination:** before 2026-08-19 every out-of-turn step in the
  drive landed on a mark that was both already finished AND at list index 0, so
  `Idx < TurnIndex` — a locally reasonable wrong reading — produced byte-identical
  output for the entire run and passed all thirteen gates.
- **`StandingOutOfTurnBanksNothing`** — `PoisonedMark` is set at the same instant
  as the wipe and the banking clause tests `Occupied != PoisonedMark.Get()`, so
  the mark being stood on banks nothing for the whole 4 s to 6.5 s even though
  the wipe has (on the two already-finished steps) just made it the current one
  again. This is the gate the primary wrong answer dies on. The reference also
  clears `PoisonedMark` on the step off, which is what the fixture's own arming
  lifetime now mirrors.
- **`TheRoundStartsOverWhenTheListChanges`** — the reference compares
  `LastSeenList != ListedMarkNames` every frame. That is `TArray<FName>`'s
  **ordered, element-wise** comparison, so it catches the second replacement
  (same three names, same first name, same length, different order) as well as
  the first; a cached `Num()`, a cached `list[0]` or a set comparison catches
  only the first. The tally denominator is `LastSeenList.Num()`, read at paint
  time, so it follows `/4 → /3` by itself. No step edge occurs at either
  replacement, so no wipe fires twice and nothing is poisoned.
- **`TheBankIsStillThereWhenYouComeBack`** — nothing in the reference clears a
  bank on exit; the map entry simply stops being incremented. The gate's bound is
  one-sided, so legitimate accrual inside the 0.5 s window cannot fail it.
- **`TheBankPicksUpFromWhereItStopped`** — the same map entry is incremented
  again on re-entry, so the face equals the preserved value plus the inside-ring
  seconds since, and it neither restarts nor double-counts the paused interval.
- **`TheBankHoldsWhileYouAreAway`** — with nobody in any ring, nothing is
  incremented and `PaintHall()` re-writes the same numbers, so every face is flat
  across the ≥ 6.5 s wait.
- **`AMarkWaitsForItsOwnNumber`** — the completion test is a **separate per-frame
  step** reading `Current->RequiredSeconds` live, OUTSIDE the `Occupied != nullptr
  && … == TurnIndex` block that does the banking, so the mid-stand raise makes
  the stand longer, the mid-stand drop below an already-banked value finishes the
  mark at once, and the **two off-mark drops finish a mark with the character
  parked clear of every ring and nobody standing anywhere**. That last one is the
  only thing in the run that distinguishes the reference's placement of the loop
  from the same loop nested inside the banking branch — a distinction task.md
  sells as ~1.5 h of the reference's judgment and which, before 2026-08-19, no
  staged moment tested. The loop advances the cursor at most once per mark per
  frame, so "the tally rises by exactly one" holds.
- **`TheUnnamedMarkStaysCold`** — `IndexInList` returns `INDEX_NONE` for the
  control mark, so it is neither current nor out of turn: the route walks
  straight through its ring twice and no bank, no lamp and no tally moves.
- **`EveryFaceReadsItsOwnBank`** — `PaintHall()` writes **all five** marks every
  frame, including the unlisted one and the demoted one, each from its own bank
  and its own `RequiredSeconds` read at that instant.
- **`TheBoardShowsHowFarYouGot`** — `ShowTally(TurnIndex, LastSeenList.Num())`,
  both halves live. It cannot read the full count early because `TurnIndex` only
  advances through the completion loop.
- **`EveryLampBurnsOnlyForAFinishedMark`** — `SetLampLit(Idx != INDEX_NONE && Idx
  < TurnIndex)` on every mark every frame, so the lit set is exactly the finished
  set and a wipe darkens the row on the same frame it empties the banks.
- **`TheHallDidItTwice`** — the run reaches `4/4`, returns to `0/4` on an
  out-of-turn step, and reaches `3/3` on the replaced list. The two full counts
  differ in denominator, so a latched round or a constant `/4` cannot produce
  both. The run-level gate additionally requires **two judged windows of each
  BRANCH**: skip-ahead out-of-turn, already-finished out-of-turn, completion with
  nobody standing, and list replacement. A short count on any of those is a
  HARNESS-PRECONDITION naming the branch, never a model failure — and
  `AttributeOverrun` re-checks gates 1, 9 and 12 unconditionally first, so it
  still cannot launder a FAIL.

**Two predicted numbers in that list are the ones most likely to be wrong**, and
both are widenings rather than narrowings, so an error costs wall clock and not a
verdict: the ≈ 285 s of modelled world time (158 s of it is walking, measured off
the committed layout by `authoring/author_map.py`; the drive's 38 steps are
adaptive, so a slow settle lengthens it) and the 0.25 s face tolerance
(one-decimal rounding alone is ±0.05 s, leaving 0.20 s of working margin against
a 1/20 s frame). **Calibrate the face tolerance against the reference at
`EveryFaceReadsItsOwnBank` on the first green run**, and read the drive's real
duration off the last `[t3-marks calib] cpNN` line before trusting the 285.

## Requirements table

Every requirement the prompt states, the assertion that checks it, and the
condition under which that assertion does not run. A row with no gate is a hole;
a row whose gate can be skipped is where a submission will aim. This is the §7
soundness artifact, and it is the reason this task ships no hand-authored variant
legs: a variant tests a POINT, and every defect this repo found on 2026-08-11 was
at a BOUNDARY that only a complete table can expose.

**No cell in the first column may contain a slash.** `parse_matrix` reads every
pipe table in this file and classifies a row as a variant when the first cell
matches `` `?([A-Za-z0-9_-]+)/`? `` and contains a `/` — so a requirement worded
"C++ under `Source/ThirdPerson/`" mints a phantom variant leg called `Source`.
That is not hypothetical: six sibling MATRIX files in this set do exactly that
today. The deliverable-root row below is therefore worded without one.

| Prompt requirement | Gate that checks it | When that gate does NOT run |
| --- | --- | --- |
| standing on a mark is inside a 150 cm ring, flat, inclusive at the edge | the fixture's model runs exactly that predicate on the pawn's actor location, and the marks ship it as `IsInsideRing`; any other predicate banks on different frames and diverges | never — but a submission that rolls its own overlap can differ by one frame, which the 0.35 s crossing suppression forgives |
| banks second for second while stood on the mark whose turn it is | `TheBankPicksUpFromWhereItStopped`, and `EveryFaceReadsItsOwnBank` everywhere else | inside another windowed gate's window, where that gate asserts the same fact more sharply |
| stepping off **pauses** the bank; it does not empty it | `TheBankHoldsWhileYouAreAway` | outside the off-mark waits (predicted: at least two of 6.5 s, plus the transit waits the drive's mark-to-mark walks create) |
| a number dropped below the bank finishes the mark **with nobody standing anywhere** | `AMarkWaitsForItsOwnNumber` on the two off-mark drops, judged 0.75 s later on the lamp and the tally; the run-level gate demands both | never — this is the only staging that separates a per-frame finish test from one nested in the banking step |
| a mark **later in the list that nobody has stood on yet** is an out-of-turn step | `AWrongStepEmptiesEveryClock` on the two SKIP-AHEAD phases, counted separately from the already-finished ones | outside those two windows, and once the character steps off the mark |
| **the same names in a different order is a different list** | `TheRoundStartsOverWhenTheListChanges` on the second replacement, which keeps the length, the names and the first name | outside that window |
| stepping back on **carries on from** the paused value | `TheBankIsStillThereWhenYouComeBack` (it did not empty) plus `TheBankPicksUpFromWhereItStopped` (it resumed, and did not double-count) | outside the two re-entries; a re-entry only arms when the mark carried at least 0.9 s, so a poisoned or finished stand cannot manufacture a vacuous window |
| finished when the bank reaches **its own** number as it reads **at that moment** | `AMarkWaitsForItsOwnNumber`, once per completion, with a raise and a drop staged mid-stand | more than 1 s from a modelled completion; a completion the round threw away inside its own window is logged and not judged |
| only the mark whose turn it is banks anything | `StandingOutOfTurnBanksNothing`, and `EveryFaceReadsItsOwnBank` everywhere else | — |
| a step onto another **listed** mark starts the whole round over **at that moment** | `AWrongStepEmptiesEveryClock` — every named face at 0.0, every named lamp dark, the tally back to none, all in one window | outside the out-of-turn windows, and while the character is no longer standing on the mark they stepped onto |
| a mark stepped on out of turn banks nothing however long anybody stands on it | `StandingOutOfTurnBanksNothing`, watching it for the rest of the stand | as above |
| re-stepping the mark whose turn it is is never out of turn | the model does not wipe there, so a submission that does fails `EveryFaceReadsItsOwnBank` and `TheBoardShowsHowFarYouGot` on the next judged frame | on frames the settle and crossing suppression cover |
| a mark the board does not name is inert | `TheUnnamedMarkStaysCold`, at **every** judged frame and never suppressed | never |
| lamp dark until its own mark is finished, at least 5000 bright after | `EveryLampBurnsOnlyForAFinishedMark`, every judged frame, evaluated last | only for the one mark whose finished-ness moved inside the last 0.75 s, and only that mark |
| the tally reads how many are finished out of how many names the board carries | `TheBoardShowsHowFarYouGot` | inside a windowed gate's window, where that gate asserts the same fact |
| the tally never reads the full count before the last name is finished in its turn | the same gate — it is an equality against the model, so early is exactly as wrong as late | as above |
| a new list starts the round over, with a new length | `TheRoundStartsOverWhenTheListChanges` | outside that window (predicted: two graded list replacements — the shift change, and the same-length reorder) |
| the numbers and the list are read at the point of use, never cached | `AMarkWaitsForItsOwnNumber` (a mid-stand raise and a mid-stand drop) and `TheRoundStartsOverWhenTheListChanges` (a new denominator), plus the committed two-name decoy at the baseline | as above |
| the hall settles within half a second of any change | the 0.75 s suppression window, which is 1.5x it, so the contract is never judged on its own boundary | never |
| a face may lag a quarter of a second | the 0.25 s comparison tolerance, which is exactly it, plus one frame per ring crossing in the current attempt | never |
| none of it is one-shot; the round has to happen again | `TheHallDidItTwice`, at drive completion or the sentinel | a run that fails a per-frame gate earlier never reaches it, which is the more useful message |
| do not move the marks or the board, and do not change any number written on them | `TheHallIsNotYoursToRewire`, every frame from the first, before the model steps | never |
| the solution is C++ in the agent-writable runtime module named in the prompt | sandbox: a file outside the writable set is exit 4 SANDBOX-REJECT, not a graded FAIL | never |

## Wrong answers with no hand-authored variant, and why that is honest

Per the 2026-08-11 owner decision reinforced on 2026-08-18, variants are written
for a hole the requirements table finds, not one per gate. `task.md`'s
requirement-to-assertion map covers every prompt sentence with no gap, so this
task ships the two mandatory legs and no more. Every entry below is a real
first-pass implementation, not a strawman.

- **judge the declared order at COMPLETION instead of at the STEP** (bank
  whatever ring you are standing on, check the order at the end) →
  `AWrongStepEmptiesEveryClock`, which finds the previously finished mark still
  lit and the tally still reading 2/4 two seconds after the wrong step. This is
  THE named wrong answer: it completes a clean run byte-identically, and only the
  deliberately dirty phases separate it.
- **reset the bank on exit instead of pausing it** →
  `TheBankIsStillThereWhenYouComeBack`, by the whole preserved bank. Note it
  *passes* `TheBankHoldsWhileYouAreAway` (zero does not move), which is exactly
  why those two are separate gates.
- **wipe only the offending mark**, or **only the progress cursor** →
  `AWrongStepEmptiesEveryClock`, whose message lists every bank it found still
  standing.
- **treat the mark you stepped on out of turn as the new current mark** ("reset
  progress, then re-evaluate where I am") → `StandingOutOfTurnBanksNothing`,
  because the drive steps onto the mark that is first on the list and watches it
  for 6.5 s.
- **count only an ALREADY FINISHED mark as out of turn** (`Idx < TurnIndex`
  where the rule says `Idx != TurnIndex`) → `AWrongStepEmptiesEveryClock` on
  either of the two SKIP-AHEAD phases, which finds the part-banked current mark's
  bank still standing 0.75 s after a step onto a name further down the list.
  **This is the highest-value row in this file**, because it is the only one of
  the four that was byte-identical to the reference for the entire pre-2026-08-19
  drive — every out-of-turn step landed on a mark that was both finished and at
  index 0.
- **nest the completion test inside the banking step** → `AMarkWaitsForItsOwnNumber`
  on either off-mark drop: the mark whose number was dropped below its bank never
  finishes, so 0.75 s later its lamp is at 0 and the tally is short by one, with
  nobody standing on any mark. Also previously byte-identical for the whole run.
- **detect a new list by its LENGTH, its first name, or its set of names** →
  `TheRoundStartsOverWhenTheListChanges` on the second replacement, which keeps
  all three and moves only the order, so the finished round is found still
  standing. Previously byte-identical too: the only staged replacement went 4
  names to 3.
- **read the list, its length, or a mark's seconds once at `BeginPlay`** →
  `TheBoardShowsHowFarYouGot` at the baseline: the committed level carries a
  TWO-name list, so the cached answer reads `0/2` where `0/4` is owed, before the
  character has entered a single ring. The committed list also names the control
  mark, so the same answer fails `TheUnnamedMarkStaysCold` on the same frame.
- **compile the tally denominator as a constant** →
  `TheRoundStartsOverWhenTheListChanges`, which names the length found; round 2
  carries three names against round 1's four.
- **infer the order from placement, name order or discovery order** → the same
  gate and `TheBoardShowsHowFarYouGot`. `author_map.py` refuses to save a hall
  whose round-1 list matches alphabetical, X-ascending, distance-from-the-parking-
  spot, required-seconds or placement order, forwards or reversed.
- **cache a mark's required seconds when the stand begins** →
  `AMarkWaitsForItsOwnNumber`, twice and in both directions: one number is raised
  mid-stand (the stand must get longer) and another dropped below its
  already-banked value (that mark must finish with nobody moving). No
  cached-at-entry value produces both, and no shared constant produces either.
- **attach the completion test to the banking step** → the same gate: the
  mid-stand drop can then never finish a mark, because nobody is moving.
- **treat every mark other than the current one as an out-of-turn step** →
  `TheUnnamedMarkStaysCold`, gauged at every judged frame and never suppressed.
- **keep correct internal state and never write a face, a lamp or the tally** →
  `EveryFaceReadsItsOwnBank` / `TheBoardShowsHowFarYouGot`. Nothing private is
  ever read: the fixture grades the two mirrors `ShowBank` writes, the two
  `ShowTally` writes, and the point lights' own intensity, and the board carries
  no other readout to call instead.
- **write only the LISTED marks' faces** → `TheUnnamedMarkStaysCold` on the
  never-written clause, from the baseline onward. The prompt says "each mark's
  face", and the demoted mark makes this bite a second time in round 2.
- **light a lamp with a hidden light component, or report it from a `bool`** →
  `EveryLampBurnsOnlyForAFinishedMark`: `LampIntensity` reads the component and
  scores an invisible light as 0.
- **add a per-frame constant instead of `DeltaSeconds`** →
  `AMarkWaitsForItsOwnNumber` on the 20 Hz leg, at the first completion; it looks
  plausible at 60 Hz and is 3x wrong at 20.
- **latch the round once complete** → `TheHallDidItTwice`, which needs the full
  count in both rounds with a return to zero in between, reached by two different
  routes (an out-of-turn wipe, and a list replacement).
- **move a mark, rename one, or rewrite a number to make the round easier** →
  `TheHallIsNotYoursToRewire`, every frame from the first.
- **edit the fixture** → not a FAIL at all: `Source/CraftBenchTests/` is outside
  the writable set (exit 4 `SANDBOX-REJECT`) and the runner grades from git HEAD.

## Status

**PREDICTED, NEVER MEASURED — on every row.** The blocking prerequisites, in
order:

1. `Content/Maps/t3-hold-the-marks-in-the-order-given/L_MarkOrder.umap` does not
   exist yet; `authoring/author_map.py` writes it. `tasklint` reports it as this
   task's only ERROR, and note that tasklint does **not** error on a missing
   fixture source, so a green-but-for-the-map lint is not evidence of anything
   else.
2. L1 has never run. Every API and content path in the fixture, the scaffold and
   the reference is source-checked against the UE 5.8 tree and against shipping
   siblings, but source-checked is not compiled.
3. `cb discriminate` has never run. When it does, the two rows above are the
   claims to check, and the one thing to check hardest is that the empty leg's
   FAIL is a **graded** FAIL (exit 1) and not exit 7: the fixture ends the run as
   `HARNESS-PRECONDITION` for a hall it cannot resolve or walk, and a layout
   fault would present as an uncredited harness exit rather than as the named
   gate above. `AttributeOverrun` re-checks `TheHallIsNotYoursToRewire`,
   `TheUnnamedMarkStaysCold` and `EveryLampBurnsOnlyForAFinishedMark`
   unconditionally before it attributes anything to staging, precisely so a
   graded FAIL can never be laundered into one.
4. The empirical half of the 2026-08-18 difficulty bar is unmet: this task has
   never met a model. One `cb eval --model claude-p:<cheap model>` run is what
   tells us whether the bar was reached; a first-try pass with no iteration means
   it was not.
5. **The 2026-08-19 adversarial review changed the FIXTURE, not the reference**,
   so nothing in this file's reference column has been re-derived from a run —
   it is the same argument against a longer drive. Three things to check first
   on the first green run, all of them new that day and none of them measured:
   (a) the two SKIP-AHEAD phases (drive steps 3 and 22) really do fire
   `AWrongStepEmptiesEveryClock` and leave `ahead` at 2 in the calib line;
   (b) the two off-mark drops (steps 14 and 33) really do produce a modelled
   completion with `OccupiedLast == INDEX_NONE`, leaving `alone` at 2 — the drop
   fires from `MaybeFireStagedRewrite` and the model sees the completion on the
   NEXT frame, so a mis-ordered guard would silently skip it; and (c) the
   same-length reorder (step 36) really does raise `l` to 2. Each of those is a
   run-level HARNESS-PRECONDITION if the drive fails to produce it, so a short
   count reads as a harness fault and not as a graded verdict — which is correct,
   but means a broken new phase presents as exit 7 rather than as a FAIL.
6. **The drive got ~50 s longer** (≈ 235 s predicted before, ≈ 285 s now, over
   two fps legs). The sentinel is unchanged at 400 s and the calibration
   checkpoints were extended from 50 to 58 (300 s → 348 s of coverage) by
   APPENDING, so `cameras.json` (the camera-plan lane; not part of this release)'s `pie_timeline` indices (highest: 36) are
   untouched — but every one of those shot labels was aimed at the OLD phase
   map and is now wrong about which phase it lands in. Re-aim them off one real
   calib log before treating any frame as the shot it is labelled; that was
   already true (the file says so) and is now true by a bigger margin.
