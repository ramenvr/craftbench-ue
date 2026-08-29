---
id: t2-ladder-climb-volume
substrate: ThirdPerson
set: cpp
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_LadderClimb :: ALadderClimbFunctionalTest"]
---

# t2-ladder-climb-volume

A climbable ladder on the **ThirdPerson substrate**: a possessed playable
character must ascend the marked ladder volume on request, hold when the climb
is ended, refuse to climb away from the ladder, and hand back to normal
gravity when it leaves the ladder's reach at the top. Sourced from an
earlier internal task list ("Ladder system" — the hardest row of its block);
the hold-a-key trigger is rephrased to the
substrate's programmatic `Do*` seam convention because headless PIE has no key
events (the tp2-sprint-stamina precedent), and the source row's "climb down" half
is cut as a second unverifiable input axis (the same rationale as tp2's
caps-lock cut: one verifiable axis per task). The verifier walks the character
to the ladder itself and judges the climb state machine purely from measured
height over time.

## Primary concept

- `char-movement` — Character Movement Component modes
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/movement-components-in-unreal-engine)

The load-bearing behavior is a volume-gated movement-mode state machine
(request / at-ladder gate / steady ascent / hold / exit-restore) on a
possessed character — overlap-driven locomotion state, the substrate surface
only ThirdPerson provides.

## Prompt given to the agent

> The level contains a ladder: a tall marked volume standing on the ground.
> Make the character the player controls able to climb it:
>
> - Expose two functions on the character named exactly `DoClimbStart` and
>   `DoClimbEnd`. Each takes no parameters and must be declared so the
>   engine's reflection system can find and call it (the character's existing
>   jump functions follow the same convention). `DoClimbStart` requests a
>   climb; `DoClimbEnd` ends it.
> - While a climb is requested AND the character is within the ladder's
>   volume, the character ascends smoothly and steadily at 300 units per
>   second — a continuous motion, not a jump or a snap.
> - A climb request made while the character is NOT at the ladder must do
>   nothing — no ascent, no floating.
> - When `DoClimbEnd` is called mid-climb, the ascent stops and the character
>   holds its height at the ladder until a new request or until it leaves the
>   ladder.
> - The moment the climbing character leaves the ladder's volume (for example
>   past its top), the climb ends and normal movement takes over — the
>   character falls under gravity as usual. Leaving the ladder also clears
>   any climb request: climbing again requires a new `DoClimbStart`.
>
> Correctness is judged by the character's measured height over time: no rise
> from an away-from-ladder request, a steady continuous rise while climbing
> at the ladder, height held after the climb is ended, and a normal fall once
> the character passes the ladder's top. Implement in C++ in the existing
> gameplay module — do not edit the level, any config file, or any test file.

## Workspace state pre-task

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources (`ThirdPersonCharacter`
  with its `DoMove`/`DoJumpStart`/`DoJumpEnd` input seams, game mode, the
  Variant_* trees). No edit needed, though the character sources show the
  house convention the new functions must follow.
- `Tasks/t2-ladder-climb-volume/LadderCharacter.h` / `.cpp` — declares and
  defines `class THIRDPERSON_API ALadderCharacter : public
  AThirdPersonCharacter` (concrete — the stock template character is abstract
  and unspawnable). Constructor adds `Tags.Add(FName("ClimbHero"))`. **No
  climb functions and no climb state ship** — the behavior is entirely the
  agent's to implement (on this class or on the writable stock parent; both
  grade identically).
- `Tasks/t2-ladder-climb-volume/LadderGameMode.h` / `.cpp` — a game mode
  whose constructor sets `DefaultPawnClass = ALadderCharacter::StaticClass()`.
  The task map's world settings select it, so PIE spawns and possesses the
  tagged character at the PlayerStart.
- `Tasks/t2-ladder-climb-volume/LadderVolumeActor.h` / `.cpp` — the ladder
  frame. Its constructor builds a tall query-only overlap box (half-extent
  60 x 60 x 600) as the root and adds `Tags.Add(FName("LadderVolume"))`. It
  ships no behavior; whether the climb logic reads it or the character's own
  overlaps is the agent's choice.
- `Content/Maps/t2-ladder-climb-volume/L_LadderClimb.umap` — a flat floor, a
  PlayerStart, one placed `ALadderVolumeActor` standing on the floor ~600
  units from the PlayerStart, and one placed `ALadderClimbFunctionalTest`.

Files that **do not exist**:

- No `DoClimbStart`/`DoClimbEnd` anywhere, no climbing state, no movement-mode
  changes. The empty submission compiles (L1 green) and fails L2 at the named
  seam gate.
- No test source in the agent's writable path. `ALadderClimbFunctionalTest`
  lives in a separate `CraftBenchTests` module the agent cannot read or
  modify.

## Verifier specification

The test runs in PIE from `Content/Maps/t2-ladder-climb-volume/L_LadderClimb.umap`
on the **ThirdPerson** substrate. The engine ticks the world at a fixed
deterministic step (`-deterministic -FPS=60`). The map's world settings select
`ALadderGameMode`, which spawns and possesses the `ClimbHero`-tagged character
at the PlayerStart.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

