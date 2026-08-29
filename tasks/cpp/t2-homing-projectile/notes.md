# Field-test log — t2-homing-projectile (2026-07-21)

The first source-row-to-runnable-eval conversion driven end-to-end through
`docs/TASK-AUTHOR-GUIDE.md` after the restructure. Source spec:
"Homing missile" (an earlier internal task list, C++ / Gameplay — "Testing its
understanding of non-trivial projectile implementation"). This file records the
process findings.

## Design decisions (and why)

- **The discriminator is a fixture perturbation**: at t=1.0s the fixture
  RELOCATES the target +800 units laterally. A homing projectile re-steers
  and still intercepts; a straight-line shot aimed at the original position
  sails past. Without the move, a stationary target makes homing and
  straight-line indistinguishable (both intercept) — the source row's raw
  verification note ("should use a projectile movement component of some
  kind") is an implementation-pattern check the prompt may not name
  (Hard Rule #2), so the behavior had to be made observable instead.
- **Anti-teleport is a closing-speed cap**: per checkpoint interval,
  `d_prev - d_now` must not exceed the disclosed max speed × dt (+30%
  slack). A SetActorLocation cheat shows an impossible closing rate.
- **Anti-spawn-at-target**: at the first checkpoint (0.5s) the projectile
  must still be far away (> 55% of the initial launcher→target distance —
  max disclosed speed covers ≤ 600 units by then).
- **Interception = per-frame min distance < 150**, tracked in an overridden
  `Tick` (calling `Super::Tick` — the base still owns the checkpoint clock);
  checkpoint-only sampling could miss the closest approach of a fast
  projectile. Early-succeed at any checkpoint once intercepted, so a
  destroy-on-hit projectile doesn't fail later existence checks.
- **Prompt disclosures** (the t0 Log/Display lesson): the `HomingMissile`
  tag, the 600–1200 u/s speed band, the 150-unit arrival radius, the 3s
  deadline, and "the target may move mid-flight" are ALL stated — every
  literal the fixture enforces is in the prompt.

## Process findings (running)

1. (from tp0, confirmed here) The checklist's step order works as written;
   authoring the map via editor-Python using the committed `aids/` recipe is
   ~3 min per iteration.
2. Trajectory tasks are MEDIUM on the automatability gradient — the
   tolerance numbers below were CALIBRATED against a reference run before
   the discrimination matrix was finalized (see the calibration section).
3. **Design-review catch:** the first fixture draft's per-frame min-distance
   tracker was satisfiable by a between-checkpoint teleport or a
   destroy-and-respawn-at-target — checkpoint-level speed caps see neither.
   Fix: per-frame displacement policing + pinning the projectile's identity
   at first sighting. Lesson for the checklist's pre-mortem step: ask "can
   the SAMPLER itself be gamed?", not just the assertions.
4. **UHT cascade failure on the live tree:** adding the fixture pair
   coincided with UHT dying ("Unhandled 1 aggregate exceptions") and every
   per-task fixture erroring "Unable to find parent class type ...
   'ACraftBenchFunctionalTest'". Bisect showed the failure persisted WITHOUT
   the new files, while the same code UHT'd fine inside the map-authoring
   editor session and from git HEAD in verifier workdirs — i.e. a corrupted
   live-tree UHT/build cache, not a source bug. Remedy: clear the
   substrate's regenerable `Intermediate/Build` + `Binaries` and rebuild.
   (An early wrong guess — TNumericLimits<double>::Max() in a UCLASS default
   member initializer — was swapped for a plain sentinel anyway; harmless.)
5. **Toolchain gotcha (self-inflicted):** `Build.bat ... | tail` in bash
   masks the build's exit code (the pipe returns tail's) — the map-authoring
   step chained past a FAILED build. Scripts must test PIPESTATUS or grep
   "Result: Succeeded".

## Calibration record

Reference leg, Windows + UE 5.8, `-deterministic -FPS=60`, 2026-07-21
(`run_task.py --substrate-from-live`, workdir t2cal — overall PASS):

```
cp0 t=0.50 d=1797.3 initial=2328.1     (gate: d > 0.55*initial = 1280 ✓)
cp1 t=1.00 d=1247.3 closed=550.0        (cap 780; floor 50 ✓)
    target relocated +800 laterally
cp2 t=1.50 d=997.4  closed=541.1        (homing re-steered ✓)
cp3 t=2.20 d=227.4  closed=770.0        (cap 1092 ✓)
(intercepted between cp3 and cp4 → early-succeed; worstframe=1100 vs cap 2400)
```

- Measured initial separation is 2328, not the nominal 2000 (editor
  placement offset) — harmless because every gate is RELATIVE to the
  measured value. Field lesson: prefer relative gates; absolutes would
  have needed a map-edit round-trip here.
- All margins ≥ 40%; tolerances shipped unchanged from the design.

## Gate results (2026-07-21, Windows + UE 5.8)

- `cb lint` — 0 errors, 0 warnings.
- `cb discriminate --wip` — **YES, 4/4 legs**: reference PASS; empty FAIL;
  straight-line FAIL via `not closing on the target` (the relocation trap);
  teleport-cheat FAIL via `u/s in a single frame` (motion policing) — after
  the ASCII fix; the first run's `[BAD] wrong-reason` was the em-dash
  encoding incident (see FAILURE-LOG), i.e. the wrong-reason machinery
  catching an unproven defense exactly as designed.

## Graded eval (the field test's final leg)

- `cb eval --task cpp/t2-homing-projectile` (a now-removed vendor arm,
  sonnet-5): **VERDICT PASS** — $0.1364, drive 391s (vs t0's ~142s: the task
  is meaningfully harder), grade 271s, L1 both targets, L2 1/1. The agent's
  projectile survived the mid-flight target relocation + motion policing.
- Run: `runs/<arm>/craftbench-tasks__t2-homing-projectile-20260722-024844` (that arm is not part of this release).
- Bring-up r1 hit the known product-login flake twice; `--restart-client`
  cleared it in one pass (live validation of the scoped client kill).
