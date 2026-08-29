---
id: t1-mud-wade-bp
substrate: ThirdPerson
set: bp
tier: T1
capability_bucket: Technical Art
category: animation
layers: [L1, L2, L2I]
fixtures: ["L_MudLane :: AMudWadeFunctionalTest"]
introspect: [t1_mud_wade_bp.py]
---

# t1-mud-wade-bp

The Blueprint leg of a surface pair. `cpp/t1-mud-wade-cpp`
is the other one. **Same map (`Content/Maps/L_MudLane.umap`), same fixture
(`AMudWadeFunctionalTest`), same checkpoint schedule, same named gates, same
tolerances** — the only difference is which surface the answer is written on,
which is what makes the pair a measurement of the surface rather than of two
designs. Nothing was re-tuned for this leg; a re-tuned gate would measure the
tuning.

## Provenance

The C++ leg was built first (2026-08-18) from the startup-eval corpus row
`t1-locomotion-idle-move-state`, reshaped because the owner's verdict on that row
was `fix-first` — idle/walk/idle is stock template behaviour on this substrate, so
it would have graded a template feature. A gait the template has no equivalent of
keeps everything the row was testing (a live read of which motion drives the pose,
driven by world state, with the supplied normal locomotion preserved) and grades
the agent's work instead. Full provenance in
`cpp/t1-mud-wade-cpp/notes.md`.

**Why the pair exists at all.** The benchmark's thesis is a (model x tool x SURFACE)
interaction, and the surface axis was carried by six `gp-` pairs alone: every task
whose graded actor is PLACED in the committed map was C++-only, because
`Content/Maps/` is deny-write to agents, so a Blueprint subclass would never be
instantiated. `ACraftBenchFunctionalTest` gained the surface lane on 2026-08-20 and
this leg cashes it for a task whose graded class is a PAWN placed twice. See
*Hidden invariants* for the mechanism, recorded there so the next reader does not
re-derive it.

## Primary concept

- `anim-state-machine` — State Machines
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/state-machines-in-unreal-engine)

The load-bearing capability is unchanged from the C++ leg: adding a
**gameplay-conditioned motion state** to a working locomotion setup — a second,
distinct motion that becomes the one driving the pose while a world condition
holds, releases cleanly when it stops holding, re-enters on a second occurrence,
and leaves the supplied normal locomotion untouched — authored **in Blueprint**.

## Composed concepts

- `ps-bp-overview` — Blueprints Visual Scripting Overview
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/blueprints-visual-scripting-in-unreal-engine)
- `movement-components` — writing the character's own walking speed rather than
  moving it by hand
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/movement-components-in-unreal-engine)

## Prompt given to the agent

> Deliver your solution **entirely as Blueprint assets** created in the editor and
> saved under `Content/Tasks/t1-mud-wade-bp/`: a Blueprint
> subclass of the figure the level already drives, carrying your work.
> **Do not add or modify any C++ source for this task.**
>
> The level is a marked lane on flat ground. Your figure starts on the lane and
> walks it end to end at its normal top speed of 500 units per second. Part-way
> along, 400 cm of the lane is a patch of dark, wet ground. That patch is a single
> thing in the level and it carries the tag `MudPatch`; it blocks nothing, so the
> figure walks straight onto and through it.
>
> Make the figure wade through it. While the figure is on that patch two things
> must be true, and both must become true within half a second of it stepping on:
> it travels at 40% of its normal top speed (200 units per second), and the motion
> driving its body is a visibly different one — the supplied heavy wade at
> `Content/Tasks/t1-mud-wade/A_MudWade`, genuinely driving
> the pose, not the ordinary walk played back slower. When the figure steps off the
> patch, the ordinary walk and the full 500 units per second must both be back
> within half a second. Walk onto the patch a second time and it must wade again,
> the same way.
>
> Nothing else may change. A second, identical figure patrols a parallel lane that
> has no mud on it; that one must keep the ordinary walk and its full speed for the
> whole run — it is never allowed to drop below **70%** of the speed the graded
> figure measures on clean ground, and the wade motion must never drive its pose.
> Both figures are the same class, so whatever you build reaches both. The graded
> figure's own clean-ground speed is itself checked against the 500 it is supposed
> to run at, with a **400-600 units per second** acceptance band, so a submission
> that changes the ordinary walk speed at all fails before any mud is touched.
> Correctness is judged from measured ground speed — on the patch it must read
> between 30% and 50% of the speed the same figure measures on clean ground, and
> off the patch between 85% and 115% — and from which motion is driving the pose,
> sampled at moments you are not told, on both crossings.
>
> The wade clip is supplied; assign it, do not author a new one. Your deliverable
> is Blueprint assets under
> `Content/Tasks/t1-mud-wade-bp/` and nothing else: do not
> edit the level, any config file, any C++ file, or any test file.

