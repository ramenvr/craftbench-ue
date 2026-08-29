# t3-lift-serves-its-calls-in-order — provenance, decisions and hazards

## Provenance

Authored 2026-08-19 from an owner-seeded T3 design ("a three-landing lift that
must latch every call regardless of what it is doing, serve them in real lift
order, stop level with landings staged at runtime, carry its rider, hold its
doors, and keep all three signs honest"), after an adversarial review whose
verdict was **revise**. This file records what the review demanded, what was
applied, and what was repaired beyond it.

The pattern is not invented: **collective control** is the standard single-car
lift dispatch (continue in the committed direction, serve every call on the way,
reverse only when nothing is left ahead). That satisfies Hard Rule #1 for a
compositional task without citing a game-specific source.

## Every critique item, and what was done about it

| Critique item | Applied as |
|---|---|
| **The sweep premise was false as applied.** With a `USceneComponent` root, `SetActorLocation(..., bSweep=true)` is never truncated (`USceneComponent::MoveComponentImpl` ignores `bSweep`) and `InterpToMovementComponent` auto-registers the same non-primitive root, so both headline wrong answers were unreachable. | **The scaffold changed, not the prose.** `Platform` (a `UStaticMeshComponent`) is now the car's **root**; `Cage`, the walls, both leaves and the three pads hang off it. `AActor::SetActorLocation` is `RootComponent->MoveComponent(...)` (Actor.h:1636 confirms `bSweep=false` is the default), so the swept path now really does route through `UPrimitiveComponent::MoveComponentImpl`. |
| **"The car sits under its passenger and the sill does not move at all" was unverified.** | **Claim deleted, not softened.** Nothing in the spec, the fixture or this file now asserts what a swept upward platform does under a standing character. `TheCarActuallyTravelsAndTakesItsRiderWithIt` is written against the OBSERVABLE (30 uu of progress in 3 s; the rider over the footprint), which fails a stall and a creep identically and does not depend on knowing which one happens. See "What is still unproven" below. |
| **Submission-caused missed windows routed to HARNESS-PRECONDITION** — a denominator opt-out. | Every wait, walk and press window now produces a **named graded FAIL**: `TheLiftKeptTheRiderWaiting`, `TheRiderCouldNotGetWhereHeWasGoing`, `TheCarKeptToItsOwnTimings`, or `NoCallIsEverDropped` when the fixture's own record shows an unserved press. `HARNESS-PRECONDITION` is now reachable **only** from facts the fixture stages (actor counts, floor numbers, shaft height, staged spread, even-spacing, axis alignment, the car/rider clear of landing 2 at re-stage, a walk that would cross a foreign pad). The named escape — "a lift that opens its doors at landing 1 and never closes them" — now dies at `TheLiftKeptTheRiderWaiting` on the wait-for-doors-closing step. |
| **No upper bound on leg 2's pad-3 press**, so the nearest-first discrimination could silently evaporate. | The window is now two-sided: the car sill must be **above the midpoint of landings 3 and 2 by 200 uu** and **already 40 uu below landing 3**. In the shipped tower that is sill ∈ [1325, 1760] — a 2.2 s window entered 0.75 s after departure. Missing it is `TheCarKeptToItsOwnTimings`, a graded FAIL. |
| **No gate behind "do not move a landing"**, and landing decks are Movable. | `TheLandingsAndTheCarStayedWhereTheyWerePut` compares every landing against the transform staged **for the leg in progress** (so the mid-run move cannot self-trip it), to 2 uu, every frame — plus the car's X/Y against the shaft and its sill against the shaft's extent. |
| **Lamp contradiction** ("reads the lamp, never a flag" vs. calling `IsPadLit`). | Resolved in favour of the lamp. The fixture **never calls `IsPadLit`**; it resolves the `UPointLightComponent` by component name and reads `IsVisible() && !bHiddenInGame && Intensity > 0`, exactly as the t1 crate exemplar does. `IsPadLit` remains on the scaffold as a convenience for the agent. |
| **Clause B graded both lamps for a floor** where the prompt says "that pad's light". | Narrowed: each recorded press remembers **which** pad it was (in-car or landing), and only that lamp is graded. The prompt now says "**That pad's** light". |
| **Press detection not tied to the pad volumes.** | Arrival **is** the press: a pad waypoint is reached when the capsule centre is inside that pad's own footprint shrunk by 15 uu. Pad extents (60 uu half) are checked at PrepareTest and a shrunken pad is `TheSuppliedMachineryIsStillThere`. Car interior and pad spacing are published in the spec: a 700 x 700 floor, pads 190 uu off centre, so the car's middle is 80 uu clear of every pad's capsule-wide footprint. |
| **No readout parse convention.** | The gate takes **the first run of digits** in the readout's `FText`, and the prompt now says "A sign is read as a number — the first whole number it prints". |
| **The ±20% speed gate silently forbids easing.** | The prompt now says "**No easing and no acceleration ramp: it is at that speed the whole way**". |
| **Float equality on the door fraction.** | **The critique was right and the first answer to it was WRONG — see "The door never reached 1.0" below.** "The leaf offsets are exact (70 ± 90·phase)" is true of the number `AdvanceDoors` computes and false of the number that ends up on the component, because the engine drops the ramp's last sliver. The snap is now performed IN `GetDoorOpenFraction()` instead of being asserted about the leaves, so the promise in the scaffold header is enforced rather than hoped for. The fixture's own 1e-3 epsilon is unchanged and still only ever forgives. |
| **Sentinel at 420 s against a 600 s governed L2 timeout.** | Trimmed to **240 s**, with checkpoints every 4 s to 200 s. The reference drive measures ~85 s of world time by hand-calculation; every step also carries its own derived deadline, so the sentinel is a backstop, and a healthy run **grades itself early** (FinishTest 0.5 s after the drive ends) rather than burning 155 s of dead simulation. |
| **Premise 2's citations were wrong / deprecated.** | Re-read. `MovementBaseUtility::UseRelativeLocation(const FMovementBaseInterfaceData*)` is Character.h:217-221 and resolves to `IsDynamicBase` → `GetBodyInstanceOwner()->IsPhysicsOwnerMovable()` (Character.cpp:833). The `UPrimitiveComponent` overloads carry `UE_DEPRECATED(5.8, ...)` (Character.h:150-190) — **neither the scaffold nor the fixture calls any of them**, so `--strict-warnings` has nothing to find. |
| **The engine's own `// @todo handle lift moving up and down through encroachment`.** | Recorded below as the one unproven premise, with what the orchestrator must check. |

## Repairs the critique did not ask for

1. **The service order is checked LIVE, as a prefix.** The design compared the
   whole opening sequence at the sentinel. That is a trap: a press-order lift on
   leg 1 opens at floor 3 second, then parks somewhere the drive's "walk out onto
   landing 3" step cannot start from, and dies at a waiting deadline — i.e. the
   single most important discriminator in the task would have scored as a harness
   fault. It now fires on the frame the diverging doors reach fully open.
2. **A gate on the car's own numbers.** `TravelSpeedUuPerSecond` is an
   `EditAnywhere` float that the fixture derives the speed band from. A submission
   that sets it to 3000 in `BeginPlay` would drag the gate's own expectation along
   with it. The five numbers and the three floor numbers are now pinned in
   `OnWorldInitializedActors` — **before any `BeginPlay`** — and compared every
   frame (`TheNumbersOnTheCarAreNotYoursToRewrite`). The prompt discloses it:
   "Those three numbers are the car's, not yours — read them, do not rewrite them."
3. **A gate on the supplied machinery.** Resolving components by name means a
   submission that deletes a lamp would previously have hit a
   HARNESS-PRECONDITION — another denominator opt-out. Structural failures on the
   **agent-writable scaffold** are now `TheSuppliedMachineryIsStillThere`, a graded
   FAIL; only structural failures of the **map** stay HARNESS-PRECONDITION.
4. **Press detection uses the CAPSULE, not the capsule's centre.** This is
   load-bearing and was nearly a false-FAIL generator. A submission bound to the
   pad's overlap event sees the press when the 42 uu capsule *touches* the box; a
   centre test would see it ~0.15 s later. The sign gate compares the signs against
   what the fixture knows is outstanding, so a fixture that learned about a press
   **later** than the submission would fail a correct lift for lighting its arrow
   too early. The press box is the pad box expanded by the capsule radius, which is
   wider at the corners than the true capsule sweep — so the fixture always knows
   first, and the half-second settle absorbs the difference in the safe direction.
5. **Every walk inside the car runs through the middle of the floor.** The first
   layout had the rider walk diagonally from pad 3 to pad 2; with capsule-sized
   press boxes that path clips pad 2's corner region and could have registered a
   press nobody made — which would have rewritten the collective answer the
   ordering gate compares against. `ValidateRoute` now samples every segment against
   every pad box **expanded by 50 uu** and refuses to start if one is crossed.
6. **The car floor grew from 600 to 700 uu square, pads from 135 to 190 uu off
   centre.** Derived, not tuned: the character brakes over ~62 uu from 500 uu/s, so
   arrival at the shrunk footprint plus coast lands him ~207 uu out with ~100 uu of
   platform left. At 600/135 the two pads' capsule footprints were 25 uu apart,
   which is not a margin.
7. **The signs are written from the first Tick, not from `BeginPlay`.** Actor
   `BeginPlay` order is undefined, and a landing's own `BeginPlay` blanks its sign.
   A reference that wrote the signs in `BeginPlay` and then only rewrote them **on a
   change** would have left three blank signs for the whole run whenever the
   landings happened to start after the car. Found by reading, not by running; the
   reference carries the comment so nobody "optimises" it back.
8. **The map's authoring script refuses to ship a decoy that is not a decoy.** It
   recomputes the two heights the verifier will stage and fails the save if the
   committed floor-2 sill is within 400 uu of the first of them, if the two staged
   heights are within 400 uu of each other, or if any of the three sits within
   100 uu of halfway.
9. **The whole tower is solved from the scaffold's own component scales**, read
   back off the spawned actors — landing X, the sill gap, the ground span, the
   parapet positions. A change to the car or landing geometry moves the level with
   it instead of silently opening a gap the character can fall down.

## Design decisions and why

- **The car floor is the ROOT and the only thing that blocks.** Cage, walls and
  door leaves are `NoCollision`. A lift that can pin the character against a wall
  or trap him in a closing door turns the grade into a collision test. The
  parapets on the landings DO block, because the alternative is a character who
  walks off an 18 m deck and ends the run for a reason that has nothing to do with
  lifts.
- **Sill heights are the top of a primitive's world bounds, on both sides.**
  `ALiftCarActor::GetSillHeight()` is `Platform->Bounds.GetBox().Max.Z`;
  `ALiftLandingActor::GetSillHeight()` is the same for `Deck`; the fixture computes
  both the same way from the root primitive. There is exactly one definition of
  "level", so the submission's number and the fixture's cannot diverge — the repo
  law that a comparison must derive both sides identically.
- **The door fraction is measured off the leaves.** `GetDoorOpenFraction()` is
  `(|right.Y - left.Y| - shut) / (open - shut)`, and the fixture recomputes it
  from the same two components with separations pinned pre-`BeginPlay`. A flag
  saying "shut" while the leaves are apart buys nothing.
- **The sign's direction truth is read off what the lift actually did next.** The
  alternative — a second scheduler implementation inside the fixture — is a
  false-FAIL generator at exactly the edges the task is about. Deriving it from the
  next observed opening cannot disagree with a correct lift, still catches the
  velocity-derived arrow at the reversal, and is honest about what it measures:
  gate 6 is **not** independent evidence of anything gate 2 does not already prove
  (the critique said so and it is right) — it measures that the indicator agrees
  with the lift, which is a separate defect surface from the ordering itself.
- **The expected sequence `[1,2,3,3,2,1,3]` is a hard-coded constant, and that is
  legitimate only because every press window is enforced as a graded FAIL.** Given
  the windows hold, the collective answer is determined. Take the windows away and
  the constant becomes a lie.
- **`fps_legs` deliberately NOT declared.** Every timing in this task is derived
  from `DeltaSeconds` and from world time, and the fixture's deadlines come from
  the car's own numbers, so a second rate would be a genuine anti-overfit — but it
  doubles a ~90 s L2 leg and this task already has the largest false-FAIL surface
  in the set. Recommend adding `fps_legs: [60, 20]` **after** the first clean
  reference run, not before.
- **Tier T3, 11–20 h.** Four subsystems that genuinely constrain each other, plus
  PIE integration debugging which dominates every task of this shape.

## Hazards hit while authoring, recorded so they are not re-discovered

- **`GENERATED_UCLASS_BODY` leaves the class body public.** That is why the fixture
  can read `UTextRenderComponent::Text` cross-module (ObjectMacros.h:799-803 →
  `GENERATED_BODY_LEGACY`). `SetText` is `ENGINE_API` despite the class being
  `MinimalAPI`, so the scaffold can call it.
- **`UTextRenderComponent` splits on `<br>`, not on `\n`.** The car's numbers plate
  is one line for that reason.
- **A Static component under a Movable root is a PIE error, not a warning.** Every
  component on both scaffold actors is `Movable`.
- **`unreal.Rotator`'s positional order is (roll, pitch, yaw).** The authoring
  script uses keywords everywhere.
- **`new_level()` refuses to overwrite, and the repo's tombstone law means
  deleting the package in-session does not help.** The script says so and tells the
  operator to delete the file from the shell and re-run in a fresh boot.
- **A level that names a game mode silently drops both halves of Enhanced Input.**
  `L_LiftTower` names none; the script refuses to save if one appears.

## 2026-08-19 owner play-test — what it found and what was done

The owner walked the tower by hand (item 5 of "What is still unproven") and filed two
defects; a third, older one was open at the same time. All three are fixed here.

### 1. The door never reached 1.0, so the reference hung at its first opening

**Symptom.** Two PIE runs 2.5 h apart, byte-identical timings:
`NoCallIsEverDropped: a pad was served for floor 1 at t=2.87 s and its light is still on
at t=3.37 s … it has not been out for a single frame since the doors opened.` The calib
line at t=3.00 reads `frac=1.00 … lamps=*../*.. opened=[1]` — the fixture had recorded the
opening, and both floor-1 lamps were still lit.

**Root cause, and it is NOT where it looks.** The lamps are a pure per-frame function of
`Calls`, so a lit lamp means `Calls` still held floor 1 — i.e. `ServeHere()` was never
reached. It was never reached because `case EPhase::Opening: if (GetDoorOpenFraction() >=
1.0f)` was **false forever**:

- `AdvanceDoors` accumulates `DoorPhase` in float. At the fixed 60 Hz / 2.0 s travel it
  lands on `0.99999940` on frame 120 and the `FMath::Min` clamps it to exactly `1.0f` on
  frame 121. That last step asks each leaf to move **6.1e-05 uu**.
- `USceneComponent::SetRelativeLocation` routes to the FQuat overload (no early-out there)
  → `MoveComponent` → `UPrimitiveComponent::MoveComponentImpl` (no early-out with
  `bSweep=false`) → `USceneComponent::InternalSetWorldLocationAndRotation`, whose
  **line 3315** is `bool bDiffLocation = !NewLocation.Equals(GetRelativeLocation());` —
  `FVector::Equals` with the default `UE_KINDA_SMALL_NUMBER` of **1e-4**. 6.1e-05 < 1e-4,
  so the write is dropped and the leaves stop short.
- Measured separation is therefore **319.99988**, not 320. `(319.99988 - 140) / 180` is
  `0.9999993`, which prints as `1.00` under `%.2f` and is not `>= 1.0f`.
- **The shut end is the same defect mirrored**: the leaves settle at **140.00011**, so
  `GetDoorOpenFraction() <= 0.0f` is false forever too. Even with the open end fixed, the
  `Closing → Idle` transition and the `Travelling` interlock would both have hung.

Ruled out along the way, so nobody re-walks them: the transform round-trip through the
Platform's scale of 7 is EXACT (`-1120 × (1/7)` rounds to exactly `-160.0` in double;
`GetSafeScaleReciprocal` is an honest divide, `UnrealMathSSE.h:2169`); `SetIntensity` is
symmetric; the hero had cleared landing 1's call-pad box before the serve, so no re-latch;
and `ServeHere`/`Calls` have no defect at all.

