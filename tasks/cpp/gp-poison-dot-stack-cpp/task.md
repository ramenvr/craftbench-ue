---
id: gp-poison-dot-stack-cpp
substrate: ThirdPerson
set: cpp
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_PoisonStack :: APoisonStackFunctionalTest"]
---

# gp-poison-dot-stack-cpp

Port of the **g2-9 "Health/Poison"** eval prompt, running on the UE 5.8
**ThirdPerson** substrate (originally ported onto the UE 5.7
CraftBenchTemplate substrate; migrated 2026-08-06 — see the substrate epoch
note below). Probes a stacking, periodic damage-over-time effect through the
Gameplay Ability System — restructured 2026-08-05 into **two stages the agent
builds in order**: **stage 1 builds the health system** (the pawn exposes a
drainable Health resource, initialized to 100, readable+writable through GAS);
**stage 2 builds the poison DoT** that drains it (~1/sec for ~5s, stacking up
to a cap, re-application refreshing the duration).

> **⚠ REDEFINITION EPOCH 2026-08-05 (health-first two-stage restructure).**
> Before this date the substrate scaffold pre-built the health system
> (`ACraftBenchCharacter` constructed the attribute set) and the task was
> stage 2 only; the checkpoint-0 baseline gate was an anti-broken-submission
> defense. From this date stage 1 is the agent's work: the provided task base
> pawn ships an ability system and **no** health resource, and the same
> checkpoint-0 gate is **the stage-1 verifier** (plus a derivation gate, an
> init-to-100 read, and a ≠100 write probe). **Results recorded before and
> after this date are not comparable** — same convention as
> `gp-glide-stamina-cpp`'s 2026-08-04 redefinition (run under its pre-rename
> id `gp-glide-stamina`).

> **⚠ REDEFINITION EPOCH 2026-08-06 (Legs C/D — refresh + cap become gates;
> owner decision 2026-08-06).** The prompt has always demanded a stack **cap**
> ("a fourth application must not exceed three stacks") and duration
> **refresh** ("~5 seconds from the most recent application"), but until this
> date neither contributed a single bit to the verdict (the tracked 2026-08-03
> correction). From this date the fixture runs a 16-checkpoint schedule with a
> **Leg C refresh gate** (mid-window re-apply → the drain must continue past
> the original expiry AND still stop by the refreshed one) and a **Leg D cap
> gate** (the 4-application/single-stack rate ratio gains an upper bound).
> The Leg A stop check was simultaneously recalibrated onto a deliberate ~5s
> acceptance band (a conforming ~6s duration no longer mis-fails). **Gates
> were added, so the task got strictly harder: results recorded before and
> after this date are not comparable** — same convention as the health-first
> note above.

> **⚠ SUBSTRATE EPOCH 2026-08-06 evening (ThirdPerson migration; owner
> decision 2026-08-06, completing the uniform substrate policy).** This task
> now runs on the `UE-projects/ThirdPerson/` substrate — the stock UE 5.8
> Third Person C++ template — joining its Blueprint twin
> `gp-poison-dot-stack-bp` (migrated 2026-08-05). C++ and BP are equal-status
> deliverables, so the pair grades on the same substrate, map, and fixture:
> the `APoisonStackFunctionalTest` fixture
> (`Source/CraftBenchTests/Tasks/gp-poison-dot-stack-bp/`, shared by both
> tasks), the `L_PoisonStack` map, the task base pawn
> (`ACraftBenchBareCharacter`), and the GAS scaffold were all ported verbatim
> by the twin's migration; this migration re-homed only the spec and the
> reference/discrimination overlays (`Source/CraftBenchTemplate/` →
> `Source/ThirdPerson/`, byte-identical files — no gate changed). **Results
> recorded before and after this flip are not comparable** (substrate change
> — same convention as the two epochs above). One deliberate delta the flip
> brings: **ThirdPerson config-disables Live Coding**
> (`Config/DefaultEditorPerProjectUserSettings.ini`), so the in-editor
> self-build lane CraftBenchTemplate still exposes does not exist here — the
> evening this decision landed, an editor-driven C++ bench on
> CraftBenchTemplate lost both sonnet-5 reps to EDITOR-GONE mid-drive, both
> after `trigger_live_coding`/`recompile_unreal_project` use. An agent-side
> compile was always verdict-irrelevant by design; the verifier's post-drive
> L1 is the only compile that scores.

