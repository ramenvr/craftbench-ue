---
id: tp2-sprint-stamina
substrate: ThirdPerson
set: cpp
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_TpSprint :: ASprintStaminaFunctionalTest"]
---

# tp2-sprint-stamina

First authentic gameplay task on the **ThirdPerson substrate** (tp0 proved the
routing; this one uses what the substrate is FOR — a possessed playable
character with tuned CharacterMovement). Sourced from an earlier internal task list (not shipped)
("Sprinting system"); the hold-a-key trigger is rephrased to
the substrate's programmatic `Do*` seam convention because headless PIE has no
key events, and the caps-lock walk-toggle from the source row was cut as a second
unverifiable input axis. The verifier drives the character forward every frame
and judges the sprint/stamina state machine purely from measured ground speed,
ratio-gated against the run's own baseline.

## Primary concept

- `char-movement` — Character Movement Component
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/movement-components-in-unreal-engine)

The load-bearing behavior is a gameplay state machine (sprint request /
drain / exhaustion / floor / regen) driving `UCharacterMovementComponent` max
ground speed on a possessed character — the substrate surface only ThirdPerson
provides.

## Prompt given to the agent

> The project's playable character moves on the ground at its existing maximum
> speed (about 500 units per second). Add a sprint system to the character the
> player controls:
>
> - Expose two functions on the character named exactly `DoSprintStart` and
>   `DoSprintEnd`. Each takes no parameters and must be declared so the
>   engine's reflection system can find and call it (the character's existing
>   jump functions follow the same convention). `DoSprintStart` requests a
>   sprint; `DoSprintEnd` ends it.
> - While sprinting, the character's maximum ground speed must be 1.7x its
>   normal value. The normal (non-sprinting) maximum ground speed must remain
>   unchanged at all times.
> - The character has a stamina value ranging 0 to 100, starting at 100. While
>   sprinting, stamina drains at 25 per second. While not sprinting, it
>   regenerates at 20 per second, capped at 100.
> - When stamina reaches 0, the sprint ends automatically and the character
>   returns to its normal maximum speed, even if `DoSprintEnd` was never
>   called.
> - A `DoSprintStart` request only takes effect if stamina is at least 30 at
>   the moment of the call. A request made below that threshold is ignored and
>   is not remembered — sprinting must not begin on its own later when stamina
>   climbs past the threshold; a new request is required.
>
> Correctness is judged by the character's measured ground speed while it is
> driven forward across flat ground: the unchanged baseline speed, the 1.7x
> ratio while sprinting, the automatic return to baseline when stamina runs
> out, a below-threshold request staying ignored, and sprinting working again
> after stamina has regenerated. Implement in C++ in the existing gameplay
> module — do not edit the level, any config file, or any test file.

## Workspace state pre-task

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources (`ThirdPersonCharacter`
  with its `DoMove`/`DoJumpStart`/`DoJumpEnd` input seams, game mode,
  the Variant_* trees). No edit needed, though the character sources show the
  house convention the new functions must follow.
- `Tasks/tp2-sprint-stamina/SprintCharacter.h` / `.cpp` — declares and defines
  `class THIRDPERSON_API ASprintCharacter : public AThirdPersonCharacter`
  (concrete — the stock template character is abstract and unspawnable).
  Constructor adds `Tags.Add(FName("SprintHero"))`. **No sprint functions, no
  stamina state, no Tick/BeginPlay override ship** — the behavior is entirely
  the agent's to implement (on this class or on the writable stock parent;
  both grade identically).
- `Tasks/tp2-sprint-stamina/SprintGameMode.h` / `.cpp` — a game mode whose
  constructor sets `DefaultPawnClass = ASprintCharacter::StaticClass()`. The
  task map's world settings select it, so PIE spawns and possesses the tagged
  character at the PlayerStart.
- `Content/Maps/tp2-sprint-stamina/L_TpSprint.umap` — a long flat runway along
  +X, a PlayerStart at the -X end facing +X, and one placed
  `ASprintStaminaFunctionalTest`.

Files that **do not exist**:

- No `DoSprintStart`/`DoSprintEnd` anywhere, no stamina member, no speed
  modification. The empty submission compiles (L1 green) and fails L2 at the
  named seam gate.
- No test source in the agent's writable path. `ASprintStaminaFunctionalTest`
  lives in a separate `CraftBenchTests` module the agent cannot read or
  modify.

## Verifier specification

The test runs in PIE from `Content/Maps/tp2-sprint-stamina/L_TpSprint.umap` on
the **ThirdPerson** substrate. The engine ticks the world at a fixed
deterministic step (`-deterministic -FPS=60`). The map's world settings select
`ASprintGameMode`, which spawns and possesses the `SprintHero`-tagged
character at the PlayerStart.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

