---
id: t2-crate-you-carry-changes-what-you-can-do
substrate: ThirdPerson
set: craftbench-public
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_HaulYard :: AHaulCarryFunctionalTest"]
fps_legs: [60, 20]
---

# t2-crate-you-carry-changes-what-you-can-do

Pick a crate up and it changes what you are: you move at half speed, you cannot
jump, and the crate rides in front of you as a solid object that will not go into
a wall. Set it on a weight plate and the plate adds up what is **resting** on it,
compares that with its **own** painted number, and lifts the **one** door it is
wired to until the weight comes off again.

Five channels are driven off one piece of state — where the crate is, whether it
and its carrier are solid to each other, top speed, jumping, and the plate/door
chain — and four of them fail silently on their own.

> **`deliverable_root:` is not a front-matter key** (`tools/verify-single/spec.py::_KNOWN_KEYS`;
> an unknown key is a hard `ValueError`, exit 2). The deliverable root is stated
> as the first line of *Workspace state pre-task* and again in the prompt:
> `Source/ThirdPerson/`.

## Primary concept

- `carried-object-kinematics` — moving an actor every frame so that it keeps
  colliding with the world it is carried through
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine)

The load-bearing behaviour is **one carry state driving five separate channels at
once, and putting every one of them back on release**. The grade never asks *how*:
a swept per-frame move, a physics constraint, or anything else that leaves the
crate solid against the world grades identically.

## Composed concepts

- `character-movement-tuning` — top ground speed on the character movement
  component, changed and restored
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/character-movement-component-in-unreal-engine)
- `jump-gating` — refusing a jump below the input layer, and re-allowing it
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/setting-up-character-movement-in-unreal-engine)
- `component-sweeps-and-move-ignore` — a moved component that still collides, and
  two actors told to ignore each other while one carries the other
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-response-reference-in-unreal-engine)
- `mass-sensing-trigger` — a trigger whose answer is a SUM over a live SET, not a
  flag, compared against its own configured threshold
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-filtering-in-unreal-engine)
- `per-instance-actor-wiring` — one actor driving the particular other actor it is
  wired to, read off the level rather than assumed from ordering
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/actor-communication-in-unreal-engine)

