# PIN SHEET (G1) -- `gp-heal-over-time-{cpp,bp}`

> ## The one question you are answering
>
> **Given only the prompt in column 2, could a competent gameplay engineer
> produce a passing solution -- and does the wrong solve in §4 actually get
> caught by the FAIL string named beside it?**
>
> Plus one scope decision this family cannot start without: **P1 -- restore the
> clamp gate** (§5 D1). Answer `ACCEPTED`, `EDIT`, or `CUT` in
> the internal design note (not shipped).

**Family:** T1.2. **Source:** source record 47 (`Difficulty: Medium`,
`Before Blueprint: from scratch`). **Substrate:** ThirdPerson. **Layers:**
`-cpp` = L1+L2; `-bp` = L1+L2+L2I. **Blocked on V1.1 + V1.4** (the
GameplayEffect-application substrate and the base-vs-current dual attribute
read). **Status: nothing built. Every number below is `PROPOSED - NOT YET
MEASURED`.**

---

## 1. Sheet row -> prompt -> gate -> drop

`sheet_verbatim` is the literal source record 47, read with `csv.reader`. The
record has only four non-empty cells; all four are shown.

| sheet_verbatim | agent_visible_rewrite | what the fixture asserts | dropped, with precedent |
|---|---|---|---|
| `Update the health potion to use a HoT instead of instantly healing the player.` | "Implement a **restorative ability** the game can activate on the character. When activated it must raise Health **repeatedly - about once per second - for roughly five seconds, then stop** (not a single instant restore, and not a restore that never ends)." | HOT-2 (periodic, still-rising across the in-band window), HOT-3 (stops past the acceptance band). | **The "Update the ..." EDIT framing is dropped** -- owner decision **Q3(a)**, the bp-g2 scale-up plan (not shipped) §7. There is **no health potion in either substrate**, and authoring a baseline potion asset would pull the Edit(Debug) lane (I3.4) onto tier 1's critical path and commit a baseline asset to the substrate's default git state. Re-framed **from-scratch**, which the row's own `Before Blueprint` cell already says. Recorded in `## Dropped clauses`. The word "potion" is dropped with it -- an item/pickup is a second, ungraded axis. |
| `Make it last for 5 seconds.` | "for **roughly five seconds**, then stop" + "The verifier accepts any duration in the four-to-seven-second range." | HOT-3's stop window opens **past** the acceptance-band top. | Nothing dropped. The **acceptance band is disclosed**, which `gp-poison-dot-stack` does not do -- this is the F5 correction (the bp-g2 scale-up plan (not shipped) §0) applied prospectively so the new family does not inherit the exemplar's bug. |
| `Use GAS.` | (no direct sentence -- carried by "an ability the game can activate", "tagged `Ability.HealOverTime`", "add it to the pawn's granted abilities") | HOT-1 (`NumGrantedAbilitiesWithTag >= 1` + activated on tag trigger). | **"GAS" dropped as a name.** Hard Rule #2 / `AUTHORING_TEMPLATE.md:365-380` ("use the X system" is Unacceptable). Precedent: the **documented GAS-category exception** carried by `gp-glide-stamina-cpp` and `gp-poison-dot-stack-cpp` -- name the contract (ability system, provided attribute set, trigger tag), never the plugin. |
| `Before Blueprint: from scratch` / `Difficulty: Medium` | -- | -- | Metadata -> front matter (`tier: T2`, `capability_bucket: Gameplay Programming`). |
| *(not in the row -- required by the restored clamp gate, P1)* | "Health is capped: **MaxHealth is 100**, your pawn must initialize it to 100, and Health must **never exceed it** - not the value the game reads, and not the underlying stored value. Restoring at full health must leave Health at 100 and must not lower it." | HOT-5 (clamp, dual read), HOT-6 (at-max no-op), HOT-0 (MaxHealth reads 100). | Nothing dropped -- this is **added** prose. It is the §C disclosure price of P1: four numbers must be pinned in the prompt (rate band, ~1/s cadence, ~5 s duration, MaxHealth=100). Recorded in `bp-g2-verifier-extensions.md` §3a as "more §C under-specification debt than poison carries". |
| *(not in the row -- family standard)* | "The character must be **visibly represented** ... assign one of the provided mannequin skeletal meshes (under `/Game/Characters/`)." | HOT-7. | Added by owner decision 2026-08-06, applied to the whole glide/poison family; this family inherits it. |
| *(not in the row -- path re-homing)* | "Author any Blueprint assets under `/Game/Tasks/gp-heal-over-time-bp/`." (`-bp` only) | Sandbox / L2I path check. | The row names no path, but the family convention re-homes every `/Game/G2/N/` to `/Game/Tasks/<id>/`; `Content/Maps/` is deny-listed. |

