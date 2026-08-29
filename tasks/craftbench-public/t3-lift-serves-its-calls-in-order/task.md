---
id: t3-lift-serves-its-calls-in-order
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_LiftTower :: ALiftTowerFunctionalTest"]
---

# t3-lift-serves-its-calls-in-order

A three-landing lift. It must latch every call whatever it happens to be doing,
serve the latched set **the way a lift does** — keep going, stop at everything on
the way, turn round only when there is nothing left ahead — stop level with
landings whose heights are staged at run time and **change part way through**,
carry the character standing in it, hold its doors, and keep all three landing
signs showing the floor it is nearest and the way it is about to go.

> **Built against the 2026-08-18 difficulty bar.** Four subsystems that constrain
> each other: the scheduler, the door interlock, constant-speed motion against a
> floor height that moves, and a three-sign indicator driven by the scheduler's
> committed next stop. Touch the scheduler's direction bookkeeping and the signs
> break; change the door timing and whether a mid-close press is even seen
> changes with it. **Nothing is hidden** — every number a gate compares against is
> either in the prompt in plain words or readable off the car at run time. It is
> hard because it is a lot of careful, mutually-constraining work with several
> ordinary-looking ways to get it subtly wrong.

## Primary concept

- `movement-components` — driving an actor's transform per frame and having the
  engine carry whatever is standing on it
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/movement-components-in-unreal-engine)

The load-bearing behaviour is **a machine that answers for a set of outstanding
requests in an order that depends on where it currently is and which way it is
already going**, while physically moving a surface a character is standing on.
The grade never asks *how*: a state machine, a queue of structs, a component, or
a plain `switch` in `Tick` all pass identically.

### Composed concepts

