---
id: t3-hold-the-marks-in-the-order-given
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: Architecture & Systems
category: gameplay
layers: [L1, L2]
fixtures: ["L_MarkOrder :: AMarkOrderFunctionalTest"]
fps_legs: [60, 20]
---

# t3-hold-the-marks-in-the-order-given

A striped hall with five painted rings on the floor and a duty board on the wall.
Each ring banks **occupancy time** — second for second while somebody stands in
it, paused (not emptied) when they step off, carried on from where it stopped
when they step back on, and finished against **its own** number of seconds *as
that number reads at that moment*. The board says which rings, **in what order**,
and only the ring whose turn it is banks anything at all: step onto another ring
the board names and the whole hall wipes there and then.

> **Built against the 2026-08-18 difficulty bar.** Two subsystems that genuinely
> interact in both directions (the order gates the banking; a wrong step or a new
> list destroys every bank; a completed bank is what moves the order on); and
> every load-bearing number — the list, its length, and each mark's seconds —
> read off placed actors at the moment of use, all of them re-written mid-run and
> none of them derivable.
>
> **Four locally-reasonable wrong answers, each caught by a NAMED gate.** Judge
> the declared order **at completion** instead of **at the step** (it compiles,
> it reads right, and it completes a clean run identically). Treat only an
> **already finished** mark as out of turn, so stepping *ahead* onto a name
> nobody has touched banks on. Nest the **completion test inside the banking
> step**, so a number dropped below its bank can never finish a mark with nobody
> standing there. Detect a new list by its **length** (or its first name, or its
> set of names) rather than by its order. The last three were each ungated until
> 2026-08-19 and each produced byte-identical output for the whole run; the drive
> now stages every one of them twice, and the run-level gate refuses to certify a
> run in which any of those branches went unjudged.

## Primary concept

- `state-tree` — an ordered machine whose current step decides what the world's
  inputs mean, and whose steps arrive as data at run time
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/state-tree-in-unreal-engine)

The load-bearing behaviour is **a data-driven ordered sequence sitting on top of
per-subject occupancy accumulators, where the sequence decides which accumulator
is allowed to run and any out-of-sequence contact destroys all of them.** The
grade never asks *how*: an `int32` cursor and a `TMap`, a queue of structs, one
state machine per mark, a component, or an actual StateTree all pass identically,
as long as the hall settles inside the half second the prompt promises.

## Composed concepts