```text
ASprintStaminaFunctionalTest (derives ACraftBenchFunctionalTest):
    PrepareTest():
        resolve pawn via GetAllActorsWithTag("SprintHero"); assert exactly one
        assert it is a walking character-type pawn
        resolve DoSprintStart/DoSprintEnd by reflection; assert each exists
        with no real input parameters
        (named failure: "... 'DoSprintStart' ... (sprint seam missing).")
        SetCheckpointSchedule({1.0, 3.0, 6.2, 7.0, 9.0, 10.5})
    Tick (every frame, after the base checkpoint clock):
        while running: Hero->AddMovementInput(+X, 1.0)   // sustains locomotion
    OnCheckpoint(i):  // Speed = Velocity.Size2D(); guard: valid + !IsFalling
        cp0 t=1.0:  assert 400 <= Speed <= 600; V0 = Speed; invoke DoSprintStart
        cp1 t=3.0:  assert 1.55 <= Speed/V0 <= 1.85          (stamina 50)
        cp2 t=6.2:  assert 0.85 <= Speed/V0 <= 1.15; invoke DoSprintStart
                    (stamina hit 0 at t=5.0; regen -> 24, below the 30 floor)
        cp3 t=7.0:  assert 0.85 <= Speed/V0 <= 1.15
                    (kills instant below-floor sprint AND a latched auto-start
                     when stamina crossed 30 at t=6.5)
        cp4 t=9.0:  assert 0.85 <= Speed/V0 <= 1.15; invoke DoSprintStart
                    (stamina ~80 — must take effect again)
        cp5 t=10.5: assert 1.55 <= Speed/V0 <= 1.85 -> Succeeded
    every checkpoint logs "[tp2-sprint calib] cp<i> t=<t> v=<v> ratio=<r>"
    (LogTemp/Display) for tolerance calibration.
```

**Pass criteria**: both L1 targets and L2 green. **Robust identity**: lookup by
the `SprintHero` tag, never by class; the sprint seam by reflection, so the
agent may implement on the scaffold subclass or the stock parent.

## Reference solution metadata

- LOC range: 70-95 (header: two UFUNCTIONs, Tick/BeginPlay overrides, stamina
  state + constants; cpp: capture base speed, gate/apply/revert, drain/regen)
- Files touched: 2 (both pre-existing scaffold files:
  `SprintCharacter.{h,cpp}`)
- Senior-dev hours: 0.5-1.0

## Anti-gaming notes

1. **Empty/partial submission.** *Failure mode*: the scaffold compiles with no
   sprint functions at all; L1 passes. *Defense*: `PrepareTest` resolves both
   seams by reflection (`FindFunction("DoSprintStart"/"DoSprintEnd")`, no real
   input parameters allowed) and FAILs via the named message `sprint seam
   missing` — FAIL-on-empty, not differs-from-reference.
2. **Permanent 1.7x boost.** *Failure mode*: `DoSprintStart` (or the
   constructor) sets max speed to 850 forever, no stamina at all. *Defense*:
   checkpoint 0 asserts the baseline is in [400,600] BEFORE any sprint request
   (a constructor boost dies here), and checkpoint 2 asserts speed reverted to
   baseline after the disclosed 4-second stamina budget (an unreverted
   `DoSprintStart` boost dies here).
3. **Cosmetic stamina.** *Failure mode*: a stamina variable exists and drains
   but never gates anything. *Defense*: three independent named assertions —
   auto-stop at 0 (cp2), below-threshold request ignored with no latching
   (cp3), regen re-enables a fresh request (cp5) — each of which a
   non-load-bearing stamina fails.
4. **Faking speed without locomotion.** *Failure mode*: teleports or velocity
   spoofing timed to satisfy point samples. *Defense*: the fixture itself
   drives movement input every frame; speed is sampled from CharacterMovement
   velocity with an on-ground guard (`IsFalling` FAILs), gated as a RATIO of
   the same pawn's measured baseline; checkpoint instants are not disclosed to
   the agent.
5. **Test disabling / environment repointing.** *Failure mode*: agent edits
   the fixture, the map, or config to weaken the gate. *Defense*:
   `Source/CraftBenchTests/` is sandbox-denied (submission files under it are
   rejected pre-grade), the runner materializes the graded substrate from git
   HEAD (an on-disk edit never reaches the grade; committed changes are
   review-gated on commit), and `Config/` + `Content/Maps/` are deny-listed.

## Hidden invariants

- The checkpoint instants (1.0/3.0/6.2/7.0/9.0/10.5) are not disclosed in the
  prompt; only the stamina constants are. A point-fit solution keyed to
  guessed sample times has six independent chances to miss.
- cp3 sits at t=7.0 — inside the window where BOTH cheats are still visibly
  sprinting: a floor-less implementation's illegal sprint (started at t=6.2
  with stamina 24) lives until ~7.16, and a latched below-threshold request
  auto-starting when regen crosses 30 at t=6.5 is at full speed by ~6.7 —
  distinguishing "ignored" from "deferred" without a dedicated leg. (Braking
  is friction-dominated — an over-max pawn settles in 1-2 frames — so
  sampling later would miss the floor-less cheat; calibrated 2026-07-23.)
