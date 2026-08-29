---
id: t3-each-local-player-owns-its-top-modal
substrate: ThirdPerson
set: craftbench-public
rhi: real
tier: T3
capability_bucket: Gameplay Programming
category: other
layers: [L1, L2, L2I]
fixtures: ["L_LocalPlayerModalIsolation :: ALocalPlayerModalIsolationFunctionalTest"]
introspect: [t3_each_local_player_top_modal.py]
deadline_s: 1800
action_budget: 55
accepted_files: [Content/Tasks/t3-each-local-player-owns-its-top-modal/WBP_LocalPlayerModalRoot.uasset, Content/Tasks/t3-each-local-player-owns-its-top-modal/WBP_LocalPlayerModalScreen.uasset]
---

# t3-each-local-player-owns-its-top-modal

> **AUTHORED / PRODUCTION DISCRIMINATION PASS / PUBLICATION READY.** The exact two-asset editable
> surface, retained production map, fixed three-check L2I, and reference are
> authored. A fresh real-RHI production reference passed L1/L2/L2I, while an
> independent no-behavior baseline passed L1 and failed the intended player-
> owned-router gate. Official git/refgate promotion remains separate.

Give each of two local players an independent top modal

## Primary concept

- `common-ui-overview` - Common UI Overview
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-advanced-multiplatform-user-interfaces-with-common-ui-for-unreal-engine)

### Composed concepts

- `commonui-input-technical-guide` - CommonUI Input Technical Guide
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/commonui-input-technical-guide-for-unreal-engine)
- `commonui-with-enhanced-input` - Using CommonUI With Enhanced Input
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/using-commonui-with-enhnaced-input-in-unreal-engine)
- `player-controllers` - Player Controllers
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/player-controllers-in-unreal-engine)

### Production-pattern justification

Epic describes CommonUI as the UI framework originally developed for Fortnite,
with an activatable input tree and one action router per local player. Local
multiplayer screens add the second production constraint: each couch player has
an independent controller/Slate user and player-screen layer. The task composes
those public patterns instead of reducing modal ownership to a single global
viewport widget.

### Concept-interaction notes

Two visible local players share one physical action key while their independent
modal stacks have different depths. The verifier routes the same key through
one local input device at a time, then observes that player's engine action
router, stack top, input context, and Slate focus while treating the other
player's complete state as a negative control.

## Prompt given to the agent

> Finish the supplied two-player modal interface. Each local player must own an
> independent screen stack. Only the top modal for the player who pressed the
> shared dismiss action may close. Closing it must restore that same player's
> exact prior screen and focus target without changing the other player's
> stack, action context, or focus.
>
> The level changes which player acts first, the shared action key, each stack's
> modal depth, and the prior focus target while it runs. Both local players must
> remain present and playable. Do not solve this with a player-zero shortcut,
> one global stack or focus variable, mirrored dismiss calls, or by disabling
> the second player's input. Work only in the exact two supplied assets
> `Content/Tasks/t3-each-local-player-owns-its-top-modal/WBP_LocalPlayerModalRoot.uasset`
> and
> `Content/Tasks/t3-each-local-player-owns-its-top-modal/WBP_LocalPlayerModalScreen.uasset`;
> they are the complete writable submission surface. Do not add or edit source,
> maps, config, tests, plugins, or any other asset.

## Workspace state pre-task

- The exact editable surface is
  `WBP_LocalPlayerModalRoot.uasset` and
  `WBP_LocalPlayerModalScreen.uasset` under
  `Content/Tasks/t3-each-local-player-owns-its-top-modal/`. No other file is
  part of the submission.
- The protected map is
  `Content/Maps/t3-each-local-player-owns-its-top-modal/L_LocalPlayerModalIsolation`.
  It starts the stock playable ThirdPerson mode, contains one
  production fixture, and create exactly two local players. It will not provide
  an editable native answer scaffold.
