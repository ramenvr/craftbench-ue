---
id: kp-spawn-level-actors
substrate: ThirdPerson
set: python
tier: T1
capability_bucket: Tools & Pipeline
category: other
layers: [L1, L2I]
introspect: [kp_spawn_level_actors.py]
---

# kp-spawn-level-actors

The first task of the `tasks/python/` basket (owner decision 2026-08-11):
**outcome-graded** editor-scripting work. The deliverable is the resulting
editor state — here, one saved level — graded by the same deterministic L2I
introspect lane as the `bp` basket. The prompt describes an outcome whose
exactness and volume (six actors, every one pinned to exact labels, meshes,
locations, scales and extents) make editor scripting the natural way to
complete it, but **no gate asserts that Python was used**: an agent that
places and types every value by hand through the details panel earns the same
PASS. A future v2 may additionally re-execute a submitted script; that is
deliberately not this version.

### Provenance and deliberate divergences from the source row

Imported from an earlier internal task list (not shipped): a level-setup row,
one of a group derived from observed editor-scripting-agent failures. The
source row's verification cell reads
*"Query editor state: all 6 actors exist with exact labels, meshes
(Cube/Sphere), locations and scales; level saved. Prints PASS/FAIL."* and its
start state is *"Empty Project"*.

Six deliberate divergences, each recorded so the source row and the task can be
reconciled (full detail in `notes.md`):

1. **A SAVED level asset replaces "the currently open editor level".** The
   source row grades transient open-level state, which is not a submittable
   artifact — the harness grades a file overlay materialized onto a clean
   substrate. The deliverable is re-pathed to the repo convention
   `/Game/Tasks/kp-spawn-level-actors/L_ActorLayout`, submittable since the
   2026-07-29 OFPA carve-out (`Content/__ExternalActors__/Tasks/` +
   `Content/__ExternalObjects__/Tasks/` are `asset_writable`).
2. **The nav bounds volume becomes a box collision region.** The source row asks
   for a navigation-bounds volume at scale (10, 10, 4). Brush-based volumes
   carry BSP brush geometry that stock editor Python cannot build, so a
   spawned one is an empty shell with no gradeable extent — and the graded
   capability (place an invisible volume with exact extents and label) does
   not need the nav system. The target becomes a box-shaped collision region
   whose scaled world extent is graded: (1000, 1000, 400) about center
   (0, 0, 200) — exactly the world-space box the source row's scale implies
   (default 200-unit brush x scale (10, 10, 4) = a 2000 x 2000 x 800 box).
3. **The "print a report" half is dropped.** Source row: *"report each actor's
   label and location"*. Session stdout is not a deliverable in the
   outcome-graded basket; the saved level IS the report. A v2 that re-executes
   submitted scripts may restore it.
4. **Labels re-slugged** (`EvalFloor` → `Floor`, `EvalPlayerStart` → `Start`,
   `EvalNavMesh` → `Bounds`, `EvalEnemy_01..03` → `Enemy_1..3`): the source row's
   `EvalPlayerStart` echoes an engine class name into an agent-visible
   literal, which Hard Rule #2 review would rightly flag.
5. **The floor moved off the origin** (source row: location (0, 0, 0)). The origin
   is what a naive spawn gets for free, so a floor-location gate at the origin
   is a dead gate. Moved to (0, 0, -50); every other source-row number that already
   excluded its free default is kept verbatim.
6. **The prompt is rewritten behavior-only.** The source row's prompt names
   `StaticMeshActor`, `PlayerStart`, `NavMeshBoundsVolume` and
   `StaticMeshComponent` verbatim; all of it is re-expressed as observable
   outcomes. The graded **numbers stay in the prompt** — that is this basket's
   point: the outcome demands exactness, and the verifier gates equality
   within tight verifier-only tolerances, not craft judgment.

