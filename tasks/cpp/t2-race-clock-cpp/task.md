---
id: t2-race-clock-cpp
substrate: ThirdPerson
set: cpp
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_RaceArena :: ARaceTheClockFunctionalTest"]
fps_legs: [60, 20]
---

# t2-race-clock

A timed score-attack round you can watch: a 10-second clock runs on screen, the
character walks into coins and the score climbs, the clock hits zero, the round
ends, and coins touched after that add nothing. Imported from the Startup Eval
corpus row `t2-score-attack` (owner: *agree* — "We could deduct it to 10
seconds to be quicker", so the round is **10.0 s**, not the corpus's 60).

Two things the corpus row got wrong are fixed here, both on the owner's
instruction. Its "the HUD must be authored without generated C++ or Slate …
FAIL 0/7" clause is **deleted**: it zeroes a correct submission for picking a
legal route. The requirement survives only in its positive form (named readouts,
live on screen, matching the authoritative values), and the route observation
survives only as a **non-gating warning line beside the verdict**. Its check 4
folded four sample points into one score, so a HUD that *stopped updating at
timeout* was indistinguishable from one that *never bound at all*; it is split
into three separately-named gates on two different channels, and the clock and
state channels are what tell those two failures apart.

Front-matter note: `deliverable_root:` is **not** an accepted front-matter key
(`tools/verify-single/spec.py::_KNOWN_KEYS` rejects unknown keys with a hard
`ValueError`, i.e. exit 2 "spec malformed"), so the deliverable root is stated
as the first line of *Workspace state pre-task* and again in the prompt body —
the two agent-visible sections.

## Primary concept

- `game-mode-and-game-state` — Game Mode and Game State
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/game-mode-and-game-state-in-unreal-engine)

What the verifier checks most directly is an authoritative, readable round
state: a score that only ever changes for a cause, a countdown that expires at
a declared deadline, an exclusive terminal transition, and a scoring rule that
is frozen by that transition. The on-screen readouts are how a human sees that
state and how the verifier gauges it; the state itself is the concept.

## Prompt given to the agent

> This level is a coin arena and nothing in it works: the clock never moves,
> walking into a coin does nothing, and the three on-screen readouts show
> frozen placeholder text. Make it a round.
>
> A round starts when play begins and runs for exactly **10.0 seconds**. Seven
> coins sit on the floor, each carrying its own point value in its `PointValue`
> property (the values differ; each is between 5 and 100).
>
> - Walking the character into a coin while the round runs consumes it — it is
>   no longer visible where it stood — and raises the score by exactly that
>   coin's own `PointValue`. A consumed coin never scores again, even on a
>   return trip across its spot.
> - The score starts at 0 and only ever changes because a coin was contacted.
> - The clock counts down from 10, reaches zero within **0.5 seconds** of
>   10.0 seconds of play (no earlier, no later), and never shows a negative
>   number. It also has to be roughly right *while* it runs, not only at the
>   end: at any moment of the round, `TimeRemaining` is within **1.0 second** of
>   the seconds actually left, and after the round ends it reads **0** — clamped,
>   never negative. Play begins at world time zero, and that is the instant the
>   10.0 seconds are measured from.
> - Before zero the round reads `InProgress`; at and after zero, `TimedOut` —
>   and those two words are the **only** values it ever takes, at any moment,
>   including during the transition.
> - After zero the score is final: contacting any coin still on the floor adds
>   nothing, ever.
> - The round marker exposes the three values an outside observer reads —
>   `Score` (whole number), `TimeRemaining` (seconds), `RoundState` — and all
>   three stay current throughout.
> - The readouts named exactly `ScoreText`, `ClockText` and `StateText` stay
>   findable on screen, each showing its live value and nothing else: the
>   score, the remaining whole seconds (round however you like), the round's
>   word. All three stay live and correct after the round has ended.
> - A coin the character never walks into is never consumed, never scores, and
>   keeps its own point value. It may idle however you like — bob, spin, glint —
>   as long as it stays where it was placed.
>
> Deliver asset work under `Content/Tasks/t2-race-clock-cpp/`;
> supporting code in `Source/ThirdPerson/` is equally acceptable and grades
> identically. Do not edit the level, any config file, or any test file.

