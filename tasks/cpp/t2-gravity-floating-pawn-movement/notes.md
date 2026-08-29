# Build notes — t2-gravity-floating-pawn-movement

Maintainer-facing. The agent never sees this file.

## Provenance

- Source row: an earlier internal task list (not shipped), "Subobject class
  override" (C++ / Actors & Components). Its prompt: *"Create a new c++ actor
  based on
  DefaultPawn that uses a customized version of floating movement component
  that has gravity when no input is being applied."*
- The source row's **Verification cell is EMPTY** — the acceptance criteria in
  `task.md` are authored here (footstep precedent: say so, do not invent a
  provenance).
- The source row's core metric is a code-shape check — *"use
  `Super(ObjectInitializer.SetDefaultSubobjectClass<UGravityFloatingPawnMovement>(ADefaultPawn::MovementComponentName))`
  in the constructor initializer list"*. **CUT from the gate** with
  provenance: no source-inspection lane exists (L5 is defined-only). The idiom
  IS the reference solution's implementation, and the
  prompt's "the change belongs to the pawn type itself — any instance, no
  per-instance setup" clause points at construction-time behavior — but the
  GRADE is pure trajectory. A solution that achieves the same three-phase
  behavior another way (e.g. a custom TickComponent on a plain
  UFloatingPawnMovement subclass wired some other construction-time way)
  passes, by design.

## Dead-gate audit (graded values vs UE 5.8 engine defaults)

Read from the engine install on this box
(`C:\Program Files\Epic Games\UE_5.8`):

| gate | engine default | verdict |
|---|---|---|
| idle sink >= 300uu/2.0s | stock `UFloatingPawnMovement` has **zero gravity tokens** (`Engine/Source/Runtime/Engine/Private/FloatingPawnMovement.cpp` — grep `Gravity` = 0 hits); an unmodified pawn measures ~0 drop | LIVE — excludes the default by two orders of magnitude |
| lateral progress >= 200uu/2.5s | stock ctor: `MaxSpeed=1200, Acceleration=4000, Deceleration=8000` (FloatingPawnMovement.cpp:14-16) → ~2,800uu expected | LIVE for ignores-input; deliberately generous |
| driven sink <= 0.25 × phase-A drop | ratio of the run's own measurement — no engine default to collide with | LIVE by construction |
| resume drop >= 0.3 × phase-A drop | same | LIVE by construction |
| continuity <= 30uu/frame | band ceiling moves 13.3uu/frame at the fixed 60Hz step; the cap is ~2x that | LIVE — only displacement can trip it |
| windowed rate <= 300uu per rolling 0.25s (16 samples) | band ceiling loses 200uu per 0.25s; the cap is 1.5x that | LIVE — bounds bursts of sub-per-frame steps |

**FPS-dependence of the continuity constants (load-bearing):** both guards
are derived FOR the spec's single `-FPS=60` leg (no `fps_legs` declared).
30uu/frame assumes a 1/60s frame — at 30fps a band-ceiling mover already
does 26.7uu/frame and would sit against the cap; the 16-sample window is
0.25s ONLY at 60Hz. If this task ever gains a second fps leg, both constants
must be re-derived (or the guards rewritten time-based) BEFORE the leg is
added — otherwise the guard falsely fails band-compliant references at lower
fps.

## Fixture design

- Base: `ACraftBenchFunctionalTest` (NOT the GAS pawn base — that resolves
  `ACraftBenchCharacter` subclasses; this pawn is a `ADefaultPawn` line).
- Possession: the fixture resolves the placed pawn by tag and calls
  `SpawnDefaultController()`. Possession is load-bearing twice over: an
  unpossessed pawn is inert, AND the stock floating movement gates its whole
  move (including input consumption) on `Controller && IsLocalController()`
  (`FloatingPawnMovement.cpp:38`). The reference's sink code runs OUTSIDE
  that gate (its own TickComponent body), so a placed-but-unpossessed
  reference pawn would sink before possession too — harmless: the phase-A
  anchor Z0 is taken at cp0, after possession.
- Drive: per-frame `AddMovementInput(+X, 1.0)` from the fixture Tick while
  `bDriving` (input is consumed per frame; never tick the world). Wave-1's
  teleport task proved AI-controller `AddMovementInput` consumption for
  `ACharacter`; the `ADefaultPawn`/`UFloatingPawnMovement` path is engine
  source-verified (`ApplyControlInputToVelocity` reads the pending vector,
  line 107) but **live-unproven** — calibration item 1.
- Three phases, traps INSIDE cheat windows: the always-sinks cheat is
  measured DURING the driven phase; the latch cheat is measured AFTER input
  ends; the stepped-teleport cheats (coarse AND fine/velocity-gated) are
  watched EVERY frame by the continuity guard pair (their average rates are
  band-plausible by construction — only amplitude bounding kills them). The
  guards bound step amplitude; they do not — cannot — forbid stepping
  outright: a descent stepped finer than ~30uu/frame AND under 300uu per
  0.25s is accepted as indistinguishable from smooth in-band motion at this
  frame rate (documented in the MATRIX coverage note).
- Error-precondition honesty (wave-1 convention): the fixture's
  `FinishTest(Error, "HARNESS-PRECONDITION: ...")` paths (no world,
  possession failed) still **grade as agent FAIL today** — automation Error
  lands as state Fail in index.json and `l2_pie.py` counts it; the prefix is
  the hook for a future runner-side routing rule, not a claim of exit-7
  routing.