**Production pattern this composes (Hard Rule 1).** Valve's *Portal* (2007) ships
exactly this composition and is the public reference for it: the Weighted Storage
Cube is carried in front of the player as a solid object that is stopped by
geometry, carrying it changes what the player can do, and setting it on a Weighted
Storage Cube Button — a trigger that answers to what is **resting** on it and not
to a player standing on it — actuates one specific door it is wired to, which
closes again when the cube is removed. Four concepts in one loop: carry
kinematics, movement modulation, a mass-sensing trigger, and per-instance
actor-to-actor wiring. Publicly documented in Valve's own developer wiki
(https://developer.valvesoftware.com/wiki/Portal) under `prop_weighted_cube` and
`prop_button`.

## Prompt given to the agent

> The yard holds three crates, two weight plates and two lift doors. Every crate
> has its weight painted on it in kilograms and no two are the same. Every plate
> has its own number painted on it — the least it will hold for — and each plate
> is wired to one particular door, its own.
>
> **The numbers are not fixed.** The weights and the thresholds are set while the
> yard is being laid out, and they are set again part way through. The number
> painted on a thing is always its current one, so read it when you need it; a
> number you copied down at the start goes stale.
>
> **Picking up.** If your hands are empty and the middle of a crate is within
> **250 cm** of your middle, measured flat, you pick that crate up — the nearest
> one, if two are close. You carry **one at a time**.
>
> **Carrying.** While you carry it, it rides in front of you: its middle stays
> ahead of you along your facing, between **290 and 380 cm** from your middle
> measured flat, and its underside stays at least **120 cm** above the yard floor.
> This is asked of you from **half a second** after you pick it up. It is still a
> solid object while you hold it: however hard you push, no more than **40 cm** of
> it may end up inside one of the yard's walls, measured in every direction at
> once. A wall that gets in the way simply stops it — so while you are within
> **600 cm** of a wall we do not ask where the crate is riding, only that it is
> not buried in the wall; once you are clear of the wall it has to be riding in
> front of you again.
>
> The crate must never be what stops **you**. You have to be able to walk about
> normally while carrying, including straight at a wall: a crate you cannot walk
> with is not carried, it is stuck.
>
> **Carrying costs you.** While you carry, your top speed on the ground is about
> half what it is empty-handed — anything from **35% to 65%** of it. Empty-handed
> that top speed is **400 to 600 units a second**. And while you carry you cannot
> jump **at all** — not from the key, and not if anything else asks you to.
> Empty-handed you jump normally: pressed and released, you are off the ground
> inside **a second and a half**. Once a crate is set down you are back to between
> **85% and 115%** of your empty-handed top speed.
>
> **Setting down.** Each plate's pad is **900 cm square**. You are standing on a
> plate when your middle is over its pad and you are on the ground. If your hands
> are full and you have been standing on a plate moving slower than **20 cm a
> second** for **half a second**, you set the crate down — where it was riding,
> straight down from where you were holding it. You do not pick anything up again
> for **a second and a half** after that. Within **two and a half seconds** the
> crate must be resting on whatever is beneath it — the pad, or the floor — with
> its underside within **12 cm** of that surface, not hanging in the air; and it
> stays within **60 cm** of where you left it until somebody picks it up again.
>
> **The plates.** A plate weighs the crates **resting on its pad**: a crate counts
> when its middle is over the pad and its underside is within **12 cm** of the
> pad's surface. A crate held in the air over a pad does not count, and neither
> does a person — a person standing on a plate is not cargo and counts for
> nothing. When the total is at least that plate's own painted number, the plate
> holds **its own** door open; the rest of the time that door is shut. Open means
> the door's slab has lifted at least **250 cm** above where it started; shut
> means it is back within **20 cm** of where it started. Either state must be
> reached within **two seconds** of the load on that plate changing, and it must
> happen **every time** — a door that lifts once and never drops, or drops once
> and never lifts again, is broken.
>
> Where the plates, the door frames and the walls stand is not yours to change.
> The slab lifting out of a door frame is the mechanism; the frame itself does not
> travel.
>
> Three things the yard already carries on those actors are its own wiring: the
> weight on a crate, the threshold on a plate, and the link that says which door a
> plate belongs to. **Keep them as they are — same names, same kinds.** Add
> whatever you like beside them; renaming or retyping one of those three takes the
> yard's own wiring with it.
>
> Write your solution in C++ under `Source/ThirdPerson/`, the agent-writable
> module on this substrate. Do not edit the level, any config file, or any test
> file. The crates, plates, doors, the character and the yard are all supplied and
> in place; nothing decides anything.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on
this substrate). `Source/CraftBenchTests/` is deny-listed and a submission file
under it is a SANDBOX-REJECT (exit 4), not a graded FAIL; so are `Content/Maps/`,
`Content/ThirdPerson/`, `Content/Characters/` and every `Config/` file (no
`config_allow` is declared by this task).

Files that **exist** under `Source/ThirdPerson/Tasks/t2-crate-you-carry-changes-what-you-can-do/`:

- `HaulCrateActor.h` / `.cpp` — `AHaulCrateActor`, tagged `HaulCrate`. Supplied
  and complete as a crate:
  - `Body` — an 80 cm cube, **the root**, movable, `BlockAll`, physics off. The
    actor stands with the box's centre at its location.
  - `WeightLabel` — a `UTextRenderComponent` above it that prints `"%.0f kg"`
    from `MassKg` **every frame**, so the painted number can never disagree with
    the number anything reads.
  - `UPROPERTY(EditAnywhere, BlueprintReadOnly) float MassKg`.
  - **No pickup logic, no tick logic beyond the readout, no reference to the
    character.**
- `WeightPlateActor.h` / `.cpp` — `AWeightPlateActor`, tagged `WeightPlate`.
  - `Pad` — a 900 x 900 x 20 cm slab, **the root**, movable, `BlockAll`. 20 cm is
    under the character's step height, so the pad is walked onto, not climbed.
  - `HoldLabel` — prints `"holds from %.0f kg"` from `MinimumHoldKg` every frame.
  - `UPROPERTY(EditAnywhere, BlueprintReadOnly) float MinimumHoldKg`.
  - `UPROPERTY(EditInstanceOnly, BlueprintReadWrite) TObjectPtr<AActor> LinkedDoor`
    — **set per placed instance in the yard**, each plate to its own door.
  - **No sensing, no sum, no door logic.**
