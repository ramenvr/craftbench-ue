# Discrimination matrix — t3-the-yard-remembers-after-you-leave

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs. The
per-checkpoint named gates carry the discrimination; the requirements table carries
the coverage argument.

> **EVERY VERDICT, SUBSTRING AND NUMBER BELOW IS PREDICTED, NOT MEASURED.** Nothing in
> this repository was built or run while this task was authored: no L1, no PIE, no
> `cb discriminate`. Verdicts are derived by reading the fixture, the scaffold and the
> reference against each other; substrings are quoted from the fixture's own source
> literals rather than from a log; arithmetic (33, 23, 51, ...) is re-derived from the
> staged table in `MemoryYardFunctionalTest.cpp::ChooseSet`, which is data the fixture
> itself re-simulates in `BuildDayTrace`. The orchestrator measures. Do not cite a cell
> of this file as an observation.
>
> **ONE EXCEPTION, and it is not in the table.** The map script's geometry gate and its
> day gate are pure Python and need no editor, so both WERE run (2026-08-19, after the
> three-rebuild rework): see *The route derives itself from the world* below for the 93
> simulated routes, the measured clearances and the 14 refused mutations, and
> `check_day` for all three staged days passing every one of `BuildDayTrace`'s
> refusals. That establishes the walk's geometry and the staged days' arithmetic, and
> nothing else — not the verdicts, not the substrings, not a single line of the
> fixture's C++, which has never been compiled.
>
> **AND NEITHER LEG CAN RUN AT ALL YET**, for a reason that is not about either
> submission: `Content/Maps/t3-the-yard-remembers-after-you-leave/L_MemoryYard.umap`
> does not exist. `authoring/author_map.py` authors it and has to be run once through
> the headless editor first. Until then L2 has no world, and the two rows below are
> unreachable rather than untested.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS | `Test Completed. Result={Success}` | The decision layer is a `UGameInstanceSubsystem`, so it outlives the props — but it holds **only the list of props currently standing**. Every question about what was taken, banked or marked is a fresh `LoadGameFromSlot`, and every change is a `SaveGameToSlot` immediately after. A post listens to its own patch of ground, latches so one arrival is one attempt, and asks the keeper; the keeper refuses to pay twice for a post the record already lists. The amount banked is the number the post was showing at that moment, never a sum re-derived from the posts. A pad arriving in a world that has already begun play is how the keeper knows the yard was rebuilt, which is when it sets the runner back down on the marked pad — against that pad's own live transform. Delete the record and every one of those answers becomes the never-visited one, because there was never a second copy. |
| `empty` | FAIL | `SessionTallyTracksExactly: the ` | The unmodified scaffold compiles, so L1 is green. `ShowWorth`, `ShowStanding`, `ShowTotal` and `ShowLamp` all exist and work, and `BeginPlay` paints every prop honestly — so the yard opens on exactly the staged numbers, the far yard reads 0, and the runner walks. Nothing is bound to any trigger volume, so after the drive has walked into three posts the board still reads 0 where the day banked 33, and all five posts are still standing. |

The empty leg's substring is a contiguous span of one source literal in
`MemoryYardFunctionalTest.cpp::GradeVisit` and stops before the first `%d`.

## Why the empty leg's named gate is deterministic

Two independent reasons, and both are needed:

1. **The first four visits are ungated.** The visit plan assigns
   `EGate::None` to the pad-1 stand, the first take, the second take and the pad-2
   stand; the first gate in the run is `SessionTallyTracksExactly`, attached to the
   *third* take. So the earlier steps cannot claim the failure even though an empty
   submission is already wrong about all of them.
2. **Inside that gate the board is compared FIRST**, before the standing set and
   before the lamp — with a comment in the fixture saying so. An empty submission is
   wrong about all three at that sample, and without a fixed order this cell would
   be a coin toss between three messages.

