---
id: t1-screen-tint-cpp
substrate: ThirdPerson
set: cpp
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_TintTrack :: AScreenTintFunctionalTest"]
---

# t1-screen-tint

A screen effect that follows how fast the character is actually moving — as a
fraction of the top speed it has **right now**. The track changes that top speed
half way through, so an effect keyed to a constant tracks the first half
perfectly and is wrong by the ratio for the whole of the second.

Imported from the Startup Eval corpus row
`t1-runtime-postprocess-reacts-to-movement` (provenance and every deviation:
`notes.md`).

> **Built against the 2026-08-18 difficulty bar.** The corpus row is a
> two-state effect — resting value, active value — which is one `if`. What makes
> this version measure something is that the effect has to be **proportional**,
> to a denominator it has to **read from the world**, and that denominator
> **changes**. The measured reference reads 0.45 at 250 uu/s on the first leg and
> 0.45 at **130** uu/s on the second.

## Primary concept

- `runtime-postprocess` — driving a post-process setting from live gameplay state
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/post-process-effects-in-unreal-engine)

The load-bearing behaviour is **a continuous readout driven from measured motion
and normalised against a value that is not constant**. The grade never asks
*how*: a `Tick`, a timer, a material parameter or a settings write all pass
identically, and only one setting is graded.

## Prompt given to the agent

> The track has a screen effect fitted: a vignette that covers the whole level.
> It is already switched on and already visible, and it currently reads its
> resting value all the time.
>
> Make it follow how fast the character the player controls is **actually
> moving**. Standing still it reads its resting value; at the character's top
> speed it reads its full value; in between it is proportional. It must be within
> **0.12** of the right value, and must get there within **0.4 seconds** of a
> change.
>
> The character's top speed is **not a constant** — the track changes it part way
> through — so the effect has to be proportional to whatever that character can
> currently do, not to a number you decide now.
>
> The screen also carries a second, unrelated setting, supplied at a fixed value.
> Leave it exactly as you found it.
>
> The effect and the switch that sets it are already supplied. Nothing decides
> what to set it to. Do not edit the level, any config file, or any test file.
> Write your solution in C++ under `Source/ThirdPerson/`.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on
this substrate). `Source/CraftBenchTests/` is deny-listed and a submission file
under it is a SANDBOX-REJECT (exit 4), not a graded FAIL; so are
`Content/Maps/`, `Content/ThirdPerson/`, `Content/Characters/` and every
`Config/` file (no `config_allow` is declared by this task).

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t1-screen-tint-cpp/ScreenTintActor.h` / `.cpp` —
  `class THIRDPERSON_API AScreenTintActor : public AActor`, tagged `ScreenTint`.
  Supplied:
  - `Screen` — a `UPostProcessComponent`, **the root**, `bUnbound = true` so it
    applies wherever the character is standing, priority 10.
  - Both graded settings are **already overridden** in the constructor, so they
    are live from the first frame and nobody has to discover that an override
    flag exists: `VignetteIntensity` (the readout) and `SceneFringeIntensity`
    (the control).
  - `UPROPERTY(EditDefaultsOnly) float RestVignette = 0.f`,
    `float FullVignette = 0.9f`, `float SuppliedFringe = 0.6f`.
  - `UFUNCTION(BlueprintCallable) void SetVignette(float)` — the supplied switch,
    which sets the override flag and the value.
  - `UFUNCTION(BlueprintPure) float CurrentVignette() const`.
  - **No tick, no timer, no reference to the character, no call to
    `SetVignette` outside `BeginPlay`.** The whole decision is the agent's, **and
    it has to land on this class**: the actor is a placed instance in a map you
    cannot edit, so a subclass would never be instantiated.
- `Content/Maps/L_TintTrack.umap` — the staged
  track, committed binary. World Settings name NO game mode, so the level
  inherits `BP_ThirdPersonGameMode`. What is in it:

  | Element | Placement | Notes |
  |---|---|---|
  | Floor | 10,000 x 2,400, striped every 200 cm, **every fifth stripe bright** | pace reads by eye, and distance between two stills is countable |
  | Stripes | **non-colliding** | a 3 cm lip is a wall to anything moved by a swept `SetActorLocation` |
  | One `AScreenTintActor` | unbound, so where it stands does not matter | |
  | Side rails | along both edges | something to judge speed against |
  | PlayerStart | at the near end, facing down the track | |
  | Landmarks | two differently sized end posts | a moving camera is distinguishable from a still one |
  | Fixture | one placed `AScreenTintFunctionalTest` | |

- `cameras.json` (the camera-plan lane; not part of this release) — the
  presentation-only camera plan. Non-gating.

Files that **do not exist**:

- No effect logic of any kind, no Blueprint subclass, no level edits. The empty
  submission compiles (L1 green) and FAILs L2 the first time the character
  settles at half pace.
- No test source in the agent's writable path. `AScreenTintFunctionalTest`
  lives in the `CraftBenchTests` module the agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/L_TintTrack.umap` on the
