# PIN SHEET (G1) -- `gp-double-jump-stamina-{cpp,bp}`

> ## The one question you are answering
>
> **Given only the prompt in column 2, could a competent gameplay engineer
> produce a passing solution -- and does the wrong solve in §4 actually get
> caught by the FAIL string named beside it?**
>
> Answer `ACCEPTED`, `EDIT` (with what to change), or `CUT` in
> the internal design note (not shipped). One gate (DJ-6) is offered as **optional** and is
> flagged for an explicit keep/cut in §5 D4.

**Family:** T1.3. **Source:** source record 33 ("Movement-1", `medium`,
`Category: Full Prompt`). **Substrate:** ThirdPerson. **Layers:** `-cpp` =
L1+L2; `-bp` = L1+L2+L2I. **Blocked on I1.4 / V2.3** (segmented-apex detection
on `CraftBenchPawnFunctionalTest`). **Budget this as a re-author, not a port.**
**Status: nothing built. Every number below is `PROPOSED - NOT YET MEASURED`.**

---

## 1. Sheet row -> prompt -> gate -> drop

`sheet_verbatim` is the literal source record 33, read with `csv.reader`. The
`Prompt` cell's line breaks are **CRLF** in the source (unlike record 29, which
is LF); reproduced below as line breaks.

| sheet_verbatim | agent_visible_rewrite | what the fixture asserts | dropped, with precedent |
|---|---|---|---|
| `Create a double jump ability using the Gameplay Ability System.` | "Implement an ability the game can activate on the character that gives it a **second jump while it is already falling through the air**: activating it must **reverse the descent and carry the character upward again**, from a standing fall, without teleporting it." | DJ-1 (granted+activated), DJ-2a (really falling pre-trigger), DJ-2b (upward impulse: max vZ after trigger > 0), DJ-2c (segmented rise after a local minimum). | **"Gameplay Ability System" dropped as a name.** Hard Rule #2 / `AUTHORING_TEMPLATE.md:365-380` ("use the X system" is Unacceptable). Carried instead by the **documented GAS-category exception** the family already uses: an ability the game can *activate*, a trigger *tag*, the pawn's *granted abilities*. Precedent: `gp-glide-stamina-cpp`, `gp-poison-dot-stack-cpp`. |
| `This ability should consume 20 stamina.` | "Activating it must **cost 20 of the character's Power resource**, debited **once** per activation - not drained continuously while airborne. If the character has **less Power than the cost, the ability must not fire**: no second jump, and Power must not go negative." | DJ-3a (Power strictly decreased), DJ-3b (exactly 20, disclosed), DJ-3c (one-shot: flat after the debit), DJ-4 (refusal leg). | Nothing dropped -- but **"stamina" is re-homed to the substrate's `Power` attribute** and named as such, exactly as `gp-glide-stamina-cpp`'s prompt names it ("a depletable **Power** resource"). The **refusal clause is added** (not in the row): without it "consume 20" is satisfied by a cosmetic subtraction, and there is no gate separating "debits a number" from "a real cost". |
| `Use the existing attribute set type: GSCAttributeSet` | "the character's **Power** resource" (the provided character already owns it) | DJ-3a/b/c read `UCraftBenchAttributeSet::GetPowerAttribute()`. | **`GSCAttributeSet` re-homed.** It exists in **neither substrate** (GAS Companion; the repo is vanilla GAS). Rebased onto `UCraftBenchAttributeSet::Power`, which is already the glide family's stamina resource -- the bp-g2 scale-up plan (not shipped) §6 item 14 freezes `Health/MaxHealth/Power`, so **no new attribute is added**. |
| `Create all assets in the folder: /Game/G2/17/` | "Author any Blueprint assets under `/Game/Tasks/gp-double-jump-stamina-bp/`." (`-bp` only) | Sandbox + L2I `asset_writable` path check; no behavioral gate. | **Re-homed.** `/Game/G2/17/` does not exist; `Content/Maps/` is deny-listed. Precedent: every bp-g2 port. |
| `Start implementing immediately without asking for confirmation` / `Do not reference any other existing assets in the project` | dropped | -- | **Dropped.** Harness-level instruction, not behavior; and the second clause contradicts the substrate (the agent must reference the provided character, its attribute set, and a provided mannequin mesh). Precedent: dropped on all 8 existing bp-g2 ports. |
| `Description: Movement-1` / `Difficulty: medium` / `Before Blueprint: from scratch` | -- | -- | Metadata -> front matter (`tier: T2`, `capability_bucket: Gameplay Programming`). |
| *(not in the row -- family standard)* | "The character must be **visibly represented** ... one of the provided mannequin skeletal meshes under `/Game/Characters/`." | DJ-7. | Owner decision 2026-08-06, applied to the whole glide/poison family. |

