---
id: t3-reach-the-exit-before-they-see-you
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_StealthYard :: AStealthYardFunctionalTest"]
fps_legs: [60, 20]
---

# t3-reach-the-exit-before-they-see-you

A walled night yard with one way out. Three watchers pace lit rounds behind painted
sight arcs, a rail truck grinds back and forth making and breaking shadows, and a mast
by the gate carries three lights — **running**, **away**, **caught** — of which exactly
one burns. A round begins when the runner steps on the start plate and ends **once**:
either a watcher sees the runner (caught) or the runner reaches the gate (away). The
first ending wins for ever, the yard stands down when it happens, and the whole thing
re-arms on the next plate click.

> **Built against the 2026-08-18 difficulty bar.** Three subsystems that genuinely
> interact — per-watcher live perception against moving occluders, an exclusive
> re-armable terminal outcome, and the watchers' own drive state, which the outcome
> feeds BACK into. Getting perception right and the feedback wrong fails a named gate;
> getting the feedback right and perception wrong fails a different one. Every
> load-bearing number is read from the world at runtime, and several are changed mid-run
> by the fixture so no cached constant survives.
>
> **Three locally-reasonable wrong answers, all of which compile, read correctly and
> pass every surface check.** (1) Detection evaluated when a watcher reaches a patrol
> post, or on a one-to-two-second re-scan. (2) A single sight radius shared across three
> watchers who look interchangeable. (3) **The stand-down lamps RE-DERIVED instead of
> remembered** — the yard has to go on showing *who* caught the runner after the
> watchers have frozen and the runner has walked away, so the one question the
> submission cannot answer by asking the world again is the one the last gate asks. None
> of the three is hinted at in the prompt; each dies at a different named gate.

## Primary concept

- `ai-perception` — an agent deciding, from its own settings, what it can see right
  now, and a system reacting to that decision
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/ai-perception-in-unreal-engine)

The load-bearing behaviour is **a per-instance, per-frame sight test against live
geometry, feeding an exclusive terminal state machine whose output is fed back into the
observers themselves**. The grade never asks *how*: a `Tick` on the mast, a `Tick` on a
watcher, a fast repeating timer on the runner — all pass identically, as long as the
yard settles within the quarter second the prompt promises.

## Composed concepts

- `traces-overview` — deciding whether anything solid stands on the line between two
  places, re-asked every instant because one of the solid things is driving past
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/traces-in-unreal-engine---overview)
- `actor-lifecycle` — the yard is a fixed cast of placed actors; the logic has to live
  on one of them and be correct from the first frame
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-actor-lifecycle)
- `collision-overview` — what is solid and what is not is the whole occlusion rule; the
  crates, the wall and the truck block and nothing else in the yard does
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine---overview)
- `ai-components` — per-instance sight settings read off the thing that owns them, three
  watchers with three different sets of numbers
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/ai-components-in-unreal-engine)
- `movement-components` — the graded readout includes the pace each watcher walks at,
  which the outcome drives to zero and a fresh round restores to that watcher's own base
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/movement-components-in-unreal-engine)

**Production pattern.** This is the standard stealth-level loop: per-guard sight cones
with distinct range and FOV, a line-of-sight check against static and *dynamic* cover, a
mission-state machine with mutually exclusive terminal outcomes that latch, a
checkpoint/restart that re-arms the whole level, and a world-visible state readout. It is
the shape described in Epic's own AI Perception documentation combined with the
detected/undetected mission-outcome loop every shipped stealth game uses (Metal Gear's
alert state, Dishonored's detection meter, Hitman's mission-failed latch); the
moving-truck occluder is the standard "dynamic cover" clause from the same genre.

**How the three subsystems interact.** They are wired in a loop, and the loop is what
the gates measure.

**Perception feeds the outcome.** Each watcher's verdict is its own: its own reach, its
own view width, its own live transform while it walks and turns, and a clear-line test
against three crate stacks, a wall and a truck that is moving the whole time. The
outcome is derived from the union of those verdicts and from the gate volume — asked of
the gate, which is the only reader the prompt names. A submission that shares one sight
radius across the three watchers
produces the right answer at most spots and the wrong one at the split spot, where the
same standing place is invisible on one watch and plainly visible on the next.

**The outcome feeds back into perception's own subjects.** When a round ends every
watcher stops dead, and the lamps that go on burning are exactly the ones belonging to
whoever could see the runner *at the instant the round ended* — nobody's, if the round
ended at the gate. That is the reverse edge, and it carries the coupling in both
directions: perception right and the feedback wrong fails
`TheYardStandsDownWhenTheRoundIsOver`; the feedback right and perception wrong fails
`EachWatcherShowsWhatItCanSeeRightNow`. It is also the one fact in the yard that cannot
be recovered by asking the world again — a second after the catch the watchers are frozen
and the runner has walked out of the cone, so "who can see the runner" and "who saw the
runner" are different questions with different answers, and only the second one is on
show. Neither documentation page describes the pair.

**The plate closes the loop.** Nothing in the yard announces a fresh round; the plate
simply counts, and a changed count is the only re-arm. So the outcome cannot be a
one-shot latch, the watchers' paces cannot be set once at BeginPlay, and the numbers
cannot be cached — between two of the rounds the sergeant swaps which watcher walks which
round and re-sets three of their numbers, with nothing to hear it happen.

## Prompt given to the agent

