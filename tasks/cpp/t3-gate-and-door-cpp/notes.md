# notes — t3-gate-and-door

Authored 2026-08-19 on the ThirdPerson substrate, UE 5.8, against the owner's
2026-08-18 difficulty bar. **Not yet built, not yet run** — the authoring agent was
forbidden from touching UBT, the editor or `cb` (builds are serial on this machine and
belong to the orchestrator), so everything below is designed, arithmetic-checked and
source-checked but not compiled.

**Scope of this change-set.** Everything except the `.umap`: `task.md`, this file, the
agent scaffold (4 pairs), the reference (1 pair), the L2 fixture
(`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/<id>/`), `authoring/author_map.py`,
`cameras.json` (the camera-plan lane; not part of this release) and `discrimination/MATRIX.md`. **The committed `L_OldDoorYard.umap` does
not exist and cannot be produced from here** — authoring it means running the editor,
which this agent is forbidden to do. `cb lint` errors on `map-binary-exists` until the
orchestrator runs `authoring/author_map.py` and commits the binary.

**What WAS run, since no build was allowed** — three static, no-UE checks, all green:

1. `tools/verify-single/spec.py::parse_task_file` on the spec: the v2 front matter
   parses, and `fixtures:` resolves to `L_OldDoorYard :: AOldDoorYardFunctionalTest`
   (an inline-list mistake here is the single most common authoring failure and it exits
   2, not FAIL).
2. `tools/run-agent/prompt_extract.py::extract_agent_visible_prompt`: the agent sees
   exactly the two allow-listed H2s and nothing else, 2,330 words — the longest in the
   set, against 1,175-2,175 for the other nine T3s. The extract was then leak-scanned by
   hand; two hits were fixed (below).
3. `tools/verify-single/tasklint.py` on the spec: **1 ERROR, 1 WARN** as of
   2026-08-19 (it was 2 and 2 before the fixture landed). The ERROR is
   `map-binary-exists` — the one artifact still missing. The WARN is
   `spec-h2-allowlist` (`Composed concepts` + `Requirement-to-assertion map`,
   byte-for-byte the same WARN every shipped sibling in this set draws). Notably
   absent: `reference-in-substrate`, which fires when a reference file is
   byte-identical to its scaffold — the reference differs by 135 added lines, so the
   empty submission cannot be passed by a scaffold that was never restored.
4. `authoring/author_map.py::solve_yard()` dry-run against a stub `unreal` module
   (`.t3patch_dryrun.py`, not committed): every mirrored precondition passes, and the
   solved lanes now read `x=380` / `x=-1180`, i.e. the fixture's own numbers.

## Provenance

| Source | What it said | What was carried, and what was not |
|---|---|---|
| `hardened-tasks.csv` → `t3-sob-pressurepad-two-crates` | "Without adding native/C++, make the supplied gate require both identified crates on the pressure pad set … Preserve the fixture-declared ordinary character-control route and one versioned unrelated gameplay route." | The **contract** is carried whole. The **route policing** is struck: "without adding native/C++", "edits outside the supplied aggregation/gate graphs … force FAIL 0/5" and "writable scope is limited to the existing graphs" are all DEF-1 (grading HOW, 47% of the corpus). Out-of-sandbox writes are exit-4 SANDBOX-REJECT and never a graded 0/N. |
| `verification-contracts.csv` → same row | Named assertions `ClosedWithZeroCrates \| ClosedWithOneCrate \| OpensWithTwoCrates \| ClosesWhenOneRemoved \| UnrelatedGameplayIntact`; empty-submission failure `OpensWithTwoCrates fails`; gamed variants always-open / latched-open / deleting unrelated systems. | All five assertions survive, renamed to outcome names and re-cut so each is failable: `TheGateStaysShutUntilBothItsCratesAreHome` (the first two), `TheGateOpensWhenBothItsCratesAreHome`, `TheGateShutsWhenACrateLeavesAndOpensWhenItComesBack` (which also absorbs `ReaddingRemovedCrateReopensGate`), and `TheOldDoorStillOpensInsideItsBand` for `UnrelatedGameplayIntact`. The three gamed variants map onto anti-gaming notes 1/6/2. |
| `check-contracts.csv` (5 rows) | 1 point per check, 5/5 = PASS. | Not carried: CraftBench is binary per task, and the per-cell `model × rig × starting-project` matrix is the harness's job, not the spec's. |
| `ADOPTION-REVIEW-2026-08-16.md` §9 K4 | The row is on the **kill list** — one of the 47 targeting an absent Stack-O-Bot substrate. | Correct, and this is **not a resurrection**. |
| Same doc §10 watch list **#17** | "Keep only the **brownfield-preservation** idea and rebuild it on ThirdPerson: ship a level with one NAMED pre-existing behaviour, have the agent add a new gate, and make *the pre-existing door still opens inside its pinned band* the headline scored check. Nothing in the built tree measures that adding a feature did not break an existing one." | This is exactly what was built. The one deviation: the reshape suggested reusing the built `gp-door-hitch` door as the pre-existing behaviour. That door lives in another task's map and another task's folder, which this assignment forbids touching, so the old door is a **new placed instance of this task's own barrier class** — which is strictly better for the coupling, because the old door and the new gate then share a class, a pad class and an occupancy question. Sharing the seam is what makes the preservation gate failable by a real submission instead of decorative. |
| Same doc §5.1 (pre-flight rewrites) | Outcome-named id · behavior-only mission · route clauses to advisory · disclose every enforced literal · **in-scene** negative control · playable + pre/post staging with a floor, markers, a camera, a visible readout and a human-performable trigger. | All six applied. The id was pre-assigned and already names the outcome. The in-scene control is the twin door 3,000 cm east, gauged every frame. The pre/post pair is explicit: old-door cycles 1 and 2 are **reported as the checkpoint-0/1 baseline** and cycles 3 and 4 are compared against them **from the same run**. |
| Same doc §7.1 | Showroom map · visible readout · **Tier-1 input driver** · re-trigger convention. | Trigger is locomotion into a pushable prop (Tier 1); no key press is injected anywhere. Every trigger fires at least twice (four remove/re-add pairs, four old-door cycles, two runner-on-pad dwells, two re-cuts). The readout is the two lamps' **lights**, graded, plus the panels' own poses. |

## What I changed in the approved design, and why