### The agent-visible prompt, verbatim (this is the ONLY text the model sees)

> The project provides a character pawn that already owns an ability system, a
> depletable **Power** resource, and an array of abilities to grant.
>
> Implement an **ability** that gives the character a **second jump while it is
> already falling through the air**. When the game activates it mid-fall, the
> character's descent must **reverse and carry it upward again** -- a real
> upward impulse it then falls back down from, not a teleport and not a slowed
> fall.
>
> - Tag the ability `Ability.DoubleJump` and add it to the pawn's granted
>   abilities, so the game can trigger the second jump by that tag.
> - Activating it **costs 20 Power**, debited **once** per activation. It must
>   not drain Power continuously while the character is airborne.
> - If the character has **less than 20 Power**, the ability must **not fire**:
>   no second jump, and Power must not go negative.
> - Deliver your pawn as a subclass of the provided character (C++ or Blueprint)
>   with your ability granted on it.
> - The character must be **visibly represented**: assign one of the provided
>   mannequin skeletal meshes (under `/Game/Characters/`) as your character's
>   mesh, so a reviewer watching the run can see it jump.
>
> The verifier drops the character from a height, waits until it is falling,
> then activates your ability by sending that tag and observes the resulting
> motion and Power.

---

## 2. Gate table

Proposed two-leg schedule. **Leg 1** (the jump + the cost): spawn at `z=1200`,
free-fall through `0.4 / 0.7`; at `t=0.7` preset Power to **60** and trigger
`Ability.DoubleJump`; dense sampling ON from the trigger (V2.3 opt-in) through
`1.0 / 1.3 / 1.6 / 1.9`. **Leg 2** (the refusal): at `t=2.4` preset Power to
**5**, re-trigger; samples `2.7 / 3.0 / 3.3`.

**All bars: `PROPOSED - NOT YET MEASURED`.**

| gate | ratio-or-absolute | measurement window | exact named FAIL string (proposed, ASCII) | defends anti-gaming note | skip-vs-fail |
|---|---|---|---|---|---|
| **DJ-1** ability granted + activated | structural | final | `no activatable ability tagged Ability.DoubleJump on the pawn (the second jump is not an activatable ability). granted=%d` / `an ability tagged Ability.DoubleJump was granted but did NOT activate on TryActivateAbilitiesByTag` | AG-1 | always FAIL |
| **DJ-2a** baseline: really falling pre-trigger | **direction + noise floor** (`vZ < -MinFallSpeed`, PROPOSED 100 cm/s) | sample at the trigger checkpoint | `no falling baseline: the character was not descending when the ability was triggered (vZ=%.0f, need vZ < -%.0f). The second jump is only meaningful from a fall.` | -- (harness sanity) | always FAIL |
| **DJ-2b** a real upward impulse | **PURE DIRECTION** -- `MaxVelocityZAfter(triggerT) > 0` | Leg 1, samples strictly after the trigger | `the ability produced no upward impulse: the highest vertical velocity after the trigger was %.0f, never positive. A real second jump reverses the descent; a teleport leaves vZ at whatever gravity produced.` | AG-2 | always FAIL |
| **DJ-2c** a segmented SECOND rise | **PURE SHAPE** -- rise after a local minimum, `RiseEpsilon` PROPOSED 20 cm | Leg 1, dense samples from trigger to `1.9` | `the character did not rise a second time: Z fell to %.0f and never climbed back by more than %.1f before the leg ended. A one-shot upward velocity that is immediately cancelled, or a slowed fall, looks like this.` | AG-2, AG-3 | always FAIL |
| **DJ-3a** Power was debited | **direction + noise floor** (`PowerEpsilon` PROPOSED 0.5) | preset(60) -> first post-trigger sample | `the second jump cost no Power: Power went %.1f -> %.1f across the activation (delta %.2f). The ability must debit the character's Power.` | AG-4 | always FAIL |
| **DJ-3b** the cost is exactly 20 | **ABSOLUTE (disclosed: 20)**, +/- `CostTol` PROPOSED 1.0 | preset(60) -> first post-trigger sample | `the second jump did not cost 20 Power: Power went 60.0 -> %.1f (debited %.1f, need 20.0 +/- %.1f). The prompt fixes the cost at 20.` | AG-4 | always FAIL |
| **DJ-3c** ONE-SHOT, not a continuous drain | **PURE "stopped changing" predicate** + `PowerEpsilon` | Leg 1, (trigger+0.3, trigger+1.2] -- after the debit has landed | `the Power cost is a continuous drain, not a one-shot debit: Power kept falling after the activation (%.1f at trigger+0.3 -> %.1f at trigger+1.2, further drop %.2f > %.2f). The cost must be charged once per activation.` | AG-5 | always FAIL |
| **DJ-4** refusal below the cost | **PURE DIRECTION x2** | Leg 2, preset Power to 5 | `the ability fired without paying for it: with only 5.0 Power (below the 20 cost) the character still rose a second time (Z climbed %.0f) and/or Power went negative (%.1f). Below the cost the ability must not fire.` | AG-6 | **SKIP-vs-FAIL: see §5 D3.** May hard-FAIL only if DJ-2c passed on Leg 1 -- otherwise the leg proves nothing and is SKIPPED with a `[DJ-REFUSE-DIAG]` line. |
| **DJ-6** *(OPTIONAL)* only ONE extra jump per airborne period | **PURE SHAPE** -- at most one segmented rise after the first trigger | Leg 1, whole dense window, third trigger at `1.3` | `the character rose more than once from repeated activations while airborne: %d separate rises detected after the first trigger. Only one extra jump is available per time in the air.` | AG-7 | **Under-specified as written -- see §5 D4. Cut unless you approve the extra prompt sentence.** |
| **DJ-7** visible character | structural | first checkpoint | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | AG-8 | always FAIL |

