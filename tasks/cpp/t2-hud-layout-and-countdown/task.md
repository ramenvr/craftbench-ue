---
id: t2-hud-layout-and-countdown
substrate: ThirdPerson
set: cpp
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_HudLayout :: AHudLayoutFunctionalTest"]
---

# t2-hud-layout-and-countdown

A HUD that reaches the screen on its own: at play start — with no input — a
widget carrying three named status bars and a named countdown readout showing
60 must be live in the viewport. Sourced from an earlier internal task list (not shipped) ("HUD UI
System"). Deliberately
DESCOPED from the source row: the spacebar button, the music slider, and the
pause interaction are cut (interactive UI input has no verification lane),
the corner-placement clauses are advisory
(editor-visual, not gated), and the countdown's per-second decrease is
observed and logged but NOT graded — the graded contract ends at the starting
value (rationale recorded in the task notes, not here). The widget asset
itself is the agent's to author; the level's game mode scaffold is the
natural (but not required) wiring point.

## Primary concept

- `umg-widget-basics` — UMG widget creation and viewport wiring
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/creating-widgets-in-unreal-engine)

The load-bearing behavior is authoring a widget asset with a named tree and
getting it onto the screen at play start unaided — the create-widget /
add-to-viewport lifecycle plus tree structure, graded live rather than as a
file on disk.

## Prompt given to the agent

> When play begins in this level, a HUD must appear on screen by itself — no
> key press, no input of any kind. The HUD must contain, findable by these
> exact widget names:
>
> - `HealthBar`, `StaminaBar`, `ManaBar` — three status bars, each a standard
>   fill-bar (progress bar) widget;
> - `CountdownText` — a text readout (a text block) that shows the whole number 60
>   (just the number) the moment the HUD appears, then counts down by one each second.
>
> Build the HUD as a widget — a widget asset in the project's content OR a
> widget class in the gameplay module, your choice — and wire it so it
> reaches the screen at play start. The level's game mode source
> (`Tasks/t2-hud-layout-and-countdown/HudGameMode.{h,cpp}`) is yours to edit
> if you want a code-side hookup; the widget's own graph is equally fine. Do
> not edit the level, any config file, or any test file.

## Workspace state pre-task

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t2-hud-layout-and-countdown/HudGameMode.h` / `.cpp` — declares and
  defines `class THIRDPERSON_API AHudGameMode : public AGameModeBase`, EMPTY.
  The task map's world settings select it, so PIE runs it at play start;
  whether the HUD wiring lives here, on a controller, or in the widget's own
  graph is the implementer's choice.
- `Content/Maps/t2-hud-layout-and-countdown/L_HudLayout.umap` — a flat floor,
  a PlayerStart, and one placed `AHudLayoutFunctionalTest`. World settings
  select `AHudGameMode`.

**This map deliberately has no drivable pawn**, and that is a design decision
rather than an oversight. `AHudGameMode`'s empty constructor names neither a
`PlayerControllerClass` nor a `DefaultPawnClass`, so — because naming a task game
mode REPLACES `GlobalDefaultGameMode` — the player spawns as an `ADefaultPawn`
under a bare `APlayerController` with no input mapping context applied. Three
reasons that is correct here, where on four sibling ThirdPerson maps the same
shape was a defect fixed on 2026-08-17 (`f52e0ea`):

1. **The prompt forbids input outright** — "no key press, no input of any kind".
   A drivable character would be scenery for a requirement that excludes it.
2. **No gate depends on a pawn.** `AHudLayoutFunctionalTest` resolves its subject
   with `UWidgetBlueprintLibrary::GetAllWidgetsOfClass` and never touches a
   controller, pawn or local player, so there is no dead input path hiding behind
   a green gate — the grader is indifferent by construction, not by oversight.
3. **This file is the agent's to edit** (see the bullet above), so seeding a
   controller into it would change the scaffold a submission starts from, and any
   agent that rewrote the constructor would silently remove it.

A reviewer pressing Play still sees the HUD, which is the whole deliverable; the
view is a free-flying pawn rather than the third-person character. Recorded here
because `cb lint`'s `game-mode-no-player-controller` rule asks for exactly this
statement rather than letting the omission pass unexamined.

Files that **do not exist**:

- No widget asset for THIS task, and nothing that puts any widget on this
  map's screen (the stock template's `Variant_*` content ships UI widgets
  under its own trees, but none reach the viewport in this map). The HUD
  widget is authored from scratch by the agent, in EITHER shape: a widget
  asset (any writable content path works; `Content/Tasks/
  t2-hud-layout-and-countdown/` is the convention) or a native widget class
  in the gameplay module. The verifier grades what is on screen by widget
  NAME - both shapes grade identically.
- No widget creation or `AddToViewport` call anywhere. The empty submission
  compiles (L1 green) and fails L2 at the named no-HUD gate.
- No test source in the agent's writable path. `AHudLayoutFunctionalTest`
  lives in a separate `CraftBenchTests` module the agent cannot read or
  modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t2-hud-layout-and-countdown/L_HudLayout.umap` on the