3. **The opening probe cannot claim it either.** The unmodified scaffold's
   `BeginPlay` calls `ShowStanding(true)` and `ShowWorth(WorthNow)` on every post and
   `ShowTotal(0)` on every board, so the yard opens on precisely the staged numbers
   and the probe returns clean — down neither of its two branches. That matters
   because the probe's scored branch names the *same* gate: if an empty submission
   could trip it, this cell would name `SessionTallyTracksExactly` for the wrong
   reason and with a different substring.

The two every-frame gates that run earlier (`TwinYardNeverChanges`,
`RunnerKeepsWalking`) and the opening save-directory probe all **pass** for an
empty submission, by design — see *Two gates are free* below.

## What carries the discrimination without variants

**Three complete staged sets, and the level agrees with none of them.** Every worth,
every take order and every pad choice is staged before any `BeginPlay` through
`FWorldDelegates::OnWorldInitializedActors` filtered to this world;
which of the three staged days runs is taken **from the clock** and logged, and
`-CraftBenchYardSeed=0|1|2` pins one so a leg reproduces byte for byte. The committed `.umap` carries different numbers again, and
the authoring script refuses to save a level whose numbers have drifted into
agreeing with any set. Nothing readable off disk is a correct answer, and no constant
is right in more than one set.

**The numbers are restaged THREE TIMES INSIDE EVERY RUN.** This is the part that does not
depend on run-to-run entropy at all. At each reopen the fixture destroys every post,
pad and board in both yards and spawns fresh ones carrying different worths on
different slots. So a total re-derived from the taken posts' current numbers is a
different number from the one that was banked — 33 versus 23 in set 0, and the
fixture's `PrepareTest` refuses to run a set unless the true total differs from *all*
of: zero, the count of posts taken, the sum of the taken posts' reopened worths, and
the sum of all five reopened worths. The gate cannot go vacuous when the table is
next edited.

**The record is DELETED mid-run — and, at a different reopening, REWOUND.** That
pair is the whole task. At every reopen the fixture destroys the props, does one
thing to the project's save-game directory, and spawns the new yard: three adjacent
statements in one tick. The one thing is **nothing** (warm), **delete** (cold), or
**delete and write back the byte-for-byte copy taken a moment after the counter board
first rose** (rewind). Each happens exactly once per day and the three staged days
order them differently, so the shape cannot be counted.

- The **delete** leaves exactly one channel by which a warm answer could survive: a
  live in-memory store. A submission holding the state on a subsystem *and* writing a
  save file reopens warm here, which is what `ColdReopenForgetsEverything` condemns.
- The **rewind** closes the hole the delete cannot see, and it is the fix for the
  2026-08-19 review finding that this task's headline concept was ungraded. Deleting
  only ever asked whether the record EXISTS. A keeper that holds the yard in memory,
  writes an EMPTY save object after every change, and resets itself whenever
  `DoesSaveGameExist` returns false satisfies that — with a record nobody ever reads
  — and passed every gate this task shipped with. Putting older bytes back changes
  the record's CONTENT and leaves its existence alone, so a memory-sourced yard
  reopens on the day it remembers and a record-sourced one reopens on the day the
  record holds. `PutBackRecordRulesTheYard` is the named gate. In staged day 2 the
  rewind comes AFTER the cold reopening, so the required state predates a deletion
  and no in-memory channel can carry it at all.

**Four post-reopen steps are behavioural, not visual.** A restore that repaints the
board and re-hides the posts while leaving the live state alone shows all the right
numbers and then fails: the walk back through a taken post's ground must move nothing
(`RetakenPostAddsNothing`), a further post must bank the number it is showing **now**
(`UntakenPostStillAddsAfterReopen`), a further pad must move the burning lamp
(`LatestPadMovesAfterReopen`), and the emptied yard must be takeable again
(`ColdYardTakesAgain`).

