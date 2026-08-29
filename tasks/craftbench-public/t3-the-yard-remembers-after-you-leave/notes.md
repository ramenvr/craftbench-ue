# notes — t3-the-yard-remembers-after-you-leave

Authored 2026-08-19 on the ThirdPerson substrate, UE 5.8, against the owner's
2026-08-18 difficulty bar. **Nothing in this repository was built or run while
this task was authored** — the orchestrator owns the build, and other agents were
working in the same tree. Every claim below that could only be established by
running is marked as unmeasured.

## Provenance

Corpus rows: `t2-save-and-resume` (7 checks, `Hardening Status = ALREADY STRONG`)
and `t1-save-survives-reload` (2 checks, `HOLD`), both from
`docs/task-design/startup-eval/`.

What the adoption review said about them, in two places that disagree:

- **§9 K4, the DEFER block (lines 1019–1022):** both rows are deferred rather
  than killed — "level streaming and SaveGame are LOCALIZED-unbuilt and cheap;
  **persistence has zero coverage anywhere in the tree**, and the runner's
  existing per-leg editor relaunch already gives a genuinely fresh process for a
  two-leg save/reload schedule."
- **§10 watch list, row 15:** "Reshape to the single-world form the playbook
  prescribes (write the slot, wipe in memory, re-derive from disk) with three of
  five pickups visibly still gone, two still collectable, and the hero standing
  at the restored checkpoint — persistence is **zero-covered** in the built
  tree."

**The K4 claim is false, and I checked rather than designing around it.**
`tools/verify-single/layers/registry.py:187` builds ONE `+`-joined automation
filter via `derive_test_filter()` and calls `run_l2` once;
`tools/verify-single/layers/l2_pie.py:454` launches a single
`UnrealEditor-Cmd … -ExecCmds=Automation RunTests <filter>; Quit`. Multi-fixture
buys a fresh PIE **world** per fixture inside ONE editor process, never a fresh
process. The only thing that spawns separate processes is `fps_legs`
(`registry.py:194-196`), and it re-runs the SAME filter at every rate with ALL
legs required to pass — it cannot express an ordered write-leg/read-leg pair, and
a leg-2 process would find leg 1's slot still on disk. the repo conventions say the same
thing in prose ("the runner discovers every fixture and runs them as one
`RunTests A+B+C` invocation in a single editor session").

So this task takes the §10 form — and goes one better than "wipe the in-memory
value", which a fixture cannot do to an implementation whose shape it does not
know. Instead the **fixture destroys and respawns every prop** (so nothing held
on an actor survives) **and deletes the project's save-game directory** (so
nothing on disk survives), leaving exactly one channel that could carry the
answer across: a live in-memory store. That is the channel
`ColdReopenForgetsEverything` condemns, and it is the whole task.

## What changed from the corpus rows, and why

| Corpus | Here | Why |
|---|---|---|
| "coins" and "checkpoints" | posts with painted worths, pads with lamps | the corpus mission names the mechanism it wants; the id and the prose here name the outcome (§5.1(1), §5.1(2)) |
| `FreshSaveCoinTotalIsZero` + `FreshSaveUsesInitialCheckpoint` (2 checks) | one merged gate, `ColdReopenForgetsEverything` | DEF-5 de-padding: both read "nothing has happened" and an empty submission gets both free, so they are one gate, not two |
| `CoinTotalRestoresAfterRestart` | `BankedTotalSurvivesRestage` | a restore into an *unchanged* world is an assignment; restoring into a world that has been renumbered is the thing that separates "stored the amount" from "stored the posts" |
| `PlayerResumesAtRestoredCheckpoint` | `RunnerResumesAtLatestPad`, measured against the **freshly respawned** pad's own transform | the corpus row would have passed on a written-down coordinate; here the pads move at every reopen |
| "a fully ended and restarted play session" | one PIE world, two mid-run rebuilds, the second preceded by deleting the save-game directory | there is no second-process lane (above). This is strictly stronger than "restart the process" for the property being measured, because it removes both the actors *and* the file while leaving the process alive to be caught holding a warm copy |
| no negative control | the far yard: three posts and a board, torn down and rebuilt in the same tick, gauged at every checkpoint | §5.1(5) / Hard Rule 12 |
| trigger unspecified | walking into a post / standing on a pad, driven by the shipping per-frame `AddMovementInput` timeline | §7.1.3 Tier 1; there is no input-injection lane |
| every trigger fires once | every trigger fires at least three times, across all three yard states | §7.1.4 re-trigger convention |
| nothing visible | rendered board text, a painted number over every post, a lamp row, a painted patch of ground that survives the post | §7.1.2, and every one of them is graded |

## Deviations from the approved design, all deliberate

1. **`UntakenPostStillAddsAfterReopen` was strengthened, not added to.** The
   approved design had ten gates plus the schedule sentinel and no gate at all
   for "the numbers over the posts are the yard's to paint". Working the
   analogue of the shop's `TheStallsAreTheMarketsToPrice`, I found the hole is
   *mostly* already closed: a solution that writes remembered worths back over
   the fresh posts pays the wrong amount at the next take and dies. But that
   only holds if the amount is compared against the **fixture's** staged number
   rather than against the post's own property, so clause (b) of that gate now
   faces the fixture on both halves. This is a strengthening of an existing
   gate rather than a twelfth one, deliberately, so N does not inflate.
   The residue — repainting a *taken* post's hidden number — is unobservable and
   is written up in *Hidden invariants* as a declared hole rather than claimed
   as defended.
