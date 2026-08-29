> ## MEASURED 2026-08-10 - full matrix green, and it found TWO gate defects
>
> `reference` **PASS**; all 9 negative legs **FAIL at L2 by a named assertion**;
> every L1 green. Reference population:
>
> ```
> legOneRises=1 legOneRiseZ=184 maxVZlegOne=600 vZatTrigger=-425
> debited=20.00 furtherDrop=0.00 legTwoRises=1 legTwoRiseZ=20
> legOneSegments: [FALL 1200->1108 | RISE 1108->1292 +184 | FALL 1292->730]
> ```
>
> **This is I1.4's first execution anywhere.** The decomposition above is the
> proof it works: a fall, one real second jump, a fall. `slowed-fall/` FAILs at
> DJ-2c ("Z fell to 1072 and never climbed back") - the shape the old
> whole-series `RoseThenFell` could not express.
>
> **DEFECT 1 - DJ-4 false-FAILed the CONFORMING reference.** The reference
> refuses correctly (it gates on `CurrentPower < PowerCost` before both the debit
> and the impulse; `lastPowerLegTwo=5.0`, nothing debited). But the series
> carried a **+20 blip mid-fall at -716 cm/s**, and `LegTwoRises >= 1` charged it
> to the ability. No ABSOLUTE bar can fix this: it must be small enough to see a
> modest jump, which is small enough to catch jitter on a fast fall. DJ-4 is now
> a RATIO against the same run's own jump, `max(0.50 * legOneRiseZ, RiseEpsilon)`
> - the blip is 11% of the 184 jump and correctly ignored.
>
> **DEFECT 2 - `teleport/` PASSED THE WHOLE TASK.** The variant authored to prove
> AG-2 proved instead that AG-2 was undefended. DJ-2b's premise - "a teleport
> leaves vZ at whatever gravity produced" - is measurably FALSE for
> `SetActorLocation`: it recorded **maxVZ=+194**, so the impulse gate passed, and
> the rise gate passed too because it did rise, by being moved. Closed by
> DJ-2b2, BALLISTIC CONSISTENCY: a rise produced by velocity v cannot exceed
> v^2/2g.
>
> | | v | v^2/2g | measured rise | ratio |
> |---|---|---|---|---|
> | reference | 600 | 184 | 184 | **1.00** |
> | `teleport/` | 194 | 19 | 293 | **15.4** |
>
> Bar at 3.0x sits between two MEASURED populations (3x margin conforming, 5x
> gaming) and is RELATIVE, so it adds no magnitude the prompt would have to
> disclose and cannot become an F5-shaped undisclosed literal.
>
> **Both defects were found by RUNNING a variant, not by reading the design.**
> Both gates looked correct in the pin sheet, in review, and in the fixture's own
> comments.
>
> **ISOLATION CAVEAT** - `empty` and `no-mesh/` share DJ-7's named FAIL: an empty
> submission resolves to a meshless pawn and trips the first gate incidentally.
> Declared, not hidden; `no-mesh/` proves the gate fires on an otherwise-complete
> pawn but does not isolate beyond `empty`.

# gp-double-jump-stamina -- discrimination matrix

> **STATUS: EVERY ROW IN THIS FILE IS `**MEASURED 2026-08-10** (L2 FAIL by name)`.** Nothing in
> this package has been compiled, launched in PIE, or graded. No `run_task.py`,
> no `cb`, no UBT, no editor, no test suite. Every verdict, every message and
> every number below is a PREDICTION derived from four sources that were read on
> disk:
> (1) the fixture,
> `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-double-jump-stamina/DoubleJumpStaminaFunctionalTest.{h,cpp}`;
> (2) the I1.4 sampler it consumes,
> `UE-projects/ThirdPerson/Source/CraftBenchTests/CraftBenchPawnFunctionalTest.{h,cpp}`
> (`Segments` / `NumRises` / `MeanVerticalRate` / `DescribeSegments`);
> (3) the committed reference, `../reference/Source/ThirdPerson/`; and
> (4) the substrate's own `ACraftBenchCharacter` / `UCraftBenchAttributeSet`.
> **Do not cite any row here as measured discrimination.** The commands that
> promote these rows from PREDICTED to MEASURED are in **Re-validate**, at the
> bottom -- and they are BLOCKED, see **Blocking dependency**.
>
> This is also why every constant introduced by a variant carries a
> `PROPOSED - NOT YET MEASURED` comment in its own source file. PIN.md's status
> line says "nothing built. Every number below is PROPOSED - NOT YET MEASURED",
> and PIN.md section 6 owes measured jitter populations for `RiseEpsilon`,
> `PowerEpsilon`, `MinFallSpeed` and `CostTol` before this family reaches G2.

> **THE ONE SUBSTRING RULE THIS FILE OBEYS.** Every fragment recorded in a "named
> substring" cell is a LITERAL RUN of one of the fixture's
> `FinishTest(EFunctionalTestResult::Failed, ...)` format strings -- it never
> spans a `%`-placeholder, because a substring that spans one can never match at
> runtime (`granted=0` is unmatchable; `granted=` is). All eight fragments were
> machine-extracted from the fixture source with
> `tools/verify-single/matrix_oracle.py`'s own `cpp_literal_tiers` +
> `literal_runs` before this file was written, so each is quoted from the
> verifier rather than paraphrased. Numbers a reader might want are stated in the
> LAST column, deliberately OUTSIDE the substring cell: a condensed human summary
> inside a substring cell would be un-matchable.

> **I1.4 HAS NEVER EXECUTED, AND TWO OF THESE ROWS ARE ITS FIRST TEST.** PIN.md
> D1 says to treat the whole sampler as untested code, and the owner decision of
> 2026-08-10 made `DescribeSegments()` a mandatory diagnostic for exactly that
> reason. `slowed-fall/` and `fires-when-broke/` both stand or fall on the
> SEGMENT DECOMPOSITION, not on a raw reading. On the first sweep, read
> `legOneSegments=` and `fullSegments=` on the second `[DOUBLEJUMP-FINAL]` line
> BEFORE believing either verdict.