**Fix.** `GetDoorOpenFraction()` now snaps inside `4 × UE_KINDA_SMALL_NUMBER` of
separation — 4e-4 uu of a 180 uu span, i.e. 2.2e-06 of fraction, **450× narrower than the
fixture's own 1e-3 epsilon**, so the car can never call a door open or shut before the
fixture does (the only dangerous direction: a car that thought the doors were shut first
would move and trip `TheCarNeverMovesWithItsDoorsOpen`). A leaf can be short by at most
`UE_KINDA_SMALL_NUMBER` — a bigger move is never dropped — so the separation can be out by
at most twice that, and the band is twice again for margin. This is SUPPLIED code and the
edit is byte-identical in the scaffold and the reference.

**The general law, which is the part worth keeping.** *A promise about where a component
will be is a promise the engine has not made.* `SetRelativeLocation` is documented as a
request; sub-`KINDA_SMALL_NUMBER` moves are dropped by design. Anywhere a task's contract
says "exactly", enforce it in the accessor the contract is written about — never assert it
about a transform.

### 2. The tower had no top, and the tower face did not block

`ParapetFar/Left/Right` DO block and their scale inheritance is already correct
(`MakeFitting` divides `kDeckWorldScale` back out), so the owner's scale-inheritance
hypothesis did not apply. The real finding is simpler: **there was no roof of any kind**,
and `TowerFace`, `ShaftBack`, the ruler ticks and both pylons were all `collide=False`.
Above landing 3 the tower simply ended. A parapet is 120 uu and the character's jump apex
is **127.6 uu** (`JumpZVelocity = 500` against the default −980, `ThirdPersonCharacter.cpp:31`),
so a rider on the top landing could hop the far rail and fall 18 m through a decorative wall.

