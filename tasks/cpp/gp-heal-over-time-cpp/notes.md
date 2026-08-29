# gp-heal-over-time-cpp - implementor notes + calibration record

> **NOTHING IN THIS FILE HAS BEEN MEASURED.**
>
> As of authoring (2026-08-10) this task has never been built, never been run
> in PIE, never graded a reference, and never run a discrimination sweep. No
> UBT invocation, no `UnrealEditor` launch, no `cb` command and no test suite
> has been executed against it - deliberately, because sibling agents were
> authoring concurrently and the UBT mutex is **engine-keyed**, so a build
> started here returns exit 1 with no compile error in someone else's graded
> matrix. **Every numeric bar below is `PROPOSED - NOT YET MEASURED`** and
> carries that exact phrase in the fixture source
> (`HealOverTimeFunctionalTest.h`) and in the reference sources. Bars in this
> repo are pinned by MEASURING; until the "What must be measured" section below
> is worked through and its results written back here, **no bar in this task is
> calibrated and no run of it is evidence of anything.**

## Provenance

- Source: BP-G2 **source record 47** (`Difficulty: Medium`,
  `Before Blueprint: from scratch`). The record has only four non-empty cells;
  all four are in `PIN.md` section 1's drop table and summarised in `task.md`'s
  `## Dropped clauses`.
- Family **T1.2** of the bp-g2 tier-1 slate
  (the internal design note (not shipped)), sign-flipped from
  `gp-poison-dot-stack-cpp`'s Leg A and re-using its congruent-window
  discipline.
- The signed design contract is `PIN.md` in this folder. It is **normative**:
  it fixes the agent-visible prompt (reproduced verbatim in `task.md`), the
  checkpoint schedule, gates HOT-0..HOT-7 with their named FAIL strings, the
  anti-gaming list AG-1..AG-7, decisions D1-D5, and - in the binding
  `OWNER DECISION 2026-08-10 -- EDIT, then ACCEPTED` block at its end -
  `StopEpsilon = 0.25` with a corrected derivation that **supersedes the body
  of the sheet**. This file records **calibration, not design**; a bar change
  is a PIN edit first.

## Blockers before anything can be measured

1. **The task folder must be renamed** to
   `tasks/cpp/gp-heal-over-time-cpp/`. The front-matter `id` is
   `gp-heal-over-time-cpp` and `tasklint.py::_rule_task_id` raises
   `task-id-folder` as an **ERROR** when it does not equal the folder name. A
   red `cb lint` masks every later CI suite, so this is the first thing to fix.
   Do **not** solve it by dropping the `-cpp`: a bare `gp-heal-over-time` id
   would be a raw substring of the coming `gp-heal-over-time-bp` and would
   re-open the prefix-shape violation the 2026-08-06 `-cpp` rename dissolved.
   This is the exact error that hit T1.1 (`gp-health-attribute-ops-cpp`) and it
   was fixed the same way. The **map** folder
   (`Content/Maps/gp-heal-over-time/`) and the **fixture** folder
   (`Source/CraftBenchTests/Tasks/gp-heal-over-time/`) are shared with the
   coming `-bp` twin and correctly stay unsuffixed - `map_locator` derives the
   automation prefix from the map's own folder name and never joins it to the
   task id (poison sets the precedent: its shared fixture folder keeps the
   `-bp` name).
2. **The map binary does not exist.**
   `Content/Maps/gp-heal-over-time/L_HealOverTime.umap` is not committed, so L2
   is an explicit FAIL and `cb lint` errors. It must be authored with
   `aids/author_L_HealOverTime.py`, which requires `ThirdPersonEditor` to be
   built first and a **real off-screen RHI** (map authoring crashes under
   `-nullrhi`).
3. **One new gameplay tag is a hard build prerequisite.**
   `FCraftBenchGameplayTags::AbilityHealOverTime()` (`Ability.HealOverTime`) is
   new for this task (PIN.md D5). It has been landed in
   `UE-projects/ThirdPerson/Source/ThirdPerson/CraftBenchGameplayTags.{h,cpp}`
   alongside the pre-existing `AbilityGlide` / `AbilityPoison` /
   `AbilityDamage` / `AbilityHeal`; the fixture and the reference ability both
   call it, so nothing here compiles without it. This is the **third** of the
   four tier-1 tags (the bp-g2 scale-up plan (not shipped) I1.5 budgeted 3; the real count is
   4 - two for `gp-health-attribute-ops-cpp`, one here, one for the double-jump
   task).
