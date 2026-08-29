---
id: t2-turret-leads-you-and-holds-fire
substrate: ThirdPerson
set: craftbench-public
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_TurretYard :: ATurretLeadFunctionalTest"]
---

# t2-turret-leads-you-and-holds-fire

Two bolted-down turrets throw slow, heavy shots at a walking character. A shot is
settled the instant it leaves the barrel, so hitting means aiming at where the
character is **going**. Each turret carries its own four numbers — shot speed,
reach, barrel-swing rate, reload — the two turrets are set differently, and the
yard **re-tunes both of them twice while it is running**. And a turret must fire
**nothing at all** when no straight shot at its own speed could ever catch the
character.

`deliverable_root`: `Source/ThirdPerson/` — see the first line of *Workspace state
pre-task*. The front-matter key of that name is rejected by the parser
(`tools/verify-single/spec.py::_KNOWN_KEYS`), so per the set's README the path is
stated twice in agent-visible prose instead: in the prompt block and in the first
line of *Workspace state pre-task*. Those two H2s are exactly
`tools/run-agent/prompt_extract.py::ALLOWED_SECTIONS`.

> **Built against the 2026-08-18 difficulty bar.** Two subsystems that genuinely
> interact: a **trigger** and a **servo**. Firing promptly enough to meet the
> engagement duty breaks the accuracy gate unless firing is gated on where the
> barrel has actually got to; being conservative about the barrel breaks the
> engagement duty unless that gate is scaled to range. Neither half can be tuned
> with the other out of view. The load-bearing facts — four numbers per turret,
> re-tuned twice — are read from the world at runtime and change under the
> solution, so no constant passes.

## Primary concept

- `predictive-aim-with-a-rate-limited-servo` — an actor solving, every frame, for
  where a target will be when a finite-speed projectile could reach it, driving a
  turret head that cannot get there instantly, and withholding the shot when the
  solution does not exist
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/vectors-in-unreal-engine)

The grade never asks *how*. A closed-form quadratic, a fixed-point iteration, or a
short numeric search all pass identically; what is graded is where the shots go and
when they are taken.

## Composed concepts

- `per-instance-configuration-read-live` — two instances of one class answering from
  their own numbers, which change under them mid-run
- `finite-slew-rate-actuation` — a commanded orientation the actuator approaches at
  a bounded rate, so the commanded and the actual orientation are different things
- `existence-test-before-action` — the same solve that produces the answer is what
  says whether there is an answer at all

## Prompt given to the agent

> The yard has two gun turrets and one thing to shoot at: the character the player
> controls. The turrets throw slow, heavy shots. A shot travels dead straight at a
> constant speed, is never pulled down, and passes through everything in its way —
> so where a shot ends up is settled entirely at the instant it leaves the barrel.
>
> Each turret carries its own four numbers, readable on the turret itself: how fast
> its shot flies, how far from the turret it is willing to engage, how quickly its
> barrel can swing, and how long it takes to reload. The two turrets are not set to
> the same numbers, and the yard **re-tunes them more than once while it is
> running** — a number you read once at startup will be wrong later on.
>
> **Make each turret shoot to hit.** A shot counts as connecting if, at its closest
> approach, it passes within **120 cm of the middle of the character**. Because the
> shots are slow and the character keeps walking, that means aiming at where the
> character is going to be, not at where they are: a shot sent at somebody's current
> position trails visibly behind them on every single attempt. **Every shot a turret
> takes while the character is walking steadily in the open, inside that turret's
> reach, has to connect** — one that does not is a miss, not bad luck.
>
> **And make each turret keep its mouth shut when there is nothing to shoot at.** A
> turret may fire only when **both** of these are true at the moment it fires: the
> character is inside **that turret's own** engagement distance, and a shot leaving
> now at **that turret's own** speed, flying dead straight, would genuinely meet the
> character somewhere ahead of them if they carry on moving exactly as they are.
> When the character is out of reach, or is moving in a way that no shot from that
> turret could ever catch, that turret fires nothing at all — it does not fire
> hopefully and watch the shot fall behind. Note that simply outrunning a shot is
> not on its own a reason to hold: somebody sprinting *at* a turret is easier to hit
> than somebody strolling past it, not harder.
>
> Whenever both of those conditions do hold, take the shot — and keep taking it, as
> often as that turret's own reload allows.
>
> The barrel is the gun. A shot always leaves along **wherever the barrel is
> actually pointing at that instant**, and the barrel does not snap into place: you
> point it somewhere and it swings there at that turret's own rate, which is not the
> same on both turrets. The turret's base is bolted to the floor and does not turn —
> only the barrel moves, and it turns on the spot rather than travelling.
>
> Where the turrets stand is not yours to change, and neither is the character or
> how fast they can move. The turret bodies, the barrel, the aiming control and the
> trigger are all supplied and working; nothing decides where to point them or when
> to pull. Do not edit the level, any config file, or any test file. Write your
> solution in C++ under `Source/ThirdPerson/`.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on
this substrate). `Source/CraftBenchTests/` is deny-listed and a submission file
under it is a SANDBOX-REJECT (exit 4), not a graded FAIL; so are `Content/Maps/`,
`Content/ThirdPerson/`, `Content/Characters/` and every `Config/` file (no
`config_allow` is declared by this task).

