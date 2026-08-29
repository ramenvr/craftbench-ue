# notes — t3-reach-the-exit-before-they-see-you

Authored 2026-08-19 on the ThirdPerson substrate, UE 5.8, against the owner's 2026-08-18
difficulty bar. **Not yet built, not yet run** — the authoring agent was forbidden from
touching UBT, the editor or `cb`, so everything below is designed, arithmetic-checked and
source-checked but **not compiled and not measured**.

**Scope, as of the 2026-08-19 adversarial-review pass.** Written and on disk: this file,
`task.md`, the agent scaffold under
`UE-projects/ThirdPerson/Source/ThirdPerson/Tasks/t3-reach-the-exit-before-they-see-you/`
(seven actor pairs), `reference/` (the one changed pair), `discrimination/MATRIX.md`
(reference + empty only, labelled PREDICTED), the fixture at
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/t3-reach-the-exit-before-they-see-you/StealthYardFunctionalTest.{h,cpp}`,
`authoring/author_map.py`, and `cameras.json` (the camera-plan lane; not part of this release).

**Still missing: THE MAP.** `UE-projects/ThirdPerson/Content/Maps/` has no
`t3-reach-the-exit-before-they-see-you/` directory, so `tools/verify-single/map_locator.py`
cannot resolve `L_StealthYard` and the L2 leg cannot start at all — every run would exit
as a harness error rather than a graded verdict. `tasklint` therefore reports one ERROR
(`map-binary-exists`) and one WARN (`spec-h2-allowlist`, on `Composed concepts` and
`Requirement-to-assertion map` — the same WARN every sibling in this set carries). See
*What is still missing* at the end.

## Provenance

Two corpus rows, merged:

| Corpus row | Hardening status | What was taken |
|---|---|---|
| `t2-stealth-reach-exit` | HARDENED, curation `Disposition=Keep` | the spine: an exclusive three-state outcome (`InProgress`/`Won`/`Caught`), the first ending winning for ever, and the two conflict-rejection legs (`CaughtBlocksLaterExitWin`, `WonBlocksLaterDetection`) |
| `t1-ai-detects-patrols-and-chases` | ALREADY STRONG, on no K1–K5 list | the perception half: a patrolling guard, an occluder that must suppress detection, and detection within a declared window |

Neither row is on the kill list. The killed neighbour is `t1-bt-blackboard-patrol-chase`,
whose distance-gated ignore-then-switch graft went to Wave 1 #9 and is already shipped;
no design work here resurrects a killed row.

**What was deliberately NOT carried over.** The chase behaviour of
`t1-ai-detects-patrols-and-chases` (`ClosesDistance` / `SwitchesToChase`) is already owned
by the shipped `t1-guard-patrols-until-the-alarm-then-chases`, so rebuilding it here would
have been duplication. What is genuinely NEW in this task and covered nowhere else in the
tree: an **exclusive terminal outcome with a re-armable round**, **dynamic (moving)
occlusion**, and **the outcome feeding back into the observers themselves**.

**Overlap with shipped tasks, stated plainly.** The per-watcher-own-eyes sight cone
already appears in `t1-guard-only-spots-what-it-can-see` and
`t2-alarm-escalates-and-cools-down`; patrol-then-transition already appears in
`t1-guard-patrols-until-the-alarm-then-chases`. This task is not a third sight-cone task:
the cone is the *input* to the three things above, and every gate is about one of them.

### Pre-flight rewrites applied (ADOPTION-REVIEW §5.1, non-negotiable)

- **DEF-1 route policing.** The corpus row's *"Edits outside the watched-region, exit and
  terminal-state assets force FAIL 0/5"* is **deleted**. An out-of-sandbox write is exit-4
  SANDBOX-REJECT, never a graded 0/N — a graded scope breach lands in the model's
  pass-rate denominator as a capability failure.
- **DEF-2 / §7.1.2 visible readout.** No graded number is log-only: three mast lights,
  three head lamps, the plate's number painted in the air, and each watcher's pace
  readable off a walking actor. The lights are read from **light intensity**, never from a
  flag, so the readout is load-bearing rather than cosmetic.
- **DEF-3 Hard Rule #2.** Both agent-visible sections are behaviour-only. No class name,
  plugin name, asset-type name or pattern name appears in either. The two precedented
  carve-outs are used: the deliverable **path** and the **supplied property names** the
  agent must read.
- **DEF-4 undisclosed literals.** Every enforced literal is in the prompt: the quarter
  second, exactly-one-lamp, inclusive edges, flat measurement, the occluder set, the
  caught-wins tie-break, the plate-click re-arm, the stand-down rule, own-base-pace on
  restart. The reach / view-width / pace numbers are **deliberately world-read**, and the
  prompt says where to read them. Three further disclosures were added that the approved
  design did not have — see *Defects found in the approved design*.
- **DEF-5 de-padded N.** The corpus's 5-point rubric is re-derived, not transcribed. The
  lamp gate is **banded two-sided** because "no lamp is lit that should not be" is free to
  an empty delivery, and the negative control's value would be free with it. The dead-gate
  audit is written into `## Verifier specification`'s empty-submission note.
- **DEF-6 in-scene negative control.** The corpus's *temporal* "occluder removed" leg is
  replaced by the **walled sentry** — a second, matched subject in the same scene, with
  the largest reach and widest view width in the yard, gauged at **every** checkpoint.
- **§7.1.3 Tier-1 trigger.** Every trigger is locomotion into a thing: the start plate and
  the gate volume. There is no key press anywhere in the graded path.
- **§7.1.4 re-trigger.** Four rounds, two ending each way, the plate clicked four times,
  the split spot held twice, the truck shadow held three times, both gate walks doubled.

## Defects found in the approved design, and what was done

The design was implemented faithfully except where it was unimplementable or would have
manufactured a false FAIL. Each divergence is listed with its reason.

