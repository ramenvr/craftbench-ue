---
id: gp-dot-aoe-burn-cpp
substrate: ThirdPerson
set: cpp
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_AoeBurn :: AAoeBurnFunctionalTest"]
---

# gp-dot-aoe-burn-cpp

Port of the **BP-G2 source record 48** (`Difficulty: Medium`,
`Before Blueprint: from scratch`), running on the UE 5.8 **ThirdPerson**
substrate. Family **T1.5** of the bp-g2 slate, unheld 2026-08-11 once its two
gate conditions were met (V1.1 landed; tier-1 bands measured).

The design contract is `PIN.md` in this folder — **normative**, G1-accepted by
the owner 2026-08-11 (parameters as pinned; verifier-owned targets; tag
`Ability.AoeBurn`). This spec implements it; it does not redesign it.

**What makes this family new, and why it earns an id.** Every task shipped
before it measures the agent's effect on the agent's OWN pawn. This is the
first **world-acting** task: the deliverable's effect lands on OTHER
characters, and those characters are **verifier-owned** — the fixture spawns
them itself, so a submission can neither author nor pre-configure them. The
novel graded axis is **spatial selectivity**: in one run, a character inside
the area burns and a character outside must not move. Nothing else in the
corpus tests "affects A, spares B".

It is also the **first family authored under the minimal-leg policy**
(`docs/TASK-AUTHOR-GUIDE.md` §7 second amendment, owner vote
2026-08-11): five legs, not seven.

## Primary concept

**Area-of-effect damage over time.** The agent must compose three things the
substrate provides separately: an activatable ability, a periodic schedule,
and a spatial predicate over other actors' attribute sets. The measured
capability is whether a model can make one system act on *other* entities
selectively — the shape underlying every area spell, aura, trap and explosion
in a real game — rather than on the pawn it is already holding.

## Prompt given to the agent

> Give the playable character a **burning area** ability.
>
> When the game activates it, a burning area appears at the character's
> location. For as long as it lasts, any character standing inside the area
> **loses Health repeatedly — about once per second**, in steps of roughly
> equal size. Characters **outside** the area are not affected at all.
>
> The area lasts a **set duration and then stops burning**. The verifier
> accepts any duration in the **four-to-seven-second** range.
>
> Sizes the verifier accepts: the area reaches about **five meters** from
> where it appeared; each character inside loses between **three and fifteen
> Health per second or so**. Over one activation that works out to somewhere
> between **twelve and about a hundred Health in total**, and the verifier
> accepts anything in that range.
>
> The ability must be **activatable by the game** through the character's
> ability system, tagged `Ability.AoeBurn`, and added to the character's
> granted abilities. Health is the attribute on the **provided attribute
> set** the project already ships.
>
> The character must be **visibly represented** — assign one of the provided
> mannequin skeletal meshes (under `/Game/Characters/`).

## Workspace state pre-task

- `Source/ThirdPerson/` — the agent-writable runtime module.
- `ACraftBenchCharacter` — the generic base pawn: pawn-owned ability system
  component, a pre-built `UCraftBenchAttributeSet` (so it has `Health`), an
  `EditAnywhere` `GrantedAbilities` array auto-granted on the authority, and
  the `"CraftBenchPawn"` tag. **The verifier's own target characters are
  instances of this class** — that is how they have Health for the area to
  remove, and it is fixture-side state the agent never sees.
- `UCraftBenchAttributeSet` — the contract attribute set (`Health`,
  `MaxHealth`, `Power`). `Health` is the only attribute this task reads.
- `FCraftBenchGameplayTags::AbilityAoeBurn()` — `"Ability.AoeBurn"`, shipped
  with this family's fixture commit.
- `Content/Characters/Mannequins/Meshes/SKM_Manny_Simple` — a provided body.

## Verifier specification

**Shipped fixture (the source of truth for every gate below):**
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-dot-aoe-burn/AoeBurnFunctionalTest.{h,cpp}`.
Every FAIL string quoted here is read from that `.cpp`.

The fixture spawns the graded pawn (resolved by `Ability.AoeBurn` +
derivation) and **three verifier-owned characters**, then presets all three
in-world at checkpoint 0:

- `TargetNear` — 300 uu from the pawn (inside the disclosed ~5 m), Health 100
- `TargetFar` — 1500 uu (well outside), Health 100
- `TargetControl` — 3000 uu, Health 100, plus the fixture's own known-rate
  periodic drain (the AB-0 control lane)

```text
OnCheckpoint idx 0 (0.5s):
    preset all three targets to 100
    apply the fixture-owned control drain to TargetControl; C0 = control Health
    AB-7 visibility  : a mesh component with an assigned mesh on the graded pawn
    TriggerTime = t  ; trigger Ability.AoeBurn (1 of 1)
    N0 = near Health ; track far deviation
