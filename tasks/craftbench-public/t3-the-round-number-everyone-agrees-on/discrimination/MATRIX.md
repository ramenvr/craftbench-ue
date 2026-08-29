# Discrimination matrix — t3-the-round-number-everyone-agrees-on

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs.

> **EVERY NUMBER AND EVERY VERDICT ON THIS PAGE IS *PREDICTED*, NOT MEASURED.**
> Nothing here has been run. `Content/Maps/t3-the-round-number-everyone-agrees-on/L_RoundHall.umap`
> does not exist yet, so no build, no PIE leg and no `cb discriminate` has ever
> touched this task. The times, the readouts, the stop numbers and the gate each
> leg lands on are all derived by reading
> `Source/CraftBenchTests/Tasks/t3-the-round-number-everyone-agrees-on/RoundHallFunctionalTest.cpp`
> against `authoring/author_map.py`'s solved layout. The orchestrator measures
> them afterwards and this file is corrected to what the run actually said.

## The two legs

| Submission | Overall (PREDICTED) | Named substring(s) (PREDICTED) | Why it lands there and not somewhere else |
| --- | --- | --- | --- |
| `../reference` | PASS | `Test Completed. Result={Success}` | One world-scoped keeper owns the number and nothing else keeps a copy. It reads the start off the entrance stone at play, reads the step off the mark **at every use**, prints on every sign that says it belongs to the hall (so the relic is never written to, because it is never in the set), prints the current number onto each sign the hoist announces, on a lost runner puts a fresh one of the level's own kind back on the stone's floor mark without touching the number, and writes the doorplate **in the two places where a runner starts walking** — once when the hall opens and once each time a fresh runner is actually in — never from the routine that keeps the signs in step. Nothing in it names a body class, a sign count or a number. Success message: `the hall came back on 17, all 6 of its signs said so, and the doorplate said 14`. |
| `empty` | FAIL | `EverySignInTheHallShowsTheNumberTheHallIsOn: the hall is on ` | The unmodified scaffold compiles, so L1 is green. Every supplied prop works — the mark announces a step-on, the hoist raises a sign, the hole takes a runner — and nothing decides anything. The hall's four signs blank their own faces in `BeginPlay` and stay blank. The relic prints its own staged `1`, so `TheRelicKeepsItsOwnNumber` **passes**; nothing has moved, so `TheHallKeepsWhatWasGivenToIt` **passes**; no fall and no entry has happened yet, so gates 3–6 are not armed; and the doorplate gate is still inside its 3.50 s opening grace, so gate 7 has not looked yet either. The widest gate is therefore the first one with anything to say, and it says it at `kFirstJudgedS` — **t = 2.00 s of world time**, before the drive has walked anywhere. If the agreement gate were ever removed the empty leg would die 1.5 s later on `TheDoorplateShowsTheRoundTheRunnerWalkedInOn`, which is also blank. |

**One PIE leg only**, `-nullrhi -deterministic -FPS=60`. `fps_legs:` is deliberately
not declared (`../task.md` § *Verifier specification*): nothing in this task asks the
submission to measure time, so a frame-count overfit is not one of its plausible wrong
answers, and a second leg would double a ~110 s drive for no discrimination. The
anti-overfit work is done by the mid-run re-stage instead.

### The empty leg's rendered line (PREDICTED — for eyeballing an `l2_pie.log`)

```
EverySignInTheHallShowsTheNumberTheHallIsOn: the hall is on 4 and sign <first hall
sign in name order> is blank at t=2.00. Every sign that belongs to the hall shows the
round number the hall is on, and a hall sign left blank is not showing it.
<sign>='' <sign>='' <sign>='' <sign>='' relic='1'
```

The MATRIX cell above quotes the **contiguous source literal up to the first format
placeholder**, so the oracle's grep cannot straddle a substituted value. The sign's
name is the actor's object name (the authoring script's label, sanitised by
`SetActorLabel`), which is why it is not quoted.

**Note the `4`, not `1`.** The number in that line is the number the FIXTURE staged
into the entrance stone in the pre-`BeginPlay` window, not the `1` the `.umap`
commits. That is the whole staged-differs-from-committed claim, visible in the empty
leg's own failure message.

## Requirements table

