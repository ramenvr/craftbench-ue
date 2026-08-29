# Admission discrimination matrix

**PRODUCTION REFERENCE PASS / EMPTY NAMED FAIL. Promotion HOLD.** Admission
`r3` remains authoritative for the verifier-owned control. The production
reference then passed L1, exact-one L2, and fixed L2I `3/3`; the independent
no-behavior baseline passed L1 and failed the intended player-owned-router gate.

| Leg | Policy | Required verdict | Named evidence |
|---|---|---:|---|
| admission epoch 0 / player 0 first | key `E`, depths `2/1`, alternating focus | PASS | `r3`; all four named gates; only player 0 top count becomes 1, then only player 1 |
| admission epoch 1 / player 1 first | key `Q`, depths `1/2`, reversed focus | PASS | `r3`; all four named gates; only player 1 top count becomes 1, then only player 0 |
| same router/device shortcut | both events resolve player 0 | named FAIL | `GATE[EachPlayerOwnsIndependentActionRouter]` or `GATE[TopModalConsumesOnlyOwningPlayersAction]` |
| global stack | first dismiss changes both roots | named FAIL | `GATE[OtherPlayersStackNeverChanges]` |
| global focus | both users report one focused widget | named FAIL | `GATE[DismissRestoresOnlyThatPlayersFocus]` |

The eventual production matrix remains exactly `../reference` plus independent
empty. It must not reuse this verifier-owned admission implementation as an
answer oracle.

## Requirements table

| Gate | Reference expectation | Empty expectation | Current evidence |
|---|---|---|---|
| `EachPlayerOwnsIndependentActionRouter` | PASS | exact named FAIL | admission `r3` PASS; identities `(user/device/slate)=(0,1)` |
| `TopModalConsumesOnlyOwningPlayersAction` | PASS | exact named FAIL | admission `r3` PASS across reversed event order |
| `DismissRestoresOnlyThatPlayersFocus` | PASS | exact named FAIL | admission `r3` PASS across alternating focus targets |
| `OtherPlayersStackNeverChanges` | PASS | exact named FAIL | admission `r3` PASS across both depth layouts |
| L2I exact-two roots | PASS | FAIL | reference PASS; empty `return_graph=0` |
| L2I owning graph | PASS | FAIL | reference PASS; empty lifecycle/focus/input graph absent |
| L2I inventory | PASS | PASS | both legs exact two assets, no global substitute |

Evidence root: `<run-out>`. The exact terminal
marker is present once; `report/index.json` SHA-256 is
`D80206B330B6ED220F3DFA8A64761CD92D0D0227DBD22A02A5E1E02DA1894EB7`.

Production reference root:
`<run-out>` (`overall=PASS`, L2 `1/1`,
L2I `3/3`). Production empty root:
`<run-out>` (`L1=PASS`, L2 exact named
`GATE[EachPlayerOwnsIndependentActionRouter]`, L2I `1/3`). A prior literal-empty
submission stopped at the accepted-files sandbox and is not behavior evidence.