## Workspace state pre-task

**Deliverable root: `Content/Tasks/t1-mud-wade-bp/`** —
Blueprint assets only. No C++ file may be added or changed; the C++ that ships is
read-only reference material for what you can call. The `ThirdPerson` substrate's
other writable root (`Source/ThirdPerson/`) is closed for this task by the surface
contract above, and `Content/Maps/`, `Content/Characters/`, `Content/ThirdPerson/`
and `Source/CraftBenchTests/` are deny-listed — a submission file there is an
exit-4 sandbox reject, not a graded FAIL.

What the level already carries, all of it working:

- **The lane figure** — a C++ character class the agent extends. It arrives
  visibly represented (a mannequin skeletal mesh and the substrate's ordinary
  unarmed locomotion are both assigned on it), walks at a top speed of 500 units
  per second, follows its movement direction, and binds the template's keyboard
  movement lane so a human can drive it. It carries the tag `MudHero`. Readable
  and writable from a Blueprint on it: its walking speed, its movement component,
  its mesh, and a `Normal Top Speed` value of 500. **It has no mud logic of any
  kind** — it walks the patch at full speed with the ordinary walk still driving
  the pose.
- **Two instances of that one class.** One is spawned at the player start by the
  level's game mode and possessed by player 0; the other is placed in a parallel
  lane 600 cm clear of the mud, carrying an extra instance tag that marks it as
  the control. Both are the same class, so an edit reaches both — that is
  deliberate, and it is what the control gate measures.
- **The mud patch** — one placed actor tagged `MudPatch`: a dark, flat slab set
  into the floor with a query-only volume over it, 400 cm along the lane and
  400 cm across, generating overlap events and blocking nothing.
- **The supplied heavy wade** at
  `Content/Tasks/t1-mud-wade/A_MudWade` — a looping
  forward-locomotion clip on the same skeleton as the figure, visibly a different
  gait from the ordinary walk at a glance, and **nothing plays it**. It is not a
  retimed copy of the walk clip. Assign it; do not author a new one.
- **The lane itself** — a flat floor with stripe markings every 200 cm so speed
  and distance read by eye, a landmark pylon at each end of the backdrop, and
  lighting.

Nothing in the level decides that the figure should behave differently on the
patch. That is the whole task.

## Verifier specification

**Identical to the C++ leg, ported verbatim** — same map, same fixture
(`AMudWadeFunctionalTest`), same drive, same checkpoint schedule, same tolerances,
same gate names and same failure literals. Nothing is re-tuned for this surface.

**The fixture, not the C++ leg's spec prose, is the authority.** The C++ leg's
`## Verifier specification` still describes a superseded design (a verifier-owned
marker curve on the clip, five hand-placed checkpoints, a `MudTwin` tag, and an
L2I asset-structure leg that was dropped — its front matter reads `[L1, L2]` and
`mud_wade_gait.py` is not on disk). What shipped instead, and what both legs are
graded by:

- **Both figures are driven by the fixture** with per-frame movement input — the
  same path a human's WASD drives. The graded figure walks the lane past the
  patch, back, and past again (three crossings, two required); the control
  patrols its own clean lane so its speed is a real measurement rather than a
  still reading. Neither figure's speed is judged within 1.5 s of a turn, because
  a turn is a real slowdown the FIXTURE caused.
