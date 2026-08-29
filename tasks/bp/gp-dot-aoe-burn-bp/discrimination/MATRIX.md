# gp-dot-aoe-burn-bp -- discrimination matrix

> ## STATUS: **MEASURED 2026-08-11 - `cb discriminate` = YES, 5/5 legs, first sweep.**
>
> Reference **PASS**; `empty`, `never-stops`, `global-burn` and `cpp-solve`
> each **FAIL credited at its named substring**. Run was `substrate=live` (the
> package was uncommitted at sweep time - `decide_from_live` flips to `HEAD`
> once committed; re-run then for the certified verdict). The reference had
> already passed standalone on its FIRST grade (L2 1/1 + L2I 5/5), reproducing
> the `-cpp` original's numbers on every shared bar. Nothing in this file is a
> prediction.

> ## MATRIX LAYOUT LAW (read before editing this file)
>
> `aura_rig.discriminate.parse_matrix` keys rows by their **FIRST CELL** and
> **LAST ROW WINS across every markdown table in the file**. A later table
> repeating a leg name silently re-registers it -- with an empty substring
> tuple if that table has no message column -- and `cb discriminate` then
> credits the leg on its exit code alone. That has happened twice in this repo.
>
> **There is exactly ONE markdown table in this file: the `## Matrix` table.**
> Everything else is a bullet list on purpose. Do not add a second table, and do
> not put a leg name or any string containing a `/` in a first column anywhere
> else.

---

## Why this package is five legs and not seven

Authored under the **minimal-leg policy**
(`docs/TASK-AUTHOR-GUIDE.md` section 7 second amendment, owner vote
2026-08-11):

- `reference` + `empty` -- automatic, cost nothing.
- `never-stops/` -- attacks **AB-5**, a hand-calibrated bar (`StopEpsilon`).
- `global-burn/` -- attacks **AB-4**, this family's novel axis.
- `cpp-solve/` -- the ONE axis with a MEASURED false PASS
  (`gp-glide-stamina-bp` 2026-08-03: a C++ solve passed a Blueprint task with
  every gate green until `resolved_pawn_is_blueprint` existed). On a `-bp`
  twin this leg IS the variant's reason to exist.
- **NOT authored:** `no-mesh` (family-standard re-proof, proven at family
  level by 9/9 recorded glide reps shipping meshless pawns) and
  `cpp-solve-with-bp` (sibling-proven four times over -- glide measured, then
  the three 2026-08-11 twins; the policy bans duplicate cheat legs).

`cpp-solve/` is the `-cpp` reference's C++ **verbatim** (4 files), so L2 is
expected to PASS on it -- that is the point -- and only L2I separates it.
Both behavioural attackers are the `-cpp` reference with **one deletion**.

## Matrix

Each "Expected message" cell carries exactly one backticked literal.

| Submission | Overall | Fails at | Expected message | Status |
| `../reference` | **PASS** | -- | all gates green | **MEASURED PASS 2026-08-11**, first grade: L2 1/1 + L2I 5/5, `meanRate=6.10 total=30.00 stopDrop=0.00 farMaxDev=0.00` |
| empty (no overlay -> generic scaffold pawn) | **FAIL** | L2 cp0, AB-7 visibility | `no mesh component with an assigned mesh on the graded pawn` | AB-7 runs at checkpoint 0, BEFORE the trigger, and the generic scaffold pawn ships no assigned mesh -- so the run never reaches the tag gate. MEASURED on the `-cpp` half, whose empty leg is byte-identical in behaviour |
| `never-stops/` | **FAIL** | L2 final, AB-5 | `the burn never expired` | one deletion: the duration check. MEASURED credited on the `-cpp` half |
| `global-burn/` | **FAIL** | L2 final, AB-4 | `the burn is not an AREA effect` | one deletion: the distance test. MEASURED credited on the `-cpp` half |
| `cpp-solve/` | **FAIL** | L2I `bp_pawn_present` | `"id": "bp_pawn_present", "passed": false` | the `-cpp` reference verbatim. L2 is expected to PASS -- that is what isolates the deliverable-format axis. `task_folder_exists` also reports false on the same run; both appear in the verdict block |

## Calibration record (measured, not predicted)

