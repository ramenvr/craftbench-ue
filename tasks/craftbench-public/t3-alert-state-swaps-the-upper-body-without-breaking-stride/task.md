---
id: t3-alert-state-swaps-the-upper-body-without-breaking-stride
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: Animation
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_AlertStride :: AAlertStrideSlowFunctionalTest", "L_AlertStride :: AAlertStrideFastFunctionalTest"]
introspect: [t3_alert_stride_linked_layer.py]
deadline_s: 1800
action_budget: 70
accepted_files: [Content/Tasks/t3-alert-state-swaps-the-upper-body-without-breaking-stride/ABP_AlertStrideHost.uasset, Content/Tasks/t3-alert-state-swaps-the-upper-body-without-breaking-stride/ABP_AlertStrideCalmLayer.uasset, Content/Tasks/t3-alert-state-swaps-the-upper-body-without-breaking-stride/ABP_AlertStrideAlertLayer.uasset, Content/Tasks/t3-alert-state-swaps-the-upper-body-without-breaking-stride/ST_AlertStride.uasset]
---

# t3-alert-state-swaps-the-upper-body-without-breaking-stride

Keep the supplied character walking while its behavior changes between calm
and alert. Alert must replace only the upper-body animation; clearing alert
must restore the original upper body without restarting the character's main
animation or stride.

## Primary concept

- `anim-linked-anim-graph` - a declared animation layer is swapped at runtime
  while the host graph and its locomotion base stay live

### Composed concepts

- `state-tree` - a real active behavior state owns the alert lifetime
- `anim-anim-instance` - live main and linked animation instances plus
  evaluated bone transforms prove the pose route
- `setting-up-character-movement` - ordinary Character Movement remains in
  continuous grounded locomotion across both layer swaps

### Production-pattern justification

Characters often change combat or awareness behavior without discarding their
locomotion graph. State and animation modularity are useful only when the
behavior state truly selects the declared upper-body layer, the main instance
survives the swap, and feet continue through a natural walking phase.

## Prompt given to the agent

> Complete the supplied alert behavior and animation assets. While the
> character walks, entering alert must replace only its upper-body pose;
> clearing alert must restore the calm upper body. Keep the original walking
> motion running underneath both changes and do not restart the character's
> main animation.
>
> The level contains two characters with different walking directions,
> speeds, and alert timings. Edit only these supplied assets under
> `Content/Tasks/t3-alert-state-swaps-the-upper-body-without-breaking-stride/`:
> `ABP_AlertStrideHost`, `ABP_AlertStrideCalmLayer`,
> `ABP_AlertStrideAlertLayer`, and
> `ST_AlertStride`. Do not edit the map, tests, native code, project settings,
> layer-interface contract, characters, or alert signal actors. Do not use a montage, switch the whole
> animation Blueprint, pause movement, or move the character directly.

## Workspace state pre-task

- The four exact editable assets already exist at the paths named in the
  prompt. A read-only layer-interface asset alongside the map declares
  `UpperBody` at
  `/Game/Maps/t3-alert-state-swaps-the-upper-body-without-breaking-stride/ALI_AlertStrideUpperBody`;
  both layer Blueprints are compatible with the supplied Manny skeleton.
- The retained baseline host evaluates ordinary Manny locomotion from the
  runtime character speed, but does not route a linked upper-body layer.
- The retained baseline StateTree has only its calm state. The runtime module
  supplies read-only condition and layer-link task types that operate on the
  fixture's real alert signal and skeletal mesh.
- The read-only `L_AlertStride` map contains two independent groups:
  `SlowEarly` and `FastLate`. Speed, travel direction, alert time, clear time,
  and group origin differ between them.

## Verifier specification

L1 builds `ThirdPersonEditor Win64 Development` and `ThirdPerson Win64
Development`.

L2 runs both listed fixtures under `-nullrhi` in fresh PIE worlds. Each fixture
pins exactly one scenario, subject, signal, StateTree, host AnimInstance,
declared layer interface, calm layer class, and alert layer class. Checkpoint
times are absolute world times derived from that fixture's own Prepare epoch.
The verifier changes only its pinned alert signal; character motion comes from
the real Character Movement component.

Dense frame samples capture character displacement, movement mode and
velocity, main AnimInstance identity, montage absence, linked-layer instance
identity, engine-reported StateTree active-state names, and evaluated Manny
`foot_l`, `foot_r`, `hand_r`, and `pelvis` transforms. The first checkpoint
observes calm walking; the fixture activates the signal, observes the alert
state/layer/pose, holds it, clears the signal, observes restoration, and then
requires continued walking.

