# t1-playable-level-bootstrap — authoring notes

Wave-3 port into the three-basket layout, text-only track (no UE run).

## 1. Provenance (the retired source row)

- **Source**: a retired internal task list — a level-setup row, never built.
- **Why it was unbuilt**: the original port plan parked it because the graded
  level would have to be *agent-authored*, and at the time no lane could load
  and grade an agent-authored level. **That obstacle is now dissolved** by the proven agent-authored-level L2I lane: the
  `kp-spawn-level-actors` precedent (headless three-route level load under
  `-nullrhi`, refgate-proven 2026-08-11/12, plus the 2026-07-29 OFPA
  `asset_writable` carve-out that makes a saved `/Game/Tasks/<id>/` level
  submittable).
- **DISTINCT from `kp-spawn-level-actors`** (recorded so nobody collapses
  the two): that task grades **exact actor transforms** — bulk placement
  precision, eleven exact numbers. THIS task grades **playable-bootstrap
  wiring** — world settings → game-mode override → agent-authored rules
  Blueprint → default pawn → agent-authored pawn Blueprint, plus
  exactly-one start placement and a deliberately COARSE floor heuristic. It
  covers the previously uncovered `game-mode-and-game-state` concept
  (checked against `tools/coverage/concepts.csv`: no other task claims it
  as primary).
- **Basket**: `bp` — the deliverable is a Blueprint/asset/editor artifact
  chain (one `.umap`, two `.uasset`). The python-basket law still shapes
  the grading (outcome-graded; no gate asserts how the state was
  produced), but the deliverable surface is squarely `bp`.

## 2. Design decisions

