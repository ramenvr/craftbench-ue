# t1-mud-wade — provenance and design decisions

## Imported from

`t1-locomotion-idle-move-state` in
an internal design note (not shipped) (line 456; contract row in
an internal design note (not shipped) line 89; wave-1 entry
an internal design note (not shipped) §1 #14, plus the un-hold ruling at
§5 line 657).

The corpus row as written: *"Using the supplied character, skeleton, idle clip, move
clip, and Animation Blueprint, author the state machine so it shows idle at rest, move
while the character travels under the supplied command, and returns to idle after it
stops."* Four checks — `SuppliedClipsUsedByAuthoredStates`, `IdleAtRest`,
`MoveStateWhileMoving`, `ReturnsToIdle` — scored k/4, PASS at 4/4. Its hardening status
was `HOLD` ("narrower duplicate of `t1-animinstance-drives-state`"), and §5 rules that
hold void because the named successor is `Disposition=Archive`: both rows die in the
source list, and *the one observable nothing in the built tree measures — a live
animation state — dies with them.*

## What the owner said

From an internal working note (not shipped), item `1:t1-locomotion-idle-move-state`,
answer `fix-first`:

> "This sounds like default manny behavior with the given template. Shall we do something
> more advanced?"

The owner is right, and the whole reshape follows from it. `UE-projects/ThirdPerson/`
ships `Content/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed.uasset` plus
`BS_Idle_Walk_Run` — a complete, working idle/walk/run locomotion graph. Grading
idle → move → idle on that substrate grades a template feature, not the agent's work.

## What changed from the corpus row, and why

- **The observable is a gait the template has no equivalent of.** Normal walk → a slow
  heavy wade on a patch of mud → normal walk again, and again on the way back. Everything
  the original row was testing survives: a live read of which motion is driving the pose,
  driven by world state, using SUPPLIED assets, with the supplied normal locomotion
  preserved (L2I `normal_gait_source_retained` is the descendant of
  `SuppliedClipsUsedByAuthoredStates`). What is gone is the part that was free.
- **The trigger is walking into something, not a "supplied command".** The corpus row's
  trigger was `move under the supplied command`; the batch convention bans key presses and
  requires a walked-into trigger. The mud patch is a tagged, non-blocking, visibly dark
  slab in the lane; the fixture drives the figure onto it with the shipping per-frame
  movement-input path (`t1-overlap-teleport-portal`
  `TeleportPortalFunctionalTest.cpp:194`, `t2-ladder-climb-volume`
  `LadderClimbFunctionalTest.cpp:246`, `t2-npc-follows-player`
  `NpcFollowFunctionalTest.cpp:144`), and a human drives the same path with WASD.
- **Two firings, not one.** The corpus row fired once. The route is out-and-back, so the
  patch is crossed twice and `cp3` re-asserts the SAME wade state and the SAME speed band
  as `cp1`. This is the only thing that catches a one-shot latch, which the batch brief
  calls the most common wrong implementation in this corpus.
- **A control figure was added; the corpus row had none.** The row's Scene/Character/
  Trigger contract is the only filled one in the corpus but it contains no control. The
  control here is a second placed instance of the agent's own `BP_MudHero`, on a parallel
  mud-free lane whose circuit deliberately spans the SAME `X` band as the mud, gauged at
  every checkpoint. That one addition kills three cheats at once (global slowdown, global
  re-gait, hard-coded lane coordinates) and its class identity is asserted equal to the
  graded figure's so it cannot be diverged.
- **Speed is a graded observable, not just the gait.** §1 #14 says to graft the held
  animbp rows' "rising-and-falling curve sample". The equivalent here, and the reason the
  brief asks for it, is that the two gaits are separable by MEASUREMENT as well as by
  name: 40% of normal top speed (200 of 500 units/second), gated as a ratio against the
  run's OWN measured baseline, twice. If the live state read turns out unavailable the
  task still grades something real.
- **Tier stays T1** (matching the id prefix): the motion shell ships already working and
  the clip is supplied, so the work is one added gait plus one world-state condition —
  1.0-2.0 senior-dev hours, inside T1's 30 min-2 h band. `capability_bucket` is
  **Technical Art**, which is where `anim-state-machine` sits in
  `tools/coverage/concepts.csv`; `category: animation` (in `tasklint`'s
  `_CATEGORY_ENUM`).
- **`deliverable_root:` was REJECTED and is not in the front matter.**
  `tools/verify-single/spec.py::_KNOWN_KEYS` has 15 keys and raises
  `ValueError: unknown front matter key(s) ... deliverable_root` — verified by running the
  real parser on this spec's own front matter with and without the key, so it is exit 2
  "spec malformed", not a graded FAIL. Per the batch convention the deliverable root is
  the first line of `## Workspace state pre-task` and is restated in the prompt body.
  `tasks/README.md` used to assert the key is carried in front matter,
  which was false for every spec in this set. **The README was corrected 2026-08-17** — it
  now states the two-agent-visible-prose-mentions rule that every spec here actually
  follows, and records that adding the key requires extending `_KNOWN_KEYS` first.
