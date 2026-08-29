# gp-glide-stamina-cpp — discrimination matrix

> **Rename + visibility epoch 2026-08-06 (owner decision).** The task id
> changed `gp-glide-stamina` → `gp-glide-stamina-cpp` (surface
> differentiation from the `-bp` twin; set stays `bp-g2`), and the shared
> fixture gained the **checkpoint-0 visible-character gate** ("the character
> is not visibly represented: no mesh component with an assigned mesh on the
> graded pawn"); the reference now constructor-assigns the mannequin mesh
> (`/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple`). Matrix rows below
> that pre-date this epoch were run under the old id and without the
> visibility gate. Re-run at this epoch on Windows / UE 5.8,
> `--substrate-from-live`, 2026-08-06: `../reference` **PASS** with the
> mannequin visible (`granted=1 activated=1 freefall=1208.7 minglide=181.7
> minpower=0.0 drained=1 exhausted=1 lastspeed=1651.7`; `exhausted_at=2.70s`,
> `window=1.40s` — physics identical to the pre-epoch run, the mesh perturbs
> nothing); the **meshless probe** (the reference minus the mesh ctor)
> **FAIL**s at the new named gate. **Empty-row change at this epoch:** an
> empty submission resolves to the meshless base scaffold pawn, and the
> checkpoint-0 visibility gate fires BEFORE the last-checkpoint GAS gates —
> so empty now FAILs at "the character is not visibly represented: ..."
> (measured 2026-08-06) instead of the historical `granted=0`. Both are
> named, deterministic FAILs; the row below records the current one.

> **Substrate epoch 2026-08-06 evening — re-validated on ThirdPerson.** The
> task moved to the `ThirdPerson` substrate (C++-pair migration; see task.md's
> substrate epoch note); the reference overlay now lives under a
> `Source/ThirdPerson/` prefix (byte-identical files). Re-run through the
> deterministic verifier on Windows / UE 5.8, `--substrate-from-live`,
> 2026-08-06 evening: `../reference` **PASS** (`granted=1 activated=1
> freefall=1208.7 minglide=181.7 minpower=0.0 drained=1 exhausted=1
> lastspeed=1651.7`; `exhausted_at=2.70s`, post-exhaustion `window=1.40s` —
> the 2026-08-06 window-honest correction holds on this substrate); empty
> **FAIL** at the named gate (`no activatable ability tagged Ability.Glide on
> the pawn (GAS not implemented). granted=0`). The measured table below is
> the CraftBenchTemplate-era calibration source; the thresholds it pinned are
> unchanged and re-confirmed by the ThirdPerson reference run (its
> lastspeed=1651.7 vs the table's ≈770 reflects only the two checkpoints the
> 2026-08-06 schedule appended, not a physics delta.)

> **VARIANT PACKAGE 2026-08-08 (this task shipped ZERO committed variants
> until now) — ALL FIVE NEW ROWS ARE NOW VALIDATED (run 2026-08-08, Windows /
> UE 5.8, `run_task.py --substrate-from-live`).** Full matrix measured:
> `reference` **PASS**; `empty` **FAIL**; and all five variants **FAIL, each
> via its own named substring** — `no-gas` (granted=0), `no-slow`
> (minglide=1600.7 > 725), `no-drain` (Power did not drain), `no-stop`
> (exhausted but no speed-up in a 1.40s window), `no-mesh` (not visibly
> represented). Reference PASS + empty FAIL + one attributable named FAIL per
> anti-gaming note is the acceptance gate in `TASK-AUTHOR-GUIDE.md` §B, and it
> now holds for this task for the first time. One honest caveat recorded below:
> `empty` and `no-mesh` land on the SAME substring (the checkpoint-0 visibility
> gate runs first and masks the ability check), so `no-mesh` proves the gate is
> reachable but adds no isolation beyond `empty`. This task
> declares 6 anti-gaming notes and, as the exemplar the bp-g2 scale-up copies,
> shipped only this MATRIX.md: half its bar was argued, not run. Five
> one-delta C++ overlays are now committed alongside, shaped exactly like
> `gp-poison-dot-stack-cpp/discrimination/` (each is the reference with
> **exactly one** file pair changed, and within that pair exactly one axis
> broken, so a FAIL is attributable):
> `no-gas/`, `no-slow/`, `no-drain/`, `no-stop/`, `no-mesh/`.
> **None of them has been compiled or run** — the authoring box had a live
> editor owned by another session, and `cb discriminate` needs UE. Every
> expected verdict/message below for those five rows is a PREDICTION derived
> from the fixture source
> (`Source/CraftBenchTests/Tasks/gp-glide-stamina-bp/GlideStaminaFunctionalTest.cpp`)
> plus the measured reference timeline; the exact commands that must be run to
> promote them from PREDICTED to MEASURED are in **Re-validate**, below.
> Anti-gaming note **5** is deliberately NOT a variant — it is recorded as an
> ARGUED/INHERITED entry in **Per-note coverage**, with the reason a sixth
> overlay would be a duplicate of `no-slow/`.

Validated on Windows / UE 5.7.4 (2026-06-19 — named-assertion recalibrated to the
exact `GlideStaminaFunctionalTest` failure string, was a stylized `…` placeholder).
Reference + empty were run empirically; the gaming rows are argued from the
fixture's named assertions (this is a GAS/trajectory **judgment-family** task —
the thresholds were calibrated from the measured reference run, below).