**Everything comes back on a different slot.** Posts, pads and boards are all
respawned somewhere else at all three reopens (cumulative shifts 1, 2, 4, which is
never the identity in a row of five or of three), and every gate matches by the name the prop
carries. A restore keyed by index, spawn order or position lands on the wrong prop —
and if it crosses the dividing wall it fails `TwinYardNeverChanges` on a yard nobody
has ever entered.

**The route derives itself from the world.** Every waypoint is re-resolved after each
rebuild from the live actor, or from the transform the fixture spawned it at for a
post that has been taken, and the runner is steered per frame toward the resolved
target. `PrepareTest` refuses a route with a waypoint within 250 uu of a prop it is
not about, or a leg that passes that close to one.

**READ THAT REFUSAL CORRECTLY WHEN YOU RUN THESE LEGS.** It is an
`EFunctionalTestResult::Error` -- a `HARNESS-PRECONDITION`, the LEVEL's fault -- and it
is NOT either row of this table. If a leg comes back naming a waypoint clearance, a
missing prop count, a dead input lane, or a yard that "did not open on the numbers the
fixture staged", the map or the workdir is wrong and nothing about the submission has
been measured yet. `authoring/author_map.py` exists to make that unreachable: it ports
the fixture's route builder, its rotation rule and both of its clearance checks, and
refuses to save a yard the walk could not be run in.

**This one thing WAS measured, and it is the only measured cell in this file.**
`check_geometry` (and, since 2026-08-19, `check_day`) is pure Python -- `math` and
nothing else -- so it runs without an editor, without a build and without the `.umap`.
Executed offline against a stubbed `unreal` module on 2026-08-19, after the three-
rebuild rework: **all three staged days pass every one of `BuildDayTrace`'s refusals**
(warm/rewind/cold once each per day, no naive answer landing on any required reading,
every walked step legal against the simulated state), and the layout PASSES,
simulating **93 routes** (3 staged days x 4 stretches x every plausible set-down
position, including the gate and each pad centre +/- the disclosed 150 uu) at all four
slot rotations 0/1/2/4, with worst clearance **700 uu to a prop** against the 250 the
fixture requires, **1,082 uu to a counter board** against 200, and **400 uu to a wall**.
**Fourteen deliberate layout mutations were then run against that same gate and all
fourteen were refused** -- a post row pulled inside the lane clearance, both rows on
one side of the lane, two posts sharing a column, pad slots inside twice the disclosed
radius, a PlayerStart parked on a mark, a narrowed gate gap, a decoy drifting into
agreement with a staged round, a worth outside the disclosed 3..17 band, unsorted post
names, duplicate pad orders, a board dragged onto the lane, two far posts sharing a
column, and a floor too small to hold the gate waypoint. So a clearance Error on the
first live run means the layout changed after this was written, not that the gate is
soft. NOTE WHAT THIS DOES AND DOES NOT ESTABLISH: it proves the walk's geometry, not
that the level was authored, not that anything compiles, and not one cell of the table
above.

## Two gates are free for an empty submission, deliberately

`TwinYardNeverChanges` and `ColdReopenForgetsEverything` both read "nothing has
happened", which an empty submission satisfies. This is declared rather than hidden:

- The first is **mandatory** under the in-scene-control law. It earns its place
  against blanket-restore bugs — a restore that writes one yard's record onto every
  board — not against emptiness.
- The second is the **headline gate against the headline wrong answer**, which is
  the reason this task exists at all.

Two originally-separate cold checks (posts + board, and runner-at-first-pad) were
**merged into one gate** rather than shipped as two, per the DEF-5 denominator audit,
so the free-for-empty count is 2 and not 3. The empty leg is named against a gate it
cannot get free.

## Requirements table

See `../task.md` § *Requirement-to-assertion map* — every prompt requirement, the
gate that checks it, and the window in which that gate stands down.

## Three hazards this fixture is shaped around