The full mapping is in `../task.md` § *Requirement-to-assertion map* (22 rows, each
naming the gate and the condition under which that gate is skipped). The short form:

| Prompt requirement | Gate | Skipped when |
| --- | --- | --- |
| the number begins on the number painted on the entrance stone | `EverySignInTheHallShowsTheNumberTheHallIsOn` | before t = 2.00 s |
| read that number off the stone, not out of the level | same gate — staged 4 vs committed 1 | as above |
| each step onto the mark raises it exactly once | `EachStepOnTheMarkRaisesTheNumberByWhatTheMarkNowCarries` | first 1.00 s after an entry |
| by the step the mark is carrying **at that moment** | same gate, from advance 3 (after the +2 → +3 re-stage) | as above |
| standing on it does not keep raising it | same gate — the while-still-inside clause | as above |
| nothing else ever changes the number | same gate — the no-entry clause | within 1.25 s of a model change, or 2.50 s of a fall |
| every hall sign shows it, all the same one | `EverySignInTheHallShowsTheNumberTheHallIsOn` | within 1.25 s of a change / 2.50 s of a fall / 1.25 s of a sign going up |
| a sign is read as the first whole number it prints; blank is not a number | the same gate's parse rule (blank FAILs, never reads as 0) | never |
| a new sign comes up already showing the current number | `TheNewSignComesUpOnTheNumberTheHallIsOn`, twice | outside the two post-hoist windows; gate 1 then carries it |
| and keeps up with every later change | `EverySignInTheHallShowsTheNumberTheHallIsOn` (it finds hoisted signs like any other) | as above |
| the relic goes on showing its own painted number | `TheRelicKeepsItsOwnNumber`, every frame, **no settle window** | never |
| the doorplate shows the round the runner now in the hall walked in on | `TheDoorplateShowsTheRoundTheRunnerWalkedInOn`, every frame | the 3.50 s after each body change, and inside a fall window |
| within two seconds a new runner of the same kind, on the mark, under the player's control, never more than one | `ANewRunnerOfTheSameKindStandsOnTheEntranceMark`, at BOTH falls | the one-runner clause never; the rest outside the two 2.25–3.50 s post-fall windows |
| the number is not touched by a fall, and the next step carries on from there | `TheNumberSurvivesANewRunner` (both halves) | outside the two falls |
| read the hall's numbers, do not rewrite them; do not move the fittings | `TheHallKeepsWhatWasGivenToIt`, every frame | never |
| the supplied hoist and hole go on working | same gate — the stood-on-it-and-nothing-happened clauses | when the runner is not standing in one |
| under the player's control and able to walk on | `TheRunnerCouldNotGetWhereHeWasGoing` | never |

## Which gate names which wrong answer (ALL PREDICTED)

Written down because the precedence order in `Tick` makes this deterministic, and
because a gate whose named failure is always stolen by a wider gate is a dead gate.
Precedence is relic → integrity → fall → body → step → late sign → **doorplate** →
agreement, and the agreement gate is **last on purpose**: it is the widest statement in
the set and would otherwise be the message printed for almost every defect.

