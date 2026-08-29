---
id: gp-glide-stamina-cpp
substrate: ThirdPerson
set: cpp
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_GlideStamina :: AGlideStaminaFunctionalTest"]
---

# gp-glide-stamina-cpp

Port of the **g2-10 "Movement/Glide"** eval prompt, running on the UE 5.8
**ThirdPerson** substrate (originally ported onto the UE 5.7
CraftBenchTemplate substrate; migrated 2026-08-06 — see the substrate epoch
note below). Probes a GAS ability that modifies fall physics
while draining a resource: an ability that, while the character is falling,
slows the descent and steadily drains a stamina resource, and ends the slowed
descent when the resource is exhausted.

> **⚠ SUBSTRATE EPOCH 2026-08-06 evening (ThirdPerson migration; owner
> decision 2026-08-06, completing the uniform substrate policy).** This task
> now runs on the `UE-projects/ThirdPerson/` substrate — the stock UE 5.8
> Third Person C++ template — joining its Blueprint twin
> `gp-glide-stamina-bp` (migrated 2026-08-05). C++ and BP are equal-status
> deliverables, so the pair grades on the same substrate, map, and fixture:
> the `AGlideStaminaFunctionalTest` fixture
> (`Source/CraftBenchTests/Tasks/gp-glide-stamina-bp/`, shared by both
> tasks), the `L_GlideStamina` map, and the GAS scaffold were all ported
> verbatim by the twin's migration; this migration re-homed only the spec and
> the reference overlay (`Source/CraftBenchTemplate/` → `Source/ThirdPerson/`,
> byte-identical files — no gate changed). **Results recorded before and
> after this flip are not comparable** (substrate change — same convention as
> the calibration correction below). One deliberate delta the flip brings:
> **ThirdPerson config-disables Live Coding**
> (`Config/DefaultEditorPerProjectUserSettings.ini`), so the in-editor
> self-build lane CraftBenchTemplate still exposes does not exist here — the
> evening this decision landed, an editor-driven C++ bench on
> CraftBenchTemplate lost both sonnet-5 reps to EDITOR-GONE mid-drive, both
> after `trigger_live_coding`/`recompile_unreal_project` use. An agent-side
> compile was always verdict-irrelevant by design; the verifier's post-drive
> L1 is the only compile that scores.

> **⚠ GATE EPOCH 2026-08-09 (owner decision). Results before and after are NOT
> comparable.** Two gates that the prompt always asked for but nothing ever
> checked are now asserted, on both variants (the fixture is shared):
> (1) **stop-on-exhaustion is UNCONDITIONAL** — at checkpoint 6 the verifier
> zeroes Power itself once the submission has proven its own drain, so gate (5)
> no longer depends on a drain rate the submission chooses. Previously 1 of 4
> `-cpp` PASSes never asserted it. (2) **the pawn must START with Power** —
> checked pre-trigger, before the verifier's own `PowerPreset` overwrites the
> value. Both are backed by new discrimination variants (`slow-no-stop/`,
> `no-power/`), and both can newly FAIL work that previously passed. Rationale
> and the measurements behind them: `discrimination/MATRIX.md` notes 7-8 and
> the internal design note (not shipped).

> **⚠ RENAME + VISIBILITY EPOCH 2026-08-06 (owner decision 2026-08-06).**
> Two changes landed together. (1) **Rename**: this task's id changed
> `gp-glide-stamina` → **`gp-glide-stamina-cpp`**, so all four glide/poison
> tasks are surface-differentiated by suffix (`-cpp` C++ original, `-bp`
> Blueprint variant; the set stays `bp-g2` — set = source-sheet provenance).
> The rename also dissolves the documented prefix-shape id violation
> (`gp-glide-stamina` was a raw substring of `gp-glide-stamina-bp`, blinding
> the CATALOG substring membership check — see the repo conventions). (2) **Visible
> character became a gate**: the prompt now requires the character to be
> visibly represented, and the shared fixture enforces it structurally — at
> checkpoint 0 the graded pawn must carry a skeletal/static mesh component
> with a mesh actually assigned, else the named FAIL "the character is not
> visibly represented: no mesh component with an assigned mesh on the graded
> pawn". This mirrors the `-bp` variant's L2I `pawn_visibly_represented` gate
> (both variants share the fixture, so both get it; the `-bp` L2I already
> demanded it) and exists because this task's film strips showed an empty
> scene — a meshless-but-conforming pawn was ungradable by a human reviewer.
> **Results recorded under the old id, or before the visibility gate, are not
> comparable with results after it.**

