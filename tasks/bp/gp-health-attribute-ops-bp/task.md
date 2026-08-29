---
id: gp-health-attribute-ops-bp
substrate: ThirdPerson
set: bp
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2, L2I]
fixtures: ["L_HealthOps :: AHealthAttributeOpsFunctionalTest"]
introspect: [gp_health_attribute_ops_bp.py]
---

# gp-health-attribute-ops-bp

**Blueprint-deliverable variant** of `gp-health-attribute-ops-cpp` (the T1.1
Band-A floor of the bp-g2 tier-1 slate, BP-G2 source record 29 "Health-1"). The
behavior spec, the fixture, the checkpoint schedule and every L2 gate
(HO-1..HO-11) are **identical** to the C++ original so C++-vs-BP results are
directly comparable - that comparability is the entire point of the pair. The
only deltas are (a) the prompt mandates a **Blueprint** deliverable under
`Content/Tasks/gp-health-attribute-ops-bp/` and (b) an L2-introspect leg
structurally asserts the deliverable really is Blueprint (the anti-gaming gate
against solving the "BP variant" in C++), plus (c) the C++ decoy discrimination
variants that exist to try to defeat (b).

The **fixture and the map are SHARED with the `-cpp` original, byte-identically
and by design**: `Source/CraftBenchTests/Tasks/gp-health-attribute-ops/` and
`Content/Maps/gp-health-attribute-ops/L_HealthOps.umap`. Neither folder carries
a `-cpp`/`-bp` suffix and neither may grow a per-variant copy -
`map_locator.locate_map` derives the automation prefix from the map's own
folder name and never joins it to the task id, and the glide/poison pairs set
the precedent. **Nothing about the observation changes between the twins; only
the authoring surface does.**

The design contract of the family is `../gp-health-attribute-ops-cpp/PIN.md`.
It is **normative** and this twin does not redesign any part of it: the prompt
text below is the signed prompt with exactly one bullet replaced (see
`## Prompt delta`), and every gate is the C++ original's.

> **STATUS: NOTHING HAS BEEN MEASURED ON THIS VARIANT.** The `-cpp` original
> shipped 2026-08-10 (`fbb0e27`) and graded PASS from git HEAD; **this twin has
> never been built, never run in PIE, never graded a reference and never run a
> discrimination sweep.** The Blueprint reference described under
> `## Reference solution metadata` is a **SPEC, not an authored asset** - no
> `.uasset` exists under `reference/` yet, because authoring one needs a live
> editor. Until that reference is authored and graded, no run of this task is
> evidence of anything. The calibration record and the exact commands are in
> `notes.md`.

> **Substrate: ThirdPerson.** This task runs on the `UE-projects/ThirdPerson/`
> substrate - the stock UE 5.8 Third Person C++ template, which ships the
> Manny/Quinn mannequin content **natively** under `/Game/Characters/`. Same
> substrate, same scaffolds and same fixture as the `-cpp` original; the twin
> adds no substrate change of any kind (0 new C++ files, 0 new tags, 0 new
> maps).

> Variant note (deliverable-format exception): like the GAS-contract naming,
> mandating the **Blueprint** authoring surface is a deliberate, documented
> exception to behavior-only prompts (Hard Rule #2) - measuring the BP
> authoring path *is the point* of this variant. The `-bp` suffix is the
> benchmark's convention for such variants (see `tasks/README.md`).

> GAS-category note (inherited verbatim from the original): this task names the
> GAS **contract** as part of the interface - the documented exception to
> behavior-only prompts, because verifying the health resource and its two
> operations *through* an ability system is the point. What the exception
> licenses, and its exact limit: the prompt names **an ability system**, **the
> attribute set type the project provides**, a **Health** attribute, and **two
> trigger tags** (`Ability.Damage`, `Ability.Heal`). It never names the plugin
> ("GAS"), the classes (`UCraftBenchAttributeSet`, `ACraftBenchBareCharacter`),
> the pattern ("GameplayEffect"), or the source row's function names
> (`TakeDamage` / `Heal`).

> **Selection constraint C1 applies to this id too** (the internal design note (not shipped)):
> `gp-health-attribute-ops-*` and `gp-poison-dot-stack-*` must **never** be
> selected into the same graded bench cell, in any of the four pairings. This
> task lifts poison's stage-1 ladder verbatim, so a model that clears stage 1
> on one clears it on the other by construction.

## Primary concept

- `gas-attributes` - Gameplay Attributes and Attribute Sets, built by the agent
  (stage 1) and moved by two symmetric, tag-activated operations (stage 2),
  authored **in Blueprint**
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/gameplay-attributes-and-attribute-sets-for-the-gameplay-ability-system-in-unreal-engine)