| Concept | Why it is load-bearing here |
|---|---|
| `collision-overview` (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine---overview) | Six unbound trigger volumes are the only way a call ever enters the system, and the rider is carried because the car floor is a **movable blocking** primitive. |
| `actor-lifecycle` (https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-actor-lifecycle) | The shaft is assembled **before any `BeginPlay`**, and one landing moves again mid-run. Anything read once at play is wrong by the second half. |
| `setting-up-character-movement` (https://dev.epicgames.com/documentation/en-us/unreal-engine/movement-components-in-unreal-engine) | The rider has to arrive at the far landing, which is a property of how the platform is moved, not of how it is drawn. |

Compositional, but the pattern it composes is not invented: it is **collective
control**, the standard single-car lift dispatch every real lift uses (continue
in the committed direction, serve every call on the way, reverse only when
nothing is left ahead).

## Prompt given to the agent

> The tower has three landings, one above the other, and a lift that serves them.
> Everything in it can be told what to do, and nothing tells it anything.
>
> **What is already built and working.** The car has a floor you can stand on, a
> pair of doors, and three pads inside it, one for each landing. Each landing has
> a deck you walk on, a call pad you step on to send for the lift, and a sign.
> Every pad has a light that comes on and goes off when you say so. The doors open
> and shut when you say so, taking the time they take. Each sign prints a floor
> number and points an arrow when you say so; they all start blank. The car
> carries three numbers written on it that you can read off it at any time: how
> fast it travels, how long its doors take to open or shut, and how long they hold
> open once open. Those three numbers are the car's, not yours — read them, do not
> rewrite them. Everything in this paragraph is already there and working: leave
> it there. Nothing calls any of it. Deciding when to is the whole job.
>
> **Where the floors are is not something you may assume.** The three landings are
> not evenly spaced, and their heights are not the ones you will find sitting in
> the level — the shaft is put together freshly before the lift ever runs. Worse:
> the middle landing is moved to a completely different height part way through,
> while nobody is standing on it. Ask a landing where its floor is at the moment
> you need to know. Do not remember it, and do not work it out from a pattern.
>
> **What the lift must do.**
>
> Stepping on a pad — on a landing or inside the car — is a call for that floor. A
> call is never forgotten. It makes no difference what the lift is doing at the
> moment somebody steps on the pad: standing still, travelling between floors, or
> halfway through shutting its doors. **That pad's** light comes on when it is
> pressed and stays on until the lift has opened its doors at that floor, and then
> goes out.
>
> If somebody calls the floor the lift is already standing at while its doors are
> shut, it opens them again.
>
> Serve the calls the way a lift does, not in the order the buttons were pressed.
> Keep going the way you are already going, stopping at every called floor you
> pass on the way, and only turn round when there is nothing left ahead of you.
> Stop only where you have been called.
>
> Arrive level. When the doors open, the car's floor must be within **five
> centimetres** of that landing's floor, so that somebody can walk straight out.
>
> Travel at the speed written on the car — the same speed whichever way it is
> going and however far it has to go. **No easing and no acceleration ramp: it is
> at that speed the whole way.** Over any one trip between two stops, the distance
> it covers divided by the time it spends moving must come out within **a fifth**
> of that number.
>
> The car must really travel, and it must carry whoever is standing in it the
> whole way. Somebody who steps in at one landing steps out at another.
>
> Never move the car unless the doors are completely shut. On arrival the doors
> open all the way and stay all the way open for at least the hold time written on
> the car, and then they begin to shut.
>
> A stop is a stop. From the moment the doors are all the way open the car stands
> still, level with that landing — inside the same **five centimetres** it arrived
> at — for at least that hold time, so that somebody can walk across the sill and
> out. It does not begin to sink or climb toward its next call while its doors are
> open.
>
> Every landing's sign — all three of them, not only the one the lift happens to
> be at — shows the number of the landing the car is nearest to, and an arrow for
> the way the lift is going to go next. **Next, not now**: while the lift is
> standing at a floor with somewhere still to go, the arrow already points the way
> it is about to leave. When there is nothing left to serve, no arrow. A sign is
> read as a number — the first whole number it prints — and it has **half a
> second** to catch up after the thing it is showing changes. You will not be
> judged on which of two landings a sign names while the car is close enough to
> halfway between them that either answer would be reasonable.
>
> **Ground rules.** Where the landings are, where the car starts, and what is
> bolted to them is not yours to change: do not move a landing, and do not move
> the car other than by driving it up and down its shaft. Do not edit the level,
> any config file, or any test file. Write your solution in C++ under
> `Source/ThirdPerson/`.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on
this substrate). `Source/CraftBenchTests/` is deny-listed and a submission file
under it is a SANDBOX-REJECT (exit 4), not a graded FAIL; so are
`Content/Maps/`, `Content/ThirdPerson/`, `Content/Characters/` and every
`Config/` file (no `config_allow` is declared by this task).

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t3-lift-serves-its-calls-in-order/LiftCarActor.h` / `.cpp` —
  `class THIRDPERSON_API ALiftCarActor : public AActor`, tagged `LiftCar`.
  Supplied and working:

  | Piece | What it is |
  |---|---|
  | `Platform` | **the root**, a 700 x 700 x 20 floor, `Movable`, `BlockAll`. Being the root is what makes a character standing on it get carried when the actor moves. |
  | `Cage` / `WallBack` / `WallLeft` / `WallRight` | the shell. **NoCollision on purpose** — only `Platform` blocks, so nothing about the car can trap or jam the character. |
  | `DoorLeftLeaf` / `DoorRightLeaf` | the two leaves, sliding apart along the car's Y. NoCollision: a closing door can never shut on anybody. |
  | `Pad1` / `Pad2` / `Pad3` (`UBoxComponent`) | the three in-car floor buttons, 120 x 120, standing 190 uu off the middle of the floor on three different sides, overlap events **on**, **nothing bound to them**. |
  | `PadLamp1..3` (`UPointLightComponent`) | the lamps over them, off at intensity 0. |
  | `NumbersReadout` | the three numbers below, painted on the back wall at play. |
  | `OpenDoors()` / `CloseDoors()` | the supplied commands. |
  | `GetDoorOpenFraction()` | 0 shut .. 1 fully open, **measured from where the two leaves actually are** — not a flag. Exactly `0.0f` and exactly `1.0f` at the two ends: **the accessor snaps them**, so `>= 1.0f` and `<= 0.0f` are safe tests and are the intended ones. (It snaps there rather than relying on the leaves landing perfectly because the engine is entitled to drop the last sliver of the door's travel — see *Hidden invariants*.) |
  | `AreDoorsCommandedOpen()` | what the doors were last *told*, as distinct from where they are. |
  | `SetPadLit(int32, bool)` / `IsPadLit(int32) const` / `GetPad(int32)` | the lamps and the volumes, by floor number. |
  | `GetSillHeight()` | world Z of the **top of `Platform`** — the surface a rider stands on. |
  | `TravelSpeedUuPerSecond` / `DoorTravelSeconds` / `DoorHoldSeconds` | `UPROPERTY(EditAnywhere)`, readable at run time. The map ships 200 uu/s, 2.0 s, 3.0 s. |
  | `DoorShutSeparationUu` / `DoorOpenSeparationUu` | the leaf separations the open fraction is measured between. |
  | `AdvanceDoors()`, called from `Tick()` | **the supplied door mechanism.** It slides the leaves and it is driven from `Tick`. If you rewrite `Tick`, keep that call — without it the leaves never move and nothing else you write can be seen. |

  **No scheduling, no call memory, no motion, no overlap bindings, no sign
  writes.** The whole decision is the agent's, **and it has to land on this class
  and on `ALiftLandingActor`**: the car and the three landings are placed
  instances in a map that cannot be edited, so a newly-placed actor class would
  never be instantiated. Additional C++ under `Source/ThirdPerson/` is fine as
  long as something on these two classes calls into it.

- `Tasks/t3-lift-serves-its-calls-in-order/LiftLandingActor.h` / `.cpp` —
  `class THIRDPERSON_API ALiftLandingActor : public AActor`, tagged `LiftLanding`,
  **three placed instances**. Supplied: `Deck` (**the root**, 700 x 800 x 20,
  `Movable`, `BlockAll`), three blocking parapets on the sides away from the
  shaft, `CallPad` (`UBoxComponent`, overlap events on, **unbound**), `CallLamp`,
  `SetCallLit(bool)` / `IsCallLit()`, `FloorNumber` (`UPROPERTY(EditAnywhere)`,
  1..3, **set per instance in the level**), `GetSillHeight()` (world Z of the top
  of `Deck`), and the sign: `Readout` (a `UTextRenderComponent`, starts blank) +
  `Arrow` (a cone, starts hidden) driven by
  `Show(int32 FloorNumber, int32 Direction)` — which prints the number (0 or less
  blanks it) and points the arrow up (`+1`) / down (`-1`) / hides it (`0`).
  **Ships no logic.**

- `Content/Maps/t3-lift-serves-its-calls-in-order/L_LiftTower.umap` — the tower,
  committed binary. World Settings name **NO** game mode, so the level inherits
  `BP_ThirdPersonGameMode` and both halves of Enhanced Input survive. What is in
  it:

  | Element | Placement | Notes |
  |---|---|---|
  | Three `ALiftLandingActor`s | one shaft, one above the other, `FloorNumber` 1/2/3 | decks `Movable` — the verifier stages the shaft |
  | One `ALiftCarActor` | parked level with landing 1, in a clear vertical shaft | the car never passes through a deck |
  | Sill gap | 15 uu between the car floor and each deck | crossable by a 42 uu capsule, too narrow to fall down |
  | PlayerStart | on landing 1, off its call pad | |
  | Tower face (**blocking**) and a **roof** over the whole tower footprint, its underside 400 uu above the top sill | closes the back and the top | a jump apex is 127.6 uu and a landing parapet is 120, so without them a rider on the top landing can hop the rail and fall 18 m. Added after the owner's 2026-08-19 play-test |
  | Shaft wall + a 300 uu tick ruler, two landmark pylons, sun/sky/atmosphere | | a moving camera reads as moving; a still is not black. The shaft wall stays **NoCollision on purpose** — it runs alongside the moving car, and a blocking wall beside a moving platform is a way to jam the rider |
  | Fixture | one placed `ALiftTowerFunctionalTest` | |

  **The landing heights are deliberately NOT in this section, and the one
  committed in the level for the middle landing is a decoy** — see the prompt.

- `cameras.json` (the camera-plan lane; not part of this release) — the
  presentation-only camera plan. Non-gating.

Files that **do not exist**:

- No scheduler, no call set, no door state machine, no motion, no sign logic, no
  Blueprint subclass, no level edits. The empty submission compiles (L1 green) and
  FAILs L2 about two seconds after the character first steps on a call pad.
- No test source in the agent's writable path. `ALiftTowerFunctionalTest` lives in
  the `CraftBenchTests` module the agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t3-lift-serves-its-calls-in-order/L_LiftTower.umap` on the