### The agent-visible prompt, verbatim (this is the ONLY text the model sees)

> The project provides a character pawn that already owns an ability system and
> a **Health** resource through the attribute set type the project provides.
>
> Implement a **restorative ability** the game can activate on that character.
> When activated, it must raise Health **repeatedly - about once per second -
> for roughly five seconds, then stop**. It must not be a single instant
> restore, and it must not keep restoring forever. The verifier accepts any
> duration in the four-to-seven-second range, and each application must restore
> a total of between **10 and 40** Health across its lifetime.
>
> - Tag the ability `Ability.HealOverTime` and add it to the pawn's granted
>   abilities, so the game can start the effect by that tag.
> - **Health is capped.** MaxHealth is **100**, and your pawn must initialize
>   MaxHealth to 100. Health must **never exceed** MaxHealth -- neither the
>   value the game reads back, nor the underlying stored value it accumulates
>   into. Activating the ability while the character is already at full health
>   must leave Health at 100: it must not push past it, and it must not lower it.
> - Deliver your pawn as a subclass of the provided character (C++ or Blueprint)
>   with your ability granted on it.
> - The character must be **visibly represented**: assign one of the provided
>   mannequin skeletal meshes (under `/Game/Characters/`) as your character's
>   mesh, so a reviewer watching the run can see it.
>
> The verifier sets Health to a known value, activates your ability by sending
> that tag, and observes Health over time.

---

## 2. Gate table

Proposed three-leg schedule, sign-flipped from `PoisonStackFunctionalTest`'s
Leg A and re-using its congruent-window discipline. **Leg 1** (periodic +
stop): preset Health to **40** at `t=0.5`, trigger; samples at `1.6 / 3.1 / 4.6`
(the in-band rate window, trigger+4.1), stop window `7.6 -> 9.7`
(trigger+7.1 -> +9.2, opening **past** the band top). **Leg 2** (clamp):
`t=10.7` preset Health to **95**, trigger; read at `15.8` (trigger+5.1, past
every conforming duration). **Leg 3** (at-max no-op): `t=17.0` preset Health to
**100**, trigger; read at `22.1`.

**All bars: `PROPOSED - NOT YET MEASURED`.**

