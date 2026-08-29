# Discrimination matrix — t2-hud-layout-and-countdown

The self-validation oracle: the reference solution must PASS and every gaming
variant + the empty leg must FAIL **at the predicted gate, via the named
assertion**. A wrong-reason FAIL (compile error, wrong checkpoint, filter-miss/
0-tests, SANDBOX-REJECT exit 4) means the verifier is NOT discriminated — fix
it, or relabel the task for the weaker property it actually tests.

**ASCII rule:** every expected-message substring below is ASCII-only. The UE
log's UTF-8 bytes are read back as cp1252, so an em dash in a fixture message
becomes mojibake and the substring grep misses — a correct FAIL then
misclassifies as wrong-reason (live incident, t2-homing-projectile 2026-07-21).

## Layout (folder-local under `tasks/cpp/t2-hud-layout-and-countdown/`; agent-writable prefixes only — a stray root file → SANDBOX-REJECT exit 4)
- `../reference/Source/ThirdPerson/Tasks/t2-hud-layout-and-countdown/…` —
  the reference: the native `UEvalHudWidget` pair (tree built in
  NativeOnInitialized — no widget asset anywhere; see ../notes.md
  archaeology) + the game-mode wiring.
- `<variant>/Source/ThirdPerson/Tasks/t2-hud-layout-and-countdown/…` — one
  dir per anti-gaming note; each is a COMPLETE submission (the widget pair +
  its delta). `missing-bars/` deltas the WIDGET (no ManaBar built); the other
  two delta the game mode.
- empty leg — run IMPLICITLY by `cb discriminate`.

## Matrix
| Submission | Overall | Fails at | Expected message (substring) | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | PASS | — | all checkpoints green | — |
| empty | FAIL | checkpoint 0 (t=0.7s, presence gate) | `no HUD widget reached the screen at play start` | #1 / FR-017 |
| `added-late/` | FAIL | checkpoint 0 (creation deferred to 3s) | `no HUD widget reached the screen at play start` | #2 late/input-gated creation (SHARED substring with empty — discriminate credits per-leg substring-in-own-log; wave-1 teleport precedent) |
| `wrong-initial-value/` | FAIL | checkpoint 0 (start-value gate) | `the countdown does not start at 60` | #4 wrong starting value |
| `missing-bars/` | FAIL | checkpoint 0 (name gate; its widget never builds ManaBar) | `missing a widget named` | #3 name/kind decoys (name half) |

Coverage note (bounded, argued from the named assertions rather than run as
separate submissions): the KIND gates (`is not a fill-bar widget`,
`is not a text widget`) have no dedicated variant — a fourth WBP authoring
pass buys little over the missing-bars leg; a created-but-never-added widget
dies at the same presence gate as empty (IsInViewport is the graded meaning
of "reached the screen"); and a HUD REMOVED after satisfying cp0 dies at
cp1's persistence gate (`the HUD disappeared after appearing`) — a one-line
cheat with an unambiguous named assert, argued rather than shipped.

Acknowledged residual bounds (NOT gates): a HUD showing a STATIC "60" that
never counts down PASSES, and so does a post-cp0 TEXT rewrite (the readout
stamped to garbage after the first sample) — the decrease and the ongoing
value are deliberately advisory-only (see ../notes.md "Residual bound" + the
descope rationale). The fixture's `[t2-hud advisory]` line exposes both
(`static` / `unreadable`) to human review.

## How to run (deterministic verifier, no agent, no tokens)
```sh
cb discriminate --task cpp/t2-hud-layout-and-countdown          # committed task
cb discriminate --task cpp/t2-hud-layout-and-countdown --wip    # while fixture/map/assets are uncommitted
```
Every leg is code-only (the native-widget redesign removed all binary
assets); only the committed `.umap` gates running the matrix.

