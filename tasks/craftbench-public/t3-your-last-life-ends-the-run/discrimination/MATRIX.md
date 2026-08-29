# Discrimination matrix — t3-your-last-life-ends-the-run

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs. The
per-checkpoint named gates carry the discrimination; `../task.md` §
*Requirement-to-assertion map* carries the coverage argument.

> **EVERY VERDICT, SUBSTRING AND NUMBER IN THIS FILE IS PREDICTED, NOT MEASURED.**
> Nothing was built or run while this task was authored: no UnrealBuildTool, no PIE,
> no `cb discriminate`, no `cb refgate`. The verdicts are derived by reading
> `LifeRunTerminalFunctionalTest.{h,cpp}`, the five scaffold pairs and the reference
> against each other. The substrings are quoted from the fixture's own `TEXT(...)`
> literals, not from a log. The arithmetic (3 → 4 → 1 and 2 → 4 → 6 on the loss leg,
> 5 → 3 and 6 → 5 on the win leg, and the finish asking 3 → 5 → 1 and 5 → 6 → 2) is
> re-derived from `ResolveLeg()`'s two staging tables, which the fixture itself
> re-simulates in `StepModel` and which `ValidateStagingTable` re-checks at run
> time. **The orchestrator measures. Do not cite a cell of this file as an
> observation.**
>
> **Rewritten 2026-08-19 after two adversarial reviews.** The finish now carries a
> number of its own, `DemandedLives`, re-staged per leg and re-painted twice
> mid-run; the win leg is won on a frame in which its runner does not move; and two
> gates are new (`TheGoalOnlyOpensToWhatItAsksFor`, `ARunnerIsAlwaysFreeToWalk`).
> Every cell below is a prediction about the NEW fixture and none of it has been
> run either. `../notes.md` § *Fourth pass* has the reasoning.
>
> **AND NEITHER LEG CAN RUN AT ALL YET**, for a reason that is about neither
> submission: `Content/Maps/t3-your-last-life-ends-the-run/L_LifeRun.umap` does not
> exist. `authoring/author_map.py` authors it and has to be run once through the
> headless editor first (`tasklint` errors `map-binary-exists` until it lands). Until
> then L2 has no world and both rows below are *unreachable*, not *untested*.

| Submission | Overall | Named substring(s) | Why it lands there and not somewhere else |
| --- | --- | --- | --- |
| `../reference` | PASS (predicted) | `Test Completed. Result={Success}`, and the fixture's own closing line beginning `Leg ` … ` Hz: the near runner was claimed ` | Remaining lives is **derived at the point of use** — `max(0, OwnMarker->PaintedLives - Deaths)` — never latched, so both mid-run re-paints move the row on the frame they land and move which death is the last one. The life is spent on the **death**, and "was that the last one?" is asked immediately afterwards, of the board as it reads *then*; the run-ending death takes a different branch that sets `Lost`, freezes the row dark and never schedules a return. **The finish is asked as a CONDITION, every frame** — `FinishUnderfoot() && RemainingLives() >= Underfoot->DemandedLives` — never on an overlap edge, which is the only reason the win leg is ever won: on both legs that becomes true on a frame in which the runner is standing still and the DISC's own number came down to it. Every later event early-outs on `State != Running`, so an ended run's ground costs nothing, its finish does nothing whether or not it is holding enough, and its re-painted marker changes nothing. `OwnMarker` is resolved once in `BeginPlay` and never re-derived, so the off-lane crossing sends the runner back to **its own** disc and not the nearer one. Nothing is shared between the three instances, so the bystander never moves. And nothing anywhere immobilises a runner: the return is the one and only `SetActorLocation`, so the drive can still walk both ended bodies afterwards. |
| `empty` | FAIL (predicted) | `TheRunReadsWhatItIs: a runner is not showing what its run is.` | L1 is green: the scaffold compiles exactly as shipped (`SetLitCount` / `GetLitCount` / `SetStateWord` / `GetStateWord` are defined and simply never called). In PIE the six lamps are authored at intensity 0 and `WordText` at the placeholder `-`, and nothing calls either switch — so on the **first judged frame** the near runner's marker reads 3 (60 Hz) or 2 (20 Hz), it has been claimed 0 times, and 0 lamps are lit against 3 (or 2) expected, while its word's first run of letters is the empty string against `RUNNING`. |

Both substrings are contiguous spans of single source literals in
`LifeRunTerminalFunctionalTest.cpp`; the empty leg's stops before the literal's first
`%s`. No two gates in this fixture share a FAIL prefix (`tasklint` reports no
`fixture-fail-unique` warning), so a substring match is unambiguous.

## Why the empty leg lands on `TheRunReadsWhatItIs` and nowhere else

Four independent reasons, and all four are needed — an empty submission is wrong
about *every* readout in the level, so without a fixed precedence this cell would be a
coin toss between five messages.