| gate | ratio-or-absolute | measurement window | exact named FAIL string (proposed, ASCII) | defends anti-gaming note | skip-vs-fail |
|---|---|---|---|---|---|
| **HOT-0** MaxHealth initialized to 100 | **ABSOLUTE (disclosed)** -- 100, +/- 0.5 | cp0, before any trigger | `MaxHealth was not initialized: read %.1f, expected 100 (+/- %.2f). The cap the restore must respect is read from the pawn's own MaxHealth attribute; an uninitialized attribute reads 0 and would clamp every restore to zero.` | AG-1 | **always FAIL, and it must run FIRST.** See §5 D3 -- without it every later gate misattributes. |
| **HOT-1** ability granted + activated | structural | final | `no activatable ability tagged Ability.HealOverTime on the pawn (the restore is not an activatable ability). granted=%d` / `an ability tagged Ability.HealOverTime was granted but did NOT activate on TryActivateAbilitiesByTag` | AG-2 | always FAIL |
| **HOT-1c** EVERY activation landed (3 legs, 3 attempts) | structural (counters, not an OR-ed latch) | final | `an ability tagged Ability.HealOverTime refused a later activation: %d of %d activations were accepted.` | AG-2 | always FAIL. **Row added 2026-08-11 — this gate SHIPPED in the fixture (`HealOverTimeFunctionalTest.cpp` "HOT-1c") but was missing from this table, the T1.2 authoring-agent objection logged in `../QUEUE.md`.** Why it exists: a refused leg-2/leg-3 activation leaves Health at that leg's preset, and HOT-5/HOT-6 then pass **vacuously** — the two gates this family exists for would go green having tested nothing. Same pattern as HO-6c. |
| **HOT-2** periodic: Health kept **rising** in steps | **PURE DIRECTION + noise floor** `RiseEpsilon` (PROPOSED 0.5) -- explicitly **not** a rate bar | Leg 1, samples at trigger+1.1 / +2.6 / +4.1 (two congruent 1.5 s windows) | `the restore was not periodic: Health did not keep rising in steps (A1=%.1f A2=%.1f A3=%.1f; each step must rise by more than %.2f). An instant restore rises once then stays flat.` | AG-3 | always FAIL |
| **HOT-3** stops after its duration | **noise floor** `StopEpsilon`, **0.25** (owner EDIT 2026-08-10; was 0.7), pinned against `StopEpsilon < 1.0 * RiseEpsilon` -- see the OWNER EDIT block below | Leg 1 stop window (trigger+7.1, trigger+9.2] | `the restore did not STOP after its duration: Health was still rising in the post-band stop window (AStop=%.1f at trigger+7.1 -> ATail=%.1f at trigger+9.2, rise %.1f > %.2f). The fixture accepts any duration in the 4-7s band; a heal-over-time must end, a permanent regeneration keeps climbing.` | AG-4 | always FAIL |
| **HOT-4** total restored inside the disclosed band | **ABSOLUTE (disclosed: 10..40)** | Leg 1, preset(40) -> ATail | `the total restored is outside the stated 10-40 band: Health went 40.0 -> %.1f over one application (total %.1f). The prompt fixes a per-application total between 10 and 40.` | AG-6 | always FAIL |
| **HOT-5** clamp: Health never exceeds MaxHealth -- **read BOTH current and base** | **ABSOLUTE (disclosed)** -- `<= MaxHealth + ClampEpsilon`, `ClampEpsilon` PROPOSED 0.5 | Leg 2, at trigger+5.1 | `the restore pushed Health past its cap: current=%.1f base=%.1f against MaxHealth=%.1f (+/- %.2f). Health must never exceed MaxHealth - neither the value read back nor the underlying stored value.` | AG-5 | always FAIL |
| **HOT-6** at-max no-op: full health stays full | **direction + noise floor** (both ways) | Leg 3, preset(100) -> trigger+5.1 | `activating the restore at full health changed Health: 100.0 -> %.1f (base %.1f). At full health the effect must leave Health at MaxHealth - it must neither push past it nor lower it.` | AG-5 | always FAIL |
| **HOT-7** visible character | structural | cp0 | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | AG-7 | always FAIL |

**The dual read in HOT-5 is the whole point of the gate.** A
`PreAttributeChange`-only clamp -- the most-documented recipe -- writes only
`CurrentValue` (`AttributeSet.cpp:94-95`), so `GetNumericAttribute` reads
exactly 100 while the base value sits at ~117: it passes a current-only clamp
gate with a health system that silently absorbs the next 17 damage. Reading
only the current value makes HOT-5 **vacuous**
(`bp-g2-verifier-extensions.md` §1a M3). This is why the family is blocked on
**V1.4**.

