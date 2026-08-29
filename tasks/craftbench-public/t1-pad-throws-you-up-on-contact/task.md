---
id: t1-pad-throws-you-up-on-contact
substrate: ThirdPerson
set: craftbench-public
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_PadLane :: APadContactLaunchFunctionalTest"]
---

# t1-pad-throws-you-up-on-contact

A pad set flush into a striped floor does nothing until the character steps on
it, then throws it straight up: it rises, hangs at the top, falls back under
gravity, and lands. Walking off and back on throws it again, to the same
height. Twenty centimetres clear of the pad's edge an identical second
character stands and is never driven anywhere; it must be on the ground at its
own starting height at every checkpoint of the run.

Both drivers see the same thing. The verifier walks the player character onto
the pad with the shipping per-frame movement-input timeline
(`Tasks/t1-overlap-teleport-portal/TeleportPortalFunctionalTest.cpp:194`,
`Tasks/t2-ladder-climb-volume/LadderClimbFunctionalTest.cpp:246`,
`Tasks/t2-npc-follows-player/NpcFollowFunctionalTest.cpp:144`); a human hits
Play and walks the same path with WASD, because the map's game mode possesses
the same stock third-person character at the PlayerStart. No key press is
graded anywhere in this task — the trigger is walking into something.

The corpus row this came from left the minimum apex height and the landing
deadline as fixture-internal literals. Both are now in the prompt, along with
every other number the grade depends on. See `notes.md`.

## Primary concept

- `collision-overview` — Collision Overview
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine---overview)

The load-bearing behaviour is an overlap-gated impulse: the pad is inert until
a runtime contact edge occurs on its volume, fires once per contact, and fires
again on a fresh contact. That contact causation is what separates a correct
answer from the three wrong ones the corpus row names (throw at play-start,
permanent lift, teleport-to-height) — all three produce upward displacement,
and only the contact gate tells them apart. The arc itself is character
movement (`movement-components`), which the verifier reads but does not
require any particular route to produce.

## Prompt given to the agent

