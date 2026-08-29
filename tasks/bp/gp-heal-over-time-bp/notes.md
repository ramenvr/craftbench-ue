# gp-heal-over-time-bp - implementor notes + asset specification

> **NOTHING IN THIS FILE HAS BEEN MEASURED.** As of authoring (2026-08-10) this
> twin has never been built, never run in PIE, never graded a reference and
> never run a discrimination sweep. No UBT invocation, no `UnrealEditor` launch,
> no `cb` command and no test suite has been executed against it. The Blueprint
> reference below is a **SPECIFICATION for a serial editor pass**, not an
> authored asset - nothing under `reference/` exists yet. The `-cpp` original's
> bars are themselves still `PROPOSED - NOT YET MEASURED` in the fixture source.

## Provenance and what this twin owns

- Source row: BP-G2 **source record 47**. Family **T1.2** of the bp-g2
  tier-1 slate; the clamp family.
- The signed design contract is `../gp-heal-over-time-cpp/PIN.md`, including its
  binding `OWNER DECISION 2026-08-10 -- EDIT, then ACCEPTED` block
  (`StopEpsilon` 0.7 -> 0.25). It is **normative** for the prompt, the schedule,
  gates HOT-0..HOT-7 and the anti-gaming list.
- **Owned by this twin (all new):** `task.md`, this file, the deliverable spec
  below, `discrimination/cpp-solve*/`, and (once authored)
  `reference/Content/Tasks/gp-heal-over-time-bp/*.uasset`.
- **NOT owned and NOT to be forked:** the L2 fixture
  (`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-heal-over-time/`),
  the map (`UE-projects/ThirdPerson/Content/Maps/gp-heal-over-time/L_HealOverTime.umap`),
  and any substrate source. Both are shared byte-identically with the `-cpp`
  original, which is what makes the two results comparable.

## Why this twin is load-bearing beyond the C++/BP comparison

`ClampEpsilon` - HOT-5's tolerance, the family's headline gate - **must be
calibrated against a Blueprint solve as well as the C++ one**
(`../gp-heal-over-time-cpp/PIN.md` section 6; the internal design note (not shipped)
P1). The C++ reference clamps in `PreAttributeChange` + `PostGameplayEffectExecute`;
Blueprint **cannot override either hook** (they carry no `UFUNCTION`), so the BP
lane has to bound the written magnitude instead. Two different mechanisms
produce two different residuals against the cap. Calibrating the tolerance
against the C++ residual alone is exactly how HOT-5 would false-FAIL a
conforming Blueprint solve - the fear F3 expressed, relocated. PIN.md requires
**three** solves: the C++ reference, the magnitude lane (the reference below)
and the ability-loop lane.

## Blockers before anything can be measured

1. ~~The Blueprint reference does not exist.~~ **RESOLVED 2026-08-11 — see
   `REFERENCE-NOTE.md` (authored + graded PASS from git HEAD; predicted trace
   reproduced line for line).** Original text: Five `.uasset`s must be authored
   in a live editor (specification below). Until then `cb lint` WARNs
   `reference-solution` and `cb discriminate` cannot run.
2. **The second calibration lane (ability-loop) is also unauthored**, and
   PIN.md section 6 makes it a precondition for calling `ClampEpsilon` pinned.
   It is a calibration artifact, not a discrimination variant: keep it out of
   `discrimination/` so no MATRIX row implies it is a decoy.
3. **The introspect script `gp_heal_over_time_bp.py` must exist** under
   `tools/verify-single/introspect/` or `cb lint` ERRORs
   (`introspect-script-exists`) and L2I cannot run. It is a thin wrapper over
   `_bp_variant_lib.py` configured with `pawn_base_class = "CraftBenchCharacter"`
   and `min_bp_abilities = 1` - the sibling shape of the already-committed
   `gp_health_attribute_ops_bp.py`.
4. **`cb lint` expectations:** `task-id-folder` clean (front-matter `id` equals
   the folder name - the ERROR that hit all three `-cpp` originals),
   `anti-gaming-count` clean (5 entries), `prompt-jargon` expected to WARN on
   "Blueprint" and the tag name (documented exceptions, not leaks).
5. **This task is NOT on `tools/verify-single/gold_set.txt`**, so
   `discrimination-coverage` does not fire on it today.