> **Two more things, both of which a reviewer notices in the first ten seconds
> of playing and no headless check had been asking for.**
>
> The three readouts must **turn to face the character**. A board somebody has to
> walk around to read is not a readout, and one that stares at a fixed compass
> point is only legible from wherever it happens to be pointing.
>
> And the arena carries a **replay pad**: a lit plate on the floor in front of the
> board. Once the round has timed out, **stepping onto that pad starts a fresh
> round** — full clock, no score. Nothing else may restart it, and somebody who
> was already standing on the pad when the whistle went does not get an endless
> string of rounds: they have to step off and on again.

## Workspace state pre-task

**Deliverable root: `Content/Tasks/t2-race-clock-cpp/`.** Assets
written anywhere outside that folder or `Source/ThirdPerson/` are a sandbox
reject (exit 4), not a graded FAIL.

Assets that **exist** under `Content/Tasks/t2-race-clock-cpp/` —
all three are the agent's to edit or replace:

- `BP_RaceCoin` — the coin. Carries a visible coin mesh, a contact region about
  60 cm around itself that already detects the character walking in, the
  identity tag `RaceCoin`, and the editable property `PointValue`. **Nothing
  responds to the contact and nothing scores.**
- `BP_RaceRound` — the round marker, a short visible post on the floor. Tagged
  `RaceRound`. Exposes `Score` (`int32`, default 0), `TimeRemaining` (`float`,
  default 10.0) and `RoundState` (`FName`, default `InProgress`). Its only
  authored logic puts `WBP_RaceHud` on screen when play begins. **No countdown,
  no state transition, no scoring.**
