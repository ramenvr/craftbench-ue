# t1-dawn-fog-lighting-rig — implementor notes + asset build spec

Text half authored 2026-07-27 (no editor, no build, no `.uasset` byte written).
**The binary half is not done.** This file is the contract the editor track
builds against: every asset below is stated property-by-property so the six
`.uasset`s can be authored without re-deriving anything from the spec.

## Provenance

- Source: an earlier internal task list (not shipped) — a lighting-and-
  atmosphere row that was never implemented there. Its Issues note:
  *"Need vision based eval?"*.
- Disposition: gate on the 4 actors + numeric bands (sun pitch/colour, fog
  density/extinction are all numbers), and preview the look. That is exactly
  what this task does — with one forced change of
  deliverable shape, argued in the spec's *Why this row is not graded on a
  level* and summarised again in §0 below.
- Substrate `ThirdPerson` is the owner's choice for the imported set. Nothing in
  this task needs the third-person character stack; the cost is real and should
  be recorded: a ThirdPerson L1 leg measured **172 s vs 131 s** on
  `CraftBenchTemplate` because there is no warm slot for it on this box
  (plan §6). If the imported set later moves to `CraftBenchTemplate`, this task
  moves with a one-key front-matter edit and no other change — nothing in the
  spec or the introspect script depends on the substrate.

## 0. The deliverable-shape decision, in one paragraph

The source row's deliverable is **level state**; there is no route in the harness
today that grades an agent-authored `.umap`. `map_locator.locate_map` searches
only `Content/Maps/` (`map_locator.py:43-51`), which is deny-listed in both
substrates; L2 needs a verifier fixture pre-placed in a committed map;
`layers/l2_introspect.py:168-177` passes the editor **no map at all**, so an
L2I script would have to load the agent's level itself under `-nullrhi`, which
is an unspiked read (plan U1); and a level authored with One-File-Per-Actor puts
its actors under the deny-listed `Content/__ExternalActors__/`, where they would
be dropped or trip exit 4. Of the two options the brief offers, this row takes
**"scope to assets the agent saves under `Content/Tasks/<id>/`"** — one
placeable lighting-rig Blueprint carrying the same four lighting parts with the
same numbers — because it needs **zero** harness change and reuses the
component-walk route the pilot already proved. The row that genuinely is blocked
on **U7** is **row R2** (`t2-basic-level-setup`), whose deliverable *is* the
level layout; nothing here should be read as unblocking it.

## Deviations from the source row (all five are deliberate)

1. Vision is out (plan D3 + FR-020d); every adjective in the row is a number on
   a component, and the look is inspected by a human (a `--visible` run), never gated.
2. Asset deliverable, not level state. See §0.
3. `/Game/EvalTemplate/` -> `/Game/Tasks/<task-id>/`. The source row's folder does
   not exist anywhere in the repo and is outside every writable prefix.
4. Id is `t<tier>-<outcome>`, not the source row's row index. The plan's §11.1 table
   pencilled `t1-level-lighting-and-atmosphere`; the word "level" is now wrong,
   so the id names what is actually produced. **This is a deviation from a
   written plan table and should be reconciled there.**
5. The prompt states explicit numeric ranges the source row leaves as
   adjectives. Without them the eval grades taste, not competence.

## The dead-gate audit (the reason this row grades anything)

Read from `<UE-root>/Engine/Source/Runtime/Engine/`, constructor by
constructor, on 2026-07-27. Nine graded numbers, nine engine defaults, zero
overlaps.

**Bands re-cut 2026-07-27, same day**, when the graded thresholds were removed
from the agent-visible prompt (task.md divergences 5 and 6): rows 1, 2, 6, 8
and 10 were widened so a band nobody can read is still reachable from the
described look. The table below is the POST-widening state and the audit was
re-run against it — every band still excludes its default. The pre-widening
values, and the justification for each move, are in the spec under *The
2026-07-27 widening, band by band*.

