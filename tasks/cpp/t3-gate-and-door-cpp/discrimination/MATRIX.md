# Discrimination matrix — t3-gate-and-door

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs: the
per-checkpoint named gates carry the discrimination.

> **EVERY NUMBER AND EVERY VERDICT ON THIS PAGE IS PREDICTED, NOT MEASURED.**
> Nothing here has been built, compiled or run — no UBT, no editor, no `cb`. The
> phase numbers, the times and the two verdicts below are traced by hand against
> the fixture's own step table and the two committed sources. The orchestrator
> measures them; where a measurement disagrees with this page, the measurement is
> right and this page is the thing to fix.
>
> **Revised 2026-08-19** after two adversarial reviews. Three things on this page
> changed: the yard now holds **two** gates cut for different pairs over the same
> two patches of floor (so the wrong-answer table has two new rows, and the
> reference is unchanged by the addition); the drive's predicted cost was **wrong
> by roughly 2x** and is corrected below; and the sentinel moved from 420 s to
> 900 s because the old one would have failed a correct reference.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS (predicted) | `Test Completed. Result={Success}` | The change lands in exactly one place: the barrier grows a predicate for "has the yard written a pair of names on ME" and a second branch taken only when it has, which asks the same pads a different question and answers it from the crates' own names read at the moment of use. The first branch — the yard's any-body rule — is untouched, so both doors keep the behaviour they shipped with. A per-slot lamp pass throws each lamp against whatever name is written in ITS OWN slot on ITS OWN barrier right now, never against whether a panel happens to be open. Nothing in it caches a name, identifies a crate by which pad it is standing on, treats one barrier differently by class, or assumes there is only one gate — so both gates, all four lamps and all three re-cuts cost it nothing. **The addition of the second gate did not change one line of it**, which is the best evidence available before a build that the second gate is coupling rather than a riddle. |
| `empty` | FAIL (predicted) | `TheGateStaysShutUntilBothItsCratesAreHome` | The unmodified scaffold compiles, so L1 is green, and the two doors work perfectly — the preservation gate, the twin control and the integrity gate are all free for it. It dies on a **wrong-OPEN**, not a never-open: the yard ships deliberately over-permissive, so at phase 3 the first crate shoved onto the near patch of floor swings BOTH gates wide under the supplied one-body-per-pad rule while the fixture's model says both are shut. The arch gate's own gate is evaluated before the second gate's, so that is the literal the leg logs. |

Both legs run twice, at `-FPS=60` and `-FPS=20`, in separate PIE processes; all
legs must pass.

## Where each leg lands, and why not somewhere else

**The reference.** Predicted to reach the run-level gate at **340-400 s** of world
time, against a **900 s** sentinel. The earlier figure on this page said "roughly
215 s" and was low by about a factor of two — a review re-counted the step table
`StageDrive` actually builds (16 shove triples + 11 standalone walks + 2 stands =
27 walking steps and 27 dwells) and got: hold time 27 × 3.5 ≈ 98 s, push time
16 × 900/220 ≈ 66 s, routed walking ≈ 69,000 uu ≈ 138 s at the template's
500 uu/s before any taper, plus two 1.5 s re-cut windows. A drive that overran the
old 420 s sentinel would have called `FailStaging` and graded a **correct**
reference as an Error. **This is still a model, not a stopwatch, and it remains the
top open risk on this task** — but the sentinel is now far enough past it that
being wrong again by 2x is survivable. The sentinel is WORLD time under a fixed
timestep, so a passing leg never reaches it and the headroom is free.

**The empty submission, step by step, and why phase 3 is the first thing that can
catch it.**

| Phase | What happens | Which gate is armed | Empty submission |
| --- | --- | --- | --- |
| 0 | walk to the old door's end of the yard | none (the character may spawn anywhere) | — |
| 1–2 | two baseline old-door cycles, before a crate is touched | `TheOldDoorStillOpensInsideItsBand` | PASSES. The scaffold's door works: this gate is free for a no-op, which is the nature of a preservation gate. |
| 3 | the near crate is shoved home on the near patch of floor | `TheGateStaysShutUntilBothItsCratesAreHome` | **DIES HERE.** The supplied rule opens both gates on one resting body. The panel clears the 10-degree shut threshold about 0.06 s after the crate crosses the pad's radius, and the arch gate's gate is armed on every judged frame outside a re-cut window and is evaluated before the second gate's. |

Three things had to be true for that to be the *first* failure, and each is a
deliberate piece of the fixture rather than an accident:

