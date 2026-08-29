# t1-hero-blueprint-copy-with-flashlight — implementor notes + asset build spec

Text half authored 2026-07-27 (no editor, no build). **The binary half is not
done.** This file is the contract the editor track builds against: everything
below is stated property-by-property so the assets can be authored without
re-deriving anything from the spec.

## Provenance

- Source: an earlier internal task list (not shipped) — a Blueprint-editing
  row that was never implemented there.
- Selected as the **pilot** of the import: the cheapest row, and the only one
  whose every read route was confirmed end-to-end on a live UE 5.8 editor
  before authoring.
- Substrate `ThirdPerson` is the owner's choice for the imported set. Nothing in
  the task needs the third-person character stack; the cost is real and should
  be recorded: a ThirdPerson L1 leg measured **172 s vs 131 s** on
  `CraftBenchTemplate` because there is no warm slot for it on this box
  (plan §6). If the imported set later moves to `CraftBenchTemplate`, this task
  moves with a one-key front-matter edit and no other change — nothing in the
  spec or the introspect script depends on the substrate.

## Deviations from the source row (all four are deliberate)

1. Id is `t<tier>-<outcome>`, not the source row's row index. See
   the set-provenance note (internal, not shipped).
2. `/Game/EvalTemplate/` -> `/Game/Tasks/<task-id>/`. The source row's folder does
   not exist anywhere in the repo and is outside every writable prefix.
3. **Required brightness is 12000, not 5000.** Evidence:
   `<UE-root>/Engine/Source/Runtime/Engine/Private/Components/LocalLightComponent.cpp:13`
   — `Intensity = 5000; IntensityUnits = ELightUnits::Unitless;` is the
   constructor default inherited by every point and spot light. The row's
   `intensity == 5000 (+/-0.5)` check therefore cannot fail. **This is the one
   call a human should confirm before the assets are cut**, because reverting
   it later means re-authoring the reference and two variants. To revert: change
   `EXPECTED_INTENSITY` in the introspect script, the check id
   `hero_flashlight_intensity_12000`, the two numbers in the prompt and the
   Verifier-specification block, and this section.
4. Parent-class acceptance is `isinstance(cdo, unreal.Character)` — Character or
   any subclass — not class equality. Rationale in the spec.

---

## 1. BASELINE asset (ships in the substrate, committed, agent-writable)

**Path on disk:**
`UE-projects/ThirdPerson/Content/Tasks/t1-hero-blueprint-copy-with-flashlight/BP_Source.uasset`
**Content path:** `/Game/Tasks/t1-hero-blueprint-copy-with-flashlight/BP_Source`

| property | required value | why the verifier cares |
|---|---|---|
| asset type | Blueprint Class | — |
| parent class | `Actor` (engine) | `source_unchanged_not_character` asserts the CDO is **not** a `Character`; any non-Character parent satisfies it, but ship plain `Actor` to match the row |
| root component | the default scene root (`DefaultSceneRoot`) | the `Body` attach point; not read directly |
| component 1 | `StaticMeshComponent`, **variable name exactly `Body`** (case-sensitive), attached under the default root, `StaticMesh` = an engine primitive cube (`/Engine/BasicShapes/Cube`) | `hero_retains_body_component` matches on the name `Body` via `FSubobjectData::GetVariableName`. The mesh asset itself is **not** asserted — pick the engine cube for fidelity to the row, but a different mesh would not fail anything |
| variable 1 | float, **name exactly `Health`**, default `100.0` | `hero_retains_health_100` reads `cdo.get_editor_property("Health")` |
| variable 1 flags | **Blueprint Read/Write** and **Instance Editable** (the eye icon ON) | **load-bearing**: a Blueprint variable that is neither BlueprintVisible nor EditAnywhere is not exposed to `get_editor_property`, and the check would fail with `HERO_HEALTH_READ_ERROR` on a correct submission. Verify by running the read in the editor's Python console before committing |
| lights | **none** | `source_has_no_flashlight` matches on the name `Flashlight`; ship no light at all |
| compile / save | compiled clean, saved, not dirty | — |

Also create the folder itself: `Content/Tasks/t1-hero-blueprint-copy-with-flashlight/`
must exist in the substrate even though only one asset lives in it.

### Two work-loss hazards for whoever authors this (plan §9.7)

- Fairness isolation physically **moves** an untracked `Content/Tasks/<id>/` out
  of the substrate the next time a *different* task is driven. Commit the
  baseline as soon as it exists.
- `run_task` grades from **git HEAD**, so an uncommitted baseline is invisible to
  a normal grade (use `--substrate-from-live` / `cb discriminate --wip` while
  iterating).
- `_CB_EDITOR_MARKER = "craftbench"` means an in-repo authoring editor is
  classified CraftBench-owned: `cb down` / `cb eval` / `cb view` will kill it
  unwarned. And launch via `launch_unreal_project` (its argv carries
  `-unattended`, which gates Live Coding OFF); an attended editor makes every
  UBT build on this box fail exit 6 in ~13 s.

---

## 2. REFERENCE solution

**Path on disk:**
`tasks/bp/t1-hero-blueprint-copy-with-flashlight/reference/Content/Tasks/t1-hero-blueprint-copy-with-flashlight/BP_Hero.uasset`

