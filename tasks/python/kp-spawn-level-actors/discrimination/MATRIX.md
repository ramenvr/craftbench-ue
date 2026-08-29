# Discrimination matrix — kp-spawn-level-actors

The self-validation oracle: the reference solution must PASS and the empty leg
must FAIL **at the predicted check, via the named substring**. A wrong-reason
FAIL (L1 build failure, a different check, a `0`-check/`error` L2I verdict,
SANDBOX-REJECT exit 4) means the verifier is NOT discriminated — fix it, or
relabel the task for the weaker property it actually tests.

Per the amended checklist §7 (owner decision 2026-08-11) this package ships
**no hand-authored gaming variants**: the automatic reference-PASS /
empty-FAIL legs provide the non-vacuity bit, and the **requirements table**
below is the mandatory soundness artifact. Author a variant only when a table
row exposes a requirement whose defense turns out not to exist.

> **STATUS: RUNNABLE (reference leg PROVEN 2026-08-11).** reference authored + validated by aids/author_reference.py, harvested, committed 39433c2, and `cb refgate` graded the committed reference PASS from git HEAD (162 s, 2026-08-11).
> Remaining before full certification: the empty-FAIL leg and the
> requirements-table spot checks ride the next `cb discriminate` run.

## Parser traps this matrix is written against (inherited from the bp L2I set)

- **ONE parseable row-table.** `discriminate.parse_matrix` returns
  `Dict[label -> MatrixRow]`, so a second table with a "substring" column and
  matching row labels would silently overwrite the first. This file has
  exactly one table with submission rows; the requirements table deliberately
  names none of its columns "substring" or "message" and its first cells are
  requirement prose, so `parse_matrix` skips it entirely.
- **Every "Expected substring" cell is a backtick-wrapped literal that
  contains a space or `=`** — `_extract_substrings` keeps only "substantive"
  backticked spans; a bare `SCREAMING_SNAKE` token hits the broken
  last-resort branch and can never match.
- **The reference row's substring cell is `—`** (maps to the empty tuple).
- **Substrings are matched against the raw `detail` string inside the
  `CRAFTBENCH-INTROSPECT-JSON` block**, and every cell below is a verbatim
  contiguous span of ONE source literal in
  `tools/verify-single/introspect/kp_spawn_level_actors.py` — never a span
  that crosses a printf placeholder or an adjacent-literal seam (the static
  oracle greps source literals).
- **ASCII rule:** every expected substring is ASCII-only (the UE log's UTF-8
  read back as cp1252 turns anything else into mojibake and the grep misses).
- **Error tokens are distinct from failure tokens.** Every exception path in
  the script emits `*_PROBE_ERROR` / `*_READ_ERROR` / `*_ABORTED` /
  `CHECK_NOT_EVALUATED`, none of which appears in any row below — a broken UE
  API name (a live risk on the unspiked headless level-load route, plan U1)
  surfaces as an uncredited FAIL, never as a credited named failure.
  (Observed directly: run the script with no `unreal` module and all 17
  checks fail with `LEVEL_ASSET_PROBE_ERROR`, which no row claims.)

## Layout (folder-local; agent-writable prefixes only)

- `../reference/Content/Tasks/kp-spawn-level-actors/L_ActorLayout.umap` — the
  one correct solution (plus, if the editor saves One-File-Per-Actor, its
  mirrors under `../reference/Content/__ExternalActors__/Tasks/…` and
  `../reference/Content/__ExternalObjects__/Tasks/…` — all three prefixes are
  `asset_writable` in `UE-projects/ThirdPerson/AGENT_WRITABLE.json`).
  **EMPTY until the authoring-lane run**; do not fabricate binaries.
- empty leg — run IMPLICITLY by `cb discriminate` (a throwaway empty dir;
  nothing to author). Its row documents the expected first-gate failure.

This task ships **no baseline asset**: the substrate contains nothing under
`Content/Tasks/kp-spawn-level-actors/`, so the empty leg is a genuinely empty
deliverable and scores `0/17`.

## Matrix

**This is the only table in this file that carries submission rows.**

| Submission | Overall | Fails at (check id) | Expected substring | Notes |
|---|---|---|---|---|
| `../reference` | PASS | — | — | all 17 checks green (17/17) |
| empty | FAIL | `level_asset_exists` | `LEVEL_ASSET_MISSING /Game/Tasks/kp-spawn-level-actors/L_ActorLayout` | the other 16 checks fan out on the same root cause (`0/17`) |
| `floor-left-unscaled/` | FAIL | `floor_scale_exact` | `FLOOR_SCALE_WRONG got=` | **MEASURED 16/17 in the authoring boot, self-graded by the real grader; harvested only because it isolates that one check.** every actor placed at its exact location with the right mesh; the floor keeps the spawn-default (1,1,1) instead of (20,20,1). |
| `one-enemy-too-many/` | FAIL | `no_extra_enemy_labels` | `ENEMY_EXTRA_LABELS extras=` | **MEASURED 16/17 in the authoring boot, self-graded by the real grader; harvested only because it isolates that one check.** **the only OVER-delivery gate in this task.** The three required enemies are exactly right; a fourth `Enemy_4` is added. Every other check asks whether the required thing is present and correct, so extras satisfy them all — and an `empty` leg can never reach a too-many gate, being always too few. Without this leg that requirement had no evidence at all. |

