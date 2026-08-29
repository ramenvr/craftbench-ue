---
id: t1-spikes-hurt-you-and-you-respawn-at-your-marker
substrate: ThirdPerson
set: craftbench-public
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_SpikeLane :: ASpikeContactRespawnFunctionalTest"]
---

# t1-spikes-hurt-you-and-you-respawn-at-your-marker

The whole hurt-die-recover chain as ONE task on the **ThirdPerson substrate**: a
spiked block slides a fixed rail, contact costs health, zero health sends the
character back to the last pad it walked onto, and walking back over an older pad
never rolls that progress backwards. Merged from three Startup-Eval corpus rows
(`t1-moving-hazard-harms-player-on-contact`, `t1-hazard-volume-resets-player-to-start`,
`t2-checkpoint-respawn-run`) on the owner's 2026-08-16 decision — those three rows
test three segments of one mechanic, so they are graded here as one run with
**separately named assertions per segment**, never folded: "damage works but the
respawn target is wrong" and "nothing was built" produce different named failures.
Two channels are deliberately kept apart — the course's exposed current-pad state
and the character's actual post-death transform are read by different checks,
because a submission that tracks its respawn point separately from the state it
exposes passes the first and fails the second, and that divergence is the bug this
task exists to catch. Everything is legible at Play: a floating health number over
each character, a pad that visibly marks itself, and a bystander character whose
number stays at 100 for the entire run.

## Primary concept

- `collision-overview` — Collision Overview
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine---overview)

Every trigger in the task is physical contact between a moving primitive and a
walking character: the block touching a character is what costs health, and a
character walking onto a pad is what makes that pad current. There are no key
presses anywhere in the run. The recovery half hangs a small rules-and-state
machine (`game-mode-and-game-state` territory — which pad is current, where a
dead character comes back) off those contact events, but the verifier's densest
assertions are all contact-caused: exactly 25 per touch, once per touch, none
without a touch, and none at all on the character nothing ever touches.

## Prompt given to the agent

> The level is one long lane on a single solid floor, striped every 200 cm. A
> character stands on a painted start mark near one end; two low pads sit off to one
> side of the lane, one nearer the start mark than the other; further along, a
> spiked slab sits on a rail between two posts. A second character stands beside the
> rail, clear of it, and never moves. Every character begins with 100 health out of
> 100, and a number floating above each character shows its current health. Make the
> course work:
>
> - When play begins the slab starts sliding on its own, back and forth between its
>   two rail posts — 600 cm apart — at a steady 300 cm per second, and it never
>   stops and never changes speed, not even at the moment it hurts somebody. Keep to
>   that speed: the checks are timed off it, with generous margin.
> - When the slab touches a character, that character loses exactly 25 health. One
>   touch costs 25 once, however long the slab stays against the character; the next
>   separate touch costs another 25. Nothing else ever changes a character's health,
>   and a character the slab never touches never loses any.
> - A character whose health reaches 0 is out. Within 1 second it reappears standing
>   on the pad it most recently walked onto, and within a further half second its
>   health reads 100 again. Reappearing "on" a pad means within 120 cm of that pad's
>   centre. Before it has walked onto any pad at all, it reappears on the painted
>   start mark instead.
> - Walking onto a pad makes that pad the current one. The pad nearer the start mark
>   is the first, the one further along is the second. After reaching the second pad,
>   walking back onto the first leaves the second current — progress never rolls
>   backwards. Walking onto the pad that is already current leaves it current.
> - The current pad must look visibly different from the other one, and exactly one
>   pad is marked as current at a time.
> - A character's floating number must always show that character's current health,
>   lagging it by at most one frame. It is read by taking the first run of digits in
>   the text, so "75" and "75/100" both read as 75.
> - After reappearing, a character is free to walk away from its pad — nothing may
>   pull or snap it back.
>
> Write your C++ under `Source/ThirdPerson/` — the project's gameplay module and the
> only place a submission is read from; work written anywhere else is not graded. Do
> not edit the level, any config file, or any test file.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable gameplay module on
this substrate). `Source/CraftBenchTests/`, `Content/Maps/` and `Config/` are
deny-listed — a submission file under any of them is rejected before grading, not
graded as a failure. (The front-matter key `deliverable_root:` is NOT in
`tools/verify-single/spec.py::_KNOWN_KEYS`; adding it raises a hard `ValueError`
and the spec would not parse, so the path is stated here and in the prompt body
instead.)

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources, plus the substrate's
  `ACraftBenchCharacter`. No edit needed.
