---
id: t1-shoved-block-slides-on-one-rail
substrate: ThirdPerson
set: craftbench-public
tier: T1
capability_bucket: Architecture & Systems
category: gameplay
layers: [L1, L2]
fixtures: ["L_RailBench :: AShovedBlockRailFunctionalTest"]
---

# t1-shoved-block-slides-on-one-rail

A showroom physics task on the **ThirdPerson substrate**: the character walks
into a plunger post and it shoves two identical blocks at the same instant with
the same push. The block standing on the painted rail must track that rail —
no sideways drift, no height change, no spin — while its un-railed twin, given
the identical push, tumbles clear in an arc. The character backs out and walks
in again, and both blocks do the same thing a second time. The twin **is** the
control and is gauged at every checkpoint: it is also what proves the push was
genuinely off-axis, so the off-axis and no-spin gates can never degenerate into
dead gates.

Imported from corpus row `t1-joint-constrains-to-axis`
(an internal design note (not shipped), Hardening Status
"ALREADY STRONG"; owner verdict `agree`). Provenance, every deviation from the
corpus row, and the artifacts still to build are in `notes.md` beside this file.

## Primary concept

- `physics-constraints` — Physics Constraints
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/physics-constraints-in-unreal-engine)

The load-bearing behavior is a simulating rigid body whose freedom is reduced
to one translation axis that is **not** a world axis, with the other two
translations and all three angular degrees locked, and which stays tethered to
that axis after an external displacement. The `weight_tier: high` concept row
files under **Architecture & Systems**; the observable is pure gameplay physics.

## Prompt given to the agent

> The level has a plunger post standing in the open and, beyond it, two
> identical blocks sitting about 3 m apart. One block stands on a painted rail
> line; the other stands on bare floor. When the character walks into the
> plunger, it shoves both blocks at the same instant with the same push. That
> push is aimed mostly along the painted rail — roughly five parts along the
> rail, two parts sideways off it, one part upward — and it lands off the
> block's centre, so it also tries to spin the block. The plunger re-arms once
> the character steps out of it, so walking in again shoves both blocks again.
>
> Make the block that stands on the painted rail behave as if the rail holds
> it:
>
> - It may only travel along the rail, and each shove must carry it at least
>   200 cm further along the rail line.
> - It must never sit more than 8 cm to either side of the rail line, never
>   more than 10 cm above or below the height it starts at, and never be turned
>   more than 10 degrees from the facing it starts with — during a shove and
>   after it.
> - It must remain a body the world's physics moves, not something driven along
>   a path: it stays physics-simulating, and its own physics velocity is what
>   carries it (at least 100 cm/s at some point during each slide).
> - The rail must keep holding it. If something lifts the block off the rail —
>   say 60 cm to one side and 40 cm up — the block must end up back on the rail
>   line within about 1.5 s: back within 10 cm of the line, within 10 cm of its
>   rail height, and not turned.
> - It must do all of this on every shove, not only the first one.
>
> The painted rail does not run along a world axis: it crosses the floor 30
> degrees off the world X axis. The block is placed square with the rail, so
> the block's own forward direction already points along the rail.
>
> The second block is the comparison and must be left exactly as it is. Given
> the same push it is expected to be thrown clear of its own start line — at
> least 60 cm off after the first shove and at least 100 cm off after the
> second — and to end up turned at least 45 degrees. Leave the plunger and the
> push it delivers alone as well; both are already built.
>
> Before the character reaches the plunger, both blocks stand still on their
> marks: within **10 cm** of the mark it was placed on, turned no more than the
> same **10 degrees** from its start facing that applies during a slide, and
> moving slower than **5 cm per second**. Nothing may move either block until the
> character walks into the plunger. Settling onto the rail at play start is fine —
> those are the numbers it has to settle inside.
>
> Work in C++ in the project's existing gameplay module under
> `Source/ThirdPerson/` — never `Source/CraftBenchTemplate/`, which is not part
> of this project's writable surface. Do not edit the level, any config file,
> or any test file.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** — the agent-writable runtime module
on this substrate. `Source/CraftBenchTemplate/` does not belong to this project
and a submission file under it is a SANDBOX-REJECT (exit 4), not a graded FAIL.
`Source/CraftBenchTests/` is deny-listed, as are `Content/Maps/` and `Config/`.

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed. Nothing
  this task needs is missing from the module's dependencies: there is no
  `.Build.cs` edit and no plugin to enable.
