---
id: t2-race-clock-bp
substrate: ThirdPerson
set: bp
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_RaceArena :: ARaceTheClockFunctionalTest"]
fps_legs: [60, 20]
introspect: [t2_race_clock_bp.py]
---

# t2-race-clock-bp

The Blueprint leg of a surface pair. `cpp/t2-race-clock-cpp` is
the other one. **Same map, same fixture, same checkpoint schedule, same named
gates, same framerate legs** - the only difference is which surface the answer is
written on, which is what makes the pair a measurement of the surface rather
than of two designs. Nothing is re-tuned for this leg: a re-tuned gate would
measure the tuning.

## Provenance

The behaviour is `cpp/t2-race-clock-cpp`'s, itself imported from
the Startup Eval corpus row `t2-score-attack` (owner: *agree* - "We could deduct
it to 10 seconds to be quicker", so the round is **10.0 s**). Read that leg's
`notes.md` for the corpus deltas; none of them are re-litigated here.

**Why the pair exists at all.** The benchmark's thesis is a (model x tool x SURFACE)
interaction, and the surface axis was carried by six `gp-` pairs alone: every
task whose graded actor is PLACED in the committed map was C++-only, because
`Content/Maps/` is deny-write to agents, so a Blueprint subclass would never be
instantiated. That is now solved in the shared L2 base class, and the mechanism
is recorded here so the next reader does not re-derive it wrongly.

`ACraftBenchFunctionalTest` (`Source/CraftBenchTests/CraftBenchFunctionalTest.h`
/ `.cpp`, the SURFACE lane block, landed 2026-08-20) owns four calls:

- `ResolveGradedBlueprintClass(UClass* PlacedClass)` - the single Blueprint under
  `/Game/Tasks` (recursive) whose `GeneratedClass` is a strict, non-abstract
  subclass of the placed class, or `nullptr` (the C++ lane, where the placed
  instance is the answer). TWO candidates raises `HARNESS-PRECONDITION` rather
  than picking one, because grading a submission the agent may not have meant is
  not a verdict.
- `SwapForGradedBlueprint(AActor* Placed)` - spawn that Blueprint at the placed
  transform, carry every tag over (downstream lookups are by tag), destroy the
  placed one.
- `SwapAllForGradedBlueprint(TArray<AActor*>&)` - the same over every instance of
  ONE class, rewriting the array in place; it refuses a MIXED array, because a
  half-swapped row grades C++ for some instances and Blueprint for the rest,
  which is a verdict about neither surface.
- `SwapAllForGradedBlueprintRepossessing(TArray<AActor*>&)` - the same plus
  re-possessing player 0. **Not used by this task**: the graded classes here are
  props, not the pawn.

This task's fixture calls **`SwapAllForGradedBlueprint` for the seven coins and
`SwapForGradedBlueprint` for the one round marker**
(`RaceTheClockFunctionalTest.cpp:165-166`), then re-resolves both by tag and
re-asserts the authored counts, so a half-completed swap reads as
HARNESS-PRECONDITION rather than as a graded failure of the submission. The two
agent classes are unrelated, so each resolves against its own placed class and
they cannot collide. **No C++ was written for this leg** - all four calls were
already wired.

## Primary concept

- `game-mode-and-game-state` - Game Mode and Game State
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/game-mode-and-game-state-in-unreal-engine)

What the verifier checks most directly is an authoritative, readable round
state: a score that only ever changes for a cause, a countdown that expires at a
declared deadline, an exclusive terminal transition, and a scoring rule frozen
by that transition. The on-screen readouts are how a human sees that state and
how the verifier gauges it; the state itself is the concept.

## Composed concepts

- `ps-bp-overview` - Blueprints Visual Scripting Overview
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/blueprints-visual-scripting-in-unreal-engine)

## Prompt given to the agent

