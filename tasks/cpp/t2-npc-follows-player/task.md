---
id: t2-npc-follows-player
substrate: ThirdPerson
set: cpp
tier: T2
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2]
fixtures: ["L_NpcFollow :: ANpcFollowFunctionalTest"]
---

# t2-npc-follows-player

An enemy that detects and pursues the player on the **ThirdPerson substrate**
— the benchmark's first AI/navigation task. Sourced from an earlier internal
task list (not shipped) ("Enemy NPC system"); the source row's "use a cube for
the mesh" dressing is advisory (non-gating — no render assertion exists in the
gate), and its one-line verification cell ("the npc has to follow the main
character") is replaced by the authored criteria below. The verifier grades
pursuit purely from measured distance over time — including after it relocates
the player wholesale mid-run — and a continuous per-frame displacement guard
rejects teleport-style "catching up". The task map generates its navmesh at
runtime (dynamic generation), so path-following works in the headless graded
world; the wave-3 spike (2026-07-30) proved this end to end on this box.

## Primary concept

- `basic-navigation` — NavMesh generation and the MoveTo flow
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/basic-navigation-in-unreal-engine)

The load-bearing concept is driving a character across a navmesh toward a
live, moving gameplay target — acquisition, pursuit, and re-acquisition —
rather than toward a remembered point.

## Prompt given to the agent

> The level contains an enemy character placed some distance from the player
> spawn. Bring it to life: from shortly after play begins, the enemy must
> detect the player-controlled character and move toward it, closing most of
> the starting gap within the first few seconds at a normal character ground
> speed (several hundred units per second — not a crawl, not a dash). It must
> keep pursuing the player's CURRENT position: if the player turns up
> somewhere else entirely, the enemy follows to where the player actually is
> now, not to where the player used to be. The enemy must MOVE there — walking
> a continuous path, never jumping or teleporting — and when the player stands
> still it should end up right next to them (within a few meters). The level
> already provides everything needed for characters to navigate. Implement in
> C++ in the existing gameplay module — do not edit the level, any config
> file, or any test file.

## Workspace state pre-task

Files that **exist** under `Source/ThirdPerson/`:

- The stock UE 5.8 Third Person C++ template sources. No edit needed.
- `Tasks/t2-npc-follows-player/ChaserNpcCharacter.h` / `.cpp` — declares and
  defines `class THIRDPERSON_API AChaserNpcCharacter : public ACharacter`,
  the placed enemy body. The constructor adds `Tags.Add(FName("ChaserNpc"))`
  and nothing else — **no controller logic and no movement logic ship**; the
  behavior is entirely the agent's to implement. Edit this type in place (its
  class defaults reach the placed instance); do not rename the class — a
  placed instance of it is graded.
- `Tasks/t2-npc-follows-player/FollowHeroCharacter.h` / `.cpp` — the playable
  character (tag `FollowHero`) the map's game mode spawns and possesses at
  the PlayerStart. It IS the player character in the running level; it needs
  no code for this task.
- `Tasks/t2-npc-follows-player/FollowGameMode.h` / `.cpp` — the game mode the
  map's world settings select. No gameplay rules live here.
- `Content/Maps/t2-npc-follows-player/L_NpcFollow.umap` — a flat floor, a
  PlayerStart, one placed `AChaserNpcCharacter` (tagged `ChaserNpc`) ~1,600
  units away, one placed `ANpcFollowFunctionalTest`, and the level's
  navigation setup (a nav bounds volume + runtime-generated navmesh covering
  the floor).

Files that **do not exist**:

- No AI controller, no pursuit logic, no Blueprint subclass, no level edits.
  Solve in C++ in the existing gameplay module (new per-task files are fine).
- No test source in the agent's writable path. `ANpcFollowFunctionalTest`
  lives in a separate `CraftBenchTests` module the agent cannot read or
  modify.

## Verifier specification

The test runs in PIE from
`Content/Maps/t2-npc-follows-player/L_NpcFollow.umap` on the **ThirdPerson**
substrate. The engine ticks the world at a fixed deterministic step
(`-deterministic -FPS=60`). The map's game mode possesses the `FollowHero`
player character at the PlayerStart; the map's navmesh generates at runtime
(dynamic generation — proven headless in the 2026-07-30 spike).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64
        Development" and "ThirdPerson Win64 Development"
