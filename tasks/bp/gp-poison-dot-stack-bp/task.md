---
id: gp-poison-dot-stack-bp
substrate: ThirdPerson
set: bp
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_PoisonStack :: APoisonStackFunctionalTest"]
introspect: [gp_poison_dot_stack_bp.py]
---

# gp-poison-dot-stack-bp

**Blueprint-deliverable variant** of `gp-poison-dot-stack-cpp` (the g2-9
"Health/Poison" port). The behavior spec, fixture logic, checkpoint schedule,
and every L2 gate are **identical** to the C++ original so C++-vs-BP results
are directly comparable; the only deltas are (a) the prompt mandates a
**Blueprint** deliverable under `Content/Tasks/gp-poison-dot-stack-bp/` and
(b) an L2-introspect leg structurally asserts the deliverable really is
Blueprint (the anti-gaming gate against solving the "BP variant" in C++).

> **⚠ REDEFINITION EPOCH 2026-08-05 (health-first two-stage restructure).**
> Same restructure as the C++ original, same date: the task is now **two
> stages the agent builds in order** — **stage 1 builds the health system**
> (the pawn exposes a drainable Health resource, initialized to 100,
> readable+writable through GAS), **stage 2 builds the poison DoT**. The
> substrate's task base pawn ships an ability system and **no** health
> resource; the checkpoint-0 gate (formerly an anti-broken-submission
> defense) is now THE stage-1 verifier (derivation + presence + init-to-100 +
> a ≠100 write probe). **Results recorded before and after this date are not
> comparable** — same convention as `gp-glide-stamina-cpp`'s 2026-08-04
> redefinition.

> **⚠ REDEFINITION EPOCH 2026-08-06 (Legs C/D — refresh + cap become gates;
> owner decision 2026-08-06).** Same redefinition as the C++ original, same
> date, byte-identical fixture logic: the stack **cap** and duration
> **refresh** the prompt always demanded are now real gates (Leg C refresh,
> Leg D cap upper bound on the stacking ratio) on a 16-checkpoint schedule,
> and the Leg A stop check moved onto a deliberate ~5s acceptance band. This
> RESOLVES the 2026-08-03 correction below. **Gates were added, so the task
> got strictly harder: results recorded before and after this date are not
> comparable** — same convention as the health-first note above.

> **Substrate: ThirdPerson (owner decision 2026-08-05).** This task runs on the
> `UE-projects/ThirdPerson/` substrate — the stock UE 5.8 Third Person C++
> template, which ships the Manny/Quinn mannequin content **natively** under
> `/Game/Characters/`. It previously ran on `CraftBenchTemplate` (git history
> keeps that variant); gameplay tasks now use the ThirdPerson substrate
> directly, following `gp-glide-stamina-bp`'s 2026-08-05 migration. The GAS
> scaffold and the `APoisonStackFunctionalTest` fixture are ported from the
> template substrate with byte-identical gate logic. Re-validation on the new
> substrate is pending (see `REFERENCE-NOTE.md` and `discrimination/MATRIX.md`).

> Variant note (deliverable-format exception): like the GAS-contract naming,
> mandating the **Blueprint** authoring surface is a deliberate, documented
> exception to behavior-only prompts — measuring the BP authoring path *is
> the point* of this variant. The `-bp` suffix is the benchmark's convention
> for such variants (see `tasks/README.md`).

> GAS-category note (inherited from the original, extended 2026-08-05 for
> stage 1): this task names the GAS contract as part of the interface — a
> documented exception to behavior-only prompts, because verifying the health
> system and the periodic-stacking effect *through GAS* is the point. The
> named contract: the pawn's ability system must expose a **Health** attribute
> **via the attribute set type the project provides** (the verifier reads that
> type's Health attribute), initialized to **100**; the poison ability is
> tagged `Ability.Poison` and granted on the pawn; the drained resource is
> that same `Health` attribute.

## Primary concept

- `gas-attributes` — Gameplay Attributes and Attribute Sets, built by the agent
  (stage 1) and moved by a periodic stacking GameplayEffect (stage 2)
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-attributes-and-attribute-sets-for-the-gameplay-ability-system-in-unreal-engine)

The load-bearing mechanics are unchanged from `gp-poison-dot-stack-cpp`: stage 1 —
an attribute set registered and initialized on the pawn's ability system
**without writing C++** (an editor-visible wiring route on the inherited
ability system component); stage 2 — a **periodic, stacking** GameplayEffect
(~1s period, ~5s duration, stacks scale the drain) — authored **in Blueprint**.

## Prompt given to the agent