- `WBP_RaceHud` — the on-screen readouts. Three text readouts named
  `ScoreText`, `ClockText`, `StateText`, showing the hardcoded literals `0`,
  `10` and `InProgress`, **bound to nothing**. Labels live in separate
  readouts, so each named readout holds only its value.

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t2-race-clock-cpp/RaceCoinBase.{h,cpp}` — the bare parent of
  `BP_RaceCoin`: mesh + contact region + tag + the `PointValue` property, no
  behaviour.
- `Tasks/t2-race-clock-cpp/RaceRoundBase.{h,cpp}` — the bare parent of
  `BP_RaceRound`: the three exposed properties + the tag, no behaviour.
- `Tasks/t2-race-clock-cpp/RaceCollector.{h,cpp}` — a concrete
  `ARaceCollector : public AThirdPersonCharacter` (the stock template character
  is abstract and unspawnable). Its constructor assigns the read-only mannequin
  `/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple` and
  `/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed`, and stamps the tag
  `RaceCollector`. No task behaviour.
- `Tasks/t2-race-clock-cpp/RaceGameMode.{h,cpp}` — sets
  `DefaultPawnClass = ARaceCollector`. The map's world settings select it, so
  PIE spawns and possesses the visible mannequin at the PlayerStart and a human
  pressing Play drives that same character with WASD.

Content that **exists** and is read-only:

- `Content/Maps/L_RaceArena.umap` — a 4000x4000
  floor with stripe decals every 200 cm; a PlayerStart on the floor at
  `(-1400, 0)` facing `+X`; a tall landmark pillar at each end of the backdrop
  (`X = -1600` and `X = +1600`, visibly different from each other); one placed
  `BP_RaceRound`; one placed `ARaceTheClockFunctionalTest`; and **seven** placed
  `BP_RaceCoin` instances, each with its own per-instance `PointValue`:

  | instance | location (uu) | role |
  |---|---|---|
  | `Coin_A` | `(-1000, 0)` | collected on the outbound leg |
  | `Coin_B` | `(-600, 0)` | collected on the outbound leg |
  | `Coin_C` | `(-200, 0)` | collected on the outbound leg |
  | `Coin_D` | `(+300, 0)` | collected late, still before the deadline |
  | `Coin_E` | `(+900, 0)` | contacted **after** the deadline |
  | `Coin_F` | `(+1300, 0)` | contacted **after** the deadline |
  | `Coin_Ctrl` | `(-600, +300)` | **the control — never contacted at all** |

  `Coin_Ctrl` sits 300 cm from `Coin_B`, both in one camera frame; the driven
  path runs along `Y = 0`, so the closest the character ever comes to the
  control is 300 cm against a contact reach of about 94 cm (60 cm region + the
  ~34 cm capsule) — better than 3x clearance.
- `Tasks/t2-race-clock-cpp/RaceReplayPadActor.h` / `.cpp` —
  `class THIRDPERSON_API ARaceReplayPadActor : public AActor`, tagged
  `RaceReplayPad`. **Supplied and working end to end**: a lit plate, a box volume
  over it, and a lamp that lights while somebody is standing there.
  `UFUNCTION(BlueprintPure) bool IsPressed() const`. Occupancy is counted, not
  flagged, so two figures on one pad do not clear it when the first steps off.
  **Nothing here knows what a round is.**
- `cameras.json` (the camera-plan lane; not part of this release) — a presentation-only
  camera plan framing `Coin_B`, `Coin_Ctrl`, the round marker and at least four
  floor stripes. Non-gating.
- `/Game/Characters/` — the mannequin pool. Deny-listed, so read-only.

Files that **do not exist**:

- No countdown, no state transition, no scoring, no coin consumption and no
  readout binding anywhere. The empty submission compiles (L1 green) and shows
  a legible frozen HUD — score `0`, clock `10`, `InProgress` — forever; it fails
  L2 at the named coin-scoring gate.
- No test source in the agent's writable path. `ARaceTheClockFunctionalTest`
  lives in the `CraftBenchTests` module, which the agent can neither read nor
  modify.

## Verifier specification

Verification primitive: **`pie-checkpoint-sampling`** (the character is driven
by a waypoint timeline and the round's state is sampled at a checkpoint
schedule), hardened with **`timer-framerate-legs`** (`fps_legs: [60, 20]` — the
same fixture in two independent PIE processes at two fixed timesteps, both
asserting the same absolute 10.0 s deadline). The test runs in PIE from
`Content/Maps/L_RaceArena.umap` on the
**ThirdPerson** substrate under `-deterministic -FPS=<rate>`.

**No second pawn is spawned, and no shared helper exists for one.** The
graded subject is the round (score / clock / state / coins) and the control
subject is the map-placed `Coin_Ctrl`, gauged at **every** checkpoint. The
collector character is staged by the map's game mode, not by the fixture, so
`ACraftBenchPawnFunctionalTest::SpawnAndPossessPawn()` is deliberately unused
and this fixture derives from `ACraftBenchFunctionalTest` directly. For the same
reason its **visible-character predicate is a task-local duplicate**:
`ACraftBenchPawnFunctionalTest::PawnVisiblyRepresented()` is bound to that
base's own `Pawn` member and cannot be called from here. The duplication is
approved; do not go looking for a shared helper and **do not edit either base
class** — they are owned by the other machine.

### Independence of the graded values

Every graded number has a verifier-side source that the submission does not
own, so no pair of submission-owned mirrors can agree its way to a PASS:

- the expected score is computed by the fixture from the `PointValue` it reads
  off the placed coin instances by reflection — not from the submission's score;
- the expected clock is the fixture's own `GetWorld()->GetTimeSeconds()` — not
  from the submission's `TimeRemaining`;
- the deadline is the fixture's own constant 10.0 s.

Each readout is then gated against the fixture's independent expectation **and**
against the round marker's authoritative property, with distinct named
failures, so "the readout is wrong" and "the authoritative value is wrong" never
collapse into one verdict (the divergence law).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

**Two gates added 2026-08-18**, after the owner played the level:

```text
assert: TheReadoutsFaceYou -- sampled every frame, each readout's forward points
        within 35 deg of the direction to the character, on at least 80% of
        samples. Judged over the run, so a board that swings round to follow is
        allowed to lag
assert: TheRoundCanBeRunAgain -- a second round happened at all
assert: TheRoundOnlyRestartsFromThePad -- and it started only after somebody had
        stood on the supplied replay pad, with the score cleared to nothing.
        Whether somebody is on the pad is read off the PAD'S OWN LAMP, not from
        a distance the fixture picks: a hand-chosen radius does not match the
        pad's trigger volume, and the first version called a corner-brush "a
        round that restarted on its own"
