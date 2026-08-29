---
id: t1-mud-wade-cpp
substrate: ThirdPerson
set: cpp
tier: T1
capability_bucket: Technical Art
category: animation
layers: [L1, L2]
fixtures: ["L_MudLane :: AMudWadeFunctionalTest"]
---

# t1-mud-wade

A gameplay-driven gait change the stock Third Person template has no equivalent of:
the figure walks normally, walks onto a patch of mud, and its motion changes to a
slow heavy wade — a *different* motion, not the ordinary walk played slower — then
returns to normal on the far side, and does the whole thing again on the way back.
The control is a second, identical figure patrolling a parallel lane with no mud,
which must read the ordinary walk and its full speed at every checkpoint.

`deliverable_root` is **not** an accepted front-matter key (`tools/verify-single/spec.py`
`_KNOWN_KEYS` rejects unknown keys with a hard `ValueError`, i.e. exit 2 "spec
malformed" — verified against the real parser while authoring). The deliverable root is
therefore stated as the first line of *Workspace state pre-task* and again in the
prompt body, which is what `tasks/README.md` requires it for.

### Why this shape and not the corpus row

The imported row (`t1-locomotion-idle-move-state`) asked for idle-at-rest,
move-while-travelling, idle-again. The owner's verdict on it was `fix-first`: *"This
sounds like default manny behavior with the given template. Shall we do something more
advanced?"* — and it is exactly right. The `ThirdPerson` substrate already ships a
working walk/idle graph, so that row would have graded a template feature rather than
the agent's work. A gait the template has no equivalent of does not have that problem,
and it keeps everything the original row was testing: a live read of which motion is
driving the pose, driven by world state, with the supplied normal locomotion preserved.
Full provenance in `notes.md`.

## Primary concept

- `anim-state-machine` — State Machines
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/state-machines-in-unreal-engine)

The load-bearing capability is adding a **gameplay-conditioned motion state** to a
working locomotion graph: a second, distinct motion that becomes the one driving the
pose while a world condition holds, releases cleanly when it stops holding, re-enters
on a second occurrence, and leaves the supplied normal locomotion untouched. The route
is the agent's — a state added to the existing state machine, a blend driven by a bool,
a linked layer, anything — and none of the graded checks name one.

## Prompt given to the agent

> The level is a marked lane on flat ground. Your figure starts on the lane and walks
> it end to end at its normal top speed of 500 units per second. Part-way along,
> 400 cm of the lane is a patch of dark, wet ground. That patch is a single thing in
> the level and it carries the tag `MudPatch`; it blocks nothing, so the figure walks
> straight onto and through it.
>
> Make the figure wade through it. While the figure is on that patch two things must
> be true, and both must become true within half a second of it stepping on: it travels
> at 40% of its normal top speed (200 units per second), and the motion driving its
> body is a visibly different one — the supplied heavy wade at
> `Content/Tasks/t1-mud-wade/A_MudWade`, genuinely driving the
> pose, not the ordinary walk played back slower. When the figure steps off the patch,
> the ordinary walk and the full 500 units per second must both be back within half a
> second. Walk onto the patch a second time and it must wade again, the same way.
>
> Nothing else may change. A second, identical figure patrols a parallel lane that has
> no mud on it; that one must keep the ordinary walk and its full speed for the whole
> run — it is never allowed to drop below **70%** of the speed the graded figure
> measures on clean ground, and the wade motion must never drive its pose. The
> graded figure's own clean-ground speed is itself checked against the 500 it is
> supposed to run at, with a **400-600 units per second** acceptance band, so a
> submission that changes the ordinary walk speed at all fails before any mud is
> touched. Correctness is judged from measured ground speed — on the patch it must read
> between 30% and 50% of the speed the same figure measures on clean ground, and off
> the patch between 85% and 115% — and from which motion is driving the pose, sampled
> at moments you are not told, on both crossings.
>
> Your deliverable is **C++** under
> `Source/ThirdPerson/Tasks/t1-mud-wade-cpp/`. The figure `AMudHeroCharacter` and
> the supplied wade clip `Content/Tasks/t1-mud-wade/A_MudWade` already exist; the
> figure carries no mud logic and nothing references the wade clip yet.
>
> **Do not author a Blueprint pawn under `Content/Tasks/`.** On this surface the
> graded figure and the control figure must be instances of the same class, and a
> Blueprint pawn makes them different ones — the run is refused before any
> behaviour is measured. Blueprint is the `-bp` twin's route, not this one.
> `Content/Tasks/` stays writable for non-pawn assets; nothing outside those two
> roots is writable.