4. **V1.1 + V1.4 must be merged, and re-gated.** This task is the **first
   consumer** of `PawnAttribute` / `PawnAttributeBase` (V1.4) and of
   `ApplyEffectToPawn` (V1.1) on `ACraftBenchPawnFunctionalTest`. PIN.md
   section 6 additionally requires
   `cb refgate gp-poison-dot-stack-cpp,gp-glide-stamina-cpp` green **after**
   the base-class extension, proving it changed no existing verdict. Until that
   is run, "V1.4 is harmless to the existing fixtures" is an assumption.
5. **`cb lint` will WARN `anti-gaming-count`.** The spec carries **7**
   anti-gaming entries (AG-1..AG-7, the PIN's "floor of 4, not a cap") and the
   linter WARNs above 5. Same state `gp-poison-dot-stack-cpp` (6) and
   `gp-health-attribute-ops-cpp` (6) ship in. It is a WARN, not an ERROR, and
   folding two sharp entries together to silence it would cost real coverage -
   AG-5 alone is the task's headline discriminator and AG-1 is the reason HOT-0
   runs first.

## Timeline behind the checkpoint schedule

`{0.5, 1.6, 3.1, 4.6, 7.6, 9.7, 10.7, 15.8, 17.0, 22.1}`,
`LastCheckpointIndex = 9`. Reproduced verbatim from PIN.md section 2.

| cp | t (s) | leg | fixture action | window that closes |
|---|---|---|---|---|
| 0 | 0.5 | 1 | **HOT-0** MaxHealth read (before any trigger AND any fixture write); **HOT-7** mesh check; `SetHealth(40)`; trigger (attempt 1/3) | - |
| 1 | 1.6 | 1 | `A1 = Health()` (trigger+1.1) | - |
| 2 | 3.1 | 1 | `A2 = Health()` (trigger+2.6) | `RiseStep1 = A2 - A1`, **1.5 s** |
| 3 | 4.6 | 1 | `A3 = Health()` (trigger+4.1) | `RiseStep2 = A3 - A2`, **1.5 s, CONGRUENT** |
| 4 | 7.6 | 1 | `AStop = Health()` (trigger+7.1) | - (stop window OPENS, past the 4-7 s band top) |
| 5 | 9.7 | 1 | `ATail = Health()` (trigger+9.2) | `StopRise = ATail - AStop`, **2.1 s** |
| 6 | 10.7 | 2 | `SetHealth(95)`; trigger (attempt 2/3) | - |
| 7 | 15.8 | 2 | `L2Current` + `L2Base` + `L2MaxLive`, all at the **same instant** (trigger+5.1) | - |
| 8 | 17.0 | 3 | `SetHealth(100)`; trigger (attempt 3/3) | - |
| 9 | 22.1 | 3 | `L3Current`, `L3Base` (trigger+5.1); **ALL FINAL ASSERTS** | - |

`TimeLimit` is set by the base from the last checkpoint plus `TimeLimitMargin`
(2.0 s), i.e. **24.1 s**, so a stuck test FAILs rather than hanging. That is
also this task's in-world floor cost per L2 rep, and it is the price of running
three legs in one world (poison's 16-checkpoint schedule costs 30.6 s the same
way).

The two **gated rise** windows are congruent by construction (both 1.5 s at
equal offsets from the same trigger). That congruence is the premise of BOTH
HOT-2 (one shared noise floor compared against two step sizes) and HOT-3 (whose
lawful bound is quantified against the **smaller** of the two rise windows'
tick counts). The fixture's second `[HEALOVERTIME-FINAL]` line reports the
**realized** window lengths `w1..w9` from `CrossingTimes` so the premise is
measured evidence, not a comment. **`w2` and `w3` must read the same to within
one frame; `w5` is the 2.1 s stop window.**

**Expected reference trace, PREDICTED not measured** (the committed reference:
`HasDuration` 5.0 s, `Period` 1.0 s, additive **+5.0** per period,
`bExecutePeriodicEffectOnApplication = false`, preset 40 at t=0.5, so periodic
executions land at t = 1.5, 2.5, 3.5, 4.5, 5.5):

```text
Leg 1: 40 -> A1 45 (1 tick) -> A2 50 (2) -> A3 60 (4) -> AStop 65 (5) -> ATail 65 (5)
       RiseStep1 = 5.0   RiseStep2 = 10.0   StopRise = 0.0   TotalRestored = 25.0
Leg 2: preset 95, would accumulate to 120, clamps -> L2Current 100.0, L2Base 100.0
Leg 3: preset 100 -> L3Current 100.0, L3Base 100.0
granted = 1, activated = 3/3
```

PASS on all nine checks, with the margins the sheet predicts: `RiseStep1` 5.0
vs `RiseEpsilon` 0.5 (10x), `StopRise` 0.0 vs `StopEpsilon` 0.25, total 25.0
dead-centre of `[10, 40]`. **If the first real run does not reproduce this line
for line, stop and find out why before touching a bar.**

Note the deliberate asymmetry `RiseStep1 = 5` vs `RiseStep2 = 10`: the windows
are congruent but their **phase** relative to a 1.0 s period is not, so a
congruent pair does not imply equal step sizes. HOT-2 is a direction predicate
precisely so that asymmetry is legal; a rate bar here would have to absorb it.

## The bars: every one PROPOSED - NOT YET MEASURED

Declared in `HealOverTimeFunctionalTest.h`. The last column is what must be
true before the value may be called calibrated.

| constant | proposed | gate | what must be MEASURED to retire the PROPOSED banner |
|---|---|---|---|
| `MaxHealthExpected` | 100.0 | HOT-0 | Not a tolerance - it is the value the prompt DISCLOSES ("MaxHealth is 100"), which is what makes an absolute bar lawful. Confirm only that a conforming reference reads exactly 100.0 at cp0, before any fixture write. |
| `MaxHealthEpsilon` | 0.5 | HOT-0 | Absorbs float noise on a direct read-back only (nothing has run inside cp0). Measure `\|MaxHealthRead - 100\|` on the reference; it should be exactly 0.0. Violating side: an uninitialized cap reads exactly 0.0, so the margin is 100. |
| `HealthPreset` | 40.0 | (Leg 1 setup) | Not a bar - PIN.md **D4**, "the single highest-risk calibration constraint in the family". Verify only that the whole Leg 1 window stays strictly below the cap: `max(A1..ATail) < 100 - ClampEpsilon` on the reference AND at the **top** of the disclosed total band (a solve restoring 40 from a preset of 40 ends at 80). If `TotalRestoredMax` is ever raised, this must come down, or HOT-2 starts false-FAILing conforming work under the wrong name. |
| `ClampPreset` | 95.0 | (Leg 2 setup) | Not a bar - a design choice. Verify only that it drives the clamp for the **band floor** as well as the ceiling: `95 + TotalRestoredMin = 105 > 100`. If `TotalRestoredMin` ever drops below 5, this must go up or HOT-5 becomes vacuous for a minimal conforming solve. |
| `AtMaxPreset` | 100.0 | (Leg 3 setup) | Not a bar - it is `MaxHealthExpected` by definition. |
| `RiseEpsilon` | 0.5 | HOT-2 | **Two populations.** Conforming side: the **smaller** of `RiseStep1` / `RiseStep2` across >= 3 reps of the reference (predicted 5.0), AND across a deliberately **slowest-lawful** solve - the minimum per-window rise a conforming implementation can produce is what actually bounds this, not the reference's generous 5.0. Violating side: `RiseStep2` on `instant-restore/` (predicted exactly 0.0). Pin, record both margins. **Do not raise it without redoing the `StopEpsilon` minimisation** - the two are coupled. |
| `StopEpsilon` | **0.25** | HOT-3 | **Owner-pinned 2026-08-10 with a derivation, not a measurement** - see the dedicated section below. Conforming side: `StopRise` on the reference (predicted exactly 0.0) and on a conforming **7 s** duration (the band top; predicted 0.0 because the window opens at trigger+7.1). Violating side: `StopRise` on `permanent-regen/`, tuned as poison's `permanent-drain/` was, by exhaustive period enumeration, to be the **smallest** value that still passes HOT-2. Both populations owed. |
| `ClampEpsilon` | 0.5 | HOT-5 | **PIN.md section 6 requires THREE solves, not one**: the C++ `PreAttributeChange` + `PostGameplayEffectExecute` reference, a **BP magnitude-calculation lane**, and a **BP ability-loop lane**. Calibrating against the C++ reference alone is exactly how this gate false-FAILs a conforming BP solve (PIN.md D1) - a BP clamp routed through an MMC can land a fraction above the cap where the C++ one lands exactly on it. Violating side: `L2Base` on `current-only-clamp/` (predicted ~115-120). **Currently NOT measured against any BP lane at all.** |
| `AtMaxEpsilon` | 0.5 | HOT-6 | Conforming side: `\|L3Current - 100\|` on the reference (predicted exactly 0.0). Violating side, **both directions**: a set-to-max clamp that *lowers* Health, and an unclamped restore that pushes past. Kept separate from `ClampEpsilon` on purpose - one constant doing two jobs is the split that had to be made on T1.1 (`DirectionEpsilon` vs `IdleEpsilon`) after re-pinning one over-constrained the other. |
| `TotalRestoredMin` / `TotalRestoredMax` | 10.0 / 40.0 | HOT-4 | Disclosed by the prompt ("a total of between 10 and 40 Health"); the bar **is** the prompt, not a measurement. What must be measured is the **misattribution** claim: `token-restore/` (1 HP per period) must die at HOT-4's named string, **not** at HOT-2's. That is the F5 regression test for this task. |
| (reference) duration / period / per-period | 5.0 s / 1.0 s / +5.0 | - | Reference CHOICES, not bars. Confirm the arithmetic empirically: 5 executions (not 6 - `bExecutePeriodicEffectOnApplication` defaults **true** in UE 5.8) and a per-application total of exactly 25.0, the midpoint of the disclosed band. |

### `StopEpsilon` = 0.25: the derivation is the calibration, and it is still owed both populations

The owner's 2026-08-10 EDIT replaced 0.7 with **0.25** and corrected the
reasoning. The derivation is reproduced in full in the fixture header and in
`task.md`'s Hidden invariants; the short form:

- HOT-3 has teeth against **every** permanent regeneration only while
  `StopEpsilon < RiseEpsilon * min over all admissible p of (nStop(p) / min(nRise(p)))`.
- The sheet's `1.4` was the **window LENGTH ratio** `2.1 / 1.5` - the wrong
  quantity, because **ticks are discrete** and a period can be phased so the
  longer window carries no more ticks than the shorter one.
- Minimising on a 1 ms grid over this schedule gives exactly **1.000**, and it
  is **attained** (period 0.576 s: 3 ticks in each 1.5 s rise window, 3 in the
  2.1 s stop window). So the lawful bound is **0.50**, the proposed 0.7 sat
  **above** it, and HOT-3 at 0.7 would not have defended AG-4 at all.
- **0.25** is midway between the conforming population (0.0) and the 0.50
  bound.

**What is still owed.** The 1.000 factor is *analysis*; the conforming 0.0 is
*prediction*. Both must be measured:

1. `StopRise` on >= 3 reps of the reference (expected 0.0; any non-zero value
   is jitter and is the real conforming population).
2. `StopRise` on a conforming solve at the **band top** (7 s duration) - the
   window opens at trigger+7.1, so this must also read 0.0. If it does not, the
   band top and the window opening are inconsistent and the schedule, not the
   bar, is wrong.
3. `StopRise` on `permanent-regen/` tuned to the **smallest** value that still
   passes HOT-2, by enumerating periods on a 1 ms grid the same way the
   minimisation did. This is the number that proves the bound is real rather
   than argued.

**RE-PINNING LAW:** `StopEpsilon` is **coupled** to `RiseEpsilon` and to all
three window lengths. Changing `RiseEpsilon`, either rise window length, or the
stop window length invalidates the 1.000 factor and **the whole minimisation
must be redone over the new schedule**. Assuming a tick count instead of
quantifying over the period is precisely the defect the owner edit fixed.

## What must be measured, and the exact commands

Run in order. **Nothing below has been run.** The repo's build-contention law
applies: `Build.bat`'s mutex is keyed on the ENGINE INSTALL, so a concurrent
build elsewhere on the box can make any of these return exit 1 with **no
compile error** - run these alone, and per the 2026-08-06 owner decision
("the build machine runs the tests") hand them over as a dated test brief rather than
running a local bench by default.

```powershell
# 0. Prerequisites (blockers above): rename the task folder to
#    tasks/cpp/gp-heal-over-time-cpp/, then lint clean.
python tools/verify-single/tasklint.py tasks/cpp/gp-heal-over-time-cpp/task.md

# 1. Author the map (needs ThirdPersonEditor BUILT + a real off-screen RHI;
#    it crashes under -nullrhi). The committed binary is the ONLY map source.
& "$env:CB_UE_ROOT\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" `
    UE-projects\ThirdPerson\ThirdPerson.uproject `
    -ExecutePythonScript="tasks\cpp\gp-heal-over-time-cpp\aids\author_L_HealOverTime.py" `
    -unattended -nopause -nosplash -RenderOffScreen

# 2. Prove the V1.1/V1.4 base-class extension changed NO existing verdict
#    (PIN.md section 6). This must be green BEFORE any number below is trusted.
cb refgate gp-poison-dot-stack-cpp,gp-glide-stamina-cpp

# 3. THE calibration run - grade the committed reference and read the two
#    [HEALOVERTIME-FINAL] lines out of the L2 log.
$env:CB_UE_ROOT='<UE-root>'
python tools/verify-single/run_task.py `
    --task tasks/cpp/gp-heal-over-time-cpp/task.md `
    --submission tasks/cpp/gp-heal-over-time-cpp/reference `
    --substrate-from-live --ue-root $env:CB_UE_ROOT

# 3b. Repeat step 3 at least THREE times. StopEpsilon's conforming population
#     is a JITTER population; one rep cannot show it.

# 4. The empty-submission leg. NOTE the expected failure differs from T1.1:
#    this family derives from the GENERIC character, which pre-builds the
#    attribute set, so an empty submission resolves to a pawn with Health but
#    an UNINITIALIZED MaxHealth -> it must die at HOT-0's named substring
#    ("MaxHealth was not initialized: read "), and if it dies anywhere else the
#    ordering premise of D3 is wrong.
python tools/verify-single/run_task.py `
    --task tasks/cpp/gp-heal-over-time-cpp/task.md `
    --submission <an-empty-dir> --substrate-from-live --ue-root $env:CB_UE_ROOT

# 5. One variant per anti-gaming note, each dying at its OWN named substring.
#    (None of these variants exist yet - see "Discrimination variants" below.)
python tools/verify-single/run_task.py --task tasks/cpp/gp-heal-over-time-cpp/task.md `
    --submission tasks/cpp/gp-heal-over-time-cpp/discrimination/<variant> `
    --substrate-from-live --ue-root $env:CB_UE_ROOT

# 6. Once green, the token-free reference gate and the full sweep:
cb refgate gp-heal-over-time-cpp
cb discriminate gp-heal-over-time-cpp
```

The two log lines to harvest from step 3 (both are emitted BEFORE any gate, so
they survive a FAIL):

```text
[HEALOVERTIME-FINAL] granted= activated=/ maxHealth= preset1=
                     A1= A2= A3= AStop= ATail=
                     total= riseStep1= riseStep2= stopRise=
                     L2cur= L2base= L2maxLive= L3cur= L3base=
[HEALOVERTIME-FINAL] baseline= w1= w2= w3= w4= w5= w6= w7= w8= w9=
                     (congruent rise pair = w2,w3; stop window = w5; bars PROPOSED ...)
```

Three reads to make on that second line, in order:

1. **`w2` vs `w3`** - if they differ by more than one frame, the congruence
   premise is false and both HOT-2's shared noise floor and HOT-3's bound are
   unsound. Fix the schedule, not the bars.
2. **`w5`** - the realized stop window. The `StopEpsilon` minimisation is
   quantified over a **2.1 s** window; a materially different realized length
   invalidates the 1.000 factor.
3. **`L2maxLive` vs `maxHealth`** - a divergence means the submission moved its
   own cap between cp0 and cp7. HOT-5 gates against the cp0 value on purpose,
   so this cannot break the gate, but it must be *seen*.

Write the harvested numbers back into the bar table above with the margin on
each side, then delete the `PROPOSED - NOT YET MEASURED` banners from the
fixture header and from the reference sources **in the same change**.

## Discrimination variants - PLANNED, none committed

PIN.md section 6 requires one committed one-delta variant per anti-gaming note
(7), each dying at its **own** named substring (I0.4's uniqueness oracle - a
variant that fails at some *other* gate proves nothing about the gate it was
written for). Every substring below is a **literal run of one FAIL format
string that does not span a `%`-placeholder**; a substring that spanned one
could never match at runtime, and the UE log is UTF-8 read back cp1252, so
every one of them is **ASCII only**.

| variant (planned) | the ONE delta from `reference/` | must FAIL at | expected MATRIX substring | predicted reading |
|---|---|---|---|---|
| `no-maxhealth/` | drop `InitMaxHealth(100)`; everything else verbatim | **HOT-0** | `MaxHealth was not initialized: read ` | `read 0.0` |
| `no-mesh/` | remove the `FObjectFinder` mesh assignment | **HOT-7** | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | whole-string match |
| `tick-regen/` | move the restore into `Tick`; grant nothing | **HOT-1** | `no activatable ability tagged Ability.HealOverTime on the pawn (the restore is not an activatable ability). granted=` | `granted=0` |
| `instant-restore/` | `DurationPolicy = Instant`, magnitude +25 | **HOT-2** | `the restore was not periodic: Health did not keep rising in steps (A1=` | `A1=65 A2=65 A3=65`, step 2 = 0.0 |
| `permanent-regen/` | `DurationPolicy = Infinite`, period/magnitude tuned by exhaustive 1 ms-grid enumeration to be the smallest that still passes HOT-2 | **HOT-3** | `the restore did not STOP after its duration: Health was still rising in the post-band stop window (AStop=` | `stopRise` just above 0.25 |
| `token-restore/` | +1.0 per period instead of +5.0 | **HOT-4**, not HOT-2 | `the total restored is outside the stated 10-40 band: Health went 40.0 -> ` | total 5.0 |
| `current-only-clamp/` | delete the `PostGameplayEffectExecute` override; keep `PreAttributeChange` | **HOT-5** | `the restore pushed Health past its cap: current=` | `current=100.0 base=120.0` |
| `set-to-max/` | "clamp" by setting `Health = MaxHealth` on activation | **HOT-6** | `activating the restore at full health changed Health: 100.0 -> ` | lowers Health when above; also catches the ceiling case |

Three of these earn their place beyond the AG floor:

- **`current-only-clamp/` is the task's headline discriminator.** PIN.md
  section 4 calls it "the one a real model writes": it is the recipe every GAS
  tutorial shows, it is what "Health must never exceed MaxHealth" reads like to
  a competent engineer, and it passes HOT-0 through HOT-4, HOT-6 and HOT-7.
  **If it ever stops FAILing, the whole P1 clamp gate has become vacuous and
  this task is a sign-flipped poison clone.**
- **`token-restore/` is the F5 regression test.** HOT-4 exists specifically so
  a bad magnitude fails by its own name, and the only way to know it does is to
  run a variant that would otherwise have been misattributed.
- **`permanent-regen/` is the test of the owner's edit.** It must be tuned the
  way poison's `permanent-drain/` was - by enumeration, to hide inside every
  other tolerance - or it proves nothing about `StopEpsilon`. Note the poison
  precedent recorded in that family's `discrimination/MATRIX.md`: a
  never-ending drain **PASSED** poison's Leg A stop gate and was caught only by
  cross-leg accumulation. This family has no second leg to save it, so
  `permanent-regen/` is the only thing standing between HOT-3 and the same
  six-week unsound-gate outcome.

**Cross-rep hygiene:** discrimination variants are full overlays. Leftover
scratch from a previous rep manufactures false FAILs (recorded on this
codebase), so each variant grade must start from a clean workdir.

**Sandbox note:** every variant directory must contain **only**
`Source/ThirdPerson/**`. A `NOTES.md` at a submission root sits outside the
writable prefix and is a **sandbox exit-4 reject**, so per-variant
documentation belongs in the variant's own source headers - the shape
`gp-health-attribute-ops-cpp/discrimination/slow-regen/` uses.

## Design decisions worth re-reading before a bar change

1. **HOT-2 is a pure direction predicate and must stay one** (owner decision
   Q5(b), applied prospectively). Poison's `PeriodicMinStep = 2.0` over a 1.5 s
   window is an **undisclosed** `> 1.33 HP/s` floor: a conforming 1 HP/s
   restore fails it under a message describing something it did not do. Adding
   a magnitude floor here would reintroduce exactly that. The magnitude
   question is HOT-4's, and HOT-4 is disclosed.
2. **The acceptance band is disclosed and poison's is not** (the F5
   correction). "The verifier accepts any duration in the four-to-seven-second
   range" is in the prompt in as many words. That disclosure is what makes the
   band lawful to gate on under `TASK-AUTHOR-GUIDE.md` section C, and it is
   why the stop window opens at trigger+7.1 rather than inside the band.