- `LiftDoorActor.h` / `.cpp` — `ALiftDoorActor`, tagged `LiftDoor`.
  - `Frame` — a scene root; `PostLeft`, `PostRight`, `Lintel` — the doorway.
  - `Panel` — the 400 x 400 cm slab that lifts. Movable, `BlockAll`.
  - `LiftLabel` — prints how far `Panel` has risen from its own play-start pose,
    **derived from the panel's live position**, so the readout cannot disagree
    with the gate.
  - `GetShutPanelHeight()` — where the slab was when play began.
  - **Nothing moves the slab.**
- `HaulHeroCharacter.h` / `.cpp` — `AHaulHeroCharacter : AThirdPersonCharacter`,
  tagged `HaulHero`. Supplied: the four Enhanced Input actions wired (the base
  class declares them and assigns none, so a native subclass otherwise binds
  nothing at all and the level cannot be driven by hand), a mannequin body and
  its animation blueprint from the read-only `/Game/Characters/` pool, and the
  template's tuned ground movement (top walking speed 500, jump velocity 500).
  **No task behaviour of any kind.** This is the class the yard places and the
  player possesses, so this is where the carry work has to land — the level is not
  editable and a subclass of a placed actor is never instantiated.

The level — `Content/Maps/t2-crate-you-carry-changes-what-you-can-do/L_HaulYard.umap`,
a committed binary, verifier-owned and deny-listed:

| Element | Placement | Notes |
|---|---|---|
| Floor | 9,800 x 8,000, striped every 400 cm, stripes non-colliding | |
| Three `AHaulCrateActor` | in a row 1,200 cm apart | |
| Two `AWeightPlateActor` | 2,400 cm apart, each with `LinkedDoor` set to its own door | |
| Two `ALiftDoorActor` | in a line east of the plates | frames static, slabs movable |
| One wall | a solid 400 x 800 x 500 block, tagged `YardBlocker`, off the measured lane | deep enough to CONTAIN a crate that was teleported into it |
| Two landmark posts | different sizes | so a moving camera is distinguishable from a still one |
| `PlayerStart` + one placed `AHaulHeroCharacter` | the character is set to be possessed by player 0 | |
| World Settings | **name NO game mode** | so `BP_ThirdPersonGameMode` and its `BP_ThirdPersonPlayerController` (the only class carrying `IMC_Default`) stay in force and the yard is playable by hand |
| Fixture | one placed `AHaulCarryFunctionalTest` | |

**The masses, the thresholds and the coordinates are deliberately NOT in this
section.** They are readable in the level, painted on the things they belong to —
and the fixture prices the yard itself, twice, so what is painted in the committed
map is only the starting paint.

Files that **do not exist**: no carry logic, no speed or jump modulation, no plate
sensing, no door motion, no Blueprint subclass, no level edits. The empty
submission compiles (L1 green) and FAILs L2 the first time the drive stands beside
a crate with empty hands.

## Verifier specification

The test runs in PIE from
`Content/Maps/t2-crate-you-carry-changes-what-you-can-do/L_HaulYard.umap` on the
**ThirdPerson** substrate, ticked at a fixed deterministic step
(`-deterministic -FPS=60`, and again at `-FPS=20`). Verification primitive:
**pie-checkpoint-sampling** with per-frame geometric readback, driven by a
per-frame `AddMovementInput` walk — the same input path a human drives with WASD.

**Everything is derived from the live world.** `PrepareTest` resolves three
`HaulCrate`, two `WeightPlate`, two `LiftDoor` and one `YardBlocker` by tag,
resolves the possessed player character, reads each plate's `LinkedDoor` by
reflection, takes the floor height off a staged crate and the pad half-width off a
placed pad, and builds the whole route (48 stops) from those numbers. Nothing about
the route is written down as a coordinate.

**The fixture prices the yard, twice.** `MassKg` and `MinimumHoldKg` are written
in `PrepareTest` and written again at the RE-PRICE, part way through the run.
Round 2's numbers are chosen so that **two doors standing open have to shut with
not one crate moving**. That is what makes a hard-coded threshold table, or a
value cached in `BeginPlay`, fail by name rather than pass.

**Carried is decided geometrically, never asked.** A crate whose underside is more
than 40 cm above the yard floor is off the ground. Off the ground and within
500 cm of the character, it is being carried and the ride gates apply; off the
ground and further away, somebody has left it hanging and
`TheCrateYouPutDownComesToRest` says so. The fixture never calls into the
submission, so any mechanism that produces the behaviour grades the same.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development"
```

No warning assert: `--strict-warnings` is off on the `cb eval` / `cb refgate`
paths and the prompt says nothing about warnings, so gating on it would be both
dead and undisclosed.

### L2 — AFunctionalTest behavioral trace

```text
AHaulCarryFunctionalTest (derives ACraftBenchFunctionalTest):