Shipped: a blocking `TowerFace`, a blocking `TowerRoof` spanning the whole tower footprint,
both walls raised to the lid, and a **refuse-to-save collision audit** — every block now
asserts that `collide=True` really answers `ECR_Block` to the Pawn channel and
`collide=False` really has none. That audit is the durable part: the owner's suspected
failure (a roof that exists and silently does not block) was one nothing in the script
would have caught, and `AStaticMeshActor`'s constructor leaves `bUseDefaultCollision = true`
(StaticMeshActor.cpp:33-36) so a placed block's real profile came from the MESH ASSET
rather than from anything the script did. `block()` now sets `BlockAll` explicitly, which
clears that flag (StaticMeshComponent.cpp:2618-2622) and turns the audit into a real check.

**Why the lid sits at `SILL_3 + 400` and not lower.** Physically it only needs ~320
(a jumping head). The binding constraint is the camera plan: `landing-three-sign` looks
from `(-1150, -600, 2150)` toward the landing-3 sign at `(-415, 0, 2045)`, and that sight
line crosses the tower's `y = -440` edge at **z ≈ 2122**. A lid at the walls' old height of
`SILL_3 + 300` (2100-2120) would have sat squarely in that shot. At 2200 the camera is
below the lid the whole way and all six poses survive; `tower-high`'s line enters the tower
at z ≈ 1823, well under the lid, so the roof reads as a ceiling at the top of that frame
rather than blocking it. `cast_shadow` is off so the slab cannot darken the interior.

