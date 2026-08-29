---
id: t3-the-round-number-everyone-agrees-on
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_RoundHall :: ARoundHallFunctionalTest"]
---

# t3-the-round-number-everyone-agrees-on

A stone hall that is on one round number at a time. Four signs show it, a relic at
the back shows something else and must go on doing so, a mark on the floor raises it
by whatever the mark is carrying **at that moment**, a hoist puts up a new sign part
way through that must come up **already showing the current number**, a sinkhole takes
the runner away — twice — without the hall losing its place, and a doorplate on the
entrance stone shows **the round the runner now in the room walked in on**.

> **Built against the 2026-08-18 difficulty bar.** Two subsystems that genuinely
> interact: the ownership of one match-scoped number, and the body lane that ends a
> runner and puts a new one of the same kind under the player's control. **They are
> joined at the doorplate**, whose value is the hall's number SAMPLED AT A BODY CHANGE —
> a number neither half produces on its own. Own the number perfectly and never notice
> the body changed and the doorplate is stale: `TheDoorplateShowsTheRoundTheRunnerWalked
> InOn` is the only gate that speaks, and no body gate is involved. Re-body perfectly and
> keep the number on the body and the doorplate is wrong as well as the signs. The
> locally-reasonable wrong answers, written down in full in *Anti-gaming notes*: the
> doorplate written once when the hall opens (right through fall 1, wrong after fall 2),
> the doorplate written like a hall sign on every advance (wrong from the first advance),
> a readout population captured once at `BeginPlay` (the hoisted sign is never written
> to), the step read once and remembered, and the number kept on the body. Every
> load-bearing number is read off the world, none of them is the number committed in the
> level file, and one of them changes mid-run.

## Primary concept

- `game-mode-and-game-state` — Game Mode and Game State
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/game-mode-and-game-state-in-unreal-engine)

The load-bearing behaviour is **match-scoped shared state**: one number owned by the
session rather than by any actor in it, which must survive the destruction of the body
that raised it and must be answerable to a reader created after it was last written.
The grade never asks *how*: a world-scoped subsystem, a placed prop that holds the
number, or a spawned keeper of the submission's own making all pass identically, as
long as the readouts agree inside the half second the prompt promises.

## Composed concepts

- `game-mode-and-game-state` — Game Mode and Game State
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/game-mode-and-game-state-in-unreal-engine)
- `programming-subsystems` — Programming Subsystems
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/programming-subsystems-in-unreal-engine)
- `spawning-actors` — Spawning Actors
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/spawning-actors-in-unreal-engine)
- `possessing-pawns` — Possessing Pawns
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/pawn-in-unreal-engine)
- `player-start-actor` — Player Start Actor
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/player-start-actor-in-unreal-engine)
- `actor-lifecycle` — Actor Lifecycle
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-actor-lifecycle)

**Production pattern.** This is the standard round/wave counter of every arena and
horde game: one authoritative match value that the whole level reads, a set of world
readouts that are told about it rather than each keeping a copy, a UI element that
joins the match late and must initialise from the authority rather than from a default,
and a death-and-respawn loop that puts the player back into a fresh body of the
configured class without disturbing match progress. Epic's own Game Mode / Game State
documentation describes the split exactly this way — rules and match-scoped state at
the top of the hierarchy, everything below it a reader — and the "late reader shows the
current value" clause is the standard test every shipped implementation of that split
has to pass.

**How they interact, at the point the verifier checks.** The doorplate is the join,
and it is load-bearing rather than decorative: its value is `the hall's number` evaluated
`at the instant the body walking in the room becomes a different object`. Neither operand
is available to half of the task. A submission that models the number perfectly — right
start, right step read at the moment of use, every sign in agreement, the hoisted sign
correct — and whose fall handler does nothing but put a body back (which is what the
"the round number is not touched by any of this" clause invites) leaves the doorplate on
the number the hall opened with and fails a gate no body check would ever raise. A
submission whose body lane is perfect but whose number lives on the pawn writes the
doorplate correctly at the moment it writes it and still has the wrong number in it.
On top of that: the advance mechanism reads its step off the world at the moment of use,
so the arithmetic cannot be cached; and the readout population *grows* at run time, so a
design that pushes copies out to a fixed set of readers is wrong from the moment the set
changes. No single concept's documentation covers the crossing point.

## Prompt given to the agent