> A square pad is set flush into the striped floor of this level. Right now it
> does nothing. Make it throw the character straight up whenever the character
> walks onto it. A marked post beside the pad carries a bright band at the
> 300 cm line, so you can see from the level whether a throw cleared it.
>
> Write your work in C++ under `Source/ThirdPerson/`. That is the only place
> your changes are read from.
>
> - When play begins, and for as long as nobody is on the pad, the pad does
>   nothing. The character stays on the ground at the height it starts at,
>   within 10 cm.
> - When the character walks onto the pad it is thrown upward. It must rise at
>   least **300 cm** above the height it was standing at, reach a highest
>   point, fall back down under the level's own gravity, and be standing on
>   the ground again no more than **4.0 seconds** after it touched the pad.
>   The whole trip must be at least **1.0 second** off the ground: a jump to
>   the top and an instant drop back is not a throw.
> - One touch is one throw. From the moment the character leaves the pad until
>   it is standing again it must not gain height a second time in mid-air —
>   gaining more than 50 cm again before it lands is a failure.
> - Walking off the pad and back onto it throws the character again. **Every**
>   throw in the run must meet the numbers above; the pad must not be a
>   one-time trick, and the second throw is not held to a weaker bar than the
>   first.
> - A second character stands 20 cm clear of the pad's edge and is never
>   driven anywhere. It must stay on the ground at its own starting height,
>   within 10 cm, for the whole run. The pad throws only what is actually on
>   it.
>
> Do not move either character by writing its position or its height
> directly, and do not fake the flight — the rise and the fall have to be real
> movement that the level's gravity brings back down. Do not edit the level,
> the characters, any settings file, or any test file.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`.** Every file you submit must live
under that path — it is the only agent-writable code module on this project.
There is no `Source/CraftBenchTemplate/` here; writing there is rejected
before grading. Also read-only: `Source/CraftBenchTests/`, `Content/Maps/`,
`Content/Characters/`, `Content/ThirdPerson/`, `Content/Input/`, `Config/`,
`Plugins/`, and the `.uproject`.

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources (`ThirdPersonCharacter`
  with its `DoMove`/`DoJumpStart`/`DoJumpEnd` seams, the player controller,
  the game mode, the `Variant_*` trees). No edit needed.
- `Tasks/t1-pad-throws-you-up-on-contact/ContactPadActor.h` / `.cpp` —
  declares and defines `class THIRDPERSON_API AContactPadActor : public
  AActor`. What ships: a visible 400 x 400 x 20 cm plate as the root, flush
  with the floor; a 400 x 400 x 500 cm box-shaped region standing on the plate
  that already **notices** anything entering or leaving it and does not block
  anything walking through it; and `Tags.Add(FName("ContactPad"))` in the
  constructor. **Nothing in the project reacts to anything touching the pad, and
  nothing anywhere moves a character up.** The
  behaviour is entirely yours — on this class, on a subclass, or anywhere else
  under `Source/ThirdPerson/`. The plate and the volume are the pad a placed
  instance of this class already puts in the level; you may resize or re-shape
  them if your answer needs it, but the graded pad is the placed instance of
  this class.

Content that **exists** and is read-only:

- `Content/Maps/t1-pad-throws-you-up-on-contact/L_PadLane.umap` — the
  staged level. A 3600 x 1400 cm floor plate with its top surface at Z = 0,
  striped with marker bands every 200 cm across the lane so distance and speed
  are readable by eye. One placed `AContactPadActor` centred on the world
  origin (its plate edges therefore at X = +/-200 and Y = +/-200). A
  PlayerStart at (-700, 0, 92) facing +X — three stripes back from the pad,
  off the world origin, looking at the pad. A **painted floor mark** 20 cm clear
  of the pad's -Y edge, at (0, -254), where the second character stands — the
  character itself is **not placed in the map**; the test spawns and possesses it
  on that mark at the start of every run, so exactly one body ever occupies that
  spot (see the verifier section: two capsules at one location is how a
  "the bystander stayed put" gate false-FAILs). A striped height post at (0, +300) with bands
  every 100 cm up to 600 cm and a bright band at exactly 300 cm. A far mark on
  the floor at X = +800. Two visually distinct landmark posts at the ends of
  the backdrop, X = -1300 and X = +2100, so a moving camera is
  distinguishable from a still one. The map's world settings select the stock
  `BP_ThirdPersonGameMode`, so hitting Play possesses the stock mannequin
  character at the PlayerStart and WASD walks it onto the pad.
- `Content/Characters/Mannequins/` — the mannequin skeletal meshes and
  animations both characters are represented by.

Files that **do not exist**:

- Nothing anywhere in the project responds to a character reaching the pad, and
  nothing anywhere sends a character upward or remembers that it has. The
  unmodified scaffold compiles, so an empty submission is L1-green and FAILs L2
  at the named throw gate.
- No test source in the agent's writable path. `APadContactLaunchFunctionalTest`
  lives in the `CraftBenchTests` module, which the agent can neither read nor
  modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t1-pad-throws-you-up-on-contact/L_PadLane.umap` on the
**ThirdPerson** substrate, at a fixed deterministic step
(`-deterministic -FPS=60`). Verification primitive:
**pie-checkpoint-sampling** with dense per-tick trajectory recording, plus
**pie-state-probe** for the grounded/airborne read
(`GetCharacterMovement()->MovementMode`, `GetVelocity()`) — the two primitives
already proven on this substrate by the glide, double-jump and teleport-portal
fixtures.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
        (short-circuits on the first failure)
