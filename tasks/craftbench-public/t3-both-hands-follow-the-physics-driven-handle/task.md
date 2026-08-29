---
id: t3-both-hands-follow-the-physics-driven-handle
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: Technical Art
category: animation
layers: [L1, L2, L2I]
fixtures: ["L_TwoHandPhysics :: ATwoHandPhysicsQuartzFunctionalTest", "L_TwoHandPhysics :: ATwoHandPhysicsVioletFunctionalTest"]
introspect: [t3_both_hands_physics.py]
deadline_s: 1800
action_budget: 60
accepted_files: [Content/Tasks/t3-both-hands-follow-the-physics-driven-handle/CR_TwoHandPhysics.uasset, Content/Tasks/t3-both-hands-follow-the-physics-driven-handle/ABP_TwoHandPhysics.uasset]
---

# t3-both-hands-follow-the-physics-driven-handle

Make both hands of each supplied character follow the two different grip points
on its live physics-driven handle. The handle must remain a real simulated body
owned by its supplied physics constraint, and the hand solve must run through
the supplied Control Rig inside the supplied Animation Blueprint. Preserve the
base pelvis and feet pose while the two world fixtures drive different grip
offsets and two different impulse directions.

## Primary concept

- `anim-control-rig-runtime` - a reachable runtime Control Rig node receives
  independent live left/right target transforms and solves both arm chains.

### Composed concepts

- `physics-constraints` - the tracked handle is a simulated constrained body,
  not a hand attachment or a verifier-owned pose value.
- `anim-anim-instance` - the supplied Animation Blueprint composes the
  procedural solve over its supplied base sequence.

### Production-pattern justification

Two-handed props such as valves, handlebars, mounted tools, and steering yokes
must preserve one physical authority while both arms respond to that authority.
The production pattern is to expose live component-space target transforms to a
runtime Control Rig and layer the solve over the normal body pose. Attaching the
prop to a hand, authoring one fixed pose, or driving bones directly reverses the
ownership boundary and breaks as soon as the physical trajectory changes.

### Concept-interaction notes

`ATwoHandPhysicsHandle` owns an anchor body, one simulated handle body, and one
`UPhysicsConstraintComponent`. `ATwoHandRigCharacter` samples the two
fixture-authored grip transforms after physics and only transports those
transforms into `UTwoHandRigAnimInstanceBase`. It never changes a bone. The
editable `ABP_TwoHandPhysics` must pass the supplied base pose through exactly
one live Control Rig node. The editable `CR_TwoHandPhysics` must set and read
the independent `hand_l_target` and `hand_r_target` controls and use them to
solve `upperarm_l -> hand_l` and `upperarm_r -> hand_r`.

The Quartz and Violet fixtures vary scenario identity, asymmetric grip offsets,
both impulse vectors, impulse magnitude, and the second impulse direction. L2
samples the physical body, the two controls, the two hand bones, and pelvis plus
both feet on the same normal PIE frames. L2I separately inspects the saved
Control Rig and AnimGraph paths.

## Prompt given to the agent

> Complete the two supplied visual-animation assets so both hands of each
> supplied character follow the two grip points on its physics-driven handle.
> Keep the handle as the supplied simulated body constrained to its supplied
> anchor; it must not be attached to either hand. Feed the live left and right
> targets through the supplied Animation Blueprint into the supplied Control
> Rig, solve both arm chains there, and preserve the supplied base pelvis and
> feet pose.
>
> The level contains two fixtures with different grip offsets and two different
> impulse directions and magnitudes. Read the live targets; do not key a fixed
> trajectory or branch on fixture names. Work only in
> `CR_TwoHandPhysics` and `ABP_TwoHandPhysics`. Do not add native code. Do not edit the
> map or character/handle scaffold, attach the handle to a hand, use Two Bone IK
> or Transform/Modify Bone as a substitute, mirror one hand with a boolean, or
> replace the supplied base animation.

## Workspace state pre-task

- Editable assets:
  `/Game/Tasks/t3-both-hands-follow-the-physics-driven-handle/CR_TwoHandPhysics`
  and
  `/Game/Tasks/t3-both-hands-follow-the-physics-driven-handle/ABP_TwoHandPhysics`.
- The Control Rig baseline imports the exact Manny hierarchy, declares public
  `FTransform` variables `LeftHandTarget` and `RightHandTarget`, and owns exact
  controls `hand_l_target` and `hand_r_target`, but its Forward Solve graph is
  empty.
- The Animation Blueprint directly derives from
  `UTwoHandRigAnimInstanceBase` and initially plays the supplied looping Manny
  idle sequence straight to Result with no Control Rig node. The project loads
  and the physical handle moves, but the hands do not follow it.
- `/Game/Maps/t3-both-hands-follow-the-physics-driven-handle/L_TwoHandPhysics`
  owns two visible scenarios, two final fixtures, one stock playable
  PlayerStart, lighting, and a collision floor. The fixtures are named Quartz
  and Violet and own different serialized world facts.
