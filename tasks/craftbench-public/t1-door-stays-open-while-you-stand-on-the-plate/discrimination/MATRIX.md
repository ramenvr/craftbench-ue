# Discrimination matrix — t1-door-stays-open-while-you-stand-on-the-plate

The self-validation oracle: the reference must PASS, and every variant plus the
empty leg must FAIL **at the predicted gate, via the named substring**. A
wrong-reason FAIL (an L1 build failure, a different gate, `SANDBOX-REJECT` exit 4)
means the gates are NOT discriminated — fix them, or relabel the task for the
weaker property it actually tests.

Each variant is wrong in exactly **one** way and aimed at a **different** gate. If
several failed the same gate, the rest would be unproven and could be dead
without anyone noticing.

## Three parser rules this file is written against

Inherited from the pad task's matrix, where all three were learned the hard way.

- **One parseable row per label.** `parse_matrix` returns `Dict[label -> MatrixRow]`,
  so a second table repeating a label silently overwrites the first. Exactly one
  table with variant rows below; everything else is prose.
- **A variant cell must contain a `/`.** A row is only classified as a variant when
  `"/" in first` (`discriminate.py:286`), so a bare `spin-in-place` is silently
  DROPPED — the leg still runs (legs come from the directory listing) but carries no
  expected substring and reports `no-named-assertion`. Write `` `spin-in-place/` ``.
- **A backticked substring must (a) contain a space or one of `(),.=` and
  (b) fall inside ONE literal run of the fixture's format string.** Both bit
  this task 2026-08-17. `_extract_substrings` keeps only "substantive" ticked
  literals; a bareword like `` `DoorSwingsSmoothly:` `` has neither a space nor
  that punctuation, so it is discarded as a parenthetical and the parser falls
  through to using the WHOLE cell -- which appears in no log, so the leg would
  report `no-named-assertion` while the row looked fine. And the original
  `` `DoorSwingsSmoothly: the graded door jumped` `` spanned a `%s`: it matches
  the LOG (which is why discrimination passed) but is not statically anchorable,
  so `test_matrix_substring_oracle` correctly called it unproducible. Fix is two
  ticked literals -- ALL-of semantics -- each inside its own run.
- **Every expected substring contains a space**, or `_extract_substrings` falls
  through to a branch that returns the cell with its backticks attached and can
  never match log text.

| Submission | Expected verdict | Expected substring | Which gate, and why it is the one that fires |
|---|---|---|---|
| `../reference` | PASS | `door opened and shut on both visits` | All gates green at BOTH frame rates. Measured: 90.0 deg open and 141 cm of panel travel at cp1/cp2/cp4/cp5, 0.0/0 at cp0/cp3/cp6, control 0.0 at all seven checkpoints, `tests=2/2`. |
| `empty` | FAIL | `DoorOpensWhileOccupied: expected the door to be open` | The unmodified scaffold compiles, so L1 is green and the failure is behavioural. Measured: `graded=0.0` with the hero standing on the plate at 87 cm. |
| `spin-in-place/` | FAIL | `PanelIsTheGradedPart: expected the door's own panel to move` | Turns the panel 90 deg about its OWN CENTRE instead of sweeping it about the hinge. The yaw is right, the timing is right, the motion is smooth, the control is untouched — and the panel never leaves the doorway. On screen it reads as a door twisting in its frame. **Replaces an earlier `decoy-mesh` variant** that swung an added decorative mesh while the panel stayed put: with the panel's angle at 0, `DoorOpensWhileOccupied` fired first, so it never reached the travel gate and was redundant with `empty` (measured 2026-08-17, `FAIL(wrong-reason)`). **To exercise a gate, a variant must SATISFY every gate checked before it.** |
| `snap-open/` | FAIL | `DoorSwingsSmoothly: the` + `door jumped` | Correct in every other respect, but it teleports to the pose in one frame: 90 deg in a 60 Hz frame is 5400 deg/s against the disclosed 720 ceiling. Caught by the CONTINUOUS per-frame guard, not by a checkpoint. |
| `both-doors/` | FAIL | `SecondPairNeverMoves: expected the untouched door` | The graded door behaves perfectly, so every open/shut/repeat gate passes — but standing on one plate opens the other pair's door too. This is what proves the in-scene control pair is load-bearing rather than scenery. |
| `frame-coupled/` | FAIL | `DoorOpensWithinDeadline: expected the door to reach the open` | **The most important leg in this task, and it found a hole in the fixture.** It advances a fixed amount per FRAME: 2.0 deg/frame is 120 deg/s at 60 Hz — identical to the reference — and 40 deg/s at 20 Hz, so 90 deg takes 2.25 s against the disclosed 2 s. On the first run it **PASSED both legs**, because cp1 is a fixed sample at t=4.80 which happens to land ~2.3 s after the hero arrives: the effective deadline was an accident of checkpoint spacing and **nothing measured the 2 seconds the prompt states** (measured 2026-08-17, `PASS(unexpected-pass)`). The fix was two-part: `DoorOpensWithinDeadline` now times plate-entry to open-band per frame (a checkpoint sample structurally cannot see either edge), and the variant's step dropped from 2.0 to 1.5 deg/frame so it misses by a margin instead of a rounding. **Measured outcome:** at 20 Hz the door reaches 88.5 deg by cp1 — above the 80 band, so the angle gate passes — and `DoorOpensWithinDeadline` is the gate that fires, because getting there took longer than the disclosed 2 s. 60 Hz passes. So the gate that discrimination revealed as MISSING is now the gate that catches the defect, which is the ideal shape: the variant proved the hole, the hole got a gate, and the gate proved the variant. (I briefly re-predicted `DoorOpensWhileOccupied` on arithmetic that assumed a later plate arrival; the trace settled it.) |

