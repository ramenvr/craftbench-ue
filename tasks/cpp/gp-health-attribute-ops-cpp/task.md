---
id: gp-health-attribute-ops-cpp
substrate: ThirdPerson
set: cpp
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_HealthOps :: AHealthAttributeOpsFunctionalTest"]
---

# gp-health-attribute-ops-cpp

Port of the **BP-G2 record 29 "Health-1"** eval prompt (`Category: Full
Prompt`, `Difficulty: medium`), running on the UE 5.8 **ThirdPerson** substrate.
The **T1.1 Band-A floor** of the bp-g2 tier-1 slate: the agent builds a health
resource on the provided task character (stage 1) and then two symmetric,
tag-activated operations that move it by a fixed amount (stage 2). Every gate
is either a stage-1 structural check lifted verbatim from
`gp-poison-dot-stack-cpp`, or a **ratio of two windows this same run produced**
plus the two absolutes the prompt itself discloses.

The design contract for this task is `PIN.md` in this folder. It is
**normative**: it fixes the prompt text, the checkpoint schedule, all eleven
gates HO-1..HO-11 with their named FAIL strings, and the anti-gaming list
AG-1..AG-6. This spec implements it; it does not redesign it.

> **STATUS: NOTHING HAS BEEN MEASURED.** No build, no PIE run, no reference
> grade, no discrimination sweep has been executed against this task. Every
> numeric bar named below carries `PROPOSED - NOT YET MEASURED` in the fixture
> source and in `notes.md`, and none of them may be treated as calibrated until
> both populations are recorded in `notes.md` with the chosen bar and the
> margin on each side (PIN.md section 6). The calibration record, the exact
> commands, and the two blockers below are in `notes.md`.

> **BLOCKER 1 - id/folder mismatch (this spec will `cb lint` ERROR until the
> folder is renamed).** The front-matter `id:` above is
> `gp-health-attribute-ops-cpp` (PIN.md's title, and the 2026-08-06 `-cpp`
> convention that surface-differentiates a C++ original from its `-bp` twin),
> but the folder is `tasks/bp-g2/gp-health-attribute-ops/`. `tasks/README.md`
> and `docs/AUTHORING_TEMPLATE.md` both state the front-matter `id` MUST equal
> the folder name, and `tasklint.py::_rule_task_id` raises that as an **ERROR**
> (`task-id-folder`). **The fix is to rename the folder to
> `tasks/cpp/gp-health-attribute-ops-cpp/`**, not to weaken the id: a bare
> `gp-health-attribute-ops` id would be a raw substring of the coming
> `gp-health-attribute-ops-bp`, which is exactly the prefix-shape violation the
> 2026-08-06 `-cpp` rename dissolved (it blinds `inventory.py`'s RAW-SUBSTRING
> CATALOG check - see the repo conventions). The **map** folder
> (`Content/Maps/gp-health-attribute-ops/`) and the **fixture** folder
> (`Source/CraftBenchTests/Tasks/gp-health-attribute-ops/`) are shared with the
> coming `-bp` twin and correctly stay unsuffixed - `map_locator.locate_map`
> derives the automation prefix from the map's own folder name and never joins
> it to the task id, and the poison pair sets the same precedent (its shared
> fixture folder keeps the `-bp` name after the `-cpp` rename; do not "fix"
> either).

> **BLOCKER 2 - the map binary does not exist yet.** The declared fixture map is
> `Content/Maps/gp-health-attribute-ops/L_HealthOps.umap`. That binary is **not
> committed**, so `cb lint` errors and L2 is an explicit FAIL (committed
> binaries are the only map source; scaffolders retired 2026-07). The one-shot
> authoring recipe that produces it is `aids/author_L_HealthOps.py` in this
> folder; it requires `ThirdPersonEditor` to be BUILT first (otherwise
> `/Script/CraftBenchTests.HealthAttributeOpsFunctionalTest` does not exist and
> `load_class` returns None) and a real off-screen RHI.