Six changes, strongest first. Some repair a defect in the design as written, some take an
upgrade it explicitly left open, and one records a decision it left to the implementor;
each entry says which it is.

0. **RE-CUT #0 — the graded pair is written by the fixture, not baked into the map.**
   This is the one place the design did not meet the 2026-08-19 difficulty bar, and it
   says so itself: condition (c) requires that *"a hard-coded answer must be wrong from
   the first frame"*, and the design's own honesty note conceded that the pair is
   *"staged into the committed `L_OldDoorYard.umap` … constant across reps"*, with a
   per-leg shuffle offered as *"an upgrade, not a dependency"*. As designed, a hard-coded
   answer is right for phases 3-10 and only dies at phase 12.

   The fix costs nothing and changes no phase: **the level is saved holding one pair and
   `PrepareTest` writes another** — the one the phase table assumes — before the first
   judged frame. The only pair a submission can read ahead of time (in the editor, in the
   level, or in `BeginPlay`, which PIE fires *before* `PrepareTest`) is therefore not the
   pair the run grades. A correct answer cannot tell the difference, because a correct
   answer reads the pair off the gate at the moment it needs it, which is the whole ask.
   A hard-coded or BeginPlay-cached one is now wrong on the lamps at phase 3 and on the
   panel at phase 4 instead of surviving to phase 12.

   Deliberately NOT done: a per-leg or seeded permutation. It buys nothing over this (the
   submission cannot see the fixture either way), it would make the two `fps_legs` legs
   grade different scenarios, and it would force the drive table to be rewritten in terms
   of roles rather than crates — untestable from here, and the kind of restructure that
   makes a task unwinnable by accident. Which brings up:

   **The trap this opens, written down because a later implementer will hit it.** Any
   pair the drive requires the gate to OPEN under must include the NEAR-pad crate's name.
   The two far-rail crates contest a single pad and can never be home together, so a pair
   naming both of them is unopenable by layout — a task made unwinnable through no fault
   of the submission. The sequence therefore is: level `(C, A)` → `PrepareTest` `(A, B)`
   → re-cut #1 `(C, A)` → re-cut #2 `(C, B)`. The first three all contain A. **Re-cut #2
   is the one deliberate exception** and is exactly why the gate must come down there
   with nothing moving. I wrote the precondition too broadly on the first pass and it
   would have failed its own staging on re-cut #2; the HARNESS-PRECONDITION list now
   scopes it to the pairs the gate must open under.