| Wrong answer | Predicted to die at | Predicted where |
| --- | --- | --- |
| nothing at all (the empty leg) | `EverySignInTheHallShowsTheNumberTheHallIsOn` | t = 2.00 s, before the drive walks |
| hard-codes the committed `1` / `+1` / `0`, or the corpus's own "starts at 1, advances to 2" | `EverySignInTheHallShowsTheNumberTheHallIsOn` | t = 2.00 s — the staged start is 4 |
| models the number correctly and never prints it | `EverySignInTheHallShowsTheNumberTheHallIsOn` | t = 2.00 s. There is no ungraded switch on any prop it could call instead |
| **the doorplate written once, when the hall opens** (THE HEADLINE) | `TheDoorplateShowsTheRoundTheRunnerWalkedInOn` | 3.50 s after the body appears at **fall 1** (stop 9). The doorplate reads **4** where **11** is required. Nothing else fails: the body lane is correct, every sign is correct, and no body gate is involved. This is the answer the prompt's own "the round number is not touched by any of this" invites, and it is right through two advances, a hoist, the re-stage, a third advance and the whole of fall 1's body window |
| the doorplate written like a sixth hall sign, on every advance | same gate | ~1.25 s after **advance 1** (stop 1): the doorplate reads 6 where 4 is required, and it never re-coincides |
| **captures the sign population once at `BeginPlay` and pushes to that fixed set** | `TheNewSignComesUpOnTheNumberTheHallIsOn`, the *blank* branch | ~1.00 s after hoist 1 (stop 5) — the raised sign is not in the captured set, is never written to at all, and blank is not a zero |
| **the step read once at `BeginPlay` and remembered** | `EachStepOnTheMarkRaisesTheNumberByWhatTheMarkNowCarries` | ~1.00 s after **entry 3** (stop 7). A rise of 2 where the mark carries +3: 10 where 11 is required. The agreement gate is still standing off at 1.25 s, which is what makes the step gate — the one whose message names the mark's current step — the gate that speaks |
| **the number kept on the body that walks around** | `TheNumberSurvivesANewRunner` | 2.25 s after **fall 1** (stop 9). The hall was on 11 and comes back on 4. Caught by a VALUE gate, not a lifetime check: the fixture never asks where the number lives |
| the number survives the signs but not the bookkeeping (right readout, wrong internal home) | `TheNumberSurvivesANewRunner`, the second-half branch inside the step gate | ~1.00 s after **entry 4** (stop 10) — the next advance carries on from the wrong place |
| **a one-shot re-body latch** | `ANewRunnerOfTheSameKindStandsOnTheEntranceMark` | 2.25 s after **fall 2** (stop 12): zero runners alive. It passes fall 1 completely — this is exactly what the re-trigger convention exists to catch |
| a doorplate written at the first fall and latched | `TheDoorplateShowsTheRoundTheRunnerWalkedInOn` | 3.50 s after the body appears at **fall 2** (stop 12): the doorplate reads 11 where 14 is required. It passes fall 1 completely, which is why the two falls are staged on **different** numbers |
| a hand-rolled body of its own class, or a body nobody controls | same gate — the class / possession clauses | 2.25 s after fall 1 |
| double-spawns, or leaves a spare body parked out of the way | same gate — the one-runner clause, which is **continuous** | the frame the second body exists |
| a fresh runner put down somewhere other than the mark | same gate — the 150 uu / 200 uu clauses | 2.25 s after fall 1 |
| **writes the round number onto every sign in the world** | `TheRelicKeepsItsOwnNumber` | the frame of **advance 1** (stop 1). No settle window at all, and nothing in the supplied sign refuses the write, so the mistake really happens and is really seen |
| destroys the relic, or re-flags it as one of the hall's, to dodge the control | `TheRelicKeepsItsOwnNumber` — the gone / says-it-belongs branches | the frame it does it |
| rewrites `StepWritten`, or repaints the stone, so the arithmetic comes out | `TheHallKeepsWhatWasGivenToIt` | the frame it does it |
| moves a fitting, or destroys one | same gate — the 2 uu placement clause | the frame it does it |
| quietly stops the hoist or the hole to dodge the gates they feed | same gate — the stood-on-it-for-0.75 s / 1.50 s clauses | while the runner stands on the plate / in the hole |
| lets a hall sign go blank, or destroys one, after getting the run right | `EverySignInTheHallShowsTheNumberTheHallIsOn` | the first judged frame after it happens |

## What carries the discrimination without variants

**Two subsystems, joined at one VALUE rather than at one call.** The number's
*ownership* and the *body lane* meet on the doorplate, whose required value is
`the hall's number` evaluated `at the instant the body in the room becomes a different
object`. Neither operand is available to half of the task, so neither half can produce
it alone:

- a submission with a perfect number and a fall handler that only puts a body back —
  which is what "the round number is not touched by any of this" invites — fails
  `TheDoorplateShowsTheRoundTheRunnerWalkedInOn` **and nothing else**. No body gate
  fires, because the body lane is right; no sign gate fires, because the signs are
  right;
- a submission with a perfect body lane and a body-scoped number fails
  `TheNumberSurvivesANewRunner` and the doorplate gate;
- a submission that treats the doorplate as a sixth sign fails the doorplate gate at
  the FIRST advance, before any of the rest of the run has been tested.

