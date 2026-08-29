# Discrimination matrix — t1-dawn-fog-lighting-rig

The self-validation oracle: the reference solution must PASS and every gaming
variant + the empty leg must FAIL **at the predicted check, via the named
substring**. A wrong-reason FAIL (L1 build failure, a different check, a
`0`-check/`error` L2I verdict, SANDBOX-REJECT exit 4) means the verifier is NOT
discriminated — fix it, or relabel the task for the weaker property it actually
tests.

> **STATUS: NOT RUNNABLE YET.** Every leg of this matrix needs a binary
> `.uasset` that does not exist on disk. The rows, the expected substrings and
> the per-variant asset specs below are complete, authored and proven against
> the real parsers offline; the bytes are not. See **What is missing** and
> `../notes.md`.

## Three parser traps this matrix is written against

- **ONE parseable row per label.** `discriminate.parse_matrix` returns
  `Dict[label -> MatrixRow]` (`discriminate.py:227`), so a *second* table that
  repeats a variant label silently **overwrites** the first — and because a
  table without a "substring"/"message" header column yields an empty message,
  the overwrite lands a blank substring tuple and the leg can never be
  credited. This file therefore has **exactly one table with variant rows**;
  every secondary/derived observation lives in prose below it, where no `|`
  row can re-register a label.
- **Every "Expected substring" cell is a backtick-wrapped literal that
  CONTAINS A SPACE.** `_extract_substrings` (`discriminate.py:195-218`) keeps a
  backticked span only when it is "substantive" — contains a space or one of
  `(),.=` — otherwise it falls through to a last-resort branch that returns the
  cell *with its backticks still attached*, which can never match log text. A
  bare `SCREAMING_SNAKE` check id has neither a space nor that punctuation, so
  it hits the broken branch. Pairing the token with the fixed prefix of the
  text that follows it in the script (`... /Game/Tasks/`, `... names=`,
  `... class=`, `... pitch=`, `... color=`, `... density=`) makes the cell
  substantive **and** keeps it a verbatim substring of the printed `detail`.
  This works whether or not the last-resort branch is ever fixed in code.
- **The reference row's substring cell is `—`.** `_extract_substrings` maps the
  em dash to an empty tuple; anything else there would be matched as a required
  literal on a leg that is supposed to pass with no failing check at all.

## Two L2I traps this matrix is written against

- **The substring is matched against the raw `detail` string as printed inside
  the `CRAFTBENCH-INTROSPECT-JSON` block** — not against the layer's
  `<script>:<check>: FAIL - ...` note rendering. Every "Expected substring"
  cell below is a literal token emitted by
  `tools/verify-single/introspect/dawn_fog_lighting_rig.py`.
- **Exactly ONE introspect script per task.** `registry.py` keeps only
  `li_last_log`, so a substring printed by an *earlier* script could never be
  credited. This task declares one script, and must keep declaring one.

**ASCII rule:** every expected substring is ASCII-only. The UE log's UTF-8
bytes are read back as cp1252, so a non-ASCII character in a detail string
becomes mojibake and the grep misses — a correct FAIL then misclassifies as
wrong-reason (live incident, `t2-homing-projectile`, 2026-07-21). The whole
introspect script is ASCII by construction.

**Error tokens are distinct from failure tokens.** Every exception path in the
script emits a `*_READ_ERROR` / `*_PROBE_ERROR` / `*_WALK_ERROR` /
`*_TYPE_PROBE_ERROR` / `*_TEMPLATE_UNAVAILABLE` / `*_ABORTED` token that appears
in **no** matrix row. So a broken UE API name can never be credited as a
variant's named failure — it shows up as an uncredited FAIL, which is the signal
you want. (Observed directly: run the script with no `unreal` module and all 14
checks fail with `RIG_ASSET_PROBE_ERROR`, which no row claims.)

## Layout (folder-local; agent-writable prefixes only — a stray root file -> SANDBOX-REJECT exit 4)

- `../reference/Content/Tasks/t1-dawn-fog-lighting-rig/…` — the one correct
  solution. The `ThirdPerson` substrate's agent-writable Content carve-out is
  `Content/Tasks/`, so the overlay mirrors that path exactly, including the
  per-task segment.
- `<variant>/Content/Tasks/t1-dawn-fog-lighting-rig/…` — one dir per
  anti-gaming note, sibling to this MATRIX.md.
