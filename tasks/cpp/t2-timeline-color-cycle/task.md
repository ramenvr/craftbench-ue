---
id: t2-timeline-color-cycle
substrate: CraftBenchTemplate
set: cpp
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_ColorCycle :: AColorCycleFunctionalTest"]
---

# t2-timeline-color-cycle

A display actor whose color must cycle continuously and smoothly through
green → blue → red → back to green, forever, published through a readable
material parameter. Sourced from an earlier internal task list (not shipped) ("Changing colors
with timeline test"). The source row's core metric — "in
the relevant blueprints timeline NODES are being used instead of something
else" — is CUT with provenance: Blueprint-graph introspection is a denied
read route (the footstep-cues precedent) and no source-inspection lane
exists; the timeline-QUALITY observable — smooth, continuous, ordered
interpolation — IS the grade.

## Primary concept

- `material-instance-dynamic` — UMaterialInstanceDynamic
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/UMaterialInstanceDynamic)

The load-bearing concept is driving a runtime material parameter from
gameplay code continuously over time — the timeline-shaped skill the source
row tests, graded through the parameter trace rather than through the
implementation's node graph.

## Prompt given to the agent

> The level contains a display actor (a visible cube, tagged `ColorCycle`)
> that today renders in one fixed color. Make its color cycle, forever:
>
> - The color must move smoothly through green, then blue, then red, then
>   back to green — a full cycle every 6 seconds (green at the start of a
>   cycle, blue one third in, red two thirds in), blending gradually between
>   those colors at every moment. It must never snap or jump from one color
>   to the next.
> - The cycle must keep running for as long as the game runs — it must not
>   stop after one pass.
> - The actor's CURRENT color must be readable at any moment from a vector
>   parameter named exactly `CycleColor` on the material of the actor's
>   visible mesh — keep that parameter updated as the color moves.
>
> The change belongs to the actor type itself — any instance of this actor
> must behave this way with no per-instance setup. Implement in C++ in the
> existing gameplay module — do not edit the level, any config file, or any
> test file.

## Workspace state pre-task

Files that **exist** under `Source/CraftBenchTemplate/`:

- `CraftBenchTemplate.Build.cs` — already depends on `Core`, `CoreUObject`,
  `Engine`, `InputCore`, `FunctionalTesting`. No edit needed.
- `Tasks/t2-timeline-color-cycle/ColorCycleActor.h` / `.cpp` — declares and
  defines `class CRAFTBENCHTEMPLATE_API AColorCycleActor : public AActor`.
  The constructor builds a visible engine-cube mesh component (movable, no
  collision) as the root and adds the `ColorCycle` tag. Ticking is disabled;
  no color logic ships.
- `Content/Maps/t2-timeline-color-cycle/L_ColorCycle.umap` — one placed
  `AColorCycleActor` (tagged `ColorCycle`) and the test harness actor.

Files that **do not exist**:

- No dynamic material instance, no color logic, no Blueprint subclass, no
  level edits. Solve in C++ by editing the existing actor type in place; do
  not rename the class — the level's placed instance of it is what gets
  graded.
- No test source in the agent's writable path. The test harness lives in a
  separate `CraftBenchTests` module the agent cannot read or modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t2-timeline-color-cycle/L_ColorCycle.umap`. The engine ticks
the world at a fixed deterministic step (`-deterministic -FPS=60`).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "CraftBenchTemplateEditor Win64
        Development" and "CraftBenchTemplate Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

```text
AColorCycleFunctionalTest (derives ACraftBenchFunctionalTest):
    PrepareTest():
        resolve the actor via GetAllActorsWithTag("ColorCycle");
        assert exactly one
        SetCheckpointSchedule({1.0, 10.0})
    Tick (every frame, after the base checkpoint clock):
        re-probe the actor's static-mesh components for a dynamic material
        instance with a READABLE "CycleColor" vector parameter (enumeration
        cannot discover override-added names — the disclosed name is the
        contract); once found, append the current value to the trace
    OnCheckpoint(0) t=1.0:
        assert a readable CycleColor exists
        ("no readable CycleColor parameter on the actor's mesh material");
        reset the trace (the graded window is exactly cp0 -> cp1)
    OnCheckpoint(1) t=10.0 — gates over the ~540-sample trace, in order:
        (0) readability: >= 2 samples were collected
                        ("no color samples could be read")
        (1) movement:   largest channel range >= 0.2
                        ("the color never changes")
        (2) smoothness: max single-frame component delta <= 0.15
                        ("the color snaps instead of blending smoothly")
        (3) order:      dominant-channel runs (margin 0.15, blend midpoints
                        skipped) visit green, blue AND red, and every
                        transition is G->B, B->R or R->G
                        ("does not cycle through green, blue and red in order")
        (4) period:     median FULL (window-interior) dominant-run length in
                        [1.2s, 3.2s] — the disclosed 6s cycle dominates each
                        anchor ~1.7s after the margin trim
                        ("the cycle period is far from the required six seconds")
        (5) continuity: >= 3 dominant-run transitions across the 9.0s window
                        ("the color stops cycling partway")
        -> Succeeded
    the MID is re-resolved EVERY frame (never cached), so a solution that
    recreates its dynamic material instance per tick still reads correctly.
    cp1 logs "[t2-colorcycle calib] ... samples= runs= transitions=
    maxdelta= range= medianrun=" (LogTemp/Display) for calibration.
