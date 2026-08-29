# Discrimination matrix - t3-both-walkers-yield-and-still-arrive

Status: **AUTHORED / PUBLISHED / COMMITTED-SUBSTRATE DISCRIMINATION PASS**.
The baseline and Detour admission assets, dynamic-navigation
admission map, final two-layout map, and reference pass fresh cold readback.
Five fresh exact-one fixed-60 NullRHI Detour runs pass
with identical decisive telemetry. The earlier one-sided CharacterMovement RVO
result remains a valid rejected-design control, not a harness failure. Four
explicit admission-only controls each fail their assigned named gate without a
harness failure or retained-input drift.

Certified production reference evidence at
`<run-out>/report.json` is Git-HEAD L1
PASS (Editor and Game, zero warnings) and L2 PASS 2/2. The independent
baseline-only submission at
`<run-out>/report.json` is Git-HEAD L1 PASS
and L2 FAIL 0/2; both layouts stop at the exact
`BothAgentsConflictDrivenSteering` gate and never report a harness failure.
Both use committed substrate `4ad7763bdaf3`.

| submission | expected overall verdict | expected named evidence |
|---|---|---|
| `../reference` | PASS | both fixtures pass all four gates |
| empty baseline | FAIL | `BothAgentsConflictDrivenSteering` |
| avoidance disabled | FAIL | `BothAgentsConflictDrivenSteering` |
| permanent detour | FAIL | `BothAgentsReachOwnGoals` |
| one walker freezes | FAIL | `BothAgentsKeepForwardProgress` |
| collision disabled | FAIL | `NoOverlapEnRoute` |
| teleport to goals | FAIL | `BothAgentsKeepForwardProgress` |

## Requirements table

| Requirement | Independent evidence | Shortcut rejected |
|---|---|---|
| Both walkers react before contact | actual velocity versus public global path-segment direction plus live crowd registration/data for each pair member | physics push or only one yielding |
| Deviation is conflict-driven | pair trajectory minus matched translated solo trajectory | baked curve, timer, or actor-wide oscillation |
| Both keep progressing | per-agent normalized progress, stall duration, walking mode, and path status | freeze one or stagger starts |
| Capsules retain clearance | dense center separation minus live capsule radii and collision response | disable collision or overlap briefly between checkpoints |
| Each reaches its own goal | controller request identity and final distance for pair and controls | shared goal, teleport, or abandoned request |
| Generalizes across facts | two rotated layouts with different speeds, lengths, and radii | literals tuned to one crossing |

## Frozen admission matrix

Rounds 02-06 are 5/5 PASS with repeated checkpoint-4 steering
`36.00/11.82 deg` and lateral deltas `128.44/19.17 uu`; minimum observed
clearance is `72.10 uu`, stall `0.017 s`, and frame step `4.75/3.83 uu`.
No-avoidance, freeze-one, collision-disabled, and permanent-detour controls
each produce their one predicted gate. Frozen thresholds are `3.0 deg`,
`1.5 deg`, `12 uu`, `4 uu`, `0.75 s`, `28 uu`, and `115 uu` respectively.
Exact evidence hashes are in `../authoring/admission_calibration.json`.
