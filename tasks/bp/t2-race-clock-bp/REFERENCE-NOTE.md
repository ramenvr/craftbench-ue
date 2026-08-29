# Reference recipe - `t2-race-clock-bp`

There is no script lane for Blueprint **graph** authoring in this repo (no
`BlueprintEditorLibrary` / `K2Node` precedent anywhere under `tools/` or
`tasks/`), so these two assets are built in an attended editor session. This file
is precise to the node and the pin so they can be rebuilt without re-deriving the
design.

Everything here is checked against the read-only C++ that ships with the task:

- `UE-projects/ThirdPerson/Source/ThirdPerson/Tasks/t2-race-clock-cpp/RaceCoinBase.h`
- `.../RaceRoundBase.h`
- `.../RaceReplayPadActor.h`
- the fixture that grades it,
  `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/t2-race-clock-cpp/RaceTheClockFunctionalTest.cpp`
- and the C++ leg's reference solution,
  `tasks/cpp/t2-race-clock-cpp/reference/Source/ThirdPerson/Tasks/t2-race-clock-cpp/`

**Nothing in this file has been run.** Every claim is derived from those sources
and the engine headers. The first graded run is what makes any of it true.

**READ *Before they exist - the one thing to check first* (near the end of this
file) BEFORE OPENING AN EDITOR.** It is a one-number, zero-cost go/no-go on
whether this leg can be graded at all; the number does not depend on these assets
existing, and if it comes out wrong the fix is in the shared fixture, not in this
recipe. Trap **R1a** is the mechanism.

---

## Is this leg winnable at all?

**Yes.** Everything the behaviour needs is reachable from a Blueprint. That is
not a given - the `t1-screen-tint-bp` leg was UNWINNABLE until the
scaffold's constructor was changed, because `bCanEverTick` carries no editor
exposure - so it was checked member by member before this recipe was written.

### `ARaceCoinBase` - what a Blueprint subclass can reach

| member | specifier | so a Blueprint can |
|---|---|---|
| `PointValue` (`int32`) | `EditAnywhere, BlueprintReadWrite` | read it, set its class default, write it |
| `CoinRegion` (`USphereComponent*`) | `VisibleAnywhere, BlueprintReadOnly` | reference it, and add its `On Component Begin Overlap` event |
| `CoinMesh` (`UStaticMeshComponent*`) | `VisibleAnywhere, BlueprintReadOnly` | reference it and call `SetVisibility` / `SetHiddenInGame` on it |
| the class itself | `AActor` is `UCLASS(BlueprintType, Blueprintable, ...)` (`Actor.h:281`), and both specifiers are inherited | subclass it, and `Cast To RaceCoinBase` |
| `PrimaryActorTick.bCanEverTick` | supplied **false**, and a bare `UPROPERTY()` with no editor exposure | see the note below - and the recipe does not need Tick on the coin |

**The coin's tick, stated because it is easy to get wrong in both directions.**
The parent sets `bCanEverTick = false`, and a Blueprint author cannot flip that
flag in the details panel. But the Blueprint compiler *re-derives* it:
`FKismetCompilerContext::SetCanEverTick` (`KismetCompiler.cpp:5527-5610`) resets
the flag from the parent and then turns it back ON for a non-empty `Event Tick`
whenever `bCanBlueprintsTickByDefault` is set - and it is
(`Engine/Config/BaseEngine.ini:319 bCanBlueprintsTickByDefault=true`). So a coin
Blueprint with a connected Event Tick *does* tick. Do not build the coin on Tick
anyway: the thing the fixture measures is the CONTACT.

### `ARaceRoundBase` - what a Blueprint subclass can reach

| member | specifier | so a Blueprint can |
|---|---|---|
| `Score` (`int32`) | `EditAnywhere, BlueprintReadWrite` | read and write it |
| `TimeRemaining` (`float`) | `EditAnywhere, BlueprintReadWrite` | read and write it |
| `RoundState` (`FString`) | `EditAnywhere, BlueprintReadWrite` | read and write it |
| `BoardRoot` (`USceneComponent*`) | `VisibleAnywhere, BlueprintReadOnly` | reference it, call `SetWorldRotation` on it |
| `ScoreText` / `ClockText` / `StateText` (`UTextRenderComponent*`) | `VisibleAnywhere, BlueprintReadOnly` | reference them and call `SetText` (`UTextRenderComponent::SetText` is `BlueprintCallable`) |
| `PrimaryActorTick.bCanEverTick` | supplied **true** by the constructor | have `Event Tick` fire, which this leg needs |

