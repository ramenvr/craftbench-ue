# PIN SHEET (G1) -- `gp-health-attribute-ops-{cpp,bp}`

> ## The one question you are answering
>
> **Given only the prompt in column 2, could a competent gameplay engineer
> produce a passing solution -- and does the wrong solve in §4 actually get
> caught by the FAIL string named beside it?**
>
> Answer `ACCEPTED`, `EDIT` (with what to change), or `CUT` in
> the internal design note (not shipped). An `EDIT` comes back to you as a before/after prompt
> diff, re-signed, before any fixture code is written.

**Family:** T1.1 - the Band-A floor. **Source:** source record 29 ("Health-1",
`medium`). **Substrate:** ThirdPerson. **Layers:** `-cpp` = L1+L2; `-bp` =
L1+L2+L2I. **Status: nothing built. Every number below is `PROPOSED - NOT YET
MEASURED`.**

---

## 1. Sheet row -> prompt -> gate -> drop

`sheet_verbatim` is the literal source record 29, read with `csv.reader`. The
`Prompt` cell's trailing `"` is **in the source file**; it is reproduced, not a
transcription slip.

| sheet_verbatim | agent_visible_rewrite | what the fixture asserts | dropped, with precedent |
|---|---|---|---|
| `I want to implement a health system` | "The project provides a **task character pawn** that owns an ability system but **no health resource yet** ... **Stage 1 - build the health system.** Give your pawn a **Health** attribute exposed through its ability system, using the attribute set type the project provides. Health must be **initialized to 100** and must be readable AND writable through the standard attribute APIs (the verifier both reads it and writes it)." | HO-1..HO-4, the stage-1 ladder, at checkpoint 0 before anything else runs. | Nothing dropped. This clause is lifted **verbatim** from `gp-poison-dot-stack`'s stage 1 -- that is deliberate (it is why this task costs zero new infra) and it is exactly what makes constraint **C1** in `QUEUE.md` binding. |
| `Implement this using GAS attributes for the health and max health values and GAS effects for the operations on these values` | (no direct sentence -- carried by "exposed through its ability system", "using the attribute set type the project provides", and "activate ... by that tag") | HO-2 (`HasAttributeSetForAttribute(Health)`), HO-6 (`NumGrantedAbilitiesWithTag >= 1`). | **"GAS" and "GameplayEffect" dropped as names.** Hard Rule #2; `AUTHORING_TEMPLATE.md:365-380` lists plugin names and "use the X system" phrasing as Unacceptable. Precedent: `gp-glide-stamina-cpp` / `gp-poison-dot-stack-cpp` both carry a **documented GAS-category exception** that names the *contract* (an ability system, an attribute set type the project provides, a trigger tag) and never the plugin. **"max health values" dropped as a gated concept** -- see the MaxHealth note in §5; upward clamping is `gp-heal-over-time`'s axis, not this one, and gating it here would double-book the two families. |
| `Create a new actor based on AGSCModularCharacter to implement this on` | "Deliver your pawn as a subclass of the provided task character (C++ or Blueprint) with your abilities granted on it." | HO-1: `Pawn->IsA(ACraftBenchBareCharacter::StaticClass())`. | **`AGSCModularCharacter` re-homed.** The class exists in **neither substrate** (it is GAS Companion; the repo is vanilla GAS). Rebased onto the committed abstract task base `ACraftBenchBareCharacter`, named only behaviorally ("the provided task character"). Precedent: identity-by-derivation, `CraftBenchPawnFunctionalTest.h:117-123`. |
| `Use the existing attribute set type: GSCAttributeSet` | "using the attribute set type the project provides" | HO-2 reads `UCraftBenchAttributeSet::GetHealthAttribute()`; `GetAttributeSubobject` matches on `IsA`, so an agent subclass of the contract set resolves. | **`GSCAttributeSet` re-homed** -- absent from both substrates. The contract class is `UCraftBenchAttributeSet` and is never named to the agent. |
| `It should contain functionality for: TakeDamage, Heal` | "Implement two abilities the game can activate on your character: one that **damages** it (Health goes down) and one that **heals** it (Health goes up). Tag them `Ability.Damage` and `Ability.Heal` and add both to the pawn's granted abilities... Each application of either ability changes Health by a **fixed amount between 5 and 25**, and **one heal restores exactly as much Health as one damage removes**." | HO-6..HO-10 (granted+activated, direction, magnitude band, repeatability ratio, symmetry ratio). | **The function names `TakeDamage` / `Heal` are dropped as names.** They are *deliverables*, not starting workspace state, so `AUTHORING_TEMPLATE.md:368-373` forbids naming them (same reasoning that keeps `BPI_Grabbable`'s four functions out of CSV 43 -- `bp-g2-verifier-extensions.md` §3c). **The seam is therefore a gameplay tag, not a reflected function** -- see §5 D1: this is the single biggest departure from the bp-g2 scale-up plan (not shipped) §1, which assumed `DoDamage`/`DoHeal` reflected seams. |
| `Create all assets in the folder: /Game/G2/8/` | "Author any Blueprint assets under `/Game/Tasks/gp-health-attribute-ops-bp/`." (`-bp` prompt only) | Sandbox + L2I `asset_writable` path check; no behavioral gate. | **Re-homed.** `/Game/G2/8/` does not exist and `Content/Maps/` is deny-listed. Precedent: every bp-g2 port re-homes its `/Game/G2/N/` path; the `AGENT_WRITABLE.json` `asset_writable` allowlist accepts `Content/Tasks/`. |
| `Start implementing immediately without asking for confirmation` / `Do not reference any other existing assets in the project"` | dropped | -- | **Dropped.** Harness-level instructions, not behavior. The second clause also contradicts the substrate (the agent *must* reference the provided character and attribute set). Precedent: dropped on all 8 existing bp-g2 ports. |
| `Category: Full Prompt` / `Difficulty: medium` / `Concepts: GAS attribute, GAS effect` / `Before Blueprint: from scratch` | -- | -- | Metadata; recorded in front matter (`tier: T1`, `capability_bucket: Gameplay Programming`), not in the prompt. |

### The agent-visible prompt, verbatim (this is the ONLY text the model sees)

> The project provides a **task character pawn** that owns an ability system but
> **no health resource yet** (the project also contains a generic character with
> a pre-built attribute set, used by other tasks -- your pawn must be a subclass
> of the *task* character, not the generic one). Build the feature in two
> stages, in order:
>
> **Stage 1 - build the health system.** Give your pawn (a subclass of the
> provided task character) a **Health** attribute exposed through its ability
> system, using the attribute set type the project provides. Health must be
> **initialized to 100** and must be readable AND writable through the standard
> attribute APIs (the verifier both reads it and writes it).
>
> **Stage 2 - the two operations.** Implement two abilities the game can
> activate on your character:
>
> - a **damage** ability, tagged `Ability.Damage`, which lowers Health;
> - a **heal** ability, tagged `Ability.Heal`, which raises Health.
>
> Add both to the pawn's granted abilities so the game can activate each one by
> its tag. Each application of either ability changes Health by a **fixed
> amount between 5 and 25** -- the same amount every time it is applied -- and
> **one heal restores exactly as much Health as one damage removes**. Neither
> ability may change Health except when it is activated.
>
> - Deliver your pawn as a subclass of the provided task character (C++ or
>   Blueprint) with both abilities granted on it.
> - The character must be **visibly represented**: assign one of the provided
>   mannequin skeletal meshes (under `/Game/Characters/`) as your character's
>   mesh, so a reviewer watching the run can see it.
>
> The verifier sets Health to a known value, then activates your abilities by
> sending those tags, and observes how Health moves.

*(`-bp` prompt adds one line: "Deliver the pawn as a Blueprint asset under
`/Game/Tasks/gp-health-attribute-ops-bp/`." -- same convention as
`gp-poison-dot-stack-bp`.)*

---

## 2. Gate table

Proposed schedule (single leg, no reset needed): checkpoints
`{0.5, 1.2, 1.9, 2.6, 3.3}`. cp0 = stage-1 ladder + preset Health to 60 +
trigger `Ability.Damage`. cp1 = read, trigger damage again. cp2 = read, trigger
`Ability.Heal`. cp3 = read. cp4 = read (idle -- nothing triggered).

**All bars: `PROPOSED - NOT YET MEASURED`.**

| gate | ratio-or-absolute | measurement window | exact named FAIL string (proposed, ASCII) | defends anti-gaming note | skip-vs-fail |
|---|---|---|---|---|---|
| **HO-1** pawn derives from the task base | structural | cp0, before any write | `stage 1 not built: the graded pawn (%s) does not derive from the provided task base pawn (CraftBenchBareCharacter). An empty submission resolves to the generic scaffold pawn; a submission subclassing the generic scaffold pawn inherits a pre-built health system and skips stage 1.` | AG-1 (inherit the pre-built set) | always FAIL |
| **HO-2** ASC carries Health | structural | cp0 | `stage 1 not built: the pawn's health attribute system is absent - the ASC has no attribute set exposing Health, so reads return 0 and writes no-op. A pawn that never builds (or detaches) the contract attribute set looks exactly like this.` | AG-1 | always FAIL |
| **HO-3** Health initializes to 100 | **ABSOLUTE (disclosed)** -- 100, +/- 0.5 | cp0, read BEFORE any fixture write | `stage 1 incomplete: Health must initialize to 100 but read %.1f before any fixture write (|delta| %.2f > %.2f). An attribute set that is registered but never initialized reads 0 here.` | AG-1 | always FAIL |
| **HO-4** write-then-read at 37 | structural (37 != 100 on purpose) | cp0 | `stage 1 incomplete: health attribute is inert, write-then-read failed (wrote %.1f, read back %.1f, |delta| %.2f > %.2f). An inert or shadowed attribute set accepts the write but keeps reading its own value.` | AG-2 (inert/shadowed set) | always FAIL |
| **HO-5** visible character | structural | cp0 | `the character is not visibly represented: no mesh component with an assigned mesh on the graded pawn` | AG-5 | always FAIL |
| **HO-6** both abilities granted + activated | structural counts | final | `no activatable ability tagged %s on the pawn (health operations not implemented as activatable abilities). granted=%d` / `an ability tagged %s was granted but did NOT activate on TryActivateAbilitiesByTag` | AG-3 (poke the attribute directly, no ability) | always FAIL |
| **HO-7** damage lowers Health | **direction + noise floor** (`DeltaEpsilon`, PROPOSED 0.5) | (cp0 trigger, cp1] | `the damage operation did not lower Health: Health went %.1f -> %.1f across the first application (delta %.2f, need a drop > %.2f).` | AG-3 | always FAIL |
| **HO-8** per-application magnitude inside the disclosed band | **ABSOLUTE (disclosed: 5..25)** | (cp0, cp1] | `the per-application Health change is outside the stated 5-25 band: one damage moved Health by %.1f. The prompt fixes a per-application amount between 5 and 25.` | AG-4 | always FAIL |
| **HO-9** repeatability | **RATIO** -- `drop2/drop1` in `[1-RepeatTol, 1+RepeatTol]`, `RepeatTol` PROPOSED 0.10 | (cp0,cp1] vs (cp1,cp2] -- **congruent windows, equal length** | `the damage operation is not a fixed amount: the first application removed %.1f and the second removed %.1f (ratio %.2f, need %.2f-%.2f). A one-shot that sets Health to a constant removes a different amount the second time.` | AG-4 (set-to-a-constant fake) | always FAIL |
| **HO-10** heal/damage symmetry | **RATIO** -- `healDelta/drop1` in `[1-SymTol, 1+SymTol]`, `SymTol` PROPOSED 0.10 | (cp2,cp3] vs (cp0,cp1] | `heal does not restore what damage removes: one damage removed %.1f but one heal restored %.1f (ratio %.2f, need %.2f-%.2f). Restoring to full health, or healing a different amount, fails here.` | AG-4 | always FAIL |
| **HO-11** the operations are event-driven, not a passive drift | **direction + noise floor** | (cp3, cp4] -- nothing triggered | `Health kept moving with no operation active: %.1f -> %.1f in the idle window (|delta| %.2f > %.2f). Damage and heal must change Health only when activated.` | AG-6 (tick-driven regen that fakes the heal) | always FAIL |

**Relative-vs-absolute accounting.** 3 of 11 gates are absolute
(HO-3 = 100, HO-8 = the 5..25 band, and the epsilons). Under
`TASK-AUTHOR-GUIDE.md` §C each is lawful only because the prompt states it:
"initialized to **100**" (HO-3) and "a **fixed amount between 5 and 25**"
(HO-8). **HO-8 exists specifically so a non-conforming magnitude fails by name
instead of being misattributed to HO-9 or HO-10** -- an agent that picks a
per-application amount of 60 would otherwise trip the floor clamp mid-leg and
be told its damage "is not a fixed amount", which is the F5 failure mode
(the bp-g2 scale-up plan (not shipped) §0) reproduced in a new task. The two load-bearing
discriminators (HO-9, HO-10) are **pure ratios of two windows this same run
produced** and are unaffected by the agent's choice of magnitude.

---

## 3. Anti-gaming notes this defends (floor of 4, not a cap)

1. **AG-1** -- subclass the *generic* character and inherit its pre-built
   attribute set, skipping stage 1 entirely. Caught by HO-1/HO-2/HO-3.
2. **AG-2** -- register an attribute set that reads its own shadow value and
   ignores writes. Caught by HO-4 (write probe at 37, deliberately != 100).
3. **AG-3** -- change Health from a Tick or from BeginPlay with no ability
   granted, so the numbers move but nothing is activatable. Caught by HO-6 + HO-11.
4. **AG-4** -- "damage" implemented as *set Health to a constant*, or "heal"
   implemented as *restore to full*. Both move Health in the right direction and
   both fail the ratio pair HO-9/HO-10.
5. **AG-5** -- a meshless pawn: conforming but invisible to a human reviewing
   the film strip. Caught by HO-5 (measured 2026-08-04: 9/9 matrix reps shipped
   meshless pawns).
6. **AG-6** -- a passive regeneration loop that makes the heal look like it
   worked. Caught by HO-11's idle window.

---

## 4. MANDATORY concrete before/after pair

*Required because paraphrased confirmation has flip-flopped twice on this
codebase -- both directions sound plausible in prose, so the pair is shown, not
described.*

### A PASSING solve (sketch)

```
BP_HealthPawn : ACraftBenchBareCharacter          (HO-1 ok)
  + attribute-set subobject "HealthAttributes" of the provided set type
      Health initialized to 100                    (HO-2, HO-3, HO-4 ok)
  + skeletal mesh = /Game/Characters/Mannequins/.../SKM_Manny  (HO-5 ok)
  + GrantedAbilities = [ GA_Damage, GA_Heal ]      (HO-6 ok)

GA_Damage  (tag Ability.Damage): on activate, apply an instant -10 to Health, end.
GA_Heal    (tag Ability.Heal):   on activate, apply an instant +10 to Health, end.
```

Fixture trace: preset 60 -> damage -> 50 -> damage -> 40 -> heal -> 50 -> idle -> 50.
`drop1 = 10`, `drop2 = 10` (**HO-9 ratio 1.00**), `healDelta = 10`
(**HO-10 ratio 1.00**), idle delta 0 (**HO-11 ok**), magnitude 10 in `[5,25]`
(**HO-8 ok**). **PASS.**

### A plausible-WRONG solve (the one a real model writes)

```
GA_Heal (tag Ability.Heal): on activate, set Health = MaxHealth.   <-- "heal the player"
```

This is a *reasonable-sounding* reading of "a heal ability which raises Health",
it moves Health in the right direction, it is activatable by tag, it is not a
Tick hack, and it passes HO-1 through HO-7 and HO-11. It is wrong because the
prompt says *"one heal restores exactly as much Health as one damage removes"*.

Fixture trace: preset 60 -> 50 -> 40 -> **heal -> 100** -> idle -> 100.
`healDelta = 60`, `drop1 = 10`, ratio **6.00**.

**Caught by HO-10, by name:**

> `heal does not restore what damage removes: one damage removed 10.0 but one heal restored 60.0 (ratio 6.00, need 0.90-1.10). Restoring to full health, or healing a different amount, fails here.`

**This is the pair to read hardest.** If you think "set Health to full" *should*
pass, the fix is a prompt EDIT (drop the symmetry sentence and delete HO-10),
not a fixture change -- and the task then loses its only defense against a heal
that ignores its own magnitude. Say which you want.

**Secondary wrong solves and the gate that catches each** (no fixture code
beyond the table above):

| wrong solve | caught by | named FAIL |
|---|---|---|
| damage = `Health = 0` ("kill it") | HO-9 | `the damage operation is not a fixed amount: ... second removed 0.0 (ratio 0.00 ...)` |
| pawn subclasses the generic character (health free) | HO-1 | `stage 1 not built: the graded pawn (...) does not derive from the provided task base pawn (CraftBenchBareCharacter) ...` |
| damage/heal are plain C++ functions, no ability granted | HO-6 | `no activatable ability tagged Ability.Damage on the pawn ... granted=0` |
| per-application amount = 50 | HO-8 | `the per-application Health change is outside the stated 5-25 band: one damage moved Health by 50.0 ...` |

---

## 5. Decisions this sheet is asking you to ratify (each is cheap to reverse now, expensive later)

- **D1 -- the operation seam is a gameplay TAG, not a reflected function name.**
  the bp-g2 scale-up plan (not shipped) §1 T1.1 assumed `DoDamage`/`DoHeal` reflected seams.
  Those cannot be reached without (a) a **second** Hard Rule #2 documented
  exception for naming deliverable functions in a prompt, and (b) the
  `CraftBenchSeam` marshalling layer, which is **V2.4 and explicitly not in tier
  1** (`bp-g2-verifier-extensions.md` §2). The tag route is the already-proven
  one (`TriggerAbilityByTag` / `NumGrantedAbilitiesWithTag`) and is what makes
  this task's "zero new infra" claim true. **Cost of declining: T1.1 moves
  behind V2.4 and stops being the cheap Band-A floor.**
- **D2 -- MaxHealth is disclosed nowhere and gated nowhere here.** The source
  row asks for "health and max health values", but `UCraftBenchAttributeSet`
  ships `MaxHealth` **uninitialized (reads 0)**, and upward clamping is
  `gp-heal-over-time`'s whole axis. Gating it in both families double-books the
  capability and re-correlates two of the four tier-1 cells. Recommend: drop it
  here, record in `## Dropped clauses`.
- **D3 -- two new tags (`Ability.Damage`, `Ability.Heal`) land in
  `CraftBenchGameplayTags.{h,cpp}`.** the bp-g2 scale-up plan (not shipped) I1.5 budgets
  **3** new tags for tier 1; the real count is **4** (2 here + 1 for HoT + 1 for
  double-jump). `PreferredAbilityTag()` returns `Ability.Damage` for this
  fixture and stays unique per GAS family.
- **D4 -- the fixture presets Health to 60, never near a boundary.** Two
  damages (max 25 each) plus one heal keeps the leg inside `(0, 100)` for every
  conforming magnitude, so neither a floor clamp nor a MaxHealth clamp can bite
  a correct solve. This is the anti-F3 discipline: a clamp must never be able to
  turn a conforming implementation into a misattributed FAIL.

## 6. What must be true before this reaches G2

Reference PASS + empty FAIL; one committed one-delta discrimination variant per
anti-gaming note (6), each dying at its **own** named substring (I0.4's
uniqueness oracle); both populations for HO-9/HO-10/HO-11 recorded in
`notes.md` with the chosen bar and the margin on each side; and the correlation
with `gp-poison-dot-stack` stage 1 declared in `notes.md` **and** carried as
constraint C1 in the internal design note (not shipped).
