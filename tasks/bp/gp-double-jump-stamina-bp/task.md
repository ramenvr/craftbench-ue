---
id: gp-double-jump-stamina-bp
substrate: ThirdPerson
set: bp
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_DoubleJump :: ADoubleJumpStaminaFunctionalTest"]
introspect: [gp_double_jump_stamina_bp.py]
---

# gp-double-jump-stamina-bp

**Blueprint-deliverable variant** of `gp-double-jump-stamina-cpp` (family T1.3
of the bp-g2 tier-1 slate, BP-G2 source record 33 "Movement-1"). The behavior spec,
the fixture, the two-leg 10-checkpoint schedule and every L2 gate
(DJ-1..DJ-4, DJ-7) are **identical** to the C++ original so C++-vs-BP results
are directly comparable - that comparability is the entire point of the pair.
The only deltas are (a) the prompt mandates a **Blueprint** deliverable under
`Content/Tasks/gp-double-jump-stamina-bp/` and (b) an L2-introspect leg
structurally asserts the deliverable really is Blueprint (the anti-gaming gate
against solving the "BP variant" in C++), plus (c) the C++ decoy discrimination
variants that exist to try to defeat (b).

The **fixture and the map are SHARED with the `-cpp` original, byte-identically
and by design**: `Source/CraftBenchTests/Tasks/gp-double-jump-stamina/` and
`Content/Maps/gp-double-jump-stamina/L_DoubleJump.umap`. Neither folder carries
a `-cpp`/`-bp` suffix and neither may grow a per-variant copy. **Nothing about
the observation changes between the twins; only the authoring surface does.**

The design contract of the family is `../gp-double-jump-stamina-cpp/PIN.md`,
including its binding `OWNER DECISION 2026-08-10 -- EDIT, then ACCEPTED` block
(**DJ-6 CUT**; `DescribeSegments()` mandatory in the diagnostic). It is
**normative** and this twin does not redesign any part of it: the prompt below
is the signed prompt with exactly one bullet replaced (see `## Prompt delta`),
and every gate is the C++ original's.

> **STATUS: NOTHING HAS BEEN MEASURED ON THIS VARIANT** - and the `-cpp`
> original's own bars are `PROPOSED - NOT YET MEASURED` in the fixture source.
> This twin has never been built, never run in PIE, never graded a reference and
> never run a discrimination sweep. The Blueprint reference described under
> `## Reference solution metadata` is a **SPEC, not an authored asset** - no
> `.uasset` exists under `reference/` yet, because authoring one needs a live
> editor. Until it is authored and graded, no run of this task is evidence of
> anything. Calibration record and exact commands: `notes.md`.

