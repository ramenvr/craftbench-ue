# Discrimination matrix — t1-screen-tint

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS | `Test Completed. Result={Success}` | Ticks every frame, reads the character's own velocity AND its current `MaxWalkSpeed` off the movement component, and lerps the vignette between the supplied rest and full values by the ratio. Neither number is written down in the solution, so neither goes stale when the track changes one. |
| `empty` | FAIL | `TintTracksHowFastYouAreMoving: on leg ` | The unmodified scaffold compiles, so L1 is green. `SetVignette` exists and works; nothing calls it after `BeginPlay`, so the effect sits at its rest value and fails the first time the character settles at half pace: 250 uu/s of 500, wants 0.45, reads 0.00. |

## The measured reference trace, and why it is the whole argument

```
cp1  leg=1 top=500 speed=250 frac=0.50 want=0.45 got=0.45
cp3  leg=1 top=500 speed=500 frac=1.00 want=0.90 got=0.90
cp7  leg=2 top=260 speed=130 frac=0.50 want=0.45 got=0.45
cp9  leg=2 top=260 speed=260 frac=1.00 want=0.90 got=0.90
```

Leg 2 is the point. **130 uu/s reads 0.45 and 260 uu/s reads 0.90** — the same
readings as leg 1 at twice the speed, because the denominator changed. An answer
that divides by a remembered 500 reads 0.23 and 0.47 at those two samples, i.e.
wrong by 0.22 and 0.43 against a 0.12 tolerance. There is no tolerance-shaped
gap for it to slip through.

## Requirements table

| Prompt requirement | Gate that checks it | When that gate does NOT run |
| --- | --- | --- |
| proportional between rest and full | `TintTracksHowFastYouAreMoving` — every settled frame | during acceleration ramps, deliberately: the window must have held within 0.05 for 0.4 s. A submission that is wrong only during ramps is not caught — and is not wrong, since the prompt allows 0.4 s to reach a new value |
| rest value when standing still | `TintIsOffWhenYouStandStill` — at least one settled still sample per leg | judged at the sentinel; a run that fails the tracking gate earlier never reaches it, which is the more useful message |
| full value at top speed | `TintReachesFullWhenYouRunFlatOut` — at least one settled sample at ≥85% per leg | as above |
| within **0.12** | the tolerance on the tracking gate | never |
| within **0.4 s** of a change | the settle window, which excludes exactly that long after any change | never |
| top speed is **not constant** | the fixture writes a 0.52x `MaxWalkSpeed` between legs; `TheTrackRanBothLegs` fails a run that never got there | never |
| leave the other setting alone | `TheOtherSettingWasLeftAlone` — every frame | never |
| C++ under `Source/ThirdPerson/` | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

## Two fixture faults that failed a CORRECT implementation first

Both are the same law that has now bitten on four consecutive tasks: **the drive
and the measurement can manufacture a failure that looks like the submission's.**

1. **Stability judged frame-to-frame instead of over a window.** Under smooth
   acceleration the per-frame change in the speed fraction is a thousandth, so
   the test called the entire ramp "stable" and graded the effect at 14% of top
   speed while the character was still accelerating. A submission easing over the
   0.4 s the prompt allows would have failed there. The window is now compared
   against the fraction it OPENED at.
2. **The fixture and the submission measured two different speeds.** The fixture
   smoothed distance-covered-per-frame with a 0.2 s constant; a correct
   submission reads the character's own velocity. Through a deceleration the
   smoothed value LAGS: the fixture read 463 uu/s while the character's velocity
   said 333, and the correct reference failed by the difference. The fixture now
   grades against the same quantity a submission would read — the character's
   velocity — and keeps distance-covered only as a cross-check that the character
   is being walked rather than teleported.

The second one is worth stating as a rule: **when a gate compares the
submission's number against the fixture's number, both have to be derived the
same way.** "Measured, not declared" is satisfied by velocity — it comes from
real motion — and does not require the fixture to re-derive speed by a different
route.