Everything under `Source/ThirdPerson/` is **yours to edit**, including the two files
below. They are supplied working and complete, and the intention is that you write
the decision on top of them rather than rewrite them — but nothing stops you, and
the grade watches the outcome, not the diff.

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t2-turret-leads-you-and-holds-fire/LeadTurretActor.h` / `.cpp` —
  `class THIRDPERSON_API ALeadTurretActor : public AActor`, tagged `LeadTurret`.
  Two of these are placed in the yard. Supplied:

  | Piece | What it is |
  |---|---|
  | `Mount` | the actor's root pivot. Bolted: the yard places it and it does not turn or move |
  | `Base` (component tag `TurretBase`) | a 220 cm cylinder standing 320 cm tall, `BlockAll`, **movable** |
  | `Barrel` (component tag `TurretBarrel`) | the gun. Its local **+X is the bore**. Mounted 320 cm above the floor and parked pointing +Y, across the yard |
  | `BarrelMesh` | cosmetic tube lying along the bore |
  | `Muzzle` (component tag `TurretMuzzle`) | the bore tip, 230 cm out along +X |
  | `float ShotSpeedUu` | how fast this turret's shot flies. **Re-tuned mid-run** |
  | `float EngageRangeUu` | how far from this turret it will engage. **Re-tuned mid-run** |
  | `float TraverseDegPerSec` | how fast this barrel swings, as a **total** angle. **Re-tuned mid-run** |
  | `float ReloadSeconds` | this turret's reload. **Re-tuned mid-run** |
  | `void AimBarrel(FRotator)` | **the aiming control.** Slews the barrel toward a world rotation at this turret's own rate and no faster. Rate-limited on the total angle (`FQuat::Slerp` clamped by `FQuat::AngularDistance`), self-clocked from the world clock and **clamped to one frame**: ten calls in one frame swing no further than one, and five idle seconds are not banked and then spent in a snap |
  | `bool FireNow()` | **the trigger.** Returns false and does nothing before the reload is up. Otherwise throws one shot from the muzzle, along the **barrel's current world forward vector**, at this turret's own `ShotSpeedUu` |
  | `bool IsReloaded()` / `FRotator GetBarrelWorldRotation()` / `FVector GetMuzzleWorldLocation()` | readbacks, so you can see where the barrel **actually** is rather than where it was last told to go |

  **No tick, no target, no aim point, no trigger pull.** `PrimaryActorTick.bCanEverTick`
  is `false`. Both turrets are placed instances in a map you cannot edit, so the
  decision has to land on this class (a subclass would never be instantiated).

- `Tasks/t2-turret-leads-you-and-holds-fire/TurretShotActor.h` / `.cpp` — the
  tracer, tagged `TurretShot`. Collision disabled outright, so it can never shove
  the character or be destroyed early. It moves itself each frame to
  `LaunchLoc + LaunchDir * LaunchSpeed * elapsed` and self-destructs after 16 s.
  Supplied complete.
- `Content/Maps/t2-turret-leads-you-and-holds-fire/L_TurretYard.umap` — the staged
  yard, committed binary. World Settings name NO game mode, so the level inherits
  `BP_ThirdPersonGameMode`. What is in it:

  | Element | Placement | Notes |
  |---|---|---|
  | Floor | ~12,250 x 3,980, striped every 400 cm, stripes **non-colliding** | |
  | Two `ALeadTurretActor`s | bolted 4,200 cm apart | authored with **different** numbers |
  | Ruler rings | fixed dashed circles at 10, 20, 30 and 40 m round each turret, **non-colliding** | a RULER, not a reach: the reaches are re-tuned twice, so a ring drawn at one of them would be a lie for two thirds of the run |
  | PlayerStart | at the near corner of the first lane | |
  | Backdrop + landmarks | a back wall and two differently sized posts | a moving camera is distinguishable from a still one |
  | Fixture | one placed `ATurretLeadFunctionalTest` | |

  **The turrets' four numbers are deliberately NOT in this section.** They are
  readable on the turrets — and they do not stay put.

- `cameras.json` (the camera-plan lane; not part of this release) — the
  presentation-only camera plan. Non-gating.

Files that **do not exist**:

- No aiming logic, no firing logic, no tick on the turret, no Blueprint subclass, no
  level edits. The empty submission compiles (L1 green) and FAILs L2 the first time
  the yard walks the character across a turret's reach and nothing is fired.
- No test source in the agent's writable path. `ATurretLeadFunctionalTest` lives in
  the `CraftBenchTests` module the agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t2-turret-leads-you-and-holds-fire/L_TurretYard.umap` on the