**Relative-vs-absolute accounting.** Seven of nine gates are **pure direction or
shape predicates** -- "was it falling", "did vZ ever go positive", "did Z rise
after a local minimum", "did Power stop moving", "did it refuse". None depends
on a magnitude the prompt does not state, and none can be moved by the agent's
choice of jump height or impulse strength. The **one real absolute is DJ-3b
(cost = 20)**, and it is lawful under `TASK-AUTHOR-GUIDE.md` §C only because
the prompt says "**costs 20 Power**" in those words -- which is also the one
number the source row itself specifies. The noise floors (`RiseEpsilon`,
`PowerEpsilon`, `MinFallSpeed`) are floors, not bars: they separate signal from
jitter and must be pinned from measured jitter under `-deterministic -FPS=60`,
never chosen.

**Why there is no "the second jump must reach height H" gate.** The source row
specifies no height, so any such bar would be an undisclosed magnitude floor --
the exact F5 defect sitting in `gp-poison-dot-stack` today
(the bp-g2 scale-up plan (not shipped) §0, owner decision Q5(b)). DJ-2b + DJ-2c ask the
question the task is actually about -- *did the descent reverse* -- with no
magnitude at all.

---

## 3. Anti-gaming notes this defends (floor of 4, not a cap)

1. **AG-1** -- implement the second jump in the character movement component or
   on input, with nothing activatable by tag. Caught by DJ-1.
2. **AG-2** -- teleport the character upward instead of applying an impulse. A
   position teleport leaves vZ at whatever gravity produced (negative), so
   DJ-2b catches it; DJ-2c catches the variant that nudges Z once and lets it
   keep falling.
3. **AG-3** -- reuse the glide answer: slow the descent instead of reversing it.
   `vZ` stays negative throughout -> DJ-2b.
4. **AG-4** -- a free double jump (no debit), or a cosmetic debit of the wrong
   size. Caught by DJ-3a / DJ-3b.
5. **AG-5** -- charge the cost as a per-tick drain while airborne, which
   technically "consumes stamina". Caught by DJ-3c.
6. **AG-6** -- debit Power but never actually gate on it: the jump fires at 0
   Power and the resource goes negative. Caught by DJ-4 -- **this is the gate
   that makes the task about a resource *cost* rather than about a subtraction.**
7. **AG-7** *(only if DJ-6 is kept)* -- unlimited air jumps while Power lasts.
8. **AG-8** -- a meshless pawn, conforming but invisible on the film strip.
   Caught by DJ-7.

---

## 4. MANDATORY concrete before/after pair

*Required because paraphrased confirmation has flip-flopped twice on this
codebase -- both directions sound plausible in prose, so the pair is shown, not
described.*

### A PASSING solve (sketch)

