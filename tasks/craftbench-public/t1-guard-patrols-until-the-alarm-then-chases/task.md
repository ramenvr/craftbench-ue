---
id: t1-guard-patrols-until-the-alarm-then-chases
substrate: ThirdPerson
set: craftbench-public
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_PatrolYard :: APatrolChaseFunctionalTest"]
---

# t1-guard-patrols-until-the-alarm-then-chases

A guard that paces a route until something calls it away, goes after the
character while it is called, and goes back to pacing when it is not — graded
on **where the guard is**, never on what it says its state is. The alarm is a
plate on the floor that the character stands on, so a reviewer drives the same
transition with WASD that the fixture drives with `AddMovementInput`.

Imported from the Startup Eval corpus row `t1-bt-patrol-then-chase`
(provenance, owner note, and every deviation: `notes.md`). Renamed because `bt`
put the mechanism in the agent-visible path, and the mechanism is not the
point: a behaviour tree, a state enum in `Tick`, or three `if`s all pass
identically.

> **The corpus row's `StaysOnPatrolWhileTargetFar` is RESTORED here.** The
> hardened rubric dropped it, and with it gone a guard that charges the
> character from frame one passes every remaining check — the alarm is never
> measured at all. It is the assertion this task is built around, not a
> nice-to-have.

> **`deliverable_root:` was REJECTED by the parser.** It is not in
> `tools/verify-single/spec.py::_KNOWN_KEYS`, and an unknown front-matter key is
> a hard `ValueError` (exit 2, "spec malformed") — not a warning. Per the
> `tasks/README.md` mitigation the deliverable root is
> therefore stated as the first line of **Workspace state pre-task** and again
> in the prompt body: it is `Source/ThirdPerson/`.

## Primary concept

- `ai-behavior-states` — switching an actor's behaviour on a world condition
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/behavior-trees-in-unreal-engine)

The load-bearing behaviour is a **transition driven by an external condition**,
in both directions, more than once, with the *quiet* behaviour graded as
strictly as the *active* one. The grade never asks *how*: no state name, enum
or blackboard key is read anywhere.

## Prompt given to the agent

