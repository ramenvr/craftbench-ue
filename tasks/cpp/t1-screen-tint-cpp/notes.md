# notes — t1-screen-tint

Authored 2026-08-18 on the ThirdPerson substrate, UE 5.8. Built against the
owner's 2026-08-18 difficulty bar.

## Provenance

Startup Eval corpus row `t1-runtime-postprocess-reacts-to-movement`, adopted per
an internal design note (not shipped) row 13
(`ADOPT+FIX · hardfail · leak · id-leak`, LOW/4h).

| The review said | What was built | Why |
|---|---|---|
| bands are declared on paper — pick an effect that swings 0.0→0.9 and CALIBRATE rest/active from a reference run into notes.md before MATRIX.md | rest 0.00, full 0.90, and the reference run is quoted below and in `discrimination/MATRIX.md` with the actual readings at six samples | the calibration is the table below, taken from the run, not from the design. |
| a second scalar on the same supplied material that must still read its supplied value at every checkpoint | built as `SceneFringeIntensity`, supplied at 0.60, checked every frame | assigning a fresh `FPostProcessSettings` to set one field is the obvious mistake, and this catches it. |
| delete "Without generated C++" from the mission; demote the scope inspection to an advisory line | the prompt says nothing about how, and there is no scope inspection at all — every gate reads the component's settings | behaviour-only, per Hard Rule #2. |
| **a post-process MATERIAL** | **not used.** The effect is built-in `PostProcessSettings` scalars on an unbound `UPostProcessComponent` | authoring a post-process material from editor Python means guessing at parameter names on assets whose parameters are not documented, and a `SetVectorParameterValue` that silently does nothing leaves the state invisible while looking like it worked — measured on the marked-ground task the same night. Built-in scalars are engine properties: readable headless, visible when played, and impossible to set "successfully" without effect. The concept — a screen effect driven from live gameplay state — is unchanged. |
| two states, resting → active → resting | **PROPORTIONAL**, and normalised against a denominator that CHANGES | a two-state effect is one `if`. Under the 2026-08-18 bar that is not a task. |

## Calibration, from the measured reference run

| what the character was doing | speed | fraction | effect |
|---|---|---|---|
| standing, leg 1 | 0 | 0.00 | 0.00 |
| half pace, leg 1 | 250 | 0.50 | 0.45 |
| flat out, leg 1 | 500 | 1.00 | 0.90 |
| standing, leg 2 | 0 | 0.00 | 0.00 |
| half pace, leg 2 | **130** | 0.50 | 0.45 |
| flat out, leg 2 | **260** | 1.00 | 0.90 |

The tolerance is 0.12 and the smallest gap between a correct reading and the
commonest wrong one (dividing by the first leg's top speed) is **0.22**. There is
no band-shaped hole for a wrong answer to sit in.

## Two fixture faults that failed a correct implementation first

Written up in `discrimination/MATRIX.md`. In short: the stability test called an
entire acceleration ramp "stable" because it compared consecutive frames rather
than a window, and the fixture graded against a heavily-smoothed
distance-per-frame while a correct submission reads the character's velocity — so
the two disagreed by 130 uu/s through every deceleration and a perfectly correct
reference failed by the difference.

Both are the same law as the four "the drive manufactures FAILs" instances of
2026-08-17, with one addition worth keeping: **when a gate compares the
submission's number against the fixture's number, both have to be derived the
same way.**

## Still to do

The empirical half of the difficulty bar. **No task in this set has been run
against a model.** `cb eval --model claude-p:<cheap model>` on this task, once:
passing first try with zero iteration means it needs another axis.