> **Where you are.** A walled yard at night, one way out, and three watchers between the
> character the player controls — the **runner** — and the gate.
>
> **The board at the gate.** A mast beside the gate carries three lights: **running**,
> **away** and **caught**. Exactly one of the three burns at any moment, and those
> lights are the only thing anyone outside the yard can read. All three start dark, and
> nothing yet decides when to throw any of them. Before anybody has stepped on the plate
> the yard is simply waiting, and waiting reads **running**.
>
> **The round.** A round runs from the moment it begins until it ends, and it ends in
> exactly one of two ways: the runner reaches the gate — **away** — or a watcher sees
> the runner — **caught**. Whichever of those happens first is how that round ended, and
> nothing that happens afterwards changes it: reaching the gate after being caught still
> reads caught, and being seen after getting away still reads away. A round ends once
> and only once.
>
> **Starting a fresh round.** There is a plate on the floor at the start line. It clicks
> its own number up by one every time somebody steps onto it, and it is already built and
> working. Whenever that number changes a fresh round has begun: the board goes back to
> running and nothing from the round before counts for anything.
>
> **What a watcher can see.** A watcher sees the runner when the runner is inside **its
> own reach**, and inside **its own view width** either side of whichever way that
> watcher happens to be facing, and nothing solid stands between the two of them. Both
> of those numbers belong to the watcher — they are set on it, and the arc it covers is
> painted on the floor around its round. Measure flat, from where the watcher is
> standing to where the runner is standing; exactly at the edge of the reach, or exactly
> at the edge of the view width, still counts as seen. **Only the crates, the wall and
> the truck are solid.** The posts, the lamps, the mast, the plate, the gate and the
> marks painted on the floor never block anything; no watcher is ever in the way of
> another watcher's view; and the runner is never something in the way of being seen.
> Everything solid stands from the floor to well over head height and the floor is dead
> level, so the height you take the line at makes no difference to the answer.
>
> Nothing about this holds still. While a round runs the watchers are on their feet —
> each walks its own round and turns at the ends — and the truck grinds back and forth
> across the yard all night, making and breaking shadows as it goes.
>
> **What each watcher shows.** Every watcher carries a lamp on its head. While a round is
> running, a watcher's lamp burns while that watcher can see the runner and is dark
> otherwise. Read each watcher for itself: one watcher seeing the runner says nothing
> about what another can see.
>
> **When a round is over, the yard stands down.** From the moment a round has ended until
> a fresh one begins, every watcher **stands still** — its pace set to nothing. If the
> round ended because a watcher saw the runner, then the lamp of **every watcher that
> could see the runner at that instant** goes on burning until the next round begins, and
> every other lamp is dark. If the round ended at the gate instead, every lamp is dark.
> When a fresh round begins they all walk their rounds again, each at **its own base
> pace**, which is a third number set on the watcher.
>
> The yard has **a quarter of a second** to catch up after anything changes.
>
> The night is long: the yard must be able to run round after round, ending some of them
> one way and some the other, in any order, for as many rounds as the night calls for.
>
> Between rounds the sergeant may swap which watcher walks which round and re-set the
> numbers written on them. Nothing announces it.
>
> The yard is not yours to rearrange. Do not move the watchers, the posts, the crates,
> the wall, the truck, the plate or the mast, and do not change any number written on any
> of them — except the one pace each watcher is currently walking at, which is yours to
> set. Everything the yard needs in order to *show* its state is already built and
> working: each light on the mast has a switch, each watcher's lamp has a switch, each
> watcher has that pace you can set and walks its round by itself, the plate counts, the
> gate knows when somebody is standing in it, and the truck drives itself. **Nothing
> decides when to throw any of it**, and because the yard itself is fixed, whatever does
> the deciding has to live on something already standing in it.
>
> **Write your solution in C++ under `Source/ThirdPerson/`** — that is the deliverable
> root. Do not edit the level, any config file, or any test file.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on this
substrate). `Source/CraftBenchTests/` is deny-listed and a submission file under it is a
SANDBOX-REJECT (exit 4), not a graded FAIL; so are `Content/Maps/`,
`Content/ThirdPerson/`, `Content/Characters/` and every `Config/` file (no
`config_allow` is declared by this task).

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t3-reach-the-exit-before-they-see-you/StealthWatcherActor.h` / `.cpp` —
  `class THIRDPERSON_API AStealthWatcherActor : public AActor`, tagged `StealthWatcher`.
  Supplied and **working**:
  - `Hull` — a 70 x 180 cm capsule, **the root**, `BlockAll`, movable; plus a body mesh
    and a nose cone so the facing reads at a glance. (A capsule root, not the mesh: a
    mesh made root and offset upward leaves collision half-buried in the floor and
    refuses every swept move.)
  - `UPROPERTY(EditAnywhere, BlueprintReadOnly) float SightReachUu`,
    `float SightHalfAngleDeg`, `float BasePaceUuPerSec`, `FName RoundTag` — **read them
    off the watcher; the three watchers in the yard are not set to the same values, and
    the sergeant may re-set them during the night.**
  - `UPROPERTY(EditAnywhere, BlueprintReadWrite) float PaceUuPerSec` — **the one that is
    yours to set.** Initialised to `BasePaceUuPerSec` in `BeginPlay`. A pace of nothing
    means the watcher stands where it is, facing the way it was facing.
  - `UFUNCTION(BlueprintCallable) void SetLampLit(bool)` and
    `UFUNCTION(BlueprintPure) bool IsLampLit() const` — the head lamp's switch. It sets
    the light's intensity **and** swaps the head's material (a material *swap*, not a
    parameter write, because not every prototype material here carries a colour
    parameter and a set that silently does nothing leaves the state invisible while
    looking like it worked). Starts dark.
  - A `Tick` that paces the watcher between the two posts carrying its own `RoundTag` at
    whatever `PaceUuPerSec` currently says, never overshooting, always facing the way it
    moves, and re-finding its posts if `RoundTag` changes under its feet.
  - **No perception, no reference to the runner, no reference to the mast, and it never
    writes its own pace and never throws its own lamp.**
- `Tasks/t3-reach-the-exit-before-they-see-you/StealthMastActor.h` / `.cpp` —
  `AStealthMastActor`, tagged `StealthMast`. **Three switches and nothing else**: the
  three point lights `RunningLight` / `AwayLight` / `CaughtLight`, their switches
  `SetRunningLit` / `SetAwayLit` / `SetCaughtLit` (each sets its light's intensity and
  swaps its housing's material), and the three matching `IsXLit()` reads. All three
  start dark. It deliberately carries **no outcome property of its own**: the three
  lights *are* the outcome, so there is no ungraded switch a submission can set instead
  of doing the work. Non-colliding on every channel.
- `Tasks/t3-reach-the-exit-before-they-see-you/StealthStartPlateActor.h` / `.cpp` —
  `AStealthStartPlateActor`, tagged `StealthStartPlate`. Supplied and **working**: a
  240 x 240 cm pad painted on the floor with an overlap region in the air above it —
  **both non-colliding on every channel**, so the plate cannot stop a line taken at any
  height — an `int32 RoundIndex` that clicks up
  by one every time a pawn steps onto it, and a text face over the plate painting that
  number in the air. It does not know what a round is. Non-colliding to a line.
- `Tasks/t3-reach-the-exit-before-they-see-you/StealthGateActor.h` / `.cpp` —
  `AStealthGateActor`, tagged `StealthGate`. Supplied and **working**: a gateway volume
  and `UFUNCTION(BlueprintPure) bool IsSomebodyStandingInIt() const`, asked live.
  Non-colliding to a line.
- `Tasks/t3-reach-the-exit-before-they-see-you/StealthBlockerActor.h` / `.cpp` —
  `AStealthBlockerActor`, tagged `StealthBlocker`. The crate stacks and the wall. A
  **solid** box sized directly from `FVector BlockHalfExtentUu` (never by scaling
  anything — a scaled parent multiplies both a child's offset and its collision extent),
  hung off an unscaled anchor at the actor's own location so it stands on the floor and
  rises to well above head height, with a mesh face that follows it exactly.
- `Tasks/t3-reach-the-exit-before-they-see-you/StealthTruckActor.h` / `.cpp` —
  `AStealthTruckActor`, tagged `StealthTruck`. Supplied and **working**: the same solid
  box shape, plus `FVector RailHalfSpanUu` and `float RailSpeedUuPerSec`, and a `Tick`
  that runs it from `(placed - RailHalfSpanUu)` to `(placed + RailHalfSpanUu)` and back
  for ever, never overshooting. It cannot be told to stop.
- `Tasks/t3-reach-the-exit-before-they-see-you/StealthPostActor.h` / `.cpp` —
  `AStealthPostActor`. Six of them mark the three rounds; each carries the tag its round
  is known by. Non-colliding on every channel.
- `Content/Maps/t3-reach-the-exit-before-they-see-you/L_StealthYard.umap` — the staged
  yard, committed binary. World Settings name **NO** game mode, so the level inherits
  `BP_ThirdPersonGameMode` — which carries `BP_ThirdPersonPlayerController` and
  `IMC_Default`, so the mannequin is visible, animated **and drivable by a human with
  WASD**. What is in it:

  | Element | Placement | Notes |
  |---|---|---|
  | Floor | 14,000 x 11,000, dead level, striped every 400 cm, stripes **non-colliding** | |
  | The lane | one straight run from the start line to the gate, painted on the floor | the route a human walks |
  | Start plate | one `AStealthStartPlateActor` at the start line, its number in the air above it | |
  | Gate | one `AStealthGateActor` at the far end | |
  | Mast | one `AStealthMastActor` beside the gate, **non-colliding** | three lights, all dark |
  | Three rounds | two in the open, one behind the wall, six posts | painted on the floor |
  | Three `AStealthWatcherActor`s | one per round, **movable** | two of them trade rounds part way through |
  | Wall | one long `AStealthBlockerActor`, **solid**, between the walled round and everything south of it | |
  | Crate stacks | three `AStealthBlockerActor`s along the lane, **solid** | they make the shadow lane |
  | Rail truck | one `AStealthTruckActor`, **solid**, on a rail clear of the lane | it never touches the runner |
  | Sight arcs | each watcher's own wedge and its widest-offset line painted on the floor | the level is honest about what it is asking |
  | PlayerStart | on the lane beside the plate, **not on it**, out of every watcher's view | |
  | Backdrop + landmarks | a low back wall and two differently sized posts, **non-colliding** | a moving camera is distinguishable from a still one |
  | Test harness | one placed harness actor | |

  **Everything except the floor, the crates, the wall, the truck and the three watchers
  is non-colliding on every channel**, so nothing else in the yard stops a line. **The
  watchers' numbers, the truck's numbers and the blocks' footprints are deliberately NOT
  in this section.** They are readable in the level, on the things themselves.

- `cameras.json` (the camera-plan lane; not part of this release) — the
  presentation-only camera plan. Non-gating.

Files that **do not exist**:

- No perception of any kind, no outcome, no re-arm, no code that throws a mast light or
  a head lamp or writes a watcher's pace, no Blueprint subclass, no level edits. Nothing
  is unimplemented — everything is simply unwired, and a yard where nobody decides
  anything is already wrong on its first frame: the mast's three lights all start dark
  and exactly one of them must burn at any moment.
- No test source in the agent's writable path. The test harness lives in a separate
  module the agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t3-reach-the-exit-before-they-see-you/L_StealthYard.umap` on the