## Blueprint asset specification (the serial editor pass)

Five assets, all under `Content/Tasks/gp-heal-over-time-bp/`, **0 lines of
C++**. This is the **magnitude-calculation lane**. Names are for the authoring
pass only - the verifier resolves by content path + derivation + tag, never by
name.

### 1. `DT_HealthInit` - DataTable, row struct `AttributeMetaData`

| row name | BaseValue |
|---|---|
| `CraftBenchAttributeSet.MaxHealth` | 100.0 |
| `CraftBenchAttributeSet.Health` | 100.0 |

Row names are `<OwnerClass>.<Property>` - `InitFromMetaDataTable` keys them that
way and a bare `MaxHealth` row reads back as uninitialized, i.e. a HOT-0 FAIL.
The `Health` row is coherence only: the fixture presets Health per leg (40, 95,
100), so no gate reads its initial value. **`MaxHealth` is gated (HOT-0 = 100
+/- epsilon, read before any trigger and any fixture write).**

### 2. `BP_HealOverTimePawn` - Blueprint, parent class `CraftBenchCharacter`

Class defaults:

- `GrantedAbilities` = `[GA_HealOverTime]`.
- Inherited **Mesh** component: `SkeletalMesh = /Game/Characters/Mannequins/Meshes/SKM_Manny_Simple`,
  relative location `(0, 0, -90)`, relative rotation `(Pitch 0, Yaw -90, Roll 0)`.

Event graph - **exactly one node chain**:

```text
Event BeginPlay -> Get Ability System Component (the inherited component)
               -> InitStats(Attributes = CraftBenchAttributeSet,
                            DataTable  = DT_HealthInit)
```

- `InitStats` is `UAbilitySystemComponent::K2_InitStats`, `UFUNCTION(BlueprintCallable,
  Category="Skills", DisplayName="InitStats")` - verified present in the UE 5.8
  header at `Public/AbilitySystemComponent.h`.
- **DO NOT use `DefaultStartingData` on this lineage.** The component consumes
  `DefaultStartingData` in `OnRegister`, which runs BEFORE the
  `InitializeComponent` scan that registers attribute sets already constructed
  as subobjects of the owner (UE 5.8: `AbilitySystemComponent.cpp` OnRegister ->
  `GetOrCreateAttributeSubobject`; `AbilitySystemComponent_Abilities.cpp`
  InitializeComponent -> `GetObjectsWithOuter` -> `SpawnedAttributes.AddUnique`).
  The generic base **already** constructs a `UCraftBenchAttributeSet` subobject,
  which is not yet registered at `OnRegister`, so the route creates a **second**
  set of the contract class. Everything then resolves through
  `GetAttributeSubobject`, which returns the first match, so it is not
  guaranteed to break - which is exactly what makes it a bad thing to pin.
  `InitStats` at BeginPlay runs after component initialization, so the
  pre-built set is **reused, not duplicated**.
- An instant Override-MaxHealth-to-100 effect applied at BeginPlay is an equally
  conforming alternative. One ordering caveat if you take it: the base pawn
  calls `Super::BeginPlay()` - which is what fires a Blueprint's own BeginPlay -
  **before** it initializes its ability actor info.

### 3. `MMC_HealClamp` - Blueprint, parent class `GameplayModMagnitudeCalculation`

Class defaults - `Relevant Attributes to Capture` (`EditDefaultsOnly,
BlueprintReadOnly` on `UGameplayEffectCalculation`, so it is editable in the
Class Defaults panel), **two** entries:

| Attribute | Source | Snapshot |
|---|---|---|
| `CraftBenchAttributeSet.Health` | Target | **false** |
| `CraftBenchAttributeSet.MaxHealth` | Target | **false** |

`CalculateBaseMagnitude` (BlueprintNativeEvent, override in the BP graph):

```text
H   = Get Captured Attribute Magnitude(EffectSpec, CraftBenchAttributeSet.Health,
                                       SourceTags, TargetTags)
Max = Get Captured Attribute Magnitude(EffectSpec, CraftBenchAttributeSet.MaxHealth,
                                       SourceTags, TargetTags)
return max(0.0, min(5.0, Max - H))
```

