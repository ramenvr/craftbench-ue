# t3-your-last-life-ends-the-run — authoring notes

Authored 2026-08-19 against the owner's 2026-08-18 difficulty bar. Spec, scaffold,
reference, the L2 fixture and `cameras.json` (the camera-plan lane; not part of this release) are in; the committed `.umap` and
`discrimination/MATRIX.md` are not (see **Left to do**). Written in two passes on
the same day — the second pass audited the first pass's fixture against the
reference and found four defects, all recorded below under **Second pass**.

## Provenance

**Corpus rows merged:** `t2-lives-system` (review row 199) and
`t2-win-lose-state-machine` (review row 208), both marked `ALREADY STRONG` in
`hardened-tasks.csv`, both `Fixed N = 6`, both with `Runtime binding = UNBOUND`
and `Manifest status = NOT CREATED` — i.e. designs, never built, never run. Their
numbers were proposals.

**Where the discrimination triple came from.** `verification-contracts.csv` has
**no row for either id** (checked by exact-id scan and by substring — the file's
nearest neighbours are `t2-collect-unlock-portal-win` and
`t1-constraint-limit-caps-swing`). So the named assertions / empty-submission
failure / gamed variants used here come from the approved design brief and from
`check-contracts.csv`'s six-per-row check IDs, not from the contracts file. Worth
recording, because the contracts file is normally the highest-value source and it
is silent on both parents.

**What the adoption review said that bears on these two rows.**
`ADOPTION-REVIEW-2026-08-16.md` §5.1(4) names `t2-lives-system` **by id** as a
**dead-gate** offender: *"what does an empty delivery get free? … `t2-lives-system`
3/6"*. Half of its rubric was satisfiable by doing nothing (`LivesStartAtDeclared`
is free if lives are a defaulted property, `GameOverFalseWhileLivesRemain` is free
if nothing ever sets it, `LivesStableBetweenDeaths` is free if nothing ever writes
it). That defect is the single biggest thing this task had to fix, and it is
fixed structurally rather than by re-wording: **there is no lives property and no
game-over flag on any supplied class**, the only readouts are a lamp row that
starts dark and a word that starts on a placeholder, and exactly one gate
(`TheRunIsNotYoursToRewire`, anti-tamper) is free to an empty delivery — which the
spec declares in as many words must be excluded from any k/N.

Neither parent is on the §9 kill list, and neither is on the §10 watch list.

## What was changed carrying the corpus over, and why

| Corpus | Here | Why |
|---|---|---|
| ids name the mechanism (`lives-system`, `win-lose-state-machine`) | `t3-your-last-life-ends-the-run` | §5.1(1). The id leaks through `Content/Tasks/<id>/`; it now names the outcome and says nothing about how. |
| missions name *kill volume*, *Widget Blueprint*, *terminal state machine*, *Game Over state* | runners, crumbling ground, a finish disc, lamps and a word | Hard Rule #1 / §5.1(2). |
| trigger is a kill volume the fixture drops you into | **walk into** a patch of crumbling ground, and **walk onto** the finish disc | §7.1.3 Tier 1: a human does it with WASD and the fixture drives the identical path with the shipping `AddMovementInput` timeline. No key press anywhere, so nothing is blocked on the input lane. |
| two saved Widget Blueprint assets + viewport-membership probes (`t2-win-lose-state-machine` checks 4-6, one of them L2I) | one **in-world word** floating over each runner, graded as the first run of letters | §7.1.2 visible-readout convention, and it keeps the task on `[L1, L2]`. The widget-identity half was the weakest part of the parent anyway: it graded *which asset exists*, not *what the run did*. Nothing is lost that this task's gates do not already own — routing is now "the right runner shows the right word", per runner. |
| one player, one life count, temporal before/after control | **three runners**, one of which is never touched and is gauged at every checkpoint | §5.1(5) / DEF-6. The in-scene twin replaces a whole serial grade leg AND is the only thing that catches the tutorial answer (one counter for the level). |
| "the declared initial-lives value" owned by the fixture | a number **painted on each runner's own marker**, staged per framerate leg and re-painted twice mid-run | The difficulty bar's clause (c): the load-bearing fact is read from the world and varies per run, so a hard-coded life count is wrong on at least two of the three runners at the first judged frame. |
| `RemainingLivesRespawnPlayer` — "respawns at the declared point" | back on **its own** marker within 1 s, then let go of | The parent's "declared point" was a fixture-owned literal (DEF-4). Here the point is a disc in the level, and *whose* disc it is is disclosed in the prompt. |
| `ZeroLivesTriggersGameOver` + `DeathTriggersGameOver` + `TerminalStateExclusive` as three points | `TheLastLifeEndsTheRun` + `ARunThatEndedNeverChangesAgain` | DEF-5 restatement-pair rule: the three corpus checks restate one fact three ways. Folded into two gates that assert genuinely different things (the boundary, and permanence under three driven conflicting events). |