> **`RiseEpsilon` MUST be calibrated against a BLUEPRINT solve, not only against
> the C++ reference** (`../gp-double-jump-stamina-cpp/task.md`, Reference
> solution metadata: "`RiseEpsilon` must be measured against a **BP lane** as
> well as this C++ one before it is called calibrated - calibrating a shape
> floor against one impulse is how DJ-2c would false-FAIL a conforming BP
> solve"). The hazard is two-directional and the dangerous direction is a floor
> set too HIGH: the prompt fixes no jump height on purpose, so a conforming but
> **gentle** Blueprint second jump that rises less than the floor is failed for
> not jumping. **This twin is therefore not merely a re-skin: it is the
> measurement lane that constant was always going to need.**

> **The whole sampler this task gates on had NEVER EXECUTED before the `-cpp`
> original** (`SetDenseSampling` / `Segments` / `NumRises` / `MeanVerticalRate` /
> `DescribeSegments`, plus `MaxVelocityZAfter` and four sibling reductions, had
> zero callers across both substrates as of 2026-08-10). DJ-2c gates on a
> **derived** quantity, and a derived quantity can be wrong **silently, in
> either direction**. Read the first run's `DescribeSegments()` output; do not
> trust a verdict from it until someone has.

> **Substrate: ThirdPerson.** Same substrate, same scaffolds and same fixture as
> the `-cpp` original; the twin adds no substrate change of any kind (0 new C++
> files, 0 new tags, 0 new maps).

> Variant note (deliverable-format exception): like the GAS-contract naming,
> mandating the **Blueprint** authoring surface is a deliberate, documented
> exception to behavior-only prompts (Hard Rule #2) - measuring the BP authoring
> path *is the point* of this variant. The `-bp` suffix is the benchmark's
> convention for such variants (see `tasks/README.md`).

> GAS-category note (inherited verbatim from the original): this task names the
> GAS **contract** as part of the interface - the documented exception to
> behavior-only prompts, because verifying an activatable, tag-triggered,
> resource-gated impulse *through* an ability system is the point. The prompt
> names **an ability system**, a **Power** resource, the pawn's **granted
> abilities** and **one trigger tag** (`Ability.DoubleJump`). It never names the
> plugin, the classes (`UCraftBenchAttributeSet`, `ACraftBenchCharacter`), the
> third-party type the source row named, or the pattern ("GameplayEffect",
> "cost", "LaunchCharacter").

> **This family shares its resource (`Power`) with `gp-glide-stamina-*`**, so a
> matrix cell containing both measures Power handling twice (PIN.md D6). They
> share no gate and no ladder, so this is a note, not a `QUEUE.md` exclusion -
> unlike constraint C1, which does not reach this family at all.

## Primary concept

- `gas-abilities` - Gameplay Abilities activated by tag, applying a **movement
  impulse** and **gated on a Gameplay Attribute** as a one-shot cost, authored
  **in Blueprint**
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-ability-system-for-unreal-engine)

The load-bearing mechanics are unchanged from `gp-double-jump-stamina-cpp`: an
activatable ability, reachable by its own gameplay tag and granted on the pawn;
a **real vertical velocity reversal** (not a teleport, not a slowed fall) taken
from a genuine free fall; a cost **charged once** at the disclosed magnitude;
and a cost that is a **gate** - below it the ability does nothing at all and the
resource is not driven negative. What changes is that all of it must be built
through an editor-visible route with **no C++**.

## Prompt given to the agent

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
> - Deliver your solution **entirely as Blueprint assets** created in the editor
>   and saved under `Content/Tasks/gp-double-jump-stamina-bp/`: a Blueprint
>   subclass of the provided character with your ability granted on it. **Do not
>   add or modify any C++ source for this task.** That content folder is the
>   only path the verifier looks in.
> - The character must be **visibly represented**: assign one of the provided
>   mannequin skeletal meshes (under `/Game/Characters/`) as your character's
>   mesh, so a reviewer watching the run can see it jump.
>
> The verifier drops the character from a height, waits until it is falling,
> then activates your ability by sending that tag and observes the resulting
> motion and Power.

## Workspace state pre-task

Files that **exist** under `Source/ThirdPerson/` - **read-only context for this
task**, since the deliverable is asset-only and the prompt forbids C++ edits:

- The stock UE 5.8 Third Person C++ template sources (`ThirdPersonCharacter`,
  game mode, the `Variant_*` trees). No edit needed and none allowed.
- `ThirdPerson.Build.cs` - already includes `GameplayAbilities`,
  `GameplayTags`, `GameplayTasks`. No edit needed.
- `CraftBenchCharacter.{h,cpp}` - **the base pawn for this family**: a
  pawn-owned ability system component (visible as an inherited component in a
  Blueprint subclass), the auto-granted `GrantedAbilities` array (ships empty,
  `EditAnywhere` - settable from Blueprint class defaults), the
  `CraftBenchPawn` tag, and a **pre-built attribute set**, which is what holds
  `Power`. It sets no capsule size, no `GravityScale` and no `JumpZVelocity`,
  so the stock character values apply.
- `CraftBenchAttributeSet.{h,cpp}` - the contract attribute set type (`Health`,
  `MaxHealth`, `Power`; **no clamping at v1.0**). `Power` is the only attribute
  this task reads.
- `CraftBenchBareCharacter.{h,cpp}` - the *other* families' task base. **That
  lineage suppresses the attribute-set subobject entirely**, so a Blueprint
  parented to it has no `Power` at all; its readings are 0.0 and it fails by
  name at the cost gate.
- `CraftBenchGameplayTags.{h,cpp}` - registers `Ability.DoubleJump` alongside
  the pre-existing `Ability.Glide` / `Ability.Poison` / `Ability.Damage` /
  `Ability.Heal` / `Ability.HealOverTime`. The tag this task needs already
  exists; no tag authoring, and therefore no config edit, is required.
- The `GameplayAbilities` plugin is enabled.
- `ADoubleJumpStaminaFunctionalTest` lives in the verifier-only `CraftBenchTests`
  module (`Source/CraftBenchTests/Tasks/gp-double-jump-stamina/`). That module
  is deny-write and is graded from git HEAD, so nothing you submit can change
  it.
- `Content/Characters/Mannequins/` - the substrate's **native**
  visual-representation content (`SKM_Manny_Simple` / `SKM_Quinn_Simple`, the
  `SK_Mannequin` skeleton). Read-only: `Content/Characters/` is outside the
  writable sandbox.

Files the agent **creates** (all assets, under
`Content/Tasks/gp-double-jump-stamina-bp/` - the `Content/Tasks/` prefix is
agent-writable for asset deliverables): a Blueprint subclass of the provided
character carrying an assigned mannequin mesh, plus a Blueprint ability tagged
`Ability.DoubleJump` in that pawn's granted abilities that **refuses below 20
Power**, otherwise **debits exactly 20 once** and applies a **real upward
vertical impulse**, and whatever supporting asset that route needs. The pawn is
resolved by derivation plus the preferred tag (the verifier scans Blueprint
assets under `/Game/Tasks` via the Asset Registry) and is spawned + possessed by
the verifier - the map places no pawn.

## Verifier specification

**L2 - behavioral (IDENTICAL to `gp-double-jump-stamina-cpp`, same fixture
binary, same map binary).** The `ADoubleJumpStaminaFunctionalTest` fixture, its
10-checkpoint schedule `{0.4, 0.7, 1.0, 1.3, 1.6, 1.9, 2.4, 2.7, 3.0, 3.3}`,
its `SetDenseSampling(true)` per-tick series, the two legs, all nine gates and
their exact named FAIL strings are the C++ original's - see
`../gp-double-jump-stamina-cpp/task.md` section "Verifier specification" for the
full table, which is the single source of truth. Nothing in it is re-derived
here. Summary of the gated legs:

```text
LEG 1 -- the jump + the cost
  cp0 (0.4 s)  DJ-7 visible-character check, before anything else
  cp1 (0.7 s)  read the LIVE vZ first (DJ-2a's falling baseline), latch the trigger
               time, SetPower(60), trigger Ability.DoubleJump
  cp2 (1.0 s)  Power at trigger+0.3   -> the debit closes ; DJ-3c's window OPENS
  cp5 (1.9 s)  Power at trigger+1.2   -> DJ-3c's window CLOSES
LEG 2 -- the refusal
  cp6 (2.4 s)  capture EVERY Leg-1 reduction FIRST (that order IS the window),
               then SetPower(5) and trigger again
  cp7..cp9     Power samples ; ALL FINAL GATES at cp9

  DJ-1  : granted by tag AND the LEG-1 activation landed (per-leg counter)
  DJ-2a : the pawn really was descending at the trigger      (harness sanity)
  DJ-2b : the highest vertical velocity after the trigger is POSITIVE (pure direction)
  DJ-2c : Z rose again after bottoming out, by more than RiseEpsilon (pure shape,
          leg-filtered segments)
  DJ-3a : Power strictly decreased across the activation
  DJ-3b : the debit is the DISCLOSED 20 (+/- CostTol)
  DJ-3c : Power stopped changing afterwards (one-shot, not a drain)
  DJ-4  : at 5 Power the ability did NOT fire -- no Leg-2 rise and no negative Power.
          SKIPPED rather than failed when Leg 1 never established a rise.
```

The fixture resolves the pawn by derivation from `ACraftBenchCharacter`
(`ResolveAgentPawnClass` scans native subclasses AND Blueprint assets under
`/Game/Tasks` via the Asset Registry, preferring the candidate whose
`GrantedAbilities` carry the fixture's `PreferredAbilityTag()` =
`Ability.DoubleJump`), so **the Blueprint deliverable grades with no fixture
changes**.

**L2-introspect - the structural "the deliverable is Blueprint" gate.** The
verifier-owned script
`tools/verify-single/introspect/gp_double_jump_stamina_bp.py` (shared mechanism
in `introspect/_bp_variant_lib.py`, configured with
`pawn_base_class = "CraftBenchCharacter"` and `min_bp_abilities = 1`) runs
headless via `UnrealEditor-Cmd -ExecutePythonScript=`. It emits **five checks on
every leg, reached or not**, so the denominator is constant and an empty
submission scores 0/5. PASS requires every one:

```text
task_folder_exists        : /Game/Tasks/gp-double-jump-stamina-bp/ exists and lists
                            >= 1 asset
bp_pawn_present           : >= 1 Blueprint asset under that folder whose GeneratedClass
                            derives from ACraftBenchCharacter -- the same lineage the L2
                            fixture resolves, so L2I and L2 agree on what "the
                            deliverable" is
bp_pawn_grants_bp_ability : the BP pawn's GrantedAbilities class-defaults array holds
                            >= 1 Blueprint-generated ability class AND ZERO native
                            (/Script/) ones. The zero-native half closes the
                            GRANTED-ABILITY NATIVE HOLE: counting BP entries alone
                            passes a submission that grants one Blueprint ability next
                            to a C++ one doing the real work. Safe against false FAILs:
                            neither substrate commits a single UGameplayAbility
                            subclass, so every /Script/ entry found is agent C++.
resolved_pawn_is_blueprint: NO agent-authored native (C++) subclass of
                            ACraftBenchCharacter exists. Exemption is by EXACT /Script/
                            path against what the substrate commits at git HEAD (today:
                            the ABSTRACT CraftBenchBareCharacter alone), never by path
                            shape -- agent C++ lands in the same writable module as the
                            scaffolds, so a folder rule would re-open the hole. Fails
                            CLOSED if the reflection sweep stops seeing the scaffold.
pawn_visibly_represented  : the BP pawn's inherited mesh component carries an assigned
                            SkeletalMesh whose asset path lives under /Game/Characters/
                            (the substrate's read-only mannequin pool). Pool-anchored on
                            purpose: "some mesh exists" is gameable with an empty
                            placeholder under the writable path.
```

Identity is by **pre-declared content path**
(`/Game/Tasks/gp-double-jump-stamina-bp/`) and **derivation**, never by asset
name or class name - the agent may name its Blueprints anything.

**What L2I does NOT cover, stated so nobody assumes it does:** the native sweep
is scaffold-PAWN shaped. A native `UGameplayEffect`, `UAttributeSet` or
`UGameplayModMagnitudeCalculation` subclass referenced from Blueprint assets is
not swept (`_bp_variant_lib.py`, "WHAT THIS MODULE DOES NOT COVER";
the internal design note (not shipped) V2.1 says the same of the two shipped
scripts). On this task the plausible instance is a native cost effect on an
otherwise-Blueprint ability. See anti-gaming note 3.

## Reference solution metadata

- **0 lines of C++. 3 Blueprint-era `.uasset`s**, all new, all under
  `Content/Tasks/gp-double-jump-stamina-bp/`. This is the "equivalent
  deliverable" the C++ original's reference metadata names (4 C++ files / 252
  LOC -> 3 assets / 0 LOC):
  - a **BP pawn** parenting `CraftBenchCharacter`, with `GrantedAbilities` =
    [the BP ability] and `SKM_Manny_Simple` on the inherited mesh component with
    the `(0,0,-90)` / `(0,-90,0)` capsule alignment every reference in this
    family uses. **It initializes nothing**: the verifier presets Power itself
    before each leg (60, then 5), so the pawn's starting Power is not
    observable, which is why this deliverable needs no init asset at all;
  - a **BP GameplayEffect**, `Instant`, one additive `Power` modifier of `-20`,
    used as the ability's **cost effect**;
  - a **BP GameplayAbility**, `InstancedPerActor`, tagged `Ability.DoubleJump`,
    whose cost is that effect and whose graph commits, then launches the
    character upward with the vertical component **overridden**, then ends
    immediately.