## Why `frame-coupled` is the leg that matters

the repo conventions records that the multi-rate mechanism is implemented and unit-tested
but has **never executed on a shipping task** — the legacy `_DT_LEGS_BY_TASK` map
is empty and the branch was unreachable everywhere. This task is the first to
declare `fps_legs: [60, 20]` and actually run both (measured: `l2_fps60.log` and
`l2_fps20.log`, `-FPS=60` and `-FPS=20`, `tests=2/2`).

`frame-coupled` is the only leg that proves that schedule earns its keep. A
single-rate task would grade it as **correct**. Frame-rate coupling is a real and
common defect, it is invisible at the rate you happen to test, and this is the
first place in the benchmark where it can be caught at all.

## What each variant deliberately does NOT break

`spin-in-place` swings on cue, at the right angle, smoothly, and leaves the control
alone — only the panel's *travel* is wrong. `snap-open` reaches the right pose at the
right time and leaves the control alone — only its *rate* is wrong. `both-doors` is a correct door that is also indiscriminate.
`frame-coupled` is correct at one frame rate. Keeping each wrong in exactly one way
is what makes a wrong-reason FAIL diagnostic instead of ambiguous.

## Gates with no variant, and why that is honest

`DoorShutsWhenVacated` and `PanelReturnsHome` carry no hand-authored variant. Per
the 2026-08-11 owner decision variants are written for a hole the requirements
table found, not one per gate. Both are reachable — a latch-open implementation
fails the first, a panel that shuts by teleporting home fails the continuity guard
before it reaches the second. If a submission is ever seen passing either
vacuously, author the variant then and record it here.

## What the first discrimination pass found, and why it was worth running

Four of six legs came back clean on the first attempt; the two that did not were
both defects in **this fixture**, not in the variants:

1. **A disclosed requirement had no gate.** The prompt states "at least 80 degrees
   from shut within 2 seconds of stepping onto the plate" and nothing measured the
   2 seconds — cp1's fixed sample time was standing in for it by coincidence. A
   genuinely too-slow door passed. Fixed by `DoorOpensWithinDeadline`.
2. **A variant aimed at a gate it could not reach.** `decoy-mesh` was meant to
   exercise `PanelIsTheGradedPart`, but by leaving the panel's angle at 0 it tripped
   `DoorOpensWhileOccupied` first. A variant only tests the gate you intend if it
   SATISFIES every gate evaluated before it — replaced by `spin-in-place`.

Neither was visible from the reference PASS or the empty FAIL. Both required a
variant that was wrong in one specific way.

## Status

Reference PASS (`tests=2/2`) and `empty` FAIL are **measured** on 2026-08-17,
UE 5.8.1, Windows. The four variant legs are authored and graded by
`cb discriminate`. Their predicted substrings are taken verbatim from the
fixture's `FinishTest` text, not paraphrased.

**Run it with `--warm-cache`.** The leg workdir is derived from
`runs/discriminate/<set>__<id>-<ts>/<leg>/wd/`, and this task's id is longer than
the pad's, so the cold path exceeds Windows `MAX_PATH` (260) and UBT refuses with
exit 6 before compiling anything — every leg comes back BAD with nothing tested.
The warm pool builds in a fixed 85-character path instead.
