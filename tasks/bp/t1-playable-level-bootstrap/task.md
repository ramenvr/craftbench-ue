---
id: t1-playable-level-bootstrap
substrate: ThirdPerson
set: bp
tier: T1
capability_bucket: Gameplay Programming
category: gameplay
layers: [L1, L2I]
introspect: [kp_playable_level_bootstrap.py]
---

# t1-playable-level-bootstrap

A `bp`-basket, **outcome-graded** editor/asset task on the headless map-load
L2I lane proven by `kp-spawn-level-actors`: the deliverable is the resulting
editor state — one saved level plus the two Blueprint assets its world
settings wire in — graded by a deterministic verifier-owned introspect
script. Any authoring route (editor by hand, editor scripting, MCP asset
lane) earns the same PASS; no gate asserts how the state was produced.

### Provenance and deliberate divergences from the source row

Ported from a retired internal task list: a level-setup row, previously parked
as unbuilt because "the graded level would have to be agent-authored, and no
lane could grade an agent-authored level". That obstacle is **dissolved** by
the proven agent-authored-level L2I lane (`kp-spawn-level-actors` precedent —
headless three-route level load, refgate-proven).

**DISTINCT from `kp-spawn-level-actors`** (recorded so the two are never
mistaken for duplicates): that task grades *exact actor transforms* — bulk
placement precision. THIS task grades *playable-bootstrap wiring* — the
game-mode override chain (level world settings → agent-authored rules class →
agent-authored pawn class) plus start placement, and covers the previously
uncovered `game-mode-and-game-state` concept. The floor here is a coarse
heuristic band, deliberately NOT a transform gate.

> **Note on the behavior-only rule (Hard Rule #2).** Like the other
> asset-deliverable tasks, this spec names the concrete deliverable folder
> and level name, and the graded numbers (the exactly-one count, the floor
> footprint and band) — the standard, precedented exception: paths, names
> and graded values are workspace inputs/outputs. Everything else stays
> behavior-only: **no engine class, asset-type, or settings-panel name
> appears in the prompt.** The rules object is described by what the engine
> consults it for; the spawn marker by what the engine does with it; the
> authored assets by where they must live.

## Primary concept

- `game-mode-and-game-state` — Game Mode and Game State
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/game-mode-and-game-state-in-unreal-engine)