## Defects found in the approved design, and what I did about them

The brief said to fix real defects rather than diverge silently. Four:

1. **The win-leg staging numbers were unsatisfiable.** The design's
   `per_run_variation` staged the win-leg runner at `4`, re-painted **down to 2**
   after its first death, while `EachDeathSpendsExactlyOneLife` required the
   ground to fire **twice** on that runner and `ReachingTheGoalWinsAndSpendsNothing`
   required it to win with lamps still lit. Work it through: `4 - 1 = 3`, re-paint
   to `2` gives `2 - 1 = 1`, and the second death gives `2 - 2 = 0` — which by this
   task's own rule is a **loss**, not a win. The leg could not both die twice and
   win. **Fixed** by raising the win-leg's painted number so the second death
   still leaves at least one life: 60 Hz `5 -> 3` (wins with 1 lit), 20 Hz
   `6 -> 5` (wins with 3 lit). The design's *shape* (down-paint after the first
   death, so a cached countdown over-estimates the spare lives) is preserved
   exactly.
2. **Two gates contradicted each other about the lost runner's position.**
   `TheLastLifeEndsTheRun` asserted the lost runner stays "within 150 cm of that
   spot **for the rest of the run**", while `ARunThatEndedNeverChangesAgain`
   required the fixture to **walk that same runner out of and back into the
   crumbling ground**. Left as written, the correct reference FAILs the moment the
   drive touches it — a manufactured FAIL of exactly the kind the
   "drive manufactures FAILs" law warns about. **Fixed** by splitting the clause:
   150 cm is gauged over the 2.5 s window after the run-ending crossing (during
   which the drive deliberately holds still), and for the rest of the run the
   clause becomes *nothing of the submission's ever moves it* — no per-frame jump
   beyond what walking produces. The prompt is worded to match ("nothing of yours
   may ever move it from there again"), so the contract the agent reads is the
   contract that is gauged.
3. **The design's risk #3 is factually wrong, in our favour.** It says driving a
   second pawn "is an extension of proven ground, not proven ground" and asks for
   a throwaway spike first. It is proven:
   `Source/CraftBenchTests/Tasks/t1-mud-wade/MudWadeFunctionalTest.cpp`
   `SpawnDefaultController()`s a second placed character and drives it with
   `AddMovementInput` **simultaneously** with the hero (lines 168 and 355-366), in
   a shipping green fixture. No spike needed and no fallback second map needed.
   I kept the design's *sequential* drive anyway — not for capability, but so that
   every gate window names exactly one runner and a FAIL never has to be attributed
   between two moving subjects.
4. **"Its own marker" was never defined** — an undisclosed gate literal (DEF-4)
   waiting to happen, and the gate `WhileLivesRemainYouComeBackToYourMarker`
   explicitly grades "not another runner's marker". **Fixed** by disclosing the
   rule in the prompt: *the disc under a runner's feet when the run opens is that
   runner's own for the rest of the run*. That single sentence turns what would
   have been an unfair gotcha into a genuine, fully-disclosed discriminator — the
   plausible wrong answer "send them to the nearest marker" is right for every
   death taken on a runner's own lane, so the drive takes one of A's four
   crossings at a spot that is **nearer a different runner's marker than its own**.
   The spot is DERIVED, not written down: the fixture scans the patch's near face
   for the point most clearly nearer somebody else's marker and refuses to start if
   the best it can find is under 400 cm. With the declared layout that is ≈ Y +1358
   — 3,435 cm to A's own marker against 2,414 cm to the far runner's, a 1,021 cm
   margin. (The `(3600,+700)` worked in the first pass's notes was arithmetic
   against a hand-picked spot, not what runs.) Anti-gaming note 4.

Two smaller additions in the same spirit:

- **"Nobody is ever replaced."** The engine-idiomatic respawn destroys the pawn
  and spawns a fresh one; a fresh runner has no death tally and would come back
  with a full row. Undisclosed, that is a gotcha; disclosed, it is a real design
  constraint and `TheRunIsNotYoursToRewire` pins the three object identities from
  t = 0.
- **"Measured flat along the floor."** A returned runner's capsule centre sits
  ~96 cm above its marker's origin, which would eat most of the disclosed 120 cm
  tolerance if the gate measured in 3D. Stated in the prompt, gauged flat.

## Second pass: four defects in the first pass's fixture, all fixed

Nothing here has been compiled or run — these were found by reading the fixture
against the reference and against the drive it actually builds. Every one of them
would have shown up as something other than what it is.

1. **Three missing closing parens** — `FinishTest(EFunctionalTestResult::Error,
   FString::Printf(…), R.Label);` in three of `ResolveStaging`'s
   HARNESS-PRECONDITION paths (the visibly-represented check, the lamp/word count
   check, and the `DiscRadiusUu` check). These do not fail this task: they fail to
   compile **`CraftBenchTests`**, which is the ThirdPerson substrate's editor
   module, so every ThirdPerson task's L1 goes red and reads as a substrate
   breakage. Fixed.
2. **`ValidateRoutes` validated journeys the drive never makes.** It re-read
   `Runners[Ph.Runner].Actor->GetActorLocation()` as the start of EVERY phase, so
   each route was checked from the runner's position at `PrepareTest` — its marker
   — rather than from where the previous phase left it. Two of the closing phases
   ("the won runner is walked back to the hazard", "the lost runner is walked onto
   the finish") then read as a walk from a marker **straight across the patch**,
   which is exactly what the route rule forbids: the run would have ended in
   `PrepareTest` with a false `HARNESS-PRECONDITION` on every submission,
   reference included, and a non-graded exit is the most expensive kind of wrong
   answer because it looks like our bug on a day when it is not. Fixed with a
   per-runner cursor walked forward phase by phase, plus the rule the real routes
   need: a phase may OPEN with the runner standing in the patch (it was just
   claimed there), so walking OUT is not a crossing and only walking back IN is a
   fault.
3. **The third conflicting event was never counted.** `FinalGrade` requires three
   driven conflicting events on each ended run, and `StepModel` counts only two of
   the three kinds (the ground and the finish); the third — moving an ended
   runner's board — happened in the drive but incremented nothing. Both ended runs
   would have finished on two apiece, so a **correct** reference would have ended
   as a non-graded staging fault instead of a PASS. Fixed where the re-paint is
   written.
4. **`LitCountOf` counted every point light on a runner.** A submission that hung
   any light of its own on a runner (a glow when it loses, say) would have failed
   `TheRunIsNotYoursToRewire` for carrying "7 lamps" — a gate firing on something
   the prompt never states, which is the DEF-4 shape this whole batch exists to
   avoid. It now resolves the row by the names the level built it under
   (`Lamp0..Lamp5`) and ignores anything else, and falls back to counting every
   point light when the row cannot be resolved by name — so a MISSING lamp is
   still a fault, and a submission that legitimately rebuilds the row is still
   graded on what is burning.

**Spec drift reconciled in the same pass.** The first pass's
*Verifier specification* described a drive the fixture did not build. `task.md` now
matches the code: calibration checkpoints every **5 s** (96 of them) plus the
sentinel at 500 s (`TimeLimit` 508); gate windows 2.5 / 1.8 / 1.8 / 1.8 s; every
disclosed deadline gauged **0.35 s late** (come-back at 1.35 s, half-second rules
from 0.85 s); holds 2.0 / 2.2 / 3.2 / 2.6 / 2.4 s and 0.6 + 2.2 s for a re-paint;
crossings staged 400 cm clear of the face and driven at the patch's centre line;
the **160 cm boundary band** that suppresses a still-running runner near either
trigger; the win leg going **around** the patch through a corridor 500 cm outside
its Y face; and the crossing count **derived** from the staging table's `RepaintA`
(4 on both legs) rather than the design's "repeat while the model says A still has
lives". The off-lane crossing spot is likewise derived by scanning the patch's near
face for the point most clearly nearer another runner's marker (≈ Y +1358 with the
declared layout: 3,435 cm to A's own marker against 2,414 to the far runner's, a
1,021 cm margin against the 400 cm floor) — the design's hand-computed `(3600,+700)`
is not what runs.

**`task.md` gained a "What the map must stage" subsection** (hidden from the agent),
because the map is authored after this change and the fixture enforces things a map
author cannot guess: the per-instance tags `RunnerLaneB` / `RunnerLaneC` on the two
placed runners, the player's marker having to be an **outer** lane (the middle lane
cannot satisfy the 400 cm ownership margin, and the fixture says so by name), the
patch being unscaled and square to the floor, and floor under the bypass corridor.

