# gp-poison-dot-stack-cpp — discrimination matrix

> **Rename + visibility epoch 2026-08-06 (owner decision).** The task id
> changed `gp-poison-dot-stack` → `gp-poison-dot-stack-cpp` (surface
> differentiation from the `-bp` twin; set stays `bp-g2`), and the shared
> fixture gained the **checkpoint-0 visible-character gate** — stage-1 gate
> (e), sequenced AFTER gates (a)-(d) so every named stage-1 FAIL below is
> unchanged ("the character is not visibly represented: no mesh component
> with an assigned mesh on the graded pawn"). The reference and the
> `no-cap`/`no-refresh`/`no-health-system` variants now constructor-assign
> the mannequin mesh (`/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple`)
> so each variant stays ONE delta from the reference. Matrix rows below that
> pre-date this epoch were run under the old id and without the visibility
> gate. All five rows re-run at this epoch on Windows / UE 5.8,
> `--substrate-from-live`, 2026-08-06: `../reference` **PASS** with the
> mannequin visible and the timeline below reproduced value-for-value
> (`Rate1=4.88 RateB=14.63 ratio=3.00`); `no-refresh/` **FAIL** at the named
> refresh gate (`CPost1=75.0 -> CPost2=75.0 ... drop 0.0 < 2.0`); `no-cap/`
> **FAIL** at the named cap gate (`RateB=19.51 / Rate1=4.88 > 3.5x` = 4.00x);
> `no-health-system/` **FAIL** at the named presence gate (sequencing proof:
> gate (b) fires before the new gate (e)); empty **FAIL** at the named
> derivation gate (unchanged — derivation precedes visibility).

> **Substrate epoch 2026-08-06 evening — re-validated on ThirdPerson.** The
> task moved to the `ThirdPerson` substrate (C++-pair migration; see task.md's
> substrate epoch note); the reference and all three variant overlays now
> live under `Source/ThirdPerson/` prefixes (byte-identical files). All five
> matrix rows re-run through the deterministic verifier on Windows / UE 5.8,
> `--substrate-from-live`, 2026-08-06 evening: `../reference` **PASS** with
> the timeline below reproduced value-for-value (`Rate1=4.88 RateB=14.63
> ratio=3.00`); `no-refresh/` **FAIL** at the named refresh gate
> (`CPost1=75.0 -> CPost2=75.0 ... drop 0.0 < 2.0`); `no-cap/` **FAIL** at
> the named cap gate (`RateB=19.51 / Rate1=4.88 > 3.5x` = 4.00x);
> `no-health-system/` **FAIL** at the named presence gate; empty **FAIL** at
> the named derivation gate. The measured timeline below (pinned on
> CraftBenchTemplate at the Leg C/D epoch) reproduced identically on
> ThirdPerson under `-deterministic -FPS=60`.

> **✅ REDEFINITION EPOCH 2026-08-05 (health-first two-stage restructure) —
> RE-VALIDATION DONE 2026-08-06.** The "every row below must be re-run"
> requirement this banner raised was **satisfied twice on 2026-08-06**, by the
> two banners above it: all five rows were re-run at the rename + visibility
> epoch (`ca7f20c`) and again after the C++ pair moved to ThirdPerson
> (`c1e68fe`), reproducing the timeline value-for-value
> (`Rate1=4.88 RateB=14.63 ratio=3.00`). **This task's matrix is fully measured
> — 5 of 5 rows, at HEAD, on the current substrate.** It is the only one of the
> four glide/poison matrices that is.
>
> _What the epoch changed (unchanged as a description):_ stage 1 (build the
> health system) is the agent's work — the task base pawn
> (`ACraftBenchBareCharacter`, abstract, ASC-only) ships with NO attribute set,
> and checkpoint 0 is the stage-1 gate (derivation + presence + init-to-100 + a
> 37≠100 write probe). The reference gained the stage-1 build (`PoisonPawn`
> parents the task base, constructs the contract attribute set under a
> non-suppressed subobject name, and inits Health/MaxHealth to 100). Results
> before/after 2026-08-05 are still not comparable (same convention as glide's
> 2026-08-04 redefinition); the pre-epoch validation stamps below this note
> refer to the old single-stage task.

First validated on Windows / UE 5.7.4 (2026-06-19); re-pinned on Windows /
UE 5.8 at the 2026-08-06 Leg C/D epoch (refresh + cap gates; congruent rate
windows). GAS judgment-family task; thresholds calibrated from the measured
reference + probe runs below.

## Measured reference timeline (calibration source — 2026-08-06 epoch, 16-checkpoint schedule, `-deterministic -FPS=60`, `--substrate-from-live`)

| leg | t (s) | Health | note |
|---|---|---|---|
| A (1 stack) | 0.5 | 100 | stage-1 gate, then preset + trigger ×1 |
| A | 1.6 / 3.1 / 4.6 | 95 / 90 / 80 | periodic −5/tick @ ~1s |
| A stop window | 7.6 / 9.7 | **75 / 75** | STOPPED (window opens PAST the ~5s band top) |
| C (refresh) | 10.7 | 100 | preset + trigger ×1 |
| C | 12.3 | 95 | mid-drain (logged) |
| C re-apply | 14.3 | 85 | trigger ×1 again (2 stacks, period reset) |
| C refresh window | 17.9 / 19.4 | **55 / 35** | still draining PAST the un-refreshed band top (refresh proven) |
| C stop window | 21.4 / 23.5 | **35 / 35** | refreshed drain ENDED (past re-apply+7.0) |
| B/D (4 applies) | 24.5 | 100 | preset + trigger ×4 (cap → 3 stacks) |
| B/D | 26.1 | 85 | mid-drain (logged), −15/tick |
| B/D | 28.6 | **40** | window trigger+4.1, CONGRUENT with Leg A's |

`Rate1 ≈ 4.88 Health/s, RateB ≈ 14.63 Health/s, ratio = 3.00×, granted=1,
activated=1.` The `no-cap/` probe (StackLimitCount=0, all else identical)
measures `RateB ≈ 19.51, ratio = 4.00×` — the two populations sit 1.0× apart
and `StackRatioMax=3.5` splits them with ~0.5× measured margin each side.
(The historical ~8.9× reading was the pre-epoch reference's −5×stackCount MMC
being multiplied AGAIN by the engine's `bFactorInStackCount` stack factor —
**re-measured at exactly 9.00× on UE 5.8** with the new congruent windows,
2026-08-06, before the reference was fixed to the MMC-less flat −5.0 recipe
the BP reference always used. That superlinear config now FAILs Leg D by
design — the 9.00× run is the measured proof.)

> **RE-VALIDATED 2026-08-08 — the whole table above reproduced EXACTLY** on a
> fresh `run_task.py --substrate-from-live` (Windows / UE 5.8), two days and
> several substrate edits later:
> `[POISON-FINAL] A1=95.0 A2=90.0 A3=80.0 AStop=75.0 ATail=75.0 CAtReapply=85.0
> CPost1=55.0 CPost2=35.0 CStop1=35.0 CStop2=35.0 BEnd=40.0 Rate1=4.88
> RateB=14.63 ratio=3.00`. Every Health value and the ratio match the recorded
> calibration to the digit — the determinism claim (`-deterministic -FPS=60`)
> is now cross-session evidence, not a single reading. The full matrix was
> re-run in the same sweep: reference **PASS**; `no-cap` / `no-health-system` /
> `no-refresh` / empty all **FAIL, each by its own named substring** (`no-cap`
> measured **4.00x**, reproducing the uncapped population that pinned
> `StackRatioMax`).
>
> **The measurement Q5 needs, extracted here because this is the calibration
> record:** the conforming population for BOTH stop windows is
> **`AStop - ATail = 0.0`** and **`CStop1 - CStop2 = 0.0`** — *exactly* zero,
> against today's `StopEpsilon = 2.5`. That is expected rather than lucky:
> Health moves only in discrete GE ticks under fixed timestep, and both stop
> windows open past the acceptance-band top, so no legitimate tick can land in
> either. Consequence for the Q5 change (replacing `PeriodicMinStep` with a
> still-dropping noise floor `eps`): the conforming side needs no headroom at
> all, so `StopEpsilon` is bounded only by the *lawful-drain* side.
>
> **CORRECTED 2026-08-08 — the first version of this paragraph made the SAME
> error as the shipped header it criticises.** It said the bound is
> `(2.1/1.5) * eps = 1.4 * eps`, reasoning as if tick density scaled with window
> length. It does not: ticks are DISCRETE. At Period 1.164s exactly one tick
> lands in a 1.5s periodic window *and* exactly one in the 2.1s stop window, so
> the ratio is **1.0**. Minimising `nStop / min(nPeriodic)` over every
> admissible period on a 1 ms grid gives a global minimum of **exactly 1.000,
> and it is ATTAINED** — so the lawful-drain bound is **`1.0 * eps`**, and
> pinning midway between the measured 0.0 and that bound gives
> **`StopEpsilon = 0.5 * eps`**, equal margin each side. Any derivation of this
> constant MUST be quantified over all admissible periods; assuming a tick count
> is exactly the defect `permanent-drain/` measured. See
> the internal design note (not shipped) for the full work order.

## Matrix

| Submission | Overall | Fails at | Expected message |
|---|---|---|---|
| `../reference` | **PASS** | — | all gates green (stage-1 gate + Legs A, C, B/D) |
| empty (no overlay → base scaffold) | **FAIL** | cp0 (a) derivation | `stage 1 not built: the graded pawn (` — **message CHANGED at the 2026-08-05 epoch** (was the ability-grant message, "no activatable ability ... granted=0"): with no submission, the resolver falls back to the generic scaffold pawn, which now fails stage-1 derivation before any GAS gate is reached |
| `no-health-system/` (NEW 2026-08-05) | **FAIL** | cp0 (b) presence | `stage 1 not built: the pawn's health attribute system is absent` — a complete, correct stage-2 solve (reference ability/GE verbatim) on a task-base pawn that skips stage 1. **Probe-proven 2026-08-05** (scratchpad probe-no-health/, which presented the same ASC-without-Health state via RemoveSpawnedAttribute on the pre-epoch scaffold and FAILed at this exact named gate on a live run); this variant is its promotion to the post-epoch shape |
| `no-refresh/` (NEW 2026-08-06) | **FAIL** | Leg C refresh gate | `re-application did not refresh the duration: after a mid-window re-apply (trigger+3.6) the drain ` — the reference GE with a never-refresh stack duration policy (the ONE delta); re-application adds a stack but the poison still dies ~5s after the FIRST application, so the refresh window (past the un-refreshed band top) shows zero drain. Every other leg passes — the variant isolates the refresh axis |
| `no-cap/` (NEW 2026-08-06) | **FAIL** | Leg D cap gate | `stack cap violated (or scaling is not ~proportional): 4 applications drained ` — the reference GE with an uncapped stack limit (the ONE delta). Doubles as the Leg D calibration probe (its measured 4.00× is the uncapped population that pinned the bar). Every other leg passes — the variant isolates the cap axis |
| `permanent-drain/` (**NEW 2026-08-08**; note 4 - the stop gate's FIRST committed failing variant) | **FAIL** *(**MEASURED 2026-08-08**)* | Leg C refreshed-stop gate | `refreshed poison never expired: Health was still dropping past the refreshed duration band` - **measured** CStop1=46.0 -> CStop2=39.2, drop 6.8 > 2.5. The ONE axis is an infinite duration policy (the drain never ends), with Period 1.164s / -2.25 per tick deliberately tuned by exhaustive rational enumeration to hide inside the tolerances - a GAMING variant, not a naive one. **Read the next block: this variant measured a real unsoundness in the Leg A stop gate.** |

> **What `permanent-drain/` actually measured (2026-08-08) - the Leg A stop gate
> derivation is UNSOUND, and the task is saved by an ACCIDENT.**
>
> `PoisonStackFunctionalTest.h:100` justifies `StopEpsilon = 2.5` as
> "2.5 < 4.0 (= 2 x PeriodicMinStep, the smallest two-tick drop a still-running
> conforming drain leaves in a >= 2.0s window)". That presumes **at least two
> ticks land in the 2.1s stop window**, i.e. a period <= 1.05s - and **no period
> bound is enforced anywhere**. At Period 1.164s only ONE tick lands, so a
> never-ending drain leaves one tick's magnitude and slips under the bar.
>
> **Measured, not argued:** this variant's Leg A stop window read
> `AStop=86.5 -> ATail=84.2`, a drop of **2.3 against the 2.5 bar - it PASSED**,
> on a poison that never ends. Anti-gaming note 4 was defended by argument
> alone until this run.
>
> **Why the task still FAILs it:** an `Infinite` GE's stacks never expire, so the
> Leg A application is still on the pawn when Leg C applies two more. By the Leg
> C refreshed-stop window the effect sits at the **3-stack cap**, and
> `bFactorInStackCount` triples the per-tick magnitude to ~6.75 - which the same
> `StopEpsilon` then catches. Exhaustive enumeration over every admissible
> period on a 1 ms grid, **with cross-leg stack accumulation modelled**, finds
> **0 of 2001 periods** where a permanent drain evades every duration gate.
> (The first enumeration, which ignored stack persistence, wrongly found 410 -
> the live run is what corrected the model.)
>
> **So: the exploit is closed, but INCIDENTALLY.** The defense rests on
> Infinite-GE stack persistence and on Leg C running after Leg A, neither of
> which any comment or gate states as load-bearing. Two consequences for Q5
> (the internal design note (not shipped)): (1) the new `StopEpsilon` derivation
> must be quantified over ALL admissible periods, not the >=2-tick case the
> current one assumes; (2) whatever replaces it must keep this variant FAILing,
> and should ideally fail it at **Leg A**, where the defect actually is.

## Deterministic gates (what flips PASS/FAIL)

0. **STAGE-1 gate (checkpoint 0, all named FAILs)**: (a) pawn derives from the
   task base; (b) ASC carries Health; (c) Health reads 100 BEFORE any fixture
   write; (d) write-then-read at 37 (≠100 so an inert-write set that inits at
   100 cannot pass vacuously); (e) **visible character (NEW 2026-08-06)** — a
   skeletal/static mesh component with an assigned mesh exists on the graded
   pawn ("the character is not visibly represented: ...").
1. `NumGrantedAbilitiesWithTag(Ability.Poison) >= 1` (GAS implemented).
2. ability activated on the tag-trigger.
3. **Periodic**: Health falls in steps (A1>A2>A3, each ≥ 2) — an instant lump fails.
4. **Stops (band-calibrated 2026-08-06)**: stop window `(trigger+7.1, trigger+9.2]`
   opens past the ~5s acceptance-band top; drop ≤ `StopEpsilon` (2.5) — a
   permanent drain fails; a conforming ~4-7s duration (incl. ~6s) passes.
5. **Refresh, direction 1 (NEW 2026-08-06)**: after the mid-window re-apply
   (trigger+3.6), drop across `(CStart+7.2, CStart+8.7]` ≥ `RefreshMinStep`
   (2.0) — a never-refreshing GE fails ("re-application did not refresh").
6. **Refresh, direction 2 (NEW 2026-08-06)**: drop across
   `(re-apply+7.1, re-apply+9.2]` ≤ `StopEpsilon` — a refreshed effect that
   never expires fails ("refreshed poison never expired").
7. **Stacking scales**: 4-application rate ≥ `StackRatioMin` (2.0) × the
   single-stack rate — a flat (non-stacking) drain fails.
8. **Cap holds (NEW 2026-08-06)**: 4-application rate ≤ `StackRatioMax` (3.5)
   × the single-stack rate — uncapped reads ~4.00× (measured) and fails.

## Advisory (logged, NOT gated)

- **Exact ~3× ratio**: the precise multiplier is logged; the two ratio gates
  already bound it to [2.0, 3.5], so pinning the exact value adds no verdict
  bits. (The 2026-06-16 "cap not reliably pinnable headless" advisory is
  RETIRED — congruent Leg A/Leg B rate windows cancel tick-count quantization,
  which was the actual source of the spread. See task.md's cap note.)

## Anti-gaming modes (defended by the gates)

1. Skip stage 1 (poison on a health-less pawn) → gate 0(b), probe-proven
   2026-08-05 (`no-health-system/`).
2. Dodge stage 1 by subclassing the generic scaffold pawn (pre-built set) →
   gate 0(a) derivation.
3. Register-but-never-init / inert-write fake → gates 0(c)/0(d).
4. No-GAS fake → (1)/(2).
5. Instant burst instead of periodic → (3) steps; permanent drain → (4)
   stop-check; no stacking → (7) lower bound; **no cap → (8)** (`no-cap/`);
   **no refresh → (5)** (`no-refresh/`); refresh-that-never-ends → (6).

## Bounded coverage

Reference (PASS) + empty (FAIL) + `no-health-system/` + `no-refresh/` +
`no-cap/` (each FAILing exactly its named gate) run through the deterministic
verifier; the remaining gaming variants are argued from the named gates, not
each run separately. Only the exact multiplier remains advisory (bounded by
the gated ratio band).

## Re-validate (post-epoch; the staged files ARE applied + committed — `a448869` → `c1e68fe` → `ca7f20c`, all 2026-08-06)

```sh
$env:CB_UE_ROOT='<UE-root>'
python tools/verify-single/run_task.py --task tasks/cpp/gp-poison-dot-stack-cpp/task.md `
    --submission tasks/cpp/gp-poison-dot-stack-cpp/reference --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task tasks/cpp/gp-poison-dot-stack-cpp/task.md `
    --submission tasks/cpp/gp-poison-dot-stack-cpp/discrimination/no-health-system --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task tasks/cpp/gp-poison-dot-stack-cpp/task.md `
    --submission tasks/cpp/gp-poison-dot-stack-cpp/discrimination/no-refresh --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task tasks/cpp/gp-poison-dot-stack-cpp/task.md `
    --submission tasks/cpp/gp-poison-dot-stack-cpp/discrimination/no-cap --substrate-from-live --ue-root $env:CB_UE_ROOT
```

Expected: reference **PASS**; no-health-system **FAIL** `stage 1 not built:
... health attribute system is absent`; no-refresh **FAIL** `re-application
did not refresh the duration`; no-cap **FAIL** `stack cap violated ...
4.00x`; empty **FAIL** at the derivation gate.

# -- DRAFT: to be APPENDED to tasks/cpp/gp-poison-dot-stack-cpp/discrimination/MATRIX.md --

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span is a contiguous `FinishTest(EFunctionalTestResult::Failed, ...)` literal in
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-poison-dot-stack-bp/PoisonStackFunctionalTest.cpp`
(the shared `-bp`-foldered fixture this `-cpp` task grades on), except the visibility
literals, which live in the shared base
`UE-projects/ThirdPerson/Source/CraftBenchTests/CraftBenchPawnFunctionalTest.cpp`
(`PawnVisiblyRepresented` fills the string the fixture passes verbatim to `FinishTest`);
the pawn-resolution literals `pawn did not spawn/resolve` and
`pawn has no AbilitySystemComponent` are the fixture's OWN `FinishTest` literals
(PoisonStackFunctionalTest.cpp:53/59).
This task's layers are **[L1, L2]** — there is no L2I grader on this lane (the 2026-08-11
correction in task.md: `gp_poison_dot_stack_bp.py` defines no `pawn_visibly_represented`
check either), so the fixture gates below plus the L1 build verdict are the ENTIRE gate set.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | deliverable compiles and the pawn resolves + possesses (C++ or Blueprint subclass, "with your ability granted") | fully, by the layer model | not a fixture literal — the L1 layer gates UBT exit 0 on BOTH the Editor and Game targets; in L2 the resolver (base class; the fixture's `PreferredAbilityTag` override returns Ability.Poison, PoisonStackFunctionalTest.cpp:19) must produce a pawn — `pawn did not spawn/resolve` / `pawn has no AbilitySystemComponent` | unconditional (these fire before every checkpoint body) | nothing; a BP-only submission skips no gate (L1 still builds the unchanged module, the resolver finds the BP pawn via the asset registry) |
| 2 | the pawn is a subclass of the provided TASK character, not the generic pre-built one | fully | stage-1 gate (a), cp0 — `does not derive from the provided task base` | pawn/ASC unresolvable (row 1) | class name, subclass depth, C++-vs-BP — all free; only the `ACraftBenchBareCharacter` lineage is checked |
| 3 | a **Health** attribute exposed through the ability system, using the attribute set type the project provides | fully | stage-1 gate (b), cp0 — `the pawn's health attribute system is absent` (`HasAttributeSetForAttribute` on the CONTRACT attribute, so a custom attribute-set type fails here too) | row 2 fires first (cp0 gates are strictly sequenced (a)->(e); any FinishTest ends the test) | extra attribute sets / extra attributes tolerated; MaxHealth and Power initialization never checked |
| 4 | Health **initialized to 100** | fully | stage-1 gate (c), cp0, read BEFORE any fixture write — `stage 1 incomplete: Health must initialize to` | rows 2-3 | init anywhere in 100±0.5 (`BaselineEpsilon`) |
| 5 | Health **readable AND writable** through the standard attribute APIs | fully | stage-1 gate (d), cp0 — write-probe at 37 (!=100, so an inert set that inits at 100 cannot pass vacuously) — `health attribute is inert, write-then-read failed` | rows 2-4 | only `SetNumericAttributeBase` at one value (37) is probed; clamps/side-effects that leave the read-back within 37±0.5 are invisible |
| 6 | the character is **visibly represented** (a reviewer watching the run can see it) | fully | stage-1 gate (e), cp0, base-class helper — `no mesh component with an assigned mesh on the graded pawn` (hidden/zero-scale branches: `every one is HIDDEN IN GAME`, "scaled to ~zero") — since 2026-08-11 the mesh must also RENDER (visible, not bHiddenInGame, scale > 0.01) | rows 2-5 | any visible mesh of any size — a 1 cm static cube passes (base-class doc: size floor deliberately not invented) |
| 7 | ...specifically "assign one of the provided mannequin skeletal meshes (under `/Game/Characters/`)" | **NOT ASSERTED** | none — `PawnVisiblyRepresented` deliberately asserts no asset path, no skeletal-vs-static type, no size (documented in the base-class header as a design decision) | — | a submission satisfies the gate with ANY mesh from ANY path — the prompt's mannequin clause is guidance the verifier never reads |
| 8 | the ability is **tagged `Ability.Poison`** and sits in the pawn's granted abilities | fully | final asserts (cp15) — `no activatable ability tagged Ability.Poison on the pawn` (fires when `Granted < 1`, cpp:234, where Granted = `NumGrantedAbilitiesWithTag(PoisonTag)`, cpp:212) | any cp0 gate fired (test already ended); a run that never reaches cp15 times out to FAIL without this literal | extra abilities / extra tags fine; the tag must be the asset tag GAS reads, but where it is granted from is free |
| 9 | poison is **applied by that tag** (activation works) | fully | final asserts — `did NOT activate on TryActivateAbilitiesByTag` (`bAbilityActivated`, set by the base on any successful tag-trigger) | row 8 fires first (final asserts are strictly sequenced; each FinishTest skips the rest) | an ability that activates but applies nothing dies at row 10 instead — activation itself carries no behavior check |
| 10 | Health lost **repeatedly** — "not a single hit" | fully | Leg A periodic gate — `poison was not periodic: Health did not keep dropping in steps` (A1>A2>A3 with each step >= `PeriodicMinStep` 2.0, samples at trigger+1.1/2.6/4.1) | rows 8-9 | any tick pattern that drops >= 2.0 in each ~1.5 s sample window — burst pairs, uneven magnitudes, near-continuous drains all pass |
| 11 | ..."about once per second" (the tick cadence) | **NOT ASSERTED** | none — no period bound exists anywhere in the fixture (MATRIX, permanent-drain block: "no period bound is enforced anywhere"); the periodic gate bounds per-window DROP, not tick period | — | a 0.1 s near-continuous drain or a ~1.4 s period both pass identically; only periods > ~1.5 s risk failing row 10 by missing a sample window |
| 12 | drains "for roughly five seconds" | partially (band) | Leg A stop gate — `poison did not STOP after its duration` — the acceptance band is ~4-7 s: still stepping at trigger+4.1 (row 10's last sample) AND silent in the stop window (trigger+7.1, trigger+9.2], drop <= `StopEpsilon` 2.5 | rows 8-10 | any duration inside ~4-7 s (deliberate, disclosed band; ~1 tick granularity above the top) |
| 13 | "then stops (not ... a drain that never ends)" | partially — **documented unsound at Leg A** | same Leg A stop token, plus Leg C's `refreshed poison never expired` as the incidental backstop | rows 8-10; the Leg C backstop additionally requires rows 14-15's leg to run | **the measured hole (MATRIX, 2026-08-08)**: at period > 1.05 s only ONE tick lands in the 2.1 s stop window, so a permanent drain can leave a drop <= 2.5 and PASS Leg A (measured: 2.3 vs the 2.5 bar, `permanent-drain/`). The task still FAILs it only via cross-leg Infinite-GE stack accumulation into the Leg C refreshed-stop gate — incidental, not designed (Q5 work order: the internal design note (not shipped)) |
| 14 | "each new application **refreshes the duration**" — ~5 s from the most recent application | fully, at one probe point | Leg C direction 1 — `re-application did not refresh the duration` (re-apply at trigger+3.6; drop across (CStart+7.2, CStart+8.7] — past the un-refreshed band top — must be >= `RefreshMinStep` 2.0) | rows 8-13 (any earlier final-assert FinishTest) | refresh is probed at ONE phase only; a policy that extends by a fixed +5 s rather than resetting from "most recent" is indistinguishable inside the bands |
| 15 | the refreshed poison still expires (~5 s from the LAST application, not forever) | fully | Leg C direction 2 — `refreshed poison never expired` (silent in (re-apply+7.1, re-apply+9.2], drop <= `StopEpsilon` 2.5) | rows 8-14 | the same ~4-7 s band latitude as row 12 |
| 16 | more active stacks drain **proportionally faster** ("three stacks ~= three times" the 1-stack loss) | partially (lower bound) | Leg B — `stacking did not scale the drain rate` (4-application rate / 1-stack rate >= `StackRatioMin` 2.0; congruent (trigger, trigger+4.1] windows cancel tick quantization) | rows 8-15 | scaling anywhere in [2.0x, 3.5x] passes — "~= three times" is tolerated down to 2.0x; sub-proportional per-stack rates pass if the aggregate lands in band |
| 17 | "a fourth application must **not** exceed three stacks" (the cap) | partially (ratio proxy) | Leg D — `stack cap violated (or scaling is not ~proportional)` (same ratio <= `StackRatioMax` 3.5; uncapped measured 4.00x, capped reference 3.00x) | rows 8-16 (last gate in the chain) | the stack COUNT is never read — any mechanism landing the 4-vs-1 ratio in [2.0, 3.5] reads as "capped" (e.g. a cap of 4 with ~0.85x per-stack scaling) |
| 18 | "each application **adds a stack** (up to 3)" — the per-application increment | **NOT ASSERTED** individually | none — only the 1-application and 4-application endpoints are ever rate-measured (Legs A and B/D); no 2- or 3-application rate is sampled (Leg C's 2-stack drain is logged, not gated) | — | a GE that jumps straight to the 3-stack rate on the second application, or increments unevenly, is indistinguishable from per-application stacking |

### Sequencing note (reads as the "skipped when" column's key)

Checkpoint-0 gates fire strictly in order (a) derivation -> (b) presence -> (c) init ->
(d) writability -> (e) visibility; any `FinishTest` ends the test, so everything after it
is skipped — including all sixteen checkpoints and the whole final-assert chain. The
final asserts (cp15) are likewise strictly sequenced: granted -> activated -> periodic ->
Leg A stop -> Leg C refresh -> Leg C refreshed-stop -> Leg B min -> Leg D max. A test
that never reaches cp15 (crash, hang) FAILs on the base class's `TimeLimit` (an
`AFunctionalTest` member set in the shared `CraftBenchFunctionalTest.h`/`.cpp`, not in
either file named in the preamble), with no
named literal — that shape is a harness/timeout FAIL, never credited to a gate.

### Holes this table found (escalation list)

1. **Row 7 — the mannequin clause is prompt-only.** The visibility gate accepts any
   rendering mesh; the "one of the provided mannequin skeletal meshes (under
   `/Game/Characters/`)" sentence is never asserted. Deliberate per the base-class
   header (path/type/size explicitly waived) — but the prompt still promises it, so
   either the prompt softens to "a visible mesh (the mannequins are provided)" or the
   residual is accepted in writing here.
2. **Row 11 — the ~1 s cadence is unasserted.** No period bound exists anywhere; this is
   also the enabling condition for the row-13 unsoundness (a >1.05 s period is what slips
   the Leg A stop window). One bound would close both.
3. **Row 13 — the Leg A stop gate is unsound in isolation** (measured 2026-08-08,
   `permanent-drain/` PASSed Leg A at 2.3 vs 2.5): the defense against a never-ending
   drain currently rests on undocumented cross-leg stack persistence into Leg C. Already
   escalated — the Q5 work order (the internal design note (not shipped)).
4. **Row 18 — per-application stack increments are never observed** (endpoints only).
   Accepted-residual candidate: the congruent-window ratio design is what makes the cap
   pinnable at all, and a 2-/3-application leg would add ~10 s of schedule for one
   low-value bit — but it should be accepted in writing, not by silence.
