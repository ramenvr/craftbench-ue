# gp-dot-aoe-burn-cpp -- discrimination matrix

> ## STATUS: **MEASURED 2026-08-11 — `cb discriminate` = YES, 4/4 legs.**
>
> Reference **PASS**; `empty`, `never-stops`, `global-burn` each **FAIL
> credited at its named substring**. Run was `substrate=live` (the package was
> uncommitted at sweep time — `decide_from_live` flips to `HEAD` once it is
> committed; re-run then for the certified verdict). Every row below is a
> MEASUREMENT; nothing here is a prediction.
>
> **The first sweep returned `discriminated: NO`, and it was right twice
> over** — the value of the named-substring rule in one line:
> `empty` came back `FAIL(wrong-reason)`, which exposed (a) a FIXTURE defect —
> AB-7 wrapped `PawnVisiblyRepresented`'s already-complete sentence in another
> `Printf`, so the FAIL string read the sentence twice; every sibling fixture
> passes `VisWhy` through verbatim and this one did not — and (b) a wrong
> PREDICTION in this file: the row claimed `empty` dies at AB-1 (no tagged
> ability) when it dies at AB-7 at checkpoint 0, before the trigger, exactly
> as every sibling family's empty leg does. A matrix that checked exit codes
> alone would have called that leg green.

> ## MATRIX LAYOUT LAW (read before editing this file)
>
> `aura_rig.discriminate.parse_matrix` keys rows by their **FIRST CELL** and
> **LAST ROW WINS across every markdown table in the file**. A later table
> repeating a leg name silently re-registers it -- with an empty substring
> tuple if that table has no message column -- and `cb discriminate` then
> credits the leg on its exit code alone. That has happened twice in this repo.
>
> **There is exactly ONE markdown table in this file: the `## Matrix` table.**
> Everything else is a bullet list on purpose. Do not add a second table, and
> do not put a leg name or any string containing a `/` in a first column
> anywhere else.

---

## Why this package is five legs and not seven

First family authored under the **minimal-leg policy**
(`docs/TASK-AUTHOR-GUIDE.md` §7 second amendment, owner vote
2026-08-11). Legs earn their place one of three ways: the automatic floor, the
one measured-false-PASS axis, or one attacker per hand-calibrated bar.

- `reference` + `empty` -- automatic, cost nothing.
- `never-stops/` -- attacks **AB-5**, a hand-calibrated bar (`StopEpsilon`).
- `global-burn/` -- attacks **AB-4**, this family's novel axis and its other
  hand-calibrated bar (`StepEpsilon` as a "did not move" floor).
- **Deliberately NOT authored:** a `no-mesh` leg (family-standard re-proof --
  the visibility gate is proven at family level by 9/9 recorded glide reps
  shipping meshless pawns) and a `cpp-solve`-style deliverable-format leg
  (this is the `-cpp` half; that axis belongs to the `-bp` twin, where it is
  the one measured false PASS).

Both attackers are the reference **with one deletion**, so an L2 failure is
attributable to the deleted line and nothing else.

## Matrix

Each "Expected message" cell carries exactly one backticked literal, quoted
from `AoeBurnFunctionalTest.cpp`.

| Submission | Overall | Fails at | Expected message | Status |
| `../reference` | **PASS** | -- | all gates green | **MEASURED PASS 2026-08-11** (`meanRate=6.10 total=30.00 stopDrop=0.00 farMaxDev=0.00`, control drop 20.00) |
| empty (no overlay -> generic scaffold pawn) | **FAIL** | L2 cp0, AB-7 visibility | `no mesh component with an assigned mesh on the graded pawn` | **MEASURED 2026-08-11.** This row originally predicted AB-1 (no tagged ability) and was WRONG: AB-7 runs at checkpoint 0, BEFORE the trigger, and the generic scaffold pawn ships no assigned mesh -- so the run never reaches the tag gate. Identical to every sibling family's empty leg, whose rows say the same thing; the prediction ignored that precedent. The sweep's `wrong-reason` credit is what caught it |
| `never-stops/` | **FAIL** | L2 final, AB-5 | `the burn never expired` | one deletion: the duration check. Rate/spatial/step behaviour identical to the reference, so AB-5 is the first gate it can trip |
| one-shot/ | **FAIL** | L2 final, AB-2 (the step gate) | `the burn was not periodic` | one coherent delta: the periodic schedule is replaced by a SINGLE whole-run-total application (5.0 x 6 = 30.0) at activation, then the ability ends. The spatial test and the post-hit silence are reference-identical, so AB-1 goes green, D2=D3=0.00 trips AB-2 first, and meanRate ~7.32 / total 30.00 sit inside their bands -- no later gate can be credited instead. AUTHORED + **MEASURED 2026-08-16 (same day)**: credited [ok] at this substring in both the run-2b sweep and the post-fix re-discriminate; authored to close the test-brief row-2 instrument gap (no one-shot leg existed) |
| `global-burn/` | **FAIL** | L2 final, AB-4 | `the burn is not an AREA effect` | one deletion: the distance test. The near target's burn, rate, total and stop are IDENTICAL to the reference -- this leg exists because every other gate goes green |

