---
id: t1-guard-only-spots-what-it-can-see
substrate: ThirdPerson
set: craftbench-public
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_SightYard :: AGuardSightFunctionalTest"]
---

# t1-guard-only-spots-what-it-can-see

Sight-based detection with a **visible red/dark lamp** as the graded readout, on
the **ThirdPerson substrate**. Two identical watch guards stand 300 cm apart in
one camera frame; the player-controlled mannequin walks a route that takes it
behind the graded guard, into its cone, past its range, and behind a crate. The
near guard's lamp must turn red only for the in-cone-in-range-unobstructed
positions; the far guard sits behind a permanent wall and must stay dark for the
whole session.

Imported from the Startup Eval corpus row `t1-ai-sight-detection`
(provenance, owner note, and every deviation: `notes.md`). The corpus row's
`k/4` rubric is **re-banded into one two-sided pair scored together** — three of
its four checks were true of a submission that does nothing, so an empty
delivery reported 3/4. Here `seen-when-visible` and `dark-when-not-visible` are
one verdict, and doing nothing scores zero.

> **`deliverable_root:` was REJECTED by the parser.** It is not in
> `tools/verify-single/spec.py::_KNOWN_KEYS`, and an unknown front-matter key is
> a hard `ValueError` (exit 2, "spec malformed") — not a warning. Per the
> `tasks/README.md` mitigation the deliverable root is
> therefore stated as the first line of **Workspace state pre-task** and again
> in the prompt body: it is `Source/ThirdPerson/`.

## Primary concept

- `ai-perception` — AI Perception
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/ai-perception-in-unreal-engine)

The load-bearing behaviour is sight as a **conjunction of three independent
conditions** evaluated per frame against live world state — range, forward
angle, and an unobstructed line — expressed relative to the observer's own
transform rather than to level coordinates. The grade never asks *how*: a sight
sense on a perception component, a sensing component, or a hand-rolled
distance + angle + trace all pass identically.

## Prompt given to the agent

> The yard contains two identical watch guards. Each stands on the floor facing
> along the yard and carries one lamp, dark when play begins. Make a guard light
> its lamp red exactly while it can see the character the player controls, and
> go dark again as soon as it cannot.
>
> A guard can see the character when all three of these hold at once, measured
> from that guard's own position and the direction it is facing: the character is
> no more than **1200 units** away; the character is within **45 degrees** either
> side of the direction the guard faces; and no solid object stands between the
> two of them. If any one of the three stops holding — the character walks round
> behind the guard, walks further than 1200 units away, or steps behind a crate —
> the lamp goes dark. The lamp must track the character for the whole session,
> turning red again every time the character becomes visible again, and it must
> settle to the correct state within **0.5 seconds** of any change.
>
> The rule belongs to a guard, not to a particular guard in this yard: both
> guards run the same rule, and neither may be special-cased by name, position
> or index. Whether either lamp ever lights is decided entirely by what that
> guard can see. Do not move the guards, the walls, the crate or the character.
>
> Each supplied guard already owns its lamp, an eye point in front of its head,
> and the switch that turns the lamp red or dark; the two numbers above are
> already set on it. Nothing decides when to throw that switch yet. Write your
> solution in C++ under `Source/ThirdPerson/` — do not edit the level, any
> config file, or any test file.

## Workspace state pre-task