- `Tasks/t1-spikes-hurt-you-and-you-respawn-at-your-marker/SpikeLaneCharacter.h` /
  `.cpp` — declares and defines
  `class THIRDPERSON_API ASpikeLaneCharacter : public ACraftBenchCharacter`
  (concrete; the stock template character is abstract and unspawnable). The
  constructor: adds `Tags.Add(FName("LaneCharacter"))`; assigns a mannequin
  skeletal mesh from the read-only `/Game/Characters/` pool, so every submission is
  something a reviewer can see; and builds a text component named `HealthReadout`
  parented above the capsule, camera-facing, whose authored text is `100`. It also
  carries `UPROPERTY(BlueprintReadWrite) float Health = 100.f;` and
  `UPROPERTY(BlueprintReadWrite) float MaxHealth = 100.f;` — these are the values
  the floating number is supposed to show and the values the grade reads.
  **No damage, no death, no respawn, and no readout updating ship.**
- `Tasks/t1-spikes-hurt-you-and-you-respawn-at-your-marker/SpikeSlabActor.h` /
  `.cpp` — `class THIRDPERSON_API ASpikeSlabActor : public AActor`, constructor adds
  `Tags.Add(FName("SlidingSpikes"))` and builds a movable spiked-slab static mesh
  root, 240 x 240 x 200 cm, with query-only overlap-all collision so it can never
  push or block anybody. **No motion and no damage ship.**
- `Tasks/t1-spikes-hurt-you-and-you-respawn-at-your-marker/LanePadActor.h` / `.cpp`
  — `class THIRDPERSON_API ALanePadActor : public AActor`, constructor adds
  `Tags.Add(FName("LanePad"))`, a flat 200 x 200 cm pad mesh sitting on the floor
  and a query-only 200 x 200 x 220 cm box over it. It carries
  `UPROPERTY(EditAnywhere) int32 PadOrder = 0;` (authored `1` and `2` on the two
  placed pads — read it, do not rewrite it),
  `UPROPERTY(BlueprintReadWrite) bool bMarkedCurrent = false;` and a supplied
  `void SetMarkedCurrent(bool bInMarked)` that flips the flag AND swaps the pad
  mesh between the supplied dark and bright materials in one call, so the visible
  state and the readable flag cannot disagree. **Nothing calls it.**