---

## What this package is

Eight one-delta C++ overlays, shaped exactly like
`gp-poison-dot-stack-cpp/discrimination/` and `gp-heal-over-time-cpp/discrimination/`:
each variant directory is a FULL copy of `../reference/Source/ThirdPerson/` (all
four files) with **exactly one file pair changed**, and within that pair
**exactly one axis broken**, so a FAIL is attributable. `diff -rq` against the
reference was run for every variant and is reproduced in **Delta audit**, below.

PIN.md section 3 declares **eight** anti-gaming notes, one of which (AG-7) is
re-recorded as ARGUED by the owner decision of 2026-08-10. There is one variant
per REACHABLE note, plus one extra row where a single note names two separable
defects:

- **AG-2 gets two rows.** The note covers both "teleport upward instead of
  applying an impulse" and "nudge Z once and let it keep falling", and those die
  at DIFFERENT gates (DJ-2b and DJ-2c respectively). `teleport/` and
  `slowed-fall/` are the two halves; between them they prove DJ-2b and DJ-2c are
  not redundant.
- **AG-4 gets two rows** for the same reason its own text names two defects: no
  debit at all (`free-jump/`, DJ-3a) and a debit of the wrong size
  (`wrong-cost/`, DJ-3b).
- **AG-7 gets NO row, on purpose.** DJ-6 ("only one extra jump per airborne
  period") is CUT by the owner decision of 2026-08-10, so there is no gate to
  aim a variant at. Authoring one would be authoring a leg that grades against
  nothing. See **AG-7 is ARGUED**, below.

---

## Predicted reference timeline (the control -- also NOT YET RUN)

Trigger offsets are from the Leg-1 trigger at `t = 0.7`. Spawn at `z = 1200`,
world gravity the UE default `-980 cm/s^2`, `GravityScale` 1.0, runner at
`-deterministic -FPS=60`, dense sampling ON (one sample per tick).

| leg | t (s) | offset | Z (cm) | vZ (cm/s) | Power | note |
|---|---|---|---|---|---|---|
| 1 | 0.4 | -0.3 | ~1122 | ~-392 | 100 | DJ-7 (mannequin) at checkpoint 0 |
| 1 | 0.7 | trigger | ~960 | **~-686** | 100 -> **60** | DJ-2a baseline read FIRST, then preset + trigger |
| 1 | 0.72 | +0.02 | ~970 | **~+584** | 60 | first dense sample after the impulse -- DJ-2b |
| 1 | 1.0 | +0.3 | ~1103 | ~+306 | **40.0** | DJ-3a / DJ-3b "to" sample, DJ-3c window OPEN |
| 1 | 1.31 | +0.61 | **~1144** | ~0 | 40.0 | apex of the second jump: **+183.7 cm** climbed |
| 1 | 1.9 | +1.2 | ~975 | ~-578 | **40.0** | DJ-3c window CLOSE -- flat, further drop 0.00 |
| 2 | 2.4 | trigger | ~564 | ~-1076 | 40 -> **5** | Leg-1 reductions captured FIRST, then preset + re-trigger |
| 2 | 2.7 / 3.0 / 3.3 | -- | on the floor | -- | **5.0** | refused: no rise, Power never negative |

Predicted `granted=1 legOneActivated=1/1 legTwoActivated=0/1`,
`maxVZlegOne=+584 legOneRises=1 legOneRiseZ=184 legTwoRises=0`,
`debited=20.00 furtherDrop=0.00 minPowerLegTwo=5.0`. All eight final gates plus
DJ-7 green. **PREDICTED - NOT YET MEASURED.** The trajectory numbers are the
reference author's hand-trace (`DoubleJumpAbility.h`, the ARITHMETIC block),
reproduced here independently and agreeing.

**The one place this trace is soft:** the reference lands at about `t = 2.8`, so
the Leg-2 re-trigger at `t = 2.4` happens with the character still airborne but
close to the floor. Nothing in Leg 2's gate depends on that (a refusal produces
no rise from either state), but if the map's floor sits higher than assumed the
`[DJ-REFUSE-DIAG]` line is where it will show first.

---

## Matrix

Every row: ****MEASURED 2026-08-10** (L2 FAIL by name).**

