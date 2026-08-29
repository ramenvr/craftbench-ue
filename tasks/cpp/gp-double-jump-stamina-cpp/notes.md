# gp-double-jump-stamina-cpp - implementor notes + calibration record

> **NOTHING IN THIS FILE HAS BEEN MEASURED.**
>
> As of authoring (2026-08-10) this task has never been built, never been run in
> PIE, never graded a reference, and never run a discrimination sweep. No UBT
> invocation, no `UnrealEditor` launch, no `cb` command and no test suite has
> been executed against it - deliberately, because sibling agents were authoring
> concurrently and the UBT mutex is **engine-keyed**, so a build started here
> returns exit 1 with no compile error in someone else's graded matrix.
> **Every numeric bar below is `PROPOSED - NOT YET MEASURED`** and carries that
> exact phrase in the fixture source (`DoubleJumpStaminaFunctionalTest.h`) and in
> the reference sources. Bars in this repo are pinned by MEASURING; until the
> "What must be measured" section below is worked through and its results written
> back here, **no bar in this task is calibrated and no run of it is evidence of
> anything.**
>
> **This task carries one extra layer of unprovenness that its siblings do not:
> the SAMPLER it gates on has also never executed.** See "I1.4 is on trial here
> too" below. A green PASS on the first run is *not* by itself evidence that
> DJ-2c works - the decomposition has to be read.

## Provenance

- Source: BP-G2 **source record 33** (`Description: Movement-1`,
  `Difficulty: medium`, `Before Blueprint: from scratch`, `Category: Full
  Prompt`). Its `Prompt` cell uses **CRLF** line breaks in the source, unlike
  record 29. All its cells are in `PIN.md` section 1's drop table and summarised
  in `task.md`'s `## Dropped clauses`.
- Family **T1.3** of the bp-g2 tier-1 slate (the internal design note (not shipped)).
  **Budgeted as a RE-AUTHOR, not a port** - the row names `GSCAttributeSet`, a
  GAS Companion type that exists in neither substrate, so nothing could be lifted.
- The signed design contract is `PIN.md` in this folder. It is **normative**: it
  fixes the agent-visible prompt (reproduced verbatim in `task.md`), the two-leg
  checkpoint schedule, the gates and their named FAIL strings, the anti-gaming
  list, decisions D1-D6, and - in the binding `OWNER DECISION 2026-08-10 -- EDIT,
  then ACCEPTED` block at its end - **the cut of DJ-6** and **the mandatory
  `DescribeSegments()` diagnostic**. This file records **calibration, not
  design**; a bar change is a PIN edit first.

## Blockers before anything can be measured

1. **The task folder must be renamed** to
   `tasks/cpp/gp-double-jump-stamina-cpp/`. The front-matter `id` is
   `gp-double-jump-stamina-cpp` and `tasklint.py::_rule_task_id` raises
   `task-id-folder` as an **ERROR** when it does not equal the folder name. A red
   `cb lint` masks every later CI suite, so this is the first thing to fix. Do
   **not** solve it by dropping the `-cpp`: a bare `gp-double-jump-stamina` id
   would be a raw substring of the coming `gp-double-jump-stamina-bp` and would
   re-open the prefix-shape violation the 2026-08-06 `-cpp` rename dissolved.
   **This is the exact error that hit T1.1 (`gp-health-attribute-ops-cpp`) and
   T1.2 (`gp-heal-over-time-cpp`), and it was fixed the same way both times.**
   The **map** folder (`Content/Maps/gp-double-jump-stamina/`) and the **fixture**
   folder (`Source/CraftBenchTests/Tasks/gp-double-jump-stamina/`) are shared with
   the coming `-bp` twin and correctly stay unsuffixed - `map_locator` derives the
   automation prefix from the map's own folder name and never joins it to the task
   id (poison sets the precedent: its shared fixture folder keeps the `-bp` name).
2. **The map binary does not exist.**
   `Content/Maps/gp-double-jump-stamina/L_DoubleJump.umap` is not committed, so L2
   is an explicit FAIL and `cb lint` errors. It must be authored with
   `aids/author_L_DoubleJump.py`, which requires `ThirdPersonEditor` built first
   and a **real off-screen RHI** (map authoring crashes under `-nullrhi`).
   **Read that script's floor block before running it** - unlike every sibling map,
   the floor here is inside the graded window.
3. **One new gameplay tag is a hard build prerequisite.**
   `FCraftBenchGameplayTags::AbilityDoubleJump()` (`Ability.DoubleJump`) is new
   for this task (PIN.md D5). It has been landed in
   `UE-projects/ThirdPerson/Source/ThirdPerson/CraftBenchGameplayTags.{h,cpp}`
   alongside `AbilityGlide` / `AbilityPoison` / `AbilityDamage` / `AbilityHeal` /
   `AbilityHealOverTime`; the fixture and the reference ability both call it, so
   nothing here compiles without it. This is the **fourth** of the four tier-1
   tags - the bp-g2 scale-up plan (not shipped) I1.5 budgeted **3**, and the real count is 4
   (two for `gp-health-attribute-ops-cpp`, one for `gp-heal-over-time-cpp`, one
   here).
4. **I1.4 must be merged, and re-gated.** This task is the **first consumer** of
   `SetDenseSampling` / `Segments` / `NumRises` / `MeanVerticalRate` /
   `DescribeSegments`, **and** the first consumer of the five older reductions
   (`MaxVelocityZAfter`, `ApexDeltaZ`, `RoseThenFell`, `ReachedMovementMode`,
   `VelocityZNear`), which had zero callers across both substrates. PIN.md section
   6 requires a **segmentation probe fixture signed off before the first
   double-jump reference run**, and I1.6's numeric-invariance check green on
   **both** substrates (the two `CraftBenchFunctionalTest.cpp` files must diff to
   0 lines - 2 PRs, 2 epochs). Dense sampling is opt-in and default OFF precisely
   so glide and poison stay byte-identical, which makes that check a **re-run, not
   a re-calibration**. Until it is run, "I1.4 is harmless to the existing
   fixtures" is an assumption.