**ThirdPerson** substrate, ticked at a fixed deterministic step
(`-deterministic -FPS=<rate>`), **twice**: once at 60 and once at 20 (`fps_legs:
[60, 20]`), each in its own PIE process. Every staged window is opened and closed on
world game-time and on live geometry, never on a frame count, so both legs stage
identically; a tick counter fitted to 60 Hz misses every window at 20 Hz.

Verification primitive: **pie-checkpoint-sampling** plus an every-frame readback of the
mast's three **light intensities**, each watcher's head-lamp **light intensity** and each
watcher's **`PaceUuPerSec`** — what a reviewer sees — over a fixture-driven walk
(`AddMovementInput`, the Tier-1 input lane), compared against the fixture's own running
model of the whole rule.

### The fixture runs the same rule

Every frame the fixture re-reads, **by name and live**, each watcher's `SightReachUu`,
`SightHalfAngleDeg`, `BasePaceUuPerSec` and `RoundTag`, each watcher's live transform,
the truck's `RailHalfSpanUu`, `RailSpeedUuPerSec` and live transform, every blocker's
`BlockHalfExtentUu` and transform, and the plate's `RoundIndex`; and steps its own model:
the same flat reach-and-view-width predicate with the same inclusive edges, the same
flat clear-line test against the live footprints of the crates, the wall and the truck,
the same first-ending-wins latch, the same latched who-was-looking set, and the same
plate-click re-arm. Every gate compares the yard's **visible** state against that model.

**"The runner reached the gate" is asked OF THE GATE.** The prompt discloses exactly one
reader -- the gate knows when somebody is standing in it -- so the model calls that reader
by name rather than re-deriving standing-in-it from the volume's extents. Two definitions
of one disclosed fact is an undisclosed gate, and the re-derived one was the stricter of
the two: a point test on the runner's origin latches the away ending several frames after
the overlap the prompt points at, which is long enough to fail a correct submission on
`EveryRoundStartsCleanWhenThePlateClicks`. The reference found it first.

The model's clear-line test is a **2-D segment-versus-rectangle test against the live
footprints**, not a trace, so the fixture and a tracing submission are two independent
implementations of the same disclosed rule. That is deliberate: the map contract below
guarantees they cannot disagree.

### The staging contract — what `PrepareTest` refuses to start without

Each of these is a **HARNESS-PRECONDITION** (never a graded FAIL) because each one, if
broken, would make a *correct* submission fail:

1. **Height cannot matter.** Every solid thing (crates, wall, truck) rises from the
   floor itself to at least 400 cm; the floor is level to within 2 uu across the whole
   yard; **everything else in the yard, the start plate's pad included, is non-colliding
   on every channel and profile** — so the only solid things at ankle height are the ones
   that are solid all the way up. Probed by tracing from each watcher at nine phases of
   its round to a dozen points on the route at **four** heights (5 / 20 / 90 / 170 cm)
   and refusing to start if any two heights disagree, and by walking every
   `PrimitiveComponent` in the level. The 5 cm probe is what makes the prompt's promise
   true for a submission that reads "the line between those two spots on the floor"
   literally; a line taken at *exactly* floor level is coplanar with the floor plane and
   is the one height the promise does not cover, which is why the yard keeps nothing else
   solid down there.
2. **The route is never shoved.** No point of the fixture's route comes within 250 uu of
   the truck's swept footprint or within 400 uu of any watcher's round segment.
3. **The walled sentry is the widest-eyed thing in the yard, at every staging**: its
   `SightReachUu` exceeds every other watcher's by at least 1.25x and its
   `SightHalfAngleDeg` exceeds every other's, *after* the re-stage multipliers are
   applied; and its reach exceeds the distance from its round to the nearest route point,
   so a range-only sight test lights it. The wall's live footprint crosses the flat line
   from every phase of its round to every route point.
4. **The two ending-producing windows are far from every turn.** Round 1's truck-clear
   and round 3's cone-crossing each open and close strictly between two of the covering
   watcher's turns, give at least **1.0 s** of continuous visibility, and leave at least
   **2.0 s** of clearance to that watcher's nearest turn at **both** ends. Re-checked at
   both stagings. This is the anti-poller margin and it is the number Gate 10 must
   measure rather than trust.
5. **The split spot means opposite things.** At the split spot the watcher covering that
   round under staging 1 cannot hold the runner from **any** phase of its round (by at
   least 1.25x its reach), and the watcher covering it under staging 2 holds it for a
   window satisfying (4).
6. **The shadow windows are real.** While the runner stands at the shadow spot, the
   covering watcher's live reach and view width contain it continuously for at least
   3.0 s, and inside that stretch the truck's live footprint lies across the flat line
   for at least 1.5 s continuously.
7. **Nobody unplanned is looking.** At every judged frame of every hold, no watcher other
   than the one that window names is within 1.25x of its own reach of the runner.
8. **The plate is not stood on at spawn.** `RoundIndex` is 0 at `StartTest`.
9. **The start line and the gate are out of every live cone, at every phase and both
   stagings.** No watcher's reach reaches within **1.25x** of the plate or of the gate
   volume from any point of any round. This is not decoration: a watcher that can see
   the start line ends every round on the frame it begins — which would make the crossing
   gate unreachable while looking exactly like a submission that latches too eagerly — and
   one that can see the gate makes both away endings impossible. The authored geometry
   leaves **1.31x** at both ends, and this precondition is what turns a later drift into a
   `HARNESS-PRECONDITION` instead of a graded FAIL.

   **It also makes one disclosed rule unreachable, and that rule is therefore not in the
   prompt.** Because no watcher can ever hold the gate, no frame can have "a watcher sees
   the runner" and "the runner is in the gate" at once, so a simultaneous tie between the
   two endings cannot occur in this yard. An earlier draft of the prompt settled the tie
   ("caught wins") and this document claimed a gate for it; the claim was false — an
   implementation resolving it either way is byte-identical over the whole drive. The
   model still asks caught first, because a model has to pick something; nothing grades
   the choice, and nothing tells the agent to make it.

### The authored geometry, and what its own solvers make of it

**SOLVED, NOT MEASURED.** These are the constants in
`authoring/author_map.py` plus the output of that script's own solvers, run offline
against them (`_t3fix`-style offline harness; the same arithmetic the fixture re-runs at
`PrepareTest`). Nothing here has been through an engine. The fixture re-derives every
solved row at run time from the placed level and refuses to start — `HARNESS-PRECONDITION`,
never a graded FAIL — if any floor is missed, so a later map drift reports itself instead
of failing a correct submission.

The closed form the whole layout is solved from: a watcher walking a straight round of
length `L`, facing along it, holds a **stationary target beyond the end of the round** at
perpendicular offset `p` and along-track lead `b` inside its cone while
`b >= p / tan(theta)`, and inside its reach while `b <= sqrt(R^2 - p^2)`. Both ends are
mid-leg exactly when both of those bounds lie strictly inside `[x_t - L/2, x_t + L/2]`.
The visible window is `(sqrt(R^2 - p^2) - p / tan(theta)) / pace` seconds and the
clearance to each turn is the remaining travel over the pace. The **return** leg has the
target more than 90 degrees off the facing whatever the reach, so there is exactly one
visible window per lap — which is why every spot sits beyond the end of a round rather
than beside it.

