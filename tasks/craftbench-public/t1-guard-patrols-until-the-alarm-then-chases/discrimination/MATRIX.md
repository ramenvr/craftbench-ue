# Discrimination matrix — t1-guard-patrols-until-the-alarm-then-chases

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS | `Test Completed. Result={Success}` | The guard walks to the post it is heading for at patrol speed, and while the supplied alarm is sounding and the character is inside its own alert range it walks at the character instead, at chase speed, aiming at where they are now. Nothing is remembered from the chase, so resuming is the same code as starting. |
| `empty` | FAIL | `ChasesWhileTheAlarmRings: alarm ` | The unmodified scaffold compiles, so L1 is green. `StepToward` exists and works; nothing calls it, so the guard stands where the level put it. The first alarm rings for 10.4 s and the gap goes from 1400 uu to 1341 — all of it the character moving. |

## Requirements table

Every requirement the prompt states, the assertion that checks it, and the
condition under which that assertion does not run. A row with no gate is a hole;
a row whose gate can be skipped is where a submission will aim.

| Prompt requirement | Gate that checks it | When that gate does NOT run |
| --- | --- | --- |
| pace between the two posts | `PatrolsBetweenThePosts` — both posts reached, at 220 uu of the post's live location | never; judged at the sentinel, which is 85 s past the end of the drive |
| stay within **450 units** of the line while the alarm is quiet | `StaysOnPatrolWhileTargetFar`, every frame | for the first 8 s after an alarm clears — the measured time a correct guard needs to walk home. A guard that never returns is still caught, because the quiet windows are 13.8 s long |
| never come within **900 units** of the character while quiet | same gate, second clause | same |
| close to **< 55%** of the gap while the alarm rings | `ChasesWhileTheAlarmRings`, per alarm | for an alarm shorter than 4 s — the fixture's own alarms are 10.4 s, so this only excuses a spell the drive cut short |
| **face** the character while closing | same gate, second clause: ≥ 70% of frames within 40° | for the first 1.2 s of each alarm, and if zero frames were sampled |
| **both** alarms send the guard | `ChasesEveryTimeTheAlarmRings` — at least 2 alarms must qualify | never |
| go back to pacing when the alarm stops | `ResumesPatrolWhenTheAlarmClears` — a post reached AFTER the first alarm ended, tracked separately from having reached one before it | never |
| the alarm is the plate's, not the submission's | `AlarmMatchesThePlate` — the panel's lamp vs the fixture's own box test over the plate | for 1 s of disagreement, so the boundary frame is not a verdict |
| never approach the second figure | `NeverApproachesTheOtherFigure` — 300 uu of slack against its starting distance | never |
| do not move the posts, panel, figure or character | not directly gated; moving the posts changes where the guard must go and the gates follow the live positions, and moving the character is measured by every distance gate | **a hole, stated plainly**: a submission that teleported the *second figure* rather than approaching it would pass `NeverApproachesTheOtherFigure`. It would gain nothing — no other gate rewards it |
| write the solution **in C++ under `Source/ThirdPerson/`** | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

## What carries the discrimination without variants

**The quiet half is graded as hard as the active half.** This is the whole
design. `StaysOnPatrolWhileTargetFar` is what the corpus row's hardened rubric
dropped, and dropping it is what let a guard that charges from frame one score
full marks — the alarm would never have been measured at all. A submission now
has to be in *two* different places depending on a condition it does not
control.

**Every gate is a position or a heading.** No behaviour-state name, enum or
blackboard key is read anywhere, so a behaviour tree, a state machine and three
`if`s in `Tick` all pass identically, and none of them can pass by *claiming* a
state. The chase gate deliberately checks facing as well as distance, because a
guard drifting past the character sideways closes the gap without going after
anybody.

**Twice, not once.** The yard rings the alarm twice and `ChasesEveryTimeTheAlarmRings`
requires both to qualify, so a one-shot implementation — the commonest wrong
answer for a "then" task — is caught with its own message rather than passing on
the strength of the first transition.

**Both directions have their own gate.** `PatrolsBetweenThePosts` requires a
post reached *before* the first alarm and `ResumesPatrolWhenTheAlarmClears`
requires one *after* it, tracked separately. "Went back to pacing" is a
different claim from "was pacing at the start", and one gate covering both would
be satisfied by the start alone.

**The trigger is supplied and is defended.** The plate and panel are complete,
working, and nothing in them knows the guard exists. `AlarmMatchesThePlate`
fails a submission that drives the panel from its own sensing — which is a
different task (`t1-guard-only-spots-what-it-can-see`) and would make this one a
duplicate of it.

**The staging is jittered.** `PrepareTest` nudges both posts before play and the
spec withholds every coordinate, so a submission keyed on where things stand
rather than on finding them reads a stale number. The reference caches the post
**actors** and reads their locations live for exactly this reason.

## What the second figure does and does not catch — honestly

The corpus row asks for a second target parked permanently outside alert range,
gauged every checkpoint. It is built and it is gauged. But it is a **secondary**
control, not the one carrying the task:

- It **does** catch a guard that wanders, or one that goes after the nearest
  actor with a body regardless of range, since it is 2595 uu from the nearest
  point of the guard's route against a 2000 uu alert range.
- It **does not** catch much on its own, because the real target is always
  nearer than it is. A submission that chases "the closest figure" picks the
  right one for the wrong reason and this gate stays silent.

What actually stops a wrong answer here is the pair of gates above:
`StaysOnPatrolWhileTargetFar` (which forbids approaching *anything*) and
`ChasesEveryTimeTheAlarmRings` (which requires the transition twice).

## The staging is measured, not tuned

`authoring/author_map.py` refuses to save the level unless it has verified, from
the real placed actors rather than from the constants at the top of the file:

- the guard's collision bottom clears the floor (a guard penetrating the floor
  cannot move at all, and its `Tick` runs perfectly while it does not);
- the guard starts clear of both posts;
- the plate is inside the alert range **from both posts, at every corner of the
  fixture's jitter**, with 150 uu of margin — the first version measured from
  the midpoint of the patrol line and would have forbidden a guard at the far
  end of its own route from responding at all;
- the wait spot and the second figure are outside that range by the same margin;
- neither the character's straight path to the plate nor the guard's straight
  path from either post passes within 102 cm of the panel's board, at its real
  yaw;
- everything the fixture relocates is `MOVABLE`, because PIE scores moving a
  static actor as a failed test;
- the level has two lights and names no game mode.
