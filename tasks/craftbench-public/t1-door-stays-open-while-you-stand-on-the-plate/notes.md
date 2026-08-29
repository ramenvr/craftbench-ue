# t1-door-stays-open-while-you-stand-on-the-plate — provenance and design decisions

## Imported from

`t1-plate-opens-door-while-occupied` in
an internal design note (not shipped) — status `HARDENED`,
5-check fixed-N rubric (`PASS = 5/5`), review row 128.

Corpus text, verbatim:

- **What the Task Is**: "Make the supplied pressure plate hold the door at the
  closed transform with no player, open only while the supplied player occupies
  it, remain stable at each endpoint, close after exit, and perform the same
  full cycle again."
- **Prerequisite / Provided Setup**: "PL1 · Focused occupancy-state task —
  Supplied plate/door with writable occupancy-to-door surface; player,
  occupancy schedule and door-transform probe are read-only. Fixture supplies
  endpoint transforms, transition and stability tolerances and repeat route."
- **Rubric**: 1 `DoorClosedWithoutOccupancy`, 2 `DoorReachesOpenTransform`,
  3 `DoorHoldsOpenThroughoutOccupancy`, 4 `DoorReturnsToClosedTransform`,
  5 `DoorTransitionsContinuously`.
- **Verification Method**: "The existing occupancy driver and door-transform
  probe independently score the public no-occupancy closed state, exact open
  endpoint, occupied-state hold, return to the closed endpoint and continuous
  reversible motion. The later repeat cycle and repeated endpoint samples
  corroborate those same five properties and add no points."

Companion rows: `check-contracts.csv` carries all five checks (`Proposed
source_layer: L2`, `Manifest status: NOT CREATED`, `Runtime binding: UNBOUND`,
`Rubric visibility: HIDDEN from measured model`, `Windows discrimination: NOT
RUN`). The id does **not** appear in `verification-contracts.csv`, so there is
no per-check contract row to reconcile — the CSV detail above plus the batch
brief is the whole source.

## What the owner said

an internal working note (not shipped) →
`cand/1:t1-plate-opens-door-while-occupied`:

```json
{ "answer": "agree", "note": "", "row_id": "t1-plate-opens-door-while-occupied", "section": "1" }
```

No verbatim note — the owner agreed with the review's own §1 row 8 lines in
an internal design note (not shipped), which are therefore the
binding brief:

- **Expect**: "Manny steps onto the plate and the door swings open and stays
  open while he stands there; he steps off and it shuts; he steps back on and
  it opens again. The grade proves the door tracks occupancy instead of firing
  once, so a one-shot latch that leaves the door hanging open fails the shut
  leg."
- **Control**: "A second identical plate+door 3 m away that nobody ever steps
  on, its door inside closed tolerance at every checkpoint."
- **Do**: "build; add the untouched second plate+door 3 m away; state the
  open-transform delta and the per-sample step tolerance as numbers in the
  prompt; predicate check 1 (door closed while unoccupied) on the authored
  mechanism existing rather than deleting it — it is free to an empty
  submission, but it is also the only SCORED defence against opening
  everything at BeginPlay."
- **Sinks it**: "The open-transform delta and the per-sample step tolerance
  are undisclosed literals, so a correct door that swings a different distance
  or eases at a different rate FAILs on numbers the agent was never told."

## What changed from the corpus row, and why

- **Both undisclosed literals are now IN THE PROMPT** — the row's whole
  "Sinks it". Open delta = 90 degrees from the authored shut pose (graded band
  >= 80 open / <= 10 shut); step tolerance = 720 degrees per second and
  3000 cm per second. Also disclosed: the 2-second open and shut budgets, the
  300 cm pair separation, the 10-degree repeat agreement, and the fact that
  the times are wall-clock and must hold at any frame rate.