That is difficulty-bar condition (a) in gate form, and it is the reason the earlier
claim in this file — that the crossing point was "the sinkhole destroys the actor the
natural first draft chose as the number's home" — was withdrawn. That crossing point
cost a submission zero lines of code: getting the ownership right and the body lane
wrong failed only the body gate and vice versa, i.e. two independent single-mechanism
tasks graded in one PIE leg.

**The readout population GROWS.** Four signs become five at stop 5 and six at stop 13.
A design that pushes copies out to a set captured once is right for the first half of
the run and wrong from the moment the set changes — and the gate that names it,
`TheNewSignComesUpOnTheNumberTheHallIsOn`, is armed only because the hoist **runs
itself**. If the submission had to call the hoist, an empty leg would raise no sign
and that gate would conflate "did not call the hoist" with "did not print the number".

**Every load-bearing number is staged before any `BeginPlay` and differs from the
committed one.** The `.umap` commits start `1`, step `+1`, relic `0`; the fixture
writes `4`, `+2` (later `+3`) and `1` in `OnWorldInitializedActors`. A hard-coded
answer, or one read out of the level file, is wrong at the FIRST judged frame — at
t = 2 s, before the drive has done anything. `authoring/author_map.py` refuses to
write a level whose committed numbers collide with the staged ones, so the two can
never quietly become the same.

