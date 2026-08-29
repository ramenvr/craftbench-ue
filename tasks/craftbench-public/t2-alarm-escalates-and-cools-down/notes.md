# notes — t2-alarm-escalates-and-cools-down

Authored 2026-08-19 on the ThirdPerson substrate, UE 5.8, against the owner's
2026-08-18 difficulty bar. **Not yet built, not yet run** — the authoring agent
was forbidden from touching UBT, the editor or `cb` (other agents were live in
the same tree), so everything below is designed, arithmetic-checked and
source-checked but not compiled.

## Provenance

Owner seed design (a three-stage yard alarm with hysteresis, two unlike guards,
a floodlight readout and a patrol-pace readout), then one adversarial review.
The review's verdict was **revise**, not reject, so the seed intent is intact.
Every item in `required_revisions` was applied; the two that changed the design
most are listed first.

| Critique item | What was done |
|---|---|
| **WALL-CLOCK BLOCKER.** `tools/verify-single/layers/l2_pie.py:369` declares `timeout_seconds: float = 600.0` and nothing passes it; exit 124 is a GRADED FAIL charged to the model. The design asked for a 760 s sentinel, twice (fps_legs). | Verified in the harness: the 600 s budget is **per `run_l2` call**, and `registry.py`'s dt-leg loop makes one call per fps leg, so the two legs do not share it. Then the drive was **cut from ~493 s to ~280 s** and the sentinel from 760 s to **400 s**: `QuietSecondsPerStepDown` 14 -> 5, cap 6 -> 5, over-exposure 9 raw -> 8, base paces 620/480 -> 280/260, hunting scale 2.2 -> 1.8, and the leg-2 visit to the close-in spot dropped. **The anchor is measured, not guessed:** `t1-touched-crate-lights-up` ships a 420 s sentinel, runs the whole schedule, and holds a refgate certificate on this box — so ~400 s of world time is proven to fit inside the 600 s wall clock on this substrate. 400 s is under that, and the fixture finishes itself at ~280 s. |
| **ADD A SECOND GENUINELY INTERACTING SUBSYSTEM** (criterion (a) was not met: floodlights and patrol pace were two independent one-line fan-outs of the same enum). | Adopted the critique's own suggestion, in one disclosable sentence: a floodlight carries `ReachBonusUu` and `CoversRoundTag`, and **while it burns the guard walking that round has that much added to its reach**. Two of the six carry a bonus, both at the hunting setting. The lamp loop is now an INPUT to perception: get it wrong and the sighting count changes, which changes the setting, which changes the lamps. It also forces an explicit decision about the order of the five steps inside one tick, which the prompt settles ("what a guard can see at any instant is settled by the floodlights as they stand at that instant"). `PrepareTest` refuses to start if no floodlight carries a bonus, so the interaction cannot be silently lost. |
| **FIX THE COUNT-EQUALITY BACKBONE** (a) disclose the predicate, (b) stop routing transits across cone boundaries, (c) extend the margin validation to the whole path. | (a) The prompt now states the origin (where the guard is standing), the target (where the character is standing), that it is flat, and that both edges are inclusive. (b) Every transit runs out through the quiet spot along ONE lane at the split spot's own offset — and on the first watch the covering guard is *geometrically blind to that entire lane*, so the only cone boundary the walk crosses is the final head-on approach. (c) `PrepareTest` scans the lane for an along-track position that gives every required window >= 2.0 s and every gap >= 2.0 s at **every** setting, and rejects any position where the cone edge lets go within 80 uu of a post. |
| **ADDRESS TICK ORDER EXPLICITLY.** | Two answers, both written into the fixture header. First, the structural one above (no grazing crossings, so a one-frame difference shifts an edge TIME, never an edge COUNT). Second, and this is the load-bearing one: **the count saturates at both ends and every phase of the drive ends at one of them** (the cap, or zero). Saturation re-syncs two independent counters, so a divergence cannot outlive the phase it started in. That is what makes a 280-second integer comparison safe without ever reading the submission's own count. |
| **MAKE THE YARD ACTUALLY UNOCCLUDED and say so.** | Everything except the floor and the two guards is authored `NoCollision` on every channel (profile AND enum — `set_collision_enabled` alone did not survive into a saved level on an earlier task). The authoring script asserts it by walking every `PrimitiveComponent` in the level, and the fixture asserts it at run time by tracing from each guard at nine phases of its round to a dozen points along the route. The prompt says "nothing in the yard to hide behind" in as many words. |
| **FIX THE CAP GATE'S DISCRIMINATION** (the no-clamp variant died at `TheAlarmComesDownOneStepAtATime` first, so the cap gate was dead for the variant it exists to catch). | Solved by moving the over-exposure to the **second** watch and giving `TheAlarmStopsCountingAtTheCap` the whole second-watch cooldown, with the step-down and deadband gates disarmed there. The first watch is deliberately **not** over-exposed — phase 3 leaves 1.5 s after the cap against a 5.6 s hunting lap — so the unclamped answer behaves identically to a correct one on the first watch and cannot die at the wrong gate. Traced numerically: model 5->0 in 25 s, unclamped-carrying-8 5->0 in 40 s, first divergence at t=15 s with the model at count 2 (watching) and the unclamped one at 5 (hunting), inside the cap gate's window. |
| **REBUILD THE SETTLE RULE AGAINST THE FASTEST SCALE.** | The window/gap precondition is evaluated at **every setting**, using the reach that setting implies, and re-evaluated after the watch change with the raised hunting scale. Measured for the shipped numbers: the worst window in the whole run is 2.52 s and the worst gap 2.99 s, against a 0.75 s post-change suppression plus a marginal band that costs at most ~0.5 s. |
| **GATE GUARD MOVEMENT DIRECTLY.** | `TheYardIsNotYoursToRewire` now checks that each guard's location is within 60 uu of the segment between its own two posts — a segment comparison, not a fixed point, because guards legitimately move. This is load-bearing rather than ceremonial: the fixture's model reads the guards' LIVE transforms, so without it a parked guard would make the model agree the yard should be hunting and every window would become unreachable. |
| **PUBLISH A FULL PRECEDENCE TABLE.** | Eight gates, written into `task.md`, into the fixture's header comment, and into `discrimination/MATRIX.md` with a row per wrong answer naming which gate catches it and where. At most one windowed gate is armed on any frame, and `TheYardShowsTheRightStage` / `TheGuardsSpeedUpWithTheAlarm` are suppressed inside every windowed gate's window. |
| **HARNESS EXITS MUST NOT LAUNDER A FAIL.** | Every deadline overrun and the sentinel path re-check `TheGuardsSpeedUpWithTheAlarm` and `TheYardIsNotYoursToRewire` **unconditionally** before writing anything off as a staging fault. The submission writes the guards' pace, the pace decides how often a cone sweeps the character, and therefore whether phases complete — so that path had to be closed explicitly rather than by luck. |
| **RECOMPUTE ALL LEVEL GEOMETRY** (the design quoted three impossible windows). | Every number was discarded and re-derived, then **checked numerically** before authoring (see below). The closed form itself survived review — the widest offset at which a guard walking a straight round can ever hold a stationary target is `reach x sin(view width)` — but nothing built on it did. |
| **FIX THE P1/P2 NARRATIVE for the stage-0 floodlight.** | Correct: with settings 1,2,0,2,1,1 exactly one floodlight must BURN at calm, and the floodlights start dark, so the empty submission fails on the **first standing phase**, not the first exposure. The MATRIX row and the named substring say so. |
| **DROP the degenerate wrong answer.** | "Zeroing a guard's reach so the bookkeeping gets easier" is gone from the wrong-answers list. It survives only as anti-gaming note 9, labelled as anti-gaming rather than a plausible first pass. The `BasePatrolSpeedUu` / `PatrolSpeedUuPerSec` mix-up is kept — that one is a real slip. |
| **CORRECT premise 5** ("the agent may rename or subclass freely"). | Deleted. The fixture header now says in as many words that reflection here buys avoiding a cast and **nothing more**, because the guards, floodlights, posts and panel are placed instances in a committed `.umap` under a deny-listed path — a renamed class orphans them and a fresh subclass is never instantiated. |
| **RE-TIER to the lower half of T2.** | `## Reference solution metadata` says **3–4 hours**, itemised, and says explicitly that "the setting has to be remembered state" is reading comprehension plus care, not a discovery, because the prompt says it. |

