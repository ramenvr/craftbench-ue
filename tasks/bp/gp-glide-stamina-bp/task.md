---
id: gp-glide-stamina-bp
substrate: ThirdPerson
set: bp
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_GlideStamina :: AGlideStaminaFunctionalTest"]
introspect: [gp_glide_stamina_bp.py]
---

# gp-glide-stamina-bp

**Blueprint-deliverable variant** of `gp-glide-stamina-cpp` (the g2-10
"Movement/Glide" port). The behavior spec, fixture logic, checkpoint schedule,
and every L2 gate are **identical** to the C++ original so C++-vs-BP results
are directly comparable; the only deltas are (a) the prompt mandates a
**Blueprint** deliverable under `Content/Tasks/gp-glide-stamina-bp/` and (b) an
L2-introspect leg structurally asserts the deliverable really is Blueprint
(the anti-gaming gate against solving the "BP variant" in C++).

> **Substrate: ThirdPerson (owner decision 2026-08-05).** This task runs on the
> `UE-projects/ThirdPerson/` substrate — the stock UE 5.8 Third Person C++
> template, which ships the Manny/Quinn mannequin content **natively** under
> `/Game/Characters/`. It previously ran on `CraftBenchTemplate` with the same
> mannequin content dropped in (the 2026-08-04 "mannequin pool" redefinition —
> git history keeps that variant); gameplay tasks now use the ThirdPerson
> substrate directly, so no asset drop is needed. The GAS scaffold
> (`ACraftBenchCharacter` + `Power` attribute + the `Ability.Glide` tag) and
> the `AGlideStaminaFunctionalTest` fixture were ported **verbatim** — no
> behavioral gate changed. Re-validation on the new substrate is pending
> (see `REFERENCE-NOTE.md` and `discrimination/MATRIX.md`).

> Variant note (deliverable-format exception): like the GAS-contract naming,
> mandating the **Blueprint** authoring surface is a deliberate, documented
> exception to behavior-only prompts — measuring the BP authoring path *is
> the point* of this variant. The `-bp` suffix is the benchmark's convention
> for such variants (see `tasks/README.md`).

> GAS-category note (inherited from the original): this task names the GAS
> contract (an ability tagged `Ability.Glide`, granted to the provided
> ability-system pawn; the stamina resource is the pawn's `Power` attribute) as
> part of the interface — a deliberate, documented exception to behavior-only
> prompts, because verifying the behavior *through GAS* is the point.

> Tier-B scope note (inherited): headless PIE injects no player input, so the
> verifier fires `Ability.Glide` by tag while the pawn is already falling; the
> spacebar/apex input-gating of the original g2-10 is dropped.

## Primary concept

- `gas-overview` + `ps-character-movement` — a GAS ability modifying
  CharacterMovement fall physics while consuming an attribute
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-ability-system-for-unreal-engine)

The load-bearing behavior is unchanged from `gp-glide-stamina-cpp`: an activated
ability that (a) reduces the character's descent rate *while falling* and (b)
drains the `Power` attribute over time, ending the slow-fall when `Power` hits
0 — authored **in Blueprint**.

## Prompt given to the agent

> The project provides a character pawn that already owns an ability system, a
> depletable **Power** resource, and an array of abilities to grant. Implement an
> **ability** that, while the character is **falling through the air**, makes it
> descend noticeably **slower** than an unaided fall, and **steadily drains the
> Power resource** while it does so. When Power reaches zero, the slowed descent
> must **end** — the character falls at its normal rate again.
>
> - Tag the ability with the gameplay tag `Ability.Glide` and add it to the
>   pawn's granted abilities, so the game can activate the glide by that tag.
> - Deliver your solution **entirely as Blueprint assets** created in the editor
>   and saved under `Content/Tasks/gp-glide-stamina-bp/`: a Blueprint subclass
>   of the provided character with your ability granted on it (starting with
>   some Power to spend). **Do not add or modify any C++ source for this task.**
> - The slowed descent must come from the *active* ability draining Power — not a
>   permanent change to fall speed, and not a teleport.
> - The character must be **visibly represented**: assign one of the provided
>   mannequin skeletal meshes (under `/Game/Characters/`) as your character's
>   mesh, so a reviewer watching the run can see it fall and glide.
>
> The verifier activates your ability by sending the `Ability.Glide` tag while
> the character is falling, and observes the resulting descent speed and Power
> over time.

## Workspace state pre-task

Files that **exist** under `Source/ThirdPerson/` (read-only context for this
task — the deliverable is asset-only):