```

**There is no second L1 assert, deliberately.** An earlier draft carried
`no new shadowed-variable / deprecated-declarations warnings in the agent-touched
compilation units`, and that was wrong twice over. Measured:
`run_task.py:1035` makes `--strict-warnings` an `action="store_true"` that is
**off by default**, and no `aura_rig` path passes it (`grep -rn strict.warnings
tools/run-agent/aura_rig/` → 0 hits), so on `cb eval` / `cb refgate` the assert
would never have run at all — a dead gate an empty submission passes. And when it
*does* run, `layers/registry.py:100` is `l1.warning_count_agent_files > 0`: **any**
warning in an agent-writable file, with no shadowed/deprecated type filter and no
"new-since-baseline" comparison. Neither the flag nor the warning rule is stated in
the prompt, so gating on it would also be an undisclosed grade-bearing condition.
The gate is therefore removed rather than described: L1 here is exactly the two
UBT targets.

### L2 — AFunctionalTest behavioural trace

**Base class: `ACraftBenchFunctionalTest`, not `ACraftBenchPawnFunctionalTest`.**
This is deliberate and the implementor should not "fix" it. The pawn base's
`SpawnAndPossessPawn()` resolves the graded body through
`ResolveAgentPawnClass()`, which calls
`GetDerivedClasses(ACraftBenchCharacter::StaticClass(), …, bRecursive=true)`
over the whole loaded module and takes the first non-abstract native subclass
(`CraftBenchPawnFunctionalTest.cpp:73-103`). Every other task's committed pawn
is in that module, so this task — whose deliverable is a pad, not a pawn, and
which therefore supplies no pawn subclass to prefer — could have a foreign
task's pawn (a glider, a double-jumper) become its graded body and change the
arc. The subject here is instead the stock third-person character the map's
game mode possesses at the PlayerStart, resolved with
`UGameplayStatics::GetPlayerCharacter(World, 0)`. The three motion reductions
this fixture needs (`RoseThenFell`, air-interval extraction, second-rise
detection) are re-implemented locally over the fixture's own dense sample
series; they are short, and the base's versions are keyed to `Pawn`.

**The control twin is spawned by this fixture's own local spawner**, duplicated
per task. The owner has explicitly approved the duplication: the base class has
no API for a second subject and adding one is the other machine's change — do
not go looking for a shared helper. The twin is spawned from the same read-only
class the game mode uses (`/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter`,
loaded by soft path) so it is an *identical* twin, and it is possessed with
`SpawnDefaultController()`. **Possession is mandatory and load-bearing**: an
unpossessed `ACharacter` is inert (`MOVE_None`, no gravity — the Slice-0 spike),
so a "the twin stays on the ground" gate on an unpossessed twin measures
nothing at all and would pass for any pad whatsoever. The fixture FAILs by name
if the twin's movement mode is not `MOVE_Walking` at cp0.

**Presentation, assert-free.** The fixture attaches a `UTextRenderComponent`
above each character showing that character's current height above its own
start, its peak so far, and its current air time in seconds, so every number
the grade depends on has an on-screen readout. Purely advisory — the capture
and preview legs render it, the certified headless `-nullrhi` leg ignores it,
and it can never flip PASS/FAIL.

```text
APadContactLaunchFunctionalTest (derives ACraftBenchFunctionalTest):

  PrepareTest():
    Super::PrepareTest()                          // base: fixed dt, PIE lever
    Pad     = single actor tagged "ContactPad"    // identity by TAG, never class
                                                  // (named FAIL if count != 1)
    Subject = GetPlayerCharacter(World, 0)        // possessed by the map's game mode
    Twin    = spawn BP_ThirdPersonCharacter at (0, -254, 92); SpawnDefaultController()
              // 254 = pad edge 200 + capsule radius 34 + the disclosed 20 cm clear
    assert Subject and Twin are both MOVE_Walking and both visibly meshed
    SubjectBaseZ = Subject Z after settle;  TwinBaseZ = Twin Z after settle
    attach the two text readouts (presentation only)
    SetCheckpointSchedule({ 0.6, 2.9, 6.6, 8.8, 13.2 })

  Tick (every frame, AFTER Super::Tick so the base clock owns the checkpoints):
    record (t, Z, vZ, MovementMode) for Subject and for Twin   // dense series
    if driving: Subject->AddMovementInput(DriveDir, 1.0)       // per-frame, as WASD does
    CONTINUOUS off-pad guard (armed cp0 -> end):
      if an air interval OPENS while the Subject's footprint is not inside the
      pad's volume, and it did not leave that volume within the previous 0.25 s
        -> FAIL "PadInertBeforeContact" / "the character was thrown while it was
           not on the pad"
      [This replaces the old pre-contact-only guard. It is armed for the WHOLE
       run, so an unconditional or timed throw is caught wherever it happens,
       and it is keyed to CONTACT, never to an interval ordinal.]
    CONTINUOUS control guard (armed cp0 -> end):
      if |Twin Z - TwinBaseZ| > 10  -> FAIL "ControlStaysGroundedThroughout"

  OnCheckpoint(i):
    cp0 t=0.6   Subject settled, grounded, |Z - SubjectBaseZ| <= 10; Twin same.
                No air interval has opened.        -> gauges 1 and 7
                Start driving +X toward the pad.   // contact expected ~2.1s
    cp1 t=2.9   ~0.8s after contact: Subject is OFF the ground and above
                SubjectBaseZ.                     -> gauge 2; Twin gauged
    cp2 t=6.6   THROW(1) — the air interval opened by contact event #1 — is
                closed and compliant: peak - SubjectBaseZ >= 300; airborne for
                >= 1.0 s; grounded again within 4.0 s of contact event #1;
                exactly one >50 cm rise inside that interval.
                                                  -> gauges 3, 3b, 4, 5; Twin gauged
                Retarget the drive to the far mark X = +800; stop on arrival.
    cp3 t=8.8   Subject grounded, and its footprint is entirely outside the pad
                volume (pad half-extent 200 + capsule radius 34 = 234, so
                |X| > 234 or |Y| > 234 — a measured consequence of the disclosed
                pad size, not a threshold of its own; the drive has in fact
                carried it to X ~ 800).           -> Twin gauged
                NOTHING here counts intervals. Whether the subject bounced back
                onto the pad between cp2 and cp3 and was thrown again is
                irrelevant: that is a fresh contact and legal. What forbids an
                uncaused throw is the continuous off-pad guard above, which is
                armed the whole time.
                Reverse the drive toward the pad.  // contact #2 expected ~10.2s
    cp4 t=13.2  At least TWO distinct contact events have occurred, and THROW(2)
                — the air interval opened by the LAST contact event before cp4 —
                satisfies the SAME four floors as THROW(1) (>= 300 cm, >= 1.0 s
                airborne, grounded within 4.0 s, exactly one >50 cm rise).
                                                  -> gauge 6; Twin gauged
                [Keyed to contact EVENTS, not to interval index. An
                 intermediate bounce shifts every ordinal but adds a contact
                 event of its own, and the LAST one before cp4 is always the
                 walk-back-on the checkpoint means to grade.]
                -> FinishTest(Succeeded)

  every checkpoint logs
    "[t1-pad calib] cp<i> t=<t> z=<z> dz=<z-base> vz=<vz> mode=<m> x=<x>
                    twindz=<tz-tbase> intervals=<n> peak=<p> air=<a>"
    (LogTemp/Display) for tolerance calibration and for reading a wrong
    decomposition instead of silently mis-gating on it.