**`cameras.json` shipped, and a repo-wide finding on the way.** The plan is six
`pose` shots computed from the declared layout, framing more than one runner's lamp
row at a time (a single row proves nothing — one shared counter for the level
produces a picture of one row that looks just as correct). It deliberately carries
**no `pixel_validated` key**: the camera-plan loader's `_TOP_KEYS` did not
recognize one and `_no_unknown` rejects the whole plan over it, so **16 of the 36
committed plans in the repo are unloadable today** (every `craftbench-public` plan
that copied the key). This one loads — verified through the real
`camera_plan.load_plan`. The fix belongs in the loader (`_TOP_KEYS` + one line),
not in sixteen task folders, so it is left for the owner.

## Design decisions worth writing down

- **The lamp row is the only lives readout, on purpose.** There is deliberately no
  `LivesRemaining` property anywhere on the supplied classes — with one, a
  submission could set an ungraded number and the grade would read it instead of
  the work. The fixture reads the six `UPointLightComponent`s directly (intensity
  > 0), **never** `GetLitCount()`, which lives on a class the submission may
  rewrite.
- **The marker keeps its paint truthful from its own `Tick`.** That lets the
  fixture stage a re-paint by writing `PaintedLives` **by reflection** — no setter
  to override, no way for a submission to intercept the staging and then satisfy
  the anti-tamper read-back.
