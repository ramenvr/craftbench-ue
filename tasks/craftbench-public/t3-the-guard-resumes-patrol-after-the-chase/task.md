---
id: t3-the-guard-resumes-patrol-after-the-chase
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: AI & Behavior
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_GuardPatrolChase :: AGuardPatrolChaseFunctionalTest"]
introspect: [t3_guard_resumes_patrol_after_chase.py]
deadline_s: 1800
action_budget: 60
accepted_files: [Content/Tasks/t3-the-guard-resumes-patrol-after-the-chase/BB_GuardPatrolChase.uasset, Content/Tasks/t3-the-guard-resumes-patrol-after-the-chase/BT_GuardPatrolChase.uasset]
---

# t3-the-guard-resumes-patrol-after-the-chase

Make the supplied guard patrol between its marked posts while the yard is quiet. When the separate alert source names a live target, the guard must immediately leave patrol, chase that moving target, and then return to the same patrol route after the alert clears.

## Primary concept

- `behavior-trees` - a priority decision tree whose observer aborts a lower-priority branch

### Composed concepts

- `bt-node-reference-composites` - ordered selector and branch sequences
- `bt-node-reference-decorators` - Blackboard observation and abort policy
- `ps-controllers` - controller-owned decision execution
- `setting-up-character-movement` - visible path-following character movement

### Production-pattern justification

Production guard AI commonly gives an interrupting chase higher priority than an ambient patrol and lets an observed world fact abort whichever branch is no longer valid. This task grades the handoff in both directions. A cosmetic tree beside native or per-frame branching is not equivalent: the supplied controller must execute the editable decision assets, and engine-owned active-node and path-following state must agree with the visible motion.

### Concept-interaction notes

The signal, decision state, navigation request, and visible character are separate systems. The fixture varies when the signal changes, which target moves, and which two marker identities form the route. The decision asset must therefore read live object keys and use observer-driven branch changes rather than memorized positions or elapsed times.

## Prompt given to the agent

> Configure the supplied guard's editable decision assets so the guard continuously patrols between the two marked posts while the yard is quiet.
>
> When the separate alert source announces a live target, the guard must immediately leave patrol and chase that moving target. When the alert clears, the guard must stop chasing and resume the original two-post patrol route.
>
> Keep the visible guard under its supplied controller and movement system. The alert timing, target motion, and marker identities can change between verification runs, so react to the live world state rather than using fixed delays or memorized coordinates.

## Workspace state pre-task

### Agent-editable assets

- `/Game/Tasks/t3-the-guard-resumes-patrol-after-the-chase/BB_GuardPatrolChase`
- `/Game/Tasks/t3-the-guard-resumes-patrol-after-the-chase/BT_GuardPatrolChase`

The two assets are the complete writable submission surface. The Blackboard shell contains the supplied keys `AlertActive`, `LiveTarget`, and `PatrolPoint`. The Behavior Tree shell is empty and references that Blackboard. Do not create substitute decision assets or modify verifier-owned map actors.

### Read-only support

- `AGuardPatrolCharacter` is a visible path-following character.
- `AGuardPatrolAIController` loads and runs the exact editable decision asset and mirrors the separate alert actor only into the supplied Blackboard keys.
- `AGuardAlertSource`, the moving target, the two marker actors, navigation, fixture, and map are verifier-owned.
- `UGuardBTTask_SelectNextPatrolPoint` selects the other live marker actor and writes `PatrolPoint`; the asset must schedule it before a normal Move To task.

## Verifier specification

### L1 - structural and packaging gate

- The ThirdPerson Editor and Game targets compile.
- The exact two writable assets exist at the declared paths, load without errors, and retain the supplied Blackboard key types.
- No extra submission asset, native source replacement, or undeclared package supplies the behavior.

### L2 - runtime behavior

The fixture resolves exact tagged support actors and fails graded if the submission-owned asset contract is missing. It uses a normal world-clock checkpoint schedule and does not manually tick the world. Alert timing, target path, and route marker assignment come from verifier-owned actors and differ between authoring and production runs.

Named gates:

- `GATE[PrioritySelectorAndDecoratorsAuthored]`: the controller is running the exact submitted tree and Blackboard; quiet-state active-node telemetry shows the patrol Move To key, not a native or per-frame shadow.
- `GATE[TrueKeyAbortsPatrolAndStartsChase]`: changing the separate alert actor to true updates the live Blackboard and replaces the active patrol request with a target request inside the response window.
- `GATE[ChaseClosesDistance]`: while the target moves, engine-owned path-following remains active and the guard closes a meaningful distance without teleporting.
- `GATE[ResetFalseExitsChase]`: clearing the alert while chase is still in progress removes the target branch and returns engine-owned active-node telemetry to patrol.
- `GATE[PatrolResumesAfterReset]`: after the reset the guard reaches a route marker and then makes progress toward the other live marker, proving the original patrol loop resumed.

### L2I - fixed asset introspection

The fixed introspector loads the declared Behavior Tree and Blackboard and reports exactly four checks:

1. `PrioritySelectorAndDecoratorsAuthored` - the root is a priority selector with chase before patrol.
2. `TrueKeyObserverAbortsPatrol` - the chase branch observes the Boolean alert key and uses `Both` observer aborts.
3. `ChaseBranchUsesLiveTarget` - the chase sequence moves to the live target object key.
4. `PatrolBranchSelectsAndMoves` - the patrol sequence loops, selects a live marker, and moves to the patrol-point object key.

The introspector reads engine-owned tree nodes and Blackboard key types. It does not trust submission-authored mirror variables, labels, comments, or screenshots.

### Runtime identity and motion controls

- Exact actor-tag cardinality and exact class checks are graded, never opt-out preflights.
- The fixture verifies the controller's `UBehaviorTreeComponent`, active `UBTTask_MoveTo` key, `UBlackboardComponent`, and `UPathFollowingComponent` state.
- Per-frame displacement is bounded; teleports, direct transform writes, and a tree that is present but not executing fail named gates.
- The unselected marker and the non-target support actors remain unchanged.
- A final scheduled sentinel fails if the entire quiet-alert-clear-resume state machine did not finish.

## Reference solution metadata

- reference type: two Blueprint assets only
- writable asset count: exactly 2
- expected L2 result: all five named runtime gates pass
- expected L2I result: 4/4
- reference status: authored and cold-read as exact two packages; production
  reference passed L1/L2/L2I and the byte-identical empty baseline failed the
  intended L2/L2I topology gates

## Anti-gaming notes

- Always chasing fails the initial quiet patrol gate and exact alert-key checks.
- Always patrolling fails the observer-abort transition and chase-distance gate.
- A Tick branch, hard-coded delay, direct transform write, or native shadow fails fixed L2I plus engine-owned active-node/path-following telemetry.
- A decorative but unexecuted tree fails exact controller tree identity.
- A one-way true transition fails the mid-chase false reset and `PatrolResumesAfterReset`.
- Memorized coordinates fail because marker actors and target motion are fixture-owned and varied.
- Clearing and rebuilding all Blackboard state fails exact supplied key types and unrelated-key preservation.

## Hidden invariants

- The fixture changes only the separate alert actor; it never writes the guard's Blackboard directly.
- The reset happens before the chase destination can be reached, so returning to patrol cannot be explained by chase completion.
- The two patrol marker identities and target path are pinned independently of displayed labels.
- Protected-support corruption is a verifier error only when the protected packages themselves are missing or invalid. Submission-owned asset corruption is a graded failure.

## Discrimination

See `discrimination/MATRIX.md`. The committed matrix contains only the reference and empty-baseline rows.

### Trust boundary

- The exact accepted-files manifest must equal the edit-only surface declared in the agent-visible prompt; extra source, assets, maps, config, or fixtures fail before grading.
- Candidate-authored telemetry, logs, strings, counters, and mirror variables never contribute verdict evidence.
- Named gates and layer denominators are fixed by the verifier specification; setup failures cannot add, remove, or reinterpret them.
- Reference, discrimination, authoring, and maintainer evidence remain outside the staged submission and agent-visible prompt.