1. **The design's re-cut #1 was internally inconsistent, and I fixed it by making it
   stronger.** As written it said re-cut #1 "fires with both gate pads empty", then
   "the character shoves crate B home (gate must stay shut) … and shoves crate C home
   … (gate must open)". With both pads empty and only C home the gate cannot open — the
   first name is not there. The minimal repair is to park A first. I took the repair
   further and made **re-cut #1 swap the ORDER as well as one name**: the pair goes from
   *(A, B)* to *(C, A)*. That costs nothing, fixes the inconsistency, and kills a wrong
   answer the design had no gate for — **identifying the crates positionally** ("near
   pad = first name, far pad = second"), which is a perfectly natural implementation
   given that each rail only reaches one pad. After re-cut #1 the first name is on the
   FAR pad and the second on the NEAR one, so a positional answer lights the wrong lamp
   at every dwell in phases 12-16 while its panel stays right. That is also what makes
   the lamp channel genuinely load-bearing rather than a second opinion on the panel.
   The prompt was amended in the same change to say so in as many words ("He may put a
   different name in either slot, and he may put the same names back in a different
   order", and "Either of the two may be resting on either of the gate's two pads").
2. **The design's `LAST-WRITER-WINS ON THE BARRIER` risk is dissolved rather than
   managed.** The design assumed the pads write the barrier's commanded state, so a
   submission driving the gate directly would fight the pad within a tick, with the
   winner decided by actor tick order — non-deterministic, which would make the task
   INDETERMINATE rather than graded. The shipped shape puts the shared rule on the
   BARRIER (`virtual bool ShouldBeOpen() const`, reading the pads that answer for it)
   and the barrier drives only its own panel. There is exactly one writer per panel,
   always. `SetCommandedOpen` is kept as a per-frame override for a submission that
   wants to decide from somewhere else, and it lapses each tick, so the worst case is a
   one-frame lag (16 ms at 60 Hz, 50 ms at 20 Hz) inside a 1.20 s contract. The barrier
   never asks who called — grading the caller would be route policing.
3. **The map names NO game mode**, so the level inherits `BP_ThirdPersonGameMode` with
   `BP_ThirdPersonPlayerController` (which carries `IMC_Default`) and
   `BP_ThirdPersonCharacter` (mesh + `ABP_Unarmed` + the four `IA_*` actions bound on
   its class defaults). The design's risk item — "the map names its own game mode …
   that game mode MUST re-state `PlayerControllerClass` and the pawn constructor MUST
   load the four `IA_*` actions" — describes the hazard correctly and the shipped
   sibling `t2-alarm-escalates-and-cools-down` already takes the strictly safer route,
   so this task takes it too. **The hazard is dissolved, not ignored**: with no game
   mode named there is no `PlayerControllerClass` to forget and no native pawn subclass
   to leave with four null `UInputAction*`s. The map-authoring step must therefore
   assert that World Settings' `GameModeOverride` is **None**, and the fixture should
   still carry the `HARNESS-PRECONDITION` check that the possessed pawn has a mesh and
   a non-empty Enhanced Input binding list (playbook §7.4 step 3) — that check is what
   tells a harness fault from an agent fault.
4. **No `randomization:` front-matter key.** The design offered one as an optional
   upgrade ("`randomization:` may additionally declare a per-leg permutation … if the
   fixture is later given a `PrepareTest` shuffle; that is an upgrade, not a
   dependency"). I left it out on purpose. The names are staged into the committed
   `.umap`, so they are constant across reps of the same map; a `PrepareTest` shuffle
   seeded from a staged number would still be constant across reps, so declaring
   randomization would claim a property the task does not have. The honest statement —
   which is in `## Hidden invariants` — is that the load-bearing fact varies **within**
   every run, twice, which is what makes a map-baked constant provably wrong for the
   second half of every run.
5. **Twenty phases, not seventeen, and dwells of 3.5 s rather than the design's
   2.5 s.** The extra phases are the split of the far-crate remove/re-add from the
   wrong-crate dwell (so `TheGateShutsWhenACrateLeavesAndOpensWhenItComesBack` and
   `TheGateStaysShutUntilBothItsCratesAreHome` never contend for the same window), and
   the second remove/re-add pair after re-cut #1. The dwell went up because the settle
   suppression is 1.80 s and a 2.5 s dwell would leave only ~1.2 s judged after the
   crate crosses the pad's radius. Modelled cost is ~215 s against the design's
   230-280 s estimate, so the trim the design asked for came out of the phase structure
   rather than out of coverage.

## The numbers, and how they were checked

Arithmetic done by hand before any file was written. Every one of these must be
re-confirmed at implementor-checklist **Gate 10** against an actual reference run — the
band is the design's own top risk and it is right about that.

| Quantity | Value | Why |
|---|---|---|
| Barrier open angle | 90 deg | |
| Barrier travel rate | 180 deg/s | reaches the 80 deg open threshold in **0.444 s** and returns to the 10 deg shut threshold in **0.444 s**, both against a **1.20 s** deadline — a **2.7x** margin in the SAFE direction |
| Disclosed angular cap | 720 deg/s | 4x the supplied 180; unfailable by a correct answer, failable by an answer that teleports the panel |
| Disclosed linear cap | 3000 cm/s | the panel's own origin sits 190 cm from the hinge, so at 180 deg/s it moves **597 cm/s**; the panel's far edge is at 380 cm and moves **1,194 cm/s**. Both well under |
| Pad contact radius | 100 cm | disclosed verbatim in the prompt |
| Pad grounded band | 50 cm | disclosed as prose ("down on the pad's own level rather than up in the air"); can only matter for an airborne body, which the drive never produces. **Widened from 25 during review, in the SAFE direction**: the predicate measures the base of a body's *colliding* bounds, and a character's colliding set includes the skeletal mesh, whose per-pose bounds can sit a little under the capsule's foot while `CharacterMovement` also floats the capsule up to 2.4 cm above the floor. At 25 cm a correct submission could have failed because the OLD DOOR stopped registering a person; at 50 cm nothing changes for a crate (base exactly 0) and a jump still clears it by a factor of four |
| Crate | 120 cm cube, `BlockAll`, movable | |
| Crate-to-crate exclusion | 120 uu of centre separation, clamped in rail coordinates | the crate's own footprint; two centres closer than that would be standing in the same place |
| Rail length / shove speed | 900 uu / 220 uu/s | one full traverse = **4.09 s**; 16 shoves = ~65 s of the drive |
| Crate parking stop | crate centre within 10 uu of the pad centre | **10x margin** inside the 100 uu radius; the other stop is 900 uu away, **9x** outside it. A crate crosses the boundary in one clean pass and is never left grazing it |
| Crossing-to-stop lead | 100/220 = **0.45 s** | the model changes 0.45 s before the crate reaches its stop, so a 3.5 s dwell judges ~2.15 s after the 1.80 s suppression |
| Dwell | 3.5 s | ≥ 1.7 s judged per dwell |
| Modelled drive | ~215 s | 16 shoves (65 s) + ~14 transits (~56 s) + ~13 dwells (~45 s) + 4 old-door cycles (20 s) + suppression and arrival slop |
| Sentinel | 420 s | the anchor `t1-touched-crate-lights-up` already runs on this substrate inside the 600 s per-leg L2 budget |
| `fps_legs` | `[60, 20]` | two PIE processes; the 600 s L2 budget is **per `run_l2` call** and `registry.py`'s dt-leg loop makes one call per leg, so the legs do not share it |

## Design decisions worth writing down

**Why the shared rule lives on the BARRIER and not on the pad.** Both placements give
the same brownfield trap, but only one is deterministic. If the pad writes the
barrier's state, a submission that also writes it fights the pad within a tick and the
winner is decided by actor tick order. With the rule on the barrier there is exactly
one writer per panel, always, and the two wrong answers are still both one line:
narrowing `AYardPadActor::IsBodyResting` to crates (W2, kills the old door) or turning
`ShouldBeOpen`'s ANY into an ALL (W1, keeps the old door, loses the gate).

**Why the pads are painted mats flush with the floor rather than raised plates.** A
raised plate makes "resting on it" mean two different things for a character (which
steps up onto it) and a crate (which would have to climb it). Flush mats make the
predicate identical for both bodies, which is what the prompt promises, and they let
the crate slide at constant height with no step logic at all. The disclosed predicate
then has exactly one form: the middle of the body's colliding bounds within 100 cm
flat, base within a band of the mat's level.

**Why the resting predicate is measured off `GetActorBounds(bOnlyCollidingComponents=true)`.**
Every actor in the yard carries floating text — a crate's name, a barrier's angle, a
lamp's slot — and all of it is `NoCollision`. Measuring off the full bounds would put a
crate's "base" at the top of its name plate. Measuring off the ROOT component's bounds
would also work for the crate and the character but breaks the moment a root is a bare
`USceneComponent` (which the crate's is). Colliding-bounds-only is the one form that is
correct for both bodies and stays correct if a submission adds a decoration.

**Why the fixture re-implements the predicate instead of calling the pad's.**
`AYardPadActor::IsBodyResting` is in the agent's writable module. A submission that
widened it — the natural sloppy fix for "my crate isn't registering" — would move the
fixture's model with it and make the grade agree with the bug. The fixture reads the
pad's `ContactRadiusUu` and `GroundedBandUu` **live** (so a re-staged yard moves the
drive with it) but applies them itself, and `TheYardIsNotYoursToRewire` pins both, so
the two can only disagree if a submission changed a number the prompt tells it not to.

**Why the shove reads the pusher's INPUT and not its velocity.** This was a real bug in
the first cut and it would have deadlocked the whole drive. A `BlockAll` crate brings
the pusher's velocity to nothing at the instant of contact, so a
"velocity along the rail > 40 uu/s" test stops the crate, which un-blocks the pusher,
which re-starts the crate — or, more likely, never starts it at all. The shipped test
reads `APawn::GetLastMovementInputVector()` — what the body is *asking* to do — with
`GetVelocity()` only as a fallback for a pawn that moves without asking. This is also
what keeps the human lane and the fixture lane identical: `AThirdPersonCharacter::DoMove`
and the fixture's scripted timeline both go through `AddMovementInput`, which is the
sole source of that vector.

**Why the contested-pad exclusion is explicit geometry and not a swept move.** The
design's exclusion ("two rails feed the far pad from opposite sides, so only one crate
at a time can be parked there") is load-bearing — it is what makes the identity axis
something a human plays rather than something a fixture teleports. The first cut of the
crate relied on `SetActorLocation(..., bSweep=true)` for it and **that could never have
worked**: the crate's root is a bare `USceneComponent` (deliberately, so the actor's
own position sits on the floor and every relative number in the constructor is in world
units), and `USceneComponent::MoveComponentImpl` ignores sweeping entirely — only a
primitive root sweeps. One crate would have tunnelled straight through the other and
both would have read "home" at once, while `task.md`, the scaffold comment and this file
all said otherwise. Caught by reading the claim against the code rather than by a run;
it is the same class of defect as the SightYard spec claiming four things its code never
did.

The shipped version clamps in the crate's own rail coordinate: any other crate whose
centre is within one footprint (120 uu) of this rail's line and ahead of this crate in
the direction of travel limits how far it may run, to one footprint short of that
crate's projection, and never backwards. That is deterministic, needs no collision
query, and states exactly the disclosed behaviour. Re-rooting the crate on its box
would also have worked and was rejected: a primitive root puts the actor's origin at the
box's centre, which forces the map-authoring step to place every crate at `Z = 60` and
turns a mis-staged height into a half-buried crate instead of a visible one.

**Why the barrier squares its hinge before recording what "shut" means.** `ShutPanelYaw`
is captured at `BeginPlay`. If the level were ever saved with a non-zero hinge rotation
and the capture happened first, `SweptAngleDeg` (which starts at 0) would snap the panel
on the first tick and the barrier would then read as permanently part-open — which would
fail `TheDoorNobodyTouchesNeverMoves` on the twin door for a reason no submission caused.
Squaring first makes "shut" mean hinge-relative-yaw-zero, whatever the map holds.

**Why the barrier carries no "is open" property.** If it did, a submission could set it
and be graded on it. The panel's pose and the lamps' lights ARE the readout, so nothing
private is ever graded and there is no ungraded switch to throw instead of doing the
work. Same reason the alarm task's panel carries no stage.

**Why the twin door is a matched instance rather than an unrelated actor.** The negative
control has to be able to fail. A twin barrier with a twin pad, identical in every
staged number, 3,000 cm from anything the drive touches, fails for exactly one class of
answer — one that binds the new rule to the barrier CLASS instead of to the barrier that
is cut for names — and that is a real answer, not a strawman: iterating every barrier in
the level from one aggregator is how a first pass usually finds the gate.

## Honest counter-arguments

**The tier.** By reference volume this is a T2: two files, 117 added lines of which 54
are code (`diff -u` against the scaffold, comment and blank lines excluded), one branch
and one loop. `tier: T3` was pre-assigned, the corpus row is a T3, and the watch-list
reshape is a T3 — and the label is defensible on coupling rather than volume (two
subsystems sharing a class and a question and wanting opposite answers, with a named
gate on each side, plus a load-bearing fact that is re-staged twice mid-run). But the
`## Reference solution metadata` section says **5–8 hours**, which is the T3 *floor*,
and says so out loud. **If the owner would rather this were T2, the only edit needed is
the front-matter `tier:` value** — nothing else in the task depends on it. Flagged
rather than quietly asserted.

**The preservation gate is free for the empty submission.** Stated in the design and
kept, not papered over. `TheOldDoorStillOpensInsideItsBand`, `TheDoorNobodyTouchesNeverMoves`
and `TheYardIsNotYoursToRewire` all pass for a no-op. That does not make them dead
gates — two plausible real submissions fail the first (anti-gaming note 2 and note 9),
and the empty submission still dies at phase 3 on `TheGateStaysShutUntilBothItsCratesAreHome`.
The empty leg dies on a **wrong-open**, which is stronger than the corpus's own
never-open leg, because an always-shut stub cannot pass it either (phases 4, 6, 8, 14
and 16 all require the gate to be open).

**`TheGateAnswersToWhatItIsCutForRightNow` is softer against the overlap-edge answer
than the design claims.** The design says an implementation "recomputing only inside
overlap begin/end handlers … is both idiomatic and cheaper than a tick". True in
general, but the shipped scaffold already evaluates `ShouldBeOpen()` per tick, so an
agent has to go out of their way to become edge-driven. The gate still catches the real
version of this failure (a submission that adds its own overlap handlers on the crates
and caches the result), and it catches the BeginPlay-cache answer squarely at re-cut #1.
I did not weaken the scaffold to manufacture the edge-driven failure, because that would
be hiding the seam rather than testing the coupling.

**The old door's band is a proposal until Gate 10.** 1.20 s / 80 deg / 10 deg /
720 deg/s / 3000 cm/s are the design's numbers. What I can assert is that they are
**self-consistent with the supplied travel by construction** (2.7x margin, computed
above) rather than copied out of the CSV's tolerance column. They still have to be
re-derived from a real reference run and, if they move, the prompt's five literals move
in the same change.

## The 2026-08-19 adversarial review, and what it changed

Two reviewers attacked the task independently and filed 13 findings (3 blockers, 5
major, 5 minor). Below is every one, whether it held, and what was done. Nothing here
has been built or run — the same caveat as the rest of this file.

### The findings that held, and the fixes

**1. `too-easy`, blocker — "the prompt kills both declared wrong answers itself."**
REAL, and the most important finding on the list. The agent-visible prompt carried one
defensive sentence per anti-gaming note, in roughly the order the fixture checks them:
*a person standing on one of the gate's pads is not a crate and never counts toward
anything*; *the shared any-body pad rule IS what makes the old door work*; *what is
being asked about is the names, not which pad a crate is standing on*; *whatever is
written on the gate at the moment you need to know is the answer*; and *today, one crate
shoved onto either of the new gate's pads is already enough to swing the gate open*.
Every trap the fixture was built to catch was announced in the prompt that preceded it,
so the straightforward transcription of the literal prompt passed all ten named gates.

*Fix, and the principle behind it.* State the contract **once, completely, in positive
form** — "a gate must be open exactly while a crate carrying the first of its two names
and a crate carrying the second of its two names are both resting on its pads, and shut
the rest of the time" — and **do not enumerate the wrong answers**. Every value those
deleted sentences carried is still entailed by that contract plus the disclosed
present-day rule, so Hard Rule 7 (every gate's value in the prompt) still holds and no
gate became undisclosed. What is gone is the pre-mortem. Concretely deleted: the
person-is-not-a-crate clause (entailed by "exactly while … a crate carrying"), the
"zero crates / either name alone / a crate it is not cut for is not enough"
enumeration (entailed by "and shut the rest of the time"), the "it is the names, not
which pad" gloss, the "read it at the moment you need to know" imperative (replaced by
the world fact it was defending: the foreman re-cuts *including when nothing else in
the yard is moving*), and the "today one crate is already enough" spoiler (derivable
from two facts the prompt still states).

**2. `too-easy`, blocker — "the scaffold hands over the solution's shape."** REAL, and
cheap to fix. Removed from `YardBarrierActor.h`/`.cpp`:
- `bool IsCutForNames() const` — the *exact* predicate that separates a gate from a
  door, i.e. the one genuinely brownfield decision in the task, pre-solved and named.
  `UpdateReadouts` now inlines the equivalent check so nothing depends on it. The
  reference declares its own copy, as a submission is entitled to.
- the "**That is the work**" three-item to-do list (`nothing here has heard of a crate's
  name / nothing throws a lamp's switch / nothing treats one barrier differently`).
- "so **read them at the moment you need them**" — the entire defence of anti-gaming
  notes 3 and 4, handed over as an imperative before the agent wrote a line.
- the `Lamps.Sort` by `NameSlot` in `BeginPlay`, and the `GetMyLamps()` comment that
  promised slot order. A submission that wants slot order now has to notice it needs it.
What was KEPT is the fairness disclosure the reviewer did not object to: *the yard is
fixed, so whatever decides has to live on a class the level already instantiates.*
Without it an agent can write a new class that is never placed and fail for a reason
that is not about the task.

**3. `too-easy`, major — "condition (a) is only nominal: subsystem A requires zero
work."** REAL as stated, and the fix is the biggest change in this pass. The reviewer is
right that the correct diff is purely additive and that "getting the old door right"
costs restraint rather than typing; that is what preservation IS, and the honest answer
is not to invent work for the old door. The answer is to put a named gate on the side
the agent DOES type. **The yard now holds a SECOND GATE.**

Its two pads are painted over the arch gate's two pads — same centres to within 2 uu,
same radius, same band, 3 cm proud so the mats do not z-fight — so both gates see
exactly the same three crates at exactly the same instants, and **nothing about the
layout can tell them apart: only the pair of names written on each can.** They are cut
for different pairs and re-cut on different schedules, traced so they disagree at four
dwells:

| Phase | What is home | Arch gate | Second gate |
|---|---|---|---|
| 3 | near crate | shut, slot-0 lamp lit | shut, **slot-1** lamp lit |
| 4 | near + east | **open** | shut |
| 5 | near + west | shut | **open** |
| 13 | near | shut, **slot-1** lamp lit | shut, **slot-0** lamp lit |
| 14 | near + west | **open** | shut |
| 17 | near + west, **nothing moving** | must come **DOWN** | must come **UP** |

Three things make this the right shape rather than a bolt-on:
- **The reference did not change by one line.** An answer written per instance, from
  the instance's own data, is already right for N gates. Only an answer that decided
  there was one gate has to be rewritten. That is the definition of coupling rather
  than riddle.
- **It costs the drive nothing.** No step, no dwell, no walking — it is judged passively
  on frames the drive already produced, exactly like the twin door. Given that the
  run's wall-clock was the top risk on this task (finding 8), discrimination that cost
  seconds would have been cut later.
- **It creates a genuinely likely wrong answer** (anti-gaming note 10): locate the gate
  once — a `TActorIterator` for the barrier that carries names, the one that owns the
  lamps, the first found, a `BeginPlay` pointer — and drive it. Correct for the arch
  gate, passes phases 0-4 outright, and named at phase 3 on the lamps and phase 5 on
  the panel. Plus note 11, the tidy version: one computed "which crates are home"
  shared by both gates with the four lamps indexed globally.
It is disclosed, in the prompt, in plain words: there are two gates, each cut for its
own pair, neither pair says anything about the other's, and their pads are painted on
the same two patches of floor. It is not a hidden second subject.

**6. `empty-passes`, minor — "the in-scene control is matched to the subsystem that
requires no work."** REAL, and the second gate is exactly the fix the reviewer asked
for. There are now two controls, one per side of the coupling: the quiet door (never
approached, reachable only by an answer that generalises to the whole class) and the
second gate (reachable by the ordinary answer that solves the task for one gate).

**8. `compile-risk`, major — "420 s sentinel against a drive that is 340-400 s."** REAL,
and it would have graded a correct reference as an Error. The step table really does
build 27 walking steps and 27 dwells, not the "~14 transits, 13 dwells" the old
`MATRIX.md` claimed. `kSentinelS` 420 → **900**, `kCalibCount` 52 → **110**. The
sentinel is WORLD time under a fixed timestep, so a passing leg never reaches it and the
headroom is free; the cost of being generous is zero and the cost of being tight was a
false FAIL. **It must be re-tightened to ~1.5x the MEASURED completion time once the
orchestrator has one** — the number is in the log line `[t3-olddooryard] run complete
at t=`.

**9. `undisclosed-gate`, major — "the HARNESS-PRECONDITION claim is unimplemented."**
**PARTLY REAL, and the reviewer's grep was right about the wrong thing.** The PREFIX
does nothing: `grep -rn "HARNESS-PRECONDITION" tools/ --include=*.py` returns only
`tests/test_verdict_taxonomy.py`, exactly as filed. But the ROUTE exists and keys on the
result enum, not the string — `layers/l2_pie.py::_harness_precondition` matches the
engine's own `FinishTest TestResult=Error.` emission and `run_task.py` predicate (4c)
routes it to **exit 7 HARNESS-ERROR**, out of the graded denominator, when
`tests_run == 0`. Every staging exit in this fixture is a terminal
`FinishTest(EFunctionalTestResult::Error, …)` with no graded result banked first, so it
does apply. So the sentence was not fabricated — it named the wrong mechanism.
*Fix*: `task.md` now describes the actual route, names the two files, and states the
invariant that route depends on (the internal design note (not shipped): an `::Error` whose
guard reads an agent-writable input is a denominator opt-out). **The orchestrator must
add this fixture's `::Error` sites to that audit.** The residual risk — a submission
that stalls the drive while leaving the three preservation gates intact — is bounded by
`PreservationStillHolds` and, now, by a sentinel that is far past the drive rather than
inside its error bars.

**10. `empty-passes`, minor — "the 1.80 s settle suppression does not exist."** REAL.
`kSettleS` and `LastModelChangeAt` were computed every frame and never read;
`Suppressed()` tested only `StagingUntil` and `Phase == 0`. Wired in. It is a widening,
and `kDwellS = 3.5` was already sized for it (1.7 s of every dwell still gets judged),
so no gate loses reach.

**11. `undisclosed-gate`, minor — "the requirements table mis-scopes the preservation
gate."** REAL, and the honest fix is to correct the table, not the gate.
`GateOldDoorBand` is called on every non-suppressed frame, before the armed switch; it
is armed for the whole run, not for four phases. The table now says so, and explains why
the four phases are still the only place it can *distinguish* anything.

**12. `unplayable`, minor — "author_map.py's mirror does not mirror."** REAL and
embarrassing, because the block's own comment claims the mirror is what makes clearance
"MEASURED here rather than discovered at run time". `LANE_CLEAR_UU` 420 → **380**
(= `kLaneClearUu`), so the script now validates the lanes the drive actually walks
(`x=380` / `x=-1180`, confirmed by the dry-run). The fixture's rail-separation
precondition (`|NearRailX - FarRailX| >= 2 * kLaneClearUu`) was missing entirely and is
now mirrored — the shipped layout clears it by 40 uu, so it was one edit away from
authoring a map that dies in every L2 run.

**13. `too-easy`, minor — "TheRunnerIsNotACrate is the one panel gate with no band."**
REAL, with one correction to the reviewer's arithmetic. The prompt's 1.20 s is a
deadline on the OUTCOME (decision plus travel), not 1.20 s of decision latency on top of
travel, so the reviewer's 1.644 s figure overstates it. The gate was still wrong: it
compared the panel angle RAW against a window measured from the CHARACTER'S ARRIVAL,
making it the only panel gate with no reference to the barrier's own model clock and
none of the 0.20 s frame-ordering grace `BandVerdict` gives every other. It survived
only because the step table always precedes it with a 3.5 s dwell — correct by accident
of staging. Routed through `BandVerdict` like every other panel gate, and `kRunnerArmS`
raised 1.50 → **2.00** (above `kBandS + kBandGraceS`) as a floor, leaving 1.5 s of each
3.5 s dwell judged.

### The findings that did NOT hold, or held only partly

**4. `too-easy`, major — "condition (c) is structurally defused; the re-cuts
discriminate nothing."** PARTLY. Correct for the PANEL: the scaffold already evaluates
`ShouldBeOpen()` per frame as a `const`, so a cache is not expressible where the agent
is invited to write, and re-cut #0's whole job — making a hard-coded pair wrong from
frame one — is passed for free by any implementation that lands there. Not correct for
the LAMPS, which do not exist in the scaffold at all: the agent writes that loop from
nothing, an event-driven lamp is entirely plausible, and re-cut #2 catches it with
nothing moving. What the finding did establish is that the re-cuts were carrying less
than the design claimed, and the second gate is the answer: re-cut #2 now moves two
barriers in opposite directions on the same frames, which no shared or cached answer
can produce. The scaffold's per-frame seam was NOT removed — handing the agent an
edge-driven seam to manufacture a stateful wrong answer would be hiding the seam rather
than testing the coupling, and it would break the supplied behaviour the preservation
gate measures.

**5. `empty-passes`, major — "the re-trigger convention re-tests nothing."** SAME ROOT
CAUSE, same answer, and the convention is mandatory regardless (authoring hard rule 11).
The re-triggers stay. What changed is that the second gate now rises twice on its own
account, at phase 5 and at phase 17, and the second of those is the re-cut where nothing
moves — so the run-level gate has a re-trigger clause that no per-frame implementation
gets for free.

**7. `unplayable`, blocker — "the committed map does not exist."** REAL, confirmed on
disk, and **NOT FIXABLE FROM HERE**: authoring the map means running the editor, which
this pass is forbidden to do. The reviewer's own note is right that the other four
tasks in the batch are in the same state. What this pass did instead: fixed the two
real defects in `author_map.py` (finding 12), added the second gate and its actors to
it, added the "the two gates must actually disagree" trace, and **dry-ran `solve_yard()`
against a stub `unreal` module** so the geometry is proven before an editor ever opens.
`cb lint` still errors on `map-binary-exists` and will until the binary is committed.

## Hazards hit while authoring

1. **A `BlockAll` crate deadlocks a velocity-based shove test.** See above. This one
   would have looked like "the drive hangs at phase 3" and cost a full L2 leg to
   diagnose.
2. **`ConstructorHelpers::FObjectFinder` cannot run outside a UObject constructor.**
   The first cut of `AGateLampActor::SetLit` resolved the lit/dark materials lazily with
   a `static FObjectFinderOptional` inside the function — which asserts in
   `CheckIfIsInConstructor` the first time the lamp is thrown. Both materials are now
   `UPROPERTY` members resolved in the constructor.
3. **A `UFUNCTION` returning `const TArray<T*>&` is not reliably accepted by UHT.**
   `GetPadsAnsweringForMe()` and `GetMyLamps()` are plain C++ accessors, not
   `UFUNCTION`s. The whole deliverable is C++, so nothing is lost.
4. **A child component inherits the root's scale**, which multiplies both its relative
   offset and its collision extent. Every actor here roots on an **unscaled**
   `USceneComponent` (`Mount`/`Frame`) with meshes scaled individually, so every
   relative number in the constructors is in world units and a `UBoxComponent`'s extent
   means what it says.
5. **A static parent pins every child.** The lamp's bulb swells, the pad's marker rides
   up, the crate slides and the panel swings — all four roots are explicitly
   `EComponentMobility::Movable` in the constructor, because a level-placed actor can be
   saved Static and a static parent silently freezes everything under it.
6. **The barrier's readouts were originally attached to the hinge**, so swinging the
   panel would have swung the floating degree number out of frame. `Hinge` now carries
   the panel and nothing else; both text components hang off the non-moving `Frame`.
7. **`AYardLampActor` already exists** in this substrate (`t2-alarm-escalates-and-cools-down`).
   UE class names are global, so this task's lamp is `AGateLampActor`. All four class
   names were checked against every `THIRDPERSON_API A*` in the module.
8. **A `bSweep=true` move on a bare-`USceneComponent` root sweeps nothing.** The whole
   story is under *Why the contested-pad exclusion is explicit geometry* above. What
   makes it worth a hazard entry rather than a design note: the false claim was written
   into three places at once (the prompt-visible workspace description, the scaffold
   comment and this file's own rationale), and every one of them read as evidence for
   the other two. A physical claim in agent-visible prose has to be traced to the line
   that enforces it, every time.
9. **Pad occupancy no longer depends on overlap bookkeeping.** The first cut answered
   *who is resting on me* by walking `PadVolume->GetOverlappingActors()` and filtering.
   That is one silent-failure mode away from disaster: an overlap pair is only tracked
   when **both** components generate overlap events, so a single `SetGenerateOverlapEvents(false)`
   anywhere — or a profile pairing that resolves to Ignore — would make every pad in the
   yard report empty. The old door would then never open **for the reference as well as
   for the empty submission**, i.e. the failure would look like a task-wide false FAIL
   with a green build. It now measures the two kinds of body that exist in this yard
   directly (`TActorIterator<APawn>` + `TActorIterator<AYardCrateActor>`), which cannot
   be one frame stale either. `PadVolume` stays, and stays honest: it notices what comes
   and goes for anybody who wants to bind to it — which is exactly the overlap-edge
   design that re-cut #2 kills — but nothing in the yard's own rule depends on it.
10. **`cameras.json` belongs to the TASK folder, not the map folder.** The first cut
   pointed at `cameras.json`, copying the shipped
   `t2-alarm-escalates-and-cools-down` spec, which has the same error. Every one of the
   24 committed camera plans lives at `cameras.json`
   (`git ls-files | grep cameras.json`); `t2-bridge-only-holds-what-it-can-bear` states
   it correctly. Cited a sibling instead of `git ls-files`, and the sibling was wrong.
11. **`L_OldDoorYard` is verified unused today** — zero hits under `git ls-files`, and it
   collides with none of the 41 committed map basenames. Re-verify at build time:
   `map_locator.py` globs both `Content/Maps/<map>.umap` and `Content/Maps/*/<map>.umap`
   and raises `DuplicateMapBasenameError` as **exit 7 HARNESS-ERROR**, and `cb lint`
   cannot catch it (`tasklint._check_map` returns clean once *any* tracked copy exists).
12. **The grader leaked into the agent-visible workspace section, in the house style.**
   Running the real extractor rather than eyeballing the file turned up two hits inside
   `## Workspace state pre-task`, which the agent DOES see: the empty submission was
   described as failing "at the first single-crate dwell" (fixture jargon naming a piece
   of the drive) and the harness row read "verifier-owned". Both are now neutral — "the
   first time a crate is shoved onto one of the gate's pads", which is a fact the prompt
   already discloses, and "lives in a module the agent can neither read nor modify",
   which is the phrasing `TASK-AUTHOR-GUIDE.md` §A asks for. **Three shipped siblings
   carry the same `FAILs L2 …` sentence and `t2-alarm-escalates-and-cools-down` goes
   further and names its fixture class, `AAlarmEscalationFunctionalTest`, in
   agent-visible prose.** Not fixed here — another task's folder is out of scope — but it
   is a real, cheap, set-wide cleanup and somebody should take it.

The three artifacts outside this change-set, with the contracts they have to meet.

**1. `Source/CraftBenchTests/Tasks/<id>/OldDoorYardFunctionalTest.{h,cpp}`.** Derives
`ACraftBenchFunctionalTest`. Resolves subjects **by tag** (`YardBarrier`, `YardPad`,
`YardCrate`, `GateLamp`) and the pawn by `UGameplayStatics::GetPlayerPawn(World, 0)`;
never by class. Drives through `AddMovementInput` only. The full gate list, precedence
order, drive table, suppression rules and `HARNESS-PRECONDITION` list are in
`## Verifier specification`. Five things it must get right that are easy to miss:

- **`PrepareTest` writes the gate's pair (re-cut #0) before anything else.** The level
  is saved holding a different pair on purpose; if the fixture trusts the level instead,
  the whole of change 0 above evaporates silently and a hard-coded answer survives to
  phase 12 again. Assert afterwards that the pair it wrote is two distinct crate names
  and that it contains the near-pad crate's name;
- it must **re-implement** the resting predicate rather than call `AYardPadActor`'s;
- `TheYardIsNotYoursToRewire` must compare the two names against **what the fixture
  itself last wrote**, never against what the level holds, and must suspend that clause
  **only** inside the re-cut windows;
- every deadline/sentinel overrun path must re-check `TheOldDoorStillOpensInsideItsBand`,
  `TheDoorNobodyTouchesNeverMoves` and `TheYardIsNotYoursToRewire` **unconditionally**
  before attributing anything to staging — a submission that jams the gate's panel
  across the walking lane can stop phases completing, and that must be a FAIL.
- every `FinishTest(Failed, …)` message must be **ASCII** (the UE log's UTF-8 is read
  back as cp1252, so an em dash breaks the MATRIX substring match) and must contain its
  gate's name verbatim. The empty leg's expected substring is
  `TheGateStaysShutUntilBothItsCratesAreHome`. `tasklint`'s `fixture-fail-unique` rule
  also compares every `TEXT("…")` literal of 6+ characters across the file's
  `FinishTest(EFunctionalTestResult::Failed, …)` calls and WARNs when two gates share
  one — with ten gates in this fixture, no two messages may share a stock phrase
  ("never did", "out of band"), or the matrix cannot say which gate fired. The gate
  name at the head of each message is necessary but not sufficient for that rule.

**2. `authoring/author_map.py` → `Content/Maps/<id>/L_OldDoorYard.umap`.** Real RHI, never
`-nullrhi`; built from `Template_Default`. World Settings `GameModeOverride` = **None**.
It must stage, and then ASSERT it staged:

- three `AYardBarrierActor`s: `OldDoor` (north, pair empty), `QuietDoor` (3,000 cm east,
  every staged number identical to `OldDoor`, pair empty), `ArchGate` (west, pair set);
- four `AYardPadActor`s with `AnsweredBarrier` set — one for `OldDoor` 300 cm in front,
  one identical for `QuietDoor`, two for `ArchGate` (near, and far 800 cm from it);
- three `AYardCrateActor`s with distinct `CrateName`s, each placed at its **away** stop
  and rotated so its forward axis points at its pad; the near-pad rail feeds the near
  pad, and the two far-pad rails approach the far pad from **opposite** sides (axis dot
  product < -0.8). Each parking stop must land the crate centre within 10 uu of the pad
  centre;
- two `AGateLampActor`s on the gate's frame with `NameSlot` 0 and 1 and `LampBarrier`
  set;
- the pair the LEVEL is saved holding = `(C, A)` — **deliberately NOT the pair the run
  grades**, which the fixture writes in `PrepareTest` (re-cut #0, change 0 above). It
  must still be a pair a human can open the gate with, i.e. it must contain the near-pad
  crate A. **No name may be alphabetically ordered in slot order, and none may order with
  the layout** — otherwise an alphabetical or positional answer passes a re-cut by luck.
  The staging this task assumes throughout: `Marrow` (near rail), `Cinder` (far, east
  rail), `Bramble` (far, west rail); **level** `(Bramble, Marrow)`; `PrepareTest`
  `(Marrow, Cinder)`; re-cut #1 `(Bramble, Marrow)`; re-cut #2 `(Bramble, Cinder)`. Note
  that the level's pair and re-cut #1's are the same pair, which is a free bonus: an
  agent that hard-codes what it read in the editor is wrong for phases 3-10 and *right*
  for 12-16, so its failure is not a flat "always wrong" that could be mistaken for a
  build fault;
- a 9,000 x 9,000 striped floor with **non-colliding** stripes, a PlayerStart on it
  facing the old door, and a backdrop with two differently sized landmarks;
- everything except the floor, the crates and the barriers' panels/posts authored
  `NoCollision` on **both** the profile and the enum (a `set_collision_enabled` alone did
  not survive into a saved level on an earlier task in this set).

Then add its row to `docs/MAPS.md`, and `git add` the binary — `tasklint`'s
`map-binary-exists` fires on an untracked `.umap` and the graded tree is cloned from git
HEAD.

**3. `cameras.json`** (the task folder — where all 24
committed camera plans live, not the map folder) — one wide pose over the gate, its two pads and the three rails,
with the old door in frame at the top of the shot; the twin door does not need a camera.
Presentation only, non-gating.

**4. `discrimination/MATRIX.md`.** Reference + empty only — the owner's 2026-08-18
directive forbids authoring variant legs, so there is no `discrimination/<variant>/`
tree to build. Two `tasklint` rules apply to the file itself, both learned by linting
the shipped siblings rather than from any doc: it must carry a literal
**`## Requirements table`** heading (`matrix-requirements-table`, mandatory since
2026-08-11; `t3-keyring-opens-what-it-was-cut-for` still WARNs for the lack of one), and
each row must name **exactly one** backticked literal (`matrix-row-single-literal` —
`grade_leg` matches ALL of them, so a two-literal row is uncreditable unless both are
logged verbatim). The empty row's single literal is
`TheGateStaysShutUntilBothItsCratesAreHome`.

## Still to do

- **Prove the empty leg, not just the reference.** `cb discriminate
  cpp/t3-gate-and-door-cpp` must report reference
  **PASS** and empty **FAIL** with the empty leg's failure naming
  `TheGateStaysShutUntilBothItsCratesAreHome`. Per `TASK-AUTHOR-GUIDE.md` §B a green
  reference alone is not acceptance — `gp-gas-launch` once shipped a "stub" that was the
  filled solution and an empty submission PASSed for weeks. Then, and only on a clean
  tree, `cb refgate` once for the certificate (a dirty tree makes the gate a full
  re-grade that caches nothing — owner, 2026-08-17).
- **Verify re-cut #0 actually re-cuts, for BOTH gates.** The cheapest possible mistake
  in the fixture is for `PrepareTest` to read a level pair instead of writing its own;
  nothing fails if it does, the task just quietly gets easier. `PrepareTest` now asserts
  this for each gate independently (level pair must be openable by hand, must differ
  from the graded pair, and the two gates must not share a pair) — confirm the staging
  log line shows four distinct pairs.
- **Add this fixture's `::Error` sites to the internal design note (not shipped).** The
  non-graded route for staging faults depends on that audit's invariant, and this
  fixture adds several `::Error` guards whose inputs the drive (and therefore, at one
  remove, a submission) can influence.
- **Gate 10 calibration.** Re-derive the five band literals from an actual reference run
  and update the prompt in the same change if they move. The margin must stay in the
  SAFE direction; "the drive manufactures FAILs" is a logged four-instance failure mode.
- **THE MAP.** `authoring/author_map.py` has never been run. Run it in a real-RHI
  editor (`UnrealEditor-Cmd <ThirdPerson.uproject> -run=pythonscript -script=<abs path>
  -unattended -nopause -log -stdout -FullStdOutLogOutput`), commit
  `Content/Maps/L_OldDoorYard.umap`, and
  re-run `cb lint`. Nothing below can be attempted before this.
- **Wall clock, and then re-tighten the sentinel.** Measure the drive on both legs and
  read `[t3-olddooryard] run complete at t=`. The prediction is 340-400 s of world time
  against a 900 s sentinel; confirm the 60 FPS leg still fits the 600 s per-leg WALL
  budget, then the 20 FPS leg, then bring the sentinel down to ~1.5x the larger measured
  number. This is still the top risk in the change-set — the previous prediction was
  wrong by about 2x in the dangerous direction.
- **Confirm the two gates really do disagree in the running world.** `author_map.py`
  proves it for the pairs it saves and the fixture proves it for the pairs it writes,
  but the trace from crate positions to two panel poses has never been executed. The
  calibration log carries both: `arch=…(…) cut=(…,…) side=…(…) cut=(…,…)` on every
  checkpoint.
- **Play it.** Owner directive 2026-08-18: a task is not done until the owner has played
  the reference. Walk the yard by hand, shove all three crates, and watch the old door
  before calling this finished.
- **The empirical half of the difficulty bar. This task has never met a model.** Run
  `cb eval --model claude-p:<cheap model>` once. Passing first try with zero iteration
  means the bar was not met and the task needs another axis.