- The task-local config overlay selects `CommonGameViewportClient` and enables
  CommonUI Enhanced Input before editor startup; the overlay is verifier-owned
  and must restore byte-identically.

## Verifier specification

The following is the frozen production contract, certified first by the
verifier-owned admission fixture and then by the production reference/empty
matrix.

L1 builds both `ThirdPerson Win64 Development` and `ThirdPersonEditor Win64
Development`.

L2 will run one `ALocalPlayerModalIsolationFunctionalTest` in a fresh real-RHI,
off-screen, fixed-60-Hz PIE world. The fixture must establish exact two
`ULocalPlayer` identities with distinct controllers, platform users, input
devices, Slate users, and `UCommonUIActionRouterBase` subsystem instances. It
then runs two policy epochs. Epochs swap first owner, common key (`E`/`Q`),
modal depths (`2/1` then `1/2`), and preferred primary/alternate focus targets.

For each owner action, the fixture records both players' exact active widget,
stack cardinality, active mapping-context pointer/priority, router leaf/input
mode, low-level Slate focused widget, and UMG user focus. It injects a simulated
key event carrying only the selected player's real mapped `FInputDeviceId` via
`UCommonGameViewportClient::InputKey`. One checkpoint later the owning top must
have handled exactly once and popped to its exact prior instance. Every recorded
fact for the other player must be unchanged. No world, widget, router, or player
is manually ticked.

Fixed proposed L2 denominator: exactly four named gates.

1. `EachPlayerOwnsIndependentActionRouter`
2. `TopModalConsumesOnlyOwningPlayersAction`
3. `DismissRestoresOnlyThatPlayersFocus`
4. `OtherPlayersStackNeverChanges`

L2I has a fixed denominator of three checks: exact two player-owned stack roots,
exact owning-player modal push/dismiss graph and focus-return path, and exact
task asset inventory with no global viewport/root substitute. The installed
script is `tools/verify-single/introspect/t3_each_local_player_top_modal.py`.

## Reference solution metadata

- Native LOC in the submission: 0.
- Assets edited: exactly the two named task assets.
- Reference: `reference/Content/Tasks/t3-each-local-player-owns-its-top-modal/`
  with exactly those two assets.
- Senior developer estimate: 10-16 hours including local-player ownership,
  action routing, focus restoration, and two-player live verification.

## Anti-gaming notes

1. Always resolving player 0 fails the reversed owner order and distinct router
   identity sentinel.
2. One global stack fails the other-player active pointer/cardinality negative
   control after the first dismiss.
3. A global focus variable or `SetKeyboardFocus` shortcut fails two distinct
   Slate user indices plus exact per-controller `HasUserFocus` evidence.
4. Broadcasting dismiss to both modal roots increments or pops the negative
   control and fails `OtherPlayersStackNeverChanges`.
5. Separate stacks with one shared action context fail the cross-player mapping
   context matrix and device-targeted action count.
6. Only changing a diagnostic owner index cannot change the engine router leaf,
   stack top, context, and Slate focus together.
7. Removing or disabling player two fails exact-two controller/device/router
   cardinality before any graded action.

## Hidden invariants

- The two policy epochs swap owner order, key, stack depth, modal order, and
  focus target in the same world.
- The input event's device-to-platform-user mapping, not a test callback, picks
  the router.
- Other-player stack pointer/count, context pointer/priority, router leaf/mode,
  focus widget, and action count are all captured before each action.
- Real off-screen Slate and world time are load-bearing. NullRHI and manual tick
  are outside this task's admission contract.

### Trust boundary

- The exact accepted-files manifest must equal the edit-only surface declared in the agent-visible prompt; extra source, assets, maps, config, or fixtures fail before grading.
- Candidate-authored telemetry, logs, strings, counters, and mirror variables never contribute verdict evidence.
- Named gates and layer denominators are fixed by the verifier specification; setup failures cannot add, remove, or reinterpret them.
- Reference, discrimination, authoring, and maintainer evidence remain outside the staged submission and agent-visible prompt.