> The project provides a **task character pawn** that owns an ability system
> but **no health resource yet** (the project also contains a generic
> character with a pre-built attribute set, used by other tasks — your pawn
> must be a subclass of the *task* character, not the generic one).
> Build the feature in two stages, in order:
>
> **Stage 1 — build the health system.** Give your pawn (a Blueprint subclass
> of the provided task character) a **Health** attribute exposed through its
> ability system, using the attribute set type the project provides — wired
> and initialized **in the editor**, not in C++. Health must be **initialized
> to 100** and must be readable AND writable through the standard attribute
> APIs (the verifier both reads it and writes it).
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
> - The character must be **visibly represented**: assign one of the provided
>   mannequin skeletal meshes (under `/Game/Characters/`) as your character's
>   mesh, so a reviewer watching the run can see it take the poison.
> - Deliver your solution **entirely as assets** created in the editor and
>   saved under `Content/Tasks/gp-poison-dot-stack-bp/`: a Blueprint subclass
>   of the provided task character with your health system built and your
>   ability granted on it. **Do not add or modify any C++ source for this
>   task.**
>
> The verifier first checks your health system (stage 1: Health present,
> initialized to 100, and responsive to a write), then applies your ability by
> sending the `Ability.Poison` tag (one or more times) and observes the Health
> attribute over time.

## Workspace state pre-task

Files that **exist** under `Source/ThirdPerson/` (read-only context for this
task — the deliverable is asset-only):

- The stock UE 5.8 Third Person C++ template sources (`ThirdPersonCharacter`,
  game mode, the Variant_* trees). No edit needed and none allowed by the
  prompt.
- `ThirdPerson.Build.cs` — already includes `GameplayAbilities`,
  `GameplayTags`, `GameplayTasks`. No edit needed.
- `CraftBenchBareCharacter.{h,cpp}` — **the task base pawn (stage-1 start
  state)**: an abstract `ACraftBenchCharacter` lineage with a pawn-owned ASC
  (visible as an inherited component in a Blueprint subclass), the
  auto-granted `GrantedAbilities` array (ships empty, `EditAnywhere` —
  settable from Blueprint class defaults), the `CraftBenchPawn` tag, and **no
  attribute set**. Stage 1 = registering + initializing the provided attribute
  set on that inherited ability system component through an editor-visible
  route.
- `CraftBenchCharacter.{h,cpp}` — the generic scaffold pawn other tasks use;
  it still pre-builds the attribute set. **Parenting your Blueprint to it does
  not satisfy this task** — the stage-1 derivation gate fails a pawn that is
  not on the task-base lineage, by name.
- `CraftBenchAttributeSet.{h,cpp}` — the contract attribute set type
  (`Health`, `MaxHealth`, `Power`). `Health` is the attribute the verifier
  reads and poison drains. The class exists; **registering (and initializing)
  an instance on your pawn's ability system is stage 1**.
- `CraftBenchGameplayTags.{h,cpp}` — registers `Ability.Poison`
  (`FCraftBenchGameplayTags::AbilityPoison()`).
- The `GameplayAbilities` plugin is enabled.
- `APoisonStackFunctionalTest` lives in the verifier-only `CraftBenchTests`
  module (`Source/CraftBenchTests/Tasks/gp-poison-dot-stack-bp/`).

Files the agent **creates** (all assets, under
`Content/Tasks/gp-poison-dot-stack-bp/` — the `Content/Tasks/` prefix is
agent-writable for asset deliverables): a Blueprint subclass of the provided
task character with the health system wired + initialized (stage 1; any
supporting asset — e.g. an init data table or an init effect — lives in the
same folder), a Blueprint GameplayEffect (periodic, stacking, duration-limited
Health drain) and a Blueprint ability tagged `Ability.Poison` that applies it
(stage 2), with the ability in the pawn's granted-abilities list. The pawn is
resolved by derivation (the verifier scans Blueprint assets under `/Game/Tasks`
via the Asset Registry) and spawned + possessed by the verifier.

## Verifier specification

**L2 — behavioral (identical to `gp-poison-dot-stack-cpp`).** The
`APoisonStackFunctionalTest` fixture, checkpoint schedule, and gates are the
C++ original's, ported byte-identical to this substrate's `CraftBenchTests`
module — see `tasks/cpp/gp-poison-dot-stack-cpp/task.md` §Verifier
specification for the full pseudo-code. The map
(`Content/Maps/L_PoisonStack.umap`) is a byte-copy of the template
substrate's: its only non-engine class reference is
`/Script/CraftBenchTests.PoisonStackFunctionalTest`, the same class path in
both substrates. Summary of the gated legs:

```text
STAGE-1 GATE (idx 0, BEFORE the trigger — all named FAILs, 2026-08-05):
  (a) derivation : the graded pawn IsA the task base (CraftBenchBareCharacter)
                   -- "stage 1 not built: ... does not derive from the provided task base pawn"
                   (an empty submission resolves to the generic scaffold pawn and fails HERE)
  (b) presence   : the ASC carries the Health attribute
                   -- "stage 1 not built: the pawn's health attribute system is absent"
  (c) init       : Health reads 100 (+/- 0.5) BEFORE any fixture write
                   -- "stage 1 incomplete: Health must initialize to 100"
  (d) writability: write 37 (a value != 100 on purpose), read-back must move
                   -- "stage 1 incomplete: health attribute is inert, write-then-read failed"
  (e) visibility : a skeletal/static mesh component with an assigned mesh exists
                   on the graded pawn (2026-08-06, shared-fixture gate)
                   -- "the character is not visibly represented: no mesh component
                   with an assigned mesh on the graded pawn"
                   (CORRECTED 2026-08-11: this cited L2I's pawn_visibly_represented
                   as a stricter twin. That check is NOT defined for poison --
                   gp_poison_dot_stack_bp.py neither defines it nor imports the
                   shared lib that does -- so this fixture gate is the ONLY
                   visibility defense, and it is not redundant with anything.
                   Since 2026-08-11 it also requires the mesh to RENDER: not
                   hidden in game, not scaled to nothing.)
Leg A: single application  -> Health drops periodically (steps), then STOPS
                              inside the ~5s acceptance band (~4-7s; the stop
                              window opens PAST the band top at trigger+7.1)
Leg C: re-apply mid-window -> REFRESH gate (2026-08-06): the drain must
                              CONTINUE past the UN-refreshed band top
                              ("re-application did not refresh the duration")
                              AND still END by the refreshed one
                              ("refreshed poison never expired")
Leg B/D: 4 applications    -> StackRatioMin (2.0) <= RateB/Rate1 <= StackRatioMax (3.5)
                              (lower bound: stacking scales; upper bound
                              2026-08-06: the cap of 3 holds — uncapped ~4x.
                              Congruent 4.1s rate windows make it pinnable.)
always: NumGrantedAbilitiesWithTag(Ability.Poison) >= 1 ; ability activated
```

> **Correction, 2026-08-03 — RESOLVED 2026-08-06 (Legs C/D implemented; owner
> decision 2026-08-06).** This block used to document that the prompt's stack
> CAP and duration REFRESH requirements contributed **zero bits to the
> verdict**: the old 8-checkpoint schedule
> (`{0.5, 1.6, 3.1, 4.6, 7.5, 8.5, 10.1, 11.6}`) had exactly two trigger
> points, no in-window re-application, no sample past the original expiry,
> and an advisory-only cap ratio. The 2026-08-06 redefinition shipped the
> designed-but-never-built legs for real: the fixture now runs the
> 16-checkpoint schedule above with a mid-window re-application (Leg C, both
> refresh directions named FAILs) and a measured upper bound on the stacking
> ratio (Leg D; capped reference measured 3.00×, uncapped probe 4.00×, bar
> 3.5 — see the C++ original's cap note for the congruent-window argument
> that made the ratio pinnable). The prompt is unchanged — cap and refresh
> were always demanded; now they are honest. The staged
> `discrimination/no-refresh/` and `discrimination/no-cap/` variants (C++
> original) are the regression probes for this resolution.

The fixture resolves the pawn by derivation from `ACraftBenchCharacter`
(`ResolveAgentPawnClass` scans native subclasses AND Blueprint assets under
`/Game/Tasks` via the Asset Registry, preferring the candidate that grants an
`Ability.Poison`-tagged ability), so the Blueprint deliverable grades with no
fixture changes. The committed task base is `UCLASS(Abstract)` and the
resolver skips abstract classes, so the base itself can never be graded.

**L2-introspect — structural "the deliverable is Blueprint" gate.** The
verifier-owned script `tools/verify-single/introspect/gp_poison_dot_stack_bp.py`
runs headless via `UnrealEditor-Cmd -ExecutePythonScript=`, and PASS requires
every check:

```text
task_folder_exists       : /Game/Tasks/gp-poison-dot-stack-bp/ exists and lists >= 1 asset
bp_pawn_present          : >= 1 Blueprint asset under that folder whose GeneratedClass
                           derives from ACraftBenchCharacter
bp_pawn_grants_bp_ability: that Blueprint pawn's GrantedAbilities class-defaults array
                           contains >= 1 ability class that is itself Blueprint-generated
                           (its class path lives under /Game/, not /Script/)
resolved_pawn_is_blueprint: NO agent-authored native (C++) subclass of ACraftBenchCharacter
                           exists. The clean substrate ships exactly ONE native subclass --
                           the committed ABSTRACT stage-1 base (CraftBenchBareCharacter),
                           exempted by exact /Script/ path; the L2 resolver skips
                           CLASS_Abstract, so it can never be the graded decoy. Any OTHER
                           native subclass fails this check: native candidates are resolved
                           BEFORE Blueprint ones, so a C++ solve shipped next to a
                           conforming Blueprint would win L2 while the Blueprint satisfies
                           the existence checks above.
effect_is_blueprint      : NO agent-authored native (C++) UGameplayEffect subclass exists
                           (added 2026-08-11). The three checks above reject a native
                           PAWN and a native ABILITY, and neither sees a native EFFECT --
                           which on this task is where the graded behaviour lives: period,
                           duration, the Health modifier, stacking policy, stack limit and
                           refresh policy are all GameplayEffect properties. A Blueprint
                           pawn granting a Blueprint ability that applies a C++ effect
                           passed all four earlier checks with its entire assessed
                           behaviour in C++. Neither substrate commits a UGameplayEffect
                           subclass outside the verifier module, so any /Script/ effect
                           found is agent C++ by construction.
```

Identity is by **pre-declared content path** (`/Game/Tasks/gp-poison-dot-stack-bp/`)
and **derivation**, never by asset name or class name — the agent may name the
Blueprints anything.

## Reference solution metadata

- LOC range: 0 lines of C++. 4-5 Blueprint-era assets: a BP subclass of the
  task base with the provided attribute set registered + initialized to 100
  through an editor-visible route on the inherited ability system component
  (plus its init data asset/table if that route needs one); a BP GameplayEffect
  (DurationPolicy=HasDuration (~5s), Period (~1s), a Health additive modifier,
  StackingType=AggregateByTarget, StackLimitCount=3, refresh/reset-on-
  application stacking policies); a BP GameplayAbility tagged `Ability.Poison`
  that applies it to self on activate.
- Files touched: 4-5 new assets under `Content/Tasks/gp-poison-dot-stack-bp/`.
- Senior-dev hours: 1.5-2.5 hours (same behavior design as the C++ original;
  editor-authoring replaces code-authoring, stage 1 included).
- The concrete no-C++ stage-1 wiring route, with its verification status, is
  documented in `REFERENCE-NOTE.md` (editor re-authoring pending — see
  an internal working note (not shipped)).

## Anti-gaming notes

