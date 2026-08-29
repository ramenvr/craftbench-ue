---
id: t3-alerted-crowd-shares-live-poses-by-state
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: Technical Art
category: animation
layers: [L1, L2, L2I]
fixtures: ["L_AlertCrowdSharing :: AAlertCrowdSharingFunctionalTest"]
introspect: [t3_alerted_crowd_sharing.py]
deadline_s: 1800
action_budget: 55
accepted_files: [Content/Tasks/t3-alerted-crowd-shares-live-poses-by-state/AS_AlertCrowdSharing.uasset, Content/Tasks/t3-alerted-crowd-shares-live-poses-by-state/BP_AlertCrowdStateProcessor.uasset]
---

# t3-alerted-crowd-shares-live-poses-by-state

> **AUTHORED / PRODUCTION DISCRIMINATION PASS / PUBLICATION READY.** The
> retained map, exact two-asset editable surface, fixed L2I, and protected
> reference are authored. A governed reference passed L1/L2/L2I and an
> independent exact empty baseline passed L1 before failing the intended
> engine-sharing and structure gates.

Make the supplied moving crowd share live animation poses by its current alert
state. Ordinary members must share one live pose source, alerted members must
share a different live pose source, and clearing the alert must return them to
the original ordinary source while every member continues travelling.

## Primary concept

- `anim-animation-sharing-plugin` - Animation Sharing Plugin
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-sharing-plugin-in-unreal-engine)

### Composed concepts

- `anim-anim-instance` - UAnimInstance / live skeletal evaluation
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/UAnimInstance)
- `setting-up-character-movement` - Character Movement Components
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/movement-components-in-unreal-engine)

### Production-pattern justification

Large crowds commonly reduce animation evaluation cost by registering many
moving actors with the engine Animation Sharing manager, deriving a compact
state from live gameplay facts, and assigning a shared evaluated component per
state. This task keeps the full coupling: live alert membership drives the
state processor, engine-owned leader-pose components drive followers, and
CharacterMovement continues independently. It is not an enum-label exercise.

### Concept-interaction notes

The verifier changes which stable subject identities belong to two groups and
which group is alerted. It then observes manager registration, engine leader
identity, leader animation asset/time, follower bone pose, and movement in the
same PIE world. An alerted label with an unchanged leader, a manually assigned
CopyPose graph, or a stopped crowd cannot satisfy the combined evidence.

## Prompt given to the agent

> Configure the supplied moving crowd so its visible bodies use the engine's
> shared-animation system. Members in the ordinary state must share one live
> pose source; eligible members whose live Alerted fact becomes true must move
> to a distinct alerted source. When that fact clears they must return to the
> original ordinary source.
>
> The level will vary subject identities, group membership, alert order, and
> leader eligibility while it runs. State choice must therefore follow each
> supplied subject's current facts, not actor names, fixed slots, or startup
> values. All crowd members must keep moving throughout both state changes.
>
> Work only in the two supplied editable assets under this task's Content
> folder. Do not replace Animation Sharing with Copy Pose, per-character
> Animation Blueprints, manual leader assignment, sequence playback on each
> actor, or a diagnostic enum/string. Do not add native source or edit the
> level, subject/host scaffold, stock animations, project settings, or tests.

## Workspace state pre-task

- The editable assets are
  `Content/Tasks/t3-alerted-crowd-shares-live-poses-by-state/AS_AlertCrowdSharing`
  and `BP_AlertCrowdStateProcessor`.
- `AS_AlertCrowdSharing` begins with the supplied Manny skeleton/mesh and the
  supplied processor class but no usable state entries.
  `BP_AlertCrowdStateProcessor` begins compiled with no
  `EvaluateAlertState` override, so its safe native fallback remains ordinary.
- The supplied map is
  `Content/Maps/t3-alerted-crowd-shares-live-poses-by-state/L_AlertCrowdSharing`.
  It owns a long floor, six visible moving task subjects, one fixed sharing
  host, one verifier fixture, and the stock playable ThirdPerson game mode.
- The fixed host holds a soft reference to the task setup. Missing submission
  assets therefore leave the world loadable but cannot create an Animation
  Sharing manager.
- The read-only pose library is the mannequin forward-walk sequence for the
  ordinary bucket and forward-jog sequence for the alerted bucket. The agent
  may reference them only through the setup.
- Animation Sharing plugin enablement and the native subject/host scaffold are
  substrate-owned. They are not editable deliverables.

## Verifier specification

L1 builds `ThirdPerson Win64 Development` and `ThirdPersonEditor Win64
Development`, loads the two exact packages, and requires the processor Blueprint
to have status `BS_UpToDate` with its generated class immediately derived from
the supplied native processor base. Submitted source, maps, configs, or extra
task assets fail the asset-only boundary.

L2 runs exactly one `AAlertCrowdSharingFunctionalTest`, derived from
`ACraftBenchFunctionalTest`, in a fresh fixed-60-Hz NullRHI PIE world. Timing is
absolute `UWorld::GetTimeSeconds()` relative to one captured start time. The
fixture never manually ticks the world, manager, character, skeletal component,
or animation instance.