**Deliverable root: `Source/ThirdPerson/`** (the agent-writable runtime module on
this substrate). `Source/CraftBenchTests/` is deny-listed and a submission file
under it is a SANDBOX-REJECT (exit 4), not a graded FAIL; so are
`Content/Maps/`, `Content/ThirdPerson/`, `Content/Characters/` and every
`Config/` file (no `config_allow` is declared by this task).

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t1-guard-only-spots-what-it-can-see/SightGuardActor.h` / `.cpp` —
  declares and defines `class THIRDPERSON_API ASightGuardActor : public AActor`.
  The constructor adds `Tags.Add(FName("SightGuard"))` and builds, all supplied:
  - `Body` — a cylinder static mesh, ~60 cm across and 180 cm tall, collision
    on (a solid prop a reviewer can see and whose facing reads from the eye).
  - `Eye` — a small sphere at relative `(40, 0, 170)`, **collision disabled**,
    the sanctioned sight origin. It sits in FRONT of `Body`, so a line drawn
    from it toward the character never starts inside the guard's own collision.
  - `Bulb` — a sphere at relative `(0, 0, 200)`, collision disabled, driven by a
    dynamic material instance (red when lit, dark grey when not).
  - `AlertLamp` — a point-light component at relative `(0, 0, 200)`,
    `LightColor` pinned red, `Intensity = 0` (dark), attenuation radius 600.
  - `UFUNCTION(BlueprintCallable) void SetSpotted(bool bNewSpotted)` — the
    supplied switch: stores the flag, sets `AlertLamp` intensity to `5000` /
    `0`, and swaps the bulb colour. **Nothing calls it.**
  - `UFUNCTION(BlueprintPure) bool IsSpotted() const`.
  - `UPROPERTY(EditDefaultsOnly) float SightRangeUu = 1200.f` and
    `float SightHalfAngleDeg = 45.f` — the two disclosed numbers, pre-set.
  - **No tick, no timer, no trace, no angle math, no call to `SetSpotted`
    anywhere.** The whole decision is the agent's to implement, **and it has to
    land on this class**: the two guards are placed instances of
    `ASightGuardActor` in a map you cannot edit, so a subclass of it would never
    be instantiated in the graded world and both placed guards would stay
    logic-free. (An earlier draft said "on this class or a subclass of it; both
    grade identically", which was false in the direction that costs a
    submission the whole task.)
- `Content/Maps/t1-guard-only-spots-what-it-can-see/L_SightYard.umap` — the staged
  showroom, committed binary. World Settings select the stock read-only
  `BP_ThirdPersonGameMode`, so play spawns and possesses the stock mannequin
  character at the PlayerStart. What is in it:

  | Element | Placement | Notes |
  |---|---|---|
  | Floor | a wide striped yard | **stripe markings every 200 cm along the long axis** so speed and distance read by eye |
  | PlayerStart | on the floor, off the world origin, facing the guards | |
  | Two `ASightGuardActor`s | side by side, a few metres apart, facing the same way, both in one camera frame | **interchangeable**: same class, same facing, **no distinguishing per-instance tag, name or index** |
  | A blocker wall | standing immediately in front of ONE of the two guards, flush to its body and wider than its cone | that guard's permanent occluder |
  | Crate | tagged `SightCrate`; the movable occluder, **relocated by the fixture before play** | |
  | Cone-edge stripes + range arc | painted at +/-45 deg out to 1200 | no collision — the two graded numbers made photographable |
  | Backdrop + landmarks | a low back wall and a distinctly coloured marker post at each end | a moving camera is distinguishable from a still one |
  | Fixture | one placed `AGuardSightFunctionalTest` | |

  **The guards' exact coordinates are deliberately NOT in this section, and the
  sentence "one of the two stands behind a wall so it must stay dark" is
  deliberately not in the prompt.** `## Workspace state pre-task` and
  `## Prompt given to the agent` are exactly
  `tools/run-agent/prompt_extract.py::ALLOWED_SECTIONS`, i.e. both reach the
  agent — so an earlier draft that tabulated `(0, +150)` / `(0, -150)` and said
  one guard must stay dark handed over `if (GetActorLocation().Y < 0) return;`,
  which defeats the every-frame control gauge outright. That gauge is the ONLY
  assertion behind the requirement row *"the rule is per-guard, not
  per-instance"*, so a position key would have hollowed out the control
  completely. Geometric role assignment in `PrepareTest` defends against tag and
  index keys, not against a coordinate key; withholding the coordinates is what
  closes it, and `PrepareTest` additionally **jitters both guards' placement**
  (see the verifier section) so even a leaked coordinate is stale.

Files that **do not exist**:

- No detection logic of any kind, no Blueprint subclass, no level edits. The
  empty submission compiles (L1 green) and FAILs L2 at the first lit-side
  checkpoint.