```
BP_DoubleJumpPawn : ACraftBenchCharacter
  + skeletal mesh = /Game/Characters/.../SKM_Manny        (DJ-7 ok)
  + GrantedAbilities = [ GA_DoubleJump ]                  (DJ-1 ok)

GA_DoubleJump (tag Ability.DoubleJump):
  on activate ->  if Power < 20: end ability, do nothing   (DJ-4 ok)
                  else: apply an instant -20 to Power      (DJ-3a/b/c ok)
                        set the character's vertical velocity to +600
                        end ability                        (DJ-2b/2c ok)
```

Leg 1 trace: vZ at trigger `-780` (**DJ-2a**), max vZ after trigger `+600`
(**DJ-2b**), Z falls to a local minimum at the trigger then climbs ~160 cm
before gravity wins (**DJ-2c**), Power `60 -> 40` at the first post-trigger
sample and **flat** thereafter (**DJ-3a/3b/3c**).
Leg 2 trace (Power preset 5): no rise, Power stays `5.0` (**DJ-4**). **PASS.**

### A plausible-WRONG solve (the one a real model writes)

```
GA_DoubleJump (tag Ability.DoubleJump):
  on activate -> apply an instant -20 to Power
                 LaunchCharacter( (0,0,600), XYOverride=false, ZOverride=false )
                 end ability
```

`LaunchCharacter` with `bZOverride = false` **adds** to the existing velocity
instead of replacing it. Mid-fall the character is already at `vZ = -780`, so
`-780 + 600 = -180`: it never goes upward at all. The Power debit is perfect,
the ability activates, the tag is right, the deliverable shape is right -- and
to a reader the code says "launch the character up by 600". It passes DJ-1,
DJ-2a, DJ-3a, DJ-3b, DJ-3c, DJ-4 and DJ-7.

Leg 1 trace: max vZ after trigger `-180` (never positive); Z falls monotonically.

**Caught by DJ-2b, by name:**

> `the ability produced no upward impulse: the highest vertical velocity after the trigger was -180, never positive. A real second jump reverses the descent; a teleport leaves vZ at whatever gravity produced.`

**This is the pair to read hardest.** It is also the reason the prompt says
"**reverse and carry it upward again**" rather than "launch the character
upward": under the second wording, the solve above is arguably conforming and
the FAIL would be unfair. If you prefer the looser wording, DJ-2b must be
downgraded to advisory and the family loses its load-bearing discriminator.

**Secondary wrong solves and the gate that catches each:**

| wrong solve | caught by | named FAIL |
|---|---|---|
| teleport `SetActorLocation(+300 Z)` | DJ-2b | `the ability produced no upward impulse: the highest vertical velocity after the trigger was -812, never positive ...` |
| slow the fall instead (the glide answer) | DJ-2b | same |
| jump is free (no debit) | DJ-3a | `the second jump cost no Power: Power went 60.0 -> 60.0 ...` |
| cost charged as 5/s while airborne | DJ-3c | `the Power cost is a continuous drain, not a one-shot debit: ...` |
| debits Power but jumps anyway at 5 Power | DJ-4 | `the ability fired without paying for it: with only 5.0 Power (below the 20 cost) the character still rose a second time ...` |

---

## 5. Decisions this sheet is asking you to ratify