- The stock UE 5.8 Third Person C++ template sources (`ThirdPersonCharacter`,
  game mode, the Variant_* trees). No edit needed and none allowed by the
  prompt.
- `ThirdPerson.Build.cs` — already includes `GameplayAbilities`,
  `GameplayTags`, `GameplayTasks`. No edit needed.
- `CraftBenchCharacter.{h,cpp}` — `ACharacter` + `IAbilitySystemInterface` with a
  pawn-owned ASC, a minimal attribute set (`Health`, `MaxHealth`, `Power`), an
  auto-granted `GrantedAbilities` array (ships empty, `EditAnywhere` — settable
  from Blueprint class defaults), and the `CraftBenchPawn` tag. `Power` is the
  stamina resource for this task.
- `CraftBenchGameplayTags.{h,cpp}` — registers `Ability.Glide`
  (`FCraftBenchGameplayTags::AbilityGlide()`).
- The `GameplayAbilities` plugin is enabled.
- `AGlideStaminaFunctionalTest` lives in the verifier-only `CraftBenchTests`
  module (`Source/CraftBenchTests/Tasks/gp-glide-stamina-bp/`).
- `Content/Characters/Mannequins/` — the substrate's **native**
  visual-representation content (SKM_Manny_Simple / SKM_Quinn_Simple, the
  SK_Mannequin skeleton, and the stock animation set). Read-only:
  `Content/Characters/` is outside the writable sandbox, so a graded character
  is visible to a human reviewer instead of an invisible capsule.

Files the agent **creates** (all `.uasset`, under
`Content/Tasks/gp-glide-stamina-bp/` — the `Content/Tasks/` prefix is
agent-writable for asset deliverables): a Blueprint ability tagged
`Ability.Glide` that slows the fall + drains `Power` + stops at zero, and a
Blueprint subclass of the provided character whose granted-abilities list
contains it (and which starts with Power to spend). The pawn is resolved by
derivation (the verifier scans Blueprint assets under `/Game/Tasks` via the
Asset Registry) and spawned + possessed by the verifier.

## Verifier specification

**L2 — behavioral (identical to `gp-glide-stamina-cpp`).** The
`AGlideStaminaFunctionalTest` fixture, checkpoint schedule, and gates are the
C++ original's, ported byte-identical to this substrate's `CraftBenchTests`
module — see `tasks/cpp/gp-glide-stamina-cpp/task.md` §Verifier specification
for the full pseudo-code. The map (`Content/Maps/L_GlideStamina.umap`) is a
byte-copy of the template substrate's: its only non-engine class reference is
`/Script/CraftBenchTests.GlideStaminaFunctionalTest`, the same class path in
both substrates. Summary of the gated assertions:

```text
(0) checkpoint-0 visible-character fixture gate (2026-08-06, shared-fixture):
    a skeletal/static mesh component with an assigned mesh exists on the
    graded pawn — named FAIL "the character is not visibly represented: no
    mesh component with an assigned mesh on the graded pawn". The
    fixture-level twin of L2I's pawn_visibly_represented below (which
    additionally pins the mannequin path) — on this task the fixture gate
    adds redundancy, not a new requirement.
(1) NumGrantedAbilitiesWithTag(Ability.Glide) >= 1        // GAS implemented
(2) ability activated on the tag-trigger
(3) min |vZ| among gliding samples <= 0.6 * FreeFallVZ    // descent was slowed
(4) Power reached ~0                                       // stamina drained to empty
(5) slow-fall STOPPED once Power hit 0 — CONDITIONAL, two-path (2026-08-04),
    and window-honest (2026-08-06): only asserted if Power actually emptied
    in-window (else SKIPPED, advisory log line says so) AND the
    post-exhaustion observation window is >= the 0.30s WindowFloor — below
    the floor the gate is likewise SKIPPED, not failed, because with ~0s of
    window the ratio fallback reads 1.33-1.49x on conforming work (4
    measured near-miss reps, week of 2026-08-06; the checkpoint schedule was
    extended to {0.5, 1.0, 1.5, 1.9, 2.3, 2.7, 3.1, 3.6, 4.1} in the same
    correction so drains that empty by ~3.6s keep a >=0.5s window). When
    gated, passes on EITHER |vZ| >= ResumeVZ (350, the fast path) OR
    |vZ| >= 1.5x the same run's min glide speed (the ratio fallback — the
    absolute bar alone graded the DRAIN RATE, which the prompt never
    specifies, and false-failed 4 measured correct runs on 2026-08-04).
    Which path decided a run is in the [GLIDE-ADVISORY] /
    [GLIDE-RESUME-DIAG] lines, surfaced in the L2 report's verdict-evidence
    notes.
```

