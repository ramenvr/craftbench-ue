# t1-shoved-block-slides-on-one-rail — provenance and design decisions

## Imported from

`t1-joint-constrains-to-axis` in
an internal design note (not shipped) (Hardening Status: **ALREADY
STRONG**; 6-check rubric, PASS = 6/6). Reviewed as §1 row 15 of
an internal design note (not shipped)
(`ADOPT+FIX · hardfail · leak · id-leak · cpp · family F-G`) and costed at
**MED, 7 h** in an internal design note (not shipped)
(line 903; family C / F-G, "Rigid-body bench: sample transform/velocity,
matched control body"). The row does **not** appear in
`verification-contracts.csv` — only its two sibling constraint rows
(`t1-constraint-limit-caps-swing`, `t1-runtime-constraint-follows`) do, so there
is no per-check contract to transcribe and the Verifier specification here is
authored from the rubric plus the §1 Expect/Control/Do/Sinks-it lines.

## What the owner said

an internal working note (not shipped) → `cand/1:t1-joint-constrains-to-axis`:
`"answer": "agree"`, `"note": ""` — approved as reviewed, with no note. (The
adjacent hold on the *sibling* row `t1-constraint-limit-caps-swing` — "For 70
and 71, how to verify and this seems hard to evaluate. I can be convinced with
aura-generated level that demonstrate this" — is that row's, not this one's, but
it is the same skepticism this design answers by making every gate a measured
transform in a staged, photographable scene.)

## What changed from the corpus row, and why

- **Renamed** `t1-joint-constrains-to-axis` → `t1-shoved-block-slides-on-one-rail`.
  `joint` named the mechanism in a path the agent can see
  (`Content/Tasks/<id>/`, `Content/Maps/<id>/`), which is the `id-leak` finding.
  The new id names the observable.
- **The impulse is partly OFF-AXIS, and that is the whole hardening.** The
  corpus row's checks 2/3/5/6 (off-axis translation locks, angular limits,
  off-axis confinement, rotation confinement) are *unfalsifiable at runtime*
  under a purely axial push: a block with no rail at all, or one that simply
  never moves, satisfies them. The push here is ~5:2:1 along-rail : off-rail :
  up and lands off-centre, so every one of those checks is a live gate. This is
  the `Sinks it` line, addressed structurally rather than by prose.
- **The control twin is the push's witness.** The un-railed twin receives the
  identical impulse in the identical frame and must end up at least 60 cm off
  its line and 45 degrees turned (cp1), 100 cm off (cp2). That is not decoration:
  the plunger lives in the *agent-writable* module, so "weaken the push until
  the off-axis gates go vacuous" is a real route — and the twin gates close it,
  because a purely axial push leaves the twin on its line and FAILs. The corpus
  row had no control leg at all.
- **The rail does not run along a world axis** (30 degrees off world X). The
  corpus row said only "the declared translation axis". A world-axis rail makes
  "lock world Y and Z" accidentally correct and de-concepts the task to two
  property writes; a 30-degree rail forces the constraint frame to come from the
  block's own (or the rail's own) orientation. The angle **is disclosed in the
  prompt**, because a headless agent cannot open the map to measure it and an
  undiscoverable scene fact would be a false FAIL, not a difficulty.
- **Checks 1/2/3 are graded as runtime behavior, not static inspection.** The
  corpus row scored "binds the exact bodies", "translation axes configured" and
  "angular limits configured" by static inspection of the generated constraint.
  Deliverable here is C++ that builds the constraint at runtime, so there is no
  asset to introspect (no L2I) and — more importantly — a static property read
  would bless one recipe and false-FAIL a legitimate alternative (constrain to
  the rail actor vs. to the world; free vs. generously-limited along the rail).
  Every one of those three is subsumed by an observable: binding by "it tracks
  the line and re-tethers after a knock", the axis config by the off-axis and
  travel gates, the angular limits by the turn gate.
- **Added the walk-in trigger, twice.** The corpus row had a bare "verifier
  impulse". Per the owner's bar the trigger is the character walking into the
  plunger, driven in the fixture by the shipping per-frame `AddMovementInput`
  timeline (same pattern as
  `Tasks/t1-overlap-teleport-portal/TeleportPortalFunctionalTest.cpp:194` and
  `Tasks/t2-ladder-climb-volume/LadderClimbFunctionalTest.cpp:246`) and by a
  human with WASD on the same possessed pawn. The plunger re-arms on
  end-overlap so the fixture can walk out and back in; cp2 repeats every cp1
  gate, which is what catches the one-shot latch.