> Deliver your solution **entirely as Blueprint assets** created in the editor
> and saved under `Content/Tasks/t2-race-clock-bp/`. **Do not add
> or modify any C++ source for this task.**
>
> This level is a coin arena and nothing in it works: the clock never moves,
> walking into a coin does nothing, and the three on-screen readouts show
> frozen placeholder text. Make it a round.
>
> A round starts when play begins and runs for exactly **10.0 seconds**. Seven
> coins sit on the floor, each carrying its own point value in its `PointValue`
> property (the values differ; each is between 5 and 100).
>
> - Walking the character into a coin while the round runs consumes it - it is
>   no longer visible where it stood - and raises the score by exactly that
>   coin's own `PointValue`. A consumed coin never scores again, even on a
>   return trip across its spot.
> - The score starts at 0 and only ever changes because a coin was contacted.
> - The clock counts down from 10, reaches zero within **0.5 seconds** of
>   10.0 seconds of play (no earlier, no later), and never shows a negative
>   number. It also has to be roughly right *while* it runs, not only at the
>   end: at any moment of the round, `TimeRemaining` is within **1.0 second** of
>   the seconds actually left, and after the round ends it reads **0** - clamped,
>   never negative. Play begins at world time zero, and that is the instant the
>   10.0 seconds are measured from.
> - Before zero the round reads `InProgress`; at and after zero, `TimedOut` -
>   and those two words are the **only** values it ever takes, at any moment,
>   including during the transition.
> - After zero the score is final: contacting any coin still on the floor adds
>   nothing, ever.
> - The round marker exposes the three values an outside observer reads -
>   `Score` (whole number), `TimeRemaining` (seconds), `RoundState` - and all
>   three stay current throughout.
> - The readouts named exactly `ScoreText`, `ClockText` and `StateText` stay
>   findable on screen, each showing its live value and nothing else: the
>   score, the remaining whole seconds (round however you like), the round's
>   word. All three stay live and correct after the round has ended.
> - A coin the character never walks into is never consumed, never scores, and
>   keeps its own point value. It may idle however you like - bob, spin, glint -
>   as long as it stays where it was placed.
>
> Do not edit the level, any config file, or any test file.

> **Two more things, both of which a reviewer notices in the first ten seconds
> of playing and no headless check had been asking for.**
>
> The three readouts must **turn to face the character**. A board somebody has
> to walk around to read is not a readout, and one that stares at a fixed
> compass point is only legible from wherever it happens to be pointing.
>
> And the arena carries a **replay pad**: a lit plate on the floor in front of
> the board. Once the round has timed out, **stepping onto that pad starts a
> fresh round** - full clock, no score. Nothing else may restart it, and
> somebody who was already standing on the pad when the whistle went does not
> get an endless string of rounds: they have to step off and on again.

## Workspace state pre-task

**Deliverable root: `Content/Tasks/t2-race-clock-bp/`, Blueprint
assets only.** No C++ file may be added or changed; the C++ that ships is
read-only reference material for what you can call. Files written anywhere
outside that folder are a sandbox reject (exit 4), not a graded FAIL.

What the level already carries, all of it working:

- Seven coins on the floor, each visible, each with a contact region about 60 cm
  around itself that already detects the character walking in, and each carrying
  its own editable `PointValue`. **Nothing responds to the contact and nothing
  scores.**
- One round marker: three readouts named exactly `ScoreText`, `ClockText` and
  `StateText` floating over the floor, and three values an observer can read -
  `Score` (whole number, 0), `TimeRemaining` (seconds, 10.0) and `RoundState`
  (the word `InProgress`). The marker is ticked every frame. **No countdown, no
  state transition, no scoring**, and all three readouts show frozen placeholder
  text bound to nothing.
- A replay pad in front of the board: a lit plate with a volume over it and a
  lamp that lights while somebody is standing there, plus one call that answers
  whether somebody is on it right now. **Supplied and working end to end.
  Nothing here knows what a round is.**
- A character the player controls, spawned and possessed by the level's own game
  mode, visible, and drivable with WASD by a human pressing Play.

Nothing in the level decides what a round is. That is the whole task.

## Verifier specification

**Identical to the C++ leg, ported verbatim** - same committed map
(`Content/Maps/t2-race-clock/L_RaceArena.umap`), same fixture
(`ARaceTheClockFunctionalTest`), same 14-instant checkpoint schedule plus its
sentinel, same waypoint drive, same tolerances, same gate names and same failure
literals, and the same `fps_legs: [60, 20]` framerate legs. The full description
lives in `cpp/t2-race-clock-cpp`'s `## Verifier specification`;
nothing is re-tuned for this surface, because a re-tuned gate would measure the
tuning rather than the surface.