**ThirdPerson** substrate, ticked at a fixed deterministic step
(`-deterministic -FPS=60`). Verification primitive: **pie-checkpoint-sampling** with
an every-frame readback of each turret's transform, each barrel's world orientation,
and every live tracer's world position, over a fixture-driven walk that the fixture
also re-tunes twice.

### The fixture trusts nothing the submission stamps

`Source/ThirdPerson/` is the agent's writable tree, which includes the turret, the
trigger, the aiming control and the tracer's own "read-only" provenance fields. So
every fact the grade rests on is re-derived by the fixture from its own per-frame
samples:

| Fact | Where the fixture gets it |
|---|---|
| which turret fired a shot | the muzzle it first appeared at, within 150 uu |
| where it left from | the fixture's own sample of that shot's first position |
| which way it left | the shot's **own motion** over its first 0.2 s |
| how fast it flies | the fixture's read of that turret's **live** `ShotSpeedUu` at the instant the shot appeared |
| the barrel's aim | the world forward vector of the component tagged `TurretBarrel` |
| the four numbers | `FNumericProperty` by NAME (covers a `float` → `double` refactor) |

Nothing in the fixture reads `ATurretShotActor::LaunchDir`, `LaunchSpeed`,
`FiredAtSeconds` or `Shooter`. Re-stamping them buys nothing; deleting them costs
nothing.

### The route is derived, and it is dry-run before it is graded

Three parameter sets, staged by the fixture. **The map's authored numbers are the
phase-1 set on purpose**, so a submission that reads the numbers once in `BeginPlay`
is exactly right until the first re-tune and wrong about all eight numbers
afterwards.

| Set | shot speed | reach | traverse | reload |
|---|---|---|---|---|
| SET-L | 460 uu/s | 4200 uu | 40 deg/s | 1.5 s |
| SET-S | 1350 uu/s | 1500 uu | 130 deg/s | 0.9 s |
| SET-M | 750 uu/s | 2600 uu | 70 deg/s | 1.2 s |

