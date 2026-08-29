---
id: t2-guard-goes-to-where-it-last-saw-you
substrate: ThirdPerson
set: craftbench-public
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_NightYard :: AGuardLastSeenFunctionalTest"]
---

# t2-guard-goes-to-where-it-last-saw-you

Two watchmen in a night yard. The one that loses sight of the character has to walk
to **the spot where it last saw them**, stand there and search it, and go home
empty-handed — while radioing that same spot to a second watchman that never saw
anything at all. Neither may creep up on somebody it cannot see, and either must
drop whatever it is doing the instant it actually sees them again.

Written against the owner's 2026-08-18 difficulty bar, and revised in full against
an adversarial review of the first design (`notes.md` lists every item and what was
done about it — including two the review was right to call fatal).

> **Why a third guard task.** `t1-guard-only-spots-what-it-can-see` grades sight as a
> per-frame predicate; `t1-guard-patrols-until-the-alarm-then-chases` grades a
> transition driven by an *external* condition. Neither grades an **event**: a value
> captured on the true→false EDGE of a predicate and then acted on for the next thirty
> seconds, by an actor that was not the one that observed it. That is the whole of
> what is new here, and it is the thing every one of the named wrong answers gets
> wrong.

## Primary concept

- `ai-behavior-states` — switching an actor's behaviour on world state
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/behavior-trees-in-unreal-engine)

The load-bearing behaviour is a **value latched on the falling edge of a per-frame
predicate**, carried across a state change, and handed to a second actor that cannot
observe the predicate itself. The grade never asks *how*: a behaviour tree, a state
enum in `Tick`, or four `if`s all pass identically. No state name, enum or blackboard
key is read anywhere.

## Composed concepts

- `ai-perception` — sight as range plus an unobstructed line, evaluated from the
  observer's own transform
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/ai-perception-in-unreal-engine)
- `character-movement` — locomotion driven by `AddMovementInput` on a possessed
  character
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/character-movement-component-in-unreal-engine)
- `actor-communication` — one actor finding and notifying another at run time, with
  no level-authored reference between them
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/actor-communication-in-unreal-engine)

## Prompt given to the agent

