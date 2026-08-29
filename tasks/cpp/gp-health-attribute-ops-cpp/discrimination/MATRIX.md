> ## HO-11 GAP CLOSED 2026-08-10 - `slow-regen/`
>
> The gap recorded above (HO-11 detecting but unreported, no leg dying at it) is
> now closed by a variant authored for exactly that purpose. MEASURED:
>
> ```
> drop1=10.00 drop2=10.00 heal=10.00 repeatRatio=1.00 symRatio=1.00
> h3=50.0 -> h4=51.8   idleDelta=1.80 > IdleEpsilon 0.50
> FAIL: "Health kept moving with no operation active: 50.0 -> 51.8 in the idle window"
> ```
>
> It passes HO-7..HO-10 with the ratios at exactly 1.00 - i.e. its drift is small
> enough not to contaminate the heal window, unlike `regen/`, which dies at HO-10
> first - and dies at HO-11 and only HO-11. Every gate in this task now has a
> committed leg failing at it by its own name.

> ## MEASURED 2026-08-10 - full matrix green (Windows / UE 5.8, `--substrate-from-live`)
>
> `reference` **PASS**; all 8 negative legs **FAIL at L2, each by a named assertion**
> (no wrong-reason FAILs: every leg's L1 passed). Reference population, which
> retires every `PROPOSED` bar in the fixture header:
>
> ```
> drop1=10.00 drop2=10.00 heal=10.00 repeatRatio=1.00 symRatio=1.00 idleDelta=0.00
> w1=0.700 w2=0.700 w3=0.700 w4=0.700     <- the ratio windows are congruent, MEASURED
> ```
>
> **HO-11 HAS NO LEG THAT DIES AT IT - the one honest gap in this matrix.**
> `regen/` was authored to prove HO-11 (AG-6, passive drift). It does drift:
> `h3=54.2 -> h4=55.6`, an `idleDelta` of **1.4 against an `IdleEpsilon` of 0.5**,
> so HO-11 *would* fire. But the regeneration also contaminates the heal window
> (`symRatio=1.33`), and **HO-10 is evaluated first**, so HO-10 is what reports.
> HO-11 is therefore *detecting* but *unreported* - it is the only gate in this
> task with no committed variant failing at it, which is exactly the shape that
> hid the poison stop-gate defect for six weeks
> (`tasks/cpp/gp-poison-dot-stack-cpp/discrimination/MATRIX.md`). The task.md
> anti-gaming note 6 is corrected to say so. **Follow-up:** author a
> `slow-regen/` variant tuned to pass HO-7..HO-10 and trip only HO-11 - the
> arithmetic is that it needs a drift under the symmetry tolerance across the
> heal window but over `IdleEpsilon` across the idle window.

# gp-health-attribute-ops-cpp -- discrimination matrix

> ## STATUS: **MEASURED 2026-08-10** (L2 FAIL by name). Every row below is a PREDICTION.
>
> **Nothing in this package has been compiled, graded, or observed.** No build,
> no UBT, no PIE run, no `run_task.py`, no `cb discriminate`. Every "Overall"
> and every "Expected message" cell is derived STATICALLY from three sources:
> the fixture C++
> (`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-health-attribute-ops/HealthAttributeOpsFunctionalTest.cpp`),
> the reference under `../reference/Source/ThirdPerson/`, and the substrate
> classes each variant leans on. Do not cite any row here as measured
> discrimination. The exact commands that promote these rows from PREDICTED to
> MEASURED are in **Re-validate**, below, and the three prerequisites that must
> land first are in **Blockers**.
>
> This is the same convention `gp-glide-stamina-cpp`'s matrix used for its
> 2026-08-08 variant package (predicted first, promoted after a sweep), and the
> same honesty bar: a variant that FAILs at a substring other than its own is a
> mis-authored variant, not a discrimination win.

> **ALL NUMERIC BARS ARE `PROPOSED - NOT YET MEASURED`** (PIN.md section 2). The
> reference's per-application magnitude (10), the `regen/` rate (2.0 Health/s),
> the `no-gas/` drain rate (14.0 Health/s) and the `set-to-constant/` constant
> (50) are CHOSEN to sit far from the bars they must not trip, not calibrated
> against a measured population. The predicted legs below are arithmetic, not
> readings.

**Task:** `tasks/bp-g2/gp-health-attribute-ops/` (front-matter id
`gp-health-attribute-ops-cpp`). **Substrate:** ThirdPerson. **Layers:** L1+L2.
**Fixture:** `L_HealthOps :: AHealthAttributeOpsFunctionalTest`.
**Design contract:** `../PIN.md` -- normative; this package implements it and
does not redesign it.

---

## Blockers (the sweep cannot run until all three are true)

1. **`Content/Maps/L_HealthOps.umap` does not exist.** The task declares
   `fixtures: ["L_HealthOps :: AHealthAttributeOpsFunctionalTest"]`, and a
   committed binary `.umap` is the ONLY map source -- the runner never re-bakes
   one, and a missing binary is an explicit L2 FAIL. `../aids/author_L_HealthOps.py`
   is the authoring aid. Until the map is committed, EVERY row below (reference
   included) fails for a reason that has nothing to do with the submission.
2. **The fixture and the two new gameplay tags are uncommitted.** The runner
   materializes the graded substrate from **git HEAD**, so a HEAD-graded run
   would compile a `CraftBenchTests` module without
   `AHealthAttributeOpsFunctionalTest` and a `CraftBenchGameplayTags` without
   `Ability.Damage` / `Ability.Heal`. Every command in **Re-validate** therefore
   passes `--substrate-from-live`. Do NOT commit mid-sweep to work around this
   (repo convention: committing while a run grades silently downgrades the git-HEAD
   substrate guarantee to a live copy).
3. **The engine must be free.** UBT's mutex is keyed on the ENGINE INSTALL, not
   the project: a contended build returns exit 1 with no compile errors, which
   reads exactly like a variant failing L1. Run the sweep with no other session
   holding UE 5.8.

---

## Predicted reference leg (the calibration source -- ARITHMETIC, NOT MEASURED)

Schedule `{0.5, 1.2, 1.9, 2.6, 3.3}`; four congruent 0.7 s windows; preset 60;
reference magnitude 10 down and 10 up.

| cp | t (s) | Health read | what happens next |
|---|---|---|---|
| 0 | 0.5 | init 100, write probe 37 -> 37, mesh present | preset to 60, `H0 = 60`, trigger `Ability.Damage` |
| 1 | 1.2 | `H1 = 50` (`drop1 = 10`) | trigger `Ability.Damage` again |
| 2 | 1.9 | `H2 = 40` (`drop2 = 10`) | trigger `Ability.Heal` |
| 3 | 2.6 | `H3 = 50` (`healDelta = 10`) | nothing -- the idle window opens |
| 4 | 3.3 | `H4 = 50` (`idleDelta = 0`) | final asserts |

Predicted `repeatRatio = 1.00`, `symRatio = 1.00`, magnitude `10` dead centre of
the disclosed 5-25 band, idle drift exactly zero. The reference is deliberately
the maximum-margin point on every gate -- an instant GameplayEffect leaves
nothing active, so HO-11's idle window is satisfied structurally rather than by
luck.

---

## Matrix

Each row's "Expected message" cell carries **exactly one backticked literal**,
and that literal is a verified **literal run** of a real
`FinishTest(EFunctionalTestResult::Failed, ...)` message in the fixture -- no
fragment spans a `%`-placeholder, so nothing here depends on a value the fixture
interpolates. (`granted=` is producible from `... granted=%d`; `granted=0` never
is.) Predicted numbers are deliberately kept OUTSIDE backticks: every backticked
span is a REQUIRED literal under `cb discriminate`'s ALL-of semantics, so a
human-readable summary in ticks could never match and would read as a
wrong-reason FAIL.

| Submission | Overall | Fails at | Expected message |
|---|---|---|---|
| `../reference` | **PASS** *(PREDICTED -- NOT YET RUN)* | -- | all eleven gates green; predicted drop1 10.0, drop2 10.0, heal 10.0, repeatRatio 1.00, symRatio 1.00, idleDelta 0.00 |
| empty (no overlay -> generic scaffold pawn) | **FAIL** *(PREDICTED)* | cp0, HO-1 derivation | `does not derive from the provided task base pawn (CraftBenchBareCharacter).` -- with no submission the resolver falls back to ACraftBenchCharacter, which is not on the task-base lineage, so the very first rung of the stage-1 ladder fires. Shares this substring with generic-pawn/ -- see the ISOLATION CAVEAT below |
| `generic-pawn/` (AG-1, derivation half) | **FAIL** *(PREDICTED)* | cp0, HO-1 derivation | `does not derive from the provided task base pawn (CraftBenchBareCharacter).` -- the reference with ONE line changed: parent ACraftBenchCharacter (the generic scaffold, which pre-builds an attribute set) instead of ACraftBenchBareCharacter. Stage 1, both abilities and the mesh are retained verbatim, so this is a behaviorally complete solve whose only defect is the parent class |
| `no-health-system/` (AG-1, presence half) | **FAIL** *(PREDICTED)* | cp0, HO-2 presence | `stage 1 not built: the pawn's health attribute system is absent` -- a complete, correct STAGE 2 on a task-base pawn that never constructs the contract attribute set. Same delta, same gate and same named string as the already-committed gp-poison-dot-stack-cpp/discrimination/no-health-system/ (PIN.md constraint C1) |
| `inert-set/` (AG-2) | **FAIL** *(PREDICTED)* | cp0, HO-4 write probe | `stage 1 incomplete: health attribute is inert, write-then-read failed (wrote` -- the set is a subclass of the contract set whose PreAttributeBaseChange / PreAttributeChange force Health back to a shadow value of 100. HO-2 and HO-3 both PASS (the set is present and reads 100); the fixture writes 37 and reads back 100. This is why the write probe is at 37 and not at 100 |
| `no-mesh/` (AG-5) | **FAIL** *(PREDICTED)* | cp0, HO-5 visibility | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` -- the reference minus the constructor mesh assignment. Behaviorally perfect; the only leg that proves HO-5 discriminates on the visibility axis alone |
| `no-gas/` (AG-3) | **FAIL** *(PREDICTED)* | cp4, HO-6 granted-damage | `no activatable ability tagged Ability.Damage on the pawn (health operations not implemented as activatable abilities). granted=` -- GrantedAbilities is empty and Health is driven from Tick instead. The drain rate is tuned so drop1 and drop2 both read about 9.8 and repeatRatio about 1.00: the numbers look conforming and the ONLY thing separating this from the reference is the granted count |
| `set-to-constant/` (AG-4) | **FAIL** *(PREDICTED)* | cp4, HO-9 repeatability | `the damage operation is not a fixed amount: the first application removed` -- the damage effect's modifier is an Override to the constant 50 instead of an additive -10. From the preset of 60 the FIRST application removes 10 (so HO-7 and HO-8 both pass and look conforming) and the second removes 0, driving repeatRatio to 0.00 |
| `slow-regen/` (AG-6b, the HO-11 leg) | **FAIL** *(**MEASURED 2026-08-10**)* | cp4, HO-11 idle drift | `Health kept moving with no operation active:` -- drift tuned small enough to leave the heal window uncontaminated, so it clears HO-7..HO-10 (ratios exactly 1.00) and dies at HO-11 and ONLY HO-11. Measured h3=50.0 -> h4=51.8, idleDelta=1.80 > IdleEpsilon 0.50. **Row added 2026-08-13**: the variant dir and its measurement both existed, but with no row here the runner could not credit the leg |
| `regen/` (AG-6) | **FAIL** *(PREDICTED)* | cp4, **HO-10 symmetry -- NOT HO-11** | `heal does not restore what damage removes: one damage removed` -- the reference plus a textbook passive regeneration loop in Tick. It fails a gate one step EARLIER than AG-6's stated defense, and that is a structural property of the current bars, not a mis-authored variant. Read **HO-11 IS NOT REACHABLE**, below, before changing anything |

---

## ISOLATION CAVEAT -- `empty` and `generic-pawn/` share one named FAIL

Both land on HO-1's `does not derive from the provided task base pawn
(CraftBenchBareCharacter).` It is irreducible: HO-1 is the FIRST rung of the
stage-1 ladder, and an empty submission resolves to the generic scaffold pawn,
which is exactly the class `generic-pawn/` parents on purpose. Any variant
targeting a task's first gate collides with `empty` -- which is precisely why the
substring oracle exempts the `empty` leg from its pairwise uniqueness matrix
(`matrix_oracle.is_isolation_leg`).

**The collision is not a duplicate.** `empty` reaches HO-1 incidentally: it
builds nothing at all, so the gate it trips first is an accident of ladder
order -- it would equally have failed HO-2, HO-3 and HO-5. `generic-pawn/` is a
behaviorally COMPLETE solve -- contract attribute set, `InitHealth(100)`, both
tagged abilities granted, mannequin assigned -- whose single defect is the parent
class. It is therefore the only leg that proves HO-1 discriminates on the
DERIVATION axis alone, which is the whole content of AG-1's first half.

**Among the seven committed variants every substring is unique**, and no
variant's substring is entailed by another's (checked as strings, both
directions). At least one variant (`no-gas/`, `set-to-constant/`, `regen/`,
`inert-set/`, `no-mesh/`, `no-health-system/` -- six of the seven) is NOT entailed
by `empty`, so the matrix does not collapse onto the smoke floor.

---

## HO-11 IS NOT REACHABLE by any one-delta passive drift -- a PIN calibration finding

**This is the most important thing in this file.** `regen/` is specified by
AG-6 to die at HO-11 (the idle window). With the bars as PIN.md section 2 pins
them and the reference's magnitude, **no constant-rate passive drift can land
there.** The variant is shipped anyway, with its true expected gate recorded.

Let `M` be the per-application magnitude (reference: 10), `W` the window length
(0.7 s, all four windows congruent), `R` the drift rate in Health/s, and write
`x = R*W` for the drift accumulated in one window. A passive drift contributes
`x` to EVERY window, so:

| gate | quantity | condition |
|---|---|---|
| HO-7 direction | `drop1 = M - x` | needs `M - x > DeltaEpsilon` (0.5) -> `x < 9.5` |
| HO-8 band | `drop1 = M - x` | needs `5 <= M - x <= 25` -> `x <= 5` |
| HO-9 repeatability | `drop2/drop1 = (M-x)/(M-x)` | **exactly 1.00 -- a constant drift cancels, HO-9 can never see it** |
| HO-10 symmetry | `healDelta/drop1 = (M+x)/(M-x)` | passes only while `x <= M/21` -> for M=10, `x <= 0.476` |
| HO-11 idle | `idleDelta = x` | fires only when `x > DeltaEpsilon` (0.5) |

HO-10 is evaluated BEFORE HO-11, and its pass condition (`x <= 0.476`) and
HO-11's fire condition (`x > 0.5`) **do not overlap**. Raising the rate only
moves the verdict further away: `x > 5` trips HO-8, `x > 9.5` trips HO-7. The
general existence condition is

> `DeltaEpsilon < x <= M * SymTol / (2 + SymTol)`, i.e. a rate window exists only
> when `M > DeltaEpsilon * (2 + SymTol) / SymTol = 0.5 * 21 = 10.5`.

The reference's `M = 10` sits just under that threshold, so the window is empty.
At `M = 25` (the band top) a rate does exist, but the margins on HO-8 and HO-10
are both a few percent -- not a bar anyone should pin a variant on, and changing
`M` would make the variant a two-delta submission anyway.

**Consequences, in order of importance:**

1. **AG-6 is currently defended by HO-10, not HO-11.** The passive-regen shape
   IS caught -- deterministically, by name, with a wide margin (predicted
   symRatio about 1.33 against a 1.10 bar) -- so the anti-gaming note is not
   open. It is the *attribution* that is wrong: the run will say "heal does not
   restore what damage removes" about a submission whose heal is perfectly
   correct.
2. **HO-11 has NO committed variant and is therefore UNPROVEN.** It may also be
   unreachable in practice by any real submission, which would make it a
   decorative gate.
3. **Recommended PIN fix (an objection, not a change made here -- the PIN is
   normative):** decouple the IDLE window length from the three gated windows.
   Moving cp4 from 3.3 to 4.7 makes the idle window 2.1 s while the gated
   windows stay 0.7 s, and HO-11 then fires at `R > 0.24` while HO-10 still
   passes up to `R > 0.68` -- a real, non-empty band with margin on both sides
   at the reference magnitude. Alternatively, shrink HO-11's noise floor below
   `M * SymTol / (2 + SymTol) / W`. Either is a PIN edit and belongs to whoever
   signs the sheet.
4. **The recipe for a variant that WOULD isolate HO-11 today** (recorded so it is
   not re-derived): make the drift EVENT-STARTED rather than passive -- have the
   heal ability additionally apply an infinite periodic effect with
   `bExecutePeriodicEffectOnApplication = false` and a period that puts its first
   tick inside `(cp3, cp4]`. That leaves all three gated windows untouched
   (symRatio 1.00) and moves Health only in the idle window. It is NOT shipped
   because it is phase-tuned against the schedule: the first tick's placement
   depends on the trigger time, so it would be fragile in exactly the way
   `gp-poison-dot-stack-cpp`'s `permanent-drain/` taught this repo to distrust.
   Ship it only alongside a measured run.

---

## A second attribution trap, found while authoring -- the checkpoint clock is ABSOLUTE

`ACraftBenchFunctionalTest` anchors checkpoints to **world game-time since the
PIE world began play** (`CraftBenchFunctionalTest.cpp:99-106`), and the pawn is
spawned in `PrepareTest` -- roughly half a second of world time BEFORE checkpoint
0 at t=0.5 s. Any submission (or variant) that moves Health from `BeginPlay` or
an ungated `Tick` has therefore already moved it off 100 by the time HO-3 reads
it, and HO-3 (`|Health - 100| <= 0.5`, read before any fixture write) fires
first.

Both drift variants here carry a `Health < MaxHealth` guard specifically to
dodge that, so the drift contributes exactly zero to the stage-1 ladder and
exactly `R * 0.7` to each window afterwards. This is a load-bearing detail of
the variants, not a stylistic one -- remove the guard and `no-gas/` dies at HO-3
instead of HO-6, and `regen/` dies at HO-3 instead of HO-10.

**It is also a live diagnostic hazard for real submissions**, and it is recorded
in Known holes below: an agent that implements the operations as a
`BeginPlay`-started drift -- precisely AG-3's stated shape -- will be told
"Health must initialize to 100", which is a true statement about a false cause.

---

## Deterministic gates (what flips PASS/FAIL)

Order matters: every gate below returns on failure, so a submission is only ever
judged by the FIRST one it trips. HO-1..HO-5 run at checkpoint 0; HO-6..HO-11 at
the last checkpoint.

0. **The stage-1 ladder (checkpoint 0)**, lifted verbatim from
   `gp-poison-dot-stack-cpp` (PIN.md constraint C1 -- the two tasks' stage-1
   populations are correlated by design):
   1. **HO-1** the graded pawn derives from `ACraftBenchBareCharacter`;
   2. **HO-2** the ASC carries an attribute set exposing Health;
   3. **HO-3** Health reads 100 BEFORE any fixture write (absolute bar, lawful
      only because the prompt discloses "initialized to 100");
   4. **HO-4** write-then-read at 37 (`!= 100` on purpose, so an inert set that
      shadows 100 cannot pass vacuously);
   5. **HO-5** a mesh component with an assigned mesh exists on the pawn.
1. **HO-6** both operations are activatable abilities: `Ability.Damage` and
   `Ability.Heal` each granted (count `>= 1`) AND each observed activating on
   `TryActivateAbilitiesByTag` -- four checks, named per tag.
2. **HO-7** the first damage application lowers Health by more than the noise
   floor (0.5).
3. **HO-8** that first application's magnitude sits inside the DISCLOSED 5-25
   band. Exists so a non-conforming magnitude fails by its own name instead of
   being misattributed to HO-9 or HO-10.
4. **HO-9** repeatability: `drop2/drop1` within `1.00 +/- 0.10`, over two
   congruent 0.7 s windows.
5. **HO-10** symmetry: `healDelta/drop1` within `1.00 +/- 0.10`, congruent
   windows again.
6. **HO-11** the operations are event-driven: `|idleDelta| <= 0.5` across
   `(cp3, cp4]`, where nothing is triggered.

A ratio-denominator guard sits between HO-8 and HO-9 with its own named FAIL. It
is unreachable in practice (HO-7 and HO-8 have already bounded `drop1` into
`[5, 25]`) and exists so a future reordering can never divide by zero.

---

## Per-note coverage (one committed variant per anti-gaming note)

Every row states which of the fixture's named FAIL substrings the delta is
expected to hit. **Substrings are unique per variant.**

| Anti-gaming note (PIN.md section 3) | Committed variant | Expected verdict | Named substring it must FAIL on | Status |
|---|---|---|---|---|
| AG-1 -- subclass the generic character, inherit its pre-built set | `generic-pawn` (dir) | FAIL at HO-1 | `does not derive from the provided task base pawn (CraftBenchBareCharacter).` | ****MEASURED 2026-08-10** (L2 FAIL by name)** |
| AG-1 -- second half: ship stage 2 on a pawn with no health system | `no-health-system` (dir) | FAIL at HO-2 | `stage 1 not built: the pawn's health attribute system is absent` | ****MEASURED 2026-08-10** (L2 FAIL by name)** |
| AG-2 -- an attribute set that reads its own shadow and ignores writes | `inert-set` (dir) | FAIL at HO-4 | `stage 1 incomplete: health attribute is inert, write-then-read failed (wrote` | ****MEASURED 2026-08-10** (L2 FAIL by name)** |
| AG-3 -- move Health from Tick or BeginPlay with no ability granted | `no-gas` (dir) | FAIL at HO-6 | `no activatable ability tagged Ability.Damage on the pawn (health operations not implemented as activatable abilities). granted=` | ****MEASURED 2026-08-10** (L2 FAIL by name)** |
| AG-4 -- damage implemented as "set Health to a constant" | `set-to-constant` (dir) | FAIL at HO-9 | `the damage operation is not a fixed amount: the first application removed` | ****MEASURED 2026-08-10** (L2 FAIL by name)** |
| AG-5 -- a meshless pawn: conforming but invisible in the film strip | `no-mesh` (dir) | FAIL at HO-5 | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | ****MEASURED 2026-08-10** (L2 FAIL by name)** |
| AG-6 -- a passive regeneration loop that makes the heal look like it worked | `regen` (dir) | FAIL at **HO-10**, not HO-11 | `heal does not restore what damage removes: one damage removed` | ****MEASURED 2026-08-10** (L2 FAIL by name).** Lands one gate early by construction -- see HO-11 IS NOT REACHABLE |

---

## The fixture's named FAIL substrings, and which note each defends

Enumerated from every `FinishTest(EFunctionalTestResult::Failed, ...)` in
`HealthAttributeOpsFunctionalTest.cpp`. Each entry is the longest LITERAL RUN of
its message -- the text between two `%`-placeholders -- because only literal runs
survive verbatim into the log. The base-class conditions this fixture inherits
(`STALE WORLD: ...` from `ACraftBenchFunctionalTest`, `SpawnAndPossessPawn: no
world` / `SpawnAndPossessPawn: spawn of %s failed` and the three
`ApplyEffectToPawn: ...` messages from `ACraftBenchPawnFunctionalTest`) are
harness conditions, not gates, and are deliberately not listed: none is
gameable, and this fixture never calls `ApplyEffectToPawn` at all.

| # | Named literal run | Fires at | Defends |
|---|---|---|---|
| 1 | `pawn did not spawn/resolve` | any checkpoint | no note -- harness/resolution condition |
| 2 | `pawn has no AbilitySystemComponent` | any checkpoint | no note -- harness condition (the task base always builds one) |
| 3 | `does not derive from the provided task base pawn (CraftBenchBareCharacter).` | cp0, HO-1 | AG-1 (`generic-pawn/`); also the `empty` leg |
| 4 | `stage 1 not built: the pawn's health attribute system is absent` | cp0, HO-2 | AG-1 (`no-health-system/`) |
| 5 | `stage 1 incomplete: Health must initialize to 100 but read` | cp0, HO-3 | AG-1 -- **no committed variant**, see hole (a) |
| 6 | `stage 1 incomplete: health attribute is inert, write-then-read failed (wrote` | cp0, HO-4 | AG-2 (`inert-set/`) |
| 7 | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | cp0, HO-5 | AG-5 (`no-mesh/`) |
| 8 | `no activatable ability tagged Ability.Damage on the pawn (health operations not implemented as activatable abilities). granted=` | cp4, HO-6 | AG-3 (`no-gas/`) |
| 9 | `an ability tagged Ability.Damage was granted but did NOT activate on TryActivateAbilitiesByTag` | cp4, HO-6 | AG-3, second half -- **no committed variant**, see hole (b) |
| 10 | `no activatable ability tagged Ability.Heal on the pawn (health operations not implemented as activatable abilities). granted=` | cp4, HO-6 | AG-3 -- **no committed variant** (the damage tag is checked first, so a both-missing submission never reaches it) |
| 11 | `an ability tagged Ability.Heal was granted but did NOT activate on TryActivateAbilitiesByTag` | cp4, HO-6 | AG-3 -- **no committed variant**, see hole (b) |
| 12 | `the damage operation did not lower Health: Health went` | cp4, HO-7 | no note -- direction sanity; **no committed variant**, see hole (c) |
| 13 | `the per-application Health change is outside the stated 5-25 band: one damage moved Health by` | cp4, HO-8 | AG-4 -- **no committed variant**, see hole (c) |
| 14 | `the repeatability and symmetry ratios have no usable denominator: the first damage` | cp4 | no note -- unreachable guard (HO-7/HO-8 bound the denominator first) |
| 15 | `the damage operation is not a fixed amount: the first application removed` | cp4, HO-9 | AG-4 (`set-to-constant/`) |
| 16 | `heal does not restore what damage removes: one damage removed` | cp4, HO-10 | AG-4 -- and, in practice, AG-6 (`regen/`) |
| 17 | `Health kept moving with no operation active:` | cp4, HO-11 | AG-6 -- **no committed variant and none is constructible**, see HO-11 IS NOT REACHABLE |

---

## Known holes (assertions or clauses with no corresponding variant)

- **(a) HO-3 (init-to-100) has no variant.** A `no-init/` overlay is trivial (the
  reference minus `InitHealth(100.0f)`) and would isolate literal 5 cleanly --
  Health reads 0, HO-2 still passes because the set is present. It is not
  shipped because the brief scopes this package to one variant per anti-gaming
  note and HO-3 is already covered as an axis by AG-1's two variants. Add it if
  the acceptance bar is per-GATE rather than per-NOTE.
- **(b) "granted but never activates" has no variant** (literals 9 and 11). It is
  the second half of AG-3's defense and the fixture checks it per tag, which is
  the whole reason the fixture added its own `bDamageActivated`/`bHealActivated`
  latches. A one-delta overlay is possible (an ability whose `CanActivateAbility`
  refuses, or one with a blocking tag), but it was not authored here -- AG-3
  already has `no-gas/`, and this hole is recorded rather than silently filled.
- **(c) HO-7 and HO-8 have no variants** (literals 12 and 13). Both are
  reachable by trivial one-line deltas (a heal effect wired to the damage
  ability; a magnitude of 60). They are deliberately NOT shipped: `set-to-constant/`
  is constructed precisely to sail past both so that its FAIL is attributable to
  HO-9, and shipping a magnitude-60 variant as well would test the same
  disclosed-band arithmetic twice.
- **(d) A BeginPlay/Tick-drift submission is diagnosed as an HO-3 failure.** See
  "the checkpoint clock is ABSOLUTE", above. This is not a gaming hole -- the
  submission still FAILs -- but the named reason is misleading, and AG-3 names
  exactly that shape. Closing it needs a fixture change (e.g. deferring the
  init read, or reporting the drift explicitly), which is verifier-owned and out
  of scope here.
- **(e) The `-bp` twin is not covered.** This package is the `-cpp` C++ overlay
  set only. `gp-health-attribute-ops-bp` adds L2I and will need its own Blueprint
  variants; none of these seven transfer.

---

## What each variant actually changes (one delta each -- verified by diff)

Every variant directory is a FULL submission overlay mirroring
`../reference/Source/ThirdPerson/` (all ten reference files present), with the
listed files being the only ones that differ from the reference byte-for-byte.

| Variant | Files differing from `../reference` | The single axis |
|---|---|---|
| `generic-pawn` (dir) | `HealthOpsPawn.h` | parent class `ACraftBenchBareCharacter` -> `ACraftBenchCharacter` |
| `no-health-system` (dir) | `HealthOpsPawn.h`, `HealthOpsPawn.cpp` | the stage-1 attribute-set subobject is never constructed |
| `inert-set` (dir) | `HealthOpsPawn.cpp` **+ adds** `InertHealthAttributeSet.{h,cpp}` | the attribute set's TYPE ignores writes to Health |
| `no-gas` (dir) | `HealthOpsPawn.h`, `HealthOpsPawn.cpp` | `GrantedAbilities` empty; Health driven from Tick instead |
| `set-to-constant` (dir) | `DamageEffect.cpp` | damage modifier Additive(-10) -> Override(50) |
| `no-mesh` (dir) | `HealthOpsPawn.cpp` | the constructor mesh assignment is deleted |
| `regen` (dir) | `HealthOpsPawn.h`, `HealthOpsPawn.cpp` | a passive Tick regeneration loop is added |

**`inert-set/` is the only variant that adds a file, and it is unavoidable.**
"The writes are ignored" is a property of the attribute-set TYPE --
`PreAttributeBaseChange` and `PreAttributeChange` are `UAttributeSet` virtuals --
so no edit to the reference's existing files can express it. The added class is
a SUBCLASS of `UCraftBenchAttributeSet`, which matters: the ASC resolves an
attribute to its set via `GetAttributeSubobject(Attribute.GetAttributeSetClass())`,
which matches on `IsA`, so the subclass registers and satisfies HO-2 exactly like
the contract set. That is what keeps it an AG-2 variant rather than a second
`no-health-system/`. The engine seams it hooks were read out of the UE 5.8
source, not assumed: `FActiveGameplayEffectsContainer::SetAttributeBaseValue`
calls `Set->PreAttributeBaseChange(Attribute, NewBaseValue)` by reference
(`GameplayEffect.cpp:4001`), and `FGameplayAttribute::SetNumericValueChecked`
calls `Dest->PreAttributeChange(*this, NewValue)` by reference
(`AttributeSet.cpp:82,95`).

**Pawn-resolution check, which only `no-gas/` needs.** `ResolveAgentPawnClass`
prefers a candidate whose CDO grants an ability whose asset tags carry
`PreferredAbilityTag()` = `Ability.Damage`. Six of the seven variants still grant
`UDamageAbility`, so they resolve by preference. `no-gas/` grants nothing, so the
resolver falls back to `Candidates[0]`; `AHealthOpsPawn` is the only non-abstract
NATIVE `ACraftBenchCharacter` subclass in the graded overlay
(`ACraftBenchBareCharacter` is `UCLASS(Abstract)` and is skipped, and every other
task's pawn lives in its own `tasks/<id>/reference/` tree rather than in the
substrate), so it is still the graded pawn and checkpoint 0 stays green. **If a
future task commits a concrete `ACraftBenchCharacter` subclass into
`Source/ThirdPerson/`, re-check that row first.**

---

## Re-validate -- the exact commands that promote every row from PREDICTED to MEASURED

Run on a box with UE 5.8 and **no other session holding the engine** (see
Blockers 3). `--substrate-from-live` is MANDATORY here, not optional: the fixture
and the two new gameplay tags are uncommitted, and the runner grades from git
HEAD by default (Blocker 2). Do not commit while the sweep runs.

```sh
$env:CB_UE_ROOT='<UE-root>'

# the reference must PASS in the same sweep -- it is the control. If it FAILs,
# stop: every variant verdict below is uninterpretable until it is green.
python tools/verify-single/run_task.py --task tasks/bp-g2/gp-health-attribute-ops/task.md `
    --submission tasks/bp-g2/gp-health-attribute-ops/reference --substrate-from-live --ue-root $env:CB_UE_ROOT

python tools/verify-single/run_task.py --task tasks/bp-g2/gp-health-attribute-ops/task.md `
    --submission tasks/bp-g2/gp-health-attribute-ops/discrimination/generic-pawn --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task tasks/bp-g2/gp-health-attribute-ops/task.md `
    --submission tasks/bp-g2/gp-health-attribute-ops/discrimination/no-health-system --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task tasks/bp-g2/gp-health-attribute-ops/task.md `
    --submission tasks/bp-g2/gp-health-attribute-ops/discrimination/inert-set --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task tasks/bp-g2/gp-health-attribute-ops/task.md `
    --submission tasks/bp-g2/gp-health-attribute-ops/discrimination/no-gas --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task tasks/bp-g2/gp-health-attribute-ops/task.md `
    --submission tasks/bp-g2/gp-health-attribute-ops/discrimination/set-to-constant --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task tasks/bp-g2/gp-health-attribute-ops/task.md `
    --submission tasks/bp-g2/gp-health-attribute-ops/discrimination/no-mesh --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task tasks/bp-g2/gp-health-attribute-ops/task.md `
    --submission tasks/bp-g2/gp-health-attribute-ops/discrimination/regen --substrate-from-live --ue-root $env:CB_UE_ROOT
```

The `empty` leg needs no directory -- grade any empty folder as the submission,
or read it off `cb discriminate`, which runs it automatically.

The equivalent single command, once the blockers are cleared and the substrate
is committed:

```sh
cb discriminate gp-health-attribute-ops-cpp
```

**What to do with the results.** Replace every *(PREDICTED)* stamp with the
measured verdict and paste the leg's `[HEALTHOPS-FINAL]` line beside it -- that
one log line carries every raw sample, both ratios and all four bar values, and
it is the calibration instrument for pinning the bars PIN.md section 6 requires
in `notes.md`. Then:

- If the reference PASSes and all seven variants FAIL on their own recorded
  substring, PIN.md section 6's discrimination requirement is met except for
  HO-11, which stays ARGUED -- record that explicitly rather than claiming 6/6.
- If `regen/` FAILs on HO-11's `Health kept moving with no operation active:`
  instead of HO-10's substring, the arithmetic in **HO-11 IS NOT REACHABLE** is
  wrong and the gate ORDER or a bar has changed -- re-read the fixture before
  editing this file.
- If any other variant FAILs at a substring other than its own, that is a
  mis-authored variant, not a discrimination win. Read the `[HEALTHOPS-FINAL]`
  line first; the four `w1..w4` window lengths on its second line are there to
  show whether the congruence HO-9 and HO-10 rest on actually held.

---

## Bounded coverage (honest note)

Nothing has been run. Reference PASS, `empty` FAIL, and one attributable named
FAIL per anti-gaming note is the acceptance gate in `TASK-AUTHOR-GUIDE.md` section B,
and **this task does not meet it yet** -- not because a variant is missing, but
because no leg has been graded. Seven one-delta overlays are committed, and the
static half of the bar IS met: this matrix was run through the repo's own
substring oracle offline (`tools/verify-single/matrix_oracle.py` +
`aura_rig.discriminate.parse_matrix`, no UE, no build, no tokens) and is green on
all four of its checks --

1. **producibility** -- all 8 recorded substrings resolve into the
   `finish_failed` tier, i.e. each is a literal run of a real
   `FinishTest(EFunctionalTestResult::Failed, ...)` message in this task's
   declared fixture, with no fragment spanning a `%`-placeholder;
2. **uniqueness** -- 0 entailment collisions across the 7 isolation legs (the
   `empty` leg is exempt by `matrix_oracle.is_isolation_leg`, and its collision
   with `generic-pawn/` is recorded above rather than hidden);
3. **the empty floor** -- 6 of the 7 variants are NOT entailed by `empty`, so
   the matrix does not re-prove the smoke test;
4. **ASCII** -- zero non-ASCII bytes in the matrix and in every variant source.

Plus, by diff: each variant differs from the reference in exactly one file pair
(`inert-set/` additionally adds one). **Read none of that as verification.** The
oracle's producibility check is one-directional -- its corpus is an
over-approximation of every fixture literal, reachable or not -- so green means
"not disproven", never "observed". Only a real sweep is verification.

The one coverage gap that a sweep will NOT close is HO-11: it has no variant and
none is constructible under the current bars. That is an argument, above, with
the arithmetic shown -- treat it as a PIN calibration item, not as a missing file.

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span is a contiguous literal run of ONE
`FinishTest(EFunctionalTestResult::Failed, ...)` message — no span crosses a
printf placeholder, and (because several messages are split across adjacent
concatenated `TEXT("...")` segments in the C++ source) no span crosses a
literal-concatenation seam either: each span is quoted from within ONE source
segment, so it greps verbatim — read from
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-health-attribute-ops/HealthAttributeOpsFunctionalTest.cpp`
(the eleven HO gates + the two per-checkpoint pre-gates) and from the base
class `UE-projects/ThirdPerson/Source/CraftBenchTests/CraftBenchPawnFunctionalTest.cpp`
(HO-5's `PawnVisiblyRepresented` strings and the pawn resolver). Layers are
L1+L2 only (no L2I), so every gate below is an L2 PIE gate; L1 (both UBT
targets build) is the unconditional precondition for all of them. Gate order
is load-bearing: HO-1..HO-5 run sequentially at cp0 (t=0.5 s, before any
trigger), HO-6..HO-11 sequentially at cp4 (t=3.3 s); every gate `return`s on
failure, so a submission is judged only by the FIRST gate it trips.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | a deliverable pawn class exists, resolves and spawns (implicit in "Deliver your pawn") | fully | pre-gate, every checkpoint — `pawn did not spawn/resolve` | unconditional (runs before every other gate, at all 5 checkpoints) | nothing; an abstract or unspawnable class dies here. NB the resolver prefers the candidate granting an `Ability.Damage`-asset-tagged ability, so with no submission it falls back to the generic scaffold pawn and row 3 fires instead |
| 2 | the pawn owns an ability system ("a task character pawn that owns an ability system") | fully, by inheritance | pre-gate, every checkpoint — `pawn has no AbilitySystemComponent` | pawn unresolvable (row 1) | nothing in practice: the task base builds the ASC, so only a pawn that detaches it can reach this |
| 3 | the pawn is a subclass of the **task** character, not the generic one | fully | HO-1, cp0 — `does not derive from the provided task base` (the sentence continues as `pawn (CraftBenchBareCharacter)` in the next concatenated literal segment, cpp:119–120) | rows 1–2 | nothing on the derivation axis; interposing extra classes in the chain is free (IsA, not identity) |
| 4 | Health exposed through the ability system **using the attribute set type the project provides** | fully (up to subclassing) | HO-2, cp0 — `stage 1 not built: the pawn's health attribute system is absent` | rows 1–3 | a SUBCLASS of the contract set also satisfies it (attribute resolution matches on IsA) — conforming by design; an invented unrelated set fails here |
| 5 | Health **initialized to 100** | fully | HO-3, cp0, read BEFORE any fixture write — `stage 1 incomplete: Health must initialize to 100 but read ` | rows 1–4 | ±0.5 (BaselineEpsilon). Side effect (documented attribution trap): a BeginPlay/Tick drift has already moved Health off 100 by t=0.5 s and is REPORTED here — a true FAIL under a misleading name |
| 6 | Health **readable AND writable** through the standard attribute APIs | fully | HO-4, cp0 — write 37, read back — `stage 1 incomplete: health attribute is inert, write-then-read failed (wrote ` | rows 1–5 | ±0.5 on the read-back; the read side is already proven by HO-3. The probe value 37 ≠ 100 on purpose, so a shadow-100 set cannot pass vacuously |
| 7 | the character is **visibly represented** (a reviewer watching the run can see it) | fully | HO-5, cp0 — `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` (sibling literals for hidden-in-game and scaled-to-~zero meshes) | rows 1–6 | any visible mesh whose component-scale minimum is strictly > 0.01 counts (the gate rejects `GetAbsMin() <= 0.01`, base cpp:344, so exactly 0.01 FAILs) — see row 8 |
| 8 | the mesh is **one of the provided mannequin skeletal meshes** (under `/Game/Characters/`) | **NOT ASSERTED** | — (HO-5 checks only that SOME mesh component has an asset assigned, is not hidden-in-game, and is not scaled to ≤0.01; asset path, mesh type and size are deliberately unchecked per the base-class comment) | — | a static-mesh cube, an engine basic shape, or any non-mannequin skeletal mesh passes HO-5; the mannequin clause is enforced by nothing |
| 9 | a damage ability **tagged `Ability.Damage`** on the ability's own tag list, granted, activatable **by that tag** | fully | HO-6a+b, cp4 — `no activatable ability tagged Ability.Damage on the pawn (health operations not implemented` (segment seam at cpp:285–286; continues `as activatable abilities). granted=`) then `an ability tagged Ability.Damage was granted but did NOT activate on TryActivateAbilitiesByTag` | any cp0 gate fired (the test already finished) | the tag must be in `GetAssetTags()` (granted-count check) — a dynamic-owned tag alone fails; more than one damage-tagged ability is tolerated (count ≥ 1) |
| 10 | a heal ability **tagged `Ability.Heal`**, granted, activatable by that tag | fully | HO-6 heal half, cp4 — `no activatable ability tagged Ability.Heal on the pawn (health operations not implemented` (segment seam at cpp:322–323; continues `as activatable abilities). granted=`) then `an ability tagged Ability.Heal was granted but did NOT activate on TryActivateAbilitiesByTag` | cp0 gates; damage rows 9/11 fire first (damage is checked before heal) | same tolerances as row 9 |
| 11 | **each damage activation lands its full effect** — re-activation ~0.7 s later must not be refused (not still-running, not on cooldown) | fully | HO-6c, cp4 — `an ability tagged Ability.Damage refused a later activation: ` | cp0 gates; rows 9 (granted/first activation) first | nothing on the refusal axis; whether the accepted activation actually MOVED Health is rows 13/16's job |
| 12 | the damage ability **lowers** Health | fully | HO-7, cp4 — `the damage operation did not lower Health: Health went ` | cp0 gates; rows 9–11 | a drop of just >0.5 (DirectionEpsilon) clears this gate but then dies at HO-8's 5-floor |
| 13 | the heal ability **raises** Health | fully, transitively | HO-10, cp4 — `heal does not restore what damage removes: one damage removed ` (a zero or negative healDelta reads symRatio ≤ 0, far outside 0.90–1.10; the same FinishTest literal row 14 gates on) | cp0 gates; rows 9–12, 15–16 (HO-8 at cpp:352 and HO-9 at cpp:378 both precede HO-10 at cpp:392) and the ratio guard first | nothing — but the FAIL is attributed to symmetry, not direction; there is no dedicated "heal did not raise Health" literal |
| 14 | **one heal restores exactly as much Health as one damage removes** (the symmetry clause) | fully, as a ±10% band | HO-10, cp4 — `heal does not restore what damage removes: one damage removed ` (symRatio = healDelta/drop1 gated to 1.00 ± 0.10 (SymTol) over congruent 0.7 s windows; one gate, one literal, serving both this row and row 13) | cp0 gates; rows 9–12, 15–16 and the ratio guard first — identical to row 13, since rows 13/14 are the same FinishTest | "exactly" is graded as ±10% of drop1; restore-to-full dies here by name (symRatio ~6.00, the PIN section-4 plausible-wrong solve), and the heal's absolute magnitude is bounded only through this ratio (see row 15) |
| 15 | each application changes Health by a **fixed amount between 5 and 25** | fully for damage | HO-8, cp4 — `the per-application Health change is outside the stated ` (5–25 band, first damage application) | cp0 gates; rows 9–12 | the HEAL magnitude is never checked against the band directly — only via HO-10's ±10% of drop1, so heal ∈ [4.5, 27.5] at the band edges; a 27-point heal against a 25-point damage passes |
| 16 | "the same amount every time it is applied" — **damage** | fully | HO-9, cp4 — `the damage operation is not a fixed amount: the first application removed ` (drop2/drop1 within 1.00 ± 0.10 over two congruent 0.7 s windows) | cp0 gates; rows 9–12, 15, and the named ratio-denominator guard (`the repeatability and symmetry ratios have no usable denominator` — unreachable while HO-7/HO-8 precede it) | ±10% wobble between the two applications |
| 17 | "the same amount every time it is applied" — **heal** | **NOT ASSERTED** | — (the fixture activates `Ability.Heal` exactly ONCE, at cp2; there is no second heal window, so heal repeatability is never observed) | — | a heal whose magnitude varies per activation (random, ramping, first-cast-bonus) passes, provided its single observed application lands within ±10% of drop1 |
| 18 | **neither ability may change Health except when activated** (no passive drift) | fully, one window | HO-11, cp4 — `Health kept moving with no operation active: ` (\|idleDelta\| ≤ 0.5 over (cp3, cp4], where nothing is triggered) | cp0 gates; rows 9–16 — in particular a drift big enough to skew the heal window dies at HO-10 FIRST (measured 2026-08-10: `regen/` symRatio 1.33; see "HO-11 IS NOT REACHABLE" above) | drift active only OUTSIDE (cp3, cp4] and small enough not to tip HO-9/HO-10 (≤ ~0.48 Health per 0.7 s window at M=10) is invisible; pre-cp0 drift is caught but misattributed to HO-3 (row 5) |
| 19 | Blueprint assets, if authored, saved under `/Game/Tasks/gp-health-attribute-ops-cpp/` — "the only content path the verifier looks in" | partially, by resolver omission | not a gate — the resolver's asset-registry scan is filtered to `/Game/Tasks` (recursive); a BP pawn saved anywhere else is never a candidate, so resolution falls back and HO-1 (row 3) reports the generic scaffold pawn | unconditional (resolution precedes every gate) | the filter is `/Game/Tasks` at ROOT granularity, recursive — a BP pawn saved under ANY `/Game/Tasks/<other-folder>/` still resolves and grades; the task-id subfolder named by the prompt is enforced by nothing (the sandbox's `asset_writable` accepts all of `Content/Tasks/` too) |

