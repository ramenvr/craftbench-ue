# notes — t1-walks-around-the-marked-ground-to-the-goal

Authored 2026-08-18 on the ThirdPerson substrate, UE 5.8. **The first task built
against the owner's 2026-08-18 difficulty bar**; the eight before it are
single-mechanism and should be treated as a floor tier.

## Provenance

Startup Eval corpus row `t1-nav-avoids-region-to-goal`, adopted per
an internal design note (not shipped) row 11
(`ADOPT+FIX · no-control`, MED/4h).

| The review said | What was built | Why |
|---|---|---|
| second identically-marked patch that is NOT forbidden and may be crossed, forcing the submission to read which region is which | built, and made LOAD-BEARING: a route avoiding both costs 1.31x against a 1.30x budget, and `CrossesTheGroundThatIsAllowed` fails a run that never sets foot on the allowed one | in the corpus row this was a control. Here it is the reason the flag has to be read at all. |
| gate "no point in the polygon" and "no step over the limit" on having TRAVELLED, or an empty submission banks 2/6 | there is no partial credit: the run is one verdict, and the empty submission fails the first gate it reaches (`ReachesTheGoalOnBothTrips`, trip 1, 0 uu covered) | a rubric that pays for not moving is the defect the review names. One verdict cannot. |
| making the region solid instead of expensive satisfies every travelled-route check; graft the collision-baseline invariance gate | `TheMarkedGroundWasNotMadeSolid` traces a chest-height line across each patch before play and every frame after, and the authoring script refuses to save a level whose patches have ANY colliding geometry | without the second half the gate could be vacuous — it would compare "blocked" with "blocked". |
| print the region-removed control leg beside the graded route | not built as a leg; the authoring script prints all three route lengths (avoid A / avoid B / avoid both) every time the level is authored | owner directive 2026-08-18: reference + empty only, no variant legs. The information the review wanted is in the authoring log, where it is checked rather than merely printed. |
| **NAVMESH** — the corpus row assumes a nav modifier | **not used.** The task grades the SHAPE of the route, and the prompt is behaviour-only, so a grid search, a nav modifier, or a visibility graph all pass identically | measured: a `NavMeshBoundsVolume` places from python but no `RecastNavMesh` is ever produced in a `-run=pythonscript` editor (the nav system does not tick there) and `build_navigation()` is not exposed. Making it work needs `bAutoCreateNavigationData` in `Config/DefaultEngine.ini` — a SUBSTRATE change that invalidates every refgate certificate on both machines. Not worth it for one task, and not necessary for the behaviour. |

## The difficulty is measured, not asserted

`authoring/author_map.py` runs a grid Dijkstra and a greedy-walker simulation
every time it authors the level, and **refuses to save** unless all four hold:

```
straight line 6800 uu, budget 8840 uu (1.3x)
  avoid A only: 7711 uu (1.13x)   avoid B only: 7741 uu (1.14x)   avoid BOTH: 8900 uu (1.31x)
  greedy local avoider with A out of bounds: stuck after 48000 uu
  greedy local avoider with B out of bounds: stuck after 48000 uu
```

Three layouts were rejected by that check before one passed:

- U's too small relative to the corridor — avoiding both cost only 1.09x, so
  reading the flag was optional.
- U's mouths off the straight line — the greedy walker deflected early, never
  entered the pocket, and **arrived**. Wall-following solved the level.
- U's staggered but too close in Y — avoiding both cost 1.26x, still inside the
  budget.

The shipped layout puts each U's mouth ON the line and staggers them in X and Y.
The measured reference detours to **y=+1088 on trip 1 and y=-1070 on trip 2** —
opposite directions, which is the swap doing its job.

## Five things that failed a CORRECT implementation before they were found

All five are now assertions. Details and the fixes are in
`discrimination/MATRIX.md`; in short:

1. the fixture teleported the walker to the start **marker's** height, burying
   its capsule 84 uu under the floor;
2. a flat marker standing 6 uu proud overlapped the walker's capsule, whose feet
   are at z=5;
3. `set_collision_enabled(NO_COLLISION)` did not survive into the saved level —
   the collision **profile** has to be set as well;
4. the reference's route compression (`FVector::Parallel`) collapsed the detour
   to a straight line;
5. the patch's out-of-bounds flag had to be a real `UPROPERTY`, and the fixture
   refuses to start if it cannot read it rather than reading `false` forever.

(1) and (2) are the same law that cost the patrol task two cycles the same
night: **an actor that starts inside anything is penetrating from frame one, and
a swept move out of a penetration is refused at zero distance** — which presents
as an actor that never moves while its `Tick` runs and its logic works perfectly.
There is now an authoring assertion for it: nothing solid may overlap where the
walker stands.

## Still to do

The owner's difficulty bar has an empirical half that this task has NOT yet
passed: **run one cheap model against it** (`cb eval --model claude-p:<model>`).
Passing first try with zero iteration means the task needs another axis. Until
that has been run, "this task is hard" is an argument, not a measurement.
