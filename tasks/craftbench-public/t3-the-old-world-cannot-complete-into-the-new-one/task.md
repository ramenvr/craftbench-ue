---
id: t3-the-old-world-cannot-complete-into-the-new-one
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_OldEpochStart :: AOldEpochStartFunctionalTest", "L_NewEpochDestination :: ANewEpochDestinationFunctionalTest"]
introspect: [t3_epoch_world_async_guard.py]
deadline_s: 2400
action_budget: 70
accepted_files: [Source/ThirdPerson/Tasks/t3-the-old-world-cannot-complete-into-the-new-one/EpochAssetWorldSubsystem.h, Source/ThirdPerson/Tasks/t3-the-old-world-cannot-complete-into-the-new-one/EpochAssetWorldSubsystem.cpp]
---

# t3-the-old-world-cannot-complete-into-the-new-one

> **AUTHORED / COMMITTED-HEAD CERTIFIED.** The
> retained records and two playable travel maps passed fresh cold readback. A
> recoverable local closure compiled and ran the narrow reference for an exact
> 4/4 pass, restored and recompiled the empty scaffold byte-for-byte, then
> observed its exact `NewWorldResolvesItsAssignedRecord` behavior failure. The
> canonical committed-HEAD verifier passes L1, custom L2, and fixed L2I.

Do not let the old world complete into the new one

## Primary concept

- `programming-subsystems` - Programming Subsystems

### Composed concepts

- `asynchronous-asset-loading` - asynchronous soft-asset loading
- `ps-garbage-collection` - object lifetime and collection
- `ps-level-travel` - world replacement while GameInstance survives

### Production-pattern justification

World-scoped async work must not outlive its authority. A callback started by an
old `UWorldSubsystem` can arrive after travel and accidentally mutate the new
world if it resolves "current world", captures a strong old-world object, or uses
global state. Production code needs explicit epoch and lifetime cancellation while
allowing the destination world's own request to complete normally.

### Concept-interaction notes

The verifier assigns distinct record identities/values and completion ordering to
the start and destination worlds. It observes subsystem initialize/deinitialize,
request handles, callbacks, destination mutation, and weak old-world objects through
a protected GameInstance-lifetime reporter. Candidate-authored facts never decide
the verdict.

## Prompt given to the agent

> Complete the supplied WorldSubsystem. Start the supplied asynchronous asset
> request for the current world and apply its record only while that same world
> epoch is still valid. When the world deinitializes, retire its request and make
> any later callback harmless. After travel, the destination world's subsystem
> must resolve and apply its own supplied record normally.
>
> The verifier changes old/new record identity and value, world epoch, travel
> timing, and completion order. Do not load synchronously, write through a global
> "current world", retain the old world, root loaded objects, or hardcode either
> map or record.
>
> Edit only `EpochAssetWorldSubsystem.h` and
> `EpochAssetWorldSubsystem.cpp` under
> `Source/ThirdPerson/Tasks/t3-the-old-world-cannot-complete-into-the-new-one/`.
> Do not edit the reporter, maps, records, tests, project settings, or other source.

## Workspace state pre-task

- Planned editable inventory: exactly the supplied subsystem `.h/.cpp` pair.
  It compiles and exposes request/observation hooks but performs no load.
- Planned protected maps:
  `Content/Maps/t3-the-old-world-cannot-complete-into-the-new-one/L_OldEpochStart.umap`
  and `L_NewEpochDestination.umap` in the same task map directory.
- A verifier-owned GameInstance subsystem records immutable peer-qualified facts
  across travel without retaining old world objects.
- Each map owns one exact assigned soft record and visible value display. The
  destination does not inherit candidate state from the start world.

## Verifier specification

L1 builds Editor and Game, requires the exact source pair, and rejects submitted
maps, records, config, reporter, fixtures, alternate subsystems, or extra source.

L2 is one aggregate result across a travel sequence. The start fixture pins world
and subsystem identity, installs a delayed old record request, records its epoch,
and initiates ordinary travel. A GameInstance-lifetime reporter receives only
verifier facts and weak object references. The destination fixture pins a new
world/subsystem/epoch, installs its different request, and waits on ordinary world
time for both request windows and GC checkpoints. Neither fixture manually ticks
the engine, streamable manager, world, subsystem, or GC.

The runner requires exact start/destination map identity and one fixture per stage,
then combines their terminal reporter record after the destination sentinel. It
launches one fresh `UnrealEditor-Cmd -game` process rather than attempting to keep
an Automation controller alive across the map replacement.

Fixed L2 denominator: exactly four named gates.

1. `OldWorldSubsystemDeinitializesOnce`
2. `OldEpochCompletionCannotMutateNewWorld`
3. `NewWorldResolvesItsAssignedRecord`
4. `TravelLeavesNoOldWorldRootedObjects`

Harness preconditions separately require genuine travel, distinct world/subsystem
identities, verifier-controlled request order, an observed late old completion or
cancellation terminal fact, one valid new completion, and collector checkpoints.

L2I has a fixed denominator of exactly three checks.

1. `UsesCancellableAsynchronousRequest`
2. `CallbackIsBoundToWeakWorldEpoch`
3. `SubmissionHasNoCrossWorldOrSynchronousSubstitute`

## Reference solution metadata

- Native reference LOC: 79 implementation lines plus the supplied header.
- Assets edited by the submission: 0.
- Senior developer estimate: 12-20 hours after the travel reporter seam is
  admitted, including cancellation/late-callback and GC discrimination.

## Anti-gaming notes

1. Synchronous loading fails the pending-old-request precondition and ordering.
2. A global callback targeting current world fails the old-late negative control.
3. Strongly capturing the old subsystem/world fails weak invalidation and GC.
4. Ignoring every callback prevents the destination record from resolving.
5. Hardcoded map/record identity fails swapped fixture policy.
6. A static epoch or process singleton fails multiple fresh sequences and exact
   subsystem lifecycle evidence.
7. Candidate telemetry cannot substitute for reporter-observed mutations.

## Hidden invariants

- Old/new record identities, values, epochs, maps, and callback ordering vary.
- One policy allows the old callback to arrive after destination initialization;
  another proves explicit cancellation while preserving a terminal retired fact.
- Destination value is not derivable from old value or map name.
- Reporter stores weak references and primitive facts only; it cannot keep old
  world packages alive.
- The final sentinel requires old world, subsystem, assigned actor, and loaded
  old record wrappers invalid/unrooted while the new world remains healthy.

### Trust boundary

- The exact accepted-files manifest must equal the edit-only surface declared in the agent-visible prompt; extra source, assets, maps, config, or fixtures fail before grading.
- Candidate-authored telemetry, logs, strings, counters, and mirror variables never contribute verdict evidence.
- Named gates and layer denominators are fixed by the verifier specification; setup failures cannot add, remove, or reinterpret them.
- Reference, discrimination, authoring, and maintainer evidence remain outside the staged submission and agent-visible prompt.