## What was NOT taken from the critique, and why

- The critique wanted the run-level gate to require **three** rises from calm.
  The drive as re-timed affords **two** (one per watch), and buying a third costs
  ~55 s of wall clock that the 600 s L2 budget cannot spare. Two rises **plus a
  proven full return to calm in between** discriminates exactly the same set: a
  latched alarm rises once, and a quiet clock armed once never returns to calm so
  the second rise never happens. `TheAlarmRoseAgainOnTheNewWatch` asserts both
  halves and says so in its message.
- The critique's `ValidateGeometry` sketch checked "the split spot is beyond the
  OTHER guard's reach". That is backwards — on the first watch the other guard is
  on the far round, 6,000 uu away, and its reach there is irrelevant. The shipped
  check identifies which watch it is **from the covering guard's own eyes**
  (either it can never hold anybody at the split spot even fully lit, or it holds
  them comfortably at every setting) and fails as a staging fault if it is
  neither.

## The numbers, and how they were checked

The geometry was solved and verified in a standalone Python transcript before any
file was written (the transcript itself is not committed; the same arithmetic
lives in `authoring/author_map.py` and in the fixture, and both refuse their job
if it does not come out).

| Quantity | Value |
|---|---|
| Round length / lap | 1,400 uu / 5,600 uu, two rounds 6,000 uu apart |
| Slit guard | reach 2,400, view width 13 deg, base pace 280, widest offset **540 uu** (674 uu fully lit) |
| Wide guard | reach 2,100, view width 55 deg, base pace 260, widest offset **1,720 uu** (2,212 uu fully lit) |
| Floodlight settings, name order | 1, 2, 0, 2, 1, 1 -> lit counts **1 / 4 / 6** |
| Reach bonuses | 600 uu over RoundNorth and 500 uu over RoundSouth, both from the hunting setting |
| Dials | raise 2 / 5, drop 2 / 0, cap 5, quiet 5.0 s, scales 1.0 / 1.4 / 1.8 |
| Watch change | raise-watch 2 -> 3, hunting scale 1.8 -> 2.1 |
| Close-in spot | 296.9 uu off the round, 1,860 uu past its +X end |
| Split spot | 1,077.4 uu off the round, 1,460 uu past its +X end |
| Quiet spot | on the same lane, 4,610 uu past the end — 4,056 uu from the nearest round point against a largest-reach-anywhere of 3,000 |
| Worst sighting window / gap anywhere in the run | 2.52 s / 2.99 s |
| Split-spot slack after the sergeant raises the hunting scale | +0.56 s |
| Cooldown trace | model 5,4,3,2,1,0 at t = 0,5,10,15,20,25 -> hunting, hunting, hunting, watching, watching, calm; unclamped-carrying-8 reaches calm at t = 40 |