Constants cited above are the fixture-header pins (`HealthAttributeOpsFunctionalTest.h`):
`HealthInitExpected=100`, `BaselineEpsilon=0.5`, `WriteProbeValue=37`,
`PresetHealth=60`, `MagnitudeMin/Max=5/25`, `DirectionEpsilon=0.5`,
`IdleEpsilon=0.5`, `RepeatTol=0.10`, `SymTol=0.10` — all still stamped
`PROPOSED - NOT YET MEASURED` pending the notes.md calibration record, though
the 2026-08-10 sweep's reference population (ratios 1.00, congruent 0.700 s
windows) has retired them in practice.

### Holes this table found (escalation list, checklist §7 doctrine)

- **(H1) Heal repeatability is unobserved** (row 17). The prompt's "the same
  amount every time it is applied" binds BOTH abilities; the fixture triggers
  the heal once, so only the damage half is gated (HO-9). Closing it needs a
  second heal window — a fixture/PIN edit (the schedule is PIN-normative), not
  a variant.
- **(H2) The mannequin clause is enforced by nothing** (row 8). HO-5
  deliberately asserts only "a visible mesh exists" (base-class comment: asset
  path, mesh type, size unchecked). A cube passes. Either the prompt's
  "assign one of the provided mannequin skeletal meshes" bullet should soften
  to "a visible mesh", or HO-5 needs an asset-path check — an owner/PIN call.
- **(H3) The content-path constraint is enforced at `/Game/Tasks` root
  granularity only** (row 19). A BP deliverable under another task's
  `/Game/Tasks/` subfolder resolves and grades normally; the prompt's "that is
  the only content path the verifier looks in" is true, but the task-id folder
  it names is not what the resolver keys on.
- **(H4) Two documented misattribution traps, restated for completeness**: a
  BeginPlay/Tick drift FAILs at HO-3 under an init-to-100 message (row 5 /
  Known holes (d) above), and a passive drift big enough to skew the heal
  window FAILs at HO-10 under a symmetry message while HO-11 stays unreported
  (row 18 / "HO-11 IS NOT REACHABLE" above). Both are true FAILs with
  misleading names — soundness holds, attribution does not.
