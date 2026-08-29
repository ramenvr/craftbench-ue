---
id: gp-double-jump-stamina-cpp
substrate: ThirdPerson
set: cpp
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_DoubleJump :: ADoubleJumpStaminaFunctionalTest"]
---

# gp-double-jump-stamina-cpp

Re-author of the **BP-G2 source record 33** (`Description: Movement-1`,
`Difficulty: medium`, `Before Blueprint: from scratch`), running on the UE 5.8
**ThirdPerson** substrate. Family **T1.3** of the bp-g2 tier-1 slate
(the internal design note (not shipped)): the agent implements an **activatable
ability that reverses a fall** - a second jump taken mid-air, charged **once**
against the character's `Power` resource, and **refused outright** when that
resource is below the cost.

The design contract for this task is `PIN.md` in this folder. It is
**normative**: it fixes the agent-visible prompt (reproduced verbatim below),
the two-leg checkpoint schedule, the gates and their named FAIL strings, the
anti-gaming list, decisions D1-D6, and - in the binding
`OWNER DECISION 2026-08-10 -- EDIT, then ACCEPTED` block at its end - **the cut
of gate DJ-6** and **one mandatory addition to the fixture diagnostic**. This
spec implements it; it does not redesign it.

**What the owner decision changed, and what it added:**

1. **DJ-6 ("only ONE extra jump per airborne period") is CUT.** It has no gate,
   no constant and no counter anywhere in the fixture, and AG-7 is re-recorded
   below as an **ARGUED** note pointing at DJ-2c rather than claiming a defense
   it does not have. See `## Dropped clauses`.
2. **`DescribeSegments()` is MANDATORY in the diagnostic.** I1.4 has never
   executed, so the first reference run of this task is also the first test of
   the segmenter that DJ-2c gates on. A wrong decomposition must be visible in
   the log rather than silently mis-gating.

> **STATUS: NOTHING HAS BEEN MEASURED.** No build, no PIE run, no reference
> grade, no discrimination sweep has been executed against this task. Every
> numeric bar named below carries `PROPOSED - NOT YET MEASURED` in the fixture
> source (`DoubleJumpStaminaFunctionalTest.h`) and in the reference sources, and
> none of them may be treated as calibrated until both populations are recorded
> in `notes.md` with the chosen bar and the margin on each side (PIN.md section
> 6). The calibration record, the exact commands, and the blockers below are in
> `notes.md`.

