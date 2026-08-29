---
id: t2-top-screen-keeps-focus-until-dismissed
substrate: ThirdPerson
set: craftbench-public
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_FocusStack :: AFocusStackFunctionalTest"]
introspect: [t2_top_screen_keeps_focus_until_dismissed.py]
deadline_s: 900
action_budget: 40
---

# t2-top-screen-keeps-focus-until-dismissed

Hardened from startup-eval sources `t1-common-ui-stack-hierarchy` and
`t1-activatable-widget-tree`. The task composes a real activation history,
active-leaf input routing, focus acquisition/restoration, and a live
world-owned focus choice.

## Primary concept

- `common-ui-overview` - Common UI Overview
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-advanced-multiplatform-user-interfaces-with-common-ui-for-unreal-engine)

The load-bearing behavior is that only the top screen participates in input
and focus, while dismissing it restores the still-live screen below.

### Composed concepts

- `common-ui-overview` - Common UI Overview
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-advanced-multiplatform-user-interfaces-with-common-ui-for-unreal-engine)
- `common-ui-quickstart` - Common UI Quickstart
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/common-ui-quickstart-guide-for-unreal-engine)
- `commonui-input-technical-guide` - CommonUI Input Technical Guide
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/commonui-input-technical-guide-for-unreal-engine)
- `creating-ui-with-umg-and-slate` - Creating UI with UMG and Slate
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/creating-user-interfaces-with-umg-and-slate-in-unreal-engine)

### Production-pattern justification

Epic's Common UI documentation presents selective interaction through an
activatable hierarchy and points to Lyra's frontend menu as the advanced public
example. Epic's Input Fundamentals guidance describes desired focus selection
and restoration when an active screen leaves the input path. This task uses
that production menu pattern: a top detail screen owns focus, a buried home
screen cannot reclaim it, and popping restores the prior live screen.

### Concept-interaction notes

The navigation history determines the active leaf. The active leaf chooses a
focus target, the input router applies that choice to local user 0, and a
world-owned policy selects between two valid detail actions each time details
activates. The verifier changes the policy between pushes, so construction-time
caching cannot satisfy both activations.

## Prompt given to the agent

> **Deliverable root:
> `Content/Tasks/t2-top-screen-keeps-focus-until-dismissed/`.**
>
> Complete the supplied editable root, home, and detail screens. Opening the
> root must show the home screen as the only active visible screen and put user
> focus on its primary action. The existing open-details control must place the
> detail screen on top, make it the only active visible screen, and focus the
> action currently chosen by the placed menu-policy object. While details is on
> top, the buried home screen must not be able to reclaim focus. The policy may
> change during play; reopening details must use its current choice rather than
> a value cached when the menu was created. Dismissing details must reveal the
> same home screen and restore focus to its primary action. Closing the root
> must leave every menu action unfocused. Preserve the supplied open, dismiss,
> and close controls so the existing host can drive the sequence. Work only in
> the supplied editable visual assets; do not edit the level, policy, host, or
> tests.

## Workspace state pre-task

**Deliverable root:
`Content/Tasks/t2-top-screen-keeps-focus-until-dismissed/`.** This is the
only agent-writable task surface; all expected submission files stay under
this asset folder.

- `WBP_MenuRoot` supplies callable `OpenDetails`, `DismissTop`, and
  `CloseMenu` entry points with empty bodies.
- `WBP_HomeScreen` supplies a button variable `Button_HomePrimary`, initially
  non-focusable.
- `WBP_DetailScreen` supplies `Button_DetailPrimary` and
  `Button_DetailAlternate`, initially non-focusable.

Read-only world state includes one tagged menu-policy actor whose current
choice can select either detail action, plus a lifecycle host and verifier.
The declared task map is
`Content/Maps/t2-top-screen-keeps-focus-until-dismissed/L_FocusStack.umap`.
The three baseline assets, final fixture, introspection script, and task map
are authored in the live substrate. Promotion tracking and certification
status are recorded below and in `notes.md`.

## Verifier specification

The task uses deterministic L1, L2I, and PIE-native L2. Screenshots and visual
judgment never contribute to PASS.

### L1 - project health