- **Reference, 2026-08-11, first grade:** `N0=100.0 N1=90 N2=85 N3=75
  NStop=70 NTail=70`, `D1=10.00 D2=5.00 D3=10.00`, `meanRate=6.10`,
  `total=30.00`, `stopDrop=0.00`, `farMaxDev=0.00`, control `100 -> 80`.
  Overall **PASS** (L2 + L2I 5/5).

**The `-cpp` and `-bp` references agree on every gated number and differ on an
ungated one, which is the whole point of a twin.** The C++ solve burns
synchronously inside `ActivateAbility`, so checkpoint 0 already reads 95; the
Blueprint drives its periodicity from the GameplayEffect, so cp0 reads 100 and
the first step lands in D1 instead (`D1=10.00` here against `5.00` there).
Both shapes pass because AB-2 is a pure direction predicate and AB-3 is a MEAN
over the whole span. Under the per-window band this file's `-cpp` sibling
started with, this twin's D1 divergence would have been one more phase-driven
false FAIL -- the same defect class, caught a second time by a second
conforming implementation.

## Two genuinely different implementations of the same contract

Worth recording, because it is the evidence a `-cpp`/`-bp` pair exists to
produce:

- **periodicity** -- `-cpp`: a 1.0 s looping `FTimerManager` timer;
  `-bp`: the GameplayEffect's own `Period`.
- **spatial filter** -- `-cpp`: `GetAllActorsOfClass` plus a per-actor
  `FVector::Dist` test; `-bp`: `SphereOverlapActors` (Pawn object type, class
  filter).
- **application** -- `-cpp`: `SetNumericAttributeBase` per target; `-bp`: one
  batched `ApplyGameplayEffectSpecToTarget` over target data.
- **stop** -- `-cpp`: a tick counter calling `EndAbility`; `-bp`: the effect's
  `Duration`.

_(A bullet list, not a table, on purpose: see the LAYOUT LAW above. This
section previously WAS a second table, contradicting the law it sits under,
and was harmless only because no cell happened to contain a `/`.)_

Same `farMaxDev=0.00`, same `total=30.00`, same `meanRate=6.10`.

The Blueprint half was forced into the better design by a tool limit:
`ForEachLoop` is not reachable through the MCP node API (the macro library
enumerates empty), so the loop-and-distance-test shape was unavailable. The
loop-free result is 11 nodes with no timer, no counter and no manual distance
math -- more idiomatic GAS than the C++ original it mirrors.

## Re-validate

```sh
cb discriminate --task gp-dot-aoe-burn-bp
```

## Parser self-check

