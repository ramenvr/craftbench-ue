# kp-spawn-level-actors — authoring notes

First task of the `tasks/python/` basket, text-only track (no UE run).

## 1. Provenance (the source row)

- **Source**: an earlier internal task list (not shipped) — a level-setup row,
  the first of a group derived from observed editor-scripting-agent failures,
  never implemented there.
- **Its summary cell**: *"Spawn a labeled floor, PlayerStart, nav-mesh
  bounds volume, and three enemy stand-in actors at exact transforms, save
  the level, and report each actor's label and location."*
- **Its verification cell**: *"Query editor state: all 6 actors exist with
  exact labels, meshes (Cube/Sphere), locations and scales; level saved.
  Prints PASS/FAIL."*
- **Its start state**: *"Empty Project"*; **screenshot cell**: *"None
  required - verified via printed editor state (no screenshot needed)"*;
  **budget cell**: *"<=12 steps; <=4 min"*.
- **Its prompt** (names APIs verbatim — the reason the prompt was fully
  rewritten): StaticMeshActor / PlayerStart / NavMeshBoundsVolume /
  StaticMeshComponent, `/Engine/BasicShapes/Cube.Cube` and
  `.../Sphere.Sphere`, labels `EvalFloor`, `EvalPlayerStart`, `EvalNavMesh`,
  `EvalEnemy_01..03`, floor at (0,0,0) scale (20,20,1), start (0,0,110), nav
  volume (0,0,200) scale (10,10,4), enemies (300,0,110) / (-300,0,110) /
  (0,300,110).

**Basket law applied** (owner decision 2026-08-11, recorded in
`tasks/README.md`): outcome-graded — the deliverable is the resulting editor
state, graded by the deterministic L2I lane; scripting is the natural path
because of the exactness/volume, but no gate asserts "python was used".
Hybrid and task-dependent by design; v2 may re-execute submitted scripts.

## 2. Divergences from the source row (mirror of the spec's list, with rationale)

1. **Saved level asset replaces open-level state.** "Currently open editor
   level" is not a submittable artifact — the harness grades a file overlay
   materialized onto a clean substrate from git HEAD. Re-pathed to
   `/Game/Tasks/kp-spawn-level-actors/L_ActorLayout`. Submittable because of
   the 2026-07-29 OFPA carve-out in
   `UE-projects/ThirdPerson/AGENT_WRITABLE.json`
   (`Content/__ExternalActors__/Tasks/` + `Content/__ExternalObjects__/Tasks/`
   are `asset_writable`). NB: `t1-dawn-fog-lighting-rig`'s "why not a level"
   §-list predates that carve-out and partly no longer applies; what remains
   genuinely open is the **headless level-load read** (risk section below).
2. **Nav bounds volume → box collision region.** Brush-based volumes carry
   BSP brush geometry stock editor Python cannot build (a spawned
   `NavMeshBoundsVolume` is an empty shell with no gradeable extent), and the
   nav system adds nothing to the graded capability. The graded object is a
   box-collision region with scaled world extent (1000, 1000, 400) about
   (0, 0, 200) — the same world box the source row's scale implies (default
   200-unit brush x (10, 10, 4) = 2000 x 2000 x 800). The reference authors it
   as a `TriggerBox`; the grader accepts ANY actor whose components include a
   box collision shape (subclass-tolerant), so alternative shapes of the same
   outcome pass.
3. **"Prints PASS/FAIL" / "report each actor's label and location" dropped.**
   Session stdout is not a deliverable in this basket version; the saved
   level is the report. A v2 that re-executes submitted scripts can restore
   it as a graded text artifact (the `datatable_csv_export.py` pattern).
