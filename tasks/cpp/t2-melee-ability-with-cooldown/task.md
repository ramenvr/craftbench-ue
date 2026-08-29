---
id: t2-melee-ability-with-cooldown
substrate: CraftBenchTemplate
set: cpp
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_MeleeCooldown :: AMeleeCooldownFunctionalTest"]
---

# t2-melee-ability-with-cooldown

A melee strike with a cooldown, delivered through the substrate's ability
system: triggering the strike damages the enemy directly in front within a
short reach — exactly once per trigger — a re-trigger during the cooldown
window does nothing, the strike works again once the cooldown has passed, and
enemies out of reach are never touched. Drawn from an earlier internal task list (not shipped)
("Melee attack (GAS)"); see Provenance for what was cut and why.

> GAS-category note: like `gp-poison-dot-stack-cpp` / `gp-glide-stamina-cpp`, this task
> names the GAS contract (an ability tagged `Ability.Melee`, granted on a
> subclass of the provided ability-system pawn) as part of the interface — the
> documented exception to behavior-only prompts, because verifying the strike
> *through the ability system* is the point.

## Primary concept

- `gas-abilities` — Gameplay Abilities with cooldown GameplayEffects
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/using-gameplay-abilities-in-unreal-engine)

The load-bearing mechanic is a **cooldown-gated, spatially-filtered ability**:
activation applies bounded damage to targets selected by reach + facing, and
the ability system's cooldown (or an equivalent hand-rolled timer — the
behavior is what is graded) blocks re-activation inside the window without
consuming or extending it.

## Prompt given to the agent

> The project provides a character pawn that already owns an ability system,
> and practice-target actors that carry a public float `Health` value
> (starting at full). Implement a **melee strike** ability:
>
> - Tag the ability `Ability.Melee` and add it to the pawn's granted
>   abilities, so the game can perform the strike by activating that tag.
> - When the strike is performed, an enemy target that is **directly in front
>   of the character and within about 250 units** loses a meaningful amount of
>   `Health` (your choice of amount, at least a few points) — **once per
>   strike**, not repeatedly over time, and the damage lands **essentially
>   immediately** when the strike is triggered (no wind-up or delayed hit).
> - Targets **outside that reach — or behind the character — must never lose
>   Health** from the strike.
> - The strike has a **2 second cooldown**: a trigger that arrives while the
>   cooldown is running must do nothing at all (no damage, and it must not
>   restart the cooldown). Once the 2 seconds have passed, the next trigger
>   strikes normally again.
> - Deliver your pawn as a subclass of the provided character with your
>   ability granted. Optionally print a short log line when damage is dealt
>   (who was hit, for how much, remaining health) — nice for debugging, not
>   graded.
>
> The verifier activates your ability by sending the `Ability.Melee` tag at
> several moments — some inside the cooldown window, some after it — and
> watches the targets' `Health` values over time.

## Workspace state pre-task

Files that **exist** under `Source/CraftBenchTemplate/`:

- `CraftBenchTemplate.Build.cs` — already includes `GameplayAbilities`,
  `GameplayTags`, `GameplayTasks`. No edit needed.
- `CraftBenchCharacter.{h,cpp}` — `ACharacter` + `IAbilitySystemInterface`
  with a pawn-owned ASC and an auto-granted `GrantedAbilities` array (ships
  empty). The agent's pawn subclass fills it.
- `CraftBenchGameplayTags.{h,cpp}` — registers `Ability.Melee`
  (`FCraftBenchGameplayTags::AbilityMelee()`), alongside the other task tags.
- `Tasks/t2-melee-ability-with-cooldown/MeleeDummyActor.{h,cpp}` — the
  practice target: a visible body, the `MeleeDummy` actor tag, and
  `float Health = 100`. **No damage handling, no ability, no cooldown exists
  anywhere.**
- `AMeleeCooldownFunctionalTest` lives in the verifier-only `CraftBenchTests`
  module.

Files the agent **creates**: a `UGameplayAbility` (C++ or Blueprint) tagged
`Ability.Melee` implementing the reach-limited, cooldown-gated strike, plus a
subclass of `ACraftBenchCharacter` granting it. The pawn is resolved by
derivation and spawned + possessed by the verifier.

## Verifier specification

The test runs in PIE from `Maps/t2-melee-ability-with-cooldown/L_MeleeCooldown.umap`
at a fixed deterministic step (`-deterministic -FPS=60`).