Named gates:

1. `AlertStateBecomesActive` - the StateTree reports Calm before the signal
   and Alert after it, from the real component's active-state path.
2. `BehaviorStateLinksAndDrivesDeclaredLayer` - the exact alert-layer instance
   replaces the calm linked instance, persists with Alert, and produces a live
   upper-body bone delta without changing the main AnimInstance or playing a
   montage.
3. `LowerBodyStrideRemainsContinuous` - grounded velocity/displacement stay
   positive and dense foot/actor steps remain bounded by the same run's calm
   baseline through both swaps.
4. `ClearRestoresOriginalLayerWithoutRestart` - clearing the world signal
   returns the engine state and exact calm linked instance, restores the live
   upper-body pose, and preserves main-instance identity.

L2I runs `t3_alert_stride_linked_layer.py` with a fixed denominator of four:

1. `StateTreeHasCalmAlertBidirectional` - the saved StateTree contains exact
   Calm/Alert states, opposite world-signal transitions, and the declared
   alert-layer task/class.
2. `HostUsesDeclaredLinkedLayer` - exactly one compiled linked-layer node uses
   the exact interface and calm default class and feeds the final composition.
3. `LocomotionRemainsBasePose` - the stock speed-driven locomotion player is
   the base pose of the upper-body blend, not replaced by it.
4. `LayerImplementationsAvoidMontageRoutes` - both layer classes implement the
   exact interface, each declared layer produces a reachable pose, and every
   reachable layer/host graph is free of montage Slot routes. The live upper-
   body delta is graded separately by L2 without prescribing its authoring
   nodes.

Missing or ambiguous verifier-owned world identities are
`HARNESS-PRECONDITION:` errors. Every submission-reachable state, layer,
AnimGraph, pose, montage, and walking failure is graded by one of the four
named ASCII gates.

## Reference solution metadata

- Native LOC: 0.
- Expected assets edited: four Blueprint/StateTree assets.
- Expected editor changes: one two-state behavior tree, one linked-layer host
  route, and two small layer implementations.
- Senior developer estimate: 6-10 hours including live-pose tuning.

## Anti-gaming notes

1. A bool/enum mirror that never changes the real StateTree active state fails
   `AlertStateBecomesActive`.
2. Directly switching the skeletal mesh's whole AnimBlueprint changes the
   pinned main-instance identity and fails the linked-layer gate.
3. A montage or Slot-based overlay fails both runtime montage absence and
   fixed L2I topology.
4. A full-body alert pose, locomotion restart, pause, or teleport fails dense
   foot, velocity, movement-mode, progress, and frame-step evidence.
5. A constant alert layer or a response hard-coded to one timestamp fails the
   second fixture's different speed, direction, and timings.
6. Logging a claimed state/layer or writing an agent-owned mirror variable
   cannot affect engine active-state, linked-instance, or evaluated-bone reads.
7. Replacing only a visible upper-body mesh or separate actor does not change
   the pinned subject's evaluated skeleton and fails pose telemetry.

## Hidden invariants

- `SlowEarly` and `FastLate` vary origin, speed, direction, alert delay, clear
  delay, and deadline while using the same submitted four-asset set and pinned
  read-only layer interface.
- Scenario actors and exact asset/class identities are pinned before runtime;
  duplicate/shadow actors cannot satisfy a fixture.
- State evidence is sourced from `UStateTreeComponent`; layer evidence is
  sourced from the skeletal mesh's linked AnimInstance; pose evidence is live
  component-space bone data.
- Thresholds are provisional. The task remains HOLD until repeated admission
  runs calibrate live pose and timing margins and reference, empty,
  direct-switch, montage, mirror-bool, and broken-locomotion controls
  discriminate.

### Trust boundary

- The exact accepted-files manifest must equal the edit-only surface declared in the agent-visible prompt; extra source, assets, maps, config, or fixtures fail before grading.
- Candidate-authored telemetry, logs, strings, counters, and mirror variables never contribute verdict evidence.
- Named gates and layer denominators are fixed by the verifier specification; setup failures cannot add, remove, or reinterpret them.
- Reference, discrimination, authoring, and maintainer evidence remain outside the staged submission and agent-visible prompt.
