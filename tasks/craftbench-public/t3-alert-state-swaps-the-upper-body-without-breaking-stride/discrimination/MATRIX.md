# Alert Stride discrimination matrix

Status: **AUTHORED-WIP / LIVE-SUBSTRATE REFERENCE-EMPTY MATRIX PASS**. Structural authoring, cold
readback, five repeated admission passes, protected reference harvest, and
reference/empty discrimination are green. Fresh governed live-substrate full
reference and supplied-empty runs reproduce the expected matrix. Git-HEAD
refgate and owner-play remain mandatory.

## Requirements table

| Agent-visible requirement | Coverage | Assertion pointer | Skip condition | Shortcut otherwise possible |
|---|---|---|---|---|
| Alert behavior owns the state change | fully asserted live + structural | `AlertStateBecomesActive`; `StateTreeHasCalmAlertBidirectional` | no submission-reachable skip | bool/enum mirror or Tick branch |
| Alert swaps only the declared upper-body layer | fully asserted live + structural | `BehaviorStateLinksAndDrivesDeclaredLayer`; `HostUsesDeclaredLinkedLayer` | no submission-reachable skip | whole AnimBP switch or unrelated pose |
| Calm returns after clear without restarting | fully asserted live | `ClearRestoresOriginalLayerWithoutRestart` plus pinned main instance | no submission-reachable skip | destroy/recreate the main instance |
| Walking remains continuous below the overlay | fully asserted live + structural | `LowerBodyStrideRemainsContinuous`; `LocomotionRemainsBasePose` | no submission-reachable skip | full-body pose, pause, teleport |
| Do not use a montage | fully asserted live + structural | montage absence; `LayerImplementationsAvoidMontageRoutes` | no submission-reachable skip | visually plausible Slot/montage overlay |
| Consume both world-varying fact vectors | fully asserted live | exact `SlowEarly` and `FastLate` fixtures | harness error only for ambiguous verifier actors | hard-code first speed/direction/times |

| Submission | L1 expected | L2 expected | L2I expected | Load-bearing rejection |
|---|---:|---:|---:|---|
| Reference four-asset overlay | PASS | PASS 2/2 | PASS 4/4 | Calm->Alert->Calm uses real StateTree and pinned linked-layer interface while stride continues. |
| Retained empty baseline | PASS | FAIL | FAIL | `BehaviorStateLinksAndDrivesDeclaredLayer`; no linked host route and no Alert state/task. |
| State mirror bool / direct graph bool | PASS | FAIL | FAIL | `AlertStateBecomesActive`; saved StateTree is not bidirectional. |
| Whole AnimBlueprint switch | PASS | FAIL | FAIL | `BehaviorStateLinksAndDrivesDeclaredLayer`; main AnimInstance identity changes and host linked route is absent. |
| Montage-only overlay | PASS | FAIL | FAIL | `BehaviorStateLinksAndDrivesDeclaredLayer`; active montage and Slot topology are forbidden. |
| Full-body alert replacement / stride restart | PASS | FAIL | possible PASS | `LowerBodyStrideRemainsContinuous`; foot/actor frame steps exceed the same-run calm baseline. |
| Hard-coded first timing/layout | PASS | FAIL second fixture | possible PASS | `AlertStateBecomesActive` or restoration gate under `FastLate` world facts. |

## Executed admission evidence

| Run | Exact count | Engine state/layer | Movement | Pose/result |
|---|---:|---|---|---|
| `<run-out>` | 1/1 | Calm -> Alert and calm linked instance -> alert linked instance | grounded, 285 cm/s, bounded 4.75 cm actor step | FAIL: hand delta 0.038 cm; no gate relaxation |
| `<run-out>` | 1/1 | authoring probe | unchanged | FAIL: exposed Translation pin overwrote the direct ModifyBone value |
| `<run-out>` through `round-07` | 5/5 | Calm -> Alert -> Calm; exact linked instances | grounded, 285 cm/s; lower maxima 0.008/0.007/0.008 cm | PASS: pose 17.999 cm, restore 0.064 cm in every run |

## Executed WIP discrimination evidence

| Leg | Result | Evidence |
|---|---|---|
| Governed reference WIP | L1 PASS; L2I 4/4; original L2 0 tests | `<run-out>/report.json`; old map actor-label mismatch, not behavior evidence |
| Corrected-map reference L2 | authoritative JSON PASS 2/2, NullRHI | `<run-out>/l2_result.json` |
| Corrected-map empty L2 | authoritative JSON FAIL 2/2; no harness precondition | `<run-out>/l2_result.json`; named linked-layer gate |
| Empty fixed L2I | overall FAIL, 1/4 | `<run-out>/l2i.log`; only montage-route avoidance remains true |
| Fresh governed reference | L1 PASS; L2 2/2 PASS; L2I 4/4 PASS | `<run-out>/report.json` |
| Fresh governed supplied empty | L1 PASS; L2 0/2 named linked-layer FAIL; L2I 1/4 | `<run-out>/report.json`; no harness precondition |

The corrected retained map SHA-256 is
`9EC800C1595BC4F843D31EFB26C02A4FE0A66F72DE8080A1B8DFCCE5CFF8EA2A`.
Reference L2 result SHA-256 is
`FFCF61CA06B5E6DF746C72803B2B6EF9AAC22F649FC42654F0461F3D295AC004`;
empty L2 result SHA-256 is
`32D2F4BD59D1E68AA4C33A6E0B0B3B50C2A202A3101A710E454DEC3E523A5AC0`;
empty L2I log SHA-256 is
`5AE2F2E5E35E550FB88B846C73FBAD89A55E3E6CC44E0E124A77DA03BA9C9C92`.

Required before promotion: git-HEAD refgate after the retained map/reference
are tracked, owner-play, tasklint, and the final leak/cheat audit. The
adversarial rows remain explicit contract coverage and are not silently
reclassified as executed legs.