## Workspace state pre-task

**Deliverable root: `Content/Tasks/t1-mud-wade-cpp/`.** The
`ThirdPerson` substrate's writable roots are `Content/Tasks/` and
`Source/ThirdPerson/` (`UE-projects/ThirdPerson/AGENT_WRITABLE.json`); everything else,
including `Content/Maps/`, `Content/Characters/`, `Content/ThirdPerson/` and
`Source/CraftBenchTests/`, is deny-listed and a submission file there is an exit-4
sandbox reject, not a graded FAIL.

Content that **exists** under `Content/Tasks/t1-mud-wade/`:

- `A_MudWade.uasset` — the supplied heavy-wade clip: a looping forward-locomotion clip
  on the same skeleton, visibly a different gait from the ordinary walk at a glance,
  duplicated from a read-only stock clip under `/Game/Characters/` and **referenced by
  nothing as shipped**. It is not a retimed copy of the walk clip. It also carries one
  verifier-owned marker on its own timeline; see *Hidden invariants*.

**No `BP_MudHero.uasset` and no `ABP_MudHero.uasset` ship on this surface**, and the
prompt must not describe them as existing. Both belong to the `-bp` twin
(`tasks/bp/t1-mud-wade-bp/`), and the paragraph that named them here was carried over
from it. `git ls-files UE-projects/ThirdPerson/Content/Tasks/t1-mud-wade*` returns the
clip and nothing else.

> **Corrected 2026-08-26, after four graded cells were voided.** Agents that followed
> the old wording authored `BP_MudHero`, which made the graded figure and the placed
> control figure different classes, and the fixture refused the run at
> `CraftBenchFunctionalTest.cpp(896)`:
> `HARNESS-PRECONDITION: the actors handed to the surface swap are not all one class
> (MudHeroCharacter vs BP_MudHero_C)`. The test aborts there, ~14 s in, before a single
> behavioural gate runs — so following the instructions was an automatic FAIL, and the
> failures read as "no model can do this task". `ResolveGradedBlueprintClass` scans
> **all** of `/Game/Tasks` recursively, so any Blueprint pawn the agent leaves there is
> enough to enter that path. The reference — the only validated solution — is C++ only.

C++ that **exists** under `Source/ThirdPerson/Tasks/t1-mud-wade-cpp/`:

- `MudHeroCharacter.h` / `.cpp` — a concrete `AMudHeroCharacter` deriving from the stock
  template's playable character (which is abstract and unspawnable, so a concrete
  subclass is required — the same arrangement `cpp/tp2-sprint-stamina` uses). It
  inherits the template's tuned ground movement (top walking speed 500 units/second,
  rotation follows movement) and the template's keyboard movement lane, so a human can
  drive it with WASD. Its constructor adds the tag `MudHero`. **No mud logic, no speed
  modification, no motion selection.**
- `MudHeroGameMode.h` / `.cpp` — a game mode whose default pawn resolves to
  `/Game/Tasks/t1-mud-wade-cpp/BP_MudHero`, falling back to
  `AMudHeroCharacter` if that asset cannot be found. The level's world settings select
  it, so hitting Play possesses the agent's own figure at the player start.

The level — `Content/Maps/L_MudLane.umap`, a
committed binary, verifier-owned and deny-listed to the agent:

- A large flat floor with **stripe markings every 200 cm** along the lane, so speed and
  distance are readable by eye.
- A **player start on that floor, off the world origin**, at the `-X` end of the lane
  facing `+X`.
- The **mud patch**: one placed actor tagged `MudPatch`, a dark wet-looking slab set
  flush into the floor spanning `X ∈ [300, 700]` (400 cm, i.e. two stripe intervals)
  and `Y ∈ [-100, +100]`, generating overlap events with pawns and **blocking nothing**.
- The **control figure**: one placed instance of
  `/Game/Tasks/t1-mud-wade-cpp/BP_MudHero` in a parallel lane at
  `Y ≈ +400`, instance-tagged `MudTwin`, with its own stripe markings and **no mud
  anywhere in that lane**. Because the level references the deliverable path, the
  control is by construction the agent's own class — the same bytes as the graded
  figure.