**ThirdPerson** substrate, ticked at a fixed deterministic step
(`-deterministic -FPS=60`). Verification primitive:
**pie-checkpoint-sampling** with an every-frame readback of the post-process
component's settings, over a fixture-driven walk.

The drive is: **stand, half pace, flat out, stand — twice**, walking back the
way it came on the second leg so no teleport is needed. **Between the legs the
fixture writes a different `MaxWalkSpeed` onto the character** (0.52x), which is
the whole anti-hard-coding design.

**How "how fast" is measured.** The fixture grades against the character's own
velocity — which is derived from real motion, so a submission cannot fake it by
writing a number somewhere — lightly smoothed, and separately cross-checks it
against the ground the character actually covered. If the two disagree by more
than 60% the character is being teleported rather than walked, and the run ends
`HARNESS-PRECONDITION`.

**The effect is never judged during an acceleration ramp.** The gate only fires
once the speed fraction has held within 0.05 of the value its window opened at
for 0.4 s. (Comparing frame-to-frame instead would call an entire smooth ramp
"stable" and grade an effect that is legitimately still easing.)

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

```text
assert: TintTracksHowFastYouAreMoving -- whenever the speed has settled, the
        vignette is within 0.12 of rest + fraction * (full - rest), where
        fraction is measured speed over the top speed the character has NOW
assert: TintIsOffWhenYouStandStill    -- on each leg, at least one settled
        sample at a standstill reading the rest value
assert: TintReachesFullWhenYouRunFlatOut -- on each leg, at least one settled
        sample at >= 85% of top speed reading the full value
assert: TheOtherSettingWasLeftAlone   -- the supplied colour-fringe setting
        still reads what it was supplied at, every frame
assert: TheTrackRanBothLegs           -- the second leg happened, so the top
        speed really did change
```

When the tracking gate fires on the second leg, the fixture works out what the
effect **would** have read if it were still dividing by the first leg's top
speed, and says so in the message when that matches — so the commonest wrong
answer is diagnosed rather than merely failed.

The checkpoint schedule carries a **sentinel at t = 120 s**, far past the ~50 s
drive, because `ACraftBenchFunctionalTest::Tick` ends the test the moment the
last scheduled checkpoint is sampled.

**Staging faults are attributed, not scored.** A track with no tagged screen
actor, a screen actor that does not expose its three numbers readably, an effect
whose rest and full values are less than 0.3 apart (too small to grade against a
0.12 tolerance), or a character with no movement component all end the run as
`HARNESS-PRECONDITION`, never as a model failure.

## Anti-gaming notes

1. **Two states instead of proportional.** *Failure mode*: full effect whenever
   the character is moving, rest when it is not — the shape the corpus row
   actually asked for, and one `if`. *Defense*: the gate compares against
   `rest + fraction * (full - rest)` at every settled sample, and the drive spends
   8 seconds per leg at **half** pace. A two-state answer reads 0.90 where 0.45
   is wanted and fails by 0.45 against a 0.12 tolerance.
2. **Dividing by a constant.** *Failure mode*: normalise against 500, or against
   whatever `MaxWalkSpeed` read at `BeginPlay`. *Defense*: the fixture changes
   the character's top speed to 260 for the second leg. Such an answer reads 0.23
   where 0.45 is wanted and 0.47 where 0.90 is wanted — and the failure message
   says *"it reads exactly what it would if it were still dividing by the 500
   uu/s top speed of the first leg"*.
3. **Driving off the setting instead of the motion.** *Failure mode*: compute the
   effect from `MaxWalkSpeed` alone, so it reads full the moment the character is
   allowed to run rather than when it is running. *Defense*: the fraction is
   measured from the character's velocity, and the drive stands still for four
   seconds at the start of each leg with the top speed unchanged — an answer keyed
   to the allowance reads full while the character is stationary and fails
   `TintIsOffWhenYouStandStill`.
4. **Touching the other setting.** *Failure mode*: write the whole
   `PostProcessSettings` struct, or reset it, taking the supplied colour-fringe
   value with it. *Defense*: `TheOtherSettingWasLeftAlone` reads it every frame
   and fails naming both values. This is not hypothetical — assigning a fresh
   `FPostProcessSettings` is the obvious way to set one field.
5. **Setting the number without the effect existing.** *Failure mode*: store the
   value on the actor and never put it on the component. *Defense*: the fixture
   reads the **component's** `Settings.VignetteIntensity`, which is what a viewer
   sees, and never the actor's own accessor.
