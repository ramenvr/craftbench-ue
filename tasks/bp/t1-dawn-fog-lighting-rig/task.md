---
id: t1-dawn-fog-lighting-rig
substrate: ThirdPerson
set: bp
tier: T1
capability_bucket: Content, Data, Assets
category: lighting
layers: [L1, L2I]
introspect: [dawn_fog_lighting_rig.py]
---

# t1-dawn-fog-lighting-rig

The second `L1 + L2I` spec in the repo, after
`t1-hero-blueprint-copy-with-flashlight`. It follows that pilot's shape exactly
— one agent-authored `.uasset` under `Content/Tasks/<task-id>/`, one
verifier-owned introspect script, no map, no fixture C++, no scaffold actor —
and adds the thing this row is actually about: **numeric property bands, every
one of them dead-gate audited against the UE 5.8 engine default it must
exclude.**

### Provenance and deliberate divergences from the source row

Imported from an earlier internal task list (not shipped): a lighting-and-
atmosphere row that was never implemented there. The source row's own
**Issues** cell reads *"Need vision based eval?"* and
its Verification cell is two lines, the second of which is
*"Screenshot to visually verify the lighting is as requested?"*.

Six deliberate divergences, each recorded so the source row and the task can be
reconciled:

1. **Vision is out; numbers are in.** Per the plan's decision **D3** (owner,
   2026-07-27) this row gates on **presence plus numeric property bands** only.
   The look is inspected by a human and **never** reaches a verdict —
   which is also what the repo's law already requires (FR-020d: the PASS/FAIL
   gate is fully deterministic, no LLM-as-judge, no pixel comparison). Every
   quality the source row describes in words — *dim*, *warm red*, *low angle*,
   *dense*, *short visibility* — is a number on a component, so nothing about
   the graded behavior is lost by dropping the screenshot.
2. **The deliverable is an ASSET, not a level.** This is the substantive
   divergence and it is forced. See **Why this row is not graded on a level**
   below: there is no route in the harness today that grades an agent-authored
   `.umap`, and inventing one is a harness change (plan U7), not a task. The
   agent instead delivers one placeable lighting rig asset carrying the same
   four lighting parts with the same numeric values; dropping it into an unlit
   level lights that level. The graded capability — *can the agent stand up the
   four pieces of a modern UE sky/lighting stack and dial them to a described
   look* — is preserved intact. The **only** thing dropped is "and place them
   as four separate actors in a saved level".
3. **Content path.** The source row's `/Game/EvalTemplate/` **does not exist
   anywhere in the repo** (the only occurrence of that string is the source
   list), and a flat `/Game/EvalTemplate/` is outside every writable prefix of
   both substrates. Re-pathed to the repo convention `/Game/Tasks/<task-id>/`,
   which is agent-writable and fairness-pruned per task.
4. **Id.** The source row's `t2-` is a row index; this repo's `t<N>-` is a tier.
   Retiered to `T1` and re-slugged to the observable outcome. The plan's §11.1
   table pencilled in `t1-level-lighting-and-atmosphere`; that slug is now
   wrong in its load-bearing word ("level"), so the id names what the agent
   actually produces. Rationale and the id-substring constraint:
   the set-provenance note (internal, not shipped).
