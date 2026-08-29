# notes — t2-guard-goes-to-where-it-last-saw-you

Authored 2026-08-19 on the ThirdPerson substrate, UE 5.8, against the owner's
2026-08-18 difficulty bar. The design was produced first, reviewed adversarially,
and then **re-designed** — the review's verdict was `revise`, and two of its findings
could not be answered by editing prose.

## Provenance

Owner seed: *"a guard goes to where it last saw you."* Designed as a T2 for the
`craftbench-public` set, deliberately as the third guard task in that set, and only
because it grades something the first two do not: **an event**, not a predicate and
not an externally-driven transition. `t1-guard-only-spots-what-it-can-see` grades
"can it see, right now"; `t1-guard-patrols-until-the-alarm-then-chases` grades "does
it switch when the alarm switches". This one grades a value **latched on the falling
edge** of a predicate, carried across a state change, and handed to a second actor
that cannot observe the predicate at all. Every named wrong answer in the matrix is
a way of getting the edge or the handover wrong; none of them is a way of getting
sight or a transition wrong.

## What the review found, and what happened to each item

The review is the reason the yard looks nothing like the first design.

| Review finding | Verdict | What was done |
| --- | --- | --- |
| **BLOCKER 1** — the prompt was self-contradictory: close to 5 m while sighted, never within 9 m while blind. A watchman that legitimately closed was in breach the frame sight broke, and the design papered over it with a staging precondition that was itself behaviour-dependent. | Correct, and fatal | The blind rule is now **relative to the errand, not to the gap**: it arms only after five seconds of blindness, and it exempts a watchman that is within twelve metres of the spot it was sent to. Both numbers are in the prompt. That makes it unfailable by a correct answer whatever geometry the run produces, because an honest searcher stays within seven metres of that spot — and it still catches a live-transform chaser by a factor of four. |
| **BLOCKER 2** — preconditions (a), (c) and (h) were functions of submission behaviour, so a misbehaving submission could convert a graded FAIL into `HARNESS-PRECONDITION`. | Correct | Every one of them is now a NAMED graded FAIL (`TheWatchmenAreAsTheYardBuiltThem`, `TheOtherWatchmanStayedPutUntilItWasTold`). Precondition (c) (a minimum gap at sight-loss) was **deleted outright**, not converted: the blind rule no longer needs it. Only geometry the fixture itself stages can end a run as attributed. |
| **BLOCKER 3** — latch pace and sight range against tampering; `BeginPlay` runs before `PrepareTest`. | Correct, partially | Two defences. The authoring script writes both numbers onto the **placed instances**, so they are baked into a `.umap` the agent cannot edit and changing the class default does nothing. The fixture then re-reads both **every frame** and FAILs by name on any divergence from the first read, which catches the remaining case (a run-time write). The honest residue: a `BeginPlay` write is latched by the fixture as if it were the yard's, so the fixture ALSO refuses a run where the numbers do not produce the staging the yard is built for — exactly one watchman may see the lane at the first sighting, and the range must sit strictly between the near and far lane offsets. |
| **BLOCKER 4** — close per-frame gates at the end of the drive rather than leaving them armed across ~350 s of dead clock. | Correct | The run **ends itself** the moment both legs are done and every tally is satisfied, through the same function the sentinel calls. There is no dead clock to leave gates armed across. |
| **BLOCKER 5** — a 600 s sentinel collides with the L2 layer's 600 s WALL-clock budget (`layers/l2_pie.py:369`, `registry.py` does not override it). | Correct, and I verified it independently | The sentinel is at **306 s** of world game-time, against a simulated drive of ~180 s, and the early finish means a healthy run does not reach it. **The orchestrator must still measure the real wall time** — see "What the orchestrator has to check". |
| **BLOCKER 6** — three geometric contradictions in the drive sketch. | Correct on all three | The whole yard was re-designed; none of the sketch's geometry survives. |
| **BLOCKER 7** — precondition (e) needed a capsule sweep, not a line trace, because the last-seen spot sits on the grazing line of the wall that broke sight and a 42 uu capsule clips the corner. | Correct, and it is the finding that changed the design most | **Dissolved rather than mitigated.** Sight now breaks by RANGE, not by a wall, so the last-seen spot is in open ground with no wall anywhere near it and there is no corner for anybody to graze. The drive's clearance to every wall is still checked, at 200 uu in the fixture and 250 uu in the authoring script. |
| **BLOCKER 8** — disclose the arming grace. | Correct | The five-second grace and the twelve-metre exemption are both in the prompt, in the same sentence as the floor. |
| **SHOULD-FIX 9** — justify a third guard task, or raise the composition. | Fair | Justified in the spec's opening note and above: the sibling tasks grade a predicate and an externally-driven transition; this grades an edge-latched value and a handover. The sibling's relative close-gate is noted as the better precedent — it is not adopted here because the character **stands still** for this gate, so an absolute 500 uu is physically reachable and reads plainly in the prompt. |
| **SHOULD-FIX 10** — state that `Pawn`/`CharacterMesh` ignore `Visibility`. | Correct and load-bearing | Stated in the scaffold, in the fixture header, and in the spec's *Hidden invariants*, each time with the `BaseEngine.ini` line numbers and with the consequence spelled out: re-profiling a wall to anything pawn-like silently deletes every sight break in the level. |
| **SHOULD-FIX 11** — the two post latches are not identical. | Correct | Not claimed to be identical anywhere. The difference is a settle onto the floor; every comparison is 2D with a 300 uu tolerance, and the fixture never reads the scaffold's copy. Written down in *Hidden invariants*. |
| **SHOULD-FIX 12** — add per-run randomisation. | Correct | Each alcove is slid by +/- 200 uu and the lanes by +/- 40 uu, drawn from `FPlatformTime::Cycles()`. The draw is re-checked against every staging precondition and **halved until they hold**, with a zero draw as the final fallback, and it is logged. A jitter may widen the yard's variety; it may never manufacture a FAIL. |
| **HOUSEKEEPING 13** — ASCII-only FAIL strings, one literal per gate, id rule. | Applied | Every `FinishTest` literal is ASCII. Each gate opens with its own name so the MATRIX substring is a contiguous span of one source chunk. The id names the outcome, not the mechanism. |
| **Ungradeable: "the hero has not been displaced by anything but the fixture's own drive"** — an `AFunctionalTest` can measure displacement, it cannot attribute it. | Correct | Restated as a bounded rolling-window displacement (820 uu over 1.0 s), and the collision worry it raised is designed out: the scaffold's stand-off is 150 uu against a 42+42 uu capsule pair, so a watchman closing on the character never touches it. |
| **Ungradeable: `TheYardRanBothLegs` clause 2 is a tautology, clause 3 is redundant** | Correct on both | Clause 2 (`|L2 - L1| >= 2000`) was **deleted**: it was a fact the fixture stages, so it could only ever have failed as a staging fault charged to the model. Clause 3 survives only as the arming backstop for `SightWinsOverWhateverItWasDoing`, and reports through that gate's own literal. |
| **Ungradeable: the leg-scoped gates break the constant-denominator rule** | Fair | Documented rather than papered over: this task produces a single verdict from the first gate that fires, so there is no ratio to improve, and the rule is inapplicable. Both leg-scoped gates are named in the requirements table. |
| **Ungradeable: the blind gate is unbounded in time** | Correct | Resolved by the early finish (BLOCKER 4). |
| **"Not over-tricked, but OVER-SPECIFIED"** — the prompt pre-negated every wrong answer, so the gates caught not-reading rather than not-knowing. | Fair, and acted on | Three enumerations were **removed** from the prompt: "not to where they have got to since / not where it was standing / not where it first spotted them", "not to wherever the character actually is, and not to the watchman who called it in", and "it is told when sight is LOST, not when the character is first spotted". What is left is the positive statement of each requirement and every number a gate demands. The disclosure law is about VALUES; it is not a licence to pre-negate the answer. |
| **"Not hard enough for a frontier model"** | Partly accepted | The composition was not raised by bolting on a supersede/expiry semantic — that was considered and rejected as a way of adding rules rather than depth, and it would have made the drive long enough to threaten the L2 wall-clock budget. What was done instead: the ALERT MODEL is now general (any sight-loss opens a fresh alert and retires the previous one unjudged), which is what makes a legitimate re-acquisition a first-class case rather than a fixture bug; and the hours estimate was corrected downward to the review's own number, 2.5-4 h. |