**Relative-vs-absolute accounting.** HOT-2 and HOT-3 are **pure direction
predicates with a noise floor** -- deliberately *not* the rate bars poison uses.
This is owner decision **Q5(b)** applied prospectively: `PeriodicMinStep = 2.0`
over a 1.5 s window is an undisclosed `> 1.33 HP/s` floor, and a conforming
1 HP/s effect fails it with the wrong message. HOT-2 asks only "is it still
moving", so any conforming rate passes. The absolutes that remain (100, the
10-40 band, the epsilons) are each stated in the prompt; `MaxHealth = 100` is
unavoidable because a cap **is** an absolute -- there is no ratio form of "does
not exceed its own maximum".

**`StopEpsilon` is coupled to `RiseEpsilon` and cannot be pinned
independently.** The stop window is 2.1 s; a permanent regeneration at the
slowest *now-lawful* rate gains about `1.4 * RiseEpsilon` across it, so HOT-3
has teeth only while `StopEpsilon < 1.4 * RiseEpsilon`. At `RiseEpsilon = 0.5`
that is `StopEpsilon < 0.7`. **That tightening is only safe if measured**: pin
it midway between the reference's actual `ATail - AStop` jitter across >= 3
reps and `1.4 * RiseEpsilon`, recording both populations. Same derivation as
the bp-g2 scale-up plan (not shipped) §7.1.

---

## 3. Anti-gaming notes this defends (floor of 4, not a cap)

1. **AG-1** -- leave MaxHealth at its default 0 so "never exceeds the cap" is
   trivially satisfiable in the wrong direction. Caught by HOT-0.
2. **AG-2** -- restore Health from Tick / BeginPlay with nothing activatable.
   Caught by HOT-1.
3. **AG-3** -- one instant restore of the full amount, dressed as an ability.
   Caught by HOT-2 (rises once, then flat).
4. **AG-4** -- permanent regeneration that never expires. Caught by HOT-3.
5. **AG-5** -- clamp only the value the game reads while the stored value
   overshoots (the `PreAttributeChange`-only recipe), or "clamp" by *setting*
   Health to MaxHealth (which lowers it when already above). Caught by HOT-5's
   dual read and HOT-6.
6. **AG-6** -- restore a token 1 HP so every window technically rises. Caught by
   HOT-4's disclosed band.
7. **AG-7** -- a meshless pawn, conforming but invisible on the film strip.
   Caught by HOT-7.

---

## 4. MANDATORY concrete before/after pair

*Required because paraphrased confirmation has flip-flopped twice on this
codebase -- both directions sound plausible in prose, so the pair is shown, not
described.*

### A PASSING solve (sketch)

```
BP_HoTPawn : ACraftBenchCharacter                       (health pre-built)
  + MaxHealth initialized to 100                        (HOT-0 ok)
  + skeletal mesh = /Game/Characters/.../SKM_Manny      (HOT-7 ok)
  + GrantedAbilities = [ GA_HealOverTime ]              (HOT-1 ok)

GA_HealOverTime (tag Ability.HealOverTime): on activate, apply a duration
  effect: Duration 5.0s, Period 1.0s, modifier Health +4 per period,
  and clamp in the attribute set's PreAttributeChange AND in
  PostGameplayEffectExecute (so the stored base value is clamped too).
```

Leg 1 (preset 40): `40 -> 44 -> 52 -> 60`, flat from ~5.5 s.
`A1=44, A2=52, A3=60` (**HOT-2**: steps +8, +8 > 0.5), stop window `60 -> 60`
(**HOT-3**: rise 0.0 < 0.7), total 20 in `[10,40]` (**HOT-4**).
Leg 2 (preset 95): would accumulate to 115, clamps -> current **100.0**, base
**100.0** (**HOT-5**). Leg 3 (preset 100): stays **100.0** (**HOT-6**). **PASS.**

### A plausible-WRONG solve (the one a real model writes)

```
The attribute set overrides PreAttributeChange only:
    if (Attribute == GetHealthAttribute())
        NewValue = FMath::Clamp(NewValue, 0.f, GetMaxHealth());
...and nothing else. PostGameplayEffectExecute is not overridden.
```