- **The step tolerance is expressed as a RATE, not per frame.** The proven
  calibration is `gp-door-hitch-fix-bp`'s (a smooth 90 deg / 1.5 s swing moves
  ~1 deg per tick at 60 fps, cubic peaks under 3; the snap it hunts jumps
  40-90 deg in one tick, and 12 deg/tick separates the families with ~4x
  margin both ways). 12 deg/tick at 60 fps = 720 deg/s. Stating the rate means
  the disclosed number means the SAME thing on the 20 fps leg — a per-frame
  literal would silently triple the allowance there.
- **`fps_legs: [60, 20]` added** (not in the corpus row). The trigger is
  spatial, but the SWING is time-driven, so a frame-counted swing is a live
  wrong implementation; at 20 fps a 90-tick swing takes 4.5 s and blows the
  disclosed 2-second budget. The legs are honoured straight from the spec
  (`layers/registry.py:196` prefers `TaskSpec.fps_legs`), so no runner edit is
  needed — the playbook's "hardcoded `_DT_LEGS_BY_TASK`" caveat is stale
  (`run_task.py:193` is now an empty dict).
- **Check 1 became a fail-only PRECONDITION, not a deleted check and not a
  credited one.** cp0 asserts both doors shut before anyone has stood on
  anything, which can only sink a submission (an open-at-play delivery), never
  bank credit — the empty submission still dies at cp1. This is the owner's
  "predicate it on the authored mechanism existing rather than deleting it",
  implemented as "the verdict also requires the full open/shut cycle".