4. **Labels re-slugged** to `Floor` / `Start` / `Bounds` / `Enemy_1..3`. The
   source row's `EvalPlayerStart` puts an engine class name inside an
   agent-visible literal (Hard Rule #2 exposure); the `Eval` prefix carries
   no information the task folder does not.
5. **Floor moved off the origin** ((0,0,0) → (0,0,-50)). The origin is the
   spawn-default location, so the source row's floor-location gate was a dead gate
   (the same defect family as row R5's `intensity == 5000`). Every other
   source-row number already excluded its free default and is kept.
6. **Prompt rewritten behavior-only**; graded numbers stay in the prompt (the
   basket's exactness-is-the-outcome law), tolerances stay verifier-only.

## 3. Design decisions

- **Identity = pre-declared level path + actor labels**, never class
  scanning. Class/mesh/box checks are assertions on the labeled actor, all
  `isinstance`-style and subclass-tolerant. Uniqueness (exactly one actor per
  label) is part of presence, so duplicate-label spam is a named failure.
- **Mesh identity by engine object path** (`/Engine/BasicShapes/Cube.Cube` /
  `Sphere.Sphere`), disclosed in the prompt as inputs — the precedented
  asset-path exception to Hard Rule #2. A fresh mesh actor carries NO mesh,
  so the gate is live by construction.
- **Bounds extent graded as SCALED world extent** (`get_scaled_box_extent`
  first): both legitimate authoring routes (set the extent, or scale the
  actor) produce the same graded number.
- **No total-actor-count gate** and no constraint on non-`Enemy_` labels:
  levels created from non-empty editor templates must not fail for reasons
  the prompt cannot pin. The `Enemy_` namespace is exclusively gated because
  the prompt says so. Recorded as accepted residuals in `MATRIX.md`.
- **Tolerances**: 1.0 unit (locations/extents), 0.01 (scale). Wide enough for
  float round-trips, too narrow for placement-by-eye.
- **Constant 17-check denominator**, single-root-cause fanout, and
  error-token/failure-token disjointness — all inherited from the
  `dawn_fog_lighting_rig.py` conventions.
- **Discrimination package** follows the amended §7 (2026-08-11): automatic
  reference-PASS / empty-FAIL rows + the requirements table; **zero
  hand-authored variants**, because every prompt requirement resolved to an
  enforcing gate (see the table — no hole found, so no variant is owed).

## 4. Reference status — PENDING THE AUTHORING-LANE RUN

**`reference/` is EMPTY. No `.uasset`/`.umap` is fabricated from this
text-only track.** `aids/author_reference.py` is the generator: run it
headless on the ThirdPerson substrate
(`UnrealEditor-Cmd <ThirdPerson.uproject>
-ExecutePythonScript=<abs path to aids/author_reference.py> -nullrhi
-unattended -nosplash`), grep the newest editor log for `KPSPAWN-DONE`. It
builds the level, self-grades with the REAL introspect script (17/17 or it
refuses to harvest), copies the saved files (including any OFPA mirrors) into
`reference/`, and deletes every staged asset from the substrate.

## 5. Offline validation already done (2026-08-11)

- `kp_spawn_level_actors.py` was driven through **nine legs** with a fake
  `unreal` module and the verdict block parsed for real: reference-shaped
  world → 17/17 PASS; missing level → `LEVEL_ASSET_MISSING` fanout `0/17`;
  level-opens-empty → graded `LEVEL_ACTOR_LIST_EMPTY`; load-refused → graded
  `LEVEL_LOAD_FAILED path=`; label-impostors → `START_NOT_SPAWN_MARKER` /
  `BOUNDS_NO_BOX_REGION` / `ENEMY_MESH_WRONG`; all-default transforms → all
  six transform gates fail; duplicates + `Enemy_9` → `FLOOR_LABEL_DUPLICATE`,
  `ENEMY_SET_INCOMPLETE`, `ENEMY_EXTRA_LABELS`; missing floor → presence
  token + identical fanout detail; no-mesh actor → `FLOOR_MESH_WRONG`.
- No-`unreal` import → all 17 checks fail with `LEVEL_ASSET_PROBE_ERROR`
  (uncreditable error token, matches no MATRIX row).
- `MATRIX.md` parses through the real `aura_rig.discriminate.parse_matrix`
  into exactly the `reference` + `empty` rows (requirements table invisible
  to it), and **all 21 backticked token spans were grep-verified as
  contiguous single-literal spans** of the introspect source.
- `task.md` front matter parses through the real
  `tools/verify-single/spec.py::parse_task_file`: v2 (non-legacy),
  `set_name=python`, `layers=('L1','L2I')`,
  `introspect_scripts=('kp_spawn_level_actors.py',)`.
- Whole introspect script is ASCII; neither automation-result marker pair
  appears anywhere in it.

## 6. Calibration TODOs (in order, all need an editor)

- [ ] **Run `aids/author_reference.py`** on a clean ThirdPerson substrate;
      require `KPSPAWN-DONE`. This is simultaneously the live spike for the
      headless level-load route (risk #1) — the in-process grade re-loads the
      authored level exactly the way the L2I leg will.
- [ ] Record here: the winning property spellings (`KPSPAWN-SPELLING` lines),
      which load/enumerate route won (`LEVEL_OPEN_OK ... route=` in the
      grader detail), and whether the save produced OFPA external files (and
      how many — the spec's "files touched" needs the real count).
- [ ] `cb discriminate --task python/kp-spawn-level-actors --wip` — reference
      PASS + empty FAIL via the named substring.
- [ ] `cb lint --task python/kp-spawn-level-actors` — zero ERRORs. Watch two
      rules written before this basket existed: the map rule (this task
      deliberately ships NO committed `Content/Maps/` map — the agent authors
      the level; if `_check_map` misfires on `L2I`-only python tasks, that is
      a tasklint fix, not a task fix) and anything asserting `set` ∈
      {bp, cpp}.
- [ ] Check `tools/verify-single/tests/test_verdict_taxonomy.py`'s
      landable-layers assertion accepts an `L1+L2I` spec in `tasks/python/`
      (the bp L2I pilots forced the same edit earlier; verify it was made
      basket-agnostic).
- [ ] Author `cameras.json` (the camera-plan lane; not part of this release) (checklist step 5) AFTER the level exists:
      a camera plan.
- [ ] After the first commit: `./cb refgate python/kp-spawn-level-actors`
      green against the landed commit (the authoring-time close), then
      `cb batch-eval --references all` for cross-task regression.
- [ ] Tolerance sanity on the real bytes: confirm the saved level round-trips
      the four exact transforms well inside 1.0/0.01 (float drift through
      save/load was assumed negligible; verify once, record numbers here).

## 7. Risks

1. **Headless level load is UNSPIKED (plan U1) — the shared risk flag of the
   level-deliverable lane.** L2I launches with no map argument
   (`layers/l2_introspect.py`), so the grader itself opens the level under
   `-nullrhi` via `LevelEditorSubsystem.load_level` /
   `EditorLevelLibrary.load_level`. Neither route is proven live on UE 5.8
   headless. Mitigations: two routes + fail-closed split between the graded
   `LEVEL_LOAD_FAILED path=` (level refuses to open) and the uncreditable
   `LEVEL_LOAD_PROBE_ERROR` (probe broken — a harness question, never agent
   evidence); the authoring run doubles as the spike. **If the route is dead,
   this task and every future level-deliverable python task is blocked on a
   harness change — surface it immediately rather than working around it.**
2. **OFPA uncertainty.** Whether `new_level`-created levels save
   One-File-Per-Actor depends on project/world settings. Both shapes are
   submittable (carve-out) and the harvest handles both, but the reference's
   file inventory — and the sandbox scan of `reference/` (`cb lint`) — must
   be re-checked after the run.
3. **Property/API spellings unconfirmed** (`get_actor_label`,
   `get_scaled_box_extent`, `static_mesh`, `set_box_extent`, subsystem
   availability under `-nullrhi`). Every read tries multiple spellings and
   fails closed; the aid logs winners. Underscore-folding is the known 5.8
   trap and is designed for.
4. **Tooling assumptions from the bp basket** (tasklint map rule, verdict-
   taxonomy layer assertion, `set:` value validation) may not yet know
   `python` exists — first-task-in-basket breakage surfaces at the lint/gate
   TODOs above, not at grade time.
5. **`TriggerBox` reference choice.** If `TriggerBox` spawns without a
   readable/settable box component under headless Python, the aid dies loudly
   (it never harvests a half-set level); fallback design is a plain actor
   with an added box component — grader-compatible either way (it accepts any
   box-collision-bearing actor).
6. **Editor-template extras.** The grader deliberately tolerates non-`Enemy_`
   extra actors (accepted residual). If a future reviewer wants a stricter
   scene, tighten the prompt AND add the gate together — never gate what the
   prompt does not say (§7 law, in both directions).

> **RECONCILIATION 2026-08-11/12 (authoring-lane + graph-lane runs DONE).**
> Statements above about pending binaries / empty reference/ describe the
> authoring-time state and are now historical: binaries are committed
> (39433c2, 09781a8) and `cb refgate` graded this task's reference PASS
> from git HEAD. Remaining: the empty-FAIL discriminate leg.