## Status
- Authored 2026-07-30 (text half + adversarial-review fixes same day).
- **EXECUTED 2026-07-30**: `cb discriminate --task cpp/t2-hud-layout-and-countdown --wip` =
  **discriminated: YES** — reference PASS; empty, added-late, wrong-initial-value, missing-bars all FAIL (5/5 on the re-run after the C4458 reference fix), each `[ok ]` (credited via its named
  substring). Calibration record in ../notes.md.

# DRAFT append for tasks/cpp/t2-hud-layout-and-countdown/discrimination/MATRIX.md

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span in the "Enforcing gate" column is verbatim-greppable in the
named source file, in one of three kinds: FAIL-MESSAGE spans are contiguous
`FinishTest(EFunctionalTestResult::Failed, ...)` source literals in
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/t2-hud-layout-and-countdown/HudLayoutFunctionalTest.cpp`
(never spanning a printf placeholder; ASCII-only per the cp1252 log read-back rule);
MECHANISM spans (API calls, casts, constants, the row-8 advisory `UE_LOG` format
string) are contiguous code tokens in that same fixture file; backticked file paths
name the source files themselves. The task wires no L2I (`layers: [L1, L2]`, no
`introspect:` key), so the second gate family is L1 (UBT,
`tools/verify-single/layers/l1_build.py`) — its target names are runtime-COMPOSED,
never source literals: line 273 builds the pair as
`(f"{game_module}Editor", game_module)`, so row 1 quotes the source-side fragments
and is marked (composed). The edit-boundary row is enforced pre-grade by
`tools/verify-single/sandbox.py` against
`UE-projects/ThirdPerson/AGENT_WRITABLE.json`.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | submission compiles into the gameplay module (implicit in "a widget class in the gameplay module ... is yours to edit") | fully | L1 build (composed) — UnrealBuildTool must exit 0 for BOTH targets, which `l1_build.py` line 273 composes as `(f"{game_module}Editor", game_module)` at platform `Win64`, configuration `Development`; the substrate manifest pins `"game_module": "ThirdPerson"`, so the pair resolves to ThirdPersonEditor and ThirdPerson (resolved names deliberately unbackticked — they exist verbatim in no source file; task.md's L1 assert line-wraps the first); short-circuits on the first failure (no fixture literal — this is the L1 layer, not L2) | unconditional (first layer; L2 is skipped when it fails) | editor-only `#if WITH_EDITOR` tricks do not help — the Game target must also link; warnings are free unless the module's flags promote them |
| 2 | "a HUD must appear on screen by itself — no key press, no input of any kind" at play start | fully (timing + environment) | presence gate, cp0 at the undisclosed t=0.7s — `no HUD widget reached the screen at play start` (full literal: "Expected the HUD unaided at play start; observed no HUD widget reached the screen at play start.") | unconditional (first graded L2 gate; only the harness-precondition `no UWorld` error path precedes it) | "no input" is enforced by the environment (headless PIE never sends input) plus the early sample, not by an input-hook check; any creation route that lands the widget in the viewport before 0.7s — BeginPlay, a 0.5s delay timer, a controller, the widget's own graph — counts equally as "at play start" |
| 3 | the HUD is built AS a widget (a widget asset OR a native widget class — agent's choice) | fully, structurally | same presence gate — the enumeration is `UWidgetBlueprintLibrary::GetAllWidgetsOfClass` called with `UUserWidget::StaticClass(), /*TopLevelOnly*/ false` and filtered by `IsInViewport()`, so anything that is not a live UUserWidget in the viewport (AHUD canvas drawing, raw Slate SWidget, debug text) fails the row-2 literal `no HUD widget reached the screen at play start` | unconditional | asset vs native class is deliberately indistinguishable (both grade identically); the asset may live at ANY writable content path, not just the conventional `Content/Tasks/t2-hud-layout-and-countdown/` |
| 4 | the HUD contains, findable by exact name, ALL of `HealthBar`, `StaminaBar`, `ManaBar`, `CountdownText` | fully | name gate — `The HUD is missing a widget named '` (recursive tree search per on-screen candidate, nested user widgets included; the FAIL names the closest candidate's first missing name) | row 2 fired (no on-screen widget to search) | the four names must sit inside ONE on-screen widget's (possibly nested) tree — but any number of extra/decoy widgets, wrong-named siblings, or duplicate names elsewhere are free; on duplicate names within a tree the first-encountered widget silently wins |
| 5 | `HealthBar`, `StaminaBar`, `ManaBar` are each "a standard fill-bar (progress bar) widget" | fully | kind gate, per bar — `is not a fill-bar widget.` (full literal: "Expected a fill-bar widget; observed %s is not a fill-bar widget.") — a `Cast<UProgressBar>` on the named widget | rows 2–4 fired | any `UProgressBar` subclass passes; fill percent, bound value, color, size, opacity, and on-screen position are all unchecked — a 0%-filled, transparent, zero-sized bar satisfies the gate |
| 6 | `CountdownText` is "a text readout (a text block)" | fully | kind gate — `CountdownText is not a text widget.` (a `Cast<UTextBlock>`) | rows 2–5 fired | any `UTextBlock` subclass; font, size, visibility, and placement unchecked |
| 7 | `CountdownText` "shows the whole number 60 (just the number) the moment the HUD appears" | fully | start-value gate at cp0 — `the countdown does not start at 60 (reads '` (trimmed text compared against `FString::FromInt(KCountdownStart)`, where `constexpr int32 KCountdownStart = 60`) | rows 2–6 fired | leading/trailing whitespace (the read is `TrimStartAndEnd()`); "the moment the HUD appears" is sampled once at 0.7s, so any value shown before that instant is unobserved as long as the text reads `60` at 0.7s |
| 8 | "then counts down by one each second" | **NOT ASSERTED** | none — the cp1 (t=4.6s) re-read is advisory only: it logs `[t2-hud advisory] countdown cp0='%s' cp1='%s' -> %s (non-gating)` and then `FinishTest(EFunctionalTestResult::Succeeded, TEXT(""))`; no decrease value ever reaches a FAIL | n/a (never a gate) | a HUD whose readout shows a STATIC `60` forever PASSES; so does a post-cp0 rewrite to garbage (`unreadable` in the advisory line) or a countdown at any wrong rate — the decrease is a deliberate descope (task spec "Hidden invariants" + this file's residual-bounds note), but it IS stated as a requirement in the agent-visible prompt |
| 9 | the HUD genuinely "appears on screen" — stays up, not a one-sample flash | fully | persistence gate, cp1 at the undisclosed t=4.6s — `the HUD disappeared after appearing.` (the SAME widget object that satisfied cp0 must still be valid and `IsInViewport()`) | cp0 fired any FAIL (the test already finished), or the `HARNESS-PRECONDITION` no-UWorld error route fired at either checkpoint | removal any time AFTER 4.6s is invisible; note the gate is stricter than the prompt in one direction — swapping the cp0 HUD for a replacement widget between 0.7s and 4.6s FAILs even though a HUD is continuously on screen (weak-pointer identity, not re-enumeration) |
| 10 | "Do not edit the level, any config file, or any test file" | fully, by the sandbox (pre-grade, not a fixture gate) | `sandbox.py` vs `UE-projects/ThirdPerson/AGENT_WRITABLE.json`: `Source/CraftBenchTests/` and `Content/Maps/` are `deny` prefixes → SANDBOX-REJECT exit 4; config files are accepted only via the semantic config lane and this task.md declares no `config_allow`, so any ini diff rejects; the graded substrate is materialized from git HEAD, so on-disk edits to the fixture never reach the grade | unconditional (runs before any layer) | nothing path-wise; edits to `Tasks/t2-hud-layout-and-countdown/HudGameMode.{h,cpp}` and the rest of `Source/ThirdPerson/` are explicitly permitted |

Reading order of the L2 gates is strictly rows 2 → 4 → 5 → 6 → 7 at cp0, then row 9
at cp1 — each `FinishTest` returns immediately, so exactly one FAIL literal can appear
per run and every later gate is skipped once an earlier one fires.