The reference overlay carries **only `BP_Hero.uasset`**. `apply_submission` is
copy-only with no wipe, so the untouched `BP_Source` falls through from the
substrate — which is exactly what the two `source_*` checks should see.

Build it by duplicating the baseline and then:

| step | required end state | check it satisfies |
|---|---|---|
| 1 | asset named `BP_Hero`, in the same folder | `hero_asset_exists` |
| 2 | reparented to engine `Character` | `hero_parent_is_character` |
| 3 | the `Body` `StaticMeshComponent` survives the reparent (it will re-root under the Character capsule; that is fine and is **not** asserted) | `hero_retains_body_component` |
| 4 | `Health` still float `100.0` | `hero_retains_health_100` |
| 5 | new `SpotLightComponent`, **variable name exactly `Flashlight`** | `hero_has_flashlight_component`, `hero_flashlight_is_cone_light` |
| 6 | `Flashlight`'s **attach parent is the inherited mesh** — the Character's `Mesh` (native object name `CharacterMesh0`). Attaching to a socket on that mesh is fine; the check reads the parent subobject, not the socket | `hero_flashlight_attach_parent_is_mesh` |
| 7 | `Flashlight.Intensity = 12000.0` exactly (tolerance +/-0.5). Leave `IntensityUnits` at its default `Unitless` | `hero_flashlight_intensity_12000` |
| 8 | compiled clean, saved | `hero_compiles_up_to_date` |
| 9 | `BP_Source` **not** touched (do not overlay it) | `source_unchanged_not_character`, `source_has_no_flashlight` |

Expected reference verdict: **L2I `11/11`, overall PASS.**

### One reparent gotcha to check by hand

Reparenting `Actor` -> `Character` re-roots the SCS: the Character's inherited
capsule becomes the root and `Body` re-parents under it. If the editor instead
*drops* `Body` during the reparent, the reference would fail
`hero_retains_body_component` — a false negative from the authoring step, not
from the agent. Confirm `Body` is still in the Components panel after step 2,
before saving.

---

## 3. Discrimination variants

Five variant `.uasset`s, one per anti-gaming note, specified in
`discrimination/MATRIX.md` and in each variant folder's
`README-MISSING-ASSETS.md`. Each is the reference with exactly ONE deviation,
so the matrix can attribute the FAIL to one gate.

---

## 4. Pre-flight before the first graded leg

Two blockers that are not about the assets at all:

1. **`tools/verify-single/tests/test_verdict_taxonomy.py:79`**
   (`test_every_shipping_spec_declares_only_landable_gating_layers`) globs
   `tasks/*/*/task.md` and asserts every spec's layers are exactly
   `("L1","L2")`. This spec makes that test fail the moment it is on disk —
   i.e. CI is red **before** any asset exists. Per plan §9.1 the fix is to
   replace the equality with a landability assertion **and** demonstrate that
   this task really does produce an `L2I` key in `layers_out` (that is the
   whole point of the test: it is the structural half of the exit-7
   harness-error argument, proving predicate (2) is inert on the reference
   sweep). Deliberately **not** done by the text track — it is a verdict-taxonomy
   change and wants its own review.
2. **Registry bookkeeping (plan §9.2).** `cb lint --all` runs
   `inventory.py`, which needs a `tasks/CATALOG.md` row for this id plus the
   six hard-coded task-count claims bumped (the repo conventions, `tasks/CATALOG.md` x2,
   the verifier-building skill (under `.claude/`, not shipped) x2,
   the task-authoring skill (under `.claude/`, not shipped)). Note the tree is
   currently **already** 8 ERRORs red from the `tp2-sprint-stamina` rescue that
   landed today (16 specs on disk, docs still say 15) — fix all of them in one pass
   (`cb lint` names each stale count) rather than stacking a second drift.

## 5. Calibration record

- [ ] Baseline `BP_Source.uasset` authored + committed.
- [ ] Reference `BP_Hero.uasset` authored; L2I reads **11/11**.
- [ ] `Health` confirmed readable via `get_editor_property` from headless Python
      (the flags gotcha in §1).
- [ ] `get_parent_handle` confirmed to return the inherited `Mesh` subobject
      under **`-nullrhi`** (`-nullrhi` is unconditional for L2I on every `cb`
      path). The route was probed on a *live* editor via MCP, not through
      `-ExecutePythonScript` under `-nullrhi`; the `SubobjectDataSubsystem` is
      an engine subsystem and should be present, but this is the one read this
      task cannot degrade gracefully from — it is the load-bearing check.
      Fallback if it is unreachable: `EditorActorSubsystem.spawn_actor_from_class`
      transiently + `component.get_attach_parent()` on the constructed actor,
      then destroy it (the route plan §10.2 prescribes for R6, itself
      `-nullrhi`-unspiked).
- [ ] Discrimination executed: reference PASS, empty + 5 variants FAIL, each via
      its MATRIX substring.
- [ ] **Measured L2I leg wall-clock recorded here.** Plan §1/§6 flags "does an
      L2I leg actually cost ~131 s like an L2 leg?" as an inference that has
      never been measured; this pilot is the first chance to answer it.
