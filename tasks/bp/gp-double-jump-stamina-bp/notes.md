# gp-double-jump-stamina-bp - implementor notes + asset specification

> **NOTHING IN THIS FILE HAS BEEN MEASURED.** As of authoring (2026-08-10) this
> twin has never been built, never run in PIE, never graded a reference and
> never run a discrimination sweep. No UBT invocation, no `UnrealEditor` launch,
> no `cb` command and no test suite has been executed against it. The Blueprint
> reference below is a **SPECIFICATION for a serial editor pass**, not an
> authored asset - nothing under `reference/` exists yet. The `-cpp` original's
> bars are themselves still `PROPOSED - NOT YET MEASURED` in the fixture source.

## Provenance and what this twin owns

- Source row: BP-G2 **source record 33 "Movement-1"**. Family **T1.3**
  of the bp-g2 tier-1 slate; the one-shot resource-**cost** axis.
- The signed design contract is `../gp-double-jump-stamina-cpp/PIN.md`,
  including its binding `OWNER DECISION 2026-08-10 -- EDIT, then ACCEPTED` block
  (**DJ-6 CUT**; `DescribeSegments()` mandatory in the diagnostic). It is
  **normative** for the prompt, the schedule, the gates and the anti-gaming
  list.
- **Owned by this twin (all new):** `task.md`, this file, the deliverable spec
  below, `discrimination/cpp-solve*/`, and (once authored)
  `reference/Content/Tasks/gp-double-jump-stamina-bp/*.uasset`.
- **NOT owned and NOT to be forked:** the L2 fixture
  (`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/gp-double-jump-stamina/`),
  the map (`UE-projects/ThirdPerson/Content/Maps/gp-double-jump-stamina/L_DoubleJump.umap`),
  and any substrate source. Both are shared byte-identically with the `-cpp`
  original, which is what makes the two results comparable.

## Why this twin is load-bearing beyond the C++/BP comparison

`RiseEpsilon` - DJ-2c's shape floor, which doubles as the segmenter's
`MinDeltaZ` and therefore cannot be split into two constants - **must be
measured against a Blueprint lane as well as the C++ one**
(`../gp-double-jump-stamina-cpp/task.md`, Reference solution metadata). The
re-pinning hazard is two-directional: too LOW and apex jitter splits one jump
into two (a false PASS at DJ-2c) while a spurious Leg-2 rise becomes a false
FAIL at DJ-4; too HIGH and a conforming but **gentle** second jump - the prompt
fixes no jump height, deliberately - is failed for not jumping. **The second
direction is the unforgivable one**, and a Blueprint solve is exactly where a
gentler impulse is likely to show up.

## Blockers before anything can be measured

1. ~~The Blueprint reference does not exist.~~ **RESOLVED 2026-08-11 — see
   `REFERENCE-NOTE.md` (authored + graded PASS from git HEAD).** Original
   text: Three `.uasset`s must be authored
   in a live editor (specification below). Until then `cb lint` WARNs
   `reference-solution` and `cb discriminate` cannot run.
2. **The introspect script `gp_double_jump_stamina_bp.py` must exist** under
   `tools/verify-single/introspect/` or `cb lint` ERRORs
   (`introspect-script-exists`) and L2I cannot run. It is a thin wrapper over
   `_bp_variant_lib.py` configured with `pawn_base_class = "CraftBenchCharacter"`
   and `min_bp_abilities = 1` - the sibling shape of the already-committed
   `gp_health_attribute_ops_bp.py`.
3. **The whole motion sampler had never executed before the `-cpp` original**
   (`SetDenseSampling` / `Segments` / `NumRises` / `MeanVerticalRate` /
   `DescribeSegments`, plus `MaxVelocityZAfter` and four sibling reductions, had
   zero callers across both substrates as of 2026-08-10). DJ-2c gates on a
   derived quantity, which can be wrong **silently, in either direction**. Read
   the first run's `DescribeSegments()` line before believing any DJ-2c verdict.
4. **`cb lint` expectations:** `task-id-folder` clean (front-matter `id` equals
   the folder name - the ERROR that hit all three `-cpp` originals),
   `anti-gaming-count` clean (5 entries), `prompt-jargon` expected to WARN on
   "Blueprint" and the tag name (documented exceptions, not leaks).
5. **This task is NOT on `tools/verify-single/gold_set.txt`**, so
   `discrimination-coverage` does not fire on it today.

## Blueprint asset specification (the serial editor pass)

Three assets, all under `Content/Tasks/gp-double-jump-stamina-bp/`, **0 lines of
C++**. Names are for the authoring pass only - the verifier resolves by content
path + derivation + tag, never by name.

### 1. `BP_DoubleJumpPawn` - Blueprint, parent class `CraftBenchCharacter`

Class defaults:

- `GrantedAbilities` = `[GA_DoubleJump]`.
- Inherited **Mesh** component: `SkeletalMesh = /Game/Characters/Mannequins/Meshes/SKM_Manny_Simple`,
  relative location `(0, 0, -90)`, relative rotation `(Pitch 0, Yaw -90, Roll 0)`.
