---
id: t2-homing-projectile
substrate: CraftBenchTemplate
set: cpp
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_HomingProjectile :: AHomingProjectileFunctionalTest"]
---

# t2-homing-projectile

Ported from an earlier internal task list (not shipped) ("Homing missile" — C++/Gameplay:
*"Testing its understanding of non-trivial projectile implementation"*).
Probes runtime projectile motion + continuous steering. The source row's raw
verification idea ("should use a projectile movement component of some kind")
is an implementation-pattern check the prompt may not name (Hard Rule #2), so
the behavior is made observable instead: **the fixture relocates the target
mid-flight** — only genuine homing keeps closing and intercepts.

## Primary concept

- `gp-projectiles` — Projectile movement / steering
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/projectiles-in-unreal-engine)

Continuous runtime motion driven by a per-tick steering rule (however
implemented: `UProjectileMovementComponent` homing, manual velocity
integration, etc. — the verifier checks the trajectory, not the mechanism).

## Prompt given to the agent

> The level contains two placed actors: a launcher and a target, roughly
> 2000 units apart. When gameplay begins, the launcher must fire exactly one
> projectile actor tagged `HomingMissile`. The projectile must travel
> continuously — no teleporting — at a speed between 600 and 1200 units per
> second, and it must steer toward the target for its entire flight: if the
> target moves mid-flight, the projectile must adjust course and still reach
> it. The projectile counts as arrived when it comes within 150 units of the
> target (it may then destroy itself or keep flying); arrival must happen
> within 3 seconds of play start. Implement in C++ in the existing gameplay
> module — do not edit the level and do not edit any test file.

## Workspace state pre-task

Files that **exist** under `Source/CraftBenchTemplate/`:

- `Tasks/t2-homing-projectile/MissileLauncherActor.h` / `.cpp` — declares
  `AMissileLauncherActor : public AActor`; constructor adds
  `Tags.Add(FName("MissileLauncher"))`. **No behavior is implemented.**
- `Tasks/t2-homing-projectile/MissileTargetActor.h` / `.cpp` — declares
  `AMissileTargetActor : public AActor`; constructor adds
  `Tags.Add(FName("MissileTarget"))` and a movable scene root. No behavior.
- `Content/Maps/t2-homing-projectile/L_HomingProjectile.umap` — persistent
  level with one placed launcher, one placed target ~2000 units away, and
  the functional-test fixture.

Files that **do not exist**:

- No projectile class, no BeginPlay overrides, no Blueprint content. The
  projectile class (and any launcher changes) are the agent's to author
  under the writable module.
- No test source in the agent's writable path.

## Verifier specification

PIE from `Content/Maps/t2-homing-projectile/L_HomingProjectile.umap`,
`-deterministic -FPS=60`. Fixture `AHomingProjectileFunctionalTest`
(derives `ACraftBenchFunctionalTest`).

```text
PrepareTest():
    exactly one MissileLauncher; exactly one MissileTarget
    InitialDistance = |launcher - target|          (~2000)
    SetCheckpointSchedule({0.5, 1.0, 1.5, 2.2, 3.0})

Tick (Super::Tick first):
    MinDistanceSeen = min over frames of |missile - target|

OnCheckpoint(i):
    if MinDistanceSeen < 150: SUCCEED            (early — destroy-on-hit OK)
    cp0: exactly one HomingMissile; d > 0.55 * InitialDistance
    every cp>0, pre-interception:
        missile still exists (named: "disappeared before reaching")
        closed = d_prev - d
        closed <= 1200 * dt * 1.3                (named: teleport/impossible rate)
        closed >= 50                             (named: "not closing ... after the target relocated")
    cp1: AFTER the checks, relocate the target +800 units laterally;
         re-baseline d_prev against the moved target
    cp4: FAIL if never intercepted (named: "never came within 150 units")
```

Calibration lines are logged as `[t2-homing calib] cp<i> t=<t> d=<d> ...`
(LogTemp/Display) for tolerance review; they are diagnostic only.

## Reference solution metadata

- LOC range: 60–100 (a projectile actor with a movement/steering component
  configured for homing + a launcher BeginPlay that spawns it and sets the
  target; or manual per-tick velocity steering)
- Files touched: 2 edited (launcher pair) + 2 new (projectile pair)
- Senior-dev hours: 0.5–1.5

## Anti-gaming notes

1. **No projectile / empty submission.** *Failure mode*: L1 builds, nothing
   flies. *Defense*: checkpoint 0 (0.5s) asserts exactly one actor tagged
   `HomingMissile` exists in flight.
2. **Straight-line shot (no homing).** *Failure mode*: fire once at the
   target's initial position — intercepts a stationary target just fine.
   *Defense*: at t=1.0s the fixture **relocates the target +800 units
   laterally**; subsequent checkpoints assert the projectile keeps closing
   on the *current* target position and ultimately arrives — a
   straight-line shot stops closing and fails the named assertion.
3. **Teleport / SetActorLocation cheat.** *Failure mode*: jump the
   projectile to the target. *Defense*: per checkpoint interval the closed
   distance is capped at the disclosed max speed (1200 u/s ×dt, +30%
   slack); an instantaneous jump shows an impossible closing rate.
4. **Spawn-at-target.** *Failure mode*: spawn the "projectile" already at
   the target. *Defense*: at 0.5s the projectile must still be beyond 55%
   of the initial launcher→target separation (1200 u/s covers at most ~600
   units by then).
5. **Test disabling.** *Failure mode*: edit the fixture. *Defense*:
   `Source/CraftBenchTests/` is sandbox-denied and the runner grades from
   git HEAD; committed changes are review-gated on commit.