**ThirdPerson** substrate, ticked at a fixed deterministic step
(`-deterministic -FPS=60`). Verification primitive: **pie-checkpoint-sampling**
with an every-frame readback of the car sill, the measured door fraction, the six
pad lamps and the three signs, over a fixture-driven two-leg walk.

**The shaft is staged, not read.** In `FWorldDelegates::OnWorldInitializedActors`
— after `PostInitializeComponents`, **before any `BeginPlay`** — the fixture moves
landing 2 to 69.44% of the shaft (≈ +1250 uu above landing 1 in the shipped
tower). Between the two legs, with the car parked at landing 3 and nobody on
landing 2, it moves it to 25% (≈ +450). Because the first staging lands before
`BeginPlay`, a submission that reads the sills at play reads the **staged**
values: the heights are honest, and only *caching* them is punished — by a move
the prompt discloses.

**Presses are the fixture's own observation.** It watches the character's capsule
enter each pad volume and never consults the submission's bookkeeping. The test
is the **capsule**, not the capsule's centre, so the fixture learns about a press
no later than an overlap-bound submission does — a fixture that learned later
would fail a correct lift for lighting its sign "too early".

**Arrival is the press.** A waypoint that is a pad is reached when the capsule
centre is inside that pad's own footprint shrunk by 15 uu, which is the same
geometry that records the press. A distance-only arrival radius could be
satisfied from off the pad.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

