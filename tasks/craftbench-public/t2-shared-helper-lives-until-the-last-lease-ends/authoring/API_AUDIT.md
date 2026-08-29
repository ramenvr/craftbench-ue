# UE5.8 API audit - shared helper leases

Status: **STATIC / BUILD NOT RUN**. All facts below were checked against the
local `<UE-root>` source tree on 2026-08-20. No protected/internal engine API is
required.

| Need | Public UE5.8 surface | Local evidence | Use in this task |
|---|---|---|---|
| one cache per game instance | `UGameInstanceSubsystem` | `Engine/Public/Subsystems/GameInstanceSubsystem.h:16` | supplied editable subject base |
| retrieve live subject | `UGameInstance::GetSubsystem<T>()` | `Engine/Classes/Engine/GameInstance.h:440` | verifier reads the actual PIE instance |
| request engine GC | `UEngine::ForceGarbageCollection(bool bFullPurge=false)` | `Engine/Classes/Engine/Engine.h:2828`; engine/functional-test call sites use `true` | fixture-only request at the next engine opportunity |
| fresh world facts | `FGuid::NewGuid()` | `Core/Public/Misc/Guid.h:366` | key, control key, versions, three payloads |
| strong object edge | `UPROPERTY` + `TObjectPtr<T>` | `CoreUObject` reflected property surface | active lease/cache owns helper |
| weak identity | `TWeakObjectPtr<T>` | `CoreUObject/Public/UObject/WeakObjectPtrTemplates.h` | fixture observes invalidation without retention |
| reflected topology | `FObjectPropertyBase`, `FWeakObjectProperty`, `FArrayProperty`, `FStructProperty` | `CoreUObject/Public/UObject/UnrealType.h` | verifier-only fixed readback helper |
| normal world time | `UWorld::GetTimeSeconds()` | existing `ACraftBenchFunctionalTest` clock contract | epoch plus four scheduled checkpoints |

## GC interpretation

`ForceGarbageCollection(true)` requests a full purge at the next safe engine
opportunity; it does not synchronously collect inside the fixture callback.
Therefore the fixture deliberately waits 0.30 world seconds before reading a
weak pointer. A fresh unrooted verifier witness is created immediately before
each request. The weak lifetime gate is evaluated only if that witness is
already invalid at the following checkpoint.

This separates two facts:

1. the engine actually completed a collection after this request; and
2. submitted reflected references did or did not keep the helper reachable.

The fixture never calls `CollectGarbage`, `ConditionalBeginDestroy`,
`MarkAsGarbage`, or manual world ticking.

## Outer and ownership

The reference creates helpers as transient objects under
`GetTransientPackage()` and relies only on reflected `CacheEntries`,
`ActiveLeases`, and `USharedHelperLease::Helper` edges. Lease tokens may use
the subsystem as Outer, but token collection is not a graded proxy. The helper
itself is judged by real weak invalidation after all explicit strong edges have
been removed.

## Dependency result

No shared dependency patch is needed. `Core`, `CoreUObject`, `Engine`, and
`FunctionalTesting` are already direct module dependencies. The only owner
action is installing the fixed introspector candidate at the governed shared
path described in `../OWNER_SHARED_PATCH.md`.