1. **Nothing is armed during phase 0.** `Tick` computes
   `bArmed = Phases[PhaseIndex].Kind != EPhaseKind::Settle`, and phase 0 is a 2.0 s
   `Settle` in which nothing is driven. So no display gate can fire before the level
   has stopped arriving — predicted at world time ≈ 2.0 s, i.e. before the first
   scheduled checkpoint at 5 s.
2. **`TheRunIsNotYoursToRewire` runs first and PASSES.** It is evaluated every frame
   from the very first tick, ahead of `bArmed` — and an empty submission moves
   nothing, replaces nobody, and still carries six lamps and one word per runner. It
   is anti-tamper, not discrimination (see *the gates that must be discounted in a
   k/N* below).
3. **No windowed gate can claim it, because no event has happened yet.** On the first
   armed frame `LastCrossingAt`, `RepaintAt`, `FirstWinAt` and `TerminalAt` are all
   still `-1`, and every runner's state is `Running`, so the precedence chain in
   `Tick` falls through `bLastLifeWindow` / `bCrossWindow` / `bRepaintWindow` /
   `bWinWindow` / `State != Running` to the `else` branch — the everywhere-else gate.
4. **The runner loop is ordered and the bystander gate is last.** `Runners` is
   `{player, RunnerLaneB, RunnerLaneC}`; runner 0 is judged first and fails on that
   frame, and `Tick` returns immediately. `GateBystander` is reached only
   `if (bAnyJudged && ...)` **after** the whole loop has agreed, so the empty leg is
   named by the everywhere-else gate and **not** by `TheBystanderIsUntouched` — even
   though the bystander's row is equally dark. That is the diagnosis that matters: an
   empty submission has not got ownership wrong, it has done nothing.

`GateNoTeleport` also runs on that frame and passes trivially (`R.Crossings == 0`).

## Read a FAIL correctly before you believe it

`ALifeRunTerminalFunctionalTest` reports anything that is the **level's** fault, not
the model's, as `EFunctionalTestResult::Error` with a message beginning
`HARNESS-PRECONDITION:` — a **non-graded** exit, and neither row of the table above. If
a leg comes back naming actor counts, per-instance lane marks, a patch that is scaled
or does not span every lane, an ownership margin, a route with no floor under it, a
dead input lane, or a drive phase that ran past its derived deadline, then the **map or
the workdir** is wrong and nothing about the submission has been measured yet.

`authoring/author_map.py` exists to make most of that unreachable: it ports the
fixture's own `PlanarDistToPatch`, `InPatchArmed`, off-lane scan (same 25 cm step, same
100 cm inset), bypass-corridor derivation and phase-by-phase route cursor, re-derives
the whole drive from the same numbers, and **refuses to save** a level any of it does
not come out for. Run offline against the authored layout it solves cleanly
(**predicted, from the Python port, not from a PIE run**): loss leg runs out on
crossing **4**, off-lane crossing at **y = +1342** with **1,012 cm** of ownership
margin against a 400 cm floor, bypass corridor at **y = −2000**, **21** driven phases
(19 before the finish's own number was added), every waypoint inside the floor, no
non-crossing segment on the hazard, and the win leg's step-off spot **465 cm** clear
of the disc's painted edge — the fixture counts an arrival from 42 cm outside it, so
stepping off and back on is a real second arrival and not a skim.

One `HARNESS-PRECONDITION` is deliberately *not* a get-out: before **any** deadline or
sentinel overrun is written off, `ReCheckDisplays` re-runs `TheRunIsNotYoursToRewire`,
the per-runner display gate and `TheBystanderIsUntouched` unconditionally. A submission
that parks a runner, moves a marker or pulls a runner back is exactly what makes a
phase overrun, so a rewired level must be a graded FAIL and never an uncredited
non-graded exit.

## What carries the discrimination without variants

**The load-bearing number is not in the committed map, and it moves twice mid-run.**
`PrepareTest` re-paints all three markers from a table chosen by the run's own
framerate, so the 60 Hz and 20 Hz PIE processes stage different numbers
(3/5/6 → 4/5/6 → 4/3/6 → 1/2/6 and 2/6/3 → 4/6/3 → 4/5/3 → 6/1/3 — predicted from
`ResolveLeg`). The authoring script paints 4/2/5 into the `.umap` and asserts that
**no authored number is a value either leg ever stages**, so a life count mined off
disk is wrong on both legs from the first judged frame. `ValidateStagingTable` refuses
a table in which two markers ever read the same number at any instant, including the
instant between the two closing writes.

**The three answers the task is now shaped to catch are code-shape errors, and
each is caught by a different named gate.** (Predicted; added 2026-08-19.)

- *Write the finish the way the level tells you to write the ground* — one overlap
  handler apiece, which is symmetrical, obvious code. It passes **both** of the win
  leg's arrivals correctly (the runner is short each time and does not win). Then
  the disc's number comes down to what that runner is holding while it stands still,
  there is no event, and it never wins the run at all — named by
  `ReachingTheGoalWinsAndSpendsNothing`, whose window opens on exactly that frame.
  The drive never walks that runner onto the disc while it is holding enough, so
  there is no route around it.
- *Measure "enough" against the board instead of against what is left* — on both
  legs the disc asks, at the win leg's first arrival, for **exactly** the number
  painted on that runner's own marker (3 vs a board of 3 at 60 Hz; 5 vs a board of 5
  at 20 Hz), so this answer opens the goal the instant the runner steps on, two
  deaths early and with the wrong row frozen. `TheGoalOnlyOpensToWhatItAsksFor`
  prints both numbers side by side. `ValidateStagingTable` refuses a table in which
  that coincidence does not hold.
