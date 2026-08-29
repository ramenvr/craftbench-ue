<!-- Generated 2026-06-01 by the pie-gold-set-verification-deep-dive workflow (13 recipes -> 13 adversarial verifications -> synthesis -> 2x critique -> finalize, 29 agents). Supersedes an earlier pre-PIE verification-strategy memo (internal, not part of this release) now that L2 runs in PIE. Grounded in the verification toolbox + anti-circularity. -->

> **Terminology note (2026-06-02):** the `R0/R1/R3` rigor spectrum has been **retired** (canonical definitions now in the root `CONTEXT.md`). In this doc, read **"R0/R1-gate"** as **"gating (deterministic) — discrimination-pending or -passed"**, and **"R2"** as the **advisory (non-gating) judge track**. The per-row gate-vs-advisory split below is unchanged in substance; only the tier labels are superseded by the layer's `gating` bool + the discrimination check (FR-017).

> **Correction (2026-08-16, decision Q1 — supersedes every "no possessed pawn / input test can't start" claim below):** this playbook's input-injection blocker was misdiagnosed. Headless L2 PIE **always has a `ULocalPlayer`** — PIE cannot start without one (`Editor/UnrealEd/Private/PlayLevel.cpp:3110-3119`: `SetupInitialLocalPlayer` failure aborts PIE, returning nullptr), so if any L2 fixture has ever run, a LocalPlayer existed. And `FunctionalTestingManager` does NOT refuse to run without a possessed pawn — every shipped fixture starts on these maps. The REAL gate on injected input is `APawn::PawnClientRestart()` (`Pawn.cpp:496-526`), the only caller of `CreatePlayerInputComponent()` + `SetupPlayerInputComponent()`, gated on `PC->IsLocalController()` — and in 5.8 `IsLocalController()` (`PlayerController.cpp:332-340`) tests `GetNetDriver() == nullptr` **before** the `NM_Standalone` branch, so a bare `SpawnActor<APlayerController>` is never local, the pawn never gets an input component, and injection lands nowhere. Two one-line defeats, both public API: possess the **PIE-supplied** controller (`UGameplayStatics::GetPlayerController(World, 0)`), or call `PC->SetAsLocalPlayerController()` (`PlayerController.h:2279`) before `Possess`. Full recipe: §7. The refuted claims below are corrected in place and dated rather than deleted, so the proven-vs-predicted bookkeeping around them stays legible.

Both confirmed against ground truth: `_DT_LEGS_BY_TASK` is the 1-entry dict at `run_task.py:50`, and `l2_pie.py` returns only `succeeded`/`failed` counts from `index.json` with no cross-process diff. Now the revised playbook.

---

# PIE Verification Playbook

*How CraftBench deterministically verifies the gold set — and any new task — now that map-based `AFunctionalTest` fixtures run in a real PIE world. Synthesized from 12 adversarially-verified per-task recipes (rows 2, 4, 9, 11, 13, 15, 19, 21, 40, 45, 48, 52, 55). Honors the adversarial corrections: claims the verify pass refuted are NOT re-inflated here. Two rounds of adversarial review applied — the second round's residual-gap fixes are folded in and marked where load-bearing.*

---

## Where things sit: foundation vs gold set vs slop

> **Historical section (2026-06-01), kept for the reasoning, not the roster.** The
> gold-set roster document and the `internal-1` / `concept-1` draft-spec trees this
> section counts are internal working material and are **not part of this release** —
> do not go looking for them. The shipped corpus and its live status are
> `tasks/CATALOG.md`. What survives here is the three-way distinction (proven
> primitive vs. target row vs. unsigned sketch) and the ban on certifying a reframed
> task under a source row's title, both of which still bind.

The boundary between "what is done", "what we are actually building toward", and "what merely exists" is easy to blur in the rest of this doc. Three layers, kept strictly distinct:

**(1) PROVEN FOUNDATION — 3 flat proof tasks, DONE.** `t0-sanity-log-on-beginplay`, `gp-spawn-sequence`, and `gp-timer-delayed-destroy` are the *calibration* tasks that achieved full PASS/FAIL discrimination on the real PIE runner. They exist to **prove the base primitives** — nothing more. **They are NOT gold-set rows** and must never be counted as gold-set progress. They are "flat" (each places one or two pre-built tagged actors in a committed map; no substrate authoring, no spike) precisely so that what they certify is the *primitive*, not a task. Everything in §2 marked **PROVEN** traces back to exactly these three runs; everything else in §2 is BUILT-but-unexercised or SPIKE.

| Foundation task | Primitive it proved (§2) | Discrimination shape proved |
|---|---|---|
| `t0-sanity-log-on-beginplay` | **beginplay-log-capture** (single-category GLog `FOutputDevice` installed pre-`BeginPlay`) | exact substring match-count on one category over the run window |
| `gp-spawn-sequence` | **pie-checkpoint-sampling**, count-by-tag leg only | `GetAllActorsWithTag` count `==` expected at fixed world-times |
| `gp-timer-delayed-destroy` | **timer-framerate-legs** (`FTimerManager` self-destruct, 60/20 absolute-threshold legs) | same world-time outcome across two independent `-FPS` PIE processes |

These three are the *whole* proven base: **only count-by-tag, single-category log-count, and timer-self-destruct have run green/red.** Every transform-of-a-moving-actor, overlap, CMC-gravity, anim-state, brush, and headless-widget claim downstream is predicted off this base, not banked (see §1, §4).