- **D1 -- THE SEGMENTATION CODE HAS NEVER RUN, and this task is its first
  consumer.** `RoseThenFell`, `ApexDeltaZ`, `ReachedMovementMode`,
  `VelocityZNear` and `MaxVelocityZAfter` on `CraftBenchPawnFunctionalTest` have
  **zero callers** anywhere in the tree; only `RecordSample` is exercised, and
  only from `GlideStaminaFunctionalTest.cpp:55` on a **checkpoint-sparse**
  schedule (`bp-g2-verifier-extensions.md` §0 F2). `RoseThenFell` is
  first-sample -> global-peak -> last-sample: **one bool for the whole series**,
  which cannot see a second rise at all. So: a dedicated **segmentation probe
  fixture must run and be signed off before the first double-jump reference
  run** (V2.3's discipline), and dense sampling must ship **opt-in, default
  OFF**, so glide and poison stay byte-identical and I1.6's numeric-invariance
  check is a re-run rather than a re-calibration. **Treat the entire existing
  sampler as untested code.**
- **D2 -- the refusal clause (DJ-4) is ADDED prose, not in the source row.**
  Without it, "consume 20 stamina" is satisfied by a subtraction that never
  gates anything, and the task measures arithmetic instead of a resource cost.
  Cost: one extra prompt bullet and one extra leg.
- **D3 -- DJ-4 is SKIP-vs-FAIL, on purpose.** If Leg 1's DJ-2c never detected a
  rise, Leg 2's "did not rise" proves nothing (the ability may simply not work),
  so hard-FAILing there would misattribute. Below that condition DJ-4 logs
  `[DJ-REFUSE-DIAG] ... SKIPPED, not failed` -- the same semantics glide's gate
  (5) uses under `ResumeWindowFloor`. **A second, unavoidable ambiguity:** an
  ability with a cooldown that also happens to block the Leg 2 re-trigger is
  indistinguishable from a correct cost gate. Leg 2 therefore sits **1.7 s**
  after the Leg 1 trigger; if calibration finds conforming solves using longer
  cooldowns, DJ-4 must move to a fresh fall rather than tighten.
- **D4 -- DJ-6 ("only one extra jump") is OPTIONAL and currently
  UNDER-SPECIFIED.** The source row says "double jump", which *implies* exactly
  one extra -- but the prompt as written does not say it, and a solve that
  allows repeated air jumps while Power lasts is a defensible reading of
  "costs 20 per activation". **Keep it only if you approve adding this sentence
  to the prompt:** *"Only one extra jump is available per time in the air --
  once used, it is unavailable until the character touches the ground again."*
  Otherwise cut DJ-6 and AG-7. **Recommendation: cut for tier 1** (it adds a
  ground-contact axis the map would then have to guarantee).
- **D5 -- one new tag** (`Ability.DoubleJump`) lands in
  `CraftBenchGameplayTags.{h,cpp}`; `PreferredAbilityTag()` returns it, keeping
  the resolver's per-family uniqueness (I1.1). With
  `gp-health-attribute-ops`'s two tags and `gp-heal-over-time`'s one, tier 1
  adds **4** tags, not the 3 budgeted in the bp-g2 scale-up plan (not shipped) I1.5.
- **D6 -- no new attribute.** The cost is charged against the existing `Power`,
  the same resource `gp-glide-stamina` drains, per §6 item 14
  (`Health/MaxHealth/Power` are frozen so no review-gated scaffold change fires).
  Consequence to accept: this family and glide share a resource, so a matrix
  cell containing both measures Power handling twice. They do **not** share a
  gate or a ladder, so this is a note, not a `QUEUE.md` exclusion.

## 6. What must be true before this reaches G2

The segmentation probe fixture signed off (D1); I1.6's numeric-invariance check
green across the V2.3 base-class change on **both** substrates (the two
`CraftBenchFunctionalTest.cpp` files diff to 0 lines -- 2 PRs, 2 epochs);
reference PASS + empty FAIL; one committed one-delta variant per anti-gaming
note, each dying at its own named substring; and measured jitter populations for
`RiseEpsilon`, `PowerEpsilon`, `MinFallSpeed` and `CostTol` in `notes.md` with
the margin on each side.

---

## OWNER DECISION 2026-08-10 -- **EDIT, then ACCEPTED**

**DJ-6 is CUT.** The sheet flags it "under-specified as written" and offers to
buy it with an extra prompt sentence. Declined: gating "only one extra jump per
airborne period" would enforce a limit the source row never states, and buying it
with added prose is the F5 trade in miniature -- more disclosure debt for a
marginal axis, on a task whose real observable (a second rise that costs a fixed
resource) is already covered by DJ-2c + DJ-3b. A gate nobody can derive from the
prompt is worse than no gate. AG-7 is re-recorded as an ARGUED note pointing at
DJ-2c rather than claiming a defense it does not have.

**Everything else ACCEPTED as written.** Specifically endorsed:

* **DJ-2c is the first real consumer of I1.4** (dense sampling + segmented
  rises). Its `RiseEpsilon` doubles as the segmenter's `MinDeltaZ`, which is what
  absorbs apex noise -- without that absorption one jitter sample at the apex
  splits a single jump into three segments and the gate reads two rises for one
  jump, a false PASS on the exact axis it exists for.
* **DJ-4's skip-vs-fail is right and must not be "simplified".** It may hard-FAIL
  only when DJ-2c passed on Leg 1; otherwise the refusal leg proves nothing about
  refusal and would report a second-jump failure under a resource-gating name.
  Same discipline as glide's window-honest gate (5).
* **DJ-3b's absolute 20 is lawful** only because the source row states it
  ("should consume 20 stamina") and the prompt repeats it.

**Mandatory for the fixture:** log `DescribeSegments()` in the diagnostic line.
I1.4 has never executed -- this reference run is its first test as well as the
task's, and a wrong decomposition must be visible in the log rather than silently
mis-gating.