## Calibration record (measured, not predicted)

- **Reference, 2026-08-11:** `N0=95 N1=90 N2=85 N3=75 NStop=70 NTail=70`,
  `D1=5.00 D2=5.00 D3=10.00`, `meanRate=6.10`, `total=30.00`,
  `stopDrop=0.00`, `farMaxDev=0.00`, control `100 -> 80`. Overall **PASS**.
- **`aids/calibration/conforming-fast/` (12 per tick, NOT a discrimination
  leg):** `D1=12.00 D2=12.00 D3=24.00`, `meanRate=14.63`, `total=72.00`,
  `farMaxDev=0.00`. Overall **PASS**.

That second solve is kept OUTSIDE `discrimination/` on purpose:
`discriminate.py` hard-codes every discovered variant to `expect_pass=False`
(line 385), so a leg that must PASS cannot live there -- it would be graded as
a failed expectation and break the sweep. It is graded standalone whenever a
bar moves.

## The three defects this family's validation found

The first two were not reachable by any wrong solve: both needed a solve that
**conforms at a different point in the disclosed space**, which is precisely
what an attacker-only leg set cannot provide. The third needed the sweep. None
of the three was reachable by reading the design -- which is now 10 of 10 on
this slate.

1. **Per-window banding was unsound.** AB-3 originally banded each 1.5 s
   window at the disclosed 3-15. The reference measured `D2=5.00` and
   `D3=10.00` -- equal durations, unequal tick counts, purely from phase
   against a 1.0 s period. A conforming 12-per-tick solve would have read
   `D3=24` against a 15 top and FAILed **under a message claiming its rate was
   out of a band it was inside**. Fixed: AB-3 is now a mean over the fixed
   4.1 s in-band span, enforced 2.0-20.0 -- deliberately WIDER than the
   disclosed 3-15, because enforcing looser can only miss a bad solve while
   enforcing tighter manufactures false FAILs.
2. **The disclosed bands contradicted each other.** With AB-3 fixed, the same
   conforming solve still FAILed at `total=72.00` against a 60.0 top -- and it
   was right: rate up to 15 for a duration up to 7 s is **105**, not 60. The
   prompt was asking for something it then punished. Fixed: the total top is
   now DERIVED (3x4 = 12 floor, 15x7 = 105 ceiling) and the prompt states the
   consistent number.
3. **The visibility FAIL string said itself twice, and this file predicted the
   wrong gate for `empty`.** Found by the first sweep's `wrong-reason` credit
   (see the STATUS banner). Both fixed; the second sweep credited 4/4.

## Re-validate

```sh
cb discriminate --task gp-dot-aoe-burn-cpp
python tools/verify-single/run_task.py \
  --task tasks/bp-g2/gp-dot-aoe-burn-cpp/task.md \
  --submission tasks/bp-g2/gp-dot-aoe-burn-cpp/aids/calibration/conforming-fast \
  --ue-root <UE-root> --workdir C:\cb\wd\<fresh>     # must PASS
```

## Parser self-check

Parsed with `aura_rig.discriminate.parse_matrix` before commit: **4 rows** --
`reference` (`expect_pass=True`, empty substring tuple), `empty`,
`never-stops`, `global-burn` (each `expect_pass=False`, exactly one
substring). No row blank, none shadowed. Re-run that check after any edit.