Continuous gates, every frame:

```text
assert: TheSuppliedMachineryIsStillThere -- the platform, both leaves, the three
        pads and their lamps, and each landing's deck, call pad, lamp, readout
        and arrow all still exist, and no pad footprint is under 110 x 110 uu
assert: TheNumbersOnTheCarAreNotYoursToRewrite -- the five numbers pinned before
        BeginPlay, and each landing's FloorNumber, still read the same
assert: TheLandingsAndTheCarStayedWhereTheyWerePut -- each landing is within
        2 uu of the transform the tower staged for the leg in progress; the car
        is within 2 uu of the shaft in X and Y and inside the shaft in Z
assert: TheCarNeverMovesWithItsDoorsOpen -- if the car sill moved more than
        1 uu since the previous frame, GetDoorOpenFraction() read 0 on BOTH
        frames (3.3 uu is one frame of real travel at the stated speed)
assert: TheCarStopsLevelWithTheLandingItServes -- on the frame the door fraction
        first reaches 1.0, |car sill - nearest landing sill| <= 5 uu. Both sides
        come from the top of a primitive's world bounds, so the submission's
        notion of "level" and the fixture's cannot diverge
assert: TheCarTravelsAtTheSpeedWrittenOnIt -- per trip, from the last frame
        before the sill changed to the last frame it changed: total path length
        divided by elapsed moving time is within +/-20% of the car's own
        TravelSpeedUuPerSecond. Dwell at either end is excluded; a trip shorter
        than 40 uu is treated as a correction and ignored
assert: TheCarActuallyTravelsAndTakesItsRiderWithIt --
        (i) PROGRESS: with the doors reading 0 and an outstanding recorded press
            for a floor more than 20 uu from the car sill, the sill must change
            by 30 uu within 3 s;
        (ii) RIDER: on every frame the sill moves by more than 1 uu, the
            character must be over the car floor's footprint (+30 uu) with his
            feet within 60 uu of the sill
assert: TheDoorsHoldOpenLongEnoughToGetOut -- per stop, the fraction reaches
        1.0, and the interval from the first frame at 1.0 to the first frame
        below it is at least the car's own DoorHoldSeconds minus 0.15 s
assert: TheCarStandsStillLongEnoughToStepOut -- per stop, the interval from the
        frame the fraction first reaches 1.0 at a landing to the first frame the
        car sill is more than 5 uu from THAT landing's sill is at least the car's
        own DoorHoldSeconds minus 0.15 s. This measures the CAR, where the gate
        above measures the DOOR: a lift that eases toward its next call while the
        door animation finishes stays under TheCarNeverMovesWithItsDoorsOpen's
        1 uu-per-frame allowance and can still drift ~180 uu out of the landing
        during a 3 s hold. Judged only when the car actually leaves the landing;
        a car still standing there when the run ends has rushed nobody and is
        not judged
assert: TheLiftServesWhatIsOnTheWayBeforeItTurnsAround -- checked as a PREFIX,
        live: the ordered floors at which the doors reached fully open must be a
        prefix of the collective answer [1,2,3,3,2,1,3], and at the end must
        equal it. Checking it live (rather than at the end) is what keeps a
        press-order lift failing HERE instead of dying at a waiting deadline
assert: NoCallIsEverDropped -- clause B, live: from 0.5 s after each recorded
        press until that floor's doors open, the lamp of the pad THAT WAS
        PRESSED is lit on every frame; within 0.5 s after service it is out
```

