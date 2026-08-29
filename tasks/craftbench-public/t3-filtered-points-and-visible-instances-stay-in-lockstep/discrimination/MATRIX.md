# Discrimination matrix

Status: **AUTHORED / REFERENCE PASS / BASELINE NAMED FAIL**.

## Requirements table

| Requirement | Verifier-owned evidence | Reasonable wrong implementation rejected |
|---|---|---|
| Reject low density | input oracle and output/instance stable-ID sets | density filter missing or fixed threshold |
| Reject exclusion metadata | exact `Excluded` values and output membership | density-only filtering |
| Retain every eligible point | per-ID oracle/output join | handpicked IDs or fixed count |
| Do not duplicate eligible points | per-ID and transform multiplicity | branch union or repeated spawner input |
| Spawn exactly published output | independent Graph Output and managed-instance counts | output-only or unfiltered spawning |
| Preserve transforms | finite one-to-one output/instance transform join | manual, offset, randomized, or stale instances |

## Planned fixture policies

| Fact | Fixture A | Fixture B |
|---|---|---|
| Threshold | provisional lower threshold | provisional higher threshold |
| Component seed | Quartz policy | Violet policy |
| Bounds | translated compact volume | rotated/translated alternate volume |
| Point IDs | non-contiguous set A | disjoint non-contiguous set B |
| Eligible count | at least three | different count, at least two |
| Boundary case | density exactly threshold | density exactly threshold |
| Negative controls | low, excluded, outside | different low, excluded, outside |

Pinned policy A retained 3/3 output/instances at threshold 0.55 and policy B
retained 4/4 at threshold 0.72. Each recorded independent Graph Output and
managed-ISM transforms after ordinary scheduled generation.

## Fixed denominators

- L2: 6 named gates from `task.md`.
- L2I: 3 named checks from `task.md`.
- L1: exact graph asset and Editor/Game build contract.

## Evidence required before promotion

1. **PASS:** scheduled completion, Graph Output, and managed-instance evidence.
2. **PASS:** admission/final graph and map independent cold readback with hashes
   unchanged.
3. **PASS:** production reference L1, L2 2/2, and L2I 3/3.
4. **PASS:** independent answer-free baseline L1; exact named L2 failure and
   solution-shape L2I failures without a harness error.
5. **PASS:** local publication under `tasks/craftbench-public/`.
6. **BATCH CLOSEOUT PENDING:** committed-HEAD official refgate and integration
   into the actual `craftbench-public` branch.