- **Added the cp3 knock (tether) leg**, which the corpus row did not have (its
  sibling `t1-constraint-limit-caps-swing` had a tether bound, under gravity).
  It exists for one specific reason: a hand-rolled per-tick clamp that zeroes
  off-axis and angular velocity passes every slide gate. Only a leg that
  requires the block to come *back* to a line it was displaced from separates a
  real tether from a clamp. The requirement is disclosed in the prompt so this
  grades a stated behavior.
- **Pre-impulse rest is a SCORING gate, not a setup gate.** The corpus row made
  it explicitly "non-scoring". The owner's bar #3 requires the *before* state to
  be photographable, so cp0 asserts both blocks at rest on their marks and
  unrotated, and a continuous per-frame guard FAILs any block that moves while
  the hero is still more than 250 cm from the plunger (a BeginPlay or timer
  shove).
- **`deliverable_root:` is NOT in the front matter.** It is not in
  `tools/verify-single/spec.py::_KNOWN_KEYS`, and `_spec_from_front_matter`
  raises `ValueError: unknown front matter key(s) ... deliverable_root` — i.e.
  exit 2 "spec malformed", never a graded FAIL, but the task would not run at
  all. Verified by parsing this exact block with and without the key. Per the
  batch convention the root is instead stated as the first line of
  `## Workspace state pre-task` **and** in the prompt body.
- **The control-twin convention's local pawn spawner does not arise here.** The
  batch convention anticipates duplicating a spawner because
  `ACraftBenchPawnFunctionalTest::SpawnAndPossessPawn()` handles exactly one
  pawn. In this task neither subject is a pawn: subject and control are both
  placed blocks, and the single pawn comes from the map's game mode (the
  `t2-ladder-climb-volume` pattern). The fixture therefore derives from
  `ACraftBenchFunctionalTest`, and **no base class is touched and nothing is
  duplicated**. Said out loud in `## Verifier specification` so the implementor
  does not hunt for a helper.
- **Capability bucket** is `Architecture & Systems`, taken from the
  `physics-constraints` row of `tools/coverage/concepts.csv` (weight_tier
  `high`, `in_scope yes`) rather than the "Gameplay Programming" a physics
  gameplay task reads like — the template files a task under the bucket of its
  primary concept.

## Scheduling note — this task needs its OWN map

`ADOPTION-REVIEW-2026-08-16.md` costed family F-G on **sharing one map** with
`t1-runtime-constraint-follows`, which is a §2 row and is **not in this batch**.
So the ≈89 h wave figure does not include this map: the ~7 h estimate here must
be read as *plus a standalone map build*, and F-G's first-in-family premium is
paid by this row alone. Nothing else in this batch stages a rail bench, so there
is no sibling to split it with.

## What still needs building

1. ~~**BLOCKER — the map basename collides with the rest of this batch**~~ —
   **misattributed, and CLOSED. Corrected 2026-08-17.** The mechanism described
   below is real, but it never applied to *this* row: measured across every
   `fixtures:` entry in `tasks/`, this task's original basename
   `L_ConstraintBench` was declared by **this spec alone**. The real
   duplicate-basename groups in the batch were `L_ContactLane` (×3 — door, pad,
   spikes), `L_NavYard` (×3 — sight, patrol, nav-walk), `L_RenderLane` (×2) and
   `L_CollectArena` (×2); all four groups were resolved by rename the same day, and
   the rule now lives in `tasks/README.md` so the next author does
   not have to rediscover it. This row's rename to `L_RailBench` was done for
   item 2's reason (the mechanism leak) and is a no-op against the collision
   mechanism. **The mechanism, kept because it is the thing to check for the next
   map:** `tools/verify-single/map_locator.py::locate_map` gathers
   `Content/Maps/<map>.umap` **plus every `Content/Maps/*/<map>.umap`** and
   raises `DuplicateMapBasenameError` on two or more candidates — routed to
   **HARNESS-ERROR (exit 7)**, deliberately never to a graded FAIL. The rule was
   tightened to this on 2026-08-08 precisely so a task can never be graded
   against a map chosen by a tie-break. Consequence: the moment a second task in
   this set commits an `L_RailBench.umap`, **every L2 leg of every task
   sharing that basename stops running** — including this one, and including
   `cb refgate`. `cb lint`'s `_check_map` will NOT catch it: it matches the
   basename anywhere under `<substrate>/Content/`, so a sibling's map even makes
   a missing map here look green. **The standing rule**: give each task a unique
   basename while keeping the shared staging *shape*; the per-task folder is not
   enough.