| Quantity | Authored / solved value |
|---|---|
| Floor | `(-7,400, -3,400)` to `(+7,400, +5,600)`, dead level, striped every 400 cm |
| Lane (the route) | one straight run at `y = -1,400`, from the plate at `x = -5,800` to the gate at `x = +5,800` |
| Mast / PlayerStart | `(+5,800, -700)` / `(-5,800, -1,900)` — beside the plate, never on it |
| Round CENTRE | posts at `(-1,200, +200)` and `(+1,200, +200)` — 2,400 uu along X |
| Round NORTH | posts at `(-1,200, +2,000)` and `(+1,200, +2,000)` — 2,400 uu along X |
| Round WALLED | posts at `(-1,000, +4,200)` and `(+1,000, +4,200)` — 2,000 uu along X |
| The wall | centred `(0, +3,200)`, half-extent `(4,600, 150, 220)` |
| Crates | `(-3,000, -400)` half `(600, 400, 260)`; `(+1,900, -2,400)` and `(+4,600, +700)` half `(400, 400, 260)` |
| Watcher NEAR, staging 1 | `RoundCentre`, reach **2,000**, view width **40 deg**, base pace **120** — a 40.0 s lap |
| Watcher FAR, staging 1 | `RoundNorth`, reach **3,100**, view width **30 deg**, base pace **220** |
| Sentry WALLED (never re-staged) | `RoundWalled`, reach **6,400**, view width **75 deg**, base pace **260** |
| Re-stage (between rounds 2 and 3) | NEAR and FAR swap `RoundTag` and are set down on their new rounds' near posts; FAR's reach x1.2 -> **3,720**; NEAR's view width x0.6 -> **24 deg**; NEAR's base pace x1.25 -> **150** |
| Truck | placed `(-760, -585)`, footprint half `(350, 150, 220)`, rail half-span `(0, 415)`, **150 uu/s** — a 5.53 s one-way pass. The rail is boxed in: its swept footprint must stay 200 uu clear of the lane round to its north and 250 uu clear of the lane to its south, which leaves ~1,150 uu of room for a 300 uu truck and its travel |
| SHADOW spot (solved) | `(-1,393, -600)` — 800 uu off the lane round, **not** on the lane |
| Shadow window (solved) | **7.33 s** of continuous sight, **6.33 s** of clearance to each turn |
| Truck cover on that line (solved) | **2.31 s** continuous at the window's worst phase, and it lets go again — against a floor of 1.5 x `kMinTruckCoverS` = 2.25 s |
| SPLIT spot (solved) | `(+3,065, -1,400)` — on the lane, invisible to all three on watch 1 |
| Round-3 crossing (solved) | **2.67 s** visible, **4.12 s** of clearance to both turns |
| Start line and gate vs the live cones | both **4,870 uu** from the nearest round against a post-re-stage reach of 3,720 — **1.31x** out of reach at both ends |
| Sentry check | 6,400 > 1.25 x 3,720 (the largest reach any watcher has after the re-stage) and 75 deg > 40 deg (widest view). It holds **11 of 25** sampled route points with the wall taken away and **0 of 25** with it there |
| Safe lane bands | watch 1: the whole lane. Watch 2: `[-5,800,-3,700]`, `[-1,500,+1,500]`, `[+4,600,+5,800]` |
| Drive / sentinel | 18 phases, **~370 s** modelled if phase 2 takes the first shadow window, **~570 s** if it takes the third; 68 checkpoints every 8 s to 544 s, **SENTINEL at 640 s** |

**Two things the solvers proved that the arithmetic alone could not.** Both were run
offline against these constants before the map was authored, and both are the reason the
drive can finish at all:

- **The shadow entry ripens, repeatedly.** Simulating the covering watcher's 40.0 s lap
  against the truck's 5.53 s one-way pass finds **4 distinct departure windows in the
  first 400 s** — at t ≈ 65 s (3.05 s wide), 145 s, 265 s and 345 s — each a stretch of
  moments at which walking in arrives unseen, arrives inside a span where the cone holds
  the spot and the truck lies across the line whether the runner stops short or long,
  holds it past the cover floor, and then lets go while the cone still holds. Phase 2's
  deadline covers ~292 s from its own start, so three of the four are reachable.

  **The lane watcher's pace and the truck's speed are what set that beat, and they are
  not free numbers.** At the originally authored 180 / 200 exactly ONE departure moment
  exists in 400 s — a coincidence, not a staging, and one that a small difference between
  the engine's start poses and the model's would move out from under the drive. 120 / 150
  is the swept choice. Changing either number means re-running the sweep.
- **The governor releases every lane leg on the second watch.** Scanning every relative
  phase of the covering watcher's lap, the longest a leg ever waits for a release is
  **11.8 s** (the long hop between the two western rest bands); no phase offset leaves any
  leg unreleasable.
### The drive

Four rounds, staged **caught, away, caught, away**, driven with the shipping per-frame
`AddMovementInput` timeline. Every hold is *"stay here until MY model says X"*, never
*"stay here for T seconds"*, except where a fixed dwell is the thing being asserted.

Every walk taken **while a round is still running** is released only once the model has
simulated all three watchers forward over the transit itself and proved that no point of
the leg can be seen before the runner gets there. Two properties of that rule are
load-bearing: the horizon is the **transit**, never a fixed stretch of seconds (two of the
places this drive stands are places a cone is *meant* to sweep, so a governor demanding
safety after arrival could never release the walk to them); and once a round has **ended**
the governor is skipped entirely (three of the drive's most important walks start or end
somewhere a watcher can plainly see, and being seen changes nothing about a round that is
already over).

| Phase | Round | Where | Until |
|---|---|---|---|
| 0 | — | stand at the PlayerStart, off the plate | 3 s (gates on from the first judged frame; the board must already read running) |
| 1 | 1 | walk onto the plate | `RoundIndex` becomes 1 |
| 2 | 1 | walk to the lane REST point beside the shadow spot, wait there, and step into the SHADOW spot when the covering watcher's cone and the truck's rail come into step | the truck's footprint has lain across the covering watcher's line for 1.5 s while the runner is inside that watcher's live reach and view width |
| 3 | 1 | stand still | the truck's footprint clears the line; the board must read caught within 0.4 s |
| 4 | 1 | walk to the OPEN spot, nobody able to see | 6 s |
| 5 | 1 | walk into the gate volume, back 900 uu down the lane, and in again | both entries complete and the walk is finished |
| 6 | 2 | walk back onto the plate | `RoundIndex` becomes 2 |
| 7 | 2 | walk to the SPLIT spot and stand | the covering watcher has walked one complete lap |
| 8 | 2 | run the lane to the gate | the board reads away |
| 9 | 2 | walk to a spot squarely inside the (now frozen) covering watcher's live reach and view width, and stand | 6 s |
| 10 | — | **the sergeant changes the watch** — the yard is stood down, so no swap can jolt an outcome | 4 s; every gate suppressed for 2 s either side |
| 11 | 3 | walk back onto the plate | `RoundIndex` becomes 3 |
| 12 | 3 | walk to the identical SPLIT spot and stand | the covering watcher's cone crosses the runner mid-leg; the board must read caught within 0.4 s of the model's first visible frame |
| 13 | 3 | walk to the OPEN spot, nobody able to see | 6 s |
| 14 | 3 | walk into the gate volume, back 900 uu down the lane, and in again | both entries complete and the walk is finished |
| 15 | 4 | walk back onto the plate | `RoundIndex` becomes 4 |
| 16 | 4 | run the lane to the gate | the board reads away |
| 17 | 4 | walk into the covering watcher's frozen reach and view width, and stand | 6 s, then the run-level gate |

**Why the truck window is staged once and not twice.** Four rounds allow at most two
caught endings, and both are spoken for: round 1 by the truck letting go of the line, and
round 3 by the cone crossing the split spot — the two independent deaths of the poller.
A second truck window inside an **away** round is not staged, because the runner would
have to leave the covering watcher's cone before the truck cleared it, and a walk out of a
cone that is only survivable while a moving occluder happens to be in the way is a race
the drive cannot govern. The truck is not thereby under-graded: its *live footprint* is in
the model's visible-set computation on **every** judged frame of the run, so a cached
blocker set is wrong wherever the truck actually matters, and the covered half of the
shadow window is asserted continuously across phases 2 and 3.
### Settle and suppression

