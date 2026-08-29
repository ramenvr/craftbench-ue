---
id: t2-one-bundle-loads-without-pulling-in-the-rest
substrate: ThirdPerson
set: craftbench-public
tier: T2
capability_bucket: Content Integration
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_BundleLeases :: ABundleLeaseFunctionalTest"]
deadline_s: 1200
action_budget: 55
accepted_files: [Source/ThirdPerson/Tasks/t2-one-bundle-loads-without-pulling-in-the-rest/BundleLeaseRuntime.cpp]
introspect: [t2_primary_asset_bundle_lease.py]
---

# t2-one-bundle-loads-without-pulling-in-the-rest

> **Status: AUTHORED / CERTIFIED / PUBLIC.** The required ThirdPerson runtime,
> protected assets, final map, cold readbacks, and exact-one runtime admission
> are green. Git-head reference passes L1/L2/L2I, while the separately staged
> supplied-empty implementation passes L1 and fails the intended
> `SelectedBundleAloneBecomesResident` gate without a harness failure. The
> former CraftBenchTemplate evidence is prototype history only.

Implement a shared, owner-counted asynchronous Primary Asset bundle lease. The
world selects one managed record, one named bundle, and which of two consumers
releases first. Only that selected bundle may become resident. Both consumers
share its residency, the first release must keep it alive, and the last release
must remove only the bundle managed by this lease.

## Primary concept

- `ps-asset-management` - Asset Management
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/asset-management-in-unreal-engine)

### Composed concepts

| Concept | Role in the composition |
|---|---|
| `ps-asset-management` | Owns pending/current bundle state and the managed streamable handle. |
| `ps-primary-asset-id` | Carries a world-authored record identity without a hard object reference. |
| `asynchronous-asset-loading` | Completes a selected-bundle request immediately or on a later engine tick. |
| `ps-garbage-collection` | Makes leaked handles and premature release observable through exact payload residency. |

### Production-pattern justification

Large Unreal projects often split a Primary Asset into named bundles so a
screen, mode, or player needs only one subset of its secondary content. Several
consumers can overlap, so the code owning the request must share a handle and
remove the bundle only after the final lease ends. `LoadPrimaryAsset` and
`ChangeBundleStateForPrimaryAssets` are the engine-owned state transitions for
that pattern; a path load, an all-bundle load, or a permanent hard reference is
not equivalent.

### Concept-interaction notes

The selected PrimaryAssetId and bundle name come from verifier-owned world
state. Bundle metadata maps that pair to one soft payload; the payload contains
one hard hidden dependency, making selective residency observable without
revealing values in the prompt. Owner identity and release order then determine
how long the selected bundle remains resident. Async completion, bundle state,
shared lease lifetime, and garbage collection are one causal chain.

## Prompt given to the agent

> The level contains a supplied bundle host and two consumers. At runtime the
> world assigns both consumers the same Primary Asset identity and one named
> bundle, then requests that bundle for each consumer. Implement the supplied
> editable bundle manager so it uses Asset Manager's managed asynchronous bundle
> APIs, shares one residency lease across the two owners, and supports completion
> either in the request call or on a later engine tick. Loading the selected
> bundle may make its payload and that payload's dependency resident, but it must
> not load another bundle or another record. Releasing one owner must keep the
> shared bundle alive. Releasing the last owner must remove only the bundle owned
> by this manager and must not retain a handle that pins its payload. Do not hardcode
> a PrimaryAssetId, bundle name, owner, release order, package path, or authored
> value. Work only in
> `Source/ThirdPerson/Tasks/t2-one-bundle-loads-without-pulling-in-the-rest/BundleLeaseRuntime.cpp`;
> the adjacent headers and schema source are read-only contracts. Do not edit
> records, maps, tests, task configuration, or build files.

## Workspace state pre-task

The deliverable root is
`Source/ThirdPerson/Tasks/t2-one-bundle-loads-without-pulling-in-the-rest/BundleLeaseRuntime.cpp`.

Files supplied in the editable runtime task directory:

- `BundleLeaseAssets.{h,cpp}` defines the verifier-authored PrimaryDataAsset,
  payload, and hidden-dependency schemas. It is support schema, not the requested
  implementation.
- `BundleLeaseRuntime.h` defines the host, two-consumer public contract, lease
  key/entry storage, and manager entry points.
- `BundleLeaseRuntime.cpp` wires consumer acquire/release calls but leaves the
  manager's exact bundle acquisition, owner sharing, and release behavior empty.

Verifier-owned content under
`Content/Maps/t2-one-bundle-loads-without-pulling-in-the-rest/` contains three
managed records, two bundles per record, six payloads, six hidden dependencies,
and `L_BundleLeases.umap`. The map has exactly one tagged host, two tagged
consumers, one world scenario, and the production fixture. The task-local
`DefaultGame.ini` overlay registers the protected Records directory before the
editor's initial Asset Manager scan.

The fixture replaces consumer decoys from the protected world scenario. Across
authored scenarios, record identity, selected bundle, and which owner releases
first differ. The editable code must use the live arguments to every request and
release, not serialized defaults or actor names.

## Verifier specification

Layer choice: **L1 + L2**. L1 builds both Editor and Game targets. L2 uses a
normal PIE world-clock checkpoint schedule. It never manually ticks the world
and never synchronously loads protected content to obtain an oracle.

### L1 - build

```text
assert: ThirdPersonEditor Win64 Development exits 0
assert: ThirdPerson Win64 Development exits 0
```

### L2 - exact bundle and shared lease lifecycle

