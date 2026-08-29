---
id: t2-menu-blocks-gameplay-and-restores-it-exactly
substrate: ThirdPerson
set: craftbench-public
rhi: d3d11
tier: T2
capability_bucket: Gameplay Programming
category: input
layers: [L1, L2, L2I]
fixtures: ["L_MenuInputRouting :: AMenuInputFunctionalTest"]
introspect: [t2_menu_blocks_gameplay_and_restores_it_exactly.py]
deadline_s: 900
action_budget: 40
accepted_files: [Content/Tasks/t2-menu-blocks-gameplay-and-restores-it-exactly/WBP_InputBlockingMenu.uasset]
---

# t2-menu-blocks-gameplay-and-restores-it-exactly

This compositional task grades the boundary between an activatable menu's
input route and the live player's pre-existing gameplay bindings. It is not a
focus-only variant: both the UI action and the suppressed gameplay action are
driven through the same physical key, and the exact prior binding state must
survive two different menu assignments.

## Primary concept

- `commonui-with-enhanced-input` - Using CommonUI With Enhanced Input
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/using-commonui-with-enhnaced-input-in-unreal-engine)

### Composed concepts

- `commonui-with-enhanced-input` - Using CommonUI With Enhanced Input
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/using-commonui-with-enhnaced-input-in-unreal-engine)
- `commonui-input-technical-guide` - CommonUI Input Technical Guide
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/commonui-input-technical-guide-for-unreal-engine)
- `enhanced-input` - Enhanced Input
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/enhanced-input-in-unreal-engine)
- `input-mapping-context` - UInputMappingContext
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/EnhancedInput/UInputMappingContext)

### Production-pattern justification

Epic's Common UI input guide describes activatable UI trees that route an
active leaf's actions before normal game input, while Epic's CommonUI with
Enhanced Input guide documents UI actions backed by the same input system as
gameplay. Lyra's publicly documented frontend and modal layers use this
production pattern: pushing a menu changes which actions may respond without
destroying the player's underlying gameplay configuration, and popping it
restores the prior route.

### Concept-interaction notes

The real activation stack establishes which menu is the current input leaf.
That leaf consumes its assigned action through the local player's UI action
router, while the live input subsystem owns the gameplay, menu, and unrelated
binding sets and their priorities.

The placed world policy changes the assigned menu binding identity and
priority between pushes. It also changes once while the first menu remains
active, so deactivation must remove the identity that was actually applied,
not whichever identity the policy exposes later.

## Prompt given to the agent

> Complete the supplied editable menu screen. While it is the active top
> screen, pressing the shared menu/gameplay key must invoke the menu action and
> must not invoke the gameplay action beneath it. Opening the menu must add
> only the binding set currently assigned by the placed policy, at that
> policy's current priority. Closing it must remove only the set that this
> particular opening added: all gameplay bindings, unrelated bindings, their
> priorities, and their ability to respond after the menu closes must be
> preserved exactly. The policy can change while a menu is open and between
> later openings, so do not hardcode an asset, cache a construction-time
> default, clear every binding, or restore a guessed default configuration.
> Preserve the supplied activation lifecycle and action route. Work only in
> the supplied editable menu asset; the level, visible playable character,
> host, policy, and tests are read-only task support.

## Workspace state pre-task

Editable asset:

- `Content/Tasks/t2-menu-blocks-gameplay-and-restores-it-exactly/WBP_InputBlockingMenu`
  derives from the supplied activatable menu base. Its visible panel already
  exists, and its activation/deactivation behavior is empty.
- The asset declares an `AppliedMenuContext` object variable for remembering
  the identity owned by one activation. The agent may add further local state.

Supplied source under
`Source/ThirdPerson/Tasks/t2-menu-blocks-gameplay-and-restores-it-exactly/`
defines the placed policy, lifecycle host, real activation-stack root, and the
Blueprint-facing menu base. These files are starting support rather than the
requested deliverable.

Verifier-owned support assets under
`Content/Maps/t2-menu-blocks-gameplay-and-restores-it-exactly/Support/`
contain two distinct gameplay/menu/unrelated context sets. Their identities,
priorities, and shared key are intentionally not part of the prompt contract.
The protected task map is
`Content/Maps/t2-menu-blocks-gameplay-and-restores-it-exactly/L_MenuInputRouting.umap`.
It uses the stock Third Person game mode, PlayerController, visible Manny/Quinn
character, movement inputs, a PlayerStart, the host and policy, and both the
final and admission fixtures.

Task-local config overlays select the Common UI game viewport client before
PIE creates the local player and enable Common UI's Enhanced Input support
before its settings singleton initializes.

## Verifier specification

Only deterministic L1, L2, and L2I facts gate the task.

### L1 - project health

```text
assert ThirdPersonEditor Win64 Development builds
assert ThirdPerson Win64 Development builds
```

### L2I - saved menu structure

The fixed introspector loads the exact deliverable path and delegates graph
inspection to a verifier-owned editor helper.

```text
menu_is_real_activatable_screen:
    exact asset exists, compiles up to date, and directly derives from the
    supplied activatable menu base

activation_adds_only_current_world_context:
    activation graph reads the current policy context and priority, stores
    the applied identity, and calls the targeted add operation

deactivation_removes_captured_context_without_global_clear:
    deactivation graph reads the stored identity and calls the targeted remove
    operation; no graph clears all mappings or switches input through a
    controller-only UI mode shortcut

menu_declares_ui_routing_config:
    the saved menu supplies an active-leaf UI input configuration rather than
    bypassing the activatable hierarchy
```