- **`AutoPossessAI = PlacedInWorld`** on the runner class: the two *placed*
  runners take an AI controller at level open (so they stand under their own
  weight and are drivable via `AddMovementInput` — an unpossessed `ACharacter` is
  inert, `CharacterMovementComponent.cpp:1749`), while the *spawned* one is left
  alone for the PIE player controller. `PlacedInWorldOrSpawned` (the
  `YardWatchmanCharacter` precedent) would also work — `AController::OnPossess`
  un-possesses the previous controller — but `PlacedInWorld` avoids the
  double-possession entirely.
- **Hard Rule #8 (playability), both halves.** The task names its own game mode,
  so `ALifeRunGameMode` re-states `PlayerControllerClass` as
  `BP_ThirdPersonPlayerController` (the thing that actually carries
  `IMC_Default`) and the runner's constructor loads the four `IA_*` actions —
  `AThirdPersonCharacter` declares them and assigns none. Without both, the map
  grades byte-identically while being uncontrollable, which is how five of six
  ThirdPerson maps once shipped.
- **Unscaled scene roots** on the marker, the crumbling patch and the finish disc.
  A child inherits the root's scale into *both* its offset and its collision
  extent (`UBoxComponent::CalcBounds` uses the full `LocalToWorld`), and this task
  has a flattened disc and a flattened slab that would otherwise multiply the
  volumes hung off them. The lamp row hangs off the character capsule, which is
  never scaled.
- **The answer may land anywhere.** The reference puts it all on the runner (2
  files) because per-runner ownership pushes that way, but the prompt explicitly
  allows a marker, the ground, the finish or the level's own rules object, and no
  gate reads where it lives. The tutorial wrong answer (state on the level's rules
  object) is *allowed* to be written — it just fails `TheBystanderIsUntouched`,
  which is the point.
- **Map basename `L_LifeRun` verified unused across the whole repo**
  (`git ls-files | grep -i liferun` → empty; the 50 committed basenames listed and
  checked). `map_locator.py` raises `DuplicateMapBasenameError` → exit 7
  HARNESS-ERROR, never a graded FAIL, and `cb lint` cannot catch it.