```text
assert: UnrealBuildTool exits 0 for ThirdPersonEditor Win64 Development
assert: UnrealBuildTool exits 0 for ThirdPerson Win64 Development
```

### L2I - saved asset structure

```text
root_and_screens_are_activatable:
    exact three generated classes derive from the activatable-screen base
    and compile up to date
real_stack_declares_home_start:
    root contains exactly one activation stack whose permanent root content
    is the supplied Home class
declared_focus_buttons_are_focusable:
    exact three named button variables exist on their intended screens and
    are focusable
```

### L2 - activation and focus lifecycle

The fixture derives from `ACraftBenchFunctionalTest`, uses engine world-time
checkpoints, never ticks Slate or the world manually, and records ASCII-only
named failures.

```text
Preflight:
    require loaded UI/input modules, initialized Slate, local user 0 and PC0
    prove set/read/clear focus on verifier-owned sentinel widgets
    resolve exactly one policy and lifecycle host by tag
    stage current policy choice A

Activate root:
    require exact Home instance is active stack top and owns user-0 focus
Push details:
    require exact Detail instance is sole active top and action A owns focus
    issue verifier-owned refresh request from buried Home
    require focus remains on Detail action A
Pop, change policy, push again:
    require same Home instance and restored Home focus
    stage current policy choice B and reopen
    require Detail action B owns focus while action A does not
Dismiss and close:
    require same Home restoration, then inactive root, no active child,
    and none of the three menu actions focused at the final sentinel
```

Named gates:

1. `root_and_screens_are_activatable`
2. `real_stack_declares_home_start`
3. `declared_focus_buttons_are_focusable`
4. `root_activation_focuses_home`
5. `push_makes_detail_the_only_active_top`
6. `top_detail_owns_declared_focus`
7. `buried_screen_cannot_reclaim_focus`
8. `world_policy_changes_reactivated_focus`
9. `dismiss_restores_home_focus`
10. `root_deactivation_releases_focus`

## Reference solution metadata

- Assets touched: 3 Widget Blueprint assets; no source, config, map, policy,
  host, or verifier changes.
- Graph/editor change range: approximately 25-55 nodes plus WidgetTree edits.
- Senior-dev hours: 4-6, including activation-stack wiring, focus routing,
  current-policy lookup, compilation, and lifecycle debugging.

### Promotion evidence

- The live substrate contains the three independently read-back baseline
  assets. The task-local `reference/` overlay contains three distinct compiled
  reference assets, while the live assets remain in baseline state.
- The declared map package is authored with the policy, lifecycle host, final
  fixture, and admission fixture. Its OFPA mirror currently contains 69
  external-actor packages and 2 external-object packages.
- The exact admission filter passed three independent rounds, each with one
  executed test, one success, and zero failures.
- Supplemental governed behavior runs observed reference L2 `1/1` PASS and,
  after the fixed introspection lookup, L2I `3/3` PASS. The empty overlay
  produced the named L2 failure
  `GATE[root_and_screens_are_activatable]: ` and L2I `1/3`.
- These are supplemental authoring and discrimination results. The official
  single-run `cb discriminate`/`cb refgate` certificate remains pending, and
  the map plus its 71 OFPA side packages must be Git-tracked before promotion.

## Anti-gaming notes

1. **Visual switcher instead of activation history.** Saved structure and
   exact active-top identity require a real stack with Home as permanent root.
2. **Focus cached during construction.** The verifier changes world policy
   before the second push and requires the alternate action.
3. **Buried screen repeatedly asks for focus.** A verifier-owned refresh
   request from inactive Home must leave exact focus on top Detail.
4. **Destroy and recreate Home on pop.** The fixture pins the original Home
   pointer and requires that same instance after both dismissals.
5. **Close only hides visuals.** The final scheduled sentinel requires root
   deactivation, no active child, and negative focus reads for all actions.

## Hidden invariants

- The committed policy choice is a decoy. The fixture overwrites it before the
  first activation and changes it between pushes.
- Runtime identity uses exact live object pointers and button variables, never
  text, display order, screenshots, or generated booleans.
- The buried request uses the engine's leaf-aware focus refresh route and is
  independently proven on verifier-owned active widgets before grading.
- The final close assertion is the last scheduled checkpoint, so no deferred
  assertion sits beyond the base class success boundary.