## Measured reference run (calibration source)

| t (s) | event | vZ (cm/s) | Power |
|---|---|---|---|
| 0.5–1.5 | free-fall | −327 → **−1300** (baseline @ trigger) | 100 |
| 1.5 | preset Power=30, fire Ability.Glide | — | 30 |
| 1.9–2.3 | gliding (clamped) | **≈ −182** | 18 → 6 |
| 2.5 | Power exhausted | — | 0 |
| 2.7–3.1 | fall resumes | −378 → **−770** | 0 |

`granted=1, activated=1, minGlide≈182 ≤ 0.6×1300=780, Power drained 30→0, lastSpeed≈770 ≥ 350`.

## Matrix

| Submission | Overall | Fails at | Expected message |
|---|---|---|---|
| `../reference` | **PASS** | — | all gates green (1/1) |
| empty (no overlay → base scaffold) | **FAIL** | checkpoint-0 visibility gate (since 2026-08-06; was (1) `granted=0` pre-epoch — the meshless base scaffold pawn trips the visibility gate first) | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` |
| `no-mesh/` (**NEW 2026-08-08**, promotion of the 2026-08-06 scratchpad meshless probe; note 6) | **FAIL** *(status: **VALIDATED 2026-08-08** as a committed dir, Windows / UE 5.8 — L1 pass, L2 fail by name)* | checkpoint-0 visibility gate | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` |
| `no-gas/` (**NEW 2026-08-08**; note 1) | **FAIL** *(status: **VALIDATED 2026-08-08**)* | last checkpoint, gate (1) | `no activatable ability tagged Ability.Glide on the pawn (GAS not implemented). granted=0` |
| `no-slow/` (**NEW 2026-08-08**; note 2) | **FAIL** *(status: **VALIDATED 2026-08-08**, Windows / UE 5.8)* | last checkpoint, gate (3) | `descent was not slowed by the glide: min glide` — **MEASURED**: `min glide \|vZ\|=1601 > 0.60 * free-fall(1209) = 725`; `[GLIDE-FINAL] granted=1 activated=1 freefall=1208.7 minglide=1600.7 drained=1 exhausted=1` (predicted ~1600, measured 1600.7) |
| `no-drain/` (**NEW 2026-08-08**; note 3) | **FAIL** *(status: **VALIDATED 2026-08-08**)* | last checkpoint, gate (4) | `the Power resource did not drain while gliding (the glide consumed no stamina)` |
| `no-stop/` (**NEW 2026-08-08**; note 4) | **FAIL** *(status: **VALIDATED 2026-08-08**)* | last checkpoint, gate (5) | **MEASURED**: `Power was exhausted (min=0.0) but the descent did NOT speed back up in a 1.40s observation window (>= the 0.30s floor)` |
| `no-power/` (**NEW 2026-08-09**; note 8) | **FAIL** *(status: **VALIDATED 2026-08-09**, Windows / UE 5.8 — L1 pass, L2 fail by name)* | checkpoint 1, pre-trigger starting-Power gate | `the pawn does not start with any Power to spend` — MEASURED (run nopower): the fixture reported Power=0.0 at t=1.00, before the glide, i.e. the gate fired at checkpoint 1 BEFORE the trigger's PowerPreset — which also proves it is not vacuous, the scaffold pawn really does start at 0. *Numbers deliberately OUTSIDE backticks: every backticked span in this column is a REQUIRED literal (ALL-of semantics), so a condensed summary in ticks can never match.* |
| `slow-no-stop/` (**NEW 2026-08-09**; note 7) | **FAIL** *(status: **VALIDATED 2026-08-09**, Windows / UE 5.8 — L1 pass, L2 fail by name)* | last checkpoint, gate (5), **after FORCED exhaustion** | `the descent did NOT speed back up in a` — MEASURED twice (runs slowleg / slowleg3, identical): GLIDE-FINAL minpower=0.0 drained=1 exhausted=1 **forced=1** lastspeed=181.7; RESUME-DIAG exhausted_at=3.60s window=0.50s mean_accel=0 cm/s^2; final vZ=182 = 1.00x the glide speed against a 1.5x bar (=273). *Only ONE backticked fragment on purpose: every backticked span in this column is a REQUIRED literal (ALL-of), so a condensed human summary in ticks can never match and reads as wrong-reason.* |