> The round hall is a stone room that is on one round number at a time. Everything in
> it works except the deciding.
>
> **What is already built and working.** Four pillars around the hall each carry a
> sign, and an older sign stands against the back wall. Every sign can be told to print
> a whole number, and the hall's own signs all start blank. Each sign says whether it
> belongs to the hall or not — the back one does not. It is a relic: the number painted
> on it is the number it must go on showing, whatever else happens in the room, and it
> comes up showing it by itself. A stone at the entrance is painted with the number the
> hall starts on, and the mark at its foot is where a runner walks in; low on the same
> stone is a second, smaller plate — the doorplate — which comes up blank and prints
> whatever it is told, whenever it is told. A mark on the floor in the middle of the
> room carries the step it raises the round by, written on the mark where anybody can
> read it; it says out loud when somebody steps onto it and when the last of them steps
> off, and it raises nothing itself. A hoist plate by the west wall **runs itself**:
> step on it and a fresh sign of the same kind as the hall's goes up, blank, on the
> empty pillar beside it, and it says that it has done so. It can be used more than
> once. A sinkhole is open in the floor and runs itself too: whoever walks in is gone,
> that runner ends there, and it says so once they are. All of that is supplied and
> working — leave it there. **Nothing decides what any sign or plate should show, what
> the hall's number is, or what happens after a runner is lost.** That deciding is the
> whole job.
>
> **The round number.** The hall begins on the number painted on the entrance stone.
> Read that number off the stone: it is not the same number every visit.
>
> **Raising it.** Each time somebody steps onto the mark in the middle of the room, the
> number goes up exactly once, by the step the mark is carrying at that moment.
> Standing on the mark does not keep raising it; stepping off and stepping on again
> raises it again. The step written on the mark can be changed while the hall is
> running. Nothing else ever changes the number.
>
> **Everyone agrees.** Every sign that belongs to the hall shows the round number the
> hall is on, and they all show the same one. A sign has **half a second** to catch up
> after the number changes. A sign is read as the first whole number it prints; a hall
> sign left blank is not showing the number. The relic at the back is not one of the
> hall's signs: it goes on showing its own painted number for the whole visit.
>
> **A sign that arrives late.** When the hoist raises a new sign part way through, that
> sign is one of the hall's from then on, and it must come up **already showing the
> number the hall is on**. Half a second after it appears it is showing that number, and
> from then on it keeps up with every later change exactly like the others.
>
> **A new runner.** Falling into the sinkhole ends that runner. Within **two seconds** a
> new runner **of the same kind** is standing on the mark at the entrance stone — within
> **150 centimetres** of the middle of it across the floor, and standing on it rather
> than hanging in the air over it, its feet within **three metres** of it up or down —
> under the player's control and able to walk on. There is never more than one runner
> alive in the hall at a time. The round number is not touched by any of this: it is
> exactly what it was before the fall, every sign still shows it, and the next step onto
> the mark carries on from there.
>
> **The doorplate.** The doorplate on the entrance stone shows **the round the runner
> now in the hall walked in on** — the number the hall was on at the moment that runner
> started walking in this room, not the number the hall is on now. The runner the hall
> opens with walked in on the number the hall starts on. The doorplate changes when the
> runner in the room changes, and at no other time. It has the same **half a second** to
> catch up as a sign, it is read the same way — the first whole number it prints — and
> a blank doorplate is not showing anything.
>
> **Ground rules.** The numbers the hall was given — the number on the entrance stone,
> the step on the mark, the number painted on the relic — are the hall's, not yours:
> read them, do not rewrite them. Do not move the marks, the pillars, the hoist or the
> sinkhole, and leave everything listed above where it is and working. The hall itself
> is fixed: you cannot put anything new into the room by hand, and the room's rules come
> from the project's own settings, which you cannot change either. Whatever does the
> deciding therefore has to live on something already standing in the hall, or on
> something your own code brings into being and keeps alive. Do not edit the level, any
> config file, or any test file. Write your solution in C++ under
> `Source/ThirdPerson/` — that is the only place your work may land.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on this
substrate). `Source/CraftBenchTests/` is deny-listed and a submission file under it is a
SANDBOX-REJECT (exit 4), not a graded FAIL; so are `Content/Maps/`,
`Content/ThirdPerson/`, `Content/Characters/`, `Content/LevelPrototyping/` and every
`Config/` file (this task declares no `config_allow`). The level's rules — which kind of
runner walks in and who controls it — come from the project's own defaults, and there is
no writable path that can change them.

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t3-the-round-number-everyone-agrees-on/RoundHallProps.h` / `.cpp` — five
  supplied prop classes, all complete and **working**, none of which knows that a round
  number exists:

  | Class | Tag | What it ships, working | What it deliberately does NOT do |
  |---|---|---|---|
  | `AHallSignActor` | `HallSign` | a board and a readable face; `Print(int32)`, `PrintNothing()`, `GetPrintedText()`; `UPROPERTY(EditAnywhere) bool bBelongsToTheHall` and `int32 PaintedNumber`, both read off the sign; a sign that does not belong to the hall prints its own `PaintedNumber` in `BeginPlay` | decide what to show; refuse a write. **`Print` writes on any sign, including the relic** |
  | `AEntranceStoneActor` | `EntranceStone` | `UPROPERTY(EditAnywhere) int32 StartNumber` shown on the stone's face every frame; `GetStartNumber()`; `GetMarkCentre()` — the middle of the mark on the floor at its foot; **the doorplate**, a second face low on the stone with `PrintOnTheDoorplate(int32)`, `ClearTheDoorplate()`, `GetDoorplateText()`, blanked in `BeginPlay` and never touched again by anything supplied | decide what the doorplate shows, or keep it in step with anything |
  | `AStepMarkActor` | `StepMark` | `UPROPERTY(EditAnywhere) int32 StepWritten` shown on the mark every frame; `GetStepWritten()`; a volume already wired to `OnSteppedOn(AActor*)` / `OnSteppedOff(AActor*)`, **one announcement per body per entry**; `IsSomebodyStandingOnIt()` | raise anything, count anything, remember anything |
  | `AHoistPlateActor` | `HoistPlate` | a plate whose volume already calls `RaiseSign()` once per entry; `RaiseSign()` spawns a sign of the same runtime class as a hall sign already standing, marks it as one of the hall's, leaves it **blank**, stacks each new one above the last, and broadcasts `OnSignRaised(AHallSignActor*)` | tell the new sign anything |
  | `ASinkholeActor` | `Sinkhole` | a mouth whose volume takes any runner that walks in — destroyed at the end of that frame — then broadcasts `OnRunnerLost()`; `GetRunnersLost()` | put anybody back |

  Every one of them is non-blocking on every channel except the level's own floor, so
  nothing in the hall can trap or trip a runner.

- `Content/Maps/t3-the-round-number-everyone-agrees-on/L_RoundHall.umap` — the hall
  itself. **World Settings name no game mode of the level's own**, so the room's rules
  come from the project's defaults: the kind of runner that walks in, who controls it
  and how it is driven are all inherited and none of them is reachable from a writable
  path. What is in the room:

  | Element | Placement | Notes |
  |---|---|---|
  | Floor | 4,000 x 4,000, striped every 200 cm, stripes **non-colliding** | |
  | Four pillars, each with one `AHallSignActor` | around the hall, all four in one camera frame | `bBelongsToTheHall = true` |
  | One `AHallSignActor` at the back wall | the relic | `bBelongsToTheHall = false` |
  | One empty pillar | beside the hoist plate | where raised signs go, stacked |
  | One `AEntranceStoneActor` | at the door; the spot a runner walks in from is on its floor mark, facing the hall | |
  | One `AStepMarkActor` | middle of the room | |
  | One `AHoistPlateActor` | west wall | its raise socket over the empty pillar |
  | One `ASinkholeActor` | off the main lane, reachable but not on any route between the other three | |
  | Backdrop + landmarks | back wall plus two differently sized posts, **non-colliding** | so a moving camera is distinguishable from a still one |
  | Test harness | one placed test-harness actor | |

  **The three numbers the hall was given are deliberately NOT in this section.** They
  are readable in the room, on the things themselves — and, as the prompt says, they
  are not the numbers written in the level file. Read them off the things.

- `cameras.json` (the camera-plan lane; not part of this release) — a
  presentation-only camera plan. Nothing about it affects the work.

Files that **do not exist**:

- No round number anywhere, no code that prints on a sign or on the doorplate, no code
  that reacts to a step on the mark, to a raised sign or to a lost runner, no Blueprint
  subclass, no level edits, and no rules object of the task's own. Every supplied class
  is complete and inert: the project as shipped builds cleanly, the hall's four signs
  stay blank for the whole visit, and so does the doorplate.
- No test source in the agent's writable path. The test harness lives in a module the
  agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t3-the-round-number-everyone-agrees-on/L_RoundHall.umap` on the