## Requirements table (checklist §7, the mandatory soundness artifact)

One row per requirement in the agent-visible prompt. Every backticked span in
the *verbatim token* column is a contiguous literal in
`tools/verify-single/introspect/kp_spawn_level_actors.py` (`grep` finds it in
source, and the script prints it inside the failing check's `detail`).
File:line anchors are into that script at authoring time; the check id is the
durable join key if lines drift.

| # | Prompt requirement | Asserted | Enforcing check — verbatim token (file:line) | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | a level asset saved at `Content/Tasks/kp-spawn-level-actors/L_ActorLayout` | fully | `level_asset_exists` — `LEVEL_ASSET_MISSING /Game/Tasks/kp-spawn-level-actors/L_ActorLayout` (kp_spawn_level_actors.py:700) | unconditional (first gate) | nothing — every other check fans out from this root cause |
| 2 | the level opens and contains placed objects | fully | `level_opens_with_actors` — `LEVEL_LOAD_FAILED path=` (:313) / `LEVEL_ACTOR_LIST_EMPTY the loaded level enumerated zero actors` (:318) | asset missing (row 1 fans out) | nothing; an unopenable or empty level fails all remaining checks with one named cause |
| 3 | one object labeled `Floor`, label used exactly once | fully | `floor_actor_present` — `FLOOR_ACTOR_MISSING wanted_label=Floor labels=` (:441) / `FLOOR_LABEL_DUPLICATE count=` (:444) | level missing/unopenable (rows 1–2 fan out) | nothing at the label layer; substance is rows 4–6 |
| 4 | `Floor` is built from the engine's stock cube | fully | `floor_mesh_is_cube` — `FLOOR_MESH_WRONG mesh=` (:486) | `Floor` unresolved (row 3's token fans out) | a *subclassed* mesh component carrying the exact Cube asset passes — accepted, that IS the outcome |
| 5 | `Floor` positioned at (0, 0, -50) | fully | `floor_location_exact` — `FLOOR_LOCATION_WRONG got=` (:497) | `Floor` unresolved (row 3 fans out) | anything inside the 1.0-unit verifier tolerance |
| 6 | `Floor` stretched to exactly 20 x 20 x 1 | fully | `floor_scale_exact` — `FLOOR_SCALE_WRONG got=` (:509) | `Floor` unresolved (row 3 fans out) | anything inside the 0.01 scale tolerance |
| 7 | one object labeled `Start`, label used exactly once | fully | `start_actor_present` — `START_ACTOR_MISSING wanted_label=Start labels=` (:452) / `START_LABEL_DUPLICATE count=` (:455) | rows 1–2 fan out | substance is rows 8–9 |
| 8 | `Start` is the marker the engine consults for player spawn | fully | `start_is_spawn_marker` — `START_NOT_SPAWN_MARKER class=` (:531) | `Start` unresolved (row 7 fans out) | any spawn-marker *subclass* passes (`isinstance`) — accepted by design |
| 9 | `Start` placed at (0, 0, 110) | fully | `start_location_exact` — `START_LOCATION_WRONG got=` (:543) | `Start` unresolved (row 7 fans out) | anything inside the 1.0-unit tolerance |
| 10 | one object labeled `Bounds`, label used exactly once | fully | `bounds_actor_present` — `BOUNDS_ACTOR_MISSING wanted_label=Bounds labels=` (:463) / `BOUNDS_LABEL_DUPLICATE count=` (:466) | rows 1–2 fan out | substance is rows 11–13 |
| 11 | `Bounds` is a real box-shaped collision region, not a visible mesh | **partially** | `bounds_is_box_region` — `BOUNDS_NO_BOX_REGION classes=` (:560) | `Bounds` unresolved (row 10 fans out) | an actor carrying BOTH a box collision component and a visible mesh passes — the gate asserts the region exists, not mesh absence; recorded as an accepted residual (the outcome "gameplay code could query it" holds) |
| 12 | `Bounds` box centered at (0, 0, 200) | fully | `bounds_center_exact` — `BOUNDS_CENTER_WRONG got=` (:583) | no box region (row 11's token fans out) | anything inside the 1.0-unit tolerance |
| 13 | `Bounds` box reaches exactly (1000, 1000, 400) from center | fully | `bounds_extent_exact` — `BOUNDS_EXTENT_WRONG got=` (:595) | no box region (row 11 fans out) | either authoring route (set extent, or scale the actor) — accepted, the world extent is the outcome |
| 14 | `Enemy_1`/`Enemy_2`/`Enemy_3` each placed, each label exactly once | fully | `enemy_actors_present` — `ENEMY_SET_INCOMPLETE found=` (:607) | rows 1–2 fan out | substance is rows 15–16 |
| 15 | each enemy is built from the engine's stock sphere | fully | `enemy_meshes_are_spheres` — `ENEMY_MESH_WRONG which=` (:626) | enemy set unresolved (row 14's token fans out) | same subclass tolerance as row 4 |
| 16 | enemies at (300, 0, 110) / (-300, 0, 110) / (0, 300, 110) | fully | `enemy_locations_exact` — `ENEMY_LOCATION_WRONG which=` (:648) | enemy set unresolved (row 14 fans out) | anything inside the 1.0-unit tolerance |
| 17 | no other object's label starts with `Enemy_` | fully | `no_extra_enemy_labels` — `ENEMY_EXTRA_LABELS extras=` (:669) | rows 1–2 fan out (needs a real actor list; on an unloadable level it FAILS with the root cause, never passes vacuously) | actors under NON-`Enemy_` labels are unconstrained — deliberate, see accepted residuals |

