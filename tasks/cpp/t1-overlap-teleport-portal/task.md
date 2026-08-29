---
id: t1-overlap-teleport-portal
substrate: ThirdPerson
set: cpp
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_TeleportPortal :: ATeleportPortalFunctionalTest"]
---

# t1-overlap-teleport-portal

Overlap-triggered teleportation on the **ThirdPerson substrate**: a placed
portal frame relocates any character that walks into it to wherever the
level's destination marker currently is. Sourced from an earlier internal task list (not shipped)
("Teleportation system"); the source row's "use a door or a
rectangular cube for the mesh" dressing is advisory (non-gating — no render
assertion exists in the gate), and the source row's one-line verification cell
("make sure you can teleport") is replaced by the authored criteria below. The
verifier supplies its own walking character, moves the destination marker
before play, and judges delivery purely from measured distance — before
contact, after contact, and after leaving the destination.

## Primary concept

- `ps-collision-overlap` — Collision overlap events
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/collision-in-unreal-engine)

The load-bearing concept is reacting to a runtime begin-overlap edge on a
placed trigger volume — exactly once per entry, with a side effect (the
relocation) computed from live world state at event time.

## Prompt given to the agent

> The level contains a portal frame placed in the world and, elsewhere in the
> level, a destination marker. When a character walks into the portal, that
> character must be instantly relocated to wherever the destination marker
> currently is — read the marker's position at the moment of the teleport
> rather than remembering it from level start, since the marker can be moved.
> A character must never be relocated before it touches the portal. Once
> delivered, the character is free: moving away from the destination
> afterwards must not pull or snap it back. Implement in C++ in the existing
> gameplay module — do not edit the level, any config file, or any test file.

## Workspace state pre-task

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t1-overlap-teleport-portal/TeleportPortalActor.h` / `.cpp` — declares
  and defines `class THIRDPERSON_API ATeleportPortalActor : public AActor`.
  The constructor builds a doorway-shaped query-only box volume
  ("PortalVolume", root, overlap events enabled, Overlap response to all
  channels) and adds `Tags.Add(FName("TeleportPortal"))`. **No overlap
  handling and no teleport logic ship** — the behavior is entirely the
  agent's to implement (on this class or a subclass; both grade identically).
- `Tasks/t1-overlap-teleport-portal/TeleportDestinationMarker.h` / `.cpp` — a
  deliberately inert actor (movable scene root only) whose constructor adds
  `Tags.Add(FName("TeleportDestination"))`. It marks the landing spot; it
  needs no code and should not gain any.
- `Content/Maps/t1-overlap-teleport-portal/L_TeleportPortal.umap` — a flat
  floor, one placed `ATeleportPortalActor` (tagged `TeleportPortal`), one
  placed `ATeleportDestinationMarker` (tagged `TeleportDestination`), and one
  placed `ATeleportPortalFunctionalTest`.

Files that **do not exist**:

- No overlap handler, no teleport code, no Blueprint subclass, no level edits.
  Solve in C++ on the existing class.
- No test source in the agent's writable path. `ATeleportPortalFunctionalTest`
  lives in a separate `CraftBenchTests` module the agent cannot read or
  modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t1-overlap-teleport-portal/L_TeleportPortal.umap` on the
**ThirdPerson** substrate. The engine ticks the world at a fixed deterministic
step (`-deterministic -FPS=60`). The fixture supplies its own moving body — no
PlayerStart or game-mode dependency.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

```text
ATeleportPortalFunctionalTest (derives ACraftBenchFunctionalTest):
    PrepareTest():
        resolve the portal via GetAllActorsWithTag("TeleportPortal");
        assert exactly one (named failure: "... tagged 'TeleportPortal' ...")
        resolve the marker via GetAllActorsWithTag("TeleportDestination");
        assert exactly one
        MOVE the marker to the fixture-chosen destination spot
        (defeats memorized coordinates; the agent's code must read the
        marker's position at teleport time)
        spawn a plain engine character ~740uu in front of the portal;
        SpawnDefaultController() (possession mandatory — an unpossessed
        character is inert)
        SetCheckpointSchedule({0.5, 3.5, 5.0})
    Tick (every frame, after the base checkpoint clock):
        while driving: CONTINUOUS pre-contact guard — if the walker turns up
        at the destination while its walked progress (tracked only on
        un-delivered frames, so a teleport cannot inflate it) is still short
        of the portal's contact zone, FAIL immediately (same named message as
        cp0); a delivery coincident with real contact just stops the drive
        and lets cp1 grade it. Otherwise AddMovementInput toward the portal
        (input is consumed per frame); the drive self-stops once the walker
        crosses the portal's X plane, so an un-teleported walker brakes just
        past the portal
    OnCheckpoint(i):  // Distance = |walker - fixture-chosen marker spot| (3D)
        cp0 t=0.5:  assert Distance >= 250 (not delivered before contact);
                    start driving
        cp1 t=3.5:  assert Distance <= 150 (delivered; contact was ~1.9s);
                    on failure the message BRANCHES on the walker's position:
                    still near the portal -> "never left the portal area";
                    relocated elsewhere -> "delivered somewhere else than the
                    marked destination". On success: stop driving and
                    relocate the walker 400uu away
        cp2 t=5.0:  assert Distance >= 250 (stays free; no re-snapping)
                    -> Succeeded
    every checkpoint logs "[t1-teleport calib] cp<i> t=<t> dist=<d>
    walkerX=<x>" (LogTemp/Display) for tolerance calibration.
```