Phase 1 `(T1=SET-L, T2=SET-S)` → **re-tune 1**, the sets swap → phase 2
`(T1=SET-S, T2=SET-L)` → **re-tune 2** → phase 3 `(T1=SET-M, T2=SET-S)`. Both
re-tunes happen 1.5 s into a dwell, with the character stationary, so no firing
window ever spans one.

Every stop is a multiple of the reach of the set that owns the leg — a lane standoff
of 0.52x, a lane half-length of 0.62x, a radial run from 0.18x to 0.90x, a charge
stopping at 0.20x with a 0.030x offset — so the route re-shapes itself around each
re-tune and no stop is written down. **The drive STANDS at every waypoint for 5 s**
before advancing; arrival radius 70 uu. Nine stops, eight legs, ~137 s of route plus
a 6 s drain.

| Leg | speed | what it is for |
|---|---|---|
| A | 260 | the headline lead leg: T1 (SET-L) has a 13.4 s firing window abeam at 2184 uu, flight time 5.8 s |
| W1→W2 | 260 | T1 stays engaged; T2 stays 2679+ uu outside its 1500 reach |
| B | 260 | **the acquisition leg**: T2's window opens 6.7 s into a leg the character is already walking steadily, after ~40 s with its barrel parked elsewhere. T1 drops out of reach for the last 9.4 s |
| W3→W4 | 620 | phase 2. A head-on close at 620 against a 460 shot: faster than the shot, and plainly hittable |
| C | 620 | **the no-interception leg**: sprinting straight out along T2's radial at 620 from a 460 gun, inside its 4200 reach the whole way |
| D | 520 | **the blanket-rule killer**: still faster than the 460 shot, but closing, with the across-sight component peaking at 154 uu/s against a 368 bar |
| W6→W7 | 260 | phase 3. T2's window closes mid-leg; T1's opens mid-leg |
| E | 260 | a third lead angle at a third shot speed (750) |

`PrepareTest` **dry-runs the whole route at 240 samples per leg** before a frame is
graded, and ends the run as `HARNESS-PRECONDITION` — never as a model failure — if:
the two shot speeds are within 500 uu/s or the two reaches within 1000 uu in any
phase; a stop or any part of a leg comes within 400 uu of a solid turret base; a stop
sits within 8% of a reach boundary in either the phase it arrives in or the phase it
leaves in; a window the yard would demand a shot in is shorter than 3.3 reloads;
the intercept point's bearing rate in such a window exceeds 0.6x that turret's
traverse (the barrel physically could not follow); either turret gets no demanded
window at all, or under 2.0 s of the route in which a shot from it could be judged
for accuracy; the longest in-reach-but-no-interception stretch is under 2.5 s; or the
longest out-of-reach stretch is under 5 s. A visibly represented player character
must exist.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

The fixture's own answer, every frame, from the LIVE numbers:

```text
D      = heroPos - barrelPivotWorldPos      (3D; the pivot is bolted, the muzzle is not)
V      = hero->GetVelocity()                (the same quantity a submission reads)
solve  : (|V|^2 - s^2) t^2 + 2(D.V) t + |D|^2 = 0, smallest POSITIVE root
across = |V - D_hat (V . D_hat)|            (component across the line of sight)
along  =  V . D_hat                         (positive = opening the range)

FIRING WINDOW for turret T  (what the yard DEMANDS a shot in):
        |V| >= 200 uu/s
    AND dist(hero, T) <= T.EngageRangeUu
    AND across <= 0.80 * T.ShotSpeedUu
    AND a positive root exists AND it is <= 8.0 s
OUT OF REACH  : dist(hero, T) > 1.25 * T.EngageRangeUu
NO SOLUTION   : across > 1.25 * T.ShotSpeedUu
             OR (|V| > 1.25 * T.ShotSpeedUu AND along > 0.25 * |V|)
GRADEABLE SHOT: fired inside a firing window, with the character in steady straight
                motion (speed within 5%, direction within 3 deg) for >= 1.0 s, and
                the solved flight time + 0.8 s still fitting inside the current leg
```