> GAS-category note: like the retired `gp-flight-mode` / `gp-gas-launch`
> (git history), this task names the GAS contract (an ability tagged
> `Ability.Glide`, granted to the provided ability-system pawn; the stamina
> resource is the pawn's `Power` attribute) as part of the interface — a
> deliberate, documented exception to behavior-only prompts, because
> verifying the behavior *through GAS* is the point.

> Tier-B scope note: the original g2-10 gates the glide on **holding spacebar in
> the air after the jump apex**. Headless PIE injects no player input, so the
> verifier instead fires `Ability.Glide` by tag while the pawn is already
> falling. This port therefore verifies the *mechanical core* — slowed descent
> while active, stamina drain, and stop-on-exhaustion — **not** the
> spacebar/apex input-gating, which is dropped (see Anti-gaming).

## Primary concept

- `gas-overview` + `ps-character-movement` — a GAS ability modifying
  CharacterMovement fall physics while consuming an attribute
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-ability-system-for-unreal-engine)

The load-bearing behavior is an activated ability that (a) reduces the
character's descent rate *while falling* and (b) drains the `Power` attribute
over time, ending the slow-fall when `Power` hits 0. The hard part: the slowed
descent must be produced by the *active, resource-gated ability* — not a
permanent fall-speed change, not a teleport, and not a glide that ignores the
resource.

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
> - Deliver your pawn as a subclass of the provided character (C++ or Blueprint)
>   with your ability granted on it, starting with some Power to spend.
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

Files that **exist** under `Source/ThirdPerson/` (this substrate's
agent-writable runtime module):

- The stock UE 5.8 Third Person C++ template sources (`ThirdPersonCharacter`,
  game mode, the Variant_* trees). No edit needed.
- `ThirdPerson.Build.cs` — already includes `GameplayAbilities`,
  `GameplayTags`, `GameplayTasks`. No edit needed.
- `CraftBenchCharacter.{h,cpp}` — `ACharacter` + `IAbilitySystemInterface` with a
  pawn-owned ASC, a minimal attribute set (`Health`, `MaxHealth`, `Power`), an
  auto-granted `GrantedAbilities` array (ships empty), and the `CraftBenchPawn`
  tag. `Power` is the stamina resource for this task.
- `CraftBenchGameplayTags.{h,cpp}` — registers `Ability.Glide`
  (`FCraftBenchGameplayTags::AbilityGlide()`).
- The `GameplayAbilities` plugin is enabled.
- `AGlideStaminaFunctionalTest` lives in the verifier-only `CraftBenchTests`
  module (`Source/CraftBenchTests/Tasks/gp-glide-stamina-bp/` — the fixture
  is shared with the Blueprint twin, byte-identical gates. The folder KEEPS
  the twin's `-bp` name after this task's 2026-08-06 `-cpp` rename: it is a
  folder name, not a task id — do not "fix" it to `-cpp`).
- `Content/Characters/Mannequins/` — the substrate's **native**
  visual-representation content (SKM_Manny_Simple / SKM_Quinn_Simple, the
  SK_Mannequin skeleton). Read-only: `Content/Characters/` is outside the
  writable sandbox; the prompt's visible-character bullet points here.

Files the agent **creates**: a `UGameplayAbility` (C++ or Blueprint) tagged
`Ability.Glide` that slows the fall + drains `Power` + stops at zero, and a
subclass of `ACraftBenchCharacter` whose `GrantedAbilities` contains it (and
which starts with Power to spend). The pawn is resolved by derivation (the
verifier scans Blueprint assets under `/Game/Tasks` via the Asset Registry) and
spawned + possessed by the verifier.

