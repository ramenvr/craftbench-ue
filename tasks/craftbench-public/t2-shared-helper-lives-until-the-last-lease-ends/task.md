---
id: t2-shared-helper-lives-until-the-last-lease-ends
substrate: ThirdPerson
set: craftbench-public
tier: T2
capability_bucket: Architecture & Systems
category: other
layers: [L1, L2, L2I]
fixtures: ["L_SharedHelperLeases :: ASharedHelperLeaseFunctionalTest"]
introspect: [t2_shared_helper_last_lease.py]
randomization: [helper-key, helper-version, helper-payload]
deadline_s: 900
action_budget: 40
accepted_files: [Source/ThirdPerson/Tasks/t2-shared-helper-lives-until-the-last-lease-ends/SharedHelperLeaseSubsystem.cpp]
---

# t2-shared-helper-lives-until-the-last-lease-ends

A game-instance cache must share one ordinary UObject helper across concurrent
leases for one key/version, keep retired versions alive only while their own
leases remain, and let Unreal garbage collection invalidate weak observations
after the final lease. The composition makes reference topology, version
replacement, and real GC reachability independently observable.

## Primary concept

- `ps-garbage-collection` - Incremental Garbage Collection
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/incremental-garbage-collection-in-unreal-engine)

The load-bearing fact is ordinary UObject reachability: a helper survives a
full collection while any reflected strong lease/cache edge remains, and its
weak identity becomes invalid after the last edge is removed.

### Composed concepts

| Concept | Epic documentation | Role in the composition |
|---|---|---|
| `programming-subsystems` | https://dev.epicgames.com/documentation/en-us/unreal-engine/programming-subsystems-in-unreal-engine | Supplies one automatically-instanced game-instance lifetime and a shared acquisition surface. |
| `ps-garbage-collection` | https://dev.epicgames.com/documentation/en-us/unreal-engine/incremental-garbage-collection-in-unreal-engine | Supplies the engine-owned reachability and weak-invalidation fact. |
| `ps-uproperties` | https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-uproperties | Supplies reflected strong references for active cache entries and lease tokens, plus a reflected weak owner observation. |

### Production-pattern justification

Epic's public [Asynchronous Asset Loading](https://dev.epicgames.com/documentation/en-us/unreal-engine/asynchronous-asset-loading-in-unreal-engine)
guidance documents handles whose lifetime controls continued ownership of a
shared loaded resource. The same
production boundary appears in pooled services, decoded-resource caches, and
request coalescing: callers share one versioned object, each caller owns a
lease, and the resource becomes reclaimable only after the final lease ends.
This task exercises that public lifetime pattern with ordinary UObjects rather
than an evaluator-owned counter or simulated destroyed flag.

### Concept-interaction notes

The game-instance subsystem supplies the cross-owner sharing scope, reflected
properties make lease/cache edges visible to the collector, and weak pointers
provide an independent observation after collection. Version replacement is
deliberately separate from release: the old helper becomes retired but remains
live through its remaining old-version lease while the new version uses a fresh
identity and current payload.

## Prompt given to the agent

> Complete the supplied shared-helper manager. When two owners acquire the
> same live key and version, both leases must expose the same helper identity
> and current payload. Ending either one of those leases must not affect the
> other. Acquiring a new version of that key must expose a fresh helper with the
> new payload while an outstanding old-version lease continues to expose the
> unchanged old helper. After the last old-version lease ends, the old helper
> must become reclaimable by ordinary engine cleanup while the new version and
> an unrelated key remain live through their own leases. After each of those
> final leases ends, those helpers must also become reclaimable. Do not pin a
> helper for the process lifetime. Work only in
> `Source/ThirdPerson/Tasks/t2-shared-helper-lives-until-the-last-lease-ends/SharedHelperLeaseSubsystem.cpp`;
> the supplied header is a read-only contract. Do not edit tests, maps, build
> files, or verifier code.

## Workspace state pre-task

The deliverable root is
`Source/ThirdPerson/Tasks/t2-shared-helper-lives-until-the-last-lease-ends/SharedHelperLeaseSubsystem.cpp`.

Files that **exist**:

- `Source/ThirdPerson/Tasks/t2-shared-helper-lives-until-the-last-lease-ends/SharedHelperLeaseSubsystem.h`
  is the read-only contract for the subsystem, cache entry, lease token, and
  helper declarations. The adjacent `.cpp` is the exact one-file editable
  submission surface; `AcquireLease` returns null and `ReleaseLease` returns
  false in the baseline.
- The runtime module already directly depends on `Core`, `CoreUObject`, and
  `Engine`, which own every API required by this task.
- The verifier owns three requester actors, fresh keys/versions/payloads,
  release order, forced-GC scheduling, and weak observations. None is writable
  submission state.

Files that **do not exist**: a working acquisition/release implementation, any
process-lifetime pin, final map
`Content/Maps/t2-shared-helper-lives-until-the-last-lease-ends/L_SharedHelperLeases.umap`,
or a submitted asset that can implement the behavior outside the supplied C++.

