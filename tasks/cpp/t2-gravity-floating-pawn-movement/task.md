---
id: t2-gravity-floating-pawn-movement
substrate: CraftBenchTemplate
set: cpp
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_GravityFloatingPawn :: AGravityFloatingPawnFunctionalTest"]
---

# t2-gravity-floating-pawn-movement

A hovering pawn that must obey gravity only when unattended: sink steadily
while no movement is requested, hold altitude (and translate) under movement
input, and start sinking again the moment input stops. Sourced from an
earlier internal task list ("Subobject class override"); the source row's
Verification cell is empty, so the acceptance criteria below are
authored here, and its core-metric code-shape check (the constructor
subobject-override idiom) is CUT — no source-inspection lane exists (L5 is
defined-only), so the idiom is the reference solution's implementation while
the GRADE is pure trajectory.

## Primary concept

- `default-pawn` — ADefaultPawn
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/ADefaultPawn)

The load-bearing concept is customizing the movement behavior a pawn type is
BORN with — the change must live in the type's own construction (the
subobject-class-override convention), not in per-instance or per-level setup.
Secondary: `movement-components` — Movement Components
(https://dev.epicgames.com/documentation/en-us/unreal-engine/movement-components-in-unreal-engine).

## Prompt given to the agent

> The level contains a hovering pawn placed high in the air. Today it floats
> in place forever and moves only when movement input is applied. Change its
> movement so that gravity applies exactly when the pawn is left alone:
>
> - While no movement input is being applied, the pawn must descend smoothly
>   and steadily — no jumps or snaps — at a rate between 150 and 800 units
>   per second once it is sinking, and the descent should reach its steady
>   rate within about half a second of going idle.
> - While movement input IS being applied, the pawn must hold its altitude
>   and translate as it does today; it must not lose height just because it
>   is moving.
> - When movement input stops, the descent must resume on its own.
>
> The change belongs to the pawn type itself — any instance of this pawn
> anywhere must behave this way with no per-instance setup. Implement in C++
> in the existing gameplay module — do not edit the level, any config file,
> or any test file.

## Workspace state pre-task

Files that **exist** under `Source/CraftBenchTemplate/`:

- `CraftBenchTemplate.Build.cs` — already depends on `Core`, `CoreUObject`,
  `Engine`, `InputCore`, `FunctionalTesting`. No edit needed.
- `Tasks/t2-gravity-floating-pawn-movement/HoverPawn.h` / `.cpp` — declares
  and defines `class CRAFTBENCHTEMPLATE_API AHoverPawn : public ADefaultPawn`
  with an `FObjectInitializer` constructor that stamps the `HoverPawn` tag.
  The pawn inherits the stock spherical collision + floating movement — it
  hovers indefinitely and never sinks. **No gravity behavior ships.**
- `Content/Maps/t2-gravity-floating-pawn-movement/L_GravityFloatingPawn.umap`
  — one placed `AHoverPawn` (tagged `HoverPawn`) high in clear air, plus the
  test harness actor.

Files that **do not exist**:

- No gravity logic, no movement-component subclass, no Blueprint subclass, no
  level edits. Solve in C++ by editing the existing pawn type in place (or
  swapping its movement component class); do not rename the pawn class — the
  level's placed instance of it is what gets graded.
- No test source in the agent's writable path. The test harness lives in a
  separate `CraftBenchTests` module the agent cannot read or modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t2-gravity-floating-pawn-movement/L_GravityFloatingPawn.umap`.
The engine ticks the world at a fixed deterministic step
(`-deterministic -FPS=60`). The fixture possesses the placed pawn itself — no
PlayerStart or game-mode dependency.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "CraftBenchTemplateEditor Win64
        Development" and "CraftBenchTemplate Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

```text
AGravityFloatingPawnFunctionalTest (derives ACraftBenchFunctionalTest):
    PrepareTest():
        resolve the pawn via GetAllActorsWithTag("HoverPawn");
        assert exactly one, and that it IS a pawn
        SpawnDefaultController() (possession mandatory — the stock floating
        movement gates its whole move on a possessing controller)
        SetCheckpointSchedule({0.5, 2.5, 5.0, 6.5})
    Tick (every frame, after the base checkpoint clock):
        continuity guard pair — any single-frame |dZ| > 30uu FAILs
        immediately ("discontinuous jump"; band-compliant motion moves
        <= ~13uu/frame at the fixed 60Hz step), and any rolling 0.25s
        window (16 samples) losing > 300uu FAILs ("descent rate burst
        beyond the allowed band"); both constants are derived for the
        spec's -FPS=60 leg
        while driving: AddMovementInput(+X, 1.0) (consumed per frame)
    OnCheckpoint(i):
        cp0 t=0.5: record Z0 (phase anchor)
        cp1 t=2.5: D_A = Z0-Z1 over 2.0s idle;
                   assert D_A >= 300  ("does not sink while idle")
                   assert D_A <= 1600 ("faster than the required band")
                   start driving
        cp2 t=5.0: assert lateral X progress >= 200uu since cp1
                   ("no lateral movement under input");
                   assert driven Z loss <= 0.25 * D_A
                   ("sinks while movement is applied"); stop driving
        cp3 t=6.5: assert resume drop (1.5s idle) >= 0.3 * D_A
                   ("sinking does not resume after input ends")
                   -> Succeeded
    every checkpoint logs "[t2-gravpawn calib] cp<i> t=<t> z=<z> x=<x>"
    (LogTemp/Display) for tolerance calibration.
```

**Pass criteria**: both L1 targets and L2 green. **Robust identity**: the
pawn is resolved by tag, never by class; every gate except the disclosed
band is a ratio of the run's own phase-A measurement.

## Reference solution metadata

- LOC range: 30-45 (a floating-movement subclass — ~25 LOC — whose tick adds
  a capped-rate descent when no input is pending, plus a one-line
  subobject-class-override in the pawn constructor)
- Files touched: 4 (2 new: the movement subclass pair; 2 pre-existing:
  `HoverPawn.{h,cpp}` constructor edit)
- Senior-dev hours: under 1

## Anti-gaming notes

1. **Empty/partial submission.** *Failure mode*: the scaffold compiles
   unchanged; the stock floating movement has no gravity, so the pawn hovers
   forever. L1 passes. *Defense*: the idle phase asserts a minimum descent;
   an unmodified pawn measures ~0 drop and FAILs via the named message
   `the pawn does not sink while idle`.
2. **Unconditional gravity.** *Failure mode*: gravity is applied always —
   idle-phase descent looks right, but the pawn also loses height whenever it
   moves. *Defense*: the driven phase feeds movement input for 2.5s and
   ratio-gates the altitude loss against the run's own idle-phase drop; an
   always-sinking pawn FAILs via `the pawn sinks while movement is applied`.
3. **Teleport-down on a timer (coarse or fine steps).** *Failure mode*: a
   repeating timer relocates the pawn downward in steps sized so the
   per-checkpoint average lands inside the disclosed rate band — possibly
   fine steps gated on the pawn's own velocity so the driven and resume
   phases also read correct. *Defense*: a continuous continuity guard PAIR
   bounds step amplitude the whole test. Motion inside the band moves at
   most ~13 units per fixed 60Hz frame; any single-frame altitude change
   beyond ~2x that FAILs immediately via `altitude changed by a
   discontinuous jump`, and any rolling quarter-second losing more than 1.5x
   the band ceiling FAILs via `descent rate burst beyond the allowed band`.
   The guards cannot forbid stepping outright — they force any stepped
   descent to be so fine-grained it is indistinguishable from smooth
   in-band motion.
4. **One-shot gravity (no resume).** *Failure mode*: descent works until the
   first movement input, then a latch disables it permanently — the idle and
   driven phases both look right. *Defense*: a third phase releases input and
   asserts the descent restarts, ratio-gated against the idle phase; a
   latched solution FAILs via `sinking does not resume after input ends`.
5. **Test disabling / environment repointing.** *Failure mode*: agent edits
   the fixture, the map, or config to weaken the gate. *Defense*:
   `Source/CraftBenchTests/` is sandbox-denied (submission files under it are
   rejected pre-grade), the runner materializes the graded substrate from git
   HEAD (an on-disk edit never reaches the grade; committed changes are
   review-gated on commit), and `Config/` + `Content/Maps/` are deny-listed.

## Hidden invariants

- The checkpoint instants, the phase durations, the ratio gates (0.25 / 0.3),
  and both continuity thresholds (30uu/frame, 300uu per rolling 0.25s) are
  not disclosed in the prompt — only the 150-800 uu/s band and the
  half-second ramp expectation are. The continuity defense is not a sampling
  instant but a per-frame guard pair that bounds step amplitude across the
  whole run; a stepped descent that survives it is necessarily fine-grained,
  band-rate motion.
- The fixture possesses the pawn itself in PrepareTest. Gravity implemented
  inside the movement component's controller-gated path only starts at
  possession — which is fine, the phase-A anchor is taken at cp0 — but a
  solution keyed to BeginPlay-time possession state reads "unpossessed" and
  may never sink at all; the type must behave correctly whenever it is
  possessed, per the prompt's "any instance, no per-instance setup" clause.