- The character and handle classes, final map, tests, and admission content are
  verifier/substrate-owned. The agent is not asked to create meshes, physics
  bodies, input, or native code.

## Verifier specification

### L1 - build, load, and deliverable boundary

- Build both `ThirdPersonEditor Win64 Development` and `ThirdPerson Win64
  Development` after the Control Rig substrate dependency is admitted.
- Load the exact map and two exact task assets without linker, Blueprint,
  Control Rig VM, or animation compiler errors.
- The accepted submission is exactly the two named `.uasset` files. Added
  source, maps, configs, animations, Control Rigs, Animation Blueprints, or
  redirectors fail the asset-only boundary.
- The exact Control Rig and Animation Blueprint must retain Manny skeleton,
  direct parent class, and task package identity through the final sentinel.

### L2 - live PIE behavior

The final map contains two independently discoverable subclasses,
`ATwoHandPhysicsQuartzFunctionalTest` and
`ATwoHandPhysicsVioletFunctionalTest`. Both derive from
`ACraftBenchFunctionalTest`. They use the same verifier code and different
serialized facts. Normal real-RHI fixed-60-Hz PIE owns physics, character,
animation, and Control Rig evaluation; the fixture never calls `Tick`,
`TickAnimation`, `RefreshBoneTransforms`, or `UWorld::Tick` manually.

Each fixture resolves exactly one handle and one character by its exact
scenario tag, validates the live constraint body identities, captures the
pelvis/feet base pose, and registers a normal
`FWorldDelegates::OnWorldPostActorTick` sampler. The absolute world-clock
schedule is:

```text
StartWorldSeconds + {0.50, 0.75, 1.80, 1.90, 3.20, 3.30}
```

At `0.75` the fixture applies its first world impulse to the simulated handle.
At `1.90` it applies a second non-collinear world impulse. `3.20` aggregates;
`3.30` is a mandatory sentinel. Every sampled frame reads:

- handle body transform/velocity and engine constraint force;
- exact constrained component identities and live constraint validity;
- `hand_l` and `hand_r` world bone transforms;
- asymmetric left/right grip transforms derived from the same handle body;
- the actual `FAnimNode_ControlRig` stored in the live AnimInstance and its
  engine-owned `UControlRig` hierarchy;
- live `hand_l_target` and `hand_r_target` global control transforms;
- pelvis, left foot, and right foot component-space transforms; and
- the monotonically advancing target sample serial.

Attachment of the handle to the subject/mesh, replacement of the body or
constraint identity, missing scenario cardinality, a missing compiled
Control Rig node, non-finite pose, or a dead sampling schedule is
`HARNESS-PRECONDITION` only when it is protected substrate damage. The editable
asset's missing/wrong Control Rig class, controls, or pose behavior is graded by
the fixed gates and L2I, not converted into a submission-controlled opt-out.

The L2 denominator is exactly four ASCII-named gates on both fixture legs:

1. `HandleMovesThroughRealConstraint` - both impulse legs move the exact
   simulated body through the exact live constraint and expose non-zero
   engine-owned constraint force.
2. `BothHandsTrackSamePhysicalHandle` - both independent hand bones remain
   within the frozen error of their different same-body grip endpoints, and
   both live Control Rig controls agree with their independent AnimInstance
   targets.
3. `TrackingRespondsToSecondImpulseDirection` - the second leg projects in its
   fixture-owned second direction while both hands keep tracking; a prerecorded
   first trajectory cannot pass.
4. `FeetAndPelvisPreserveBasePose` - pelvis and both feet stay inside frozen
   component-space translation/angular envelopes while the arms solve.

The formulas, schedule, and numeric bars are frozen in source after five fresh
reference and five empty legs per fixture separated with large margins:
handle displacement and second-direction projection minimum `4.0 cm`, hand
error maximum `18.0 cm`, Control Rig target error maximum `2.0 cm`, and
feet/pelvis component-space translation/angular maxima `8.0 cm` / `15.0 deg`.
Every live metrics record must report `thresholds_frozen=1`.

### L2I - saved Control Rig and AnimGraph structure

The fixed L2I denominator is exactly three checks:

1. `RuntimeControlRigComposesOverBasePose` - Result-reachable AnimGraph path is
   exactly one looping supplied base sequence feeding exactly one compiled
   runtime Control Rig node of the exact task rig class. The public
   custom-property mapping API maps the existing `LeftHandTarget` and
   `RightHandTarget` AnimInstance fields to the same-named rig variables.
2. `RigUsesIndependentHandControls` - the exact rig has public transform inputs
   and exact controls `hand_l_target`/`hand_r_target`; both controls are set and
   read on a Forward Solve execution path, and two reachable FABRIK units solve
   the exact left/right arm effectors independently.
3. `NoDirectTransformTwoBoneIKOrMirror` - the final AnimGraph/RigVM path contains
   no Two Bone IK, Transform/Modify Bone, Copy Pose, Set Bone Transform, mirror
   node/variable, or extra pose writer, and the accepted manifest/asset registry
   inventory is exactly the two supplied packages.