- **Heading is `## Workspace state pre-task`, not `## Workspace pre-state`.** The batch
  brief names the latter; `tasklint._CANONICAL_H2_ORDER` and
  `docs/AUTHORING_TEMPLATE.md` both fix the former, and the brief also says to copy the
  template's H2s verbatim. The template wins.
- **`layers: [L1, L2, L2I]` — NOT first-of-kind. Corrected 2026-08-17.** Six shipped
  specs already declare all three (`bp/gp-dot-aoe-burn-bp`,
  `bp/gp-double-jump-stamina-bp`, `bp/gp-glide-stamina-bp`, `bp/gp-heal-over-time-bp`,
  `bp/gp-health-attribute-ops-bp`, `bp/gp-poison-dot-stack-bp` — measured with
  `grep -l 'layers: \[L1, L2, L2I\]' tasks/*/*/task.md`), and they are refgate-PASSing,
  so the combination is exercised, not novel. An earlier version of this line called it
  first-of-kind and flagged it as a risk; that inflated the risk and should not be
  carried into the build brief. Structurally it is also clean: in `layers/registry.py`
  both depend only on `L1` (`L2` order 20, `L2I` order 30, neither in the other's
  `requires`), so both run and both gate.

## The risk the brief names, and how the design de-fangs it

**The live animation-state read has never run headless in this repo.**
`docs/pie-verification-playbook.md` is explicit: the anim-state read is a SPIKE
(§ picker row `pie-state-probe`; the AnimBP archetype row says that if the spike fails,
"this archetype has **NO non-gameable gate**"). So:

- **Run the 30-minute probe BEFORE writing the fixture.** Route:
  `IAnimClassInterface::GetFromClass(AnimInstance->GetClass())` →
  `GetBakedStateMachines()`; then `AnimInstance->GetStateMachineInstance(i)` →
  `GetCurrentState()` (an `int32` index), mapped back through
  `FBakedAnimationStateMachine::States[idx].StateName`
  (`Animation/AnimStateMachineTypes.h`). Guard `GetStateMachineInstance` for `nullptr`.
  Expect a possible one-frame staleness (anim update may be off the game thread); that is
  inside every tolerance here.
- **NEVER `UAnimInstance::GetCurrentStateName(int32)` — it segfaults.** Do not use it as a
  convenience wrapper, not even for the log line.
- **The gate does not depend on the probe landing.** The primary read of "which motion is
  driving the pose" is a **marker curve on the supplied `A_MudWade`**, read with
  `UAnimInstance::GetCurveValue` — a stock, long-proven API, no spike. It is also
  **route-independent**, which the state read is not: a state-identity gate would FAIL a
  legitimate blend-node or linked-layer answer, which breaks the batch's rule 6 ("never
  write a clause that FAILs a legitimate alternative implementation"). The state-read
  clauses are therefore marked *(when available)* and skip, logged as
  `state=unavailable`, when a submission's motion asset exposes no baked state machine.