```text
ALadderClimbFunctionalTest (derives ACraftBenchFunctionalTest):
    PrepareTest():
        resolve hero via GetAllActorsWithTag("ClimbHero"); assert exactly one
        assert it is a walking character-type pawn
        resolve ladder via GetAllActorsWithTag("LadderVolume"); assert exactly
        one; read its world bounds once (center X ~600, top Z ~1200)
        resolve DoClimbStart/DoClimbEnd by reflection; assert each exists with
        no real input parameters
        (named failure: "... 'DoClimbStart' ... (climb seam missing).")
        SetCheckpointSchedule({0.6, 1.6, 4.0, 5.2, 9.8})
    Tick (every frame, after the base checkpoint clock):
        climb phases: per-frame ascent-continuity guard (one-frame rise > 50
        units -> named FAIL "ascent jumped discontinuously")
        walk phase:   Hero->AddMovementInput(toward the ladder) every frame;
                      on arrival (|X - ladderX| < 40) invoke DoClimbStart and
                      record the climb-start height
        second climb: record the moment the hero crosses the ladder's top
    OnCheckpoint(i):  // heights in world Z; guard: hero still valid
        cp0 t=0.6: record Z0 (settled at the PlayerStart); invoke DoClimbStart
                   AWAY from the ladder
        cp1 t=1.6: assert Z <= Z0 + 40  ("climb engaged away from the ladder")
                   invoke DoClimbEnd; start the walk (arrival ~2.7s)
        cp2 t=4.0: assert the at-ladder climb gained >= 150 units
                   ("no meaningful height gain"); invoke DoClimbEnd; record
                   the hold height
        cp3 t=5.2: assert |Z - hold| <= 60  ("hold its height after the climb
                   was ended"); invoke DoClimbStart again
        cp4 t=9.8: assert the ladder's top was crossed (top exit ~7.3-8.5s)
                   AND Z is now below top - 50 (gravity resumed)
                   ("still ascending or hovering after leaving the ladder")
                   -> Succeeded
    every checkpoint logs "[t2-ladder calib] cp<i> t=<t> z=<z> phase=<p>"
    (LogTemp/Display) for tolerance calibration.
```

**Pass criteria**: both L1 targets and L2 green. **Robust identity**: hero and
ladder resolved by tag, never by class; the climb seams by reflection, so the
agent may implement on the scaffold subclass or the stock parent.

## Reference solution metadata

- LOC range: 70-90 (header: two UFUNCTIONs, Tick override, two state flags;
  cpp: overlap check by tag, enter/hold/exit transitions on
  CharacterMovement, steady-velocity ascent)
- Files touched: 2 (both pre-existing scaffold files:
  `LadderCharacter.{h,cpp}`)
- Senior-dev hours: 0.5-1.0

## Anti-gaming notes

1. **Empty/partial submission.** *Failure mode*: the scaffold compiles with no
   climb functions at all; L1 passes. *Defense*: `PrepareTest` resolves both
   seams by reflection (`FindFunction("DoClimbStart"/"DoClimbEnd")`, no real
   input parameters allowed) and FAILs via the named message `climb seam
   missing` — FAIL-on-empty, not differs-from-reference.
2. **Location-free climb.** *Failure mode*: the seams fly the character upward
   wherever it stands — no ladder check at all. *Defense*: the fixture's first
   act is a `DoClimbStart` invoked AWAY from the ladder (~540 units out) with
   a full second of observation; any rise beyond settle jitter FAILs via
   `climb engaged away from the ladder`. (Growing the volume to cover the map
   is self-defeating: the away-probe stands inside it and the same gate
   fires.)
3. **Teleport to the top.** *Failure mode*: `DoClimbStart` at the ladder snaps
   the character to the top — right destination, no journey. *Defense*: from
   the moment the at-ladder climb is requested, every frame runs an
   ascent-continuity guard; a one-frame rise beyond 50 units (the disclosed
   steady rate moves ~5 units/frame) FAILs via `ascent jumped
   discontinuously`.
4. **Climb that never releases.** *Failure mode*: once climbing, the character
   ascends forever — the ladder's top edge is ignored and gravity never
   returns. *Defense*: the final checkpoint requires BOTH that the character
   actually crossed the ladder's top and that, given over a second of
   post-exit time, it has fallen back below the top; a riser/hoverer FAILs
   via `still ascending or hovering after leaving the ladder`.
5. **Test disabling / environment repointing.** *Failure mode*: agent edits
   the fixture, the map, or config to weaken the gate. *Defense*:
   `Source/CraftBenchTests/` is sandbox-denied (submission files under it are
   rejected pre-grade), the runner materializes the graded substrate from git
   HEAD (an on-disk edit never reaches the grade; committed changes are
   review-gated on commit), and `Config/` + `Content/Maps/` are deny-listed.

## Hidden invariants

- The checkpoint instants (0.6/1.6/4.0/5.2/9.8) and the fixture's walk/arrival
  timing are not disclosed in the prompt; only the climb rate is. A point-fit
  solution keyed to guessed sample times has five independent chances to miss.
- The away-side probe runs FIRST (0.6-1.6s), inside the window where a
  location-free climb is already rising — before the fixture has ever
  approached the ladder.
- The ascent-continuity guard is continuous (every climb-phase frame), not a
  checkpoint sample: there is no between-checkpoints window where a snap can
  hide.
- The final gate requires the top exit AND the fall-back — each of the two
  halves kills a different cheat (never-reached vs never-released).