**What is still open, and why it was not fixed here.**
- **The SIDE parapets are jumpable by 7.6 uu** (127.6 apex vs a 120 uu rail), so a rider on
  any landing can still hop a side rail into the void. The obvious fix — raise the parapets
  — is **not free**: `landing-one-approach`'s sight line to the call pad at `(-565, -220)`
  crosses the near side rail at **z ≈ 156**, so a 150 uu rail already clips the shot and a
  180 uu one hides it. Closing the sides with walls is worse: three of the six poses look
  into the tower from −Y, and an invisible-in-game wall would still be opaque in the
  `editor_stills` captures. Costed decision for the owner, not a silent change.
- **`ShaftBack` stays NoCollision.** The car's `Cage`/`WallBack`/`WallLeft`/`WallRight` are
  NoCollision on purpose, so a rider can walk out of the back or sides of the car at any
  floor. Making `ShaftBack` blocking where it is (x = 410) leaves a 60 uu slot beside the
  car floor (x = 350); making it flush means moving it to 360, which is a level-layout
  change and a re-check of the `tower-wide` / `shaft-ride` framing — and it puts a blocking
  wall directly alongside a moving platform, which is the hazard the original author called
  out. Second costed decision.

### 3. "The lift must stay for a few seconds to have player get out"

The owner asked for a 0.5 s minimum dwell and called it a hidden checkpoint. **It is not
hidden**: the requirement is now a sentence in the agent-visible prompt ("A stop is a stop
…"), and it introduces no new number — it reuses the *five centimetres* and *the hold time
written on the car* that the prompt already gives.

The hole it closes is real and was not covered. `TheDoorsHoldOpenLongEnoughToGetOut`
measures the DOOR; nothing measured the CAR's position during the hold, and
`TheCarNeverMovesWithItsDoorsOpen` forgives `kMovedUu = 1.0` per frame — **60 uu/s** at the
fixed step — so a lift that eases toward its next call while the door animation finishes
could drift ~180 uu out of the landing during a 3 s hold and pass everything.

`TheCarStandsStillLongEnoughToStepOut` runs the clock from the frame the doors reach fully
open (the same edge, arming *after* the level check, so a stop that was never level never
starts a dwell) to the first frame the sill is more than `kLevelToleranceUu` from that
landing, and requires `Car.DoorHold - kHoldSlackS`. It is judged **only on departure**: a
car still standing there when the run ends has rushed nobody, so there is deliberately
nothing to evaluate at the end and no way for the gate to false-FAIL a slow-but-correct
lift.

**The threshold is `DoorHoldSeconds`, and a fourth number was considered and rejected.**
It is `EditAnywhere`, set by `author_map.py`, painted on the car's `NumbersReadout`
("… hold 3.0 s"), named in the prompt, and pinned pre-`BeginPlay` by
`TheNumbersOnTheCarAreNotYoursToRewrite` — so the bar is read from the world and varies with
the tower. Shipped at **3.0 s, six times the owner's 0.5 s floor**, and `ResolveCar` already
refuses to stage a tower whose `DoorHold < 0.5 s`, so the gate can never fall below that
floor (the refusal now says why). A separate `StepOutSeconds` would be a second constant
that must agree with `DoorHoldSeconds` — the desync law has cost this repo four incidents —
and would drag the scaffold, the reference, the fixture's pin set, the prompt AND the map
with it for no extra discrimination. If the owner wants a separately-named number, say so
and the map moves too.

**Reference margin.** At each stop the reference holds 3.0 s fully open, then takes 2.0 s
to close, and only travels once the doors read 0 — so it is level and stationary for ~5.0 s
against a 2.85 s bar.

### The map MUST be re-authored

`TowerRoof` is new and `TowerFace`/`ShaftBack` changed height, so the committed `.umap` no
longer matches the script. `author_map.py` refuses to overwrite an existing package and the
tombstone law means deleting it in-session does not help, so the orchestrator must delete
`UE-projects/ThirdPerson/Content/Maps/t3-lift-serves-its-calls-in-order/L_LiftTower.umap`
**from the shell** and re-run the script in a fresh boot, checking for `LIFTTOWER-DONE`.
Nothing else counts as success. The scaffold, reference and fixture edits do not themselves
need a re-author; only the map edits do.

## What is still unproven, and what the orchestrator must check

1. **THE RIDER CLAUSE HAS NEVER BEEN RUN.** Engine premises 1 and 3 were
   re-verified by reading — `UpdateBasedMovement` applies
   `NewBaseLocation - OldBaseLocation` to whoever is standing on the base
   (CharacterMovementComponent.cpp:2557-2670), the follow-move is swept with an
   explicit `OnUnableToFollowBaseMove` on truncation (:2667-2678), and
   `AddTickDependency` makes the rider's movement tick a dependent of the car
   actor's tick (Character.cpp:823-860, which is why the car ships
   `bCanEverTick = true`). **But the engine carries a literal open TODO directly
   above that function**: `// @todo handle lift moving up and down through
   encroachment` (CharacterMovementComponent.cpp:2530). A vertically-moving lift is
   exactly the case Epic says is not fully handled. **First run: watch
   `TheCarActuallyTravelsAndTakesItsRiderWithIt` on BOTH the ascent and the
   descent, and watch the leg-2 descent specifically, where the rider walks between
   pads while the car is moving.** If the rider drifts, the fix is to widen
   `kRiderFeetUu` (currently 60 uu) — the safe direction — not to drop the gate.
