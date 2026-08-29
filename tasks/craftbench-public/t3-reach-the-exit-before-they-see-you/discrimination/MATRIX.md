# Discrimination matrix — t3-reach-the-exit-before-they-see-you

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs.

**Status: PREDICTED, NOT MEASURED.** Nothing in this task has been built, driven or
graded, **and the map does not exist yet** — `UE-projects/ThirdPerson/Content/Maps/` has
no `t3-reach-the-exit-before-they-see-you/` directory, so `map_locator` cannot resolve
`L_StealthYard` and no L2 leg can start. The fixture
(`Source/CraftBenchTests/Tasks/t3-reach-the-exit-before-they-see-you/
StealthYardFunctionalTest.{h,cpp}`) and the map script (`authoring/author_map.py`) are
written, and the script's own solvers have been RUN offline against its constants (every
number in the table below is that run's output, not hand arithmetic), but no UBT build,
no map authoring, no PIE run and no `cb discriminate` has happened. Every "Overall" and every
substring below is a **contract on the run**, not an observation: `cb discriminate` must
reproduce this table before the task is done, and any cell it contradicts is this file's
error, not the fixture's. Read the two `Named substring(s)` cells as *"the fixture shall
print this"*.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS | `Test Completed. Result={Success}` | One tick on the mast, in a fixed order: read the plate's number (a change re-arms and clears the remembered set), stand down and return while a round is over, then for each watcher work out from **its own** reach, **its own** view width and **its own** live facing whether it can see the runner with nothing solid on the flat line between them, throw that watcher's lamp on the answer, end the round caught if anybody sees — **remembering exactly who** — and away if nobody does and the gate says somebody is standing in it, and finally either stand the whole yard down (everybody still, the remembered lamps still burning) or put every watcher back on **its own** base pace. Nothing in it knows which watcher is which or which round is which, which is exactly why the watch change costs it nothing. |
| `empty` | FAIL | `ExactlyOneLampBurnsOnTheBoard: ` | The unmodified scaffold compiles, so L1 is green — nothing is unimplemented, everything is merely unwired. The three mast lights, the three head lamps, every watcher's pace and the plate's counter all exist and work; nothing calls any of them. The yard is therefore wrong on its **first judged frame**, before any trigger has fired: all three board lights ship dark and the prompt says exactly one burns at any moment. |

Both legs run twice, at `-FPS=60` and `-FPS=20`, in separate PIE processes; all legs must
pass.

**Where the empty leg dies, and where it would die next.** It dies at the FIRST JUDGED
frame — about 0.4 s of world time in, once the run's opening settle window has passed and
well before the first checkpoint at 8 s — inside `Tick`, before the drive has taken a
step. `ExactlyOneLampBurnsOnTheBoard` reads the mast's three light intensities directly
and finds none burning. That is a deliberately shallow death, and it is why the
counterfactual matters. If that gate were removed the empty leg would still fail, in this
order:

1. `TheYardStandsDownWhenTheRoundIsOver` on the first judged frame after the model's
   round 1 ends — **twice over**: every watcher is still pacing at its base pace (half a),
   and the lamps that should be burning are the ones that caught the runner while none
   are (half b, `the burning head lamps should be exactly {watcher N}, and they are {}`).
2. `TheTruckMakesAShadowWhileItPasses` when the truck lets go of the line and the board
   never reads caught.
3. `EveryRoundStartsCleanWhenThePlateClicks` 0.4 s after the plate first reads 1, since
   the running light is not burning either.

**The counterfactual is no longer degenerate on the lamp channel.** In the build reviewed
on 2026-08-19 it was: `EachWatcherShowsWhatItCanSeeRightNow` was cited as the empty leg's
second death (`expected the burning head lamps to be exactly {watcher 1}, found {}`) and
that string could never be printed, because the model's visible set is empty on every
frame that gate can run — seeing the runner ends the round. The lit half now lives in
`TheYardStandsDownWhenTheRoundIsOver` and the substring above is the one it prints.
**Every item is a prediction, not an observation.**

**Dead-gate audit (DEF-5).** Because the empty leg dies on the first judged frame,
**nine of the eleven gates are never reached at all**. They are **unreached, not free points**, and the
discriminate report must say so rather than scoring them. One gate,
`TheYardIsNotYoursToRewire`, an empty delivery banks for free on purpose — it is a
scope/precondition gate, and its whole value is that it stops a submission from making the
fixture's own model agree with a lie (a watcher parked on the runner).

## The numbers the fixture will actually solve