The verifier traverses from AnimGraph Result and from the RigVM Forward Solve
entry. Disconnected decorative Control Rig/FABRIK nodes receive no credit. L2I
never consumes runtime hand-error telemetry, while L2 never trusts serialized
booleans or a reported solved-state variable.

## Reference solution metadata

- Deliverable overlay: exactly two modified assets,
  `CR_TwoHandPhysics.uasset` and `ABP_TwoHandPhysics.uasset`.
- Native LOC: zero. Map/config/input/mesh/animation edits: zero.
- Intended reference rig: public left/right target variables set two exact
  controls, those controls feed two independent FABRIK arm solvers, and the
  Animation Blueprint passes the supplied base sequence through one runtime
  Control Rig node.
- Expected senior time after locating the two supplied assets: 2-5 hours,
  including Control Rig pin mapping, component-space validation, physics-driven
  tuning, and both-fixture live verification.
- The reference overlay mirrors the exact submission-relative paths under
  `Content/Tasks/t3-both-hands-follow-the-physics-driven-handle/` and contains
  only the two named assets. It is maintainer-owned and never enters an empty
  or candidate submission.

## Anti-gaming notes

1. Attaching the handle to a hand fails exact owner/component/constraint
   identities and independent body motion telemetry.
2. Moving the two hand bones directly fails L2I's reachable graph ban and the
   exact two-file boundary; L2 independently reads live Control Rig controls.
3. Two Bone IK or Transform/Modify Bone may reach one pose, but both are banned
   on the final AnimGraph path and cannot satisfy the RigVM route.
4. Mirroring one hand from the other fails asymmetric grip offsets, independent
   property/control routes, and the two differently oriented world fixtures.
5. A prerecorded animation or keyed handle path fails exact live constraint
   force/body identity and the second non-collinear impulse response.
6. A decorative disconnected Control Rig/FABRIK graph fails result/Forward
   Solve reachability.
7. Snapping the whole character to the handle fails pelvis and bilateral-foot
   component-space preservation.
8. Hard-coding Quartz/Violet values fails the second fact set and the exact
   current grip transforms sampled from the world.
9. Reporting a solved boolean without changing pose earns nothing: all scored
   values come from engine physics, bone, compiled node, hierarchy, and graph
   state.
10. Tick/time spoofing fails the absolute world-clock schedule, normal delegate
    callback count, monotonic target serial, and no-manual-tick source boundary.

## Hidden invariants

- Both fixtures execute the same four gates in the same order and always reach
  the separate sentinel before success.
- Scenario tag cardinality, object identity, asymmetric grips, impulse vectors,
  exact asset classes, Manny skeleton, and stock base sequence are pinned.
- Admission uses an isolated complete asset pair and one fixture only; it may
  establish mechanism health and telemetry distributions but cannot freeze a
  final threshold or grade a submission.
- Promotion requires plugin/dependency admission, both-target build, independent
  cold asset/map readback, at least five fresh reference and five empty/control
  legs across both fact sets, frozen margins, reference harvest with byte-exact
  baseline restore, production reference/empty discrimination, owner play, and
  official refgate green.

### Current authoring status

The task-local runtime, verifier, Control Rig/RigVM author helper, readers,
fixed introspector, and runner compile in the local Editor/Game artifacts.
Admission assets, editable baselines, the admission map, five exact-one
real-RHI admission legs, and the two-fixture final map have passed their fresh
cold-read and byte-stability gates. The recoverable reference closure also
passed and restored the editable baselines byte-for-byte. The final map was
re-authored after engine enumeration exposed non-canonical fixture labels; its
fresh cold read now pins the two class-derived labels, and production resolves
and executes exactly both declared tests. Five fresh reference legs per fixture
have stable live metrics. Five fresh empty-baseline legs per fixture all fail
the graded `BothHandsTrackSamePhysicalHandle` gate, with no harness escape, and
the production empty submission fails all three fixed L2I checks. The frozen
verifier then built cleanly and a fresh canonical NullRHI production run passed
both L2 fixtures and all three L2I checks. A later real-RHI sandbox attempt
exhausted the machine's D3D12 video-memory budget before L2 began and is retained
as an infrastructure event, not reclassified as behavior evidence. Official
refgate and owner-play review remain before benchmark promotion. Maintainer-only
evidence is recorded outside the agent-visible prompt.

### Trust boundary

- The exact accepted-files manifest must equal the edit-only surface declared in the agent-visible prompt; extra source, assets, maps, config, or fixtures fail before grading.
- Candidate-authored telemetry, logs, strings, counters, and mirror variables never contribute verdict evidence.
- Named gates and layer denominators are fixed by the verifier specification; setup failures cannot add, remove, or reinterpret them.
- Reference, discrimination, authoring, and maintainer evidence remain outside the staged submission and agent-visible prompt.