3. **The clamp legs are SEPARATE legs with their own presets** (PIN.md D4).
   F3's objection - "a clamp saturates the periodic steps" - is real but is a
   *schedule* problem, not a mechanism problem: it bites only if the periodic
   gate and the clamp gate share a leg. Leg 1 starts at 40 and the disclosed
   total is at most 40, so `40 + 40 = 80 < 100`. **This is the single
   highest-risk calibration constraint in the family**; moving the preset up or
   widening `TotalRestoredMax` starts false-FAILing conforming work at HOT-2.
4. **HOT-1 keeps COUNTERS, not the base class's latch.** The base's
   `bAbilityActivated` is a single OR across every tag and every activation.
   This fixture triggers three times in one run, and UE 5.8 legitimately
   refuses re-activation of a still-running `InstancedPerActor` ability or one
   on cooldown - idiomatic GAS, not gaming. With a latch, a refused Leg 2
   activation leaves Health parked at 95 and **HOT-5 passes vacuously**; a
   refused Leg 3 activation makes **HOT-6 pass vacuously**. The two gates this
   family exists for would both go green having tested nothing. If per-tag
   counters are ever pushed down into the base, delete the private ones here
   rather than keeping both.
5. **HOT-6 gates the CURRENT value only, and reports the base.** PIN.md section
   4 states the plausible-wrong solve passes HOT-6 and dies at HOT-5. If HOT-6
   also gated the base, two gates would fire on one defect and HOT-5 would stop
   being the named cause - the sheet's own discrimination story would collapse.
   The base value is still printed because it is the number a reviewer needs to
   tell the two defects apart.