The split spot is **1.60x** beyond the Slit guard's widest possible offset even
fully lit, and **0.63x** of the Wide guard's unlit one. That is the whole task in
one number: the same place, two watches, opposite answers.

## Design decisions worth writing down

**Why the count re-syncs matter more than the settle window.** The obvious way to
protect a 280-second integer comparison is a wide settle window. That is not
enough, because a settle window forgives a *late* answer and this failure mode is
a *permanently offset* one. The fix that actually works is structural: the count
clamps at the cap and floors at zero, so any two counters that both obey the
disclosed rule agree exactly at those two values, and every phase of the drive is
written to end at one of them. The settle window then only has to cover the
one-frame jitter around each edge, which it comfortably does.

**Why the spots sit BEYOND the end of the round rather than beside it.** With the
target ahead of the round, the return pass has it more than 90 degrees off the
guard's facing, so a guard can only ever sight it on the outbound pass — one edge
per lap, whatever its reach. Beside the round the return pass produces a second,
usually much shorter, window whose length depends on the reach, which is exactly
the fragile grazing shape that desynchronises counters. This also makes the
"a burning floodlight lengthens the reach" clause safe: it widens windows without
ever adding an edge, because the return-pass exclusion is angle-limited and
therefore reach-independent.

**Why the fixture never grades the climb loosely.** The rising branch of the
deadband gate is asserted while the character is STANDING at a spot, with the
guard sweeping past it — a clean, repeatable geometry — rather than during a
transit. Both branches of the hysteresis gate are therefore exercised on
stationary geometry.