```

**Pass criteria**: both L1 targets and L2 green. **Robust identity**: the
actor is resolved by tag, never by class; the color is read through the
disclosed parameter contract, so the implementation (timeline node, tick
lerp, curve asset) is free.

## Reference solution metadata

- LOC range: 25-40 (BeginPlay creates the dynamic material instance; Tick
  computes the 6s phase and piecewise-lerps between the three anchors;
  one SetVectorParameterValue per frame)
- Files touched: 2 (the pre-existing `ColorCycleActor.{h,cpp}`)
- Senior-dev hours: under 1

## Anti-gaming notes

1. **Set-once color.** *Failure mode*: the agent creates the material
   instance and sets `CycleColor` to green once — the parameter is readable,
   L1 passes, and a spot check at one instant could read a plausible color.
   *Defense*: the fixture traces the color EVERY frame for 9 seconds and
   requires real movement; a static color FAILs via the named message
   `the color never changes`.
2. **Snap cycling (no blending).** *Failure mode*: a repeating timer flips
   the color instantly green→blue→red on the right period — order, coverage
   and period all read correct at any sampling instant. *Defense*: the
   per-frame trace bounds the largest single-frame color change; blending
   along the disclosed cycle moves a channel ~0.008 per frame while an
   instant flip is a 1.0 jump — a snap FAILs via `the color snaps instead of
   blending smoothly`.
3. **Wrong sequence.** *Failure mode*: a smooth continuous cycle through the
   wrong order (green→red→blue) — movement, smoothness, and continuity all
   pass. *Defense*: the trace is collapsed into dominant-color runs and every
   transition must follow the disclosed cyclic order (G→B, B→R, R→G); a
   wrong-order cycle FAILs via `does not cycle through green, blue and red
   in order`.
4. **Right at an instant, wrong over time (stop or wrong speed).** *Failure
   mode*: a cycle that is perfect at any single sampling moment but wrong as
   a timeline — it freezes after one flawless pass, or it runs smoothly at
   the wrong speed (a 2s or 18s period). *Defense*: the trace judges the
   whole window — the median full dominant-run length must sit in a band
   around the disclosed period's per-color share (off-period cycles FAIL via
   `the cycle period is far from the required six seconds`), and the window
   must contain at least 3 dominant-run transitions where the disclosed 6s
   period yields 4-5 (a one-pass freeze leaves 2 and FAILs via `the color
   stops cycling partway`).
5. **Test disabling / environment repointing.** *Failure mode*: agent edits
   the fixture, the map, or config to weaken the gate. *Defense*:
   `Source/CraftBenchTests/` is sandbox-denied (submission files under it are
   rejected pre-grade), the runner materializes the graded substrate from git
   HEAD (an on-disk edit never reaches the grade; committed changes are
   review-gated on commit), and `Config/` + `Content/Maps/` are deny-listed.

## Hidden invariants

- The checkpoint instants, the smoothness cap, the dominance margin, the
  period band, and the transition floor are not disclosed — only the 6s
  period, the anchor order, and "never snaps" are. The gates are
  phase-agnostic: nothing depends on where in the cycle BeginPlay lands, so
  a solution keyed to absolute world time and one keyed to
  time-since-BeginPlay both grade identically.
- The judge is a per-frame trace, not sampling instants: order, smoothness,
  coverage and continuity are all read from the same ~540-sample window, so
  a shape that looks right at any finite set of spot checks but wrong in
  between still fails.
