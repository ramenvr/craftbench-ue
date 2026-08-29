---
id: gp-heal-over-time-bp
substrate: ThirdPerson
set: bp
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_HealOverTime :: AHealOverTimeFunctionalTest"]
introspect: [gp_heal_over_time_bp.py]
---

# gp-heal-over-time-bp

**Blueprint-deliverable variant** of `gp-heal-over-time-cpp` (family T1.2 of the
bp-g2 tier-1 slate, BP-G2 source record 47). The behavior spec, the fixture, the
10-checkpoint schedule and every L2 gate (HOT-0..HOT-7) are **identical** to the
C++ original so C++-vs-BP results are directly comparable - that comparability
is the entire point of the pair. The only deltas are (a) the prompt mandates a
**Blueprint** deliverable under `Content/Tasks/gp-heal-over-time-bp/` and (b) an
L2-introspect leg structurally asserts the deliverable really is Blueprint (the
anti-gaming gate against solving the "BP variant" in C++), plus (c) the C++
decoy discrimination variants that exist to try to defeat (b).

The **fixture and the map are SHARED with the `-cpp` original, byte-identically
and by design**: `Source/CraftBenchTests/Tasks/gp-heal-over-time/` and
`Content/Maps/gp-heal-over-time/L_HealOverTime.umap`. Neither folder carries a
`-cpp`/`-bp` suffix and neither may grow a per-variant copy. **Nothing about the
observation changes between the twins; only the authoring surface does.**

The design contract of the family is `../gp-heal-over-time-cpp/PIN.md`,
including its binding `OWNER DECISION 2026-08-10 -- EDIT, then ACCEPTED` block
(`StopEpsilon` 0.7 -> 0.25). It is **normative** and this twin does not redesign
any part of it: the prompt below is the signed prompt with exactly one bullet
replaced (see `## Prompt delta`), and every gate is the C++ original's.

> **STATUS: NOTHING HAS BEEN MEASURED ON THIS VARIANT** - and the `-cpp`
> original's own bars are `PROPOSED - NOT YET MEASURED` in the fixture source.
> This twin has never been built, never run in PIE, never graded a reference and
> never run a discrimination sweep. The Blueprint reference described under
> `## Reference solution metadata` is a **SPEC, not an authored asset** - no
> `.uasset` exists under `reference/` yet, because authoring one needs a live
> editor. Until it is authored and graded, no run of this task is evidence of
> anything. Calibration record and exact commands: `notes.md`.

> **`ClampEpsilon` MUST be calibrated against a BLUEPRINT solve, not only
> against the C++ reference** (`../gp-heal-over-time-cpp/PIN.md` section 6, and
> the internal design note (not shipped) P1). HOT-5 is the family's headline
> gate and the BP lane reaches the clamp by a **different mechanism** than the
> C++ reference's `PreAttributeChange` + `PostGameplayEffectExecute` pair -
> Blueprint cannot override either hook, so the clamp has to move to the
> magnitude. Calibrating that tolerance against the C++ reference alone is
> exactly how HOT-5 would false-FAIL a conforming Blueprint solve. **This twin
> is therefore not merely a re-skin of the original: it is one of the two
> calibration lanes the C++ family was approved on.**

> **Substrate: ThirdPerson.** Same substrate, same scaffolds and same fixture as
> the `-cpp` original; the twin adds no substrate change of any kind (0 new C++
> files, 0 new tags, 0 new maps).