**ThirdPerson** substrate, ticked at a fixed deterministic step
(`-deterministic -FPS=60`), one leg. Verification primitive:
**pie-checkpoint-sampling** plus an every-frame readback of what the signs actually
print — the thing a reviewer reads off the wall — over a fixture-driven walk, compared
against the fixture's own running model of the rule.

`fps_legs` is deliberately **not** declared: nothing in this task asks the submission to
measure time, so a frame-count overfit is not one of its plausible wrong answers, and
the anti-overfit work is done by the mid-run re-stage instead of by a second frame rate.
The drive is ~110 s and a second leg would double it for no discrimination.

### What the fixture stages, and when

In `FWorldDelegates::OnWorldInitializedActors` — after `PostInitializeComponents`,
before any `BeginPlay` — the fixture writes the numbers the hall actually runs on, so a
submission that reads them at play reads the staged values and every gate below is
honest. Only CACHING is punished, and only by a move the prompt discloses.

| What | Staged | Committed in the .umap (the decoy) |
|---|---|---|
| `AEntranceStoneActor::StartNumber` | **4** | 1 |
| `AStepMarkActor::StepWritten` | **2**, re-staged to **3** mid-run | 1 |
| the relic's `PaintedNumber` | **1** | 0 |

A hard-coded answer is therefore wrong at the FIRST checkpoint: the corpus's own
"starts at 1, advances once to 2" is 4 and +2 here, and so is anything read out of the
committed map.

**The doorplate is not staged, because it is not the hall's to state.** It comes up
blank in the stone's own start-up and nothing supplied writes on it again, so what it
shows at every judged frame is the submission's, and the fixture's model of it — the
number the hall was on at the last body change — is derived from the two things it
already tracks.

**The mid-run re-stage.** With nobody standing on it, after the second advance and the
first hoist, the fixture rewrites the mark's step from 2 to 3 and
`TheHallKeepsWhatWasGivenToIt` starts comparing against 3 from that frame. The run's
arithmetic is therefore:

```text
4 -> 6 -> 8 -> [hoist #1: the new sign must read 8] -> [the step becomes 3]
  -> 11 -> [fall #1: still 11, and the doorplate becomes 11] -> 14
  -> [fall #2: still 14, and the doorplate becomes 14]
  -> [hoist #2: the new sign must read 14] -> 17

doorplate: 4 . . . 4 -> [fall #1] 11 -> [fall #2] 14
```

The triple is chosen so that no wrong answer's number ever coincides with the right one
at a sampled checkpoint: the cached-step answer says 10 where 11 is required, 12 where
14 is, 14 where 17 is; the pawn-scoped answer says 4 where 11 is required; a doorplate
that mirrors the hall says 6 where 4 is required and never comes back; a doorplate
written once says 4 where 11 is required and 4 where 14 is; and the relic's 1 is never a
value the hall takes. **The fixture asserts every one of those properties of its own
staging as a HARNESS-PRECONDITION rather than trusting this paragraph to stay true.**

### The drive

Ordinary locomotion between the marks named in the prompt, driven by the shipping
per-frame `AddMovementInput` timeline. No step asks for anything the prompt does not
already promise works. Every walk is routed so that it never clips a trigger it was not
aimed at (a HARNESS-PRECONDITION on the staged layout, re-checked before the drive
starts).

**Nineteen stops.** Each is *walk to here, then dwell*; the walk leg's deadline is derived
from the distance at a deliberately slow 220 uu/s (2.3x slower than the ~500 uu/s the
stock pawn manages) plus 4 s of slack for acceleration and settling, so an ordinary walk
never runs its own clock out. A `Clear` stop is the lane point beside the thing just used,
i.e. *step off it*, which is what makes the next entry an entry.

| Stop | Kind | Where | What it is for | The hall is then on |
|---:|---|---|---|---|
| 0 | Settle | the entrance mark | the opening state is graded before anything happens | **4** |
| 1 | Mark | the step mark | advance 1, at +2 | **6** |
| 2 | Clear | the lane beside the mark | step off | 6 |
| 3 | Mark | the step mark | advance 2, at +2 | **8** |
| 4 | Clear | the lane beside the mark | step off | 8 |
| 5 | Hoist | the hoist plate | **hoist #1** — the raised sign must come up on 8 | 8 |
| 6 | Restage | the lane beside the plate | the fixture rewrites the mark's step **2 → 3**, with nobody standing on it | 8 |
| 7 | Mark | the step mark | advance 3, at **+3** — the cached-step answer says 10 here | **11** |
| 8 | Clear | the lane beside the mark | step off | 11 |
| 9 | Hole | the sinkhole | **fall #1** — a new runner within 2 s, the hall still on 11, the doorplate becomes **11** | 11 |
| 10 | Mark | the step mark | advance 4, at +3, carrying on from 11 | **14** |
| 11 | Clear | the lane beside the mark | step off | 14 |
| 12 | Hole | the sinkhole | **fall #2** — a *different* doorplate value (**14**, not 11), so a doorplate written once dies here having passed fall #1 | 14 |
| 13 | Hoist | the hoist plate | **hoist #2** — the raised sign must come up on **14**, a number that has SURVIVED a re-body with no advance since | 14 |
| 14 | Clear | the lane beside the plate | step off | 14 |
| 15 | Mark | the step mark | advance 5, at +3, carrying on from 14 | **17** |
| 16 | Clear | the lane beside the mark | step off | 17 |
| 17 | Settle | the lane beside the mark | stand and settle | 17 — all **six** hall signs agree |
| 18 | Finish | — | the run-level gate, then `FinishTest` | 17 |

