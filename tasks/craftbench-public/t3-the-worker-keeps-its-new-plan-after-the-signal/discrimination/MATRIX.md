# Discrimination matrix

Status: **AUTHORED / CERTIFIED / PUBLIC.** The Git-head reference passes L1,
exact-one L2, and L2I 3/3
(`<run-out>/report.json`, SHA-256
`8848363C89A1297AA375BBDFDA795F9B3B7D82E8297410B92984D9EFC9B9D3A2`).
The independent empty shell passes L1, fails L2 at
`IdleStateActiveBeforeSignal`, and fails L2I 0/3 without a harness failure
(`<run-out>/report.json`, SHA-256
`5DCB23608D97FB79583E190028FEF9AA9A8036478E249BE012C32B1167C05983`).
Corrected admission rounds 2..6 each executed exactly one test with 1/1
Success, zero report errors/warnings, no harness/named failure, unchanged
asset/map hashes, one signal-condition pass, one navigation-task entry, zero
exits, and distances `0,0,169.29,331.29,583.29,835.29`.

The live editable shell is SHA-256
`DDB5D4AB75A280C18E4EB8892596F90F04BFDD165381390EA611BE8C7F4474BD`;
the structurally correct reference is
`792FBF826EF14AA31F50E386BF6194EF109744554A5CD32B588D3E3CA2D2B0A1`;
and the cold-read playable final map is
`17C0B716BBCCD8D45B8AC61C17BD91FA3A8E78BA87343609493C440C3D8376F9`.

### Historical round 1 harness evidence

The exact admission StateTree remains 26,799 bytes, SHA-256
`30EC0FC1E242B90B5CB9F889AD1B9FF8DD4BD02237D19272B5D2B0347D80C87F`.
The successful public-API map build reported editor `active_tiles=8`; its exact
58,332-byte map and fresh cold-read hash are
`C4CE511B52F6BFEAB6A1CF4242AF61F3E11C7554CC077702A6DCDC6BA173E294`
(`<run-out>:2138,2146` and
`<run-out>/readback.log:2106-2107`).

Round 1 found the exact intended test once, but its authoritative report is
`Error/HARNESS-PRECONDITION`, not a task failure: PIE had the exact default
Recast actor with `active_tiles=0`
(`runs/authoring/t3-the-worker-keeps-its-new-plan-after-the-signal/admission/round-1/report/index.json:30-43`).
Startup also logged `UStateTreeComponent` with no asset before fixture
`ConfigureStateTree` (`l2.log:2168`). The runner serializer failure occurred
after the raw report and has since been repaired by root; it does not convert
this run into behavior evidence. Both package hashes stayed unchanged. UE5.8
source and corrected live rounds subsequently closed both harness facts:
automatic component start is disabled until exact asset assignment, while
serialized nav validity, endpoint projection, and a complete path replace the
generator-only tile count as the fail-closed navigation gate.

## Requirements table

| Fact | Layer and evidence | Correct reference | Empty | Reasonable wrong solution |
|---|---|---|---|---|
| `UsesStateTree` | L2I exact compiled schema/hierarchy; L2 live component | PASS | FAIL | Tick Blueprint fails `StateTreeOwnsWorkerBehavior` |
| `ReadsSeparateSignalActor` | L2I exact condition; L2 condition callback count | PASS | FAIL | local bool/timer fails `IdleTransitionReadsSeparateSignal` |
| `IdleStateActiveBeforeSignal` | L2 pre-pulse node/path telemetry | PASS | PASS only if shell idles | always-active fails named L2 gate |
| `SubjectStationaryBeforeSignal` | L2 world displacement | PASS | PASS | always-moving controller fails named L2 gate |
| `TransitionedAndRemainsActive` | exact task enter once/exit zero after clear | PASS | FAIL | while-signal-only tree exits or restarts |
| `ContinuesMoving` | path request/status plus post-clear displacement | PASS | FAIL | teleport or one-shot nudge fails dense/post-clear gates |

## Fixed L2I denominator

| ID | PASS condition | Fail-closed detail |
|---|---|---|
| `StateTreeOwnsWorkerBehavior` | exact ready StateTree, AI schema, Root with Idle then Active | missing/wrong asset, schema, state, or cardinality |
| `IdleTransitionReadsSeparateSignal` | one Idle OnTick Goto Active transition with exact signal condition | eventless state jump, timer, local bool, alternate condition |
| `ActiveStateUsesNavigationTask` | one exact navigation task in Active; exact task asset inventory | alternate task, extra task asset, submitted source/behavior asset |

## Required variants

| Variant | Expected result | Named reason |
|---|---|---|
| Reference | L1 PASS, L2 PASS, L2I 3/3 | real signal → StateTree → navigation chain |
| Empty StateTree shell | overall FAIL | `IdleTransitionReadsSeparateSignal` and `ActiveStateUsesNavigationTask` |
| Always navigate | overall FAIL | `IdleStateActiveBeforeSignal` / `SubjectStationaryBeforeSignal` |
| Active exits when pulse clears | overall FAIL | `TransitionedAndRemainsActive` |
| Tick polls signal then calls move | overall FAIL | `StateTreeOwnsWorkerBehavior` |
| Teleport on signal | overall FAIL | `ContinuesMoving` plus no navigation task |
| StateTree changes mirror variable; BP moves | overall FAIL | `ActiveStateUsesNavigationTask` |

## Admission GO criteria

1. Exact admission StateTree authors, saves, cold-loads, and reports the expected
   hierarchy/condition/task with unchanged hash.
2. Fresh map author/readback proves exact-one bounds plus navigation-owned
   `ARecastNavMesh`; runtime proves it is valid default nav data, projects both
   endpoints, and supplies a complete synchronous path.
3. Exact-one automation test runs from the admission map with no harness error,
   ensure, fatal, or warning.
4. Pre-signal displacement stays within a stable noise envelope.
5. Signal true is observed by the exact condition before the navigation task
   enters exactly once.
6. After signal false, task exits remain zero and displacement continues over
   multiple world-clock checkpoints.
7. Five fresh runs establish tolerances; always-move, while-signal-only,
   teleport, and empty controls fail their predicted named gates.