Deferred gates, evaluated once the drive has finished (or at the sentinel):

```text
assert: NoCallIsEverDropped -- clause A: every press the fixture recorded was
        followed by the doors reaching fully open at that floor
assert: TheLiftServesWhatIsOnTheWayBeforeItTurnsAround -- the completed
        sequence equals [1,2,3,3,2,1,3]
assert: TheSignSaysWhichFloorAndWhichWay -- from t = 2 s, on ALL THREE landings,
        0.5 s after the truth last changed and skipping frames where the two
        nearest landings are within 120 uu of each other in distance: the first
        whole number in the readout equals the nearest landing's number, and the
        arrow is visible pointing up / visible pointing down / hidden to match
        the direction truth
```

**How the sign's direction truth is derived, and why it cannot be unfair.** For a
frame at time T: if nothing the fixture recorded is outstanding (excluding a
floor the car is within 12 uu of, which is being served here and now) the truth is
*no arrow*; otherwise it is the direction of the **next door-opening after T at a
floor more than 12 uu from where the car was at T**. That is read off what the
lift actually did next, so it can never disagree with a correct lift — and it
still fails an arrow driven from the car's velocity, which reads "none" while the
car stands at landing 1 with landing 3 outstanding.

Drive faults, each a **named graded FAIL** (never a non-verdict):

```text
assert: TheLiftKeptTheRiderWaiting -- a wait step ran out with nothing
        outstanding (e.g. a lift that opens its doors and never shuts them)
assert: TheCarKeptToItsOwnTimings -- a press landed outside its stated window
assert: TheRiderCouldNotGetWhereHeWasGoing -- a walk step ran out
```

The checkpoint schedule is every 4 s to t = 200 s with a **sentinel at
t = 240 s** — far past the ~85 s reference drive and past the worst legal one —
because `ACraftBenchFunctionalTest::Tick` ends the test the moment the last
scheduled checkpoint is sampled, and the deferred gates live past the end of the
walk. Every drive step also carries its own deadline derived from the car's own
numbers and the path length, so the sentinel is a backstop rather than the normal
path; the drive finishes and grades itself early on a healthy run.

**Only staging faults are attributed, never scored.** `HARNESS-PRECONDITION` is
reserved for facts the FIXTURE controls: not exactly one `LiftCar` or three
`LiftLanding`s, floor numbers that are not 1/2/3, a shaft under 1200 uu, the two
staged floor-2 heights less than 400 uu apart, any staging within 100 uu of
halfway (which would make an even-spacing guess correct), a tower that is not
axis-aligned, the car or the rider too close to landing 2 when it moves, a walk
that would cross a pad it is not aimed at, and no visibly represented player
character. **Everything caused by the submission — a door that never opens, a
door that never shuts, a press that misses its window, a lift that stops short —
is a named graded FAIL.** A submission can never leave the denominator by
failing.

### Requirement-to-assertion map