| # | property | engine default | source | required band | dead gate? |
|---|---|---|---|---|---|
| 1 | `Sun.RelativeRotation.Pitch` | `0.0` | `FRotator::ZeroRotator` on a fresh `USceneComponent` | `[-25, -1]` deg | no |
| 2 | `Sun.Intensity` | `10` | `Private/Components/DirectionalLightComponent.cpp` ctor | `[0.05, 5.0]` | no |
| 3 | `Sun.LightColor` | `FColor::White` | `Private/Components/LightComponent.cpp`, `ULightComponentBase` ctor | `R > G > B`, `R >= 150`, `R - B >= 60` | no |
| 4 | `Sun.bUseTemperature` | `false` | `Private/Components/LightComponent.cpp`, `ULightComponent` ctor | `true` (only for the temperature route) | no |
| 5 | `Sun.Temperature` | `6500` | same ctor | `[1000, 4000]` (only for the temperature route) | no |
| 6 | `Ambient.Intensity` | `1` | `Private/Components/SkyLightComponent.cpp` ctor | `[0.01, 0.6]` | no |
| 7 | `Ambient.bRealTimeCapture` | `false` | same ctor | `true` | no |
| 8 | `Fog.FogDensity` | `0.02` | `Private/Components/ExponentialHeightFogComponent.cpp` ctor | `[0.1, 10.0]` | no |
| 9 | `Fog.bEnableVolumetricFog` | `false` | **never assigned in that ctor** → zero-initialised | `true` | no |
| 10 | `Fog.VolumetricFogExtinctionScale` | `1.0` | same ctor | `>= 1.5` | no |

Two near-misses worth recording, because both are the shape §12.6 warns about:

- **A "low sun" band that included 0 would have been dead.** The component
  default relative rotation is identity, i.e. pitch `0.0`, which reads as "sun
  exactly on the horizon" — the most plausible way to write this check
  (`-30 <= pitch <= 0`) would have passed on a sun nobody rotated. The band's
  upper bound is `-2` for exactly that reason.
- **`USkyAtmosphereComponent` is deliberately presence-only.** Its ctor sets a
  complete, physically calibrated Earth atmosphere (Rayleigh/Mie/ozone
  coefficients from real values). Requiring a *non-default* scattering value
  would be a dead gate in the opposite direction: it would fail the physically
  correct answer. The dawn colour is produced by the sun's angle *through* that
  atmosphere, and the angle is graded on the sun.

`USkyLightComponent.SourceType` was also considered and rejected: its default is
`SLS_CapturedScene`, which is already the correct value for a dynamic sky, so
asserting it would grade nothing. `bRealTimeCapture` (default `false`) carries
the same intent and is a live gate.

## Reflection-visibility audit

Python readability is decided by `CPF_Edit | CPF_BlueprintVisible |
CPF_BlueprintAssignable` alone (`PropertyAccessUtil.cpp:425-433`) and is a
static property of the declaration, so this was settled from headers without an
editor (plan §12.1 — the "protected UPROPERTY" story was a misreading of the
error string, and the retraction is what makes this audit possible offline):

| property | declaration | flags | verdict |
|---|---|---|---|
| `RelativeRotation` | `SceneComponent.h:142` | `EditAnywhere, BlueprintReadOnly` | readable |
| `Intensity` | `LightComponentBase.h:36` | `BlueprintReadOnly` | readable |
| `LightColor` | `LightComponentBase.h:44` | `BlueprintReadOnly` | readable |
| `Temperature` | `LightComponent.h:57` | `EditAnywhere, BlueprintReadOnly` | readable |
| `bUseTemperature` | `LightComponent.h:69` | `EditAnywhere, BlueprintReadOnly` | readable |
| `bRealTimeCapture` | `SkyLightComponent.h:108` | `EditAnywhere, BlueprintReadOnly` | readable |
| `FogDensity` | `ExponentialHeightFogComponent.h:22` | `BlueprintReadOnly` | readable |
| `bEnableVolumetricFog` | `ExponentialHeightFogComponent.h:136` | `EditAnywhere, BlueprintReadOnly` | readable |
| `VolumetricFogExtinctionScale` | `ExponentialHeightFogComponent.h:163` | `EditAnywhere, BlueprintReadOnly` | readable |
| `UBlueprint::Status` | `Blueprint.h` | `transient, BlueprintReadOnly` | readable (not serialized — reads the load-time compile state, which is the property worth gating) |

