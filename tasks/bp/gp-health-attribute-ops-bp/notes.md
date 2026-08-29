# gp-health-attribute-ops-bp - implementor notes + asset specification

> **NOTHING IN THIS FILE HAS BEEN MEASURED.** As of authoring (2026-08-10) this
> twin has never been built, never run in PIE, never graded a reference and
> never run a discrimination sweep. No UBT invocation, no `UnrealEditor` launch,
> no `cb` command and no test suite has been executed against it. The Blueprint
> reference below is a **SPECIFICATION for a serial editor pass**, not an
> authored asset - nothing under `reference/` exists yet.

## Provenance and what this twin owns

- Source row: BP-G2 **source record 29 "Health-1"**. Family **T1.1**,
  the Band-A floor of the bp-g2 tier-1 slate.
- The signed design contract is `../gp-health-attribute-ops-cpp/PIN.md`. It is
  **normative** for the prompt, the schedule, gates HO-1..HO-11 and the
  anti-gaming list. This twin implements the same contract on a different
  authoring surface; it does not redesign any of it.
- **Owned by this twin (all new):** `task.md`, this file, the deliverable spec
  below, `discrimination/cpp-solve*/`, and (once authored)
  `reference/Content/Tasks/gp-health-attribute-ops-bp/*.uasset`.
- **NOT owned and NOT to be forked:** the L2 fixture
  (`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-health-attribute-ops/`),
  the map (`UE-projects/ThirdPerson/Content/Maps/gp-health-attribute-ops/L_HealthOps.umap`),
  and any substrate source. Both are shared byte-identically with the `-cpp`
  original, which is what makes the two results comparable. A per-variant copy
  of either silently ends the comparison.

## Blockers before anything can be measured

1. ~~The Blueprint reference does not exist.~~ **RESOLVED 2026-08-11 — see
   `REFERENCE-NOTE.md` (authored + graded PASS from git HEAD).** Original
   text: Six `.uasset`s must be authored
   in a live editor (specification below). Until then `cb lint` WARNs
   `reference-solution`, `cb discriminate` cannot run, and the task cannot be
   smoke-tested. This is the ONLY blocker that needs an editor.
2. **The `cpp-solve-with-bp/` discrimination variant is only half-authorable
   without the reference.** Its Blueprint half is by definition the reference's
   assets shipped alongside the C++ solve, so it cannot be completed before
   step 1. Its C++ half is already on disk.
3. **`cb lint` expectations once the reference lands:** `task-id-folder` clean
   (front-matter `id` equals the folder name - this is the ERROR that hit all
   three `-cpp` originals, do not repeat it), `l2i-introspect` clean
   (`introspect:` names `gp_health_attribute_ops_bp.py`, which exists),
   `introspect-script-exists` clean, `anti-gaming-count` clean (5 entries, the
   3-5 window), `prompt-jargon` expected to WARN on "Blueprint" and the tag
   names - those are the documented deliverable-format and GAS-category
   exceptions, not leaks.
4. **This task is NOT on `tools/verify-single/gold_set.txt`.** The
   `discrimination-coverage` rule therefore does not fire on it. If it is ever
   added, every anti-gaming note already carries either a variant path or an
   inherited/argued pointer, so it should pass as written - but re-run the lint,
   do not assume.

## Blueprint asset specification (the serial editor pass)

Six assets, all under `Content/Tasks/gp-health-attribute-ops-bp/`, **0 lines of
C++**. Names below are for the authoring pass only - **the verifier resolves by
content path + derivation + tag, never by asset name.**

### 1. `DT_HealthInit` - DataTable, row struct `AttributeMetaData`

| row name | BaseValue |
|---|---|
| `CraftBenchAttributeSet.Health` | 100.0 |
| `CraftBenchAttributeSet.MaxHealth` | 100.0 |

- **The row name contract is load-bearing.** `InitFromMetaDataTable` keys rows
  as `<OwnerClass>.<Property>`; a bare `Health` row reads back as "registered
  but never initialized" and produces a stage-1 HO-3 FAIL that looks like the
  agent forgot to initialize. Byte-verified in the committed poison equivalent
  2026-08-08.
