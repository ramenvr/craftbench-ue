---
id: gp-heal-over-time-cpp
substrate: ThirdPerson
set: cpp
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_HealOverTime :: AHealOverTimeFunctionalTest"]
---

# gp-heal-over-time-cpp

Port of the **BP-G2 source record 47** (`Difficulty: Medium`,
`Before Blueprint: from scratch`), running on the UE 5.8 **ThirdPerson**
substrate. Family **T1.2** of the bp-g2 tier-1 slate
(the internal design note (not shipped)): the agent implements a **restorative
ability** that raises Health periodically for a bounded duration and then
stops, and that **never pushes Health past its cap** - not the value the game
reads back, and not the underlying stored value it accumulates into.

The design contract for this task is `PIN.md` in this folder. It is
**normative**: it fixes the agent-visible prompt (reproduced verbatim below),
the checkpoint schedule, gates HOT-0..HOT-7 with their named FAIL strings, the
anti-gaming list AG-1..AG-7, decisions D1-D5, and - in the binding
`OWNER DECISION 2026-08-10 -- EDIT, then ACCEPTED` block at its end - the
corrected `StopEpsilon`. This spec implements it; it does not redesign it.

Two things make this task different from its sign-flipped ancestor
`gp-poison-dot-stack-cpp`, and both are corrections applied **prospectively**
so the new family does not inherit the exemplar's bugs:

