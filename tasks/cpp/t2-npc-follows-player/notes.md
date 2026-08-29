# t2-npc-follows-player — build contract + calibration notes

Task authoring notes (verifier-side; never agent-visible — this folder is not
part of any agent surface). Sourced from an earlier internal task list ("Enemy
NPC system"). The source row's verification cell ("play the
game and the NPC follows you around") is replaced by the authored criteria in
`task.md`; the "use a cube for the mesh" dressing is advisory and non-gating.
The behavior-tree route the source row mentions is deliberately NOT named in the
prompt (Hard Rule #2) — an agent may use a BT, a plain AI controller loop, or
manual steering; the gate judges distance over time only.

## Why this task is buildable headless (spike provenance)

The 2026-07-30 wave-3 spike proved, under the real L2 launch
shape (`-nullrhi -deterministic -FPS=60`):

- a Python-spawned `NavMeshBoundsVolume` + a Python-spawned `RecastNavMesh`
  with `runtime_generation = DYNAMIC`, saved in the map, produce WORKING nav
  data in headless PIE — no editor bake;
- `ProjectPointToNavigation` succeeds, `AAIController::MoveToActor` returns
  RequestSuccessful, and a possessed character path-follows 2,000uu to
  arrival (final distance 0).

The map recipe below is that spike's recipe verbatim. Treat the nav trio
(floor + bounds volume + dynamic RecastNavMesh) as LOAD-BEARING — a map
without the volume or with default (static) runtime generation has NO navmesh
in the graded world and the REFERENCE fails.

## Map contract (`aids/author_L_NpcFollow.py` — keep the two in sync)

| element | value | why |
|---|---|---|
| floor | engine cube, scale (40,20,1), center (1200,0,-48) | spans X [-800,3200], Y [-1000,1000], top at Z=+2 — room for the 1,615uu chase plus the 2,600uu re-acquisition leg |
| PlayerStart | (0,0,120), yaw 0 | hero spawns/settles ~(0,0,98) |
| AChaserNpcCharacter | placed at (1500,600,110) | settles ~(1500,600,90); 2D distance to hero ~1,615 (cp0 gate: >= 800) |
| NavMeshBoundsVolume | center (1200,0,200), scale (25,15,5) | default volume brush is a 200uu cube -> 5,000 x 3,000 x 1,000 — covers the whole floor |
| RecastNavMesh | anywhere; `runtime_generation = DYNAMIC` | the spike-proven runtime-generation lever; without it the volume alone builds nothing headless |
| fixture | (-400,-400,120) | off both walk lanes |
| GameModeOverride | `/Script/ThirdPerson.FollowGameMode` | possesses the `FollowHero`-tagged player at the PlayerStart |

## Timeline arithmetic (60Hz fixed dt)

- Enemy: plain `ACharacter` CMC default MaxWalkSpeed = 600uu/s -> 10uu/frame.
- Phase A (cp0=1.0 -> cp1=4.0, 3.0s): gap to close ~1,615 - ~170 (acceptance
  radius 100 + capsule separation) = ~1,445uu; at 600uu/s that is ~2.4s —
  the reference ARRIVES before cp1 and measures a ratio ~0.1 vs the 0.55
  gate. A slower legitimate mover that closed only half the gap still passes.
- cp1 relocation: hero -> (2600,-600,92); then driven along (-1,0,0) for
  1.0s at hero ground speed 500uu/s (stock ThirdPersonCharacter) -> final
  hero position ~(2100,-600), safely interior to floor and navmesh.
- Phase B (cp1=4.0 -> cp3=9.5, 5.5s): enemy is near the hero's OLD spot
  (~origin) at cp1; distance to the hero's final spot ~2,184uu -> ~3.6s at
  600uu/s + one 0.5s re-issue period + path repath latency; arrival ~t=8.2,
  1.3s of margin before cp3.
- Continuity guard: 50uu/frame = 5x the legitimate 10uu/frame step; the
  teleport variant's first snap (~1,300uu in one frame at t=1.5) exceeds it
  by 26x. Guard is ARMED AT cp0 so placed-actor gravity settle (a few uu)
  and possession-time adjustments before t=1.0 can never trip it.
- The guard threshold is FPS-DEPENDENT (frames, not seconds): valid for the
  `-FPS=60` leg only; re-derive before ever adding a different fps leg.

## Fixture design notes

- The fixture never touches AIModule — it reads positions and drives/moves
  the HERO only. The agent's chase machinery is theirs entirely.
- `AutoPossessAI` engine default is `PlacedInWorld` and `AIControllerClass`
  defaults to plain `AAIController` — so even the EMPTY leg's placed enemy
  gets a (do-nothing) AI controller at BeginPlay. Inert is exactly what the
  cp1 gate catches; the reference only swaps `AIControllerClass` (and pins
  `AutoPossessAI = PlacedInWorldOrSpawned` for explicitness). Placed-actor
  unedited properties read the class defaults at load, so a ctor-level swap
  reaches the placed instance — the same CDO mechanism the
  t1-default-cube-mesh-actor task graded live.
- An IN-FLIGHT `MoveToActor` request TRACKS a moving goal (path repathing
  follows the destination actor) — but the request COMPLETES when the NPC
  first reaches the hero (~t=2.5 on this map), and a completed request
  tracks nothing. A one-shot solution therefore has NO active pursuit when
  the hero is relocated at cp1 and dies at cp3 exactly like the give-up
  variant. Continuous following must keep the pursuit alive: re-issue on
  completion (an OnMoveCompleted re-arm) or a periodic re-issue loop (the
  reference's 0.5s timer). Consequence for variant design: the caching cheat
  caches a LOCATION (`goes-to-original-spot`), and the give-up cheat aborts
  and stops re-issuing (`stops-after-brief-follow`).
- The hero is BOTH relocated and then walked 500uu, so re-reading the player
  position exactly once at the jump still under-shoots cp3's 350uu tolerance
  by ~150uu. A solution re-issuing at any period <= ~0.7s passes comfortably.
- cp0's floor does DOUBLE DUTY: it catches spawn-on-player AND any mover
  fast enough to close the ~1,615uu gap inside the first second (>~850uu/s
  sustained) — the "dash" shape the prompt's pace clause excludes. The cp0
  failure message names both shapes.
- HARNESS-PRECONDITION `FinishTest(Error)` paths (no world; FollowHero
  resolved but not a Character): **today these still GRADE as agent FAIL**
  (automation Error lands as state Fail in index.json; l2_pie counts it).
  The prefix is the hook for a future runner-side exit-7 routing rule — do
  not claim otherwise.

## Calibration checklist (fill from the first live legs)

1. **Dynamic navmesh readiness by cp0=1.0s** — the spike observed nav data
   live at its cp0=1.0 on a same-sized map; confirm on THIS map (the calib
   line's cp1 distance collapsing is the signal). Fallback: shift the
   schedule right by 0.5s AND re-derive the cp0 floor in the same change —
   `KStartMinDistance = 800` is calibrated to the ~1,615uu authored gap AT
   cp0=1.0; by cp0=1.5 the reference itself has closed to ~800uu (zero
   margin), so a later cp0 needs a proportionally lower floor (or re-anchor
   it as a ratio of the authored distance).
2. **Reference phase-A arrival** — expect cp1 dist ~170 (ratio ~0.1); the
   0.55 gate has ~4x margin.
3. **Re-acquisition arrival by cp3=9.5** — expect ~t=8.2; if the calib line
   shows later, widen cp3 toward 10.5 (TimeLimit margin adjusts with it).
4. **Continuity guard false-trip sweep** — the reference must never exceed
   50uu/frame; watch the cp1 hero relocation frame (only the HERO jumps —
   the guard reads the NPC only) and nav path corner-cutting.
5. **Placed-NPC settle before cp0** — placed at Z=110, settles ~90; the
   guard arms at cp0 so settle is outside the guarded window by design.
6. **`AutoPossessAI` default possession** — confirmed from engine defaults
   (PlacedInWorld + AAIController); verify the empty leg logs no controller
   errors and simply stands still.
7. **Post-teleport recovery of a completed-then-reissued move** — the
   reference's phase-A request COMPLETES on arrival (~t=2.5); its 0.5s loop
   issues a FRESH `MoveToActor` within half a second of the cp1 relocation,
   which is why it re-acquires at all. Verify on the reference leg: the cp3
   calib line must show distance collapsed from ~2,668 (post-relocation) to
   <350 — that collapse IS the evidence the re-issue recovered the pursuit.

## Discrimination record

Not yet run — see `discrimination/MATRIX.md` §Status. To be filled from the
first `cb discriminate --wip` after the map lands: per-leg verdicts, the
calib line values at each checkpoint, and any re-timed checkpoints.

## Landing gate

Do NOT add this task to CATALOG/registry (or count claims) before (1) the
`.umap` + all sources are committed and (2) one full `cb discriminate` run
has filled the discrimination record above and MATRIX.md's Status.

## Calibration record — first live validation (2026-07-30)

Binary half + full matrix ran this date (Win11, UE 5.8, substrate=live via
`--wip`): **`cb discriminate` = discriminated: YES** — reference PASS; empty +
EVERY variant FAIL via its named MATRIX substring (`[ok ]` on all legs).
Editor-target builds of the scaffold/fixture C++ were clean; per-leg run dirs
not retained (no `--keep`) — the verdicts answer the checklist's yes/no items.

Wave-3 specifics: the runtime-DYNAMIC navmesh recipe (NavMeshBoundsVolume +
RecastNavMesh authored by the aids script) carried a real graded leg —
reference PASS proves nav data was live by cp0=1.0s and the agent-style
AIController re-issue loop re-acquired the teleported hero by cp3.