> `no-mesh/` and the `empty` leg share a substring, and that is not a
> duplicate: `empty` reaches the visibility gate incidentally (the base scaffold
> pawn is meshless AND grants nothing, so the gate it trips first is an accident
> of checkpoint order), whereas `no-mesh/` is a behaviorally PERFECT solve whose
> only defect is invisibility — it is the only leg that proves the visibility
> gate discriminates on the visibility axis alone. Among the five committed
> variants every substring is unique.

## ISOLATION CAVEAT — `no-stop/` and `slow-no-stop/` share one named FAIL

Recorded 2026-08-10 by the substring oracle
(`tools/verify-single/tests/test_matrix_substring_oracle.py`, check 2). The
fragment recorded for `slow-no-stop/` is a strict prefix of the one recorded for
`no-stop/`, so one log line satisfies both greps and the two rows do not isolate
*at the substring level*.

**It is irreducible, not sloppy.** `GlideStaminaFunctionalTest.cpp:360-368` holds
exactly ONE `FinishTest(EFunctionalTestResult::Failed, ...)` for gate (5); both
variants reach it, and since the 2026-08-09 forced-exhaustion change they are
*meant* to — making gate (5) unconditional is precisely what routed note 7's axis
into note 4's assertion. The only marker that differs is `forced=1`, which lives
in the `[GLIDE-FINAL]` **UE_LOG** (`:227`) and spans a `%d`, so it is not a
literal any grep can match verbatim.

**What still isolates them is the RUN, not the string.** Each is graded
separately and their `[GLIDE-FINAL]` lines differ (`forced=0` vs `forced=1`;
`minpower` above zero vs at zero). The collision costs nothing at grading time —
it only means the MATRIX cannot, by itself, prove the two axes are separately
defended.

The oracle carries a matching `_KNOWN_UNSOUND` entry citing this block. **If gate
(5) is ever split into two named assertions, delete that entry** — the ratchet
will then demand it, because the check will start passing on its own.

## Anti-gaming modes (defended by the named assertions)