| Concept | Why it is load-bearing here |
|---|---|
| `actor-lifecycle` (https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-actor-lifecycle) | The hall is **staged after `BeginPlay`** and re-staged again mid-run. Anything read once at play — the list, its length, a mark's seconds — is already wrong at the first graded checkpoint. |
| `ps-timers` (https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-timers-in-unreal-engine) | Banking is game-time that must pause and resume without loss, and finish against a threshold that can move under it in both directions. The task runs at 60 Hz **and** 20 Hz, so a frame-counted clock fires at the wrong wall time. |
| `ps-hud` (https://dev.epicgames.com/documentation/en-us/unreal-engine/user-interfaces-and-huds-in-unreal-engine) | Nothing private is ever graded. Every scored number is read off a face somebody can stand in the hall and read, or off a lamp they can see burning. |
| `ps-strings` (https://dev.epicgames.com/documentation/en-us/unreal-engine/string-handling-in-unreal-engine) | Marks are identified **by name**, never by index, placement or discovery order — the board names them and the set it names changes mid-run. |

**Production pattern, not an invented combination.** This is the standard
*ordered control-point round*: a capture meter that accrues only while its point
is occupied and **pauses rather than resets** when it is vacated (every
king-of-the-hill / control-point mode ships this), driven by a **rotation** —
a data-authored ordered objective list that resets on an out-of-order
interaction, which is how objective rounds, tutorial gates and time-trial
checkpoint sequences are built. The two are always coupled in shipped code
exactly the way they are coupled here: the rotation decides which meter is live,
and a meter completing is what advances the rotation.

## Prompt given to the agent

> The hall has five marks painted on its floor and a duty board on the wall.
> Every mark carries its own name and its own number of seconds — how long
> somebody has to stand on it. The board names some of those marks, in an order.
> The round is simple to say: stand on the marks the board names, one at a time,
> in the order the board gives them, each for its own number of seconds. When the
> last name on the list is finished, the round is done.
>
> **Standing on a mark** means the character the player controls is inside that
> mark's ring — a circle of radius 150 cm around the mark's centre, as painted on
> the floor. The hall is flat and **height plays no part**: measure from the
> mark's centre to where the character is standing, and exactly on the ring still
> counts as on. No two marks are within 500 cm of each other, so the character is
> never on two marks at once.
>
> **Banking time.** While the character stands on the mark whose turn it is, that
> mark banks time, second for second. **Stepping off pauses that bank; it does
> not empty it.** Step back on and it carries on from the value it stopped at.
> Stepping back onto the mark whose turn it is, however many times, is never out
> of turn.
>
> **Finishing a mark.** A mark is finished the moment its bank has reached its
> own number of seconds. The numbers on the marks can be changed at any time,
> including while somebody is standing on one: a mark is finished as soon as its
> bank has reached whatever its number says **at that moment**, so a number
> raised mid-stand means standing longer, and a number dropped below what is
> already banked finishes the mark at once — **even with nobody standing on it,
> and nobody standing anywhere**. When a mark finishes, the turn moves on to the
> next name on the list.
>
> **The order is the board's, not yours.** Only the mark whose turn it is banks
> anything. Stepping onto any other mark the board names — one that comes later
> in the list, **including one nobody has stood on yet**, or one already
> finished — starts the whole round over at that moment: every named mark's bank
> empties to zero, every named mark goes dark, and the turn goes back to the
> first name on the list. It is the step onto the mark that does this, not what
> happens afterwards, and **a mark stepped on out of turn banks nothing at all**,
> however long anybody stands on it.
>
> **A mark the board does not name is not part of tonight's round.** Standing on
> it banks nothing, lights nothing and disturbs nothing: it never starts the
> round over, and it leaves every other mark's bank exactly as it was.
>
> **What the hall shows.** These are the only things anybody outside can see, and
> they are what the work is judged on. The hall already owns the wording of both
> faces and the switch behind every lamp — what none of it has is anybody
> deciding *when*, or with *what numbers*, to write them.
>
> - **Each mark's face** reads its own banked seconds and its own number, one
>   decimal each, with a slash between: `0.0/4.0` at the start of a round,
>   `1.4/4.0` part way through, `4.0/4.0` when it is finished. The two numbers
>   are yours; the wording around them is the hall's.
> - **Each mark's lamp** is dark — brightness 0 — until that mark is finished,
>   and at least 5000 bright from the moment it finishes until the round starts
>   over.
> - **The board's tally face** reads how many of the board's marks are finished,
>   out of how many names the board is carrying: `0/4` when a round begins, `1/4`
>   after the first, `4/4` when the round is done. It must never read the full
>   count before the last name on the list has been finished in its turn.
> - A finished mark keeps its lamp lit and its face standing at its own number
>   until the round starts over.
>
> **Nothing is announced.** The board's list can be changed at any time — a
> different order, a different set of names, a different number of names — and so
> can the numbers written on the marks. **The same names in a different order is
> a different list**, and so is a list of the same length. Nothing tells you when
> it happens.
> Whatever the board and the marks read at the moment you need them is what they
> say; a number read once and kept will be wrong before the night is out. **When
> the board's list changes the round starts over:** every bank empties, every
> lamp goes dark, and the tally face reads zero out of however many names the new
> list carries.
>
> The hall has **half a second** to catch up after anything changes, and a mark's
> face may sit up to **a quarter of a second** behind the true bank.
>
> None of this is one-shot. A round that has been finished has to be able to
> happen again, and again, as many times as the night calls for.
>
> All of it is driven by the character walking — there are no key presses
> anywhere in this.
>
> The hall is not yours to rearrange. Do not move the marks or the board, do not
> add or remove either, and do not change any number written on them: a mark's
> name, its number of seconds, the size of its ring, or the board's list.
> Everything the hall needs in order to *show* its state is already built and
> working — every mark has a face and a switch for its lamp, and the board has a
> face — and nothing decides when to write any of it. Because the hall itself is
> fixed, whatever does the deciding has to live on something already standing in
> it: a mark, the board, or the character.
>
> Write your solution in C++ under `Source/ThirdPerson/`. Do not edit the level,
> any config file, or any test file.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on
this substrate). `Source/CraftBenchTests/` is deny-listed and a submission file
under it is a SANDBOX-REJECT (exit 4), not a graded FAIL; so are
`Content/Maps/`, `Content/ThirdPerson/`, `Content/Characters/` and every
`Config/` file (no `config_allow` is declared by this task).

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t3-hold-the-marks-in-the-order-given/FloorMarkActor.h` / `.cpp` —
  `class THIRDPERSON_API AFloorMarkActor : public AActor`, tagged `HallMark`.
  Five of them stand in the hall. Supplied and **working**:
  - An **un-scaled `USceneComponent` root**, with the ring, the mast, the lamp
    and the two text faces sized individually beneath it. (Not a scaled mesh
    root: a scaled root multiplies both a child's offset *and* its own extent,
    which is how a 120 x 120 pad once became 840 x 960 in mid-air.) The mark's
    **centre is the actor's location**.
  - `UPROPERTY(EditAnywhere, BlueprintReadOnly) FName MarkName`,
    `float RequiredSeconds`, `float RingRadiusUu` — **read them off the mark you
    are dealing with; the five marks are not set alike, and the hall re-writes
    some of these part way through the night.**
  - `Ring` — the circle painted on the floor, sized from `RingRadiusUu` in
    `OnConstruction`, so what a person sees and what the hall means are the same
    circle. **Non-colliding on every channel**: it is paint, not a trigger.
  - `UFUNCTION(BlueprintPure) bool IsInsideRing(const FVector&) const` — the
    disclosed predicate, exactly: flat, mark centre to the point, `<=` the
    radius. Supplied so everybody in the hall means the same thing by *standing
    on it*.
  - `UFUNCTION(BlueprintCallable) void ShowBank(float BankedSeconds, float
    RequiredSecondsShown)` — **the face.** Writes `"<banked>/<required>"` to one
    decimal each and mirrors both into `LastShownBankedSeconds` /
    `LastShownRequiredSeconds` / `bFaceEverWritten` in the same breath, so what a
    reviewer reads off the glass and what a tool reads off the actor are the same
    numbers by construction. **Ships blank.**
  - `UFUNCTION(BlueprintCallable) void SetLampLit(bool)` and
    `UFUNCTION(BlueprintPure) bool IsLampLit() const` — the lamp on the mast.
    Lit is 6500 intensity, dark is 0. **Ships dark.**
  - A `Tick` that does exactly one thing: keeps the name plate reading whatever
    `MarkName` currently says.
  - **No clock, no progress, no idea of whose turn it is, and no reference to the
    board or to anybody walking about.**
- `Tasks/t3-hold-the-marks-in-the-order-given/DutyBoardActor.h` / `.cpp` —
  `ADutyBoardActor`, tagged `DutyBoard`. **A list, a tally face and nothing
  else.** Supplied:
  - `UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<FName> ListedMarkNames` —
    tonight's list, in order, by mark name. It can be replaced at any time.
  - `OrderFace` — the board paints its **own** list here, self-driven from
    `ListedMarkNames` every frame, so a person standing in the hall can read the
    round. It is presentation only and it never touches the tally.
  - `UFUNCTION(BlueprintCallable) void ShowTally(int32 FinishedCount, int32
    ListLength)` — **the tally face.** Writes `"<finished>/<length>"` and mirrors
    both into `LastShownFinished` / `LastShownListLength` /
    `bTallyEverWritten`. **Ships blank.**
  - No progress of its own, no cursor, no bank, and no reference to a mark or to
    the character.
- `Content/Maps/t3-hold-the-marks-in-the-order-given/L_MarkOrder.umap` — the
  staged hall, committed binary. **World Settings name NO game mode**, so the
  level inherits `BP_ThirdPersonGameMode` and its
  `BP_ThirdPersonPlayerController` (which carries `IMC_Default`) — the map is
  controllable with WASD by a person, not merely by the fixture. What is in it:

  | Element | Placement | Notes |
  |---|---|---|
  | Floor | 8,000 x 8,000, striped every 200 cm, stripes **non-colliding** | distance and pace readable by eye |
  | Five `AFloorMarkActor`s | three along the near row, two along the far row; the closest pair is **exactly 500 cm** centre to centre, every other pair further | against a 150 cm ring, so nobody is ever on two at once |
  | One `ADutyBoardActor` | on the wall at the open end, facing the hall, **non-colliding** | both its faces read from the whole floor |
  | PlayerStart | on the floor, clear of every ring by more than 300 cm, facing the marks | |
  | Backdrop + landmarks | a low back wall and two differently sized posts, **non-colliding** | a moving camera is distinguishable from a still one |
  | Fixture | one placed `AMarkOrderFunctionalTest` | |

  **Everything except the floor is non-colliding**, so nothing in the hall can
  block or deflect the walk. **The marks' names, their numbers of seconds and the
  board's list are deliberately NOT in this section.** They are readable in the
  level, on the things themselves — and what a mark or the board happens to read
  when the level is opened is only what it read at that moment. The hall
  re-writes those numbers, and that list, while it runs; nothing announces it.

- `cameras.json` (the camera-plan lane; not part of this release) is **not** content and is **not** committed yet: per
  the retired camera-plan convention it lived beside this spec at
  `cameras.json`, it is presentation-only and
  non-gating, and it frames all five marks and the board in one shot.

Files that **do not exist**:

- No occupancy test, no bank, no cursor, no order, no round, no code that writes
  a face, throws a lamp or writes the tally; no Blueprint subclass; no level
  edits. The empty submission compiles (L1 green) and FAILs L2 at the **baseline
  checkpoint**, because the board's tally face ships blank and a round that has
  begun reads `0/4`.
- No test source in the agent's writable path. `AMarkOrderFunctionalTest` lives
  in the `CraftBenchTests` module the agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t3-hold-the-marks-in-the-order-given/L_MarkOrder.umap` on the
**ThirdPerson** substrate, ticked at a fixed deterministic step
(`-deterministic -FPS=<rate>`), **twice**: once at 60 and once at 20
(`fps_legs: [60, 20]`), each in its own PIE process. The whole task is an
integral of game time, so a per-frame accumulator that adds a constant instead of
`DeltaSeconds` lands on the right answer at one rate and is 3x wrong at the
other.

Verification primitive: **pie-checkpoint-sampling** plus an every-frame readback
of the two mirrored face values on each mark, each mark's **point-light
intensity**, and the two mirrored tally values on the board — i.e. exactly what a
person standing in the hall reads — compared against the fixture's own running
model of the whole rule, driven over a Tier-1 locomotion route
(`AddMovementInput`, the same path a human drives with WASD; there is not one key
press anywhere in this task).

### The fixture runs the same rule

Every frame the fixture re-reads, **live and by tag**: the board's
`ListedMarkNames`, and every mark's `MarkName`, `RequiredSeconds`,
`RingRadiusUu` and world location. It then steps its own model with the same
disclosed predicate (flat, mark centre to the **player pawn's actor location**,
`<=` radius, inclusive), the same pause-and-resume banking, the same
finish-against-the-live-number rule, the same step-onto wipe, the same inert
unlisted mark and the same restart-on-a-new-list. Every gate compares what the
hall **shows** against that model. The model's own numbers are never compared to
anything inside the submission — they could not be.

### Per-run staging (why nothing can be hard-coded)

| Moment | What the fixture stages |
|---|---|
| `PrepareTest` (**after** every `BeginPlay`) | Writes **round 1**: each mark's `RequiredSeconds` from its own table, and the board's list — **four** names, in an order that matches neither the marks' name order, nor their placement order, nor their number order. The committed `.umap` carries a **two-name** list and a different set of seconds, so a submission that snapshots either at `BeginPlay` reads `0/2` at the baseline checkpoint and is already wrong. |
| mid-stand, round 1 | **Raises** one listed mark's `RequiredSeconds` while the character is banking on it (that stand must get longer). |
| mid-stand, round 1 | **Drops** a different listed mark's `RequiredSeconds` **below the value it has already banked** while the character is standing on it (that mark must finish at once). No value cached at entry can produce either. |
| **parked, round 1** | **Drops the mark whose turn it is below its already-banked value while the character is standing clear of every ring.** That mark must finish **with nobody moving and nobody anywhere** — lamp lit, tally up by one, face at its own new number. This is the one staging a completion test nested inside "somebody is standing here and banking" cannot produce at all; every other completion in the run happens under somebody's feet. |
| the shift change, mid-stand | Replaces the board's list with **three** names — a different order, a different subset (one round-1 mark is **demoted to unlisted**) — and re-writes several marks' seconds, **one of them the mark the character is standing on at that instant**. The tally denominator moves from `/4` to `/3`. |
| **parked, round 2** | The second off-mark drop, on the new list's second name. Both halves of the completion rule therefore fire **twice**. |
| **parked, after round 2 is shown finished** | Replaces the board's list a second time — **the same three names, the same first name, the same number of names and every mark's seconds left exactly where they stand, in a different order.** The round starts over anyway. Nothing about this one is visible to a change detector that compares the list's *length*, its *first name*, or the *set* of names it carries, and the round-1-to-round-2 replacement (four names to three) is what makes each of those look right the first time. |
| the whole run | The one **never-named control mark** keeps its own distinct number of seconds from first frame to last, so its face `0.0/<its own number>` cannot be produced by a shared constant either. |

Everything staged is deterministic and identical on the 60 Hz and 20 Hz legs.
**The drive is ADAPTIVE**: every standing phase is *"stay until MY model says
this mark's bank reads X"*, never *"stay for T seconds"* — so a submission's own
accrual rate can never shift the schedule the gates are anchored to.

### The drive

Tier-1 throughout: walk in, walk out, walk across. Waypoints are solved from the
marks' live centres and radii, never written down; every transit is routed so it
enters and leaves a ring **head-on** and clears every non-target ring by at least
120 cm; the parking spot is at least 300 cm outside every ring.

| # | Phase | Until | What it is for |
|---|---|---|---|
| 0 | walk to the parking spot | arrival, then settle | gates off — the character may spawn anywhere |
| 1 | **baseline**, parked | 1.5 s | `TheBoardShowsHowFarYouGot` first armed here; this is the empty-submission FAIL |
| 2 | stand on list[0] | model bank ≈ 40% of its number | banking starts |
| 3 | **step onto list[2] — later in the list, unfinished, never yet the current mark** | 4 s standing | `AWrongStepEmptiesEveryClock`, then `StandingOutOfTurnBanksNothing`. **THE SKIP-AHEAD HALF of the out-of-turn rule**: a mark nobody has ever stood on is still an out-of-turn step, and a submission that only treats an *already finished* mark as out of turn leaves list[0]'s bank standing here |
| 4 | walk back onto list[0] and re-bank | model bank ≈ 40% again | the wipe took that bank with it |
| 5 | walk out to the parking spot and wait | ≥ 6 s | `TheBankHoldsWhileYouAreAway` |
| 6 | walk back onto list[0] | its completion | `TheBankIsStillThereWhenYouComeBack`, then `TheBankPicksUpFromWhereItStopped`; **the mid-stand raise lands here** |
| 7 | cross the control mark's ring | out the far side | `TheUnnamedMarkStaysCold`, crossing 1 of 2 |
| 8 | stand on list[1] | its completion | **the mid-stand drop lands here** — it must finish at once |
| 9 | step onto list[0] — **already finished, out of turn** | 6.5 s standing | the OTHER half of the rule. list[0] is chosen deliberately: after the wipe it is the mark whose turn it is again, which is exactly where "re-evaluate and start banking" goes wrong |
| 10 | walk off, then re-walk list[0] and list[1] in order | tally reads 2/4 | |
| 11 | bank list[2] **part way** and then walk out to the parking spot | the fixture drops its number below that bank | **THE COMPLETION WITH NOBODY ANYWHERE.** `AMarkWaitsForItsOwnNumber` judges it 0.75 s later: lamp lit, tally 3/4, face at its own new number — with the character parked clear of every ring. A completion test nested inside the banking step cannot fire here at all |
| 12 | walk in from the parking spot to list[3] | tally reads 4/4 | round 1 completed |
| 13 | hold | 6 s | a finished mark keeps its lamp and its face |
| 14 | step onto list[0] (out of turn again), step off, step back on | model bank ≈ 2 s | sets up a mid-stand shift change |
| 15 | **the shift change** — fixture replaces the list, mid-stand | 3.2 s | `TheRoundStartsOverWhenTheListChanges`. The character is still standing on that mark, which the **new** list names at position 2 — so it must stop banking and read `0.0/<its new number>` while they stand there, and no wipe may fire, because no step happened |
| 16 | walk to new-list[0] and bank | model bank ≈ 45% of its number | round 2 |
| 17 | **step onto new-list[1] — later in the list, unfinished, never current** | 4 s standing | the second SKIP-AHEAD, on a list the submission was never handed at `BeginPlay` |
| 18 | walk back to new-list[0] and re-bank | model bank ≈ 45% again | |
| 19 | walk out and wait | ≥ 6 s | second `TheBankHoldsWhileYouAreAway` |
| 20 | back on, to completion | tally 1/3 | second pause/resume pair; **the second mid-stand raise lands here** |
| 21 | cross the demoted mark **and** the control mark | out the far side | `TheUnnamedMarkStaysCold` crossing 2 of 2; the demoted mark must now be as inert as the control |
| 22 | bank new-list[1] part way, then step onto new-list[0] | 6.5 s standing | second already-finished out-of-turn step |
| 23 | re-walk new-list[0], then bank new-list[1] **part way** and walk out | the fixture drops its number below that bank | **the second completion with nobody anywhere** |
| 24 | walk in from the parking spot to new-list[2] | tally reads 3/3 | round 2 completed |
| 25 | hold, then **the same-length reorder** — fixture replaces the list a second time while the character is parked | 3.2 s, then the run-level gate | second `TheRoundStartsOverWhenTheListChanges`, on a replacement that keeps the length, the names and the first name. Then `TheHallDidItTwice` |

The fixture walks **38 steps** against these 25 rows, because five of the rows are
several walks and stands (a row that says "re-walk the whole list in order" is
several stands). Every step logs its own label; the mapping lives in `BeginStep`.

Modelled world time ≈ **285 s** — 158 s of walking, measured off the committed
layout by `authoring/author_map.py`, plus ~98 s of standing and ~10% for the
acceleration ramps. The checkpoint schedule is calibration checkpoints every 6 s
out to **348 s** plus a **SENTINEL at 400 s**, because
`ACraftBenchFunctionalTest::Tick` ends the test the moment the last scheduled
checkpoint is sampled. The run-level gate is evaluated when the last phase
completes **and** again at the sentinel, whichever comes first, and only then
does the fixture call `FinishTest(Succeeded)`. (400 s of world time is a measured
anchor, not a guess: `t1-touched-crate-lights-up` ships a 420 s sentinel, runs
its whole schedule and holds a refgate certificate on this substrate.)
Checkpoint points are only ever **appended**: the index is a public key —
`cameras.json`'s `pie_timeline` binds shots to it — so inserting one at the front
would silently re-aim every camera shot, while adding one at the back moves
nothing but the sentinel's index.

### Settle and suppression

Nothing is judged on a frame where any of these hold. Each is a **widening** of
the disclosed contract, never a narrowing:

- less than **0.75 s** since the fixture's own model last changed state (a wipe,
  a list change, a completion, a bank starting or stopping) — 1.5x the half
  second the prompt promises;