- empty leg — run IMPLICITLY by `cb discriminate` (it creates a throwaway empty
  dir; nothing to author). Its row documents the expected first-gate failure.

This task ships **no baseline asset**: the substrate contains nothing under
`Content/Tasks/t1-dawn-fog-lighting-rig/`, so the empty leg is a genuinely
empty deliverable and scores `0/14`.

## Matrix

**This is the only table in this file that carries variant rows.** Do not add a
second one — see the first parser trap above.

| Submission | Overall | Fails at (check id) | Expected substring | Also fails (recorded, not matched) | Anti-gaming note |
|---|---|---|---|---|---|
| `../reference` | PASS | — | — | none — all 17 checks green (17/17) | — |
| empty | FAIL | `rig_asset_exists` | `RIG_ASSET_MISSING /Game/Tasks/` | the other 16 checks fan out on the same root cause (`0/17`) | #1 / FR-017 |
| `three-lights-no-atmosphere/` | FAIL | `rig_sky_atmosphere_present` | `RIG_SKY_ATMOSPHERE_MISSING names=` | — | #1 one of the four parts quietly dropped; scores 16/17 |
| `named-not-typed/` | FAIL | `rig_sun_light_present` | `RIG_SUN_LIGHT_WRONG_TYPE class=` | `sun_angle_is_low_dawn`, `sun_color_is_warm`, `sun_intensity_is_dim`, `sun_casts_shadows` | #2 right name, wrong thing; scores 12/17. The shadow gate JOINED this fan-out 2026-08-19 — it resolves the sun through the same type-checked lookup, so a wrong-typed `Sun` cascades into it too. Recorded because the row would otherwise overstate this leg's isolation, and because the cascade is invisible to `cb discriminate`, which only checks that the leg fails at its NAMED substring — which it still does |
| `overhead-noon-sun/` | FAIL | `sun_angle_is_low_dawn` | `SUN_PITCH_NOT_LOW world_pitch=` | — | #3 lights added, look never dialled; scores 16/17 |
| `default-white-sun/` | FAIL | `sun_color_is_warm` | `SUN_COLOR_NOT_WARM color=` | — | #3 lights added, look never dialled; scores 16/17 |
| `engine-default-fog/` | FAIL | `fog_density_is_dense` | `FOG_DENSITY_TOO_THIN density=` | `fog_volumetric_enabled`, `fog_extinction_raised` | #4 fog present at engine defaults; scores 14/17 |

Why each "Also fails" entry is expected and does **not** make the
discrimination muddy (prose on purpose — a table here would re-register the
labels and blank their substrings):

- `named-not-typed/` also fails `sun_angle_is_low_dawn`, `sun_color_is_warm`
  and `sun_intensity_is_dim`, all three carrying the **same**
  `RIG_SUN_LIGHT_WRONG_TYPE class=` detail. That is deliberate: when the part
  named `Sun` is not a directional light, its numbers are meaningless, so
  `_sun_checks` fans out the single resolution failure instead of inventing
  three unrelated numeric verdicts against whatever object is sitting there.
  One cause, one token, four checks.
- `engine-default-fog/` also fails `fog_volumetric_enabled`
  (`FOG_VOLUMETRIC_DISABLED enabled=`) and `fog_extinction_raised`
  (`FOG_EXTINCTION_TOO_LOW scale=`): a fog part left exactly as the engine
  constructs it misses all three fog gates at once. Three independent checks
  catching the same "never touched it" defect is the point of anti-gaming #4.
- `three-lights-no-atmosphere/` fails **only** its one check. The sky
  atmosphere carries no graded number of its own (see the spec's *Why the sky
  atmosphere is presence-only*), so nothing fans out from it.

Coverage note (bounded, argued from the named checks rather than run as
separate submissions):

- A rig that gets the sun's angle right **by rotating the rig's root instead of
  the light component** is an ACCEPTED solution, and used to be a FALSE
  NEGATIVE. `sun_angle_is_low_dawn` grades the WORLD-space elevation of the
  sun's forward vector, composed up the SCS attach chain
  (`_world_elevation_of`), not the light's own `RelativeRotation`. Before
  2026-07-27 it read the component only, so root-pitch -8 / light-pitch 0 —
  visually identical to the reference — failed with
  `SUN_PITCH_NOT_LOW world_pitch=0.0000`. No variant is authored for the
  accepted shape (a variant is by definition a leg that must FAIL); it is
  pinned in the offline oracle instead, as
  `TestWorldSpaceSunAngle::test_a_rig_rotated_at_the_root_is_accepted`,
  alongside its mirror — a rig whose root cancels the light's rotation back to
  the horizon is REJECTED, so composition did not just widen the gate.