- **The cost effect is the refusal gate, and that is the whole of DJ-4 on this
  lane.** A committed cost is refused when applying it would take the attribute
  below zero, so at 5 Power the commit fails, the graph ends the ability without
  launching, and Power is left untouched - which is precisely
  "no second jump, and Power must not go negative". An explicit read-and-branch
  before the commit is an equally conforming alternative and is what the C++
  reference does; both are one-shot debits, so both satisfy DJ-3a/3b/3c.
- **The impulse must OVERRIDE the vertical velocity, not add to it** - the
  single most important line to carry over from the C++ reference. Mid-fall the
  character carries a large negative vZ, so an additive launch can leave the
  velocity still negative and the character still descending: it would read as
  "launch the character up by 600" and never reverse anything, which is the
  plausible-wrong solve DJ-2b exists to catch. The Blueprint launch node takes a
  Z-override flag; the reference sets it.
- **The +600 cm/s impulse is the C++ reference's CHOICE carried over
  unchanged**, and carrying it over is load-bearing for the comparison: against
  world gravity (-980 cm/s^2, stock across this substrate) a reversal to +600
  rises `600^2 / 1960 = 183.7 cm`, a **9.2x margin** over `RiseEpsilon` = 20 cm,
  with ~37 dense samples inside the rising run at `-FPS=60` - far too long a
  monotonic run to be mistaken for jitter by the segmenter. Changing it here
  would make a `-cpp` vs `-bp` difference an artifact of the reference rather
  than of the authoring surface. **But note the asymmetry: the reference's job
  is to be comfortably inside the gate, while `RiseEpsilon`'s job is to admit
  every conforming solve - which is why the constant still needs a measured
  population of BP impulses, not this one number.**