- **Residual risk, stated honestly.** The marker is spoofable in principle by a
  curve-override node that fakes it without playing the clip. Defences are stacked (L2I
  requires the clip wired in; `cp1`/`cp3` require the slowdown; the control must stay
  fast; the state clause catches it when available) and the spoof is strictly more work
  than the correct solution — the same calibration
  `CraftBenchPawnFunctionalTest.h` applies to the "1 cm cube technically passes" case.
  **If the state-read probe FAILS, harden the marker rather than shipping it alone**: add
  a calibrated pose signature (e.g. pelvis height relative to the actor, or the head
  bone's vertical range, sampled from the reference run and banded in `notes.md`), which
  no curve node can fake. Decide that before the fixture ships, not after.

## Build-time decisions left open, with the default

- **Which stock clip `A_MudWade` is duplicated from.** Requirements: same mannequin
  skeleton, looping, forward locomotion, visibly a different gait from
  `MF_Unarmed_Walk_Fwd` at a glance, and NOT a retimed copy of it. There is no
  purpose-made trudge clip in `Content/Characters/Mannequins/Anims/` (no crouch-walk in
  the 5.8 template pool — the whole list was checked). **Default:
  `/Game/Characters/Mannequins/Anims/Rifle/Walk/MF_Rifle_Walk_Fwd`** — note the
  `Rifle/Walk/` subfolder; an earlier version of this line wrote the path as
  `Anims/Rifle/MF_Rifle_Walk_Fwd`, which does not resolve. The arms-carried-high
  silhouette is unmistakably a different gait, it loops, and it is on the same skeleton;
  the phantom-weapon look is a cosmetic caveat worth accepting over a broken-looking
  strafe or backward clip. If a real heavy-trudge clip can be sourced, prefer it and
  record the substitution here. (The old `wade_clip_unmodified` check read a
  length/frame oracle LIVE off whichever deny-listed stock path was used; that check is
  **gone** — it forbade retiming or re-looping the supplied clip, which the prompt never
  rules out and which is a plausible legitimate answer. `wade_clip_still_a_clip`
  replaces it and only requires a non-degenerate forward-locomotion sequence, so the
  stock path is no longer a grading oracle at all.)
- **Duplicate vs hand-author for `ABP_MudHero`.** Default is a duplicate of the read-only
  `ABP_Unarmed`. Inspect it first: if 5.8's version turns out to be layered or otherwise
  awkward to add a state to, hand-author a simple shell instead (one state machine, idle
  + walk off `BS_Idle_Walk_Run`) — which is closer to the corpus row's "AnimBP shell"
  anyway. The invariant either way is that the shell **already produces a correct
  ordinary locomotion as shipped**, so the grade measures the agent's addition.
- **All five checkpoint instants and both figures' route geometry are CALIBRATION
  TARGETS, not measurements.** The numbers in the spec
  (`{1.6, 3.4, 4.9, 7.6, 9.4}`, the hero's turn mark at `X = 1100`, the positional
  windows `X < 250` / `350-650` / `X > 800`, the control's circuit
  `X ∈ [-400, 800] × Y ∈ [200, 600]`) were derived from the template's ground movement
  (top speed 500, `MaxAcceleration` 2048, `BrakingDecelerationWalking` 2000, rotation
  rate 500°/s) and from a 400 cm patch at 200 units/second. **Confirm every one against a
  reference run's `[mud-wade calib]` log line and record the measured values here before
  MATRIX.md.** The two that matter most: the figure must genuinely be mid-patch at `cp1`
  and `cp3` with speed settled, and the control must be in steady travel (rounded
  corners, never stopping, never reversing) at all five.
- **`cameras.json` (the camera-plan lane; not part of this release).** Not authored here (output discipline: this change ships `task.md`
  and `notes.md` only). It must frame subject + control + at least four 200 cm stripes
  with the mud patch in frame at every shot, and the two backdrop landmark posts visible
  so a still camera is distinguishable from a moving one.

## What still needs building

Everything below is `/craftbench-build-verifier`'s work; none of it exists yet.

1. **Level** — `UE-projects/ThirdPerson/Content/Maps/L_MudLane.umap`,
   committed binary (the only map source; a missing binary is an explicit L2 FAIL and a
   `cb lint` error). Contents per *Workspace state pre-task*: striped floor, off-origin
   player start, the tagged `MudPatch` slab, the placed `MudTwin` instance of
   `/Game/Tasks/<id>/BP_MudHero`, two backdrop landmark posts, the fixture, and the
   readout actor. World settings select `AMudHeroGameMode`.
   **The basename `L_MudLane` is unique repo-wide.** (Corrected 2026-08-17: an earlier
   draft of this file claimed other tasks in the batch shared this map name. They did
   not — no other spec ever declared `L_AnimLane`, this task's previous name. The map
   was renamed `L_AnimLane` → `L_MudLane` for a different reason: "AnimLane" names the
   mechanism, and the map path is agent-visible via `Workspace state pre-task`. The
   real duplicate-basename groups in this batch were `L_ContactLane` ×3, `L_NavYard`
   ×3, `L_RenderLane` ×2 and `L_CollectArena` ×2, all resolved by rename the same day
   — a shared basename is exit 7 HARNESS-ERROR via
   `map_locator.DuplicateMapBasenameError`, and per-task folders do not isolate it.)
2. **Scaffold C++** — `Source/ThirdPerson/Tasks/t1-mud-wade-cpp/`:
   `MudHeroCharacter.{h,cpp}` (concrete subclass of the stock abstract playable
   character, tag `MudHero`, no mud logic) and `MudHeroGameMode.{h,cpp}` (default pawn
   resolves to `/Game/Tasks/<id>/BP_MudHero`, falling back to `AMudHeroCharacter`).
   **The fallback matters**: without it a level that cannot find the deliverable spawns
   nothing and the run reads as a model failure.
3. **Supplied content** — `Content/Tasks/t1-mud-wade-cpp/`:
   `BP_MudHero.uasset` (mannequin mesh from the read-only pool + `ABP_MudHero` as its
   motion asset, no mud logic), `ABP_MudHero.uasset` (working ordinary locomotion, no
   wade), `A_MudWade.uasset` (the supplied clip + the marker curve added across its full
   length via `AnimationLibrary`).
4. **L2 fixture** — `Source/CraftBenchTests/Tasks/t1-mud-wade-cpp/MudWadeGaitFunctionalTest.{h,cpp}`,
   deriving `ACraftBenchFunctionalTest`. It carries its own local control-figure
   possessor and its own local visible-mesh predicate; the base classes
   (`CraftBenchFunctionalTest.h`, `CraftBenchPawnFunctionalTest.h`) are **not** to be
   edited — they are owned by the other machine, `SpawnAndPossessPawn()` handles exactly
   one pawn, and the duplication is owner-approved.
5. **Readout actor** — same folder: floating text above each figure showing its measured
   ground speed and its gait as the verifier reads it, so a human hitting Play sees the
   same numbers the grade uses, in a module the agent cannot write to. Assert-free; it
   must never reach a verdict and must not emit Warnings inside the test window.
6. **L2I script** — `tools/verify-single/introspect/mud_wade_gait.py`, exactly 8 named
   checks on every leg, constant denominator, fail-closed, unique ASCII failure tokens,
   and no occurrence of either automation result marker (`"TestResult"` + `"=Passed"`, or
   `"Automation Test"` + `" Succeeded"`) anywhere in the file including its docstring —
   `parse_automation_log` counts those as tests and a stray one flips the leg count.
7. **Reference solution** — `reference/`, asset-only, mirroring
   `Content/Tasks/t1-mud-wade-cpp/`.
8. **Discrimination** — `discrimination/` plus `discrimination/MATRIX.md` carrying a
   `## Requirements table` (mandatory since 2026-08-11; `tasklint`'s
   `matrix-requirements-table` rule keys on that literal heading) mapping every prompt
   requirement to the assertion that checks it AND to the condition under which that gate
   is skipped — the state-read clauses' *(when available)* skip is exactly such a row and
   must appear. Beyond the automatic reference-PASS / empty-FAIL legs, the variants worth
   hand-authoring are the ones the requirements table cannot cover by inspection:
   `slower-same-clip` (marker off), `global-slowdown` (control fails), `latched-once`
   (`cp3` fails), `hardcoded-x-band` (control fails), `marker-stripped`
   (`wade_clip_keeps_marker` fails).
9. **Close the loop** — `cb refgate cpp/t1-mud-wade-cpp`
   must grade the committed reference PASS. Note the certificate key covers the substrate
   tree and the verifier tree as well as the task tree, so adding the scaffold and the
   fixture invalidates every existing certificate — expect a full re-gate.

## One known set-level gap (not this task's to fix)

the corpus-ledger tool (since removed) iterates the three basket names literally, so
every task in `tasks/craftbench-public/` is invisible to the generated review page until
`"craftbench-public"` is added to that tuple. It does not turn CI red.


## Deviations from the spec as written (2026-08-18, all recorded before building)

1. **The L2I layer was dropped, and the front matter now reads `[L1, L2]`.** The spec
   declared `mud_wade_gait.py` for "the static asset structure that runtime cannot
   see" -- i.e. an inspection of the animation blueprint. But the prompt itself says
   `Source/ThirdPerson/` is equally acceptable "if you would rather put the gameplay
   logic in code", and a code-route answer has NO animation blueprint to inspect. A
   static structural check would therefore have failed a legitimate submission for
   taking a route the prompt explicitly offers. What that check was for is covered at
   runtime instead: `WadeDrivesPose` asks the MESH what is driving it and accepts
   either a single-node player or an animation blueprint, so both routes are graded
   the same way and neither is preferred.
2. **The fixture is `AMudWadeFunctionalTest`, not `AMudWadeGaitFunctionalTest`.**
   Name only.
3. **The wade clip is supplied by duplication, not authored.**
   `Content/Tasks/<id>/A_MudWade` is a duplicate of `MF_Pistol_Walk_Fwd` -- a visibly
   different gait that already ships in the substrate. That keeps the task free of any
   new asset dependency, and the clip is supplied content either way: what the agent
   builds is deciding WHEN it drives the pose.

### Two calibrations the run forced, both about the fixture's own drive

- **Turn grace, 1.5 s.** Both figures reverse at their waypoints, and a turn is a real
  slowdown the FIXTURE caused. Judging through one read the graded figure at 388 of
  500 and the control at 68% of the floor -- both correct answers, failed by the
  drive. Neither gate is judged within 1.5 s of a turn.
- **Entering and leaving get DIFFERENT windows.** Entering is judged at the half
  second the prompt states; leaving gets 1.2 s. Entering is a deceleration (~0.15 s)
  plus the fixture's smoothing (~0.1 s), so half a second is comfortable -- and it
  MUST stay at half a second, because at full speed the figure clears the 400 cm patch
  in 0.8 s, so a wider window never lands on the patch at all and the substantive gate
  silently never runs. Leaving is an acceleration with no dwell limit, so it can
  afford the longer window; measured, the same correct answer read 388 at 0.5 s and
  500 at 1.2 s.