- *`>` where the level says at least* — the disc's last move lands exactly on what
  the win leg holds at 60 Hz (1 against 1) and strictly below it at 20 Hz (2 against
  3). This answer PASSES 20 Hz and FAILs 60 Hz on
  `ReachingTheGoalWinsAndSpendsNothing`. **A leg-split verdict on this task is a
  real off-by-one, not framerate flakiness.**

And one that used to escape scoring altogether:

- *Nail the ended runner down* (`DisableMovement()`, a per-frame
  `StopMovementImmediately()`, or re-asserting the claim spot) — green on every
  display gate, and it used to stall the drive into a non-graded
  `HARNESS-PRECONDITION` attributed to us. It is now disclosed in the prompt (*a
  runner is always a body that can be walked*) and graded by
  `ARunnerIsAlwaysFreeToWalk`, which fires only after `ReCheckDisplays` has re-run
  every display gate unconditionally.

**The older named wrong answers, each still caught by a different named gate.**

- *Spend the life on the RETURN, not on the death* — the natural first
  implementation. Every surface check passes: lives start right, each death costs one,
  non-final deaths return you home, the row comes down one at a time. It is wrong in
  two measured places, and `TheLastLifeEndsTheRun` names both of them: the run-ending
  death still runs the return branch, so the runner is standing **on its marker**
  (predicted ≈ 2,400 cm from the spot the ground claimed it, against a disclosed
  150 cm) with zero lamps lit and still reading `RUNNING`.
- *Read the painted number once, at `BeginPlay`* (or keep a countdown latched at the
  start) — `TheBoardIsReadWhenItMatters` names it in **both** directions, because A's
  board goes UP and B's comes DOWN. A latched countdown also ends A's run one crossing
  early on the 60 Hz leg and two crossings early on the 20 Hz leg, which
  `TheLastLifeEndsTheRun` then names at the wrong crossing.
- *One run for the level* (a shared counter and a shared latch) — passes the whole
  loss leg and the whole win leg in isolation and is named by
  `TheBystanderIsUntouched`, which is evaluated on **every** judged frame including
  inside every other gate's window.
- *Send them back to the nearest marker* — one of the two matched crossing spots is
  deliberately nearer a different runner's marker (predicted margin 1,012 cm, derived
  by the fixture rather than written down), and
  `WhileLivesRemainYouComeBackToYourMarker` prints which marker it actually went to.

**Nothing one-shot survives.** The crumbling ground spends four lives on the loss-leg
runner in two matched pairs (own lane / off lane) and two on the win-leg runner; the
finish disc is arrived at **four** times by two runners and the win happens on none of
them; and `FinalGrade` refuses to grade
a run whose own tallies came up short (`>= 4` and `>= 2` spending crossings, a total
crossing count that agrees with the staging table, `>= 3` conflicting events driven at
**each** ended run, `>= 2` disc arrivals by the win leg, `>= 2` moves of the finish's
own number, and `>= 2` judged frames on which the win leg stood on the disc short of
it) — attributed as ours, never passed.

**Nothing private is ever read.** There is no lives property on any supplied class;
the fixture counts lit lamps off the `UPointLightComponent`s' own intensity (resolving
the row by the names the level built it under, `Lamp0..Lamp5`, and ignoring any other
light a submission hangs on a runner) and reads the word as the first run of ASCII
letters in the `UTextRenderComponent`'s string. `GetLitCount()` — which a submission
may rewrite — is never called.

## The gates that must be discounted in a k/N, declared

**`TheRunIsNotYoursToRewire` is anti-tamper, not discrimination.** It is green for a
do-nothing delivery by construction, and it must be excluded from any k/N presented as
a discrimination score — this is the DEF-5 dead-gate defect the adoption review found
at 3/6 on the parent corpus row `t2-lives-system`. Every other gate in the fixture
fails on an empty delivery; `TheRunReadsWhatItIs` is simply the one that gets there
first.