6. **HOT-5 gates against the cp0 cap read, not a live re-read.** A live re-read
   would let a submission raise its own cap at activation time and clear the
   gate by moving the goalposts. The live value is logged as `L2maxLive` so the
   divergence is visible rather than silently absorbed.
7. **Reads go through the CURRENT value everywhere except HOT-5** (the V1.4
   law). A restore implemented as a duration/infinite **aggregator** modifier
   never touches the base, so a base-only read would report zero rise for a
   conforming solve and false-FAIL it at HOT-2. Writes use
   `SetNumericAttributeBase`; no base-write helper exists.
8. **The reference replaces the inherited attribute set's CLASS rather than
   adding a second set.** `GetAttributeSubobject` matches on `IsA`, so two
   registered sets of the contract lineage both answer `GetHealthAttribute()`
   and which one wins is enumeration order.
   `ObjectInitializer.SetDefaultSubobjectClass<...>(TEXT("AttributeSet"))` must
   be in the constructor **initializer list**, not the body -
   `AssertIfSubobjectSetupIsNotAllowed` fires for body calls.
9. **`ClampHealth` reads `GetMaxHealth()`, not a constant, and is NOT
   special-cased for `MaxHealth == 0`.** An uninitialized cap clamping every
   restore to zero is the honest consequence, and HOT-0 exists to name it.
   Special-casing it would be writing to the gate.