- **Control twin added and gauged at all 7 checkpoints** — a second identical
  plate-and-door pair 300 cm away whose door must stay within 10 degrees of
  shut, plus a staging assertion that the character never came within 200 cm
  of the control plate. It also creates a requirement the corpus row had no
  gate for at all: a plate addresses only its OWN door. That pairing is
  supplied (each placed plate's `LinkedDoor`), so it is a behaviour
  requirement, not a puzzle.
- **The corpus's "exact supplied open transform" was relaxed to a band.** An
  exact-equality endpoint on a rotation is the classic false-FAIL on
  correct-but-conservative work; >= 80 / <= 10 degrees around a disclosed
  90-degree delta is the same observable with a stated tolerance.
- **A repeat-agreement gate was added** (second open within 10 degrees of the
  run's own FIRST measured open angle). The corpus said the repeat cycle
  "corroborates and adds no points"; the owner's bar #5 says the second firing
  must produce the same MEASURED outcome, and self-referencing the first
  measurement means widening the absolute band never widens this one.
- **Occupancy is judged geometrically by the fixture**, from the character's
  own measured 2D distance to the plate centre plus a not-falling guard —
  never from submission-owned state and never through a component the
  submission could disable. Both halves of a check must not be
  submission-owned (the `t1-onscreen-tally` lesson in the same feedback
  section).
- **Trigger is walking in, twice, with no key presses** — the fixture drives
  the game-mode-spawned mannequin with the shipping per-frame
  `AddMovementInput` timeline, the same idiom a human reproduces with WASD.
- **`deliverable_root:` was REJECTED by the parser** and is therefore stated
  as the first line of `## Workspace state pre-task` and again in the prompt
  body, per `tasks/README.md`'s mandatory mitigation.
  Measured, not assumed: adding the key raises
  `ValueError: unknown front matter key(s) ... deliverable_root (allowed:
  action_budget, allow_redirectors, capability_bucket, category, config_allow,
  deadline_s, fixtures, fps_legs, id, introspect, layers, randomization, set,
  substrate, tier)`, i.e. exit 2 "spec malformed" on every parse.
- **Concept id: `collision-overview`, not `ps-collision-overlap`.** The three
  shipped overlap tasks (`cpp/t1-overlap-teleport-portal`,
  `cpp/t1-overlap-logs-once`, `cpp/t1-extraction-volume-per-actor-trigger`)
  all cite `ps-collision-overlap`, which **does not exist in
  `tools/coverage/concepts.csv`** — nothing validates concept ids, so the
  phantom has propagated three times. Flagged here rather than cloned;
  `collision-overview` is the real in-scope row (Gameplay Programming, weight
  `high`).
- **On-screen readouts are scaffold-owned and ungraded**: a floating angle
  readout above each door panel (derived from the panel's measured pose, so it
  cannot disagree with the gate) and a lamp on each plate lit while a body is
  inside its own volume. Deliberate trade, recorded so nobody "fixes" it: the
  lamp's per-frame volume query reveals that occupancy is queryable, which is a
  route hint, not an answer (bar #6 — grade the outcome, warn on the route),
  and the alternative is a run with no on-screen occupancy readout at all,
  which bar #1 forbids. Neither readout is asserted on, so removing one costs
  the reviewer and not the grade.
- **Map basename is UNIQUE repo-wide, and it has to be.** This spec originally
  declared `L_ContactLane`, a name two sibling specs in this batch also declared.
  That was a **blocker, not a design choice**: `map_locator._map_candidates` globs
  `Content/Maps/<map>.umap` *and* `Content/Maps/*/<map>.umap`, and `locate_map`
  raises `DuplicateMapBasenameError` on two or more candidates → **exit 7
  HARNESS-ERROR for every submission of every task sharing the name**. Per-task
  folders do not isolate the basename, and `cb lint` cannot see it
  (`tasklint._check_map` returns clean once any tracked copy exists). Renamed to
  `L_PlateDoorLane` 2026-08-17; the siblings took `L_PadLane` and `L_SpikeLane`.
  `Content/Maps/t1-door-stays-open-while-you-stand-on-the-plate/L_PlateDoorLane.umap`
  is this task's own copy under its own per-task folder. The automation name
  resolves as
  `Project.Functional Tests.Maps.<task-id>.L_PlateDoorLane.PlateDoorFunctionalTest`
  (the runner's `map_locator` derives the foldered prefix, and UE strips the
  `A`).
- **No second-pawn spawner and no base-class change.** The control here is a
  placed pair, not a body, so the fixture derives from
  `ACraftBenchFunctionalTest` and needs nothing the base does not already
  give. `CraftBenchFunctionalTest.h` / `CraftBenchPawnFunctionalTest.h` are
  owned by the other machine and are not touched; the spec says so explicitly
  so the implementor does not hunt for a shared second-subject helper.
- **Tier stays T1** (single concept, 40-70 LOC, 0.75-1.5 senior-dev hours).
  The corpus's PL1 framing agrees.

## What still needs building

> **STATUS 2026-08-17 — ALL BUILT.** Every numbered item below is done and is
> kept as the authoring record of what was asked for, not as an open list.
> Scaffold, map, fixture, `cameras.json` (the camera-plan lane; not part of this release) (pixel-validated, not just authored),
> reference and the six-leg discrimination package are committed;
> `cb discriminate` is YES 6/6 with each leg at its own named gate, and
> `cb refgate` grades the committed reference **PASS** on both framerate legs.
> The certificate itself is withheld for a reason outside this task: the cert key
> covers `tools/verify-single`, which carries another workstream's uncommitted
> changes, so refgate reports "PASS not certified -- uncommitted changes under
> the task/substrate" and will re-run. Item 7 below is FIXED (`the corpus-ledger tool.py`
> now reads the basket list off disk, so this set reaches the generated review
> page at all -- it is 2 tasks today and every one added later, NOT the "18"
> an earlier note claimed; that number came from counting every id beginning
> `t1-` across all four sets).

Verifier-owned (`/craftbench-build-verifier`), none of it authored here:

1. **Scaffold, `Source/ThirdPerson/Tasks/t1-door-stays-open-while-you-stand-on-the-plate/`**
   — `ContactPlateActor.{h,cpp}` (200x200 pad + query-only 200x200x60 volume,
   overlap events on, lamp readout, instance-editable `LinkedDoor`, ctor tag
   `ContactPlate`, no behaviour); `SwingDoorActor.{h,cpp}` (hinge root +
   offset `DoorPanel` mesh clear of the lane + floating angle readout, ctor tag
   `SwingDoor`, no motion); `PlateHeroCharacter.{h,cpp}` (concrete
   `AThirdPersonCharacter` subclass, mannequin mesh + anim blueprint from the
   read-only `/Game/Characters/Mannequins/` pool — the stock template assigns
   the mesh in its Blueprint, NOT in C++, so a plain C++ subclass is invisible
   unless the ctor loads it; ctor tag `PlateHero`);
   `PlateDoorGameMode.{h,cpp}` (`DefaultPawnClass`).
2. **Map**, `Content/Maps/t1-door-stays-open-while-you-stand-on-the-plate/L_PlateDoorLane.umap`
   — committed binary, the showroom staging in the spec: 3000x1600 floor,
   200 cm stripes, PlayerStart at ~(-600,-150) facing +X, graded pair at
   (0,-150)/(300,-150) tagged `GradedPlate`/`GradedDoor` with `LinkedDoor`
   wired, control pair at (0,+150)/(300,+150) tagged
   `ControlPlate`/`ControlDoor` with `LinkedDoor` wired, two distinct end
   landmarks, world settings selecting `APlateDoorGameMode`, one placed
   fixture. The per-instance tags and the two `LinkedDoor` references are
   MAP data — the level is deny-listed, so they cannot be tampered with, and
   they cannot be omitted without making the task unsolvable.
3. **Fixture**, `Source/CraftBenchTests/Tasks/t1-door-stays-open-while-you-stand-on-the-plate/PlateDoorFunctionalTest.{h,cpp}`
   — `APlateDoorFunctionalTest : ACraftBenchFunctionalTest` exactly as the
   spec's pseudo-code: tag resolve, closed-pose capture per static-mesh
   component, `SetCheckpointSchedule({0.8, 4.8, 6.4, 9.4, 13.1, 14.7, 17.7})`,
   the phase-driven per-frame walk drive, the per-tick continuity guard
   (`Super::Tick` first), the 7-of-7 control gauge, and one distinct
   `FinishTest(Failed, ...)` literal per gate carrying the credited substrings.
4. **`cameras.json`** beside the spec — one wide shot holding both pairs and
   >= 4 stripes for cp0/cp3/cp6, plus a `frame_subject` mid-shot on the graded
   door for the open checkpoints; presentation only.
5. **Reference solution**, `reference/Source/ThirdPerson/Tasks/<id>/...`, then
   `cb refgate craftbench-public/t1-door-stays-open-while-you-stand-on-the-plate`
   PASS on BOTH framerate legs. Re-confirm the seven instants and the settle
   distance from the reference run's `[t1-plate-door calib]` lines before
   pinning them — especially the 20 fps leg's arrival time.
6. **Discrimination package** — `discrimination/MATRIX.md` (the requirements
   table in the spec is the source), plus variants only for holes that table
   finds. The obvious candidates to prove rather than argue: `always-open/`
   (dies at cp0), `latch-once/` (dies at cp3), `snap-open/` (dies on the
   continuity guard), `broadcast-all-doors/` (dies on the control gauge).
7. **Known set-level gap** (not this task's to fix):
   the corpus-ledger tool (since removed) iterates the three basket names
   literally, so every `craftbench-public` task is silently omitted from the
   generated review page until `"craftbench-public"` joins that tuple.

`tasklint` state of this spec when it was written: 2 errors + 1 warning, all
three being exactly the artifacts above — `fixture-source-exists`,
`map-binary-exists`, `reference-solution`. No format, section-order, H2,
category, anti-gaming-count or prompt-jargon finding. **Now 0 errors**, since
those three artifacts exist and are committed.

## The play lane — found by trying to walk around it (2026-08-17)

The owner opened this level and the character would not move. It graded perfectly
at the time: L1 built, the reference L2 passed on both framerate legs, and all
five variants separated at their own gates. Nothing was wrong with the task; the
level simply could not be driven.

**Cause, both halves needed.** Naming `APlateDoorGameMode` in WorldSettings
replaces `GlobalDefaultGameMode` (`BP_ThirdPersonGameMode`), and both halves of
Enhanced Input live on the Blueprints it would otherwise have supplied:

- `AThirdPersonCharacter` declares `MoveAction`, `LookAction`, `MouseLookAction`
  and `JumpAction` as `UPROPERTY(EditAnywhere)` and assigns **none** of them —
  Epic fills them on `BP_ThirdPersonCharacter`'s class defaults, so
  `APlateHeroCharacter` inherited four nulls and `SetupPlayerInputComponent`
  bound nothing at all.
- `IMC_Default` lives in `DefaultMappingContexts` on
  `BP_ThirdPersonPlayerController`. The game mode set `DefaultPawnClass` but not
  `PlayerControllerClass`, so the player got a bare `APlayerController` that has
  no such property — no key mapped to any action even once the actions were set.

This is the same trap already recorded for the mannequin mesh in item 1 of the
build list above ("the stock template assigns the mesh in its Blueprint, NOT in
C++"). It applies to the INPUT wiring for exactly the same reason, and that half
was missed. `L_PadLane` is the control: it names no game mode, so it inherited
both halves and was playable from the first build.

**Why no gate could have caught it.** `APlateDoorFunctionalTest` drives the hero
with `AddMovementInput` and never presses a key — as does every other fixture in
the repo. A level with a dead keyboard therefore grades BYTE-IDENTICALLY to a
healthy one. Same shape as the black-stills incident: the automatic gate measured
the graded outcome correctly and said nothing about whether a person could reach
or perceive it.

**Fix**, both in this task's own folder (never Epic's `ThirdPersonCharacter.*` —
that is shared substrate and re-shas the project tree for every task at once):
`PlateDoorGameMode` now loads `BP_ThirdPersonPlayerController` into
`PlayerControllerClass`, and `PlateHeroCharacter` loads the four `IA_*` assets in
its constructor. No `Build.cs` change — `EnhancedInput` is already
public-transitive via the `ThirdPerson` module.

**Guard.** `DescribeBrokenPlayerInput` asserts both halves as a
`HARNESS-PRECONDITION`, reading by **property name** rather than class so a
subclassed or renamed pawn still answers, and needing no new module dependency.
Proved in both directions before being trusted, because a guard that cannot tell
broken from correct is not a guard:

- controller unset + `MoveAction` nulled on purpose → `HARNESS-PRECONDITION: the
  level cannot be played by hand -- the pawn (PlateHeroCharacter) has nothing
  bound to MoveAction; PlayerController carries no DefaultMappingContexts, ...`
- wired → precondition passes, grading proceeds to `DoorOpensWhileOccupied` on
  the inert scaffold, so the `empty` leg's named substring is unchanged.

**One imprecision in that message, recorded rather than churned.** The deliverable
root is `Source/ThirdPerson/`, which CONTAINS this task's scaffold — so an agent
*can* trip the precondition by deleting the shipped input-action assignments,
where the message's "fix the substrate, not the task" reads oddly. It is not a
scoring hole: a `EFunctionalTestResult::Error` surfaces as `Result={Fail}` and
`overall: fail` (measured), so breaking the input lane is never a way to dodge a
FAIL — and deleting shipped scaffold unrelated to the asked behaviour would not
have passed regardless. The wording was left alone deliberately: the fixture is in
the certificate key, so re-cutting it for a message would have invalidated the
discrimination run and the certificate taken from it.

**Set-level consequence.** Four other ThirdPerson maps were measured in this exact
state — `L_LadderClimb`, `L_NpcFollow`, `L_FireAnimation`, `L_TpSprint`, all in the
established set owned by the other machine. Left untouched on purpose (changing a
controller class shifts possession in fixtures that cannot be re-validated
cheaply from here). Table, recipe and the caveat about `CraftBenchTemplate` are in
the internal design note (not shipped); the requirement is now
step 4 of `docs/TASK-AUTHOR-GUIDE.md` and pitfall 8.