All four component types carry `meta=(BlueprintSpawnableComponent)`
(`SkyAtmosphereComponent.h:48`, `SkyLightComponent.h:100`,
`DirectionalLightComponent.h:17`, `ExponentialHeightFogComponent.h:16`), so the
whole deliverable shape is legal by construction.

**What the offline audit cannot settle** is the pythonized *spelling* each
property resolves under (`bRealTimeCapture` -> `real_time_capture`?
`b_real_time_capture`?). The script therefore tries several spellings per read
and records a `*_READ_ERROR` if none resolves — but an editor must confirm the
winners before this task is called validated. See §5.

---

## 1. BASELINE asset

**There is none.** This task ships nothing under
`UE-projects/ThirdPerson/Content/Tasks/t1-dawn-fog-lighting-rig/`; the folder
need not exist in the substrate at all. That is a real simplification over the
pilot: there is no baseline to author, no fairness-isolation work-loss hazard
for an untracked baseline, and the empty leg is a genuine `0/14`.

---

## 2. REFERENCE solution

**Path on disk:**
`tasks/bp/t1-dawn-fog-lighting-rig/reference/Content/Tasks/t1-dawn-fog-lighting-rig/BP_DawnLighting.uasset`
**Content path:** `/Game/Tasks/t1-dawn-fog-lighting-rig/BP_DawnLighting`

Create a Blueprint Class parented to plain `Actor`, then add four components
directly under the default scene root. Component **variable names are
case-sensitive and load-bearing** — the verifier matches on
`FSubobjectData::GetVariableName`.

| # | component | variable name | properties to set | check(s) it satisfies |
|---|---|---|---|---|
| 1 | `SkyAtmosphereComponent` | `Sky` | **none** — leave every default | `rig_sky_atmosphere_present` |
| 2 | `SkyLightComponent` | `Ambient` | `Intensity = 0.25`; `Real Time Capture = true` | `rig_sky_light_present`, `skylight_intensity_is_dim`, `skylight_recaptures_live_sky` |
| 3 | `DirectionalLightComponent` | `Sun` | rotation `(Pitch = -8, Yaw = 0, Roll = 0)`; `Light Color = (R=255, G=128, B=70)`; `Intensity = 2.5` | `rig_sun_light_present`, `sun_angle_is_low_dawn`, `sun_color_is_warm`, `sun_intensity_is_dim` |
| 4 | `ExponentialHeightFogComponent` | `Fog` | `Fog Density = 0.6`; `Volumetric Fog = true`; `Extinction Scale = 4.0` | `rig_height_fog_present`, `fog_density_is_dense`, `fog_volumetric_enabled`, `fog_extinction_raised` |

Then compile clean and save (`rig_compiles_up_to_date`).

Expected reference verdict: **L2I `14/14`, overall PASS.** These exact values are
the ones the offline oracle ran the reference leg with.

Three authoring notes:

- **Set the rotation on the `Sun` COMPONENT, not on the actor.** The check reads
  the component template's own `RelativeRotation`; an actor-level rotation is
  not part of the asset the verifier loads.
- The **colour** may instead be delivered as `Use Temperature = true` with
  `Temperature = 2400`. Both routes pass. The reference uses the filter colour
  because it is the one visible in a thumbnail.
- `Fog`'s `Extinction Scale` lives under the *Volumetric Fog* category and only
  takes visible effect with `Volumetric Fog` on — which is why the two are
  separate checks: an agent can plausibly do one and not the other.

---

## 3. Discrimination variants

Five variant `.uasset`s, one per anti-gaming note, specified in
`discrimination/MATRIX.md` and in each variant folder's
`README-MISSING-ASSETS.md`. Each is the reference with exactly ONE deviation, so
the matrix can attribute the FAIL to one gate. In order:

| variant | the single deviation | primary failing check |
|---|---|---|
| `three-lights-no-atmosphere/` | the `Sky` component is not added at all | `rig_sky_atmosphere_present` |
| `named-not-typed/` | `Sun` is a `PointLightComponent` instead of a directional one (everything else identical, including its rotation/colour/intensity) | `rig_sun_light_present` |
| `overhead-noon-sun/` | `Sun` rotation pitch is `-60` instead of `-8` | `sun_angle_is_low_dawn` |
| `default-white-sun/` | `Sun` light colour left at white `(255,255,255)`, temperature untouched | `sun_color_is_warm` |
| `engine-default-fog/` | `Fog` added and every fog property left at the engine default | `fog_density_is_dense` |