> Variant note (deliverable-format exception): like the GAS-contract naming,
> mandating the **Blueprint** authoring surface is a deliberate, documented
> exception to behavior-only prompts (Hard Rule #2) - measuring the BP authoring
> path *is the point* of this variant. The `-bp` suffix is the benchmark's
> convention for such variants (see `tasks/README.md`).

> GAS-category note (inherited verbatim from the original): this task names the
> GAS **contract** as part of the interface - the documented exception to
> behavior-only prompts, because verifying a periodic, duration-bounded restore
> and its cap *through* an ability system is the point. The prompt names **an
> ability system**, **the attribute set type the project provides**, a
> **Health** resource, a **MaxHealth** cap and **one trigger tag**
> (`Ability.HealOverTime`). It never names the plugin, the classes
> (`UCraftBenchAttributeSet`, `ACraftBenchCharacter`) or the pattern
> ("GameplayEffect", "PreAttributeChange", "PostGameplayEffectExecute").

> **This family is deliberately NOT in the stage-1 correlation set.** It derives
> from the **generic** character, whose attribute set is pre-built (PIN.md D2),
> so constraint C1 in the internal design note (not shipped) does not reach it and it may sit in
> the same graded bench cell as either health-first family.

## Primary concept

- `gas-attributes` - Gameplay Attributes raised by a **periodic,
  duration-bounded** effect and **clamped against the pawn's own MaxHealth on
  both the current and the stored value**, authored **in Blueprint**
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-attributes-and-attribute-sets-for-the-gameplay-ability-system-in-unreal-engine)

The load-bearing mechanics are unchanged from `gp-heal-over-time-cpp`: an
activatable ability, reachable by its own gameplay tag, that restores Health on
a ~1 s cadence for a ~5 s duration and then **ends**; a per-application total
inside the disclosed 10-40 band; and an **invariant** - Health never exceeds
MaxHealth - enforced where a **periodic** modifier actually writes, which is the
**base** value. What changes is that all of it must be built through an
editor-visible route with **no C++**, which relocates the clamp from an
attribute-set hook to the modifier magnitude.

## Prompt given to the agent

> The project provides a character pawn that already owns an ability system and
> a **Health** resource through the attribute set type the project provides.
>
> Implement a **restorative ability** the game can activate on that character.
> When activated, it must raise Health **repeatedly - about once per second -
> for roughly five seconds, then stop**. It must not be a single instant
> restore, and it must not keep restoring forever. The verifier accepts any
> duration in the four-to-seven-second range, and each application must restore
> a total of between **10 and 40** Health across its lifetime.
>
> - Tag the ability `Ability.HealOverTime` and add it to the pawn's granted
>   abilities, so the game can start the effect by that tag.
> - **Health is capped.** MaxHealth is **100**, and your pawn must initialize
>   MaxHealth to 100. Health must **never exceed** MaxHealth -- neither the
>   value the game reads back, nor the underlying stored value it accumulates
>   into. Activating the ability while the character is already at full health
>   must leave Health at 100: it must not push past it, and it must not lower it.
> - Deliver your solution **entirely as Blueprint assets** created in the editor
>   and saved under `Content/Tasks/gp-heal-over-time-bp/`: a Blueprint subclass
>   of the provided character with your ability granted on it. **Do not add or
>   modify any C++ source for this task.** That content folder is the only path
>   the verifier looks in.
> - The character must be **visibly represented**: assign one of the provided
>   mannequin skeletal meshes (under `/Game/Characters/`) as your character's
>   mesh, so a reviewer watching the run can see it.
>
> The verifier sets Health to a known value, activates your ability by sending
> that tag, and observes Health over time.

## Workspace state pre-task

Files that **exist** under `Source/ThirdPerson/` - **read-only context for this
task**, since the deliverable is asset-only and the prompt forbids C++ edits:

- The stock UE 5.8 Third Person C++ template sources (`ThirdPersonCharacter`,
  game mode, the `Variant_*` trees). No edit needed and none allowed.
- `ThirdPerson.Build.cs` - already includes `GameplayAbilities`,
  `GameplayTags`, `GameplayTasks`. No edit needed.
- `CraftBenchCharacter.{h,cpp}` - **the base pawn for this family**: a
  pawn-owned ability system component (visible as an inherited component in a
  Blueprint subclass), the auto-granted `GrantedAbilities` array (ships empty,
  `EditAnywhere` - settable from Blueprint class defaults), the
  `CraftBenchPawn` tag, and a **pre-built attribute set**. Health is pre-built
  here, so there is no stage-1 ladder in this task.
- `CraftBenchAttributeSet.{h,cpp}` - the contract attribute set type (`Health`,
  `MaxHealth`, `Power`; **no clamping at v1.0**). `Health` is the attribute the
  verifier reads and the restore must raise; `MaxHealth` is the cap it must
  respect. **`MaxHealth` ships UNINITIALIZED** - it reads **0**, and there is no
  initializer anywhere in either substrate.
