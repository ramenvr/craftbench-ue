---
id: t3-only-the-near-active-sector-exists
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: World & Streaming
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_NearActiveSector :: ANearActiveSectorFunctionalTestA", "L_NearActiveSector :: ANearActiveSectorFunctionalTestB"]
introspect: [t3_only_near_active_sector.py]
deadline_s: 1800
action_budget: 60
accepted_files: [Content/Tasks/t3-only-the-near-active-sector-exists/BP_NearActiveSectorController.uasset]
---

# t3-only-the-near-active-sector-exists

> **Status: AUTHORED / REFERENCE AND EMPTY DISCRIMINATION PASS / REFGATE
> PENDING.** The production World Partition map, editable no-op Blueprint,
> mirrored reference, two-fixture L2 verifier, and fixed three-check L2I are
> authored. Clean production grading passed the reference and rejected the
> empty implementation at the intended named gates on pinned Windows UE 5.8.1.

Make only the near active sector exist

## Primary concept

- `ps-world-partition` - World Partition
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition-in-unreal-engine)

### Composed concepts

- `ps-world-partition-data-layers` - World Partition Data Layers
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition---data-layers-in-unreal-engine)
- `ps-components` - actor-owned streaming-source component
- `ps-actors` - streamed actor identity and lifecycle

### Production-pattern justification

Open worlds commonly need both spatial residency and logical state. A streaming
source makes nearby cells eligible while runtime Data Layers decide which
logical sector is allowed to become live. Correctness is the intersection of
those systems: leaving a cell destroys its actor instances, switching a layer
does not load distant content, and returning creates fresh valid identities.
This is intentionally distinct from classic `ULevelStreaming` sublevels.

### Concept-interaction notes

The verifier owns two runtime Data Layer assets, two spatially separated cell
contents, and one placed streaming source. It reverses first sector, travel
direction, and layer switch order between two fixtures. It observes the
registered engine streaming source, effective Data
Layer states, World Partition settle, exact live actor sets, level/package
ownership, and weak-object invalidation together.

## Prompt given to the agent

> **Deliverable root:
> `Content/Tasks/t3-only-the-near-active-sector-exists/`.**
>
> Complete the supplied sector controller. When a sector is selected, make
> that sector's runtime Data Layer active and every other supplied sector
> inactive, then move the supplied streaming source to the selected sector.
> Only actors belonging to the selected nearby sector may exist. Leaving a
> sector must unload its actors, and returning later must create fresh valid
> play instances.
>
> The level supplies sector assets, locations, source radius, selection order,
> and marker identities at runtime. Use the supplied references and runtime
> requests rather than names or fixed coordinates. Do not replace World
> Partition with sublevel streaming, spawn lookalikes, keep every layer active,
> or simulate unload by hiding or disabling actors.
>
> Edit only the supplied controller Blueprint. Do not edit the map, Data Layer
> assets, streaming-source actor, sector actors, tests, project settings, or
> native source.

## Workspace state pre-task

- **Deliverable root:
  `Content/Tasks/t3-only-the-near-active-sector-exists/`.** This is the only
  agent-writable task surface.
- The editable baseline asset is
  `Content/Tasks/t3-only-the-near-active-sector-exists/BP_NearActiveSectorController`.
- The protected map is
  `Content/Maps/t3-only-the-near-active-sector-exists/L_NearActiveSector`.
  It must be a real World Partition/OFPA world, not a classic streaming host.
- Two protected runtime Data Layer assets and two protected spatial marker sets
  are supplied outside the editable task folder.
- One protected actor owns the exact enabled
  `UWorldPartitionStreamingSourceComponent`. The controller receives this actor,
  the selected Data Layer asset, all candidate layer assets, and the selected
  destination through verifier-owned requests.
- The baseline controller compiles but its request event is empty. The world is
  still loadable and contains no agent-owned native answer path.

## Verifier specification

The following production contract is admission- and discrimination-certified.

L1 builds `ThirdPerson Win64 Development` and `ThirdPersonEditor Win64
Development`, loads the exact Blueprint, and requires a current generated class
directly derived from the supplied native controller base.