5. **The look is described; the bands are NOT in the prompt.** The source row
   gives the agent adjectives only (*dim*, *warm red*, *low angle*, *dense*)
   and no numbers, and this task keeps it that way. An earlier draft of this
   spec restated every graded threshold verbatim in the agent-visible prompt —
   *"between `0.05` and `0.6`"*, *"between **2 and 20 degrees below
   horizontal**"*, *"red channel at least `150`"* — on the argument that
   adjectives alone make the eval a guessing game about the author's taste.
   That argument is wrong, and the draft was **reverted 2026-07-27**: printing
   the band in the prompt *is* printing the answer key. An agent handed the
   rubric tunes to the band — it can satisfy every gate by typing nine numbers
   it was given, without ever knowing that a dawn sun is low or that fog gets
   thicker near the ground — so the row stops measuring the craft it exists to
   measure and measures transcription instead. The numbers now live **only** in
   *Verifier specification* below, which `prompt_extract.py` does not emit.
   What the agent is given instead is the look in behavioural terms plus, for
   each graded value, the **direction of travel relative to the untouched
   part** ("clearly weaker than the fill you get from that part left as you
   find it", "nowhere near enough", "turned up well above where it starts") —
   which is exactly the property the dead-gate audit is built on, stated
   without disclosing where the line falls. Divergence 6 records the band
   widening that this reversal made necessary.

6. **Bands widened for a prompt that no longer names them** (2026-07-27, same
   change as divergence 5). A threshold an agent can read is a target; a
   threshold it cannot read has to be *reachable by anyone who actually
   produced the described look*. Five bands were re-cut on that test — the two
   intensity floors, the sun-pitch band, the fog-density band and the fog
   extinction floor. Each widening, with its justification and its re-run of
   the dead-gate column, is in *Verifier specification* under **Every band
   excludes the engine default**. Two bands were deliberately **left alone**:
   `sun_color_is_warm` (the phrase "warm and red" pins the colour unambiguously,
   and both of its routes are already generous) and every boolean check (a
   boolean has no band to widen).

### Why this row is not graded on a level — the evidence

The source row's start state is *"Empty level with lighting deleted"* and its
deliverable is level state. That has **no grading route in the harness today**,
for four independent reasons, all checked in code on 2026-07-27:

1. **`map_locator.locate_map` searches only `Content/Maps/`**
   (`tools/verify-single/map_locator.py:43-51`), while
   `tasklint._check_map` also accepts `Content/Tasks/`
   (`tasklint.py:403-417`) — a live lint/runtime divergence recorded as plan
   **O3**. `Content/Maps/` is **deny-listed** in both substrates'
   `AGENT_WRITABLE.json`, so an agent can never write where the locator looks.
2. **L2 in an agent-authored map is impossible by construction.** An L2 fixture
   must be pre-placed in a committed map and the map scaffolders were retired
   2026-07; there is no way to get a verifier-owned `AFunctionalTest` into a map
   the agent invents.
3. **L2I does not open a map at all.** `layers/l2_introspect.py:168-177` builds
   the editor command line as
   `UnrealEditor-Cmd <project> -ExecutePythonScript=<script> -nullrhi …` with
   **no map argument**, and `map_locator` is imported only by the L2 and L3
   branches of `layers/registry.py` (`:123`, `:389`) — never by
   `L2IntrospectLayer`. So an L2I script would have to load the agent's level
   itself, headless, under `-nullrhi`. That read is **unspiked** (plan U1 lists
   "level load/enumerate" as an open probe) and cannot be spiked from this
   track without an editor.
4. **Even a successful level would likely be rejected at the sandbox.** A level
   authored with One-File-Per-Actor writes its actors into
   `Content/__ExternalActors__/…`, which is an explicit `deny` prefix in
   `UE-projects/ThirdPerson/AGENT_WRITABLE.json` — so the actors would either be
   dropped from the submission or trip SANDBOX-REJECT (exit 4), and the correct
   solution would fail for a reason that has nothing to do with lighting.

**The choice taken** (of the two the plan offers) is therefore **"scope the row
to assets the agent saves under `Content/Tasks/<id>/`"**, not "declare the row
BLOCKED on U7". The asset route needs **zero** harness changes and reuses the
component-walk route already proven end-to-end by the pilot; the level route
needs U7 *plus* a `-nullrhi` map-load spike *plus* an OFPA/deny-prefix decision.
The row that would have been blocked is **row R2**
(`t2-basic-level-setup`), whose whole deliverable *is* the level layout and
which has no asset-shaped equivalent — that one stays blocked on U7, and this
spec does not pretend otherwise.

> **Note on the behavior-only rule (Hard Rule #2).** Like
> `t1-hero-blueprint-copy-with-flashlight` and `t0-sanity-bp-log-on-beginplay`,
> this task names the concrete deliverable asset path and the four subobject
> names the verifier keys on. That is the standard, precedented exception for
> asset-deliverable tasks whose whole point *is* producing a specific asset —
> naming the path lets the verifier load one asset directly instead of scanning
> content. Everything else in the prompt stays behavior-only: **no component
> type name and no editor operation name appears in it.** The four parts are
> described by what they do (the modelled air that colours the sky; the fill
> light that reads that sky; the one distant shadow-casting light; the ground
> fog), never by their class names, and **no graded threshold appears in the
> prompt at all** — each value is asked for as a look and a direction of
> travel away from the untouched part, never as a number or a range (see
> divergences 5 and 6).

## Primary concept

- `sky-atmosphere` — Sky Atmosphere Component
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/sky-atmosphere-component-in-unreal-engine)

The load-bearing capability is standing up a **modern UE dynamic-sky lighting
stack** — the physically modelled atmosphere, the sky-driven ambient fill, the
single directional key light and the height fog — and then dialling four of its
numeric knobs to hit a *described look* rather than a named preset. The
adjacent concept is `ps-components` (Components,
https://dev.epicgames.com/documentation/en-us/unreal-engine/components-in-unreal-engine),
which the composition half exercises; it is not the primary one, because the
graded difficulty is knowing which four pieces a dawn sky is made of and which
property on each is the one the description names.

## Prompt given to the agent

> This project ships no lighting content of its own. The folder
> `Content/Tasks/t1-dawn-fog-lighting-rig/` is empty, and nothing in it lights
> anything.
>
> Produce one placeable game-object asset in that folder, named
> `BP_DawnLighting`. Dropping that single object into an otherwise unlit level
> must be enough to light the whole scene as a **foggy early dawn**: a dim,
> gloomy world in the first minutes of light, a warm red sun sitting just over
> the horizon, and fog thick enough that the distance disappears into it.
>
> It must carry exactly four working parts, named `Sky`, `Ambient`, `Sun` and
> `Fog`:
>
> - **`Sky`** — the physically modelled body of air wrapped around the planet:
>   the thing that gives the scene its sky colour and its distance haze rather
>   than painting a fixed backdrop.
> - **`Ambient`** — the soft fill that takes its colour from that sky and lifts
>   what the sun does not reach. It must keep re-reading the live sky as the sky
>   changes, instead of being frozen to one stored snapshot. This is pre-dawn
>   shadow, not a bright overcast morning, so hold the fill well down — clearly
>   weaker than the fill you get from that part left as you find it.
> - **`Sun`** — the one distant light that casts the scene's shadows. Sit it
>   just over the horizon, so its light rakes across the ground almost level
>   instead of coming down from above. Make it warm and red: *either* give it a
>   filter colour that is strongly red-dominant — red clearly ahead of green,
>   green clearly ahead of blue — *or* switch it over to a low, firelight-warm
>   colour temperature. And keep it dim: a sun that has only just cleared the
>   horizon, noticeably darker than an untouched one, but still lighting the
>   scene.
> - **`Fog`** — distance fog that thickens toward the ground, and genuinely
>   dense: the thin haze an untouched fog part gives you is nowhere near
>   enough, this fog has to swallow the distance. It must also be simulated
>   through the volume of the world rather than applied as a flat screen-depth
>   tint, and the light that fog absorbs on its way through that volume must be
>   turned up well above where it starts.
>
> `BP_DawnLighting` must compile cleanly and be saved.

## Workspace state pre-task

Substrate content that **exists** under
`Content/Tasks/t1-dawn-fog-lighting-rig/`:

- Nothing. This task ships **no baseline asset**. The folder is the
  agent-writable Content carve-out of the `ThirdPerson` substrate
  (`UE-projects/ThirdPerson/AGENT_WRITABLE.json` lists `Content/Tasks/` under
  both `writable` and `asset_writable`) and is where this task's content
  belongs; fairness isolation keeps this task's folder while hiding every other
  task's.

Files that **do not exist** (the agent must create):

- `Content/Tasks/t1-dawn-fog-lighting-rig/BP_DawnLighting.uasset`.

Out of scope / not needed:

- No C++ is required or expected. No level needs to be created, opened or
  saved, and no level is graded: the whole deliverable is one asset.
  `Content/Maps/`, `Content/__ExternalActors__/`, `Config/`,
  `Content/Characters/`, `Content/ThirdPerson/` and `Content/Input/` are
  deny-listed — the agent neither can nor needs to touch them.

## Verifier specification

Layer choice: this task grades via **L1 + L2I**. Every graded property is a
static property of a saved `.uasset` (which subobjects exist, what type each
one is, and six numbers on three of them), so it is read by verifier-owned
editor-Python reflection over the submitted asset — not by rendering, ticking,
or a PIE world. L2 is deliberately **not** declared: there is nothing to observe
over time, and a fixture would need a map and a placed actor this task has no
use for. L3 is **not** declared either, even though the source row asks for a
screenshot — see divergence 1.

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

The submission is content-only, so L1 is a precondition (the project and its
Asset Registry must load cleanly), never a correctness signal.

### L2I — Structural assertion

The verifier-owned script
`tools/verify-single/introspect/dawn_fog_lighting_rig.py` runs headless via
`UnrealEditor-Cmd -ExecutePythonScript=` under `-nullrhi`, read-only, and prints
one `CRAFTBENCH-INTROSPECT-JSON` verdict block. It emits **exactly 14 named
checks on every leg** (a constant denominator, so the per-check
`tests_passed/tests_run` the registry already records is comparable across
submissions). PASS requires all 14:

```text
rig_asset_exists                /Game/Tasks/<id>/BP_DawnLighting resolves
rig_sky_atmosphere_present      a subobject named "Sky" exists AND is an
                                atmosphere component
rig_sky_light_present           "Ambient" exists AND is a sky-light component
rig_sun_light_present           "Sun" exists AND is a directional-light component
rig_height_fog_present          "Fog" exists AND is a height-fog component
sun_angle_is_low_dawn           Sun's own relative-rotation pitch in [-25, -1] deg
sun_color_is_warm               Sun is warm by EITHER route: colour temperature
                                switched ON and in [1000, 4000] K, OR filter
                                colour with R > G > B, R >= 150, R - B >= 60
sun_intensity_is_dim            Sun brightness in [0.05, 5.0]
skylight_intensity_is_dim       Ambient brightness in [0.01, 0.6]
skylight_recaptures_live_sky    Ambient re-captures the live sky (not a frozen
                                stored capture)
fog_density_is_dense            Fog density in [0.1, 10.0]
fog_volumetric_enabled          Fog is simulated through the world volume
fog_extinction_raised           Fog light-absorption scale >= 1.5
rig_compiles_up_to_date         the asset loads with an up-to-date compile
                                status (BS_UpToDate / ...WithWarnings)
```

**These bands are verifier-only and must stay here.** Not one of the numbers
above appears in *Prompt given to the agent*, and none may be moved there.
`tools/run-agent/prompt_extract.py` emits exactly two H2 sections — *Prompt
given to the agent* and *Workspace state pre-task* — so everything in this
section is invisible to the agent by construction, and that is the property
this row's discriminating power rests on (divergences 5 and 6). A prompt that
restates a band grades transcription, not craft.

**Read routes.** Every property read below was checked against its `UPROPERTY`
declaration in UE 5.8 engine source *before* being relied on, because Python
readability is decided by `CPF_Edit | CPF_BlueprintVisible |
CPF_BlueprintAssignable` alone (`PropertyAccessUtil.cpp:425-433`) and is a
static property of the declaration:

- *asset existence* — `unreal.EditorAssetLibrary.does_asset_exist`.
- *component walk* — `unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)`.
  It is an **engine** subsystem: `get_editor_subsystem` raises
  `TypeError: Cannot nativize`. Then
  `SubobjectDataBlueprintFunctionLibrary.get_data / get_variable_name /
  get_object`. This is the same walk the pilot proved live on UE
  5.8.0-55116800 (plan §10.1).
- *component type* — `isinstance` against `unreal.SkyAtmosphereComponent`,
  `unreal.SkyLightComponent`, `unreal.DirectionalLightComponent`,
  `unreal.ExponentialHeightFogComponent`. All four carry
  `meta=(BlueprintSpawnableComponent)` in their `UCLASS`
  (`SkyAtmosphereComponent.h:48`, `SkyLightComponent.h:100`,
  `DirectionalLightComponent.h:17`, `ExponentialHeightFogComponent.h:16`), so
  all four are addable to a Blueprint's component list — the deliverable shape
  is legal by construction, not by hope.
- *sun angle* — `USceneComponent::RelativeRotation` is
  `EditAnywhere, BlueprintReadOnly` (`SceneComponent.h:142`), so it reads; the
  `GetRelativeRotation` UFUNCTION is tried first where codegen exposes it.
- *sun colour / brightness* — `Intensity` and `LightColor` are
  `BlueprintReadOnly` (`LightComponentBase.h:36,44`); `Temperature` and
  `bUseTemperature` are `EditAnywhere, BlueprintReadOnly`
  (`LightComponent.h:57,69`).
- *ambient* — `Intensity` as above; `bRealTimeCapture` is
  `EditAnywhere, BlueprintReadOnly` (`SkyLightComponent.h:108`).
- *fog* — `FogDensity` is `BlueprintReadOnly`
  (`ExponentialHeightFogComponent.h:22`); `bEnableVolumetricFog` and
  `VolumetricFogExtinctionScale` are `EditAnywhere, BlueprintReadOnly`
  (`:136,163`).
- *compile status* — `UBlueprint::Status` is
  `UPROPERTY(transient, BlueprintReadOnly)`; it is not serialized, so what is
  read is the compile state produced by loading the submitted asset, which is
  the property worth gating.

**Identity is by pre-declared content path and pre-declared subobject name,
never by class.** The asset path and the four names (`Sky`, `Ambient`, `Sun`,
`Fog`) are fixed by the spec and stated in the prompt. Class is consulted only
as the *assertion* — "is the thing named `Sun` really a directional light" — and
is written as `isinstance`, so a legitimate subclass is not penalized.

**Every band excludes the engine default.** This is the pass the plan's §12.6
added to the recipe after finding row R5 asserting `intensity == 5000`,
which is UE 5.8's constructor default for every local light and therefore grades
nothing. Audited here, default → band:

| property | UE 5.8 default | source | band | default inside band? |
|---|---|---|---|---|
| Sun `RelativeRotation.Pitch` | `0.0` | `FRotator::ZeroRotator` on a fresh `USceneComponent` | `[-25, -1]` | **no** |
| Sun `Intensity` | `10` | `DirectionalLightComponent.cpp` ctor | `[0.05, 5.0]` | **no** |
| Sun `LightColor` | `FColor::White` (255,255,255) | `LightComponent.cpp` (`ULightComponentBase`) | needs `R > G > B` | **no** (R == G == B) |
| Sun `bUseTemperature` / `Temperature` | `false` / `6500` | `LightComponent.cpp` (`ULightComponent`) | `true` AND `[1000, 4000]` | **no**, on both halves |
| Ambient `Intensity` | `1` | `SkyLightComponent.cpp` ctor | `[0.01, 0.6]` | **no** |
| Ambient `bRealTimeCapture` | `false` | `SkyLightComponent.cpp` ctor | must be `true` | **no** |
| Fog `FogDensity` | `0.02` | `ExponentialHeightFogComponent.cpp` ctor | `[0.1, 10.0]` | **no** (the floor is 5x the default) |
| Fog `bEnableVolumetricFog` | `false` | never assigned in the ctor → zero-initialised | must be `true` | **no** |
| Fog `VolumetricFogExtinctionScale` | `1.0` | `ExponentialHeightFogComponent.cpp` ctor | `>= 1.5` | **no** |

Nine graded numbers, nine live gates. A rig assembled from four freshly added,
untouched parts scores `5/14` — the presence checks and the compile check —
and fails every value check, which is exactly what the
`engine-default-fog/` and `default-white-sun/` variants demonstrate in
isolation.

**The 2026-07-27 widening, band by band.** The bands above are *not* the ones
this spec first shipped with. When the prompt restated every threshold
verbatim, a band only had to be *typed*; now that it is invisible, it has to be
*reachable from the description alone*. Five were re-cut on exactly that test,
and the dead-gate column above was re-run against every one of them:

| band | was | now | why it moved |
|---|---|---|---|
| Sun pitch | `[-20, -2]` | `[-25, -1]` | The far end is a taste boundary: 20° and 25° of elevation are the same sentence in prose ("just over the horizon", "raking almost level"), so failing a `-22` is failing an agent for a distinction the prompt cannot express. The near end exists *only* to exclude the `0.0` default — it has to be non-zero, not big — so it is relaxed to `-1` and a sun placed essentially on the horizon now passes. |
| Sun `Intensity` | `[0.5, 5.0]` | `[0.05, 5.0]` | **Ceiling deliberately unmoved.** It is the whole discrimination: `5.0` is half the `10` default, and "noticeably darker than an untouched one" means at most that. The floor's only job is to reject a sun switched off in all but name; `0.5` was doing a second job it was never asked to do — vetoing a *very* dim dawn, which is a legitimate reading of the prompt. `0.05` still rejects "off". |
| Ambient `Intensity` | `[0.05, 0.6]` | `[0.01, 0.6]` | Same argument, same shape. `0.6` is the "clearly weaker than the fill you get from that part left alone" boundary and stays; the floor drops to `0.01` so a deep pre-dawn fill is not failed for being too good at the thing that was asked for. |
| Fog `FogDensity` | `[0.2, 5.0]` | `[0.1, 10.0]` | The riskiest of the five. `0.1` is already visibly thick fog and is **5x** the `0.02` default — and it is a value an agent aiming at "swallow the distance" plausibly lands on, with nothing in the prompt to tell it `0.2` was wanted. The ceiling goes to `10.0` so over-delivering the described look is not a failure; there is no upper bound in the description, so an upper bound of `5` was arbitrary. Dead gate intact: the default is 5x below the new floor. |
| Fog `VolumetricFogExtinctionScale` | `>= 2.0` | `>= 1.5` | `2.0` was an author's round number, never a look boundary. The graded property is "turned up well above where it starts", and `1.5` is half again the `1.0` default: a raise an agent had to mean, still strictly excluding the untouched value. |

Two families were **left alone on purpose**. `sun_color_is_warm` is not widened
because "warm and red — red clearly ahead of green, green clearly ahead of
blue" or "a low, firelight-warm colour temperature" pins the target as tightly
as any number would, and both of its routes are already generous (`1000–4000` K
spans candle to tungsten; `R >= 150` with a `60` red/blue gap admits everything
from deep ember to pale amber). And every boolean check — `bRealTimeCapture`,
`bEnableVolumetricFog` — has no band to widen: the prompt describes each as a
behaviour ("keep re-reading the live sky", "simulated through the volume of the
world rather than a flat screen-depth tint") and the gate is the flag.

**Is the row still fair? Yes — and it is a better row than it was.** The
honest cost of hiding the rubric is that an agent can now produce a
recognisably correct dawn and still miss a band; the widenings above are sized
to make that a *taste* failure rather than a *psychic* one. What is bought in
exchange is the thing the row exists for: with the numbers on the page, all
nine value gates collapse into one skill — reading nine numbers out of a prompt
and typing them into a details panel — and an agent that has never heard of a
sky atmosphere can score `14/14`. With them hidden, passing requires knowing
which four parts make a dynamic sky, which property on each one is the quality
being described, and which direction the untouched value has to move. That is
the capability the *Primary concept* section claims this row measures, and it
is only actually measured in the second version.

**Why the sky atmosphere is presence-only.** `USkyAtmosphereComponent`'s
defaults are a complete, physically calibrated Earth atmosphere
(`SkyAtmosphereComponent.cpp` ctor sets Rayleigh/Mie/ozone coefficients from
real values), and a correct dawn does **not** require changing any of them — the
dawn colour comes from the *sun angle* through that atmosphere, which is graded
on the sun. Asserting a non-default Rayleigh scale would be a dead gate in the
opposite direction: it would fail the physically correct answer. Presence is a
real gate here regardless, because the start state has nothing.

**Why `saved` is not a separate check.** The source row's Verification cell asks
that the actors "exist". Dirtiness is not observable to this layer and does not
need to be: the runner grades a file overlay materialized onto a clean
substrate, so unsaved editor state never reaches the grader at all — an unsaved
edit presents as a missing asset and fails `rig_asset_exists`. The compile half
is asserted directly off the freshly loaded asset.

**Score granularity.** `registry.py:340-346` sets `tests_run`/`tests_passed`
from the per-check counts, so `report.json` already carries `x/14` for this
task. That number is **reported, not gating** — `overall` stays
`all(status == "pass")` (plan §3.2).

**The visual, and where it is allowed to live.** Drop `BP_DawnLighting` into a
level and a `--visible` run will show the dawn. That image is for a human to look at
and is **never** consulted by the gate; no L3 fixture, no R2 rubric, no
screenshot path reaches `overall`.

## Reference solution metadata

- LOC range: **0** lines of code. The deliverable is one new `.uasset`.
- Files touched: 1 created
  (`Content/Tasks/t1-dawn-fog-lighting-rig/BP_DawnLighting.uasset`), 0
  modified.
- Senior-dev hours: 0.3-0.75 (one Blueprint, four components added, nine
  property values set, compile and save — plus knowing which four components a
  dawn sky is made of).

## Anti-gaming notes

1. **One of the four parts quietly dropped.** *Failure mode*: the agent
   delivers a sun, an ambient fill and fog — the three obvious ones — and never
   adds the atmosphere, because the scene "looks lit" without it. *Defense*:
   `rig_sky_atmosphere_present` (`RIG_SKY_ATMOSPHERE_MISSING names=`) names the
   missing part and records the full list of names that *were* found, so the
   omission is legible rather than a bare count mismatch. Exercised by
   `discrimination/three-lights-no-atmosphere/`.
2. **Right name, wrong thing.** *Failure mode*: the agent produces four
   subobjects with the four required names but reaches for the wrong types — a
   point light called `Sun`, a plain scene component called `Sky` — and every
   name-only check passes. *Defense*: each presence check requires **name AND
   `isinstance` against the required component type**, and the type probe is
   tri-state: if the type is not exposed to Python at all the check FAILS
   (`RIG_SUN_LIGHT_TYPE_PROBE_ERROR`) rather than passing on the absence of an
   exception. An impostor dies at `RIG_SUN_LIGHT_WRONG_TYPE class=`, which also
   names the class it actually found. Exercised by
   `discrimination/named-not-typed/`.
3. **Lights added, sun never angled.** *Failure mode*: the agent adds all four
   correct parts, sets the colour and the fog, and leaves the sun pointing
   straight down (or at whatever the editor gave it) — a midday scene with dawn
   colours. *Defense*: `sun_angle_is_low_dawn` reads the sun part's **own
   relative rotation** and bands the pitch to `[-25, -1]` degrees
   (`SUN_PITCH_NOT_LOW world_pitch=`). The engine default is `0.0`, outside the band,
   so "never touched it" fails too. Exercised by
   `discrimination/overhead-noon-sun/`.
4. **Sun added, never made warm.** *Failure mode*: the agent adds a correctly
   angled, correctly dimmed sun and leaves it pure white, or claims in prose
   that it "set a warm dawn tone" without touching either colour route.
   *Defense*: `sun_color_is_warm` (`SUN_COLOR_NOT_WARM color=`) accepts either
   the filter-colour route or the colour-temperature route and **both branches
   exclude the engine default** — white fails `R > G > B`, and the temperature
   branch additionally requires `bUseTemperature` to be switched on, which
   defaults off. Prose cannot satisfy it: the verdict is read only from the
   submitted bytes. Exercised by `discrimination/default-white-sun/`.
5. **Fog present, at engine defaults.** *Failure mode*: the agent adds the fog
   part and stops, because a fog component is visibly "there" — the single
   cheapest way to appear to have done the atmospheric half. *Defense*: three
   independent fog checks, all pinned to **non-default** values on purpose:
   `fog_density_is_dense` (`FOG_DENSITY_TOO_THIN density=`, floor is 5x the
   `0.02` default), `fog_volumetric_enabled` (`FOG_VOLUMETRIC_DISABLED
   enabled=`, default `false`) and `fog_extinction_raised`
   (`FOG_EXTINCTION_TOO_LOW scale=`, default `1.0`). Exercised by
   `discrimination/engine-default-fog/`.

## Hidden invariants

- **Every numeric band excludes the property's engine default, by
  construction.** That is not a coincidence to be preserved by care; it is the
  table in *Verifier specification* and it is the reason this row grades
  anything at all. Any future edit that widens a band must re-run that column.
  The source row's own equivalent check family — row R5's
  `intensity == 5000` — is the counter-example: an assertion that reads
  thorough and cannot fail. (The 2026-07-27 widening did re-run it; see *The
  2026-07-27 widening, band by band*. The offline oracle
  `tools/verify-single/tests/test_introspect_dawn_fog.py` now asserts
  the exclusion mechanically, so the next widening cannot quietly swallow a
  default.)
- **No graded threshold may be moved into the agent-visible prompt.** The nine
  bands are discriminating *because* the agent cannot read them: with them on
  the page every value gate degrades into transcription and an agent with no
  lighting knowledge scores `14/14`. `prompt_extract.py`'s two-section
  allow-list is what keeps this section invisible, and
  `tools/verify-single/tests/test_prompt_no_rubric_leak.py` asserts that the
  extracted prompt contains **no digit at all** once the task id is removed —
  so a well-meaning "let's make the task clearer" edit fails a test instead of
  silently gutting the row.
- **The check denominator is fixed at 14 on every leg**, including the empty
  submission (which scores `0/14`, since this task ships no baseline for any
  check to pass against). A submission cannot improve its reported
  `tests_passed/tests_run` by making checks unreachable — the crash-shaped
  "fewer checks ran, so the ratio looks better" path is closed by construction.
- **A failed component resolution fans out to that component's value checks
  carrying the resolution's own token**, not three invented numeric failures.
  So the matrix always attributes an impostor or a missing part to one cause,
  and a wrong-reason FAIL is visible as an uncredited token rather than hidden
  behind a plausible-looking numeric verdict.
- **Error tokens are disjoint from failure tokens.** Every exception path emits
  `*_READ_ERROR` / `*_PROBE_ERROR` / `*_WALK_ERROR` / `*_TYPE_PROBE_ERROR` /
  `*_TEMPLATE_UNAVAILABLE` / `*_ABORTED`, none of which appears in any MATRIX
  row — so a broken UE API name can never be credited as a variant's named
  failure.