- **No event graph, no attribute initialization, no init DataTable.** The
  verifier presets Power itself before each leg (60 at cp1, 5 at cp6), so the
  pawn's starting Power is **not observable** and initializing it is neither
  rewarded nor required. This is the one place where this twin's deliverable is
  legitimately smaller than `gp-health-attribute-ops-bp`'s.
- Parent must be the **generic** `CraftBenchCharacter`. The bare lineage
  suppresses the attribute-set subobject entirely, so a pawn parented to it has
  no `Power` at all and dies at the cost gate by name.

### 2. `GE_DoubleJumpCost` - Blueprint, parent class `GameplayEffect`

- `Duration Policy = Instant`
- One modifier: attribute `CraftBenchAttributeSet.Power`, op **Add**
  (`ADD_BASE` in 5.8), magnitude Scalable Float **-20.0**
- No period, no duration, no stacking.

### 3. `GA_DoubleJump` - Blueprint, parent class `GameplayAbility`

- `Instancing Policy = Instanced Per Actor`
- **Ability Tags** (the 5.8 editor property backed by the ability's asset tags;
  python name `ability_tags`) = `Ability.DoubleJump`
- **`Cost Gameplay Effect Class` = `GE_DoubleJumpCost`** - this is both the
  one-shot debit (DJ-3a/3b/3c) and the refusal gate (DJ-4): a committed cost is
  refused when applying it would take the attribute below zero, so at 5 Power
  the commit fails, nothing launches and Power is left untouched.
- **No cooldown effect.**
- Graph:

```text
ActivateAbility
  -> Commit Ability
       false -> End Ability (bWasCancelled = true)          // the refusal path
       true  -> Get Avatar Actor -> Cast to Character
             -> Launch Character(LaunchVelocity = (0, 0, 600),
                                 bXYOverride = false,
                                 bZOverride  = TRUE)
             -> End Ability (bWasCancelled = false)
```

- **`bZOverride` MUST be true.** Mid-fall the character carries a large negative
  vertical velocity; an additive launch can leave the velocity still negative
  and the character still descending - it reads as "launch the character up by
  600" and never reverses anything, which is exactly the plausible-wrong solve
  DJ-2b exists to catch. With the override the reversal is independent of
  descent speed, matching the C++ reference's assign-don't-add semantics.
  (`ACharacter::LaunchCharacter` stores a pending launch velocity that
  `UCharacterMovementComponent::HandlePendingLaunch` applies on the next
  movement update, where it also switches the character to falling movement -
  the same two effects the C++ reference performs by hand.)
- **The ability must end synchronously.** `bRetriggerInstancedAbility` defaults
  false, so an ability still running at the Leg-2 trigger (1.7 s later) is
  refused for a reason that has nothing to do with the cost. DJ-4 accepts that
  leniently, but the reference would stop testing what it is for.
- **Equally conforming alternative** (what the C++ reference does): drop the
  cost effect, read Power in the graph, branch out below 20 without touching
  anything, otherwise apply an instant -20 Power effect and then launch. Both
  are one-shot debits and both satisfy DJ-3a/3b/3c and DJ-4. The cost-effect
  route is pinned here because it is fewer nodes and cannot get the refusal
  ordering wrong.

### Why these values and not others

- **+600 cm/s is the C++ reference's choice carried over unchanged.** Against
  world gravity (-980 cm/s^2 - stock across this substrate: the whole
  `ThirdPerson/Config` tree has zero `gravity` hits and the base pawn never
  touches `CharacterMovement`) a reversal to +600 rises `600^2 / 1960 = 183.7
  cm`, a **9.2x margin** over `RiseEpsilon` = 20 cm, and time-to-apex `0.612 s`
  is ~37 dense samples at `-FPS=60` - a monotonic run far too long for the
  segmenter to mistake for jitter. 600 is also a plausible jump velocity on its
  own terms (stock `JumpZVelocity` is 420-700 across the templates), so it is
  not a number reverse-engineered from a bar.
- **20 is the only disclosed number in the prompt**, which is what makes DJ-3b
  a lawful absolute.
- **Predicted trace, inherited from the C++ reference and PREDICTED not
  measured:** free fall gives `vZ ~ -686` and `z ~ 960` at the trigger (DJ-2a);
  the rise reaches `z ~ 1144` at `t ~ 1.31` (DJ-2b, DJ-2c); back to `z ~ 975` at
  `t = 1.90`; lands at `t ~ 2.78`. Power `60 -> 40` at trigger+0.3 and flat at
  trigger+1.2 (DJ-3a/3b/3c); Leg 2 stays at `5.0` with no rise (DJ-4). The
  segment decomposition at `MinDeltaZ = 20` is
  `[FALL (pre-trigger) | RISE d=+184 | FALL]`, i.e. **one** rise, not two.
  Expect the Blueprint lane to sit **one frame later** than the C++ prediction
  because the launch is applied on the next movement update; that is latency,
  not magnitude, and no gate reads a time. **If the first real run diverges from
  this in any other way, stop and find out why before touching a bar.**