5. **`cb lint` will WARN `anti-gaming-count`.** The spec carries **8**
   anti-gaming entries (AG-1..AG-8, the PIN's "floor of 4, not a cap"), one of
   which (AG-7) is an explicitly **ARGUED, undefended** note. The linter WARNs
   above 5. Same state `gp-poison-dot-stack-cpp` (6),
   `gp-health-attribute-ops-cpp` (6) and `gp-heal-over-time-cpp` (7) ship in. It
   is a WARN, not an ERROR, and folding entries together to silence it would cost
   real coverage - AG-6 alone is the reason DJ-4 exists.

## I1.4 is on trial here too - the first read of the first run

PIN.md D1: *"Treat the entire existing sampler as untested code."* The owner
decision makes `DescribeSegments()` mandatory in the diagnostic for exactly this
reason: **DJ-2c gates on a derived segment count, and a derived count can be
wrong silently in either direction.** A PASS/FAIL verdict says nothing about
whether the decomposition was right.

**The single most likely way this family false-FAILs**, and it is a
documentation trap rather than a code bug:

> `NumRises`'s doc comment (`CraftBenchPawnFunctionalTest.h:168-171`) reads
> *"a single jump is 1, a double jump is 2"*. That is true only for a pawn that
> **jumped from the ground first**. **This verifier DROPS the pawn** - there is no
> first jump - so a conforming series decomposes as `[FALL | RISE | FALL]` and
> `NumRises(20) == 1`. The fixture is correct (`LegOneRises >= 1`), but anyone
> "fixing" the gate to `>= 2` to match that comment would **false-FAIL every
> conforming solve, including the reference**.

This has been hand-traced through the real `Segments()` walk
(`CraftBenchPawnFunctionalTest.cpp:527-599`), not merely reasoned about. It is
still **PREDICTED, not measured**. `legOneRisesRaw` and `risesAll` are printed
next to the gate input so the segmenter's first execution has an independent
cross-check; they must agree with `legOneRises` except for rises that ended
**before** the trigger.

**What a wrong decomposition looks like in the log:**

| symptom in `DescribeSegments()` | cause | consequence |
|---|---|---|
| one jump printed as `RISE \| FALL \| RISE` with a micro-`FALL` of a few cm at the apex | `RiseEpsilon` / `MinDeltaZ` too **low** | **false PASS** at DJ-2c (two rises counted for one jump), and a possible **false FAIL** at DJ-4 if the spurious second rise starts after the Leg-2 trigger |
| a real second jump swallowed into one long `FALL` | `RiseEpsilon` too **high** | **false FAIL** at DJ-2c against a gentle but conforming impulse - the unforgivable direction |
| a `RISE` at `t ~ 2.2-2.9` with `d` of a few cm | the **landing**'s floor adjustment | harmless at `RiseEpsilon` = 20 (~8x margin), **fatal** if `RiseEpsilon` is ever lowered below ~5 |
| `segments=0` or `samples` in the single digits | dense sampling did not engage | everything downstream is vacuous; check `SetDenseSampling(true)` reached the base |

## Timeline behind the checkpoint schedule

`{0.4, 0.7, 1.0, 1.3, 1.6, 1.9, 2.4, 2.7, 3.0, 3.3}`, `LastCheckpointIndex = 9`.
Reproduced verbatim from PIN.md section 2.

| cp | t (s) | leg | fixture action | window that closes |
|---|---|---|---|---|
| 0 | 0.4 | 1 | **DJ-7** mesh check (before anything else); free-fall | - |
| 1 | 0.7 | 1 | **DJ-2a** live `vZ` read **FIRST**; `TriggerTime = t`; `SetPower(60)` + read back; trigger (Leg-1 attempt 1/1) | - |
| 2 | 1.0 | 1 | `PowerFirstAfter` + `PowerFirstAfterBase` (trigger+0.3) | DJ-3c window **OPENS** |
| 3 | 1.3 | 1 | (dense sampling only) | - |
| 4 | 1.6 | 1 | (dense sampling only) | - |
| 5 | 1.9 | 1 | `PowerAtPlus12` (trigger+1.2) | `FurtherDrop`, **0.9 s** |
| 6 | 2.4 | 1 -> 2 | **capture every Leg-1 reduction FIRST** (`MaxVZLegOne`, `MinZLegOne`, `LegOneSegmentsDesc`, `LegOneRisesRaw`, `LegOneRises`), **then** `RefusalTriggerTime = t`, `SetPower(5)`, seed `MinPowerLegTwo`, trigger (Leg-2 attempt 1/1) | **Leg-1 motion window**, realized (0.7, ~2.38] |
| 7 | 2.7 | 2 | Power sample -> `MinPowerLegTwo` | - |
| 8 | 3.0 | 2 | Power sample -> `MinPowerLegTwo` | - |
| 9 | 3.3 | 2 | Power sample + base; **ALL FINAL GATES** | Leg-2 rise window (start-keyed) |

`TimeLimit` is set by the base from the last checkpoint plus `TimeLimitMargin`
(2.0 s), i.e. **5.3 s**, so a stuck test FAILs rather than hanging. That is also
this task's in-world floor cost per L2 rep - **by far the cheapest leg in the
family** (heal-over-time 24.1 s, poison 30.6 s), because both legs fit inside one
fall.

**The cp6 ordering IS the Leg-1 window, and it is the one structural trick in the
fixture.** `MaxVelocityZAfter` / `NumRises` / `Segments` / `DescribeSegments` all
read the **whole** series and take **no upper time bound**, so a two-leg fixture
cannot window them by argument. Evaluating them at cp6 *before* the Leg-2 preset
makes the series itself the window: the base's `Tick` fires `OnCheckpoint`
**before** appending that tick's dense sample, so the series there ends one frame
short of `t = 2.4`.

**Realized window (0.7, ~2.38] vs the sheet's (0.7, 1.9] - a lenient-only
superset.** The extra ~0.5 s is post-apex free-fall, which can add a `FALL`
segment but **not a `RISE`**, and can only **lower** a maximum vertical velocity.
Recorded rather than silently absorbed. **`w6` on the second diagnostic line is
what confirms it** - if the realized cp5 -> cp6 gap is not ~0.5 s the premise
changes.

## Expected reference trace - PREDICTED, not measured

Committed reference: gate at `Power < 20`, one-shot debit of 20, then
`CMC->Velocity.Z = 600` (**assigned, not added**), `EndAbility` synchronously.
World gravity is the UE default `-980 cm/s^2` (zero `gravity` hits in the whole
`ThirdPerson/Config` tree; `ACraftBenchCharacter`'s ctor never touches
`CharacterMovement`, so `GravityScale` is the stock 1.0), and spawn is `z = 1200`.

```text
t=0.00  spawn z=1200, vZ=0
t=0.40  cp0  z~1122  vZ~-392   DJ-7 mesh check
t=0.70  cp1  z~960   vZ~-686   DJ-2a ok (< -100); preset Power 60; TRIGGER
                              -> ability gates (60 >= 20), debits to 40,
                                 assigns vZ = +600
t=0.72  first dense sample after the trigger: vZ ~ +583.7  (DJ-2b ok, positive)
t=1.00  cp2  Power 40.0        debited = 20.0   (DJ-3a, DJ-3b ok)
t=1.31  APEX z~1144            rise = +183.7 cm (DJ-2c ok, 9.2x over RiseEpsilon)
t=1.90  cp5  z~975  Power 40.0 furtherDrop = 0.00 (DJ-3c ok)
t=2.40  cp6  z~564  vZ~-1066   Leg-1 window closes; preset Power 5; RE-TRIGGER
                              -> ability gates (5 < 20): NO debit, NO impulse
t=2.78  LANDING on the floor   (between cp7 and cp8 - see the aids script)
t=3.30  cp9  Power 5.0, no Leg-2 rise    (DJ-4 ok)

granted = 1, legOneActivated = 1/1, legTwoActivated = 0/1  (a Leg-2 REFUSAL is
                                                            CONFORMING, never gated)
legOneSegments : [FALL t=0.00-0.70 d=-240 | RISE t=0.70-1.31 d=+184 | FALL ...]
legOneRises = 1   legOneRisesRaw = 1   legTwoRises = 0
```

PASS on all nine gates, with these margins: `maxVZlegOne` +600 vs a bar of
**0** (pure direction); `legOneRiseZ` 183.7 vs `RiseEpsilon` 20.0 (**9.2x**);
`debited` 20.0 vs 20.0 +/- 1.0 (**dead centre**); `furtherDrop` 0.00 vs
`PowerEpsilon` 0.5; `vZatTrigger` -686 vs `MinFallSpeed` -100 (**6.9x**).

**If the first real run does not reproduce this line for line, stop and find out
why before touching a bar.**

Note the deliberate absence of any height or rate gate. The prompt fixes no jump
height, so `+600` is a reference **choice**; the smallest impulse that clears
`RiseEpsilon` at all is `sqrt(2*980*20) = 198.0 cm/s`, and **any** value above
that is conforming. Every gate must stay indifferent to which one a submission
picks.

## The bars: every one PROPOSED - NOT YET MEASURED

Declared in `DoubleJumpStaminaFunctionalTest.h`. The last column is what must be
true before the value may be called calibrated.

| constant | proposed | gate | what must be MEASURED to retire the PROPOSED banner |
|---|---|---|---|
| `PawnSpawnZ` | 1200.0 | (Leg 1 setup) | Not a bar - a schedule premise, and the **only** one that couples to the map. Verify **three** things on the reference: `vZatTrigger` is comfortably past `-MinFallSpeed` at t=0.7 (predicted -686 vs -100); the pawn is **still airborne at t=2.4** (predicted z~564); and the **landing** appears in `fullSegments` as a `FALL` terminating around t~2.78 with no `RISE` after it. Then repeat the third check with a **minimally-conforming ~200 cm/s impulse variant**, where the landing moves to t~2.25, i.e. **before** the Leg-2 trigger - Leg 2 becomes a GROUND leg. That is lenient-only for DJ-4 but it must be *seen*, not assumed. |
| `PowerPreset` | 60.0 | (Leg 1 setup) | Not a bar - a design choice with two constraints. Far enough above the disclosed 20 cost that a conforming solve cannot be gated by its own starting resource, and far enough above it that a **double** debit (40) is still positive and therefore still reads as a magnitude error at DJ-3b rather than as a refusal. **The literal `60.0` in DJ-3b's FAIL message must be kept in step with this.** |
| `RefusalPreset` | 5.0 | (Leg 2 setup) | Not a bar - it must simply be **strictly below** `CostExpected`, which is the entire premise of the refusal leg. **The literal `5.0` in DJ-4's FAIL message must be kept in step with this.** |
| `CostExpected` | 20.0 | DJ-3b | Not a tolerance - it is the value the prompt **DISCLOSES** ("costs 20 Power"), which is what makes an absolute bar lawful under `TASK-AUTHOR-GUIDE.md` section C. It is also the one number the source source record itself specifies. Confirm only that a conforming reference debits exactly 20.0. **The literals `20` and `20.0` in the DJ-3b and DJ-4 messages must be kept in step with this.** |
| `CostTol` | 1.0 | DJ-3b | **Two populations.** Conforming side: `\|debited - 20\|` across >= 3 reps of the reference (predicted exactly 0.0) **and** across a solve that charges the cost via a `GameplayEffect` rather than a direct `SetNumericAttributeBase` - the aggregator path can land a fraction off where the direct write lands exactly. Violating side: `wrong-cost/` (a 10 or 30 debit, margin 9.0 each side). |
| `PowerEpsilon` | 0.5 | DJ-3a, DJ-3c, DJ-4 | **A floor, not a bar** - it separates signal from jitter and must be pinned from **measured** jitter under `-deterministic -FPS=60`, never chosen. Same shape and value as the glide fixture's `PowerEpsilon`, so the glide population is a starting prior but **not** a substitute. Conforming side: `furtherDrop` on the reference (predicted exactly 0.00) across >= 3 reps. Violating side: `drain-cost/`, tuned to the **smallest** per-tick drain that still passes DJ-3b at trigger+0.3 - that is the number that proves DJ-3c has teeth. |
| `MinFallSpeed` | 100.0 | DJ-2a | **Harness sanity, not an anti-gaming bar** (PIN.md section 2 marks DJ-2a's anti-gaming column `--`). Conforming side: `vZatTrigger` on the reference (predicted -686, a 6.9x margin). What actually has to be measured is the **other** direction: that no conforming submission can be *not falling* at t=0.7. If DJ-2a ever fires, read the spawn height and the map's floor before reading anything into the submission. |
| `RiseEpsilon` | 20.0 | **DJ-2c**, and `MinDeltaZ` for `Segments`/`NumRises`/`DescribeSegments` | **The highest-risk constant in the task, and it is TWO jobs in one number ON PURPOSE** - see the dedicated section below. **Three populations owed**, not two. |
| `SegmentBoundarySlack` | 0.10 | DJ-4 (Leg-2 start filter) | **Not a bar and not a physical quantity.** It covers the one frame (~0.017 s at `-FPS=60`) by which a leg-bounding local extremum can sit on the wrong side of a trigger's world time, because the base fires `OnCheckpoint` *before* appending that tick's dense sample. Measure the realized frame time from `samples=N` over the 5.3 s run and confirm `0.10` is >= 4 frames, and confirm it stays orders of magnitude below the 1.7 s inter-leg gap (`w6`) so it cannot make Leg-1 motion reachable from Leg 2. |
| (reference) `JumpImpulseZ` / `PowerCost` / `DoubleJumpInitialPower` | 600 / 20 / 100 | - | Reference **CHOICES**, not bars. `PowerCost` is the disclosed 20. `DoubleJumpInitialPower` is explicitly **non-observable** - the verifier presets Power itself before each leg - so it cannot become a hidden bar. Confirm `JumpImpulseZ`'s arithmetic empirically: rise = `600^2/1960` = **183.7 cm**, apex at **0.612 s**, ~**37 dense samples** in the rising run at `-FPS=60`, first post-trigger sample **+583.7 cm/s**. |

### `RiseEpsilon` = 20.0: one number doing two jobs, and the three populations it owes

**It is deliberately BOTH** DJ-2c's noise floor **and** the segmenter's
`MinDeltaZ` (owner decision, endorsed explicitly). `MinDeltaZ` is what **absorbs
apex jitter**: `Segments()` closes a monotonic run only once the run that would
replace it has itself moved `MinDeltaZ`
(`CraftBenchPawnFunctionalTest.cpp:560-586`). Without that absorption **one noisy
sample at the apex splits a single jump into three segments** - rise, micro-fall,
rise - and the count reads **2 rises for ONE jump**: a **false PASS on the exact
axis DJ-2c exists to defend**. So the two are **not two constants that happen to
be equal**, and re-pinning one without the other reintroduces the apex-split.

**RE-PINNING HAZARD, BOTH DIRECTIONS:**

- **Too LOW** -> apex jitter splits one jump into two rises (false PASS at
  DJ-2c), and a spurious rise after the Leg-2 trigger is a **false FAIL at DJ-4**.
  Below ~5 cm the **landing's own floor adjustment** (~2.4 cm, UE's
  `MAX_FLOOR_DIST`) starts registering as a Leg-2 rise - see the aids script.
- **Too HIGH** -> a conforming but **gentle** second jump rises less than the
  floor and is failed for not jumping. **The prompt fixes no jump height,
  deliberately** (PIN.md, "Why there is no 'the second jump must reach height H'
  gate"), so this is the unforgivable direction.

**Three populations owed** (most constants here need two):

1. **Conforming, reference:** `legOneRiseZ` across >= 3 reps of the committed
   reference. Predicted **183.7 cm**, a 9.2x margin. This is the *easy* one and
   it proves almost nothing on its own.
2. **Conforming, WEAKEST LAWFUL:** `legOneRiseZ` on a deliberately gentle solve.
   **The minimum rise a conforming implementation can produce is what actually
   bounds this constant, not the reference's generous 183.7.** Note the
   circularity to avoid: "the weakest lawful impulse" is currently *defined* by
   `RiseEpsilon` itself, so this population must be taken from what a **real
   model** ships, not from a variant tuned to the bar. Harvest it from the first
   matrix reps.
3. **Conforming, BLUEPRINT lane:** PIN.md section 6's discipline applied to this
   family. A BP ability routing the impulse through `Launch Character` or a
   `Set Velocity` node can produce a materially different arc from the C++
   `CMC->Velocity.Z = 600`. **Calibrating a shape floor against one impulse
   implementation is exactly how DJ-2c would false-FAIL a conforming BP solve.**
   **Currently measured against NO BP lane at all.**

Violating side: `cancelled-impulse/` (a one-shot upward velocity immediately
zeroed - predicted `legOneRiseZ` ~0 with a positive `maxVZlegOne`, i.e. it must
pass DJ-2b and die at DJ-2c, which is the whole reason both gates exist).

## What must be measured, and the exact commands

Run in order. **Nothing below has been run.** The repo's build-contention law
applies: `Build.bat`'s mutex is keyed on the ENGINE INSTALL, so a concurrent
build elsewhere on the box can make any of these return exit 1 with **no compile
error** - run these alone, and per the 2026-08-06 owner decision ("the build machine runs the
tests") hand them over as a dated test brief rather than running a local bench by
default.

```powershell
# 0. Prerequisites (blockers above): rename the task folder to
#    tasks/cpp/gp-double-jump-stamina-cpp/, then lint clean.
python tools/verify-single/tasklint.py tasks/cpp/gp-double-jump-stamina-cpp/task.md

# 1. Author the map (needs ThirdPersonEditor BUILT + a real off-screen RHI;
#    it crashes under -nullrhi). The committed binary is the ONLY map source.
#    READ the floor block at the top of the script first - unlike every sibling
#    map, the floor here is inside the graded window.
& "$env:CB_UE_ROOT\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" `
    UE-projects\ThirdPerson\ThirdPerson.uproject `
    -ExecutePythonScript="tasks\cpp\gp-double-jump-stamina-cpp\aids\author_L_DoubleJump.py" `
    -unattended -nopause -nosplash -RenderOffScreen

# 2. Prove the I1.4 base-class extension changed NO existing verdict
#    (PIN.md section 6). Dense sampling is opt-in and default OFF, so this must
#    be a RE-RUN, not a re-calibration. Must be green BEFORE any number below is
#    trusted.
cb refgate gp-poison-dot-stack-cpp,gp-glide-stamina-cpp,gp-heal-over-time-cpp

# 3. THE calibration run - grade the committed reference and read the two
#    [DOUBLEJUMP-FINAL] lines and the [DJ-REFUSE-DIAG] line out of the L2 log.
$env:CB_UE_ROOT='<UE-root>'
python tools/verify-single/run_task.py `
    --task tasks/cpp/gp-double-jump-stamina-cpp/task.md `
    --submission tasks/cpp/gp-double-jump-stamina-cpp/reference `
    --substrate-from-live --ue-root $env:CB_UE_ROOT

# 3b. Repeat step 3 at least THREE times. PowerEpsilon's and CostTol's
#     conforming populations are JITTER populations; one rep cannot show them.

# 4. The empty-submission leg. Expected: an empty submission resolves to the
#    BASE ACraftBenchCharacter, which grants nothing, so it must die at DJ-1a's
#    named substring with granted=0. If it dies anywhere else - and in particular
#    if it dies at DJ-2a or DJ-2b - the gate ORDERING premise is wrong and a
#    non-GAS submission is being reported as a motion defect.
python tools/verify-single/run_task.py `
    --task tasks/cpp/gp-double-jump-stamina-cpp/task.md `
    --submission <an-empty-dir> --substrate-from-live --ue-root $env:CB_UE_ROOT

# 5. One variant per anti-gaming note, each dying at its OWN named substring.
#    (None of these variants exist yet - see "Discrimination variants" below.)
python tools/verify-single/run_task.py --task tasks/cpp/gp-double-jump-stamina-cpp/task.md `
    --submission tasks/cpp/gp-double-jump-stamina-cpp/discrimination/<variant> `
    --substrate-from-live --ue-root $env:CB_UE_ROOT

# 6. Once green, the token-free reference gate and the full sweep:
cb refgate gp-double-jump-stamina-cpp
cb discriminate gp-double-jump-stamina-cpp
```

The three log lines to harvest from step 3 (all emitted BEFORE any gate, so they
survive a FAIL):

```text
[DOUBLEJUMP-FINAL] granted= legOneActivated=/ legTwoActivated=/ vZatTrigger=
                   maxVZlegOne= maxVZtail= minZlegOne=
                   legOneRises= legOneRisesRaw= legTwoRises= risesAll=
                   legOneRiseZ= legTwoRiseZ=
                   powerPreset= powerAtTrigger= plus03= plus12= debited= furtherDrop=
                   refusalPreset= minPowerLegTwo= lastPowerLegTwo=
                   baseAtPlus03= baseLegTwoLast=
                   meanRateLegOne= meanRateLegTwo= triggerT= refusalT=
[DOUBLEJUMP-FINAL] baseline= samples= legOneSegments= fullSegments=
                   w1=..w9= (bars PROPOSED - NOT YET MEASURED: ...)
[DJ-REFUSE-DIAG]   ... HARD-GATED ... | ... SKIPPED, not failed ...
```

**Five reads to make, in this order** - the first two are the ones that are
specific to this task and have no precedent anywhere in the repo:

1. **`legOneSegments`** - the decomposition DJ-2c actually gated on. Expect
   `[FALL | RISE d~+184 | FALL]`. **This is I1.4's first-ever output; read it
   before believing any DJ-2c or DJ-4 verdict.** Cross-check the table in
   "I1.4 is on trial here too".
2. **`legOneRises` vs `legOneRisesRaw` vs `risesAll`** - they must agree except
   for rises that ended **before** the trigger. A divergence with **no such rise
   in the printed decomposition** means the segmenter is not doing what the
   fixture assumes, and the gate is unsound regardless of the verdict.
3. **`fullSegments`** - look for the **landing** (a `FALL` terminating around
   t~2.78 with nothing after it) and confirm there is **no `RISE` starting after
   `refusalT`**. That is DJ-4's soundness, measured.
4. **`samples`** - divide by the 5.3 s run to get the realized frame time.
   Confirm dense sampling actually engaged (expect ~300+ samples, not ~10) and
   that `SegmentBoundarySlack` = 0.10 s is >= 4 frames.
5. **`baseAtPlus03` vs `plus03`, and `baseLegTwoLast` vs `lastPowerLegTwo`** - a
   divergence means the submission's cost is an aggregator modifier rather than a
   base write. **No gate reads the base values**, on purpose (V1.4: a base-only
   read would false-FAIL a duration/infinite implementation), so this cannot break
   a gate - but a divergence means `debited` describes something other than what
   the submission stored, and it must be *seen* rather than silently absorbed.

Write the harvested numbers back into the bar table above with the margin on each
side, then delete the `PROPOSED - NOT YET MEASURED` banners from the fixture
header and from the reference sources **in the same change**.

## Discrimination variants - PLANNED, none committed

PIN.md section 6 requires one committed one-delta variant per anti-gaming note,
each dying at its **own** named substring (I0.4's uniqueness oracle - a variant
that fails at some *other* gate proves nothing about the gate it was written
for). Every substring below is a **literal run of one FAIL format string that
does not span a `%`-placeholder**; a substring that spanned one could never match
at runtime, and the UE log is UTF-8 read back cp1252, so every one of them is
**ASCII only**.

| variant (planned) | the ONE delta from `reference/` | must FAIL at | expected MATRIX substring | predicted reading |
|---|---|---|---|---|
| `no-mesh/` | remove the `FObjectFinder` mesh assignment | **DJ-7** | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | whole-string match |
| `cmc-jump/` | move the impulse into the pawn (a `Tick`/`BeginPlay` timer); grant nothing | **DJ-1a** | `no activatable ability tagged Ability.DoubleJump on the pawn (the second jump is not an activatable ability). granted=` | `granted=0` |
| `teleport-up/` | replace the velocity assignment with `SetActorLocation(+300 Z)` | **DJ-2b** | `the ability produced no upward impulse: the highest vertical velocity after the trigger was ` | `-812, never positive` |
| `slow-fall/` | the glide answer - scale `Velocity.Z` by 0.2 instead of assigning +600 | **DJ-2b** | same substring | vZ negative throughout |
| `launch-additive/` | `LaunchCharacter((0,0,600), false, false)` - **PIN.md section 4's headline plausible-wrong solve** | **DJ-2b** | same substring | `-180, never positive` |
| `cancelled-impulse/` | assign `+600` then zero it on the next tick | **DJ-2c**, **not** DJ-2b | `the character did not rise a second time: Z fell to ` | `maxVZlegOne` positive, `legOneRiseZ` ~0 |
| `free-jump/` | delete the `SetNumericAttributeBase` debit; keep the gate | **DJ-3a** | `the second jump cost no Power: Power went ` | `60.0 -> 60.0` |
| `wrong-cost/` | `PowerCost = 10` | **DJ-3b**, **not** DJ-3a | `the second jump did not cost 20 Power: Power went 60.0 -> ` | `50.0 (debited 10.0)` |
| `drain-cost/` | charge the cost as a per-tick drain while airborne, tuned by enumeration to the **smallest** rate that still passes DJ-3b at trigger+0.3 | **DJ-3c** | `the Power cost is a continuous drain, not a one-shot debit: Power kept falling after the activation (` | `furtherDrop` just above 0.5 |
| `ungated-cost/` | delete the `Power < 20` early-out; debit and jump unconditionally | **DJ-4** | `the ability fired without paying for it: with only 5.0 Power (below the 20 cost) the character still rose a second time (Z climbed ` | `Z climbed 184`, Power `-15.0` |

Four of these earn their place beyond the AG floor:

- **`launch-additive/` is the task's headline discriminator.** PIN.md section 4
  calls it "the one a real model writes": `LaunchCharacter` with
  `bZOverride = false` **adds** to the existing velocity, so mid-fall at
  `vZ = -780` it gives `-780 + 600 = -180` and the character **never goes upward
  at all** - while the ability activates, the tag is right, the Power debit is
  perfect and the deliverable shape is right. It passes DJ-1, DJ-2a, DJ-3a,
  DJ-3b, DJ-3c, DJ-4 and DJ-7 and dies **only** at DJ-2b. **If it ever stops
  FAILing, DJ-2b has become vacuous and this task no longer distinguishes a
  reversal from a nudge.**
- **`cancelled-impulse/` is the reason DJ-2c exists separately from DJ-2b.** It
  must **pass** DJ-2b (there really was a positive vZ sample) and die at DJ-2c. A
  variant that dies at DJ-2b instead proves nothing about DJ-2c and must be
  re-tuned.
- **`wrong-cost/` is the F5 regression test.** DJ-3b exists specifically so a bad
  **magnitude** fails by its own name, and the only way to know it does is to run
  a variant that would otherwise have been misattributed to DJ-3a.
- **`ungated-cost/` is the whole point of the refusal leg (AG-6).** It is also
  the only variant that can prove DJ-4's **skip-vs-fail** guard behaves: it must
  reach the **hard-gated** `[DJ-REFUSE-DIAG]` branch (because its Leg 1 rises
  fine) and then FAIL. A companion check worth running once: a variant that
  breaks the jump **and** ungates the cost must produce the **SKIPPED** branch and
  die at **DJ-2c**, never at DJ-4 - that is the misattribution DJ-4's guard
  exists to prevent, and nothing else in the sweep exercises it.

**Cross-rep hygiene:** discrimination variants are full overlays. Leftover
scratch from a previous rep manufactures false FAILs (recorded on this codebase),
so each variant grade must start from a clean workdir.

**Sandbox note:** every variant directory must contain **only**
`Source/ThirdPerson/**`. A `NOTES.md` at a submission root sits outside the
writable prefix and is a **sandbox exit-4 reject**, so per-variant documentation
belongs in the variant's own source headers - the shape
`gp-health-attribute-ops-cpp/discrimination/slow-regen/` uses.

## Design decisions worth re-reading before a bar change

1. **DJ-6 is CUT and must not be quietly reintroduced** (owner decision
   2026-08-10). Gating "only one extra jump per airborne period" would enforce a
   limit the source row never states, and buying it with the offered extra prompt
   sentence is the **F5 trade in miniature**. It also needs a guaranteed ground
   contact to define "per airborne period", and on this map the touchdown time is
   a **function of the submission's impulse strength** - the very magnitude the
   prompt refuses to fix. AG-7 is re-recorded as an **ARGUED, undefended** note.
2. **DJ-2b must stay a PURE DIRECTION predicate.** The moment it acquires a
   magnitude ("vZ must exceed 300") it becomes an undisclosed jump-height floor -
   the exact F5 defect sitting in `gp-poison-dot-stack` today. The prompt
   specifies no height, so no gate may require one. The same reasoning is why
   `meanRateLegOne` / `meanRateLegTwo` are **diagnostic only** and why PIN.md
   refuses a "must reach height H" gate outright.
3. **DJ-4's skip-vs-fail must not be "simplified"** (PIN.md D3, endorsed verbatim
   by the owner). The `bLegOneRose` guard is the **contract**; DJ-2c's early
   return sitting above it is an accident of **layout**. A later reorder must not
   silently convert a skip into a FAIL.
4. **The Leg-2 activation counter is EVIDENCE, never a gate.** Lifting
   heal-over-time's HOT-1c ("every attempt must land") here would be wrong in the
   unforgivable direction: at 5 Power against a 20 cost, **refusing IS the
   conforming answer** and is precisely what DJ-4 rewards. Only the Leg-1 counter
   is gated.
5. **`RiseEpsilon` and the segmenter's `MinDeltaZ` are one number on purpose** and
   must be re-pinned together - see the dedicated section above.
6. **The Leg-1 window is the cp6 ORDERING, not an argument.** If a future base
   class gains time-windowed reductions, delete the cp6 capture block and use
   them; do **not** keep both.
7. **The leg-boundary rules are asymmetric on one stated principle:** each leg
   gets the rule whose boundary error points toward **PASS**. Leg 1 is
   end-keyed/inclusive because DJ-2c fails on the **absence** of a rise; Leg 2 is
   start-keyed/exclusive because DJ-4 fails on the **presence** of one. Making
   them symmetric "for consistency" would introduce a false-FAIL path at whichever
   end got the wrong rule.
8. **Every Power gate reads the CURRENT value; the base reads are evidence only**
   (the V1.4 law). A cost implemented as a duration/infinite **aggregator**
   modifier never touches the base, so a base-only read would false-FAIL a
   conforming solve at DJ-3a. Writes use `SetNumericAttributeBase`; no base-write
   helper exists.
9. **A missing ASC is deliberately NOT failed at the checkpoint pre-gate.** DJ-1
   owns that failure by name; stealing it earlier would report a non-GAS
   submission under a generic harness-shaped name. Every write is individually
   ASC-guarded and every read returns 0.0 rather than crashing, and DJ-1 runs
   first among the final gates so no Power gate is reachable on a pawn whose
   readings are meaningless.
10. **The reference ends the ability SYNCHRONOUSLY**, which is what lets Leg 2
    re-trigger it. `bRetriggerInstancedAbility` defaults false and only bites an
    instance still running. An ability held open across the 1.7 s inter-leg gap
    would be refused at Leg 2 for a reason unrelated to the cost - which DJ-4
    accepts leniently, but which would make the reference stop testing what it is
    for.

## Correlation: what this task shares with the rest of tier 1

- **It shares the `Power` resource with `gp-glide-stamina-cpp`** (PIN.md D6, the
  price of not adding an attribute). A matrix cell containing both measures Power
  handling twice. They share **no gate and no ladder**, so this is a note to carry
  on a leaderboard, **not** a `QUEUE.md` exclusion.
- **It is NOT in the stage-1 correlation set** (`QUEUE.md` constraint C1). Like
  `gp-heal-over-time-cpp`, it derives from the **generic**
  `ACraftBenchCharacter`, whose attribute set is pre-built, so there is no stage-1
  ladder and no derivation gate. A submission deriving from the **bare** character
  has no `Power` at all and dies at DJ-3a by name.
- **`gp-glide-stamina-cpp` is its nearest neighbour and an active hazard, not
  just a note.** "Slow the descent" is the glide answer and is a defensible
  misreading of "second jump" (AG-3). A model that has seen glide in the same
  matrix is **primed** for it. DJ-2b is the only thing separating them, which is
  another reason it must never be downgraded to advisory.
- The GAS-plumbing skill (grant an ability, tag it, activate by tag) is shared
  with **every** GAS family in the set. What is genuinely independent evidence
  here is the **motion** axis: this is the only tier-1 task whose primary
  observable is a trajectory rather than an attribute curve, and the only one
  where the map's geometry is inside the graded window.

## Gate to G2 (PIN.md section 6) - status

- [ ] The **segmentation probe fixture** signed off (PIN.md D1) - the whole
      sampler is untested code and this task is its first consumer.
- [ ] I1.6's numeric-invariance check green across the I1.4 base-class change on
      **both** substrates (the two `CraftBenchFunctionalTest.cpp` files diff to 0
      lines - 2 PRs, 2 epochs), and
      `cb refgate gp-poison-dot-stack-cpp,gp-glide-stamina-cpp,gp-heal-over-time-cpp`
      green afterwards.
- [ ] Task folder renamed to `gp-double-jump-stamina-cpp/`; `cb lint` clean apart
      from the documented `anti-gaming-count` WARN.
- [ ] `Content/Maps/gp-double-jump-stamina/L_DoubleJump.umap` authored and
      committed, with the floor/landing checks in the aids script confirmed.
- [ ] Reference PASS, >= 3 reps, with the predicted trace reproduced line for
      line **and `legOneSegments` read by a human**.
- [ ] Empty submission FAILs at **DJ-1a**'s named substring (not at DJ-2a or
      DJ-2b).
- [ ] One committed one-delta discrimination variant per anti-gaming note, each
      dying at its **own** named substring - including `cancelled-impulse/`
      passing DJ-2b and dying at DJ-2c, and the DJ-4 **SKIPPED**-branch companion
      check.
- [ ] Measured jitter populations recorded here, with the margin on each side, for
      `RiseEpsilon`, `PowerEpsilon`, `MinFallSpeed` and `CostTol`.
- [ ] `RiseEpsilon` measured against **three** conforming populations: the C++
      reference, a **weakest-lawful** impulse harvested from real model output, and
      a **Blueprint** lane. (Currently measured against **none**.)
- [ ] The `PROPOSED - NOT YET MEASURED` banners deleted from the fixture header
      and every reference source, in the same change that writes the measured
      numbers here.

## Dropped clauses (moved from task.md 2026-08-16; lint spec-h2-allowlist)

`PIN.md` section 1 is the signed drop table (the literal cells of source record 33,
read with `csv.reader`; the `Prompt` cell's line breaks are **CRLF** in the
source). This is the record the spec carries, plus the two dispositions the
owner decision of 2026-08-10 added.

| source-row clause | disposition | why |
|---|---|---|
| `Create a double jump ability using the Gameplay Ability System.` | **"Gameplay Ability System" DROPPED as a name**; the contract is named behaviorally instead. | Hard Rule #2 / `AUTHORING_TEMPLATE.md:365-380` ("use the X system" is Unacceptable). Carried by the GAS-category exception above: an ability the game can *activate*, a trigger *tag*, the pawn's *granted abilities*. Precedent: `gp-glide-stamina-cpp`, `gp-poison-dot-stack-cpp`. |
| `This ability should consume 20 stamina.` | **KEPT, and re-homed**: "stamina" becomes the substrate's **`Power`** attribute and is named as such. The **refusal clause is ADDED** (PIN.md D2). | `gp-glide-stamina-cpp`'s prompt already names "a depletable **Power** resource"; there is no stamina attribute in either substrate. The refusal clause is added prose because without it "consume 20" is satisfied by a cosmetic subtraction and **no gate separates "debits a number" from "a real cost"** - the task would measure arithmetic. Cost: one extra prompt bullet and one extra leg. |
| `Use the existing attribute set type: GSCAttributeSet` | **RE-HOMED onto the contract attribute set.** Everything is written against `UCraftBenchAttributeSet::GetPowerAttribute()`; **no new attribute is added** (PIN.md D6). | `GSCAttributeSet` is **GAS Companion** and exists in **neither substrate** - the repo is vanilla GAS. the bp-g2 scale-up plan (not shipped) section 6 item 14 freezes `Health/MaxHealth/Power`, so rebasing onto the existing `Power` fires no review-gated scaffold change. **Consequence accepted (PIN.md D6):** this family and `gp-glide-stamina-cpp` share a resource, so a matrix cell containing both measures Power handling twice. They share no gate and no ladder, so this is a note, not a `QUEUE.md` exclusion. |
| `Create all assets in the folder: /Game/G2/17/` | **RE-HOMED** to `/Game/Tasks/gp-double-jump-stamina-bp/`, on the **`-bp` twin only**. | `/Game/G2/17/` does not exist and `Content/Maps/` is deny-listed. The family convention re-homes every `/Game/G2/N/`. Sandbox + L2I `asset_writable` path check only; no behavioral gate. Precedent: every bp-g2 port. |
| `Start implementing immediately without asking for confirmation` | **DROPPED.** | Harness-level instruction, not behavior. Precedent: dropped on all 8 existing bp-g2 ports. |
| `Do not reference any other existing assets in the project` | **DROPPED.** | Contradicts the substrate outright: the agent **must** reference the provided character, its attribute set, and a provided mannequin mesh. Precedent: dropped on all 8 existing bp-g2 ports. |
| `Description: Movement-1` / `Difficulty: medium` / `Before Blueprint: from scratch` | Metadata -> front matter (`tier: T2`, `capability_bucket: Gameplay Programming`). | - |
| *(not in the row - family standard)* the **visible-character** bullet | **ADDED.** | Owner decision 2026-08-06, applied to the whole glide/poison family; this family inherits it. Measured cause: **9/9 glide matrix reps shipped meshless pawns** and the poison film strips showed an empty scene. Gated by DJ-7. |
| *(a proposed gate, not a source-row clause)* **DJ-6 - "only ONE extra jump per airborne period"** | **CUT by owner decision 2026-08-10.** No gate, no constant, no counter exists for it anywhere in the fixture. | The sheet flagged it "under-specified as written" and offered to buy it with an extra prompt sentence (*"Only one extra jump is available per time in the air..."*). **Declined.** Gating it would enforce a limit the source row never states, and buying it with added prose is **the F5 trade in miniature** - more section C disclosure debt for a marginal axis, on a task whose real observable (a second rise that costs a fixed resource) is already covered by **DJ-2c + DJ-3b**. *A gate nobody can derive from the prompt is worse than no gate.* It would also have added a **ground-contact axis the map would then have to guarantee**, which this map cannot: see Hidden invariants, "The floor is inside the schedule". **AG-7 is consequently re-recorded as an ARGUED note**, below, pointing at DJ-2c rather than claiming a defense it does not have. |
