> ## MEASURED 2026-08-10 - full matrix green (Windows / UE 5.8)
>
> `reference` **PASS**; all 11 negative legs **FAIL at L2, each by a named
> assertion**; every L1 green (no wrong-reason FAILs). Reference population,
> which retires the `PROPOSED` tags:
>
> ```
> A1=45.0 A2=50.0 A3=60.0 AStop=65.0 ATail=65.0 total=25.00
> riseStep1=5.00 riseStep2=10.00 stopRise=0.00 activated=3/3
> L2cur=100.0 L2base=100.0   L3cur=100.0 L3base=100.0
> w2=1.500 w3=1.500          <- the congruent rise pair, MEASURED
> ```
>
> **The owner `StopEpsilon` edit (0.7 -> 0.25) is PROVEN LOAD-BEARING.**
> `never-stops-in-band/` measures **`stopRise = 0.60`**. That FAILs against 0.25
> - and would have **PASSED** against the pin sheet's original 0.7. A
> never-ending regeneration would have shipped through HOT-3 into a family
> authored specifically to avoid inheriting poison's Leg-A defect.
>
> **HOT-5's dual read is PROVEN NOT DECORATION.** `current-only-clamp/` measures
> `L2cur=100.0 L2base=120.0`: the current value reads exactly the cap while the
> base runs 20 over. A current-only gate passes that submission, and its health
> system then silently absorbs the next 20 damage. This is the variant V1.4
> exists for.
>
> **ISOLATION CAVEAT - `empty` and `no-maxhealth/` share HOT-0's named FAIL**
> (`MaxHealth was not initialized: read 0.0`). Declared, not hidden: an empty
> submission resolves to a pawn with no initialized attribute set, so it trips
> the first gate incidentally - the same structural reason `empty` collides with
> `no-mesh` on `gp-health-attribute-ops-cpp`. `no-maxhealth/` still earns its
> place (it proves the gate fires on a pawn that is otherwise complete), but it
> does not isolate an axis beyond what `empty` already proves.

# gp-heal-over-time -- discrimination matrix

> **STATUS: EVERY ROW IN THIS FILE IS `**MEASURED 2026-08-10** (L2 FAIL by name)`.** Nothing in
> this package has been compiled, launched in PIE, or graded. No `run_task.py`,
> no `cb`, no UBT, no editor. Every verdict, every message and every number
> below is a PREDICTION derived from three sources that were read on disk:
> (1) the fixture,
> `UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-heal-over-time/HealOverTimeFunctionalTest.{h,cpp}`;
> (2) the committed reference, `../reference/Source/ThirdPerson/`; and
> (3) UE 5.8 engine source under `<UE-root>`. **Do not cite any row here as
> measured discrimination.** The commands that promote these rows from
> PREDICTED to MEASURED are in **Re-validate**, at the bottom.
>
> This is also the reason every constant introduced by a variant carries a
> `PROPOSED - NOT YET MEASURED` comment in its own source file: bars in this
> repo are pinned by MEASURING, and PIN.md's own status line says "nothing
> built. Every number below is PROPOSED - NOT YET MEASURED".

> **The one substring rule this file obeys.** Every fragment recorded in a
> "named substring" cell is a LITERAL RUN of one of the fixture's
> `FinishTest(EFunctionalTestResult::Failed, ...)` format strings -- it never
> spans a `%`-placeholder, because a substring that spans one can never match at
> runtime. All twelve fragments below were machine-checked against the
> fixture's reconstructed (adjacent-literal-concatenated) format strings before
> this file was written. Numbers that a reader might want are therefore stated
> OUTSIDE the substring cells: a condensed human summary in a substring cell
> would be un-matchable.

---

## What this package is

Ten one-delta C++ overlays, shaped exactly like
`gp-poison-dot-stack-cpp/discrimination/`: each variant directory is a FULL
copy of `../reference/Source/ThirdPerson/` (all eight files) with **exactly one
file pair changed**, and within that pair **exactly one axis broken**, so a FAIL
is attributable. `diff -rq` against the reference was run for every variant and
is reproduced in **Delta audit**, below.

PIN.md section 3 declares **seven** anti-gaming notes. There is one variant per
note, plus three extra rows that close named gates the seven would otherwise
leave uncovered:

- `never-stops-in-band/` -- the only shape that would have passed the WHOLE task
  at the sheet's original `StopEpsilon = 0.7`. It is the row that proves the
  owner EDIT of 2026-08-10 was load-bearing; `never-stops/` alone does not (see
  **The owner EDIT**, below).
- `current-only-clamp/` -- the PIN section 4 "plausible-WRONG solve", the row
  that proves HOT-5's dual read is not decoration.
- `lowers-at-max/` -- HOT-6 would otherwise have zero committed coverage.

---

## Predicted reference timeline (the control -- also NOT YET RUN)

Trigger offsets are from the Leg 1 trigger at `t = 0.5`. The reference effect is
`HasDuration 5.0s / Period 1.0s / +5.0 per period /
bExecutePeriodicEffectOnApplication = false`, so it executes five times, at
trigger+1 through trigger+5, for a per-application total of 25.