10. **This family deliberately has NO stage-1 ladder and NO derivation gate**
    (PIN.md D2) - see the correlation section below.

## Correlation: this task is NOT in the stage-1 set (constraint C1)

`gp-poison-dot-stack-cpp` and `gp-health-attribute-ops-cpp` share a lifted
stage-1 ladder, so their stage-1 pass populations are correlated and
`QUEUE.md` carries that as **constraint C1**. **This task is deliberately
outside that set.** PIN.md D2 routes it through the **generic**
`ACraftBenchCharacter`, whose attribute set is pre-built: Health is free, there
is no stage-1 ladder, and no derivation gate. Routing it through
`ACraftBenchBareCharacter` would have made C1 a three-way exclusion and cost
tier 1 a usable graded cell.

Two consequences to carry on any bp-g2 tier-1 leaderboard:

- The task is **slightly easier** than the plan's Band-B estimate (recorded in
  PIN.md D2), because the agent is handed the health system.
- Its result **is** independent evidence relative to the other two health
  tasks, which is the whole point of the decision - but only for the
  clamp/duration axis. The GAS-plumbing skill (grant an ability, tag it,
  activate by tag) is still shared with every GAS family in the set.

## Gate to G2 (PIN.md section 6) - status

- [ ] V1.1 + V1.4 merged, and `cb refgate gp-poison-dot-stack-cpp,gp-glide-stamina-cpp`
      green afterwards (proving the base-class extension changed no existing
      verdict).
