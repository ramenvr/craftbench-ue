# gp-dot-aoe-burn-bp — reference solution (binary .uasset, editor-authored)

**Status: AUTHORED + GRADED PASS 2026-08-11, first grade** — L2 1/1 + L2I
**5/5**, `meanRate=6.10 total=30.00 stopDrop=0.00 farMaxDev=0.00`. The
reference lives at `reference/Content/Tasks/gp-dot-aoe-burn-bp/` (3 `.uasset`s),
byte-verified free of `/Script/CraftBenchTemplate` bytes.

Read the three 2026-08-11 twins' REFERENCE-NOTEs first — the two-lane recipe
(headless editor-Python for CDO/data, Aura MCP for the K2 graph, sandbox
promotion, aids-script CDO repair, byte-verify) is identical here and is not
repeated. What follows is only what this family adds.

## As-built (3 assets)

1. **GE_AoeBurnTick** — HasDuration **5.0**, Period **1.0**,
   `bExecutePeriodicEffectOnApplication` **ON**, one `Health` AddBase **−5.0**
   modifier. The flag is load-bearing: it makes 5 s of a 1 s period **six**
   executions, which is the `-cpp` reference's measured total of 30.
2. **GA_AoeBurn** — InstancedPerActor, `ability_tags = Ability.AoeBurn`, no
   cost, no cooldown. Graph (11 nodes): ActivateAbility → CommitAbility →
   Branch; false → EndAbility; true → `SphereOverlapActors` (radius **500**,
   `ObjectTypes = [Pawn]` via a Make Array, `ActorClassFilter =
   CraftBenchCharacter`, centred on the avatar's location) →
   `AbilityTargetDataFromActorArray` → `ApplyGameplayEffectSpecToTarget`
   (spec from `MakeOutgoingGameplayEffectSpec`, GE_AoeBurnTick, Level 1) →
   EndAbility.
3. **BP_AoeBurnPawn** — parent `CraftBenchCharacter`,
   `GrantedAbilities=[GA_AoeBurn]`, `SKM_Manny_Simple` at (0,0,−90)/(0,−90,0).
   No event graph.

## THE PORT TRAP THIS FAMILY ADDS — a class-reference PIN

The ability's `SphereOverlapActors` node carries an **`ActorClassFilter` pin
whose value is a class reference**. Authored on CraftBenchTemplate it reads
`/Script/CraftBenchTemplate.CraftBenchCharacter`, and if it survived the port
in that form the reference would find **no targets at all**: the burn would do
nothing, and AB-2 would report *"the burn was not periodic"* — a true statement
about a symptom whose cause is the port, not the solve. That is the
heal-over-time pin-literal defect wearing different clothes.

**Measured answer: a class pin default IS a real object import, so
CoreRedirects DO re-point it** — unlike HOT's `FGameplayAttribute` struct pin
literals, which carry a field path that gets no fix-up. The two cases look
identical in the editor and behave oppositely, so `aids/author_assets.py`
**asserts** the filter after load rather than trusting either precedent: it
`die()`s if the pin still names the template class, or if it stops naming
`CraftBenchCharacter` at all. The assert ran green on the 2026-08-11 port
(`spatial filter=/Script/ThirdPerson.CraftBenchCharacter`).

## The Blueprint is a genuinely different implementation, not a transcription

| | `-cpp` reference | this twin |
|---|---|---|
| periodicity | 1.0 s looping `FTimerManager` timer | the GameplayEffect's own `Period` |
| spatial filter | `GetAllActorsOfClass` + `FVector::Dist` per actor | `SphereOverlapActors` |
| application | `SetNumericAttributeBase` per target | one batched apply over target data |
| stop | tick counter → `EndAbility` | the effect's `Duration` |

Same `farMaxDev=0.00`, `total=30.00`, `meanRate=6.10`.

It was forced into the better design by a tool limit: **`ForEachLoop` is not
reachable through the MCP node API** — `add_blueprint_node_to_strand` reports
`Macro 'ForEachLoop' not found. Available macros:` (empty), so the
loop-and-distance-test shape was simply unavailable. The loop-free result has
no timer, no counter and no manual distance math. If a future family needs a
BP loop, budget for that gap up front.

## The one number that differs, and why it is not a defect

`-cpp` reads `N0=95.0, D1=5.00`; this twin reads `N0=100.0, D1=10.00`. The C++
ability burns synchronously inside `ActivateAbility`, so checkpoint 0 already
sees the first tick; the Blueprint's first tick lands on the effect's first
periodic evaluation, after cp0. **Both pass because AB-2 is a pure direction
predicate and AB-3 is a mean over the whole span.** Under the per-window band
the `-cpp` half shipped with for one afternoon, this divergence would have been
another phase-driven false FAIL — the second conforming implementation to
catch that same defect class, which is exactly the argument for keeping a
conforming-but-different solve in the loop (`../gp-dot-aoe-burn-cpp/aids/calibration/`).

## Re-validate

```sh
cb discriminate --task gp-dot-aoe-burn-bp
```
