# Discrimination matrix

Status: **PRODUCTION DISCRIMINATION PASS.** Admission rounds 2-6 passed all six
gates. The correct reference passed L1/L2/L2I, while the exact supplied-empty
asset passed L1 and failed `FarPathFailsOutsideInvokerRadius` plus the two
expected ownership/radii L2I checks without a harness error.

## Fixed production denominators

| Layer | Denominator | Named checks |
|---|---:|---|
| L2 | 4 | `FarPathFailsOutsideInvokerRadius`; `NewNeighborhoodBecomesNavigable`; `OldNeighborhoodLosesNavigation`; `NewlyNavigableGroundCarriesRealMove` |
| L2I | 3 | `DesignatedAgentOwnsNavigationInvoker`; `InvokerRadiiAreLocalAndOrdered`; `SubmissionHasNoGlobalNavigationSubstitute` |

Admission adds exactly two setup markers,
`DynamicNavigationIsInvokerBounded` and
`DesignatedAgentOwnsNavigationInvoker`, before exercising the same four world
facts. Those markers prove the substrate can expose the mechanism; they are not
additional production score rows.

## Requirements table

| Fact | Independent evidence | Correct | Empty | Reasonable wrong shortcut |
|---|---|---|---|---|
| local engine owner | saved SCS component plus live registered invoker location/radii | PASS | FAIL L2I | component on decoy/global host fails exact owner and moved registration |
| dynamic local-only generation | exact nav-system mode plus dynamic Recast active set | PASS | protected world remains valid but no task invoker | prebuilt/global field makes initial distant/far paths available |
| new ground follows scout | new complete path and populated tiles only after moved invoker | PASS | FAIL | near-only diagnostic bool cannot change engine path result |
| old ground retires | old path false and old populated tile layers zero | PASS | FAIL after never generating | permanent visited tiles fail retirement |
| far never appears | complete-path negative sampled every 0.25 world-second | PASS | PASS alone | full/global or oversized field fails named far gate |
| real traversal | AI move request, path-following Moving samples, dense bounded CharacterMovement | PASS | FAIL | transform teleport fails request/status/step chain |

## Required reference/empty matrix after admission

| Submission | Expected overall | Exact named reason |
|---|---|---|
| `../reference` | PASS | L1, L2 4/4, L2I 3/3 |
| fresh empty submission | FAIL | `DesignatedAgentOwnsNavigationInvoker` and `InvokerRadiiAreLocalAndOrdered` |

Per current owner policy there are no authored gaming-variant legs. The named
gates carry discrimination, but each shortcut below must be exercised during
admission/reference review before promotion.

| Shortcut | Expected first named failure | Why it cannot wrong-reason PASS |
|---|---|---|
| whole-map pre-bake | `FarPathFailsOutsideInvokerRadius` | new/far complete before scout move |
| unrestricted global dynamic generation | `FarPathFailsOutsideInvokerRadius` | far dense negative observes eventual global build |
| only validate near positive | `OldNeighborhoodLosesNavigation` | old path + tile-layer retirement are independent |
| leave every visited tile alive | `OldNeighborhoodLosesNavigation` | old populated layers must reach zero |
| direct-transform movement | `NewlyNavigableGroundCarriesRealMove` | real request/status and dense step bound required |
| attach generator to decoy | `DesignatedAgentOwnsNavigationInvoker` | SCS and live registration/location both pin owner |

## Admission GO criteria

1. First Editor build is green with no new warning.
2. Fresh real/off-screen author process saves exactly one map, reports one
   scout/fixture/bounds/floor/player-start, persistent custom nav config, and
   serialized navigation-data count zero; protected hashes remain unchanged.
3. Fresh cold readback loads the same map bytes and reports the exact contract.
4. Exact-one NullRHI round emits each of six admission markers once, terminal
   marker once, JSON-authoritative 1/0 automation counts, and no harness/error/
   ensure/fatal/timeout token.
5. Five fresh runs cover both policy shapes. Generation and retirement windows,
   frame-step envelope, movement count, path/tile transitions, and far negatives
   have separated margins before any production tolerance is frozen.
6. A deliberate global/full-field control and no-invoker control fail their
   predicted named gate rather than filter/build/harness setup.