1. **The acceptance band is DISCLOSED** ("any duration in the
   four-to-seven-second range"). Poison gates the same shape and tells the
   agent nothing about the band it is gated against - the F5 defect.
2. **HOT-2 is a pure direction predicate, not a rate bar.** Poison's
   `PeriodicMinStep = 2.0` over a 1.5 s window is an undisclosed
   "> 1.33 HP/s" floor that fails a conforming 1 HP/s effect under a message
   describing something it did not do (owner decision Q5(b)).

> **STATUS: NOTHING HAS BEEN MEASURED.** No build, no PIE run, no reference
> grade, no discrimination sweep has been executed against this task. Every
> numeric bar named below carries `PROPOSED - NOT YET MEASURED` in the fixture
> source (`HealOverTimeFunctionalTest.h`) and in the reference sources, and
> none of them may be treated as calibrated until both populations are
> recorded in `notes.md` with the chosen bar and the margin on each side
> (PIN.md section 6). The calibration record, the exact commands, and the
> blockers below are in `notes.md`.

> **BLOCKER 1 - id/folder mismatch (this spec will `cb lint` ERROR until the
> folder is renamed).** The front-matter `id:` above is `gp-heal-over-time-cpp`
> (PIN.md's own family title `gp-heal-over-time-{cpp,bp}`, and the 2026-08-06
> `-cpp` convention that surface-differentiates a C++ original from its `-bp`
> twin), but the folder is `tasks/bp-g2/gp-heal-over-time/`. `tasks/README.md`
> and `docs/AUTHORING_TEMPLATE.md` both state the front-matter `id` MUST equal
> the folder name, and `tasklint.py::_rule_task_id` raises that as an **ERROR**
> (`task-id-folder`) - and a red `cb lint` masks every later CI suite. **The
> fix is to rename the folder to `tasks/cpp/gp-heal-over-time-cpp/`**, not to
> drop the `-cpp` from the id: a bare `gp-heal-over-time` id is a raw substring
> of the coming `gp-heal-over-time-bp`, which is exactly the prefix-shape
> violation the 2026-08-06 `-cpp` rename dissolved (it blinds `inventory.py`'s
> RAW-SUBSTRING CATALOG check - see the repo conventions). This is the same error that hit
> T1.1 (`gp-health-attribute-ops-cpp`) and was fixed the same way. The **map**
> folder (`Content/Maps/gp-heal-over-time/`) and the **fixture** folder
> (`Source/CraftBenchTests/Tasks/gp-heal-over-time/`) are shared with the
> coming `-bp` twin and correctly stay unsuffixed - `map_locator.locate_map`
> derives the automation prefix from the map's own folder name and never joins
> it to the task id, and the poison pair sets the precedent (its shared fixture
> folder keeps the `-bp` name after the `-cpp` rename; do not "fix" either).

> **BLOCKER 2 - the map binary does not exist yet.** The declared fixture map
> is `Content/Maps/gp-heal-over-time/L_HealOverTime.umap`. That binary is **not
> committed**, so `cb lint` errors and L2 is an explicit FAIL (committed
> binaries are the only map source; the text scaffolders retired 2026-07). The
> one-shot authoring recipe that produces it is `aids/author_L_HealOverTime.py`
> in this folder; it requires `ThirdPersonEditor` to be BUILT first (otherwise
> `/Script/CraftBenchTests.HealOverTimeFunctionalTest` does not exist and
> `load_class` returns None) and a **real off-screen RHI** (map authoring
> crashes under `-nullrhi`). It is **fixture-only placement**: this task is
> pawn-shaped and the fixture spawns and possesses the graded pawn itself.

> **BLOCKER 3 - one new gameplay tag is a hard build prerequisite.**
> `FCraftBenchGameplayTags::AbilityHealOverTime()` (`Ability.HealOverTime`) is
> new for this task (PIN.md D5) and has been landed in
> `UE-projects/ThirdPerson/Source/ThirdPerson/CraftBenchGameplayTags.{h,cpp}`
> alongside the pre-existing `AbilityGlide` / `AbilityPoison` / `AbilityDamage`
> / `AbilityHeal`. The fixture and the reference ability both call it, so
> nothing here compiles without it. The tag is deliberately **distinct from
> `Ability.Heal`** (owned by `gp-health-attribute-ops-cpp`) so
> `PreferredAbilityTag()` stays unique per GAS family (I1.1).

> **BLOCKER 4 - this task is blocked on V1.1 + V1.4.** It is the **first
> consumer** of the base class's dual attribute read
> (`PawnAttribute` / `PawnAttributeBase`, `CraftBenchPawnFunctionalTest.h`).
> HOT-5 is **vacuous** without it - see Hidden invariants. PIN.md section 6
> additionally requires `cb refgate gp-poison-dot-stack-cpp,gp-glide-stamina-cpp`
> green after the base-class extension, proving it changed no existing verdict.

> **GAS-category note.** Like `gp-flight-mode`, `gp-glide-stamina-cpp`,
> `gp-poison-dot-stack-cpp` and `gp-health-attribute-ops-cpp`, this task names
> the GAS **contract** as part of the interface - the documented exception to
> behavior-only prompts (Hard Rule #2), because verifying a periodic,
> duration-bounded restore and its cap *through* an ability system is the
> point. What the exception licenses, and its exact limit: the prompt names
> **an ability system**, **the attribute set type the project provides**, a
> **Health** resource, a **MaxHealth** cap, and **one trigger tag**
> (`Ability.HealOverTime`). It never names the plugin ("GAS" - dropped as a
> name, see Dropped clauses), the classes (`UCraftBenchAttributeSet`,
> `ACraftBenchCharacter`), or the pattern ("GameplayEffect",
> "PreAttributeChange", "PostGameplayEffectExecute"). The clumsy phrase
> "neither the value the game reads back, nor the underlying stored value it
> accumulates into" is deliberate prose, and is discussed under Hidden
> invariants: it exists so HOT-5's FAIL is fair under `TASK-AUTHOR-GUIDE.md`
> section C.

## Primary concept

- `gas-attributes` - Gameplay Attributes and Attribute Sets, raised by a
  **periodic, duration-bounded** GameplayEffect and **clamped against the
  pawn's own MaxHealth on both the current and the base value**
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-attributes-and-attribute-sets-for-the-gameplay-ability-system-in-unreal-engine)

The load-bearing mechanics: an activatable ability, reachable by its own
gameplay tag, that applies a **periodic** effect on a ~1 s cadence for a ~5 s
duration and then **ends**; a per-application total inside the disclosed 10-40
band; and an **invariant** - Health never exceeds MaxHealth - enforced where a
**periodic** modifier actually writes, which is the **base** value. An
uninitialized cap, a tick-driven fake, one instant restore, a permanent
regeneration, a token magnitude, a current-only clamp, a clamp that lowers
Health at full, and an invisible pawn each fail by their own name.

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
> - Deliver your pawn as a subclass of the provided character (C++ or Blueprint)
>   with your ability granted on it.
> - The character must be **visibly represented**: assign one of the provided
>   mannequin skeletal meshes (under `/Game/Characters/`) as your character's
>   mesh, so a reviewer watching the run can see it.
>
> The verifier sets Health to a known value, activates your ability by sending
> that tag, and observes Health over time.

*(The prompt above is reproduced VERBATIM from `PIN.md` section 1 - it is the
signed contract and must not be paraphrased. The coming `-bp` variant adds one
line: "Deliver the pawn as a Blueprint asset under
`/Game/Tasks/gp-heal-over-time-bp/`." - same convention as
`gp-poison-dot-stack-bp`.)*

## Workspace state pre-task

Files that **exist** under `Source/ThirdPerson/` (this substrate's
agent-writable runtime module):

- The stock UE 5.8 Third Person C++ template sources (`ThirdPersonCharacter`,
  game mode, the `Variant_*` trees). No edit needed.
- `ThirdPerson.Build.cs` - already includes `GameplayAbilities`,
  `GameplayTags`, `GameplayTasks`. No edit needed.
- `CraftBenchCharacter.{h,cpp}` - **the base pawn for this family** (PIN.md
  D2): a pawn-owned ability system, the auto-granted `GrantedAbilities` array
  (ships empty), the `CraftBenchPawn` tag, and a **pre-built attribute set**
  (`CreateOptionalDefaultSubobject<UCraftBenchAttributeSet>(TEXT("AttributeSet"))`).
  **Health is pre-built here, so there is no stage-1 ladder in this task** -
  deliberately, so this family does not join the stage-1 correlation set with
  `gp-poison-dot-stack-cpp` and `gp-health-attribute-ops-cpp` (`QUEUE.md`
  constraint C1). Cost of that choice, recorded in PIN.md D2: the agent gets
  Health for free, so the task is slightly easier than the plan's Band-B
  estimate.
- `CraftBenchAttributeSet.{h,cpp}` - the contract attribute set type
  (`Health`, `MaxHealth`, `Power`; **no clamping at v1.0**). `Health` is the
  attribute the verifier reads and the restore must raise; `MaxHealth` is the
  cap it must respect. **`MaxHealth` ships UNINITIALIZED** (it reads **0** -
  there is no initializer anywhere in either substrate), which is exactly why
  HOT-0 exists and must run first.
- `CraftBenchBareCharacter.{h,cpp}` - the *other* families' task base (no
  attribute set). Not used here; a submission may derive from it, but then it
  has no Health and fails HOT-0 by name.
- `CraftBenchGameplayTags.{h,cpp}` - registers `Ability.HealOverTime`
  (`FCraftBenchGameplayTags::AbilityHealOverTime()`) alongside the pre-existing
  `Ability.Glide` / `Ability.Poison` / `Ability.Damage` / `Ability.Heal`. **The
  `AbilityHealOverTime` accessor is NEW for this task** and is a hard build
  prerequisite for both the fixture and the reference (PIN.md D5, Blocker 3).