1. **No GAS / permanent low-gravity pawn** → (1) `NumGrantedAbilitiesWithTag(Ability.Glide) >= 1` reads the ASC; (2) requires activation on the tag-trigger.
2. **Teleport / no actual slow** → (3) `min glide |vZ| ≤ 0.6 × free-fall(@trigger)`; an unchanged descent (≫ that) fails.
3. **Never drains stamina (free glide)** → (4) `Power < PowerAtTrigger`; a glide that consumes no Power fails.
4. **Glide forever, ignore stamina** → (5) CONDITIONAL: when Power reaches ~0, `|vZ|` must re-accelerate past ResumeVZ; a never-stopping glide fails. (Skipped — advisory — only if Power didn't exhaust in-window, so a correct slow-drainer is never false-failed.)
5. **Permanent fall-speed change (not resource-gated)** → (5) the verifier presets a small Power and checks the descent returns to fast once Power==0; a permanent change never speeds up. **See the correction in Per-note coverage below: the gate that actually catches this shape is (3), not (5).**
6. **Invisible deliverable (skip the visual entirely)** → checkpoint-0 visibility gate; the graded pawn must carry a skeletal/static mesh component with a mesh assigned.

## Per-note coverage (one committed variant per note, or an explicit ARGUED entry)

Every row states which of the fixture's 9 named FAIL substrings the delta is
expected to hit. **Substrings are unique per variant** — no two committed
variants die at the same gate.

| Anti-gaming note | Committed variant | Expected verdict | Named substring it must FAIL on | Status |
|---|---|---|---|---|
| 1. No GAS (slow the fall without an ability) | `no-gas/` | FAIL | `no activatable ability tagged Ability.Glide on the pawn (GAS not implemented). granted=` | **VALIDATED 2026-08-08** (L1 pass, L2 fail by name) |
| 2. Teleport / no actual slow | `no-slow/` | FAIL | `descent was not slowed by the glide: min glide` | **VALIDATED 2026-08-08** (L1 pass, L2 fail by name) |
| 3. Never drains stamina (free glide) | `no-drain/` | FAIL | `the Power resource did not drain while gliding (the glide consumed no stamina)` | **VALIDATED 2026-08-08** (L1 pass, L2 fail by name) |
| 4. Glide forever, ignore stamina | `no-stop/` | FAIL | `the descent did NOT speed back up in a` | **VALIDATED 2026-08-08** (L1 pass, L2 fail by name) |
| 5. Permanent fall-speed change (not resource-gated) | **none — ARGUED, see below** | (FAIL, at note 2's gate) | *(would duplicate* `descent was not slowed by the glide` *)* | ARGUED / INHERITED |
| 6. Invisible deliverable | `no-mesh/` | FAIL | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | **VALIDATED 2026-08-08** as a committed dir (L1 pass, L2 fail by name); shares its substring with the `empty` leg — see the caveat in the variant-package banner |
| 7. **Drain so slowly that Power never empties, and never implement the stop** | `slow-no-stop/` | FAIL | `the descent did NOT speed back up in a` | **VALIDATED 2026-08-09** (L1 pass, L2 fail by name). This was a LIVE HOLE for the whole life of the task: both of gate (5)'s skip paths key on "did Power empty in-window", and the drain rate is chosen by the submission — so a glide that ignores exhaustion passed provided it drained slowly. Measured on real runs: 1 of 4 `-cpp` PASSes never asserted the requirement (opus-5 `20260809-012802`, `minpower=4.2`). Closed 2026-08-09 by FORCED exhaustion (see note 8) |
| 8. Ship a pawn that never seeds the resource, and let the verifier's preset supply it | `no-power/` | FAIL | `the pawn does not start with any Power to spend` | **NEW 2026-08-09.** The prompt asks for a pawn "starting with some Power to spend" and nothing checked it: the fixture overwrites the value at the trigger (`PowerPreset`). Not vacuous — `UCraftBenchAttributeSet::Power` has no initializer and `ACraftBenchCharacter` never seeds it, so the scaffold pawn genuinely starts at 0 |

### Note 5 — ARGUED / INHERITED (no variant, on purpose)

A sixth overlay for note 5 would be **redundant**, and the lint rule's accepted
alternative (an explicit argued justification with a pointer to where the axis
IS proven) is used instead. The argument, from the fixture source:

- Gate (3) compares `MinGlideSpeed` against `SlowFactor * FreeFallSpeed`, where
  `FreeFallSpeed` is sampled **on the same pawn, in the same run, at the trigger
  checkpoint** (`GlideStaminaFunctionalTest.cpp`, the `CheckpointIndex ==
  TriggerCheckpoint` block). A *permanent* fall-speed change scales BOTH sides of
  that comparison, so it can never make the glide look 0.6x slower than its own
  baseline: under any constant acceleration the later sample is the FASTER one,
  so `MinGlideSpeed > 0.6 * FreeFallSpeed` and gate (3) fires. Under a permanent
  velocity CAP both readings are the cap, so `cap > 0.6 * cap` and gate (3) fires
  again.
- Therefore a genuine "permanent low-gravity / permanently capped fall" pawn dies
  at the SAME named substring as `no-slow/` (`descent was not slowed by the
  glide: ...`), never at gate (5). Committing it would ship two variants with one
  substring between them — which the discrimination contract treats as a
  duplicate, not as coverage.
- **Where the axis IS proven**: the "not permanent" half is proven by `no-stop/`
  (a slow that outlives the resource FAILs gate (5)) plus `no-slow/` (a slow that
  is not relative to the run's own baseline FAILs gate (3)). Between them the two
  committed variants close both directions of note 5.
- **Correction to the note as written in task.md**: note 5 claims its defense is
  gate (5). That is wrong in the reachability sense — gate (5) is only ever
  evaluated on a submission that already PASSED gate (3), i.e. one whose slow was
  genuinely relative to its own free-fall baseline. The gate that actually
  catches note 5's failure mode is **(3)**.

### The fixture's 9 named FAIL substrings, and which note each defends

Enumerated from every `FinishTest(EFunctionalTestResult::Failed, ...)` in
`Source/CraftBenchTests/Tasks/gp-glide-stamina-bp/GlideStaminaFunctionalTest.cpp`
(the two additional ones in the base class, `SpawnAndPossessPawn: no world` and
`SpawnAndPossessPawn: spawn of %s failed`, are harness conditions, not gates):

| # | Named substring | Fires at | Defends |
|---|---|---|---|
| 1 | `pawn did not spawn/resolve` | any checkpoint | **no note** — harness/resolution condition, not gameable |
| 2 | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | checkpoint 0 | note 6 (`no-mesh/`) |
| 3 | `no activatable ability tagged Ability.Glide on the pawn (GAS not implemented). granted=` | last cp, gate (1) | note 1 (`no-gas/`) |
| 4 | `an ability tagged Ability.Glide was granted but did NOT activate on TryActivateAbilitiesByTag` | last cp, gate (2) | note 1, second half — **no committed variant** (see holes below) |
| 5 | `no free-fall baseline: pawn was not descending fast pre-trigger` | last cp | **no note** — measurement-validity sanity check |
| 6 | `no gliding samples captured with Power>0 (ability never reduced descent before Power ran out)` | last cp | **no note** — see hole (b) below |
| 7 | `descent was not slowed by the glide: min glide` | last cp, gate (3) | notes 2 AND 5 (`no-slow/`) |
| 8 | `the Power resource did not drain while gliding (the glide consumed no stamina)` | last cp, gate (4) | note 3 (`no-drain/`) |
| 9 | `the descent did NOT speed back up in a` | last cp, gate (5) — **UNCONDITIONAL since 2026-08-09** (the verifier zeroes Power itself at checkpoint 6 once the submission has proven its own drain; previously CONDITIONAL on the drain emptying Power in-window, which the submission decided) | notes 4 (`no-stop/`) AND 7 (`slow-no-stop/`) |
| 10 | `the pawn does not start with any Power to spend` | checkpoint 1, pre-trigger | note 8 (`no-power/`) |

### Known holes (notes / prompt clauses with NO corresponding assertion)

- **(a) The "teleport" half of note 2 is UNDEFENDED.** Every gate reads
  `Pawn->GetVelocity().Z`; `RecordSample` stores Location but **no assertion ever
  compares displacement against velocity**. A submission that stops
  CharacterMovement and drives the descent by writing the actor's location
  directly reads `|vZ| ~ 0`, which SATISFIES gate (3), drains Power for gate (4),
  and re-accelerates for gate (5) — i.e. the prompt's explicit "not a teleport"
  clause would PASS. This cannot be expressed as a discrimination variant
  (a variant must FAIL); closing it needs a new fixture assertion, e.g. that the
  per-checkpoint dZ is consistent with the sampled vZ. Not fixed here — the
  fixture is verifier-owned.
- **(b) Substring 6 defends a gaming shape no note names**: an ability whose
  Power drain empties the resource before the first post-trigger sample (or which
  never reduces the descent while Power > 0) produces zero gliding samples. It is
  a real, deterministic gate with no anti-gaming note behind it.
- **(c) Substring 4 (gate 2, granted-but-never-activates) has no committed
  variant.** It is the second half of note 1's stated defense. A one-delta
  overlay for it is possible (e.g. an ability whose `CanActivateAbility` refuses),
  but it was not authored here — note 1 already has `no-gas/`, and this hole is
  recorded rather than silently filled.

## Substrate dependency

Relies on the **ability-aware pawn resolver** added to
`Source/CraftBenchTests/CraftBenchPawnFunctionalTest.cpp` (`PreferredAbilityTag()`),
which disambiguates pawn resolution when more than one `ACraftBenchCharacter`
subclass is committed (the launch pawn). This fix also **repaired** gp-flight-mode
(reference PASS confirmed post-fix), which was latently broken by the same
collision.

## Bounded coverage (honest note)

Reference (PASS) + empty (FAIL) were run through the deterministic verifier, as
was the 2026-08-06 scratchpad meshless probe whose delta `no-mesh/` now commits.
**The five committed variants of 2026-08-08 have NOT been compiled or run** —
their expected verdicts and messages are derived from the fixture source plus the
measured reference timeline, not observed. Do not cite them as measured
discrimination until the Re-validate block below has been run and this section
replaced with the results. The stop-on-exhaustion gate (5) is conditional
(drain-rate-robust and, since 2026-08-06, window-honest); `no-stop/` is the
variant that DOES exhaust Power and should therefore hard-FAIL it.

### Predicted mechanics behind each new row (what to check if a run disagrees)

Reference timeline for reference: trigger at checkpoint 2 (t=1.5s),
`freefall=1208.7`, `minglide=181.7`, Power preset 30 draining 3/tick every 0.1s
so it empties ~1.0s after the trigger, `exhausted_at=2.70s`, `window=1.40s`.

- `no-gas/` — gate (1) is the FIRST final assertion, so the verdict does not
  depend on any physics: `GrantedAbilities` is empty, `NumGrantedAbilitiesWithTag`
  returns 0. The permanent `GravityScale = 0.1f` only makes the submission the
  shape note 1 describes. **Resolution check**: with no candidate granting
  `Ability.Glide`, `PreferredAbilityTag()` finds nothing and the resolver falls
  back to `Candidates[0]`; the ThirdPerson substrate ships no other **concrete**
  native `ACraftBenchCharacter` subclass (`ACraftBenchBareCharacter` is
  `UCLASS(Abstract)` and is skipped), so `AGlidePawn` is still the graded pawn and
  the mesh keeps checkpoint 0 green. If a future task commits another concrete
  subclass into the substrate, re-check this row first.
- `no-slow/` — the ability activates and drains on schedule but never clamps
  velocity, so the gliding samples (t=1.9, 2.3) read an unaided fall of roughly
  1209 + 980*(t-1.5) ~ 1600-1990 cm/s against a 0.6 * 1209 = 725 bar. Margin is
  ~2.2x, far outside sampling jitter.
- `no-drain/` — Power is never written, so `bPowerDrained` stays false and
  `MinPowerSeen` stays 30. Gate (3) passes on the unchanged clamp, gate (4) fires.
  Gate (5) is never reached (and would have skipped anyway: `bExhausted` false).
- `no-stop/` — Power still reaches 0 at ~2.5s, so `ExhaustTime` = 2.7 and
  `window` = 4.1 - 2.7 = 1.40s, comfortably over the 0.30s `ResumeWindowFloor`,
  so gate (5) is ALLOWED to hard-FAIL. The clamp keeps running, and every
  post-trigger checkpoint sits a whole number of 0.1s timer periods past the 1.5s
  trigger (0.4/0.8/1.2/1.6/2.1/2.6), so the final sample reads the same clamped
  speed as the glide samples: ratio 1.00x against the 1.5x bar. If a run shows a
  ratio near 1.5x instead, suspect timer/checkpoint phase drift and read the
  `[GLIDE]` per-sample lines before touching the variant.
- `no-mesh/` — structural, no physics: the inherited ACharacter mesh component
  has no skeletal mesh asset, so checkpoint 0 fires before anything else.

**Grep note:** gate (5)'s message contains a non-ASCII em dash (U+2014) in the
fixture source (`... the glide speed (%.0f) — need %.1fx`). Match on the ASCII
prefix `the descent did NOT speed back up in a` only; do not grep across that
character.

## Re-validate (the commands that produced the 2026-08-08 measurements above)

Run on a box with UE 5.8 and **no other session holding the engine** (UBT's mutex
is keyed on the engine install; a contended build returns exit 1 with no compile
errors and would be misread as a variant failing L1).

```sh
$env:CB_UE_ROOT='<UE-root>'
# the reference must still PASS in the same sweep — it is the control
python tools/verify-single/run_task.py --task tasks/cpp/gp-glide-stamina-cpp/task.md `
    --submission tasks/cpp/gp-glide-stamina-cpp/reference --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task tasks/cpp/gp-glide-stamina-cpp/task.md `
    --submission tasks/cpp/gp-glide-stamina-cpp/discrimination/no-gas --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task tasks/cpp/gp-glide-stamina-cpp/task.md `
    --submission tasks/cpp/gp-glide-stamina-cpp/discrimination/no-slow --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task tasks/cpp/gp-glide-stamina-cpp/task.md `
    --submission tasks/cpp/gp-glide-stamina-cpp/discrimination/no-drain --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task tasks/cpp/gp-glide-stamina-cpp/task.md `
    --submission tasks/cpp/gp-glide-stamina-cpp/discrimination/no-stop --substrate-from-live --ue-root $env:CB_UE_ROOT
python tools/verify-single/run_task.py --task tasks/cpp/gp-glide-stamina-cpp/task.md `
    --submission tasks/cpp/gp-glide-stamina-cpp/discrimination/no-mesh --substrate-from-live --ue-root $env:CB_UE_ROOT
```

Expected: reference **PASS**; `no-gas` **FAIL** `... GAS not implemented.
granted=0`; `no-slow` **FAIL** `descent was not slowed by the glide`; `no-drain`
**FAIL** `the Power resource did not drain while gliding`; `no-stop` **FAIL**
`the descent did NOT speed back up in a`; `no-mesh` **FAIL** `the character is
not visibly represented`. **A variant that FAILs at a substring other than its
own is a mis-authored variant, not a discrimination win** — re-read the
`[GLIDE]` / `[GLIDE-FINAL]` lines before editing the fixture.

The equivalent single command, when the box is free and `cb` is preferred:

```sh
cb discriminate gp-glide-stamina-cpp
```

# DRAFT — to be appended to tasks/cpp/gp-glide-stamina-cpp/discrimination/MATRIX.md

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span is a contiguous `FinishTest(EFunctionalTestResult::Failed, ...)`
source literal in
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-glide-stamina-bp/GlideStaminaFunctionalTest.cpp`
(the fixture shared with the `-bp` twin — including row 1's
`pawn did not spawn/resolve`, the fixture's own literal at line 51; only the
resolution MACHINERY lives in the base class) or, for row 2's visibility literals
only, in the base class
`UE-projects/ThirdPerson/Source/CraftBenchTests/CraftBenchPawnFunctionalTest.cpp`
(the hoisted `PawnVisiblyRepresented` gate); thresholds quoted in
prose come from `GlideStaminaFunctionalTest.h` (SlowFactor=0.6, PowerPreset=30,
PowerEpsilon=0.5, ResumeFactor=1.5, ResumeWindowFloor=0.30 s, trigger at checkpoint 2
= t=1.5 s, forced exhaustion at checkpoint 6 = t=3.1 s, last checkpoint t=4.1 s).
The task's layers are `[L1, L2]` — every gate below is L2; there is no L2I grader.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | deliver the pawn as a subclass of the provided character (the verifier spawns it) | fully, by the resolution model | resolve gate — `pawn did not spawn/resolve` (re-checked at every checkpoint); resolution only ever considers `ACraftBenchCharacter` subclasses, so a non-subclass pawn can never become the graded pawn | unconditional (first check of every checkpoint) | committing extra helper subclasses is free — the ability-aware resolver (`PreferredAbilityTag()` = `Ability.Glide`) picks the one granting the glide tag; decoys are ignored, not failed |
| 2 | the character is visibly represented: assign one of the provided mannequin skeletal meshes (under `/Game/Characters/`) as the mesh | partially — a renderable mesh is asserted; the MANNEQUIN-SPECIFIC clause is **NOT ASSERTED** | checkpoint-0 visibility gate — `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` (sibling literals in the same base-class check catch a mesh that is `hidden in game` or `scaled to ~zero`) | row 1 | ANY skeletal/static mesh that would render satisfies the gate — a debug cube, not the prompt's mannequin; the asset path under `/Game/Characters/` is never read (a deliberate base-class non-assert, documented at `PawnVisiblyRepresented`) |
| 3 | the pawn starts with some Power to spend | fully (since 2026-08-09) | checkpoint-1 pre-trigger gate — `the pawn does not start with any Power to spend` (read at t=1.0 s, BEFORE the trigger's PowerPreset overwrite) | rows 1–2; also skipped when the pawn has NO ASC at all (`ASC != nullptr` guard — deliberate, so the no-GAS shape dies at row 4's named gate instead of a misleading Power message) | "some" = anything above PowerEpsilon (0.5): a pawn seeded with Power=1 passes; seeding any time before t=1.0 s counts as "starting with" |
| 4 | tag the ability `Ability.Glide` and add it to the pawn's granted abilities | fully | gate (1), last checkpoint — `no activatable ability tagged Ability.Glide on the pawn (GAS not implemented). granted=` (fires when `Granted < 1`, where `NumGrantedAbilitiesWithTag(GlideTag)` reads the live ASC) | rows 1–3 fire first | the granting ROUTE is free — the scaffold's `GrantedAbilities` array is the offered path but any code that gets a tagged, activatable ability onto the ASC passes (mechanism-agnostic by design) |
| 5 | the game can activate the glide by that tag (verifier fires the tag while falling) | fully | gate (2), last checkpoint — `an ability tagged Ability.Glide was granted but did NOT activate on TryActivateAbilitiesByTag` | rows 1–4 fire first | activation is demanded exactly once, on the verifier's tag-trigger at t=1.5 s; the original g2-10 spacebar/apex input-gating is dropped (documented Tier-B scope cut — headless PIE has no input) |
| 6 | while falling, descend noticeably slower than an unaided fall | fully, as a same-run ratio | gate (3), last checkpoint — `descent was not slowed by the glide: min glide` (min glide \|vZ\| must be <= 0.6 x the SAME run's free-fall \|vZ\| sampled at the trigger); prerequisite sanity: `no free-fall baseline: pawn was not descending fast pre-trigger` and `no gliding samples captured with Power>0 (ability never reduced descent before Power ran out)` | rows 1–5 fire first, and so does row 7's never-DESCENDING gate, which precedes gate (3) in source order (cpp:310 before cpp:326); the ratio is computable only if >= 1 descending sample with Power > 0 exists (else, when every Power>0 sample was non-descending, row 7's never-DESCENDING literal fires; otherwise the no-samples literal — either way still a FAIL, never a skip) | the bar is the MINIMUM over gliding samples: one slow checkpoint suffices even if the rest of the glide is fast; 0.6x is deliberately generous |
| 7 | the slow fall is a DESCENT — not hovering, rising, or holding the pawn up | fully for the all-samples shape | descending-sample sign gate (2026-08-11) — `the pawn was never DESCENDING while the ability was active` (fires when every post-trigger Power>0 sample had vZ >= 0; such samples are excluded from gate (3)'s minimum) | at least one Power>0 sample descends — then the non-descending samples are silently ignored, not failed | a pawn that hovers at most checkpoints but descends at ONE gets that one sample graded as its glide |
| 8 | steadily drains the Power resource while gliding | partially — a drain is asserted; "STEADILY" is **NOT ASSERTED** | gate (4), last checkpoint — `the Power resource did not drain while gliding (the glide consumed no stamina)` (`bPowerDrained` credits only the submission's OWN writes — samples after the verifier's forced zeroing never set it) | rows 1–7 fire first | one lump-sum decrement > 0.5 Power at any single post-trigger checkpoint passes; no gate reads drain RATE, monotonicity, or per-tick cadence |
| 9 | when Power reaches zero the slowed descent ends (falls at the normal rate again) | fully since 2026-08-09 (forced exhaustion) + 2026-08-11 (absolute fast path removed) — with two documented skip paths | gate (5), last checkpoint — `the descent did NOT speed back up` (contiguous within the cpp:409 literal; the following "in a %.2fs…" continues on the next source line) (final \|vZ\| must be >= 1.5x the run's own min glide speed; the verifier ZEROES Power itself at checkpoint 6 / t=3.1 s once the submission has proven its own drain, so the drain rate the submission chose no longer decides whether this gate runs) | rows 1–8 fire first (final-assert source order cpp:280→288→296→304→326→335→355); also (i) post-exhaustion window < the 0.30 s `ResumeWindowFloor` (Power emptied inside the schedule's final gap — SKIP, logged, same semantics as never-emptied); (ii) the drain never registered (> 0.5 below preset) by checkpoint 6, so exhaustion is never forced — logged as the `[GLIDE-ADVISORY]` not-gated line | a glide whose drain FIRST registers after t=3.1 s (between the forced-exhaust checkpoint and the t=4.1 s end) sets `bPowerDrained` — passing gate (4) — but is never force-exhausted, so stop-on-exhaustion goes ungated for that run (narrow: ~1 s window, and a drain that slow usually fails gate (4) outright) |
| 10 | the slow must not be a permanent change to fall speed | fully, by inheritance | gate (3)'s literal `descent was not slowed by the glide: min glide` — a permanent slow scales BOTH sides of the same-run ratio (baseline is sampled on the same pawn at the trigger), so it can never look 0.6x slower than itself; gate (5) then demands the clamp actually RELEASE after exhaustion | as rows 6 and 9 | effectively nothing — the per-note-coverage §Note 5 analysis: a permanent gravity change fails gate (3); a permanent velocity cap reads cap > 0.6 x cap and fails gate (3); one that somehow passed (3) still has to re-accelerate for (5) |
| 11 | the slow must not be a teleport | partially — the hover/zero-vZ half is caught by row 7; the DISPLACEMENT half is **NOT ASSERTED** | no displacement gate exists: `RecordSample` stores Location every checkpoint but NO assertion ever compares per-checkpoint dZ against the sampled vZ (MATRIX known hole (a), still open — closing it needs a new fixture assertion in the verifier-owned module) | — (there is nothing to skip) | drive the descent by writing the actor's location directly while pinning CharacterMovement velocity to a small NEGATIVE vZ: every velocity-reading gate sees a compliant slow descent, Power can be drained on a timer for gate (4), and releasing the location-writer after exhaustion satisfies gate (5) — the prompt's explicit "not a teleport" clause passes |

### NOT ASSERTED residuals (the holes this table found — escalation list)

- **Row 2 — the mannequin clause**: the gate demands A renderable mesh, not one of
  the provided `/Game/Characters/` mannequins. Deliberate at the base-class level
  (asset path/type/size explicitly not asserted), but the PROMPT names the
  mannequins specifically — either soften the prompt bullet or accept the gap
  knowingly.
- **Row 8 — "steadily"**: a single lump decrement > PowerEpsilon (0.5) at one
  checkpoint satisfies gate (4); drain rate and continuity are ungated.
- **Row 9 — late-registering drain**: a drain that first exceeds 0.5 only after the
  forced-exhaustion checkpoint (t=3.1 s) passes gate (4) yet is never force-zeroed,
  so gate (5) is skipped via the advisory path — the one remaining drain-rate-chosen
  escape from stop-on-exhaustion.
- **Row 11 — the teleport displacement half**: no gate cross-checks recorded
  Location deltas against sampled velocity, so a location-write descent with a
  spoofed slow negative CMC velocity passes every gate (matches the matrix's Known
  hole (a); the 2026-08-11 sign gate closed only the vZ >= 0 shapes).