# DRAFT ONLY — nothing in this scratch file is committed. To be APPENDED to tasks/cpp/gp-dot-aoe-burn-cpp/discrimination/MATRIX.md.
# markdown table in this file" — amend that sentence when appending (the door-hitch
# precedent already ships a second, non-parseable requirements table; the law's real
# invariant is no leg name and no `/` in a first column, which this table satisfies:
# every first cell is a bare integer, and no column is named "substring" or "message").

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked FAIL-message span is a contiguous `FinishTest(EFunctionalTestResult::Failed, ...)`
source literal, and every backticked gate-condition span quotes the fixture's if-condition verbatim —
AB-1..AB-6 from `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-dot-aoe-burn/AoeBurnFunctionalTest.cpp`,
AB-7 from the base class `UE-projects/ThirdPerson/Source/CraftBenchTests/CraftBenchPawnFunctionalTest.cpp`
(`PawnVisiblyRepresented`'s `OutWhy`, passed to `FinishTest` verbatim). Gate order is the fixture's
early-return order at cp5 (AB-0 → AB-1 → AB-2 → AB-3 → AB-4 → AB-5 → AB-6), with AB-7 the only
agent gate at checkpoint 0 — but NOT first there: cp0 runs the `[HARNESS]` target-spawn check, the
presets, and the `[HARNESS]` control-drain-build check before AB-7 reaches evaluation, and the run can
FinishTest even earlier, in PrepareTest, via the fixture's `[HARNESS] no world in PrepareTest` or the
base class's spawn preconditions — `SpawnAndPossessPawn: no world` and `spawn of %s failed`
(composed: the latter is the source-side `FString::Printf` format fragment; both are harness
preconditions yet carry NO `[HARNESS]` prefix). The four `[HARNESS]`-prefixed strings (AB-0 control
lane, target-spawn, control-drain-build, no-world) are machine-fault verdicts, never agent gates —
no row below claims one as an enforcing gate.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | an ability tagged `Ability.AoeBurn` is added to the character's granted abilities | fully | AB-1 (granted arm, `NumGrantedAbilitiesWithTag(FCraftBenchGameplayTags::AbilityAoeBurn()) < 1`) — `no activatable ability tagged Ability.AoeBurn on the pawn` | AB-7 failed at cp0, or any earlier harness-precondition FinishTest ended the run (a `[HARNESS]` verdict — AB-0 / target-spawn / control-drain-build / no-world — or a base-class `SpawnAndPossessPawn` failure) | HOW it is granted is free — constructor default, BeginPlay, a `GrantedAbilities` entry on a pawn subclass, all indistinguishable |
| 2 | the ability is activatable by the game through the character's ability system (activation not refused) | fully | AB-1 (activation arm, `BurnActivations < BurnTriggerAttempts` after the fixture's single tag-trigger at cp0) — same literal, tail `or its activation was refused` | as row 1 | costs, cooldowns, instancing policy, activation side effects — none read; one accepted activation is the whole contract |
| 3 | a burning area appears at the character's location | partially (bracketed, not measured) | no placement gate exists — placement is bracketed by AB-2 (the near target 300 uu from the pawn's spawn MUST burn: `the burn was not periodic`) and AB-4 (the far target at 1500 uu MUST NOT: `the burn is not an AREA effect`) | rows 1-2 | an area centered meters off the character — any shape/origin that still covers 300 uu and misses 1500 uu; an aura that FOLLOWS the caster is also indistinguishable (the graded pawn never moves in this fixture) |
| 4 | a character inside the area loses Health repeatedly — about once per second | fully at window granularity | AB-2 — `the burn was not periodic: the character inside the area did not keep` + `losing Health in steps` (one literal, re-quoted either side of its C++ concatenation seam; D2 and D3, two equal 1.37 s windows, must each drop > StepEpsilon 0.5; D1 is EVIDENCE ONLY since the 2026-08-15 FALSE_FAIL repair) | AB-0/AB-1 fired first | any period <= ~1.37 s reads as "about once per second" — a 10 Hz or per-tick drain passes; a first-window (trigger -> +1.37 s) dead zone is invisible, D1 is printed but never gated |
| 5 | the repeated losses come in steps of roughly equal size | **NOT ASSERTED** | none — AB-2 is a pure direction-plus-noise-floor predicate; the per-window magnitude band was deliberately REMOVED 2026-08-11 (measured unsound: equal-duration windows hold unequal tick counts) | n/a | wildly unequal steps (e.g. 0.6 / 0.6 / 60 across the three windows) pass, provided each gated window moves > 0.5 and the mean-rate (2-20) and total (12-105) backstops hold |
| 6 | characters outside the area are not affected at all | fully, at EVERY checkpoint (worst deviation tracked cp0-cp5, so a burn-then-restore cannot hide) | AB-4 — `the burn is not an AREA effect: a character well outside the area` | rows 1-4 (AB-0..AB-3 early-return first) | up to StepEpsilon 0.5 Health of perturbation on the far target; anything at all to characters between 300 and 1500 uu — the 700 uu edge target is sampled and printed but EVIDENCE ONLY by design |
| 7 | the area reaches about five meters from where it appeared | partially (3x latitude both ways, by design) | same bracket as row 3: inside asserted at 300 uu (AB-2), outside at 1500 uu (AB-4) — deliberate, so no reasonable reading of "about" decides a verdict | rows 1-4 | any effective radius in the open (300, 1500) uu interval — from 3x under to 3x over a literal 5 m |
| 8 | the area lasts a set duration then stops; four-to-seven seconds accepted | top fully; **floor only indirect** | AB-5 — `the burn never expired: the character inside the area was still losing` (NStop - NTail must be <= StopEpsilon 0.25 over the (trigger+7.1, trigger+9.2] window; 0.25 < StepEpsilon per the T1.2 law, so a permanent burn cannot pass) | rows 1-6 plus row 9 (AB-0..AB-4 early-return first) | a duration UNDER the disclosed 4 s floor: ~2.8-3.7 s survives (one tick inside the D3 window trigger+2.74..+4.1 satisfies AB-2, and total >= 12 is easy at in-band rates); "set" is also unread — any mechanism quiet after trigger+7.1 s passes, deterministic or not |
| 9 | each character inside loses between three and fifteen Health per second or so | partially — ENFORCED WIDER on purpose | AB-3 — `the burn rate is outside the stated band` (MEAN over the fixed 4.1 s in-band span, enforced 2.0-20.0 against the disclosed 3-15; the documented F5 asymmetry — enforcing tighter manufactures false FAILs from tick phase) | rows 1-5 (AB-0..AB-2 first) | mean rates in 2-3 or 15-20 pass despite sitting outside the disclosed band; rate need not be constant — only the 4.1 s mean is read |
| 10 | one activation totals between twelve and about a hundred Health | fully | AB-6 — `the total burn is outside the stated band` (12.0-105.0; the top DERIVED as 15 x 7 after the conforming-fast calibration solve false-FAILed a 60.0 top) | rows 1-8 (every other gate early-returns first) | nothing beyond the band's own disclosed width |
| 11 | Health is the attribute on the provided attribute set | fully, by measurement channel | not a named gate — the fixture reads ONLY `UCraftBenchAttributeSet::GetHealthAttribute()` through the verifier-owned targets' ASCs, so a burn landed on any other attribute (or a parallel bookkeeping float) reads as NO burn and dies at AB-2's `the burn was not periodic` | rows 1-2 | the WRITE mechanism is free: GameplayEffect, `SetNumericAttributeBase`, or any other route that moves the contract attribute grades identically (behavior-only by design) |
| 12 | the character is visibly represented | fully, at checkpoint 0 BEFORE the trigger | AB-7 — `no mesh component with an assigned mesh on the graded pawn` (base-class `PawnVisiblyRepresented`, passed through verbatim; sibling literals in the same function catch a mesh that is assigned but hidden-in-game or scaled to ~zero) | first agent-attributable gate, but not unconditional: the `[HARNESS]` target-spawn check AND the `[HARNESS]` control-drain-build check both run before it at cp0, and the base class's un-prefixed `SpawnAndPossessPawn: no world` / `spawn of %s failed` (composed) FinishTests preempt it from PrepareTest | see row 13 — the gate proves SOMETHING renders, not WHAT |
| 13 | the assigned mesh is one of the provided mannequin skeletal meshes (under `/Game/Characters/`) | **NOT ASSERTED** | none — AB-7 accepts ANY visible, real-scale `UMeshComponent` with ANY assigned asset, static or skeletal; no gate reads the asset's identity or path | n/a | a cube static mesh, an engine placeholder, any renderable asset whatsoever — the mannequin clause and the `/Game/Characters/` path are prompt-only |

### Residuals this table surfaces (escalation candidates, not silently accepted)

- **Row 5 is a documented deliberate deletion**, not an oversight: per-window
  magnitude banding was measured unsound 2026-08-11 (fixture header + MATRIX
  defect log). If "roughly equal steps" is to stay in the prompt unasserted, it
  belongs in an *Accepted residuals* block like the door-hitch exemplar's;
  otherwise soften the prompt wording.
- **Row 8's duration floor**: the disclosed "four-to-seven" band's 4 s floor is
  enforced only as ~2.75 s (a tick inside the D3 window) — a ~3 s burn passes.
- **Row 13** is the family's real identity hole: the visible-character gate is
  family-proven, but nothing anywhere binds the mesh to the named mannequins.
- **task.md's Verifier-specification block has drifted from the shipped
  fixture**: it still shows the pre-2026-08-15 schedule (1.6/3.1 vs the shipped
  1.87/3.24) and describes AB-2 as gating D1, which is now evidence-only.