- **Overlap with the neighbours, checked deliberately.**
  `t1-spikes-hurt-you-and-you-respawn-at-your-marker` owns damage-on-contact,
  death at zero health, respawn-at-last-pad and a bystander twin, and
  `t3-checkpoint-restores-the-world` owns death → world rollback. This task has
  **no health, no damage number, no checkpoint progression, no world rollback and
  no moving hazard**. Its subject is the finite budget, *which* crossing is the
  last one, and a terminal latch that gates its own inputs.

## Hazards to watch on the first real run (the fixture is now built)

- **The two entry models must agree.** The fixture edge-detects a crossing from
  the capsule centre against the patch box **expanded by the capsule radius**;
  the reference uses the plain box. That is at most one capsule radius of travel
  apart — about 0.09 s at the template's walk speed — against a 0.75 s settle
  window, and a still-running runner inside a 160 cm band around either trigger is
  not judged at all. Keep the expansion at exactly one capsule radius; widening it
  further starts to matter. The other half of the same hazard is the RELEASE rule:
  the drive must keep pushing until the capsule centre is inside the PLAIN box,
  because the character coasts only ~28 cm and would otherwise be parked outside
  the patch a point-in-box answer never noticed.
- **Re-paint staging rules are load-bearing, not decoration.** Never re-paint at
  or below the deaths already suffered (the prompt promises a re-paint alone never
  ends a run, so the fixture must never create the ambiguous case), never within
  0.75 s of that runner's own death or terminal event, and suppress that runner's
  gates for 0.5 s either side. The tables in the spec already satisfy all three,
  including "no two markers ever read the same number at any instant" on either
  leg.
- **Gate ordering around the diagonal crossing spot.** A submission that returns a
  runner to the *nearest* marker will teleport it onto the bystander's disc, where
  two capsules will push each other — which trips `TheBystanderIsUntouched` as
  well as the return gate. The spec fixes precedence so the **return** gate is
  named (windowed gates first; the bystander gate always last, and only once the
  armed gate agreed). Do not reorder those two.
- **Run length.** ~200 s of modelled drive per leg, two legs. The sentinel is at
  t = 500 s. If the drive grows, move the sentinel with it —
  `ACraftBenchFunctionalTest::Tick` ends the test at the last scheduled
  checkpoint, so a run-level gate scheduled after the drive is the base fixture's
  auto-success trap if it is never reached.

## Left to do (not in this change)

1. `Content/Maps/t3-your-last-life-ends-the-run/L_LifeRun.umap` (committed binary,
   real-RHI authored) + its `docs/MAPS.md` row. **Author it against the spec's
   "What the map must stage" subsection**, not against the prose table alone: the
   per-instance `RunnerLaneB` / `RunnerLaneC` tags, the `PlayerStart` on the
   **outer** (y = -1100) marker, `ALifeRunGameMode` in the map's world settings,
   the patch unscaled and square to the floor, and floor out to y = -2000 for the
   bypass corridor are all `HARNESS-PRECONDITION`s if missed. There is no
   `authoring/author_map.py` yet — the empty folder is deliberate, not an oversight
   of this change.
2. `discrimination/MATRIX.md` — reference PASS / empty FAIL only (owner directive
   2026-08-18: no variant legs). `cb lint` WARNs `discrimination-required` until it
   exists; it must record measured results, not predicted ones.
3. Nothing here has been compiled or run. `tasklint` on this spec now reports
   exactly **one** ERROR — the missing map binary (`map-binary-exists`) — plus the
   `spec-h2-allowlist` WARN every sibling in this set reports (`Composed concepts`
   / `Requirement-to-assertion map`) and the `discrimination-required` WARN from
   item 2. No `fixture-fail-unique` warning: every gate's FAIL literal is unique,
   which is what lets the matrix name which one fired.
4. **The two entry models still have to be measured, not reasoned about.** The
   fixture arms a crossing one capsule radius early and releases the drive at the
   plain box; the reference reads the plain box. The first real run should be read
   with the `[t3-liferun calib]` lines (one every 5 s, per runner: painted number,
   deaths, wanted vs found lamps and word, position) before anything else is
   believed.
5. The owner has not played the reference. Per the 2026-08-18 directive a task is
   not done until they have.

## Third pass: the map script audited, the matrix written, one more fixture defect

A later pass had already landed `authoring/author_map.py` (884 lines) after the
second pass reported. This pass audited it, wrote `discrimination/MATRIX.md`, and
found one more fixture defect.