- **Speed is MEASURED ground speed** — distance actually covered per frame,
  smoothed — never the walking-speed setting. A submission that writes the number
  without the figure slowing down does not pass, and one that slows the figure by
  any legitimate means passes regardless of how.
- **The clean-ground reference is measured on THIS run**, averaged before the
  figure first touches the patch and only once it is up to speed, so every band
  below is a fraction of what this figure actually does. That average is
  separately checked against the disclosed 400-600 band, which is what catches a
  submission that slows the ordinary walk instead of adding a wade.
- **The pose question is answered by asking the MESH**, never the submission:
  `WadeDrivesPose` reads the mesh's single-node player's current asset and the
  active montage and accepts either, matching on the clip's name. A submission
  cannot answer by setting a flag. See *Hidden invariants* for what that read
  can and cannot see.
- **Both directions carry the half second the prompt states**, checked
  continuously rather than at a sample: entering, the figure has 0.5 s to be
  inside the 30-50% band with the wade driving; leaving, it gets 1.2 s to be back
  inside 85-115% with the wade gone (a measured ground speed also has to climb
  200 -> 500 at the engine's own acceleration and then work through the fixture's
  smoothing; judging that at 0.5 s failed a correct answer at 388 of 500,
  measured 2026-08-18, and a longer window can only let a genuinely slow answer
  through, never fail a correct one).
- **A sentinel checkpoint** at the end of the schedule declares the verdict, and
  fails by name when a leg never happened at all: the figure never moved on clean
  ground, fewer than two crossings, or the wade drove the pose on fewer than two
  of them.

**What this leg adds, and only this:** an L2I introspect leg
(`t1_mud_wade_bp.py`) that structurally proves the thing
L2 graded really was a Blueprint. Proving a Blueprint *exists* is not enough — a
C++ solve shipped beside a conforming Blueprint would pass L2 on the C++ and pass
a naive existence check on the asset. The script reproduces the fixture's own
resolution and requires the resolved answer to be Blueprint-generated, with no
native subclass of the placed class delivered. See the script's own header.

## Requirement-to-assertion map