> **⚠ RENAME + VISIBILITY EPOCH 2026-08-06 (owner decision 2026-08-06).**
> Two changes landed together. (1) **Rename**: this task's id changed
> `gp-poison-dot-stack` → **`gp-poison-dot-stack-cpp`**, so all four
> glide/poison tasks are surface-differentiated by suffix (`-cpp` C++
> original, `-bp` Blueprint variant; the set stays `bp-g2` — set =
> source-sheet provenance). The rename also dissolves the documented
> prefix-shape id violation (`gp-poison-dot-stack` was a raw substring of
> `gp-poison-dot-stack-bp`, blinding the CATALOG substring membership check —
> see the repo conventions). (2) **Visible character became a gate**: the prompt now
> requires the character to be visibly represented, and the shared fixture
> enforces it structurally — at checkpoint 0, after the stage-1 gates, the
> graded pawn must carry a skeletal/static mesh component with a mesh
> actually assigned, else the named FAIL "the character is not visibly
> represented: no mesh component with an assigned mesh on the graded pawn".
> **CORRECTED 2026-08-11:** this was written as mirroring the `-bp` variant's
> L2I `pawn_visibly_represented` gate. **That gate does not exist on this
> family** — `tools/verify-single/introspect/gp_poison_dot_stack_bp.py` does not
> define it and does not import the shared `_bp_variant_lib` that does, so
> neither poison lane has ever had an L2I visibility backstop. The fixture gate
> below is the ONLY visibility defense here, on both variants. It exists because this task's film strips showed an empty scene — a
> meshless-but-conforming pawn was ungradable by a human reviewer. **Results
> recorded under the old id, or before the visibility gate, are not
> comparable with results after it.**

> GAS-category note: like `gp-flight-mode` / `gp-glide-stamina-cpp`, this task names
> the GAS contract as part of the interface — a documented exception to
> behavior-only prompts, because verifying the health system and the
> periodic-stacking effect *through GAS* is the point. The named contract,
> extended 2026-08-05 for stage 1: the pawn's ability system must expose a
> **Health** attribute **via the attribute set type the project provides**
> (the verifier reads that type's Health attribute), initialized to **100**;
> the poison ability is tagged `Ability.Poison` and granted on the pawn; the
> drained resource is that same `Health` attribute.

> Tier-B scope note: the original g2-9 also plays a gameplay-cue VFX for the
> poison duration. Headless `-nullrhi` cannot observe VFX, so this port verifies
> the **mechanical DoT + stacking core** — periodic Health loss, stop-after-
> duration, stack-scaling, the stack cap, and duration refresh (ALL gated as of
> 2026-08-06) — and **drops the cue VFX** (see Anti-gaming). Built on
> **vanilla GAS** (no GAS Companion): a periodic, stacking `GameplayEffect`.

## Primary concept

- `gas-attributes` — Gameplay Attributes and Attribute Sets, built by the agent
  (stage 1) and moved by a periodic stacking GameplayEffect (stage 2)
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-attributes-and-attribute-sets-for-the-gameplay-ability-system-in-unreal-engine)

The load-bearing mechanics: **stage 1** — an attribute set registered on the
pawn-owned ASC exposing an initialized, writable Health; **stage 2** — a
**periodic, stacking** GameplayEffect that subtracts Health on a ~1s period
for a ~5s duration (a DoT that *stops*), aggregates up to a stack cap, and
refreshes its duration when re-applied. A missing/inert health system, a
single instant subtraction, a never-ending drain, a non-scaling stack, an
uncapped fourth stack, or a re-application that refreshes nothing all fail by
name (the last two gated 2026-08-06).

## Prompt given to the agent