- `CraftBenchBareCharacter.{h,cpp}` - the *other* families' task base (no
  attribute set). Not used here; a Blueprint may parent to it, but then it has
  no Health and fails by name at the first gate.
- `CraftBenchGameplayTags.{h,cpp}` - registers `Ability.HealOverTime` alongside
  the pre-existing `Ability.Glide` / `Ability.Poison` / `Ability.Damage` /
  `Ability.Heal` / `Ability.DoubleJump`. The tag this task needs already exists;
  no tag authoring, and therefore no config edit, is required.
- The `GameplayAbilities` plugin is enabled.
- `AHealOverTimeFunctionalTest` lives in the verifier-only `CraftBenchTests`
  module (`Source/CraftBenchTests/Tasks/gp-heal-over-time/`). That module is
  deny-write and is graded from git HEAD, so nothing you submit can change it.
- `Content/Characters/Mannequins/` - the substrate's **native**
  visual-representation content (`SKM_Manny_Simple` / `SKM_Quinn_Simple`, the
  `SK_Mannequin` skeleton). Read-only: `Content/Characters/` is outside the
  writable sandbox.

Files the agent **creates** (all assets, under
`Content/Tasks/gp-heal-over-time-bp/` - the `Content/Tasks/` prefix is
agent-writable for asset deliverables): a Blueprint subclass of the provided
character that initializes MaxHealth to 100 and never lets Health exceed it (on
the value read back **and** on the stored value), plus a Blueprint ability
tagged `Ability.HealOverTime` that raises Health periodically for a bounded
duration, with that ability in the pawn's granted abilities, and whatever
supporting assets that route needs. The pawn is resolved by derivation plus the
preferred tag (the verifier scans Blueprint assets under `/Game/Tasks` via the
Asset Registry) and is spawned + possessed by the verifier - the map places no
pawn.

## Verifier specification

**L2 - behavioral (IDENTICAL to `gp-heal-over-time-cpp`, same fixture binary,
same map binary).** The `AHealOverTimeFunctionalTest` fixture, its 10-checkpoint
schedule `{0.5, 1.6, 3.1, 4.6, 7.6, 9.7, 10.7, 15.8, 17.0, 22.1}`, the three
legs, all eight gates HOT-0..HOT-7 and their exact named FAIL strings are the
C++ original's - see `../gp-heal-over-time-cpp/task.md` section "Verifier
specification" for the full table, which is the single source of truth. Nothing
in it is re-derived here. Summary of the gated legs:

```text
LEG 1 -- periodic + stop
  cp0 (0.5 s)  HOT-0 MaxHealth read (100 +/- eps) BEFORE any trigger and any fixture write
               HOT-7 visible-character check
               SetHealth(40) ; trigger Ability.HealOverTime          (attempt 1 of 3)
  cp1..cp3     A1 / A2 / A3   -> two CONGRUENT 1.5 s rise windows
  cp4..cp5     AStop / ATail  -> the 2.1 s stop window, OPENING at trigger+7.1,
                                 past the top of the disclosed 4-7 s band
LEG 2 -- the clamp
  cp6 (10.7 s) SetHealth(95) ; trigger                                (attempt 2 of 3)
  cp7 (15.8 s) THE DUAL READ at one instant: current AND base, both against the cap
LEG 3 -- at-max no-op
  cp8 (17.0 s) SetHealth(100) ; trigger                               (attempt 3 of 3)
  cp9 (22.1 s) final read ; ALL FINAL ASSERTS

  HOT-1  : granted by tag AND activated ; HOT-1c: ALL THREE activations landed
  HOT-2  : both congruent rise windows rose (pure direction + noise floor)
  HOT-3  : no rise left in the post-band stop window (StopEpsilon 0.25)
  HOT-4  : one application's total inside the DISCLOSED 10-40 band
  HOT-5  : current <= MaxHealthRead + ClampEpsilon AND base <= MaxHealthRead + ClampEpsilon
  HOT-6  : at full health the restore left Health at 100, in BOTH directions
```