2. **No PIE run has happened at all.** No `cb`, no UBT, no editor: this authoring
   pass writes files only. So the drive's hand-calculated timeline (~85 s) is
   arithmetic, not measurement. The three places to check against the reference
   run's `[t3-lift calib]` lines, in order of how likely they are to be wrong:
   - **the mid-close press on leg 1** — the one timing-sensitive step in the whole
     drive. Expected door fraction ≈ 0.8 at the press against a window that closes
     at 0.10, i.e. ~2.4 s of slack, all of it downstream of how fast the character
     actually accelerates. If it lands under 0.10, shorten the two landing dwells
     (1.5 s and 0.3 s, and the arithmetic behind them is in a comment above
     `BuildSteps`'s step table) — **do not widen the window**, which is the only
     thing making `if (State != Idle) return;` fail;
   - the leg-2 pad-3 press (expected car sill ≈ 1650 against a [1325, 1760] window,
     entered 0.75 s into a descent that takes 2.2 s to leave it);
   - the leg-2 pad-2 press (expected car sill ≈ 1120 against a > 550 window).
3. **The map does not exist yet.** `authoring/author_map.py` must be run headlessly
   before anything can be graded, and `tasklint` will report `map-binary-exists`
   and `fixture-source-exists` until the map and the fixture are committed. The
   script prints `LIFTTOWER-DONE` on success and **nothing else counts as success**.
4. **`cameras.json` (the camera-plan lane; not part of this release) is NOT pixel-validated** (`pixel_validated: false`). The two
   poses most likely to be wrong are the landing-3 sign shot (small, high subject,
   pitch solved from geometry) and whether the `NoCollision` shaft wall reads as a
   backdrop or as a grey slab. A capture leg must have motion blur off.
5. **The owner HAS now played the tower (2026-08-19) and the reference has NOT been
   re-graded since the three fixes above.** The rule is unchanged: this task is not
   done until somebody walks it again after the re-author. The specific things that
   play-test must confirm, because each is a fix nobody has run: the doors reach fully
   open and the lamps go dark (the snap); the lift holds at each floor long enough to
   step out; and a rider on landing 3 can neither walk nor jump out through the top or
   the back. **He CAN still hop a side rail** — see item 2 of that section.
6. **One honest weakness, recorded rather than hidden.** The
   "clear the lamp in the end-overlap handler" wrong answer is **not** caught by
   the leg-1 landing press: the doors reach fully open (and the lamp legitimately
   goes out) at ~t=3.4 s, about 0.2 s before the rider steps off the pad. It IS
   caught by the in-car presses — pad 3 is pressed at ~t=8 s, the rider leaves it
   at ~t=9.5 s and it is not served until ~t=26 s, so clause B fires at ~t=10 s. If
   a future edit removes the in-car presses, that defense goes with them.