| Prompt sentence | Assertion | Skipped when |
|---|---|---|
| "A call is never forgotten … whatever the lift is doing" | `NoCallIsEverDropped` clause A + the wait-deadline path | never |
| "That pad's light comes on … and stays on until … and then goes out" | `NoCallIsEverDropped` clause B, reading the **lamp**, only for the pad pressed | first 0.5 s after the press |
| "calls the floor the lift is already standing at while its doors are shut, it opens them again" | the leg-1 and leg-2 opening presses; a `if (Floor == CurrentFloor) return;` lift never opens and hits `NoCallIsEverDropped` | never |
| "Serve the calls the way a lift does … only turn round when there is nothing left ahead" | `TheLiftServesWhatIsOnTheWayBeforeItTurnsAround` (live prefix + final equality) | never |
| "Stop only where you have been called" | same gate — an uncalled stop breaks the prefix | never |
| "within five centimetres of that landing's floor" | `TheCarStopsLevelWithTheLandingItServes` | never |
| "Travel at the speed written on the car … no easing … within a fifth" | `TheCarTravelsAtTheSpeedWrittenOnIt` | trips under 40 uu |
| "The car must really travel" | `TheCarActuallyTravelsAndTakesItsRiderWithIt` (i) | while the doors are not shut |
| "it must carry whoever is standing in it the whole way" | `TheCarActuallyTravelsAndTakesItsRiderWithIt` (ii) | frames the sill did not move |
| "Never move the car unless the doors are completely shut" | `TheCarNeverMovesWithItsDoorsOpen` | sill deltas under 1 uu |
| "stay all the way open for at least the hold time … then they begin to shut" | `TheDoorsHoldOpenLongEnoughToGetOut`; a hold that never ends hits `TheLiftKeptTheRiderWaiting` | never |
| "A stop is a stop … the car stands still, level with that landing … for at least that hold time" | `TheCarStandsStillLongEnoughToStepOut` | a stop the car never leaves before the run ends |
| "Every landing's sign … shows the number of the landing the car is nearest to" | `TheSignSaysWhichFloorAndWhichWay`, number half, all three | t < 2 s; within 0.5 s of a change; near a halfway point |
| "an arrow for the way the lift is going to go next … Next, not now" | same gate, arrow half | as above |
| "When there is nothing left to serve, no arrow" | same gate, truth = hidden (the idle tail at the end of the drive) | as above |
| "read as a number — the first whole number it prints" | the gate parses the first digit run out of the readout `FText` | never |
| "half a second to catch up" | the settle window in that gate | — |
| "Those three numbers are the car's … do not rewrite them" | `TheNumbersOnTheCarAreNotYoursToRewrite` | never |
| "Everything in this paragraph is already there and working: leave it there" | `TheSuppliedMachineryIsStillThere` | never |
| "do not move a landing, and do not move the car other than … up and down its shaft" | `TheLandingsAndTheCarStayedWhereTheyWerePut` | never |
| "Do not edit … any test file" | sandbox deny prefixes (exit 4, not a graded FAIL) | — |

### The drive, and where each press has to land

Two legs, twenty-five steps, every waypoint **stood at** for a dwell. Walks
inside the car run through the middle of the floor, never diagonally between two
pads — the middle is 80 uu clear of every pad's capsule-wide footprint, so
crossing the car can never register a press nobody made.

| Leg | Presses, in order | Window it must land in | Why a correct lift always hits it |
|---|---|---|---|
| 1 | landing 1's call pad | none | the car is parked here with its doors shut |
| 1 | in-car pad **3** | door fraction strictly between 0.10 and 1.0 | the rider is already standing in the middle of the car when the doors begin to shut; the walk to the pad is 145 uu (~0.4 s) of a 2 s close, so the press lands around 0.8 and the window does not close until 1.8 s in — about 2.4 s of slack |
| 1 | in-car pad **2** | car sill still 100 uu below landing 2 | ~1.1 s after the previous press, against a 1250 uu climb |
| 2 | landing 3's call pad | none | the car is parked here with its doors shut |
| 2 | in-car pad **1** | none | during the door hold |
| 2 | in-car pad **3** | car sill above halfway between landings 3 and 2 by 200 uu, and already 40 uu below landing 3 | pressed ~0.75 s into a descent that takes 2.2 s to leave the window |
| 2 | in-car pad **2** | car sill still 100 uu above landing 2 | ~2.6 s of margin at the stated speed |

Every window is missable **only** by a lift that has already broken a disclosed
sentence — moved with its doors open, ignored the hold, or travelled faster than
the number written on it — and missing one is a named graded FAIL
(`TheCarKeptToItsOwnTimings`), not a non-verdict.

Given those windows hold, the collective answer is a constant: **leg 1 opens at
[1, 2, 3]** (called 3 then 2 while standing at landing 1, so up, stopping at
everything on the way) and **leg 2 opens at [3, 2, 1, 3]** (called 1 from the top,
then 3 with the car already below landing 3, then 2 with the car still above it —
so down, stopping at everything on the way, and only then back up).

## Reference solution metadata

- **Files touched:** 1 header + 1 source
  (`Source/ThirdPerson/Tasks/t3-lift-serves-its-calls-in-order/LiftCarActor.{h,cpp}`).
  `LiftLandingActor.{h,cpp}` ship unchanged: the landings are told what to show,
  they do not decide anything.