Nothing is judged on a frame where any of these hold. Each is a **widening** of the
disclosed contract, never a narrowing:

- less than **0.4 s** since the fixture's own model last changed (1.6x the quarter second
  the prompt promises);
- any watcher's verdict is **marginal** — within 3 degrees of its own view width *while*
  inside 1.06x its own reach, or within 6% of its own reach *while* inside its view width
  plus 3 degrees. (Both halves, not either: a watcher whose facing sweeps past its own
  view width while the runner is four times its reach away is not marginal about
  anything.)
- the truck's footprint edge is within **40 uu** of any watcher-to-runner line;
- within **2 s** of the re-stage.

### The sentinel

The checkpoint schedule is **68 graded checkpoints every 8 s** (8 s .. 544 s) plus a
**SENTINEL at t = 640 s**, past the ~370-570 s the drive models, because
`ACraftBenchFunctionalTest::Tick` ends the test the moment the last scheduled checkpoint
is sampled. The spread is the shadow entry: the drive waits on the lane for the covering
watcher's lap and the truck's rail to line up, and how long that takes is the yard's own
arithmetic — the first of the four departure windows is at ~65 s and the third at ~265 s.
The run-level gate is evaluated when the last phase completes **and** again at the
sentinel, whichever comes first, and only then does the fixture call
`FinishTest(Succeeded)`. A phase that stalls is caught by its own derived deadline long
before the sentinel, so the sentinel costs nothing unless something is already wrong. The
three numbers here are the three constants at the top of `StealthYardFunctionalTest.cpp`
(`kGradedCheckpoints`, `kCheckpointEveryS`, `kSentinelAtS`); an earlier draft of this
document, `notes.md` and the fixture each carried a different set.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

**Gate precedence, in the order the fixture evaluates them. Exactly one of 3-8 is armed
on any judged frame, and exactly one of 9-10 runs after it, so a named FAIL is never a
race between two of them.**

```text
 1  TheYardIsNotYoursToRewire        -- every frame, UNSUPPRESSED, from the first
 -- everything below is judged only inside the settle window the prompt promises --
 2  ExactlyOneLampBurnsOnTheBoard    -- every JUDGED frame, from the first
 -- exactly one BOARD gate, narrowest window first --
 3  SeenTheMomentTheyCross           -- phase 12's crossing window
 4  TheTruckMakesAShadowWhileItPasses-- phases 2-3
 5  EachWatcherSeesWithItsOwnEyes    -- phases 7 and 12's hold (before first-visible)
 6  CaughtIsFinalEvenAtTheGate       -- phases 4-5 and 13-14
 7  AwayIsFinalEvenInPlainSight      -- phases 9 and 17
 8  EveryRoundStartsCleanWhenThePlateClicks -- every other judged frame of a running
                                       round, from 0.4 s after the plate's number changed
 -- then exactly one INDEPENDENT CHANNEL gate, always LAST, and only once the armed
 -- board gate has already agreed --
 9  EachWatcherShowsWhatItCanSeeRightNow    -- while a round is running
10  TheYardStandsDownWhenTheRoundIsOver     -- while a round is over
 -- run level --
11  BothEndingsHappenedTwice         -- at drive completion and again at the sentinel
```

**Gate 2 is judged INSIDE the settle window, not outside it.** It used to run before the
suppression check, which quietly narrowed the disclosed contract: a submission that
paints the board from its own `Tick` rather than from `BeginPlay` reads zero of three on
the first frame whenever actor tick order puts the fixture ahead of the mast — something
the agent neither controls nor can observe — and a board transition split across two
frames reads zero or two for one frame. The prompt gives the yard a quarter of a second
after anything changes and makes no exception for this gate, so the fixture makes none
either. Nothing is lost: an empty delivery still dies here, on the first judged frame,
because nothing ever settles it.

**Where the LIT half of the lamp channel lives.** Seeing the runner is what ENDS a round,
so on every frame gate 9 can possibly run the model's visible set is necessarily EMPTY —
gate 9's teeth are *"no lamp burns that should not"*, which is precisely where a
range-only or occlusion-blind sight test dies (the whole truck window, and the walled
sentry on every judged frame of the run). The LIT half is gate 10's: when a round ends
caught, the lamps of the watchers that could see the runner **at that instant** go on
burning until the next plate click, and gate 10 requires the burning set to equal that
set exactly.

Gates 9 and 10 are mutually exclusive by definition (running versus over), so exactly one
of them runs on every judged frame. They are **not** suppressed inside a board gate's
window, because they are a genuinely separate channel — suppressing them would leave the
head lamps and the paces ungraded on exactly the frames that matter most. Running them
LAST, and only on a frame where the board has already been agreed, gets both: a wrong
board reading is always named by the board gate, and a right board reading with wrong
lamps or wrong paces is always named by the channel gate.