> **BLOCKER 1 - id/folder mismatch (this spec will `cb lint` ERROR until the
> folder is renamed).** The front-matter `id:` above is
> `gp-double-jump-stamina-cpp` (PIN.md's own family title
> `gp-double-jump-stamina-{cpp,bp}`, and the 2026-08-06 `-cpp` convention that
> surface-differentiates a C++ original from its `-bp` twin), but the folder is
> `tasks/bp-g2/gp-double-jump-stamina/`. `tasks/README.md` and
> `docs/AUTHORING_TEMPLATE.md` both state the front-matter `id` MUST equal the
> folder name, and `tasklint.py::_rule_task_id` raises that as an **ERROR**
> (`task-id-folder`) - and a red `cb lint` masks every later CI suite. **The fix
> is to rename the folder to `tasks/cpp/gp-double-jump-stamina-cpp/`**, not to
> drop the `-cpp` from the id: a bare `gp-double-jump-stamina` id is a raw
> substring of the coming `gp-double-jump-stamina-bp`, which is exactly the
> prefix-shape violation the 2026-08-06 `-cpp` rename dissolved (it blinds
> `inventory.py`'s RAW-SUBSTRING CATALOG check - see the repo conventions). **This is the
> same error that hit T1.1 (`gp-health-attribute-ops-cpp`) and T1.2
> (`gp-heal-over-time-cpp`), and it was fixed the same way both times.** The
> **map** folder (`Content/Maps/gp-double-jump-stamina/`) and the **fixture**
> folder (`Source/CraftBenchTests/Tasks/gp-double-jump-stamina/`) are shared
> with the coming `-bp` twin and correctly stay unsuffixed -
> `map_locator.locate_map` derives the automation prefix from the map's own
> folder name and never joins it to the task id, and the poison pair sets the
> precedent (its shared fixture folder keeps the `-bp` name after the `-cpp`
> rename; do not "fix" either).

> **BLOCKER 2 - the map binary does not exist yet.** The declared fixture map is
> `Content/Maps/gp-double-jump-stamina/L_DoubleJump.umap`. That binary is **not
> committed**, so `cb lint` errors and L2 is an explicit FAIL (committed binaries
> are the only map source; the text scaffolders retired 2026-07). The one-shot
> authoring recipe that produces it is `aids/author_L_DoubleJump.py` in this
> folder; it requires `ThirdPersonEditor` to be BUILT first (otherwise
> `/Script/CraftBenchTests.DoubleJumpStaminaFunctionalTest` does not exist and
> `load_class` returns None) and a **real off-screen RHI** (map authoring crashes
> under `-nullrhi`). It is **fixture-only placement**: this task is pawn-shaped
> and the fixture spawns and possesses the graded pawn itself. **Unlike every
> other task in this family the map's FLOOR is inside the graded window** - the
> pawn is dropped from z=1200 and lands during Leg 2. See Hidden invariants
> ("The floor is inside the schedule") and the header of the aids script.

> **BLOCKER 3 - one new gameplay tag is a hard build prerequisite.**
> `FCraftBenchGameplayTags::AbilityDoubleJump()` (`Ability.DoubleJump`) is new
> for this task (PIN.md D5) and has been landed in
> `UE-projects/ThirdPerson/Source/ThirdPerson/CraftBenchGameplayTags.{h,cpp}`
> alongside the pre-existing `AbilityGlide` / `AbilityPoison` / `AbilityDamage` /
> `AbilityHeal` / `AbilityHealOverTime`. The fixture and the reference ability
> both call it, so nothing here compiles without it. The tag is deliberately
> **distinct from every other ability tag in the substrate** so
> `PreferredAbilityTag()` stays unique per GAS family (I1.1). This is the
> **fourth** of the four tier-1 tags; the bp-g2 scale-up plan (not shipped) I1.5 budgeted 3.

> **BLOCKER 4 - this task is blocked on I1.4, and is its FIRST CONSUMER.**
> `SetDenseSampling` / `Segments` / `NumRises` / `MeanVerticalRate` /
> `DescribeSegments` on `ACraftBenchPawnFunctionalTest` had **zero callers across
> both substrates** as of 2026-08-10, and so did the five older reductions this
> fixture also uses (`MaxVelocityZAfter` in particular). Only `RecordSample` had
> ever run, and only from the glide fixture's 9-point **checkpoint-sparse**
> schedule. PIN.md D1 is explicit: **treat the entire existing sampler as
> untested code.** DJ-2c gates on a derived segment count, so if the
> decomposition is wrong the gate is wrong **silently, in either direction** -
> which is why `DescribeSegments()` in the diagnostic is mandatory and why the
> first reference run must be read, not trusted. See Hidden invariants.

> **GAS-category note.** Like `gp-flight-mode`, `gp-glide-stamina-cpp`,
> `gp-poison-dot-stack-cpp`, `gp-health-attribute-ops-cpp` and
> `gp-heal-over-time-cpp`, this task names the GAS **contract** as part of the
> interface - the documented exception to behavior-only prompts (Hard Rule #2),
> because verifying an activatable, tag-triggered, resource-gated impulse
> *through* an ability system is the point. What the exception licenses, and its
> exact limit: the prompt names **an ability system**, a **Power** resource, the
> pawn's **granted abilities**, and **one trigger tag** (`Ability.DoubleJump`).
> It never names the plugin ("Gameplay Ability System" - dropped as a name, see
> Dropped clauses), the classes (`UCraftBenchAttributeSet`,
> `ACraftBenchCharacter`), the third-party type the source row named
> (`GSCAttributeSet`), or the pattern ("GameplayEffect", "cost", "LaunchCharacter").

## Primary concept

- `gas-abilities` - Gameplay Abilities activated by tag, applying a **movement
  impulse** through `CharacterMovementComponent` and **gated on a Gameplay
  Attribute** as a one-shot cost
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-ability-system-for-unreal-engine)

The load-bearing mechanics: an activatable ability, reachable by its own gameplay
tag and granted on the pawn; a **real vertical velocity reversal** (not a
teleport, not a slowed fall) taken from a genuine free fall; a cost that is
**charged once** at the disclosed magnitude; and a cost that is a **gate** -
below it the ability does nothing at all and the resource is not driven negative.
A movement-component fake, a teleport, a cancelled impulse, the reused glide
answer, a free jump, a wrong-sized debit, a per-tick drain, an ungated cost and
an invisible pawn each fail by their own name.

## Prompt given to the agent

> The project provides a character pawn that already owns an ability system, a
> depletable **Power** resource, and an array of abilities to grant.
>
> Implement an **ability** that gives the character a **second jump while it is
> already falling through the air**. When the game activates it mid-fall, the
> character's descent must **reverse and carry it upward again** -- a real
> upward impulse it then falls back down from, not a teleport and not a slowed
> fall.
>
> - Tag the ability `Ability.DoubleJump` and add it to the pawn's granted
>   abilities, so the game can trigger the second jump by that tag.
> - Activating it **costs 20 Power**, debited **once** per activation. It must
>   not drain Power continuously while the character is airborne.
> - If the character has **less than 20 Power**, the ability must **not fire**:
>   no second jump, and Power must not go negative.
> - Deliver your pawn as a subclass of the provided character (C++ or Blueprint)
>   with your ability granted on it.
> - The character must be **visibly represented**: assign one of the provided
>   mannequin skeletal meshes (under `/Game/Characters/`) as your character's
>   mesh, so a reviewer watching the run can see it jump.
>
> The verifier drops the character from a height, waits until it is falling,
> then activates your ability by sending that tag and observes the resulting
> motion and Power.

*(The prompt above is reproduced VERBATIM from `PIN.md` section 1 - it is the
signed contract and must not be paraphrased. In particular "**reverse and carry
it upward again**" is load-bearing prose and is NOT interchangeable with "launch
the character upward": PIN.md section 4 states that under the looser wording the
plausible-wrong solve is arguably conforming and DJ-2b's FAIL would be unfair,
so DJ-2b would have to be downgraded to advisory and the family would lose its
load-bearing discriminator. The coming `-bp` variant adds one line: "Deliver the
pawn as a Blueprint asset under `/Game/Tasks/gp-double-jump-stamina-bp/`." -
same convention as `gp-poison-dot-stack-bp`.)*

## Workspace state pre-task

Files that **exist** under `Source/ThirdPerson/` (this substrate's
agent-writable runtime module, confirmed writable in `AGENT_WRITABLE.json`):

- The stock UE 5.8 Third Person C++ template sources (`ThirdPersonCharacter`,
  game mode, the `Variant_*` trees). No edit needed.
- `ThirdPerson.Build.cs` - already includes `GameplayAbilities`, `GameplayTags`,
  `GameplayTasks`. No edit needed.
- `CraftBenchCharacter.{h,cpp}` - **the base pawn for this family**: a pawn-owned
  ability system, the auto-granted `GrantedAbilities` array (ships empty), the
  `CraftBenchPawn` tag, and a **pre-built attribute set**
  (`CreateOptionalDefaultSubobject<UCraftBenchAttributeSet>(TEXT("AttributeSet"))`),
  which is what holds `Power`. It sets no capsule size, no `GravityScale` and no
  `JumpZVelocity`, so the stock `ACharacter` values apply.
- `CraftBenchAttributeSet.{h,cpp}` - the contract attribute set type (`Health`,
  `MaxHealth`, `Power`; **no clamping at v1.0**). `Power` is the only attribute
  this task reads. **It is deliberately NOT extended** (PIN.md D6).
- `CraftBenchBareCharacter.{h,cpp}` - the *other* families' task base. **This
  lineage suppresses the attribute-set subobject entirely**, so a submission that
  derives from it has no `Power` at all; its readings are 0.0 and it dies at
  DJ-3a by name.
- `CraftBenchGameplayTags.{h,cpp}` - registers `Ability.DoubleJump`
  (`FCraftBenchGameplayTags::AbilityDoubleJump()`). **NEW for this task** and a
  hard build prerequisite for both the fixture and the reference (Blocker 3).
- The `GameplayAbilities` plugin is enabled.
- `ADoubleJumpStaminaFunctionalTest` lives in the verifier-only `CraftBenchTests`
  module (`Source/CraftBenchTests/Tasks/gp-double-jump-stamina/`). The folder is
  deliberately unsuffixed: the coming `-bp` twin shares this fixture
  byte-identically, exactly as the glide/poison pairs do.
- `Content/Characters/Mannequins/` - the substrate's **native**
  visual-representation content (`SKM_Manny_Simple` / `SKM_Quinn_Simple`, the
  `SK_Mannequin` skeleton). Read-only: `Content/Characters/` is outside the
  writable sandbox; the prompt's visible-character bullet points here.

Files the agent **creates**: a pawn subclass of `ACraftBenchCharacter` carrying
an assigned mannequin mesh, plus an ability (C++ or Blueprint) tagged
`Ability.DoubleJump` in that pawn's `GrantedAbilities` that, on activation,
**refuses below 20 Power**, otherwise **debits exactly 20 once** and applies a
**real upward vertical impulse**. The pawn is resolved **by derivation plus the
preferred tag** and is spawned + possessed by the verifier - the map places no
pawn.

## Verifier specification

Two legs in one world, each with its own Power preset and its own trigger. The
pawn is **dropped from z=1200** so that Leg 1 observes a real fall; the fixture
never touches gravity, never injects input, and never calls `World->Tick` or
`Actor->Tick`.

**Shipped fixture (the source of truth for every gate below):**
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-double-jump-stamina/DoubleJumpStaminaFunctionalTest.{h,cpp}`
- 10-checkpoint schedule `{0.4, 0.7, 1.0, 1.3, 1.6, 1.9, 2.4, 2.7, 3.0, 3.3}`,
`LastCheckpointIndex = 9`, all final assertions at cp9. **Every FAIL string
quoted below is read from that `.cpp`**, not from the PIN sheet.

**`SetDenseSampling(true)` is called in `PrepareTest` - I1.4's first execution
anywhere.** One sample per tick, so at the runner's `-FPS=60` a jump arc is ~70
samples instead of ~4. `OnCheckpoint` therefore deliberately does **not** call
`RecordSample`: the dense path already samples every tick, and a second append at
the checkpoint instant would put two samples at nearly the same `T` for no gain.

```text
LEG 1 -- the jump + the cost (DJ-2a/2b/2c, DJ-3a/3b/3c)
  idx 0 (0.4s):  DJ-7 visible-character check (before anything else)
  idx 1 (0.7s):  VZAtTrigger = Pawn->GetVelocity().Z     // LIVE, read FIRST
                 TriggerTime = t
                 SetPower(60)  -> read back as evidence
                 Trigger Ability.DoubleJump              (Leg-1 attempt 1 of 1)
  idx 2 (1.0s):  PowerFirstAfter + PowerFirstAfterBase   // trigger+0.3; DJ-3c OPENS
  idx 3 (1.3s):  (dense sampling only)
  idx 4 (1.6s):  (dense sampling only)
  idx 5 (1.9s):  PowerAtPlus12                           // trigger+1.2; DJ-3c CLOSES

LEG 2 -- the refusal (DJ-4)
  idx 6 (2.4s):  CAPTURE EVERY LEG-1 REDUCTION FIRST -- this order IS the window:
                   MaxVZLegOne       = MaxVelocityZAfter(TriggerTime)
                   MinZLegOne        = MinZAfter(TriggerTime)
                   LegOneSegmentsDesc= DescribeSegments(RiseEpsilon)
                   LegOneRisesRaw    = NumRises(RiseEpsilon)       // EVIDENCE ONLY
                   LegOneRises       = |{Seg : bRising, DeltaZ>=RiseEpsilon,
                                          EndT > TriggerTime}|     // DJ-2c GATE INPUT
                 THEN start Leg 2:
                   RefusalTriggerTime = t
                   SetPower(5); seed MinPowerLegTwo = 5
                   Trigger Ability.DoubleJump            (Leg-2 attempt 1 of 1)
  idx 7 (2.7s):  Power sample -> MinPowerLegTwo
  idx 8 (3.0s):  Power sample -> MinPowerLegTwo
  idx 9 (3.3s):  Power sample + base; ALL FINAL GATES

  LegTwoRises = |{Seg : bRising, DeltaZ >= RiseEpsilon,
                  StartT >= RefusalTriggerTime - SegmentBoundarySlack}|  // DJ-4 GATE INPUT
  Debited     = 60 - PowerFirstAfter                    // DJ-3a / DJ-3b
  FurtherDrop = PowerFirstAfter - PowerAtPlus12         // DJ-3c

  DJ-1  : NumGrantedAbilitiesWithTag(Ability.DoubleJump) >= 1
          AND LegOneActivations == LegOneTriggerAttempts
  DJ-2a : VZAtTrigger < -MinFallSpeed                   (direction + noise floor)
  DJ-2b : MaxVZLegOne > 0.0                             (PURE DIRECTION, no magnitude)
  DJ-2c : LegOneRises >= 1                              (PURE SHAPE)
  DJ-3a : Debited > PowerEpsilon                        (direction + noise floor)
  DJ-3b : |Debited - 20| <= CostTol                     (ABSOLUTE, DISCLOSED)
  DJ-3c : FurtherDrop <= PowerEpsilon                   ("stopped changing")
  DJ-4  : IF LegOneRises >= 1 THEN NOT (LegTwoRises >= 1
                                        OR MinPowerLegTwo < -PowerEpsilon)
          ELSE SKIPPED, not failed                      (see Hidden invariants)
```

`TimeLimit` is set by the base class from the last checkpoint plus its margin
(3.3 + 2.0 = **5.3 s**), so a stuck test FAILs rather than hanging. That is also
this task's in-world floor cost per L2 rep - by far the cheapest leg in the
family (heal-over-time costs 24.1 s, poison 30.6 s).

**Every Power read goes through the CURRENT (post-aggregator) value**, per the
V1.4 law in `CraftBenchPawnFunctionalTest.h`: a cost implemented as a duration or
infinite **aggregator** modifier never touches the base value, so a base-only
read would report no debit for a conforming implementation and false-FAIL it at
DJ-3a. The **base** values are read at the same instants as evidence only
(`PowerFirstAfterBase`, `PowerLegTwoLastBase`) and **no gate reads either**.
Writes use `ASC->SetNumericAttributeBase` (no base-write helper exists), the same
call the poison, health-ops and heal-over-time fixtures make.

### The gates and their exact named FAIL strings

Read from `DoubleJumpStaminaFunctionalTest.cpp` after C++ literal concatenation.
Every string is **ASCII** and every literal run quoted in the MATRIX column is a
**literal substring of one format string that does not span a `%`-placeholder** -
a substring that spanned one could never match at runtime.

| gate | kind | window | exact FAIL string (from the fixture `.cpp`) | usable MATRIX substring |
|---|---|---|---|---|
| **DJ-7** visible character | structural | cp0, before anything else | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | the whole string (no placeholder) |
| **DJ-1a** ability granted | structural count | cp9, FIRST of the final gates | `no activatable ability tagged Ability.DoubleJump on the pawn (the second jump is not an activatable ability). granted=%d` | `no activatable ability tagged Ability.DoubleJump on the pawn (the second jump is not an activatable ability). granted=` |
| **DJ-1b** Leg-1 activation landed | structural **per-leg counter** | cp9 | `an ability tagged Ability.DoubleJump was granted but did NOT activate on TryActivateAbilitiesByTag` | the whole string (no placeholder) |
| **DJ-2a** really falling pre-trigger | **direction + noise floor** (`MinFallSpeed` 100 cm/s) - **HARNESS SANITY** | live read at cp1, before the preset and the trigger | `no falling baseline: the character was not descending when the ability was triggered (vZ=%.0f, need vZ < -%.0f). The second jump is only meaningful from a fall.` | `no falling baseline: the character was not descending when the ability was triggered (vZ=` |
| **DJ-2b** a real upward impulse | **PURE DIRECTION** - `MaxVelocityZAfter(TriggerTime) > 0`, no magnitude at all | Leg 1, samples strictly after the trigger | `the ability produced no upward impulse: the highest vertical velocity after the trigger was %.0f, never positive. A real second jump reverses the descent; a teleport leaves vZ at whatever gravity produced.` | `the ability produced no upward impulse: the highest vertical velocity after the trigger was ` |
| **DJ-2c** a segmented SECOND rise | **PURE SHAPE** - leg-filtered `Segments(RiseEpsilon)`, `RiseEpsilon` 20 cm | Leg 1, realized (0.7, ~2.38] | `the character did not rise a second time: Z fell to %.0f and never climbed back by more than %.1f before the leg ended. A one-shot upward velocity that is immediately cancelled, or a slowed fall, looks like this.` | `the character did not rise a second time: Z fell to ` |
| **DJ-3a** Power was debited | **direction + noise floor** (`PowerEpsilon` 0.5) | preset(60) -> trigger+0.3 | `the second jump cost no Power: Power went %.1f -> %.1f across the activation (delta %.2f). The ability must debit the character's Power.` | `the second jump cost no Power: Power went ` |
| **DJ-3b** the cost is exactly 20 | **ABSOLUTE (DISCLOSED: 20)**, +/- `CostTol` 1.0 | preset(60) -> trigger+0.3 | `the second jump did not cost 20 Power: Power went 60.0 -> %.1f (debited %.1f, need 20.0 +/- %.1f). The prompt fixes the cost at 20.` | `the second jump did not cost 20 Power: Power went 60.0 -> ` |
| **DJ-3c** ONE-SHOT, not a continuous drain | **"stopped changing"** + `PowerEpsilon` | (trigger+0.3, trigger+1.2], 0.9 s | `the Power cost is a continuous drain, not a one-shot debit: Power kept falling after the activation (%.1f at trigger+0.3 -> %.1f at trigger+1.2, further drop %.2f > %.2f). The cost must be charged once per activation.` | `the Power cost is a continuous drain, not a one-shot debit: Power kept falling after the activation (` |
| **DJ-4** refusal below the cost | **PURE DIRECTION x2**, **SKIP-vs-FAIL** | Leg 2, preset(5), start-keyed segments | `the ability fired without paying for it: with only 5.0 Power (below the 20 cost) the character still rose a second time (Z climbed %.0f) and/or Power went negative (%.1f). Below the cost the ability must not fire.` | `the ability fired without paying for it: with only 5.0 Power (below the 20 cost) the character still rose a second time (Z climbed ` |

Two pre-gates run at **every** checkpoint and are not counted among the nine:
`pawn did not spawn/resolve` (a hard FAIL) and - deliberately **not** a FAIL - a
missing `AbilitySystemComponent`, which is left to DJ-1 to name. Stealing that
FAIL earlier would report a non-GAS submission under a generic harness-shaped
name; instead every write is individually ASC-guarded, every read goes through
`PawnAttribute()` (which returns 0.0 rather than crashing), and **DJ-1 runs first
among the final gates** so no Power gate can be reached on a pawn whose readings
are meaningless.

**DJ-6 has no representation anywhere in the fixture** - no gate, no constant, no
counter. It was CUT (owner decision 2026-08-10; see Dropped clauses).

**Relative-vs-absolute accounting.** Eight of the nine gates are **pure direction
or shape predicates**: "was it falling", "did vZ ever go positive", "did Z rise
after a local minimum", "did Power stop moving", "did it refuse". None depends on
a magnitude the prompt does not state, and **none can be moved by the agent's
choice of jump height or impulse strength**. The **one real absolute is DJ-3b
(cost = 20)**, lawful under `TASK-AUTHOR-GUIDE.md` section C only because the
prompt says "**costs 20 Power**" in those words - which is also the one number
the source row itself specifies. `RiseEpsilon`, `PowerEpsilon`, `MinFallSpeed`
and `CostTol` are **floors, not bars**: they separate signal from jitter and must
be pinned from measured jitter under `-deterministic -FPS=60`, never chosen.

**This fixture forms NO ratio and performs NO division**, so unlike T1.1 there is
no denominator to guard, and none may be introduced without also introducing the
guard. The one division-shaped construct is the diagnostic's `Window()` lambda,
which subtracts two `CrossingTimes` entries and is index-guarded rather than
trusted; `MeanVerticalRate`'s own division is guarded inside the base class and
its result is diagnostic only.

### Calibration instrument

The final checkpoint emits **two** `[DOUBLEJUMP-FINAL]` lines **before any gate
runs**, so both survive a FAIL, plus one `[DJ-REFUSE-DIAG]` line.

1. **30 values on one line**: both legs' activation counts, `vZatTrigger`, the
   Leg-1-windowed and the unwindowed max vZ (`maxVZlegOne` / `maxVZtail` - they
   differ exactly when Leg 2 produced upward velocity, which is DJ-4's business
   and must never satisfy DJ-2b), `minZlegOne`, **all four rise counts**
   (`legOneRises`, `legOneRisesRaw`, `legTwoRises`, `risesAll`), both rise
   heights, every Power sample **including the two evidence-only BASE reads**,
   `debited`, `furtherDrop`, both mean vertical rates, and both trigger times.
   Enough to read the real population off a **single** run.
2. **`DescribeSegments()` for BOTH the Leg-1 window and the full series** - the
   owner's mandatory addition - plus `samples=N`, the nine **realized** checkpoint
   gaps `w1..w9` from `CrossingTimes`, and every bar labelled
   `PROPOSED - NOT YET MEASURED`. The `w` values make the schedule's timing
   premises (DJ-3c's 0.9 s window; D3's 1.7 s inter-leg gap) **measured evidence**
   rather than assumptions in a comment. `CrossingTimes` is evidence only; no gate
   reads it.
3. `[DJ-REFUSE-DIAG]`, emitted **before any gate in both branches**, naming
   whether DJ-4 is hard-gated or SKIPPED and why.

**Pass criteria** (gated): the pawn is visibly represented at cp0; the second
jump is an ability granted on the pawn that **activated on Leg 1**; the pawn was
genuinely descending at the trigger; the highest vertical velocity after the
trigger is **positive**; Z **rose again** by more than `RiseEpsilon` after
bottoming out; Power **decreased**, by **exactly 20** +/- `CostTol`, and then
**stopped decreasing**; and at 5 Power the ability **did not fire** - no Leg-2
rise and no negative Power.

## Reference solution metadata

- **252 LOC as committed** (comments included) across 2 file pairs, all under
  `Source/ThirdPerson/` (the writable prefix in `AGENT_WRITABLE.json`; the bp-g2
  ports stay flat per the repo conventions):
  - `DoubleJumpPawn.{h,cpp}` (81 LOC) - subclasses **`ACraftBenchCharacter`**,
    **not** the Bare lineage: this family is not health-first and Bare suppresses
    the very attribute set that holds `Power`. Null-checked
    `AttributeSet->InitPower(100)`, `GrantedAbilities.Add(UDoubleJumpAbility::StaticClass())`,
    and a guarded `ConstructorHelpers::FObjectFinder<USkeletalMesh>` on
    `/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple` with the same
    `-90 Z / -90 yaw` capsule alignment the poison reference uses.
    Ctor-time init (the heal-over-time shape, not glide's `BeginPlay`): it is live
    before `BeginPlay` and uses the **initter**, which runs no attribute-set hooks.
  - `DoubleJumpAbility.{h,cpp}` (171 LOC) - `InstancedPerActor`, asset-tagged
    `Ability.DoubleJump` via `SetAssetTags` (what **both**
    `NumGrantedAbilitiesWithTag` and `TryActivateAbilitiesByTag` read).
    `ActivateAbility`: `CommitAbility` -> resolve ASC + `ACharacter` avatar ->
    **gate** (`Power < 20` -> `EndAbility(cancelled)`, **no debit, no impulse,
    Power untouched**) -> **one-shot debit**
    (`SetNumericAttributeBase(Power, Current - 20)`, no timer, nothing held open)
    -> **impulse** (`SetMovementMode(MOVE_Falling)` then `CMC->Velocity.Z = 600`)
    -> `EndAbility`.
- **Ending synchronously is what lets Leg 2 re-trigger it.**
  `bRetriggerInstancedAbility` defaults false and only bites an instance that is
  still running; an ability that held itself open across the 1.7 s inter-leg gap
  would be refused at Leg 2 for a reason that has nothing to do with the cost -
  which DJ-4 accepts leniently, but which would make the reference stop testing
  what it is for.
- **The impulse is ASSIGNED, not added, and the `.cpp` says why in prose.**
  Mid-fall the character carries a large negative vZ, so the
  `LaunchCharacter(..., bZOverride = false)` shape adds into it and can leave the
  velocity still negative. Assignment makes the reversal **independent of descent
  speed**. This is the reference's answer to PIN.md section 4's plausible-wrong
  solve, and it is the single most important line to read before copying the shape.
- **The impulse arithmetic** (world gravity is the UE default **-980 cm/s^2**: the
  whole `ThirdPerson/Config` tree has zero `gravity` hits and
  `ACraftBenchCharacter`'s ctor never touches `CharacterMovement`, so
  `GravityScale` is the stock 1.0):
  - A reversal to `+v` rises `h = v^2 / 1960`, **independent of how fast it was
    falling** (because it replaces rather than adds). `h(600) = 183.7 cm`.
  - Against `RiseEpsilon` = 20 cm that is a **9.2x margin**. The smallest impulse
    that merely *touches* 20 cm is `sqrt(2*980*20) = 198.0 cm/s`, so 600 sits
    **3.0x above the cliff in velocity terms** and the margin degrades
    quadratically, not linearly.
  - Time to apex `600/980 = 0.612 s` -> at `-FPS=60` that is **~37 dense samples
    inside the rising run**. This is the part that matters for I1.4 specifically:
    `MinDeltaZ` absorption is designed to swallow *short* direction flips, and a
    37-sample monotonic run cannot be mistaken for jitter.
  - Discretization error on the sampled apex is at most `g*dt^2/2 = 0.14 cm`,
    **0.7% of the 20 cm floor**.
  - First dense sample strictly after the trigger reads `600 - 980/60 = +583.7
    cm/s` - unambiguously positive for DJ-2b's pure-direction test.
  - 600 is a plausible jump velocity on its own terms (stock `ACharacter`
    `JumpZVelocity` is 420-700 across the templates), so it is **not a number
    reverse-engineered from a bar**.
- **Predicted reference trace** (hand-traced against the shipped schedule,
  **PREDICTED not measured**): free-fall gives `vZ = -686` and `z ~ 960` at the
  trigger (**DJ-2a**); the rise reaches `z ~ 1144` at `t ~ 1.31` (**DJ-2b**,
  **DJ-2c**); back to `z ~ 975` at `t = 1.90`; still airborne at `z ~ 564` at the
  Leg-2 trigger; **lands at `t ~ 2.78`**. Power `60 -> 40` at trigger+0.3 and flat
  at trigger+1.2 (**DJ-3a/3b/3c**); Leg 2 stays at `5.0` with no rise (**DJ-4**).
  **The segment decomposition at `MinDeltaZ = 20`, hand-traced through the real
  `Segments()` walk (`CraftBenchPawnFunctionalTest.cpp:527-599`), is
  `[FALL (pre-trigger) | RISE d=+184 | FALL]`, i.e. `NumRises(20) == 1` - see
  Hidden invariants, and read that entry before believing any DJ-2c verdict.**
  **If the first real run does not reproduce this line for line, stop and find
  out why before touching a bar.**
- CONSTANTS: `PowerCost = 20` (lawful absolute - the prompt discloses it),
  `JumpImpulseZ = 600`, `DoubleJumpInitialPower = 100`. All three carry an
  explicit `PROPOSED - NOT YET MEASURED` marker in-file. The initial Power is
  documented as **non-observable** - the verifier presets Power itself before each
  leg - so it cannot be a hidden bar.
- Senior-dev hours: 1.5-2.5 hours.
- A Blueprint reference (BP pawn parenting the provided character + a BP ability
  tagged `Ability.DoubleJump`) is the equivalent deliverable; the verifier
  resolves a BP pawn via the asset registry. The `-bp` variant will mandate it,
  and `RiseEpsilon` must be measured against a **BP lane** as well as this C++
  one before it is called calibrated - calibrating a shape floor against one
  impulse is how DJ-2c would false-FAIL a conforming BP solve.

## Anti-gaming notes

1. **AG-1 - implement the second jump in the character movement component or on
   input, with nothing activatable by tag.** *Failure mode*: the character rises
   on cue and the motion is perfect, but there is no ability the game can start
   by tag - and a pawn with no ability system at all lands here too. *Defense*:
   **DJ-1**, which is two checks - `NumGrantedAbilitiesWithTag(Ability.DoubleJump)
   >= 1` **and** a **per-leg activation counter** proving the Leg-1
   `TryActivateAbilitiesByTag` actually landed. *Discrimination variant*
   (**PLANNED, NOT YET COMMITTED**): `discrimination/cmc-jump/` -> DJ-1
   (`granted=0`).
2. **AG-2 - teleport the character upward instead of applying an impulse.**
   *Failure mode*: `SetActorLocation(+300 Z)` moves the character up and reads,
   in code, as a second jump. *Defense*: **DJ-2b** - a position teleport leaves
   vZ at whatever gravity produced (negative), so the highest vertical velocity
   after the trigger is never positive. **DJ-2c** catches the variant DJ-2b
   cannot: a one-shot upward *velocity* that is immediately cancelled, which
   shows a positive vZ sample but no travel. *Discrimination variants*
   (**PLANNED**): `discrimination/teleport-up/` -> DJ-2b,
   `discrimination/cancelled-impulse/` -> DJ-2c.
3. **AG-3 - reuse the glide answer: slow the descent instead of reversing it.**
   *Failure mode*: a defensible misreading of "second jump" that is also the
   nearest neighbour task in the same slate, so a model that has seen
   `gp-glide-stamina-cpp` is actively primed for it. `vZ` stays negative
   throughout. *Defense*: **DJ-2b**. *Discrimination variant* (**PLANNED**):
   `discrimination/slow-fall/` -> DJ-2b.
4. **AG-4 - a free double jump (no debit), or a cosmetic debit of the wrong
   size.** *Defense*: **DJ-3a** (Power strictly decreased, direction + noise
   floor) and **DJ-3b** (the debit is the **disclosed** 20, +/- `CostTol`).
   DJ-3b exists as a separate named gate so a wrong **magnitude** fails by its
   own name instead of being misattributed - the F5 discipline. *Discrimination
   variants* (**PLANNED**): `discrimination/free-jump/` -> DJ-3a,
   `discrimination/wrong-cost/` -> DJ-3b.
5. **AG-5 - charge the cost as a per-tick drain while airborne**, which
   technically "consumes stamina". *Failure mode*: it passes DJ-3a outright and
   passes DJ-3b at the first sample, so it is invisible to every other gate.
   *Defense*: **DJ-3c**, a pure "stopped changing" predicate over
   (trigger+0.3, trigger+1.2] - i.e. **after** the debit has landed, so a correct
   one-shot cost contributes exactly nothing to that window. *Discrimination
   variant* (**PLANNED**): `discrimination/drain-cost/` -> DJ-3c.
6. **AG-6 - debit Power but never actually gate on it**: the jump fires at 5
   Power and the resource goes negative. *Failure mode*: the deliverable shape is
   right, the tag is right, the debit is right, and it passes **every gate above**.
   *Defense*: **DJ-4**, the refusal leg. **This is the gate that makes the task
   about a resource *cost* rather than about a subtraction**, and it is why PIN.md
   D2 added the refusal clause to the prompt. *Discrimination variant*
   (**PLANNED**): `discrimination/ungated-cost/` -> DJ-4.
7. **AG-7 - unlimited air jumps while Power lasts. ARGUED, NOT DEFENDED.**
   *Status*: **there is no gate for this and DJ-6 was CUT** (owner decision
   2026-08-10). *The argument*: the source row says "double jump", which
   **implies** exactly one extra jump, but the prompt as written does not say it,
   and a solve that allows repeated air jumps while Power lasts is a defensible
   reading of "costs 20 per activation". Gating it would enforce an undisclosed
   limit. What partially covers it anyway: **DJ-2c** requires a segmented rise
   *after a local minimum*, so an implementation that simply never lets the
   character fall cannot satisfy it; and **DJ-3b + DJ-3c** still make every
   activation cost exactly 20, once. **This entry is recorded so the gap is
   explicit rather than assumed covered** - do not read the AG list as claiming a
   defense here.
8. **AG-8 - a meshless pawn**: behaviorally conforming, invisible on the film
   strip, ungradable by a human reviewer. **Measured 2026-08-04 on the glide
   family: 9/9 matrix reps shipped meshless pawns.** *Defense*: **DJ-7**, the
   checkpoint-0 visible-character gate - a skeletal or static mesh component with
   a mesh **actually assigned** must exist on the graded pawn. Structural and
   deterministic; the fixture-level twin of the `-bp` variant's L2I
   `pawn_visibly_represented` check. *Discrimination variant* (**PLANNED**):
   `discrimination/no-mesh/` -> DJ-7.

## Hidden invariants

- **Why DJ-4 is SKIP-vs-FAIL, and why the guard is the contract rather than the
  ordering** (PIN.md D3, endorsed verbatim by the owner decision: "DJ-4's
  skip-vs-fail is right and must not be 'simplified'"). DJ-4 may hard-FAIL **only
  when DJ-2c passed on Leg 1**. If Leg 1 never established a second rise, then
  Leg 2's "it did not rise" observation proves **nothing about refusal** - the
  ability may simply not work at all - and failing there would report a
  **second-jump defect under a resource-gating name**, which is the exact
  misattribution class this repo treats as the worst defect (a wrong verdict that
  looks like a right one, and never files an incident). The fixture therefore
  guards the hard FAIL on an **explicit `bLegOneRose`**, deliberately *not*
  relying on DJ-2c's early return sitting above it: **the guard is the contract,
  the ordering is an accident of layout**, and a later reorder must not silently
  convert a skip into a FAIL. In both branches a `[DJ-REFUSE-DIAG]` line is
  emitted **before any gate**, naming which branch was taken and why - so the skip
  is legible in the log rather than inferred from a missing failure. Same
  discipline as glide's window-honest gate (5) under `ResumeWindowFloor`.
  **A second, unavoidable ambiguity, accepted in the LENIENT direction:** an
  ability with a cooldown that also happens to block the Leg-2 re-trigger is
  indistinguishable from a correct cost gate. It can only make DJ-4 pass, never
  fail. Leg 2 therefore sits **1.7 s** after the Leg-1 trigger; if calibration
  finds conforming solves using longer cooldowns, **DJ-4 moves to a fresh fall
  rather than tightening**. Relatedly, the **Leg-2 activation counter is evidence,
  never a gate**: a refusal there is the *conforming* answer, so lifting
  heal-over-time's "every attempt must land" check (HOT-1c) would contradict DJ-4
  outright and hard-FAIL correct work. Only the **Leg-1** counter is gated (DJ-1b).
- **Why `RiseEpsilon` doubles as the segmenter's `MinDeltaZ`, and why they can
  never be two constants** (owner decision, endorsed explicitly). DJ-2c's noise
  floor is passed straight through as `Segments()` / `NumRises()` /
  `DescribeSegments()`' `MinDeltaZ`. That parameter is what **absorbs apex
  jitter**: the segmenter closes a monotonic run only once the run that would
  replace it has itself moved `MinDeltaZ`
  (`CraftBenchPawnFunctionalTest.cpp:560-586`). Without that absorption **one
  noisy sample at the apex splits a single jump into three segments** - rise,
  micro-fall, rise - and the count reads **2 rises for ONE jump**: a **false PASS
  on the exact axis DJ-2c exists to defend**. So the floor and the segmenter's
  tolerance must be **the same number** and must be **re-pinned together**.
  **RE-PINNING HAZARD, BOTH DIRECTIONS.** Too LOW: apex jitter splits one jump in
  two (false PASS at DJ-2c) and a spurious Leg-2 rise becomes a **false FAIL at
  DJ-4**. Too HIGH: a conforming but **gentle** second jump - the prompt fixes no
  jump height, deliberately - rises less than the floor and is failed for not
  jumping. **The second direction is the unforgivable one**, and it is why this
  constant must be pinned against a **measured population of conforming impulses**,
  not against the 600 cm/s reference alone.
- **I1.4 had never executed before this task, so the reference run is also the
  sampler's first test.** `SetDenseSampling` / `Segments` / `NumRises` /
  `MeanVerticalRate` / `DescribeSegments` had **zero callers** across both
  substrates as of 2026-08-10, and neither had the five older reductions this
  fixture uses (`MaxVelocityZAfter`, `ApexDeltaZ`, `RoseThenFell`,
  `ReachedMovementMode`, `VelocityZNear`). Only `RecordSample` had ever run, and
  only from the glide fixture's checkpoint-sparse schedule. **DJ-2c gates on a
  derived quantity**, and a derived quantity can be wrong **silently, in either
  direction**, with nothing in a PASS/FAIL verdict saying so. That is the entire
  reason `DescribeSegments()` in the diagnostic is *mandatory* and not merely
  nice: a human must read what the segmenter **actually saw** on the first run
  instead of trusting it. What a wrong decomposition looks like: one jump printed
  as `RISE | FALL | RISE` with a micro-`FALL` of a few cm at the apex
  (`RiseEpsilon` too low), or a real second jump swallowed into one long `FALL`
  (`RiseEpsilon` too high). Dense sampling itself is **opt-in and default OFF**
  precisely so that turning it on here changes nothing for glide or poison - their
  series stay byte-identical, so I1.6's numeric-invariance check is a **re-run,
  not a re-calibration**.
- **A conforming double jump on THIS task produces exactly ONE rise, not two -
  and the base class's own doc comment says otherwise.** `NumRises`'s header
  comment (`CraftBenchPawnFunctionalTest.h:168-171`) reads *"a single jump is 1, a
  double jump is 2"*. That is true only for a pawn that **jumped from the ground
  first**. Here the verifier **drops** the pawn: there is no first jump, so a
  conforming series decomposes as `[FALL | RISE | FALL]` and `NumRises(20) == 1`.
  The fixture is correct - it gates `LegOneRises >= 1` - but **anyone "fixing" the
  gate to `>= 2` to match that doc comment would false-FAIL every conforming
  solve, including the reference**. This is the single most likely way this family
  false-FAILs. The `legOneRisesRaw` / `risesAll` values are printed alongside the
  gate input for exactly this reason: they are an independent cross-check on the
  segmenter's first-ever execution, and they must agree with `legOneRises` except
  for rises that ended **before** the trigger.
- **DJ-2c's gate input is leg-filtered `Segments(RiseEpsilon)`, not raw
  `NumRises()`.** Dense sampling starts at **spawn**, so the series also covers
  the pre-trigger free-fall; an unfiltered count would credit a **pre-trigger
  rise** - an auto-jump on `BeginPlay` - as "rose a second time" without the pawn
  ever responding to the ability. `NumRises()` is still called and logged as
  `legOneRisesRaw`, as evidence only.
- **The leg-boundary rules are deliberately ASYMMETRIC, on one stated principle:
  each leg gets the rule whose boundary error points toward PASS.** DJ-2c fails on
  the **ABSENCE** of a rise, so Leg 1 is **inclusive** (`EndT > TriggerTime`) - a
  start-keyed filter would drop the real jump whenever the local minimum opening
  it sits one frame before the trigger's world time, i.e. a **false FAIL on
  conforming work**. It cannot let a pre-trigger rise in: such a rise *ends*
  before the trigger, and DJ-2a independently asserts the pawn was still
  descending when the ability fired. DJ-4 fails on the **PRESENCE** of a rise, so
  Leg 2 is **exclusive** (`StartT >= RefusalTriggerTime - SegmentBoundarySlack`) -
  a Leg-1 rise that somehow ran long must not leak in and fail a submission that
  never jumped twice. `SegmentBoundarySlack` (0.10 s) is **not a bar and not a
  physical quantity**: the base fires `OnCheckpoint` from `Tick` *before*
  appending that tick's dense sample, so a leg-bounding extremum can legitimately
  sit up to one frame (~0.017 s at `-FPS=60`) on the wrong side of the trigger's
  world time. 0.10 s is several frames of headroom and still **orders of magnitude
  short of the 1.7 s between the legs**, so it cannot make one leg's motion
  reachable from the other.
- **The realized Leg-1 window is (0.7, ~2.38], not the sheet's (0.7, 1.9] - a
  deliberate, lenient-only divergence.** `MaxVelocityZAfter` / `NumRises` /
  `Segments` / `DescribeSegments` all read the **whole** series and take **no
  upper time bound**, so a two-leg fixture cannot window them by argument. Rather
  than hand-roll a windowed variant of each in a subclass (which would violate the
  "push shared machinery down into the base" rule), the fixture evaluates every
  Leg-1 reduction **at cp6, before the Leg-2 preset and re-trigger** - the base's
  `Tick` fires `OnCheckpoint` *before* appending that tick's dense sample, so the
  series there ends one frame short of `t = 2.4` and **the series itself is the
  window**. The realized window is a **superset** of the sheet's, and only in the
  lenient direction: the extra ~0.5 s is post-apex free-fall, which can add a
  `FALL` segment but **not a `RISE`**, and can only **lower** a maximum vertical
  velocity. Recorded here rather than silently absorbed, because the sheet states
  the narrower window.
- **The floor is inside the schedule - this is the one task in the family where
  the map's geometry is graded-window-relevant.** The pawn is dropped from
  `z = 1200` onto `Template_Default`'s floor, so at spawn there is ~12 m of
  clearance and DJ-2a's falling baseline is comfortable. But the pawn **lands
  before the run ends**: the reference (`+600` impulse) touches down at
  `t ~ 2.78`, between cp7 and cp8; a **minimally-conforming gentle impulse** - the
  ~198-200 cm/s that just clears `RiseEpsilon` - reaches apex sooner and lands at
  `t ~ 2.25`, i.e. **before the Leg-2 trigger at 2.4**. Three consequences, none
  of which is a false-FAIL path today but all of which must be read off the first
  run's `DescribeSegments()`:
  (1) **Landing sits inside DJ-4's start-keyed window.** UE's walking-mode floor
  adjustment moves the capsule up by at most `MAX_FLOOR_DIST` (~2.4 cm), and
  `CharacterMovement` moves **swept**, so there is no deep-penetration pop. That is
  ~8x under `RiseEpsilon` = 20 cm, so DJ-4 is sound - **but the margin is against
  the floor, not against jitter**, and the fixture header's re-pinning hazard note
  discusses only apex jitter. **Lowering `RiseEpsilon` below ~5 cm would make
  landing itself fail DJ-4 on conforming work.**
  (2) For a gentle conforming solve, **Leg 2 is a GROUND leg, not a fall leg**, so
  DJ-4 tests "refuses from the ground" rather than "refuses mid-fall". That is
  lenient-only (DJ-4 fails on the *presence* of a rise, and an ungated ability
  jumping from the ground still rises and is still caught), but the sheet's Leg-2
  premise implicitly assumes the pawn is airborne. Recorded, not fixed.
  (3) It is also **why cutting DJ-6 was right on its own merits**: "only one extra
  jump per airborne period" needs a guaranteed ground contact to define "per
  airborne period", and on this map the ground contact time is a **function of the
  submission's impulse strength** - i.e. the very magnitude the prompt refuses to
  fix. The map could not have guaranteed the axis DJ-6 would have gated.
- **`PreferredAbilityTag()` returns `Ability.DoubleJump`, and that is what
  disambiguates pawn resolution.** `ResolveAgentPawnClass` prefers the candidate
  whose CDO `GrantedAbilities` contains an ability whose **asset tags** carry the
  fixture's preferred tag; without the override, any other committed
  `ACraftBenchCharacter` subclass (glide, poison, health-ops, heal-over-time)
  could win purely by **enumeration order**. The tag is **unique per GAS family**
  (PIN.md D5, I1.1), and that uniqueness is precisely what lets all of those pawns
  stay committed alongside this one.
- **The per-leg activation counters, and why the base class's latch is not
  enough.** `bAbilityActivated` is a single OR across every tag and every
  activation, so it cannot tell "Leg 1 activated" from "Leg 1 was silently refused
  and Leg 2 activated". Under that latch a **refused Leg-1 activation** surfaces
  as **DJ-2b, "the ability produced no upward impulse"** - a *motion* defect
  reported for a submission whose actual fault is that the trigger never activated
  at all. DJ-1b names it instead. UE 5.8 legitimately refuses re-activation of a
  still-running `InstancedPerActor` ability and of one whose `CommitAbility`
  cooldown has not elapsed - both idiomatic GAS, not gaming - which is exactly why
  the **Leg-2** counter is deliberately left ungated.
- **Samples initialize to `0.0`, and nothing gates on a sentinel** - except
  `MinPowerLegTwo`, which is seeded to `TNumericLimits<double>::Max()` and set to
  the Leg-2 **preset** at the preset itself, then mapped back to that preset if it
  was never sampled. That is what keeps DJ-4's "Power went negative" half from
  firing off a leg that never ran: an unsampled Leg 2 reads back the positive
  value the fixture wrote, which is not negative. `UCraftBenchAttributeSet` does no
  clamping of its own, so Power can legitimately read 0 or negative and `-1.0`
  would be equally ambiguous as a sentinel.
- **The map (`Content/Maps/gp-double-jump-stamina/L_DoubleJump.umap`, once
  authored) places ONLY the fixture** and sets no `GameModeOverride`, so PIE also
  spawns the substrate's default `BP_ThirdPersonGameMode` pawn at the PlayerStart.
  It is not an `ACraftBenchCharacter` subclass, so it can never win pawn
  resolution and no gate reads it - the graded pawn is exclusively the one the
  fixture spawns and possesses. Same invariant `L_PoisonStack`, `L_GlideStamina`,
  `L_HealthOps` and `L_HealOverTime` rely on.
- **The braced checkpoint literal in the fixture is load-bearing to a tool outside
  the verifier.** `aura_rig/checkpoint_states.py` statically parses
  `SetCheckpointSchedule\s*\(\s*\{([^}]*)\}` out of the fixture source for
  per-frame time labels; a schedule built into a `TArray` variable would demote
  every checkpoint label to index-only. Keep the literal braces.