- `Tasks/t1-shoved-block-slides-on-one-rail/BenchBlockActor.h` / `.cpp` —
  declares and defines `class THIRDPERSON_API ABenchBlockActor : public AActor`:
  a 60 cm cube static-mesh root that the world's physics already moves, mass
  50 kg, solid to everything. This base carries **all** the physical setup, so the
  two placed blocks are identical bodies by construction rather than by
  promise. No motion logic ships, and nothing holds either block to anything.
- `Tasks/t1-shoved-block-slides-on-one-rail/RailBlockActor.h` / `.cpp` —
  `class THIRDPERSON_API ARailBlockActor : public ABenchBlockActor`; the
  constructor adds `Tags.Add(FName("RailBlock"))` and nothing else. **This is
  the graded subject** and the only class the task asks the agent to change
  (a subclass grades identically — the tag inherits).
- `Tasks/t1-shoved-block-slides-on-one-rail/TwinBlockActor.h` / `.cpp` —
  `class THIRDPERSON_API ATwinBlockActor : public ABenchBlockActor`; the
  constructor adds `Tags.Add(FName("TwinBlock"))` and nothing else. **This is
  the control** and must stay as shipped.
- `Tasks/t1-shoved-block-slides-on-one-rail/PlungerActor.h` / `.cpp` —
  `class THIRDPERSON_API APlungerActor : public AActor`, tagged `Plunger`.
  **Fully implemented, not a stub:** a post mesh plus a query-only box trigger;
  when a character walks into it, it gives every `RailBlock`- and
  `TwinBlock`-tagged body in the level one identical shove, delivered the same way
  to both and aimed partly along the rail, partly across it and partly upward
  (~5:2:1, read from the rail marker's forward axis) rather than squarely down the
  rail. It logs one `[t1-rail calib] shove #<n>` line and re-arms once the
  character steps away.
- `Tasks/t1-shoved-block-slides-on-one-rail/RailActor.h` / `.cpp` — the painted
  rail: a long, low, non-simulating static-mesh plinth tagged `RailLine` whose
  **forward axis is the rail direction**. It is a solid, immovable body the
  block may be anchored to; it needs no code and should not gain any.
- `Tasks/t1-shoved-block-slides-on-one-rail/BenchCharacter.h` / `.cpp` — a
  concrete, spawnable subclass of the project's third-person character (the
  stock template character is abstract). Its constructor assigns a mannequin
  skeletal mesh and anim blueprint from the read-only `/Game/Characters/` pool
  so the hero is visible on screen, and adds `Tags.Add(FName("BenchHero"))`.
- `Tasks/t1-shoved-block-slides-on-one-rail/BenchGameMode.h` / `.cpp` — a game
  mode whose constructor sets `DefaultPawnClass = ABenchCharacter::StaticClass()`.
  The map's world settings select it, so PIE spawns and possesses the tagged,
  visible character at the PlayerStart — the same pawn a human drives with WASD.

Content that **exists** (verifier-owned, deny-listed):

- `Content/Maps/t1-shoved-block-slides-on-one-rail/L_RailBench.umap` —
  the staged showroom: a flat floor with stripe markings every 200 cm running
  perpendicular to the rail (so 200 cm of rail travel is one stripe by eye); a
  2,400 cm painted `ARailActor` crossing the floor 30 degrees off world X; one
  `ARailBlockActor` standing on the rail's near end and one `ATwinBlockActor`
  300 cm away from it, perpendicular to the rail, on bare floor, both square
  with the rail and both in one camera frame; one `APlungerActor` 400 cm behind
  the pair on the rail bearing; a PlayerStart ~900 cm further back, off the
  world origin, facing the plunger and the blocks; a tall landmark pillar at
  each end of the backdrop so a moving camera reads as moving; and one placed
  `AShovedBlockRailFunctionalTest`.
- `cameras.json` (the camera-plan lane; not part of this release) — **not committed yet and not under `Content/`**: it lives beside
  this spec at `cameras.json` and is item 4 of
  `notes.md`'s still-to-build list, as is the `.umap` above. When it lands it is a
  presentation-only camera plan framing subject, twin,
  plunger and at least four stripes. Non-gating.

Files that **do not exist**:

- Nothing that holds the block to its rail ships: no added components, no
  motion or restraint code, and nothing anywhere that holds the block to its
  rail. The empty submission
  compiles (L1 green) and fails L2 on the first shove's off-rail gate.