**PREDICTED — computed by running the map script's own solver arithmetic offline
(`author_map.py::solve_shadow_spot` / `solve_split_spot`), never measured in the engine.**
The fixture re-derives every one of these at run time from the placed level and refuses to
start (HARNESS-PRECONDITION, never a graded FAIL) if any floor is missed, so a later map
drift reports itself instead of failing a correct submission.

| Quantity | Predicted value | Floor the fixture enforces |
| --- | --- | --- |
| Lane | straight at `y = -1400`, plate `x = -5800`, gate `x = +5800` | — |
| Rounds | Centre `y=+200` x∈[-1200,1200]; North `y=+2000` same span; Walled `y=+4200` x∈[-1000,1000] | three rounds, two posts each |
| Watcher NEAR (watch 1: Centre) | reach 2,000, view width 40°, base pace 120 (a 40.0 s lap) | — |
| Watcher FAR (watch 1: North) | reach 3,100, view width 30°, base pace 220 | — |
| Sentry WALLED (never re-staged) | reach 6,400, view width 75°, base pace 260 | ≥1.25× every other reach **after** the watch change, and strictly the widest view |
| Watch change | NEAR and FAR trade rounds; NEAR's view width ×0.6 → 24°, its base pace ×1.25 → 150; FAR's reach ×1.2 → 3,720 | — |
| Shadow spot | `(-1393, -600)`, 800 uu off the lane round | ≥400 uu from every round, ≥250 from every solid thing |
| Shadow window | **7.33 s** of continuous sight, **6.33 s / 6.33 s** clearance to the two turns | ≥3.0 s window, ≥2.0 s clearance |
| Truck cover on that line | **2.31 s** at the window's worst phase, and it lets go again | ≥1.5 x `kMinTruckCoverS` = **2.25 s**, and it must clear |
| Truck itself | rail at `x = -760`, half-span `(0, 415)`, **150 uu/s**, footprint half `(350, 150, 220)` | its swept footprint must clear the lane round by 200 uu and the lane by 250 uu, which is what boxes the rail in |
| Shadow ENTRY (the drive's own wait) | **4 distinct departure windows in the first 400 s** — ~65 s (3.05 s wide), 145 s, 265 s, 345 s; walking in then arrives unseen whether the runner stops short or long, holds cover past the floor, and the truck lets go while the cone still holds | phase 2's deadline covers ~292 s from its own start, so three of the four are reachable |
| Governor releases, watch 2 | worst wait over every relative lap phase: **11.8 s** (the long western hop); every leg releases | a leg that never releases stalls its phase to a HARNESS-PRECONDITION |
| Split spot | `(3065, -1400)` — on the lane | invisible to all three on watch 1 |
| Round-3 crossing | **2.67 s** of continuous sight, **4.12 s** clearance to both turns | ≥1.0 s window, ≥2.0 s clearance |
| Control (sentry) | holds **11 of 25** route points with the wall taken away, **0 of 25** with it there | 0 with the wall; ≥⅓ without it |
| Safe lane bands | watch 1: the whole lane. watch 2: `[-5800,-3700]`, `[-1500,1500]`, `[4600,5800]` | at least one band per watch |
| Drive | 18 phases (0-17), **~370 s** modelled on the first shadow window and **~570 s** on the third; 68 checkpoints every 8 s to 544 s; **SENTINEL at 640 s** | the three numbers are `kGradedCheckpoints` / `kCheckpointEveryS` / `kSentinelAtS` verbatim; per-leg L2 wall clock is UNMEASURED and is an orchestrator check |

**`../task.md` now carries these same numbers** (its old "worked geometry" table was a
different, earlier layout and has been replaced by the solver output). The three ways the
original design had to move are kept here because they are the reasons the layout looks
the way it does:

1. **The design's shadow spot was unreachable.** With the lane round's watcher at
   reach 1,900 / view width 26°, the cone bound at the lane's 1,600 uu offset
   (`1600/tan 26° = 3,280`) exceeds the reach bound (`sqrt(1900² − 1600²) = 1,025`), so
   that watcher can never hold **any** point of the lane and there was no shadow window
   at all. Resolved by moving the shadow spot **off** the lane (850 uu from the lane
   round instead of 1,600) and widening that watcher to 2,000 / 40°, which keeps the
   split spot 1.36× out of its reach.
2. **The truck had to move to have anything to shadow.** Its rail is now at `x = -760`,
   west of the lane round's middle and clear of the split spot's sightline by
   construction — the map script and the fixture both refuse the level if the truck's
   swept rail touches any line inside the crossing window.
3. **The split spot moved from 3,400 to 3,065** because it is now solved from the window
   rather than written down: the crossing is centred in the round so both ends are
   mid-leg with equal clearance.

## Requirements table

The full prompt-requirement to gate mapping is in `../task.md` under
**Requirement-to-assertion map**. It has 20 rows; every one names the gate that checks it
and the condition under which that gate is skipped, and **two of them say in the third
column that no judged frame can distinguish them** (inclusive edges, and flat-versus-3-D
measurement — both sit inside the fixture's own marginality suppression). Those two are
disclosed so a correct submission cannot diverge from the model, not because they
discriminate; counting them as graded requirements is how a requirement count gets
inflated.

## Which gate names which wrong answer

Written down because the precedence table makes this deterministic, and because a gate
whose named failure is always stolen by another gate is a dead gate. **Every row is a
prediction.**

| Wrong answer | Dies at | When |
| --- | --- | --- |
| nothing at all (the empty stub) | `ExactlyOneLampBurnsOnTheBoard` | the first judged frame, before the drive moves |
| **sight evaluated only when a watcher reaches a post**, or on a 1–2 s re-scan | `TheTruckMakesAShadowWhileItPasses` first, then `SeenTheMomentTheyCross` | round 1's truck-clear (0.4 s deadline, 6.33 s from either turn) and round 3's mid-leg crossing (a 2.67 s window with 4.12 s of clearance at both ends). THE primary wrong answer, and it has two independent deaths so it cannot survive on luck |
| one shared sight radius, or the first watcher's numbers used for all three | `EachWatcherSeesWithItsOwnEyes` | the split spot: out of reach for the watcher covering it on watch 1 (its reach × sin(view width) is 1,286 uu against the lane's 1,600 uu offset, so it can never hold **any** lane point), squarely inside a 2.67 s window for a *different* watcher on watch 2 |
| range only, no view-width test | `EachWatcherShowsWhatItCanSeeRightNow` | the first judged frame — it lights the walled sentry, whose 6,400 uu reach covers a lane it can never see |
| a cone test that never asks what is in the way | `EachWatcherShowsWhatItCanSeeRightNow` | whenever the walled sentry faces south — 11 of 25 sampled route points are inside its reach and view width with the wall taken away |
| the blocker set gathered once at `BeginPlay`, or a baked visibility map | `TheTruckMakesAShadowWhileItPasses` | phase 2, while the truck's live footprint is on the line and the lamp must be dark |
| `if (AtGate) Outcome = Away;` written after the sight test | `CaughtIsFinalEvenAtTheGate` | phase 5, the first walk into the gateway after round 1 was lost |
| **the stand-down lamps RE-DERIVED instead of remembered** | `TheYardStandsDownWhenTheRoundIsOver` | phases 4-5 and 13-14, once the runner has walked out of the frozen cone: the yard shows `{}` where it owes `{the watcher that caught you}`. The third named wrong answer, and the only one that cannot be recovered by asking the world again |
| a one-shot latch, never re-armed | `EveryRoundStartsCleanWhenThePlateClicks` | 0.4 s after the plate reads 2 — round 2 opens still showing round 1's caught |
| lamps driven straight off the instantaneous sight test (stand-down missed) | `TheYardStandsDownWhenTheRoundIsOver` | phase 9, standing squarely inside a frozen watcher's live reach and view width |
| watchers never stopped when a round ends | `TheYardStandsDownWhenTheRoundIsOver` | the first judged frame after round 1 ends (pace non-zero) |
| one flat pace written to every watcher, or a base pace cached at `BeginPlay` | `EveryRoundStartsCleanWhenThePlateClicks` | round 3, after the sergeant multiplies one base pace by 1.25 |
| `BasePaceUuPerSec` written instead of `PaceUuPerSec` | `TheYardIsNotYoursToRewire` | the frame it does it |
| a correct internal outcome enum and no light thrown | `ExactlyOneLampBurnsOnTheBoard` | the first judged frame |
| away set without clearing running (two lights burning) | `ExactlyOneLampBurnsOnTheBoard` | phase 8, the frame the round is won |
| the runner's own capsule left in the trace, so nothing is ever seen | `TheTruckMakesAShadowWhileItPasses` | phase 3 — the truck lets go and the board never reads caught |
| lamps switched off wholesale at stand-down (the reading the prompt no longer pre-empts) | `TheYardStandsDownWhenTheRoundIsOver` | the first judged frame of round 1's stand-down |
| a watcher parked on the runner | `TheYardIsNotYoursToRewire` | the frame it leaves its round by more than 60 uu |

## Three claims this file used to make that were FALSE, and what replaced them

Kept rather than deleted, because a discrimination contract that quietly drops a row it
could not have reproduced is how the next one gets written the same way.

1. **"The loop runs in both directions … perception wrong fails
   `EachWatcherShowsWhatItCanSeeRightNow`."** True only for the DARK half. That gate can
   only ever run with the model's visible set empty (seeing ends the round), so the lit
   half — and with it the whole per-watcher lamp requirement, Hard Rule 12's negative
   control and Hard Rule 13's visible readout for the perception channel — was free. Now
   carried by `TheYardStandsDownWhenTheRoundIsOver`'s set equality against the latched
   catcher set.
2. **"The sight test written after the gate test … dies at
   `TheTruckMakesAShadowWhileItPasses`, phase 3."** Unreachable by construction: staging
   precondition 9 keeps the gate 1.31x outside every watcher's largest reach, so no frame
   can have both endings available and the two orderings never diverge. The rule is out
   of the prompt and off this table.
3. **"Phase 5: walk into the gate volume, out, and in again."** The out-and-in leg was
   never planned — one walk to the gate centre, and the gate-entry bookkeeping sat behind
   a round-is-over early return that phase 5 always trips — so the phase could never
   complete and the run ended as a harness error at phase 5 of 18. Both halves are fixed;
   the walk is now gate, back 900 uu down the lane, gate.

## What carries the discrimination without variants

**Two ending-producing windows, both timed against the covering watcher's turns.** Round 1
ends when the truck clears the line; round 3 ends when the cone crosses the runner mid-leg.
Both carry the same 0.4 s deadline, and the fixture **measures** the window and the
clearance from the placed level and refuses to start if either is under its floor. That is
the whole anti-poller design, and it is measured rather than trusted.

**The split spot means opposite things on the two watches.** The identical standing place
is held for a full lap on watch 1 with nobody seeing anything, and again on watch 2 after a
*different* watcher takes that round with its reach multiplied by 1.2. The run-level check
refuses to report a pass unless the two holds gave **opposite** answers — a run in which
they agreed proves nothing about per-watcher eyes, and that is a fault in the yard, not in
the submission, so it exits HARNESS-PRECONDITION.

**The negative control is in the scene, not in time.** The walled sentry has the largest
reach and the widest view width in the yard — after the watch change's multipliers are
applied — and its round is behind a solid wall that crosses every line from every phase of
it to every point of the route. Its lamp is gauged inside a two-sided set-equality gate on
every judged frame, **and again at every checkpoint whatever the suppression**, because it
can never be marginal about anything.

**The loop runs in both directions.** Perception right and the feedback wrong fails
`TheYardStandsDownWhenTheRoundIsOver`; the feedback right and perception wrong fails
`EachWatcherShowsWhatItCanSeeRightNow`. Neither gate can be satisfied by the other's work.

**Every load-bearing number is read off the actors and appears nowhere in the prompt** —
each watcher's `SightReachUu`, `SightHalfAngleDeg`, `BasePaceUuPerSec` and `RoundTag`, the
truck's live transform, the blockers' footprints, the plate's `RoundIndex` — and the
fixture re-reads every one of them by name, live, every frame. A hard-coded reach, cone,
pace or blocker set is wrong from the first frame rather than at some late checkpoint.

**The drive cannot manufacture a failure by walking into a cone.** Every transit taken
while a round is still running is released only once the fixture has simulated all three
watchers forward **over the transit itself** and proved that no point of the leg can be
seen before the runner gets there, with the truck deliberately excluded from that
prediction (a moving occluder can only ever help, so ignoring it is the safe direction). A
walk that is not provably safe is not taken, it is waited out — measured worst wait on the
second watch, over every relative phase of the covering watcher's lap: 11.8 s.

Two bounds on that rule are what make it usable rather than paralysing, and both were
absent from the reviewed build. The horizon is the **transit**, not a fixed span of
seconds: two of the places this drive stands are places a cone is meant to sweep, so a
governor demanding safety after arrival could release neither walk and the drive stalled
at phase 4. And the governor is **skipped once a round has ended**, because three of the
drive's most important walks start or end somewhere a watcher can plainly see and being
seen changes nothing about a round that is already over.

**The one walk the governor cannot prove is waited out instead.** Stepping into the
truck's shadow is safe only while the truck is in the way, so the drive holds on a lane
rest point nobody can see and commits only when its own forward simulation of the cone and
the rail says that leaving now arrives unseen, arrives inside a stretch where the cone
holds the spot and the truck lies across the line, holds it past the cover floor, and then
watches the truck let go while the cone still holds. Without that wait the entry is a coin
toss that ends round 1 on arrival about half the time — a manufactured staging fault, not
a measurement.