**Pass criteria**: both L1 targets and L2 green. **Robust identity**: portal
and marker are resolved by tag, never by class; the walker is fixture-owned,
so the agent's code must handle "a character it has never seen before."

## Reference solution metadata

- LOC range: 12-25 (a begin-overlap override or component-delegate binding +
  tag-resolve of the marker + one relocation call)
- Files touched: 2 (both pre-existing scaffold files:
  `TeleportPortalActor.{h,cpp}`)
- Senior-dev hours: under 0.5

## Anti-gaming notes

1. **Empty/partial submission.** *Failure mode*: the scaffold compiles with no
   teleport logic at all; L1 passes. *Defense*: the fixture drives a character
   into the portal and asserts delivery to the marker; with no teleport the
   character brakes just past the portal, ~1,450 units short, and FAILs via
   the named message `never left the portal area - no teleport happened`.
2. **Teleport without contact.** *Failure mode*: the portal relocates every
   character to the marker unconditionally — per-tick, on BeginPlay, or on a
   timer picked to dodge any sampling instant — so every end-state sample
   looks delivered. *Defense*: checkpoint 0 samples the walker before it
   reaches the portal, AND a continuous per-frame guard covers the whole
   approach: a delivery observed while the walker's walked progress is still
   short of the portal's contact zone FAILs via the named message
   `delivered mid-approach without ever reaching the portal`, while the
   BeginPlay/per-tick shape (already there on the first sample) FAILs via
   `already delivered before it had walked at all`.
   There is no timing window to thread — only a delivery coincident with real
   contact is accepted.
3. **Hardcoded landing coordinates.** *Failure mode*: the agent reads the
   marker's authored map position in the editor and pastes the constant into
   code; a casual manual test passes. *Defense*: the fixture MOVES the marker
   to a fixture-chosen spot before play, so a memorized-constant solution
   delivers ~1,900 units from the real marker and FAILs via the named message
   `delivered somewhere else than the marked destination`.
4. **Sticky teleport (re-snapping).** *Failure mode*: the entrant is
   remembered and re-pinned to the marker every tick — delivery holds at any
   sampling instant, but the character is never free again. *Defense*: after
   the delivery check the fixture relocates the walker away from the
   destination and checkpoint 2 asserts it STAYS away, via `no repeated
   snapping back`.
5. **Test disabling / environment repointing.** *Failure mode*: agent edits
   the fixture, the map, or config to weaken the gate. *Defense*:
   `Source/CraftBenchTests/` is sandbox-denied (submission files under it are
   rejected pre-grade), the runner materializes the graded substrate from git
   HEAD (an on-disk edit never reaches the grade; committed changes are
   review-gated on commit), and `Config/` + `Content/Maps/` are deny-listed.

## Hidden invariants

- The checkpoint instants (0.5/3.5/5.0), the fixture-chosen marker spot, and
  the walk-out relocation are not disclosed in the prompt — and the
  pre-contact defense is not a sampling instant at all but a continuous
  per-frame guard across the whole approach, so a timed unconditional
  teleport cannot thread a gap between samples. The only residual window is
  the ~3-frame contact zone immediately before real contact, whose width and
  position depend on undisclosed geometry.
- The marker relocation happens in PrepareTest — after BeginPlay of placed
  actors but before any contact — so caching the marker position in the
  portal's BeginPlay *happens* to read the authored spot and fails the
  delivery gate exactly like a hardcoded constant. Only teleport-time
  resolution passes.