Every prompt requirement has an enforcing gate — nothing is unenforced prose —
so no targeted variant is owed under §7. Two rows are honest about being
*partial* or tolerance-bounded (11, 17); both are accepted residuals, argued
below, not holes.

## Accepted residuals (documented, not defended)

- **Extra non-enemy actors are allowed.** The verifier constrains the six
  demanded labels, uniqueness, and the `Enemy_` namespace — not the total
  actor count. An agent may leave a light or an editor-template actor in the
  level. Deliberate: a total-count gate would fail legitimate levels created
  from non-empty editor templates for a reason the prompt cannot fairly pin,
  and no graded outcome depends on the level containing nothing else.
- **`Bounds` may also carry a mesh** (row 11): the graded outcome is that a
  queryable box region with the exact extent exists at the exact center; a
  decorative mesh alongside it does not falsify that outcome.
- **Tolerances**: 1.0 unit on locations/extents, 0.01 on scale — wide enough
  for float round-tripping, far too narrow for placement-by-eye to survive;
  values inside them are graded as exact by design.
- **Mechanism-agnostic by basket law**: hand-authored and script-authored
  levels are indistinguishable to every gate. That is the basket's design
  (outcome-graded; "python was used" is deliberately not asserted).

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task python/kp-spawn-level-actors --wip
```

(`--wip` until the reference binaries and this task's first commit land; the
runner materializes the graded substrate from git HEAD.) Per-leg fallback
while iterating (short `--workdir` dodges Windows MAX_PATH):

```sh
UE='<UE-root>'
py tools/verify-single/run_task.py \
    --task tasks/python/kp-spawn-level-actors/task.md \
    --submission tasks/python/kp-spawn-level-actors/reference \
    --ue-root "$UE" --workdir C:\cb\wd\kpspawn       # expect exit 0
```

Then open the workdir's `report.json` and the L2I log it names, find the
`CRAFTBENCH-INTROSPECT-JSON-START` block, and confirm the verdict. L2I
graders are read from the LIVE working tree, so iterating on
`kp_spawn_level_actors.py` needs no commit — but the level binaries DO need
committing before a non-`--wip` grade sees them.

## Status

- Authored 2026-08-11, text-only track. **Never executed against a real
  editor** — no level binary exists yet, and the headless level-load route is
  unspiked (plan U1; the task spec and `../notes.md` carry the shared risk
  flag).
- **Proven offline against the real grader logic**: a fake `unreal` module
  drove `kp_spawn_level_actors.py` through nine legs (reference-shaped 17/17
  PASS; missing-level, empty-world, load-refused, label-impostor,
  default-transform, duplicate-label, extra-label, missing-actor,
  no-mesh legs all FAIL at the predicted check with the predicted token), the
  verdict block parsed at a constant 17-check denominator, and the whole
  script is ASCII with no automation-marker collision.
- **Still missing, in order:** (1) the reference level binaries
  (`../aids/author_reference.py` builds and self-grades them); (2) live
  confirmation of the headless level-load route and the property spellings
  (`get_actor_label`, `get_scaled_box_extent`, `static_mesh`, load/enumerate
  subsystem routes) that the offline fake cannot settle; (3) a `cameras.json` (the camera-plan lane; not part of this release)
  camera plan (checklist step 5) once the scene exists.