1. **The two ending-producing gates wanted three caught endings and there are two.**
   `SeenTheMomentTheyCross` ends its round caught; `TheTruckMakesAShadowWhileItPasses`'s
   second half ("within 0.4 s of the footprint clearing that line, the lamp burns and the
   round ends caught") also ends its round caught. With four rounds staged
   caught/away/caught/away there are exactly two caught endings available, and a round
   ends **once**. *Resolution*: the truck-clear ends round 1, the mid-leg cone crossing
   ends round 3, and the truck gate's *shadow-holds* half additionally fires in rounds 2
   and 4 (three firings in total). **This makes the discrimination stronger, not weaker**:
   the primary wrong answer (the waypoint poller / slow re-scan) now has **two**
   independent named deaths, because round 1's truck-clear carries the same 0.4 s deadline
   and the same 2.0 s clearance-to-the-nearest-turn precondition. The cost is that
   `SeenTheMomentTheyCross` itself fires once rather than twice.
2. **The precedence table raced two gates on the same frames.** The design put
   `TheYardStandsDownWhenTheRoundIsOver` in the same "exactly one of" list as the board
   gates, but it asserts *paces and head lamps*, not the board, and every frame it covers
   is also covered by `CaughtIsFinalEvenAtTheGate` or `AwayIsFinalEvenInPlainSight`.
   *Resolution*: two gates every frame (`TheYardIsNotYoursToRewire`,
   `ExactlyOneLampBurnsOnTheBoard`), then **exactly one BOARD gate**, then **exactly one
   CHANNEL gate** evaluated last — `EachWatcherShowsWhatItCanSeeRightNow` while a round
   runs, `TheYardStandsDownWhenTheRoundIsOver` while it is over. Those two are mutually
   exclusive by definition, so exactly one runs, and neither is suppressed inside a board
   window (suppressing them would leave the lamps and paces ungraded on exactly the frames
   that matter). This copies the shipped alarm exemplar's independent-channel move.
3. **The running-pace assertion had no permanent home.** The prompt requires each watcher
   to walk at *its own base pace* whenever a round is running, but the design only asserted
   it right after a plate click. *Resolution*:
   `EveryRoundStartsCleanWhenThePlateClicks` is armed for **the whole running round** —
   which is what the design's own wording already said ("until that round ends") — so it
   is the default board gate, the narrower windows take precedence inside it, and the pace
   assertion is covered continuously.
4. **Three literals were enforced but not disclosed** (DEF-4, the corpus's own worst
   defect, present in 60% of the rows this came from). All three would have failed a
   *correct* submission:
   - **What the board reads before the first plate click.** `ExactlyOneLampBurnsOnTheBoard`
     fires "from the first judged frame", but no round has begun then. It is derivable
     (away and caught are terminal outcomes with triggers that have not fired, so running
     is the only remaining option) — but derivable is not disclosed. The prompt now says
     it in as many words.
   - **Whether a watcher blocks another watcher's view.** The design's occluder list names
     the crates, the wall and the truck as solid and the posts/lamps/mast/plate/gate/floor
     marks as never blocking, and says nothing about the watchers — which are solid
     `BlockAll` capsules. A trace-based submission would read them as blockers; the
     fixture's footprint model does not. The prompt now states that no watcher ever blocks
     another watcher's view, and the reference puts every watcher in the trace's ignore
     list.
   - **What height the line is taken at.** The design's own risk #2 identified this ("any
     sane implementation traces at eye height") and required the *staging* to make the two
     agree, but never told the agent. The prompt now says everything that blocks stands
     from the floor to well over head height and the floor is dead level, so the height
     makes no difference — and the staging contract's three-height probe
     (20 / 90 / 170 cm) is what makes that true.
5. **The re-stage could have falsified the negative control's own claim.** The design
   multiplies one active watcher's `SightReachUu` by 1.4 and separately asserts that the
   walled sentry has "the largest reach and widest view width in the yard". Those two can
   contradict each other. *Resolution*: the sentry's dominance is a **precondition
   evaluated after the re-stage multipliers are applied** (reach at least 1.25x every
   other watcher's, view width strictly widest), and the worked geometry satisfies it
   (5,600 against a post-re-stage maximum of 4,340).
6. **The truck could shove the runner.** A solid, moving `BlockAll` box that "grinds back
   and forth across the middle" while the runner walks a lane is a drive-manufactures-FAILs
   hazard of exactly the recorded kind. *Resolution*: the truck stays `BlockAll` on every
   channel (so no trace channel can miss it — making it pawn-transparent would have set a
   trap for anyone tracing `ECC_Pawn`), it moves with **sweep off** so it can never push
   anything, and the staging contract requires no route point within 250 uu of its swept
   footprint. The worked geometry leaves ~750 uu.
7. **Round 4 was kept**, against the design's own cost note offering it as the cheapest
   cut. It is the only second *away* ending `BothEndingsHappenedTwice` has, and it is what
   makes `AwayIsFinalEvenInPlainSight` and the truck's shadow-hold fire twice. Cutting it
   would have left three of the eleven gates single-shot.
8. **The crossing window was widened, never narrowed.** The design asked for ~1.2 s of
   visibility; the contract's floor is 1.0 s and the worked geometry gives **4.86 s** with
   2.18 s / 2.20 s of clearance to the two turns. Per the drive-manufactures-FAILs law,
   widen only in the safe direction.
9. **The reference ships only the changed pair.** The design did not say. Shipping the six
   byte-identical pairs drew 12 `reference-in-substrate` tasklint warnings and is the exact
   shape of the recorded "reference inside the substrate" hazard (a reference copied over
   its scaffold and never restored makes an EMPTY submission pass). Only
   `StealthMastActor.{h,cpp}` ships.

10. **`OnConstruction` was moving the actor the yard had just placed.** The blocker and
    the truck seated their solid box above the floor by setting the ROOT component's
    relative location — and a root component's relative location *is* the actor's
    location, so every crate, the wall and the truck silently rose by half their own
    height at load, permanently, and `TheYardIsNotYoursToRewire`'s "within 2 uu of where
    the yard put them" would have compared against a position the yard never chose.
    (Flat-footprint arithmetic is unaffected, which is exactly what makes it the kind of
    defect that survives review.) *Resolution*: every one of these actors now roots on an
    **unscaled `USceneComponent` anchor at floor level** and hangs its box, mesh and lamps
    off that at plain centimetres above the floor. Five actors changed the same way —
    blocker, truck, plate, gate and mast — and the useful side effect is that all five are
    now placed at **Z = 0**, instead of each needing its own magic Z.
11. **The mast hung its three lamps off a 6x-scaled root.** It worked, because every offset
    was divided by six on the way in, but it is precisely the "child inherits the root's
    scale" hazard this repo has already been bitten by, and the arithmetic is one edit away
    from being wrong. *Resolution*: the column is now a child of the anchor and carries its
    own 6x scale alone; the three shades and the three lights hang off the **unscaled**
    anchor at 520 / 400 / 280 cm above the floor, with nothing to undo.
12. **The start plate's pad was solid, and the plate is disclosed as never blocking.** A
    `BlockAll` pad 10 cm tall does not block a line at eye height, so it would never have
    shown up in the drive — but the prompt says the plate never blocks anything, and a
    submission that reads "the line between those two spots on the floor" literally and
    traces low would have been blocked by it while the runner stood on the plate. That is
    DEF-4 with extra steps: an undisclosed occluder. *Resolution*: the pad is paint —
    non-colliding on every channel and profile, 4 cm thick, lying on the floor — and the
    staging contract's occlusion probe gained a fourth, near-floor height (5 cm) so the
    promise is tested down there rather than assumed. The one height the promise still does
    not cover is *exactly* floor level, which is coplanar with the floor plane and
    numerically ambiguous in any engine; the yard keeps nothing else solid at ankle height
    so that this is the only residual case, and it is written down here rather than left to
    be re-discovered.

13. **A gate asked for a burning lamp and a caught board on the same frame — which is
    unsatisfiable, and unsatisfiable for the REFERENCE first.** The approved design's
    `TheTruckMakesAShadowWhileItPasses` says that within 0.4 s of the truck clearing the
    line "the lamp burns and the round ends caught". But the instant the watcher can see
    the runner the round has ENDED, and the design's own stand-down rule requires every
    lamp dark from that moment. The two clauses cannot both hold, and the reference —
    which stands the yard down on the same tick it latches the loss — would have failed
    the gate written to check it. *Resolution*: the lamp carries the **covered** half
    (dark while the truck is on the line, which is where a correct submission and an
    occlusion-blind one disagree) and the **board** carries the cleared half. The same
    scoping was applied to `EachWatcherSeesWithItsOwnEyes`, whose "every lamp matches the
    model on every judged frame of the hold" is now bounded at the model's first visible
    frame, after which the round is over and the lamps belong to the stand-down gate.
14. **The worked geometry made round 3 unwinnable and put the gate inside a live reach.**
    Re-deriving it (the arithmetic is in *The numbers* below) turned up two numbers that
    would have manufactured FAILs rather than measuring anything:
    - With the plate at `x = -5,200` and the re-staged reach at 4,340, the start line sits
      **4,308 uu** from the west post of the round covering it — `0.99x` its reach — and
      **21.8 deg** inside its cone. Round 3 would have ended *caught on the frame the
      plate clicked*, so `SeenTheMomentTheyCross`, the gate the whole task is built
      around, would never have been reachable. A submission would have looked wrong at the
      one place the design believed it was measuring.
    - The gate volume sits **4,682 uu** from the same post — `1.08x` a reach of 4,340,
      i.e. 82 uu outside the marginality band. Both away endings were resting on that.
    *Resolution*: the re-stage multiplier drops from **x1.4 to x1.2** (reach 3,700), the
    plate moves west to `x = -5,800`, and the sentry's reach rises from 5,600 to **6,400**.
    The crossing window becomes 2.17 s (still well over the 1.0 s floor) with 4.86 s and
    2.20 s of clearance to the two turns; the plate is 1.32x out of reach and the gate
    1.27x; the sentry still dominates every other watcher by 1.73x, and its reach now
    genuinely EXCEEDS the 5,600 uu perpendicular distance to the lane rather than equalling
    it — at 5,600 the range-only wrong answer would have lit the sentry only at the single
    exactly-aligned point, which is no control at all. The staging contract gained a
    precondition for the start line and the gate so this class of fault reports as
    HARNESS-PRECONDITION rather than as a model failure if the map ever drifts.

**What was NOT changed.** The **stand-down coupling** was kept in full, against the
design's own risk #6, which offered dropping it as a fallback if the owner reads it as
scope creep. It is the only thing that makes the watchers' drive state agent-*written*
rather than merely agent-read, it is what gives the "perception right, feedback wrong"
wrong answer a named gate, and without it condition (a) of the difficulty bar rests
entirely on "A must be evaluated against B's live output", which is weaker. The
`randomization:` key was also left off: this is variation **within** a run, deterministic
across runs by design, because both fps legs must stage identically or they stop being a
framerate control.

## The numbers, and how they were checked

The layout was solved from one closed form and checked arithmetically before any file was
written. Nothing here has been measured in the engine.

A watcher walking a straight round of length `L`, facing along it, holds a **stationary
target beyond the end of the round** at perpendicular offset `p` and along-track lead `b`:

- inside its cone while `b >= p / tan(theta)`;
- inside its reach while `b <= sqrt(R^2 - p^2)`;
- on the **return** leg the target is more than 90 degrees off the facing whatever the
  reach, so there is **exactly one visible window per lap**.

| Quantity | Value |
|---|---|
| Watcher NEAR, staging 1 | `RoundCentre`, reach 1,900, view width 26 deg, base pace 300 |
| Watcher FAR, staging 1 | `RoundNorth`, reach 3,100, view width 30 deg, base pace 260 |
| Sentry WALLED (never re-staged) | `RoundWalled`, reach 6,400, view width 75 deg, base pace 220 |
| Re-stage | NEAR and FAR swap `RoundTag`; FAR reach x1.2 -> 3,700; NEAR view width x0.6 -> 15.6 deg; NEAR base pace x1.25 -> 375 |
| Split spot | on the lane, 3,400 uu past the CENTRE round's centre, perpendicular offset 1,600 |
| Split spot vs NEAR (staging 1) | nearest round point 2,720 uu against a reach of 1,900 — **1.43x out of reach from every phase** |
| Split spot vs FAR (staging 2) | cone bound `b >= 1,600 / tan 30 = 2,771`; reach bound `b <= sqrt(3,700^2 - 1,600^2) = 3,336`; the 2,400 uu round gives `b` in `[2,200, 4,600]` |
| Round-3 crossing window | `(3,336 - 2,771) / 260` = **2.17 s** |
| Clearance to the two turns | `(4,600 - 3,336) / 260` = **4.86 s** and `(2,771 - 2,200) / 260` = **2.20 s** |
| Start line vs the live cones | plate at `x = -5,800`: 4,870 uu from the nearest CENTRE-round point against a post-re-stage reach of 3,700 — **1.32x out of reach** |
| Gate vs the live cones | gate at `x = +5,600`: 4,682 uu against the same 3,700 — **1.27x out of reach** |
| Wall coverage | every line from the walled round (`y = 4,200`, `x` in `[-1,000, 1,000]`) to every lane point (`y = -1,400`, `x` in `[-5,800, 5,600]`) crosses `y = 3,200` within `x` in `[-1,857, +1,821]` — the wall spans `x` in `[-4,600, +4,600]`, so coverage is total with ~2,700 uu to spare at both ends |
| Sentry range check | the walled round is 5,600 uu from the lane at its closest against a reach of 6,400, so a **range-only** sight test lights the sentry over 3,098 uu of lane either side of it |
| Sentry cone check | the split spot is 6,093 uu from the sentry's round at 66.8 deg off its facing — inside both 6,400 and 75 deg — so an **occlusion-blind cone** test lights it there too; the wall crosses that same line at `x = +1,429` |
| Drive | ~290 s modelled, 380 s budget, **460 s sentinel**, against a 600 s per-leg L2 wall clock |

The 460 s sentinel is anchored on a measurement, not a guess: the shipped
`t1-touched-crate-lights-up` runs a 420 s schedule inside the same 600 s budget on this
substrate and holds a refgate certificate — but 460 s is more than that, and the sentinel
is only reached when the drive does NOT complete, so the happy path finishes at ~290 s and
the sentinel costs nothing unless something is already wrong. `l2_pie.py`'s 600 s is **per `run_l2` call**,
and `registry.py`'s dt-leg loop makes one call per fps leg, so the two legs do not share
it.

## Design decisions worth writing down

**Why every spot sits BEYOND the end of a round rather than beside it.** With the target
ahead of the round, the return pass has it more than 90 degrees off the watcher's facing,
so a watcher can only ever sight it on the outbound pass — one edge per lap, whatever its
reach. Beside the round the return pass produces a second, usually much shorter window
whose length depends on the reach, which is exactly the fragile grazing shape that makes a
one-frame sampling difference change an edge COUNT rather than an edge TIME. (This is the
alarm task's own finding, re-used.)

**Why the mast is the host and carries no outcome property.** If the mast had a "current
outcome" field, a submission could set it and be graded on it. The three lights *are* the
outcome, so nothing private is ever graded and there is no ungraded switch to call instead
of doing the work. The mast is the natural host because the yard is a committed `.umap`
under a deny-listed path: a brand new class would never be instantiated, and a renamed one
would orphan every placed instance. Reflection here buys avoiding a cast and nothing more.

**Why the fixture models occlusion with footprints and the reference traces.** Two
independent implementations of one disclosed rule is the point — a fixture that traced
would grade "did you call the same function I called". The staging contract's three-height
probe is what guarantees they cannot disagree; if that probe is ever dropped, this gate
degrades into a coin toss on trace height. It is written into `## Hidden invariants` for
that reason.

**Why the primary wrong answer is plausible here.** The scaffold nudges toward per-frame
work (the mast ships with ticking enabled), so "poll at waypoints" is not the *first*
thing a competent engineer writes. What makes it plausible is the **line trace**: three
watchers times a trace every frame reads as an obvious cost, and throttling it to a 1–2 s
re-scan, or hanging it off the "reached the next post" callback, is an ordinary and
defensible-looking optimisation. That is why the two ending windows are both timed far
from every turn — the poller must miss them *by construction*, not by luck.

**Why the re-stage happens while the yard is stood down.** No swap can jolt an outcome
there, because no outcome is being computed. A submission that fails to stand its watchers
down is re-staged mid-walk, which `TheYardIsNotYoursToRewire` and
`TheYardStandsDownWhenTheRoundIsOver` both catch **before** any later deadline overrun can
be written off as a staging fault. That ordering is deliberate: a harness exit must never
launder a FAIL.

## Hazards hit while authoring

1. **A round perpendicular to the lane cannot give a mid-leg window at both ends.** The
   first geometry ran the CENTRE round along Y so a watcher would face straight at the
   lane. With that shape visibility is entered at the *reach* bound and exited at the
   *cone* bound as the watcher walks toward the target's perpendicular foot — and the cone
   exit coincides with the near post, i.e. a turn. The ≥2.0 s clearance requirement is then
   unsatisfiable at one end. Running every round **parallel** to the lane with every spot
   **beyond the end of it** dissolves both problems at once.
2. **The design's implied 18-degree view width makes the split spot permanently
   invisible.** With `p = 1,600` and a re-staged reach of 4,340, the reach bound is
   `sqrt(4,340^2 - 1,600^2) = 4,034` while the cone bound is `1,600 / tan 18 = 4,924`. The
   cone bound exceeds the reach bound, so there is **no** visible window at all — the gate
   would have been unreachable and the round would never have ended. The covering
   watcher's view width had to go to 30 degrees, and it is the *reach* multiplier, not the
   angle multiplier, that must land on the watcher covering the split lane.
3. **A truck rail placed between the CENTRE round and the split spot silently contaminates
   `EachWatcherSeesWithItsOwnEyes`.** The first placement put the rail at `x = +2,200`; the
   sightline from the CENTRE round to a split spot at `x = +3,400` passes through
   `y` in `[-1,058, -450]` inside the truck's `x`-band, which the truck's southern rail end
   reaches. The truck's shadow would then fall across the split-spot hold, and the gate
   would be measuring the truck instead of the two watchers' eyes. The rail is staged west
   of the CENTRE round instead, and the staging contract now says "never between the CENTRE
   round and the split spot" in as many words.
4. **The runner's own capsule is the trace's end point.** A trace that ends *at* the
   runner hits the runner's capsule from outside and reports "blocked" — every sight test
   silently inverts to always-false. The runner must be in the ignore list, and so must
   every watcher (hazard 4 in the DEF-4 list above). This is the single easiest way to
   write a submission that compiles, reads correctly and never sees anybody.
5. **A scaled root multiplies both a child's offset and its collision extent.** The
   blockers and the truck therefore size their boxes **directly** from
   `BlockHalfExtentUu` / `TruckHalfExtentUu` in `OnConstruction`, and every actor in this
   task that needs a vertical offset roots on an unscaled anchor rather than on the thing
   being offset (defects 10 and 11 above). Nothing in the yard hangs a child off a scaled
   parent except the mast's column, which has no children of its own.
6. **`SCENE_QUERY_STAT` lives in `WorldCollision.h`, not `CollisionQueryParams.h`.**
   Replaced with a plain `FName` tag so the reference's include set stays minimal and
   nothing depends on a header it does not include.
7. **An elaborated type specifier in a parameter list is a poor forward declaration.**
   `const struct FCollisionQueryParams&` in the header works but declares the type at
   namespace scope from inside a class; the reference header forward-declares
   `struct FCollisionQueryParams;` explicitly instead.
8. **`PrimaryActorTick.bCanEverTick` is not a serialized UPROPERTY**, so a constructor that
   flips it from `false` to `true` DOES take effect on already-placed instances (confirmed
   against the shipped `t1-touched-crate-lights-up` reference, which does exactly that and
   holds a refgate certificate). The scaffold mast nevertheless ships with ticking already
   **enabled**, so an agent that adds a `Tick` and forgets the flag does not lose a whole
   task to a silent no-op. That is a gratuitous failure mode, not a measured capability.
9. **The plate must not be stood on at spawn.** `PlayerStart` is beside the plate, not on
   it, and `PrepareTest` refuses to start unless `RoundIndex` is 0 — otherwise round 1
   begins before the fixture has taken its baseline.

## What is still missing (the orchestrator's list)

1. **THE MAP — the one blocker.**
   `Content/Maps/t3-reach-the-exit-before-they-see-you/L_StealthYard.umap` does not exist.
   Author it by running `authoring/author_map.py` in a real (off-screen) RHI editor:

   ```text
   UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
       -script="<abs path>/authoring/author_map.py" -unattended -nopause -log -stdout
   ```

   The script refuses to save unless every geometric floor comes out, and its solvers
   were run offline against its own constants during the review pass — shadow, split,
   control, ends, route and safe bands **all pass** — so a failure at authoring time
   means the editor/assets differ from the script's assumptions, not that the arithmetic
   is wrong. **Re-run `python authoring/check_staging.py` first** (no Unreal needed): it
   runs those same solvers plus the two drive-level simulations the map script cannot do
   — whether the shadow entry ever ripens, and whether the governor releases every lane
   leg on the second watch — and exits non-zero if the staging would stall the drive.
   `--sweep` re-tunes the lane watcher's pace against the truck's speed if it does. `new_level()` saves an empty package immediately, so a map file existing
   proves nothing: the only evidence it finished is the script reaching its `SAVED` line.
   The basename `L_StealthYard` is still unused repo-wide (Hard Rule 9 holds).
2. **`docs/MAPS.md` row** and the `tasks/CATALOG.md` row.
3. **The placement convention the map must follow** — all of it is already implemented in
   `author_map.py`, and it re-derives and re-checks every value it places; listed here
   only because every one of them is silent when wrong:
   - **Z = 0** (floor level) for every `AStealthBlockerActor`, the `AStealthTruckActor`,
     the `AStealthStartPlateActor`, the `AStealthGateActor` and the `AStealthMastActor` —
     all five root on an unscaled anchor at their own foot.
   - **Z ≈ 95, MEASURED** for every `AStealthWatcherActor` (`WATCHER_STAND_Z`, corrected
     from the placed actor's own bounds). NOT 90: a capsule whose bottom face is exactly
     on the floor's top face starts every frame in contact, and a horizontal swept move
     against the floor's up-normal has `MoveDot == 0`, so `ShouldIgnoreHitResult` refuses
     the sweep at zero distance for ever and the watcher never walks its round.
   - **Z = 150** for every `AStealthPostActor`: a 300 cm cylinder centred on the actor.
   - **Scale 1 on every actor.**
   - `PlayerStart` **beside** the plate, never on it, and outside every watcher's view.
4. **Gate calibration from the first real run, MANDATORY.** Every number in `task.md`'s
   geometry table is solver output, not measurement. Read the fixture's own
   `[t3-stealth]` and `[t3-stealth calib]` log lines from the first reference run and
   confirm: the crossing window and its clearance to both turns, the truck's cover and
   clear durations, and the shadow entry's committed alignment (`shadow entry committed
   at t=… arrive in … truck across the line for … lets go at +…`). Widen only in the safe
   direction. Mid-leg timing IS the task, and a window a correct solution can straddle
   manufactures a FAIL.
5. **The L2 wall clock at both framerate legs.** The schedule is now 68 checkpoints every
   8 s (to 544 s) with the SENTINEL at 640 s, against a drive that models ~310-400 s.
   Confirm the 20 FPS leg finishes inside whatever per-leg budget the runner enforces —
   this is the one number in the task that no offline check can produce.
6. **`cb refgate craftbench-public/t3-reach-the-exit-before-they-see-you`** once the map
   exists and the tree is committed. Do not run it on a dirty tree.

## Still to do after that

The empirical half of the difficulty bar. **This task has never met a model.** Run
`cb eval --model claude-p:<cheap model>` on it once: passing first try with zero iteration
means the bar was not met and it needs another axis. The intended outcome is that a
frontier model fails roughly half the time, and the gate it should fail on is
`SeenTheMomentTheyCross` or `TheTruckMakesAShadowWhileItPasses` — if the observed failures
are all `ExactlyOneLampBurnsOnTheBoard`, the task is measuring reading comprehension rather
than coupling and the drive needs re-shaping.

Also worth a decision the orchestrator owns: this is a genuine T3 with an 8–12 hour
reference, and the front matter declares no `deadline_s` / `action_budget`, so it inherits
the 600 s / 30-action defaults like every sibling in this set. That is almost certainly too
small a budget for the work, but deviating from the set's uniform budgets would skew
cross-task comparisons — flagged rather than decided.

---

# Adversarial review, 2026-08-19 — what was found and what changed

Two reviewers attacked the task. **Nine of their eleven findings were real**, three of
them fatal to the run rather than to the grade, and working through them turned up **two
more that neither reviewer reached**, both of which would have stalled the drive before
any gate could speak. Everything below is a source change; nothing here has been compiled
or run.

## The findings, and the verdict on each

### REAL, blocker — the lamp gate could never require a LIT lamp

`GateLampsShowWhatIsSeen` asserts `Lit == ModelVisible`, but `Tick` dispatches it only
when the round is still running, and `StepModel` — which runs first in the same `Tick` —
sets the round to caught on the very frame `ModelVisible` becomes non-empty. So the gate
was only ever evaluated with `ModelVisible` EMPTY and degraded to "no lamp is lit". The
reviewer's proof stands: deleting both `SetLampLit` calls from the reference leaves all
eleven gates passing. The reference itself never showed a lit lamp for one observable
frame — it called `SetLampLit(true)`, reached `kCaught`, and `StandDown()` put it out
inside the same tick.

That voided Hard Rule 12 (the walled sentry's dark lamp cost nothing — an implementation
that lit nothing banked it) and Hard Rule 13 for the perception channel (the head lamps
were decoration, invisible even to a human playing the reference).

**The fix is not a tighter gate; it is a state in which a lit lamp is observable.** The
prompt now carries one more disclosed rule: *when a round ends because a watcher saw the
runner, the lamp of every watcher that could see the runner at that instant goes on
burning until the next round begins, and every other lamp is dark; a round that ended at
the gate leaves them all dark.* The model latches that set on the ending frame
(`CaughtBy` / `RoundCaughtBy[Slot]`), and `TheYardStandsDownWhenTheRoundIsOver` now
demands set equality against it on every judged over-frame. The reference latches it too.

Three things this buys, and they are why this shape was chosen over the alternatives:

- **A lit lamp is required for tens of seconds per caught round**, across the walk to the
  open spot and both walks into the gateway, with a human able to see who caught them.
- **It adds the third named wrong answer, and the best one.** Re-deriving the set at
  stand-down time is the natural thing to write — it is the SAME code path as the
  running-round lamp rule — and it is correct for the first second, while the runner is
  still standing where it was caught. It goes wrong only once the runner walks away.
  Nothing in the prompt rebuts it.
- **It costs no geometry.** The alternative considered was a detection dwell (a watcher
  must hold the runner for a disclosed second before the catch), which is a better stealth
  mechanic but re-sizes every staged window on a map that does not exist yet and cannot be
  measured from here. Rejected on risk, not on merit; recorded because it is the right
  next hardening step once the map is real.

### REAL, blocker — the prompt pre-negated all eleven of its own anti-gaming rows

The reviewer's charge is fair: the prompt bolded a rebuttal of every bug the fixture
hunts for, so a frontier model following it paragraph by paragraph transcribes ~120 lines
into one `Tick` and passes. Hard Rule 7 requires every gate's VALUE in the prompt; it does
not require the algorithm, its step order, or a pre-emptive answer to every wrong turn.

Removed, with every gated value kept:

| Removed | Why it was safe to remove |
| --- | --- |
| "The three watchers are not set to the same numbers" (bold) | the prompt still says the numbers are set on the watcher and belong to it; assuming they are equal is an unforced assumption, not a hidden rule |
| "What a watcher can see is settled by where everything is at that instant" (bold) | the world's behaviour (watchers walk and turn, the truck makes and breaks shadows) and the quarter-second settle are both still disclosed, and they are what a 1-2 s re-scan violates |
| "None of this is one-shot" (bold) | "the night is long: round after round, ending some one way and some the other" is the contract and is still there |
| "Whatever a watcher reads at the moment you need a number is the number" (bold) | "the sergeant may re-set the numbers … nothing announces it" is the disclosure; the follow-on sentence was the answer |
| "whatever it might have been able to see from where it stopped" | the stand-down rule now states exactly which lamps burn, which is stronger and unambiguous |
| "If both would happen at the same instant, caught wins" | unreachable — see the next finding |
| the shortlist of hosts ("the mast, a watcher, the plate, the truck or the runner") | "something already standing in the yard" is the constraint; the Workspace section lists everything standing in it |
| the two-sentence flat/height clause | compressed to one sentence — see the height finding |

### REAL, major — the "caught wins a tie" rule was unreachable by construction

`ValidateStagingContract` precondition 9 refuses to start unless the gate volume is at
least 1.25x outside every watcher's largest post-re-stage reach (the authored geometry
leaves 1.31x), so no frame can have `bAtGate && ModelVisible.Num() > 0`. Writing the two
tests in the other order diverges on exactly zero frames. `task.md` claimed it "diverges
at phase 3" and marked the gate's does-not-run column "never"; both false.

**Fixed by deletion, not by staging.** The rule is out of the prompt, out of the
requirement map (with the reason recorded in its place) and out of MATRIX's wrong-answer
table. Staging a reachable tie would mean letting a watcher see the gate, which is what
precondition 9 exists to forbid — it makes both away endings impossible.

### REAL, blocker — the model's "reached the gate" was a second, stricter definition

`StepModel` computed `bAtGate` as a point-in-box test on the runner's ORIGIN, while the
only reader the prompt discloses is `AStealthGateActor::IsSomebodyStandingInIt()`, which
is an overlap test the capsule's 42 uu radius satisfies ~40 uu of travel earlier. At the
character's 500 uu/s that is ~5 frames during which the reference reads "away" and the
model still reads "running" — and `GateRoundStartsClean` then demands a running board and
every watcher at its base pace from a yard that has correctly stood down. The committed
reference fails a named gate at both framerate legs. `Suppressed()` cannot save it:
`LastModelChangeAt` was last set at the plate click seconds earlier, and
`AnyVerdictMarginal` knows nothing about the gate boundary.

**Fixed by disclosure-alignment, not by widening a tolerance.** The model now CALLS
`IsSomebodyStandingInIt` by name (new reflection helper `CallBoolFunc`), so the fixture
and the submission read the same fact by construction. A gate that does not answer that
function is a `HARNESS-PRECONDITION`, never a graded FAIL.

### REAL, blocker — phases 5 and 14 could never complete

`bDone = (GateEntries >= 2)` but `BeginPhase` planned exactly ONE walk to the gate centre,
and `GateEntries` was reset to 0 at every phase start. Worse, and neither reviewer saw
this half: the gate-volume bookkeeping sat BEHIND `StepModel`'s round-is-over early
return, and phases 5 and 14 run only when the round IS over — so `GateEntries` could not
have reached even 1. The phase ran to its deadline and the run ended
`HARNESS-PRECONDITION` at phase 5 of 18, with rounds 2-4 never happening.

Both halves fixed: the gate reader and the entry counting now run on every frame ahead of
the round-is-over return, and phases 5/14 plan **gate, 900 uu back down the lane, gate**
(900 uu because the runner coasts past every waypoint, so "just outside" is not outside).
`bDone` additionally requires the walk to have finished.

### REAL, major — `ExactlyOneLampBurnsOnTheBoard` was judged outside the settle window

It ran before the `Suppressed` guard while every other board gate got 0.40 s of grace, so
a submission that paints the board from its own `Tick` rather than `BeginPlay` reads 0 of
3 on frame 1 whenever actor tick order puts the fixture ahead of the mast — which the
agent neither controls nor can observe — and any two-frame board transition reads 0 or 2
for a frame. Nothing in the prompt exempts this gate from the quarter second.

Moved inside the guard, first in order, and `LastModelChangeAt` is now initialised to the
world time at `PrepareTest` so the run's first 0.4 s carries the same grace. The empty
delivery still dies here, on the first judged frame — about 0.4 s in, well before the
first checkpoint at 8 s. MATRIX's "dies at checkpoint 0" wording was wrong and is fixed.

### REAL, major — the shadow spot was solved once and reused under a different staging

`SolveSpots` ran only from `PrepareTest`; `StageWatch(1)` rewrote round tags, view widths,
paces and reaches and re-ran only `ReReadNumbers` / `RebuildFootprints` /
`SolveSafeLaneBands`. Phase 16 then walked to a spot scored against the staging-1 lane
watcher.

**Fixed by removing the second window rather than re-solving the spot** — see the next
finding for why the second window could not survive anyway. `SpotShadow` is now used only
in phases 2-3, entirely under staging 1, so nothing stale can be reused.

### PARTLY REAL, minor — the truck window's "second firing"

The reviewer's mechanism was **wrong**: `TruckCoverBest` is not a run-wide maximum, it is
zeroed in `BeginPhase` at every phase start. But the conclusion was right for a different
reason — the clearing assertion was gated `&& Phase == 3` and phase 17 deliberately left
the cone before the truck cleared, so the sharper of the two anti-poller deaths fired
exactly once.

**Honest resolution rather than a cosmetic second window.** Four rounds allow at most two
caught endings and both are spoken for (the truck letting go; the cone crossing the split
spot). A second truck window inside an AWAY round would require the runner to leave a cone
while only a moving occluder protects it — a race the drive cannot govern, and the reason
phase 17 was a coin toss in the reviewed build. The window is now staged once, in round 1,
and `task.md` says so and says why. Three compensations, all real: the truck's live
footprint is in the model's visible-set computation on every judged frame of the run; the
covered half is asserted continuously across phases 2 and 3; and the clearing's "who"
half is now carried for the whole of round 1's stand-down by the latched-catcher gate.

Also fixed while in there: the covered half is now conditioned on the round still running.
Phase 3 waits a full second past the clearing, and a truck that swings back across the
line inside that second would have made the gate demand a running board from a yard
correctly showing caught — a false FAIL the reference finds first. And the doc/fixture
phase-list mismatch is gone (`task.md` said "phases 2-3, 8, 16"; the code said 2, 3, 16;
both now say 2-3).

### REAL, minor — the flat/height clause has no discriminating power

`WATCHER_STAND_Z` is ~95 and the character's capsule centre ~88 on a level floor, so over
2,000-3,700 uu of reach a 3-D distance differs by ~0.01 uu and an un-flattened direction
by ~0.2 deg — both inside the fixture's own marginality suppression (6% of reach, 3 deg).

**Not deleted — relabelled.** The clause's job is to stop a correct submission DIVERGING
from the model, which is the opposite job from discriminating. It is one sentence in the
prompt now, and the requirement map says in its third column that no judged frame can
distinguish it. Same treatment for "inclusive at the edges". Counting either as a graded
requirement is an inflated requirement count, which is the undisclosed-gate defect one
direction over.

### REAL, minor — three different sentinel schedules

`task.md` said 47 checkpoints and a 460 s sentinel; the fixture said 56 / 8 s / 500 s with
a header comment claiming ~340 s; `notes.md` said 400 s and ~215 s. All three now agree
with the code, which is the authority: **68 checkpoints every 8 s to 544 s, SENTINEL at
640 s**, drive ~310-400 s (a range, because three holds wait on the yard's own periods
rather than on a walk).

### REAL, blocker — the map does not exist

Confirmed: `UE-projects/ThirdPerson/Content/Maps/` has no
`t3-reach-the-exit-before-they-see-you/` directory. **This authoring pass cannot fix it**
— authoring the map needs a real editor, which this pass is forbidden to launch. It is
item 1 of the orchestrator's list above. The basename is fine; no other `L_StealthYard`
exists anywhere in the repo.

## Two more, found while fixing the above, that neither reviewer reached

Both are fatal to the RUN, not the grade, and both were in the same rule.

### The governor deadlocked every departure from — and arrival at — a seen place

`DriveHero` released a walk only when `EarliestSightingOnPath` proved nobody could see the
runner for a horizon of `min(transit * 1.6 + 3, 40)` seconds. Two consequences, neither
survivable:

- **Nothing could ever leave a place the runner was caught standing in.** At
  `BeginPhase(4)` the runner is at the shadow spot, plainly visible (the truck has just
  let go — that is what ended the round), so the predicate returns 0 at T=0 and the walk
  is never released. Phase 4 stalls to its deadline. The same for phases 5, 13 and 14.
- **Nothing could ever walk INTO a place a cone will sweep.** The shadow spot and the
  split spot on the second watch are exactly such places — that is what they are for — so
  the horizon extending past arrival made those walks unreleasable too. Phases 9 and 17
  walk deliberately into a frozen watcher's cone and were unreleasable for the same
  reason.

The drive would have stalled at phase 4 — one phase EARLIER than the phase-5 stall the
reviewer found, so that stall was never reachable in practice.

**Fixed by bounding the rule in two directions.** The horizon is now the transit
(`transit * 1.35 + 0.6`) and nothing beyond it, and the governor is skipped entirely once
the round has ended, because being seen changes nothing about a round that is already
over. Simulated offline against the watch-2 staging over every relative phase of the
covering watcher's lap: every leg releases, worst wait 11.8 s.

### The one truck window was a coin toss

Even with the governor fixed, phase 2 walked straight to the shadow spot and hoped. The
covering watcher's cone (as authored, a 3.49 s window once per 26.7 s lap) and the truck's
rail (a 4.15 s one-way pass) are independent periodic things; arriving while the cone holds the
spot and the truck is elsewhere ends round 1 on arrival, after which phase 2's completion
condition can never be met and the run reports a staging fault. Roughly half of all
arrivals.

**Fixed with a phase-aligned entry.** The runner now waits on a lane rest point nobody can
see (`SpotShadowWait`) and commits only when `ShadowEntryRipe` proves, by forward
simulation of all three watchers AND the truck, that leaving now (a) is unseen the whole
way in, (b) arrives inside a stretch where the cone holds the spot and the truck lies
across the line, lasting past the cover floor, and (c) is followed by the truck letting go
while the cone still holds — which is the event phase 3 grades. Predicting the truck
needed its rail ends, so the fixture now reads `GetRailEndA`/`GetRailEndB` off the truck
by name (`CallVectorFunc`) instead of assuming its placed position was mid-rail, which it
never is by the time `PrepareTest` runs.

The shadow solver's truck-cover floor went from 1.2x to **1.5x** `kMinTruckCoverS` in both
the fixture and `author_map.py`: a window sized to the GATE's floor can never satisfy the
ENTRY, and a drive that never commits reports a staging fault instead of a grade.

Simulated offline over the whole beat: **4 distinct departure WINDOWS in the first
400 s** — at ~65 s (3.05 s wide), 145 s, 265 s and 345 s — against a phase-2 deadline
covering ~292 s from its own start, so three of the four are reachable.

**And that took a staging change, which is worth recording as its own finding.** With the
originally authored numbers (lane watcher base pace 180, truck 200 uu/s) the sweep found
exactly ONE departure moment in 400 s. One is a coincidence, not a staging: the beat is
set by two independent periods, and any difference between the engine's start poses and
the model's would move that single moment out from under the drive. Sweeping the lane
watcher's pace and the truck's speed against every author-time check plus the ripeness
predicate, **pace 120 / truck 150** is the choice — it lengthens the cone window from
3.49 s to 7.33 s while leaving the truck cover at 2.31 s, which is what creates room for
the cover-then-clear to fit inside the window repeatedly. The rail itself cannot be
lengthened: its swept footprint has to stay 200 uu clear of the lane round to its north
and 250 uu clear of the lane to its south, and at half-span 415 with a 300 uu truck it is
already within ~10 uu of both. Both numbers now carry that note in `author_map.py`, and
changing either means re-running the sweep.

Two smaller corrections came out of the same work. `kRipeArriveSlackS` is an arrival
UNCERTAINTY, not a delay, so the covered stretch is now checked from the IDEAL transit
time rather than from ideal-plus-slack — the frames in between were exactly the ones on
which the cone could hold the runner with the truck elsewhere. And every arrival check is
made at both ends of the stopping segment, because `DriveHero` releases the input inside
`kWaypointUu` of the waypoint and the character coasts: the standing place is a ~90 uu
segment, not a point, and a window that holds only at the exact spot is one the drive
cannot be relied on to land in.

## What was checked offline, and how

The map script's own solvers were run against its own constants with `unreal` stubbed out
and `main()` stripped, which is the same arithmetic `PrepareTest` re-runs in the engine.
All six pass at the tuned staging: shadow spot `(-1393, -600)` with a 7.33 s window,
6.33 s of clearance to each turn and 2.31 s of truck cover; split spot `(3065, -1400)`,
invisible to all three on watch 1 and held for 2.67 s with 4.12 s of clearance on watch 2;
the sentry holding 11 of 25 route points with the wall taken away and 0 of 25 with it
there; both ends 4,870 uu from the nearest round against a largest post-re-stage reach of
3,720 (1.31x); the rounds and the lane clear of everything solid; and at least one safe
lane band per watch (the WHOLE lane on watch 1, three bands on watch 2). Then two more
simulations written for this pass: the shadow entry's ripeness and the governor's release
times, both above, and a joint sweep of the lane watcher's pace against the truck's speed
that runs every author-time check AND the ripeness predicate for each candidate.

**None of this is a substitute for a run.** It rules out the arithmetic being wrong; it
says nothing about whether the code compiles, whether the map authors, or whether the
engine's swept movement, tick order and overlap semantics behave as the model assumes.

## Files changed in this pass

- `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/t3-reach-the-exit-before-they-see-you/StealthYardFunctionalTest.h`
- `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/t3-reach-the-exit-before-they-see-you/StealthYardFunctionalTest.cpp`
- `tasks/craftbench-public/t3-reach-the-exit-before-they-see-you/reference/Source/ThirdPerson/Tasks/t3-reach-the-exit-before-they-see-you/StealthMastActor.{h,cpp}`
- `tasks/craftbench-public/t3-reach-the-exit-before-they-see-you/task.md`
- `tasks/craftbench-public/t3-reach-the-exit-before-they-see-you/authoring/author_map.py` (the shadow solver's cover floor, the lane watcher's base pace 180 -> 120, the truck's speed 200 -> 150)
- `tasks/craftbench-public/t3-reach-the-exit-before-they-see-you/authoring/check_staging.py` (NEW — the offline staging checker described above)
- `tasks/craftbench-public/t3-reach-the-exit-before-they-see-you/discrimination/MATRIX.md`
- `tasks/craftbench-public/t3-reach-the-exit-before-they-see-you/notes.md`

**Nothing under `UE-projects/ThirdPerson/Source/ThirdPerson/` changed** — the seven
scaffold pairs are untouched, so the agent-visible scaffold is exactly what it was.