- less than **0.35 s** either side of a modelled ring crossing. At 20 Hz a
  ~500 uu/s walk moves 25 cm per frame against a 300 cm ring, so at most one
  frame is genuinely ambiguous; the route enters and leaves head-on and never
  grazes a ring tangentially, so a one-frame difference shifts an edge *time* and
  never an edge *count*;
- the fixture itself is re-staging the hall.

Face values are compared to the model within **0.25 s** — the lag the prompt
promises. One-decimal rounding alone is ±0.05 s, so the working margin is 0.20 s;
**this tolerance is calibrated against the reference at Gate 10 before ship.**

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

**Gate precedence, in the order the fixture evaluates them. At most one of 2-8 is
armed on any judged frame, so a named FAIL is never a race between two gates.**

```text
1   TheHallIsNotYoursToRewire        -- every frame, from the first
2   AWrongStepEmptiesEveryClock      -- 0.75 s to 2.0 s after each out-of-turn step
3   StandingOutOfTurnBanksNothing    -- 2.0 s after that step until they leave it
4   TheRoundStartsOverWhenTheListChanges -- 0.75 s to 2.5 s after each list change
5   TheBankIsStillThereWhenYouComeBack   -- first 0.5 s after each re-entry
6   TheBankPicksUpFromWhereItStopped     -- 0.5 s after re-entry to that completion
7   TheBankHoldsWhileYouAreAway      -- 0.75 s after each exit until re-entry
8   AMarkWaitsForItsOwnNumber        -- +/- 1 s around each modelled completion
9   TheUnnamedMarkStaysCold          -- EVERY judged frame, NEVER suppressed
10  EveryFaceReadsItsOwnBank         -- everywhere else (suppressed inside 2-8)
11  TheBoardShowsHowFarYouGot        -- everywhere else, and FIRST at the baseline
12  EveryLampBurnsOnlyForAFinishedMark -- every judged frame, ALWAYS LAST, and only
                                          once whichever of 2-8 was armed has agreed
13  TheHallDidItTwice                -- once, at drive completion or the sentinel
```