- Subject and control sit in one camera frame ~300-400 cm apart, and a
  **landmark at each end of the backdrop** (two differently-coloured posts) so a moving
  camera is distinguishable from a still one in the captured stills.
- One placed `AMudWadeGaitFunctionalTest` (the L2 fixture) and one placed
  verifier-owned readout actor (below).
- `cameras.json` (the camera-plan lane; not part of this release) beside this spec frames subject + control + at least four stripes,
  with the mud patch inside the frame at every shot.

The **on-screen readout** is verifier-owned, in `Source/CraftBenchTests/Tasks/t1-mud-wade-cpp/`,
placed in the level and therefore live for a human who simply hits Play: floating text
above each figure showing that figure's measured ground speed in units/second and its
gait as the verifier reads it (`NORMAL` / `WADING`). Every number the grade depends on
is therefore on screen, read by the same code path that grades it, in a module the
agent cannot write to. It is assert-free and can never reach a verdict.

Content that **does not exist** (the agent creates nothing new unless it wants to):

- No wading motion, no second gait, no mud detection, no speed change, anywhere. An
  untouched submission builds (L1 green) and fails L2 at the named wade gate.
- No test source in the agent's writable path. `AMudWadeGaitFunctionalTest`, the readout
  actor and `tools/verify-single/introspect/mud_wade_gait.py` all live outside it.

## Verifier specification

> **The fixture, not this section, is the authority.** What follows still
> describes a superseded design — a verifier-owned marker curve on the clip,
> five hand-placed checkpoints, a `MudTwin` tag, and an **L2I leg that was
> dropped**. The front matter above is correct: `layers: [L1, L2]`, and
> `tools/verify-single/introspect/mud_wade_gait.py` is not on disk. Both legs
> are graded by the committed fixture driving per-frame movement input — the
> same path a human's WASD drives. See `tasks/bp/t1-mud-wade-bp/task.md` for
> the description that matches what shipped.

Verification primitive: **`pie-checkpoint-sampling`** as the spine, with
**`pie-state-probe`** for the in-fixture reads (ground velocity, movement mode, the live
animation-curve read, the live animation-state read) and
**`editor-python-introspection` (L2I)** for the static asset structure that runtime
cannot see. Nothing here invents a verifier mechanism.

The test runs in PIE from
`Content/Maps/L_MudLane.umap` on the
**ThirdPerson** substrate, at a fixed deterministic step (`-deterministic -FPS=60`). The
level's world settings select `AMudHeroGameMode`, which spawns and possesses the
`MudHero`-tagged figure at the player start.

