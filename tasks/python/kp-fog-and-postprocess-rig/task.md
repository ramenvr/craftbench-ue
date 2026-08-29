---
id: kp-fog-and-postprocess-rig
substrate: ThirdPerson
set: python
tier: T1
capability_bucket: Tools & Pipeline
category: lighting
layers: [L1, L2I]
introspect: [kp_fog_and_postprocess_rig.py]
---

# kp-fog-and-postprocess-rig

The first task of the new `tasks/python/` basket (owner decision 2026-08-11):
**outcome-graded** — the deliverable is the resulting editor state (here: a
saved level), graded by the existing deterministic L2I introspect lane exactly
like the `bp` basket. The prompt describes an outcome whose exactness (nine
exact property values across three actors) makes editor scripting the natural
way to complete it, but **no gate asserts that Python was used** — hybrid and
task-dependent by design. A future v2 may re-execute submitted scripts; not
this version (`tasks/README.md`, basket definition).

It is also the first task whose L2I introspect **loads a map**. The introspect
lane launches `UnrealEditor-Cmd -ExecutePythonScript= -nullrhi` with no map
argument (`layers/l2_introspect.py` builds the command line; `map_locator` is
never consulted by L2I), so the verifier script loads the submitted level
itself — `_load_level` in
`tools/verify-single/introspect/kp_fog_and_postprocess_rig.py`, two routes,
fail-closed, world-identity-verified. **This is the pattern-to-prove**: no
shipped introspect did it before this task, and the headless `-nullrhi` level
load was still listed as an open probe (plan U1) when
`t1-dawn-fog-lighting-rig` scoped itself down to an asset deliverable to avoid
it. The level-deliverable lane this task uses became legal on 2026-07-29, when
the OFPA carve-out (`Content/__ExternalActors__/Tasks/` +
`Content/__ExternalObjects__/Tasks/` in
`UE-projects/ThirdPerson/AGENT_WRITABLE.json`) made an agent-authored
`/Game/Tasks/<id>/` level submittable.

### Provenance and deliberate divergences from the source row

Imported from an earlier internal task list (not shipped): a lighting row, one
of a group derived from observed editor-scripting-agent failures. Full
divergence record: `notes.md` section 2. The load-bearing
ones:

1. **The source row's prompt names UE Python APIs verbatim** (`fog_density`,
   `set_editor_property`, `unreal.Vector4`, "using Python", spelling-probe
   advice for the inscattering colour). Hard Rule #2 forbids all of it in the
   agent-visible prompt, so every requirement is rewritten as an observable
   outcome. The **numbers stay** — exact values in the prompt are this
   basket's point, and the verifier gates on tolerance bands around exactly
   the numbers the prompt states.
2. **Vignette moved 0.45 → 0.6.** The source row's 0.45 sits 0.05 from the UE 5.8
   engine default (0.4, `Scene.cpp:541`); a readable tolerance band around it
   could not exclude the default without becoming tighter than float-typed
   transcription deserves. 0.6 keeps the band `[0.55, 0.65]` honest.
3. **Scoped to nine graded values.** The source row also sets fog max-opacity,
   start-distance, volumetric flags, colour-contrast and the sky light's
   lower-hemisphere colour. Dropped: the lower-hemisphere target
   `(0.005, 0.008, 0.02)` is un-dead-gateable (within noise of the `(0,0,0)`
   default), and the rest would push past a stable 14-check denominator
   without adding a new capability. Recorded per-property in `notes.md`.
4. **"Print a verification summary" is dropped.** Printed prose grades
   nothing here: the grader reads only the saved bytes of the submission
   overlay, never the agent's stdout (anti-gaming note 5).
5. **Start state.** The source row says "Empty Project" / "the current level";
   this repo's convention is the `ThirdPerson` substrate with the deliverable
   authored at `/Game/Tasks/<task-id>/`.