**ThirdPerson** substrate. The engine ticks the world at a fixed deterministic
step (`-deterministic -FPS=60`). The map's world settings select
`AHudGameMode`.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

```text
AHudLayoutFunctionalTest (derives ACraftBenchFunctionalTest):
    PrepareTest():
        SetCheckpointSchedule({0.7, 4.6})
    OnCheckpoint(0)  t=0.7:
        enumerate live UUserWidgets; filter IsInViewport()
        assert at least one on screen
        ("... no HUD widget reached the screen at play start.")
        find the first on-screen widget whose tree (searched recursively,
        including nested user widgets) contains ALL of HealthBar, StaminaBar,
        ManaBar, CountdownText
        ("The HUD is missing a widget named '<first-missing>' ...")
        assert each bar is a UProgressBar ("... <name> is not a fill-bar
        widget."), CountdownText a UTextBlock ("... not a text widget.")
        assert trimmed text of CountdownText == "60"
        ("... the countdown does not start at 60 (reads '<observed>').")
    OnCheckpoint(1)  t=4.6:
        persistence gate (GRADED, mechanism-free): the SAME widget that
        satisfied cp0 must still be valid and in the viewport
        ("... the HUD disappeared after appearing.")
        then ADVISORY ONLY (never gates): re-read CountdownText; log
        "[t2-hud advisory] countdown cp0='60' cp1='<now>' ->
        decreasing|static|unreadable (non-gating)" -> Succeeded
    every checkpoint logs an ASCII "[t2-hud calib]" line.
```

**Pass criteria**: both L1 targets and L2 green. **Robust identity**: the HUD
is found by what is ON SCREEN, not by asset path or class — the agent may
name and place the widget asset anywhere writable; nesting the named widgets
inside child user widgets is fine (the search recurses).

## Reference solution metadata

- LOC range: 90-120 C++ — a native UUserWidget subclass whose
  NativeOnInitialized builds the tree programmatically (canvas root, three
  progress bars, one text block) + game mode BeginPlay (CreateWidget +
  AddToViewport + a 1s looping world timer stepping the readout). No asset:
  headless WBP authoring has no stock route on 5.8 (notes archaeology), and
  the fixture grades both shapes identically.
- Files touched: 4 (the two pre-existing scaffold files + a new widget
  class pair).
- Senior-dev hours: 0.5.

## Anti-gaming notes

1. **Empty/partial submission.** *Failure mode*: the scaffold compiles with no
   widget and no wiring; L1 passes. *Defense*: the fixture enumerates the LIVE
   widgets actually on screen (`IsInViewport`) at an undisclosed early instant
   and FAILs via the named message `no HUD widget reached the screen at play
   start` — a widget asset that exists on disk but never reaches the viewport
   fails the same gate.
2. **Late or input-gated creation.** *Failure mode*: the HUD appears lazily
   seconds in, or only after an input event (which headless PIE never sends).
   *Defense*: the presence gate samples early (an undisclosed instant under a second);
   anything not on screen by then fails gate #1's named message.
3. **Name-only decoys.** *Failure mode*: four widgets carry the right names
   but the wrong kinds (e.g. four text blocks — no bars at all). *Defense*:
   per-name kind gates — each bar must be a real fill-bar widget (`X is not a
   fill-bar widget`), the countdown a real text widget (`CountdownText is not
   a text widget`). Names alone never pass.
4. **Wrong starting value.** *Failure mode*: the countdown text exists but
   reads something other than 60 (empty, "60s", a designer placeholder).
   *Defense*: the trimmed text must be exactly the whole number 60 at the
   presence gate — else the named FAIL `the countdown does not start at 60`.
5. **Test disabling / environment repointing.** *Failure mode*: agent edits
   the fixture, the map, or config to weaken the gate. *Defense*:
   `Source/CraftBenchTests/` is sandbox-denied (submission files under it are
   rejected pre-grade), the runner materializes the graded substrate from git
   HEAD, and `Config/` + `Content/Maps/` are deny-listed.

## Hidden invariants

- The presence-gate instant (0.7s: after BeginPlay creation, before any
  1-second timer's first fire) is not disclosed; "at play start, by
  itself" is the prompt's contract and anything input-gated or lazy misses it.
- The 4.6s re-visit is not disclosed either: the HUD must still be on
  screen there (graded persistence), and the countdown is re-read as an
  advisory (non-gating) line; from the prompt's view the countdown clause
  is simply part of the task.
- The named-widget search recurses into nested user widgets — composition is
  legal and cannot hide a required name; equally, a name present only in a
  NON-viewport widget (created, never added) does not count.
