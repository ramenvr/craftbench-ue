# Discrimination matrix - t2-shared-helper-lives-until-the-last-lease-ends

Status: **THIRDPERSON REFERENCE/EMPTY DISCRIMINATION CERTIFIED**.
The genuine ThirdPerson final map passed fresh cold readback. The isolated
ThirdPerson admission reference passed both targets and exact-one L2 with all
five behaviors. The git-head production reference passed all layers; the
supplied empty passed L1/L2I and failed only at the intended SHL-0 gate without
a harness precondition. Fixed denominators remain five L2 named behaviors and
exactly three L2I checks.

| submission | expected overall verdict | expected named evidence | executed |
|---|---|---|---|
| `../reference` | PASS | SHL-1 through SHL-5 green; L2I 3/3 | PASS: `<run-out>/` |
| supplied empty scaffold | FAIL | `SHL-0 runtime_contract_available`; L2I surface 3/3 | expected FAIL: `<run-out>/` |

Admission evidence is under
`<run-out>/test/`: report state Success,
1/1 passed, zero warnings/errors, four exact checkpoints, and terminal
`[CB-SHARED-LEASE] PASS checkpoints=4`. The protected admission map and three
source locks were unchanged. The admission map SHA is
`11BAC6FAB7BE11115CEE6C9D416996D4E52B1EDE8B5BD5490B289C094C227330`.
The retained final map independently cold-read at SHA
`EA22E1F1B81B8002EE74ACF0518DA9DCBB1E70B23E049BC010A1F540AD1CF940`.

The empty row is valid even though its structural L2I surface passes: its
stub `AcquireLease` returns null in the real subsystem, so the exact production
fixture fails before any GC assertion. Admission does not replace that stub in
the live project; only a copied scratch project receives the reference overlay.

## Requirements table

| Agent-visible requirement | Coverage | Assertion pointer | Skip condition | What a submission could otherwise get away with |
|---|---|---|---|---|
| Same key/version shares one helper | fully asserted live | `ValidateInitialSharing` / `SHL-1` | unconditional after non-null leases | allocate per owner or compare only fields |
| Unrelated key stays independent | fully asserted live | `ValidateInitialSharing` / `SHL-1` | unconditional | use one process-wide singleton |
| Ending one sibling lease preserves the other | fully asserted after witnessed full GC | `ValidateFirstRelease` / `SHL-2` | harness error if witness survives | clear the whole key on any release |
| Replacement gets fresh identity/payload while old remains unchanged | fully asserted live | `ValidateReplacement` / `SHL-3` | unconditional | mutate one helper in place or ignore version |
| Retired helper dies only after final old lease | fully asserted through weak invalidation | `ValidateRetiredCollected` / `SHL-4` | harness error if witness survives | leak old entries or destroy them at replacement |
| Current and unrelated helpers die after their final leases | fully asserted through weak invalidation | `ValidateFinalCollection` / `SHL-5` | harness error if witness survives | root helpers or keep stale cache entries forever |
| Use reflected strong cache/lease edges and weak owner | structurally asserted | fixed L2I checks 1-3 | all three IDs always emitted | hide ownership in raw/static storage that the collector cannot trace |
| Consume world-varying facts rather than literals | behaviorally asserted | fresh GUID keys/versions/payloads in `PrepareTest` | unconditional | hardcode one key, version, payload, or actor identity |

## Fixed L2I denominator

| ID | Exact evidence | Expected reference | Expected empty |
|---|---|---|---|
| `GameInstanceLeaseSurfacePresent` | native helper exact subsystem/functions vector | PASS | PASS |
| `ReflectedLeaseAndCacheOwnership` | native helper exact strong-property vector | PASS | PASS |
| `WeakOwnerAndNoRootPin` | native weak-owner vector plus accepted-source no-root/static scan | PASS | PASS |

L2I intentionally cannot turn the empty scaffold green overall. It validates
the supplied architectural surface; L2 validates that the submission actually
uses that surface to produce real UObject lifetime behavior.

## Bounded-coverage note

The current owner rule requires reference plus empty for a new task. No gaming
variant is claimed as executed evidence. The requirements table states the
independent mechanism for each shortcut. The matrix is pinned to git substrate
revision `ad98f50c6534`; batch-wide refgate and owner-play remain final audits.