### `ARaceReplayPadActor` - supplied, working, not the agent's to change

| member | specifier | so a Blueprint can |
|---|---|---|
| `IsPressed()` | `UFUNCTION(BlueprintPure)` | ask whether somebody is standing on it right now |
| `Lamp`, `Plate`, `Volume` | `VisibleAnywhere, BlueprintReadOnly` | read them - but ask `IsPressed()`, not the lamp |

Occupancy is COUNTED, not flagged, so two figures on one pad do not clear it when
the first steps off. Nothing on the pad knows what a round is.

**Nothing needed is unreachable.** If a future scaffold change breaks one of the
rows above, this leg becomes an unwinnable task rather than a surface
measurement, and that is a bug to report, not a recipe to work around.

**WINNABLE is not the same as GRADABLE, and only the first is settled.** Every
member the behaviour needs is reachable from a Blueprint, so a correct submission
is expressible. Whether the harness can then MEASURE it without failing it is a
separate, still-open question - trap **R1a** below, and the *Before they exist*
step at the end of this file. Do not start an editor session until that number
has been read.

---

## The two assets

Two Blueprints, one per agent class. Nothing else. They are unrelated classes, so
each resolves against its own placed class and they cannot collide.

| asset | path | parent class | the placed thing it stands in for |
|---|---|---|---|
| `BP_RaceCoin` | `/Game/Tasks/t2-race-clock-bp/BP_RaceCoin` | `RaceCoinBase` | all **seven** placed coins (`SwapAllForGradedBlueprint`) |
| `BP_RaceRound` | `/Game/Tasks/t2-race-clock-bp/BP_RaceRound` | `RaceRoundBase` | the **one** placed round marker (`SwapForGradedBlueprint`) |

The folder matters. `ResolveGradedBlueprintClass` filters the asset registry to
`/Game/Tasks` **recursively** and takes the single Blueprint deriving from the
placed class; a SECOND such Blueprint anywhere under `/Game/Tasks` is
`HARNESS-PRECONDITION`, not a verdict. Ship exactly one per class, in the
declared folder (L2I additionally asserts the answer is in the declared folder,
so a misfiled Blueprint reads as misfiled rather than as missing).

### Class defaults

**`BP_RaceCoin`**

- `PointValue` = **40**. It MUST be non-zero, and this is not cosmetic: the swap
  spawns the Blueprint from its class default, so the map's per-instance values
  (15, 40, 25, 60, 35, 90, 100) are gone and every coin carries this one number.
  `ResolveStaging` FAILs with `HARNESS-PRECONDITION: ... a coin carries no
  PointValue` when it reads `<= 0`, and a HARNESS-PRECONDITION is a non-verdict:
  the run says nothing about the submission at all. 40 is arbitrary; any value in
  the prompt's disclosed 5-100 range does.
- Everything else inherited, untouched.

**`BP_RaceRound`**

- `Score` = **0**, `TimeRemaining` = **10.0**, `RoundState` = **`InProgress`** -
  i.e. leave all three at their inherited defaults. Same reason: the swap carries
  the transform and the tags and NOTHING else, so the class defaults are the
  round's starting state, and `ResolveStaging` reads the round LENGTH straight off
  `TimeRemaining` immediately after the swap.
- Everything else inherited, untouched.

---

## `BP_RaceCoin` - the graph

One event. Roughly fifteen nodes. Ask the round first, bank the value, consume
itself.

Variables to add:

| name | type | default | why |
|---|---|---|---|
| `Consumed` | Boolean | false | one contact, one payment - see trap **C7** |

```
[On Component Begin Overlap (CoinRegion)]          <- select the INHERITED
   |   Other Actor                                    CoinRegion in the
   |                                                   Components panel ->
   |                                                   Details -> Events -> "+"
   v
[Branch]  Condition = [Get Consumed]
   |  True  -> (nothing)
   |  False
   v
[Cast To Character]  Object = Other Actor
   |  Cast Failed -> (nothing)
   |  (success; the As Character pin is unused)
   v
[Get All Actors With Tag]  Actor Tag = "RaceRound"
   |  Out Actors
   v
[Length] -> [Branch] Condition = (Length > 0)
   |  False -> (nothing)
   |  True
   v
[Get (a copy)]  Array = Out Actors, Index = 0
   |
   v
[Cast To RaceRoundBase]
   |  Cast Failed -> (nothing)
   |  As Race Round Base  ---------------------+
   v                                           |
[Get RoundState]  Target = As Race Round Base  |
   |                                           |
   v                                           |
[Equal (String)]  A = RoundState, B = "InProgress"
   |                                           |
   v                                           |
[Branch]                                       |
   |  False -> (nothing: the whistle has gone, so this coin neither scores
   |            NOR disappears -- trap C3)     |
   |  True                                     |
   v                                           |
[Set Score]  Target = As Race Round Base <-----+
             Score  = [Get Score (target = As Race Round Base)]
                      + [Get PointValue (self)]        <- an [Integer + Integer]
   |
   v
[Set Consumed]  = true
   |
   v
[Destroy Actor]  Target = self
```