## What must be measured before this task is trusted

1. Author the three assets, then grade the reference from git HEAD. Expect
   **overall PASS**, L2I **5/5**, and the predicted trace above.
2. **Read `DescribeSegments()` for both the Leg-1 window and the full series on
   that first run.** A conforming solve here decomposes as
   `[FALL | RISE | FALL]` and `NumRises(20) == 1`; the base class's own doc
   comment says a double jump is 2, which is true only for a pawn that jumped
   from the ground first. **Anyone "fixing" the gate to `>= 2` to match that
   comment would false-FAIL every conforming solve, including both references.**
3. **Pin `RiseEpsilon` against a measured population of conforming BP impulses**,
   not against the 600 cm/s reference alone. Record the gentlest conforming
   impulse's realized rise and the largest jitter excursion, and put the floor
   between them with margin on each side. Note the third constraint the map
   adds: landing sits inside DJ-4's start-keyed window and the walking-mode
   floor adjustment moves the capsule up by at most ~2.4 cm, so the floor can
   never drop near that value either.
4. `cb discriminate`: reference PASS; empty FAIL (at DJ-7 visibility, which runs
   at cp0 before anything else, or at DJ-1 - record which, do not assume);
   `cpp-solve/` FAIL at `bp_pawn_present`; `cpp-solve-with-bp/` FAIL at
   `resolved_pawn_is_blueprint`.
5. **Cross-twin invariance check:** the `-cpp` and `-bp` references must produce
   the same `[DOUBLEJUMP-FINAL]` numbers within jitter, allowing for the
   one-frame launch latency above.

## Open risks and unverified claims

- **The cost-effect refusal path has not been live-validated on this
  substrate.** The semantics relied on are standard GAS (a committed cost is
  refused when applying its modifiers would take an attribute below zero, so 5 -
  20 refuses), but if the first run shows the ability firing at 5 Power,
  switch the reference to the explicit read-and-branch alternative documented
  above - it is what the C++ reference does and it needs no engine behavior
  beyond an attribute read. **Do not "fix" DJ-4 in response; fix the
  reference.**
- **The one-frame launch latency is asserted from the engine's pending-launch
  path, not measured.** It cannot affect a pure-direction or pure-shape gate,
  but it is the most likely source of a small `-cpp` vs `-bp` trace difference,
  and recording it now is what stops that difference being read as a defect
  later.
- **The L2I native sweep does not cover a native cost effect.**
  `_bp_variant_lib.py` sweeps native subclasses of the scaffold PAWN only, so a
  C++ `UGameplayEffect` referenced from a Blueprint ability passes all five
  checks while adding C++ the prompt forbids. Recorded as ARGUED, NOT DEFENDED
  in `task.md`; closing it is the internal design note (not shipped) V2.1's
  native-decoy sweep, which is not built.
- **AG-7 is inherited as an explicit gap**: "unlimited air jumps while Power
  lasts" has no gate on either twin, because DJ-6 was cut by owner decision
  2026-08-10 as an undisclosed limit. Do not read either task's anti-gaming list
  as claiming a defense there.
- **The `-cpp` original's own spec banners are stale** (they still say the
  folder must be renamed and the map binary does not exist; both are done, and
  `L_DoubleJump.umap` is committed). Correct them when that task is next
  touched; do not copy them.

## Prompt delta vs the `-cpp` original (moved from task.md 2026-08-16; lint spec-h2-allowlist)

Not agent-visible (`prompt_extract.py` allow-lists only `## Prompt given to the
agent` and `## Workspace state pre-task`). Recorded here as a literal
before/after because prompt direction on this codebase has flip-flopped twice
under paraphrased confirmation.

**Exactly one bullet is replaced. Every other character of the prompt is the
`-cpp` original's, which is PIN.md section 1 verbatim** - in particular
"**reverse and carry it upward again**" is load-bearing prose and is NOT
interchangeable with "launch the character upward": under the looser wording the
plausible-wrong solve is arguably conforming, DJ-2b's FAIL would be unfair, and
the family would lose its load-bearing discriminator.

BEFORE (`gp-double-jump-stamina-cpp`):

```text
- Deliver your pawn as a subclass of the provided character (C++ or Blueprint)
  with your ability granted on it.
```

AFTER (this twin):

```text
- Deliver your solution **entirely as Blueprint assets** created in the editor
  and saved under `Content/Tasks/gp-double-jump-stamina-bp/`: a Blueprint
  subclass of the provided character with your ability granted on it. **Do not
  add or modify any C++ source for this task.** That content folder is the
  only path the verifier looks in.
```

The delta deliberately does **not** name an impulse mechanism, a jump height, or
the ability's cost machinery. The C++ original discloses exactly one number (the
cost of 20) and this one discloses exactly the same one.