- A rig whose sun uses a **low colour temperature** instead of a red filter
  colour is an ACCEPTED solution: `sun_color_is_warm` passes on either route
  (`bUseTemperature` on with 1000–4000 K, or R > G > B with a >= 60 red/blue
  gap). Both exclude the engine default (white, 6500 K, temperature off), so
  accepting both costs no discriminating power.
- A rig with a correctly warm, correctly angled sun left at full brightness
  dies at `sun_intensity_is_dim` (`SUN_INTENSITY_NOT_DIM value=`); no separate
  variant is authored because `default-white-sun/` and `overhead-noon-sun/`
  already prove that a single mis-set number on the sun is caught in isolation.
- A rig whose ambient fill is left at a baked capture dies at
  `skylight_recaptures_live_sky` (`SKYLIGHT_NOT_REALTIME capture=`), and one
  left at full ambient brightness dies at `skylight_intensity_is_dim`
  (`SKYLIGHT_INTENSITY_NOT_DIM value=`). Same argument.
- A rig left in an uncompiled state dies at `rig_compiles_up_to_date`
  (`RIG_NOT_UP_TO_DATE status=`); no variant is authored for it because
  producing that state deliberately requires hand-editing a `.uasset`'s
  transient compile state, which is not reliably authorable.

## What is missing (this matrix cannot run until these exist)

**`.uasset` binaries cannot be authored from a text-only track.** Six binaries
are needed. Each variant folder holds a `README-MISSING-ASSETS.md` at the exact
path the `.uasset` must occupy, describing property-by-property what to author;
**delete that README in the same commit that lands the real asset.** The full
property-level spec for the reference is `../notes.md`.

| # | Path | What it must be |
|---|---|---|
| 1 | `../reference/Content/Tasks/t1-dawn-fog-lighting-rig/BP_DawnLighting.uasset` | the **reference**. `notes.md` §2 |
| 2 | `three-lights-no-atmosphere/Content/Tasks/…/BP_DawnLighting.uasset` | variant. See that folder's README |
| 3 | `named-not-typed/Content/Tasks/…/BP_DawnLighting.uasset` | variant |
| 4 | `overhead-noon-sun/Content/Tasks/…/BP_DawnLighting.uasset` | variant |
| 5 | `default-white-sun/Content/Tasks/…/BP_DawnLighting.uasset` | variant |
| 6 | `engine-default-fog/Content/Tasks/…/BP_DawnLighting.uasset` | variant |

No variant needs any second asset: `apply_submission` is a copy-only overlay
with no wipe, and this task ships no baseline, so each variant is exactly one
file.

## How to run (deterministic verifier, no agent, no tokens)

```sh
cb discriminate --task bp/t1-dawn-fog-lighting-rig
```

Per-leg fallback while iterating on one variant (a short `--workdir` dodges
Windows MAX_PATH; use the `py` launcher — this box's `py -3.12` does not
resolve):

```sh
UE='<UE-root>'
py tools/verify-single/run_task.py \
    --task tasks/bp/t1-dawn-fog-lighting-rig/task.md \
    --submission tasks/bp/t1-dawn-fog-lighting-rig/discrimination/overhead-noon-sun \
    --ue-root "$UE" --workdir C:\cb\wd\kv3var       # expect exit 1
```

Then open the workdir's `report.json` and the `L2I` log it names, find the
`CRAFTBENCH-INTROSPECT-JSON-START` block, and confirm the failing check's raw
`detail` contains this table's "Expected substring" cell.

**L2I graders are read from the LIVE working tree** (`registry.py:312` resolves
`introspect_root = _VERIFY / "introspect"`), unlike L2 fixtures which come from
git HEAD. So iterating on `dawn_fog_lighting_rig.py` needs no commit — but the
`.uasset` files DO need committing before a non-`--wip` grade sees them
(`run_task` materializes the substrate from git HEAD).

## Status

- Authored 2026-07-27 from the spec, text-only track. **Never executed against
  a real editor** — no leg has run in UE, because no `.uasset` exists yet.