- **Snapshot must be false on both captures.** A snapshotted capture freezes
  `Max - H` at application time and the effect overshoots on later periods -
  the exact HOT-5 failure the lane exists to avoid.
- The magnitude is re-evaluated on **every** period:
  `FActiveGameplayEffectsContainer::ExecuteActiveEffectsFrom` calls
  `Spec.CalculateModifierMagnitudes()` on each execution (UE 5.8
  `GameplayEffect.cpp`). That is what makes this lane work at all.
- `5.0` is the per-period restore, carried over from the C++ reference (see
  "Why these values").

### 4. `GE_HealOverTime` - Blueprint, parent class `GameplayEffect`

- `Duration Policy = Has Duration`, `Duration Magnitude` Scalable Float **5.0**
- `Period` **1.0**
- **`Execute Periodic Effect on Application = OFF`** (`bExecutePeriodicEffectOnApplication`,
  which defaults to **true** in 5.8; leaving it on makes a 5 s / 1 s effect
  execute six times, so the per-application total becomes 30 instead of 25 and
  the first restore is blurred into the activation frame)
- One modifier: attribute `CraftBenchAttributeSet.Health`, op **Add**,
  magnitude type **Custom Calculation Class** = `MMC_HealClamp`, with
  `Coefficient = 1.0`, `Pre Multiply Additive Value = 0.0`,
  `Post Multiply Additive Value = 0.0`
- **No stacking policy.** The prompt asks nothing about stacking; the engine
  default (each application its own instance) is the right shape, and borrowing
  the poison family's stacking block would answer a question that was not asked.

### 5. `GA_HealOverTime` - Blueprint, parent class `GameplayAbility`

- `Instancing Policy = Instanced Per Actor`
- **Ability Tags** (the 5.8 editor property backed by the ability's asset tags;
  python name `ability_tags`) = `Ability.HealOverTime`
- Graph: `ActivateAbility` -> `Commit Ability` -> on failure `End Ability`
  (cancelled); on success `Apply Gameplay Effect to Owner` (`GE_HealOverTime`,
  Level 1) -> `End Ability`
- **No cooldown, and the ability must NOT hold itself open for the effect's
  lifetime.** The verifier activates it **three times in one run** (t = 0.5,
  10.7, 17.0) and **HOT-1c requires all three to land**; an `InstancedPerActor`
  ability that is still running refuses the next activation, which would make
  HOT-5 and HOT-6 pass **vacuously** on a submission that never ran legs 2 and 3.

### Why these values and not others

- **The 5.0 s / 1.0 s / +5 shape is the C++ reference's choice carried over
  unchanged.** Five executions restore **25**, the exact midpoint of the
  disclosed 10-40 band (15 of margin each side), and 5.0 s sits mid-band in the
  disclosed 4-7 s window. Carrying it over is what keeps a `-cpp` vs `-bp`
  difference attributable to the authoring surface.
- **Predicted trace, identical to the C++ reference's and PREDICTED not
  measured:** Leg 1 `40 -> A1 45 -> A2 50 -> A3 60`, `AStop = ATail = 65`;
  `RiseStep1 = 5`, `RiseStep2 = 10`, `StopRise = 0.0`, `TotalRestored = 25`.
  Leg 2 (preset 95): first period `+5 -> 100`, later periods compute `min(5, 0)
  = 0`, so current **100.0** and base **100.0**. Leg 3 (preset 100): every
  period computes 0, so **100.0** in both directions. PASS on all nine checks.
  **If the first real run does not reproduce this line for line, stop and find
  out why before touching a bar.**

### The second calibration lane (ability-loop) - specification sketch

Not part of the reference; built only to calibrate `ClampEpsilon`. A BP ability
that, on activate, loops five times one second apart, each iteration computing
`Amount = max(0, min(5, MaxHealth - Health))` from `GetFloatAttribute` and
applying an **Instant** effect whose Health modifier magnitude is **Set By
Caller**, then ends. Its Set-By-Caller key **must be an already-registered tag**
(`Ability.HealOverTime` will do): authoring a new gameplay tag is a
`Config/DefaultGameplayTags.ini` edit, this spec declares no `config_allow`, and
such a submission is sandbox-rejected (exit 4).

## What must be measured before this task is trusted

1. Author the five assets, then grade the reference from git HEAD. Expect
   **overall PASS**, L2I **5/5**, and the predicted trace above.