**The defect: `SuppressedFor` banded a still-running runner on BOTH sides of a
trigger's surface** (`FMath::Abs(PlanarDistToPatch(At)) < 160`). The drive releases
input at the plain box and the character coasts ~28 cm, so a runner ends a crossing
36–53 cm INSIDE the near face — inside the band. A submission that never returns a
runner therefore left it lying there permanently unjudgeable, and
`WhileLivesRemainYouComeBackToYourMarker` (which gauges at crossing + 1.35 s, window
to +1.8 s) could not fire against the one answer it exists to name: the drive walks
the runner clear of the band only at ~+2.7 s, after the window has closed. It never
showed on a correct submission — which is the tell that it could only ever hide a
WRONG answer. The band is now one-sided (`0 <= dist < 160`, outside only). Once the
capsule centre is inside a trigger, every honest entry model agrees it is inside, and
the 0.75 s model-change suppression already covers the <= 0.084 s the two models can
lag by plus a frame of tick order. `task.md` § *Settle and suppression* (twice) and
the fixture header were corrected to match.

**The map script audited, and nothing changed in it.** Its geometry solver was run
offline against the authored layout with `unreal` stubbed out — it solves cleanly:
loss leg runs out on **crossing 4**, off-lane crossing at **y = +1342** with
**1,012 cm** of ownership margin (floor 400), bypass corridor at **y = -2000**,
**19** driven phases, every waypoint inside the floor, no non-crossing segment on the
hazard. An independent re-implementation of the fixture's C++ scan
(`ValidateGeometry`, 25 cm step, 100 cm inset) reproduced `+1342 / 1011.77 / marker 2`
exactly. Every API call it makes was checked: `GetUnscaledBoxExtent`,
`GetComponentByClass` and `DefaultMappingContexts` were the only three not used by a
sibling script, and all three were verified against the UE 5.8 headers on disk. All
13 asset paths it and the scaffold load exist. Every prop it places is NoCollision by
construction, and the four engine components it does not control (`APlayerStart`'s
capsule, `UArrowComponent`, `UBillboardComponent`, `UFuncTestRenderingComponent`) were
each checked in the engine source to be NoCollision — otherwise its own read-back
collision sweep would refuse to save, and the fixture's route probe would report an
obstacle.

`cameras.json` was verified to load through the real
camera-plan loader (22 of the 39 plans committed at the time did;
the 17 that fail carry the unrecognised `pixel_validated` key, which is a loader bug
and not ours). All six poses were re-derived from the layout and are correct.

`tasklint` now reports one ERROR (`map-binary-exists`) and one WARN
(`spec-h2-allowlist`, set-wide) — `discrimination-required` is closed.

**Still true:** nothing has been compiled or run, the `.umap` does not exist, and the
owner has not played the reference.

## Fourth pass: two adversarial reviews, three blockers, and a real second subsystem

Two reviewers attacked the task on 2026-08-19. Eight findings; **six were real and
are fixed below, one was half-right, one was wrong.** Still nothing compiled and
nothing run.

### The verdict on each finding

| # | Claim | Verdict |
|---|---|---|
| 1 | *Difficulty bar (b) unmet — every one of the nine "locally-reasonable wrong answers" is refuted verbatim by a sentence of the prompt, and the reference is a 1:1 transcription of the prompt's bullet order* | **REAL.** Fixed by adding a second subsystem, not by hiding anything. |
| 2 | *Scaffold comments hand the agent the answers to the two headline gates* | **REAL.** Both comments deleted. |
| 3 | *The "three subsystems" collapse to two one-line early-outs inside one class; nothing crosses an actor boundary but one read* | **REAL**, and the same root cause as 1. |
| 4 | *`BothRunsEndedTheirOwnWay` is close to a fixture self-check* | **REAL.** Re-expressed against the level's own readouts; the model half is now a HARNESS-PRECONDITION; declared corroborative and to be discounted in a k/N. |
| 5 | *The graded map does not exist* | **REAL, and not fixable in this pass** — authoring the `.umap` needs a compiled editor and this pass is forbidden to build. `author_map.py` is updated for the new drive and re-solved offline. |
| 6 | *The drive REQUIRES the lost runner to stay walkable and the prompt says the opposite twice; immobilising it is a NON-GRADED exit* | **REAL, and the most expensive of the eight.** Disclosed in the prompt AND made a graded FAIL. |
| 7 | *The actor tag `LifeRunner` is load-bearing and never mentioned in either agent-visible section* | **HALF-RIGHT.** The tags **are** named in `## Workspace state pre-task` (which the agent sees) — "tagged `LifeRunner`", "tagged `LifeMarker`", and so on — so the reviewer's "never mentioned" is false. What was missing is the **consequence** of dropping one. Now stated, in the prompt and in the workspace section. |
| 8 | *The prompt's "keeps its own full row of lamps lit" contradicts the bystander gate on the 20 Hz leg* | **REAL.** Re-worded to "keeps lit exactly the lamps its own marker calls for". |

