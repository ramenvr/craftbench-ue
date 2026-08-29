---
id: t1-door-stays-open-while-you-stand-on-the-plate
substrate: ThirdPerson
set: craftbench-public
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_PlateDoorLane :: APlateDoorFunctionalTest"]
fps_legs: [60, 20]
---

# t1-door-stays-open-while-you-stand-on-the-plate

Occupancy-tracked door on the **ThirdPerson substrate**: the character walks
onto a pressure plate, the plate's door swings open and stays open while he
stands there, and it swings shut again when he walks off — twice in one run.
Imported from the Startup Eval corpus row
`t1-plate-opens-door-while-occupied` (owner verdict: agree); provenance and
every deviation are in `notes.md`. The scene is staged as a showroom: a
stripe-marked lane, the graded plate-and-door pair, and an **identical control
pair 300 cm away that nobody ever steps on**, both in one camera frame, so a
human watching Play sees the same thing the gate measures.

## Primary concept

- `collision-overview` — Collision Overview
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine---overview)

The load-bearing behavior is a **continuous** occupancy state read off contact
with a placed volume — enter and leave edges (or an equivalent poll) driving a
reversible motion that must hold for as long as the contact holds, and must
address only the one door the occupied plate belongs to. Anything one-shot,
anything level-wide, and anything that snaps instead of travelling fails.

## Prompt given to the agent