```text
assert: TheYardIsNotYoursToRewire -- every frame: each watcher's SightReachUu,
        SightHalfAngleDeg, BasePaceUuPerSec and RoundTag, the truck's RailHalfSpanUu
        and RailSpeedUuPerSec, every blocker's BlockHalfExtentUu, and the plate's step
        are exactly what the yard staged for the phase in progress (floats to 0.1%);
        the crates, the wall, the mast and the plate are within 2 uu of where the yard
        put them; the truck's live location is on its own rail; and EACH WATCHER IS ON
        ITS OWN ROUND -- within 60 uu of the segment between the two posts carrying its
        own RoundTag. The last clause is load-bearing rather than ceremonial: the
        fixture's model reads the watchers' LIVE transforms, so without it a submission
        that parks a watcher on the runner makes the model agree the round should be
        caught and every other window becomes unreachable -- a do-nothing pass.

assert: ExactlyOneLampBurnsOnTheBoard -- every JUDGED frame from the first, i.e.
        inside the same quarter-second settle window as every other gate: exactly one of
        RunningLight / AwayLight / CaughtLight is burning, read from the light itself
        (visible, not hidden, intensity > 0), never from a flag. The message names how
        many were burning and which. This is where the empty submission dies -- on the
        FIRST JUDGED FRAME of the run (about 0.4 s of world time in, well before the
        first checkpoint at 8 s), before any trigger has fired.

assert: SeenTheMomentTheyCross -- through phase 12's staged crossing: the board reads
        caught within 0.4 s of the model's first visible frame. The window opens and
        closes strictly between two of the covering watcher's turns, is at least 1.0 s
        long, and leaves at least 2.0 s of clearance to the nearest turn at both ends,
        so a submission that only re-asks the question when a watcher reaches a post --
        or on a one-to-two-second re-scan -- never samples inside it and the board still
        reads running when the window has closed. The message names the covering
        watcher, the seconds since its last turn, the seconds to its next, the model's
        first-visible time and what the board showed.

assert: TheTruckMakesAShadowWhileItPasses -- ONE staged window, spanning phases 2 and
        3, entered on a phase alignment the drive waits for rather than hopes for.
        While the truck's live footprint lies across the flat line from the covering
        watcher to the runner AND THE ROUND IS STILL RUNNING, that watcher's lamp is
        dark and the board still reads running -- even though the runner is inside that
        watcher's live reach and view width. Then, within 0.4 s of the footprint
        clearing that line, the BOARD reads caught, and that clearing is itself at least
        2.0 s from the covering watcher's nearest turn. Kills a blocker set cached at
        BeginPlay and a baked static visibility map: the geometry is only right if the
        line test is re-run against live transforms. The message names the truck's
        position, the two endpoints of the line, the lamp state and the board.

        THE COVERED HALF IS CONDITIONED ON THE ROUND STILL RUNNING, which is not
        ceremony: phase 3 waits out a full second after the clearing, and if the truck
        swings back across the line inside that second, a gate demanding a running board
        would be demanding it of a yard that is correctly showing caught. That is a
        false FAIL, and the reference finds it first.

        THE LAMP IS DELIBERATELY NOT ASSERTED LIT AT THAT CLEARING. The instant the
        watcher can see the runner the round has ENDED, and from that moment the lamps
        belong to the stand-down rule. The clearing's lit half is not lost, it MOVES: the
        stand-down gate then requires exactly that watcher's lamp -- and no other -- to
        burn for the whole of the round's stand-down, which is phases 4 and 5, some
        twenty seconds and two walks into the gateway later, with the runner nowhere the
        frozen watcher can see. So the lamp carries the "covered" half here, the board
        carries the "cleared" half here, and the "who cleared it" half is carried by name
        for the rest of the round.

assert: EachWatcherSeesWithItsOwnEyes -- at the SPLIT spot, an identical standing place
        walked in BOTH stagings with a DIFFERENT watcher covering that round: the board
        and every lamp match the model on every judged frame of the hold UP TO the
        model's first visible frame, after which SeenTheMomentTheyCross owns the window
        and the round has ended (so the lamps are the stand-down gate's business, not
        this one's). Under staging
        1 that is one complete lap of the covering watcher with nobody seeing anything
        (its reach is 1.43x short of the spot from every phase of its round); under
        staging 2 the different covering watcher holds the runner for a real window. The
        gate additionally asserts, at the end of the run, that the two holds produced
        OPPOSITE answers at the identical spot -- a shared sight radius, one hard-coded
        cone, or one watcher's numbers used for all three cannot report both. The
        message names both watchers, each one's own reach and view width as staged at
        that instant, the offset held, and what was shown.

assert: CaughtIsFinalEvenAtTheGate -- after a round has been lost, at every later judged
        frame of that round -- including 6 s of standing in the open with nobody able to
        see the runner, and two separate walks into the gate volume -- the caught light
        burns and the away light is dark. Fires in rounds 1 and 3. The message names the
        round number, the plate's current count, when the round was lost, and which
        lights were burning.

assert: AwayIsFinalEvenInPlainSight -- after a round has been won, at every later judged
        frame of that round -- including 6 s standing squarely inside the covering
        watcher's live reach and view width -- the away light burns and the caught light
        is dark. Fires in rounds 2 and 4. The message names the round, the watcher whose
        cone the runner is standing in, its own two numbers, and which lights were
        burning.

assert: EveryRoundStartsCleanWhenThePlateClicks -- on every judged frame from 0.4 s
        after the plate's number changes until that round ends: the running light burns,
        both terminal lights are dark, and every watcher is walking its round again at
        its OWN base pace within 1%. Fires four times. This is the gate a one-shot latch
        dies on -- a latch armed once for the session never re-arms, so round 2 opens
        still showing round 1's ending -- and it is the gate a base pace cached at
        BeginPlay dies on, because the sergeant multiplies one of them by 1.25 before
        round 3. The message names the plate's old and new number and what the mast and
        each watcher's pace showed.

assert: EachWatcherShowsWhatItCanSeeRightNow -- INDEPENDENT CHANNEL, on every judged
        frame while a round is running, always evaluated LAST: the set of burning
        watcher head lamps equals EXACTLY the set of watchers the model says can see the
        runner, computed live from each watcher's own reach, own view width, own live
        transform, and the live footprints of the crates, the wall and the truck. Read
        from each lamp's light (visible, not hidden, intensity > 0), never from a flag.

        BE HONEST ABOUT WHAT THIS SET IS. Seeing the runner is what ENDS a round, so on
        every frame this gate can possibly run the model's set is EMPTY, and the gate
        reduces to "no lamp burns that should not". That is not a weak assertion here --
        it is exactly what a range-only or an occlusion-blind sight test fails, on the
        first judged frame (the walled sentry) and continuously through the whole truck
        window (the covering watcher, whose lamp must stay dark for the seconds the truck
        is across the line while the runner stands squarely inside its reach and view
        width). The LIT half of the channel is not asserted here; it is asserted by name
        in the stand-down gate below, and an implementation that never lights any head
        lamp fails THERE rather than banking the control for free.

        The in-scene negative control spans both gates: the walled sentry patrols behind
        the solid wall with the largest reach and widest view width in the yard, so it is
        never in the model's set and never in the latched set, and its lamp is
        additionally gauged at EVERY checkpoint whatever the suppression. The message
        names the expected set, the found set, and each watcher's own two numbers.

assert: TheYardStandsDownWhenTheRoundIsOver -- INDEPENDENT CHANNEL, on every judged
        frame between a round ending and the next plate click, always evaluated LAST,
        and the ONLY place in the run where a burning head lamp is REQUIRED. Two halves:

        (a) every watcher's PaceUuPerSec reads zero -- no exceptions, including watchers
            the model says could still see the runner from where they stopped;
        (b) the set of burning head lamps equals EXACTLY the set of watchers that could
            see the runner AT THE INSTANT THE ROUND ENDED, which is empty for a round
            that ended at the gate.

        (b) is the gate a re-derivation cannot pass. Within a second or two of a catch
        the watchers are frozen and the runner has walked to the open spot and then into
        the gateway, so "who can see the runner" answers {} while "who saw the runner"
        still answers {that watcher} -- and it is the second question the yard is
        showing. The message names the round, how it ended, the set that ended it, the
        set actually burning, and, separately, the set the model says COULD see the
        runner right now, so a re-derivation is diagnosed rather than merely failed.

        Between them these two halves are what fails when perception is right and the
        feedback is wrong: lamps driven straight off the instantaneous sight test fail
        (b) at phases 9 and 17, where the runner stands squarely inside a frozen
        watcher's live reach and view width in a round that ended AT THE GATE and every
        lamp must be dark; lamps simply switched off at stand-down fail (b) in rounds 1
        and 3; and watchers never stopped fail (a) on the first judged frame after any
        ending.

assert: BothEndingsHappenedTwice -- run-level, evaluated at drive completion and again
        at the sentinel: across the four rounds the yard ended caught at least twice and
        away at least twice, in the staged order, and no round ever showed two endings
        or changed its ending after the first. A yard that can only ever end one way, or
        only once per session, never reaches this.
```

**Staging faults are attributed, not scored.** Any breach of the staging contract above,
plus wrong actor counts, a watcher/mast/plate/gate/truck that does not expose its numbers
readably, or a phase that overruns its derived deadline, ends the run as
`HARNESS-PRECONDITION`, never as a model failure.

**A harness exit can never launder a FAIL.** The stand-down rule means a submission that
never stops the watchers changes where they are when the next round opens, which can make
a later phase's derived deadline unreachable. Before any deadline or sentinel overrun is
written off as a staging fault, `TheYardIsNotYoursToRewire` and
`TheYardStandsDownWhenTheRoundIsOver` are re-checked **unconditionally**.

## Requirement-to-assertion map

Every row names the gate that checks the requirement and the condition under which that
gate is skipped. **A requirement that no gate can distinguish says so in the third
column and is not counted as graded** — an inflated requirement count is the same defect
as an undisclosed gate, one direction over.