2. Author the ability-loop lane and grade it. **Record both lanes' residuals
   against the cap** (`current - MaxHealth` and `base - MaxHealth` at cp7) and
   pin `ClampEpsilon` from the worst conforming residual with margin - not from
   the C++ reference alone.
3. `cb discriminate`: reference PASS; empty FAIL (at HOT-0, MaxHealth reads 0 -
   or at HOT-7 if the checkpoint-0 order puts visibility first; record which);
   `cpp-solve/` FAIL at `bp_pawn_present`; `cpp-solve-with-bp/` FAIL at
   `resolved_pawn_is_blueprint`.
4. **Cross-twin invariance check:** the `-cpp` and `-bp` references must produce
   the same `[HEALOVERTIME-FINAL]` numbers within jitter.

## Open risks and unverified claims

- **The MMC lane's Blueprint capture API has not been live-validated here.**
  What is verified from the UE 5.8 headers in this session:
  `UGameplayModMagnitudeCalculation` is `Blueprintable`, `CalculateBaseMagnitude`
  is a `BlueprintNativeEvent`, `K2_GetCapturedAttributeMagnitude` is
  `BlueprintCallable`, and `RelevantAttributesToCapture` is `EditDefaultsOnly,
  BlueprintReadOnly`. What is NOT verified is the end-to-end behavior in an
  editor-authored Blueprint on this substrate. If the capture array turns out
  not to be editable in the Class Defaults panel, **fall back to the
  ability-loop lane as the reference** and demote the MMC lane to the second
  calibration solve - the spec is symmetric and nothing else changes.
- **`UGameplayEffectExecutionCalculation` is a trap, not a lane.** It is
  `Blueprintable` and `Execute` is a `BlueprintNativeEvent`, but its
  capture-read and modifier-emit functions are unexposed: a BP execution
  calculation can be entered and can neither read a capture nor emit a
  modifier. Do not document it as a route; teaching it is teaching a dead API.
- **The L2I native sweep does not cover a native magnitude calculation.**
  `_bp_variant_lib.py` sweeps native subclasses of the scaffold PAWN only, so a
  C++ `UGameplayModMagnitudeCalculation` referenced from a Blueprint effect
  passes all five checks while adding C++ the prompt forbids. On THIS task that
  is the sharpest gap in the family, because the clamp is the graded axis and a
  magnitude calculation is its natural home. It is recorded as ARGUED, NOT
  DEFENDED in `task.md`; closing it is
  the internal design note (not shipped) V2.1's native-decoy sweep, which is
  not built.
- **The `-cpp` original's own spec banners are stale** (they still say the
  folder must be renamed and the map binary does not exist; both are done).
  Correct them when that task is next touched; do not copy them.

## Prompt delta vs the `-cpp` original (moved from task.md 2026-08-16; lint spec-h2-allowlist)

Not agent-visible (`prompt_extract.py` allow-lists only `## Prompt given to the
agent` and `## Workspace state pre-task`). Recorded here as a literal
before/after because prompt direction on this codebase has flip-flopped twice
under paraphrased confirmation.

**Exactly one bullet is replaced. Every other character of the prompt is the
`-cpp` original's, which is PIN.md section 1 verbatim** - including all four
disclosed absolutes (the 4-7 s band, the 10-40 total, MaxHealth = 100, and the
"neither the value the game reads back, nor the underlying stored value"
clause, which is the section C disclosure that makes HOT-5's FAIL fair).

BEFORE (`gp-heal-over-time-cpp`):

```text
- Deliver your pawn as a subclass of the provided character (C++ or Blueprint)
  with your ability granted on it.
```

AFTER (this twin):

```text
- Deliver your solution **entirely as Blueprint assets** created in the editor
  and saved under `Content/Tasks/gp-heal-over-time-bp/`: a Blueprint subclass
  of the provided character with your ability granted on it. **Do not add or
  modify any C++ source for this task.** That content folder is the only path
  the verifier looks in.
```

The delta deliberately does **not** hint at the clamp mechanism. The C++
original's prompt says nothing about *where* to clamp, and neither does this
one: whether the agent finds the magnitude route, the ability-loop route or
something else is exactly what the variant measures. Naming a route would turn
the family's headline gate into a reading-comprehension test.