- The `GameplayAbilities` plugin is enabled.
- `AHealOverTimeFunctionalTest` lives in the verifier-only `CraftBenchTests`
  module (`Source/CraftBenchTests/Tasks/gp-heal-over-time/`). The folder is
  deliberately unsuffixed: the coming `-bp` twin shares this fixture
  byte-identically, exactly as the glide/poison pairs do.
- `Content/Characters/Mannequins/` - the substrate's **native**
  visual-representation content (`SKM_Manny_Simple` / `SKM_Quinn_Simple`, the
  `SK_Mannequin` skeleton). Read-only: `Content/Characters/` is outside the
  writable sandbox; the prompt's visible-character bullet points here.

Files the agent **creates**: a pawn subclass of `ACraftBenchCharacter` that
initializes MaxHealth to 100 and clamps Health against it on **both** the
current and the stored value, plus an ability (C++ or Blueprint) tagged
`Ability.HealOverTime` that raises Health periodically for a bounded duration,
with that ability in the pawn's `GrantedAbilities`. The pawn is resolved **by
derivation plus the preferred tag** and is spawned + possessed by the
verifier - the map places no pawn.

## Verifier specification

Three legs, each with its own preset and its own trigger. The verifier reads
the cap **before any trigger**, then presets Health and activates the ability
once per leg, sampling Health on a checkpoint schedule.

**Shipped fixture (the source of truth for every gate below):**
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-heal-over-time/HealOverTimeFunctionalTest.{h,cpp}`
- 10-checkpoint schedule
`{0.5, 1.6, 3.1, 4.6, 7.6, 9.7, 10.7, 15.8, 17.0, 22.1}`,
`LastCheckpointIndex = 9`, all final assertions at cp9. **Every FAIL string
quoted below is read from that `.cpp`**, not from the PIN sheet.

```text
LEG 1 -- periodic + stop (HOT-2, HOT-3, HOT-4)
  idx 0 (0.5s):  HOT-0 MaxHealth read, BEFORE any trigger and any fixture write
                 HOT-7 visible-character check
                 SetHealth(40)          // HealthPreset -- PIN.md D4
                 Trigger Ability.HealOverTime          (attempt 1 of 3)
  idx 1 (1.6s):  A1    = Health()       // trigger+1.1
  idx 2 (3.1s):  A2    = Health()       // trigger+2.6 -- closes rise window 1 (1.5 s)
  idx 3 (4.6s):  A3    = Health()       // trigger+4.1 -- closes rise window 2 (1.5 s, CONGRUENT)
  idx 4 (7.6s):  AStop = Health()       // trigger+7.1 -- stop window OPENS, PAST the band top
  idx 5 (9.7s):  ATail = Health()       // trigger+9.2 -- stop window closes (2.1 s)

LEG 2 -- the clamp (HOT-5)
  idx 6 (10.7s): SetHealth(95)          // ClampPreset; 95 + 10 > 100 even at the band FLOOR
                 Trigger Ability.HealOverTime          (attempt 2 of 3)
  idx 7 (15.8s): L2Current = PawnAttribute(Health)     // trigger+5.1 -- THE DUAL READ,
                 L2Base    = PawnAttributeBase(Health) //   both at the SAME instant
                 L2MaxLive = PawnAttribute(MaxHealth)  // DIAGNOSTIC ONLY

LEG 3 -- at-max no-op (HOT-6)
  idx 8 (17.0s): SetHealth(100)         // AtMaxPreset
                 Trigger Ability.HealOverTime          (attempt 3 of 3)
  idx 9 (22.1s): L3Current = Health(); L3Base = HealthBase()   // trigger+5.1
                 ALL FINAL ASSERTS

  RiseStep1     = A2 - A1            over (cp1, cp2]  -- 1.5 s
  RiseStep2     = A3 - A2            over (cp2, cp3]  -- 1.5 s, CONGRUENT with the above
  StopRise      = ATail - AStop      over (cp4, cp5]  -- 2.1 s, opens past the band top
  TotalRestored = ATail - 40         one whole application

  HOT-1  : NumGrantedAbilitiesWithTag(Ability.HealOverTime) >= 1 AND it activated
  HOT-1c : HealActivations == HealTriggerAttempts   (all three legs landed)
  HOT-2  : RiseStep1 > RiseEpsilon AND RiseStep2 > RiseEpsilon   (direction + noise floor)
  HOT-3  : StopRise <= StopEpsilon                              (noise floor, 0.25)
  HOT-4  : TotalRestoredMin <= TotalRestored <= TotalRestoredMax (the DISCLOSED 10-40 band)
  HOT-5  : L2Current <= MaxHealthRead + ClampEpsilon
           AND L2Base <= MaxHealthRead + ClampEpsilon           (DUAL read; V1.4)
  HOT-6  : |L3Current - 100| <= AtMaxEpsilon                    (both directions)