| leg | t (s) | offset | Health | note |
|---|---|---|---|---|
| 1 | 0.5 | trigger | 100 -> 40 | HOT-0 (MaxHealth 100.0), HOT-7 (mannequin), preset, trigger |
| 1 | 1.6 | +1.1 | **45.0** | A1, 1 execution |
| 1 | 3.1 | +2.6 | **50.0** | A2, closes rise window 1 |
| 1 | 4.6 | +4.1 | **60.0** | A3, closes rise window 2 (congruent) |
| 1 | 7.6 | +7.1 | **65.0** | AStop, stop window opens past the 4-7s band top |
| 1 | 9.7 | +9.2 | **65.0** | ATail, stop window closes |
| 2 | 10.7 | trigger | 95 | preset, trigger |
| 2 | 15.8 | +5.1 | **current 100.0 / base 100.0** | the dual read (HOT-5) |
| 3 | 17.0 | trigger | 100 | preset, trigger |
| 3 | 22.1 | +5.1 | **100.0** | HOT-6 |

Predicted `granted=1 activated=3/3`, `riseStep1=5.00 riseStep2=10.00
stopRise=0.00 total=25.00`. All nine gates green. **PREDICTED - NOT YET
MEASURED** (this trace is the fixture author's hand-trace, independently
recomputed here against the committed reference and agreeing digit for digit).

---

## Matrix

Every row: ****MEASURED 2026-08-10** (L2 FAIL by name).**

| Submission | Overall | Fails at | Named substring it must FAIL on | Predicted numbers (NOT in the substring) |
|---|---|---|---|---|
| `../reference` | **PASS** (predicted) | -- | -- | see the timeline above |
| empty (no overlay -> scaffold pawn) | **FAIL** | cp0, HOT-0 | `MaxHealth was not initialized: read ` | reads `0.0`; no `[HEALOVERTIME-FINAL]` line is emitted. **Shares its substring with `no-maxhealth/` -- see ISOLATION CAVEAT 1** |
| `no-maxhealth/` (AG-1) | **FAIL** | cp0, HOT-0 | `MaxHealth was not initialized: read ` | reads `0.0` while Health reads `100.0`; no FINAL line |
| `no-mesh/` (AG-7) | **FAIL** | cp0, HOT-7 | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | HOT-0 passes first at `100.0`; no FINAL line. Cleanly isolated -- see the note under CAVEAT 1 |
| `no-gas/` (AG-2) | **FAIL** | last cp, HOT-1 | `no activatable ability tagged Ability.HealOverTime on the pawn (the restore is not an activatable ability). granted=` | `granted=0 activated=0/3`, with the Tick-driven restore raising Health on schedule -- the numbers show a working restore and the verdict names the missing contract |
| `instant/` (AG-3) | **FAIL** | last cp, HOT-2 | `the restore was not periodic: Health did not keep rising in steps (A1=` | `A1=A2=A3=AStop=ATail=65.0`, `riseStep1=0.00 riseStep2=0.00`, `total=25.00` (in band, so HOT-4 cannot take the credit) |
| `never-stops/` (AG-4) | **FAIL** | last cp, HOT-3 | `the restore did not STOP after its duration: Health was still rising in the post-band stop window (AStop=` | `A1=40.0 A2=40.6 A3=41.2 AStop=42.4 ATail=43.0`, `riseStep1=0.60 riseStep2=0.60 stopRise=0.60 total=3.00`. **Shares its substring with `never-stops-in-band/` -- see ISOLATION CAVEAT 2** |
| `never-stops-in-band/` (AG-4, the load-bearing row) | **FAIL** | last cp, HOT-3 | `the restore did not STOP after its duration: Health was still rising in the post-band stop window (AStop=` | `A1=45.0 A2=50.6 A3=61.2 AStop=67.4 ATail=68.0`, `riseStep1=5.60 riseStep2=10.60 stopRise=0.60 total=28.00`, `L2cur=100.0 L2base=100.0 L3cur=100.0`. **Every other gate PASSES** |
| `out-of-band/` (AG-6) | **FAIL** | last cp, HOT-4 | `the total restored is outside the stated 10-40 band: Health went 40.0 -> ` | `A1=41.0 A2=42.0 A3=44.0 AStop=ATail=45.0`, `riseStep1=1.00 riseStep2=2.00 stopRise=0.00 total=5.00` |
| `no-clamp/` (AG-5, first half) | **FAIL** | last cp, HOT-5 | `the restore pushed Health past its cap: current=` | Leg 1 identical to the reference; `L2cur=120.0 L2base=120.0` against `maxHealth=100.0`. **Shares its substring with `current-only-clamp/` -- see ISOLATION CAVEAT 3** |
| `current-only-clamp/` (AG-5, the PIN section 4 wrong solve) | **FAIL** | last cp, HOT-5 | `the restore pushed Health past its cap: current=` | Leg 1 identical to the reference; `L2cur=100.0 L2base=120.0`. The read-back is a clean 100 and the STORED value is 20 over |
| `lowers-at-max/` (AG-5, second half) | **FAIL** | last cp, HOT-6 | `activating the restore at full health changed Health: 100.0 -> ` | Leg 1 identical to the reference; `L2cur=98.0 L2base=98.0` (HOT-5 PASSES, deliberately), `L3cur=98.0` against an AtMaxEpsilon of 0.5 |

---

## The owner EDIT of 2026-08-10 -- what these two rows actually prove

PIN.md's binding owner block pins `StopEpsilon` at **0.25** (was 0.7) and states
the reason: at 0.7, "HOT-3 would not defend AG-4". Two rows in this package test
that claim, and they do not say the same thing.

