---
id: t2-cutscene-camera-push-and-hero-rise
substrate: ThirdPerson
set: bp
tier: T2
capability_bucket: Technical Art
category: other
layers: [L1, L2I]
introspect: [cutscene_camera_push_and_hero_rise.py]
---

# t2-cutscene-camera-push-and-hero-rise

The second `layers: [L1, L2I]` task in the repo, and the first whose
deliverable is a **LevelSequence**. It follows the lane
`t1-hero-blueprint-copy-with-flashlight` opened: a committed-or-authored
`.uasset` under `Content/Tasks/<task-id>/`, one verifier-owned introspect
script asserting named structural checks, **no map, no fixture C++, no
scaffold actor**. Unlike the pilot it ships **no baseline asset at all** — the
agent creates the whole deliverable from nothing, so the only binaries this
task ever needs are the reference and the discrimination variants.

### Provenance and deliberate divergences from the source row

Imported from an earlier internal task list (not shipped): a sequencer row that
was never implemented there.
**The source row's `Verification` cell is EMPTY** — no acceptance criteria were ever
authored for this row, so everything under *Verifier specification* below is
designed here, not transcribed.

Five deliberate divergences, each recorded so the source row and the task can be
reconciled:

1. **Id.** The source row's `t8-` is a row index; this repo's `t<N>-` is a tier.
   Retiered to `T2` and re-slugged to the observable outcome
   (the set-provenance note (internal, not shipped)). The slug deliberately names the *shot* ("camera
   push", "hero rise"), never an editor operation.
2. **Content path.** The source row's `/Game/EvalTemplate/` **does not exist
   anywhere in the repo** (the only occurrence of that string is the source
   list), and a flat `/Game/EvalTemplate/` is outside every writable prefix of
   both substrates. Re-pathed to the repo convention `/Game/Tasks/<task-id>/`,
   which is agent-writable and fairness-pruned per task.
3. **The hero and the camera are carried BY the sequence, not placed in the
   level.** The source row opens with "in the current level, place a cube actor at
   the origin and name it `EvalHero`". Level state has **no grading route in
   this harness today** (plan §4/O3: `map_locator.locate_map` searches only
   `Content/Maps/`, an agent-authored `.umap` cannot be graded, and
   `apply_submission` cannot express a level edit). Rather than ship a half
   that grades nothing, the whole deliverable is scoped into the sequence
   asset: the sequence must **spawn its own** camera and its own `EvalHero`.
   That is not a workaround — it is a stronger, self-contained property, it is
   fully readable from the asset
   (`MovieSceneSequenceExtensions.get_spawnables`, which in 5.8 covers both
   the legacy `FMovieSceneSpawnable` array and `UMovieSceneSpawnableActorBinding`
   custom bindings), and it turns "add EvalHero to the sequence as well" into
   something a verifier can actually see. The API was checked before the row
   was designed; see *Read routes*.
4. **Six seconds at 24 fps, not the source row's five seconds at 30 fps.** Both
   source-row numbers are **engine defaults** and would grade nothing — see
   *Dead-gate audit* below. Six seconds and 24 fps ask for exactly the same
   capability (set the timeline length; set the display rate) while making
   both assertions real. **This is the one divergence a human should
   confirm**; reverting it is a three-constant edit in the introspect script,
   the prompt and `notes.md`, and it would knowingly restore two dead gates.
5. **Camera rotation is NOT graded.** "Facing toward the origin" from
   X = -500 is yaw/pitch/roll `(0,0,0)`, the default rotation of any actor —
   a third dead gate. The phrase stays in the prompt because it is how a human
   would describe the shot, and the spec says plainly that it is not gated.

> **Note on the behavior-only rule (Hard Rule #2).** Like
> `t1-hero-blueprint-copy-with-flashlight` and `t0-sanity-bp-log-on-beginplay`,
> this task names the concrete deliverable asset path and the one binding name
> the verifier keys on (`EvalHero`). That is the standard, precedented
> exception for asset-deliverable tasks whose whole point *is* producing a
> specific asset — naming the path lets the verifier load one asset directly
> instead of scanning content. Everything else in the prompt stays
> behavior-only: no class name, no track type name, no channel name, and no
> editor operation. "Brings its own camera and removes it when the shot ends"
> is the observable; *spawnable* is not said. "The viewer sees the whole shot
> through that camera" is the observable; *camera cut track* is not said.
> "Opens black and becomes fully visible" is the observable; *fade track* is
> not said.

## Primary concept

- `camera-actors` — Camera Actors
  (https://dev.epicgames.com/documentation/en-us/unreal-engine/camera-actors-in-unreal-engine)

**Recorded gap:** Sequencer / LevelSequence has **no in-scope row in
`tools/coverage/concepts.csv`**. The corpus deliberately excludes cinematics —
`cinematic-render-passes` and `movie-render-queue-runtime` are both
`in_scope=no` with the note *"orchestrator excludes cinematics"* — so the
load-bearing capability of this task (authoring a timeline asset with tracks,
sections, keyed channels and object bindings) is not enumerated anywhere in
Deliverable 1. `camera-actors` is listed above as the nearest in-scope
neighbour, not as an accurate label. If the the earlier internal task list keeps sending cinematics
rows, the concept corpus needs a Sequencer entry; that is a D1 decision, not
something this task can settle.

## Prompt given to the agent

> This project has no cutscene content. Produce exactly one new asset,
> `Content/Tasks/t2-cutscene-camera-push-and-hero-rise/SEQ_EvalCutscene`, and
> nothing else.
>
> It is a short cutscene, and it must be **entirely self-contained**: dropped
> into a completely empty level and played, it brings everything the shot
> needs into being and takes it away again when the shot ends. Nothing may be
> required to already exist in the level, and the cutscene may not depend on
> any object it did not bring itself.
>
> The shot:
>
> - It runs for exactly **six seconds**, and its timeline is counted in
>   **twenty-four frames per second**.
> - It brings its own **cinematic camera** — the kind with film-back and
>   focal-length controls, not a plain viewpoint — and for the entire six
>   seconds the viewer sees the shot through that camera and through nothing
>   else. There is one continuous view; the shot never cuts away and never
>   falls back to whatever camera the game would otherwise use.
> - The camera begins pulled back at X = -500, facing toward the origin, and
>   slowly pushes in until it reaches X = -150 exactly as the six seconds run
>   out.
> - It also brings its own simple stand-in for the hero — a plain box shape is
>   fine — and the cutscene refers to that object by the name `EvalHero`.
> - `EvalHero` starts at Z = 0, rises to Z = 200 over the first three seconds,
>   and then stays at that height for the remaining three.
> - The shot opens fully black and becomes fully visible over the first half
>   second.
>
> Save the asset when you are done.

## Workspace state pre-task

Substrate content that **exists** under
`Content/Tasks/t2-cutscene-camera-push-and-hero-rise/`:

- **nothing.** This task ships no baseline asset. The folder itself may not
  exist yet; creating it is part of the deliverable.
  `Content/Tasks/<task-id>/` is the agent-writable Content carve-out of the
  `ThirdPerson` substrate (`UE-projects/ThirdPerson/AGENT_WRITABLE.json`) and
  is where this task's content belongs; fairness isolation keeps this task's
  folder while hiding every other task's.

Files that **do not exist** (the agent must create):

- `Content/Tasks/t2-cutscene-camera-push-and-hero-rise/SEQ_EvalCutscene.uasset`.

Out of scope / not needed:

- No C++ is required or expected. No level, no placed actor, no functional
  test: the whole deliverable is one content asset. `Content/Maps/`,
  `Config/`, `Plugins/`, `ThirdPerson.uproject`, `Content/Characters/`,
  `Content/ThirdPerson/` and `Content/Input/` are deny-listed — the agent
  neither can nor needs to touch them. Every editor feature this task needs is
  already enabled in the stock project, so no plugin or project-settings change
  is possible **or** required.

## Verifier specification

Layer choice: this task grades via **L1 + L2I**. Every graded property is a
static property of a saved `.uasset` — a display rate, a playback range, which
tracks exist, one section's bounds, which bindings the sequence owns and
whether it spawns them, and the times and values of eleven keys on three
channels. All of it is read by verifier-owned editor-Python reflection over
the submitted asset, not by rendering, ticking, or a PIE world. L2 is
deliberately **not** declared: there is nothing to observe over time, and a
fixture would need a map and a placed actor this task has no use for. L3 is
not declared either — the visual is inspected by a human and never
gated (FR-020d, plan D3).

### L1 — Build

```text
assert: UnrealBuildTool exits 0 for BOTH "ThirdPersonEditor Win64 Development"
        and "ThirdPerson Win64 Development" (short-circuits on first failure)
```

The submission is content-only, so L1 is a precondition (the project and its
Asset Registry must load cleanly), never a correctness signal.

### L2I — Structural assertion

The verifier-owned script
`tools/verify-single/introspect/cutscene_camera_push_and_hero_rise.py` runs
headless via `UnrealEditor-Cmd -ExecutePythonScript=` under `-nullrhi`,
read-only, and prints one `CRAFTBENCH-INTROSPECT-JSON` verdict block. It emits
**exactly 12 named checks on every leg** (a constant denominator, so the
per-check `tests_passed/tests_run` the registry already records is comparable
across submissions). PASS requires all 12:

```text
sequence_asset_exists             /Game/Tasks/<id>/SEQ_EvalCutscene resolves AND
                                  loads as a level-sequence asset
sequence_display_rate_24fps       its display rate is exactly 24/1
sequence_spans_six_seconds        its playback range is 0.000s .. 6.000s (+/-0.02)
camera_cut_track_present          the sequence owns a camera-cut track with >=1
                                  section
camera_cut_covers_whole_shot      exactly ONE bounded cut section, spanning
                                  0.000s .. 6.000s (+/-0.02)
camera_cut_targets_cine_camera    the binding that cut points at animates a
                                  cinematic camera actor (or a subclass)
camera_spawned_by_sequence        that binding is one the SEQUENCE spawns, not a
                                  borrowed level actor
camera_pushes_in_over_full_shot   its Location.X curve reads -500 (+/-1) at
                                  t=0.0 and -150 (+/-1) at t=6.0, from >=2 keys
hero_binding_named_evalhero       a binding named exactly "EvalHero" exists
hero_spawned_by_sequence          that binding is one the SEQUENCE spawns
hero_rises_then_holds             its Location.Z curve reads 0 (+/-1) at t=0.0,
                                  200 (+/-1) at t=3.0 AND 200 (+/-1) at t=6.0,
                                  from >=2 keys
fade_in_from_black                the sequence owns a fade track whose curve
                                  reads 1.00 (+/-0.01) at t=0.0 and 0.00
                                  (+/-0.01) at t=0.5, from >=2 keys
```

### Dead-gate audit

A check that asserts an **engine default** passes for free and grades nothing.
Three of the source row's stated properties are exactly that shape, and all
three were confirmed against UE 5.8 engine source at `<UE-root>` before this
spec was written:

| source-row property | engine default | disposition |
|---|---|---|
| "five seconds long" | `UMovieSceneToolsProjectSettings::DefaultStartTime = 0.f`, `DefaultDuration = 5.f` (`MovieSceneToolsProjectSettings.cpp:9-10`), stamped onto every asset made by `ULevelSequenceFactoryNew::FactoryCreateNew` (`LevelSequenceFactoryNew.cpp`) | **retargeted to 6.000s** so the assertion is real |
| "thirty frames per second" | `ULevelSequenceProjectSettings::DefaultDisplayRate = "30fps"` (`LevelSequenceProjectSettings.cpp:11`), applied by `ULevelSequence::Initialize` (`LevelSequence.cpp:115-117`) | **retargeted to 24/1** so the assertion is real |
| "facing toward the origin" | a camera at X=-500 looking at the origin is yaw/pitch/roll `(0,0,0)`, the default rotation of any spawned actor | **not asserted at all**; recorded here so nobody "adds the missing check" later |
| "fade in **from black**" | `UMovieSceneFadeSection::UMovieSceneFadeSection()` sets `FadeColor(FLinearColor::Black)` (`MovieSceneFadeSection.cpp:16`) | the **colour** is not asserted; the fade *curve* (1.0 -> 0.0 over 0.5s) is, and it is not a default — a fresh fade section has no keys at all |

The retargeted numbers change no capability: "set the sequence length" and
"set the display rate" are still the things being asked for and still the
things being read.

### Read routes

Every route below was read out of UE 5.8 engine source under `<UE-root>`; the
whole family was additionally confirmed present on a live UE 5.8.0-55116800
headless editor (plan §10.1). None is guessed.

- **Plugin availability.** `MovieSceneSequenceExtensions` and friends live in
  the `SequencerScripting` plugin, whose own `.uplugin` carries **no**
  `EnabledByDefault`. It is nevertheless live in both substrates because
  `LevelSequenceEditor.uplugin` is `"EnabledByDefault": true` and declares
  `"Plugins": [{"Name": "SequencerScripting", "Enabled": true}]`. This matters
  because `Plugins/` and `ThirdPerson.uproject` are deny-listed, so an agent
  could not have enabled it and a verifier must not need it enabled by hand.
- *asset* — `EditorAssetLibrary.does_asset_exist` / `load_asset`, then a
  positive `isinstance(asset, unreal.LevelSequence)`.
- *timeline* — `MovieSceneSequenceExtensions.get_display_rate` (an `FFrameRate`
  whose `Numerator`/`Denominator` are `BlueprintReadWrite` in
  `NoExportTypes.h:2175-2185`), `get_playback_start_seconds` /
  `get_playback_end_seconds`, `get_tick_resolution`.
- *tracks* — `get_tracks` for root tracks (camera cut, fade);
  `MovieSceneBindingExtensions.get_tracks` for a binding's own tracks, plus
  `get_child_possessables` so a transform keyed on the root-component child
  binding is found too. Type matching is `isinstance` against
  `unreal.MovieSceneCameraCutTrack` / `MovieSceneFadeTrack` /
  `MovieScene3DTransformTrack`, so a subclass is accepted.
- *sections* — `MovieSceneTrackExtensions.get_sections`, then
  `MovieSceneSectionExtensions.has_start_frame` / `has_end_frame` /
  `get_start_frame_seconds` / `get_end_frame_seconds`. The `has_*` probes are
  load-bearing: the seconds accessors return **`-1.0`** on an unbounded
  section rather than raising (`MovieSceneSectionExtensions.cpp:61-73`).
- *the cut's target* — `UMovieSceneCameraCutSection::GetCameraBindingID` is a
  `UFUNCTION(BlueprintPure)` (`MovieSceneCameraCutSection.h:40-44`) and the
  underlying `CameraBindingID` is `UPROPERTY(EditAnywhere)`, so both routes
  are readable; `FMovieSceneObjectBindingID::Guid` is `UPROPERTY(EditAnywhere)`
  (`MovieSceneObjectBindingID.h:404-405`). The guid is matched against
  `MovieSceneBindingExtensions.get_id` over `get_bindings`.
- *spawn ownership* — `MovieSceneSequenceExtensions.get_spawnables`, which
  unions the legacy `FMovieSceneSpawnable` array **and** every
  `UMovieSceneSpawnableActorBinding` custom binding
  (`MovieSceneSequenceExtensions.cpp:745-778`), so the check does not depend
  on which representation the agent's tooling produced.
- *the bound object's type* — `MovieSceneBindingExtensions.get_object_template`
  (which reaches `MovieSceneHelpers::GetObjectTemplate`,
  `MovieSceneCommonHelpers.cpp:1038-1063`, handling both spawnable shapes),
  falling back to `get_possessed_object_class` for a possessable.
- *keys* — `MovieSceneSectionExtensions.get_channel(section, "Location.X")`
  (the channel metadata names registered at
  `MovieScene3DTransformSection.cpp:83, 842`), then `channel.get_keys()`, then
  `key.get_time(unreal.MovieSceneTimeUnit.TICK_RESOLUTION)` and
  `key.get_value()`. Times are divided by the sequence's tick resolution, so
  no sub-frame rounding enters any comparison.
- *the fade curve* — **not** by name. `UMovieSceneFadeSection` registers its
  float curve with a default-constructed `FMovieSceneChannelMetaData()`
  (`MovieSceneFadeSection.cpp:35`), i.e. `NAME_None`, so
  `get_channel(section, "Fade")` cannot work; `get_all_channels` is used
  instead. The same section's constructor calls
  `SetRange(TRange<FFrameNumber>::All())`, so it is **infinite** and its
  bounds are meaningless — the fade is graded on its keys alone.

**Identity is by pre-declared content path and pre-declared binding name,
never by class.** The asset path and the name `EvalHero` are fixed by the spec
and stated in the prompt. The agent may build the sequence by any route, use
any mesh for the hero, subclass the camera, add extra tracks it finds useful,
and key the transforms on the actor binding or on its root-component child —
none of that is penalized.

**Why the curves are EVALUATED, not key-matched.** "Rise to Z=200 by t=3 and
hold" is correctly authored either as two keys (`0s->0`, `3s->200`) or as three
(`0s->0`, `3s->200`, `6s->200`); Sequencer holds the last key's value forever
after it. Demanding a key at t=6 would fail the first, perfectly good
solution. So the script builds the key list and evaluates it piecewise-linearly
with constant extrapolation, then asserts the value at t=0, t=3 and t=6. This
still fails the interesting wrong answer — a single straight ramp 0->200 across
the whole six seconds reads **100** at t=3, a hundred times the tolerance away.

**Why `saved` is not a separate check.** Dirtiness is not observable to this
layer and does not need to be: the runner grades a file overlay materialized
onto a clean substrate, so unsaved editor state never reaches the grader at
all — an unsaved sequence presents as no asset and fails `sequence_asset_exists`.

**Score granularity.** `registry.py:340-346` sets `tests_run`/`tests_passed`
from the per-check counts, so `report.json` already carries `x/12` for this
task. That number is **reported, not gating** — `overall` stays
`all(status == "pass")` (plan §3.2).

## Reference solution metadata

- LOC range: **0** lines of code. The deliverable is one new `.uasset`.
- Files touched: 1 created
  (`Content/Tasks/t2-cutscene-camera-push-and-hero-rise/SEQ_EvalCutscene.uasset`),
  0 modified.
- Senior-dev hours: 0.5-1.0 (create the sequence, set rate and length, add two
  spawned bindings, add a cut track and a fade track, key three channels,
  save — plus checking that the "hold" really holds and that nothing leaked
  into the level).

## Anti-gaming notes

1. **A correctly-shaped empty timeline.** *Failure mode*: the agent creates
   `SEQ_EvalCutscene`, sets the length and the frame rate — the two cheapest,
   most visible properties — and stops, or adds tracks with no sections. The
   asset then *looks* right in the content browser and in any screenshot of
   the Sequencer tab. *Defense*: nine of the twelve checks read past the
   timeline header. `camera_cut_track_present` fails first
   (`CAMERA_CUT_TRACK_MISSING tracks=`), and the four camera checks, the three
   hero checks and the fade check all fail behind it, so a partial fix cannot
   quietly pass.
2. **A camera borrowed from the level instead of carried by the shot.**
   *Failure mode*: the agent drops a camera into the current level and
   possesses it from the sequence. This is the path of least resistance in
   every editor flow, it looks identical when scrubbed, and it makes the
   deliverable silently un-portable — the asset alone no longer produces the
   shot. *Defense*: `camera_spawned_by_sequence`
   (`CAMERA_BINDING_NOT_SPAWNABLE name=`) resolves the cut's binding guid
   against `get_spawnables`. Note the pair is deliberately split from
   `camera_cut_targets_cine_camera`: a possessed cine camera passes the *type*
   check and fails only the *ownership* one, so the matrix can tell "wrong
   camera" from "wrong ownership".
3. **A cut that is present but does not actually cover the shot.** *Failure
   mode*: the cut section is left at whatever length the editor created, or
   the agent adds two cuts, or leaves the section unbounded — the viewer then
   drops back to the game camera partway through, which no static inspection
   of "is there a camera cut track" would catch. *Defense*:
   `camera_cut_covers_whole_shot` requires **exactly one** section, requires it
   to be **bounded** (`has_start_frame`/`has_end_frame` — the seconds accessors
   return `-1.0` rather than raising on an unbounded section, so a naive check
   would read `-1.0` and could not distinguish it), and requires its bounds to
   be `0.000s..6.000s`.
4. **Motion faked by a section rather than by keys, or by the wrong curve
   shape.** *Failure mode (a)*: the transform section spans the whole shot but
   carries one key or none, so nothing moves while the timeline "looks"
   animated. *Failure mode (b)*: the hero is ramped 0->200 across all six
   seconds instead of rising by t=3 and holding — visually plausible, and it
   satisfies both endpoint values. *Defense*: both curves are **evaluated**,
   not merely counted. `camera_pushes_in_over_full_shot`
   (`CAMERA_PUSH_IN_KEYS_WRONG keys=`) needs >=2 keys and needs the curve to
   read -500 at t=0 **and** -150 at t=6, which one constant key cannot do;
   `hero_rises_then_holds` (`HERO_RISE_KEYS_WRONG keys=`) additionally samples
   the **midpoint** t=3, where the straight ramp reads 100 against a tolerance
   of 1.0.
5. **A fade that is the wrong way round, or is only a coloured section.**
   *Failure mode*: the agent adds a fade track and leaves it unkeyed (the
   section is infinite and black by construction, so it *is* a valid-looking
   fade section that does nothing), or keys it `0.0 -> 1.0` and produces a fade
   **to** black. *Defense*: `fade_in_from_black` (`FADE_IN_KEYS_WRONG keys=`)
   requires >=2 keys and requires the curve to read `1.00` at t=0 and `0.00` at
   t=0.5 — the polarity is the assertion. The fade **colour** is deliberately
   not asserted because black is the constructor default
   (`MovieSceneFadeSection.cpp:16`) and would be a dead gate.

## Hidden invariants

- The check denominator is fixed at 12 on every leg, including the empty
  submission. A submission cannot improve its reported `tests_passed/tests_run`
  by making checks unreachable — the crash-shaped "fewer checks ran, so the
  ratio looks better" path is closed by construction.
- Every exception path in the introspect script emits a distinct
  `*_READ_ERROR` / `*_PROBE_ERROR` / `*_LOAD_ERROR` / `*_UNRESOLVED` /
  `*_ABORTED` token that appears in **no** discrimination-matrix row, so a
  broken UE API name can never be credited as a variant's named failure. It
  surfaces as an uncredited FAIL, which is the signal the author wants.
- Nothing in this task is graded against the level. If an agent *also* places
  a cube in the current level (which the source row asked for), that is
  neither rewarded nor punished — it simply cannot reach the grader, because
  `Content/Maps/` is deny-listed and a level edit is not expressible as a
  submission overlay.