- No test source in the agent's writable path. `AShovedBlockRailFunctionalTest`
  lives in the `CraftBenchTests` module the agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t1-shoved-block-slides-on-one-rail/L_RailBench.umap` on the
**ThirdPerson** substrate, at a fixed deterministic step
(`-deterministic -FPS=60`). Verification primitive:
**pie-state-probe** (in-fixture rigid-body transform / velocity / simulation
reads after tag-resolve) clocked by **pie-checkpoint-sampling**.

**No second-pawn spawner is needed here, and the implementor must not go
looking for a shared helper.** `AShovedBlockRailFunctionalTest` derives from
`ACraftBenchFunctionalTest` (**not** `ACraftBenchPawnFunctionalTest`): the
graded subject and the control are both *placed blocks*, and the single pawn is
spawned and possessed by the map's game mode and resolved by tag. Nothing in
either base class is changed, and no fixture-local pawn spawner is duplicated.

All rail measurements are expressed in the rail frame: `s` = distance along the
authored rail direction, `d` = signed perpendicular horizontal distance from
the rail line, `z` = height. The fixture holds the authored rail direction as a
constant of the map contract **and** asserts the placed `RailLine` marker still
matches it at every checkpoint — so rotating the rail at runtime to make a
world-axis lock "correct" is not a route.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

**There is no warning assert, deliberately.** An earlier draft carried `no new
shadowed-variable / deprecated-declarations warnings in the agent-touched
compilation units`, and the grade would have depended on a rule the prompt never
states. It is also not the rule it describes: `--strict-warnings` is
`action="store_true"` and **off by default** (`run_task.py:1035`) and no
`aura_rig` path passes it, so on `cb eval` / `cb refgate` the assert never ran at
all; and when it does run it is `l1.warning_count_agent_files > 0`
(`layers/registry.py:100`) — **any** warning, with no shadowed/deprecated filter
and no new-since-baseline baseline. With `--strict-warnings` now genuinely
enforcing, keeping it would FAIL a working solution that touches a deprecated API
on an unstated rule. L1 here is exactly the two UBT targets.

### L2 — AFunctionalTest behavioral trace

```text
AShovedBlockRailFunctionalTest (derives ACraftBenchFunctionalTest):
    PrepareTest():
        Super::PrepareTest()                       // base: fixed dt
        resolve by tag, exactly one each (never by class):
          "RailBlock", "TwinBlock", "Plunger", "RailLine", "BenchHero"
          (named failure per tag, e.g. "... tagged 'RailBlock' ...")
        assert RailLine's forward axis matches the authored rail bearing
          within 0.5 deg and its origin within 5 cm  ("the rail marker is not
          where the level put it")
        assert the hero carries a mesh component with a non-null asset that is
          visible and not zero-scaled ("the playable character has no visible
          mesh") -- owner bar #1: an invisible run is unreviewable
        record Rail0/Twin0 = each block's start location + rotation; both
          blocks' primitive components cached for physics reads
        SetCheckpointSchedule({0.7, 4.5, 8.5, 10.1})   // NOT disclosed

    Tick (every frame, after the base checkpoint clock; never ticks the world):
        while driving: AddMovementInput toward / away from the plunger
          (input is consumed per frame, so it is re-applied every tick)
        measure the shove instants instead of assuming them: the first frame
          the TWIN's speed exceeds 50 cm/s latches T_shove1, then T_shove2
          after the drive has re-entered the plunger
        CONTINUOUS pre-contact guard: if either block moves more than 10 cm from
          its mark while the hero is still more than 250 cm from the plunger,
          FAIL "the blocks moved before the character reached the plunger"
          (10 cm, matching cp0 and the prompt; 250 cm is fixture drive geometry)
        per-shove windows: accumulate the railed block's max rigid-body linear
          speed and its max |d|, |dz| and turn angle since its shove

    OnCheckpoint(i):
      cp0 t=0.7  BEFORE state, photographable:
        both blocks: speed < 5 cm/s, within 10 cm of their marks, within 10 deg
          of their start facing, and SimulatePhysics true
          (4 named gates: rail-at-rest, twin-at-rest, rail-simulating,
           twin-simulating)
          [10 cm and 10 deg, not the earlier 5 cm and 2 deg. Both of those were
           graded and undisclosed, and the 2 deg was TIGHTER than the 10 deg the
           prompt promised for a slide — so a constraint whose projection settled
           the block 3 deg at t=0, or snapped it 6 cm onto the line, FAILed cp0 on
           a number it was never told while satisfying every number it was. The
           bands now match the prompt's, which states all three.]
        start driving the hero toward the plunger (contact expected ~2.5 s)
      cp1 GRADED AT max(4.5, T_shove1 + 1.5), NOT at a fixed 4.5. If the
                 checkpoint clock crosses 4.5 before that instant, the fixture
                 DEFERS the cp1 assertions to the first later frame at which
                 t >= T_shove1 + 1.5 and grades them there.
                 (If no shove was seen by 4.0 s -> FAIL "the plunger never shoved
                 the blocks".)
                 [WHY: T_shove1 is MEASURED, not assumed, and the spec's own
                  drive expects contact ~2.5 s while allowing as late as 3.9 s.
                  At T_shove1 = 3.9 a fixed cp1 = 4.5 leaves 0.6 s of the required
                  1.5 s window, so the "s advanced >= 200 cm" and window-max gates
                  would grade a slide that has barely started — a false FAIL on
                  correct work, from the schedule rather than the submission. The
                  deferral makes the 1.5 s a real minimum. The base class's
                  TimeLimit is set from the LAST checkpoint plus the maximum
                  possible deferral, so a deferred grade can never run out of
                  time.]
        railed: s advanced >= 200 cm since cp0
        railed: max |d| <= 8 cm over the whole window (not just at the sample)
        railed: max |dz| <= 10 cm ; max turn <= 10 deg ; still simulating
        railed: max rigid-body speed in the window >= 100 cm/s
        twin  : |d| from Twin0 >= 60 cm AND turn >= 45 deg  (CONTROL: this is
                also what certifies the push was genuinely off-axis and
                off-centre -- with a purely axial push these gates fail and
                the task reports it instead of silently going vacuous)
        then reverse the drive: walk the hero out of the plunger, then back in
      cp2 GRADED AT max(8.5, T_shove2 + 1.5), deferred the same way and for the
                 same reason (the walk-out/walk-in cycle only begins when cp1 is
                 graded, so T_shove2 moves with cp1). Same six
                 railed gates with distinct named messages, s measured from
                 the cp1 position (a further >= 200 cm), |d| still from the
                 rail line; twin: |d| >= 100 cm AND turn >= 45 deg
        then KNOCK both blocks: relocate each +60 cm along d and +40 cm in z
          (teleport-physics), recording each block's pre-knock d
      cp3 GRADED 1.6 s AFTER THE KNOCK (which happens when cp2 is graded, so
                 this instant moves with cp2) — the TETHER leg. FOUR named gates,
                 enumerated the way cp0's are:
        railed, `rail-back-on-line`   : within 10 cm of the rail line
        railed, `rail-back-at-height` : within 10 cm of rail height
        railed, `rail-back-square`    : within 10 deg of start facing
        railed, `rail-still-simulating`: SimulatePhysics still true
        twin, `twin-stays-off-its-line`: the twin's |d| from its OWN START LINE is
                still at least 40 cm GREATER than its pre-knock |d| was — i.e. the
                knock's displacement is still there and nothing pulled the twin
                back toward its line.
                [The earlier wording was "still at least 40 cm from where the
                 knock put it, measured against its own pre-knock d", which names
                 two mutually exclusive references and is unimplementable. On the
                 literal first reading (40 cm from the KNOCKED POSITION) it is
                 also INVERTED: an untouched twin dropped +40 cm in z lands ~40 cm
                 from that position, i.e. exactly at the threshold — a coin flip —
                 while a RAILED twin (the cheat this gate exists to catch) travels
                 ~72 cm back to its line and PASSES comfortably. Only the
                 pre-knock-d reading discriminates, so that is the one specified,
                 and the "from where the knock put it" clause is deleted.]
        -> FinishTest(Succeeded)
    every checkpoint logs
      "[t1-rail calib] cp<i> t=<t> rail s=<s> d=<d> dz=<dz> turn=<a> v=<v>
       twin d=<d> turn=<a>"  (LogTemp/Display) for tolerance calibration.
```

**Pass criteria**: both L1 targets and L2 green. **Robust identity**: every
actor is resolved by tag, never by class, so subclassing or renaming
`ARailBlockActor` is free. **Message law**: every gate's FAIL text is ASCII-only
and unique across the fixture (the cp1252 log read-back rule + the
`fixture-fail-unique` lint law), so a MATRIX row can say which gate fired.

### Requirement coverage

Every prompt requirement, the gate that checks it, and when that gate is
skipped. A requirement with no gate is the hole this table exists to find.

| Prompt requirement | Gate | Skipped when |
|---|---|---|
| travels >= 200 cm along the rail per shove | cp1 / cp2 `s` advance | shove never observed (own named FAIL) |
| never > 8 cm off the rail line | cp1 / cp2 window max `\|d\|` | — |
| never > 10 cm off rail height | cp1 / cp2 window max `\|dz\|` | — |
| never turned > 10 degrees | cp1 / cp2 window max turn | — |
| stays a physics-simulating body | cp0 / cp1 / cp2 / cp3 simulate read | — |
| own physics velocity carries it | cp1 / cp2 window max rigid-body speed | — |
| rail re-tethers after a 60 cm / 40 cm knock | cp3 recovery gates | cp2 already failed |
| same behavior on every shove | cp2 repeats all six cp1 gates | shove 2 never observed |
| both blocks at rest before contact | cp0 rest gates + continuous guard | — |
| the twin is untouched and thrown clear | twin gates at cp0, cp1, cp2, cp3 | — |
| the supplied rail is not moved | `RailLine` transform assert, every cp | — |
| the character is visible | mesh assert in `PrepareTest` | — |

## Reference solution metadata

- LOC range: 20-45 (one constraint component on `ARailBlockActor`, its two
  constrained bodies wired to the block and the rail anchor, the constraint
  frame taken from the block's own forward axis, one translation freed, the
  other two locked, all three angular degrees locked)
- Files touched: 2 (both pre-existing scaffold files: `RailBlockActor.{h,cpp}`)
- Senior-dev hours: 1.0-2.0

## Hidden invariants

- The four checkpoint instants (0.7 / 4.5 / 8.5 / 10.1) are not disclosed; only
  the physical thresholds are. The shove instants are **measured** from the
  control twin's motion rather than assumed, so a solution timed against a
  guessed schedule has nothing stable to fit.
- The off-rail, height and turn gates are evaluated against the **window
  maximum** across each shove, not against the value at the sample instant. A
  block that swings wide and settles back onto the line before the checkpoint
  still fails.
- The cp3 knock is the leg that separates a real tether from a hand-rolled
  per-tick velocity clamp. A clamp that zeroes the off-axis and angular
  velocity every frame satisfies every cp1/cp2 gate, but it cannot bring the
  block *back* to a line it was displaced from: it either falls straight down
  60 cm off the rail (off-line FAIL) or, if the vertical velocity is clamped
  too, hangs 40 cm in mid-air and slides along the rail in the air (height
  FAIL). The requirement is disclosed in the prompt, so this grades a stated
  behavior rather than a route.
- The knock is applied to BOTH blocks and recovery is measured per block
  against its **own** pre-knock offset, so neither "the twin was already far
  away" nor "the twin was already on its mark" can manufacture the control
  reading.

## Anti-gaming notes

1. **Empty or partial submission.** *Failure mode*: the scaffold compiles with
   no rail behavior at all; L1 passes. *Defense*: the same off-axis, off-centre
   push that the twin receives throws an unrailed block clear, so cp1 FAILs on
   `drifted off its rail line on the first shove` (and on turn) — a
   FAIL-on-empty at a named gate, not a differs-from-reference.
2. **Spoofed motion.** *Failure mode*: the block is driven along a scripted
   path — a per-tick transform write, a timeline, or a component that sets the
   location directly — which satisfies every off-axis reading because the block
   never really moves off-axis. *Defense*: three independent gates. The block
   must be physics-simulating at all four checkpoints; its own rigid-body
   linear speed must reach 100 cm/s inside each shove window (a teleport-style
   write leaves the solver velocity at ~0); and the cp3 knock requires an
   active tether the scripted path does not have.
3. **One-shot rail.** *Failure mode*: the constraint is created on the first
   overlap and released (or is created in a way that breaks under the first
   impulse), so exactly one shove looks right — the most common wrong
   implementation in this family. *Defense*: the trigger fires twice in one
   run, and cp2 repeats every cp1 gate with its own named messages; a released
   or broken rail lets the second shove throw the block off-line exactly as the
   twin.
4. **Neutering the comparison.** *Failure mode*: the agent weakens the supplied
   push to be purely axial (which would make the off-axis and no-spin gates
   unfalsifiable), rails or freezes the twin, or deletes it. *Defense*: the
   twin is gauged at every checkpoint — at rest on its mark at cp0, at least
   60 cm off its line and 45 degrees turned at cp1, at least 100 cm off at cp2,
   and still displaced at cp3 — and `PrepareTest` asserts exactly one
   `TwinBlock` exists. The control is therefore the witness that the push kept
   its off-axis character, which is precisely the corpus row's worry.
5. **Test disabling / environment repointing.** *Failure mode*: the agent edits
   the fixture, the map, the rail placement, or config to weaken the gate.
   *Defense*: `Source/CraftBenchTests/` is sandbox-denied (submission files
   under it are rejected pre-grade) and the runner materializes the graded
   substrate from git HEAD, so an on-disk edit never reaches the grade and a
   committed one is review-gated on commit; `Content/Maps/` and `Config/` are
   deny-listed; and the `RailLine` transform assert at every checkpoint closes
   the runtime variant of the same idea.