- [ ] Task folder renamed to `gp-heal-over-time-cpp/`; `cb lint` clean apart
      from the documented `anti-gaming-count` WARN.
- [ ] `Content/Maps/gp-heal-over-time/L_HealOverTime.umap` authored and
      committed.
- [ ] Reference PASS, >= 3 reps, with the predicted trace reproduced line for
      line.
- [ ] Empty submission FAILs at **HOT-0**'s named substring (not elsewhere).
- [ ] One committed one-delta discrimination variant per anti-gaming note (7),
      each dying at its **own** named substring.
- [ ] Both measured populations recorded here, with the margin each side, for
      `RiseEpsilon`, `StopEpsilon`, `ClampEpsilon` and the total-restored band,
      **plus** the `StopEpsilon < 1.000 * RiseEpsilon` inequality it is pinned
      against.
- [ ] `ClampEpsilon` measured against **three** solves: the C++ reference, a BP
      magnitude-calculation lane, and a BP ability-loop lane. (Currently
      measured against **none**.)
- [ ] The `PROPOSED - NOT YET MEASURED` banners deleted from the fixture header
      and every reference source, in the same change that writes the measured
      numbers here.

## Dropped clauses (moved from task.md 2026-08-16; lint spec-h2-allowlist)

`PIN.md` section 1 is the signed drop table (four non-empty cells of CSV record
47, all four shown there). This is the record the spec carries.