**(2) THE GOLD SET — 13 hand-certified rows, the actual target corpus.** `#2, 4, 9, 11, 13, 15, 19, 21, 40, 45, 48, 52, 55` (roster internal, not shipped). This is the **go-to corpus** the whole playbook is written to serve: each row is to be authored by **reusing the foundation primitives + a thin config**, not by writing a new verifier. None are shipped yet (§4: *zero banked*). The intended build order is **cheapest-first**, widening the proven base before betting authoring effort:
   - **Start zero-cost: #40** (`type-gated-tag-attach-matrix`) and **#21** (`per-identity-slot-save-roundtrip-isolation`) — synchronous, controller-free, no Tick, reusing count-by-tag/log-capture-shaped readbacks; both still need their substrate + map authored (nothing on disk yet) and a never-run readback class, so they are low-risk first-runs, not freebies.
   - **Then the keystone: moving-pawn checkpoint-sampling** (roadmap #1/#3a) — the single foundational readback no shipped fixture has ever exercised. It unblocks the gameplay-behavior/GAS/anim/input spine (rows 2, 9, 15, 19, 45, 52). Prove its controller-free half (#3a, row-15-shaped) before the substrate-heavy rows.

**(3) THE ~44 OTHER AUTHORED SPECS — uncertified "slop", not the target.** Everything under `tasks/internal-1/` (21) + `tasks/concept-1/` (21) plus the loose top-level specs is **uncertified**: signed off by no one, superseded by the gold set as ground truth. A handful overlap a gold row (e.g. `internal-1/bt-modular-attachment.md` ↔ #40, `internal-1/gas-ability-launches-pawn-3m.md` ↔ #19), but the gold *row* — reframed and re-filed under its own ID — is the certified artifact; the slop spec is only a starting sketch. **Do not treat slop-count as corpus progress, and do not certify a reframed task under a slop spec's title** (§6 trap 2).

---

## 1. What PIE changed

The L2 migration to a real PIE world (base class overrides `IsEditorOnlyLoadedInPIE()->true`, so `BeginPlay` auto-fires and the engine ticks the fixture every frame) flips the gradability of the *behavioral* gold rows: across the 12 recipes, **6 rows are now genuinely R0/R1-gate-or-mixed and on the low-risk path to gradable-via-PIE** (rows 4, 11, 15, 21, 40, 52*) versus the pre-PIE strategy that found ~1–3 of 13 gradable. The headline reason is that three pre-PIE blockers dissolved at once: (a) `FTimerManager`/`CharacterMovement`/overlap-delegate/anim-eval all tick under the real PIE clock instead of being inert in Editor World; (b) the `Content/Tasks/` write boundary now exists in `AGENT_WRITABLE.json` (2026-06-01), unblocking asset-deliverable tasks that were previously DENY→exit-4; and (c) the L2-introspect layer (`l2_introspect.py` + `introspect/mat_emissive_pulse.py`) gives a shipped, read-only, JSON-verdict channel for static asset/graph structure. **But the adversarial pass refuted several over-claims and they stay refuted here:** only *three* PIE primitives have actually been RUN green/red (pre-`BeginPlay` GLog log-count, count-by-tag, FTimerManager self-destruct). No shipped fixture has ever driven a pawn, sampled a transform-over-time, fired an overlap, read a `MOVE_` mode, sampled velocity, or constructed a widget headless — so rows depending on those (2, 9, 19, 45, 52, 55) are **predicted, not proven**, and several carry honest `gradableNowViaPIE: false`. Two rows do **not** move at all: row 13 (perf) is categorically barred from the gate by FR-020d's allowed-assertion list, and row 48 (project-summary prose) has zero runtime behavior for PIE to observe.

**A blunt correction the second adversarial round forced (load-bearing):** by §4's own definition — "a shipped fixture could run it on the proven primitive path *without a new spike*" — **zero rows are banked.** Every row labeled low-risk (4, 11, 15, 21, 40) still needs a *readback class no shipped fixture has ever exercised*: row 4 a recorded-`FVector`-vs-collision-bounds read, row 11 a `GetBrush().GetResourceObject()` read + headless widget construction, row 15 a Tick-driven transform-Z sample, row 21 a `DoesSaveGameExist`/`LoadGameFromSlot`-in-fixture + disk-path compare, row 40 an *any-category* GLog device + `GetAttachParentActor` loop. These are genuinely lower-risk than the moving-*pawn* spike (they need no possessed controller), but "no moving-pawn spike" is not "no spike." Per that memo’s own standard — no gold-row discrimination property has been *observed*, only predicted — **nothing is banked; the honest status is "low-risk, pending first-run discrimination-pass."** §4 names that column accordingly.

\* Row 52's recipe claims `gradableNowViaPIE: true` but the adversarial pass refuted that to `false` (depends on the unproven pawn-traversal + overlap-delegate legs and a missing PlayerStart). This playbook treats it as a predicted-not-proven R1 candidate.

---

## 2. The PIE primitive menu

The reusable building blocks. **Status is honest per the adversarial pass: "PROVEN" means a shipped fixture has run it green/red; "BUILT-but-unexercised-for-X" and "SPIKE" are called out explicitly.**

| Primitive | What it observes | R0/R1 PASS shape | Built vs needs building | One-line example |
|---|---|---|---|---|
| **beginplay-log-capture** | Substring count on a category/verbosity, captured from before `BeginPlay` via a GLog `FOutputDevice` installed in `FWorldDelegates::OnWorldInitializedActors` | `match_count == expected` over the run window | **PROVEN** (`SanityFunctionalTest`, single-category Display; the device literally has `if (InCategory != Category) return;`). Generalizing to Warning\|Error-any-category needs a *new device* (delete the single-category filter), not a reconfig | Sanity: exactly 1 `BeginPlay` log line on the expected category |
| **pie-checkpoint-sampling** | Actor state at fixed world-times: `SetCheckpointSchedule({t…})` + `OnCheckpoint(idx,t)` clocked off `GetWorld()->GetTimeSeconds()` under `-deterministic -FPS=<rate>` | sampled value at checkpoint `t` `==`/`<=`/in-band the expected | **PROVEN for count-by-tag** (`SpawnSequence`). **Transform/velocity/Z sampling of a moving actor is BUILT-but-never-exercised** — a spike for rows 2/9/15/19/45/52 | SpawnSequence: marker count at t=1.0s `== 2` |
| **timer-framerate-legs** | Same fixture at two `-FPS` rates (60/20) in two independent PIE processes; each leg self-asserts absolute thresholds (NO cross-process numeric diff in the runner — `run_l2` returns only `{succeeded, failed}` counts from `index.json`) | each leg independently green against its own absolute thresholds | **PROVEN** (`gp-timer-delayed-destroy`). Mechanism is a **hardcoded per-task dict** `_DT_LEGS_BY_TASK` at `run_task.py:50` — a new task id requires a runner-code edit | Timer: self-destruct fires at the same world-time at 60Hz and 20Hz |
| **pie-state-probe** (in-fixture) | Engine-owned runtime state read **in-fixture, in C++, after tag-resolve** (NOT the Aura RC tool of a similar name): `GetActorLocation`/`GetVelocity`, `GetCharacterMovement()->MovementMode`, `GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight()`, ASC tag/active-ability state | state `==`/within-tol the expected | **PROVEN for count/transform-at-rest**; **moving-pawn/CMC/GAS/anim-state reads are SPIKES** (CMC gravity on a Character, `GetCurrentStateName`, brush `GetResourceObject` under `-nullrhi` all unconfirmed) | GAS: `apex_z - start_z >= 300cm` at an interior sample |
| **editor-python-introspection** (L2-introspect) | Static asset/graph structure: Blueprint/AnimBP graph, Material params/HLSL, `WidgetTree`, DataTables, gameplay tags — via `unreal.load_asset` + reflection, headless `-ExecutePythonScript` | introspect JSON verdict block parses; every check `true` (set/tuple equality) | **PROVEN, SHIPPED** (`l2_introspect.py` + `mat_emissive_pulse.py`). **READ-ONLY contract** (`INTROSPECT_CONTRACT.md:47`) — must not mutate asset/level/project | AnimBP: `state_machine_count>=1 AND distinct_states>=2 AND transition rule references the member var` |
| **log-assertion** | On-disk `Saved/Logs/*.log` substring/sequence assertions (vs the in-PIE GLog device) | expected line(s) present / absent | **The in-PIE GLog device is PROVEN; the on-disk `Saved/Logs/` variant is NOT — no fixture parses `Saved/Logs/` today.** It is mechanically straightforward but unexercised; do not over-credit it as "adjacent to proven" | Modular-attach: zero Warning\|Error lines across 6 rejections |
| **spatial-instance-readback** | Per-instance world transforms off `UInstancedStaticMeshComponent::GetInstanceTransform`/`GetInstanceCount`; or a recorded `FVector` + static collision bounds | count in band; all-inside-footprint; Z-on-surface within tol | **SPIKE** — never run. For PCG (row 55), the recipe's "force-generate is synchronous" claim was **REFUTED**: `UPCGComponent::Generate` is frame-ticked/time-sliced, so a single `-ExecutePythonScript` invocation reads N==0 | HitResult: `\|ReportedPoint.X - WallFaceX\| <= 2.0` AND `> 10.0` off the swept-center |
| **input injection** | A pawn driven by `AddMovementInput` / a scripted-input timeline / injected key events | observable motion/state change caused by injected input | **NOT BUILT — and the old blocker here was misdiagnosed (corrected 2026-08-16; see the correction note + §7)**: the missing piece is not a PlayerStart/LocalPlayer (PIE always supplies both), it is that a fixture-spawned controller is never local (`IsLocalController()` tests `GetNetDriver()==nullptr` before `NM_Standalone`), so `SetupPlayerInputComponent` never runs. Defeat: possess the PIE-supplied controller (`UGameplayStatics::GetPlayerController(World,0)`) or `SetAsLocalPlayerController()` before `Possess`. The **scripted-input timeline** (row 9) remains the honest option for motion-outcome tasks that don't grade a binding | Crouch: substrate base calls `StartCrouch@0.2s`/`ReleaseCrouch@0.45s` from `BeginPlay` |
| **profiler (CSV)** | Wall-clock game-thread frame time via stock `CsvProfile start/stop` → on-disk `Saved/Profiling/*.csv` | *(none that gates)* | **NOT BUILT and CANNOT GATE** — a wall-clock ms threshold is not one of FR-020d's five allowed assertions, is non-deterministic under fixed-step, and is non-portable across machines (refuted in row 13). **R2-advisory evidence only** | Perf: p99 game-thread ms as *advisory* grounding, never PASS/FAIL |

---

## 3. Per-archetype recipe

| Archetype | Canonical PIE recipe | Primitive(s) | Rigor tier |
|---|---|---|---|
| **Gameplay-behavior** (spawn timing, self-destruct, lerp/easing, traversal gates) | Place tagged actor(s); checkpoint-sample transform/count vs a pinned `f(t)`; assert endpoints + monotonicity + (where relevant) easing-window shape; add a 60/20 leg for framerate-independence. **The easing-window is a *behavioral proxy*, not a math ease-detector** (a piecewise-linear curve passes — acceptable per Hard Rule #2). **Anti-gaming caveat for any single-sample readback** (e.g. a recorded contact point read off one fixed obstacle): a single fixed reference lets a *hardcoded literal* or a *wrong-field-plus-reconstruct* both PASS — see row 4 below; harden with a 2nd obstacle or per-run-randomized geometry before claiming concept-discrimination | checkpoint-sampling, state-probe, framerate-legs | **R1-gate** (+ R2 for design/visual). Rows 15, 4 proven-pattern; 52 predicted |
| **GAS / abilities** | Substrate pre-enables GAS plugin (maintainer flow, `.uproject` is DENY). Agent grants an ability bound to a **verifier-published gameplay tag**; fixture activates via `TryActivateAbilitiesByTag`; checkpoint-sample the resulting Z-parabola/effect + assert ASC tag clears. **Gate certifies the observable arc + self-end, NOT "used CMC gravity"** | checkpoint-sampling, state-probe, framerate-legs | **R0/R1-gate** for the observable; CMC-gravity-on-a-Character is a **spike**. Row 19 |
| **AnimBP / animation** | Two legs, both must be green: LEG A static `AnimBlueprintGeneratedClass` introspection (state-machine count, ≥2 states, var-bound transition); LEG B PIE checkpoint-sample the *evaluated* current-state name + the AnimInstance speed var. **Both legs must require the state-name read.** **Contingent-blocker (load-bearing):** the current-state-name read (`GetCurrentStateName`) is itself a SPIKE. If that spike fails, this archetype has **NO non-gameable gate** — LEG A structure-only is weakly gameable, and the var-tracking fallback de-concepts to "a float tracks velocity." The recipe's var-tracking secondary exists *because* the state-read is unproven; do not present the state-name read as available. This prescription may be unsatisfiable until the spike lands (roadmap #5) | editor-python-introspection, checkpoint-sampling, state-probe | **R1-gate** (+ R2 for idiom/visual). Row 2 — `gradableNowViaPIE:false`: anim content substrate absent, state-read API a spike, blend-duration timing hazard |
| **Materials** | L2-introspect only: `MaterialEditingLibrary` param introspection + HLSL regex on the agent's asset under `Content/Tasks/<id>/` | editor-python-introspection | **R0/R1-gate** (structural stage). Visual/functional stages deferred to v1.x |
| **UMG / widgets** | Tagged host actor `CreateWidget`s + `Populate(row)` in `BeginPlay`; checkpoint-read `UImage->GetBrush().GetResourceObject()` (UObject-ref, survives `-nullrhi`) + `TextBlock->GetText()`; introspect `WidgetTree` to guard delete-the-widget gaming. **Any agent-writable cached-UObject UPROPERTY fallback (lives under `Source/CraftBenchTemplate/`, agent-writable) MUST NEVER be the sole gate** — keep the live brush read alongside it (§6 caution b) | checkpoint-sampling, state-probe, editor-python-introspection | **R1-gate** (+ R2 for diagnosis/idiom/visual). Row 11 — low-risk spikes: headless widget construction + brush readback |
| **PCG / procedural** | Introspect-load `UPCGGraph` + `Generate(force=true)`, read ISM per-instance transforms; assert count-band + footprint + on-surface. **REFUTED as drop-in**: generation is time-sliced/frame-budgeted → needs a tick-pump (new capability), violates introspect's read-only contract, and count-band alone doesn't pin "PCG was used" (require ISM ownership by `UPCGManagedISMComponent`) | spatial-instance-readback, editor-python-introspection | **R1-with-reframe but BLOCKED** on a generation-completion pump. Row 55 — `false` |
| **Input** | Key-level injection (`APlayerController::InputKey` with `FInputKeyEventArgs::CreateSimulated`) through the **PIE-supplied** controller — corrected 2026-08-16: the possessed pawn IS available once the fixture possesses `GetPlayerController(World,0)` (or `SetAsLocalPlayerController()`s its own before `Possess`); see §7 for the full recipe and why key-level subsumes action-level. The **verifier-owned scripted-input timeline in the substrate base** stays the right tool where the task grades a motion outcome, not a binding — a timeline can never grade a mapping | (key injection or scripted timeline) + checkpoint-sampling | **R1-gate** if scripted; live injection is a **new capability** (mechanism corrected, still unbuilt). Rows 9, 45 |
| **Performance** | **There is NO v1.0-compliant gate for this archetype.** The behavior-preservation leg (checkpoint-sample `f(t)` vs pinned, defeats disable-the-cost) is R1 and *necessary but not sufficient* — it certifies *nothing about the perf concept* alone. The perf leg **cannot gate** (FR-020d's five-assertion list + non-determinism under fixed-step + non-portability). Profiler CSV is R2-advisory evidence only. **Net: row 13 does not ship as a gate under v1.0** | checkpoint-sampling (behavior-preservation, non-gating-alone); profiler (advisory) | **R2-advisory-only**; no admissible perf assertion exists. Row 13 |
| **Multiplayer** | **Reframe to single-PIE-world**: isolation is keyed on an identity *string*, not a network connection. Save-roundtrip + per-slot-isolation needs no `NumPlayers>1`. Seed two identities in one world, save, wipe in-memory, re-derive from disk via stock `UGameplayStatics::DoesSaveGameExist`/`LoadGameFromSlot` | checkpoint-sampling, state-probe, log-assertion | **R1-gate** (+ R2 for true-networked-correctness). Row 21 — `true` |
| **Advisory / design** | No PIE. Gather deterministic ground truth (introspection/AST) and hand it + the agent's prose to an **R2 evidence-grounded judge** (advisory, never gates, judge model ≠ agent model). Or reframe to a structured-manifest tool-authoring task (set-equality diff, R0/R1, no PIE) — but that is a **different, re-filed task** | editor-python-introspection (for the reframe) | **R2-advisory-only**. Row 48 — canonical negative-exemplar, no shift |

---

## 4. Updated gold-set rigor matrix

Honors the adversarial corrections. The status column is renamed **"Low-risk, pending first-run"** — per §1, *zero* rows are banked: by the definition "a shipped fixture could run it on the proven primitive path without a new readback class," all five low-risk rows still need a never-run readback class, so the honest standard is "no moving-pawn spike, first-run discrimination-pass not yet observed." Where the recipe claimed `true` but the verify pass refuted it, the refuted value is shown with the reason.

| Row | Concrete (reframed) task | Rigor tier | Low-risk, pending first-run? | Gating new capability |
|---|---|---|---|---|
| **2** | `anim-locomotion-speed-gated-state` | R1-gate + R2-advisory | **No (blocked)** | Anim content substrate (skeleton/mesh/idle-walk clips — *none on disk*); AnimBP introspect script; pawn-speed-drive fixture; anim-state-read API (spike). **Contingent-blocker:** if the state-name-read spike fails, the task has no non-gameable gate (see §3 AnimBP) |
| **4** | `surface-contact-point-passed-to-interface` | **R0/R1-gate** | **Yes (low-risk, pending first-run)** | Sweep substrate (IHitConsumer + reporter + recording receiver); `L_HitSweep.umap`; never-run recorded-`FVector`-vs-bounds readback. **Gaming gap (load-bearing, carry into the cell):** *as-specified with one fixed wall*, both `OnHitReported(FVector(KnownWallX,0,0))` (hardcoded literal) and `Hit.Location + FVector(R,0,0)` (wrong field + reconstruct) PASS — so it discriminates correct-vs-empty but **NOT correct-vs-wrong-field**, which is the entire ImpactPoint-vs-Location concept. **MUST add a 2nd wall or per-run-randomized X before claiming concept-discrimination** |
| **9** | `crouch-transition-interrupt-continuity` | R1-gate + R2-advisory | **No (blocked)** | ACharacter crouch substrate + `L_CrouchInterrupt` + fixture. **Discrimination is weak**: a single fixed release time can't separate "reacts to release" from "plays a scripted bump" — needs ≥2 release-time legs that track the trigger; frame-order hazard at the 0.45 release frame |
| **11** | `widget-image-brush-binds-from-row` | R1-gate + R2-advisory | **Yes (low-risk, pending first-run)** | UMG/Slate Build.cs deps; pre-bugged widget + 2 textures + `L_CardSlot`; never-run spikes: headless widget construction + `GetResourceObject` brush readback (both plausible under `-nullrhi`). Re-add a null→Collapsed slot. **Cached-UObject fallback must never be the sole gate** (§6 b) |
| **13** | `gp-optimize-hot-tick` | **R2-advisory-only — ships with NO v1.0 gate** | **No (no admissible gate exists)** | **Categorically blocked**: wall-clock perf threshold violates FR-020d's five-assertion list + non-deterministic under fixed-step + non-portable. The behavior-preservation leg is necessary-but-not-sufficient and certifies nothing about the concept, so **the task does not ship as a gate under v1.0** |
| **15** | `eased-lerp-reaches-end-pose` | R1-gate + R2-advisory | **Yes (low-risk, pending first-run; closest to shippable)** | `L_EasedLerp` + fixture; the never-run Tick-driven transform-Z sample. Calibrate easing thresholds *with* the ~0.05s world-start offset. Reference solution should be Tick-driven, not `UTimelineComponent` (component-tick unproven). 60/20 leg is independent absolute-threshold, not cross-process diff (`run_l2` has no diff) |
| **19** | `gas-vertical-launch-apex-300cm` | R0/R1-gate (observable) | **No (blocked)** | GAS plugin enable (`.uproject`, maintainer-only); GAS substrate; **CMC-gravity-on-a-Character in headless PIE is a spike** (no Character has ever ticked in any fixture); apex-undershoot tolerance must clear at the worst framerate |
| **21** | `per-identity-slot-save-roundtrip-isolation` | R1-gate + R2-advisory | **Yes (low-risk, pending first-run + discrimination-pass — nothing on disk: no `L_InvSave`)** | Save substrate + `L_InvSave` + fixture; never-run `DoesSaveGameExist`/`LoadGameFromSlot`-in-fixture + disk-path compare. Per-run Saved/ isolation is **already free** (runner copies to tempdir). Drop the `.sav` size-compare; keep path-distinctness + content-isolation |
| **40** | `type-gated-tag-attach-matrix` | R1-gate + R2-advisory | **Yes (low-risk, pending first-run + discrimination-pass — nothing on disk: no `L_ModularAttach`/`AModularAttachFunctionalTest`)** | Attach substrate + `L_ModularAttach` + fixture; a *new* any-category Warning\|Error GLog device (not a reconfig — Sanity's device has `if (InCategory != Category) return;`); never-run `GetAttachParentActor` loop |
| **45** | `zero-angular-velocity-on-flying-entry-only` | R1-gate + R2-advisory | **No (blocked)** | Spin-pawn substrate + fixture; **broken leg schedule**: A-before-B means a correct solution has already zeroed spin before the isolation leg → mis-FAILs the reference; needs reset/reorder/2-pawns; yaw delta-angle normalization; `_DT_LEGS_BY_TASK` runner edit |
| **48** | (reframe) `structured project-introspection manifest` | **R2-advisory-only** (faithful row); R0/R1 (reframe, no PIE) | **No** (faithful) | None for the faithful row (pure judge). Reframe needs a manifest set-diff comparator + a C++ ground-truth source scanner (does NOT exist; not foldable into l2_introspect — confirmed no clang-AST/UHT code in `tools/verify-single/`) |
| **52** | `player-traversal-gate-sequence` | R1-gate + R2-advisory | **No (recipe said yes — refuted)** | **PlayerStart/GameMode** (committed maps have none — corrected 2026-08-16: functional tests DO start regardless, PIE supplies the LocalPlayer + controller; a PlayerStart buys spawn *placement*, not startability — §7); possessed-pawn traversal + overlap-delegate firing are **unproven legs**; kill-Z respawn timing is fragile against the checkpoint schedule |
| **55** | `pcg-scatter-instances-on-floor-at-density` | R1-gate + R2-advisory | **No (blocked)** | PCG plugin enable + L1-build-with-PCG (unproven); `Content/Tasks/` asset-submission end-to-end (never run); **PCG generation-completion pump** (generate is time-sliced, not synchronous); count-band doesn't pin "PCG was used" (require `UPCGManagedISMComponent` ownership) |

**Tally (corrected, second round):**
- **Banked (shipped fixture runs it on a proven primitive with no new readback class): 0.** This is the honest count — per that earlier strategy memo, no gold-row discrimination property has been *observed*, only predicted.
- **Low-risk, pending first-run (no moving-pawn spike, but each needs ≥1 never-run readback class + an unrun discrimination-pass): 5** (4, 11, 15, 21, 40). Of these, 21 and 40 additionally have *nothing on disk yet*; 15 is closest to shippable.
- **R2-advisory-only, no shift, no v1.0 gate: 2** (13, 48).
- **Blocked on substrate-authoring + ≥1 spike (incl. the moving-pawn spike): 6** (2, 9, 19, 45, 52, 55).

---

## 5. Capability roadmap

Re-ordered by **leverage-per-effort** after the second adversarial round, which surfaced two cheap hard-unblockers under-ranked behind the expensive moving-pawn spike. Cheap, hard, broadly-unblocking items now lead; the moving-pawn spike is split into its controller-free (provable now) and input-driven (gated on #2) halves. (Full ordered list in `capabilityRoadmap`.)

1. **`_DT_LEGS_BY_TASK` generalization (cheapest, highest leverage-per-effort — do first).** Today a 1-entry hardcoded dict at `run_task.py:50` (`{gp-timer-delayed-destroy: (60,20)}`); every new framerate-independence task needs a runner edit. This **silently blocks the framerate-independence leg the whole gameplay-behavior/GAS spine leans on** (rows 15, 19, 45, 52) — the primary anti-overfit defense. A ~5-line change to a per-task spec field. **Effectively free; promote to first.**

2. **PlayerStart + GameMode in committed maps (cheap — corrected 2026-08-16: NOT a startup-blocker).** The claim that stood here ("`FunctionalTestingManager` refuses to run until a possessed pawn exists, so no input test can even start") is **false** — every shipped fixture starts on these maps, because PIE always supplies a LocalPlayer + player controller (see the correction note + §7). What a PlayerStart/GameMode buys is spawn *placement* and a sensible default pawn, not startability; the input door itself is the PIE-supplied controller (possess it, or `SetAsLocalPlayerController()` a fixture-spawned one before `Possess`). Still cheap and still worth doing for rows 52 and the live-input variants of 2/9/45, and still useful staging for #3b.

3. **Moving-actor transform/velocity checkpoint readback — split into two halves:**
   - **3a. Self-propelled (controller-free, provable NOW).** Sample `GetActorLocation().Z`/`GetVelocity()`/`MovementMode` of a *Tick-driven* mover (like row 15's reference) — needs **no** controller, so it is provable before #2. This is the single foundational readback class almost every behavioral low-risk row (4, 11, 15, 21, 40) and the gameplay-behavior/GAS archetypes depend on. **No shipped fixture has ever done this; prove it first among the readback spikes.**
   - **3b. Input-driven pawn.** Drive a *possessed* pawn via injected/scripted input and read the same state. (Corrected 2026-08-16: previously "gated on #2" — but possession does not wait on a PlayerStart; the fixture possesses the PIE-supplied controller, §7. A CMC pawn still needs possession to consume `AddMovementInput`.) Unblocks 52 and live-input variants of 2/9/45.

4. **CMC-gravity-on-a-Character + ballistic integration under headless `-nullrhi` PIE (spike).** Distinct from #3: confirm a Character actually *falls* under gravity (no Character has ever ticked in any fixture). Unblocks GAS row 19 and any jump/fall/launch task.

5. **GAS plugin enable (maintainer `.uproject` flow) + GameplayAbilities/Tags/Tasks Build.cs deps.** `.uproject` is DENY so the maintainer must pre-enable; the agent edits Build.cs. Unblocks the entire GAS/abilities archetype (row 19 +).

6. **Anim content substrate + AnimBP-graph introspect script + anim-state-read API (`GetCurrentStateName` spike).** Currently *zero* skeleton/mesh/clip/AnimBP on disk. **Note the contingent-blocker:** if the `GetCurrentStateName` spike fails, the AnimBP archetype has no non-gameable gate (§3) — so this item carries gate-existence risk, not just authoring effort. Unblocks rows 2, 9 (AnimBP variant) and the AnimBP archetype.

7. **UMG/Slate Build.cs deps + headless `UUserWidget` construction + brush-`GetResourceObject` readback under `-nullrhi` (low-risk spikes).** Unblocks row 11 and the UMG/widgets archetype.

8. **`Content/Tasks/` asset-submission end-to-end shakeout.** The writable carve-out exists but no `.uasset`-deliverable task has been run through sandbox+overlay. Unblocks materials (already partly), AnimBP (row 2), PCG (row 55), widgets (row 11).

9. **PCG plugin enable + L1-build-with-PCG + a generation-completion tick-pump.** REFUTES the "synchronous generate" assumption — generation is frame-budgeted, so a tick-loop that drains the `FPCGTaskId` is required, plus a way to do this outside the read-only introspect contract. Unblocks row 55 and the PCG archetype.

10. **R2 evidence-grounded advisory-judge harness** (gather deterministic evidence → score against a rubric → never gates; judge model ≠ agent model). Unblocks the *advisory residue* of every row (design quality, visual fidelity, diagnosis prose) and the advisory/design archetype (row 48). **Never a gate.**

**Explicitly NOT on the roadmap (refuted):** an L4 wall-clock perf gate (row 13 — incompatible with FR-020d + non-deterministic + non-portable; row 13 ships with no gate at all); a C++ AST source scanner folded into l2_introspect (row 48 — does not exist, is a genuinely new primitive, no clang-AST/UHT in `tools/verify-single/`); multiplayer `NumPlayers>1` PIE (row 21 — the deterministic core never needed it).

---

## 6. Anti-circularity + the R0/R1-vs-R2 boundary

**The anti-circularity rule (load-bearing, clean across all 12 recipes — second adversarial round found no leak):** Grade by **re-deriving** state through stock-UE primitives CraftBench controls end-to-end — `GetAllActorsWithTag` (identity by **tag, never class**, so the agent may subclass), `GetActorLocation`/`GetVelocity`/`MovementMode`, `GetBrush().GetResourceObject()`, `DoesSaveGameExist`/`LoadGameFromSlot`, ISM `GetInstanceTransform`, a verifier-installed GLog `FOutputDevice`, and `unreal.load_asset` reflection in a hash-pinned read-only introspect script. **Never put the agent's own tools in a gate** — no `review_blueprint`, `query_unreal_project_assets`, `get_player_transform`, `get_actor_by_name_in_pie`, `analyze_profiler_capture`, or any Aura/MCP surface. The verifier launches its *own* headless PIE/editor session and reads the engine's own state. Where a recipe exercises the agent's API under test (row 21's `LoadFor`, row 40's `TryAttachModule`), the result is **cross-checked against an independently re-derived stock-UE fact** (the stock-loaded disk contents; the engine attachment hierarchy), so a lying agent surface is caught by the disagreement. Two adversarial cautions, propagated into the archetype cells (§3) so an implementer reading only the archetype table still sees them: **(a)** name primitives precisely — "pie-state-probe" must mean *in-fixture C++ tag-resolve + transform-sample*, not the Aura RC tool of a similar name; **(b)** any agent-writable fallback (row 11's cached-UObject UPROPERTY lives under `Source/CraftBenchTemplate/`) must **never be the sole gate** — keep the real-state read live alongside it.

**The R0/R1 (gate) vs R2 (advisory) boundary, per FR-020d's five allowed assertions** (build-tool exit code, `AFunctionalTest` outcome, Python introspection equality, hash equality, AST predicate):

- **R0/R1 gates** the *observable behavioral/structural fact*: a transform hits `f(t)`, a state name flips, a brush ResourceObject matches, two save slots are distinct files with isolated contents, 9/9 attach pairs satisfy `ok==expected` with zero stray logs. Binary, numeric, threshold-bearing, reproducible across same-machine reruns (else **INDETERMINATE**, never a silent PASS/FAIL — per `spec.md:194-195`).
- **R2-advisory picks up the genuine residue and NEVER flips PASS/FAIL**: "is this idiomatic/well-architected" (AnimBP state factoring, GAS hand-rolled-vs-`LaunchCharacter`, modular-vs-if/else), **visual fidelity** (does the walk cycle / scatter / image *look* right — screenshot-only, no comparator, `-nullrhi` uploads no pixels), **diagnosis/explanation prose** ("why ImpactPoint not Location", "why the interrupted transition skips your rules", the project-summary), and **perf "is it faster"** (wall-clock, refuted from the gate; row 13 has no gate). The R2 evaluator gathers deterministic evidence and judges against a rubric; **its model must differ from the agent-under-test's model.**

**The two boundary traps the adversarial pass surfaced, stated as rules:** (1) **A gate must discriminate the *concept*, not a sanitized proxy.** Row 4's single-fixed-wall (passes both a hardcoded literal *and* `Location + R` — discriminates correct-vs-empty but not correct-vs-wrong-field), row 9's smooth-arc-through-6-points, row 55's count-band, row 13's behavior-preservation-alone, and the row-2 var-tracking fallback each pass solutions that never implement the named concept — fix by requiring the *causal* observable (a 2nd wall / per-run-randomized X for row 4; ≥2 release-time legs that track the trigger for row 9; ISM ownership by `UPCGManagedISMComponent` for row 55; the actual current-state-name read for row 2 — itself a spike, so the row-2 gate may not exist until that spike lands). (2) **Don't certify under the gold-row title.** Every reframed task ("speed-gated idle↔move", "surface-contact-point", "eased-lerp", "type-gated tag attach") is a **named, narrower derivative** — ship it labeled for what it *actually* tests, record the distortion, and keep the dropped open-ended intent in the R2-advisory track. PIE widened the deterministic gate; it did not abolish the residue, and the residue stays advisory.

---

## 7. Input injection under headless PIE (added 2026-08-16 — the corrected model)

Corrects this playbook's own §2/§3/§5 premise (marked in place above) and the
an earlier input-injection spike verdict. Everything below is read off pinned
UE 5.8 source, not inferred; decision provenance:
the 2026-08-16 decision review, Q1.

### 7.1 What is already true in every headless L2 run

- **A `ULocalPlayer` exists, always.** PIE calls `ViewportClient->SetupInitialLocalPlayer`
  and **aborts, returning nullptr, if it fails** (`Editor/UnrealEd/Private/PlayLevel.cpp:3110-3119`).
  If any L2 fixture has ever run, a LocalPlayer existed — "headless L2 lacks a `ULocalPlayer`"
  was never true.
- **A PIE-supplied `APlayerController` exists with it** — `UGameplayStatics::GetPlayerController(World, 0)`
  resolves it (`LevelActor.cpp:1099` logs `got player` at creation).
- **A `UEnhancedPlayerInput` on the controller is free**: `PlayerController.cpp:5636-5641`
  lazily inits it and explicitly accepts `Player == nullptr`. The possessed pawn's input
  component is pushed into the controller's input stack for free too (`:2673`).

### 7.2 The real gate: `APawn::PawnClientRestart()`

`Pawn.cpp:496-526` is the ONLY caller of `CreatePlayerInputComponent()` +
`SetupPlayerInputComponent()`, and it is gated on `PC->IsLocalController()`. In 5.8,
`IsLocalController()` (`PlayerController.cpp:332-340`) tests `GetNetDriver() == nullptr`
**before** the `NM_Standalone` branch and returns **false** when there is no `ULocalPlayer` —
so a bare `SpawnActor<APlayerController>` never becomes local, the pawn never gets an input
component, and injection lands nowhere. Two one-line defeats, both public API:

1. possess the **PIE-supplied** controller: `UGameplayStatics::GetPlayerController(World, 0)`;
2. or call `PC->SetAsLocalPlayerController()` (`PlayerController.h:2279`) **before** `Possess`.

### 7.3 Key-level subsumes action-level — ONE go/no-go, no flip-to-B fallback

Key-level (`APlayerController::InputKey`, simulated key events) and action-level
(`InjectInputForAction`) both need, in order: (1) a `UEnhancedPlayerInput` on the controller
(free, §7.1); (2) a `UEnhancedInputComponent` on the possessed pawn with `BindAction`
registered — i.e. `PawnClientRestart` ran (§7.2); (3) that component in the controller's
input stack (free). Key-level additionally needs (4) a populated key→action table. If
(1)–(3) fail, action-level fails identically. The only world where action-level works and
key-level does not is when (4) alone is broken — the mapping context was never applied —
which is exactly the case where action-level measures *less than the task asks*, because it
bypasses the mapping being graded. **If key-level is dead, action-level is dead; the honest
third option is the scripted `AddMovementInput` timeline already shipping in five fixtures**
(`TeleportPortalFunctionalTest.cpp:194`, `LadderClimbFunctionalTest.cpp:246`,
`NpcFollowFunctionalTest.cpp:144`, `SprintStaminaFunctionalTest.cpp:167`,
`GravityFloatingPawnFunctionalTest.cpp:174`) — which can grade motion outcomes and can never
grade a binding.

**Epic's own precedent** that none of this needs a heavyweight bootstrap:
`Engine/Plugins/EnhancedInput/Source/InputEditor/Private/Tests/InputTestFramework.h:66`
mocks the subsystems "to avoid having to create an actual subsystem + local player + game
instance", then drives `InputKey(FInputKeyEventArgs::CreateSimulated(...))` and asserts the
full Started/Ongoing/Triggered/Completed chain fires.

### 7.4 The recipe

1. `PC = UGameplayStatics::GetPlayerController(World, 0)` — never spawn a controller when
   the PIE one will do; a fixture that must spawn its own calls `SetAsLocalPlayerController()`
   before `Possess`.
2. `PC->Possess(GradedPawn)` — or read the pawn the GameMode already possessed.
3. **Assert the input component landed** before injecting: `Pawn->InputComponent` non-null
   AND `Cast<UEnhancedInputComponent>(Pawn->InputComponent)->GetActionEventBindings().Num() > 0`.
   Zero bindings = `SetupPlayerInputComponent` never ran — this is the assertion that tells a
   HARNESS fault (the §7.2 gate) apart from an AGENT fault; without it, an `IsLocalController`
   bail reads as "injection is a headless no-op" and records a false NO-GO.
4. (key-level only) After `AddMappingContext(IMC, 0, {.bForceImmediately = true})`, assert
   `QueryKeysMappedToAction(IA).Num() > 0` — the mapping table is live.
5. Inject via `PC->InputKey(FInputKeyEventArgs::CreateSimulated(...))` — always
   `CreateSimulated`, never the deprecated `FInputKeyParams` path. **Corrected 2026-08-16
   against UE 5.8 source on disk:** `FInputKeyParams::NumSamples` defaults to **0**
   (`PlayerInput.h:389`), and the `bTreatAsAnalog` guard
   (`PlayerInput.cpp:299-301`) already excludes `MouseX`/`MouseY` when `NumSamples == 0` —
   so the `ensure` INSIDE that branch is unreachable for this case and the axis degrades
   **silently to a digital button press**, which is worse than an ensure and is the real
   reason to avoid the path. `CreateSimulated` is safe because its
   `InNumSamplesOverride == -1` resolves to `IsAnalog() ? 1 : 0`
   (`InputKeyEventArgs.cpp:50-53`), i.e. 1 sample for an analog key. Keyboard verbs are
   digital and unaffected either way.

### 7.5 Three token-free proofs to run BEFORE any paid spike

1. *Is the LocalPlayer already there?* Grade any committed pawn reference with
   `--keep-workdir` and grep the kept `out/l2_pie.log` for
   `Enhanced Input local player subsystem has initialized` and for `got player`
   (`LevelActor.cpp:1099`).
2. *Did the pawn get an input component?* The step-3 assertion above, logged before injecting.
3. *Is the mapping table live?* The step-4 `QueryKeysMappedToAction` assertion.

---

## Capability roadmap (structured)

1. 1. Moving-pawn transform/velocity/MovementMode checkpoint readback under PIE (the foundational spike — no shipped fixture has ever sampled a moving actor's transform; unblocks rows 2,9,15,19,45,52 and the gameplay-behavior/GAS/anim/input archetypes)
2. 2. PlayerStart + GameMode in committed maps (or a controller-providing fixture path) so possessed-pawn traversal/input works — corrected 2026-08-16: the "FunctionalTestingManager refuses to run without a possessed pawn" claim is FALSE (PIE always supplies a LocalPlayer + controller; the gate is IsLocalController on the possessing controller, see section 7); a PlayerStart buys spawn placement, not startability; unblocks rows 52 and live-input variants of 2/9/45
3. 3. CMC-gravity-on-a-Character + ballistic integration under headless -nullrhi PIE (spike, distinct from #1 — confirm a Character actually falls under gravity; unblocks GAS row 19 and any jump/fall/launch task)
4. 4. GAS plugin enable via maintainer .uproject flow + GameplayAbilities/GameplayTags/GameplayTasks Build.cs deps (.uproject is DENY so agent cannot self-enable; unblocks the GAS/abilities archetype, row 19)
5. 5. Anim content substrate (known skeleton + committed idle/walk AnimSequences + tag-resolvable AnimInstance-bindable character) + AnimBP-graph introspect script + anim-state-read API spike (GetCurrentStateName) — zero skeleton/mesh/clip/AnimBP on disk today; unblocks rows 2,9 and the AnimBP archetype
6. 6. _DT_LEGS_BY_TASK generalization to a per-task spec field (today a hardcoded dict requiring a runner edit per task; unblocks framerate-independence legs for rows 15,19,45,52)
7. 7. UMG/Slate Build.cs deps + headless UUserWidget construction + UImage brush GetResourceObject readback under -nullrhi (low-risk spikes; unblocks row 11 and the UMG/widgets archetype)
8. 8. Content/Tasks/ asset-submission end-to-end shakeout through sandbox+overlay (carve-out exists but no .uasset-deliverable task has run; unblocks materials, AnimBP row 2, PCG row 55, widgets row 11)
9. 9. PCG plugin enable + L1-build-with-PCG + a generation-completion tick-pump (REFUTES the synchronous-generate assumption: UPCGComponent::Generate is frame-budgeted/time-sliced; needs a tick-loop draining the FPCGTaskId plus a way outside the read-only introspect contract; unblocks row 55 and the PCG archetype)
10. 10. R2 evidence-grounded advisory-judge harness (gather deterministic evidence, score against a rubric, never gates, judge model != agent model; unblocks the advisory residue of every row — design quality, visual fidelity, diagnosis prose — and the advisory/design archetype, row 48)

## Decisions for maintainer (structured)

- PERF (row 13) is categorically out of the gate, not just unbuilt: a wall-clock game-thread-ms threshold is none of FR-020d's five allowed assertions, is non-deterministic under fixed-step PIE, and is non-portable across machines (FR-001/FR-023). DECIDE: ship row 13 as R2-advisory-only (CSV profiler as advisory evidence + behavior-preservation as the only R1 leg, which certifies nothing about 'is it faster'), OR amend FR-020d to admit a relative baseline-differential assertion (a spec change, not a layer build). Do not present row 13 as an R0/R1 gate.
- The 'gradable-NOW' set is 5 rows (4,11,15,21,40) but only the THREE base primitives (BeginPlay-log-count, count-by-tag, FTimerManager self-destruct) have actually run green/red. Every transform-of-a-moving-actor, overlap-delegate, CMC-gravity, anim-state, brush-readback, and headless-widget claim is PREDICTED. DECIDE the sequencing: run the foundational moving-pawn transform spike (roadmap #1) and a discrimination-pass on rows 40 + 21 on the REAL runner BEFORE authoring the substrate-heavy rows (2,9,19,45,52,55), so the proven-primitive base is widened before betting authoring effort on it.
- Several recipes pass solutions that never implement the named concept (row 9 smooth-arc-through-6-points; row 55 count-band gameable by a hand-rolled scatter loop; row 4 'Location+R' / hardcoded-literal bypass; row 2 var-tracking fallback; row 52 default-pawn-slides-through). DECIDE per task whether to (a) add the causal observable (>=2 release-time legs that track the trigger; UPCGManagedISMComponent ownership; per-run-randomized geometry; require the actual current-state-name read) or (b) accept the proxy and relabel the task honestly for the weaker property. Do NOT ship these as concept-gating without the causal leg.
- Row 45's leg schedule is BROKEN as written: leg A (zero-spin-on-Flying) permanently zeros the spin before leg B (the non-Flying isolation leg) runs, so a CORRECT solution mis-FAILs the isolation precondition. DECIDE the fix before authoring: reorder B-before-A, reset/re-impart spin between legs, or use two separate pawns/runs. As specified the central discriminator fails the reference.
- Row 52 ships no PlayerStart/GameMode (documented per-map in `docs/MAPS.md`) and depends on possessed-pawn traversal + overlap-delegate firing that have never run under PIE. The recipe's gradableNowViaPIE:true is refuted to false. DECIDE: either invest in roadmap #1+#2 first, or descope row 52 to a no-pawn synchronous-overlap variant (like row 40's call-loop) that needs no controller.
- Reframed tasks must be relabeled and re-filed under new IDs, never certified under the gold-row title (rows 2,4,9,13,15,19,21,40,45,48,52,55 are all narrower derivatives). DECIDE the certification-record convention so the dropped open-ended intent (design quality, prose, true-networked correctness, aesthetic) is explicitly parked in the R2-advisory track and the distortion is recorded — per the gold-set-verification-strategy section-6 certification rule.
- Row 48 reframe needs a C++ ground-truth source scanner that DOES NOT EXIST and cannot be folded into l2_introspect (which walks assets via editor-Python, not C++ source). DECIDE whether the structured-manifest reframe is worth building a genuinely new primitive, or whether row 48 stays the canonical advisory negative-exemplar with no reframe.