The fixture resolves the pawn by derivation from `ACraftBenchCharacter`
(`ResolveAgentPawnClass` scans native subclasses AND Blueprint assets under
`/Game/Tasks` via the Asset Registry, preferring the candidate whose
`GrantedAbilities` carry the fixture's `PreferredAbilityTag()` =
`Ability.HealOverTime`), so **the Blueprint deliverable grades with no fixture
changes**.

**L2-introspect - the structural "the deliverable is Blueprint" gate.** The
verifier-owned script `tools/verify-single/introspect/gp_heal_over_time_bp.py`
(shared mechanism in `introspect/_bp_variant_lib.py`, configured with
`pawn_base_class = "CraftBenchCharacter"` and `min_bp_abilities = 1`) runs
headless via `UnrealEditor-Cmd -ExecutePythonScript=`. It emits **five checks on
every leg, reached or not**, so the denominator is constant and an empty
submission scores 0/5. PASS requires every one:

```text
task_folder_exists        : /Game/Tasks/gp-heal-over-time-bp/ exists and lists >= 1 asset
bp_pawn_present           : >= 1 Blueprint asset under that folder whose GeneratedClass
                            derives from ACraftBenchCharacter -- the same lineage the L2
                            fixture resolves, so L2I and L2 agree on what "the
                            deliverable" is
bp_pawn_grants_bp_ability : the BP pawn's GrantedAbilities class-defaults array holds
                            >= 1 Blueprint-generated ability class AND ZERO native
                            (/Script/) ones. The zero-native half closes the
                            GRANTED-ABILITY NATIVE HOLE: counting BP entries alone
                            passes a submission that grants one Blueprint ability next
                            to a C++ one doing the real work. Safe against false FAILs:
                            neither substrate commits a single UGameplayAbility
                            subclass, so every /Script/ entry found is agent C++.
resolved_pawn_is_blueprint: NO agent-authored native (C++) subclass of
                            ACraftBenchCharacter exists. Exemption is by EXACT /Script/
                            path against what the substrate commits at git HEAD (today:
                            the ABSTRACT CraftBenchBareCharacter alone), never by path
                            shape -- agent C++ lands in the same writable module as the
                            scaffolds, so a folder rule would re-open the hole. Fails
                            CLOSED if the reflection sweep stops seeing the scaffold.
pawn_visibly_represented  : the BP pawn's inherited mesh component carries an assigned
                            SkeletalMesh whose asset path lives under /Game/Characters/
                            (the substrate's read-only mannequin pool). Pool-anchored on
                            purpose: "some mesh exists" is gameable with an empty
                            placeholder under the writable path.
```

Identity is by **pre-declared content path** (`/Game/Tasks/gp-heal-over-time-bp/`)
and **derivation**, never by asset name or class name - the agent may name its
Blueprints anything.

**What L2I does NOT cover, and on THIS task it is the sharpest gap in the
family:** the native sweep is scaffold-PAWN shaped. A native `UAttributeSet`,
`UGameplayModMagnitudeCalculation` or `UGameplayEffect` subclass referenced from
Blueprint assets is not swept (`_bp_variant_lib.py`, "WHAT THIS MODULE DOES NOT
COVER"; the internal design note (not shipped) **V2.1** calls for exactly
that additional sweep and it is **not built**). The clamp is this family's
graded axis and a magnitude calculation is its natural home, so a C++
magnitude-calculation class referenced from a Blueprint effect is the one
undefended route that would matter here. See anti-gaming note 3 - it is recorded
as **ARGUED, NOT DEFENDED**, not assumed covered.

## Reference solution metadata