Gates 10 and 11 are suppressed inside every windowed gate's window: they assert
the same facts from a different angle and would otherwise shadow every named
message. **Gates 9 and 12 are never suppressed**, because each is a genuinely
separate channel — the control mark and the lamp row would otherwise be ungraded
on precisely the frames that matter most, and running gate 12 last (and only
where the windowed gate already agreed) gets both: a wrong bank is always named
by the windowed gate, and a right bank with wrong lamps is always named by the
lamp gate. Where 8 overlaps 6, 8 wins.

```text
assert: TheHallIsNotYoursToRewire -- every frame: each mark's MarkName,
        RequiredSeconds and RingRadiusUu, and the board's ListedMarkNames, are
        exactly what the fixture staged for the phase in progress (floats to
        0.1%); each mark's world location is within 2 uu of where the hall put
        it; and the hall still holds exactly five marks and one board. LOAD-
        BEARING, not ceremonial: the fixture's model reads the marks' LIVE
        numbers and the LIVE list, so without this a submission could re-write
        the hall into a shape where every other window is unreachable -- a
        do-nothing pass.

assert: AWrongStepEmptiesEveryClock -- windowed on each out-of-turn entry (the
        character's location crosses inside a listed-but-not-current mark's
        ring): every named mark's face reads 0.0 of its own current number,
        every named mark's lamp is at intensity 0, and the tally reads 0 out of
        the current list length. The message names the mark stepped on, WHICH
        HALF OF THE RULE it exercised, the mark whose turn it was, and every
        bank found still standing. THIS is the gate that catches a wipe scoped
        to the offending mark only, and a wipe deferred to completion (the
        primary wrong answer).
        BOTH HALVES OF THE RULE ARE DRIVEN, TWICE EACH, and counted separately:
        two SKIP-AHEAD steps onto a mark that sits LATER in the list, is
        unfinished, and has never been the current mark; and three steps onto a
        mark ALREADY FINISHED. A rule with two branches whose drive only ever
        exercises one of them is an ungated rule, however loudly the prompt
        states it -- and the skip-ahead branch is the one a model is likelier to
        get wrong, because it needs the realisation that a mark nobody has ever
        touched can still be an out-of-turn step. The run-level gate demands two
        judged windows of EACH.

assert: StandingOutOfTurnBanksNothing -- windowed for the whole 4 s to 6.5 s the
        drive deliberately remains standing on that mark after the wipe: its
        face stays at 0.0 of its own number (within 0.25 s), its lamp stays at
        0, and the tally stays at 0. Independent of the gate above: an
        implementation may wipe correctly at the step and then treat the mark it
        is standing on as the new current one -- which is exactly what "reset
        the round and re-evaluate" does, since two of the drive's out-of-turn
        steps land on the mark that IS first on the list.
        Both this gate and the one above are claims about THE STAND the
        out-of-turn step began, so both stand down the moment the character
        steps off. That is enforced by clearing the armed state in the same
        place the poisoned stand is cleared, and re-checked inside each gate:
        leaving it armed made every LATER legitimate stand on the same mark look
        like a continuation of the poisoned one, which false-FAILed a correct
        submission four separate times and also silently un-graded the per-mark
        face channel for the whole of those stands.

assert: TheBankIsStillThereWhenYouComeBack -- windowed on the first 0.5 s after
        each re-entry onto the current mark: the face reads AT LEAST the value
        it held at the instant of stepping off, less the 0.25 s tolerance. A
        one-sided bound on purpose -- legitimate accrual inside the window is
        the other gate's business, and this gate's whole claim is "it did not
        empty". Fires at least twice (once per round). This is what separates
        PAUSE from RESET-ON-EXIT, the wrong answer the corpus row was written
        against.

assert: TheBankPicksUpFromWhereItStopped -- windowed from 0.5 s after re-entry
        to that mark's completion: the face equals the preserved value plus the
        modelled inside-ring seconds since re-entry, within 0.25 s. Catches an
        implementation that preserves the number for DISPLAY but restarts the
        accrual from zero, and one that double-counts the paused interval.

assert: TheBankHoldsWhileYouAreAway -- windowed over each off-mark wait (>= 6 s,
        parked outside every ring by a margin): the partially-banked mark's face
        changes by no more than 0.25 s across the whole wait, and no other named
        mark's face moves at all. Kept SEPARATE from the re-entry gate
        deliberately: an implementation that RESETS on exit passes freeze (zero
        does not move) and fails preservation, and the two messages say
        different things.

assert: AMarkWaitsForItsOwnNumber -- windowed +/- 1 s around each modelled
        completion: the mark's lamp goes 0 -> >= 5000 and the tally rises by
        exactly one, at the moment its bank reaches THAT mark's own number as it
        reads AT THAT INSTANT -- not before, not a shared constant, and not the
        value cached when the stand began. The fixture raises one mark's number
        mid-stand and drops another below its already-banked value mid-stand, so
        no cached-at-entry required-value can produce both. The message names the
        mark, its number then and now, its bank, and the tally found.
        TWICE IN THE RUN THE COMPLETION HAS TO FIRE WITH NOBODY IN ANY RING. The
        drive banks the mark whose turn it is part way, walks all the way out to
        the parking spot, and only there does the fixture drop that mark's
        number below what it has already banked. The mark must finish AT ONCE --
        lamp lit, tally up by one, face at its own new number -- with nobody
        standing anywhere. This is the ONLY thing in the run that separates a
        finish test run every frame from one nested inside "somebody is standing
        here and banking", because every other completion in the drive happens
        under somebody's feet; the message says so in as many words when it
        fires, and the run-level gate demands two of them.

assert: TheRoundStartsOverWhenTheListChanges -- windowed 0.75 s to 2.5 s after
        EACH of the two list replacements: every mark's face reads 0.0 of its
        NEW number, every lamp is at 0, and the tally reads 0 out of the NEW
        list length. Catches a list read once at BeginPlay, a tally denominator
        compiled as a constant, and a completed round that latches. On the FIRST
        replacement (four names to three, mid-stand) the character is standing
        on a listed-but-not-current mark throughout the window, so it also
        catches "whatever I am standing on is the current mark".
        THE SECOND REPLACEMENT KEEPS THE LENGTH, THE NAMES, THE FIRST NAME AND
        EVERY MARK'S SECONDS, and moves only the order, with the character
        parked. It is what separates a real order-sensitive comparison from a
        detector that watches the list's LENGTH, or its FIRST name, or the SET
        of names it carries -- each of which is a locally reasonable reading of
        "the board's list can be changed at any time", and each of which fires
        correctly on the first replacement and sees nothing at all here. The
        staging refuses to run if that second list differs in anything but
        order.

assert: TheUnnamedMarkStaysCold -- IN-SCENE NEGATIVE CONTROL, gauged at EVERY
        judged frame and never suppressed: the one mark that NEITHER list ever
        names -- same class, same 150 cm ring, 500 cm from a listed mark, in the
        same camera frame -- reads 0.0 of its own number, sits at intensity 0,
        and the two crossings the route makes through its ring change no other
        mark's bank, no lamp and no tally. Catches the plausible reading that
        any mark other than the current one is an out-of-turn step.

assert: EveryFaceReadsItsOwnBank -- the everywhere-else PER-MARK channel, on
        every judged frame outside a windowed gate: each mark's face reads
        <banked>/<required> to one decimal each; the banked half equals the
        fixture's own model for THAT mark within 0.25 s and the required half
        equals THAT mark's own current number; and a finished mark's face stands
        at its number until the round starts over. A face never written at all
        (bFaceEverWritten false) is an AGENT FAIL named here, never a harness
        exit.

assert: TheBoardShowsHowFarYouGot -- the everywhere-else HALL channel, on every
        judged frame outside a windowed gate, and the FIRST gate armed at the
        baseline checkpoint: the tally reads <finished>/<list length> and equals
        the model's count of marks finished in the current attempt over the
        CURRENT list length. Subsumes the anti-premature-win claim: it can only
        read the full count once the last name has been finished in its turn.

assert: EveryLampBurnsOnlyForAFinishedMark -- INDEPENDENT CHANNEL, evaluated
        LAST on every judged frame and only once whichever windowed gate was
        armed has already agreed: the set of lamps at intensity >= 5000 is
        exactly the set of marks the model has finished in the current attempt,
        every other lamp at 0, read from the light component itself (visible,
        not hidden), never from a flag. Kept unsuppressed so a correct tally
        with wrong lamps is still named.

assert: TheHallDidItTwice -- run-level, at drive completion or the sentinel: the
        tally reached the full list length in BOTH rounds and returned to zero in
        between, and each of the pause/resume, out-of-turn-wipe, list-change and
        completion triggers fired at least twice with the same measured outcome
        -- AND SO DID EACH BRANCH OF EACH: two out-of-turn steps onto a name not
        due yet, two onto a name already finished, two completions with nobody
        standing anywhere, and two list replacements. A one-shot latch can only
        complete once; a round that never restarts never reaches the second full
        count; and a branch the drive never produced is a HARNESS fault, named
        with its own short count, never a model's.
```