2. **Leak fixed by the rename (2026-08-17).** The original name
   `L_ConstraintBench` put `Constraint` into an agent-visible path, which
   is the same `id-leak` finding that got `joint` removed from the id. Concrete,
   because **`## Workspace state pre-task` is shown to the agent** —
   `tools/run-agent/prompt_extract.py::ALLOWED_SECTIONS` is
   `('Prompt given to the agent', 'Workspace state pre-task')`, not the prompt
   alone — so the map path is literally in the agent's context, and it is the
   ONLY occurrence of the word in everything the agent sees (measured). That
   same fact is why the workspace section here names no engine constraint type,
   says "nothing that holds the block to its rail ships" instead of naming a
   component, and states only that no `.Build.cs` edit is needed rather than
   which stock actor already compiles the joint types (that detail lives in this
   file instead). The rename to `L_RailBench` closes the last of it — "rail" is a
   word the prompt itself uses about the observable, not an engine type.
3. **The map** `L_RailBench.umap` (committed binary — the only map source;
   a missing binary is an explicit L2 FAIL and a `cb lint` error): floor with
   200 cm stripes perpendicular to the rail; 2,400 cm painted rail at 30 degrees
   off world X; `ARailBlockActor` on the rail and `ATwinBlockActor` 300 cm to
   its side, both square with the rail, both in one frame; `APlungerActor`
   400 cm behind the pair on the rail bearing; PlayerStart ~900 cm further back,
   off the world origin, facing the plunger; a landmark pillar at each end of
   the backdrop; world settings selecting `ABenchGameMode`; the placed fixture.
   Commit it — the graded substrate is cloned from git HEAD.
4. **`cameras.json` (the camera-plan lane; not part of this release)** at authoring time (checklist step 5), framing subject +
   twin + plunger + at least four stripes. Presentation-only, non-gating.
5. **The scaffold** under `Source/ThirdPerson/Tasks/t1-shoved-block-slides-on-one-rail/`:
   `BenchBlockActor` (all the physics setup, so the twins are identical by
   construction), `RailBlockActor` / `TwinBlockActor` (tag only),
   `PlungerActor` (**fully implemented**: off-centre 5:2:1 impulse to both
   tagged bodies, re-arm on end-overlap, one calib log line per shove),
   `RailActor`, `BenchCharacter` (mannequin mesh + ABP from the read-only
   `/Game/Characters/` pool — a meshless pawn grades clean and is invisible to a
   reviewer), `BenchGameMode`.
6. **The fixture** `Source/CraftBenchTests/Tasks/t1-shoved-block-slides-on-one-rail/ShovedBlockRailFunctionalTest.{h,cpp}`.
   Derive from `ACraftBenchFunctionalTest`; do not modify either base class
   (they are owned by the other machine). ASCII-only FAIL text, one unique
   literal per gate.
7. **The reference solution** at `reference/Source/ThirdPerson/Tasks/<id>/RailBlockActor.{h,cpp}`,
   then `cb refgate craftbench-public/t1-shoved-block-slides-on-one-rail` must
   grade it PASS. Deliberately NOT authored here (spec-only pass).
8. **Discrimination variants + `discrimination/MATRIX.md`** with the `##
   Requirements table` (the §7 soundness artifact `cb lint` looks for). The
   requirement→gate table in `## Verifier specification` is the seed. The
   variants worth hand-authoring, in value order: `clamp/` (per-tick zeroing of
   off-axis + angular velocity — must FAIL only at cp3), `latch/` (rail released
   after the first shove — must FAIL at cp2), `scripted/` (transform-write slide
   — must FAIL the simulate/own-velocity gates), `world-axis-lock/` (locks world
   Y and Z instead of the rail frame — must FAIL the off-rail gate),
   `axial-push/` (the supplied push weakened to purely axial — must FAIL the
   TWIN gates, which is the leg that proves the control is load-bearing).