```

### L2 — AFunctionalTest behavioral trace

```text
ANpcFollowFunctionalTest (derives ACraftBenchFunctionalTest):
    PrepareTest():
        resolve the enemy via GetAllActorsWithTag("ChaserNpc"); assert
        exactly one (named failure: "... tagged 'ChaserNpc' ...")
        resolve the player via GetAllActorsWithTag("FollowHero"); assert
        exactly one, and that it is a Character
        SetCheckpointSchedule({1.0, 4.0, 5.0, 9.5})
    Tick (every frame, after the base checkpoint clock):
        once armed (cp0): CONTINUOUS displacement guard on the enemy — a
        single-frame step > 50uu FAILs immediately ("moved by a
        discontinuous jump"); a walking character at 600uu/s steps 10uu
        per 60Hz frame
        while driving (cp1..cp2): AddMovementInput on the HERO along the
        fixture-chosen escape direction (input is consumed per frame)
    OnCheckpoint(i):  // Distance = |enemy - player| (2D)
        cp0 t=1.0:  assert Distance >= 800 (the enemy did not start on the
                    player, nor close the gap faster than a normal ground
                    move); record D0; arm the guard
        cp1 t=4.0:  assert Distance <= 0.55 * D0 (the follow gate); then
                    RELOCATE the hero to the fixture-chosen far spot and
                    start driving it away
        cp2 t=5.0:  stop driving (the hero walked ~500uu from the spot)
        cp3 t=9.5:  assert Distance <= 350 (re-acquired the CURRENT
                    position) -> Succeeded
    every checkpoint logs "[t2-npcfollow calib] cp<i> t=<t> dist=<d>
    npc=(x,y) hero=(x,y)" (LogTemp/Display) for tolerance calibration.
```

**Pass criteria**: both L1 targets and L2 green. **Robust identity**: enemy
and player are resolved by tag, never by class; the follow gate is a RATIO of
the run's own measured starting distance, never an absolute.

## Reference solution metadata

- LOC range: 55-75 (a small AI controller with a periodic re-issue chase
  loop + two class-default lines wiring it onto the placed enemy)
- Files touched: 4 (two new per-task controller files + the two pre-existing
  scaffold files)
- Senior-dev hours: under 1

## Anti-gaming notes

1. **Empty/partial submission.** *Failure mode*: the scaffold compiles with no
   pursuit logic; the placed enemy stands still forever; L1 passes.
   *Defense*: checkpoint 1 requires the enemy-to-player distance to have
   shrunk below a fraction of the run's measured starting distance; an inert
   enemy measures the full gap and FAILs via the named message `is not
   closing on the player`.
2. **Teleport instead of walking.** *Failure mode*: a timer (or tick) snaps
   the enemy to the player's position, so every sampled instant looks like a
   perfect chase. *Defense*: from the first checkpoint on, a continuous
   per-frame guard watches the enemy's displacement; any single-frame step
   larger than a legitimate walk step FAILs immediately via `moved by a
   discontinuous jump` — there is no sampling window to thread.
3. **Following the player's STARTING spot instead of the player.** *Failure
   mode*: the enemy reads the player's position once (BeginPlay or first
   tick) and forever moves to that stale location; against a stationary
   manual test it is indistinguishable from a real chase. *Defense*: after
   the follow gate, the fixture relocates the player wholesale to a
   fixture-chosen far spot and then walks it further; checkpoint 3 requires
   the enemy to be next to the player's CURRENT position and FAILs via
   `never re-acquired the moved player`.
4. **Spawning on (or next to) the player — or a super-speed dash.** *Failure
   mode*: the enemy is moved onto the player at BeginPlay (or crosses the
   whole gap at far beyond a normal ground speed), satisfying any "ends up
   close" check without ever following at the disclosed pace. *Defense*:
   checkpoint 0 requires the enemy to still be FAR from the player shortly
   after play begins — anything that closed the ~1,600-unit gap within the
   first second was either started on the player or moving several times
   faster than the disclosed pace — and FAILs via `already next to the
   player at the start`.
5. **Test disabling / environment repointing.** *Failure mode*: agent edits
   the fixture, the map, or config to weaken the gate. *Defense*:
   `Source/CraftBenchTests/` is sandbox-denied (submission files under it are
   rejected pre-grade), the runner materializes the graded substrate from git
   HEAD (an on-disk edit never reaches the grade; committed changes are
   review-gated on commit), and `Config/` + `Content/Maps/` are deny-listed.

## Hidden invariants

- The checkpoint instants, the relocation spot, the escape walk (direction
  and duration), the 0.55 follow ratio, the 350uu re-acquisition tolerance,
  and the 50uu/frame continuity threshold are all undisclosed. The
  anti-teleport defense is not a sampling instant but a continuous per-frame
  guard from cp0 on.
- The hero is relocated AND then walked, so a solution that re-reads the
  player's position exactly once when it notices the jump still ends ~500
  units short of the player's final spot and fails the re-acquisition gate —
  only continuous pursuit of the live target passes.
- An engine move request tracks its goal only while it is IN FLIGHT — it
  COMPLETES when the enemy first reaches the player (~2.5s in on this map),
  and a completed request tracks nothing. A solution that issues one request
  and never re-arms therefore has no active pursuit when the player is
  relocated, and fails the re-acquisition gate. Continuous following requires
  keeping the pursuit alive — re-issuing on completion, re-arming from a
  completion callback, or a periodic re-issue loop; the gate judges the
  behavior, not which of those shapes is chosen.