1. **Skip stage 1 (grant poison on a pawn with no health system).** *Defense*:
   checkpoint-0 stage-1 gate — `HasAttributeSetForAttribute(Health)` FAILs by
   NAME ("stage 1 not built"). **Proven live 2026-08-05** on the C++ fixture
   logic this substrate shares byte-identically (probe promoted to the C++
   original's `discrimination/no-health-system/`). The BP-side twin — a bare-
   parented BP pawn with a mesh and no health wiring — **now ships committed on
   this task** as `discrimination/bp-no-health-system/`, MEASURED FAIL at this
   gate at HEAD 2026-08-06 (`dfee504`); the earlier "on the editor re-authoring
   list" wording is retired — see that row in `discrimination/MATRIX.md`.
2. **Dodge stage 1 by parenting the BP pawn to the generic scaffold character**
   (pre-built attribute set). *Defense*: the checkpoint-0 **derivation gate** —
   the graded pawn must derive from the task base; a generic-parent BP FAILs by
   name. Register-but-never-initialize and inert-write fakes fail gates (c)/(d)
   (init read BEFORE any write; write probe at 37 ≠ 100). *Where proven*: no BP
   generic-parent variant is committed on THIS task (it needs an authored asset),
   so the defense is **argued**, from two things. (i) The gate itself — the
   `IsA(ACraftBenchBareCharacter)` rung at
   `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-poison-dot-stack-bp/PoisonStackFunctionalTest.cpp`
   lines 80-88, whose FAIL text names this exact dodge ("a submission
   subclassing the generic scaffold pawn inherits a pre-built health system and
   skips stage 1"), with gates (c)/(d) immediately below it in the same
   `case 0:`; being an `IsA` test it is blind to the class name and to
   C++-vs-BP, so a Blueprint on the generic lineage trips it exactly like a
   native one. (ii) That same rung, with a **byte-identical FAIL literal**, is
   MEASURED against a real reparented-**Blueprint** decoy on the sibling task
   `gp-health-attribute-ops-bp`: its committed `bp-generic-pawn` variant (the
   reference BP pawn with one property changed — the parent set to the generic
   scaffold character) ran 2026-08-11 and was credited at that named substring.
   The two fixtures share the pawn-resolution base class but each writes its own
   derivation rung (the health-ops copy: `HealthAttributeOpsFunctionalTest.cpp`
   lines 116-125), so this is same-logic evidence, not shared-code evidence. On
   this task the automatic **empty** leg reaches the identical gate and message,
   but its row in `discrimination/MATRIX.md` records that it has NOT been re-run
   since the 2026-08-05 epoch — so read the poison-side gate as
   assert-verified, not measured-at-HEAD.
3. **Solve it in C++ anyway (defeats the variant's point).** *Defense*: the
   L2-introspect leg FAILs `bp_pawn_present` — no Blueprint subclass of the
   provided character exists under `/Game/Tasks/gp-poison-dot-stack-bp/`.
   *Where proven*: this task's own committed variant `discrimination/cpp-solve/`
   (C++ pawn/ability/effect, zero assets), measured FAIL at that named check
   2026-07-17 — pre-migration substrate, not re-run at HEAD (see its row in
   `discrimination/MATRIX.md`). Re-provable token-free at any time against THIS
   task's own introspect script: the offline oracle
   `tools/verify-single/tests/test_introspect_bp_variant_resolution.py`
   (`test_cpp_solve_fails`) drives `gp_poison_dot_stack_bp.py` over a C++-only
   fake and asserts it scores 0 of its 5 checks.
4. **Decoy BP shell + real C++ solve.** *Failure mode*: a Blueprint pawn
   satisfies the existence checks while a C++ pawn wins L2 resolution.
   *Defense*: **`resolved_pawn_is_blueprint`** — no agent-authored native
   subclass of `ACraftBenchCharacter` may exist (the committed ABSTRACT task
   base is exempted by exact path; it cannot win resolution). Fails closed if
   the reflection sweep ever stops working. *Where proven*: the decoy ships as
   this task's committed `discrimination/cpp-solve-with-bp/`, but it has never
   been measured HERE — its three `Content/` binaries were left unported by the
   2026-08-06 substrate migration (re-verified by byte scan: they still carry
   `/Script/CraftBenchTemplate` references and no `CraftBenchBareCharacter`
   parent), so at HEAD that overlay would die at the earlier `bp_pawn_present`
   instead of at the gate it targets — the `cpp-solve-with-bp` note in
   `discrimination/MATRIX.md` carries this caveat. What IS proven: (i) the
   measured PASS→FAIL on the 3-check vs 4-check verifier (2026-08-03,
   CraftBenchTemplate era) is **inherited** from the sibling that shares this
   L2I check — `gp-glide-stamina-bp`, whose matrix carries that before/after
   table; (ii) token-free at HEAD, on THIS task's own script, the offline oracle
   `tools/verify-single/tests/test_introspect_bp_variant_resolution.py`
   (`test_decoy_passes_every_older_check_and_fails_only_the_newest`) asserts the
   decoy passes `task_folder_exists`, `bp_pawn_present` and
   `bp_pawn_grants_bp_ability` and fails `resolved_pawn_is_blueprint` alone.
5. **Instant burst / permanent drain / no stacking / no CAP / no REFRESH**
   (inherited, extended 2026-08-06): Leg A periodic steps + band stop-check;
   Leg C both refresh directions (a GE whose re-application resets nothing
   FAILs by name — `discrimination/no-refresh/` on the C++ original); Leg B/D
   `StackRatioMin <= RateB/Rate1 <= StackRatioMax` (an uncapped GE reads ~4×
   and FAILs by name — `discrimination/no-cap/`). See the resolved 2026-08-03
   correction above.

## Hidden invariants

- All hidden invariants of `gp-poison-dot-stack-cpp` apply unchanged (stage order
  enforced by observation; periodic AND bounded; rate scales with stacks;
  Health read via the contract attribute; the 37≠100 write probe;
  `PreferredAbilityTag()` → `Ability.Poison` pawn-resolution preference; the
  abstract task base is skipped by the resolver).
- **BP resolution is Asset-Registry-based**: the fixture only discovers
  Blueprint pawns saved under `/Game/Tasks/` — a BP saved elsewhere (e.g.
  `Content/Blueprints/`) is sandbox-accepted but never resolved, and fails L2.
- The map has no GameModeOverride, so PIE also spawns the substrate's default
  `BP_ThirdPersonGameMode` pawn at the PlayerStart. It is not a
  `ACraftBenchCharacter` subclass, so it can never win pawn resolution and no
  gate reads it — the graded pawn is exclusively the one the fixture spawns.