```

**Definitions the gates share.** An *air interval* is a maximal run of
consecutive dense samples in which the subject's movement mode is not a
grounded mode; its *peak* is the maximum Z over the interval. Its *duration* is
measured **ground-departure to ground-contact** — from the last grounded sample
before the interval to the first grounded sample after it — not
last-airborne-sample minus first-airborne-sample. That matters: at `-FPS=60` the
sample-to-sample form undercounts a true flight by up to one frame (16.7 ms), so a
genuine 1.000 s flight measures 0.983 s and misses the **disclosed** `>= 1.0 s`
floor. The departure-to-contact form brackets the real flight and can only ever
over-count, never under-count, a correct throw.

A *rise* inside an interval is a monotone upward run of **more than 50 cm**
(strictly greater, matching the prompt's "gaining more than 50 cm again"; an
exactly-50.0 cm re-gain is legal by the prompt and must not be counted as a
rise). It absorbs air-control jitter and the settle frame while catching a real
second throw.

A *contact event* is a sample at which an air interval opens while the subject's
footprint is inside the pad's volume. Contact events, not interval ordinals, are
what the gates key on — see cp3 and cp4.

**Robust to both correct shapes.** A throw that preserves horizontal speed
carries the subject forward and it lands past the pad; a throw that zeroes
horizontal speed drops it back onto the pad, and if it re-triggers there that
is a *fresh contact* and is legal under the prompt. Both produce air intervals
that each satisfy the same floors, so both PASS. **Nothing in the gate set counts
intervals to an exact number, forbids a bounce, keys on an interval index, or
names a route** — an earlier draft's cp3 ("no new air interval has opened since
landing #1") and cp4 ("air interval #2") did exactly that and would have FAILed
the zero-horizontal-speed shape this paragraph declares legal.

### Named assertions

Eight gates. Five come from the corpus row (its checks 4 and 5 collapsed into
one, per the review note); two are this batch's mandatory additions; and the
air-time floor is split back out of gate 3 into gate 3b.

| # | Named assertion | Corpus check | Gauged at |
|---|---|---|---|
| 1 | `PadInertBeforeContact` | 1 | cp0 + the continuous off-pad guard, armed for the whole run |
| 2 | `ContactThrowsSubjectUp` | 2 | cp1 |
| 3 | `RisesThenFallsUnderGravity` | 4 + 5 (collapsed) | cp2, cp4 — the 300 cm apex and peak-then-descend only |
| 3b | `StaysOffTheGroundLongEnough` | 4 + 5 (split back out) | cp2, cp4 — the `>= 1.0 s` air-time floor alone |
| 4 | `LandsBackOnTheGround` | 6 | cp2, cp4 |
| 5 | `OneThrowPerContact` | 3 | cp2, cp4 |
| 6 | `SecondContactThrowsAgain` | new (batch rule 5) | cp4 (the second contact EVENT exists at all) |
| 7 | `ControlStaysGroundedThroughout` | new (batch rule 2) | cp0–cp4 + continuous guard |

**Why 3b is split back out.** Collapsing 4 and 5 was the review's instruction and
stands — but folding the air-time floor in with the apex made a 250 cm honest
launch and a set-Z-then-drop spoof produce the identical failure string, and it
made the planned discrimination variant *set-Z-then-let-gravity* (which must FAIL
on air time, not on apex) unable to prove it failed for the intended reason. The
split costs nothing: same measurements, two literals.

### Requirement-to-gate table

Every requirement stated in the prompt, the gate that checks it, and the one
condition under which that gate does not run.

| Prompt requirement | Gate | Skipped when |
|---|---|---|
| Pad does nothing while nobody is on it; character within 10 cm of start height | 1 (cp0 + the continuous off-pad guard, armed cp0→end) | never — the guard is per-frame for the whole run |
| Throw on walking onto the pad | 2 (cp1) | never |
| Rise >= 300 cm above standing height | 3 (cp2, cp4) | if cp1 already FAILed (no air interval to measure) |
| Reaches a top, then falls under gravity | 3 (cp2, cp4 — peak-then-descend) | as above |
| At least 1.0 s off the ground | 3b (cp2, cp4 — its OWN literal) | as above |
| Standing again within 4.0 s of contact | 4 (cp2, cp4) | as above |
| One touch is one throw; no >50 cm mid-air re-gain | 5 (cp2, cp4) | as above |
| Walking off and back on throws again | 6 (cp4 — a second contact event exists) | if cp2 FAILed |
| Second throw held to the same numbers | 3 / 3b / 4 / 5 re-run at cp4 against THROW(2) | as above |
| Second character stays grounded within 10 cm | 7 (cp0–cp4 + continuous guard) | never |
| No direct position/height writes; the flight is real | 3b (a 1-frame snap has ~0 s air time and cannot satisfy >= 1.0 s) | as above |
| Do not edit the level / character / config / tests | sandbox deny prefixes + git-HEAD substrate provenance | never (pre-grade, exit 4) |

**Pass criteria**: both L1 targets green and all eight L2 gates green.
**Robust identity**: the pad by its `ContactPad` tag, never by class — a
subclassed or renamed pad inherits the constructor-stamped tag; the subject via
`GetPlayerCharacter`, so the graded body is whatever the map's game mode
possesses.

## Reference solution metadata

- LOC range: 25-60 (header: an overlap-handler declaration and the throw
  constants; cpp: bind the volume's begin-overlap delegate, filter to a
  character, apply the upward impulse once per contact edge)
- Files touched: 2 (both pre-existing scaffold files:
  `ContactPadActor.{h,cpp}`)
- Senior-dev hours: 0.5-1.0

## Anti-gaming notes

1. **Empty / partial submission.** *Failure mode*: the scaffold compiles with
   no overlap handling at all, so L1 is green. *Defense*: cp1 asserts the
   subject is off the ground and above its baseline ~0.8 s after contact and
   FAILs by the named message `ContactThrowsSubjectUp` — FAIL-on-empty, not
   differs-from-reference.
2. **A rise that was not caused by the pad, or is not a real flight.** *Failure
   modes*: the lift is applied unconditionally when play begins or on a timer;
   the pad holds the character up forever; or the character's Z is written to
   +350 and gravity returns it, or it is snapped up and snapped back.
   *Defense*: cp0 asserts the subject is grounded within 10 cm of its start
   height before any contact, and the **continuous off-pad guard is armed for
   the whole run** — any air interval that opens while the footprint is not on
   the pad FAILs by name, so there is no window a timed unconditional lift can
   hide in. `LandsBackOnTheGround` kills the permanent lift at contact + 4.0 s.
   For the fake flight, gate 3b's air-time floor is **1.0 s**: a 300 cm free
   fall alone is 0.78 s and a snap-up-snap-down is one or two frames — neither
   clears it. Every number here is disclosed, so a correct implementation is
   never surprised by one.
3. **Fires the wrong number of times per contact.** *Failure modes*: a
   `bHasFired` flag that never resets (the most common wrong answer in this
   corpus), or the opposite — the lift re-applied every frame the character is
   inside the volume, so it hovers or stair-steps upward. *Defense*: the run
   walks the subject off the pad to the far mark and back on, and gate 6
   requires a **second contact event** with a throw meeting the *same* four
   floors as the first; a latch produces no second throw at all. In the other
   direction `OneThrowPerContact` requires exactly one >50 cm rise inside each
   throw's air interval, and `LandsBackOnTheGround` catches the hover
   independently. Both gates key on contact events, never on interval index, so
   a legal bounce back onto the pad cannot be mistaken for either fault.
4. **Throw everything nearby.** *Failure mode*: a radius or distance test
   instead of the pad's own footprint, so anything standing near the pad goes
   up too. *Defense*: the identical control twin stands 20 cm clear of the
   pad's edge — deliberately tight — is possessed so its movement component
   and gravity are genuinely live, and is gauged at **every** checkpoint plus
   per frame; `ControlStaysGroundedThroughout` FAILs on 10 cm of lift.
5. **Test disabling / environment repointing.** *Failure mode*: edit the
   fixture, the map, the mannequin character, or a config file to weaken the
   gate. *Defense*: `Source/CraftBenchTests/`, `Content/Maps/`,
   `Content/Characters/`, `Content/ThirdPerson/` and `Plugins/` are
   sandbox-denied (submission files under them are rejected pre-grade, exit 4),
   `Config/` is admitted only through the semantic config lane and this spec
   declares no `config_allow`, and the runner materializes the graded substrate
   from git HEAD so an on-disk edit never reaches the grade.

## Hidden invariants

Every number the grade compares the submission against is disclosed in the prompt
— the 300 cm apex, the 1.0 s air-time floor, the 4.0 s landing deadline, the 50 cm
mid-air re-gain tolerance, the 10 cm ground tolerance, the pad's 400 x 400 cm
footprint (so its +/-200 cm edges), the 20 cm the bystander stands clear, and the
two throws. The only verifier-side numbers left are two pieces of drive geometry
that no submission can fail — the 234 cm off-pad clearance at cp3 (a measured
consequence of the disclosed 200 cm pad half-extent plus the character's 34 cm
capsule) and the 0.25 s just-left-the-pad grace in the off-pad guard, which is
leniency in the submission's favour. (An earlier draft graded an undisclosed
`|X| >= 400`; that number is gone.) What is hidden is staging and sampling, not
thresholds:

- **The checkpoint instants (0.6 / 2.9 / 6.6 / 8.8 / 13.2), the drive
  timeline, and the far mark at X = +800 are not disclosed.** A point-fit
  solution keyed to guessed sample times has five independent chances to miss,
  and the two continuous per-frame guards mean the windows *between*
  checkpoints are covered too.
- **The gates read a dense per-tick series, not the checkpoints alone.** Apex,
  air-interval duration and the second-rise test are all computed over every
  frame, so a solution tuned to satisfy five instants still has to produce the
  right shape in between.
- **The control twin is possessed.** A "stays grounded" gate on an unpossessed
  `ACharacter` is vacuous — `MOVE_None`, no gravity, nothing to lift — so the
  fixture FAILs by name at cp0 if the twin is not walking. This is the
  invariant that keeps gate 7 from being a permissive fake.
- **cp3 is the second inert sample, and it is not announced as one.** It sits
  after the first landing and requires that no new air interval has opened
  while the subject stood off the pad — which is where a "keep throwing on a
  timer" solution reveals itself even though it passed cp0 by luck.