**Staging faults are attributed, not scored.** Any of these ends the run as
`HARNESS-PRECONDITION`, never as a model failure: fewer or more than five marks
resolving by tag, or other than one board; any pair of mark centres closer than
500 cm; any mark whose `RingRadiusUu` is not 150; any two marks whose
`RequiredSeconds` are within 0.5 s of each other at any staged moment; duplicate
`MarkName`s, or a listed name that no mark carries; a route waypoint that fails
to clear every non-target ring by 120 cm, or a parking spot within 300 cm of any
ring; an off-mark drop that is not clear of the bank it is meant to complete by
0.5 s; or a phase that overruns its derived deadline.

The three staged lists carry their own preconditions, because each one is
load-bearing in a different direction. The first two must differ in **both**
order and length — the tally's right-hand number is graded. The third must differ
from the second in **order only**: same length, same names, same first name, and
no mark's seconds may move (three marks are finished when it lands, and whether a
finished mark comes undone when its own number moves under it is a corner no
prompt sentence settles). A reorder that quietly changed any of those would test
nothing the first replacement did not already test, so it is refused rather than
run.

**A harness exit can never launder a FAIL.** Before any deadline or sentinel
overrun is written off as a staging fault, `TheHallIsNotYoursToRewire`,
`TheUnnamedMarkStaysCold` and `EveryLampBurnsOnlyForAFinishedMark` are re-checked
**unconditionally** — every adaptive phase ends on a condition the *submission's*
own output has to reach, so a hall that never advances must be a graded FAIL and
not an uncredited harness exit.