### The blocker fix: the finish now asks for a number

Findings 1 and 3 are the same defect — the task was one mechanism wearing three
costumes — and the fix had to be a **second subsystem that genuinely interacts**,
not a riddle. `AFinishDiscActor` gains `DemandedLives`: a number painted on the
disc's face (kept truthful by its own `Tick`, exactly like a marker's), which the
fixture re-stages per framerate leg and **re-paints twice mid-run**.

The two triggers now have **deliberately opposite temporal shapes**, and both live
in the same tick:

- the crumbling ground is an **edge** — the prompt says so in as many words, and
  every implementation gets it right;
- the finish is a **standing condition** — it opens whenever the runner on it is
  holding at least what the disc asks for.

The drive is built so that **the only frame on which the win leg is ever won is a
frame on which its runner did not move and entered nothing**: it walks onto the
disc holding less than the disc asks for (twice, with a step off and back on
between), and then the disc's own number comes down to it while it stands still.

That is what makes the wrong answers **code-shape errors instead of comprehension
errors** — which is the thing finding 1 was actually complaining about. Three of
them, each staged deliberately and each named by a different gate:

1. **Write the finish the way the level tells you to write the ground.** One
   overlap handler apiece is symmetrical, obvious code. It passes every arrival
   check, and has no event to hang the win on. `ReachingTheGoalWinsAndSpendsNothing`.
2. **Measure "enough" against the board rather than against what is left.** On
   **both** legs the disc asks, at the moment of the win leg's first arrival, for
   exactly the number painted on that runner's own marker (3 vs a board of 3 at
   60 Hz; 5 vs a board of 5 at 20 Hz) — so this answer opens the goal the instant
   the runner steps on. `ValidateStagingTable` refuses a table where that
   coincidence does not hold, so the discriminator cannot quietly stop
   discriminating. `TheGoalOnlyOpensToWhatItAsksFor`.
3. **`>` where the level says *at least*.** The disc's last move lands **exactly
   on** what the runner holds at 60 Hz and strictly below it at 20 Hz, so this
   answer PASSES 20 Hz and FAILs 60 Hz. A leg-split verdict on this task is a real
   off-by-one, not flakiness — that is now written into *Hidden invariants* so
   nobody debugs the harness for it.

Staging, both legs, re-derived offline and asserted by `ValidateStagingTable` (and
mirrored in `author_map.py`): 60 Hz the goal asks **3 → 5 → 1** against a win leg
holding 1; 20 Hz **5 → 6 → 2** against a win leg holding 3. Four safety rules —
arrive short, arrive short again after the first move, ask for no more than the
board (or the discriminator dies), and come down to at most what is held (or the
win is unreachable) — plus "both moves must be real moves".

### Finding 6: the non-graded exit that looked like our bug

This was the worst one. `task.md` told the agent the lost runner is *left standing
where the ground claimed it* and that *nothing of yours may ever move it from
there again* — and the drive then **walks that same body** off the patch and onto
the finish. A submission that implemented the prompt literally by immobilising the
pawn was green on every display gate, stalled the phase, and exited
`HARNESS-PRECONDITION` — non-graded, attributed to us, on a day the model was
never judged, with the cell silently dropped from the matrix.

Fixed on both sides, which is the only honest fix:

- **Disclosed.** A new prompt paragraph, *a runner is always a body that can be
  walked*: putting a runner back on its own marker after a death is the one and
  only time anything of yours moves a runner; apart from that nothing of yours may
  hold a runner where it is, pin it down or put it back — and an ended run is never
  *moved by you* again rather than *nailed down*. The lost-runner bullet points
  forward to it so the two sentences are not three paragraphs apart.