- **Ending the ability synchronously is what lets Leg 2 re-trigger it.** An
  `InstancedPerActor` ability that is still running refuses its next
  activation, and an ability that held itself open across the 1.7 s inter-leg
  gap would be refused at Leg 2 for a reason that has nothing to do with the
  cost - which DJ-4 accepts leniently, but which would make the reference stop
  testing what it is for.
- Senior-dev hours: 1.5-2.5 hours.
- The exact package paths, parent classes and property values are enumerated in
  `notes.md` section "Blueprint asset specification". **The reference is a SPEC
  today, not an authored asset**: `.uasset` authoring needs a live editor and is
  a serial pass. `cb lint` will WARN `reference-solution` until it exists, and
  `cb discriminate` cannot run.

## Anti-gaming notes

1. **Solve it in C++ anyway (defeats the variant's whole point).** *Failure
   mode*: the agent writes the same C++ solution as the `-cpp` original -
   behaviorally correct, so L2 alone would pass it. *Defense*: the L2I leg FAILs
   `bp_pawn_present` (no Blueprint subclass of the provided character exists
   under `/Game/Tasks/gp-double-jump-stamina-bp/`) and independently
   `resolved_pawn_is_blueprint`. *Discrimination variant*:
   `discrimination/cpp-solve/` (the `-cpp` reference verbatim; the same shape as
   `tasks/bp/gp-glide-stamina-bp/discrimination/cpp-solve/`, which is the
   proven original - measured FAIL at that named check on a live runner
   2026-07-17).
2. **Decoy BP shell + real C++ solve.** *Failure mode*: the agent ships a
   Blueprint pawn (enough to satisfy the existence checks) plus a C++ pawn that
   actually implements the behavior and wins L2 resolution - so L2 grades the
   C++ while L2I grades the Blueprint and **both layers pass**, on a submission
   the prompt explicitly forbids. *Defense*: **`resolved_pawn_is_blueprint`** -
   no agent-authored native subclass of `ACraftBenchCharacter` may exist at all.
   **This is MEASURED, not argued, and the measurement is cited rather than
   re-argued**: `tasks/bp/gp-glide-stamina-bp/discrimination/MATRIX.md`
   records the `cpp-solve-with-bp/` variant grading **overall PASS on the
   3-check verifier and overall FAIL on the 4-check one**, same box, same
   commit, on UE 5.8 - a real false PASS that existed until 2026-08-03. The
   check logic is substrate-independent and is now shared code. *Discrimination
   variant*: `discrimination/cpp-solve-with-bp/`.
3. **A C++ helper reached from Blueprint** - the residual, and only partly
   defended. *Failure mode*: the pawn and the ability are genuine Blueprints,
   but the real work sits in agent-authored C++ they reference - here, most
   plausibly a native cost effect. *Defense, for the ability case*:
   `bp_pawn_grants_bp_ability` requires **zero native entries** in
   `GrantedAbilities`, so a BP-shell-plus-C++-ability grant FAILs by that check
   (a deliberate divergence from the two shipped originals, which only count the
   Blueprint entries). *ARGUED, NOT DEFENDED, for the rest*: a native
   `UGameplayEffect`, `UAttributeSet` or `UGameplayModMagnitudeCalculation`
   subclass referenced from a Blueprint asset is **not swept** and would pass
   all five checks while adding C++ the prompt forbids. Closing it is
   the internal design note (not shipped) V2.1's native-decoy sweep, which is
   not built. Do not read this list as claiming a defense there.
4. **An invisible deliverable.** *Failure mode*: a behaviorally-correct pawn
   with no mesh - **MEASURED 2026-08-04 on the glide family: all 9 matrix reps
   across 3 models shipped meshless pawns**, and human review was only possible
   by instrumenting copies with a debug cube. *Defense*: two independent gates,
   L2's DJ-7 (a mesh component with a mesh actually assigned) and L2I's
   **`pawn_visibly_represented`**, which additionally pins the mesh to the
   read-only `/Game/Characters/` pool the agent cannot author into.
5. **Every behavioral gaming mode of the original** - a movement-component or
   input-driven jump with nothing activatable by tag, a teleport upward, a
   cancelled one-shot velocity, the reused glide answer (slow the descent
   instead of reversing it), a free jump, a wrong-sized debit, a per-tick drain
   dressed as a cost, and an ungated cost that fires at 5 Power. *Defense*:
   **inherited unchanged**, because the fixture is the same binary - DJ-1,
   DJ-2b, DJ-2c, DJ-2b, DJ-3a, DJ-3b, DJ-3c and DJ-4 respectively. The full
   argument, **including AG-7 ("unlimited air jumps while Power lasts") which
   the original records as ARGUED, NOT DEFENDED after DJ-6 was cut**, is in
   `../gp-double-jump-stamina-cpp/task.md` section "Anti-gaming notes". That gap
   is inherited too, and inheriting it honestly is the point of saying so. Per
   the `-bp` inheritance law (`tools/verify-single/gold_set.txt`), a twin
   legitimately inherits its C++ original's behavioral variants rather than
   cloning them.

## Hidden invariants

- **Every hidden invariant of `gp-double-jump-stamina-cpp` applies unchanged**:
  why DJ-4 is skip-vs-fail and why the guard rather than the ordering is the
  contract; why `RiseEpsilon` doubles as the segmenter's `MinDeltaZ` and why the
  two can never be separate constants; why a conforming double jump on this task
  produces exactly **one** rise and not two (the pawn is dropped, so there is no
  first jump - "fixing" the gate to `>= 2` would false-FAIL every conforming
  solve, including both references); why the leg-boundary rules are
  deliberately asymmetric; why the realized Leg-1 window is a lenient superset
  of the sheet's; that the floor is inside the schedule; the preferred-tag pawn
  resolution; and the per-leg activation counters.
- **BP resolution is Asset-Registry-based.** The fixture only discovers
  Blueprint pawns saved under `/Game/Tasks/` - a Blueprint saved anywhere else
  (e.g. `Content/Blueprints/`) is sandbox-accepted but never resolved, and the
  task FAILs L2 for what looks like a behavioral reason. This is why the prompt
  names the folder and why `task_folder_exists` is the first L2I check.
- **The BP lane's impulse and the C++ lane's impulse are the same physics but
  not the same call, and the difference is a one-frame latency, not a
  magnitude.** The Blueprint launch node stores a pending launch velocity that
  the movement component applies on its next update (replacing the velocity and
  putting the character into falling movement), where the C++ reference assigns
  the velocity directly. At `-FPS=60` that is at most one 0.017 s frame before
  the same `+600` shows up in the series - immaterial to DJ-2b (pure direction)
  and to DJ-2c (pure shape), and it does not move the apex enough to matter
  against a 20 cm floor. Recorded so a first-run trace that is one sample
  "late" against the C++ prediction is not mistaken for a defect.
- **This is a two-leg fixture in ONE world with no reset**, so a Blueprint
  ability that holds itself open, sets a cooldown, or spawns a timer that
  outlives the activation changes what Leg 2 measures. The ability must end
  synchronously; a cooldown that happens to block the Leg-2 re-trigger is
  indistinguishable from a correct cost gate and can only make DJ-4 pass, never
  fail, which is a leniency the family accepts deliberately.
- **The pawn's starting Power is NOT observable**, on either lane: the fixture
  presets it at cp1 (60) and again at cp6 (5). A Blueprint that initializes
  Power is neither rewarded nor penalized, and a Blueprint that does not is not
  disadvantaged - which is why this twin's reference ships no init DataTable
  while `gp-health-attribute-ops-bp`'s must.
- The map places **only the fixture** and sets no `GameModeOverride`, so PIE
  also spawns the substrate's default `BP_ThirdPersonGameMode` pawn at the
  PlayerStart. It is not an `ACraftBenchCharacter` subclass, so it can never win
  pawn resolution and no gate reads it - the graded pawn is exclusively the one
  the fixture spawns and possesses. **Unlike every other task in this family the
  map's FLOOR is inside the graded window**: the pawn is dropped from z=1200 and
  lands during Leg 2, which is why `RiseEpsilon` must stay well above the
  walking-mode floor adjustment (~2.4 cm) as well as above apex jitter.
- **No config edit is needed and none is licensed.** `Ability.DoubleJump`
  already exists in `CraftBenchGameplayTags`; this spec declares no
  `config_allow` entries, so any `Config/` edit rides the exit-4 sandbox path.