The exact no-root condition is `across > s` OR `(|V| > s AND opening)`, so the
NO SOLUTION test is a strict **subset** of it and can only ever forgive. The window
test is the mirror margin: the yard only demands a shot where the solution is
comfortable, so a submission is never charged with silence for declining an absurd
one. Gradeability is computed purely from the world and the route — nothing a
submission does can widen or narrow it, and it can only ever EXCLUDE shots.

```text
assert: ShotsFromTheOpenConnect -- per gradeable shot, the closest approach between
        the shot's sampled path and the character's path, computed segment against
        segment so frame discretisation contributes nothing, is <= 120 uu. Read
        0.5 s + the fixture's own flight time after the shot appeared, or on the
        shot's death, whichever is first
assert: TheTurretsActuallyEngage -- per firing window, on close: at least 1 shot
        from that turret if (window - 90 deg / its traverse) >= max(2.5 s,
        1.6 x its reload), and at least 3 if that remainder >= 10 s
assert: NothingIsFiredBeyondItsOwnReach -- zero shots from turret T at any instant
        when the character is farther from T than 1.25 x T's LIVE EngageRangeUu
assert: NothingIsFiredWithNowhereToAim -- zero shots from turret T at any instant
        the fixture's own solve calls unsolvable, with margin
assert: TheBaseIsBoltedDownAndTheBarrelDoesTheAiming -- every frame each turret's
        actor and its TurretBase component are within 0.5 deg and 2 uu of what the
        yard staged, and its barrel pivot within 2 uu of where it is mounted; per
        shot, the direction the shot actually left on is within 6 deg of the barrel's
        world forward at that instant, and it appeared within 150 uu of that muzzle
assert: ShotsFlyStraightAtTheirOwnSpeed -- every frame, every live shot is within
        max(3% of S, 25 uu) of firstSeenPos + measuredDir * S * elapsed, where S is
        the FIRING TURRET's live ShotSpeedUu -- not anything the shot carries
assert: TheBarrelSwingsAtItsOwnRate -- every frame, each barrel's world orientation
        moved at most (its LIVE TraverseDegPerSec x dt x 3 + 1.5 deg) since the
        previous frame
assert: NoTurretFiresFasterThanItsOwnReload -- consecutive shots from one turret are
        at least 0.85 x the SMALLEST reload it advertised between them apart; and
        never more than 400 tracers alive at once
assert: EveryTurretTookAShotYouCanJudge -- at route end, each turret produced >= 1
        gradeable shot and the run produced >= 4 in total
assert: TheCharacterKeptTheSpeedTheYardSet -- every frame, MaxWalkSpeed is within
        1 uu/s of what the yard staged for the leg in progress
assert: TheYardWalkedTheWholeRoute -- at the sentinel: all nine stops reached and
        both re-tunes done
assert: TheTurretsKeptTheirFourNumbers -- every frame, both turrets still expose all
        four numbers readably by name, and still carry a base, a barrel and a muzzle
```

The checkpoint schedule is every 10 s to 220 s with a **sentinel at t = 300 s**,
because `ACraftBenchFunctionalTest::Tick` ends the test the moment the last scheduled
checkpoint is sampled. A healthy run does **not** reach the sentinel: the fixture
finishes itself 6 s after the last stop, once the totals have been taken and the
shots still in the air have landed. The sentinel exists so a run that stalled in
phase 1 cannot read green on the strength of the legs it did walk.

## Requirement-to-assertion map