- **Proven offline, against the real parsers.** All six rows here parse out of
  this file through the REAL `aura_rig.discriminate.parse_matrix` with
  non-empty, backtick-free substrings (the reference row deliberately empty),
  and each substring is proven to be a literal
  `tools/verify-single/introspect/dawn_fog_lighting_rig.py` actually prints on
  that leg — simulated with a fake `unreal` module and read back through the
  REAL `layers/l2_introspect.parse_introspect_verdict` at a constant 14-check
  denominator. That is the LOGIC oracle, not an engine oracle.
- **Still missing, in order:** (1) the six `.uasset` binaries above — nothing
  here can run in UE without them; (2) a live-editor confirmation of the four
  UE property spellings the offline fake cannot settle
  (`relative_rotation` / `GetRelativeRotation`, `light_color`,
  `real_time_capture`, `enable_volumetric_fog`, `volumetric_fog_extinction_scale`)
  — the script tries several spellings each, but only an editor decides;
  (3) the `discriminate.py` last-resort backtick strip — this file does not
  *depend* on it, but every future L2I MATRIX will hit the same trap until it
  lands.
- Blocked additionally on `tools/verify-single/tests/test_verdict_taxonomy.py:79`
  (`test_every_shipping_spec_declares_only_landable_gating_layers`), which
  asserts every spec on disk is exactly `("L1","L2")` and therefore fails as
  soon as any `L1+L2I` spec exists. Plan §9.1 assigns replacing that equality
  with a landability assertion to Phase 1; it is shared with
  `t1-hero-blueprint-copy-with-flashlight`, not additional work for this row.

## Requirements table (checklist §7, the mandatory soundness artifact)

This task grades `[L1, L2I]` on the `ThirdPerson` substrate — there is no L2 fixture and no map. Every
backticked token in the "Enforcing gate" column below is verbatim-greppable in the one declared grader,
`tools/verify-single/introspect/dawn_fog_lighting_rig.py` (14 checks, constant denominator); the check id is
the durable join key. Several failing details are runtime-COMPOSED via Python `%`-format strings; those rows
are marked "(composed)" and quote the source-side pieces instead of the emitted string: the constant token
stem (e.g. `RIG_ASSET_MISSING`, `RIG_SKY_ATMOSPHERE`) plus the contiguous format-string fragment it is joined
to — `_resolve`'s `_MISSING names=` / `_WRONG_TYPE class=` / `_TYPE_PROBE_ERROR class=` family, the
missing-asset join `%s %s`, the pre-declared path template `/Game/Tasks/%s/BP_DawnLighting`, and the warmth
summary head `color=(R=`. L1 is a content-only precondition (the project must still build), never a
correctness signal; when L1 fails, no L2I check runs at all. Within L2I there are THREE fan-out routes, in
evaluation order: (a) `rig_asset_exists` fails → ALL 13 remaining checks fan out carrying its detail;
(b) the asset loads but the subobject walk raises → every non-compile check (rows 4–18) fans out carrying
`RIG_SUBOBJECT_WALK_ERROR raised ` while `rig_compiles_up_to_date` still runs; (c) one of the four parts
fails to resolve (absent / impostor / unprobeable type) → that part's value checks fan out carrying the
resolution detail — never an invented numeric verdict.

