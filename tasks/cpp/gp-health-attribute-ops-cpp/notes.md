# gp-health-attribute-ops-cpp - implementor notes + calibration record

> **NOTHING IN THIS FILE HAS BEEN MEASURED.**
>
> As of authoring (2026-08-10) this task has never been built, never been run
> in PIE, never graded a reference, and never run a discrimination sweep. No
> UBT invocation, no `UnrealEditor` launch, no `cb` command, no test suite has
> been executed against it. **Every numeric bar below is
> `PROPOSED - NOT YET MEASURED`** and carries that exact phrase in the fixture
> source (`HealthAttributeOpsFunctionalTest.h`) and in the two reference effect
> sources. Bars in this repo are pinned by MEASURING; until the "must be
> measured" section below is worked through and its results written back here,
> **no bar in this task is calibrated and no run of it is evidence of
> anything.**

## Provenance

- Source: BP-G2 **source record 29 "Health-1"** (`Category: Full
  Prompt`, `Difficulty: medium`, `Concepts: GAS attribute, GAS effect`,
  `Before Blueprint: from scratch`).
- Family **T1.1**, the Band-A floor of the bp-g2 tier-1 slate
  (the internal design note (not shipped)).
- The signed design contract is `PIN.md` in this folder. It is **normative**:
  it fixes the agent-visible prompt (reproduced verbatim in `task.md`), the
  checkpoint schedule, gates HO-1..HO-11 with their named FAIL strings, the
  anti-gaming list AG-1..AG-6, and decisions D1-D4. This file records
  calibration, not design; a bar change is a PIN edit first.

## Blockers before anything can be measured

1. **The task folder must be renamed** to
   `tasks/cpp/gp-health-attribute-ops-cpp/`. The front-matter `id` is
   `gp-health-attribute-ops-cpp` and `tasklint.py::_rule_task_id` raises
   `task-id-folder` as an **ERROR** when it does not equal the folder name. A
   red `cb lint` masks every later CI suite, so this is the first thing to fix.
   Do **not** solve it by dropping the `-cpp`: a bare `gp-health-attribute-ops`
   id would be a raw substring of the coming `gp-health-attribute-ops-bp` and
   would re-open the prefix-shape violation the 2026-08-06 `-cpp` rename
   dissolved. The **map** folder (`Content/Maps/gp-health-attribute-ops/`) and
   the **fixture** folder
   (`Source/CraftBenchTests/Tasks/gp-health-attribute-ops/`) are shared with the
   coming `-bp` twin and correctly stay unsuffixed - `map_locator` derives the
   automation prefix from the map's own folder name and never joins it to the
   task id (poison sets the precedent: its shared fixture folder keeps the
   `-bp` name).
2. **The map binary does not exist.**
   `Content/Maps/gp-health-attribute-ops/L_HealthOps.umap` is not committed, so
   L2 is an explicit FAIL and `cb lint` errors. It must be authored with
   `aids/author_L_HealthOps.py`, which requires `ThirdPersonEditor` to be built
   first and a **real off-screen RHI** (map authoring crashes under `-nullrhi`).
3. **Two new gameplay tags are a hard build prerequisite.**
   `FCraftBenchGameplayTags::AbilityDamage()` / `::AbilityHeal()` are new for
   this task (PIN.md D3). They have been landed in
   `UE-projects/ThirdPerson/Source/ThirdPerson/CraftBenchGameplayTags.{h,cpp}`
   alongside the pre-existing `AbilityGlide` / `AbilityPoison`; the fixture and
   both reference abilities call them, so nothing here compiles without them.
   Note the tier-1 tag budget: the bp-g2 scale-up plan (not shipped) I1.5 assumed **3** new
   tags; the real count is **4** (2 here, 1 for `gp-heal-over-time`, 1 for the
   double-jump task).