The load-bearing mechanics are unchanged from `gp-health-attribute-ops-cpp`:
**stage 1** - an attribute set registered and initialized on the pawn's
inherited ability system, exposing a readable and writable Health; **stage 2** -
two activatable abilities, each reachable by its own gameplay tag, each moving
Health by **one fixed amount per activation**, equal in size and opposite in
sign, and **only** when activated. What changes is that all of it must be built
through an editor-visible route with **no C++**.

## Prompt given to the agent

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
> - Deliver your solution **entirely as Blueprint assets** created in the editor
>   and saved under `Content/Tasks/gp-health-attribute-ops-bp/`: a Blueprint
>   subclass of the provided task character with your health system built on it
>   and both abilities granted on it. **Do not add or modify any C++ source for
>   this task.** That content folder is the only path the verifier looks in.
> - Stamp each tag on the ability **itself**, in its own tag list, so the
>   ability can be activated *by that tag*. The verifier activates abilities by
>   tag directly; it does not send gameplay events.
> - The character must be **visibly represented**: assign one of the provided
>   mannequin skeletal meshes (under `/Game/Characters/`) as your character's
>   mesh, so a reviewer watching the run can see it.
>
> The verifier sets Health to a known value, then activates your abilities by
> sending those tags, and observes how Health moves. **It activates the damage
> ability more than once, about 0.7 seconds apart, and each activation must
> land its full effect** -- so an ability that is still running, or is on
> cooldown, when the next activation arrives will not be counted.

## Workspace state pre-task

Files that **exist** under `Source/ThirdPerson/` - **read-only context for this
task**, since the deliverable is asset-only and the prompt forbids C++ edits:

- The stock UE 5.8 Third Person C++ template sources (`ThirdPersonCharacter`,
  game mode, the `Variant_*` trees). No edit needed and none allowed.
- `ThirdPerson.Build.cs` - already includes `GameplayAbilities`,
  `GameplayTags`, `GameplayTasks`. No edit needed.
- `CraftBenchBareCharacter.{h,cpp}` - **the task base pawn (the stage-1 start
  state)**: an abstract `ACraftBenchCharacter` lineage with a pawn-owned
  ability system component (visible as an inherited component in a Blueprint
  subclass), the auto-granted `GrantedAbilities` array (ships empty,
  `EditAnywhere` - settable from Blueprint class defaults), the
  `CraftBenchPawn` tag, and **no attribute set**. Stage 1 is registering and
  initializing the provided attribute set on that inherited ability system
  component through an editor-visible route. `UCLASS(Abstract)` does not
  prevent a Blueprint from parenting to it.
- `CraftBenchCharacter.{h,cpp}` - the generic scaffold pawn other tasks use; it
  still pre-builds the attribute set. **Parenting your Blueprint to it does not
  satisfy this task** - the stage-1 derivation gate fails a pawn that is not on
  the task-base lineage, by name.
- `CraftBenchAttributeSet.{h,cpp}` - the contract attribute set type (`Health`,
  `MaxHealth`, `Power`; no clamping at v1.0). `Health` is the attribute the
  verifier reads and both operations must move. The class exists; **registering
  and initializing an instance on your pawn's ability system is stage 1**.
- `CraftBenchGameplayTags.{h,cpp}` - registers `Ability.Damage` and
  `Ability.Heal` alongside the pre-existing `Ability.Glide` / `Ability.Poison` /
  `Ability.HealOverTime` / `Ability.DoubleJump`. Both tags this task needs
  already exist; no tag authoring, and therefore no config edit, is required.
- The `GameplayAbilities` plugin is enabled.
- `AHealthAttributeOpsFunctionalTest` lives in the verifier-only
  `CraftBenchTests` module
  (`Source/CraftBenchTests/Tasks/gp-health-attribute-ops/`). That module is
  deny-write and is graded from git HEAD, so nothing you submit can change it.
- `Content/Characters/Mannequins/` - the substrate's **native**
  visual-representation content (`SKM_Manny_Simple` / `SKM_Quinn_Simple`, the
  `SK_Mannequin` skeleton). Read-only: `Content/Characters/` is outside the
  writable sandbox, so a graded character is visible to a human reviewer
  instead of an invisible capsule.