PrepareTest():
    Super::PrepareTest()
    resolve by tag: 3 HaulCrate (sorted west->east), 2 WeightPlate (sorted by Y),
      2 LiftDoor, >=1 YardBlocker; the player character, which must carry the tag
      HaulHero and a visible body.        [all HARNESS-PRECONDITION on failure]
    read MassKg / MinimumHoldKg as FFloatProperty and LinkedDoor as
      FObjectProperty; refuse if any is absent, if a plate names no door, or if
      both plates name the same door.
    resolve each door's graded part: the component named "Panel", else the
      largest by local bounds, ties by name. Record its world Z as "shut".
    FloorTopZ := a staged crate's box minimum Z.  PadHalf := a placed pad's
      own half-width.  Both read, never written down.
    ValidateMargins(): every one of the 13 comparisons the drive actually
      stages, across BOTH price rounds, must clear its threshold by >= 8 kg,
      and the second price list must change at least one plate's verdict.
      [HARNESS-PRECONDITION -- a gate that could round either way is not a gate]
    PriceYard(round 1);  BuildRoute();
    ValidateRoute(): every leg must pass more than 290 cm from any crate it is
      not fetching (anything inside 250 cm gets picked up), and no leg but the
      wall push may run into a wall.       [HARNESS-PRECONDITION]
    SetCheckpointSchedule({10, 20, ... 470, 480})
      -- 480 s is the SENTINEL. The base class declares success the instant the
      last scheduled checkpoint is sampled, so every end-of-run gate is
      evaluated there and nowhere earlier. The drive measures ~330 s.

Tick (every frame):
    measured ground speed, exponentially smoothed at 0.15 -- the estimator
    already validated on t1-mud-wade. Samples count
    only on a designated straight leg, only after 1.8 s of that leg (which
    covers BOTH the acceleration ramp and the turn at its head), only above
    30 uu/s, and at least 20 of them are required or the gate FAILS rather
    than silently skipping.

    assert: TheCrateYouPutDownComesToRest -- no crate is off the ground with
            nobody within 500 cm of it; and 2.5 s after a crate lands, its
            underside is within 12 cm of whatever a downward trace finds
            beneath it
    assert: TheCrateRidesInFrontOfYou -- at most one crate off the ground at a
            time; a crate does not come off the ground from further than
            320 cm away; from 0.5 s after a pick-up and while the character is
            more than 600 cm from every wall, the carried crate is ahead along
            the facing (positive dot), 290-380 cm away flat, underside >= 120 cm
            above the floor; and standing within 250 cm of a crate with empty
            hands for 2 s with nothing riding FAILS here
    assert: TheCrateStaysOutOfTheWalls -- the intersection of the carried
            crate's collision box with any YardBlocker box does not exceed
            40 cm on ALL THREE axes for more than 0.5 s continuously
    assert: EachPlateHoldsItsOwnDoorForItsOwnWeight -- 2 s after the load on a
            plate last changed (or after the re-price), if the summed MassKg of
            the crates RESTING on that plate's pad is at least THAT plate's own
            MinimumHoldKg, then the door named by THAT plate's LinkedDoor is
            >= 250 cm above its own play-start pose
    assert: TheDoorDropsWhenTheWeightComesOff -- and if it is not, that same
            door is back within 20 cm of its play-start pose
    assert: TheYardStaysWhereItIsPut -- every plate, every door ACTOR and every
            wall is within 2 cm of where the yard staged it (the door PANEL is
            expected to move -- that is the mechanism); and a crate that has
            been set down stays within 60 cm of where it landed
    assert: CarryingStopsYouJumping / EmptyHandedYouJumpNormally -- at two
            scheduled stops the fixture stands the character still, calls
            Jump(), calls StopJumping() 0.2 s later, and watches for 1.5 s.
            Empty-handed it must leave the ground (movement mode falling, or
            Z up >= 40 cm); carrying it must never leave the ground.

    DRIVE: AddMovementInput toward the current stop. A stop that names a crate
    walks at that crate's LIVE position and arrives 240 cm short of it. On
    arrival the character STANDS for that stop's dwell before advancing --
    advancing on arrival consumes stops instantly and nothing is measured. The
    wall push never arrives: it pushes until the character has been stalled for
    3 s. Each leg carries a deadline of (path length / a quarter of the MEASURED
    empty-handed speed) + 12 s + its own dwell, never a written-down number of
    seconds; blowing it FAILs TheHaulRanBothRounds naming the stop, its label,
    the distance covered and the leg length.