idx 1 (1.6s): N1     = near Health   (D1 closes — 1.1 s window, EVIDENCE ONLY)
idx 2 (3.1s): N2     = near Health   (D2 closes — 1.5 s)
idx 3 (4.6s): N3     = near Health   (D3 closes — 1.5 s, CONGRUENT with D2)
idx 4 (7.6s): NStop  = near Health   (stop window OPENS, past the 4-7s band top)
idx 5 (9.7s): NTail  = near Health   (stop window closes) ; ALL FINAL ASSERTS

    Far deviation is tracked at EVERY checkpoint, not just the last.

    AB-0 : control Health dropped        -> else [HARNESS] FAIL, never an agent verdict
    AB-1 : granted by tag AND activated
    AB-2 : D1, D2, D3 each > StepEpsilon              (direction + noise floor)
    AB-3 : MEAN rate over the 4.1s in-band span within 2.0-20.0
           (disclosed 3-15; ENFORCED WIDER on purpose - see Hidden invariants.
            A per-window band was measured unsound 2026-08-11: equal-duration
            windows hold unequal tick counts, so it false-FAILed a conforming
            12-per-tick solve at D3=24 against a 15 top.)
    AB-4 : FarMaxDeviation <= StepEpsilon             (THE AREA GATE)
    AB-5 : (NStop - NTail) <= StopEpsilon             ("stopped changing")
    AB-6 : 12.0 <= (100 - NTail) <= 105.0             (DISCLOSED total band, DERIVED
           from the rate and duration tops: 3x4 = 12, 15x7 = 105)
