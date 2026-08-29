# gp-double-jump-stamina-bp — reference solution (binary .uasset, editor-authored)

**Status: AUTHORED + GRADED PASS 2026-08-11, from git HEAD (the certified
lane, no `--substrate-from-live`).** L2 `Result={Success}` + L2I **5/5**;
verdict evidence: `vZatTrigger=-425 maxVZlegOne=584` (mid-fall launch REVERSES
descent — `bZOverride=true` earning its keep), `debited=20.00 furtherDrop=0.00`
(one-shot debit), `refusalPreset=5.0 minPowerLegTwo=5.0 lastPowerLegTwo=5.0`
(at 5 Power the commit is refused, nothing launches, the attribute is
untouched). Report: the 2026-08-11 session's `djref-report.json`.

The reference lives at `reference/Content/Tasks/gp-double-jump-stamina-bp/`
(3 `.uasset`s), natively ThirdPerson-bound — **zero `/Script/CraftBenchTemplate`
bytes, no CoreRedirect port needed** (unlike the glide/poison twins, whose
assets predated the substrate move).

## As-built (3 assets) — spec in `notes.md`

1. **GE_DoubleJumpCost** — instant GE, `CraftBenchAttributeSet.Power`
   AddBase **-20**.
2. **GA_DoubleJump** — InstancedPerActor; `ability_tags = Ability.DoubleJump`;
   `CostGameplayEffectClass = GE_DoubleJumpCost` (both the debit and the
   refusal gate). Graph: ActivateAbility → CommitAbility → Branch
   (false → EndAbility; true → GetAvatarActorFromActorInfo → Cast to Character
   → LaunchCharacter(0,0,600, `bZOverride=TRUE`) → EndAbility).
3. **BP_DoubleJumpPawn** — parent `CraftBenchCharacter` (generic base, so the
   pre-built Power set exists); `GrantedAbilities=[GA_DoubleJump]`;
   `SKM_Manny_Simple` at (0,0,-90)/(0,-90,0).

## How it was authored (the two-lane recipe — reuse this)

- **Headless lane** (`aids/author_assets.py`, run against ThirdPerson with
  `-ExecutePythonScript`): everything that is CDO/data — both GEs' modifiers via
  T3D `import_text` (the ONLY route: `GameplayModifierInfo` exposes zero editor
  properties to Python and `GameplayAttribute.attribute_name` is read-only),
  tags, policies, the pawn.
- **MCP lane** (Aura tools on CraftBenchTemplate, ported): only the K2 event
  graph. UE 5.8 Python cannot SPAWN function-call nodes (`BlueprintEditorLibrary`
  has pin finders + `add_event_override`, no node spawner); pin VALUES are
  headless-editable via `BlueprintGraphPin.set_pin_value`.

Four measured traps for the next session:
1. MCP writes land in `Intermediate/Sandboxes/AuraSandbox/`, not `Content/` —
   promote by file copy.
2. Aura's `bp_agent` regenerates whole graphs and **dropped `ability_tags`** —
   re-run the aids script after any graph pass (it reuses assets, restoring the
   CDO without touching the graph), then byte-verify BOTH.
3. Node pin names are **localized** on this box (the Cast output is `As角色`,
   not `AsCharacter`) — read the error's pin listing, don't guess.
4. The Aura editor bridge needs the cb dev stack (`cb up --drive-ready
   --session-pid <pid>`), but the stack must be DOWN before grading — and so
   must every headless editor launch, whose UBT ValidatePlatforms preamble
   takes the same machine-global mutex (3 wrong-reason L1 FAILs, 2026-08-11).

## Re-validate

```sh
python tools/verify-single/run_task.py \
  --task tasks/bp-g2/gp-double-jump-stamina-bp/task.md \
  --submission tasks/bp-g2/gp-double-jump-stamina-bp/reference \
  --ue-root <UE-root> --workdir C:\cb\wd\<fresh>
```