**`BothRunsEndedTheirOwnWay` is corroborative and must be discounted too** (added
2026-08-19, after a reviewer showed the old version was close to a fixture
self-check). It now reads the three runners' own words and lamp counts off the level
rather than off the fixture's model — so it is a statement about the submission — but
any runner showing the wrong word has already been named by a per-frame gate long
before `FinalGrade` runs, so it can only ever confirm. The question of whether the
DRIVE happened at all is asked separately and first, against the fixture's own model,
and reported as a `HARNESS-PRECONDITION`: nothing a submission does can move that
model, so a graded FAIL there was mis-attribution waiting to happen.

**`ARunnerIsAlwaysFreeToWalk` is a real discrimination gate but fires only on a
stalled drive.** It is not free to an empty submission (an empty submission never
stalls anything — it simply fails the first judged frame), and it should be counted;
but a k/N that lists it as "not fired" on a correct answer is reading it right.

## One fixture defect was found and fixed while writing this file

`SuppressedFor` banded a still-running runner within 160 cm of a trigger's edge on
**both** sides of the surface. Measured off the drive's own arithmetic, a runner
released inside the patch comes to rest ~36–53 cm inside the near face — inside the
band — so a runner **left lying in the patch** was permanently unjudgeable, and
`WhileLivesRemainYouComeBackToYourMarker` could not fire against the one submission it
is written to name (never implementing the return at all). The band is now one-sided:
`0 <= dist < 160` outside the surface only. Once the capsule centre is inside a
trigger every honest entry model agrees it is inside, and the 0.75 s
model-change suppression already covers the ≤ 0.084 s the two models can lag by, plus a
frame of tick order. **This can only widen what is judged, never narrow it**, and it
cannot change the reference's verdict: a correct answer is back on its marker (and
~2,400 cm clear of the band) long before the gate gauges at crossing + 1.35 s. Both
`../task.md` § *Settle and suppression* and the fixture header were corrected to match.

## Requirements table

See `../task.md` § *Requirement-to-assertion map* — every prompt requirement, the gate
that checks it, and the condition under which that gate stands down.

## Not yet run

Neither leg has been executed and, until the `.umap` is authored, neither leg *can*
be. **Treat every cell of this file as a prediction until
`cb discriminate --task craftbench-public/t3-your-last-life-ends-the-run --wip` has
been run once.** Six things to check on that first run, because they are the cells
most likely to move:

1. **That the empty leg names `TheRunReadsWhatItIs`** and not `TheBystanderIsUntouched`
   — the whole precedence argument above rests on the runner loop being ordered and the
   bystander gate running last.
2. **The two entry models, on the 20 Hz leg especially.** The fixture arms one capsule
   radius (42 cm) before the reference's plain-box test, and at 20 Hz one frame is
   25 cm of travel against that 42 cm disagreement band. Read the
   `[t3-liferun calib]` lines — one every 5 s per runner, carrying the painted number,
   the deaths, the wanted vs found lamp count and word, and the position — before
   believing any verdict.
3. **That the drive finishes inside the schedule.** The whole drive is *predicted* at
   ~150–180 s (it grew ~19 s when the finish's own number was added) against 480 s of
   graded checkpoints and a 500 s sentinel, but that is
   arithmetic over the route legs at an assumed 500 cm/s walk, not a stopwatch. A
   drive that overruns reports `HARNESS-PRECONDITION`, not a FAIL — after
   `ReCheckDisplays` **and** `ARunnerIsAlwaysFreeToWalk` have both run.
4. **That `PrepareTest` accepts the authored map at all.** The `.umap` will have been
   authored by a script that re-derives the fixture's geometry rather than by hand, but
   the script's floor check is a bounding box while the fixture's is a real line trace,
   and the script's obstacle check is a collision-profile sweep while the fixture's is
   a real capsule overlap. Those are the two places the two could still disagree.
5. **That the win leg wins at all, and wins where it should.** This is the newest and
   least-proven thing in the fixture: the win now hangs on a fixture WRITE to
   `DemandedLives` landing while the runner stands still, on `StagingUntil`
   suppressing the frames either side of it, and on `StepModel` (which runs first in
   `Tick`) being what flips the model. Read the `[t3-liferun calib]` lines — they now
   carry `goal-asks=` — and confirm the win timestamp sits inside the stand phase
   that follows the second demand write, not on either disc arrival.
6. **That `ARunnerIsAlwaysFreeToWalk` never fires on the reference.** It is the one
   new gate that could in principle manufacture a FAIL. It needs a walking phase to
   overrun its derived deadline (2.5x the ideal plus 12 s) *and* the body being
   pushed to have moved under 150 cm in all that time, so a correct answer cannot
   reach it — but that is an argument, not a measurement.
