---
id: t3-the-worker-keeps-its-new-plan-after-the-signal
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: AI & Behavior
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_WorkerPlan :: AWorkerPlanFunctionalTest"]
introspect: [t3_worker_keeps_new_plan.py]
deadline_s: 1800
action_budget: 60
accepted_files: [Content/Tasks/t3-the-worker-keeps-its-new-plan-after-the-signal/ST_WorkerPlan.uasset]
---

# t3-the-worker-keeps-its-new-plan-after-the-signal

> **Status: AUTHORED / CERTIFIED / PUBLIC.** The retained map is playable with
> the stock ThirdPerson GameMode. The Git-head reference passes L1, the exact
> runtime test, and all three StateTree introspection checks. The independently
> staged empty StateTree shell passes L1 and fails the intended
> `IdleStateActiveBeforeSignal` behavior gate without a harness failure.

Build the supplied worker's decision asset so it waits without moving, accepts
a new plan only when a separate signal actor announces it, then keeps executing
that plan after the signal goes quiet.

## Primary concept

- `ai-statetree` - StateTree decision logic

### Composed concepts

- `ai-navigation` - controller path following
- `ai-world-signal` - a separate world actor owns the changing signal
- `ai-persistent-state` - a completed transition outlives its trigger

### Production-pattern justification

Production workers commonly translate a short-lived dispatch signal into a
long-lived plan. The signal source, decision state, and navigation executor are
different systems. This task grades that hand-off: StateTree must own the
transition and the persistent state, while path following—not transform writes—
must own visible motion.

### Concept-interaction notes

The verifier begins with the signal false and the worker stationary. It pulses
the separate signal actor, waits for the StateTree transition and navigation
request, then clears the signal while the destination remains far away. The
worker must remain in the active plan and continue making physical progress.

## Prompt given to the agent

> Configure the supplied worker's editable decision asset. The worker must wait
> in its idle plan while the separate signal actor is quiet. When that actor
> announces the new destination, transition into an active plan and navigate
> there.
>
> The announcement is brief. After it goes quiet, keep the active plan and
> continue moving toward the announced destination. The visible worker must not
> jump or teleport.
>
> The decision and the move must be owned by the supplied decision system. Do
> not replace it with per-frame Blueprint polling, direct transform movement, a
> timer loop, or a mirrored state variable. Edit only the supplied task asset,
> save it, and do not add native source or edit the level, project settings,
> tests, signal actor, worker, or destination.

## Workspace state pre-task

- The editable asset is
  `Content/Tasks/t3-the-worker-keeps-its-new-plan-after-the-signal/ST_WorkerPlan.uasset`.
- It uses the AI-component StateTree schema and begins with a `Root`, `Idle`, and
  `Active` shell. The task palette supplies a condition that reads the uniquely
  tagged separate signal actor and a navigation task that issues a real AI move
  request to that actor's published destination.
- The read-only map is
  `Content/Maps/t3-the-worker-keeps-its-new-plan-after-the-signal/L_WorkerPlan.umap`.
  It contains one visible tagged worker, one separate tagged signal actor, one
  far destination, navigable ground, and one functional-test fixture.
- The signal starts false. The fixture alone pulses and clears it at hidden
  world-clock checkpoints. The worker and signal have no actor Tick policy.

## Verifier specification

L1 builds `ThirdPerson Win64 Development` and `ThirdPersonEditor Win64
Development`, then loads and compiles the exact StateTree package.

L2 runs exactly one `AWorkerPlanFunctionalTest` in fixed-step PIE. Timing comes
from the ordinary world clock; the fixture never manually ticks the world,
StateTree, controller, or pawn. It requires exactly one tagged subject, signal,
and destination, a visible skeletal body, the exact compiled StateTree, and a
live StateTree AI component. It observes the engine node callbacks, controller
path-following status, request result, frame-to-frame displacement, and subject
position. The signal is pulsed and then cleared by the separate signal actor.

Named L2 gates:

1. `IdleStateActiveBeforeSignal`
2. `SubjectStationaryBeforeSignal`
3. `TransitionedAndRemainsActive`
4. `ContinuesMoving`
5. `VisibleWorkerAndNavigationHealthy` (`HARNESS-PRECONDITION`)

The sentinel requires one navigation-task entry, zero exits after the signal
clears, continued displacement after the clear, and no teleport-sized frame.

L2I has a fixed denominator of exactly three gates:

1. `StateTreeOwnsWorkerBehavior` - the exact package is compiled with the AI
   component schema and the exact `Root`/`Idle`/`Active` hierarchy.
2. `IdleTransitionReadsSeparateSignal` - the single Idle-to-Active transition
   contains the supplied separate-actor signal condition.
3. `ActiveStateUsesNavigationTask` - Active contains the supplied StateTree
   navigation task, and the task content boundary contains no submitted native
   source or alternate Blueprint behavior asset.

All three checks are emitted on every introspection run. Pass requires L1,
every graded L2 gate, and 3/3 L2I.

## Reference solution metadata

- Native LOC: 0.
- Expected assets edited: one supplied StateTree.
- Expected visual-authoring size: 6-12 edits.
- Senior developer estimate: 4-7 hours including live validation.

## Anti-gaming notes

1. Tick polling plus a Boolean fails the exact StateTree transition check.
2. `SetActorLocation`, teleport, or movement input fails engine navigation and
   dense-displacement evidence.
3. Always moving fails the quiet pre-signal window.
4. Moving only while the signal is true fails after the verifier clears it.
5. A fake `Active` variable cannot replace the StateTree task enter/exit facts.
6. Reading the worker or fixture instead of the separate signal actor fails the
   exact condition type and live signal-read telemetry.
7. A one-shot move or short destination fails continued post-clear progress.

## Hidden invariants

- Pulse and clear times are verifier-owned and measured in world time.
- Subject, signal, destination, StateTree, AI component, and skeletal mesh
  identities remain pinned through the sentinel.
- The destination is far enough that a correct admitted worker is still moving
  in the post-clear observation window.
- Admission calibrates displacement tolerances; no candidate-authored value can
  become a threshold.

### Trust boundary

- The exact accepted-files manifest must equal the edit-only surface declared in the agent-visible prompt; extra source, assets, maps, config, or fixtures fail before grading.
- Candidate-authored telemetry, logs, strings, counters, and mirror variables never contribute verdict evidence.
- Named gates and layer denominators are fixed by the verifier specification; setup failures cannot add, remove, or reinterpret them.
- Reference, discrimination, authoring, and maintainer evidence remain outside the staged submission and agent-visible prompt.
