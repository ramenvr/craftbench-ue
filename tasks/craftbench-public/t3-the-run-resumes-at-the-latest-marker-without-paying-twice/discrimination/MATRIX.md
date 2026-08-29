# Discrimination matrix

Status: **REFERENCE PASS / ANSWER-FREE NAMED FAIL**.

The reference result is reproduced from committed Git HEAD `d4b76f1c` by the
canonical runner: L1 PASS, custom two-process L2 PASS (2/2 processes, 7/7 fixed
gates), and L2I PASS (3/3).

## Requirements table

| Requirement | Cross-process evidence | Shortcut rejected |
|---|---|---|
| Fresh isolated slot | pre-write absence plus nonce and exact save inventory | stale or hardcoded slot |
| Latest checkpoint saved | protected record ID/transform after second checkpoint | first-only or transform-only save |
| Collected set saved | exact protected record identity set | fixed list or world scan |
| Resume at latest marker | new player/process at supplied transform | retained player or literal transform |
| Total restored | exact changed reward-value sum | fixed/recomputed total |
| No double payment | retired identities attempted after resume with zero delta | respawned or merely hidden reward |
| Control pays once | uncollected actor remains and produces one exact delta | destroy/hide all rewards |

## Protocol legs

| Leg | Process identity | Allowed persistent input | Required terminal evidence |
|---|---|---|---|
| Write | fresh UE process A | immutable protocol, absent nonce slot | exact-one JSON Success, saved-record facts, slot created |
| Resume | fresh UE process B | same immutable protocol, engine slot | exact-one JSON Success, restore/retirement/control facts |
| Cleanup | verifier owner | exact slot path recorded by protocol | retained evidence, exact slot absent, no broad deletion |

## Negative protocol tests

- Reuse one process for both legs: harness rejection.
- Carry a Python-computed total/identity set into resume expectations: harness
  contract rejection unless it originated in immutable pre-write policy.
- Resume with wrong nonce or slot: named harness failure.
- Missing, multiple, skipped, or wrong full test path in either report: rejection.
- Slot already exists before write: rejection without launching UE.
- Slot missing or unchanged after write: rejection before resume.
- Timeout/crash/owned-tree leak: infrastructure failure with evidence retained.
- Cleanup touches any non-owned slot: safety failure.

## Measured discrimination

| Submission | L1 | Two-process L2 | L2I | Verdict |
|---|---:|---:|---:|---|
| solved reference | Editor+Game PASS | 2/2 processes, 7/7 gates PASS | 3/3 PASS | accepts |
| answer-free scaffold | Editor+Game PASS | write exact1 FAIL at `NewestCheckpointRecordIsSerialized`; resume not launched | solution checks fail by construction | rejects |

The baseline binary was explicitly rebuilt after overlaying the live empty
implementation; UBT compiled `RunResumePersistenceComponent.cpp` for both
targets before the negative protocol. The negative result therefore cannot be
a stale reference DLL.