- `MaxHealth` is initialized for coherence only. **No gate in this task reads
  it** and the contract attribute set applies no clamping, so it cannot bound
  the heal or interact with HO-8/HO-10.

### 2. `BP_HealthOpsPawn` - Blueprint, parent class `CraftBenchBareCharacter`

Class defaults:

- Inherited **AbilitySystemComponent** -> `DefaultStartingData`: **one** entry
  with `Attributes = CraftBenchAttributeSet` and
  `DefaultStartingTable = DT_HealthInit`. **This is the whole of stage 1 on the
  no-C++ lane** and it is the route empirically confirmed on UE 5.8 2026-08-06
  by `gp-poison-dot-stack-bp` (`../gp-poison-dot-stack-bp/REFERENCE-NOTE.md`).
  It is safe on THIS lineage precisely because the bare base suppresses the
  constructor-time attribute-set subobject, so exactly one set is ever created.
- `GrantedAbilities` = `[GA_Damage, GA_Heal]` (order irrelevant).
- Inherited **Mesh** component: `SkeletalMesh = /Game/Characters/Mannequins/Meshes/SKM_Manny_Simple`,
  relative location `(0, 0, -90)`, relative rotation `(Pitch 0, Yaw -90, Roll 0)`.
- No event graph is needed on the happy path.

### 3. `GE_Damage` - Blueprint, parent class `GameplayEffect`

- `Duration Policy = Instant`
- One modifier: attribute `CraftBenchAttributeSet.Health`, op **Add**
  (`ADD_BASE` in 5.8), magnitude Scalable Float **-10.0**
- No period, no stacking, no duration.

### 4. `GE_Heal` - Blueprint, parent class `GameplayEffect`

- Identical to `GE_Damage` with magnitude **+10.0**.

### 5. `GA_Damage` - Blueprint, parent class `GameplayAbility`

- `Instancing Policy = Instanced Per Actor`
- **Ability Tags** (the 5.8 editor property backed by the ability's asset tags;
  python name `ability_tags`) = `Ability.Damage`. This is what both
  `NumGrantedAbilitiesWithTag` and `TryActivateAbilitiesByTag` read.
- Graph: `ActivateAbility` -> `Commit Ability` -> on failure `End Ability`
  (cancelled); on success `Apply Gameplay Effect to Owner` (`GE_Damage`,
  Level 1) -> `End Ability`.
- No cooldown effect, no cost effect, nothing held open: the fixture activates
  the damage ability **twice, 0.7 s apart**, and an ability still running or on
  cooldown refuses the second activation (HO-6 then FAILs on work whose only
  fault is that it held itself open).

### 6. `GA_Heal` - Blueprint, parent class `GameplayAbility`

- Identical to `GA_Damage` with **Ability Tags** = `Ability.Heal` and
  `GE_Heal`.

### Why these values and not others

- **The +/-10 magnitude is the C++ reference's choice carried over unchanged.**
  It sits mid-band inside HO-8's disclosed 5-25 window and makes HO-9
  (`Drop2/Drop1`) and HO-10 (`HealDelta/Drop1`) read exactly **1.00**. Carrying
  it over is what keeps a `-cpp` vs `-bp` difference attributable to the
  authoring surface rather than to the reference.
- **Instant effects, not a direct attribute poke.** An instant effect leaves
  nothing active afterwards, so HO-11's idle window `(cp3, cp4]` is satisfied
  structurally rather than by luck.
- **Predicted trace, inherited from the C++ reference and PREDICTED not
  measured:** preset 60 -> `H1 = 50` -> `H2 = 40` -> `H3 = 50` -> `H4 = 50`;
  `Drop1 = Drop2 = HealDelta = 10`, `IdleDelta = 0`, both ratios `1.00`. If the
  first real run does not reproduce this line for line, stop and find out why
  before touching a bar.

## What must be measured before this task is trusted

1. Author the six assets, then grade the reference from git HEAD. Expect
   **overall PASS**, L2I **5/5**.
