# Discrimination matrix — t2-npc-follows-player

The self-validation oracle: the reference solution must PASS and every gaming
variant + the empty leg must FAIL **at the predicted checkpoint, via the named
assertion**. A wrong-reason FAIL (compile error, wrong checkpoint, filter-miss/
0-tests, SANDBOX-REJECT exit 4) means the verifier is NOT discriminated — fix
it, or relabel the task for the weaker property it actually tests.

**ASCII rule:** every expected-message substring below is ASCII-only. The UE
log's UTF-8 bytes are read back as cp1252, so an em dash in a fixture message
becomes mojibake and the substring grep misses — a correct FAIL then
misclassifies as wrong-reason (live incident, t2-homing-projectile 2026-07-21).

## Layout (folder-local under `tasks/cpp/t2-npc-follows-player/`; agent-writable prefixes only — a stray root file → SANDBOX-REJECT exit 4)
- `../reference/Source/ThirdPerson/Tasks/t2-npc-follows-player/…` — the one
  correct solution (mirrors the writable path INCLUDING the per-task segment;
  ThirdPerson substrate — the agent-writable module is `Source/ThirdPerson/`).
- `<variant>/Source/ThirdPerson/Tasks/t2-npc-follows-player/…` — one dir per
  anti-gaming note, sibling to this MATRIX.md.
- empty leg — run IMPLICITLY by `cb discriminate` (it creates a throwaway
  empty dir; nothing to author). The row below documents its expected
  first-gate failure substring.

## Matrix
| Submission | Overall | Fails at | Expected message (substring) | Anti-gaming note |
|---|---|---|---|---|
| `../reference` | PASS | — | all checkpoints green | — |
| empty | FAIL | checkpoint 1 (t=4.0s) | `is not closing on the player` | #1 / FR-017 |
| `teleports-to-player/` | FAIL | continuous guard (t=1.5s, first snap) | `moved by a discontinuous jump` | #2 teleport instead of walking |
| `goes-to-original-spot/` | FAIL | checkpoint 3 (t=9.5s) | `never re-acquired the moved player` | #3 stale-location pursuit |
| `stops-after-brief-follow/` | FAIL | checkpoint 3 (t=9.5s) | `never re-acquired the moved player` | #3 (give-up shape) |