```

`TimeLimit` is set by the base class from the last checkpoint plus its margin,
so a stuck test FAILs rather than hanging.

**Reads go through the CURRENT (post-aggregator) value, except in HOT-5 which
reads BOTH.** The fixture's `Health()` helper calls `PawnAttribute(...)` per
the V1.4 law in `CraftBenchPawnFunctionalTest.h`: a restore implemented as a
duration or infinite **aggregator** modifier never touches the base value, so a
base-only read would report zero rise for a conforming implementation and
false-FAIL it at HOT-2. Writes use `ASC->SetNumericAttributeBase` (no base
helper exists), the same call the poison and health-ops fixtures make.

### The eight gates and their exact named FAIL strings

Read from `HealOverTimeFunctionalTest.cpp`. Every string is **ASCII** and every
literal run quoted in the MATRIX column is a **literal substring of one format
string that does not span a `%`-placeholder** - a substring that spanned one
could never match at runtime.

| gate | kind | window | exact FAIL string (from the fixture `.cpp`) | usable MATRIX substring |
|---|---|---|---|---|
| **HOT-0** MaxHealth initialized to 100 | **ABSOLUTE (disclosed)**, 100 +/- `MaxHealthEpsilon` | cp0, before any trigger and any fixture write | `MaxHealth was not initialized: read %.1f, expected 100 (+/- %.2f). The cap the restore must respect is read from the pawn's own MaxHealth attribute; an uninitialized attribute reads 0 and would clamp every restore to zero.` | `MaxHealth was not initialized: read ` |
| **HOT-7** visible character | structural | cp0 | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | the whole string (no placeholder) |
| **HOT-1a** ability granted | structural count | cp9 | `no activatable ability tagged Ability.HealOverTime on the pawn (the restore is not an activatable ability). granted=%d` | `no activatable ability tagged Ability.HealOverTime on the pawn (the restore is not an activatable ability). granted=` |
| **HOT-1b** ability activated | structural latch | cp9 | `an ability tagged Ability.HealOverTime was granted but did NOT activate on TryActivateAbilitiesByTag` | the whole string (no placeholder) |
| **HOT-1c** every activation landed | structural counters | cp9 | `an ability tagged Ability.HealOverTime refused a later activation: %d of %d activations were accepted. The verifier activates the restore once per leg, three legs in one run, and each activation must land its full effect - an ability that is still running when the next activation arrives, or that is on cooldown, is not counted.` | `an ability tagged Ability.HealOverTime refused a later activation: ` |
| **HOT-2** periodic: Health kept rising in steps | **PURE DIRECTION + noise floor** `RiseEpsilon` - explicitly NOT a rate bar | two congruent 1.5 s windows, (cp1,cp2] and (cp2,cp3] | `the restore was not periodic: Health did not keep rising in steps (A1=%.1f A2=%.1f A3=%.1f; each step must rise by more than %.2f). An instant restore rises once then stays flat.` | `the restore was not periodic: Health did not keep rising in steps (A1=` |
| **HOT-3** stops after its duration | **noise floor** `StopEpsilon` = **0.25** (owner EDIT 2026-08-10; was 0.7) | 2.1 s stop window (trigger+7.1, trigger+9.2] | `the restore did not STOP after its duration: Health was still rising in the post-band stop window (AStop=%.1f at trigger+7.1 -> ATail=%.1f at trigger+9.2, rise %.1f > %.2f). The fixture accepts any duration in the 4-7s band; a heal-over-time must end, a permanent regeneration keeps climbing.` | `the restore did not STOP after its duration: Health was still rising in the post-band stop window (AStop=` |
| **HOT-4** total restored inside the disclosed band | **ABSOLUTE (disclosed: 10..40)** | Leg 1, preset(40) -> ATail | `the total restored is outside the stated 10-40 band: Health went 40.0 -> %.1f over one application (total %.1f). The prompt fixes a per-application total between 10 and 40.` | `the total restored is outside the stated 10-40 band: Health went 40.0 -> ` |
| **HOT-5** clamp, **dual read** | **ABSOLUTE (disclosed)**, `<= MaxHealth + ClampEpsilon` on **both** values | Leg 2, cp7 (trigger+5.1) | `the restore pushed Health past its cap: current=%.1f base=%.1f against MaxHealth=%.1f (+/- %.2f). Health must never exceed MaxHealth - neither the value read back nor the underlying stored value.` | `the restore pushed Health past its cap: current=` |
| **HOT-6** at-max no-op | **direction + noise floor**, both ways | Leg 3, cp9 (trigger+5.1) | `activating the restore at full health changed Health: 100.0 -> %.1f (base %.1f). At full health the effect must leave Health at MaxHealth - it must neither push past it nor lower it.` | `activating the restore at full health changed Health: 100.0 -> ` |

Two pre-gates run at **every** checkpoint and are not counted among the eight:
`pawn did not spawn/resolve` and `pawn has no AbilitySystemComponent`.

**HOT-1 is three checks, not one.** `NumGrantedAbilitiesWithTag >= 1`,
`TriggerAbilityByTag` returned true at least once, and - **HOT-1c** - it
returned true on **all three** attempts. The fixture keeps per-tag **counters**
(`HealActivations` / `HealTriggerAttempts`) rather than using the base class's
single `bAbilityActivated` latch, which is an OR across every tag and every
activation. That distinction is load-bearing here in a way it is not on a
single-trigger fixture: UE 5.8 refuses re-activation of an `InstancedPerActor`
ability that is still running (`bRetriggerInstancedAbility` defaults false) and
of any ability whose `CommitAbility` cooldown has not elapsed, returning false
with only a Verbose log. Both are idiomatic GAS shapes, not gaming - but with a
latch, a refused **Leg 2** activation leaves Health parked at the preset of 95
and **HOT-5 passes vacuously**, and a refused **Leg 3** activation makes
**HOT-6 pass vacuously** for the same reason. The two gates this family exists
for would both go green having tested nothing.

### Calibration instrument

The final checkpoint emits **two** `[HEALOVERTIME-FINAL]` lines **before any
gate runs**, so both survive a FAIL:

1. The pinned diagnostic: `granted activated/attempts maxHealth preset1 A1 A2
   A3 AStop ATail total riseStep1 riseStep2 stopRise L2cur L2base L2maxLive
   L3cur L3base` - the cap read, every raw sample from all three legs, every
   computed value and the activation counts, so the real population can be read
   off ONE run.
2. The congruence evidence: `baseline w1..w9` plus every bar value, where
   `w1..w9` are the **realized** window lengths taken from the fixture's
   `CrossingTimes` array (`w2`, `w3` are the congruent rise pair; `w5` is the
   stop window whose tick count the `StopEpsilon` derivation is quantified
   over). HOT-2's shared noise floor and HOT-3's bound both rest on that
   congruence; this line makes the premise **measured evidence** rather than an
   assumption in a comment. `CrossingTimes` is evidence only - no gate reads
   it, and the window lambda is index-guarded.

