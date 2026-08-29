# tp2-sprint-stamina — implementor notes + calibration record

## Provenance

- Source: an earlier internal task list (not shipped), row "Sprinting system".
  Selected 2026-07-23 against three lenses (ThirdPerson
  leverage / deterministic verifiability / benchmark value) as the first
  authentic gameplay task on the ThirdPerson substrate.
- Scope kept: hold-to-sprint at 1.7x, stamina drain/regen, minimum re-sprint
  floor. Scope cut: the caps-lock walk-toggle (second unverifiable key axis;
  `Content/Input/` + `Config/` are deny-listed so a real binding deliverable
  is impossible by design). The key trigger is rephrased to the substrate's
  `Do*` programmatic seam (the `DoJumpStart`/`DoJumpEnd` precedent).

## Design decisions (confirm before shipping)

1. **No-latch semantics pinned**: "a below-threshold request is ignored and
   not remembered" is a design decision (auto-resume-on-regen is a legitimate
   real-game design) and is load-bearing for cp3. Fully disclosed in the
   prompt.
2. **Reflection seam precedent**: first fixture invoking agent-defined
   UFUNCTIONs by name (`FindFunction` + `ProcessEvent`). The seam gate
   tolerates a return value but rejects real input parameters; the fixture
   compiles against git HEAD where the functions do not exist, so
   reflection-by-name is the only sound call path.
3. **Concrete scaffold subclass**: the stock template classes are
   `UCLASS(abstract)` and unspawnable; `BP_ThirdPersonCharacter` is
   deny-listed. `ASprintCharacter` + `ASprintGameMode` (map WorldSettings
   GameModeOverride) spawn/possess the tagged pawn without the mannequin/ABP
   stack (lighter under `-nullrhi`).
4. **Fixture drives, agent gates**: the fixture feeds
   `AddMovementInput(+X, 1)` every frame while the test runs; the agent's
   code only shapes max speed. Speed asserts are ratios of the measured cp0
   baseline (never absolutes past cp0), with an `IsFalling` guard.

## Stamina timeline behind the checkpoint schedule {1.0, 3.0, 6.2, 7.0, 9.0, 10.5}

- t=1.0 cp0: baseline sampled; DoSprintStart invoked (stamina 100).
- t=1.0..5.0: drain 25/s -> stamina 0 at t=5.0; auto sprint-end.
- t=3.0 cp1: mid-sprint sample (stamina 50).
- t=5.0..6.2: regen 20/s -> 24 at cp2 (below the 30 floor). cp2 asserts the
  revert, then invokes DoSprintStart (must be ignored, not latched).
- t=6.5: stamina crosses 30 — the latch trap instant. A remembered request
  auto-starting here reaches sprint speed by ~6.7 (accel ~2048 uu/s^2).
- t=7.0 cp3: still-baseline assert. Kills BOTH the instant below-floor sprint
  (a floor-less implementation sprints from t=6.2 with stamina 24; the
  illegal sprint lives until ~7.16, so at 7.0 it reads full sprint ratio with
  a 0.16 s margin) and the latched auto-start (full ratio by 6.7).
- t=9.0 cp4: still-baseline (no request pending; stamina ~80), then
  DoSprintStart (must take effect).
- t=10.5 cp5: second sprint sample (stamina ~42.5; budget 80/25=3.2 s runs to
  t=12.2 — 1.7 s spare). PASS.
- TimeLimit: base sets last checkpoint + 2 s margin = 12.5 s.

**Why cp3 moved 7.2 → 7.0 (2026-07-23 discrimination lesson).** The first
matrix run graded `no-threshold` FAIL(wrong-reason): UE braking is
friction-dominated (`ApplyVelocityBraking`: friction times velocity plus
BrakingDeceleration, roughly 14,000 uu/s^2 at sprint speed), so an over-max
pawn settles to baseline in 1-2 frames — NOT the ~0.18 s a pure
BrakingDeceleration=2000 estimate gives. At cp3=7.2 the floor-less variant's
illegal sprint (ended ~7.16) had already settled -> cp3 PASSed; the variant
then died at cp5 (its third sprint, from stamina ~36.8 at cp4, expires at
~10.49, one frame before the 10.5 sample) with the REGEN message — the wrong
named assertion. The reference's own cp2 reading of exactly 500.0 only 1.2 s
after a sprint end corroborates the fast settle. Sampler pre-mortem lesson
(t2 rule): a trap checkpoint must sit INSIDE the cheat's active window, not
after it, because settle time is ~0.

## Map facts (Content/Maps/tp2-sprint-stamina/L_TpSprint.umap)

- Authored by `aids/author_L_TpSprint.py` (headless editor-Python,
  `-RenderOffScreen`; committed binary is the ONLY map source).
- Runway: engine basic cube scaled (250, 20, 1) = 25,000 x 2,000 x 100,
  centered X=12,000 (top at Z=+2; spans X in [-500, 24,500]). Worst-case
  compliant run distance ~9,000 uu -> ~2.5x headroom before `IsFalling`.
- PlayerStart at (0, 0, 120), yaw 0 (+X down the runway). Fixture at
  (0, 400, 120). WorldSettings GameModeOverride = `ASprintGameMode`.
- Automation name:
  `Project.Functional Tests.Maps.tp2-sprint-stamina.L_TpSprint.SprintStaminaFunctionalTest`.

## Calibration record

Tolerance bands shipped in the fixture (pre-calibration estimates):

| Gate | Band |
|---|---|
| cp0 baseline absolute | [400, 600] (stock MaxWalkSpeed 500) |
| sprint ratio (cp1, cp5) | [1.55, 1.85] around the disclosed 1.7x |
| baseline ratio (cp2, cp3, cp4) | [0.85, 1.15] |

- [x] Calibrated 2026-07-23 (Windows + UE 5.8.0, `-deterministic -FPS=60`,
  reference leg PASS L1+L2 1/1; workdir `C:\cb\wd\tp2ref`). Measured:

  ```
  cp0 t=1.00  v=500.0  (band [400,600]      — dead-center, 100% margin)
  cp1 t=3.00  v=850.0  ratio=1.700  (band [1.55,1.85] — dead-center)
  cp2 t=6.20  v=500.0  ratio=1.000  (band [0.85,1.15] — dead-center)
  cp3 t=7.20  v=500.0  ratio=1.000  (dead-center)
  cp4 t=9.00  v=500.0  ratio=1.000  (dead-center)
  cp5 t=10.50 v=850.0  ratio=1.700  (dead-center)
  ```

  Under fixed timestep the trajectory is exactly deterministic — every gate
  sits dead-center in its band (margins ~100% of half-width, >> the 40% t2
  bar). No schedule adjustment needed; cp3 stays at 7.2.
- [x] Discrimination executed 2026-07-23 (Windows/UE 5.8.0,
  `cb discriminate --wip`): **discriminated 1/1** — reference PASS, empty +
  `permanent-boost` + `no-threshold` all FAIL via their named substrings.
  (First attempt caught the cp3 mistiming — see "Why cp3 moved" above; a
  second attempt with `--keep` burned all 4 legs on the `--keep`-relocation
  MAX_PATH bug — do not combine `--keep` with a deeply nested repo path.)