Coverage note: `goes-to-original-spot/` and `stops-after-brief-follow/`
deliberately share cp3's credited substring (the teleport task's shared-pair
precedent) — both model "stops tracking the live player", by caching a stale
location vs aborting outright; their calib lines differ (the cacher sits at
the hero's ORIGINAL spot, the quitter mid-floor where it gave up at t=3.0).
Anti-gaming note #4 (spawn-on-player / dash) is argued from cp0's named
assertion `already next to the player at the start` — a variant would be a
one-line SetActorLocation in BeginPlay and dies trivially there; not shipped
as a folder. The guard's residual, stated honestly: sliding in steps
<= 50uu/frame IS accepted, and at the 60Hz step that is up to ~2,940uu/s —
about 5x FASTER than the legitimate 600uu/s ground move — so the continuity
guard alone does not bound speed. The remaining bounds are cp0's
start-distance floor (a slider moving from play start at that rate closes the
1,615uu gap in ~0.55s and dies at cp0; only one that waits until after
cp0=1.0s to start sliding threads it) and the prompt's disclosed
"several hundred units per second - not a dash" pace clause. A sub-guard
slider in the ~850-2,940uu/s band that starts after cp0 is an accepted
residual of this fixture.

## How to run (deterministic verifier, no agent, no tokens)
```sh
cb discriminate --task cpp/t2-npc-follows-player          # committed task
cb discriminate --task cpp/t2-npc-follows-player --wip    # while fixture/map are uncommitted
```
Per-leg fallback while iterating on one variant (short `--workdir` dodges
Windows MAX_PATH; UE root per this box's `.env` / `CB_UE_ROOT`):
```sh
py -3.12 tools/verify-single/run_task.py \
    --task tasks/cpp/t2-npc-follows-player/task.md \
    --submission tasks/cpp/t2-npc-follows-player/discrimination/goes-to-original-spot \
    --ue-root "$CB_UE_ROOT" --substrate-from-live --workdir C:\cb\wd\npcf   # expect exit 1
```
Open the workdir `report.json` / `l2_pie.log` and confirm the L2 failure
message matches the "Expected message" cell for each FAIL row.

## Status
- Authored 2026-07-30 (text half + adversarial-review fixes same day).
- **EXECUTED 2026-07-30**: `cb discriminate --task cpp/t2-npc-follows-player --wip` =
  **discriminated: YES** — reference PASS; empty, teleports-to-player, goes-to-original-spot, stops-after-brief-follow all FAIL (5/5), each `[ok ]` (credited via its named
  substring). Calibration record in ../notes.md.

## Requirements table (checklist §7, the mandatory soundness artifact)

Every backticked L2 span is a contiguous `FinishTest(EFunctionalTestResult::Failed, ...)` source literal in
`UE-projects/ThirdPerson/Source/CraftBenchTests/Tasks/t2-npc-follows-player/NpcFollowFunctionalTest.cpp`
(never spanning a printf placeholder; ASCII-only per the cp1252 log read-back rule). Structural rows cite
`UE-projects/ThirdPerson/AGENT_WRITABLE.json` prefixes enforced by `tools/verify-single/sandbox.py` /
`config_lane.py` (SANDBOX-REJECT, exit 4). The L1 target names are runtime-COMPOSED, not source literals:
`tools/verify-single/layers/l1_build.py` builds `targets = (f"{game_module}Editor", game_module)` (line 273)
and invokes UBT with platform `"Win64"` (line 142) at configuration `"Development"` (line 405), with
`"game_module": "ThirdPerson"` read from the substrate manifest — rows citing those emitted target names are
marked "(composed)". Layers are `[L1, L2]` — this task has no L2I grader, so there is
no check-id family; the two gate families here are the L1 UBT build and the L2 fixture assertions.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | "the level contains an enemy character … bring it to life" — the PLACED enemy is the body graded (present, unique, never destroyed) | fully | resolve gate — `Expected exactly one actor tagged 'ChaserNpc' (the enemy) in the running level; found ` — plus the per-checkpoint validity re-check `is no longer valid (neither may be destroyed)` | unconditional (first gate, PrepareTest) | subclassing the placed C++ class is deliberately legal (the ctor-stamped tag inherits); spawning extra UNtagged helper actors (an AI controller, waypoints) is free |
| 2 | "the player-controlled character" is pursued — implicit: the possessed player is left intact (not destroyed, duplicated, or swapped for a decoy) | fully | resolve gate — `Expected exactly one actor tagged 'FollowHero' (the game-mode-possessed player character) in the running level; found ` (a hero that is no longer a Character dies on the adjacent `is not a Character` harness-precondition arm) | row 1 failed (test already finished) | nothing behavioral — possession itself is the map/game-mode's job, not gated beyond the tag + Character checks |
| 3 | enemy is "placed some distance from the player spawn" and must CLOSE that gap — it may not begin on (or be snapped to) the player, nor cross the whole gap inside the first second | fully | checkpoint 0 (t=1.0) — `already next to the player at the start - it began on top of the player` (floor: 2D distance >= 800uu against the ~1,615uu authored gap) | rows 1–2 failed | standing perfectly still through cp0 is fine (cp0 is a floor, not a motion demand); a mover that closes up to ~815uu inside the first second still passes the floor |
| 4 | "from shortly after play begins, the enemy must detect the player … and move toward it, closing most of the starting gap within the first few seconds" | fully | checkpoint 1 (t=4.0) — `is not closing on the player (distance ` (gate: distance <= 0.55 x the run-measured cp0 distance — a RATIO, never an absolute) | cp0 failed (run ends at the first tripped gate) | "most" is graded generously: closing only ~45% of the gap passes; the detection MECHANISM (perception, tick poll, event) is deliberately free — behavior-only |
| 5 | "at a normal character ground speed (several hundred units per second — … not a crawl)" — the speed floor | partially | same cp1 gate — `is not closing on the player (distance ` (0.45 x ~1,615uu over the 3.0s cp0→cp1 window implies an effective floor of only ~242uu/s) | cp0 failed | an effective pace as low as ~242uu/s passes — below the prompt's "several hundred"; the floor rejects a crawl, not a slow walk |
| 6 | "not a dash" — the speed ceiling | partially | checkpoint 0 floor (`already next to the player at the start - it began on top of the player`) + the per-frame continuity guard (`moved by a discontinuous jump (`, fails only on a single-frame step strictly > 50uu, so up to 50uu/frame = ~3,000uu/s continuous at the deterministic 60Hz step) | guard armed only from cp0 (t=1.0) on; cp0 skipped per rows 1–2 | the documented accepted residual: a slider that waits out cp0 and then moves in steps of at most 50uu/frame anywhere in the ~850–3,000uu/s band threads both gates (see this file's coverage note) — the ceiling is bounded, not tight |
| 7 | "keep pursuing the player's CURRENT position: if the player turns up somewhere else entirely, the enemy follows to where the player actually is now, not to where the player used to be" | fully | checkpoint 3 (t=9.5) — `never re-acquired the moved player (distance ` (the fixture relocates the hero wholesale at cp1 to a far spot, then WALKS it ~500uu further until cp2 — a one-shot re-read at relocation time still ends ~500uu short and fails here) | cp1 failed (test already finished) | the pursuit SHAPE is free (re-issue loop, completion callback, per-tick MoveTo); up to 350uu of standing separation is tolerated |
| 8 | "the enemy must MOVE there — … never jumping or teleporting" (continuous path) | fully, per-FRAME from cp0 on | continuity guard in Tick — `moved by a discontinuous jump (` (any single-frame 2D step > 50uu FAILs immediately; evaluated BEFORE the base checkpoint clock so the final crossing frame is covered — no sampling window to thread) | before cp0 arms (t < 1.0s: spawn/settle noise window); only the NPC is guarded (the HERO is fixture-relocated by design) | a teleport inside the first second that still lands >= 800uu from the player is unobserved; the guard and every distance gate are 2D (`Dist2D`), so purely VERTICAL relocation is invisible — though Z buys nothing against the 2D distance gates |
| 9 | "walking a continuous path" + "the level already provides everything needed for characters to navigate" — i.e. grounded, navigation-driven locomotion | **NOT ASSERTED** | — no gate inspects movement mode, floor contact, or navmesh/path usage; the only motion constraints are the 2D continuity cap (row 8) and the distance windows | — | a hovering/flying pawn, a root-motion slide, or a hand-rolled per-tick position lerp that stays under 50uu/frame and hits the distance windows passes every gate — "walking" and "navigate" are enforced only as dressing |
| 10 | "when the player stands still it should end up right next to them (within a few meters)" | fully | same checkpoint 3 gate — `never re-acquired the moved player (distance ` (the hero stands still from cp2 t=5.0; at t=9.5 the enemy must be within 350uu — 3.5m — of it) | cp1 failed | parking a full ~3.5m away passes ("a few meters" is honored at its generous edge — deliberately absorbs the path-follow acceptance radius + capsule separation + one re-issue period of drift) |
| 11 | "implement in C++ in the existing gameplay module" (and it must compile) | structurally | L1 gate (composed) — UBT must exit 0 for BOTH targets built by `targets = (f"{game_module}Editor", game_module)` at `"Win64"` `"Development"` (`tools/verify-single/layers/l1_build.py`) with `"game_module": "ThirdPerson"` from the manifest — i.e. the emitted targets ThirdPersonEditor / ThirdPerson, Win64 Development (short-circuits on first failure); sandbox `writable` names only `"Source/ThirdPerson/"` as a source prefix, and the placed instance IS the C++ class, so only C++ edits reach its behavior | unconditional (L1 is the first layer; sandbox runs pre-grade) | auxiliary `.uasset` content under `"Content/Tasks/"` (and the other `asset_writable` prefixes) is path-accepted, so a hybrid C++-plus-asset solution passes — "in C++" is forced only in the sense that no other route reaches the placed actor; new per-task files are explicitly allowed by the prompt |
| 12 | "do not edit the level" | fully, structurally | sandbox deny — `"Content/Maps/"` is a deny prefix (SANDBOX-REJECT, exit 4, pre-grade); an OFPA mirror of the task map (a path under Content/__ExternalActors__/Maps/, un-backticked — illustrative, not a manifest literal) rejects by allowlist-miss (only `Content/__ExternalActors__/Tasks/` and `Content/__ExternalObjects__/Tasks/` are `asset_writable`) | unconditional | nothing — the graded map is materialized from git HEAD, so even an on-disk edit never reaches the grade |
| 13 | "do not edit … any config file" | fully, structurally | config lane — `Config/` files reject by allowlist-miss except the two `config_writable` rel-paths (`Config/DefaultEngine.ini`, `Config/DefaultInput.ini`), which are path-accepted then diff-validated against this spec's `config_allow` — **this task declares none**, so ANY ini change yields `config change not allowed` and rides the exit-4 path (`config_lane.py::validate_config_submission`) | unconditional | resubmitting a byte-identical ini (empty diff) is accepted and harmless — nothing behavioral leaks through |
| 14 | "do not edit … any test file" | fully, structurally | sandbox deny — `"Source/CraftBenchTests/"` is a deny prefix (exit 4), and the runner materializes the graded substrate from git HEAD, so an on-disk fixture edit never reaches the grade; a committed edit is review-gated on commit | unconditional | nothing |

Holes found (rows above marked NOT ASSERTED — escalation candidates, not papered over):

- **Row 9 — grounded/nav-driven "walking" is not asserted.** Any 2D-continuous mover (flying, hovering,
  hand-rolled lerp) under 50uu/frame passes every gate. Defensible under the behavior-only law (the graded
  concept is live-target pursuit, not locomotion mode), but the prompt's "walking a continuous path" promises
  more than the fixture checks; either soften the prompt clause or accept-and-document alongside the existing
  slider residual (row 6 / the coverage note above).