9. **Calibration, in this order, from a reference run's `[t1-rail calib]`
   lines** — every number in the prompt is disclosed, so each one must be
   confirmed rather than assumed:
   - the impulse magnitude, so a *railed* block travels comfortably past 200 cm
     per shove (target ~350-500 cm) and the *twin* clears 60/100 cm off-line and
     45 degrees;
   - the walk distances and the checkpoint instants (0.7 / 4.5 / 8.5 / 10.1),
     against measured contact times — the fixture measures the shove instants
     from the twin's motion, so the schedule only needs enough margin;
   - **the cp3 tether tolerances are the one genuine risk.** Chaos joint
     projection recovering a 60 cm / 40 cm teleport in 1.6 s is *predicted, not
     proven* in this repo. If the reference does not recover inside 10 cm,
     widen the tolerance or shrink the knock — **do not delete the leg**, it is
     the only thing separating a real tether from a per-tick clamp;
   - the 10-degree turn tolerance on the railed block: locked swing/twist is
     stiff but not rigid under a big off-centre impulse; raise it toward the
     twin's 45-degree floor only as far as the measured reference needs, and
     record the measured value here.
10. **Known set-level gap (not this task's to fix)**:
    the corpus-ledger tool (since removed) iterates `("cpp", "bp", "python")`
    literally, so every `craftbench-public` task is silently omitted from the
    generated review page. Documented in `tasks/README.md`.

## Building it — what the physics and the harness actually cost (2026-08-17)

The reference is ~35 lines. Getting to it took eleven measured runs, and none of the
five decisions below could have been reasoned out from the spec. They are recorded
because every one of them is the kind of thing that silently produces either a
flaky task or a green-but-meaningless one.

### The one that made the task read green while grading nothing

`ACraftBenchFunctionalTest::Tick` ends with:

```cpp
if (Checkpoints.Num() > 0 && NextCheckpointIndex >= Checkpoints.Num())
{
    FinishTest(EFunctionalTestResult::Succeeded, TEXT("All checkpoints sampled."));
}
```

The base declares SUCCESS the moment the last scheduled instant is crossed. This
fixture, as the spec requires, treats the schedule as the EARLIEST instant each
checkpoint may be graded and defers the rest off measured events -- so cp3, clocked
1.6 s after a knock that only happens when cp2 grades, landed past the last
scheduled instant (10.1) and **never ran at all**.

Measured: the reference and the `one-shot-rail` variant both reported
`Result={Success}` with **no `cp3` line in either log**. The tether leg -- the
"hidden invariant" the whole task is built around, and the only thing separating a
real constraint from a per-frame velocity edit -- was unreachable while reading
green. `cb discriminate` reported `one-shot-rail PASS(unexpected-pass)`, which is
the only reason it was caught: a variant that should have failed passing is a much
louder signal than a reference that should have passed passing.

Fix: a fifth SENTINEL instant at t=20 far past any real grade, so the base's
auto-success is never reached, plus a named `RailRunCompletes` FAIL if the machine
has not finished by then. An unfinished deferred grade now fails loudly instead of
inheriting a pass.

**Generalises to any fixture that defers grading off a measured event.** If the
last thing you grade is not clocked by a scheduled checkpoint, the base will finish
the test out from under you.

### Four physics decisions, each found by measurement

1. **The joint anchors to the WORLD, not to the rail's static body.** Both look
   equivalent -- the rail never moves either way. Anchored to the rail primitive the
   joint degraded as the block travelled away from where it was defined: first shove
   held the line to 0.01 cm, second shove (starting 496 cm along) was torn 16.6 cm
   off it and lost a third of its travel. Against the world: 0.00 cm on both.
2. **Both blocks are held 4 cm clear of the floor.** A block resting exactly on the
   floor with its height locked fights the floor contact -- the solver resolves the
   interpenetration with a large normal force and friction follows it -- and a
   600 cm/s shove arrived at **31.7 cm/s**. The air gap in the map is not cosmetic.
   The twin simply settles it at play start, which the prompt's "settling at play
   start is fine" covers and cp0's 10 cm allows.
3. **The stripes leave a 120 cm corridor down the rail.** A stripe crossing the rail
   is a 3 cm obstacle in the slide. With continuous stripes the block scraped every
   one, and **a bigger shove travelled LESS** (35 cm against 170 cm) -- that
   non-monotonicity is the tell, and it is what pointed at the stripes rather than
   at the constraint.
4. **The shove is a FORCE over 0.15 s, not a one-frame impulse.** As an impulse the
   identical push landed differently depending on the block's state (311 cm/s one
   time, 610 cm/s the next) and the harder one tore a constrained block 20 cm off
   its line. Spread over nine frames both shoves deliver the same speed. A plunger
   shoving something is a push over time anyway.

