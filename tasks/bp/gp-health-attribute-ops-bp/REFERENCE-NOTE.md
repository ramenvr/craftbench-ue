# gp-health-attribute-ops-bp — reference solution (binary .uasset, editor-authored)

**Status: AUTHORED + GRADED PASS 2026-08-11, from git HEAD.** L2
`Result={Success}` + L2I **5/5**; verdict evidence: `init=100.0` (the
DataTable + DefaultStartingData stage-1 route), `activatedDamage=2
activatedHeal=1`, `drop1=10.00 drop2=10.00 heal=10.00 repeatRatio=1.00
symRatio=1.00 writeProbe=37.0` (Band-A floor live). Report: the 2026-08-11
session's `horef-report.json`.

Reference at `reference/Content/Tasks/gp-health-attribute-ops-bp/`
(6 `.uasset`s), natively ThirdPerson-bound — zero template bytes, no port.

## As-built (6 assets) — spec in `notes.md`

1. **DT_HealthInit** — DataTable of `AttributeMetaData`; rows
   `CraftBenchAttributeSet.Health`=100, `CraftBenchAttributeSet.MaxHealth`=100.
   The `<OwnerClass>.<Property>` row-name contract is load-bearing
   (`InitFromMetaDataTable` keys rows that way).
2. **BP_HealthOpsPawn** — parent `CraftBenchBareCharacter` (ABSTRACT bare base:
   suppressed attribute-set subobject, so the DefaultStartingData entry below
   is the only set ever created — the whole of stage 1 on the no-C++ lane).
   Inherited ASC `DefaultStartingData` = one entry
   `{Attributes=CraftBenchAttributeSet, DefaultStartingTable=DT_HealthInit}`;
   `GrantedAbilities=[GA_Damage, GA_Heal]`; `SKM_Manny_Simple`. **No event
   graph** — authored 100% headlessly.
3. **GE_Damage / GE_Heal** — instant GEs, Health AddBase **-10 / +10**
   (T3D `import_text` modifiers).
4. **GA_Damage / GA_Heal** — InstancedPerActor; tags `Ability.Damage` /
   `Ability.Heal`; **no cost, no cooldown** (the fixture activates damage twice
   0.7 s apart — anything held open refuses the second activation and HO-6
   FAILs conforming work). Graph: ActivateAbility → CommitAbility → Branch
   (false → EndAbility; true → BP_ApplyGameplayEffectToOwner(GE, Level 1) →
   EndAbility).

## Authoring notes beyond the DJ twin's (read that one first)

- 4 of 6 assets are fully headless; only the two 6-node ability graphs needed
  the MCP lane. Graphs were authored with the GRANULAR tools
  (`add_blueprint_node_to_strand` → `connect_blueprint_nodes` →
  `set_node_pins_defaults` → `compile_blueprint`), NOT `bp_agent` — deterministic,
  no tag-drop, no budget churn. The GAS function is
  **`BP_ApplyGameplayEffectToOwner`** (not `K2_`).
- `DefaultStartingData` survives compile — asserted by read-back in
  `aids/author_assets.py` (a value that only lived pre-compile would misread
  as "never initialized", a stage-1 HO-3 FAIL).
- The GA class-pin default reports an empty `new_value` in the tool response
  even when it took — verify with `get_asset_graph`, not the setter's echo.

## Re-validate

```sh
python tools/verify-single/run_task.py \
  --task tasks/bp-g2/gp-health-attribute-ops-bp/task.md \
  --submission tasks/bp-g2/gp-health-attribute-ops-bp/reference \
  --ue-root <UE-root> --workdir C:\cb\wd\<fresh>
```
