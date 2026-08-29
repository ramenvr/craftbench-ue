# PIN — gp-dot-aoe-burn (CSV 48) — family sheet for `-cpp` + `-bp`

**State: `PENDING-G1`.** Drafted 2026-08-11 after the tier-1.5 unlock condition
was met (V1.1 landed `fbb0e27`-era; tier-1 bands measured 2026-08-10/11).
Everything below follows the tier-1 laws: constants are **PROPOSED — NOT YET
MEASURED** until the calibration runs pin them; every absolute the fixture
enforces is disclosed in the prompt (§C / F5); rate-like gates prefer ratios of
same-run measurements; the stop bar obeys the `< 1.0 × step-floor` law that
corrected T1.2.

**First family authored under the minimal-leg policy** (§7 second amendment,
owner vote 2026-08-11): reference + empty + `cpp-solve` (`-bp` only) + at most
one attacker per hand-calibrated bar the requirements table shows unprobed.
Planned legs are listed in §6 — five for `-cpp`, six for `-bp`, not seven.

---

## 1. Source row and re-framing

> `Create a DoT AoE that burns enemies for a set duration, and update the
> rocket launcher projectile to spawn it on impact. Make use of GAS`

| source clause | graded contract | dropped? |
|---|---|---|
| "Create a DoT AoE that burns enemies" | An ability on the pawn that, when activated, creates a burning area at the pawn's location: characters inside it lose Health **repeatedly — about once per second — in equal steps**; characters outside it are untouched. | kept (the task) |
| "for a set duration" | The area stops burning after its duration; the prompt disclosed band is **4–7 s** (same window family as heal-over-time — deliberately congruent so the two families' stop machinery stays comparable). | kept |
| "update the rocket launcher projectile to spawn it on impact" | **DROPPED — Q3(a), the potion precedent** (`gp-heal-over-time-cpp/PIN.md` row 1): there is no rocket launcher in either substrate, and authoring one would put the Edit(Debug) lane on the critical path and commit a baseline weapon to git-default state. Re-framed from-scratch: the fixture activates the ability by tag, exactly like every tier-1 family. Recorded in `## Dropped clauses` of both task.md files. | dropped |
| "Make use of GAS" | Carried by the same contract language as tier-1 ("an ability the game can activate", the provided attribute set, a trigger tag) — **and this row's sheet text names GAS itself**, so the documented GAS-category exception applies with zero Hard-Rule-#2 pressure (the ledger row already notes this). | kept |

**Trigger tag:** `Ability.AoeBurn` (new accessor in `CraftBenchGameplayTags`,
same one-line pattern as `AbilityDoubleJump`; ships in the fixture commit —
the atomicity rule from T1.1 applies: tags + fixture + map + spec + any pawn
base change land in ONE commit or L1 breaks every ThirdPerson family).

## 2. What is genuinely NEW here (why this family earns its id)

Every tier-1 family measures the agent's effect on the agent's OWN pawn. This
is the first **world-acting** family: the deliverable's effect lands on OTHER
actors — and those targets are **verifier-owned** (spawned by the fixture,
carrying the contract `UCraftBenchAttributeSet` via the V1.1 route), so a
submission cannot pre-rig them. The novel graded axis is **spatial
selectivity**: same run, one target inside the area, one outside; inside burns,
outside must not move. No existing gate in the corpus tests "affects A, spares
B".

## 3. Fixture shape (derives `ACraftBenchPawnFunctionalTest`)

- Map `L_AoeBurn` (per-task folder convention, authored by the proven aids
  recipe; flat floor is fine — nothing here is motion-dependent).
- Fixture spawns the graded pawn (resolved by tag/derivation as ever), plus
  THREE verifier-owned targets:
  - `TargetNear` — inside the disclosed radius (prompt: "about five meters";
    placed at ~300 uu), Health preset 100.
  - `TargetFar` — well outside (placed at ~1500 uu), Health preset 100.
  - `TargetControl` — far from everything; the fixture applies its OWN V1.1
    `MakePeriodicAttributeDrain` (known rate/period) to it. This is the
    ledger's "control burn": it proves periodic GE execution works in THIS
    run's world before any gate judges the agent's periodicity (`baseline=ok`
    lane, same role as tier-1's baseline checks).
- Trigger `Ability.AoeBurn` once. Checkpoint schedule (PROPOSED):
  `{0.5, 1.6, 3.1, 4.6, 7.6, 9.7}` — trigger at 0.5; three 1.5 s congruent
  windows over the in-band burn; stop window `(t+7.1, t+9.2]` — reusing
  T1.2's measured-good spacing wholesale, since the disclosed duration band
  is identical.

## 4. Gate table (all constants PROPOSED until calibration)

| gate | rubric | window | FAIL string sketch | class |
|---|---|---|---|---|
| **AB-0** control burn ticked | fixture-owned drain moved TargetControl by the expected per-period amount | pre-final | (harness/baseline lane, not an agent gate — a dead control is a HARNESS-ERROR, never an agent FAIL) | baseline |
| **AB-1** ability granted + activated | tag present AND activation landed | final | `no activatable ability tagged Ability.AoeBurn on the pawn ...` | structural |
| **AB-2** near target burns in steps | N1/N2/N3 samples each drop by more than `StepEpsilon` (0.5) — pure direction + noise floor, NOT a rate bar | 3 congruent windows | `the burn was not periodic: TargetNear's Health did not keep falling in steps (N1=%.1f N2=%.1f N3=%.1f ...)` | shape |
| **AB-3** per-window magnitude in band | disclosed **3–15 per second-ish window** (wide on purpose; the sheet fixes nothing) | same windows | `the burn is outside the stated band ...` | absolute, disclosed |
| **AB-4** far target untouched | `|FarDelta| <= StepEpsilon` across the whole run | cp0 → final | `the burn is not an AREA effect: a character well outside the area lost %.1f Health` | **the novel axis** |
| **AB-5** burn stops after duration | near target flat in the stop window: `StopDrop <= 0.25` (the `< 1.0 × StepEpsilon` law, T1.2's corrected bound, adopted as-is) | stop window | `the burn never expired: TargetNear was still losing Health past the stated duration ...` | stop |
| **AB-6** total per application in band | disclosed **12–60 total** on TargetNear | preset → stop | `total burn outside the stated band ...` | absolute, disclosed |
| **AB-7** visible character | family standard (gate stays; the *variant* re-proof does not — minimal-leg policy) | cp0 | family string | structural |

**The passing-solve / plausible-wrong-solve pair (the mandatory concrete pair,
never a paraphrase):**

- **PASSES:** ability spawns an area actor at the pawn; on overlap/periodic
  scan it applies an infinite-period GE (`Period 1.0`, Health `AddBase -5`)
  to targets inside; destroys itself (or removes the GE) at `t+5.0`.
  Predicted trace: Near `100 → 95 → … → 75` (total 25, in band), Far `100.0`
  flat, stop window flat.
- **FAILS (plausibly wrong):** ability applies the SAME periodic GE directly
  to every `UCraftBenchAttributeSet` holder in the world (no spatial test —
  "AoE" read as "everyone"). Near burns identically, total in band, stops on
  time — **every gate green except AB-4**, which names it: the far target
  lost Health. This is the wrong-solve the family exists to catch, and it is
  exactly one `GetAllActors…` call away from the passing solve.

## 5. Calibration plan (BOTH boxes law + P1 lesson)

Reference `-cpp` AND `-bp` solves are built **before** any bar is pinned —
T1.2's clamp lesson: calibrating against one implementation's numbers is how a
conforming other-lane solve gets false-FAILed. The control-burn lane gives the
per-run expected periodic delta; `StepEpsilon`/stop bar are pinned midway
between the reference population and the `never-stops` / `global-burn`
attacker populations, per the calibration law. Predicted reference trace is in
§4 — **if the first real run does not reproduce it, stop and find out why.**

## 6. Legs (minimal-leg policy applied — the first family shipped under it)

| leg | family | axis |
|---|---|---|
| reference | both | PASS from git HEAD |
| empty | both | floor (automatic) |
| `never-stops` | both | attacks the AB-5 stop bar (hand-calibrated) |
| `global-burn` | both | attacks AB-4 (the novel axis; hand-calibrated epsilon) |
| `cpp-solve` | `-bp` only | the measured-false-PASS deliverable-format axis |
| `cpp-solve-with-bp` | **NOT authored** | sibling-proven ×4 (glide measured + 3 twins); banned by the policy |
| `bp-no-mesh` | **NOT authored** | family-standard re-proof; banned by the policy |

Five legs `-cpp`, six `-bp`. The requirements table in each MATRIX.md remains
the mandatory soundness artifact; if it finds a hole beyond these axes, one
named leg per hole may be added — with the hole cited.

## 7. G1 questions for the owner (the one human gate)

1. **Radius disclosure**: "about five meters" in the prompt, fixture places
   near/far at 300/1500 uu (3 m / 15 m) — generous margins so no submission
   ever dies on radius interpretation. Accept?
2. **Bands**: burn 3–15 per window, total 12–60, duration 4–7 s. All three are
   §C disclosure debt this family pays for V1.1's world-acting shape. Accept?
3. **Target shape**: verifier-owned targets are plain fixture-spawned pawns
   carrying the contract attribute set — the agent's prompt describes them
   only as "characters". Accept that the agent never sees or configures them?
4. Tag `Ability.AoeBurn` — naming veto?
