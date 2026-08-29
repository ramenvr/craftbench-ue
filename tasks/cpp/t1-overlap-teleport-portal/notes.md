# Build notes — t1-overlap-teleport-portal

Authoring status (2026-07-29): **text half complete, binary half pending.**
Everything below except the committed map exists on disk; nothing has compiled
or run yet. Provenance: a source row "Teleportation system" out of an earlier
internal task list. The source row's verification cell was one sentence
("Make sure you can play game and you can teleport"); the acceptance criteria
in `task.md` are authored, not transcribed — footstep precedent, stated here
per the playbook's provenance rule. The source row's "use a door or modify a cube
to be rectangular for the mesh" is visual dressing: non-gating, dropped from
the graded contract (the scaffold's doorway-shaped volume nods at it).

## The design in one paragraph

The agent gets a portal scaffold (tagged `TeleportPortal`, query-only box
volume, no logic) and an inert marker (tagged `TeleportDestination`). The
fixture owns everything that moves: it relocates the marker to a
fixture-chosen spot in `PrepareTest` (kills memorized coordinates AND
BeginPlay-cached marker reads — both deliver to the authored spot), spawns a
plain engine `ACharacter`, possesses it via `SpawnDefaultController()`, and
walks it into the portal with per-frame `AddMovementInput` (the tp2 pattern).
Three distance-gated checkpoints — not-delivered-before-contact (0.5s),
delivered-after-contact (3.5s), still-free-after-walking-out (5.0s) — plus a
CONTINUOUS pre-contact guard in the fixture Tick: a delivery observed while
the walker's walked progress (`MaxApproachX`, advanced only on un-delivered
frames) is still short of the portal's contact zone FAILs immediately with
the cp0 message. Without the guard, a BeginPlay+timer unconditional teleport
(fire at 1.0s, snap every pawn, zero overlap logic) threads the gap between
cp0 and contact and produces a wrong verdict that looks right — the
`delayed-unconditional-teleport/` variant exists to prove the guard. The cp1
failure message branches on the walker's position (still near the portal =
no teleport happened vs relocated elsewhere = wrong destination), giving the
empty leg and the hardcoded-coordinates leg distinct credited substrings.

## Map contract (binary half — the ONLY missing piece)

`Content/Maps/t1-overlap-teleport-portal/L_TeleportPortal.umap`, authored by
`aids/author_L_TeleportPortal.py` (one-shot recipe, real off-screen RHI — map
authoring crashes under `-nullrhi`):

| element | value | why |
|---|---|---|
| floor | engine cube scaled (36, 30, 1) at (1800, 0, -48) | top face Z=+2; spans X [0, 3600], Y [-1500, 1500] — covers walker start (660, 0), portal (1400, 0), moved marker (2600, -900), walk-out spot (3000, -900), authored marker (3200, 900) |
| portal | `ATeleportPortalActor` at (1400, 0, 122) | box extent (60,120,120) → volume spans X [1340,1460], Z [2,242]; walker capsule (r34, hh88) overlaps it walking through |
| marker | `ATeleportDestinationMarker` at (3200, 900, 90) | the AUTHORED spot — what `hardcoded-destination/` bakes in; the fixture moves the marker to (2600, -900, 90) before play |
| fixture | `ATeleportPortalFunctionalTest` at (0, 400, 120) | out of the walker's lane |
| game mode | WorldSettings GameModeOverride = `/Script/Engine.GameModeBase` | keeps the stock BP_ThirdPersonGameMode mannequin stack out of the headless run (tp2 precedent); the default pawn it spawns sits at the world origin, off the walker's lane and >1,300uu from the portal |
| PlayerStart | none | the fixture spawns and possesses its own walker |

## Fixture geometry + timeline (all constants in the fixture's anonymous namespace)

