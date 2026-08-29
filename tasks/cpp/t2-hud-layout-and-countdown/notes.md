# t2-hud-layout-and-countdown — build contract + calibration notes

Source row "HUD UI System", out of an earlier internal task list. Text half
authored 2026-07-30 on the wave-1/2 molds, DESCOPED per the wave-3 spike
verdict.

## Provenance and cuts

- **Spacebar button / music slider / pause interaction: CUT** — interactive
  UI input has no verification lane (the input-injection spike is
  staged-never-run; UMG interaction has zero prior art). Recorded, not
  silently dropped.
- **Corner placement (top-right bars, top-left timer, etc.): ADVISORY** —
  layout positions are editor-visual; the deterministic gate covers presence,
  names, kinds, and the start value. `cb review` is the
  inspection surfaces for the look.
- **Countdown DECREASE: ADVISORY-ONLY (the load-bearing descope).** Spike
  fact (2026-07-30, real L2 launch shape): **widget Tick never
  fires under `-nullrhi`** (a NativeTick counter stayed 0 across seconds)
  while **world timers DO run**. A tick-driven countdown is therefore
  invisible headless and a timer-driven one works — gating the decrease
  would grade the agent's choice of mechanism, not the behavior. The fixture
  logs `[t2-hud advisory] countdown ... -> decreasing|static (non-gating)`
  and never gates on it. This rationale is VERIFIER-INTERNAL — the prompt
  keeps the counts-down sentence (the reference honors it via a world timer)
  and never hints at the descope.