| Submission | Overall | Fails at | Named substring it must FAIL on | Predicted numbers (NOT part of the recorded literal) |
|---|---|---|---|---|
| `../reference` | **PASS** (predicted) | -- | -- | see the timeline above |
| empty (no overlay -> scaffold pawn) | **FAIL** | cp0, DJ-7 | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | no `[DOUBLEJUMP-FINAL]` line is emitted at all. **Shares its substring with `no-mesh/` -- see ISOLATION CAVEAT 1** |
| `no-mesh/` (AG-8) | **FAIL** | cp0, DJ-7 | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | behaviourally the reference; no FINAL line, because the fixture finishes at checkpoint 0 |
| `no-gas/` (AG-1) | **FAIL** | last cp, DJ-1 | `no activatable ability tagged Ability.DoubleJump on the pawn (the second jump is not an activatable ability). granted=` | `granted=0 legOneActivated=0/1` NEXT TO a real rise and a real `60.0 -> 40.0` debit -- the numbers show a working double jump and the verdict names the missing contract |
| `teleport/` (AG-2, first half) | **FAIL** | last cp, **DJ-2c** (the v^2/2g ballistic-consistency gate) | `the second jump was not produced by an upward impulse: the character rose ` | **RE-MEASURED 2026-08-18** (single-leg grade, workdir kept): `maxVZlegOne=194` — POSITIVE — `legOneRiseZ=293`, so `v^2/2g = 19` and the rise outruns its own velocity 15.4x. DJ-2b (`MaxVZLegOne > 0`) therefore PASSES and the leg is caught by DJ-2c instead. **This row previously claimed DJ-2b with `maxVZlegOne` "deeply negative (about -690)", which was stale, not wrong-at-the-time:** the DJ-2c gate was added in `3895b2c` (2026-08-10) whose own calibration comment already records this variant at `v=194 -> 19, rose 293, ratio 15.4`, and the row was never updated (`5bb3221` only moved the file). Not attributable to the 2026-08-18 possession change. The task is *better* defended than the old row implied — a physics-consistency gate beats a sign check, and the fixture says so: "the variant authored to prove AG-2 proved instead that AG-2 was undefended" |
| `slowed-fall/` (AG-3 + AG-2 second half; **the I1.4 row**) | **FAIL** | last cp, DJ-2c | `the character did not rise a second time: Z fell to ` | `maxVZlegOne=+19` (**DJ-2b PASSES on purpose**), `legOneRises=0 legOneRisesRaw=0 legOneRiseZ=0`, climb 4.08 cm against `riseEpsilon=20`, `debited=20.00` |
| `free-jump/` (AG-4, first half) | **FAIL** | last cp, DJ-3a | `the second jump cost no Power: Power went ` | `plus03=60.0 plus12=60.0 debited=0.00` -- **exactly** zero, not merely small -- next to a normal jump (`maxVZlegOne=+584 legOneRiseZ=184`) |
| `wrong-cost/` (AG-4, second half) | **FAIL** | last cp, DJ-3b | `the second jump did not cost 20 Power: Power went 60.0 -> ` | `plus03=25.0 debited=35.00 furtherDrop=0.00` -- a perfectly one-shot debit of the wrong size; DJ-3a passes at 70x its floor |
| `continuous-drain/` (AG-5) | **FAIL** | last cp, DJ-3c | `the Power cost is a continuous drain, not a one-shot debit: Power kept falling after the activation (` | `debited=20.45` (DJ-3b PASSES with 0.55 of its 1.0 tolerance to spare), `furtherDrop=1.35` against `powerEpsilon=0.50` |
| `fires-when-broke/` (AG-6) | **FAIL** | last cp, DJ-4 | `the ability fired without paying for it: with only 5.0 Power (below the 20 cost) the character still rose a second time (Z climbed ` | Leg 1 identical to the reference (all seven earlier gates pass); `legTwoRises=1 legTwoRiseZ=184 minPowerLegTwo=-15.0`. The `[DJ-REFUSE-DIAG]` line must show the **HARD-GATED** branch |

---

## AG-7 is ARGUED, and no variant is authored for it

PIN.md section 3 note 7 ("unlimited air jumps while Power lasts") was written as
"only if DJ-6 is kept". **DJ-6 is CUT** (OWNER DECISION 2026-08-10): gating "only
one extra jump per airborne period" would enforce a limit the source row never
states, and buying it with an added prompt sentence is the F5 trade in miniature.
The owner block re-records AG-7 as an ARGUED note pointing at DJ-2c.

So there is no DJ-6 gate, no DJ-6 constant and no DJ-6 counter anywhere in the
fixture, and **a variant aimed at AG-7 would be a leg that grades against
nothing** -- it would trip whichever gate its collateral damage reached and be
credited under another row's name. Recording the note as ARGUED is the honest
outcome; padding the matrix with a ninth directory would not be.

What DJ-2c actually buys against AG-7, stated so the ARGUED claim is checkable:
a submission that allows unlimited air jumps still has to produce a real
segmented rise on Leg 1, and still has to refuse below the cost on Leg 2. What it
is NOT checked for is a THIRD activation inside one airborne period, which the
fixture never attempts. **That is a real, uncovered axis, and it is uncovered by
decision rather than by oversight.**

---

## ISOLATION CAVEAT 1 -- `empty` and the meshless overlay share one named FAIL

DJ-7 is the FIRST gate this fixture runs (checkpoint 0), and it is a single
`FinishTest(Failed, ...)` with no placeholders, so one log line satisfies both
greps. **The two rows do not isolate at the substring level.** Declared, not
hidden.

The mechanism, verified on disk at authoring time: with no overlay
`ResolveAgentPawnClass` (`CraftBenchPawnFunctionalTest.cpp:68-140`) finds no
concrete native `ACraftBenchCharacter` subclass in the ThirdPerson substrate
(`ACraftBenchBareCharacter` is `UCLASS(Abstract)` and `ACraftBenchCharacter`
itself is excluded from the candidate list) and no Blueprint subclass under
`/Game/Tasks`, so it returns `ACraftBenchCharacter::StaticClass()` -- whose
constructor (`CraftBenchCharacter.cpp`) never assigns a mesh. The empty leg
therefore trips the visibility gate INCIDENTALLY, on the way past everything else
it is also missing.

**It is not a duplicate.** The meshless overlay is a submission that is correct
on every other axis -- it grants the tagged ability, gates the cost, debits
exactly 20 once, and reverses the descent -- whose only fault is invisibility. It
is the only leg that proves DJ-7 discriminates on the visibility axis alone. The
two are separated by the RUN, not by the string.

`matrix_oracle.is_isolation_leg` already EXCLUDES the smoke leg from the pairwise
entailment matrix for exactly this shape, and records the reason: an empty
submission has no authored defect to attribute and trips whichever gate the
schedule reaches first. Same collision, same structural cause and the same
declaration as `gp-glide-stamina-cpp`'s and `gp-health-attribute-ops-cpp`'s
matrices. Note the CONTRAST with `gp-heal-over-time-cpp`, where the meshless row
IS cleanly isolated: that fixture runs an attribute-initialisation gate before
its visibility gate, so the scaffold pawn dies earlier. This family has no
checkpoint-0 gate before DJ-7, so the collision is structural here.

**No other pair in this package collides.** The remaining seven substrings are
pairwise distinct and none is contained in another, so no leg's log can be
satisfied by another leg's failure.

---

## The two rows that carry the I1.4 claim