**One of the three changes under the submission's feet.** With nobody standing on or
within 400 uu of the mark, at stop 6, the fixture rewrites the step from `+2` to `+3`
and starts comparing against 3 from that frame. The prompt discloses this in as many
words ("the step written on the mark can be changed while the hall is running, so read
it when you use it"), so only CACHING is punished and only by a move the agent was
told about.

**The trajectory is chosen so no modelled wrong answer ever re-coincides.**
Required `4 → 6 → 8 → 11 → 14 → 17`; cached-step `4, 6, 8, 10, 12, 14`; body-scoped
`4, 6, 8, 11, 7, 7`. The doorplate required `4, 4, 4, 4, 11, 14`; mirrors-the-hall
`4, 6, 8, 11, 14, 17`; written-once `4, 4, 4, 4, 4, 4`. Each first diverges at a
different point and never comes back. **The fixture asserts every one of those
properties of its own staging in `PrepareTest`** rather than trusting this paragraph,
and the authoring script asserts the identical thing before the level is written, so a
re-staged hall either moves the gates with it or refuses to start.

**There is NO "private counter per sign" row any more, and that is a correction.** An
earlier draft of this file called it THE HEADLINE wrong answer and claimed the raised
sign "runs the same `BeginPlay`, reads the entrance stone into its own field". It
cannot: `AHoistPlateActor::RaiseSign` spawns `Template->GetClass()` off a sign the LEVEL
placed, so the sign it raises is always the stock supplied `AHallSignActor`, which
blanks its own face. To make a per-sign counter exist at all a submission would have to
rewrite the supplied prop file the prompt tells it to leave alone — a strawman, which
the difficulty bar forbids as a difficulty source. The row is retired here, in
`../task.md` and in `authoring/author_map.py`. What
`TheNewSignComesUpOnTheNumberTheHallIsOn` really catches is the fixed-population answer,
which is a genuine draft, and it is now filed as such.

**Every trigger fires at least twice, AND THE SECOND FIRING ASKS SOMETHING NEW.** The
mark five times, the hoist twice, the hole twice — and `FinalGrade` refuses to declare
success unless it counted 5 / 2 / 2. Beyond the count:

- fall 2 lands on **14** where fall 1 landed on **11**, so the doorplate has to be
  *rewritten* and a doorplate written at the first fall dies at the second;
- hoist 2 sits immediately **after** fall 2 with no advance in between (stop 13, not
  stop 12 as in the first draft of the script), so the sign it raises must come up on a
  number that has survived a re-body — a question hoist 1 cannot ask because no body has
  been lost yet;
- mark entry 3 is the first after the re-stage, entry 4 the first after a fall.

Without those three the second firing of the hoist and of the hole re-ran an identical
stateless handler and bought no discrimination at all.

**The control is an in-scene twin, not a temporal before/after.** The relic is the same
class, on the same `Print` path, with the same readout component, distinguished only by
the `bBelongsToTheHall` flag the level set on it — and `Print` deliberately refuses
nothing, so the control really can be broken. It is gauged on **every frame with no
settle window at all**, because it should never change, ever. *Its honest strength is
narrow*: a submission that filters on `BelongsToTheHall()` passes it without writing a
line aimed at it, so what it really catches is the one-line miss of not filtering the
`HallSign`-tagged set at all. The readout a submission cannot pass by doing nothing is
the **doorplate** — it starts blank, nothing supplied ever writes it, and it must be
written *differently* from the hall's signs.

**Nothing private is ever graded.** Every gate is a statement about what a sign PRINTS,
read off its `UTextRenderComponent`. The fixture's model integer is never compared
against a member the submission holds, and there is no ungraded switch on any prop that
a submission could call instead of doing the work.

**Entries are counted off the CAPSULE, not off the mark's announcement.** The fixture
edge-detects the character against the union of *(the mark's own overlap set)* and
*(its box grown by capsule radius + half height + 60 uu)* — a strict superset of what
the prop can see — so a submission that suppresses, re-broadcasts or re-plumbs the
announcement is graded against the walk that actually happened, and the fixture's window
can only ever open EARLIER than the prop fires, never later.

## Honest limits of this matrix

1. **Nothing has been run.** Every cell is a prediction from source. The first real
   `cb discriminate` may land the empty leg on a different message than the one quoted
   if any assumption above is wrong — in particular, that the four placed signs really
   are blank at t = 2 s (they blank themselves in `AHallSignActor::BeginPlay`, which is
   read, not measured).
6. **The doorplate's opening value depends on a start-up order that is read, not
   measured.** `AEntranceStoneActor::BeginPlay` blanks the doorplate; the reference
   writes it from `UWorldSubsystem::OnWorldBeginPlay`, which UE dispatches after
   `AGameModeBase::StartPlay` has run every actor's `BeginPlay`. The reference does not
   rely on that: it repeats the write on the next tick, exactly as it already did for
   the signs. If the order were the other way round and the repeat were removed, the
   reference would fail its own doorplate gate at t = 3.50 s.
7. **`kFeetTolUu = 300` is now disclosed, and that is a fix, not a widening for its own
   sake.** The vertical bound was 200 uu measured against the pawn's ACTOR location —
   the capsule centre, ~96 uu up on this substrate — and no sentence in the prompt
   mentioned a vertical bound at all. A submission that respawned late with a plausible
   spawn lift met every clause the prompt stated and still took a named FAIL, at both
   falls. It is now measured from the capsule's FOOT, raised to 300 uu, stated in the
   prompt ("its feet within three metres of it up or down") and named in the failure
   message.
2. **The no-collision property is a guard on a KNOWN set, not a proof.** The fixture
   asserts that the three *modelled* wrong answers never re-coincide with the required
   value. A fourth wrong answer nobody has thought of could in principle coincide at a
   graded checkpoint.
3. **Respawning at the level's own `PlayerStart` is a CORRECT answer here, not a gamed
   one.** `authoring/author_map.py` asserts the `PlayerStart` sits within the gate's own
   150 uu of the stone's floor mark, precisely so that a submission which re-bodies
   through the level's start is not failed for it. The task never asks *where from*, only
   *where to*.
4. **Which sign is named in a failure message depends on actor name ordering**, which
   the authoring labels fix but which no gate depends on.
5. **The two body gates cannot attribute "no controlled body at all" at t = 0.** A level
   that failed to put a runner in and a submission that removed the one it was given look
   identical from `PrepareTest`, so that one case keeps its HARNESS-PRECONDITION
   non-verdict. Everything after `BeginPlay` — including a submission that spawns a spare
   runner — is GRADED, deliberately, so that no submission can buy a denominator opt-out.

## After the map exists

`cb discriminate craftbench-public/t3-the-round-number-everyone-agrees-on` must show
reference PASS and empty FAIL on `EverySignInTheHallShowsTheNumberTheHallIsOn`. Only
then, and only on a clean tree,
`cb refgate craftbench-public/t3-the-round-number-everyone-agrees-on` — once. A dirty
tree cannot certify and turns the gate into a full re-grade that caches nothing. The
owner plays the reference by hand before the task is called done.