| # | Prompt requirement | Asserted | Enforcing gate — verbatim token | Gate skipped when | What a submission could still get away with |
|---|---|---|---|---|---|
| 1 | one asset at the exact folder + name: `Content/Tasks/t1-dawn-fog-lighting-rig/BP_DawnLighting` | fully | `rig_asset_exists` — `RIG_ASSET_MISSING` + path (composed, `%s %s`; probe is `does_asset_exist` on the pre-declared path template `/Game/Tasks/%s/BP_DawnLighting` filled with `t1-dawn-fog-lighting-rig`) | unconditional (first check); L1 FAIL prevents the whole layer | nothing on location/name — an asset saved anywhere else in the writable set simply never resolves and dies here |
| 2 | the asset is a *placeable* game object | **fully** (closed 2026-08-19) | `rig_is_placeable_actor` — `RIG_NOT_PLACEABLE generate_abstract_class=True`; an unreadable flag FAILS via `RIG_PLACEABLE_UNREADABLE` / `RIG_PLACEABLE_READ_ERROR raised ` (fail-closed: unreadable placeability is not evidence of placeability) | row 1 fan-out; walk-error route (b) | the prompt says "Produce one **placeable** game-object asset", and before this a Generate-Abstract-Class rig scored 14/14 while being undroppable. Reference measured `generate_abstract_class=False` |
| 3 | dropping it into an otherwise unlit level lights the whole scene as a foggy early dawn (the LOOK: dim, gloomy, warm red sun, distance swallowed) | by numeric proxy — deliberate (task divergence 1, FR-020d: no render, no PIE, no pixel ever reaches the verdict) | the nine value gates of rows 9–13 and 16–18 stand in for the look | n/a | a rig whose numbers all sit in-band but whose ungated dimensions are wrong (sun yaw, fog height offset, atmosphere transform) passes while looking wrong on screen — accepted residual, human-inspected only |
| 4 | carries a part named `Sky` = the physically modelled body of air (sky colour + distance haze, not a painted backdrop) | fully (name AND `isinstance`) | `rig_sky_atmosphere_present` — stem `RIG_SKY_ATMOSPHERE` (composed): absent → `_MISSING names=`; impostor → `_WRONG_TYPE class=` (SkyAtmosphereComponent, subclass-tolerant); unprobeable type FAILS via `_TYPE_PROBE_ERROR class=` | asset missing (row 1 fan-out); subobject walk raised (route (b) `RIG_SUBOBJECT_WALK_ERROR raised ` fan-out) | every atmosphere property value — presence-only BY DESIGN (the calibrated engine defaults ARE a correct dawn atmosphere; spec: *Why the sky atmosphere is presence-only*) |
| 5 | carries `Ambient` = the sky-reading fill light | fully (name AND `isinstance`) | `rig_sky_light_present` — stem `RIG_SKY_LIGHT` (composed): `_MISSING names=` / `_WRONG_TYPE class=` (SkyLightComponent) | row 1 fan-out; walk-error route (b) | a legitimate subclass (by design) |
| 6 | carries `Sun` = a distant directional light | fully (name AND `isinstance`) | `rig_sun_light_present` — stem `RIG_SUN_LIGHT` (composed): `_MISSING names=` / `_WRONG_TYPE class=` (DirectionalLightComponent) | row 1 fan-out; walk-error route (b) | a legitimate subclass (by design) |
| 7 | carries `Fog` = height/distance fog | fully (name AND `isinstance`) | `rig_height_fog_present` — stem `RIG_HEIGHT_FOG` (composed): `_MISSING names=` / `_WRONG_TYPE class=` (ExponentialHeightFogComponent) | row 1 fan-out; walk-error route (b) | a legitimate subclass (by design) |
| 8 | *exactly* four working parts — no extras | **fully** (closed 2026-08-19) | `rig_carries_only_the_four_parts` — `RIG_EXTRA_PARTS extras=` naming the offending part(s); an unreadable hierarchy FAILS via `RIG_CENSUS_READ_ERROR raised ` | row 1 fan-out; walk-error route (b) | the prompt says "It must carry **exactly four** working parts", and the four presence checks were floors — a fifth bright point light re-lighting the "dim" scene scored full marks (14/14 under the pre-2026-08-19 denominator). **Two things are excluded from the count, both measured not assumed:** the actor ROOT subobject (not a component — its object is the actor CDO) and UE's structural attach root, identified by TOPOLOGY (no scene-component ancestor) rather than by name. Exactly ONE structural root is tolerated, so "attach nothing and pass" is not a replacement loophole. The first cut of this gate FAILED the reference at `extras=['DefaultSceneRoot']` |
| 9 | `Ambient` keeps re-reading the live sky (not frozen to a stored snapshot) | fully | `skylight_recaptures_live_sky` — `SKYLIGHT_NOT_REALTIME capture=` (`bRealTimeCapture` must be true; engine default false) | rows 1/5 fan out (carries the Ambient resolution token); walk-error route (b) | nothing — the flag is the behaviour |
| 10 | `Ambient` fill held well down — clearly weaker than the untouched part | fully | `skylight_intensity_is_dim` — `SKYLIGHT_INTENSITY_NOT_DIM value=` (Intensity in [0.01, 0.6]; engine default 1.0 excluded) | rows 1/5 fan out; walk-error route (b) | anywhere in the band — a near-off 0.01 fill passes (floor deliberately relaxed, 2026-07-27 widening) |
| 11 | `Sun` sits just over the horizon, light raking almost level | fully, in WORLD space | `sun_angle_is_low_dawn` — `SUN_PITCH_NOT_LOW world_pitch=` (forward-vector elevation composed up the SCS attach chain, in [-25, -1] deg; default 0.0 excluded) | rows 1/6 fan out; walk-error route (b); an unreadable rotation FAILS via `SUN_PITCH_READ_ERROR raised ` | rotating the rig root instead of the light is ACCEPTED (by design, oracle-pinned); yaw is free |
| 12 | `Sun` warm and red — red-dominant filter colour OR low colour temperature | fully, either route | `sun_color_is_warm` — `SUN_COLOR_NOT_WARM` + summary head `color=(R=` (composed; route A: `bUseTemperature` on AND 1000–4000 K; route B: strict R > G > B with R >= 150 and R − B >= 60; default white/6500 K/off fails both) | rows 1/6 fan out; walk-error route (b) | anything from deep ember to pale amber — the band is deliberately generous |
| 13 | `Sun` dim — noticeably darker than untouched, but still lighting the scene | fully | `sun_intensity_is_dim` — `SUN_INTENSITY_NOT_DIM value=` (Intensity in [0.05, 5.0]; engine default 10 excluded — the 5.0 ceiling IS the discrimination) | rows 1/6 fan out; walk-error route (b) | a barely-on 0.05 sun ("still lighting the scene" is graded only as "not switched off in all but name") |
| 14 | `Sun` is THE ONE light that casts the scene's shadows | **partially** (the CASTS half closed 2026-08-19) | `sun_casts_shadows` — `SUN_CASTS_NO_SHADOWS cast_shadows=False`; unreadable FAILS via `SUN_SHADOW_UNREADABLE` / `SUN_SHADOW_READ_ERROR raised ` | rows 1/6 fan out; walk-error route (b) | the prompt says "`Sun` — the **one** distant light that casts the scene's shadows". The CASTS half is now gated (reference measured `cast_shadows=True`; the engine default merely happens to be on, so this is conjoined with the sun's non-default presence and dimming). The **ONE** half is now carried by row 8's census, which rejects a second directional light under another name |
| 15 | `Fog` thickens toward the ground | partially — by component TYPE only | `rig_height_fog_present` (stem `RIG_HEIGHT_FOG` + `_WRONG_TYPE class=`, composed — rejects a non-height-fog impostor, and an exponential height fog has a ground-thickening falloff by construction) | row 1 fan-out; walk-error route (b) | `FogHeightFalloff` is unbanded — dial it to ~0 and the fog is effectively uniform with no ground gradient, still 14/14 |
| 16 | `Fog` genuinely dense — swallows the distance, far beyond the untouched part's thin haze | fully | `fog_density_is_dense` — `FOG_DENSITY_TOO_THIN density=` (FogDensity in [0.1, 10.0]; floor is 5x the 0.02 engine default) | rows 1/7 fan out; walk-error route (b) | anywhere in a wide band — over-delivering up to 10.0 passes (ceiling deliberately raised) |
| 17 | `Fog` simulated through the world volume, not a flat screen-depth tint | fully | `fog_volumetric_enabled` — `FOG_VOLUMETRIC_DISABLED enabled=` (`bEnableVolumetricFog` must be true; default false) | rows 1/7 fan out; walk-error route (b) | nothing — the flag is the behaviour |
| 18 | light the fog absorbs turned up well above where it starts | fully | `fog_extinction_raised` — `FOG_EXTINCTION_TOO_LOW scale=` (`VolumetricFogExtinctionScale` >= 1.5; engine default 1.0 excluded) | rows 1/7 fan out; walk-error route (b) | no ceiling — an extreme extinction passes |
| 19 | `BP_DawnLighting` must compile cleanly | fully (warnings tolerated by design) | `rig_compiles_up_to_date` — `RIG_NOT_UP_TO_DATE status=` (transient `UBlueprint::Status` re-derived on load; `UP_TO_DATE` substring accepted, which admits BS_UpToDateWithWarnings) | asset missing (row 1 fan-out); note it still RUNS when the subobject walk errors | a compile with WARNINGS passes — "cleanly" is graded as "neither dirty nor in error" |
| 20 | ...and be saved | fully, by the substrate model | not a separate gate — the runner grades a file overlay materialized onto a clean substrate, so unsaved editor state presents as a missing file and dies at row 1's `RIG_ASSET_MISSING` (composed, row 1) | unconditional | nothing |