- **Identity = pre-declared level path + the wiring the level itself
  declares.** The two authored Blueprints are resolved THROUGH the chain
  (world settings → rules class → its CDO's pawn class), never by asset
  name — so asset names are the agent's free choice and the verifier can
  never be gamed by name-squatting, nor can it unfairly pin a name the
  prompt never demanded.
- **"Agent-authored" is enforced as a class-origin gate**: the resolved
  class's object path must start `/Game/Tasks/t1-playable-level-bootstrap/`
  AND the class must be Blueprint-generated. This single gate kills all
  three freebie routes at once: native engine classes (`/Script/...`), the
  substrate's stock `BP_ThirdPersonGameMode` / `BP_ThirdPersonCharacter`
  (`/Game/ThirdPerson/...`), and any other out-of-folder asset.
- **Subclassing stock content is explicitly permitted** (prompt + workspace
  state): the pawn gate is `isinstance(Pawn)` on the CDO, so a BP parented
  from the stock third-person character (or from bare `Character`) passes.
  The AUTHORED ASSET is what must live in the task folder — parentage is
  free. This is the stated workspace context, not a loophole.
- **The dead-gate audit found one real near-trap**: a freshly authored
  game-rules class already carries a **non-None** default pawn (the engine
  seeds its built-in stand-in pawn class), so "default pawn is set" alone
  would be a DEAD gate. The presence check is kept (it catches an
  explicitly nulled wiring and gives the fanout a clean root cause) but the
  LIVE gate is the task-folder Blueprint gate, which the stand-in's
  `/Script/` path fails. Recorded in the spec's dead-gate table; any future
  edit must re-run that audit.
- **Floor = coarse heuristic, deliberately NOT a transform gate**
  (distinctness from kp-spawn is a design goal, not an accident):
  colliding-components-only bounds (`get_actor_bounds(True)`), a minimum
  footprint, XY containment with margin, and a generous vertical band. A
  no-collision decoration reports zero colliding extent and fails; a
  tiny/offset/out-of-band prop fails; anything honestly floor-shaped under
  the marker passes.
- **Exactly-one spawn marker is a subclass-tolerant type COUNT**, not a
  label lookup — the marker is engine-consumed identity (the engine finds
  it by type at spawn time), so type-count is the honest read; label-keying
  would gate something the engine itself ignores.
- **No K2 graph anywhere** (authoring-lane law): the whole outcome is
  property/asset-reference wiring (one CDO property, one world-settings
  property). Nothing in the reference or the grading needs event-graph
  logic, so the BlueprintFactory lane suffices end to end.
- **Constant 12-check denominator**, single-root-cause fanout, error-token/
  failure-token disjointness, and the `unreal.get_default_object`-only CDO
  route — all inherited from the `kp_blueprint_actor_audit_report.py` /
  `kp_spawn_level_actors.py` conventions.
- **Discrimination package** follows the amended §7 (2026-08-11): automatic
  reference-PASS / empty-FAIL rows + the requirements table; **zero
  hand-authored variants**, because every prompt requirement resolved to an
  enforcing gate (see the table — no hole found, so no variant is owed).

## 3. Verifier-owned constants (the authoring-time truth the introspect embeds)

All pinned in `tools/verify-single/introspect/kp_playable_level_bootstrap.py`
(constants block, lines ~130-150). "Disclosed" = appears in the
agent-visible prompt; verifier-only values never reach
`prompt_extract.py`'s output.

| constant | value | disclosed? | role |
|---|---|---|---|
| `LEVEL_ASSET` | `/Game/Tasks/t1-playable-level-bootstrap/L_PlayableBootstrap` | yes (as `Content/Tasks/.../L_PlayableBootstrap`) | the one graded level path |
| `TASK_CLASS_PREFIX` | `/Game/Tasks/t1-playable-level-bootstrap/` | yes ("saved in that same folder") | authored-asset origin gate for BOTH classes |
| `EXPECTED_START_COUNT` | `1` | yes ("exactly one") | spawn-marker count gate |
| `FLOOR_MIN_HALF_EXTENT_XY` | `100.0` | yes (as "at least 200 units across") | floor footprint gate (colliding half-extent per horizontal axis) |
| `FLOOR_BAND_ABOVE` | `10.0` | yes ("between 10 units above ...") | marker may sit up to 10 units below the floor top |
| `FLOOR_BAND_BELOW` | `500.0` | yes ("... and 500 units below") | floor top at most 500 units below the marker |
| `FLOOR_XY_MARGIN` | `50.0` | **no** (verifier-only generosity) | XY containment slack on the under-start test |
| override property | `default_game_mode` / `DefaultGameMode` | n/a (route, not value) | the world-settings per-level override |
| pawn property | `default_pawn_class` / `DefaultPawnClass` | n/a (route, not value) | the rules-CDO pawn wiring |

Reference-side placement (aid constants, satisfy the gates with margin):
floor cube at (0, 0, -50) scale (20, 20, 1) → colliding half-extents
(1000, 1000, 50), top at z=0; start at (0, 0, 110) → gap 110, mid-band.

## 4. Reference status — PENDING THE AUTHORING-LANE RUN

**`reference/` is EMPTY and no corpus exists (this task ships no baseline
asset). No `.uasset`/`.umap` is fabricated from this text-only track —
reference and corpus binaries stay EMPTY until the authoring-lane run
builds them.** `aids/author_reference.py` is the generator: run it headless
on the ThirdPerson substrate
(`UnrealEditor-Cmd <ThirdPerson.uproject>
-ExecutePythonScript=<abs path to aids/author_reference.py> -nullrhi
-unattended -nosplash`), grep the newest editor log for `KPBOOT-DONE`. It
authors the two Blueprints (BlueprintFactory, property wiring only), builds
and saves the level, self-grades with the REAL introspect script (12/12 or
it refuses to harvest), copies the saved files (including any OFPA mirrors)
into `reference/`, and deletes every staged asset from the substrate
(disk-is-truth cleanup: a stale in-memory registry row is a WARN, never a
die after a validated harvest).

## 5. Offline validation already done (2026-08-11)

- `kp_playable_level_bootstrap.py` was driven through **fourteen legs**
  with a fake `unreal` module and the verdict block parsed for real:
  reference-shaped world → 12/12 PASS; missing level →
  `BOOT_LEVEL_MISSING` fanout `0/12`; load-refused → graded
  `BOOT_LEVEL_LOAD_FAILED path=`; level-opens-empty → graded
  `BOOT_ACTOR_LIST_EMPTY`; no-override → `BOOT_GAMEMODE_OVERRIDE_NONE`
  (checks 5-9 fan out, placement checks still evaluate); stock-gamemode
  cheat → `BOOT_GAMEMODE_NOT_TASK_ASSET` alone; native-default-pawn (the
  dead-gate case) → presence PASSES, `BOOT_PAWN_NOT_TASK_ASSET` fails;
  non-pawn body → `BOOT_PAWN_NOT_PAWN_CLASS`; wrong-base ruleset →
  `BOOT_GAMEMODE_WRONG_BASE`; zero / two markers → `BOOT_START_MISSING` /
  `BOOT_START_COUNT_WRONG`; uncollidable floor →
  `BOOT_FLOOR_NO_CANDIDATE`; offset and too-deep floors →
  `BOOT_FLOOR_NOT_UNDER_START`.
- No-`unreal` import → all 12 checks fail with
  `BOOT_LEVEL_ASSET_PROBE_ERROR` (uncreditable error token, matches no
  MATRIX row).
- `MATRIX.md` parses through the real `aura_rig.discriminate.parse_matrix`
  into exactly the `reference` + `empty` rows (requirements table invisible
  to it), and **all 16 backticked token spans were verified as contiguous
  spans of single string literals** of the introspect source (AST-walked,
  not just grepped).
- `task.md` front matter parses through the real
  `tools/verify-single/spec.py::parse_task_file`: v2 (non-legacy),
  `set_name=bp`, `layers=('L1','L2I')`,
  `introspect_scripts=('kp_playable_level_bootstrap.py',)`.
- Whole introspect script and aid are ASCII; neither automation-result
  marker pair appears anywhere in either.

## 6. Calibration TODOs (in order, all need an editor)

- [ ] **Run `aids/author_reference.py`** on a clean ThirdPerson substrate;
      require `KPBOOT-DONE`. This is simultaneously the live spike for the
      two routes this task adds on top of the proven map-load lane: the
      world-settings resolution/write (`default_game_mode` spelling,
      `get_world_settings` vs `persistent_level.world_settings`) and the
      rules-CDO pawn write (`default_pawn_class` spelling via
      `unreal.get_default_object`).
- [ ] Record here: the winning property spellings (`KPBOOT-SPELLING`
      lines), which world-settings route won, whether the save produced
      OFPA external files (and how many — the spec's "files touched" needs
      the real count), and whether the BP CDO edit survived
      `save_asset` (see risk 2).
- [ ] **Fresh-session byte proof**: after committing the harvested
      binaries, `./cb refgate bp/t1-playable-level-bootstrap` must grade
      the committed reference PASS from git HEAD — this is the ONLY step
      that proves the wiring survived serialization (the in-process 12/12
      reads live objects; see the aid's comment at the grade step).
- [ ] `cb discriminate --task bp/t1-playable-level-bootstrap --wip` —
      reference PASS + empty FAIL via the named substring.
- [ ] `cb lint --task bp/t1-playable-level-bootstrap` — zero ERRORs. Watch
      the map rule: this task deliberately ships NO committed
      `Content/Maps/` map (the agent authors the level); if `_check_map`
      misfires on an `L2I`-only bp task, that is a tasklint fix, not a task
      fix (`kp-spawn-level-actors` hit the same rule in the python basket).
- [ ] Author `cameras.json` (the camera-plan lane; not part of this release) (checklist step 5) AFTER the level exists:
      a camera plan.
- [ ] After the first commit: `cb batch-eval --references all` for
      cross-task regression (shared substrate).
- [ ] Floor-heuristic sanity on real bytes: confirm the reference floor's
      colliding bounds read back near (1000, 1000, 50) and the gap near
      110, well inside every band; record the real numbers here.

## 7. Risks

1. **World-settings routes are UNSPIKED** (the one lane-novelty this task
   adds; the level LOAD itself is proven). Neither
   `World.get_world_settings` nor the reflected
   `persistent_level.world_settings` chain nor the `WorldSettings` actor
   scan is live-confirmed under `-nullrhi` on UE 5.8, and the
   `default_game_mode` spelling is assumed underscore-folded. Mitigations:
   three read routes in the grader, fail-closed split between graded
   tokens and the uncreditable `BOOT_WORLD_SETTINGS_PROBE_ERROR` (a
   harness question, never agent evidence); the aid run doubles as the
   spike and dies loudly if the write side is blind. **If all routes are
   dead, this task is blocked on a harness change — surface it, do not
   work around it.**
2. **CDO-edit persistence through save.** The aid sets
   `default_pawn_class` on the generated class's CDO and then
   `save_asset`s the Blueprint without an explicit recompile; whether the
   edit reaches the saved bytes (vs only the live object) is exactly what
   the fresh-session refgate proves (TODO above). If it does not persist,
   the fix is a `BlueprintEditorLibrary.compile_blueprint` +
   mark-dirty step in the aid — grader unchanged.
3. **`get_actor_bounds` signature drift.** The grader calls `fn(True)` with
   a `TypeError` retry as `fn(True, False)`; if 5.8 exposes a different
   arity the probe fails closed as `BOOT_FLOOR_BOUNDS_PROBE_ERROR`
   (uncreditable). The aid does not depend on bounds at all.
4. **Blocking vs query-only collision.** The floor gate cannot tell them
   apart (accepted residual, MATRIX row 10): a huge query-only volume
   under the marker would pass. Judged acceptable — the free value (no
   collision) is still excluded, and a per-component blocking-response
   walk under headless reflection is exactly the kind of fragile probe
   this basket avoids. Revisit only with a live-proven read.
5. **PlayerStart count near-misses.** Some editor templates auto-place a
   start; `new_level` from the blank template should not, but if the
   authoring run finds a surprise second start the aid's self-grade
   catches it (12/12 required) before anything is harvested.
6. **Tooling assumptions.** The bp basket already carries L2I-only tasks,
   so the lint/taxonomy edits the python basket forced should cover this
   task; first `cb lint` run confirms (TODO above).
7. **Cross-task substrate regression.** Two new Blueprints and a level
   land under `Content/Tasks/<id>/` only — no shared-file edits — so the
   `batch-eval --references all` sweep is expected clean; run it anyway
   (tag/pawn ambiguity has bitten sibling tasks before).