| Prompt requirement | Gate | When that gate does not run |
|---|---|---|
| a shot connects within **120 cm** of the middle of the character | `ShotsFromTheOpenConnect` | for a shot fired while the character was accelerating, turning, standing still, out of that turret's reach, within 0.5 s of a re-tune, or with a flight longer than the leg has left |
| **every** shot taken in the open has to connect | the same gate, per shot, no averaging | same |
| aim at where they are going, not where they are | the same gate: aim-at-current misses by 1080 uu on leg A | same |
| a turret must have taken judgeable shots at all | `EveryTurretTookAShotYouCanJudge` | never |
| fire only inside **that turret's own** engagement distance | `NothingIsFiredBeyondItsOwnReach` | in the 1.0x–1.25x band, which forgives measuring range from the muzzle rather than the turret |
| fire only when a straight shot at **that turret's own** speed would genuinely meet them | `NothingIsFiredWithNowhereToAim` | inside the 1.25x / 0.25x margins, which forgive every borderline case |
| outrunning a shot is not on its own a reason to hold | `TheTurretsActuallyEngage`, on leg D | for windows too short to demand a shot |
| whenever both hold, take the shot, and keep taking it | `TheTurretsActuallyEngage` | same |
| as often as **that turret's own** reload allows | `NoTurretFiresFasterThanItsOwnReload` | never |
| a shot leaves along wherever the barrel is actually pointing | `TheBaseIsBoltedDownAndTheBarrelDoesTheAiming` (6 deg) | never |
| the barrel swings at **that turret's own** rate; it does not snap | `TheBarrelSwingsAtItsOwnRate` | for the first two graded frames |
| the base is bolted and does not turn; the barrel turns on the spot | `TheBaseIsBoltedDownAndTheBarrelDoesTheAiming` | never |
| a shot travels dead straight, at that turret's own speed, never pulled down | `ShotsFlyStraightAtTheirOwnSpeed` | for shots fired within 0.5 s of a re-tune |
| the four numbers are readable on the turret and change under you | `TheTurretsKeptTheirFourNumbers` + every gate above reading them live | never |
| how fast the character can move is not yours to change | `TheCharacterKeptTheSpeedTheYardSet` | never |
| where the turrets stand is not yours to change | the bolted-down gate, every frame | never |
| the whole run happened | `TheYardWalkedTheWholeRoute` | never |
| C++ under `Source/ThirdPerson/` | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

## Reference solution metadata

`reference/Source/ThirdPerson/Tasks/t2-turret-leads-you-and-holds-fire/` — the same
four files as the scaffold, differing **only** in the parts the agent is asked to
write: `PrimaryActorTick.bCanEverTick` flipped to `true`, one static
`SolveIntercept`, and one `Tick` body. ~110 lines of decision.

Every frame the reference reads `ShotSpeedUu` and `EngageRangeUu` off itself, solves
`(|V|^2-s^2)t^2 + 2(D.V)t + |D|^2 = 0` from the **muzzle** to the character's actor
location, takes the **smallest positive** root (not the smaller root — when the
target outruns the shot both roots share a sign), and returns without doing anything
at all when there is none. Otherwise it commands the barrel at the meeting point and
lets the servo get as far as it can this frame. It then fires only if the character
is inside its own reach, the trigger is free, and the barrel's forward vector is
inside a cone **derived from the disclosed 120 cm** rather than picked:
`asin(42 / range-to-meeting-point)`, spending a third of the stated allowance on
aiming error. Measured against that cone: at leg A's 2196 uu the cone is 1.1 deg and
the aim point moves 0.12 deg per frame, so it converges with an order of magnitude
in hand; a fixed 4 deg cone would land 156 uu at that range and fail.

Numbers the reference is calibrated against, all computed from the route geometry:

| At leg A abeam (2196 uu, 460 uu/s shot, 260 uu/s target, 5.79 s flight) | closest approach |
|---|---|
| converged intercept solve | 0 uu |
| barrel 1 deg off | 38 uu |
| barrel 2 deg off | 77 uu |
| barrel 4 deg off | 157 uu — **over the bar** |
| single-iteration lead (`pos + vel * dist/speed`) | 184 uu |
| horizontal-only solve, barrel left level | 224 uu |
| aim at the character's current position | 1080 uu |
| fired with the barrel still parked | 2196 uu |

## Anti-gaming notes

1. **Point the barrel straight at the answer.** *Failure mode*: the aiming control
   feels restrictive, so `Barrel->SetWorldRotation(Solution)` every tick — one line,
   in a file the agent owns, and it satisfies "the shot left along the barrel"
   exactly. It would delete the entire trigger-against-servo problem this task is
   built on: with no swing, firing in the same breath as aiming is never wrong.
   *Defense*: `TheBarrelSwingsAtItsOwnRate` measures the barrel's own world
   orientation frame to frame against its live `TraverseDegPerSec`, so the servo is
   effectively mandatory whether or not `AimBarrel` is used. The allowance is three
   frames of legal slew plus 1.5 deg — a snap to a 90 deg solution is caught by more
   than ten times over, and no tick-order jitter can false-FAIL correct work.
2. **Spawn shots straight from `Tick`, ignoring the trigger.** *Failure mode*: the
   reload is inconvenient, so the projectile is spawned directly; or homing is bolted
   on to force the hits; or the shot is quietly launched faster to shrink the flight
   time and with it the whole lead problem. *Defense*: three separate gates, none of
   which read anything the shot carries. `NoTurretFiresFasterThanItsOwnReload` caps
   the rate at the smallest reload that turret advertised between two shots;
   `ShotsFlyStraightAtTheirOwnSpeed` compares the sampled path against the **firing
   turret's live** number; and `TheBaseIsBoltedDownAndTheBarrelDoesTheAiming` needs
   the shot to have appeared at a muzzle and left along that barrel. A projectile
   that carries no `TurretShot` tag is not seen at all — and then
   `TheTurretsActuallyEngage` and `EveryTurretTookAShotYouCanJudge` fail as if
   nothing had been fired, which is what happened.
3. **Rotate the turret instead of the barrel.** *Failure mode*:
   `SetActorRotation(FindLookAtRotation(...))` — the single most natural first pass
   at "make the turret aim", and one that works mechanically, since the barrel is
   attached and the shots would connect. *Defense*: the bolted gate compares the
   actor's quaternion, the `TurretBase` component's quaternion and the barrel
   pivot's world **location** against what the yard staged, every frame, to 0.5 deg
   and 2 uu. The base mesh is authored **movable** on purpose, so this really does
   rotate rather than being blocked by mobility and scored as some other failure.
4. **Cache the four numbers in `BeginPlay`.** *Failure mode*: read once, keep. It is
   correct for the whole of phase 1 — the map's authored values are the phase-1 set
   — and wrong about all eight numbers from the first re-tune onward. *Defense*: the
   sets are re-staged twice through reflection, the two turrets are never within
   500 uu/s or 1000 uu of each other, and the route itself re-derives from the new
   numbers. After re-tune 1 the ex-short turret sits silent inside its new 4200 reach
   (`TheTurretsActuallyEngage`) while the ex-long turret opens up from 4000 uu away
   with a 1500 reach (`NothingIsFiredBeyondItsOwnReach`).
5. **One blanket hold-fire rule.** *Failure mode*: "if the target is faster than my
   shot, hold" — the most plausible simplification of the existence test, and one
   that is right on the sprint-away leg. *Defense*: leg D. The character charges a
   460 uu/s gun at 520 uu/s with the across-sight component peaking at 154 against a
   368 bar, so an interception plainly exists; the window is 5.7 s against a 1.5 s
   reload and the gate names the turret and the silence. "Hold whenever receding OR
   faster" and a float-equality barrel-convergence test die on the same leg.
