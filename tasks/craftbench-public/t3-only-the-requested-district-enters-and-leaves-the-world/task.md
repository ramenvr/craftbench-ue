---
id: t3-only-the-requested-district-enters-and-leaves-the-world
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: World & Streaming
category: gameplay
layers: [L1, L2]
fixtures: ["L_DistrictStreaming :: ADistrictStreamingFunctionalTestAlpha", "L_DistrictStreaming :: ADistrictStreamingFunctionalTestBeta"]
deadline_s: 1800
action_budget: 60
accepted_files: [Content/Tasks/t3-only-the-requested-district-enters-and-leaves-the-world/BP_DistrictStreamLoader.uasset]
---

# t3-only-the-requested-district-enters-and-leaves-the-world

Complete the supplied district loader so it streams only the requested world
section into the running world, removes that section again, and can later load
the same section as fresh actor instances.

## Primary concept

- `ps-levels` - runtime level streaming lifecycle and ownership

### Composed concepts

- `asynchronous-asset-loading` - a soft world reference chooses the section
- `programming-subsystems` - verifier-owned world state observes entry and exit
- `object-lifecycle` - reloading must create fresh actors, not reveal old ones

### Production-pattern justification

Large games commonly keep districts, interiors, or encounter cells outside the
persistent world until a runtime request needs them. A correct loader must keep
the request identity, streaming object, level ownership, visibility, and unload
lifecycle aligned. Hiding persistent actors or spawning lookalikes does not
exercise that production boundary.

### Concept-interaction notes

Each fixture supplies a different soft world reference while keeping a second,
unrelated streamed section alive as a control. The verifier observes the real
`ULevelStreaming` state and the exact tagged actors owned by its loaded level.
It unloads and reloads through the submitted loader and rejects stale actor
identity, persistent-level actors, duplicate sections, and collateral unloads.

## Prompt given to the agent

> Complete the supplied district-loader Blueprint. When its request is asked to
> load, stream the world section named by that request and make it visible. When
> asked to unload, remove that same streamed section. A later load request must
> work again.
>
> The requested section changes between verifier worlds. Preserve the unrelated
> district that is already active. Do not hardcode a map, pre-place or spawn
> replacement actors, load every district, or simulate unloading by hiding
> actors.
>
> Edit only the supplied loader Blueprint, save it, and do not edit the level,
> project settings, request actor, streamed sections, tests, or native source.

## Workspace state pre-task

- The editable asset is
  `Content/Tasks/t3-only-the-requested-district-enters-and-leaves-the-world/BP_DistrictStreamLoader.uasset`.
- The read-only host map is
  `Content/Maps/t3-only-the-requested-district-enters-and-leaves-the-world/L_DistrictStreaming.umap`.
- Two verifier-owned section maps and their tagged marker actors are supplied
  outside the editable task folder.
- The loader base exposes the current request and two Blueprint-native lifecycle
  events. Their baseline implementation intentionally performs no streaming.
- Each fixture changes the requested section, instance name, marker identity,
  and unrelated control while keeping the same event surface.

## Verifier specification

L1 builds `ThirdPerson Win64 Development` and `ThirdPersonEditor Win64
Development`, then loads and compiles the exact editable Blueprint.

L2 runs exactly two fixtures in fresh fixed-step PIE worlds. Timing comes from
ordinary world time; neither fixture manually ticks the world, async loading, or
streaming manager. The fixture first establishes one unrelated control section,
then drives load, unload, and reload through the exact submitted loader. It
records streaming-object identity, source world package, loaded/visible state,
loaded-level ownership, marker actor identity, and unrelated-control continuity.

Named L2 gates:

1. `NamedSectionInactiveAtStart`
2. `ExactActorsEnterViaNamedSection`
3. `UnrelatedSectionsUnchanged`
4. `ExactActorsLeaveAfterUnload`
5. `ReloadCreatesFreshSectionActors`
6. `StreamingHarnessHealthy` (`HARNESS-PRECONDITION`)

Both fixtures must pass every gate. The Alpha fixture requests District Alpha
while Beta remains the control; the Beta fixture reverses those identities.

## Reference solution metadata

- Native LOC: 0.
- Expected assets edited: one supplied Blueprint.
- Expected visual-authoring size: 8-16 nodes.
- Senior developer estimate: 4-6 hours including live validation.

## Anti-gaming notes

1. Persistent-level actors fail exact loaded-level ownership.
2. `SpawnActor` lookalikes fail streaming-object and source-package identity.
3. Loading both districts fails requested/control cardinality.
4. Hiding actors fails loaded-level removal and actor lifecycle checks.
5. Destroying the control fails its unchanged object and stream identity.
6. Reusing stale actors fails fresh unique-object identity after reload.
7. Hardcoding Alpha fails the Beta fixture, and hardcoding Beta fails Alpha.
8. Teleporting or renaming actors cannot manufacture a streamed `ULevel` owner.

## Hidden invariants

- Request and control world references vary only through verifier-owned actors.
- Optional streaming instance names are unique per fixture and reload epoch.
- Settle windows are calibrated on the pinned Windows engine and remain
  verifier-owned.
- The exact section marker class, district ID, tag, level owner, and source world
  package are all checked together.
- This task uses classic `ULevelStreamingDynamic`; it is not World Partition and
  does not claim Data Layer coverage.

### Trust boundary

- The exact accepted-files manifest must equal the edit-only surface declared in the agent-visible prompt; extra source, assets, maps, config, or fixtures fail before grading.
- Candidate-authored telemetry, logs, strings, counters, and mirror variables never contribute verdict evidence.
- Named gates and layer denominators are fixed by the verifier specification; setup failures cannot add, remove, or reinterpret them.
- Reference, discrimination, authoring, and maintainer evidence remain outside the staged submission and agent-visible prompt.
