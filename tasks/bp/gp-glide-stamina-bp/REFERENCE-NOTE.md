# gp-glide-stamina-bp — reference solution (binary .uasset, editor-authored)

> **✅ SUBSTRATE MIGRATION 2026-08-05 — RE-AUTHORING RESOLVED 2026-08-06 at
> `dfee504`.** The re-authoring HAPPENED, and it happened **headlessly** —
> commit `dfee504` ("headless port of the -bp reference assets — all four
> glide/poison gates green at HEAD"): copy + scratch-only CoreRedirects +
> editor-Python CDO surgery + resave, **no live editor session at any point**.
> The four committed `.uasset`s are now ThirdPerson-bound. Verdict recorded at
> `dfee504`: reference **overall PASS**, L2I **5/5** including
> `pawn_visibly_represented` via the native `SKM_Manny_Simple`; re-confirmed
> 2026-08-07 by a token-free `cb refgate` **PASS (1/1, 154 s)** at repo
> `61e4c98` before the 9-rep model matrix
> (an internal eval report (not shipped)).
>
> **Do NOT budget an editor session for this reference.** The handoff
> an internal working note (not shipped) is spent; read it as
> history only.
>
> Re-verified on disk 2026-08-08 (byte scan of all four assets): **zero**
> `/Script/CraftBenchTemplate` bytes remain; `BP_GlidePawn` carries
> `ThirdPerson` class paths, `CraftBenchCharacter`, and `SKM_Manny_Simple`.
>
> _History (the superseded warning this banner replaces):_ the four assets were
> originally authored against **CraftBenchTemplate** — `BP_GlidePawn`
> reparented to `/Script/CraftBenchTemplate.CraftBenchCharacter`,
> `GE_GlideDrain`/`GE_InitPower` bound
> `CraftBenchTemplate.CraftBenchAttributeSet.Power` — none of which resolve in
> the ThirdPerson project. The port re-pointed them to
> `/Script/ThirdPerson.CraftBenchCharacter` /
> `ThirdPerson.CraftBenchAttributeSet.Power` and assigned the mannequin mesh
> the `pawn_visibly_represented` L2I check requires. Everything below this note
> still describes the pre-migration CraftBenchTemplate build; the recipe
> transferred unchanged.

**Status: AUTHORED + VALIDATED 2026-07-17 (on CraftBenchTemplate);
RE-VALIDATED ON ThirdPerson 2026-08-06 at `dfee504`.** The reference lives at
`reference/Content/Tasks/gp-glide-stamina-bp/` (4 `.uasset`s). It was authored
in a live UE 5.8 editor via Aura's MCP tools (Claude driving
`create_assets` / editor-Python CDO config / `bp_agent` graph building), then
promoted here and deleted from the substrate; the 2026-08-06 substrate port was
headless (see the banner). Original validation:
`cb discriminate --task gp-glide-stamina-bp` = reference **PASS**, empty
**FAIL**, cpp-solve **FAIL** at the named L2I check (`bp_pawn_present`).

## As-built assets (4) — mirrors `gp-glide-stamina-cpp`'s C++ reference behavior

The C++ reference's mechanism (`GlideAbility.cpp`: velocity clamp on a 0.1 s
looping timer + `SetNumericAttributeBase` Power drain) survives intact, with
two **BP-native adaptations** — `UAbilitySystemComponent::
SetNumericAttributeBase` is NOT BlueprintCallable in stock UE 5.8, so attribute
writes go through instant GameplayEffects instead:

1. **GA_Glide** — Blueprint of `GameplayAbility`. InstancedPerActor; ability
   tags = `Ability.Glide` (NB the 5.8 Python/editor property is
   `ability_tags`; `asset_tags` does not exist on abilities). Event graph:
   - ActivateAbility → Commit Ability → (fail → End Ability) / (success →
     `Set Timer by Event`, 0.1 s, looping → handle stored in `GlideTimerHandle`).
     No End Ability on the success path — the timer event ends it.
   - `GlideTick` (timer event): clamp descent (if CharacterMovement
     `Velocity.Z < -100` set it to `-100`) → `Apply Gameplay Effect to Owner`
     (**GE_GlideDrain**) → `Get Float Attribute` (Power) → if `<= 0` →
     End Ability.
   - OnEndAbility → `Clear and Invalidate Timer by Handle` (covers every end
     path, mirroring the C++ `EndAbility` override).
2. **GE_GlideDrain** — instant GE, `CraftBenchAttributeSet.Power` Add **-3.0**
   (the C++ `DrainPerTick`; at 10 Hz = 30 Power/s — the fixture's ~30 preset
   empties in ~1 s). Instant GEs write the attribute BASE, so this is exactly
   the `SetNumericAttributeBase(current - 3)` of the C++ version. No max(0,·)
   clamp is needed: the fixture's exhaustion gate is `MinPowerSeen <=
   PowerEpsilon(0.5)`, so a slightly-negative overshoot still counts.
3. **GE_InitPower** — instant GE, Power Override **100.0**.
4. **BP_GlidePawn** — Blueprint of `CraftBenchCharacter`; class defaults
   `GrantedAbilities = [GA_Glide]`; BeginPlay → ASC → Make Effect Context →
   Apply Gameplay Effect to Self (**GE_InitPower**) — the C++ `BeginPlay`
   Power=100 init ("starting with some Power to spend" per the prompt).

Asset names are free — the verifier resolves by derivation + tag, never by name.

## UE 5.8 authoring gotchas hit (for the next asset-authoring session)

- `EGameplayModOp` Python entries renamed: Additive is `ADD_BASE` (T3D
  `import_text` string tokens like `Additive` also resolve).
- `GameplayTagLibrary.request_gameplay_tag` / `GameplayTagContainer.to_string`
  don't exist in 5.8 Python — use `GameplayTag.import_text` +
  `GameplayTagLibrary.add_gameplay_tag`, read back via the `gameplay_tags`
  array property.
- **Grading and an open interactive editor cannot coexist**: Live Coding's
  machine-global mutex makes UBT refuse ALL builds (L1 exit 6, `Unable to
  build while Live Coding is active`). Save → verify zero dirty packages →
  close the editor → then run the verifier. See the internal failure log (not shipped)
  2026-07-17.

## Re-validate

```sh
$env:CB_UE_ROOT='F:\Games\UE_5.8'
.\tools\run-agent\cb.cmd discriminate --task gp-glide-stamina-bp
```

Expected: reference PASS; empty FAIL (`granted=0`); cpp-solve/ FAIL at the
named L2I check (`"bp_pawn_present", "passed": false`).