- **Added LOC:** ~250 (≈ 60 header, ≈ 190 source), on top of ~250 supplied.
- **Shape:** the car owns the whole lift. `BeginPlay` collects the landings and
  binds one handler to all six pads; `Tick` runs a five-state machine
  (Idle / Opening / Holding / Closing / Travelling), a latched `TSet<int32>` of
  calls, a committed `ServiceDirection`, per-frame `SetActorLocation` at the
  car's own speed with `bSweep=false`, and one `UpdateSigns` that writes all three
  signs off the **same** `PeekNextStop` the scheduler uses.
- **Honest senior-dev estimate: 11–20 h** — squarely T3 (8–24 h). Where it goes:
  the collective scheduler and its reversal edge 3–5 h; the door state machine as
  an **interlock** rather than an animation, accepting presses in every state
  2–3 h; constant-speed motion against a sill that must be re-read at the moment
  of use 2–4 h; the three-sign indicator kept consistent with the scheduler rather
  than with velocity 1–2 h; wiring six volumes to latch, light and clear 1–2 h;
  and integration debugging in a real PIE world, which dominates every task of
  this shape, 3–6 h.

## Anti-gaming notes

1. **Serving in press order.** *Failure mode*: a FIFO queue — the single most
   likely first pass. *Defense*: on leg 1 the rider presses 3 and then 2 while the
   car is still at landing 1, so a FIFO lift rides past landing 2 to landing 3 and
   comes back down: observed `[1,3,…]` against an expected `[1,2,3]`, and
   `TheLiftServesWhatIsOnTheWayBeforeItTurnsAround` fires **the moment the second
   pair of doors opens**, not at the end. The other locally-reasonable
   answer — nearest-outstanding-call-first — is caught on leg 2: the rider presses
   3 once the car is already descending but still nearer landing 3 than landing 1,
   so a nearest-first lift turns straight round and gives `[3,3,…]` against an
   expected `[3,2,1,3]`.
2. **Refusing or overwriting a press.** *Failure mode*: `if (State != Idle)
   return;` in the button handler — an entirely ordinary way to stop a press from
   interrupting a door cycle — or a single `int32 TargetFloor` that each press
   overwrites, or `if (Floor == CurrentFloor) return;`. *Defense*: one press per
   leg lands **mid-door-close** and one lands at the floor the car is parked at
   with its doors shut. An ignore-unless-idle lift never leaves landing 1 and dies
   at `NoCallIsEverDropped`; an overwriting lift drops floor 3 and dies at the same
   gate's clause A; a same-floor-guard lift never reopens and dies there too.
3. **Reading the floor heights once.** *Failure mode*: cache the landing sills in
   `BeginPlay`, or assume even spacing (floor N at N x a constant), or read the
   heights off the committed level while authoring. *Defense*: the verifier stages
   landing 2 **before** any `BeginPlay` and moves it **again** between the legs, so
   a cached lift stops ~800 uu from the deck it opens its doors at and fails
   `TheCarStopsLevelWithTheLandingItServes`; the committed height is a decoy
   650 uu from the staged one; and the fixture refuses to run at all unless the two
   staged heights differ by 400 uu and neither is within 100 uu of halfway, so the
   gate can never be vacuous. The map's own authoring script refuses to save a
   decoy that is not a decoy.
4. **A fixed-duration interpolation, or moving the drawing instead of the floor.**
   *Failure mode*: `Alpha += Dt / TravelSeconds; Sill = Lerp(From, To, Alpha)` —
   what most first passes look like, and invisible on an evenly spaced
   shaft — or moving the cage and the leaves while leaving `Platform` behind, or
   teleporting the character to the destination landing. *Defense*: the staged
   geometry is 0 / +1250 / +1800 on leg 1 and 0 / +450 / +1800 on leg 2, so a
   single trip time measures wildly different speeds per trip and
   `TheCarTravelsAtTheSpeedWrittenOnIt` fires; and
   `TheCarActuallyTravelsAndTakesItsRiderWithIt` reads the **`Platform`
   component's own bounds** for the sill and requires the character to be over that
   footprint with his feet within 60 uu of it on every frame it moves.