**No shared control-figure helper exists, and the implementor should not go looking for
one.** `ACraftBenchPawnFunctionalTest::SpawnAndPossessPawn()` spawns and possesses
exactly ONE pawn and has no API for a second subject; adding one is the other machine's
change and the base classes are not to be edited. This fixture therefore derives from
`ACraftBenchFunctionalTest` (the game mode, not the fixture, supplies the graded figure —
the same arrangement `cpp/tp2-sprint-stamina` uses) and carries **its own local
possess-and-drive code for the control figure**, duplicated per task with the owner's
explicit approval. The same applies to the visible-mesh predicate: the base's
`PawnVisiblyRepresented` reads the base's own `Pawn` member, so this fixture carries a
local copy that it applies to both figures.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on the first failure)
```

An asset-only submission still has to load cleanly, so L1 is a precondition, never a
correctness signal.

### L2 — AFunctionalTest behavioral trace

```text
AMudWadeGaitFunctionalTest (derives ACraftBenchFunctionalTest):

  PrepareTest():
      Super::PrepareTest()                       // base sets fixed timestep
      // identity by TAG, never by class — the agent may subclass freely
      Hero = the single MudHero-tagged actor that is NOT MudTwin-tagged
             (named FAIL: "... exactly one MudHero ... (graded figure missing).")
      Twin = the single MudTwin-tagged actor
             (named FAIL: "... exactly one MudTwin ... (control figure missing).")
      assert Twin->GetClass() == Hero->GetClass()
             (named FAIL: "... control figure is not the same class as the graded
              figure (control substituted).")
      Patch = the single MudPatch-tagged actor; assert its extent matches the
              staged 400x200 cm slab
      local visible-mesh predicate on BOTH figures
             (named FAIL: "... figure carries no visible mesh ...")
      if Twin has no controller: spawn one   // local possessor; an unpossessed
                                             // Character is inert (MOVE_None)
      SetCheckpointSchedule({1.6, 3.4, 6.4, 8.6, 11.4})  // WORLD game-time

  Tick(dt):
      Super::Tick(dt)                        // base runs the checkpoint clock first
      if !IsRunning(): return
      // shipping per-frame movement input — the same path a human's WASD drives:
      // see Tasks/t1-overlap-teleport-portal/TeleportPortalFunctionalTest.cpp:194,
      // Tasks/t2-ladder-climb-volume/LadderClimbFunctionalTest.cpp:246,
      // Tasks/t2-npc-follows-player/NpcFollowFunctionalTest.cpp:144
      Hero->AddMovementInput(HeroLegDir, 1.0f)     // +X out, then -X back
      Twin->AddMovementInput(TwinLegDir, 1.0f)     // closed rectangular circuit
      advance HeroLeg when the hero passes its turn mark (X >= 1400 -> -X)
             // 1400, not 1100: cp2 grades a SETTLED clean phase on the +X
             // side, and the turn must not happen before it
      advance TwinLeg when the twin comes within 100 cm of its next corner
             // rounded corners: the circuit never stops and never reverses, so the
             // control is in steady travel at every checkpoint by construction

  PHASE MEMBERSHIP, recorded every frame. This is what makes the checkpoint
  windows safe; the earlier draft's absolute X windows were NOT safe -- see the
  note below the block.
      InPatch(t)   := the hero capsule's 2D centre is inside the MudPatch actor's
                      live world bounds
      DwellIn(t)   := seconds the hero has been continuously InPatch
      DwellOut(t)  := seconds the hero has been continuously !InPatch
      SETTLE := 0.5 s + one frame   // the prompt's own disclosed transition
                                    // latency, plus one frame of sampling slack

  OnCheckpoint(i, t):
      // Speed = Velocity.Size2D(); guard: valid, !IsFalling()
      //         (named FAIL: "... figure is airborne at checkpoint i ...")
      // EVERY checkpoint first checks that it is grading a SETTLED phase, and
      // reports a miscalibrated schedule as a HARNESS-PRECONDITION, never as a
      // graded FAIL:
      //   a WADE checkpoint  requires InPatch  and DwellIn  >= SETTLE
      //   a CLEAN checkpoint requires !InPatch and DwellOut >= SETTLE
      //   else FinishTest(Error, "HARNESS-PRECONDITION: checkpoint <i> did not
      //        land in a settled <wade|clean> phase (heroX=<x> inPatch=<b>
      //        dwell=<s>) -- recalibrate the schedule")
      cp0 CLEAN  t=1.6   hero on clean ground before the patch
                 V0 = HeroSpeed; assert 400 <= V0 <= 600
                   ("the figure's clean-ground top speed measured <v>, outside
                     the 400-600 band the prompt states")
                 NormalMarker = HeroWadeMarker; assert NormalMarker < 0.5
                   ("the wade motion was already driving the pose on clean
                     ground")
                 NormalState  = HeroActiveState                 (may be unavailable)
                 THE FOUR TWIN GATES, run at cp0 and at every later checkpoint
                 with " (cp<i>)" appended to each literal:
                 assert TwinSpeed >= 0.70 * V0
                   ("the control figure was slowed on its own clean lane")
                 assert TwinWadeMarker < 0.5
                   ("the control figure was wading on its own clean lane")
                 assert |TwinY| >= 150
                   ("the control figure was not on its own separate lane")
                 assert TwinActiveState == NormalState           (when available)
                   ("the control figure was in a different motion state from the
                     graded figure on clean ground")
                 [cp0 previously read the control's SPEED and STATE only. Since
                  the state read is a declared-skippable spike, that left the
                  control's GAIT completely ungauged at cp0 whenever
                  state=unavailable -- contradicting anti-gaming note 2, which
                  claims the marker is gauged at EVERY checkpoint. TwinWadeMarker
                  and |TwinY| are now read at cp0 too, so all four twin gates run
                  five times.]
      cp1 WADE   t=3.4   hero inside the patch, FIRST crossing
                 assert 0.30 <= HeroSpeed/V0 <= 0.50
                   ("first crossing: measured <r> of clean-ground speed, outside
                     the stated 30-50% band")
                 assert HeroWadeMarker >= 0.5                   // wade clip drives pose
                   ("first crossing: the supplied wade motion was not driving the
                     pose")
                 WadeState = HeroActiveState; assert != NormalState  (when available)
                   ("first crossing: the figure stayed in its ordinary motion
                     state")
                 the four twin gates, suffixed " (cp1)"
      cp2 CLEAN  t=6.4   hero clear of the patch, +X side
                 assert 0.85 <= HeroSpeed/V0 <= 1.15
                   ("after the first crossing: measured <r> of clean-ground
                     speed, outside the stated 85-115% band")
                 assert HeroWadeMarker < 0.5
                   ("after the first crossing: the wade motion was still driving
                     the pose")
                 assert HeroActiveState == NormalState           (when available)
                   ("after the first crossing: the figure never returned to its
                     ordinary motion state")
                 the four twin gates, suffixed " (cp2)"
      cp3 WADE   t=8.6   hero inside the patch, SECOND crossing
                 assert 0.30 <= HeroSpeed/V0 <= 0.50
                   ("second crossing: measured <r> of clean-ground speed,
                     outside the stated 30-50% band")
                 assert HeroWadeMarker >= 0.5
                   ("second crossing: the supplied wade motion was not driving
                     the pose")
                 assert HeroActiveState == WadeState             (when available)
                   ("second crossing: the figure entered a DIFFERENT state from
                     the one it used on the first crossing")
                 the four twin gates, suffixed " (cp3)"
      cp4 CLEAN  t=11.4  hero clear of the patch, -X side
                 assert 0.85 <= HeroSpeed/V0 <= 1.15
                   ("after the second crossing: measured <r> of clean-ground
                     speed, outside the stated 85-115% band")
                 assert HeroWadeMarker < 0.5
                   ("after the second crossing: the wade motion was still
                     driving the pose")
                 assert HeroActiveState == NormalState           (when available)
                   ("after the second crossing: the figure never returned to its
                     ordinary motion state")
                 the four twin gates, suffixed " (cp4)"
                 -> FinishTest(Succeeded)

  TRANSITION-LATENCY GATE, from the per-frame record (four firings). The prompt
  says both changes must happen "within half a second" in each direction, and an
  earlier draft asserted that NOWHERE -- no checkpoint sampled near a boundary,
  so a two-second ramp passed. For each of the four patch-boundary crossings the
  hero makes, the fixture records the crossing frame and the first later frame at
  which BOTH the speed ratio is inside the destination band AND the marker has
  crossed 0.5 in the right direction, then asserts the gap <= SETTLE:
      entering the patch, crossing 1   ("the figure took <s> s to start wading on
                                         the first entry; the limit is half a
                                         second")
      leaving  the patch, crossing 1   ("the figure took <s> s to return to the
                                         ordinary walk after the first crossing")
      entering the patch, crossing 2   ("the figure took <s> s to start wading on
                                         the second entry")
      leaving  the patch, crossing 2   ("the figure took <s> s to return to the
                                         ordinary walk after the second
                                         crossing")

  every checkpoint logs "[mud-wade calib] cp<i> t=<t> heroX=<x> v=<v> ratio=<r>
  marker=<m> state=<machine>/<state> twinV=<v> twinY=<y> twinSettled=<0|1>"
  (LogTemp/Display) for tolerance calibration and for the reference read.
```

**The two independent reads of "which motion is driving the pose."**

1. **`HeroWadeMarker` — the marker read (primary, route-independent, no spike).**
   `UAnimInstance::GetCurveValue(<verifier-owned marker name>)` on the figure's mesh.
   The supplied `A_MudWade` carries that marker across its whole length; the read-only
   stock sources the ordinary walk comes from carry nothing like it. Any mechanism that
   actually plays the supplied clip makes the marker read — a state added to the state
   machine, a blend driven by a bool, a linked layer, a montage. The ordinary walk played
   back slower makes it read zero. This is a stock, long-proven API and is the read the
   grade leans on.
2. **`HeroActiveState` — the live state read (as the batch brief directs).**
   `IAnimClassInterface::GetFromClass(AnimInstance->GetClass())` →
   `GetBakedStateMachines()`, then `AnimInstance->GetStateMachineInstance(i)` →
   `GetCurrentState()`, mapped back to `FBakedAnimationStateMachine::States[idx].StateName`.
   **Never `UAnimInstance::GetCurrentStateName(int32)` — it segfaults.** This read has
   never run headless in this repo; a 30-minute probe is a GO/NO-GO before the fixture is
   written (`notes.md`).
   Its checks are marked *(when available)* on purpose, and that is a **stated skip
   condition, not a route ban**: a submission whose motion asset exposes no baked state
   machine — a legitimate blend-node or layer answer — has nothing here to read, and the
   fixture logs `state=unavailable` and skips exactly these clauses while the marker,
   speed and structural gates still carry the grade. A submission that DOES expose state
   machines is held to all of them. Grade the outcome, warn on the route.

**Pass criteria**: L1 both targets, all five L2 checkpoints, and all eight L2I checks.
**Robust identity**: figures by tag, the patch by tag, the wading motion by the marker on
the supplied clip — never by class name, node type or asset type.
**Why no `fps_legs`**: every graded quantity is instantaneous (a speed ratio, a marker
value, a state identity) rather than a duration, and the two crossings sit at asymmetric
times, so there is no timed behaviour for a frame-count fit to land on. A second rate
would add cost and a false-FAIL surface (coarser movement integration drifting the
positional windows) for no discrimination.

### L2I — Structural assertion

`tools/verify-single/introspect/mud_wade_gait.py`, run headless read-only via
`UnrealEditor-Cmd -ExecutePythonScript=` under `-nullrhi`, printing one
`CRAFTBENCH-INTROSPECT-JSON` verdict block. It emits **exactly 8 named checks on every
leg** — a constant denominator, so a submission cannot improve its reported
`tests_passed/tests_run` by making checks unreachable. PASS requires all 8:

```text
hero_figure_resolves          /Game/Tasks/<id>/BP_MudHero resolves and its generated
                              class derives from the substrate playable character
hero_figure_drives_a_motion   BP_MudHero names SOME motion asset for its mesh, and
                              that asset is not one of the deny-listed read-only
                              stock ones — i.e. the figure's pose is decided by
                              something the submission owns, WHEREVER it lives.
                              NOT "contains /Game/Tasks/<id>/ABP_MudHero": the
                              pre-state explicitly invites the agent to author its
                              own motion asset ("the agent creates nothing new
                              unless it wants to"), and pinning the identity of the
                              supplied shell FAILed a structurally-correct
                              submission that wrote its own
motion_asset_resolves         /Game/Tasks/<id>/ABP_MudHero resolves and is a motion
                              asset for the mannequin skeleton
wade_clip_resolves            /Game/Tasks/<id>/A_MudWade resolves, is an animation
                              sequence, and has positive length
wade_clip_still_a_clip        it is still a non-degenerate forward-locomotion
                              sequence on the mannequin skeleton with positive play
                              length and at least the frame count needed to read as
                              motion. It does NOT have to match the stock clip it
                              was duplicated from: the earlier
                              `wade_clip_unmodified` check required its play length
                              and frame count to equal the read-only original, which
                              forbids retiming or re-looping the supplied clip — a
                              plausible legitimate answer that nothing in the prompt
                              rules out. Retiming is now legal; deleting the motion
                              is not
wade_clip_keeps_marker        it still carries the verifier-owned marker across its
                              length — stripping the marker is a submission fault and
                              must FAIL by name, never read as "not wading"
wade_motion_reachable         A_MudWade is referenced by SOMETHING the submission
                              owns that can drive this figure's pose — its motion
                              asset, a montage, a layer asset, or agent code under
                              `Source/ThirdPerson/`. Computed as: the clip has at
                              least one referencer inside the two writable roots.
                              NOT "ABP_MudHero's dependency set contains
                              A_MudWade": that FAILed the C++ route the prompt
                              itself offers, the montage route anti-gaming note 1
                              endorses, and any soft-reference wiring — none of
                              which land in the shell's dependency set. The
                              STRUCTURAL check only has to prove the clip is not
                              orphaned; whether it actually drives the pose is
                              measured at runtime by `HeroWadeMarker`, which is the
                              read the grade leans on
normal_gait_source_retained   ABP_MudHero's dependency set still contains
                              /Game/Characters/Mannequins/Anims/Unarmed/BS_Idle_Walk_Run
                              — the supplied ordinary locomotion was not ripped out or
                              swapped for something else
```

Every route is reflection-safe and precedented. Asset existence and class identity go
through `EditorAssetLibrary.does_asset_exist` + `load_asset` with an `isinstance` gate;
dependency sets through the asset registry (`get_dependencies`); clip length and frame
count through `AnimationLibrary.get_sequence_length` / `get_num_frames`, the same
UFUNCTIONs `bp/t1-walk-animation-footstep-cues` already grades on. **Blueprint and motion
GRAPH internals are deliberately not read**: `UBlueprint`'s graph arrays and
`UAnimBlueprintGeneratedClass::BakedStateMachines` are bare `UPROPERTY()` and so
reflection-denied to Python (readability is `CPF_Edit | CPF_BlueprintVisible |
CPF_BlueprintAssignable`, `PropertyAccessUtil.cpp:425-433`) — which is exactly why the
"a different motion actually plays" claim is made at runtime by the marker read and not
statically here.

Every check is wrapped in its own `try/except` so one wrong API name degrades to one
FAILED check with the exception in `detail`, and every failing check owns a unique ASCII
`*_MISSING` / `*_WRONG` / `*_CHANGED` token that never appears on a passing branch.
**Fail closed**: no check may pass because a probe did not raise.

## Reference solution metadata

- LOC range: **0-40** lines. The reference is asset-only and writes **0** lines of C++
  (mud detection as an overlap on the figure's graph, a max-walk-speed write, a bool
  onto the motion asset, and one added motion state). The 40 is the ceiling for a
  submission that puts the same logic in `Source/ThirdPerson/` instead — both grade
  identically.
- Files touched: 0 created, 2 modified
  (`Content/Tasks/t1-mud-wade-cpp/BP_MudHero.uasset` and
  `ABP_MudHero.uasset`).
- Senior-dev hours: 1.0-2.0 (read the supplied motion shell, add the second gait and its
  two transition conditions, wire the patch overlap to the condition and to the speed,
  confirm the ordinary locomotion is untouched, confirm it re-enters on the way back).

## Anti-gaming notes

1. **The same walk, played slower.** *Failure mode*: the agent leaves one gait in place
   and drops its playback rate (or just its speed) inside the patch, which looks
   plausible in a still frame and satisfies any speed-only gate. *Defense*: `cp1`/`cp3`
   require `HeroWadeMarker >= 0.5` — the marker only reads when the **supplied wade clip
   itself** is driving the pose, and the ordinary walk's read-only stock sources cannot
   carry it. The L2I `wade_motion_reachable` check fails a submission that never wired
   the clip up at all, and where state machines are exposed the
   `WadeState != NormalState` clause fails it a third time.
2. **Wade everywhere, or wade always.** *Failure mode*: the figure is slowed and re-gaited
   globally, or from the constructor, so the patch is never actually read. *Defense*
   three ways: `cp0` fixes the baseline `400 <= V0 <= 600` with the marker off **before**
   any mud is touched (a global change dies here); `cp2`/`cp4` require `0.85-1.15` and the
   marker off on clean ground; and the **control figure** — same class, same bytes, driven
   the same way in a lane with no mud — is gauged at **every** checkpoint for
   `TwinSpeed >= 0.70 * V0`, marker off, and `TwinActiveState == NormalState`. A global
   change cannot satisfy the control and the subject at once.
3. **A one-shot latch, in either direction.** *Failure mode (a)*: the wade fires on the
   first entry and never again. *Failure mode (b)*: it fires once and never releases, so
   the figure wades for the rest of the run. *Defense*: `cp3` is a **second** crossing and
   requires the same wade state and the same speed band as `cp1`, so (a) fails; `cp2` and
   `cp4` require the ordinary walk and full speed after each exit, so (b) fails. Both
   crossings and both exits are separately named assertions, so the discrimination matrix
   can say which half broke.
4. **Not reading the patch at all.** *Failure mode*: the agent hard-codes the lane
   coordinates (`X` between 300 and 700) or a timer instead of reading the tagged patch —
   the cheapest way to pass a positional gate. *Defense*: the **control figure's circuit
   deliberately spans the same `X` band** in a lane with no mud, so a coordinate fit slows
   the control and fails `TwinSpeed >= 0.70 * V0` at up to five checkpoints; and the
   fixture additionally asserts `|TwinY| >= 150`, so the control provably never entered the
   patch band that a correct implementation reads. A timer fit has to hit two crossings at
   asymmetric, undisclosed instants while leaving the control alone.
5. **Spoofing the observable, or the verifier.** *Failure mode*: transform or velocity
   writes timed to satisfy point samples rather than actually wading; stripping the marker
   from the supplied clip so the read cannot fire; adding a curve-override node to fake the
   marker without playing the clip; or editing the fixture, the level or the introspect
   script. *Defense*: the fixture drives locomotion itself with per-frame movement input and
   reads speed off character movement with an `!IsFalling()` guard, and every checkpoint
   *also* asserts the figure is in the positional zone it claims to be in — a velocity
   spoof that does not actually traverse 400 cm of mud twice fails those. L2I
   `wade_clip_keeps_marker` makes stripping the marker a named FAIL rather than a silent
   "not wading". The curve-override spoof has to wire the clip in (L2I), slow the figure
   (`cp1`/`cp3`), leave the control alone, AND add a node whose only purpose is to lie —
   strictly more work than implementing the gait, and where state machines are exposed the
   state clause catches it anyway; it is the contrived cheat, not the one measured in the
   wild. And `Source/CraftBenchTests/`, `Content/Maps/` and
   `tools/verify-single/introspect/` are all outside the agent's writable roots (exit-4
   sandbox reject), with the graded substrate materialized from **git HEAD** so an on-disk
   edit never reaches the grade and any committed change is review-gated on commit.

## Hidden invariants

- **The five checkpoint instants (1.6 / 3.4 / 6.4 / 8.6 / 11.4 s) are not disclosed.**
  The prompt states every threshold the grade compares the submission against — the 500
  and 200 units/second, the 40%, the 30-50% and 85-115% bands, the half-second latency,
  the 400-600 units/second clean-ground acceptance band, the control's 70% floor, the
  400 cm patch, both crossings, the control figure — but not when the samples are taken.
  A point-fit keyed to guessed instants has five independent chances to miss.
  (Two of those numbers used to be graded and NOT stated: `400 <= V0 <= 600` and
  `TwinSpeed >= 0.70 * V0`. Both are now in the prompt. The only undisclosed graded
  numbers left are the marker's `>= 0.5` threshold and the marker's name, which are
  verifier-owned by design and named under the marker invariant below.)
- **Phase membership replaces the absolute positional windows, and that is a
  correctness fix, not a tidy-up.** The earlier draft asserted `X < 250` before,
  `350 <= X <= 650` inside and `X > 800` beyond. Those windows and the mandated in-patch
  speed were **mutually unsatisfiable across cp1's own declared window**: a hero at
  `X = 350` at cp1 (t=3.4) needs `(750-350)/200 = 2.0 s` just to clear the patch, so at
  cp2 (t=4.9) it was still at `X ~= 650` and still wading — FAILing cp2 on BOTH position
  and ratio, with a correct implementation. The prompt's own permitted +/- 0.5 s
  transition latency is worth +/- 250 cm at 500 u/s, i.e. wider than the 100 cm of
  margin cp2 left past the patch exit. Each checkpoint now declares which PHASE it
  grades and requires the hero to have been settled in that phase for
  `0.5 s + one frame`; a schedule that misses reports
  `HARNESS-PRECONDITION: checkpoint <i> did not land in a settled <wade|clean> phase`
  and is a staging fault, **never** a graded FAIL. Standing still in the mud still fails,
  because the transition-latency gate needs four real boundary crossings and the
  in-patch band is a ratio of measured travel.
- **The wade clip carries a verifier-owned marker whose name is not disclosed**, and
  reading it is how "which motion is driving the pose" is observed. A correct
  implementation needs no knowledge of it: any mechanism that genuinely plays the supplied
  clip makes it read. It lives on an asset inside the writable root, so it is
  *undisclosed* rather than unreachable — see anti-gaming note 5 for why faking it costs
  more than doing the work, and `notes.md` for the hardening path if the state read turns
  out to be unavailable.
- **The control figure's class identity is asserted equal to the graded figure's**
  (`Twin->GetClass() == Hero->GetClass()`), and the level reaches it through the
  deliverable path — so the control cannot be quietly diverged into a different, unslowed
  class, and every edit the agent makes to the graded figure lands on the control too.
- **`cp3` re-asserts the SAME wade state as `cp1`**, not merely "some state other than
  normal". An implementation that enters a different gait on the second crossing, or that
  re-enters a fresh one-shot state each time, fails there while passing `cp1`.
- **The control is gauged at every checkpoint, including the two where the subject is on
  clean ground.** Its speed gate uses a `>= 0.70` floor rather than a two-sided band
  because its circuit rounds corners; the floor sits clear of the `0.30-0.50` wade
  ceiling, so the separation the check exists for is intact without a per-corner timing
  calibration.