| | `never-stops/` | `never-stops-in-band/` |
|---|---|---|
| effect shape | ONE effect: Infinite, Period 1.65s, +0.6 | the reference's conforming effect PLUS an Infinite drip, Period 1.65s, +0.6 |
| changed files | `HealOverTimeEffect.cpp` | `HealOverTimeAbility.{h,cpp}` |
| gate HOT-2 (`riseStep1` / `riseStep2` vs 0.5) | 0.60 / 0.60 -- PASS | 5.60 / 10.60 -- PASS |
| gate HOT-3 at `StopEpsilon = 0.25` | `stopRise` 0.60 -- **FAIL** | `stopRise` 0.60 -- **FAIL** |
| gate HOT-3 at `StopEpsilon = 0.70` | 0.60 -- PASS | 0.60 -- PASS |
| HOT-4 (`total` vs 10..40) | 3.00 -- **FAIL** | 28.00 -- PASS |
| HOT-5 / HOT-6 | not reached | PASS / PASS |
| **verdict had the sheet shipped 0.7** | still FAIL, at HOT-4 | **PASS -- all nine gates green** |

So:

- **`never-stops/` shows the edit buys ATTRIBUTION, not a new catch.** At 0.7
  this submission still FAILs -- but under the name "the total restored is
  outside the stated 10-40 band", which describes something its author did not
  get wrong. That is the F5 defect class the whole family was authored to avoid.
- **`never-stops-in-band/` shows the edit buys a CATCH that did not exist.** At
  0.7 a permanent regeneration ships green.

**Why `never-stops/` cannot do better, and why that is structural rather than a
tuning failure.** For a single periodic effect the executions are uniform, so
the count over the whole `(0, +9.2]` observation is about `9.2/p` and the count
in the 2.1s stop window is about `2.1/p` -- a ratio of about 4.4. Passing HOT-4
needs `total >= 10` while passing HOT-3 at 0.7 needs the stop-window gain
`<= 0.7`, i.e. a ratio of at least 14.3. And the period is not free: one
execution in each 1.5s rise window bounds `p` to `(1.37, 2.05]`, and over that
entire range the 2.1s stop window always contains at least one execution (it is
longer than the largest admissible period), so `nStop >= 1` always. **No
single-GE permanent regeneration clears HOT-3 and HOT-4 together.** Escaping
that bound requires paying HOT-4 with a second, conforming effect -- which is
exactly what `never-stops-in-band/` does.

**The magnitude in both rows is pinned the same way the owner pinned
`StopEpsilon`.** With exactly one execution in each gated window, the per-period
magnitude `m` must satisfy `m > RiseEpsilon = 0.50` (so HOT-2 passes) and
`m <= 0.70` (so HOT-3 would have passed at the old bar). `m = 0.60` is the exact
midpoint: 0.10 of margin on each side. Against the PINNED 0.25 the margin is
0.35.

**The period is pinned by tick placement, not by taste.** At `p = 1.65s` and
`bExecutePeriodicEffectOnApplication = false`, executions land at
1.65 / 3.30 / 4.95 / 6.60 / 8.25 / 9.90 after the trigger, putting exactly one
in each of `(+1.1, +2.6]`, `(+2.6, +4.1]` and `(+7.1, +9.2]`. The smallest
distance from any execution to a boundary that would change one of those counts
is **0.50 s = 30 frames at the runner's `-FPS=60`**. The counts are therefore
structural, not lucky. Full derivation, execution by execution, is in
`never-stops/Source/ThirdPerson/HealOverTimeEffect.cpp`.

---

## ISOLATION CAVEAT 1 -- `empty` and `no-maxhealth/` share one named FAIL

With no overlay, `ResolveAgentPawnClass` finds no concrete native
`ACraftBenchCharacter` subclass in the ThirdPerson substrate
(`ACraftBenchBareCharacter` is `UCLASS(Abstract)` and is skipped, and
`ACraftBenchCharacter` itself is explicitly excluded from the candidate list)
and no Blueprint subclass under `/Game/Tasks`, so it returns
`ACraftBenchCharacter::StaticClass()`. That pawn never initializes MaxHealth, so
**HOT-0 fires first** -- the same gate, and the same single
`FinishTest(Failed, ...)`, that `no-maxhealth/` is aimed at.

**It is not a duplicate.** `empty` reaches HOT-0 incidentally: the scaffold pawn
is uninitialized AND meshless AND grants nothing, so which gate it trips first
is an accident of checkpoint order. `no-maxhealth/` is a submission that is
correct on every other axis -- it grants the ability, ships the clamping
attribute set, wears the mannequin, and initializes Health to 100 -- whose only
fault is the missing cap. It is the only leg that proves HOT-0 discriminates on
the MaxHealth axis alone. The two are separated by the RUN, not by the string.

**Note the contrast with `gp-glide-stamina-cpp`,** whose MATRIX records `empty`
and `no-mesh/` colliding. That does NOT happen here: this fixture runs HOT-0
BEFORE HOT-7 at checkpoint 0 (PIN.md D3), and the scaffold pawn fails HOT-0
first, so **`no-mesh/` is cleanly isolated in this package.**

## ISOLATION CAVEAT 2 -- `never-stops/` and `never-stops-in-band/` share one named FAIL

`HealOverTimeFunctionalTest.cpp` holds exactly ONE
`FinishTest(EFunctionalTestResult::Failed, ...)` for HOT-3, and both variants
reach it, so one log line satisfies both greps. **The two rows do not isolate at
the substring level.** It is irreducible without splitting HOT-3 into two named
assertions, which would be a verifier-module change and is out of this package's
ownership.