- **Graded.** New gate `ARunnerIsAlwaysFreeToWalk`: a walking phase that ran past
  its **derived** deadline while the body it was pushing every frame moved less
  than 150 cm, on floor the route was traced for, with nothing in the level able to
  block it. It is checked **only after `ReCheckDisplays` has re-run every display
  gate unconditionally**, so the ordering is: rewired level → FAIL; wrong readout →
  FAIL; pinned body → FAIL; and only a genuinely un-driveable level is ours.

### The other three

- **Finding 2.** `LifeRunnerCharacter.h`'s "nothing here is shared between them,
  and nothing here reaches another runner" (the answer to `TheBystanderIsUntouched`)
  and `LifeMarkerActor.h`'s "it can be re-painted while the run is going, and when
  it is, the paint follows at once" (the answer to `TheBoardIsReadWhenItMatters`)
  are **deleted**. Nothing compelled either: Hard Rule #7 requires the gate's VALUE
  in the prompt, and both values are there. The marker's "read it, do not write it"
  stays — that is a constraint, not an answer, and the prompt states it too.
- **Finding 4.** `FinalGrade` now asks the two questions separately. *Did the drive
  happen at all* is checked first against the fixture's own model and reported as a
  `HARNESS-PRECONDITION` — nothing a submission does can move that model, so a
  graded FAIL there was mis-attribution waiting to happen. *What is the level
  showing* is then read off the three runners' own lamps and words. It is still
  corroborative (a wrong word is named by a per-frame gate long before), and
  `task.md` and the fixture header now say so and require it to be discounted in a
  k/N alongside the anti-tamper gate.
- **Finding 8.** One word change in the prompt, and it closes a real 20 Hz-only
  false FAIL.

### What the fourth pass did NOT do

- **It did not weaken a gate to make a finding go away.** Every fix is a disclosure
  or an addition. The one gate whose message changed materially
  (`ReachingTheGoalWinsAndSpendsNothing`) got *stricter*, not looser: it now names
  the instant the goal opened rather than an arrival.
- **It did not author the map.** Finding 5 stands. `author_map.py` was updated (the
  goal's own authored number `4` — asserted to be a value neither leg stages; the
  two new drive phases; the four staging rules mirrored; a read-back assertion) and
  **re-solved offline with `unreal` stubbed out**: loss leg out on crossing 4,
  off-lane crossing at y = +1342 with 1,012 cm of ownership margin, bypass corridor
  at y = −2000, **21** driven phases (was 19), every waypoint on the floor, no
  non-crossing segment on the hazard, and the step-off spot 465 cm clear of the
  disc's painted edge (the fixture counts an arrival from 42 cm outside it, so
  stepping off and back on is a real second arrival).
- **It did not run `cb`, UBT or the editor.** `tasklint` reports the same one ERROR
  (`map-binary-exists`) and the same set-wide WARN as before — no new lint
  regression, and still no `fixture-fail-unique` warning, so every gate's FAIL
  literal is still unique.

### Hazards this pass introduced, for whoever runs it first

1. **The win now depends on a fixture WRITE, not on a walk.** If `DemandedLives`
   cannot be written by reflection the win leg is unreachable — named as
   `HARNESS-PRECONDITION` at the write, and `FinalGrade` additionally refuses a run
   in which the goal's number did not move twice or the win leg was never judged
   standing short of it.
2. **Intra-frame ordering at the winning write.** The write happens in
   `AdvancePhases`, i.e. AFTER that frame's gates; `StagingUntil` then suppresses
   0.6 s either side, and `StepModel` (which runs first next frame) is what flips
   the model. So the fixture can never judge a frame in which it moved the number
   itself. Worth confirming on the first real run all the same — read the
   `[t3-liferun calib]` lines, which now carry `goal-asks=`.
3. **The drive grew by ~19 s per leg** (~150–180 s modelled against 480 s of
   checkpoints and a 500 s sentinel). Still comfortable, still predicted.
4. **`ARunnerIsAlwaysFreeToWalk` has never fired.** Its threshold (150 cm of
   movement over a whole derived deadline) is chosen to be unreachable by any
   answer that walks at all, but it is the one new gate that could in principle
   manufacture a FAIL, and it should be the first thing checked if a correct
   reference ever trips it.
