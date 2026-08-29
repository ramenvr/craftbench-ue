# Discrimination matrix - t2-one-bundle-loads-without-pulling-in-the-rest

The owner-approved minimum matrix is reference plus empty. This table is the
pre-execution contract; no behavior result is claimed until protected assets,
maps, cold readback, and exact-one admission have succeeded.

| Submission | Expected verdict | Expected first failing gate | Required message substring | Rationale |
|---|---|---|---|---|
| `../reference` | PASS | -- | -- | exact selected bundle, shared two-owner residency, first-release survival, and last-release bundle-only unload |
| empty | FAIL | first acquire's same-call manager/Asset Manager state | SelectedBundleAloneBecomesResident | untouched manager creates no lease and no managed bundle handle; admission control is absent from the production map |

## Reasonable wrong implementations

| Wrong implementation | Required named gate |
|---|---|
| load every protected record | `UnselectedBundleStaysNonResident` |
| load both bundles or omit the bundle list | `UnselectedBundleStaysNonResident` |
| remove/unload on the first owner's release | `OneReleaseKeepsSharedDependencyAlive` |
| retain a streamable handle or hard payload reference after the last release | `LastReleaseUnloadsOnlyManagedBundle` |
| call broad `UnloadPrimaryAsset` | `LastReleaseUnloadsOnlyManagedBundle` |
| use `TryLoad`/`LoadSynchronous` | `SelectedBundleAloneBecomesResident` |

## Requirements table

| # | Requirement | Enforcement | Gate skipped when | Remaining allowance |
|---|---|---|---|---|
| 1 | Load the live PrimaryAssetId and only its live selected bundle through Asset Manager | same-call managed handle/bundle-state check plus exact selected residency | never | immediate or later completion |
| 2 | Keep every unselected record/bundle/dependency nonresident | continuous exact object-path and other-ID handle checks | never | the selected primary record itself remains managed |
| 3 | Share residency across two exact owners | manager owner/key contract and external residency after staggered release | never | internal container organization may differ |
| 4 | First release keeps the shared dependency alive | post-GC selected payload/dependency and exact bundle state | never | either world-selected owner may release first |
| 5 | Last release removes only this bundle without leaking a handle | zero-bundle primary-only managed state, post-GC secondary nonresidency, stability window | never | Asset Manager may complete removal in the call or later |
| 6 | Read world-varying id/bundle/release order | protected scenario overwrites consumer decoys and controls release order | never | request-local caching during one lease |

## Status

- **BUILD + ASSET AUTHORING PASS:** Editor/Game builds pass; all 15 protected
  assets pass fresh cold readback; the isolated admission map author passes with
  exact admission-only cardinality and protected map SHA
  `80977E9D7830F133AE4F140E3AE64F28D6871F3EA18CA775CCE6BE982B0153FA`.
  Independent fresh-process map cold readback also passes with all 16 protected
  hashes unchanged.
- **ADMISSION PASS:** round 2 proved that the initial terminal stall was the
  UE Editor `RF_Standalone` GC keep policy even after exact bundle removal.
  With the verifier's selected-secondary-only, in-memory PIE keep-flag seam,
  real-RHI round 3 passed exact one test (`1/1/0`) and all 16 protected hashes
  remained unchanged. Evidence:
  `<run-out>/`.
- **FINAL MAP PASS:** the production map author and independent cold readback
  pass with exact scenario/final-fixture/host/two-consumer cardinality, no
  admission fixture, and all 16 hashes unchanged. Map SHA-256:
  `D16B8B4FE9E12B62C73B238EFF7CE3BFAD4ED3638D2085AD2A430D3AE595E123`.
- **PRODUCTION DISCRIMINATION PASS:** the separately staged reference passed
  L1 Editor+Game and exact-one L2. The separately staged empty submission
  passed L1 and failed exact-one L2 at
  `SelectedBundleAloneBecomesResident` at t=0.37 seconds, matching the frozen
  matrix. Evidence roots:
  `<run-out>/` and
  `<run-out>/`.
- **PROMOTION HOLD:** the live substrate was intentionally used while the new
  task files are untracked. Owner tracking/commit and git-HEAD refgate remain.