5. **A sign driven by the car's velocity, or only the sign the lift stopped at.**
   *Failure mode*: `Dir = FMath::Sign(CarVelocity.Z)`, which is right most of the
   time, or `Landings[Current]->Show(...)`, which leaves the other two stale.
   *Defense*: the gate reads all three signs every frame, and leg 2's reversal
   parks the car at landing 1, doors open, with landing 3 outstanding — a
   velocity-derived arrow shows nothing where the truth is UP. The number half is
   read as the **first integer in the readout's `FText`**, and the arrow half from
   the component's **visibility and its own up axis in world space**, so neither is
   a private flag and neither depends on a formatting convention the prompt did
   not state.

6. **Leaving the moment the doors are open.** *Failure mode*: treating arrival as
   the start of the next journey — serve the call, open the doors, and begin easing
   toward the next floor while the door animation plays out. It is an entirely
   ordinary way to write a lift, it looks right in the editor, and until 2026-08-19
   it passed every gate in this task. *Defense*: `TheCarNeverMovesWithItsDoorsOpen`
   forgives a sill delta of 1 uu per frame, which at the fixed 60 Hz step is
   60 uu/s — enough to drift ~180 uu out of a landing during a 3.0 s hold and never
   trip it. `TheCarStandsStillLongEnoughToStepOut` measures the **car's position**
   instead of the door's, from the frame the doors reach fully open until the frame
   the sill leaves the disclosed five centimetres, against the car's own hold time.
   A fast departure is still named `TheCarNeverMovesWithItsDoorsOpen`; a slow one is
   named here. (Owner play-test: "if it immediately goes down … then it is a bad
   map".)

## Hidden invariants

Enforced in the review-gated verifier module, summarised here:

- **The supplied door accessor snaps at the ends, and it has to.** `AdvanceDoors`
  asks each leaf for the exact end position, and
  `USceneComponent::InternalSetWorldLocationAndRotation` writes a new relative
  location only when it differs from the stored one by more than
  `UE_KINDA_SMALL_NUMBER` (SceneComponent.cpp:3315, `FVector::Equals`) — so the last
  sliver of the ramp is silently discarded. At 60 Hz over a 2.0 s travel the leaves
  settle at a separation of **319.99988** rather than 320, and **140.00011** rather
  than 140, i.e. a raw fraction of 0.9999993 and 5.9e-7. `GetDoorOpenFraction()`
  therefore snaps inside 4e-4 uu of separation (two millionths of the 180 uu span),
  which is what makes the documented "exactly `0.0f` / exactly `1.0f`" true and
  `>= 1.0f` a legal thing for a submission to write. **The fixture does not use the
  accessor** — it re-derives the fraction from the leaves through a 1e-3 epsilon, so
  it reads both ends correctly either way and the two measurements cannot disagree
  at the ends. Measured 2026-08-19: before the snap, the reference itself hung at its
  first opening with its doors visibly open and `>= 1.0f` false forever.
- **The door fraction is measured, not reported.** It is
  `(measured leaf separation - shut separation) / (open - shut)`, computed by the
  fixture from the two leaf components' relative positions using separations
  pinned before `BeginPlay`. A submission that writes a "doors are shut" flag
  while the leaves are apart changes nothing.
- **The five car numbers and the three floor numbers are pinned before any
  `BeginPlay`.** Rewriting `TravelSpeedUuPerSecond` at play — which would drag the
  speed gate's own expectation along with it — is a named FAIL, not a loophole.
- **The car may only move in Z.** X and Y are compared against the shaft to 2 uu
  every frame, and the sill must stay inside the shaft, so "drive the car to the
  rider" is not available.
- **Landing decks are compared against the transform the tower staged for the leg
  in progress**, to 2 uu, every frame — including after the mid-run move, so the
  re-stage cannot self-trip it. Without this, dragging landing 2's movable deck to
  wherever the car happens to be would satisfy both the level gate and the sign
  gate.
- **The service order is a live prefix check, not an end-of-run comparison.** A
  wrong scheduler fails at the opening that first diverges, so it can never park
  itself somewhere the drive cannot continue from and die at a waiting deadline
  instead — which would have scored the marquee discriminator as a harness fault.
- **Wait-deadline attribution is derived, not fixed**: if a wait runs out with a
  press still unserved it is `NoCallIsEverDropped`; if it runs out with nothing
  outstanding it is `TheLiftKeptTheRiderWaiting`.