Before phase one, the verifier resolves exact tagged cardinality (six subjects,
one host), overwrites all subject identities with a fresh run token, shuffles
them into two groups of three, chooses alert order from that run token, and
makes exactly one member of each group ineligible. It records every object,
setup, mesh, and initial leader identity. The fixed sequence is:

1. all ordinary; verify manager registration and one common ordinary leader;
2. alert the first hidden group; only its two eligible members change leader;
3. alert the other hidden group; the changed identities swap without changing
   either state leader identity;
4. clear all alerts; all six return to the original ordinary leader.

At every phase, the fixture obtains `UAnimationSharingManager` from the world,
calls `CheckDataForActor`, reads the follower mesh's public engine-owned
`LeaderPoseComponent`, and reads that leader's `UAnimSingleNodeInstance`
animation asset/current time. Pelvis and bilateral-hand component-space bone
transforms on follower and leader must agree. Dense per-frame movement samples
must remain finite, bounded by configured CharacterMovement speed, and advance
for a majority of frames; final displacement and velocity are scaled from the
fixture-owned speed and elapsed world time rather than an agent property.

Fixed L2 denominator: exactly six named gates.

1. `CrowdRegistersWithWorldSharingManager`
2. `AlarmChangesOnlyAssignedMembers`
3. `SharedStateUsesEnginePoseLeader`
4. `ClearedAlarmRestoresOriginalBucket`
5. `CrowdContinuesMovingThroughStateChanges`
6. `LeaderAnimationRemainsLive`

The last gate requires many genuine advances of the engine leader's current
single-node animation time through both alert waves. The final sentinel also
requires every recorded subject identity, exact setup, manager, mesh, and
original ordinary leader to survive all phases.

L2I has a fixed denominator of exactly three gates, emitted on every run:

1. `SetupDefinesTwoEngineSharedPoseStates` - exact one skeleton setup, Manny
   skeleton/mesh, exact state values 0/1, one enabled unrandomized sequence per
   state, no blend/additive AnimBP, no state blending, exact processor class.
2. `ProcessorReadsTheLiveAlertFact` - the compiled exact processor Blueprint's
   only function graph overrides `EvaluateAlertState`; its Subject input drives
   an external get of `bAlerted`, then the exact supplied enum conversion, then
   the return pin. No event graph or other call path is allowed.
3. `SubmissionHasNoIndependentAnimationSubstitute` - the accepted-file manifest
   and exact task asset registry inventory are precisely the two named packages;
   no source, AnimBP, CopyPose asset, map, redirector, or extra package exists.

## Reference solution metadata

- Native LOC: 0.
- Assets edited: exactly 2.
- Expected visual-authoring size: about 18-30 property/graph edits.
- Senior developer estimate: 8-12 hours including manager/state setup,
  state-processor graph work, and live verification.

## Anti-gaming notes

1. Six independent AnimBPs or per-actor sequence playback fail manager/leader
   evidence and the two-file inventory.
2. `CopyPoseFromMesh` or manual `SetLeaderPoseComponent` needs a forbidden extra
   animation/source path and cannot satisfy manager registration plus exact
   setup/graph checks.
3. Only changing an enum or alert label leaves the leader pointer/asset
   unchanged and fails `AlarmChangesOnlyAssignedMembers`.
4. One shared leader for both states fails leader separation and exact setup
   sequence identity.
5. Fixed actor-name logic fails fresh identity/group shuffling and the reversed
   second alert wave.
6. Freezing leader animation time fails the live-time sentinel even if a single
   bone sample happens to look plausible.
7. Stopping or teleporting actors during a switch fails dense CharacterMovement
   displacement/velocity evidence.

## Hidden invariants

- Identity tokens, group assignment, alert order, and ineligible identities are
  fixture-owned and rewritten in PIE on every run.
- Both states use exactly one permutation, so same-state actors must expose the
  same leader pointer and different states must expose different pointers.
- The engine setup, manager, subject mesh, stock sequence paths, and three bone
  names are verifier-owned and pinned through the final sentinel.
- Fixed world time and delta drive every checkpoint; no wall-clock or manual
  tick participates in the verdict.
- NullRHI is intentional: Animation Sharing creates leader skeletal components
  with `AlwaysTickPoseAndRefreshBones`, so the tested data path is CPU animation
  evaluation rather than capture/render output.

### Trust boundary

- The exact accepted-files manifest must equal the edit-only surface declared in the agent-visible prompt; extra source, assets, maps, config, or fixtures fail before grading.
- Candidate-authored telemetry, logs, strings, counters, and mirror variables never contribute verdict evidence.
- Named gates and layer denominators are fixed by the verifier specification; setup failures cannot add, remove, or reinterpret them.
- Reference, discrimination, authoring, and maintainer evidence remain outside the staged submission and agent-visible prompt.