The load-bearing capability is **wiring a playable bootstrap**: a per-level
game-rules override that resolves to an authored rules class whose default
pawn resolves to an authored pawn class. Adjacent concepts (not primary):
`setting-up-a-game-mode` — Setting Up a Game Mode
(https://dev.epicgames.com/documentation/en-us/unreal-engine/setting-up-a-game-mode-in-unreal-engine),
the how-to this outcome exercises; `player-start-actor` — Player Start Actor
(https://dev.epicgames.com/documentation/en-us/unreal-engine/player-start-actor-in-unreal-engine),
the placement half; `ps-levels` — Levels
(https://dev.epicgames.com/documentation/en-us/unreal-engine/levels-in-unreal-engine),
the container being authored and saved.

## Prompt given to the agent

> The folder `Content/Tasks/t1-playable-level-bootstrap/` is empty. Produce
> one saved level asset in that folder, named `L_PlayableBootstrap`, plus the
> supporting assets described below — every asset you author for this task
> must be saved in that same folder. The level must be a minimal,
> self-contained playable bootstrap:
>
> - **The level carries its own play rules.** The level itself — not the
>   project — must declare the ruleset the engine consults when a play
>   session starts in this level: a per-level override, so that playing this
>   level uses your rules while every other level keeps the project default.
>   That ruleset must be an asset you author, saved in the task folder.
> - **Your rules name the player's body.** Your ruleset must name, as the
>   default controllable body handed to the player at the moment play
>   begins, a second asset you author in the task folder. Building it on top
>   of the playable character the project already ships is fine and expected
>   (see the workspace state).
> - **Exactly one spawn marker.** The level contains exactly one of the
>   standard markers the engine consults when it decides where the player
>   appears at play start — no more, no fewer.
> - **Solid ground under the marker.** Directly under the marker's position
>   there is real, collision-carrying ground to land on: a surface at least
>   200 units across in each horizontal direction, whose top sits between 10
>   units above and 500 units below the marker.
>
> Save everything to disk. A fresh checkout that opens your level and starts
> play must get your rules, your body, your spawn point and your floor, with
> no project-wide setting touched.

## Workspace state pre-task

Substrate content that **exists** under
`Content/Tasks/t1-playable-level-bootstrap/`:

- Nothing. This task ships **no baseline asset**. The folder is the
  agent-writable Content carve-out of the `ThirdPerson` substrate
  (`UE-projects/ThirdPerson/AGENT_WRITABLE.json` lists `Content/Tasks/`
  under both `writable` and `asset_writable`); fairness isolation keeps this
  task's folder while hiding every other task's.

Substrate content the agent starts with (read-only inputs it may build on):

- The stock third-person playable character: the C++ class in
  `Source/ThirdPerson/ThirdPersonCharacter.h/.cpp` and its Blueprint at
  `/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter`. Either may be used
  as the **parent** of the authored body asset; the folder they live in is
  deny-listed for writing, so the authored asset itself must land in the
  task folder.

Files that **do not exist** (the agent must create):

- `Content/Tasks/t1-playable-level-bootstrap/L_PlayableBootstrap.umap` —
  plus, if the project saves levels One-File-Per-Actor, the actor files the
  editor writes under
  `Content/__ExternalActors__/Tasks/t1-playable-level-bootstrap/` and
  `Content/__ExternalObjects__/Tasks/t1-playable-level-bootstrap/`. All
  three prefixes are `asset_writable` (the 2026-07-29 level-deliverable
  carve-out), so the saved level is submittable either way.
- The two authored assets (the ruleset and the body) under
  `Content/Tasks/t1-playable-level-bootstrap/`. Their asset **names are the
  agent's choice** — the verifier resolves them through the level's own
  wiring, never by name.

Out of scope / not needed:

- No C++ is required or expected. `Content/Maps/`, `Config/`,
  `Content/ThirdPerson/`, `Content/Characters/` and `Content/Input/` are
  deny-listed — the agent neither can nor needs to touch them. In
  particular, the project-wide default rules stay untouched: the graded
  override lives **in the level**. The verifier never opens any map other
  than the one the agent saves.

## Verifier specification

Layer choice: this task grades via **L1 + L2I**. Every graded property is a
static property of saved assets (the level's world-settings wiring, two
Blueprint class facts each, one actor count, one geometric heuristic), read
by verifier-owned editor-Python reflection after loading the submitted level
headless. L2 is deliberately **not** declared: nothing is observed over
time, and an L2 fixture must live in a committed `Content/Maps/` map — this
task's whole point is that the AGENT authors the map. L3 is not declared: no
rendering assertion (and `-nullrhi` uploads no pixels anyway).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

The submission is content-only, so L1 is a precondition (the project and its
Asset Registry must load cleanly), never a correctness signal.

### L2I — Structural assertion

The verifier-owned script
`tools/verify-single/introspect/kp_playable_level_bootstrap.py` runs
headless via `UnrealEditor-Cmd -ExecutePythonScript=` under `-nullrhi`,
read-only, and prints one `CRAFTBENCH-INTROSPECT-JSON` verdict block. It
emits **exactly 12 named checks on every leg** (constant denominator — the
reported `tests_passed/tests_run` is comparable across submissions and a
submission cannot improve its ratio by making checks unreachable). PASS
requires all 12:

```text
level_asset_exists            /Game/Tasks/t1-playable-level-bootstrap/L_PlayableBootstrap resolves
level_opens_with_actors       the level loads headless AND enumerates a non-empty
                              actor list (an empty enumeration is a graded FAIL)
world_settings_resolved       the loaded level's world-settings object resolves
gamemode_override_present     its per-level game-rules override is set (non-None)
gamemode_is_task_blueprint    the override resolves to a Blueprint-generated class
                              whose path starts /Game/Tasks/t1-playable-level-bootstrap/
gamemode_is_gamemode_subclass its CDO IS a game-rules class (isinstance
                              GameModeBase, subclass-tolerant, tri-state)
default_pawn_class_present    that CDO's default pawn class is set (non-None)
default_pawn_is_task_blueprint the pawn class is a Blueprint-generated class
                              under the same task prefix
default_pawn_is_pawn_subclass its CDO IS a possessable pawn (isinstance Pawn —
                              subclassing the stock character passes by design)
player_start_exactly_one      exactly one player spawn marker in the level
floor_candidate_present       some actor's COLLIDING bounds span >= 100 units
                              half-extent on both horizontal axes
floor_under_player_start      one such candidate contains the marker's X,Y
                              (with a 50-unit margin) and its top is within
                              [-10, +500] units below the marker
```

**Disclosed vs verifier-only numbers.** The prompt disclosed everything
gated as a demand: the folder, the level name, the exactly-one count, the
200-units-across footprint, the 10-above/500-below band. Verifier-only: the
50-unit XY containment margin (pure generosity). All constants live pinned
in the introspect script's constants block (mirrored in `notes.md`).

**The level load rides the PROVEN map-load lane.** `layers/l2_introspect.py`
builds the editor command line with **no map argument**, so the script opens
the submitted level itself through the exemplar three-route loader
(`LevelEditorSubsystem.load_level`, `EditorLoadingAndSavingUtils.load_map`,
`EditorLevelLibrary.load_level` — the route the kp-spawn / audit refgates
proved live under `-nullrhi`, 2026-08-11/12). It fails closed and keeps the
two failure classes apart: a level that *refuses to open* is the graded
`BOOT_LEVEL_LOAD_FAILED path=`, a *broken probe* (every route raising) is
`BOOT_LEVEL_LOAD_PROBE_ERROR`, an error token no MATRIX row credits — a
harness break is never attributed to the agent.

**Read routes** (each wrapped, multi-spelling, fail-closed):

- *asset existence* — `unreal.EditorAssetLibrary.does_asset_exist`.
- *identity* — **pre-declared content path and the wiring the level itself
  declares** (world settings → rules class → pawn class), never asset-name
  scanning, never actor labels. Class is consulted only as an assertion,
  `isinstance`-style, subclass-tolerant, tri-state (an unexposed type FAILS
  the check).
- *world settings* — three routes: the world's `get_world_settings` method,
  the reflected `persistent_level.world_settings` chain, a `WorldSettings`
  actor scan. The override is the reflected `default_game_mode` property.
- *CDO reads* — `unreal.get_default_object(cls)` ONLY (the module function;
  the instance-method spelling resolves against the wrong class and is a
  known poison — refgate catch 2026-08-12). Pawn wiring is the reflected
  `default_pawn_class` property.
- *authored-asset gate* — class object path must start with
  `/Game/Tasks/t1-playable-level-bootstrap/` AND the class must be
  Blueprint-generated. Native classes (`/Script/...`) and stock content
  (`/Game/ThirdPerson/...`) both fail the same prefix gate.
- *spawn marker* — count of actors `isinstance` the spawn-marker type
  (subclass-tolerant; the marker is engine-placed identity, not label-keyed).
- *floor* — per-actor `get_actor_bounds(only_colliding_components=True)`:
  collision truth (a no-collision decoration reports a zero colliding
  extent). Candidate = both horizontal half-extents >= 100; the under-start
  gate then needs X,Y containment (+50 margin) and floor-top in the
  [-10, +500] band below the marker.

**Every graded fact excludes the value an untouched or lazy delivery gets
for free** (the dead-gate audit):

| gate | free/untouched value | graded demand | free value inside the gate? |
|---|---|---|---|
| game-rules override | None on a fresh level | set | **no** |
| override class origin | project default is NOT read; stock BP lives under `/Game/ThirdPerson/` | task-folder Blueprint | **no** |
| default pawn presence | **non-None for free** (a fresh rules class seeds the engine's built-in stand-in pawn) — presence alone would be a DEAD gate | — | (dead alone — see next row) |
| default pawn origin | the built-in stand-in is a `/Script/` native class | task-folder Blueprint | **no** (this is the live gate) |
| spawn markers | 0 in a fresh level | exactly 1 | **no** |
| floor | none; a no-collision mesh has zero colliding extent | collidable, >=200 across, in-band under the marker | **no** |

**Score granularity.** `registry.py` sets `tests_run`/`tests_passed` from
the per-check counts, so `report.json` carries `x/12` for this task. That
number is reported, not gating — `overall` stays `all(status == "pass")`.

**The visual, and where it is allowed to live.** A `--visible` run on the saved
level shows the bootstrap for a human; no screenshot, no pixel comparison,
no LLM judge reaches `overall` (FR-020d).

## Reference solution metadata

- LOC range: **0** shipped lines of code. The natural route is a short
  throwaway editor-scripting session (or ~5 minutes of editor UI): author
  two Blueprint assets (rules + body, property wiring only — no event-graph
  logic is needed or graded), set one world-settings property, place two
  actors, save.
- Files touched: 3 created (`L_PlayableBootstrap.umap` + 2 `.uasset`) plus
  any One-File-Per-Actor mirrors the editor writes — the authoring-lane run
  pins the real count in `notes.md`.
- Senior-dev hours: 0.25–0.5 (this is deliberately the floor of T1 — the
  wiring chain, not volume, is the content).

## Anti-gaming notes

Per the amended checklist §7 (2026-08-11), each note names its defense with
a resolvable pointer — the check id, its named failure token, and the
requirements-table row in `discrimination/MATRIX.md` that carries the
file:line anchor.

1. **Empty or partial delivery.** *Failure mode*: no level, or a level with
   nothing wired, banking on presence-shaped checks passing vacuously.
   *Defense*: FAIL-on-empty at every stage — a missing level fails all 12
   via `level_asset_exists` (`BOOT_LEVEL_MISSING /Game/Tasks/`), an empty
   enumeration is the graded `BOOT_ACTOR_LIST_EMPTY`, a fresh level's
   override is None (`BOOT_GAMEMODE_OVERRIDE_NONE`), and the constant
   12-check denominator means unreachable checks still score as failures.
   MATRIX rows 1–3.
2. **Point the override at existing content instead of authoring.** *Failure
   mode*: the level's override names the substrate's stock game-mode
   Blueprint (`/Game/ThirdPerson/...`) or a native engine class — zero
   authoring, wiring looks set. *Defense*: `gamemode_is_task_blueprint`
   requires a Blueprint-generated class whose object path starts with
   `/Game/Tasks/t1-playable-level-bootstrap/`
   (`BOOT_GAMEMODE_NOT_TASK_ASSET class_path=`); stock and native classes
   both fail the prefix. Same gate on the pawn side
   (`BOOT_PAWN_NOT_TASK_ASSET class_path=`). MATRIX rows 5, 8.
3. **Author the ruleset but never touch the pawn resolution.** *Failure
   mode*: a fresh rules class already carries a non-None default pawn (the
   engine's built-in stand-in), so a naive presence check would pass with
   zero pawn work — the classic dead gate. *Defense*: the presence gate is
   deliberately NOT the live gate; `default_pawn_is_task_blueprint` fails
   the built-in stand-in on its `/Script/` path
   (`BOOT_PAWN_NOT_TASK_ASSET class_path=`), and
   `default_pawn_is_pawn_subclass` separately rejects a non-pawn asset
   wired in to dodge that (`BOOT_PAWN_NOT_PAWN_CLASS class=`). MATRIX
   rows 7–9 and the dead-gate table above.
4. **Marker spam.** *Failure mode*: scatter several spawn markers so at
   least one lands somewhere favorable. *Defense*:
   `player_start_exactly_one` is an exact count over a subclass-tolerant
   type scan — zero is `BOOT_START_MISSING count=0`, more than one is
   `BOOT_START_COUNT_WRONG count=` — and the floor gate is evaluated against
   THE unique marker, so there is no favorable-one to pick. MATRIX row 10.
5. **Fake floor.** *Failure mode*: a huge no-collision decorative mesh under
   the marker (looks right in the viewport), or a tiny/elsewhere collidable
   prop. *Defense*: bounds are read with colliding-components-only, so a
   no-collision mesh reports a ZERO colliding extent and fails the footprint
   gate (`BOOT_FLOOR_NO_CANDIDATE examined=`); a collidable prop that is
   small, offset, or out of band fails containment
   (`BOOT_FLOOR_NOT_UNDER_START start=`). MATRIX rows 11–12.

## Hidden invariants

- **The check denominator is fixed at 12 on every leg**, including the empty
  submission (which scores `0/12` — this task ships no baseline for any
  check to pass against). The crash-shaped "fewer checks ran, so the ratio
  looks better" path is closed by construction.
- **A failed prerequisite fans out carrying its own token.** A missing
  level, an unset override, an unresolvable CDO, or a non-unique marker
  propagates its single root-cause detail into every dependent check — the
  matrix always attributes a failure to one cause instead of inventing
  verdicts against an object that was never validated.
- **Error tokens are disjoint from failure tokens.** Every exception path
  emits `*_PROBE_ERROR` / `*_READ_ERROR` / `*_ABORTED` /
  `CHECK_NOT_EVALUATED`, none of which appears in any MATRIX row — a broken
  UE API name can never be credited as a variant's named failure.
- **CDO reads use the module-function route only.** The instance-method
  spelling silently returns the wrong CDO and poisons every downstream
  read; this script never calls it (refgate catch 2026-08-12).
- **Every graded fact excludes the free value, by construction.** That is
  the dead-gate table in *Verifier specification*; the non-None
  fresh-ruleset default pawn is the documented near-miss any future edit
  must re-check.