Files the agent **creates** (all assets, under
`Content/Tasks/gp-health-attribute-ops-bp/` - the `Content/Tasks/` prefix is
agent-writable for asset deliverables): a Blueprint subclass of the provided
task character with the health system registered + initialized on its inherited
ability system (stage 1; any supporting asset - e.g. an init data table or an
init effect - lives in the same folder), plus two Blueprint abilities tagged
`Ability.Damage` and `Ability.Heal`, each applying one fixed, equal-and-opposite
change to Health, both listed in the pawn's granted abilities (stage 2). The
pawn is resolved by derivation plus the preferred tag (the verifier scans
Blueprint assets under `/Game/Tasks` via the Asset Registry) and is spawned +
possessed by the verifier - the map places no pawn.

## Verifier specification

**L2 - behavioral (IDENTICAL to `gp-health-attribute-ops-cpp`, same fixture
binary, same map binary).** The `AHealthAttributeOpsFunctionalTest` fixture, its
5-checkpoint schedule `{0.5, 1.2, 1.9, 2.6, 3.3}`, all eleven gates HO-1..HO-11
and their exact named FAIL strings are the C++ original's - see
`../gp-health-attribute-ops-cpp/task.md` section "Verifier specification" for
the full table, which is the single source of truth. Nothing in it is
re-derived here. Summary of the gated legs:

```text
CHECKPOINT 0 (0.5 s) - THE STAGE-1 LADDER, all named FAILs, before any trigger:
  HO-1 derivation : the graded pawn IsA ACraftBenchBareCharacter
  HO-2 presence   : the ASC exposes the contract Health attribute
  HO-3 init       : Health reads 100 (+/- BaselineEpsilon) BEFORE any fixture write
  HO-4 writability: write 37 (a value != 100 on purpose), read-back must move
  HO-5 visibility : a skeletal/static mesh component with an assigned mesh exists
                    on the graded pawn
  then SetHealth(60) ; H0 read ; trigger Ability.Damage
cp1 (1.2 s): H1 ; trigger Ability.Damage        Drop1     = H0 - H1   over (cp0,cp1]
cp2 (1.9 s): H2 ; trigger Ability.Heal          Drop2     = H1 - H2   over (cp1,cp2]
cp3 (2.6 s): H3   (nothing triggered)           HealDelta = H3 - H2   over (cp2,cp3]
cp4 (3.3 s): H4 ; ALL FINAL ASSERTS             IdleDelta = H4 - H3   over (cp3,cp4]

  HO-6  : per tag, NumGrantedAbilitiesWithTag >= 1 AND TriggerAbilityByTag returned true
  HO-7  : Drop1 > DeltaEpsilon
  HO-8  : Drop1 inside the DISCLOSED 5-25 band
  HO-9  : Drop2 / Drop1     in [1 - RepeatTol, 1 + RepeatTol]   (congruent 0.7 s windows)
  HO-10 : HealDelta / Drop1 in [1 - SymTol,    1 + SymTol]      (congruent 0.7 s windows)
  HO-11 : |IdleDelta| <= DeltaEpsilon
```

The fixture resolves the pawn by derivation from `ACraftBenchCharacter`
(`ResolveAgentPawnClass` scans native subclasses AND Blueprint assets under
`/Game/Tasks` via the Asset Registry, preferring the candidate whose
`GrantedAbilities` carry the fixture's `PreferredAbilityTag()` =
`Ability.Damage`), so **the Blueprint deliverable grades with no fixture
changes**. The committed task base is `UCLASS(Abstract)` and the resolver skips
abstract classes, so the base itself can never be graded.

**L2-introspect - the structural "the deliverable is Blueprint" gate.** The
verifier-owned script `tools/verify-single/introspect/gp_health_attribute_ops_bp.py`
(shared mechanism in `introspect/_bp_variant_lib.py`) runs headless via
`UnrealEditor-Cmd -ExecutePythonScript=`. It emits **five checks on every leg,
reached or not**, so the denominator is constant and an empty submission scores
0/5. PASS requires every one:

```text
task_folder_exists        : /Game/Tasks/gp-health-attribute-ops-bp/ exists and lists
                            >= 1 asset
bp_pawn_present           : >= 1 Blueprint asset under that folder whose GeneratedClass
                            derives from ACraftBenchBareCharacter -- the TASK base, not
                            the generic scaffold, so L2I and L2's HO-1 agree on what
                            "the deliverable" is
bp_pawn_grants_bp_ability : the BP pawn's GrantedAbilities class-defaults array holds
                            >= 2 DISTINCT Blueprint-generated ability classes (damage
                            and heal, both authored in Blueprint) AND ZERO native
                            (/Script/) ones. The zero-native half closes the
                            GRANTED-ABILITY NATIVE HOLE: counting BP entries alone
                            passes a submission that grants one Blueprint ability next
                            to a C++ one doing the real work. Safe against false FAILs:
                            neither substrate commits a single UGameplayAbility
                            subclass, so every /Script/ entry found is agent C++.
                            Deliberately a COUNT, not a per-tag lookup -- L2's HO-6
                            already gates tag ownership, and re-deriving it here would
                            double-book one axis on a reflection API this repo has
                            never live-validated.
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

Identity is by **pre-declared content path** (`/Game/Tasks/gp-health-attribute-ops-bp/`)
and **derivation**, never by asset name or class name - the agent may name its
Blueprints anything.

**What L2I does NOT cover, stated so nobody assumes it does:** the native sweep
is scaffold-PAWN shaped. A native `UAttributeSet`,
`UGameplayModMagnitudeCalculation` or `UGameplayEffect` subclass referenced from
Blueprint assets is not swept (`_bp_variant_lib.py`, "WHAT THIS MODULE DOES NOT
COVER"; the internal design note (not shipped) V2.1 says the same of the two
shipped scripts). See anti-gaming note 3.

## Reference solution metadata

- **0 lines of C++. 6 Blueprint-era `.uasset`s**, all new, all under
  `Content/Tasks/gp-health-attribute-ops-bp/`. This is the "equivalent
  deliverable" the C++ original's own reference metadata names (12 C++ files /
  315 LOC -> 6 assets / 0 LOC):
  - a **BP pawn** parenting `CraftBenchBareCharacter`, carrying (i) stage 1 on
    its inherited ability system component, (ii) `GrantedAbilities` = the two
    BP abilities, (iii) `SKM_Manny_Simple` on the inherited mesh component with
    the `(0,0,-90)` / `(0,-90,0)` capsule alignment every reference in this
    family uses;
  - a **`AttributeMetaData` DataTable** initializing `Health` (and `MaxHealth`,
    for coherence only - no gate reads it) to 100, referenced from the pawn's
    inherited-ASC `DefaultStartingData`. This is the whole of stage 1 on the
    no-C++ lane, and it is the route **empirically confirmed on UE 5.8** by
    `gp-poison-dot-stack-bp` at `dfee504` (see that task's `REFERENCE-NOTE.md`);
  - two **BP GameplayEffects**, each `Instant` with one additive `Health`
    modifier of `-10` / `+10`;
  - two **BP GameplayAbilities**, `InstancedPerActor`, tagged `Ability.Damage` /
    `Ability.Heal`, each committing then applying its effect to the owner and
    ending immediately.
- **The +/-10 magnitude is the C++ reference's CHOICE carried over unchanged**,
  and carrying it over is load-bearing for the comparison: it sits mid-band in
  HO-8's disclosed 5-25 window and makes HO-9 and HO-10 read exactly **1.00**,
  giving both twins the identical margin on both ratio gates. Changing it here
  would make a `-cpp` vs `-bp` difference an artifact of the reference rather
  than of the authoring surface.
- **Instant effects, not a direct attribute poke** - the same reasoning as the
  C++ reference: an instant effect leaves nothing active afterwards, so HO-11's
  idle window is satisfied structurally rather than by luck.
- Senior-dev hours: 1-1.5 hours (editor authoring replaces code authoring; the
  behavior design is the C++ original's).
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
   under `/Game/Tasks/gp-health-attribute-ops-bp/`) and independently
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
   defended. *Failure mode*: the pawn and the two abilities are genuine
   Blueprints, but the real work sits in agent-authored C++ they reference.
   *Defense, for the ability case*: `bp_pawn_grants_bp_ability` requires **zero
   native entries** in `GrantedAbilities`, so a BP-shell-plus-C++-ability grant
   FAILs by that check (a deliberate divergence from the two shipped originals,
   which only count the Blueprint entries). *ARGUED, NOT DEFENDED, for the
   rest*: a native `UGameplayEffect`, `UAttributeSet` or
   `UGameplayModMagnitudeCalculation` subclass referenced from a Blueprint asset
   is **not swept** and would pass all five checks while adding C++ the prompt
   forbids. The gap is recorded rather than assumed covered - closing it is
   the internal design note (not shipped) V2.1's native-decoy sweep, which is
   not built. Do not read this list as claiming a defense there.
4. **An invisible deliverable.** *Failure mode*: a behaviorally-correct pawn
   with no mesh - **MEASURED 2026-08-04 on the glide family: all 9 matrix reps
   across 3 models shipped meshless pawns**, and human review was only possible
   by instrumenting copies with a debug cube. *Defense*: two independent gates,
   L2's HO-5 (a mesh component with a mesh actually assigned) and L2I's
   **`pawn_visibly_represented`**, which additionally pins the mesh to the
   read-only `/Game/Characters/` pool the agent cannot author into. The pool
   anchor is what makes it ungameable by an empty placeholder asset under the
   writable path.
5. **Every behavioral gaming mode of the original** - skipping stage 1 by
   parenting to the generic scaffold, an inert or shadowed attribute set,
   moving Health from Tick with nothing activatable, "damage" as
   set-to-a-constant, "heal" as restore-to-full, and passive regeneration.
   *Defense*: **inherited unchanged**, because the fixture is the same binary -
   HO-1, HO-4, HO-6, HO-9, HO-10 and HO-11 respectively. The full argument,
   including the measured `discrimination/regen/` result that dies at HO-10
   rather than HO-11, is in `../gp-health-attribute-ops-cpp/task.md` section
   "Anti-gaming notes" and `../gp-health-attribute-ops-cpp/discrimination/MATRIX.md`.
   Per the `-bp` inheritance law (`tools/verify-single/gold_set.txt`), a twin
   legitimately inherits its C++ original's behavioral variants rather than
   cloning them.

## Hidden invariants

- **Every hidden invariant of `gp-health-attribute-ops-cpp` applies unchanged**:
  the preferred tag `Ability.Damage` disambiguating pawn resolution; the
  abstract task base being unresolvable; the preset of 60 keeping the whole leg
  inside `(0, 100)` so no clamp can shrink `Drop2` or `HealDelta`; the three
  gated ratio windows being congruent; stage order enforced by observation;
  Health read through the contract attribute; the 37-not-100 write probe; and
  samples initializing to `0.0` with nothing gating on a sentinel.
- **BP resolution is Asset-Registry-based.** The fixture only discovers
  Blueprint pawns saved under `/Game/Tasks/` - a Blueprint saved anywhere else
  (e.g. `Content/Blueprints/`) is sandbox-accepted but never resolved, and the
  task FAILs L2 for what looks like a behavioral reason. This is why the prompt
  names the folder and why `task_folder_exists` is the first L2I check.
- **Stage 1 has no BP-visible constructor, so the wiring route is different
  from the C++ one and that difference is the measurement.** A Blueprint cannot
  call `CreateDefaultSubobject`; the proven no-C++ route is `DefaultStartingData`
  on the **inherited** ability system component (an `Attributes` set class plus
  an `AttributeMetaData` DataTable), consumed at component initialization.
  Confirmed empirically on UE 5.8 2026-08-06 by the poison twin. The
  subobject-name suppression on the bare lineage does not affect it: those sets
  are created at runtime component init, not through the construction-phase
  `FObjectInitializer`.
- **The DataTable row-name contract is load-bearing**: rows must be named
  `CraftBenchAttributeSet.Health`, not bare `Health` - `InitFromMetaDataTable`
  keys them `<OwnerClass>.<Property>`, and a bare name reads back as
  "registered but never initialized", i.e. a stage-1 HO-3 FAIL that looks like
  the agent forgot to initialize.
- **An init GameplayEffect at BeginPlay is an equally conforming stage-1
  route.** The prompt states the observable contract (Health present,
  initialized to 100, readable and writable), never a mechanism, so a pawn that
  applies an instant Override-Health-100 effect to itself on BeginPlay passes
  the same gates. The reference picks `DefaultStartingData` because it is the
  route already measured on this substrate, not because it is required.
- The map places **only the fixture** and sets no `GameModeOverride`, so PIE
  also spawns the substrate's default `BP_ThirdPersonGameMode` pawn at the
  PlayerStart. It is not an `ACraftBenchCharacter` subclass, so it can never win
  pawn resolution and no gate reads it - the graded pawn is exclusively the one
  the fixture spawns and possesses.
- **No config edit is needed and none is licensed.** Both trigger tags already
  exist in `CraftBenchGameplayTags`, so nothing here requires touching
  `Config/DefaultGameplayTags.ini`; this spec declares no `config_allow`
  entries, so a config edit rides the exit-4 sandbox path.