- **0 lines of C++. 5 Blueprint-era `.uasset`s**, all new, all under
  `Content/Tasks/gp-heal-over-time-bp/`. This is the "equivalent deliverable"
  the C++ original's reference metadata names (8 C++ files / 405 LOC -> 5 assets
  / 0 LOC), and it is deliberately the **magnitude-calculation lane** - the
  first of the two BP lanes `ClampEpsilon` must be calibrated against:
  - a **BP pawn** parenting `CraftBenchCharacter`, whose event graph calls the
    ability system component's Blueprint-exposed `InitStats` once on BeginPlay
    with the contract attribute set class and the init DataTable, and which
    carries `GrantedAbilities` = [the BP ability] and `SKM_Manny_Simple` on the
    inherited mesh component with the `(0,0,-90)` / `(0,-90,0)` capsule
    alignment every reference in this family uses;
  - an **`AttributeMetaData` DataTable** setting `MaxHealth` (and `Health`, for
    coherence - the fixture presets Health per leg, so no gate reads its initial
    value) to 100;
  - a **BP magnitude calculation** capturing Health and MaxHealth on the target,
    NOT snapshotted, returning `max(0, min(5, MaxHealth - Health))`;
  - a **BP GameplayEffect**, `HasDuration` 5.0 s, `Period` 1.0 s,
    `bExecutePeriodicEffectOnApplication = false`, one additive Health modifier
    whose magnitude is that custom calculation;
  - a **BP GameplayAbility**, `InstancedPerActor`, tagged `Ability.HealOverTime`,
    committing then applying the effect to the owner and ending immediately so
    the next leg's activation is not refused (HOT-1c).
- **Why the clamp moves to the magnitude, and why that is the point of the
  twin.** `UCraftBenchAttributeSet`'s clamp hooks (`PreAttributeChange`,
  `PreAttributeBaseChange`, `PostGameplayEffectExecute`) carry **no UFUNCTION**,
  so a Blueprint subclass cannot override them
  (the internal design note (not shipped) F3, leg 1). A Blueprint also cannot
  replace the inherited attribute-set subobject's class, which needs a C++
  constructor initializer. The BP-reachable answer is therefore to make the
  **written magnitude itself** unable to overshoot - which satisfies HOT-5's dual
  read structurally, because a periodic execution writes the base value and the
  value written is already bounded.
- **The magnitude is re-evaluated on every period, which is what makes this lane
  work at all**: `FActiveGameplayEffectsContainer::ExecuteActiveEffectsFrom`
  calls `Spec.CalculateModifierMagnitudes()` on each execution (UE 5.8
  `GameplayEffect.cpp`), and non-snapshot target captures read live. A
  snapshotted capture would freeze `MaxHealth - Health` at application time and
  overshoot on later periods.
- **The 5.0 s / 1.0 s / +5 shape is the C++ reference's CHOICE carried over
  unchanged**, and carrying it over is load-bearing for the comparison: with
  `bExecutePeriodicEffectOnApplication = false` a 5.0 s duration on a 1.0 s
  period executes **five** times, so one application restores **25** - the exact
  midpoint of the disclosed 10-40 band. The predicted trace is therefore the C++
  reference's predicted trace, line for line: Leg 1 `40 -> 45 -> 50 -> 60`,
  `AStop = ATail = 65`, `StopRise = 0.0`, `TotalRestored = 25`; Leg 2 current
  **100.0** and base **100.0**; Leg 3 **100.0**. **If the first real run of
  either twin does not reproduce that line for line, stop and find out why
  before touching a bar.**
- **The second calibration lane is the ability-loop route** and is equally
  conforming: a BP ability that loops five times, one second apart, applying an
  instant Set-By-Caller effect whose magnitude the ability graph computes as
  `min(5, MaxHealth - Health)`, then ends. PIN.md section 6 requires
  `ClampEpsilon` to be measured against **three** solves - the C++ reference,
  this magnitude lane and that ability lane. Its Set-By-Caller key must be an
  **already-registered tag**: authoring a new gameplay tag is a
  `Config/DefaultGameplayTags.ini` edit, and this spec declares no
  `config_allow`, so such a submission is sandbox-rejected (exit 4).
- Senior-dev hours: 1.5-2.5 hours.
- The exact package paths, parent classes and property values are enumerated in
  `notes.md` section "Blueprint asset specification". **The reference is a SPEC
  today, not an authored asset**: `.uasset` authoring needs a live editor and is
  a serial pass. `cb lint` will WARN `reference-solution` until it exists, and
  `cb discriminate` cannot run.