This is the recipe every GAS tutorial shows, it is what "Health must never
exceed MaxHealth" reads like to a competent engineer, and it passes HOT-0
through HOT-4, HOT-6 and HOT-7. It is wrong because a **periodic** effect
executes into the **base** value: `PreAttributeChange` guards `CurrentValue`
only (`AttributeSet.cpp:94-95`), so the read-back is a clean 100 while the
stored base has accumulated to ~115 -- and the next 15 points of damage do
nothing at all.

Leg 2 trace (preset 95, +4 per period x 5): current **100.0**, base **115.0**.

**Caught by HOT-5, by name:**

> `the restore pushed Health past its cap: current=100.0 base=115.0 against MaxHealth=100.0 (+/- 0.50). Health must never exceed MaxHealth - neither the value read back nor the underlying stored value.`

**This is the pair to read hardest**, and it is the reason the prompt says "not
the value the game reads back, nor the underlying stored value it accumulates
into" -- clumsy prose that exists solely so this FAIL is fair under §C. If you
think that sentence is too much of a hint (it does gesture at *how* attributes
are stored), the alternatives are: **(i)** keep it and accept the hint; **(ii)**
delete it and grade only the read-back, which makes HOT-5 vacuous and P1
pointless; **(iii)** replace it with an observable consequence -- *"after the
restore ends, the next damage the character takes must reduce Health by its full
amount"* -- which grades the same defect through behavior and needs one extra
fixture leg. **Recommendation: (iii) if you have an appetite for one more leg,
(i) otherwise.** Say which.

**Secondary wrong solves and the gate that catches each:**

| wrong solve | caught by | named FAIL |
|---|---|---|
| instant +20, dressed as an ability | HOT-2 | `the restore was not periodic: Health did not keep rising in steps ...` |
| permanent regeneration, no duration | HOT-3 | `the restore did not STOP after its duration: ...` |
| "clamp" by setting Health = MaxHealth on activation | HOT-6 | `activating the restore at full health changed Health: ...` (and it lowers Health when above) |
| MaxHealth left at its default | HOT-0 | `MaxHealth was not initialized: read 0.0, expected 100 ...` |

---

## 5. Decisions this sheet is asking you to ratify

- **D1 -- P1: RESTORE THE CLAMP GATE.** the bp-g2 scale-up plan (not shipped) §6 item 2 cut
  every clamp-at-MaxHealth gate on F3; **all three legs of F3 are refuted**
  (`AttributeSet.h:184` is `UCLASS(..., Blueprintable, ...)`; the 3-line
  substrate `.cpp` is irrelevant because `GetAttributeSubobject` matches on
  `IsA`; the `-bp` lane has two proven clamp routes). Approving costs V1.1+V1.4
  (~285 LOC, one PR, compile-only) **before** this task is authored, then grows
  the fixture from ~420 to ~800 LOC, adds a ~380-line introspect script with a
  new native-decoy sweep, and requires **two extra authored BP solves built
  purely to calibrate `ClampEpsilon`** (MMC lane + ability-loop lane).
  Calibrating only against the C++ `PreAttributeChange` reference is exactly how
  this fixture would false-FAIL a conforming BP solve. **Declining leaves the
  benchmark with zero invariant-enforcement gates and this task a sign-flipped
  poison clone.** Ledger recommendation: APPROVE.
- **D2 -- this family derives from the GENERIC character, not the bare one.**
  Health is pre-built; stage 1 is *not* part of this task. That is deliberate:
  routing it through `ACraftBenchBareCharacter` would make it a third member of
  the stage-1 correlation set with `gp-poison-dot-stack` and
  `gp-health-attribute-ops`, and constraint **C1** in `QUEUE.md` would grow to a
  three-way exclusion -- costing tier 1 a usable graded cell. Cost of this
  choice: the agent gets Health for free, so the task is slightly easier than
  the plan's Band-B estimate.
- **D3 -- HOT-0 must be the first gate, before any trigger.** `MaxHealth` ships
  **uninitialized** in `UCraftBenchAttributeSet` (it reads **0**; verified this
  session -- there is no initializer anywhere in either substrate). A pawn that
  never sets it clamps every restore to 0, and without HOT-0 that presents as
  "the restore was not periodic" -- a misattributed FAIL on a submission whose
  only fault is one missing initializer. This is the poison stage-1 lesson
  applied here.