> **Note on the behavior-only rule (Hard Rule #2).** Like
> `t1-dawn-fog-lighting-rig`, this task names the concrete deliverable asset
> path, the six actor labels the verifier keys on, and the two engine shape
> assets (`/Engine/BasicShapes/Cube`, `/Engine/BasicShapes/Sphere`) — the
> standard, precedented exception for asset-deliverable tasks: paths and
> names are workspace inputs/outputs, and naming them lets the verifier
> resolve one asset directly. Everything else stays behavior-only: **no actor
> or component class name appears in the prompt.** The spawn marker is
> described by what the engine does with it, the bounds object by what
> gameplay code could ask of it.

## Primary concept

- `ps-levels` — Levels
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/levels-in-unreal-engine)

The load-bearing capability is **populating and saving a level to an exact
specification**: creating a level asset at a demanded path and placing six
actors whose labels, meshes, transforms and extents all land on demanded
values. Adjacent concepts (not primary): `ps-actors` — Actors
(https://dev.epicgames.com/documentation/en-us/unreal-engine/actors-in-unreal-engine),
which every placement exercises, and `ps-scripting-editor-python` — Scripting
the Unreal Editor Using Python
(https://dev.epicgames.com/documentation/en-us/unreal-engine/scripting-the-unreal-editor-using-python),
the basket's natural-path skill — deliberately not gated (outcome-graded
basket law; see the header note).

## Prompt given to the agent

> The folder `Content/Tasks/kp-spawn-level-actors/` is empty. Produce one
> saved level asset in that folder, named `L_ActorLayout`. Opening that level
> must show a small combat-test layout of six placed objects. Each object
> carries exactly the display label given below — the name the editor shows
> for it in the level's outline — and each of the six labels is used exactly
> once:
>
> - **`Floor`** — a flat slab built from the engine's stock cube shape (the
>   asset at `/Engine/BasicShapes/Cube`), positioned at (0, 0, -50) and
>   stretched to exactly 20 x 20 x 1 times its natural size.
> - **`Start`** — the standard marker the engine itself consults when it
>   decides where the player appears at the moment play begins, placed at
>   (0, 0, 110).
> - **`Bounds`** — an invisible box-shaped region that gameplay code could
>   later query for containment — a real collision region, not a visible
>   mesh. Its box is centered at (0, 0, 200) and reaches exactly 1000 units
>   out from that center along X, 1000 along Y and 400 along Z (a
>   2000 x 2000 x 800 box overall).
> - **`Enemy_1`**, **`Enemy_2`**, **`Enemy_3`** — three stand-ins for future
>   enemies, each built from the engine's stock sphere shape (the asset at
>   `/Engine/BasicShapes/Sphere`), placed at (300, 0, 110), (-300, 0, 110)
>   and (0, 300, 110) respectively.
>
> All positions are world-space and exact. No object other than those three
> may carry a label starting with `Enemy_`. The level must be saved to disk
> with all six objects in it.

## Workspace state pre-task

Substrate content that **exists** under
`Content/Tasks/kp-spawn-level-actors/`:

- Nothing. This task ships **no baseline asset**. The folder is the
  agent-writable Content carve-out of the `ThirdPerson` substrate
  (`UE-projects/ThirdPerson/AGENT_WRITABLE.json` lists `Content/Tasks/` under
  both `writable` and `asset_writable`); fairness isolation keeps this task's
  folder while hiding every other task's.

Engine content the agent starts with (available in every UE project, named in
the prompt as inputs):

- `/Engine/BasicShapes/Cube` and `/Engine/BasicShapes/Sphere`.

Files that **do not exist** (the agent must create):

- `Content/Tasks/kp-spawn-level-actors/L_ActorLayout.umap` — plus, if the
  project saves levels One-File-Per-Actor, the actor files the editor writes
  under `Content/__ExternalActors__/Tasks/kp-spawn-level-actors/` and
  `Content/__ExternalObjects__/Tasks/kp-spawn-level-actors/`. Both prefixes
  are `asset_writable` (the 2026-07-29 level-deliverable carve-out), so the
  saved level is submittable either way.