- **Game-end at zero: CUT** (the source row itself says "you don't have to have
  any game-ending logic").

## Residual bound (acknowledged, not a gate)

A submission whose HUD shows a STATIC "60" that never counts down PASSES the
graded gates — the decrease is advisory by design (above); likewise a
post-cp0 TEXT rewrite (e.g. the readout stamped to garbage at t=2s) passes,
since only the widget's PRESENCE is re-gated at cp1 and the countdown value
itself stays ungated by design. The advisory log line exposes both to human
review (`static` / `unreadable`), and the discrimination matrix documents
the bound. If a future lane makes widget-mechanism-independent countdown
grading possible, promote the advisory to a gate then.

## Map contract (aids/author_L_HudLayout.py must match)

| element | value | why |
|---|---|---|
| floor | engine cube, scale (20, 20, 1), center (0, 0, -48), top at Z=+2 | somewhere for the default pawn to stand; nothing else needed |
| PlayerStart | (0, 0, 120), yaw 0 | a PlayerController must exist for the viewport (widget owner); `AGameModeBase` spawns its default pawn here |
| fixture | `AHudLayoutFunctionalTest` at (0, 400, 120) | passive observer |
| GameModeOverride | `AHudGameMode` (`/Script/ThirdPerson.HudGameMode`) | the agent's natural wiring point; empty scaffold at HEAD |

## Fixture design (why each number)

- **Schedule {0.7, 4.6} — cp0 BEFORE the first timer fire (adversarial-review
  BLOCKER, fixed 2026-07-30)**: checkpoints and world timers share world
  game-time, so a 1-second countdown timer started at BeginPlay fires at
  ~1.0s; a cp0 any later reads the ALREADY-DECREMENTED value and fails
  exactly the timer-driven implementations the descope protects (the original
  1.5s instant failed the reference itself). 0.7s sits after BeginPlay-time
  creation (spike: `CreateWidget`+`AddToViewport` complete inside the first
  frames, on screen by ~frame 2) and before any 1s timer's first fire. cp1
  at 4.6s carries the persistence gate and gives the advisory re-read a
  ~3.9s window (a 1s-period timer has fired >=3 times).
- **Enumeration**: `UWidgetBlueprintLibrary::GetAllWidgetsOfClass(...,
  TopLevelOnly=false)` then `IsInViewport()` filter — "reached the screen" is
  the graded meaning; created-but-never-added widgets are invisible to it.
- **Recursive name search**: `WidgetTree->ForEachWidget` + recursion into
  nested `UUserWidget`s — composition cannot hide a required name, and the
  first tree carrying all four names is the HUD (multiple qualifying HUDs:
  first wins, no fail — over-delivery is not a cheat shape here).
- **Kind gates**: `UProgressBar` for the bars (the standard fill-bar the
  prompt discloses in UI vocabulary), `UTextBlock` for the readout.
- **Start-value gate**: trimmed text == "60" exactly, disclosed as "the whole
  number 60 (just the number)".
- **Persistence gate at cp1 (adversarial-review MAJOR)**: the SAME widget that
  satisfied cp0 must still be valid and `IsInViewport()` at 4.6s — a HUD that
  appears for one sample and vanishes FAILs via `the HUD disappeared after
  appearing`. Mechanism-free: it never touches the countdown descope. No
  dedicated variant (argued coverage — a remove-after-cp0 delta is a
  one-line cheat with an unambiguous named assert).
- **Advisory verdict set**: `decreasing|static|unreadable` — non-numeric cp1
  text is its own word (`Atoi` on garbage returns 0 and would masquerade as
  decreasing).

## Build.cs note (verifier-module change, maintainer flow)

`UE-projects/ThirdPerson/Source/CraftBenchTests/CraftBenchTests.Build.cs`
gains `"UMG", "Slate", "SlateCore"` in PrivateDependencyModuleNames — the
fixture reads widget trees. Passive readback only; the fixture never creates
widgets. This is the first UMG dependency in either substrate's tests module
(the wave-3 spike ran with a temporary local edit; this one ships).

## Named assertions → discrimination legs

| leg | dies at | credited substring |
|---|---|---|
| empty | cp0 presence gate | `no HUD widget reached the screen at play start` |
| `added-late/` | cp0 presence gate (creation fires at 3s > 0.7s) | `no HUD widget reached the screen at play start` (SHARED with empty — documented; discriminate credits per-leg substring-in-own-log, wave-1 teleport precedent) |
| `wrong-initial-value/` | cp0 start-value gate | `the countdown does not start at 60` |
| `missing-bars/` | cp0 name gate | `missing a widget named` (its widget never builds ManaBar) |

Kind-gate coverage (`is not a fill-bar widget` / `is not a text widget`) is
argued from the named assertions without a dedicated variant — a fourth variant
buys little over the missing-bars leg (honest-coverage
convention).

## Calibration checklist (fill from the first live matrix)

HONESTY NOTE: the fixture's `FinishTest(EFunctionalTestResult::Error,
"HARNESS-PRECONDITION: ...")` paths still GRADE AS AGENT FAIL today —
automation Error lands as state Fail in index.json and `l2_pie.py` counts it;
the prefix is the hook for a future runner-side routing rule.

1. **[RESOLVED 2026-07-30 — archaeology record] Headless WBP-asset
   authoring is a NO-GO on UE 5.8; the reference is native C++ BY DESIGN.**
   Live evidence from the binary-half session: (a)
   `wbp.get_editor_property("widget_tree")` fails ("Failed to find
   property"); (b) the retired-umg route `unreal.find_object(wbp,
   "WidgetTree")` DOES resolve the tree — the READ side works on 5.8,
   re-confirming that task's archaeology; (c) but
   `tree.set_editor_property("root_widget", canvas)` fails the same way —
   `WidgetTree::RootWidget` carries no exposure flags, so the WRITE side has
   no stock-Python route at all. (The Aura MCP `edit_widget` fallback was
   unavailable that session — desktop client unsigned — and is NOT needed:)
   the reference ships `EvalHudWidget.{h,cpp}`, a native `UUserWidget` whose
   `NativeOnInitialized` builds the tree via `WidgetTree->ConstructWidget`
   (spike-proven end-to-end under `-nullrhi`: construct + AddToViewport +
   FindWidget round-trip). `NativeOnInitialized` fires at the end of
   `UUserWidget::Initialize()` — inside `CreateWidget`, where the transient
   WidgetTree for a native widget already exists — so the named tree is
   complete before `AddToViewport` and long before cp0. NO binary asset
   exists anywhere in this task. LOAD-BEARING CLAIM (restated): the fixture
   grades what is ON SCREEN by widget NAME via live enumeration — an
   agent-authored WBP asset and a native widget class grade IDENTICALLY, so
   the prompt offers both shapes explicitly. Record for the playbook:
   headless WBP authoring = NO-GO (read yes via find_object, write no).
2. **BP-authored widget trees resolve via `WidgetTree->FindWidget` /
   `ForEachWidget` on the CONSTRUCTED instance** — spike-proven for a
   native-constructed tree, which is now also the REFERENCE's shape (so the
   reference leg no longer exercises the BP-instance path). For agent
   submissions that ship a WBP asset, the instance's WidgetTree is the same
   runtime object either way — accepted-risk note, not reference-proven;
   first graded WBP submission confirms it.
3. **`GetAllWidgetsOfClass` under `-nullrhi`** — the spike enumerated via
   direct pointer; the library route is the same widget registry, confirm it
   returns the reference HUD at cp0.
4. **cp0=0.7s window** — reference creates in `AHudGameMode::BeginPlay`
   (on-screen by frame ~2) and its 1s countdown timer first fires at ~1.0s:
   confirm the calib line shows `onscreen>=1` AND countdown '60' (not '59')
   at cp0.
5. **The advisory line** — reference (world-timer countdown) must log
   `decreasing` (spike: world timers run headless); a static widget logs
   `static`. Non-gating either way.
6. **added-late timing** — its 3.0s deferred creation must still be off
   screen at cp0=0.7s (deterministic under fixed dt; confirm).

## Landing gate

Do NOT land this task in CATALOG/registry before (1) the `.umap` + these
sources are committed and (2) one full `cb discriminate` run has filled the
calibration record and the MATRIX status. Every leg is code-only now — the
native-widget redesign removed all binary assets except the map.

## Discrimination record

Not yet run — see `discrimination/MATRIX.md` §Status. To be filled from the
first `cb discriminate --wip` after the binary half lands.

## Calibration record — first live validation (2026-07-30)

Binary half + full matrix ran this date (Win11, UE 5.8, substrate=live via
`--wip`): **`cb discriminate` = discriminated: YES** — reference PASS; empty +
EVERY variant FAIL via its named MATRIX substring (`[ok ]` on all legs).
Editor-target builds of the scaffold/fixture C++ were clean; per-leg run dirs
not retained (no `--keep`) — the verdicts answer the checklist's yes/no items.

Wave-3 specifics: FIRST matrix ran 0/1 — the never-compiled reference overlay
C++ died at L1 (`C4458: 'Slot' hides class member`; FAILURE-LOG 2026-07-30).
Fixed (local renamed `PanelSlot` in all four copies), re-run = **5/5**. The
native-widget redesign is thereby live-proven: CreateWidget + AddToViewport +
name-based tree reads graded a real PIE leg under `-nullrhi`, and the
headless-WBP-authoring NO-GO (RootWidget write reflection-denied) is recorded
above as the route rationale. Lesson recorded: overlay-only C++ is the one
wave code the pre-discriminate builds never compile — build the reference
overlay once before the first matrix run.