> **Calibration correction (2026-08-06), applied identically to both this task
> and `gp-glide-stamina-cpp`** (the fixture copies stay byte-identical): the old
> 7-checkpoint schedule ending at 3.1s gave a conforming-but-slow drain that
> emptied Power at the last checkpoint a 0.00s post-exhaustion window — 4
> measured near-miss FAILs (3 reps of `bench-20260806-023946` at |vZ|=298 vs a
> 300 bar, plus this task's the build machine opus rep 2 at 1.33x). Fixed by (a) appending
> checkpoints 3.6 + 4.1 and (b) the gate-(5) window floor above; see
> `tasks/cpp/gp-glide-stamina-cpp/task.md` for the full correction note.

The fixture resolves the pawn by derivation from `ACraftBenchCharacter`
(`ResolveAgentPawnClass` scans native subclasses AND Blueprint assets under
`/Game/Tasks` via the Asset Registry, preferring the candidate that grants an
`Ability.Glide`-tagged ability), so the Blueprint deliverable grades with no
fixture changes.

**L2-introspect — structural "the deliverable is Blueprint" gate.** The
verifier-owned script `tools/verify-single/introspect/gp_glide_stamina_bp.py`
runs headless via `UnrealEditor-Cmd -ExecutePythonScript=`, and PASS requires
every check:

```text
task_folder_exists       : /Game/Tasks/gp-glide-stamina-bp/ exists and lists >= 1 asset
bp_pawn_present          : >= 1 Blueprint asset under that folder whose GeneratedClass
                           derives from ACraftBenchCharacter
bp_pawn_grants_bp_ability: that Blueprint pawn's GrantedAbilities class-defaults array
                           contains >= 1 ability class that is itself Blueprint-generated
                           (its class path lives under /Game/, not /Script/)
resolved_pawn_is_blueprint: NO native (C++) subclass of ACraftBenchCharacter exists.
                           The three checks above are EXISTENCE checks and never ask which
                           pawn L2 actually grades; ResolveAgentPawnClass enumerates native
                           candidates BEFORE Blueprint ones, so a C++ solve shipped next to a
                           conforming Blueprint wins L2 while the Blueprint satisfies L2I.
pawn_visibly_represented : the Blueprint pawn's inherited mesh component has a
                           SkeletalMesh assigned whose asset path lives under
                           /Game/Characters/ (the substrate's native mannequin content).
```

Identity is by **pre-declared content path** (`/Game/Tasks/gp-glide-stamina-bp/`)
and **derivation**, never by asset name or class name — the agent may name the
Blueprints anything.

## Reference solution metadata

- LOC range: 0 lines of C++. 2-3 Blueprint assets (a BP GameplayAbility: tag in
  class defaults, on-activate applies a reduced-fall mechanism — e.g. lower
  `GravityScale` / capped fall velocity — starts a periodic Power drain via
  timer, and on Power<=0 restores normal fall + ends the ability; a BP subclass
  of the provided character granting it + initializing Power). This is exactly
  the "equivalent deliverable" shape the C++ original's task.md documents.
- Files touched: 2-3 new `.uasset` under `Content/Tasks/gp-glide-stamina-bp/`.
- Senior-dev hours: 45-90 minutes (same behavior design as the C++ original;
  editor-authoring replaces code-authoring).

## Anti-gaming notes

1. **Solve it in C++ anyway (defeats the variant's point).** *Failure mode*: the
   agent writes the same C++ solution as the original task — behaviorally
   correct, so L2 alone would pass it. *Defense*: the L2-introspect leg FAILs
   `bp_pawn_present` — no Blueprint subclass of the provided character exists
   under `/Game/Tasks/gp-glide-stamina-bp/`.

   *Where this is proven*: the task-local `discrimination/cpp-solve/` variant is
   byte-identical to `gp-glide-stamina-cpp`'s reference C++ solve with no
   Blueprint shipped beside it, and `discrimination/MATRIX.md` records it FAIL
   at the named check (`"id": "bp_pawn_present", "passed": false`). Read that
   row's stamp honestly: **2026-07-17, CraftBenchTemplate era**. The C++ sources
   were re-homed to the `Source/ThirdPerson/` prefix with their content
   unchanged, and the check reads the Asset Registry rather than anything
   substrate-specific, so the outcome is expected to hold — but the row has not
   been re-measured since the migration.
2. **Decoy BP shell + real C++ solve.** *Failure mode*: the agent ships a
   Blueprint pawn (enough to satisfy an existence check) plus a C++ pawn that
   actually implements the behavior and wins L2 resolution — so L2 grades the
   C++ while L2I grades the Blueprint and BOTH layers pass, on a submission the
   prompt explicitly forbids. *Defense*: **`resolved_pawn_is_blueprint`** — no
   native subclass of `ACraftBenchCharacter` may exist at all.

   This was a documented hole until 2026-08-03 and is now **measured**, not
   argued: the `discrimination/cpp-solve-with-bp/` variant (a C++ solve shipped
   next to the *real* Blueprint reference, which is strictly harder to satisfy
   than a do-nothing shell) graded **overall PASS** on the 3-check verifier and
   **overall FAIL** on the 4-check one, on UE 5.8, same box, same commit (on
   the pre-migration CraftBenchTemplate substrate; the check logic is
   substrate-independent). The reference still scores 4/4 and an empty
   submission still scores 0/4. The check is deliberately stronger than
   mirroring the fixture's tag preference: for a `-bp` task ANY C++ subclass of
   the provided character is already the violation, and that is the rule a
   human reviewer applies. It fails closed if the reflection sweep ever stops
   working, so a future UE API change cannot silently re-open the hole.
3. **No GAS (slow the fall without an ability).** *Defense* (inherited): (1)
   reads the resolved pawn's ASC; (2) requires the tag-trigger to activate
   something.

   *Where the inheritance is grounded* (this paragraph is the shared-fixture
   basis notes 4 and 5 also rely on): this task and `gp-glide-stamina-cpp` both
   declare the fixture `L_GlideStamina :: AGlideStaminaFunctionalTest`, and that
   class is compiled from ONE translation unit for BOTH tasks, and the reason
   is the `substrate:` key rather than uniqueness of the file. **Corrected
   2026-08-17 after review:** the repo tracks TWO definitions of
   `AGlideStaminaFunctionalTest` —
   `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-glide-stamina-bp/GlideStaminaFunctionalTest.cpp`
   and a pre-migration leftover at
   `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-glide-stamina-bp/GlideStaminaFunctionalTest.cpp`.
   What pins both tasks to the FIRST one is that this task.md and
   `gp-glide-stamina-cpp/task.md` both declare `substrate: ThirdPerson`, so the
   CraftBenchTemplate copy is compiled for neither and is graded by no task in
   the tree (verified by grepping every spec that names this fixture). The twin
   therefore does not own a *copy* of these gates, it drives the same
   translation unit — the conclusion stands, on the substrate key rather than
   on a uniqueness claim that was not true. A gate measured discriminating on the twin is therefore
   measured on the code that grades here. The family variants cited below are
   C++ overlays, so they are legs of the twin and could never be legs of this
   task (a C++ overlay also trips `resolved_pawn_is_blueprint`); what transfers
   is the shared L2 gate's measured discrimination, not the verdict.

   Gate (1) is proven by the family variant `discrimination/no-gas/` — one
   delta: it grants no ability at all and permanently lowers `GravityScale`
   instead, which is exactly this note's failure mode — VALIDATED 2026-08-08,
   L1 pass and L2 FAIL at the named substring
   `no activatable ability tagged Ability.Glide on the pawn (GAS not implemented). granted=`.
   Gate (2) — granted-but-never-activates — has **no committed variant** in the
   family; it is recorded as known hole (c) in
   `tasks/cpp/gp-glide-stamina-cpp/discrimination/MATRIX.md` rather than
   silently claimed.
4. **Teleport / no actual slow, or never drains stamina.** *Defense*
   (inherited): (3) requires the gliding descent ≤ 0.6× the same-run free-fall
   baseline; the draining assertion + (4) require Power to strictly drain to ~0.

   *Where this is proven* (same shared fixture as note 3): the **no-slow** half
   by the family variant `discrimination/no-slow/` — VALIDATED 2026-08-08, L2
   FAIL at `descent was not slowed by the glide: min glide`, measured min glide
   speed 1600.7 against a 725 bar (0.60 × a 1208.7 free-fall baseline). The
   **never-drains** half by `discrimination/no-drain/` — VALIDATED 2026-08-08,
   L2 FAIL at
   `the Power resource did not drain while gliding (the glide consumed no stamina)`.

   The **teleport** half of this note has NO defense, and no discrimination
   variant can supply one (a variant must FAIL, and this shape PASSES): every
   gate reads the pawn's velocity Z, and no assertion compares per-checkpoint
   displacement against the sampled velocity, so a submission that pins
   CharacterMovement velocity to a small negative vZ while driving the descent
   by writing the actor's location satisfies (3), (4) and (5). It is recorded as
   known hole (a) in `tasks/cpp/gp-glide-stamina-cpp/discrimination/MATRIX.md`;
   closing it needs a new assertion in the verifier-owned fixture, not a
   variant.
5. **Glide forever / permanent fall-speed change (not resource-gated).**
   *Defense* (inherited): (5) requires `|vZ|` to speed back up once Power hits
   0; a permanent low-gravity pawn or a never-stopping glide stays slow and
   fails (5).

   *Where this is proven* (same shared fixture as note 3): the
   **never-stopping** half by the family variant `discrimination/no-stop/` —
   one delta, the exhaustion `EndAbility` deleted while the real drain still
   floors Power at 0 — VALIDATED 2026-08-08, L2 FAIL at
   `the descent did NOT speed back up in a`. The slow-drain escape from that
   gate (the submission picks its own drain rate, and gate (5) skips when Power
   never empties in-window) is itself proven closed by
   `discrimination/slow-no-stop/` — VALIDATED twice 2026-08-09 at the same named
   substring, after the shared fixture began zeroing Power itself at
   `ForceExhaustCheckpoint` once the submission has already proved its own drain
   (`bForcedExhaust` in the fixture source cited in note 3).

   The **permanent fall-speed change** half is ARGUED, not measured, and the
   twin's matrix records it landing on a different gate than this note names:
   permanently lowered gravity also slows the same-run free-fall baseline the
   ratio is taken against, so gate (3) fires first at the same checkpoint. Same
   FAIL verdict, different named substring — see note 5 of
   `tasks/cpp/gp-glide-stamina-cpp/discrimination/MATRIX.md`.
6. **Invisible deliverable (skip the visual entirely).** *Failure mode*: the
   agent ships a behaviorally-correct pawn with no mesh — MEASURED 2026-08-04:
   all 9 matrix reps (3 models) shipped meshless pawns, and human review was
   only possible by instrumenting copies with a debug cube. *Defense*:
   **`pawn_visibly_represented`** requires a SkeletalMesh from the read-only
   `/Game/Characters/` content on the pawn's mesh component. Anchored to that
   path on purpose: "some mesh exists" is gameable with an empty placeholder
   asset under the writable path, while `/Game/Characters/` is the substrate's
   own deny-listed content the agent cannot author — and it mirrors the
   prompt's own instruction.

   *Where this is proven*: the check itself is implemented in
   `tools/verify-single/introspect/gp_glide_stamina_bp.py`, where
   `pawn_visibly_represented` passes only when the resolved BP pawn's assigned
   mesh path starts with `POOL_PREFIX` (`/Game/Characters/`) — read the source
   before trusting this sentence. Its POSITIVE leg is measured: the committed
   reference scores L2I 5/5 including this check (2026-08-06 `dfee504`, recorded
   in `discrimination/MATRIX.md`). Its NEGATIVE leg is measured only on the
   fixture-level twin of the same requirement — the checkpoint-0 gate
   `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn`
   in
   `UE-projects/ThirdPerson/Source/CraftBenchTests/CraftBenchPawnFunctionalTest.cpp`
   — which the family variant `discrimination/no-mesh/` (the twin's reference
   minus its mesh constructor) is VALIDATED 2026-08-08 to FAIL by name. **No
   variant anywhere exercises the L2I check's negative leg**: that needs an
   authored `.uasset` BP pawn with no mesh, which is not written yet.

## Hidden invariants

- All hidden invariants of `gp-glide-stamina-cpp` apply unchanged (resource-gated
  slow, same-run free-fall baseline, verifier-owned possession, the tag as the
  trigger contract).
- **BP resolution is Asset-Registry-based**: the fixture only discovers
  Blueprint pawns saved under `/Game/Tasks/` — a BP saved elsewhere (e.g.
  `Content/Blueprints/`) is sandbox-accepted but never resolved, and fails L2.
- The map has no GameModeOverride, so PIE also spawns the substrate's default
  `BP_ThirdPersonGameMode` pawn at the PlayerStart. It is not a
  `ACraftBenchCharacter` subclass, so it can never win pawn resolution and no
  gate reads it — the graded pawn is exclusively the one the fixture spawns.