## The simulation, and why there is one

Nothing in this task could be tuned by eye, and the fixture cannot be run from here.
So the whole yard and the whole reference behaviour were simulated offline first — a
throwaway 2D model with the same sight rule (range + segment-vs-box), the same speeds,
the same 1/60 s step, and the reference's own state machine — and the layout was
searched until every gate had a margin at every corner of the jitter band. The numbers
quoted in the spec and the matrix are that simulation's, not guesses.

Seven layouts were built and discarded before this one. What killed each is worth
keeping, because every one of them is a trap that looks fine on paper:

1. **A wall breaks sight; the watchman walks to the spot.** The watchman *moves*, so it
   comes out from behind the wall and re-acquires within a couple of seconds. Sight
   never durably breaks and there is nothing to search. **A sight break caused by an
   occluder is only durable if the occluder also hides the target from the searcher.**
2. **A dog-leg corridor.** Fixes (1), but the last-seen spot then sits on the grazing
   line of the wall that broke sight — exactly the review's BLOCKER 7 — and the
   watchman's straight walk to it clips the corner.
3. **A doorway in a long barrier.** The last-seen spot lands *in* the doorway, and a
   searcher standing there sees straight down the cone into the room.
4. **A room with the hiding place tucked against the doorway wall.** Durable against
   every exterior observer, but then the hiding place is only ~800 uu inside, so a
   live-transform chaser sees the character before the blind floor can catch it.
5. **A deeper room with an internal partition.** The chaser rounds the partition and
   re-acquires at ~2200 uu — still above any floor a correct searcher can survive.
6. **Sight breaks by range, no walls at all.** Durable and clean, but then a chaser
   re-acquires at the sight range and the blind floor never fires either.