> **Note on the behavior-only rule (Hard Rule #2).** Like
> `t1-dawn-fog-lighting-rig`, this task names the concrete deliverable path
> (`Content/Tasks/kp-fog-and-postprocess-rig/`, level `L_FogRig`) and the
> three actor labels (`Fog`, `Mood`, `Ambient`) the verifier keys on — the
> standard, precedented exception for asset-deliverable tasks. Everything
> else stays behavior-only: **no UE class name, no API name, no editor
> operation name appears in the prompt.** The three parts are described by
> what they do (ground fog that swallows distance; a region that re-grades
> what the camera sees; the sky-driven fill light), never by class. Unlike
> the dawn task, the **numeric targets DO appear in the prompt** — that is
> the python basket's charter, and the graded capability is "hit many exact
> values across editor state", not "guess where the band lies".

## Primary concept

- `ps-scripting-editor-python` — Scripting the Unreal Editor Using Python
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/scripting-the-unreal-editor-using-python)

The load-bearing capability is driving the editor to produce **exact,
verifiable editor state in bulk**: spawn the right three environment actors
into a new level, address the correct property on each (including the
post-process settings struct with its per-property override flags — the
classic trap where a value written without its flag is silently inert), hit
nine exact values, and save everything the level references. The prompt never
requires scripting, but nine exact values across three actors and a
write-back-sensitive settings struct is exactly the shape where the editor
Python route is the natural one — which is what this basket exists to
measure. The adjacent concept is `ps-levels` (Levels,
https://dev.epicgames.com/documentation/en-us/unreal-engine/levels-in-unreal-engine):
the deliverable is a saved level, not a loose asset.

## Prompt given to the agent

> The folder `Content/Tasks/kp-fog-and-postprocess-rig/` is empty, and the
> project ships no graded night scene of its own.
>
> Author and save one level asset in that folder, named `L_FogRig`. The level
> must contain three configured objects, identified by the labels `Fog`,
> `Mood` and `Ambient`, that together give the scene a cold, dim, heavily
> graded look. Every value below must be hit exactly as written — close does
> not count:
>
> - **`Fog`** — ground fog that sits in the world itself, thickest near the
>   ground and thinning with height, swallowing the distance. Its overall
>   thickness value must be exactly `0.03`; the rate at which it thins with
>   height must be exactly `0.15`; and the colour it scatters back toward the
>   camera must be a deep night blue — red `0.02`, green `0.04`, blue `0.10`,
>   at full alpha.
> - **`Mood`** — a region that re-grades everything the camera sees, and
>   whose influence must cover the whole world, not just the space inside its
>   own bounds. Four of its picture adjustments must be deliberately switched
>   on — each explicitly marked as an intentional override of the inherited
>   look, not left in its untouched "inherit" state — and set exactly: the
>   glow that bright spots bleed into their surroundings raised to `1.8`; the
>   darkening toward the corners of the frame set to `0.6`; the per-channel
>   colour saturation scaled to red `0.85`, green `0.88`, blue `0.95`; and
>   the camera's automatic brightness adaptation biased half a stop darker,
>   to `-0.5`.
> - **`Ambient`** — the soft fill light that takes its illumination from the
>   sky, with its brightness set to exactly `0.2`.
>
> Save the level and everything it references, so that every value above can
> be read back from the saved files alone.

## Workspace state pre-task

Substrate content that **exists** under
`Content/Tasks/kp-fog-and-postprocess-rig/`:

- Nothing. This task ships **no baseline asset**. The folder is the
  agent-writable Content carve-out of the `ThirdPerson` substrate
  (`UE-projects/ThirdPerson/AGENT_WRITABLE.json` lists `Content/Tasks/`
  under both `writable` and `asset_writable`); fairness isolation keeps this
  task's folder while hiding every other task's.

Files that **do not exist** (the agent must create):

- `Content/Tasks/kp-fog-and-postprocess-rig/L_FogRig.umap` — the graded
  level (plus whatever sidecar files saving it produces there).
- If the level is saved with One File Per Actor (the editor default), its
  actors land under `Content/__ExternalActors__/Tasks/kp-fog-and-postprocess-rig/`
  and `Content/__ExternalObjects__/Tasks/kp-fog-and-postprocess-rig/` — both
  are `asset_writable` (the 2026-07-29 OFPA carve-out), so the whole file set
  is submittable. Mirrors of any OTHER map reject by allowlist-miss.

Out of scope / not needed:

- No C++ is required or expected. `Content/Maps/`, `Content/ThirdPerson/`,
  `Content/Characters/`, `Content/Input/` and the variant content dirs are
  deny-listed — the agent neither can nor needs to touch them.

## Verifier specification

Layer choice: **L1 + L2I**. Every graded property is a static property of a
saved level (which actors exist, what type each is, and nine numbers across
them), read by verifier-owned editor-Python reflection after loading that
level headless. L2 is deliberately **not** declared: there is nothing to
observe over time, and an L2 fixture must live in a committed
`Content/Maps/` map, which an agent-authored level can never be. L3 is not
declared: the look is never rendered or graded (FR-020d — deterministic gate,
no pixels).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

The submission is content-only, so L1 is a precondition (the project must
load cleanly), never a correctness signal.

### L2I — Structural assertion over the loaded level

The verifier-owned script
`tools/verify-single/introspect/kp_fog_and_postprocess_rig.py` runs headless
via `UnrealEditor-Cmd -ExecutePythonScript=` under `-nullrhi`, read-only, and
prints one `CRAFTBENCH-INTROSPECT-JSON` verdict block. It emits **exactly 14
named checks on every leg** (constant denominator; the empty submission
scores `0/14`). PASS requires all 14:

```text
level_asset_exists            /Game/Tasks/<id>/L_FogRig resolves
level_loads_clean             the level LOADS into the headless editor and the
                              loaded editor world's package path is the graded
                              level (wrong-world fails; every downstream check
                              fans out from a load failure)
fog_actor_present             exactly one actor labelled "Fog" exists AND is a
                              height-fog actor (isinstance, subclass-tolerant)
fog_density_exact             fog thickness in [0.025, 0.035]   (target 0.03)
fog_falloff_exact             height falloff in [0.13, 0.17]    (target 0.15)
fog_color_night_blue          inscattering colour RGB within 0.01 per channel
                              of (0.02, 0.04, 0.10)
ppv_actor_present             exactly one actor labelled "Mood" exists AND is
                              a post-process volume
ppv_is_unbound                the volume's influence is unbound (whole-world)
ppv_bloom_overridden          bloom override flag ON AND intensity in
                              [1.7, 1.9]                        (target 1.8)
ppv_vignette_overridden       vignette override flag ON AND value in
                              [0.55, 0.65]                      (target 0.6)
ppv_saturation_overridden     saturation override flag ON AND XYZ within 0.02
                              of (0.85, 0.88, 0.95)
ppv_exposure_bias_overridden  exposure-bias override flag ON AND value in
                              [-0.6, -0.4]                      (target -0.5)
skylight_actor_present        exactly one actor labelled "Ambient" exists AND
                              is a sky light
skylight_intensity_exact      sky light intensity in [0.15, 0.25] (target 0.2)
```

**Identity is by pre-declared content path and pre-declared actor label,
never by class.** The level path and the three labels are fixed by the spec
and stated in the prompt. Class is consulted only as the *assertion* ("is the
thing labelled `Mood` really a post-process volume"), written as
`isinstance`, so a legitimate subclass is not penalized. Duplicate labels
fail (ambiguity is never resolved silently), and label resolution is
conjoined with the positive existence chain that precedes it: asset exists →
level loads → world identity matches → actor walk.

**Read routes** (each verified against its UE 5.8 `UPROPERTY` declaration on
2026-08-11; Python readability per `PropertyAccessUtil.cpp:425-433`):

- *level load* — `LevelEditorSubsystem.load_level` (route 1) /
  `EditorLoadingAndSavingUtils.load_map` (route 2), then the loaded editor
  world's `get_path_name()` must begin with the graded asset path. A truthy
  load return is never trusted alone.
- *actor walk* — `EditorActorSubsystem.get_all_level_actors` (legacy
  `EditorLevelLibrary` fallback); labels via `get_actor_label()`.
- *fog* — `FogDensity` / `FogHeightFalloff` / `FogInscatteringLuminance` are
  `BlueprintReadOnly, interp` (`ExponentialHeightFogComponent.h:22-43`),
  read off the actor's height-fog component.
- *post-process volume* — `Settings` is `UPROPERTY(interp)`
  (`PostProcessVolume.h:27`; `interp` implies `CPF_Edit`), `bUnbound` is
  `EditAnywhere, BlueprintReadWrite` (`:50-51`). Inside
  `FPostProcessSettings`, every graded value member is
  `interp, BlueprintReadWrite` and every `bOverride_*` flag is
  `EditAnywhere, BlueprintReadWrite` (`Scene.h:726-727, 819-820, 937, 1015,
  1628-1629`).
- *sky light* — `Intensity` on the sky-light component
  (`ULightComponentBase`, `BlueprintReadOnly`).

**Every band excludes the UE 5.8 engine default** (the dead-gate discipline,
audited from engine source at `<UE-root>/Engine/Source/Runtime/Engine/` on
2026-08-11):

| property | UE 5.8 default | source | band | default inside band? |
|---|---|---|---|---|
| Fog `FogDensity` | `0.02` | `ExponentialHeightFogComponent.cpp:92` | `[0.025, 0.035]` | **no** |
| Fog `FogHeightFalloff` | `0.2` | `:93` | `[0.13, 0.17]` | **no** |
| Fog `FogInscatteringLuminance` | `FLinearColor::Black` | `:76` | RGB within `0.01` of `(0.02, 0.04, 0.10)` | **no** (blue alone is 10x the tolerance from 0) |
| PPV `bUnbound` | `false` | zero-init; ctor sets only `bEnabled` (`PostProcessVolume.cpp:21`) | must be `true` | **no** |
| PPV `bOverride_*` (all four) | `false` | `FMemory::Memzero` (`Scene.cpp:398-402`) | must be `true` | **no** |
| PPV `BloomIntensity` | `0.675` | `Scene.cpp:458` | `[1.7, 1.9]` | **no** |
| PPV `VignetteIntensity` | `0.4` | `Scene.cpp:541` | `[0.55, 0.65]` | **no** (why the source row's 0.45 was re-cut) |
| PPV `ColorSaturation` | `(1, 1, 1, 1)` | `Scene.cpp:408` | XYZ within `0.02` of `(0.85, 0.88, 0.95)` | **no** |
| PPV `AutoExposureBias` | cvar `r.DefaultFeature.AutoExposure.Bias` (non-negative) | `Scene.cpp:516-519` | `[-0.6, -0.4]` | **no** (band is strictly negative) |
| SkyLight `Intensity` | `1.0` | `ULightComponentBase` (dawn audit) | `[0.15, 0.25]` | **no** |

Each override gate is dead-gate-safe **twice**: the flag defaults off AND the
value defaults outside the band, and the check conjoins both — so neither
"flipped the flag, never set the value" nor "set the value, never flipped the
flag" can pass.

**The bands are tolerances, not hidden rubric.** Unlike
`t1-dawn-fog-lighting-rig` (whose whole discrimination rests on the agent not
knowing the numbers), this task *tells* the agent every target — the basket
grades exact-outcome execution, not taste. The band half-widths are sized for
float-typed transcription slack, and each still excludes its engine default,
which is what keeps an untouched actor at zero credit.

**Alpha / W channels are not graded** where the target equals the observable
default (fog-colour alpha, saturation W) — a gate there would either be dead
or grade nothing the prompt asked for. Recorded under accepted residuals.

**Score granularity.** `registry.py` reports `tests_passed/tests_run` from
the per-check counts, so `report.json` carries `x/14`; `overall` stays
all-checks-pass. This replaces the source row's "% of verification checks passed"
metric; its "# of tool calls to reach success" efficiency metric has no
harness signal and is dropped (`notes.md`).

## Reference solution metadata

- LOC range: **0** shipped lines of code. The deliverable is a saved level;
  the reference was produced by a throwaway editor-Python script of ~120
  lines (`aids/author_reference.py`), which is an authoring aid, not part of
  the solution.
- Files touched: 1 level asset created
  (`Content/Tasks/kp-fog-and-postprocess-rig/L_FogRig.umap`) plus its OFPA
  actor sidecars (typically 3-6 files under `Content/__ExternalActors__/Tasks/…`).
- Senior-dev hours: 0.3-0.75 (new level, three actors spawned and labelled,
  nine values set — including knowing the post-process settings struct needs
  its per-property override flags — save).

## Anti-gaming notes

Per the amended checklist section 7 (2026-08-11), each note names its defense
with a resolvable pointer; variants are authored only for holes the
requirements table (`discrimination/MATRIX.md`) actually finds.

1. **Nothing submitted / level never saved.** *Failure mode*: the agent works
   in the editor but never saves, or saves elsewhere. *Defense*: the runner
   grades a file overlay materialized onto a clean substrate, so unsaved
   state presents as a missing asset and fails `level_asset_exists`
   (`RIG_LEVEL_MISSING path=` — `kp_fog_and_postprocess_rig.py::_rig_checks`),
   and all 13 remaining checks fan out on that single root cause. This is the
   automatic empty-leg FAIL in `discrimination/MATRIX.md`.
2. **Right label, wrong thing.** *Failure mode*: three actors carry the three
   required labels but the wrong types — a point light labelled `Ambient`, a
   trigger box labelled `Mood`. *Defense*: each presence check requires
   **exactly-one-label AND `isinstance`** against the required actor type
   (`_resolve_actor`), and the type probe is tri-state — an unevaluable probe
   FAILS (`PPV_ACTOR_TYPE_PROBE_ERROR class=`) rather than passing on the
   absence of an exception. An impostor dies at
   `PPV_ACTOR_WRONG_TYPE class=`, which names the class actually found.
3. **Settings written, overrides never flipped** — the classic post-process
   trap, and the exact failure the source list's editor-scripting sessions
   exhibited. *Failure mode*: the agent writes the four values into the
   settings struct but never marks them as overridden, so the level renders
   as if untouched — or flips the flags and never writes the values.
   *Defense*: each of the four override checks conjoins **flag AND band in
   one check** (`_flag_scalar_check`;
   `PPV_BLOOM_NOT_SET override=` / `PPV_VIGNETTE_NOT_SET override=` /
   `PPV_SATURATION_NOT_SET override=` / `PPV_EXPOSURE_NOT_SET override=`),
   and both halves' engine defaults are excluded (dead-gate table above).
4. **Actors spawned, values left default.** *Failure mode*: the three right
   actors exist and the submission banks on presence checks carrying the
   score. *Defense*: 9 of the 14 checks are value gates and **every band
   excludes the engine default** (dead-gate table; e.g.
   `FOG_DENSITY_OFF_TARGET density=`, `SKYLIGHT_INTENSITY_OFF_TARGET value=`).
   An untouched trio scores at most `5/14` and `overall=fail`.
5. **Prose/print gaming.** *Failure mode*: the source row's own verification was
   "print back every value", which a submission could satisfy by printing the
   expected numbers without setting them. *Defense*: the grader never reads
   agent output — every verdict is computed from the saved bytes of the
   submission overlay, loaded fresh (`_load_level` + reflection reads), and
   the world-identity check (`LEVEL_WRONG_WORLD world=`) stops a submission
   from redirecting the read to some other, pre-lit level.

### Accepted residuals

- **Extra actors are tolerated.** The level may contain helper actors beyond
  the graded three; only ambiguity on a graded label (duplicates) fails.
  Outcome-graded: extras change nothing the spec asks for.
- **How the agent authored it is ungraded by design** — hand-editing in a
  live editor, editor Python, or MCP tooling all pass identically. The
  basket's charter (owner decision 2026-08-11) is outcome-grading; no gate
  asserts "python was used".
- **Ungraded properties**: fog max-opacity, start-distance and volumetric
  settings; colour-contrast; the sky light's lower-hemisphere colour and
  mobility; every actor's transform. The prompt does not ask for them
  (divergence 3), so no gate polices them.
- **Fog-colour alpha and saturation W** are read but not gated (target equals
  default / observably inert; see the verifier note above).
- **The look itself is never rendered or graded** — `-nullrhi`, no pixels, no
  screenshot. That image is for humans and never reaches `overall`.

## Hidden invariants

- **The check denominator is fixed at 14 on every leg**, including the empty
  submission (`0/14` — this task ships no baseline for any check to pass
  against). A submission cannot improve its reported ratio by making checks
  unreachable; a crashed walk fans out failures rather than shrinking the
  list.
- **Error tokens are disjoint from failure tokens.** Every exception path
  emits `*_READ_ERROR` / `*_PROBE_ERROR` / `*_WALK_ERROR` / `*_LOAD_ERROR` /
  `*_ABORTED`, none of which appears in any MATRIX row — a broken UE API name
  (a real risk on this task's unproven map-load pattern) can never be
  credited as a variant's named failure.
- **A failed actor resolution fans out to that actor's value checks carrying
  the resolution's own token**, never invented numeric failures — the matrix
  always attributes an impostor or a missing actor to one cause.
- **Every numeric band excludes the property's engine default, by
  construction** (the dead-gate table in *Verifier specification*). Any
  future band edit must re-run that column against engine source — the
  vignette re-cut (divergence 2) is the worked example of why.