Before any request, the fixture resolves exact actor-tag cardinality, validates
all 15 protected object paths/classes/registry fields, and asks Asset Manager for
each exact bundle load set without loading it. Every object must be nonresident
and every protected PrimaryAssetId must have no pending/current handle. Missing
tags, altered public contracts, eager loads, record drift, or overlay failure are
graded failures, never a skip or `NO_VERDICT` escape.

```text
Phase 1 - first owner:
    assign both consumers the scenario's PrimaryAssetId and bundle name
    call consumer A acquire
    in the same call require one manager owner and an Asset Manager handle whose
        pending/current bundle list is exactly [selected bundle]
    allow completion immediately or poll for at most 3.0 world seconds
    require exact selected record + payload + hidden dependency resident
    named gate: SelectedBundleAloneBecomesResident

Continuous negative control:
    every checkpoint requires the other bundle's payload/dependency, both bundles
        of every other record, and every other primary record to remain nonresident
    every other PrimaryAssetId must remain without a managed handle
    named gate: UnselectedBundleStaysNonResident

Phase 2 - shared owner:
    call consumer B acquire for the same live identity/bundle
    require two exact owners backed by the same manager entry and exact engine
        bundle state; wait up to 3.0 world seconds for B completion
    release the world-selected first owner and request GC
    after 0.30 world seconds require the selected payload and hidden dependency
        still resident, one exact owner remaining, and exact bundle state intact
    named gate: OneReleaseKeepsSharedDependencyAlive

Phase 3 - last release:
    release the remaining owner, discard the old load handle, remove exactly the
        selected bundle through Asset Manager, and request GC on later checkpoints
    within 3.0 world seconds require both selected secondary objects nonresident,
        no leases/ready consumers, and a managed primary-only handle with no bundles
    require all never-selected objects stayed nonresident and hold for 0.25 seconds
    named gate: LastReleaseUnloadsOnlyManagedBundle
```

PIE runs execute with `GIsEditor`, where engine GC intentionally preserves
`RF_Standalone` objects. After positively observing the selected secondary
payload and hidden dependency under the exact managed bundle handle, the
verifier clears only that in-memory editor keep flag on those two objects. It
does not alter a package, save an asset, touch the primary record, or touch any
negative-control object. The live handle therefore still keeps both objects
resident through the first release, while a leaked old handle still prevents
collection after the last release. This is the PIE equivalent of packaged-Game
GC, whose keep flags are `RF_NoFlags`.

The primary-only handle requirement after the last release rejects broad
`UnloadPrimaryAsset`: the task owns one bundle transition, not every possible
owner of that Primary Asset. The secondary-object residency gate rejects a
retained old streamable handle. No gate assumes a minimum async delay.

### L2I - fixed three-check denominator

1. `ManagedPrimaryAssetBundleApisPresent` - the accepted source uses both
   `LoadPrimaryAsset` and `ChangeBundleStateForPrimaryAssets`, proving the
   managed bundle request/removal route rather than a path load.
2. `SharedOwnerHandleTopologyPresent` - the protected header retains the exact
   weak-owner set, owner-to-key map, per-key entry map, and shared
   `FStreamableHandle` surface used by the live fixture.
3. `NoBroadOrSynchronousLoading` - the accepted source contains no `TryLoad`,
   `LoadSynchronous`, `UnloadPrimaryAsset`, root pin, protected record name, or
   protected bundle-name literal.

All three IDs are always emitted. L2I cannot establish residency or lifetime;
the four named L2 behaviors remain authoritative.

## Reference solution metadata

- Files touched: one supplied editable `.cpp` file.
- Expected size: 150-260 C++ LOC including synchronous-completion safety,
  per-owner key tracking, one shared entry/handle, and exact bundle removal.
- Senior developer time: 5-7 hours including Asset Manager state inspection and
  reference/empty discrimination.

## Anti-gaming notes

1. Loading every record fails `UnselectedBundleStaysNonResident` immediately.
2. Loading all bundles of the selected record fails the same gate because the
   unselected payload and its hidden dependency become resident.
3. Releasing on the first owner fails `OneReleaseKeepsSharedDependencyAlive`
   after verifier-requested GC.
4. Keeping the request handle or a hard reference forever fails
   `LastReleaseUnloadsOnlyManagedBundle` when the selected secondary objects do
   not become nonresident.
5. Calling `UnloadPrimaryAsset` is too broad and fails the required managed
   primary-only zero-bundle state.
6. `TryLoad`/`LoadSynchronous` cannot establish the exact engine-owned bundle
   handle and pending/current bundle list required in the acquire call.

## Hidden invariants

- Protected record assets live below the map task root, outside submission
  writable asset prefixes; their exact paths, metadata, and dependency graph are
  pinned in verifier-only source.
- Task config is overlaid before editor boot; initial scan ordering is proved by
  exact PrimaryAssetId path and load-set checks in `PrepareTest`.
- Actor identity uses exact tags and cardinality, not labels or enumeration order.
- The admission fixture is a verifier-only engine control in a separate map. It
  is absent from `L_BundleLeases` and cannot make the empty runtime pass.
- Polling uses normal PIE world time. The fixture never calls `World->Tick`,
  `DispatchBeginPlay`, `TryLoad`, or `LoadSynchronous`.
- The verifier's PIE-only `RF_Standalone` clearing is restricted to the two
  already-loaded selected secondary objects and is never serialized.

### Trust boundary

- The exact accepted-files manifest must equal the edit-only surface declared in the agent-visible prompt; extra source, assets, maps, config, or fixtures fail before grading.
- Candidate-authored telemetry, logs, strings, counters, and mirror variables never contribute verdict evidence.
- Named gates and layer denominators are fixed by the verifier specification; setup failures cannot add, remove, or reinterpret them.
- Reference, discrimination, authoring, and maintainer evidence remain outside the staged submission and agent-visible prompt.