What separates them is the RUN: every sample in their `[HEALOVERTIME-FINAL]`
lines differs (`A1` 40.0 vs 45.0, `ATail` 43.0 vs 68.0, `total` 3.00 vs 28.00),
and only `never-stops-in-band/` would have passed the whole task at
`StopEpsilon = 0.7`. Those digits all sit behind `%.1f` / `%.2f` placeholders,
so no grep can reach them. Keeping both rows is deliberate -- see **The owner
EDIT**, above: one of them proves attribution, the other proves the catch.

## ISOLATION CAVEAT 3 -- `no-clamp/` and `current-only-clamp/` share one named FAIL

Same mechanism: HOT-5 has exactly one `FinishTest(Failed, ...)`, and both
variants reach it. **They do not isolate at the substring level.**

They are nevertheless both required, and this is the caveat to read hardest:

- `no-clamp/` reads `current=120.0 base=120.0` -- caught by EITHER half of
  HOT-5's disjunction. A current-only gate would catch it too.
- `current-only-clamp/` reads `current=100.0 base=120.0` -- caught ONLY by the
  base half. **This is the row that proves HOT-5's dual read is not
  decoration**: delete `PawnAttributeBase()` from the gate and this submission
  passes the entire task while silently absorbing the next 20 points of damage.
  It is PIN.md section 4's "plausible-WRONG solve ... the one a real model
  writes", verbatim.

The distinguishing digits sit behind `%.1f`, so the separation is in the run.
`cb discriminate` grades each variant separately, so the collision costs nothing
at grading time -- it only means this MATRIX cannot, by itself, prove the two
axes are separately defended.

---

## Delta audit (`diff -rq ../reference/Source/ThirdPerson <variant>/Source/ThirdPerson`)

Run at authoring time; reproduce it before trusting any row.

> NOTE: the overlay name is deliberately NOT column 1 here. `parse_matrix`
> keys rows by their FIRST cell and LAST ROW WINS, so a later table repeating
> a leg label silently blanks that leg's recorded substring - the exact defect
> the substring oracle caught on `gp-poison-dot-stack-bp` and again here.

| Files that differ from the reference | Overlay | Axis |
|---|---|---|
| `HealOverTimePawn.cpp` | `no-maxhealth/` | `InitMaxHealth` not called |
| `HealOverTimePawn.cpp` | `no-mesh/` | mannequin finder removed |
| `HealOverTimePawn.{h,cpp}` | `no-gas/` | ability not granted; restore moved to Tick |
| `HealOverTimeEffect.cpp` | `instant/` | `Instant` policy, +25.0 once |
| `HealOverTimeEffect.cpp` | `never-stops/` | `Infinite` policy, Period 1.65, +0.6 |
| `HealOverTimeAbility.{h,cpp}` | `never-stops-in-band/` | second `Infinite` drip applied alongside the conforming effect |
| `HealOverTimeEffect.cpp` | `out-of-band/` | +1.0 per period (total 5.0) |
| `HealOverTimeAttributeSet.{h,cpp}` | `no-clamp/` | both clamp hooks removed |
| `HealOverTimeAttributeSet.{h,cpp}` | `current-only-clamp/` | `PostGameplayEffectExecute` removed |
| `HealOverTimeAttributeSet.{h,cpp}` | `lowers-at-max/` | clamp upper bound `MaxHealth - 2.0` |

No variant adds or removes a file: each directory carries the reference's eight
files. Nothing outside `Source/ThirdPerson/` is added -- a `NOTES.md` at a
submission root would be a sandbox exit-4 reject, so every variant's
documentation lives in its own source headers, which is also where a reviewer
diffing the overlay will actually see it.

---

## Per-note coverage (PIN.md section 3)

| Anti-gaming note | Committed variant | Gate | Named substring | Status |
|---|---|---|---|---|
| **AG-1** MaxHealth left at its default 0 | `no-maxhealth/` | HOT-0 | `MaxHealth was not initialized: read ` | **MEASURED 2026-08-10** (L2 FAIL by name) |
| **AG-2** restore driven from Tick or BeginPlay, nothing activatable | `no-gas/` | HOT-1 | `no activatable ability tagged Ability.HealOverTime on the pawn (the restore is not an activatable ability). granted=` | **MEASURED 2026-08-10** (L2 FAIL by name) |
| **AG-3** one instant restore dressed as an ability | `instant/` | HOT-2 | `the restore was not periodic: Health did not keep rising in steps (A1=` | **MEASURED 2026-08-10** (L2 FAIL by name) |
| **AG-4** permanent regeneration that never expires | `never-stops/` **and** `never-stops-in-band/` | HOT-3 | `the restore did not STOP after its duration: Health was still rising in the post-band stop window (AStop=` | **MEASURED 2026-08-10** (L2 FAIL by name); the two share this substring (CAVEAT 2) |
| **AG-5** clamp only the read value, or "clamp" by lowering | `no-clamp/`, `current-only-clamp/`, `lowers-at-max/` | HOT-5 (first two), HOT-6 (`lowers-at-max/`) | `the restore pushed Health past its cap: current=` | **MEASURED 2026-08-10** (L2 FAIL by name); the substring column names the HOT-5 literal ONLY, because that is what the two clamp overlays log and a cell naming two literals would demand BOTH in one log line. `lowers-at-max/` trips HOT-6 instead and logs `activating the restore at full health changed Health: 100.0 -> ` -- documented here, matched on its own Matrix row above. The first two share the HOT-5 substring (CAVEAT 3) |
| **AG-6** token 1 HP restore | `out-of-band/` | HOT-4 | `the total restored is outside the stated 10-40 band: Health went 40.0 -> ` | **MEASURED 2026-08-10** (L2 FAIL by name) |
| **AG-7** meshless pawn, invisible on the film strip | `no-mesh/` | HOT-7 | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | **MEASURED 2026-08-10** (L2 FAIL by name) |