**Pass criteria** (gated): MaxHealth reads 100 and the pawn is visibly
represented at checkpoint 0, before anything is triggered (each a NAMED FAIL,
never a misattributed "not periodic"); the restore is an ability granted on the
pawn that activates on its tag **on all three legs**; Health rises in **both**
congruent 1.5 s windows (HOT-2); Health is **not** still rising in the
post-band stop window (HOT-3); one application's total lands inside the
disclosed 10-40 band (HOT-4); at a preset of 95 **neither** the current nor the
base value exceeds MaxHealth (HOT-5); and activating at full health leaves
Health at 100 in **both** directions (HOT-6).

> **Design note (relative vs absolute).** HOT-2, HOT-3 and HOT-6 are direction
> predicates with a noise floor. HOT-0, HOT-4 and HOT-5 are absolutes, and
> under `TASK-AUTHOR-GUIDE.md` section C each is lawful **only because the
> prompt states it** - "MaxHealth is **100**", "a total of between **10 and
> 40**". `MaxHealth = 100` is unavoidable as an absolute: a cap **is** an
> absolute, and there is no ratio form of "does not exceed its own maximum".
> **This fixture forms no ratio at all**, so unlike T1.1 there is no
> denominator to guard.
>
> **Why HOT-4 exists at all**, given that HOT-2 and HOT-3 already gate the
> shape: so a non-conforming **magnitude** fails by its own name. An agent that
> restores 1 HP per period would otherwise be told its restore "was not
> periodic" or nothing at all - the F5 failure mode
> (the bp-g2 scale-up plan (not shipped) section 0) reproduced in a new task.
>
> **Why the Leg 1 preset is 40** (PIN.md D4 - "the single highest-risk
> calibration constraint in the family"): 40 is far from **both** boundaries.
> The disclosed per-application total is at most 40, so `40 + 40 = 80 < 100`
> and **no conforming solve can saturate against the cap anywhere inside the
> HOT-2 rise window**. If a later edit raises this preset or widens the total
> band, a conforming restore starts hitting the clamp mid-window, its steps go
> flat, and HOT-2 begins false-FAILing conforming work under the name "the
> restore was not periodic". F3's objection - "a clamp saturates the periodic
> steps" - is real, but it is a **schedule** problem, not a mechanism problem:
> it bites only if the periodic gate and the clamp gate share a leg. They do
> not; Leg 2 is a separate leg with its own preset of 95.

## Reference solution metadata

- LOC range: 150-250 LOC across 4 file pairs (**405 LOC as committed**,
  comments included), all under `Source/ThirdPerson/` (the writable prefix in
  `AGENT_WRITABLE.json`):
  - `HealOverTimePawn.{h,cpp}` - subclasses the **generic**
    `ACraftBenchCharacter` (PIN.md D2), initializes `MaxHealth` **and** `Health`
    to 100 through the `Init*` accessors, grants the ability, and
    constructor-assigns `/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple`
    through a guarded `ConstructorHelpers::FObjectFinder` with the same
    `(0,0,-90)` / `(0,-90,0)` capsule alignment the poison reference uses.
  - `HealOverTimeAttributeSet.{h,cpp}` - **the clamp**. Overrides
    `PreAttributeChange` **and** `PostGameplayEffectExecute`, which is exactly
    the pair PIN.md section 4's "A PASSING solve" sketch names.
    `PreAttributeBaseChange` is deliberately **not** overridden and is
    documented in the header as the equally-correct third route.
  - `HealOverTimeEffect.{h,cpp}` - `DurationPolicy = HasDuration` (5.0 s),
    `Period` 1.0 s, a plain **additive +5.0** Health modifier, and
    `bExecutePeriodicEffectOnApplication = false`. No stacking policy is set:
    this prompt does not ask about stacking, and borrowing poison's stacking
    block would answer a question that was not asked.
  - `HealOverTimeAbility.{h,cpp}` - `InstancedPerActor`, tagged
    `Ability.HealOverTime` via `SetAssetTags`, applies the effect to self on
    activate.
- **The one structural decision worth reading before copying this shape:** the
  pawn derives from the generic `ACraftBenchCharacter`, which **already**
  pre-builds a `UCraftBenchAttributeSet` subobject named `"AttributeSet"`.
  Constructing a *second*, clamping set alongside it would be wrong -
  `GetAttributeSubobject` matches on `IsA`, so two registered sets of the
  contract lineage both answer `GetHealthAttribute()` and which one wins is
  enumeration order. The reference instead **overrides the inherited
  subobject's CLASS** in the constructor initializer list:
  `Super(ObjectInitializer.SetDefaultSubobjectClass<UHealOverTimeAttributeSet>(TEXT("AttributeSet")))`.
  It must be in the initializer list, not the body -
  `AssertIfSubobjectSetupIsNotAllowed` fires for calls made from the
  constructor body.
- **Why `PreAttributeChange` + `PostGameplayEffectExecute` and not
  `PreAttributeChange` alone** - this is HOT-5's whole content. The Health
  modifier is **periodic**, so each execution writes into the **base** value;
  `PreAttributeChange` guards the **current** value only. A current-only clamp
  therefore leaves `PawnAttribute()` reading exactly 100 while
  `PawnAttributeBase()` sits at ~115 - the PIN's plausible-wrong solve
  verbatim. `PostGameplayEffectExecute` runs after the execution and copies the
  honest number down onto the stored one (`SetHealth(ClampHealth(GetHealth()))`
  - the generated `..._VALUE_GETTER` returns the already-clamped current value
  and the `..._VALUE_SETTER` calls `SetNumericAttributeBase`). `PreAttributeChange`
  is still needed on its own account: a duration/infinite **aggregator**
  modifier moves only the current value and never reaches
  `PostGameplayEffectExecute`.
- `ClampHealth` reads `GetMaxHealth()` from the pawn's own attribute, **not a
  constant**, and is deliberately **not** special-cased for `MaxHealth == 0`.
  An uninitialized cap clamping every restore to zero is the honest
  consequence, and **HOT-0 exists to name it**; special-casing it would be
  writing to the gate.
- **The 5.0 s / 1.0 s / +5.0 shape is a reference CHOICE, not a calibrated
  bar** (`PROPOSED - NOT YET MEASURED` in the effect source). With
  `bExecutePeriodicEffectOnApplication = false`, a 5.0 s duration on a 1.0 s
  period executes **five** times (the UE 5.8 default of `true` would execute
  six), so one application restores **25** - the exact midpoint of the
  disclosed 10-40 band, 15 of margin on each side. 5.0 s sits mid-band in the
  disclosed 4-7 s window with 1.0 s below and 2.0 s above.
- **Predicted reference trace** (hand-traced through the shipped schedule,
  **PREDICTED not measured**): Leg 1 `40 -> A1 45 -> A2 50 -> A3 60`,
  `AStop = ATail = 65`; `RiseStep1 = 5`, `RiseStep2 = 10`, `StopRise = 0.0`,
  `TotalRestored = 25` inside `[10, 40]`. Leg 2: current **100.0**, base
  **100.0**. Leg 3: **100.0**. PASS on all nine checks. **If the first real run
  does not reproduce this line for line, stop and find out why before touching
  a bar.**
- Senior-dev hours: 1.5-2.5 hours.
- A Blueprint reference (BP pawn parenting the generic character + BP effect +
  BP ability, with the clamp in a BP attribute-set route) is the equivalent
  deliverable; the verifier resolves a BP pawn via the asset registry. The
  `-bp` variant will mandate it, and PIN.md section 6 requires `ClampEpsilon`
  to be measured against **three** solves - this C++ reference, a BP
  magnitude-calculation lane, and a BP ability-loop lane - because calibrating
  it against the C++ reference alone is exactly how HOT-5 would false-FAIL a
  conforming BP solve (PIN.md D1).

## Anti-gaming notes

1. **AG-1 - leave MaxHealth at its default 0**, so "never exceeds the cap" is
   trivially satisfiable in the wrong direction. *Failure mode*:
   `UCraftBenchAttributeSet` ships `MaxHealth` uninitialized, so a pawn that
   never sets it has a cap of **zero**; a clamp written against it then clamps
   every restore to nothing, and Leg 1 shows no rise at all. *Defense*:
   **HOT-0**, at checkpoint 0 **before any trigger and before any fixture
   write**, reads MaxHealth and requires 100 +/- 0.5. Without it, that
   submission presents as "the restore was not periodic" - a misattributed FAIL
   on work whose only fault is one missing initializer. *Discrimination
   variant* (**PLANNED, NOT YET COMMITTED**): `discrimination/no-maxhealth/`
   -> HOT-0.
2. **AG-2 - restore Health from Tick or BeginPlay with nothing activatable.**
   *Failure mode*: the number moves in the right direction on the right
   cadence, but there is no ability the game can start by tag. *Defense*:
   **HOT-1** reads the ability system - `NumGrantedAbilitiesWithTag(
   Ability.HealOverTime) >= 1` **and** `TriggerAbilityByTag` must have returned
   true - and **HOT-1c** additionally requires that **every** one of the three
   per-leg activations landed, so a silently refused re-activation cannot leave
   HOT-5 or HOT-6 passing vacuously. *Discrimination variant* (**PLANNED**):
   `discrimination/tick-regen/` -> HOT-1 (`granted=0`).
3. **AG-3 - one instant restore of the full amount, dressed as an ability.**
   *Failure mode*: an `Instant` effect applied on activate. It is granted, it
   activates, the total lands inside the band, and it stops (there was never
   anything running) - it fails only the *periodic* requirement. *Defense*:
   **HOT-2** samples two **congruent 1.5 s** rise windows and requires a rise
   in **each**: an instant restore rises once and is then flat, so its second
   step is 0. *Discrimination variant* (**PLANNED**):
   `discrimination/instant-restore/` -> HOT-2.
4. **AG-4 - permanent regeneration that never expires.** *Failure mode*: an
   `Infinite` effect, or a timer with no end - it passes HOT-2 with room to
   spare and looks conforming for the whole rise window. *Defense*: **HOT-3**
   samples a **2.1 s stop window that opens at trigger+7.1, past the top of the
   disclosed 4-7 s band**, so a conforming duration leaves zero legitimate
   ticks inside it and `StopEpsilon` absorbs jitter only. **This is the gate
   the owner's 2026-08-10 EDIT was about**: at the sheet's proposed
   `StopEpsilon = 0.7` the gate did not defend AG-4 at all (see Hidden
   invariants for the derivation). *Discrimination variant* (**PLANNED**):
   `discrimination/permanent-regen/` -> HOT-3, tuned - as poison's
   `permanent-drain/` was - to hide inside every other tolerance.
5. **AG-5 - clamp only the value the game reads while the stored value
   overshoots**, or "clamp" by *setting* Health to MaxHealth (which **lowers**
   it whenever Health was already above). *Failure mode*: the
   `PreAttributeChange`-only recipe is what every GAS tutorial shows and is
   what "Health must never exceed MaxHealth" reads like to a competent
   engineer. It passes HOT-0 through HOT-4, HOT-6 and HOT-7. *Defense*:
   **HOT-5**'s **dual read** - current AND base, both at the same instant, both
   against the cap - and **HOT-6**, which gates the at-max no-op in **both**
   directions. **This is the headline discriminator of the task**; PIN.md
   section 4 calls it "the one a real model writes". *Discrimination variants*
   (**PLANNED**): `discrimination/current-only-clamp/` -> HOT-5,
   `discrimination/set-to-max/` -> HOT-6.
6. **AG-6 - restore a token 1 HP so every window technically rises.** *Failure
   mode*: conforming shape, meaningless magnitude - it would otherwise pass
   HOT-2 and HOT-3 and be indistinguishable from real work. *Defense*:
   **HOT-4** bounds the whole per-application total into the **disclosed**
   10-40 band, so a non-conforming magnitude fails **by its own name** rather
   than being misattributed to HOT-2 or HOT-3 (the F5 failure mode; the same
   role HO-8 plays on T1.1). *Discrimination variant* (**PLANNED**):
   `discrimination/token-restore/` -> HOT-4.
7. **AG-7 - a meshless pawn**: behaviorally conforming, invisible on the film
   strip, ungradable by a human reviewer. **Measured 2026-08-04 on the glide
   family: 9/9 matrix reps shipped meshless pawns.** *Defense*: **HOT-7**, the
   checkpoint-0 visible-character gate - a skeletal or static mesh component
   with a mesh **actually assigned** must exist on the graded pawn. Structural
   and deterministic; the fixture-level twin of the `-bp` variant's L2I
   `pawn_visibly_represented` check. *Discrimination variant* (**PLANNED**):
   `discrimination/no-mesh/` -> HOT-7.

## Hidden invariants

- **Why the acceptance band is DISCLOSED here when poison does not disclose
  its equivalent.** `gp-poison-dot-stack-cpp` gates a ~5 s duration against an
  acceptance band of roughly 4-7 s that **appears nowhere in its prompt**: an
  agent that reads "roughly five seconds" and ships 8 s fails a gate it was
  never told the shape of, and the FAIL it gets describes a stop that did not
  happen rather than a duration outside a band. That is the **F5 defect**
  (the bp-g2 scale-up plan (not shipped) section 0). The correction is applied here
  **prospectively** - the prompt states "The verifier accepts any duration in
  the four-to-seven-second range" in as many words - so this family does not
  inherit the exemplar's bug. Disclosure is also what makes the band lawful to
  gate on: under `TASK-AUTHOR-GUIDE.md` section C an absolute bar is
  permissible only when the prompt states it. The same reasoning covers the
  other two disclosed absolutes, the 10-40 total and `MaxHealth = 100`, and it
  is why HOT-4 exists as a separate named gate rather than being folded into
  HOT-2/HOT-3. The cost is recorded honestly in `bp-g2-verifier-extensions.md`
  section 3a: this family carries **more section C under-specification debt
  than poison**, because restoring the clamp gate (P1) required pinning four
  numbers in the prompt.
- **Why HOT-0 must be the FIRST gate, before any trigger and before any
  fixture write** (PIN.md D3). `UCraftBenchAttributeSet` ships `MaxHealth`
  **uninitialized** - it reads **0**, and there is no initializer anywhere in
  either substrate. A submission that never sets it has a cap of zero, so a
  correctly-written clamp against that cap clamps **every** restore to nothing.
  Leg 1 then shows no rise at all, and without HOT-0 that presents as **"the
  restore was not periodic"** - a misattributed FAIL on a submission whose only
  fault is one missing initializer, told it got the mechanism wrong when it got
  the mechanism right. This is the poison stage-1 lesson applied here.
  Ordering matters twice more: HOT-0 runs before the Leg 1 **preset write**, so
  the read is the submission's own initialization and not the fixture's; and
  HOT-5 later gates against `MaxHealthRead` - the value HOT-0 already pinned -
  rather than a live re-read, so a submission cannot raise its own cap at
  activation time and clear the clamp gate by moving the goalposts. The live
  value is logged as `L2maxLive` so that divergence is visible rather than
  silently absorbed.
- **Why HOT-5 reads BOTH the current and the base value, at the same instant.**
  A `PreAttributeChange`-only clamp writes `CurrentValue` only
  (`AttributeSet.cpp:94-95`). The restore is **periodic**, and a periodic
  execution writes into the **base** value. So with the Leg 2 preset of 95 and
  a conforming total, `GetNumericAttribute` reads a clean **100.0** while the
  stored base has accumulated to **~115**: the submission passes a current-only
  gate while shipping a health system that **silently absorbs the next 15
  points of damage**. Reading only the current value makes HOT-5 **vacuous**
  against the single most-documented wrong recipe in the ecosystem
  (`bp-g2-verifier-extensions.md` section 1a M3) - which is precisely why this
  family was blocked on **V1.4** and is its first consumer. Both values are
  read at the **same checkpoint** so they cannot be reconciled by timing, and
  the FAIL message prints both numbers so the defect is legible without a
  debugger. **HOT-6 deliberately gates the CURRENT value only** and merely
  *reports* the base: PIN.md section 4 states that the plausible-wrong solve
  passes HOT-0..HOT-4, HOT-6 and HOT-7 and dies **at HOT-5** - if HOT-6 also
  gated the base, two gates would fire on one defect and HOT-5 would stop being
  the named cause, collapsing the sheet's own discrimination story.
- **The `StopEpsilon` derivation, quantified over ALL admissible periods**
  (the binding `OWNER DECISION 2026-08-10 -- EDIT, then ACCEPTED`;
  `StopEpsilon` 0.7 -> **0.25**). What HOT-3 must defeat is AG-4, a **permanent
  regeneration that never expires**. Such a submission must still pass HOT-2,
  so with per-tick magnitude `m` and period `p` it must satisfy
  `nRise(p) * m > RiseEpsilon` in **each** of the two 1.5 s rise windows, i.e.
  `m > RiseEpsilon / min(nRise(p))`. Across the 2.1 s stop window that same
  submission gains `nStop(p) * m`, so HOT-3 has teeth for that period exactly
  while

  ```text
  StopEpsilon < ( nStop(p) / min(nRise(p)) ) * RiseEpsilon
  ```

  and it has teeth against **every** permanent regeneration only while

  ```text
  StopEpsilon < RiseEpsilon * min over all admissible p of ( nStop(p) / min(nRise(p)) ).
  ```

  **The sheet's original factor of 1.4 was the wrong quantity.** It came from
  the window **LENGTH** ratio `2.1 s / 1.5 s` - reasoning as if tick density
  scaled continuously with window length. **It does not: ticks are discrete**,
  and a period can be phased so the longer window carries no more ticks than
  the shorter one. Minimising `nStop(p) / min(nRise(p))` over **every**
  admissible period on a 1 ms grid against **this** schedule gives a global
  minimum of exactly **1.000**, and that minimum is **attained** - e.g. a
  period of **0.576 s** puts **3** ticks in each 1.5 s rise window and **3** in
  the 2.1 s stop window. So the lawful bound is
  `StopEpsilon < 1.000 * RiseEpsilon = 0.50`, and the sheet's proposed **0.7
  sat above it**: a permanent regeneration tuned to the slowest rate HOT-2
  still admits leaves `>= 0.5` of rise in the stop window, and `0.5 <= 0.7`
  **PASSES** - HOT-3 would not have defended AG-4 at all, in a family authored
  specifically not to inherit that bug (it is poison's Leg-A defect
  reproduced). **0.25** is pinned midway between the conforming population
  (**0.0** - a restore that actually stops leaves exactly zero rise in a window
  that opens **past** the disclosed band top, so no legitimate expiry tick can
  land inside it) and the 0.50 bound: equal margin each side, the
  `StackRatioMax` form. **RE-PINNING LAW:** `StopEpsilon` is **coupled** to
  `RiseEpsilon` and to all three window lengths and cannot be moved
  independently. Changing `RiseEpsilon`, either rise window length, or the stop
  window length invalidates the 1.000 factor, and the whole minimisation must
  be redone over the new schedule. Assuming a tick count instead of quantifying
  over the period is precisely the defect the owner edit fixes.
- **Why the two gated rise windows are congruent.** `(cp1,cp2]` and
  `(cp2,cp3]` are both 1.5 s at equal offsets from the same trigger. HOT-2
  compares two step sizes against **one shared** noise floor, and the
  `StopEpsilon` bound above is quantified against the **smaller** of the two
  rise windows' tick counts - both arguments require the windows to be the same
  length, which is what makes the tick-count quantization identical in each.
  Unequal windows are exactly what kept the poison fixture's stack cap
  ungateable until they were made congruent. The realized lengths are logged on
  the second `[HEALOVERTIME-FINAL]` line, so the premise is measured evidence
  rather than an assumption in a comment.
- **`PreferredAbilityTag()` returns `Ability.HealOverTime`, and that is what
  disambiguates pawn resolution.** `ResolveAgentPawnClass` prefers the
  candidate whose CDO `GrantedAbilities` contains an ability whose **asset
  tags** carry the fixture's preferred tag; without the override, any other
  committed `ACraftBenchCharacter` subclass (the glide pawn, the poison pawn,
  the health-ops pawn) could win purely by enumeration order. The tag is
  **unique per GAS family** (PIN.md D5, I1.1) - deliberately not the
  pre-existing `Ability.Heal`, which `gp-health-attribute-ops-cpp` already
  owns - and that uniqueness is precisely what lets all of those pawns stay
  committed alongside this one.
- **There is no derivation gate, and that is a decision, not an omission**
  (PIN.md D2). This family derives from the **generic** `ACraftBenchCharacter`,
  whose attribute set is pre-built, so Health is free and there is no stage-1
  ladder. Routing it through `ACraftBenchBareCharacter` instead would make this
  a **third** member of the stage-1 correlation set with
  `gp-poison-dot-stack-cpp` and `gp-health-attribute-ops-cpp`, and constraint
  **C1** in `QUEUE.md` would grow to a three-way exclusion - costing tier 1 a
  usable graded cell. The price is that the task is slightly easier than the
  plan's Band-B estimate. A submission that derives from the *bare* character
  instead has no Health system and dies at **HOT-0** by name (`PawnAttribute`
  returns 0.0 for an absent attribute), which is the truthful message for it.
- **Samples initialize to `0.0`, and nothing gates on a sentinel.**
  `UCraftBenchAttributeSet` does no clamping of its own, so Health can
  legitimately read 0 or negative and `-1.0` would be equally ambiguous. All
  gates run at cp9, by which time every sample has been taken - the same
  reasoning as the poison fixture's "guard on the capture TIMES, not the Health
  values".
- **The map (`Content/Maps/gp-heal-over-time/L_HealOverTime.umap`, once
  authored) places ONLY the fixture** and sets no `GameModeOverride`, so PIE
  also spawns the substrate's default `BP_ThirdPersonGameMode` pawn at the
  PlayerStart. It is not an `ACraftBenchCharacter` subclass, so it can never
  win pawn resolution and no gate reads it - the graded pawn is exclusively the
  one the fixture spawns and possesses. Same invariant `L_PoisonStack`,
  `L_GlideStamina` and `L_HealthOps` rely on.
- **The braced checkpoint literal in the fixture is load-bearing to a tool
  outside the verifier.** `aura_rig/checkpoint_states.py` statically parses
  `SetCheckpointSchedule\s*\(\s*\{([^}]*)\}` out of the fixture source for
  per-frame time labels; a schedule built into a `TArray` variable would demote
  every checkpoint label to index-only. Keep the literal braces.