> The night yard has two watchmen. Each one already stands on a post of its own, and
> left alone neither of them ever moves. They are the two that must do this work —
> they are already standing out there and there is no way to put different ones in
> the yard.
>
> Each watchman comes with three things already built and working, which you should
> use rather than rebuild.
>
> * **Eyes.** Ask a watchman whether it can see a particular actor right now and it
>   will tell you truthfully: an unobstructed straight line from its own chest to the
>   other's, and no further than its own sight range. The sight range is a plain
>   number written on the watchman; read it off if you need it, and leave it alone.
> * **Feet.** Give a watchman a spot in the yard and it walks there under its own
>   power at its own walking pace — also a number written on it, and also not yours
>   to change — and stops when it gets there. Tell it to stand and it stands. It
>   walks; it does not appear places.
> * **A post.** Where it was standing when the yard opened. It knows its own.
>
> What none of them has is any idea what to do. That is the whole of the job.
>
> Everything below is measured on the two watchmen, on the character the player
> controls, and on nothing else.
>
> **Sight beats everything.** While a watchman can see the character it goes after
> them. Once it has had them in unbroken sight for **two seconds** it must close to
> within **five metres** of them — and it must do that no matter what it was in the
> middle of when they came into view: standing its post, walking somewhere,
> searching, or trudging home.
>
> **When it loses sight, it goes to where it last saw them.** The spot is where the
> character was standing on the last moment that watchman could still see them.
> Getting within **four metres** of that spot counts as arriving.
>
> **Then it searches, and then it gives up.** From the moment it arrives it stays
> within **seven metres** of that spot for **six seconds**. If the character has not
> shown up in that time it walks back to its post and stands on it again — within
> **three metres** of where it started. (If the character does show up, the paragraph
> about sight applies and the search is over.)
>
> **Timing.** Wherever a watchman is headed, allow it the time its own walking pace
> needs to cover that distance in a straight line, **plus six seconds**. That is the
> whole of the allowance — for going to a spot, for closing on the character, and for
> getting home.
>
> **The radio.** The moment a watchman loses sight of the character it tells the
> other watchman **where the character was last seen**, and the other one walks to
> that same spot and searches it on the same terms — arrive within four metres, hold
> within seven metres for six seconds, then home. The second watchman never sees the
> character at all while this is going on: it knows only what it is told.
>
> **Nobody stirs without a reason.** A watchman that has neither seen the character
> itself nor been told anything stays on its post.
>
> **And nobody creeps up on what they cannot see.** Once a watchman has been unable
> to see the character for **five seconds**, it must not be within **twelve metres**
> of them — unless it is itself within twelve metres of the spot it is searching,
> which is where it was sent. Standing on that spot is allowed; homing in on somebody
> you cannot see is not. It looks perfectly fine while the character walks straight
> at you, and it is obvious the moment they break your line and get away.
>
> **A watchman is never anywhere it did not walk to.** Do not place, teleport or
> otherwise shift one; the only way a watchman moves is by being given somewhere to
> walk. Likewise the character, the walls and the posts are the yard's, not yours: do
> not move any of them.
>
> The yard runs the whole thing **twice**, and it has to work both times. The second
> time it is the *other* watchman that has the character in view, the walls are not
> where they were, and the last-seen spot is somewhere else entirely — nothing you
> can write down in advance is right both times.
>
> Do not edit the level, any config file, or any test file. Write your solution in
> C++ under `Source/ThirdPerson/`.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on this
substrate). `Source/CraftBenchTests/` is deny-listed and a submission file under it is
a SANDBOX-REJECT (exit 4), not a graded FAIL; so are `Content/Maps/`,
`Content/ThirdPerson/`, `Content/Characters/` and every `Config/` file (no
`config_allow` is declared by this task).

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t2-guard-goes-to-where-it-last-saw-you/YardWatchmanCharacter.h` / `.cpp` —
  `class THIRDPERSON_API AYardWatchmanCharacter : public ACharacter`, tagged
  `YardWatchman`. Supplied and working:
  - A visible body (the Quinn mannequin, so the watchmen read as a different party
    from the character the player controls) on a 42 x 96 capsule, auto-possessed by
    an AI controller so it is locally controlled and its movement component runs.
  - `UPROPERTY(EditAnywhere, BlueprintReadOnly) float WalkPaceUuPerSecond` and
    `float SightRangeUu` — **the yard sets both on the placed instances**; read them,
    do not change them. `WalkPaceUuPerSecond` is mirrored into the movement
    component's max walk speed, so the number on the watchman and the speed it
    actually walks are the same thing.
  - `UPROPERTY(BlueprintReadOnly) FVector PostLocation` — latched from
    `GetActorLocation()` in `BeginPlay`.
  - `UFUNCTION(BlueprintPure) bool CanSeeActor(const AActor*) const` — a
    chest-to-chest visibility line trace plus a range check.
  - `UFUNCTION(BlueprintCallable) void WalkToSpot(const FVector&)` /
    `void StandStill()`, `UFUNCTION(BlueprintPure) bool HasArrivedAtSpot() const`,
    `FVector GetGoalSpot() const`, `bool HasGoal() const`.
  - `Tick` contains **locomotion only**: while a goal is set it `AddMovementInput()`s
    along the 2D direction to the goal and stops inside a 150 uu stand-off. There is
    **no state, no timer, no last-seen field, no reference to the character, no
    reference to the other watchman and no radio of any kind.** Every decision in the
    prompt is missing, **and the work has to land on this class**: both watchmen are
    placed instances in a map that cannot be edited, so a subclass would never be
    constructed.
- `Content/Maps/t2-guard-goes-to-where-it-last-saw-you/L_NightYard.umap` — the staged
  yard, committed binary. World Settings name NO game mode, so the level inherits
  `BP_ThirdPersonGameMode` and a human can drive the same route with WASD. What is in
  it:

  | Element | Placement | Notes |
  |---|---|---|
  | Floor | one long yard, striped, with the two lanes painted | stripes and paint are **non-colliding** — a 3 cm lip is a wall to a swept move |
  | Two `AYardWatchmanCharacter`s | one post north of the middle, one south | each stands 1800 uu from its own lane and 3000 uu from the other's |
  | Two alcoves | three **movable** walls each, tagged `YardWall`, one at each end of the yard | each opens on the side facing **away** from its lane |
  | Sight rings | one painted circle per watchman, at its own sight range, non-colliding | so a human can see why one of them reaches a lane and the other does not |
  | PlayerStart | on the near lane, outside both watchmen's range | |
  | Backdrop + landmarks | a low back wall and three differently sized posts | a moving camera is distinguishable from a still one |
  | Fixture | one placed `AGuardLastSeenFunctionalTest` | |

  **The posts', the alcoves' and the lanes' exact coordinates are deliberately NOT in
  this section**, and the fixture additionally **slides each alcove along the yard by a
  per-run amount** before that alcove's leg, so a submission keyed on where anything
  stands reads a stale number.
- `cameras.json` (the camera-plan lane; not part of this release) — the
  presentation-only camera plan. Non-gating.

Files that **do not exist**:

- No decision logic of any kind, no Blueprint subclass, no level edits. The empty
  submission compiles (L1 green) and FAILs L2 the first time a watchman loses sight
  of the character and does not go anywhere.
- No test source in the agent's writable path. `AGuardLastSeenFunctionalTest` lives in
  the `CraftBenchTests` module the agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t2-guard-goes-to-where-it-last-saw-you/L_NightYard.umap` on the