The shape, in one paragraph: the fixture resolves the round marker, the seven
coins, the replay pad and the collector BY TAG, reads each coin's `PointValue`
and the marker's three values BY REFLECTION, performs the surface swap described
under *Provenance*, then drives the character along the `Y = 0` line through four
coins, HOLDS until the clock is safely past zero, walks through two more, and
finally stands on the replay pad. Everything about the clock, the state word, the
score and the three readouts is checked EVERY TICK against the fixture's own
clock and its own running total; the gates that would be vacuous unless their leg
happened (the round ended, four coins were consumed, the after-whistle coins were
reached, a second round ran) are evaluated at the sentinel with their own
literals.

**What this leg adds, and only this:** an L2I introspect leg
(`t2_race_clock_bp.py`) that structurally proves the things L2
graded really were Blueprints - for BOTH agent classes, since this task delivers
two. Proving a Blueprint *exists* is not enough: a C++ solve shipped beside a
conforming Blueprint would pass L2 on the C++ and pass a naive existence check on
the asset. See the introspect script's own header, including the one hole it
CANNOT close on this task (an in-place edit of the supplied scaffold), recorded
in *Hidden invariants* below.

## Requirement-to-gate map

Gate names are the shipping fixture's
(`Source/CraftBenchTests/Tasks/t2-race-clock-cpp/RaceTheClockFunctionalTest.cpp`).
Note that the `-cpp` spec's own table names an eight-checkpoint schedule from an
earlier draft; the schedule in the code is 14 instants plus a sentinel, and the
gate NAMES are the same in both.

| the prompt says | the gate that checks it | skipped when |
|---|---|---|
| coin contact raises the score by exactly that coin's own value | `CoinAddsItsOwnValue`, every tick, against a fixture-owned running total | never - the sentinel FAILs if fewer than four coins were consumed inside the round, so it cannot go unmeasured |
| a consumed coin is no longer visible where it stood | the same gate's visibility test (destroyed, hidden, or moved far off its spot) | never |
| a consumed coin never scores again | the drive re-crosses all three consumed spots; `CoinAddsItsOwnValue` plus `ScoreOnlyRisesFromCoins` | never |
| the score starts at 0 and only changes for a cause | `ScoreOnlyRisesFromCoins` (never falls) plus `CoinAddsItsOwnValue` (exact expected total) | never |
| the clock reaches zero within 0.5 s of 10.0 s | `RoundRunsForTenSeconds`, both directions, measured from THIS round's start | never |
| the clock is within 1.0 s of the seconds actually left | `ClockTracksTheRound`, every tick | never |
| the clock never shows a negative number | `ClockNeverGoesNegative`, every tick | never |
| after the round ends the clock reads 0 | `ClockReadsZeroWhenTheRoundEnds`, at the instant the state flips | never |
| `InProgress` before zero, `TimedOut` at and after | `RoundRunsForTenSeconds` | never |
| those two words are the ONLY values, at any instant | `RoundStateIsOneOfTwoWords`, tick-wide, no window | never |
| after zero the score is final | `ScoreIsFinalAfterTheRound` - the score may not change, AND no coin may be consumed, after the whistle; two real post-deadline contacts | never |
| the three exposed values stay current | every gate above reads them by reflection; a name that cannot be read is a HARNESS-PRECONDITION, not a FAIL | never |
| the three named readouts show their live values, during and after | `ReadoutsShowTheLiveValues`, read by COMPONENT NAME, every tick | a numeric readout carrying no parseable number is skipped on that channel; the state channel has no such escape |
| the readouts turn to face the character | `TheReadoutsFaceYou`, sampled every frame, judged over the whole run | never |
| stepping on the pad after the whistle starts a fresh round | `TheRoundCanBeRunAgain` (a second round happened, from no score) | never |
| nothing else may restart it | `TheRoundOnlyRestartsFromThePad`, read off the PAD'S OWN LAMP, never a hand-chosen radius | never |
| a coin nobody walks into is untouched and stays put | `TheUntouchedCoinSurvives` - exists, visible, on its spot, own value - every tick and again at the sentinel | never |
| Blueprint assets only, no C++ added | L2I `t2_race_clock_bp.py` | never - L2I is declared, so a missing script is exit 7, not a pass |