> The project provides a **task character pawn** that owns an ability system
> but **no health resource yet** (the project also contains a generic
> character with a pre-built attribute set, used by other tasks — your pawn
> must be a subclass of the *task* character, not the generic one).
> Build the feature in two stages, in order:
>
> **Stage 1 — build the health system.** Give your pawn (a subclass of the
> provided task character) a **Health** attribute exposed through its ability
> system, using the attribute set type the project provides. Health must be
> **initialized to 100** and must be readable AND writable through the
> standard attribute APIs (the verifier both reads it and writes it).
>
> **Stage 2 — the poison.** Implement a **poison** ability that, when
> activated, makes the character lose Health **repeatedly — about once per
> second — for roughly five seconds, then stops** (not a single hit, and not a
> drain that never ends).
>
> - Tag the ability `Ability.Poison` and add it to the pawn's granted abilities,
>   so the game can apply poison by that tag.
> - Poison **stacks up to three**: each application adds a stack (up to 3), and
>   more active stacks make Health drain **proportionally faster** (three stacks
>   ≈ three times the per-second loss of one). A fourth application must **not**
>   exceed three stacks.
> - Each new application **refreshes the duration** — the whole poison lasts ~5
>   seconds from the most recent application, not from the first.
> - Deliver your pawn as a subclass of the provided task character (C++ or
>   Blueprint) with your ability granted.
> - The character must be **visibly represented**: assign one of the provided
>   mannequin skeletal meshes (under `/Game/Characters/`) as your character's
>   mesh, so a reviewer watching the run can see it take the poison.
>
> The verifier first checks your health system (stage 1: Health present,
> initialized to 100, and responsive to a write), then applies your ability by
> sending the `Ability.Poison` tag (one or more times) and observes the Health
> attribute over time.

## Workspace state pre-task

Files that **exist** under `Source/ThirdPerson/` (this substrate's
agent-writable runtime module):

- The stock UE 5.8 Third Person C++ template sources (`ThirdPersonCharacter`,
  game mode, the Variant_* trees). No edit needed.
- `ThirdPerson.Build.cs` — already includes `GameplayAbilities`,
  `GameplayTags`, `GameplayTasks`. No edit needed.
