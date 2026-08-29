---
id: t3-walkable-ground-follows-the-designated-scout
substrate: ThirdPerson
set: craftbench-public
tier: T3
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_WalkableGround :: AWalkableGroundFunctionalTest"]
introspect: [t3_walkable_ground_designated_scout.py]
deadline_s: 1800
action_budget: 55
accepted_files: [Content/Tasks/t3-walkable-ground-follows-the-designated-scout/BP_DesignatedScout.uasset]
---

# t3-walkable-ground-follows-the-designated-scout

> **PUBLISHED-RUNNABLE.** The supplied empty Blueprint, playable production
> map, protected reference, fixed verifier, five-run admission calibration,
> clean reference PASS, and supplied-empty named FAIL are all complete.

Make walkable ground follow the designated scout

## Primary concept

- `navigation-invokers` - Using Navigation Invokers
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/using-navigation-invokers-in-unreal-engine)

### Composed concepts

- `ps-controllers` - Controllers
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/controllers-in-unreal-engine)
- `setting-up-character-movement` - Movement Components
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/movement-components-in-unreal-engine)

### Production-pattern justification

Epic's public Navigation Invokers guide presents agent-centered runtime tile
generation as the production pattern for large/open worlds where building the
whole navigation field is too expensive. This task composes that pattern with
an AI controller's real path request and CharacterMovement. It therefore grades
both halves: ground appears and retires around the moving designated identity,
and an ordinary controlled body can actually traverse the newly live ground.

### Concept-interaction notes

The protected world spans three well-separated ground neighborhoods while only
one supplied scout is designated. The verifier changes the scout identity
token, lane, generation/removal radii, move target, and path segment across
hidden policies. It observes the engine's registered local generator, dynamic
navigation tiles, complete path results, path-following state, and continuous
CharacterMovement together. A global field, permanently retained old region,
near-only positive sample, or direct-transform walk cannot satisfy that matrix.

## Prompt given to the agent

> Configure the supplied visible scout so walkable ground is available only in
> its current neighborhood. A distant goal must begin unreachable. When the
> designated scout moves into that area, routes there must become available and
> an ordinary controlled character must be able to walk to the new goal. After
> the scout has stayed away, the old neighborhood must stop offering routes.
>
> The level changes the designated identity, local ranges, neighborhood
> positions, and goals. Do not make the whole level walkable, keep every visited
> neighborhood forever, move characters by setting transforms, or substitute a
> diagnostic flag/string. Edit only the supplied scout asset; do not edit the
> level, project settings, source, tests, ground, controller, or goals.

## Workspace state pre-task

- Exact editable asset:
  `Content/Tasks/t3-walkable-ground-follows-the-designated-scout/BP_DesignatedScout.uasset`.
  It is a clean compiled child of the supplied `DesignatedScoutCharacter`
  base, with no authored graph behavior and no local-ground generator.
- Protected map:
  `Content/Maps/t3-walkable-ground-follows-the-designated-scout/L_WalkableGround.umap`.
  It contains a broad connected floor covering old/new/far neighborhoods,
  one visible task scout, an independent moving probe, the stock playable Third
  Person game mode, and exactly one production fixture.
- The protected world owns dynamic, local-only navigation configuration.
  That configuration, navigation bounds, goals, controller, test fixture, and
  stock mannequin assets are not editable deliverables.
- The exact one-file task inventory excludes maps, configs, source, redirectors,
  navigation data, alternate Blueprints, and extra assets.

## Verifier specification

This is the fixed intended production contract; it is not certified by the
admission fixture yet.

L1 builds `ThirdPerson Win64 Development` and `ThirdPersonEditor Win64
Development`, loads the exact Blueprint, and requires compile status
`BS_UpToDate`, immediate native parent identity, and the one-file task inventory.

L2 will run exactly one `AWalkableGroundFunctionalTest` in a fresh fixed-60-Hz
NullRHI PIE world. The ordinary world clock drives three phases; neither the
fixture nor the candidate manually ticks the world, navigation system,
controller, character, or movement component.

1. **Old-only phase.** Pin the exact designated scout, its visible skeletal
   body, controller, local generator owner/radii, the exact dynamic default
   Recast data, and local-only generation mode. A complete old path must exist;
   new and far control paths must not.