Parsed with `aura_rig.discriminate.parse_matrix` before commit: **5 rows** --
`reference` (`expect_pass=True`, empty substring tuple), `empty`,
`never-stops`, `global-burn`, `cpp-solve` (each `expect_pass=False`, exactly
one substring). No row blank, none shadowed. Re-run that check after any edit.

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked L2 span is a contiguous `FinishTest(EFunctionalTestResult::Failed, ...)` literal in
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-dot-aoe-burn/AoeBurnFunctionalTest.cpp`
(row 13's cp0 string comes verbatim from the shared base `CraftBenchTests/CraftBenchPawnFunctionalTest.cpp`, passed through unwrapped);
every L2I token is a check-id string emitted by `tools/verify-single/introspect/gp_dot_aoe_burn_bp.py` via `_bp_variant_lib.py::run_checks` (all five emit on EVERY leg — none is ever skipped).
NB: the FIXTURE is the source of truth and has moved past the task.md prose — since 2026-08-15 D1 is EVIDENCE ONLY (only D2/D3 gate), the in-band checkpoints are 1.87/3.24 (three equal 1.37 s windows), and a fourth 700 uu edge target is sampled but never gated; this table reads from the fixture.

L2 gate order: AB-7 fires at checkpoint 0 (preceded inside cp0 only by the two `[HARNESS]` preconditions, target-spawn then control-drain build), and an AB-7 FAIL FinishTests the run — so it temporally preempts EVERY final-checkpoint gate; every other gate evaluates at the final checkpoint (9.7 s) in PIN order AB-0 → AB-6 with early return, so "gate skipped when" for an ABn row means AB-7 (cp0) or any earlier AB fired first. The `[HARNESS]`-prefixed strings (spawn failure, control-drain build failure, AB-0) can never grade the agent and appear in no row below.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | ability activatable by the game through the character's ability system, tagged `Ability.AoeBurn`, added to granted abilities | fully | L2 AB-1 — `no activatable ability tagged Ability.AoeBurn on the pawn` (requires >= 1 granted ability with the tag AND activations == trigger attempts, 1 of 1) | AB-7 (cp0) or AB-0 fired first | the tag may sit on the ability any way GAS honors; cost/cooldown free (the fixture triggers exactly once) |
| 2 | a burning area appears at the character's location when activated | partially | no gate reads the area's origin — enforced only geometrically: the near target 300 uu from the pawn's spawn must burn, else L2 AB-2 `the burn was not periodic: the character inside the area did not keep` (or AB-6) fires | AB-7 (cp0) or AB-0/AB-1 fired first | an area centered anywhere that still covers a point 300 uu from the pawn spawn and misses one 1500 uu away — e.g. centered ON the near target — passes |
| 3 | characters inside lose Health repeatedly, about once per second | partially | L2 AB-2 — `the burn was not periodic: the character inside the area did not keep` (pure direction + noise floor: D2 > 0.5 AND D3 > 0.5 over the two 1.37 s windows; D1 is evidence only since 2026-08-15) | AB-7 (cp0) or AB-0/AB-1 fired first | the "once per second" cadence itself is ungated: anything from a continuous smooth drain to a ~1.37 s period passes, provided each gated window moves > 0.5 |
| 4 | steps of roughly equal size | **NOT ASSERTED** | none — AB-2 is deliberately a direction-plus-noise-floor predicate only (equal-duration windows hold unequal tick counts from phase alone; measured D1=5 D2=5 D3=10 on the conforming reference, 2026-08-11) | — | wildly unequal steps (e.g. 1 HP then 20 HP) pass, as long as each gated window moves > 0.5 and the mean-rate and total bands hold |
| 5 | characters outside the area are not affected at all | fully, per-CHECKPOINT | L2 AB-4 — `the burn is not an AREA effect` (FarMaxDeviation <= 0.5, tracked at EVERY checkpoint — a burn-then-restore cannot hide) | AB-7 (cp0) or AB-0..AB-3 fired first | deviation under the 0.5 noise floor; and "outside" is only proven at 1500 uu — a burn covering everything within 1500 uu passes (the 700 uu edge target is sampled but NEVER gated) |
| 6 | the area lasts a set duration then stops burning; 4–7 s accepted | partially | L2 AB-5 — `the burn never expired` (NStop − NTail <= StopEpsilon 0.25 over the 7.6–9.7 s stop window) | AB-7 (cp0) or AB-0..AB-4 fired first | only the STOP half is gated: the enforced stop window opens at trigger+7.1 s, so durations up to ~7.1 s pass; the 4 s floor is only indirect (AB-2's D3 window forces ticking to ~trigger+2.8 s; AB-6's 12.0 floor) — a ~3 s burn can pass; a residual drip <= 0.25 in the stop window passes |
| 7 | rate three to fifteen Health per second per character inside | partially | L2 AB-3 — `the burn rate is outside the stated band` (MEAN over the fixed 4.1 s in-band span) | AB-7 (cp0) or AB-0..AB-2 fired first | the enforced band is deliberately 2.0–20.0 (phase costs ±1 tick in ~5): a mean of 2.5/s or 18/s passes despite the disclosed 3–15; per-window rate spikes are unbounded by design |
| 8 | total twelve to about a hundred Health over one activation | fully | L2 AB-6 — `the total burn is outside the stated band` (12.0 <= preset − NTail <= 105.0; top DERIVED 15×7) | AB-7 (cp0) or AB-0..AB-5 fired first | nothing beyond the band's own disclosed width |
| 9 | the playable character is a Blueprint asset under `Content/Tasks/gp-dot-aoe-burn-bp/` | fully | L2I — `task_folder_exists` (`/Game/Tasks/gp-dot-aoe-burn-bp/` exists, >= 1 asset) + `bp_pawn_present` (a Blueprint THERE whose GeneratedClass derives from `ACraftBenchCharacter`; graded candidate = the one satisfying both downstream gates) | never — all five L2I checks emit on every leg | asset NAMES are free (identity is path + derivation); extra junk assets in the folder are free |
| 10 | the ability is a Blueprint asset (with the character, "both Blueprint assets") under the task folder | partially | L2I — `bp_pawn_grants_bp_ability` (>= 1 Blueprint-generated class in `GrantedAbilities` AND zero native `/Script/` entries) | auto-fails `no BP pawn resolved` when row 9's pawn is absent | the ability asset's LOCATION is unscoped — `granted_ability_paths` only splits `/Game/` vs `/Script/`, so a BP ability (and its GameplayEffect) authored anywhere asset-writable, e.g. `/Game/Blueprints/`, passes despite the prompt's "under `Content/Tasks/gp-dot-aoe-burn-bp/`" |
| 11 | **Write no C++** | partially | L2I — `resolved_pawn_is_blueprint` (native-subclass sweep of the scaffold root, git-HEAD exemptions, fail-closed on an empty sweep) plus row 10's zero-native-abilities rule | never (emits on every leg); the sweep fails CLOSED if it cannot see the scaffold class | C++ that is neither a character subclass nor a granted ability — e.g. a C++ helper actor the thin BP ability spawns to do the burning, or a static function library — compiles in the agent-writable `Source/ThirdPerson/` and passes both checks |
| 12 | Health is the attribute on the provided attribute set | fully, by construction | the fixture reads its OWN targets via `UCraftBenchAttributeSet::GetHealthAttribute()` — damage routed to any other attribute never moves a reading and dies at AB-2's `the burn was not periodic: the character inside the area did not keep` | AB-7 (cp0) or AB-0/AB-1 fired first | nothing — the reading IS the contract attribute; touching other attributes alongside Health is ungated |
| 13 | visibly represented — one of the provided mannequin skeletal meshes (under `/Game/Characters/`) | fully, in two layers | L2 AB-7 at cp0 — `no mesh component with an assigned mesh on the graded pawn` (shared-base `PawnVisiblyRepresented`, passed through verbatim); L2I — `pawn_visibly_represented` (assigned SkeletalMesh whose path starts with the `/Game/Characters/` pool prefix) | AB-7: only the two `[HARNESS]` cp0 preconditions precede it — target-spawn, then control-drain build (cpp lines 110/134); L2I: never | L2 alone accepts ANY assigned, visible, real-scale mesh (even a cube) — the mannequin-pool pin lives ONLY in L2I; which mannequin, transform and animation are free |
| 14 | the area reaches about **five meters** from where it appeared | partially — bracketed, never measured | no gate reads a radius; the reach is only BRACKETED: L2 AB-2 `the burn was not periodic: the character inside the area did not keep` forces the area to reach the near target at 300 uu, and L2 AB-4 `the burn is not an AREA effect` forces it NOT to reach the far target at 1500 uu; the fourth target at 700 uu (just outside a literal 5 m) is sampled at every checkpoint and printed in the AOEBURN-FINAL evidence line as EVIDENCE-ONLY, never gated (owner decision 2026-08-15, fixture header) | AB-2 half: AB-7 (cp0) or AB-0/AB-1 fired first; AB-4 half: AB-7 (cp0) or AB-0..AB-3 fired first | any effective radius from just over 300 uu to just under 1500 uu passes — a 3.1 m area and a 14 m area both grade as "about five meters" |

Holes found by this table (escalation list, not papered over):

- **Row 4 (NOT ASSERTED):** step-size equality is ungated — deliberate (phase makes per-window tick counts unequal), but it is a prompt clause with no assertion.
- **Row 10:** the ability/GE asset placement is unscoped — a BP ability outside `Content/Tasks/gp-dot-aoe-burn-bp/` passes L2I despite the prompt's folder mandate.
- **Row 11:** "Write no C++" is only enforced at the two shapes with measured false PASSes; a non-pawn, non-granted C++ helper class in the writable module escapes both checks.
- **Row 14:** the ~5 m reach is bracketed (must cover 300 uu, must miss 1500 uu) but never measured — deliberate per the fixture header (gating the 700 uu edge target would let a reading of "about" decide a verdict; it stays evidence-only until logs show real over-radius solves passing), but it is a prompt clause whose literal figure no gate reads.
- **Spec drift (not a row):** `task.md`'s Verifier specification still prints the pre-2026-08-15 fixture (checkpoints 1.6/3.1, "AB-2: D1, D2, D3 each > StepEpsilon", no edge target) — the shipped fixture gates D2/D3 only, at 1.87/3.24, with a never-gated 700 uu edge sample.