- `Tasks/t1-spikes-hurt-you-and-you-respawn-at-your-marker/SpikeLaneCourse.h` /
  `.cpp` — `class THIRDPERSON_API ASpikeLaneCourse : public AActor`, constructor
  adds `Tags.Add(FName("SpikeLane"))` and carries the readable state shell
  `UPROPERTY(BlueprintReadWrite) int32 CurrentPadOrder = 0;` (`0` means "no pad yet
  — the painted start mark"). **No logic ships**; keeping this value truthful is
  part of the work.
- `Tasks/t1-spikes-hurt-you-and-you-respawn-at-your-marker/SpikeLaneGameMode.h` /
  `.cpp` — a game mode whose constructor sets
  `DefaultPawnClass = ASpikeLaneCharacter::StaticClass()`. The map's world
  settings select it, so play begins with one lane character spawned and possessed
  on the start mark — the same character a human drives with WASD and the same one
  the verifier drives.

The staged scene, `Content/Maps/t1-spikes-hurt-you-and-you-respawn-at-your-marker/L_SpikeLane.umap`
(committed binary; the agent does not author maps):

- One solid floor platform, 3200 x 1400 cm, top face at Z = 0, spanning X 0 → 3200
  and Y -700 → +700, with stripe markings across the lane every 200 cm of X (16
  stripes) so distance and speed read by eye. **The whole course — start mark, both
  pads, the entire rail, and both characters' feet — sits on this one platform;
  nothing in the run can fall out of the world.**
- The painted start mark: a 200 x 200 cm square centred at (300, 0), tagged
  `StartMark`, with the PlayerStart on it facing +X (down the lane, toward the
  slab).
- Pad 1: `ALanePadActor`, `PadOrder = 1`, centred (1100, -300). Pad 2: `PadOrder = 2`,
  centred (1900, -300). Both are off the lane's centre line by 300 cm, so walking
  straight down the middle of the lane touches neither — that is what makes "die
  before touching any pad" reachable at all.
- The slab: `ASpikeSlabActor` placed at (2400, 0, 100), between two visible rail
  posts at (2400, 0) and (3000, 0) — 600 cm apart, tagged `RailPost`. Its swept
  corridor is X 2280 → 3120, Y -120 → +120.
- The bystander: a second `ASpikeLaneCharacter` placed at (2700, 200, 96) facing
  +X, carrying the extra per-instance actor tag `ControlTwin` (authored on the
  placed instance in the map, never in a constructor, so the two characters are the
  same class and are told apart by placement alone). Its capsule stands 46 cm clear
  of the slab's swept corridor and 200 cm from where the driven character stops in
  front of the slab, so both are in one frame with the slab between passes.
- Two distinct tall backdrop landmarks at (100, 650) and (3100, 650), so a moving
  camera is distinguishable from a still one in any capture.
- One placed `ASpikeContactRespawnFunctionalTest`.
- `cameras.json` (the camera-plan lane; not part of this release) beside this spec (presentation-only, non-gating) frames the driven
  character, the bystander and at least four stripes.

Files that **do not exist**:

- No slab motion, no damage, no death, no respawn, no pad activation, no state
  update, no readout updating, and no Blueprint subclass. The empty submission
  compiles (L1 green) and fails L2 at the first named segment gate.
- No test source in the agent's writable path. `ASpikeContactRespawnFunctionalTest`
  lives in the separate `CraftBenchTests` module the agent can neither read nor
  modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t1-spikes-hurt-you-and-you-respawn-at-your-marker/L_SpikeLane.umap`
on the **ThirdPerson** substrate, at a fixed deterministic step
(`-deterministic -FPS=60`). The map's world settings select `ASpikeLaneGameMode`,
which spawns and possesses the `LaneCharacter`-tagged driven character on the start
mark.

**Verification primitive**: `pie-state-probe` (in-fixture, engine-owned state read
after tag-resolve — `GetActorLocation`, component bounds, and reflection reads of
the supplied `Health` / `CurrentPadOrder` / `bMarkedCurrent` / `PadOrder` surfaces),
gauged on a `pie-checkpoint-sampling` grid, with the driven character moved by the
shipped per-frame `AddMovementInput` timeline (the same pattern as
`Tasks/t1-overlap-teleport-portal/TeleportPortalFunctionalTest.cpp:194`,
`Tasks/t2-ladder-climb-volume/LadderClimbFunctionalTest.cpp:246` and
`Tasks/t2-npc-follows-player/NpcFollowFunctionalTest.cpp:144`). **Contact is
computed geometrically by the fixture, never taken from the submission's own
overlap plumbing**: the fixture builds the slab's world bounding box, expands it by
the character capsule's radius in X/Y and half-height in Z, and treats a character
as touching while its capsule centre is inside. A submission cannot make itself look
contacted, and a submission that detects contact by any other legitimate means still
grades identically.

**The control subject is spawned-into-life by this fixture's own local helper, and
that duplication is deliberate and owner-approved (2026-08-16).**
`ACraftBenchPawnFunctionalTest::SpawnAndPossessPawn()` handles exactly one pawn and
has no API for a second subject; adding one is the other machine's change. So this
fixture derives from `ACraftBenchFunctionalTest` (the house pattern for every
ThirdPerson gameplay fixture) and declares its own local control helper that
resolves the map-placed `ControlTwin` character and `SpawnDefaultController()`s it —
possessed on purpose, because an unpossessed Character is inert (the Slice-0 spike),
and an inert bystander would prove nothing about staying put. **Do not go looking
for a shared helper; there is none, and each task in this set carries its own.**

Every FAIL message is ASCII-only (the cp1252 log read-back rule) and each carries
the segment-named substring in the table below, so a partial implementation is
diagnosable from the verdict line alone.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

```text
ASpikeContactRespawnFunctionalTest (derives ACraftBenchFunctionalTest):

  PrepareTest():
      Super::PrepareTest()                      // base: FApp globals + fixed dt
      resolve by tag, never by class:
          "SpikeLane" x1, "SlidingSpikes" x1, "StartMark" x1,
          "RailPost" x2, "LanePad" x2 with PadOrder {1,2},
          "LaneCharacter" x2 of which exactly one also has "ControlTwin"
          -> the other is the DRIVEN character
      local control helper: SpawnDefaultController() on the placed twin
      reflection-resolve the supplied readable surfaces on both characters and on
          the course + pads; assert both characters read Health == 100 at t0
      record the slab's authored location, the rail segment (post to post), the
          start mark, both pad centres, and the twin's placement
      SetCheckpointSchedule({2, 6, 10, ... 66})  // 17 gauging instants, 4s apart

  Tick (every frame, after the base checkpoint clock):
      re-resolve driven + twin (identity may change: a destroy-and-respawn
          implementation is legal, so the driven character is "the LaneCharacter
          that is not the ControlTwin", re-resolved every frame)
      sample: slab location; driven location + Health + readout text;
              twin location + Health + readout text; CurrentPadOrder;
              both pads' bMarkedCurrent
      geometric contact test (slab box expanded by the capsule) for BOTH
          characters; maintain the current contact window
      per-tick gates: rail band, health-only-on-contact, one-25-per-window,
          twin pinned at 100 and unmoved, roll-back never observed after the
          walk-back
      waypoint drive (re-applied every tick; the drive self-advances on arrival
          within 60cm, and each phase carries a >=2x-margin deadline off the
          disclosed 300 cm/s slab speed):
        EVERY leg returns to the LANE CENTRE LINE (Y = 0) before travelling in
        X, and every freedom probe is driven in +X. Both rules exist to stop the
        DRIVE from manufacturing a FAIL:
          - a straight line from pad 1 (1100,-300) to the hold point (2700, 0)
            passes 30.7 cm from the corner (1800,-200) of pad 2's box
            (PadOrder 2 at (1900,-300), box 200x200x220 -> X 1800..2000,
            Y -400..-200). The character's capsule radius is 34 cm
            (`ACraftBenchCharacter` derives `ACharacter`, not
            `AThirdPersonCharacter`, so it keeps the default — the same 34 the
            bystander's "46 cm clear" figure is computed from). 34 > 30.7, so
            that leg would clip pad 2's volume mid-flight, a COMPLIANT
            submission would set CurrentPadOrder = 2, and
            `DeathAfterTheFirstPadReturnsThere` would FAIL correct work. Routing
            via (1100, 0) keeps the whole leg >= 200 cm clear of pad 2's box.
          - the freedom probe direction is +X, never -X: respawn #1 is the start
            mark at (300, 0) and the platform begins at X = 0, so a 400 cm probe
            in -X would leave the world at X = -100 and contradict the staging
            promise that nothing in the run can fall out of the world.
        L1: start mark -> hold point (2700, 0) in front of the slab; stand and
            take passes until Health hits 0  -> respawn #1 expected: start mark
        F1: driven 400cm in +X off the respawn point, hold 1.0s (freedom probe)
        L2: -> (1100, 0) -> pad 1 (1100,-300) -> back to (1100, 0)
            -> hold point -> die   -> respawn #2: pad 1
        F2: freedom probe (+X, 400 cm)
        L3: -> (1100, 0) -> (1900, 0) -> pad 2 (1900,-300) -> back to (1900, 0)
            -> (1100, 0) -> BACK onto pad 1 (1100,-300) -> back to (1100, 0)
            -> hold point -> die
            -> respawn #3 expected: pad 2, NOT pad 1
        F3: freedom probe (+X, 400 cm), then walk back onto pad 2 once more via
            (1900, 0) (the second firing of that trigger)
            -> FinishTest(Succeeded)

  OnCheckpoint(i, t):
      gauge the twin (Health == 100, location within 20cm of placement) and the
      readout-vs-Health agreement on both characters at EVERY checkpoint
      log "[t1-spikes calib] cp<i> t=<t> hp=<h> pad=<p> drivenXY=<x,y> slabX=<s>
           twinHp=<th> twinD=<d>"  (LogTemp/Display) for calibration
```

Named assertions. Each row is an independent requirement with its own ASCII FAIL
substring; the fixture reports the first one that trips, and the substring names the
segment, so a submission that gets the damage right and the respawn target wrong is
never confused with one that built nothing.

| Segment | Named check | ASCII substring in the FAIL message | Graded |
|---|---|---|---|
| staging | `CourseStagedAsAuthored` | `contact-lane course is not staged as authored` | precondition |
| staging | `BothCharactersVisiblyRepresented` | `the driven character is not visibly represented` / `the bystander character is not visibly represented` — **two literals, one per subject** | precondition |
| staging | `ReadableSurfacesIntact` | `readable course surface is missing` | precondition |
| staging | `CharactersStayResolvable` | `graded character could no longer be resolved` | yes |
| slab | `SpikesMoveOnTheirOwn` | `the spiked slab never moved on its own` | yes |
| slab | `SpikesStayOnTheirRail` | `the spiked slab left its rail` | yes |
| slab | `SpikesKeepSlidingAfterContact` | `the spiked slab stopped sliding after it hurt someone` | yes |
| damage | `HealthFullUntilFirstContact` | `lost health before the slab ever touched it` | yes |
| damage | `FirstContactCostsExactly25` | `first touch of the slab did not cost exactly 25` | yes |
| damage | `OneDeductionPerContact` | `a single touch of the slab cost more than one 25` | yes |
| damage | `SecondContactCostsAnother25` | `second touch of the slab did not cost another 25` | yes |
| damage | `HealthOnlyChangesOnContact` | `lost health while nothing was touching it` | yes |
| control | `BystanderHealthStaysFull` | `bystander character lost health without ever being touched` | yes |
| control | `BystanderNeverMoves` | `bystander character moved from where it was placed` | yes |
| death | `ZeroHealthSendsYouBack` | `reached zero health and was never sent back` | yes |
| death | `HealthIsFullAgainAfterRespawn` | `came back with the wrong amount of health` | yes |
| death | `DeathBeforeAnyPadReturnsToTheStart` | `first death did not return the character to the start mark` | yes |
| death | `FreeToWalkAwayAfterRespawn` | `character kept being pulled back to its pad` | yes |
| pad state | `TouchingTheFirstPadMakesItCurrent` | `walking onto the first pad did not make it current` | yes |
| pad state | `TheSecondPadTakesOver` | `walking onto the second pad did not take over from the first` | yes |
| pad state | `WalkingBackDoesNotRollBack` | `walking back onto the earlier pad rolled the current pad backwards` | yes |
| pad state | `TouchingTheCurrentPadAgainKeepsIt` | `walking onto the current pad again did not leave it current` | yes |
| pad state | `TheCurrentPadIsTheMarkedOne` | `the marked pad is not the one the course says is current` | yes |
| respawn spot | `DeathAfterTheFirstPadReturnsThere` | `death after the first pad did not return the character there` | yes |
| respawn spot | `DeathAfterTheWalkBackReturnsToTheSecondPad` | `death after walking back did not return the character to the second pad` | yes |
| legibility | `TheFloatingNumberMatchesTheHealth` | `number floating over the driven character does not match its health` / `number floating over the bystander character does not match its health` — **two literals, one per subject** | yes |
| drive | `DriveReachedItsWaypoints` | `a drive phase ran out of time before reaching its waypoint` | yes |

The two rows that must never be folded are `WalkingBackDoesNotRollBack` (reads the
course's exposed `CurrentPadOrder`) and `DeathAfterTheWalkBackReturnsToTheSecondPad`
(reads where the character actually came back to). A submission that keeps its
respawn point in a second, separately-updated place passes the first and fails the
second, and only reading them apart tells you so.

**`DriveReachedItsWaypoints` exists because the base class's time limit is
anonymous.** `SetCheckpointSchedule` also sets `AFunctionalTest::TimeLimit`, so a
stall reports UE's own generic time-limit line — under which a submission that pins
or blocks the character, a harness stall, and an editor hitch are
indistinguishable. Each drive phase therefore carries its own deadline (>= 2x the
margin computed off the disclosed 300 cm/s slab speed and the stock walk speed) and
its own ASCII substring naming the phase. Anti-gaming note 3 leans on exactly this
("the walk legs themselves also cannot complete if something keeps snapping the
character home") and had no row to lean on until now.

**Which graded rows can only trip if their precondition was reached, and how the
fixture keeps them honest.** `OneDeductionPerContact`, `SecondContactCostsAnother25`,
`TouchingTheCurrentPadAgainKeepsIt`, `SpikesKeepSlidingAfterContact`,
`WalkingBackDoesNotRollBack`, `TheSecondPadTakesOver`,
`DeathAfterTheFirstPadReturnsThere` and
`DeathAfterTheWalkBackReturnsToTheSecondPad` are all **vacuously true if their leg
never happened**. Each therefore carries an explicit *precondition-reached* assert
alongside it, with its own substring, evaluated at the checkpoint that closes the
leg:

| Row | Precondition-reached assert | Substring when the precondition was never met |
|---|---|---|
| `OneDeductionPerContact` | at least one contact window opened and closed | `no contact window ever opened, so per-touch cost was never measured` |
| `SecondContactCostsAnother25` | at least two separate contact windows | `the slab only ever touched the character once` |
| `SpikesKeepSlidingAfterContact` | a contact window opened | (shares the row above's precondition substring) |
| `TouchingTheCurrentPadAgainKeepsIt` | the current pad was entered a second time | `the character never walked back onto the pad that was already current` |
| `TheSecondPadTakesOver` / `WalkingBackDoesNotRollBack` | pad 2 was entered after pad 1 | `the character never reached the second pad` |
| `DeathAfterTheFirstPadReturnsThere` | a death occurred after pad 1 became current | `the character never died after reaching a pad` |
| `DeathAfterTheWalkBackReturnsToTheSecondPad` | a death occurred after the walk-back | `the character never died after walking back` |

A partial submission therefore cannot bank these rows silently: the precondition
assert fires with its own message and the verdict says *why* the row was
unmeasurable. `CharactersStayResolvable` stays a pure negative that an empty
submission also passes — that one is an anti-tamper guard, banks nothing (the L2
verdict is all-or-nothing), and the empty submission still dies on
`SpikesMoveOnTheirOwn` / `FirstContactCostsExactly25` /
`DeathBeforeAnyPadReturnsToTheStart`.

**Tolerances.** Disclosed in the prompt: 25 per touch; health 100 at start and after
each respawn; 120 cm around a pad centre or the start mark for "came back on it";
relocation within 1.0 s of health reaching 0 and health restored within a further
0.5 s; the readout may lag the value by one frame; the 300 cm/s slab speed; the
600 cm rail; the pads' 200 x 200 cm footprint. **Verifier-side and NOT disclosed**,
each of which can only ever be more permissive than the sentence it implements, so
none can FAIL a submission that satisfies the prompt: the `+/- 0.01` float epsilon
around the disclosed exact 25; the 60 cm rail band; 20 cm on the bystander's
placement; 400 cm of displacement to count as a relocation; 300 cm still-clear at
the end of a freedom probe; the 17 checkpoint instants and the waypoint route; and
the 34 cm capsule radius the geometric contact test expands the slab box by. (An
earlier draft claimed all tolerances including the `0.01` were "all disclosed in the
prompt" — the epsilon never was.)

**Pass criteria**: L1 green on both targets and every graded row above holding.
**Robust identity**: every subject is resolved by tag and re-resolved every frame,
so subclassing, renaming, or destroying-and-respawning the character all grade
identically; the supplied readable surfaces are resolved by reflection, so a missing
one is a named FAIL rather than a build break.

## Reference solution metadata

- LOC range: 150-260 net new lines (slab motion ~25; contact damage with a
  per-contact latch ~40; death, relocation and restore ~45; pad activation,
  ordered progression and the marked-pad visual ~50; readout sync ~15).
- Files touched: 6-9, all pre-existing scaffold files under
  `Source/ThirdPerson/Tasks/t1-spikes-hurt-you-and-you-respawn-at-your-marker/`
  (`SpikeLaneCharacter.{h,cpp}`, `SpikeSlabActor.{h,cpp}`,
  `SpikeLaneCourse.{h,cpp}`, and optionally `LanePadActor.{h,cpp}` and the game
  mode). No new files are required; no asset or level edits are permitted.
- Senior-dev hours: 2.0-3.5.

## Anti-gaming notes

1. **Empty or one-segment submission.** *Failure mode*: the scaffold compiles with
   no motion, no damage and no recovery, so L1 is green. *Defense*: FAIL-on-empty,
   not differs-from-reference — `SpikesMoveOnTheirOwn` trips first with its own
   substring, and each later segment has its own, so a submission that builds the
   damage and skips the recovery reports
   `first death did not return the character to the start mark`, never the
   empty-submission line.
2. **Damage-cadence cheats.** *Failure modes*: draining a little every frame while
   in contact; a one-shot latch that fires once and never again; damaging every
   character whenever the slab moves. *Defense*: four independent named rows —
   `FirstContactCostsExactly25` (exact 100 -> 75), `OneDeductionPerContact`
   (per-tick arithmetic over each maximal contact window, so a per-frame drainer
   that happens to land on 75 at a gauging instant still fails), 
   `SecondContactCostsAnother25` (the latch dies here), and
   `BystanderHealthStaysFull` on a character whose capsule stands 46 cm outside the
   swept corridor — which is a whole serial no-contact leg replaced by one in-frame
   control, gauged every tick and at all 17 checkpoints.
3. **Respawn faked by pinning.** *Failure mode*: continuously teleporting the
   character onto the current pad, which satisfies every "came back on the pad"
   read without any death logic at all. *Defense*: `FreeToWalkAwayAfterRespawn`
   drives the character 400 cm off each respawn point at undisclosed instants and
   requires it to still be 300 cm clear a second later; the walk legs themselves
   also cannot complete if something keeps snapping the character home, and
   `HealthFullUntilFirstContact` refuses any state change before the first contact.
4. **Progress tracked twice, or re-armed on the most recent touch.** *Failure
   modes*: exposing a current-pad value while respawning from a separately-tracked
   variable; treating the newest overlap as the respawn point so walking back over
   pad 1 rolls progress backwards. *Defense*: the state read
   (`WalkingBackDoesNotRollBack`, on the course's exposed value, asserted on every
   tick from the walk-back to the end of the run) and the transform read
   (`DeathAfterTheWalkBackReturnsToTheSecondPad`) are separate rows, plus
   `TheCurrentPadIsTheMarkedOne` ties the visible mark to the same value so a lying
   display is caught too. The walk-back leg is what makes re-arming visible; without
   it, both implementations look identical.
5. **Test disabling or environment repointing.** *Failure mode*: editing the
   fixture, the map, or config to weaken the gate. *Defense*:
   `Source/CraftBenchTests/` is sandbox-denied (a submission file under it is
   rejected pre-grade, exit 4), the runner materializes the graded substrate from
   git HEAD so an on-disk edit never reaches the grade and a committed one is
   review-gated on commit, and `Config/` + `Content/Maps/` are deny-listed. The
   fixture also computes contact itself instead of trusting the submission's overlap
   events, so there is no reporting channel to spoof.

## Hidden invariants

- **No checkpoint instant, phase deadline or freedom-probe instant is disclosed.**
  The prompt carries every number the grade compares against (25, 100, 600 cm,
  300 cm/s, 1 s, 0.5 s, 120 cm, one frame) and none of the times at which it looks.
  A point-fit solution keyed to guessed sample times has 17 checkpoints and a
  per-tick observer to miss.
- **The damage and control gates run EVERY TICK, not only at checkpoints.**
  `HealthOnlyChangesOnContact`, `OneDeductionPerContact`, `SpikesStayOnTheirRail`
  and the bystander's pinned health are evaluated on the whole sample series, so a
  submission that is only correct at the gauging grid fails.
- **The third respawn target is the discriminating one.** Legs 1 and 2 (start mark,
  then pad 1) are satisfied by "respawn at the most recently touched pad". Only leg
  3 — pad 2, then back over pad 1, then die — separates that from "respawn at the
  furthest pad reached", and the prompt states the rule without announcing that a
  leg tests it.
- **Identity is re-resolved every frame.** A submission that destroys and respawns
  the character is graded identically to one that relocates it, so neither route is
  rewarded or punished; but a submission that destroys the bystander, or leaves two
  driven characters in the world, trips `CharactersStayResolvable` by name instead
  of silently grading whichever actor the fixture happened to hold.