```text
AMeleeCooldownFunctionalTest::PrepareTest():
    pin the two MeleeDummy-tagged targets BEFORE the pawn exists
    (name-sorted; nothing the pawn's BeginPlay spawns can be pinned)
    PawnSpawnLocation = (0, 0, 120)      // settles on the floor before cp0
    Super::PrepareTest()                  // resolve (PreferredAbilityTag=Ability.Melee) + spawn + possess
    SetCheckpointSchedule({ 0.6, 1.2, 1.8, 2.2, 2.5, 3.4, 4.0 })

cp0 (0.6): place near target at pawn+forward*150, far at pawn+forward*900
           (fixture-owned geometry); capture baselines; assert equal baselines;
           Trigger #1; assert granted>=1 and activation (the GAS gates)
cp1 (1.2): assert near dropped >= MinDamage; assert far unchanged;
           record post-strike value; RE-trigger (INSIDE the 0.6+2.0 window)
cp2 (1.8): assert near unchanged since cp1   // first hold-check
cp3 (2.2): second in-window RE-trigger        // narrows the accepted band
cp4 (2.5): assert near still unchanged        // window reaches at least here
cp5 (3.4): assert near STILL unchanged        // deferred-strike trap
           then Trigger #3                    // past the 2.6 expiry
cp6 (4.0): assert near dropped again since cp1  // the strike recovered
           assert far still unchanged           // reach held for the whole run
```

**Pass criteria**: both L1 targets build; every cp0-cp4 gate green. Health is
read by REFLECTION (`FindFProperty` on `Health`) so subclassed targets stay
legal; targets are found by the `MeleeDummy` tag, the pawn by derivation from
`ACraftBenchCharacter` (identity by tag/derivation, never class name).

## Reference solution metadata

- LOC range: ~90-130 across 6 files: `MeleeAbility.{h,cpp}` (tag + commit +
  reach/facing sweep + Health write), `MeleeCooldownEffect.{h,cpp}` (a 2.0s
  HasDuration GE granting the ability's cooldown tag),
  `MeleePawn.{h,cpp}` (grants the ability).
- Files touched: 6 new; 0 edits to existing files.
- Senior-dev hours: 1-2.
- A Blueprint reference (BP ability + BP cooldown GE + BP pawn) is the
  equivalent deliverable; the verifier resolves a BP pawn via the asset
  registry.

## Anti-gaming notes

1. **No GAS (damage the targets from Tick/BeginPlay without an ability).**
   *Failure mode*: the agent writes `Health` down directly without any
   ability. *Defense*: the fixture requires
   `NumGrantedAbilitiesWithTag(Ability.Melee) >= 1` AND an actual activation
   on the tag trigger; with no ability granted the run fails at the first
   checkpoint regardless of any Health movement.
2. **No cooldown (spammable strike).** *Failure mode*: every trigger lands.
   *Defense*: the fixture re-triggers INSIDE the 2s window (at +0.6s) and
   asserts the near target's Health is unchanged at the next checkpoint —
   still inside the window, so a landed second strike is caught before the
   cooldown would have expired.
3. **Area nuke (no reach/facing check).** *Failure mode*: the strike damages
   every tagged target on the map. *Defense*: a second target is pinned far
   outside reach along the same facing; any Health movement on it fails the
   "out-of-reach enemy was damaged" assertion.
4. **One-shot ability (cooldown that never ends).** *Failure mode*: the
   ability refuses all triggers after the first, trivially passing the
   cooldown check. *Defense*: the fixture triggers again after the 2s window
   (at +2.8s) and requires the near target's Health to drop again.
5. **Pre-spent targets.** *Failure mode*: the agent edits the scaffold's
   Health default or burns damage in at BeginPlay so later deltas look
   plausible. *Defense*: all gates are DELTAS from fixture-captured baselines,
   and the two targets must start at EQUAL health — asymmetric pre-damage
   fails before the first trigger.

## Hidden invariants

- **The re-trigger timings are undisclosed.** The prompt discloses the 2.0s
  cooldown but not WHEN the verifier re-triggers (0.6s and 1.6s into the
  window) or re-checks. The accepted band: the window must still be closed
  1.9s in (the 2.2s re-trigger must be refused, checked at 2.5) and must be
  open by 2.8s in (the 3.4 trigger must land). A cooldown shorter than ~1.9s
  or longer than ~2.8s fails; a buffered trigger executing at expiry is
  caught by the deferred-strike trap at 3.4.
- **The far target sits along the pawn's facing** — a reach check without a
  facing check still passes (far fails on distance alone), but a
  damage-everything sweep fails. Facing is additionally exercised because
  both targets are in FRONT: a behind-the-pawn filter alone (facing without
  reach) damages the far target and fails.
- **Blocked triggers must not re-arm the cooldown.** The fixture's failed
  re-trigger at 1.2s must not push the expiry past 3.4s — an implementation
  that restarts its timer on REFUSED triggers fails the recovery gate at 4.0s.