**ThirdPerson** substrate, ticked at a fixed deterministic step
(`-deterministic -FPS=60`). Verification primitive: **pie-checkpoint-sampling** (the
schedule and clock owned by `ACraftBenchFunctionalTest`) over a per-frame
`AddMovementInput` drive of the game-mode-spawned player character — the same input
path a human uses.

**The fixture computes sight itself**, every frame, from the identical geometric rule
the scaffold uses (chest to chest via `GetPawnViewLocation`, an `ECC_Visibility` line
trace, and a range check against that watchman's own `SightRangeUu`). It never calls
the submission's copy. A submission that weakens the supplied eyes therefore diverges
from the world instead of moving the gates with it.

**Every waypoint is computed at run time** from the live positions of the tagged walls
and the two latched posts. No coordinate is written into the fixture.

### The drive

Per leg (two legs; leg 2 is the 180-degree mirror, with the other watchman doing the
seeing and its alcove slid along the yard):

| Stop | What it is for |
|---|---|
| lane start | out of both watchmen's range; the baseline, and the window in which the second watchman must not move |
| the far turn | one watchman acquires by range partway along, and the character **outruns it** (500 uu/s against 300), so sight breaks by range with the watchman ~2400 uu behind. That break is the last-seen spot |
| behind the alcove | the character runs on past the alcove and round the back |
| inside the alcove | it stands here for the whole measured window. The alcove opens away from the lane, so nothing on the lane side can see in |
| *(leg 2 only)* three standing spots | the character walks back out and stands still, three times, spread along the line the second watchman has to walk home |

Leg 1 holds the character in hiding until **both** watchmen are back on their posts;
leg 2 releases it once both have stood their six seconds, so a watchman is still on its
way home when the character reappears.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development"
```

No warning assert, deliberately: `--strict-warnings` is off on every `aura_rig` path,
and the prompt never mentions warnings, so gating on one would be an undisclosed
grade-bearing condition.

### L2 — AFunctionalTest behavioral trace

Every gate is judged from **positions, distances and times**. No behaviour-state name,
enum or blackboard key is read anywhere.

```text
assert: WentToWhereItLastSawYou -- for each alert, the watchman that lost sight must
        bring its distance to L (the character's position on its last sighted frame)
        to <= 400 uu by  t_lost + dist(that watchman at t_lost, L)/pace + 6 s + 2 s.
        The message names L, its closest approach, where it FIRST spotted the
        character, and where the character actually is.

assert: TheRadioCarriedThePlaceNotThePerson -- the other watchman, which the fixture
        computes as never having seen the character, must reach the SAME L on the
        same allowance, measured from where it stood when the alert was raised. The
        message names L, the character's live position and the caller's position, so
        "went to the person" and "went to the caller" are told apart in the verdict.

assert: SearchedThenWentBackToItsPost -- LEG 1 ONLY (leg 2's search is deliberately
        interrupted by a real re-acquisition). From its first frame within 400 uu of
        L, a watchman must accumulate >= 6.0 s of continuous time within 700 uu of L
        while blind; then, by (that moment) + dist(L, its post)/pace + 6 s + 2 s, it
        must be within 300 uu of its post.

assert: NeverCreptUpOnWhatItCouldNotSee -- every frame: a watchman the fixture
        computes as blind, that has been blind for >= 5.0 s, and that is more than
        1200 uu from the alert's spot, must be >= 1200 uu from the character.

assert: SightWinsOverWhateverItWasDoing -- a watchman with >= 2.0 s of unbroken sight
        of a character that is STANDING STILL at one of leg 2's standing spots must
        bring its distance to <= 500 uu by (arming) + gap/pace + 6 s + 2 s. Armed
        only at those spots, so a half-second pause on the way up the lane can never
        arm a chase the drive gives no time to finish.

assert: TheOtherWatchmanStayedPutUntilItWasTold -- from the start of a leg until that
        leg's first sight-loss, a watchman that has not itself seen the character
        stays within 300 uu of its post.

assert: TheWatchmenOnlyEverWalked -- over any rolling 1.0 s window, a watchman's 2D
        displacement is <= its own pace * 1.4 + 60 uu.

assert: NobodyMovedWhatWasNotTheirsToMove -- every tagged wall is still where the
        yard staged it for the leg in progress, to 2 uu, and the character's own
        displacement over any rolling 1.0 s window is <= 820 uu.

assert: TheWatchmenAreAsTheYardBuiltThem -- exactly two actors answer to the watchman
        tag, both expose WalkPaceUuPerSecond and SightRangeUu readably, neither value
        changes during the run, and exactly one watchman has the character in view the
        first moment anybody does.

assert: TheYardRanBothLegs -- evaluated at the sentinel: leg 2 completed, and at least
        one watchman was ever armed by the standing character.
```

The checkpoint schedule runs every 6 s and carries a **sentinel at t = 306 s**, far
past the ~180 s the two legs take, because `ACraftBenchFunctionalTest::Tick` ends the
test the moment the last scheduled checkpoint is sampled. The fixture **also finishes
itself the moment both legs are done and every tally is satisfied**, through the same
function the sentinel calls — so nothing that would have been judged at the sentinel is
skipped, and a healthy run does not spend 120 s of wall clock waiting for it. (The L2
layer's own budget is 600 s of WALL time, `tools/verify-single/layers/l2_pie.py:369`.)

**Per-run staging.** Each alcove is slid along the yard by an amount drawn from the
hardware timestamp (+/- 200 uu), and the lanes are offset by +/- 40 uu, before that
alcove's leg. Every draw is re-checked against the staging preconditions and halved
until they hold, with a zero draw as the final fallback: a jitter may widen the yard's
variety and may never manufacture a FAIL. The draw is logged, so a verdict is
reproducible from the log.

**Staging faults are attributed, not scored.** A yard whose posts are on the same side,
whose sight range does not sit strictly between the near and far lane offsets, whose
drive would scrape a wall, or whose hiding place can be seen from the band a watchman
searches, ends the run as `HARNESS-PRECONDITION` (`EFunctionalTestResult::Error`), never
as a model failure. **Everything a submission can cause is graded**, not attributed:
a missing or altered `WalkPaceUuPerSecond` / `SightRangeUu`, a re-labelled or destroyed
watchman, and a watchman that has wandered off its post are all named FAILs.

## Requirement-to-assertion map

| Prompt requirement | Gate that checks it | When that gate does NOT run |
| --- | --- | --- |
| close to five metres after two seconds of unbroken sight, whatever it was doing | `SightWinsOverWhateverItWasDoing` | while the character is moving, and at the short waypoint pauses (armed only at leg 2's three standing spots) |
| go to where it last saw them, within four metres | `WentToWhereItLastSawYou` | for an alert superseded by a newer one before its deadline |
| stay within seven metres for six seconds from arrival | `SearchedThenWentBackToItsPost`, first half | leg 2, where a real re-acquisition ends the search — as the prompt says it should |
| then go home, within three metres | `SearchedThenWentBackToItsPost`, second half | same |
| the allowance is distance/pace + six seconds | every deadline above is built from exactly that, plus 2 s of fixture slack | never |
| the radio carries the place | `TheRadioCarriedThePlaceNotThePerson` | for a superseded alert |
| nobody stirs without a reason | `TheOtherWatchmanStayedPutUntilItWasTold` | after the leg's first sight-loss |
| never within twelve metres of what you cannot see | `NeverCreptUpOnWhatItCouldNotSee` | for the first 5 s of blindness, and while the watchman is within twelve metres of the spot it was sent to |
| it walks; it does not appear places | `TheWatchmenOnlyEverWalked` | never |
| the walls, the posts and the character are the yard's | `NobodyMovedWhatWasNotTheirsToMove` | the character's clause is off during the fixture's own between-leg staging |
| the pace and the sight range are the yard's | `TheWatchmenAreAsTheYardBuiltThem` | never |
| it has to work both times | `TheYardRanBothLegs` | never |
| C++ under `Source/ThirdPerson/` | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

**This task grades all-or-nothing.** There is one verdict, produced by the first gate
that fires; there is no per-check ratio, so the charter's constant-denominator rule
(which exists to stop a submission improving a ratio by making checks unreachable) does
not apply. The two leg-scoped gates are named as such above rather than left implicit.

## Reference solution metadata

- **Files touched:** 2 (`YardWatchmanCharacter.h`, `YardWatchmanCharacter.cpp`), both
  already present. No new file, no `Build.cs` edit — `AIModule` is already a public
  dependency of the agent-writable module.
- **LOC:** +115 over the scaffold (a five-state enum, one edge test, one broadcast, one
  arrival-started timer, and a switch).
- **Honest senior-dev hours: 2.5–4 h**, i.e. solidly T2. The scaffold hands over the two
  genuinely fiddly UE pieces — a working sight test and working locomotion — so nothing
  is spent on traces, navmesh, controllers or animation. Where the hours go: ~1 h on a
  state machine that is correct at the EDGES (two of its transitions are events rather
  than states, and one preempts every state unconditionally); ~45 min on the radio
  (deciding it carries a point rather than an actor or a sender, finding the other
  watchman with no help from the level, and deciding what a report does to a watchman
  that already has eyes on); ~45 min on timing (three deadlines, and a give-up clock
  that must start on ARRIVAL — the walk there is longer than the search); ~45 min
  debugging leg 2, where the roles are reversed and the walls have moved, which is where
  anything keyed on array index or on a remembered position falls over.
- Not T3: no new subsystem, no asset authoring, no build-system work, one class.

## Anti-gaming notes

1. **Chase the live transform once alerted.** *Failure mode*: on losing sight, keep
   calling `WalkToSpot(Target->GetActorLocation())`. It looks flawless while the
   character walks straight down the lane. *Defense*: the character gets away round the
   back of an alcove that opens the other way, so the chaser walks up to somebody it
   cannot see and `NeverCreptUpOnWhatItCouldNotSee` fires with the gap in the message;
   `WentToWhereItLastSawYou` fires too, because it never converges on the spot. Measured
   on the reference: the nearest a correct watchman comes to the hidden character while
   blind and away from the spot is ~2400 uu, against a floor of 1200.
2. **Store the spot on ACQUISITION instead of on loss.** *Failure mode*: write
   `LastSeen` inside the "just spotted them" branch — a one-line placement mistake.
   *Defense*: the character is in unbroken view for ~3200 uu before sight breaks, and
   the fixture measures ~6200 uu between where it was first spotted and where it was
   last seen. `WentToWhereItLastSawYou` names both points in the same sentence.
3. **Store the WATCHMAN's own position at sight-loss.** *Failure mode*: "go back to
   where I lost him" reads naturally and is wrong. *Defense*: sight breaks by RANGE
   while the character outruns the watchman, so the two are ~2400 uu apart at that
   moment — six times the 400 uu arrival tolerance. Same gate, and
   `TheRadioCarriedThePlaceNotThePerson` for the radioed copy.
4. **Radio the actor, or the caller.** *Failure mode*: `Other->Alerted(Target)` so the
   receiver resolves a live transform, or `Other->Alerted(GetActorLocation())` so it
   walks to the caller. *Defense*: `TheRadioCarriedThePlaceNotThePerson` reports the
   spot, the character's live position and the caller's position side by side, so which
   of the three was handed over is legible from the verdict alone.
5. **Broadcast on FIRST sight instead of on loss of sight.** *Failure mode*: raise a
   yard-wide alert inside the acquire branch — a completely reasonable reading of "tell
   the others" that produces a nice convergent response. *Defense*:
   `TheOtherWatchmanStayedPutUntilItWasTold` watches the second watchman's post for the
   whole of the pre-loss window, which is ~10 s of the character walking up the lane in
   the first watchman's plain view.
6. **A state machine where only the watch state polls the eyes**, or a
   `bAlreadySearchedThisAlert` latch. *Failure mode*: the searching or homeward-bound
   watchman walks straight past a character standing in the open. *Defense*:
   `SightWinsOverWhateverItWasDoing`, on leg 2's standing spots. **Honest limit**: the
   three standing spots are spread along the second watchman's homeward line so that
   one of them is very likely to land while it is still walking, but the fixture cannot
   *guarantee* which state a given submission will be in when the character reappears;
   what it does guarantee is that the gate is armed at all (the last spot is inside the
   spotter's range from its own post). A submission that never chases at all, and one
   that latches until its own state machine resets, both fail it outright.
7. **Start the give-up timer at sight-loss rather than at arrival.** *Failure mode*: one
   timer, started when the alert is raised. *Defense*: the walk to the spot takes ~8 s
   for the watchman that saw and ~15 s for the one that was told, both longer than the
   6 s search, so the timer has expired before either arrives and each turns for home on
   its arrival frame. The hold half of `SearchedThenWentBackToItsPost` measures the
   accumulated hold and prints it.
8. **Arrive and stop for good.** *Failure mode*: no give-up path at all. *Defense*: the
   return half of the same gate, with a deadline built from the disclosed allowance.
9. **`SetActorLocation` to meet a deadline.** *Failure mode*: teleport the second
   watchman to the reported spot when its walk looks too slow. *Defense*:
   `TheWatchmenOnlyEverWalked` over a rolling one-second window. The same window also
   refuses a submission that raises the watchmen's speed to outrun the character — the
   budget (pace x 1.4 + 60 = 480 uu/s) is deliberately below the character's 500.
10. **Weaken the supplied eyes.** *Failure mode*: make `CanSeeActor` always false so the
    watchman is never "blind while alerted", or always true so it may always chase.
    *Defense*: the fixture computes sight itself from the same geometric rule, so
    tampering moves the submission away from the world rather than moving the gates;
    and `TheWatchmenAreAsTheYardBuiltThem` separately refuses a changed
    `SightRangeUu` / `WalkPaceUuPerSecond`, a re-labelled watchman, and a first sighting
    seen by both of them at once.
11. **Hard-code the spot, the alcove or the roles.** *Failure mode*: "watchman 0 watches,
    watchman 1 answers the radio", or a remembered coordinate. *Defense*: leg 2 reverses
    the roles by geometry, slides the alcove, and puts the last-seen spot thousands of uu
    away; the fixture derives every waypoint and every deadline from live positions; and
    the per-run jitter means two runs of the same submission do not see the same numbers.

## Hidden invariants

- **The posts are latched twice, and that is fine.** The scaffold latches
  `PostLocation` in `BeginPlay`; the fixture latches its own copy in `PrepareTest`,
  which runs later, after the placed capsules have settled onto the floor. The two are
  therefore not bit-identical. Every comparison against a post is 2D and the tolerance
  is 300 uu, which swallows the settle many times over. The fixture never reads the
  scaffold's copy.
- **Only walls and floor occlude.** `BaseEngine.ini:3110` gives the `Pawn` collision
  profile — which `ACharacter`'s capsule uses (`Character.cpp:79`) —
  `Visibility=ECR_Ignore`, and `:3112` does the same for `CharacterMesh`. No character
  can block a visibility trace, so two watchmen converging on one spot can never occlude
  each other or the character, and the scaffold's self/target ignore list is
  belt-and-braces. **Re-profiling a wall to anything pawn-like would silently delete
  every sight break in this level.**
- **The blind rule is exempt at the spot, on purpose.** `NeverCreptUpOnWhatItCouldNotSee`
  never fires on a watchman within twelve metres of the spot it was sent to. That is what
  makes it unfailable by a correct answer whatever the run-time geometry turns out to be:
  the honest searcher stays within seven metres of that spot, and the distance from the
  spot to the hiding place depends on how far the submission chased, which no number in
  the fixture can pin down.
- **An alert supersedes.** Every sight-loss opens a fresh alert and retires the previous
  one unjudged. A submission whose watchman legitimately re-acquires and loses the
  character again is therefore graded against the *latest* spot, not held to a stale one.
- **The fixture may end the run early**, once both legs are done and every tally is
  satisfied — through the same function the sentinel calls. Nothing deferred to the
  sentinel is skipped by the early exit.
