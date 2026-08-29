# Discrimination matrix — t2-melee-ability-with-cooldown

One row per submission; the "Expected message" cell must appear as a
substring of the L2 failure (discriminate greps the log for it — a
wrong-reason FAIL is NOT discrimination). Run:
`cb discriminate --task cpp/t2-melee-ability-with-cooldown [--wip]`.

| Submission | Verdict | Fails at | Expected message substring | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | PASS | — | — | — |
| empty | FAIL | cp0 (0.6s) | `no activatable ability tagged Ability.Melee` | #1 (no-GAS shape) |
| `no-cooldown/` | FAIL | cp2 (1.8s) | `during the cooldown window` | #2 |
| `hits-everything/` | FAIL | cp1 (1.2s) | `out-of-reach enemy was damaged` | #3 |
| `cooldown-never-ends/` | FAIL | cp6 (4.0s) | `never recovered after the cooldown` | #4 |

Notes:
- Checkpoint schedule is {0.6, 1.2, 1.8, 2.2, 2.5, 3.4, 4.0}; the disclosed
  2.0s cooldown from the trigger at 0.6 expires at 2.6. Both in-window
  re-triggers (1.2 and 2.2) and both hold-checks (1.8 and 2.5) sit INSIDE the
  window — the 2.2/2.5 pair narrows the accepted cooldown band (a cooldown
  ending before ~2.5 fails). The recovery trigger (3.4) sits past expiry with
  0.8s margin, and cp5 additionally asserts NO drop appeared in the
  2.5..3.4 no-trigger window — the **deferred-strike trap**: a solution that
  buffers an in-window trigger and executes it at expiry (the wave-1
  delayed-cheat shape) dies at `a deferred strike landed after the cooldown
  window` without needing a dedicated variant. cp6 re-asserts the far target
  (same shared assertion text as cp1 — one branch, one message).
- **Honestly-bounded coverage:** the agent owns the scaffold source
  (`MeleeDummyActor.cpp`), so a stub ability plus SELF-SCRIPTED Health values
  (the dummy driving its own Health down on a timeline that mimics the
  expected trace) is a residual gaming shape no assertion here fully
  excludes. The defenses that raise its cost: the targets are pinned BEFORE
  the agent pawn exists (pawn-spawned decoys are never read), the equal-
  baseline symmetry check, the far target having to stay FLAT while the near
  one moves on exactly the undisclosed checkpoint timeline, and the
  granted+activated GAS gates still requiring a real tagged ability. Total
  scripted-trace immunity is NOT claimed.
- The empty leg (base pawn, no ability granted) dies at cp0's granted-count
  check — the same named assertion a no-GAS direct-damage solution hits.
- Anti-gaming note #5 (pre-spent targets) is argued from cp0's equal-baseline
  check plus the delta-only gates rather than a separate submission — an
  absolute-health check would be gameable by editing the scaffold default,
  a delta from a fixture-captured baseline is not. Bounded coverage, stated
  honestly.
- **ASCII rule (inherited from t2-homing-projectile the hard way):** FinishTest
  messages and these substrings must be ASCII-only — the UE log's UTF-8 bytes
  are read back as cp1252, so an em dash becomes mojibake and the substring
  grep misses, classifying a CORRECT fail as wrong-reason.

## Status
- Authored 2026-07-30 (text half + adversarial review fixes same day — incl.
  replacing the GE-component cooldown route the review proved is an engine
  Fatal at CDO registration).
- **EXECUTED 2026-07-30** (after the binary half landed):
  `cb discriminate --task cpp/t2-melee-ability-with-cooldown --wip` =
  **discriminated: YES on the first attempt** — reference PASS; empty,
  no-cooldown, hits-everything, cooldown-never-ends all FAIL, each `[ok ]`
  (credited via its named substring). First GAS task authored since the
  bp-g2 ports; the hand-rolled cooldown gate discriminated at the shipped
  times (../notes.md calibration record).