---

## 4. Pre-flight before the first graded leg

Two blockers that are not about the assets at all, **both shared with
`t1-hero-blueprint-copy-with-flashlight`** — they are paid once for the pair,
not twice:

1. **`tools/verify-single/tests/test_verdict_taxonomy.py:79`**
   (`test_every_shipping_spec_declares_only_landable_gating_layers`) globs
   `tasks/*/*/task.md` and asserts every spec's layers are exactly
   `("L1","L2")`. Any `L1+L2I` spec makes that test fail the moment it is on
   disk — i.e. CI is red **before** any asset exists. Per plan §9.1 the fix is
   to replace the equality with a landability assertion **and** demonstrate that
   an L2I task really does produce an `L2I` key in `layers_out`. Deliberately
   **not** done by this track — it is a verdict-taxonomy change and wants its
   own review.
2. **Registry bookkeeping (plan §9.2/§12.3).** `cb lint --all` runs
   `inventory.py`, which needs a `tasks/CATALOG.md` row for this id plus the six
   hard-coded task-count claims bumped (the repo conventions, `tasks/CATALOG.md` x2,
   the verifier-building skill (under `.claude/`, not shipped) x2,
   the task-authoring skill (under `.claude/`, not shipped)). This task ships **no
   `.umap`**, so the 8th rule (`inventory-maps-count`) does not fire — 7, not 8.
   The cost is **shared** with the other rows landing in the same window: do one
   reconciliation pass over the final spec count, not one per task.

A third, lint-invisible item at the time: a new task was classified **wired**
rather than validated because that status was read off a dated table kept
outside the repo. That classification has since been removed — a task's
`discrimination/MATRIX.md` is now the only status record, and it is the one
that ships.

## 5. Calibration record

- [x] Reference `BP_DawnLighting.uasset` authored 2026-07-28 (headless
      `-ExecutePythonScript` + SubobjectDataSubsystem construction); the REAL
      grader run in-process against the saved asset reads **14/14**.
- [x] **Property spellings confirmed in a live headless editor** (2026-07-28,
      `-nullrhi`): every write resolved on the FIRST plain pythonized
      spelling — `relative_rotation`, `light_color`, `intensity`,
      `real_time_capture`, `fog_density`, `enable_volumetric_fog`,
      `volumetric_fog_extinction_scale` (DAWNFOG-SPELLING lines, authoring
      log). `use_temperature`/`temperature`/`status` were not exercised (the
      reference uses the filter-colour route; `status` is read-side only).
- [x] **`SubobjectDataSubsystem` confirmed under `-nullrhi`** (2026-07-28):
      the entire authoring pass ran through it headless —
      `k2_gather_subobject_data_for_blueprint`, `add_new_subobject`,
      `rename_subobject`, `get_data`/`get_object` all behaved. This also
      answers the shared-with-pilot question in the authoring direction.
- [x] **The four component types confirmed exposed to Python** (2026-07-28):
      all four (`SkyAtmosphereComponent`, `SkyLightComponent`,
      `DirectionalLightComponent`, `ExponentialHeightFogComponent`) plus
      `PointLightComponent` (the impostor variant) loaded and spawned
      headless. Variant vectors from the in-process grader:
      three-lights-no-atmosphere 13/14 (sky gate), named-not-typed 10/14
      (sun presence + the three sun property reads fan out onto the
      point-light impostor), overhead-noon-sun 13/14, default-white-sun
      13/14, engine-default-fog 11/14 (all three fog gates).
- [ ] Discrimination executed: reference PASS, empty + 5 variants FAIL, each via
      its MATRIX substring.
- [ ] Look inspected once by a human (`--visible`) with the rig dropped into a
      level — **for a human's eyes only**; it never gates, and no verdict may
      cite it.
- [ ] Measured L2I leg wall-clock recorded here (still an inference repo-wide;
      plan §1/§6).
