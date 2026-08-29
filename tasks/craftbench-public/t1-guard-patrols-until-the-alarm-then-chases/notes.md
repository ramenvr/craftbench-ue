# notes — t1-guard-patrols-until-the-alarm-then-chases

Authored 2026-08-18 on the ThirdPerson substrate, UE 5.8.

## Provenance

Startup Eval corpus row `t1-bt-patrol-then-chase`, adopted per
an internal design note (not shipped) row 9
(`ADOPT+FIX`, MED/8h). Every deviation from that row is listed below.

| The review said | What was built | Why |
|---|---|---|
| restore `StaysOnPatrolWhileTargetFar`, which the hardened rubric DROPPED | restored, and it is the gate the task is built around | with it gone, a guard that charges from frame one passes everything else and the alarm is never measured. It is the *quiet* half that makes the *active* half mean something. |
| do NOT adopt the contract Mission verbatim — it moves the trigger to agent-authored sensing and recreates an already-merged row | the trigger is a **supplied plate** the character stands on; the panel is complete and working, and `AlarmMatchesThePlate` fails a submission that drives the panel itself | agent-authored sensing is exactly `t1-guard-only-spots-what-it-can-see`, which shipped the same day. Two tasks measuring the same thing is one task and one duplicate. |
| replace the behaviour-state name read with a position/heading test | no state name, enum or blackboard key is read anywhere; every gate is distance-from-the-line, distance-to-the-character, or angle-off-facing | a name is a claim; a position is a fact. |
| rename, because `bt` puts the mechanism in the agent-visible path | renamed | a behaviour tree, a state enum, or three `if`s all pass identically, and the id should not hint otherwise. |
| control: a second target parked permanently outside alert range, distance to BOTH gauged every checkpoint | built, tagged `DecoyFigure`, gauged every frame | see the honest note on what it does and does not catch, in `discrimination/MATRIX.md`. |

## Five things that were measured, not assumed

Each of these failed a **correct** implementation before it was found, which is
the only reason they are worth writing down.

1. **A root component's relative location is the actor's location.** The guard's
   body was a static mesh made root and offset up by 90 cm, the way the sight
   guard's is. That offset is silently ignored: the collision stayed centred on
   the actor origin, i.e. half inside the floor. Every swept move came back
   `bStartPenetrating=1, PenetrationDepth=90.00` and moved the guard zero
   distance — for 3600 consecutive frames, with its `Tick` running the whole
   time and resolving its posts and its alarm correctly. The fix is a capsule
   root and the actor placed at half its own height; the level now asserts the
   placed guard's real bounds clear the floor.

2. **The guard was spawned inside a patrol post.** Same symptom, different
   cause, and found first: starting it *on* post A put its 70 cm body inside the
   post's 50 cm one. The level now asserts a body-radius + post-radius + 90 cm
   clearance from the guard's start to every post.

3. **PIE scores moving a STATIC actor as a failed test.** `PrepareTest` nudges
   the posts; they were authored `STATIC`; PIE logged
   *"mobility must be Movable"* twice and `AFunctionalTest` turned that into
   `Result={Fail}` — on a reference run that had just patrolled, chased twice
   and walked home correctly. Nothing in the failure text mentions mobility
   unless you go looking past the automation summary. The level now asserts that
   everything the fixture relocates is movable.

4. **A settle window can fail a correct answer for being slow.** The quiet rule
   started applying 2.5 s after an alarm cleared. Measured: a chase leaves the
   guard ~1136 uu off its line, and it walks home toward a *post* rather than
   straight at the line, so it is still 490 uu out at 5 s and inside the 450 uu
   band at 8. The settle is now 8 s, chosen off that trace. This is the fourth
   time in two days a window has failed a correct answer — the rule is to widen
   only in the direction that cannot mask a wrong answer, and a longer settle
   only ever shortens the window in which the guard is *judged*.

5. **The alarm's occupancy counter is unreadable by reflection.** `Occupants` is
   a plain private `int32` with no `UPROPERTY`, so `FindFProperty` returns
   `nullptr` and a fixture keyed on it would have read "quiet" forever and
   failed every correct answer. The fixture reads the panel's **lamp intensity**
   instead — which is also what a reviewer sees. Identical trap to `bSpotted` in
   `t1-guard-only-spots-what-it-can-see`, caught the same way: by asking what
   the assertion is actually reading before running anything.

## Two staging facts the layout depends on

- **The panel cannot stand on the axis everything else uses.** Whichever way it
  faces, its board ends up between the plate and either the character walking up
  to it or the guard coming for the character. The first layout put the board
  across the character's path: the character stopped 200 cm short, the alarm
  never rang, and the empty submission failed on the *fixture's* inability to
  ring rather than on its own. The panel now stands off-axis, its plate 300 cm
  clear of its board, and the authoring script measures both straight paths
  against the board's real footprint at its real yaw.

- **The alert range must cover the plate from BOTH ends of the route.** The
  first geometry check measured from the *midpoint* of the patrol line — the
  most flattering point on it. It passed, while the far post sat 2143 uu from
  the plate against a 2000 uu alert range: a guard standing at the wrong end of
  its own route would have been forbidden to respond to the alarm at all, and a
  correct submission would have failed intermittently depending on where the
  pacing happened to have got to. The check now measures from **each post, at
  every corner of the fixture's jitter**, and demands 150 uu of margin.

## Floor paint is not geometry

The yard's stripes are 3 cm proud of the floor. A character's capsule steps over
them without noticing. Anything moved by a swept `SetActorLocation` — which is
what the supplied `StepToward` does — treats a 3 cm lip as a wall. All floor
paint in this level (stripes, patrol line, range arc) is authored with collision
off. This did not turn out to be the cause of the stuck guard, but it would have
been the next one.