| the prompt says | the gate that checks it | skipped when |
|---|---|---|
| walks at its normal top speed of 500 on clean ground | `WalksAtItsNormalTopSpeed` (the measured clean-ground average, 400-600) | never — the sentinel runs it, and a figure that never moved fails the same gate by its own literal |
| travels at 40% of normal top speed on the patch | `WadesSlowlyThroughTheMud` (30-50% of this run's measured clean-ground speed) | while fewer than 20 clean samples exist, while the figure is under 30 units/s, within 1.5 s of a turn, and within 0.5 s of entering the patch. A figure that never enters is caught by `WadesAgainOnTheSecondCrossing` |
| the supplied wade genuinely drives the pose | `TheWadeMotionDrivesThePose` | the same guards as above — it is asserted at the moment the slowed-speed gate passes, so it cannot be skipped independently of it |
| within half a second of stepping on | the 0.5 s entering window on both gates above | never |
| the ordinary walk and the full 500 are back within half a second | `FullSpeedReturnsOffThePatch` + `TheOrdinaryWalkReturnsOffThePatch` | until 1.2 s after leaving the patch (see the calibration note above), and under the same speed/turn guards |
| walk on a second time and it wades again, the same way | `WadesAgainOnTheSecondCrossing` (>= 2 crossings AND the wade drove the pose on >= 2 of them, each with its own literal) | never — it is the sentinel |
| the control keeps the ordinary walk | `TheCleanLaneFigureIsUntouched` (the wade may never drive its pose) | never — read every frame the test is running |
| the control never drops below 70% | `TheCleanLaneFigureIsUntouched` (speed floor) | while the control is under 30 units/s or within 1.5 s of its own patrol turn |
| Blueprint assets only, no C++ added | L2I `t1_mud_wade_bp.py` | never — L2I is declared, so a missing or unparseable script is exit 7 (HARNESS-ERROR, non-graded), not a pass |

Staging faults — the lane not staged as authored, the surface swap leaving the
wrong number of figures, a stand-in that is not a pawn, re-possession not taking,
or two candidate Blueprints — are reported as `HARNESS-PRECONDITION` and are
**never** a graded FAIL.

## Anti-gaming notes

1. **The same walk, played slower.** *Failure mode*: leave one gait in place and
   drop its playback rate (or just the walking speed) inside the patch, which
   looks plausible in a still frame and satisfies any speed-only gate.
   *Defense*: `TheWadeMotionDrivesThePose` asks the MESH what is driving it and
   fires the moment the figure is slowed on the patch without the supplied clip
   driving the pose; and the sentinel's `WadesAgainOnTheSecondCrossing` requires
   the wade to have driven the pose on at least two separate crossings.
2. **Wade everywhere, or wade always.** *Failure mode*: the figure is slowed and
   re-gaited globally, or from construction, so the patch is never actually read.
   *Defense* three ways: the measured clean-ground average must sit in 400-600
   **before** any mud is touched (a global slowdown dies there);
   `FullSpeedReturnsOffThePatch` / `TheOrdinaryWalkReturnsOffThePatch` require
   85-115% and no wade on clean ground after each exit; and the **control
   figure** — same class, same bytes, driven the same way in a lane 600 cm from
   any mud — may never wade and may never drop below 70%. A global change cannot
   satisfy the control and the subject at once. This is the note the Blueprint
   surface makes *easier* to trip, because a class-defaults edit is one click.
3. **A one-shot latch, in either direction.** *Failure mode (a)*: the wade fires
   on the first entry and never again. *(b)*: it fires once and never releases.
   *Defense*: the drive makes three crossings and the sentinel requires the wade
   on at least two of them, so (a) fails by its own literal; the off-patch gates
   require the ordinary walk and full speed after each exit, so (b) fails there.
   Each half is a separately named assertion.
4. **Not reading the patch at all.** *Failure mode*: hard-code the lane
   coordinates, or a timer, instead of reading the tagged patch. *Defense*: the
   control's patrol deliberately spans the same X band in a lane with no mud, so
   a coordinate fit slows the control (or wades it) and fails
   `TheCleanLaneFigureIsUntouched`; a timer fit has to hit three crossings whose
   instants are undisclosed and asymmetric while leaving the control alone.
5. **Shipping C++ next to a conforming Blueprint.** *Failure mode*: solve the task
   in `Source/ThirdPerson/` — where the placed class lives, so the map
   instantiates the answer with no Blueprint involved — and ship a decorative
   Blueprint beside it so an existence check passes. *Defense*: L2I reproduces the
   fixture's own resolution and requires the resolved answer to be
   Blueprint-generated AND no native subclass of the placed class to exist, with
   the scaffold class exempt by exact `/Script/` path rather than by name.
6. **A Blueprint the swap cannot use.** *Failure mode*: two candidate Blueprints
   under `/Game/Tasks`, an abstract one, or one that is not a pawn. *Defense*: two
   **non-abstract** candidates raise `HARNESS-PRECONDITION` rather than picking
   one, because grading a submission the agent may not have meant is not a
   verdict; a candidate marked abstract is skipped by the resolver, so if EVERY
   candidate is abstract it returns the C++ lane silently and L2I names that with
   `answer_is_instantiable`; and a non-pawn stand-in cannot be re-possessed, which
   the swap reports as a precondition. All three would otherwise present as "the
   submission never moved". **The skip runs BEFORE the ambiguity check**
   (`ResolveGradedBlueprintClass`, `CraftBenchFunctionalTest.cpp:682-696`), so an
   abstract intermediate shipped beside one concrete Blueprint resolves to exactly
   one class and is graded normally — L2I counts the RESOLVABLE set only, because
   counting raw candidates would FAIL a submission the harness graded correctly
   and charge it to the model. Corrected 2026-08-20; the first version of the
   script had it wrong in exactly that direction.
7. **Spoofing the observable.** *Failure mode*: transform or velocity writes timed
   to satisfy point samples rather than actually wading; or editing the fixture,
   the level or the introspect script. *Defense*: the fixture drives locomotion
   itself and measures ground actually covered per frame, smoothed, so a spoof has
   to genuinely traverse 400 cm of mud twice at 30-50% of its own clean speed; and
   `Source/CraftBenchTests/`, `Content/Maps/` and
   `tools/verify-single/introspect/` are outside the agent's writable roots
   (exit-4 sandbox reject), with the graded substrate materialized from **git
   HEAD** so an on-disk edit never reaches the grade.

## Hidden invariants

- **The surface swap, recorded here so the next reader does not re-derive it.**
  `ACraftBenchFunctionalTest` owns the surface lane (all four fixtures wired
  2026-08-20): `ResolveGradedBlueprintClass(PlacedClass)` returns the single
  Blueprint under `/Game/Tasks` whose generated class is a non-abstract strict
  subclass of the placed class, or `nullptr` for the C++ lane; TWO candidates
  raise `HARNESS-PRECONDITION` rather than picking one.
  `SwapForGradedBlueprint` spawns it at the placed transform, carries the tags
  over, and destroys the placed one. `SwapAllForGradedBlueprint` does the same
  over every instance of one class and REFUSES a mixed array.
  **This task uses `SwapAllForGradedBlueprintRepossessing`**, because one of the
  two figures is the pawn the game mode spawned and player 0 is driving:
  destroying a possessed pawn without re-possessing leaves every drive input
  going nowhere, which would read as a submission that never moves. Both figures
  are replaced or neither is — a swapped driven figure beside an unswapped
  control would grade the Blueprint against a C++ control, which measures
  nothing. The fixture self-checks the tag count after the swap rather than
  trusting it. No C++ was written for this leg.
- **The tags ride on the placed instances and are copied to the stand-ins**
  (`MudHero` on both, the control's extra instance tag on the control), so every
  tag lookup after the swap still resolves. A Blueprint that adds `MudHero` to
  its own class defaults as well is harmless (`AddUnique`), but a Blueprint that
  adds the CONTROL's tag would make both figures read as the control and the
  graded figure would never be found — a `HARNESS-PRECONDITION`, not a FAIL.
- **What `WadeDrivesPose` can actually see, and what it cannot.** It reads the
  mesh's `GetSingleNodeInstance()->GetAnimationAsset()` and the anim instance's
  current active montage, and matches on the clip's NAME. So the routes it
  answers for are: playing the clip on the mesh directly (which puts the mesh in
  single-node mode), or an active montage whose asset name carries the clip's
  name. **A state added to an Animation Blueprint's state machine, a blend driven
  by a bool, or a linked layer does NOT register**, however visibly it changes the
  pose. That is a property of the shared fixture and therefore identical on both
  legs — it is not a -bp tuning — but it is the single most likely way a correct
  intent scores as a failure on this pair, and it is why `REFERENCE-NOTE.md`
  leads with it. If a future run shows models reaching for the state-machine
  route, widen the fixture's read for BOTH legs at once, never for one.
- **The gate VALUES are all disclosed** (500, 200, 40%, 30-50%, 85-115%, half a
  second, 400-600, 70%, 400 cm, two crossings). The fixture's own clocking is
  not, and does not need to be: the 1.5 s turn grace, the 1.2 s leaving window,
  the 0.5 s entering window, the speed smoothing, the 30 units/s
  do-not-judge-a-standing-figure floor, the 20-sample clean-ground minimum and
  the sentinel's instant are all one-sided in the safe direction or are fixture
  artifacts a correct answer never has to predict.
- **Tick is SUPPLIED, not something to switch on.** `APawn`'s constructor sets
  `PrimaryActorTick.bCanEverTick = true` (`Pawn.cpp:50`), so the placed class
  inherits it and `Event Tick` fires in a Blueprint child. Independently, the
  Blueprint compiler force-enables it for any Blueprint with a CONNECTED Event
  Tick (`FKismetCompilerContext::SetCanEverTick`, `KismetCompiler.cpp:5504`, gated
  on `bCanBlueprintsTickByDefault`, which `BaseEngine.ini:319` sets true). Two
  independent reasons this leg is not unwinnable the way the tint pair's was
  before its scaffold was given a tick.

### MEASURED 2026-08-23 — what is now known, and what still is not

- **Both legs discriminate.** `cb discriminate` on `substrate=HEAD`:
  `bp/t1-mud-wade-bp` reference PASS / empty FAIL, and
  `cpp/t1-mud-wade-cpp` reference PASS / empty FAIL. The reference asset is
  `reference/Content/Tasks/t1-mud-wade-bp/BP_MudWader.uasset`; what was actually
  built deviates from the recipe in three recorded ways (`REFERENCE-NOTE.md`,
  *WHAT WAS ACTUALLY BUILT*).
- **The FIRST attempt that day returned `reference FAIL(skipped)`, and it was a
  MACHINE artifact, not a verdict.** Same commit, same asset: the preflight had
  warned at 10.6 GB of free commit against a 10 GB floor, L1 died, and the run
  recorded it as the submission failing — exactly the C3859 shape the preflight
  text names. The next seven legs then aborted at exit 2 under the blocker at
  8.1 GB. The cause was 26 orphaned `Aura/MCP` python children holding 11.75 GB
  of commit; reaping them took free commit to 22.3 GB and the same command then
  read `11 checks OK` and PASSed. **Treat `reference FAIL(skipped)` as
  uninterpretable until the commit headroom at that run is known.**
- **FIXED 2026-08-23: the C++ leg's own reference was broken and now is not.**
  Its `FObjectFinder` was repointed at the un-suffixed path, and that leg now
  discriminates. The SCAFFOLD's finder is still dead on purpose — it is trap 2,
  it is dead identically on both legs, and overcoming it is part of the task.
  The original diagnosis is kept below because it is what the fix was derived
  from.
- **(historical) The C++ leg's own reference is currently broken, and it is not
  this leg's to fix.** The scaffold and the committed `-cpp` reference both resolve the wade
  clip at `/Game/Tasks/t1-mud-wade-cpp/A_MudWade`, and
  the clip has only ever existed at the un-suffixed
  `/Game/Tasks/t1-mud-wade/A_MudWade` (added in
  `b0633747`; the path was rewritten by the `-cpp` rename in `1a484c7a` while the
  content folder was not). `ConstructorHelpers::FObjectFinder` therefore fails,
  `WadeMotion` is null, `PlayAnimation` no-ops, and
  `TheWadeMotionDrivesThePose` cannot pass on the C++ leg. Its
  `discrimination/MATRIX.md` "reference PASS" row predates the rename. **This
  leg's recipe deliberately does not go through that inherited property** — it
  references the clip asset directly at the path that actually holds it.
- **BLOCKER — CODE FIXED 2026-08-23, STILL UNVERIFIED ON A LIVE DRIVE.**
  `stage_per_task_dirs_active_only` is now pair-aware: it keeps any per-task
  directory whose `pair_base` matches the active task's base, and keeps only its
  own directory for a task carrying no surface suffix
  (`tools/verify-single/task_layout.py`, via `runlib.run_identity.pair_base`;
  both directions pinned by `tools/verify-single/tests/test_task_layout_pair_sharing.py`).
  Both live call sites route through that one function
  (`tools/run-agent/workspace.py:312`, `aura_rig/graded_scratch.py:313`), so the
  fix reaches both surfaces. **What is NOT yet true: no live agent drive has been
  run on this task since the fix.** Note carefully that the discriminate PASSes
  above CANNOT verify this, for the reason this bullet itself gives — the grading
  path does not stage at all. Do not read them as clearing it.
- **(historical, the defect the fix above addresses) on the live agent
  surface this task is UNWINNABLE, and the reference will still PASS.** Not a
  Blueprint-expressiveness limit — a staging one, and it is fixable, but
  disclosure does not make the leg winnable and this bullet is not a licence to
  run it.
  `task_layout.stage_per_task_dirs_active_only` (`tools/verify-single/task_layout.py:183-207`)
  deletes every per-task directory under `PER_TASK_ROOTS` (`:40` — `Content/Tasks`,
  `Content/Maps`, `Source/ThirdPerson/Tasks`, `Source/CraftBenchTests/Tasks`) whose
  name is not EXACTLY the active task id. `bare_task_id` (`:93`) strips the SET
  prefix only, never the `-bp` suffix, so with
  `t1-mud-wade-bp` active two directories this leg depends
  on match `TASK_DIR_RE` (`:52`), fail the equality test, and are `shutil.rmtree`'d:
  - `Content/Tasks/t1-mud-wade/` — **the only copy of
    `A_MudWade.uasset` anywhere on disk**, and the exact path this leg's prompt
    and *Workspace state pre-task* both name as supplied.
  - `Source/ThirdPerson/Tasks/t1-mud-wade-cpp/` —
    `MudHeroCharacter.h/.cpp`, the class the Blueprint must derive from. (Source
    roots skip the `require_task_like` test entirely, so the name shape does not
    save it.)

  It runs on BOTH agent-visible surfaces (`tools/run-agent/workspace.py:312`, on
  the copied `project_dir`, and `aura_rig/graded_scratch.py:313`). The GRADING
  path (`run_task.py`) does not stage at all, so `cb discriminate` and
  `cb refgate` grade with the clip present and will report the reference PASS —
  **the worst asymmetry shape there is**, because it reads as models failing the
  surface. The clip half alone is fatal and does not depend on whether the staged
  tree keeps prebuilt binaries: `WadeDrivesPose`
  (`MudWadeFunctionalTest.cpp:80-108`) answers true only for a single-node player
  or an active montage whose asset NAME contains `A_MudWade` (`kWadeName`, `:23`),
  so with the asset gone `TheWadeMotionDrivesThePose` cannot pass for ANY
  submission, and `WadesAgainOnTheSecondCrossing`'s "the wade drove the pose on
  >= 2 crossings" half cannot either. **The clip half hits the `-cpp` leg too** —
  same folder name, same deletion, same active-id mismatch.

  **The fix, for whoever picks it up.** Move the shared clip to a directory the
  stager cannot classify as a foreign task, and re-point every reference to it in
  ONE change. `TASK_DIR_RE` is `^[a-z0-9][a-z0-9-]*$`, so a leading underscore is
  the established escape — underscore-prefixed folders such as
  `Content/Tasks/_runreport/` already survive staging for exactly this reason, and
  root-level flat maps are the same precedent; `Content/Tasks/_shared/mud-wade/A_MudWade`
  would survive both surfaces. That change touches the substrate, the scaffold's
  `FObjectFinder` path (`MudHeroCharacter.cpp:52`) and the prompt prose on BOTH
  legs, so it is out of this leg's scope and is reported rather than half-done
  here: naming a path that does not yet hold the asset is precisely the `-cpp` bug
  below. The scaffold-folder half is pair-wide (the tint pair has the same
  `-cpp`-named scaffold folder), so a carve-out in `task_layout` — a pair-aware
  `bare_task_id`, or keeping the sibling leg's per-task dirs — is the alternative
  worth costing, and it would fix every future bp/cpp pair at once.
- **BLOCKER — the pair's two prompts disclose DIFFERENT paths for the same
  supplied clip, which forks the pair in the one dimension it exists to hold
  constant.** This leg (the *Prompt* and *Workspace state* blocks above) names
  `Content/Tasks/t1-mud-wade/A_MudWade`, which is where
  the asset actually lives. The `-cpp` leg's prompt
  (`cpp/t1-mud-wade-cpp/task.md:63`) names
  `Content/Tasks/t1-mud-wade-cpp/A_MudWade` — a folder
  that does not exist, the same dead path as the scaffold's `FObjectFinder`, and
  the working path is disclosed NOWHERE on that leg. No gate VALUE was forked
  (500 / 400 cm / 40% / 200 / 0.5 s / 70% / 400-600 / 30-50% / 85-115% are
  identical and the `fixtures:` string matches byte-for-byte), so this is not a
  tolerance fork — it is a DIFFICULTY fork: the `-bp` agent is handed a resolvable
  path and the `-cpp` agent a dead one. Any (model x tool x surface) number drawn
  from this pair would carry that asymmetry rather than the surface. **This leg is
  the correct half**, so the fix belongs on the `-cpp` prompt and the scaffold
  finder — but it must land before EITHER leg is benched.
  **FIXED 2026-08-23, prompt half only.** The `-cpp` prompt and that leg's MATRIX
  now name the un-suffixed `Content/Tasks/t1-mud-wade/A_MudWade`, so both prompts
  disclose the same working path and the difficulty fork is closed. The SCAFFOLD
  finder was deliberately left dead: it is trap 2 in this leg's REFERENCE-NOTE
  (the property arrives null and `Play Animation` on a null asset silently does
  nothing), and it is dead IDENTICALLY on both legs, so it is a shared trap rather
  than a fork. The rename to the short base preserved that relationship exactly —
  the finder moved to `t1-mud-wade-cpp` and the clip to `t1-mud-wade`, the same gap
  it had as `...-the-mud-cpp` vs `...-the-mud`.
- **The L2I abstract-count defect is FIXED here (2026-08-20), and its twin is
  still open elsewhere.** The first cut of
  `t1_mud_wade_bp.py` counted every Blueprint subclass
  toward ambiguity, but `ResolveGradedBlueprintClass` skips `CLASS_Abstract`
  candidates BEFORE its two-candidate check
  (`CraftBenchFunctionalTest.cpp:682-696`), so a submission shipping an abstract
  intermediate plus one concrete Blueprint is graded normally while three of the
  script's six checks reported FAIL — a false FAIL charged to the model on a run
  the harness graded correctly. The script now partitions candidates into
  resolvable / skipped-as-abstract / unprobed and counts only the resolvable set,
  with an unreadable abstract flag failing closed. **Proven offline only** —
  `tools/verify-single/tests/test_introspect_mud_wade_bp.py` drives the real
  `main()` over ten faked project states (13 tests, green) and a mutation check
  confirmed the pre-fix logic FAILs the abstract-intermediate case with exactly
  the 3-of-6 shape the review predicted. That oracle cannot prove the UE
  reflection names are right; only a live editor does, and no live editor has run
  this script.
  **`t1_screen_tint_bp.py` still carries the original shape**
  (`exactly_one_blueprint_answer` and `answer_is_in_the_declared_folder` both
  count raw candidates, and it has no `answer_is_instantiable` check at all) — not
  this leg's file to edit, reported instead.

## Reference solution metadata

`reference/Content/Tasks/t1-mud-wade-bp/` — Blueprint
assets, to be authored in an attended editor session (there is no script lane for
Blueprint graph authoring in this repo). The recipe is `REFERENCE-NOTE.md`,
precise to the node and the pin so the asset can be rebuilt without re-deriving
the design.

- Files: 1 created (one Blueprint), 0 modified. 0 lines of C++, by contract.
- Senior-dev estimate: 1.0-1.5 h (read the supplied class, add the patch read, the
  speed write and the motion swap, confirm both directions and the second
  crossing, confirm the control is untouched).

**Not yet true:** no reference asset exists, no run has happened, and the three
blockers above (the `-cpp` reference's dead clip path, the staging deletion that
makes the live agent surface unwinnable, and the forked clip path across the
pair's two prompts) are all open. **The staging blocker gates benching this leg at
all** — a run scheduled before it lands measures the harness, not the model. `cb discriminate --task t1-mud-wade-bp`
(reference PASS / empty FAIL) and a re-discriminate of the `-cpp` leg on the same
tree are what would make any of this true. The owner has to PLAY it as well
(2026-08-18 directive); the map is shared with the C++ leg, so the play project
already carries it.