Out of scope / not needed:

- No C++ is required or expected. `Content/Maps/`, `Config/`,
  `Content/Characters/`, `Content/ThirdPerson/` and `Content/Input/` are
  deny-listed — the agent neither can nor needs to touch them. The verifier
  never opens any map other than the one the agent saves.

## Verifier specification

Layer choice: this task grades via **L1 + L2I**. Every graded property is a
static property of a saved level asset (which actors exist, their labels,
their assigned meshes, and eleven exact numbers across four transform/extent
gates), read by verifier-owned editor-Python reflection after loading the
submitted level headless. L2 is deliberately **not** declared: nothing is
observed over time, and an L2 fixture must live in a committed
`Content/Maps/` map — this task's whole point is that the AGENT authors the
map. L3 is not declared: no rendering assertion (and `-nullrhi` uploads no
pixels anyway).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

The submission is content-only, so L1 is a precondition (the project and its
Asset Registry must load cleanly), never a correctness signal.

### L2I — Structural assertion

The verifier-owned script
`tools/verify-single/introspect/kp_spawn_level_actors.py` runs headless via
`UnrealEditor-Cmd -ExecutePythonScript=` under `-nullrhi`, read-only, and
prints one `CRAFTBENCH-INTROSPECT-JSON` verdict block. It emits **exactly 17
named checks on every leg** (constant denominator — the reported
`tests_passed/tests_run` is comparable across submissions and a submission
cannot improve its ratio by making checks unreachable). PASS requires all 17:

```text
level_asset_exists        /Game/Tasks/kp-spawn-level-actors/L_ActorLayout resolves
level_opens_with_actors   the level loads headless AND enumerates a non-empty
                          actor list (an empty enumeration is a graded FAIL)
floor_actor_present       exactly one actor labeled "Floor"
floor_mesh_is_cube        its assigned mesh is /Engine/BasicShapes/Cube.Cube
floor_location_exact      at (0, 0, -50) within 1.0 unit per axis
floor_scale_exact         scale (20, 20, 1) within 0.01 per axis
start_actor_present       exactly one actor labeled "Start"
start_is_spawn_marker     it IS a player spawn marker (isinstance, subclass-
                          tolerant; an unevaluable probe FAILS)
start_location_exact      at (0, 0, 110) within 1.0 unit per axis
bounds_actor_present      exactly one actor labeled "Bounds"
bounds_is_box_region      it carries a box-shaped collision component
bounds_center_exact       box world center (0, 0, 200) within 1.0 unit
bounds_extent_exact       box scaled world extent (1000, 1000, 400) within 1.0
enemy_actors_present      Enemy_1 / Enemy_2 / Enemy_3 each exactly once
enemy_meshes_are_spheres  all three carry /Engine/BasicShapes/Sphere.Sphere
enemy_locations_exact     (300,0,110) / (-300,0,110) / (0,300,110), 1.0 unit
no_extra_enemy_labels     no OTHER label starts with "Enemy_"
```

**The tolerances are verifier-only; the targets are not.** Per the basket's
design the demanded values appear verbatim in the prompt (the outcome IS the
exactness), while the acceptance bands (1.0 unit / 0.01 scale) stay in this
section, which `tools/run-agent/prompt_extract.py` never emits.

**The level load is the one unspiked step (plan U1) — the shared risk flag of
the level-deliverable lane.** `layers/l2_introspect.py` builds the editor
command line with **no map argument**, so the script must open the submitted
level itself: `LevelEditorSubsystem.load_level` first,
`EditorLevelLibrary.load_level` as fallback, then
`EditorActorSubsystem.get_all_level_actors` /
`EditorLevelLibrary.get_all_level_actors`. Neither load route has been proven
live under `-nullrhi` on UE 5.8 as of authoring. The script fails closed
either way, and keeps the two failure classes apart: a level that *refuses to
open* is the graded `LEVEL_LOAD_FAILED path=`, while a *broken probe* (every
route raising) is `LEVEL_LOAD_PROBE_ERROR`, an error token no MATRIX row
credits — so a harness break can never be attributed to the agent. Until the
authoring-lane run proves the route, treat any `LEVEL_LOAD_PROBE_ERROR`
verdict as a harness question (`notes.md`, risks section).