- Walker spawns at portal − (740, 0, 0), Z=92 (capsule-center settle height
  over the Z=+2 floor top). Drive starts at cp0 (t=0.5); at default
  `UCharacterMovementComponent` max walk speed (600 uu/s, engine default for a
  plain `ACharacter` — NOT the stock template character's 500) contact with
  the volume face (X=1340, minus capsule radius) lands ≈ t=1.6–2.0s
  after accel. cp1 at 3.5 leaves ≥1.5s settle margin.
- Drive self-stops at the portal's X plane (portalX − 20): an un-teleported
  walker brakes just past the portal (~X 1440–1480 after friction, Y=0)
  instead of wandering toward the destination on its own — distance to the
  moved marker (2600, −900) rests at **~1,450uu**, far above the 150uu
  delivery tolerance. (The ~1,900uu figure belongs to the
  hardcoded-destination leg only: authored spot (3200, 900) to moved marker.)
- Continuous pre-contact guard: contact zone = portalX − 140 (box extent 60 +
  capsule radius 34 + ~5 frames of 60Hz walk margin). `MaxApproachX` advances
  only on frames where the walker is NOT at the destination, so a cheat
  teleport cannot inflate it; a legit contact teleport leaves it at ~1,300
  (inside the zone) while a 1.0s-timer cheat leaves it at ~860 (well short).
  Residual granularity: a timed cheat that fires inside the ~3-frame /
  ~50ms window just before real contact passes the guard — undisclosed,
  geometry-dependent, and accepted as out of scope.
- Delivery tolerance 150uu (3D): a reference teleporting capsule-center to the
  marker at Z=90 measures ~0 after settle; a reference that lifts the landing
  by a capsule half-height measures ≤ ~92 pre-settle. Free floor 250uu, with
  the true separations at ~400 (walk-out), ~1,450 (no-teleport rest),
  ~1,900 (hardcoded landing), and ~2,100 (pre-contact at cp0) — comfortable
  margin on every gate. These are the calibration baselines to diff the
  `[t1-teleport calib]` lines against.
- cp1 message branching threshold: walker within 600uu (3D) of the portal
  center = "never left the portal area" (empty leg rests ~70uu from it);
  farther = "delivered somewhere else than the marked destination"
  (hardcoded leg lands ~2,000uu from the portal).
- cp2 sits 1.5s after the walk-out relocation: a re-snapping Tick has ~90
  frames at 60Hz to drag the walker back — the cheat is ACTIVE at the sample
  instant (tp2's trap-inside-the-cheat-window lesson; here the window is
  unbounded, so the trap placement is trivially safe).

## Grading honesty: the fixture's Error paths GRADE AS AGENT FAIL today

The fixture has four `FinishTest(EFunctionalTestResult::Error)` precondition
paths — no-UWorld, marker-not-movable, walker-spawn-failed,
possession-failed. **Do not read "Error" as harness-error routing: today an
automation Error lands as state "Fail" in `index.json`, `l2_pie.py` counts it
in `tests_failed` with no special-casing, and no `harness_error_reasons`
predicate reads fixture message text — so all four paths grade as an agent
FAIL.** All four messages carry a `HARNESS-PRECONDITION: ` prefix as the hook
for a future runner-side routing rule (a named work item in the parent plan)
that would route them to exit 7; until that lands, a flake on any of these
paths is scored against the model, which is exactly the verdict-taxonomy
hazard the repo fights. This is the top calibration risk below.

## Calibration checklist (UNPROVEN until the first compile + graded leg)

Every item below is a believed-true assumption the binary-half session must
confirm; each has a designed fallback. Item 1 is the load-bearing risk.

1. **Possession + drive — a flake here grades as agent FAIL today.**
   `SpawnDefaultController()` must possess the walker (an unpossessed
   Character is inert), and per-frame `AddMovementInput` must move it under
   the resulting `AAIController` (no ULocalPlayer; tp2 proved the pattern
   only under a PLAYER controller from the map's game mode).
   `APawn::ControlInputVector` consumption by CMC does not depend on the
   controller class, so this should walk — but if possession or input
   consumption proves flaky, the failure lands on the
   `HARNESS-PRECONDITION: ... possession failed` path or as a
   never-arrives cp1 FAIL, both of which GRADE AS AGENT FAIL (see the
   section above). *Fallback (named, designed)*: drop the controller
   dependency entirely and drive with scripted `SetActorLocation` sweep
   steps toward the portal in the fixture Tick — still fires begin-overlap,
   loses CMC realism, keeps every assertion and every named message.
2. **Plain `ACharacter` spawns concrete** (it is not abstract) and settles
   onto the floor within 0.5s from Z=92. *Fallback*: raise cp0 to 0.8s.
3. **Marker root is movable.** Plain `USceneComponent` roots default to
   Movable mobility; `SetActorLocation` on the placed marker must return
   true. A false return hits the `HARNESS-PRECONDITION: ... marker` path —
   which today grades as an agent FAIL (see above), so confirm this before
   the first graded leg. *Fallback*: set mobility explicitly in the marker
   constructor.
4. **Walk time budget.** The 600 uu/s engine-default speed and ~0.2s accel
   are estimates; read the `[t1-teleport calib]` lines under
   `-deterministic -FPS=60` and re-time cp1 if contact lands later than
   ~2.5s. The guard's contact zone (portalX − 140) assumes ~10uu/frame at
   contact speed — re-derive if the speed differs.
5. **Capsule-vs-box overlap fires while walking through** a query-only box
   with Overlap-to-all responses (pawn capsule generates overlap events by
   default). This is the same wiring `cpp/t1-overlap-logs-once` gates on,
   but on the other substrate.
6. **GameModeBase override spawns its default pawn at the world origin**
   given no PlayerStart, and that pawn neither wanders nor touches the
   portal. *Fallback*: a tiny task game mode with `DefaultPawnClass =
   nullptr` (tp2-style scaffold addition — needs a re-run of the L1 half
   only).

## Known harness gap (documented, fixed by the parent session's change)

`tools/run-agent/fairness.py::_PER_TASK_ROOTS` does not include
`Source/ThirdPerson/Tasks`, so ThirdPerson C++ scaffolds (this task's portal +
marker, tp2's character pair) are NOT fairness-pruned when a DIFFERENT task is
driven on this substrate — a foreign task's agent can see this task's scaffold
as a decoy. Harmless for grading (grading reads git HEAD per task), but it
diverges from the CraftBenchTemplate isolation contract. The parent session is
adding the root + a test in the same change; this note is the provenance
pointer.

## Discrimination record

Not yet run — see `discrimination/MATRIX.md` §Status. To be filled from the
first `cb discriminate --wip` after the map lands: per-leg verdicts, the calib
line values at each checkpoint, and any re-timed checkpoints.

## Calibration record — first live validation (2026-07-29)

Binary half + full matrix ran this date on this box (Win11, UE 5.8 at
`C:\Program Files\Epic Games\UE_5.8`, substrate=live via `--wip`):

- **Build**: editor target compiled the task's scaffold + fixture C++ clean on
  the FIRST attempt (no warnings in task files).
- **Map**: authored headless by `aids/` script (`-ExecutePythonScript`,
  `-RenderOffScreen`); single monolithic `.umap`, no OFPA spillover; placement
  log line confirmed in the editor log.
- **Matrix**: `cb discriminate --wip` = **discriminated: YES** — reference
  PASS; empty + EVERY variant FAIL, each credited via its named MATRIX
  substring (`[ok ]` on all legs).
- **Not retained**: per-leg run dirs (no `--keep`), so the fixture's numeric
  calib log lines were not harvested. The checklist's yes/no assumptions are
  answered by the verdicts themselves; re-run with `--keep` if the numeric
  baselines are wanted before re-timing any checkpoint.

Checklist items resolved by the 2026-07-29 matrix (verdict-level evidence):
1. **Possession/drive (the load-bearing unknown): CONFIRMED WORKING** — the
   reference leg PASSed, which requires the spawned `ACharacter` under
   `SpawnDefaultController()` to consume per-frame `AddMovementInput`, walk
   ~600 uu into the portal, and be teleported on begin-overlap. The scripted
   `SetActorLocation`-sweep fallback is NOT needed.
2. The continuous pre-contact guard did NOT false-fire on the reference (PASS)
   and DID catch `delayed-unconditional-teleport` (FAIL via `before entering
   the portal`).
3. Capsule-vs-box overlap fires on this substrate (reference teleported).
4. The `GameModeBase` default pawn at origin did not disturb any leg.