Also: the blocks carry linear/angular damping so a shove SETTLES. With none they
accumulated -- measured 3,502 cm and still moving at 805 cm/s, which reads on screen
as a block sliding away for ever.

### Two measurement bugs in the fixture itself

- **The twin's TURN is graded as the window maximum, not the value at the sample.**
  `FQuat::AngularDistance` returns the shortest angle in [0,180], so a block that
  tumbles through several revolutions finishes reading an arbitrary angle -- the
  same twin read 158 deg on one layout and 15 deg on another purely from where the
  tumble stopped. Displacement stays at the sample, because displacement does not
  wrap.
- **The map's own authoring assertion caught the level being built on its side.**
  `unreal.Rotator`'s positional order is `(roll, pitch, yaw)`, so `Rotator(0, 30, 0)`
  is a 30 degree PITCH. The rail, both blocks, the plunger, every stripe and the sun
  were laid over that way on the first run, and the only thing that noticed was the
  script's "the placed rail's forward axis must equal the authored bearing" check.
  Every Rotator in the script is now keyword-built.

### One spec claim that did not survive contact

The spec's hidden-invariant #3 says a per-frame clamp that "zeroes the off-axis and
angular velocity every frame satisfies every cp1/cp2 gate". **It does not.** A
velocity-only clamp measured `dz` 12.4 cm and `turn` 48 deg at cp1, against
allowances of 10 and 10 -- the block still moves and rotates within the frame before
the clamp runs, so it fails cp1 on height and turn without ever reaching the tether
leg. To be the cheat the spec describes, the variant has to correct the POSE as well
while it is sliding; `discrimination/velocity-clamp/` does that, and only then does
cp3 become the one thing standing between it and a pass. The claim was written from
reasoning; this is what it measures.

### Two gates that were not gates, found by variants passing

Both were caught by `cb discriminate` reporting `PASS(unexpected-pass)` on a leg
that should have failed. Neither would have been visible from the reference, which
passed throughout.

- **The peak-speed floor is satisfiable by residual.** "Its own physics velocity is
  what carries it" was graded as `max speed >= 100 cm/s` inside each shove window.
  The plunger's real push gives even a scripted block a brief real velocity, so a
  `spoofed-motion` leg that zeroed the velocity every frame and wrote the position
  along the rail still recorded 131 cm/s and PASSED the whole task. The fix is a
  second gate per shove, `RailMotionIsPhysicsFirstShove` / `...SecondShove`, that
  compares distance actually covered per frame against the velocity the solver
  reports and fails when the two disagree by more than 120 cm/s. That is the same
  sentence in the prompt, read properly. The knock frame is excluded by clearing
  the previous-location baseline when the fixture teleports the blocks.
- **The tether leg needed a variant that could reach it.** See below.

### The velocity-clamp variant took three shapes before it was one

Its job is to prove cp3 is load-bearing: pass everything a shove can be judged on,
then fail only on being carried back. Two threshold-based shapes could not do it,
and the reason generalises:

1. Correct while |along-rail speed| > 30 → the correction re-engaged on the ~280 cm/s
   of the knock's own fall, so the cheat snapped itself back onto the line and
   PASSED cp3.
2. Correct while |along-rail speed| > 200 (then > 400) → the opening frames of each
   shove went uncorrected, and because every per-shove gate is a WINDOW MAXIMUM that
   error is recorded permanently: `dzmax` 10.5 cm and `turnmax` 38.6 deg, so it
   failed cp1 and never reached the leg it was written for.

Any threshold low enough to cover the first frame of a shove is low enough to fire
on the knock. The shape that works has no threshold at all: **a real one-axis joint,
re-anchored at the block's current pose every frame.** It prevents the block from
acquiring off-axis or angular motion — cp1 and cp2 read 0.00 / 0.00 / 0.00, byte-for-byte
what the reference reads — and it forgets the line it was defined against every
frame, so after the knock it re-anchors at 60 cm off and 40 cm up and stays there.

That is also the cleanest statement of what this task actually grades: the
difference between PREVENTING a body from leaving a line and HOLDING it to one.