4. **`cb lint` will also WARN `anti-gaming-count`.** The spec carries **6**
   anti-gaming entries (AG-1..AG-6, the PIN's "floor of 4, not a cap"), and the
   linter WARNs above 5. This is the same state `gp-poison-dot-stack-cpp` ships
   in; it is a WARN, not an ERROR, and folding two sharp entries together to
   silence it would cost real coverage.

## Timeline behind the checkpoint schedule `{0.5, 1.2, 1.9, 2.6, 3.3}`

| cp | t (s) | fixture action | window that closes |
|---|---|---|---|
| 0 | 0.5 | HO-1..HO-5 ladder; `SetHealth(60)`; read `H0`; trigger `Ability.Damage` | - |
| 1 | 1.2 | read `H1`; trigger `Ability.Damage` | `Drop1 = H0 - H1` over (cp0,cp1], 0.7 s |
| 2 | 1.9 | read `H2`; trigger `Ability.Heal` | `Drop2 = H1 - H2` over (cp1,cp2], 0.7 s |
| 3 | 2.6 | read `H3` (nothing triggered) | `HealDelta = H3 - H2` over (cp2,cp3], 0.7 s |
| 4 | 3.3 | read `H4`; ALL final asserts | `IdleDelta = H4 - H3` over (cp3,cp4], 0.7 s |

`TimeLimit` is set by the base from the last checkpoint plus its margin
(~5.3 s), so a stuck test FAILs rather than hanging.

The three **gated** windows are congruent by construction (all 0.7 s, all at
equal offsets from their own triggers). That congruence is the entire premise
of HO-9 and HO-10 - a ratio of unequal windows leaves tick-count quantization
uncancelled and reads differently by phase, which is why the poison fixture's
stack cap was ungateable until its rate windows were made congruent. The
fixture's second `[HEALTHOPS-FINAL]` line reports the **realized** window
lengths (`w1..w4`, from `CrossingTimes`) so the premise is measured evidence,
not a comment.

**Expected reference trace, PREDICTED not measured** (the -10 / +10 reference,
preset 60): `60 -> 50 -> 40 -> 50 -> 50`. `Drop1 = 10`, `Drop2 = 10`
(`repeatRatio = 1.00`), `HealDelta = 10` (`symRatio = 1.00`),
`IdleDelta = 0`, magnitude 10 inside `[5, 25]`. If the first real run does not
reproduce this line for line, **stop and find out why before touching a bar**.

## The bars: every one PROPOSED - NOT YET MEASURED

Declared in `HealthAttributeOpsFunctionalTest.h`. The last column is what must
be true before the value may be called calibrated.

| constant | proposed | gate | what must be MEASURED to pin it |
|---|---|---|---|
| `HealthInitExpected` | 100.0 | HO-3 | Not a tolerance - it is the value the prompt DISCLOSES ("initialized to 100"), which is what makes an absolute bar lawful. Confirm only that a conforming reference reads exactly 100.0 before any fixture write. |
| `BaselineEpsilon` | 0.5 | HO-3, HO-4 | Absorbs float noise on a direct read-back only (no operation can have run inside cp0). Measure `\|init - 100\|` and `\|writeProbeRead - 37\|` on the reference; both should be exactly 0.0. |
| `WriteProbeValue` | 37.0 | HO-4 | Not a bar - a design choice that must stay `!= HealthInitExpected` so an inert-write set that inits at 100 cannot pass vacuously (AG-2). |
| `PresetHealth` | 60.0 | (leg setup) | Not a bar - PIN.md D4. Verify only that the whole reference leg stays strictly inside `(0, 100)`: `min(h0..h4) > 0` and `max(h0..h4) < 100`. If HO-8's band top is ever raised, this must come down. |
| `MagnitudeMin` / `MagnitudeMax` | 5.0 / 25.0 | HO-8 | Disclosed by the prompt ("a fixed amount between 5 and 25"); the bar is the prompt, not a measurement. What must be measured is the **misattribution** claim: an out-of-band variant (e.g. 50 per application) must die at HO-8's named string, NOT at HO-9's. |
| `DeltaEpsilon` | 0.5 | HO-7, HO-11, ratio guard | **The one genuinely two-population bar.** Conforming side: `\|IdleDelta\|` on the reference (predicted exactly 0.0 - an instant effect leaves nothing active). Violating side: the smallest `\|IdleDelta\|` a plausible regen-drift variant produces across a 0.7 s window. Pin midway and record the margin on each side. |
| `RepeatTol` | 0.10 | HO-9 | Conforming side: `repeatRatio` on the reference (predicted exactly 1.00). Violating side: `repeatRatio` measured on `damage-to-zero/` (predicted 0.00). Record both, then pin. |
| `SymTol` | 0.10 | HO-10 | Conforming side: `symRatio` on the reference (predicted exactly 1.00). Violating side: `symRatio` measured on `heal-to-full/` - PIN.md section 4 predicts **6.00** for a preset of 60 with a 10-point damage. Record both, then pin. |

**Note on `RepeatTol` / `SymTol`.** Both are expected to have an enormous
margin (a conforming instant effect is exactly repeatable under fixed timestep,
so both ratios should read 1.00 to the digit), which means the 0.10 window is
probably far tighter than it needs to be. **Do not loosen it on that
reasoning alone.** The population that matters is the *gaming* side, and the
nearest gaming solve to 1.00 has not been enumerated. Widening a tolerance
without measuring what it lets through is exactly how a discriminator stops
discriminating.

**Note on `DeltaEpsilon` doing three jobs.** It is HO-7's direction floor,
HO-11's idle floor, and the ratio guard's denominator floor. If the measured
regen-drift population forces it upward, check that HO-7 is still satisfied by
the *smallest lawful* damage (5.0 at the band floor) with margin - one constant
serving three gates is convenient until the two populations pull opposite ways.

## What must be measured, and the exact commands

Run in order. **Nothing below has been run.** The repo's build-contention law
applies: `Build.bat`'s mutex is keyed on the ENGINE INSTALL, so a concurrent
build elsewhere on the box can make any of these return exit 1 with no compile
error - run these alone.

```powershell
# 0. Prerequisites (blockers above): rename the task folder to
#    tasks/cpp/gp-health-attribute-ops-cpp/, then lint clean.
python tools/verify-single/tasklint.py tasks/cpp/gp-health-attribute-ops-cpp/task.md

# 1. Author the map (needs ThirdPersonEditor BUILT + a real off-screen RHI;
#    it crashes under -nullrhi). The committed binary is the ONLY map source.
& "$env:CB_UE_ROOT\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" `
    UE-projects\ThirdPerson\ThirdPerson.uproject `
    -ExecutePythonScript="tasks\cpp\gp-health-attribute-ops-cpp\aids\author_L_HealthOps.py" `
    -unattended -nopause -nosplash -RenderOffScreen

# 2. THE calibration run - grade the committed reference and read the two
#    [HEALTHOPS-FINAL] lines out of the L2 log.
$env:CB_UE_ROOT='<UE-root>'
python tools/verify-single/run_task.py `
    --task tasks/cpp/gp-health-attribute-ops-cpp/task.md `
    --submission tasks/cpp/gp-health-attribute-ops-cpp/reference `
    --substrate-from-live --ue-root $env:CB_UE_ROOT

# 3. The empty-submission leg (must FAIL at HO-1's named derivation string,
#    because an empty submission resolves to the generic scaffold pawn).
python tools/verify-single/run_task.py `
    --task tasks/cpp/gp-health-attribute-ops-cpp/task.md `
    --submission <an-empty-dir> --substrate-from-live --ue-root $env:CB_UE_ROOT

# 4. One variant per anti-gaming note, each dying at its OWN named substring.
#    (None of these variants exist yet - see "Discrimination variants" below.)
python tools/verify-single/run_task.py --task tasks/cpp/gp-health-attribute-ops-cpp/task.md `
    --submission tasks/cpp/gp-health-attribute-ops-cpp/discrimination/<variant> `
    --substrate-from-live --ue-root $env:CB_UE_ROOT

# 5. Once green, the token-free reference gate and the full sweep:
cb refgate gp-health-attribute-ops-cpp
cb discriminate gp-health-attribute-ops-cpp
```

The two log lines to harvest from step 2 (both are emitted BEFORE any gate, so
they survive a FAIL):

```text
[HEALTHOPS-FINAL] grantedDamage= grantedHeal= activatedDamage= activatedHeal=
                  init= writeProbe= h0= h1= h2= h3= h4=
                  drop1= drop2= heal= repeatRatio= symRatio=
[HEALTHOPS-FINAL] baseline= idleDelta= w1= w2= w3= w4= (bars PROPOSED ...)
```

Write the harvested numbers back into the bar table above with the margin on
each side, then delete the `PROPOSED - NOT YET MEASURED` banners from the
fixture header and both effect sources in the same change.

## Discrimination variants - PLANNED, none committed

PIN.md section 6 requires one committed one-delta variant per anti-gaming note
(6), each dying at its **own** named substring (I0.4's uniqueness oracle - a
variant that fails at some *other* gate proves nothing about the gate it was
written for).

| variant (planned) | the ONE delta from `reference/` | must FAIL at | predicted reading |
|---|---|---|---|
| `generic-pawn-subclass/` | pawn parents `ACraftBenchCharacter` instead of the task base | HO-1 | derivation string names the generic pawn |
| `no-health-system/` | drop the `HealthAttributes` subobject; everything else verbatim | HO-2 | presence string |
| `inert-attribute-set/` | an attribute set that reads a shadow value and ignores writes | HO-4 | `wrote 37.0, read back 100.0` |
| `meshless-pawn/` | remove the `FObjectFinder` mesh assignment | HO-5 | visibility string |
| `no-ability-tick-damage/` | move the damage/heal into `Tick`; grant nothing | HO-6a | `granted=0` |
| `damage-to-zero/` | damage sets `Health = 0` instead of subtracting | HO-9 | `second removed 0.0 (ratio 0.00 ...)` |
| `heal-to-full/` | heal sets `Health = MaxHealth` instead of adding | HO-10 | `ratio 6.00, need 0.90-1.10` |
| `out-of-band-magnitude/` | magnitude 50 instead of 10 | **HO-8**, not HO-9 | `moved Health by 50.0` |
| `regen-drift/` | a tick/timer that raises Health continuously | HO-11 | idle-window string |

Two of these earn their place beyond the AG floor. **`out-of-band-magnitude/`
is the F5 regression test**: HO-8 exists specifically so a bad magnitude fails
by its own name, and the only way to know it does is to run a variant that
would otherwise have died at HO-9. **`heal-to-full/` is the task's headline
discriminator** - PIN.md section 4 calls it "the one a real model writes": it
passes HO-1 through HO-7 and HO-11, is activatable by tag, is not a tick hack,
and is a reasonable-sounding reading of "a heal ability which raises Health".
If it ever stops FAILing, this task has lost its only defense against a heal
that ignores its own magnitude.

## Correlation with `gp-poison-dot-stack-cpp` (constraint C1)

The stage-1 ladder HO-1..HO-5 is **lifted** from
`PoisonStackFunctionalTest.cpp` - same derivation gate, same presence gate,
same init-100 read-before-write, same 37 write probe, same visible-character
check, same named FAIL strings. That reuse is deliberate and is precisely why
this task costs zero new verifier infrastructure. It also means the two tasks'
**stage-1 pass populations are correlated**: a model that fails stage 1 here
fails it there for the same reason, and the two results are not independent
evidence about the model. This must be:

- declared here (done, this section), and
- carried as **constraint C1** in the internal design note (not shipped).

Anyone reading a bp-g2 tier-1 leaderboard should treat "passed stage 1 on both
health tasks" as roughly one bit, not two.

## Design decisions worth re-reading before a bar change

1. **The operation seam is a gameplay TAG, not a reflected function name**
   (PIN.md D1). the bp-g2 scale-up plan (not shipped) section 1 T1.1 assumed `DoDamage` /
   `DoHeal` reflected seams; reaching those needs a second Hard Rule #2
   exception for naming deliverable functions AND the `CraftBenchSeam`
   marshalling layer, which is V2.4 and explicitly not tier 1. The tag route
   uses `NumGrantedAbilitiesWithTag` / `TriggerAbilityByTag`, both already on
   the base. Declining D1 moves T1.1 behind V2.4 and it stops being the cheap
   Band-A floor.
2. **`MaxHealth` is disclosed nowhere and gated nowhere** (PIN.md D2). The
   source row asks for "health and max health values", but
   `UCraftBenchAttributeSet` ships `MaxHealth` uninitialized (reads 0) and
   upward clamping is `gp-heal-over-time`'s whole axis. Gating it in both
   families double-books the capability and re-correlates two of the four
   tier-1 cells. The reference initializes it to 100 only for human legibility;
   no gate reads it and the set applies no clamping, so it cannot bound the
   heal. Drop that line if the reference should demonstrate strictly what the
   prompt discloses.
3. **Reads use the CURRENT value, not the base** (the V1.4 law in
   `CraftBenchPawnFunctionalTest.h`). A damage or heal implemented as a
   duration/infinite modifier - or as an `Override` - never touches the BASE,
   so a base-only read would report `drop1 == 0` for a conforming solve and
   false-FAIL it at HO-7. Writes still use `SetNumericAttributeBase`; no base
   helper exists.
4. **Sample ordering** (`H0` after the preset and before the trigger; `H1`/`H2`
   before their own triggers). An instant effect executes synchronously inside
   `TryActivateAbilitiesByTag`, so a read-after-trigger folds the first
   application into the baseline and makes `Drop1` read 0. Do not "tidy" the
   reads to the top of `OnCheckpoint`.
5. **HO-6 is four checks.** The base's `bAbilityActivated` is a single latch
   across all tags, so it cannot name which tag failed; the fixture keeps
   private per-tag latches. If a future refactor pushes per-tag latches down
   into the base, delete the private ones here rather than keeping both.
6. **The ratio-denominator guard is unreachable and stays anyway.** HO-7 plus
   HO-8 already bound `Drop1` into `[5, 25]`. The guard exists so a future
   reordering of the gates can never reach a division by zero, and it refuses
   by a named string rather than dividing. The `0.0` ratio fallback beside it
   exists only so the diagnostic line always prints; nothing gates on it.
7. **The reference uses an instant GameplayEffect, not `ApplyModToAttribute`.**
   The source record itself says "GAS effects for the operations"; a competent
   engineer writes an effect; `ApplyModToAttribute` bypasses the
   aggregator/execution path and models the very "poke the attribute directly"
   shape AG-3 punishes. An instant effect also leaves nothing active
   afterwards, so **HO-11's idle window is satisfied structurally rather than
   by luck**. Cost: 6 file pairs instead of 4.

## Gate to G2 (PIN.md section 6) - status

- [ ] Reference PASS.
- [ ] Empty submission FAIL at HO-1's named derivation substring.
- [ ] One committed one-delta discrimination variant per anti-gaming note (6
      minimum; 9 planned above), each dying at its **own** named substring.
- [ ] Both populations for HO-9 / HO-10 / HO-11 recorded in this file with the
      chosen bar and the margin on each side.
- [ ] Correlation with `gp-poison-dot-stack-cpp` stage 1 declared here (**done**)
      **and** carried as constraint C1 in the internal design note (not shipped) (not done).
- [ ] The `PROPOSED - NOT YET MEASURED` banners deleted from the fixture header
      and both reference effect sources, in the same change that writes the
      measured numbers here.