The live key, version, and payload strings are generated from a fresh GUID in
each PIE world. Constructor literals, actor labels, or one global singleton do
not contain the values used for grading.

## Verifier specification

Layer choice is **L1 + L2 + L2I**. L1 compiles both targets. L2 runs one
verifier-owned `ACraftBenchFunctionalTest` in real PIE at fixed 60 Hz. The
fixture never calls `World->Tick`; only the engine advances the world. L2I has
a fixed denominator of exactly three read-only structural checks.

### L1 - build

```text
assert: UnrealBuildTool exits 0 for ThirdPersonEditor Win64 Development
assert: UnrealBuildTool exits 0 for ThirdPerson Win64 Development
```

### L2 - live sharing, retirement, and garbage collection

At fixture preparation, three verifier-owned actors acquire two leases for one
fresh key/version and one lease for an unrelated fresh key. The fixture stores
lease tokens strongly but helper identities only as `TWeakObjectPtr`. Every GC
request creates an additional unrooted verifier witness; if that witness does
not invalidate by the next world-clock checkpoint, the result is a verifier
`Error`, never a graded lifetime verdict.

At four checkpoints derived from the fixture's live world-time epoch:

```text
same key/version -> exact same non-null helper identity and old payload
unrelated key -> different identity and exact control payload
named failure: SHL-1 SameKeySharesOneLiveHelper

release first sibling; request full GC; witness proves GC occurred
remaining sibling -> old helper still valid and unchanged
named failure: SHL-2 FirstReleaseDoesNotCollectSharedHelper

acquire new version -> fresh identity/new payload while old remains unchanged
named failure: SHL-3 ReplacementKeepsFreshIdentityAndPayload

release final old lease; request full GC; witness proves GC occurred
old weak identity invalid; new and control helpers still valid
named failure: SHL-4 RetiredVersionCollectedAfterLastLease

release new and control final leases; request full GC; witness proves GC occurred
both weak identities invalid
named failure: SHL-5 LastLeaseCollectsCurrentAndControl
```

The fixture logs one final `[CB-SHARED-LEASE] PASS` vector only after all five
named behaviors and all three independent GC witnesses are green.

### L2I - fixed three-check denominator

1. `GameInstanceLeaseSurfacePresent` - exact subsystem base and exact acquire /
   release callable surface exist.
2. `ReflectedLeaseAndCacheOwnership` - the lease helper, cache helper, cache
   lease array, and active lease array are reflected strong object properties.
3. `WeakOwnerAndNoRootPin` - the owner is a reflected weak object property and
   the accepted task source contains no process-root pin or static helper store.

The three IDs are always emitted, including on inspection failure. L2I does not
claim live lifetime correctness; the real collector and weak invalidation in
L2 are authoritative.

## Reference solution metadata

- LOC range: 70-110 C++ LOC in the supplied source pair.
- Files touched: 1-2; no map, asset, build, config, or verifier edit.
- Senior developer estimate: 3-5 hours including reflected ownership,
  version retirement, release isolation, and real-GC validation.

## Anti-gaming notes

1. **One helper per owner.** The first live gate compares exact helper UObject
   identity across two distinct verifier-owned owners; `SHL-1` fails.
2. **One singleton for every key/version.** The unrelated key and replacement
   version must have different identities and exact distinct payloads;
   `SHL-1` or `SHL-3` fails.
3. **Release-any clears everything.** Full GC follows the first release while
   the sibling, replacement, and unrelated leases are independently retained;
   `SHL-2` or `SHL-4` fails.
4. **Rooting/static/process-lifetime retention.** After the final lease, the
   helper is observed only through a verifier weak pointer and must invalidate;
   `SHL-4`/`SHL-5` and the fixed no-root check reject permanent pins.
5. **Flags, counters, direct destruction, or verifier mimicry.** Gates compare
   real UObject identity, exact live fields, and engine GC weak invalidation.
   The admission reference is overlaid only into a disposable project and the
   same production fixture grades it; no alternate admission implementation is
   linked into the live empty runtime.

## Hidden invariants

- Keys, versions, and all three payloads vary per PIE world from a fresh GUID.
- Owners are distinct verifier-only actors; the owner edge is weak and cannot
  accidentally keep a requester alive.
- Helper observations in the fixture are weak. Only live lease/cache UPROPERTY
  edges can explain survival across a completed GC.
- Each full-GC checkpoint has an independent unrooted witness. A missed or
  delayed collection is a harness error, not a false lifetime PASS/FAIL.
- Replacement happens before the last old lease is released, exposing code
  that mutates one cached object in place.
- The reference source overlays the live empty source only inside a fresh
  scratch substrate. Live source hashes are locked before and after admission.

### Trust boundary

- The exact accepted-files manifest must equal the edit-only surface declared in the agent-visible prompt; extra source, assets, maps, config, or fixtures fail before grading.
- Candidate-authored telemetry, logs, strings, counters, and mirror variables never contribute verdict evidence.
- Named gates and layer denominators are fixed by the verifier specification; setup failures cannot add, remove, or reinterpret them.
- Reference, discrimination, authoring, and maintainer evidence remain outside the staged submission and agent-visible prompt.