2. **New-live phase.** Move the verifier-designated scout to the hidden new
   neighborhood and poll on world time. The engine's registered invoker location
   and active tile set must follow it. The new path must become complete while
   the far control stays unavailable.
3. **Retirement/movement phase.** Issue one real controller path request on the
   new path. Observe path-following and bounded continuous CharacterMovement.
   After the removal window, the old path and old populated tile layers must be
   gone; the far control must never have become reachable.

Fixed L2 denominator: exactly four named gates.

1. `FarPathFailsOutsideInvokerRadius`
2. `NewNeighborhoodBecomesNavigable`
3. `OldNeighborhoodLosesNavigation`
4. `NewlyNavigableGroundCarriesRealMove`

The mechanism precondition separately requires dynamic Recast, local-only tile
generation, exactly one designated component owner, exact live registration,
one broad bounds volume, a visible scout, and a playable stock input lane. A
broken protected world routes to `HARNESS-PRECONDITION`, never to a candidate
behavior verdict.

L2I has a fixed denominator of exactly three checks, emitted on every run.

1. `DesignatedAgentOwnsNavigationInvoker` - the exact compiled Blueprint is an
   immediate child of the supplied base and its SCS owns exactly one engine
   local-navigation generator component.
2. `InvokerRadiiAreLocalAndOrdered` - its saved component template has finite
   positive generation/removal radii with removal greater than generation and
   no executable Blueprint graph nodes.
3. `SubmissionHasNoGlobalNavigationSubstitute` - the accepted-files manifest
   and Asset Registry inventory contain only the exact Blueprint; no map,
   config, source, nav data, redirector, or alternate behavior asset exists.

Pass requires L1, all four L2 gates, and L2I 3/3. Admission setup gates do not
increase either production denominator.

## Reference solution metadata

- Native LOC in the reference submission: 0.
- Assets edited by the reference submission: exactly 1.
- Expected visual-authoring size: 3-7 component/property edits.
- Senior developer estimate: 8-12 hours including dynamic-nav diagnosis,
  world-clock generation/retirement calibration, and live negative controls.

## Anti-gaming notes

1. Whole-map pre-bake or unrestricted global runtime generation makes the new
   or far path available in the old-only phase and fails
   `FarPathFailsOutsideInvokerRadius`; the one-file manifest also forbids map or
   config replacement.
2. A large permanent field that merely includes the near region fails the far
   control and leaves old populated tile layers/path alive at retirement.
3. Verifying only the positive near region is insufficient: every phase carries
   the never-near far control, and the final phase independently checks old
   path failure plus zero populated old tile layers.
4. Teleporting or setting the moving probe's transform cannot produce the real
   AI request, engine path-following status, bounded dense frame steps, and
   continuous CharacterMovement evidence together.
5. A Boolean/string such as `HasLocalNav` cannot create registered invoker
   identity, dynamic engine tiles, complete path results, and actual motion.
6. Attaching the local generator to a decoy or global manager fails the exact
   SCS owner and live registration/location sentinel after the hidden identity
   policy changes.

## Hidden invariants

- Hidden policies vary the identity token, symmetric lane, local radii, path
  length, and goal while preserving equivalent geometric difficulty.
- Old, new, and never-near far zones all lie inside one broad navigation bounds
  volume. Bounds coverage therefore cannot explain a negative path.
- Generation radius is smaller than removal radius; both are smaller than zone
  separation. The far control is outside every allowed radius in every phase.
- The engine's invoker location/radii, active tile set, populated tile layers,
  complete path result, path-following status, and body displacement are read
  independently; no candidate-authored telemetry gates the score.
- Actor/component/nav-system/Recast identities remain pinned through the final
  sentinel. Candidate assets never choose thresholds or polling windows.
- Admission rounds 2-6 passed on the same Windows host with stable generation,
  movement, retirement, and never-near controls. Reference/empty production
  discrimination remains the final behavioral freeze boundary.

### Trust boundary

- The exact accepted-files manifest must equal the edit-only surface declared in the agent-visible prompt; extra source, assets, maps, config, or fixtures fail before grading.
- Candidate-authored telemetry, logs, strings, counters, and mirror variables never contribute verdict evidence.
- Named gates and layer denominators are fixed by the verifier specification; setup failures cannot add, remove, or reinterpret them.
- Reference, discrimination, authoring, and maintainer evidence remain outside the staged submission and agent-visible prompt.