| Prompt requirement | Gate that checks it | When that gate does NOT run |
| --- | --- | --- |
| exactly one of the three mast lights burns at any moment | `ExactlyOneLampBurnsOnTheBoard` | inside the quarter-second settle window after any model change, and for the run's first 0.4 s — the same grace every other gate gets |
| waiting, before the first plate click, reads running | `ExactlyOneLampBurnsOnTheBoard` plus phase 0 of `EveryRoundStartsCleanWhenThePlateClicks` | as above |
| a watcher sees inside **its own** reach and **its own** view width | `EachWatcherSeesWithItsOwnEyes` at the split spot, both stagings; `EachWatcherShowsWhatItCanSeeRightNow` every running frame; `TheYardStandsDownWhenTheRoundIsOver` names WHICH watcher ended each caught round | suppressed only by the settle and marginality rules |
| the numbers belong to the watcher, and the three are not alike | not a gate but a **precondition**: the fixture refuses to start unless the split spot is out of one covering watcher's reach from every phase of its round and inside a real window for the other. The prompt no longer says the three differ — it says the numbers are set on the watcher, and the yard proves the difference matters | never |
| inclusive at both edges of reach and view width | the model uses exactly that predicate | **NOT INDEPENDENTLY GRADED.** Both edges sit inside the marginality suppression (3 deg / 6% of reach), which declines to judge exactly there; disclosed so an exclusive-edge reading is not a surprise, not because a frame can tell the two apart |
| measure flat / height plays no part | the staging contract's four-height probe makes every trace height agree with the model | **NOT INDEPENDENTLY GRADED, and deliberately so.** The watchers stand ~95 uu up and the runner's capsule centre ~88 uu on a level floor, so over 2,000-3,700 uu of reach a 3-D distance differs from a flat one by ~0.01 uu and an un-flattened direction by ~0.2 deg — inside the suppression band either way. This clause exists to stop a correct submission DIVERGING from the model, which is the opposite job from discriminating |
| only the crates, the wall and the truck are solid | `TheTruckMakesAShadowWhileItPasses` (the moving half) and `EachWatcherShowsWhatItCanSeeRightNow` (the static half, continuously — the sentry behind the wall) | suppressed only by the settle and marginality rules |
| what a watcher can see is settled by where everything is at this instant | `SeenTheMomentTheyCross` (a 2.67 s mid-leg crossing with 4.12 s of clearance to both turns) and `TheTruckMakesAShadowWhileItPasses` (the board on both sides of the truck letting go of the line) | outside their staged windows, where the lamp gate checks the same fact less sharply |
| a watcher's lamp burns while it can see the runner | `EachWatcherShowsWhatItCanSeeRightNow`, every running judged frame — in practice the "must be dark" half, because seeing the runner ends the round | while a round is over, where the stand-down gate owns the lamps |
| the lamps of whoever saw the runner keep burning until the next round | `TheYardStandsDownWhenTheRoundIsOver`, set equality against the set latched at the ending instant, on every judged over-frame of rounds 1 and 3 | while a round is running |
| a round that ended at the gate leaves every lamp dark | `TheYardStandsDownWhenTheRoundIsOver`, rounds 2 and 4 — including 6 s standing squarely inside a frozen watcher's live reach and view width | as above |
| the first ending wins and nothing later changes it | `CaughtIsFinalEvenAtTheGate` (two walks into the gateway per caught round) and `AwayIsFinalEvenInPlainSight` | outside those windows, where nothing later has yet been attempted |
| a fresh plate number re-arms everything | `EveryRoundStartsCleanWhenThePlateClicks`, four times | inside a narrower board gate's window |
| the watchers stand still while a round is over | `TheYardStandsDownWhenTheRoundIsOver` (a), every judged over-frame | while a round is running |
| a fresh round restores **each** watcher's OWN base pace | `EveryRoundStartsCleanWhenThePlateClicks`, within 1% | as above |
| it settles within a quarter of a second | the 0.4 s suppression window, which is 1.6x it, and the 0.4 s deadlines in gates 3 and 4 | never |
| the night is long — round after round, both endings | `BothEndingsHappenedTwice` | judged at drive completion or the sentinel; a run that fails a per-frame gate earlier never reaches it, which is the more useful message |
| the numbers change and must be read at the point of use | `EveryRoundStartsCleanWhenThePlateClicks` (base pace x1.25 on round 3) and `EachWatcherSeesWithItsOwnEyes` (reach x1.2, view width x0.6) | as above |
| do not move anything or change any number on it, except the pace | `TheYardIsNotYoursToRewire`, every frame, unsuppressed, including "on its own round" | never |
| C++ under `Source/ThirdPerson/` | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

**One requirement was REMOVED from the prompt rather than given a gate.** "Caught wins a
simultaneous tie" is unreachable in this yard: staging precondition 9 refuses to start
unless the gate volume is at least 1.25x outside every watcher's largest post-re-stage
reach, so no frame can have a watcher seeing the runner and the runner standing in the
gate at once. An implementation resolving the tie either way is byte-identical over the
whole drive. It used to be in the prompt and this table used to claim `phase 3` graded
it; both were false, and a disclosed rule the staging makes impossible is one fewer thing
the model must get right, dressed up as one more.

## Reference solution metadata

- **Files touched**: 2 —
  `Source/ThirdPerson/Tasks/t3-reach-the-exit-before-they-see-you/StealthMastActor.h`
  and `.cpp`. The other six supplied pairs are untouched, so `reference/` ships only
  that one pair — a reference that also carried byte-identical copies of the scaffold is
  the exact shape of the "reference inside the substrate" hazard.
- **LOC**: ~215 added (about 75 of them comment), on top of the supplied three switches.
- **Senior-dev hours**: **8-12**, the lower half of T3. The code is not large; the hours
  go into judgment, not typing:
  1. ~1.5 h working out that the outcome is an **exclusive terminal latch** re-armed by
     an external counter, not a function of the current triggers — and that both the
     "later gate touch overwrites the loss" and the "one-shot latch" bugs are one line
     each and both compile and read correctly.
  2. ~2 h on the sight predicate: per-instance numbers read at the point of use, flat
     measurement, inclusive edges, and a clear-line test that must be re-asked every
     frame because one of the occluders is driving past. Deciding *what to ignore* on
     that line (the runner, the watchers) is a real decision the prompt settles and a
     first pass usually gets wrong in one direction or the other.
  3. ~2 h on the reverse edge: the outcome writing back into the watchers' pace and
     lamps, and getting it right in three directions — every watcher still while the
     round is over, each watcher's own base pace while it runs, and the lamps of
     whoever ended the round left burning. The last of those is the one that cannot be
     recovered by asking the world again: by the time the gate looks, the watchers are
     frozen and the runner has walked out of the cone, so the set has to have been TAKEN
     on the frame the round ended. A first pass that re-derives it at stand-down time
     compiles, reads correctly, and is dark exactly when it should be burning.
  4. ~2 h on the reading discipline: nothing cached, because the sergeant re-stages three
     numbers and swaps two round tags with nothing to hear it.
  5. ~2 h on the order of the five steps inside one tick, which the prompt settles
     ("what a watcher can see is settled by where everything is at that instant") and
     which the re-arm makes subtle: the plate is read first, or the round that just
     started is graded with the previous round's ending still latched.
- **Why not T2**: three subsystems in a two-way loop, a moving occluder, a re-armable
  terminal state and a mid-run re-stage. Any one of them alone is a T1/T2 task; the
  interaction is the work, and eleven gates exist because eleven independent things can
  be wrong.

## Anti-gaming notes

1. **Evaluating sight only when a watcher reaches a patrol post — or on a
   one-to-two-second re-scan timer.** *Failure mode*: THE primary wrong answer, and the
   one a competent engineer actually writes when detection is hung off the patrol state
   machine rather than off the frame, or when the line test looks expensive enough to
   throttle. It compiles, it reads correctly, and it passes every surface check: a runner
   who STANDS in a cone is still standing there at the next sample, so caught fires; the
   walled sentry never lights; the lamps look right most of the time; the latch, the
   re-arm and the stand-down are all perfectly implemented. *Defense*: TWO independent
   deaths, both named. `SeenTheMomentTheyCross` times phase 12's crossing so the runner
   enters and leaves the covering watcher's live cone entirely between two of its turns
   — a window at least 1.0 s long with at least 2.0 s of clearance at both ends, far
   outside the quarter second the prompt allows — so the poller never samples inside it.
   `TheTruckMakesAShadowWhileItPasses` does the same with the truck clearing the line in
   phase 3, at least 2.0 s from the nearest turn. A poller that survives one dies at the
   other.
2. **One shared sight radius, or the first watcher's numbers applied to all three.**
   *Failure mode*: the obvious refactor once the three watchers look interchangeable.
   *Defense*: the split spot is held in both stagings with a different watcher covering
   it — 1.43x out of reach under staging 1, comfortably inside under staging 2 after the
   sergeant multiplies that watcher's reach by 1.2. `EachWatcherSeesWithItsOwnEyes` names
   both watchers' own numbers and asserts at the end of the run that the two holds gave
   opposite answers at the identical spot. No single radius survives both.