> **A Blueprint pawn saved anywhere else is invisible to that scan, and the run
> then grades the base class.** The preamble lists several writable asset roots
> --- `Content/Blueprints/`, `Content/Abilities/`, `Content/Generated_Materials/`
> and more --- and every one of them is legal to write but OUTSIDE the resolver's
> `/Game/Tasks` scope. A Blueprint-route submission that puts its pawn under
> `Content/Abilities/`, which is the natural place for an ability pawn, falls
> back to `ACraftBenchCharacter` with an empty `GrantedAbilities` and FAILs at
> `granted=0` --- a spec failure scored as a model failure, and one that lands
> only on the Blueprint route. The `-bp` twin has always disclosed the scope in
> this sentence; this surface dropped it. Restored 2026-08-26.

## Verifier specification

The pawn is spawned high and allowed to free-fall briefly (establishing a fast
descent in the Falling movement mode); the verifier then presets `Power` to a
known small value and fires `Ability.Glide` by tag, and samples vertical
velocity + `Power` over the schedule. All thresholds marked `«calibrate»` are
pinned empirically from the reference run by `/craftbench-build-verifier`.

```text
PrepareTest():
    PawnSpawnLocation = (0, 0, «calibrate: high, e.g. 4000»)
    Super::PrepareTest()                       // resolve + spawn + SpawnDefaultController
    SetCheckpointSchedule({ 0.5, 1.0, 1.5, 1.9, 2.3, 2.7, 3.1, 3.6, 4.1 })
    // 3.6 + 4.1 appended 2026-08-06 (calibration correction, see below): the old
    // 3.1s tail gave a conforming-but-slow drain that emptied Power at the last
    // checkpoint a 0.00s post-exhaustion window. TimeLimit auto-extends.

OnCheckpoint:
    every idx : RecordSample (location, velocity, MovementMode); read Power = GetNumericAttribute(Power)
    idx 0     : assert a skeletal/static mesh component with an assigned mesh exists on the
                graded pawn — else the named FAIL "the character is not visibly represented:
                no mesh component with an assigned mesh on the graded pawn" (2026-08-06)
    idx 0     : assert MovementMode == MOVE_Falling; FreeFallVZ = |vZ|   // fast unaided descent baseline
    trigger idx (after a free-fall sample):
                ASC->SetNumericAttributeBase(Power, «calibrate: small preset, e.g. 30»)
                TriggerAbilityByTag(Ability.Glide); record PowerAtTrigger
    a "gliding" idx (Power still > 0):
                assert |vZ| <= «calibrate: GlideVZMax»  AND  |vZ| <= 0.6 * FreeFallVZ   // slowed
                assert Power < PowerAtTrigger                                            // draining
    last idx (after enough time for Power to reach 0):
        assert (1) NumGrantedAbilitiesWithTag(Ability.Glide) >= 1     // GAS implemented
        assert (2) ability activated on the tag-trigger
        assert (3) min |vZ| among gliding samples <= 0.6 * FreeFallVZ // descent was slowed (load-bearing)
        assert (4) Power reached ~0 (<= «calibrate: epsilon»)         // stamina drained to empty
        assert (5) slow-fall STOPPED once Power hit 0 — CONDITIONAL, two-path, and
                   window-honest: asserted only if Power emptied in-window AND the
                   post-exhaustion observation window >= WindowFloor (0.30s); else
                   SKIPPED, not failed. Passes on EITHER |vZ| >= «calibrate: ResumeVZ»
                   (the fast path) OR |vZ| >= 1.5x the same run's min glide speed
                   (the ratio fallback)
```

**Pass criteria**: the pawn is visibly represented (checkpoint-0 mesh gate),
carries an activatable `Ability.Glide`, it activates,
the descent is slowed while Power remains, Power drains to zero, and the descent
then speeds back up. **(3) and (5) are the load-bearing pair**: (3) fails a
no-slow / teleport fake; (5) fails a glide that ignores the resource and slows
forever — but (5) may hard-FAIL only when the fixture actually had room to
measure the resume (post-exhaustion window >= the 0.30s floor); with less room
it is SKIPPED, not failed, on the same semantics as "Power never emptied
in-window".

> Calibration note: if the stop-on-exhaustion leg (4)+(5) proves agent-drain-rate
> sensitive and cannot be pinned cleanly, the build-verifier will relax it to an
> advisory observation and keep (1)–(3) + "Power strictly drained while gliding"
> as the deterministic gate (Tier-B, relabeled). The reference's drain rate +
> the preset + schedule are tuned so (4)+(5) fire for the reference.