## Anti-gaming notes

1. **Solve it in C++ anyway (defeats the variant's whole point).** *Failure
   mode*: the agent writes the same C++ solution as the `-cpp` original -
   behaviorally correct, so L2 alone would pass it. *Defense*: the L2I leg FAILs
   `bp_pawn_present` (no Blueprint subclass of the provided character exists
   under `/Game/Tasks/gp-heal-over-time-bp/`) and independently
   `resolved_pawn_is_blueprint`. *Discrimination variant*:
   `discrimination/cpp-solve/` (the `-cpp` reference verbatim; the same shape as
   `tasks/bp/gp-glide-stamina-bp/discrimination/cpp-solve/`, which is the
   proven original - measured FAIL at that named check on a live runner
   2026-07-17).
2. **Decoy BP shell + real C++ solve.** *Failure mode*: the agent ships a
   Blueprint pawn (enough to satisfy the existence checks) plus a C++ pawn that
   actually implements the behavior and wins L2 resolution - so L2 grades the
   C++ while L2I grades the Blueprint and **both layers pass**, on a submission
   the prompt explicitly forbids. *Defense*: **`resolved_pawn_is_blueprint`** -
   no agent-authored native subclass of `ACraftBenchCharacter` may exist at all.
   **This is MEASURED, not argued, and the measurement is cited rather than
   re-argued**: `tasks/bp/gp-glide-stamina-bp/discrimination/MATRIX.md`
   records the `cpp-solve-with-bp/` variant grading **overall PASS on the
   3-check verifier and overall FAIL on the 4-check one**, same box, same
   commit, on UE 5.8 - a real false PASS that existed until 2026-08-03. The
   check logic is substrate-independent and is now shared code. *Discrimination
   variant*: `discrimination/cpp-solve-with-bp/`.
3. **A C++ helper reached from Blueprint - and on this task that is the clamp.**
   *Failure mode*: the pawn and the ability are genuine Blueprints, but the
   invariant the family exists to grade is enforced by agent-authored C++ they
   reference - most plausibly a native magnitude-calculation class on the
   effect's modifier, since Blueprint cannot override the attribute-set hooks
   and a model that knows that may reach for C++ for the clamp alone. *Defense,
   for the ability case only*: `bp_pawn_grants_bp_ability` requires **zero
   native entries** in `GrantedAbilities` (a deliberate divergence from the two
   shipped originals, which only count the Blueprint entries). ***ARGUED, NOT
   DEFENDED* for the clamp case**: a native `UGameplayModMagnitudeCalculation`,
   `UAttributeSet` or `UGameplayEffect` subclass referenced from a Blueprint
   asset is **not swept** and would pass all five checks. Closing it is
   the internal design note (not shipped) **V2.1**'s native-decoy sweep,
   which is **not built**; until it is, this entry is a recorded gap, not a
   claimed defense. It is recorded here rather than left implicit for the same
   reason `gp-double-jump-stamina-cpp` records AG-7: a note that quietly implies
   a defense it does not have is worse than no note.
4. **An invisible deliverable.** *Failure mode*: a behaviorally-correct pawn
   with no mesh - **MEASURED 2026-08-04 on the glide family: all 9 matrix reps
   across 3 models shipped meshless pawns**, and human review was only possible
   by instrumenting copies with a debug cube. *Defense*: two independent gates,
   L2's HOT-7 (a mesh component with a mesh actually assigned) and L2I's
   **`pawn_visibly_represented`**, which additionally pins the mesh to the
   read-only `/Game/Characters/` pool the agent cannot author into.
5. **Every behavioral gaming mode of the original** - an uninitialized MaxHealth
   (a cap of zero that clamps every restore to nothing), a tick-driven fake with
   nothing activatable, one instant restore dressed as an ability, a permanent
   regeneration, a token 1 HP magnitude, a current-only clamp whose stored value
   overshoots, and a "clamp" that *sets* Health to MaxHealth and therefore lowers
   it. *Defense*: **inherited unchanged**, because the fixture is the same binary
   - HOT-0, HOT-1, HOT-2, HOT-3, HOT-4, HOT-5 and HOT-6 respectively. The full
   argument, including the `StopEpsilon` derivation that the owner's 2026-08-10
   EDIT corrected from 0.7 to 0.25, is in `../gp-heal-over-time-cpp/task.md`
   sections "Anti-gaming notes" and "Hidden invariants". Per the `-bp`
   inheritance law (`tools/verify-single/gold_set.txt`), a twin legitimately
   inherits its C++ original's behavioral variants rather than cloning them.

## Hidden invariants

- **Every hidden invariant of `gp-heal-over-time-cpp` applies unchanged**: why
  HOT-0 must run before any trigger and any fixture write; why HOT-5 reads both
  current and base at the same instant while HOT-6 gates the current value only;
  the `StopEpsilon` derivation and its **re-pinning law** (`StopEpsilon` is
  coupled to `RiseEpsilon` and to all three window lengths and cannot be moved
  independently); why the two gated rise windows are congruent; why the Leg-1
  preset is 40; the preferred-tag pawn resolution; and samples initializing to
  `0.0` with nothing gating on a sentinel.
- **BP resolution is Asset-Registry-based.** The fixture only discovers
  Blueprint pawns saved under `/Game/Tasks/` - a Blueprint saved anywhere else
  (e.g. `Content/Blueprints/`) is sandbox-accepted but never resolved, and the
  task FAILs L2 for what looks like a behavioral reason. This is why the prompt
  names the folder and why `task_folder_exists` is the first L2I check.
- **`DefaultStartingData` is the WRONG init route on this lineage, and the
  reason is an ordering fact, not a style preference.** The ability system
  component consumes `DefaultStartingData` in **`OnRegister`**, which runs
  *before* the component's `InitializeComponent` scan that registers attribute
  sets already constructed as subobjects of the owner. On the **bare** lineage
  (`gp-health-attribute-ops-bp`, `gp-poison-dot-stack-bp`) there is no such
  subobject, so exactly one set is created and the route is the proven one. On
  **this** lineage the pre-built set is not yet registered at `OnRegister`, so
  `GetOrCreateAttributeSubobject` creates a **second** set of the contract class
  and the pawn ends up with two. Everything then resolves through
  `GetAttributeSubobject`, which returns the first match, so it is not
  guaranteed to break - which is exactly what makes it a bad thing to pin. The
  reference instead calls the Blueprint-exposed `InitStats` on BeginPlay, by
  which time the pre-built set IS registered and is therefore **reused, not
  duplicated**.
- **An init GameplayEffect is an equally conforming alternative to `InitStats`**
  (an instant effect that Overrides MaxHealth to 100), and the prompt states the
  observable contract, never a mechanism. The one ordering caveat worth knowing:
  the base pawn calls `Super::BeginPlay()` - which is what fires a Blueprint's
  own BeginPlay - **before** it initializes its ability actor info, so an
  effect-application route runs earlier in the lifecycle than a reader might
  assume. `InitStats` writes attribute values directly and does not care.
- **Blueprint cannot override the attribute-set clamp hooks**, so the two
  reachable clamp lanes are the magnitude route and the ability-loop route.
  `UGameplayEffectExecutionCalculation` is `Blueprintable` and is a **trap**:
  its capture-read and modifier-emit functions are unexposed, so a BP execution
  calculation can be entered but can neither read a capture nor emit a modifier
  (the internal design note (not shipped)). Do not document it as a lane.
- The map places **only the fixture** and sets no `GameModeOverride`, so PIE
  also spawns the substrate's default `BP_ThirdPersonGameMode` pawn at the
  PlayerStart. It is not an `ACraftBenchCharacter` subclass, so it can never win
  pawn resolution and no gate reads it - the graded pawn is exclusively the one
  the fixture spawns and possesses.
- **No config edit is needed and none is licensed.** `Ability.HealOverTime`
  already exists in `CraftBenchGameplayTags`; this spec declares no
  `config_allow` entries, so any `Config/` edit - including authoring a new
  gameplay tag for a Set-By-Caller key - rides the exit-4 sandbox path.