**Read routes.** Every read is wrapped, tries multiple pythonized spellings
(UE underscore-folds property names), and fails closed:

- *asset existence* — `unreal.EditorAssetLibrary.does_asset_exist`.
- *identity* — **pre-declared content path and pre-declared actor label,
  never class scanning.** Labels via the editor-only `get_actor_label`.
  Class is consulted only as an assertion ("is the thing labeled `Start`
  really a spawn marker"), written as `isinstance` so a legitimate subclass
  is not penalized, and tri-state: a type not exposed to Python FAILS the
  check rather than passing on the absence of an exception.
- *transforms* — `get_actor_location` / `get_actor_scale3d`.
- *mesh identity* — `get_components_by_class(StaticMeshComponent)`, the
  component's `static_mesh` property, compared by `get_path_name()` against
  the two engine object paths. A fresh mesh actor ships with **no** mesh, so
  this gate cannot pass by accident.
- *box region* — `get_components_by_class(BoxComponent)` (subclass-tolerant);
  center via the component's `get_world_location` (actor location fallback);
  extent via `get_scaled_box_extent` first — the world truth, which accepts
  BOTH legitimate authoring routes (setting the extent directly, or scaling
  the actor) — falling back to `box_extent` x world scale.

**Every graded number excludes the value an untouched spawn gets for free**
(the dead-gate audit; the floor's origin location in the source row failed it
and was moved — divergence 5):

| gate | free/untouched value | graded value | free value inside the gate? |
|---|---|---|---|
| floor location | (0, 0, 0) spawn default | (0, 0, -50) | **no** |
| floor scale | (1, 1, 1) | (20, 20, 1) | **no** (x, y) |
| floor / enemy mesh | none assigned | Cube / Sphere object path | **no** |
| start location | (0, 0, 0) | (0, 0, 110) | **no** |
| bounds center | (0, 0, 0) | (0, 0, 200) | **no** |
| bounds extent | tens of units (fresh box region) | (1000, 1000, 400) | **no** |
| all six labels | editor auto-labels (class-derived) | the demanded strings | **no** |

**Score granularity.** `registry.py` sets `tests_run`/`tests_passed` from the
per-check counts, so `report.json` carries `x/17` for this task. That number
is reported, not gating — `overall` stays `all(status == "pass")`.

**The visual, and where it is allowed to live.** A `--visible` run on the saved
level shows the layout for a human; no screenshot, no pixel comparison, no
LLM judge reaches `overall` (FR-020d).

## Reference solution metadata

- LOC range: **0** shipped lines of code. The natural completion route is a
  ~40–80 line throwaway editor-Python script the agent runs and discards; the
  deliverable is the saved level. A by-hand editor route ships the same bytes.
- Files touched: 1 created (`L_ActorLayout.umap`) plus, when the project
  saves One-File-Per-Actor, one external actor file per placed actor under
  `Content/__ExternalActors__/Tasks/kp-spawn-level-actors/` (and any
  `__ExternalObjects__` siblings) — the authoring-lane run pins the real
  count in `notes.md`.
- Senior-dev hours: 0.3–0.75 (spawn six actors, set eleven numbers plus two
  meshes and six labels, save — scripted or by hand).

## Anti-gaming notes

Per the amended checklist §7 (2026-08-11), each note names its defense with a
resolvable pointer — the check id, its named failure token, and the
requirements-table row in `discrimination/MATRIX.md` that carries the
file:line anchor.

1. **Empty or partial delivery.** *Failure mode*: the agent creates the level
   (or nothing at all) and places few or none of the six objects, banking on
   presence-shaped checks passing vacuously. *Defense*: FAIL-on-empty at
   every stage — a missing level fails all 17 via `level_asset_exists`
   (`LEVEL_ASSET_MISSING /Game/Tasks/`), a level that enumerates zero actors
   is the graded `LEVEL_ACTOR_LIST_EMPTY`, and each absent label is its own
   named miss (`FLOOR_ACTOR_MISSING wanted_label=Floor labels=` records the
   labels that WERE found). MATRIX rows 1–3, 7, 10, 14.
2. **Label-only impostors.** *Failure mode*: the agent labels any six cheap
   actors with the six demanded names — a cube named `Start`, a mesh box
   named `Bounds`, cubes named `Enemy_*` — and every name check passes.
   *Defense*: labels are only the lookup key; each group then gates substance
   — exact mesh object path (`FLOOR_MESH_WRONG mesh=` /
   `ENEMY_MESH_WRONG which=`), a tri-state spawn-marker `isinstance`
   (`START_NOT_SPAWN_MARKER class=`), and a real box collision component
   (`BOUNDS_NO_BOX_REGION classes=`). MATRIX rows 4, 8, 11, 15.
3. **Spawn-and-forget transforms.** *Failure mode*: all six objects placed
   with the right labels and meshes but transforms left wherever spawning put
   them. *Defense*: every graded location/scale/extent excludes the
   untouched-spawn value by construction (dead-gate table above), so "never
   set it" fails each of `FLOOR_LOCATION_WRONG got=`,
   `FLOOR_SCALE_WRONG got=`, `START_LOCATION_WRONG got=`,
   `BOUNDS_CENTER_WRONG got=`, `BOUNDS_EXTENT_WRONG got=`,
   `ENEMY_LOCATION_WRONG which=`. MATRIX rows 5–6, 9, 12–13, 16.
4. **Duplicate-label spam.** *Failure mode*: the agent scatters several
   actors under one demanded label (five `Enemy_1`s, two `Floor`s) hoping the
   verifier grades a lucky one. *Defense*: every label must resolve to
   **exactly one** actor — duplicates are their own named failures
   (`FLOOR_LABEL_DUPLICATE count=`, `ENEMY_SET_INCOMPLETE found=` carries
   per-label counts) — and surplus enemy-shaped actors under new names die at
   `ENEMY_EXTRA_LABELS extras=`. MATRIX rows 3, 7, 10, 14, 17.
5. **Bounds faked with a stretched visible mesh.** *Failure mode*: the agent
   scales a cube mesh to 2000 x 2000 x 800, labels it `Bounds`, and the size
   looks right in the viewport. *Defense*: `bounds_is_box_region` requires an
   actual box-shaped **collision** component (`BOUNDS_NO_BOX_REGION
   classes=` names the component classes it found instead), and the extent
   gate reads that component's scaled world extent, which a bare mesh does
   not carry. MATRIX rows 11–13.

## Hidden invariants

- **The check denominator is fixed at 17 on every leg**, including the empty
  submission (which scores `0/17` — this task ships no baseline for any check
  to pass against). The crash-shaped "fewer checks ran, so the ratio looks
  better" path is closed by construction.
- **A failed resolution fans out carrying its own token.** A missing or
  duplicated label, an unloadable level, or a boxless `Bounds` actor
  propagates its single root-cause detail into the dependent value checks —
  the matrix always attributes a failure to one cause instead of inventing
  numeric verdicts against an object that was never validated.
- **Error tokens are disjoint from failure tokens.** Every exception path
  emits `*_PROBE_ERROR` / `*_READ_ERROR` / `*_ABORTED` /
  `CHECK_NOT_EVALUATED`, none of which appears in any MATRIX row — a broken
  UE API name (a live risk on the unspiked level-load route) can never be
  credited as a variant's named failure.
- **Every graded number excludes the untouched-spawn default, by
  construction.** That is the dead-gate table in *Verifier specification*;
  any future edit that moves a target or widens a tolerance must re-run that
  column (the source row's origin-floor gate is the counter-example this task
  already fixed).