```

Adding the replay made FIVE existing gates wrong, every one of which had quietly
assumed the level contains exactly one round starting at world time zero:
`ClockTracksTheRound`, `RoundRunsForTenSeconds` (both directions),
`ScoreOnlyRisesFromCoins` and `ScoreIsFinalAfterTheRound`. All five are now
measured from THIS round rather than from the level, and the two score gates
re-baseline when a round starts.

```text
ARaceTheClockFunctionalTest (derives ACraftBenchFunctionalTest):

  PrepareTest():
      Super::PrepareTest()
      resolve by tag: exactly one "RaceRound", exactly seven "RaceCoin",
        exactly one "RaceCollector"  (else HARNESS-PRECONDITION FAIL)
      identify each coin by its authored location, not by name or class
      read PointValue off each coin by reflection -> PV[A..F], PV[Ctrl]
      ExpectedFinal = PV[A] + PV[B] + PV[C] + PV[D]
      resolve Score / TimeRemaining / RoundState on the round marker by
        reflection ("the round marker does not expose '<name>'").
        ACCEPTED TYPES, so a legal replacement marker is never mistaken for a
        missing property: Score = any integer or float property (read as a
        whole number); TimeRemaining = any float or double; RoundState = FName,
        FString, FText, or a UEnum-backed byte/enum property (read via its
        display/entry name). The read walks the resolved object's whole
        property chain including inherited and Blueprint-added properties. A
        name that resolves to none of those types FAILs as "the round marker's
        '<name>' is not a readable <number|word>" — a DIFFERENT literal from
        "does not expose", so "I named it something else" and "I typed it as
        something unreadable" are told apart.
      assert the collector carries a mesh a reviewer would SEE: non-null mesh
        asset, component visible (not hidden in game), not scaled to nothing
        ("the character has no visible representation")
      SetCheckpointSchedule({0.6, 3.6, 6.0, 8.8, 9.4, 10.9, 12.4, 13.6})

  Tick (every frame, after the base checkpoint clock):
      drive the collector along the waypoint timeline with per-frame movement
        input (the shipping pattern: TeleportPortalFunctionalTest.cpp:194,
        LadderClimbFunctionalTest.cpp:246, NpcFollowFunctionalTest.cpp:144);
        advance a waypoint once within 60 uu of it:
          W0 (-100,0)  outbound PAST Coin_C, over Coin_A, Coin_B, Coin_C
                       (100 uu clear of Coin_C's own spot, so no coin's
                        consumption is coupled to the arrival threshold —
                        the drive walks THROUGH every coin it collects and
                        stops at none of them)
          W1 (-1100,0) back-track, RE-CROSSING all three consumed spots
          W2 (+300,0)  late pre-deadline coin, Coin_D
          W3 HOLD      stand still until world time >= 10.4
          W4 (+1300,0) post-deadline, through Coin_E then Coin_F
      CONTINUOUS guards, every tick (a point sample cannot see these):
        G1 before the first coin contact: Score must stay 0
           ("the score rose before any coin was contacted")
        G2 while world time < 9.5: RoundState must read exactly InProgress
           ("the round ended before its deadline")
        G3 while world time > 10.5: RoundState must read exactly TimedOut
           ("the round was still running 10.5 s after play began")
        G4 the parsed number in ClockText is never negative
           ("the clock displayed a negative number")
        G5 record, per coin, the first world time at which it stopped being
           visible at its authored location, and the Score value at that tick
        G6 at EVERY tick, whatever the world time: RoundState reads exactly
           InProgress or exactly TimedOut, and nothing else
           ("the round read '<value>', which is neither InProgress nor
             TimedOut")
           [G2/G3 leave (9.5, 10.5) uncovered by construction, and no
            checkpoint falls inside it (cp4 = 9.4, cp5 = 10.9) — so without
            G6 a round that reads a third word for that whole second passes.
            G6 is tick-wide and has no window at all.]

  OnCheckpoint(i):   // every checkpoint also gauges the control (below)
    cp0 t=0.6   Score == 0; RoundState == InProgress; all seven coins present
                and visible; ScoreText == "0"; StateText == "InProgress";
                HUD found on screen. (PRECONDITIONS — an empty submission
                earns these; they are not scored.) Start the drive.
    cp1 t=3.6   [A|B|C consumed at ~2.7 s, 0.9 s slack]
                A, B, C no longer visible at their spots
                  ("coin at <loc> was contacted but never consumed")
                Score == PV[A]+PV[B]+PV[C]  exactly
                  ("the score is <n>; contacting those coins should have
                    added exactly <expected>")
                ScoreText parses == Score                          -> gate 4a
                  ("ScoreText reads '<s>' while the score is <n>")
                ClockText parses within 1.0 of (10.0 - t)          -> gate 4b
                  ("ClockText reads '<s>' with <f> seconds left")
                |TimeRemaining - (10.0 - t)| <= 1.0
                  ("TimeRemaining reads <f> with <f> seconds left")
                  [1.0 s, the SAME band the prompt discloses for mid-round
                   accuracy. It deliberately is not tighter than any disclosed
                   number: a submission decrementing on a 0.5 s timer is legal
                   as prompted and must pass. The band also absorbs the
                   sub-frame offset between world time 0 and the round marker's
                   BeginPlay, which no submission controls.]
    cp2 t=6.0   [back-track re-crossed A, B, C at ~4.9 s]
                Score UNCHANGED from cp1
                  ("a consumed coin scored a second time")
    cp3 t=8.8   [D consumed at ~7.6 s, 1.2 s slack] — FOUR separately named
                assertions, because four different bugs land here:
                D no longer visible at its spot
                  ("the late coin was contacted but never consumed")
                Score == ExpectedFinal exactly
                  ("the late coin added nothing; the score froze at <n> before
                    the deadline")
                  (kills a scoring rule frozen early — see anti-gaming 4)
                RoundState == InProgress
                  ("the round was already over 1.2 s before its deadline")
                ClockText parses > 0
                  ("ClockText had already reached zero before the deadline")
    cp4 t=9.4   RoundState == InProgress; TimeRemaining > 0
                  ("the round ended earlier than the declared deadline")
    cp5 t=10.9  RoundState == TimedOut
                  ("the round had not reached TimedOut 0.9 s after zero")
                |TimeRemaining| <= 0.1
                  ("TimeRemaining reads <f> after the round ended; it should
                    read 0")
                  [0.1 is a float epsilon around the prompt's disclosed "after
                   the round ends it reads 0 — clamped, never negative"; it can
                   only ever be more permissive than that sentence.]
                ClockText parses exactly 0                        -> gate 4c-clock
                  ("ClockText stopped updating at timeout; it reads '<s>'")
                StateText == "TimedOut"                          -> gate 4c-state
                  ("StateText stopped updating at timeout; it reads '<s>'")
                  [SPLIT deliberately: a HUD whose clock readout binds and
                   whose state readout does not is a different bug from the
                   reverse, and an AND under one message cannot say which.]
                Score == ExpectedFinal; FinalScore := Score. Resume the drive.
    cp6 t=12.4  [Coin_E contacted at ~11.9 s]
                Score == FinalScore
                  ("a coin scored after the round ended")
                RoundState == TimedOut
                  ("the round left its terminal state after reaching it")
    cp7 t=13.6  [Coin_F contacted at ~12.8 s — the SECOND post-deadline firing,
                same measured outcome as cp6, its OWN literals]
                Score == FinalScore
                  ("the second post-deadline coin scored; the freeze did not
                    hold")
                ClockText parses exactly 0
                  ("ClockText did not hold at zero after the round ended")
                StateText == "TimedOut"
                  ("StateText did not hold at TimedOut after the round ended")
                FinalScore == ExpectedFinal exactly, i.e. PV[Ctrl] is not in
                  the total   ("the never-contacted coin contributed <n>")
                -> Succeeded

  Control gauge, at EVERY checkpoint cp0..cp7 — four conditions, four literals:
      Coin_Ctrl still exists          ("the control coin was destroyed")
      its mesh is visible             ("the control coin was hidden")
      its HORIZONTAL displacement from its authored location is <= 60 uu
                                      ("the control coin moved <f> cm")
      its PointValue is unchanged     ("the control coin's point value changed
                                        from <n> to <n>")
      [Only horizontal displacement is gauged, and generously: the prompt
       explicitly permits an idling coin (bob, spin, glint), so a Z bob or any
       rotation must not FAIL correct work. 60 uu is a fifth of the 300 cm the
       driven path stays clear of the control, so it still catches a coin that
       was actually moved, and it is disclosed in the prompt as "stays where it
       was placed".]

  Whether a POST-deadline coin disappears on contact is deliberately NOT
  graded — both are legal answers to "adds nothing".

  Every checkpoint logs one ASCII line
  "[t2-race calib] cp<i> t=<t> score=<n> rem=<f> state=<s>
   readouts=<score>/<clock>/<state> coinsLeft=<n>"
  for tolerance calibration.

  ADVISORY, NON-GATING — the route line. After the verdict is decided, log
  once: whether WBP_RaceHud's three readouts are still unbound literals while
  an equivalently-named readout set reached the screen from elsewhere
  (native/generated). Format:
  "[t2-race route] hud=supplied-asset|replaced|native (non-gating)".
  This is the corpus row's route ban, demoted to a warning per the owner. It
  can never flip PASS/FAIL.
```

### Requirement-to-gate map

| Prompt requirement | Gate | Skipped when |
|---|---|---|
| coin contact raises score by that coin's own value | cp1, cp3 (exact sums from reflected `PointValue`) | never |
| score starts at 0, changes only for a cause | cp1 + cp3's exact reflected sums are what CARRY this row; continuous guard G1 is a fail-only guard (cp0 is a precondition the baseline already satisfies, and G1 is free to a do-nothing submission too — a score that never moves never rises early) | never |
| a consumed coin is no longer visible | cp1, cp3 | never |
| a consumed coin never scores again | cp2 (three re-crossings) | never |
| clock reaches zero within 0.5 s of 10.0 s | cp4 (not earlier) + cp5 (reached) | never |
| clock never shows a negative number | continuous guard G4 | if `ClockText` is unparseable, gate 4b already FAILed |
| `InProgress` before zero, `TimedOut` at and after | continuous guards G2 (`t < 9.5`) + G3 (`t > 10.5`), plus cp0/cp3/cp4/cp5/cp6/cp7 | inside `(9.5, 10.5)` neither G2 nor G3 constrains WHICH of the two words is read, and no checkpoint falls in that window — that second is covered only by G6 below |
| `RoundState` is never a third value, at any instant | continuous guard **G6** (tick-wide, no window) | never |
| `TimeRemaining` tracks the seconds left within 1.0 s | cp1 authoritative read | never |
| `TimeRemaining` reads 0 after the round ends (clamped, never negative) | cp5 (`\|TimeRemaining\| <= 0.1`) | never |
| score is final after zero | cp5, cp6, cp7 (two real post-deadline contacts) | never |
| `Score`/`TimeRemaining`/`RoundState` stay current | cp1..cp7 authoritative reads; resolution failure is its own named FAIL | never |
| `ScoreText` shows the live score | gate 4a (cp1), re-read cp5, cp7 | never |
| `ClockText` shows the live clock | gate 4b (cp1), cp3, cp5, cp7 | never |
| `StateText` shows the live round word | cp5, cp7 (cp0 is a precondition — the literal already reads `InProgress`) | never |
| readouts still live after the round ends | gate 4c (cp5) + cp7 | never |
| the control coin contributes nothing, and stays where it was placed | control gauge at all 8 checkpoints (4 separate literals) + the cp7 total accounting | never |

**Pass criteria**: both L1 targets green and L2 green **at both framerate legs**.
**Robust identity**: the round marker, the coins and the collector are resolved
by tag; the coins are told apart by authored location; the three round values
and each coin's `PointValue` are read by reflection by name — so a Blueprint
implementation, a native implementation, or any mix of the two grades
identically.

## Reference solution metadata

- Asset-graph size: 45-70 nodes across the three supplied assets
  (`BP_RaceCoin`: contact -> gate on `RoundState` -> add own `PointValue` ->
  hide/destroy self; `BP_RaceRound`: per-frame or timed countdown, the
  `TimedOut` flip at zero, clamp at zero, keep the three values current;
  `WBP_RaceHud`: three live readout bindings). Equivalent to 90-140 LOC if
  written natively instead — the fixture grades both shapes identically.
- Files touched: 3 (all three pre-existing supplied assets). Zero new files;
  zero C++ edits required, though a native solution is legal.
- Senior-dev hours: 1.5-2.5.

## Anti-gaming notes

1. **A score that is not caused by the coin it hit** — a constant per-coin
   amount, a plausible total written outright, a score that rises on a timer, a
   one-shot latch that only scores the first coin, or a consumed coin that
   scores twice. *Defense*: the expected total is computed by the fixture from
   the `PointValue` it reads off the placed coin instances, and those values are
   **not disclosed** in the prompt (see *Hidden invariants*) — cp1 asserts the
   exact three-coin sum and cp3 the exact four-coin sum, so no constant
   per-coin amount hits both; the scoring trigger fires **four** times
   pre-deadline; continuous guard G1 FAILs any rise before the first contact;
   and cp2 FAILs a re-crossed consumed coin that scores again (three
   re-crossings in one pass).
2. **Frame-count overfit on the countdown.** *Failure mode*: the round ends
   after 600 ticks rather than 10.0 seconds of play. *Defense*:
   `fps_legs: [60, 20]` runs the identical fixture in two independent PIE
   processes; a 600-tick round expires at 30 s wall time in the 20 Hz leg and
   FAILs cp5's terminal gate there.
3. **Freeze-everything-early.** *Failure mode*: scoring is frozen (or
   `TimedOut` is set) well before the deadline, which satisfies every
   post-timeout gate for free. *Defense*: `Coin_D` is collected **late**
   (~7.6 s) and cp3 requires the score to have risen by exactly its value at
   8.8 s; continuous guard G2 FAILs any `RoundState` other than `InProgress`
   at any tick before 9.5 s.
4. **Spoofed observables.** *Failure mode*: `ClockText` animates while
   `TimeRemaining` never moves (or the reverse); a coin is hidden without
   scoring; the score is written directly at play start. *Defense*: each
   readout is gated against the fixture's own independent clock/expected total
   **and** against the authoritative property with a distinct named failure,
   coin disappearance and score delta are asserted as a pair, and G1 catches a
   score written before any contact. Note what is deliberately **not** a
   defense: the route the HUD was authored by. That is the advisory warning
   line, never a FAIL.
5. **Test disabling / environment repointing.** *Failure mode*: the agent edits
   the fixture, the map, or config to weaken the gate. *Defense*:
   `Source/CraftBenchTests/` is sandbox-denied, the runner materializes the
   graded substrate from **git HEAD** (an on-disk edit never reaches the grade;
   committed changes are review-gated on commit), and `Content/Maps/` plus
   `Content/Characters/` are deny-listed. `Config/` is **not** a deny prefix on
   this substrate — `Config/DefaultEngine.ini` and `Config/DefaultInput.ini` are
   `config_writable`, path-accepted and then semantically diffed against the
   spec's `config_allow` list (`tools/verify-single/config_lane.py`). This spec
   declares **no** `config_allow`, so every ini diff is uncovered and rides the
   exit-4 path; the reject is real but it comes from an empty allowlist, not from
   a deny prefix, and adding a `config_allow` entry later would open it.

## Hidden invariants

- **The per-coin point values are the deliberate hidden-value pattern.** The
  prompt discloses the mechanism (each coin carries its own `PointValue`), the
  count (seven coins) and the range (5-100), but **not the numbers**. The agent
  must read the value off the coin it contacted; the fixture reads the same
  property off the same placed instances by reflection and computes the
  expected total from them. A hardcoded per-coin amount cannot satisfy both the
  three-coin sum at cp1 and the four-coin sum at cp3. This is the one sanctioned
  exception to the disclose-every-number rule, and it is disclosed here.
- **The checkpoint instants and the waypoint timeline are not disclosed.** The
  prompt states the round length (10.0 s), the deadline tolerance (0.5 s), the
  mid-round accuracy band (1.0 s), the post-round clamp (reads 0), the two
  legal state words and the control coin's "stays where it was placed"; the
  eight sample times, the drive path and the roles of individual coins are
  not. A solution fitted to guessed sample times has eight independent chances
  to miss.
- **Every number the grade compares the submission against is now disclosed,
  and the three that are not are leniency only.** The verifier-side numbers are
  `0.1` (the float epsilon around the disclosed "reads 0"), `60 uu` (the
  control's horizontal displacement window, three hundred cm inside the
  clearance the route keeps, and looser than the disclosed "stays where it was
  placed"), and `60 uu` again as the waypoint arrival radius, which is drive
  geometry and nothing the submission can fail. None of them can FAIL a
  submission that satisfies the prompt. The earlier draft graded mid-round clock
  accuracy at `0.35 s` — **tighter than the 0.5 s the prompt disclosed** and
  therefore a false-FAIL on a legal 0.5 s-timer decrement; that is fixed, and
  the band is stated in the prompt.
- **Which coins are pre-deadline, post-deadline and control is not disclosed.**
  From the prompt's side there are simply seven coins on the floor and one rule
  for all of them. `Coin_Ctrl` is never contacted, so a submission that credits
  score for coins it never touched is caught by the cp7 total accounting rather
  than by anything it could have anticipated.
- **The continuous guards have no checkpoint to be fitted to.** G1-G4 run every
  tick, so an early terminal transition, a pre-contact score write, or a
  negative clock frame between two checkpoints is caught where a point sample
  would miss it.