> **GAS-category note.** Like `gp-flight-mode`, `gp-glide-stamina-cpp` and
> `gp-poison-dot-stack-cpp`, this task names the GAS **contract** as part of the
> interface - the documented exception to behavior-only prompts (Hard Rule #2),
> because verifying the health resource and its two operations *through* an
> ability system is the point. What the exception licenses, and its exact
> limit: the prompt names **an ability system**, **the attribute set type the
> project provides**, **a Health attribute**, and **two trigger tags**
> (`Ability.Damage`, `Ability.Heal`). It never names the plugin ("GAS"), the
> class (`UCraftBenchAttributeSet`, `ACraftBenchBareCharacter`), the pattern
> ("GameplayEffect"), or the deliverable function names the source row used
> (`TakeDamage` / `Heal`) - those are deliverables, not starting workspace
> state, so `AUTHORING_TEMPLATE.md` forbids naming them.

> **Dropped source-row clauses** (PIN.md section 1 is the signed table; this is
> the summary the spec carries). `AGSCModularCharacter` and `GSCAttributeSet`
> are **GAS Companion** types present in neither substrate - re-homed onto the
> committed `ACraftBenchBareCharacter` / `UCraftBenchAttributeSet` and named
> only behaviorally. `TakeDamage` / `Heal` dropped **as names** (the seam is a
> gameplay tag, not a reflected function - PIN.md D1). `/Game/G2/8/` re-homed
> (that path does not exist and `Content/Maps/` is deny-listed). "Start
> implementing immediately" / "Do not reference any other existing assets"
> dropped as harness-level instructions - the second also contradicts the
> substrate, since the agent *must* reference the provided character and
> attribute set. **"max health values" dropped as a gated concept** (PIN.md
> D2): `UCraftBenchAttributeSet` ships `MaxHealth` uninitialized (reads 0), and
> upward clamping is `gp-heal-over-time`'s whole axis - gating it in both
> families would double-book the capability and re-correlate two of the four
> tier-1 cells. Nothing here reads MaxHealth.

## Primary concept

- `gas-attributes` - Gameplay Attributes and Attribute Sets, built by the agent
  (stage 1) and moved by two symmetric, tag-activated operations (stage 2)
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-attributes-and-attribute-sets-for-the-gameplay-ability-system-in-unreal-engine)

The load-bearing mechanics: **stage 1** - an attribute set registered on the
pawn-owned ASC exposing an initialized, readable and writable Health; **stage
2** - two activatable abilities, each reachable by its own gameplay tag, each
changing Health by **one fixed amount per activation**, equal in size and
opposite in sign, and **only** when activated. A missing/inert health system, a
non-derived pawn, an invisible pawn, an operation that is not an activatable
ability, a wrong-direction damage, an out-of-band magnitude, a non-repeatable
damage, an asymmetric heal, and a passive drift each fail by their own name.

## Prompt given to the agent

> The project provides a **task character pawn** that owns an ability system but
> **no health resource yet** (the project also contains a generic character with
> a pre-built attribute set, used by other tasks -- your pawn must be a subclass
> of the *task* character, not the generic one). Build the feature in two
> stages, in order:
>
> **Stage 1 - build the health system.** Give your pawn (a subclass of the
> provided task character) a **Health** attribute exposed through its ability
> system, using the attribute set type the project provides. Health must be
> **initialized to 100** and must be readable AND writable through the standard
> attribute APIs (the verifier both reads it and writes it).
>
> **Stage 2 - the two operations.** Implement two abilities the game can
> activate on your character:
>
> - a **damage** ability, tagged `Ability.Damage`, which lowers Health;
> - a **heal** ability, tagged `Ability.Heal`, which raises Health.
>
> Add both to the pawn's granted abilities so the game can activate each one by
> its tag. Each application of either ability changes Health by a **fixed
> amount between 5 and 25** -- the same amount every time it is applied -- and
> **one heal restores exactly as much Health as one damage removes**. Neither
> ability may change Health except when it is activated.
>
> - Deliver your pawn as a subclass of the provided task character (C++ or
>   Blueprint) with both abilities granted on it. If you author Blueprint
>   assets, save them under `/Game/Tasks/gp-health-attribute-ops-cpp/` -- that
>   is the only content path the verifier looks in.
> - Stamp each tag on the ability **itself**, in its own tag list, so the
>   ability can be activated *by that tag*. The verifier activates abilities by
>   tag directly; it does not send gameplay events.
> - The character must be **visibly represented**: assign one of the provided
>   mannequin skeletal meshes (under `/Game/Characters/`) as your character's
>   mesh, so a reviewer watching the run can see it.
>
> The verifier sets Health to a known value, then activates your abilities by
> sending those tags, and observes how Health moves. **It activates the damage
> ability more than once, about 0.7 seconds apart, and each activation must
> land its full effect** -- so an ability that is still running, or is on
> cooldown, when the next activation arrives will not be counted.

*(The prompt above is reproduced VERBATIM from `PIN.md` section 1 - it is the
signed contract and must not be paraphrased. The coming `-bp` variant adds one
line: "Deliver the pawn as a Blueprint asset under
`/Game/Tasks/gp-health-attribute-ops-bp/`." - same convention as
`gp-poison-dot-stack-bp`.)*

## Workspace state pre-task