### L2 - live stack, action routing, and exact restoration

The fixture derives from `ACraftBenchFunctionalTest`, uses only world-clock
checkpoints, and injects the shared key through the real game viewport client.
It independently reads live context presence/priority from the local-player
input subsystem and action counters from the pawn's engine input component.

```text
Preflight:
    require exact protected support assets, Common UI viewport, one local
    player/controller, initialized UI action router, visible possessed stock
    Third Person pawn, Enhanced Input component, movement bindings, one host,
    and one world policy

Leg A prior state:
    add hidden gameplay A and unrelated A contexts with distinct priorities
    prove the shared key invokes gameplay before the menu opens

Leg A active:
    push exact editable menu through the real activation stack
    require menu A at policy priority while gameplay A, unrelated A, and stock
    movement context retain their exact prior priorities
    inject shared key; require current top menu action increments once and the
    gameplay action remains unchanged

Leg A hostile pop:
    while menu A is still active, change world policy to menu B
    pop; require menu A removed, menu B absent, and every prior context exact
    inject shared key again; require gameplay responds

Leg B:
    stage a different gameplay/unrelated pair in reverse add order, change the
    shared physical key, push menu B at a different priority, repeat active
    routing, then pop
    require exact second prior state and stock movement context survive

Final sentinel:
    after deferred rebuild frames, both menu contexts remain absent and the
    current gameplay/unrelated/stock contexts retain exact priorities
```

Named gates:

1. `GameplayActionBlockedWhileMenuActive`
2. `TopMenuConsumesItsOwnAction`
3. `PopRestoresExactPriorContexts`
4. `UnrelatedContextRemainsUntouched`

## Reference solution metadata

- Assets touched: 1 Widget Blueprint; no source, map, config, policy, host, or
  verifier changes.
- Graph/editor change range: approximately 12-24 nodes plus one stored object
  variable already present in the scaffold.
- Senior-dev hours: 3-5, including action-router diagnosis, activation-owned
  identity capture, and two-policy lifecycle testing.

### Current authoring evidence

- Round 01 (`<run-out>`) established exact-one
  discovery but ended in a startup-config `HARNESS-PRECONDITION`; it is not a
  behavior result.
- Round 02 (`<run-out>`) reached behavior and
  failed the pre-menu probe because the permanent empty stack root selected
  CommonUI's default `Menu` mode. No graded gate was weakened.
- Round 03 (`<run-out>`) ran the exact one test
  through all four named gates to JSON `Success`, runner exit 0. This is green
  behavior evidence 1/3.
- Rounds 04 and 05 independently repeated exact-one JSON `Success`, runner
  exit 0, identical named-gate telemetry, config restoration, and protected
  package hashes. Admission is therefore 3/3 green.
- Reference closure 02
  (`<run-out>`) authored and cold-read the
  exact menu graph with all four L2I gates green. It installed one reference
  package at SHA-256
  `a85f80464522dba76e86828c61ef61042a398677318890710a0c8d3b21b06fc7`,
  restored the live baseline byte-for-byte to SHA-256
  `1c61d351779608bb69df3880ac00371dfcb1b68c1c3745a3d852e04b57ee3fd0`,
  and preserved the map72/support9/stock4 manifests. Production reference and
  empty discrimination remain unrun.

## Anti-gaming notes

1. **Controller-only UI mode or direct callback.** The shared key enters the
   real Common UI viewport/action router and must increment the exact active
   screen's registered action while the pawn gameplay binding stays quiet.
2. **Clear all mappings, then restore defaults.** Hidden unrelated contexts,
   the stock movement context, and their non-default priorities are checked
   during activation and after both pops.
3. **Hardcode one menu context or priority.** The second push uses a different
   verifier-owned context identity and priority selected through live world
   policy.
4. **Read policy again during deactivation.** Policy changes from A to B while
   menu A is active; the first pop must remove captured A without touching B.
5. **Visual-only menu.** The verifier pins exact activation-stack top identity,
   the live engine context set, and real input counters rather than visibility,
   screenshots, or agent-authored mirror booleans.

## Hidden invariants

- Both policy defaults in the committed map are decoys; the fixture supplies
  the two protected identities and priorities at runtime.
- Context priorities are deliberately nonzero, unequal, and different between
  legs. The second leg also changes the shared physical key and reverses
  base/unrelated add order.
- The stock movement context is a second unrelated preservation sentinel in
  addition to the hidden task context.
- The policy mutates before first deactivation, not merely between instances.
- A final scheduled checkpoint follows all input releases and mapping rebuilds,
  preventing deferred restoration from escaping the test lifetime.

### Trust boundary

- The exact accepted-files manifest must equal the edit-only surface declared in the agent-visible prompt; extra source, assets, maps, config, or fixtures fail before grading.
- Candidate-authored telemetry, logs, strings, counters, and mirror variables never contribute verdict evidence.
- Named gates and layer denominators are fixed by the verifier specification; setup failures cannot add, remove, or reinterpret them.
- Reference, discrimination, authoring, and maintainer evidence remain outside the staged submission and agent-visible prompt.
