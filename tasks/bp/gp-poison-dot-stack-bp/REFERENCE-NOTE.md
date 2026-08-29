# gp-poison-dot-stack-bp — reference solution (binary .uasset, editor-authored)

> **✅ RE-AUTHORING RESOLVED 2026-08-06 at `dfee504` — both stacked 2026-08-05
> changes are BUILT, and no editor session was needed.** Commit `dfee504`
> ("headless port of the -bp reference assets — all four glide/poison gates
> green at HEAD") ported the assets with copy + scratch-only CoreRedirects +
> editor-Python CDO surgery + resave. Verdict recorded there: reference
> **overall PASS** (stage 1 + Legs A/C/D green, L2I 4/4), and the NEW
> `discrimination/bp-no-health-system/` variant **FAIL** at the named stage-1
> presence gate.
>
> **Do NOT budget an editor session for this reference.** Both handoffs —
> an internal working note (not shipped) and
> an internal working note (not shipped) — are
> spent; read them as history only.
>
> Re-verified on disk 2026-08-08: **four** `.uasset`s are committed
> (`BP_PoisonPawn`, `DT_HealthInit`, `GA_Poison`, `GE_Poison`), **zero**
> `/Script/CraftBenchTemplate` bytes remain in any of them, and `BP_PoisonPawn`
> carries `CraftBenchBareCharacter` + `DefaultStartingData` + `DT_HealthInit` +
> `CraftBenchAttributeSet` + `SKM_Manny_Simple` — stage 1 built, character
> visible.
>
> _History (the two changes this banner used to gate on):_
> (1) **Substrate migration** — the assets were authored against
> **CraftBenchTemplate** (`BP_PoisonPawn` reparented to
> `/Script/CraftBenchTemplate.CraftBenchCharacter`, `GE_Poison` bound
> `CraftBenchTemplate.CraftBenchAttributeSet.Health`) and did not resolve in
> the ThirdPerson project; the port re-pointed them.
> (2) **Health-first restructure (redefinition epoch)** — stage 1, building the
> health system, is the agent's work, so the reference had to demonstrate it:
> parent is `/Script/ThirdPerson.CraftBenchBareCharacter` (the abstract
> ASC-only task base — NOT the generic `CraftBenchCharacter`, which the stage-1
> derivation gate rejects), attribute binding
> `ThirdPerson.CraftBenchAttributeSet.Health`. Results before/after 2026-08-05
> are still not comparable. Everything below the stage-1 section describes the
> pre-migration, pre-epoch CraftBenchTemplate build (still the stage-2 recipe
> to follow).

**Status: AUTHORED + VALIDATED 2026-07-17 (on CraftBenchTemplate, pre-epoch);
RE-AUTHORED + RE-VALIDATED ON ThirdPerson 2026-08-06 at `dfee504`.** The
reference lives at `reference/Content/Tasks/gp-poison-dot-stack-bp/` — now
**4** `.uasset`s (the stage-1 `DT_HealthInit` is the fourth). Pre-epoch
validation: `cb discriminate --task gp-poison-dot-stack-bp` = reference
**PASS**, empty **FAIL**, cpp-solve **FAIL** at the named L2I check
(`bp_pawn_present`); post-epoch verdict is the `dfee504` overall PASS above.

## Stage-1 wiring route (the no-C++ lane) — CONFIRMED 2026-08-06

Stage 1 must register the provided `CraftBenchAttributeSet` on the task base's
inherited AbilitySystemComponent and initialize `Health = 100`, entirely in
the editor. The canonical route:

- **`DefaultStartingData` on the inherited ASC** — `UAbilitySystemComponent`
  exposes `DefaultStartingData: TArray<FAttributeDefaults>` (each entry: an
  `Attributes` set class + an optional `DefaultStartingTable` DataTable of
  `AttributeMetaData` rows). Set it in the BP pawn's class defaults by
  selecting the inherited AbilitySystemComponent in the Components panel:
  add one entry with `Attributes = CraftBenchAttributeSet` and a
  `DT_HealthInit` DataTable (row `Health`, BaseValue 100; save it in the task
  folder). The engine consumes the array at component initialization,
  creating + registering the set instance and applying the table values — no
  C++.
- **Verification status: CONFIRMED EMPIRICALLY on UE 5.8, 2026-08-06 at
  `dfee504`** (this note previously said "no in-repo evidence exists" and
  scheduled the check as step B0 of an editor session — that check ran, and it
  ran headlessly). `DefaultStartingData` **does** register the attribute set on
  5.8: the ported pawn read `Health = 100` before any fixture write (stage-1
  gate (c)) and passed the `37 ≠ 100` write probe (gate (d)). The shipped wiring
  is exactly this route — `DefaultStartingData` on the inherited ASC pointing at
  a NEW `DT_HealthInit` `AttributeMetaData` table (`Health`/`MaxHealth` = 100).
  Both are readable in the committed binary (byte-verified 2026-08-08).
  The **fallback** below was therefore never needed, and is kept only as an
  alternative for agents: wire + initialize via any other editor-visible route —
  e.g. an instant "init" GameplayEffect (Override Health = 100) applied from the
  pawn BP at BeginPlay. The task spec deliberately words stage 1 as "an
  editor-visible route" (observable contract, agent's choice), so a solution
  that picks the fallback is equally conforming.
- **Prior confidence note (2026-08-05, superseded by the line above):** the
  property and `FAttributeDefaults` shape are long-standing engine API (HIGH
  confidence they exist and are editor-visible on the inherited component);
  consumption timing at component init on **UE 5.8 specifically** was rated
  MEDIUM-HIGH. That rating is now moot.
- **DataTable row-name contract (load-bearing):** rows must be named
  `<OwnerClass>.<Property>`, not bare `Health` — `InitFromMetaDataTable` keys
  them that way (`AttributeSet.cpp:448`), and a bare name reads back as
  "registered but never initialized". Byte-verified in the committed
  `DT_HealthInit` 2026-08-08: row struct `AttributeMetaData`, rows
  `CraftBenchAttributeSet.Health` and `CraftBenchAttributeSet.MaxHealth`.
- The subobject-name suppression on the bare lineage does NOT affect this
  route: `DefaultStartingData` sets are created at runtime component init,
  not through the construction-phase `FObjectInitializer` (only the ctor-time
  `"AttributeSet"` default subobject name is suppressed).

## As-built assets (pre-epoch: 3; post-port: 4, `DT_HealthInit` added) — the MMC is replaced by a 5.8-native flag

The C++ reference used to ship `PoisonDamageMMC` (`-5 × stackCount`) on the
belief that stock GAS did not scale periodic magnitudes by stack count.
**Measured false on UE 5.8 (2026-08-06)**: the engine multiplied the MMC's
result by the stack count AGAIN, draining −5×stacks² — 4 applications read
exactly **9.00×** the single-stack rate on the Leg C/D fixture, failing the
new cap gate. The C++ reference (and every C++ variant copy) dropped the MMC
at that epoch and now uses this same recipe. **UE 5.8 scales it natively**:
`UGameplayEffect::bFactorInStackCount` (default **true** in the 5.8
constructor, `GameplayEffect.cpp:195`) routes periodic executions through
`ComputeStackedModifierMagnitude(magnitude, GetStackCount(), op)`
(`GameplayEffect.cpp:2025-2028`). So the BP reference ships a plain `-5.0`
scalable-float modifier and no MMC — 3 stacks ⇒ −15 Health/tick, identical
observable behavior, and the L2 stack-ratio gate (≥2.0× the 1-stack rate)
passes on it.

1. **GE_Poison** — Blueprint of `GameplayEffect`:
   - Duration Policy `Has Duration`, Duration Magnitude `5.0`
   - Period `1.0`, **Execute Periodic Effect on Application: OFF**
     (`bExecutePeriodicEffectOnApplication = false` — first damage lands one
     period AFTER application; the fixture calibration depends on this)
   - Modifier: `CraftBenchAttributeSet.Health`, op Add (`ADD_BASE` in 5.8),
     magnitude ScalableFloat **-5.0**; `bFactorInStackCount = true`
   - Stacking: `Aggregate by Target`, Stack Limit Count `3`,
     Duration Refresh Policy `Refresh on Successful Application`,
     Period Reset Policy `Reset on Successful Application`
     — **as of the 2026-08-06 Leg C/D epoch the stack cap and duration
     refresh are GATED** (Leg C re-applies mid-window and asserts the drain
     continues past the original expiry band then stops; Leg D bounds the
     4-application ratio at ≤ 3.5×, uncapped measures 4.00×), so these
     stacking settings are no longer optional polish — they are the tested
     contract. The C++ reference GE (this exact config) graded PASS through
     all gates 2026-08-06.
2. **GA_Poison** — Blueprint of `GameplayAbility`: InstancedPerActor, ability
   tags = `Ability.Poison` (5.8 property name `ability_tags`). Graph:
   ActivateAbility → Commit Ability → (fail → End Ability) / (success →
   `Apply Gameplay Effect to Owner` (GE_Poison, level 1) → End Ability).
   Each activation = one new application/stack; the ability holds no state.
3. **BP_PoisonPawn** — post-epoch: Blueprint of `CraftBenchBareCharacter`
   (was `CraftBenchCharacter`): class defaults `GrantedAbilities =
   [GA_Poison]` **plus the stage-1 wiring** (see the route section above —
   adds `DT_HealthInit` as asset 4) **plus the mesh** `SKM_Manny_Simple`, which
   the checkpoint-0 visibility gate (stage-1 gate (e), added 2026-08-06)
   requires. No event graph on the happy path.
4. **DT_HealthInit** (NEW at `dfee504`) — an `AttributeMetaData` DataTable with
   rows `CraftBenchAttributeSet.Health` and `CraftBenchAttributeSet.MaxHealth`,
   both BaseValue 100, referenced from the pawn's inherited-ASC
   `DefaultStartingData`. This is the whole of stage 1 on the no-C++ lane.

Asset names are free — the verifier resolves by derivation + tag, never by name.

## Re-validate (post-epoch)

```sh
$env:CB_UE_ROOT='F:\Games\UE_5.8'
.\tools\run-agent\cb.cmd discriminate --task gp-poison-dot-stack-bp --wip
```

Expected: reference PASS (stage-1 gate + Legs A, C, B/D — the 2026-08-06
epoch added the refresh + cap gates); empty FAIL at the stage-1
**derivation** gate (message changed at the epoch — see
`discrimination/MATRIX.md`); cpp-solve/ FAIL at the named L2I check
(`"bp_pawn_present", "passed": false`); cpp-solve-with-bp/ FAIL at
`resolved_pawn_is_blueprint`; bp-no-health-system/ FAIL at the stage-1
**presence** gate; bp-no-refresh/ + bp-no-cap/ (still unauthored — see
`discrimination/MATRIX.md`) FAIL at the Leg C / Leg D named gates
respectively.

> **Measured 2026-08-06 at `dfee504`:** reference **overall PASS** and
> `bp-no-health-system/` **FAIL at the named presence gate**. `--wip` is no
> longer required for those two — the assets are committed, so they grade from
> git HEAD. The two remaining `bp-no-*` rows are still unbuilt, and building
> them no longer needs an editor: `dfee504`'s headless recipe (copy +
> scratch-only CoreRedirects + editor-Python CDO surgery + resave) is the lane.