1. **A record written to disk survives the WORKDIR.** This is the one hazard that
   fails a *correct* submission. The fixture empties
   `FPaths::ProjectSavedDir()/SaveGames` before anything begins play, and separately
   checks at the first settled sample that the yard opened on the staged numbers.
   Without both, the second run in one workdir (a re-capture, a refgate re-run, a
   `--keep-workdir` iteration) opens warm at t = 0 and the model is blamed for having
   obeyed the prompt.

   **The probe splits its verdict on whether the wipe worked, and that split is
   load-bearing in both directions.** The fixture records, at wipe time — when nothing
   has begun play, so the reading can mean nothing else — whether the directory was
   genuinely gone afterwards. Still there ⇒ an attributed **Error** naming the leftover
   record. Verifiably empty ⇒ a scored **FAIL** under `SessionTallyTracksExactly`,
   because with nothing written down anywhere, the only thing that can have repainted
   or hidden a post before anybody walked into it is the submission's own `BeginPlay`.
   Attributing that case to the workdir as well would hand every submission a
   denominator opt-out requiring no correct behaviour at all — repaint one post in
   `BeginPlay` and the run goes UNGRADED instead of FAILED — and ambiguity resolves
   toward GRADED. **Neither branch touches the empty leg**, which opens on exactly the
   staged numbers with both boards at 0 and passes the probe.
2. **Whatever is done to the record must come AFTER the closing writes, and the whole
   thing inside one tick.** `EndPlay` on a destroyed prop is a legitimate place to
   write the day down, so acting first would leave that submission holding a record
   the fixture never touched. Waiting between the act and the respawn would let a
   submission that flushes on a timer re-create the record inside the window. Destroy,
   act, spawn — adjacent statements — is the only ordering that is both strong and
   fair, and it is the same ordering for all three kinds.
   **The mid-day copy is held in MEMORY, never on disk.** A copy left anywhere under
   `Saved/` would be a second channel the submission could find and read, which is
   exactly the thing the rewind exists to rule out.
3. **A mirror the agent can write is not a display.** `LastShownTotal`,
   `LastShownWorth`, `bLastShownStanding` and `bLastShownLit` live in files the agent
   edits by design. Every sample reads the rendered `FText`, the pillar's visibility
   and the lamp's intensity, and requires the mirror to agree — so a mirror is a
   cross-check and never the evidence.

## Not yet run

Neither leg has been executed, and until the `.umap` is authored neither leg CAN be.
Nothing in this repository was built or run while this task was authored — the orchestrator owns the build. Both cells above are derived
from the sources, not measured; the substrings are quoted from the fixture's literals
rather than from a log. **Treat this file as a prediction until
`cb discriminate --task t3-the-yard-remembers-after-you-leave --wip` has been run
once.** Five things to check on that first run, because they are the cells most likely
to move:

1. that the empty leg names `SessionTallyTracksExactly` and not one of the every-frame
   gates;
2. that the reference's cold reopen really reads 0 on the board rather than tripping
   the opening Error probe;
3. that the reference finishes inside the schedule at all -- the walk is predicted at
   ~160 s (eleven steps, three rebuilds) against a 480 s sentinel, but that prediction
   is arithmetic over the route legs at the substrate's measured 500 uu/s, not a
   stopwatch, and `TheYardDayFinished` is the gate that would catch it being wrong;
4. **that the rewind actually rewinds** -- `SnapshotDurableStores` /
   `RestoreDurableStores` have never executed. Watch for the two log lines
   (`took a copy of the written record: N file(s)` / `put the earlier copy of the
   written record back: N file(s)`) and check `N > 0` on the first. `N == 0` means the
   reference had not written by the snapshot moment, or the path is wrong, and the
   rewind gate would then be indistinguishable from a cold one;
5. **that the reference PASSES `PutBackRecordRulesTheYard` on all three staged days**
   -- run it three times with `-CraftBenchYardSeed=0`, `=1`, `=2`. The clock default
   means an unpinned run samples one day, and day 2's rewind-after-cold is the leg
   with the least margin.