Files that **exist** under `Source/ThirdPerson/` (this substrate's
agent-writable runtime module):

- The stock UE 5.8 Third Person C++ template sources (`ThirdPersonCharacter`,
  game mode, the `Variant_*` trees). No edit needed.
- `ThirdPerson.Build.cs` - already includes `GameplayAbilities`,
  `GameplayTags`, `GameplayTasks`. No edit needed.
- `CraftBenchBareCharacter.{h,cpp}` - **the task base pawn (the stage-1 start
  state)**: an abstract `ACraftBenchCharacter` lineage with a pawn-owned ASC,
  the auto-granted `GrantedAbilities` array (ships empty), the `CraftBenchPawn`
  tag, and **no attribute set** (the `"AttributeSet"` default subobject is
  suppressed on this lineage, so a C++ subclass building stage 1 must create
  its set under a **different** subobject name; the pawn-owned ASC
  auto-registers owner-outer'd attribute sets at `InitializeComponent`).
- `CraftBenchCharacter.{h,cpp}` - the generic scaffold pawn other tasks use; it
  still pre-builds the attribute set. **Subclassing it does not satisfy this
  task** - HO-1 fails a pawn that is not on the task-base lineage, by name.
- `CraftBenchAttributeSet.{h,cpp}` - the contract attribute set type (`Health`,
  `MaxHealth`, `Power`; no clamping at v1.0). `Health` is the attribute the
  verifier reads and both operations must move. The class exists; **registering
  and initializing an instance on your pawn's ability system is stage 1**.
- `CraftBenchGameplayTags.{h,cpp}` - registers `Ability.Damage`
  (`FCraftBenchGameplayTags::AbilityDamage()`) and `Ability.Heal`
  (`::AbilityHeal()`) alongside the pre-existing `Ability.Glide` /
  `Ability.Poison`. **Both accessors are NEW for this task** and are a hard
  build prerequisite for the fixture (PIN.md D3) - the bp-g2 scale-up plan (not shipped) I1.5
  budgeted 3 new tier-1 tags; the real count is 4 (2 here, 1 for
  `gp-heal-over-time`, 1 for the double-jump task).
- The `GameplayAbilities` plugin is enabled.
- `AHealthAttributeOpsFunctionalTest` lives in the verifier-only
  `CraftBenchTests` module
  (`Source/CraftBenchTests/Tasks/gp-health-attribute-ops/`). The folder is
  deliberately unsuffixed: the coming `-bp` twin shares this fixture
  byte-identically, exactly as the glide/poison pairs do.
- `Content/Characters/Mannequins/` - the substrate's **native**
  visual-representation content (`SKM_Manny_Simple` / `SKM_Quinn_Simple`, the
  `SK_Mannequin` skeleton). Read-only: `Content/Characters/` is outside the
  writable sandbox; the prompt's visible-character bullet points here.

Files the agent **creates**: a pawn subclass of `ACraftBenchBareCharacter` that
builds the health system (stage 1), plus two abilities (C++ or Blueprint)
tagged `Ability.Damage` and `Ability.Heal` that each change Health by one fixed
amount per activation (stage 2), with both in the pawn's `GrantedAbilities`.
The pawn is resolved **by derivation plus the preferred tag** and is spawned +
possessed by the verifier - the map places no pawn.

## Verifier specification

Single leg, no reset. The verifier gates stage 1 at checkpoint 0 (BEFORE any
trigger), then presets Health, activates the two abilities by tag, and samples
Health across four equal-length windows.

**Shipped fixture (the source of truth for every gate below):**
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-health-attribute-ops/HealthAttributeOpsFunctionalTest.{h,cpp}`
- 5-checkpoint schedule `{0.5, 1.2, 1.9, 2.6, 3.3}`, `LastCheckpointIndex = 4`,
all final assertions at cp4. Every FAIL string quoted below is read from that
`.cpp`, not from the PIN sheet.

```text
OnCheckpoint idx 0 (0.5s) - THE STAGE-1 LADDER (all named FAILs, before any trigger):
    HO-1 derivation : Pawn IsA ACraftBenchBareCharacter
    HO-2 presence   : PawnHasAttribute(UCraftBenchAttributeSet::GetHealthAttribute())
    HO-3 init       : |Health - 100| <= BaselineEpsilon, read BEFORE any fixture write
    HO-4 writability: SetNumericAttributeBase(Health, 37); |read-back - 37| <= BaselineEpsilon
    HO-5 visibility : a skeletal/static mesh component with an assigned mesh on the graded pawn
    then SetHealth(60)              // PresetHealth - PIN.md D4, never near a clamp
         H0 = Health()              // read AFTER the preset, BEFORE the trigger
         Trigger Ability.Damage
idx 1 (1.2s): H1 = Health()  (drop1 closes)  ; Trigger Ability.Damage   // drop2 opens
idx 2 (1.9s): H2 = Health()  (drop2 closes)  ; Trigger Ability.Heal     // healDelta opens
idx 3 (2.6s): H3 = Health()  (healDelta closes)                          // the IDLE window opens
idx 4 (3.3s): H4 = Health()  (idle window closes) ; ALL FINAL ASSERTS

    Drop1     = H0 - H1     over (cp0, cp1]   - 0.7 s
    Drop2     = H1 - H2     over (cp1, cp2]   - 0.7 s, CONGRUENT with the above
    HealDelta = H3 - H2     over (cp2, cp3]   - 0.7 s, CONGRUENT with both
    IdleDelta = H4 - H3     over (cp3, cp4]   - nothing triggered

    HO-6  : per tag, NumGrantedAbilitiesWithTag >= 1 AND TriggerAbilityByTag returned true
    HO-7  : Drop1 > DeltaEpsilon                                  (direction + noise floor)
    HO-8  : MagnitudeMin <= Drop1 <= MagnitudeMax                 (the DISCLOSED 5-25 band)
    guard : Drop1 > DeltaEpsilon, else a NAMED "no usable denominator" FAIL (never a divide)
    HO-9  : Drop2 / Drop1     in [1 - RepeatTol, 1 + RepeatTol]
    HO-10 : HealDelta / Drop1 in [1 - SymTol,    1 + SymTol]
    HO-11 : |IdleDelta| <= DeltaEpsilon
```

**Reads go through the CURRENT (post-aggregator) value, not the base.** The
fixture's `Health()` helper calls `PawnAttribute(...)`, per the V1.4 law in
`CraftBenchPawnFunctionalTest.h`: a damage or heal implemented as a
duration/infinite modifier - or as an `Override` - never touches the BASE value,
so a base-only read would report `Drop1 == 0` for a conforming solve and
false-FAIL it at HO-7. Writes still use `ASC->SetNumericAttributeBase` (no base
helper exists), the same call the poison fixture makes.

**Sample ordering is load-bearing.** `H0` is read AFTER the preset and BEFORE
the trigger; `H1`/`H2` are read BEFORE their own triggers. An instant effect
executes synchronously inside `TryActivateAbilitiesByTag`, so a read taken
after the trigger would fold the first application into the baseline and make
`Drop1` read 0.

### The eleven gates and their exact named FAIL strings

| gate | kind | window | exact FAIL string (from the fixture `.cpp`) |
|---|---|---|---|
| **HO-1** derivation | structural | cp0, before any write | `stage 1 not built: the graded pawn (%s) does not derive from the provided task base pawn (CraftBenchBareCharacter). An empty submission resolves to the generic scaffold pawn; a submission subclassing the generic scaffold pawn inherits a pre-built health system and skips stage 1.` |
| **HO-2** Health present | structural | cp0 | `stage 1 not built: the pawn's health attribute system is absent - the ASC has no attribute set exposing Health, so reads return 0 and writes no-op. A pawn that never builds (or detaches) the contract attribute set looks exactly like this.` |
| **HO-3** init to 100 | **ABSOLUTE (disclosed)** | cp0, read BEFORE any fixture write | `stage 1 incomplete: Health must initialize to 100 but read %.1f before any fixture write (\|delta\| %.2f > %.2f). An attribute set that is registered but never initialized reads 0 here.` |
| **HO-4** write-then-read at 37 | structural (37 != 100 on purpose) | cp0 | `stage 1 incomplete: health attribute is inert, write-then-read failed (wrote %.1f, read back %.1f, \|delta\| %.2f > %.2f). An inert or shadowed attribute set accepts the write but keeps reading its own value.` |
| **HO-5** visible character | structural | cp0 | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` |
| **HO-6a** damage granted | structural count | cp4 | `no activatable ability tagged Ability.Damage on the pawn (health operations not implemented as activatable abilities). granted=%d` |
| **HO-6b** damage activated | structural latch | cp4 | `an ability tagged Ability.Damage was granted but did NOT activate on TryActivateAbilitiesByTag` |
| **HO-6c** heal granted | structural count | cp4 | `no activatable ability tagged Ability.Heal on the pawn (health operations not implemented as activatable abilities). granted=%d` |
| **HO-6d** heal activated | structural latch | cp4 | `an ability tagged Ability.Heal was granted but did NOT activate on TryActivateAbilitiesByTag` |
| **HO-7** damage lowers Health | direction + noise floor | (cp0, cp1] | `the damage operation did not lower Health: Health went %.1f -> %.1f across the first application (delta %.2f, need a drop > %.2f).` |
| **HO-8** magnitude in the disclosed band | **ABSOLUTE (disclosed: 5..25)** | (cp0, cp1] | `the per-application Health change is outside the stated 5-25 band: one damage moved Health by %.1f. The prompt fixes a per-application amount between 5 and 25.` |
| *(ratio guard)* | named refusal, not a divide | cp4 | `the repeatability and symmetry ratios have no usable denominator: the first damage application moved Health by %.2f (need > %.2f). HO-9 and HO-10 are both ratios against that first application and cannot be formed.` |
| **HO-9** repeatability | **RATIO** `Drop2/Drop1` | (cp0,cp1] vs (cp1,cp2] - congruent | `the damage operation is not a fixed amount: the first application removed %.1f and the second removed %.1f (ratio %.2f, need %.2f-%.2f). A one-shot that sets Health to a constant removes a different amount the second time.` |
| **HO-10** heal/damage symmetry | **RATIO** `HealDelta/Drop1` | (cp2,cp3] vs (cp0,cp1] - congruent | `heal does not restore what damage removes: one damage removed %.1f but one heal restored %.1f (ratio %.2f, need %.2f-%.2f). Restoring to full health, or healing a different amount, fails here.` |
| **HO-11** event-driven, not drift | direction + noise floor | (cp3, cp4] - nothing triggered | `Health kept moving with no operation active: %.1f -> %.1f in the idle window (\|delta\| %.2f > %.2f). Damage and heal must change Health only when activated.` |

Two pre-gates run before the ladder at every checkpoint and are not counted
among the eleven: `pawn did not spawn/resolve` and `pawn has no
AbilitySystemComponent`.

**HO-6 is four checks, not two.** The base's `bAbilityActivated` is a single
latch across all tags and therefore cannot say *which* tag failed, while HO-6's
message takes the tag by name. The fixture keeps private per-tag latches
(`bDamageActivated` / `bHealActivated`) fed from `TriggerAbilityByTag`'s return
value, and checks granted+activated per tag.

**The ratio-denominator guard is unreachable in practice, deliberately.** HO-7
already requires `Drop1 > DeltaEpsilon` and HO-8 then bounds it into
`[MagnitudeMin, MagnitudeMax]`, so the guard can only fire if the gates are
ever re-ordered. It **FAILs by a named string rather than dividing**, and the
`0.0` ratio fallback beside it exists only so the diagnostic line always
prints - nothing gates on it.

**Pass criteria** (gated): the stage-1 ladder holds at checkpoint 0
(derivation, Health present, initialized to 100, a 37-write moves it, and the
pawn is visibly represented - each a NAMED stage-1 FAIL, never a misattributed
stage-2 one); both abilities are granted and activate on their own tags; the
first damage lowers Health by an amount inside the disclosed 5-25 band; the
second damage removes the same amount (HO-9); one heal restores that same
amount (HO-10); and Health does not move at all in the idle window (HO-11).

### Calibration instrument

The final checkpoint emits **two** `[HEALTHOPS-FINAL]` lines before any gate
runs, so both survive a FAIL:

1. The pinned diagnostic: `grantedDamage grantedHeal activatedDamage
   activatedHeal init writeProbe h0 h1 h2 h3 h4 drop1 drop2 heal repeatRatio
   symRatio` - every raw sample, all three deltas and both ratios, so the real
   population can be read off ONE run.
2. The congruence evidence: `baseline idleDelta w1 w2 w3 w4` plus the four bar
   values, where `w1..w4` are the **realized** window lengths taken from the
   fixture's `CrossingTimes` array. HO-9 and HO-10 are pinnable **only**
   because the three gated windows are congruent; this line makes that premise
   measured rather than assumed. `CrossingTimes` is evidence only - no gate
   reads it.

> **Design note (relative vs absolute).** Three of the eleven gates are
> absolute: HO-3 (100), HO-8 (the 5-25 band), and the epsilons. Under
> `TASK-AUTHOR-GUIDE.md` section C each is lawful **only because the prompt
> states it** - "initialized to **100**" and "a **fixed amount between 5 and
> 25**". The two load-bearing discriminators, HO-9 and HO-10, are **pure ratios
> of two windows this same run produced** and are therefore unaffected by the
> agent's choice of magnitude anywhere inside the band.
>
> **Why HO-8 exists at all**, given that HO-9/HO-10 already gate the shape: so
> a non-conforming *magnitude* fails by its own name. An agent that picks 60
> per application would otherwise drive Health through the floor mid-leg and be
> told its damage "is not a fixed amount" - the F5 failure mode
> (the bp-g2 scale-up plan (not shipped) section 0) reproduced in a new task.
>
> **Why the preset is 60 and not 100** (PIN.md D4, the anti-F3 discipline): the
> leg applies at most two damages and one heal. At 60, two damages at the band
> top (25 each) leave Health at 10, so no floor clamp can bite; one heal at the
> band top leaves Health at 85, so no MaxHealth ceiling can saturate it. A
> preset of 100 would put the heal hard against the ceiling and a saturated
> heal would shrink `HealDelta` - turning a **conforming** implementation into
> a misattributed HO-10 FAIL. A clamp must never be able to do that.

## Reference solution metadata

- LOC range: 250-350 LOC across 6 file pairs (315 LOC as committed, comments
  included). **Stage 1**: `HealthOpsPawn.{h,cpp}` parents
  `ACraftBenchBareCharacter`, constructs the contract attribute set under the
  non-suppressed subobject name `"HealthAttributes"` (reusing `"AttributeSet"`
  would produce a null set and a self-inflicted HO-2), calls
  `InitHealth(100.0f)`, grants both abilities, and constructor-assigns
  `/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple` through a guarded
  `ConstructorHelpers::FObjectFinder` with the same `(0,0,-90)` / `(0,-90,0)`
  capsule alignment the poison reference uses. **Stage 2**:
  `DamageAbility.{h,cpp}` / `HealAbility.{h,cpp}` (each `InstancedPerActor`,
  each `SetAssetTags` with its own tag, each applying its effect to self on
  activate and ending immediately) plus `DamageEffect.{h,cpp}` /
  `HealEffect.{h,cpp}` (each a `UGameplayEffect` subclass configured entirely
  in its constructor: `DurationPolicy = Instant`, one additive Health modifier
  of -10 / +10).
- Files touched: **12 new**, all under `Source/ThirdPerson/` (the writable
  prefix in `AGENT_WRITABLE.json`). The 3 pairs the PIN sketch named became 6
  because the reference routes the operations through instant GameplayEffects
  rather than `ApplyModToAttribute`.
- **Why an instant GameplayEffect and not `ApplyModToAttribute`:** the source
  source record itself says "GAS effects for the operations on these values"; a
  competent engineer writing this from the prompt writes an effect, since
  `ApplyModToAttribute` is a back door around the aggregator/execution path; it
  reuses the recipe already proven on disk in this substrate (`PoisonEffect`);
  and an instant effect leaves nothing active afterwards, so **HO-11's idle
  window is satisfied structurally rather than by luck**. `ApplyModToAttribute`
  would have saved two file pairs but modelled the very "poke the attribute
  directly" shape AG-3 exists to punish.
- **The +/-10 magnitude is a reference CHOICE, not a calibrated bar**
  (`PROPOSED - NOT YET MEASURED` in both effect sources): it sits mid-band, far
  from both edges of HO-8, and pairing -10 with +10 makes HO-9 and HO-10 read
  exactly **1.00**, giving the reference maximum margin on both ratio gates.
- `MaxHealth` is initialized to 100 on the reference pawn purely so the
  resource reads coherently to a human. **No gate reads it**, and
  `UCraftBenchAttributeSet` applies no clamping, so it cannot bound the heal or
  interact with HO-8/HO-10 (PIN.md D2).
- Senior-dev hours: 1-1.5 hours (the Band-A floor of the tier-1 slate; stage 1
  is shared with `gp-poison-dot-stack-cpp` and stage 2 is two symmetric instant
  effects with no timing, stacking, or duration semantics).
- A Blueprint reference (BP pawn parenting the task base + two BP abilities +
  two BP effects) is the equivalent deliverable; the verifier resolves a BP
  pawn via the asset registry. The `-bp` variant will mandate it.

## Anti-gaming notes

1. **AG-1 - skip stage 1 by inheriting a pre-built health system.** *Failure
   mode*: subclass the **generic** scaffold pawn (whose attribute set is still
   pre-built for other tasks' sake) instead of the task base, so Health exists
   for free and stage 1 is never done; or build no attribute set at all, in
   which case reads silently return 0 and writes silently no-op - which without
   a gate would misgrade later as "the damage operation did not lower Health".
   *Defenses*, all at checkpoint 0 before any trigger: **HO-1** derivation
   (`Pawn->IsA(ACraftBenchBareCharacter)`), **HO-2** presence
   (`PawnHasAttribute(Health)`), **HO-3** init-to-100 read taken **before any
   fixture write**. An empty submission resolves to the generic scaffold pawn
   and dies at HO-1. *Discrimination variants* (**PLANNED, NOT YET COMMITTED**):
   `discrimination/generic-pawn-subclass/` -> HO-1, and
   `discrimination/no-health-system/` -> HO-2 (the poison family's
   `no-health-system/` variant is the proven shape to copy - probe-proven live
   2026-08-05).
2. **AG-2 - an inert or shadowed attribute set.** *Failure mode*: register
   something that reads its own shadow value and ignores writes; if it happens
   to initialize at 100 it would pass a 100-valued write vacuously. *Defense*:
   **HO-4** write-probes at **37**, deliberately `!= 100`, and requires the
   read-back to move. HO-3 runs first, so init and writability are two separate
   named failures, never one ambiguous one. *Discrimination variant*
   (**PLANNED**): `discrimination/inert-attribute-set/` -> HO-4.
3. **AG-3 - move Health without an activatable ability.** *Failure mode*: do
   the damage/heal from `Tick` or `BeginPlay`, or as plain C++ functions with
   nothing granted - the numbers move in the right direction but nothing is
   reachable by tag. *Defense*: **HO-6** checks, **per tag**, that
   `NumGrantedAbilitiesWithTag >= 1` **and** that `TriggerAbilityByTag`
   returned true, so the FAIL names *which* tag is missing; **HO-11**'s idle
   window then catches the drift a tick-driven fake leaves behind.
   *Discrimination variant* (**PLANNED**):
   `discrimination/no-ability-tick-damage/` -> HO-6.
4. **AG-4 - "damage" as set-to-a-constant, or "heal" as restore-to-full.**
   *Failure mode*: both move Health the right way, both are activatable by tag,
   neither is a tick hack - and `heal = set Health to MaxHealth` is a genuinely
   *reasonable-sounding* reading of "a heal ability which raises Health". It is
   wrong only against the prompt's "one heal restores exactly as much Health as
   one damage removes". *Defense*: the ratio pair. **HO-9** (`drop2/drop1`)
   collapses for a one-shot that sets Health to a constant - the second
   application removes a different amount. **HO-10** (`healDelta/drop1`) is
   what kills restore-to-full: PIN.md section 4's worked trace reads ratio
   **6.00** against the `[0.90, 1.10]` window. **HO-8** exists beside them so a
   merely non-conforming *magnitude* (say 50 per application) fails by its own
   name instead of being misattributed to "your damage is not a fixed amount" -
   the F5 failure mode. *Discrimination variants* (**PLANNED**):
   `discrimination/heal-to-full/` -> HO-10, `discrimination/damage-to-zero/` ->
   HO-9.
5. **AG-5 - a meshless pawn.** *Failure mode*: behaviorally correct, invisible
   to a human reviewing the film strip - the run is ungradable by eye.
   **Measured 2026-08-04 on the glide family: 9/9 matrix reps shipped meshless
   pawns**, and the poison family's own film strips showed an empty scene.
   *Defense*: **HO-5**, the checkpoint-0 visible-character gate - a
   skeletal/static mesh component with a mesh actually assigned must exist on
   the graded pawn. Structural and deterministic. *Discrimination variant*
   (**PLANNED**): `discrimination/meshless-pawn/` -> HO-5.
6. **AG-6 - passive regeneration that makes the heal look like it worked.**
   *Failure mode*: a tick or timer that drifts Health upward continuously, so
   the heal window shows a rise the ability never caused. *Defense*: **HO-11**
   samples the `(cp3, cp4]` window in which **nothing is triggered** and
   requires `|delta| <= IdleEpsilon` in either direction. Note the pairing:
   HO-6 proves the abilities exist and fire, HO-11 proves nothing *else* is
   moving Health.

   *Discrimination variant*: `discrimination/regen/` -- **MEASURED 2026-08-10,
   and it does NOT die at HO-11.** It dies at **HO-10**: the drift also
   contaminates the heal window (`symRatio=1.33`), and HO-10 is evaluated
   first. HO-11 was not idle-blind -- the same run recorded
   `h3=54.2 -> h4=55.6`, an `idleDelta` of **1.4 against `IdleEpsilon=0.5`**, so
   it would have fired second. The honest consequence is that **HO-11 has no
   committed variant that dies at it**, which is precisely the shape that let
   the poison stop-gate ship unsound for six weeks. Follow-up: a `slow-regen/`
   variant tuned to pass HO-7..HO-10 and trip only HO-11. See
   `discrimination/MATRIX.md`.

## Hidden invariants

- **`PreferredAbilityTag()` returns `Ability.Damage`, and that is what
  disambiguates pawn resolution.** `ResolveAgentPawnClass` prefers a candidate
  whose CDO `GrantedAbilities` contains an ability whose **asset tags** carry
  the fixture's preferred tag; without the override, any other committed
  `ACraftBenchCharacter` subclass (the glide pawn, the poison pawn,
  `gp-heal-over-time`'s pawn) could win purely by enumeration order. The tag is
  UNIQUE per GAS family, which is precisely what lets all of those pawns stay
  committed alongside this one. `Ability.Heal` is deliberately **not** the
  preferred tag: `gp-heal-over-time` will also want a heal-shaped tag, and one
  preferred tag per family is the invariant. Verified at authoring time: no
  committed pawn under `Source/ThirdPerson/**` grants `Ability.Damage` or
  `Ability.Heal`.
- **The committed task base is abstract, so the resolver can never grade it.**
  `ACraftBenchBareCharacter` is `UCLASS(Abstract)` and `ResolveAgentPawnClass`
  skips `CLASS_Abstract` candidates. This is load-bearing twice: the base is
  something to derive from rather than a pawn that could be graded by accident,
  and committing it leaves every other task's resolution order untouched. HO-1
  therefore tests *derivation*, never *identity*.
- **Why the preset is 60.** Two damages and one heal, each at most 25 per the
  disclosed band, keep the entire leg strictly inside `(0, 100)` from a start
  of 60 - Health never approaches the floor at 0 or a MaxHealth ceiling at 100.
  Neither clamp can bite, so a clamp can never shrink `Drop2` or `HealDelta`
  and turn a conforming implementation into a misattributed HO-9/HO-10 FAIL.
  60 is the anti-F3 discipline, not an arbitrary round number, and it is the
  reason HO-8's band top (25) and the preset are linked: raising the band would
  require lowering the preset.
- **Why the three gated ratio windows are congruent.** `(cp0,cp1]`,
  `(cp1,cp2]` and `(cp2,cp3]` are all 0.7 s at equal offsets from their own
  triggers. A ratio of two windows of *different* length is not pinnable:
  tick-count quantization does not cancel between numerator and denominator, so
  the same conforming implementation reads a different ratio depending on phase.
  That is exactly why the poison fixture's stack cap stayed ungateable until its
  two rate windows were made congruent (its 2026-08-06 cap note). Here the
  congruence makes both ratios measure the per-application magnitude directly,
  and the second `[HEALTHOPS-FINAL]` line reports the realized window lengths so
  the premise is evidence rather than assumption.
- **Stage order is enforced by observation, not narration.** Checkpoint 0 runs
  before any trigger, so a submission cannot pass stage 2 without stage 1 - the
  operation windows read the same attribute stage 1 must expose.
- **Health is read via the contract attribute** (`GetHealthAttribute()` on the
  provided attribute set type). An agent that invents its own attribute set
  type, or moves a different attribute, fails HO-2/HO-3 by name.
- **The write probe uses 37, not 100.** HO-3 reads init-100 first, then HO-4
  writes 37 and requires the read-back to move - an inert-write set that
  happens to initialize at 100 cannot pass the writability gate vacuously.
- **Samples initialize to `0.0`, and nothing gates on the sentinel.**
  `UCraftBenchAttributeSet` does no clamping, so Health can legitimately read 0
  or negative; `-1.0` would be equally ambiguous. All gates run at cp4, by which
  time every sample has been taken - the same reasoning as the poison fixture's
  "guard on the capture TIMES, not the Health values".
- The map (`Content/Maps/gp-health-attribute-ops/L_HealthOps.umap`, once
  authored) places **only the fixture** and sets no `GameModeOverride`, so PIE
  also spawns the substrate's default `BP_ThirdPersonGameMode` pawn at the
  PlayerStart. It is not an `ACraftBenchCharacter` subclass, so it can never win
  pawn resolution and no gate reads it - the graded pawn is exclusively the one
  the fixture spawns and possesses. Same invariant `L_PoisonStack` and
  `L_GlideStamina` rely on.
- **Correlation with `gp-poison-dot-stack-cpp` (constraint C1).** The entire
  stage-1 ladder (HO-1..HO-5) is lifted from that task's fixture - same
  derivation gate, same presence gate, same init-100 read-before-write, same
  37 write probe, same visible-character check, same named FAIL strings. That
  reuse is deliberate (it is why this task costs zero new infra) and it means
  **the two tasks' stage-1 pass populations are correlated**: a model that
  fails stage 1 here fails it there for the same reason, and the two results
  must not be treated as independent evidence. Recorded in `notes.md` and
  carried as constraint C1 in the internal design note (not shipped).