**Pass criteria**: both L1 targets green, L2 green **at both framerate legs**, and
L2I green.

## Reference solution metadata

`reference/Content/Tasks/t2-race-clock-bp/` - TWO Blueprints, one
per agent class (`BP_RaceCoin` deriving from the coin, `BP_RaceRound` deriving
from the round marker), authored in an attended editor session because there is
no script lane for Blueprint graph authoring in this repo. The recipe is
`REFERENCE-NOTE.md`, precise to the node and the pin so the assets can be
rebuilt without re-deriving the design.

- Asset-graph size, predicted: ~15 nodes on the coin (contact, ask the round, add
  own value, consume itself) and ~35-45 on the round (countdown, the terminal
  flip, the clamp, three readout writes, the facing update, the step-on-the-pad
  replay). Equivalent to the ~130 LOC of the C++ leg's reference.
- Files: 2 new `.uasset`s. Zero C++ edits - and any C++ edit is a surface
  violation on this leg.
- Senior-dev hours: 2-3. The graph is not hard; the pin-level traps in
  `REFERENCE-NOTE.md` are where the time goes.

**Not yet true:** the assets do not exist yet and this leg has never been graded.

## Anti-gaming notes

1. **A score that is not caused by the coin it hit** - a constant amount, a
   plausible total written outright, a score that rises on a timer, a one-shot
   latch that scores only the first coin, or a consumed coin that scores twice.
   *Defense*: `CoinAddsItsOwnValue` computes the expected total from the
   `PointValue` the fixture reads off the coin actors themselves and asserts the
   exact running total at the tick each coin visibly goes; the trigger fires four
   times inside the round; the drive re-crosses all three consumed spots; and
   `ScoreOnlyRisesFromCoins` FAILs a score that ever falls. **Weakened on this
   leg** - see *Hidden invariants*, "the per-coin values do not survive the
   swap": the values the fixture grades against are all one number here, so a
   constant per-coin amount equal to that number is NOT caught on this leg,
   though it still is on the `-cpp` leg.
2. **Frame-count overfit on the countdown.** *Failure mode*: the round ends after
   600 ticks rather than 10.0 seconds of play. *Defense*: `fps_legs: [60, 20]`
   runs the identical fixture in two independent PIE processes; a 600-tick round
   expires at 30 s in the 20 Hz leg and FAILs `RoundRunsForTenSeconds` there.
3. **Freeze-everything-early.** *Failure mode*: scoring is frozen, or `TimedOut`
   is set, well before the deadline, which satisfies every post-whistle gate for
   free. *Defense*: the fourth coin is collected late and its exact value must
   have landed while the state still reads `InProgress`; `RoundRunsForTenSeconds`
   FAILs any state other than `InProgress` before 9.5 s into the round.
4. **Spoofed observables.** *Failure mode*: a readout animates while the
   authoritative value never moves (or the reverse); a coin is hidden without
   scoring; the score is written at play start. *Defense*: every readout is gated
   against BOTH the fixture's own clock/total AND the authoritative property,
   with distinct named failures, so "the readout is wrong" and "the value is
   wrong" never collapse into one verdict; coin disappearance and score delta are
   asserted as a PAIR. What is deliberately **not** a defense: the route the
   readouts were authored by. That is an advisory log line, never a FAIL.
5. **Shipping C++ next to a conforming Blueprint.** *Failure mode*: the answer is
   written in C++ and a decorative Blueprint is shipped beside it, passing L2 on
   the C++ and a naive existence check on the asset. *Defense*: L2I reproduces
   the fixture's own resolution for BOTH agent classes - the same strict-subclass
   test, the same `/Game/Tasks` scope and the same `CLASS_Abstract` skip - and
   requires the resolved answer to be Blueprint-generated with no native subclass
   of either placed class present; the scaffold classes themselves are exempt by
   EXACT `/Script/` path, never by name. Reproducing the resolution *exactly* is
   the whole design: a stricter grader would condemn a Blueprint-only submission
   that happens to factor an abstract parent, which is the surface leg failing the
   surface it exists to confirm. **Its limit is stated in *Hidden invariants***: a
   C++ answer written IN PLACE into the supplied scaffold creates no subclass and
   is not caught structurally.
