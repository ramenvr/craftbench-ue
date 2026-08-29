# Discrimination matrix — t1-shoved-block-slides-on-one-rail

A task discriminates when the committed reference PASSes and every variant and the
empty leg FAIL **at the predicted gate, via the named substring**. A leg that fails
for a different reason proves nothing about the gate it was written for.

Two parsing laws bit sibling tasks in this set and both apply here:

- `parse_matrix` classifies a variant row by requiring `"/" in first`
  (`discriminate.py:286`), so a bare `spoofed-motion` is silently dropped and the
  leg still runs — it just carries no expected substring and reports
  `no-named-assertion`. Write `` `spoofed-motion/` ``.
- **A backticked substring must (a) contain a space or one of `(),.=` and (b) fall
  inside ONE literal run of the fixture's format string.** `_extract_substrings`
  discards a bareword tick as a parenthetical and then falls through to matching
  the WHOLE cell, which appears in no log; and a phrase that spans a `%s`/`%.1f`
  matches the LOG but is not statically anchorable, which
  `test_matrix_substring_oracle` correctly rejects. Two ticked literals per row,
  ALL-of semantics, each inside its own run.

| Submission | Overall | Named substring(s) | Why this leg exists |
| --- | --- | --- | --- |
| `../reference` | PASS | `the railed block tracked its rail on both shoves` | One world-anchored, one-axis physics constraint on `ARailBlockActor`. Measured: cp1 s=779.8 cm, cp2 a further 896.0 cm, and the window maxima for off-line, height and turn were **0.00 / 0.00 / 0.00** against allowances of 8 / 10 / 10 cm-deg; peak rigid-body speed 950 and 965 cm/s against the 100 asked for; twin 264 cm and 121 deg then 543 cm and 136 deg. The tether leg recovers after the knock. |
| `empty` | FAIL | `RailStaysOnLineFirstShove: the railed block drifted` + `off its rail line during the first shove` | The unmodified scaffold compiles, so L1 is green and the failure is behavioural. The same off-axis, off-centre push that throws the twin throws an unheld block: measured 274.0 cm off the line and 179.5 deg of turn on the first shove. |
| `spoofed-motion/` | FAIL | `RailMotionIsPhysicsFirstShove: the railed block covered ground` + `so it is being driven along a path rather than moved by the world` | Writes the block along the rail line frame by frame instead of holding it there. Off-line, height and turn readings all come out perfect and the body still reports as simulating. **It also sailed past a peak-speed floor:** the plunger's real push gives even a scripted block a brief real velocity, and 131 cm/s of that residual satisfied a `>= 100 cm/s` gate while a per-tick transform write did all the travelling (measured 2026-08-17 — this leg PASSED the whole task). What a transform write cannot fake is the AGREEMENT between distance covered and the velocity the solver reports, which is the prompt's own wording: *its own physics velocity is what carries it*. |
| `one-shot-rail/` | FAIL | `RailStaysOnLineSecondShove: the railed block drifted` + `so the rail did not hold it a second time` | A real constraint, released after the first slide — the most common wrong implementation in this family. Every first-shove gate passes; the second shove throws the block off the line exactly as it does the twin. This is what the two-shove structure is for. |
| `velocity-clamp/` | FAIL | `RailBackOnLine: the railed block is still` + `so nothing is holding it to the rail` | **The leg that earns the tether requirement.** A REAL one-axis joint, re-anchored at the block's current pose every frame — threshold-free, so there is nothing in it tuned to this scene. It passes ALL SIX cp1 gates and all six cp2 gates — it is simulating, its own velocity carries it, it never leaves the line, never changes height, never turns, and it does it twice. A joint that forgets its line every frame cannot carry a body BACK to one, so after the knock it re-anchors at 60 cm off and 40 cm up and stays there — cp3 is the only thing between this and a PASS. |
| `rails-the-twin/` | FAIL | `TwinThrownClearFirstShove: the untouched twin ended` + `so the push was not the off-axis` | Solves the graded block correctly and quietly rails the COMPARISON block too. Without a gauged twin this is the cheapest way to make the off-axis and no-spin gates unfalsifiable: if nothing is ever thrown off-axis, "stayed on the line" means nothing. The twin is therefore measured at every checkpoint, and it is the witness that the push kept its off-axis, off-centre character. |

## Why the tether leg is the one that matters

`velocity-clamp` is the only variant that reaches cp3, and it gets there with
readings IDENTICAL to the reference's: 0.00 off-line, 0.00 off-height, 0.00 turn at
both cp1 and cp2. It is a complete, plausible, cheap answer that satisfies every
gate a reasonable author would think to write — twelve of them — and it is not a
rail at all. Without the knock this task would grade "prevents the block from
leaving the line" as equivalent to "holds the block to the line". The knock is disclosed in the prompt ("if something lifts
the block off the rail ... it must end up back on the rail line"), so this grades a
stated behaviour and not a route.

## What the physics cost, recorded so nobody re-derives it

The reference is short, but three of its choices are load-bearing and were each
found by measurement rather than reasoning:

1. **The joint anchors to the WORLD, not to the rail's static body.** Both look
   equivalent. Anchored to the rail primitive, the joint degraded as the block
   travelled away from where it was defined: the first shove held the line to
   0.01 cm, the second — starting 496 cm along — was torn 16.6 cm off it and lost a
   third of its travel. Against the world the same joint reads 0.00 cm on both.
2. **The blocks are held clear of the floor.** A block resting exactly on the floor
   with its height locked fights the floor contact; a 600 cm/s shove arrived at
   31.7 cm/s. The 4 cm gap in the map is not cosmetic.
3. **The stripes leave a corridor down the rail.** A stripe crossing the rail is a
   3 cm obstacle in the slide: with continuous stripes the block scraped every one,
   and a BIGGER shove travelled LESS, which is the tell.

Also measured and worth keeping: the twin's TURN is graded as the window maximum,
not the value at the sample. `FQuat::AngularDistance` returns the shortest angle in
[0,180], so a block that tumbles through several revolutions can finish reading any
angle at all — the same twin read 158 deg on one layout and 15 deg on another
purely from where the tumble stopped. Displacement is read at the sample, because
displacement does not wrap.