L2 runs exactly two fixtures sequentially in one fresh fixed-60-Hz NullRHI PIE
world. Each performs a verifier-owned per-run reset, anchors its schedule to
its actual `StartTest` world-time epoch, and never manually ticks the world, World
Partition, Data Layer manager, streaming source, or actors. Before grading it
requires a real `UWorldPartition`, exactly one enabled and subsystem-registered
streaming-source provider, two exact runtime Data Layer instances, and no live
sector markers.

Each fixture drives this sequence through the submitted controller:

1. source beside the first sector while both layers are unloaded;
2. activate the first layer and wait for that source to report streaming
   complete;
3. move the source to the second sector while leaving its layer unloaded;
4. activate the second layer and unload the first;
5. return to the first sector and restore only its layer.

At each settled checkpoint, L2 records the source provider registration,
component transform and shape/radius, requested and effective layer states,
`UWorldPartitionSubsystem::IsStreamingCompleted`, exact tagged live actors,
their runtime level/package ownership, stable marker facts, and weak pointers to
all prior instances. The second fixture reverses the sector order and travel
direction. Protected locations, radius, layer identities, and marker identities
come from the world/request surface rather than the submission.

Fixed L2 denominator: exactly four named gates.

1. `InactiveLayerHasNoLiveActors`
2. `ActiveNearCellLoadsExactActorSet`
3. `LeavingCellUnloadsPriorIdentities`
4. `ReturningCellCreatesFreshValidInstances`

L2I is reserved with a fixed denominator of exactly three gates:

1. `ControllerUsesRuntimeDataLayerSelection` - the request asset drives exact
   runtime-state calls for the selected and non-selected supplied assets.
2. `ControllerMovesThePlacedStreamingSource` - the supplied source reference
   and destination drive the source owner transform; no spawned provider or
   literal actor lookup exists.
3. `SubmissionHasNoStreamingSubstitute` - accepted files and task registry
   inventory contain only the exact controller package; no map, source,
   sublevel, actor, config, or extra asset is submitted.

## Reference solution metadata

- Native LOC: 0.
- Assets edited: exactly 1.
- Authored reference graph: 13 nodes and 36 links; all three fixed L2I checks
  require the exact native graph vector.
- Senior developer estimate: 10-16 hours including World Partition settle
  diagnosis and two-order live verification.

## Anti-gaming notes

1. Hiding or disabling persistent actors fails live actor cardinality, runtime
   level ownership, and weak-pointer invalidation.
2. `SpawnActor` lookalikes fail World Partition package/level ownership and
   fresh marker identity.
3. Classic `Load Stream Level` or `ULevelStreamingDynamic` fails the real
   World Partition and registered-provider precondition.
4. Keeping both Data Layers active fails the distant/inactive negative controls.
5. Hardcoded asset names, actor names, or coordinates fail the reversed fixture
   and rewritten request facts.
6. Moving a camera or pawn while leaving the supplied source fixed fails exact
   source identity and transform evidence.
7. Reusing an old actor pointer after return fails destroyed-old/fresh-new
   identity checks even if the visible marker text matches.

## Hidden invariants

- Sector order and request token vary by fixture. Positions, radius, layer
  assets, and marker identities are protected world facts read through the
  supplied request/fixture surface.
- Layer state and spatial proximity are independent negative controls: each is
  held wrong once while the other is correct.
- Settle is accepted only from the engine subsystem/provider after ordinary
  world time advances; sleep, wall clock, and manual tick are outside grading.
- The final sentinel rechecks map World Partition identity, provider identity,
  exact Data Layer assets/instances, and invalidity of every retired actor.

### Trust boundary

- The exact accepted-files manifest must equal the edit-only surface declared in the agent-visible prompt; extra source, assets, maps, config, or fixtures fail before grading.
- Candidate-authored telemetry, logs, strings, counters, and mirror variables never contribute verdict evidence.
- Named gates and layer denominators are fixed by the verifier specification; setup failures cannot add, remove, or reinterpret them.
- Reference, discrimination, authoring, and maintainer evidence remain outside the staged submission and agent-visible prompt.