A `Hole` stop is ended by the fall itself, not by its dwell: the dwell is an 8 s ceiling
after which the drive gives up and `TheRunnerCouldNotGetWhereHeWasGoing` speaks. The
hoist and the hole are also each required to actually FIRE within 0.75 s / 1.50 s of the
runner standing on them (read off `GetSignsRaised()` / `GetRunnersLost()`), so a
submission that breaks a supplied fitting is named by `TheHallKeepsWhatWasGivenToIt`
rather than by a silent stall.

Every trigger fires at least twice — the mark five times, the hoist twice, the sinkhole
twice — and **the second firing of each one asks something the first could not**, which
is the difference between satisfying the re-trigger convention in letter and in effect:

- **fall #2 lands on a different number from fall #1** (14 against 11), so the doorplate
  has to be *rewritten*, not merely written. A submission that writes it once at the
  first fall passes fall #1 completely and dies at fall #2 — and a one-shot re-body latch
  dies there too, on its own gate.
- **hoist #2 is placed immediately after fall #2, with no advance in between**, so the
  sign it raises must come up on a number that has survived a re-body. Hoist #1 raises on
  a freshly advanced number with no body yet lost and cannot ask that question.
- **mark entry #3 is the first after the re-stage**, entry #4 the first after a fall
  (which is where `TheNumberSurvivesANewRunner`'s second half is decided), and entry #5
  the first after the second fall.

### Settle and suppression

The prompt promises a sign **half a second** to catch up and a fresh runner **two
seconds** to arrive. Every window the fixture actually uses is a MULTIPLE of one of
those two, and every one of them is a **widening** of the disclosed contract, never a
narrowing. All of them are named constants at the top of the fixture, expressed as
multiples of the two disclosed numbers so that they cannot drift apart from the prompt:

| Window | Value | = | What it governs |
|---|---|---|---|
| the disclosed settle | 0.50 s | — | what the prompt promises a sign |
| rise deadline | **1.00 s** | 2 x settle | how long `EachStepOnTheMark…` waits after an entry before it judges the rise |
| agreement stand-off | **1.25 s** | 2.5 x settle | how long `EverySignInTheHall…` (and the "nothing else changes the number" clause) stands off after the fixture's own model changes |
| raised-sign grace | **1.00 s** | 2 x settle | how long `TheNewSignComesUpOn…` waits after a sign exists before it judges what it came up on |
| raised-sign stand-off | **1.25 s** | 2.5 x settle | how long the agreement gate leaves a just-raised sign out of the population |
| the disclosed re-body | 2.00 s | — | what the prompt promises a fresh runner |
| body judge point | **2.25 s** | re-body + 0.25 s | when the two body gates judge, leaving the fresh body a frame's grace |
| fall stand-off | **2.50 s** | body judge + 0.25 s | how long the agreement gate stands off across a fall |
| doorplate grace | **3.50 s** | re-body + 3 x settle | how long `TheDoorplateShowsTheRound…` leaves the doorplate alone after the body in the room becomes a different object |
| input hold | **3.50 s** | > fall stand-off | how long the fixture holds its OWN input after a fall |

`EverySignInTheHallShowsTheNumberTheHallIsOn` additionally judges nothing before
**t = 2 s**, which is the first graded checkpoint and the frame the empty leg dies on.
`TheRelicKeepsItsOwnNumber` and `TheHallKeepsWhatWasGivenToIt` deliberately have **no
window at all** and are gauged from the first frame the fixture runs: the relic has
already printed its own number in its own start-up, and nothing the hall was given may
move at any time. Nothing is judged on a frame where the fixture is re-staging the hall.

**Two of those orderings are load-bearing, not slack.** They are what decides WHICH gate
speaks for a given wrong answer, and getting them the other way round would leave a real
defect named by the wrong message:

- **agreement stand-off (1.25 s) > rise deadline (1.00 s).** A cached step is visible to
  both the step gate and the agreement gate. Because the agreement gate is still standing
  off when the step gate's deadline expires,
  `EachStepOnTheMarkRaisesTheNumberByWhatTheMarkNowCarries` is the gate that speaks —
  which is the one whose message names the mark's current step.
- **fall stand-off (2.50 s) > body judge point (2.25 s).** A number that did not survive
  the fall is named by `TheNumberSurvivesANewRunner` (and, for a body fault, by
  `ANewRunnerOfTheSameKindStandsOnTheEntranceMark`) rather than laundered into a
  generic disagreement.

**The fixture holds its own input for 3.50 s after each fall.** Without that it would be
walking the fresh body away from the entrance mark while measuring how far from that mark
the body is — i.e. measuring its own drive, at up to 500 uu/s against a 150 uu tolerance.

### The sentinel

The checkpoint schedule is **99 graded checkpoints every 2 s (t = 2 s … 198 s)** plus a
**SENTINEL at t = 200 s**, far past the ~110 s the drive models, because
`ACraftBenchFunctionalTest::Tick` ends the test the moment the last scheduled checkpoint
is sampled. The run-level gate is evaluated when the last phase completes **and** again
at the sentinel, whichever comes first, and only then does the fixture call
`FinishTest`. This is the base-fixture law: the last scheduled checkpoint ENDS the test,
so a grade hung off a measured event that never arrives is silently skipped and the run
reads green.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

**Gate precedence, in the order the fixture evaluates them every frame.** The order is
chosen so that each wrong answer is named by the gate whose MESSAGE diagnoses it, and it
works together with the stand-off table above — a gate that is still standing off cannot
shadow the gate that owns the answer.

```text
1  TheRelicKeepsItsOwnNumber                                -- every frame, no settle window
2  TheHallKeepsWhatWasGivenToIt                             -- every frame, including
                                                               "the hoist/hole still fires"
3  TheNumberSurvivesANewRunner                              -- the two fall windows, from 2.25 s
4  ANewRunnerOfTheSameKindStandsOnTheEntranceMark           -- the two fall windows, from 2.25 s
5  EachStepOnTheMarkRaisesTheNumberByWhatTheMarkNowCarries   -- per entry, from 1.00 s; plus
                                                               the two "nothing else moves it"
                                                               clauses
6  TheNewSignComesUpOnTheNumberTheHallIsOn                  -- the two post-hoist windows,
                                                               from 1.00 s
7  TheDoorplateShowsTheRoundTheRunnerWalkedInOn             -- every judged frame from 3.50 s
                                                               after the body in the room last
                                                               changed, and never inside a
                                                               fall window
8  EverySignInTheHallShowsTheNumberTheHallIsOn              -- every judged frame, LAST, so it
                                                               never shadows a named message
9  TheRunnerCouldNotGetWhereHeWasGoing                      -- a walk leg's derived deadline
10 the run-level gate                                       -- at drive completion AND at the
                                                               sentinel
```

`EverySignInTheHallShowsTheNumberTheHallIsOn` runs last deliberately: it is the widest
statement in the set and would otherwise be the message printed for almost every defect.
Placed last, it is the gate for exactly the failures no narrower gate claims — and it is
still the gate an EMPTY submission dies on, at t = 2 s, because no narrower window is open
yet.

```text
assert: EverySignInTheHallShowsTheNumberTheHallIsOn -- every judged frame from the
        first checkpoint: for EVERY sign tagged HallSign whose own
        bBelongsToTheHall is true -- the four placed ones and each hoisted one from
        the frame it exists -- the FIRST whole number in its printed text equals the
        number the fixture's own model says the hall is on. A blank or unparseable
        readout on a hall sign FAILS this gate; it is never read as zero. This is the
        gate an empty submission dies on at t = 2 s. It is deliberately LAST in
        precedence: it is the widest statement in the set, so it speaks only for the
        failures no narrower gate claims. The message names every hall sign, what it
        printed, and what was required.

assert: TheNewSignComesUpOnTheNumberTheHallIsOn -- for each of the two signs the
        hoist raises: from 1.00 s after the sign exists until the next advance, its
        first whole number equals the number the hall is on at the moment it was
        raised (8 at the first hoist, 14 at the second) -- and blank FAILS, it is
        never read as zero. This is the OPEN-POPULATION gate: a design that captures
        the set of readers once at BeginPlay and pushes copies to it is right for the
        first half of the run and wrong from the moment the set changes, because the
        raised sign is not in the set and is never written to at all. The second hoist
        runs immediately after the second fall with no advance in between, so it asks
        the same question of a number that has survived a re-body. The message names
        the sign, the number it came up on, and the number the hall was on.

assert: TheDoorplateShowsTheRoundTheRunnerWalkedInOn -- THE CROSSING POINT of the
        two halves of the task. On every judged frame from 3.50 s after the body
        walking in the room last became a different object (the two seconds the
        prompt promises a fresh runner plus three times the half second it promises a
        readout), and never inside a fall window: the first whole number on the
        entrance stone's doorplate equals the number the hall was on AT THAT BODY
        CHANGE -- 4 while the opening runner is in the room, 11 from the first fall,
        14 from the second. Blank FAILS and is never read as zero. The fixture samples
        the required value off its own model of the hall's number at the instant it
        sees a different body, so it is the same value whether the submission put the
        fresh runner in on the frame of the fall or a second and a half later. This is
        the gate that a submission with a perfect number and a fall handler that only
        moves bodies fails, with no body gate involved; and the gate that a doorplate
        written like a hall sign fails at the first advance. The message names what
        the doorplate reads, which runner of the visit is in the room, what the hall
        was on when they walked in, and what the hall is on now.

assert: EachStepOnTheMarkRaisesTheNumberByWhatTheMarkNowCarries -- per entry into the
        mark's volume, which the fixture watches on the CAPSULE ITSELF and never by
        consulting the submission's bookkeeping: within 1.00 s (2x the half second the
        prompt promises) the hall's number (read
        off the hall's signs) rises by exactly the mark's CURRENT StepWritten and by
        no more; it does not rise again while the capsule stays inside; it rises
        again on the next entry; and it never changes on any frame when no entry was
        recorded. The fixture re-stages the step from 2 to 3 part way through, so a
        step cached at BeginPlay yields 10 where 11 is required. The message names
        the entry number, the mark's step at that instant, the number before and the
        number after.

assert: TheNumberSurvivesANewRunner -- across each of the two falls: the number read
        off the hall's signs at the first settled frame after the new runner exists
        equals the number read at the last judged frame before the fall, and the next
        entry onto the mark raises it from THAT number -- not from the entrance
        stone's number and not from zero. Any storage scoped to the body that fell
        fails here. The message names the number before the fall, the number after,
        and the number after the next advance.

assert: ANewRunnerOfTheSameKindStandsOnTheEntranceMark -- within 2.0 s of each fall
        (graded at 2.25 s to leave the fresh body a frame's grace): there is exactly
        ONE live player character in the world; it is a DIFFERENT object from the one
        that fell; its class is the SAME class as the runner the level began with;
        it is possessed by player 0; and its horizontal distance from
        AEntranceStoneActor::GetMarkCentre() is <= 150 uu with ITS FEET within 300 uu
        of it up or down -- both numbers are in the prompt ("within 150 centimetres of
        the middle of it across the floor", "its feet within three metres of it up or
        down"). The vertical is measured from the capsule's FOOT, not from the actor
        location, which on this substrate is the capsule centre ~96 uu up: measuring
        from the centre spent a third of the allowance before the runner had done
        anything wrong. The class half is what stops a hand-rolled uncontrollable body
        from grading identically. The message names the count, the two object names,
        both classes, the possessing controller, and BOTH distances against BOTH
        limits.

assert: TheRelicKeepsItsOwnNumber -- THE IN-SCENE NEGATIVE CONTROL, gauged on every
        frame from t = 0 to the end with no settle window at all: the back-wall sign
        -- same class, same readout path, same visual kind as the hall's four,
        distinguished only by its supplied bBelongsToTheHall flag -- prints its own
        staged PaintedNumber (1) on every sampled frame and never any other number. A
        submission that writes the round number to every sign in the world fails here
        at the first advance. The message names what the relic printed and what it
        was painted with.

assert: TheHallKeepsWhatWasGivenToIt -- continuous integrity, every frame: the
        entrance stone, the step mark, the hoist plate, the sinkhole, the four pillar
        signs and the relic all still exist and are within 2 uu of where the fixture
        staged them; the four placed signs still carry bBelongsToTheHall true and the
        relic still carries false; and the three staged numbers (the stone's
        StartNumber, the mark's StepWritten as the fixture currently intends it, the
        relic's PaintedNumber) still read what the fixture last staged. Stops a
        submission from rewriting the step to a number it likes, or repainting the
        stone instead of reading it. The message names the property, the staged value
        and the found value.

assert: TheRunnerCouldNotGetWhereHeWasGoing -- DRIVE FAULT, a NAMED GRADED FAIL and
        never a non-verdict: a walk step's derived deadline expired -- no live
        controlled body to steer after a fall, a body the player does not actually
        control (AddMovementInput reaches nothing), or a runner put back somewhere it
        cannot walk out of. Before any deadline overrun is written off,
        EverySignInTheHallShowsTheNumberTheHallIsOn and TheHallKeepsWhatWasGivenToIt
        are re-checked unconditionally, so a broken hall is named by its own gate
        rather than laundered into a drive fault.
```

**Staging faults are attributed, not scored.** Each of these is a fault in the LEVEL, the
STAGING or the DRIVE, never in the submission, and each ends the run as
`HARNESS-PRECONDITION` — attributed, kept out of every pass-rate denominator, and never
a model failure. They are checked in `PrepareTest`, before the drive starts, except where
noted.

*The cast.* Not exactly four hall signs plus exactly one relic at t = 0; an actor tagged
as a sign that is not one; a sign with no readable face; a missing stone, mark, plate or
hole; a trigger with no volume; an entrance stone with no floor mark.

*The staging.* The staged numbers not surviving into play (i.e. something overwrote them
between the pre-play window and `PrepareTest`); the fixture never receiving the pre-play
window in which it writes them at all; the two steps being equal; the relic's painted
number being a value the hall takes at any point in the run; the hall being on its own
START number at either hoist (which would make "the sign initialised itself from the
entrance stone" indistinguishable from a right answer); the hall reading the same number
at two different advances; or any of the three named wrong answers' trajectories
coinciding with the required value at a graded checkpoint. **The fixture
asserts these against its own staged triple rather than trusting the prose above** — a
re-staged hall either moves the gates with it or refuses to start.

*The opening state.* More than one pawn alive when the hall opens; no player character
possessed by player 0; a runner with no visible body (the 2026-08-06 visible-character
policy — a meshless conforming pawn grades clean and is unreviewable by a human); or the
sinkhole reporting runners already lost.

*Playability (Hard Rule #8, read off the level's own configuration and never off the live
instance).* The level having no rules object; its rules naming no kind of runner (so "a
new runner of the same kind" has no kind to be); a template-shaped runner with any of the
four movement/look actions unbound; rules naming no controller; or a controller that
applies no key mapping. Identity is by PROPERTY, never by class, so a substrate that does
not use the pattern stays silent. This is the gate form of the finding that five of six
ThirdPerson maps once shipped visible, animated and completely uncontrollable while
grading byte-identically with a playable one. Note the deliberate asymmetry: the level's
class defaults are the LEVEL's business, but a submission that rewrites the LIVE rules
object is that submission's failure — named by the body gates and by
`TheRunnerCouldNotGetWhereHeWasGoing`, not laundered into a non-verdict.

*The route*, sampled numerically along the drive's own lane rather than asserted in prose.
The lane itself coming within **600 uu** of any of the three triggers at any of 200 points
along it; the spur that walks in and out of one trigger coming within **200 uu** of either
of the other two, at any of 40 points (this is the property the prompt's layout claim —
"the hole is off any route between the other three" — actually stands on); the entrance
mark, where a fresh runner is put back, sitting within **600 uu** of any trigger, so that
nothing is waiting under a fresh runner's feet; or the sinkhole sitting more than **150
uu** above or below the entrance mark, since the runner only walks.

*Mid-run, the one that is not checked in `PrepareTest`.* The fixture's own re-stage of the
mark landing while somebody is standing on it.

**A harness exit can never launder a FAIL.** Before any deadline or sentinel overrun is
written off, `EverySignInTheHallShowsTheNumberTheHallIsOn` and
`TheHallKeepsWhatWasGivenToIt` are re-checked unconditionally, so a broken hall is named
by its own gate rather than by the drive.

## Requirement-to-assertion map

| Prompt requirement | Gate that checks it | When that gate does NOT run |
| --- | --- | --- |
| the number begins on the number painted on the entrance stone | `EverySignInTheHallShowsTheNumberTheHallIsOn` at the first checkpoint (the staged 4, not the committed 1) | never |
| read the start number off the stone, not out of the level | same gate — the staged value differs from the committed one, so a level-file read is wrong from the first frame | never |
| each step onto the mark raises it exactly once | `EachStepOnTheMarkRaisesTheNumberByWhatTheMarkNowCarries` | frames the settle rule suppresses |
| by the step the mark is carrying **at that moment** | same gate, from advance 3 onward, after the fixture re-stages 2 -> 3 | as above |
| standing on the mark does not keep raising it | same gate — the "does not rise again while the capsule stays inside" clause | as above |
| nothing else ever changes the number | same gate — the "never changes on a frame with no entry" clause | as above |
| every sign that belongs to the hall shows it, and all the same one | `EverySignInTheHallShowsTheNumberTheHallIsOn` | frames the settle rule suppresses |
| half a second to catch up | the 1.25 s agreement stand-off (2.5x it) and the 1.00 s rise deadline (2x it) — see *Settle and suppression* | never |
| a sign is read as the first whole number it prints; blank is not a number | the same gate's parse rule: blank FAILs, and is never read as zero | never |
| a new sign comes up already showing the current number | `TheNewSignComesUpOnTheNumberTheHallIsOn`, twice | outside the two post-hoist windows; the same fact is then carried by gate 1 forever after |
| and keeps up with every later change | `EverySignInTheHallShowsTheNumberTheHallIsOn`, which finds hoisted signs like any other | as above |
| the relic goes on showing its own painted number | `TheRelicKeepsItsOwnNumber`, every frame, no settle window | never |
| within two seconds a new runner is standing on the entrance mark | `ANewRunnerOfTheSameKindStandsOnTheEntranceMark`, twice | outside the two post-fall windows |
| of the same kind, under the player's control | same gate — the class and possession clauses | as above |
| within 150 centimetres of the middle of the mark across the floor | same gate — the horizontal clause | as above |
| standing on the mark, its feet within three metres of it up or down | same gate — the vertical clause, measured from the capsule's foot | as above |
| never more than one runner alive at a time | same gate — the exactly-one clause | as above |
| the number is not touched by a fall, and the next step carries on from there | `TheNumberSurvivesANewRunner` | outside the two falls |
| falling into the sinkhole ends that runner — an unconditional rule, so it holds at every fall | both body gates run at BOTH falls; a one-shot latch passes the first and fails the second. **The prompt deliberately no longer says "this can happen more than once"**: the rule is stated in the present tense with no qualifier, so nothing is undisclosed, and the nudge that disarmed the latch answer is gone | never |
| the doorplate shows the round the runner now in the hall walked in on | `TheDoorplateShowsTheRoundTheRunnerWalkedInOn` | the 3.50 s after each body change, and inside a fall window |
| the runner the hall opens with walked in on the number the hall starts on | same gate, from t = 3.50 s | before then |
| it goes on showing that until another runner walks in | same gate — it is judged on every frame outside those windows, not only just after a fall | as above |
| the doorplate is read as the first whole number it prints; blank is not a number | same gate's parse rule | as above |
| read the hall's numbers, do not rewrite them | `TheHallKeepsWhatWasGivenToIt` | never |
| do not move the marks, the pillars, the hoist or the sinkhole | same gate — the 2 uu placement clause | never |
| under the player's control and able to walk on | `TheRunnerCouldNotGetWhereHeWasGoing` | never |
| C++ under `Source/ThirdPerson/` | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

## Reference solution metadata

- **Files touched**: 2 — one new `.h` / `.cpp` pair under
  `Source/ThirdPerson/Tasks/t3-the-round-number-everyone-agrees-on/`. **No supplied
  prop file is modified**, which is the cleanest demonstration that the hall really is
  inert as shipped.
- **LOC**: 308 across the pair (84 comment, 44 blank), so ~180 lines of code, of which the doorplate is 12.
- **Senior-dev hours**: **6–9**, the top of T2 into the bottom of T3. Filed T3 for the
  width of the failure surface — nine gates over five advances, two hoists and two
  falls, where one slip in any of five pieces fails a different one. Where the hours go:
  1. ~1 h deciding where the number LIVES, which is the whole task in one decision. The
     three natural homes (a sign, the runner, something world-scoped) are not equally
     wrong: two of them pass most of the run.
  2. ~1 h on the readout population being open rather than closed — a set that grows at
     run time cannot be captured once at `BeginPlay`, and the hoist's announcement has
     to be joined to the same truth the four placed signs read.
  3. ~1.5 h on the body lane: ending a runner is supplied, but putting a new one of the
     **same kind** at a named spot, under player 0, exactly one alive, more than once,
     is where a first draft usually latches or double-spawns.
  4. ~1.5 h on the reading discipline: three numbers, each read at the point of use, one
     of which changes under the submission's feet.
  5. ~1 h on the doorplate, which is the only value in the run that neither half
     produces: it has to be written from the place that knows the hall's number, at a
     moment decided by the body lane, and it must NOT be written by the routine that
     keeps the signs in step. Every draft that treats it as a sixth sign is wrong from
     the first advance, and every draft that writes it only when the hall opens is wrong
     from the first fall.
  6. ~1–2 h wiring it all up and walking the level to check it is actually playable.
- **Why not lower**: no single one of these is hard; making all four agree, over a body
  that is destroyed twice and a reader set that grows twice, is the task.

## Anti-gaming notes

1. **The doorplate written once, when the hall opens.** *Failure mode*: THE HEADLINE
   WRONG ANSWER, and the one this task exists for. The prompt says in as many words that
   the round number is not touched by a runner being lost, so the natural fall handler
   does exactly one thing: put a fresh runner in. The doorplate is then written where
   every other opening state is written — once, at start-up, from the number the hall
   starts on — and it is *right* for the whole first half of the visit, through two
   advances, a hoist, the re-stage, a third advance and the first fall's body checks.
   *Defense*: `TheDoorplateShowsTheRoundTheRunnerWalkedInOn`, from 3.50 s after the first
   fall: the doorplate reads 4 where 11 is required. No body gate fires — the body lane
   is correct — and no sign gate fires, because every sign is correct. This is the gate
   form of difficulty-bar condition (b), and of condition (a): the value is the hall's
   number sampled at a body change, so it cannot be produced by either half alone.
2. **The doorplate written like a sixth sign.** *Failure mode*: the reader that folds
   the doorplate into the "tell everything the number" routine, because it is a readout
   on a thing in the hall and "everyone agrees" is the loudest sentence in the prompt.
   *Defense*: the same gate, at the FIRST advance — the doorplate reads 6 where 4 is
   required and never re-coincides. The fixture asserts that never-re-coincides property
   of its own staging in `PrepareTest`.
3. **A readout population captured once at `BeginPlay`.** *Failure mode*: the honest push
   design — find every sign at start-up, keep the list, print to the list on every
   change. It is correct for the four placed signs for the whole run. *Defense*:
   `TheNewSignComesUpOnTheNumberTheHallIsOn`, at the first hoist: the sign that goes up is
   not in the list, is never written to, and is still blank 1.00 s later. A blank hall
   sign is not a zero, so this is a named FAIL rather than a lucky pass. (**Note what is
   NOT claimed here.** An earlier draft of this file called "a private counter per sign,
   initialised from the entrance stone in the sign's own `BeginPlay`" the headline wrong
   answer. It is not reachable: the hoist spawns `Template->GetClass()` off a sign the
   LEVEL placed, so the raised sign is always the stock supplied sign, and to make a
   per-sign counter exist a submission would have to rewrite the supplied prop file it
   was told to leave alone. That row is retired, here and in the discrimination matrix.)
4. **The number kept on the body that walks around.** *Failure mode*: plausible because
   the mark's announcement hands you the character and "rounds cleared" feels like it
   belongs to the runner. It survives every advance. *Defense*:
   `TheNumberSurvivesANewRunner` — the sinkhole destroys the pawn and the new one comes
   up on 4 instead of 11. Note this is caught by a value gate, not by a lifetime check:
   the fixture never asks where the number lives, only what the signs say afterwards.
   The doorplate gate fails it too, one window later, which is the point of the join.
5. **The step read once at `BeginPlay` and remembered.** *Failure mode*: the single most
   natural micro-optimisation in the whole task. The prompt states, as an observable fact
   about the room, that the step written on the mark can change while the hall is
   running; it does not tell the agent what to do about that. *Defense*:
   `EachStepOnTheMarkRaisesTheNumberByWhatTheMarkNowCarries`. After the fixture
   re-stages the mark from 2 to 3, the cached answer produces 10 where 11 is required,
   while every sign still agrees with every other sign — so the gate that names it is
   the gate about the step, not the gate about agreement.
6. **A one-shot re-body latch.** *Failure mode*: a bool guarding the "send in a new
   runner" path, which is what a first draft writes to avoid double-spawning. It passes
   the first fall completely. *Defense*: `ANewRunnerOfTheSameKindStandsOnTheEntranceMark`
   is graded at BOTH falls; the second one has no live body inside 2 s and the drive
   then dies on `TheRunnerCouldNotGetWhereHeWasGoing`. This is precisely what the
   re-trigger convention exists to catch.
7. **Writing the round number onto every sign in the world.** *Failure mode*: the
   cheapest way to satisfy "everyone agrees" — enumerate signs, print. It is one line
   short of correct: `GetAllActorsWithTag("HallSign")` returns the relic too, and the
   filter is a call the submission has to make. *Defense*:
   `TheRelicKeepsItsOwnNumber`, the in-scene negative control, gauged every frame with
   no settle window. The relic is the same class with the same readout path and
   `Print` deliberately does **not** refuse a write, so the mistake really happens and
   is really seen. It fails at the first advance.
8. **Hard-coding the numbers.** *Failure mode*: reading 1 / +1 / 0 out of the committed
   map, or taking the corpus's own "starts at 1, advances to 2". *Defense*: every graded
   number is staged before `BeginPlay` and differs from what the map file holds, so a
   hard-coded answer is wrong at the first checkpoint — before the drive has done
   anything.
9. **Rewriting the hall's numbers instead of reading them** (setting `StepWritten`, or
   repainting the stone, so the arithmetic comes out). *Defense*:
   `TheHallKeepsWhatWasGivenToIt` compares all three staged numbers and every staged
   placement on every frame, and its message names the property that is NOT the
   submission's to write.
10. **Modelling the number correctly and never printing it.** *Failure mode*: the classic
   "state is right, output is missing". *Defense*: nothing private is ever graded — every
   gate is a statement about what a sign PRINTS. There is no ungraded switch on any prop
   that a submission can call instead of doing the work.

## Hidden invariants

- **The number is never read out of the submission; only its consequences are.** The
  fixture's model integer is compared against what the SIGNS print, never against any
  member the submission holds. A submission is free to represent the hall's number
  however it likes, and to put it wherever it likes — the only two homes that fail are
  the ones that fail a value gate.
- **Entries onto the mark are counted off the CAPSULE, not off the announcement.** The
  fixture edge-detects the character's overlap with the mark's volume itself, so a
  submission that suppresses, re-broadcasts or re-plumbs the mark's announcement is
  graded against the walk that actually happened.
- **The fixture asserts its own staging.** The property that no wrong answer's
  trajectory ever coincides with the required value at a graded checkpoint is checked in
  `PrepareTest` against the staged triple, not trusted to the prose above. A re-staged
  hall either moves the gates with it or refuses to start.
- **A blank hall sign is not a zero.** Parsing yields "no number", which FAILs gate 1.
  Reading blank as 0 would be a permissive fake the moment a wrong answer's value
  happened to be 0.
- **The relic is writable.** Nothing in the supplied sign protects it. If the negative
  control could not be broken, it would not be a control. Its honest strength is
  narrower than it looks: a submission that filters on the sign's own
  `BelongsToTheHall()` passes it without writing a line aimed at it, so what it really
  catches is the one-line miss of not filtering at all. The readout that a submission
  cannot pass by doing nothing is **the doorplate**, which must be actively written and
  written *differently* from the hall's signs — that is where the in-scene control's
  spread actually comes from.
- **The doorplate is the join, and it is graded on almost every frame.** Its window is
  not a post-fall window: once its 3.50 s grace has passed it is judged continuously
  until the next body change, so a stale doorplate is caught wherever the drive happens
  to be. Its required value is sampled off the FIXTURE's model of the hall's number at
  the instant the fixture sees a different body, never off anything the submission
  holds, and never off when the submission chose to write it.
- **`randomization:` is deliberately NOT declared.** `run_task.apply_randomization` is
  built and unit-tested but nothing in the repo calls it, exactly like L3 and R2;
  declaring the key would promise per-run variation the harness does not deliver. The
  staged-differs-from-committed triple plus the mid-run re-stage do that work instead,
  and a seeded per-run form can be added the day the key is wired.