2. **The post's ground volume is never switched off.** The obvious reading of
   "a taken post is gone" makes `ShowStanding(false)` disable the trigger, which
   would make `RetakenPostAddsNothing` free for every submission within a single
   visit. `ShowStanding` therefore hides the pillar and its number and makes the
   pillar non-colliding, and leaves `Ground` and `GroundPlate` alone: the patch
   stays painted, the volume keeps firing, and refusing to pay twice is a
   decision somebody has to make. The prompt discloses this ("walking back
   through the ground it stood on must not move the counter board").
3. **`PadOrder` was added, and the pad paints it.** The design's cold gate
   requires "the first pad", which is unresolvable once the yard shuffles its
   pads. `PadOrder` is a supplied property (the §5.1(2) supplied-property
   carve-out), the pad's own sign shows `pad <n>`, and the prompt says a pad
   carries "its place in the order". Without this the cold gate would enforce a
   literal the prompt could not state — corpus defect DEF-4.
4. **The pad stood on after the first reopen is required NOT to be the first
   pad** (a `PrepareTest` precondition). The design's schedule did not pin this,
   and if the runner's last mark before the cold reopen happened to be pad 1,
   the cold gate's placement half would be satisfied by a warm restore and only
   two of its three halves would discriminate. All three staged sets end the
   warm visit on a pad other than the first.
5. **Both reopens shuffle positions, not just numbers.** The design only
   required new worths. Moving the posts, the pads and the boards is free (the
   fixture already spawns them) and it is what makes "keyed on identity, never
   on index, spawn order or world position" measurable rather than asserted.
6. **`fps_legs` is deliberately absent**, as the design says. Every graded
   quantity here is a count, a rendered string, a lamp state or a position; the
   only time bound is a one-second settle sampled at three seconds. A second
   rate would double a ~150 s drive's exposure to the reposition-mid-drive
   hazard for no anti-overfit gain.

## Design decisions worth writing down

- **Why the reference keeps a subsystem at all.** Something has to know which
  props are currently standing so a change to one can refresh its siblings, and
  that something cannot be a prop. `UYardMemorySubsystem` is therefore a
  `UGameInstanceSubsystem` — but it holds *only* the live-prop lists. Every
  question about what was taken, banked or marked is a fresh
  `LoadGameFromSlot`, and every change is a `SaveGameToSlot` immediately after.
  The wrong answer is one field away, which is exactly the point: the reference
  and the headline wrong answer differ by *where the answer is read from*, not
  by how much code was written.
- **`World->HasBegunPlay()` is how the reference tells a rebuild from a level
  open.** `AWorldSettings::NotifyBeginPlay` sets `bBegunPlay` *after* its
  dispatch loop, so a placed actor sees `false` in its own `BeginPlay` and an
  actor spawned into a running world sees `true`. That is the reference's signal
  to set the runner down. **It is not load-bearing for the grade**: no gate
  samples the runner's position before the first reopen, so a submission that
  also places the runner at the level's first open passes. Written up in
  *Hidden invariants* so a reviewer does not "fix" it into a requirement.
- **Lamps are graded off the point light's intensity, not off the mirror.**
  `bLastShownLit` lives in a file the agent may edit. Same reasoning as the
  shop's revision #2: the mirror is required to *agree* with engine-owned state,
  never to stand in for it. Same for `LastShownTotal` vs the rendered `FText`
  and `bLastShownStanding` vs `Pillar->IsVisible()`.
- **Unscaled scene-component roots on all three props.** A scaled root
  multiplies both a child's relative offset and its collision extent
  (`UBoxComponent::CalcBounds` uses the full `LocalToWorld`), which is how a
  120 x 120 pad once became 840 x 960 in mid-air. The shop scaffold divides the
  root scale back out of every child; this one avoids the arithmetic entirely by
  putting a bare `USceneComponent` at the root, with the actor's origin **on the
  floor**. Every size in these files is the size it says it is.
- **Everything is `Movable`.** The props are destroyed and respawned mid-run;
  PIE scores moving a Static actor as a failed test.
- **150 cm is 150 uu, and the geometry was chosen around it, not the other
  way.** Pad slots are 1,000 uu apart and the PlayerStart is 1,221 uu from the
  nearest pad, so the disclosed radius cannot be satisfied by the wrong pad or by
  standing where the level started. The number is in the prompt; the geometry is
  not, so the geometry is what moves if calibration disagrees — and
  `authoring/author_map.py` says so in the failure text of the check that enforces
  it ("CHANGE THE SPACING, NEVER THE DISCLOSED NUMBER").

## Hazards, and what was done about each

1. **A durable record survives the workdir.** This is the highest-risk defect in
   the whole design, and it is the one that fails a *correct* submission. The
   fixture must empty `FPaths::ProjectSavedDir()/SaveGames` from
   `OnWorldInitializedActors`, before any `BeginPlay` — the same
   `IFileManager::Get().DeleteDirectory(*Dir, false, true)` already shipping at
   `MarketDayFunctionalTest.cpp:269-270` — or the second run in one workdir (a
   re-capture, a refgate re-run, a `--keep-workdir` iteration) opens warm at
   t = 0. The spec also demands a probe at the first settled sample: if the yard
   did not open on the staged numbers, the run stops there rather than grading a
   yard that was already wrong.

   **BUILT WITH A SPLIT VERDICT, which the spec's earlier draft did not have.**
   Attributing *every* opening mismatch to the workdir would have handed any
   submission a denominator opt-out costing it nothing — repaint one post in
   `BeginPlay` and the run goes UNGRADED instead of FAILED. So the fixture records,
   at wipe time (before anything has begun play, so the reading can mean nothing
   else), whether the directory was genuinely gone afterwards. Store still there ⇒
   Error, naming the leftover record. Store verifiably empty ⇒ a scored FAIL under
   `SessionTallyTracksExactly`, because with nothing written down anywhere the only
   thing that can have repainted or hidden a post before anybody walked into it is
   the submission's own code. The hazard this hazard-note is about — a correct
   submission failed for having obeyed the prompt — lives entirely in the first
   branch, and that branch is unchanged.
2. **Whatever is done to the record and the respawn must be in the SAME tick.**
   (Superseded in part by the 2026-08-19 rework: there are three reopenings now and
   each does its own thing to the record, but the ordering argument below is
   unchanged and applies to all three.)
   If the fixture wipes and then waits, a submission that flushes its state on a
   timer re-creates the record inside the window and opens warm through no fault
   of its own. The spec states the ordering as a construction requirement; any
   future edit that separates them re-opens the hazard.
3. **Does `SaveGameToSlot` recreate a deleted directory?** CLOSED at authoring
   time by reading the engine, not by running it. `UGameplayStatics::SaveGameToSlot`
   reaches `FGenericSaveGameSystem::SaveGame`, which calls
   `FFileHelper::SaveArrayToFile` (`SaveGameSystem.h:153`) -> `CreateFileWriter` ->
   `FFileManagerGeneric::CreateFileWriterInternal`, and that function
   (`FileManagerGeneric.cpp:110-117`) retries `OpenWrite` after
   `MakeDirectory(*FPaths::GetPath(Filename), /*Tree=*/true)` when the first open
   fails. So a deleted `Saved/SaveGames/` is recreated by the next write, and
   Windows uses the generic system (no platform override), so that is the live
   path. **Belt and braces:** even if it somehow failed, the reference would still
   pass `ColdYardTakesAgain`, because `TakePost` shows the board off the record
   object it has just mutated in memory rather than off a re-read — a failed write
   would only lose the day, and nothing after checkpoint G reads it back.
   Source-verified, still not run-verified.
4. **The drive can manufacture FAILs.** The runner is repositioned by the
   agent's own code at each reopen, so the drive must re-resolve every waypoint
   per frame from the live actors (or, for a taken post, from the transform the
   fixture spawned it at) rather than replaying a fixed-direction timeline. It
   must also issue **no movement input at all** for the 3.0 s after each rebuild,
   or it will walk the runner off the pad it is about to be graded on. Dwells are
   sized against the substrate's measured `MaxWalkSpeed = 500` /
   `BrakingDecelerationWalking = 2000` (`ThirdPersonCharacter.cpp:33,35`), **not**
   the engine defaults.
5. **Overlap at spawn.** A post spawned on top of the runner would fire its
   ground volume before anything is bound. The rows sit on opposite sides of the
   lane, so the nearest post slot is 1,404 uu from the nearest pad slot — against
   the 372 uu that a set-down would need to reach a post's ground (130 half-extent
   + 42 capsule + 200 margin), which `author_map.py` asserts explicitly. Both
   rebuilds happen while the runner is at the gate, 1,792 uu from the nearest pad
   and 1,700 uu from the nearest post.