7. **Posts moved far apart to lengthen the responder's walk home**, so that the
   character could get back out and be seen while the responder was still walking. It
   works, and it pushes the yard past 20,000 uu wide for a gain the fixture cannot
   guarantee anyway. Dropped in favour of three standing spots and an honest note.

The layout that survived is **(6) plus an alcove**: sight breaks by range, because the
character outruns the watchmen, so the last-seen spot is in open ground with a real gap
behind it; and the character then hides in a three-walled alcove **whose mouth faces
away from the lane**, so a blind chaser has to walk up to the outer wall — about
600 uu from the character — before it can see anything. Sight-loss gives the gates
their distance; the alcove gives them their blindness. Neither alone was enough.

## The three numbers everything rests on

- **Pace 300 uu/s against the character's 500.** This is not flavour. It is what makes
  sight break by range with ~2400 uu of gap instead of with the watchman standing on
  the character, and it is why the "it only ever walked" budget (pace x 1.4 + 60 =
  480 uu/s) can be set **below** the character's speed: a submission that speeds its
  watchmen up to keep the character in view fails that gate rather than quietly
  deleting every other one. The authoring script refuses to save a level where that
  inequality does not hold.
- **Sight range 2400 uu, lanes 1800 uu from one post and 3000 uu from the other.** The
  range must sit strictly between those two, with margin, or either nobody sees the
  character or both do and the radio has nothing to carry. Checked by the authoring
  script and again by the fixture.
- **The alcove opens away from the lane.** Checked by sampling the whole band a
  watchman could be searching (the lane, plus or minus the seven-metre hold radius) and
  refusing to save if the hiding place is visible from any of it.

## Hazards hit while building this

- **`new_level()` saves immediately.** An authoring script that raises later leaves a
  plausible-looking empty map on disk that the automation run then reports as "no
  tests". Check the log for the `SAVED` line, not the filesystem for the file. (Carried
  over from `t1-touched-crate-lights-up`; the same trap applies here.)
- **A trace that starts inside geometry answers nothing useful.** The fixture's staging
  check samples a band around the lane, and part of that band falls inside an alcove
  wall. Those samples are now skipped on clearance before the trace is issued.
- **A precondition that ends the run cannot be retried.** The first cut of the jitter
  loop called `FinishTest(Error, ...)` from inside the precondition check and then tried
  the next draw — on a test that had already finished. The check now reports a reason
  string and `PrepareTest` decides.
- **Leg 2 can stall.** Its search is deliberately interrupted, so the "both have held
  their six seconds" release could never arrive for a submission that never settles.
  There is now an unconditional time-out on that release, computed from the disclosed
  allowance, so a real failure reports as a failure instead of hanging to the sentinel.

## What is honestly NOT enforced

- **`SightWinsOverWhateverItWasDoing` cannot pin down which state the watchman is in.**
  The three standing spots are spread along the second watchman's homeward line
  specifically so that one of them is likely to land while it is still walking, and the
  last is close enough to a post that a watchman already standing on one has the
  character in plain sight — so the gate is guaranteed to be ARMED. It is not guaranteed
  to arm against a *non-idle* state. A submission that never chases, and one that latches
  until its own machine resets, both fail it outright; a submission whose only defect is
  that it polls the eyes in the watch state and nowhere else may, on an unlucky
  interleaving, be armed against its watch state and pass. Said plainly here rather than
  claimed away in the spec.
- **The per-run jitter is small** (+/- 200 uu on an alcove, +/- 40 uu on a lane). It
  closes the theoretical two-constants-and-a-clock cheat; it is not the primary defence
  against hard-coding, which is the reversed roles and moved walls of leg 2.
- **No model has met this task.** The empirical half of the difficulty bar is untested.
  `cb eval --model claude-p:<cheap model>` once, first: passing first try with zero
  iteration would mean it needs another axis.

## What the orchestrator has to check when it builds

1. **The map does not exist yet.** `authoring/author_map.py` must be run headlessly to
   build `Content/Maps/t2-guard-goes-to-where-it-last-saw-you/L_NightYard.umap`, and it
   must print its `SAVED` line. It refuses to save if any staging invariant fails.
2. **Wall-clock time of the L2 leg.** The sentinel is at 306 s of game time and the
   simulated drive is ~180 s, but this level carries three skeletal-mesh characters with
   animation over up to ~18,000 fixed steps. If the L2 leg approaches the 600 s wall
   budget (`layers/l2_pie.py:369`), the fix is to plumb a larger timeout for this
   fixture, not to shorten the drive — the drive's length is what the gates measure.
3. **The reference's measured trace against the simulation.** The `[t2-lastseen alert]`
   and `[t2-lastseen calib]` log lines print the last-seen spot, both deadlines, each
   watchman's closest approach and each one's accumulated hold. If the real numbers
   differ materially from the simulated ones quoted in the matrix, the matrix table is
   what should be corrected — not the gates.
4. **The empty leg fails at the quoted substring**, not merely fails.
5. **Nothing outside this task's own directories was touched.**