- **The lamp channel runs LAST.** The empty submission never throws a lamp
  either, and lamp 0's expectation flips on the same frame the crate lands — but
  the lamp gate is evaluated only once whichever panel gate was armed has already
  agreed, and it waits out the disclosed 1.20 s band before it judges. The panel
  gate fires roughly 1.3 s earlier. Without that ordering the empty leg would
  name `TheGateLampsNameTheCratesItHolds` and this table would be wrong.
- **The preservation gate cannot steal it.** `TheOldDoorStillOpensInsideItsBand`
  judges a *different barrier*, and the empty submission's old door is correct,
  so it never fires at all.
- **An always-shut stub cannot pass either.** Phases 4, 6, 8, 14 and 16 all
  require the gate to be **open**, and the run-level gate requires it to have
  risen on both sides of the first re-cut. So the empty leg's wrong-open and a
  stubbed-shut answer's wrong-shut both fail, at different named gates.

## Requirements table

The full prompt-requirement to gate mapping is in `../task.md` under
**Requirement-to-assertion map**. It has 17 rows, and every one names the gate
that checks it and the condition under which that gate does not run.

| Requirement (abbreviated) | Gate | First frame it can fire |
| --- | --- | --- |
| the old door opens and shuts inside its band, every time | `TheOldDoorStillOpensInsideItsBand` | phase 1, ~1.4 s after the character reaches the pad |
| nothing else in the yard moves | `TheDoorNobodyTouchesNeverMoves` | the first frame of the run |
| no number, name, pad wiring or crate position is rewritten | `TheYardIsNotYoursToRewire` | the first frame of the run |
| a person on a gate pad never counts toward anything | `TheRunnerIsNotACrate` | phase 7, 1.5 s into the dwell |
| whatever is written on the gate right now is the answer | `TheGateAnswersToWhatItIsCutForRightNow` | phase 12 |
| a crate leaving shuts it, coming back opens it | `TheGateShutsWhenACrateLeavesAndOpensWhenItComesBack` | phase 5 |
| shut for zero, either name alone, or a crate it is not cut for | `TheGateStaysShutUntilBothItsCratesAreHome` | phase 3 |
| open exactly while both its names are home | `TheGateOpensWhenBothItsCratesAreHome` | phase 4 |
| two lamps per gate, one per name slot, in that order | `TheGateLampsNameTheCratesItHolds` | phase 3, 1.4 s after the crate lands |
| the second gate answers to its own pair, not to the first gate's | `TheSecondGateAnswersToItsOwnPair` | phase 5, where it must open while the arch gate is shut |
| both gates rose and came home again around every re-cut | `TheGateRoseAgainAfterEveryRecut` | drive completion, or the sentinel |

## Which gate names which wrong answer

PREDICTED throughout. Written down because the precedence order makes it
deterministic, and because a gate whose named failure is always stolen by another
gate is a dead gate.

| Wrong answer | Dies at | Where |
| --- | --- | --- |
| nothing at all (the empty scaffold) | `TheGateStaysShutUntilBothItsCratesAreHome` | phase 3, the first single-crate dwell |
| **a barrier is open while ALL of its pads are occupied** — one line, keeps the old door perfect, 90% of the stated requirement | `TheGateLampsNameTheCratesItHolds` | phase 3: its panel is right (one of two pads occupied) but it never lights lamp 0. It then fails the panel at phase 5 (`TheGateStaysShutUntilBothItsCratesAreHome`, the un-named crate on the contested pad) and at phase 7 (`TheRunnerIsNotACrate`). It PASSES the preservation gate — it is the "subsystem A right, subsystem B wrong" half of the coupling. |
| **narrowing the shared pad occupancy to crates** — the brownfield failure the task is named for; every gate about the NEW behaviour passes | `TheOldDoorStillOpensInsideItsBand` | phase 9, old-door cycle 3, reported against cycles 1 and 2 measured earlier in the same run. Nobody ever puts a crate on the old door's pad, so it never opens again. This is the "subsystem B right, subsystem A wrong" half. |
| reading the pair once at `BeginPlay`, or hard-coding what the level shows | `TheGateLampsNameTheCratesItHolds` | phase 3. `PrepareTest` writes the graded pair *after* every `BeginPlay`, over a different pair saved in the level, so a cached answer lights lamp 1 where lamp 0 is wanted. Its panel then fails at phase 4 (`TheGateOpensWhenBothItsCratesAreHome`). |
| identifying the crates positionally (near pad = first name) | `TheGateLampsNameTheCratesItHolds` | phases 13–14. Re-cut #1 puts the FIRST name on the far pad and the SECOND on the near one, so the panel stays right and only the lamps disagree — which is exactly why the lamp channel is graded rather than cosmetic. |
| recomputing only inside overlap begin/end handlers | `TheGateAnswersToWhatItIsCutForRightNow` | phase 17, where the pair changes with **no actor moving**, no overlap beginning or ending and no contact state changing. `TheGateRoseAgainAfterEveryRecut` names the same failure at run level. |
| latching the gate open on the first both-home moment | `TheGateShutsWhenACrateLeavesAndOpensWhenItComesBack` | phase 5, the first crate removal. Four independent remove/re-add pairs across two crates and two re-cuts follow it. |
| a correct internal flag and no output | `TheGateStaysShutUntilBothItsCratesAreHome` | phase 4 → the panel never moves, so phase 4's open is missed; nothing private is ever read. |
| an aggregator that drives every barrier of the class | `TheDoorNobodyTouchesNeverMoves` | the frame it first swings the twin, which the drive never goes within 2,000 cm of. |
| teleporting a crate onto a pad, or rewriting the gate's names to match a hard-coded pair | `TheYardIsNotYoursToRewire` | the frame it does it. The model reads LIVE transforms and LIVE names, so without this gate such an answer would make the model agree with itself. |
| a panel snapped into place instead of travelled | `TheGateOpensWhenBothItsCratesAreHome` | the frame it jumps more than 720 deg or 3000 cm in one frame's worth of time. |
| **solving it for THE gate** — find the barrier that carries names (or the lamps, or the first one found), drive that one and its two lamps. The most likely wrong answer in the hardened task, and entirely reasonable: correct for the arch gate, passes phases 0-4 outright | `TheGateLampsNameTheCratesItHolds` | phase 3, where two of the four lamps are never thrown. The panel follows at phase 5, where the second gate must open while the arch gate is shut (`TheSecondGateAnswersToItsOwnPair`), and again at phase 17 where one must fall while the other rises with nothing moving. |
| **one computed answer shared by both gates** — a global lamp index 0..3, or lamps driven off "is my gate open" | `TheGateLampsNameTheCratesItHolds` | phase 3, where the same near crate must light the arch gate's slot 0 and the second gate's slot 1, and phase 13, where the two swap. |