6. **Solve, then fire in the same breath.** *Failure mode*:
   `if (IsReloaded() && HasSolution) { AimBarrel(R); FireNow(); }`. It works
   perfectly once the barrel has converged, which is exactly what makes it a real
   trap. *Defense*: leg B. T2 has sat idle for ~40 s with its barrel parked pointing
   +Y, and its window opens 6.7 s into a leg the character is already walking
   steadily with 16 s left, so the first shot is fully gradeable and leaves ~90 deg
   wide — 1517 uu against a 120 uu bar.
7. **Fire whenever in range, with no existence test.** *Failure mode*: no test at
   all, or an unguarded `sqrt` of a negative discriminant that yields NaN and fires
   along it, or the extrapolate-and-shoot shape (`pos + vel * dist/speed`) which
   produces a direction in every case and therefore never holds. *Defense*: leg C
   gives three reload-spaced chances to fail `NothingIsFiredWithNowhereToAim` while
   sitting comfortably inside a 4200 reach.
8. **Never fire at all.** *Failure mode*: the submission that passes all three
   hold-fire gates for free — and the shape the inert scaffold already has.
   *Defense*: `TheTurretsActuallyEngage` fires at the first window close, ~26 s in,
   and `EveryTurretTookAShotYouCanJudge` catches the subtler version where the
   convergence cone is so tight the turret never converges on a moving aim point.

## Hidden invariants

- **The base fixture declares SUCCESS the moment the last scheduled checkpoint is
  crossed**, so the schedule carries a sentinel at 300 s, ~160 s past the route, and
  the end-of-run totals are evaluated at route completion + 6 s (or at the sentinel,
  whichever comes first). Nothing is evaluated twice and nothing is skipped.
- **Firing windows are moving-only.** A stationary target always has an
  interception, so counting dwells would merge every leg into one enormous window
  that three shots at a standing character would satisfy — and legs A and D, the two
  legs that carry the engage duty, would prove nothing. The 200 uu/s floor is what
  makes the dwell a break rather than part of the window.
- **The re-tunes happen 1.5 s into a dwell**, after the window that just closed has
  already been evaluated, so no window ever spans two sets of numbers and the
  demand is always read against the numbers that were live throughout it.
- **Shots fired within 0.5 s of a re-tune are neither speed-checked nor
  accuracy-graded**, because the fixture cannot say which of the two shot speeds was
  live when they left. They are stationary-target shots in every case.
- **The fixture solves from the barrel PIVOT, not the live muzzle.** The muzzle
  swings 230 uu with the barrel and the barrel belongs to the submission; a window
  definition that moved with it would be a window definition the submission could
  shift. The pivot's world location is separately gated to 2 uu.
- **`FMath::RInterpConstantTo` is not used and must not be.** It clamps Pitch, Yaw
  and Roll independently, so a diagonal swing runs up to sqrt(2) faster than the
  advertised rate — which would make `TraverseDegPerSec` a lie and
  `TheBarrelSwingsAtItsOwnRate` unmeasurable. `AimBarrel` uses `FQuat::Slerp` clamped
  by `FQuat::AngularDistance`, which is the FULL angle
  (`acos(2*dot^2 - 1)`, `Quat.h:1228`).
- **The muzzle sits at 320 uu and the character's centre at 96.** A horizontal-only
  solve that leaves the barrel level passes 224 uu over the target's head — a fixed
  1.87x the tolerance at every range, which is what makes the 2D shortcut a real
  failure rather than a coin flip.
- **The turret base is authored MOVABLE.** A static root would make
  `SetActorRotation` a mobility warning rather than the named failure it should be.
- **The tracer's lifespan (16 s) exceeds the longest demanded flight (8 s) plus the
  1.5 s settle**, so no accuracy verdict is ever lost to a shot expiring first.
- **Nothing in any gate reads a light, a material or a rendered pixel** — component
  world rotations, actor locations and per-frame actor positions only — so the
  certified headless `-nullrhi` lane measures exactly what a windowed `--visible`
  run would.