### Ways to get the coin subtly wrong

**C1. Leaving `PointValue` at its inherited default of 0.** Not a FAIL - a
`HARNESS-PRECONDITION`, which is worse, because the run produces no verdict and
looks like a harness fault rather than a missing default. See *Class defaults*.

**C2. Caching the round in `Event BeginPlay`.** The fixture swaps the COINS
first and the ROUND second (`RaceTheClockFunctionalTest.cpp:165-166`), so a coin
Blueprint's `BeginPlay` runs while the round is still the PLACED C++ actor - which
is destroyed on the very next line. A cached reference is then dangling and every
contact silently does nothing. Resolve the round AT CONTACT TIME, which is also
what the C++ reference does (`RaceCoinBase.cpp:70-71`).

**C3. Consuming the coin when the round is NOT running.** Ask first. The drive
deliberately walks THROUGH two coins after the whistle, and a coin that vanishes
then FAILs `ScoreIsFinalAfterTheRound: a coin was consumed after the round had
ended`. Note that the `-cpp` spec's prose claims post-deadline disappearance is
"deliberately NOT graded" - the shipping fixture disagrees
(`RaceTheClockFunctionalTest.cpp:526-532`), and the code is the law.

**C4. Consuming with `Set Actor Hidden In Game`.** The fixture's "gone" test walks
the actor's `StaticMeshComponent`s and asks each one `IsVisible() &&
!bHiddenInGame` - and `USceneComponent::IsVisible()`
(`SceneComponent.cpp:3555-3564`) does NOT consult the owner's hidden flag. So the
coin still reads as PRESENT, its value is never banked into the fixture's expected
total, and the sentinel FAILs `CoinAddsItsOwnValue: only N coin(s) were consumed
inside the round`. Use `Destroy Actor` (what the reference does), or
`SetHiddenInGame` / `SetVisibility` on the MESH COMPONENT.

**C5. Adding a second visible static mesh for decoration and then hiding only
`CoinMesh`.** Any visible static mesh component keeps the coin "present". Same
failure as C4, and harder to see. If you decorate, destroy the actor.

**C6. Idling by moving the ACTOR.** The prompt allows an idle (bob, spin, glint)
"as long as it stays where it was placed", and the fixture enforces that on the
untouched control coin with `FVector::Dist(location, placed) > 200` - a **3D**
distance, so a tall Z bob trips `TheUntouchedCoinSurvives` exactly like a
sideways drift does. (The `-cpp` spec's prose says only horizontal displacement is
gauged; that is stale - `RaceTheClockFunctionalTest.cpp:548` is `FVector::Dist`.)
The safe answers are: no idle at all, or animate `CoinMesh`'s RELATIVE transform
and leave the actor where it was spawned. And a coin that moves more than 500 uu
from its spot counts as CONSUMED, which is a different and worse failure.

**C7. No `Consumed` latch.** `Destroy Actor` does not stop other overlap events
already queued for this frame, and a character can begin-overlap a region with
more than one of its own components. Two payments for one coin FAILs
`CoinAddsItsOwnValue` on the exact-total comparison. Latch first, destroy last.

**C8. Banking a number the coin decided instead of its own `PointValue`.** The
fixture reads `PointValue` off the same actor by reflection and asserts the exact
running total. On THIS leg every coin carries the class default, so a hardcoded 40
would pass here - it does not pass the `-cpp` leg, it is not what the prompt asks
for, and a `-bp` PASS is not evidence about it either way (see the task spec's
*Hidden invariants*). Read the property.

**C9. Gating on the coin's own copy of the round state.** A boolean the coin
latches once is not the round's word. The round is the authority, and it is asked
per contact.

**C10. Not filtering the overlap to the character.** `Event ActorBeginOverlap`
also works as the entry point, but either route must filter (`Cast To Character`)
- the arena contains other actors, and a coin that pays out for anything that
brushes it is a score not caused by the character walking into it.

---

## `BP_RaceRound` - the graph

Two events and two collapsed functions. Roughly forty nodes.

Variables to add:

| name | type | default | why |
|---|---|---|---|
| `RoundLength` | Float | 10.0 | read off the board in BeginPlay; never a second hardcoded 10 |
| `RoundStartedAt` | Float | **0.0** | the world time THIS round began. The default 0.0 is load-bearing - see trap **R1** |
| `ReplayPad` | Actor (object reference) | none | the supplied pad, found once by tag. Safe to cache: the pad is NOT swapped |
| `ReplayArmed` | Boolean | false | the pad must be STEPPED ON, not held - see trap **R11** |

Do **not** add variables named `Score`, `TimeRemaining` or `RoundState` - see
trap **R15**.

### `Event BeginPlay`

```
[Event BeginPlay]
   |
   v