**Why the far guard is designed to be irrelevant.** The drive walks entirely on
the side of the watched round away from the other one, and the fixture asserts
that every point of the route is at least 1.25x the far guard's reach from the
far round. A sighting nobody designed, landing in the middle of a graded window,
would force both counters to agree about something neither the author nor the
agent reasoned about.

**Why the panel carries no readout.** If the board had a "current setting"
property, a submission could set it and be graded on it. The floodlights and the
guards' pace ARE the readout, so nothing private is ever graded and there is no
ungraded switch to call instead of doing the work.

## Hazards hit while authoring

1. **`FGuard` is a private nested type, and an out-of-class definition's LEADING
   return type is looked up in NAMESPACE scope.** `const AAlarmEscalationFunctionalTest::FGuard* AAlarmEscalationFunctionalTest::CoveringGuard() const` does not compile for that reason. Both accessors use a trailing return type (`auto ... const -> const FGuard*`), where the return type is looked up after the declarator-id and class access applies.
2. **The first cut of the marginal-band test used OR where it needed AND.** "Within 3 degrees of the view width" fires constantly at the quiet spot, where the guard's facing sweeps past that angle every lap while the character is four times its reach away — which would have suppressed the gates for most of the phase where the empty submission is supposed to die. A verdict is only marginal when the boundary in question is the one deciding it: near the range boundary AND inside the cone, or near the cone edge AND inside the range.
3. **The design's first geometry put both spots BESIDE the round**, which forced the two guards' angle-limited windows into a 1,400 uu round that could not hold both — the narrow guard needs to be 1,286 uu behind the target to clear 13 degrees, the wide one only 208 uu. Moving the spots past the end of the round dissolved the conflict and killed the return-pass problem at the same time.
4. **Two painted elements fell off the floor** when the limit lines were drawn on the outward side of each round (the wide guard's lands at y = -4,720) and when the narrow guard's rear wedge ran to x = -3,100. The floor grew to 10,200 x 10,200 and both limit lines are drawn on the yard-facing side; the cone is symmetric, so it is the same statement either way.
5. **`PrimaryActorTick.bCanEverTick` is NOT a serialized UPROPERTY**, so flipping it from `false` to `true` in a constructor does take effect on already-placed instances. Confirmed against the shipped `t1-touched-crate-lights-up` reference, which does exactly that and holds a refgate certificate.
6. **`TArray::Add({...})` with a braced-init-list of a local aggregate is ambiguous** between the const-ref and rvalue-ref overloads; the shipped code writes `Add(FCase{...})`.

## What the orchestrator must check

Listed in the report, but the two that matter most: the L2 **wall clock** for a
400 s sentinel at 60 FPS on this map (the budget is 600 s per leg and there is no
env override), and that `author_map.py` actually reaches its `SAVED` line —
`new_level()` saves an empty package immediately, so a map file existing is not
evidence that the authoring script finished.

## Still to do

The empirical half of the difficulty bar. **This task has never met a model.**
`cb eval --model claude-p:<cheap model>` on it once: passing first try with zero
iteration means the bar was not met and it needs another axis.