2. `cb discriminate` once the variants are complete. Expected rows: reference
   PASS; empty FAIL (at HO-1 derivation, or at HO-5 visibility if the
   checkpoint-0 order puts it first - record which, do not assume);
   `cpp-solve/` FAIL at `bp_pawn_present`; `cpp-solve-with-bp/` FAIL at
   `resolved_pawn_is_blueprint`.
3. Record both populations (conforming and non-conforming) for every bar the
   `-cpp` original still carries as `PROPOSED - NOT YET MEASURED`, with the
   margin on each side. A bar is not calibrated until that is written down.
4. **Cross-twin invariance check:** the `-cpp` and `-bp` references must produce
   the same `[HEALTHOPS-FINAL]` numbers within jitter. They exercise the same
   fixture with the same magnitudes, so a divergence is evidence about the
   authoring lane (or about a duplicated attribute set), not noise.

## Open risks and unverified claims

- **`DefaultStartingData` is confirmed on this lineage; do not port that
  confidence to the generic one.** The ability system component consumes
  `DefaultStartingData` in `OnRegister`, which runs BEFORE the
  `InitializeComponent` scan that registers attribute sets constructed as
  subobjects of the owner. On the bare lineage there is no such subobject, so
  exactly one set exists. On the generic lineage a second set of the contract
  class would be created - see `../gp-heal-over-time-bp/notes.md`.
- **The `-cpp` original's own spec banners are stale** (they still say the
  folder must be renamed and the map binary does not exist; both are done, and
  the folder is `gp-health-attribute-ops-cpp` with `L_HealthOps.umap`
  committed). Do not copy those banners into anything new, and correct them
  when that task is next touched.
- **HO-11 has no committed discrimination variant that dies at it** - the
  `regen/` variant was MEASURED 2026-08-10 dying at HO-10 instead. That gap is
  the `-cpp` original's to close (a `slow-regen/` variant tuned to pass
  HO-7..HO-10 and trip only HO-11) and this twin inherits it.
- **Constraint C1 applies here** (the internal design note (not shipped)): this id must never
  share a graded bench cell with any `gp-poison-dot-stack-*` id, because the
  stage-1 ladder is lifted verbatim.

## Prompt delta vs the `-cpp` original (moved from task.md 2026-08-16; lint spec-h2-allowlist)

Not agent-visible (`prompt_extract.py` allow-lists only `## Prompt given to the
agent` and `## Workspace state pre-task`). Recorded here as a literal
before/after because prompt direction on this codebase has flip-flopped twice
under paraphrased confirmation.

**Exactly one bullet is replaced. Every other character of the prompt is the
`-cpp` original's, which is PIN.md section 1 verbatim.**

BEFORE (`gp-health-attribute-ops-cpp`):

```text
- Deliver your pawn as a subclass of the provided task character (C++ or
  Blueprint) with both abilities granted on it. If you author Blueprint
  assets, save them under `/Game/Tasks/gp-health-attribute-ops-cpp/` -- that
  is the only content path the verifier looks in.
```

AFTER (this twin):

```text
- Deliver your solution **entirely as Blueprint assets** created in the editor
  and saved under `Content/Tasks/gp-health-attribute-ops-bp/`: a Blueprint
  subclass of the provided task character with your health system built on it
  and both abilities granted on it. **Do not add or modify any C++ source for
  this task.** That content folder is the only path the verifier looks in.
```

Two things the delta deliberately does **not** do:

1. **It does not touch stage 1's wording.** `gp-poison-dot-stack-bp` adds
   "wired and initialized **in the editor**, not in C++" to its stage-1
   sentence; this twin does not, because the replaced bullet's "Do not add or
   modify any C++ source for this task" already covers the whole submission and
   a second statement of the same constraint is prompt drift, not clarity. If a
   measured reading ever shows agents building stage 1 in C++ *despite* that
   bullet, adopt poison's sentence - and record it as a redefinition epoch,
   because it changes the prompt.
2. **It does not restate the path in `/Game/` form.** The `-cpp` bullet uses
   the `/Game/Tasks/...` mount path; the `-bp` bullets across the family use
   the on-disk `Content/Tasks/...` form, which is also the form
   `AGENT_WRITABLE.json` accepts. The two name the same folder.