6. **Test disabling / environment repointing.** *Defense*:
   `Source/CraftBenchTests/` is sandbox-denied, the runner materializes the graded
   substrate from git HEAD (an on-disk edit never reaches the grade), and
   `Content/Maps/` plus `Content/Characters/` are deny-listed. This spec declares
   no `config_allow`, so every ini diff rides the exit-4 path.

## Hidden invariants

- **THE PER-COIN VALUES DO NOT SURVIVE THE SWAP, and this is the one real
  measurement asymmetry of the pair.** `SwapAllForGradedBlueprint` spawns the
  Blueprint class at each placed transform; it carries the TRANSFORM and the TAGS
  and nothing else, so the map's per-instance `PointValue` overrides (15, 40, 25,
  60, 35, 90, 100 - `authoring/author_map.py` on the `-cpp` leg) are replaced by
  the Blueprint class default on all seven coins. The fixture reads `PointValue`
  off the coins AFTER the swap, so the grade stays self-consistent and a correct
  submission still passes - but on this leg every coin is worth the same, the
  prompt's "the values differ" is not true at grade time, and the hidden-value
  defense in anti-gaming note 1 does not bite. Two consequences: (a) the
  Blueprint coin MUST carry a non-zero default `PointValue`, or the fixture
  raises HARNESS-PRECONDITION ("a coin carries no PointValue") and the run says
  nothing at all; (b) do not read a `-bp` PASS as evidence against a hardcoded
  per-coin constant. Fixing it properly means copying per-instance property
  values across the swap in the shared base class, which is out of scope here and
  is filed as a finding, not patched.
- **THE SWAP FRAME CAN FAIL A CORRECT SUBMISSION, and no Blueprint can prevent
  it.** This is the one open question about whether the leg is gradable as
  written, and it has to be answered BEFORE the first grade. It is a harness
  artefact of the surface lane, not a property of any submission.

  On the `-cpp` leg the round marker is PLACED, so it has been ticking since
  world time ~0 and its `TimeRemaining` equals the fixture's own `TrueRemaining`
  on every frame the fixture ever looks. (The `-cpp` reference does NOT stamp its
  round start in `BeginPlay`: `RoundStartedAt` keeps its `0.0` default
  (`reference/.../RaceRoundBase.h:73`) and only `StartFreshRound` writes it
  (`.cpp:81`). The two legs' designs are IDENTICAL - only when the graded actor
  starts existing differs.)

  On this leg the marker is SPAWNED during `PrepareTest`
  (`RaceTheClockFunctionalTest.cpp:166`), so between the spawn and its own first
  `Tick` it still reports the class default `TimeRemaining` of 10.0. The fixture
  meanwhile anchors the first round at `RoundStartedAtWorld = 0.0`
  (`RaceTheClockFunctionalTest.h:80`, *not* `.cpp:80`) and computes
  `TrueRemaining = 10.0 - Now`, and `ClockTracksTheRound`
  (`RaceTheClockFunctionalTest.cpp:449`) is unconditional with a 1.0 s allowance.
  So on that one frame the measured drift is exactly `Now` - **the world time at
  the fixture's first graded tick, with no dependence on the submission at all.**

  Three facts make the window real rather than theoretical: `bIsRunning` is set
  in `AFunctionalTest::RunTest` (engine `FunctionalTest.cpp:357`) BEFORE it calls
  `PrepareTest` (`:361`), so `IsRunning()` is already true on the frame of the
  swap; the L2 base's tick gate is only `if (!bStarted || !IsRunning()) return;`
  (`CraftBenchFunctionalTest.cpp:104`), with no first-frame grace; and the spawned
  marker and the fixture tick in the SAME tick group, whose internal order is not
  something a Blueprint gets to choose.

  **The window is exactly one frame wide and the recipe already picks the
  minimum-exposure design.** Every alternative converts a one-frame drift of
  `Now` into a PERMANENT drift of the same size: stamping `RoundStartedAt` in
  `BeginPlay` (`REFERENCE-NOTE.md` trap R1) shifts the whole round late by the
  swap delay, and writing `TimeRemaining` in `BeginPlay` (trap R2) shortens the
  `RoundSeconds` that `ResolveStaging` reads by the same amount. There is nothing
  left for a Blueprint author to do about it.

  **So the leg is gradable iff the world time at the fixture's first graded tick
  is <= 1.0 s** - and that number is set by the automation pre-roll, not by
  anything either leg delivers, so it is measurable **token-free today off the
  `-cpp` leg**: read `[CB-CP] idx=0 t=` (or `[t2-race calib] cp0 t=`) out of the
  existing L2 log at BOTH framerate legs. Weak existing evidence that it is
  small: the `-cpp` `discrimination/MATRIX.md` records four coins banked by
  `t=4.0`, which the drive could not manage if grading had only begun at 3-4 s.
  Check **20 Hz first**: if the pre-roll is counted in FRAMES rather than
  seconds, a fixed frame count buys 3x the world time at 0.05 s/frame that it
  does at 1/60 s/frame, so 20 Hz is where a marginal offset crosses 1.0 s. The
  failing signature survives the FAIL, because `LogCalib` runs inside the base's
  checkpoint loop BEFORE the subclass's clock gate: a
  `[t2-race calib] cp0 t=<over 1.0> ... remain=10.00` line, immediately followed
  by `ClockTracksTheRound: the clock read 10.00 with <10 - t> seconds actually
  left`.

  **If it fires, the fix belongs in the SHARED fixture, not here** - a first-frame
  grace on `ClockTracksTheRound`, or seeding the swapped actor's `TimeRemaining`
  from the placed one inside `SwapForGradedBlueprint` - applied to both legs in
  one change. Re-tuning the tolerance on this leg alone would make the pair
  differ by its tuning, which is the one thing the pair convention exists to
  prevent. The proven `t1` pair gives no cover here:
  `ScreenTintFunctionalTest.cpp:147` opens at cp 3.0 s and its continuous gates
  are speed-relative and behind a settle window (`:248`, `:268`), never an
  absolute world-time-anchored value read off the swapped actor. This is the first
  `-bp` leg to point a tolerance-tight continuous gate at the swap window.