> The deliverable is C++ source under `Source/ThirdPerson/` (the writable
> gameplay module on this project).
>
> The level holds two identical pressure plates, each with its own door
> standing 300 cm behind it; the two plate-and-door pairs stand 300 cm apart.
> Each plate already carries a reference to the door it belongs to (the
> plate's `LinkedDoor` field, set on each placed plate). Both doors start shut
> when play begins.
>
> While a character is standing on a plate, that plate's door must be open,
> and the rest of the time it must be shut. Precisely:
>
> - shut is the door's authored pose; open means the door's panel — the part a
>   person sees swing — turned 90 degrees about the vertical axis from that
>   pose (either direction), and it must be at least 80 degrees from shut
>   within 2 seconds of a character stepping onto the plate. It is the panel
>   itself that has to move: the part that is judged is the largest visible
>   piece of the door, and both its facing and its position have to travel;
> - each plate is a 200 x 200 cm pad, and "standing on it" means being within
>   100 cm of its centre with both feet on the ground;
> - it stays open for as long as anyone keeps standing there;
> - within 2 seconds of the last character stepping off, the door is back
>   within 10 degrees of shut;
> - the door travels: it must never move faster than 720 degrees per second or
>   3000 cm per second, in either direction;
> - the cycle works every time, not once: the second time a character stands
>   on the plate, the door must reach the same open position as the first,
>   within 10 degrees;
> - a plate moves only its own door. Nothing that happens on one plate may
>   move the other pair's door, which must stay within 10 degrees of shut for
>   the whole run.
>
> All times are wall-clock seconds and must hold whatever the frame rate. Do
> not edit the level, any config file, or any test file.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** — the agent-writable module on
this substrate. Never `Source/CraftBenchTemplate/`, which is a sandbox
REJECT (exit 4, not a graded FAIL), and never `Source/CraftBenchTests/`,
`Config/` or `Content/Maps/`, all deny-listed. (The front-matter key
`deliverable_root:` is **not** in `spec.py::_KNOWN_KEYS` — adding it raises
`ValueError` and exits 2 "spec malformed" — so the path is stated here and in
the prompt body instead, per `tasks/README.md`.)

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources (`ThirdPersonCharacter`
  and friends). No edit needed.
- `Tasks/t1-door-stays-open-while-you-stand-on-the-plate/ContactPlateActor.h`
  / `.cpp` — declares and defines
  `class THIRDPERSON_API AContactPlateActor : public AActor`. The constructor
  builds a 200x200 cm pad mesh, a query-only 200x200x60 cm box volume
  ("PlateVolume", root, overlap events enabled, Overlap response to all
  channels), a lamp mesh, and an instance-editable `TObjectPtr<AActor>
  LinkedDoor`; it adds `Tags.Add(FName("ContactPlate"))`. **No overlap
  handling and no door logic ship.** Its Tick drives ONLY the presentation
  lamp (lit while a body is inside its own volume) — an ungraded readout.
- `Tasks/t1-door-stays-open-while-you-stand-on-the-plate/SwingDoorActor.h` /
  `.cpp` — declares and defines
  `class THIRDPERSON_API ASwingDoorActor : public AActor`: a scene root at
  the hinge, a `DoorPanel` static mesh offset so it sweeps about that root
  (clear of the walking lane), and a floating text component above the panel
  that prints the panel's current angle from its own play-start pose every
  frame — an ungraded readout, derived from the measured pose, so it cannot
  disagree with the gate. Constructor adds `Tags.Add(FName("SwingDoor"))`.
  **No motion logic ships.**
- `Tasks/t1-door-stays-open-while-you-stand-on-the-plate/PlateHeroCharacter.h`
  / `.cpp` — a concrete `AThirdPersonCharacter` subclass whose constructor
  assigns a mannequin skeletal mesh + anim blueprint from the read-only
  `/Game/Characters/Mannequins/` pool (a meshless pawn grades clean and is
  invisible to a reviewer) and adds `Tags.Add(FName("PlateHero"))`. No task
  behavior.
- `Tasks/t1-door-stays-open-while-you-stand-on-the-plate/PlateDoorGameMode.h`
  / `.cpp` — a game mode whose constructor sets
  `DefaultPawnClass = APlateHeroCharacter::StaticClass()`. The task map's
  world settings select it, so PIE spawns and possesses the tagged character
  at the PlayerStart.

Content that **exists** (committed binary, deny-listed for writing):

- `Content/Maps/t1-door-stays-open-while-you-stand-on-the-plate/L_PlateDoorLane.umap`
  — the staged showroom:
  - a 3000 x 1600 cm floor with stripe markings every 200 cm along the
    walking lane, so speed and distance read by eye;
  - a PlayerStart **on** that floor at about (-600, -150), off the world
    origin, facing +X at the graded pair;
  - the **graded** pair: one `AContactPlateActor` at (0, -150) carrying the
    instance tag `GradedPlate`, its `LinkedDoor` pointing at the
    `ASwingDoorActor` at (300, -150) tagged `GradedDoor`;
  - the **control twin** pair: an identical `AContactPlateActor` at
    (0, +150) tagged `ControlPlate`, its `LinkedDoor` pointing at the
    `ASwingDoorActor` at (300, +150) tagged `ControlDoor` — 300 cm from the
    graded pair, both pairs inside one camera frame, and nobody ever steps
    on it;
  - two distinct landmark pylons at the +X and -X ends of the backdrop, so a
    moving camera is distinguishable from a still one;
  - one placed `APlateDoorFunctionalTest`.

`cameras.json` (the camera-plan lane; not part of this release) is **not** content and is **not** committed yet — it lives beside
this spec in the task folder (`cameras.json`), not
under `Content/`, and is item 4 of `notes.md`'s still-to-build list. When it
lands it frames both pairs plus at least four stripes. Presentation only — the
camera plan and the `--capture` stills are advisory and never reach a verdict.

Files that **do not exist**:

- No overlap handler, no occupancy state, no door motion, no Blueprint
  subclass, no level edit. The empty submission compiles (L1 green) and FAILs
  L2 at the first open gate. Solve in C++ on the existing classes — the
  placed instances are of those classes and the level is not editable, so
  additional classes and components are free but the behavior has to land
  where the placed actors can reach it.
- No test source in the agent's writable path. `APlateDoorFunctionalTest`
  lives in `Source/CraftBenchTests/Tasks/t1-door-stays-open-while-you-stand-on-the-plate/`,
  a module the agent can neither read nor modify.

## Verifier specification

**Verification primitive**: `pie-checkpoint-sampling` (the base class's
checkpoint clock owns the schedule) for the state gates, over an in-fixture
`pie-state-probe` transform read of both doors, plus a per-tick continuity
guard in a `Tick` override (`Super::Tick` first) and `timer-framerate-legs`
via the front matter's `fps_legs: [60, 20]`. No new verifier mechanism.

The test runs in PIE from
`Content/Maps/t1-door-stays-open-while-you-stand-on-the-plate/L_PlateDoorLane.umap`
under `-deterministic -FPS=<rate> -nullrhi`. The map's world settings select
`APlateDoorGameMode`, which spawns and possesses the `PlateHero`-tagged
mannequin at the PlayerStart; the fixture drives that body with the shipping
per-frame `AddMovementInput` timeline (the idiom at
`Tasks/t1-overlap-teleport-portal/TeleportPortalFunctionalTest.cpp:194`,
`Tasks/t2-ladder-climb-volume/LadderClimbFunctionalTest.cpp:246`,
`Tasks/t2-npc-follows-player/NpcFollowFunctionalTest.cpp:144`), so a human
driving the same route with WASD produces the same observable.

**On the control subject and the base classes.** `ACraftBenchFunctionalTest`
and `ACraftBenchPawnFunctionalTest` are owned by the other machine and MUST
NOT be edited; the pawn base spawns and possesses exactly ONE pawn
(`SpawnAndPossessPawn()`) and has no API for a second subject. This fixture
therefore derives from `ACraftBenchFunctionalTest` (not the pawn base): the
graded body comes from the map's game mode, and the CONTROL is a placed
plate-and-door pair, so no second-pawn spawner is needed here. If a later
revision does need a second body, it declares its **own local spawner in this
fixture** — that duplication is owner-approved. Do not go looking for a
shared helper; there isn't one.

**Occupancy is judged by the fixture, from geometry.** "Standing on the
plate" means the character's own measured 2D distance to the plate centre is
<= 100 cm (the pad is 200x200 cm) and it is not falling. It is never read
from any state the submission owns and never from a component the submission
could remove or disable — both halves of a check must not be
submission-owned.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
        (short-circuits on the first failure)
```

The natural submission is C++, so L1 is a precondition, never a correctness
signal.

### L2 — AFunctionalTest behavioral trace

```text
APlateDoorFunctionalTest (derives ACraftBenchFunctionalTest):

    PrepareTest():
        Super::PrepareTest()                       // fixed dt + globals snapshot
        resolve the hero via GetAllActorsWithTag("PlateHero"); assert exactly
          one and that it is a walking character-type pawn
        resolve GradedPlate / GradedDoor / ControlPlate / ControlDoor by
          instance tag, exactly one each; assert exactly two "ContactPlate"
          and two "SwingDoor" actors exist (identity by TAG, never by class)
        PANEL RESOLUTION, once, in PrepareTest — the graded part of each door is
          ONE component, not the max over all of them:
            Panel(Door) = the door's static-mesh component named "DoorPanel" if
              present, else the static-mesh component with the largest local
              bounding-box volume; ties broken by component name, ascending.
            assert Panel(Door) resolves for both doors
              -> "the door has no visible panel to swing"
          [WHY this is not `max over all static-mesh components`: the agent owns
           SwingDoorActor.{h,cpp}, so under a max-rule it could add a decorative
           mesh component, rotate THAT smoothly 90 deg and back, and satisfy
           every angle gate and the continuity guard while the panel a human
           watches never moves. A max over parts is a gate on "something on this
           actor turned", which is not the observable. Named-then-largest is the
           same `ResolveAgentPawnClass` idiom the substrate already uses: prefer
           the declared thing, fall back to a deterministic rule, never to
           enumeration order.]
        record each door's CLOSED POSE: Panel(Door)'s world rotation and world
          location as of PrepareTest, plus the same for every other static-mesh
          component (used only by the continuity guard, which is fail-only)
        SetCheckpointSchedule({0.8, 4.8, 6.4, 9.4, 13.1, 14.7, 17.7})
        Phase = Settle

    Angle(Door)  = |FindDeltaAngleDegrees(closedYaw, worldYaw)| of Panel(Door)
                   // YAW, i.e. about the vertical axis — disclosed in the prompt
    Travel(Door) = dist3D(Panel(Door) world location,
                          Panel(Door) recorded closed world location)
    OnPlate(P)   = dist2D(hero, P) <= 100 && !hero.IsFalling()
                   // 100 cm and the 200x200 pad are BOTH disclosed in the prompt

    Tick(dt):
        // CONTINUOUS continuity guard: armed for the WHOLE run, on BOTH
        // doors, evaluated BEFORE the base clock so the frame that crosses
        // the last checkpoint is still covered.
        // SEEDING, load-bearing: on the FIRST tick the guard only RECORDS
        // LastAngle/LastLoc from the current sample and returns. Zero-
        // initialised baselines would give |Loc - LastLoc| = |(300, +/-150)|
        // = 335 cm on frame 1 — over 3000*dt at any framerate (50 cm at
        // 60 fps, 150 cm at 20 fps) — and FAIL every submission, including the
        // reference, on the first frame. The baseline is the previous SAMPLE,
        // never a default-constructed value.
        for Door in {GradedDoor, ControlDoor}:
            if first tick: LastAngle/LastLoc := current; continue
            if |Angle - LastAngle| > 720*dt or |Loc - LastLoc| > 3000*dt:
                FAIL "swing smoothly"     // 12 deg / 50 cm per frame at 60 fps
        Super::Tick(dt)                   // base runs the checkpoint clock
        if !IsRunning(): return
        // the walk drive: movement input is consumed per frame, so it is
        // re-applied every tick (and the world is NEVER ticked here)
        if Phase in {Approach1, Approach2}:
            if dist2D(hero, GradedPlate) <= 100: Phase = Stand   // stop driving;
                // braking settles the hero on the 200x200 pad
            else: hero->AddMovementInput(toward the plate centre, 1.0)
        if Phase in {Depart1, Depart2}:
            if dist2D(hero, GradedPlate) >= 400: Phase = Away    // stop driving
            else: hero->AddMovementInput(-X, away from the plate, 1.0)

    OnCheckpoint(i, t):
        log "[t1-plate-door calib] cp<i> t=<t> graded=<deg> control=<deg>
             heroDist=<cm> onPlate=<0|1> phase=<n>"   (LogTemp/Display)

        EVERY checkpoint — the control gauge, 7 of 7. ONE literal per checkpoint,
        suffixed with the checkpoint index, so "the control broke while the
        graded door was open" and "the control was already broken at play start"
        are different strings:
            assert Angle(ControlDoor) <= 10
                -> "the untouched door to stay shut at cp<i>"
            assert !OnPlate(ControlPlate) && dist2D(hero, ControlPlate) >= 200
                -> "nobody to go near the second plate at cp<i>"

        cp0 t=0.8   PRECONDITION, fail-only (banks no credit):
            assert Angle(GradedDoor) <= 10
                -> "shut before anyone stood on a plate"
            assert dist2D(hero, GradedPlate) >= 400 && !hero.IsFalling()
            Phase = Approach1
        cp1 t=4.8   assert OnPlate(GradedPlate)
                      -> "could not reach the plate on the first approach"
                    assert Angle(GradedDoor) >= 80
                      -> "open while the character stood on its plate (cycle 1)"
                    assert Travel(GradedDoor) >= 50
                      -> "the door's own panel to move, not just turn in place"
                      [the panel's hinge offset means a real 90 deg swing carries
                       it well over a metre; 50 cm is a generous floor that only
                       a panel which did not actually swing can miss]
                    Open1 = Angle(GradedDoor)
        cp2 t=6.4   assert OnPlate(GradedPlate)
                    assert Angle(GradedDoor) >= 80
                      -> "stay open for as long as the character kept standing
                          (cycle 1)"
                    Phase = Depart1
        cp3 t=9.4   assert !OnPlate(GradedPlate) && dist2D >= 300
                    assert Angle(GradedDoor) <= 10
                      -> "shut again after the character walked off (cycle 1)"
                    assert Travel(GradedDoor) <= 50
                      -> "the panel to come back to where it started (cycle 1)"
                    Phase = Approach2
        cp4 t=13.1  assert OnPlate(GradedPlate)
                      -> "could not reach the plate on the second approach"
                    assert Angle(GradedDoor) >= 80
                      -> "open again the second time"
                    assert Travel(GradedDoor) >= 50
                      -> "the door's own panel to move again the second time"
                    assert |Angle(GradedDoor) - Open1| <= 10
                      -> "same open position as the first time"
        cp5 t=14.7  assert OnPlate(GradedPlate)
                    assert Angle(GradedDoor) >= 80
                      -> "stay open for as long as the character kept standing
                          (cycle 2)"
                    Phase = Depart2
        cp6 t=17.7  assert !OnPlate(GradedPlate) && dist2D >= 300
                    assert Angle(GradedDoor) <= 10
                      -> "shut again after the character walked off (cycle 2)"
                    assert Travel(GradedDoor) <= 50
                      -> "the panel to come back to where it started (cycle 2)"
                    -> FinishTest(Succeeded)
```

Every gate fails through its own `FinishTest(Failed, ...)` literal (the
named-FAIL placement law); the substrings above are the credited ones, and
**no two of them are equal**. That is why cycle 1 and cycle 2 carry explicit
`(cycle 1)` / `(cycle 2)` suffixes, the two approach failures name which
approach, and the control gauge carries `at cp<i>`: an earlier draft reused
cp1/cp4, cp2/cp5 and cp3/cp6's strings verbatim and fired one literal at all
seven checkpoints for the control, so "the second cycle degraded" reported
identically to "the first cycle never worked".

**Schedule margins.** Measured against the disclosed budgets at the stock
500 cm/s walk: arrival ~t=2.2 (600 cm lane), so cp1 sits ~2.6 s after
arrival against a disclosed 2.0 s open budget; the pad is cleared ~0.35 s
after Depart1 begins at cp2, so cp3 sits ~2.6 s after the hero left against
the disclosed 2.0 s shut budget; the second cycle repeats with ~0.9 s and
~0.65 s of margin. Every gate therefore carries **>= 0.6 s of slack over the
number the prompt discloses**, which is what keeps a correct-but-conservative
implementation from false-FAILing. The instants are re-confirmed from the
reference run's `calib` line on BOTH framerate legs at build time; the
continuity limits reuse the calibration proven on `gp-door-hitch-fix-bp`
(a smooth 90 deg / 1.5 s swing moves ~1 deg per tick at 60 fps, cubic peaks
under 3; a snap moves 40-90 deg in one tick), re-expressed as a per-second
rate so it means the same thing on both legs.

**Every graded fact excludes the value an empty or lazy delivery gets for
free** (the dead-gate audit):

| requirement (all disclosed in the prompt) | assertion | free to an empty/lazy submission? |
|---|---|---|
| doors shut when play begins | cp0 `shut before anyone stood on a plate` | **yes, deliberately** — fail-only precondition, banks no credit; it exists solely to sink an open-at-play delivery, and the empty submission still dies at cp1 |
| open >= 80 deg within 2 s of stepping on | cp1 `open while the character stood on its plate` | no — the discriminating gate; the empty leg dies here |
| stays open while occupied | cp2 / cp5 `stay open for as long as the character kept standing` | no — kills an auto-close timer that reshuts under a standing body |
| shut within 10 deg within 2 s of stepping off | cp3 / cp6 `shut again after the character walked off (cycle N)` | **yes, and it is not a hole** — an unmoved door is always within 10 deg of shut, so an empty submission satisfies this row for free. It banks NO credit (the L2 verdict is one all-or-nothing outcome with no k/N), and the empty leg is already dead at cp1. Kept as a fail-only guard because it is the only thing that kills the one-shot latch which leaves the door hanging open |
| works every time, second open == first | cp4 `open again the second time` + `same open position as the first time` | no — the run's OWN first measurement is the reference, so a degraded repeat dies even inside the generous absolute band |
| the panel itself swings and travels | cp1 / cp4 `the door's own panel to move…` + cp3 / cp6 `the panel to come back…` | no — an unmoved panel FAILs cp1's `>= 50 cm`, and a decorative-mesh spoof FAILs it too because only `Panel(Door)` is measured |
| never faster than 720 deg/s or 3000 cm/s | per-tick guard, both doors, whole run, `swing smoothly` | **yes, and it is not a hole** — a door that never moves never exceeds any rate limit, so this is free to an empty submission. Same accounting as above: fail-only, banks nothing, and it is the only thing that kills a snap to the open pose |
| a plate moves only its own door | control gauge at all 7 checkpoints `the untouched door to stay shut at cp<i>` | **yes, and it is not a hole** — the empty submission's control door never moves either. Fail-only; what makes it worth keeping is that an occupancy-blind broadcast dies at the first checkpoint after the graded door opens, and nothing else catches that |
| (staging) nobody touches the control plate | control gauge `nobody to go near the second plate at cp<i>` | (guard row — proves the control's shut state is genuinely un-driven) |

**Read the "yes" rows the way the owner's guidance reads them.** Three of the
eight rows above — including corpus checks 4 (`DoorReturnsToClosedTransform`) and
5 (`DoorTransitionsContinuously`) — are true of a do-nothing submission. That is
declared here rather than hidden, and it costs no score: L2 is a single
`AFunctionalTest` outcome, so a free row inflates nothing, and the empty
submission FAILs at cp1 before reaching any of them. The reason to keep them is
`startup-feedback.md`'s own instruction about check 1 — *"it is free to an empty
submission, but it is also the only SCORED defence against opening everything at
BeginPlay"*. Each free row above is the only defence against exactly one wrong
implementation (hanging-open latch, snap, occupancy-blind broadcast). An earlier
draft of this table asserted "no" for all three, which was simply false.

**Pass criteria**: both L1 targets green, and the fixture green on **both**
framerate legs (60 and 20). **Robust identity**: hero, plates and doors are
all resolved by tag, never by class; the door's observable surface is its
**panel** — the `DoorPanel`-named static-mesh component if it is still there,
otherwise the largest one — measured relative to that component's own recorded
closed pose. So renaming the panel, replacing its mesh, or adding extra parts
are all free, while adding a part and swinging *that* instead is not: the gate
follows the piece a person watches, not whichever piece happens to have moved.

## Reference solution metadata

- LOC range: 40-70 (plate: begin/end-overlap handling or an equivalent poll,
  an occupant count so two bodies do not close the door when one leaves, and
  a call through `LinkedDoor`; door: a target angle plus a per-frame
  interpolation toward it, both directions)
- Files touched: 4 (all pre-existing scaffold files:
  `ContactPlateActor.{h,cpp}`, `SwingDoorActor.{h,cpp}`)
- Senior-dev hours: 0.75-1.5

## Anti-gaming notes

1. **Empty / partial submission.** *Failure mode*: the scaffold compiles with
   no occupancy handling and no door motion, so L1 is green. *Defense*: cp1
   asserts the graded door is >= 80 degrees from shut while the driven
   character is measurably standing on the pad, and FAILs via the named
   message `open while the character stood on its plate` — FAIL-on-empty, not
   differs-from-reference.
2. **Open regardless of occupancy.** *Failure mode*: the door is opened in the
   constructor / at play start / unconditionally every frame, so every open
   sample looks right. *Defense*: cp0 is a fail-only precondition that sinks
   an already-open door before anyone has stood on anything
   (`shut before anyone stood on a plate`), and cp3 / cp6 both require the
   door back within 10 degrees of shut with the character measured >= 300 cm
   away.
3. **One-shot latch, or a degraded repeat.** *Failure mode*: the first contact
   opens the door and nothing ever closes it; or a state machine that only
   half-works the second time; or a timer fit to guessed sample instants.
   *Defense*: cp3 and cp6 are shut gates, cp4 is a second open gate, and cp4
   additionally requires the second open angle within 10 degrees of the
   **first measured** one. The checkpoint instants are undisclosed and both
   arrival and departure are measured from the character's own position, so
   there is no timetable to fit.
4. **Spillover onto the untouched twin.** *Failure mode*: any occupancy
   anywhere opens every door in the level (a level-wide broadcast, an
   all-actors iteration, or a class-default flag), which satisfies every gate
   aimed at the graded pair. *Defense*: the control door is gauged at ALL
   SEVEN checkpoints and must stay within 10 degrees of shut
   (`the untouched door to stay shut`), and the fixture also proves the
   control plate was never approached — seven independent chances to die.
5. **Cheat the measurement instead of implementing the behavior.**
   *Failure mode*: (a) snap or teleport the panel to the open pose so the
   angle reads 90 with no travel, including a tick-count swing that happens
   to look right at one frame rate; (b) **move a part nobody watches** — the
   agent owns `SwingDoorActor.{h,cpp}`, so it can add a decorative static-mesh
   component and swing THAT smoothly through 90 degrees and back while the
   visible `DoorPanel` never moves. A human watching Play sees a door that never
   opens; (c) edit the fixture, the map or config to
   weaken the gate. *Defense*: (a) the per-tick continuity guard is armed for
   the whole run on both doors (720 deg/s, 3000 cm/s) and the same fixture
   re-runs at 20 fps, where a tick-count swing blows the disclosed 2-second
   budget; (b) the gate measures **exactly one component** —
   `Panel(Door)` = `DoorPanel` if present, else the largest-volume static mesh,
   resolved once in `PrepareTest` — and requires that component's world
   **location** to travel >= 50 cm, not only its yaw to change. A `max` over all
   the door's meshes, which is what an earlier draft used, is a gate on
   "something on this actor turned" and would have PASSed this route with a
   human-visible door that never opened; (c) `Source/CraftBenchTests/` is
   sandbox-denied (submission files
   under it are rejected pre-grade), the runner materializes the graded
   substrate from git HEAD (an on-disk edit never reaches the grade;
   committed changes are review-gated on commit), `Content/Maps/` is
   deny-listed, and `Config/` is admitted only through the semantic config lane
   against this spec's `config_allow` — which is empty, so every ini diff is
   uncovered and rides the exit-4 path.

## Hidden invariants

- The seven checkpoint instants are not disclosed; the prompt carries every
  threshold the grade compares the submission against (90 / 80 / 10 degrees,
  2 seconds, 720 deg/s, 3000 cm/s, 300 cm, 10 degrees of repeat agreement, the
  200 x 200 cm pad and the **100 cm occupancy radius**, and the fact that it is
  the panel's yaw about the vertical axis that is measured) but no sampling
  times. Two numbers are verifier-side and neither can FAIL a submission that
  satisfies the prompt: the `Travel(Door) >= 50 cm` panel-displacement floor,
  which a real 90-degree swing about a hinge-offset panel clears by more than a
  metre, and the `>= 200 cm` / `>= 300 cm` / `>= 400 cm` staging distances the
  fixture's own drive produces. (An earlier draft graded the 100 cm occupancy
  radius without disclosing it while claiming the prompt "carries every
  threshold" — a submission judging occupancy with a narrower test than the
  fixture's, which the prompt permitted, would have had its door still shut at
  cp1 and FAILed on a number it was never told.) A point-fit keyed to
  guessed instants has seven independent chances to miss, and the ones that
  matter most (arrival, departure) are triggered by the character's measured
  position, not by the clock.
- The continuity guard is **per-tick across the whole run**, not a checkpoint
  sample, and it covers the control door as well as the graded one — there is
  no window between samples in which a door can snap unobserved, and no frame
  in which the control pair is unwatched.
- cp0 is deliberately fail-only. The corpus's check 1 ("door closed while
  unoccupied") is free to an empty submission, so it banks nothing here; it
  survives as a **precondition** because it is the only scored defence
  against a delivery that simply opens everything at play start. Deleting it
  would remove that defence; crediting it would pay an empty submission.
- The second-cycle gate compares against the run's OWN first measured open
  angle, so the repeat requirement is self-referential: widening the absolute
  band never widens it.
- Framerate independence is gated only to the extent the disclosed
  wall-clock budgets require it (the 20 fps leg exists to kill a
  frame-counted swing). The per-frame limits in the fixture are expressed as
  per-second rates so both legs enforce the same disclosed number.
