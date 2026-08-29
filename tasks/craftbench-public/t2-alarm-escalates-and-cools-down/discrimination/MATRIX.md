# Discrimination matrix — t2-alarm-escalates-and-cools-down

**REFERENCE + EMPTY ONLY** (owner directive 2026-08-18). No variant legs.

| Submission | Overall | Named substring(s) | Why |
| --- | --- | --- | --- |
| `../reference` | PASS | `Test Completed. Result={Success}` | The panel runs one tick: read the guards' and the board's numbers live, work out who can see the character from each guard's own two numbers plus whatever burning floodlight lengthens its round's reach, count the false-to-true edge with a clamp, run the quiet clock, move the setting one step at a time against two different tables, then throw every floodlight against its own setting number and set every guard's pace from its own base. Nothing in it knows which guard is which or which round is which, which is exactly why the watch change costs it nothing. |
| `empty` | FAIL | `TheYardShowsTheRightStage: the floodlights are not showing the setting` | The unmodified scaffold compiles, so L1 is green. `SetLit` and `PatrolSpeedUuPerSec` exist and work; nothing calls them. The yard begins **calm**, and calm is not "every floodlight dark" — one of the six burns from the calmest setting — so the very first standing phase (8 s at the quiet spot, model calm with nothing counted, no gate suppression in force) fails with one floodlight dark that should be burning. |

Both legs run twice, at `-FPS=60` and `-FPS=20`, in separate PIE processes; all
legs must pass.

## Requirements table

The full prompt-requirement to gate mapping is in `../task.md` under
**Requirement-to-assertion map**. It has 17 rows and every one names the gate
that checks it and the condition under which that gate is skipped.

## Which gate names which wrong answer

Written down because the precedence table makes this deterministic, and because
a gate whose named failure is always stolen by another gate is a dead gate.

| Wrong answer | Dies at | Where |
| --- | --- | --- |
| nothing at all (the empty stub) | `TheYardShowsTheRightStage` | phase 1, ~8 s in |
| one threshold ladder, `stage = f(count)` | `TheYardRemembersWhichWayItCame` | first-watch cooldown, model count 4 (falling, hunting; the ladder says watching) — about 5.75 s in |
| clears the alarm after one quiet window | `TheYardRemembersWhichWayItCame` | same frame, same reason |
| decrements the SETTING on the quiet timer | `TheYardRemembersWhichWayItCame` | same frame, same reason |
| drops all the way at the drop number | `TheAlarmComesDownOneStepAtATime` | first-watch cooldown, model count 2 (watching, not calm) |
| never comes down at all | `TheAlarmComesDownOneStepAtATime` | first-watch cooldown, model count 0 |
| no clamp on the sighting counter | `TheAlarmStopsCountingAtTheCap` | second-watch cooldown, ~15.75 s in (model count 2 = watching; the unclamped one is still at 5 = hunting). It behaves identically to a correct answer on the FIRST watch, which is deliberately not over-exposed, so it cannot die at the wrong gate first. |
| range only, no view-width test | `EachGuardSeesWithItsOwnEyes` | phase 7 — the narrow guard passes within 1,200–2,220 uu of the split spot constantly and its reach is 2,400, but the spot is 1,077 uu off its round and it can never hold anybody past 675 |
| one hard-coded cone (45 deg, or one guard's numbers for both) | `EachGuardSeesWithItsOwnEyes` | phase 7 if too wide, phase 13 if too narrow — the same spot with different eyes on it |
| counts seconds-in-view instead of edges | whichever gate is armed, first at `TheYardShowsTheRightStage` | phase 3, the first climb |
| lights the first N floodlights, or N floodlights | `TheYardShowsTheRightStage` | phase 1 — the correct lit counts are 1 / 4 / 6 and the settings are 1,2,0,2,1,1 in name order |
| one flat pace for both guards, or never writes a pace | `TheGuardsSpeedUpWithTheAlarm` | phase 3, at the first escalation (both guards read correct at calm, so the gate first bites when the setting moves) |
| caches the hunting scale at `BeginPlay` | `TheGuardsSpeedUpWithTheAlarm` | phase 13, once the second watch reaches hunting and the sergeant has raised the scale from 1.8 to 2.1. The pace gate runs on every judged frame, always last and only after the lamps have been agreed, precisely so this frame is not swallowed by `EachGuardSeesWithItsOwnEyes`. |
| caches the raise number at `BeginPlay` | `EachGuardSeesWithItsOwnEyes` | phase 13, one sighting early: the second watch raises at 3 and the cached answer raises at 2 |
| writes `BasePatrolSpeedUu` instead of `PatrolSpeedUuPerSec` | `TheYardIsNotYoursToRewire` | the frame it does it |
| a latched alarm, or a quiet clock armed once | `TheAlarmComesDownOneStepAtATime` first, `TheAlarmRoseAgainOnTheNewWatch` if it somehow got past | first-watch cooldown / the sentinel |
| parks a guard on the character | `TheYardIsNotYoursToRewire` | the frame it leaves its round by more than 60 uu |
| a correct internal enum and no output | `TheYardShowsTheRightStage` | phase 1 |

## What carries the discrimination without variants

**The floodlights are an INPUT, not just a readout.** Two of the six carry a
reach bonus and a round they cover; while they burn, the guard on that round sees
further. So the lamp loop and the perception pass are the same problem: get the
lamp loop wrong and the sighting count changes, which changes the setting, which
changes the lamps. The fixture refuses to start if no floodlight carries a bonus,
so the interaction can never be silently lost.

**Two guards whose widest-offset limits are 675 uu and 1,720 uu.** That is a
2.5x spread even with the narrow one fully lit, and the fixture refuses to start
below 2x. The split spot sits at the geometric mean of the two, so it is 1.6x
beyond one guard and 0.63x of the other — and the two guards **trade rounds** half
way through, so the identical spot means opposite things on the two watches.

**The raise numbers and the drop numbers are two different tables.** Raise at
2 and 5, drop at 2 and 0. Counts 3 and 4 mean *watching* climbing and *hunting*
cooling; count 1 means *calm* climbing and *watching* cooling. The drive enters
both bands from both directions, and the fixture asserts at the end that it did.

**The count re-syncs at both ends.** The count clamps at the cap and floors at
zero, and every phase of the drive ends at one of those two, so a divergence
between the fixture's counter and the submission's cannot outlive the phase it
started in. That is what makes a 280-second integer comparison safe without ever
reading the submission's own count.

**Every derived number is derived.** The three standing places, the lane, the
phase deadlines and the sentinel all come from the round's measured length, the
guards' own numbers, the panel's live dials and the character's measured
`GetMaxSpeed()`. The authoring script solves the identical geometry and refuses
to save a level that does not come out, so the level and the fixture cannot drift
apart into a run-time `HARNESS-PRECONDITION`.