6. **Overlap with two shipped siblings — worth an owner glance.**
   `t2-shop-takes-your-coins-and-remembers` already ships the
   destroy-and-respawn-mid-run pattern, the restaged-numbers pattern and a
   restore across it; its spec says outright that "a save-game slot, a
   game-instance subsystem, a world subsystem or a file all pass identically,
   and the fixture never looks for one." **This task is the exact complement**
   and the only place in the tree where those four answers do *not* pass
   identically. `t3-checkpoint-restores-the-world` owns
   checkpoint-restore-after-death *within* a session; the pad/lamp subsystem
   here is deliberately held to two gates so it carries the seed's "runner
   standing at the restored checkpoint" without becoming a second checkpoint
   task.
7. **Two gates are free for an empty submission.** `TwinYardNeverChanges` and
   `ColdReopenForgetsEverything` both read "nothing has happened". Declared, not
   hidden: the first is mandatory under the in-scene-control law, the second is
   the headline gate against the headline wrong answer, and the empty leg is
   named against a gate it cannot get free (`SessionTallyTracksExactly`, on the
   substring "the counter board should read").

## The wrong answer this task exists to catch

Written down explicitly, because a task whose plausible wrong answer cannot be
named is too easy:

> Keep the yard's state on a game-instance or world subsystem — the natural UE
> answer to "the actors are destroyed, where does the state live?", and exactly
> what the already-shipped shop task teaches — and *also* write a save file on
> every change, so the prompt's "write it down on disk" line is satisfied. On
> reopen, restore from the live subsystem, because it is right there and warm.

That submission passes every warm gate: the taken set comes back correct, the
banked total is exact, the runner lands on the right pad, the untaken posts are
still takeable, the far yard is untouched. It dies on
`ColdReopenForgetsEverything`, because the fixture deletes the save-game
directory in the same tick it rebuilds the yard and the warm-restored yard opens
with three posts still missing, the old total on the board and the runner on the
wrong pad. Nothing about it is sloppy; the load-bearing question — *is disk the
source of truth, or merely a copy of it?* — is simply never asked by the author.