`slowed-fall/` and `teleport/` are deliberately aimed at the two halves of "a
real second jump", and the pair is the argument that DJ-2b and DJ-2c are both
load-bearing. Read this table before touching either variant's constants.

| | motion-by-teleport | motion-by-slowed-fall |
|---|---|---|
| what the ability does | Z moves +300 in one frame; velocity untouched | vZ set to a token +20, then `GravityScale` 0.05 |
| max vZ after the trigger | about `-690` (negative) | `+19.2`, positive for ~24 frames |
| segmented rise in Leg 1 | **1** (the teleport step is 15x `RiseEpsilon`) | **0** (climb 4.08 cm, 4.9x UNDER the floor) |
| gate DJ-2b (`maxVZ > 0`) | **FAIL** | PASS |
| gate DJ-2c (segmented rise) | would have PASSED | **FAIL** |
| what the row proves | velocity is not derivable from position | a rise is not derivable from velocity |

**Why the slowed-fall row cannot be a PURE slowed fall.** PIN.md AG-3 says a
descent that is merely slowed keeps `vZ` negative throughout and is therefore
caught by DJ-2b. That is true -- and it means a pure slowed fall would die at
DJ-2b, on `teleport/`'s substring, isolating nothing beyond it. DJ-2b runs
BEFORE DJ-2c, so the only way to author a row that actually tests DJ-2c is a
submission that CLEARS DJ-2b: a token upward flick that arrests the descent
without carrying the character anywhere, which is precisely the shape DJ-2c's own
message names ("A one-shot upward velocity that is immediately cancelled, or a
slowed fall, looks like this"). The variant's header states this in full.

**Why this row is also a calibration probe, and the hazard that comes with it.**
The only thing separating `slowed-fall/` from a CONFORMING but gentle second jump
is the magnitude of the climb: 4.08 cm against a `RiseEpsilon` of 20 cm. That
bar is `PROPOSED - NOT YET MEASURED`, and the fixture's own header calls a
too-high `RiseEpsilon` "the unforgivable direction" because it fails a conforming
gentle jump for not jumping. So this row supplies the VIOLATING population
(4.08 cm) against the reference's CONFORMING one (183.7 cm), and a green on it
is **not** evidence that `RiseEpsilon` is pinned -- only that those two numbers
sit on opposite sides of whatever 20 cm turns out to be. PIN.md section 6 owes
the measured populations either way.

**What the old reductions would have said, which is the whole reason I1.4
exists.** `RoseThenFell` is first-sample -> global-peak -> last-sample: one bool
for the entire series, decided by where sampling happened to start. On this
submission the series opens at the SPAWN (`z = 1200`), so the peak IS the first
sample; start the series a few frames later and the same 4 cm flick becomes the
global peak and the same trajectory reads "rose then fell". Same code, opposite
verdict, decided by a sampling boundary. `ApexDeltaZ` cannot separate "did not
rise" from "rose 4 cm" from "rose 184 cm" without a magnitude bar, and the prompt
fixes no jump height. Only a segmented decomposition answers "did Z climb back,
after bottoming out, by more than the noise floor" without asking how high.

---

## Delta audit (`diff -rq ../reference/Source/ThirdPerson <overlay>/Source/ThirdPerson`)

Run at authoring time (2026-08-10); reproduce it before trusting any row.

> NOTE ON LAYOUT: the overlay name is deliberately NOT column 1 in this table, or
> in any other table in this file except **Matrix**. `parse_matrix` keys rows by
> their FIRST CELL and **LAST ROW WINS**, so a later table repeating a leg label
> silently BLANKS that leg's recorded substring -- the exact defect the substring
> oracle caught on `gp-poison-dot-stack-bp` and again on `gp-heal-over-time-cpp`.

| Files that differ from the reference | Overlay | Axis broken |
|---|---|---|
| `DoubleJumpPawn.{h,cpp}` | no-gas | ability not granted; the second jump moved into the pawn's own `Tick` |
| `DoubleJumpAbility.{h,cpp}` | teleport | `Velocity.Z = 600` replaced by `SetActorLocation(+300 Z)` |
| `DoubleJumpAbility.{h,cpp}` | slowed-fall | `Velocity.Z = 600` replaced by `Velocity.Z = 20` + `GravityScale = 0.05` |
| `DoubleJumpAbility.cpp` | free-jump | the one-shot debit removed; the refusal gate KEPT |
| `DoubleJumpAbility.h` | wrong-cost | `PowerCost` 20.0f -> 35.0f |
| `DoubleJumpAbility.{h,cpp}` | continuous-drain | the one-shot debit KEPT, plus a never-cleared 1.5 Power/s upkeep timer |
| `DoubleJumpAbility.cpp` | fires-when-broke | the refusal gate removed and the debit's `FMath::Max(0.0f, ...)` floor with it |
| `DoubleJumpPawn.cpp` | no-mesh | the mannequin `FObjectFinder` and its placement removed |

No overlay adds or removes a file: each directory carries the reference's four
files. Nothing outside `Source/ThirdPerson/` is added -- a `NOTES.md` at a
submission root would be a sandbox exit-4 reject (`AGENT_WRITABLE.json`), so every
variant's documentation lives in its own source headers, which is also where a
reviewer diffing the overlay will actually see it. All 32 files are byte-checked
pure ASCII with LF line endings.

---

## Per-note coverage (PIN.md section 3)

| Anti-gaming note | Committed overlay | Gate | Status |
|---|---|---|---|
| **AG-1** second jump in the movement component / on input, nothing activatable by tag | no-gas | DJ-1 | **MEASURED 2026-08-10** (L2 FAIL by name) |
| **AG-2** teleport upward instead of applying an impulse | teleport | DJ-2b | **MEASURED 2026-08-10** (L2 FAIL by name) |
| **AG-2** (second half) nudge Z once and keep falling | slowed-fall | DJ-2c | **MEASURED 2026-08-10** (L2 FAIL by name) |
| **AG-3** reuse the glide answer: slow the descent instead of reversing it | slowed-fall | DJ-2c | **MEASURED 2026-08-10** (L2 FAIL by name); see the caveat below |
| **AG-4** a free double jump, no debit | free-jump | DJ-3a | **MEASURED 2026-08-10** (L2 FAIL by name) |
| **AG-4** (second half) a cosmetic debit of the wrong size | wrong-cost | DJ-3b | **MEASURED 2026-08-10** (L2 FAIL by name) |
| **AG-5** the cost charged as a per-tick drain while airborne | continuous-drain | DJ-3c | **MEASURED 2026-08-10** (L2 FAIL by name) |
| **AG-6** debit Power but never gate on it; the resource goes negative | fires-when-broke | DJ-4 | **MEASURED 2026-08-10** (L2 FAIL by name) |
| **AG-7** unlimited air jumps while Power lasts | **none -- ARGUED** | none (DJ-6 CUT) | no gate exists; see **AG-7 is ARGUED** |
| **AG-8** a meshless pawn, conforming but invisible | no-mesh | DJ-7 | **MEASURED 2026-08-10** (L2 FAIL by name); shares its substring with `empty` (CAVEAT 1) |

**The AG-3 caveat, stated rather than buried.** PIN.md routes AG-3 to DJ-2b ("vZ
stays negative throughout"), and the committed overlay routes it to DJ-2c
instead, because a submission that keeps vZ negative throughout is
indistinguishable at the substring level from the teleport row. The two readings
disagree about WHICH GATE defends AG-3, and this package cannot settle that
without a fixture change. What it can say is that both gates are exercised, by
two rows, with a stated margin each. **Escalated with this change-set rather than
resolved here.**

---

## The fixture's named FAIL substrings, and which note each defends

Enumerated from every `FinishTest(EFunctionalTestResult::Failed, ...)` in
`DoubleJumpStaminaFunctionalTest.cpp`, machine-extracted (not transcribed) with
`matrix_oracle.cpp_literal_tiers`. Each recorded fragment below is the first
literal run of its message, so none spans a `%`-placeholder.

| # | Named substring (a literal run -- no `%` spanned) | Fires at | Defends |
|---|---|---|---|
| 1 | `pawn did not spawn/resolve` | any checkpoint | **no note** -- harness / resolution condition |
| 2 | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | cp0, DJ-7 | AG-8 (and `empty`, incidentally) |
| 3 | `no activatable ability tagged Ability.DoubleJump on the pawn (the second jump is not an activatable ability). granted=` | last cp, DJ-1 | AG-1 |
| 4 | `an ability tagged Ability.DoubleJump was granted but did NOT activate on TryActivateAbilitiesByTag` | last cp, DJ-1 | AG-1, second half -- **NO COMMITTED OVERLAY**, see holes |
| 5 | `no falling baseline: the character was not descending when the ability was triggered (vZ=` | last cp, DJ-2a | **no note** -- harness sanity (PIN.md marks its anti-gaming column "--") |
| 6 | `the ability produced no upward impulse: the highest vertical velocity after the trigger was ` | last cp, DJ-2b | AG-2 first half |
| 7 | `the character did not rise a second time: Z fell to ` | last cp, DJ-2c | AG-2 second half, AG-3 |
| 8 | `the second jump cost no Power: Power went ` | last cp, DJ-3a | AG-4 first half |
| 9 | `the second jump did not cost 20 Power: Power went 60.0 -> ` | last cp, DJ-3b | AG-4 second half |
| 10 | `the Power cost is a continuous drain, not a one-shot debit: Power kept falling after the activation (` | last cp, DJ-3c | AG-5 |
| 11 | `the ability fired without paying for it: with only 5.0 Power (below the 20 cost) the character still rose a second time (Z climbed ` | last cp, DJ-4 | AG-6 |

Eight of the eleven are reached by a committed overlay. The three that are not
are recorded below rather than silently filled.

---

## Known holes (named gates with NO corresponding overlay)

- **(a) Substring 4 -- granted-but-never-activates.** The second half of AG-1's
  stated defense has no overlay. One is authorable (an ability whose
  `CanActivateAbility` refuses, or one carrying a blocking tag), but AG-1 already
  has `no-gas/` and the hole is recorded instead of padded. Same shape and the
  same decision as hole (a) in `gp-heal-over-time-cpp`'s matrix and hole (c) in
  `gp-glide-stamina-cpp`'s.
- **(b) Substring 5 -- DJ-2a, the falling baseline.** No overlay, and none should
  be authored: DJ-2a is HARNESS SANITY, not an anti-gaming gate. It fires when
  the spawn height or the map floor is wrong, i.e. when the box is wrong rather
  than the submission. A variant aimed at it would be testing the fixture's
  schedule, not a gaming mode.
- **(c) DJ-4's "Power went negative" half is only reachable together with its
  "rose again" half.** `fires-when-broke/` trips BOTH halves of the disjunction
  at once (`legTwoRises=1` AND `minPowerLegTwo=-15.0`), so no committed row
  proves the negative-Power half fires ON ITS OWN. A variant that refuses to jump
  below the cost but still debits (Power to `-15`, no Leg-2 rise) would isolate
  it, and is not authored here. Recorded, not padded.
- **(d) No overlay tests `RiseEpsilon` from just BELOW the conforming side.**
  `slowed-fall/` attacks DJ-2c with 4.08 cm against a 20 cm floor -- a 4.9x
  margin. Nothing sits at, say, 18 cm. Nor can it be authored honestly until
  `RiseEpsilon` is MEASURED: a variant tuned against an unmeasured bar tests the
  guess, not the gate. Same reasoning, same wording, as hole (c) in
  `gp-heal-over-time-cpp`'s matrix.

---

## Substrate dependency

- The **I1.4 sampler** (`SetDenseSampling`, `Segments`, `NumRises`,
  `MeanVerticalRate`, `DescribeSegments` on `CraftBenchPawnFunctionalTest`).
  **It has never executed.** `slowed-fall/` and `fires-when-broke/` have no
  meaning without a correct decomposition; `teleport/` does not depend on it.
- The **ability-aware pawn resolver** (`PreferredAbilityTag()`,
  `CraftBenchPawnFunctionalTest.cpp`). The fixture returns
  `FCraftBenchGameplayTags::AbilityDoubleJump()`, so seven of the eight overlays
  are resolved by the tag they grant and cannot be displaced by another committed
  `ACraftBenchCharacter` subclass.
- **`no-gas/` is the exception and is the row to re-check first if anything in
  the substrate changes.** It grants nothing, so the tag preference finds no
  match and the resolver falls back to `Candidates[0]` -- the first CONCRETE
  NATIVE `ACraftBenchCharacter` subclass. Verified on disk at authoring time: the
  ThirdPerson substrate ships exactly one other subclass,
  `ACraftBenchBareCharacter`, and it is `UCLASS(Abstract)`, so `ADoubleJumpPawn`
  is still the graded pawn and DJ-7 still passes on it. **If a future task commits
  another concrete native subclass into `Source/ThirdPerson/`, enumeration order
  decides the fallback and this row can start failing under a different name.**
- The **`Ability.DoubleJump` native tag** in
  `Source/ThirdPerson/CraftBenchGameplayTags.{h,cpp}` (PIN.md D5). Added with
  this family; every overlay except `no-gas/` depends on it.
- **`UCraftBenchAttributeSet` does no clamping** (its header: "no clamping, no
  GameplayEffect execution logic at v1.0"). `fires-when-broke/` depends on that
  directly -- if a clamp is ever added to `Power`, its predicted `-15.0` becomes
  `0.0` and only the Leg-2-rise half of DJ-4 would fire.

---

## Blocking dependency before any of this can be run

**There is no `task.md` for this family yet.**
`tasks/bp-g2/gp-double-jump-stamina/` currently holds `PIN.md`, `reference/` and
this `discrimination/` package. `run_task.py` takes `--task <path to task.md>`,
so **every command below will fail with a spec error (exit 2) until the spec is
authored.** Note also that PIN.md's title gives the family's final ids as
`gp-double-jump-stamina-{cpp,bp}` while the folder on disk is
`gp-double-jump-stamina`; if the folder is renamed to `gp-double-jump-stamina-cpp`
(the 2026-08-06 `-cpp` convention `gp-glide-stamina` and `gp-poison-dot-stack`
already went through), **update every path below in the same change**.

The fixture is also not yet reachable from a spec: nothing declares
`ADoubleJumpStaminaFunctionalTest` in a `fixtures:` list, and no committed
`.umap` for this task exists under `Content/Maps/`. Both are prerequisites of the
first run, and neither is in this package's ownership.

---

## Re-validate (the commands that promote every row above from UNVALIDATED to MEASURED)

Run on a box with UE 5.8 and **no other session holding the engine**:
`Build.bat`'s mutex is keyed on the ENGINE INSTALL, not the project, so a
contended build returns exit 1 with no compile errors and would be misread as an
overlay failing L1. Check `CRAFTBENCH_L1_MAX_PARALLEL` is SET before starting --
an unset cap makes L1 die with `C3859`/`C1076` deterministically on every task,
and no preflight probe catches it.

```sh
$env:CB_UE_ROOT='<UE-root>'
$T='tasks/bp-g2/gp-double-jump-stamina/task.md'
$D='tasks/bp-g2/gp-double-jump-stamina/discrimination'

# The reference must PASS in the same sweep -- it is the control. A sweep in
# which the reference FAILs measures the box, not the overlays.
python tools/verify-single/run_task.py --task $T `
    --submission tasks/bp-g2/gp-double-jump-stamina/reference --substrate-from-live --ue-root $env:CB_UE_ROOT

python tools/verify-single/run_task.py --task $T --submission $D/no-gas --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task $T --submission $D/teleport --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task $T --submission $D/slowed-fall --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task $T --submission $D/free-jump --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task $T --submission $D/wrong-cost --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task $T --submission $D/continuous-drain --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task $T --submission $D/fires-when-broke --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task $T --submission $D/no-mesh --substrate-from-live --ue-root $env:CB_UE_ROOT
```

The equivalent single command once the spec exists and the box is free:

```sh
cb discriminate gp-double-jump-stamina
```

**An overlay that FAILs at a substring other than its own is a MIS-AUTHORED
OVERLAY, not a discrimination win.** Read the two `[DOUBLEJUMP-FINAL]` lines
before touching the fixture -- line 1 carries every sample and every computed
value, line 2 carries the segment decomposition plus the nine REALIZED checkpoint
gaps, which is where a tick-placement disagreement with the derivations in this
package will show up first.

### What to record when the sweep is run

Replace this section with the results, and capture -- per PIN.md section 6, which
this package does NOT discharge -- the numbers the family still owes:

1. **Both populations for `RiseEpsilon`**: the reference's measured
   `legOneRiseZ` (predicted 184 cm) against `slowed-fall/`'s (predicted 4.08 cm),
   with the margin on each side. This is the bar whose too-high direction
   false-FAILs a conforming gentle jump, so the conforming population must come
   from more than the reference alone.
2. **Both populations for `PowerEpsilon`**: the reference's `furtherDrop`
   (predicted 0.00, and structurally so -- the debit lands before the window
   opens) against `continuous-drain/`'s (predicted 1.35), and `free-jump/`'s
   `debited=0.00` against the reference's 20.00 for the DJ-3a direction.
3. **Both populations for `CostTol`**: the reference's `debited` (predicted
   20.00) and `continuous-drain/`'s (predicted 20.45, which must stay INSIDE the
   tolerance) against `wrong-cost/`'s 35.00.
4. **`MinFallSpeed`**: the measured `vZatTrigger` on the reference (predicted
   about -686) against the 100 cm/s floor. This is harness sanity, so the number
   to watch is the MARGIN to the map's floor, not the bar.
5. **The I1.4 decomposition itself**, which nothing else in the repo owes: the
   reference's `legOneSegments=` string, read against `legOneRisesRaw` and
   `risesAll`. The fixture logs both so the segmenter has an independent
   cross-check on its first-ever execution; a divergence with no pre-trigger rise
   in the printed decomposition means the segmenter is not doing what the fixture
   assumes, and every DJ-2c and DJ-4 verdict in this package is then suspect.

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span in the Enforcing-gate column's FAIL MESSAGES is a contiguous literal run of ONE `FinishTest(EFunctionalTestResult::Failed, ...)` format string in
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-double-jump-stamina/DoubleJumpStaminaFunctionalTest.cpp`
(DJ-7's message is emitted by that fixture but authored in the shared base,
`UE-projects/ThirdPerson/Source/CraftBenchTests/CraftBenchPawnFunctionalTest.cpp::PawnVisiblyRepresented`); none spans a `%`-placeholder. Backticks OUTSIDE those FAIL messages — identifiers and code expressions (row 1's resolver names, row 8's `Segments(RiseEpsilon)`/`EndT > TriggerTime`), the prompt-only `/Game/Characters/` (row 3), row 7's `LaunchCharacter(bZOverride=false)` shorthand (the source comment at cpp:531 reads `LaunchCharacter((0,0,600), bZOverride=false)`), the `[DJ-REFUSE-DIAG]` UE_LOG tag (cpp:467, row 14), and the hypothetical example `Power < 6` — are NOT FinishTest literals and carry no verbatim-grep claim.
NOTE: the fixture is AHEAD of task.md's gate table — DJ-2b2 (ballistic consistency), DJ-2d (came back down) and DJ-4b (charged without delivering) were added by the 2026-08-10/11 owner fixes and appear below but not in the spec's table. Layers are `[L1, L2]` (no L2I), so L1 (both UBT targets build) is the only gate before every row and is not repeated per-row. Skip-cell convention: the pre-gate pawn-resolve failure (row 1) and a DJ-7 FAIL at cp0 (row 2) finish the fixture before ANY final gate runs, so they preempt every row 4–15 gate even where a skip cell enumerates only "rows 4–N fired first"; likewise any earlier final gate firing first skips all later ones, in SOURCE order.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | "Deliver your pawn as a subclass of the provided character (C++ or Blueprint)" | fully, by the resolution model | not a `FinishTest` literal — `ResolveAgentPawnClass` grades only `ACraftBenchCharacter` subclasses, preferring the candidate granting an `Ability.DoubleJump`-tagged ability (`PreferredAbilityTag()`); a non-subclass deliverable is never resolved, and the meshless scaffold fallback then dies at row 2's gate | unconditional (resolution runs before everything; total resolution failure is the pre-gate `pawn did not spawn/resolve`, checked at every checkpoint) | the C++-vs-Blueprint choice is free; committing extra `ACraftBenchCharacter` subclasses is free — the tag-granting one wins resolution |
| 2 | "The character must be **visibly represented**" — a mesh assigned, so a reviewer can see it jump | fully | DJ-7, cp0 (first gate) — `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` (hidden / scaled-to-zero variants share the prefix `the character is not visibly represented: the pawn has `) | pawn did not resolve (pre-gate fires instead) | any assigned, rendering mesh at component scale > 0.01 — the gate is visibility-level only (see row 3) |
| 3 | "assign one of the **provided mannequin skeletal meshes** (under `/Game/Characters/`) as your character's mesh" | **NOT ASSERTED** (asset identity) | none — `PawnVisiblyRepresented` deliberately asserts neither asset path, nor mesh type, nor size (stated in its own header comment); no gate reads the mesh's package path or class | — | a static cube, an engine sphere, or any mesh from anywhere satisfies row 2; the mannequin bullet is enforced only down to "some visible mesh". Deliberate in the base class, but the prompt names a specific asset family and nothing checks it |
| 4 | "Tag the ability `Ability.DoubleJump` and add it to the pawn's granted abilities" | fully | DJ-1a, cp9 (first of the final gates) — `no activatable ability tagged Ability.DoubleJump on the pawn (the second jump is not an activatable ability). granted=` | DJ-7 failed at cp0 (fixture finishes; no final gate runs) | the tag must be readable as an ASSET tag (`NumGrantedAbilitiesWithTag` and `TryActivateAbilitiesByTag` both read asset tags); granting additional unrelated abilities is free |
| 5 | "so the game can **trigger** the second jump by that tag" — the Leg-1 activation must actually land | fully (Leg 1 only, per-leg counter) | DJ-1b, cp9 — `an ability tagged Ability.DoubleJump was granted but did NOT activate on TryActivateAbilitiesByTag` | rows 2/4 fired first | the Leg-2 activation counter is deliberately ungated — a refused re-activation there is the conforming answer (and a cooldown blocking Leg 2 is accepted leniently, PIN.md D3) |
| 6 | "second jump while it is **already falling** through the air" — the mid-fall premise | asserted as HARNESS SANITY (fixture-owned drop from z=1200; `MinFallSpeed` 100 cm/s) | DJ-2a, cp9, input read live at cp1 BEFORE preset+trigger — `no falling baseline: the character was not descending when the ability was triggered (vZ=` | rows 4–5 fired first | nothing useful — this gate guards the fixture's own drop; a FAIL here indicts the map/schedule (or an agent BeginPlay auto-jump that leaves the pawn rising at t=0.7), not the ability's logic |
| 7 | "the character's descent must **reverse**" — vZ goes positive after the trigger | fully | DJ-2b, cp9, over the Leg-1 window (0.7, ~2.38] — `the ability produced no upward impulse: the highest vertical velocity after the trigger was ` | rows 4–6 fired first | pure direction, no magnitude: a +1 cm/s flick passes THIS gate (row 8 then demands travel); the additive `LaunchCharacter(bZOverride=false)` plausible-wrong solve dies here |
| 8 | "**carry it upward again**" — real travel, "not a slowed fall" (and not a cancelled one-shot velocity) | fully | DJ-2c, cp9 — `the character did not rise a second time: Z fell to ` (gate input: Leg-1-filtered `Segments(RiseEpsilon)` rises, `EndT > TriggerTime`) | rows 4–7 fired first, or row 9's DJ-2b2 fired first — the fixture evaluates DJ-2b2 BEFORE DJ-2c (cpp:568 vs cpp:588); this table keeps the spec's gate order, which inverts the source order for these two rows | a gentle rise just over `RiseEpsilon` = 20 cm (deliberate — the prompt fixes no jump height; bar carries `PROPOSED - NOT YET MEASURED`) |
| 9 | "**not a teleport**" | fully | DJ-2b2 (owner fix 2026-08-10; `teleport/` had PASSED the whole task) — `the second jump was not produced by an upward impulse: the character rose ` (ballistic consistency: rise ≤ 3.0 × v²/2g of the measured max vZ) | rows 4–7 fired first (a vZ-negative teleport dies at row 7's DJ-2b); DJ-2b2 itself runs BEFORE row 8's DJ-2c in the fixture, so DJ-2c never preempts it | a rise up to 3.0× its own v²/2g; a teleport that ALSO writes a ballistically consistent upward velocity is indistinguishable from an impulse by construction |
| 10 | "a real upward impulse **it then falls back down from**" | fully | DJ-2d (fixture audit 2026-08-11) — `the character rose a second time but never came back down: Z climbed ` (a falling segment of ≥ `RiseEpsilon` starting at/after the rise's end) | rows 4–9 fired first (in source order DJ-2d follows DJ-2c, which follows DJ-2b2; a DJ-2c FAIL means no rise to fall from) | any post-apex fall of ≥ 20 cm satisfies it — cancelling gravity AFTER falling 20 cm passes; fall speed/completeness unconstrained |
| 11 | "Activating it **costs Power**" — a real debit happened | fully | DJ-3a, cp9, preset(60) → trigger+0.3 — `the second jump cost no Power: Power went ` | rows 4–10 fired first | a debit ≤ `PowerEpsilon` 0.5 reads as free (noise floor); reads are post-aggregator CURRENT values, so duration/infinite-GE cost shapes are accepted (by design, the V1.4 law) |
| 12 | "costs **20** Power" — the disclosed magnitude | fully (the one absolute; lawful — the prompt says "costs 20 Power") | DJ-3b, cp9 — `the second jump did not cost 20 Power: Power went 60.0 -> ` | rows 4–11 fired first | ±`CostTol` 1.0 around 20; the debit is only sampled at trigger+0.3, so a debit landing later than 0.3 s reads as free/wrong-size (lenient direction: it FAILs, never falsely passes) |
| 13 | "debited **once** per activation. It must **not drain Power continuously** while airborne" | fully, in-window | DJ-3c, cp9, window (trigger+0.3, trigger+1.2] — `the Power cost is a continuous drain, not a one-shot debit: Power kept falling after the activation (` | rows 4–12 fired first | a drain that completes before trigger+0.3 or starts after trigger+1.2 is invisible; a slow leak ≤ 0.5 total across the 0.9 s window passes; Power REGEN in the window is invisible (only a further DROP is gated) |
| 14 | "If the character has **less than 20 Power**, the ability must **not fire**: no second jump" | conditionally (SKIP-vs-FAIL, deliberate) | DJ-4 rise half, cp9, Leg 2 preset(5) — `the ability fired without paying for it: with only 5.0 Power (below the 20 cost) the character still rose a second time (Z climbed ` (ratio bar: rise ≥ max(0.50 × legOneRiseZ, RiseEpsilon)) | rows 4–13 fired first, or Leg 1 never rose (`bLegOneRose` false) — DJ-4 is SKIPPED, not failed, announced on the `[DJ-REFUSE-DIAG]` line; PIN.md D3 forbids "simplifying" this | the refusal is probed ONLY at Power=5, so a wrong threshold anywhere in (5, 20] — e.g. `Power < 6` — refuses at 5 and passes; a Leg-2 rise under half the run's own Leg-1 jump is ignored (the 2026-08-10 ratio fix, which un-false-FAILed the reference); a cooldown blocking Leg 2 passes (accepted lenient) |
| 15 | "and **Power must not go negative**" (nor be spent at all when refusing) | conditionally (same skip) | DJ-4 negative half — `and/or Power went negative (` (`MinPowerLegTwoShown < -PowerEpsilon`, min-tracked over cp7–cp9, sentinel-seeded at the preset); the clamp escape is closed by DJ-4b — `the ability charged without delivering: with only ` (any Leg-2 spend > `PowerEpsilon` 0.5 below the cost) | rows 4–13 fired first, or Leg 1 never rose (both halves skipped, as row 14); DJ-4b (cpp:747) is additionally preempted when row 14's disjunction (cpp:706) fires first | negative/spent Power is probed only on the below-cost leg — Leg-1 Power sign is never checked (irrelevant at preset 60, cost 20); a refusal-path spend ≤ 0.5 passes; Power between the cp7/cp8/cp9 samples is unobserved |

Residual gate-affecting observations (escalated, not papered over): row 3 is the one true hole; rows 13–15's last-column windows are point/interval probe limits inherent to the two-leg schedule, recorded so nobody reads the AG list as covering them. AG-7 (unlimited air jumps) remains ARGUED with no gate — DJ-6 was CUT by owner decision 2026-08-10 and the fixture never attempts a third activation; that gap is by decision, already declared in this file's coverage table, and is a prompt-level non-requirement rather than a table row (the prompt as written never states a one-per-airborne-period limit).