## Map contract (mirrors `aids/author_L_GravityFloatingPawn.py` — keep in sync)

| element | value | why |
|---|---|---|
| template | `/Engine/Maps/Templates/Template_Default` | ships a WorldSettings |
| pawn | `AHoverPawn` at (0, 0, 6000) | needs **clear air below through cp3**: max band-compliant sink is 800uu/s × 6.5s = 5,200uu → worst-case end Z ≈ 800, still above the template floor at Z≈0 |
| fixture | `AGravityFloatingPawnFunctionalTest` at (0, 1200, 6000) | well clear laterally; a functional-test actor is not physics-simulated |
| PlayerStart / GameMode | none | the fixture possesses the placed pawn itself |

The driven phase moves the pawn up to ~2,800uu along +X — it stays airborne
the whole run, so leaving the template floor's footprint is irrelevant.

## Calibration checklist (fill from the first live run)

1. **AI-controller input consumption on `ADefaultPawn`** — the load-bearing
   unproven step. Engine source says the pending input vector is consumed
   under any local controller, but no CraftBench fixture has driven a
   floating-movement pawn yet (teleport proved `ACharacter` +
   CharacterMovement only). *Fallback if it does not consume*: a genuinely
   different path — write `Velocity` directly on the movement component
   during the drive phase, or scripted `SetActorLocation` sweeps for the
   lateral phase. (NOT `AddInputVector`: that feeds the same pending-input
   vector through the same `IsLocalController`-gated consumption and would
   fail the same way.)
2. Reference sink profile: the sink runs from BeginPlay (the reference's
   TickComponent body is outside the stock component's controller gate), so
   by cp0 (t=0.5) the ramp (980uu/s² to the 500uu/s terminal, reached at
   ~0.51s) is essentially complete. Phase-A drop over cp0→cp1 ≈ ~5uu of
   residual ramp + 1.99s × 500 ≈ **~995uu** — comfortably inside [300,
   1600]. Confirm from the `[t2-gravpawn calib]` lines.
3. Driven-phase altitude: the reference zeroes SinkSpeed on pending input the
   same tick — expected driven Z loss ≈ 0. Gate allows 0.25 × D_A (~249uu)
   for input-consumption timing slop. Confirm actual.
4. Continuity guard margins: reference max per-frame |dZ| = 500/60 ≈ 8.3uu
   vs the 30uu cap, and 125uu per 0.25s window vs the 300uu cap. Confirm no
   false trip across all legs (watch the first driven frames where lateral
   accel is steep — Z should be untouched — and the ramp's steepest frames).
5. `teleport-down-on-timer` first step lands at t≈0.75s (timer starts at
   BeginPlay, t≈0 world time) — inside the running window (StartTest is
   ~0.1-0.3s). Confirm the guard fires there and not at a checkpoint.
   `small-step-timer-descent` steps every 0.1s from BeginPlay — confirm its
   first RUNNING step (t<=~0.6s) trips the per-frame guard (50uu > 30uu).
6. Map air clearance: pawn ends phase C at Z ≈ 6000 − ~2,300 (reference) —
   nowhere near the floor. An over-band submission is failed by the band cap
   before it could reach the floor; confirm no leg ever lands.

## Discrimination record

Not yet run — see `discrimination/MATRIX.md` §Status. To be filled from the
first `cb discriminate --wip` after the map lands: per-leg verdicts, the
calib line values at each checkpoint, and any re-timed checkpoints.

## Landing gate

MUST NOT land in CATALOG/registry before (1) the `.umap` + these sources are
committed and (2) one full `cb discriminate` run has filled the calibration
record and the MATRIX status. The registry reconciliation (CATALOG row +
count claims + MAPS.md row) happens in the shared batch pass, not per-task.

## Calibration record — first live validation (2026-07-30)

Binary half + full matrix ran this date on this box (Win11, UE 5.8 at
`C:\Program Files\Epic Games\UE_5.8`, substrate=live via `--wip`):

- **Build**: editor target compiled the task's scaffold + fixture C++ clean on
  the FIRST attempt (post-adversarial-review sources).
- **Map**: authored headless by the `aids/` script (`-ExecutePythonScript`,
  `-RenderOffScreen`); single monolithic `.umap`; placement log line confirmed.
- **Matrix**: `cb discriminate --wip` = **discriminated: YES on the first
  attempt** — reference PASS; empty + EVERY variant FAIL, each credited via
  its named MATRIX substring (`[ok ]` on all legs).
- **Not retained**: per-leg run dirs (no `--keep`) — numeric calib lines
  unharvested; the checklist's yes/no assumptions are answered by the
  verdicts. Re-run with `--keep` only if a checkpoint ever needs re-timing.

Checklist items resolved by the 2026-07-30 matrix (verdict-level evidence):
1. **AI-controller input consumption on ADefaultPawn (the load-bearing
   unknown): CONFIRMED WORKING** — the reference leg PASSed, which requires
   the possessed pawn to consume per-frame `AddMovementInput` laterally in
   phase B (the `Velocity`-write fallback is NOT needed).
2. Both tightened guards behaved: no false trip on the reference
   (8.3 uu/frame vs 30; ~125 uu/window vs 300), and each timer variant died
   at the per-frame guard as designed.
3. Phase gates (idle sink, driven hold, resume) all discriminated on the
   first attempt at the shipped checkpoint times.