```

`TimeLimit` is set by the base class from the last checkpoint plus its margin,
so a stuck test FAILs rather than hanging.

**Constants — PROPOSED, NOT YET MEASURED** (pinned by the calibration runs,
per the calibration law): `StepEpsilon` 0.5, `StopEpsilon` 0.25 (must remain
`< 1.0 × StepEpsilon`), mean-rate band 2.0–20.0 enforced over the 4.1 s in-band span (disclosed 3–15;
enforced wider on purpose — see below), total band 12.0–105.0,
target preset 100.0, control drain −2.0 per 1.0 s for 20 s.

Both the `-cpp` and `-bp` reference solves are built **before** any bar is
pinned — the T1.2 lesson: calibrating against one implementation's numbers is
how a conforming other-lane solve gets false-FAILed.

## Reference solution metadata

`reference/Source/ThirdPerson/` — 4 files, 0 assets:

- `AoeBurnAbility.{h,cpp}` — `InstancedPerActor`; ability tag
  `Ability.AoeBurn`; on activation captures the activation point (the area is
  a **place**, not an aura that follows the caster), burns immediately, then
  on a 1.0 s looping timer removes 5.0 Health from every other
  `ACraftBenchCharacter` within 500 uu of that point, via
  `SetNumericAttributeBase`; ends itself after 5.0 s of ticks and clears the
  timer in `EndAbility` (covering every end path).
- `AoeBurnPawn.{h,cpp}` — `ACraftBenchCharacter` subclass; grants the
  ability; assigns `SKM_Manny_Simple` through a guarded constructor finder.

**Predicted reference trace — PREDICTED, not yet measured.** Near
`100 → 95 → 90 → 85 …` in 5.0 steps; `D2 = D3 = 7.5` (1.5 s windows at
5.0/s), total 25–30, `StopDrop = 0.0`, far exactly `100.0`, control dropping
steadily. **If the first real run does not reproduce this shape, stop and find
out why before touching a bar.**

## Anti-gaming notes

1. **Burn everything in the world ("AoE" read as "everyone").** *Failure
   mode*: apply the periodic effect to every attribute-set holder with no
   spatial test. Near-target burn, rate, total and stop are all identical to
   a conforming solve — this passes every gate except one. *Defense*:
   **AB-4**, the far character's Health must stay within the noise floor of
   its starting value across the whole run, sampled at EVERY checkpoint (a
   final-read-only check would miss a burn-then-restore). *Discrimination
   variant*: `global-burn/`.
2. **A burn that never expires.** *Failure mode*: a permanent area or an
   infinite-duration effect — the periodic gates go green and only the ending
   is wrong. *Defense*: **AB-5**, a stop window opening past the disclosed
   band top, with `StopEpsilon` pinned **below** the step floor per the
   T1.2 law (at a looser bar a permanent burn passes). *Discrimination
   variant*: `never-stops/`.
3. **A single instant hit instead of a periodic burn.** *Failure mode*: one
   large hit whose total sits inside the disclosed band, so the total gate
   cannot catch it. *Defense*: **AB-2** is a pure direction-plus-noise-floor
   predicate over three windows — an instant hit drops once and stays flat —
   and **AB-3** gates the MEAN rate over the whole in-band span, so the
   magnitude cannot be smeared into one sample. AB-3 is a mean and not a
   per-window band for a measured reason — see *Hidden invariants*.
4. **A dead or mis-timed periodic system blamed on the agent.** *Failure
   mode*: not gaming — an environment fault (a broken GE path, a stalled
   world) that makes a conforming submission read as non-periodic.
   *Defense*: **AB-0**, the control lane: a third, distant verifier-owned
   character receives the fixture's OWN known-rate periodic drain. If that
   did not tick, the run FAILs with a `[HARNESS]`-prefixed message that
   `cb discriminate` can never credit and no reader can mistake for an agent
   failure.
5. **An invisible deliverable.** *Failure mode*: behaviourally correct,
   nothing to see. *Defense*: **AB-7** at checkpoint 0, the family-standard
   visible-character gate. *No variant is authored for it* — the minimal-leg
   policy: this gate is proven at family level (9/9 recorded glide reps
   shipped meshless pawns) and a re-proof here would find nothing.

## Hidden invariants

- **AB-3 is a MEAN rate, and the two magnitude bands are arithmetically
  consistent — both are 2026-08-11 calibration repairs, not original design.**
  The first calibration run measured the reference at `D1=5.00 D2=5.00
  D3=10.00`: equal-DURATION windows hold unequal TICK COUNTS (1.5 s windows
  against a 1.0 s period), so the original per-window band would have
  false-FAILed a conforming 12-per-tick solve at `D3=24` against a 15 top.
  Replacing it with a mean over the fixed 4.1 s span fixed that — and then the
  `conforming-fast` calibration solve (12 per tick, squarely inside the
  disclosed 3-15) FAILed again at **72.00 total against a 60.0 top**, because
  the disclosed rate band and the disclosed total band could not both be
  satisfied: 15/s for 7 s is 105, not 60. The total top is now DERIVED from
  the other two bands' tops. Neither defect was reachable by any attacker
  variant; both needed a solve that CONFORMS at a different point in the
  disclosed space, which is why `aids/calibration/conforming-fast/` is kept
  and graded whenever a bar moves.

- **The caster's own Health is deliberately ungated.** The reference skips the
  avatar (a character standing in their own fire is a design choice, not a
  contract), and the fixture never reads the graded pawn's Health. Both
  readings of "burns enemies" — including or excluding self — therefore grade
  identically. This is the §C way to price an ambiguity the source row never
  resolves: at zero.
- **The far target is 1500 uu out against a disclosed ~5 m (500 uu) radius**,
  and the near target is 300 uu in. A submission would have to misread the
  radius by 3× in one direction, or 5× in the other, before a gate noticed —
  no reasonable reading of "about five meters" is punished.
- **Targets are presets, not spawn defaults.** They are spawned in
  `PrepareTest` but written in-world at checkpoint 0, after their BeginPlay:
  the generic base's attribute defaults are not this task's contract.
- **`Ability.AoeBurn` is distinct from every other family's tag**, because
  `PreferredAbilityTag()` drives `ResolveAgentPawnClass` — a reused tag would
  let another family's committed pawn win this family's resolution by
  enumeration order.
- **The control lane can only ever produce a non-agent verdict.** Its FAIL
  string is `[HARNESS]`-prefixed and appears in no MATRIX row, so no
  discrimination leg can be credited by it.