> **Calibration correction (2026-08-06).** The original 7-checkpoint schedule
> (…, 3.1) gave a conforming-but-slower-than-reference drain that emptied Power
> at exactly the last checkpoint a **0.00s** post-exhaustion window, where the
> 1.5x resume-ratio fallback reads 1.33–1.49x on correct work — **4 measured
> near-miss FAILs across both substrates** (3 reps of `bench-20260806-023946`,
> |vZ|=298 vs a 300 bar; the build machine's glide-bp opus rep 2 at 1.33x). Two fixes,
> applied identically to this task and `gp-glide-stamina-bp`: (a) two
> checkpoints appended (**3.6, 4.1**) so a drain that empties by ~3.6s keeps a
> >=0.5s window (the reference now gets ~1.4s); (b) gate (5) is **window-honest**
> — it may hard-FAIL only when the post-exhaustion window is >= the **0.30s**
> `WindowFloor` (comfortably under the reference's measured 0.40s); below the
> floor it routes to the existing SKIPPED-not-failed semantics, since gates
> (3)+(4) already proved glide+drain and no static schedule can eliminate the
> final-gap boundary zone.

## Reference solution metadata

- LOC range: 40–80 LOC (a `UGameplayAbility`: tag in ctor, `ActivateAbility`
  applies a reduced-fall mechanism — e.g. lower `GravityScale`/cap fall velocity —
  starts a periodic Power drain via timer, and on Power<=0 restores normal fall +
  `EndAbility`; a pawn subclass granting it + initializing Power, and — since the
  2026-08-06 visibility gate — constructor-assigning the template's mannequin
  mesh via a guarded `ConstructorHelpers::FObjectFinder`, same pattern as the
  substrate's `AFireCharacter`).
- Files touched: 4 new (`GlideAbility.{h,cpp}`, `GlidePawn.{h,cpp}`).
- Senior-dev hours: 45–90 minutes.
- A Blueprint reference (BP ability + BP pawn) is the equivalent deliverable; the
  verifier resolves a BP pawn via the asset registry (proven on the retired
  `gp-gas-launch` — git history).

## Anti-gaming notes

1. **No GAS (slow the fall without an ability).** *Failure mode*: a pawn that
   just sets a low `GravityScale` permanently, no ability. *Defense*: (1)
   `NumGrantedAbilitiesWithTag(Ability.Glide) >= 1` reads the ASC; (2) requires
   the tag-trigger to activate something. *Measured*: `discrimination/no-gas/`
   FAILs by name (`granted=0`), 2026-08-08.
2. **Teleport / no actual slow.** *Failure mode*: the ability fires but descent
   speed is unchanged (or it nudges position). *Defense*: (3) requires the
   gliding descent to be ≤ 0.6× the measured free-fall speed. *Measured*:
   `discrimination/no-slow/` FAILs by name at `min glide |vZ|=1601 > 725`,
   2026-08-08.
3. **Never drains stamina (free glide).** *Failure mode*: descent slows but Power
   never decreases. *Defense*: the "draining" assertion (`Power < PowerAtTrigger`)
   and (4) (`Power` reaches ~0) fail. *Measured*: `discrimination/no-drain/`
   FAILs by name, 2026-08-08.
4. **Glide forever, ignore stamina.** *Failure mode*: the slow-fall continues
   after Power is gone. *Defense*: (5) requires `|vZ|` to speed back up once
   Power hits 0; a never-stopping glide stays slow and fails (5). *Measured*:
   `discrimination/no-stop/` FAILs by name in a 1.40s window, 2026-08-08.
5. **Permanent fall-speed change (not resource-gated/active).** *Failure mode*:
   the agent lowers fall speed globally so it's slow before *and* after the
   resource is gone. *Defense*: the verifier presets a small Power and (5) checks
   the descent returns to fast once Power==0; a permanent change never speeds up.
   *Defense proven by inheritance*: a dedicated overlay would be byte-equivalent
   to `discrimination/no-stop/` (both present a descent that never re-accelerates
   after exhaustion, and both die at gate (5)), so this note is covered by that
   measured variant rather than a duplicate one — see
   `discrimination/MATRIX.md`.
6. **Invisible deliverable (skip the visual entirely).** *Failure mode*: a
   behaviorally-correct pawn with no mesh — MEASURED 2026-08-04 on the `-bp`
   twin: all 9 matrix reps shipped meshless pawns, and human review was only
   possible by instrumenting copies with a debug cube; this task's own film
   strips showed an empty scene. *Defense* (2026-08-06): the checkpoint-0
   **visible-character fixture gate** — the graded pawn must carry a
   skeletal/static mesh component with a mesh actually assigned, else the
   named FAIL "the character is not visibly represented". Structural and
   deterministic; the fixture-level twin of the `-bp` variant's L2I
   `pawn_visibly_represented` check. *Measured*: `discrimination/no-mesh/`
   FAILs by name, 2026-08-08 — though note it shares its substring with the
   `empty` leg (checkpoint 0 runs before the ability check), so it proves the
   gate is reachable rather than isolating a distinct axis.
7. **Drain so slowly that Power never empties — then never implement the stop.**
   *Failure mode*: the glide clamps the descent and does decrease Power, but at a
   rate that cannot empty it inside the measurement window, so the
   stop-on-exhaustion requirement is never exercised and need not be implemented
   at all. **This was a LIVE HOLE for the whole life of the task**: both of gate
   (5)'s skip paths key on "did Power empty in-window", and *the drain rate is
   chosen by the submission*. Measured 2026-08-09 across the six `-cpp` runs on
   disk: **1 of 4 PASSes never asserted the requirement** (opus-5
   `20260809-012802`, `minpower=4.2`, `gate (5) SKIPPED`) — so two PASSes on this
   task were not the same claim. *Defense* (2026-08-09): at checkpoint 6 the
   verifier **zeroes Power itself**, once the submission has already proven its
   own drain, so gate (5) is measured in a window the VERIFIER chose. Monotone by
   construction — it cannot fire on a submission that never drained, and the
   reference (30/s, empties a full checkpoint earlier) never reaches it.
   *Measured*: `discrimination/slow-no-stop/` FAILs by name — `forced=1`,
   `exhausted_at=3.60s window=0.50s mean_accel=0`, final `|vZ|=182` = 1.00× the
   glide speed against a 1.5× bar.
8. **Ship a pawn that never seeds the resource and let the verifier's preset
   supply it.** *Failure mode*: the prompt asks for a pawn "starting with some
   Power to spend", but the fixture **overwrites** Power at the trigger
   (`PowerPreset`), so a pawn that starts at 0 glided and drained exactly like a
   compliant one. Nothing asserted the clause. Not a hypothetical gap: the
   attribute has no initializer and the base character never seeds it, so the
   scaffold pawn really does start at 0. *Defense* (2026-08-09): a **checkpoint-1
   pre-trigger gate** — `Power > 0` before the glide, else the named FAIL "the
   pawn does not start with any Power to spend". The preset stays, because it
   normalizes the drain measurement; the gate is about the resource existing, a
   different question. *Measured*: `discrimination/no-power/` — the reference
   minus its one seeding call — FAILs by name.

## Hidden invariants

- **The slow is resource-gated, not permanent.** (5) (speed-up after Power==0) is
  what separates a real, stamina-consuming glide from a permanent low-gravity
  pawn that also "descends slowly."
- **The descent must actually be slow while active**, measured against the *same
  run's* free-fall baseline (not an absolute number), so a heavy/light pawn can't
  skew it.
- **Possession is verifier-owned** (`SpawnDefaultController`); CMC will not tick
  on an unpossessed pawn.
- **The tag is the trigger contract** (`Ability.Glide`); an ability without that
  asset tag is never activated. The spacebar/apex input-gating of the original
  prompt is NOT verified (headless has no input).
- The map (`Content/Maps/L_GlideStamina.umap`) has no GameModeOverride, so PIE
  also spawns the substrate's default `BP_ThirdPersonGameMode` pawn at the
  PlayerStart. It is not an `ACraftBenchCharacter` subclass, so it can never
  win pawn resolution and no gate reads it — the graded pawn is exclusively
  the one the fixture spawns.