> The yard has one guard, two lit posts, and an alarm panel with a plate on the
> floor in front of it. The panel goes red exactly while somebody is standing on
> that plate, and it is already wired up and working.
>
> Make the guard pace between the two posts, and make it go after the character
> the player controls whenever the alarm is sounding **and** that character is
> inside the guard's own alert range.
>
> While the alarm is quiet, the guard belongs on its route: it must stay within
> **450 units** of the line joining the two posts, and it must never come within
> **900 units** of the character. While the alarm is sounding, it must close on
> the character — ending up at **less than 55%** of the distance it was at when
> that alarm began — and it must be facing them while it does; closing the
> distance sideways or backwards is not going after somebody. When the alarm
> stops, the guard goes back to pacing and must reach a post again. The yard
> sounds the alarm **twice**, and both times must send the guard after the
> character.
>
> Deciding when the alarm rings is not your job and must not become your job:
> the plate does that, and the panel's own behaviour must be left exactly as it
> is. A guard that makes the alarm sound on its own terms has replaced the thing
> it was supposed to be reacting to.
>
> A second figure stands elsewhere in the yard, parked permanently outside the
> guard's alert range. It is never the target, and the guard must never approach
> it.
>
> The guard already has a body, a facing, one call that walks it toward a point
> at a given speed, and a test for whether it has arrived; its patrol speed,
> chase speed, arrive radius and alert range are already set on it. Nothing
> decides where it should be going. Do not move the posts, the panel, the second
> figure or the character, and do not edit the level, any config file, or any
> test file. Write your solution in C++ under `Source/ThirdPerson/`.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on
this substrate). `Source/CraftBenchTests/` is deny-listed and a submission file
under it is a SANDBOX-REJECT (exit 4), not a graded FAIL; so are
`Content/Maps/`, `Content/ThirdPerson/`, `Content/Characters/` and every
`Config/` file (no `config_allow` is declared by this task).

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t1-guard-patrols-until-the-alarm-then-chases/PatrolGuardActor.h` /
  `.cpp` — declares and defines
  `class THIRDPERSON_API APatrolGuardActor : public AActor`. The constructor
  adds `Tags.Add(FName("PatrolGuard"))` and builds, all supplied:
  - `Hull` — a capsule, 70 cm across and 180 cm tall, **the root**, collision
    `BlockAll`. It is a capsule and not the mesh on purpose: a root component's
    relative location *is* the actor's location, so a mesh made root and offset
    upward leaves its collision centred on the actor origin, half inside the
    floor, permanently penetrating, and refusing every swept move.
  - `Body` — a cylinder static mesh centred on the hull, collision off (the
    hull does the colliding).
  - `Snout` — a cone on the front, so which way the guard faces reads at a
    glance.
  - `UPROPERTY(EditDefaultsOnly) float PatrolSpeedUu = 220.f`,
    `float ChaseSpeedUu = 520.f`, `float ArriveRadiusUu = 120.f`,
    `float AlertRangeUu = 2000.f`.
  - `UFUNCTION(BlueprintCallable) void StepToward(const FVector& Destination,
    float SpeedUu, float DeltaSeconds)` — the supplied locomotion. Walks the
    guard toward `Destination` for one frame at `SpeedUu`, never overshooting,
    turning it to face the way it moved, leaving height alone.
  - `UFUNCTION(BlueprintPure) bool HasReached(const FVector& Point) const`.
  - **No tick, no timer, no target lookup, no call to `StepToward` anywhere.**
    The whole decision is the agent's to implement, **and it has to land on this
    class**: the guard is a placed instance of `APatrolGuardActor` in a map you
    cannot edit, so a subclass of it would never be instantiated in the graded
    world and the placed guard would stay logic-free.
- `Tasks/t1-guard-patrols-until-the-alarm-then-chases/AlarmPanelActor.h` /
  `.cpp` — `class THIRDPERSON_API AAlarmPanelActor : public AActor`, tagged
  `AlarmPanel`. **Supplied and working end to end**: a board, a lit plate, a
  box volume over the plate, and a `Lamp` point light. Standing a pawn on the
  plate takes the board and the lamp red; stepping off puts them out.
  `UFUNCTION(BlueprintPure) bool IsRinging() const`. Occupancy is counted, not
  flagged, so two figures on one plate do not clear the alarm when the first
  steps off. Nothing needs changing here, and nothing here knows the guard
  exists.
- `Content/Maps/t1-guard-patrols-until-the-alarm-then-chases/L_PatrolYard.umap` —
  the staged yard, committed binary. World Settings select the stock read-only
  `BP_ThirdPersonGameMode`, so play spawns and possesses the stock mannequin at
  the PlayerStart. What is in it:

  | Element | Placement | Notes |
  |---|---|---|
  | Floor | a long striped yard | stripe markings every 400 cm, **no collision** — they are paint, and a 3 cm lip is a wall to anything moved by a swept `SetActorLocation` |
  | Two posts | tagged `PatrolPost`, lit tops, **movable** | the fixture nudges them before play, and PIE scores moving a *static* actor as a failed test |
  | One `APatrolGuardActor` | tagged `PatrolGuard`, standing clear of both posts | a guard spawned inside a post penetrates it from frame one and can never move |
  | One `AAlarmPanelActor` | tagged `AlarmPanel`, standing off the axis everything else uses | its plate sits 300 cm clear of its board, so neither the character walking up nor the guard coming for the character has to get past the board |
  | A second figure | tagged `DecoyFigure`, parked permanently outside the guard's alert range | never the target |
  | Patrol line + alert-range arc | painted on the floor, no collision | the line the guard must keep to, and the range it works to, made visible |
  | PlayerStart | on the floor, outside the guard's alert range | |
  | Backdrop + landmarks | a low back wall and two differently sized marker posts | a moving camera is distinguishable from a still one |
  | Fixture | one placed `APatrolChaseFunctionalTest` | |

  **The posts', the panel's and the second figure's exact coordinates are
  deliberately NOT in this section**, and `PrepareTest` additionally **nudges
  both posts** before play, so a submission keyed on where things stand rather
  than on finding them reads a stale number. `## Workspace state pre-task` and
  `## Prompt given to the agent` are exactly
  `tools/run-agent/prompt_extract.py::ALLOWED_SECTIONS`, i.e. both reach the
  agent.
- `cameras.json` (the camera-plan lane; not part of this release) — the
  presentation-only camera plan. Non-gating.

Files that **do not exist**:

- No patrol logic, no chase logic, no Blueprint subclass, no level edits. The
  empty submission compiles (L1 green) and FAILs L2 at the first alarm.