OnCheckpoint(i):
    every checkpoint LOGS and grades nothing:
      "[t2-haul calib] cp<i> t=<t> stop=<n>/<N> riding=<c> spd=<v> free=<v>
       carry=<v> back=<v> round=<r> picks=<n> loadL=<kg> liftL=<cm>
       loadH=<kg> liftH=<cm> spellsL=<n> spellsH=<n>"

    at the SENTINEL (t = 480 s), the gates that are vacuous unless their leg
    happened:
      TheHaulRanBothRounds              every stop completed, and the yard was
                                        re-priced
      WalksAtItsNormalTopSpeedEmptyHanded  >= 20 clean samples, and 400-600 uu/s
      CarryingSlowsYouDown              >= 20 clean samples, and 35-65% of that
      SettingItDownGivesYourSpeedBack   >= 20 clean samples, and 85-115% of it
      CarryingStopsYouJumping           both jump tries actually happened
      EachDoorLiftsMoreThanOnce         each door reached the open band on >= 2
                                        separate occasions and returned to the
                                        shut band at least once in between
```

**The staged sequence** (crate masses and plate thresholds are the fixture's, not
the map's; `L` is the low-Y plate, `H` the high-Y one):

| # | What the drive does | L holds | H holds | Verdict |
|---|---|---|---|---|
| 1 | west crate onto L | 18 | 0 | L shut (18 < 30) |
| 2 | stand on H, empty-handed | 18 | 0 | H shut — **a person is not cargo** |
| 3 | middle crate onto H | 18 | 42 | H shut (42 < 55) — **one hard-coded threshold of 30 opens here** |
| 4 | east crate onto H beside it | 18 | 112 | H **opens** |
| 5 | lift the middle crate off H | 18 | 70 | H **stays open** — the single-occupant-flag catcher |
| 6 | set it on L | 60 | 70 | L **opens** |
| 7 | lift the east crate off H, put it back on H's other slot | 60 | 0 → 70 | H **shuts**, then **opens again** |
| — | **RE-PRICE. Nothing moves.** | 76 vs 90 | 48 vs 60 | **both doors must shut** |
| 8 | lift the west crate off L, add it to H | 52 | 72 | L shut, H **opens** |
| 9 | lift the east crate off H, set it on L | 100 | 24 | H **shuts**, L **opens again** |

Every comparison clears by at least 8 kg and `ValidateMargins` refuses to start if
one does not.

## Requirement-to-assertion map

| Prompt requirement | Assertion | Skipped when |
|---|---|---|
| pick up a crate within 250 cm with empty hands | `TheCrateRidesInFrontOfYou` (the empty-hands-beside-a-crate clause) | never |
| the nearest one, and one at a time | `TheCrateRidesInFrontOfYou` (the two-in-the-air clause) | never |
| not from further than that | `TheCrateRidesInFrontOfYou` (the over-reach clause, > 320 cm) | never |
| it rides 290-380 cm in front, 120 cm clear of the floor | `TheCrateRidesInFrontOfYou`, every frame | for the first 0.5 s after a pick-up, and within 600 cm of a wall — both stated in the prompt |
| no more than 40 cm of it inside a wall | `TheCrateStaysOutOfTheWalls`, every frame | for the first 0.5 s of any one contact |
| the crate never stops you | `TheHaulRanBothRounds` — the leg deadline, naming the stop and the distance covered | never |
| carrying, top speed is 35-65% of empty-handed | `CarryingSlowsYouDown` at the sentinel | never — under 20 samples FAILS, it does not skip |
| empty-handed, 400-600 units a second | `WalksAtItsNormalTopSpeedEmptyHanded` | same |
| after setting down, 85-115% again | `SettingItDownGivesYourSpeedBack` | same |
| carrying, you cannot jump at all | `CarryingStopsYouJumping` | never |
| empty-handed you jump normally | `EmptyHandedYouJumpNormally` | never |
| set down on a plate when you stop | not a gate of its own — it is how every plate load in the table above is produced; a submission that never sets down fails at step 1 | never |
| it comes to rest, not hanging | `TheCrateYouPutDownComesToRest`, both clauses | for 2.5 s after it lands — the settle the prompt states |
| it stays within 60 cm of where you left it | `TheYardStaysWhereItIsPut` (the crate clause) | same |
| a plate weighs what is RESTING on its pad | `EachPlateHoldsItsOwnDoorForItsOwnWeight` — the load is the sum over crates whose middle is over the pad and whose underside is within 12 cm of it | for 2 s after that plate's load changes, or after the re-price |
| a person is not cargo | step 2 of the table: H holds 0 with somebody standing on it | same |
| its own painted number | steps 3 and the re-price: one threshold is wrong somewhere | same |
| its own door | the per-plate iff, judged for both plates every frame, so a cross-wire fails from both sides at once | same |
| open >= 250 cm, shut within 20 cm, within 2 s | the two door gates | same |
| it must happen every time | `EachDoorLiftsMoreThanOnce` at the sentinel | never |
| the numbers change part way through | the RE-PRICE row of the table — both doors must shut with nothing moving | never |
| keep `MassKg` / `MinimumHoldKg` / `LinkedDoor` as they are | HARNESS-PRECONDITION, uncredited, naming the property — never a graded FAIL, because a task made unwinnable by a rename is a staging fault, not a wrong answer | never |
| where the yard stands is not yours to change | `TheYardStaysWhereItIsPut` (plates, door actors, walls) | never |
| C++ under `Source/ThirdPerson/` | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

## Reference solution metadata

- LOC range: 260-320 across three of the four supplied files
  (`HaulHeroCharacter.{h,cpp}` — the carry state machine, speed and jump;
  `WeightPlateActor.cpp` — the resting set, the sum, the comparison, the wired
  door; `LiftDoorActor.{h,cpp}` — the slab's travel). `HaulCrateActor` is
  **unchanged**: nothing the crate does is the crate's job.
- Files touched: 5 (all pre-existing scaffold files).
- Senior-dev hours: 4-6. Where it goes: ~1.5 h on the carry state machine (the
  pick-up and set-down predicates with their two guards, the hold point, the
  **swept** per-frame move, telling the crate and the capsule to ignore each other
  in **both** directions, and putting the crate down on what is beneath it rather
  than letting go of it); ~0.5 h on speed and jump with correct restore in both
  directions; ~1 h on the plate (a SET, a sum, this plate's own threshold, this
  plate's own wired door); ~0.5 h on the slab's travel; and ~1.5 h of integration
  debugging, which is where the task actually lives — four of the five channels
  fail silently on their own.

## Anti-gaming notes

1. **Carry by teleport.** *Failure mode*: `SetActorLocation(HoldPoint)` every
   frame with `bSweep` left at its default `false`, or a rigid attachment. Both
   move the crate by teleport, so pushing into the yard's wall puts it bodily
   inside. *Defense*: `TheCrateStaysOutOfTheWalls`. The arithmetic is done, not
   assumed: the character's capsule (radius 42) stops at the wall face, the hold
   point is 330 cm beyond it, so a teleported 80 cm crate sits 248-328 cm inside
   an 800 cm deep block — 80 cm of overlap on every axis, twice the 40 cm the
   prompt allows. A swept carry stops the crate AT the face and overlaps by 0. The
   gate separates the two by 2x, and the authoring script refuses to save a wall
   too shallow to contain the wrong answer.
2. **A plate keyed to any overlap.** *Failure mode*: the door opens for whatever
   is on the pad. *Defense*: the drive parks the character on the high plate
   empty-handed for 3.5 s with 0 kg resting on it, and the load is a sum over
   crates only — `TheDoorDropsWhenTheWeightComesOff` fires with *"plate 1 is
   holding 0 kg and holds from 55 kg"*. The same clause catches a crate merely
   **carried over** a pad, because "resting" is a height test as well as a
   footprint test.
3. **One threshold for every plate, or a number cached at `BeginPlay`.** *Failure
   mode*: a table, a constant, or the value read off the first plate found.
   *Defense*: two of them. Step 3 of the staged sequence puts 42 kg on a plate
   that holds from 55 while the other holds from 30 — a single number is wrong.
   And the RE-PRICE changes both plates' verdicts **with nothing moving**, so a
   remembered mass or a remembered threshold leaves two doors standing open and
   fails at `TheDoorDropsWhenTheWeightComesOff`. The prompt discloses that the
   numbers change.
4. **A single occupant instead of a set.** *Failure mode*: a `bool`, or one
   `AActor*`; two crates on, one off, and the end-overlap clears the flag.
   *Defense*: step 5 lifts one of two crates off a plate that must **stay open**
   on the 70 kg still resting there. This is the commonest real version of the bug
   and it is caught by a scripted removal, not by a variant.
5. **Begin-overlap with no end, or a door that latches.** *Failure mode*: the
   first haul opens the door and nothing ever shuts it. *Defense*: step 7 empties
   a plate completely (`TheDoorDropsWhenTheWeightComesOff`), and
   `EachDoorLiftsMoreThanOnce` separately requires each door to have reached the
   open band on two distinct occasions with a shut in between.
6. **Driving whichever door is first in the level.** *Failure mode*: the plate
   finds a door rather than reading its own `LinkedDoor`. *Defense*: the per-plate
   iff is evaluated for BOTH plates every frame, so a cross-wire fails from both
   sides at once — the right door shut and the wrong door open.
7. **Doing all the visible mechanism and never touching speed or jumping.**
   *Failure mode*: the plates and doors are perfect and the character walks and
   jumps exactly as before. *Defense*: four separate named gates, each with the
   measured number in its message, and each stated as an **iff** so breaking
   walking or jumping outright fails the other half.
8. **A "set down" that lets go without putting down.** *Failure mode*: a flag is
   cleared and the crate is left where it was — in the air, or still following the
   character. *Defense*: `TheCrateYouPutDownComesToRest` (a crate off the ground
   with nobody near it, and a crate whose underside is more than 12 cm above what
   a downward trace finds) and `TheYardStaysWhereItIsPut` (a set-down crate that
   moves more than 60 cm). A hanging crate additionally never counts as resting on
   any pad, so its door never opens and `EachDoorLiftsMoreThanOnce` refuses.
9. **Holding the crate solid against its own carrier.** *Failure mode*: the crate
   is told to ignore the character but the character's capsule is not told to
   ignore the crate, so the character grinds against the thing it is carrying.
   *Defense*: the per-leg deadline in `TheHaulRanBothRounds`, which names the
   stop, its label and the distance covered — a jam reads as a diagnosis, not as a
   silent timeout.

## Hidden invariants

- **The route, the checkpoint instants and the two price lists are undisclosed.**
  Only the behaviour and its numbers are in the prompt. The route is 48 stops
  built from live transforms, so a solution fitted to guessed sample times has
  dozens of independent chances to miss.
- **The yard is priced by the FIXTURE, twice**, and the second pricing happens
  while the character is standing still with empty hands and every crate at rest.
  Nothing moves; two doors have to change state. This is the only mechanism in the
  task that a hard-coded table of thresholds cannot survive, and it is why the
  prompt says the numbers change.
- **Carried is inferred geometrically** (underside more than 40 cm above the yard
  floor, and within 500 cm of the character), never asked of the submission. There
  is no "am I carrying" call to satisfy and no name to match.
- **The graded part of a door is the component named `Panel`, resolved once in
  `PrepareTest`** — else the largest by local bounds, ties by name. A decorative
  component added later can never become the thing that is measured, and the door
  ACTOR is separately held to its staged transform, so sliding the whole door up
  is not the slab lifting out of its frame.
- **The floor height and the pad half-width are read off the level**, not written
  down, so the yard can be re-authored at a different scale and the fixture
  follows.
- **`ValidateMargins` runs before anything moves** and refuses the whole run if
  any staged comparison clears by less than 8 kg, or if the second price list does
  not change a verdict. A gate that could round either way, or that could never
  fire, ends the run as a HARNESS-PRECONDITION instead of scoring against a model.
- **`ValidateRoute` refuses a route it could grade unfairly**: any leg passing
  within 290 cm of a crate it is not fetching would pick that crate up and
  desynchronise the script, and any leg but the push running into a wall would jam
  the character. Both are attributed to staging, not to the submission.
- **The over-reach clause is a graded FAIL; an ambiguous pick-up is not.** A crate
  that comes off the ground from more than 320 cm away is the submission reaching
  further than the yard's 250 cm; that is a named FAIL. Everything else about a
  mis-staged pick-up is a precondition.