[Set RoundLength] = [Get TimeRemaining (self)]     <- READ it; do not write
   |                                                  TimeRemaining here (R2)
   v
[Get All Actors With Tag]  Actor Tag = "RaceReplayPad"
   |  Out Actors
   v
[Length] -> [Branch] (Length > 0)
   |  True
   v
[Set ReplayPad] = [Get (a copy)] Array = Out Actors, Index = 0
   |
   v
[Refresh Readouts]        <- the collapsed function below, so the board shows
                             real values from its first frame rather than the
                             supplied placeholders
```

Nothing else. In particular **no** `Set RoundStartedAt` and **no**
`Set TimeRemaining`.

### `Event Tick`

```
[Event Tick]
   |
   v
[Get Game Time in Seconds]        (target = self)
   |  Return Value = NOW
   v
[float - float]  A = NOW, B = [Get RoundStartedAt]        = INTO ROUND
   |
   v
[float - float]  A = [Get RoundLength], B = INTO ROUND    = LEFT
   |
   +--> [Max (float)]  A = LEFT, B = 0.0  --> [Set TimeRemaining]
   |
   +--> [float > float]  A = LEFT, B = 0.0  = RUNNING
                |
                v
        [Select (String)]  Index/Condition = RUNNING
                           True  = "InProgress"
                           False = "TimedOut"
                |
                v
        [Set RoundState]
   |
   v
[Refresh Readouts]                 <- one call, after BOTH values are set
   |
   v
[Face The Watcher]                 <- the collapsed function below
   |
   v
[Branch]  Condition = RUNNING
   |  True  -> (nothing more this tick)
   |  False
   v
[Is Valid]  Input Object = [Get ReplayPad]
   |  Is Not Valid -> (nothing)
   |  Is Valid
   v
[Cast To RaceReplayPadActor]
   |  Cast Failed -> (nothing)
   v
[Is Pressed]  Target = As Race Replay Pad Actor
   |
   v
[Branch]
   |  False -> [Set ReplayArmed] = true          (stepped OFF: arm it)
   |  True  -> [Branch] Condition = [Get ReplayArmed]
   |              False -> (nothing: somebody is standing there who never
   |                        stepped off, and they do not get another round)
   |              True
   v
[Start Fresh Round]                <- the collapsed function below
```

### `Start Fresh Round` (collapsed function, no inputs)

All five writes in ONE sequence, in one tick. That is not style - see trap
**R12**.

```
[Set Score]          = 0
[Set TimeRemaining]  = [Get RoundLength]
[Set RoundState]     = "InProgress"
[Set RoundStartedAt] = [Get Game Time in Seconds]
[Set ReplayArmed]    = false
[Refresh Readouts]
```

Note the asymmetry with `BeginPlay`, and that it is deliberate: the FIRST round is
anchored at world time zero (the `RoundStartedAt` default), every LATER round is
anchored at the moment the pad was stepped on.

### `Refresh Readouts` (collapsed function, no inputs)

```
[ScoreText] -> [Set Text]  Value = [Format Text] "SCORE {n}"  n = [Get Score]
[ClockText] -> [Set Text]  Value = [To String (integer)] of
                                   [Ceil] ([Get TimeRemaining])
[StateText] -> [Set Text]  Value = [Get RoundState]
```

`Set Text` here is `UTextRenderComponent::SetText`, reached by dragging off the
inherited component reference. Never write an empty string to any of the three -
see trap **R8**.

### `Face The Watcher` (collapsed function, no inputs)

```
[Get Player Pawn]  Player Index = 0
   |  Return Value
   v
[Is Valid] -> Is Not Valid -> (nothing)
   |
   v
[Find Look at Rotation]
      Start  = [GetActorLocation (self)]
      Target = [GetActorLocation (the pawn)]
   |  Return Value (Rotator)
   v
