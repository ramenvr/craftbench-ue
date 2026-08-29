---
id: t3-both-walkers-yield-and-still-arrive
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: AI & Behavior
category: gameplay
layers: [L1, L2]
fixtures: ["L_BothWalkersYield :: ABothWalkersYieldLayoutAFunctionalTest", "L_BothWalkersYield :: ABothWalkersYieldLayoutBFunctionalTest"]
deadline_s: 1800
action_budget: 60
accepted_files: [Content/Tasks/t3-both-walkers-yield-and-still-arrive/BP_YieldingWalker.uasset]
---

# t3-both-walkers-yield-and-still-arrive

Configure one supplied walker asset so two independently controlled walkers
reactively share a crossing while both preserve their own navigation request.
The same asset is exercised in two world-authored layouts and against matched
solo controls.

## Primary concept

- `navigation-avoidance` - reciprocal local avoidance for moving agents

### Composed concepts

- `ai-navigation` - independent controller-owned path requests
- `setting-up-character-movement` - genuine walking movement and capsule collision
- `ps-actors` - two instances share one asset but retain distinct world facts

### Production-pattern justification

Crowds and companion AI routinely need local collision avoidance without
abandoning their global path. A robust implementation must respond to a live
conflict, preserve collision clearance, and resume progress toward each
independent goal. Checking arrival alone would reward freezing, physics pushes,
or baked detours, so this task compares the crossing pair with simultaneous
solo copies of the same paths.

### Concept-interaction notes

Each layout supplies four instances of the same editable class: a crossing
pair and two translated solo controls. The fixture supplies distinct starts,
goals, speeds, and capsule radii, then issues all four path requests in one
world frame. It compares actual movement velocity with the engine's current
path-request velocity, and compares each crossing trajectory with its matched
solo trajectory. Thus the avoidance response, ordinary walking, controller
path following, and per-instance world facts must agree.

## Prompt given to the agent

> Configure the supplied shared walker asset so two walkers approaching the
> same crossing steer around one another while both continue toward their own
> assigned destinations. Both must begin together, keep physical capsule
> collision enabled, remain ordinary walking characters, and arrive without a
> jump, teleport, prolonged stop, or overlap.
>
> The level exercises the same asset in two different crossing layouts. Starts,
> goals, movement speeds, and body radii differ between them. Each crossing
> walker also has a matched solo copy following the equivalent path elsewhere
> in the world; a permanent curve or time-based sidestep that also affects the
> solo copy is not a conflict response.
>
> Edit only the supplied walker asset and save it. Do not add native source,
> replace controller navigation with transform writes or per-frame scripted
> movement, disable collision, delay one walker, edit the level, or edit tests
> and project settings.

## Workspace state pre-task

- The editable asset is
  `Content/Tasks/t3-both-walkers-yield-and-still-arrive/BP_YieldingWalker.uasset`.
  It is a visible character Blueprint with an inherited capsule, character
  movement component, and task-owned AI controller. Its event graphs are empty.
- Its initial movement settings do not participate in reciprocal avoidance.
  Ordinary navigation, collision, mesh, animation, and walking defaults are
  already supplied.
- The read-only map is
  `Content/Maps/t3-both-walkers-yield-and-still-arrive/L_BothWalkersYield.umap`.
  It contains two independent scenario groups, each with a crossing pair,
  matched translated solo controls, four tagged destinations, and one fixture.
- The fixtures read the map-authored scenario facts and issue all movement
  requests. They never move, tick, or teleport a walker manually.

## Verifier specification

L1 builds both `ThirdPersonEditor Win64 Development` and `ThirdPerson Win64
Development`.

L2 runs the two named fixtures in fresh PIE worlds. Each fixture resolves its
scenario, four walkers, and four destinations by exact tags. It requires a
single shared Blueprint-generated walker class, four distinct AI controllers,
walking movement, query-and-physics capsule collision that blocks Pawn, and a
live navigation mesh. It writes the scenario's speed and radius facts before
issuing four independent `MoveToLocation` requests in one StartTest frame.

The engine advances the world. The fixture densely samples identity, location,
velocity, the controller's current global path-segment direction, movement mode, path status, frame step,
capsule clearance, goal progress, and live avoidance registration. Checkpoints
are absolute world-clock values derived from each fixture's Prepare epoch, so
the second fixture cannot reuse the first fixture's elapsed world time.

Named gates:

1. `BothAgentsConflictDrivenSteering` - before capsule contact, both crossing
   walkers must show a live registered avoidance response and must divert from
   their requested path more than their matched solo copies.
2. `BothAgentsKeepForwardProgress` - both crossing walkers must make concurrent
   progress, stay walking, avoid prolonged stalls, and remain free of
   teleport-sized frame steps.
3. `NoOverlapEnRoute` - capsule clearance must remain positive while collision
   remains query-and-physics with Pawn blocking.
4. `BothAgentsReachOwnGoals` - both crossing walkers and their controls must
   finish their own controller requests within the final goal band.

Harness-only failures use `HARNESS-PRECONDITION:` and are limited to missing or
ambiguous verifier-owned map facts, missing navigation data, or corrupt fixture
identity. Submission-reachable asset, movement, collision, steering, progress,
and arrival failures are always graded named failures.

## Reference solution metadata

- Native LOC: 0.
- Expected assets edited: one supplied Blueprint.
- Expected editor changes: 3-8 component-default edits.
- Senior developer estimate: 3-6 hours including trajectory validation.

## Anti-gaming notes

1. A permanent or timed sidestep also bends the matched solo trajectory and
   fails `BothAgentsConflictDrivenSteering`.
2. Staggering one start is impossible because the verifier owns all four
   controller requests and issues them in one frame.
3. Freezing or yielding with only one walker fails the per-agent concurrent
   progress and conflict-response facts.
4. Disabling capsule collision fails the live collision gate even if paths
   visually cross without contact.
5. Relying on a physics push produces no pre-contact requested-vs-actual
   steering margin and fails before the clearance assertion can reward it.
6. Teleporting, destroying/replacing a walker, or writing transforms is caught
   by pinned identities, dense frame steps, walking mode, and live path status.
7. Hardcoding one crossing orientation or speed is rejected by the second
   rotated layout with different path lengths, speeds, and capsule radii.
8. Sending both instances to one goal fails exact per-controller goal progress
   and final goal identity.

## Hidden invariants

- Layout A and B use distinct origins, rotations, speeds, path lengths, and
  capsule radii while sharing the same submitted class.
- Solo controls run simultaneously and use translated copies of the matched
  pair paths; they are outside every other walker's consideration radius.
- Steering is observed from engine-owned actual velocity, requested path
  velocity, live avoidance-manager registration, and world transforms, never
  from a candidate-authored mirror variable.
- The fixture records minimum clearance and maximum per-frame displacement
  continuously, not only at the named checkpoints.
- Thresholds are frozen from five byte-stable fresh Detour Crowd passes plus
  four admission-only controls: steering `3.0 deg`, pair-over-solo steering
  `1.5 deg`, pair-over-solo lateral deviation `12 uu`, clearance `4 uu`, stall
  `0.75 s`, frame step `28 uu`, and arrival band `115 uu`.

### Trust boundary

- The exact accepted-files manifest must equal the edit-only surface declared in the agent-visible prompt; extra source, assets, maps, config, or fixtures fail before grading.
- Candidate-authored telemetry, logs, strings, counters, and mirror variables never contribute verdict evidence.
- Named gates and layer denominators are fixed by the verifier specification; setup failures cannot add, remove, or reinterpret them.
- Reference, discrimination, authoring, and maintainer evidence remain outside the staged submission and agent-visible prompt.