| source-row clause | disposition | why |
|---|---|---|
| `Update the health potion to use a HoT instead of instantly healing the player.` | **The "Update the ..." EDIT framing is DROPPED. Re-framed FROM SCRATCH.** Owner decision **Q3(a)**, the bp-g2 scale-up plan (not shipped) section 7. | There is **no health potion in either substrate**. Authoring a baseline potion asset to be edited would (a) pull the Edit(Debug) lane (I3.4) onto tier 1's critical path, and (b) commit a baseline asset into the substrate's default git state, where every other task would then have to ignore it. The row's own `Before Blueprint: from scratch` cell already says from-scratch, so the EDIT framing was never load-bearing. **Consequence to keep in view:** the task no longer measures "can the model modify existing behavior", only "can it build the behavior" - if the Edit(Debug) lane is ever wanted, it is a separate task, not a re-framing of this one. |
| the word **`potion`** | **DROPPED with the EDIT framing.** | An item/pickup is a **second, ungraded axis**. Grading "a potion" would mean grading inventory, pickup, or use-item semantics that no gate here reads and that the prompt would then have to disclose. Every gate in this task reads exactly one attribute on one pawn; naming a potion would put prose in the prompt that no FAIL string can ever cite. |
| `Make it last for 5 seconds.` | **KEPT, and the acceptance band is DISCLOSED**: "roughly five seconds, then stop" + "The verifier accepts any duration in the four-to-seven-second range." | The F5 correction applied prospectively - see Hidden invariants. |
| `Use GAS.` | **"GAS" DROPPED as a name**; the contract is named behaviorally instead. | Hard Rule #2 / `AUTHORING_TEMPLATE.md` ("use the X system" is Unacceptable). Carried by the GAS-category exception above: name the contract (an ability system, the provided attribute set, a trigger tag), never the plugin or the class. |
| `Difficulty: Medium` / `Before Blueprint: from scratch` | Metadata -> front matter (`tier: T2`, `capability_bucket: Gameplay Programming`). | - |
| *(not in the row)* the **cap** prose (MaxHealth is 100, never exceed it, at-max is a no-op) | **ADDED.** | The section C disclosure price of **P1 - restore the clamp gate** (PIN.md D1). An absolute bar is lawful only when the prompt states it, so four numbers had to be pinned in the prompt: the 10-40 total band, the ~1/s cadence, the ~5 s duration, and MaxHealth = 100. Recorded in `bp-g2-verifier-extensions.md` section 3a as "more section C under-specification debt than poison carries". |
| *(not in the row)* the **visible-character** bullet | **ADDED.** | Owner decision 2026-08-06, applied to the whole glide/poison family; this family inherits it. Measured cause: 9/9 glide matrix reps shipped meshless pawns and the poison film strips showed an empty scene. |
| *(not in the row)* `/Game/Tasks/gp-heal-over-time-bp/` | Added on the **`-bp` twin only**. | The row names no path; the family convention re-homes every `/Game/G2/N/` to `/Game/Tasks/<id>/`, and `Content/Maps/` is deny-listed. |