[Break Rotator]  -> keep Z (Yaw) only
   |
   v
[Make Rotator]  Roll = 0.0, Pitch = 0.0, Yaw = the yaw above
   |
   v
[Set Actor Rotation]  Target = self, New Rotation = that rotator
```

One rotation for the whole board is correct and is the cheapest thing that
satisfies the gate: the three readouts hang off the unscaled `BoardRoot` at
relative locations `(0, 0, H)`, so a yaw about the actor's own vertical moves none
of them and sets all three world rotations at once. The C++ reference instead
calls `SetWorldRotation` on each of the three components
(`RaceRoundBase.cpp:132-150`); both satisfy `TheReadoutsFaceYou`, which samples
EVERY `UTextRenderComponent` on the marker and wants each one's own `+X` within
35 degrees of the direction to the character on at least 80% of samples.

### Ways to get the round subtly wrong

**R1. Stamping `RoundStartedAt` in `BeginPlay`.** This is the trap unique to the
Blueprint surface and it is the one most likely to sink a first attempt. The
fixture measures the FIRST round's deadline from world time ZERO -
`RoundStartedAtWorld = 0.0`, declared at **`RaceTheClockFunctionalTest.h:80`**
(the `.h`, not the `.cpp`: `.cpp:78` is the closing `return FString();` of
`ReadRoundState()` and `.cpp:80` is blank). On the `-cpp` leg the round marker is
PLACED, so it has been ticking since world time ~0 and the same anchor is exact
for free - and note that the C++ reference does NOT stamp `BeginPlay` either: it
leaves `RoundStartedAt` at its `0.0` default
(`reference/.../RaceRoundBase.h:73`) and writes it only in `StartFreshRound`
(`.cpp:81`). On this leg the marker is SPAWNED by the surface swap during
`PrepareTest`, so its `BeginPlay` runs however late the fixture got there. A
BeginPlay-stamped round therefore times out late by exactly the swap delay,
against `RoundRunsForTenSeconds`' 0.5 s window and `ClockTracksTheRound`'s 1.0 s
band. Leave `RoundStartedAt` at 0.0 - which is also what mirrors the `-cpp`
reference exactly - and let `Start Fresh Round` be the only thing that ever
writes it.

**R1a. The residual that is NOT yours to fix, recorded so you do not try.**
Leaving `RoundStartedAt` at 0.0 is the minimum-exposure design, not a
zero-exposure one. Between the swap spawning the marker and the marker's own
first `Tick`, `TimeRemaining` still reads the class default 10.0 while the
fixture already computes `TrueRemaining = 10.0 - Now` and checks it
unconditionally with a 1.0 s allowance
(`RaceTheClockFunctionalTest.cpp:449`) - so on that ONE frame the drift equals
the world time at the fixture's first graded tick, whatever the submission is.
Every alternative is worse, not better: R1 makes that drift permanent, and R2
makes it permanent *and* corrupts the round length. **Do not design around it.**
The task spec's *Hidden invariants* carries the mechanism, the go/no-go bound
(<= 1.0 s), the token-free instrument, and the fact that the fix - if it fires -
belongs in the shared fixture and lands on both legs at once. Reading that number
is *Before they exist - the one thing to check first* below, and it needs neither
of these assets to exist.

**R2. Writing `TimeRemaining` in `BeginPlay`.** `ResolveStaging` reads the round
LENGTH off the marker immediately after the swap (`RoundSeconds =
ReadTimeRemaining()`), and requires it to be `>= 1.0`. A marker that has already
begun counting down tells the fixture the round is shorter than it is, and every
clock tolerance is then measured against the wrong length - including the
`>= 0.9 * RoundSeconds` threshold that detects a replay. Read `TimeRemaining` in
BeginPlay; write it only from Tick and from `Start Fresh Round`.

**R3. Accumulating the clock instead of deriving it.** Counting ticks, or
subtracting a per-tick constant, is what `fps_legs: [60, 20]` exists to catch: the
same fixture runs in two independent PIE processes at two fixed timesteps and both
assert the same absolute 10.0 s. Derive `TimeRemaining` from the game clock every
tick, as above; then it cannot drift and cannot care about the framerate.

**R4. A third state word, even for one frame.** `RoundStateIsOneOfTwoWords` is
tick-wide and has no window at all: `Ready`, `Waiting`, `Timeout`, `TIMED OUT` or
an empty string FAILs on the frame it appears. There are exactly two legal
strings, spelled `InProgress` and `TimedOut`.

**R5. Flipping the state before clamping the clock.** At the instant the state
first reads `TimedOut` the fixture requires `TimeRemaining <= 0.001`
(`ClockReadsZeroWhenTheRoundEnds`). Setting the state on one tick and clamping the
clock on the next FAILs. Both writes are in one node sequence above, off the same
`LEFT` value, for exactly this reason.

**R6. Formatting `ClockText` as a duration.** The readout parser takes the FIRST
run of digits in the string (`FirstNumber`,
`RaceTheClockFunctionalTest.cpp:29-38`), so `00:09` reads as **0** with nine
seconds left and FAILs `ReadoutsShowTheLiveValues`. Print the whole seconds and
nothing before them. `9`, `9 s` and `9.0` are all fine; `00:09` and `T-9` are not.

**R7. Putting another number in front of the score.** Same parser, same failure:
`0 / 500` reads as 0 forever. `SCORE 120` is fine because the letters are not
digits. Keep the number last.

**R8. Leaving any readout empty.** `ResolveStaging` requires all three to be
non-empty and FAILs `HARNESS-PRECONDITION: a readable round surface is missing -
the readout named <X> was not found on the round marker` otherwise. That is a
non-verdict, not a FAIL. An empty string is the one value never to write.

**R9. Facing with pitch and roll.** `Find Look at Rotation` returns the full
rotation to the character, which tips the glyphs at anybody standing close and
reads badly for the human who has to play this. Zero the pitch and roll and keep
the yaw. (The gate normalizes in 2D, so a small pitch survives it - but a nearly
vertical facing vector has almost no 2D component left and the dot product
fails.)

**R10. Facing one readout, or adding a label that never turns.**
`TheReadoutsFaceYou` samples EVERY `UTextRenderComponent` on the marker, so a
static "SCORE:" label component drags the hit ratio down toward the 80% floor even
though the three graded readouts are perfect. Rotate the actor (or the root) so
everything attached turns together.

**R11. Restarting while the pad is HELD rather than when it is STEPPED ON.** The
drive's last waypoint IS the pad, and the character stands there for the rest of
the run, so a level-triggered restart starts a new round roughly every ten
seconds until the sentinel at t=60. That is not merely untidy: if one of those
rounds is still in flight when the sentinel fires, the run FAILs
`RoundRunsForTenSeconds: the round never ended, so nothing about what happens
after the whistle was measured` - intermittently, depending on where the last
restart landed, which is the worst kind of failure to debug. Arm on release
(`ReplayArmed`), exactly as the C++ reference does.

**R12. Resetting the score and the clock on different ticks.** The fixture detects
a new round by "the previous frame read `TimedOut` and this frame's
`TimeRemaining` is back above 90% of the round length", and on THAT frame it
requires `Score` to already read 0 (`TheRoundCanBeRunAgain: the clock restarted
but the score still reads N`). Reset the score FIRST and the clock LATER and you
fail differently and earlier: a score that drops while the round is still timed
out FAILs `ScoreOnlyRisesFromCoins: the score went down`. One tick, one sequence,
all five writes.

**R13. Restarting the round on anything but the pad.** An auto-restart at timeout,
a keypress, a timer - all FAIL `TheRoundOnlyRestartsFromThePad`, which is judged
against the PAD'S OWN LAMP rather than a distance the fixture picks.

**R14. Editing the class defaults for `Score` / `TimeRemaining` / `RoundState`.**
The swap carries no per-instance values, so the class defaults ARE the round's
starting state. 0 / 10.0 / `InProgress`.

**R15. Adding Blueprint variables that shadow the inherited ones.** The fixture
reads by reflection with `FindFProperty<T>` on the resolved class, and a
Blueprint-added variable lives on the most-derived class, so it is found FIRST.
Two distinct disasters follow. A Blueprint `String` named `RoundState` shadows the
inherited one, so the fixture reads YOUR new variable while your graph may be
writing the inherited one (or the reverse) - and the two disagree silently. A
Blueprint `Float` named `TimeRemaining` is worse: Blueprint "Float" is a **double**
(`FDoubleProperty`), the fixture's lookup is `FindFProperty<FFloatProperty>`, so
the double is skipped entirely, the inherited float is read instead, and your
countdown is invisible to the grade even though the board on screen looks right.
Use the inherited variables. If you need scratch state, name it something else.

**R16. Two Blueprints deriving from the same placed class.** A duplicate, an
earlier attempt, or a base you subclassed - anywhere under `/Game/Tasks`, not just
in this folder - makes `ResolveGradedBlueprintClass` raise
`HARNESS-PRECONDITION: two or more Blueprints under /Game/Tasks derive from <X>`,
and L2I's `exactly_one_blueprint_answer` FAILs too. Exactly one per class.

**R17. Filing the Blueprints outside the declared folder.** The fixture scans all
of `/Game/Tasks` recursively, so a misfiled Blueprint would still be graded by L2
- and L2I's `answer_is_in_the_declared_folder` would FAIL it, so the surface leg
reads red while the behaviour leg reads green. Put both assets under
`/Game/Tasks/t2-race-clock-bp/`.

**R18. Solving any of it in C++.** Editing `RaceRoundBase.cpp` or
`RaceCoinBase.cpp` in place is invisible to L2I's native-subclass sweep (there is
no subclass to find) and it would still be graded green - see the task spec's
*Hidden invariants*. It is nonetheless a violation of the one thing this leg
measures. Do not.

---

## Saving it out

Author both Blueprints in the substrate project so the parent classes resolve,
then copy the `.uasset`s into the task folder - the reference tree mirrors the
deliverable root exactly:

```
tasks/bp/t2-race-clock-bp/reference/
  Content/Tasks/t2-race-clock-bp/BP_RaceCoin.uasset
  Content/Tasks/t2-race-clock-bp/BP_RaceRound.uasset