**The one this task actually turns on, added 2026-08-19.** The paragraph above is
the *careless* version of the warm answer, and the review that landed that day
pointed out something uncomfortable: the prompt used to hand it to the reader
outright ("make that written record the thing the yard reads when it opens —
because some days it is thrown away"), so nobody who read the paragraph
clause-by-clause would write it. The prescriptive clause is gone, and the answer
this task is now shaped around is the **careful** version — keep the state warm,
write a save file, and *clear the warm state whenever the file is missing*. That
one satisfies every question about whether the record EXISTS, needs the file's
contents to be nothing at all, and passed every gate this task shipped with. It
dies on the rewind, because putting the earlier bytes back changes what the record
SAYS without changing whether it is there. No amount of reading the prompt talks
you out of that answer; only deciding that the record is the memory does.

Two more, each on a different named gate:

- persist the **total and the count** of posts taken rather than which posts →
  every post comes back standing (`TakenPostsStayGoneAfterReopen`), and the
  drive's deliberate pass back through an already-taken post's ground then
  double-counts (`RetakenPostAddsNothing`);
- persist the taken identities and **recompute** the total on reopen by summing
  those posts' worths off the fresh posts → right on the first day, wrong the
  moment the yard is renumbered (`BankedTotalSurvivesRestage`).

## Honest limits of the per-run variation

> **SUPERSEDED 2026-08-19 by the adversarial review — see that section below.**
> The paragraph that follows was the honest statement of a position the review
> showed to be indefensible, and it is kept because the reasoning that led to it
> is the reasoning a future author will repeat. The trade it describes ("this repo
> has been bitten worse by unreproducible failures than by hardcoding") is a real
> trade, but it is only available while the answer key is secret — and
> `tasks/README.md` says these specs are the ones intended for
> publication, so it never was. The staged day is now chosen from the clock and
> logged, and pinning is explicit.

Three complete number sets ship in the fixture, selected by
`-CraftBenchYardSeed=N` with default 0, so a discrimination leg reproduces byte
for byte. With no seed on the command line, every run uses set 0 — so "varies per
run" is really **"varies per staged set, and restages twice inside every single
run."** The anti-hardcode defence rests on those two mid-run restages plus the
level's decoy numbers, not on run-to-run entropy. That is a deliberate trade
(this repo has been bitten worse by unreproducible failures than by hardcoding),
and it is stated rather than overclaimed.

## Verified at authoring time, without building anything

Every item here is a static check and each names its instrument, so a reviewer can
redo it in seconds. None of it substitutes for L1.

- **The front matter parses.** `tools/verify-single/spec.py::parse_task_file`
  returns `task_id=t3-the-yard-remembers-after-you-leave`, `substrate=ThirdPerson`,
  `set_name=craftbench-public`, `tier=T3`, `layers=('L1','L2')` and one fixture,
  `L_MemoryYard :: AMemoryYardFunctionalTest`. No `fps_legs`, per the design.
- **All five cited concept ids exist** in `tools/coverage/concepts.csv`
  (`saving-and-loading-your-game`, `actor-lifecycle`, `collision-overview`,
  `programming-subsystems`, `ps-strings`) — one row each.
- **`L_MemoryYard` is unique across the repo.** `git ls-files | grep -i memoryyard`
  returns 0 matches, so `map_locator.DuplicateMapBasenameError` (exit 7) cannot
  trip.
- **All twelve gate names in this spec exist verbatim in the fixture, and vice
  versa** — grepped both directions. The schedule the spec describes (60 logging
  checkpoints at 6 s plus a sentinel -- since 2026-08-19, index 78 / t = 480 s) matches the fixture's
  `kSentinelIndex = 60`, `kSentinelAtS = 420.0`, `kCheckpointEveryS = 6.0`.
- **`UWorld::HasBegunPlay()` is not deprecated in UE 5.8** (`World.h:2840`), and
  the ordering the reference leans on is still the engine's:
  `AWorldSettings::NotifyBeginPlay` dispatches `BeginPlay` to every placed actor
  and only *then* calls `World->SetBegunPlay(true)`
  (`WorldSettings.cpp:363-379`), so a placed actor reads `false` in its own
  `BeginPlay` and an actor spawned into a running world reads `true`. This matters
  because `--strict-warnings` now FAILs a reference that uses a deprecated API.
  Precedent: the shipped `t3-keyring-opens-what-it-was-cut-for` reference makes the
  same call.
- **The reference's registry types have shipped precedent.**
  `TArray<TWeakObjectPtr<A...>>` with `AddUnique(RawPtr)` / `Remove(RawPtr)` is
  exactly what the refgate-PASS `MarketKeeperSubsystem` does
  (`MarketKeeperSubsystem.h:54-55`, `.cpp:84,105`), so the implicit
  raw-pointer-to-weak-pointer conversion at those call boundaries is known to
  compile on this engine at this warning level.
- **The scaffold leaks nothing.** Grepped all four scaffold files for `fixture`,
  `assert`, `gate`, `checkpoint`, `seed`, `staged`, `Cold`, `SaveGame`,
  `subsystem`, `record`, `disk` and `150`: the only hits are the yard's own gate (a
  gap in a wall) and two geometry constants that happen to be 150 uu. Nothing in
  the scaffold hints that the answer is a file on disk, which is the point — a
  scaffold that said `record` would hand over the headline gate.

## A real defect found in the reference, and fixed

Found by walking the reopen tick statement by statement rather than by running it,
and it would have failed the reference on its own warm gate.

**The symptom it would have produced:** `RunnerResumesAtLatestPad` FAIL at
checkpoint B — the runner standing on, and the lamp burning on, whichever pad the
fixture happened to respawn FIRST, rather than the pad the mark was on. Intermittent
across staged sets, and completely opaque from the failure message, because every
other number would have been right.

**The mechanism.** `PlaceRunnerOn` moves the pawn with `SetActorLocation`, and a move
fires begin-overlap **notifications synchronously** — `USceneComponent`'s move path
calls `UpdateOverlaps(..., bDoNotifies = true)` before `SetActorLocation` returns
(`SceneComponent.cpp:1087,1195`). So the pad the runner is put down on immediately
reports somebody standing on it, and the first cut let that count as a visit:

1. The pads come back **one at a time**, each registering in its own `BeginPlay`.
2. The first pad to register is usually not the marked one, so `ResolveMarkedPad`
   falls back to "the lowest `PadOrder` standing **so far**" — that pad alone — lights
   it, and sets the runner down on it.
3. That placement's synchronous overlap called `StandOnPad`, which saw a pad that was
   not the recorded mark and **overwrote the record with it**.
4. Every later pad's registration then read the corrupted record and faithfully
   honoured the yard's own mistake for the rest of the run.

Worse, it also broke the **cold** gate whenever the respawn order did not happen to
start with pad 1: the yard would put the runner down on, say, pad 3, write pad 3 into
a record that had just been deleted, and `ColdReopenForgetsEverything` would fail on
its placement clause while the board and the posts read perfectly.

**The fix**, six lines, and it is a semantic rather than a workaround: *being set down
by the yard is not the runner choosing to stand somewhere.* A `bSettingRunnerDown`
flag is raised across the move with `TGuardValue` (`UnrealTemplate.h:350`, not
deprecated in 5.8) and `StandOnPad` ignores any visit that arrives while it is up.
Traced by hand against both reopens in every respawn order: the transient placements
still happen, they just no longer write, so the last registration — the one that can
see the whole pad set — decides, and it decides correctly. The cold path now also
leaves the record genuinely absent instead of re-creating it with a spurious mark.

**Not extended to the posts, deliberately.** A placement that dropped the runner into
a standing post's ground would take that post, but it cannot happen: the post row and
the pad row are on opposite sides of the walking lane, 1,404 uu apart at their closest,
and a runner standing at a pad centre reaches only 42 uu (its capsule radius) toward a
post's 260-square ground volume — 1,232 uu clear. `author_map.py` asserts the 372 uu
this needs as a named check, kept deliberately even though the row checks subsume it
today, so a future loosening of those cannot make a set-down take a post in silence.
Guarding `TakePost` as well would be defending against geometry the map script
enforces, and would quietly change what a placement means if that geometry ever
moved. Recorded here rather than coded.

**Why this belongs in the notes and not only in the code:** it is the single most
expensive trap in the task, it is invisible until the *second* reopen, and any agent
that writes the obvious reference will hit it. It is the main reason the honest
senior-dev estimate for this task is 5-8 hours rather than 3.

## Two spec/fixture divergences found and fixed

Both were found by reading the landed fixture against the spec written earlier the
same day, and in both cases **the fixture was right and the spec was corrected to
match it** — the reverse would have left the spec describing a gate that does not
exist.

1. **The order of the cold rebuild.** The spec said delete-the-record, then
   destroy, then respawn. The fixture does destroy, then delete, then respawn, and
   says why in a comment: `EndPlay` on a destroyed prop is a perfectly legitimate
   place for a submission to write the day down, so deleting first would leave
   exactly that submission holding a record the fixture never took away — and
   `ColdReopenForgetsEverything` would then fail a *correct* solution for having
   obeyed the prompt. The "same tick" requirement (no window in which a
   timer-flushing solution could re-create the record) survives either ordering,
   because all three phases are adjacent statements. The spec's
   Verifier-specification paragraph and the step-10 line of the day table now state
   the fixture's order and the reason for it.
2. **`RunnerKeepsWalking`'s exemption window.** The spec said "the two single
   frames on which the yard reopens". The fixture grants `kRebuildGraceS = 0.5`,
   because setting the runner down legitimately drops the character into a fall for
   a frame or two. The spec now says 0.5 s in all three places it described that
   window, and says why the grace cannot launder a frozen runner: the reopen sample
   is taken 3.0 s after the rebuild, six times later.

## The map layout was RE-SHAPED, and the old one was provably unwalkable

Found while writing `authoring/author_map.py` against the landed fixture, and it is the
one place where the build brief's map table and the fixture could not both be right.

**What the fixture actually needs.** `AMemoryYardFunctionalTest` does not walk to a prop
directly. It derives ONE walking lane,

    LaneY = 0.5 * (mean near-post Y + mean pad Y)        (ResolveYards, line 805)

reaches every prop by a straight perpendicular leg off that lane (`LanePointFor` /
`BuildRoute`), and then `CheckRouteIsWalkable` refuses -- as an attributed
`HARNESS-PRECONDITION`, never a graded FAIL -- any waypoint within `kMinPropClearanceUu`
= 250 uu of a prop the step is not about, or any leg that passes that close to one. Two
structural consequences, and neither is optional:

1. the posts have to be on ONE side of the lane and the pads on the OTHER, each row far
   enough off it that a lane traverse clears every prop in the row at once;
2. **no two props may share a column**, because the outer one's perpendicular retreat to
   the lane runs straight through the inner one at a lateral offset of zero.

Note where the exemption is and is not. `PropOfLeg` returns a prop only for a Kind-1
leg -- the one that stands ON the thing. The lane-approach and lane-return legs (Kinds 0
and 2) carry NO exemption at all, so a lane waypoint has to clear even the prop the step
is about.

**The brief's table cannot satisfy (2), and this was measured, not argued.** It placed
five posts on a 2 x 4 grid at x in {400, 1100}, y in {-1200, -400, 400, 1200} and three
pads on a 2 x 3 grid at x in {-1400, -500}, y in {-800, 0, 800}. Two columns cannot hold
five posts without one column holding three, and of any three posts in one column at
least two fall on the same side of the lane. Brute-forced the fixture's own route builder
and its own two checks over **all 56 x 20 = 1,120 slot choices x 3 staged sets x 3
rebuild rotations: ZERO walkable.** Every one of them would have ended the run as a
`HARNESS-PRECONDITION` -- the level's fault, attributed to nobody, on every model.

**What shipped instead** is the same yard re-shaped into rows: five posts at y = +700 on
x in {-1500, -750, 0, 750, 1500}, three pads at y = -700 on x in {-1400, -400, 600}, the
lane painted at y = 0, the boards well off it at y = -1300. Derived LaneY comes out at
exactly 0, and `check_geometry` asserts that rather than assuming it. Worst clearance
anywhere in the (now) 93 simulated routes: **700 uu to a prop** (against 250 needed), 1,082 uu
to a board (against 200), 400 uu to a wall. That is 2.8x margin on the binding
constraint, in the direction that cannot mask a wrong answer.

**It is a better showroom, too**, which is the part that was luck rather than design.
Everything the scaffolds print faces -Y (a text component's readable face is +X and each
sign is yawed -90), so with the board nearest, then the pad row, then the lane, then the
post row, a single camera south of the yard reads the whole graded state front-on -- and
one wider pose gets the far yard in the same frame across the dividing wall.
`cameras.json` (the camera-plan lane; not part of this release) was re-solved on the new layout and each pose was checked by computing the
horizontal half-angle to the near board and to both ends of the post row.

**The script REFUSES rather than trusting any of this.** `check_geometry` runs before
`new_level` (which saves an empty package immediately, so a script that raises later
leaves a plausible-looking map on disk that the automation run reports as "No automation
tests"), and it ports the fixture's constants, its rotation rule and both of its checks
rather than restating conclusions. Twelve deliberate mutations of the layout were run
against it and **all twelve were refused**: posts and pads on the same side of the lane;
two posts sharing a column; pad spacing inside twice the disclosed 150 uu; a row pulled
onto the lane; both rows pulled in with the lane left at 0; the dividing wall moved into
the walk; a counter board standing in the lane; the gate gap narrowed to a doorway; the
gate gap moved off where the fixture walks out; a board parked where the fixture would
never move it; and a single decoy worth drifting into agreement with a staged round. Two
of those were caught by the route simulation itself rather than by a pre-check, which is
what the simulation is there for -- the pre-checks are the binding constraints today, and
the simulation is what will catch a layout change they do not anticipate.

**Consequences recorded elsewhere:** `task.md`'s map table (agent-visible prose -- a
stale table misleads the model, which is worse than disclosing the layout) and three
geometry paragraphs in this file now state the row layout; `cameras.json` was re-posed;
nothing in the reference or the scaffold referenced a coordinate, so neither moved.


## Adversarial review 2026-08-19, and what it changed

Two reviewers attacked the task. Six findings; **five were real and are fixed
below, one is unfixable from an authoring seat and is the top handoff item.**
Every fix is a tightening or a disclosure — no gate was weakened to make a finding
go away.

### BLOCKER (confirmed real, NOT fixed here) — the level does not exist

`Content/Maps/t3-the-yard-remembers-after-you-leave/L_MemoryYard.umap` is absent,
while `task.md`'s agent-visible *Workspace state pre-task* calls it "the staged
yard, committed binary". `tools/verify-single/map_locator.py::locate_map` globs
`Content/Maps/L_MemoryYard.umap` and `Content/Maps/*/L_MemoryYard.umap`; with zero
candidates L2 has no world and **every** submission — the committed reference
included — comes back HARNESS-ERROR rather than graded. `cb refgate` cannot close.

This cannot be fixed by authoring: `authoring/author_map.py` places a
`MemoryYardFunctionalTest` actor, so it needs the `CraftBenchTests` module BUILT
before the editor can resolve the class, and this seat is explicitly barred from
running builds. It is the orchestrator's first action. The command and the
uniqueness check are in *What is still open* below. Nothing downstream of it —
route clearances in a live world, the staged-vs-decoy separation as actually
authored, both MATRIX cells — is verified until it runs.

### MAJOR (real, fixed) — the record's CONTENT was entirely ungraded

The fixture only ever asked whether the record **exists**: `WipeDurableStores`
called `DeleteDirectory` / `DirectoryExists` and nothing else, and no gate ever
compared a restored value against anything the submission wrote. The reviewer's
concrete passing wrong answer is exact and worth keeping written down:

> a `UGameInstanceSubsystem` holding `TSet<FName> Taken` / `TMap<FName,int32>
> Banked` / `TMap<FName,FName> Marked` purely in memory, calling `SaveGameToSlot`
> with an **empty** `USaveGame` subclass (zero `UPROPERTY`s) after every change,
> and on every prop registration doing
> `if (!UGameplayStatics::DoesSaveGameExist(TEXT("Yard"),0)) { Taken.Reset();
> Banked.Reset(); Marked.Reset(); }`

Walked through every gate of the old task, that passes all eleven. It is an
in-memory answer, and the *Hidden invariants* section claimed in so many words
that "what the gate genuinely excludes is the whole family of in-memory answers".
That claim was false. The headline concept — deciding what belongs in the record —
was not measured at all.

**Fix: the REWIND.** A third kind of reopening. At the settled sample after the
first post is taken (the moment the counter board first rises), the fixture reads
every byte under `Saved/SaveGames/` into memory — `SnapshotDurableStores`. At one
of the three rebuilds it deletes that directory and writes the copy back byte for
byte — `RestoreDurableStores`. Existence is unchanged; content is older. A
record-sourced yard reopens on one post gone and the early total; a memory-sourced
one reopens on the day it remembers. The gate is `PutBackRecordRulesTheYard`.

Three decisions inside that fix are load-bearing:

- **The copy lives in memory, not on disk.** A copy under `Saved/` anywhere would
  be a second channel the submission could find and read — the exact thing the
  rewind exists to rule out.
- **The moment is disclosed in the prompt**, in the words "a copy of the written
  record is taken a moment after the counter board first rises — so keep the
  record up to date as the day goes, not only when the yard shuts". A submission
  that batches its write to `EndPlay` fails a stated contract rather than an
  ambush. Rule 7 satisfied: the value is in the prompt, the gate's name is not.
- **In staged day 2 the rewind comes AFTER the cold reopening**, so the state it
  requires existed before the record was ever deleted. No in-memory channel can
  carry that at all — not even a keeper that snapshots itself.

### MAJOR (real, fixed) — a fixed seed plus a published answer key

`ChooseSet` read `int32 Seed = 0` from `-CraftBenchYardSeed=`, and **nothing in
`tools/` passes that flag**, so every graded run ran staged set 0 for ever.
Meanwhile `task.md` prints all three sets in full and
`tasks/README.md` says these specs are the ones intended for
publication. Difficulty condition (c) — a hard-coded answer must be wrong from the
first frame — held only while the print run stayed secret.

**Fix**, copied from the sibling one folder over
(`AKeyringFunctionalTest::RecutTheYard`): the default is now
`FPlatformTime::Cycles() & 0x7fffffff`, logged at the top of every run with the
exact flag to reproduce it. Pinning still works and is now cleaner than the
sibling's — `FParse::Value`'s RETURN value decides, so `-CraftBenchYardSeed=0`
pins day 0 and absence randomises, rather than 0 meaning "no seed".

### MINOR (real, fixed) — the day's SHAPE was a constant across all three sets

The old `RebuildBothYards` hard-wired `if (ReopenIndex >= 2) WipeDurableStores()`
and `BuildRoute` was called with the fixed schedule `(0,5) (5,3) (8,1)`, so "there
are exactly two rebuilds and the cold one is the second" was invariant across
every set. A submission with **no persistence at all** could count how many times
a board registers into a world where `HasBegunPlay()` is true and clear its ledger
on the second. Randomising the seed does not close it, because all three sets
shared the shape.

**Fix**: the shape is now a per-set field. `FStagedSet` carries a 14-step
`Script[]` of `StandOnPad` / `TakePost` / `WalkThroughTakenPost` / `Rebuild(kind)`,
`BuildDayTrace` simulates it, and the stretches between rebuilds
(`PhaseStart`/`PhaseCount`) are sliced out of it — nothing hard-codes "five then
three then one" any more. Every day does warm, rewind and cold **once each in its
own order**: `Warm/Rewind/Cold`, `Rewind/Cold/Warm`, `Cold/Warm/Rewind`.
`PrepareTest` refuses a day whose three kinds are not one of each. "Reset on the
Nth" is now wrong in at least two days out of three, for every N, and the day is
picked from the clock.

### MINOR (real, fixed) — the prompt prescribed the mechanism it was measuring

`task.md` said "make that written record the thing the yard reads when it opens —
because some days it is thrown away while the yard is shut", which pre-empts the
inference the anti-gaming note claimed as the discriminator. **Fix**: the
prescriptive clause is deleted. The observable values are all still stated (rule 7
holds), and the honest accounting is now in the spec: the warm-cache answer was
never much of a discriminator once that paragraph was read, and the answer this
task actually catches is the *careful* one (finding 2's keeper-with-a-token),
which no amount of reading the prompt talks you out of.

### MINOR (real, fixed) — the two halves disagreed about `Destroy()`

`ReadWorld`'s `ReadPostRow` explicitly tolerated a destroyed post ("counts as gone
exactly like a hidden one") while `ResolveYards(false)`, one rebuild later, hard-
required `Near.Num() == 5 && Far.Num() == 3` and emitted a SCORED FAIL. A
destroy-based submission graded green through the whole opening stretch and then
died under a gate whose value it had never been told — and the message read as
though it had removed props it was told to leave alone.

**Fix, both halves**: the value is DISCLOSED in the prompt ("The five posts, the
three pads and the two counter boards are the yard's own, and the yard always has
exactly those: never add one, never take one out of the world, never rename one. A
post that has been taken is still one of the yard's five...") and `ReadWorld` now
agrees with `ResolveYards` — a prop missing from the world is a scored
`TheYardsOwnPropsAreStillThere` failure at the FIRST sample after it goes, not a
reading of "gone". `ReadFailGate` carries the right gate name to `FailUnderGate`
so the failure is not attributed to whichever gate happened to be in flight.

### Everything else that moved with those fixes

- **Rotation rule.** Prop `i` moves to slot `i + shift` with shift `1, 1, 2` across
  the three rebuilds — cumulative `1, 2, 4`. A plain `1, 1, 1` would have walked
  the three pads and the three far posts all the way round to their ORIGINAL slots
  at the third reopening, which is a free pass for a position-keyed restore at the
  rebuild it is likeliest to survive.
- **Board offsets are bounded, not cumulative** (`{+550, +1100, +300}` along the
  board's own row, indexed by reopen). `kBoardShiftUu * ReopenIndex` at three
  rebuilds would have put the far board at x = 4050, outside the far yard's east
  wall at 3700 and past the floor edge. `check_geometry` now checks the floor and
  the dividing-wall side for every offset.
- **`RetakenPostAddsNothing` compares against the settled sample immediately
  before the walk-through**, not against a board text remembered from the
  reopening. Same claim, no bookkeeping, and it works wherever in the day the step
  falls — which matters now that the walk-through is in a different stretch in
  different days.
- **Schedule**: 78 checkpoints at 6 s plus a sentinel at 480 s (was 60 + 420), for
  eleven walked steps and three rebuilds instead of nine and two.
- **`GradeWarmReopen` + `GradeColdReopen` collapsed into one `GradeReopen`.** The
  three questions asked at a reopening are the same three every time; only the
  answer the record gives differs. Gate names are chosen by kind: warm keeps the
  three original names, rewind is `PutBackRecordRulesTheYard`, cold is
  `ColdReopenForgetsEverything`.
- **`author_map.py` gained `check_day`**, which re-runs every one of
  `BuildDayTrace`'s refusals over all three staged days in pure Python before the
  level is saved. A table typo is now caught at authoring time instead of as a
  HARNESS-PRECONDITION in the middle of a graded run.
- **The reference needs no change.** `UYardMemorySubsystem::ReadRecord` goes to
  disk on every single call and caches nothing, so a rewound record is simply read
  and followed. That discipline — which the reference already had, and which the
  old fixture could not distinguish from a token — is now the thing the task
  measures.

### Re-verified offline, 2026-08-19 (no editor, no build)

`author_map.py`'s `check_day` + `check_geometry` were executed against a stubbed
`unreal` module after the rework:

- all three staged days pass every one of `BuildDayTrace`'s refusals;
- the simulated board values are `[0,12,28,33,33,44,12,25,0,16]` (day 0),
  `[0,15,21,25,15,27,0,3,3,10]` (day 1), `[0,13,24,41,0,16,16,31,13,29]` (day 2),
  matching the tables printed in `task.md` step for step;
- the phase slices are `(0,5)(5,3)(8,2)(10,1)` for days 0 and 1 and
  `(0,5)(5,2)(7,3)(10,1)` for day 2 — eleven walked steps each;
- **93 routes** simulated (3 days x 4 stretches x every plausible set-down) at all
  four slot rotations 0/1/2/4, worst clearance 700 uu to a prop (need 250),
  1,082 uu to a board (need 200), 400 uu to a wall;
- the decoys still disagree with all **twelve** staged rounds.

None of that touches the C++. **`MemoryYardFunctionalTest.cpp` has never been
compiled**, and the rework added ~450 lines to it.

## What is still open (for the build stage)

- **THE BLOCKER, and it gates everything else in this list.** The `.umap` does not
  exist, so `map_locator.locate_map` returns None and **every** submission — the
  reference included — comes back HARNESS-ERROR, not graded. `tasklint` on this
  spec reports exactly one ERROR and it is this one. Authoring it needs a built
  editor (the script resolves `MemoryYardFunctionalTest` by name), which is the
  orchestrator's lane; the command is below.
- **The 2026-08-19 rework added ~450 lines of never-compiled C++**, including two
  new file-system helpers (`SnapshotDurableStores` / `RestoreDurableStores`), a
  rewritten `BuildDayTrace` that simulates a per-set script, a merged `GradeReopen`,
  and a third rebuild. The offline validator covered the arithmetic and the
  geometry, not one line of the C++. Specific things to watch on the first build
  and the first run are listed at the end of `discrimination/MATRIX.md`.
- **The fixture has LANDED** since this file was first written:
  `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/t3-the-yard-remembers-after-you-leave/MemoryYardFunctionalTest.{h,cpp}`.
  It stages by reflection (`FindFProperty` on `WorthNow`, `PostId`, `PadId`,
  `PadOrder`, `YardName`), reads a display by parsing the rendered `FText` for a
  NAMED TOKEN (`banked <N>`, `worth <W>`) rather than by matching a whole string,
  resolves the pillar and the lamp by component `FName`, and respawns via
  `SpawnActorDeferred<AActor>(DestroyedActor->GetClass(), ...,
  ESpawnActorScaleMethod::OverrideRootScale)` so a subclassed prop survives the
  rebuild. All of that lines up with the scaffold and the reference as shipped, in
  both directions — checked name by name.
- **`authoring/author_map.py` has LANDED**; the `.umap` it authors has NOT.
  `Content/Maps/t3-the-yard-remembers-after-you-leave/L_MemoryYard.umap` still does
  not exist, because authoring it means running the headless editor and nothing in
  this repository was built or run while this task was authored. Until it lands,
  `tasklint` ERRORs on `map-binary-exists` and the L2 leg has no world. The one
  command, and it needs the ThirdPerson module BUILT first (the script resolves
  `unreal.MemoryPostActor`, `MemoryPadActor`, `MemoryBoardActor` and
  `MemoryYardFunctionalTest` by name and fails loudly if the module is not built):

  ```
  UnrealEditor-Cmd.exe <ThirdPerson.uproject> -run=pythonscript \
      -script="<abs path>/authoring/author_map.py" -nullrhi -unattended -nopause \
      -log -stdout -FullStdOutLogOutput
  ```

  `L_MemoryYard` was verified unique across the repo (`git ls-files |
  grep -i memoryyard` → 0 matches), so `DuplicateMapBasenameError` (exit 7) cannot
  trip.
- **The geometry claims are now solved, but still not run.** Every clearance in this
  file and in `task.md`'s table is computed by `check_geometry`, which was executed
  offline against a stub `unreal` module (14 negative mutations, all refused; re-run
  2026-08-19 after the three-rebuild rework) -- but
  no clearance has been MEASURED in a live world, and no character has walked this
  yard. The two numbers most worth reading off the first calib log are the walk's
  wall-clock length (predicted ~160 s against a 480 s sentinel) and whether the
  runner ever stops short of a Kind-1 waypoint's 35 uu tolerance.
- `cameras.json` **is now shipped** (seven poses, five of them distinct). Its
  framing rule is written into the plan's own notes: a shot has to contain a
  counter board AND the posts together, because the graded quantity is that the
  board's number and the set of missing posts agree while the numbers over the
  posts have changed underneath both — a close-up of a board reading 33 proves
  nothing, since every wrong answer in the anti-gaming list produces a plausible
  single board. `the-posts-before` / `the-posts-after` / `the-cold-yard` are the
  SAME pose at three phases of the day so a reviewer can flick between them, and
  `both-yards-across-the-wall` puts the in-scene negative control in the same frame
  as the near yard. Poses were RE-SOLVED on the row layout `author_map.py` builds
  (the earlier ones were computed against the grid table that turned out to be
  unwalkable) and each was checked by computing the horizontal half-angle from the
  camera to the near board and to both ends of the post row; **not
  pixel-validated**, because nothing was run.
- **A schema finding, reported rather than copied:**
  the camera-plan loader rejected unrecognised top-level keys,
  and the shipped `cameras.json` therefore
  **fails to load** — it carries a `"pixel_validated": false` key the schema does
  not recognise (recognised: `camera_plan`, `task_id`, `authored_by`, `notes`,
  `shots`, `pie_timeline`, `editor_stills`, `flythrough`). This plan states its
  un-validated status in `notes` instead, and loads clean. Fixing the shop's plan is
  a one-key edit in another task's folder, so it is left for whoever owns that
  task.
- `discrimination/MATRIX.md` **is now shipped** and clears `tasklint`'s
  `discrimination-required` WARN. Per the owner directive of 2026-08-18 there are
  **no variant legs** on this task -- discrimination is reference + empty only -- so
  it holds those two legs plus the coverage argument, and every cell in it is marked
  PREDICTED. Both substrings were re-verified verbatim against the fixture's
  literals, and the empty leg's determinism argument was re-checked in the source:
  the first four visits carry `EGate::None`, and inside `SessionTallyTracksExactly`
  the board is compared before the standing set and before the lamps, with a comment
  in the fixture saying so.
- `docs/MAPS.md` needs its inventory row when the map lands.
- Nothing here has been compiled. The C++ was written against the shipped shop
  and alarm scaffolds and re-checked by eye for the four traps this repo has
  logged (scaled roots, a local named `Role`, wall-clock random seeds, the
  most-vexing parse), but L1 is the orchestrator's to run.
