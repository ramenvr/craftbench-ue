---
id: t3-guard-aims-only-at-the-visible-target
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: AI & Behavior
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_GuardVisibleAim :: AGuardVisibleAimLeftHighFunctionalTest", "L_GuardVisibleAim :: AGuardVisibleAimRightLowFunctionalTest"]
introspect: [t3_guard_visible_aim.py]
deadline_s: 1800
action_budget: 70
accepted_files: [Content/Tasks/t3-guard-aims-only-at-the-visible-target/ABP_GuardVisibleAim.uasset]
---

# t3-guard-aims-only-at-the-visible-target

Keep a walking guard's base locomotion live while its upper body aims only at
the target that the sight-perception system currently sees. Occlusion must
remove the aim, and restored line of sight must reacquire it.

## Primary concept

- `anim-aim-offset` - a directional Aim Offset is evaluated as an additive
  overlay over a live locomotion pose

### Composed concepts

- `ai-perception` - engine sight stimuli, perception updates, and forgetting
- `setting-up-character-movement` - controller-owned path following remains
  ordinary walking throughout every sight transition
- `animation-blueprints` - live AnimInstance state drives the compiled graph

### Production-pattern justification

Combat AI commonly needs to keep traversing a route while visually tracking a
threat. A convincing result cannot rotate the whole pawn toward a guessed
actor, play a non-additive montage, or preserve a stale target through a wall.
Perception identity, locomotion, and evaluated upper-body pose must therefore
agree in the same frames.

## Prompt given to the agent

> Update the supplied guard animation so a moving guard aims its upper body at
> the target it can currently see. Keep the walking pose and movement running
> underneath the aim. When the target becomes hidden, return the upper body to
> neutral; when it becomes visible again, reacquire it and resume aiming.
>
> The level contains a nearer hidden decoy as well as the visible target and
> exercises two layouts with different target sides and elevations. Edit only
> the supplied `ABP_GuardVisibleAim` animation Blueprint and save it. Do not
> edit the level, tests, native code, project settings, target actors, or
> occluders. Do not rotate or teleport the whole character and do not replace
> locomotion with a montage.

## Workspace state pre-task

- Editable asset:
  `Content/Tasks/t3-guard-aims-only-at-the-visible-target/ABP_GuardVisibleAim.uasset`.
  Its native AnimInstance parent already exposes live `GroundSpeed`, `AimYaw`,
  `AimPitch`, `AimAlpha`, and `PerceivedTarget` values derived from the guard's
  actual sight listener. The baseline graph plays locomotion but has no aim
  overlay.
- Read-only map:
  `Content/Maps/t3-guard-aims-only-at-the-visible-target/L_GuardVisibleAim.umap`.
  It contains two independent scenario groups. Each group has a moving main
  guard, a perception-disabled locomotion control twin, one visible target,
  one closer sight-occluded decoy, a movable sight occluder, and distinct
  destinations.
- Sight is a real `UAIPerceptionComponent` configured with
  `UAISenseConfig_Sight`; targets use real sight stimulus-source components.
  A lost stimulus enters the engine-owned `ForgetActor` lifecycle.

## Verifier specification

L1 builds `ThirdPersonEditor Win64 Development` and `ThirdPerson Win64
Development`.

L2 runs both listed fixtures under `-nullrhi` in fresh PIE worlds. Each fixture
pins eight map-authored actor identities, the exact generated AnimInstance
class, live Recast navigation, visibility-blocking occluders, two independent
AI controllers, and the real sight component. The fixture issues parallel
`MoveToLocation` requests and never moves or manually ticks either guard.

Three world-clock checkpoints are derived from that fixture's own Prepare
epoch. The first observes the visible target while a nearer decoy remains
behind its permanent wall. It then moves only the verifier-owned switch wall
into the current sight ray. The second requires the target to leave both the
current and known sight sets and the AnimInstance/pose to return to neutral,
then removes the wall. The third requires a new perception revision and the
same exact target to be reacquired. Dense samples retain frame-step and
character-facing evidence across all phases.

Named gates:

1. `OnlySightPerceivedIdentityMayDriveAim` - the controller's current target,
   current sight set, known sight set, and target identity agree; the nearer
   hidden decoy is absent.
2. `PerceivedTargetDrivesAdditiveAimOverlay` - live aim coordinates have the
   world-authored yaw/pitch signs and the evaluated `spine_03` pose diverges
   from the simultaneous no-sight control twin.
3. `OccludedTargetStopsDrivingAim` - the real sight revision advances through
   loss/forget, current and known identity clear, alpha/coordinates neutralize,
   and the evaluated upper body returns toward the control pose.
4. `ReappearingTargetIsReacquired` - removing the wall reacquires the same
   target and restores the directional evaluated-pose response.
5. `BaseLocomotionRemainsContinuous` - main and control traverse every phase as
   walking characters without a teleport-sized frame step or actor-facing
   rotation away from movement.

L2I runs `t3_guard_visible_aim.py` with a fixed denominator of two:

1. `SightStateFeedsAimCoordinates` - the task-owned native AnimInstance is the
   exact parent, GroundSpeed feeds the locomotion player, and AimYaw,
   AimPitch, and AimAlpha feed the aim node.
2. `AimOffsetIsAdditiveOverLocomotion` - exactly one Rifle Aim Offset player
   receives exactly one locomotion BlendSpace as BasePose and directly writes
   the final pose; montage Slot nodes are absent.

Missing/ambiguous verifier-owned world facts and missing navigation are
`HARNESS-PRECONDITION:` errors. Any submission-reachable graph, class,
perception identity, pose, rotation, or movement failure is graded by a named
ASCII gate.

## Reference solution metadata

- Native LOC: 0.
- Expected assets edited: one Animation Blueprint.
- Expected editor changes: 6-12 AnimGraph nodes/connections.
- Senior developer estimate: 4-8 hours including animation/perception tuning.

## Anti-gaming notes

1. `GetAllActors`, nearest-actor selection, or a cached actor chooses the closer
   occluded decoy or survives the forget transition and fails sight identity.
2. Controller or pawn rotation is caught by velocity-versus-actor-facing
   telemetry and still produces no additive spine delta against the control.
3. A montage or full-body replacement fails the fixed AnimGraph topology even
   if a screenshot resembles aiming.
4. Mirrored AimYaw/Pitch constants fail the opposite side/elevation layout.
5. An authored mirror boolean or target variable cannot replace independent
   reads of engine perception sets and evaluated bone transforms.
6. Pausing movement during sight changes fails per-phase displacement and live
   walking mode.
7. Teleports are caught by dense frame steps; replacing actors breaks pinned
   scenario references.

## Hidden invariants

- Layouts vary target side, elevation, wall position, group origin, and sight
  transition timing while using the same submitted AnimBlueprint class.
- The visible target and closer decoy both register real sight stimuli. Only
  line of sight differentiates them.
- Runtime pose evidence comes from evaluated skeletal bone transforms, not an
  agent-authored mirror value.
- Static thresholds are provisional. This task remains HOLD until repeated
  real admission runs calibrate sight timing and pose margins, and reference,
  empty, nearest-target, actor-rotation, and montage controls discriminate.

### Trust boundary

- The exact accepted-files manifest must equal the edit-only surface declared in the agent-visible prompt; extra source, assets, maps, config, or fixtures fail before grading.
- Candidate-authored telemetry, logs, strings, counters, and mirror variables never contribute verdict evidence.
- Named gates and layer denominators are fixed by the verifier specification; setup failures cannot add, remove, or reinterpret them.
- Reference, discrimination, authoring, and maintainer evidence remain outside the staged submission and agent-visible prompt.