## Requirement-to-assertion map

| Prompt requirement | Gate that checks it | When that gate does NOT run |
| --- | --- | --- |
| inside a 150 cm ring, flat, inclusive at the edge | the fixture's model uses exactly that predicate, and the marks ship it as `IsInsideRing`; any other one banks on different frames and diverges | never |
| banks second for second while stood on the current mark | `TheBankPicksUpFromWhereItStopped` and `EveryFaceReadsItsOwnBank` | inside another windowed gate |
| stepping off **pauses**, it does not empty | `TheBankHoldsWhileYouAreAway` | outside the two off-mark waits |
| stepping back on **carries on from** the paused value | `TheBankIsStillThereWhenYouComeBack` (it did not empty) + `TheBankPicksUpFromWhereItStopped` (it resumed, and did not double-count) | outside the two re-entries |
| finished when the bank reaches **its own** number, **as it reads at that moment** | `AMarkWaitsForItsOwnNumber`, once per completion, with a raise and a drop staged mid-stand | more than 1 s from a completion |
| a number dropped below the bank finishes the mark **even with nobody standing on it, and nobody standing anywhere** | `AMarkWaitsForItsOwnNumber`, on the two off-mark drops the fixture stages while the character is parked clear of every ring; the run-level gate demands both | never — every other completion in the drive happens under somebody's feet, which is exactly why these two exist |
| only the mark whose turn it is banks anything | `StandingOutOfTurnBanksNothing` and, everywhere else, `EveryFaceReadsItsOwnBank` | — |
| a step onto another **listed** mark starts the whole round over **at that moment** | `AWrongStepEmptiesEveryClock` | outside the five out-of-turn windows, and once the character has stepped off the mark |
| a mark **later in the list, that nobody has stood on yet**, is an out-of-turn step | `AWrongStepEmptiesEveryClock` on the two SKIP-AHEAD phases, counted separately from the already-finished ones and demanded twice by the run-level gate | as above |
| a mark **already finished** is an out-of-turn step | the same gate on the three already-finished phases, also counted separately and demanded twice | as above |
| a mark stepped on out of turn banks nothing however long you stand | `StandingOutOfTurnBanksNothing` | as above |
| re-stepping the **current** mark is never out of turn | the model does not wipe there; a submission that does fails `EveryFaceReadsItsOwnBank` and `TheBoardShowsHowFarYouGot` on the next frame judged | frames the settle rule suppresses |
| an **unlisted** mark is inert | `TheUnnamedMarkStaysCold`, every frame | never |
| lamp dark until finished, >= 5000 after | `EveryLampBurnsOnlyForAFinishedMark`, every judged frame | only on a frame where a windowed gate already failed |
| the tally is finished-out-of-list-length | `TheBoardShowsHowFarYouGot` | inside a windowed gate's window, where that gate asserts the same fact |
| it never reads the full count early | `TheBoardShowsHowFarYouGot` (it is an equality against the model, so early is as wrong as late) | as above |
| a new list starts the round over, with a new length | `TheRoundStartsOverWhenTheListChanges` on the first replacement (four names to three, mid-stand) | outside that window |
| **the same names in a different order is a different list** | the same gate on the second replacement, which keeps the length, the names, the first name and every mark's seconds. This is what separates a real order comparison from a length-, first-name- or set-comparing detector | outside that window |
| the numbers and the list must be read at the point of use | `AMarkWaitsForItsOwnNumber` (mid-stand raise and drop) and `TheRoundStartsOverWhenTheListChanges` (new length) | as above |
| settles within **half a second** | the 0.75 s suppression window, which is 1.5x it | never |
| the face may lag a **quarter of a second** | the 0.25 s comparison tolerance, which is exactly it | never |
| it can do the whole thing again | `TheHallDidItTwice` | judged at drive completion or the sentinel; a run that fails a per-frame gate earlier never reaches it, which is the more useful message |
| do not move the marks or change any number on them | `TheHallIsNotYoursToRewire`, every frame | never |
| C++ under `Source/ThirdPerson/` | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