- **The fixture reads the round LENGTH off the marker after the swap**
  (`RoundSeconds = ReadTimeRemaining()` in `ResolveStaging`, and it must be
  >= 1.0). So the Blueprint round must keep `TimeRemaining`'s inherited default
  of 10.0 and must NOT write `TimeRemaining` in `BeginPlay`: a marker that has
  already started counting down by the time the fixture looks tells the fixture
  the round is shorter than it is, and every clock tolerance is then measured
  against the wrong length.
- **A coin consumed AFTER the whistle is a FAIL, whatever the `-cpp` spec's prose
  says.** That spec's verifier section states "whether a POST-deadline coin
  disappears on contact is deliberately NOT graded"; the shipping fixture FAILs
  it (`ScoreIsFinalAfterTheRound: a coin was consumed after the round had
  ended`), and the drive walks through two post-deadline coins on purpose. The
  code is the law on both legs; the prose is stale. Filed as a finding against
  the `-cpp` spec, not fixed here.
- **The per-coin values, the checkpoint instants and the drive path are not
  disclosed.** The prompt discloses the round length (10.0 s), the deadline
  tolerance (0.5 s), the mid-round accuracy band (1.0 s), the post-round clamp
  (reads 0), the two legal state words, the coin count (7) and the value range
  (5-100). It does not disclose the 14 sample instants, the waypoint timeline,
  which coins are pre-deadline / post-deadline / control, or the fixture's own
  contact reach.
- **Two gate values are NOT disclosed anywhere in the prompt, on either leg:** the
  readout-facing window (35 degrees) and the fraction of samples that must fall
  inside it (80%). The prompt says only "must turn to face the character". That is
  a real breach of the disclose-every-gate-value rule, inherited verbatim from the
  `-cpp` leg. It is left inherited on purpose - editing the prompt would make the
  pair differ by something other than its surface contract, which is the one thing
  this leg exists to isolate - and it is filed for the owner to fix on BOTH legs in
  one change.