# DRAFT — to be appended to tasks/cpp/t2-melee-ability-with-cooldown/discrimination/MATRIX.md

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked span is a contiguous `FinishTest(EFunctionalTestResult::Failed, ...)`
literal in `UE-projects/CraftBenchTemplate/Source/CraftBenchTests/Tasks/t2-melee-ability-with-cooldown/MeleeCooldownFunctionalTest.cpp`
(the only file whose FinishTest literals appear as gate tokens in the table below);
pawn resolution-by-derivation and the tag-preference disambiguation live in the shared base
`UE-projects/CraftBenchTemplate/Source/CraftBenchTests/CraftBenchPawnFunctionalTest.cpp`
(`ResolveAgentPawnClass` — it has no failure literal of its own: a missing subclass
falls back to the base pawn and dies at row 1's token). The base's `SpawnAndPossessPawn`
DOES carry its own `FinishTest(Failed, ...)` literals — `SpawnAndPossessPawn: no world`
(line 156) and `SpawnAndPossessPawn: spawn of %s failed` (line 169) — which can fail this
task from PrepareTest before any fixture gate runs. Timeline for reading the
rows: checkpoints at {0.6, 1.2, 1.8, 2.2, 2.5, 3.4, 4.0}s; trigger #1 at 0.6 (window
0.6..2.6), in-window re-triggers at 1.2 and 2.2, recovery trigger at 3.4. Gates fire
in checkpoint order and the first `FinishTest` ends the run, so every row is
implicitly skipped once any earlier row's gate has fired; the "Gate skipped when"
column names only the skips beyond that rule (and L2 as a whole is skipped when L1
fails to build either target).

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | an ability tagged `Ability.Melee` is granted on the pawn (the strike goes through the ability system, not direct Health writes) | fully | cp0 (0.6s) granted-count gate — `no activatable ability tagged Ability.Melee on the pawn` (fails when `Granted < 1`, where Granted = the possessed pawn's `NumGrantedAbilitiesWithTag`(Ability.Melee) count) | equal-baseline gate (row 15) fires first at cp0 | a stub ability that itself does nothing, paired with scaffold-scripted Health movement — the MATRIX's honestly-bounded residual (agent owns `MeleeDummyActor.cpp`); the delta/symmetry/timeline gates raise its cost but total scripted-trace immunity is not claimed |
| 2 | activating the tag actually activates the ability | fully | cp0 activation gate — `was granted but did NOT activate on the tag trigger` (checks the `TryActivateAbilitiesByTag` success flag) | row 1 fires first | an ability that activates and instantly self-cancels satisfies this bit — the damage/cooldown rows carry the rest |
| 3 | the pawn is delivered as a subclass of the provided character, with the ability granted | indirectly (no dedicated gate) | resolution-by-derivation in the base (`ResolveAgentPawnClass`): native then `/Game/Tasks` Blueprint subclasses of `ACraftBenchCharacter`, preferring one whose CDO grants an `Ability.Melee`-tagged ability; no subclass → base pawn, empty `GrantedAbilities` → dies at row 1's token. Spawn/possess faults fail in the BASE with its `SpawnAndPossessPawn: ...` literals (CraftBenchPawnFunctionalTest.cpp:156/169) before the fixture's token can fire; the fixture's `pawn did not spawn/resolve` covers only a pawn that resolved/spawned but is invalid at checkpoint time (MeleeCooldownFunctionalTest.cpp:92) | unconditional (runs in PrepareTest) | granting the ability at runtime (e.g. possessed-pawn BeginPlay) instead of via the CDO `GrantedAbilities` array still passes rows 1–2 — the granted-count check reads the live ASC, and the CDO tag-preference only matters for disambiguation when foreign pawn subclasses coexist |
| 4 | the enemy directly in front and within ~250 units loses a meaningful amount of Health (at least a few points) | partially (floor is 1.0, near target sits at 150uu) | cp1 (1.2s) damage gate — `the strike did not damage the enemy within reach` (fires on `NearBase - NearNow < MinDamage`, MinDamage = 1.0) | cp0 failed | a 1.0-point strike passes despite the "at least a few points" language; reach is probed only at 150uu (near) and 900uu (far), so any effective reach in (150, 900) uu passes as "about 250" |
| 5 | damage lands essentially immediately (no wind-up / delayed hit) | fully, at 0.6s resolution | same cp1 token — `the strike did not damage the enemy within reach` fires if the 0.6s trigger has not landed by 1.2s | cp0 failed | a wind-up of up to ~0.6s is invisible (checkpoint granularity) |
| 6 | damage lands once per strike, not repeatedly over time | fully, on the checkpoint grid | hold gates cp2 (1.8s) / cp4 (2.5s) — `a strike landed during the cooldown window` (near Health must not move off the post-strike value); plus cp5's row-12 token for the 2.5..3.4 window | rows 4–5 failed at cp1 (run already over) | a multi-tick DoT fully contained inside 0.6..1.2s is indistinguishable from one immediate hit |
| 7 | targets outside reach never lose Health | fully | far-target gate at cp1 AND re-asserted at cp6 (4.0s) — `an out-of-reach enemy was damaged by the strike` (far pinned at pawn+forward*900, delta vs baseline, epsilon 0.1) | at cp1: the row-4 gate fires first; at cp6: the row-13 gate fires first | any Health movement on the far target between the checkpoints that returns to baseline by the next read (delta checks sample, they don't monitor per-tick) |
| 8 | targets **behind the character** never lose Health | **NOT ASSERTED** | none — both dummies are placed along the pawn's +forward vector (near 150uu, far 900uu); no target is ever behind the pawn | — | a reach-limited 360-degree radial sweep with no facing check whatsoever passes every gate — "directly in front" is enforced only in the positive direction (the near target IS in front). task.md's Hidden invariants state this bound deliberately (far fails on distance alone), but nothing asserts behind-immunity |
| 9 | a trigger during the 2s cooldown does no damage | fully | cp2/cp4 hold gates after the in-window re-triggers at 1.2s and 2.2s — `a strike landed during the cooldown window` | cp1 failed | nothing beyond row 11's band latitude |
| 10 | a blocked trigger must not restart the cooldown | fully (via recovery) | cp6 recovery gate — `the strike never recovered after the cooldown`: a restart on the refused 2.2s trigger pushes expiry to 4.2s, past the 3.4s recovery trigger, so cp6's required second drop never comes | rows through cp5 failed first | an implementation that re-arms only on the FIRST refused trigger (expiry 3.2s < 3.4s) would slip through — no plausible implementation restarts on exactly one refusal |
| 11 | the cooldown is 2 seconds | partially (band, not value) | lower bound: `a strike landed during the cooldown window` (the +1.6s re-trigger at 2.2 must be refused, checked at 2.5); upper bound: `the strike never recovered after the cooldown` (the +2.8s trigger at 3.4 must land, checked at 4.0) | rows 9–10 skips | any constant cooldown in (1.6s, 2.8s] passes as "2 seconds" — the undisclosed re-trigger/checkpoint times are the only calibration |
| 12 | no buffering: a refused in-window trigger must not execute later at expiry | fully | cp5 (3.4s) deferred-strike trap — `a deferred strike landed after the cooldown window` (near Health must be flat across 2.5..3.4, a window in which no trigger is sent but the 2.6s expiry sits) | `bAfterFirstCaptured` false (cp1 never ran — impossible past cp1's own gate) | a deferred strike executing after 3.4 but before the 4.0 read would instead be read as legitimate recovery at cp6 — masked, not caught, though it requires suppressing the real 3.4 trigger too |
| 13 | once the 2s have passed, the next trigger strikes normally again | fully | cp6 (4.0s) recovery gate — `the strike never recovered after the cooldown` (near must drop >= 1.0 again after the 3.4s trigger) | earlier checkpoints failed | the second strike's amount only needs the same 1.0 floor; nothing requires it to equal the first strike's damage |
| 14 | the targets' public float `Health` contract stays intact (readable on every tagged target) | fully | every-checkpoint reflection gate — `a MeleeDummy-tagged target has no readable float Health property` (`FindFProperty<FFloatProperty>` on "Health"; subclassed dummies stay legal) | never (runs before the per-checkpoint switch) | renaming/retyping on a NON-tagged helper actor — only the two pinned tagged targets are read |
| 15 | targets start at full Health (no pre-spent baselines) | partially (equality, not absolute) | cp0 equal-baseline gate — `the two practice targets did not start at equal health` (epsilon 0.1, captured after fixture-owned placement, before trigger #1) | unconditional (first cp0 gate) | SYMMETRIC pre-spend (both targets edited to the same lower start) passes — deliberate: every later gate is a DELTA from the fixture-captured baseline, so absolute values are moot (anti-gaming note #5) |
| 16 | the two map-shipped practice targets stay present and alive | fully | PrepareTest precondition — `expected 2 MeleeDummy-tagged targets in the map, found ` (harness-labelled; the committed map ships exactly two) — plus per-checkpoint `a pinned MeleeDummy target is no longer valid at checkpoint time` for a runtime destroy | never | extra tagged decoys spawned by SCAFFOLD BeginPlay could displace a real target in the name-sort (pin happens before the PAWN exists, but not before map-actor BeginPlay); the equal-baseline + timeline gates are the stated cost-raisers, not the pin alone |
| 17 | optional: print a short log line when damage is dealt | n/a — explicitly ungraded ("nice for debugging, not graded") | none, by design (FR-020d: no undisclosed log gating) | — | anything: absent, wrong, or misleading log lines are all free |

Rows 8 is the one open hole (behind-immunity); rows 4, 11, 15 are deliberate
calibrated bands, stated here so a reviewer never mistakes the band for the value.