## Reference solution metadata

- **Files touched**: 2 —
  `Source/ThirdPerson/Tasks/t3-hold-the-marks-in-the-order-given/DutyBoardActor.h`
  and `.cpp`. `FloorMarkActor.{h,cpp}` is untouched, so the reference ships only
  the pair it changed.
- **LOC**: **243 added** across those two files, measured as a diff against the
  shipped scaffold (67 in the header, 176 in the source); 108 of the added lines
  are comment or blank, so ~135 lines of code on top of the supplied board.
- **Senior-dev hours**: **6–9**, the lower half of T3. The code is small; the
  hours go into judgment, not typing:
  1. ~1 h working out that the round is **two coupled machines** rather than one
     — a per-mark bank and a hall-wide cursor — and that the cursor has to gate
     the bank rather than merely read it. The natural first cut banks whatever
     ring you are standing on and checks the order at the end; it compiles, it
     reads right, and it completes a clean run identically.
  2. ~1.5 h on the out-of-turn rule alone: that it fires on the **step**, that it
     empties **every** bank and not just the offending one, that it puts the turn
     back to the **first** name, that the stand it interrupts banks nothing —
     which needs a per-stand flag, because after the wipe the mark you are stood
     on is very often the mark whose turn it now is — and that it has **two
     directions**. "Already finished" is the one that comes to mind; "later in
     the list, and never stood on" is the one that does not, and it is graded
     twice.
  3. ~1.5 h on the completion rule: re-reading the required number **at the
     moment of use** in both directions, and the realisation that the check
     cannot be attached to the banking step, because a number dropped below an
     already-banked value must finish a mark with nobody moving. The drive stages
     exactly that twice, with the character parked clear of every ring, so this
     is a graded distinction rather than a claim.
  4. ~1 h on the list: detecting a replacement without being told, restarting on
     it, and carrying the length through to the tally denominator. The
     replacement is staged twice on purpose: once four names to three, and once
     the same three names, in a different order, with the same first name — so
     the detector has to compare the ORDER and not the length, the head, or the
     set.
  5. ~1.5 h on the reading discipline and the readout: five faces, five lamps and
     a tally that must all agree **every frame**, each from that mark's own
     numbers, plus deciding where the whole thing lives given that the hall is
     fixed and no new class would ever be instantiated.
  6. ~1 h on the corners the prompt settles and a first pass gets wrong anyway:
     the unlisted mark being inert rather than out-of-turn, re-stepping the
     current mark being legal, and a finished mark holding its face and lamp.
- **Why T3 and not a heavy T2**: two subsystems whose coupling runs in both
  directions and is load-bearing in both (getting the bank right and the order
  wrong fails a named gate; getting the order right and the bank wrong fails a
  different one), five interacting rules that each have a plausible wrong
  reading, and three separate live-read disciplines that a cached value breaks.

## Anti-gaming notes

1. **Judge the order at COMPLETION instead of at the STEP.** *Failure mode*: the
   primary wrong answer and the most natural first implementation — let every
   listed mark bank whenever it is occupied, and only check at the end that they
   completed in the declared order. *Defense*: `AWrongStepEmptiesEveryClock`
   (nothing wipes within 2 s of the out-of-turn step; the previously finished
   mark is still lit and the tally still reads 2/4) and
   `StandingOutOfTurnBanksNothing` (the wrong mark's face climbs where it must
   stay flat at 0.0). Note this answer completes a *clean* run byte-identically,
   so nothing but a deliberately dirty route can catch it.
2. **Reset the bank on exit rather than pausing it.** *Failure mode*: the classic
   hold-the-zone bug, and the one the corpus row was written against.
   *Defense*: `TheBankIsStillThereWhenYouComeBack`. Deliberately **not**
   `TheBankHoldsWhileYouAreAway`, which this answer PASSES (zero does not move) —
   that split is why the two gates are separate.
3. **Wipe only the offending mark, or only the progress cursor.** *Failure mode*:
   two ordinary partial readings of "starts the whole round over". *Defense*:
   `AWrongStepEmptiesEveryClock` asserts every named mark's face **and** every
   named lamp **and** the tally in the same window, and its message lists the
   banks it found still standing.
4. **Treat the mark you stepped on out of turn as the new current mark.**
   *Failure mode*: "reset progress, then re-evaluate where I am" — a two-line
   implementation that looks obviously right. *Defense*: two of the drive's
   out-of-turn steps land on the mark that is **first on the list**, so after the
   wipe it is the current one again; `StandingOutOfTurnBanksNothing` watches it
   for 6.5 s and it must not move.

4a. **Count only an ALREADY FINISHED mark as out of turn** — `Idx < Turn` where
   the rule says `Idx != Turn`. *Failure mode*: the most reasonable wrong reading
   in the whole task, and it survives every clean run: "have I done this one
   already?" is the question that comes to mind, and stepping *ahead* onto a mark
   nobody has touched does not feel like breaking an order at all. *Defense*: the
   drive stages **two SKIP-AHEAD steps** — round 1 onto list[2] with list[0] part
   banked, and round 2 onto new-list[1] with new-list[0] part banked. Neither
   mark has ever been the current one. `AWrongStepEmptiesEveryClock` finds the
   part-banked mark's bank still standing 0.75 s later and names it, and the
   run-level gate refuses to certify a run in which fewer than two such windows
   were judged. **This was ungated until 2026-08-19**: every out-of-turn step in
   the drive landed on a mark that was both already finished AND at list index 0,
   so this answer produced byte-identical output for the whole run.

4b. **Nest the completion test inside the banking step.** *Failure mode*: the
   natural place to put it — you have just added `DeltaSeconds` to a bank, so you
   check that bank against its number right there. It is correct for every
   completion that happens under somebody's feet, which is most of them.
   *Defense*: the fixture drops the current mark's number below its already
   banked value **twice, with the character parked clear of every ring**. The
   mark has to finish with nobody standing anywhere, which that implementation
   cannot do at all; `AMarkWaitsForItsOwnNumber` fires 0.75 s later on the dark
   lamp and says in as many words that nobody was standing. **This was also
   ungated until 2026-08-19** — every drop the drive staged landed mid-stand on
   the mark being banked.