- No test source in the agent's writable path. `APatrolChaseFunctionalTest`
  lives in the `CraftBenchTests` module the agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t1-guard-patrols-until-the-alarm-then-chases/L_PatrolYard.umap` on
the **ThirdPerson** substrate, ticked at a fixed deterministic step
(`-deterministic -FPS=60`). Verification primitive:
**pie-checkpoint-sampling** (the schedule + `OnCheckpoint` clock owned by
`ACraftBenchFunctionalTest`) over a per-frame `AddMovementInput` drive of the
game-mode-spawned player character. The fixture walks that character from a
wait spot to the alarm plate and back, twice, and reads the alarm off the
panel's **lamp intensity** — the thing a reviewer sees — rather than off the
panel's occupancy counter, which is a plain private int with no `UPROPERTY` and
which reflection therefore cannot see at all.

A human hitting Play drives the identical transition with WASD: walk onto the
plate, the panel goes red, the guard comes; step off, it goes dark and the
guard walks back to its posts.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

**No warning assert, deliberately** — `--strict-warnings` is off by default and
no `aura_rig` path passes it, so such a gate would never run on `cb eval` /
`cb refgate`; and the prompt never mentions warnings, so gating on one would be
an undisclosed grade-bearing condition.

### L2 — AFunctionalTest behavioral trace

Every gate below is judged from the guard's **position and heading**. No
behaviour-state name, enum or blackboard key is read anywhere.

```text
assert: StaysOnPatrolWhileTargetFar  -- with the alarm quiet (after an 8 s
        settle, measured as the time a correct guard needs to walk home from
        where a chase leaves it), the guard is within 450 uu of the line
        joining the posts AND at least 900 uu from the character
assert: ChasesWhileTheAlarmRings     -- each alarm lasting >= 4 s must see the
        guard reach < 55% of the gap it had when that alarm began, AND face
        the character (within 40 deg) on >= 70% of frames sampled after a
        1.2 s settle
assert: ChasesEveryTimeTheAlarmRings -- at least 2 alarms must qualify
assert: PatrolsBetweenThePosts       -- both posts reached, and at least one of
        them reached BEFORE the first alarm
assert: ResumesPatrolWhenTheAlarmClears -- a post reached again AFTER the first
        alarm ended
assert: NeverApproachesTheOtherFigure -- the guard never gets 300 uu closer to
        the second figure than it started
assert: AlarmMatchesThePlate         -- the panel's lamp agrees with whether the
        character is on the plate, allowing 1 s of disagreement for the
        boundary frame
assert: TheRouteWasWalked            -- the fixture's own drive reached all 5 of
        its stops, so both alarms actually happened
```

The checkpoint schedule carries a **sentinel at t = 150 s**, far past the ~65 s
the drive takes, because `ACraftBenchFunctionalTest::Tick` ends the test the
moment the last scheduled checkpoint is sampled — so every gate that can only
be judged once the whole drive is done hangs off that sentinel.

**Staging faults are attributed, not scored.** A yard that cannot resolve its
guard, posts, panel or second figure, or a panel with no readable lamp, ends the
run as `HARNESS-PRECONDITION` (`EFunctionalTestResult::Error`), never as a model
failure.

## Anti-gaming notes

1. **Always chasing.** *Failure mode*: go at the character every frame and never
   pace at all — which is exactly what the corpus row's hardened rubric permitted
   once it dropped `StaysOnPatrolWhileTargetFar`, and it scored full marks there.
   *Defense*: that gate is restored and is the strictest in the task. With the
   alarm quiet the guard must be within 450 uu of the line joining the posts AND
   at least 900 uu from the character, judged every frame across three quiet
   windows totalling ~40 s. An always-chaser is 1100+ uu off the line and ~70 uu
   from the character, i.e. wrong on both clauses at once.
2. **Never chasing.** *Failure mode*: pace correctly and ignore the alarm — the
   shape the empty submission degenerates to. *Defense*: `ChasesWhileTheAlarmRings`
   requires the gap to fall below 55% of what it was when that alarm began. The
   measured empty run closes 1400 uu to 1341 uu, all of it the character walking,
   and FAILs with both numbers in the message.
3. **Chasing once.** *Failure mode*: latch on the first alarm, or leave a
   one-shot flag set so the guard never returns, or return but never re-trigger.
   *Defense*: the yard rings the alarm **twice** and
   `ChasesEveryTimeTheAlarmRings` requires both spells to qualify;
   `ResumesPatrolWhenTheAlarmClears` separately requires a post reached AFTER the
   first alarm ended, tracked apart from having reached one before it. A latch
   fails the second; a guard that never comes home fails the third.
4. **Claiming the state instead of being in it.** *Failure mode*: expose a
   behaviour-state name, enum or blackboard key that reads "Chasing" while the
   guard stands still, or drift past the character sideways so the distance falls
   without any pursuit. *Defense*: no gate reads any name, enum or key — every
   one is a distance or an angle taken from the guard's transform. The chase gate
   pairs the distance clause with a heading clause (within 40 deg of the
   character on ≥ 70% of sampled frames), so closing the gap without going after
   anybody does not count.
5. **Taking over the trigger.** *Failure mode*: make the guard's own sensing
   drive the panel, or hard-code where the posts and the plate are so the
   "decision" is really a fixed route. *Defense*: `AlarmMatchesThePlate` compares
   the panel's lamp against the fixture's own test of whether the character is on
   the plate, allowing 1 s for the boundary frame; and `PrepareTest` nudges both
   posts before play while the spec withholds every coordinate, so a hard-coded
   position is stale before the first frame.
