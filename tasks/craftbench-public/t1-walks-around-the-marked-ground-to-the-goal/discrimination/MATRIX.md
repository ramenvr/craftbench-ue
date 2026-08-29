# Discrimination matrix — t1-walks-around-the-marked-ground-to-the-goal

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS | `Test Completed. Result={Success}` | The walker searches a grid over the yard with the out-of-bounds patch blocked, keeps the corners of the resulting route, walks them with the supplied `StepToward`, and **re-plans whenever the yard changes which patch is out of bounds**. Measured: detours to y=+1088 on trip 1 and y=-1070 on trip 2 — the opposite way round. |
| `empty` | FAIL | `ReachesTheGoalOnBothTrips: trip ` | The unmodified scaffold compiles, so L1 is green. `StepToward` exists and works; nothing calls it, so the figure stands on the start mark for the whole run and trip 1 times out having covered 0 uu. |

## Requirements table

| Prompt requirement | Gate that checks it | When that gate does NOT run |
| --- | --- | --- |
| never stand on the patch that is out of bounds | `NeverStepsOnTheGroundThatIsOutOfBounds` — every frame, against bounds the fixture measured before play | never, once the run reaches `StartTest` |
| the other patch may be crossed | `CrossesTheGroundThatIsAllowed` — at least one frame on it, per trip | judged at the sentinel; a run that never finishes a trip fails the arrival gate first, which is the more useful message |
| both crossings finish | `ReachesTheGoalOnBothTrips` — 70 s per trip, checked at each checkpoint so the failure names the trip | never |
| within **1.3x** the straight line | `StaysWithinTheDistanceBudget` — distance actually covered, accumulated per frame, reset per trip and not charged for the fixture's own teleport | never |
| the marking is not yours to change | `TheMarkingWasNotChanged` — every patch's flag against what the yard set, every frame | never |
| the marked ground stays walkable | `TheMarkedGroundWasNotMadeSolid` — a chest-height line across each patch, clear before play and every frame after | if a patch already blocked before play, which ends the run `HARNESS-PRECONDITION` rather than grading it |
| do not move the patches, marks or start | not directly gated; moving a patch moves the bounds the fixture measured at `PrepareTest`, so the walker is then graded against where the patch USED to be — which is strictly harder, not easier | **stated plainly**: a submission that moved a patch and then avoided its old footprint would pass. It gains nothing: the old footprint is what it must avoid either way |
| C++ under `Source/ThirdPerson/` | sandbox: a file outside the writable set is exit 4, not a graded FAIL | never |

## What makes this one harder than the eight before it

The owner's directive of 2026-08-18 is that a task a hand-written reference
passes easily is probably a task every flagship model passes. Three things
answer that here, and **none of them is a matter of opinion** — the authoring
script measures all three and refuses to save the level if any stops holding:

**Local steering does not solve it.** `author_map.py` simulates a greedy avoider
— head for the goal, sidestep when the next step lands on out-of-bounds paint,
trying turns out to ±90° — and refuses to save unless that walker gets *stuck*,
with either patch marked. Measured: stuck both ways, after 48,000 uu of
thrashing. The reason is the shape: each patch is a **U whose mouth straddles the
straight line**, so a steering walker enters the clean pocket, meets the back
wall, and meets an arm whichever way it slides. Escaping means moving away from
the goal, which is the one move a greedy rule never makes.

**Keeping off all marked ground does not solve it.** The script runs a grid
search three ways and prints all three: avoiding only A costs 1.13x the straight
line, only B 1.14x, and **both 1.31x against a 1.30x budget**. So a submission
has to determine *which* patch is out of bounds rather than avoiding anything
painted. `CrossesTheGroundThatIsAllowed` says the same thing in one sentence when
it fails.

**A route decided once does not solve it.** The yard swaps the marking between
trips. A submission that plans on the first trip and reuses the answer walks
straight over the newly-forbidden patch. The reference re-plans because it
compares the patch it planned against with the patch that is currently marked —
five lines, but a submission that never asks the question fails trip 2 with its
own message.

## Five staging faults that failed a CORRECT implementation first

Each is now an assertion in `author_map.py` or the fixture, so it cannot recur
silently:

1. **The fixture teleported the walker to the start MARKER's height.** The marker
   is a disc at z=6; the walker's capsule centre belongs at z=95. Its feet ended
   up 84 uu under the floor, it was penetrating from frame one, and every swept
   move was refused at zero distance — while its `Tick` ran and its route planned
   perfectly. The fixture now preserves the walker's own height.
2. **A flat marker standing 6 uu proud overlapped the walker's capsule**, whose
   feet are at z=5. Same symptom, different actor. Flat markers now sit at z=1.5
   with a 3 uu thickness, and the level refuses to save if anything solid
   overlaps where the walker stands.
3. **`set_collision_enabled(NO_COLLISION)` did not survive into the saved level.**
   The start marker was authored with it and still blocked the walker. The
   authoring helper now sets the collision **profile** to `NoCollision` as well.
   (`collision_enabled` is not an editor property on a `StaticMeshComponent`, so
   that third spelling is not available — the script tried and raised.)
4. **The reference's route compression threw the route away.**
   `FVector::Parallel` on consecutive grid steps kept only the endpoints, so a
   carefully planned detour collapsed to a straight line through the patch. Now
   an explicit `Dot(In, Out) < 0.999` on normalised directions.
5. **The marked patch's flag had to be readable.** It is a real `UPROPERTY` on
   purpose — the walker must read which patch is out of bounds, and the fixture
   must check nobody changed it — and `PrepareTest` refuses to start if it cannot
   find the property, rather than reading `false` forever and failing every
   correct answer. (That exact trap cost two earlier tasks a debugging cycle
   each.)
