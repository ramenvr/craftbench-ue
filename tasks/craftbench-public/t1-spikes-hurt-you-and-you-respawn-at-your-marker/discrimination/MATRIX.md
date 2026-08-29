# Discrimination matrix — t1-spikes-hurt-you-and-you-respawn-at-your-marker

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs. This task
carries 26 separately named gates across five segments, so a partial implementation
is already diagnosable from the verdict line alone -- which is what variant legs
would otherwise have been proving.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS | `the slab slid its rail and cost 25 a touch` | Slab slides post to post at 300 cm/s and costs 25 per touch; the course holds one `CurrentPadOrder` and derives BOTH the pad marks and the respawn point from it. Measured, the whole chain in one run: 100 -> 75 -> 25 -> death 1 returns to the START MARK (no pad walked yet) -> death 2 returns to PAD 1 -> pad 2 takes over -> walking back over pad 1 leaves pad 2 current -> death 3 returns to PAD 2. The bystander finished at 100 having never moved. |
| `empty` | FAIL | `SpikesMoveOnTheirOwn: the spiked slab never moved` + `on its own` | The unmodified scaffold compiles, so L1 is green and the failure is behavioural. Nothing moves the slab, so the first segment gate fires before any of the damage, death or pad gates can be reached -- which is the honest order: a course whose hazard never moves has not started. |

## What carries the discrimination without variants

Five segments, each with its own named gates, and the ones that could be vacuously
true carry an explicit precondition-reached assert with its own substring:

- **slab** — moves at all, stays on its rail, and KEEPS sliding after it hurts
  someone (a hazard that stops on contact is a different, easier level).
- **damage** — full health until first contact, exactly 25 for the first touch, one
  25 per touch however long the slab stays, another 25 for the next separate touch,
  and never a change while nothing is touching.
- **control** — the bystander must finish at 100 and unmoved. It is possessed on
  purpose: an unpossessed Character is inert, and an inert bystander proves nothing.
- **death / respawn** — three deaths at three different points in the run, each
  expecting a DIFFERENT return point (start mark, pad 1, pad 2), plus health back to
  100 and a freedom probe after each so nothing may pull the character back.
- **pad state** — the two rows that must never be folded:
  `WalkingBackDoesNotRollBack` reads the course's exposed `CurrentPadOrder`, and
  `DeathAfterTheWalkBackReturnsToTheSecondPad` reads where the character ACTUALLY
  came back to. A submission that keeps its respawn point in a second,
  separately-updated place passes the first and fails the second.

## The one-sided margins, and why they cannot false-FAIL correct work

- **Contact.** The fixture's window is the slab's world box grown by the capsule
  PLUS 25 cm, so it opens a frame or two before the engine's own overlap edge can
  fire. `Taken`-style upper-bound reasoning: a legitimate hit can never read as
  "lost health while nothing was touching it".
- **Same touch.** Measured 2026-08-18: the engine's overlap edges FLICKER as the
  slab steps past a capsule (begin/end/begin inside a few frames), so a naive
  once-per-overlap deduction cost 50 for one pass. The reference treats a re-begin
  within 0.6 s as the same touch; real passes are ~2 s apart at the disclosed
  300 cm/s over a 600 cm rail, so nothing legitimate is missed.
- **Drive routing.** Every leg returns to the lane centre line before travelling in
  X, because a straight line from pad 1 to the hold point passes 30.7 cm from pad
  2's box and the capsule is 34 cm -- the DRIVE itself would clip pad 2, a compliant
  submission would set `CurrentPadOrder = 2`, and the respawn-target gate would fail
  correct work. Freedom probes are driven in +X only: respawn #1 is the start mark at
  x = 300 and the platform begins at x = 0.

## The sentinel

The schedule ends with an instant far past any real grade. `ACraftBenchFunctionalTest`
declares SUCCESS the moment the last scheduled checkpoint is crossed, and this fixture
grades off measured events (deaths, contact windows) rather than fixed sample times --
so without the sentinel a run whose legs never finished would report a green pass
having graded nothing. Measured on the rail task 2026-08-17; now pitfall 8 of the
implementor checklist.