```

Copy, do not move: leaving the authored assets in the substrate's own
`Content/Tasks/` would put an answer inside the graded substrate, which is how an
EMPTY submission passes (see the internal failure log (not shipped)'s "reference inside the
substrate" entry - it is a `cb lint` ERROR now).

## Before they exist - the one thing to check first

**Step 0, and it costs nothing.** Read `[CB-CP] idx=0 t=` (or
`[t2-race calib] cp0 t=`) out of the `-cpp` leg's EXISTING L2 log, at **both**
framerate legs, 20 Hz first. That number is the world time at the fixture's first
graded tick, it is set by the automation pre-roll rather than by anything either
leg delivers, and per trap **R1a** the leg is gradable iff it is **<= 1.0 s**. If
it is over 1.0 s the swap frame FAILs a correct Blueprint submission on
`ClockTracksTheRound` and the leg is not gradable as written - stop, and fix the
shared fixture (a first-frame grace, or seeding the swapped actor's
`TimeRemaining`) across both legs before authoring anything. Authoring first and
discovering it afterwards costs an editor session and looks like a recipe bug.

The failing signature, so it is not mistaken for a submission error: a
`[t2-race calib] cp0 t=<over 1.0> ... remain=10.00` line immediately followed by
`ClockTracksTheRound: the clock read 10.00 with <10 - t> seconds actually left`.

## After they exist

1. `cb discriminate --task t2-race-clock-bp` - reference must PASS,
   empty must FAIL. Empty here means no Blueprint at all, in which case both swaps
   find nothing, the placed C++ scaffolds are graded, and the run FAILs on the
   very first tick at `ReadoutsShowTheLiveValues: the state readout shows '----'
   with a round state of 'InProgress'` - the same literal the `-cpp` leg's empty
   variant produces.
2. Confirm the PASS at **both** framerate legs (`fps_legs: [60, 20]`). A clock
   bug that only shows at 20 Hz is exactly what that leg exists to find - and so
   is the step-0 offset above.
3. Read the L2I check details and confirm
   `..._answer_is_the_one_blueprint` says **`abstract=read`**, not `abstract=?`.
   `?` means the grader's abstractness probe is blind in a live editor, which
   silently restores a divergence from the fixture's own resolver
   (`CraftBenchFunctionalTest.cpp:682-687`) rather than failing loudly. The
   grader's logic is pinned offline by
   `tools/verify-single/tests/test_introspect_t2_race_clock_bp.py`; only a
   real editor can confirm the three UE API names it leans on.
4. Re-discriminate `t2-race-clock-cpp` as well. The two legs share
   one fixture; a change that fixes this leg and breaks that one is a net loss and
   grading both is the only way to see it.
5. The owner has to PLAY it (2026-08-18 directive). Same map as the C++ leg, so
   the play project already carries it.

---

## AS BUILT 2026-08-23 — where the shipped asset differs from the recipe above

The asset exists and compiles clean. Three places the graph is NOT what this file
says, each because the recipe was not buildable as written. **A recipe that does
not match the shipped asset is its own trap**, so they are recorded here rather
than left for the next reader to discover by diffing.

1. **`Length > 0` became `IsValid(the retrieved element)`.** The recipe's
   empty-array guard is not buildable through the MCP graph tools: `Array_Length`
   takes a WILDCARD `Target Array`, and a `CallFunction` wildcard pin does not
   specialise when wired through that layer, so the Blueprint fails to compile
   with *"Target Array's type is not yet determined"* — on a freshly created node
   too, not just a re-wired one. Native nodes (`K2Node_GetArrayItem`, the
   `ForEachLoop` macro) resolve their wildcards fine; only library CustomThunks
   do not.
   The substitution is behaviourally equivalent and strictly stronger: on an empty
   array `Get (a copy)` returns null and `IsValid` is false, so the early-out is
   the same, and it additionally rejects a non-empty array whose element is null.
2. **`Set Text` is `K2_SetText`.** `UTextRenderComponent::SetText` is a bare
   `UFUNCTION()` and is NOT callable from a Blueprint
   (`TextRenderComponent.h:103-104`); the exposed one is `K2_SetText`, display
   name "Set Text" (`:107-108`). Calling the wrong one compiles as
   *"function 'SetText' should not be called from Blueprints"*.
3. **The three "collapsed functions" are real Blueprint FUNCTIONS.** They have to
   be: `Refresh Readouts` is called from `BeginPlay`, from `Tick` and from
   `Start Fresh Round`, and a collapsed subgraph (`K2Node_Composite`) is one
   inline block with a single entry — it cannot be called from three places at
   all. Behaviour is identical for these graphs (no latent nodes).

One clause of the recipe's REASONING is also stale, though its instruction stands.
The asset table says the swap "carries the transform and the tags and NOTHING
else, so the class defaults are the round's starting state". That stopped being
true when the surface lane learned to carry per-instance state
(`SpawnStandInFor` -> `CopyPropertiesForUnrelatedObjects` +
`RepointReferencesTo`, deferred spawn). `PointValue = 40` is still the right
class default — it is simply now overwritten by each coin's own placed value
rather than being the only value in play — so follow the instruction, not the
justification.

### 4. The recipe's readout timing is WRONG, and it fails a correct submission

**Measured 2026-08-23**, on the asset built exactly as written above:

```
ReadoutsShowTheLiveValues: the score readout shows 0 with a score of 15
```

The graph above banks the score FROM THE COIN (`Set Score` on the round) and leaves
the refresh to the round's next `Event Tick`. The `-cpp` reference does not: its
coin calls `Round->AddPoints(PointValue)`, and `ARaceRoundBase::AddPoints` is

```cpp
Score += Points;
RefreshFaces();      // same synchronous call
```

so the bank and the refresh are ATOMIC. Deferring the refresh by one frame leaves
the readout stale at the moment the fixture samples, and **`-deterministic -FPS=60`
makes that reproducible rather than flaky** — fixed timestep, fixed tick order, so
if the coin's overlap fires after the round's tick within a frame it does so every
run.

Two things ruled OUT along the way, so nobody re-checks them:

* **Not a stale-tick problem.** `ARaceRoundBase`'s constructor sets
  `PrimaryActorTick.bCanEverTick = true`, and the readout showed a literal `0`
  rather than the shipped placeholder `"SCORE --"`. `FirstNumber("SCORE --")`
  returns **-1** and the fixture's check is `if (ShownScore >= 0 && ...)`, so the
  placeholder would have SKIPPED the check entirely. A `0` proves the refresh ran
  and read a pre-bank value.
* **Not the swap dropping per-instance values.** The message says `score of 15`,
  which is the first placed coin's own `PointValue` — not this asset's class
  default of 40. `CopyPropertiesForUnrelatedObjects` carried it across correctly.

**AS BUILT, and this is what the recipe should say:** `BP_RaceRound` gains a
function `Add Points (Points : Integer)` — `Set Score = Get Score + Points`, then
call `Refresh Readouts` — and the coin, after its `RoundState == "InProgress"`
check, casts the tagged actor to `BP_RaceRound_C` and calls it, instead of doing
its own `Get Score` / `+` / `Set Score`. That mirrors the C++ reference's shape
exactly: the round owns both the arithmetic and the refresh, and the coin only
asks.

The cast couples the two Blueprints, which is fine and is what the asset table
already implies — exactly one Blueprint per placed class, so `BP_RaceRound_C` is
unambiguous within a submission.

**Time source, stated because it is graded:** the round anchors on
`GetTimeSeconds` (UGameplayStatics, WORLD time), matching the fixture's own
`World->GetTimeSeconds()`. The recipe's "[Get Game Time in Seconds] (target =
self)" would be actor time, which is a different quantity.