- **What L2I can and cannot see.** It reproduces the fixture's resolution -
  including the resolver's `CLASS_Abstract` skip
  (`CraftBenchFunctionalTest.cpp:682-687`), so a submission that factors an
  abstract Blueprint base plus one concrete subclass is counted the way the
  fixture counts it rather than reported as two answers - and refuses a native
  subclass of either placed class, which is exactly the "C++ solve with a
  decorative Blueprint beside it" hole. It CANNOT see a C++ answer
  written IN PLACE into the supplied scaffold (`RaceRoundBase.cpp` /
  `RaceCoinBase.cpp` under `Source/ThirdPerson/Tasks/`), which is how the `-cpp`
  reference solves it: that creates no subclass, needs no new reflected member,
  and the graded substrate on disk is indistinguishable from git HEAD by the time
  the editor loads. On this leg the Blueprint stand-in would still be resolved and
  graded while inheriting the C++ behaviour, and both layers would read green. The
  prompt forbids it; nothing structural catches it. Do not describe this leg's L2I
  as proving "no C++ was written" - it proves "the class the run graded was
  Blueprint-generated, and no native subclass of either placed class was
  delivered".

  Two further properties of that grader, both deliberate:
  - **A verifier fault there is NON-GRADED.** If it cannot see the scaffold
    classes, or cannot list `/Game/Tasks` at all, it emits NO verdict block, which
    the layer maps to status `error` -> HARNESS-ERROR / exit 7, out of every
    pass-rate denominator. A module rename must not score against the model. (The
    four `gp-*-bp` graders and `t1_screen_tint_bp.py` still emit a
    graded FAIL in that situation; that is a defect on those files, filed rather
    than fixed from here.)
  - **The abstractness probe fails OPEN, and reports itself.** Whether a
    Blueprint's generated class carries `CLASS_Abstract` is read two independent
    ways (the asset registry's `ClassFlags` tag, and the UBlueprint's
    `bGenerateAbstractClass`); if neither answers, the candidate is KEPT, because
    the defect being fixed was a false FAIL and tightening on an unreadable probe
    would re-create it. The check's detail says `abstract=read` or `abstract=?`,
    and **a first run showing `abstract=?` means the probe is blind and the
    divergence is back** - that is a thing to read on the first graded run, not a
    thing to assume.

## Not yet measured

Everything on this leg. Specifically:

- **No reference asset exists.** `REFERENCE-NOTE.md` is a recipe derived from the
  `-cpp` reference, the scaffold headers and the fixture; no `.uasset` has been
  authored.
- **No run.** Reference PASS, empty FAIL, both framerate legs and the L2I leg are
  all predictions. The `-cpp` leg discriminates (reference PASS / empty FAIL,
  `discrimination/MATRIX.md`); this one has never been graded, so it ships no
  `discrimination/MATRIX.md` of its own yet - that is pending the first run, not
  an omission.
- **WHETHER THE LEG IS GRADABLE AT ALL is the open question**, and it is the FIRST
  thing to settle: the world time at the fixture's first graded tick must be
  <= 1.0 s or the swap frame FAILs a correct submission on
  `ClockTracksTheRound`. See the *Hidden invariants* entry for the mechanism, the
  token-free instrument (`[CB-CP] idx=0 t=` in the `-cpp` leg's existing L2 log,
  20 Hz first) and where the fix goes if it fires (the shared fixture, both legs,
  one change). Nothing about this depends on the reference assets existing, so it
  can and should be answered before they are authored.
- **The L2I grader has never run in an editor.** Its logic is pinned offline by
  `tools/verify-single/tests/test_introspect_t2_race_clock_bp.py` (14 tests,
  green, running the REAL `_bp_variant_lib` and the REAL layer parser against a
  fake `unreal`), but that cannot prove the three UE API names the abstractness
  probe uses are right - `EditorAssetLibrary.find_asset_data`, the `ClassFlags`
  asset-registry tag, and `bGenerateAbstractClass`. The first graded run must
  confirm the check detail reads `abstract=read`, not `abstract=?`.
- **The owner has not played it** (2026-08-18 directive: a task is not done until
  the owner has played the reference). Same map as the `-cpp` leg, so the play
  project already carries it.
