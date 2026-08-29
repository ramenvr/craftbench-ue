# Discrimination matrix

Status: **COMMITTED-HEAD REFERENCE PASS / ANSWER-FREE NAMED FAIL**.

## Requirements table

| Requirement | Verifier evidence | Shortcut rejected |
|---|---|---|
| Deinitialize once | reporter lifecycle count and exact old identity | leaked/static subsystem |
| Old completion harmless | late/cancel terminal fact plus no new-world mutation | global current-world callback |
| New request succeeds | exact new record/value applied by new subsystem | cancel/ignore all requests |
| Old objects collect | weak world/subsystem/actor/record probes after GC | strong capture or rooting |

Policies reverse record identities and vary delay/travel ordering. Reference and
empty must run through the same travel reporter; a same-world approximation is a
harness rejection, not a graded result.

## Observed local matrix

| Leg | Result | Named evidence |
|---|---|---|
| Reference | PASS 4/4 | old deinitialize, harmless old completion, exact new record, old-object collection all PASS |
| Restored empty | Behavior FAIL 3/4 | only `NewWorldResolvesItsAssignedRecord` FAIL; no harness marker |

Closure 03 used a single ordinary `-game` process per leg and genuine
`OpenLevel` travel. Reference completion reported a valid weak subsystem, world,
destination, matching epoch, and resolved record. The empty leg ran only after
the scaffold source was restored byte-for-byte and both Editor/Game targets
explicitly recompiled it. Input package vectors were identical before/after.

The canonical verifier independently materialized commit `0673a332` from Git
HEAD and reported L1 PASS (Editor+Game, 0 warnings), custom L2 PASS (1/1,
4/4), and fixed L2I PASS (3/3). Its report is retained at
`<run-out>/report.json`.