- **D4 -- the periodic leg presets Health to 40, far from both boundaries.**
  The clamp legs are **separate legs with their own presets**. F3's objection --
  "clamp -> saturation stops the periodic steps" -- is real but is a *schedule*
  problem, not a mechanism problem: it only bites if the periodic gate and the
  clamp gate share a leg. 40 + the disclosed 10-40 total can never reach 100, so
  no conforming solve saturates inside the HOT-2 window. **This is the single
  highest-risk calibration constraint in the family** -- if a later edit moves
  the preset or widens the total band, HOT-2 starts false-FAILing conforming
  work.
- **D5 -- one new tag** (`Ability.HealOverTime`) lands in
  `CraftBenchGameplayTags.{h,cpp}`, distinct from `gp-health-attribute-ops`'s
  `Ability.Heal` so `PreferredAbilityTag()` stays unique per GAS family (I1.1).

## 6. What must be true before this reaches G2

V1.1 + V1.4 merged and `cb refgate gp-poison-dot-stack-cpp,gp-glide-stamina-cpp`
green (proving the base-class extension changed no existing verdict); reference
PASS + empty FAIL; one committed one-delta variant per anti-gaming note (7),
each dying at its own named substring; **both** measured populations for
`RiseEpsilon`, `StopEpsilon`, `ClampEpsilon` and the total-restored band in
`notes.md`, with the margin each side and the `StopEpsilon < 1.4 * RiseEpsilon`
inequality it is pinned against; and `ClampEpsilon` measured against **three**
solves -- the C++ `PreAttributeChange`+`PostGameplayEffectExecute` reference,
a BP magnitude-calculation lane, and a BP ability-loop lane.

---

## OWNER DECISION 2026-08-10 -- **EDIT, then ACCEPTED**

Signed by the acting owner. One change was required before any fixture code:

**`StopEpsilon` 0.7 -> 0.25, and its derivation is corrected.**

The sheet pinned `StopEpsilon < 1.4 * RiseEpsilon`. That 1.4 came from a
`(2.1s stop window / 1.5s rise window)` ratio -- reasoning as if tick density
scaled with window length. **It does not: ticks are discrete.** Minimising
`nStop / min(nRise)` over every admissible period on a 1 ms grid against THIS
schedule gives a global minimum of **exactly 1.000, and it is attained** (e.g.
period 0.576 s: 3 ticks in each 1.5 s rise window, 3 in the 2.1 s stop window).

So the lawful bound is `StopEpsilon < 1.0 * RiseEpsilon = 0.50`, and the
proposed 0.7 is **above** it. A PERMANENT regeneration at the slowest rate that
still satisfies HOT-2 leaves >= 0.5 in the stop window, and `0.5 <= 0.7` PASSES
-- i.e. HOT-3 would not defend AG-4, in a family authored specifically to avoid
inheriting that bug. **This is poison's Leg-A defect reproduced**, and it is in
the sheet because the erroneous 1.4 was mine, written before I corrected it on
the poison side; the sheet faithfully inherited it.

Pinned at **0.25** = midway between the conforming population (0.0 -- a heal
that stops leaves exactly zero rise in a window opening past the band top, the
same structural argument measured on poison) and the 0.50 bound. Equal margin
each side, the `StackRatioMax` form.

**Consequence for authoring:** the fixture must carry this derivation in a
comment quantified over ALL admissible periods, not over one assumed tick count.
Assuming a tick count is precisely the defect.

Everything else in this sheet is **ACCEPTED as written** -- in particular the
disclosed 4-7 s acceptance band (the F5 correction applied prospectively, which
poison still lacks), HOT-2 as a pure direction predicate rather than a rate bar,
and the HOT-5 dual read, without which the clamp gate is vacuous against the
most-documented `PreAttributeChange` recipe.