Seven notes, ten variants, and **no note is left to an ARGUED entry** -- every
one has a committed overlay. **This table's note column deliberately carries no
path-shaped text** ("Tick or BeginPlay", never "Tick/BeginPlay"): `parse_matrix`
reads any `<word>/` fragment in a FIRST cell as a variant directory, so the old
wording minted a phantom `Tick` leg out of a documentation row -- and, because
this table also heads a column with "substring" in it, made it a SECOND
submission table whose labels can overwrite the Matrix table's. Same hazard,
same discipline, as the NOTE above the Delta audit.

---

## The fixture's named FAIL substrings, and which note each defends

Enumerated from every `FinishTest(EFunctionalTestResult::Failed, ...)` in
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-heal-over-time/HealOverTimeFunctionalTest.cpp`.
The two in the base class (`SpawnAndPossessPawn: no world`,
`SpawnAndPossessPawn: spawn of `) are harness conditions, not gates, and are not
listed.

| # | Named substring (a literal run -- no `%` spanned) | Fires at | Defends |
|---|---|---|---|
| 1 | `pawn did not spawn/resolve` | any checkpoint | **no note** -- harness/resolution condition |
| 2 | `pawn has no AbilitySystemComponent` | any checkpoint | **no note** -- harness condition |
| 3 | `MaxHealth was not initialized: read ` | cp0, HOT-0 | AG-1 (`no-maxhealth/`) |
| 4 | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | cp0, HOT-7 | AG-7 (`no-mesh/`) |
| 5 | `no activatable ability tagged Ability.HealOverTime on the pawn (the restore is not an activatable ability). granted=` | last cp, HOT-1 | AG-2 (`no-gas/`) |
| 6 | `an ability tagged Ability.HealOverTime was granted but did NOT activate on TryActivateAbilitiesByTag` | last cp, HOT-1 | AG-2, second half -- **NO COMMITTED VARIANT**, see holes |
| 7 | `an ability tagged Ability.HealOverTime refused a later activation: ` | last cp, HOT-1c | **no note** -- see holes |
| 8 | `the restore was not periodic: Health did not keep rising in steps (A1=` | last cp, HOT-2 | AG-3 (`instant/`) |
| 9 | `the restore did not STOP after its duration: Health was still rising in the post-band stop window (AStop=` | last cp, HOT-3 | AG-4 (`never-stops/`, `never-stops-in-band/`) |
| 10 | `the total restored is outside the stated 10-40 band: Health went 40.0 -> ` | last cp, HOT-4 | AG-6 (`out-of-band/`) |
| 11 | `the restore pushed Health past its cap: current=` | last cp, HOT-5 | AG-5 first half (`no-clamp/`, `current-only-clamp/`) |
| 12 | `activating the restore at full health changed Health: 100.0 -> ` | last cp, HOT-6 | AG-5 second half (`lowers-at-max/`) |

Ten of the twelve are reached by a committed variant. The two that are not are
recorded below rather than silently filled.

---

## Known holes (named gates with NO corresponding variant)

- **(a) Substring 6 -- granted-but-never-activates.** This is the second half of
  AG-2's stated defense and has no overlay. One is authorable (an ability whose
  `CanActivateAbility` refuses, or one with a blocking tag), but AG-2 already has
  `no-gas/` and the hole is recorded instead of padded. Same shape and the same
  decision as hole (c) in `gp-glide-stamina-cpp/discrimination/MATRIX.md`.
- **(b) Substring 7 -- HOT-1c, the refused re-activation -- defends a shape no
  anti-gaming note names.** The fixture triggers the same tag once per leg,
  three legs in one run, and UE 5.8 refuses re-activation of a still-running
  `InstancedPerActor` ability or one on cooldown. HOT-1c exists so that a
  refused Leg 2 or Leg 3 activation cannot pass HOT-5 or HOT-6 *vacuously* --
  a real and important gate with no note behind it. A variant is easy (give the
  reference ability a cooldown effect longer than the schedule) and was not
  authored here; the hole is the record.
- **(c) HOT-2's undisclosed lower edge is untested from BELOW.** `instant/`
  attacks HOT-2 with a step of exactly 0.0. No committed variant sits just under
  `RiseEpsilon = 0.5` -- and none can be authored honestly until `RiseEpsilon`
  is MEASURED, because a variant tuned against an unmeasured bar tests the
  guess, not the gate. PIN.md section 6 owes both populations.

---

## Substrate dependency

- The **ability-aware pawn resolver** (`PreferredAbilityTag()`,
  `CraftBenchPawnFunctionalTest.cpp`). The fixture returns
  `FCraftBenchGameplayTags::AbilityHealOverTime()`, so nine of the ten variants
  are resolved by the tag they grant and cannot be displaced by another
  committed `ACraftBenchCharacter` subclass.
- **`no-gas/` is the exception and is the row to re-check first if anything in
  the substrate changes.** It grants nothing, so the tag preference finds no
  match and the resolver falls back to `Candidates[0]` -- the first CONCRETE
  NATIVE `ACraftBenchCharacter` subclass. Verified on disk at authoring time:
  the ThirdPerson substrate ships exactly one other subclass,
  `ACraftBenchBareCharacter`, and it is `UCLASS(Abstract)`, so `AHealOverTimePawn`
  is still the graded pawn. **If a future task commits another concrete native
  subclass into `Source/ThirdPerson/`, enumeration order decides the fallback
  and this row can start failing under a different name.**
- The **V1.4 dual attribute read** (`PawnAttribute` / `PawnAttributeBase` on
  `CraftBenchPawnFunctionalTest.h`). `current-only-clamp/` is the row that has no
  meaning without it.
- The **`Ability.HealOverTime` native tag** in
  `Source/ThirdPerson/CraftBenchGameplayTags.{h,cpp}` (PIN.md D5).

---

## Blocking dependency before any of this can be run

**There is no `task.md` for this family yet.** `tasks/bp-g2/gp-heal-over-time/`
currently holds `PIN.md`, `reference/` and this `discrimination/` package.
`run_task.py` takes `--task <path to task.md>`, so **every command below will
fail with a spec error until the spec is authored.** Note also that the family's
final id is `gp-heal-over-time-{cpp,bp}` per PIN.md's title while the folder on
disk is still `gp-heal-over-time`; if the folder is renamed to
`gp-heal-over-time-cpp` (the 2026-08-06 `-cpp` rename convention that
`gp-glide-stamina` and `gp-poison-dot-stack` already went through), **update
every path below in the same change**.

---

## Re-validate (the commands that promote every row above from PREDICTED to MEASURED)

Run on a box with UE 5.8 and **no other session holding the engine**: `Build.bat`'s
mutex is keyed on the ENGINE INSTALL, not the project, so a contended build
returns exit 1 with no compile errors and would be misread as a variant failing
L1. Check `CRAFTBENCH_L1_MAX_PARALLEL` is SET before starting -- an unset cap
makes L1 die with `C3859`/`C1076` deterministically on every task, and no
preflight probe catches it.

```sh
$env:CB_UE_ROOT='<UE-root>'
$T='tasks/bp-g2/gp-heal-over-time/task.md'

# The reference must PASS in the same sweep -- it is the control. A sweep in
# which the reference FAILs measures the box, not the variants.
python tools/verify-single/run_task.py --task $T `
    --submission tasks/bp-g2/gp-heal-over-time/reference --substrate-from-live --ue-root $env:CB_UE_ROOT

python tools/verify-single/run_task.py --task $T `
    --submission tasks/bp-g2/gp-heal-over-time/discrimination/no-maxhealth --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task $T `
    --submission tasks/bp-g2/gp-heal-over-time/discrimination/no-mesh --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task $T `
    --submission tasks/bp-g2/gp-heal-over-time/discrimination/no-gas --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task $T `
    --submission tasks/bp-g2/gp-heal-over-time/discrimination/instant --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task $T `
    --submission tasks/bp-g2/gp-heal-over-time/discrimination/never-stops --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task $T `
    --submission tasks/bp-g2/gp-heal-over-time/discrimination/never-stops-in-band --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task $T `
    --submission tasks/bp-g2/gp-heal-over-time/discrimination/out-of-band --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task $T `
    --submission tasks/bp-g2/gp-heal-over-time/discrimination/no-clamp --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task $T `
    --submission tasks/bp-g2/gp-heal-over-time/discrimination/current-only-clamp --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task $T `
    --submission tasks/bp-g2/gp-heal-over-time/discrimination/lowers-at-max --substrate-from-live --ue-root $env:CB_UE_ROOT
```

The equivalent single command once the spec exists and the box is free:

```sh
cb discriminate gp-heal-over-time
```

**A variant that FAILs at a substring other than its own is a MIS-AUTHORED
VARIANT, not a discrimination win.** Read the two `[HEALOVERTIME-FINAL]` lines
before touching the fixture -- line 1 carries every sample and every computed
value, line 2 carries the nine REALIZED window lengths (`w2`,`w3` are the
congruent rise pair, `w5` is the stop window), which is where a tick-placement
disagreement with the derivations in this package will show up first.

### What to record when the sweep is run

Replace this section with the results, and capture -- per PIN.md section 6, which
this package does NOT discharge -- the numbers the family still owes:

1. **Both populations for `RiseEpsilon`**: the reference's measured
   `riseStep1`/`riseStep2` (conforming side) against `instant/`'s 0.00
   (violating side), with the margin on each side.
2. **Both populations for `StopEpsilon`**: the reference's measured `stopRise`
   (predicted 0.00, and structurally so -- the stop window opens past the
   disclosed band top, so no legitimate execution can land in it) against
   `never-stops/`'s and `never-stops-in-band/`'s 0.60, plus the
   `StopEpsilon < 1.000 * RiseEpsilon` inequality it is pinned against.
3. **`ClampEpsilon` against THREE solves** -- the C++ reference, a BP
   magnitude-calculation lane, and a BP ability-loop lane. **This package
   contains none of the BP lanes**, so `ClampEpsilon` remains uncalibrated for
   the `-bp` twin even after every row above is green. PIN.md D1 names
   calibrating only against the C++ reference as "exactly how this fixture would
   false-FAIL a conforming BP solve".
4. **The total-restored band**: the reference's measured `total` (predicted
   25.00, the exact midpoint of 10..40) against `out-of-band/`'s 5.00.

## Requirements table (checklist §7, the mandatory soundness artifact)

Layers are `[L1, L2]` — every gate below is an L2 `FinishTest(EFunctionalTestResult::Failed, ...)`
literal; there is no L2I lane on this task. Every backticked span is a contiguous literal run of ONE
format string (never spanning a `%`-placeholder) in
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-heal-over-time/HealOverTimeFunctionalTest.cpp`,
except row 12's, which lives in the hoisted base-class check
`ACraftBenchPawnFunctionalTest::PawnVisiblyRepresented`
(`UE-projects/ThirdPerson/Source/CraftBenchTests/CraftBenchPawnFunctionalTest.cpp`) and reaches
`FinishTest` through the fixture's `VisWhy` pass-through. Gate ordering, which the "Gate skipped when"
column depends on: two pre-gates (`pawn did not spawn/resolve`, `pawn has no AbilitySystemComponent`)
run at EVERY checkpoint; HOT-0 then HOT-7 run at cp0 and a FAIL there ends the run before any final
gate; the final gates run at cp9 in the fixed order HOT-1a → HOT-1b → HOT-1c → HOT-2 → HOT-3 → HOT-4
→ HOT-5 → HOT-6, each `FinishTest` skipping everything after it.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | the restore is an **ability the game can activate** on the character (not Tick/BeginPlay regeneration) | fully | HOT-1a — `no activatable ability tagged Ability.HealOverTime on the pawn (the restore is not an activatable ability). granted=` | pre-gates, or a cp0 FAIL (HOT-0/HOT-7) ends the run before cp9 | the ability body is unconstrained — it may do arbitrary extra work (spawn actors, log, apply unrelated effects); only the Health trace is gated |
| 2 | tagged `Ability.HealOverTime`, in the pawn's granted abilities, **startable by that tag** | fully — and STRICTER than the prompt | HOT-1b — `an ability tagged Ability.HealOverTime was granted but did NOT activate on TryActivateAbilitiesByTag`; plus HOT-1c — `an ability tagged Ability.HealOverTime refused a later activation: ` | row 1 fires first; cp0 FAIL | nothing on the lenient side. **Reverse hole**: HOT-1c requires all THREE per-leg activations to land, a re-activatability demand the prompt never states — an idiomatic still-running `InstancedPerActor` ability or one on cooldown FAILs conforming work by this name (recorded as MATRIX hole (b); no anti-gaming note owns it) |
| 3 | raises Health **repeatedly** — "It must not be a single instant restore" | fully | HOT-2 — `the restore was not periodic: Health did not keep rising in steps (A1=` | rows 1–2 fire first; cp0 FAIL | exactly TWO rising ticks (one per 1.5 s window) already read as "repeatedly"; each step need only clear `RiseEpsilon = 0.5` (PROPOSED — NOT YET MEASURED) |
| 4 | cadence "**about once per second**" | partially — as "at least one rising tick in each congruent 1.5 s window", never as a rate (deliberate: owner decision Q5(b), no rate bar) | HOT-2 — same token as row 3 (the two windows are `(trigger+1.1, +2.6]` and `(+2.6, +4.1]`) | rows 1–2; cp0 FAIL | any period from a few ms up to ~2.05 s (phased) passes; a 3-tick burst shaped to land one tick per window passes. "Once per second" is not a number any gate holds |
| 5 | duration "**roughly five seconds, then stop**"; disclosed: "any duration in the four-to-seven-second range" | partially — UPPER edge only (stopped before the stop window opens at trigger+7.1) | HOT-3 — `the restore did not STOP after its duration: Health was still rising in the post-band stop window (AStop=` | rows 1–3 fire first; cp0 FAIL | **the band's 4 s FLOOR is unenforced**: a ~3 s effect that ticks once in each rise window and restores ≥ 10 total passes every gate despite sitting below the disclosed acceptance band |
| 6 | "it must not keep restoring forever" | fully | HOT-3 — same token as row 5 (`StopEpsilon = 0.25`, the owner-EDIT bound; PROPOSED — NOT YET MEASURED) | rows 1–3; cp0 FAIL | a permanent drip tuned under the noise floor (≤ 0.25 gain across the 2.1 s stop window, i.e. ≲ 0.12 HP/s) riding alongside a conforming effect clears HOT-3 AND keeps HOT-4 in band — the sub-epsilon sibling of `never-stops-in-band/` |
| 7 | "each application must restore a total of between **10 and 40** Health across its lifetime" | fully (Leg 1) | HOT-4 — `the total restored is outside the stated 10-40 band: Health went 40.0 -> ` | rows 1–6 (HOT-1a through HOT-3) fire first; cp0 FAIL | measured on Leg 1 ONLY (preset 40 → ATail); Legs 2/3 totals are structurally unobservable behind the clamp, so a magnitude that varies per activation is invisible |
| 8 | "your pawn must **initialize MaxHealth to 100**" | fully — first gate, cp0, before any trigger and any fixture write | HOT-0 — `MaxHealth was not initialized: read ` (100 ± `MaxHealthEpsilon` 0.5) | only the two pre-gates (pawn unresolved / no ASC) precede it | changing MaxHealth AFTER cp0 is ungated per se — but HOT-5 clamps against the cp0-pinned `MaxHealthRead`, not a live re-read, so raising the cap later buys nothing (the live value is logged as `L2maxLive`, diagnostic only). Initializing Health is NOT required — the fixture presets it |
| 9 | "Health must **never exceed** MaxHealth — neither the value the game reads back, nor the underlying stored value" | fully at the sampled instant — the V1.4 DUAL read (current AND base, same checkpoint) | HOT-5 — `the restore pushed Health past its cap: current=` | rows 1–7 (HOT-1a through HOT-4) fire first; cp0 FAIL | "never" is sampled ONCE, at Leg-2 trigger+5.1 (cp7, after the effect should have expired): a transient mid-effect overshoot that settles back under the cap before the read passes; overshoot ≤ `ClampEpsilon` 0.5 tolerated (uncalibrated against any BP lane — PIN.md D1) |
| 10 | activating at full health "must leave Health at 100: it must not push past it, and it must not lower it" | fully, both directions — on the CURRENT value only (base reported, deliberately ungated so HOT-5 stays the single named cause of the current-only-clamp defect) | HOT-6 — `activating the restore at full health changed Health: 100.0 -> ` (±`AtMaxEpsilon` 0.5) | rows 1–7 or 9 (HOT-1a through HOT-5) fire first; cp0 FAIL | a Leg-3 BASE excursion with a clean current read is ungated here by design (the same mechanism is caught at Leg 2 by HOT-5, so only a defect that manifests exclusively under at-max activation escapes) |
| 11 | "Deliver your pawn as a **subclass of the provided character** (C++ or Blueprint) with your ability granted on it" | structurally, by the substrate's pawn-resolution model — no dedicated FinishTest | not a gate — `ResolveAgentPawnClass` enumerates only `ACraftBenchCharacter` subclasses and prefers the candidate granting the `Ability.HealOverTime` tag (`PreferredAbilityTag()`); a non-subclass delivery falls back to the scaffold pawn and dies at HOT-0 (`MaxHealth was not initialized: read `) — a truthful FAIL but not this requirement's name | unconditional | shipping EXTRA pawns/actors is free; among tag-granting subclasses the preferred-tag rule picks the graded one, so a decoy without the tag is simply ignored |
| 12 | "The character must be **visibly represented**" — a mesh a reviewer can see | fully (existence + not hidden-in-game + not zero-scale, per the 2026-08-11 hoisted base-class check) | HOT-7 — `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` (the no-mesh arm; every arm shares the prefix `the character is not visibly represented: `) | pre-gates, or HOT-0 fires first at cp0 (the `empty`/`no-maxhealth` collision, CAVEAT 1) | a tiny-but-not-degenerate mesh, an unlit/transparent material, or a mesh buried inside the capsule all pass — visibility is structural, not rendered |
| 13 | the mesh is "**one of the provided mannequin skeletal meshes (under /Game/Characters/)**" | **NOT ASSERTED** | — no gate reads the assigned asset's path, type, or identity; `PawnVisiblyRepresented` documents asset path / mesh type / size as deliberately not asserted | — | any mesh asset satisfies HOT-7 — a static-mesh cube, an engine primitive, or a custom import; the prompt's specific mannequin instruction is unenforced end to end |
| 14 | Health lives in "the attribute set type the project provides" | structurally, by construction | not a dedicated gate — every fixture read/write goes through `UCraftBenchAttributeSet::GetHealthAttribute()` on the pawn's ASC (`PawnAttribute`/`PawnAttributeBase`/`SetNumericAttributeBase`), so a home-grown health variable shows a flat trace and dies at HOT-2 (`the restore was not periodic: Health did not keep rising in steps (A1=`) — a FAIL, but under the periodicity name, not this requirement's | unconditional | subclassing the attribute set is fine and expected (`IsA` match — the reference does exactly this); the misattributed FAIL NAME for a wrong-resource submission is a legibility cost, not a soundness one |

### Residuals this table surfaces (escalation list, not papered over)

- **(R1, row 13 — the one NOT ASSERTED row.)** The mannequin/`/Game/Characters/` clause is prompt
  text with no gate behind it anywhere. The base class records the omission as deliberate, but the
  prompt still instructs it in imperative voice — either the `-bp` twin's L2I
  `pawn_visibly_represented` lane should check asset identity, or the prompt clause should soften to
  match what HOT-7 actually holds.
- **(R2, row 5.)** The DISCLOSED 4–7 s acceptance band is enforced only from above. The disclosure
  was this family's headline F5 correction, which makes the unenforced floor worth naming: the
  fixture accepts durations the prompt says the verifier would not.
- **(R3, row 2.)** HOT-1c is stricter than the prompt (three activations must land; re-activatability
  is never stated). Already MATRIX hole (b); it belongs in the prompt or out of the gate.
- **(R4, row 6.)** A sub-`StopEpsilon` permanent drip stacked on a conforming effect passes all nine
  gates. Bounded by HOT-4's band on Leg 1, so the residual magnitude is ≲ 0.12 HP/s — documented
  here rather than defended.
- **(R5, row 9.)** "Never exceeds" is a single-instant sample per leg; transient overshoot that
  self-corrects before trigger+5.1 is invisible. A mid-effect checkpoint inside Leg 2 would close it
  at the cost of one more sample.