- No test source in the agent's writable path. `AGuardSightFunctionalTest`
  lives in the `CraftBenchTests` module the agent can neither read nor modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t1-guard-only-spots-what-it-can-see/L_SightYard.umap` on the
**ThirdPerson** substrate, ticked at a fixed deterministic step
(`-deterministic -FPS=60`). Verification primitive:
**pie-checkpoint-sampling** (the schedule + `OnCheckpoint` clock owned by
`ACraftBenchFunctionalTest`), with an in-fixture **pie-state-probe** readback of
each guard's point-light intensity, driven by the shipping per-frame
`AddMovementInput` timeline (`Tasks/t1-overlap-teleport-portal/TeleportPortalFunctionalTest.cpp:194`,
`Tasks/t2-ladder-climb-volume/LadderClimbFunctionalTest.cpp:246`,
`Tasks/t2-npc-follows-player/NpcFollowFunctionalTest.cpp:144`). A human hitting
Play drives the identical route with WASD and sees the identical lamp states —
same observable, two drivers.

**Two implementor notes, so nobody goes looking for a helper that does not
exist.** (1) This fixture derives from `ACraftBenchFunctionalTest`, **not** from
`ACraftBenchPawnFunctionalTest`: the walker is the game-mode-spawned player
character (resolved as player 0), not a fixture-spawned pawn, and the control
twin is a **placed** actor resolved by tag — so no second-pawn spawner is needed
at all. (2) If the implementor nonetheless chooses to spawn the control twin
instead of placing it, that spawner is **declared locally in this task's own
fixture class and duplicated per task** — the owner has approved the
duplication explicitly. `SpawnAndPossessPawn()` handles exactly one pawn, there
is no shared API for a second subject, and
`CraftBenchFunctionalTest.{h,cpp}` / `CraftBenchPawnFunctionalTest.{h,cpp}` are
owned by another machine and **must not be edited**.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

**No warning assert, deliberately.** An earlier draft carried `no new
shadowed-variable / deprecated-declarations warnings in the agent-touched
compilation units`. Measured: `--strict-warnings` is `action="store_true"` and
**off by default** (`run_task.py:1035`), and no `aura_rig` path passes it, so on
`cb eval` / `cb refgate` that assert would never have run — a dead gate. When it
does run it is `l1.warning_count_agent_files > 0` (`layers/registry.py:100`):
**any** warning, no shadowed/deprecated filter, no new-since-baseline
comparison. And the prompt never mentions warnings, so gating on it would be an
undisclosed grade-bearing condition. L1 here is exactly the two UBT targets.

### L2 — AFunctionalTest behavioral trace

Lit/dark is read from each guard's own point-light component — found by
component type, never by name, so a rename cannot break the gate — via
`Intensity > 0`. That is the on-screen truth: the colour is pinned red by the
supplied constructor, so "lit" and "red" cannot diverge. `IsSpotted()` and the
bulb colour are logged **advisorily** and never gate, so an implementation that
drives the lamp by its own route grades identically to one that calls the
supplied switch.

```text
AGuardSightFunctionalTest (derives ACraftBenchFunctionalTest):
    PrepareTest():
        Super::PrepareTest()
        resolve GetAllActorsWithTag("SightGuard"); assert exactly TWO
          (named failure: "... two guards tagged 'SightGuard' ...")
        JITTER both guards: offset each guard's placed location by a
          fixture-chosen amount in [-120, +120] cm along Y and [-60, +60] cm
          along X (deterministic, derived from a fixture constant, not from
          RNG), keeping each inside its own staging envelope — the walled guard
          stays behind its wall and the graded guard keeps the route's 127 cm
          body clearance. A coordinate-keyed special case ("if my Y is
          negative, never light") is then keyed to a location no guard is at.
          The wall is authored FLUSH to its guard's body and wider than the
          cone, so the jitter cannot open a sight line.
        classify them GEOMETRICALLY, not by tag and not by the authored
          coordinates: trace from each guard's eye to the clear waypoint; the
          guard with the blocked line is the CONTROL twin, the other is the
          GRADED guard. (No per-instance tag distinguishes them, so no
          implementation can special-case one.)
        assert the control twin has NO clear sight line to ANY point on the
          floor inside its own cone, at any distance — swept as a fan of traces
          from its eye at 5-degree steps across +/-45 deg out to 1200 uu, every
          one of which must be blocked
          ("HARNESS-PRECONDITION: the walled guard has an unobstructed line
            inside its own cone")
          [This is the staging invariant the whole control rests on, and the
           earlier geometry did not satisfy it. With the wall standing 160 cm in
           FRONT of the twin, a character between the eye (x = 40) and the wall
           (x = 140) is inside the cone with a completely unobstructed line — so
           a CORRECT per-guard rule lights the twin there and the every-frame
           control gauge FAILs correct work. The old layout was safe only
           because the fixture's route happened to avoid that gap: safety by
           route choice, unacknowledged, and broken the instant a human hits
           Play and walks into it. The wall is now authored FLUSH to the twin's
           body — its inner face at the body's front face, no near-field gap at
           all — and wide enough that the fan finds no opening. The precondition
           SWEEPS it rather than trusting the arithmetic, so a map edit that
           reopens the gap is a named harness precondition failure and never a
           graded FAIL.]
        resolve GetAllActorsWithTag("SightCrate"); assert exactly one, then
          MOVE it to the fixture-chosen spot (620, 480) — a shadow polygon
          baked from the crate's AUTHORED map coordinates is now wrong
        resolve the player character (player 0); assert valid and that it
          carries a visible mesh (a meshless walker is invisible to a
          reviewer) — both HARNESS-PRECONDITION-prefixed
        derive the occluded waypoint from the crate's LIVE transform:
          Eye + 1.45 * (crate - Eye), i.e. ~(881, 628)
        SetCheckpointSchedule({1.0, 3.5, 7.5, 10.5, 13.5})

    Tick (every frame, after the base checkpoint clock):
        CONTROL GAUGE, EVERY FRAME: the control twin's lamp must be dark.
          A lit control lamp FAILs immediately
          ("the second guard ... lit although a wall blocks its view").
        PRE-SIGHTING GUARD, EVERY FRAME: until the frame the fixture's own
          MOST-PERMISSIVE oracle first says the character is visible to the
          graded guard, the graded lamp must be dark. A lit lamp before that
          FAILs ("lit before the character could possibly have been visible")
          — this is what a BeginPlay/timer light-up dies on; there is no gap
          between samples to thread.
          THE ORACLE IS THE UNION OF EVERY SANCTIONED MEASUREMENT BASIS,
          PLUS THE DISCLOSED SETTLE WINDOW. It says "visible" as soon as ANY
          of these says visible, and the guard then disarms 0.5 s earlier
          still (T_arm_end = T_first_visible_any_basis - 0.5 s):
            - range and angle measured from the guard's ACTOR ORIGIN, or from
              its EYE point;
            - the angle taken as a 2D yaw difference, or as a full 3D dot
              product against the facing vector;
            - the trace aimed at the character's capsule centre, at its head,
              or at its feet.
          WHY, measured: on the W0->W1 leg the 45 deg crossing happens at path
          fraction s = 0.714 from the origin `(0,150)` but s = 0.771 from the
          eye `(40,150)` — a ~43 cm / ~0.086 s window in which an
          origin-measuring implementation (which this spec explicitly declares
          CORRECT) is legitimately lit while an eye-based oracle still says
          not-yet-visible. A single-basis oracle would FAIL that submission
          outright. The union plus the 0.5 s disclosed settle margin means the
          basis a submission chose can never decide its verdict — which is the
          whole point of the "measured from origin or from eye, both correct"
          claim below, and that claim was previously true only AT the five
          waypoints, not on the continuous guard.
        DRIVE: AddMovementInput toward the current target waypoint (input is
          consumed per frame; never tick the world); stop applying input
          within the arrival tolerance so the character stands still for the
          sample. The target advances only at a checkpoint.

    OnCheckpoint(i):   // asserts BOTH lamps at every checkpoint
                       // Distances/angles are ORIGIN-based, with the eye-based
                       // reading in parentheses where it differs by > 1 deg or
                       // > 30 cm. Both readings give the same verdict at every
                       // checkpoint, by construction.
        cp0 t=1.0   at W0 (-400, 250): behind the guard, 412 (459) away, IN
                    range, 167 deg off its facing, clear line
                    -> GRADED DARK  "lit while the character stood behind it"
                       CONTROL DARK; target := W1
        cp1 t=3.5   at W1 (350, 300): 381 (354) away, 23 (26) deg, clear
                    -> GRADED LIT
                       "the guard's lamp stayed dark although the character was
                        in plain view"
                       CONTROL DARK; target := W2      [firing 1]
        cp2 t=7.5   at W2 (1600, 150): 1600 (1562) away (> 1200), 0 deg, clear
                    -> GRADED DARK
                       "lit while the character stood beyond the stated range"
                       CONTROL DARK; target := W3
        cp3 t=10.5  at W3 ~(881, 628): 1018 (967) away, 29 deg, BLOCKED by
                    the relocated crate
                    -> GRADED DARK
                       "lit while a solid object stood between them"
                       CONTROL DARK; target := W3a then W1
        cp4 t=13.5  back at W1: identical position to cp1
                    -> GRADED LIT
                       "the lamp did not come back on the second time the
                        character was in plain view"
                       CONTROL DARK -> Succeeded                    [firing 2]

        The four DARK/LIT literals above, the two-guards precondition
        ("... two guards tagged 'SightGuard' ..."), the control-lit literal
        ("the second guard ... lit although a wall blocks its view") and the
        pre-sighting literal ("lit before the character could possibly have been
        visible") are EIGHT distinct strings — one per gate. The three negative
        legs (behind / out of range / occluded) are the three separable
        mechanics, so "the range check is missing" can never read as "the
        occlusion check is missing".
        each checkpoint first asserts the character is within 150 of the
        expected waypoint (HARNESS-PRECONDITION-prefixed: a walk that did not
        complete tested nothing), then logs
        "[t1-guardsight calib] cp<i> t=<t> pos=<x,y> d=<d> ang=<a>
         graded=<lit|dark> control=<lit|dark> spotted=<b>" (LogTemp/Display).
```

Route (fixture-owned, undisclosed to the agent), all legs collision-checked
against the wall, the crate and the guards' own bodies (`W0 -> W1` passes 127
clear of the graded guard): `W0 (-400,250) -> W1 (350,300) -> W2 (1600,150) ->
W3 ~(881,628) -> W3a (900,200) -> W1 (350,300)`. `W3a` exists only to walk round
the crate rather than into it. **Every leg's verdict is the same whether range
and angle are measured from the guard's actor origin or from its eye point** —
the two differ by 40 cm in X and 170 in Z, and the tightest margin (cp2's
beyond-range leg) is 30% either way. That ambiguity must not be gradable, since
both readings are correct implementations; the continuous pre-sighting guard is
therefore keyed to the UNION of every sanctioned basis (above), not to one of
them, because at the five waypoints the bases agree and *between* them they do
not. The per-checkpoint annotations below give the ORIGIN-based distance and
angle throughout, and the eye-based figure in parentheses where they differ by
more than a degree; a checkpoint annotated in one basis and its neighbour in the
other is a calibration bug, not a spec choice. Leg lengths total ~4,000 cm;
at the stock ~500 uu/s ground speed the schedule above carries >= 0.5 s of
settle after every arrival, which is exactly the disclosed response window.
**The checkpoint instants are calibrated estimates: the build step must confirm
each one against the `calib` lines of a reference run before any MATRIX row is
trusted.**

### Requirement-to-assertion map

| Prompt requirement | Assertion | Skipped when |
|---|---|---|
| lamp dark when play begins | cp0 GRADED DARK + the every-frame pre-sighting guard | never (cp0 is before any drive) |
| red while in range, in cone, unobstructed | cp1 and cp4 GRADED LIT | never |
| dark when behind the guard (in range) | cp0 GRADED DARK | never |
| dark when beyond 1200 (in cone, clear) | cp2 GRADED DARK | never |
| dark when a solid object blocks the line | cp3 GRADED DARK, crate relocated | never |
| turns red again every time it becomes visible | cp4, the same measurement as cp1 | never |
| settles within 0.5 s of a change | every checkpoint sits >= 0.5 s after arrival | never |
| the rule is per-guard, not per-instance | control twin dark at every checkpoint AND every frame | never |
| measured from the guard's own transform | the twin (identical class, blocked line) + the relocated crate | never |

**Scoring — the re-band.** L2 is a single `AFunctionalTest` outcome, so the two
sides are structurally inseparable: PASS requires the LIT side (cp1 **and** cp4)
and the DARK side (cp0, cp2, cp3, plus both continuous guards) together. There
is no partial credit and no `k/4`. An empty submission FAILs at cp1 with
`the guard's lamp stayed dark although the character was in plain view`; a
lamp that is always on FAILs at cp0 before the character has moved.

**Pass criteria**: both L1 targets and L2 green. **Robust identity**: guards by
`SightGuard` tag and then by geometry, never by class or per-instance tag; the
lamp by component type; the crate by tag and read at its LIVE transform.

## Reference solution metadata

- LOC range: 30-60 (a tick or short-interval evaluation: distance against the
  supplied range, forward-angle test against the supplied half-angle, one line
  trace from the supplied eye to the character, and a change-detecting call to
  the supplied switch)
- Files touched: 2 (both pre-existing scaffold files:
  `SightGuardActor.{h,cpp}`)
- Senior-dev hours: 0.5-1.0

## Anti-gaming notes

1. **Always-detecting / never-detecting.** *Failure mode*: `SetSpotted(true)` in
   BeginPlay, or nothing at all. *Defense*: the two sides are one verdict — the
   always-on shape FAILs at cp0 (and, before that, the every-frame pre-sighting
   guard, which leaves no window to thread) **and** lights the control twin the
   very first frame; the do-nothing shape FAILs at cp1. Neither can bank the
   3-of-4 the corpus rubric would have paid it.
2. **One criterion instead of three.** *Failure mode*: distance-only,
   line-of-sight-only, or cone-plus-line-with-no-range (the last is exactly what
   the successor corpus row drops). *Defense*: three negative legs, each
   isolating one missing criterion with a wide margin — cp0 is in range and
   unobstructed but 167 deg off the facing; cp2 is in cone and unobstructed at
   1600 (33% beyond the disclosed 1200); cp3 is in range and in cone but behind
   the crate. Line-of-sight-only additionally lights the **control twin** at
   cp0, where the twin's line to `W0` is clear and only its cone excludes it.
3. **Baked geometry.** *Failure mode*: the agent reads the level, then hardcodes
   a visible-region box, the crate's shadow polygon, or "the guard sits at
   `(0,150)` facing +X". *Defense*: the fixture MOVES the crate before play, so
   the occluded waypoint is derived from a transform the agent never saw; the
   route is undisclosed, so a fitted region must cover the whole cone anyway;
   and the two guards carry **no** distinguishing per-instance tag, so any
   world-coordinate rule either lights the twin or lights nothing.
4. **One-shot latch, or a lamp that never re-fires.** *Failure mode*: the lamp
   lights on first sight and stays lit, or fires exactly once. *Defense*: the
   latch dies at cp2/cp3 (must go dark twice more); the fire-once shape dies at
   cp4, which repeats cp1's measurement from the identical position — the second
   firing must produce the same measured outcome.
5. **Test disabling / environment repointing.** *Failure mode*: the agent edits
   the fixture, the map, the game mode or config to weaken the gate.
   *Defense*: `Source/CraftBenchTests/` is sandbox-denied and the graded
   substrate is materialized from git HEAD (an on-disk edit never reaches the
   grade; a committed one is review-gated on commit); `Content/Maps/`,
   `Content/ThirdPerson/` and `Content/Characters/` are deny-listed, so the map's
   game-mode override and the mannequin cannot be repointed; and this task
   declares no `config_allow`, so any `Config/` edit is a sandbox-class reject.

## Hidden invariants

- **The checkpoint instants (1.0/3.5/7.5/10.5/13.5) and the whole route are
  undisclosed.** Only the three sight numbers and the 0.5 s response window are
  in the prompt, per the disclose-every-graded-number rule. A solution fitted to
  guessed sample times has five independent chances to miss.
- **The crate is relocated in `PrepareTest`** — after the placed actors'
  BeginPlay but before any walking. So caching the crate's position (or its
  shadow) at BeginPlay *happens* to read the authored spot and fails cp3 exactly
  like a hardcoded constant. Only occlusion resolved against live world geometry
  passes.
- **Two continuous per-frame guards, not sampling instants.** The control twin's
  lamp is gauged EVERY frame, not only at the five checkpoints; and the graded
  lamp is gauged every frame from `StartTest` until the fixture's own oracle
  first reports the character visible. A timed or BeginPlay light-up therefore
  has no gap between samples to fire in.
- **The graded/control roles are assigned geometrically at PrepareTest**, from a
  trace to the clear waypoint — not from a per-instance tag, an index, or a
  name. "If I am the second guard, never light" cannot be written against
  anything the agent can read.