## What carries the discrimination without variants

**Two subsystems share a class, a pad class and one question, and want opposite
answers from it.** The narrowing that fixes the gate kills the old door; the
aggregation change that keeps the old door loses the gate. There is a named gate
on each side, and the two wrong answers are the same size as the right one.

**The load-bearing fact is read off the world and re-staged three times.** The
level is saved holding `(Bramble, Marrow)`; the fixture writes `(Marrow, Cinder)`
in `PrepareTest`, which PIE runs *after* every `BeginPlay`, then `(Bramble,
Marrow)` at phase 11 and `(Bramble, Cinder)` at phase 17. So the only pair a
submission can read ahead of time is not the pair the run grades, and a
hard-coded answer is wrong from the first judged frame. The level's pair and
re-cut #1's are deliberately the same, which is a free bonus: an agent that
hard-codes what it read in the editor is wrong for phases 3–10 and *right* for
12–16, so its failure does not look like a build fault.

**The two contested rails oppose, so the layout enforces the identity axis.**
Cinder and Bramble both park on the same far pad from opposite sides and can
never be home together — which is why re-cut #2's pair is unopenable by layout
and the gate must come down with nothing in the yard moving. Both the fixture and
`authoring/author_map.py` refuse to run a yard where any pair the gate must
*open* under fails to name the near-pad crate; get that wrong and the task is
unwinnable through no fault of any submission.

**There are TWO in-scene controls, one on each side of the coupling.** The quiet
door is the same class with the same staged numbers and its own matched pad,
3,000 cm from anything the drive touches, gauged on every frame and again at every
one of the 110 calibration checkpoints — it controls the side of the coupling the
agent must NOT touch. The second gate controls the side the agent DOES build: a
matched instance over the same two patches of floor, watching the same three
crates, cut for a different pair and re-cut on its own schedule, gauged on every
judged frame. A review found the first control could only ever be reached by an
answer that generalised to the whole class, which nothing in the scaffold suggests;
the second is reached by the ordinary answer that solves the task for one gate.

**Every graded number is a thing a person can see.** Four panel poses and four
lamps' own lights. The barrier deliberately exposes no "is open" property, so
there is no ungraded switch to throw instead of doing the work.

**The map does not exist yet.** `Content/Maps/L_OldDoorYard.umap`
is not on disk, so `cb lint` errors on `map-binary-exists` and every leg on this
page is unreachable until the orchestrator runs `authoring/author_map.py` in a
real-RHI editor and commits the binary. The script's `solve_yard()` has been
dry-run against a stub `unreal` module and passes every precondition it mirrors
from the fixture, including the two new ones (the rail-separation floor and the
"the two gates must actually disagree" trace) — but a solved geometry is not a
saved level.