5. **Read the list, its length, or a mark's seconds once at `BeginPlay`.**
   *Failure mode*: the obvious optimisation. *Defense*: the hall is staged in
   `PrepareTest`, which runs **after** `BeginPlay` — so a cached list is a
   two-name decoy and fails `TheBoardShowsHowFarYouGot` at the baseline, before
   the character has entered a single ring. The shift change and the two
   mid-stand rewrites close it again later.
6. **Compile the tally denominator as a constant** (or infer the order from mark
   placement, name order, or discovery order). *Failure mode*: pattern-matching
   on "four marks". *Defense*: round 2 carries **three** names in a different
   order, drawn from a different subset;
   `TheRoundStartsOverWhenTheListChanges` names the length found, and the round-1
   list order matches no orderable property of the hall.

6a. **Detect a new list by its LENGTH** (or by its first name, or by the set of
   names). *Failure mode*: "did the board's list change?" answered with
   `Num()`, or with `list[0]`, or with a set compare — each cheaper than an
   ordered comparison and each right about the only replacement the drive used to
   stage. *Defense*: a **second** replacement, while the character is parked,
   that carries the same three names in a different order with the same first
   name and every mark's seconds left where they stand. Only an order-sensitive
   comparison sees it; `TheRoundStartsOverWhenTheListChanges` finds the finished
   round still standing, and the run-level gate demands two judged list-change
   windows. The staging refuses to run unless that second list differs from the
   first in **order only** — otherwise it would be testing what round 2 already
   tested.
7. **Cache a mark's required seconds when the stand begins.** *Failure mode*: an
   ordinary and locally sensible entry-time read. *Defense*:
   `AMarkWaitsForItsOwnNumber` — one number is **raised** mid-stand (the stand
   must get longer) and another is **dropped below its already-banked value**
   mid-stand (that mark must finish at once, with nobody moving). No cached-at-
   entry value satisfies both, and no shared constant satisfies either.
8. **Treat every mark that is not the current one as an out-of-turn step.**
   *Failure mode*: a genuinely plausible reading of "the order is the board's".
   *Defense*: `TheUnnamedMarkStaysCold`, the in-scene negative control, gauged at
   every checkpoint and never suppressed — the route walks straight through its
   ring twice, once per round, and nothing in the hall may move.
9. **Keep a correct internal state and never write a face, a lamp or the tally.**
   *Failure mode*: modelling the round and forgetting the output. *Defense*:
   nothing private is ever graded. The fixture reads the two mirrored face
   values (written only by the supplied `ShowBank`), the point lights' own
   intensity, and the two mirrored tally values (written only by the supplied
   `ShowTally`). The board deliberately carries no other readout.
10. **Latch the round once it is complete.** *Failure mode*: an ordinary
    one-shot. *Defense*: `TheHallDidItTwice` needs the full count reached in both
    rounds with a return to zero in between, and the drive reaches it twice by
    two different routes (an out-of-turn wipe, and a list replacement).
11. **Edit the fixture, or re-write the hall.** *Failure mode*: making the
    problem easier. *Defense*: `CraftBenchTests` is outside the writable set and
    the runner grades from git HEAD; and `TheHallIsNotYoursToRewire` compares
    every staged number, every mark location and the list itself every frame. It
    is load-bearing rather than ceremonial, because the fixture's model reads
    those same live values — without it a submission could re-write the hall into
    a shape where every other window is unreachable.

## Hidden invariants

- **The bank is never read out of the submission.** The fixture's model integer
  is its own; every gate is a statement about faces, lamps and a tally. A
  submission may represent the bank, the cursor and the round however it likes.
- **The model's required-seconds and list reads happen at the same instant the
  gate is evaluated**, never from a snapshot taken at the top of the phase — so a
  submission that reads them at the point of use agrees with the model by
  construction, and one that caches them diverges by exactly the staged delta.
- **The out-of-turn step is detected on the model's own ring-entry edge**, not on
  a UE overlap event, and the disclosed predicate is the one the marks ship. A
  submission that uses `IsInsideRing` cannot disagree with the fixture about
  which frame an entry happened on; one that rolls its own sphere or box overlap
  can, and the 0.35 s crossing suppression is what keeps that from being a false
  FAIL rather than a real one.
- **The two gates that watch an out-of-turn stand die with that stand.**
  `AWrongStepEmptiesEveryClock` and `StandingOutOfTurnBanksNothing` are claims
  about the stand the out-of-turn step began, so the fixture clears their armed
  state in the same place it forgives the poisoned stand — at the step off — and
  each gate re-checks that invariant before it reads anything. This is written
  down because the opposite cost a whole task: the armed state used to outlive
  the stand, and since the drive walks back onto the same marks several times,
  a **correct** submission's climbing face was read as a bank that should have
  stayed at zero. Four separate legitimate stands were fatal, which meant the
  reference could never PASS. The same staleness made the suppression window
  permanently true on those stands, so the per-mark face channel and the tally
  went ungraded there. Suppression must be exactly as wide as the sharper gate
  that replaces it, and never wider.

- **Two corners are deliberately never exercised, so neither can become an
  undisclosed literal.** (a) Whether a stand that was poisoned by an out-of-turn
  step *stays* poisoned across a list replacement: the drive never replaces the
  list while the character is standing on a poisoned mark — the first
  replacement lands on a legitimately re-entered stand, the second while the
  character is parked. (b) Whether a mark that has already finished becomes
  unfinished again if **its own number moves afterwards**: the fixture only ever
  moves a number on a mark that is **unfinished** (mid-stand for the two raises
  and the mid-stand drop, and parked-but-still-owed for the two off-mark drops);
  the shift change wipes the round in the same instant it re-writes the numbers;
  and the same-length reorder lands when three marks ARE finished, which is
  exactly why it is forbidden to move any number at all — `StageRound` refuses
  to write it if the table has drifted, and `author_map.py` refuses to save a
  hall whose tables would make it drift. Neither corner is settled by any prompt
  sentence, no gate can distinguish the two answers in either case, and an
  implementation may resolve both either way. **Do not add a drive phase that
  exercises one of these without adding the prompt sentence that settles it
  first.**
- **`fps_legs: [60, 20]` runs the whole drive twice**, in two PIE processes, each
  with its own wall-clock budget. Every number in this task is an integral of
  game time: an accumulator that adds a per-frame constant rather than
  `DeltaSeconds` completes each mark 3x too slowly at 20 Hz and fails the very
  first `AMarkWaitsForItsOwnNumber` window on that leg.
- **The empty-submission FAIL is not resting on one string.** The named substring
  the empty leg of `cb discriminate` matches is `TheBoardShowsHowFarYouGot` (the
  tally face ships blank and the baseline demands `0/4`), but
  `EveryFaceReadsItsOwnBank` and `TheUnnamedMarkStaysCold` fail on the same
  checkpoint for the same reason — all five faces ship blank.