- `CraftBenchBareCharacter.{h,cpp}` — **the task base pawn (stage-1 start
  state)**: an abstract `ACraftBenchCharacter` lineage with a pawn-owned ASC,
  the auto-granted `GrantedAbilities` array (ships empty), the `CraftBenchPawn`
  tag, and **no attribute set** (the `"AttributeSet"` default subobject is
  suppressed on this lineage — a C++ subclass building stage 1 must create its
  set under a **different** subobject name; the pawn-owned ASC auto-registers
  owner-outer'd attribute sets at `InitializeComponent`).
- `CraftBenchCharacter.{h,cpp}` — the generic scaffold pawn other tasks use;
  it still pre-builds the attribute set. **Subclassing it does not satisfy
  this task** — the stage-1 derivation gate fails a pawn that is not on the
  task-base lineage, by name.
- `CraftBenchAttributeSet.{h,cpp}` — the contract attribute set type
  (`Health`, `MaxHealth`, `Power`). `Health` is the attribute the verifier
  reads and poison drains. The class exists; **registering (and initializing)
  an instance on your pawn's ability system is stage 1**.
- `CraftBenchGameplayTags.{h,cpp}` — registers `Ability.Poison`
  (`FCraftBenchGameplayTags::AbilityPoison()`).
- The `GameplayAbilities` plugin is enabled.
- `APoisonStackFunctionalTest` lives in the verifier-only `CraftBenchTests`
  module (`Source/CraftBenchTests/Tasks/gp-poison-dot-stack-bp/` — the
  fixture is shared with the Blueprint twin, byte-identical gates. The folder
  KEEPS the twin's `-bp` name after this task's 2026-08-06 `-cpp` rename: it
  is a folder name, not a task id — do not "fix" it to `-cpp`).
- `Content/Characters/Mannequins/` — the substrate's **native**
  visual-representation content (SKM_Manny_Simple / SKM_Quinn_Simple, the
  SK_Mannequin skeleton). Read-only: `Content/Characters/` is outside the
  writable sandbox; the prompt's visible-character bullet points here.

Files the agent **creates**: a pawn subclass of `ACraftBenchBareCharacter`
that builds the health system (stage 1), a `UGameplayAbility` (C++ or
Blueprint) tagged `Ability.Poison` that applies a periodic, stacking,
duration-limited Health drain (stage 2), with the ability in the pawn's
`GrantedAbilities`. The pawn is resolved by derivation and spawned + possessed
by the verifier.

## Verifier specification

The verifier gates stage 1 at checkpoint 0 (BEFORE any trigger), then applies
poison by tag (one or more times) and samples Health on a checkpoint schedule.

**Shipped fixture (the source of truth for gates):** 16-checkpoint schedule
`{0.5, 1.6, 3.1, 4.6, 7.6, 9.7, 10.7, 12.3, 14.3, 17.9, 19.4, 21.4, 23.5,
24.5, 26.1, 28.6}` — Leg A (×1 @ idx 0, stop window idx 4-5), Leg C (refresh:
×1 @ idx 6, RE-APPLY @ idx 8, gates idx 9-12), Leg B/D (×4 @ idx 13, rate
gates @ idx 15). This is the 2026-08-06 Leg C/D redefinition: the descendant
of the 2026-06-19 "CALIBRATE" design that was never shipped, adapted to the
health-first two-stage shape and re-pinned from measured 5.8 runs — it
RESOLVES the 2026-08-03 correction (cap + refresh used to contribute zero
verdict bits; see the `-bp` variant's task.md for the resolved block).

```text
OnCheckpoint idx 0 (0.5s) — THE STAGE-1 GATE (all named FAILs, before any trigger):
    (a) derivation : Pawn IsA ACraftBenchBareCharacter
                     // else "stage 1 not built: ... does not derive from the provided task base pawn"
                     // (empty submission -> generic base pawn; generic-pawn subclass = pre-built dodge)
    (b) presence   : ASC->HasAttributeSetForAttribute(GetHealthAttribute())
                     // else "stage 1 not built: the pawn's health attribute system is absent"
    (c) init       : |GetNumericAttribute(Health) - 100| <= 0.5, read BEFORE any fixture write
                     // else "stage 1 incomplete: Health must initialize to 100"
    (d) writability: SetNumericAttributeBase(Health, 37); |read-back - 37| <= 0.5
                     // 37 != 100 on purpose: an inert-write set that inits at 100 must not pass vacuously
                     // else "stage 1 incomplete: health attribute is inert, write-then-read failed"
    (e) visibility : a skeletal/static mesh component with an assigned mesh exists on the
                     graded pawn (2026-08-06)
                     // else "the character is not visibly represented: no mesh component
                     // with an assigned mesh on the graded pawn"
    then SetNumericAttributeBase(Health, 100); Trigger x1          // Leg A begins
idx 1..3 (1.6/3.1/4.6): each Health step down >= PeriodicMinStep   // periodic, not an instant hit
idx 4..5 (7.6/9.7)    : (AStop - ATail) <= StopEpsilon             // STOPPED inside the ~5s band:
                     // the window opens at trigger+7.1, PAST the acceptance-band top (~7.0s),
                     // so a conforming ~4-7s duration (incl. ~6s) shows zero ticks here
idx 6  (10.7): SetHealth(100); Trigger x1                          // Leg C (refresh) begins
idx 7  (12.3): mid-drain sample (logged)
idx 8  (14.3): RE-APPLY (Trigger x1) at trigger+3.6, inside every conforming window
idx 9..10 (17.9/19.4): (CPost1 - CPost2) >= RefreshMinStep         // GATE: drain CONTINUES past the
                     // UN-refreshed band top — else "re-application did not refresh the duration"
idx 11..12 (21.4/23.5): (CStop1 - CStop2) <= StopEpsilon           // GATE: refreshed drain still ENDS
                     // (window opens at re-apply+7.1) — else "refreshed poison never expired"
idx 13 (24.5): SetHealth(100); Trigger x4                          // Leg B/D (cap -> ~3 stacks)
idx 14 (26.1): mid-drain sample (logged)
idx 15 (28.6): RateB over (trigger, trigger+4.1] — CONGRUENT with Rate1's Leg A window
    gate : RateB / Rate1 >= StackRatioMin (2.0)                    // Leg B: stacking scales the rate
    gate : RateB / Rate1 <= StackRatioMax (3.5)                    // Leg D: the cap holds (uncapped ~4x)
always   : NumGrantedAbilitiesWithTag(Ability.Poison) >= 1 ; ability activated
advisory : the exact ~3x multiplier is LOGGED (already bounded by the two ratio gates)
```

**Pass criteria** (gated): the stage-1 gate holds at checkpoint 0 (derivation,
Health present, initialized to 100, write moves it, and — 2026-08-06 — the
pawn is visibly represented — else a NAMED stage-1/visibility
FAIL, never a misattributed "not periodic"); poison is granted + activates;
Health drops periodically and **stops** inside the ~5s acceptance band
(Leg A); a mid-window re-application **refreshes** the duration — the drain
continues past the original expiry band and still ends by the refreshed one
(Leg C); 4 applications drain ≥ `StackRatioMin`× AND ≤ `StackRatioMax`× the
single-stack rate (Leg B/D — scaling works and the cap holds).

> Design note (relative gates): every stage-2 gate is a RATIO or a "still
> dropping?" — never an absolute magnitude. Stage 1 is the exception by
> design: `initialized to 100` is an absolute the prompt names explicitly (the
> GAS-contract exception covers it), because the stage-1 contract IS the
> interface the stage-2 legs then consume.
>
> **The ~5s acceptance band, made deliberate 2026-08-06:** the drain must still
> be stepping at trigger+4.1 (the periodic gate's last sample) and be fully
> over by trigger+7.1 (where the stop window opens) — durations of roughly
> 4-7s pass, with one-period (~1s) enforcement granularity above the top
> (ticks are what's observable; an expiry between ticks cannot be seen). The
> retired schedule's `StopEpsilon=9.0` existed because its tail sample sat
> INSIDE the band (trigger+7.0) and had to absorb legitimate expiry ticks —
> and still mis-failed a conforming ~6s duration by two ticks. Both stop
> windows (Leg A and Leg C's refreshed-stop) now open past the band top, so
> `StopEpsilon=2.5` absorbs only jitter: it is < 4.0 (two ticks at the minimum
> lawful per-tick step, so a permanent drain at the slowest conforming rate
> still fails a ≥2s window) and > rounding noise. Leg C's re-apply sits at
> trigger+3.6 — late enough that the refreshed expiry clears the UN-refreshed
> band top by ≥1.5s (a mid-window +2.5s re-apply would be indistinguishable
> from an un-refreshed ~6.5s duration), early enough to land inside every
> conforming ~4-7s window (this is also what pins the band floor at ~4s).
>
> Cap note — how the cap became gate-able (2026-08-06, resolving the
> 2026-06-16 advisory): the old fixture measured Leg B over 3.1s but Leg A
> (the ratio's denominator) over 4.1s. With unequal windows the tick-count
> quantization does NOT cancel, and a conforming capped GE legitimately read
> anywhere from ~2.98× to ~3.97× depending on period/phase config — which is
> why the 2026-06-16 calibration concluded the multiplier was "not reliably
> pinnable headless" (its ~9× reading was the then-reference's own
> −5×stackCount MMC being multiplied AGAIN by the engine's
> `bFactorInStackCount` stack factor — re-measured at exactly **9.00×** on UE
> 5.8 under the congruent windows 2026-08-06, then fixed by dropping the MMC;
> see Reference solution metadata). The redesigned Leg B window
> is **congruent** with Leg A's (both `(trigger, trigger+4.1]`), which cancels
> quantization for any conforming period/duration/on-application config, so
> the ratio reads the stack multiplier directly. Measured 2026-08-06 under
> `-deterministic -FPS=60`: capped reference = **3.00×**, uncapped probe
> (`discrimination/no-cap/`, `StackLimitCount=0`) = **4.00×**. The bar
> `StackRatioMax=3.5` sits midway with ~0.5× measured margin to both
> populations (bars are raised only by measuring — repo law).

## Reference solution metadata

- LOC range: 50-100 LOC (stage 1: the pawn subclass constructs the provided
  attribute set under a non-suppressed subobject name and inits Health/MaxHealth
  to 100 — and, since the 2026-08-06 visibility gate, constructor-assigns the
  template's mannequin mesh via a guarded `ConstructorHelpers::FObjectFinder`,
  same pattern as the substrate's `AFireCharacter`; stage 2: a `UGameplayEffect` subclass configured in its ctor —
  DurationPolicy=HasDuration (~5s), Period (~1s), a plain Health additive
  modifier (−5.0; UE 5.8's `bFactorInStackCount` — default true — multiplies
  periodic executions by the stack count, so NO MMC is needed and 3 stacks ⇒
  ~3× the drain), StackingType=AggregateByTarget, StackLimitCount=3,
  StackDurationRefreshPolicy=RefreshOnSuccessfulApplication,
  StackPeriodResetPolicy=ResetOnSuccessfulApplication; a `UGameplayAbility` that
  `ApplyGameplayEffectToSelf`s it on activate; the pawn granting it).
- Files touched: 6 new (`PoisonAbility.{h,cpp}`, `PoisonEffect.{h,cpp}`,
  `PoisonPawn.{h,cpp}` — the pawn carries the stage-1 build). The pre-epoch
  reference also shipped a `PoisonDamageMMC` returning −5×stackCount — on UE
  5.8 that magnitude is multiplied AGAIN by `bFactorInStackCount`, measuring
  **9.00×** the single-stack rate for 4 applications (superlinear, violating
  the prompt's "three stacks ≈ three times") — dropped at the 2026-08-06
  epoch, aligning the C++ recipe with the BP reference's (which never had an
  MMC). Leg D fails the old double-scaling recipe by design.
- Senior-dev hours: 1.5-2.5 hours.
- A Blueprint reference (BP pawn parenting the task base + BP GE + BP ability)
  is the equivalent deliverable; the verifier resolves a BP pawn via the asset
  registry. See `gp-poison-dot-stack-bp` for the BP-mandated variant.

## Anti-gaming notes

1. **Skip or fake stage 1 (health system absent, uninitialized, or inert).**
   *Failure modes*: the agent wires the ability but never builds the attribute
   set — reads silently return 0 and writes no-op, which without a gate would
   misgrade later as "not periodic"; or the set registers but Health reads 0;
   or an inert-write set initializes at 100 and would pass a 100-write
   vacuously. *Defenses*, both at the checkpoint-0 stage-1 gate: (1)
   **presence** — `HasAttributeSetForAttribute(Health)` FAILs by NAME
   ("stage 1 not built"); (2) **init + writability** — checkpoint 0 reads
   Health **before any fixture write** (must be 100±0.5), then write-probes at
   **37 ≠ 100** and requires the read-back to move. **Presence gate proven
   live 2026-08-05** (scratchpad probe, promoted to
   `discrimination/no-health-system/`).
2. **Dodge stage 1 by subclassing the generic scaffold pawn** (whose attribute
   set is still pre-built for other tasks' sake). *Defense*: the checkpoint-0
   **derivation gate** — the graded pawn must derive from the task base
   (`ACraftBenchBareCharacter`); a generic-pawn subclass FAILs by name. (An
   empty submission resolves to the generic base pawn and fails the same gate.)
   *Where this is proven* — there is no local one-delta variant, so the coverage
   is one measured local leg plus an **inherited** sibling reading. (1) The gate
   is `Pawn->IsA(ACraftBenchBareCharacter::StaticClass())` in
   `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-poison-dot-stack-bp/PoisonStackFunctionalTest.cpp`
   (cpp:80-89). (2) This task's own **empty** leg is MEASURED FAILing exactly
   that gate — `discrimination/MATRIX.md` records it at both 2026-08-06 epochs
   and again in the 2026-08-08 sweep ("empty **FAIL** at the named derivation
   gate"), which proves the gate fires on the generic scaffold pawn: the very
   class a generic-pawn subclass descends from. (3) The one-delta
   subclass-the-generic-pawn shape itself is variant-proven on the sibling
   `tasks/cpp/gp-health-attribute-ops-cpp`, whose fixture
   (`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-health-attribute-ops/HealthAttributeOpsFunctionalTest.cpp`,
   cpp:116-125) carries the same `IsA(ACraftBenchBareCharacter)` check and the
   same FAIL literal word for word; its committed `generic-pawn` variant swaps
   ONLY the pawn's parent class to `ACraftBenchCharacter` and is recorded
   **MEASURED 2026-08-10, L2 FAIL by name** in that task's per-note coverage
   table. Carrying that reading over here is an argument from identical gate
   code, not a second run.
3. **No GAS (drain Health without an ability).** *Defense*: (1)
   `NumGrantedAbilitiesWithTag(Ability.Poison) >= 1` reads the ASC; (2) requires
   activation on the tag-trigger. *Where this is proven* — gate (1) is
   `PoisonStackFunctionalTest.cpp:212/234-239` (named FAIL "no activatable
   ability tagged Ability.Poison on the pawn (GAS not implemented)") and gate
   (2) is cpp:240-245. **Corrected 2026-08-17 after review: only gate (1) reads
   the shared base helper.** Gate (1) tests `NumGrantedAbilitiesWithTag(PoisonTag)`
   from
   `UE-projects/ThirdPerson/Source/CraftBenchTests/CraftBenchPawnFunctionalTest.cpp`
   (`cpp:389`), so a sibling measurement of that helper transfers here. Gate (2)
   tests the fixture-LOCAL `bAbilityActivated` flag, which no shared helper feeds,
   so it inherits NOTHING from a sibling — consistent with this note's own
   residual below: gate (2) has no committed failing variant anywhere in the tree. Gate (1) has one historical LOCAL
   measurement plus an **inherited** sibling variant: before the 2026-08-05
   stage-1 restructure this task's own **empty** leg FAILed on exactly this
   grant literal (`discrimination/MATRIX.md`, empty row — "was the ability-grant
   message, 'no activatable ability ... granted=0'"; the derivation gate now
   fires first and masks it), and the drain-Health-with-nothing-granted shape is
   variant-proven on two siblings whose fixtures gate on the same helper in the
   same position (first final assertion): `tasks/cpp/gp-glide-stamina-cpp`'s
   committed `no-gas` (the reference with `GrantedAbilities.Add(...)` commented
   out; **VALIDATED 2026-08-08**, L1 pass / L2 FAIL on the tag-only-different
   literal "... Ability.Glide ... (GAS not implemented). granted=0") and
   `tasks/cpp/gp-health-attribute-ops-cpp`'s committed `no-gas` (**MEASURED
   2026-08-10**). **Gate (2), activation, has no failing variant anywhere in the
   tree** — it is argued from the fixture source plus the reference's measured
   `granted=1 activated=1`; what that gate does and does not bind is documented
   as requirements-table row 9 in `discrimination/MATRIX.md`.
4. **Instant burst / permanent drain / no-refresh re-application.** *Measured
   2026-08-08*: `discrimination/permanent-drain/` (`DurationPolicy = Infinite`,
   Period/magnitude tuned by exhaustive enumeration to hide inside the
   tolerances) FAILs by name at the Leg C refreshed-stop gate
   (`CStop1=46.0 -> CStop2=39.2, drop 6.8 > 2.5`). **Read the caveat in
   `discrimination/MATRIX.md`:** that same run PASSED the **Leg A** stop gate
   (drop 2.3 vs the 2.5 bar) on a poison that never ends, because the shipped
   `StopEpsilon` derivation presumes >=2 ticks per stop window and no period
   bound is enforced. The task is saved by cross-leg stack accumulation, which
   is incidental rather than designed. *Defense*:
   Leg A samples Health across the ~5s window and again in a post-band stop
   window — a lump-sum drop fails the periodic steps; a never-ending drain
   fails the stop-check; and **Leg C** (2026-08-06) re-applies mid-window and
   requires the drain to CONTINUE past the original expiry band ("re-application
   did not refresh the duration" is the named FAIL for a GE that resets
   nothing — the staged `discrimination/no-refresh/` variant) and to still STOP
   by the refreshed one ("refreshed poison never expired").
5. **No stacking (rate doesn't scale) — or no CAP (a 4th application keeps
   stacking).** *Defense*: **Leg B/D** bounds the 4-application/single-stack
   rate ratio on BOTH sides: ≥ `StackRatioMin` (a flat rate fails) and — gated
   2026-08-06 — ≤ `StackRatioMax` (an uncapped GE reads ~4× vs the capped ~3×;
   the staged `discrimination/no-cap/` variant). The rate windows of Legs A and
   B are congruent, so the ratio is pinnable headless (see the cap note).
6. **Invisible deliverable (skip the visual entirely).** *Failure mode*: a
   behaviorally-correct pawn with no mesh — measured on the glide family
   2026-08-04 (9/9 matrix reps meshless) and this task's own film strips
   showed an empty scene. *Defense* (2026-08-06): the checkpoint-0
   **visible-character fixture gate** (stage-1 gate (e)) — the graded pawn
   must carry a skeletal/static mesh component with a mesh actually assigned,
   else the named FAIL "the character is not visibly represented". Structural
   and deterministic, and since 2026-08-11 it also requires the component to
   RENDER (not hidden in game, not scaled to nothing) — a hidden mesh used to
   pass the gate that exists because pawns were invisible. **This is the ONLY
   visibility defense on this family**: the `-bp` L2I `pawn_visibly_represented`
   check this line used to cite as its twin is not defined for poison.
   *Where this is proven* — the gate is the shared base helper
   `ACraftBenchPawnFunctionalTest::PawnVisiblyRepresented`
   (`UE-projects/ThirdPerson/Source/CraftBenchTests/CraftBenchPawnFunctionalTest.cpp`,
   cpp:295 onward), called from `PoisonStackFunctionalTest.cpp:151`; it was
   hoisted out of five inlined per-fixture copies on 2026-08-11, so every caller
   now runs identical code. The no-mesh-at-all branch — the one that ends
   `no mesh component with an assigned mesh on the graded pawn`, i.e. exactly the
   failure mode this note names — is variant-proven twice on siblings that call
   this same gate, and this note
   **inherits** that coverage: `tasks/cpp/gp-glide-stamina-cpp`'s committed
   `no-mesh` (the reference minus its constructor
   `ConstructorHelpers::FObjectFinder` mesh assignment, the same pattern this
   task's reference uses; **VALIDATED 2026-08-08**, L1 pass / L2 FAIL on this
   exact literal) and `tasks/cpp/gp-health-attribute-ops-cpp`'s committed
   `no-mesh` (**MEASURED 2026-08-10**). Both readings predate the 2026-08-11
   hoist, so they ran against inlined copies emitting this same literal.
   **Not covered by any variant, here or anywhere in the tree: the two RENDER
   branches** (a mesh assigned but hidden in game, or scaled to ~zero) — those
   are argued from the base-class source only; both branch literals are
   enumerated as requirements-table row 6 in `discrimination/MATRIX.md`.

## Hidden invariants

- **Stage order is enforced by observation, not narration.** Checkpoint 0 runs
  before any trigger, so a submission cannot pass stage 2 without stage 1 —
  the drain legs read the same attribute stage 1 must expose.
- **Periodic AND bounded.** The distinction from both an instant hit and a
  permanent drain is that Health falls in ~1s steps and then *stops* inside
  the ~5s acceptance band (~4-7s) — Leg A samples across the window and again
  in a post-band stop window to pin both.
- **Re-application refreshes, and the refreshed effect still ends.** Leg C
  (2026-08-06) re-applies at trigger+3.6 and gates BOTH directions: drain
  past the un-refreshed band top, silence past the refreshed one.
- **The rate scales with stacks, AND the cap holds.** Leg B/D bounds the
  4-application/single-stack ratio to `[StackRatioMin, StackRatioMax]` =
  [2.0, 3.5] (2026-08-06; congruent rate windows make the ratio pinnable —
  see the cap note).
- **Health is read via the contract attribute** (`GetHealthAttribute()` on the
  provided attribute set type) — an agent that builds a custom attribute set
  type, or drains a different attribute, fails the stage-1/Health checks.
- **The write probe uses 37, not 100.** Checkpoint 0 reads init-100 FIRST,
  then writes 37 and requires the read-back to move — an inert-write set that
  happens to initialize at 100 cannot pass the writability gate vacuously.
- **GAS pawn-resolution dependency:** the fixture overrides
  `PreferredAbilityTag()` → `Ability.Poison` so the resolver picks the poison
  pawn, never another committed `ACraftBenchCharacter` subclass. The committed
  task base is `UCLASS(Abstract)`, so the resolver (which skips abstract
  classes) can never grade the base itself. See
  `Source/CraftBenchTests/CraftBenchPawnFunctionalTest.cpp`.
- The map (`Content/Maps/L_PoisonStack.umap`) has no GameModeOverride, so PIE
  also spawns the substrate's default `BP_ThirdPersonGameMode` pawn at the
  PlayerStart. It is not an `ACraftBenchCharacter` subclass, so it can never
  win pawn resolution and no gate reads it — the graded pawn is exclusively
  the one the fixture spawns.
