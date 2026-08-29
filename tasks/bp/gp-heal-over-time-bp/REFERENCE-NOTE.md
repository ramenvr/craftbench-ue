# gp-heal-over-time-bp — reference solution (binary .uasset, editor-authored)

**Status: AUTHORED + GRADED PASS 2026-08-11, from git HEAD — and the
spec's predicted trace reproduced LINE FOR LINE:** predicted
`40 → A1 45 → A2 50 → A3 60, AStop=ATail=65, steps 5/10, stopRise 0.0,
total 25, legs 2/3 at 100.0/100.0`; measured `A1=45.0 A2=50.0 A3=60.0
AStop=65.0 ATail=65.0 riseStep1=5.00 riseStep2=10.00 stopRise=0.00
total=25.00 L2cur=100.0 L2base=100.0 L3cur=100.0 L3base=100.0`, plus
`activated=3/3` (HOT-1c) and `maxHealth=100.0` (HOT-0). L2I **5/5**.
Report: the 2026-08-11 session's `hotref5-report.json`.

Reference at `reference/Content/Tasks/gp-heal-over-time-bp/` (5 `.uasset`s).
This is the **magnitude-calculation lane** — the only twin whose assets came
through BOTH port mechanisms (CoreRedirects for imports, `set_pin_value` for
pin-literal strings).

## As-built (5 assets) — spec in `notes.md`

1. **DT_HealthInit** — `CraftBenchAttributeSet.{Health,MaxHealth}` = 100/100.
2. **BP_HealOverTimePawn** — parent `CraftBenchCharacter`; granted
   `[GA_HealOverTime]`; `SKM_Manny_Simple`. Graph: BeginPlay →
   `AbilitySystemBlueprintLibrary.GetAbilitySystemComponent(Self)` →
   `K2_InitStats(CraftBenchAttributeSet, DT_HealthInit)`. (NOT
   DefaultStartingData — on this generic lineage that route creates a SECOND
   set of the contract class; see notes.md.)
3. **MMC_HealClamp** — BP of `GameplayModMagnitudeCalculation`;
   `RelevantAttributesToCapture` = Health + MaxHealth, both **Target /
   bSnapshot=false**. `CalculateBaseMagnitude` override graph:
   two `K2_GetCapturedAttributeMagnitude` calls (exec-chained — they are
   BlueprintCallable in 5.8, not pure; by-ref tag pins need a
   `MakeLiteralGameplayTagContainer` feeding all four) → `Max − H` →
   `FMin(·, 5.0)` → `FMax(·, 0.0)` → result.
4. **GE_HealOverTime** — HasDuration **5.0**, Period **1.0**,
   `bExecutePeriodicEffectOnApplication=OFF`, one Health AddBase modifier with
   `CustomCalculationClass=MMC_HealClamp` (Coefficient 1.0).
5. **GA_HealOverTime** — InstancedPerActor, `Ability.HealOverTime`, no
   cost/cooldown, ends synchronously (three activations in one run).

## THE DEFECT THE FIRST GRADE CAUGHT — pin literals need the FIELD PATH

First grade FAILed `total=0.00`: the GE applied, the MMC ran, and every period
healed zero. Root cause (probed, not guessed): the MMC's two
`FGameplayAttribute` **pin literals** were written with only
`AttributeName + AttributeOwner`, which leaves the struct's `Attribute` field
path EMPTY — and `FGameplayAttribute` lookup compares the FProperty pointer,
so the literal matched no capture and `GetCapturedAttributeMagnitude`
returned 0. The capture DEFINITIONS with the same text resolved fine (struct
import fixes them up; pin strings get no such fix-up). Fix: store the full
path in the pin text —
`(AttributeName="Health",Attribute=/Script/ThirdPerson.CraftBenchAttributeSet:Health,AttributeOwner=...)`.
`aids/author_assets.py` die()s if a pin lacks the resolved form.

## GE recipe corrections (from the 2026-08-11 python_agent research)

- duration magnitude: build `GameplayEffectModifierMagnitude()` +
  `import_text("(MagnitudeCalculationType=ScalableFloat,ScalableFloatMagnitude=(Value=5.0))")`
  — the kwarg constructor throws.
- period: **get-modify-set** (`get_editor_property("period")` → set value →
  set back) — a freshly constructed bare `ScalableFloat` throws.

## Port mechanics (three ported assets; temp CoreRedirects since REVERTED)

Graphs were MCP-authored on CraftBenchTemplate, copied in, then finalized by
`aids/author_assets.py` under a TEMPORARY `[CoreRedirects]` block in
`Config/DefaultEngine.ini` (CraftBenchTemplate→ThirdPerson for
CraftBenchCharacter + CraftBenchAttributeSet), reverted by `git checkout`
immediately after the resave — the redirects are baked into the committed
assets and the ini carries nothing. `EdGraph.Nodes` is protected to Python;
the aids script resolves K2 nodes by OBJECT NAME via `unreal.find_object`.

## Re-validate

```sh
python tools/verify-single/run_task.py \
  --task tasks/bp-g2/gp-heal-over-time-bp/task.md \
  --submission tasks/bp-g2/gp-heal-over-time-bp/reference \
  --ue-root <UE-root> --workdir C:\cb\wd\<fresh>
```