3. **`if (AtGate) Outcome = Away;` written after the sight test.** *Failure mode*: an
   ordinary ordering slip — a later gate touch overwrites a latched loss. *Defense*:
   `CaughtIsFinalEvenAtTheGate` walks the runner into the gate volume twice after each
   caught round and requires the caught light to still burn and the away light to still
   be dark.
4. **Latching the outcome once for the whole session and never re-arming.** *Failure
   mode*: the single most common wrong implementation in this corpus family — a latch
   that satisfies every first-pass check. *Defense*:
   `EveryRoundStartsCleanWhenThePlateClicks` fires four times and requires the running
   light and only the running light from 0.4 s after every plate click;
   `BothEndingsHappenedTwice` requires both endings twice across the session.
5. **A range-only sight test, or a cone test that never asks what is in the way.**
   *Failure mode*: the two ordinary first passes at perception. *Defense*: the in-scene
   negative control. The walled sentry has the largest reach and the widest view width in
   the yard and its round is behind a solid wall that crosses every line from it to every
   point of the route; `EachWatcherShowsWhatItCanSeeRightNow` gauges its lamp at **every**
   judged frame, so range-only lights it on the first one and occlusion-blind lights it
   whenever it faces south.
6. **A blocker set gathered once at BeginPlay, or a baked visibility map.** *Failure
   mode*: a sensible-looking optimisation, since the crates and the wall genuinely never
   move. *Defense*: the truck does, all night.
   `TheTruckMakesAShadowWhileItPasses` requires the lamp dark and the board running for
   the whole 2.3 s the truck's LIVE footprint lies across the line, and the board to read
   caught within 0.4 s of it letting go. A cached blocker set has the watcher seeing
   through the truck, so it ends round 1 caught while the model still says running — it
   fails on the board, several seconds before the window it was meant to survive. The
   truck is in the model's visible-set computation on EVERY judged frame of the run as
   well, so the same submission is wrong wherever else the truck happens to matter, not
   only inside the staged window.
7. **Driving the head lamps straight off the instantaneous sight test.** *Failure mode*:
   the natural reading of "a lamp burns while that watcher can see the runner", with the
   stand-down clause missed. Perception can be perfect and this still wrong.
   *Defense*: `TheYardStandsDownWhenTheRoundIsOver` gauges every over-frame — including
   phases 9 and 17, where the runner deliberately stands squarely inside a frozen
   watcher's live reach and view width in a round that ended AT THE GATE, so every lamp
   must be dark — and requires zero pace throughout.

7a. **RE-DERIVING the stand-down lamps instead of remembering them.** *Failure mode*: the
   third of the three named wrong answers, and the subtlest. The rule is disclosed in
   full — the lamps of every watcher that could see the runner *at the instant the round
   ended* go on burning — and an implementation that simply re-runs its own sight test
   every frame of the stand-down satisfies it perfectly for the first second, while the
   runner is still standing where it was caught. It compiles, it reads correctly, it
   passes every surface check, and it is *the same code path* as the running-round lamp
   rule, which is exactly why it is the natural thing to write. *Defense*: the drive
   walks the runner away. Phase 4 crosses to a lane place nobody can see and stands there
   6 s; phase 5 walks into the gateway, back 900 uu and in again. Over all of it
   `TheYardStandsDownWhenTheRoundIsOver` demands set equality against the LATCHED set, so
   a re-derivation reads `{}` where the yard owes `{the watcher that caught you}` and
   fails by name, with the message printing both sets side by side so the diagnosis is in
   the failure. Fires in rounds 1 and 3.
8. **Setting a correct internal outcome enum and never touching a light.** *Failure
   mode*: modelling the state and forgetting the output. *Defense*: nothing private is
   ever graded — the fixture reads the mast's three light intensities, each head lamp's
   intensity and each watcher's `PaceUuPerSec`. The mast deliberately carries no outcome
   property of its own.
9. **Reading the watchers' numbers or round tags once at `BeginPlay` and caching them.**
   *Failure mode*: the obvious optimisation. *Defense*: the sergeant swaps two round tags
   and re-sets three numbers between rounds 2 and 3. A cached base pace fails
   `EveryRoundStartsCleanWhenThePlateClicks` on round 3; a cached reach or round tag
   fails `EachWatcherSeesWithItsOwnEyes` at the split spot.
10. **Moving a watcher, or parking one on the runner.** *Failure mode*: forcing a
    permanent sighting, or removing an inconvenient one. *Defense*: this is anti-gaming
    rather than a plausible first pass, and it is why `TheYardIsNotYoursToRewire` checks
    that each watcher is within 60 uu of the segment between its own two posts. Relying
    on the sight gate instead would not work: the model reads the watchers' LIVE
    transforms and would agree with the parked watcher.
11. **Writing `BasePaceUuPerSec` instead of `PaceUuPerSec`.** *Failure mode*: two
    similarly named floats on the same actor; an ordinary slip. *Defense*:
    `TheYardIsNotYoursToRewire` compares every staged number every frame and its message
    names the property that IS yours to write.

## Hidden invariants

- **The outcome is never compared directly; only its consequences are.** The fixture's
  model state is never read out of the submission (it could not be), so every gate is a
  statement about lights and paces. A submission is free to represent the outcome however
  it likes.
- **The model's clear-line test is a 2-D segment-versus-rectangle test against live
  footprints, not a trace.** The fixture and a tracing submission are therefore two
  independent implementations of one disclosed rule, and the staging contract's
  three-height probe is what guarantees they cannot disagree. If that probe is ever
  dropped, this gate becomes a coin toss on trace height.
- **The lamp channel is split across two gates on purpose, and the split is where an
  earlier build of this task was WRONG.** Seeing the runner is what ends a round, so
  "the burning lamps equal the watchers that can see the runner" can only ever be
  evaluated with that set EMPTY — which made the whole per-watcher lamp requirement free,
  and made an implementation that never lit a head lamp indistinguishable from a correct
  one. The reference itself never showed a lit lamp for a single observable frame. The
  fix was not to weaken the gate but to give the yard a state in which a lit lamp is
  observable and required: from a caught ending until the next plate click, the lamps of
  whoever saw the runner go on burning, and `TheYardStandsDownWhenTheRoundIsOver` demands
  that exact set. An empty delivery now fails it, the walled sentry's dark lamp now costs
  something, and a human playing the level can see who caught them.
- **`fps_legs: [60, 20]` runs the whole drive twice**, in two PIE processes. Every window
  is opened and closed on world game-time and on live geometry, so the two legs stage
  identically; a re-scan fitted to a tick count fires at the wrong wall time at 20 Hz and
  misses a differently-sized set of windows, so the two legs also fail *differently* for
  a frame-coupled submission, which is itself diagnostic.
- **The re-stage happens while the yard is stood down**, so no swap can jolt an outcome,
  and every gate is suppressed for 2 s either side. A submission that fails to stand the
  watchers down is therefore re-staged while its watchers are still walking — which
  `TheYardIsNotYoursToRewire` and `TheYardStandsDownWhenTheRoundIsOver` both catch before
  any deadline overrun can be blamed on staging.

- **The model asks the GATE whether somebody is standing in it, rather than deciding for
  itself.** The prompt discloses one reader and the model uses that reader. This is a
  hidden invariant rather than a detail because it is the difference between grading the
  disclosed rule and grading a second, stricter rule nobody was told about: a point test
  on the runner's origin against the volume's own half-extent fires roughly 40 uu of
  travel later than the overlap does, which at the character's shipping speed is about
  five frames of the reference reading "away" while the fixture's model still reads
  "running" — long enough to FAIL the reference on `EveryRoundStartsCleanWhenThePlateClicks`
  at both framerate legs.

- **The drive's shadow entry waits for a phase alignment it can prove, and the fixture's
  own solver refuses a window too tight for that wait to end.** The covering watcher's
  cone and the truck's rail are independent periodic things; walking in at an arbitrary
  moment ends round 1 on the spot roughly half the time, which would make this task's
  headline window a coin toss. The shadow-spot solver therefore demands 1.5x the cover
  the GATE asks for, so that a departure moment exists at all. If that floor is ever
  lowered to the gate's own floor, phase 2 stops committing and every run reports a
  staging fault instead of a grade.
